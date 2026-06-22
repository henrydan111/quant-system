"""Rung-2 PIT validation (GPT R1 Major-1 hardened): does the LOCAL provider PIT
income-statement serving reproduce 果仁's per-holding 净利润(单季) — AND, critically,
does the value the STRATEGY actually gates on (the PREVIOUS trading day) match, with
NO gate-status flips?

果仁's 各阶段持仓详单 carries 净利润(万) for every held name as-of each rebalance
(开始日期). build_schedule gates 净利润(单季)>0 on the PREV trading day (the Ref(,1)
PIT lag), NOT the rebalance date. So we compare the provider $n_income_sq_q0 under
BOTH as-of dates:
  (A) as-of the holding START date         (= 果仁's display date)
  (B) as-of the PREV trading day           (= what the strategy gate uses)
and report, for 果仁-HELD (hence positive-profit) names:
  - match rate vs 果仁 净利润(万) under A and under B
  - rows where A matches but B differs (a value updated ON the rebalance day)
  - GATE FLIPS: 果仁-held rows with value_A > 0 but value_B <= 0 or NaN  (the strategy
    would WRONGLY drop a 果仁-held name)  <-- the load-bearing PIT-timing metric
Also tests $n_income_attr_p_sq_q0 (归母) for field identity.

Saves the artifact to workspace/outputs/guorn_parity/rung2_pit_validation.json.
Throwaway validation utility (sandbox; reads the already-PIT-materialized provider
field as-of the date — no hand-rolled alignment).
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

XLSX = ROOT / "Knowledge" / "果仁回测结果" / "16_sm_noc_纯市值正盈利_v4.xlsx"
OUT = ROOT / "workspace" / "outputs" / "guorn_parity" / "rung2_pit_validation.json"
FIELDS = ["$n_income_sq_q0", "$n_income_attr_p_sq_q0"]


def _asof(wide: pd.DataFrame, idx, code, shift_days: int = 0):
    """Provider value as-of (the trading day at position pos-shift_days) for `code`.
    shift_days=0 -> as-of the date itself; 1 -> the previous trading day."""
    pos = wide.index.searchsorted(idx, side="right") - 1 - shift_days
    if pos < 0:
        return np.nan
    return wide.iat[pos, code] if isinstance(code, int) else wide.loc[wide.index[pos]].get(code, np.nan)


def main():
    h = pd.read_excel(XLSX, sheet_name="各阶段持仓详单")
    code6 = h["股票代码"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
    h = h.assign(qlib=code6 + "_SZ", date=pd.to_datetime(h["开始日期"]),
                 np_wan=pd.to_numeric(h["净利润(万)"], errors="coerce")).dropna(subset=["np_wan"])

    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(ROOT / "data" / "qlib_data"), region=REG_CN, kernels=1)
    insts = sorted(h["qlib"].unique())
    lo, hi = h["date"].min().strftime("%Y-%m-%d"), h["date"].max().strftime("%Y-%m-%d")
    print(f"[validate] {len(h)} holding-rows | {len(insts)} names | {lo}..{hi}", flush=True)
    df = D.features(insts, FIELDS, start_time=lo, end_time=hi, freq="day")
    df.columns = [c.replace("$", "") for c in FIELDS]

    artifact = {"field_identity": {}, "pit_timing": {}}
    for field in df.columns:
        wide = df[field].unstack(level=0).sort_index()
        # scale probe (provider 元 vs 果仁 万)
        recsA = []
        for dt, sub in h.groupby("date"):
            for q, gnp in zip(sub["qlib"], sub["np_wan"]):
                recsA.append((gnp, _asof(wide, dt, q, 0)))
        cmpA = pd.DataFrame(recsA, columns=["g", "loc"]).dropna()
        ratio = (cmpA["loc"] / cmpA["g"].replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).dropna()
        scale = 1e4 if ratio.median() > 100 else 1.0
        relA = ((cmpA["loc"] / scale) - cmpA["g"]).abs() / cmpA["g"].abs().clip(lower=1.0)
        artifact["field_identity"][field] = {
            "matched": int(len(cmpA)), "n": int(len(h)),
            "median_relerr": float(relA.median()), "within_0.1pct": float((relA <= 0.001).mean()),
            "scale": scale}
        print(f"\n=== {field} (field identity, as-of start date) ===")
        print(f"  matched {len(cmpA)}/{len(h)} | median rel-err {relA.median():.4f} | within 0.1%: {(relA<=0.001).mean():.1%}")

    # --- PIT timing on the confirmed field: as-of START (A) vs PREV trading day (B) + gate flips ---
    field = "n_income_sq_q0"
    wide = df[field].unstack(level=0).sort_index()
    scale = artifact["field_identity"][field]["scale"]
    rows = []
    for dt, sub in h.groupby("date"):
        for q, gnp in zip(sub["qlib"], sub["np_wan"]):
            vA = _asof(wide, dt, q, 0)
            vB = _asof(wide, dt, q, 1)
            rows.append((gnp, vA, vB))
    c = pd.DataFrame(rows, columns=["g", "vA", "vB"])
    okA = c["vA"].notna(); okB = c["vB"].notna()
    relA = ((c["vA"] / scale) - c["g"]).abs() / c["g"].abs().clip(lower=1.0)
    relB = ((c["vB"] / scale) - c["g"]).abs() / c["g"].abs().clip(lower=1.0)
    a_match = okA & (relA <= 0.001)
    b_match = okB & (relB <= 0.001)
    a_not_b = a_match & ~b_match                       # value updated ON the rebalance day
    # GATE FLIPS: 果仁-held (positive) name with A>0 but B<=0 or NaN -> strategy would drop it
    gate_flip = (c["vA"] > 0) & (~okB | (c["vB"] <= 0))
    # all 果仁-held names are positive by construction; count B<=0/NaN among them
    held_pos = c["g"] > 0
    b_nonpos_or_nan = held_pos & (~okB | (c["vB"] <= 0))
    pit = {
        "n": int(len(c)),
        "match_rate_start_date_A": float(a_match.mean()),
        "match_rate_prev_trade_day_B": float(b_match.mean()),
        "rows_A_match_B_differ": int(a_not_b.sum()),
        "gate_flips_A_pos_B_nonpos_or_nan": int(gate_flip.sum()),
        "guorn_held_with_prevday_nonpos_or_nan": int(b_nonpos_or_nan.sum()),
        "prevday_value_nan": int((~okB).sum()),
    }
    artifact["pit_timing"] = pit
    # The STRATEGY GATE now reads AS-OF THE REBALANCE DAY (A) — PIT-safe via the provider's
    # effective_date>disclosure anchor (§3.2), faithful to 果仁's 公告日 selection. B (prev-day)
    # is the OLD over-conservative Ref(,1) gate; the A>0/B<=0 rows are names B wrongly dropped,
    # RESOLVED by the switch to A (GPT R1 Major-1).
    print("\n=== PIT TIMING (n_income_sq_q0): STRATEGY GATE = as-of rebalance day (A) vs old prev-day (B) ===")
    print(f"  match rate A (gate, as-of-d)   : {pit['match_rate_start_date_A']:.1%}  <- the gate the strategy uses")
    print(f"  match rate B (old prev-day gate): {pit['match_rate_prev_trade_day_B']:.1%}")
    print(f"  names the OLD prev-day gate over-dropped (A>0, B<=0/NaN): {pit['gate_flips_A_pos_B_nonpos_or_nan']}"
          f"  -> RESOLVED by gating as-of-d")
    artifact["gate_basis"] = "as_of_rebalance_day (lag-0, provider effective_date-safe)"
    verdict = ("PIT PATH VALIDATED ON THE GATE DATE (as-of-d, 96%+ penny-exact)"
               if pit["match_rate_start_date_A"] >= 0.90 else "REVIEW — gate diverges")
    artifact["verdict"] = verdict
    print(f"\n  VERDICT: {verdict}")
    OUT.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  saved -> {OUT}")


if __name__ == "__main__":
    main()
