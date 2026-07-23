"""B2 (2026-07-22): the daily coverage preflight rehearses the forward
runner's TEXT gates with today as decision time, so a coverage gap raises an
alert flag the DAY it appears — not at decision time.

Anti-drift pin: the preflight must REUSE run_forward_cycle's gate functions
verbatim (no local reimplementation), so the rehearsal can never diverge from
the real gate."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

SCRIPT = PROJECT_ROOT / "workspace" / "scripts" / "text_coverage_preflight.py"
SOURCES = ("anns_d", "irm_qa_sh", "irm_qa_sz", "research_report")
NOW = "2026-07-22T21:00:00+08:00"          # rehearsal decision time (CN)


@pytest.fixture()
def preflight_mod():
    spec = importlib.util.spec_from_file_location("text_coverage_preflight_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_manifest(mdir: Path, run_ts: pd.Timestamp, start: str, end: str,
                    *, ok=True, latest=False):
    m = {"run_ts": run_ts.isoformat(), "timezone": "Asia/Shanghai",
         "window": {"start": start, "end": end}, "lookback_days": 4,
         "counts": {s: 1 for s in SOURCES},
         "source_status": {s: "ok_nonzero_rows" for s in SOURCES},
         "failures": [] if ok else ["anns_d@x: fetch failed"],
         "ok": ok}
    mdir.mkdir(parents=True, exist_ok=True)
    (mdir / f"pull_manifest_{run_ts.strftime('%Y%m%d_%H%M%S')}.json").write_text(
        json.dumps(m), encoding="utf-8")
    if latest:
        (mdir / "pull_manifest_latest.json").write_text(json.dumps(m),
                                                        encoding="utf-8")


def _run(mod, tmp_path, now=NOW):
    mdir, ldir = tmp_path / "text_pull", tmp_path / "logs"
    rc = mod.main(["--manifest-dir", str(mdir), "--log-dir", str(ldir),
                   "--now", now])
    status_p = mdir / "coverage_preflight_latest.json"
    status = (json.loads(status_p.read_text(encoding="utf-8"))
              if status_p.exists() else None)
    flags = list(ldir.glob("text_coverage_alert_*.flag")) if ldir.exists() else []
    return rc, status, flags


def test_full_coverage_ok_and_clears_same_day_flag(preflight_mod, tmp_path):
    mdir, ldir = tmp_path / "text_pull", tmp_path / "logs"
    now = pd.Timestamp(NOW)
    # one clean window-form manifest covering the whole 30d dossier lookback
    _write_manifest(mdir, now - pd.Timedelta(hours=1),
                    "2026-06-20", "2026-07-22", latest=True)
    ldir.mkdir(parents=True)
    stale_flag = ldir / "text_coverage_alert_20260722.flag"
    stale_flag.write_text("{}", encoding="utf-8")   # recovered-run semantics
    rc, status, flags = _run(preflight_mod, tmp_path)
    assert rc == 0
    assert status["ok"] is True and not status["problems"]
    assert status["coverage_window"] == {"start": "2026-06-22",
                                         "end": "2026-07-22"}
    assert not flags                                # same-day flag cleared


def test_coverage_gap_writes_alert_flag_same_day(preflight_mod, tmp_path):
    mdir = tmp_path / "text_pull"
    now = pd.Timestamp(NOW)
    # window starts AFTER the dossier cutoff -> 2026-06-22..24 uncovered
    _write_manifest(mdir, now - pd.Timedelta(hours=1),
                    "2026-06-25", "2026-07-22", latest=True)
    rc, status, flags = _run(preflight_mod, tmp_path)
    assert rc == 1 and status["ok"] is False
    assert any(p["check"] == "coverage_history" for p in status["problems"])
    assert len(flags) == 1 and flags[0].name == "text_coverage_alert_20260722.flag"
    body = json.loads(flags[0].read_text(encoding="utf-8"))
    assert body["problems"]


def test_stale_latest_pull_is_flagged_even_with_full_coverage(preflight_mod, tmp_path):
    mdir = tmp_path / "text_pull"
    now = pd.Timestamp(NOW)
    _write_manifest(mdir, now - pd.Timedelta(hours=60),      # stale (>48h)
                    "2026-06-20", "2026-07-22", latest=True)
    rc, status, _ = _run(preflight_mod, tmp_path)
    assert rc == 1
    checks = {p["check"] for p in status["problems"]}
    assert checks == {"latest_pull"}       # coverage itself is fine


def test_missing_latest_manifest_is_flagged(preflight_mod, tmp_path):
    rc, status, flags = _run(preflight_mod, tmp_path)
    assert rc == 1
    checks = {p["check"] for p in status["problems"]}
    assert {"latest_pull", "coverage_history"} <= checks
    assert flags


def test_failed_manifest_recovered_by_later_clean_pull(preflight_mod, tmp_path):
    mdir = tmp_path / "text_pull"
    now = pd.Timestamp(NOW)
    _write_manifest(mdir, now - pd.Timedelta(days=2), "2026-06-20",
                    "2026-07-22", ok=False)
    _write_manifest(mdir, now - pd.Timedelta(hours=1), "2026-06-20",
                    "2026-07-22", latest=True)
    rc, status, _ = _run(preflight_mod, tmp_path)
    assert rc == 0 and status["ok"] is True


def test_preflight_reuses_runner_gates_verbatim():
    src = SCRIPT.read_text(encoding="utf-8")
    assert "check_text_coverage_history(" in src
    assert "check_pull_manifest(" in src
    # no local reimplementation of either gate — drift-proof by construction
    assert "def check_text_coverage_history" not in src
    assert "def check_pull_manifest" not in src
