# SCRIPT_STATUS: ACTIVE — NF integration P4b: per-stock decision driver
"""NF per-stock decision driver (integration unit P4b, Tier-2).

The thin orchestration above the hardened doors — per (stock, cutoff):
P3b assemble → `record_decision` → `execute_news_decision` (factor + penalty LLM
legs) → `seal_decision_archive`. Everything security-bearing lives BELOW this
module (the P4a doors + the executors); the driver adds identity discipline,
committed-evidence sourcing, and crash-safe idempotent re-entry.

Declared invariants (Tier-2; see NF_UNIT_P4_DESIGN.md):

1. **Deterministic decision identity.** `decision_id = nf:{ingest_class}:{ts_code}:
   {cutoff_iso}` — the same (stock, cutoff, class) always claims the same ledger
   slot, so re-runs meet first-write-wins instead of minting parallel decisions.
2. **Committed evidence only.** The driver's P3b inputs come from
   `resolve_committed_evidence` (the SAME trusted-root resolution the record door
   re-runs) — a driver artifact is by construction the one the door will prove.
3. **One object flow.** The SAME `(artifact, assembly)` pair flows
   assemble → record → execute → seal; the driver never re-assembles between steps.
4. **Crash-safe idempotent re-entry, with audit backfill, under a per-decision
   flow lock** (P4b review P1 + re-review#2 P1). The whole write-bearing flow
   (record → commitment enumeration/backfill → success check → execute → seal)
   runs inside ONE cross-process per-`decision_id` lock, so driver flows for
   the same decision are fully serialized — a concurrent commitment can never
   land between this task's snapshot and its return (it either precedes the
   snapshot and is backfilled now, or its whole flow runs after ours and
   backfills itself). On every entry, EVERY committed execution whose
   per-execution archive is missing — success OR hard_failed — is recovered
   from pure disk state via `recover_and_seal_execution_archive` BEFORE any
   resume or retry. Then: an existing SUCCESS commitment is never re-executed;
   a hard_failed one does NOT block a fresh retry. The lock guards DRIVER flows
   only — direct engine-API callers bypass driver guarantees (the driver is
   the orchestration unit).
5. **NothingToDecide propagates** — a stock with no routed flash writes NOTHING
   (no ledger row, no execution, no archive).
6. **Identities out, payloads stay sealed.** The return value carries identities
   + hashes only (`decision_id / execution_id / news_status / assembly_hash /
   archive_sha256`); consumers go through `load_and_verify_decision_archive`
   (C1's door), never through this return value.

NON_EVIDENTIARY: zero production callers until FORWARD_PREREG; the production
root binding (which store/artifact/ledger roots are THE roots) is the
FORWARD_PREREG governed-runner obligation recorded in threat model v3.
"""
from __future__ import annotations

import hashlib
import logging
import sys
import time
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from workspace.research.ai_research_dept.engine.news_archive import (  # noqa: E402
    _archive_path, load_and_verify_execution_archive,
    recover_and_seal_execution_archive, seal_decision_archive,
)
from workspace.research.ai_research_dept.engine.news_decision import (  # noqa: E402
    find_success_commitment, list_execution_commitments, record_decision,
)
from workspace.research.ai_research_dept.engine.news_executors import (  # noqa: E402
    NewsScoringContract, execute_news_decision,
)
from workspace.research.ai_research_dept.engine.news_flash_assemble import (  # noqa: E402
    NothingToDecide, assemble_stock_artifact, resolve_committed_evidence,
)
from workspace.research.ai_research_dept.engine.news_flash_typing import (  # noqa: E402
    _canonical_cutoff,
)

logger = logging.getLogger("news_flash_decide")


def _decision_flow_lock_path(ledger_dir, decision_id: str) -> Path:
    """本决策**整段流程**的跨进程锁位(P4b re-review#2 P1 的结构折叠)。文件系统
    安全名 = decision_id 的 sha256 前 16 位;置于账本根(该决策的权威根)。"""
    digest = hashlib.sha256(decision_id.encode("utf-8")).hexdigest()[:16]
    return Path(ledger_dir) / f".nf_decision_flow_{digest}.lock"


@contextmanager
def _decision_flow_lock(ledger_dir, decision_id: str, *, timeout: float):
    """跨进程**按决策**流锁(原子 mkdir 自旋;`_ledger_lock` 同款模式)。

    P4b re-review#2 P1:回填用一次性快照——快照后、本任务返回前,另一并发
    driver 可写入 hard_failed 承诺后崩溃,其档案没人再补(本任务已 success,
    不会自然重入)。同一不变量类连续两轮 → 结构折叠:整段
    `record → 承诺枚举/回填 → success 检查 → execute → seal` 在**一把按决策
    的锁**内,同一 decision_id 的 driver 流全序化——任何承诺要么在本任务的
    快照之前落账(被本次回填看见),要么在本任务释放锁之后才开始(由那个
    任务自己的回填兜底)。不同 decision 互不串行。

    锁语义与 `_ledger_lock`/`_prov_lock` 一致:崩溃遗留的锁目录会让后继者
    等待至超时后 fail-closed 报错(运维介入清锁)——LLM 双腿在锁内,默认
    超时须显著大于账本锁。仅 driver 流之间互斥:绕过 driver 直接调引擎 API
    的调用方不在本保证内(与 P4b 之前一致——driver 是编排单元)。"""
    lock_dir = _decision_flow_lock_path(ledger_dir, decision_id)
    lock_dir.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    while True:
        try:
            lock_dir.mkdir(parents=False, exist_ok=False)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"决策流锁超时({timeout}s):{lock_dir} —— 另一 driver 持锁"
                    f"或崩溃遗留锁目录,fail-closed(P4b re-review#2)")
            time.sleep(0.05)
    try:
        yield
    finally:
        try:
            lock_dir.rmdir()
        except OSError:
            pass


def nf_decision_id(cutoff, *, ingest_class: str, ts_code: str) -> str:
    """Invariant 1: the deterministic ledger identity for one (stock, cutoff,
    class). Canonicalizes the cutoff exactly as every other door does, so the
    same instant can never mint two ids."""
    cut = _canonical_cutoff(cutoff)
    if type(ingest_class) is not str or not ingest_class.strip():
        raise ValueError("ingest_class 须恰 str 非空——拒")
    if type(ts_code) is not str or not ts_code.strip():
        raise ValueError("ts_code 须恰 str 非空——拒")
    return f"nf:{ingest_class}:{ts_code}:{cut.isoformat()}"


def decide_stock(cutoff, *, ingest_class: str, ts_code: str, ledger_dir,
                 prov_dir, archive_dir, store_dir, artifact_dir,
                 contract: NewsScoringContract, call_fn,
                 lock_timeout: float = 600.0) -> dict:
    """ONE stock's full NF decision for `cutoff`: assemble → record → execute →
    seal, honouring the P4a doors, the whole write-bearing flow inside ONE
    cross-process per-decision lock (P4b re-review#2 P1). Returns identities
    only (invariant 6).

    `lock_timeout` must exceed the worst-case competing flow (two LLM legs) —
    default 600s; a stale crash-leftover lock fails closed at timeout.

    Raises `NothingToDecide` when no flash routes to the stock (invariant 5)."""
    cut = _canonical_cutoff(cutoff)
    decision_id = nf_decision_id(cut, ingest_class=ingest_class, ts_code=ts_code)

    # invariant 2: the SAME committed-evidence resolution the record door re-runs
    p2, p3a, rows = resolve_committed_evidence(
        cut, ingest_class=ingest_class, store_dir=store_dir,
        artifact_dir=artifact_dir)
    # invariant 5: NothingToDecide propagates from here — nothing written yet
    artifact, assembly = assemble_stock_artifact(
        cut, ingest_class=ingest_class, ts_code=ts_code, decision_id=decision_id,
        assessed_artifact=p2, split_artifact=p3a, source_rows=rows)

    # P4b re-review#2 P1(结构折叠):整段 record → 回填 → success 检查 →
    # execute → seal 在**一把按决策的跨进程锁**内。快照后才落账的并发承诺
    # 不再可能:同一 decision 的 driver 流全序化——任何承诺要么先于本次快照
    # (被本次回填看见),要么整段发生在本任务之后(那个任务自己回填兜底)。
    with _decision_flow_lock(ledger_dir, decision_id, timeout=lock_timeout):
        # first-write-wins (idempotent for the identical chain; a different
        # chain for the same slot refuses inside the door)
        record_decision(ledger_dir, decision_id, artifact, assembly=assembly,
                        store_dir=store_dir, artifact_dir=artifact_dir)

        # invariant 4 (P4b review P1): BACKFILL first — every committed
        # execution whose per-execution audit archive is missing (a crash
        # between commit and seal, hard_failed included) is recovered from pure
        # disk state BEFORE any resume or new retry.
        for c in list_execution_commitments(ledger_dir, decision_id):
            if not _archive_path(archive_dir, decision_id,
                                 c["execution_id"]).exists():
                recover_and_seal_execution_archive(
                    decision_id, c["execution_id"], artifact,
                    ledger_dir=ledger_dir, prov_dir=prov_dir,
                    contract=contract, archive_dir=archive_dir)
                logger.info("%s: backfilled missing archive for committed "
                            "execution %s", decision_id, c["execution_id"])

        # invariant 4: success is terminal per decision — never re-execute it
        # (its archive is guaranteed present by the backfill above)
        success = find_success_commitment(ledger_dir, decision_id)
        if success is not None:
            execution_id = success["execution_id"]
            archive = load_and_verify_execution_archive(
                decision_id, execution_id, artifact, ledger_dir=ledger_dir,
                prov_dir=prov_dir, contract=contract, archive_dir=archive_dir)
            logger.info("%s: success already committed — idempotent re-entry",
                        decision_id)
            return {"decision_id": decision_id, "execution_id": execution_id,
                    "news_status": "success",
                    "assembly_hash": assembly.assembly_hash,
                    "archive_sha256": archive["archive_sha256"], "resumed": True}

        bundle = execute_news_decision(
            artifact, ledger_dir=ledger_dir, prov_dir=prov_dir,
            decision_id=decision_id, contract=contract, call_fn=call_fn)
        # invariant 3: the same (artifact, assembly) that was recorded is sealed
        archive = seal_decision_archive(
            bundle, artifact, ledger_dir=ledger_dir, prov_dir=prov_dir,
            contract=contract, archive_dir=archive_dir, assembly=assembly)
        news_status = bundle["outcome"].news_status
        logger.info("%s: executed %s -> %s, archive %s", decision_id,
                    bundle["execution_id"], news_status,
                    archive["archive_sha256"][:12])
        return {"decision_id": decision_id,
                "execution_id": bundle["execution_id"],
                "news_status": news_status,
                "assembly_hash": assembly.assembly_hash,
                "archive_sha256": archive["archive_sha256"], "resumed": False}
