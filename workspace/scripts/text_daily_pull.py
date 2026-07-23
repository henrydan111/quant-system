# SCRIPT_STATUS: ACTIVE — Phase-2A daily forward text pull (scheduled task)
"""Daily incremental pull of the 4 ts_code-bearing text sources into the C1 store.

Design:
  - LOOKBACK = 4 calendar days each run: catches late replies/revisions and a
    missed run (machine off). Idempotent — content_hash dedup in text_store
    means overlapping pulls are free; a revision becomes a NEW row (C1).
  - anns_d uses offset pagination (busy days exceed 2000/call); a truncated
    day (M3: df.attrs['truncated']) counts as a FAILURE, never silent.
  - impl-review B5: every run writes a manifest JSON to logs/text_pull/ and
    exits NON-ZERO on ANY source failure — the forward runner reads the
    latest manifest and refuses a cycle whose text inputs are incomplete.
  - Sequential calls only (§6.1). Logs to logs/text_daily_pull.log (rotating).

B1 ops hardening (2026-07-22, FORWARD_PREREG §3 ops-repair channel; recorded
in mvp_pool_book/OPS_AUDIT_LOG.md — gate semantics UNCHANGED):
  - Per-source in-run circuit breaker: >= BREAKER_THRESHOLD consecutive
    exception failures for one source open the breaker — remaining days for
    that source are skipped this pass (still counted as failures, never
    silent) instead of hammering a downed endpoint (§6.1: back off, don't
    retry harder).
  - End-of-run retry pass: after a cooldown, every exception/skipped
    (source, day) pair is retried ONCE sequentially. Transient failures that
    survived TushareFetcher._safe_api_call's own retries get a second chance
    minutes later, converting a failed manifest into an ok one. Truncated
    days are NOT retried (page-cap, not transport).
  - Additive manifest audit fields (consumers unaffected — the forward
    runner's gates read only ok/run_ts/window/source_status/failures):
    ``attempts`` (per-call audit incl. pass 1|2), ``breaker_events``,
    ``retry_pass``, ``partial_run``, ``sources_pulled``.
  - --sources allows a targeted manual re-pull. A partial run NEVER writes
    pull_manifest_latest.json (the runner's latest-manifest gate must only
    ever see full-source runs) and un-attempted sources are marked
    ``not_attempted`` (never ok_*, so the coverage gate grants no credit).

Scheduled as Windows task `QuantTextDailyPull` (daily 20:30) — the forward
clean panel accrues through this job; without it, only fixtures exist. When
run as a script, a FULL run chains text_coverage_preflight.py afterwards
(best-effort, its own alert flag; never alters this job's exit code).
"""
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from datetime import date, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from data_infra.fetchers import TushareFetcher  # noqa: E402
from data_infra.text_store import ingest_rows  # noqa: E402

LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
handler = RotatingFileHandler(LOG_DIR / "text_daily_pull.log",
                              maxBytes=2_000_000, backupCount=3, encoding="utf-8")
logging.basicConfig(level=logging.INFO, handlers=[handler, logging.StreamHandler()],
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("text_daily_pull")

LOOKBACK_DAYS = 4
MANIFEST_DIR = LOG_DIR / "text_pull"
CN_TZ = "Asia/Shanghai"   # R2 Blocker-5: the ONLY decision timezone
SOURCES = ("anns_d", "research_report", "irm_qa_sh", "irm_qa_sz")
SOURCE_PUB_COL = {"anns_d": "rec_time", "research_report": None,
                  "irm_qa_sh": "pub_time", "irm_qa_sz": "pub_time"}
BREAKER_THRESHOLD = 2       # consecutive exception failures -> skip rest of pass
RETRY_COOLDOWN_S = 90.0     # wait before the retry pass
PREFLIGHT_SCRIPT = Path(__file__).resolve().parent / "text_coverage_preflight.py"


def _fetch(f: TushareFetcher, source: str, ymd: str) -> pd.DataFrame | None:
    if source == "anns_d":
        return f.fetch_anns_d_paged(ymd)
    if source == "research_report":
        return f.fetch_research_report(ymd)
    if source == "irm_qa_sh":
        return f.fetch_irm_qa_sh(ymd, ymd)
    return f.fetch_irm_qa_sz(ymd, ymd)


def _attempt(f: TushareFetcher, source: str, ymd: str, pass_no: int,
             counts: dict[str, int], attempts: list[dict]) -> str:
    """One (source, day) call. Returns outcome:
    ok_rows | ok_zero | error | truncated. Truncated frames are still
    ingested (dedup makes the eventual clean re-pull free)."""
    t0 = time.time()
    try:
        df = _fetch(f, source, ymd)
    except Exception as e:  # noqa: BLE001
        attempts.append({"source": source, "day": ymd, "pass": pass_no,
                         "outcome": "error", "error_type": type(e).__name__,
                         "error": str(e)[:300],
                         "elapsed_s": round(time.time() - t0, 2)})
        log.error("%s @%s (pass %d) failed: %s", source, ymd, pass_no, e)
        return "error"
    if df is None or df.empty:
        attempts.append({"source": source, "day": ymd, "pass": pass_no,
                         "outcome": "ok_zero", "rows": 0,
                         "elapsed_s": round(time.time() - t0, 2)})
        return "ok_zero"
    outcome = "truncated" if df.attrs.get("truncated") else "ok_rows"
    if outcome == "truncated":   # M3: incomplete day = failure, never silent
        log.error("%s @%s TRUNCATED — day incomplete, counted as failure",
                  source, ymd)
    ingest_rows(source, df, published_col=SOURCE_PUB_COL[source],
                retrieved_at=pd.Timestamp.now(tz=CN_TZ))
    counts[source] = counts.get(source, 0) + len(df)
    attempts.append({"source": source, "day": ymd, "pass": pass_no,
                     "outcome": outcome, "rows": len(df),
                     "elapsed_s": round(time.time() - t0, 2)})
    return outcome


def main(argv: list[str] | None = None, *, chain_preflight: bool = False) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", default=None,
                        help="comma list subset of %s — targeted manual re-pull; "
                             "partial runs never update pull_manifest_latest.json"
                             % ",".join(SOURCES))
    parser.add_argument("--no-retry-pass", action="store_true",
                        help="disable the end-of-run retry pass")
    parser.add_argument("--retry-cooldown", type=float, default=RETRY_COOLDOWN_S,
                        help="seconds to wait before the retry pass")
    parser.add_argument("--skip-preflight", action="store_true",
                        help="do not chain text_coverage_preflight.py")
    args = parser.parse_args(argv if argv is not None else [])

    if args.sources:
        selected = tuple(s.strip() for s in args.sources.split(",") if s.strip())
        bad = [s for s in selected if s not in SOURCES]
        if bad:
            log.error("unknown sources: %s (valid: %s)", bad, SOURCES)
            return 2
    else:
        selected = SOURCES
    partial_run = set(selected) != set(SOURCES)

    f = TushareFetcher()
    run_ts = pd.Timestamp.now(tz=CN_TZ)
    end = run_ts.date()
    start = end - timedelta(days=LOOKBACK_DAYS - 1)
    log.info("daily pull window %s..%s (CN wall time)%s", start, end,
             f" | partial sources={selected}" if partial_run else "")

    counts: dict[str, int] = {s: 0 for s in selected}
    attempts: list[dict] = []
    breaker_events: list[dict] = []
    #: (source, ymd) -> failure kind ("error" | "truncated" | "skipped_breaker")
    failed: dict[tuple[str, str], str] = {}
    consecutive_errors: dict[str, int] = {s: 0 for s in selected}
    breaker_open: set[str] = set()

    d = start
    while d <= end:
        ymd = d.strftime("%Y%m%d")
        for source in selected:
            if source in breaker_open:
                failed[(source, ymd)] = "skipped_breaker"
                attempts.append({"source": source, "day": ymd, "pass": 1,
                                 "outcome": "skipped_breaker"})
                continue
            outcome = _attempt(f, source, ymd, 1, counts, attempts)
            if outcome == "error":
                failed[(source, ymd)] = "error"
                consecutive_errors[source] += 1
                if consecutive_errors[source] >= BREAKER_THRESHOLD:
                    breaker_open.add(source)
                    breaker_events.append(
                        {"source": source, "opened_after": ymd,
                         "consecutive_errors": consecutive_errors[source]})
                    log.warning("breaker OPEN for %s after %d consecutive "
                                "failures — skipping its remaining days this "
                                "pass (retry pass will re-attempt)",
                                source, consecutive_errors[source])
            else:
                consecutive_errors[source] = 0
                if outcome == "truncated":
                    failed[(source, ymd)] = "truncated"
        d += timedelta(days=1)
        time.sleep(0.3)

    # B1 retry pass: one sequential re-attempt per transient failure after a
    # cooldown. Truncation is a page-cap condition, not transport — no retry.
    retryable = [(s, ymd) for (s, ymd), kind in failed.items()
                 if kind in ("error", "skipped_breaker")]
    recovered: list[str] = []
    retry_performed = False
    if retryable and not args.no_retry_pass:
        retry_performed = True
        log.info("retry pass: %d (source,day) pairs after %.0fs cooldown",
                 len(retryable), args.retry_cooldown)
        time.sleep(args.retry_cooldown)
        for source, ymd in retryable:
            outcome = _attempt(f, source, ymd, 2, counts, attempts)
            if outcome in ("ok_rows", "ok_zero"):
                del failed[(source, ymd)]
                recovered.append(f"{source}@{ymd}")
            elif outcome == "truncated":
                failed[(source, ymd)] = "truncated"
            time.sleep(0.3)

    failures = [f"{s}@{ymd}: "
                + {"error": "fetch failed (see attempts audit)",
                   "truncated": "truncated (max_pages hit, day incomplete)",
                   "skipped_breaker": "skipped (breaker_open after repeated "
                                      "failures; retry pass did not recover)",
                   }[kind]
                for (s, ymd), kind in sorted(failed.items())]
    failed_sources = {s for (s, _ymd) in failed}

    # B5 + R2 Blocker-6: per-run manifest with PER-SOURCE status — the forward
    # runner's completeness evidence (counts alone cannot distinguish
    # zero-rows-ok from never-attempted/failed). Un-attempted sources of a
    # partial run are "not_attempted": never ok_*, so no coverage credit.
    source_status = {
        s: ("not_attempted" if s not in selected
            else "failed" if s in failed_sources
            else "ok_nonzero_rows" if counts.get(s, 0) > 0
            else "ok_zero_rows")
        for s in SOURCES
    }
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {
        "run_ts": run_ts.isoformat(),         # ISO-8601 with +08:00 offset
        "timezone": CN_TZ,
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "lookback_days": LOOKBACK_DAYS,
        "counts": counts,
        "source_status": source_status,
        "failures": failures,
        "ok": not failures,
        # B1 additive audit (gate-neutral):
        "partial_run": partial_run,
        "sources_pulled": list(selected),
        "attempts": attempts,
        "breaker_events": breaker_events,
        "retry_pass": {"performed": retry_performed,
                       "cooldown_s": args.retry_cooldown,
                       "attempted": len(retryable) if retry_performed else 0,
                       "recovered": recovered},
    }
    mpath = MANIFEST_DIR / f"pull_manifest_{run_ts.strftime('%Y%m%d_%H%M%S')}.json"
    mpath.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    if not partial_run:
        # the runner's latest-manifest gate must only ever see FULL runs
        (MANIFEST_DIR / "pull_manifest_latest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    log.info("done: %s%s%s | manifest -> %s", counts,
             f" | recovered on retry: {recovered}" if recovered else "",
             f" | FAILURES: {failures}" if failures else "", mpath)

    # B2 chaining: coverage preflight is a separate read-only alerting step
    # with its OWN flag file and exit code — it never alters this job's rc.
    if chain_preflight and not partial_run and not args.skip_preflight:
        try:
            r = subprocess.run([sys.executable, str(PREFLIGHT_SCRIPT)],
                               timeout=300, check=False)
            log.info("coverage preflight exited %d (its alert flag is "
                     "authoritative; pull rc unaffected)", r.returncode)
        except Exception as e:  # noqa: BLE001
            log.error("coverage preflight could not run: %s", e)

    return 1 if failures else 0            # B5: ANY failure = non-zero exit


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:], chain_preflight=True))
