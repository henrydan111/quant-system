# ──────────────────────────────────────────────────────────────────────
# SCRIPT_STATUS header block.
# script_status: class_d_research_tooling
# formal_research_allowed: false
# touches_formal_data_plane: false
# pr2_audit_class: D
# notes: |
#   Idea-sourcing fetcher (English-academic slice). Pulls newest arXiv
#   q-fin.* preprints into a local Parquet metadata store for research-idea
#   triage. Read-only against arXiv; writes ONLY under
#   workspace/research/idea_sourcing/store/. Does NOT touch the PIT ledger,
#   Qlib provider, field registry, or any of the 5 typed registries. A paper
#   sourced here is a HYPOTHESIS source, never evidence — any factor it
#   inspires still runs the full IS-only -> sealed-OOS lifecycle.
#   Respects the arXiv API ToU: >=3s between requests, single connection.
# ──────────────────────────────────────────────────────────────────────
"""
arXiv q-fin fetcher — lands newest Quantitative Finance preprints into a
local Parquet idea store.

Pipeline role:  fetch -> dedup -> store   (the LLM "extract testable claim"
step is intentionally NOT here — this pilot stops at a queryable store.)

Store:  workspace/research/idea_sourcing/store/arxiv_qfin.parquet
        one row per arXiv base id (latest version kept), with first_seen /
        last_seen timestamps so re-runs are incremental and idempotent.

Usage
-----
  # newest 100 across all q-fin subcategories (default)
  venv/Scripts/python.exe workspace/research/idea_sourcing/fetchers/fetch_arxiv_qfin.py

  # only portfolio-management + statistical-finance, newest 300
  ...fetch_arxiv_qfin.py --categories q-fin.PM,q-fin.ST --max-results 300

  # see what it would do without writing
  ...fetch_arxiv_qfin.py --dry-run

arXiv API ToU: one request every >=3 seconds, single connection. Do not lower
--sleep below 3.0 without reading https://info.arxiv.org/help/api/tou.html.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import ssl
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

PROJECT_ROOT = Path(__file__).resolve().parents[4]
STORE_DIR = PROJECT_ROOT / "workspace" / "research" / "idea_sourcing" / "store"
DEFAULT_STORE = STORE_DIR / "arxiv_qfin.parquet"

API_URL = "http://export.arxiv.org/api/query"
USER_AGENT = "quant-research-idea-sourcing/0.1 (arXiv q-fin idea triage; ToU-compliant)"

# All q-fin subcategories (https://arxiv.org/archive/q-fin).
QFIN_CATEGORIES = [
    "q-fin.CP",  # Computational Finance
    "q-fin.EC",  # Economics
    "q-fin.GN",  # General Finance
    "q-fin.MF",  # Mathematical Finance
    "q-fin.PM",  # Portfolio Management
    "q-fin.PR",  # Pricing of Securities
    "q-fin.RM",  # Risk Management
    "q-fin.ST",  # Statistical Finance
    "q-fin.TR",  # Trading and Market Microstructure
]

ATOM = "http://www.w3.org/2005/Atom"
OPENSEARCH = "http://a9.com/-/spec/opensearch/1.1/"
ARXIV = "http://arxiv.org/schemas/atom"
NS = {"a": ATOM, "o": OPENSEARCH, "arxiv": ARXIV}

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("fetch_arxiv_qfin")


def _build_search_query(categories: list[str], extra_term: str | None) -> str:
    cat_clause = " OR ".join(f"cat:{c}" for c in categories)
    q = f"({cat_clause})"
    if extra_term:
        q = f"{q} AND all:{extra_term}"
    return q


def _fetch_page(search_query: str, start: int, page_size: int, retries: int = 3) -> bytes:
    params = {
        "search_query": search_query,
        "start": start,
        "max_results": page_size,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    ctx = ssl.create_default_context()
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=40, context=ctx) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            last_exc = exc
            wait = 5 * (attempt + 1)
            log.warning("arXiv HTTP %s (start=%s); retry in %ss", exc.code, start, wait)
            time.sleep(wait)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            wait = 5 * (attempt + 1)
            log.warning("arXiv error %s (start=%s); retry in %ss", exc, start, wait)
            time.sleep(wait)
    raise RuntimeError(f"arXiv page fetch failed after {retries} tries (start={start}): {last_exc}")


def _text(el, path: str) -> str:
    found = el.findtext(path, default="", namespaces=NS)
    return " ".join(found.split()) if found else ""


def _parse_entries(xml_bytes: bytes) -> tuple[list[dict], int]:
    root = ET.fromstring(xml_bytes)
    total_el = root.find("o:totalResults", NS)
    total = int(total_el.text) if total_el is not None and total_el.text else 0
    records = []
    for e in root.findall("a:entry", NS):
        raw_id = _text(e, "a:id")  # e.g. http://arxiv.org/abs/2606.07450v1
        base_id, version = raw_id, ""
        if "/abs/" in raw_id:
            tail = raw_id.split("/abs/")[-1]
            if "v" in tail:
                base_id, version = tail.rsplit("v", 1)
            else:
                base_id = tail
        authors = [_text(a, "a:name") for a in e.findall("a:author", NS)]
        cats = [c.get("term") for c in e.findall("a:category", NS) if c.get("term")]
        prim = e.find("arxiv:primary_category", NS)
        pdf_url, abs_url = "", raw_id
        for link in e.findall("a:link", NS):
            if link.get("title") == "pdf":
                pdf_url = link.get("href", "")
            elif link.get("rel") == "alternate":
                abs_url = link.get("href", abs_url)
        records.append({
            "arxiv_id": base_id,
            "version": version,
            "title": _text(e, "a:title"),
            "abstract": _text(e, "a:summary"),
            "authors": "; ".join(authors),
            "primary_category": prim.get("term") if prim is not None else "",
            "categories": "; ".join(cats),
            "published": _text(e, "a:published"),
            "updated": _text(e, "a:updated"),
            "doi": _text(e, "arxiv:doi"),
            "journal_ref": _text(e, "arxiv:journal_ref"),
            "comment": _text(e, "arxiv:comment"),
            "pdf_url": pdf_url,
            "abs_url": abs_url,
            "source": "arxiv",
        })
    return records, total


def _load_store(path: Path):
    import pandas as pd
    if path.exists():
        return pd.read_parquet(path)
    return pd.DataFrame()


def _merge(existing, fetched: list[dict], now_iso: str):
    import pandas as pd
    new_df = pd.DataFrame(fetched)
    new_df["first_seen_utc"] = now_iso
    new_df["last_seen_utc"] = now_iso
    if existing is None or len(existing) == 0:
        merged = new_df
        n_new, n_upd = len(new_df), 0
    else:
        seen_ids = set(existing["arxiv_id"])
        is_new = ~new_df["arxiv_id"].isin(seen_ids)
        n_new = int(is_new.sum())
        n_upd = int((~is_new).sum())
        # Preserve original first_seen_utc for rows we already had.
        first_seen_map = dict(zip(existing["arxiv_id"], existing["first_seen_utc"]))
        new_df["first_seen_utc"] = new_df["arxiv_id"].map(first_seen_map).fillna(now_iso)
        combined = pd.concat([existing, new_df], ignore_index=True)
        # Keep the freshest fetch per id (new_df rows come last → keep="last").
        merged = combined.drop_duplicates(subset="arxiv_id", keep="last")
    merged = merged.sort_values("published", ascending=False).reset_index(drop=True)
    return merged, n_new, n_upd


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch newest arXiv q-fin preprints into a local idea store.")
    ap.add_argument("--categories", default=",".join(QFIN_CATEGORIES),
                    help="Comma-separated arXiv categories (default: all q-fin.*).")
    ap.add_argument("--max-results", type=int, default=100, help="Total newest papers to fetch.")
    ap.add_argument("--page-size", type=int, default=100, help="Results per request (arXiv max 2000).")
    ap.add_argument("--query", default=None, help="Optional extra full-text AND term (all:<term>).")
    ap.add_argument("--sleep", type=float, default=3.0, help="Seconds between requests (arXiv ToU >=3).")
    ap.add_argument("--out", default=str(DEFAULT_STORE), help="Parquet store path.")
    ap.add_argument("--dry-run", action="store_true", help="Fetch + report, but do not write the store.")
    args = ap.parse_args()

    if args.sleep < 3.0:
        log.warning("--sleep %.1f is below arXiv ToU (>=3s); raising to 3.0", args.sleep)
        args.sleep = 3.0

    categories = [c.strip() for c in args.categories.split(",") if c.strip()]
    search_query = _build_search_query(categories, args.query)
    out_path = Path(args.out)

    log.info("query: %s", search_query)
    log.info("target: newest %d (page size %d), store=%s%s",
             args.max_results, args.page_size, out_path, "  [DRY RUN]" if args.dry_run else "")

    fetched: list[dict] = []
    start, total = 0, None
    while len(fetched) < args.max_results:
        page_size = min(args.page_size, args.max_results - len(fetched))
        xml = _fetch_page(search_query, start, page_size)
        records, total = _parse_entries(xml)
        if not records:
            log.info("no more results at start=%d (total reported=%s)", start, total)
            break
        fetched.extend(records)
        log.info("progress: %d/%d fetched (arXiv reports %s total matches)",
                 len(fetched), args.max_results, total)
        start += len(records)
        if total is not None and start >= total:
            break
        if len(fetched) < args.max_results:
            time.sleep(args.sleep)

    if not fetched:
        log.error("nothing fetched — aborting without touching the store.")
        return 1

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    existing = _load_store(out_path)
    merged, n_new, n_upd = _merge(existing, fetched, now_iso)

    log.info("fetched=%d  new=%d  updated=%d  store_total=%d",
             len(fetched), n_new, n_upd, len(merged))
    print("\nNewest 5 in store:")
    for _, row in merged.head(5).iterrows():
        print(f"  [{row['published'][:10]}] {row['primary_category']:<9} {row['title'][:90]}")

    if args.dry_run:
        log.info("DRY RUN — store not written.")
        return 0

    STORE_DIR.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(out_path, index=False)
    log.info("wrote %s (%d rows)", out_path, len(merged))
    return 0


if __name__ == "__main__":
    sys.exit(main())
