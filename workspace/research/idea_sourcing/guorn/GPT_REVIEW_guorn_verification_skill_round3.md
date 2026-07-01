# GPT cross-review — ROUND 3 (re-review after folding round-2 REVISE)

> Pushed branch **`report-rc-registration`** (HEAD `348131b`). Round-2 = REVISE (1 Blocker, 1 Major, 2 Minors)
> + a firm REFACTOR requirement (5 fresh-agent reps). Copy the block to GPT-5.5 Pro.

---

```text
ROLE — same as before (senior reviewer; research validity outranks code that runs; skill-craft per writing-skills).

This is RE-REVIEW #2. Your round-2 verdict was REVISE. Status below; re-fetch the live files (HARD-REFRESH —
one finding last round was a stale CDN read). Branch report-rc-registration:
- web guide:     https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/workspace/research/idea_sourcing/guorn/GUORN_WEB_FACTOR_VERIFICATION_GUIDE.md
- field mapping: https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/workspace/research/idea_sourcing/guorn/guorn_local_field_mapping.md
- comparator:    https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/workspace/scripts/guorn_factor_parity.py
- reference.md:  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/.claude/skills/guorn-verification/reference.md
- SKILL.md:      https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/.claude/skills/guorn-verification/SKILL.md
- tests:         https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/tests/workspace/test_guorn_factor_parity.py

BLOCKER (stale guide board method) — FIXED. GUORN_WEB_FACTOR_VERIFICATION_GUIDE.md §2a: the 科创板 row's LOCAL
column now reads "use the shared board_of() (jq_rep_utils.py): STAR = board_of(c)=='star'; … Do NOT build
universes from bare prefix tuples — MAIN_PREFIXES-style snapshots drift (miss 30xxxx ChiNext, e.g. 302xxx); a
legacy prefix list must be asserted == board_of() on the frozen provider first." The "MAIN_PREFIXES correctly
omit them" sentence is replaced with "locally enforce 北证/BSE exclusion with board_of(c) != 'bse', NOT a bare
prefix tuple; legacy MAIN_PREFIXES … currently miss 30xxxx ChiNext extensions such as 302xxx." grep confirms NO
remaining "prefix gate on" / "exclude from MAIN_PREFIXES" / "correctly omit" instruction; the only MAIN_PREFIXES
mentions are the drift WARNINGS.

MAJOR (mapping-ledger conflict) — NOT A REAL MISS; this was a STALE FETCH. The §1c vendor-approximate row IS
live. A raw fetch of guorn_local_field_mapping.md returns matches for "1c. Vendor-approximate", "评级机构数",
"$report_rc__n_active_orgs", "70.8%", "0.990", "Spearman 0.982". The §5 "NOT mapped" entry was corrected to
point to §1c, and I added a top-of-file pointer ("VENDOR-APPROXIMATE … mappings … live in §1c"). Please HARD-
REFRESH the raw URL and search "1c. Vendor-approximate" / "n_active_orgs". (If your tool cached the round-1
state of this file, that explains the round-2 false negative — the row landed in the round-1 commit and is at
the current HEAD.)

MINOR (coverage gate vs <5-row early return) — FIXED. report() now applies the coverage gate FIRST: for ANY row
count, cov < min_coverage prints "VERDICT: ✗ coverage gap …" and returns; a tiny export under 5 matched rows
that also passes coverage gets its OWN "VERDICT: ✗ insufficient matched rows …". No path prints metrics-then-
no-verdict. (test_low_coverage_cannot_green still green.)

MINOR (volatile calendar value in guide) — FIXED. Both guide spots now read "pick a trading day ≤ the local
provider calendar max — read it from data/reference/trade_cal.parquet or let guorn_factor_parity.py print it at
runtime (don't rely on a date shown in a historical example)." No embedded 2026-02-27 as a rule.

REFACTOR (writing-skills 5 fresh-agent GREEN reps under pressure) — DONE, 5/5 PASS. Each fresh, context-free
agent with the skill available, given a ship-today pressure scenario, RESISTED the rationalization and applied
the correct discipline:
1. "book return within 5% → ship the field" → refused; demanded per-stock comparison via the comparator (field
   can be degenerate on the book's universe).
2. "板块=全部 so include 688/689" → refused; identified 科创板 as a separate knob, classified via board_of()
   (main+chinext, drop star/bse), mask-not-row-drop.
3. "engine under-fills limit-ups, log as execution" → refused; ran selection-overlap/replay FIRST ("attribute
   with the actual number, not a plausible story").
4. "PE 3% off → file a data bug" → refused; recited lag → unit → 复权 → calendar/window → vendor → bug, bug last.
5. "0.99 corr → use 评级机构数 ≥ 10 as a hard filter" → refused; fidelity ≠ alpha + degenerate-on-universe
   coverage bias (the #18 trap).
(Plus the 2 round-context RED baselines that motivated the skill.)

TESTS: tests/workspace/test_guorn_factor_parity.py — 4 green (coverage false-green, cross-sectional refuse,
non-trading-date fail-closed, board_of-vs-snapshot drift bounded).

OUT-OF-SCOPE FOLLOW-UP (tracked separately, not part of this skill): the 302xxx drift means the EXISTING
guorn_verify_*/guorn_parity_rung* harnesses (which still use MAIN_PREFIXES) under-include 30xxxx ChiNext names;
a task chip tracks migrating them to board_of().

REVIEW ASK
1. Do the Blocker + 2 Minor fixes resolve their findings? Confirm the Major was a stale read (or quote the live
   line you believe is still missing).
2. Any NEW issue introduced (coverage-gate ordering, the <5 verdict, the guide board_of wording)?
3. Final verdict: SHIP / REVISE / REWORK + the single most important residual risk.
```
