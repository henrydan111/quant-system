# NF wave: deterministic core of news_ingest (FIX-FIRST full-seal rebuild).
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from workspace.research.ai_research_dept.engine.news_ingest import (  # noqa: E402
    CONTENT_KIND, EVENT_TYPES, MACRO_TYPES, SessionInputError, TypingSchemaError,
    VERIFICATION_STATUS, build_cluster_snapshots, build_coverage_artifact,
    coordination_flag, deterministic_prefilter, flow_features,
    market_state_at_publish, no_exchange_session_since_publish, type_batch,
)
from workspace.research.ai_research_dept.engine.news_seal import SealError  # noqa: E402


# ---- provenance stamping mimicking text_store output (build requires full cols) ----
def _stamp(rows, ingest_class="forward"):
    df = pd.DataFrame(rows)
    if "source_published_at" not in df:
        df["source_published_at"] = pd.to_datetime(df["datetime"])
    if "first_ingested_at" not in df:
        df["first_ingested_at"] = pd.to_datetime(df["datetime"]) + pd.Timedelta(minutes=1)
    df["decision_visible_at"] = df[["source_published_at", "first_ingested_at"]].max(axis=1)
    # object_id/content hashes are DETERMINISTIC functions of content (as text_store
    # computes them), never row position — so permutation-invariance holds
    df["object_id_hash"] = df.apply(
        lambda r: "obj:" + str(r["src"]) + "|" + str(r["datetime"]) + "|" + str(r["content"]),
        axis=1)
    df["content_hash"] = df["content"].map(lambda c: "ch:" + str(c))
    df["ingest_class"] = ingest_class
    return df


def _cov(complete=True):
    return build_coverage_artifact(
        {"src": "sina", "start": "2025-01-27 00:00:00", "end": "2025-01-27 18:00:00",
         "complete": complete, "windows": []},
        watermark_before=None, watermark_after=None, population_hash="pop1")


# --------------------------------------------------- session / market state

class TestMarketState:
    @pytest.mark.parametrize("t,expect", [
        ("2025-01-27 10:00:00", "intraday"), ("2025-01-27 12:00:00", "intraday"),
        ("2025-01-27 15:30:00", "after_close"), ("2025-01-27 09:20:00", "pre_open"),
        ("2025-01-27 08:00:00", "overnight"),
    ])
    def test_open_day_states(self, t, expect):
        assert market_state_at_publish(t, is_open_day=True) == expect

    def test_non_open_day_overnight(self):
        assert market_state_at_publish("2025-01-25 10:00:00", is_open_day=False) == "overnight"


class TestNoSession:
    def _opens(self):
        return {"2025-01-27", "2025-01-28"}

    def test_after_close_no_session(self):
        assert no_exchange_session_since_publish(
            "2025-01-27 16:00:00", "2025-01-27 18:00:00", self._opens()) is True

    def test_intraday_had_session(self):
        assert no_exchange_session_since_publish(
            "2025-01-27 10:00:00", "2025-01-27 18:00:00", self._opens()) is False

    def test_published_after_cutoff_raises(self):
        # review M3: not silent no-session
        with pytest.raises(SessionInputError):
            no_exchange_session_since_publish("2025-01-27 19:00:00",
                                              "2025-01-27 18:00:00", self._opens())

    def test_tz_aware_input_no_typeerror(self):
        # review M3: tz-aware publication must not raise TypeError
        assert isinstance(no_exchange_session_since_publish(
            pd.Timestamp("2025-01-27 16:00:00+08:00"), "2025-01-27 18:00:00",
            self._opens()), bool)

    def test_intraday_intervals_suspension(self):
        # review M3: morning-suspended, afternoon-tradable -> a session existed only
        # in the afternoon; a flash at 10:00 (during suspension) with cutoff 12:00
        # (before pm open) had NO tradable session
        intervals = [("2025-01-27 09:30:00", "2025-01-27 11:30:00", "suspended"),
                     ("2025-01-27 13:00:00", "2025-01-27 15:00:00", "tradable")]
        assert no_exchange_session_since_publish(
            "2025-01-27 10:00:00", "2025-01-27 12:00:00", self._opens(),
            target_intervals=intervals) is True
        # cutoff after the afternoon session -> a tradable session intervened
        assert no_exchange_session_since_publish(
            "2025-01-27 10:00:00", "2025-01-27 14:00:00", self._opens(),
            target_intervals=intervals) is False


class TestPrefilter:
    def test_tout_dropped(self):
        assert deterministic_prefilter("免费荐股加微信老师带你抓涨停")[0] is False

    def test_normal_kept(self):
        assert deterministic_prefilter("中芯国际一季度产能利用率85.2%")[0] is True


# --------------------------------------------------- immutable clusters (B2)

class TestClusters:
    def test_staggered_reposts_one_family(self):
        v = _stamp([{"src": "sina", "datetime": f"2025-01-27 10:0{m}:00", "content": "同一措辞X"}
                    for m in range(3)])
        assert len(build_cluster_snapshots(v, "2025-01-27 18:00:00")) == 1

    def test_frozen_and_full_sha256_id(self):
        v = _stamp([{"src": "sina", "datetime": "2025-01-27 10:00:00", "content": "订单利好"}])
        s = build_cluster_snapshots(v, "2025-01-27 18:00:00")[0]
        with pytest.raises(Exception):
            s.n_outlets = 99
        assert len(s.snapshot_id) == 64            # FULL sha256 (review B2)

    def test_tail_collision_distinct_ids(self):
        # review B2: same first-120 chars, different tail -> DIFFERENT snapshot IDs
        # (member carries the full content_hash, not the truncated fingerprint)
        base = "字" * 120
        v1 = _stamp([{"src": "sina", "datetime": "2025-01-27 10:00:00", "content": base + "A"}])
        v2 = _stamp([{"src": "sina", "datetime": "2025-01-27 10:00:00", "content": base + "B"}])
        s1 = build_cluster_snapshots(v1, "2025-01-27 18:00:00")[0]
        s2 = build_cluster_snapshots(v2, "2025-01-27 18:00:00")[0]
        assert s1.snapshot_id != s2.snapshot_id

    def test_reject_future_member(self):
        v = _stamp([{"src": "sina", "datetime": "2025-01-27 20:00:00", "content": "future"}])
        with pytest.raises(ValueError, match="cutoff"):
            build_cluster_snapshots(v, "2025-01-27 18:00:00")

    def test_reject_nat_effective(self):
        v = _stamp([{"src": "sina", "datetime": "2025-01-27 10:00:00", "content": "x"}])
        v["source_published_at"] = pd.NaT
        v["first_ingested_at"] = pd.NaT
        with pytest.raises(ValueError, match="NaT"):
            build_cluster_snapshots(v, "2025-01-27 18:00:00")

    def test_equal_time_permutation_same_id(self):
        # review B2: equal effective-time members in any input order -> same ID
        rows = [{"src": "a", "datetime": "2025-01-27 10:00:00", "content": "同措辞"},
                {"src": "b", "datetime": "2025-01-27 10:00:00", "content": "同措辞"}]
        s1 = build_cluster_snapshots(_stamp(rows), "2025-01-27 18:00:00")[0]
        s2 = build_cluster_snapshots(_stamp(rows[::-1]), "2025-01-27 18:00:00")[0]
        assert s1.snapshot_id == s2.snapshot_id

    def test_forged_snapshot_id_rejected(self):
        v = _stamp([{"src": "sina", "datetime": "2025-01-27 10:00:00", "content": "x"}])
        s = build_cluster_snapshots(v, "2025-01-27 18:00:00")[0]
        from workspace.research.ai_research_dept.engine.news_ingest import ClusterSnapshot
        with pytest.raises(SealError):
            ClusterSnapshot(cluster_id=s.cluster_id, algo_version=s.algo_version,
                            cutoff_iso=s.cutoff_iso, members=s.members,
                            fact_occurrence_id=s.fact_occurrence_id,
                            cluster_first_visible_at_iso=s.cluster_first_visible_at_iso,
                            n_outlets=s.n_outlets, snapshot_id="0" * 64)

    def test_coordination_only_confirmed_absent(self):
        v = _stamp([{"src": s, "datetime": "2025-01-27 10:00:00", "content": "拉升在即主力介入"}
                    for s in ("sina", "eastmoney", "10jqka")])
        snap = build_cluster_snapshots(v, "2025-01-27 18:00:00")[0]
        assert coordination_flag(snap, structured_backing_status="confirmed_absent"
                                 )["coordination_flag"] is True
        assert coordination_flag(snap, structured_backing_status="present"
                                 )["coordination_flag"] is False


# --------------------------------------------------- flow features (M1/M2)

def _cluster_at(vis_time, content, cutoff="2025-01-27 18:00:00"):
    return build_cluster_snapshots(
        _stamp([{"src": "sina", "datetime": vis_time, "content": content}]), cutoff)[0]


class TestFlow:
    def test_requires_sealed_complete_coverage(self):
        f = flow_features([_cluster_at("2025-01-27 10:00:00", "x")],
                          "2025-01-27 18:00:00", coverage=_cov(complete=False))
        assert f["flow_count_1d"] is None
        assert f["flow_velocity_status"] == "not_applicable_incomplete_coverage"

    def test_bare_true_rejected(self):
        # passing a bare truthy (not the sealed artifact) must be treated as incomplete
        f = flow_features([_cluster_at("2025-01-27 10:00:00", "x")],
                          "2025-01-27 18:00:00", coverage=True)
        assert f["flow_count_1d"] is None

    def test_velocity_null_on_zero_baseline(self):
        f = flow_features([], "2025-01-27 18:00:00", coverage=_cov())
        assert f["flow_velocity"] is None
        assert f["flow_velocity_status"] == "not_applicable_zero_baseline"

    def test_reappearance_new_day_counts(self):
        # review M2: same wording weeks apart -> distinct fact occurrences (family x day)
        old = _cluster_at("2025-01-06 10:00:00", "重复公告文")   # ~21 days before
        new = _cluster_at("2025-01-27 10:00:00", "重复公告文")   # today
        f = flow_features([old, new], "2025-01-27 18:00:00", coverage=_cov())
        assert f["flow_count_1d"] == 1            # today's occurrence counted (was 0)
        assert f["flow_count_20d"] >= 1

    def test_breadth_is_unique_source_families(self):
        # two distinct wordings today -> breadth 2 (unique families)
        c1 = _cluster_at("2025-01-27 10:00:00", "措辞甲")
        c2 = _cluster_at("2025-01-27 11:00:00", "措辞乙")
        f = flow_features([c1, c2], "2025-01-27 18:00:00", coverage=_cov())
        assert f["coverage_breadth_1d"] == 2


# --------------------------------------------------- coverage artifact (M1)

class TestCoverageArtifact:
    def test_complete_is_confirmed_absent(self):
        a = _cov(complete=True)
        assert a.availability_state == "confirmed_absent" and len(a.coverage_hash) == 64

    def test_incomplete_state(self):
        assert _cov(complete=False).availability_state == "coverage_incomplete"

    def test_source_unavailable(self):
        a = build_coverage_artifact(
            {"src": "cls", "start": "s", "end": "e", "complete": True, "windows": []},
            watermark_before=None, watermark_after=None, population_hash="p",
            source_available=False)
        assert a.availability_state == "source_unavailable" and a.complete is False

    def test_watermark_cannot_advance_when_incomplete(self):
        with pytest.raises(ValueError, match="watermark"):
            build_coverage_artifact(
                {"src": "sina", "start": "s", "end": "e", "complete": False, "windows": []},
                watermark_before="w0", watermark_after="w1", population_hash="p")

    def test_forged_coverage_hash_rejected(self):
        a = _cov()
        from workspace.research.ai_research_dept.engine.news_ingest import NewsCoverageArtifact
        with pytest.raises(SealError):
            NewsCoverageArtifact(src=a.src, start=a.start, end=a.end, complete=a.complete,
                                 availability_state=a.availability_state, windows=a.windows,
                                 watermark_before=a.watermark_before,
                                 watermark_after=a.watermark_after,
                                 population_hash=a.population_hash, coverage_hash="0" * 64)


# --------------------------------------------------- typing strictness (M4)

class _Reply:
    def __init__(self, text):
        self.text = text


def _mock(results):
    import json as _json
    return lambda msgs: _Reply(_json.dumps({"results": results}, ensure_ascii=False))


class TestTyping:
    def test_valid_passthrough(self):
        out = type_batch([{"idx": 0, "content": "x"}], _mock([
            {"idx": 0, "event_type": "订单合同", "verification_status": "官方证实",
             "content_kind": "事实", "direction": "利好", "is_rumor": False}]))
        assert out[0]["event_type"] == "订单合同" and out[0]["is_rumor"] is False

    def test_unregistered_enum_coerced(self):
        out = type_batch([{"idx": 0, "content": "x"}], _mock([
            {"idx": 0, "event_type": "EVIL", "verification_status": "hacked",
             "content_kind": "?", "direction": "定涨停", "is_rumor": "false"}]))
        r = out[0]
        assert r["event_type"] == "市场评论" and r["verification_status"] == "未证实"
        assert r["is_rumor"] is True              # "false" not a literal bool -> True

    def test_bool_response_idx_not_matching_int(self):
        # review M4: a bool response idx must NOT satisfy an int request (True==1)
        with pytest.raises(TypingSchemaError, match="missing"):
            type_batch([{"idx": 1, "content": "x"}], _mock([{"idx": True}]))

    def test_duplicate_requested_idx_hard_fails(self):
        with pytest.raises(TypingSchemaError, match="duplicate requested"):
            type_batch([{"idx": 0, "content": "a"}, {"idx": 0, "content": "b"}],
                       _mock([{"idx": 0}]))

    def test_bool_requested_idx_rejected(self):
        with pytest.raises(TypingSchemaError, match="non-bool int"):
            type_batch([{"idx": True, "content": "x"}], _mock([{"idx": True}]))

    def test_missing_result_hard_fails(self):
        with pytest.raises(TypingSchemaError, match="missing"):
            type_batch([{"idx": 0, "content": "a"}, {"idx": 1, "content": "b"}],
                       _mock([{"idx": 0}]))

    def test_output_sorted_by_input(self):
        out = type_batch([{"idx": 5, "content": "a"}, {"idx": 2, "content": "b"}],
                         _mock([{"idx": 2}, {"idx": 5}]))
        assert [r["idx"] for r in out] == [5, 2]

    def test_macro_missing_not_applicable(self):
        out = type_batch([{"idx": 0, "content": "x"}], _mock([
            {"idx": 0, "event_type": "政策转述"}]), macro=True)
        assert out[0]["macro_type"] is None and out[0]["macro_type_status"] == "not_applicable"
        assert "行业景气" in MACRO_TYPES
