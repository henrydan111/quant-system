# SCRIPT_STATUS: ACTIVE — calendar-unfreeze Phase 5-B: monthly provider freeze-bump driver
"""Monthly calendar freeze-bump: package the manual thaw Phase 1-4 into a repeatable,
--dry-run-able driver with a HARD human sign-off gate before publish.

UNFREEZE_PLAN.md Phase 5-B (GPT §10 SHIP). Three modes:

  --plan            Preflight + determine target_end + print the plan. No execution.
  (default execute) Catch up raw -> new policy YAML -> full rebuild (staged) -> frozen-prefix
                    audit + FRESH-WINDOW SURVIVORSHIP audit -> dry-run report. STOPS before
                    publish (prints the --publish-approved instruction).
  --publish-approved  The publish leg (only after a human reviewed the dry-run report):
                    safe atomic swap -> approvals rebind -> post-publish QA -> parent-build
                    metadata. §13 risk action — NEVER in the automated flow.

Design invariants honored:
  - spent_oos_end STAYS 2026-02-27 across every bump (D3 §6); only calendar_end advances,
    so the born-sealed fresh window grows monotonically.
  - target_end = last COMPLETE trading day passing an endpoint-readiness contract (M1),
    never wall-clock (a partial day must never enter a formal provider).
  - the frozen-prefix audit (bin byte-identity + calendar append-only + sidecar membership)
    AND a fresh-window universe/survivorship audit (M2, no blanket exceptions) both gate.
  - approved exceptions are typed, per-bump, trend-reported (M3); the same type recurring two
    bumps in a row must be a permanent migration, not a silent re-approval.
  - the policy id is passed explicitly (no module default; publish is fail-closed on blank).

The heavy steps (rebuild, publish) delegate to the proven pit_backend / safe-publish paths;
this driver is the ORCHESTRATION + the two new audits + the gates.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

SPENT_OOS_END = "2026-02-27"        # D3 §6: FROZEN across every bump
FRESH_HOLDOUT_START = "2026-02-28"  # must equal REPORT_RC_FRESH_HOLDOUT_START
POLICY_DIR = PROJECT_ROOT / "config" / "calendar_policies"
OUT_DIR = PROJECT_ROOT / "workspace" / "outputs" / "calendar_unfreeze"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger("monthly_bump")


# ── M1: endpoint-readiness target_end ────────────────────────────────────────
# Each required endpoint family has a post-close vendor-update time (CST hour). target_end
# is the latest open trading day for which (a) the day is closed past every family's update
# hour, and (b) the daily endpoint is non-empty with a plausible name count. Clock+calendar
# alone MAY schedule raw ingest but MUST NOT authorize a formal target_end.
ENDPOINT_UPDATE_HOUR_CST = {"daily": 16, "cyq_perf": 19, "report_rc": 22, "moneyflow": 19}
MIN_PLAUSIBLE_DAILY_ROWS = 4000  # A-share市场级 daily should carry ~5k names; a partial pull is far below


def _open_trading_days(upto: str | None = None) -> list[str]:
    f = PROJECT_ROOT / "data" / "reference" / "trade_cal.parquet"
    if not f.exists():
        return []
    cal = pd.read_parquet(f)
    days = cal[cal["is_open"] == 1]["cal_date"].astype(str).sort_values().tolist()
    return [d for d in days if (upto is None or d <= upto)]


def now_cst() -> datetime:
    """Wall-clock in China time — the vendor-update hours are CST, so the readiness check
    must not use the host's local time (GPT B2)."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Shanghai"))
    except Exception:  # pragma: no cover — zoneinfo always present on 3.9+
        return datetime.now()


def determine_target_end(now: datetime, *, probe_ready=None) -> tuple[str | None, dict]:
    """Return (target_end, evidence). The latest open trading day whose data is complete:
    the day is past the LATEST required endpoint update hour AND, when probe_ready is given,
    every required endpoint family passes its readiness/coverage probe. Rolls back to the
    previous open day otherwise. probe_ready(date) -> (ok: bool, evidence: dict) is injectable
    for tests; None skips the probe (schedule/plan use). A formal execute REQUIRES probe_ready
    — daily row count alone cannot authorize a formal target_end (GPT B2)."""
    today = now.strftime("%Y%m%d")
    latest_hour = max(ENDPOINT_UPDATE_HOUR_CST.values())
    candidates = _open_trading_days(upto=today)
    evidence: dict = {"evaluated": [], "latest_required_hour_cst": latest_hour}
    for d in reversed(candidates):
        rec: dict = {"date": d}
        # a day is complete only once we are past its vendor-update window; for `today`
        # that means now (CST) must be past latest_hour, for past days it is trivially so.
        if d == today and now.hour < latest_hour:
            rec["reason"] = f"today not past update hour {latest_hour}:00 CST"
            evidence["evaluated"].append(rec)
            continue
        if probe_ready is not None:
            ok, ep_ev = probe_ready(d)
            rec.update(ep_ev)
            if not ok:
                evidence["evaluated"].append(rec)
                continue
        rec["ok"] = True
        evidence["evaluated"].append(rec)
        return d, evidence
    return None, evidence


# ── policy YAML generation (D1 append-only; spent_oos_end frozen) ─────────────
def next_thaw_step_number() -> int:
    existing = list(POLICY_DIR.glob("frozen_*_thaw_step*.yaml"))
    steps = []
    for p in existing:
        try:
            steps.append(int(p.stem.rsplit("thaw_step", 1)[1]))
        except (IndexError, ValueError):
            continue
    return (max(steps) + 1) if steps else 1


def generate_thaw_policy(target_end: str, parent_build_id: str, *, write: bool) -> tuple[str, Path]:
    """Create a NEW append-only frozen policy at target_end. spent_oos_end/fresh_holdout_start
    stay FROZEN (D3 §6). Returns (policy_id, path). Never edits an existing policy file."""
    end_iso = f"{target_end[:4]}-{target_end[4:6]}-{target_end[6:]}"
    step = next_thaw_step_number()
    policy_id = f"frozen_{target_end}_thaw_step{step}"
    path = POLICY_DIR / f"{policy_id}.yaml"
    if path.exists():
        raise SystemExit(f"policy {policy_id} already exists — refusing to overwrite (append-only)")
    body = {
        "policy_id": policy_id, "policy_schema_version": 1,
        "calendar_start_date": "2008-01-02", "calendar_end_date": end_iso, "data_end_date": end_iso,
        "frozen": True, "reason": f"thaw_step{step}_monthly_freeze_bump",
        "established_at": end_iso,
        "spent_oos_end": SPENT_OOS_END, "fresh_holdout_start": FRESH_HOLDOUT_START,
        "allowed_modes": ["sandbox", "joinquant_replication", "formal_research_with_explicit_freeze",
                          "joinquant_daily", "joinquant_open_close_replica", "formal", "oos_test"],
        "default_formal_behavior": "require_explicit_policy",
        "notes": [f"Monthly freeze-bump thaw step {step}; parent provider build = {parent_build_id}.",
                  f"spent_oos_end frozen at {SPENT_OOS_END}; the born-sealed fresh window "
                  f"[{FRESH_HOLDOUT_START}, {end_iso}] grows with the calendar (D3)."],
    }
    if write:
        path.write_text(yaml.safe_dump(body, allow_unicode=True, sort_keys=False), encoding="utf-8")
        logger.info("wrote new policy %s", path)
    return policy_id, path


# ── M2: fresh-window survivorship / universe-completeness audit ───────────────
def _membership_from_all_stocks(instruments_dir: Path, cal: pd.DatetimeIndex) -> pd.DataFrame:
    """Daily membership matrix from all_stocks.txt (code, list, delist ranges)."""
    import numpy as np

    rows = []
    for line in (instruments_dir / "all_stocks.txt").read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 3:
            rows.append((parts[0].upper(), parts[1], parts[2]))
    if not rows:
        return pd.DataFrame(index=cal)
    codes = sorted({r[0] for r in rows})
    cidx = {c: i for i, c in enumerate(codes)}
    lo = cal.searchsorted(pd.to_datetime([r[1] for r in rows]), side="left")
    hi = cal.searchsorted(pd.to_datetime([r[2] for r in rows]), side="right")
    mat = np.zeros((len(cal), len(codes)), dtype=bool)
    for (c, _, _), a, b in zip(rows, lo, hi):
        mat[a:b, cidx[c]] = True
    return pd.DataFrame(mat, index=cal, columns=codes)


# core price/volume bins every tradable code must carry (the engine-required kline set); a
# features/<code>/ dir missing any of these is feature-incomplete, not merely present.
REQUIRED_PRICE_BINS = ("open.day.bin", "high.day.bin", "low.day.bin", "close.day.bin",
                       "vol.day.bin", "amount.day.bin", "adj_factor.day.bin")


def _feature_code_paths(features_dir: Path) -> dict[str, Path]:
    """UPPER-code -> feature dir, for codes whose dir carries EVERY core price bin (a bare/partial
    dir does not count). Returns the actual (lowercase on disk) path so bins can be decoded."""
    out: dict[str, Path] = {}
    for p in features_dir.iterdir():
        if p.is_dir() and all((p / b).exists() for b in REQUIRED_PRICE_BINS):
            out[p.name.upper()] = p
    return out


def _bin_span(bin_path: Path) -> tuple[int, int]:
    """(start_pos, last_pos) a Qlib .day.bin covers. Format: float32[0] = start_index (calendar
    position of the first value), float32[1:] = values -> last_pos = start_index + nvalues - 1. A
    per-code bin spans [listing, last-data], NOT the whole calendar — decoding the header is the
    only correct coverage test (a size-vs-full-calendar check false-flags every post-2008 listing).
    Returns (-1, -1) if unreadable/empty/misaligned."""
    import struct
    try:
        size = bin_path.stat().st_size
    except OSError:
        return -1, -1
    nvalues = size // 4 - 1  # minus the 1-float header
    if nvalues <= 0 or size % 4 != 0:  # a non-4-multiple is a corrupt/truncated bin
        return -1, -1
    with open(bin_path, "rb") as fh:
        start_pos = int(struct.unpack("<f", fh.read(4))[0])
    return start_pos, start_pos + nvalues - 1


def fresh_window_survivorship_audit(provider_dir: Path, fresh_start: str, target_end: str) -> dict:
    """M2: for [fresh_start, target_end], EVERY ts_code with a raw daily price row must be in
    the provider all_stocks universe on that day (raw-price-vs-sidecar contradiction = FAIL,
    a universe-contract inconsistency; NO blanket exceptions). This protects the future
    holdout window from survivorship bias (a missing delisted/suspended name biases it)."""
    import numpy as np

    daily_root = PROJECT_ROOT / "data" / "market" / "daily"
    cal = pd.read_parquet(PROJECT_ROOT / "data" / "reference" / "trade_cal.parquet")
    fresh_days = cal[(cal["is_open"] == 1) & (cal["cal_date"] >= fresh_start.replace("-", ""))
                     & (cal["cal_date"] <= target_end.replace("-", ""))]["cal_date"].astype(str).tolist()
    cal_idx = pd.to_datetime(fresh_days)
    members = _membership_from_all_stocks(provider_dir / "instruments", cal_idx)
    # B4/M1: provider feature-COMPLETENESS — membership alone is not completeness, a bare
    # features/<code>/ dir is not either, and neither is a dir whose bins are TRUNCATED before the
    # day the code is raw-priced. (i) present = dir carries every core price bin; (ii) each
    # raw-priced code's close.day.bin must COVER that trading day (decode the Qlib header).
    features_dir = provider_dir / "features"
    feature_paths = _feature_code_paths(features_dir) if features_dir.is_dir() else {}
    feature_codes = set(feature_paths)
    # provider calendar position by YYYYMMDD (day.txt is ISO) — for the bin-coverage check.
    prov_cal = (provider_dir / "calendars" / "day.txt").read_text(encoding="utf-8").split()
    prov_pos = {d.replace("-", ""): i for i, d in enumerate(prov_cal)}
    _span: dict[tuple, tuple] = {}

    def span_of(code: str, binname: str) -> tuple[int, int]:
        key = (code, binname)
        if key not in _span:
            p = feature_paths.get(code)
            _span[key] = _bin_span(p / binname) if p else (-1, -1)
        return _span[key]

    violations: list[dict] = []
    checked_days = 0
    for d in fresh_days:
        f = daily_root / d[:4] / f"daily_{d}.parquet"
        if not f.exists():
            violations.append({"date": d, "type": "missing_raw_daily"})
            continue
        checked_days += 1
        raw = pd.read_parquet(f, columns=["ts_code"])
        # provider code form 000001_SZ (underscore); raw is 000001.SZ / 830001.BJ etc.
        raw_codes = {c.replace(".", "_").upper() for c in raw["ts_code"].dropna().astype(str)}
        day_ts = pd.Timestamp(d)
        if day_ts not in members.index:
            continue
        present = set(members.columns[members.loc[day_ts].values])
        # (a) raw-priced code missing from all_stocks membership on that day
        not_in_universe = sorted(raw_codes - present)
        if not_in_universe:
            violations.append({"date": d, "type": "raw_price_not_in_universe",
                               "n": len(not_in_universe), "examples": not_in_universe[:10]})
        # (b) raw-priced code missing from the provider feature tree (or missing a core bin)
        not_in_features = sorted(raw_codes - feature_codes)
        if not_in_features:
            violations.append({"date": d, "type": "raw_price_not_in_feature_tree",
                               "n": len(not_in_features), "examples": not_in_features[:10]})
        # (c) a fresh raw-priced day MUST be in the staged provider calendar — else the provider
        # cannot support the claimed target_end (fail closed, GPT M1).
        pos_d = prov_pos.get(d)
        if pos_d is None:
            violations.append({"date": d, "type": "raw_price_day_not_in_provider_calendar",
                               "n": len(raw_codes), "examples": sorted(raw_codes)[:10]})
            continue
        # (d) raw-priced code whose ANY core bin does NOT span this trading day (truncated bin) —
        # every required bin must contain pos_d, not just close (vol/amount/adj_factor matter too).
        too_short = sorted(c for c in (raw_codes & feature_codes)
                           if any(not (span_of(c, b)[0] <= pos_d <= span_of(c, b)[1])
                                  for b in REQUIRED_PRICE_BINS))
        if too_short:
            violations.append({"date": d, "type": "raw_price_bins_short_through_day",
                               "n": len(too_short), "examples": too_short[:10]})
    return {"fresh_days": len(fresh_days), "checked_days": checked_days,
            "feature_tree_codes": len(feature_codes),
            "ok": not violations, "violations": violations[:50]}


# ── M3: typed approved-exceptions registry ───────────────────────────────────
class ExceptionRegistry:
    """Typed, append-only, per-bump approved exceptions for the frozen-prefix audit. The
    fresh-window survivorship audit has NO exceptions. A type recurring for two consecutive
    bumps must become a permanent migration (not re-approved by count)."""

    def __init__(self, path: Path):
        self.path = path
        self.rows = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []

    def add(self, *, exc_type: str, root_cause: str, dataset: str, symbols, date_range: str,
            gross: int, net_after: int, reviewer: str, expiry: str, evidence: str, diff_hash: str):
        if symbols in ("*", "all") or date_range in ("*", "all"):
            raise ValueError("wildcard symbols/date_range are forbidden in an approved exception")
        self.rows.append({
            "exc_type": exc_type, "root_cause": root_cause, "dataset": dataset,
            "symbols": symbols, "date_range": date_range, "gross_diff": gross,
            "net_diff_after_exception": net_after, "reviewer": reviewer,
            "expiry_condition": expiry, "evidence": evidence, "diff_hash": diff_hash,
        })

    def recurring_types(self) -> list[str]:
        from collections import Counter
        c = Counter(r["exc_type"] for r in self.rows)
        return [t for t, n in c.items() if n >= 2]

    def commit(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.rows, ensure_ascii=False, indent=1), encoding="utf-8")


def live_provider_ids() -> tuple[str, str]:
    m = json.loads((PROJECT_ROOT / "data" / "qlib_data" / "metadata" / "provider_build.json").read_text(encoding="utf-8"))
    return m["provider_build_id"], m["calendar_policy_id"]


def _disk_free_gb() -> int:
    return shutil.disk_usage(str(PROJECT_ROOT))[2] // 2**30


def _prune_cyq_state(suffix: str) -> None:
    """On a post-catch-up completeness failure, drop the Stage-D cyq_perf resume keys from the
    catch-up state file so a rerun RE-FETCHES cyq (m1): a zero-row cyq fetch from a late endpoint
    is marked 'done' and would otherwise be SKIPPED on rerun, leaving the bump unrecoverable
    without manual state deletion. The state file is scoped by --state-suffix=target_end."""
    sp = OUT_DIR / f"catchup_fund_state_{suffix}.json"
    if not sp.exists():
        return
    try:
        st = json.loads(sp.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    pruned = {k: v for k, v in st.items() if not (k.startswith("D:cyq") or k == "D:cyq_repartition")}
    if len(pruned) != len(st):
        sp.write_text(json.dumps(pruned, ensure_ascii=False, indent=1), encoding="utf-8")
        logger.warning("pruned %d Stage-D cyq resume keys from %s so a rerun refetches cyq_perf",
                       len(st) - len(pruned), sp.name)


# Endpoint-readiness contract (M1/B2). Existence != completeness — an empty/partial per-day file
# must not authorize a formal calendar_end. Two tiers, because coverage-lag differs:
#   - DAILY-FRESH (daily OHLCV, moneyflow, stk_limit): refreshed same-day, so they exist for a
#     candidate target_end BEFORE the monthly catch-up -> they GATE target_end on ROW COUNT.
#   - LAGGING (cyq_perf, per-symbol Stage-D fetch): brought current by the monthly catch-up
#     ITSELF, so a pre-catch-up existence check is meaningless -> verified POST-catch-up
#     (assert_endpoints_complete). Confirmed live: cyq_perf lagged 07-01 while daily/moneyflow/
#     stk_limit were current to 07-03.
#   - report_rc: a window-anchored year-file; completeness = the Stage-E halo fetch failing closed
#     on an all-zero replay (not a per-day file).
#   - northbound (hk_hold): inherently partial + declining coverage -> NOT a hard gate.
READINESS_DAILY_FRESH = {"moneyflow": "market/moneyflow", "stk_limit": "market/stk_limit"}
READINESS_POSTCATCHUP = {"cyq_perf": "market/cyq_perf"}
MIN_ENDPOINT_ROWS = 3000  # cheap empty/corruption guard ONLY — completeness is the coverage ratio
# Per-endpoint completeness = |endpoint ∩ COMPLETE daily universe| / |daily| >= floor. Floors from a
# measured COMPLETE day (2026-06-30): moneyflow 0.94 (low-liquidity names lack flow) / stk_limit
# 1.00 / cyq_perf 1.00. But the denominator MUST be a *proven-complete* daily — otherwise a partial
# daily lets every endpoint cover that same partial universe at 100% (GPT B1).
ENDPOINT_COVERAGE_FLOOR = {"moneyflow": 0.90, "stk_limit": 0.95, "cyq_perf": 0.95}
# Daily universe count is stable day-to-day (~5510, <0.3% variation), so a PARTIAL daily above the
# absolute floor is caught by comparing to the median of recent complete sessions.
DAILY_BASELINE_FLOOR = 0.98
DAILY_BASELINE_WINDOW = 10


def _endpoint_rows(sub: str, ep: str, date: str) -> int:
    """O(1) parquet row count (footer metadata) for a per-day endpoint file; 0 if absent."""
    import pyarrow.parquet as pq
    f = PROJECT_ROOT / "data" / sub / date[:4] / f"{ep}_{date}.parquet"
    if not f.exists():
        return 0
    try:
        return pq.ParquetFile(f).metadata.num_rows
    except Exception:  # noqa: BLE001 — a corrupt/half-written file reads as 0 rows (not complete)
        return 0


def _read_codes_for_trade_date(sub: str, ep: str, date: str) -> tuple[set[str], dict]:
    """ts_codes whose row's trade_date == date, plus diagnostics. date_ok proves the file is NOT a
    stale/mispartitioned file carrying a different trade_date (GPT B1 second form)."""
    f = PROJECT_ROOT / "data" / sub / date[:4] / f"{ep}_{date}.parquet"
    if not f.exists():
        return set(), {"rows": 0, "date_ok": False, "trade_dates": [], "reason": "missing"}
    try:
        df = pd.read_parquet(f, columns=["ts_code", "trade_date"])
    except Exception:  # noqa: BLE001 — unreadable or no trade_date column = not provably complete
        return set(), {"rows": 0, "date_ok": False, "trade_dates": [], "reason": "unreadable/no trade_date"}
    td = df["trade_date"].astype(str).str.replace("-", "", regex=False)
    trade_dates = set(td.unique())
    codes = {str(x).upper().strip() for x in df.loc[td == date, "ts_code"].dropna()}
    return codes, {"rows": int(len(df)), "date_ok": trade_dates == {date},
                   "trade_dates": sorted(trade_dates)[:5]}


def _daily_row_count(date: str) -> int:
    return _endpoint_rows("market/daily", "daily", date)


def _daily_universe(date: str) -> tuple[set[str], bool, dict]:
    """The COMPLETE daily universe for `date` — the denominator every endpoint coverage is measured
    against. daily is a completeness OBJECT, not just a count: (1) file trade_date == date; (2) code
    count >= the absolute floor; (3) code count >= DAILY_BASELINE_FLOOR x the median of the last
    DAILY_BASELINE_WINDOW complete sessions (catches a partial daily still above the absolute floor
    — the GPT B1 residual). Returns (codes, ok, evidence)."""
    codes, diag = _read_codes_for_trade_date("market/daily", "daily", date)
    ev: dict = {"daily_codes": len(codes), "daily_rows": diag["rows"], "daily_date_ok": diag["date_ok"]}
    if not diag["date_ok"]:
        ev["reason"] = f"daily file trade_date mismatch: {diag.get('trade_dates')}"
        return codes, False, ev
    if len(codes) < MIN_PLAUSIBLE_DAILY_ROWS:
        ev["reason"] = f"daily codes {len(codes)} < {MIN_PLAUSIBLE_DAILY_ROWS}"
        return codes, False, ev
    # baseline uses the SAME trade_date-filtered code count as the target (not the raw footer row
    # count) so the ratio is apples-to-apples; only date-correct prior sessions above the floor count.
    prior = [d for d in _open_trading_days(upto=date) if d < date][-DAILY_BASELINE_WINDOW:]
    base = []
    for d in prior:
        pc, pdiag = _read_codes_for_trade_date("market/daily", "daily", d)
        if pdiag["date_ok"] and len(pc) >= MIN_PLAUSIBLE_DAILY_ROWS:
            base.append(len(pc))
    if base:
        import statistics
        baseline = statistics.median(base)
        ratio = len(codes) / max(1, baseline)
        ev["daily_baseline_median"] = baseline
        ev["daily_baseline_ratio"] = round(ratio, 4)
        if ratio < DAILY_BASELINE_FLOOR:
            ev["reason"] = (f"daily universe PARTIAL: {len(codes)} vs baseline {baseline} "
                            f"(ratio {ratio:.4f} < {DAILY_BASELINE_FLOOR})")
            return codes, False, ev
    return codes, True, ev


def _daily_set_continuity(date: str, daily_codes: set[str]) -> tuple[bool, dict]:
    """SET-LEVEL daily completeness proof (GPT B1): a name that TRADED on the previous session (so
    it was listed and NOT suspended then) must trade today UNLESS it delisted or newly suspended.
    Because prior-session names were trading, the only PIT reasons for a same-name to vanish today
    are delist (stock_basic.delist_date <= date) or a NEW suspension (suspend_d S event ON date) —
    no historical suspension-state reconstruction is needed. Any name that vanishes without such a
    reason is a survivorship hole the count baseline cannot see. Fail-CLOSED. Codes are compared in
    the dotted-upper form _read_codes_for_trade_date returns (000001.SZ), so stock_basic/suspend_d
    (already dotted) are just upper-cased — NO dot->underscore here."""
    ev: dict = {}
    prior_days = [d for d in _open_trading_days(upto=date) if d < date]
    if not prior_days:
        ev["status"] = "skipped_no_prior_session"
        return True, ev
    prev = prior_days[-1]
    prior_codes, pdiag = _read_codes_for_trade_date("market/daily", "daily", prev)
    if not pdiag["date_ok"] or len(prior_codes) < MIN_PLAUSIBLE_DAILY_ROWS:
        ev["status"] = f"skipped_prior_unverified:{prev}"
        return True, ev  # can't establish a reference; the baseline still guards gross partials

    def norm(s) -> set[str]:
        return {str(x).upper().strip() for x in s.dropna()}

    sb = pd.read_parquet(PROJECT_ROOT / "data" / "reference" / "stock_basic.parquet",
                         columns=["ts_code", "list_date", "delist_date"])
    delisted = norm(sb.loc[sb["delist_date"].notna() & (sb["delist_date"].astype(str) <= date), "ts_code"])
    ipo_today = norm(sb.loc[sb["list_date"].astype(str) == date, "ts_code"])

    susp_f = PROJECT_ROOT / "data" / "market" / "suspend_d" / date[:4] / f"suspend_d_{date}.parquet"
    if not susp_f.exists():
        ev["status"] = "suspend_d_missing"
        ev["reason"] = f"suspend_d for {date} absent — cannot prove daily completeness (fail-closed)"
        return False, ev
    sd = pd.read_parquet(susp_f, columns=["ts_code", "suspend_type"])
    stype = sd["suspend_type"].astype(str).str.upper()
    suspended = norm(sd.loc[stype == "S", "ts_code"])
    resumed = norm(sd.loc[stype == "R", "ts_code"])

    # names that traded yesterday must trade today unless delisted/newly-suspended; plus today's IPOs
    expected = (prior_codes - delisted - suspended) | (ipo_today - suspended)
    missing = sorted(expected - daily_codes)
    unexpected = sorted(daily_codes - prior_codes - ipo_today - resumed)
    ev.update({"prev": prev, "prior_codes": len(prior_codes), "expected": len(expected),
               "delisted_by_date": len(delisted), "suspended_today": len(suspended),
               "ipo_today": len(ipo_today), "missing": len(missing), "unexpected": len(unexpected)})
    if missing:
        ev["reason"] = (f"daily universe incomplete vs {prev}: {len(missing)} expected names absent "
                        f"without a delist/suspend reason; examples={missing[:10]}")
        return False, ev
    if unexpected:
        logger.warning("daily %s: %d names appeared vs %s w/o IPO/resume evidence: %s",
                       date, len(unexpected), prev, unexpected[:10])
    return True, ev


def _coverage_gate(date: str, endpoints: dict, ev: dict, daily_codes: set[str]) -> bool:
    """True iff every endpoint file is date-correct AND covers the PROVEN-complete daily universe
    above its floor. Mutates ev with per-endpoint diagnostics + a reason on failure."""
    cov = ev.setdefault("endpoint_coverage", {})
    for ep, sub in endpoints.items():
        codes, diag = _read_codes_for_trade_date(sub, ep, date)
        ratio = len(codes & daily_codes) / max(1, len(daily_codes))
        cov[ep] = {"rows": diag["rows"], "codes": len(codes), "coverage": round(ratio, 4),
                   "date_ok": diag["date_ok"], "missing_examples": sorted(daily_codes - codes)[:8]}
        floor = ENDPOINT_COVERAGE_FLOOR.get(ep, 0.95)
        if not diag["date_ok"] or ratio < floor or diag["rows"] < MIN_ENDPOINT_ROWS:
            ev["reason"] = (f"{ep} incomplete: coverage {cov[ep]['coverage']} < {floor} "
                            f"(rows {diag['rows']}, date_ok {diag['date_ok']})")
            return False
    return True


def endpoint_ready(date: str) -> tuple[bool, dict]:
    """PRE-catch-up target_end gate: the daily universe is PROVEN complete (date-correct + not a
    partial vs the recent baseline) AND every DAILY-FRESH endpoint (moneyflow, stk_limit) covers it
    above floor. Lagging endpoints (cyq_perf) + the report_rc halo are verified POST-catch-up."""
    daily_codes, daily_ok, ev = _daily_universe(date)
    if not daily_ok:
        return False, ev
    return _coverage_gate(date, READINESS_DAILY_FRESH, ev, daily_codes), ev


def assert_endpoints_complete(date: str) -> tuple[bool, dict]:
    """POST-catch-up completeness gate on the FINAL target_end data: re-prove the daily universe +
    daily-fresh endpoints AND the lagging cyq_perf the catch-up just fetched, by COVERAGE vs the
    PROVEN-complete daily. Fail-closed — a formal provider must never stamp calendar_end at a
    partial day."""
    daily_codes, daily_ok, ev = _daily_universe(date)
    if not daily_ok:
        return False, ev
    if not _coverage_gate(date, READINESS_DAILY_FRESH, ev, daily_codes):
        return False, ev
    # SET-LEVEL daily completeness proof (GPT B1) — post-catch-up, where prev daily + stock_basic +
    # suspend_d(date) are all present. The rolling baseline (in _daily_universe) is only a cheap
    # early detector; THIS is the formal completeness gate before a policy is minted.
    cont_ok, cont_ev = _daily_set_continuity(date, daily_codes)
    ev["daily_continuity"] = cont_ev
    if not cont_ok:
        ev["reason"] = cont_ev.get("reason")
        return False, ev
    return _coverage_gate(date, READINESS_POSTCATCHUP, ev, daily_codes), ev


# ── phases ───────────────────────────────────────────────────────────────────
def phase_plan(args) -> dict:
    parent_build, parent_policy = live_provider_ids()
    target_end, evidence = determine_target_end(now_cst(), probe_ready=None)
    plan = {
        "mode": "plan", "generated": datetime.now().isoformat(timespec="seconds"),
        "parent_build_id": parent_build, "parent_policy_id": parent_policy,
        "target_end": target_end, "target_end_evidence": evidence,
        "spent_oos_end": SPENT_OOS_END, "fresh_holdout_start": FRESH_HOLDOUT_START,
        "next_policy_id": f"frozen_{target_end}_thaw_step{next_thaw_step_number()}" if target_end else None,
        "disk_free_gb": _disk_free_gb(),
        "catchup_range": f"{parent_policy} end +1 .. {target_end}",
        "notes": ["spent_oos_end frozen (D3); fresh window grows.",
                  "execute (default) runs catch-up->rebuild->audits->dry-run report, STOPS before publish.",
                  "publish is a §13 human-gated action: --publish-approved after reviewing the report."],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "monthly_bump_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(plan, ensure_ascii=False, indent=1))
    return plan


DRYRUN_REPORT_PATH = OUT_DIR / "monthly_bump_dryrun_report.json"
FRESH_AUDIT_PATH = OUT_DIR / "fresh_window_survivorship_audit.json"
PUBLISH_HANDOFF_PATH = OUT_DIR / "publish_handoff.json"


def _report_rc_halo_start(target_end: str) -> str:
    """report_rc replay must cover a pre-boundary halo (Phase 5-A contract): a forecast
    dated up to REPORT_RC_ACTIVE_TTL_OPEN_DAYS before the boundary can carry INTO the fresh
    window, and a create_time gap up to REPORT_RC_BACKFILL_GAP_DAYS matters. Replay from
    fresh_holdout_start - (TTL open days + backfill guard) through target_end."""
    from data_infra.pit_backend import REPORT_RC_ACTIVE_TTL_OPEN_DAYS, REPORT_RC_BACKFILL_GAP_DAYS
    opens = _open_trading_days(upto=target_end)
    fresh = FRESH_HOLDOUT_START.replace("-", "")
    pos = next((i for i, d in enumerate(opens) if d >= fresh), len(opens))
    halo_pos = max(0, pos - REPORT_RC_ACTIVE_TTL_OPEN_DAYS)
    start = opens[halo_pos] if opens else fresh
    # subtract the backfill guard in CALENDAR days as a conservative extra margin
    return (pd.Timestamp(start) - pd.Timedelta(days=REPORT_RC_BACKFILL_GAP_DAYS)).strftime("%Y%m%d")


def phase_execute(args) -> int:
    """Catch up raw -> new policy YAML -> full rebuild (staged) -> frozen-prefix audit +
    fresh-window survivorship audit -> dry-run report. STOPS before publish. Multi-hour."""
    import subprocess

    parent_build, parent_policy = live_provider_ids()

    # M1: the parent policy MUST still be in the Phase-5 frozen regime (spent_oos_end /
    # fresh_holdout_start match the constants) before we mint a child — a Phase-6 release
    # policy must not be silently regressed. Route through the typed loader so the YAML-parsed
    # ISO dates are normalized to strings (a bare yaml.safe_load yields datetime.date objects,
    # which would false-fail a string compare) and the loader's own validation runs.
    from research_orchestrator.calendar_policy import load_calendar_policy
    parent_pol = load_calendar_policy(parent_policy)
    if parent_pol.spent_oos_end != SPENT_OOS_END:
        logger.error("parent policy spent_oos_end %s != Phase-5 constant %s — refusing",
                     parent_pol.spent_oos_end, SPENT_OOS_END)
        return 2
    if parent_pol.fresh_holdout_start != FRESH_HOLDOUT_START:
        logger.error("parent policy fresh_holdout_start %s != Phase-5 constant %s — refusing",
                     parent_pol.fresh_holdout_start, FRESH_HOLDOUT_START)
        return 2
    parent_end = parent_pol.calendar_end_date.replace("-", "")

    # B2: target_end via the multi-endpoint readiness contract; validate any override.
    ready_target, ev = determine_target_end(now_cst(), probe_ready=endpoint_ready)
    if args.target_end:
        ok, ov_ev = endpoint_ready(args.target_end)
        if not ok or (ready_target is not None and args.target_end > ready_target):
            logger.error("--target-end %s is not endpoint-complete or later than the complete "
                         "target_end %s; evidence=%s / override=%s", args.target_end, ready_target, ev, ov_ev)
            return 2
        target_end = args.target_end
    else:
        target_end = ready_target
    if target_end is None:
        logger.error("no endpoint-complete trading day found for target_end; evidence=%s", ev)
        return 2
    logger.info("target_end=%s (parent build=%s / policy=%s)", target_end, parent_build, parent_policy)

    if _disk_free_gb() < 400:
        logger.error("disk free %dGB < 400GB floor — prune referenced-safe backups first", _disk_free_gb())
        return 2

    # 1. catch up raw (the two proven drivers; strictly serial, single fetcher). B3: the
    # fundamentals catch-up is bump-scoped (--state-suffix) and report_rc replays the
    # pre-boundary halo, not just parent_end+1 (the Phase-5-A availability contract).
    catchup_start = _open_trading_days()
    lo = next((d for d in catchup_start if d > parent_end and d <= target_end), None)
    if lo is not None:
        py = str(PROJECT_ROOT / "venv" / "Scripts" / "python.exe")
        halo = _report_rc_halo_start(target_end)
        logger.info("catch-up raw %s..%s (report_rc halo from %s)", lo, target_end, halo)
        subprocess.run([py, str(PROJECT_ROOT / "workspace" / "scripts" / "catchup_daily_range.py"),
                        "--start", lo, "--end", target_end], check=True)
        subprocess.run([py, str(PROJECT_ROOT / "workspace" / "scripts" / "catchup_fundamentals_range.py"),
                        "--start", lo, "--end", target_end,
                        "--report-rc-start", halo, "--report-rc-end", target_end,
                        "--state-suffix", target_end], check=True)
    else:
        logger.info("raw already current through %s", target_end)

    # 1b. POST-catch-up completeness gate (B1): the catch-up just fetched the lagging endpoints
    # (cyq_perf) through target_end — VERIFY the FINAL target_end data is complete across all
    # required endpoints (row counts, not existence) before minting a policy / building a formal
    # provider. Fail-closed: a partial cyq_perf/moneyflow/stk_limit must never enter a formal
    # calendar_end. report_rc halo completeness is enforced inside the catch-up (Stage E fails
    # closed on an all-zero replay).
    ok_complete, complete_ev = assert_endpoints_complete(target_end)
    if not ok_complete:
        _prune_cyq_state(target_end)  # m1: let a rerun refetch cyq (don't leave zero-row 'done')
        logger.error("target_end %s endpoint completeness FAILED post-catch-up: %s — bump BLOCKED "
                     "(vendor may be late; re-run when complete or pass an earlier --target-end).",
                     target_end, complete_ev)
        return 2
    logger.info("endpoint completeness OK for %s: %s", target_end, complete_ev)

    # 2. new policy YAML (append-only; spent_oos_end frozen).
    policy_id, policy_path = generate_thaw_policy(target_end, parent_build, write=True)

    # 3. full rebuild (staged, NOT published).
    from data_infra.pit_backend import build_qlib_backend
    build_id = f"thaw_{target_end}_{datetime.now().strftime('%H%M%S')}"
    logger.info("full rebuild build_id=%s (staged, no publish)", build_id)
    result = build_qlib_backend(mode="all", stage="full", build_id=build_id, publish=False,
                                calendar_policy_id=policy_id)
    staged_provider = Path(result.provider_dir)

    # 4a. frozen-prefix audit (delegates to the proven audit script against the NEW staged
    # tree via THAW_STAGED_PROVIDER). Its exit code GATES — a frozen-prefix violation blocks
    # the bump (do NOT ignore it: it protects pre-parent-end replay byte-identity). Monthly
    # mode is STRICT (THAW_MONTHLY_MODE): the first-thaw provenance exceptions (indicator
    # refetch SHA drift, sidecar suspension-healing) are one-time and already baked into the
    # SETTLED parent, so a recurring bump must see a byte-identical frozen prefix + identical
    # sidecars — any drift is a real regression, not an exception.
    logger.info("frozen-prefix audit (staged=%s, monthly strict) ...", staged_provider)
    fp_artifact = OUT_DIR / "frozen_prefix_audit.json"
    audit_env = {**os.environ, "THAW_STAGED_PROVIDER": str(staged_provider), "THAW_MONTHLY_MODE": "1"}
    fp = subprocess.run([str(PROJECT_ROOT / "venv" / "Scripts" / "python.exe"),
                         str(PROJECT_ROOT / "workspace" / "scripts" / "audit_thaw_frozen_prefix.py")],
                        env=audit_env)
    if fp.returncode != 0:
        logger.error("FROZEN-PREFIX AUDIT FAILED (exit %d) — bump BLOCKED. Review the audit report "
                     "+ register any legitimate provenance change as a typed exception.", fp.returncode)
        return 1
    # B1 hard guarantee (GPT #1 residual risk): prove the audit actually ran against THIS
    # staged tree, not a stale default — a passing audit against the wrong provider is worse
    # than a failing one. The artifact records the audited `staged` path.
    if not fp_artifact.exists():
        logger.error("frozen-prefix audit produced no artifact at %s — bump BLOCKED.", fp_artifact)
        return 1
    audited = json.loads(fp_artifact.read_text(encoding="utf-8")).get("staged", "")
    if Path(audited).resolve() != staged_provider.resolve():
        logger.error("frozen-prefix audit ran against %s, NOT the staged build %s — bump BLOCKED "
                     "(THAW_STAGED_PROVIDER plumbing failure).", audited, staged_provider)
        return 1
    # 4b. fresh-window survivorship audit (M2, no blanket exceptions).
    logger.info("fresh-window survivorship audit ...")
    fresh = fresh_window_survivorship_audit(staged_provider, FRESH_HOLDOUT_START, target_end)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    FRESH_AUDIT_PATH.write_text(json.dumps(fresh, ensure_ascii=False, indent=1), encoding="utf-8")
    if not fresh["ok"]:
        logger.error("FRESH-WINDOW SURVIVORSHIP AUDIT FAILED (%d violations) — bump BLOCKED. See %s",
                     len(fresh["violations"]), FRESH_AUDIT_PATH)
        return 1

    # 4c. recurring approved-exception GATE (M2): a frozen-prefix exception type recurring
    # two bumps in a row must become a permanent migration (note + tests), not a silent
    # re-approval by count. Block unless the operator explicitly acknowledges the migration.
    recurring = ExceptionRegistry(OUT_DIR / "bump_exceptions.json").recurring_types()
    if recurring and not args.allow_migration_exception:
        logger.error("recurring frozen-prefix exception types require a permanent migration "
                     "(note + tests), not a re-approval by count: %s. Re-run with "
                     "--allow-migration-exception once migrated.", recurring)
        return 1

    # 5. dry-run report -> STOP for human sign-off.
    report = {
        "target_end": target_end, "new_policy_id": policy_id, "staged_build_id": build_id,
        "staged_provider_dir": str(staged_provider),
        "parent_build_id": parent_build, "parent_policy_id": parent_policy,
        "spent_oos_end": SPENT_OOS_END, "fresh_holdout_start": FRESH_HOLDOUT_START,
        "disk_free_gb": _disk_free_gb(),
        "frozen_prefix_audit_ok": True, "frozen_prefix_audit_artifact": "frozen_prefix_audit.json",
        "fresh_window_audit_ok": fresh["ok"], "fresh_window_audit_artifact": str(FRESH_AUDIT_PATH.name),
        "report_rc_replay_halo_start": _report_rc_halo_start(target_end),
        "endpoint_completeness": complete_ev,
        "recurring_exception_types": recurring,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "next": "review this report + both audit artifacts, then --publish-approved --i-reviewed-the-dryrun",
    }
    DRYRUN_REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    logger.info("DRY-RUN COMPLETE. Review %s + both audits, then --publish-approved.", DRYRUN_REPORT_PATH)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


def phase_publish(args) -> int:
    """§13 human-gated publish leg. Requires a reviewed dry-run report. Safe swap -> rebind ->
    QA -> parent-build metadata. This driver refuses to run publish unless the operator passes
    --i-reviewed-the-dryrun AND the report exists (belt: the report is the approval evidence)."""
    if not args.i_reviewed_the_dryrun:
        logger.error("publish requires --i-reviewed-the-dryrun (you must have read %s). Refusing.",
                     DRYRUN_REPORT_PATH)
        return 2
    if not DRYRUN_REPORT_PATH.exists():
        logger.error("no dry-run report at %s — run the execute phase first.", DRYRUN_REPORT_PATH)
        return 2
    # m1: the live swap/rebind/QA are deliberately not auto-wired (they mutate the live
    # provider — §13 — and follow the proven depth9/sharecap precedents). Emit an explicit
    # handoff artifact the proven scripts consume, and return NON-ZERO so a caller/scheduler
    # never mistakes this manual-handoff gate for a completed publish.
    rep = json.loads(DRYRUN_REPORT_PATH.read_text(encoding="utf-8"))
    handoff = {
        "reviewed_dryrun_report": str(DRYRUN_REPORT_PATH),
        "staged_build_id": rep.get("staged_build_id"),
        "staged_provider_dir": rep.get("staged_provider_dir"),
        "new_policy_id": rep.get("new_policy_id"),
        "parent_build_id": rep.get("parent_build_id"),
        "required_manual_steps": [
            "safe atomic swap (staged->adjacent->live, backup old live) per _depth9_safe_publish.py",
            "rebind ~25 approval YAMLs to the new build+policy id per _rebind_approvals_*.py",
            "run scripts/run_daily_qa.py — must be Overall PASS (manifest + approval binding + POLICY001)",
            "write parent-build metadata + retain the referenced old live as .bak",
        ],
        "generated_cst": now_cst().isoformat(timespec="seconds"),
    }
    PUBLISH_HANDOFF_PATH.write_text(json.dumps(handoff, ensure_ascii=False, indent=1), encoding="utf-8")
    logger.warning("Publish is MANUAL (§13). Wrote handoff %s. Execute the required_manual_steps "
                   "with the proven scripts, then run_daily_qa. This gate confirmed the review; it "
                   "did NOT publish.", PUBLISH_HANDOFF_PATH)
    return 3  # non-zero: a manual-handoff gate, not a completed publish


def main() -> int:
    ap = argparse.ArgumentParser(description="Monthly calendar freeze-bump driver")
    ap.add_argument("--plan", action="store_true", help="Preflight + target_end + plan only")
    ap.add_argument("--execute", action="store_true",
                    help="Run catch-up->rebuild->audits->dry-run report (multi-hour); STOPS before publish")
    ap.add_argument("--publish-approved", action="store_true", help="Run the publish leg")
    ap.add_argument("--i-reviewed-the-dryrun", action="store_true",
                    help="Attest the dry-run report was reviewed (required for --publish-approved)")
    ap.add_argument("--target-end", type=str, default=None, help="Override target_end (YYYYMMDD)")
    ap.add_argument("--allow-migration-exception", action="store_true",
                    help="Acknowledge that a frozen-prefix exception type recurring 2+ bumps has "
                         "been migrated to a permanent note+tests (M2). Without it, a recurring "
                         "exception type BLOCKS the bump.")
    args = ap.parse_args()

    if args.plan:
        phase_plan(args)
        return 0
    if args.execute:
        return phase_execute(args)
    if args.publish_approved:
        return phase_publish(args)
    logger.error("choose a mode: --plan (review) | --execute (multi-hour, stops before publish) | "
                 "--publish-approved --i-reviewed-the-dryrun")
    return 2


if __name__ == "__main__":
    sys.exit(main())
