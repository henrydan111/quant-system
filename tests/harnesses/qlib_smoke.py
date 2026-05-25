"""Small live-provider smoke test for the local Qlib backend."""

from __future__ import annotations

import os

import numpy as np
import qlib
from qlib.config import REG_CN
from qlib.data import D


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PROVIDER_URI = os.path.join(PROJECT_ROOT, "data", "qlib_data")


def test_qlib() -> None:
    print(f"Initializing Qlib from: {PROVIDER_URI}")
    qlib.init(provider_uri=PROVIDER_URI, region=REG_CN, kernels=1)
    print("Qlib successfully initialized.")

    universe = D.instruments(market="all")
    instruments_list = D.list_instruments(
        instruments=universe,
        start_time="2020-01-01",
        end_time="2025-12-31",
        as_list=True,
    )
    print(f"Found {len(instruments_list)} instruments in 'all'.")

    fields = [
        "$close",
        "$roe",
        "$roe_q0",
        "$revenue_q",
        "$revenue_sq_q0",
        "$q_roe",
        "$pit_or_yoy",
    ]
    names = ["close", "roe", "roe_q0", "revenue_q", "revenue_sq_q0", "q_roe", "pit_or_yoy"]
    test_universe = ["000001_SZ", "600519_SH", "688981_SH"]
    start_time = "2024-05-10"
    end_time = "2024-05-10"

    df = D.features(test_universe, fields, start_time=start_time, end_time=end_time, freq="day")
    df.columns = names
    print("\nSample rows:")
    print(df.dropna(how="all").to_string())

    alias_pair = df[["revenue_q", "revenue_sq_q0"]].dropna()
    if alias_pair.empty:
        print("\nNo overlapping rows for revenue_q parity check.")
    else:
        equal_mask = np.isclose(
            alias_pair["revenue_q"].to_numpy(),
            alias_pair["revenue_sq_q0"].to_numpy(),
            rtol=1e-6,
            atol=1e-6,
            equal_nan=True,
        )
        print(
            f"\nrevenue_q parity: {int(equal_mask.sum())}/{len(alias_pair)} exact matches "
            f"({equal_mask.mean():.2%})"
        )


if __name__ == "__main__":
    test_qlib()
