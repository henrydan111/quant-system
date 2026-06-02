"""Phase 4 slice 3 — historical (mode-2) revalidate_panel + report CSV contract.

`revalidate_panel` is the data-loading-free core (testable without Qlib). `report.py`
renders the exact legacy CSV columns/rounding so Phase-2 `import_revalidation` keeps
consuming the output (round-trip proven here).
"""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.alpha_research.factor_lifecycle import report
from src.alpha_research.factor_lifecycle.revalidation import revalidate_panel
from src.alpha_research.factor_lifecycle.status_rules import assign_historical_status
from src.alpha_research.factor_library.catalog import get_composite_defs
from src.alpha_research.factor_registry import FactorRegistryStore

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_OUTPUTS = PROJECT_ROOT / "workspace" / "outputs"


def _is_oos_panel(seed: int = 1):
    instruments = [f"{i:06d}_SZ" for i in range(100)]
    # 60 months spanning 2018-2022 -> IS (<=2020-12-31) + OOS (>=2021-01-01) both populated
    dates = pd.date_range("2018-01-31", periods=60, freq="ME")
    index = pd.MultiIndex.from_product([instruments, dates], names=["instrument", "datetime"])
    rng = np.random.default_rng(seed)
    fwd = pd.Series(rng.standard_normal(len(index)), index=index)
    # one aligned factor (predicts fwd) + one degenerate (all NaN -> no IC -> draft)
    aligned = 0.6 * fwd + 0.4 * pd.Series(rng.standard_normal(len(index)), index=index)
    degenerate = pd.Series(np.nan, index=index)
    panel = pd.DataFrame({"f_aligned": aligned, "f_degenerate": degenerate})
    return panel, fwd


class RevalidatePanelTests(unittest.TestCase):
    def test_catalog_mode_columns_and_status_self_consistency(self):
        panel, fwd = _is_oos_panel()
        df = revalidate_panel(
            panel, fwd, is_end="2020-12-31", oos_start="2021-01-01",
            field_eligible={c: True for c in panel.columns},
        )
        for col in ("factor", "field_eligible", "full_rank_icir", "is_rank_icir",
                    "oos_rank_icir", "sign_consistency", "n_years", "status", "reason"):
            self.assertIn(col, df.columns)
        # the degenerate factor -> draft / no IC
        deg = df[df["factor"] == "f_degenerate"].iloc[0]
        self.assertEqual(deg["status"], "draft")
        self.assertEqual(int(deg["n_years"]), 0)
        # every row's status equals the rule recomputed from its own metrics (port applied
        # assign_historical_status faithfully)
        for _, r in df.iterrows():
            expected, _ = assign_historical_status(
                bool(r["field_eligible"]), r["is_rank_icir"], r["oos_rank_icir"], r["sign_consistency"],
            )
            self.assertEqual(r["status"], expected)

    def test_field_ineligible_capped_at_draft(self):
        panel, fwd = _is_oos_panel()
        df = revalidate_panel(
            panel, fwd, is_end="2020-12-31", oos_start="2021-01-01",
            field_eligible={"f_aligned": False, "f_degenerate": False},
        )
        self.assertTrue((df["status"] == "draft").all())

    def test_derived_mode_has_kind_and_long_only_columns(self):
        panel, fwd = _is_oos_panel()
        df = revalidate_panel(
            panel, fwd, is_end="2020-12-31", oos_start="2021-01-01",
            kinds={"f_aligned": "composite", "f_degenerate": "industry_rel"},
            compute_long_only=True,
        )
        for col in ("kind", "lo_excess_ann", "lo_sharpe", "lo_hit"):
            self.assertIn(col, df.columns)
        self.assertEqual(df[df["factor"] == "f_aligned"].iloc[0]["kind"], "composite")


class ReportContractTests(unittest.TestCase):
    def test_catalog_frame_columns_rounding_and_sort(self):
        panel, fwd = _is_oos_panel()
        raw = revalidate_panel(panel, fwd, is_end="2020-12-31", oos_start="2021-01-01",
                               field_eligible={c: True for c in panel.columns})
        frame = report.to_catalog_frame(raw)
        self.assertEqual(list(frame.columns), report.CATALOG_COLUMNS)
        # rounding: 4 dp for ICIR columns (a populated value has <= 4 decimals)
        v = frame["full_rank_icir"].dropna().iloc[0]
        self.assertEqual(round(float(v), 4), float(v))
        # sorted by status ascending
        statuses = list(frame["status"])
        self.assertEqual(statuses, sorted(statuses))

    def test_round_trip_through_phase2_import(self):
        # a derived CSV rendered by report.py must be consumable by Phase-2 import_revalidation
        comp_name = str(get_composite_defs()[0]["name"])
        raw = pd.DataFrame([{
            "factor": comp_name, "kind": "composite", "full_rank_icir": 0.123456,
            "is_rank_icir": 0.2, "oos_rank_icir": 0.31, "sign_consistency": 0.8,
            "status": "candidate", "reason": "x",
            "lo_excess_ann": 0.12, "lo_sharpe": 1.4, "lo_hit": 0.66,
        }])
        WORKSPACE_OUTPUTS.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="p4_roundtrip_", dir=WORKSPACE_OUTPUTS) as d:
            csv_path = Path(d) / "derived_revalidation_status.csv"
            report.write_derived_csv(raw, csv_path)
            store = FactorRegistryStore(d)
            store.sync_catalog(record_run=False, generated_at="2026-04-04 21:00:00")
            store.save()
            rep = store.import_revalidation(derived_csv=csv_path, run_id="p4_rt")
            self.assertIn(comp_name, rep["attached"])
            ev = store.factor_evidence[
                (store.factor_evidence["factor_id"] == comp_name)
                & (store.factor_evidence["run_type"] == "revalidation")
            ]
            self.assertEqual(len(ev), 1)
            self.assertAlmostEqual(float(ev.iloc[0]["lo_sharpe_gross"]), 1.4)
            self.assertEqual(ev.iloc[0]["evidence_class"], "historical_investigation")


class OrchestrationSmokeTests(unittest.TestCase):
    def test_run_historical_catalog_revalidation_mocked(self):
        # de-risk the orchestration glue (field_eligible + fwd extraction + revalidate_panel
        # wiring) without Qlib by injecting compute_factors_fn.
        from src.alpha_research.factor_lifecycle.revalidation import run_historical_catalog_revalidation
        from src.alpha_research.factor_library.catalog import get_factor_catalog

        names = list(get_factor_catalog(include_new_data=True))
        insts = [f"{i:06d}_SZ" for i in range(60)]
        dates = pd.date_range("2018-01-31", periods=48, freq="ME")  # spans IS + OOS
        idx = pd.MultiIndex.from_product([insts, dates], names=["instrument", "datetime"])
        rng = np.random.default_rng(7)
        fwd = pd.Series(rng.standard_normal(len(idx)), index=idx)
        panel = pd.DataFrame({n: rng.standard_normal(len(idx)) for n in names}, index=idx)

        def spy(*, catalog, start_date, end_date, horizons, **kw):
            return panel[list(catalog)], pd.DataFrame({"fwd_ret_20d": fwd})

        df = run_historical_catalog_revalidation(compute_factors_fn=spy)
        self.assertEqual(len(df), len(names))
        for col in ("factor", "field_eligible", "full_rank_icir", "is_rank_icir",
                    "oos_rank_icir", "sign_consistency", "n_years", "status", "reason"):
            self.assertIn(col, df.columns)
        self.assertTrue(set(df["status"]).issubset({"draft", "candidate", "deprecated"}))
        # field-ineligible factors (e.g. alpha endpoints) are present and capped at draft
        if (~df["field_eligible"].astype(bool)).any():
            self.assertTrue((df.loc[~df["field_eligible"].astype(bool), "status"] == "draft").all())


if __name__ == "__main__":
    unittest.main()
