# BUILD-0 — Transfer-Coefficient measurement + light-construction PoC — FINDINGS

> **Status:** COMPLETE (2026-07-11). IS-only (2014-2020), no sealed OOS spent, fully reversible.
> First empirical task of [STRATEGY_DEVELOPMENT_METHODOLOGY_v1.0](STRATEGY_DEVELOPMENT_METHODOLOGY_v1.0.md)
> (§1.1 TC diagnosis, §S2/§S3 construction). Script: [build0_tc_poc.py](../../scripts/build0_tc_poc.py)
> (reuses [guorn_optimize_09.py](../../scripts/guorn_optimize_09.py), no edits). Design red-teamed by a
> 4-lens adversarial review (2026-07-11) — its findings are folded in and the verdict logic was rebuilt as
> a result (see §7). GPT §10 cross-review still owed before anything here is treated as load-bearing.

---

## 1. Verdict (one paragraph)

**ADJUST, not greenlight.** On the s3_core deployable-core book (value+quality+low-vol, top-30,
non-microcap), **weight construction is a weak, statistically-insignificant lever for net risk-adjusted
return.** The methodology-faithful light construction (§S3-literal `w ∝ calibrated α = IC·σ·z`) does **not**
beat equal-weight top-K (ΔSharpe **−0.04**, bootstrap p=0.76; and it does not even raise the book's
Fundamental-Law transfer coefficient, ΔTC_full **−0.034**). **No** signal-proportional construction clears a
meaningful-margin + MDD-guard gate; the entire weight-construction family spans just **0.10 Sharpe (0.80–0.90)
and every difference vs equal-weight is inside bootstrap noise.** The lever this PoC did *not* control —
**selection** — is corroborated as larger by **one uncontrolled cross-composite** point: the real #9 book
(different names/factors, *same* sqrt-mv weighting) is Sharpe **1.18**, **+0.28 above the weighting family** —
subject to the same value-favorable-window caveat below, so *corroborating* (not *measuring*) selection
dominance; the controlled selection evidence is **external** (the #9 26pp→~1pp deployable-alpha
decomposition). This **corroborates and extends the parallel #9 result**: not only did a heavy MV optimizer
fail to beat naive top-K, even a *light* signal-proportional construction fails. **The BUILD-0 construction stack
should NOT be built as a return engine for this class of book.** It should be built (if at all) for **risk
reporting / neutralization / MDD control**, and the highest-ROI work stays on **signal-SELECTION
(deployable-alpha admission) + universe/lane** — the methodology's own §4.5 ranking.

**Scope guard (do not over-read):** this is *one* non-microcap value+quality+low-vol book on *one*
value-favorable IS window (2014-2020). It is exactly the **well-conditioned case §S3 assigns to the
optimizer**, and the *opposite* of the micro-tail lane where §S3 *prescribes* light construction. This PoC
therefore **does not settle** whether construction helps in the micro-tail lane — that is a separate test.
**Power caveat:** the paired-bootstrap 95% CIs are wide (`sqrtmv` [−0.12, +0.19], `sigcomp` [−0.25, +0.11]) —
this single IS window cannot detect even the gate's own +0.10 Sharpe margin, so the honest reading is
*"construction is not a **detectable** return lever here,"* not *"construction has no effect."*

---

## 2. What was tested, and why (cheaply, before building the stack)

The methodology's §1.1 spine is that deployable return is lost at the **portfolio-construction** step: `rank →
top-K → equal-weight` is a low-**transfer-coefficient** construction that throws away the cardinal signal, so
a real IC converts to only a fraction of its IR (`IR ≈ TC·IC·√breadth`). That "raise TC via better
construction" claim was **an unmeasured prior** in this system — and a parallel result had already *falsified
one form of it* (an MV optimizer, λ=2…100, did not beat naive top-K on #9). The open question: does a
**lighter** signal-proportional construction (not MVO) beat equal-weight on **net** PnL?

**Controlled experiment.** All constructions hold the **same 30 names** (top-30 by the shared
size+industry-neutralized composite `comp`), run through the **identical** event-driven envelope (0.2%/side,
slippage 0, `volume_limit=0.10`, `hold_on_limit_up`, Model-I 5-day rebalance, benchmark 000300.SH, ¥1M,
total-return). **Only the weight vector differs** → any net delta is a *construction* effect, not selection.

| construction | weights | role |
|---|---|---|
| `eqw` | `1/K` | the methodology's low-TC baseline (rank→top-K→EW) |
| `alpha` | `∝ σ·z` (Grinold `α = IC·σ·z`) | **§S3-literal `target_w ∝ calibrated α` — the methodology-faithful PRIMARY** |
| `sigcomp` | `∝ (comp − min + ε)` | score-proportional (the harness `wmode="signal"`; `∝ z`, **not** α) |
| `invvol` | `∝ z/σ` | risk-scaled / MV-diagonal *form* (its holdings-TC = 1 is a tautology) |
| `sqrtmv` | `∝ √circ_mv` | #9's own weighting — a **size** tilt, not signal; also a reuse cross-check |

PIT: factors are `Ref(...,1)`; `comp`, `σ` (trailing-60d vol) and the top-K selection all read data
`≤ pday = T-1`; the composite IS-IC uses `comp(≤T-1)` vs `fwd_5d[d]` (no overlap). No OOS path exists in the
script. **Reuse-fidelity is exact**: the `sqrtmv` construction reproduces the cached g09 s3_core baseline
**bit-for-bit** (`max|Δ daily return| = 0.0`), proving the composite pipeline reuse is faithful.

---

## 3. Step 1 — Transfer-coefficient measurement

`TC = corr(μ/σ, Δw·σ)` (Clarke–de-Silva–Thorley), Δw vs an equal-weight-over-eligible benchmark; calibrated
`μ = IC·σ·z ⇒ μ/σ = IC·z ⇒ TC = corr(z, Δw·σ)` (the IC scalar washes out). **Composite IS rank-IC (5d) =
+0.057** (IS-fitted, optimistic); **median eligible names/date = 2865**; 342 rebalances.

| construction | **TC_full** (headline) | TC_hold* (diagnostic) | eff-N | max_w | wt_turn | w~size | w~vol |
|---|---|---|---|---|---|---|---|
| `eqw` | **0.320** | 0.150 | 30.0 | 0.033 | 0.174 | — (flat) | — (flat) |
| `alpha` (∝σz) | **0.286** | 0.408 | 26.1 | 0.070 | 0.185 | −0.16 | **+0.86** |
| `sigcomp` (∝comp) | **0.262** | 0.941 | 15.5 | 0.135 | 0.193 | −0.05 | +0.15 |
| `invvol` (∝z/σ) | **0.338** | **1.000** | 27.3 | 0.061 | 0.189 | +0.16 | **−0.79** |
| `sqrtmv` (∝√mv) | **0.284** | 0.032 | 21.8 | 0.113 | 0.198 | **+0.95** | −0.17 |

**Headline (full-eligible, Fundamental-Law) TC does NOT support the §1.1 prior.** For a 30-of-2865 book the
active-weight TC is **selection-dominated**: it barely moves with construction (all span 0.26–0.34) and
`eqw` (0.32) sits **near the top**, *above* the faithful `alpha` (0.286, **ΔTC = −0.034**) and `sigcomp`
(0.262). No construction *materially* raises it — `invvol`'s +0.018 above eqw is inside the 0.26–0.34
barely-moves band, and the methodology-faithful `alpha` *lowers* it (−0.034).

**The holdings-only TC is a within-book diagnostic, not evidence.** `TC_hold` (eqw 0.15 → sigcomp 0.94 →
invvol 1.00) is **tautological for any signal-proportional weight**: `invvol ∝ z/σ ⇒ Δw·σ ∝ z ⇒
corr(z, Δw·σ) = 1` by construction. It measures "did the weights track the score", never realized return, so
it **cannot be used to select a construction** and must **not** be recorded as an edge. (Its inclusion in the
first-cut verdict was the review's headline blocker — see §7.)

**The confound diagnostics are consistent with what the net table shows.** `w~size`/`w~vol` (corr of the
weight with log-mktcap / σ) show each non-eqw construction is an **incidental style tilt**: `alpha`
tilts into **high-vol** (+0.86), `invvol` into **low-vol** (−0.79), `sqrtmv` into **large-cap** (+0.95).
`sigcomp` instead **halves effective breadth** (eff-N 15.5, top-name 13.5% — which would breach a 10% cap).

---

## 4. Step 2 — Net-of-cost IS returns (the decision metric)

Gate = **net Sharpe primary** (meaningful margin ≥ 0.10 **and** paired-bootstrap p < 0.10) **+ MDD guard**
(no worse by > 2pp). **TC is descriptive, never in the gate.** (Absolute Sharpe; the TC benchmark
[EW-eligible] ≠ the PnL benchmark [CSI300] — the two are **not** cross-cited.)

| construction | CAGR | **Sharpe** | MDD | vol | eff-N | TC_full | TC_hold* | ΔSharpe vs eqw (boot p) |
|---|---|---|---|---|---|---|---|---|
| `eqw` | +22.20% | **0.87** | −40.06% | 27.5% | 30.0 | 0.320 | 0.150 | — baseline |
| `alpha` (faithful) | +21.67% | 0.83 | −40.02% | 28.5% | 26.1 | 0.286 | 0.408 | **−0.04 (p=0.76)** |
| `sigcomp` | +20.96% | 0.80 | −42.22% | 29.2% | 15.5 | 0.262 | 0.941 | −0.07 (p=0.78) |
| `invvol` | +22.57% | 0.89 | −39.68% | 27.0% | 27.3 | 0.338 | 1.000 | +0.02 (p=0.23) |
| `sqrtmv` | +22.87% | **0.90** | −39.74% | 26.8% | 21.8 | 0.284 | 0.032 | +0.04 (p=0.33) |
| **#9 REPLAY** (selection) | **+30.03%** | **1.18** | −33.88% | 24.8% | — | — | — | *different names* |

Three decisive reads:

1. **No construction beats equal-weight significantly.** The best signal-proportional variant (`invvol`,
   +0.02 Sharpe) is **inside noise** (bootstrap p=0.23); the faithful `alpha` is **worse** (−0.04, p=0.76);
   `sigcomp` is the worst on every axis (Sharpe, CAGR, MDD, vol). `premise_holds = False`.

2. **Net-Sharpe is decoupled from holdings-TC.** The **best-Sharpe** book (`sqrtmv`, 0.90) has the
   **near-lowest** holdings-TC (0.03), while `sigcomp` — the highest-holdings-TC book *excluding* the
   tautological `invvol`=1.00 — is the **worst** (0.80). Across all five there is **no monotone/inverse
   TC_hold→Sharpe relation** (`invvol` at holdings-TC 1.00 has the 2nd-best Sharpe, 0.89). If TC drove
   return this ordering would be impossible. The tiny Sharpe spread is **consistent with the §3 style tilts**
   (not signal transfer): `sqrtmv`'s large-cap tilt (favorable in 2014-2020), `invvol`'s low-vol tilt;
   `alpha`'s high-vol tilt and `sigcomp`'s breadth loss (eff-N 15.5) look like the drag — but this positive
   attribution is a *hypothesis consistent with the tilt signs*, not established (§5 names the resolving test).

3. **Selection ≫ weighting (corroborated here, not measured).** The real #9 dividend book — *different
   names/factors*, same sqrt-mv weighting — is Sharpe **1.18**, **+0.28 above the entire weight-construction
   family**. This is **one uncontrolled, window-confounded** cross-composite point (the cleanest internal
   contrast is `sqrtmv` 0.90 → #9 1.18: same weighting, different selection), so it *corroborates* — it does
   not *measure* — that "which names" dominates "how to weight them". The controlled selection evidence is the
   **external** #9 26pp→~1pp tradeability decomposition.

---

## 5. Why this is robust (multiple independent corroborations)

- The **FLA-correct** TC (full-eligible) says weighting doesn't raise the book's TC (eqw near the top).
- The **net Sharpe** says no construction beats eqw, and every delta is **bootstrap-insignificant**.
- The **confound diagnostics** show the 0.10 Sharpe spread is **consistent with** style tilts (size/low-vol),
  not the TC mechanism; the spread is within bootstrap noise, and the tilt *signs* are consistent with — but
  do not establish — a size/low-vol explanation (resolving test: regress the five books' daily returns on
  size/low-vol factor returns).
- It **matches the #9 MVO null** and extends it from "heavy optimizer" to "even light construction".
- The **reuse cross-check is bit-exact**, so this is not a plumbing artifact.

---

## 6. Recommendation for BUILD-0 (and the methodology)

- **Do NOT build the construction stack expecting a weighting-driven return lift for this class of book.**
  The premise that "TC collapse at the weighting step is the operative leak" is **not supported** here.
- **Re-rank the levers to what is measured (methodology §4.5, now empirically anchored):** the large,
  *confirmed* lever is **deployable-alpha SELECTION** (the #9 26pp→~1pp gap close) + **universe / lane**;
  weighting is a weak lever for this book.
- **If a construction/risk layer is built, build it for RISK, not return:** the §S3 minimal risk model for
  **MDD control, neutralization, and attribution**, deployed only as a light risk-scaled (low-vol) tilt where
  it *demonstrably* cuts MDD (`invvol` cut MDD by only 0.4pp here — not compelling). Fail-closed, unlevered.
- **The micro-tail lane is the untested, higher-value question.** §S3 prescribes light construction *there*
  (ill-conditioned Σ, where the optimizer is wrong); this PoC tested the *opposite* (well-conditioned value
  book). A micro-tail construction test is the natural next PoC — but note the micro-tail's own hazards
  (§1.3: shell-premium decay, −33%/5-week tail risk).

---

## 7. Design red-team (folded) — what changed, and honest self-correction

A 4-lens adversarial review (TC-formula / PIT-leakage / verdict-stats / methodology-fidelity) verified the
**instrument** as PIT-clean, reversible, and formula-correct, but flagged the **first-cut verdict as broken**.
All findings were applied *before* recording this conclusion:

- **[fixed] Verdict logic was vacuous + lenient.** The old gate's TC leg (`ΔTC_full OR ΔTC_hold`) was carried
  entirely by the **tautological** holdings-TC term (always True for ∝signal), giving TC zero decision
  weight; the return leg (`ΔSharpe OR ΔCAGR`, **MDD never read**) admitted a concentration-driven CAGR bump
  with worse Sharpe/MDD. **Rebuilt:** net Sharpe primary + bootstrap significance + MDD guard; **TC removed
  from the gate.**
- **[fixed] TC headline was the wrong one.** Now headlines the **full-eligible calibrated** TC (which favors
  eqw); holdings-TC labeled a diagnostic; `invvol=1.00` labeled an algebraic identity, never "best".
- **[fixed] "Primary" was mislabeled.** `sigcomp (∝comp = z)` is **not** the §S3-literal `∝ calibrated α`;
  `alpha (∝σz)` was promoted to the faithful primary. All 5 reported (implicit 5-construction multiplicity;
  no deflation claimed).
- **[added] Confound diagnostics + paired bootstrap** (eff-N, max-w, weight-turnover, `w~size`, `w~vol`,
  Sharpe-diff CI/p) — so a net delta is attributable, and the ~0.10 spread is shown to be noise.
- **[disclosed] σ is a total-vol PROXY**, not residual/idio vol (handoff permits 先粗后精); this mislabels
  the `alpha`/`invvol` Grinold/MV *pedigree* and gives `alpha` a beta/high-vol tilt — **residual vol is the
  BUILD-0b refinement.** Only the **eqw-vs-`sigcomp`** comparison is σ-independent (both use no σ); the
  faithful **`alpha` (∝σz)** and **`invvol` (∝z/σ)** results ARE computed under the total-vol proxy, which
  tilts `alpha` into high total-vol — **whether residual/idio vol changes the faithful-`alpha` ΔSharpe/ΔTC
  is UNTESTED** (resolving test = re-run `alpha`/`invvol` on residual σ, BUILD-0b). The absolute
  IC/CAGR/Sharpe are **IS-fitted** (sign-orientation on the same window) → optimistic, design-stage, **not
  deployable estimates**.

---

## 8. Guardrails honored

IS-only (2014-2020); **no sealed OOS touched** (the script has no OOS path); fully reversible. Reused the
trusted harness (no edits) + cached panel/returns/IS-IC; metrics via `research_utils.goal_metrics`; MLflow
opt-in (`--mlflow`). #9 session confirmed stopped before starting (no conflict). Every absolute number is an
**IS design-stage** figure, not a deployment estimate. The stale E-wave / eps_diffusion deployment magnitudes
(CLAUDE.md §3.5) are **not** quoted.

## 9. Reproduce

```bash
venv/Scripts/python.exe workspace/scripts/build0_tc_poc.py --prepare      # Step 1: TC + confounds + schedules
venv/Scripts/python.exe workspace/scripts/build0_tc_poc.py --run-all      # Step 2: 5 event-driven IS backtests
venv/Scripts/python.exe workspace/scripts/build0_tc_poc.py --assemble     # Step 3: table + bootstrap + verdict
# artifacts: workspace/outputs/guorn_parity/optimize09_cache/{build0_tc.json, build0_results.json, sched_build0_*.json, net_build0_*_is.parquet}
```
