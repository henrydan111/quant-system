# GPT Re-review #2 — NF integration C1 (DIFF-SCOPED) — Tier-2

Round 2 of 3. Per CLAUDE.md §10, diff-scoped: does the fold close what it claims, and does it
introduce new surface? **Tier stays Tier-2**; v3 root-scope rule applies.

**Fold commit: `59a7f18`** (you reviewed `6a95a62`). Verdict folded: **REVISE, 2 P1** — zero
declines. Net effect: **the unit SHRINKS** — C1 is now the consumption module only.

## Your two P1s → the fold

1. **Default-OFF still changed the frozen v3.1 contract** (the manifest hashes
   `analyst_chain.py`'s bytes into `engine_contract_sha256`; you measured the collision:
   `c0e45d49… → f8818ea1…`). Folded per your minimal fix: **`analyst_chain.py` reverted to the
   exact frozen v3.1 bytes** (git checkout of the parent state — please re-hash to confirm it now
   matches `c0e45d49…`). The wiring (hook parameter, news-seat branch, `nf_decision` block) is
   DEFERRED to the formal chain-version bump. A mechanical guard test
   (`test_analyst_chain_is_untouched_before_the_version_bump`) asserts the file contains no trace
   (`nf_news` / `nf_decision` / `news_session_embed`) until then.
2. **The legacy judge zeroed the opaque sealed score** (`news.final=49.0` →
   `news.adj_final=0.0` in a publishable archive, no bear refutation). Folded as **declared
   semantics + frozen obligation**: the consumed seat (scalar AND vector_only) now carries
   `opaque_scalar=True` — the anchor for wiring obligation (b): *the judge must set
   `adj_final == final` for an opaque seat absent an NF-native discount contract; an
   empty-legacy-lists recompute that zeroes the sealed score is forbidden; a hook-on regression
   pinning `news.adj_final == news.final` under no bear refutations ships with the bump.* Your
   third note (production cutoff binding: full timestamp, never a bare date) is frozen as
   obligation (c).

The obligations live verbatim in BOTH the module docstring
([news_session_embed.py](https://raw.githubusercontent.com/henrydan111/quant-system/59a7f18/workspace/research/ai_research_dept/engine/news_session_embed.py))
and the design doc
([NF_UNIT_C1_DESIGN.md](https://raw.githubusercontent.com/henrydan111/quant-system/59a7f18/workspace/research/ai_research_dept/NF_UNIT_C1_DESIGN.md))
— the same cross-unit freeze pattern that carried P3b→P4a (where you verified the obligations were
discharged, not lost).

## Why "defer" rather than "fix the judge now"

Your P1#2 offered two shapes (define opaque semantics now, or make the path unpublishable until
then). The judge lives in the scoring contract territory that the Unit-2 spec §2 explicitly
excludes from C1 (`scorecard.py` change + scoring contract + chain bump = one separate unit); with
P1#1 forcing the analyst_chain wiring out of C1 anyway, there is NO in-repo path that reaches the
judge with an opaque seat until that unit lands — the flag + frozen obligation make the semantics
unambiguous for it. If you judge that C1 cannot close with (b) as an obligation rather than code,
say so — that becomes a unit-boundary question for the user, per §10.

## What did NOT change

`consume_news_decision`'s matrix (routed+success / vector_only / no_decision / missing /
hard_failed / tampered), the identity block, the falsifier mapping, the AST single-door guard —
all as you verified them in round 1.

## Verification

`analyst_chain.py` byte-reverted (the working tree file is the parent commit's exact blob). Tests:
**12** C1 (the analyst_chain-signature test replaced by the untouched-guard; + the opaque_scalar
declaration test) + full `ai_research_dept` **896** green.

## Files (pin to `59a7f18`)

- https://raw.githubusercontent.com/henrydan111/quant-system/59a7f18/workspace/research/ai_research_dept/engine/news_session_embed.py
- https://raw.githubusercontent.com/henrydan111/quant-system/59a7f18/workspace/research/ai_research_dept/engine/analyst_chain.py (assert: byte-identical to the pre-C1 frozen v3.1)
- https://raw.githubusercontent.com/henrydan111/quant-system/59a7f18/workspace/research/ai_research_dept/tests/test_news_session_embed.py

## The two diff-scoped questions

1. **Does the fold close both P1s?** — P1#1: re-hash `analyst_chain.py` at `59a7f18` against the
   pre-C1 contract hash; is the guard test a sufficient mechanical hold until the bump? P1#2: is
   `opaque_scalar=True` + frozen obligation (b) the right anchor, or must the judge semantics land
   in code before C1 can close?
2. **Does the fix create new surface?** — the shrunken unit's boundary (consumption module with no
   session wiring at all): anything the consumption module now promises that nothing enforces?

Verdict: SOUND-TO-PROCEED (C1 closed as the consumption unit; wiring obligations frozen for the
final-integration bump) or specific in-tier findings.
