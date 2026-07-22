# -*- coding: utf-8 -*-
"""The ONE canonical per-date 3-leg daily merge (daily + daily_basic + adj_factor).

Why this module exists (adapter design v4, F9 rider): the raw-store recovery must reconstruct
`market/daily` files that are indistinguishable from what the daily pipeline writes going forward. Two
independent merge implementations — one in `pipeline/update_daily_data.py`, one in the recovery
adapters — is exactly the shape that lets recovered history and live history drift apart silently. Both
callers now call this function.

Consolidating them surfaced a real gap rather than a formality: **each side had a check the other
lacked.** Production validated that the daily_basic PAYLOAD survived the merge (a wrong-date or
mis-keyed aux frame merges to all-NULL even at 100% code overlap, so a code-coverage check alone
passes it) and that adj_factor was non-null afterwards; the recovery merger had neither, so a silently
empty daily_basic would have been written into the recovered store. The recovery merger in turn had
`validate="one_to_one"`, a per-leg wrong-date scan, and row-count preservation, none of which
production had. This function is the UNION — every check from both sides — so neither caller can be
weaker than the other again.

Pure: no I/O, no mutation of the inputs.
"""
from __future__ import annotations

import pandas as pd

#: subclasses RuntimeError so the recovery callers' existing `pytest.raises(RuntimeError)` still holds
class DailyMergeError(RuntimeError):
    """A leg is missing, mis-dated, mis-keyed, or did not survive the merge."""


#: daily's own `close` is canonical — daily_basic's copy is auxiliary and must not shadow it.
#: `raw_fetch_ts` is a recovery-side page stamp present on every leg; keeping all three would collide.
_AUX_DROP_ALWAYS = ("raw_fetch_ts",)
_AUX_DROP_BASIC = ("close",)

MIN_BASIC_CODE_COVERAGE = 0.90
MIN_BASIC_PAYLOAD_COVERAGE = 0.90


def merge_daily_legs(df_daily, df_basic, df_adj, target_date: str):
    """Merge the three legs for `target_date` and return the canonical frame.

    Raises `DailyMergeError` on any violation; callers that owe a different exception type to their own
    contract should catch and re-raise.
    """
    target_date = str(target_date)

    # ── 1. every leg must be present ────────────────────────────────────────────────────────────
    if df_daily is None or not len(df_daily):
        raise DailyMergeError(f"market {target_date}: daily leg EMPTY — a dense per-date merge needs it")
    if df_adj is None or not len(df_adj):
        raise DailyMergeError(f"market {target_date}: adj_factor EMPTY (required leg)")
    if df_basic is None or not len(df_basic):
        raise DailyMergeError(f"market {target_date}: daily_basic EMPTY (required leg)")

    # ── 2. no leg may carry another date's rows ─────────────────────────────────────────────────
    for name, df in (("daily", df_daily), ("daily_basic", df_basic), ("adj_factor", df_adj)):
        if "trade_date" not in df.columns:
            raise DailyMergeError(f"market {target_date}: {name} leg has no trade_date column")
        bad = df[df["trade_date"].astype(str) != target_date]
        if len(bad):
            raise DailyMergeError(f"market {target_date}: {name} carries {len(bad)} rows of ANOTHER date")

    # ── 3. pre-merge coverage ───────────────────────────────────────────────────────────────────
    daily_codes = set(df_daily["ts_code"].dropna().astype(str))
    adj_pos = df_adj.loc[pd.to_numeric(df_adj["adj_factor"], errors="coerce") > 0, "ts_code"]
    missing_adj = daily_codes - set(adj_pos.dropna().astype(str))
    if missing_adj:
        raise DailyMergeError(f"market {target_date}: {len(missing_adj)} priced daily codes lack a "
                              f"positive adj_factor (must be 100%); e.g. {sorted(missing_adj)[:5]}")
    basic_cov = len(set(df_basic["ts_code"].dropna().astype(str)) & daily_codes) / max(1, len(daily_codes))
    if basic_cov < MIN_BASIC_CODE_COVERAGE:
        raise DailyMergeError(f"market {target_date}: daily_basic code coverage {basic_cov:.3f} "
                              f"< {MIN_BASIC_CODE_COVERAGE:.2f}")

    # ── 4. merge, base-key preserving ───────────────────────────────────────────────────────────
    basic_payload = [c for c in df_basic.columns
                     if c not in ("ts_code", "trade_date") + _AUX_DROP_BASIC + _AUX_DROP_ALWAYS]
    aux_basic = df_basic.drop(columns=[c for c in _AUX_DROP_BASIC + _AUX_DROP_ALWAYS
                                       if c in df_basic.columns])
    aux_adj = df_adj.drop(columns=[c for c in _AUX_DROP_ALWAYS if c in df_adj.columns])
    merged = pd.merge(df_daily, aux_basic, on=["ts_code", "trade_date"], how="left",
                      validate="one_to_one")
    merged = pd.merge(merged, aux_adj, on=["ts_code", "trade_date"], how="left",
                      validate="one_to_one")
    if len(merged) != len(df_daily):
        raise DailyMergeError(f"market {target_date}: merge changed the row count "
                              f"({len(df_daily)} -> {len(merged)}) — base-key preservation violated")

    # ── 5. POST-merge: the aux payloads must have actually SURVIVED ─────────────────────────────
    # A mis-keyed or wrong-date aux frame left-merges to all-NULL while passing every code-coverage
    # check above, so coverage of the KEYS is not evidence that the VALUES arrived.
    if "adj_factor" not in merged.columns:
        raise DailyMergeError(f"market {target_date}: merged frame lost the adj_factor column")
    adj_nn = float(pd.to_numeric(merged["adj_factor"], errors="coerce").notna().mean())
    if adj_nn < 1.0:
        raise DailyMergeError(f"market {target_date}: post-merge non-null adj_factor {adj_nn:.4f} < 1.0 "
                              f"(merge dropped adjustment rows)")
    if basic_payload:
        present = [c for c in basic_payload if c in merged.columns]
        if not present:
            raise DailyMergeError(f"market {target_date}: merged frame lost every daily_basic payload column")
        payload_nn = float(merged[present].notna().any(axis=1).mean())
        if payload_nn < MIN_BASIC_PAYLOAD_COVERAGE:
            raise DailyMergeError(f"market {target_date}: post-merge daily_basic payload coverage "
                                  f"{payload_nn:.3f} < {MIN_BASIC_PAYLOAD_COVERAGE:.2f} "
                                  f"(wrong-date/mis-keyed daily_basic?)")

    if merged.duplicated(subset=["ts_code", "trade_date"]).any():
        raise DailyMergeError(f"market {target_date}: merged output has duplicate (ts_code, trade_date) keys")
    return merged
