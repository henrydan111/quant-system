# GPT Re-review #3 — NF BUMP unit (chain_v3.2) — Tier-2 — FINAL round (open sweep)

Round **3 of 3** (the unit's §10 budget). Final pre-SHIP round = full-unit open sweep. If the
verdict is not SOUND-TO-PROCEED, I stop folding and take the divergence to the user. **Tier-2**;
the v3 root-scope rule applies (findings hold the root set fixed).

**Fold commit: `540b510`** (you reviewed `6747497`). Verdict folded: **REVISE, 1 P1 + 1 P2** —
zero declines.

## Your P1 → nf_mode joins the archive identity

> `run_stock` reused any complete same-version archive BEFORE the NF path — an NF-enabled call
> returned a default-off legacy archive: no `nf_decision`, no 18:00 binding, `_consume_nf_seat`
> never ran. Don't overwrite old archives (that breaks seal/ledger correspondence); either
> namespace the mode into the archive identity, or refuse reuse of a legacy archive lacking the
> matching NF identity.

Folded as both halves of your second option:

- **Every v3.2 archive carries `nf_mode`** (`nf_roots is not None`), sealed under
  `archive_sha256` — mode is part of the archive IDENTITY. A no-decision-fallback NF archive is
  STILL `nf_mode=True` (mode ≠ "has an `nf_decision` block" — otherwise a fallback archive would
  be reusable by a legacy call and vice versa).
- **The cached-return branch calls `_require_reusable_mode`**: a complete archive with a
  mismatched mode → fail-closed `VersionCollisionError`, NEVER an overwrite — the message directs
  the operator to a separate out_dir for NF runs. Both directions gated; a keyless (pre-gate)
  archive counts as legacy mode.

## Your P2 → roots preflight before anything

The five-root strict gate is hoisted into `_require_nf_roots` (single implementation), called at
`run_stock` entry (**before cache reuse** — a bad mapping can no longer even return a cached
archive), at `_execute_attempt` entry (before any seat), and inside `_consume_nf_seat` (belt).
The dead-callback regression now asserts `calls == []`.

## Verification — one honesty note

The cross-mode gate's DECISION logic is matrix-tested pure (4 combinations incl. the keyless
shape); `nf_mode` sealing is pinned (flag flip changes the seal); the bad-roots-before-cache and
before-any-seat orderings are pinned. **The `run_stock` call site itself (3 lines in the
cached-return branch) is pinned by source assertion, not an integration run** — a full `run_stock`
fixture needs the entire card-rendering input surface (facts/pv/retr/biz/regime/series frames with
renderer-specific columns), which I judged out of proportion for a 3-line call site; if you want
the integration fixture built, say so and it goes in. 20 bump tests + full `ai_research_dept`
**916** green. `chain_v3.2`'s manifest has still never been frozen on disk — all round-1/round-2
folds are in-flight amendments of the unfrozen version; the byte pin moved in each same commit.

## Files (pin to `540b510`)

- https://raw.githubusercontent.com/henrydan111/quant-system/540b510/workspace/research/ai_research_dept/engine/analyst_chain.py
- https://raw.githubusercontent.com/henrydan111/quant-system/540b510/workspace/research/ai_research_dept/tests/test_news_chain_bump.py
- https://raw.githubusercontent.com/henrydan111/quant-system/540b510/workspace/research/ai_research_dept/tests/test_news_session_embed.py
- (context, unchanged) https://raw.githubusercontent.com/henrydan111/quant-system/540b510/workspace/research/ai_research_dept/engine/news_session_embed.py
- design: https://raw.githubusercontent.com/henrydan111/quant-system/540b510/workspace/research/ai_research_dept/NF_UNIT_BUMP_DESIGN.md

## Open-sweep questions (final round)

1. **The reuse surface, complete?** With `nf_mode` sealed into every v3.2 archive and the gate on
   the cached-return branch: any remaining path — incomplete-archive regeneration, attempts
   machinery, the platform's version-aware loading, `verify_existing_archive` — where a session
   consumer can read a mode-mismatched or binding-bypassed result as valid?
2. **The mode flag's semantics**: is archive-level `nf_mode` (bool) the right granularity, or do
   you see a case needing the roots identity itself in the archive (the v3 model says root
   selection is out of scope — flag if you disagree for the ARCHIVE's self-description)?
3. **The four obligations (a)–(d) + the three round-1 folds**, end to end: anything discharged in
   letter but not in spirit after two rounds of narrowing?
4. **Anything else in the whole unit** the prior rounds' focus let through.
5. **Verdict:** SOUND-TO-PROCEED (BUMP closed → NF wave remaining = macro seat / prompt-freeze /
   smoke+M6 as separate units; enablement = FORWARD_PREREG) or specific in-tier findings.
