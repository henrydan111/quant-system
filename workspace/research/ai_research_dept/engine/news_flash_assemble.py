# SCRIPT_STATUS: ACTIVE — NF integration P3b: per-stock D7 artifact assembly
"""NF per-stock D7 artifact assembly (integration unit P3b).

Producer stage 3b — the point where the market-wide artifacts become ONE stock's decision
input. It selects the flashes routing to a stock, reconstructs their sealed cluster
snapshots, renders the D7 flash section, joins P3a's attribute splits, and builds the
`D7DecisionArtifact` that P4 records/executes/seals.

Declared invariants (Tier-2; see NF_UNIT_P3B_DESIGN.md):

1. **Chain binding.** Both inputs are fully verified (dict or path), both must be for this
   run's `(cutoff, ingest_class)`, and P3a's `consumed_assessed_flash_sha256` MUST equal the
   P2 artifact's `artifact_sha256` — artifacts from two different runs cannot be mixed.
2. **PIT inherited; no dated source of its own.** The only text used is bound by
   **recomputing** `content_hash` from caller-supplied raw rows against the P2 population
   (the caller's `text_store` read is not trusted; the recomputation is the binding).
3. **Selection is DERIVED**, never caller-supplied: `news_render_eligible ∧
   ts_code ∈ route.subject_codes`.
4. **Split coverage is EXACT**: every minted base fact with `importance >= D7_IMPORTANCE_FLOOR`
   has exactly one P3a split, joined by `fact_cluster_id`; a missing one is a hard error here
   (with a clearer cause than the downstream `verify_d7_artifact` coverage gate would give).
5. **Verify-not-trust throughout**: the reconstructed `ClusterSnapshot` self-verifies its
   `snapshot_id`; `render_news_flash_section` recomputes `evidence_class`;
   `build_attribute_bundle` → `verify_d7_artifact` re-derives the whole lineage.
6. **`decision_id` discipline**: exact non-empty `str` (the ledger becomes its authority in P4).
7. **NON_EVIDENTIARY.** A stock with no selected flash yields **no artifact** — an explicit
   "nothing to decide" result, never an empty-but-valid D7 artifact.

Output: the in-memory `D7DecisionArtifact` + a provenance dict (consumed SHAs, selection
basis). P3b seals nothing of its own — **P4 is the sealing boundary** and binds all of it
into the decision archive.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from workspace.research.ai_research_dept.engine.news_cards import (  # noqa: E402
    D7_IMPORTANCE_FLOOR, build_attribute_bundle, render_news_flash_section,
)
from workspace.research.ai_research_dept.engine.news_flash_assess import (  # noqa: E402
    load_assessed_flash_artifact, verify_assessed_flash_artifact,
)
from workspace.research.ai_research_dept.engine.news_flash_split import (  # noqa: E402
    _bind_source_rows, load_split_artifact, verify_split_artifact,
)
from workspace.research.ai_research_dept.engine.news_flash_typing import (  # noqa: E402
    _canonical_cutoff,
)
from workspace.research.ai_research_dept.engine.news_ingest import (  # noqa: E402
    ClusterSnapshot,
)

logger = logging.getLogger("news_flash_assemble")


class NothingToDecide(Exception):
    """No flash routes to this stock at this cutoff (invariant 7). An explicit result, not
    an empty D7 artifact — a decision with no evidence must not be manufactured."""


def _verified_inputs(cut, ingest_class: str, assessed_artifact, split_artifact):
    """Invariant 1: verify both artifacts, identity-match both to this run, and require the
    split artifact to have been produced FROM this exact assessed artifact."""
    p2 = (verify_assessed_flash_artifact(assessed_artifact)
          if isinstance(assessed_artifact, dict)
          else load_assessed_flash_artifact(assessed_artifact))
    p3a = (verify_split_artifact(split_artifact)
           if isinstance(split_artifact, dict)
           else load_split_artifact(split_artifact))
    for name, art in (("assessed-flash", p2), ("D7 split", p3a)):
        if art.get("cutoff_iso") != cut.isoformat() \
                or art.get("ingest_class") != ingest_class:
            raise ValueError(
                f"{name} artifact ({art.get('ingest_class')}, {art.get('cutoff_iso')}) "
                f"does not match this run ({ingest_class}, {cut.isoformat()}) — refusing")
    if p3a.get("consumed_assessed_flash_sha256") != p2.get("artifact_sha256"):
        raise ValueError(
            f"D7 split artifact was produced from a DIFFERENT assessed-flash artifact "
            f"(consumed {str(p3a.get('consumed_assessed_flash_sha256'))[:12]} vs supplied "
            f"{str(p2.get('artifact_sha256'))[:12]}) — artifacts from two runs cannot be "
            f"mixed, refusing (chain binding)")
    return p2, p3a


def _select_for_stock(p2: dict, ts_code: str) -> list[dict]:
    """Invariant 3: derived selection — never a caller-supplied flash list."""
    sel = [a for a in p2["assessed"]
           if a.get("news_render_eligible") is True
           and ts_code in a["route"]["subject_codes"]]
    return sorted(sel, key=lambda a: a["cluster"]["fact_occurrence_id"])


def _reconstruct_cluster(payload: dict) -> ClusterSnapshot:
    """Invariant 5: rebuild the sealed snapshot from P2's payload; `__post_init__`
    recomputes `snapshot_id`, and the payload itself is covered by P2's artifact seal."""
    return ClusterSnapshot(
        cluster_id=payload["cluster_id"], algo_version=payload["algo_version"],
        cutoff_iso=payload["cutoff_iso"],
        members=tuple(dict(m) for m in payload["members"]),
        fact_occurrence_id=payload["fact_occurrence_id"],
        cluster_first_visible_at_iso=payload["cluster_first_visible_at_iso"],
        n_outlets=int(payload["n_outlets"]))


def assemble_stock_artifact(cutoff, *, ingest_class: str, ts_code: str, decision_id: str,
                            assessed_artifact, split_artifact, source_rows) -> tuple:
    """Assemble ONE stock's `D7DecisionArtifact` for `cutoff`. Returns
    `(artifact, provenance)`. Raises `NothingToDecide` when no flash routes to the stock."""
    cut = _canonical_cutoff(cutoff)
    if type(decision_id) is not str or not decision_id.strip():
        raise ValueError("decision_id 须恰 str 非空——拒(P4 的账本随后持有其权威)")
    if type(ts_code) is not str or not ts_code.strip():
        raise ValueError("ts_code 须恰 str 非空——拒")
    p2, p3a = _verified_inputs(cut, ingest_class, assessed_artifact, split_artifact)

    selected = _select_for_stock(p2, ts_code)
    if not selected:
        raise NothingToDecide(
            f"{ts_code} @ {cut.isoformat()}: 无路由命中的快讯——不产 D7 工件"
            f"(绝不制造无证据的决策,invariant 7)")

    # invariant 2: the only text used is bound by RECOMPUTED content_hash
    bound = _bind_source_rows(source_rows, {a["content_hash"] for a in selected})
    assessed = [{
        "cluster": _reconstruct_cluster(a["cluster"]),
        "typing": a["typing"],
        # render recomputes evidence_class from typing+route, so it re-derives rather than
        # trusting P2's class; `content` is the hash-bound source text
        "route": {"primary_route": a["route"]["primary_route"],
                  "content": bound[a["content_hash"]]},
        "evidence_class": a["evidence_class"],
        "coordination_fired": a["coordination_fired"],
    } for a in selected]

    card, records, base_facts = render_news_flash_section(assessed, cut)

    # invariant 4: exact split coverage, joined by fact_cluster_id
    splits_by_fact = {s["fact_occurrence_id"]: s["attributes"] for s in p3a["splits"]}
    splits = []
    for bf in base_facts:
        if bf.importance < D7_IMPORTANCE_FLOOR:
            continue
        attrs = splits_by_fact.get(bf.fact_cluster_id)
        if attrs is None:
            raise ValueError(
                f"{ts_code}: 基事实 {bf.base_record_id}(事实 {bf.fact_cluster_id})"
                f"在 D7 split 工件中无对应拆分——覆盖不全,拒(invariant 4)")
        splits.append({"base_record_id": bf.base_record_id, "attributes": dict(attrs)})

    artifact = build_attribute_bundle(splits, base_facts, records, card=card,
                                      decision_id=decision_id, cutoff=cut)
    provenance = {
        "ts_code": ts_code,
        "decision_id": decision_id,
        "cutoff_iso": cut.isoformat(),
        "ingest_class": ingest_class,
        "consumed_assessed_flash_sha256": p2["artifact_sha256"],
        "consumed_d7_split_sha256": p3a["artifact_sha256"],
        "selected_fact_occurrence_ids": [a["cluster"]["fact_occurrence_id"]
                                         for a in selected],
        "n_selected": len(selected),
        "n_splits_used": len(splits),
    }
    logger.info("%s @ %s: %d flashes selected, %d D7 splits -> artifact %s",
                ts_code, cut.isoformat(), len(selected), len(splits),
                artifact.artifact_hash[:12])
    return artifact, provenance
