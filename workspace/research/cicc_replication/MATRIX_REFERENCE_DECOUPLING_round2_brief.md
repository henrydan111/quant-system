# Matrix reference-decoupling — round-2 review brief (confirm fold-in + scope, pre-implementation)

**Round-1 verdict (you, GPT 5.5 Pro):** CHANGES REQUIRED — architecture approved, 6 changes (R1–R6)
before code. All 6 folded into the design; the R4/R5 premise-check has been RUN. This round: confirm
the fold-in is faithful, confirm the premise-check interpretation, and settle the implementation
scope — **before** I touch the shared eval engine. No engine code written yet.

**Reviewed commit:** `ebce368` on `report-rc-registration`. Repo: https://github.com/henrydan111/quant-system
**Design (with the GPT-verdict fold-in + premise-check result):**
https://github.com/henrydan111/quant-system/blob/ebce368/workspace/research/cicc_replication/MATRIX_REFERENCE_DECOUPLING_DESIGN.md

## What changed since your round-1 verdict

- **R1–R6 folded in** (see the "GPT 5.5 Pro verdict … 6 changes" section of the design doc):
  R1 two reference hashes (stable+current); R2 Layer-2 append-only/separate table; R3 decision-time
  `Layer2DecisionSnapshot` + `layer2_usage` (descriptive_live vs frozen_decision_snapshot); R4
  committed byte-identical-Layer-1-columns regression test (the impl gate); R5 anchor seed/index to
  STYLE+market only; R6 new `methodology_schema_version` namespace + legacy rows immutable + append
  derived migration rows with `migration_assertion`.
- **Premise-check RAN** (your R4/R5 deepest concern): `compute_factors` over 2018-2019 with
  style-only vs style+approved factor sets → **identical panel index (1,730,317 rows, index.equals
  = True)**. The seed `panel_index` (hence all Layer-1 labels/masks/coverage/walk-forward) is
  reference-invariant. → R5 reframed as a *hardening* (anchor explicitly + lock with R4's test), not
  a bug fix; migration is a metadata op over unchanged Layer-1 values; R6 namespace still adopted.

## Confirm / decide (C1–C4)

**C1 — Faithful fold-in?** Re-read the fold-in section; is each of R1–R6 captured correctly and
completely, or did any requirement get diluted/misread (especially R3's frozen-snapshot discipline
and R6's append-don't-mutate)?

**C2 — Premise-check interpretation.** The index-equality check shows the one indirect path you
flagged (seed-index dependence) is clean. Is index-invariance + "Layer-1 metrics don't reference the
approved set, only r_st/r_cu do" sufficient to call Layer-1 reference-invariant — with R4's full
byte-identical-columns test then RUN as the FIRST implementation step (the gate) — or do you want the
full R4 test executed and shown GREEN before any hash/namespace change is written at all?

**C3 — Implementation scope / PR split (the real decision).** Two options:
  - (a) **Single change**: R4 test + R5 anchor + hash/namespace (R6) + two hashes (R1) + Layer-2 table
    (R2) + decision snapshot (R3) + migration, all together.
  - (b) **Two PRs**: PR-1 = R4 test + R5 anchor + hash/namespace + two hashes (the core decoupling that
    unblocks E1a and stops the churn); PR-2 = Layer-2 table + `Layer2DecisionSnapshot` + the
    selection-time discipline.
  Concern with (b): after PR-1, where do `resid_ic_vs_approved_stable/current` live? They'd still be
  written inline (as today) but now NOT in the frozen hash — is that an acceptable interim (columns
  present, tagged with the two reference hashes, but not yet in the separate append-only table), or
  does R2's "separate table, not overwrite" have to land in the same change as the hash decoupling to
  avoid an audit gap? Which split do you recommend?

**C4 — Migration + wire-ups.** Planned: append derived rows in the new namespace (legacy immutable);
update the drift guard (compare Layer-1 hash only; warn on stale Layer-2 ref hashes), the resume
guard, the dashboard methodology display, and the `record_formal_auto_evidence` import key. Is
anything in this list underspecified or risky, and is appending derived migration rows (vs a derived
read-time VIEW over legacy rows) the right mechanism?

## Requested verdict

Per C1–C4: OK / CHANGES REQUIRED (+ fix). Overall: **PROCEED to implement** (with the recommended PR
split) / **CHANGES REQUIRED first**. If PROCEED, confirm whether R4 must be shown GREEN before any
other code lands.
