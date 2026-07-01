# Factor Eval — Stage-0 evidence-provenance patch (+ the "is tiering worth it?" question)

> **Extends** v1.3 (the approved source of truth). **Gap it closes:** v1.3 Stage 0 writes "a-priori
> rationale, expected direction" as if direction is always a-priori, and the live system only has the
> coarse `a_priori` vs `oos_informed` labels (about whether OOS was *burned*). Neither captures a
> **third tier**: OOS-clean, but the *direction/hypothesis was formed from the full-IS aggregate*. v1.3
> would mislabel that as `a_priori` and **overstate the evidence** (treat "IS formed the idea" as "IS
> independently confirmed a prior idea"). **Primary deliverable for review: NOT just whether the patch
> is correct, but what the PRACTICAL significance of evidence-tiering actually is (§2/§3).**
> **Status:** proposal for GPT analysis; nothing changes code until reviewed.

## §1 — The patch (the three-tier model)

```
direction_provenance / evidence_tier:
  theory_a_priori     : direction + rationale committed from theory/literature/external mechanics,
                        BEFORE computing IS. → IS is an INDEPENDENT confirmation; OOS is an
                        independent test. (3 independent pieces: prior · IS · OOS.)
  a_priori_is_informed: OOS never observed (clean), BUT direction/hypothesis was formed by looking at
                        the full-IS aggregate. → IS is NOT independent (it produced the hypothesis);
                        only OOS is an independent test. (effectively 1 independent test: OOS.)
  oos_informed        : OOS was observed/used in selection → OOS BURNED for this factor; no fresh OOS
                        claim possible. (the existing label.)
```

**Conservation principle (the rule that forces the tier):** *a given dataset may DEVELOP a hypothesis
or CONFIRM it, not both for the same claim.* Therefore an `a_priori_is_informed` factor **may not cite
its IS RankICIR/sign-consistency as confirming evidence** — IS already spent its independence forming
the direction.

**Sign-flip recording:** if IS contradicts a committed direction, record `prior_contradicted_by_is=true`
and downgrade the tier (theory_a_priori → a_priori_is_informed). **Never silently flip the sign and
proceed as `a_priori`.**

**Three-case workflow → tier:**
- no prior → form direction from IS → register `a_priori_is_informed` (disclose the screening pool).
- weak prior → commit tentatively; IS confirms → stays `theory_a_priori` (weak); IS contradicts →
  `a_priori_is_informed` + contradiction recorded.
- strong prior → `theory_a_priori`; IS is independent confirmation; if IS falsifies, it's a *cheap
  rejection*, not a rescue-by-revision.

**What is UNCHANGED:** the PIT alignment, role, and "why I'm testing it" are always a-priori-fillable;
the pass bar is fixed in all tiers; the OOS is single-shot in all tiers; the IS gate is already
leak-proof to direction-fitting (it re-derives direction per train-fold), so the tier is **not** about
a mechanical leak — it is about **evidence accounting**.

## GPT verdict (resolved): APPROVE — minimal load-bearing form (NOT inert metadata, NOT an IS-bar change)

GPT 5.5 Pro analysis: the tier does **not** change mechanical validity (a fresh sealed OOS is real
evidence in any tier) — it changes **evidentiary independence, reporting permissions, multiplicity
accounting, and deployment/revalidation trust**. Keep it, but only in a small form with teeth.

**The single load-bearing rule (most important):**
> For `a_priori_is_informed` factors, IS may **generate** the hypothesis/direction but may **NOT** be
> cited as confirming evidence for the same claim. Framing: **"OOS-clean, IS-spent"** — still testable
> on OOS, but IS already spent its independence forming the direction.

**Do NOT change the IS candidate bar by tier** — keep the fixed `|RankICIR|≥0.10 ∧ sign≥0.70`; change
only *what an IS pass is allowed to MEAN*, not the bar. **Do NOT create a parallel status universe** —
the tier is a field inside the provenance/multiplicity object.

**Minimal schema (`Stage0EvidenceProvenance_v1`):**
```yaml
evidence_tier: theory_a_priori | a_priori_is_informed | oos_informed
direction_source: external_theory | literature | mechanism | IS_aggregate | OOS_observed | mixed
is_seen_before_direction: bool ; oos_seen_before_claim: bool ; prior_contradicted_by_is: bool
may_cite_is_as_confirmation:   # derived
  theory_a_priori -> true ; a_priori_is_informed -> false ; oos_informed -> false
fresh_oos_eligible:            # derived
  oos_informed -> false ; otherwise -> true
multiplicity_scope_id: required_if evidence_tier != theory_a_priori OR cohort/family expansion
```

**The 4 downstream hard reads (this is what makes it load-bearing — wire all four or drop the tier):**
1. **Reports** read `may_cite_is_as_confirmation` → forbid "IS confirmed the prior" language for
   `a_priori_is_informed`.
2. **Stage 6/7 OOS report** reads `multiplicity_scope_id` → discloses the screened-pool denominator;
   labels the OOS "first independent confirmation" for `a_priori_is_informed`; FDR/max-stat at the
   selected-set/family level.
3. **Deployment / revalidation** read `evidence_tier` → tighter monitoring / faster downgrade leash for
   `a_priori_is_informed` (NOT a fake-precision sizing formula).
4. **Seal logic** reads `fresh_oos_eligible` → `oos_informed` cannot make a fresh-OOS approval claim.

**Not redundant with multiplicity disclosure** — it is a *trigger + classifier* for it: a factor can be
`theory_a_priori` + high multiplicity (40 literature variants) OR `a_priori_is_informed` + low recorded
multiplicity (one IS-aggregate look), so the tier ≠ the count. Implement it **inside** the
provenance/multiplicity object, not as an isolated label no rule reads.

**Sign-flip:** `prior_contradicted_by_is=true` + downgrade `theory_a_priori → a_priori_is_informed`;
never silently flip and stay `theory_a_priori`.

*(My §2/§3 first-cut below is retained as the design rationale; the verdict above is the resolution.)*

## §2 — My first-cut analysis of the practical significance (for GPT to attack)

The honest tension: the IS gate is leak-proof (train-fold) and the OOS is single-shot for *all* tiers,
so a `theory_a_priori` and an `a_priori_is_informed` factor that both pass IS+OOS **passed the same
gates with the same fixed bar**, and the OOS number is a genuine out-of-sample number either way. So
the question is sharp: **does the tier change the VALIDITY of a result, only its INTERPRETATION, or a
concrete downstream DECISION?** Four candidate consequences, ordered weakest→strongest:

- **(a) Reporting honesty / anti-overclaim (interpretation-only).** The tier stops the claim "I had a
  prior and IS confirmed it" when IS actually produced the idea. Value is proportional to how often the
  team would otherwise overclaim — and this project has a documented history of exactly that failure
  (val_heavy, eps_diffusion's "too-good" LS Sharpe, the report_rc provenance saga). But if this is ALL
  it does, it is reputational bookkeeping that changes no decision.
- **(b) Multiplicity proxy (should tighten the OOS interpretation).** `a_priori_is_informed` is a flag
  that the *effective* hypothesis count is higher (you saw IS, possibly tried both signs, likely
  screened several). Multiplicity DOES change what a single OOS pass means: 1 OOS pass from 1 theory
  prior is stronger than 1 OOS pass selected from 20 IS-screened candidates. This gives the tier teeth
  **iff** it is wired to the existing multiplicity disclosure (C7/FC6) and/or a stricter/FDR-adjusted
  OOS treatment for is_informed sets.
- **(c) Double-counting prevention (concrete iff IS is read downstream).** Any later step that consumes
  IS-confirmation — composite-construction priors, "robust because IS+OOS agree" robustness claims, a
  deployment trust/sizing prior — must EXCLUDE IS for `is_informed` factors, else it double-counts the
  data that formed the hypothesis. Concrete only to the extent such downstream reads exist.
- **(d) Deployment trust / revalidation leash (concrete iff the deployment layer reads the tier).**
  A weaker-evidence factor (`is_informed`) could get a smaller initial allocation, a shorter leash, or
  a faster downgrade trigger in the revalidation cadence. This makes the tier load-bearing at the
  deployment/maintenance layer.

**My position (challenge it):** the tier is **load-bearing only if it changes a concrete thing** —
minimally (b) mandatory multiplicity disclosure + (c) "IS may not be cited as confirmation for
is_informed"; ideally also (d) a tier input to deployment trust / revalidation cadence. If it is
**decoupled** from every bar/sizing/cadence, it collapses to (a) — honest metadata with no decision
consequence — and then the added Stage-0 complexity is **probably not worth it** given the gates are
already leak-proof. The risk is **inert metadata**: a field everyone fills in and no rule ever reads.

## §3 — The questions for GPT (centered on practical significance)

1. **Is evidence-tiering practically load-bearing, or interpretation-only?** Given the IS gate is
   already leak-proof (train-fold) and the OOS is single-shot, does the tier change the *validity* of
   a result at all — or only how we *describe* it?
2. **Where, concretely, should the tier plug into a decision** (if anywhere): the OOS multiplicity/FDR
   bar, the deployment trust/position-sizing prior, the revalidation cadence, the "may-IS-be-cited"
   rule? Or nowhere?
3. **Is it redundant with the existing multiplicity contracts (C7/FC6)?** Is `a_priori_is_informed`
   just a per-factor restatement of "disclose your screening pool"? If so, fold it into multiplicity
   disclosure rather than a new tier.
4. **Is the marginal honesty worth the added Stage-0 complexity**, for a team that has been burned by
   provenance overclaim before — or is it ceremony that will become inert metadata?
5. **If kept, what is the minimal load-bearing form** — the smallest set of concrete consequences that
   makes the tier change real decisions without bloating Stage 0?

## Decision requested

A candid analysis of whether evidence-tiering earns its place: what it concretely buys, where it must
wire into a real decision to not be inert, and whether the minimal form is worth it — or whether the
existing leak-proof IS gate + single-shot OOS + multiplicity disclosure already cover the substance,
making the explicit tier redundant.
