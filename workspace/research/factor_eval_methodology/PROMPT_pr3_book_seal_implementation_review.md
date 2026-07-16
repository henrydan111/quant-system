# PR3 (book-level promotion machinery) — GPT §10 implementation review prompt (ROUND 12)

R1..R10 REWORK → all folded. R11 REWORK (1B/1m — runtime-EQUAL parameters were not runtime-EXECUTABLE:
a matched horizon=60 was accepted, computed NOTHING [rank_icir_60d never exists → NaN metrics] and
still consumed a seal; a matched n_quantiles=5 executed a QUINTILE spread while the persisted protocol
declared decile_long_short; identity-type comments still advertised the retired universe/rebalance
semantics) → **all folded**. R11 confirmed both R10 fixes real (SimpleNamespace, two-specs-one-recipe,
subclass record() ratchet, persisted payload, full_provider_universe honesty). Branch: `calendar-unfreeze`.

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. ROUND-12 re-review of PR3: verify the R11 finding is genuinely closed (re-run your probes) and surface anything new. Do not rubber-stamp. Top invariant at stake: the declared protocol must be the EXECUTABLE runtime recipe — equal is not enough; the runtime must actually compute it.

REPO (public) https://github.com/henrydan111/quant-system  (branch: calendar-unfreeze)
Raw form: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/<path>

FETCH (authoritative):
- src/alpha_research/factor_eval_skill/sealed_oos.py       (EXECUTABLE_HORIZONS + validate_executable_protocol_axes)
- src/research_orchestrator/promotion_evidence.py          (independent axes validation before ANY governance action; SCREENING_HORIZONS = EXECUTABLE_HORIZONS)
- src/alpha_research/factor_eval_skill/orchestration.py    (cmd_seal wraps the constructor ValueError)
- src/alpha_research/factor_eval_skill/identity.py         (corrected field comments; rebalance default "none")
- tests/alpha_research/test_pr3_book_seal.py               (R1..R11 probes pinned)
- tests/research_orchestrator/test_promotion_evidence.py   (fixtures now 20/10)

YOUR R11 FINDING — how it was closed (your exact replacement, verbatim where given):
Blocker (runtime-equal ≠ runtime-executable) →
   * sealed_oos.EXECUTABLE_HORIZONS = (5, 10, 20) + validate_executable_protocol_axes(horizon,
     n_quantiles): horizon must be IN the executable set; n_quantiles must equal
     DEFAULT_N_QUANTILES (the decile standard). executable_protocol_spec() validates through it.
   * reproduce_sealed_oos calls the SAME validator INDEPENDENTLY (exact-type callers can construct
     EvalProtocolSpec directly), at the very top — before the calendar guards, before any store, any
     authorization, any claim — wrapping ValueError as PromotionEvidenceError.
   * SCREENING_HORIZONS = EXECUTABLE_HORIZONS (one constant — the executable axes ARE the screening
     horizons; no second copy to drift).
   * cmd_seal wraps the constructor's ValueError as FactorEvalError (pinned:
     test_cmd_seal_wraps_axes_error — horizon=60 and n_quantiles=5 both refuse at the CLI layer).
   * the successful 4/5 fixtures were replaced with 20/10 (test_promotion_evidence — the full
     reproduction + access-context tests now run the canonical decile recipe).
   * your negative probes pinned: test_matched_but_non_executable_axes_refuse_before_claim,
     parameterized over EXACTLY your two cases (60/10 matched-but-never-computed; 20/5
     quintile-vs-declared-decile), asserting ZERO evaluator calls, ZERO A5 ledger rows, ZERO seal
     events; plus test_constructor_refuses_non_executable_axes.
Minor (retired-semantics comments) → your exact replacement applied: universe_filter_policy is
   commented as the observation universe (A5 requires full_provider_universe) and the rebalance
   default is now "none" ("registration observations have no rebalance schedule"). Note the default
   change shifts protocol hashes only for direct default-constructed specs — the sanctioned
   constructor always passed rebalance explicitly via EXECUTABLE_PROTOCOL_FIELDS, and no live spend
   exists under any prior protocol identity.

TEST STATE: 594 passed across the full affected suite (serial); full-dir sentinel clean. Subsets
fitting a 124s budget:
  pytest tests/alpha_research/test_pr3_book_seal.py tests/research_orchestrator/test_promotion_evidence.py tests/research_orchestrator/test_r4_wall_hardening.py -q   (~10s)
  pytest tests/alpha_research/test_v14_book_level_promotion.py tests/research_orchestrator/test_pr9_validation_field_gate.py tests/alpha_research/test_factor_eval_skill_orchestration.py -q   (~10s)
Clean-checkout data-dependent failures (gitignored provider_build.json / calendars) remain environment.

SELF-REVIEW PREFLIGHT — VERDICT: clean for GPT round 12.
RESIDUAL CONCERNS (honest list):
(a) The validator hard-pins the DECILE standard; historical quintile evidence (pre-2026-06-11 rows)
    remains reproducible only through the NON-sealed research paths (n_quantiles=5 was always a
    documented reproduction knob there) — the SEALED path now refuses it by design.
(b) ls_sharpe is read at the PRIMARY horizon (5d) regardless of the declared rank_icir horizon —
    long-standing registration-bar semantics (documented in the metric_note and the bar), not a new
    axis; flagging so you can confirm it is within the declared-protocol contract (the persisted
    metric_note states it explicitly).
(c) Your standing final residual is unchanged and remains the agreed follow-up scope: no versioned,
    fail-closed replay/migration path for historical bar/evaluator versions yet (planned alongside
    the S6 governed runner + the formal-OOS routing lint).

REVIEW QUESTIONS
1. Re-run your R11 probes (horizon=60 direct sealed call; 20/5 quintile probe). Both must show zero
   evaluator calls / zero A5 rows / zero seal events. Any variant still landing?
2. Residual (b): is the fixed primary-horizon ls_sharpe within the declared-protocol contract as
   persisted, or do you require it as an explicit protocol field?
3. Anything else blocking SHIP for the machinery layer (S6 governed runner + real-data burned-window
   pilot + versioned bar/evaluator migration remain scoped future PRs; live promotion is unreachable
   until a verifier registers).

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending line quoted and an exact suggested
  replacement. Map every Blocker to the principle or invariant it violates.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.
```
