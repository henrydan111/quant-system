# report_rc: quarantine → officially registered in Qlib — concrete roadmap

*2026-06-08. From the current state (plumbing merged, `$report_rc__*` QUARANTINE, ZERO live
bins) to a formally-registered, approved, factor-bearing dataset. Each phase is separately
gated; nothing here is done yet.*

## Current state (verified)
- Code path merged to main (PR #41): `DatasetSpec`, `build_ledger` report_rc branch (the
  validated `report_date+1` anchor), `_materialize_report_rc_consensus` (emits the P1 subset
  `$report_rc__{eps_up, eps_dn, eps_revision_count, n_active_analysts}`).
- `field_status.yaml`: `report_rc` present, **status = quarantine** (not formal-eligible).
- Live provider `data/qlib_data/`: **0** `$report_rc__*` bins. Live `data/pit_ledger/report_rc/`:
  **absent**. Everything validated so far was a **sandbox** build under `workspace/outputs/`.
- Live raw `data/analyst/report_rc/` **carries `create_time`** → no re-fetch needed.

## Dependency graph
```
  Phase A (restatement canary, ~06-15)  ┐
                                        ├─> Phase C (quarantine→approved) ─> Phase D (IS gate) ─> Phase E (sealed OOS)
  Phase B (full provider rebuild)       ┘
```
A and B are independent and can proceed in parallel. C needs BOTH (A = the breadth-PIT
evidence; B = the live bins to parity-check). D needs C (approved fields). E needs D (a
candidate factor).

---

## Phase A — discharge the breadth-PIT dependency (restatement canary)  ⟵ the dependency you asked about
**Why:** the re-anchor validated `report_date+1` as PIT for the consensus **LEVEL** (corr +0.997,
broad +0.94). But the flagship `eps_diffusion` is **breadth** = a *second-difference* (net % of
analysts raising), which is sensitive to the exact per-revision SET in a way the level is not. A
2022 backfill could preserve the mean yet have dropped/restated individual revisions. Level-parity
is necessary **but not sufficient** for breadth.

**Mechanism:** `scripts/report_rc_backfill_canary.py recheck` already baselined SNAP1 (64,966 rows,
2,743 stocks); a one-time scheduled task fires **2026-06-15 09:30 +08:00** to take SNAP2 and
auto-diff. The diff reports the three smoking guns: (1) BACKFILLED old-dated rows, (2) report_date
DRIFT, (3) payload RESTATEMENT.

**Gate:** PASS = 0 backfilled + 0 drift in the observed window → the per-revision set is stable →
breadth is PIT-safe to deploy on the deep history. FAIL = size an ingestion-lag buffer from the
gap distribution and/or restrict the breadth factor to the contemporaneous (2023+) window.

**Status:** waiting on the 2026-06-15 snapshot. This gates Phase C's PIT evidence for the breadth
field and, at the latest, Phase E (the breadth factor's OOS). *Until A passes, registration can
proceed for the LEVEL/count fields but the breadth factor must not be sealed-OOS'd.*

---

## Phase B — full provider rebuild on the re-anchored history (the gated `mode="all"`)
**Why:** unlike moneyflow (whose bins already existed — its promotion was a pure registry flip),
report_rc has **no live bins**. They must be materialized into `data/qlib_data/` + a live
`data/pit_ledger/report_rc/` built.

**Mechanism:** `venv/Scripts/python.exe src/data_infra/pipeline/build_qlib_backend.py --mode all
--stage full --publish` (report_rc is in `PHASE3_DATASETS`, so the `materialize_provider` hook
fires automatically). Adding a new dataset is a **schema-level change** → `mode=all` is the
sanctioned path (CLAUDE.md §6.3). This is a **§13 risky action** (expensive full rebuild;
needs explicit go-ahead).

**Constraints to respect (already enforced in code):**
- **Publish atomicity (P0-6):** staged build and `data/qlib_data/` must be on the **same volume**
  (`os.replace`); else `BuildGateError`.
- **Provider attestation:** the build emits a NEW `data/qlib_data/metadata/provider_build.json`
  with a new `provider_build_id` — Phase C's approval YAML must bind to it.
- **Calendar policy:** frozen `frozen_20260227_system_build` (observed calendar end must equal it).

**Verify after build:** `scripts/audit_qlib.py` + `tests/harnesses/qlib_smoke.py` + a spot
`D.features(["$report_rc__eps_up"])` on a known stock; confirm full-history span (2010+).

**Decision — scope of the rebuild:** a clean `mode=all` regenerates the WHOLE provider (all
datasets, hours). If that's too heavy, the alternative is a provider-only staged build that
materializes report_rc and merges into the existing tree — but that needs care so `publish` does
not replace the full tree with a report_rc-only one. *Recommend the clean full rebuild for
correctness; confirm the volume/runtime budget first.*

---

## Phase C — promote `quarantine → approved` (field governance)
**Why:** even with live bins, the field-status registry refuses report_rc at any formal stage while
it is `quarantine` (the release gate `assert_field_dependencies_eligible` + the validation
resolver/dataset-build gates fail-closed).

**Mechanism (mirror `approvals/2026-06-04_moneyflow_quarantine_to_approved.yaml`):**
1. Read-only review script → evidence dump (like `diag_moneyflow_review.py`).
2. New `config/field_registry/approvals/2026-06-XX_report_rc_quarantine_to_approved.yaml` with:
   - `from_status: quarantine → to_status: approved`, `approval_scope.stages` all true;
   - **bind** `provider_build_id` + `calendar_policy_id` to Phase B's new build (daily-QA
     `approval_evidence_binding` validates this);
   - `pit_contract`: events anchored at `report_date+1` (effective_date); predictive factors wrap
     every field in `Ref(...,1)` (same daily-outcome discipline as moneyflow);
   - **evidence:** coverage (per-field non-null % by year, the ≥50%-on-a-bar-year gate),
     value-sanity (eps_up/eps_dn non-negative, revision_count = up+dn, n_active ≤ analyst count),
     **provider parity** (`D.features($report_rc__*)` vs the ledger-derived expected, 0 mismatch),
     field inventory, and **the Phase-A canary result** as the breadth-PIT evidence.
3. Append a `field_approval_log.jsonl` promotion entry.
4. Tests: `test_field_registry` (report_rc resolves approved at formal_validation),
   `test_approval_evidence` (YAML binding-valid vs live `provider_build.json`).

**Decision — promote which fields:** the P1 subset is enough for the flagship. Recommend promoting
`$report_rc__eps_up`, `$report_rc__eps_dn`, `$report_rc__eps_revision_count` (the breadth inputs)
+ `$report_rc__n_active_analysts` (coverage). The richer primitives
(`eps_same`/`dispersion`/`FY1-level`/`coverage`) are a LATER materializer extension — do not block
the flagship on them.

---

## Phase D — add the catalog factor (`eps_diffusion`) + factor_lifecycle IS gate
**Mechanism:**
- Add a PIT-safe Qlib expression to `catalog.py` (sentiment/quality section), e.g.
  `eps_diffusion = (Sum(Ref($report_rc__eps_up,1), W) − Sum(Ref($report_rc__eps_dn,1), W)) /
  (Sum(Ref($report_rc__eps_up,1), W) + Sum(Ref($report_rc__eps_dn,1), W) + ε)` over a trailing
  window W (~the v2 120d revision window; materializer n_active TTL is 120d). Lint-safe: every
  `$field` inside `Ref(...,1)`, `If`-guarded denominator (no `-Operator`).
- `sync_catalog` → registry `draft`. Run the **`factor_lifecycle`** profile (IS-only gate) →
  `draft→candidate`.

**Gate / honest caveat:** this is the **first trustworthy compliant-backend measurement** of
`eps_diffusion`. The WAVE1A **+0.64 ICIR is INVALID** (non-compliant hand-rolled path + survivorship
bypass + breadth-set unverified) — the re-anchor only makes the deep history *PIT-usable*; it does
NOT re-validate that number. The IS gate will tell us if the clean signal clears the bar.
Given the project prior (marginal IS signals usually die OOS; GP just did), treat a PASS here as
necessary-not-sufficient.

---

## Phase E — single sealed-OOS shot
**Mechanism:** if `eps_diffusion` reaches `candidate`, run the one sealed-OOS test via the sanctioned
path (`FrozenSelectionSet` → `HoldoutSealStore`, `seal_key = frozen_set_hash`), OOS window
2021-2026 (fresh for report_rc through the compliant path — WAVE1A touched no OOS). PASS → `approved`
factor. FAIL → stays `candidate`, OOS spent (cannot re-test as fresh) — the GP outcome.

**Phase-A interaction:** the breadth factor must NOT be sealed-OOS'd until the restatement canary
(Phase A) passes — otherwise a breadth-set contamination would invalidate the one-shot OOS.

---

## Recommended sequencing
1. **Now:** decide whether to kick off **Phase B** (the full rebuild — needs your go-ahead + a
   volume/runtime budget) while **Phase A** waits for the 06-15 canary. These two run in parallel.
2. **After A passes + B publishes:** **Phase C** (the approval YAML, bound to B's new build id).
3. **Then C→D→E** in order. Stop after D if the IS signal is weak (don't spend the OOS on a dud).

**Lowest-regret next step:** wait for the **06-15 restatement canary** (Phase A) before the full
rebuild — if it shows breadth contamination, the whole breadth thesis changes and we'd rebuild for
the level/count fields only. The rebuild is the expensive irreversible-ish step; the canary is cheap
and gates the thesis. (If you want the level/count fields registered regardless, B+C can start now.)
