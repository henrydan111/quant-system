"""B1 ops hardening (2026-07-22): in-run circuit breaker + end-of-run retry
pass + additive manifest audit + partial-run isolation.

Gate-neutrality is the load-bearing property: a partial run must NEVER write
pull_manifest_latest.json, and un-attempted sources must never carry an ok_*
status (the coverage gate grants credit on str.startswith("ok_") alone)."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

SCRIPT = PROJECT_ROOT / "workspace" / "scripts" / "text_daily_pull.py"


@pytest.fixture()
def pull_mod(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("text_daily_pull_b1_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "MANIFEST_DIR", tmp_path / "text_pull")
    ingested = []
    monkeypatch.setattr(mod, "ingest_rows",
                        lambda source, df, **kw: ingested.append((source, len(df))))
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    mod._ingested = ingested
    return mod


def _frame(truncated=False):
    df = pd.DataFrame([{"ts_code": "000001.SZ", "title": "t",
                        "rec_time": "2026-07-08 09:00:00",
                        "pub_time": "2026-07-08 09:00:00"}])
    df.attrs["truncated"] = truncated
    return df


class _FlakyFetcher:
    """anns_d fails its first `fail_first_n` calls, then succeeds; other
    sources always succeed. `anns_truncated` makes every anns frame truncated."""

    def __init__(self, fail_first_n=0, anns_truncated=False):
        self.fail_first_n = fail_first_n
        self.anns_truncated = anns_truncated
        self.anns_calls = 0

    def fetch_anns_d_paged(self, ymd):
        self.anns_calls += 1
        if self.anns_calls <= self.fail_first_n:
            raise ConnectionError(f"simulated transient failure #{self.anns_calls}")
        return _frame(truncated=self.anns_truncated)

    def fetch_research_report(self, ymd):
        return _frame()

    def fetch_irm_qa_sh(self, s, e):
        return _frame()

    def fetch_irm_qa_sz(self, s, e):
        return _frame()


def _run(mod, monkeypatch, argv=None, **fetcher_kw):
    fetcher = _FlakyFetcher(**fetcher_kw)
    monkeypatch.setattr(mod, "TushareFetcher", lambda: fetcher)
    rc = mod.main(argv)
    stamped = sorted((mod.MANIFEST_DIR).glob("pull_manifest_2*.json"))
    manifest = json.loads(stamped[-1].read_text(encoding="utf-8"))
    return rc, manifest, fetcher


def test_transient_failure_recovered_by_retry_pass(pull_mod, monkeypatch):
    # 2 pass-1 failures open the breaker (days 3-4 skipped); the retry pass
    # re-attempts all 4 pairs and every one succeeds -> clean manifest, rc 0.
    rc, m, fetcher = _run(pull_mod, monkeypatch, fail_first_n=2)
    assert rc == 0 and m["ok"] is True and not m["failures"]
    assert m["source_status"]["anns_d"] == "ok_nonzero_rows"
    assert m["breaker_events"] and m["breaker_events"][0]["source"] == "anns_d"
    assert m["retry_pass"]["performed"] is True
    assert m["retry_pass"]["attempted"] == 4
    assert len(m["retry_pass"]["recovered"]) == 4
    assert any(a["pass"] == 2 and a["outcome"] == "ok_rows" for a in m["attempts"])
    # breaker saved the 2 doomed pass-1 calls: 2 fails + 4 retries = 6
    assert fetcher.anns_calls == 6


def test_persistent_failure_still_fails_with_audit(pull_mod, monkeypatch):
    rc, m, _ = _run(pull_mod, monkeypatch, fail_first_n=99)
    assert rc == 1 and m["ok"] is False
    assert m["source_status"]["anns_d"] == "failed"
    assert any("anns_d" in f for f in m["failures"])
    assert m["retry_pass"]["performed"] is True and not m["retry_pass"]["recovered"]
    # every attempt (both passes) is in the audit trail
    assert sum(a["source"] == "anns_d" and a["outcome"] == "error"
               for a in m["attempts"]) >= 3
    # latest IS written for a full run, even a failed one (status evidence)
    assert (pull_mod.MANIFEST_DIR / "pull_manifest_latest.json").exists()


def test_truncated_days_are_not_retried(pull_mod, monkeypatch):
    rc, m, _ = _run(pull_mod, monkeypatch, anns_truncated=True)
    assert rc == 1
    assert any("truncated" in f for f in m["failures"])
    assert m["retry_pass"]["performed"] is False
    assert not any(a["pass"] == 2 for a in m["attempts"])


def test_no_retry_pass_flag_disables_recovery(pull_mod, monkeypatch):
    rc, m, _ = _run(pull_mod, monkeypatch, argv=["--no-retry-pass"], fail_first_n=2)
    assert rc == 1 and m["ok"] is False
    assert m["retry_pass"]["performed"] is False


def test_partial_run_never_touches_latest_or_grants_credit(pull_mod, monkeypatch):
    rc, m, _ = _run(pull_mod, monkeypatch, argv=["--sources", "anns_d"])
    assert rc == 0 and m["ok"] is True
    assert m["partial_run"] is True and m["sources_pulled"] == ["anns_d"]
    # the latest-manifest gate must only ever see FULL runs
    assert not (pull_mod.MANIFEST_DIR / "pull_manifest_latest.json").exists()
    # un-attempted sources: never ok_* (no coverage credit), never "failed"
    for s in ("research_report", "irm_qa_sh", "irm_qa_sz"):
        assert m["source_status"][s] == "not_attempted"
    assert m["source_status"]["anns_d"] == "ok_nonzero_rows"


def test_unknown_source_refused(pull_mod, monkeypatch):
    monkeypatch.setattr(pull_mod, "TushareFetcher", lambda: _FlakyFetcher())
    assert pull_mod.main(["--sources", "nope"]) == 2
