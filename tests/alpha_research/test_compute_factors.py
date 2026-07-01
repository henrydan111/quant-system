import sys
import types
import unittest
from pathlib import Path
from unittest.mock import mock_open, patch

import pandas as pd

# Pre-import the pyarrow-backed parquet machinery BEFORE any
# patch.dict(sys.modules, ...) block below. patch.dict restores sys.modules to
# its pre-block snapshot on exit, evicting modules first imported INSIDE the
# block. compute_factors now routes through qlib_windowed_features →
# cache_manifest → pd.read_parquet, whose first call lazily imports
# pandas.core.arrays.arrow.extension_types; that module registers pyarrow
# extension types at import time, and a forced re-import in the next test
# raises ArrowKeyError ("pandas.period already defined") because pyarrow's
# global registry survives the eviction.
import pandas.core.arrays.arrow.extension_types  # noqa: F401
import pyarrow.parquet  # noqa: F401

import src.alpha_research.factor_library as factor_library
import src.alpha_research.factor_library.catalog as factor_catalog_module
from src.alpha_research.factor_library import operators
import workspace.research.alpha_mining.batch_factor_screening_latest_backend as latest_backend_wrapper
import workspace.scripts.batch_factor_screening as batch_factor_screening


def _sample_feature_frame():
    index = pd.MultiIndex.from_tuples(
        [("000001_SZ", pd.Timestamp("2024-01-02"))],
        names=["instrument", "datetime"],
    )
    return pd.DataFrame([[1.23]], index=index)


class ComputeFactorsFallbackTests(unittest.TestCase):
    def _build_fake_modules(self, features_impl, init_calls, init_impl=None):
        fake_qlib = types.ModuleType("qlib")

        def fake_init(default_conf="client", **kwargs):
            init_calls.append(kwargs.copy())
            if init_impl is not None:
                return init_impl(default_conf=default_conf, **kwargs)
            return None

        fake_qlib.init = fake_init

        fake_data_module = types.ModuleType("qlib.data")
        fake_data_module.D = types.SimpleNamespace(
            instruments=lambda market="all_stocks": ["000001_SZ"],
            features=features_impl,
        )

        fake_config_module = types.ModuleType("qlib.config")
        fake_config_module.REG_CN = "cn"
        return {
            "qlib": fake_qlib,
            "qlib.data": fake_data_module,
            "qlib.config": fake_config_module,
        }

    def test_compute_factors_falls_back_to_single_worker_on_permission_error(self):
        init_calls = []
        feature_calls = {"count": 0}

        def fake_features(instruments, fields, start_time=None, end_time=None):
            feature_calls["count"] += 1
            if feature_calls["count"] == 1:
                raise PermissionError(5, "Access is denied while creating Pipe")
            return _sample_feature_frame()

        fake_modules = self._build_fake_modules(fake_features, init_calls)

        with patch.dict(sys.modules, fake_modules, clear=False):
            factors_df, fwd_df = operators.compute_factors(
                {"alpha": "$close"},
                "2024-01-01",
                "2024-01-10",
                horizons=None,
                qlib_dir="E:/fake/qlib_data",
                kernels=None,
                progress_interval=0,
            )

        self.assertEqual(feature_calls["count"], 2)
        self.assertEqual(len(init_calls), 2)
        self.assertNotIn("kernels", init_calls[0])
        self.assertEqual(init_calls[1]["kernels"], 1)
        self.assertEqual(list(factors_df.columns), ["alpha"])
        self.assertTrue(fwd_df.empty)
        self.assertEqual(factors_df.attrs["qlib_requested_kernels"], "qlib default")
        self.assertEqual(factors_df.attrs["qlib_effective_kernels"], "1")
        self.assertEqual(fwd_df.attrs["qlib_requested_kernels"], "qlib default")
        self.assertEqual(fwd_df.attrs["qlib_effective_kernels"], "1")

    def test_compute_factors_keeps_parallel_mode_when_it_succeeds(self):
        init_calls = []

        def fake_features(instruments, fields, start_time=None, end_time=None):
            return _sample_feature_frame()

        fake_modules = self._build_fake_modules(fake_features, init_calls)

        with patch.dict(sys.modules, fake_modules, clear=False):
            factors_df, _ = operators.compute_factors(
                {"alpha": "$close"},
                "2024-01-01",
                "2024-01-10",
                horizons=None,
                qlib_dir="E:/fake/qlib_data",
                kernels=None,
                progress_interval=0,
            )

        self.assertEqual(len(init_calls), 1)
        self.assertNotIn("kernels", init_calls[0])
        self.assertEqual(factors_df.attrs["qlib_requested_kernels"], "qlib default")
        self.assertEqual(factors_df.attrs["qlib_effective_kernels"], "qlib default")

    def test_compute_factors_falls_back_on_permission_like_worker_oserror(self):
        init_calls = []
        feature_calls = {"count": 0}

        def fake_features(instruments, fields, start_time=None, end_time=None):
            feature_calls["count"] += 1
            if feature_calls["count"] == 1:
                raise OSError(
                    "Access is denied while joblib creates a multiprocessing pipe"
                )
            return _sample_feature_frame()

        fake_modules = self._build_fake_modules(fake_features, init_calls)

        with patch.dict(sys.modules, fake_modules, clear=False):
            factors_df, _ = operators.compute_factors(
                {"alpha": "$close"},
                "2024-01-01",
                "2024-01-10",
                horizons=None,
                qlib_dir="E:/fake/qlib_data",
                kernels=None,
                progress_interval=0,
            )

        self.assertEqual(feature_calls["count"], 2)
        self.assertEqual(len(init_calls), 2)
        self.assertNotIn("kernels", init_calls[0])
        self.assertEqual(init_calls[1]["kernels"], 1)
        self.assertEqual(factors_df.attrs["qlib_requested_kernels"], "qlib default")
        self.assertEqual(factors_df.attrs["qlib_effective_kernels"], "1")

    def test_compute_factors_retries_when_qlib_init_hits_permission_like_worker_error(self):
        init_calls = []

        def fake_features(instruments, fields, start_time=None, end_time=None):
            return _sample_feature_frame()

        def fake_init_impl(default_conf="client", **kwargs):
            if len(init_calls) == 1:
                raise OSError(
                    "Access is denied while joblib creates a multiprocessing pipe"
                )

        fake_modules = self._build_fake_modules(
            fake_features,
            init_calls,
            init_impl=fake_init_impl,
        )

        with patch.dict(sys.modules, fake_modules, clear=False):
            factors_df, _ = operators.compute_factors(
                {"alpha": "$close"},
                "2024-01-01",
                "2024-01-10",
                horizons=None,
                qlib_dir="E:/fake/qlib_data",
                kernels=None,
                progress_interval=0,
            )

        self.assertEqual(len(init_calls), 2)
        self.assertNotIn("kernels", init_calls[0])
        self.assertEqual(init_calls[1]["kernels"], 1)
        self.assertEqual(factors_df.attrs["qlib_requested_kernels"], "qlib default")
        self.assertEqual(factors_df.attrs["qlib_effective_kernels"], "1")

    def test_compute_factors_threads_stage_kwarg_to_qlib_windowed_features(self):
        """Gate 0 regression (jolly-seeking-lollipop):
        compute_factors must thread the stage parameter through to
        qlib_windowed_features so cache_manifest enforcement is correctly
        stage-tagged. Default is is_only (backward compat); explicit oos_test
        must propagate. Source-inspection style to avoid pyarrow extension
        collisions caused by importing real qlib modules in this test process.
        """
        import inspect

        sig = inspect.signature(operators.compute_factors)
        self.assertIn("stage", sig.parameters)
        self.assertEqual(sig.parameters["stage"].default, "is_only")

        src = inspect.getsource(operators.compute_factors)
        # Must use the parameter, not a hardcoded literal, when calling
        # qlib_windowed_features. The signature and docstring may contain
        # 'is_only' as the default value; that's expected. The smoking gun
        # for the leak is whether the call site uses `stage=stage`.
        self.assertIn("stage=stage", src)

    def test_compute_factors_does_not_silently_downgrade_explicit_kernel_requests(self):
        init_calls = []

        def fake_features(instruments, fields, start_time=None, end_time=None):
            raise PermissionError(5, "Access is denied while creating Pipe")

        fake_modules = self._build_fake_modules(fake_features, init_calls)

        with patch.dict(sys.modules, fake_modules, clear=False):
            with self.assertRaises(PermissionError):
                operators.compute_factors(
                    {"alpha": "$close"},
                    "2024-01-01",
                    "2024-01-10",
                    horizons=None,
                    qlib_dir="E:/fake/qlib_data",
                    kernels=4,
                    progress_interval=0,
                )

        self.assertEqual(len(init_calls), 1)
        self.assertEqual(init_calls[0]["kernels"], 4)


class BatchFactorScreeningKernelMetadataTests(unittest.TestCase):
    def test_alpha_mining_wrapper_defaults_to_qlib_default_workers(self):
        args = latest_backend_wrapper.build_default_args()

        self.assertEqual(args[args.index("--kernels") + 1], "0")
        self.assertEqual(args[args.index("--end") + 1], "auto")
        self.assertEqual(args[args.index("--cache-mode") + 1], "resume")
        self.assertEqual(
            Path(args[args.index("--qlib-dir") + 1]).resolve(),
            (latest_backend_wrapper.PROJECT_ROOT / "data" / "qlib_data").resolve(),
        )
        self.assertEqual(
            Path(args[args.index("--output-dir") + 1]).name,
            "latest_backend_screening",
        )

    def test_batch_screening_records_requested_and_effective_kernels(self):
        factor_index = pd.MultiIndex.from_tuples(
            [(pd.Timestamp("2024-01-02"), "000001_SZ")],
            names=["datetime", "instrument"],
        )
        factors_df = pd.DataFrame({"alpha": [1.23]}, index=factor_index)
        factors_df.attrs["qlib_requested_kernels"] = "qlib default"
        factors_df.attrs["qlib_effective_kernels"] = "1"
        fwd_df = pd.DataFrame(index=factor_index)
        fwd_df.attrs["qlib_requested_kernels"] = "qlib default"
        fwd_df.attrs["qlib_effective_kernels"] = "1"
        results_df = pd.DataFrame({"grade": ["A (Graduated)"]}, index=["alpha"])

        cached_states = []
        json_writes = []
        logged_messages = []

        def capture_stage_cache(meta_path, cache_key, state, data_writers):
            cached_states.append(
                {
                    "meta_path": str(meta_path),
                    "cache_key": dict(cache_key),
                    "state": dict(state),
                }
            )

        def capture_json(path, payload):
            json_writes.append({"path": str(path), "payload": dict(payload)})

        def capture_info(message, *args, **kwargs):
            if args:
                message = message % args
            logged_messages.append(message)

        # Import before patching pathlib.Path.mkdir; jsonschema/lark may touch
        # package caches during orchestrator import.
        import src.research_orchestrator.engine  # noqa: F401

        with (
            patch.object(
                batch_factor_screening,
                "_resolve_latest_backend_end_date",
                return_value="2024-01-31",
            ),
            patch.object(
                batch_factor_screening,
                "_dir_signature",
                return_value={"path": "E:/fake/qlib_data", "file_count": 1, "latest_mtime_ns": 1},
            ),
            patch.object(
                batch_factor_screening,
                "_build_code_fingerprint",
                return_value={"files": {}, "hash": "test-hash"},
            ),
            patch.object(batch_factor_screening, "_write_stage_cache", side_effect=capture_stage_cache),
            patch.object(batch_factor_screening, "_atomic_write_json", side_effect=capture_json),
            patch.object(batch_factor_screening, "run_batch_screening", return_value=results_df),
            patch.object(batch_factor_screening, "generate_report", return_value=(results_df, "summary")),
            patch.object(batch_factor_screening.logger, "info", side_effect=capture_info),
            patch.object(factor_library, "get_factor_catalog", return_value={"alpha": "$close"}),
            patch.object(factor_library, "compute_factors", return_value=(factors_df, fwd_df)),
            patch.object(
                factor_library,
                "add_composites",
                side_effect=lambda df, composite_defs=None, progress_every=5: df,
            ),
            patch.object(factor_catalog_module, "get_composite_defs", return_value=[]),
            patch("pandas.DataFrame.to_parquet"),
            patch("pandas.DataFrame.to_csv"),
            patch("pathlib.Path.mkdir"),
            patch("builtins.open", mock_open()),
        ):
            batch_factor_screening.run_factor_screening_pipeline(
                [
                    "--start", "2024-01-01",
                    "--end", "auto",
                    "--horizon", "5",
                    "--kernels", "0",
                    "--cache-mode", "refresh",
                    "--output-dir", "workspace/outputs/test_kernel_metadata",
                    "--cache-dir", "workspace/outputs/test_kernel_metadata/cache",
                    "--qlib-dir", "data/qlib_data",
                ]
            )

        factor_cache_state = next(
            item["state"]
            for item in cached_states
            if item["state"].get("requested_kernels") == "qlib default"
        )
        self.assertEqual(factor_cache_state["effective_kernels"], "1")

        final_metadata = json_writes[-1]["payload"]
        self.assertEqual(final_metadata["requested_kernels"], "qlib default")
        self.assertEqual(final_metadata["effective_kernels"], "1")
        self.assertIn(
            "Factor compute kernels: requested=qlib default, effective=1",
            logged_messages,
        )


if __name__ == "__main__":
    unittest.main()
