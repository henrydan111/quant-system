from pathlib import Path
import sys
import types

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.modules.setdefault("tushare", types.SimpleNamespace(set_token=lambda *_args, **_kwargs: None, pro_api=lambda: None))

from data_infra.fetchers import TushareFetcher


class _DummyPro:
    def __init__(self):
        self.calls = []

    def income_vip(self, **kwargs):
        self.calls.append(("income_vip", dict(kwargs)))
        return pd.DataFrame([{"report_type": kwargs.get("report_type"), "period": kwargs.get("period")}])

    def cashflow_vip(self, **kwargs):
        self.calls.append(("cashflow_vip", dict(kwargs)))
        return pd.DataFrame([{"report_type": kwargs.get("report_type"), "period": kwargs.get("period")}])

    def fina_indicator_vip(self, **kwargs):
        self.calls.append(("fina_indicator_vip", dict(kwargs)))
        limit = int(kwargs.get("limit", 0))
        offset = int(kwargs.get("offset", 0))
        if kwargs.get("period") == "20240331":
            total = 6911
        else:
            total = 12050
        if offset >= total:
            return pd.DataFrame()
        rows = min(limit, total - offset)
        return pd.DataFrame(
            {
                "ts_code": [f"{offset + i:06d}.SZ" for i in range(rows)],
                "ann_date": ["20240425"] * rows,
                "end_date": [kwargs.get("period")] * rows,
                "update_flag": [1] * rows,
            }
        )


def _build_fetcher() -> TushareFetcher:
    fetcher = TushareFetcher.__new__(TushareFetcher)
    fetcher.pro = _DummyPro()
    fetcher.max_retries = 1
    fetcher.base_sleep = 0.0
    return fetcher


def test_income_quarterly_vip_combines_report_types():
    fetcher = _build_fetcher()
    df = fetcher.fetch_income_quarterly_vip(period="20240331")

    assert sorted(df["report_type"].astype(str).tolist()) == ["2", "3"]
    assert set(df["period"].astype(str).tolist()) == {"20240331"}


def test_cashflow_quarterly_vip_combines_report_types():
    fetcher = _build_fetcher()
    df = fetcher.fetch_cashflow_quarterly_vip(period="20240331")

    assert sorted(df["report_type"].astype(str).tolist()) == ["2", "3"]
    assert set(df["period"].astype(str).tolist()) == {"20240331"}


def test_fina_indicator_vip_uses_high_limit_and_single_call_when_period_fits():
    fetcher = _build_fetcher()

    df = fetcher.fetch_fina_indicator_vip(period="20240331")

    assert len(df) == 6911
    indicator_calls = [kwargs for name, kwargs in fetcher.pro.calls if name == "fina_indicator_vip"]
    assert len(indicator_calls) == 1
    assert indicator_calls[0]["limit"] == 10000
    assert indicator_calls[0]["offset"] == 0


def test_fina_indicator_vip_keeps_offset_pagination_as_fallback():
    fetcher = _build_fetcher()

    df = fetcher.fetch_fina_indicator_vip(period="20241231")

    assert len(df) == 12050
    indicator_calls = [kwargs for name, kwargs in fetcher.pro.calls if name == "fina_indicator_vip"]
    assert [call["offset"] for call in indicator_calls] == [0, 10000]
    assert all(call["limit"] == 10000 for call in indicator_calls)


def test_locked_pro_routes_calls_and_refuses_raw_escape(tmp_path, monkeypatch):
    # GPT 5-C Major 1 + re-review #4: the _LockedPro proxy routes EVERY endpoint call through the
    # cross-process lock (spaced_call) AND leaves no unlocked handle — `fetcher.pro._real` must NOT
    # return the raw client (a bare __getattr__ would leak it; __getattribute__ + __slots__ closes it).
    import pytest
    from data_infra import tushare_lock
    from data_infra.fetchers import _LockedPro
    monkeypatch.setattr(tushare_lock, "_ACCOUNT_LOCK_DIR", tmp_path / "locks")  # inject via attr, not env

    captured = []

    class _FakeRaw:
        data_attr = 42

        def report_rc(self, **kw):
            captured.append(kw)
            return "OK"

    proxy = _LockedPro(_FakeRaw(), 0.0)
    assert proxy.report_rc(ts_code="000001.SZ") == "OK"       # routed, real result returned
    assert captured == [{"ts_code": "000001.SZ"}]
    assert proxy.data_attr == 42                               # non-callable attrs pass through
    assert proxy.__class__.__name__ == "_LockedPro"           # dunders resolve on the wrapper
    for private in ("_real", "_base_sleep", "__dict__"):       # no CASUAL unlocked client handle
        with pytest.raises(AttributeError):
            getattr(proxy, private)
    import pickle                                              # unpicklable (Windows spawn) — GPT M1
    with pytest.raises(TypeError):
        pickle.dumps(proxy)
