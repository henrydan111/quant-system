# ──────────────────────────────────────────────────────────────────────
# SCRIPT_STATUS header block.
# script_status: class_d_research_tooling
# formal_research_allowed: false
# touches_formal_data_plane: false
# pr2_audit_class: D
# notes: |
#   Research-map builder (Layer 3 of the arXiv knowledge framework). Reads the
#   value-scored ranked_papers.parquet and organizes the firehose into a
#   dimension-clustered RESEARCH MAP: per taxonomy dimension (with OUR
#   saturation status + data coverage), the top-ranked papers, whether the
#   direction is buildable on data we have, and — for the top BUILDABLE frontier
#   papers — DRAFT hypothesis-stub skeletons (OSAP-stub format) wiring the path
#   to pre-registration. Writes ONLY under knowledge/. Touches no formal data.
#   A stub is a DRAFT: non-registerable until a human implements the factor,
#   sets expected_effect, and confirms an unburned OOS window (CLAUDE.md §7/§10).
# ──────────────────────────────────────────────────────────────────────
"""
Cluster value-ranked arXiv papers into an actionable research map.

Inputs : knowledge/ranked_papers.parquet  (from score_papers.py)
Outputs: knowledge/research_map.parquet        machine-readable map rows
         knowledge/RESEARCH_DIRECTIONS.md       human deliverable (the read)
         knowledge/stubs/arxiv_<id>.json         draft pre-registration stubs

The .md is a SCAFFOLD for the analyst/LLM precision pass: each dimension lists
its top papers with an abstract snippet and a "→ A-share direction" slot. The
deterministic score is a triage prior; the read is the verdict.

Usage
-----
  venv/Scripts/python.exe workspace/research/idea_sourcing/knowledge/build_research_map.py
  ...build_research_map.py --top 80 --stubs 10
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from workspace.research.idea_sourcing.knowledge import taxonomy as tax  # noqa: E402

IDEA_DIR = PROJECT_ROOT / "workspace" / "research" / "idea_sourcing"
KNOWLEDGE_DIR = IDEA_DIR / "knowledge"
RANKED = KNOWLEDGE_DIR / "ranked_papers.parquet"
STUB_DIR = KNOWLEDGE_DIR / "stubs"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("research_map")

# Display order: where deployable alpha lives first, blocked/method context next.
STATUS_ORDER = [tax.FRONTIER_OPEN, tax.METHOD, tax.FRONTIER_BLOCKED, tax.SATURATED, tax.NOT_PORTABLE]
STATUS_BLURB = {
    tax.FRONTIER_OPEN: "We HAVE the data, have barely mined it — the highest-value target. "
                       "A new factor here can reach formal eligibility today.",
    tax.METHOD: "Cross-cutting methodology — improves how we COMBINE existing factors / construct "
                "portfolios, not a new raw signal. Feeds model_zoo / portfolio_risk / the gates.",
    tax.FRONTIER_BLOCKED: "Promising dimension but we LACK the data — value is as a DATA-ACQUISITION "
                          "direction, not buildable today.",
    tax.SATURATED: "Our 182-factor book already spans this; OSAP US-anomaly ports came back redundant. "
                   "Only a genuinely new variant is worth a marginal-contribution test.",
    tax.NOT_PORTABLE: "A-share structural mismatch (no data / shorting restricted). Excluded.",
}


def _snippet(abstract: str, n: int = 320) -> str:
    a = " ".join(str(abstract).split())
    return (a[:n] + "…") if len(a) > n else a


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(s).lower()).strip("_")[:48]


def _build_stub(row: dict, today: str) -> dict:
    """DRAFT pre-registration stub for a buildable frontier paper. Mirrors the
    OSAP triage stub: expected_effect INTENTIONALLY null (human fills their own
    A-share prediction); arXiv evidence carried as context only."""
    aid = str(row["arxiv_id"])
    dim = str(row["primary_dim"])
    proposed = f"arxiv_{_slug(dim)}_{_slug(aid)}"
    d = tax.DIM_BY_KEY.get(dim)
    data_need = "; ".join(f"{t}({tax.OUR_DATA.get(t, (False,'?',''))[1]})" for t in (d.data_tags if d else ()))
    thesis = (f"Paper '{str(row['title'])[:160]}' (arXiv:{aid}) proposes a signal in the "
              f"'{dim}' dimension. Hypothesis: an A-share adaptation predicts the cross-section "
              f"of forward returns. Test whether the published effect ports to A-shares.")
    mechanism = (f"Taxonomy dimension: {dim} ({row['dim_status']}). Buildable on: {data_need}. "
                 f"Abstract: {_snippet(row.get('abstract', ''), 400)}")
    rebal = "5d" if dim in {"informed_flow", "earnings_events", "behavioral_chips"} else "20d"
    return {
        "hypothesis": {
            "hypothesis_id": f"hyp_arxiv_{_slug(aid)}_{today}_001",
            "thesis_statement": thesis,
            "mechanism": mechanism,
            "source": {
                "source_type": "academic_paper", "identifier": f"arXiv:{aid}",
                "title": str(row["title"]), "authors": [], "url": str(row.get("url", "")),
                "publication_date": str(row.get("year", "")), "publisher": "arXiv preprint",
            },
            "factor_refs": [{"object_type": "composite_factor", "object_name": proposed}],
            "factor_yaml_hashes": [],
            "universe": "csi_all", "benchmark": "000905.SH",
            "time_split": {"is_start": "2015-01-01", "is_end": "2021-12-31",
                           "oos_start": "2022-01-01", "oos_end": "2024-12-31",
                           "walk_forward_config": {"train_years": 3, "validation_years": 1,
                                                   "test_years": 1, "step_years": 1}},
            "rebalance_frequency": rebal, "neutralization": ["size", "industry"],
            "expected_sign": 0,
            "expected_effect": None,   # INTENTIONALLY NULL — your A-share prediction
            "expected_decay_horizon_days": 20,
            "success_criteria": {"min_rank_icir": 0.025, "min_deflated_sharpe": 0.6,
                                 "min_cost_adjusted_sharpe": 0.4, "max_drawdown": 0.35,
                                 "max_annual_turnover": 4.0, "min_monotonicity_pvalue": 0.10,
                                 "max_correlation_to_approved": 0.80, "effect_size_must_be_in_ci": True,
                                 "custom_rules": []},
            "pre_registered_concerns": {
                "most_likely_failure_mode": f"[DRAFT] The paper's effect may not survive A-share "
                    f"microstructure (T+1, limit boards, retail flow) or may be subsumed by existing "
                    f"factors after neutralization.",
                "weakest_assumption": "[DRAFT] That the paper's construction maps faithfully to "
                    "Tushare A-share fields without definitional drift.",
                "what_would_falsify_this": "[DRAFT] Sealed-OOS rank-ICIR below the committed band, "
                    "or hard rules failing after realistic costs.",
                "priors_on_cost_sensitivity": "[DRAFT] Review turnover at the chosen rebalance.",
            },
            "pre_registered_at": "", "registered_by": "",
        },
        "_draft_review": {
            "GENERATED_BY": "build_research_map.py — DRAFT, not registerable as-is",
            "taxonomy_dimension": dim, "dim_status": str(row["dim_status"]),
            "buildable_now": bool(row.get("buildable_now")), "value_score": float(row.get("composite", 0)),
            "matched_dims": str(row.get("all_dims", "")),
            "arxiv_evidence_context_only": {
                "abstract": _snippet(row.get("abstract", ""), 700), "url": str(row.get("url", "")),
                "citations_openalex": (None if row.get("citations") is None else row.get("citations")),
            },
            "proposed_factor_name": proposed,
            "todo_before_registering": [
                f"Read the full paper; extract the EXACT signal construction.",
                f"Implement '{proposed}' in factor_library mapping it to A-share Tushare/Qlib fields "
                f"(PIT-safe Ref(...,1)); confirm fields are registered/approved.",
                "Run the SANDBOX screen + size/industry-neutralized MARGINAL-contribution test vs the "
                "catalog (marginal IC × low correlation — the house rule), NOT standalone ICIR.",
                "SET expected_effect = YOUR A-share prediction (point + CI + horizon).",
                "CONFIRM the OOS window is unburned, then factor_lifecycle (draft→candidate) → sealed-OOS.",
            ],
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the arXiv research-direction map from ranked papers.")
    ap.add_argument("--ranked", default=str(RANKED))
    ap.add_argument("--top", type=int, default=80, help="Papers to include in the map.")
    ap.add_argument("--per-dim", type=int, default=8, help="Max papers shown per dimension in the md.")
    ap.add_argument("--stubs", type=int, default=8, help="Draft stubs for top buildable frontier papers.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    import pandas as pd
    ranked = Path(args.ranked)
    if not ranked.exists():
        log.error("ranked file missing: %s — run score_papers.py first.", ranked)
        return 1
    df = pd.read_parquet(ranked).head(args.top).copy()
    log.info("loaded top %d ranked papers", len(df))

    # Machine-readable map rows.
    map_rows = df[["rank", "composite", "primary_dim", "dim_status", "buildable_now",
                   "lacked_data", "year", "title", "url", "arxiv_id"]].copy()

    # Directions summary (per dimension touched within the top slice).
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    md = [f"# arXiv Research-Direction Map", "",
          f"*Generated {today} from the top {len(df)} value-ranked papers "
          f"(`ranked_papers.parquet`). This is the knowledge framework's deliverable: the arXiv "
          f"firehose organized into actionable directions, clustered by OUR research-frontier "
          f"taxonomy and tagged with whether each is buildable on data we have.*", "",
          "**How to read:** dimensions are ordered by where deployable alpha lives for our book. "
          "`FRONTIER_OPEN` = we have the data and have barely mined it (build now). `METHOD` = improves "
          "how we combine what we have. `FRONTIER_BLOCKED` = great direction, needs data we lack. "
          "`SATURATED` = the 182-book already spans it. The score is a triage prior; the abstract "
          "snippet + your read is the verdict.", "",
          "> A paper is a **hypothesis source, never evidence**. Any factor it inspires still runs the "
          "full IS-only → sealed-OOS lifecycle, and must pass the size/industry-neutralized "
          "**marginal-contribution** test vs the catalog (CLAUDE.md §3.5, §7).", ""]

    # Summary table.
    md += ["## Directions summary", "",
           "| Dimension | Our status | Build? | # in top | Top score | Coverage note |",
           "|---|---|---|---|---|---|"]
    present = [k for k in [d.key for d in tax.DIMENSIONS]]
    counts = df["primary_dim"].value_counts().to_dict()
    # order by status then count
    def _statrank(dimkey):
        st = tax.DIM_BY_KEY[dimkey].status if dimkey in tax.DIM_BY_KEY else "ZZ"
        return (STATUS_ORDER.index(st) if st in STATUS_ORDER else 99, -counts.get(dimkey, 0))
    for dimkey in sorted([k for k in present if counts.get(k, 0) > 0], key=_statrank):
        d = tax.DIM_BY_KEY[dimkey]
        sub = df[df["primary_dim"] == dimkey]
        build = "✅" if d.buildable else ("⛔" if d.status in (tax.FRONTIER_BLOCKED, tax.NOT_PORTABLE) else "·")
        md.append(f"| {d.label} | {d.status} | {build} | {len(sub)} | {sub['composite'].max():.3f} | {d.note} |")
    md.append("")

    # Per-status, per-dimension sections.
    emitted_stubs: list[str] = []
    stub_budget = args.stubs
    for status in STATUS_ORDER:
        dims_here = [d for d in tax.DIMENSIONS if d.status == status and counts.get(d.key, 0) > 0]
        if not dims_here:
            continue
        md += [f"# {status}", "", f"*{STATUS_BLURB[status]}*", ""]
        for d in sorted(dims_here, key=lambda x: -counts.get(x.key, 0)):
            sub = df[df["primary_dim"] == d.key].head(args.per_dim)
            data_have = "; ".join(f"`{t}`→{tax.OUR_DATA.get(t,(False,'?',''))[1]}" for t in d.data_tags) or "—"
            lacked = ", ".join(t for t in d.data_tags if not tax.OUR_DATA.get(t, (False, "", ""))[0])
            buildline = "yes" if d.buildable else (f"NO — need {lacked}" if lacked else "n/a")
            md += [f"## {d.label}  ·  {len(df[df['primary_dim']==d.key])} papers", "",
                   f"- **Our coverage:** {d.note}",
                   f"- **Data:** {data_have}",
                   f"- **Buildable now:** {buildline}",
                   ""]
            for _, r in sub.iterrows():
                cites = "" if (r.get("citations") is None or (isinstance(r.get("citations"), float) and r.get("citations") != r.get("citations"))) else f" · {int(r['citations'])} cites"
                md += [f"### [{r['rank']}] {r['title']}  *(score {r['composite']:.3f}, {r['year'] or '—'}{cites})*",
                       f"{_snippet(r['abstract'])}",
                       f"[{r['url']}]({r['url']})",
                       f"→ **A-share direction:** _[extract: what factor would this become on our data? "
                       f"orthogonal to catalog? which fields?]_", ""]
                # stub for top buildable frontier papers
                if (stub_budget > 0 and status == tax.FRONTIER_OPEN and bool(r.get("buildable_now"))):
                    stub = _build_stub(r.to_dict(), datetime.now(timezone.utc).strftime("%Y%m%d"))
                    if not args.dry_run:
                        STUB_DIR.mkdir(parents=True, exist_ok=True)
                        p = STUB_DIR / f"arxiv_{_slug(r['arxiv_id'])}.json"
                        p.write_text(json.dumps(stub, indent=2, ensure_ascii=False), encoding="utf-8")
                    emitted_stubs.append(str(r["arxiv_id"]))
                    stub_budget -= 1

    if args.dry_run:
        log.info("DRY RUN — would write map + %d stubs", len(emitted_stubs))
        print("\n".join(md[:60]))
        return 0

    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    map_rows.to_parquet(KNOWLEDGE_DIR / "research_map.parquet", index=False)
    (KNOWLEDGE_DIR / "RESEARCH_DIRECTIONS.md").write_text("\n".join(md), encoding="utf-8")
    log.info("wrote RESEARCH_DIRECTIONS.md + research_map.parquet; emitted %d draft stubs: %s",
             len(emitted_stubs), ", ".join(emitted_stubs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
