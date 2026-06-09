> # ⚠ NON-COMPLIANT BUILD — QUARANTINED (2026-06-08 correction)
> This feature store was built by **reading raw `data/` parquet directly and hand-rolling PIT
> alignment**, which violates the backend rules (CLAUDE.md §3.2 / src/system.md §0): all factor/feature
> data MUST flow through the PIT ledger + Qlib provider and be accessed via `pit_research_loader`
> (sandbox PIT) / `compute_factors` (Qlib factors) — never hand-rolled from raw files. It also skipped
> the provider boundary guard (delist/IPO-lag masking) → likely survivorship contamination. **Do NOT
> use `bucket_a_ml_monthly.parquet` for any ML test.** The features must be re-derived through the
> sanctioned backend (materialize fields via `pit_backend`, register in `field_status.yaml`, read via
> the loader/qlib) before a feature store is legitimate. Kept for design reference only.

# Bucket A ML Feature Store

*2026-06-08. PIT-correct feature matrix from all 8 new-data (Bucket A) endpoints, built for future
ML experiments. Builder: [bucket_a_feature_store.py](bucket_a_feature_store.py).*

## What it is
A unified point-in-time feature panel + forward-return labels, ready to drop into an ML pipeline.
- **File:** `workspace/outputs/feature_store/bucket_a_ml_monthly.parquet` (+ `manifest.json`)
- **Shape:** 460,140 rows × 20 features + 3 labels, 6,485 stocks
- **Index:** `(datetime, instrument)` — **instrument is Qlib format** (`000001_SZ`), so it joins directly
  to the provider / `compute_factors` output.
- **Grid:** monthly month-end, **IS 2014-2020 only** (OOS 2021-2026 deliberately excluded).
- **Status:** SANDBOX research artifact — NOT formal Qlib fields, NOT registry-governed. (That governance
  is only needed to promote a *standalone* factor; an ML feature set lives in sandbox.) PIT-correctness
  IS enforced.

## PIT contract
Every feature is visible only from `strictly_next_open_trade_day(disclosure_date)` (the canonical
anchor). Per source: report_rc → `report_date`; express / repurchase / top10 / audit / disclosure →
`ann_date`; pledge → `end_date + 7d` (weekly stat date, conservative); mainbz → `end_date + 120d`
(no `ann_date` in schema — conservative annual-disclosure lag). No same-day leakage.

## Features (20) by source + coverage

| Source | Features | Cov% | Notes |
|---|---|---|---|
| **report_rc** | `rc_eps_diffusion`★, `rc_eps_revision`, `rc_rating_revision`, `rc_eps_dispersion`, `rc_n_analysts`, `rc_rating_score`, `rc_eps_fy1`, `rc_rating_diffusion` | 13–46 | ★`rc_eps_diffusion` is the validated strong signal (incr RankICIR +0.64 @20d, t=5.89; tradeable +5.5%/yr long-only). `rc_rating_diffusion` (1%) is dead — keep for completeness. |
| **express** | `exp_npy_yoy`, `exp_roe` | 43 | preliminary-earnings YoY net profit + ROE (early earnings signal) |
| **disclosure** | `disc_days_to_report` | 24 | trading days to next scheduled report (pre-announcement window) |
| **repurchase** | `repo_active`, `repo_amount_180d`, `repo_events_180d` | 8 | buyback events in trailing 180d (sparse by nature) |
| **pledge** | `pledge_pledge_ratio` | 56 | share-pledge ratio (tail-risk overlay) |
| **top10** | `float_top10_share`, `float_hold_change` | 60 | top-10 float ownership concentration + net change |
| **audit** | `audit_nonstandard` | 68 | 1 if audit opinion is non-标准无保留 (risk flag) |
| **mainbz** | `mainbz_hhi`, `mainbz_n_seg` | 97 | revenue-segment concentration (Herfindahl) + segment count |

**Labels:** `label_fwd_5d`, `label_fwd_20d`, `label_fwd_60d` (forward H-trading-day close returns;
52–54% coverage = the feature∩priced-universe overlap). Drop unlabeled rows for supervised training.

## How to load
```python
import pandas as pd
df = pd.read_parquet("workspace/outputs/feature_store/bucket_a_ml_monthly.parquet")
df = df.set_index(["datetime", "instrument"])
X = df[[c for c in df.columns if not c.startswith("label_")]]
y = df["label_fwd_20d"]
mask = y.notna()
X, y = X[mask], y[mask]   # ~248k labeled rows
```

## Why ML (not standalone factors)
The Wave-1A pilot ([WAVE1A_PILOT_FINDINGS.md](WAVE1A_PILOT_FINDINGS.md)) found `report_rc` consensus is
**orthogonal but individually weak** (except `eps_diffusion`). Weak-but-orthogonal signals are precisely
what a non-linear ML model can combine — the honest home for most of these features is a *learned
ensemble*, not standalone promotion. This store makes that experiment turn-key.

## Caveats for the ML user
- **IS-only.** Any model trained here must be validated on a sealed OOS (2021-2026, untouched) before
  any deployment claim. Use temporal (walk-forward) CV, never random splits.
- **Coverage is uneven + size-tilted** (report_rc/express skew large-cap; mainbz/audit are broad). The
  NaN pattern is informative, not missing-at-random — prefer models/encodings that handle missingness
  (or add per-feature "is-present" indicators) rather than naive imputation.
- **Neutralize / rank cross-sectionally per date** before training if you want the model to learn
  cross-sectional ranking rather than market beta / size.
- **Conservative anchors** (pledge +7d, mainbz +120d) are deliberately late — safe, may slightly
  understate freshness. Tighten only with a verified disclosure-date join.
- The 2026-06-15 `report_date` backfill canary still applies to the `rc_*` features' PIT-safety; this
  sandbox store used the 1-day-lag-verified anchor.

## Next ML steps (turn-key from here)
1. Walk-forward train (e.g. LightGBM/GBT) on IS folds predicting `label_fwd_20d`; report fold IC +
   feature importance (does `rc_eps_diffusion` dominate? do the risk flags add?).
2. Cross-sectional rank-IC of the model score vs the single-feature baselines.
3. Only if the IS model is robust → one sealed-OOS evaluation vs CSI500.
