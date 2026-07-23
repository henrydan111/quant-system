# GPT Re-review #2 — NF integration P3b (DIFF-SCOPED) — Tier-2

Round 2 of 3. Per CLAUDE.md §10, re-reviews from round 2 are **diff-scoped**: exactly two questions —
does the fold close the invariant class it claims, and does the fix introduce new surface of its own?
(A full open sweep happens only at round 1 and the final pre-SHIP round.) **Tier stays Tier-2** —
crafted-object / subclass / dunder analysis is out of tier; raise a tier change as a recommendation to
the user, not as a finding.

**Fold commit: `4caf4a2`** (reviewed at `c591629`). Verdict folded: **REVISE, 1 P1** — zero declines.

## Your P1, restated

> P3b returned a plain provenance dict, but `record_decision` / the executors /
> `seal_decision_archive` all take only a `D7DecisionArtifact`. `provenance` had nowhere to go, so the
> sealed archive proves the D7 artifact but not which P2/P3a inputs, which stock, or which facts
> produced it. "P4 binds all of it" was false as built.

Accepted in full. Your suggested fix has a **P3b half** and a **P4 half**; I did the P3b half now and
**froze the P4 half in writing** as a precondition of the P4 unit. That split is put to you below.

## The fold — P3b half (done)

`AssemblyProvenance`, a frozen dataclass:

- hash body = `{schema, artifact_hash, ts_code, decision_id, cutoff, ingest_class, assessed_sha,
  split_sha, selected_facts, n_splits_used}`; **`artifact_hash` is inside it**, so the provenance and
  the artifact bind each other.
- `assembly_hash` recomputed in `__post_init__` (a claimed-but-wrong value = hard fail), same pattern
  as the existing `ClusterSnapshot`.
- every field gated to an exact base type (`type(x) is str` / `is int`; the int gate also rejects
  `bool`, since `type(True) is bool`); empty `selected_facts` refused (invariant 7 again at the
  identity layer).
- `verify_assembly_provenance(payload)` — strict top-level key set (extra/missing = refuse), schema
  value check, `selected_facts` must be an exact `list`, then full recompute. Recompute-not-trust.
- **`require_assembly_for(assembly, artifact)`** — the single binding door P4 must call. Refuses a
  non-`AssemblyProvenance` (a look-alike dict included), re-verifies through the payload rather than
  trusting the instance's claimed hash, and refuses a mismatched `artifact_hash` or `decision_id`.
- rejection-path `str(...)` diagnostics swapped for `safe_repr` (the class the sealing surface's AST
  meta-test bans).

`assemble_stock_artifact` now returns `(D7DecisionArtifact, AssemblyProvenance)`.

## The P4 half — FROZEN, not dropped

Recorded **verbatim in both** the [P3b design doc](NF_UNIT_P3B_DESIGN.md) and the
[news_flash_assemble.py](engine/news_flash_assemble.py) module docstring, so it cannot be lost between
units. P4 MUST: (a) **require** the provenance — no default, no `None` path; (b) call
`require_assembly_for`; (c) write `assembly_hash` into the decision ledger entry; (d) embed
`assembly.payload` in the sealed archive under a bumped `_ARCHIVE_SCHEMA` **v1 → v2** (extending the
strict key set), re-verified on read-back; (e) ship refusal tests — missing provenance, artifact-hash
mismatch, and an archive round-trip proving the chain survives (a v1-shaped archive must not verify).

**Why deferred to P4 rather than folded here** (please rule on this explicitly):

1. §10 "one review unit per review" — the audit found the 4-module bundle diverged (3B→3B→4B) while
   single-unit arcs closed in 3. Folding (c)+(d) means editing `news_decision.py` **and**
   `news_archive.py` in a unit whose subject is `news_flash_assemble.py`.
2. `news_archive.py` is the module that took a **28-round** arc and is **Tier-1** by the §10 tiering
   rule (sealed-archive commitment). Its schema bump belongs with the P4 execution wiring it serves,
   reviewed at its own tier — not as a rider on a Tier-2 assembly unit.
3. P4 is the immediately next unit; the chain closes within one unit's time, and its review will open
   against a written, frozen obligation rather than an open-ended ask.

If you judge that P3b cannot be signed off with the consumer half outstanding, say so plainly and I
will fold (a)–(e) into this unit instead — but note that **re-scoping a unit is a user decision**, so
that would go to the user, not be decided in-round.

## Honest verification notes

- The invariant-8 tests exercise a **new API**; they are not apples-to-apples fail-pre-fix probes
  (`require_assembly_for` / `verify_assembly_provenance` did not exist pre-fix). What they do prove:
  a provenance minted for artifact A is refused against artifact B; a tampered payload with a stale
  hash is refused; a wrong key set / wrong schema is refused; a plain dict does not satisfy the door;
  changing the consumed P2 SHA changes the identity; the identity round-trips through `payload`.
- Tests: **22** P3b (6 new) + full `ai_research_dept` **837** green. Your sandbox could not create
  pytest tmpdirs (`WinError 5`) — these ran locally on the real tree.

## Files (pin to `4caf4a2`)

- https://raw.githubusercontent.com/henrydan111/quant-system/4caf4a2/workspace/research/ai_research_dept/engine/news_flash_assemble.py
- https://raw.githubusercontent.com/henrydan111/quant-system/4caf4a2/workspace/research/ai_research_dept/tests/test_news_flash_assemble.py
- https://raw.githubusercontent.com/henrydan111/quant-system/4caf4a2/workspace/research/ai_research_dept/NF_UNIT_P3B_DESIGN.md
- P4 targets (context only, unchanged): [news_decision.py](https://raw.githubusercontent.com/henrydan111/quant-system/4caf4a2/workspace/research/ai_research_dept/engine/news_decision.py) · [news_archive.py](https://raw.githubusercontent.com/henrydan111/quant-system/4caf4a2/workspace/research/ai_research_dept/engine/news_archive.py)

## The two diff-scoped questions

1. **Does the fold close the class?** Is `AssemblyProvenance` + `require_assembly_for` a sufficient
   P3b-side answer — i.e. once P4 honours the frozen obligation, is the chain provable end to end from
   a sealed archive alone? Anything in the hash body that should be there and isn't (or is there and
   shouldn't be)?
2. **Does the fix create new surface?** Specifically: the strict key set / schema-value gate in
   `verify_assembly_provenance`; the double-verification in `require_assembly_for` (payload rebuild
   rather than trusting the instance); the `ASSEMBLY_SCHEMA` content-contract versioning rule; and the
   `n_splits_used` int gate.

Plus: **rule on the P3b/P4 split** above. Verdict: SOUND-TO-PROCEED (to P4, with the obligation
frozen) or a specific in-tier gap.
