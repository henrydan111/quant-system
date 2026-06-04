# ──────────────────────────────────────────────────────────────────────
# Anomaly review for the `moneyflow` dataset (quarantine → approved candidate).
# script_status: historical_investigation
# formal_research_allowed: false
# deployment_target: research
# requires_provider_manifest: false
# requires_preload_strict: false
# pr2_audit_class: B
# notes: |
#   Discharges the "pending anomaly review" gate for the Tushare moneyflow
#   endpoint (18 capital-flow fields), mirroring the stk_limit precedent
#   (diag_stk_limit_coverage.py + an approval YAML). Read-only. Produces the
#   evidence the approval YAML needs:
#     (1) COVERAGE — per-field non-null % across sample years (bar: >=50%);
#     (2) VALUE SANITY — sign (buy/sell components >=0), ranges, and the
#         turnover-balance identity (Sum(buy_amount) ~= Sum(sell_amount));
#     (3) NET RECONCILIATION — which formula (if any) reproduces net_mf_amount
#         / net_mf_vol from the component columns (documents the field's true
#         meaning so factors use it correctly);
#     (4) PROVIDER PARITY — Qlib D.features vs raw parquet on sample stock-days;
#     (5) PIT note — moneyflow is a same-day-realized daily fact (trade_date
#         anchor) → predictive factors need Ref(...,1).
# ──────────────────────────────────────────────────────────────────────
"""moneyflow anomaly review: coverage + value sanity + net reconciliation + parity."""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # workspace/scripts -> workspace -> project root
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

MF_DIR = ROOT / "data" / "market" / "moneyflow"
QLIB_DIR = ROOT / "data" / "qlib_data"
OUT = ROOT / "workspace" / "outputs" / "gated_review"
OUT.mkdir(parents=True, exist_ok=True)

BUY = ["buy_sm_amount", "buy_md_amount", "buy_lg_amount", "buy_elg_amount"]
SELL = ["sell_sm_amount", "sell_md_amount", "sell_lg_amount", "sell_elg_amount"]
BUY_V = ["buy_sm_vol", "buy_md_vol", "buy_lg_vol", "buy_elg_vol"]
SELL_V = ["sell_sm_vol", "sell_md_vol", "sell_lg_vol", "sell_elg_vol"]
ALL_FIELDS = BUY + SELL + BUY_V + SELL_V + ["net_mf_vol", "net_mf_amount"]
COVERAGE_YEARS = ["2008", "2014", "2018", "2021", "2024", "2026"]
DEEP_YEAR = "2018"


def _load_year(year: str) -> pd.DataFrame:
    fs = sorted(glob.glob(str(MF_DIR / year / "*.parquet")))
    if not fs:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True)


def _corr_and_err(implied: pd.Series, actual: pd.Series) -> dict:
    m = implied.notna() & actual.notna()
    if m.sum() < 100:
        return {"corr": None, "mean_abs_err": None, "exact_match_pct": None, "n": int(m.sum())}
    a, b = implied[m], actual[m]
    return {
        "corr": round(float(np.corrcoef(a, b)[0, 1]), 6),
        "mean_abs_err": round(float((a - b).abs().mean()), 4),
        "exact_match_pct": round(float((np.isclose(a, b, rtol=1e-3, atol=1.0)).mean() * 100), 4),
        "n": int(m.sum()),
    }


def main() -> int:
    out: dict = {"dataset": "moneyflow", "fields": ALL_FIELDS}

    # ── (1) COVERAGE across years ──
    cov = {}
    for y in COVERAGE_YEARS:
        df = _load_year(y)
        if df.empty:
            cov[y] = {"files": 0}
            continue
        nn = {f: round(float(df[f].notna().mean() * 100), 3) for f in ALL_FIELDS if f in df.columns}
        cov[y] = {"rows": len(df), "stock_days": int(df[["ts_code", "trade_date"]].drop_duplicates().shape[0]),
                  "min_nonnull_pct": round(min(nn.values()), 3), "per_field_nonnull_pct": nn}
    out["coverage"] = cov

    # ── (2)+(3) VALUE SANITY + NET RECONCILIATION on the deep year ──
    df = _load_year(DEEP_YEAR)
    sum_buy = df[BUY].sum(axis=1)
    sum_sell = df[SELL].sum(axis=1)
    sum_buy_v = df[BUY_V].sum(axis=1)
    sum_sell_v = df[SELL_V].sum(axis=1)
    neg_components = int((df[BUY + SELL + BUY_V + SELL_V] < 0).any(axis=1).sum())
    out["value_sanity"] = {
        "deep_year": DEEP_YEAR, "rows": len(df),
        "negative_component_rows": neg_components,
        "turnover_balance_sum_buy_vs_sum_sell": _corr_and_err(sum_buy, sum_sell),
        "net_mf_amount_range": [round(float(df["net_mf_amount"].min()), 2), round(float(df["net_mf_amount"].max()), 2)],
        "amount_units": "万元 (10k CNY) per data_dictionary", "vol_units": "手 (lots)",
    }
    # candidate formulas for net_mf_amount
    out["net_amount_reconciliation"] = {
        "all_sizes  (Sbuy - Ssell)": _corr_and_err(sum_buy - sum_sell, df["net_mf_amount"]),
        "lg+elg     (main force)": _corr_and_err((df["buy_lg_amount"] + df["buy_elg_amount"]) - (df["sell_lg_amount"] + df["sell_elg_amount"]), df["net_mf_amount"]),
        "md+lg+elg  (ex-small)": _corr_and_err((df["buy_md_amount"] + df["buy_lg_amount"] + df["buy_elg_amount"]) - (df["sell_md_amount"] + df["sell_lg_amount"] + df["sell_elg_amount"]), df["net_mf_amount"]),
        "elg only": _corr_and_err(df["buy_elg_amount"] - df["sell_elg_amount"], df["net_mf_amount"]),
    }
    out["net_vol_reconciliation"] = {
        "all_sizes  (Sbuy - Ssell)": _corr_and_err(sum_buy_v - sum_sell_v, df["net_mf_vol"]),
        "lg+elg": _corr_and_err((df["buy_lg_vol"] + df["buy_elg_vol"]) - (df["sell_lg_vol"] + df["sell_elg_vol"]), df["net_mf_vol"]),
    }

    # ── (4) PROVIDER PARITY spot-check ──
    parity = {"checked": [], "ok": None}
    try:
        import qlib
        from qlib.data import D
        qlib.init(provider_uri=str(QLIB_DIR), region="cn", kernels=1)
        insts = ["000001_sz", "600519_sh"]
        prov = D.features(insts, ["$net_mf_amount", "$net_mf_vol"],
                          start_time="2018-01-02", end_time="2018-01-10", freq="day")
        mism = 0
        for inst in insts:
            ts = inst.replace("_sz", ".SZ").replace("_sh", ".SH").upper()
            raw = df[(df["ts_code"] == ts)]
            raw = raw[(raw["trade_date"].astype(str) >= "20180102") & (raw["trade_date"].astype(str) <= "20180110")]
            try:
                pv = prov.loc[inst]
            except KeyError:
                parity["checked"].append({inst: "provider missing"}); continue
            for _, r in raw.iterrows():
                d = pd.Timestamp(str(r["trade_date"]))
                if d in pv.index:
                    pa = float(pv.loc[d, "$net_mf_amount"])
                    if not np.isclose(pa, float(r["net_mf_amount"]), rtol=1e-3, atol=1.0):
                        mism += 1
            parity["checked"].append({inst: f"{len(raw)} raw rows compared"})
        parity["ok"] = (mism == 0)
        parity["mismatches"] = mism
    except Exception as e:
        parity["error"] = str(e)[:200]
    out["provider_parity"] = parity

    out["pit_note"] = ("moneyflow is a SAME-DAY-realized daily fact (the day's classified order flow), "
                       "anchored on trade_date, knowable only at session CLOSE of day T. Predictive factors "
                       "MUST wrap it in Ref(...,1) (use day T-1 flow to predict day T) — same discipline as "
                       "$turnover_rate / any daily outcome field. NOT an execution field.")

    (OUT / "moneyflow_review.json").write_text(json.dumps(out, indent=2, default=str))
    # console summary
    print("=== moneyflow coverage (min non-null % per year) ===")
    for y, c in cov.items():
        print(f"  {y}: {c.get('min_nonnull_pct', 'no files')}%  ({c.get('stock_days','-')} stock-days)")
    print(f"\nnegative component rows ({DEEP_YEAR}): {neg_components}")
    print(f"turnover balance Sbuy~Ssell: {out['value_sanity']['turnover_balance_sum_buy_vs_sum_sell']}")
    print("\n=== net_mf_amount reconciliation (corr / exact-match%) ===")
    for k, v in out["net_amount_reconciliation"].items():
        print(f"  {k:28s}: corr={v['corr']} exact={v['exact_match_pct']}%")
    print("\n=== net_mf_vol reconciliation ===")
    for k, v in out["net_vol_reconciliation"].items():
        print(f"  {k:28s}: corr={v['corr']} exact={v['exact_match_pct']}%")
    print(f"\nprovider parity: {parity}")
    print(f"\n[saved] {OUT / 'moneyflow_review.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
