# SCRIPT_STATUS: ACTIVE — 新闻快讯:档案/绑定边界(NF §7 最终集成·单元1)
"""Decision archive boundary — joint tuple verification + sealing + ledger-head anchoring.

最终集成子块的第一承重单元,逐字落执行体终审的 6 条 BINDING 需求中的 #1/#6:

- **联合验证先于封印**(BINDING #1,终审头条):`verify_execution_bundle` 对
  outcome / 选定终态出处行 / 空罚分三元组做**全量重推导联合验证**:
  * outcome 经 `verify_outcome_for_binding`(canonical payload 确定性重建 →
    哈希逐字节相等;expected_output_mode 来自冻结契约);
  * 每条选定终态行:entry_hash 重算、**盘上出处文件内存在**、execution_id/
    decision_id/schema_id/payload_hash 五向一致、verdict 与腿终态语义一致
    (success→valid|deterministic_zero;failed→invalid|call_error;
    empty_success→empty_penalty;not_run→无选定行);
  * **空罚分哨兵只联合接受**:`"0"*64` payload_hash 仅当
    penalty_eligible_count==0 ∧ empty_success ∧ outcome 无 penalty payload 哈希
    ∧ verdict==empty_penalty 同时成立——绝不凭哈希单独接受;
  * evaluation **从封存记录重算**(`evaluate_news_horizon` 同一路径)逐字节比对
    ——M2⁴"不信封存计算值";硬失败决策 evaluation 必须为 None。
- **档案密封 + 账本链头外锚**(BINDING #6):`seal_decision_archive` 把
  决策档案(契约/工件/outcome/评估/记录/选定出处行)与**封印时的账本链头**一起
  全 SHA-256 密封,原子 fsync 写盘;`load_and_verify_decision_archive` 重验档案
  封印、重建 outcome(矩阵自验)、重跑联合验证、并要求**档案锚定的链头仍在当前
  账本链内**——整本重算替换会换掉全部 entry_hash,旧链头消失即抓获(账本 M1
  已知盲区的外锚闭合)。

四席装配/scorecard 薄分发/链 bump 在下一单元;本单元零活链触碰。
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from workspace.research.ai_research_dept.engine.news_cards import (
    D7DecisionArtifact, verify_d7_artifact,
)
from workspace.research.ai_research_dept.engine.news_decision import (
    _GENESIS, _ledger_path, _read_chain, build_leg_payload_ast,
    build_sealed_payload, ledger_head,
)
from workspace.research.ai_research_dept.engine.news_evidence import RegistryError
from workspace.research.ai_research_dept.engine.news_executors import (
    NewsScoringContract, read_execution_provenance,
)
from workspace.research.ai_research_dept.engine.news_horizon import (
    evaluate_news_horizon,
)
from workspace.research.ai_research_dept.engine.news_legs import (
    NewsLegOutcome, verify_outcome_for_binding,
)
from workspace.research.ai_research_dept.engine.news_seal import seal_hash, verify_sealed

_EMPTY_PENALTY_SENTINEL = "0" * 64
#: 腿终态 ↔ 选定出处 verdict 的语义一致表(BINDING #1)
_LEG_VERDICTS = {
    ("factor", "success"): {"valid", "deterministic_zero"},
    ("factor", "failed"): {"invalid", "call_error"},
    ("penalty", "success"): {"valid"},
    ("penalty", "failed"): {"invalid", "call_error"},
    ("penalty", "empty_success"): {"empty_penalty"},
}


def _rebuild_leg_payloads(artifact, outcome, *, ledger_dir):
    """canonical payload 确定性重建(同 AST + 同工件 → 同哈希)。penalty 只在
    实际执行过(success/failed)时存在。"""
    factor_payload = build_sealed_payload(
        build_leg_payload_ast(artifact, use="factor_positive", consumer_seat="news"),
        artifact, ledger_dir=ledger_dir, decision_id=outcome.decision_id,
        consumer_seat="news", use="factor_positive")
    penalty_payload = None
    if outcome.penalty_leg_status in ("success", "failed"):
        penalty_payload = build_sealed_payload(
            build_leg_payload_ast(artifact, use="penalty", consumer_seat="news"),
            artifact, ledger_dir=ledger_dir, decision_id=outcome.decision_id,
            consumer_seat="news", use="penalty")
    return factor_payload, penalty_payload


def _verify_selected_row(row, *, leg: str, outcome: NewsLegOutcome,
                         execution_id: str, contract: NewsScoringContract,
                         leg_payload_hash: str, on_disk_hashes: set) -> None:
    """单条选定终态行的联合验证(BINDING #1)。"""
    if not isinstance(row, dict):
        raise RegistryError(f"{leg} 腿选定终态行缺失/非法——尝试过的腿必须恰一终态")
    body = {k: v for k, v in row.items() if k != "entry_hash"}
    if seal_hash(body) != row.get("entry_hash"):
        raise RegistryError(f"{leg} 腿选定终态行 entry_hash 重算不符——行被改,拒")
    if row["entry_hash"] not in on_disk_hashes:
        raise RegistryError(f"{leg} 腿选定终态行不在盘上出处文件内——出处必须已持久化")
    if row["execution_id"] != execution_id or row["decision_id"] != outcome.decision_id:
        raise RegistryError(f"{leg} 腿选定终态行 execution/decision 身份不符")
    if row["schema_id"] != contract.schema_id:
        raise RegistryError(f"{leg} 腿选定终态行 schema_id 与冻结契约不符")
    status = getattr(outcome, f"{leg}_leg_status")
    allowed = _LEG_VERDICTS.get((leg, status))
    if allowed is None or row["verdict"] not in allowed:
        raise RegistryError(
            f"{leg} 腿终态 {status!r} 与选定 verdict {row['verdict']!r} 语义不符"
            f"(允许 {sorted(allowed) if allowed else '无'})")
    if row["payload_hash"] != leg_payload_hash:
        raise RegistryError(f"{leg} 腿选定终态行 payload_hash 与重建 payload 不符")


def verify_execution_bundle(bundle: dict, artifact: D7DecisionArtifact, *,
                            ledger_dir, prov_dir,
                            contract: NewsScoringContract) -> dict:
    """**封印前的联合验证**(BINDING #1)。全量重推导:工件过门 → canonical
    payload 重建 → outcome 绑定验证 → 每条选定终态行五向一致 + 盘上存在 +
    verdict 语义 → 空罚分哨兵**联合**接受 → evaluation 从封存记录重算。"""
    if not isinstance(contract, NewsScoringContract):
        raise RegistryError("联合验证必须提供冻结 NewsScoringContract")
    outcome = bundle["outcome"]
    if not isinstance(outcome, NewsLegOutcome):
        raise RegistryError("bundle.outcome 须为密封 NewsLegOutcome")
    execution_id = bundle["execution_id"]
    if type(execution_id) is not str or not execution_id.strip():
        raise RegistryError("bundle.execution_id 须为非空 str")
    verify_d7_artifact(artifact)
    factor_payload, penalty_payload = _rebuild_leg_payloads(
        artifact, outcome, ledger_dir=ledger_dir)
    verify_outcome_for_binding(outcome, artifact, factor_payload, penalty_payload,
                               ledger_dir=ledger_dir,
                               expected_output_mode=contract.output_mode)
    on_disk = {e["entry_hash"] for e in read_execution_provenance(prov_dir)}
    sel = bundle["selected_provenance"]
    # factor 腿:总被尝试(真实执行或确定性零路径)→ 恰一选定终态
    _verify_selected_row(sel.get("factor"), leg="factor", outcome=outcome,
                         execution_id=execution_id, contract=contract,
                         leg_payload_hash=factor_payload.payload_hash,
                         on_disk_hashes=on_disk)
    # penalty 腿:按终态分派
    p_status = outcome.penalty_leg_status
    if p_status == "not_run":
        if sel.get("penalty") is not None:
            raise RegistryError("penalty not_run 不得有选定终态行")
    elif p_status == "empty_success":
        row = sel.get("penalty")
        _verify_selected_row(row, leg="penalty", outcome=outcome,
                             execution_id=execution_id, contract=contract,
                             leg_payload_hash=_EMPTY_PENALTY_SENTINEL,
                             on_disk_hashes=on_disk)
        # BINDING #1:哨兵只**联合**接受——绝不凭 "0"*64 单独放行
        if not (outcome.penalty_eligible_count == 0
                and outcome.penalty_payload_hash is None
                and row["verdict"] == "empty_penalty"
                and row["payload_hash"] == _EMPTY_PENALTY_SENTINEL):
            raise RegistryError(
                "空罚分哨兵联合验证失败:须 eligible==0 ∧ empty_success ∧ outcome 无 "
                "penalty payload 哈希 ∧ verdict==empty_penalty 同时成立(BINDING #1)")
    else:                                          # success / failed:真实执行过
        _verify_selected_row(sel.get("penalty"), leg="penalty", outcome=outcome,
                             execution_id=execution_id, contract=contract,
                             leg_payload_hash=penalty_payload.payload_hash,
                             on_disk_hashes=on_disk)
    # evaluation 从封存记录重算(M2⁴ 不信封存计算值)
    records = bundle.get("records") or {}
    if outcome.news_status == "success":
        recomputed = evaluate_news_horizon(
            records["factor"], records["penalty"], artifact.final_registry,
            output_mode=contract.output_mode,
            primary_decision_horizon=contract.primary_decision_horizon)
        if recomputed != bundle["evaluation"]:
            raise RegistryError(
                f"evaluation 重算不符:封存 {bundle['evaluation']} vs 重算 "
                f"{recomputed}——不信封存计算值(M2⁴)")
    else:
        if bundle.get("evaluation") is not None:
            raise RegistryError("硬失败决策不得携带 evaluation")
    return {"factor_payload_hash": factor_payload.payload_hash,
            "penalty_payload_hash": (penalty_payload.payload_hash
                                     if penalty_payload else None)}


def _archive_path(archive_dir, decision_id: str) -> Path:
    # 文件名用 decision_id 的哈希前缀(decision_id 可能含文件系统非法字符)
    return Path(archive_dir) / f"news_decision_{seal_hash(decision_id)[:16]}.json"


def seal_decision_archive(bundle: dict, artifact: D7DecisionArtifact, *,
                          ledger_dir, prov_dir, contract: NewsScoringContract,
                          archive_dir) -> dict:
    """联合验证 → 密封决策档案(news 席切片)+ **账本链头外锚**(BINDING #6)。
    archive_sha256 = 全 SHA-256 over {契约/工件/outcome/评估/记录/选定出处行/
    封印时账本链头};原子 fsync 写盘。"""
    verify_execution_bundle(bundle, artifact, ledger_dir=ledger_dir,
                            prov_dir=prov_dir, contract=contract)
    outcome: NewsLegOutcome = bundle["outcome"]
    payload = {
        "archive_schema": "news_decision_archive_v1",
        "decision_id": outcome.decision_id,
        "execution_id": bundle["execution_id"],
        "contract": contract._payload(),
        "contract_hash": contract.contract_hash,
        "artifact_hash": artifact.artifact_hash,
        "bundle_hash": artifact.bundle.bundle_hash,
        "final_registry_hash": artifact.final_registry.registry_hash,
        "outcome": outcome._payload(),
        "outcome_hash": outcome.outcome_hash,
        "evaluation": bundle["evaluation"],
        "records": bundle["records"],
        "selected_provenance": bundle["selected_provenance"],
        "ledger_head_at_seal": ledger_head(ledger_dir),
    }
    archive = {**payload, "archive_sha256": seal_hash(payload)}
    path = _archive_path(archive_dir, outcome.decision_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".json.tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(archive, f, ensure_ascii=False, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return archive


def load_and_verify_decision_archive(decision_id: str, artifact: D7DecisionArtifact,
                                     *, ledger_dir, prov_dir,
                                     contract: NewsScoringContract,
                                     archive_dir) -> dict:
    """档案读取 + **全量重验**:档案封印重算 → outcome 从封存字段重建(矩阵自验)
    → 联合验证重跑(canonical 重建/选定行/哨兵/evaluation 重算)→ **链头锚验**:
    档案锚定的链头必须仍在当前账本链内(整本重算=旧链头消失=拒,BINDING #6)。"""
    path = _archive_path(archive_dir, decision_id)
    if not path.exists():
        raise RegistryError(f"决策档案缺失:{path}")
    archive = json.loads(path.read_text(encoding="utf-8"))
    body = {k: v for k, v in archive.items() if k != "archive_sha256"}
    verify_sealed(body, archive.get("archive_sha256", ""),
                  field_name="archive_sha256")
    if archive["contract_hash"] != contract.contract_hash \
            or archive["contract"] != contract._payload():
        raise RegistryError("档案契约与提供的冻结契约不符")
    if archive["artifact_hash"] != artifact.artifact_hash:
        raise RegistryError("档案工件哈希与提供的工件不符")
    # outcome 从封存字段重建——NewsLegOutcome 构造即重跑 M3⁴ 矩阵自验
    o = archive["outcome"]
    outcome = NewsLegOutcome(
        decision_id=o["decision_id"], output_mode=o["output_mode"],
        factor_leg_status=o["factor_leg_status"],
        penalty_eligible_count=o["penalty_eligible_count"],
        penalty_eligible_set_hash=o["penalty_eligible_set_hash"],
        penalty_leg_status=o["penalty_leg_status"], news_status=o["news_status"],
        shadow_complete=o["shadow_complete"],
        decision_complete=o["decision_complete"],
        binding_eligible=o["binding_eligible"],
        factor_payload_hash=o["factor_payload_hash"],
        penalty_payload_hash=o["penalty_payload_hash"],
        outcome_hash=archive["outcome_hash"])
    bundle = {"execution_id": archive["execution_id"], "outcome": outcome,
              "evaluation": archive["evaluation"], "records": archive["records"],
              "selected_provenance": archive["selected_provenance"]}
    verify_execution_bundle(bundle, artifact, ledger_dir=ledger_dir,
                            prov_dir=prov_dir, contract=contract)
    # 链头锚验(BINDING #6):封印时链头必须仍在当前链内
    anchored = archive["ledger_head_at_seal"]
    current_hashes = {e["entry_hash"] for e in _read_chain(_ledger_path(ledger_dir))}
    if anchored != _GENESIS and anchored not in current_hashes:
        raise RegistryError(
            f"档案锚定链头 {anchored[:12]} 不在当前账本链内——账本被整本重算/替换,"
            f"拒(BINDING #6 外锚)")
    return archive
