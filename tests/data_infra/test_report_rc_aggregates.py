"""Unit tests for _materialize_report_rc_aggregates (report_rc CONSENSUS + RATING aggregates).

GPT §10 R1->R4 SHIP design. Self-contained: writes synthetic report_rc + income LEDGERS directly to the
builder's ledger paths and drives the materializer with a custom calendar (bypassing the normalize/build
pipeline), capturing _write_feature_series. Covers the FY1 roll/expiry (M2), the latest-per-org median +
missing-value rule (m1), distinct-org counting, and the supersede-on-every-report rating state machine (M4).
"""
from __future__ import annotations
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from data_infra.pit_backend import StagedQlibBackendBuilder   # noqa: E402

CODE = "000001_sz"
CAL = pd.bdate_range("2022-01-03", periods=320)   # 320 business days (> TTL=120) so expiry is reachable
NAN = -999.0


def _pos(ts: str) -> int:
    return int(CAL.searchsorted(pd.Timestamp(ts)))


def _run(rc_rows: list[dict], inc_rows: list[dict] | None = None) -> dict:
    """Write synthetic ledgers, run the materializer, return {field: np.array} (NaN->NAN sentinel)."""
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    b = StagedQlibBackendBuilder(data_root=str(tmp / "data"), qlib_dir=str(tmp / "qlib"),
                                 build_id="t_rrc_agg", allow_exceptions=True)
    rc_path = Path(b.ledger_path("report_rc")); rc_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rc_rows).to_parquet(rc_path, index=False)
    inc_path = Path(b.ledger_path("income")); inc_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(inc_rows or [{"qlib_code": CODE, "end_date": "2099-12-31", "effective_date": "2099-12-31"}]
                 ).to_parquet(inc_path, index=False)
    cap: dict = {}
    b._write_feature_series = lambda fd, fn, arr: cap.__setitem__(fn, np.nan_to_num(
        np.asarray(arr, dtype=float), nan=NAN))
    b._materialize_report_rc_aggregates(CAL, {CODE: str(tmp / "feat")})
    return cap


def _rc(eff: str, quarter: str, *, np_=None, op_rt=None, rating="买入", org="中信证券股份有限公司") -> dict:
    return {"qlib_code": CODE, "effective_date": eff, "quarter": quarter, "np": np_, "op_rt": op_rt,
            "rating": rating, "org_name": org}


# ─────────────────────────── FY1 consensus (A) ───────────────────────────

def test_np_fy1_median_over_orgs_latest_per_org():
    # 3 orgs forecast FY2022 (quarter 2022Q4) np; org A REVISES up (latest wins). No income annual yet ->
    # FY1 = calendar-year(d) = 2022. Median of {A_latest=300, B=100, C=200} = 200 (万元).
    rows = [
        _rc("2022-02-01", "2022Q4", np_=150, org="A证券股份有限公司"),
        _rc("2022-03-01", "2022Q4", np_=300, org="A证券股份有限公司"),  # A revises up -> latest
        _rc("2022-02-10", "2022Q4", np_=100, org="B证券股份有限公司"),
        _rc("2022-02-15", "2022Q4", np_=200, org="C证券股份有限公司"),
    ]
    a = _run(rows)["report_rc__np_fy1"]
    assert a[_pos("2022-03-15")] == pytest.approx(200.0)   # median(300,100,200)


def test_np_fy1_missing_metric_excludes_that_org():
    # m1: an org's LATEST forecast has np=NaN -> excluded from the np median (no fallback to its older finite).
    rows = [
        _rc("2022-02-01", "2022Q4", np_=500, org="A证券股份有限公司"),
        _rc("2022-03-01", "2022Q4", np_=None, org="A证券股份有限公司"),   # A's latest np missing -> A dropped
        _rc("2022-02-10", "2022Q4", np_=100, org="B证券股份有限公司"),
    ]
    a = _run(rows)["report_rc__np_fy1"]
    assert a[_pos("2022-03-15")] == pytest.approx(100.0)   # only B (A excluded), median(100)=100


def test_fy1_rolls_on_annual_disclosure():
    # FY2021 annual discloses 2022-04-20. Two annual forecasts present (both active within TTL at the test
    # dates): 2021Q4 (np=100) and 2022Q4 (np=900). Before the roll -> FY1=2021 (serve 100); after -> FY1=2022.
    rows = [_rc("2022-02-01", "2021Q4", np_=100), _rc("2022-02-01", "2022Q4", np_=900)]
    inc = [{"qlib_code": CODE, "end_date": "2020-12-31", "effective_date": "2021-04-20"},   # FY2020 disclosed
           {"qlib_code": CODE, "end_date": "2021-12-31", "effective_date": "2022-04-20"}]   # FY2021 -> roll
    a = _run(rows, inc)["report_rc__np_fy1"]
    assert a[_pos("2022-03-01")] == pytest.approx(100.0)   # FY2021 not yet disclosed -> FY1=2021
    assert a[_pos("2022-05-10")] == pytest.approx(900.0)   # FY2021 disclosed -> FY1=2022


def test_fy1_non_monotonic_income_uses_max_visible_fy():
    # GPT post-impl Major-1: a DELAYED older annual (FY2020) discloses AFTER FY2021's annual. FY1 must use
    # the MAX fiscal year VISIBLE as-of d (+1), NOT the fiscal-year-ordered last row (a date-unsorted
    # searchsorted picked the wrong FY). FY2021 on time (2022-04-20); FY2020 delayed/restated (2022-06-20).
    rows = [_rc("2022-02-01", "2021Q4", np_=100), _rc("2022-02-01", "2022Q4", np_=900)]
    inc = [{"qlib_code": CODE, "end_date": "2021-12-31", "effective_date": "2022-04-20"},   # FY2021 on time
           {"qlib_code": CODE, "end_date": "2020-12-31", "effective_date": "2022-06-20"}]   # FY2020 DELAYED (later!)
    a = _run(rows, inc)["report_rc__np_fy1"]
    # after the later FY2020 disclosure, max-visible-FY is STILL 2021 -> FY1=2022 -> 900 (NOT pulled back to 100)
    assert a[_pos("2022-07-01")] == pytest.approx(900.0)


def test_fy1_expires_to_nan_after_ttl_with_no_event():
    # M2: a lone forecast at e; with NO later forecast/income event it must go NaN at e+TTL+1 (not served stale).
    e = "2022-02-01"
    a = _run([_rc(e, "2022Q4", np_=777)])["report_rc__np_fy1"]
    p = _pos(e)
    assert a[p] == pytest.approx(777.0)          # active at e
    assert a[p + 120] == pytest.approx(777.0)    # active at e+TTL (inclusive, option-b)
    assert a[p + 121] == NAN                      # expired at e+TTL+1


# ─────────────────────────── n_active_orgs (B) ───────────────────────────

def test_n_active_orgs_counts_distinct_orgs_not_reports():
    # Org A files TWICE (suffix-variant names that normalize equal), org B once -> 2 distinct orgs, not 3.
    rows = [
        _rc("2022-02-01", "2022Q4", np_=1, org="中信证券股份有限公司"),
        _rc("2022-02-05", "2022Q4", np_=1, org="中信证券"),   # normalizes == 中信证券 -> same org
        _rc("2022-02-03", "2022Q4", np_=1, org="华泰证券股份有限公司"),
    ]
    a = _run(rows)["report_rc__n_active_orgs"]
    assert a[_pos("2022-02-10")] == pytest.approx(2.0)
    assert a[_pos("2022-01-04")] == NAN   # NaN before first coverage


# ─────────────────────────── rating state machine (C, M4) ───────────────────────────

def _two(eff1, r1, eff2, r2) -> list[dict]:
    # one org, two reports with ratings r1 then r2 (np present so the org is also FY-active/coverage)
    return [_rc(eff1, "2022Q4", np_=1, rating=r1), _rc(eff2, "2022Q4", np_=1, rating=r2)]


def test_rating_upgrade_sets_up():
    # 增持(4) -> 买入(5) = upgrade. rating_up=1 between the upgrade and its window end.
    a = _run(_two("2022-02-01", "增持", "2022-03-01", "买入"))
    assert a["report_rc__rating_up"][_pos("2022-03-10")] == pytest.approx(1.0)
    assert a["report_rc__rating_dn"][_pos("2022-03-10")] == pytest.approx(0.0)


def test_rating_upgrade_then_downgrade_flips_not_double_counts():
    # 增持->买入 (up) then 买入->减持 (down). After the downgrade: up=0, dn=1 (never both).
    rows = [_rc("2022-02-01", "2022Q4", np_=1, rating="增持"),
            _rc("2022-03-01", "2022Q4", np_=1, rating="买入"),    # upgrade
            _rc("2022-04-01", "2022Q4", np_=1, rating="减持")]    # downgrade (supersedes)
    a = _run(rows)
    assert a["report_rc__rating_up"][_pos("2022-04-10")] == pytest.approx(0.0)
    assert a["report_rc__rating_dn"][_pos("2022-04-10")] == pytest.approx(1.0)


def test_rating_upgrade_then_unknown_clears():
    # M4: upgrade then an UNKNOWN real label -> clears up/dn from that date (coverage stays).
    a = _run(_two("2022-02-01", "增持", "2022-03-01", "买入") +
             [_rc("2022-04-01", "2022Q4", np_=1, rating="关注")])  # 关注 = unknown ordinal, real rating
    assert a["report_rc__rating_up"][_pos("2022-04-10")] == pytest.approx(0.0)
    assert a["report_rc__n_active_orgs"][_pos("2022-04-10")] == pytest.approx(1.0)  # still covered


def test_rating_upgrade_then_no_rating_clears_and_drops_coverage():
    # M4: upgrade then explicit '无' (no rating) -> clears up/dn AND not counted in n_active_orgs at that date.
    a = _run(_two("2022-02-01", "增持", "2022-03-01", "买入") +
             [_rc("2022-04-01", "2022Q4", np_=1, rating="无")])
    assert a["report_rc__rating_up"][_pos("2022-04-10")] == pytest.approx(0.0)
    # '无' report supersedes -> the org has no active REAL rating from 2022-04-01 onward
    assert a["report_rc__n_active_orgs"][_pos("2022-04-10")] == pytest.approx(0.0)


def test_rating_reaffirm_holds_to_original_ttl_not_extended():
    # M4: upgrade at e1, then a REAFFIRM (same rating) at e2 within the window -> the up-state holds only to
    # its ORIGINAL expiry (e1+window+1), NOT extended by the reaffirm.
    rows = [_rc("2022-02-01", "2022Q4", np_=1, rating="增持"),
            _rc("2022-02-15", "2022Q4", np_=1, rating="买入"),    # upgrade at p_up
            _rc("2022-03-01", "2022Q4", np_=1, rating="买入")]    # reaffirm (no extension)
    a = _run(rows)
    p_up = _pos("2022-02-15")
    assert a["report_rc__rating_up"][p_up + 120] == pytest.approx(1.0)   # still up at original e+window
    assert a["report_rc__rating_up"][p_up + 121] == pytest.approx(0.0)   # expires at original window, not extended
