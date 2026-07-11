# BUILD-0 — Transfer-Coefficient measurement + light-construction screen — FINDINGS (v2)

> **Status:** COMPLETE, reworked after GPT §10 = **REWORK** (2026-07-11). IS-only (2014-2020), **no sealed
> OOS spent**, fully reversible. First empirical task of
> [STRATEGY_DEVELOPMENT_METHODOLOGY_v1.0](STRATEGY_DEVELOPMENT_METHODOLOGY_v1.0.md) (§1.1 TC diagnosis,
> §S2/§S3 construction). Script: [build0_tc_poc.py](../../scripts/build0_tc_poc.py) (reuses
> [guorn_optimize_09.py](../../scripts/guorn_optimize_09.py), no edits). Tests:
> [test_build0_tc_poc.py](../../../tests/workspace/test_build0_tc_poc.py) +
> [test_build0_window_isolation.py](../../../tests/workspace/test_build0_window_isolation.py) (19 passed).
> Design + findings were adversarially reviewed by two internal multi-agent workflows, then by GPT-5.5 Pro
> (verdict **REWORK**, 5 Blockers). **This v2 folds every GPT finding** (§7). Round-2 GPT prompt:
> [BUILD0_GPT_REVIEW_PROMPT.md](BUILD0_GPT_REVIEW_PROMPT.md). Not load-bearing until GPT returns SHIP.

---

## 1. Verdict (one paragraph)

**INCONCLUSIVE — no greenlight, and no re-scoping of the roadmap on this evidence alone.** This is an
**exploratory screen** that varies *only the weight vector* over a **fixed top-30 selection** on **one**
non-microcap value+quality+low-vol book across **one** IS window — it is **not** an equivalence test and it
does **not** measure selection or universe (the universe never changes). Under **every** tested
configuration — uncapped / capped-at-5% × total-σ / residual-σ — **no signal-proportional construction
passes a fail-closed screen** (net Sharpe margin ≥ 0.10 **and** MDD-not-worse **and** finite bootstrap
tail-mass < 0.10). The methodology-faithful §S3-form (`alpha ∝ σ·z`) is **below** equal-weight in all four
cells (Sharpe 0.83–0.84 vs 0.87), and **residual σ does not rescue it** (0.83 under both σ modes). But the
paired-bootstrap 95% CIs are **wide** (they straddle the ±0.10 margin), so the honest reading is
**"weight construction is not a *detectable* net-return lever for this book/window"**, *not* "weighting has
no effect" and *not* "selection/universe beat weighting". With a real §S3 concentration cap the constructions
**collapse toward equal-weight** (Sharpes 0.82–0.89), which is consistent with — but does not prove — a weak
weighting lever. **Recommendation:** do not build the construction stack expecting a *weighting-driven return*
lift for this class of book; the properly-scoped next tests are a residual-σ / §S3-*fully-constrained*
constructor and, above all, a **micro-tail-lane** construction test (the lane §S3 actually prescribes light
construction for — untested here). Any "selection + universe ≫ weighting" claim must be earned by an
experiment that *varies* selection and universe, which this is not.

---

## 2. What was tested — and the four things it is NOT (read before citing)

The methodology's §1.1 prior: deployable return is lost at the **construction** step because
`rank → top-K → equal-weight` discards the cardinal signal (a transfer-coefficient **TC** collapse), so a
real IC converts to a fraction of its IR (`IR ≈ TC·IC·√breadth`). A parallel result already showed an **MV
optimizer** (λ=2…100) did not beat naive top-K on this book; the open question was whether a **lighter**
signal-proportional construction does.

**Controlled experiment.** The SAME top-30 names (top of the size+industry-neutralized composite `comp`,
non-microcap), 5 weight vectors, identical event-driven envelope (0.2%/side, slippage 0, `volume_limit=0.10`,
`hold_on_limit_up`, Model-I 5-day rebalance, benchmark 000300.SH, ¥1M, total-return). **Only the weight
vector differs.**

| construction | weights | role |
|---|---|---|
| `eqw` | `1/K` | low-TC baseline (no σ, no orientation dependence) |
| `alpha` | `∝ σ·z` | Grinold-form; the §S3-*literal* `w ∝ calibrated α` **shape** — but an **unconstrained proxy**, NOT the §S3 constructor (see below) |
| `sigcomp` | `∝ (comp − min + ε)` | score-proportional (harness `wmode="signal"`; `∝ z`) |
| `invvol` | `∝ z/σ` | MV-diagonal *form*; its holdings-TC ≈ 1 is a structural near-identity, not an edge |
| `sqrtmv` | `∝ √circ_mv` | #9's own weighting (a size tilt); also a reuse cross-check |

**This experiment is NOT:**
1. **NOT a §S3 light constructor.** `alpha`/`invvol` are *unconstrained σ-proxies*. §S3 additionally mandates
   **portfolio-level** size/industry neutrality, **single-name + industry caps**, and **ADV / turnover / cost
   penalties**. This PoC adds only the first-order **single-name cap** (`--max-weight`) and **residual σ**
   (`--sigma residual`); the rest is untested. Calling `alpha` "the §S3 construction" would be false.
2. **NOT an equivalence test.** "No construction passed the screen" is *absence of detected effect*, not
   *evidence of absence* — the bootstrap CIs are wide enough to contain a deployment-relevant +0.10 Sharpe.
3. **NOT a measurement of selection or universe.** The name set and universe are held fixed. This PoC cannot
   rank selection/universe against weighting; the #9 contrast (§4) is one uncontrolled cross-composite point.
4. **NOT a resubstitution artifact on direction.** Factor **values** are `Ref(...,1)` (≤ T-1) and the
   composite **direction is a-priori** (value/quality long, low-vol short-high-vol). The IS-IC-fit signs
   **coincide exactly** with those a-priori signs (verified — §3), so the composite carries **no cross-time
   fitted parameter** and no orientation lookahead. (Its *magnitude* is a neutralized cross-sectional
   z-score — also point-in-time.)

**Window isolation:** every input is truncated to **≤ IS_END on load** (asserted) — no 2021-2026 row or
metric enters any computation. The run still *opens* caches that physically contain OOS rows, so it does
**not certify the window pristine**; treat 2021-2026 as **potentially-observed-for-this-design**, and any
future virgin-OOS test of the s3_core book must be generated from strictly-windowed inputs.

---

## 3. Orientation is a-priori — no lookahead (Blocker-2, resolved with evidence)

The composite orients each factor by its economic prior: **value & quality long, low-volatility
short-high-vol** (`APRIORI_SIGNS`). Running `--orientation a_priori` vs `--orientation is_fit` (the harness's
IS-IC-fit signs) over all **342** rebalance dates:

```
max|Δ composite| = 0.00e+00 ;  top-30 selection symmetric-difference = 0  →  IDENTICAL
```

The fitted signs equal the a-priori signs for all 8 factors, so the two orientations produce the **same
composite bit-for-bit**. The composite therefore has **no fitted-on-the-full-window parameter** — the
direction concern is empirically nil. `--orientation walk_forward` (expanding IC, label realized ≤ pday,
a-priori warm-up) is also implemented for completeness; a-priori is the *reported* orientation because it
removes the fit entirely. (Absolute IC/CAGR/Sharpe are still IS-*characterisations*, not deployable
estimates — the experiment is on the design window by construction, with no OOS being predicted.)

---

## 4. Results — three configurations (net-of-cost IS)

Composite IS rank-IC(5d) **+0.057**; median eligible/date **2865**; **342** rebalances. Gate = **fail-closed
screen**: net Sharpe primary (margin ≥ 0.10), MDD-not-worse (≤ +2pp), finite bootstrap tail-mass < 0.10 —
**missing statistical evidence never passes.** TC is descriptive (the TC benchmark is EW-over-eligible; the
PnL Sharpe is absolute vs 000300.SH — **not** cross-cited). "Tail-mass" = paired circular-block bootstrap
`P(Δ*≤0)`, a bootstrap tail probability, **not** a null-calibrated p-value.

**(A) `build0_ref` — a-priori, total σ, uncapped** (reproduces the original run):

| con | CAGR | Sharpe | MDD | eff-N | max_w | TC_full | ΔSharpe vs eqw (tail-mass; 95% CI) |
|---|---|---|---|---|---|---|---|
| eqw | +22.20% | **0.87** | −40.06% | 30.0 | 0.03 | 0.320 | baseline |
| alpha | +21.67% | 0.83 | −40.02% | 26.1 | **0.26** | 0.286 | −0.04 (tm 0.76; [−0.15,+0.06]) |
| sigcomp | +20.96% | 0.80 | −42.22% | **15.5** | **0.26** | 0.262 | −0.07 (tm 0.78; [−0.25,+0.11]) |
| invvol | +22.57% | 0.89 | −39.68% | 27.3 | 0.13 | 0.338 | +0.02 (tm 0.23; [−0.04,+0.09]) |
| sqrtmv | +22.87% | **0.90** | −39.74% | 21.8 | 0.24 | 0.284 | +0.04 (tm 0.33; [−0.12,+0.19]) |
| #9 REPLAY | +30.03% | 1.18 | −33.88% | — | — | — | *different NAMES* (selection, not weighting) |

*The `max_w` column now reports the true per-day **max** single-name weight (the v1 table mistakenly showed
the mean-of-daily-maxes = 0.07; the actual uncapped concentration is **26%**, which a §S3 cap must control.)*

**(B) `build0_cap` — a-priori, total σ, single-name cap 0.05** (the concentration §S3 mandates):

| con | CAGR | Sharpe | MDD | eff-N | max_w | ΔSharpe vs eqw (tm; CI) |
|---|---|---|---|---|---|---|
| eqw | +22.20% | 0.87 | −40.06% | 30.0 | 0.03 | baseline |
| alpha | +21.70% | 0.84 | −40.40% | 27.6 | 0.05 | −0.03 (tm 0.80; [−0.11,+0.04]) |
| sigcomp | +20.78% | 0.82 | −40.01% | 23.2 | 0.05 | −0.05 (tm 0.85; [−0.16,+0.04]) |
| invvol | +22.55% | 0.89 | −39.71% | 27.9 | 0.05 | +0.02 (tm 0.24; [−0.04,+0.09]) |
| sqrtmv | +22.01% | 0.87 | −40.00% | 27.2 | 0.05 | +0.00 (tm 0.50; [−0.08,+0.08]) |

**(C) `build0_res` — a-priori, RESIDUAL σ, single-name cap 0.05** (identical to B except σ, per the GPT contract):

| con | CAGR | Sharpe | MDD | eff-N | ΔSharpe vs eqw (tm; CI) |
|---|---|---|---|---|---|
| eqw | +22.20% | 0.87 | −40.06% | 30.0 | baseline |
| alpha | +21.46% | 0.83 | −41.04% | 27.0 | −0.04 (tm 0.83; [−0.12,+0.04]) |
| sigcomp | +20.78% | 0.82 | −40.01% | 23.2 | −0.05 (tm 0.85; [−0.16,+0.04]) |
| invvol | +22.33% | 0.88 | −39.67% | 27.2 | +0.01 (tm 0.34; [−0.06,+0.09]) |
| sqrtmv | +22.01% | 0.87 | −40.00% | 27.2 | +0.00 (tm 0.50; [−0.08,+0.08]) |

**What the three configs establish (with certainty from the data):**
1. **No signal-proportional construction passes the fail-closed screen in any config** — `screen_passed =
   False` throughout. Every ΔSharpe vs eqw is inside its bootstrap CI (tail-mass 0.23–0.85).
2. **The §S3-faithful `alpha` (∝σz) is below eqw in all four cells** (0.83–0.84 vs 0.87), and **residual σ
   does not rescue it** (build0_res alpha 0.83 = build0_ref alpha 0.83). This directly answers GPT's residual
   question: switching to market-residual vol does not turn the faithful form into a winner here.
3. **A real 5% single-name cap collapses the constructions toward equal-weight** (eff-N rises to 23–28;
   Sharpes converge to 0.82–0.89) — with the concentration §S3 requires, "how you weight the 30 names"
   barely differs from equal-weight. This is *consistent with* a weak weighting lever; it is **not** a proof
   (the CIs are wide).

**What it does NOT establish:** that weighting has no effect (underpowered), or that selection/universe
dominate weighting (neither was varied).

---

## 5. Honest scope, power, and the #9 contrast

- **Power.** On one IS window the paired-bootstrap CIs (e.g. `sqrtmv` [−0.12,+0.19], `sigcomp` [−0.25,+0.11])
  admit values above the +0.10 margin → this experiment **cannot detect** a deployment-relevant ±0.10 Sharpe
  construction effect. The screen is conservative; a null is *not demonstrated*.
- **Scope.** n=1 **non-microcap value+quality+low-vol** book. This is exactly the **well-conditioned case
  §S3 assigns to the OPTIMIZER**, and the *opposite* of the **micro-tail lane** where §S3 *prescribes* light
  construction. **This PoC does not settle the micro-tail lane** — the natural, higher-value next test.
- **The #9 contrast is corroboration, not measurement.** The real #9 dividend book (Sharpe 1.18) differs in
  *names, factors, and K* from this book — an **uncontrolled** cross-composite point, and it sits in the same
  window this doc flags as "value-favorable" (a style-timing confound applied here symmetrically). It
  *corroborates* that "which names" can matter more than "how to weight them" (cleanest internal echo:
  `sqrtmv` 0.90 → #9 1.18 at fixed sqrt-mv weighting, different selection), but the **controlled** selection
  evidence is **external** (the #9 26pp→~1pp deployable-alpha decomposition). Durable memory must not read
  "BUILD-0 measured selection ≫ weighting".
- **"Value-favorable window"** is *asserted*, not verified in this PoC (no HML/value-book relative-return
  artifact computed) — treat as an unverified caveat.
- **Absolute numbers are IS-characterisations**, optimistic, not deployable estimates.

TC framing (Blockers 2/M2, unchanged from v1's fix): headline = **full-eligible calibrated TC** (which
*favors* eqw — eqw 0.320 near the top; the faithful `alpha` *lowers* it, ΔTC −0.034; `invvol` +0.018 is
inside the barely-moves band). **Holdings-only TC is a within-book diagnostic**, a **structural near-identity**
for any ∝signal weight (`invvol ≈ 1.000` because the benchmark term `σ/N_elig` is tiny — **not** an exact
algebraic 1, and **not** an edge). Never used to select a construction.

---

## 6. Recommendation for BUILD-0

- **Do not build the construction stack expecting a weighting-driven *return* lift for this class of book.**
  The evidence does not support it; but the evidence is INCONCLUSIVE, so this is a "no positive signal", not
  a proof against construction.
- **The two properly-scoped follow-ups** (not run here): (i) a **fully-§S3-constrained** constructor
  (portfolio-level neutrality + industry caps + ADV + turnover/cost penalties) with a residual-σ risk model,
  and (ii) — highest value — a **micro-tail-lane** construction test, the lane §S3 actually targets.
- **If a construction/risk layer is built, build it for RISK, not return** (MDD control, neutralization,
  attribution), unlevered/fail-closed. The 5% cap already shows the constructions are ~risk-neutral vs eqw
  here (no MDD win worth the complexity).
- **The selection lever must be tested by *varying selection*** (it was not here); cite the external #9
  26pp→~1pp result for that, not this PoC.

---

## 7. GPT §10 REWORK response — every Blocker/Major/Minor, and its disposition

| id | GPT finding | disposition |
|---|---|---|
| **B1** | "no sealed OOS spent" unprovable — caches span 2021-26 | **Fixed.** `_setup()` truncates all inputs to ≤ IS_END + asserts (test-pinned); claim reworded to "compute IS-only, but caches opened → 2021-26 potentially-observed, not virgin". |
| **B2** | full-window IC-fit direction = temporal lookahead | **Resolved with evidence.** Signs are **a-priori economic**; the fit signs *coincide* → `a_priori`==`is_fit` bit-for-bit (§3). No fitted parameter, no lookahead. `walk_forward` also implemented. |
| **B3** | `alpha` isn't the §S3 constructor; `max_w` table bug | **Fixed.** `alpha` relabeled an *unconstrained σ-proxy* (§2.1); the §S3 gaps enumerated; `--max-weight` + `--sigma residual` added and **tested** (§4B/C); table now shows true **max** (26%) via mean/p95/max. |
| **B4** | four-layer: signal-layer price gate | **Disclosed.** The `broad` mask uses `cr.notna()` at pday (a PIT last-known-price gate), applied **identically** to all 5 → does not bias the weighting delta; stated, not over-claimed as pristine four-layer. |
| **B5** | verdict over-claimed (rejected-null → "weak lever") | **Fixed.** `premise_holds`→`screen_passed`; status **INCONCLUSIVE_no_greenlight**; gate is **fail-CLOSED** (missing tail-mass never passes; MDD guard; margin). |
| **M1** | bootstrap mislabeled p-value; gate fail-open | **Fixed.** Relabeled **tail-mass** (circular-block); gate now `np.isfinite(tm) and … and tm < FWER_ALPHA` — missing evidence fails closed. Familywise threshold noted. |
| **M2** | `invvol TC_hold=1` not a strict identity | **Fixed.** Reworded "structural near-identity (0.9997) because the benchmark term σ/N is tiny", never "=1 by construction" / never "best". |
| **M3** | not reproducible; no evidence manifest | **Fixed.** `assemble` emits an **evidence manifest** (git SHA, input/output/dep SHA-256, provider/calendar ids, CLI config, `evidence_class=NON_EVIDENTIARY_IS_DESIGN_PROBE`); the **full local dep chain is content-addressed** (`frozen_local_deps_sha256`); `guorn_optimize_09.py` committed. `manifest_complete=True`. |
| **M4** | PoC didn't measure selection/universe | **Fixed.** §2 (NOT #3), §5: selection/universe not varied; #9 = one uncontrolled corroborating point; external 26→1pp is the controlled selection evidence. |
| **Minor-1** | mean columns hide peaks | **Fixed.** eff-N/max_w reported mean/p95/**max**. |
| **Minor-2** | "value-favorable" unbound | **Fixed.** Flagged as an unverified caveat (§5). |

**Verified-clean (GPT):** 342 rebalances × identical 30-name set per date; `000001.SZ`/`000300.SH` code
forms; weights sum to 1, no leverage; `sqrtmv` bit-exact vs the cached baseline; factor-library PIT tests 25
passed; ≥53 delisted names in-universe (no survivorship filter); all v1 numbers reconciled.

---

## 8. Guardrails & reproduce

IS-only (2014-2020); **no OOS path exists in the script**; inputs truncated ≤ IS_END; fully reversible;
reused the trusted harness (no edits); metrics via `research_utils.goal_metrics`; evidence manifest per run;
19 tests pass. Every absolute number is an **IS design-stage** figure (evidence_class NON_EVIDENTIARY).

```bash
py=venv/Scripts/python.exe
$py workspace/scripts/build0_tc_poc.py --verify-orientation                                   # a_priori==is_fit
$py workspace/scripts/build0_tc_poc.py --all --tag build0_ref --orientation a_priori --sigma total    --max-weight 1.0
$py workspace/scripts/build0_tc_poc.py --all --tag build0_cap --orientation a_priori --sigma total    --max-weight 0.05
$py workspace/scripts/build0_tc_poc.py --all --tag build0_res --orientation a_priori --sigma residual --max-weight 0.05
$py -m pytest tests/workspace/test_build0_tc_poc.py tests/workspace/test_build0_window_isolation.py -q
# artifacts: workspace/outputs/guorn_parity/optimize09_cache/{build0_*_tc.json,build0_*_results.json,sched_build0_*_*.json,net_build0_*_*_is.parquet}
```
