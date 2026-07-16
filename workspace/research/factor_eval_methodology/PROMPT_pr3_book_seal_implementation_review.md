# PR3 (book-level promotion machinery) — GPT §10 implementation review prompt (ROUND 11)

R1..R9 REWORK → all folded. R10 REWORK (2B/1m — protocol identity accepted duck-typed look-alikes and
was never verified against the recipe the runner actually executes [two real specs with different
horizons both ran the same 20d/10q recipe as two seals]; a subclass re-declaring
PUBLIC_RECORD_ENABLED=True reopened the base record() door; the R9 prompt named a pinned test that did
not exist) → **all folded**. Branch: `calendar-unfreeze`.

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. ROUND-11 re-review of PR3: verify each R10 finding is genuinely closed (re-run your probes) and surface anything new. Do not rubber-stamp. Top invariants: (1) ONE canonical sealed world; (2) one seal/request executes OOS at most once — including raw store-level forgeries and subclass tricks; (3) the declared judgment/protocol IS the executable canonical recipe — declarations are executed, never merely hashed.

REPO (public) https://github.com/henrydan111/quant-system  (branch: calendar-unfreeze)
Raw form: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/<path>

FETCH (authoritative):
- src/alpha_research/factor_eval_skill/_store.py            (MRO-walk PUBLIC_RECORD_ENABLED gate)
- src/alpha_research/factor_eval_skill/sealed_oos.py        (EXECUTABLE_PROTOCOL_FIELDS + executable_protocol_spec)
- src/research_orchestrator/promotion_evidence.py           (exact-type + runtime-recipe verification + payload persistence)
- src/alpha_research/factor_eval_skill/orchestration.py     (cmd_seal: executable constructor + unsupported-declaration refusals)
- tests/alpha_research/test_pr3_book_seal.py                (R1..R10 probes pinned)

YOUR R10 FINDINGS — how each was closed (verify in code; probes pinned as named tests):
B1 (protocol identity not bound to the executed recipe) → your exact repair:
   * `type(eval_protocol) is EvalProtocolSpec` (exact type — your SimpleNamespace probe refuses with
     zero governance actions).
   * the spec IS the runtime recipe, verified field by field BEFORE any claim: horizon, n_quantiles,
     and oos_window must equal the runner's actual parameters ("protocol/runtime mismatch" — your
     two-horizons-one-recipe probe now refuses instead of minting two seals), and EVERY remaining
     identity field must equal the new EXECUTABLE_PROTOCOL_FIELDS constants (metric=rank_icir,
     construction=decile_long_short, universe_filter_policy=full_provider_universe [the runtime
     truthfully computes over the full provider universe — the SELECTION universe remains
     FrozenSelectionSet/TUD identity, no longer smuggled into a runtime claim], neutralization=none,
     rebalance=none, label/rank/winsor/missing/tie/cost = the actual screening path). Unsupported
     declarations REFUSE — never merely hashed.
   * cmd_seal declares ONLY through the new sealed_oos.executable_protocol_spec() constructor and
     itself refuses non-executable metric / neutralization / portfolio_side up front (pinned:
     test_cmd_seal_refuses_unsupported_runtime_declarations; the old
     "portfolio_side moves the seal hash via cmd_seal" pin was rewritten — the FS identity property
     is retained at the FrozenSelectionSet layer, the cmd_seal reachability now refuses).
   * the canonical protocol payload is PERSISTED verbatim with its hash in the completion record
     (eval_protocol_payload).
   Pinned: test_declared_rank_rule_is_the_rule_actually_executed (NOW REAL — see Minor below;
   protocol/runtime mismatch on horizon + an unsupported neutralization, both refusing pre-claim with
   zero seal events) + the reworked test_arbitrary_eval_protocol_hash_is_rejected (signature pins,
   None, SimpleNamespace, wrong-bar-hash chain, foreign-frozen-set observation mismatch — all zero
   seal events).
B2 (subclass re-enables the record() door) → your exact replacement: the base gate now walks the MRO
   for an EXPLICIT `PUBLIC_RECORD_ENABLED is False` — once any ancestor state machine disabled it, a
   subclass re-declaring True cannot reopen it (one-way ratchet). Pinned:
   test_reenabled_subclass_cannot_reopen_record_door (both machines, over the SAME log, bound and
   unbound calls, crashed state stays execution_started, evaluator calls stay 1).
Minor (the R9 prompt named a non-existent test) → CORRECTED HONESTLY: that was a prompt-authoring
   error on my side in round 9 — the closest real pin then was the forged-bar canonical refusal. The
   named test now EXISTS as a real probe (protocol/runtime mismatch + unsupported-field refusal +
   zero-seal-event assertions), and this record supersedes the R9 claim.

TEST STATE: 590 passed across the full affected suite (serial); full-dir sentinel clean. Subsets
fitting a 124s budget:
  pytest tests/alpha_research/test_pr3_book_seal.py tests/research_orchestrator/test_promotion_evidence.py tests/research_orchestrator/test_r4_wall_hardening.py -q   (~10s)
  pytest tests/alpha_research/test_v14_book_level_promotion.py tests/research_orchestrator/test_pr9_validation_field_gate.py tests/alpha_research/test_factor_eval_skill_orchestration.py -q   (~10s)
Clean-checkout data-dependent failures (gitignored provider_build.json / calendars) remain environment.

SELF-REVIEW PREFLIGHT — VERDICT: clean for GPT round 11.
RESIDUAL CONCERNS (honest list):
(a) EXECUTABLE_PROTOCOL_FIELDS declares universe_filter_policy="full_provider_universe" and
    rebalance="none" — truthful to the runtime, and a DELIBERATE semantic change from the pre-R10
    specs that hashed the selection universe / a "20d" cadence into the protocol. No live spend
    passed through the old protocol identity; the selection universe remains FS/TUD identity.
    Flagging the re-declaration for your confirmation.
(b) The runtime-match check trusts `horizon`/`n_quantiles` as reproduce's own parameters — the spec
    is verified against what reproduce WILL pass to the metric computation; a divergence between
    reproduce's parameters and _compute_oos_per_factor_metrics' actual use would be a code bug inside
    the single audited function (no caller seam).
(c) Your R10 final residual stands and is the agreed next scope: NO versioned evaluator/bar migration
    path yet — intentional bar/protocol code changes leave historical sealed results fail-closed and
    unreplayable until a versioned registry (evaluator_hash → historical callable) ships. Proposed as
    the explicit follow-up PR alongside the S6 governed runner and the runner-routing lint.

REVIEW QUESTIONS
1. Re-run your R10 probes (SimpleNamespace protocol; two-specs-one-recipe; subclass re-enable over the
   same log). Any still land?
2. Residual (a): confirm the executable-truth re-declaration of universe/rebalance in the protocol
   (selection semantics stay in FS/TUD identity)?
3. Anything else blocking SHIP for the machinery layer (S6 governed runner + real-data burned-window
   pilot + versioned bar/evaluator migration remain scoped future PRs; live promotion is unreachable
   until a verifier registers).

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending line quoted and an exact suggested
  replacement. Map every Blocker to the principle or invariant it violates.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.
```
