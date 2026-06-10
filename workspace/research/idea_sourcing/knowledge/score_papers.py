# ──────────────────────────────────────────────────────────────────────
# SCRIPT_STATUS header block.
# script_status: class_d_research_tooling
# formal_research_allowed: false
# touches_formal_data_plane: false
# pr2_audit_class: D
# notes: |
#   Value scorer (Layer 2 of the arXiv knowledge framework). Reads the local
#   arXiv idea store (optionally OpenAlex-enriched), scores every paper with the
#   taxonomy backbone, and writes a ranked shortlist. DETERMINISTIC + offline
#   (no network) — given the same store it produces the same ranking, so the
#   triage is reproducible. Writes ONLY under knowledge/. Touches no formal data.
#
#   The composite score is a TRIAGE PRIOR, not a verdict: it estimates
#   P(paper yields a new, orthogonal, deployable A-share factor) from keyword
#   evidence. The precision verdict is the human/LLM read of the top slice
#   (build_research_map.py + the analyst). A paper is a hypothesis source,
#   never evidence (CLAUDE.md §3.5, §7).
# ──────────────────────────────────────────────────────────────────────
"""
Score & rank arXiv papers by *value to this system*.

value ≈ P(yields a new, orthogonal, DEPLOYABLE A-share factor), estimated from:
  relevance_gate  is it cross-sectional EQUITY at all?      (gate, multiplies)
  dimension_value where does its alpha live × can we build? (taxonomy status)
  empirical       does the abstract report real OOS results?
  recency         frontier preference (newer ranks higher)
  china           A-share-specific bonus
  impact          OpenAlex citations / venue (credibility; sparse for frontier)

Two presets:
  frontier (default)  dimension/empirics/recency dominate; impact is a tiebreak.
                      Use to FIND NEW DIRECTIONS (classic cited anomalies are
                      already saturated for our book).
  established         impact dominates; surfaces the canonical, well-cited work.

Usage
-----
  venv/Scripts/python.exe workspace/research/idea_sourcing/knowledge/score_papers.py
  ...score_papers.py --preset established --top 40
  ...score_papers.py --min-relevance 0.3 --top 60 --out-prefix knowledge/ranked
"""
from __future__ import annotations

import argparse
import logging
import math
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from workspace.research.idea_sourcing.knowledge import taxonomy as tax  # noqa: E402

IDEA_DIR = PROJECT_ROOT / "workspace" / "research" / "idea_sourcing"
DEFAULT_STORE = IDEA_DIR / "store" / "arxiv_qfin.parquet"
DEFAULT_ENRICHED = IDEA_DIR / "store" / "arxiv_qfin_enriched.parquet"
KNOWLEDGE_DIR = IDEA_DIR / "knowledge"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("score_papers")

# Composite weights per preset (the blended part; relevance_gate multiplies it).
PRESETS: dict[str, dict[str, float]] = {
    "frontier":    {"dimension": 0.42, "empirical": 0.22, "recency": 0.16, "impact": 0.12, "china": 0.08},
    "established": {"dimension": 0.20, "empirical": 0.20, "recency": 0.05, "impact": 0.45, "china": 0.10},
}

RECENCY_FLOOR_YEAR = 2015     # papers at/below this get recency 0
RECENCY_CEIL_YEAR = 2026      # current frontier
IMPACT_CITE_CAP = 500         # citations giving impact≈1 (log-scaled)
EMPIRICAL_CAP = 5             # empirical-term hits giving empirical 1.0


def _year_of(published: str) -> int | None:
    if not published or len(str(published)) < 4:
        return None
    try:
        return int(str(published)[:4])
    except ValueError:
        return None


def _relevance_gate(pos: int, neg: int, hard_neg: int = 0) -> float:
    """Smooth gate in [0.05, 1.0]. Clearly out-of-scope (many neg, few pos)
    collapses toward the floor and zeroes the composite regardless of empirics.
    A hard-veto term (different asset class — crypto/FX/bond) caps the gate at
    0.12 no matter how much equity-factor vocabulary the paper incidentally uses."""
    raw = 0.20 + 0.20 * pos - 0.25 * neg
    gate = max(0.05, min(1.0, raw))
    if hard_neg > 0:
        gate = min(gate, 0.12)
    return gate


def _recency(year: int | None) -> float:
    if year is None:
        return 0.3   # unknown date — mild penalty, not zero
    span = RECENCY_CEIL_YEAR - RECENCY_FLOOR_YEAR
    return max(0.0, min(1.0, (year - RECENCY_FLOOR_YEAR) / span))


def _impact(citations) -> float:
    try:
        c = float(citations)
    except (TypeError, ValueError):
        return 0.0
    if c <= 0 or math.isnan(c):
        return 0.0
    return min(1.0, math.log1p(c) / math.log1p(IMPACT_CITE_CAP))


def _dimension_value(dim_hits: dict[str, list[str]]) -> tuple[float, str | None, int]:
    """(value, primary_dim_key, n_frontier_open_dims). value = primary dim's
    status weight + a bonus when the paper genuinely touches >1 OPEN frontier."""
    if not dim_hits:
        return (0.0, None, 0)
    primary = tax.best_dimension(dim_hits)
    base = tax.STATUS_VALUE.get(tax.DIM_BY_KEY[primary].status, 0.0)
    n_open = sum(1 for k, h in dim_hits.items()
                 if tax.DIM_BY_KEY[k].status == tax.FRONTIER_OPEN and len(h) >= 2)
    bonus = 0.15 if (n_open >= 2 or (n_open >= 1 and tax.DIM_BY_KEY[primary].status != tax.FRONTIER_OPEN
                                     and any(tax.DIM_BY_KEY[k].status == tax.FRONTIER_OPEN and len(h) >= 2
                                             for k, h in dim_hits.items()))) else 0.0
    return (min(1.0, base + bonus), primary, n_open)


def score_paper(title: str, abstract: str, citations=None) -> dict:
    text = f"{title}. {abstract}"
    pos = len(tax.lexicon_hits(text, tax.RELEVANCE_POS))
    neg = len(tax.lexicon_hits(text, tax.RELEVANCE_NEG))
    hard_neg_hits = tax.lexicon_hits(text, tax.RELEVANCE_HARD_NEG)
    gate = _relevance_gate(pos, neg, hard_neg=len(hard_neg_hits))

    dim_hits = tax.score_dimensions(text)
    dim_val, primary, n_open = _dimension_value(dim_hits)

    emp_hits = tax.lexicon_hits(text, tax.EMPIRICAL_TERMS)
    empirical = min(len(emp_hits), EMPIRICAL_CAP) / EMPIRICAL_CAP
    china_hits = tax.lexicon_hits(text, tax.CHINA_TERMS)
    china = 1.0 if china_hits else 0.0
    impact = _impact(citations)

    buildable, lacked = (False, [])
    if primary is not None:
        buildable, lacked = tax.feasibility_for_dimension(primary)
        status = tax.DIM_BY_KEY[primary].status
    else:
        status = None
    return {
        "primary_dim": primary, "dim_status": status, "buildable_now": buildable,
        "lacked_data": "; ".join(lacked),
        "all_dims": "; ".join(f"{k}({len(v)})" for k, v in
                              sorted(dim_hits.items(), key=lambda kv: -len(kv[1]))),
        "n_frontier_open_dims": n_open,
        "rel_pos": pos, "rel_neg": neg, "relevance_gate": round(gate, 3),
        "dimension_value": round(dim_val, 3), "empirical": round(empirical, 3),
        "china": china, "impact": round(impact, 3),
        "matched_empirical": "; ".join(emp_hits[:6]), "matched_china": "; ".join(china_hits[:4]),
    }


def composite(row: dict, weights: dict[str, float]) -> float:
    blend = (weights["dimension"] * row["dimension_value"]
             + weights["empirical"] * row["empirical"]
             + weights["recency"] * row["recency"]
             + weights["impact"] * row["impact"]
             + weights["china"] * row["china"])
    return round(row["relevance_gate"] * blend, 4)


def main() -> int:
    ap = argparse.ArgumentParser(description="Score & rank arXiv papers by value to this system.")
    ap.add_argument("--store", default=str(DEFAULT_STORE))
    ap.add_argument("--enriched", default=str(DEFAULT_ENRICHED),
                    help="Optional OpenAlex-enriched store (adds cited_by_count). Used if present.")
    ap.add_argument("--preset", choices=list(PRESETS), default="frontier")
    ap.add_argument("--top", type=int, default=40, help="How many to print / write to the md shortlist.")
    ap.add_argument("--min-relevance", type=float, default=0.25,
                    help="Drop papers whose relevance_gate is below this before ranking.")
    ap.add_argument("--out-prefix", default=str(KNOWLEDGE_DIR / "ranked_papers"),
                    help="Output path prefix (.parquet + .md).")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    import pandas as pd
    store = Path(args.store)
    if not store.exists():
        log.error("arXiv store missing: %s — run fetch_arxiv_qfin.py first.", store)
        return 1
    df = pd.read_parquet(store)
    log.info("loaded %d papers from %s", len(df), store)

    # Optional impact enrichment.
    cite_map: dict[str, float] = {}
    enr = Path(args.enriched)
    if enr.exists():
        edf = pd.read_parquet(enr)
        if "cited_by_count" in edf.columns and "arxiv_id" in edf.columns:
            cite_map = dict(zip(edf["arxiv_id"].astype(str),
                                pd.to_numeric(edf["cited_by_count"], errors="coerce")))
            log.info("impact enrichment: %d papers have OpenAlex citations", len(cite_map))
    else:
        log.info("no OpenAlex enrichment found (%s) — impact=0 for all (frontier preset is robust to this).", enr.name)

    weights = PRESETS[args.preset]
    recs = []
    for _, r in df.iterrows():
        aid = str(r.get("arxiv_id", ""))
        sc = score_paper(str(r.get("title", "")), str(r.get("abstract", "")), cite_map.get(aid))
        year = _year_of(r.get("published", ""))
        sc["recency"] = round(_recency(year), 3)
        sc.update({
            "arxiv_id": aid, "year": year, "published": str(r.get("published", ""))[:10],
            "primary_category": str(r.get("primary_category", "")),
            "title": str(r.get("title", "")), "abstract": str(r.get("abstract", "")),
            "url": str(r.get("abs_url", "") or r.get("pdf_url", "")),
            "citations": cite_map.get(aid),
        })
        sc["composite"] = composite(sc, weights)
        recs.append(sc)

    out = pd.DataFrame(recs)
    out = out[out["relevance_gate"] >= args.min_relevance].copy()
    out = out.sort_values("composite", ascending=False).reset_index(drop=True)
    out.insert(0, "rank", range(1, len(out) + 1))
    log.info("scored %d papers (preset=%s); %d pass relevance>=%.2f",
             len(recs), args.preset, len(out), args.min_relevance)

    # Console summary by status.
    print(f"\n== Top {args.top} by value (preset={args.preset}) ==")
    print(f"{'#':>3}  {'score':>5}  {'dim_status':<16} {'build':<5} {'yr':<4} dim / title")
    for _, r in out.head(args.top).iterrows():
        flag = "yes" if r["buildable_now"] else ("BLK" if r["dim_status"] in
               (tax.FRONTIER_BLOCKED, tax.NOT_PORTABLE) else "-")
        print(f"{r['rank']:>3}  {r['composite']:.3f}  {str(r['dim_status'] or '—'):<16} "
              f"{flag:<5} {str(r['year'] or '????'):<4} {str(r['primary_dim'] or '—'):<22} "
              f"{r['title'][:70]}")

    # Status mix among the top slice.
    head = out.head(args.top)
    mix = head["dim_status"].value_counts(dropna=False).to_dict()
    print(f"\nstatus mix (top {args.top}): {mix}")

    if args.dry_run:
        log.info("DRY RUN — nothing written.")
        return 0

    prefix = Path(args.out_prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    cols_keep = ["rank", "composite", "primary_dim", "dim_status", "buildable_now", "lacked_data",
                 "relevance_gate", "dimension_value", "empirical", "recency", "china", "impact",
                 "n_frontier_open_dims", "all_dims", "matched_china", "matched_empirical",
                 "year", "published", "primary_category", "citations", "arxiv_id", "title", "url", "abstract"]
    out[cols_keep].to_parquet(prefix.with_suffix(".parquet"), index=False)

    # Markdown shortlist — FRONTIER_OPEN first (where deployable alpha lives).
    md = [f"# arXiv value-ranked shortlist — preset `{args.preset}`", "",
          f"*Generated from {len(df)} papers in `{store.name}`"
          f"{' (+OpenAlex impact)' if cite_map else ''}. Score = relevance_gate × "
          f"weighted(dimension·empirical·recency·impact·china). A TRIAGE PRIOR, not a verdict — "
          f"the LLM read of the top slice is the precision pass.*", ""]
    order = [tax.FRONTIER_OPEN, tax.METHOD, tax.FRONTIER_BLOCKED, tax.SATURATED, tax.NOT_PORTABLE, None]
    for st in order:
        sub = head[head["dim_status"] == st] if st is not None else head[head["dim_status"].isna()]
        if len(sub) == 0:
            continue
        label = st or "UNCLASSIFIED"
        md += [f"## {label}  ({len(sub)} of top {args.top})", "",
               "| # | score | dim | build | yr | title |", "|---|---|---|---|---|---|"]
        for _, r in sub.iterrows():
            b = "✅" if r["buildable_now"] else ("⛔" if st in (tax.FRONTIER_BLOCKED, tax.NOT_PORTABLE) else "·")
            t = r["title"].replace("|", "/")
            md.append(f"| {r['rank']} | {r['composite']:.3f} | {r['primary_dim'] or '—'} | {b} | "
                      f"{r['year'] or '—'} | [{t[:88]}]({r['url']}) |")
        md.append("")
    prefix.with_suffix(".md").write_text("\n".join(md), encoding="utf-8")
    log.info("wrote %s(.parquet/.md)", prefix)
    return 0


if __name__ == "__main__":
    sys.exit(main())
