# =============================================================================
# JoinQuant CLOUD RESEARCH NOTEBOOK  (聚宽云端研究 — NOT a backtest)
# PIT-anchor validation, scale-up pull.
#
# Purpose: export JoinQuant's genuinely-PIT 朝阳永续 consensus factors as-of a grid
# of historical dates, for the SURVIVORSHIP-CORRECT as-of universe (get_all_securities
# with date=asof => includes names ALIVE then that later delisted). The local side
# reconstructs the Tushare report_rc report_date+1 consensus and compares; agreement
# across small caps + delisted names => report_date+1 is a validated PIT visibility
# anchor for the pre-2022-05 backfilled history.
#
# HOW TO RUN:
#   1. JoinQuant web -> 研究 (research) -> 新建 Notebook (Python 3 kernel).
#   2. Paste each CELL below into its own notebook cell; run top to bottom.
#   3. CELL 1 prints the consensus/revision factor catalog — if a PIT EPS-revision or
#      rating-upgrade-breadth factor appears, add its name to FACTORS in CELL 2.
#   4. After CELL 3, download `jq_consensus_pit_broad.csv` from the research file
#      browser to:  E:\量化系统\聚宽回测明细\jq_consensus_pit_broad.csv
#   5. Locally: venv/Scripts/python.exe workspace/research/data_expansion/report_rc_pit_anchor_broad_compare.py
# =============================================================================


# ---- CELL 1: discover which 朝阳永续 / consensus factors exist (PIT revision/breadth?) ----
import pandas as pd
from jqfactor import get_all_factors

allf = get_all_factors()
print("get_all_factors columns:", list(allf.columns))          # defensive: confirm column names
text_cols = [c for c in allf.columns if allf[c].dtype == object]
kw = ['predict', 'expected', 'consensus', 'revision', 'forecast', 'rating', 'eps',
      'earnings', 'upgrade', '一致预期', '预期', '评级', '上调', '盈利预测']
mask = pd.Series(False, index=allf.index)
for c in text_cols:
    mask |= allf[c].astype(str).str.contains('|'.join(kw), case=False, na=False)
cand = allf[mask]
pd.set_option('display.max_rows', 300); pd.set_option('display.max_colwidth', 80); pd.set_option('display.width', 220)
print(f"\n{len(cand)} candidate consensus/revision factors "
      f"(the validated series is 'predicted_earnings_to_price_ratio'):")
print(cand.to_string())
# >>> ACTION: scan for a PIT consensus EPS-revision or rating-upgrade-BREADTH factor.
#     If one exists, adding it to FACTORS lets us validate the eps_diffusion BREADTH
#     form directly (not just the consensus level).


# ---- CELL 2: config ----
YEARS = list(range(2013, 2022))               # the backfilled era (2010-2021); 2013+ = solid coverage
# mid-FY (Jun-30) ONLY: FY1 = current year unambiguously (matches the proven 0.997 pilot).
# year-end is deliberately excluded — at Dec-31 JQ's consensus "FY1" rolls to next year,
# a confound that would muddy the comparison. 9 full-market cross-sections = ample power.
ASOF_DATES = [f"{y}-06-30" for y in YEARS]

# Must-have validated series first; the rest are best-effort (CELL 3 skips any that error).
FACTORS = [
    'predicted_earnings_to_price_ratio',          # consensus FY1 earnings yield (the proven series)
    'short_term_predicted_earnings_growth',
    'long_term_predicted_earnings_growth',
    # 'add a PIT revision/breadth factor name from CELL 1 here',
]
CHUNK = 500                                       # securities per get_factor_values call (cap-safe)
OUT = 'jq_consensus_pit_broad.csv'


# ---- CELL 3: pull the survivorship-correct as-of universe x factors -> tidy long CSV ----
import pandas as pd
from jqfactor import get_factor_values


def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def pull_one(asof, factor):
    """Tidy long rows (asof, code, factor, value) for ONE factor at ONE as-of date."""
    secs = get_all_securities(types=['stock'], date=asof)     # alive-as-of-asof => incl. future-delisted
    uni = list(secs.index)
    rows = []
    for batch in chunks(uni, CHUNK):
        fv = get_factor_values(securities=batch, factors=[factor], end_date=asof, count=1)
        df = fv.get(factor)
        if df is None or df.empty:
            continue
        s = df.iloc[-1]                                       # single as-of row: index=code, values=value
        sub = s.rename('value').rename_axis('code').reset_index()
        sub['asof'] = asof
        sub['factor'] = factor
        rows.append(sub[['asof', 'code', 'factor', 'value']])
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=['asof', 'code', 'factor', 'value'])


frames = []
for asof in ASOF_DATES:
    for factor in FACTORS:
        try:
            part = pull_one(asof, factor)
            frames.append(part)
            print(f"{asof}  {factor:<40s} rows={len(part)}")
        except Exception as e:
            print(f"{asof}  {factor:<40s} SKIPPED ({type(e).__name__}: {e})")

out = pd.concat(frames, ignore_index=True).dropna(subset=['value'])
out.to_csv(OUT, index=False)
print(f"\nwrote {OUT}: rows={len(out)}  dates={out['asof'].nunique()}  "
      f"codes={out['code'].nunique()}  factors={sorted(out['factor'].unique())}")
print(out.head(8).to_string(index=False))
# >>> ACTION: download jq_consensus_pit_broad.csv -> E:\量化系统\聚宽回测明细\, then run the
#     local comparison (report_rc_pit_anchor_broad_compare.py).
