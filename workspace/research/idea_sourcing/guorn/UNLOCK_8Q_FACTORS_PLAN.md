# Plan — unlock the "8-quarter-depth" blocked 果仁 factors (3 routes)

**Goal.** Unlock + top-K-validate the factors blocked in the deployed-20 campaign for needing data beyond the
live provider's single-quarter slot depth (q0..q4). They split into **three unlock routes** (only two need a
provider build). All work is **NON-FORMAL parity validation** (same class as the rest of the campaign): build
transient / read existing data → comparator top-K vs the 果仁 web export (broad 排除ST排除科创, ONE rank
condition, lag per factor) → record in `guorn_web_validation_campaign.json`. No formal registration, no live
provider publish, no registry writes.

Public repo for review: `https://github.com/henrydan111/quant-system` (branch `report-rc-registration`).

```
SCRIPT_STATUS: NON_FORMAL_PARITY_DIAGNOSTIC
No publish (staged provider only, publish=False, deleted after).  No field_status writes.
No factor-registry writes.  No OOS spend.  Route-A provider = an explicit STAGED URI (data/qlib_builds/<id>/provider).
ACCEPTANCE GATES (all factors): coverage ≥ 0.90 (sub-universe) / 0.98 (broad)  AND  pointwise value parity
(median rel-err + within-0.1/1/5% + sign)  AND  Spearman  AND  top-5/10/20 selection overlap. Top-K ALONE is
NOT sufficient (m1). A caliber is accepted ONLY by 果仁 parity, never by intuition (M5/M6).
```

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
- **Build script (GPT-M4):** `workspace/scripts/_build_deepslot_8q.py` — task-specific wrapper (slot_depth=8,
  the 3 fields above, datasets=[income,balancesheet], publish=False) with HARD preflight: prints symbols / est
  bins / est GB; ABORTS if est > 30GB, if publish=True, or if the target is the live `data/qlib_data`. `--test`
  (2 syms) → `--go`. (Does NOT reuse the rung-6 `_build_deepslot_scoped.py`, which is depth-16 / 7-field.)
- **Universe preflight (GPT-m2):** touched_symbols = all main+chinext (排除科创/北证) instruments = a SUPERSET
  of every 果仁-export code for these factors. Assert `set(果仁_export_codes) − set(touched) == ∅` before
  trusting any top-K (a narrower build → false top-K on a subset).
- **Compute (read the STAGED provider via the M2 `--provider-uri data/qlib_builds/guorn_unlock_8q_scoped/provider`):**
  - `RnDTTMGr%PY = (Σrd_exp_sq_q0..q3 − Σrd_exp_sq_q4..q7) / |Σrd_exp_sq_q4..q7|`
  - `AssetTurnoverDiffPY = ATO(0) − ATO(4)`. **果仁's denominator caliber is UNVERIFIED (GPT-M5)** → pre-register
    BOTH, pick ONLY by 果仁 parity: **(A)** `ATO(k)=Σrev_sq[k..k+3]/mean(total_assets_q[k..k+3])` (4-quarter avg)
    vs **(B)** `ATO(k)=Σrev_sq[k..k+3]/((total_assets_q[k]+total_assets_q[k+4])/2)` (begin+end avg).
- **Teardown:** delete the staged dir after computing (rung-6 pattern; transient, not persisted).

## Route B — daily total_share sampling (SharesAvgGr%PY) — no build

`$total_share` is a **daily series** (verified: steps at share-change events). 果仁
`SharesAvgGr%PY = AvgQ(总股本,4,0)/AvgQ(总股本,4,4) − 1`.
- **PIT anchor (GPT-M3 — the key fix; was the residual REVISE risk):** the eight fiscal periods q0..q7 are
  taken from the **PIT-visible report sequence** (the same as-of financial-state kernel that drives the statement
  slots) — NOT inferred from the signal calendar. q0 = the latest fiscal period whose report is ANNOUNCED as of
  the signal date; q1..q7 step back from there. A calendar quarter-end whose report is not yet visible (e.g. the
  current-FY-Q4 end before the annual report drops) is **INELIGIBLE**. For each eligible end_date, sample daily
  `$total_share` on the latest trading day ≤ that end_date. **If the 8-quarter chain is incomplete → serve NaN.**
- Two 4-quarter means → ratio − 1. Custom helper (no build, no comparator — date-specific sampling isn't a
  single qlib expr) → compare to the 果仁 export directly with the same pointwise+top-K battery.
- **Canary:** for a signal date BEFORE a stock's annual-report announcement, that FY's quarter-end must NOT
  enter the 8-quarter window (no undisclosed-period leak).

## Route C — dividend-ledger aggregation (DivGrPY%, DivOP%, Div%NetIncY2, DivAGrPY%, 连续N年分红) — no build

Extend the **validated** dividend caliber (`workspace/scripts/guorn_dividend_caliber.py`,
`declared_dividend_ttm(signal, window_days)`; data path validated by 股息率TTM, 0.5% match, PIT ann_date≤signal).
- `DivGrPY% = TTM_div(signal)/TTM_div(signal−365d) − 1` (trailing-div YoY).
- `DivOP% = TTM_div(signal) / TTM(营业利润)` (needs `operate_profit_sq_q0..q3`, live depth OK).
- `DivAGrPY% = annual_div(FY0)/annual_div(FY−1) − 1`; `Div%NetIncY2` = 2-yr avg payout (annual div / annual NI).
  → add an `annual_dividend(fiscal_year)` aggregator (group the ledger by `end_date` fiscal year, PIT ann≤signal).
- `连续N年分红(3)` = a dividend declared in each of the last 3 fiscal years (boolean/count).
- **⚠ amount basis (GPT-M6) — pre-register the share base, accept ONLY by 果仁 parity:** the helper returns
  PER-SHARE `dps`; the total-denominated ratios (DivOP%, Div%NetIncY2) need 分红总金额 = `dps × share_base`.
  Pre-register share_base candidates and test EACH vs 果仁: (1) total_share at record_date, (2) at ex_date,
  (3) at earliest ann/proposal date, (4) at fiscal end_date, (5) a Tushare total-amount field if PIT-safe. Do
  NOT accept dividend-YIELD parity as proof for total-ratio parity (per-share can be right while the total
  ratio is wrong by a share-base/unit convention). **Unit checks:** cash_div_tax per-share vs per-10-shares;
  total_share in shares vs 万股; the NI/OP denominator units. All PIT ann_date≤signal.

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

---

## GPT R1 — findings folded (2026-06-30)

- **M1 (plan not fetchable):** root cause was a branch slip — the session committed on local `trading-agents-design`
  while `git push` targeted a stale `report-rc-registration` (no-op). FIXED: fast-forwarded the remote branch to
  the session commits (`bff4449..787bed5`); the plan + all work are now live on `report-rc-registration`. Added the
  `SCRIPT_STATUS` governance header + acceptance gates (above).
- **M2 (comparator read the live provider):** FIXED in code — `guorn_factor_parity.py` now takes `--provider-uri`
  (default = live), threaded into `load_local_factor` + `qlib.init`, with `[provider] uri=… staged_deepslot=…`
  logging. Route A passes the staged URI.
- **M3 (Route B PIT anchor):** REWRITTEN — q0..q7 come from the PIT-visible report sequence, not the signal
  calendar; ineligible-if-unannounced; NaN if the chain is incomplete; + the pre-annual-report canary.
- **M4 (Route A wrapper mismatch):** ADDED `workspace/scripts/_build_deepslot_8q.py` (slot_depth=8, 3 fields,
  publish=False) with hard disk/governance preflight (est-GB ceiling 30GB, refuse-live-provider, refuse-publish).
- **M5 (asset-turnover denominator):** pre-register BOTH AvgQ(4) and (begin+end)/2; accept by 果仁 parity only.
- **M6 (dividend total-amount share base):** pre-register 5 share-base candidates + unit checks; per-share-yield
  parity is NOT accepted as proof for total-denominated ratios.
- **m1:** acceptance gate now requires pointwise parity AND top-K (top-K alone insufficient).
- **m2:** Route A universe = main+chinext superset; assert `果仁_export_codes ⊆ touched_symbols`.
- **m3:** Route C stays NON-FORMAL (direct ledger via the validated caliber helper); any future FORMAL use must
  route through the PIT ledger/provider + registration, not direct reads.

Self-review of the folds: §3.2 PIT preserved+strengthened (M3); §6.3 disk/governance hardened (M4); no publish/
registry writes (m3); no hedge words. **Verdict: clean for GPT re-review.**
