# Cross-Review Brief — Roadmap to Bring All Remaining CICC Factors into Formal Evaluation (2026-06-13)

**For:** GPT 5.5 Pro cross-review. You have NOT seen the conversation that produced this — this brief is
self-contained. **Your job:** adversarially review the ROADMAP in
[REMAINING_CICC_FORMAL_EVAL_PLAN.md](REMAINING_CICC_FORMAL_EVAL_PLAN.md) (Chinese): is the wave
decomposition correct, the prerequisite/sequencing right, the data-workflow compatibility sound, the
scope honest, and the multiple-testing implication of mass factor registration adequately handled?
Concrete failure scenarios > generic praise.

---

## 1. System context (10 lines)

A-share quant research platform (Tushare + Qlib). Factors live in a catalog (208: 184 base + 20
composite + 4 industry-relative), each a registry row with a status ladder: `draft` → (human-signed
**IS-only walk-forward gate**, leak-proof: factor date AND label-realization date ≤ is_end) →
`candidate` → (**single-shot sealed OOS**, seal spent on attempt) → `approved`. Evidence NEVER changes
status (resolve-but-label); only the two human gates do. IS window 2010-2020, 20-day horizon, deciles.

We are replicating three CICC (中金) sell-side factor handbooks (基本面/价量/高频) against their
published truth tables. A **universe-coupled evaluation design** was just approved through three GPT
review rounds (CHANGES REQUIRED → APPROVE): universe enters factor-evaluation IDENTITY not computational
identity; every factor is auto-evaluated across 7 universes (univ_all / csi300 / csi500 / csi1000 /
microcap / growth / liquid_top300) on entry; a unified TaintLedger + FactorDomainClaim model;
multiplicity-tiered IS bar (clean singleton-primary = original bar, post-hoc/multi-domain = permutation
max-stat); thin-domain + effective-window hard floors.

## 2. What's done

- 18 fundamental CICC factors faithfully replicated + registered (Phase D5), truth-certified
  (exact-tier non-size IC 99% within tolerance vs the handbook over 2010-2022 × 3 domains).
- Full 208 × 7-universe evidence matrix just ran (1,449 units, zero errors).
- The factor×universe claim/taint infrastructure (F1) landed.

## 3. The roadmap being reviewed (summary of the Chinese doc)

**Goal:** bring ALL ~180 remaining *replicable* CICC factors into the formal pipeline (draft → 7-domain
matrix → IS gate → candidate → sealed OOS → approved). Ordered by **constraint readiness** (data/field/
operator), not factor count. 68 high-freq factors are explicitly OUT (need minute/tick data we don't have).

**Three cross-cutting prerequisites (block mass formal eval):**
- **P-OP**: operator library — CICC needs new operators (amplitude-conditional rolling sum, path-adjusted
  momentum, info-discreteness, cross-sectional/time-series rank momentum, upper/lower-shadow families,
  rolling-regression residuals). Needed by ~60 price-volume + 2 fundamental.
- **P-GATE**: the universe-coupled IS gate (declared-domain adjudication + tiered max-stat bar + thin/
  effective-window floors) is DESIGNED but NOT yet wired into the lifecycle gate (only F1 foundation done).
- **P-CAL**: max-stat permutation calibration (block-permutation null, window-matched).

**Waves (by data readiness):**
| Wave | factors | unlock |
|---|---|---|
| E1 price-volume | ~135 | zero new data (OHLCV + already-approved cyq_perf/moneyflow/hk_hold/margin) + P-OP operators |
| D-COMP composites | ~13 | zero data (composites of existing) |
| D4a balance-sheet D-deltas | ~10 | **register-only** (q0-q4 bins verified already materialized) |
| D4b OCF-YoY | 2 | provider rebuild (cashflow slots q5-q7 missing) |
| D6 analyst consensus-levels | ~11 | extend report_rc materializer (report_rc PIT verified from 2010) + rebuild |
| D7 new-endpoint | ~12 | new Tushare endpoints (exec comp / institutional holdings / top-holders); some droppable |

**Data-workflow compatibility (verified per-bin):** two-tier cost — (A) bin-exists → register-only
(field_status + approval YAML + parity, no rebuild); (B) bin-missing → materialize + ledger/provider
rebuild. Verified: E1 alt-data fields are servable bins NOW (cyq_perf__*, buy_*_amount, net_mf_amount,
hk_hold ratio, margin rzye/rqye) + approved; D4a D-delta bins (q0-q4) already exist → register-only
(corrected from "needs rebuild"). Genuine rebuilds only: D4b, D6, D7 — all on the standard
`build_qlib_backend --mode update --datasets X` path; recommend merging into ONE incremental build.

## 4. Specific review asks (attack these)

1. **Mass-registration multiple testing.** Registering ~180 new factors grows the catalog 208→~390 and
   the matrix to ~2,730 units. Every new draft auto-runs 7-domain evidence. Does mass registration of a
   whole sell-side handbook create a multiplicity problem the per-(factor,universe) ledger doesn't
   capture — i.e., "we replicated 250 published factors and 12 passed sealed-OOS" is itself a
   garden-of-forking-paths unless the handbook-as-a-whole is treated as one family? Should CICC
   replications carry a handbook-level taint / family multiplicity scope from the start?
2. **Operator correctness risk (P-OP).** Several CICC factors need bespoke operators (amplitude-rank
   conditional sums, rolling OLS residuals). A subtly wrong operator silently produces a plausible-but-
   wrong factor that could pass IS. What verification should gate P-OP operators before any factor built
   on them is allowed into formal evaluation (beyond the existing PIT-safety lint)?
3. **Sequencing.** Is "P-OP + P-GATE first, then waves" right? Or should a small E1 slice go through the
   EXISTING univ_all gate first (interim) to de-risk the operators before P-GATE lands? Trade-off:
   interim univ_all evidence becomes observed-domain taint under the new gate.
4. **D6 analyst consensus reconstruction.** report_rc is per-broker forecast detail; we'd reconstruct
   FY1 consensus levels at report_date+1 and materialize them. report_date+1 PIT was validated at the
   LEVEL layer (corr +0.997 vs a genuine-PIT oracle; reconstruction LESS accurate than oracle = no
   lookahead). Is materializing a *reconstructed consensus* (vs a vendor-provided consensus) a PIT or
   methodological risk we're underweighting?
5. **Scope honesty.** Is excluding the 68 high-freq factors (no minute/tick data) the right call, or is
   there a daily-data proxy worth attempting for any of them? Is "~180 replicable" an honest count or
   are we over-claiming replicability for price-volume factors whose CICC construction we can only
   approximate?
6. **Anything else** — missed pipeline dependencies, a cheaper ordering, a governance gap.

## 5. Not under review

The universe-coupled design itself (approved over 3 prior rounds), the 10-group standard, seal
mechanics, the report_rc 2010-PIT validation. Context only. Focus on the roadmap §1-8.
