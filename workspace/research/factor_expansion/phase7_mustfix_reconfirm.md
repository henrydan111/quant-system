# Phase 7 must-fix RE-CONFIRM (for GPT) — persist `expected_direction` to `factor_master`

Your impl-review NO-GO had exactly one must-fix: the lifecycle verdict's `expected_direction`
was dropped by `record_lifecycle_evidence` (evidence-only), so `factor_master.expected_direction`
stayed blank — and the future `FrozenSelectionSet` hash consumes that durable field. You verified
the blank state with a temp-registry probe (`heldout_rank_icir=-0.25` attaches, but
`factor_master.expected_direction` empty). This is the fix; confirm it resolves the NO-GO.

## The fix (commit fdc1471, on top of build c91cda9)

New metadata-only store method (`FactorRegistryStore.set_expected_direction`):
```python
def set_expected_direction(self, *, factor_id, expected_direction, version=None) -> None:
    """Metadata-only: set factor_master.expected_direction on the current row. Does NOT touch
    status / approval_validity / definition_hash and writes NO status-history row. Blank -> no-op."""
    ed = str(expected_direction or "").strip()
    if not ed:
        return
    index = self._resolve_master_index(factor_id=factor_id, version=version)
    self.factor_master.at[index, "expected_direction"] = ed
    self.factor_master.at[index, "updated_at"] = _now_str()
```

Wired into the publish promotion loop (`handle_factor_lifecycle_registry_publish`), per attached
factor, AFTER the (idempotent) evidence write and the `set_status('candidate')`:
```python
for v in candidate_verdicts:
    fid = str(v.get("factor", ""))
    if fid and fid in ev_report["attached"]:
        store.set_status(factor_id=fid, status="candidate", reason=..., source_run_id=run_id)
        store.set_expected_direction(factor_id=fid, expected_direction=str(v.get("expected_direction", "")))
        promoted.append(fid)
store.save()
```
`expected_direction` on the verdict row comes from `_expected_direction(signed heldout ICIR)`
→ `positive` / `inverse` / `undetermined`. `record_lifecycle_evidence` is UNCHANGED (still
evidence-only, still stores the signed `is_rank_icir`); the master metadata write is a separate,
explicit, metadata-only call — so the Phase-1 evidence-writer boundary is preserved.

## Verification
New test `test_publish_persists_expected_direction_metadata`: set a promoted factor's
`heldout_rank_icir=-0.25` / `expected_direction="inverse"`, run publish (approved), then assert:
- `factor_master.expected_direction == "inverse"` for the promoted factor (the blank field your
  probe caught is now populated, with the correct INVERSE direction), AND
- `status == "candidate"` (unchanged — proves metadata-only).

Also cleaned the stale `non_base_deferred` docstring in `dataset_build`. Sweep after the fix:
**107 passed** (lifecycle + registry + promotion-gate + helpers); the full Phase-7 build sweep
was 178 passed.

## Confirm
Does this resolve the NO-GO (durable `expected_direction` populated, metadata-only, no touch to
status/approval_validity/definition_hash)? GO to push + PR + merge, then the promote-16
`oos_informed_backfill` run?
