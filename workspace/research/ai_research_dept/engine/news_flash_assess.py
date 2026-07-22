# SCRIPT_STATUS: ACTIVE — NF integration P2: market-wide cluster + route + assess
"""NF market-wide clustering + routing + assessment (integration unit P2).

Producer stage 2. Consumes P1's typed-flash artifact and produces a **sealed
market-wide assessed-flash artifact**: for each cutoff-visible news cluster, its
typing (from P1), its route (which A-share stocks / industries / concepts it
mentions), and its evidence class. P3 then selects, per stock, the flashes whose
route touches that stock and renders them into a D7 decision artifact.

**Wiring, not new logic.** Every step already exists and is tested:
`text_store.load_text` (PIT gate + forward fail-closed), `news_ingest.build_cluster_
snapshots` (sealed clusters), `news_routing.route_cluster` over `AliasRegistry`
(deterministic, alias-based, as-of cutoff), `news_cards.assess_flash`
(verify-not-trust evidence class). The reference inputs (alias registry, industry
terms, concept terms) are INJECTED so the core is testable; the CLI builds them
from `stock_basic` / the SW industry reference / the THS concept index.

Declared invariants (Tier-2; see NF_UNIT_P2_DESIGN.md):

1. **PIT inherited + one canonical cutoff.** `load_text` filters + forward fail-closed;
   the SAME `_canonical_cutoff` (microsecond-max) drives load, clustering, and routing
   as-of; `build_cluster_snapshots` re-asserts `effective_at <= cutoff`; an alias listed
   after cutoff does not resolve.
2. **P1 binding — same identity, full coverage, fail-closed.** The consumed P1 artifact
   MUST be for the exact (cutoff, ingest_class); its `artifact_sha256` is verified and
   bound into P2's artifact. Every cluster representative's `content_hash` MUST be in the
   P1 typing index — a miss is a hard error (population mismatch), never a default typing.
3. **Deterministic PIT routing, no LLM.** Routing is a pure function of (content,
   registry, cutoff, terms); the registry's `content_hash`+version is recorded so P3/P4
   can bind the exact routing basis.
4. **evidence_class is verify-not-trust.** `assess_flash` recomputes it from typing+route.
5. **Macro-routed flashes kept but flagged.** A `primary_route=='macro'` cluster stays in
   the artifact (audit) with `news_render_eligible=False`; the news D7 render (P3) excludes
   it (the macro seat is a separate unit).
6. **Immutable, self-describing, write-once persistence** — same discipline as P1.
7. **NON_EVIDENTIARY.** Empty day → empty artifact; replay-class marker.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import tempfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from data_infra.text_store import load_text  # noqa: E402
from workspace.research.ai_research_dept.engine.news_cards import assess_flash  # noqa: E402
from workspace.research.ai_research_dept.engine.news_flash_typing import (  # noqa: E402
    _canonical_cutoff, load_typed_flash_artifact,
)
from workspace.research.ai_research_dept.engine.news_ingest import (  # noqa: E402
    build_cluster_snapshots,
)
from workspace.research.ai_research_dept.engine.news_routing import route_cluster  # noqa: E402
from workspace.research.ai_research_dept.engine.news_seal import seal_hash  # noqa: E402

logger = logging.getLogger("news_flash_assess")

ARTIFACT_SCHEMA = "nf_assessed_flash_v1"
EVIDENCE_CLASS = "nf_assessed_flash/NON_EVIDENTIARY"


class AssessedFlashConflictError(ValueError):
    """write-once conflict: an assessed-flash artifact for this (ingest_class, cutoff)
    already exists with different content (same discipline as P1/P4)."""


def _cluster_payload(cluster) -> dict:
    """Serialize a sealed ClusterSnapshot to a JSON dict P3 can reconstruct + re-verify."""
    return {"cluster_id": cluster.cluster_id, "algo_version": cluster.algo_version,
            "cutoff_iso": cluster.cutoff_iso,
            "members": [dict(m) for m in cluster.members],
            "fact_occurrence_id": cluster.fact_occurrence_id,
            "cluster_first_visible_at_iso": cluster.cluster_first_visible_at_iso,
            "n_outlets": cluster.n_outlets}


def assess_day_flashes(cutoff, *, ingest_class: str, typed_artifact,
                       registry, industry_terms: frozenset, concept_terms: frozenset,
                       store_dir=None, require_exists: bool = False) -> dict:
    """Market-wide cluster + route + assess for one (cutoff, ingest_class). Reference
    inputs are injected: `typed_artifact` = the loaded P1 artifact dict (or a path),
    `registry` = an `AliasRegistry`, `industry_terms`/`concept_terms` = frozensets. Returns
    a self-describing assessed-flash artifact dict."""
    cut = _canonical_cutoff(cutoff)
    if not isinstance(typed_artifact, dict):
        typed_artifact = load_typed_flash_artifact(typed_artifact)   # accept a path
    # invariant 2: the P1 artifact must be for the EXACT (cutoff, ingest_class)
    if typed_artifact.get("cutoff_iso") != cut.isoformat() \
            or typed_artifact.get("ingest_class") != ingest_class:
        raise ValueError(
            f"typed-flash artifact ({typed_artifact.get('ingest_class')}, "
            f"{typed_artifact.get('cutoff_iso')}) does not match this run "
            f"({ingest_class}, {cut.isoformat()}) — refusing (P1/P2 identity mismatch)")
    typing_index = {t["content_hash"]: t["typing"] for t in typed_artifact["typed"]}
    consumed_p1_sha = typed_artifact["artifact_sha256"]

    req = ingest_class == "forward" or bool(require_exists)   # forward: hard fail-closed
    df = load_text("news", cut, store_dir=store_dir, ingest_class=ingest_class,
                   require_exists=req)
    clusters = build_cluster_snapshots(df, cut) if not df.empty else []
    content_by_hash = {} if df.empty else dict(zip(df["content_hash"], df["content"]))

    assessed: list[dict] = []
    for cluster in clusters:
        rep = cluster.members[0]                 # deterministic representative (sorted)
        ch = rep["content_hash"]
        if ch not in content_by_hash:
            raise ValueError(f"cluster {cluster.fact_occurrence_id} representative "
                             f"content_hash absent from loaded rows — refusing")
        if ch not in typing_index:               # invariant 2: full P1 coverage
            raise ValueError(
                f"cluster {cluster.fact_occurrence_id} representative content_hash "
                f"{ch[:12]} has no P1 typing — P1/P2 population mismatch, refusing "
                f"(never default a typing)")
        content = str(content_by_hash[ch])
        route = route_cluster(content, registry, cut, industry_terms, concept_terms)
        route["content"] = content               # render uses it as the representative text
        a = assess_flash(cluster, typing_index[ch], route)   # recomputes evidence_class
        assessed.append({
            "cluster": _cluster_payload(cluster),
            "content_hash": ch,
            "typing": a["typing"],
            "route": {k: a["route"][k] for k in
                      ("primary_route", "subject_codes", "industry_tags",
                       "concept_tags", "mentions")},
            "evidence_class": a["evidence_class"],
            "coordination_fired": a["coordination_fired"],
            # invariant 5: macro-routed flashes stay for audit but are not news-render eligible
            "news_render_eligible": a["route"]["primary_route"] != "macro",
        })
    assessed.sort(key=lambda x: x["cluster"]["fact_occurrence_id"])   # deterministic
    population_hash = seal_hash(sorted(x["cluster"]["fact_occurrence_id"] for x in assessed))
    artifact = {
        "artifact_schema": ARTIFACT_SCHEMA,
        "cutoff_iso": cut.isoformat(),
        "ingest_class": ingest_class,
        "evidence_class": EVIDENCE_CLASS,
        "consumed_typed_flash_sha256": consumed_p1_sha,
        "alias_registry_version": registry.version,
        "alias_registry_hash": registry.content_hash,   # bind the exact routing basis
        "population_hash": population_hash,
        "n_flashes": len(assessed),
        "assessed": assessed,
    }
    artifact["artifact_sha256"] = seal_hash(artifact)
    return artifact


def _artifact_path(out_dir, cutoff_iso: str, ingest_class: str) -> Path:
    stamp = _canonical_cutoff(cutoff_iso).strftime("%Y%m%dT%H%M%S%f")   # bijective (P1 contract)
    return Path(out_dir) / f"nf_assessed_flash_{ingest_class}_{stamp}.json"


def write_assessed_flash_artifact(artifact: dict, out_dir) -> Path:
    """Immutable, atomic, write-once / first-write-wins under a lock (same as P1/P4)."""
    from research_orchestrator.file_lock import file_lock
    path = _artifact_path(out_dir, artifact["cutoff_iso"], artifact["ingest_class"])
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(artifact, ensure_ascii=False, indent=1)
    with file_lock(path.parent / (path.name + ".lock")):
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing == artifact:
                return path
            raise AssessedFlashConflictError(
                f"assessed-flash artifact for ({artifact['ingest_class']}, "
                f"{artifact['cutoff_iso']}) already exists with different content — "
                f"write-once, refusing to overwrite a possibly-consumed version")
        fd, tmp = tempfile.mkstemp(suffix=".json.tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(blob)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    return path


def load_assessed_flash_artifact(path) -> dict:
    """Load + re-verify both hashes (a tampered artifact, or an altered consumed-P1 SHA,
    changes artifact_sha256 → refused)."""
    artifact = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(artifact, dict) or artifact.get("artifact_schema") != ARTIFACT_SCHEMA:
        raise ValueError("not an nf_assessed_flash_v1 artifact")
    body = {k: v for k, v in artifact.items() if k != "artifact_sha256"}
    if seal_hash(body) != artifact.get("artifact_sha256"):
        raise ValueError("artifact_sha256 mismatch — assessed-flash artifact tampered")
    if seal_hash(sorted(x["cluster"]["fact_occurrence_id"] for x in artifact["assessed"])) \
            != artifact["population_hash"]:
        raise ValueError("population_hash mismatch — assessed set altered")
    return artifact


def main() -> int:
    ap = argparse.ArgumentParser(description="NF market-wide cluster+route+assess (P2)")
    ap.add_argument("--cutoff", required=True)
    ap.add_argument("--ingest-class", default="history_bulk",
                    choices=["forward", "history_bulk"])
    ap.add_argument("--typed-artifact", required=True, help="path to the P1 typed-flash artifact")
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from workspace.research.ai_research_dept.engine import config as C
    from data_infra import provider_metadata  # noqa: F401 (real SW industry source)
    # reference inputs are assembled from existing sources; kept in the CLI (not the core)
    registry, industry_terms, concept_terms = _build_reference_inputs(args.cutoff)
    out_dir = Path(args.out_dir) if args.out_dir else C.OUT_ROOT / "nf_assessed_flash"
    artifact = assess_day_flashes(
        args.cutoff, ingest_class=args.ingest_class,
        typed_artifact=Path(args.typed_artifact), registry=registry,
        industry_terms=industry_terms, concept_terms=concept_terms)
    path = write_assessed_flash_artifact(artifact, out_dir)
    logger.info("assessed %d flashes @ %s (%s) -> %s",
                artifact["n_flashes"], artifact["cutoff_iso"], args.ingest_class, path)
    return 0


def _build_reference_inputs(cutoff):
    """CLI-side assembly of the injected reference inputs from existing sources
    (kept out of the testable core). Left as a thin seam; the per-source PIT details
    are wired when the offline P2 driver is first run for real."""
    raise NotImplementedError(
        "P2 CLI reference assembly (alias registry from stock_basic as-of cutoff, "
        "SW L1 industry-name set, THS concept-name set) is wired at first offline run; "
        "the testable core assess_day_flashes takes these injected")


if __name__ == "__main__":
    raise SystemExit(main())
