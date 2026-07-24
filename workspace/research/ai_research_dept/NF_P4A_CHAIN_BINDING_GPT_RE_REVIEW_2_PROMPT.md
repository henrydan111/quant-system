# GPT Re-review #2 — NF integration P4a (DIFF-SCOPED) — Tier-1

Round 2 of 3. Per CLAUDE.md §10, re-reviews from round 2 are **diff-scoped**: exactly two questions —
does the fold close the invariant class it claims, and does the fix introduce new surface of its own?
(The full open sweep returns at the final pre-SHIP round.)

**Frozen threat model** (unchanged, the sending precondition):
https://raw.githubusercontent.com/henrydan111/quant-system/8479b31/workspace/research/ai_research_dept/NF_ARCHIVE_THREAT_MODEL.md
— classify findings in/out-of-scope against its criterion; scope-bounded verdict.

**Fold commit: `8479b31`** (you reviewed `371349c`). Verdict folded: **REVISE, 1 P1** — zero declines.

## Your P1, restated

> `AssemblyProvenance` is a self-consistent CLAIM, not a verifiable proof of upstream origin. A
> public-constructor assembly with the real `artifact_hash` but forged ts_code / cutoff / P2+P3a SHAs
> completed record → execute → seal → load end-to-end. First-write pinning and byte-comparison only
> guarantee "later uses equal the first-write claim" — they cannot prove the first-write claim came
> from P2/P3a. Patching SHA-format or cutoff-equality checks is not enough.

Accepted in full. You offered two fix shapes; **the user arbitrated** (per §10, fold shape = scope =
user decision) and chose your option 1 in its strongest form:

## The fold — evidence at the first-write door, proof by re-derivation

`record_decision(ledger_dir, decision_id, artifact, *, assembly, assessed_artifact, split_artifact,
source_rows)` — the three evidence params are REQUIRED, no defaults. After `verify_d7_artifact`, the
door calls the new single chokepoint
[`prove_assembly_by_rederivation`](https://raw.githubusercontent.com/henrydan111/quant-system/8479b31/workspace/research/ai_research_dept/engine/news_flash_assemble.py):
re-run `assemble_stock_artifact` from the supplied evidence under the **claimed** identity
(`assembly.cutoff_iso / ingest_class / ts_code / decision_id`) and demand **bit-equality of both
hashes** (`rebuilt_artifact.artifact_hash == artifact.artifact_hash`,
`rebuilt_assembly.assembly_hash == assembly.assembly_hash`). Deterministic re-derivation is the proof:

- forged cutoff / ingest_class → dies in `_verified_inputs`' P2/P3a identity gates;
- forged P2/P3a SHA → dies in the SHA equality / chain binding inside the re-run;
- forged ts_code → dies in derived selection (`NothingToDecide` or a different fact set → different
  `assembly_hash`);
- forged fact set / split count → different `assembly_hash`;
- a hand-built artifact (invented split text, fabricated provenance stamps) paired with real
  evidence → dies on the `artifact_hash` comparison — this closes the two residual faces I derived
  for field-level checking (same-fingerprint-prefix content substitution; forged split text), which
  is why the equality-check shape was rejected in arbitration;
- **all refusals fire before any write** — the regression suite asserts no ledger file exists after
  each refused attempt.

Downstream doors are UNCHANGED from `371349c`: seal / read-back / recovery byte-compare
`{assembly_hash, payload}` against the ledger-pinned row and **inherit** the first write's proof —
exactly the "first-write lock now guarantees the right thing" structure your P1 pointed at. Recovery
recovers the proven payload from the ledger row (your note that it would "reliably recover a wrong
first-write claim" is thereby resolved at the source: a wrong claim can no longer become a first
write).

## Regressions (your probe, pinned)

[test_news_p4a_chain_binding.py](https://raw.githubusercontent.com/henrydan111/quant-system/8479b31/workspace/research/ai_research_dept/tests/test_news_p4a_chain_binding.py)
— `test_gpt_probe_forged_provenance_refused_and_writes_nothing` is your reproduced attack verbatim
(real `artifact_hash`, `ts_code=000001.SZ`, `cutoff=1999-01-01`, arbitrary SHAs); plus a per-field
forged matrix (ts_code / cutoff / class / each SHA / split count), evidence-from-another-chain, and
the hand-built-artifact probe. All assert **no ledger row or file is produced**. 21 tests in the
file. Honest note: these exercise the new required-evidence signature, so they are not
apples-to-apples pre-fix probes — the pre-fix acceptance is your own e2e reproduction at `371349c`.

## Collateral you should check (the fix's own new surface)

1. **The chokepoint calls back into P3b.** `prove_assembly_by_rederivation` re-runs the full P3b
   assemble (which re-verifies P2/P3a, chain binding, population, recomputed content-hash text
   binding). Question: any way the re-run can be steered by the caller-supplied evidence objects
   (dict vs path forms) into proving something other than what gets recorded? Note the door returns
   the REBUILT assembly instance — the caller's instance is discarded.
2. **The engine test corpus migrated to real chains**
   ([assembly_fixtures.py](https://raw.githubusercontent.com/henrydan111/quant-system/8479b31/workspace/research/ai_research_dept/tests/assembly_fixtures.py)):
   cached text_store→P1→P2→P3a→P3b chains, variants basic/full/context_only/floor3. Semantic
   re-expressions to sanity-check: `with_penalty=False` → `floor3` (a P3a split ALWAYS carries a
   penalty-eligible `source_status` child, so an empty penalty population can only mean no ≥floor
   fact); evaluation pins 74.0→49.0 (the chain's exclusive factor population is 2 rows —
   `NFD01.fact`, `NFD02` — so `fundamental_link` is uncited and the mean drops by a third). Flag if
   either re-expression weakens what a migrated test used to prove.
3. **`require_assembly_for` demoted, not removed** — its docstring now states it is binding-only and
   serves the ledger-inheriting downstream doors. Flag any remaining call site where it is the ONLY
   gate between an unproven claim and a write.

## Verification

Full `ai_research_dept` suite **868** green (845 migrated + 21 P4a + 2 net-new elsewhere); the
timing-probe classes (#23) and the AST meta-sweep (news_flash_assemble enumerated) all pass. Your
leftover probe dir `.codex_review_p4a_371349c_probe` was removed from the working tree.

## Files (pin to `8479b31`)

- https://raw.githubusercontent.com/henrydan111/quant-system/8479b31/workspace/research/ai_research_dept/engine/news_decision.py
- https://raw.githubusercontent.com/henrydan111/quant-system/8479b31/workspace/research/ai_research_dept/engine/news_flash_assemble.py
- https://raw.githubusercontent.com/henrydan111/quant-system/8479b31/workspace/research/ai_research_dept/engine/news_archive.py (unchanged this round — context)
- https://raw.githubusercontent.com/henrydan111/quant-system/8479b31/workspace/research/ai_research_dept/tests/test_news_p4a_chain_binding.py
- https://raw.githubusercontent.com/henrydan111/quant-system/8479b31/workspace/research/ai_research_dept/tests/assembly_fixtures.py
- design + fold record: https://raw.githubusercontent.com/henrydan111/quant-system/8479b31/workspace/research/ai_research_dept/NF_UNIT_P4_DESIGN.md

## The two diff-scoped questions

1. **Does the fold close class (i)?** With proof-by-re-derivation at the sole first-write door and
   byte-inheritance everywhere downstream, is there any remaining path — record, seal, read-back, or
   recovery — by which a forged/decoupled provenance value is sealed or accepted?
2. **Does the fix create new surface?** Specifically items 1–3 above.

Verdict: SOUND-TO-PROCEED (to P4b) or specific in-scope findings.
