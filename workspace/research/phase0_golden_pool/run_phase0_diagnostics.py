# SCRIPT_STATUS: ACTIVE — NON-FORMAL Phase-0 pool-level diagnostic (C9 diagnostics-only)
"""Phase 0 · 金股池 go/no-go 诊断: does broker pre-filtering add value for quant factors?

PRE-REGISTERED design (fixed before any result is seen):
  - Factors (7, the ex-approved / most-validated set; ids from the factor registry;
    expected_direction read from data/factor_registry/factor_master.parquet — NOT
    inferred from this window):
      liq_zero_ret_days_10d, rev_turnover_spike_5d, qual_piotroski_fscore_9pt,
      earn_sue_ni_assets, grow_total_revenue_yoy_accel_q,
      grow_n_income_attr_p_yoy_accel_q, grow_operate_profit_yoy_accel_q
    + composite = mean of direction-oriented within-universe pct-ranks.
  - Rebalance dates = the golden-pool activation dates (first trading day >= day-4,
    from data_infra.golden_stock_universe — C3-enforced module).
  - Horizon h = 20 trading days, label = adjusted close(t) -> close(t+20).
  - Universes per date: POOL (golden members), BROAD (all provider names with valid
    factor+label), CONTROL (size-matched twins: for each pool name the nearest
    ln(total_mv) non-pool broad name, without replacement).
  - DECISION RULE (pre-registered): the pool adds value for quant selection iff
    composite rank_icir(POOL) >= composite rank_icir(CONTROL). BROAD is context.
  - Metrics: RankIC mean / RankICIR / n_obs / coverage ONLY (C9 allowlist; no
    CAGR/Sharpe/returns — those need the Phase-1 event-driven total-return gate).

METHODOLOGY CAVEATS (recorded, non-negotiable):
  - Window 2020-07..2026-01 lies almost entirely inside the spent-OOS 2021+ window:
    this run is a NON-FORMAL pool-level diagnostic (same class as the 2026-06-28
    mother-signal validation); it mints NO factor-level evidence.
  - Signed RankIC per factor is reported as-is; per-factor pool-vs-control
    comparison is orientation-invariant. Composite uses registry directions.

Outputs: workspace/outputs/phase0_golden_pool/phase0_report.json (C9 envelope)
         + per-date detail parquet + console table.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from data_infra.golden_stock_universe import load_golden_stock_events  # noqa: E402
from result_analysis.phase0_report import build_phase0_report  # noqa: E402
from alpha_research.factor_library.catalog import get_factor_catalog  # noqa: E402

OUT_DIR = PROJECT_ROOT / "workspace" / "outputs" / "phase0_golden_pool"
REGISTRY = PROJECT_ROOT / "data" / "factor_registry" / "factor_master.parquet"

FACTORS7 = [
    "liq_zero_ret_days_10d",
    "rev_turnover_spike_5d",
    "qual_piotroski_fscore_9pt",
    "earn_sue_ni_assets",
    "grow_total_revenue_yoy_accel_q",
    "grow_n_income_attr_p_yoy_accel_q",
    "grow_operate_profit_yoy_accel_q",
]
H = 20
START = "2020-06-01"
END = "2026-02-27"
MIN_NAMES = 30  # per-date minimum valid names per universe, else date skipped


def load_directions() -> dict[str, int]:
    reg = pd.read_parquet(REGISTRY)
    id_col = "factor_id" if "factor_id" in reg.columns else "name"
    cur = reg.sort_values(id_col).drop_duplicates(subset=[id_col], keep="last")
    dirs: dict[str, int] = {}
    for f in FACTORS7:
        rows = cur[cur[id_col] == f]
        if rows.empty or "expected_direction" not in cur.columns:
            raise RuntimeError(f"expected_direction for {f} not found in registry — refuse to guess")
        d = str(rows["expected_direction"].iloc[0]).lower()
        dirs[f] = -1 if ("inverse" in d or "neg" in d) else 1
    return dirs


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dirs = load_directions()
    print(f"[dirs] {dirs}", flush=True)

    events = load_golden_stock_events()
    anchors = (
        events.drop_duplicates(subset=["month"])[["month", "activation_date", "expiry_date"]]
        .sort_values("activation_date")
        .reset_index(drop=True)
    )
    pool_by_month = {
        m: set(g["ts_code"].str.replace(".", "_", regex=False))
        for m, g in events.groupby("month")
    }
    print(f"[pool] {len(anchors)} months {anchors['month'].iloc[0]}..{anchors['month'].iloc[-1]}", flush=True)

    import qlib
    from qlib.config import REG_CN
    from qlib.data import D

    qlib.init(provider_uri=str(PROJECT_ROOT / "data" / "qlib_data"), region=REG_CN, kernels=1)
    insts = D.list_instruments(D.instruments("all"), start_time=START, end_time=END, as_list=True)
    print(f"[qlib] {len(insts)} instruments", flush=True)

    cat = get_factor_catalog(include_new_data=True)
    exprs = [cat[f] for f in FACTORS7] + ["$close*$adj_factor", "$total_mv"]
    names = FACTORS7 + ["adjclose", "total_mv"]
    print(f"[qlib] computing {len(exprs)} expressions {START}..{END} (this is the slow part)", flush=True)
    df = D.features(insts, exprs, start_time=START, end_time=END, freq="day")
    df.columns = names
    print(f"[qlib] features done: {df.shape}", flush=True)

    # per-field date x instrument panels (Qlib MI = (instrument, datetime))
    panels = {c: df[c].unstack(level=0).sort_index() for c in names}
    fwd = panels["adjclose"].shift(-H) / panels["adjclose"] - 1.0  # trading-day shift

    # normalize instrument casing both sides
    cols_upper = {c: c.upper() for c in fwd.columns}
    for k in panels:
        panels[k] = panels[k].rename(columns=cols_upper)
    fwd = fwd.rename(columns=cols_upper)
    pool_by_month = {m: {c.upper() for c in s} for m, s in pool_by_month.items()}

    rows = []
    for _, a in anchors.iterrows():
        t = a["activation_date"]
        if t not in fwd.index:
            continue
        fret = fwd.loc[t]
        if fret.notna().sum() < MIN_NAMES:
            continue  # no forward window (calendar tail)
        mcap = panels["total_mv"].loc[t]
        pool_codes = pool_by_month[a["month"]] & set(fwd.columns)

        fvals = {f: panels[f].loc[t] for f in FACTORS7}
        # broad validity: label + mcap present
        broad_valid = fret.notna() & mcap.notna()
        pool_mask = pd.Series(False, index=fret.index)
        pool_mask[list(pool_codes)] = True
        pool_valid = broad_valid & pool_mask

        # size-matched control: nearest ln(mcap) non-pool twin, w/o replacement
        lp = np.log(mcap[pool_valid].dropna())
        cand = np.log(mcap[broad_valid & ~pool_mask].dropna()).sort_values()
        used, control = set(), []
        cand_idx, cand_vals = cand.index.to_numpy(), cand.to_numpy()
        for v in lp.to_numpy():
            j = int(np.searchsorted(cand_vals, v))
            for k in sorted(range(max(0, j - 3), min(len(cand_idx), j + 3)),
                            key=lambda x: abs(cand_vals[x] - v)):
                if cand_idx[k] not in used:
                    used.add(cand_idx[k]); control.append(cand_idx[k]); break
        ctrl_mask = pd.Series(False, index=fret.index)
        ctrl_mask[control] = True

        universes = {"pool": pool_valid, "ctrl": ctrl_mask & broad_valid, "broad": broad_valid}
        rec = {"date": t, "month": a["month"],
               "n_pool": int(pool_valid.sum()), "n_ctrl": int((ctrl_mask & broad_valid).sum()),
               "n_broad": int(broad_valid.sum())}

        for uname, umask in universes.items():
            # per-factor signed RankIC
            comp_rank = pd.Series(0.0, index=fret.index[umask]); comp_n = 0
            for f in FACTORS7:
                x = fvals[f][umask]; y = fret[umask]
                ok = x.notna() & y.notna()
                if ok.sum() >= MIN_NAMES:
                    ic = spearmanr(x[ok], y[ok]).statistic
                    rec[f"ic_{f}_{uname}"] = float(ic)
                # oriented pct-rank into composite (NaN-safe)
                r = x.rank(pct=True)
                if dirs[f] < 0:
                    r = 1.0 - r
                comp_rank = comp_rank.add(r.fillna(0.5), fill_value=0.0); comp_n += 1
            comp = comp_rank / comp_n
            y = fret[umask]; ok = comp.notna() & y.notna()
            if ok.sum() >= MIN_NAMES:
                rec[f"ic_composite_{uname}"] = float(spearmanr(comp[ok], y[ok]).statistic)
        rows.append(rec)

    det = pd.DataFrame(rows)
    det.to_parquet(OUT_DIR / "per_date_detail.parquet", index=False)
    print(f"[detail] {len(det)} usable rebalance dates", flush=True)

    # aggregate -> C9-allowlisted flat metrics
    metrics: dict[str, float | int] = {"n_obs": int(len(det)),
                                       "coverage_pool_mean": float(det["n_pool"].mean()),
                                       "coverage_ctrl_mean": float(det["n_ctrl"].mean()),
                                       "coverage_broad_mean": float(det["n_broad"].mean())}
    for uname in ("pool", "ctrl", "broad"):
        for f in FACTORS7 + ["composite"]:
            col = f"ic_{f}_{uname}"
            if col in det.columns and det[col].notna().sum() >= 12:
                s = det[col].dropna()
                metrics[f"rank_ic_mean_{f}_{uname}"] = float(s.mean())
                metrics[f"rank_icir_{f}_{uname}"] = float(s.mean() / s.std(ddof=1))
                metrics[f"n_obs_{f}_{uname}"] = int(len(s))

    report = build_phase0_report(
        metrics,
        universe="golden_stock_pool vs size-matched control vs broad",
        window=f"{det['date'].min().date()}..{det['date'].max().date()} (h={H}d, monthly at pool activation)",
        notes=("NON-FORMAL pool-level diagnostic; window overlaps spent-OOS 2021+; "
               "mints no factor-level evidence. Decision rule (pre-registered): pool adds "
               "value iff rank_icir_composite_pool >= rank_icir_composite_ctrl."),
    )
    (OUT_DIR / "phase0_report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    # console verdict table
    print("\n=== Phase-0 diagnostics (RankIC mean / RankICIR) ===", flush=True)
    for f in FACTORS7 + ["composite"]:
        line = f"{f:38s}"
        for uname in ("pool", "ctrl", "broad"):
            m = metrics.get(f"rank_ic_mean_{f}_{uname}")
            i = metrics.get(f"rank_icir_{f}_{uname}")
            line += f" | {uname}: " + (f"{m:+.3f}/{i:+.2f}" if m is not None else "   n/a    ")
        print(line, flush=True)
    icp, icc = metrics.get("rank_icir_composite_pool"), metrics.get("rank_icir_composite_ctrl")
    print(f"\nDECISION (pre-registered): composite ICIR pool={icp} vs ctrl={icc} -> "
          f"{'POOL ADDS VALUE' if (icp is not None and icc is not None and icp >= icc) else 'NO INCREMENT (pool fails)'}",
          flush=True)
    print(f"wrote -> {OUT_DIR / 'phase0_report.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
