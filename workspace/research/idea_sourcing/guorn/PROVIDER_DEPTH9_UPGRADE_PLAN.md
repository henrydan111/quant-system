# Plan — upgrade the LIVE provider single-quarter depth q0..q4 → q0..q8 (slot_depth 5 → 9)

**Directive (2026-06-30):** make ALL periodic qlib factors' single-quarter reachback go from q4 to q8 — i.e.
materialize single-quarter (`_sq_q*`) AND level (`_q*`) slots to **depth 9 (q0..q8)** on the LIVE provider, so
every 8-quarter / year-ago-TTM factor is natively available with no transient deep-slot build. **This SUPERSEDES
the transient Route-A scoped build** (`UNLOCK_8Q_FACTORS_PLAN.md` Route A) — `RnDTTMGr%PY` and
`AssetTurnoverDiffPY` will just read the live provider. (Routes B/C are slot-depth-independent and unaffected;
Route B's M2 period-sequence anchor is *helped* — it can source the visible report sequence from the live
provider's q0..q8 report slots.)

Public repo for review: `https://github.com/henrydan111/quant-system` (branch `report-rc-registration`).

```
SCRIPT_STATUS: DATA_INFRA_PROVIDER_CHANGE (FORMAL — touches the live provider all research reads)
§13 risky action: full re-materialization (mode=all) + publish to data/qlib_data → needs user GO.
§10: substantial data-infra change (SLOT_DEPTH_DEFAULT affects PIT materialization for ALL factors) → GPT review.
```

---

## Mechanism

`pit_backend.py:70 SLOT_DEPTH_DEFAULT` is the single source. The materializer writes `{field}_sq_q{slot}` and
the level `{field}_q{slot}` for `slot in range(self.slot_depth)`. Today the live provider is depth 5 (q0..q4).

1. **Code (DONE, reversible):** `SLOT_DEPTH_DEFAULT = 5 → 9`. This makes depth 9 the durable default so
   `update_daily_data.py` keeps producing q0..q8 (a daily update at the old default 5 would freeze q5..q8 stale
   while q0..q4 advance — so the default MUST change, not just a one-off `slot_depth=9` build arg).
2. **Re-materialize (GATED on GO):** full provider re-materialization at depth 9 over ALL symbols —
   `build_qlib_backend(mode="all", stage="provider-only", slot_depth=9, publish=...)` (normalized/ledger data is
   current as of the 2026-06-24 build + frozen 2026-02-27 calendar, so no upstream re-ingest). Staged build →
   atomic `os.replace` publish (P0-6; same volume — verified, all on E:).
3. **Verify → governance updates** (below).

## Safety analysis (audited, read-only)

- **Additive, no breakage.** Every `_sq_q4`/`_q4` reference in the catalog (`grow_*_q_yoy`, piotroski, etc.) is a
  **year-ago consumer** (q0 vs q4); q0..q4 are byte-unchanged, q5..q8 are new. No code assumes q4 is the max slot.
- **Tests pass.** The 4 slot-exercising test files (90 tests) PASS at depth 9; every count-asserting test
  (`test_profit_dedt_sq.py:94` etc.) pins `slot_depth` explicitly (5 or 2), not the default. Full `tests/data_infra`
  sweep at depth 9: **317 passed, 9 skipped** (0 failures).
- **Both flow + level slots scale.** `_sq_q*` (flows, e.g. `revenue_sq_q5..q8`) via the single-quarter path AND
  `_q*` (balances, e.g. `total_assets_q8`) via `materialize_visibility_segments(..., slot_depth=self.slot_depth)`
  (pit_backend.py:3481) — so AssetTurnoverDiffPY's begin/end denominator (`(assets_q4+assets_q8)/2`) and
  RnDTTMGr%PY's year-ago TTM (`rd_exp_sq_q4..q7`) are both natively materialized.
- **PIT-safe (§3.2).** Deeper slots use the SAME restatement-safe kernel (`derive_single_quarter_value`,
  `effective_date>disclosure` STRICT) as q0..q4 — rung-6 validated this **bit-faithful to depth 16** (median
  rel-err 0.0, n~2M). No new lookahead. The deepslot income special-cases (slot_depth=12/16) pass explicit
  values and are unaffected by the default.
- **Disk feasible.** E: free **1.97 TB** / 3.8 TB. `_sq_q` is ~20.8% of the provider (835/4021 bins/stock,
  14.7MB/stock at depth 5). Depth 5→9 = +80% on that ~21% → provider grows ~16.6% (~241GB → ~281GB, **+~40GB
  permanent**); staged-build+publish PEAK ≈ 520GB (live + staged) + any retained backup. Well within headroom.
  (4 stale staged builds under `data/qlib_builds/` can be pruned for hygiene.)

## Caveats / follow-ups (NOT blockers for the provider build)

- **Field registry (formal-gate).** `field_status.yaml` ENUMERATES `_sq_q` slots up to q4 (e.g. `$n_income_sq_q4`).
  q5..q8 will be **unregistered** → fine for NON-FORMAL parity (the comparator reads `D.features` directly), but a
  FORMAL factor using q5..q8 needs an approval entry first (§3.4 field-status gate). Document, don't pre-register.
- **Provider attestation.** New `provider_build.json` (`provider_build_id`, `provider_published_at`); frozen
  calendar policy unchanged (still 2026-02-27). Daily-QA approval-evidence binding re-validates against the new id.
- **Cost.** Full re-materialization is multi-hour — run in background, verify before publish.

## Execution steps (on GO)

1. (done) `SLOT_DEPTH_DEFAULT=9` + full `tests/data_infra` green + GPT §10 review.
2. Staged build: `build_qlib_backend(mode="all", stage="provider-only", slot_depth=9, build_id="depth9_<date>",
   publish=False)` over all symbols → background, logged.
3. Verify staged: `audit_qlib.py` + `qlib_smoke.py` + spot-check `revenue_sq_q8` / `total_assets_q8` exist and a
   q8-using expr resolves PIT-correctly on a sample (vs the rung-6 deepslot truth).
4. Publish (atomic `os.replace`, same-volume verified) → new `provider_build.json`.
5. Post-publish verify: `run_daily_qa.py` (provider boundary + PIT live regression).
6. Governance: `data_dictionary.md` (document q5..q8), `data_tracker.md`, `project_state.md`, the rule files if
   any slot-depth fact is stated there.
7. Re-run the blocked campaign factors (RnDTTMGr%PY, AssetTurnoverDiffPY) against the live provider via the
   comparator (no `--provider-uri` needed now) → record top-K in the campaign.

## Self-review (§3 invariants + quant principles)

- §3.2 PIT: same kernel, additive, rung-6-proven bit-faithful — no lookahead. ✓
- §6.3 rebuild discipline: full re-materialization is the sanctioned use (schema-level change); staged + atomic
  publish; same-volume; verify after. ✓
- Disk hazard (memory): scoped to provider-only (no upstream re-ingest), measured ~+40GB / ~520GB peak vs 1.97TB
  free; prune stale staged builds. ✓
- No factor/test breakage (audited + 90 tests green). ✓ No hedge words. ✓
- **Verdict: clean for GPT review.**

## GPT §10 review — APPROVED (2026-06-30), publish gates MANDATORY

GPT-5.5 Pro: **APPROVE** — "no PIT/no-lookahead reason to block; depth extension over the same effective-date /
restatement-safe machinery, not a new alignment rule." No blockers, no majors. PIT confirmed safe across all 5
periodic families; additive confirmed; default-change is the correct durability choice; q5..q8-unregistered is
the correct governance posture. The conditions are PUBLISH gates (the residual risk is **operational, not PIT**:
publishing without a q0..q4 byte audit could silently invalidate prior formal evidence). Enforced as fail-closed:

- **m1 — staged-vs-live q0..q4 byte/hash audit BEFORE the atomic swap.** For every existing registered periodic
  slot (`*_q0..q4`, `*_sq_q0..q4`, `*_cum_q0..q4` where present) across income/balancesheet/cashflow/indicators/
  profit_dedt: staged bins MUST be byte-identical to current live → else FAIL publish (do not swap).
- **m2 — rebind approval evidence ONLY after the audit.** Emit the new `provider_build.json`, then rebind
  approval YAMLs to the new `provider_build_id` only after: q0..q4 byte audit passes → manifest emitted →
  `run_daily_qa.py` passes provider-boundary + manifest + field-gate + PIT live regression.
- **m3 — document the sandbox side effect.** Default is now depth 9; shallow sandbox/scoped builds that want q0..q4
  only MUST pass `slot_depth=5` explicitly; live/provider-maintenance builds use the default 9. (Add to the
  data-ops note + the scoped-build wrappers.)

**Pre-publish checklist (ALL must pass before the atomic swap):**
1. Full staged provider build completes at slot_depth=9.
2. q0..q4 existing registered bins byte/hash-identical staged-vs-live (m1).
3. q5..q8 smoke tests pass for BOTH `_sq_q*` and level `_q*` slots.
4. A q8-using expression resolves through Qlib and matches the rung-6 deepslot truth on samples.
5. `provider_build.json` emitted with the new `provider_build_id` + unchanged calendar policy (2026-02-27).
6. `run_daily_qa.py` passes provider-boundary, manifest, field-gate, PIT live regression.
7. q5..q8 remain ABSENT from `field_status.yaml` (no bulk-register just because they exist on disk).
8. approval-evidence bindings updated ONLY after the byte audit + manifest checks (m2).

## Review questions for GPT

1. **PIT:** Is upgrading `SLOT_DEPTH_DEFAULT` 5→9 + full re-materialization PIT-safe for ALL periodic families
   (income/balancesheet/cashflow/indicators/profit_dedt), given the shared restatement-safe kernel — any family
   where deeper slots could leak or mis-anchor?
2. **Breakage:** Is the change truly additive (q0..q4 byte-unchanged), or is there a path where re-materializing
   changes existing q0..q4 values, or where a consumer/test/registry silently breaks on the new q5..q8?
3. **Durability:** Is changing the DEFAULT (vs threading `slot_depth=9` through the live build + daily update) the
   right way to keep q5..q8 fresh across daily updates, and does it have unintended effects on sandbox/scoped builds?
4. **Governance:** Is leaving q5..q8 unregistered in `field_status.yaml` (non-formal-readable, formal-gated) the
   correct posture, and are the provider-attestation / calendar-policy / daily-QA implications fully covered?
5. **Anything else** that makes this unsafe to publish to the live provider all research depends on?
