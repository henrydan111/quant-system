# CICC factor-logic R3 fold-in — verification cross-review (for GPT 5.5 Pro)

> 2026-06-14. You returned **CHANGES REQUIRED** on the D4a/D-COMP factor LOGIC (10 findings, 5
> blocking). This brief asks you to **verify the fold-in** — did each change actually fix what you
> flagged, and is anything still wrong or newly introduced? Be adversarial, especially on the canary
> methodology (§5 below) where I made a judgement call that could be excusing a real problem.
>
> Web-based — repo `henrydan111/quant-system`, branch `report-rc-registration`, commit `23bc25b`.
> - catalog (D4a block + comp_cicc_profit): https://github.com/henrydan111/quant-system/blob/report-rc-registration/src/alpha_research/factor_library/catalog.py
> - cohort manifest **v2**: https://github.com/henrydan111/quant-system/blob/report-rc-registration/config/replication/cicc_fundamental_cohort_v2.yaml
> - tier→ceiling lattice (proxy_approx = hard candidate cap): https://github.com/henrydan111/quant-system/blob/report-rc-registration/src/alpha_research/factor_registry/replication_governance.py
> - q-slot parity canary: https://github.com/henrydan111/quant-system/blob/report-rc-registration/workspace/scripts/canary_qslot_value_parity.py
> - redundancy check: https://github.com/henrydan111/quant-system/blob/report-rc-registration/workspace/scripts/redundancy_strong_d4a.py
> - full triage: https://github.com/henrydan111/quant-system/blob/report-rc-registration/workspace/research/cicc_replication/FACTOR_LOGIC_cross_review_response.md

## What I did per finding (verify each)

**F1 — qual_aprd (BLOCKING).** Confirmed your verdict AND that my proposed `(NI−OCF)/total_assets`
fix was also wrong. **Removed `qual_aprd` from the catalog entirely** rather than ship a third guess.
Rationale: the faithful CICC `APRD = Δ(应计利润TTM / 营业利润TTM)` needs an **operating-profit-TTM
denominator**, but `operate_profit_sq` has only q0/q4 registered (q1/q2/q3 absent → OP-TTM not
buildable); and the 应计利润 numerator isn't transcribed in the handbook (standard is `NI_TTM −
OCF_TTM`, unconfirmed). Manifest APRD row unlinked (`catalog_factor_id` removed) + `exclusion_reason`
set. The `accounts_pay_q0/q1` slots are now unconsumed (annotated, left approved).
→ **Verify:** is full removal the right call, or should I register `operate_profit_sq` q1-q3 and build
it now? Is `NI_TTM − OCF_TTM` over `OP_TTM` the correct APR, or is the numerator `OP_TTM − OCF_TTM`?

**F2-4 — proxy_approx caps (BLOCKING).** Bumped the frozen manifest to **v2** (didn't edit v1 — v1 is
archived unchanged, out of the gate glob; `source_cohort_id` unchanged so governance records stay
keyed; denominators unchanged → conservative downgrade, not p-hacking). Downgraded to `proxy_approx`
(a HARD `candidate_ceiling` cap in `resolve_replication_ceiling`, vs `formula_equivalent_pending`
which is advanceable): `comp_cicc_profit` (PIT-TTM CFOA mixed with vendor cumulative-YTD ROE/ROIC;
exact TTM-ROIC not cleanly buildable — handbook itself flags ROIC ⚠️投入资本口径), `qual_roed`/
`qual_dted` (incl-minority equity + incl-minority NI; CICC ROE/产权比率 are 归母), `qual_qrd`
(inventory-only; CICC subtracts 1年内到期非流动资产 + 待摊费用 + 预付款 too). Gate re-run confirms
all four now resolve `ceiling=candidate_ceiling blocking=proxy_approx,…`.
→ **Verify:** (a) is bumping to v2 + archiving v1 the right anti-p-hacking move? (b) **Is the
"6 mechanically-faithful" set you blessed (CFOAD/ROAD/CCRD/CSRD/DAD/CURD) actually clean, or did I
wrongly leave any at formula_equivalent_pending?** Specifically: ROAD/CFOAD/CCRD use the SAME
incl-minority `NI_TTM` / `OCF_TTM` in their prior-TTM (q1+q2+q3+q4); CSRD uses `money_cap` (货币资金)
as a proxy for CICC 现金及现金等价物. Are any of those a proxy you'd cap?

**F5 — q-slot value-parity (BLOCKING). Built + ran; see §5 — this is where I most want challenge.**

**F6 — strong-D4a redundancy (non-blocking, confirmed).** Average per-date cross-sectional rank
correlation, 700-name universe × 60 months (2018-2022):
```
qual_road  ~ qual_roed   rho=+0.867   [within-group, share NI_TTM]
qual_cfoad ~ qual_ccrd    rho=+0.855   [within-group, share OCF_TTM]
all cross-group pairs     rho=+0.09 … +0.16   (mean +0.136)
```
→ ~2 distinct signals (net-income accel ≈ ΔROA/ΔROE; cash-flow accel ≈ ΔCFOA/ΔCCR), not 4. Recorded
for the selection step (keep one representative per group / orthogonalized residual).
→ **Verify:** agree? Any reason 0.86 is NOT "near-duplicate" in this context?

**F7 — cleanup.** catalog D4a comments rewritten (tiers + proxy caveats + APRD removal); accounts_pay
approval YAML annotated as unconsumed.

## §5 — Canary methodology (challenge this hardest)

[canary_qslot_value_parity.py] tests the **roll-forward identity**: when a new period rolls in (q0
steps once), what was q0 must become q1 (`q1[t]==q0[t-1]`); the single-quarter stack shifts
(`q4[t]==q3[t-1]`). A future-ann leak would break this, so a high identity rate is simultaneously the
"q1=prior / q4=4th-prior" and the no-lookahead proof. **Actual output (82-name diverse basket):**

```
family                         CLEAN(¬Apr-May) shift/total   rate     ANNUAL(Apr-May)
n_income_sq:  q1 vs q0              826/827          99.88%        (70.8%)
total_assets: q1 vs q0             814/816          99.75%        (71.7%)
... (all 10 q1-vs-q0 fields)       99.73 – 100.00%
n_income_sq:  q4 vs q3 (mature)    603/632          95.41%        (65.3%)   <- deepest slot
n_cashflow_act_sq: q4 vs q3        582/631          92.23%        (61.2%)   <- deepest slot
clean-stock value-run identity: 600519/000002/600036/601318 each 20/20 on q1, q4 AND total_assets
slot-distinctness: q1!=q0 on ~99% of rows
VERDICT: PASS (q1 floor 98%, q4 floor 90%, clean-stock run-identity 100%)
```

**The judgement calls I made (please pressure-test):**
1. I **exclude April-May** from the gating rate. Justification: empirically 98% of identity breaks
   fall in months 4-5 — the annual-report + Q1 dual-disclosure window, where (a) q0 leapfrogs a
   period when annual & Q1 file together, and (b) the audited annual restates the held period
   (verified example: `000333 2020-05-06` q1=audited-2019-annual vs q0[t-1]=express-2019-annual —
   q1 holds the genuine prior period, just restated). **Is excluding Apr-May legitimate, or am I
   hiding a real disclosure-window bug?**
2. I **gate q1 at 98% (passes ~100%) and q4 at a looser 90%**, justifying the deeper slot's ~5-8%
   clean-window residual as "cumulative-restatement exposure" (e.g. `000538`'s 2019 reverse-merger).
   The clean-stock run-identity (20/20 including q4) is my decisive positional proof. **But I did NOT
   exhaustively attribute every q4 break to a restatement event — I spot-checked.** Is the
   clean-stock proof + spot-check enough to call q4 positionally correct, or do you want every
   clean-window q4 break traced before CFOAD/ROAD/CCRD/ROED (which sum q1..q4 for their prior-TTM)
   are trusted? I flagged this as an OPEN, non-blocking item — is "non-blocking" defensible given
   those factors are capped at candidate anyway?
3. Is the roll-forward identity even the right test, or is there a stronger independent value check
   I should run (e.g. reconstruct the single-quarter from raw cumulative statements and compare)?

## Requested verdict

Per prior rounds: overall verdict + numbered confirmations/objections. Especially: (a) is qual_aprd
removal (vs rebuild) right, and the APR numerator/denominator; (b) is the "6 faithful" set actually
clean or did I miss a proxy; (c) **is the canary's Apr-May exclusion + q1/q4 split-floor legitimate
or am I excusing a real problem**; (d) is the q4 residual genuinely safe to leave as a non-blocking
open item. Nothing has been promoted — all are drafts at candidate_ceiling; the proxies are now
hard-capped.
