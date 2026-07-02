"""#2 sm_01_成长_v1 — v2 construction upgrade from the 2026-07 T1 caliber campaign (NON-FORMAL parity).

SCRIPT_STATUS: Class-B parity diagnostic (kept). RESULT = NEGATIVE (v2 slightly WORSE than v1 at holdings
tracking: in25 0.733→0.727) — recorded as evidence that factor-standalone fidelity ≠ book-composite fidelity;
v1 construction stays canonical. See the run log in verify02_result.json + verify02b_holdcmp.parquet.

Two caliber fixes discovered by the per-factor campaign, applied to the validated verify_01/02 harness:
  1. 真实负债资产率 filter: the book's 10%-rank screen uses the VERIFIED 真实 caliber
     总负债/(总资产 − 商誉 − 无形资产 − 开发支出), NaN→0 on the intangibles (campaign: penny-exact,
     top-K 100%) — v1 used the plain 负债/资产, shifting the bottom-10% cutoff boundary.
  2. 股价振幅%当日成交额10日 (ILLIQ term): 果仁 internally QUANTIZES to 2dp — 76% of the universe ties at
     0.00 and shares one 排名分 (campaign: 3341/4412 tied at 排名分=100, 220 rank levels). v1 ranked at full
     precision, spreading the tied mass. v2 rounds to 2dp; rank(method='min') then reproduces the tie block.

Evaluation BEFORE any backtest: against 果仁's own per-period holdings (各阶段持仓详单), does the local
composite rank the 果仁-held names better under v2 than v1?  Metric per period-start: median local rank of
果仁-held names + share with rank<25 (the sell band) + share in top-20 (the buy band).
"""
from __future__ import annotations
import json, sys
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

OUT = ROOT / "workspace" / "outputs" / "guorn_parity"
CACHE = OUT / "verify01_cache"
SCHED_V1 = OUT / "verify02_schedule.json"
SCHED_V2 = OUT / "verify02b_schedule.json"
XLSX = ROOT / "Knowledge" / "果仁回测结果" / "05_sm_01_成长_v1.xlsx"

WEIGHTS = {"mktcap_ind": (2, -1), "mktcap_x": (3, -1), "CoreProfitQGr": (1, +1),
           "EpsExclXorGr": (1, +1), "ROETTMDiff": (1, +1), "ILLIQ": (1, +1)}


def build_zsfz_frame():
    """真实负债资产率 daily frame over the cached grid (fetch the 5 statement fields; NaN→0 intangibles)."""
    out_p = CACHE / "e_zsfz.parquet"
    if out_p.exists():
        print("[zsfz] cached e_zsfz.parquet found — reuse", flush=True)
        return
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(ROOT / "data" / "qlib_data"), region=REG_CN, kernels=1)
    grid = pd.read_parquet(CACHE / "e_close_raw.parquet").index
    insts = list(pd.read_parquet(CACHE / "e_close_raw.parquet").columns)
    fields = ["$total_liab_q0", "$total_assets_q0", "$goodwill_q0", "$intan_assets_q0", "$r_and_d_q0"]
    print(f"[zsfz] fetching {len(fields)} fields x {len(insts)} insts over {grid[0].date()}..{grid[-1].date()}", flush=True)
    df = D.features(insts, fields, start_time=str(grid[0].date()), end_time=str(grid[-1].date()), freq="day")
    P = {c.replace("$", ""): df[c].unstack(level=0).sort_index().reindex(grid).ffill() for c in fields}
    z = lambda fr: fr.fillna(0.0)
    denom = P["total_assets_q0"] - z(P["goodwill_q0"]) - z(P["intan_assets_q0"]) - z(P["r_and_d_q0"])
    zsfz = (P["total_liab_q0"] / denom.where(denom.abs() > 1e-9)).replace([np.inf, -np.inf], np.nan)
    zsfz.astype("float32").to_parquet(out_p)
    print(f"[zsfz] saved {out_p.name}  cov={zsfz.notna().mean().mean():.3f}", flush=True)


_orig_load = g1._load

def _load_v2():
    f, ind, e = _orig_load()
    f = dict(f)
    f["ILLIQ"] = f["ILLIQ"].round(2)                        # 果仁 2dp internal quantization (tie block)
    e = dict(e)
    e["debt_assets"] = pd.read_parquet(CACHE / "e_zsfz.parquet")   # 真实 caliber for the 10% rank screen
    return f, ind, e


def build_schedule_v2(start, end):
    g1.WEIGHTS = WEIGHTS
    g1.TOTAL_W = sum(w for w, _ in WEIGHTS.values())
    g1.CACHE = CACHE
    g1.SCHED = SCHED_V2
    g1._load = _load_v2
    g1.build_schedule(start, end, headroom=30)


def compare_vs_holdings(end="2026-02-27"):
    """Rank the 果仁-held names in each period's local composite (v1 vs v2 schedules are top-lists;
    rank = position in the schedule list; absent = worse than headroom)."""
    hold = pd.read_excel(XLSX, sheet_name="各阶段持仓详单")
    hold["start"] = pd.to_datetime(hold["开始日期"], errors="coerce")
    hold["code"] = hold["股票代码"].astype(str).str.zfill(6)
    hold = hold[(hold["start"].notna()) & (hold["start"] <= pd.Timestamp(end))]
    s1 = {pd.Timestamp(k): v for k, v in json.loads(SCHED_V1.read_text(encoding="utf-8")).items()}
    s2 = {pd.Timestamp(k): v for k, v in json.loads(SCHED_V2.read_text(encoding="utf-8")).items()}

    def code6(inst):
        return str(inst).split("_")[0].split(".")[0].zfill(6)

    rows = []
    for d, grp in hold.groupby("start"):
        held = set(grp["code"])
        for tag, s in (("v1", s1), ("v2", s2)):
            lst = s.get(d)
            if lst is None:
                continue
            order = {code6(c): i + 1 for i, c in enumerate(lst)}
            rks = [order.get(c, 999) for c in held]
            rows.append(dict(date=d, tag=tag, n=len(held),
                             med_rank=float(np.median(rks)),
                             in20=float(np.mean([r <= 20 for r in rks])),
                             in25=float(np.mean([r <= 25 for r in rks])),
                             in30=float(np.mean([r <= 30 for r in rks]))))
    df = pd.DataFrame(rows)
    if df.empty:
        print("[cmp] no overlapping periods")
        return
    agg = df.groupby("tag").agg(periods=("date", "nunique"), med_rank=("med_rank", "median"),
                                in20=("in20", "mean"), in25=("in25", "mean"), in30=("in30", "mean"))
    print("\n=== 果仁-held names vs local composite rank (lower med_rank / higher in-band = more faithful) ===")
    print(agg.to_string(float_format=lambda x: f"{x:.3f}"))
    # yearly split for diagnosis
    df["year"] = df["date"].dt.year
    piv = df.pivot_table(index="year", columns="tag", values="in25", aggfunc="mean")
    print("\nin25 by year:")
    print(piv.to_string(float_format=lambda x: f"{x:.3f}"))
    df.to_parquet(OUT / "verify02b_holdcmp.parquet")


SCHED_V3 = OUT / "verify02c_schedule.json"


def build_schedule_v3(start, end, headroom=30):
    """v3 = v1 construction + the miss-diagnosis fixes (2026-07-02):
      1. BOTH rank-band screens FLIPPED: 果仁 排名%区间 10%-100% ranks 从大到小 (rank1 = largest) → it drops
         the TOP decile (highest 负债率 / highest 乖离率). v1/v2 dropped the BOTTOM decile — inverted; the
         held-name percentile check is decisive (held names sit in my bottom decile 11-16% of the time,
         in the top decile ~0-5%; held p99 ≈ 0.86-0.92).
      2. The debt screen uses the VERIFIED 真实 caliber (e_zsfz), matching the book's 真实负债资产率.
      3. 上市天数>20 = CALENDAR days since listing (verified campaign caliber), not 20 local bars
         (the bar proxy over-excluded 次新 names 果仁 held — 359 misses in 2015 alone).
    Composite terms/weights = v1 canonical (full-precision ILLIQ: the v2 quantization was negative)."""
    import json as _json
    g1.WEIGHTS = WEIGHTS
    g1.TOTAL_W = sum(w for w, _ in WEIGHTS.values())
    f, ind, e = _orig_load()
    zsfz = pd.read_parquet(CACHE / "e_zsfz.parquet")
    cal = ru.trading_calendar()
    cal = cal[(cal >= pd.Timestamp(start)) & (cal <= pd.Timestamp(end))]
    close_raw, amt = e["close_raw"], e["amt"]
    amt5 = amt.rolling(5, min_periods=1).mean()
    amt20 = amt.rolling(20, min_periods=1).mean()
    insts = close_raw.columns
    bounds = g1.LISTED_BOUNDS
    list0 = {c: (bounds.get(str(c).upper())[0] if bounds.get(str(c).upper()) else pd.NaT) for c in insts}
    list0 = pd.Series(list0)
    grid = close_raw.index
    sched = {}
    for d in cal:
        d = pd.Timestamp(d)
        pos = grid.searchsorted(d)
        if pos == 0:
            sched[d] = []
            continue
        pday = grid[pos - 1]
        st = ru.st_codes_on(d)
        cr = close_raw.loc[pday]
        keep = cr.notna() & (cr >= 2.0)
        keep &= (amt5.loc[pday] > 5000.0) & (amt20.loc[pday] > 5000.0)
        cald = (pday - list0).dt.days + 1                             # 上市天数 (calendar, inclusive — verified)
        keep &= (cald > 20).fillna(False)
        listed = pd.Series([(bounds.get(str(c).upper()) is not None
                             and bounds[str(c).upper()][0] <= pday <= bounds[str(c).upper()][1]) for c in insts],
                           index=insts)
        keep &= listed
        keep &= pd.Series([str(c).upper() not in st for c in insts], index=insts)
        da = zsfz.loc[pday]
        bz = e["bias120"].loc[pday]
        keep &= ~(da.rank(pct=True) > 0.90).fillna(False)             # drop TOP decile 真实负债率 (flip + NaN keep)
        keep &= ~(bz.rank(pct=True) > 0.90).fillna(False)             # drop TOP decile 乖离率120 (flip)
        elig = keep[keep].index
        if len(elig) < headroom:
            sched[d] = []
            continue
        comp = g1._composite_row(f, ind, pday, elig).dropna()
        top = comp.sort_values(ascending=False).head(headroom)
        sched[d] = [str(c).upper().replace("_", ".") for c in top.index]
    SCHED_V3.write_text(_json.dumps({str(k.date()): v for k, v in sched.items()}, ensure_ascii=False),
                        encoding="utf-8")
    nonempty = sum(1 for v in sched.values() if v)
    print(f"[sched-v3] {nonempty}/{len(cal)} non-empty; saved {SCHED_V3.name}", flush=True)


def compare_v3(end="2026-02-27"):
    """Holdings tracking: v1 vs v3 (same metric as compare_vs_holdings)."""
    hold = pd.read_excel(XLSX, sheet_name="各阶段持仓详单")
    hold["start"] = pd.to_datetime(hold["开始日期"], errors="coerce")
    hold["code"] = hold["股票代码"].astype(str).str.zfill(6)
    hold = hold[(hold["start"].notna()) & (hold["start"] <= pd.Timestamp(end))]
    s1 = {pd.Timestamp(k): v for k, v in json.loads(SCHED_V1.read_text(encoding="utf-8")).items()}
    s3 = {pd.Timestamp(k): v for k, v in json.loads(SCHED_V3.read_text(encoding="utf-8")).items()}

    def code6(inst):
        return str(inst).split("_")[0].split(".")[0].zfill(6)

    rows = []
    for d, grp in hold.groupby("start"):
        held = set(grp["code"])
        for tag, s in (("v1", s1), ("v3", s3)):
            lst = s.get(d)
            if lst is None:
                continue
            order = {code6(c): i + 1 for i, c in enumerate(lst)}
            rks = [order.get(c, 999) for c in held]
            rows.append(dict(date=d, tag=tag, in25=float(np.mean([r <= 25 for r in rks]))))
    df = pd.DataFrame(rows)
    df["year"] = df["date"].dt.year
    piv = df.pivot_table(index="year", columns="tag", values="in25", aggfunc="mean")
    print("\nin25 by year (v1 vs v3):")
    print(piv.to_string(float_format=lambda x: f"{x:.3f}"))
    print("\noverall:", df.groupby("tag")["in25"].mean().round(3).to_dict())


def run_v3(start="2014-01-01", end="2026-02-27"):
    from src.backtest_engine.event_driven import EventDrivenBacktester, CostConfig
    from src.backtest_engine.event_driven.exchange import FixedSlippage
    from guorn_parity_rung2_posprofit import ModelIIPosProfitStrategy
    sched = {pd.Timestamp(k): v for k, v in json.loads(SCHED_V3.read_text(encoding="utf-8")).items()}
    strat = ModelIIPosProfitStrategy(sched, buy_rank=20, sell_rank=25, target_n=10, pos_max=0.13,
                                     max_holds=15, use_exits=False, rebuy_cooldown=0)
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
    net.to_frame("net").to_parquet(OUT / "verify02c_net.parquet")
    m = ru.goal_metrics(net)
    yr = net.groupby(net.index.year).apply(lambda r: (1 + r).prod() - 1)
    gdf = pd.read_excel(XLSX, sheet_name="年度收益统计", header=0)
    gy = {}
    for _, r in gdf.iterrows():
        try:
            y = int(str(r.iloc[0])[:4])
        except Exception:
            continue
        v = pd.to_numeric(r.iloc[1], errors="coerce")
        if pd.notna(v):
            gy[int(y)] = float(v)
    print("\n" + "=" * 74)
    print(f"  #2 v3 (screen fixes)  CAGR={m['cagr']:+.2%}  MDD={m['mdd']:+.2%}")
    print("  year     v3-LOCAL     果仁      diff")
    for y in sorted(yr.index):
        g = gy.get(int(y))
        gt = f"{g:+8.1%}" if g is not None else "   n/a "
        dt = f"{float(yr[y]) - g:+7.1%}" if g is not None else ""
        print(f"  {int(y)}   {float(yr[y]):+8.1%}  {gt}  {dt}")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-zsfz", action="store_true")
    ap.add_argument("--schedule", action="store_true")
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--schedule-v3", action="store_true")
    ap.add_argument("--compare-v3", action="store_true")
    ap.add_argument("--run-v3", action="store_true")
    ap.add_argument("--start", default="2014-01-01")
    ap.add_argument("--end", default="2026-02-27")
    a = ap.parse_args()
    if a.build_zsfz:
        build_zsfz_frame()
    if a.schedule:
        build_schedule_v2(a.start, a.end)
    if a.compare:
        compare_vs_holdings(a.end)
    if a.schedule_v3:
        build_schedule_v3(a.start, a.end)
    if a.compare_v3:
        compare_v3(a.end)
    if a.run_v3:
        run_v3(a.start, a.end)


if __name__ == "__main__":
    main()
