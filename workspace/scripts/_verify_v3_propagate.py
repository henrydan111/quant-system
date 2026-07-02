"""Propagate the #2-validated v3 screen fixes to #1 (sm_01_成长动量) and #6 (sm_01_成长高贝塔@TMT_v1).

SCRIPT_STATUS: Class-B parity diagnostic (kept). The fixes (validated on #2: in25 0.733→0.893, CAGR
50.1%→58.32% vs 果仁 58.20%):
  1. 排名%区间 10%-100% = drop the TOP decile (rank 从大到小), NOT the bottom — applies to
     真实负债资产率+乖离率120 (#1) and 乖离率60 (#6, no debt screen).
  2. debt screen on the verified 真实 caliber (e_zsfz) — #1 only.
  3. 上市天数>20 = CALENDAR days since listing (campaign-verified), not 20 local bars.
Composites/weights/trade models = each book's canonical harness (g1 default 9-term; g6 8-term TMT).
NON-FORMAL parity artifacts.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "workspace" / "research" / "long_only_50cagr"))
sys.path.insert(0, str(ROOT / "workspace" / "scripts"))
sys.stdout.reconfigure(encoding="utf-8")

import research_utils as ru                                          # noqa: E402
import guorn_verify_01_growth as g1                                  # noqa: E402
import guorn_verify_06_growth as g6                                  # noqa: E402
from guorn_parity_rung2_posprofit import ModelIIPosProfitStrategy    # noqa: E402

OUT = ROOT / "workspace" / "outputs" / "guorn_parity"
CACHE = OUT / "verify01_cache"


def _yearly_from_xlsx(xlsx):
    df = pd.read_excel(xlsx, sheet_name="年度收益统计", header=0)
    out = {}
    for _, r in df.iterrows():
        try:
            y = int(str(r.iloc[0])[:4])
        except Exception:
            continue
        v = pd.to_numeric(r.iloc[1], errors="coerce")
        if pd.notna(v):
            out[y] = float(v)
    return out


def _base_screens(e, zsfz, pday, d, insts, bounds):
    st = ru.st_codes_on(d)
    cr = e["close_raw"].loc[pday]
    keep = cr.notna() & (cr >= 2.0)
    amt5 = e["_amt5"].loc[pday]
    amt20 = e["_amt20"].loc[pday]
    keep &= (amt5 > 5000.0) & (amt20 > 5000.0)
    list0 = e["_list0"]
    cald = (pday - list0).dt.days + 1
    keep &= (cald > 20).fillna(False)
    listed = pd.Series([(bounds.get(str(c).upper()) is not None
                         and bounds[str(c).upper()][0] <= pday <= bounds[str(c).upper()][1]) for c in insts],
                       index=insts)
    keep &= listed
    keep &= pd.Series([str(c).upper() not in st for c in insts], index=insts)
    return keep




def build_onmom_v2():
    """onmom250/120 v2: min_periods=1 on all rolling sums (果仁 SUM(x,N) sums AVAILABLE bars for young
    stocks; the v1 frames' min_periods 120/60/10 NaN-ed 次新 names (21-119 bars) that the v3 calendar
    screen now admits -> they bottom-ranked locally while 果仁 ranks their partial sums normally)."""
    out250 = CACHE / "f_onmom250_v2.parquet"
    out120 = CACHE / "f_onmom120_v2.parquet"
    if out250.exists() and out120.exists():
        print("[onmomv2] cached — reuse", flush=True)
        return
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(ROOT / "data" / "qlib_data"), region=REG_CN, kernels=1)
    grid = pd.read_parquet(CACHE / "e_close_raw.parquet").index
    insts = list(pd.read_parquet(CACHE / "e_close_raw.parquet").columns)
    fields = ["$open", "$close", "$adj_factor", "$limit_status"]
    df = D.features(insts, fields, start_time=str(grid[0].date()), end_time=str(grid[-1].date()), freq="day")
    P = {c.replace("$", ""): df[c].unstack(level=0).sort_index().reindex(grid) for c in fields}
    adjc = P["close"] * P["adj_factor"]
    adjo = P["open"] * P["adj_factor"]
    onret = np.log((adjo / adjc.shift(1)).where(lambda x: x > 0))
    onret = onret.where(P["limit_status"] != 1, 0.0)
    s20 = onret.rolling(20, min_periods=1).sum()
    (onret.rolling(250, min_periods=1).sum() - s20).astype("float32").to_parquet(out250)
    (onret.rolling(120, min_periods=1).sum() - s20).astype("float32").to_parquet(out120)
    print("[onmomv2] saved f_onmom250_v2 + f_onmom120_v2", flush=True)

def build_schedule(book, start, end, variant="v3"):
    if book == 1:
        f, ind, e = g1._load()                                       # g1 default 9-term WEIGHTS
        comp_row, weights_mod = g1._composite_row, g1
        zsfz = pd.read_parquet(CACHE / "e_zsfz.parquet")
        bias = e["bias120"]
        headroom = 30
        sched_path = OUT / ("verify01d_schedule.json" if variant == "v4" else "verify01c_schedule.json")
        if variant == "v4":
            f = dict(f)
            f["ROETTMDiff"] = pd.read_parquet(CACHE / "f_ROETTMDiff_v2.parquet")
            f["onmom250"] = pd.read_parquet(CACHE / "f_onmom250_v2.parquet")
            f["onmom120"] = pd.read_parquet(CACHE / "f_onmom120_v2.parquet")
        tmt = None
    else:
        f, ind, e = g6._load()
        comp_row, weights_mod = g6._composite_row, g6
        zsfz = None
        bias = e["bias60"]
        headroom, sched_path = 20, OUT / "verify06c_schedule.json"
        tmt = g6.TMT_L1
    bounds = g1.LISTED_BOUNDS
    insts = e["close_raw"].columns
    e["_amt5"] = e["amt"].rolling(5, min_periods=1).mean()
    e["_amt20"] = e["amt"].rolling(20, min_periods=1).mean()
    e["_list0"] = pd.Series({c: (bounds.get(str(c).upper())[0] if bounds.get(str(c).upper()) else pd.NaT)
                             for c in insts})
    cal = ru.trading_calendar()
    cal = cal[(cal >= pd.Timestamp(start)) & (cal <= pd.Timestamp(end))]
    grid = e["close_raw"].index
    sched = {}
    for d in cal:
        d = pd.Timestamp(d)
        pos = grid.searchsorted(d)
        if pos == 0:
            sched[d] = []
            continue
        pday = grid[pos - 1]
        keep = _base_screens(e, zsfz, pday, d, insts, bounds)
        if tmt is not None:
            indrow = ind.loc[pday]
            keep &= pd.Series([indrow.get(c) in tmt for c in insts], index=insts)
        if zsfz is not None:
            keep &= ~(zsfz.loc[pday].rank(pct=True) > 0.90).fillna(False)     # drop TOP decile 真实负债率
        keep &= ~(bias.loc[pday].rank(pct=True) > 0.90).fillna(False)         # drop TOP decile 乖离率
        elig = keep[keep].index
        if len(elig) < headroom:
            sched[d] = []
            continue
        comp = comp_row(f, ind, pday, elig).dropna()
        top = comp.sort_values(ascending=False).head(headroom)
        sched[d] = [str(c).upper().replace("_", ".") for c in top.index]
    sched_path.write_text(json.dumps({str(k.date()): v for k, v in sched.items()}, ensure_ascii=False),
                          encoding="utf-8")
    nonempty = sum(1 for v in sched.values() if v)
    print(f"[sched-v3 #{book}] {nonempty}/{len(cal)} non-empty; saved {sched_path.name}", flush=True)


def run(book, start, end, variant="v3"):
    from src.backtest_engine.event_driven import EventDrivenBacktester, CostConfig
    from src.backtest_engine.event_driven.exchange import FixedSlippage
    if book == 1:
        if variant == "v4":
            sched_path, net_name, label = OUT / "verify01d_schedule.json", "verify01d_net.parquet", "#1 sm_01_成长动量 v4(roev2+onmom)"
        else:
            sched_path, net_name, label = OUT / "verify01c_schedule.json", "verify01c_net.parquet", "#1 sm_01_成长动量 v3"
        params = dict(buy_rank=20, sell_rank=25, target_n=10, pos_max=0.13, max_holds=15)
        xlsx = g1.XLSX
    else:
        sched_path, net_name = OUT / "verify06c_schedule.json", "verify06c_net.parquet"
        params = dict(buy_rank=20, sell_rank=15, target_n=7, pos_max=0.225, max_holds=13)
        xlsx, label = g6.XLSX, "#6 sm_01_成长高贝塔@TMT v3"
        _ = variant
    sched = {pd.Timestamp(k): v for k, v in json.loads(sched_path.read_text(encoding="utf-8")).items()}
    strat = ModelIIPosProfitStrategy(sched, use_exits=False, rebuy_cooldown=0, **params)
    cost = CostConfig(buy_commission=0.002, sell_commission=0.002, stamp_tax=0.0, min_commission=0.0,
                      transfer_fee=0.0)
    bt = EventDrivenBacktester(data_dir=str(ROOT / "data"))
    res = bt.run(strategy=strat, start_time=start, end_time=end, benchmark="000300.SH", account=1_000_000.0,
                 exchange_config=cost, slippage=FixedSlippage(0.0), volume_limit=0.10, hold_on_limit_up=True,
                 preload_fields=["$open", "$close", "$high", "$low", "$vol", "$amount", "$pre_close",
                                 "$adj_factor", "$up_limit", "$down_limit"])
    rep = res.report.copy()
    if "date" in rep.columns:
        rep = rep.set_index(pd.to_datetime(rep["date"]))
    net = rep["return"].astype(float)
    net.to_frame("net").to_parquet(OUT / net_name)
    m = ru.goal_metrics(net)
    yr = net.groupby(net.index.year).apply(lambda r: (1 + r).prod() - 1)
    gy = _yearly_from_xlsx(xlsx)
    print("\n" + "=" * 72)
    print(f"  {label}  CAGR={m['cagr']:+.2%}  MDD={m['mdd']:+.2%}")
    print("  year     v3-LOCAL     果仁      diff")
    for y in sorted(yr.index):
        g = gy.get(int(y))
        gt = f"{g:+8.1%}" if g is not None else "   n/a "
        dt = f"{float(yr[y]) - g:+7.1%}" if g is not None else ""
        print(f"  {int(y)}   {float(yr[y]):+8.1%}  {gt}  {dt}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", type=int, choices=(1, 6), required=True)
    ap.add_argument("--schedule", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--variant", default="v3", choices=("v3", "v4"))
    ap.add_argument("--build-onmom-v2", action="store_true")
    ap.add_argument("--start", default="2014-01-01")
    ap.add_argument("--end", default="2026-02-27")
    a = ap.parse_args()
    if a.build_onmom_v2:
        build_onmom_v2()
    if a.schedule:
        build_schedule(a.book, a.start, a.end, a.variant)
    if a.run:
        run(a.book, a.start, a.end, a.variant)


if __name__ == "__main__":
    main()
