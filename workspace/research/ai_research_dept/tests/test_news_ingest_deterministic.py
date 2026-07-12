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
    def test_same_wording_across_sources_one_family(self):
        # 4 outlets, same wording -> 1 cluster (source-family), 4 outlets
        v = _members([
            {"src": s, "datetime": "2025-01-27 10:00:00",
             "content": "A公司中标5亿元订单", "decision_visible_at": pd.Timestamp("2025-01-27 10:00:05")}
            for s in ("sina", "eastmoney", "10jqka", "wallstreetcn")])
        snaps = build_cluster_snapshots(v, "2025-01-27 18:00:00")
        assert len(snaps) == 1 and snaps[0].n_outlets == 4

    def test_staggered_reposts_one_family_not_inflated(self):
        # review M2: same wording at 10:00/10:01/10:02 -> ONE family (not 3),
        # regardless of the exact minute
        v = _members([
            {"src": "sina", "datetime": f"2025-01-27 10:0{m}:00", "content": "同一措辞X",
             "decision_visible_at": pd.Timestamp(f"2025-01-27 10:0{m}:05")}
            for m in range(3)])
        snaps = build_cluster_snapshots(v, "2025-01-27 18:00:00")
        assert len(snaps) == 1                       # one family, minute ignored

    def test_immutable_snapshot_frozen_and_content_bound_id(self):
        v = _members([{"src": "sina", "datetime": "2025-01-27 10:00:00",
                       "content": "订单利好", "decision_visible_at": pd.Timestamp("2025-01-27 10:00:05")}])
        s = build_cluster_snapshots(v, "2025-01-27 18:00:00")[0]
        with pytest.raises(Exception):
            s.n_outlets = 99                          # frozen
        assert len(s.snapshot_id) == 24               # full-payload SHA-256

    def test_build_rejects_future_member(self):
        # review B2: a member with effective_at > cutoff HARD-FAILS (no silent keep)
        v = _members([{"src": "sina", "datetime": "2025-01-27 20:00:00", "content": "future",
                       "decision_visible_at": pd.Timestamp("2025-01-27 20:00:00")}])
        with pytest.raises(ValueError, match="cutoff"):
            build_cluster_snapshots(v, "2025-01-27 18:00:00")

    def test_coordination_only_when_confirmed_absent_backing(self):
        v = _members([
            {"src": s, "datetime": "2025-01-27 10:00:00", "content": "拉升在即主力介入",
             "decision_visible_at": pd.Timestamp("2025-01-27 10:00:05")}
            for s in ("sina", "eastmoney", "10jqka")])
        snap = build_cluster_snapshots(v, "2025-01-27 18:00:00")[0]
        # only fires with confirmed_absent structured backing
        assert coordination_flag(snap, structured_backing_status="confirmed_absent"
                                 )["coordination_flag"] is True
        assert coordination_flag(snap, structured_backing_status="coverage_incomplete"
                                 )["coordination_flag"] is False
        assert coordination_flag(snap, structured_backing_status="present"
                                 )["coordination_flag"] is False


# --------------------------------------------------- flow features (E1, as-of)

def _cluster_at(vis_time, content, cutoff="2025-01-27 18:00:00"):
    v = pd.DataFrame([{"src": "sina", "datetime": vis_time, "content": content,
                       "decision_visible_at": pd.Timestamp(vis_time)}])
    return build_cluster_snapshots(v, cutoff)[0]


class TestFlowFeaturesAsOf:
    def test_velocity_null_on_zero_baseline(self):
        f = flow_features([], "2025-01-27 18:00:00")
        assert f["flow_velocity"] is None
        assert f["flow_velocity_status"] == "not_applicable_zero_baseline"
        assert f["flow_count_1d"] == 0 and f["flow_count_20d"] == 0

    def test_velocity_null_when_only_old_history(self):
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

    def test_incomplete_coverage_all_not_applicable(self):
        # review M2: incomplete required-source coverage -> flow null, not silent data
        f = flow_features([_cluster_at("2025-01-27 10:00:00", "x")],
                          "2025-01-27 18:00:00", coverage_complete=False)
        assert f["flow_count_1d"] is None
        assert f["flow_velocity_status"] == "not_applicable_incomplete_coverage"

    def test_breadth_is_outlet_union_not_sum(self):
        # two same-day clusters, one carried by {sina}, one by {sina, eastmoney}
        # -> breadth = |{sina, eastmoney}| = 2 (union), not 1+2=3
        v1 = pd.DataFrame([{"src": "sina", "datetime": "2025-01-27 10:00:00",
                            "content": "事实甲", "decision_visible_at": pd.Timestamp("2025-01-27 10:00:05")}])
        v2 = pd.DataFrame([
            {"src": s, "datetime": "2025-01-27 11:00:00", "content": "事实乙",
             "decision_visible_at": pd.Timestamp("2025-01-27 11:00:05")}
            for s in ("sina", "eastmoney")])
        c1 = build_cluster_snapshots(v1, "2025-01-27 18:00:00")[0]
        c2 = build_cluster_snapshots(v2, "2025-01-27 18:00:00")[0]
        f = flow_features([c1, c2], "2025-01-27 18:00:00")
        assert f["coverage_breadth_1d"] == 2


# --------------------------------------------------- LLM three-dim typing (fail-closed enum)

from workspace.research.ai_research_dept.engine.news_ingest import (  # noqa: E402
    CONTENT_KIND, EVENT_TYPES, MACRO_TYPES, TypingSchemaError,
    VERIFICATION_STATUS, type_batch,
)


class _Reply:
    def __init__(self, text):
        self.text = text


def _mock_call(results):
    import json as _json
    return lambda msgs: _Reply(_json.dumps({"results": results}, ensure_ascii=False))


class TestTypingFailClosed:
    def test_valid_enums_pass_through(self):
        out = type_batch([{"idx": 0, "content": "x"}], _mock_call([
            {"idx": 0, "event_type": "订单合同", "verification_status": "官方证实",
             "content_kind": "事实", "direction": "利好", "is_rumor": False}]))
        r = out[0]
        assert r["event_type"] == "订单合同" and r["verification_status"] == "官方证实"
        assert r["content_kind"] == "事实" and r["direction"] == "利好"
        assert r["is_rumor"] is False

    def test_unregistered_enum_coerced_to_conservative_default(self):
        out = type_batch([{"idx": 0, "content": "x"}], _mock_call([
            {"idx": 0, "event_type": "ARBITRARY_EVIL", "verification_status": "hacked",
             "content_kind": "???", "direction": "定涨停", "is_rumor": "false"}]))
        r = out[0]
        assert r["event_type"] == "市场评论"
        assert r["verification_status"] == "未证实"
        assert r["content_kind"] == "评论"
        assert r["direction"] == "中性"
        # review M4: is_rumor="false" is NOT a literal bool -> conservative True
        # (never silently True from a truthy string, never silently passed through)
        assert r["is_rumor"] is True

    def test_string_false_is_not_true_passthrough(self):
        # a literal-bool false stays false; only non-bool coerces to conservative True
        out = type_batch([{"idx": 0, "content": "x"}], _mock_call([
            {"idx": 0, "is_rumor": False}]))
        assert out[0]["is_rumor"] is False

    def test_duplicate_idx_hard_fails(self):
        with pytest.raises(TypingSchemaError, match="duplicate"):
            type_batch([{"idx": 0, "content": "x"}], _mock_call([
                {"idx": 0}, {"idx": 0}]))

    def test_missing_idx_hard_fails(self):
        with pytest.raises(TypingSchemaError, match="missing"):
            type_batch([{"idx": 0, "content": "a"}, {"idx": 1, "content": "b"}],
                       _mock_call([{"idx": 0}]))     # idx 1 missing

    def test_output_sorted_by_input_order(self):
        out = type_batch([{"idx": 5, "content": "a"}, {"idx": 2, "content": "b"}],
                         _mock_call([{"idx": 2}, {"idx": 5}]))
        assert [r["idx"] for r in out] == [5, 2]

    def test_macro_type_valid(self):
        out = type_batch([{"idx": 0, "content": "央行逆回购"}], _mock_call([
            {"idx": 0, "event_type": "政策转述", "macro_type": "货币政策"}]), macro=True)
        assert out[0]["macro_type"] == "货币政策" and out[0]["macro_type_status"] == "ok"

    def test_macro_type_missing_is_not_applicable_not_real_dim(self):
        # review M4: missing macro_type must be not_applicable, NEVER default to 行业景气
        out = type_batch([{"idx": 0, "content": "x"}], _mock_call([
            {"idx": 0, "event_type": "政策转述"}]), macro=True)
        assert out[0]["macro_type"] is None
        assert out[0]["macro_type_status"] == "not_applicable"
        assert "行业景气" in MACRO_TYPES     # it IS a real dim -> must not be the default

    def test_no_macro_type_when_not_macro(self):
        out = type_batch([{"idx": 0, "content": "x"}], _mock_call([
            {"idx": 0, "event_type": "公司经营"}]), macro=False)
        assert "macro_type" not in out[0]
