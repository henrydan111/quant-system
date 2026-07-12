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


def test_uncapped_window_single_manifest_entry():
    f = _FakeFetcher(_stream(100))
    df, man = f.fetch_news_covered("sina", "2025-01-27 09:00:00",
                                   "2025-01-27 10:00:00")
    assert len(df) == 100
    assert len(man) == 1 and man[0]["status"] == "ok" and not man[0]["cap_hit"]


def test_capped_window_splits_and_covers_all():
    # 3000 flashes over an hour → exceeds the 1500 cap → must split and recover all
    f = _FakeFetcher(_stream(3000, step_s=1))   # 3000s ≈ 50 min
    df, man = f.fetch_news_covered("sina", "2025-01-27 09:00:00",
                                   "2025-01-27 10:00:00")
    assert len(df) == 3000                       # no flash lost
    assert df["title"].is_unique                  # overlap dedup worked
    assert len(man) > 1                           # actually split
    assert any(m["cap_hit"] for m in man)         # split parent recorded
    assert any(m["status"] == "split" for m in man)
    assert all(m["status"] in ("ok", "split", "cap_at_min_window") for m in man)
    # every leaf (ok/cap_at_min) is a real coverage window
    assert any(m["status"] == "ok" for m in man)


def test_dedup_absorbs_boundary_overlap():
    f = _FakeFetcher(_stream(3000, step_s=1))
    df, _ = f.fetch_news_covered("sina", "2025-01-27 09:00:00",
                                 "2025-01-27 10:00:00")
    # per-source identity is src+datetime+content → the +1s right-half overlap
    # must not double-count any row
    key = df["src"] + "|" + df["datetime"] + "|" + df["content"]
    assert key.is_unique


def test_cap_at_min_window_is_flagged_not_silent():
    # 2000 flashes inside a single 60s window → cannot split below min → must be
    # RECORDED as cap_at_min_window, never silently accepted as complete
    burst = [(f"2025-01-27 09:00:{s % 60:02d}", f"b-{i}")
             for i, s in enumerate(range(2000))]
    f = _FakeFetcher(burst)
    df, man = f.fetch_news_covered("sina", "2025-01-27 09:00:00",
                                   "2025-01-27 09:00:59", min_window_seconds=60)
    assert any(m["status"] == "cap_at_min_window" for m in man)


def test_source_whitelist_excludes_cls():
    assert "cls" not in TushareFetcher.NEWS_SOURCES
    assert set(TushareFetcher.NEWS_SOURCES) == {
        "sina", "wallstreetcn", "10jqka", "eastmoney"}
