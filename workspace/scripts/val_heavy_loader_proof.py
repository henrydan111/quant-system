# script_status: historical_investigation
# formal_research_allowed: false
# deployment_target: N/A
# requires_provider_manifest: false
# requires_preload_strict: false
# pr2_audit_class: D
"""val_heavy loader-migration PROOF (PIT-prevention phase 3, step 3).

Demonstrates that the sanctioned ``pit_research_loader`` cleanly REPLACES the
hand-rolled ``build_pit_pivot`` pattern that caused the original lookahead bug.
The entire buggy block — read raw ``data/pit_ledger`` parquet, ``.astype(str)``
the dashed ``effective_date``, ``sorted(set(dashed)|set(compact))``, ``ffill``,
``shift`` — collapses to ONE call:

    panels = load_pit_signal_panel(fields, sim_dates, signal_lag_bars=1)

This script is therefore **PIT002-clean** (it never reads the raw ledger; the
lint cannot flag it) and it is the first real consumer of the five indicator
columns registered in PR #19 (it uses ``dt_netprofit_yoy``). Running it
independently re-confirms — through a completely different, governed code path —
the de-contaminated val_heavy result the fixed sandbox produced (weak CAGR,
negative walk-forward), i.e. NOT the +81.9%/WF+82.4% phantom.

NOT a formal run. Close-to-close engine, mirrors sandbox_v15o's val_heavy config.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from src.data_infra.pit_research_loader import (  # noqa: E402
    _data_root,
    _trading_calendar,
    load_pit_signal_panel,
)

DAILY_ROOT = _data_root() / "market" / "daily"
SIM_START, SIM_END = "20140101", "20260228"
IS_END, OOS_START = "20191231", "20200101"

# val_heavy config (sandbox_v15o_val_heavy_confirm.py): the now-INVALIDATED
# deployment candidate. Re-running it here proves the loader serves these fields
# and reproduces the corrected (weak) profile via the sanctioned path.
WEIGHTS = {"npy": 0.20, "dt_npy": 0.15, "q_qoq": 0.15, "roe": 0.20, "val": 0.30}
FIELD_MAP = {"npy": "netprofit_yoy", "dt_npy": "dt_netprofit_yoy", "q_qoq": "q_op_qoq", "roe": "roe"}
K, MIN_SCALE, TARGET_VOL, PB_MAX, PB_MIN, REBAL, COST = 6, 0.70, 0.40, 7.0, 0.30, 35, 25 / 10000
WF_FOLDS = [("16-18", "20160101", "20181231"), ("18-20", "20180101", "20201231"),
            ("20-22", "20200101", "20221231"), ("22-24", "20220101", "20241231"),
            ("24-26", "20240101", "20261231")]


def main() -> None:
    cal = _trading_calendar()
    sim = [d.strftime("%Y%m%d") for d in cal if SIM_START <= d.strftime("%Y%m%d") <= SIM_END]
    print(f"sim dates: {len(sim)}  ({sim[0]}..{sim[-1]})")

    # ─── THE MIGRATION: one loader call replaces the whole build_pit_pivot block.
    t0 = time.time()
    fund = load_pit_signal_panel(list(FIELD_MAP.values()), sim, signal_lag_bars=1)
    print(f"load_pit_signal_panel: {time.time()-t0:.0f}s "
          f"({len(fund)} fields, PIT002-clean, signal_lag_bars=1)")

    # ─── Daily panel (prices/pb): NOT pit_ledger reads, so no lint concern.
    cols = ["ts_code", "trade_date", "pct_chg", "pb"]
    chunks = []
    for yr in range(2013, 2027):
        for f in sorted((DAILY_ROOT / str(yr)).glob("daily_*.parquet")) if (DAILY_ROOT / str(yr)).exists() else []:
            try:
                chunks.append(pd.read_parquet(f, columns=cols))
            except Exception:
                pass
    raw = pd.concat(chunks, ignore_index=True)
    raw["trade_date"] = raw["trade_date"].astype(str)  # noqa: unsafe-pit-dates[PIT001] reason: compact market-date index only; NOT joined/unioned/ffilled against any fundamental effective_date
    # Safe-stringify guard: these are compact YYYYMMDD market dates compared only
    # against compact SIM_START/SIM_END and used as a pivot index — never mixed
    # with a dashed fundamental effective_date (the original-bug pattern).
    if not raw["trade_date"].str.fullmatch(r"\d{8}").all():
        raise ValueError("daily trade_date must be compact YYYYMMDD")
    raw = raw[(raw["trade_date"] >= SIM_START) & (raw["trade_date"] <= SIM_END)]
    ret = raw.pivot_table(index="trade_date", columns="ts_code", values="pct_chg", aggfunc="first").sort_index() / 100.0
    pb = raw.pivot_table(index="trade_date", columns="ts_code", values="pb", aggfunc="first").sort_index()

    # ─── Common universe across loader panels + daily, aligned to sim.
    common = sorted(set(ret.columns) & set(pb.columns) & set(fund["roe"].columns))
    ret = ret.reindex(index=sim, columns=common)
    pb = pb.reindex(index=sim, columns=common).shift(1)
    fa = {k: fund[col].reindex(index=sim, columns=common).to_numpy() for k, col in FIELD_MAP.items()}
    fa["val"] = (1.0 / pb.replace(0, np.nan)).to_numpy()
    pb_arr, ret_arr = pb.to_numpy(), ret.to_numpy()
    mkt_vol = (ret.mean(axis=1).rolling(60, min_periods=45).std() * np.sqrt(252)).shift(1).to_numpy()

    def pct_rank(a):
        o = np.argsort(a); r = np.empty(len(a)); r[o] = np.arange(1, len(a) + 1) / len(a); return r

    def run(dates_idx):
        r_set = {dates_idx[0]} | {dates_idx[i] for i in range(REBAL, len(dates_idx), REBAL)}
        nav, navs, basket = 1.0, [], None
        for i in dates_idx:
            if i in r_set:
                npy_r, roe_r, pb_r = fa["npy"][i], fa["roe"][i], pb_arr[i]
                valid = (np.isfinite(npy_r) & (npy_r >= 0) & np.isfinite(roe_r) & (roe_r >= 0)
                         & np.isfinite(pb_r) & (pb_r > PB_MIN) & (pb_r <= PB_MAX))
                vidx = np.where(valid)[0]
                if len(vidx) >= K:
                    score = np.zeros(len(vidx))
                    for k, w in WEIGHTS.items():
                        arr = fa[k][i][vidx]; vf = np.isfinite(arr); sr = np.full(len(vidx), 0.5)
                        if vf.sum() >= 3:
                            sr[vf] = pct_rank(arr[vf])
                        score += w * sr
                    basket = vidx[np.argpartition(score, -K)[-K:]]
            if basket is None:
                navs.append(nav); continue
            rv = mkt_vol[i]
            scale = float(np.clip(TARGET_VOL / rv, MIN_SCALE, 1.0)) if (np.isfinite(rv) and rv > 0.01) else 1.0
            dr = ret_arr[i, basket]; dr = dr[np.isfinite(dr)]
            if len(dr) == 0:
                navs.append(nav); continue
            pnl = scale * float(np.mean(dr)) - (scale * 2 * COST if i in r_set else 0.0)
            nav *= 1 + pnl; navs.append(nav)
        return np.array(navs)

    def stats(navs):
        ny = len(navs) / 252.0
        cagr = (navs[-1] / navs[0]) ** (1 / max(ny, 0.01)) - 1
        pk = np.maximum.accumulate(navs); mdd = ((navs - pk) / pk).min()
        return cagr, mdd

    full = run(list(range(len(sim))))
    is_idx = [i for i, d in enumerate(sim) if d <= IS_END]
    oos_idx = [i for i, d in enumerate(sim) if d >= OOS_START]
    cagr_f, mdd_f = stats(full)
    cagr_is, _ = stats(run(is_idx)); cagr_oos, mdd_oos = stats(run(oos_idx))
    wf = []
    for _, fs, fe in WF_FOLDS:
        idx = [i for i, d in enumerate(sim) if fs <= d <= fe]
        if len(idx) > 50:
            wf.append(stats(run(idx))[0])
    wf_avg = float(np.nanmean(wf)) if wf else float("nan")

    print("\n=== val_heavy via the SANCTIONED LOADER (de-contaminated, sanity check) ===")
    print(f"  Full   CAGR={cagr_f*100:6.1f}%  MDD={mdd_f*100:7.1f}%")
    print(f"  IS     CAGR={cagr_is*100:6.1f}%")
    print(f"  OOS    CAGR={cagr_oos*100:6.1f}%  MDD={mdd_oos*100:7.1f}%")
    print(f"  WF avg CAGR={wf_avg*100:6.1f}%   folds={['%.0f%%' % (x*100) for x in wf]}")
    print("\n  Compare to the INVALIDATED phantom (+81.9% / WF +82.4%): the loader")
    print("  path independently reproduces the weak de-contaminated profile.")
    print("  ERGONOMICS PROOF: build_pit_pivot replaced by one load_pit_signal_panel call;")
    print("  this script is PIT002-clean and consumes the PR#19-registered dt_netprofit_yoy.")

    # ─── Leakage sentinel (NOT an optimization target). The original failure
    # was that phantom numbers got recorded instead of quarantined. If the
    # PIT-correct loader path ever reproduces phantom-like strength, that signals
    # leakage or material semantics drift — fail loudly, do not print-and-pass.
    # Threshold (30%) sits far above the true de-contaminated profile
    # (OOS ~2-10%, WF ~0%) and far below the invalidated +81.9%/+82.4% phantom.
    PHANTOM_GUARD = 0.30
    if cagr_oos > PHANTOM_GUARD or wf_avg > PHANTOM_GUARD:
        raise AssertionError(
            f"val_heavy loader proof produced unexpectedly strong results "
            f"(OOS CAGR={cagr_oos:.1%}, WF avg={wf_avg:.1%}) above the {PHANTOM_GUARD:.0%} "
            f"phantom-leakage sentinel. The PIT-correct path should be WEAK; this likely "
            f"indicates reintroduced lookahead or a semantics drift — investigate before "
            f"recording any result."
        )


if __name__ == "__main__":
    main()
