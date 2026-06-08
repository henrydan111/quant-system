# Cross-Review for GPT 5.5 Pro — Report-Factor Expansion DESIGN (`report_rc` → factors)

**Date:** 2026-06-08.
**Repository:** https://github.com/henrydan111/quant-system
**Scope:** review a *design plan*, not code. We are adding sell-side **analyst-forecast** data
(`report_rc`) to an A-share quant factor platform as PIT-correct, registry-governed Qlib factor fields.
This is a **Phase-0 design review BEFORE coding** — we want adversarial scrutiny of (1) the backend
materialization design (the novel/hard part), (2) the PIT correctness, (3) the architectural line
between the backend and the Qlib-expression layer, and (4) the phasing. Full plan in repo:
`workspace/research/data_expansion/report_factor_expansion_plan.md`.

---

## 0. Context GPT needs (you have not seen this repo)

- **System:** Tushare → Parquet → **PIT ledger → Qlib provider** → factor catalog → backtest. The
  iron rule (CLAUDE.md §3.2 / src/system.md §0): **a new dataset becomes a factor ONLY after it is
  materialized into the PIT ledger + Qlib provider by `pit_backend` and registered in
  `field_status.yaml`; factors are then Qlib expression strings computed via `compute_factors`.**
  Hand-rolling PIT alignment from raw parquet is forbidden (it caused two prior lookahead disasters).
- **Why this review exists:** a first attempt computed analyst-consensus features in a sandbox script
  by reading raw parquet + hand-rolling the PIT alignment — a rule violation, now quarantined. It
  *suggested* one feature (`eps_diffusion` = analyst EPS-revision breadth) is a strong, orthogonal,
  tradeable signal (IS RankICIR ~0.64, long-only +5.5%/yr), **but that is an untrusted HYPOTHESIS** (no
  provider-bounds/delist masking → likely survivorship inflation). This plan re-derives it compliantly.
- **The `report_rc` data:** 2.87M rows, 2010-2026, ~5,600 stocks. One row = **(stock × analyst × forecast
  quarter)**. Columns: `ts_code, report_date, org_name, author_name, quarter (e.g. 2026Q4), eps, rating,
  tp, np, …`. Properties we verified: rating is **sticky** (A-share analysts ~never change a rating →
  recommendation-change signals are dead, 2% coverage); `tp` is **unit-corrupted** (e.g. 9600 targets);
  coverage is **size-tilted** (large-cap ~95%, small-cap ~22-53%); a forecast's visibility date is
  `report_date` (publication), anchored PIT via `effective_date = strictly_next_open_trade_day(report_date)`.
- **Precedent we will mirror:** `pit_backend._materialize_stk_holdertrade` — a custom materializer that
  reads an event PIT ledger, aggregates per `(qlib_code, effective_date)`, and writes per-day Qlib bins
  (NaN between events), namespaced via `EVENT_LIKE_DAILY_FIELD_PREFIX` to avoid shadowing `$close` etc.
- **Downstream gates (already exist):** `field_status.yaml` (quarantine→audit→approve), the
  factor-library PIT-safety lint (every `$field` must sit inside `Ref(...)`), the `factor_lifecycle`
  IS-only screen (draft→candidate), and a single sealed-OOS shot (candidate→approved).

---

## 1. TL;DR — what to check

| # | Decision | Risk | What to verify |
|---|---|---|---|
| A | **Where to split backend vs Qlib layer** — precompute a windowed *consensus* field, OR materialize *atomic daily revision-event bins* and let Qlib operators (`Sum(Ref(...),W)`) do the windowing | **high / architectural** | Which is correct given "factors = Qlib expressions"? Can the per-analyst stateful part be minimized into the materializer and the windowing pushed to Qlib? |
| B | **Rolling-consensus materializer** (per-stock event-driven state: insert latest-per-analyst vote on `effective_date`, expire after AGE_DAYS, emit daily) | **high** | Any subtle lookahead? Determinism (P0-4 tie-break)? Performance over daily × full history × 5,600 stocks? |
| C | **FY1 target-selection rule** (consensus EPS refers to the nearest not-yet-reported annual) | medium | PIT-correctness of the Q4-roll-forward; does it ever peek at a not-yet-disclosed actual? |
| D | **`report_date` as the PIT anchor** | medium | Is `next_open(report_date)` enough, or must the materializer bake an ingestion-lag buffer (a separate backfill canary is verifying this)? |
| E | **Independent-recompute parity** as the materializer's test oracle | medium | Valid, or circular? (Same method we used for the Wave-1 statement promotion.) |
| F | **Candidate field set + "materialize a set, let the screen decide"** | low | Right features? Missing any (revision acceleration, coverage initiation)? Is not-pre-selecting correct? |

---

## 2. The plan in brief
Six phases: (0) pre-register + this design review; (1) `DatasetSpec` + build `data/pit_ledger/report_rc/`
with `effective_date`; (2) custom materializer → `$report_rc__*` daily bins + namespacing; (3) staged
provider rebuild + `field_status.yaml` quarantine→approve (+ coverage/parity audit); (4) catalog factors
as `Ref($report_rc__<f>, 1)`; (5) **compliant `factor_lifecycle` IS screen** (this REPLACES the tainted
pilot — `eps_diffusion` is confirmed or falsified here, trustworthy); (6) sealed-OOS or ML features via
`compute_factors`. Candidate fields: `eps_diffusion` (lead), `eps_revision`, `rating_revision`,
`eps_dispersion`, `n_analysts` (size-proxy control), `eps_fy1` (level control). Defer `tp` (corrupt);
drop `rating_diffusion` (dead).

---

## 3. Design decisions we want challenged

**Q-A (most important — the architectural line).** A windowed cross-analyst consensus is NOT a pure
Qlib expression: it needs **per-analyst dedup** (one vote = latest forecast per analyst) + **per-analyst
revision direction** (latest vs prior) — stateful, cross-time, per-analyst logic Qlib's operator engine
can't express. Two designs:
  - **(A1) Precompute the windowed consensus** (`$report_rc__eps_diffusion` already windowed+aged) in the
    materializer; the factor is just `Ref($report_rc__eps_diffusion, 1)`. Simple factor, heavy/opaque
    materializer (window + age baked into the bin → re-materialize to change them).
  - **(A2) Materialize ATOMIC daily event bins** — the materializer does only the per-analyst-stateful
    part (emit, per `effective_date`, the **net up/down EPS-revision counts** and **active-analyst
    count**); then the *factor* is a Qlib expression that does the windowing:
    `eps_diffusion ≈ (Sum(Ref($report_rc__eps_up,1),W) − Sum(Ref($report_rc__eps_dn,1),W)) /
    Sum(Ref($report_rc__eps_active,1),W)`. Keeps windowing in the sanctioned factor layer; window length
    becomes a factor hyperparameter (no re-materialize); matches the `stk_holdertrade` per-event-day
    precedent more closely.
  We lean **A2**. Is that right? Is there a leakage or correctness trap in A2 (e.g., the diffusion
  denominator, or `cs_rank` on a discrete ratio)? Or is A1 safer given the FY1/dedup complexity?

**Q-B (rolling-state correctness).** For the per-analyst diff (needed in BOTH designs), the materializer
keeps, per stock, each analyst's most recent FY1 EPS and compares the next one to it to emit an up/down
event on the new forecast's `effective_date`. Is an event-driven per-stock state machine the right shape?
Any lookahead risk in "emit on `effective_date`"? It is strictly visible (anchor is `next_open`), but we
want your eyes on the boundary. Determinism: we will reuse the P0-4 `_src_file`/`_src_ordinal` tie-break.

**Q-C (FY1 rule).** Consensus EPS-level/revision features target the **nearest not-yet-reported annual**
(`quarter == "{fiscal_year}Q4"`). The rule must never compare against a forecast for a period whose
actual is already public (that would mix horizons). What's the cleanest PIT-correct rule for choosing the
target period as-of T, and the Q4 roll-forward (when does FY1 advance to next year)?

**Q-D (anchor sufficiency).** We anchor on `next_open(report_date)`. A parallel backfill canary is
checking whether Tushare backfills `report_date` (which would break PIT). If it shows a multi-day
ingestion lag, should the materializer bake a fixed lag buffer (anchor at `report_date + Kbars`), or is
that over-engineering vs just `Ref(...,1)` on top of `next_open`?

**Q-E (parity oracle).** Phase-2's correctness test reimplements the consensus from scratch in pandas off
the ledger (importing none of the materializer's code) and compares cell-by-cell to `D.features`. You
endorsed this for the Wave-1 statement fields. Is it equally valid here given the extra windowing logic,
or does the shared dependency on the ledger + the window definition make it circular?

**Q-F (field set & non-selection).** We deliberately materialize a SET and let the compliant screen pick
winners (rather than pre-selecting `eps_diffusion` from the tainted pilot). Agree? Any high-value analyst
feature we're missing — e.g. **revision acceleration** (Δ diffusion), **coverage initiation** (first-time
coverage event), **forecast horizon/age**, **dispersion-change**?

---

## 4. Open risks / honest unknowns
1. The compliant screen may yield a **weaker or null** `eps_diffusion` once provider-bounds masking
   removes the survivorship inflation the raw-read pilot allowed. We treat a null as a valid outcome — is
   that the right posture, or should we predefine a kill-threshold now to avoid post-hoc rationalization?
2. **Discreteness:** diffusion has a large point-mass at 0 → must be `cs_rank`/sign-based downstream, not
   quantile-sorted. Does materializing a discrete field then cross-sectionally ranking it introduce any
   pathology?
3. **Coverage is size-tilted** (the field only exists on ~covered, larger names) → the factor implicitly
   ranks a sub-universe. Should the materializer emit NaN off-coverage (let the factor rank within
   coverage), or is there a better neutral-fill convention?
4. **Cost/perf:** a full provider rebuild is expensive; we basket-test first. Any cheaper validation path?

## 5. Consolidated questions for GPT
1. **(A)** A1 (precomputed windowed field) vs A2 (atomic event bins + Qlib-operator windowing) — which,
   and any leakage/correctness trap in the chosen one?
2. **(B)** Is the event-driven per-stock revision-state machine correct + lookahead-free, and how would
   you test the `effective_date` emission boundary?
3. **(C)** The cleanest PIT-correct FY1 target-selection + Q4 roll-forward rule?
4. **(D)** Bake an ingestion-lag buffer into the anchor, or is `next_open(report_date)` + `Ref(...,1)` enough?
5. **(E)** Is the independent-recompute parity a valid oracle for a *windowed* derived field?
6. **(F)** Right candidate field set? Missing features? Is "materialize a set, let the screen decide" right?
7. **(risk-1)** Predefine a kill-threshold for the compliant screen now, or accept a null post-hoc?
8. **Sequencing:** is the "smallest first slice" (pre-register → ledger → materializer + parity on a small
   basket, NO full rebuild) the right way to de-risk before the expensive provider rebuild + screen?

*Companion: the full plan (`report_factor_expansion_plan.md`), the quarantined pilot findings
(`WAVE1A_PILOT_FINDINGS.md`, method-reference only), and the precedent materializer
(`src/data_infra/pit_backend.py::_materialize_stk_holdertrade`).*
