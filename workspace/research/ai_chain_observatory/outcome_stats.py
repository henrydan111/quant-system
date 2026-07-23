# SCRIPT_STATUS: ACTIVE — AI 链路观察站 Block E:打分 outcome 分桶统计器(Class-D,非证据)
"""C1 v0 (DSA_INTEGRATION_PLAN Track C):AI 打分 vs 前向收益的只读诊断统计。

两条腿(全部 NON_EVIDENTIARY_PILOT,不构成 alpha 证据,不消耗任何 seal):
  leg-obs   202501 观察站重放的 16 个决策日逐日评分(combined/text/anon/fund/quant)
            → 逐日横截面 RankIC(主指标,我们的母语)+ 五分位 Q5−Q1 价差 +
            相对命中率(顶部五分位跑赢当日池中位数的概率)+ 三个分桶:
            no_text(输入覆盖)/in_floor(量化前50)/named-vs-anon(名称偏置消融)
  leg-chain 20250127 分析师链(五席)单日横截面:composite_adj + 各席 final vs
            前向收益;divergence 旗/空头折减/dispersion 分桶。单日无统计力,
            仅方向性观察,报告中必须如此标注。

口径:
  - leg-obs 决策于 D 日开盘前 → 入场 = open(D);r_h = open(D+h)/open(D) − 1。
  - leg-chain 链消费 D 日收盘后卡片 → 入场 = open(D+1);
    r_h = open(D+1+h)/open(D+1) − 1。h ∈ {1,3,5,10,20} 交易日。
  - 价格 = provider 前复权 open($open×$adj_factor),同 run_paper_sim 口径。
  - 毛收益、无成本——这是"信号是否有序"的诊断,不是账本;账本级看 paper_sim。
  - h≥5 的逐日 IC 序列存在窗口重叠自相关,ICIR 只作横向比较,不作 t 检验。

C16 围栏:本工具输出为只读诊断,禁止回流任何 prompt/权重/选股逻辑;
若未来要据此调整链路,必须走 C16b 注册 + 新前向纪元。
用法: venv/Scripts/python.exe workspace/research/ai_chain_observatory/outcome_stats.py
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from data_infra.provider_metadata import tushare_to_qlib_canonical  # noqa: E402

OBS_DAILY = PROJECT_ROOT / "workspace" / "outputs" / "ai_chain_observatory" / "daily"
CHAIN_ROOT = (PROJECT_ROOT / "workspace" / "outputs" / "ai_research_dept"
              / "analyst_chain")
OUT_DIR = (PROJECT_ROOT / "workspace" / "outputs" / "ai_chain_observatory"
           / "outcome_stats")
EVIDENCE_CLASS = "NON_EVIDENTIARY_PILOT"
HORIZONS = (1, 3, 5, 10, 20)
OBS_SCORES = ("combined", "text_final", "anon_final", "fund_final", "quant_score")
CHAIN_DAY = "20250127"
PRICE_END = "20250331"          # covers 20 trading days past 20250127 (含春节休市)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("outcome_stats")


# ------------------------------------------------------------------ data
def load_obs_scorecards() -> pd.DataFrame:
    parts = []
    for p in sorted(OBS_DAILY.glob("*/scorecards.parquet")):
        parts.append(pd.read_parquet(p))
    if not parts:
        raise RuntimeError("no observatory scorecards — run run_chain_replay.py first")
    df = pd.concat(parts, ignore_index=True)
    df["no_text"] = df["n_chars"].fillna(0) <= 0
    return df


def pick_chain_version() -> tuple[str, Path]:
    """Prefer the newest chain version whose CHAIN_DAY dir holds a full pool
    of complete archives (>=140)."""
    candidates = sorted(CHAIN_ROOT.glob("chain_v*"), reverse=True,
                        key=lambda p: [int(x) for x in
                                       p.name.replace("chain_v", "").split(".")])
    for vdir in candidates:
        day = vdir / CHAIN_DAY
        if day.is_dir() and len(list(day.glob("*.json"))) >= 140:
            return vdir.name, day
    raise RuntimeError(f"no chain version has a full {CHAIN_DAY} archive set")


def load_chain_cross_section() -> tuple[str, pd.DataFrame]:
    version, day_dir = pick_chain_version()
    rows = []
    for p in sorted(day_dir.glob("*.json")):
        a = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(a, dict) or "judge" not in a:
            continue
        j = a["judge"]
        finals = j.get("finals", {}) or {}
        adj = j.get("adj_finals", {}) or {}
        div = j.get("divergence_flags") or []
        disc = j.get("bear_discounts") or {}
        rows.append({
            "ts_code": str(a.get("ts_code", "")),
            "complete": bool(a.get("complete", False)),
            "composite": j.get("composite"),
            "composite_adj": j.get("composite_adj"),
            "fund_final": finals.get("fund"), "tech_final": finals.get("tech"),
            "news_final": finals.get("news"),
            "fund_adj": adj.get("fund"), "tech_adj": adj.get("tech"),
            "news_adj": adj.get("news"),
            "dispersion": j.get("dispersion"),
            "divergent": bool(div) if not isinstance(div, dict) else bool(
                any(div.values())),
            "bear_discounted": bool(disc) if not isinstance(disc, dict) else bool(
                any(disc.values())),
        })
    df = pd.DataFrame(rows)
    df = df[df["complete"] & df["ts_code"].astype(bool)].reset_index(drop=True)
    if len(df) < 100:
        raise RuntimeError(f"chain cross-section too small: {len(df)}")
    return version, df


def adj_open_matrix(codes: list[str], start: str, end: str) -> pd.DataFrame:
    """provider 前复权 open,index=YYYYMMDD 交易日,columns=ts_code(同 run_paper_sim)。"""
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(PROJECT_ROOT / "data" / "qlib_data"),
              region=REG_CN, kernels=1)
    avail = {i.upper(): i for i in D.list_instruments(
        D.instruments("all"), start_time=start, end_time=end, as_list=True)}
    qmap = {c: avail[tushare_to_qlib_canonical(c)] for c in codes
            if tushare_to_qlib_canonical(c) in avail}
    df = D.features(list(qmap.values()), ["$open", "$adj_factor"],
                    start_time=start, end_time=end, freq="day")
    adj = (df["$open"] * df["$adj_factor"]).unstack(level=0)
    back = {v: k for k, v in qmap.items()}
    adj.columns = [back.get(str(c), str(c)) for c in adj.columns]
    adj.index = [d.strftime("%Y%m%d") for d in adj.index]
    return adj


def forward_returns(adj: pd.DataFrame, day: str, entry_offset: int,
                    horizon: int) -> pd.Series:
    """r = open(pos+entry_offset+horizon)/open(pos+entry_offset) − 1,按交易日位置。"""
    if day not in adj.index:
        return pd.Series(dtype=float)
    pos = adj.index.get_loc(day)
    i0, i1 = pos + entry_offset, pos + entry_offset + horizon
    if i1 >= len(adj.index):
        return pd.Series(dtype=float)
    return adj.iloc[i1] / adj.iloc[i0] - 1.0


# ------------------------------------------------------------------ metrics
def rank_ic(score: pd.Series, ret: pd.Series) -> float | None:
    df = pd.concat([score, ret], axis=1, keys=["s", "r"]).dropna()
    if len(df) < 20 or df["s"].nunique() < 3:
        return None
    return float(df["s"].rank().corr(df["r"].rank()))


def quintile_spread(score: pd.Series, ret: pd.Series) -> float | None:
    df = pd.concat([score, ret], axis=1, keys=["s", "r"]).dropna()
    if len(df) < 25 or df["s"].nunique() < 5:
        return None
    q = pd.qcut(df["s"].rank(method="first"), 5, labels=False)
    return float(df.loc[q == 4, "r"].mean() - df.loc[q == 0, "r"].mean())


def top_q_beats_median(score: pd.Series, ret: pd.Series) -> float | None:
    """相对命中率:顶部五分位名字中,前向收益跑赢当日池中位数的比例。"""
    df = pd.concat([score, ret], axis=1, keys=["s", "r"]).dropna()
    if len(df) < 25:
        return None
    med = df["r"].median()
    top = df[df["s"] >= df["s"].quantile(0.8)]
    if top.empty:
        return None
    return float((top["r"] > med).mean())


def summarize_ic_series(vals: list[float]) -> dict:
    arr = np.array([v for v in vals if v is not None and np.isfinite(v)])
    if arr.size == 0:
        return {"n": 0}
    return {"n": int(arr.size), "mean": round(float(arr.mean()), 4),
            "std": round(float(arr.std(ddof=1)), 4) if arr.size > 1 else None,
            "icir": (round(float(arr.mean() / arr.std(ddof=1)), 3)
                     if arr.size > 1 and arr.std(ddof=1) > 0 else None),
            "pct_positive": round(float((arr > 0).mean()), 3)}


# ------------------------------------------------------------------ legs
def run_leg_obs(sc: pd.DataFrame, adj: pd.DataFrame) -> dict:
    days = sorted(sc["trade_date"].unique())
    daily_rows, per_score = [], {s: {h: [] for h in HORIZONS} for s in OBS_SCORES}
    spread = {s: {h: [] for h in HORIZONS} for s in OBS_SCORES}
    hitrate = {s: {h: [] for h in HORIZONS} for s in OBS_SCORES}
    bucket_ic = {"has_text": {h: [] for h in HORIZONS},
                 "in_floor": {h: [] for h in HORIZONS}}
    no_text_excess, corr_combined_quant = [], []
    for day in days:
        g = sc[sc["trade_date"] == day].set_index("ts_code")
        rets = {h: forward_returns(adj, day, 0, h) for h in HORIZONS}
        cq = pd.concat([g["combined"], g["quant_score"]], axis=1).dropna()
        if len(cq) >= 20:
            corr_combined_quant.append(
                float(cq["combined"].rank().corr(cq["quant_score"].rank())))
        for s in OBS_SCORES:
            for h in HORIZONS:
                r = rets[h].reindex(g.index)
                ic = rank_ic(g[s], r)
                per_score[s][h].append(ic)
                spread[s][h].append(quintile_spread(g[s], r))
                hitrate[s][h].append(top_q_beats_median(g[s], r))
                if ic is not None:
                    daily_rows.append({"day": day, "score": s, "horizon": h,
                                       "rank_ic": round(ic, 4)})
        # 分桶:有文本 vs 全部;floor 内
        for h in HORIZONS:
            r = rets[h].reindex(g.index)
            bucket_ic["has_text"][h].append(
                rank_ic(g.loc[~g["no_text"], "combined"], r[~g["no_text"]]))
            bucket_ic["in_floor"][h].append(
                rank_ic(g.loc[g["in_floor"], "combined"], r[g["in_floor"]]))
            if h == 5:
                r5 = r
        # no_text 名字的超额(相对当日池均值,h=5)
        r5 = rets[5].reindex(g.index)
        if g["no_text"].any() and r5.notna().sum() >= 25:
            no_text_excess.append(
                float(r5[g["no_text"]].mean() - r5.mean()))
    summary = {
        "days": days, "n_days": len(days),
        "rank_ic": {s: {str(h): summarize_ic_series(per_score[s][h])
                        for h in HORIZONS} for s in OBS_SCORES},
        "q5_minus_q1": {s: {str(h): summarize_ic_series(spread[s][h])
                            for h in HORIZONS} for s in OBS_SCORES},
        "top_quintile_beats_median": {
            s: {str(h): summarize_ic_series(hitrate[s][h])
                for h in HORIZONS} for s in OBS_SCORES},
        "bucket_rank_ic_combined": {
            b: {str(h): summarize_ic_series(bucket_ic[b][h]) for h in HORIZONS}
            for b in bucket_ic},
        "no_text_excess_h5": summarize_ic_series(no_text_excess),
        "rank_corr_combined_vs_quant": summarize_ic_series(corr_combined_quant),
        "named_minus_anon_delta": {
            "mean": round(float(sc["delta_named_minus_anon"].mean()), 3),
            "abs_mean": round(float(sc["delta_named_minus_anon"].abs().mean()), 3),
        },
    }
    return {"daily": pd.DataFrame(daily_rows), "summary": summary}


def run_leg_chain(cs: pd.DataFrame, adj: pd.DataFrame) -> dict:
    cs = cs.set_index("ts_code")
    scores = ["composite_adj", "composite", "fund_final", "tech_final",
              "news_final", "fund_adj", "tech_adj", "news_adj"]
    out: dict = {"day": CHAIN_DAY, "n_names": int(len(cs)),
                 "entry": "open(D+1)", "rank_ic": {}, "buckets": {}}
    rets = {h: forward_returns(adj, CHAIN_DAY, 1, h).reindex(cs.index)
            for h in HORIZONS}
    for s in scores:
        out["rank_ic"][s] = {str(h): (round(v, 4) if (v := rank_ic(cs[s], rets[h]))
                                      is not None else None) for h in HORIZONS}
    for flag in ("divergent", "bear_discounted"):
        grp = {}
        for h in (5, 20):
            r = rets[h]
            a, b = r[cs[flag]], r[~cs[flag]]
            grp[str(h)] = {"n_flagged": int(cs[flag].sum()),
                           "flagged_mean_ret": (round(float(a.mean()), 4)
                                                if a.notna().any() else None),
                           "unflagged_mean_ret": (round(float(b.mean()), 4)
                                                  if b.notna().any() else None)}
        out["buckets"][flag] = grp
    disp = cs["dispersion"].astype(float)
    ter = pd.qcut(disp.rank(method="first"), 3, labels=["low", "mid", "high"])
    out["buckets"]["dispersion_terciles_h5"] = {
        str(t): round(float(rets[5][ter == t].mean()), 4)
        for t in ("low", "mid", "high") if rets[5][ter == t].notna().any()}
    return out


def main() -> int:
    sc = load_obs_scorecards()
    version, cs = load_chain_cross_section()
    codes = sorted(set(sc["ts_code"]) | set(cs["ts_code"]))
    start = min(sc["trade_date"].min(), CHAIN_DAY)
    log.info("obs days=%d rows=%d | chain %s names=%d | prices %s..%s (%d codes)",
             sc["trade_date"].nunique(), len(sc), version, len(cs),
             start, PRICE_END, len(codes))
    adj = adj_open_matrix(codes, start, PRICE_END)
    dropped = sorted(set(codes) - set(adj.columns))
    if dropped:
        log.warning("no price series for %d codes (dropped): %s...",
                    len(dropped), dropped[:5])

    obs = run_leg_obs(sc, adj)
    chain = run_leg_chain(cs, adj)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    obs["daily"].to_parquet(OUT_DIR / "obs202501_daily_ic.parquet", index=False)
    payload = {"evidence_class": EVIDENCE_CLASS,
               "generated_by": "outcome_stats.py (C1 v0)",
               "price_basis": "provider adj open (open*adj_factor), gross, no cost",
               "caveats": [
                   "202501 单月/单日样本,诊断性观察,非 alpha 证据",
                   "h>=5 的逐日 IC 存在窗口重叠自相关,ICIR 不作显著性使用",
                   f"dropped_codes_no_price={len(dropped)}",
               ],
               "leg_obs_202501": obs["summary"],
               "leg_chain_single_day": {"chain_version": version, **chain}}
    (OUT_DIR / "outcome_stats_202501.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("written -> %s", OUT_DIR / "outcome_stats_202501.json")

    # 控制台速览
    for s in OBS_SCORES:
        row = payload["leg_obs_202501"]["rank_ic"][s]
        log.info("obs IC %-11s h5=%s h20=%s", s,
                 row["5"].get("mean"), row["20"].get("mean"))
    log.info("chain composite_adj IC: %s", chain["rank_ic"]["composite_adj"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
