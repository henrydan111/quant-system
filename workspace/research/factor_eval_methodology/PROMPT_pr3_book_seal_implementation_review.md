# PR3 (book-level promotion machinery) — GPT §10 implementation review prompt (ROUND 13)

R1..R11 REWORK → all folded. R12 REWORK (1B/1M/1m — the LS judgment horizon and the ORDERED screening
horizons were not protocol identity [your drift probe: (5,10,20) and (10,5,20) produced the SAME
protocol_hash while executing 5d vs 10d LS judgments]; the persisted metric_note falsely claimed the
decile path matches Round-6 quintile evidence bit-for-bit; the R11 regression neither bound the frozen
set to the illegal spec's observation hash nor checked the A5 state store) → **all folded**.
R12 confirmed R11 truly closed (both illegal-axes probes: zero provider/root/catalog/evaluator calls,
zero A5, zero seals). Branch: `calendar-unfreeze`.

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. ROUND-13 re-review of PR3: verify the R12 finding is genuinely closed (re-run your probes) and surface anything new. Do not rubber-stamp. Top invariant at stake: EVERY axis that changes the judgment metric is pre-declared hash material, verified against the runtime before any governance action — never an after-the-fact note.

REPO (public) https://github.com/henrydan111/quant-system  (branch: calendar-unfreeze)
Raw form: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/<path>

FETCH (authoritative):
- src/alpha_research/factor_eval_skill/identity.py         (screening_horizons + ls_sharpe_horizon = REQUIRED observation identity)
- src/alpha_research/factor_eval_skill/sealed_oos.py       (EXECUTABLE_LS_SHARPE_HORIZON; constructor declares both)
- src/research_orchestrator/promotion_evidence.py          (entry-point horizon-chain verification; corrected metric_note/docstrings)
- tests/alpha_research/test_pr3_book_seal.py               (R1..R12 probes pinned)

YOUR R12 FINDINGS — how each was closed (your exact replacements, verbatim where given):
Blocker (LS horizon + ordered screening horizons not identity) →
   * EvalProtocolSpec gains REQUIRED fields screening_horizons: tuple[int, ...] and
     ls_sharpe_horizon: int, serialized into the OBSERVATION payload
     ("screening_horizons": [int(h)...], "ls_sharpe_horizon": int(...)) — reordering the horizons or
     moving the LS horizon changes observation_protocol_hash (and therefore the seal key) BEFORE
     anything executes; __post_init__ fails closed on empty/non-positive values.
   * sealed_oos: EXECUTABLE_LS_SHARPE_HORIZON = EXECUTABLE_HORIZONS[0]; executable_protocol_spec()
     declares both (your exact constructor).
   * reproduce_sealed_oos: immediately after the entry axes validation — before ANY provider/store/
     authorization action — the exact-type check runs EARLY and then your exact two checks:
     declared screening_horizons must equal tuple(SCREENING_HORIZONS) and ls_sharpe_horizon must equal
     runtime_horizons[0] ("protocol/runtime mismatch: ...").
   * Pinned: test_judgment_axes_move_the_observation_hash (your drift probe inverted — (5,10,20)/5,
     (10,5,20)/10 and (5,10,20)/10 give THREE distinct observation hashes),
     test_required_judgment_axes_fail_closed, and
     test_declared_horizons_must_match_runtime_zero_side_effects (runtime constant monkeypatched to
     (10,5,20) against a (5,10,20) declaration bound to a MATCHED frozen set: refusal with zero
     evaluator calls, zero A5 state rows, zero A5 budget rows, zero seal events).
Major (false Round-6 bit-for-bit claim) → your exact metric_note replacement applied ("Canonical
   post-2026-06-11 sealed protocol ... Pre-2026-06-11 Round-6 evidence used quintiles and is legacy
   audit evidence; its ls_sharpe values are not bit-for-bit comparable"), plus the module-level
   SCREENING_HORIZONS comment and the reproduce docstring no longer claim Round-6 equivalence (the
   old quintile-era verification numbers are kept only as explicitly-historical context).
Minor (R11 regression gaps) → your exact replacement applied: the parameterized illegal-axes probe now
   binds matched_fs = dataclasses.replace(FS, eval_protocol_hash=spec.observation_protocol_hash) and
   asserts A5ReproductionStore + OosWindowLedgerStore + HoldoutSealStore ALL empty.

TEST STATE: 597 passed across the full affected suite (serial); full-dir sentinel clean. Subsets
fitting a 124s budget:
  pytest tests/alpha_research/test_pr3_book_seal.py tests/research_orchestrator/test_promotion_evidence.py tests/research_orchestrator/test_r4_wall_hardening.py -q   (~10s)
  pytest tests/alpha_research/test_v14_book_level_promotion.py tests/research_orchestrator/test_pr9_validation_field_gate.py tests/alpha_research/test_factor_eval_skill_identity.py -q   (~10s)
Clean-checkout data-dependent failures (gitignored provider_build.json / calendars) remain environment.

SELF-REVIEW PREFLIGHT — VERDICT: clean for GPT round 13.
RESIDUAL CONCERNS (honest list):
(a) The observation-identity extension changes observation_protocol_hash (and hence frozen-set/seal
    keys) relative to R10/R11-era specs — consistent with the standing position: no live spend exists
    under any prior protocol identity; the alias store bridges if a historical equivalence ever needs
    proving.
(b) SCREENING_HORIZONS remains the runtime truth the declaration is verified AGAINST; the constant and
    the executable set are one object (R11), so a drift needs a code change that also changes the
    canonical declaration — at which point old declarations refuse (your intended fail-closed
    direction).
(c) Your standing final residual is unchanged and remains the agreed follow-up scope: versioned,
    fail-closed replay/migration for historical bar/evaluator versions (planned with the S6 governed
    runner + the formal-OOS routing lint).

REVIEW QUESTIONS
1. Re-run your R12 drift probe (both orderings through the official constructor — the hashes must now
   differ) and the declared-vs-runtime mismatch probe (zero side effects). Any variant still landing?
2. Anything else blocking SHIP for the machinery layer (S6 governed runner + real-data burned-window
   pilot + versioned bar/evaluator migration remain scoped future PRs; live promotion is unreachable
   until a verifier registers).

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending line quoted and an exact suggested
  replacement. Map every Blocker to the principle or invariant it violates.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.
```
