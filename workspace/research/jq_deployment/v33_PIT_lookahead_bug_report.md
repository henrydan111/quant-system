# v33 / v32 / v31 PIT Lookahead Bug Report

**Status:** CONFIRMED → **FIXED → RE-MEASURED (2026-05-29).** High severity (invalidated reported performance). See §9 Resolution at the bottom.
**Found:** 2026-05-29, during JoinQuant factor-alignment verification of `v33_strategy_spec.md`.
**Audience:** a fresh session tasked with fixing the local research pipeline. Self-contained.

> **RESOLUTION SUMMARY (2026-05-29):** Report validated in full (code + on-disk repro). Scope determined: bug is CONFINED to the `workspace/scripts/sandbox_v*` hand-rolled loaders — the production backend (`pit_backend.py` → Qlib provider → EventDrivenBacktester) and the JoinQuant deployment script are PIT-correct and unaffected. All 58 sandbox loaders fixed (compact-date normalization + permanent assertion). Re-measured on the same engine: the v33 champion OOS collapsed 188.7%→**2.0%** (MDD -33.8%→-76.3%), and the val_heavy "deployment" config collapsed +81.9%→**+9.6%** CAGR with **-3.4% (negative) walk-forward**, 0/18 configs passing. The edge was almost entirely earnings foresight. Full detail in §9.

---

## 0. TL;DR

`sandbox_v15aa_v32_open_execution.py → build_pit_pivot()` joins fundamental
factors onto trading dates using **string comparison between two incompatible
date formats**:

- `effective_date` from the PIT ledger is **dashed**: `"2018-10-30"`.
- `sim_dates` (from daily `trade_date`) are **compact**: `"20180607"`.

Because the ASCII dash `-` (0x2D) sorts **below** every digit `0-9` (0x30+),
`"2018-10-30" < "20180607"` evaluates to `True`. As a result, the forward-fill
that maps "latest known fundamental as of T-1" instead selects the **latest
quarter of the entire calendar year** — available from the **first trading days
of January** onward.

**Net effect:** every rebalance in calendar year Y uses **Q3-Y financial data**
(published ~late October Y). At the start of the year this is ~9–11 months of
forward knowledge of the company's earnings trajectory. Only late-year
(post-Q3-publication) rebalances are accidentally correct.

This contaminates **every fundamental factor** in the signal and therefore
**every performance number** reported for v31 / v32 / v33, including the headline
v33 figures (OOS CAGR 77.8%, full-period CAGR 106.4%, Sharpe 2.57). It also
contaminates the universe **eligibility filter** (which reads the same arrays).

The JoinQuant replication built from the spec is **correctly point-in-time** and
therefore *cannot* reproduce the contaminated reference baskets — non-alignment
is the correct outcome and was the signal that surfaced this bug.

---

## 1. Exact location

File: `workspace/scripts/sandbox_v15aa_v32_open_execution.py`
Function: `build_pit_pivot(df, col)` — lines ~181–193.

```python
def build_pit_pivot(df, col):
    if col not in df.columns:
        prt(f"  [MISSING] {col} — NaN array")
        return pd.DataFrame(np.nan, index=sim_dates_loc, columns=all_cols)
    sub = df[["ts_code", "effective_date", col]].dropna(subset=[col])
    prt(f"  Building {col}: {len(sub):,} non-null, {sub['ts_code'].nunique()} stocks")
    pv = sub.pivot_table(index="effective_date", columns="ts_code",   # <-- index = dashed strings
                         values=col, aggfunc="last").sort_index()      # <-- lexical sort of dashed strings
    all_d = sorted(set(pv.index.tolist()) | set(sim_dates_loc))        # <-- MIXES dashed + compact, sorts lexically
    res = pv.reindex(all_d).ffill().reindex(sim_dates_loc)             # <-- ffill across a wrongly-ordered index
    for c in all_cols:
        if c not in res.columns: res[c] = np.nan
    return res[all_cols].shift(1)
```

The offending precondition is set at line ~135:

```python
ind_df["effective_date"] = ind_df["effective_date"].astype(str)   # keeps the dashed "YYYY-MM-DD" form
```

while `sim_dates_loc` derives from the daily panel where (line ~148):

```python
raw["trade_date"] = raw["trade_date"].astype(str)   # compact "YYYYMMDD"
```

So `all_d = sorted(set(dashed) | set(compact))` is **not chronologically
ordered**, and `.ffill()` over it propagates the wrong values.

---

## 2. Why string comparison breaks the ordering

For any calendar year Y, ASCII ordering gives:

```
"Y-03-29"  <  "Y-05-02"  <  "Y-08-03"  <  "Y-10-30"   <   "Y0102" < "Y0103" < ... < "Y1231"
( all dashed quarter-effective dates of year Y )      ( all compact trade dates of year Y )
```

Every dashed `"Y-MM-DD"` string is **less than** even the earliest compact
`"Y0102"`, because at character index 4 the dash `-` (0x2D) loses to the digit
`0` (0x30). Consequently, in the merged sorted index, **all of year Y's published
quarters sit immediately before January Y's first trading day**. `ffill()` at any
2018 trade date therefore reaches back to the **largest dashed 2018 date**, which
is **Q3-2018** (`"2018-10-30"`) — the last quarter whose effective date still
falls inside calendar year 2018. (Q4/annual reports are published the *next*
year, so their effective date is `"2019-…"`, i.e. compact-greater, and they are
correctly excluded during year Y.)

`reference shift(1)` shifts by a single trading day and does not change this.

---

## 3. Evidence (reproduced on disk)

### 3.1 Raw ledger rows for 600519.SH (贵州茅台)

```
ts_code     ann_date    end_date    effective_date   roa     roe     roe_waa  q_roe
600519.SH   2018-03-28  2017-12-31  2018-03-29       31.25   32.95   32.95    8.07
600519.SH   2018-04-28  2018-03-31  2018-05-02        9.05    8.89    8.89     8.89   <- 2018Q1 (the CORRECT PIT value in June 2018)
600519.SH   2018-08-02  2018-06-30  2018-08-03       17.17   17.06   15.87    7.51
600519.SH   2018-10-29  2018-09-30  2018-10-30       25.25   25.52   24.93    9.16   <- 2018Q3 (published Oct 2018)
```

### 3.2 What the pipeline actually serves (buggy ffill) vs a correct PIT load

`roa` for 600519, by rebalance date:

| Rebalance date | Pipeline (buggy) | Quarter used | Correct PIT | Quarter | Lookahead |
|---|---|---|---|---|---|
| 2018-01-08 | **25.25** | 2018Q3 | 23.64 | 2017Q3 | **~9 months** |
| 2018-03-01 | **25.25** | 2018Q3 | 25.25* | — | (varies) |
| 2018-06-07 | **25.25** | 2018Q3 | 9.05 | 2018Q1 | **~5 months** |
| 2018-09-03 | **25.25** | 2018Q3 | 17.17 | 2018Q2 | **~2 months** |
| 2018-11-01 | 25.25 | 2018Q3 | 25.25 | 2018Q3 | none (Q3 now public) |

The §13.2 / §13.3 reference baskets in `v33_strategy_spec.md` were generated by
this pipeline and therefore inherit the contamination. The spec's "2018-06-07"
factor row for 600519 (`roa 25.25, roe_waa 24.93, q_roe 9.16`) is verifiably the
**2018Q3** row above, not the 2018Q1 row that was actually knowable on 2018-06-06.

### 3.3 Reproduction script (standalone, ~15 lines)

```python
import pandas as pd, glob
ind = pd.read_parquet(r'E:\量化系统\data\pit_ledger\indicators\indicators.parquet',
                      columns=['ts_code','effective_date','end_date','roa'])
ind['effective_date'] = ind['effective_date'].astype(str)
files = []
for yr in (2017, 2018):
    files += glob.glob(rf'E:\量化系统\data\market\daily\{yr}\daily_*.parquet')
sim = sorted(pd.concat([pd.read_parquet(f, columns=['trade_date']) for f in files])
             ['trade_date'].astype(str).unique())
s = ind[ind['ts_code'] == '600519.SH'][['effective_date','roa']].dropna()

# BUGGY (string ffill, as the pipeline does today):
pv = s.groupby('effective_date')['roa'].last().sort_index()
buggy = pv.reindex(sorted(set(pv.index) | set(sim))).ffill().reindex(sim).shift(1)

# CORRECT (parse to real datetimes before ffill):
pv2 = s.assign(eff=pd.to_datetime(s['effective_date'])).groupby('eff')['roa'].last().sort_index()
simd = pd.to_datetime(pd.Series(sim), format='%Y%m%d')
correct = pv2.reindex(sorted(set(pv2.index) | set(simd))).ffill().reindex(simd).shift(1)
correct.index = sim

for dt in ['20180108','20180607']:
    print(dt, 'buggy=%.2f  correct=%.2f' % (float(buggy.loc[dt]), float(correct.loc[dt])))
# 20180108 buggy=25.25  correct=23.64
# 20180607 buggy=25.25  correct=9.05
```

---

## 4. Scope of impact

### 4.1 Factors affected (all built via `build_pit_pivot`)

`npy` (netprofit_yoy), `dt_npy`, `q_qoq`, `roe`, `roa`, `q_roe`, `rev_growth`
(or_yoy), `netprofit_margin`, `roe_yoy`, `q_dt_roe`, `roe_dt`, `roe_waa`.
That is **all 9 fundamental factors** plus the derived `q_roe_yoy` (built from the
contaminated `q_roe`).

**Not affected** (sourced from the daily panel, which is correctly compact and
`shift(1)`-ed): `size` (`-ln total_mv`) and `val` (`1/pb`). These two aligned
perfectly in the JoinQuant verification (`val` 0.10 vs 0.101), consistent with
them being clean.

### 4.2 Eligibility filter also contaminated

`build_basket()` / `eligible_idx()` test `_npy_raw` and `_roe_raw`, which are
copies of the contaminated `npy` / `roe` arrays. So the universe membership
(`netprofit_yoy >= 0`, `roe >= 0`) is itself forward-looking. (`_pb_raw` is from
the clean daily panel, so the PB band `0.30 < pb <= 6.0` is fine.)

### 4.3 Scripts / outputs that inherit the bug

- `sandbox_v15aa_v31_focuspct_confirmation.py` (if it shares the loader)
- `sandbox_v15aa_v32_open_execution.py` — the bug's home
- `sandbox_v15aa_v33_event_driven.py` — imports `v32` and uses
  `v32.factor_arrays` / `v32.load_data()` directly (lines 54, 99, 216). The
  realistic-execution layer (T+1, limit-up, costs) is unrelated and probably
  fine, but it ranks on contaminated factors.
- `v33_factor_alignment_dump.py` → `workspace/outputs/v33_factor_alignment.txt`
  (the §13 reference tables in the spec).
- Any `project_state.md` performance record citing v31/v32/v33 CAGR/Sharpe/MDD.

### 4.4 Performance implication

The reported edge is partly **earnings foresight**, not tradable alpha. Expect
the corrected (true-PIT) CAGR to be **materially lower** than the reported
77.8% OOS / 106% full. The spec's own §0.4 "statistical-honesty caveat" already
guessed a bias-corrected 40–60%; this lookahead is an *additional, separate*
inflation on top of the multiple-comparison concern, so the honest number could
be lower still. Re-measurement after the fix is required — do not assume a haircut.

---

## 5. The fix

**Minimal, surgical:** normalize `effective_date` to the same compact format as
`trade_date` at load time, so all subsequent string comparisons are
chronological. One line, at `sandbox_v15aa_v32_open_execution.py` ~line 135:

```python
# BEFORE
ind_df["effective_date"] = ind_df["effective_date"].astype(str)          # "2018-10-30"

# AFTER  (compact, matches sim_dates "YYYYMMDD")
ind_df["effective_date"] = (pd.to_datetime(ind_df["effective_date"])
                            .dt.strftime("%Y%m%d"))                       # "20181030"
```

After this, `"20181030" > "20180607"` correctly, so a June-2018 rebalance no
longer sees Q3-2018.

**More robust (recommended):** stop mixing string keys entirely — do the join on
real `datetime64` and let pandas order chronologically:

```python
def build_pit_pivot(df, col):
    if col not in df.columns:
        return pd.DataFrame(np.nan, index=sim_dates_loc, columns=all_cols)
    sub = df[["ts_code", "effective_date", col]].dropna(subset=[col]).copy()
    sub["eff"] = pd.to_datetime(sub["effective_date"], errors="coerce")     # real dates
    sub = sub.dropna(subset=["eff"])
    pv = sub.pivot_table(index="eff", columns="ts_code", values=col, aggfunc="last").sort_index()
    sim_idx = pd.to_datetime(pd.Index(sim_dates_loc), format="%Y%m%d")
    res = (pv.reindex(pv.index.union(sim_idx)).ffill().reindex(sim_idx))
    res.index = sim_dates_loc                                              # restore compact labels
    for c in all_cols:
        if c not in res.columns:
            res[c] = np.nan
    return res[all_cols].shift(1)
```

Notes:
- Keep the existing `.shift(1)` — it is the intended 1-trading-day disclosure
  buffer and is still correct once ordering is fixed.
- `aggfunc="last"` on the pivot is fine once the index is real dates (handles two
  reports sharing an effective date).
- Double-check the **`q_roe_yoy` 252-row lag** still lines up after the fix; it
  indexes positionally into the corrected `q_roe` array (line ~208–212), so it
  should be fine, but re-verify a couple of values.

---

## 6. Verification after fixing (acceptance gates)

1. **600519 spot check.** On a June-2018 rebalance, the corrected pipeline must
   serve 600519 `roa ≈ 9.05`, `roe_waa ≈ 8.89` (2018Q1), **not** 25.25 / 24.93.
   On a Jan-2018 rebalance it must serve 2017Q3 (`roa ≈ 23.64`), not 2018Q3.
2. **No same-year forward leakage, universe-wide.** For every rebalance date T,
   assert that the `end_date`/`statDate` backing each used factor value has its
   `effective_date <= T` *chronologically*. A cheap global check: for each factor
   cell used at T, the source quarter end must be ≤ the most recent quarter whose
   `ann_date < T`. Add this as a permanent assertion in `load_data()`.
3. **Re-run v32 and v33.** Record the corrected IS/OOS/full CAGR, MDD, Sharpe.
   Expect a significant drop from 77.8% OOS / 106% full. Update `project_state.md`
   and `v33_strategy_spec.md` §0.1 / §13 with the corrected numbers and baskets.
4. **Regenerate `v33_factor_alignment_dump.py`.** The corrected reference baskets
   on 2018-06-07 / 2019-06-04 / 2021-06-17 / 2023-06-08 should then match the
   JoinQuant correct-PIT run (see §7) to ≥3/5 — closing the alignment loop.
5. **Scan for the same pattern elsewhere.** Grep the codebase for other places
   that compare or merge `effective_date` / `ann_date` / `disclosure_date`
   (dashed) against `trade_date` (compact). Any `sorted(set(dashed) | set(compact))`
   or string `<=` between the two formats is suspect.

---

## 7. Cross-check: the correct-PIT JoinQuant baskets (independent reference)

A correctly point-in-time JoinQuant research run (full A-share universe incl.
科创/北交, same 11 weights, same PB filter, single-quarter factors reconstructed
from parent-company fields) produced these **pre-substitution top-5** on the spec's
four reference dates. These are an *independent, lookahead-free* second opinion —
the fixed local pipeline should converge toward them (codes shown 6-digit):

```
2018-06-07 : 002133 600641 600516 002168 002001        (eligible universe 1799)
2019-06-04 : 603508 002234 002882 300702 002755        (eligible universe 1856)
2021-06-17 : 603477 002932 600512 300677 002382        (eligible universe 2615)
2023-06-08 : 300970 000014 000048 300511 301089         (eligible universe 2024)
```

Overlap with the spec's contaminated baskets was 0/5, 2/5, 1/5, 0/5 — as expected
when one side has ~5–9 months of earnings foresight and the other does not. The
partial overlaps (e.g. 002234, 300702 in 2019; 002932 in 2021) are names whose
ranking is robust to the lookahead. After the local fix, overlap should jump.

Verification details that passed cleanly on JoinQuant (i.e. *not* in question):
- PB cap correctly excludes 600519 on all four dates (pb 9.0–15.5 > 6.0).
- Single-quarter parent-company `q_roe` reconstruction matches to vendor noise
  (600519 q_roe 8.89 on JQ vs 9.16 in the — contaminated — reference; both are
  quarter-scale, the residual is vendor + the Q1-vs-Q3 lookahead).
- Per-factor coverage on JQ is ~93–100% (the spec's 67–85% is the buggy
  pipeline's coverage; higher clean coverage is expected and fine).

---

## 8. One-paragraph summary for `project_state.md`

> **2026-05-29 — PIT lookahead bug found in v31/v32/v33 factor loader.**
> `build_pit_pivot()` in `sandbox_v15aa_v32_open_execution.py` forward-fills
> fundamentals by lexically comparing dashed `effective_date` (`"2018-10-30"`)
> against compact `sim_dates` (`"20180607"`); since `-` < digits, every
> rebalance in calendar year Y silently uses Q3-Y data from January onward
> (≈9-month max lookahead). All 9 fundamental factors + eligibility are
> contaminated; `size`/`val` (daily panel) are clean. v33 imports these arrays,
> so 77.8% OOS / 106% full / Sharpe 2.57 are inflated and must be re-measured.
> Fix: normalize `effective_date` to `"%Y%m%d"` (or join on `datetime64`) before
> the ffill. A correct-PIT JoinQuant run is the independent cross-check.

---

## 9. Resolution (2026-05-29)

### 9.1 Validity — confirmed in full
Report reproduced exactly on disk. `"2018-10-30" < "20180607"` is `True`; the buggy
ffill serves 600519 `roa=25.25` (Q3) on 2018-06-07 where the correct PIT value is
`9.05` (Q1). The minimal fix (`pd.to_datetime(effective_date).dt.strftime("%Y%m%d")`)
was proven **full-series identical** to a `datetime64`-join reference.

### 9.2 Scope — bug is sandbox-only; the backend is clean
This was the load-bearing question. **The production backend does NOT have the bug:**
- `src/data_infra/pit_backend.py` normalizes every date through `normalize_date_series()`
  → `datetime64`, then aligns with `calendar.searchsorted()` on a `DatetimeIndex`.
  Comparisons are between `pd.Timestamp` objects, never strings. The only date
  `sorted(set | set)` in `src/` (`pit_backend.py:1256`) operates on normalized
  Timestamp keys.
- **Empirical proof:** the live Qlib provider serves `$roa` for 600519 stepping EXACTLY
  on each report's `effective_date` (2018-05-02→9.05, 2018-08-03→17.17, 2018-10-30→25.25).
  June-2018 = Q1 = 9.05, not Q3.
- `EventDrivenBacktester`, `VectorizedBacktester`, and the research orchestrator read
  via `D.features()` (datetime calendar) → unaffected.
- The JoinQuant deployment script `workspace/scripts/jq_11f_roewaa_strategy.py` uses
  JoinQuant-native `get_fundamentals(date=...)` + `pubDate` filtering → PIT-correct,
  no bug.

The bug existed ONLY in the `sandbox_v*` scripts that bypassed the provider and
re-implemented PIT alignment by hand against the raw ledger (the anti-pattern of
reimplementing the factor pipeline outside the framework).

### 9.3 Fix — applied to all 58 sandbox loaders
Every `sandbox_v*` script carrying `ind_df["effective_date"] = ...astype(str)` was
patched to `pd.to_datetime(...).dt.strftime("%Y%m%d")` plus a permanent guard
`assert effective_date.dropna().str.fullmatch(r"\d{8}").all()`. Idempotent, syntax-clean.

### 9.4 Re-measurement — the edge was foresight
Re-run on the SAME sandbox engine with the loader as the only changed variable:

| Config | Metric | Contaminated | Corrected (true PIT) |
|---|---|---|---|
| v33 champion (11F+roe_waa) | OOS CAGR | 188.7% | **2.0%** |
| | MDD | −33.8% | **−76.3%** |
| | Walk-forward | ~213% | **16.9%** |
| val_heavy (deployed config K6_min70) | CAGR | +81.9% | **+9.6%** |
| | MDD | −29.2% | **−65.1%** |
| | Walk-forward | +82.4% | **−3.4% (negative)** |

val_heavy: 0/18 param configs and 0/9 rebalance configs pass. The lookahead
contributed ≈71pp of CAGR and ≈85pp of walk-forward. The §0.4 spec caveat guessed a
bias-corrected 40–60%; the true number is far lower — the strategy fails every gate.

### 9.5 Deployment implication
The +81.9%/WF+82.4% "FINAL deployment" numbers were the **contaminated sandbox**
numbers. Because the JoinQuant script is itself PIT-correct, a real JoinQuant backtest
would show the weak de-contaminated profile, not +82% — the JoinQuant verification that
surfaced this bug (the 0/5, 2/5 basket divergence in §7) was the signal that the sandbox
numbers were unreal. **The live JQ code will not leak future data, but it will not
deliver the performance it was selected on.** Recommendation: halt any live/pending use
of the val_heavy / 11F-roe_waa strategy and re-derive from scratch on PIT-correct factors,
preferably through the production backend rather than a hand-rolled sandbox loader.

Logs: `workspace/outputs/v32_rerun_fixed.log`, `workspace/outputs/v15o_rerun_fixed.log`.
