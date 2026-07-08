"""B7/B2 (C8): the canonical converter's output form must MATCH the live
provider's instruments sidecar — a silent case/format drift would make every
join return 0 rows with no error (the classic C8 failure mode)."""
from __future__ import annotations

from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from data_infra.provider_metadata import (  # noqa: E402
    QLIB_CANONICAL_LOWER, ts_code_to_qlib, tushare_to_qlib_canonical,
)

ALL_STOCKS = PROJECT_ROOT / "data" / "qlib_data" / "instruments" / "all_stocks.txt"


def test_wrapper_is_the_sanctioned_ts_code_to_qlib_form():
    assert tushare_to_qlib_canonical("000001.SZ") == ts_code_to_qlib(
        "000001.SZ", lower=QLIB_CANONICAL_LOWER)
    assert tushare_to_qlib_canonical("000001.SZ") == "000001_SZ"
    assert tushare_to_qlib_canonical("600519.SH") == "600519_SH"
    assert tushare_to_qlib_canonical("920001.BJ") == "920001_BJ"


@pytest.mark.skipif(not ALL_STOCKS.exists(), reason="provider instruments not built")
def test_canonical_form_matches_live_instruments_sidecar():
    lines = ALL_STOCKS.read_text(encoding="utf-8").strip().splitlines()
    assert lines, "all_stocks.txt is empty"
    sidecar = {ln.split("\t")[0].strip() for ln in lines}
    # sample well-known permanent names; every one must resolve via the wrapper
    for ts in ("000001.SZ", "600519.SH", "000002.SZ", "601398.SH"):
        assert tushare_to_qlib_canonical(ts) in sidecar, (
            f"{ts} → {tushare_to_qlib_canonical(ts)} not found in instruments "
            f"sidecar — canonical form drifted from the provider (C8)")
