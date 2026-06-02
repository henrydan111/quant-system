# script_status: historical_investigation
# formal_research_allowed: false
# deployment_target: none
# requires_provider_manifest: false
# requires_preload_strict: false
# pr2_audit_class: D
"""Real-data verification of the Tushare-stk_limit-primary / computed-fallback
limit detection. Constructs the Exchange exactly as a real backtest does (with
the authoritative ST ranges) and exercises corner cases on ACTUAL provider rows:

  1. Real limit-UP days (close ≈ up_limit, field present)  → is_limit_up True
  2. Real limit-DOWN days (close ≈ down_limit, field present) → is_limit_down True
  3. Real non-limit days (field present, close mid-band)   → both False
  4. Real FALLBACK rows (traded, up/down NaN — BSE 2021)   → resolve computes
     the board band; is_limit_up/down still function (never crash / never treat
     a limit-locked stock as silently unconstrained)
  5. Tier consistency: present up_limit matches get_limit_pct band (or is an
     explained IPO-±44% off-tier)

Run: venv/Scripts/python.exe workspace/scripts/verify_stk_limit_corner_cases.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backtest_engine.event_driven.data_feeder import QlibDataFeeder
from src.backtest_engine.event_driven.exchange import Exchange, NoSlippage

DATA_DIR = str(PROJECT_ROOT / "data")
ST_PATH = str(PROJECT_ROOT / "data" / "qlib_data" / "instruments" / "st_stocks.txt")

PASS = "PASS"
FAIL = "FAIL"
_failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    status = PASS if cond else FAIL
    if not cond:
        _failures.append(name)
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))


def build_row(r: pd.Series) -> pd.Series:
    """Build an engine-style day row from a flat provider record."""
    return pd.Series({
        "raw_close": r["close"], "close": r["close"],
        "raw_pre_close": r["pre_close"], "pre_close": r["pre_close"],
        "up_limit": r["up_limit"], "down_limit": r["down_limit"],
        "vol": r.get("vol", np.nan),
    })


def main() -> None:
    feeder = QlibDataFeeder(DATA_DIR, stage="is_only")
    ex = Exchange(slippage_model=NoSlippage(), st_data_path=ST_PATH, feeder=feeder)
    stock_codes = set(feeder._stock_basic["ts_code"].astype(str))

    # 2021 carries BOTH present rows AND the BSE-launch NaN gap rows.
    feeder.preload_features(
        "all", ["$up_limit", "$down_limit", "$close", "$pre_close", "$vol"],
        "2021-01-01", "2021-12-31", strict=True,
    )
    df = feeder._cache_df.rename(columns={
        "$up_limit": "up_limit", "$down_limit": "down_limit",
        "$close": "close", "$pre_close": "pre_close", "$vol": "vol",
    })
    inst = df.index.get_level_values("instrument")
    df = df[inst.isin(stock_codes)].reset_index()
    df = df[df["vol"].fillna(0) > 0]  # traded only
    df = df[df["pre_close"].fillna(0) > 0]
    present = df[df["up_limit"].notna() & df["down_limit"].notna()]
    missing = df[df["up_limit"].isna() | df["down_limit"].isna()]
    print(f"2021 traded stock-days: {len(df)}  present={len(present)}  fallback(NaN)={len(missing)}\n")

    date = pd.Timestamp("2021-06-15")  # any non-ST-boundary-sensitive date for fallback band

    # ── 1. Real limit-UP days (field present) ─────────────────────────
    print("[1] Real limit-UP days (Tushare field present):")
    up_days = present[(present["close"] - present["up_limit"]).abs() < 0.005].head(50)
    n_up_ok = sum(
        ex.is_limit_up(build_row(r), str(r["instrument"]), pd.Timestamp(r["datetime"]))
        for _, r in up_days.iterrows()
    )
    check("all sampled real limit-up rows detected", n_up_ok == len(up_days),
          f"{n_up_ok}/{len(up_days)} detected")
    if len(up_days):
        s = up_days.iloc[0]
        print(f"      e.g. {s['instrument']} {str(s['datetime'])[:10]} "
              f"close={s['close']:.2f} up_limit={s['up_limit']:.2f}")

    # ── 2. Real limit-DOWN days (field present) ───────────────────────
    print("[2] Real limit-DOWN days (Tushare field present):")
    dn_days = present[(present["close"] - present["down_limit"]).abs() < 0.005].head(50)
    n_dn_ok = sum(
        ex.is_limit_down(build_row(r), str(r["instrument"]), pd.Timestamp(r["datetime"]))
        for _, r in dn_days.iterrows()
    )
    check("all sampled real limit-down rows detected", n_dn_ok == len(dn_days),
          f"{n_dn_ok}/{len(dn_days)} detected")

    # ── 3. Real non-limit days (mid-band) ─────────────────────────────
    print("[3] Real non-limit days (close strictly inside the band):")
    mid = present[
        ((present["close"] - present["up_limit"]).abs() > 0.05)
        & ((present["close"] - present["down_limit"]).abs() > 0.05)
    ].head(50)
    n_mid_false = sum(
        (not ex.is_limit_up(build_row(r), str(r["instrument"]), pd.Timestamp(r["datetime"])))
        and (not ex.is_limit_down(build_row(r), str(r["instrument"]), pd.Timestamp(r["datetime"])))
        for _, r in mid.iterrows()
    )
    check("mid-band rows are neither limit-up nor limit-down", n_mid_false == len(mid),
          f"{n_mid_false}/{len(mid)} correct")

    # ── 4. Real FALLBACK rows (NaN field, must compute board band) ────
    print("[4] Real FALLBACK rows (up/down NaN on a traded day):")
    if len(missing):
        ok_fallback = 0
        ok_band = 0
        sample = missing.head(50)
        for _, r in sample.iterrows():
            code = str(r["instrument"])
            d = pd.Timestamp(r["datetime"])
            up, down = ex.resolve_limit_prices(build_row(r), code, d)
            # Fallback must return finite computed prices (NOT the NaN field).
            if np.isfinite(up) and np.isfinite(down):
                ok_fallback += 1
                # And they must equal pre_close × the board band.
                is_st = ex.is_st(code, d)
                band = ex.get_limit_pct(code, is_st, d)
                exp_up, exp_down = ex.compute_limit_prices(float(r["pre_close"]), band)
                if abs(up - exp_up) < 0.005 and abs(down - exp_down) < 0.005:
                    ok_band += 1
        check("fallback returns finite computed prices (never NaN)", ok_fallback == len(sample),
              f"{ok_fallback}/{len(sample)}")
        check("fallback prices equal pre_close × board band", ok_band == len(sample),
              f"{ok_band}/{len(sample)}")
        s = sample.iloc[0]
        code = str(s["instrument"]); d = pd.Timestamp(s["datetime"])
        up, down = ex.resolve_limit_prices(build_row(s), code, d)
        print(f"      e.g. {code} {str(d)[:10]} pre_close={s['pre_close']:.2f} "
              f"field=NaN → computed up={up:.2f} down={down:.2f} "
              f"(band={ex.get_limit_pct(code, ex.is_st(code, d), d):.0%})")
        # BSE concentration sanity
        bse = sample[sample["instrument"].astype(str).str.endswith(".BJ")]
        print(f"      ({len(bse)}/{len(sample)} sampled fallback rows are .BJ / Beijing exchange)")
    else:
        check("fallback rows present to test", False, "no NaN rows found in 2021")

    # ── 5. Tier consistency on present rows ───────────────────────────
    print("[5] Tier consistency (present up_limit vs get_limit_pct band):")
    chk = present.head(3000).copy()
    on_tier = 0
    ipo44 = 0
    for _, r in chk.iterrows():
        code = str(r["instrument"]); d = pd.Timestamp(r["datetime"])
        is_st = ex.is_st(code, d)
        band = ex.get_limit_pct(code, is_st, d)
        exp_up, _ = ex.compute_limit_prices(float(r["pre_close"]), band)
        if abs(float(r["up_limit"]) - exp_up) < 0.02:
            on_tier += 1
        elif abs(float(r["up_limit"]) / float(r["pre_close"]) - 1.44) < 0.02:
            ipo44 += 1
    pct = 100.0 * (on_tier + ipo44) / len(chk)
    check("≥99% of present rows match board band (or IPO-±44%)", pct >= 99.0,
          f"{pct:.2f}% ({on_tier} band + {ipo44} ipo44 of {len(chk)})")

    print("\n" + "=" * 60)
    if _failures:
        print(f"RESULT: {len(_failures)} FAILED — {_failures}")
        sys.exit(1)
    print("RESULT: ALL CORNER CASES PASS")


if __name__ == "__main__":
    main()
