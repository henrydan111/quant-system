"""B7/B5+M3: the daily text pull exits NON-ZERO on ANY source failure (a
partially-ingested window must never look like success to the scheduler or the
forward runner) and records a per-run manifest; an anns_d truncated day counts
as a failure."""
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
    spec = importlib.util.spec_from_file_location("text_daily_pull_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "MANIFEST_DIR", tmp_path / "text_pull")
    ingested = []
    monkeypatch.setattr(mod, "ingest_rows",
                        lambda source, df, **kw: ingested.append((source, len(df))))
    mod._ingested = ingested
    return mod


def _frame(truncated=False):
    df = pd.DataFrame([{"ts_code": "000001.SZ", "title": "t",
                        "rec_time": "2026-07-08 09:00:00", "pub_time": "2026-07-08 09:00:00"}])
    df.attrs["truncated"] = truncated
    return df


class _FakeFetcher:
    def __init__(self, *, anns_raises=False, anns_truncated=False):
        self._raises, self._trunc = anns_raises, anns_truncated

    def fetch_anns_d_paged(self, ymd):
        if self._raises:
            raise ConnectionError("simulated 网络故障")
        return _frame(truncated=self._trunc)

    def fetch_research_report(self, ymd):
        return _frame()

    def fetch_irm_qa_sh(self, s, e):
        return _frame()

    def fetch_irm_qa_sz(self, s, e):
        return _frame()


def _run(mod, monkeypatch, **fetcher_kw):
    monkeypatch.setattr(mod, "TushareFetcher", lambda: _FakeFetcher(**fetcher_kw))
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    rc = mod.main()
    manifest = json.loads((mod.MANIFEST_DIR / "pull_manifest_latest.json")
                          .read_text(encoding="utf-8"))
    return rc, manifest


def test_partial_source_failure_exits_nonzero(pull_mod, monkeypatch):
    rc, manifest = _run(pull_mod, monkeypatch, anns_raises=True)
    assert rc == 1                                   # OTHER sources succeeded — still fail
    assert manifest["ok"] is False and manifest["failures"]
    assert any("anns_d" in f for f in manifest["failures"])
    assert pull_mod._ingested                        # partial ingestion did happen


def test_truncated_anns_day_counts_as_failure(pull_mod, monkeypatch):
    rc, manifest = _run(pull_mod, monkeypatch, anns_truncated=True)
    assert rc == 1
    assert any("truncated" in f for f in manifest["failures"])


def test_clean_run_exits_zero_with_manifest(pull_mod, monkeypatch):
    rc, manifest = _run(pull_mod, monkeypatch)
    assert rc == 0 and manifest["ok"] is True
    assert manifest["counts"] and manifest["window"]["start"] <= manifest["window"]["end"]
