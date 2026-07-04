# Self-review — STRATEGY_DEVELOPMENT_METHODOLOGY v1.0 (§10, 2026-07-04)

Structured self-review completed before the GPT 5.5 Pro cross-review, per CLAUDE.md §10. Scope: the v1.0
methodology doc + the two-pass deep-research adjudication + the machinery audit, as consolidated 2026-07-04.

## §3 hard-invariants check (does the methodology respect each?)

- **PIT / no-lookahead (§3.2):** RESPECTED + reinforced. Universe declared before diagnostics (§S1); α
  calibrated IS-only (§S2b); sealed single-shot strategy OOS (§S6); improvement is IS-only, OOS spent once
  (§4.1). Defers factor-level PIT to factor-eval v1.4. No new PIT surface introduced.
- **Sealed-OOS / `book_seal_key` (§3.4, v1.4):** RESPECTED. The book is the single-shot OOS unit; A8 block
  on virgin windows before the strategy-registry path exists is carried (§S6).
- **Fill-price-aware limits / T+1 / total-return (§3.3):** RESPECTED (reused as-is, §S4); no change to the
  engine's cost/limit contracts.
- **Field-status / registries / module boundaries (§3.4):** RESPECTED. `strategy_registry` is the book
  home; `portfolio_risk` stays dormant until BUILD-4; no formal-path import of dormant symbols proposed.
- **Unlevered gross ≤ 1× (§7.11):** RESPECTED and load-bearing throughout (Part V; no MN claim at <2M).
- **Verdict:** no §3 invariant is weakened; several are extended to the strategy level.

## §7 quantitative-research principles check

- No lookahead ✓ · temporal splits only ✓ · OOS sacred (§4.1, §S6) ✓ · factor-eval standard (references
  v1.4) ✓ · survivorship (delist-aware universe inherited) ✓ · centralized metrics (`result_analysis`) ✓ ·
  **no hedge words (§7.10)** ✓ (claims are marked verified / unverified explicitly; the microcap 10-18% is
  labelled an unverified hypothesis) · **no leverage (§7.11)** ✓.
- **Gap found + noted (not yet fixed):** MLflow logging (§7.6) is not called out as mandatory for the
  strategy-level runs — should be added in the consolidation-with-GPT pass. Minor.

## Issues found and fixed during this self-review

1. The lever ranking was inverted from the draft's "construction-first" to the evidence's "selection ≫
   cost > universe > weighting" — now consistent across §1.2, §2.2, §4.5, §S2-S3, and the adjudication.
2. The microcap 10-18% CAGR was softened from "target" → "upper bound" → (after 3-vote verification) an
   explicit **unverified hypothesis** (§1.3). Consistent everywhere.
3. The decorrelation ambition was quantified honestly (`1/√ρ` ceiling, §5.1) so §5.7's "Sharpe ~1.2-1.4"
   reads as a ceiling, not a promise.

## Residual open items / caveats disclosed to GPT (these are DISCLOSED, not defects)

1. **Claims 6 (ML) and 7 (parity) are NOT 3-vote-verified** (the second research pass hit the session
   usage limit mid-run). They rest on primary sources + the earlier ML thread — weight accordingly.
2. **The #9 optimizer-failed verdict is first-cut** (pragmatic Ledoit-Wolf Σ, not the full factor model;
   the parallel session is iterating). The light-construction-default conclusion is independently supported
   by DGU/Platanakis, so it is robust even if #9's specific numbers move — but the empirical claim is
   provisional.
3. **The whole microcap deployment lane is a hypothesis**, not an established edge — 83% of A-share
   anomalies don't replicate and the shell premium is decaying; the lane must be proven by a sealed
   strategy-level OOS, not assumed.
4. **Strategic tension for GPT to weigh:** the verified decorrelation ceiling (`1/√ρ` ≈ 1.1-1.4× at ρ
   0.52-0.79) makes the "diversified portfolio of books" north-star deliver only a *modest* Sharpe lift
   over a single strong book. Is the multi-book build (PR/BUILD-6) worth its cost at this scale, or should
   the emphasis stay on one robust book + the microcap-lane hypothesis test? (Genuine open question.)
5. **The build roadmap (BUILD-0..7) is a plan, not code** — nothing here is implemented yet.

## Verdict

**Clean for GPT cross-review.** No §3 hard-invariant or §7 research-integrity violation; the load-bearing
claims are either 3-vote-verified (1-5) or explicitly flagged as sourced-not-verified (6-7); all
uncertainties are disclosed rather than hedged. The MLflow-mandate gap (minor) and the five caveats above
are the recommended focus for the reviewer.
