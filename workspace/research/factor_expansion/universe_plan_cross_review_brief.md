# Cross-Review Brief — Universe-Coupled Factor Evaluation Redesign (2026-06-11)

**For:** GPT 5.5 Pro cross-review. You have NOT seen the conversation that produced this — this brief is
self-contained. **Your job:** adversarially review the DESIGN in
[universe_coupled_evaluation_plan.md](universe_coupled_evaluation_plan.md) (Chinese; Draft-3 + §3.7).
Attack: statistical soundness, multiple-testing exposure, identity/governance design, normalization
population choices, thin-domain power, and anything internally inconsistent or gameable. Concrete
counter-arguments and failure scenarios > generic praise. If a decision point (§8, D1–D5) should be
decided differently, say so with the argument.

---

## 1. Context (the system, in 10 lines)

A-share quant research platform (Tushare + Qlib). ~190 catalog factors, each a registry row with a
status ladder: `draft` → (human-signed **IS-only walk-forward gate**, leak-proof: factor date AND
label-realization date ≤ is_end) → `candidate` → (**single-shot sealed OOS**, seal spent on attempt,
keyed by a FrozenSelectionSet hash that already includes a `universe` field) → `approved`.
Evidence NEVER changes status (resolve-but-label); only the two human gates do. OOS windows are
permanently accounted: ~88 candidates' 2021–2026 OOS is burned (`oos_informed_backfill`).
Evaluation taxonomy was just consolidated to TWO classes: `discovery` (cheap in-sample screening,
zero status power) and `formal` (the walk-forward methodology; human-signed runs can back status,
automated runs are evidence-only). All quantile evaluation paths use 10 groups (deciles).
Sealed-OOS empirical kill rate on IS-strong factors: ~4/5 (multiple precedents).

New since this week: a 7-universe mask framework (univ_all / csi300 / csi500 / csi1000 / microcap-400 /
ChiNext+STAR boards / liquid-top300), CICC-style exclusion screens (ST/suspension/limit-board/<1yr),
externally calibrated against a CICC factor handbook's published truth tables (anchor factors hit
IC/monotonicity/turnover fingerprints to ~0.1pp on change-type factors).

## 2. What the plan proposes (summary of the Chinese doc)

1. **Universe enters factor-evaluation identity, NOT computational identity.** Expressions +
   definition_hash stay universe-agnostic (Barra Layer-1: compute full market, mask later). The
   LIFECYCLE gains universe:
   - `intended_universe` is a REQUIRED declaration at draft registration, timestamped BEFORE any
     evaluation evidence exists for that factor (pre-registration moment moved to birth).
   - On entering draft, the factor is AUTOMATICALLY evaluated across ALL 7 universes (discovery
     methodology; evidence rows keyed (factor, universe, methodology_hash)). So declaration precedes
     observation mechanically, then the full matrix exists from day one.
   - IS gate evaluates on the DECLARED universe only; candidate records `gated_universe`. Changing
     domain after seeing the matrix requires disclosure of observed results + an economic prior for
     the new domain, flagged post-hoc with stricter review.
   - Sealed OOS: unchanged (FrozenSelectionSet already carries universe).
   - `approved` gains `validity_domains` metadata: {gated domain (OOS-verified)} ∪ {domains whose
     evidence clears the same bar, labeled evidence-only}. Strategies referencing evidence-only
     domains get a warning, not a block.
2. **Multiple-testing discipline:** testing ledger accounts per (factor, universe); the 7-domain
   matrix is descriptive and cannot itself justify a gate application — the application needs an
   economic prior for the declared domain; re-applying in a second domain requires disclosing all
   prior domains' outcomes.
3. **Normalization population (§3.7):** any cross-sectional transform that produces FACTOR VALUES
   (size/industry neutralization, industry-relative composites) normalizes on a FIXED estimation
   universe (univ_all post-screens, Barra ESTU style) — one value per stock-day, hash-locked.
   The evaluation layer separately computes a WITHIN-DOMAIN neutralized IC as a diagnostic
   (hashed methodology knob) — explicitly a different question, named apart.
4. Thin domains (microcap-400 / liquid-300: 30–40 names per decile) get mandatory bootstrap CIs in
   gate reports; the bar is NOT loosened. CSI1000 domain only spans 2014-11+ (shorter IS/OOS windows,
   must be flagged).
5. Execution: backfill the 190-factor × 7-universe matrix; new registrations get the matrix at entry;
   IS-gate contract change (declared universe) is decision point D1.

## 3. Specific review asks (attack these)

1. **Pre-registration timing.** Is "declare intended_universe at draft, before the auto-matrix runs"
   actually airtight? Failure mode we worry about: the researcher PRE-computes the matrix in a
   sandbox (the screening tools accept ad-hoc expressions without registration), peeks, then
   registers with the "right" declaration. Can a process/technical control close this, or is it
   irreducibly a discipline norm? Is the post-hoc flag + stricter review sufficient mitigation?
2. **Multiple-testing accounting.** With 7 domains per factor, what's the right family-wise
   correction for the IS gate bar (heldout RankICIR + sign consistency)? The plan counts tests per
   (factor, universe) in a ledger but does NOT currently adjust the gate bar for the number of
   domains observed in the matrix. Is "economic prior required + disclosure" enough, or should the
   bar itself scale (e.g., Bonferroni-ish on the declared-domain count, or a stricter bar when the
   declaration was post-hoc)?
3. **validity_domains semantics.** Mixing OOS-verified and evidence-only domains in one metadata
   field (with labels + warnings) — gameable? Alternative: only the gated domain in metadata,
   evidence matrix kept separate. Which failure modes does each invite?
4. **Estimation-universe choice (§3.7).** univ_all post-screens (≈2,500–5,000 names, equal-weight
   regression). Barra uses cap-weighted mean / sqrt-cap WLS. Does equal-weight ESTU neutralization
   leave a systematic size remnant that the within-domain diagnostic would then "discover" as
   signal? Should the neutralization regression be cap-weighted?
5. **Thin-domain gates.** microcap-400: 10 deciles × 40 names, monthly, ~12y. Is heldout RankICIR
   + bootstrap CI honest here, or does the gate need a hard minimum-breadth rule (e.g., no IS gate
   below N names/bucket)?
6. **Legacy backfill.** 190 existing factors get intended_universe=univ_all retroactively, with
   their matrix evidence marked "already observed" (any domain change = post-hoc). Loopholes?
7. **Anything else** — internal contradictions, governance gaps, incentive problems, simpler
   designs that achieve the same.

## 4. What is NOT under review

The 10-group standard, the two-class taxonomy, the seal mechanics, and the CICC replication
methodology are decided/calibrated; context only. Focus on §2/§3 above.
