# PR3 (book-level promotion machinery) — GPT §10 implementation review prompt (ROUND 15)

R1..R13 REWORK → all folded. R14 REWORK (1B/1M/1m — VERIFIED TOCTOU: the entry guard captured
`_validated_runtime_horizons()` but the compute leaf and the persistence re-read the global, so a
mid-call rebind to the still-LEGAL (10,5,20) executed a 10d LS judgment under a sealed 5d declaration
WITH seal + A5 state written; the book path's injectable `compute_metrics_fn` + bare
`eval_protocol_hash` are an S6-precondition bypass surface; my "zero int() coercion in src" claim was
too broad) → **all folded**. Branch: `calendar-unfreeze`.

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. ROUND-15 re-review of PR3: verify the R14 finding is genuinely closed (re-run your probes) and surface anything new. Do not rubber-stamp. Top invariant at stake: the judgment axes verified at declaration time must be THE axes that execute and THE axes that persist — one immutable snapshot, no re-read window.

REPO (public) https://github.com/henrydan111/quant-system  (branch: calendar-unfreeze)
Raw form: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/<path>

FETCH (authoritative):
- src/research_orchestrator/promotion_evidence.py          (snapshot threading: entry → leaf → persistence)
- src/alpha_research/factor_eval_skill/book_seal.py        (S6 preconditions pinned in the live refusal)
- tests/research_orchestrator/test_promotion_evidence.py   (the mid-call rebind regression)
- tests/alpha_research/test_pr3_book_seal.py               (R1..R14 probes pinned)

YOUR R14 FINDINGS — how each was closed (your exact prescription):
Blocker (TOCTOU axis drift) → the ENTRY-captured immutable snapshot is now threaded end-to-end:
   * `_validated_runtime_horizons(horizons=None)` validates a PASSED snapshot when given; it reads the
     module global only when none is passed (standalone callers, e.g. book diagnostics).
   * `reproduce_sealed_oos` passes its entry snapshot into `_compute_oos_per_factor_metrics(...,
     runtime_horizons=snapshot)` — the leaf executes EXACTLY that tuple (compute_factors horizons,
     run_batch_screening horizons, per-factor ls_sharpe_horizon).
   * the PERSISTED record (`ls_sharpe_horizon`, `metric_note`) is built from the SAME snapshot — no
     `SCREENING_HORIZONS` re-read anywhere after the entry guard on the sealed path.
   * Pinned with your exact probe shape: test_midcall_horizon_rebind_cannot_swap_executed_axis —
     declare (5,10,20)/5, pass the entry guard, rebind the global to the LEGAL (10,5,20) via a hook
     that runs between the guard and the leaf (the expression resolver), and assert the leaf received
     [5,10,20], the persisted ls_sharpe_horizon is 5, and the metric_note carries
     screening_horizons=(5, 10, 20).
Major (book-path S6 bypass surface) → per your scoping this is an S6 PRECONDITION, not a live hole
   (live is hard-refused). The live-refusal message in run_book_sealed_evaluation now PINS the three
   preconditions verbatim so the S6 implementer cannot miss them: (1) full EvalProtocolSpec instead of
   the bare eval_protocol_hash string, verified observation_protocol_hash ==
   frozen_set.eval_protocol_hash; (2) live FORBIDS injected book_backtest_fn / compute_metrics_fn (an
   injected callable bypasses the validated-horizons guarded leaf); (3) verifier registration in
   REGISTERED_GOVERNED_RUNNER_VERIFIERS. No behavioral change to the intentional
   reserve→claim→backtest→diagnostics ordering (v1.4 one-seal-per-book with in-book diagnostics).
Minor (overbroad claim) → CORRECTED: the accurate statement is that the R13 judgment-axis fields
   (screening_horizons / ls_sharpe_horizon) carry NO coercion anywhere; `int(self.horizon)` /
   `int(self.n_quantiles)` normalization remains in identity/sealed_oos payloads and constructor-axes
   validation — those are validated-then-normalized BEFORE execution and are not an identity/execution
   fork. This record supersedes the previous wording.

Your five clarifications are absorbed: (1) noted — your 133+96 comes from your two attachment
commands, which I cannot reconstruct exactly from the totals; to avoid another counting mismatch, THIS
round's suggested subsets are named explicitly below with locally-verified counts; (2) book-path
claim-before-diagnostics is by design; (3) construction-level `ls_sharpe_horizon in
screening_horizons` + runtime `== runtime[0]` layering retained as you endorsed; (4) no Python
`assert` guards any invariant (none was added; the runtime validator is the enforcement);
(5) production EvalProtocolSpec construction remains exclusively in sealed_oos's official constructor.

TEST STATE: 601 passed across the full affected suite (serial); full-dir sentinel clean. Named
subsets with locally-verified counts (each <30s):
  pytest tests/alpha_research/test_pr3_book_seal.py tests/research_orchestrator/test_r4_wall_hardening.py -q            -> 116 passed
  pytest tests/research_orchestrator/test_promotion_evidence.py tests/alpha_research/test_v14_book_level_promotion.py tests/alpha_research/test_factor_eval_skill_identity.py -q   -> 57 passed
Clean-checkout data-dependent failures (gitignored provider_build.json / calendars) remain environment.

SELF-REVIEW PREFLIGHT — VERDICT: clean for GPT round 15.
RESIDUAL CONCERNS (honest list):
(a) The snapshot threading covers the SEALED path (reproduce → leaf → persistence). The book
    diagnostics leg calls the leaf WITHOUT a snapshot (validates the global at call time) — it runs
    inside an already-claimed book context whose protocol identity is the bare-hash surface already
    scoped to S6 precondition (1); the S6 runner should thread its own verified snapshot the same way.
(b) The mid-call rebind pin hooks the expression resolver as the between-guard-and-leaf interception
    point; a rebind at OTHER interleavings (e.g. inside compute_factors_fn itself) is covered by the
    same mechanism (the leaf already holds the snapshot before calling compute_factors_fn).
(c) Your standing final residual is unchanged and remains the agreed follow-up scope: versioned,
    fail-closed replay/migration for historical bar/evaluator versions (with the S6 governed runner +
    the formal-OOS routing lint).

REVIEW QUESTIONS
1. Re-run your R14 TOCTOU probe (entry-pass then legal rebind). EXECUTED_HORIZONS must stay [5,10,20]
   with the persisted record matching the declaration. Any interleaving still landing?
2. Residual (a): is deferring the book-leg snapshot threading to the S6 runner (with the bare-hash
   fix) acceptable, or do you want the diagnostics leg to thread a snapshot now?
3. Anything else blocking SHIP for the machinery layer (S6 governed runner + real-data burned-window
   pilot + versioned bar/evaluator migration remain scoped future PRs; live promotion is unreachable
   until a verifier registers).

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending line quoted and an exact suggested
  replacement. Map every Blocker to the principle or invariant it violates.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.
```
