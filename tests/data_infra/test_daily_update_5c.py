"""Phase 5-C daily-raw job: last-complete-session resolution (CST close-aware) + the canonical
timing-preserving suspend_d writer."""
from __future__ import annotations

import sys
import types
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from data_infra.pipeline.update_daily_data import (  # noqa: E402
    DailyDataUpdater, resolve_last_complete_session, _validate_trade_cal)
from data_infra.pipeline import daily_ops  # noqa: E402
from data_infra import tushare_lock  # noqa: E402 — lock-dir injected via module attr, not an env var


def _stub_updater(ref_dir):
    stub = DailyDataUpdater.__new__(DailyDataUpdater)  # bypass __init__ (no Tushare/config)
    stub.ref_dir = str(ref_dir)
    stub.update_reference_data = lambda d: None  # no-op the fetch
    return stub


def test_update_for_date_saturday_is_non_trading_skip(tmp_path):
    # GPT M2: the calendar holds ONLY open days (is_open='1' fetch); a Saturday is ABSENT -> a
    # legitimate non-trading skip (exit 0), NOT "missing daily data".
    ref = tmp_path / "reference"
    ref.mkdir(parents=True)
    pd.DataFrame({"exchange": "SSE", "cal_date": ["20260703", "20260706", "20260707"], "is_open": 1,
                  "pretrade_date": ""}).to_parquet(ref / "trade_cal.parquet")
    res = DailyDataUpdater.update_for_date(_stub_updater(ref), "20260704")  # Saturday
    assert res["is_trading_day"] is False and res["errors"] == []


def test_update_for_date_beyond_coverage_is_error(tmp_path):
    # GPT M2: a date beyond calendar coverage is an ERROR (insufficient calendar), not a silent skip.
    ref = tmp_path / "reference"
    ref.mkdir(parents=True)
    pd.DataFrame({"exchange": "SSE", "cal_date": ["20260703"], "is_open": 1,
                  "pretrade_date": ""}).to_parquet(ref / "trade_cal.parquet")
    res = DailyDataUpdater.update_for_date(_stub_updater(ref), "20260710")  # > max 20260703
    assert res["is_trading_day"] is True and res["errors"]


def _holder_code(lockdir, marker):
    # a spawned holder injects the lock dir via the MODULE ATTRIBUTE (not an env var — the env override
    # is removed), acquires raw_maintenance_lock, and holds it while sleeping.
    return (
        "import sys, time, pathlib\n"
        f"sys.path.insert(0, r'{ROOT / 'src'}')\n"
        "import data_infra.tushare_lock as tl\n"
        f"tl._DATA_LOCK_DIR = pathlib.Path(r'{lockdir}')\n"
        "from data_infra.tushare_lock import raw_maintenance_lock\n"
        "with raw_maintenance_lock():\n"
        f"    open(r'{marker}', 'w').close()\n"
        "    time.sleep(30)\n"
    )


def test_raw_maintenance_lock_kernel_held_and_auto_released(tmp_path, monkeypatch):
    # GPT B1: the lock is KERNEL-held (filelock) — a second acquirer blocks while the first holds it,
    # and the OS releases it when the holder process DIES (no age-based stealing). A subprocess holds
    # it; the parent must time out; after the holder is killed, the parent acquires.
    import subprocess as _sp
    import time as _time
    import filelock
    lockdir = tmp_path / "locks"
    monkeypatch.setattr(tushare_lock, "_DATA_LOCK_DIR", lockdir)  # inject via attr, not env
    holder = _sp.Popen([sys.executable, "-c", _holder_code(lockdir, tmp_path / "acq")])
    try:
        for _ in range(200):  # wait until the holder has acquired
            if (tmp_path / "acq").exists():
                break
            _time.sleep(0.05)
        assert (tmp_path / "acq").exists(), "holder never acquired"
        with pytest.raises(filelock.Timeout):
            with tushare_lock.raw_maintenance_lock(timeout=0.3):
                pass
    finally:
        holder.kill()
        holder.wait()
    with tushare_lock.raw_maintenance_lock(timeout=5):  # holder died -> OS released it (not age-based)
        pass


def test_raw_maintenance_lock_namespace_not_env_forgeable(tmp_path, monkeypatch):
    # GPT REWORK-5 Blocker 1: the lock namespace must NOT be forgeable via an ambient env var. A live
    # subprocess holds the lock; the parent — even with QUANT_LOCK_DIR pointed at a DIFFERENT directory
    # (the old bypass) — must still contend on the SAME immutable lock and time out (the env is ignored).
    import subprocess as _sp
    import time as _time
    import filelock
    lockdir = tmp_path / "locks"
    monkeypatch.setattr(tushare_lock, "_DATA_LOCK_DIR", lockdir)  # the real (injected) identity
    holder = _sp.Popen([sys.executable, "-c", _holder_code(lockdir, tmp_path / "acq2")])
    try:
        for _ in range(200):
            if (tmp_path / "acq2").exists():
                break
            _time.sleep(0.05)
        assert (tmp_path / "acq2").exists(), "holder never acquired"
        # FORGE a different namespace via the (now-ignored) env var — must NOT grant a second lock
        monkeypatch.setenv("QUANT_LOCK_DIR", str(tmp_path / "ALT_namespace"))
        with pytest.raises(filelock.Timeout):
            with tushare_lock.raw_maintenance_lock(timeout=0.3):
                pass
    finally:
        holder.kill()
        holder.wait()
    with tushare_lock.raw_maintenance_lock(timeout=5):  # holder gone -> real lock free
        pass


def _load_script(name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, str(ROOT / "scripts" / f"{name}.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _provider_scaffold(tmp_path, tail_iso="2026-07-01", attested_iso="2026-07-01",
                       day_txt="2026-06-30\n2026-07-01\n"):
    import json as _json
    cal_dir = tmp_path / "data" / "qlib_data" / "calendars"
    meta = tmp_path / "data" / "qlib_data" / "metadata"
    ref = tmp_path / "data" / "reference"
    for d in (cal_dir, meta, ref):
        d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"exchange": "SSE", "cal_date": ["20260630", "20260701"], "is_open": 1,
                  "pretrade_date": ["", "20260630"]}).to_parquet(ref / "trade_cal.parquet")
    (cal_dir / "day.txt").write_text(day_txt, encoding="utf-8")
    (meta / "provider_build.json").write_text(
        _json.dumps({"provider": {"calendar_end_date": attested_iso}}), encoding="utf-8")
    return str(ref)


def test_provider_floor_attestation_fail_closed(tmp_path):
    # GPT M4: the floor must be ATTESTED — day.txt tail == provider_build.json calendar_end_date AND a
    # real open SSE session. Mismatch / unsorted / future floor fails closed. Shared helper (M2.4).
    from data_infra.pipeline.daily_ops import provider_floor, ProviderFloorError
    ref = _provider_scaffold(tmp_path)
    assert provider_floor(tmp_path, ref) == "20260701"  # tail == attested == open session
    _provider_scaffold(tmp_path, attested_iso="2026-06-30")  # manifest mismatch
    with pytest.raises(ProviderFloorError, match="attested|calendar_end"):
        provider_floor(tmp_path, ref)
    _provider_scaffold(tmp_path, day_txt="2026-07-01\n2026-06-30\n")  # unsorted
    with pytest.raises(ProviderFloorError, match="sorted"):
        provider_floor(tmp_path, ref)
    _provider_scaffold(tmp_path, day_txt="2026-06-30\n2026-07-01\n2099-01-01\n", attested_iso="2099-01-01")
    with pytest.raises(ProviderFloorError, match="open trading session"):  # future floor not a real session
        provider_floor(tmp_path, ref)


def test_watchdog_requires_latest_attempt_certified(tmp_path, monkeypatch):
    # GPT REWORK-5 M2: a stale PASS heartbeat must NOT certify a later FAILED run. The heartbeat must
    # belong to the LATEST attempt (start_attempt deletes a prior one) and prove qa_ok for this cut.
    import json as _json
    from data_infra.pipeline import daily_ops
    from data_infra.pipeline import update_daily_data as udd
    wd = _load_script("daily_job_watchdog")
    logs = tmp_path / "logs"
    logs.mkdir()
    ref = _provider_scaffold(tmp_path)  # floor attested to 20260701
    monkeypatch.setattr(wd, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(wd, "LOGS_DIR", logs)
    monkeypatch.setattr(wd, "HEARTBEAT", logs / "daily_job_heartbeat.json")
    monkeypatch.setattr(udd, "resolve_last_complete_session", lambda ref_dir: "20260702")  # floor<expected
    monkeypatch.setattr(daily_ops, "compute_contiguous_watermark", lambda *a, **k: "20260702")
    monkeypatch.setattr(daily_ops, "manifest_set_digest", lambda *a, **k: "DIG")
    alert = logs / f"daily_job_alert_{wd._cst_date()}.flag"
    daily_ops.start_attempt(str(logs), "ATT1", "20260702")  # attempt exists, heartbeat invalidated

    def _hb(attempt, qa):
        return {"attempt_id": attempt, "completed_session": "20260702", "floor": "20260701",
                "qa_ok": qa, "manifest_digest": "DIG"}

    # A) latest attempt has NO heartbeat -> RED
    assert wd.main() == 1 and alert.exists()
    # B) heartbeat from a STALE attempt (ATT0) -> RED (does not certify the latest attempt)
    wd.HEARTBEAT.write_text(_json.dumps(_hb("ATT0", True)), encoding="utf-8")
    assert wd.main() == 1
    # C) latest-attempt heartbeat but qa_ok False -> RED
    wd.HEARTBEAT.write_text(_json.dumps(_hb("ATT1", False)), encoding="utf-8")
    assert wd.main() == 1
    # D) latest-attempt, qa_ok True -> GREEN, alert cleared
    wd.HEARTBEAT.write_text(_json.dumps(_hb("ATT1", True)), encoding="utf-8")
    assert wd.main() == 0 and not alert.exists()


def test_watchdog_greens_when_provider_current(tmp_path, monkeypatch):
    # GPT REWORK-5 M2: floor == expected (provider current, e.g. just after a monthly publish) is green
    # WITHOUT a heartbeat — there was genuinely nothing to backfill (no false-red period).
    from data_infra.pipeline import update_daily_data as udd
    wd = _load_script("daily_job_watchdog")
    logs = tmp_path / "logs"
    logs.mkdir()
    ref = _provider_scaffold(tmp_path)  # floor attested to 20260701
    monkeypatch.setattr(wd, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(wd, "LOGS_DIR", logs)
    monkeypatch.setattr(wd, "HEARTBEAT", logs / "daily_job_heartbeat.json")
    monkeypatch.setattr(udd, "resolve_last_complete_session", lambda ref_dir: "20260701")  # == floor
    (logs / f"daily_job_alert_{wd._cst_date()}.flag").write_text("stale", encoding="utf-8")
    assert wd.main() == 0 and not (logs / f"daily_job_alert_{wd._cst_date()}.flag").exists()


def test_spaced_call_fails_closed_when_state_unwritable(tmp_path, monkeypatch):
    # GPT minor 1: if the shared next-allowed timestamp can't be persisted, spacing must be enforced
    # IN-BAND (sleep under the API lock), never silently dropped to zero.
    import time as _time
    monkeypatch.setattr(tushare_lock, "_ACCOUNT_LOCK_DIR", tmp_path / "locks")  # inject via attr, not env
    monkeypatch.setattr(tushare_lock, "_set_next_allowed", lambda delta: False)  # simulate unwritable
    t0 = _time.time()
    tushare_lock.spaced_call(lambda: "ok", 0.4)
    assert _time.time() - t0 >= 0.35  # it slept in-band rather than returning instantly


def test_spaced_call_fails_closed_on_nan_state(tmp_path, monkeypatch):
    # GPT REWORK-5 minor 1: a state file containing `nan` parses via float() but makes delay>0 False and
    # fires immediately. isfinite-guard must force the conservative in-band sleep.
    import time as _time
    monkeypatch.setattr(tushare_lock, "_ACCOUNT_LOCK_DIR", tmp_path / "locks")
    (tmp_path / "locks").mkdir(parents=True)
    tushare_lock._next_allowed_path().write_text("nan")
    t0 = _time.time()
    tushare_lock.spaced_call(lambda: "ok", 0.4)
    assert _time.time() - t0 >= 0.35  # NaN treated as unreadable -> conservative in-band sleep


def test_session_status_watermark_and_backlog(tmp_path):
    # GPT M1/M3: completion is manifest-based; the watermark advances only over a CONTIGUOUS run of
    # complete sessions; backlog is discovered from the watermark (floor), oldest-first.
    ref = tmp_path / "reference"
    ref.mkdir(parents=True)
    opens = ["20260701", "20260702", "20260703", "20260704"]
    pd.DataFrame({"exchange": "SSE", "cal_date": opens, "is_open": 1,
                  "pretrade_date": ""}).to_parquet(ref / "trade_cal.parquet")
    logs = str(tmp_path / "logs")
    floor = "20260701"  # provider boundary; daily job owns 0702..0704
    # nothing done yet -> backlog = 0702,0703,0704
    assert daily_ops.backlog_sessions(str(ref), logs, "20260704", floor) == ["20260702", "20260703", "20260704"]
    # 0702 complete, 0703 INCOMPLETE (daily ok but a required endpoint failed), 0704 complete
    daily_ops.write_session_status(logs, "20260702", True)
    daily_ops.write_session_status(logs, "20260703", False)
    daily_ops.write_session_status(logs, "20260704", True)
    # watermark advances only to 0702 (0703 breaks the contiguous run) — NOT past the hole to 0704
    assert daily_ops.advance_watermark(str(ref), logs, "20260704", floor) == "20260702"
    # backlog now = ONLY the incomplete 0703 (0704 already complete, 0702 done + watermark at 0702)
    assert daily_ops.backlog_sessions(str(ref), logs, "20260704", floor) == ["20260703"]
    # fill the hole -> watermark jumps contiguously to 0704
    daily_ops.write_session_status(logs, "20260703", True)
    assert daily_ops.advance_watermark(str(ref), logs, "20260704", floor) == "20260704"


def test_validate_trade_cal_rejects_missing_session():
    # GPT Blocker 2: a syntactically-fine fresh calendar MISSING 20260702 (with a dangling
    # pretrade_date) must be REJECTED by the continuity check.
    bad = pd.DataFrame({"exchange": ["SSE", "SSE"], "cal_date": ["20260701", "20260703"], "is_open": [1, 1],
                        "pretrade_date": ["20260630", "20260702"]})  # 0703 references the absent 0702
    with pytest.raises(ValueError, match="continuity"):
        _validate_trade_cal(bad, fresh=True)
    good = pd.DataFrame({"exchange": ["SSE"] * 3, "cal_date": ["20260701", "20260702", "20260703"],
                         "is_open": [1, 1, 1], "pretrade_date": ["20260630", "20260701", "20260702"]})
    _validate_trade_cal(good, fresh=True)  # complete chain -> ok


def test_session_required_ok_strict(tmp_path):
    # GPT M2: a string "false" must not be truthy; a mislabelled date must fail.
    import json
    logs = str(tmp_path)
    sd = tmp_path / "session_status"
    sd.mkdir()
    (sd / "20260703.json").write_text(json.dumps({"date": "20260703", "required_ok": "false"}))
    assert daily_ops.session_required_ok(logs, "20260703") is False
    (sd / "20260703.json").write_text(json.dumps({"date": "20260702", "required_ok": True}))  # wrong date
    assert daily_ops.session_required_ok(logs, "20260703") is False
    (sd / "20260703.json").write_text(json.dumps({"date": "20260703", "required_ok": True}))
    assert daily_ops.session_required_ok(logs, "20260703") is True


def test_contiguous_watermark_ignores_poisoned_future_cache(tmp_path):
    # GPT M2: a cached future watermark (20990101) must NOT false-green; the watermark is recomputed
    # from the floor every call.
    ref = tmp_path / "reference"
    ref.mkdir(parents=True)
    pd.DataFrame({"exchange": "SSE", "cal_date": ["20260701", "20260702", "20260703"], "is_open": 1,
                  "pretrade_date": ""}).to_parquet(ref / "trade_cal.parquet")
    logs = str(tmp_path / "logs")
    daily_ops.save_watermark(logs, "20990101")  # poisoned
    assert daily_ops.contiguous_watermark(str(ref), logs, "20260703", "20260701") == "20260701"


def _daily_frame(codes=("A", "B"), date="20260703"):
    n = len(codes)
    return pd.DataFrame({"ts_code": list(codes), "trade_date": [date] * n,
                         "open": [1.0] * n, "high": [1.1] * n, "low": [0.9] * n, "close": [1.0] * n,
                         "vol": [100.0] * n, "amount": [1000.0] * n, "pre_close": [1.0] * n})


def _market_stub(tmp_path, daily, adj, basic):
    stub = DailyDataUpdater.__new__(DailyDataUpdater)
    stub.market_daily_dir = str(tmp_path / "daily")
    stub.fetcher = types.SimpleNamespace(
        fetch_daily_data=lambda trade_date: daily,
        fetch_fundamentals=lambda trade_date: basic,
        fetch_adj_factor=lambda trade_date: adj)
    return stub


def test_update_market_data_raises_on_empty_adj_factor(tmp_path):
    # GPT B3: nonempty daily but EMPTY adj_factor (engine-required) must RAISE + NOT write.
    from data_infra.pipeline.update_daily_data import MarketDataError
    stub = _market_stub(tmp_path, _daily_frame(),
                        pd.DataFrame(),  # empty adj
                        pd.DataFrame({"ts_code": ["A", "B"], "trade_date": ["20260703"] * 2, "pe": [1.0, 2.0]}))
    with pytest.raises(MarketDataError, match="adj_factor EMPTY"):
        DailyDataUpdater.update_market_data(stub, "20260703")
    assert not (tmp_path / "daily" / "2026" / "daily_20260703.parquet").exists()  # prior preserved


def test_update_market_data_commits_when_complete(tmp_path):
    adj = pd.DataFrame({"ts_code": ["A", "B"], "trade_date": ["20260703"] * 2, "adj_factor": [1.0, 1.2]})
    basic = pd.DataFrame({"ts_code": ["A", "B"], "trade_date": ["20260703"] * 2, "pe": [10.0, 20.0]})
    stub = _market_stub(tmp_path, _daily_frame(), adj, basic)
    codes = DailyDataUpdater.update_market_data(stub, "20260703")
    assert codes == {"A", "B"}
    out = pd.read_parquet(tmp_path / "daily" / "2026" / "daily_20260703.parquet")
    assert out["adj_factor"].notna().all() and out["pe"].notna().all()  # no hole, real payload


def test_update_market_data_m1_probes_rejected(tmp_path):
    # GPT REWORK-5 M1: the three probes that used to slip through must all RAISE.
    from data_infra.pipeline.update_daily_data import MarketDataError
    good_adj = pd.DataFrame({"ts_code": ["A", "B"], "trade_date": ["20260703"] * 2, "adj_factor": [1.0, 1.2]})
    good_basic = pd.DataFrame({"ts_code": ["A", "B"], "trade_date": ["20260703"] * 2, "pe": [1.0, 2.0]})
    # (a) wrong-date daily_basic -> merges all-null -> rejected (target-date check)
    wrong_basic = pd.DataFrame({"ts_code": ["A", "B"], "trade_date": ["20260702"] * 2, "pe": [1.0, 2.0]})
    with pytest.raises(MarketDataError, match="daily_basic .*other trade_dates|daily_basic"):
        DailyDataUpdater.update_market_data(_market_stub(tmp_path, _daily_frame(), good_adj, wrong_basic), "20260703")
    # (b) duplicate adj keys -> rejected (natural-key uniqueness)
    dup_adj = pd.DataFrame({"ts_code": ["A", "A", "B"], "trade_date": ["20260703"] * 3, "adj_factor": [1.0, 1.0, 1.2]})
    with pytest.raises(MarketDataError, match="duplicate"):
        DailyDataUpdater.update_market_data(_market_stub(tmp_path, _daily_frame(), dup_adj, good_basic), "20260703")
    # (c) adj covers only 1 of 2 priced codes (a null row) -> rejected (100% coverage)
    partial_adj = pd.DataFrame({"ts_code": ["A", "B"], "trade_date": ["20260703"] * 2, "adj_factor": [1.0, np.nan]})
    with pytest.raises(MarketDataError, match="100%|positive adj_factor"):
        DailyDataUpdater.update_market_data(_market_stub(tmp_path, _daily_frame(), partial_adj, good_basic), "20260703")


def test_validate_trade_cal_rejects_malformed():
    # GPT B2: reject malformed ground truth, do NOT coerce it.
    good = pd.DataFrame({"exchange": ["SSE"], "cal_date": ["20260703"], "is_open": [1], "pretrade_date": [""]})
    _validate_trade_cal(good, fresh=True)  # ok
    with pytest.raises(ValueError, match="is_open"):
        _validate_trade_cal(pd.DataFrame({"exchange": ["SSE"], "cal_date": ["20260703"], "is_open": ["BAD"]}), fresh=False)
    with pytest.raises(ValueError, match="non-open"):  # fresh fetch must be all is_open=1
        _validate_trade_cal(pd.DataFrame({"exchange": ["SSE"], "cal_date": ["20260703"], "is_open": [0]}), fresh=True)
    with pytest.raises(ValueError, match="8-digit"):
        _validate_trade_cal(pd.DataFrame({"exchange": ["SSE"], "cal_date": ["2026-7-3"], "is_open": [1]}), fresh=True)
    with pytest.raises(ValueError, match="required columns"):
        _validate_trade_cal(pd.DataFrame({"cal_date": ["20260703"], "is_open": [1]}), fresh=True)


def _trade_cal(tmp_path, open_days):
    ref = tmp_path / "reference"
    ref.mkdir(parents=True, exist_ok=True)
    # a full week Mon..Sun; is_open=1 only for open_days
    days = ["20260629", "20260630", "20260701", "20260702", "20260703", "20260704", "20260705"]
    pd.DataFrame({"exchange": "SSE", "cal_date": days,
                  "is_open": [1 if d in open_days else 0 for d in days],
                  "pretrade_date": ""}).to_parquet(ref / "trade_cal.parquet")
    return str(ref)


OPEN = {"20260629", "20260630", "20260701", "20260702", "20260703"}  # Mon..Fri


def test_last_complete_session_before_close_rolls_back(tmp_path):
    ref = _trade_cal(tmp_path, OPEN)
    # Friday 20260703 at 14:00 CST — today's data not yet complete -> prior session (Thu 0702)
    assert resolve_last_complete_session(ref, now=datetime(2026, 7, 3, 14, 0)) == "20260702"


def test_last_complete_session_after_close_is_today(tmp_path):
    ref = _trade_cal(tmp_path, OPEN)
    # Friday 20260703 at 18:00 CST — past close -> today
    assert resolve_last_complete_session(ref, now=datetime(2026, 7, 3, 18, 0)) == "20260703"


def test_last_complete_session_on_weekend_uses_last_trading_day(tmp_path):
    ref = _trade_cal(tmp_path, OPEN)
    # Saturday 20260704 (closed) -> the last open day <= today = Friday 0703 (complete)
    assert resolve_last_complete_session(ref, now=datetime(2026, 7, 4, 12, 0)) == "20260703"


def test_last_complete_session_fails_closed_on_stale_calendar(tmp_path):
    # GPT B1: a calendar not future-aware through today (e.g. truncated by a prior buggy run) must
    # FAIL, not silently pick a stale session.
    ref = _trade_cal(tmp_path, OPEN)  # calendar ends 20260705
    with pytest.raises(SystemExit, match="future-aware|stale"):
        resolve_last_complete_session(ref, now=datetime(2026, 7, 10, 18, 0))  # today > calendar end


def test_last_complete_session_fails_when_only_preclose_today(tmp_path):
    # m2: if the only candidate is a pre-close today, refuse a partial session rather than return it.
    ref = _trade_cal(tmp_path, {"20260629"})  # only one open day, which is "today"
    with pytest.raises(SystemExit, match="pre-close|partial"):
        resolve_last_complete_session(ref, now=datetime(2026, 6, 29, 9, 0))


def test_update_reference_data_merges_calendar_not_truncate(tmp_path):
    # GPT B1 regression: a daily run must NOT truncate the future-aware calendar to target_date (which
    # freezes the selector). update_reference_data fetches a forward horizon and MERGES; a Monday run
    # must leave Tuesday selectable.
    ref = tmp_path / "reference"
    ref.mkdir(parents=True)
    pd.DataFrame({"exchange": "SSE",
                  "cal_date": pd.bdate_range("20260101", "20261231").strftime("%Y%m%d"),
                  "is_open": 1, "pretrade_date": ""}).to_parquet(ref / "trade_cal.parquet")
    fetched = pd.DataFrame({"exchange": "SSE",
                            "cal_date": pd.bdate_range("20260101", "20271231").strftime("%Y%m%d"),
                            "is_open": 1, "pretrade_date": ""})
    stub = types.SimpleNamespace(ref_dir=str(ref), fetcher=types.SimpleNamespace(
        fetch_stock_basic=lambda: pd.DataFrame(),
        fetch_trade_cal=lambda end_date: fetched))
    DailyDataUpdater.update_reference_data(stub, "20260706")  # a "Monday" run
    cal = pd.read_parquet(ref / "trade_cal.parquet")
    assert cal["cal_date"].astype(str).max() > "20260706", "future calendar must NOT be truncated"
    # Tuesday selector (post-close) returns Tuesday — the job advances, not stuck on Monday
    assert resolve_last_complete_session(str(ref), now=datetime(2026, 7, 7, 18, 0)) == "20260707"


def test_write_suspend_d_preserves_timing_atomic_overwrite(tmp_path):
    # the canonical writer keeps suspend_timing and overwrites (replaces) the same-date snapshot.
    df = pd.DataFrame({"ts_code": ["000001.SZ", "600000.SH"], "trade_date": ["20260703", "20260703"],
                       "suspend_type": ["S", "S"], "suspend_timing": ["", "09:30-10:00"],
                       "extra_col": [1, 2]})  # extra_col must be dropped
    stub = types.SimpleNamespace(
        data_dir=str(tmp_path),
        fetcher=types.SimpleNamespace(fetch_suspend_d=lambda trade_date: df))
    res = DailyDataUpdater.write_suspend_d(stub, "20260703")
    assert res["suspend_rows"] == 2 and res["suspend_timing_present"] is True
    out = pd.read_parquet(tmp_path / "market" / "suspend_d" / "2026" / "suspend_d_20260703.parquet")
    assert list(out.columns) == ["ts_code", "trade_date", "suspend_type", "suspend_timing"]
    assert set(out["suspend_timing"]) == {"", "09:30-10:00"}
    # re-fetch with fewer rows REPLACES (not merges) the snapshot
    df2 = pd.DataFrame({"ts_code": ["000001.SZ"], "trade_date": ["20260703"], "suspend_type": ["S"],
                        "suspend_timing": [""]})
    stub.fetcher = types.SimpleNamespace(fetch_suspend_d=lambda trade_date: df2)
    DailyDataUpdater.write_suspend_d(stub, "20260703")
    out2 = pd.read_parquet(tmp_path / "market" / "suspend_d" / "2026" / "suspend_d_20260703.parquet")
    assert len(out2) == 1  # replaced, not accumulated


def test_write_suspend_d_empty_day_writes_schema(tmp_path):
    stub = types.SimpleNamespace(
        data_dir=str(tmp_path),
        fetcher=types.SimpleNamespace(fetch_suspend_d=lambda trade_date: pd.DataFrame()))
    res = DailyDataUpdater.write_suspend_d(stub, "20260703")
    assert res["suspend_rows"] == 0
    out = pd.read_parquet(tmp_path / "market" / "suspend_d" / "2026" / "suspend_d_20260703.parquet")
    assert len(out) == 0 and "suspend_timing" in out.columns  # empty snapshot with the expected schema


def test_write_suspend_d_rejects_wrong_date_and_preserves_prior(tmp_path):
    # GPT M3: a response carrying the WRONG trade_date must RAISE and preserve the prior valid snapshot.
    good = pd.DataFrame({"ts_code": ["000001.SZ"], "trade_date": ["20260703"], "suspend_type": ["S"],
                         "suspend_timing": [""]})
    stub = types.SimpleNamespace(data_dir=str(tmp_path),
                                 fetcher=types.SimpleNamespace(fetch_suspend_d=lambda trade_date: good))
    DailyDataUpdater.write_suspend_d(stub, "20260703")
    path = tmp_path / "market" / "suspend_d" / "2026" / "suspend_d_20260703.parquet"
    assert len(pd.read_parquet(path)) == 1
    bad = pd.DataFrame({"ts_code": ["000002.SZ"], "trade_date": ["20260702"], "suspend_type": ["S"],
                        "suspend_timing": [""]})  # wrong date
    stub.fetcher = types.SimpleNamespace(fetch_suspend_d=lambda trade_date: bad)
    with pytest.raises(ValueError, match="trade_date"):
        DailyDataUpdater.write_suspend_d(stub, "20260703")
    assert list(pd.read_parquet(path)["ts_code"]) == ["000001.SZ"]  # prior snapshot intact


def test_write_suspend_d_rejects_missing_timing(tmp_path):
    # GPT M3: a nonempty response without suspend_timing is ambiguous -> RAISE (don't write).
    bad = pd.DataFrame({"ts_code": ["000001.SZ"], "trade_date": ["20260703"], "suspend_type": ["S"]})
    stub = types.SimpleNamespace(data_dir=str(tmp_path),
                                 fetcher=types.SimpleNamespace(fetch_suspend_d=lambda trade_date: bad))
    with pytest.raises(ValueError, match="missing columns|suspend_timing"):
        DailyDataUpdater.write_suspend_d(stub, "20260703")
    assert not (tmp_path / "market" / "suspend_d" / "2026" / "suspend_d_20260703.parquet").exists()
