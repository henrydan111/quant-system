# GPT Cross-Review Request — C1 outcome stats v0 + acceptance review tooling — Tier-3 (single pass)

Reviewing **one unit**: three read-only Class-D diagnostic tools over the AI chain's test
artifacts, plus the methodology of the first 202501 diagnostic run. Everything here is
NON_EVIDENTIARY and consumes chain outputs; nothing feeds back into any scoring path.

## ⚠ FROZEN REVIEW TIER — Tier-3

Per CLAUDE.md §10 tiering: workspace research scripts — self-review + **at most one GPT
pass**. No adversarial-caller analysis. Verdict: SOUND / CHANGES REQUIRED (+ tracked notes).

**Commit under review: `30780a2`** on branch `calendar-unfreeze`.

## Quantitative-research principles first (PIT / no-lookahead / C16)

- All outputs are labeled `NON_EVIDENTIARY_PILOT`; single month (202501) / single day
  (20250127); gross returns, no cost — diagnostics, not alpha evidence.
- **C16 fence**: results must NOT be wired into prompts/weights/selection (stated in the
  script header and findings doc); any future feedback = C16b registration + new forward
  epoch.
- Forward returns are computed from the local attested qlib provider (adj open), NOT from
  the reviewed repo's conventions. Entry conventions: leg-obs decisions pre-open day D →
  entry open(D); leg-chain consumes day-D EOD cards → entry open(D+1). Please check these
  for lookahead.

## Files (pin to `30780a2`)

1. [workspace/research/ai_chain_observatory/outcome_stats.py](https://raw.githubusercontent.com/henrydan111/quant-system/30780a2/workspace/research/ai_chain_observatory/outcome_stats.py)
   — C1 v0: leg-obs (16 replay days × ~149 names; RankIC / quintile spread / top-quintile-
   beats-median; buckets: no_text / in_floor / named-vs-anon) + leg-chain (single
   cross-section 20250127, 5-seat chain composite/seat ICs + divergence/bear-discount/
   dispersion buckets).
2. [workspace/research/ai_chain_observatory/OUTCOME_STATS_202501.md](https://raw.githubusercontent.com/henrydan111/quant-system/30780a2/workspace/research/ai_chain_observatory/OUTCOME_STATS_202501.md)
   — the findings doc under review for over-claiming.
3. [workspace/research/ai_research_dept/acceptance_digest.py](https://raw.githubusercontent.com/henrydan111/quant-system/30780a2/workspace/research/ai_research_dept/acceptance_digest.py)
   — validation-day one-page acceptance digest (149 archives; uniformity/judge
   distributions/fence+bear aggregates/spot-check list). Reads archives as plain JSON, no
   engine imports (contract-hash neutral).
4. [workspace/research/ai_research_dept/acceptance_mechanical_check.py](https://raw.githubusercontent.com/henrydan111/quant-system/30780a2/workspace/research/ai_research_dept/acceptance_mechanical_check.py)
   — INDEPENDENT re-implementation of evidence grounding (span↔card-line, bear
   quote↔all-lines incl. market_context M-domain) + judge arithmetic
   (composite = 0.4/0.3/0.3 · finals, 1-decimal round semantics; adj≤final monotonicity).
   Result on chain_v3.0/20250127: 6,113 spans + 870 quotes + all arithmetic = 0 violations
   (two initial finding classes were adjudicated as MY checker's gaps — M-domain omitted;
   round-boundary tolerance — and fixed; that adjudication is part of what to review).

## Key findings claimed (check for over-claim / method error)

- Old replay chain 202501: named-text score IC negative (h5 −0.019, h20 −0.104) while the
  anonymized ablation scores better (h5 +0.027) → framed as name-prior-bias evidence
  **within this month**; fund structured-card strongest (h5 +0.158, ICIR 1.03);
  `combined` ≈ its own quant input (h5 +0.078 vs +0.080); no-text names −1.4pp h5 excess.
- 5-seat chain single-day cross-section anti-correlated with the Feb-2025 rally
  (composite_adj h20 −0.234) — explicitly direction-only, no statistical force.
- h≥5 daily IC series overlap (autocorrelation) — ICIR labeled comparative-only.

## Review questions

1. **Lookahead**: any leak in the forward-return constructions (entry offsets, positional
   trading-day indexing, dropped codes) for either leg?
2. **Method**: RankIC/quintile/beats-median implementations and the aggregation across 16
   overlapping days — any statistical claim the findings doc makes that the design cannot
   support? Is the named-vs-anon "name-prior bias" framing justified as a within-month
   observation?
3. **Independence**: does acceptance_mechanical_check genuinely constitute a second
   implementation (no shared code with engine validators), and are its two self-adjudicated
   fixes correct (M-domain inclusion; `round(x,1)` semantics vs a strict 0.05 tolerance)?
4. **Containment**: any way these tools' outputs could act as an unregistered selector /
   feedback path violating the stated C16 fence?
5. Anything in the findings doc that should be weakened or caveated further?

## Self-review

Clean for GPT: read-only consumers; no engine imports in acceptance tools; evidence-grounding
re-verified independently at 0 violations; findings doc carries single-month/single-day and
gross-return caveats and the C16 prohibition. The 202501 numbers were spot-echoed from the
generated JSON, not hand-copied.
