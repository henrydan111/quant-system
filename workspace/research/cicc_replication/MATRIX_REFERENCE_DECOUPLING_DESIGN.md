# Matrix-evaluation reference-set decoupling — design + GPT-review brief

**Goal:** stop the unified-eval matrix methodology from being hostage to the live approved-factor set,
so (a) approving/revoking ANY factor stops forcing a full ~1568-pair re-baseline, and (b) the CICC
price-volume campaign (E1a–h, ~100+ factors) and ongoing promotions are mutually independent. Mirrors
the institutional two-layer pattern (stable risk-model neutralization for per-factor research; the
"additive vs the current book?" question handled cheaply at selection/combination time).

**Status:** DESIGN ONLY — no engine code changed. Seeking GPT 5.5 Pro review before touching the
shared eval engine. Reviewed commit: TBD on `report-rc-registration`. Repo: https://github.com/henrydan111/quant-system

---

## 1. The problem, in code

`EvalMethodology.methodology_hash` ([unified_eval.py:139-145](src/alpha_research/factor_eval/unified_eval.py#L139)) hashes,
among the protocol knobs, the **live approved-alpha sets**:
`reference_set_stable`, `reference_set_current`, `provisional_factors`, `reference_set_definition_hashes`.
`build_frozen_methodology` reads these LIVE from the registry
([unified_eval_common.py:47-75](workspace/scripts/unified_eval_common.py#L47)). So any approval/revoke
changes the hash → the matrix producer's drift guard refuses to resume → a full re-run is forced to
keep one consistent methodology. We hit this today (eps_diffusion revoke: saved `c72a7d97` [9-approved]
≠ current `c28914…` [7-approved]).

But the approved set feeds **only** the reference-dependent residual metrics. In `_evaluate_batch`
([unified_eval_full_run.py:256-265](workspace/scripts/unified_eval_full_run.py#L256)) there are THREE
discrete `residual_ic_vs_controls` calls per factor:
- `r_st` vs `reference_stable` → columns `resid_ic_vs_approved_stable_signed/oriented` (the load-bearing marginal/dedup metric)
- `r_cu` vs `approved_current` → `resid_ic_vs_approved_current_*`
- `r_sty` vs `styles` (STYLE_CONTROLS_V1) → the STABLE style-neutralized residual

Everything else a factor's row carries — walk-forward IC/ICIR, quantile spread, decay, turnover,
monotonicity, the style-neutralized residual — is **reference-set-invariant** (depends only on the
factor's own values + forward returns + the fixed style controls). The expensive walk-forward is
re-run today purely to refresh `r_st`/`r_cu`, which are cheap cross-sectional regressions.

## 2. The design — two layers

**Layer 1 (FROZEN, expensive, reference-INVARIANT).** The methodology hash drops the approved-alpha
sets; it depends only on the protocol knobs + `STYLE_CONTROLS_V1` (+ their def-hashes). Everything in
Layer 1 — all walk-forward metrics + the style-neutralized residual `r_sty` — is frozen evidence,
keyed by this stable hash. Approving/revoking a factor never changes it. The anti-snooping freeze is
preserved: the protocol + the style basis are still fully frozen+hashed before any results are seen.

**Layer 2 (CHEAP, on-demand, reference-DEPENDENT).** `r_st`/`r_cu` (marginal contribution vs the
approved book) move out of the frozen-hash identity. They are recomputed on demand against the
**current** approved set via the existing `residual_ic_vs_controls` (a per-date cross-sectional
residualization on cached/processed factor values — NO walk-forward, NO bootstrap, NO decay/turnover).
Each Layer-2 value is stamped with a `reference_set_hash` (sha over the approved-set membership +
def-hashes) recording which book it was computed against.

Net effect: the per-factor research (Layer 1) is tied to the stable style model; the "additive vs our
current book?" question (Layer 2) is tied to the changing book but is seconds-cheap to refresh.

## 3. Concrete changes (for review — not yet implemented)

1. **`EvalMethodology.methodology_hash`**: remove `reference_set_stable`, `reference_set_current`,
   `provisional_factors`, `reference_set_definition_hashes` from the hashed dict. KEEP them as recorded
   (un-hashed) dataclass fields for provenance. KEEP `style_controls_v1` + `style_control_definition_hashes`
   + all protocol knobs in the hash.
2. **New `reference_set_hash`** property/field = sha over `sorted(reference_set_current)` +
   `reference_set_definition_hashes`. Stamped on each evidence row alongside the `resid_ic_vs_approved_*`
   columns (so a row always says which book its marginal metric used).
3. **Matrix producer drift guard** ([unified_eval_universe_matrix.py:144-151]): now never fires on
   approval churn (hash is reference-invariant). Add a SEPARATE soft check: if a row's stored
   `reference_set_hash` ≠ current, mark its `resid_ic_vs_approved_*` as `stale` (recompute via Layer 2).
4. **Layer-2 recompute helper** (new, thin): given the current approved set + factor values, re-run
   only `residual_ic_vs_controls(control_names=current/stable)` for the requested factors and overwrite
   the `resid_ic_vs_approved_*` + `reference_set_hash` columns. To make it walk-forward-free, persist
   the residual-ready inputs (the `preprocess_for_residual` output per factor) alongside `results.jsonl`,
   OR recompute factor values via `compute_factors` (cached) — either way NO walk-forward.
5. **Migration of existing evidence**: the existing ~1568 rows' VALUES are unchanged (core metrics are
   reference-invariant; `r_sty` unchanged; only the HASH label + `r_st`/`r_cu` attribution change).
   Re-stamp them with the new (reference-excluded) `methodology_hash` and a `reference_set_hash` = the
   9-approved set they were computed against. **A metadata re-stamp, NOT a re-walk-forward.**

## 4. Why this is the institutional pattern

Professional shops neutralize per-factor research against a **stable, versioned risk model** (Barra/
Axioma style+industry factors), updated on a slow deliberate cadence — never automatically per new
alpha. The "additive vs the current book?" question is a separate, cheap step at alpha combination.
Layer 1 = our `STYLE_CONTROLS_V1` as that stable risk model; Layer 2 = the combination-time book check.
Today we have it inverted (expensive research tied to the churning book) — this fixes it.

## 5. Verification points — please challenge each

**Q1 — Anti-snooping freeze preserved?** Dropping the approved sets from the hash leaves the protocol +
style basis frozen+hashed pre-results. The reference-set membership (feeding 2 of ~25 columns) becomes
Layer-2 provenance. Is the "methodology frozen before results" guarantee still intact, or does moving
`r_st`/`r_cu` out of the hash open a snooping hole?

**Q2 — Layer-2 against the LIVE book = re-checkable.** Recomputing marginal contribution vs the current
book on demand means you could, in principle, re-check until a factor looks additive. Mitigation: the
matrix is EVIDENCE-ONLY (descriptive); the load-bearing gates (factor_lifecycle IS gate, sealed OOS)
are separate and spend-once. Is "Layer-2 is descriptive, not a spent gate" sufficient, or does Layer-2
need its own freeze-at-decision-time discipline?

**Q3 — Cross-factor comparability of Layer 2.** Factor A's stored `resid_ic_vs_approved` (vs 9-approved)
and factor B's (vs 11-approved) aren't directly comparable. Is stamping `reference_set_hash` + a
"recompute-all-together-before-a-selection-decision" rule enough, or must Layer 2 ALWAYS recompute
every factor against one book snapshot before any comparison is made?

**Q4 — Migration soundness.** Re-stamping existing rows' methodology_hash (values unchanged) + adding
`reference_set_hash` to the resid columns — no re-walk-forward. Is there ANY row whose VALUES would
actually differ under the new hash (i.e., is any currently-hashed-but-now-dropped field also a silent
INPUT to a Layer-1 metric)? My read: no — the approved sets are inputs only to `r_st`/`r_cu`. Confirm.

**Q5 — A candidate factor inside the style basis.** `STYLE_CONTROLS_V1` includes
`qual_gross_profitability`, which FAILED sealed-OOS and is `candidate`, not approved. As a *style-model
control* (a known quality style) its approval status is arguably irrelevant — but should the frozen
style basis be required to contain only approved factors, or is "style model membership is a
methodological choice independent of alpha-approval" the right stance?

**Q6 — Style-model versioning + refresh cadence.** With `STYLE_CONTROLS_V1` now the frozen reference,
when do we deliberately bump to V2 (a signed decision + one full re-baseline)? Propose: only on an
explicit, documented governance decision (new style discovered, or a control deprecated), never
automatically. Is a version-bump-only-by-signed-decision rule the right cadence?

**Q7 — Formal-gate impact.** The matrix is evidence-only (ceiling adjudication). The factor_lifecycle
IS gate + sealed OOS are separate and do NOT consume the matrix's reference residual. Does decoupling
the matrix methodology touch any FORMAL gate semantics? My read: no. Confirm, or name the coupling.

**Q8 — What else relies on the current hash?** The drift guard (intended to change), the dashboard's
methodology display, any test asserting the hash includes the reference set, the `record_formal_auto_evidence`
import key. I'll enumerate + update all before implementing. Anything structural I'm likely to miss?

## Requested verdict

Per Q1–Q8: OK / CHANGES REQUIRED (+ fix). Overall: APPROVE the decoupling design / CHANGES REQUIRED /
REJECT (+ alternative). If APPROVE, also: should migration re-stamp existing evidence in place, or
write a NEW methodology-version namespace and leave the old rows as legacy?

---

## GPT 5.5 Pro verdict (2026-06-15): CHANGES REQUIRED — architecture approved, 6 changes before code

Direction approved (decouple Layer-1 research from the live approved book); 6 required changes folded
in below. GPT verified the code premises (hash fields, live registry read, the 3 residual calls; only
stable/current approved-book residuals are reference-dependent).

**R1 — TWO reference hashes, not one.** The engine computes BOTH `r_st` (vs `reference_set_stable`)
and `r_cu` (vs `reference_set_current`). A single `reference_set_hash` over `current` doesn't identify
the stable residual. Stamp **`reference_set_stable_hash`** AND **`reference_set_current_hash`** (each
over membership + def-hashes), plus the member lists.

**R2 — Layer-2 append-only / separate table, NOT overwrite-in-place.** Overwriting `resid_ic_vs_approved_*`
falsifies audit. Store Layer-2 in its own table keyed by `(factor_id, universe_id, layer1_methodology_hash,
reference_book_type ∈ {stable,current}, reference_set_hash, computed_at)`; comparison queries select one hash.

**R3 — Decision-time Layer-2 freeze (the real anti-snooping guard).** `r_st`/`r_cu` answer "additive vs
the book?" — inherently selection-relevant. Live recompute is fine for DASHBOARD DISPLAY (`layer2_usage =
descriptive_live`), but ANY selection / marginal-contribution / portfolio decision must cite ONE frozen
`Layer2DecisionSnapshot{decision_id, factor_pool, universe_id, reference_set_stable_hash,
reference_set_current_hash, members, def_hashes, computed_at, layer1_methodology_hash}` with ALL pooled
factors recomputed against that single snapshot (`layer2_usage = frozen_decision_snapshot`).

**R4 — Regression test: approved-book membership must NOT change ANY Layer-1 column.** Run the same
factor/universe/protocol under TWO different approved books; assert byte-identical
`heldout_rank_icir / sign_consistency / mean_rank_ic / quantile_profile / turnover / coverage / decay_* /
neutralized_* / resid_ic_vs_style_controls_v1_* / long_leg_*`. ONLY `resid_ic_vs_approved_stable/current`
+ their reference hashes may differ. **This test is the implementation GATE.**

**R5 — Anchor seed/panel/index to STYLE + canonical market data, NOT the live approved set.** Today
`resident_names = STYLE_CONTROLS_V1 ∪ reference_set_current` ([unified_eval_universe_matrix.py:168]),
and `panel_index = seed.index` drives labels/masks/coverage. If `compute_factors` returns a
field-dependent index, the approved set could silently shift Layer-1 inputs. Fix: build the seed
index from STYLE_CONTROLS_V1 + ADJ/market only; the approved-book factor values are pulled separately
for Layer-2. **R4 empirically proves this is necessary or already-safe** (see premise-check below).

**R6 — New methodology schema namespace; legacy rows IMMUTABLE.** Do not mutate existing rows' hashes
(falsifies historical provenance). Introduce `methodology_schema_version = unified_eval_layer1_ref_invariant_v1`;
new `layer1_methodology_hash`; migrate by APPENDING derived rows carrying `legacy_methodology_hash` +
`migration_assertion{layer1_values_unchanged:true, approved_book_residuals_moved_to_layer2:true}` +
both reference hashes (the books actually used). Old rows stay as immutable legacy evidence.

**Also (R-extra):** resume guard compares Layer-1 hash only (warn on stale Layer-2 ref hashes); style
model versioned by SIGNED decision only (style change → new Layer-1 hash → full re-baseline; approval
churn → never); formal gates may NOT read live `resid_ic_vs_approved_*` unless tied to a frozen
`Layer2DecisionSnapshot`.

### Revised implementation order (test-first)
1. **Premise-check / R4 gate** — empirically verify `panel_index` (hence all Layer-1 metrics) is
   independent of the approved set. If dependent → R5 seed-anchoring is a REQUIRED fix first.
2. R5 seed/index anchoring (if the premise-check shows dependence).
3. `methodology_hash` → exclude reference sets + `methodology_schema_version` + `layer1_methodology_hash` (R6).
4. Two reference hashes (R1) + Layer-2 separate append-only table (R2).
5. `Layer2DecisionSnapshot` + `layer2_usage` discipline (R3).
6. Migration: append derived rows, legacy immutable (R6); update drift guard / resume / dashboard / import keys (R-extra).
7. Encode R4 as a committed regression test.

### Premise-check result (2026-06-15) — R5 concern resolved favorably

Empirical check (`compute_factors` over 2018-2019, style-only `{val_ep_ttm, mom_return_20d}` vs
style+approved `{…, liq_zero_ret_days_10d, qual_piotroski_fscore_9pt}`): **both produce the IDENTICAL
panel index (1,730,317 rows; `index.equals` = True).** `compute_factors` returns a fixed
(instrument, datetime) grid over the universe × calendar regardless of the requested factor set, so
the seed `panel_index` — hence every Layer-1 label/mask/coverage/walk-forward metric — is
**reference-invariant**. Consequences:
- The "Layer-1 is reference-invariant → migration is value-safe" premise HOLDS empirically.
- R5 (seed anchoring) is a **hardening** (anchor the seed index explicitly to STYLE + ADJ/market so
  it STAYS invariant, and lock it with the R4 regression test), NOT a required bug fix.
- R6's new-namespace migration is still adopted (audit integrity — don't falsify historical hashes),
  but it is now provably a metadata operation over unchanged Layer-1 values.
- R4 (the committed byte-identical-Layer-1-columns test under two books) remains the gate; this
  premise-check de-risks it (the index — the one indirect path GPT flagged — is invariant).
