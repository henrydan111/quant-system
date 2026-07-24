# SCRIPT_STATUS: ACTIVE — NF integration C1: sealed-decision consumption + session embedding
"""NF sealed-decision consumption for the session news seat (integration unit C1).

The CONSUMER half of the NF chain: given (stock, cutoff), rebuild the D7 artifact
deterministically from the committed evidence, read the sealed decision back through
THE single sanctioned consumer door (`load_and_verify_decision_archive` — the
decision-level canonical read), and convert it into (a) a news-seat result in the
exact `run_seat` shape and (b) the decision's IDENTITY block for embedding into the
session archive.

Declared invariants (Tier-2; spec = NF_UNIT2_SESSION_EMBEDDING_DESIGN.md §3, wiring
shape = NF_UNIT_C1_DESIGN.md):

1. **Single door.** The news outcome comes exclusively from
   `load_and_verify_decision_archive`. `load_and_verify_execution_archive` is
   audit/display only and MUST NOT appear in this module (AST-guarded).
2. **Identity, not copy.** The session archive embeds the decision's identity block
   (ids + hashes only); the decision's internals are not re-derived or re-summarised.
3. **Recompute, don't trust.** The seat's `final` is cross-derived from the sealed
   evaluation: on `primary_horizon`, `news_final_by_horizon[primary]` must equal the
   sealed `news_final` (the deep entry-level re-derivation already ran inside the
   load door — `trusted_eval` is recomputed and byte-compared there); a mismatch is
   a HARD error seat, never a warning.
4. **Fail-closed seat.** Missing archive / verification failure / non-success
   news_status → an ERROR seat (`final=None` + structured error), never a silent
   absence, never a zero. `archive_complete` then refuses publication (a seat with
   an error is unpublishable by the shared integrity predicate).
5. **`vector_only` never yields a scalar.** A vector_only decision produces
   `final=None` WITHOUT an error; the identity block carries
   `binding_eligible=False`; the session archive stays unpublishable-as-scalar.
6. **Legacy unchanged — C1 itself touched no `analyst_chain.py` byte** (C1
   review round-1 P1#1: the manifest hashes that file's BYTES into
   `engine_contract_sha256`, so even a default-OFF hook parameter would have
   changed the then-frozen `chain_v3.1` contract). The wiring landed with the
   **chain_v3.2 bump** per the (now-discharged) FROZEN WIRING OBLIGATIONS
   below; v3.1 archives live in their own version dir, untouched.
7. **No post-cutoff reads.** Inputs are the committed evidence + sealed artifacts
   only — every one of them is cutoff-bound by the producer chain.
8. **Opaque external scalar, declared** (C1 review round-1 P1#2 + re-review#2
   P2#1). The consumed seat's `final` is a SEALED EXTERNAL score: its `record`
   deliberately carries empty legacy scoring lists (NF dimensions are a
   different contract), so a legacy judge that recomputes `adj_final` from
   those lists would silently zero the sealed score while the archive stays
   publishable. Flag discipline: `opaque_external=True` marks EVERY consumed
   seat (external origin); `opaque_scalar=True` marks ONLY the scalar branch —
   it is the anchor of wiring obligation (b) (`adj_final == final`), and a
   no-scalar (vector_only) seat carrying it would make that obligation
   self-contradictory.

⚠ **FROZEN WIRING OBLIGATIONS — DISCHARGED by chain_v3.2 (2026-07-24)**. The
four obligations below were frozen at the C1 arc's close and discharged by the
version-bump unit: (a) the wiring landed WITH `CHAIN_VERSION = "chain_v3.2"`
(the byte pin moved in the same commit); (b) `judge()` passes `opaque_scalar`
seats through (`adj_final == final`, hook-on regression pinned); (c) the
manifest's frozen `nf_contract` section + `nf_contract_from_chain` /
`nf_cutoff_for_day` below bind the session day to the full 18:00:00 cutoff;
(d) preserved verbatim in the hook branch. The text is kept as the contract
record; it now BINDS v3.2 (any further `analyst_chain.py` edit = another
bump):

  a. **Chain-version bump first.** Any edit to `analyst_chain.py` (the hook
     parameter, the news-seat branch, the `nf_decision` block) is a NEW chain
     version with a re-frozen manifest — never an in-place edit of the current
     frozen version (its contract hash covers the file bytes; P1#1).
  b. **Opaque-scalar judge semantics.** For a seat with `opaque_scalar=True`
     (set ONLY on seats with a scalar `final` — re-review#2 P2#1), the judge
     must set `adj_final = final` when no NF-native bear-discount contract
     exists (P1#2) — an empty-scoring recompute that zeroes the sealed score is
     forbidden; seats carrying only `opaque_external` (vector_only) have no
     scalar and the judge must not manufacture one. Ship a hook-on regression
     pinning `news.adj_final == news.final` with no bear refutations.
  c. **Cutoff binding.** The production hook must bind the session `day` to the
     FULL, pre-declared NF cutoff timestamp (never a bare date) — reviewer-noted
     boundary, frozen here.
  d. The hook's fallback dichotomy is fixed: `no_decision` → legacy inline seat;
     verification failure → error seat, NEVER fallback.

Structural distinction (the fallback semantics): `NothingToDecide` — the chain
routed NO flash to this stock at this cutoff — is NOT a failure; it returns
`{"no_decision": True}` and the caller falls back to the legacy inline seat. A
decision that SHOULD exist but cannot be verified (missing/failed/tampered) is an
ERROR seat: fail-closed, no fallback (falling back would silently swallow a broken
producer chain).

NON_EVIDENTIARY: zero production callers until FORWARD_PREREG (root binding is the
governed-runner obligation of threat model v3).
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from workspace.research.ai_research_dept.engine.news_archive import (  # noqa: E402
    load_and_verify_decision_archive,
)
from workspace.research.ai_research_dept.engine.news_flash_assemble import (  # noqa: E402
    NothingToDecide, assemble_stock_artifact, resolve_committed_evidence,
)
from workspace.research.ai_research_dept.engine.news_flash_decide import (  # noqa: E402
    nf_decision_id,
)
from workspace.research.ai_research_dept.engine.news_executors import (  # noqa: E402
    NewsScoringContract,
)
from workspace.research.ai_research_dept.engine.news_flash_typing import (  # noqa: E402
    _canonical_cutoff,
)

logger = logging.getLogger("news_session_embed")


def nf_contract_from_chain(chain_contract) -> NewsScoringContract:
    """义务 (c) 前半(v3.2):NF 评分契约**只能**从对盘验证过的 `ChainContract`
    的冻结 `nf` 节构造(该节在 `ChainContract.load` 逐值校验、对盘复核比对);
    v3.2 之前的契约无此节 → fail-closed 拒——NF 消费不可能接错契约。"""
    nf = getattr(chain_contract, "nf", None)
    if not nf:
        raise ValueError(
            "ChainContract 无 nf_contract 节——chain_v3.2 之前的契约不可驱动 NF"
            "消费,拒(义务 c)")
    return NewsScoringContract(
        schema_id=nf["schema_id"], output_mode=nf["output_mode"],
        primary_decision_horizon=nf["primary_decision_horizon"])


def nf_cutoff_for_day(day, chain_contract):
    """义务 (c) 后半(v3.2):会话 `day`(YYYYMMDD)→ **完整冻结 cutoff 时间戳**
    的唯一绑定——裸日期永远到不了 NF 门。时刻来自契约冻结的
    `nf.input_cutoff_time`;经与所有 NF 门相同的 `_canonical_cutoff` 规范化。"""
    nf = getattr(chain_contract, "nf", None)
    if not nf:
        raise ValueError("ChainContract 无 nf_contract 节——拒(义务 c)")
    d = str(day)
    if len(d) != 8 or not d.isdigit():
        raise ValueError(f"day 须为 YYYYMMDD(得 {day!r})——拒")
    return _canonical_cutoff(
        f"{d[:4]}-{d[4:6]}-{d[6:8]} {nf['input_cutoff_time']}")

#: 会话层证伪条目的合法域(与 analyst_chain._normalize_falsifiers 同标);NF 论点
#: 的最强反证在新闻域可观察
_NF_FALSIFIER_DOMAIN = "news"
_MAX_FALSIFIER_CHARS = 60
_MAX_FALSIFIERS = 5

#: 身份块字段(invariant 2;spec §3.2 的 8 字段 + P4a 的 assembly_hash + 语义旗)
_IDENTITY_FIELDS = ("decision_id", "archive_sha256", "contract_hash",
                    "artifact_hash", "bundle_hash", "final_registry_hash",
                    "outcome_hash", "ledger_head_at_seal")


def _error_seat(error: str) -> dict:
    """Invariant 4: the fail-closed seat — same shape `_execute_attempt` builds for
    an inline seat failure; `verify_publishable_archive` refuses any seat whose
    error is not None, so publication is structurally impossible."""
    return {"seat": {"final": None,
                     "record": {"factor_scores": [], "penalty_scores": []},
                     "scored_dims": 0, "total_dims": 0, "error": error},
            "nf_decision": None, "no_decision": False}


def _map_falsifiers(factor_record) -> tuple[list, dict]:
    """Spec §5 (declared decision): NF `horizon_theses[].strongest_counter` → the
    legacy `what_could_weaken` registry shape ({condition, observable_in}) the bear
    consumes. Mapping only — losses are counted, never silent."""
    theses = factor_record.get("horizon_theses", []) \
        if isinstance(factor_record, dict) else []
    stats = {"n_theses": len(theses) if isinstance(theses, list) else 0,
             "n_kept": 0, "n_truncated": 0}
    out = []
    if not isinstance(theses, list):
        return out, stats
    for t in theses:
        if not isinstance(t, dict):
            continue
        sc = t.get("strongest_counter")
        if not isinstance(sc, str) or not sc.strip():
            continue
        if len(sc) > _MAX_FALSIFIER_CHARS:
            sc = sc[:_MAX_FALSIFIER_CHARS]
            stats["n_truncated"] += 1
        out.append({"condition": sc, "observable_in": _NF_FALSIFIER_DOMAIN})
        if len(out) >= _MAX_FALSIFIERS:
            break
    stats["n_kept"] = len(out)
    return out, stats


def consume_news_decision(code: str, cutoff, *, ingest_class: str, ledger_dir,
                          prov_dir, archive_dir, store_dir, artifact_dir,
                          nf_contract) -> dict:
    """Consume ONE stock's sealed NF decision for `cutoff` into a session news
    seat. Returns `{"seat", "nf_decision", "no_decision"}`:

    - routed decision, success, scalar mode → seat with recomputed `final` +
      identity block;
    - `vector_only` → seat with `final=None`, NO error (invariant 5);
    - NO flash routed (`NothingToDecide`) → `no_decision=True` (caller falls back
      to the legacy inline seat — absence of news is not a failure);
    - anything else → the fail-closed error seat (invariant 4)."""
    try:
        cut = _canonical_cutoff(cutoff)
        decision_id = nf_decision_id(cut, ingest_class=ingest_class, ts_code=code)
        # deterministic artifact rebuild from the COMMITTED evidence — the same
        # construction the P4a record door proved (invariant 7: everything here
        # is cutoff-bound by the producer chain)
        p2, p3a, rows = resolve_committed_evidence(
            cut, ingest_class=ingest_class, store_dir=store_dir,
            artifact_dir=artifact_dir)
        artifact, assembly = assemble_stock_artifact(
            cut, ingest_class=ingest_class, ts_code=code,
            decision_id=decision_id, assessed_artifact=p2, split_artifact=p3a,
            source_rows=rows)
    except NothingToDecide:
        return {"seat": None, "nf_decision": None, "no_decision": True}
    except Exception as e:  # noqa: BLE001 — invariant 4: total fail-closed seat
        return _error_seat(f"nf_consume:evidence:{type(e).__name__}:{e}")

    try:
        # invariant 1: THE single sanctioned consumer door (decision-level
        # canonical read; full chain re-verification inside, incl. trusted_eval
        # recomputation and the P4a assembly/ledger cross-checks)
        archive = load_and_verify_decision_archive(
            decision_id, artifact, ledger_dir=ledger_dir, prov_dir=prov_dir,
            contract=nf_contract, archive_dir=archive_dir)
    except Exception as e:  # noqa: BLE001 — missing/hard_failed/tampered → error
        return _error_seat(f"nf_consume:load:{type(e).__name__}:{e}")

    try:
        outcome = archive["outcome"]
        if outcome["news_status"] != "success":       # belt — canonical read
            return _error_seat(                       # already guarantees this
                f"nf_consume:status:{outcome['news_status']}")
        contract_payload = archive["contract"]
        evaluation = archive["evaluation"]
        identity = {k: archive[k] if k != "decision_id" else decision_id
                    for k in _IDENTITY_FIELDS}
        identity["assembly_hash"] = archive["assembly"]["assembly_hash"]
        identity["output_mode"] = contract_payload["output_mode"]
        identity["binding_eligible"] = outcome["binding_eligible"]
        falsifiers, fstats = _map_falsifiers(
            archive.get("records", {}).get("factor"))

        if contract_payload["output_mode"] == "vector_only":
            # invariant 5: the mode is carried, never collapsed to a number
            # C1 re-review#2 P2#1:vector_only **不带** opaque_scalar——义务 (b)
            # 的语义是 `opaque_scalar ⇒ adj_final == final`,无标量席打这个旗
            # 会让义务自相矛盾;外部来源身份另用 opaque_external 标注,裁判只
            # 处理有标量 final 的席
            seat = {"final": None, "opaque_external": True,
                    "record": {"factor_scores": [], "penalty_scores": [],
                               "what_could_weaken": falsifiers},
                    "scored_dims": 0, "total_dims": 0,
                    "vector_only": True, "falsifier_norm": fstats}
            return {"seat": seat, "nf_decision": identity, "no_decision": False}

        # invariant 3: recompute-don't-trust at this layer — the sealed scalar
        # must equal the sealed per-horizon value at the sealed primary horizon
        # (the entry-level re-derivation ran inside the load door)
        primary = contract_payload["primary_decision_horizon"]
        by_h = evaluation["news_final_by_horizon"]
        final = by_h[primary]
        if final != evaluation["news_final"]:
            return _error_seat(
                f"nf_consume:recompute:news_final {evaluation['news_final']!r} "
                f"≠ by_horizon[{primary}] {final!r} — sealed values decoupled")
        if not (isinstance(final, (int, float)) and 0 <= final <= 100):
            return _error_seat(f"nf_consume:recompute:final out of range {final!r}")

        n_factor = len(archive["records"]["factor"].get("factor_scores", []))
        # invariant 8: the sealed external scalar is OPAQUE to the legacy judge —
        # the flag is the wiring obligation (b) anchor (adj_final must equal
        # final absent an NF-native discount contract; empty legacy scoring
        # lists must never let a recompute zero the sealed score). SCALAR branch
        # ONLY (re-review#2 P2#1) — a no-scalar seat carries opaque_external.
        seat = {"final": float(final), "opaque_scalar": True,
                "opaque_external": True,
                "record": {"factor_scores": [], "penalty_scores": [],
                           "what_could_weaken": falsifiers},
                "scored_dims": n_factor, "total_dims": n_factor,
                "falsifier_norm": fstats}
        logger.info("%s: consumed sealed NF decision %s -> final %.1f",
                    code, decision_id, final)
        return {"seat": seat, "nf_decision": identity, "no_decision": False}
    except Exception as e:  # noqa: BLE001 — invariant 4
        return _error_seat(f"nf_consume:shape:{type(e).__name__}:{e}")
