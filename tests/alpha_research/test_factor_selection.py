"""Phase 3 — tests for the sandbox-only status-aware factor readers
(``get_factors`` / ``get_factor_selection``) in
``src/alpha_research/factor_library/selection.py``.

Safety tests land WITH the slice they protect (design-review sequencing): formal-stage
refusal + name-parity + drift here (P3.1); the off-status dependency contract (P3.1b).
The AST-usage formal-gate boundary is in tests/architecture/test_get_factors_boundary.py.
"""

import tempfile
import unittest
from collections import OrderedDict
from pathlib import Path

from src.alpha_research.factor_library import (
    get_factors,
    get_factor_selection,
    get_factor_catalog,
    FORMAL_STAGES,
    FormalStageNotAllowedError,
    RegistryNotSyncedError,
    FactorSelectionDriftError,
)
from src.alpha_research.factor_library.catalog import get_composite_defs
from src.alpha_research.factor_registry import FactorRegistryStore

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_OUTPUTS = PROJECT_ROOT / "workspace" / "outputs"


class FactorSelectionTests(unittest.TestCase):
    def _temp_dir(self, name: str):
        WORKSPACE_OUTPUTS.mkdir(parents=True, exist_ok=True)
        return tempfile.TemporaryDirectory(prefix=f"{name}_", dir=WORKSPACE_OUTPUTS)

    def _synced_store(self, temp_dir):
        store = FactorRegistryStore(temp_dir)
        store.sync_catalog(record_run=False, generated_at="2026-04-04 21:00:00")
        store.save()
        return store

    # ── P3.1: stage gate + empty + status validation ───────────────────────
    def test_empty_registry_raises_not_synced(self):
        with self._temp_dir("sel_empty") as d:
            with self.assertRaises(RegistryNotSyncedError):
                get_factors(stage="sandbox_screening", status_in={"draft"}, registry_dir=d)

    def test_formal_stage_refused_at_runtime(self):
        with self._temp_dir("sel_formal") as d:
            self._synced_store(d)
            for stage in FORMAL_STAGES:
                with self.assertRaises(FormalStageNotAllowedError):
                    get_factors(stage=stage, status_in={"draft"}, registry_dir=d)
                with self.assertRaises(FormalStageNotAllowedError):
                    get_factor_selection(stage=stage, status_in={"draft"}, registry_dir=d)

    def test_status_in_required_and_validated(self):
        with self._temp_dir("sel_status_arg") as d:
            self._synced_store(d)
            # bare string is rejected (would otherwise become a char set)
            with self.assertRaises(ValueError):
                get_factors(stage="sandbox_screening", status_in="approved", registry_dir=d)
            # empty is rejected
            with self.assertRaises(ValueError):
                get_factors(stage="sandbox_screening", status_in=set(), registry_dir=d)
            # unknown status token is rejected
            with self.assertRaises(ValueError):
                get_factors(stage="sandbox_screening", status_in={"frozen"}, registry_dir=d)

    # ── P3.1: name parity + compute-ready ──────────────────────────────────
    def test_get_factors_base_name_parity_and_compute_ready(self):
        with self._temp_dir("sel_parity") as d:
            self._synced_store(d)
            cat = get_factor_catalog(include_new_data=True)
            gf = get_factors(
                stage="sandbox_screening",
                status_in={"draft", "candidate", "approved"},
                include_new_data=True,
                registry_dir=d,
            )
            self.assertIsInstance(gf, OrderedDict)
            self.assertEqual(set(gf), set(cat))               # exact base name parity
            self.assertTrue(all(gf[k] == cat[k] for k in gf))  # identical expressions -> drop-in
            # include_new_data=False is a strict subset (the 36 new-data bases drop out)
            gf_small = get_factors(
                stage="sandbox_screening", status_in={"draft", "candidate", "approved"},
                include_new_data=False, registry_dir=d,
            )
            self.assertTrue(set(gf_small).issubset(set(gf)))
            self.assertEqual(set(gf_small), set(get_factor_catalog(include_new_data=False)))

    # ── P3.1: status filter ────────────────────────────────────────────────
    def test_status_filter_includes_and_excludes_precisely(self):
        with self._temp_dir("sel_filter") as d:
            store = self._synced_store(d)
            cat = get_factor_catalog(include_new_data=True)
            fid = next(iter(cat))
            store.set_status(factor_id=fid, status="candidate", reason="test")
            store.save()
            cand = get_factors(stage="sandbox_screening", status_in={"candidate"},
                               include_new_data=True, registry_dir=d)
            self.assertEqual(set(cand), {fid})
            # draft set no longer includes the promoted factor
            draft = get_factors(stage="sandbox_screening", status_in={"draft"},
                                include_new_data=True, registry_dir=d)
            self.assertNotIn(fid, draft)
            # deprecated only when explicitly requested
            store.set_status(factor_id=fid, status="deprecated", reason="test")
            store.save()
            self.assertNotIn(fid, get_factors(stage="sandbox_screening", status_in={"candidate"},
                                              include_new_data=True, registry_dir=d))
            self.assertIn(fid, get_factors(stage="sandbox_screening", status_in={"deprecated"},
                                           include_new_data=True, registry_dir=d))

    # ── P3.1: drift modes ──────────────────────────────────────────────────
    def test_drift_modes_skip_default_codewarn_raise(self):
        with self._temp_dir("sel_drift") as d:
            store = self._synced_store(d)
            cat = get_factor_catalog(include_new_data=True)
            fid = next(iter(cat))
            idx = store.factor_master.index[
                (store.factor_master["factor_id"] == fid)
                & (store.factor_master["is_current"].fillna(False))
            ][0]
            store.factor_master.at[idx, "definition_hash"] = "dead" * 16  # drift vs code
            store.save()
            # default skip -> excluded
            self.assertNotIn(fid, get_factors(stage="sandbox_screening", status_in={"draft"},
                                              include_new_data=True, registry_dir=d))
            # code_warn -> included (code def)
            self.assertIn(fid, get_factors(stage="sandbox_screening", status_in={"draft"},
                                           include_new_data=True, registry_dir=d, on_drift="code_warn"))
            # raise
            with self.assertRaises(FactorSelectionDriftError):
                get_factors(stage="sandbox_screening", status_in={"draft"},
                            include_new_data=True, registry_dir=d, on_drift="raise")

    # ── P3.1b: FactorSelection records + composites ────────────────────────
    def test_selection_returns_composites_and_first_class_records(self):
        with self._temp_dir("sel_records") as d:
            self._synced_store(d)
            sel = get_factor_selection(
                stage="sandbox_screening",
                status_in={"draft", "candidate", "approved"},
                include_new_data=True, registry_dir=d,
            )
            # Counts are DERIVED from catalog_composition() (CLAUDE.md §3.5: never
            # hard-code a catalog count — the 2026-07-03 grn_* wave broke the old
            # hard-coded 20 silently).
            from src.alpha_research.factor_library.catalog import catalog_composition
            comp = catalog_composition()
            self.assertEqual(len(sel.composite_defs), comp["composite"])
            self.assertEqual(len(sel.industry_relative_defs), comp["industry_relative"])
            # every composite's base components are present in base_expressions (compute-ready)
            for cdef in sel.composite_defs:
                for comp in cdef.get("components", []):
                    self.assertIn(comp, sel.base_expressions)
            # records carry the first-class selection fields
            rec = sel.records[0]
            for attr in ("factor_id", "kind", "status", "selected", "selection_role", "dependency_included"):
                self.assertTrue(hasattr(rec, attr))
            # with everything selected, there are no dependency-only rows
            self.assertTrue(all(r.selection_role == "selected" for r in sel.records))

    # ── P3.1b: the off-status dependency contract (design-review required) ──
    def test_off_status_composite_pulls_dependencies_only_in_selection(self):
        with self._temp_dir("sel_deps") as d:
            store = self._synced_store(d)
            cat = get_factor_catalog(include_new_data=True)
            # pick a composite whose base components are all in the (new-data) catalog
            comp = next(
                c for c in get_composite_defs()
                if all(str(x) in cat for x in c.get("components", []))
            )
            comp_name = str(comp["name"])
            components = [str(x) for x in comp["components"]]
            store.set_status(factor_id=comp_name, status="candidate", reason="test")
            store.save()

            sel = get_factor_selection(stage="sandbox_screening", status_in={"candidate"},
                                       include_new_data=True, registry_dir=d)
            # the composite is selected and its def is returned
            self.assertIn(comp_name, [str(c["name"]) for c in sel.composite_defs])
            # its draft base deps ARE in base_expressions (compute-ready) ...
            for comp_base in components:
                self.assertIn(comp_base, sel.base_expressions)
            # ... and tagged dependency-only (never confused with a status selection)
            dep_ids = {r.factor_id for r in sel.records
                       if r.selection_role == "dependency" and not r.selected and r.dependency_included}
            self.assertTrue(set(components).issubset(dep_ids))

            # get_factors() is the STRICT base-status filter: no base is `candidate`,
            # so the dependency bases are EXCLUDED from the plain reader.
            gf = get_factors(stage="sandbox_screening", status_in={"candidate"},
                             include_new_data=True, registry_dir=d)
            for comp_base in components:
                self.assertNotIn(comp_base, gf)

    # ── P3.2: sync_catalog_to_registry parity + dry-run ────────────────────
    def test_sync_catalog_to_registry_parity_and_dry_run(self):
        from src.alpha_research.factor_library import sync_catalog_to_registry
        with self._temp_dir("sel_sync") as d:
            # dry_run on an empty registry: reports the full catalog as would-be drafts,
            # writes NOTHING (a read still raises not-synced afterwards).
            from src.alpha_research.factor_library.catalog import catalog_composition
            total = catalog_composition()["total"]  # derived, not hard-coded
            dry = sync_catalog_to_registry(registry_dir=d, dry_run=True)
            self.assertTrue(dry["dry_run"])
            self.assertEqual(len(dry["new_drafts"]), total)
            self.assertFalse(dry["parity_ok"])
            with self.assertRaises(RegistryNotSyncedError):
                get_factors(stage="sandbox_screening", status_in={"draft"}, registry_dir=d)

            # real sync: full-catalog draft rows, reaches parity
            res = sync_catalog_to_registry(registry_dir=d, record_run=False)
            self.assertFalse(res["dry_run"])
            self.assertEqual(res["synced"], total)
            self.assertEqual(len(res["new_drafts"]), total)
            self.assertEqual(res["catalog_only"], [])
            self.assertEqual(res["registry_only"], [])
            self.assertTrue(res["parity_ok"])

            # never writes `approved` (Phase-1 writer gate stands): all rows draft
            store = FactorRegistryStore(d)
            cur = store.factor_master[store.factor_master["is_current"].fillna(False)]
            self.assertEqual(set(cur["status"]), {"draft"})

            # a second dry_run now shows parity and still writes nothing
            dry2 = sync_catalog_to_registry(registry_dir=d, dry_run=True)
            self.assertTrue(dry2["parity_ok"])
            self.assertEqual(dry2["new_drafts"], [])

    def test_sync_parity_ok_false_when_registry_only_orphan_present(self):
        # GPT PR-#32 finding 1: an orphan current registry row (a factor removed from
        # code but still is_current) is a parity violation — parity_ok must be False even
        # when catalog_only and drifted are empty. (Pre-fix parity_ok ignored
        # registry_only, so this asserted False where the buggy code returned True.)
        import pandas as pd
        from src.alpha_research.factor_library import sync_catalog_to_registry
        with self._temp_dir("sel_sync_orphan") as d:
            store = self._synced_store(d)
            ghost = store.factor_master[store.factor_master["is_current"].fillna(False)].iloc[0].copy()
            ghost["factor_id"] = "ghost_removed_from_code"
            ghost["version"] = 1
            store.factor_master = pd.concat(
                [store.factor_master, pd.DataFrame([ghost])], ignore_index=True
            )
            store.save()
            rep = sync_catalog_to_registry(registry_dir=d, dry_run=True)
            self.assertIn("ghost_removed_from_code", rep["registry_only"])
            self.assertEqual(rep["catalog_only"], [])   # the code catalog is fully present
            self.assertEqual(rep["new_versions"], [])    # nothing drifted
            self.assertFalse(rep["parity_ok"])           # but NOT parity: orphan present

    # ── P3.1: prioritize ordering ──────────────────────────────────────────
    def test_prioritize_orders_without_filtering(self):
        with self._temp_dir("sel_prio") as d:
            self._synced_store(d)
            base = get_factors(stage="sandbox_screening", status_in={"draft"},
                               include_new_data=True, registry_dir=d)
            prio = get_factors(stage="sandbox_screening", status_in={"draft"},
                               include_new_data=True, registry_dir=d,
                               prioritize="long_only_viable_provisional")
            self.assertEqual(set(base), set(prio))  # same set, possibly different order
            with self.assertRaises(ValueError):
                get_factors(stage="sandbox_screening", status_in={"draft"},
                            include_new_data=True, registry_dir=d, prioritize="bogus_key")


if __name__ == "__main__":
    unittest.main()
