# GPT Cross-Review Request — NF integration P4a (ledger + archive chain binding) — Tier-1

Reviewing **one unit**: P4a — the edits that discharge the five frozen P3b obligations inside the two
sealing-surface modules (`news_decision.py`, `news_archive.py`). The P4b per-stock driver is a separate
Tier-2 unit and is NOT in scope here.

**Commit under review: `371349c`** on branch `calendar-unfreeze`.

## ⚠ FROZEN THREAT MODEL — the round-1 sending precondition

This unit is reviewed **under the existing user-approved frozen threat model**:
https://raw.githubusercontent.com/henrydan111/quant-system/371349c/workspace/research/ai_research_dept/NF_ARCHIVE_THREAT_MODEL.md
(v2). Its load-bearing criterion: *a boundary function is defective iff a crafted in-process instance
can (i) get a forged / non-exact / decoupled value sealed or accepted, (ii) mutate
already-verified/trusted state, or (iii) leak — a benign callback on a raising path is out of scope.*
The P4a edits live inside that same trust boundary (the ledger + sealed archive), so no new threat
model is minted; the tier assignment (P4a Tier-1 / P4b Tier-2) is the user's decision, made at design
freeze.

**Classify every finding in-scope / out-of-scope against that criterion and return a scope-bounded
verdict.** A finding gates iff it demonstrates an in-scope class with a probe needing no out-of-scope
capability.

## What P4a must achieve (the five obligations, frozen at the end of the P3b arc)

| # | obligation | where discharged |
|---|---|---|
| a | `assembly` REQUIRED at `record_decision` / `seal_decision_archive` — no default, no `None` path | keyword-only, no default; `require_assembly_for` refuses non-`AssemblyProvenance` |
| b | verify the D7 artifact FIRST, then bind — binding to an unverified artifact proves nothing | record: `verify_d7_artifact` → `require_assembly_for`; seal: binds `verify_execution_bundle`'s internal verified copy (see delta 2) |
| c | the decision ledger entry pins `assembly_hash` | + embeds the FULL `assembly.payload` (see delta 1); first-write-wins now refuses a second chain for the same artifact; `_read_chain` self-consistency pair check |
| d | archive `_ARCHIVE_SCHEMA` v1→v2 embedding the assembly, re-verified on read-back | strict key set + `assembly`; seal cross-checks ledger-pinned chain; read-back recomputes + re-binds + re-checks the ledger on the SAME chain snapshot |
| e | refusal tests incl. "a v1-shaped archive must not verify" | 14 tests in `test_news_p4a_chain_binding.py` |

## Two implementation deltas from the frozen obligation text (rule on both)

1. **The ledger row embeds the full `assembly.payload`, not only the hash.** The obligation said
   "write `assembly_hash` into the ledger entry". Hash-only would make `recover_and_seal_success_archive`
   impossible: it rebuilds from **pure disk state** after a crash between commit and seal, and the
   assembly would exist only in dead memory. The embed follows this codebase's own precedent — the
   commitment row embeds the full contract payload for exactly this reason (re-review#5 P0). Recovery
   now recovers the assembly from the ledger row (recompute → bind → normal seal), signature unchanged.
2. **Seal does not run its own `verify_d7_artifact` at entry.** My first attempt did, and the pinned
   GPT #23 P1#1 probes failed immediately: an entry-point artifact verification is a registry
   `.items()` callback point that fires BEFORE `verify_execution_bundle`'s contract/outcome snapshots —
   re-opening the exact timing class those probes pin. The fix: `verify_execution_bundle` now also
   returns its internal `verified_artifact` (the independent trusted copy produced AFTER the
   snapshots), and seal binds the assembly against that copy. Obligation (b)'s substance — bind only to
   a verified artifact — holds; the verification just happens at the already-established point.

## One behavioral change to flag

`ledger_head_at_seal` is now the tail of the **same** `_read_chain` snapshot used for the assembly
cross-check (previously a separate, possibly later, `ledger_head()` read). The decision row and the
success commitment are both already in the chain when seal runs, so the ancestry rule
(commitment `seq` ≤ anchor `seq`) still holds; the anchor can only be *older* than before, never
younger than the commitment. Flag if you see a case where this matters.

## Self-review (done before sending, per §10)

- Timing classes: the only new pre-snapshot code in seal is the `require_exact_id`-shaped kwarg
  presence itself (no reads); binding + cross-check run strictly after the snapshots, on plain/verified
  objects. The pinned #23 probes and the full 861-test suite pass.
- New surfaces checked against the v2 criterion: `_find_decision` / `_require_ledger_assembly` operate
  on `_read_chain` output (plain JSON dicts); `require_assembly_for` re-verifies through the payload
  (never trusts the instance); the archived assembly is recomputed on read-back; the ledger pair check
  refuses a re-sealed row with a decoupled pair.
- `news_flash_assemble.py` joined `SECURITY_MODULES` in the AST meta-sweep (its binding door now gates
  this surface); the sweep passes with only the sys.path-bootstrap whitelist addition.
- Error-type uniformity: `require_assembly_for`'s `ValueError` is wrapped into `RegistryError` at both
  doors.
- Honest fail-pre-fix note: most of the 14 new tests exercise the new required parameter, so they are
  not apples-to-apples pre-fix probes (the pre-fix signature TypeErrors on the new kwarg). The two
  that are: `test_record_without_assembly_is_a_typeerror` (old call shape, new behavior) and the
  v1-shape refusal (pre-fix, v1 WAS the valid shape). Test tallies: 14 new + 92 archive + full
  `ai_research_dept` **861** green; 89 pre-existing record/seal call sites across 6 test files were
  mechanically routed through a shared derivation helper (`assembly_fixtures.asm_for` — pure, so
  record and seal derive the same identity).

## Files (pin to `371349c`)

- https://raw.githubusercontent.com/henrydan111/quant-system/371349c/workspace/research/ai_research_dept/engine/news_decision.py
- https://raw.githubusercontent.com/henrydan111/quant-system/371349c/workspace/research/ai_research_dept/engine/news_archive.py
- https://raw.githubusercontent.com/henrydan111/quant-system/371349c/workspace/research/ai_research_dept/engine/news_flash_assemble.py (the binding door, reviewed SOUND in the P3b arc — context)
- https://raw.githubusercontent.com/henrydan111/quant-system/371349c/workspace/research/ai_research_dept/tests/test_news_p4a_chain_binding.py
- https://raw.githubusercontent.com/henrydan111/quant-system/371349c/workspace/research/ai_research_dept/tests/assembly_fixtures.py
- obligations + design: https://raw.githubusercontent.com/henrydan111/quant-system/371349c/workspace/research/ai_research_dept/NF_UNIT_P4_DESIGN.md

## Review questions

1. **Chain-forgery surface (in-scope class i):** with the ledger pinning `{assembly_hash, payload}` at
   first write, the seal cross-checking byte-for-byte, and read-back recomputing + re-checking on one
   snapshot — is there any path by which an archive ends up sealed or accepted whose assembly is not
   the ledger-pinned one? Consider the recovery path specifically.
2. **Mutation surface (in-scope class ii):** does either new door (`record_decision`'s binding,
   seal's post-verify binding) create a point where already-verified state can be swapped before it is
   written? The #23 timing probes pass — is there a variant they do not cover?
3. **The two deltas** — payload-embed (recovery) and bind-to-internal-copy (timing). Right calls?
4. **The anchor change** (same-snapshot tail) — any verification path where an older-but-valid anchor
   breaks an invariant?
5. **Verdict:** SOUND-TO-PROCEED (to P4b) or specific in-scope findings.
