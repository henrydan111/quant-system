# PR3 (book-level promotion machinery) — GPT §10 implementation review prompt (ROUND 5)

R1 REWORK (5B/3M/1m) → folded. R2 REWORK (5B/3M) → folded. R3 REWORK (3B/1M/1m) → folded.
R4 REWORK (3B/1M/2m — caller-suppliable seal_root forks the sealed world; allow_same_run recomputes a
completed OOS; low-level entry accepts arbitrary factor_exprs; a6-for-A5 not request-bound; in-batch
diagnostic dup; show-mode virgin preview reads the wrong ledger) → **all folded**. R4 confirmed the R3
six closed within one seal root. Branch: `calendar-unfreeze`.

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. ROUND-5 re-review of PR3: verify each R4 finding is genuinely closed (re-run your probes) and surface anything new. Do not rubber-stamp. The single most important invariant: a caller must NOT be able to build a new "sealed world" (fork the seal store / budget ledger) and re-read the same OOS window.

REPO (public) https://github.com/henrydan111/quant-system  (branch: calendar-unfreeze)
Raw form: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/<path>

FETCH (authoritative):
- src/research_orchestrator/holdout_seal.py                 (resolve_configured_global_holdout_root — the ONE root)
- src/research_orchestrator/promotion_evidence.py           (no seal_root/factor_exprs; completion machine; recipe hash)
- src/alpha_research/factor_eval_skill/book_seal_stores.py  (A5ReproductionStore; has_authorization; batch-dup)
- src/alpha_research/factor_eval_skill/stores.py            (reserve_a5_study_spend: request-bound a6 consume)
- src/alpha_research/factor_eval_skill/sealed_oos.py        (no seal_root/factor_exprs passthrough)
- src/alpha_research/factor_eval_skill/orchestration.py     (cmd_seal: configured root; show-mode virgin preview)
- workspace/scripts/factor_eval_cli.py                      (--holdout-seal-root override removed)
- config.yaml                                               (research_governance.holdout_seal_root)
- tests/alpha_research/test_pr3_book_seal.py                (R1..R4 probes pinned)
- tests/research_orchestrator/test_promotion_evidence.py    (resolver/catalog seams)
- tests/research_orchestrator/test_r4_wall_hardening.py

YOUR R4 FINDINGS — how each was closed (verify in code; probes pinned as named tests):
B1 (caller-suppliable seal_root forks the sealed world) → the public seal_root parameter is REMOVED
   from reproduce_sealed_oos AND run_sealed_oos; both derive EVERY sealed store (seal events, override
   authorizations, the A5/A6 ledger, the A5 reproduction records) from resolve_configured_global_holdout_root()
   (holdout_seal.py) — config.yaml research_governance.holdout_seal_root, else the canonical
   data/holdout_seals. The CLI --holdout-seal-root override is removed. Tests monkeypatch the RESOLVER
   (never pass a path). Pinned: test_reproduce_sealed_oos_virgin_authorizes_ledgers_then_claims asserts
   `seal_root` is not a parameter and that the spend lands in the resolver-derived ledger;
   test_live_seal_uses_configured_root_and_catalog_gate.
B2 (allow_same_run recomputes a completed OOS) → the new A5ReproductionStore is a completion state
   machine keyed by seal_key with request binding: reproduce_sealed_oos consults it FIRST — a `complete`
   record returns its PERSISTED result and NEVER recomputes (and never re-claims / re-consumes); only a
   not-yet-existing key opens a fresh claim; a still-`claimed` (crash) state of the IDENTICAL request
   resumes WITHOUT re-consuming or re-reserving; a changed recipe refuses. Pinned:
   test_completed_a5_reproduction_is_never_recomputed (metric_compute_calls stays 1 across two identical
   calls) + test_direct_a5_changed_recipe_cannot_reuse_the_spend.
B3 (low-level entry accepts arbitrary factor_exprs) → the public factor_exprs parameter is REMOVED;
   resolve_frozen_catalog_expressions(frozen_set) resolves expressions from the CURRENT catalog and
   REQUIRES (a) every SelectedFactor exists in the catalog and (b) the current catalog definition_hash
   EQUALS the frozen SelectedFactor.definition_hash (the P1.3 definition-binding parity primitive) —
   exactly the selected ids, nothing more. Pinned: TestCatalogExpressionResolution
   (exact-ids / definition-drift-refused / missing-factor-refused) + the orchestration catalog-gate test.
M1 (a6-for-A5 not request-bound) → reserve_a5_study_spend now CONSUMES the a6 authorization (not just
   require_consumed) bound to consumed_by_request_hash = the A5 request, and ONLY when the hard band is
   actually hit (no waste below it). An a6 consumed for another recipe can never admit this spend.
   Pinned: test_direct_a5_hard_band_consumes_request_bound_a6.
m1 (in-batch diagnostic dup) → append_rows tracks batch_keys and refuses a duplicate logical key WITHIN
   one batch (not only vs disk). Pinned: test_append_rows_batch_idempotent_and_divergence_refused
   (extended) / the batch-dup path.
m2 (show-mode virgin preview reads the run-local ledger) → cmd_seal computes virgin = is_virgin_window
   up front and, for a virgin window, the governing report (show AND live) is virgin_window_multiplicity
   over the CANONICAL ledger at the configured root. Pinned: test_cmd_seal_show_previews_canonical_virgin_budget
   (4 canonical spends + pending => n_spent=5, refuse_without_override).

Also folded from your R4 residual (a): a crash-resume of the identical recipe no longer burns a fresh
A5 authorization (is_fresh_open gating on the reproduction record) — see the disclosed residual below
for the one remaining narrow window.

NON-TEST CALLERS: the 5 one-off promotion drivers under workspace/scripts/ (promote_gp/eps/arxiv/winners,
select_e_wave) targeted the PRE-R4 signature; they are HISTORICAL records of already-spent windows (the
spend is in the provenance JSONs), NOT re-runnable, and now carry a "HISTORICAL DRIVER (pre-PR3-R4)"
banner. They are intentionally not rewired.

TEST STATE: 548 passed across the full affected suite (serial). Subsets fitting a 124s budget:
  pytest tests/alpha_research/test_pr3_book_seal.py tests/research_orchestrator/test_promotion_evidence.py -q   (~10s)
  pytest tests/alpha_research/test_factor_eval_skill_orchestration.py tests/research_orchestrator/test_r4_wall_hardening.py -q   (~10s)
As you noted at R3/R4: a clean checkout without the gitignored data/ tree (provider_build.json, screening
metadata) fails a handful of data-dependent tests — environment, not code.

SELF-REVIEW PREFLIGHT — VERDICT: clean for GPT round 5.
RESIDUAL CONCERNS (honest list):
(a-narrowed) The consume->reserve->claim->record->compute->complete sequence is fail-closed but not
    fully atomic: the reserve is idempotent by request_hash and the seal claim is idempotent under
    allow_same_run, so a crash never double-spends the ledger or double-claims the seal. The ONE
    non-idempotent-on-resume step is the consume-once A5 authorization: a crash in the narrow window
    AFTER consuming it but BEFORE the reproduction `claimed` record is written strands that
    authorization (resume fails closed with "already consumed"), requiring one manual re-record of a
    fresh A5 authorization (the ledger/seal then resume idempotently). Fail-closed (never a silent
    double or unbudgeted spend). Should consume become idempotent-by-request (skip if already consumed
    by THIS request_hash) to close even that window, or is the fail-closed manual-re-record acceptable
    for the machinery layer?
(b) resolve_frozen_catalog_expressions reads the live catalog + registry at call time; a definition
    drift between seal time and reproduce time correctly refuses (the sealed recipe is no longer
    reproducible) — this is intended, but means a legitimately-migrated factor needs a migration_record
    path (not in PR3; the legacy revalidate path exists separately).
(c) config.yaml research_governance.holdout_seal_root is a project-root-relative default; a deployment
    that relocates data/ must set it. The resolver falls back to <project_root>/data/holdout_seals.
(d) The completion state machine keys by seal_key (frozen_set_hash); two DIFFERENT recipes on the same
    frozen set produce the same seal_key but different request_hash — the second refuses at open_or_resume
    ("changed recipe can never resume"), which is correct (one frozen set = one sealed spend) but means
    a genuine re-selection on the same frozen set is blocked at this layer by design.

REVIEW QUESTIONS
1. Re-run your R4 probes (new-root fork => canonical_events vs fork_events; allow_same_run double-compute;
   arbitrary factor_exprs; a6-for-A5 cross-recipe; in-batch dup; show-mode virgin preview). Any land?
2. Residual (a-narrowed): is the fail-closed manual-re-record acceptable, or must consume be
   idempotent-by-request?
3. Is resolve_configured_global_holdout_root the right seam (config key + canonical fallback + single
   monkeypatch point), or do you require an explicit injected dependency instead of a module function?
4. Anything else blocking SHIP for the machinery layer (the S6 governed runner + real-data burned-window
   pilot remain future PRs; live promotion is unreachable until a verifier registers).

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending line quoted and an exact suggested
  replacement. Map every Blocker to the principle or invariant it violates.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.
```
