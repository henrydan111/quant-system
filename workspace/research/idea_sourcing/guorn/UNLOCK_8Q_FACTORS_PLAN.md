# Plan — unlock the "8-quarter-depth" blocked 果仁 factors (3 routes)

**Goal.** Unlock + top-K-validate the factors blocked in the deployed-20 campaign for needing data beyond the
live provider's single-quarter slot depth (q0..q4). They split into **three unlock routes** (only two need a
provider build). All work is **NON-FORMAL parity validation** (same class as the rest of the campaign): build
transient / read existing data → comparator top-K vs the 果仁 web export (broad 排除ST排除科创, ONE rank
condition, lag per factor) → record in `guorn_web_validation_campaign.json`. No formal registration, no live
provider publish, no registry writes.

Public repo for review: `https://github.com/henrydan111/quant-system` (branch `report-rc-registration`).

---

## Route A — scoped deep-slot build (RnDTTMGr%PY, AssetTurnoverDiffPY)

These genuinely need single-quarter slots **q0..q7** (the year-ago TTM leg). Mechanism = the **proven rung-6
deep-slot path** (`workspace/scripts/_build_deepslot_scoped.py` → `build_unified_qlib(field_filter=…,
datasets=…, touched_symbols=…, slot_depth=8, publish=False)`), which materializes deeper `_sq_q*` slots via the
**same** restatement-safe single-quarter kernel (`derive_single_quarter_value`, effective_date>disclosure
STRICT) the live q0..q4 slots use — so the deep slots inherit the §3.2 PIT guarantee. rung-6 validated this
**bit-faithful** vs the deepslot truth (median rel-err 0.0, n~2M).

- **Fields / datasets:** `rd_exp`, `revenue` (income) + `total_assets` (balancesheet). `slot_depth=8`.
- **Scope (disk hazard — `feedback_provider_build_disk_hazard`):** `touched_symbols` = the 排除ST排除科创
  universe (~4400, via the Python API like rung-6, not the CLI), `field_filter` = the 3 fields,
  `datasets=["income","balancesheet"]`, `publish=False` → staged-only. **Size estimate ≈ 4–5GB** (3 fields ×
  ~16 bins × ~4400 syms; cf rung-6's 7×24-bin scoped ~18GB). `--test` (2 syms) first to confirm before scaling.
- **Compute (read the staged deep-slot provider):**
  - `RnDTTMGr%PY = (Σrd_exp_sq_q0..q3 − Σrd_exp_sq_q4..q7) / |Σrd_exp_sq_q4..q7|`
  - `AssetTurnoverDiffPY = ATO(0) − ATO(4)`, `ATO(k)=Σrevenue_sq_q[k..k+3] / mean(total_assets_q[k..k+3])`
- **Teardown:** delete the staged dir after computing (rung-6 pattern; ~GB transient, not persisted).

## Route B — daily total_share sampling (SharesAvgGr%PY) — no build

`$total_share` is a **daily series** (verified: steps at share-change events). 果仁
`SharesAvgGr%PY = AvgQ(总股本,4,0)/AvgQ(总股本,4,4) − 1`.
- Sample the **daily** `$total_share` at the 8 trailing fiscal-quarter-end dates (q0=latest disclosed report
  period … q7), take the two 4-quarter means, ratio − 1. **PIT:** all 8 quarter-ends are strictly in the past
  at the signal date, so each sampled value was already known (no lookahead). Custom helper (~30 lines), no
  provider build, no comparator (date-specific sampling isn't a single qlib expr) → compare the helper output
  to the 果仁 export directly.

## Route C — dividend-ledger aggregation (DivGrPY%, DivOP%, Div%NetIncY2, DivAGrPY%, 连续N年分红) — no build

Extend the **validated** dividend caliber (`workspace/scripts/guorn_dividend_caliber.py`,
`declared_dividend_ttm(signal, window_days)`; data path validated by 股息率TTM, 0.5% match, PIT ann_date≤signal).
- `DivGrPY% = TTM_div(signal)/TTM_div(signal−365d) − 1` (trailing-div YoY).
- `DivOP% = TTM_div(signal) / TTM(营业利润)` (needs `operate_profit_sq_q0..q3`, live depth OK).
- `DivAGrPY% = annual_div(FY0)/annual_div(FY−1) − 1`; `Div%NetIncY2` = 2-yr avg payout (annual div / annual NI).
  → add an `annual_dividend(fiscal_year)` aggregator (group the ledger by `end_date` fiscal year, PIT ann≤signal).
- `连续N年分红(3)` = a dividend declared in each of the last 3 fiscal years (boolean/count).
- **⚠ amount basis:** 分红总金额 is the TOTAL amount = `cash_div_tax × shares`; the helper returns per-share
  `dps`. For the growth/payout RATIOS, per-share is share-stable-equivalent; where 果仁 uses 分红总金额 against
  a total (NI/OP), multiply `dps × total_share` per event for faithfulness. All PIT ann_date≤signal.

---

## Validation (all three)

Per factor: 果仁 web export (broad 排除ST排除科创, ONE rank condition, 选股日期 2025-12-31, lag-0 for the
daily/total_share factors, lag-1 for statement factors) → comparator (Route A) or direct join (Routes B/C) →
report median rel-err / Spearman / **top-5/10/20 selection overlap** (the completion gate) → record verdict.
Expected per the settled pattern: RnDTTMGr%PY weak-head (near-zero-base R&D growth, like RnDQGR%PY);
AssetTurnoverDiff / SharesAvgGr / DivGrPY clean-ish (stable-ish denominators); the annual/continuity dividend
ones may carry a caliber.

## Self-review (§3 invariants + quant principles)

- **PIT / no-lookahead (§3.2):** Route A deep slots inherit `effective_date>disclosure` from the shared kernel
  (rung-6-proven); year-ago slots (q4..q7) are ~1–2yr-old reports, disclosed long before signal. Route B samples
  only past quarter-ends. Route C is ann_date≤signal-clamped. **No lookahead introduced.**
- **Provider/disk (§6.3, disk-hazard memory):** Route A is `touched_symbols`+`field_filter`+`datasets`-scoped,
  `slot_depth=8`, `publish=False`, transient + deleted → no full-tree copy, ~4–5GB. `--test` gate before scale.
- **No raw-ledger hand-rolling (§3.2 / feedback_factors_must_go_through_ledger_qlib):** Route A reads the
  staged QLIB provider via `D.features` (the factor-library path), NOT raw `pit_ledger/*`. Route C reads the
  dividends parquet via the EXISTING sanctioned caliber helper (already validated, not a new raw-ledger hand-roll).
  Route B reads `$total_share` via `D.features`.
- **NON-FORMAL:** no live publish, no registry/field-status writes, no formal artifact — a parity diagnostic
  (the staged provider is transient). If any factor is later wanted FORMALLY, that's a separate publish+register
  +GPT pass (the rung-6 stability precedent).
- **No hedge words (§7.10):** verdicts will state the measured top-K + the localized cause, not guesses.
- **Verdict:** clean for GPT.

## Review questions for GPT

1. **PIT:** Is reusing `slot_depth=8` (the rung-6 kernel) PIT-safe for the year-ago TTM leg (q4..q7), and is
   the Route-B "sample daily total_share at past fiscal-quarter-ends" free of lookahead / restatement leakage?
2. **Caliber faithfulness:** Are the derived formulas faithful to 果仁 — esp. AssetTurnoverDiffPY's ATO
   (TTM-rev / AvgQ(assets,4) vs (begin+end)/2), and the dividend 分红总金额 = per-share×shares basis for the
   total-denominated ratios (DivOP%, Div%NetIncY2)?
3. **Disk/governance:** Is the scoped slot_depth=8 / 3-field / publish=False / transient plan sufficient to
   avoid the 1TB hazard, and is NON-FORMAL (no publish/register) the right call for a parity check?
4. **Anything that would make a result a false pass** (e.g. a coverage gap in the deep-slot universe, a
   fiscal-quarter-end vs disclosure-date mismatch in Route B, a per-share-vs-total error in Route C)?
