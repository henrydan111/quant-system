# =============================================================================
# JoinQuant CLOUD RESEARCH NOTEBOOK  (聚宽云端研究 — NOT a backtest)
# eps_diffusion GENUINE-PIT BENCHMARK — artifact-vs-decay discriminator.
#
# WHY: Tushare report_rc deep history (pre-2022-05) is a 2022-05 bulk backfill. Our local
# lag-stress showed the pre-2022 eps_diffusion strength is LAG-INVARIANT (RankICIR_20d 0.36 @ +0td
# == 0.37 @ +5td) => a data-VINTAGE artifact (values not as-of), while the real per-row window
# (2022-05+) is weak (0.04) and DECAYS with lag (genuine but weak). This notebook checks that
# verdict against JoinQuant's GENUINELY-PIT 朝阳永续 consensus (get_factor_values is as-of, no
# lookahead) — the independent oracle. We reconstruct the consensus FY1 EPS REVISION (the breadth
# proxy: rising consensus ~ net analysts raising) from the VALIDATED PIT series
# `predicted_earnings_to_price_ratio` (EP) x contemporaneous close, and measure its RankIC pre- vs
# post-2022 on real PIT data.
#
# PRE-REGISTERED INTERPRETATION (decide BEFORE seeing numbers):
#   * JQ-PIT pre-2022 RankIC ~ Tushare deep (mean_rank_ic strong, ICIR ~0.3-0.4)  => the pre-2022
#       signal is REAL (both PIT sources agree) -> Tushare-artifact verdict OVERTURNED; eps_diffusion
#       re-approval back on the table; post-2022 weakness = genuine decay/regime.
#   * JQ-PIT pre-2022 RankIC ~ Tushare clean (mean_rank_ic ~0, ICIR ~0-0.1)        => CONFIRMS the
#       Tushare backfill artifact (genuine PIT shows the factor was never strong pre-2022).
#   * post-2022 JQ should ~ Tushare clean (~0.04) — a sanity cross-check that both PIT sources agree
#       where both are genuinely point-in-time.
#
# HOW TO RUN:
#   1. JoinQuant web -> 研究 -> 新建 Notebook (Python 3). Paste each CELL into its own cell; run top-down.
#   2. CELL 1 lists consensus/revision factors — if a DIRECT PIT eps-revision or analyst-up/down-count
#      (breadth) factor exists, add its name to DIRECT_BREADTH_FACTORS in CELL 2 for an exact replication.
#   3. After CELL 5, download `jq_eps_diffusion_benchmark.csv` from the research file browser to
#      E:\量化系统\data\external\jq_eps_diffusion_benchmark.csv  (then tell me; I compare locally).
#
# NOTE on scissors: JQ 朝阳永续 is genuine-PIT but CONSENSUS-level (not per-analyst). The EP-derived
# EPS-revision is therefore a PROXY for the per-analyst breadth — same economic signal (upward-revision
# momentum), genuinely PIT. A direct breadth factor (if CELL 1 finds one) would be exact; use both.
# =============================================================================


# ---- CELL 1: discover consensus / revision / breadth factors -----------------------------------
import pandas as pd
from jqfactor import get_all_factors

allf = get_all_factors()
print("get_all_factors columns:", list(allf.columns))
text_cols = [c for c in allf.columns if allf[c].dtype == object]
kw = ['predict', 'expected', 'consensus', 'revision', 'forecast', 'rating', 'eps', 'earnings',
      'upgrade', 'analyst', 'report', 'num', 'count', '一致预期', '预期', '评级', '上调', '下调',
      '盈利预测', '分析师', '家数', '上修', '下修']
mask = pd.Series(False, index=allf.index)
for c in text_cols:
    mask |= allf[c].astype(str).str.contains('|'.join(kw), case=False, na=False)
cand = allf[mask]
pd.set_option('display.max_rows', 400); pd.set_option('display.max_colwidth', 90); pd.set_option('display.width', 240)
print(f"\n{len(cand)} candidate consensus/revision/breadth factors:")
print(cand.to_string())
# >>> ACTION: scan for (a) a consensus FY1 EPS *level* factor (cleaner than EP) and (b) a DIRECT
#     eps-revision or analyst up/down COUNT (breadth) factor. Put any you find into CELL 2.


# ---- CELL 2: config ----------------------------------------------------------------------------
# Monthly as-of grid (last trading day each month is resolved in CELL 3). Two windows:
PRE_WINDOW  = ("2014-01-01", "2021-12-31")     # backfilled era in Tushare; genuinely-PIT in JQ
POST_WINDOW = ("2022-05-01", "2026-02-27")     # real per-row create_time in Tushare; PIT in JQ (cross-check)
EP_FACTOR = "predicted_earnings_to_price_ratio"   # the VALIDATED genuine-PIT consensus FY1 EP series
DIRECT_BREADTH_FACTORS = []                        # <- add a direct PIT revision/breadth factor name from CELL 1, if any
REV_WINDOWS_M = {"rev_2m(~60d)": 2, "rev_4m(~120d)": 4}   # consensus-revision lookbacks (months)
FWD_HORIZONS_TD = [5, 10, 20]                      # forward-return horizons (trading days); 20d is primary
CHUNK = 400                                        # securities per get_factor_values / get_price call
OUT = "jq_eps_diffusion_benchmark.csv"


# ---- CELL 3: pull genuine-PIT consensus EP panel (monthly as-of x code), survivorship-correct ---
import numpy as np
import pandas as pd
from jqfactor import get_factor_values
from jqdata import *   # get_trade_days, get_all_securities, get_price — not auto-loaded in JQ research

def month_end_trading_dates(start, end):
    days = get_trade_days(start_date=start, end_date=end)
    s = pd.Series(pd.to_datetime(days))
    return [d.strftime("%Y-%m-%d") for d in s.groupby(s.dt.to_period("M")).max().tolist()]

def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]

def pull_factor_asof(asof, factor):
    """as-of single-row factor values for the survivorship-correct universe alive at asof."""
    secs = list(get_all_securities(types=['stock'], date=asof).index)
    vals = {}
    for batch in chunks(secs, CHUNK):
        fv = get_factor_values(securities=batch, factors=[factor], end_date=asof, count=1)
        df = fv.get(factor)
        if df is not None and not df.empty:
            vals.update(df.iloc[-1].dropna().to_dict())
    return pd.Series(vals, name=asof)

def build_panel(window, factor):
    dates = month_end_trading_dates(*window)
    cols = {}
    for d in dates:
        try:
            s = pull_factor_asof(d, factor); cols[d] = s
            print(f"  {factor:42s} {d}  n={s.notna().sum()}")
        except Exception as e:
            print(f"  {factor:42s} {d}  SKIP ({type(e).__name__}: {e})")
    panel = pd.DataFrame(cols).T            # index=asof(date str), columns=code
    panel.index = pd.to_datetime(panel.index)
    return panel.sort_index()

print("=== PRE window EP panel ==="); ep_pre = build_panel(PRE_WINDOW, EP_FACTOR)
print("=== POST window EP panel ==="); ep_post = build_panel(POST_WINDOW, EP_FACTOR)
direct_pre, direct_post = {}, {}
for f in DIRECT_BREADTH_FACTORS:
    print(f"=== PRE direct {f} ==="); direct_pre[f] = build_panel(PRE_WINDOW, f)
    print(f"=== POST direct {f} ==="); direct_post[f] = build_panel(POST_WINDOW, f)


# ---- CELL 4: forward returns at each as-of date (adjusted close), survivorship-correct ----------
import pandas as pd

def fwd_returns(panel, horizons):
    """Per as-of date: (a) RAW close at asof for the EPS reconstruction, (b) ADJUSTED forward returns.
    EPS = EP * price recovers consensus earnings ONLY with the RAW price JQ used in E/P (price cancels
    exactly: (earnings/P)*P = earnings); adjusted close would inject a spurious revision = the cumulative
    split/dividend factor over the lookback. Forward returns DO need adjusted close (true return, no
    ex-date jumps). So: raw (fq=None) for the level, post-adjusted (fq='post') for the return."""
    out = {h: {} for h in horizons}
    raw_close_at = {}
    asofs = [d.strftime("%Y-%m-%d") for d in panel.index]
    for d in asofs:
        codes = list(panel.columns[panel.loc[pd.Timestamp(d)].notna()])
        if not codes:
            continue
        fwd_days = get_trade_days(start_date=d, count=max(horizons) + 2)   # asof .. asof+maxh
        end = pd.Timestamp(fwd_days[-1]).strftime("%Y-%m-%d")
        c_raw, c_fwd = {}, {h: {} for h in horizons}
        for batch in chunks(codes, CHUNK):
            # (a) RAW close at asof — matches EP's price basis so EP*close == earnings (price cancels)
            praw = get_price(batch, end_date=d, count=1, frequency='daily', fields=['close'],
                             fq=None, panel=False)
            if praw is not None and len(praw):
                for _, r in praw.iterrows():
                    c_raw[r['code']] = r['close']
            # (b) ADJUSTED close over the forward window — true forward returns
            padj = get_price(batch, start_date=d, end_date=end, frequency='daily', fields=['close'],
                             fq='post', panel=False)
            if padj is None or len(padj) == 0:
                continue
            w = padj.pivot(index='time', columns='code', values='close').sort_index()
            for h in horizons:
                if len(w) > h:
                    rr = w.iloc[h] / w.iloc[0] - 1.0
                    for cc in w.columns:
                        c_fwd[h][cc] = rr.get(cc, np.nan)
        raw_close_at[d] = pd.Series(c_raw)
        for h in horizons:
            out[h][d] = pd.Series(c_fwd[h])
        print(f"  fwd {d}  codes={len(codes)}")
    close_panel = pd.DataFrame(raw_close_at).T; close_panel.index = pd.to_datetime(close_panel.index)
    fwd_panels = {}
    for h in horizons:
        fp = pd.DataFrame(out[h]).T; fp.index = pd.to_datetime(fp.index); fwd_panels[h] = fp.sort_index()
    return close_panel.sort_index(), fwd_panels

print("=== PRE fwd returns ==="); close_pre, fwd_pre = fwd_returns(ep_pre, FWD_HORIZONS_TD)
print("=== POST fwd returns ==="); close_post, fwd_post = fwd_returns(ep_post, FWD_HORIZONS_TD)


# ---- CELL 5: reconstruct consensus-EPS revision, compute RankIC / RankICIR, export --------------
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

def eps_from_ep(ep_panel, close_panel):
    """consensus FY1 EPS_t = EP_t * close_t  (EP genuine-PIT; close contemporaneous). aligned panel."""
    c = close_panel.reindex(index=ep_panel.index, columns=ep_panel.columns)
    return ep_panel * c

def revision_signal(eps_panel, lookback_m):
    """EPS revision over `lookback_m` monthly rows: eps_t / eps_{t-lookback} - 1 (per code)."""
    return eps_panel / eps_panel.shift(lookback_m) - 1.0

def rankic_series(signal_panel, fwd_panel):
    idx = signal_panel.index.intersection(fwd_panel.index)
    ics = {}
    for d in idx:
        s = signal_panel.loc[d]; f = fwd_panel.loc[d].reindex(s.index)
        m = s.notna() & f.notna()
        if m.sum() >= 30:
            ics[d] = spearmanr(s[m], f[m]).correlation
    return pd.Series(ics).dropna()

def summarize(label, signal_panel, fwd_panels):
    rows = []
    for h, fwd in fwd_panels.items():
        ic = rankic_series(signal_panel, fwd)
        if len(ic) >= 6:
            mean_ic = ic.mean(); icir = mean_ic / ic.std(ddof=1) if ic.std(ddof=1) > 0 else np.nan
            rows.append({"signal": label, "fwd_h_td": h, "n_dates": len(ic),
                         "mean_rank_ic": round(mean_ic, 4), "rank_icir": round(icir, 4),
                         "rank_icir_ann": round(icir * np.sqrt(12), 4)})
        else:
            rows.append({"signal": label, "fwd_h_td": h, "n_dates": len(ic),
                         "mean_rank_ic": np.nan, "rank_icir": np.nan, "rank_icir_ann": np.nan})
    return rows

eps_pre, eps_post = eps_from_ep(ep_pre, close_pre), eps_from_ep(ep_post, close_post)
results = []
for wlabel, eps_p, fwd_p, direct_p in [("PRE_2014_2021", eps_pre, fwd_pre, direct_pre),
                                       ("POST_2022_05+", eps_post, fwd_post, direct_post)]:
    for rlabel, lb in REV_WINDOWS_M.items():
        sig = revision_signal(eps_p, lb)
        for r in summarize(f"{wlabel}|EPrev|{rlabel}", sig, fwd_p):
            results.append(r)
    for f, dpanel in direct_p.items():   # direct breadth factor (if any) used as-is (no revision)
        for r in summarize(f"{wlabel}|DIRECT|{f}", dpanel, fwd_p):
            results.append(r)

res = pd.DataFrame(results)
print("\n================= eps_diffusion GENUINE-PIT (JoinQuant) benchmark =================")
print(res.to_string(index=False))
res.to_csv(OUT, index=False)
print(f"\nwrote {OUT} (rows={len(res)}). Download to E:\\量化系统\\data\\external\\{OUT}")
print("\nREAD (pre-registered): PRE mean_rank_ic strong (~0.03-0.06+, ICIR ~0.3-0.4) => pre-2022 signal "
      "REAL (Tushare-artifact verdict overturned). PRE ~ 0 => Tushare backfill artifact CONFIRMED. "
      "POST should ~ Tushare clean window (weak) as a both-PIT-agree cross-check.")
