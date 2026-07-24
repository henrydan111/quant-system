# GPT Re-review #4 — NF integration C1 — CONFIRMATION round (user-arbitrated folds)

Round 3 hit the §10 budget with 2 mechanical P2s (no new P1; both round-1 P1s you confirmed
closed); per protocol the residue went to **user arbitration**, who chose: fold both + this
confirmation round. Scope: exactly the two fold diffs. NOT a fresh open sweep. **Tier-2**; v3
root-scope rule.

**Fold commit: `12917ee`** (you reviewed `c4c0d7f`).

## P2-1 → the old Unit-2 spec is now HISTORICAL

[NF_UNIT2_SESSION_EMBEDDING_DESIGN.md](https://raw.githubusercontent.com/henrydan111/quant-system/12917ee/workspace/research/ai_research_dept/NF_UNIT2_SESSION_EMBEDDING_DESIGN.md)'s
header now reads **HISTORICAL — SUPERSEDED 2026-07-24; do not implement from this document**, with
the two-correction history (premise falsified 2026-07-22; the §1 wiring scope moved out by your
round-1 P1#1), explicit pointers to [NF_UNIT_C1_DESIGN.md](https://raw.githubusercontent.com/henrydan111/quant-system/12917ee/workspace/research/ai_research_dept/NF_UNIT_C1_DESIGN.md)
as THE C1 contract and to the FROZEN WIRING OBLIGATIONS as the bump unit's spec, and the statement
that its seven invariants carry over as inherited requirements — "nothing below this line is a
current work order". NF_UNIT_C1_DESIGN's header claims contract authority explicitly (your exact
complaint: it previously *deferred* to the stale doc).

## P2-2 → the byte pin is now the LF-canonical content hash

The test normalizes `CRLF → LF` before hashing and pins
`12b1a3244c2e8c4a01af3800705c9bd9542b7fddc0ca83d7a5bc48c5498b3bac` — computed locally from the
worktree bytes after normalization and cross-checked against your reported canonical value (not
copied). Same unedited source now hashes identically on a CRLF Windows checkout and an LF
`ubuntu-latest` checkout; any real edit still fails on every platform. `analyst_chain.py`'s
checkout EOL policy is deliberately untouched (your own caveat: changing it would alter the live
v3.1 runtime manifest).

Plus your minor hardening: the scalar success case now also asserts `opaque_external is True`.

## Verification

12 C1 tests + full `ai_research_dept` **896** green.

## Files (pin to `12917ee`)

- https://raw.githubusercontent.com/henrydan111/quant-system/12917ee/workspace/research/ai_research_dept/tests/test_news_session_embed.py
- https://raw.githubusercontent.com/henrydan111/quant-system/12917ee/workspace/research/ai_research_dept/NF_UNIT2_SESSION_EMBEDDING_DESIGN.md
- https://raw.githubusercontent.com/henrydan111/quant-system/12917ee/workspace/research/ai_research_dept/NF_UNIT_C1_DESIGN.md
- (unchanged this round) https://raw.githubusercontent.com/henrydan111/quant-system/12917ee/workspace/research/ai_research_dept/engine/news_session_embed.py

## Confirmation questions

1. **P2-1:** does the supersession header eliminate the contradiction — is there any remaining
   place a future session could read the old §1 scope as a current work order?
2. **P2-2:** is the LF-normalized pin correct and portable (and is `replace(b"\r\n", b"\n")` the
   right normalization for this file — no lone-`\r` edge you can see in the frozen blob)?
3. **Verdict:** SOUND-TO-PROCEED — C1 closed as the consumption unit; the NF wave's remaining work
   = the final-integration chain-version-bump unit discharging the frozen wiring obligations — or
   a specific residual gap.
