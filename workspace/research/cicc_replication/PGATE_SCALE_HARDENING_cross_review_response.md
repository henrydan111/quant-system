# P-GATE gate-at-scale hardening — cross-review response & triage

> 2026-06-14. After the gate-at-scale hardening (commit `d683eed`), GPT 5.5 Pro first reviewed
> STALE code (it had fetched `ac668dc`, pre-hardening) → I pushed; on re-review against `d683eed`
> it returned **APPROVE WITH CONDITIONS**, confirming the pushed code resolves the stale-code
> objections (F11 ledger, F3 stamp + dropped-link fail-closed, F9-full per-domain, exact-calendar
> quarantine, OOS assertion, APRD tier all verified present) and that **none of the residual gaps
> block current draft / candidate-ceiling / field-registration / P-OP work** — they gate a future
> at-scale publish wave and any sealed-OOS spend. Per the user's directive, items #2/#3/#4 are
> folded in now; #1 is a deliberate, documented deferral.

## Triage

| GPT condition | Gates | Verdict | Action |
|---|---|---|---|
| **#2** OOS quarantine enforced only in the event handler, not the universal seal-claim chokepoint | sealed-OOS spend | **Folded in** | `_assert_cicc_oos_quarantine` MOVED to `steps._claim_holdout_access_if_needed` (the single chokepoint every OOS path — event-driven, vectorized, promotion-evidence — routes through to claim a seal), called BEFORE the seal claim. The per-handler call in `validation_steps` is removed (helper relocated to `steps.py` to avoid an import cycle). |
| **#3** ledger records `definition_hash` but the gate doesn't verify it for drift (+ silent auto-relink) | at-scale publish | **Folded in** | `_cohort_ceiling` takes `linked_definition_hash`; an active link whose hash ≠ the current registry hash **raises** (stale linkage — definition drifted since link). The handler no longer silently writes a `relinked` event every run — it appends a `linked` event ONLY for a genuinely new link; drift must be resolved by an explicit relink. |
| **#4** linkage stamp/ledger write is non-fatal | at-scale publish | **Folded in** | The stamp/ledger persistence for confirmed cohort factors is now **fatal** (no `try/except` swallow) — a write failure raises before any `set_status`, so a promoted factor can never lack a durable link (which would defeat the dropped-link fail-closed check). |
| **#1** never-created link still fails open (only dropped links guarded) | at-scale publish | **Deferred (documented)** | The robust fix is a run-scoped pre-declared expected-cohort-factor allowlist (GPT's recommendation; a name-heuristic is fragile and GPT called it only a "secondary warning"). It gates an at-scale *auto*-publish workflow that does not exist yet — today's waves are explicit named batches via `gate_cohort_factors.py`, where a missing link is visible to the operator. Building run-scope plumbing now would be premature; deferring with a clear design note is the right sequencing. |
| **#6** OOS guard asserts every matching record (conservative / over-block-prone) | — | **Accepted as interim** | GPT confirmed strictest-all is safe as an interim before any OOS spend; refine to claim/universe-resolved selection if/when domain-specific OOS is run. Recorded. |
| **#7** 20+5 quarantine horizon is a global default | — | **Accepted as interim** | GPT confirmed 20+5 trading days is correct for the current truth tables; make horizon/embargo per-truth-source metadata when a chart uses a different label horizon. Recorded (the manifest rows can carry `truth_label_horizon_trading_days` later). |

## Verification

- Tests: **177 pass** (lifecycle + governance + `pr8d` OOS-seal boundary + `pr9` validation-field-gate + registry parity), including new units: F11 definition-drift fail-closed, the seal-claim chokepoint guard (enforces + no-ops + refuses approximate).
- Live dry-run re-gate of the already-linked cohort factors: **no false drift** (matching `definition_hash` → adjudicates normally), ceilings stable (`candidate_ceiling`, 4 with `proxy_approx`). The drift check fires only on a genuine hash change.

## Net state

- **Sealed-OOS condition: now satisfied** — the quarantine is enforced at the universal seal-claim chokepoint with an exact (non-approximate) boundary; any approximate or pre-quarantine CICC OOS claim is refused before the seal is spent.
- **At-scale-publish condition: #3 + #4 done; #1 remains** — a never-created link is the one residual at-scale gap, deferred by design until an at-scale auto-publish workflow exists.
- Nothing promoted; resolve-but-label intact; proxies hard-capped. Current draft / field-reg / P-OP work is unblocked (per GPT).
