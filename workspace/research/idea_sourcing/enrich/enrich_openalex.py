# ──────────────────────────────────────────────────────────────────────
# SCRIPT_STATUS header block.
# script_status: class_d_research_tooling
# formal_research_allowed: false
# touches_formal_data_plane: false
# pr2_audit_class: D
# notes: |
#   Impact-enrichment (Layer 4 of the arXiv knowledge framework). For each
#   paper in the local arXiv store, looks it up in OpenAlex (keyless polite
#   pool, verified reachable 2026-06-08) to attach cited_by_count + venue +
#   type + concepts — the credibility/impact signal the value scorer's
#   `impact` term and the `established` preset use. Read-only against OpenAlex;
#   writes ONLY store/arxiv_qfin_enriched.parquet (idempotent cache — re-runs
#   only fill un-enriched ids unless --refresh). Touches no formal data plane.
#   Sparse-by-design: frontier 2026 preprints often have 0 citations / no
#   OpenAlex record yet — that is expected and the frontier preset is robust
#   to it (impact weight 0.12).
# ──────────────────────────────────────────────────────────────────────
"""
Enrich the arXiv idea store with OpenAlex citation / venue metadata.

Match strategy per paper:
  1. by DOI            api.openalex.org/works/doi:<doi>            (exact)
  2. else title search api.openalex.org/works?search=<title>...   (fuzzy-verify)
A candidate is accepted only if its normalized title shares >= MATCH_JACCARD
of tokens with ours (guards against wrong-paper matches on common titles).

Politeness: OpenAlex keyless "polite pool" via mailto=. ~3 req/s (sleep 0.34).

Usage
-----
  venv/Scripts/python.exe workspace/research/idea_sourcing/enrich/enrich_openalex.py
  ...enrich_openalex.py --limit 200            # cap work this run
  ...enrich_openalex.py --refresh              # re-enrich everything
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
IDEA_DIR = PROJECT_ROOT / "workspace" / "research" / "idea_sourcing"
DEFAULT_STORE = IDEA_DIR / "store" / "arxiv_qfin.parquet"
DEFAULT_OUT = IDEA_DIR / "store" / "arxiv_qfin_enriched.parquet"

OPENALEX = "https://api.openalex.org/works"
MAILTO = "quant-idea-sourcing@example.com"   # polite-pool identifier (no account needed)
USER_AGENT = "quant-research-idea-sourcing/0.1 (OpenAlex enrichment; polite pool)"
MATCH_JACCARD = 0.55

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("enrich_openalex")


def _norm_tokens(title: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", str(title).lower()) if len(w) > 2}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _get_json(url: str, retries: int = 3) -> dict | None:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 404):
                return None   # malformed/absent — retrying won't help
            wait = 3 * (attempt + 1)
            log.warning("OpenAlex HTTP %s; retry in %ss", exc.code, wait)
            time.sleep(wait)
        except Exception as exc:  # noqa: BLE001
            wait = 3 * (attempt + 1)
            log.warning("OpenAlex error %s; retry in %ss", exc, wait)
            time.sleep(wait)
    return None


def _extract(work: dict) -> dict:
    src = ((work.get("primary_location") or {}).get("source") or {})
    concepts = [c.get("display_name") for c in (work.get("concepts") or [])[:4] if c.get("display_name")]
    return {
        "openalex_id": work.get("id", ""),
        "cited_by_count": work.get("cited_by_count", 0),
        "oa_publication_year": work.get("publication_year"),
        "venue": src.get("display_name", "") or "",
        "venue_type": src.get("type", "") or "",
        "work_type": work.get("type", "") or "",
        "is_published": bool(src.get("display_name")) and (work.get("type") != "preprint"),
        "concepts": "; ".join(concepts),
        "oa_matched": True,
    }


def _empty_match() -> dict:
    return {"openalex_id": "", "cited_by_count": float("nan"), "oa_publication_year": None,
            "venue": "", "venue_type": "", "work_type": "", "is_published": False,
            "concepts": "", "oa_matched": False}


def _lookup(title: str, doi: str, sleep: float) -> dict:
    ours = _norm_tokens(title)
    # 1. DOI exact
    doi = (doi or "").strip()
    if doi:
        d = doi.lower().replace("https://doi.org/", "").replace("doi.org/", "")
        url = f"{OPENALEX}/doi:{urllib.parse.quote(d)}?mailto={MAILTO}"
        w = _get_json(url)
        time.sleep(sleep)
        if w and isinstance(w, dict) and w.get("id"):
            return _extract(w)
    # 2. title search + fuzzy verify. OpenAlex `search=` 400s on punctuation
    # (?, :, quotes) even URL-encoded — sanitize to plain alphanumeric words.
    if title:
        clean = " ".join(w for w in re.split(r"[^A-Za-z0-9]+", title) if len(w) > 1)[:200]
        if not clean:
            return _empty_match()
        q = urllib.parse.quote(clean)
        url = f"{OPENALEX}?search={q}&per-page=3&mailto={MAILTO}"
        res = _get_json(url)
        time.sleep(sleep)
        for cand in (res or {}).get("results", [])[:3]:
            if _jaccard(ours, _norm_tokens(cand.get("display_name", ""))) >= MATCH_JACCARD:
                return _extract(cand)
    return _empty_match()


def main() -> int:
    ap = argparse.ArgumentParser(description="Enrich arXiv store with OpenAlex citations/venue.")
    ap.add_argument("--store", default=str(DEFAULT_STORE))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--limit", type=int, default=0, help="Max papers to (re)enrich this run (0 = all).")
    ap.add_argument("--sleep", type=float, default=0.34, help="Seconds between OpenAlex requests.")
    ap.add_argument("--refresh", action="store_true", help="Re-enrich even already-cached ids.")
    args = ap.parse_args()

    import pandas as pd
    store = Path(args.store)
    if not store.exists():
        log.error("arXiv store missing: %s", store)
        return 1
    df = pd.read_parquet(store)
    out_path = Path(args.out)

    done: dict[str, dict] = {}
    if out_path.exists() and not args.refresh:
        prev = pd.read_parquet(out_path)
        done = {str(r["arxiv_id"]): r.to_dict() for _, r in prev.iterrows()}
        log.info("resuming: %d already enriched", len(done))

    todo = [r for _, r in df.iterrows()
            if args.refresh or str(r.get("arxiv_id", "")) not in done
            or not done.get(str(r.get("arxiv_id", "")), {}).get("oa_matched", False)]
    if args.limit:
        todo = todo[: args.limit]
    log.info("enriching %d / %d papers (OpenAlex polite pool, sleep=%.2fs)", len(todo), len(df), args.sleep)

    rows = list(done.values())
    rows = [r for r in rows if str(r.get("arxiv_id", "")) not in
            {str(t.get("arxiv_id", "")) for t in todo}]  # drop rows we will re-fetch
    n_match = 0
    for i, r in enumerate(todo, 1):
        aid = str(r.get("arxiv_id", ""))
        meta = _lookup(str(r.get("title", "")), str(r.get("doi", "")), args.sleep)
        n_match += int(meta["oa_matched"])
        rows.append({"arxiv_id": aid, "title": str(r.get("title", "")), **meta})
        if i % 25 == 0 or i == len(todo):
            log.info("  progress %d/%d  (matched so far this run: %d)", i, len(todo), n_match)

    out = pd.DataFrame(rows)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(out_path, index=False)
    matched = int(out["oa_matched"].sum()) if "oa_matched" in out.columns else 0
    cited = out[out["cited_by_count"].fillna(0) > 0] if "cited_by_count" in out.columns else out.iloc[0:0]
    log.info("wrote %s (%d rows; %d OpenAlex-matched, %d with >=1 citation)",
             out_path, len(out), matched, len(cited))
    if len(cited):
        top = cited.sort_values("cited_by_count", ascending=False).head(8)
        print("\nMost-cited matched papers:")
        for _, r in top.iterrows():
            print(f"  {int(r['cited_by_count']):>6} cites | {str(r['venue'])[:28]:<28} | {r['title'][:70]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
