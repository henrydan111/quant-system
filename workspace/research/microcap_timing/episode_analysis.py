# SCRIPT_STATUS: ACTIVE — research utility (microcap timing replication, 2026-06-11)
"""Episode-level decomposition of the MA5/MA200 timing on the microcap replica.

For every flat (out-of-market) episode: what the exit cost before it triggered,
what the index did while flat (avoided return -> relative edge), and what re-entry
missed. Also: every >=15% index drawdown episode and how much of it was spent
in-market (the 'uncaught crash' table).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUT = PROJECT_ROOT / "workspace" / "outputs" / "microcap_timing"
EVAL_START = "2014-01-02"

out = pd.read_parquet(OUT / "guoren_microcap_replica.parquet")
level, ret = out["level"], out["ret"].fillna(0)
ma5, ma200 = level.rolling(5).mean(), level.rolling(200).mean()
sig = (ma5 > ma200).astype(int)
pos = sig.shift(1).fillna(0)

ev_idx = out.loc[EVAL_START:].index
pos_ev = pos.loc[ev_idx]

# ---- flat episodes ----
rows = []
arr = pos_ev.to_numpy()
dates = pos_ev.index
i = 0
while i < len(arr):
    if arr[i] == 0:
        j = i
        while j + 1 < len(arr) and arr[j + 1] == 0:
            j += 1
        flat_days = dates[i : j + 1]
        avoided = float((1 + ret.loc[flat_days]).prod() - 1)
        edge = 1.0 / (1.0 + avoided) - 1.0  # relative gain of flat vs holding
        last_in = dates[i - 1] if i > 0 else None
        if last_in is not None:
            hist = level.loc[:last_in].iloc[-252:]
            dd_at_exit = float(level.loc[last_in] / hist.max() - 1)
        else:
            dd_at_exit = np.nan
        # what the first 20 days after re-entry did (re-entry quality)
        after = ret.loc[dates[j] :].iloc[1:21]
        post20 = float((1 + after).prod() - 1) if len(after) else np.nan
        rows.append(
            {
                "flat_start": str(dates[i].date()),
                "flat_end": str(dates[j].date()),
                "n_days": j - i + 1,
                "dd_at_exit_pct": round(dd_at_exit * 100, 1),
                "idx_move_while_flat_pct": round(avoided * 100, 1),
                "rel_edge_pct": round(edge * 100, 1),
                "idx_20d_after_reentry_pct": round(post20 * 100, 1),
            }
        )
        i = j + 1
    else:
        i += 1

ep = pd.DataFrame(rows)
ep.to_csv(OUT / "timing_episodes.csv", index=False)
print("=== flat episodes (exit already effective; dd_at_exit = drawdown vs 1y high when exit triggered) ===")
print(ep.to_string(index=False))
print(
    "\nepisodes: %d | winners (edge>0): %d | losers: %d | sum edge (pp, non-compound): %.1f"
    % (len(ep), (ep.rel_edge_pct > 0).sum(), (ep.rel_edge_pct <= 0).sum(), ep.rel_edge_pct.sum())
)

# ---- uncaught crash table: index drawdown episodes >= 15% within eval window ----
lv_ev = level.loc[ev_idx] / level.loc[ev_idx].iloc[0]
cummax = lv_ev.cummax()
dd = lv_ev / cummax - 1
crash_rows = []
in_dd = False
for t in range(1, len(dd)):
    if not in_dd and dd.iloc[t] < -0.15:
        in_dd = True
        peak_t = lv_ev.iloc[: t + 1].idxmax()
    if in_dd and dd.iloc[t] == 0:
        in_dd = False
if True:
    # simpler: find troughs of each excursion below -15%
    below = dd < -0.15
    grp = (below != below.shift()).cumsum()
    for g, seg in dd.groupby(grp):
        if not below.loc[seg.index[0]]:
            continue
        trough = seg.idxmin()
        peak = lv_ev.loc[:trough].idxmax()
        depth = float(dd.loc[trough])
        seg_days = lv_ev.loc[peak:trough].index
        in_mkt = float(pos.loc[seg_days].mean())
        timed_seg = float((1 + (ret.loc[seg_days] * pos.loc[seg_days])).prod() - 1)
        crash_rows.append(
            {
                "peak": str(peak.date()),
                "trough": str(trough.date()),
                "idx_depth_pct": round(depth * 100, 1),
                "pct_days_in_market": round(in_mkt * 100),
                "timed_ret_same_window_pct": round(timed_seg * 100, 1),
            }
        )
cr = pd.DataFrame(crash_rows).drop_duplicates(subset=["peak"]).sort_values("peak")
print("\n=== index drawdown episodes >= 15% (peak->trough) and what the timed book did ===")
print(cr.to_string(index=False))

# ---- 2016-01 check: closest MA5-vs-MA200 approach, was it ever flat? ----
w = pd.DataFrame({"ma5": ma5, "ma200": ma200}).loc["2016-01-01":"2016-03-31"]
gap = (w["ma5"] / w["ma200"] - 1) * 100
print("\n2016-01..03 min MA5 vs MA200 gap: %.1f%% on %s (never crossed: %s)"
      % (gap.min(), gap.idxmin().date(), bool((gap > 0).all())))

# ---- state at data end ----
end = level.index[-1]
print("\nat data end %s: index vs MA200 gap %.1f%%, signal=%d"
      % (end.date(), (level.iloc[-1] / ma200.iloc[-1] - 1) * 100, int(sig.iloc[-1])))
