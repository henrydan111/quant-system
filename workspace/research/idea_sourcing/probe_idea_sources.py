# ──────────────────────────────────────────────────────────────────────
# SCRIPT_STATUS header block.
# script_status: class_d_research_tooling
# formal_research_allowed: false
# touches_formal_data_plane: false
# pr2_audit_class: D
# notes: |
#   Read-only feasibility probe for the idea-sourcing pipeline (English
#   academic slice). Makes ONE minimal real API call per source and records
#   ACCESS / RATE_LIMITED / BLOCKED / ERROR + a sample record. Stdlib only
#   (no new dependency) so it runs before anything is installed. This is
#   upstream idea-sourcing tooling — it does NOT read or write the PIT
#   ledger / Qlib provider / any registry. Any factor later derived from a
#   sourced idea still goes through the full IS-only -> sealed-OOS gates.
# ──────────────────────────────────────────────────────────────────────
"""
Idea-sourcing feasibility probe — English academic slice.

Mirrors the house norm established by scripts/probe_tushare_endpoints.py:
"ground truth = live API probe, not memorized docs". For each free source we
intend to automate, fire one minimal read-only call and classify the result.

Sources probed
--------------
  arxiv        arXiv ATOM API (q-fin.* preprints, full text + abstract)
  semanticsch  Semantic Scholar Graph API (citation graph, 200M+ papers)
  openalex     OpenAlex works API (free scholarly metadata graph)
  osap         Open Source Asset Pricing data page reachability
               (212 published predictors; bulk pull via `pip install
                openassetpricing`, this probe only checks the host is up)

Usage
-----
  venv/Scripts/python.exe workspace/research/idea_sourcing/probe_idea_sources.py

Writes a structured JSON report to workspace/outputs/ and prints a summary
table. Exit code 0 if every source returned ACCESS, else 1.
"""
from __future__ import annotations

import json
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

# Project-root-relative output dir (this file is workspace/research/idea_sourcing/).
PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = PROJECT_ROOT / "workspace" / "outputs"

USER_AGENT = (
    "quant-research-idea-sourcing-probe/0.1 "
    "(read-only feasibility check; one request per source)"
)
TIMEOUT_S = 25


def _http_get(url: str, accept: str | None = None) -> tuple[int, bytes, float]:
    """Single GET. Returns (http_code, body_bytes, latency_ms). Raises on transport error."""
    headers = {"User-Agent": USER_AGENT}
    if accept:
        headers["Accept"] = accept
    req = urllib.request.Request(url, headers=headers, method="GET")
    ctx = ssl.create_default_context()
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=TIMEOUT_S, context=ctx) as resp:
        body = resp.read()
        code = resp.getcode()
    latency_ms = round((time.perf_counter() - t0) * 1000, 1)
    return code, body, latency_ms


def _classify_error(exc: Exception) -> tuple[str, str]:
    """Map a transport exception to (status, note)."""
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code == 429:
            return "RATE_LIMITED", f"HTTP 429 (rate limited): {exc.reason}"
        if exc.code in (401, 403):
            return "BLOCKED", f"HTTP {exc.code} (auth/forbidden): {exc.reason}"
        return "ERROR", f"HTTP {exc.code}: {exc.reason}"
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, (socket.timeout, TimeoutError)):
            return "ERROR", "network timeout (no response within %ss)" % TIMEOUT_S
        return "ERROR", f"network/URL error: {reason}"
    return "ERROR", f"{type(exc).__name__}: {exc}"


# ── per-source probes ────────────────────────────────────────────────────

def probe_arxiv() -> dict:
    url = (
        "http://export.arxiv.org/api/query?"
        "search_query=cat:q-fin.PM&start=0&max_results=2"
        "&sortBy=submittedDate&sortOrder=descending"
    )
    rec = {"source": "arxiv", "endpoint": url, "free": True,
           "auth_required": False, "rate_limit": "1 req / 3 s (legacy API ToU)"}
    try:
        code, body, latency = _http_get(url, accept="application/atom+xml")
        ns = {"a": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(body)
        entries = root.findall("a:entry", ns)
        sample = None
        if entries:
            e = entries[0]
            sample = {
                "id": (e.findtext("a:id", default="", namespaces=ns) or "").strip(),
                "title": " ".join((e.findtext("a:title", default="", namespaces=ns) or "").split()),
                "published": e.findtext("a:published", default="", namespaces=ns),
                "primary_category": (e.find("{http://arxiv.org/schemas/atom}primary_category").get("term")
                                     if e.find("{http://arxiv.org/schemas/atom}primary_category") is not None else None),
            }
        rec.update(status="ACCESS", http_code=code, latency_ms=latency,
                   n_returned=len(entries), sample=sample,
                   note="ATOM parsed OK; full abstract+PDF link available per entry.")
    except Exception as exc:  # noqa: BLE001 - probe must classify every failure
        status, note = _classify_error(exc)
        rec.update(status=status, note=note, sample=None)
    return rec


def probe_semantic_scholar() -> dict:
    """Probe S2 with light backoff. Honours an optional free key in env IDEA_S2_API_KEY."""
    import os
    url = (
        "https://api.semanticscholar.org/graph/v1/paper/search?"
        "query=cross-sectional+stock+return+predictability&limit=2"
        "&fields=title,year,abstract,externalIds,citationCount"
    )
    api_key = os.environ.get("IDEA_S2_API_KEY")
    rec = {"source": "semanticscholar", "endpoint": url, "free": True,
           "auth_required": False, "key_present": bool(api_key),
           "rate_limit": "keyless public pool (shared, often 429s); free x-api-key gives a dedicated quota; bulk datasets downloadable"}
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if api_key:
        headers["x-api-key"] = api_key
    last_exc = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            ctx = ssl.create_default_context()
            t0 = time.perf_counter()
            with urllib.request.urlopen(req, timeout=TIMEOUT_S, context=ctx) as resp:
                body = resp.read()
                code = resp.getcode()
            latency = round((time.perf_counter() - t0) * 1000, 1)
            data = json.loads(body)
            items = data.get("data", []) or []
            sample = None
            if items:
                it = items[0]
                sample = {"title": it.get("title"), "year": it.get("year"),
                          "citationCount": it.get("citationCount"),
                          "has_abstract": bool(it.get("abstract"))}
            rec.update(status="ACCESS", http_code=code, latency_ms=latency,
                       n_returned=len(items), sample=sample, attempts=attempt + 1,
                       note="JSON parsed OK; abstracts + citation graph available.")
            return rec
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            time.sleep(4)
    status, note = _classify_error(last_exc)
    if status == "RATE_LIMITED":
        note += (" | keyless pool exhausted from this IP after 3 tries. "
                 "Fix: request a free S2 API key (x-api-key) or use the bulk Datasets snapshots. "
                 "OpenAlex is a keyless substitute for the same citation-graph role.")
    rec.update(status=status, note=note, sample=None, attempts=3)
    return rec


def probe_openalex() -> dict:
    url = (
        "https://api.openalex.org/works?"
        "search=momentum%20factor%20stock%20returns&per-page=2"
    )
    rec = {"source": "openalex", "endpoint": url, "free": True,
           "auth_required": False, "rate_limit": "100k/day free; polite pool via mailto"}
    try:
        code, body, latency = _http_get(url, accept="application/json")
        data = json.loads(body)
        items = data.get("results", []) or []
        meta = data.get("meta", {}) or {}
        sample = None
        if items:
            it = items[0]
            sample = {"title": it.get("title") or it.get("display_name"),
                      "year": it.get("publication_year"),
                      "doi": it.get("doi")}
        rec.update(status="ACCESS", http_code=code, latency_ms=latency,
                   n_returned=len(items), total_hits=meta.get("count"),
                   sample=sample, note="JSON parsed OK; full metadata graph.")
    except Exception as exc:  # noqa: BLE001
        status, note = _classify_error(exc)
        rec.update(status=status, note=note, sample=None)
    return rec


def probe_osap() -> dict:
    rec = {"source": "osap", "free": True, "auth_required": False,
           "rate_limit": "n/a (static dataset download)"}
    last = None
    for url in ("https://www.openassetpricing.com/data/", "https://openassetpricing.com/"):
        rec["endpoint"] = url
        try:
            code, body, latency = _http_get(url)
            ok = code == 200 and len(body) > 0
            rec.update(status="ACCESS" if ok else "ERROR", http_code=code, latency_ms=latency,
                       sample={"bytes": len(body)},
                       note=("Data page reachable. NOTE: verifies only that the host is up; "
                             "the actual 212-predictor bulk pull uses `pip install openassetpricing` "
                             "(Peng Li), which downloads from a separate data host."))
            return rec
        except Exception as exc:  # noqa: BLE001
            last = exc
    status, note = _classify_error(last)
    rec.update(status=status, sample=None,
               note=(note + " | The openassetpricing.com website is UNREACHABLE from this "
                     "environment (TLS handshake timeout). This does NOT verify the data path: "
                     "the dataset is pulled by `pip install openassetpricing` from a different host. "
                     "UNVERIFIED here — resolve with: pip install openassetpricing && pull one signal."))
    return rec


PROBES = [probe_arxiv, probe_semantic_scholar, probe_openalex, probe_osap]


def main() -> int:
    print("=" * 74)
    print("Idea-sourcing feasibility probe — English academic slice (read-only)")
    print("=" * 74)
    results = []
    for fn in PROBES:
        name = fn.__name__.replace("probe_", "")
        print(f"\n[probe] {name} ...", flush=True)
        rec = fn()
        results.append(rec)
        line = f"  -> {rec['status']:<12}"
        if rec.get("http_code") is not None:
            line += f" http={rec.get('http_code')}"
        if rec.get("latency_ms") is not None:
            line += f" {rec.get('latency_ms')}ms"
        if rec.get("n_returned") is not None:
            line += f" n={rec.get('n_returned')}"
        print(line)
        if rec.get("sample"):
            print(f"     sample: {json.dumps(rec['sample'], ensure_ascii=False)[:200]}")
        print(f"     note:   {rec.get('note')}")
        # Be a good citizen between sources even though these are different hosts.
        time.sleep(1.0)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"idea_sources_probe_{ts}.json"
    report = {"probe_utc": ts, "user_agent": USER_AGENT, "results": results}
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    n_ok = sum(1 for r in results if r["status"] == "ACCESS")
    print("\n" + "-" * 74)
    print(f"Summary: {n_ok}/{len(results)} ACCESS")
    for r in results:
        print(f"  {r['source']:<16} {r['status']}")
    print(f"\nReport: {out_path}")
    return 0 if n_ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
