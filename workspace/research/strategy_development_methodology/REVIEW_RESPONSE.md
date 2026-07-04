# GPT 5.5 Pro cross-review R1 — response & disposition (2026-07-04)

**Verdict received: REVISE (not load-bearing yet).** The reviewer confirmed the spine is directionally
right and raised 8 blocking issues, 6 claim-downgrades, and 6 non-blocking edits. **All folded; none
declined.** Two of the blocking issues (the sealed-OOS-as-selector bug and the stale-citation honesty
problem) were genuine misses in my own self-review — recorded as a lesson.

## Blocking issues (all fixed)

| # | Issue | Fix | Where |
|---|---|---|---|
| 1 | §S3/App-B used the **sealed OOS as an optimizer-selection gate** (model selection on the test set) | Condition 4 now reads "beats light construction on IS / walk-forward / **pre-seal** folds"; explicit rule that selecting on OOS spends the seal | §S3 cond 4, App B, invariant 11 |
| 2 | §1.1/§S6 cited **stale E-wave / eps_diffusion deployment magnitudes** as live (superseded by the fill-price-aware gate, CLAUDE.md §3.5) | Marked STALE (must-rerun) throughout; only the qualitative pattern retained; added to §7.3 anti-patterns | §1.1, §S6 |
| 3 | §S3 construction **not explicitly long-only / gross-constrained** (`w∝α` can go negative/levered) | Added `wᵢ≥0`, `Σw≤1 + cash`, no shorts, lot/min-order rounding, FAIL-CLOSED to the default box | §S3 box, invariant 14 |
| 4 | §S7 parity only covered **equal-weight core**, not the actual weighted book | Split into core parity (vs 果仁) + **actual-book execution parity** (weights/orders/lots/fills/timing via the event-driven engine) | §S7 |
| 5 | §S1 microcap shell/junk filters **not explicitly PIT** | Every exclusion field must be visible-as-of the decision (as-of source + lag), hashed into the TUD | §S1, invariant 14 |
| 6 | Part V lacked a **portfolio-level sealed test** | Added `portfolio_seal_key` + effective-N + one spend for the meta-allocation layer | §5.6, invariant 12 |
| 7 | §S5 PBO/CSCV not **temporal / purged / autocorrelation-aware** | Temporal row-blocks + purge/embargo + non-overlapping/HAC/block-bootstrap SEs; + mandatory trial ledger | §S5, App A |
| 8 | §S8 said capacity is "informational, not a gate" for <2M — unsafe | Split: institutional ceiling informational; **actual-capital ¥2M capacity is a HARD gate** | §S8, invariant 8 |

## Claim downgrades (all applied)

- "TC is near the floor" → **not yet measured** (strong prior, not a measurement) — §1.1.
- "top-K/EW is close to minimum-TC possible" → "among the lowest-TC constructions" — §1.1.
- "every past failure was exactly one of three leaks" → "past failures … typically" — §1.1/§1.2.
- "#9 vindicates" → "**corroborates**" the light-construction default — §S3.
- "VQ10 best deployable to date" → "best historical local **benchmark**, not re-validated through S6/S7" — §1.5, App D.
- "50%+ CAGR infeasible … confirmed exhaustively" → "**looks infeasible on the evidence to date** — a strong prior, not a proven theorem" — App D.
- microcap "10–18% upper bound" → **unverified hypothesis** (shell magnitude refuted) — §1.3, App D.
- "divergence localizes a local bug" → "localizes a **mismatch** (local bug / 果仁 assumption / translation / legitimate model difference)" — §S7.
- ML "~+3%/yr reliably helps" → "**testable candidate improvement**; the figure is US-equity, not a guaranteed A-share microcap increment" — §S2.

## Non-blocking edits (applied)

- **North-star reframed** (reviewer's + self-review caveat #4): "**one robust, parity-verified book + one controlled microcap-lane hypothesis test**"; the diversified portfolio is a **later phase**, not the organizing goal (the `1/√ρ` ≈ 1.1–1.4× ceiling makes its lift modest) — §1.5, §5.7.
- **§S2 exclusion → book-context admission test** (turnover-conditioned; fast factors admitted iff their after-cost edge survives on the tradeable set, not banned by name) — §S2.
- **Quality ratio defined operationally** (effective rank of the name-correlation matrix over the rebalance-horizon window) — App B.
- **All construction "OOS" language → pre-seal validation folds** — §S3, App B, invariant 11.
- **Trial-ledger requirement** (count/cluster every recipe/variant/fork/sweep/seed/parity-attempt into effective-N) — §S5.
- **MLflow mandatory** for substantive strategy-level runs — invariant 13.

## Deferred to BUILD-time (noted, not a doc change)

- Reviewer suggested moving **capacity from P2→P1** in the build roadmap (actual-capital gating) and keeping risk-model v1 at P1 for reporting/neutralization/attribution. Captured here; the roadmap table (Part VI) will absorb it when BUILD sequencing is finalized — the invariant (#8, capacity = hard gate) is already load-bearing.

## Lesson recorded

Two blocking issues (OOS-as-selector; stale citations) should have been caught in the author self-review.
Added to memory: a self-review must (a) trace every "OOS" reference to confirm it is a diagnostic, not a
selector, and (b) cross-check every cited empirical number against CLAUDE.md §3 staleness flags.

**Status:** all R1 findings folded → the doc is ready for a GPT re-review.
