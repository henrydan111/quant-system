# BUILD-0 TC PoC — GPT §10 cross-review prompt (ROUND 2, post-REWORK)

Round 1 verdict = **REWORK** (5 Blockers + 4 Majors + 2 Minors). Every finding is folded (see the
disposition table in [BUILD0_TC_POC_FINDINGS.md](BUILD0_TC_POC_FINDINGS.md) §7). This round asks GPT to
confirm the Blockers are closed. Self-contained; raw links are on branch `calendar-unfreeze`;
`guorn_optimize_09.py` is now committed, and the full local dep chain is content-addressed in each run's
evidence manifest.

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. This is your ROUND-2 re-review of an IS-only, design-stage PoC you returned REWORK on. Confirm each Round-1 Blocker is genuinely closed (not papered over), and surface anything new. Do not rubber-stamp.

REPO (public — fetch to verify against live code)
https://github.com/henrydan111/quant-system   (branch: calendar-unfreeze)
Raw form: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/<path>

FETCH THESE (authoritative):
- CLAUDE.md  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/CLAUDE.md
- Methodology (§1.1/§S2/§S3/§4.5)  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/strategy_development_methodology/STRATEGY_DEVELOPMENT_METHODOLOGY_v1.0.md
- Script (reworked)  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/scripts/build0_tc_poc.py
- Findings v2 (verdict + full REWORK-response table §7)  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/strategy_development_methodology/BUILD0_TC_POC_FINDINGS.md
- Reused harness (now committed)  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/scripts/guorn_optimize_09.py
- Tests  .../tests/workspace/test_build0_tc_poc.py  and  .../tests/workspace/test_build0_window_isolation.py

YOUR ROUND-1 BLOCKERS AND HOW THEY WERE ADDRESSED — verify each against the live code:
B1 (OOS access): `_setup()` now truncates close/circ/ret/fwd5 to <= IS_END on load and ASSERTS it; a test
   (test_build0_window_isolation.py) pins "no row > IS_END" and "no --window/OOS path". Findings reworded:
   compute is IS-only but caches were opened -> 2021-2026 is "potentially-observed", not certified virgin.
   CONFIRM: is this sufficient, or do you still require inputs regenerated via qlib_windowed_features?
B2 (full-window direction = lookahead): The composite orientation is A-PRIORI (value/quality long, low-vol
   short-high-vol). The IS-IC-fit signs COINCIDE with the a-priori signs for all 8 factors, so
   `--orientation a_priori` reproduces `--orientation is_fit` BIT-FOR-BIT (verify-orientation: max|Δcomp|=0,
   top-30 selection symmetric-diff=0 over 342 dates). => the composite has NO cross-time fitted parameter, so
   no orientation lookahead. `walk_forward` (expanding IC, label<=pday, a-priori warm-up) is also implemented.
   CONFIRM: does a_priori==is_fit dissolve the resubstitution concern, or do you require walk_forward numbers?
B3 (alpha != §S3; max_w table bug): `alpha` is relabeled an UNCONSTRAINED σ-proxy (NOT the §S3 constructor);
   the §S3 gaps are enumerated; `--max-weight` (single-name cap) and `--sigma residual` are added and RUN;
   the table now reports true per-day MAX (26%) not the mean (7%). CONFIRM the relabel + the new runs suffice.
B4 (four-layer): the `broad` mask's `cr.notna()` price gate is disclosed as a PIT last-known-price gate
   applied identically to all 5 (does not bias the weighting delta); not claimed as pristine four-layer.
B5 (verdict over-claim): `premise_holds`->`screen_passed`; status = INCONCLUSIVE_no_greenlight; gate is
   FAIL-CLOSED (finite tail-mass < 0.10 AND ΔSharpe >= 0.10 AND MDD not worse). Verdict no longer claims
   "weighting is weak" or "selection/universe > weighting".
M1 fail-open bootstrap gate -> fail-closed + relabeled "tail-mass" (circular-block), not p-value.
M2 invvol TC_hold "=1" -> "structural near-identity (0.9997), benchmark term σ/N tiny", never "best".
M3 reproducibility -> evidence manifest per run (git SHA, input/output/dep SHA-256, provider/calendar ids);
   full local dep chain content-addressed; guorn_optimize_09.py committed; manifest_complete=True.
M4 selection/universe not measured -> stated; #9 = one uncontrolled corroborating point; external 26->1pp is
   the controlled selection evidence.
Minors: mean/p95/MAX columns; "value-favorable" flagged unverified.

NEW RESULTS (from Findings v2 §4; reconcile against build0_{ref,cap,res}_results.json). SAME top-30 names,
weights differ only. Fail-closed screen. All screen_passed=False; status INCONCLUSIVE_no_greenlight.
  build0_ref (a_priori, total σ, uncapped):  eqw Sharpe 0.87 | alpha 0.83 (ΔSh −0.04, tm 0.76) | sigcomp 0.80
    (−0.07, tm 0.78) | invvol 0.89 (+0.02, tm 0.23) | sqrtmv 0.90 (+0.04, tm 0.33). Uncapped max_w: alpha/sigcomp 0.26.
  build0_cap (a_priori, total σ, cap 0.05):  eqw 0.87 | alpha 0.84 | sigcomp 0.82 | invvol 0.89 | sqrtmv 0.87.
  build0_res (a_priori, RESIDUAL σ, cap 0.05): eqw 0.87 | alpha 0.83 | sigcomp 0.82 | invvol 0.88 | sqrtmv 0.87.
  => the §S3-faithful alpha stays below eqw under BOTH σ modes (residual σ does not rescue it); the 5% cap
     compresses all constructions toward eqw (eff-N 23-28); every ΔSharpe CI straddles ±0.10 (underpowered).
VERDICT (Findings v2 §1): INCONCLUSIVE — no greenlight; "construction is not a DETECTABLE net-return lever
for this well-conditioned value book on this one IS window", NOT "weighting has no effect", NOT "selection ≫
weighting". Micro-tail lane (where §S3 prescribes light construction) untested.

QUANTITATIVE-RESEARCH PRINCIPLES — a violation is a Blocker (PIT/no-lookahead #1; OOS sacred #2; survivorship
#3; execution/cost realism #5; no leverage #6; no hedge words #7; four-layer #8; multiple testing #9).

REVIEW QUESTIONS
1. Are Round-1 Blockers B1-B5 genuinely closed? For each, is the fix real (verify in code) or cosmetic?
   In particular: (a) does a_priori==is_fit dissolve B2, or do you still require walk_forward net numbers?
   (b) is the ≤IS_END truncation + "potentially-observed" disclosure sufficient for B1, or must inputs be
   regenerated via the sanctioned windowed door?
2. Is the INCONCLUSIVE verdict now correctly scoped (no evidence-of-absence, no unmeasured selection/universe
   claim, power caveat present)? Any remaining over-claim?
3. Correctness of the NEW code: `_cap_simplex` (water-filling), `_sigma_asof` residual = total*sqrt(1-ρ²),
   `_walkforward_signs` (label realized ≤ pday), the fail-closed `_verdict`, the evidence manifest.
4. Anything unsafe to record to durable memory as the BUILD-0 conclusion.

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending line/claim quoted and an exact replacement;
  map every Blocker to the principle/invariant it violates.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.
```
