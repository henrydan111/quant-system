# NF wave §7 step 1: fetch_news_covered recursive window-split coverage (design B2).
# Mocks the single-call primitive — no real Tushare call.
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from data_infra.fetchers import TushareFetcher  # noqa: E402


class _FakeFetcher(TushareFetcher):
    """Bypass __init__ (no token / no API); inject a synthetic flash stream."""

    def __init__(self, stream):
        # stream: list of (datetime_str, title) sorted by time
        self._stream = stream

    def fetch_news(self, src, start, end):
        t0, t1 = pd.Timestamp(start), pd.Timestamp(end)
        rows = [{"datetime": d, "title": t, "content": f"body-{t}", "channels": "",
                 "src": src}
                for d, t in self._stream
                if t0 <= pd.Timestamp(d) <= t1]
        rows = rows[: self._NEWS_CAP + 50]          # simulate the vendor cap
        df = pd.DataFrame(rows)
        df.attrs["cap_hit"] = len(df) >= self._NEWS_CAP
        return df


def _stream(n, start="2025-01-27 09:00:00", step_s=1):
    base = pd.Timestamp(start)
    return [((base + pd.Timedelta(seconds=i * step_s)).strftime("%Y-%m-%d %H:%M:%S"),
             f"flash-{i}") for i in range(n)]


def test_uncapped_window_complete_artifact():
    f = _FakeFetcher(_stream(100))
    df, cov = f.fetch_news_covered("sina", "2025-01-27 09:00:00",
                                   "2025-01-27 10:00:00")
    assert len(df) == 100
    assert cov["complete"] is True
    assert len(cov["windows"]) == 1 and cov["windows"][0]["status"] == "ok"


def test_capped_window_splits_and_covers_all():
    # 3000 flashes over an hour → exceeds the 1500 cap → must split and recover all
    f = _FakeFetcher(_stream(3000, step_s=1))   # 3000s ≈ 50 min
    df, cov = f.fetch_news_covered("sina", "2025-01-27 09:00:00",
                                   "2025-01-27 10:00:00")
    assert len(df) == 3000                       # no flash lost
    assert df["content"].is_unique                # overlap dedup worked
    assert cov["complete"] is True               # every leaf resolved
    w = cov["windows"]
    assert any(x["status"] == "split" for x in w)     # split parent recorded
    assert any(x["status"] == "ok" for x in w)
    assert all(x["status"] in ("ok", "split", "cap_at_min_window") for x in w)


def test_dedup_absorbs_boundary_overlap():
    f = _FakeFetcher(_stream(3000, step_s=1))
    df, _ = f.fetch_news_covered("sina", "2025-01-27 09:00:00",
                                 "2025-01-27 10:00:00")
    key = df["src"] + "|" + df["datetime"] + "|" + df["content"]
    assert key.is_unique                          # no boundary double-count


def test_cap_at_min_window_makes_coverage_incomplete():
    # 2000 flashes inside a single 60s window → cannot split below min → coverage
    # MUST be complete=False (M1: caller must not freeze/advance on incomplete)
    burst = [(f"2025-01-27 09:00:{s % 60:02d}", f"b-{i}")
             for i, s in enumerate(range(2000))]
    f = _FakeFetcher(burst)
    df, cov = f.fetch_news_covered("sina", "2025-01-27 09:00:00",
                                   "2025-01-27 09:00:59", min_window_seconds=60)
    assert cov["complete"] is False
    assert any(x["status"] == "cap_at_min_window" for x in cov["windows"])


def test_source_whitelist_excludes_cls():
    assert "cls" not in TushareFetcher.NEWS_SOURCES
    assert set(TushareFetcher.NEWS_SOURCES) == {
        "sina", "wallstreetcn", "10jqka", "eastmoney"}


def test_non_whitelisted_source_rejected():
    import pytest
    f = _FakeFetcher(_stream(1))
    # override the fake's fetch_news bypass — call the real whitelist guard
    with pytest.raises(ValueError, match="whitelist"):
        TushareFetcher.fetch_news(f, "cls", "2025-01-27 09:00:00",
                                  "2025-01-27 10:00:00")
