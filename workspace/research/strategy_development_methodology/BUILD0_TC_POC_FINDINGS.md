# BUILD-0 — weight-construction screen — FINDINGS (v3, finalized NON-EVIDENTIARY)

> **Status:** FINALIZED as a **NON-EVIDENTIARY design probe** (2026-07-12). GPT-5.5 Pro §10 returned
> **REWORK twice**; the correctness findings are fixed and the over-claims removed, and — by explicit user
> decision — this PoC is **recorded as a non-evidentiary negative screen, NOT pursued to a formal SHIP.**
> The formal construction experiment (walk-forward orientation + four-layer-clean universe + full §S3
> constructor, built through the sanctioned windowed door) is **deferred to a properly-scoped BUILD-0b**
> (§7). IS-only (2014-2020), reversible. Script: [build0_tc_poc.py](../../scripts/build0_tc_poc.py); tests:
> [test_build0_tc_poc.py](../../../tests/workspace/test_build0_tc_poc.py) +
> [test_build0_window_isolation.py](../../../tests/workspace/test_build0_window_isolation.py) (19 passed).

---

## 1. What is safe to record (the verdict)

**BUILD-0 is a non-evidentiary, post-hoc, IS proxy screen. Across three configurations, none of the nine
signal-proportional proxy comparisons produced a positive result under an unadjusted screen — this means
only that there is NO positive evidence from re-weighting a fixed top-30 book, nothing more.** It does not
establish that weighting is a weak lever, does not rank selection/universe against weighting (neither was
varied), and does not test the §S3 constructor (only unconstrained σ-proxies plus a single-name cap were
tested). Net returns are bounded to 2014-2020; the reported RankIC now uses **only labels realized ≤ IS_END**
(the earlier version mistakenly included a `fwd_5d` label realizing 2021-01-07 — fixed, §7 B1); but the run
opened caches that physically contain 2021-2026 rows, so **that window is potentially-observed and is not a
virgin OOS for this design.**

**The practical takeaway for the roadmap question ("build the construction stack?"):** there is **no positive
signal** that a lighter signal-proportional construction beats equal-weight for this class of book — so this
PoC provides **no evidence to greenlight** the stack. It also provides no evidence *against* construction.
The question is properly answered by the deferred formal **BUILD-0b**, not by this probe.

**Explicitly NOT supported by this experiment (do not record these):** "weighting is weak", "the §S3 alpha
failed", "residual σ cannot rescue construction", "selection/universe > weighting", "build construction only
for risk", "no sealed OOS was spent".

---

## 2. What the experiment is, and the four things it is NOT

The methodology's §1.1 prior: deployable return is lost at the **construction** step (`rank→top-K→equal-weight`
discards the cardinal signal — a transfer-coefficient collapse). This probe asks, cheaply, whether a lighter
signal-proportional construction *shows any sign* of beating equal-weight on net PnL, over a **fixed** top-30
name set (weights the only thing varied), identical event-driven envelope (0.2%/side, slippage 0,
`volume_limit=0.10`, `hold_on_limit_up`, Model-I 5-day rebalance, 000300.SH, ¥1M, total-return).

| construction | weights | note |
|---|---|---|
| `eqw` | `1/K` | baseline; no σ, no orientation dependence |
| `alpha` | `∝ σ·z` | Grinold *shape*; an **unconstrained σ-proxy**, NOT the §S3 constructor |
| `sigcomp` | `∝ (comp − min + ε)` | score-proportional (harness `wmode="signal"`) |
| `invvol` | `∝ z/σ` | MV-diagonal *form*; holdings-TC ≈ 1 is a structural near-identity, not an edge |
| `sqrtmv` | `∝ √circ_mv` | #9's own weighting (size tilt); a reuse cross-check, not a signal-prop proxy |

**It is NOT:**
1. **NOT the §S3 light constructor.** Only a single-name cap (`--max-weight`) and a one-factor-market
   residual σ (`--sigma residual`) are added. §S3 further mandates portfolio-level size/industry neutrality,
   industry caps, ADV, turnover/cost penalties, lot rounding, capacity — **all untested**.
2. **NOT an equivalence test, and unadjusted.** "None passed" is *absence of a detected effect*, not evidence
   of absence. `tail_mass` is a bootstrap tail probability, **not** a null-calibrated p-value, and there is
   **no familywise (FWER) control** across the 9 comparisons.
3. **NOT a measurement of selection or universe.** Both are held fixed. The #9 book (Sharpe 1.18) differs in
   names/factors/K and lives in the same window — an uncontrolled contrast, recorded here only as background.
4. **A known-limited orientation & universe (see §7 B2/B4).** The composite direction is a-priori economic
   but **IS-informed** (the a-priori sign map was written after the fitted signs existed — a retrospective
   consistency check, not a pre-registered artifact), and the reused harness applies a **signal-layer
   price-availability gate** (a four-layer deviation). Both are documented limitations of a non-evidentiary
   probe, not claimed clean.

---

## 3. Results — three configurations (net-of-cost IS)

Composite IS rank-IC(5d) **+0.057** (IS-fitted, optimistic; labels realized ≤ IS_END); 342 rebalances; median
eligible/date 2865. Screen (unadjusted, fail-closed): net Sharpe margin ≥ 0.10 **and** MDD-not-worse-by->2pp
**and** finite bootstrap tail-mass < 0.10; family incomplete unless all members present. Every `screen_passed
= False`; status `INCONCLUSIVE_no_greenlight`.

**(A) `build0_ref` — a-priori(IS-informed), total σ, uncapped:**

| con | CAGR | Sharpe | MDD | eff-N | max_w | ΔSharpe vs eqw (tail-mass; 95% CI) |
|---|---|---|---|---|---|---|
| eqw | +22.20% | 0.87 | −40.06% | 30.0 | 0.03 | baseline |
| alpha | +21.67% | 0.83 | −40.02% | 26.1 | **0.26** | −0.04 (0.76; [−0.15, +0.06]) |
| sigcomp | +20.96% | 0.80 | −42.22% | 15.5 | **0.26** | −0.07 (0.78; [−0.25, +0.11]) |
| invvol | +22.57% | 0.89 | −39.68% | 27.3 | 0.13 | +0.02 (0.23; [−0.04, +0.09]) |
| sqrtmv | +22.87% | 0.90 | −39.74% | 21.8 | 0.24 | +0.04 (0.33; [−0.12, +0.19]) |

**(B) `build0_cap` — a-priori, total σ, cap 0.05** *(re-run with the corrected cap function)*:  eqw 0.87 · alpha 0.84 · sigcomp 0.85 · invvol 0.89 · sqrtmv 0.87 — ΔSharpe vs eqw: alpha −0.03 (tm 0.79; [−0.10,+0.04]) · sigcomp −0.02 (0.68; [−0.10,+0.06]) · invvol +0.02 (0.24; [−0.04,+0.08]). `screen_passed=False` for all.

**(C) `build0_res` — a-priori, RESIDUAL σ, cap 0.05** *(identical to B except σ)*:  eqw 0.87 · alpha 0.84 · sigcomp 0.85 · invvol 0.88 · sqrtmv 0.87 — ΔSharpe vs eqw: alpha −0.03 (tm 0.82; [−0.12,+0.04]) · sigcomp −0.02 (0.68; [−0.10,+0.06]) · invvol +0.01 (0.32; [−0.06,+0.09]). `screen_passed=False` for all.

**Reading (safe):** across the 9 signal-proportional comparisons, **none is a screen-positive**. All ΔSharpe
percentile intervals **include zero**; among them **only uncapped `sigcomp`'s upper bound (+0.11) exceeds
+0.10** — the rest sit below the +0.10 margin. These are **post-hoc, unadjusted percentile intervals**, so
they support **neither** an equivalence claim **nor** a roadmap change; the only recordable fact is that no
tested proxy produced a screen-qualified positive. (The uncapped `alpha`/`sigcomp` single-name weights reach
**26%** — the v1 table wrongly showed the 7% *mean-of-daily-maxes*; the column now reports mean/p95/max.)

---

## 4. Scope & power

- **Power.** On one IS window the paired-bootstrap intervals are wide → the screen **cannot detect** even a
  deployment-relevant ±0.10 Sharpe effect. Absence of a screen-positive is not evidence of absence.
- **Scope.** n=1 non-microcap value+quality+low-vol book — the well-conditioned case §S3 assigns to the
  *optimizer*, the opposite of the **micro-tail lane** where §S3 prescribes light construction (**untested**).
- **"Value-favorable window"** is an *unverified* caveat (no HML/value-book relative-return artifact computed).
- Absolute IC/CAGR/Sharpe are **IS design-stage** figures (evidence_class `NON_EVIDENTIARY_IS_DESIGN_PROBE`).

TC (descriptive only, never in the gate): headline full-eligible calibrated TC *favors* eqw (0.320 near the
top; the σ·z proxy *lowers* it, ΔTC −0.034). Holdings-only TC is a within-book diagnostic and a **structural
near-identity** (≈0.9997) for any ∝signal weight — not an edge, never used to select a construction.

---

## 5. GPT §10 round-2 disposition (REWORK → finalize non-evidentiary)

Round-1 (5B/4M/2m) and round-2 (5B/4M/1m) both REWORK. Every **correctness** finding is fixed; every
**over-claim** is removed; the two findings that would require converting this reused-harness probe into a
formal experiment are **documented as known limitations** and **deferred to BUILD-0b** (per the user decision
to finalize non-evidentiary rather than pursue SHIP).

| id | round-2 finding | disposition |
|---|---|---|
| **B1** | `fwd_5d` label at 2020-12-30 realizes 2021-01-07 → RankIC not IS-isolated | **FIXED.** IC/orientation now use only dates whose 5d label realizes ≤ IS_END (`_realization_date`); `max_ic_label_realization` recorded; test-pinned. Claim reworded (net bounded 2014-2020; window potentially-observed, not virgin). |
| **B2** | a_priori==is_fit is a retrospective consistency check, not pre-registration; walk-forward changes 177/342 dates' selection | **DISCLOSED + DEFERRED.** Recipe relabeled `a_priori_is_informed` (§2.4); `walk_forward` is *implemented* but its **net results are not run** here — that (or a bound pre-run direction artifact) is a **BUILD-0b** requirement. Not claimed a-priori-clean. |
| **B3** | "§S3-faithful" language; only 3 cells run | **FIXED (language) + DEFERRED (coverage).** All "§S3-faithful" phrasing removed; `alpha` is an *unconstrained σ-proxy*. Only 3 cells (uncapped/total, capped/total, capped/1-factor-residual) were run; uncapped/residual + full §S3 = BUILD-0b. |
| **B4** | signal-layer `cr.notna()` price gate = four-layer violation; "last-known-price" was false | **DISCLOSED + DEFERRED.** Described accurately: the reused harness drops NaN-price (suspended) names at the signal layer (not last-known-price), applied **identically to all 5** (does not bias the weighting comparison). The four-layer-clean universe (forward-fill + keep suspended in ranking + reserves) is a **BUILD-0b** fix. |
| **B5** | rejected-null over-claimed as "weighting is weak" | **FIXED.** `screen_passed`, INCONCLUSIVE, fail-closed at construction **and** family level (missing member → incomplete, never a pass). Verdict claims only "no positive evidence". |
| **M1** | gate not familywise; fail-open on missing member | **FIXED.** Relabeled *unadjusted exploratory screen* (no FWER claim); family fail-closed on a missing member (test-pinned). |
| **M2** | invvol TC "=1" | **FIXED.** "structural near-identity (≈0.9997)", never "best". |
| **M3** | manifest partial; `bool(pinfo)` fail-open; MLflow optional; git dirty | **FIXED (honesty) + partial.** Renamed a **partial reproducibility bundle** (not a durable manifest); requires non-empty provider ids + a **clean commit** for `reproducible_from_clean_commit`; added reference-data + full-config hashes; expanded inputs. Canonical-metrics / MLflow-mandatory + external result-root hash = BUILD-0b. |
| **M4** | selection/universe not measured | **FIXED.** Stated throughout; #9 is background, not a measurement. |
| **B3-cap bug** | `_cap_simplex` fail-open (returned max=1.0; uniform on infeasible) | **FIXED.** Water-fills to every headroom coord (incl. zeros), raises `InfeasibleCapError`, asserts sum & cap; capped configs re-run with the fix; test-pinned. |
| **Minor** | "MDD-not-worse"; "value-favorable" unbound; mean columns | **FIXED.** "MDD no more than 2pp worse"; value-favorable flagged unverified; mean/p95/max columns. |

**GPT's confirmed-clean items (round 2):** all JSON numbers reconcile with the nets; 342 rebalances × same
top-30 per date; `000001.SZ`/`000300.SH` code forms; weights sum to 1, no leverage; nets end 2020-12-31;
residual-σ formula correct (max error 5.7e-9 vs OLS); ≥53 delisted names in-universe; factor-library PIT
tests pass.

---

## 6. BUILD-0b — the deferred formal experiment (if construction is prioritized)

Build a **fresh, formal** experiment (do NOT keep patching this reused-harness probe): walk-forward (or a
pre-registered) orientation with net results; a **four-layer-clean** universe (declared PIT membership,
forward-filled last-known price for any floor, suspended names retained in ranking, tradability enforced only
at execution with reserves); the **full §S3 constructor** (portfolio neutrality + industry caps + ADV +
turnover/cost penalties, residual-σ risk model); routed through the **sanctioned windowed door**
(`qlib_windowed_features` / an `IsWindowedPanel` with label-realization ≤ is_end) with a durable evidence
manifest and canonical `src/result_analysis` metrics + mandatory MLflow; and — the highest-value target — a
**micro-tail-lane** test (the lane §S3 actually prescribes light construction for). Only such an experiment
can support a construction *conclusion*.

---

## 7. Guardrails & reproduce

IS-only (2014-2020); **no OOS path exists in the script**; inputs truncated ≤ IS_END on load (label-realization
boundary enforced for ICs); fully reversible; reused the trusted harness (no edits); 19 tests pass; every
number is `NON_EVIDENTIARY_IS_DESIGN_PROBE`.

```bash
py=venv/Scripts/python.exe
$py workspace/scripts/build0_tc_poc.py --verify-orientation                                    # a_priori==is_fit (retrospective check)
$py workspace/scripts/build0_tc_poc.py --all --tag build0_ref --orientation a_priori --sigma total    --max-weight 1.0
$py workspace/scripts/build0_tc_poc.py --all --tag build0_cap --orientation a_priori --sigma total    --max-weight 0.05
$py workspace/scripts/build0_tc_poc.py --all --tag build0_res --orientation a_priori --sigma residual --max-weight 0.05
$py -m pytest tests/workspace/test_build0_tc_poc.py tests/workspace/test_build0_window_isolation.py -q
```
