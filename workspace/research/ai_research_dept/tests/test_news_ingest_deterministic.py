# NF wave §7 step 2+3: deterministic core of news_ingest — the PIT-critical parts.
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from workspace.research.ai_research_dept.engine.news_ingest import (  # noqa: E402
    build_cluster_snapshots, coordination_flag, deterministic_prefilter,
    flow_features, market_state_at_publish, no_exchange_session_since_publish,
)


# --------------------------------------------------- session / market state (M2‴)

class TestMarketState:
    @pytest.mark.parametrize("t,expect", [
        ("2025-01-27 10:00:00", "intraday"),
        ("2025-01-27 11:45:00", "intraday"),      # lunch: market has traded today
        ("2025-01-27 12:00:00", "intraday"),
        ("2025-01-27 14:30:00", "intraday"),
        ("2025-01-27 15:30:00", "after_close"),
        ("2025-01-27 09:20:00", "pre_open"),
        ("2025-01-27 08:00:00", "overnight"),
    ])
    def test_open_day_states(self, t, expect):
        assert market_state_at_publish(t, is_open_day=True) == expect

    def test_non_open_day_is_overnight(self):
        assert market_state_at_publish("2025-01-25 10:00:00", is_open_day=False) == "overnight"

    def test_lunch_break_no_session_field_is_separate_from_state(self):
        # market_state_at_publish tags lunch as intraday (traded today), but the
        # PIT-load-bearing field is no_exchange_session_since_publish, which uses
        # actual session intervals — verified in TestNoSessionSincePublish.
        assert market_state_at_publish("2025-01-27 12:00:00", is_open_day=True) == "intraday"


class TestNoSessionSincePublish:
    def _opens(self):
        return {"2025-01-27", "2025-01-28"}

    def test_after_close_flash_no_session_until_next_open(self):
        # published 2025-01-27 16:00 (after close), cutoff 2025-01-27 18:00 same evening
        assert no_exchange_session_since_publish(
            "2025-01-27 16:00:00", "2025-01-27 18:00:00", self._opens()) is True

    def test_intraday_flash_has_had_a_session(self):
        # published 10:00, cutoff same-day 18:00 -> the market traded after publish
        assert no_exchange_session_since_publish(
            "2025-01-27 10:00:00", "2025-01-27 18:00:00", self._opens()) is False

    def test_after_close_then_next_session_before_cutoff(self):
        # published 01-27 16:00, cutoff 01-28 18:00 -> 01-28 session intervened
        assert no_exchange_session_since_publish(
            "2025-01-27 16:00:00", "2025-01-28 18:00:00", self._opens()) is False

    def test_weekend_gap_no_session(self):
        # published Fri after close, cutoff Sun -> no session (no open day between)
        assert no_exchange_session_since_publish(
            "2025-01-24 16:00:00", "2025-01-26 18:00:00",
            {"2025-01-24", "2025-01-27"}) is True


# --------------------------------------------------- prefilter (tout)

class TestPrefilter:
    def test_tout_dropped(self):
        kept, reason = deterministic_prefilter("免费荐股加微信老师带你抓涨停")
        assert not kept and reason.startswith("tout:")

    def test_too_short_dropped(self):
        assert deterministic_prefilter("涨")[0] is False

    def test_normal_flash_kept(self):
        kept, reason = deterministic_prefilter("中芯国际一季度产能利用率85.2%")
        assert kept and reason == ""


# --------------------------------------------------- clusters + source families (B4)

def _members(rows):
    return pd.DataFrame(rows)


class TestClustersAndFamilies:
    def test_same_content_across_sources_one_cluster(self):
        # 4 outlets, same wording, same minute -> 1 cluster, 1 independent source
        v = _members([
            {"src": s, "datetime": "2025-01-27 10:00:00",
             "content": "A公司中标5亿元订单", "decision_visible_at": pd.Timestamp("2025-01-27 10:00:05")}
            for s in ("sina", "eastmoney", "10jqka", "wallstreetcn")])
        snaps = build_cluster_snapshots(v, "2025-01-27 18:00:00")
        assert len(snaps) == 1
        assert snaps[0].n_outlets == 4
        assert snaps[0].n_independent_sources == 1   # syndication collapsed

    def test_distinct_content_distinct_clusters(self):
        v = _members([
            {"src": "sina", "datetime": "2025-01-27 10:00:00", "content": "订单利好",
             "decision_visible_at": pd.Timestamp("2025-01-27 10:00:05")},
            {"src": "sina", "datetime": "2025-01-27 11:00:00", "content": "高管减持",
             "decision_visible_at": pd.Timestamp("2025-01-27 11:00:05")}])
        assert len(build_cluster_snapshots(v, "2025-01-27 18:00:00")) == 2

    def test_coordination_flag_on_syndicated_burst(self):
        v = _members([
            {"src": s, "datetime": "2025-01-27 10:00:00", "content": "拉升在即主力介入",
             "decision_visible_at": pd.Timestamp("2025-01-27 10:00:05")}
            for s in ("sina", "eastmoney", "10jqka")])
        snap = build_cluster_snapshots(v, "2025-01-27 18:00:00")[0]
        assert coordination_flag(snap)["coordination_flag"] is True

    def test_no_coordination_on_single_genuine(self):
        v = _members([{"src": "sina", "datetime": "2025-01-27 10:00:00",
                       "content": "公司公告季报",
                       "decision_visible_at": pd.Timestamp("2025-01-27 10:00:05")}])
        assert coordination_flag(build_cluster_snapshots(v, "2025-01-27 18:00:00")[0]
                                 )["coordination_flag"] is False


# --------------------------------------------------- flow features (E1, as-of)

def _cluster_at(vis_time, content):
    v = pd.DataFrame([{"src": "sina", "datetime": vis_time, "content": content,
                       "decision_visible_at": pd.Timestamp(vis_time)}])
    return build_cluster_snapshots(v, "2025-01-27 18:00:00")[0]


class TestFlowFeaturesAsOf:
    def test_velocity_null_on_zero_baseline(self):
        # zero baseline = NO news in the trailing 480h (20d window empty) -> velocity
        # must be None, NOT a floor. (A cluster today is always in the 20d window, so
        # the genuine zero-baseline case is an entity with no trailing news at all.)
        f = flow_features([], "2025-01-27 18:00:00")
        assert f["flow_velocity"] is None
        assert f["flow_velocity_status"] == "not_applicable_zero_baseline"
        assert f["flow_count_1d"] == 0 and f["flow_count_20d"] == 0

    def test_velocity_null_when_only_old_history(self):
        # only clusters older than 480h -> count_20d == 0 -> velocity None
        old = _cluster_at("2024-12-01 10:00:00", "old")
        f = flow_features([old], "2025-01-27 18:00:00")
        assert f["flow_count_20d"] == 0 and f["flow_velocity"] is None

    def test_velocity_computed_with_history(self):
        clusters = [_cluster_at(f"2025-01-{d:02d} 10:00:00", f"c{d}")
                    for d in range(8, 28)]           # 20 days of history, 1/day
        clusters.append(_cluster_at("2025-01-27 14:00:00", "spike"))  # +1 today
        f = flow_features(clusters, "2025-01-27 18:00:00")
        assert f["flow_velocity"] is not None and f["flow_velocity"] > 0
        assert f["flow_velocity_status"] == "ok"

    def test_flow_is_as_of_cutoff_not_future(self):
        # a cluster first-visible AFTER the cutoff must not count (as-of discipline)
        past = _cluster_at("2025-01-27 10:00:00", "past")
        future = _cluster_at("2025-01-27 20:00:00", "future")  # after 18:00 cutoff
        f = flow_features([past, future], "2025-01-27 18:00:00")
        assert f["flow_count_1d"] == 1               # only the past cluster counts
