# GPT Cross-Review Request — NF integration P4b (per-stock decision driver) — Tier-2

Reviewing **one unit**: P4b, the thin per-stock orchestration above the hardened P4a doors — the last
producer stage of the NF chain (C1 session embedding is the remaining consumer unit).

## ⚠ FROZEN REVIEW TIER — Tier-2

Per CLAUDE.md §10: the tier is set at design freeze and **the reviewer must not escalate it mid-arc**.
Tier-2 = declared-invariant review against ordinary well-formed inputs. Tier-1 crafted-object /
dunder / adversarial-caller analysis is OUT OF TIER — the security surface lives BELOW this module in
the P4a doors, which closed their own Tier-1 arc (round-4 SOUND at `5d3d0be` under threat model v3).
The v3 scope rule applies: root selection is out of scope; findings hold the root set fixed.

**Commit under review: `7f34551`** on branch `calendar-unfreeze`.

## Context

P1 → P2 → P3a → P3b all SOUND; P4a (ledger + archive chain binding) SOUND under
[NF_ARCHIVE_THREAT_MODEL.md](https://raw.githubusercontent.com/henrydan111/quant-system/7f34551/workspace/research/ai_research_dept/NF_ARCHIVE_THREAT_MODEL.md)
v3. P4b wires them: per (stock, cutoff) — committed-evidence assemble → `record_decision` →
`execute_news_decision` (factor + penalty LLM legs; commitment happens inside) →
`seal_decision_archive`.

## Declared invariants (the review target)

1. **Deterministic decision identity** — `nf:{ingest_class}:{ts_code}:{cutoff_iso}` with the same
   canonical-cutoff normalization every other door uses; the same (stock, cutoff, class) always
   claims the same ledger slot, so re-runs meet first-write-wins instead of minting parallel
   decisions.
2. **Committed evidence only** — the driver's P3b inputs come from `resolve_committed_evidence`, the
   SAME trusted-root resolution the record door re-runs; a driver-built artifact is by construction
   the one the door will prove.
3. **One object flow** — the same `(artifact, assembly)` pair flows assemble → record → execute →
   seal; never re-assembled between steps.
4. **Crash-safe idempotent re-entry** — an existing SUCCESS commitment is never re-executed (the
   test's counting probe asserts the LLM is not re-invoked); commit-but-no-seal recovers pure-disk
   via `recover_and_seal_success_archive`; `hard_failed` does NOT block a retry (success-unique gates
   success only; each execution keeps its own immutable audit archive).
5. **NothingToDecide propagates** with zero writes (no ledger row, no provenance, no archive).
6. **Identities out, payloads sealed** — the return dict carries identities + hashes only; consumers
   go through `load_and_verify_decision_archive` (C1's door).

## Declared design decisions (challenge explicitly)

- **The success-resume check runs AFTER `record_decision`.** Order: resolve → assemble → record
  (idempotent) → check `find_success_commitment` → resume-or-execute. Recording before the resume
  check re-proves the chain on every re-entry (a re-run with a now-inconsistent store fails closed at
  the record door rather than silently resuming); the cost is one re-derivation per re-entry. Is that
  the right order, or should resume short-circuit before the proof?
- **`hard_failed` returns normally** (identities with `news_status="hard_failed"`) rather than
  raising — the caller (a future per-day batch driver) decides retry policy; the executors already
  guarantee the audit trail. Right call?
- **The driver takes `contract` + `call_fn` as parameters** — binding the on-disk `ChainContract` and
  the real LLM route is the final-integration unit's job (with the production ROOT binding, the
  FORWARD_PREREG governed-runner obligation of threat model v3). P4b deliberately does not read any
  global config.

## Files (pin to `7f34551`)

- https://raw.githubusercontent.com/henrydan111/quant-system/7f34551/workspace/research/ai_research_dept/engine/news_flash_decide.py
- https://raw.githubusercontent.com/henrydan111/quant-system/7f34551/workspace/research/ai_research_dept/tests/test_news_flash_decide.py
- design: https://raw.githubusercontent.com/henrydan111/quant-system/7f34551/workspace/research/ai_research_dept/NF_UNIT_P4_DESIGN.md
- the doors below (context, closed units): [news_decision.py](https://raw.githubusercontent.com/henrydan111/quant-system/7f34551/workspace/research/ai_research_dept/engine/news_decision.py) · [news_archive.py](https://raw.githubusercontent.com/henrydan111/quant-system/7f34551/workspace/research/ai_research_dept/engine/news_archive.py) · [news_flash_assemble.py](https://raw.githubusercontent.com/henrydan111/quant-system/7f34551/workspace/research/ai_research_dept/engine/news_flash_assemble.py)

## Self-review

Clean for GPT. Premise checks done: `execute_news_decision` commits internally (news_executors:697),
so the driver never touches commitment APIs; `recover_and_seal_success_archive` is idempotent against
an already-sealed archive; the resume path reads the EXECUTION archive by the success commitment's
`execution_id` (per-execution audit door), not the decision-level canonical door, because the two are
equivalent once success-unique holds. Tests: 8 P4b (identity determinism incl. str-vs-Timestamp
cutoffs, round-trip through the consumer door, no-LLM resume probe, crash recovery, hard_failed
retry with two independent archives, zero-write NothingToDecide, cross-variant first-write-wins) +
full `ai_research_dept` **880** green.

## Review questions

1. **Re-entry matrix:** fresh / success-sealed / success-committed-unsealed / hard_failed-only /
   nothing-routed — is every cell handled, and is there a state the driver can reach that leaves the
   ledger/provenance/archive in a shape a later re-entry cannot resolve?
2. **Identity:** any way two distinct (stock, cutoff, class) triples collide into one `decision_id`,
   or one triple into two ids (the cutoff is canonicalized microsecond-max upstream)?
3. **The three declared design decisions** above.
4. **Verdict:** SOUND-TO-PROCEED (to C1) or a specific in-tier declared-invariant gap.
