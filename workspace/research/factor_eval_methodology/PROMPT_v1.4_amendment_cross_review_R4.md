# GPT 5.5 Pro cross-review prompt — v1.4 amendment, ROUND 4 (confirmation after round-3 wording fixes)

> Round-3 verdict: REVISE — N1/N3 RESOLVED; N2 substantively fixed but PARTIAL on stale wording
> (R3-M1, R3-M2, R3-m1). All four wording fixes applied verbatim in revision 4; no normative content
> changed. You stated: "After correcting the stale `book_plan_hash` / 'plan-hash counting' wording
> above, I do not see another guardrail that remains merely implicit." This round is the
> confirmation pass. Branch `calendar-unfreeze` is pushed.

```text
ROLE
You are a senior reviewer for an A-share quantitative research system. This is ROUND 4 — a confirmation pass. In round 3 you found N1/N3 RESOLVED and N2 PARTIAL solely on stale wording (A2 heading said book_plan_hash; A6 thresholds said "book plans"; two summary lines said "plan-hash counting"), and you stated that after those corrections no guardrail remains merely implicit. Revision 4 applies your three replacement texts verbatim and changes nothing else. Verify the four fixes and issue the final verdict.

REPO
https://github.com/henrydan111/quant-system   (branch: calendar-unfreeze)
The revised amendment (revision 4):
https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/factor_eval_methodology/FACTOR_EVAL_V1.4_AMENDMENT_book_level_promotion.md

SELF-REVIEW PREFLIGHT: verdict "clean for GPT round-4 (confirmation)"; the four fixes applied verbatim (A2 heading → book_seal_key; A6 → "warn at 3 / hard stop at 5 distinct book_seal_key spends per OOS window, book_plan_hash for disclosure grouping only"; §7 Q5 + §8 principle-9 summaries → book_seal_key spend counting); grep sweep confirms the only remaining "book plans"/"plan-hash counting" strings are the §9 disposition rows quoting the historical defects. No normative content changed in revision 4.

THE FOUR FIXES (verify against the raw link — the committed file is authoritative):
1. A2 heading now reads: "A2. One seal per book, keyed by `book_seal_key`; the spend reports two layers."
2. A6 threshold sentence now reads: "Default budget for virgin windows: warn at 3 distinct `book_seal_key` spends per OOS window, hard stop at 5 distinct `book_seal_key` spends per OOS window, with `book_plan_hash` used only for disclosure grouping, unless a user-signed multiplicity override is recorded before the spend and the artifact reports adjusted max-stat/FDR/DSR/PSR where applicable."
3. §7 Q5 resolution now reads: "virgin windows get `book_seal_key` spend counting, grouped by `book_plan_hash` only for disclosure, with warn 3 / hard 5 + recipe-family and A5-overlap accounting (M3 adopted, unit per round-2 N2)."
4. §8 principle 9 now reads: "Multiple testing: materially strengthened — `book_seal_key` spend counting grouped by `book_plan_hash` for disclosure, virgin-window warn-3/hard-5, A5 spends folded into the same budget."
Plus: status header updated to revision 4; §9 gains the round-3 disposition table; §8 gains the revision-4 self-review note. Nothing else changed (diff-verifiable via the two most recent commits on the branch).

REVIEW QUESTIONS
1. Confirm each of the four fixes matches your round-3 replacement text (per-fix: CONFIRMED / MISMATCH with quote).
2. Confirm N2 is now fully RESOLVED and no stale seal-key/unit wording remains outside the §9 historical rows.
3. Final verdict: SHIP / REVISE / REWORK, plus the single most important residual risk to carry into implementation pass 1.

OUTPUT FORMAT
- Four-line fix-verification table.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk.
```
