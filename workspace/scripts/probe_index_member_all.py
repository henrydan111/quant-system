"""A0 — Live Tushare endpoint verification for SW2021 historical membership.

Plan ref: C:\\Users\\henry\\.claude\\plans\\vast-exploring-rabbit.md (v8)

This is the mandatory pre-flight gate. Probes pro.index_member_all with both
candidate parameter names (l1_code= and index_code=) on the 银行 (801780.SI)
sector. Either branch must pass the same 4-criterion validation before the
plan can advance to A1 fetcher implementation.

Pass criteria (ALL must hold):
  1. >= 30 rows returned
  2. Columns include exactly: ts_code, in_date, out_date, is_new
  3. At least 1 row with in_date <= '20080101' (proof of pre-2008 history)
  4. At least 1 row with is_new == 'N' (proof of historical/time-varying)

Delete this file after A0 passes.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd  # noqa: E402

from src.data_infra.fetchers import TushareFetcher  # noqa: E402


def _validate(df, label: str) -> bool:
    """Run the full 4-criterion gate. Returns True iff all pass."""
    if df is None or df.empty:
        print(f"{label}: FAIL — empty")
        return False
    print(f"{label}: shape={df.shape}, cols={list(df.columns)}")
    print(df.head(3).to_string())

    has_min_rows = len(df) >= 30
    has_ts = "ts_code" in df.columns
    has_in = "in_date" in df.columns
    has_out = "out_date" in df.columns
    has_isnew = "is_new" in df.columns
    has_required_cols = has_ts and has_in and has_out

    has_pre_2008 = False
    if has_in:
        try:
            min_in = df["in_date"].min()
            max_in = df["in_date"].max()
            pre_2008_count = int((df["in_date"].astype(str) <= "20080101").sum())
            has_pre_2008 = pre_2008_count >= 1
            print(
                f"min in_date: {min_in}, max in_date: {max_in}, "
                f"pre-2008 rows: {pre_2008_count}"
            )
        except Exception as e:
            print(f"  in_date introspection failed: {e}")

    has_historical = False
    if has_isnew:
        is_new_counts = df["is_new"].value_counts().to_dict()
        has_historical = is_new_counts.get("N", 0) >= 1
        print(f"is_new value counts: {is_new_counts}")

    pass_criteria = (
        has_min_rows and has_required_cols and has_pre_2008 and has_historical
    )
    print(
        f"{label}: rows>=30={has_min_rows}, cols={has_required_cols}, "
        f"pre_2008={has_pre_2008}, historical={has_historical}, "
        f"gate_pass={pass_criteria}"
    )
    return pass_criteria


def main() -> int:
    f = TushareFetcher(
        config_path=str(PROJECT_ROOT / "config.yaml"), base_sleep=1.5
    )

    # Probe signature 1: l1_code=
    ok = False
    try:
        df = f._safe_api_call(f.pro.index_member_all, l1_code="801780.SI")
        ok = _validate(df, "l1_code=")
    except Exception as e:
        print(f"l1_code= FAILED: {e}")

    # Probe signature 2: index_code= (always run so we know which works)
    ok2 = False
    try:
        df2 = f._safe_api_call(f.pro.index_member_all, index_code="801780.SI")
        ok2 = _validate(df2, "index_code=")
        if not ok and ok2:
            print("USE index_code= IN A1 WRAPPER")
    except Exception as e2:
        print(f"index_code= FAILED: {e2}")

    if not (ok or locals().get("ok2", False)):
        print(
            "BOTH SIGNATURES FAILED VALIDATION — endpoint, VIP access, "
            "or scope issue; STOP plan execution."
        )
        return 1

    print("A0 PASSED — proceed to A1.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
