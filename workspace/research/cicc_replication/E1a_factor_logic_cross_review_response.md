# CICC Wave E1a — response to GPT 5.5 Pro CHANGES REQUIRED (factor-logic cross-review)

**Verdict received:** CHANGES REQUIRED before any registry write (2 blockers: Q1, Q7).
**Fold-in commit:** `34f72a7` on `report-rc-registration` (preceded by `ebe0644`, the v1→archive move).
**Repo:** https://github.com/henrydan111/quant-system

All 8 questions + the additional finding are addressed below. Tests after the fold-in: **173 passed**
(pit_safety + operator_expressions + operator_certification + replication_governance + factor_registry).
Still nothing registered — this is the corrected pre-gate state, presented for APPROVE confirmation.

---

## Blockers

### Q1 — path_adjusted_momentum numerator → period return ✅ DONE
Changed `Sum(daily_ret,W)/Sum(|daily_ret|,W)` → **`period_return(W) / Sum(|daily_ret|,W)`**, i.e.
`(adj_close_{t-1}/adj_close_{t-W-1} - 1) / Sum(|daily_ret|,W)`, 0-guarded. This is the literal
handbook "过去N内收益率" and matches how `op.momentum` reads "收益率".
[operators.py `path_adjusted_momentum`](https://github.com/henrydan111/quant-system/blob/34f72a7/src/alpha_research/factor_library/operators.py).
The catalog now emits (20d): `If(Sum(Abs(ret),20)>0, (Ref(adj_close,1)/Ref(adj_close,21)-1)/Sum(Abs(ret),20), 0)`.
**Re-certified** — the reference/vectorized in
[certify_e1a_operators.py](https://github.com/henrydan111/quant-system/blob/34f72a7/workspace/scripts/certify_e1a_operators.py)
now compute the period-return form (and the old `|value|≤1` property — which does NOT hold for the
period-return form due to compounding — was replaced with sign + choppy-path properties). The
certification hash/spec text was regenerated (your explicit instruction not to keep the stale cert).

### Q7 — mmt_range manifest binding → v2 + operator-id split ✅ DONE
Created **[cicc_price_volume_cohort_v2.yaml](https://github.com/henrydan111/quant-system/blob/34f72a7/config/replication/cicc_price_volume_cohort_v2.yaml)** (sha `3e07e048b35cdd87`). v1 (sha
`01dbe38b9281a968`) is **archived UNCHANGED** at
[archive/cicc_price_volume_cohort_v1.yaml](https://github.com/henrydan111/quant-system/blob/34f72a7/config/replication/archive/cicc_price_volume_cohort_v1.yaml).
- `mmt_range_M/A` `required_operators`: `[amplitude_conditional_sum]` → **`[amplitude_top_bottom_20pct_return_spread]`**
  (the true top/bottom-20%-by-rank spread; **PENDING** build+cert → `mmt_range` stays deferred).
- The fixed-4%-threshold operator was **renamed** `amplitude_conditional_sum` →
  **`amplitude_threshold_4pct_conditional_sum`** with an accurate spec ("NOT handbook mmt_range")
  in [certify_operators.py](https://github.com/henrydan111/quant-system/blob/34f72a7/workspace/scripts/certify_operators.py);
  the cert store was regenerated so the ambiguous old name no longer exists. No PV factor binds it.
- This is a **pre-registration correction** (no PV factor has been gated; no OOS spent) — exactly the
  case you flagged as "not p-hacking; the frozen hash should change."

---

## Non-blocking items

| Q | Your verdict | Resolution |
|---|---|---|
| Q2 | OK (keep guard, no ε) | Unchanged — `If(den>0, …, 0)` kept. |
| Q3 | OK (250/20 split) | Unchanged — `Mean(Rank(close,250),20)`. |
| Q4 | OK + fix rationale | Docstring corrected: adjusted high is used *because* cross-day highs need a comparable basis; an ex-rights adjustment **can** move the argmax — that's the reason, not an accident. |
| Q5 | OK draft / CHANGES before formal gate | **Front-loaded now**: operators certified at **W∈{20,250}**; the composed `Mean(Rank(px,250),20)` form is verified (ref==vec, bounded [0,1]) in the cert script. |
| Q6 | OK + note | `mmt_discrete_20d` row in v2 carries a `known_near_duplicate_of rev_up_down_ratio_20d` comment + selection rule (must clear `resid_ic_vs_controls`; not counted as independent discovery otherwise). |
| Q8 | OK after Q1/Q7 | Mechanics unchanged: `sync_catalog` drafts → v2 `catalog_factor_id` link → F3/F11 at the #34 gate. |
| +finding | warmup expression-specific | Per-factor warmup minima recorded as a v2 comment (route 22/252, discrete 22/252, time_rank 270, highest_days 251); the **enforcing test** is a #34 gate-harness deliverable (the gate must drop partial-window rows, not a generic 60d buffer). |

---

## What is NOT in this fold-in (explicit, not silent)
- The **warmup-enforcement test** and the **W=250 cert is sufficient-for-formal** sign-off are #34
  (formal-gate) prerequisites — recorded, not yet coded. Draft registration does not require them.
- `amplitude_top_bottom_20pct_return_spread` (true mmt_range operator) is **not built** — `mmt_range`
  remains deferred from the E1a tranche.

---

## Requested confirmation
With Q1 + Q7 folded in: **APPROVE to register the 6 E1a drafts + link the v2 manifest?** (or any
residual CHANGES REQUIRED). The 6: `mmt_route_20d/_250d`, `mmt_discrete_20d/_250d`,
`mmt_time_rank_20d`, `mmt_highest_days_250d`.
