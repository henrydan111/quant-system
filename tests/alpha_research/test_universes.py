"""Tests for alpha_research.factor_eval.universes — specs, screens, assembly."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from src.alpha_research.factor_eval import universes as uv  # noqa: E402

DATES = pd.bdate_range("2020-01-01", "2020-03-31")  # ~64 business days
INSTS = ["000001_SZ", "300001_SZ", "600000_SH", "688001_SH"]


def _wide(value=1.0):
    return pd.DataFrame(value, index=DATES, columns=INSTS)


def _panel():
    vol = _wide(1000.0)
    close = _wide(10.0)
    high = _wide(10.5)
    low = _wide(9.8)
    return {"vol": vol, "close": close, "high": high, "low": low}


def _reference(listed=True, st=False, young=False):
    return {
        "listed": _wide(listed).astype(bool),
        "st": _wide(st).astype(bool),
        "young": _wide(young).astype(bool),
    }


class TestScreens:
    def test_suspended_mask_vol_zero_nan_and_close_nan(self):
        panel = _panel()
        panel["vol"].iloc[0, 0] = 0.0
        panel["vol"].iloc[1, 1] = np.nan
        panel["close"].iloc[2, 2] = np.nan
        m = uv.suspended_mask(panel)
        assert m.iloc[0, 0] and m.iloc[1, 1] and m.iloc[2, 2]
        assert m.to_numpy().sum() == 3

    def test_one_word_limit_requires_flat_and_limit(self):
        panel = _panel()
        panel["up_limit"] = _wide(11.0)
        panel["down_limit"] = _wide(9.0)
        # flat at up-limit
        for k in ("high", "low", "close"):
            panel[k].iloc[3, 0] = 11.0
        # flat but NOT at a limit -> not 一字板 when limits provided
        for k in ("high", "low", "close"):
            panel[k].iloc[4, 1] = 10.0
        m = uv.one_word_limit_mask(panel)
        assert m.iloc[3, 0]
        assert not m.iloc[4, 1]
        assert m.to_numpy().sum() == 1

    def test_one_word_limit_without_limit_columns_counts_flat(self):
        panel = _panel()
        for k in ("high", "low", "close"):
            panel[k].iloc[4, 1] = 10.0
        m = uv.one_word_limit_mask(panel)
        assert m.iloc[4, 1]

    def test_suspended_day_not_double_counted_as_limit(self):
        panel = _panel()
        for k in ("high", "low", "close"):
            panel[k].iloc[5, 2] = 10.0
        panel["vol"].iloc[5, 2] = 0.0  # suspended flat day
        assert not uv.one_word_limit_mask(panel).iloc[5, 2]

    def test_cicc_exclusion_combines_all(self):
        panel = _panel()
        ref = _reference()
        ref["st"].iloc[:, 0] = True                       # 000001 always ST
        ref["young"].iloc[:, 1] = True                    # 300001 young
        panel["vol"].iloc[0, 2] = 0.0                     # 600000 suspended day0
        excluded = uv.cicc_exclusion_mask(DATES, INSTS, panel, reference=ref)
        assert excluded["000001_SZ"].all()
        assert excluded["300001_SZ"].all()
        assert excluded.iloc[0, 2] and not excluded.iloc[1, 2]
        assert not excluded["688001_SH"].any()


class TestMonthlyRankBase:
    def test_bottom_rank_refresh_and_carry(self):
        score = _wide()
        # column order of size: 000001 smallest .. 688001 largest, constant over time
        for i, c in enumerate(INSTS):
            score[c] = float(i + 1)
        # in February, invert the ranking so the selection flips at the Feb refresh
        feb = (DATES.month == 2)
        for i, c in enumerate(INSTS):
            score.loc[feb, c] = float(len(INSTS) - i)
        eligible = _wide(True).astype(bool)
        mask = uv.monthly_rank_base(score, 2, "bottom", eligible, DATES)
        jan_end = DATES[DATES.month == 1][-1]
        feb_end = DATES[DATES.month == 2][-1]
        # first day uses day-1 selection (no refresh yet -> current is None -> selects)
        assert mask.loc[DATES[0], "000001_SZ"] and mask.loc[DATES[0], "300001_SZ"]
        # carried through January
        assert mask.loc[jan_end, "000001_SZ"] and mask.loc[jan_end, "300001_SZ"]
        # AFTER the Jan-end refresh (scores still Jan ranking) selection unchanged
        # at the Feb-end refresh the inverted Feb scores flip the selection
        d_after_feb = DATES[DATES > feb_end][0]
        assert mask.loc[d_after_feb, "600000_SH"] and mask.loc[d_after_feb, "688001_SH"]
        assert not mask.loc[d_after_feb, "000001_SZ"]
        # exactly 2 names every day
        assert (mask.sum(axis=1) == 2).all()

    def test_short_population_selects_all(self):
        score = _wide()
        eligible = _wide(False).astype(bool)
        eligible["000001_SZ"] = True
        mask = uv.monthly_rank_base(score, 3, "top", eligible, DATES)
        assert (mask.sum(axis=1) == 1).all()
        assert mask["000001_SZ"].all()

    def test_invalid_side_raises(self):
        with pytest.raises(ValueError):
            uv.monthly_rank_base(_wide(), 2, "middle", _wide(True).astype(bool), DATES)


class TestBuildUniverseMask:
    def test_board_base_growth(self):
        mask = uv.build_universe_mask(
            "univ_growth", DATES, INSTS, _panel(), reference=_reference()
        )
        # spec start_date 2010-06-01 < window, so prefix logic decides
        assert mask["300001_SZ"].all() and mask["688001_SH"].all()
        assert not mask["000001_SZ"].any() and not mask["600000_SH"].any()

    def test_univ_all_is_listed_minus_screens(self):
        ref = _reference()
        ref["st"].iloc[:, 3] = True
        mask = uv.build_universe_mask("univ_all", DATES, INSTS, _panel(), reference=ref)
        assert mask["000001_SZ"].all()
        assert not mask["688001_SH"].any()

    def test_microcap_needs_total_mv(self):
        with pytest.raises(KeyError, match="total_mv"):
            uv.build_universe_mask("univ_microcap", DATES, INSTS, _panel(),
                                   reference=_reference())

    def test_microcap_bottom_selection(self):
        panel = _panel()
        mv = _wide()
        for i, c in enumerate(INSTS):
            mv[c] = float(i + 1)
        panel["total_mv"] = mv
        spec = uv.UNIVERSE_SPECS["univ_microcap"]
        assert spec.base == "mcap_bottom:400"
        # with only 4 names and N=400 it selects all eligible -> equals univ_all
        mask = uv.build_universe_mask("univ_microcap", DATES, INSTS, panel,
                                      reference=_reference())
        assert mask.all().all()

    def test_liquid_top_uses_adv(self):
        panel = _panel()
        amt = _wide()
        for i, c in enumerate(INSTS):
            amt[c] = float(i + 1)
        panel["amount"] = amt
        # with 4 names < 300 the selection is "all eligible". Without warmup history
        # the day-1 immediate selection sees all-NaN ADV20 (min_periods=10) -> empty,
        # carried until the first month-end refresh where ADV20 is defined ->
        # fail-closed False through January, True from Jan-end onward. Callers must
        # include >=20d warmup in panel['amount'] to avoid this.
        mask = uv.build_universe_mask("univ_liquid_top300", DATES, INSTS, panel,
                                      reference=_reference())
        jan_end = DATES[DATES.month == 1][-1]
        assert not mask.loc[mask.index < jan_end].to_numpy().any()
        assert mask.loc[mask.index >= jan_end].all().all()

    def test_start_date_clamp(self):
        snaps = pd.DataFrame({
            "snapshot_date": pd.to_datetime(["2020-01-31"]),
            "instrument": ["000001_SZ"],
        })
        mask = uv.build_universe_mask(
            "univ_csi1000", DATES, INSTS, _panel(),
            reference=_reference(), index_snapshots=snaps,
        )
        # spec.start_date = 2014-11-01 < window start, no clamp effect here; member from snap
        assert mask.loc[DATES[-1], "000001_SZ"]
        # force a clamp: synthetic spec exercise via direct call on csi1000 with
        # window before start_date
        early = pd.bdate_range("2014-01-01", "2014-03-31")
        panel_e = {k: pd.DataFrame(v.iloc[0, 0], index=early, columns=INSTS)
                   for k, v in _panel().items()}
        ref_e = {k: pd.DataFrame(True if k == "listed" else False,
                                 index=early, columns=INSTS) for k in ("listed", "st", "young")}
        m2 = uv.build_universe_mask("univ_csi1000", early, INSTS, panel_e,
                                    reference=ref_e, index_snapshots=snaps)
        assert not m2.to_numpy().any()

    def test_unknown_universe_raises(self):
        with pytest.raises(KeyError, match="unknown universe_id"):
            uv.build_universe_mask("univ_nope", DATES, INSTS, _panel(),
                                   reference=_reference())
