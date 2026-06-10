"""Part B: validate our self-computed single-quarter YoY (pit_*) vs Tushare vendor q_*.

Recomputes OUR pit_* growth using the EXACT deployed primitives
(derive_single_quarter_value + percent_change + same_period_last_year_end on the income
ledger's final cumulative values) and compares, per (ts_code, fiscal end_date), to
Tushare's vendor single-quarter YoY (q_*) from the indicators ledger:

  pit_netprofit_yoy (n_income_attr_p) vs q_netprofit_yoy
  pit_op_yoy        (operate_profit)  vs q_op_yoy
  pit_or_yoy        (revenue)         vs q_sales_yoy

Diagnostic — reads raw ledgers directly (q_* are intentionally unregistered, so the
sanctioned loader refuses them). Pure pandas, no qlib/loky/find/du. Compares FINAL
(latest-restatement) values → validates the COMPUTATION math (PIT timing is separate).
"""
import os
import sys
import numpy as np
import pandas as pd

ROOT = r'E:\量化系统'
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, ROOT)
from data_infra.pit_backend import (  # noqa: E402
    derive_single_quarter_value, percent_change, same_period_last_year_end,
)

PAIRS = [('pit_netprofit_yoy', 'n_income_attr_p', 'q_netprofit_yoy'),
         ('pit_op_yoy', 'operate_profit', 'q_op_yoy'),
         ('pit_or_yoy', 'revenue', 'q_sales_yoy')]
BASE = ['revenue', 'operate_profit', 'n_income_attr_p']


def final_rows(path, value_cols):
    """Latest-restatement (max ann_date) row per (ts_code, end_date)."""
    df = pd.read_parquet(path, columns=['ts_code', 'end_date', 'ann_date'] + value_cols)
    df['end_date'] = pd.to_datetime(df['end_date'])
    df['ann_date'] = pd.to_datetime(df['ann_date'], errors='coerce')
    df = df.sort_values(['ts_code', 'end_date', 'ann_date'])
    return df.drop_duplicates(['ts_code', 'end_date'], keep='last')


def main():
    inc = final_rows(os.path.join(ROOT, 'data/pit_ledger/income/income.parquet'), BASE)
    ind = final_rows(os.path.join(ROOT, 'data/pit_ledger/indicators/indicators.parquet'),
                     ['q_netprofit_yoy', 'q_op_yoy', 'q_sales_yoy'])
    print(f'income final rows={len(inc)}, indicators final rows={len(ind)}')

    # recompute our pit_* per (ts_code, end_date)
    recs = []
    for ts, g in inc.groupby('ts_code'):
        cum_state = {row.end_date: {b: getattr(row, b) for b in BASE} for row in g.itertuples()}
        # single-quarter values per end_date
        sq_state = {}
        for ed in cum_state:
            sq_state[ed] = {b: derive_single_quarter_value(cum_state, ed, b) for b in BASE}
        for ed in sq_state:
            ref = same_period_last_year_end(ed)
            if ref is None or ref not in sq_state:
                continue
            rec = {'ts_code': ts, 'end_date': ed}
            for out_f, base_f, _ in PAIRS:
                rec[out_f] = percent_change(sq_state[ed][base_f], sq_state[ref][base_f])
            recs.append(rec)
    ours = pd.DataFrame(recs)
    print(f'recomputed ours: {len(ours)} (ts_code,quarter) rows')

    merged = ours.merge(ind, on=['ts_code', 'end_date'], how='inner')
    print(f'merged with vendor: {len(merged)} rows')

    out_lines = ['# Part B — our pit_* (recomputed via deployed primitives) vs Tushare vendor q_*', '',
                 f'Per (ts_code, fiscal end_date), FINAL restatement. merged rows={len(merged)}.', '',
                 '| ours | vendor | N | pearson | spearman | sign% | <=1pp% | <=5pp% | medAbsΔ |',
                 '|---|---|---|---|---|---|---|---|---|']
    print(f"\n{'ours':<20}{'vendor':<18}{'N':>9}{'pears':>8}{'spear':>8}{'sign%':>7}{'<=1pp':>7}{'<=5pp':>7}{'medAbs':>8}")
    for out_f, _, vend_f in PAIRS:
        sub = merged[[out_f, vend_f]].replace([np.inf, -np.inf], np.nan).dropna()
        a = sub[out_f].to_numpy(float); b = sub[vend_f].to_numpy(float)
        n = len(a)
        if n < 50:
            print(f'{out_f:<20}{vend_f:<18}{n:>9}  insufficient'); out_lines.append(f'| {out_f} | {vend_f} | {n} | — | — | — | — | — | — |'); continue
        pear = float(np.corrcoef(a, b)[0, 1])
        spear = float(pd.Series(a).corr(pd.Series(b), method='spearman'))
        sign = float(np.mean(np.sign(a) == np.sign(b)))
        w1 = float(np.mean(np.abs(a - b) <= 1.0))
        w5 = float(np.mean(np.abs(a - b) <= 5.0))
        md = float(np.median(np.abs(a - b)))
        near_exact = float(np.mean(np.abs(a - b) < 0.05))
        # outlier diagnosis: clip to a sane YoY range and re-correlate
        m = (np.abs(a) <= 300) & (np.abs(b) <= 300)
        pear_clip = float(np.corrcoef(a[m], b[m])[0, 1]) if m.sum() > 50 else float('nan')
        n_huge = int(np.sum(np.abs(a - b) > 50))
        print(f'{out_f:<20}{vend_f:<18}{n:>9}{pear:>8.4f}{spear:>8.4f}{sign*100:>6.1f}{w1*100:>7.1f}{w5*100:>7.1f}{md:>8.3f}'
              f'  exact={near_exact*100:.1f}% pearClip[±300]={pear_clip:.4f} (kept {m.mean()*100:.2f}%) bigΔ>50={n_huge}')
        out_lines.append(f'| {out_f} | {vend_f} | {n} | {pear:.4f} | {spear:.4f} | {sign*100:.1f} | {w1*100:.1f} | {w5*100:.1f} | {md:.3f} |')
        out_lines.append(f'  - near-exact(|Δ|<0.05): {near_exact*100:.1f}% · Pearson after ±300 clip: {pear_clip:.4f} (keeps {m.mean()*100:.2f}%) · |Δ|>50pp count: {n_huge}')

    outp = os.path.join(ROOT, 'workspace/research/data_audit/PIT_VS_VENDOR_Q_PARITY.md')
    open(outp, 'w', encoding='utf-8').write('\n'.join(out_lines) + '\n')
    print(f'\nwrote {outp}')


if __name__ == '__main__':
    main()
