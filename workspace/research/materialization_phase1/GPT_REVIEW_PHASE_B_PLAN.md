ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that runs. A single lookahead invalidates the result even if every test passes. This is a DESIGN-PLAN review (no code yet) — be skeptical, surface blockers, do not rubber-stamp.

REPO (public — fetch to verify)
https://github.com/henrydan111/quant-system   (branch: report-rc-registration)
- THE PLAN (authoritative): workspace/research/materialization_phase1/PHASE_B_DESIGN_PLAN.md
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/workspace/research/materialization_phase1/PHASE_B_DESIGN_PLAN.md
- CLAUDE.md §3.2 (PIT), §3.5 (factor lifecycle), §7 (research integrity)
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/CLAUDE.md
- pit_backend.py (derive_single_quarter_value ~line 1188; _materialize_forecast_growth = the custom-materializer precedent ~line 2762)
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/src/data_infra/pit_backend.py

================================================================================
WHAT THIS PLANS (authoritative summary — full doc at the link)
================================================================================

## Background
25 Tushare `q_*` single-quarter fina_indicator fields were INTENTIONALLY left unregistered
(field_status.yaml, 2026-06-09: "we self-compute PIT-correct _sq equivalents; the vendor q_* are not
guaranteed PIT-safe"). A Phase-1 rebuild materialized their bins but they are inert (unregistered →
formal fail-closed). Plan: replace the VALUABLE ones with OUR PIT-correct `_sq` derivations — never
registering a vendor field. Classification (verified vs the live provider + ledgers):
- 23 fully derivable from existing validated `_sq` (Part A) — incl. q_opincome = total_revenue_sq − total_cogs_sq.
- 1 needs a base-field materialization, DEFERRED (q_impair_to_gr_ttm; sparse post-2019).
- 1 genuinely hard (q_dtprofit 扣非单季) — Part C.

## Part A — 23 derivable factors (no new materialization)
Each = an expression over existing `_sq` snapshots (e.g. earn_np_yoy_q = (n_income_sq_q0 −
n_income_sq_q4)/Abs(n_income_sq_q4); qual_gross_margin_q = (revenue_sq_q0 − oper_cost_sq_q0)/revenue_sq_q0;
earn_eps_q = n_income_attr_p_sq_q0/total_share). PIT-correct BY CONSTRUCTION: `_sq` anchors on
effective_date (§3.2); every $field wrapped in Ref(...,1) per the factor-library PIT-safety invariant.
Enter as `draft`. Design rules: (1) catalog-duplicate audit first — some already exist (grow_sales_yoy_q
≈ validated SalesQGr%PY); (2) redundancy disclosure — a correlated family, NOT independent discoveries,
downstream selection by marginal orthogonal contribution; (3) denominator 0/NaN guards (financial/net-cash
firms → sub-universe); (4) sync_catalog to the registry as draft.

## Part C — q_dtprofit (扣非净利润单季): DESIGN FOR ACCURACY + PIT
GOAL: PIT-correct single-quarter 扣非净利润 (归母 net profit excl. non-recurring), replacing the
PIT-uncertain vendor q_dtprofit.
SOURCE (verified): `profit_dedt` (扣非净利润, CUMULATIVE YTD) in the indicators (fina_indicator) ledger —
confirmed cumulative (600519 2022: 17.24B → 29.76B → 44.39B → 62.79B). `extra_item` (非经常性损益) also
cumulative there.
DERIVATION: single-q = profit_dedt[Q] − profit_dedt[Q−1] (Q1 = profit_dedt[Q1]) via
derive_single_quarter_value (the income/cashflow flow logic).
IMPLEMENTATION: Option A (RECOMMENDED) = a custom materializer `_materialize_profit_dedt_sq` mirroring
`_materialize_forecast_growth` — reads the indicators ledger profit_dedt, derives single-q, writes
$profit_dedt_sq_q0..q4. Option B = move profit_dedt into a flow family (more invasive; rejected unless A unsafe).
PIT (by construction, NOT validated against the distrusted vendor field):
  (1) profit_dedt anchors on indicators ann_date → effective_date (§3.2), same anchor as approved q_roe;
  (2) cumulative→single-q respects restatement (derive_single_quarter_value retroactively updates at the
      restatement effective_date — §3.2 cumulative→quarterly late-restatement); (3) Ref(...,1) for predictive use.
ACCURACY validation (VALUE, not timing):
  - PRIMARY oracle = 果仁 (trusted benchmark): if a 果仁 book shows 扣非净利润单季 / EpsExclXorQ, holding-level parity.
  - SECONDARY = vendor q_dtprofit VALUE (Tushare's value is correct; only its PIT timing is uncertain) —
    our $profit_dedt_sq should match near-exactly; a mismatch flags a derivation bug.
  - CROSS-CHECK = $profit_dedt_sq vs (n_income_attr_p_sq − single-q of extra_item) — must agree.
PIT validation: restatement canary + provider-read exact-date audit.
GOVERNANCE: new materializer → GPT cross-review (like forecast R1→R4); build + publish + register
$profit_dedt_sq + the factor qual_dtprofit_to_profit_q.

================================================================================
QUANTITATIVE-RESEARCH PRINCIPLES — judge the PLAN against each; a violation is a Blocker
================================================================================
1. PIT / NO-LOOKAHEAD (cardinal). Does the q_dtprofit cumulative→single-q derivation from the indicators
   (snapshot-configured) ledger preserve PIT? Is the restatement handling sound when the SOURCE dataset is
   a periodic_snapshot, not a flow family? Do the Part-A `_sq` expressions (Ref(...,1)) have any same-day leak?
2-3. (OOS / survivorship) — n/a for this data-infra/factor-definition plan (factors enter as draft; promotion is a separate sealed gate).
4. FACTOR-EVAL / MULTIPLICITY. 23 correlated single-q factors are not independent signals — is the
   redundancy disclosure + marginal-contribution selection sufficient, and the catalog-duplicate audit adequate?
7. NO HEDGE WORDS — every claim in the plan is backed by a verified probe or marked; flag any that isn't.
8. FOUR-LAYER — these are Layer-1 factors; confirm nothing encodes tradability/universe (the denominator
   sub-universe masks are Layer-2).

REVIEW QUESTIONS
1. q_dtprofit PIT: is deriving a single-quarter FLOW from `profit_dedt` (a cumulative field living in the
   periodic_snapshot indicators ledger) PIT-correct + restatement-safe via derive_single_quarter_value, or
   does the snapshot-vs-flow configuration mismatch introduce a hazard? Is Option A (custom materializer)
   the right call vs Option B (flow-family inclusion)?
2. Accuracy oracle: is "vendor q_dtprofit VALUE is correct, only its PIT TIMING is uncertain" an airtight
   separation for using it as a value oracle, or could a vendor value-error hide? Is the 果仁-preferred +
   extra_item cross-check enough?
3. Part A: are the 23 `_sq` expressions PIT-correct as written? Any that is NOT actually redundant/derivable,
   or mis-mapped to the wrong vendor field? Denominator-domain handling adequate?
4. Sequencing/scope: is deferring q_impair right? Anything in the plan that should be a Blocker before any code.
5. Evidence: what additional probe/test would you require before implementing Part C.

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each mapped to the principle/invariant it violates, with a concrete fix.
- Final line: APPROVE-PLAN / REVISE-PLAN / REWORK-PLAN + the single most important residual risk.
