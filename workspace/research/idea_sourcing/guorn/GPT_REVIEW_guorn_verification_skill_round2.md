# GPT cross-review — ROUND 2 (re-review after folding round-1 REVISE)

> Pushed branch **`report-rc-registration`** (HEAD `aac0474`) — all raw links below now resolve to the fixed
> files. Round-1 verdict was **REVISE** (2 Blockers, 6 Majors, 2 Minors). Copy the block to GPT-5.5 Pro.

---

```text
ROLE — same as round 1 (senior reviewer; research validity outranks code that runs; skill-craft per writing-skills).

This is a RE-REVIEW. Your round-1 verdict was REVISE. I folded every finding; confirm each fix resolves the
issue, then give a fresh verdict. Re-fetch the live files to verify (branch report-rc-registration):
- comparator:      https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/workspace/scripts/guorn_factor_parity.py
- SKILL.md:        https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/.claude/skills/guorn-verification/SKILL.md
- reference.md:    https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/.claude/skills/guorn-verification/reference.md
- web guide:       https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/workspace/research/idea_sourcing/guorn/GUORN_WEB_FACTOR_VERIFICATION_GUIDE.md
- field mapping:   https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/workspace/research/idea_sourcing/guorn/guorn_local_field_mapping.md
- tests:           https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/tests/workspace/test_guorn_factor_parity.py

WHAT CHANGED PER FINDING (verify against the files):

BLOCKER 1 (coverage can return green) — FIXED. `report()` now takes `min_coverage` (CLI `--min-coverage`,
default 0.98); after printing metrics, `if cov < min_coverage` the verdict is FORCED to "✗ coverage gap" and
no ✅ is printed (metrics still shown for diagnosis: a high matched-subset score with low coverage localizes a
join/universe break). Locked by test_low_coverage_cannot_green (50% cov + exact-on-matched → coverage gap, no ✅;
100% cov exact → ✅). VERIFIED live: default 0.98 on the 评级机构数 run (92% cov) → "✗ coverage gap".

BLOCKER 2 (cross-sectional on subset) — FIXED + clarified. `assert_pointwise(expr)` refuses tokens
CROSS_SECTIONAL_TOKENS=("cs_","csrank","havg","hneutralize","neutralize","grouped by") with a redirect to the
综合级 harness; both docs now say POINTWISE-only. CLARIFICATION for your round-1 token list: qlib's expression
engine is per-instrument time-series (Ref/Mean/Corr/Rank-over-window…) — a VALID --local-expr is inherently
pointwise, so I did NOT guard `Rank(`/`Quantile(` (those are time-series-safe; guarding them would falsely
refuse legitimate exprs). The guard catches the genuinely cross-sectional helpers (cs_/HAVG/neutralize), which
would otherwise error cryptically in D.features. Locked by test_cross_sectional_expr_refuses_subset_fetch.

MAJOR 1 (hard-coded 0.2% cost) — FIXED. reference.md 策略级 step 4 now: "Read the book's cost from
deployed_20_trade_models.md — do NOT hard-code it. The recipes record 单边千分之二或千分之五 = 0.2% OR 0.5%/side
→ run BOTH as a sensitivity and label the chosen cost (a wrong cost can flip a replay gap between selection and
execution)." (Verified the source string in deployed_20_trade_models.md.)

MAJOR 2 (count "reproduces" too strong) — FIXED. Count verdict now: "✅ same-vendor count-exact" (exact≥95% AND
|frac>0 breadth diff|≤0.01) vs "◑ vendor-approx rank-faithful — ranking/composite use ONLY; NOT threshold/
value-exact" (corr≥0.95 AND breadth diff≤0.03) vs ◑ partial vs ✗. Docs mirror it. VERIFIED live: 评级机构数 (with
--min-coverage 0.90) → "◑ vendor-approx rank-faithful", no longer a blanket ✅.

MAJOR 3 (mapping-doc conflict) — FIXED. guorn_local_field_mapping.md: added §1c "Vendor-approximate (rank-
faithful — RANKING-USE ONLY)" with the 评级机构数 → $report_rc__n_active_orgs row (exact 70.8% / corr-nonzero
0.990 / Spearman 0.982); the §5 "NOT mapped/irreducible" entry was corrected (评级机构数 removed from it, points
to §1c). reference.md index now says the ledger is canonical for penny/structure-exact, vendor-approximate
flagged ranking-only.

MAJOR 4 (replay overstates) — FIXED. SKILL.md + reference.md: "feed 果仁's exact held names (+ closest weights/
cost/fill); names-only replay does NOT fully isolate selection (weights/cost/fill/CA unverified) → replay ≈ 果仁
⇒ selection is the DOMINANT residual (never 'IS selection'); replay gap ⇒ execution path unlocalized."

MAJOR 5 (residual order omits calendar) — FIXED. Order is now lag → unit → 复权 → calendar/suspension/window-
membership → vendor → bug (SKILL.md, reference.md, web guide), citing the proven 250日涨幅 / 乖离率 window-
membership residuals.

MAJOR 6 (MAIN_PREFIXES as 2nd classifier) — FIXED, and your concern was EMPIRICALLY CONFIRMED. reference.md now
makes board_of() (jq_rep_utils.py) the canonical classifier; the prefix tuples are a snapshot that must be
asserted-equal to board_of() before use. test_board_of_is_canonical_and_prefix_drift_is_bounded FOUND a real
drift on the frozen provider — 302132_SZ (ChiNext) is classified chinext by board_of but MISSED by the 300/301
prefix snapshot. The test locks board_of as canonical and bounds the drift to ChiNext 30xxxx; a separate task
chip tracks migrating the existing harnesses off MAIN_PREFIXES to board_of().

MINOR 1 (frozen date pinned) — FIXED. The comparator reads the calendar max from data/reference/trade_cal.parquet
at runtime and prints it (no pinned 2026-02-27 in help); the guide cites "the local provider calendar max
(currently 2026-02-27; read from trade_cal.parquet)". MINOR 2 (non-trading date) — FIXED. validate_trading_date()
fails closed on a non-trading day or a date > calendar max (no silent searchsorted fallback). Locked by
test_non_trading_date_fails_closed.

PROOF: tests/workspace/test_guorn_factor_parity.py — 4 tests, all green (the 3 you asked for + the board-drift
check). The 4th (frozen-provider board_of vs snapshot) is the one you specified and it caught 302132_SZ.

STILL OUTSTANDING (disclosed): the writing-skills REFACTOR asks for 5 fresh-agent GREEN reps under pressure; I
have run 1 (on the pre-fix skill) and the 2 round-context RED reps. Tell me whether you want the 5 reps to GATE
SHIP, or accept them as a documented follow-up given the code-level guards + tests now exist.

REVIEW ASK
1. Does each fix above resolve its finding? Quote any that you judge incomplete.
2. Any NEW issue introduced by the changes (e.g. the coverage-gate default 0.98 too strict/lax; the count-tier
   breadth thresholds; the board_of test bounding logic)?
3. Verdict: SHIP / REVISE / REWORK + the single most important residual risk. If SHIP-conditional-on-the-5-reps,
   say so explicitly.
```
