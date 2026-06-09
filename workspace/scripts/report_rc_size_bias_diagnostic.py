"""report_rc size-selection diagnostic (cross-review Q-D1, design question).

Question: does report_rc's cap-tilt (large-cap ~95% covered, small-cap 22-53%)
make a POOLED cross-sectional consensus factor unsound unless ranked within
coverage / within size?

This answers it STRUCTURALLY (no forward returns — that IC study is Wave-1A and
needs pre-registration). For a few as-of cross-sections in the IS window it
measures, among covered names:
  (a) coverage probability by size decile        -> how size-selected is coverage
  (b) rank-corr(signal, size)                     -> is the signal just size?
  (c) within-size-decile dispersion of the signal -> is there signal to rank once
                                                     size is held fixed?
Signals: consensus rating score (ordinal map), n_analysts (coverage intensity),
mean forward EPS. Decision rule in the printed verdict.

Sandbox-only exploration; report_rc is NOT registered, so this never feeds a
formal stage. Read-only, sequential.
"""
from __future__ import annotations
import json, logging, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from src.data_infra.fetchers import TushareFetcher  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("rc_bias")

AS_OF = ["20160630", "20180629", "20191231"]   # IS-window mid/year-end cross-sections
WINDOW_DAYS = 90
PAGE = 5000

RATING_MAP = {
    # positive
    "strong buy": 2, "强烈推荐": 2, "强推": 2, "买入": 1, "buy": 1, "overweight": 1,
    "outperform": 1, "增持": 1, "推荐": 1, "add": 1, "accumulate": 1, "优于大市": 1, "审慎增持": 1,
    # neutral
    "hold": 0, "neutral": 0, "中性": 0, "持有": 0, "market perform": 0, "谨慎推荐": 0,
    "equal-weight": 0, "equalweight": 0, "观望": 0,
    # negative
    "reduce": -1, "underweight": -1, "sell": -1, "减持": -1, "卖出": -1, "回避": -1,
    "underperform": -1, "弱于大市": -1,
}


def _paginate(pro, start, end):
    months, cur = [], datetime.strptime(start, "%Y%m%d")
    end_dt = datetime.strptime(end, "%Y%m%d")
    while cur <= end_dt:
        nxt = (cur.replace(day=28) + timedelta(days=4)).replace(day=1)
        months.append((cur.strftime("%Y%m%d"), min(nxt - timedelta(days=1), end_dt).strftime("%Y%m%d")))
        cur = nxt
    frames, seen = [], set()
    for s, e in months:
        offset = 0
        while True:
            df = pro.report_rc(start_date=s, end_date=e, limit=PAGE, offset=offset)
            n = 0 if df is None else len(df)
            if not n:
                break
            keys = pd.util.hash_pandas_object(df, index=False).values
            mask = ~pd.Series(keys).isin(seen).values
            new = df[mask]
            if new.empty:
                break
            seen.update(keys[mask].tolist())
            frames.append(new)
            offset += n
            time.sleep(1.3)
            if n < PAGE:
                break
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _rating_score(s):
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return np.nan
    return RATING_MAP.get(str(s).strip().lower(), np.nan)


def main():
    pro = TushareFetcher(config_path=str(PROJECT_ROOT / "config.yaml")).pro
    report = {}
    for asof in AS_OF:
        start = (datetime.strptime(asof, "%Y%m%d") - timedelta(days=WINDOW_DAYS)).strftime("%Y%m%d")
        rc = _paginate(pro, start, asof)
        size = pro.daily_basic(trade_date=asof, fields="ts_code,total_mv,circ_mv")
        time.sleep(1.3)
        size = size[size["total_mv"].notna()].copy()
        size["size_decile"] = pd.qcut(size["total_mv"].rank(method="first"), 10,
                                      labels=list(range(1, 11)))
        covered = set(rc["ts_code"].unique())

        # (a) coverage by size decile
        cov_by_dec = (size.assign(cov=size["ts_code"].isin(covered))
                      .groupby("size_decile", observed=True)["cov"].mean().mul(100).round(1))

        # per-stock consensus signal over the window
        rc = rc.copy()
        rc["rscore"] = rc["rating"].map(_rating_score)
        unmapped = rc["rating"].notna().sum() - rc["rscore"].notna().sum()
        eps = pd.to_numeric(rc["eps"], errors="coerce")
        rc["eps_num"] = eps
        g = rc.groupby("ts_code").agg(
            rscore=("rscore", "mean"),
            n_analysts=("org_name", "nunique"),
            eps_mean=("eps_num", "mean"),
        ).reset_index()
        df = g.merge(size[["ts_code", "total_mv", "size_decile"]], on="ts_code", how="inner")
        df["log_mv"] = np.log(df["total_mv"])

        def rcorr(a, b):
            m = df[[a, b]].dropna()
            return round(m[a].rank().corr(m[b].rank()), 3) if len(m) > 30 else None

        # (c) within-decile dispersion of rscore (std), averaged across deciles
        wd = df.dropna(subset=["rscore"]).groupby("size_decile", observed=True)["rscore"]
        within_std = round(wd.std().mean(), 3)
        overall_std = round(df["rscore"].std(), 3)

        report[asof] = {
            "covered_stocks": len(covered),
            "listed_with_size": int(len(size)),
            "rating_unmapped_rows": int(unmapped),
            "coverage_pct_by_size_decile": {str(k): float(v) for k, v in cov_by_dec.items()},
            "rankcorr_n_analysts_vs_size": rcorr("n_analysts", "log_mv"),
            "rankcorr_rscore_vs_size": rcorr("rscore", "log_mv"),
            "rankcorr_epsmean_vs_size": rcorr("eps_mean", "log_mv"),
            "rscore_within_decile_std": within_std,
            "rscore_overall_std": overall_std,
        }
        log.info("%s: covered=%d  corr(n_an,size)=%s  corr(rscore,size)=%s  "
                 "within_std=%s overall_std=%s", asof, len(covered),
                 report[asof]["rankcorr_n_analysts_vs_size"],
                 report[asof]["rankcorr_rscore_vs_size"], within_std, overall_std)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    p = PROJECT_ROOT / "workspace" / "outputs" / f"report_rc_size_bias_{stamp}.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n==== report_rc SIZE-SELECTION DIAGNOSTIC ====")
    for asof, r in report.items():
        print(f"\n{asof}  covered={r['covered_stocks']}/{r['listed_with_size']} listed "
              f"(rating unmapped rows={r['rating_unmapped_rows']})")
        cov = r["coverage_pct_by_size_decile"]
        print("  coverage% by size decile (1=small..10=large): "
              + " ".join(f"{cov.get(str(k),0):.0f}" for k in range(1, 11)))
        print(f"  rankcorr(n_analysts, size) = {r['rankcorr_n_analysts_vs_size']}  "
              f"(coverage intensity is a size proxy if high)")
        print(f"  rankcorr(rating_score, size) = {r['rankcorr_rscore_vs_size']}  "
              f"(direction signal's size contamination)")
        print(f"  rating_score dispersion: within-size-decile std={r['rscore_within_decile_std']} "
              f"vs overall std={r['rscore_overall_std']}")
    print("\nwrote", p)


if __name__ == "__main__":
    main()
