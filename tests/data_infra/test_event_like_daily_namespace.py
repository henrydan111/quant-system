"""Regression tests for the event-like daily endpoint namespace fix.

Background: `_materialize_daily_dataset` writes one `.day.bin` per
numeric column using the column name verbatim. It runs AFTER
`_run_dump_bin` writes the canonical `$open/$high/$low/$close/$vol/$amount`
bins from kline data. Several "event-like" daily endpoints
(`top_list`, `top_inst`, `block_trade`, `cyq_perf`) ship numeric
columns whose names collide with canonical kline fields — e.g.,
`top_list` has `close` / `amount`, `block_trade` has `vol` / `amount`.
Without namespacing, those rows silently overwrite the canonical bins
on every event day, silently corrupting the factor feed for any
stock that ever appeared on 龙虎榜 or 大宗交易.

The fix lives in `src/data_infra/pit_backend.py`:
`EVENT_LIKE_DAILY_FIELD_PREFIX` + the rename block inside
`_materialize_daily_dataset`. This test suite enforces:

1. Every event-like dataset gets a prefix entry.
2. The rename step actually fires for those datasets and the payload
   columns on disk carry the `{dataset}__` prefix.
3. No numeric column from any event-like dataset can ever collide with
   the canonical kline field set.
"""

from pathlib import Path
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from data_infra.pit_backend import (  # noqa: E402
    CANONICAL_KLINE_FIELDS,
    EVENT_LIKE_DAILY_DATASETS,
    EVENT_LIKE_DAILY_FIELD_PREFIX,
    StagedQlibBackendBuilder,
    _EVENT_LIKE_RESERVED_COLUMNS,
    payload_numeric_columns,
)


# --------------------------------------------------------------------------- #
# Static invariants                                                            #
# --------------------------------------------------------------------------- #


def test_every_event_like_dataset_has_a_prefix_entry():
    """Every dataset we flagged as event-like must have a namespace prefix."""
    missing = EVENT_LIKE_DAILY_DATASETS - set(EVENT_LIKE_DAILY_FIELD_PREFIX)
    assert not missing, (
        f"event-like daily datasets missing from EVENT_LIKE_DAILY_FIELD_PREFIX: {sorted(missing)}. "
        "If a new endpoint is added to EVENT_LIKE_DAILY_DATASETS it MUST also receive a "
        "namespace prefix — otherwise its numeric columns can silently shadow canonical "
        "kline .day.bin files."
    )


def test_prefix_keys_match_event_like_dataset_set():
    """Prefix map must not contain stray datasets."""
    extras = set(EVENT_LIKE_DAILY_FIELD_PREFIX) - EVENT_LIKE_DAILY_DATASETS
    assert not extras, (
        f"EVENT_LIKE_DAILY_FIELD_PREFIX has datasets not in EVENT_LIKE_DAILY_DATASETS: "
        f"{sorted(extras)}"
    )


def test_prefix_values_are_well_formed():
    for dataset_name, prefix in EVENT_LIKE_DAILY_FIELD_PREFIX.items():
        assert prefix.startswith(dataset_name), (
            f"{dataset_name}: prefix {prefix!r} should start with the dataset name so the "
            "on-disk .day.bin filename is self-describing."
        )
        assert prefix.endswith("__"), (
            f"{dataset_name}: prefix {prefix!r} should end with '__' so the boundary "
            "between dataset name and payload column is visually obvious."
        )


def test_canonical_kline_fields_covers_all_shadowing_risks():
    """Anything the dump_bin price stager could emit must be in the guard set."""
    required = {"open", "high", "low", "close", "vol", "amount", "factor", "volume"}
    missing = required - CANONICAL_KLINE_FIELDS
    assert not missing, f"CANONICAL_KLINE_FIELDS missing known kline columns: {sorted(missing)}"


# --------------------------------------------------------------------------- #
# Behavioral: rename actually fires for every known-risky column.              #
# --------------------------------------------------------------------------- #


# Columns observed in production Tushare responses for each endpoint, as of
# 2026-04-16 (see scripts/fetch_new_alpha_endpoints.py and the stored parquet
# partitions under data/market/{top_list,top_inst,block_trade,cyq_perf}/).
# The subsets below are the numeric payload columns — identity columns
# (ts_code, trade_date) are intentionally excluded because those must NOT
# be renamed.
_SYNTHETIC_PAYLOADS: dict[str, dict[str, list[float]]] = {
    "top_list": {
        # Direct collisions with canonical kline: close, amount.
        "close": [12.34, 12.56],
        "pct_change": [1.2, -0.8],
        "turnover_rate": [3.4, 4.5],
        "amount": [1.2e8, 9.8e7],
        "l_sell": [2.0e7, 1.5e7],
        "l_buy": [3.0e7, 4.0e7],
        "l_amount": [5.0e7, 5.5e7],
        "net_amount": [1.0e7, 2.5e7],
        "net_rate": [0.11, 0.22],
        "amount_rate": [0.05, 0.07],
        "float_values": [1.0e9, 1.1e9],
    },
    "top_inst": {
        "buy": [1.0e7, 2.0e7],
        "buy_rate": [0.01, 0.02],
        "sell": [5.0e6, 6.0e6],
        "sell_rate": [0.005, 0.006],
        "net_buy": [5.0e6, 1.4e7],
    },
    "block_trade": {
        # Direct collisions with canonical kline: vol, amount.
        "price": [12.0, 12.5],
        "vol": [1000.0, 2000.0],
        "amount": [1.2e4, 2.5e4],
    },
    "cyq_perf": {
        # cyq_perf does not collide with kline today, but a future schema
        # change could introduce one. We still prefix all payload cols
        # for uniformity.
        "his_low": [5.0, 5.1],
        "his_high": [20.0, 20.5],
        "cost_5pct": [8.0, 8.1],
        "cost_50pct": [12.0, 12.1],
        "cost_95pct": [18.0, 18.1],
        "weight_avg": [11.5, 11.6],
        "winner_rate": [0.55, 0.58],
    },
}


def _build_synthetic_daily(dataset_name: str) -> pd.DataFrame:
    payload = _SYNTHETIC_PAYLOADS[dataset_name]
    frame = pd.DataFrame(
        {
            "ts_code": ["000001.SZ"] * 2,
            "trade_date": pd.to_datetime(["2024-01-02", "2024-01-03"]),
            **{column: values for column, values in payload.items()},
        }
    )
    return frame


def test_no_event_like_payload_column_collides_with_canonical_kline():
    """Guard: if a synthetic payload for any event-like dataset contains a column
    whose NAMESPACED name still collides with canonical kline, we have a bug in
    either the prefix string or the canonical set. The unnamespaced names will
    collide (that's the whole point of the fix); the namespaced ones must NOT.
    """
    for dataset_name, payload in _SYNTHETIC_PAYLOADS.items():
        prefix = EVENT_LIKE_DAILY_FIELD_PREFIX[dataset_name]
        namespaced = {f"{prefix}{column}" for column in payload}
        collisions = namespaced & CANONICAL_KLINE_FIELDS
        assert not collisions, (
            f"{dataset_name}: namespaced columns {sorted(collisions)} still collide with "
            f"canonical kline. Prefix {prefix!r} is insufficient."
        )


def test_rename_block_fires_for_every_event_like_dataset(monkeypatch, tmp_path):
    """End-to-end: feed a synthetic daily DataFrame into _materialize_daily_dataset,
    capture every `field_name` passed to `_write_feature_series`, and assert:
    - every original payload column appears only in its prefixed form on disk
    - no canonical kline field name is ever written from this code path
    """
    for dataset_name in sorted(EVENT_LIKE_DAILY_DATASETS):
        prefix = EVENT_LIKE_DAILY_FIELD_PREFIX[dataset_name]
        synthetic = _build_synthetic_daily(dataset_name)
        original_payload_cols = set(_SYNTHETIC_PAYLOADS[dataset_name])

        # Minimal builder instance — we only need the materializer method and
        # its small dependencies. Avoid __init__ side effects by using object
        # construction + attribute injection, since StagedQlibBackendBuilder's
        # real __init__ expects a full data-root layout.
        builder = StagedQlibBackendBuilder.__new__(StagedQlibBackendBuilder)
        builder.field_filter = None
        builder._bin_ref_cache = {}

        # Stub the loader so _materialize_daily_dataset sees our fixture.
        monkeypatch.setattr(
            builder,
            "load_normalized_daily",
            lambda name, frame=synthetic: frame.copy(),
            raising=False,
        )
        # northbound branch never fires for event-like datasets; do not stub.
        # expected_empty_dates is also only consulted for northbound.

        # Record every field passed to _write_feature_series.
        written_fields: list[str] = []

        def _fake_write(feature_dir, field_name, values):  # noqa: ARG001
            written_fields.append(field_name)

        monkeypatch.setattr(builder, "_write_feature_series", _fake_write, raising=False)

        calendar = pd.DatetimeIndex(pd.to_datetime(["2024-01-02", "2024-01-03"]))
        feature_dir = tmp_path / dataset_name / "000001_sz"
        feature_dir.mkdir(parents=True, exist_ok=True)
        target_dirs = {"000001_sz": str(feature_dir)}

        builder._materialize_daily_dataset(dataset_name, calendar, target_dirs)

        written = set(written_fields)
        # Every written field must carry the dataset prefix.
        non_prefixed = {name for name in written if not name.startswith(prefix)}
        assert not non_prefixed, (
            f"{dataset_name}: _write_feature_series was invoked with un-prefixed "
            f"field names {sorted(non_prefixed)} — the rename block did not fire."
        )
        # Every synthetic payload column must have been written in its
        # namespaced form.
        expected = {f"{prefix}{column}" for column in original_payload_cols}
        missing = expected - written
        assert not missing, (
            f"{dataset_name}: expected namespaced fields {sorted(missing)} were "
            f"never written. Got {sorted(written)}."
        )
        # No canonical kline field may be written through this path.
        shadows = written & CANONICAL_KLINE_FIELDS
        assert not shadows, (
            f"{dataset_name}: event-like materializer wrote canonical kline "
            f"fields {sorted(shadows)} — this would overwrite _run_dump_bin output."
        )


def test_non_event_like_daily_datasets_keep_original_names(monkeypatch, tmp_path):
    """Regression guard: existing datasets (moneyflow, northbound, margin,
    stk_limit) are NOT prefixed. Consumers read those fields by their native
    name today — prefixing them would be a breaking change.
    """
    # Synthetic payload: pick a column that does NOT collide with kline.
    synthetic = pd.DataFrame(
        {
            "ts_code": ["000001.SZ"] * 2,
            "trade_date": pd.to_datetime(["2024-01-02", "2024-01-03"]),
            "buy_sm_amount": [1.0, 2.0],
        }
    )

    builder = StagedQlibBackendBuilder.__new__(StagedQlibBackendBuilder)
    builder.field_filter = None
    builder._bin_ref_cache = {}
    monkeypatch.setattr(
        builder, "load_normalized_daily", lambda name: synthetic.copy(), raising=False
    )

    written_fields: list[str] = []
    monkeypatch.setattr(
        builder,
        "_write_feature_series",
        lambda feature_dir, field_name, values: written_fields.append(field_name),
        raising=False,
    )

    calendar = pd.DatetimeIndex(pd.to_datetime(["2024-01-02", "2024-01-03"]))
    feature_dir = tmp_path / "moneyflow" / "000001_sz"
    feature_dir.mkdir(parents=True, exist_ok=True)
    target_dirs = {"000001_sz": str(feature_dir)}

    builder._materialize_daily_dataset("moneyflow", calendar, target_dirs)

    # Verify the native name was preserved — no prefix applied to moneyflow.
    assert "buy_sm_amount" in written_fields, (
        f"moneyflow payload column 'buy_sm_amount' was not written verbatim. Got: {written_fields}. "
        "Non-event-like datasets MUST keep their original column names to avoid breaking "
        "downstream consumers."
    )
    prefixed = [name for name in written_fields if name.startswith("moneyflow__")]
    assert not prefixed, (
        f"moneyflow wrote prefixed fields {prefixed} — only event-like datasets should be prefixed."
    )


def test_reserved_columns_never_get_prefixed():
    """ts_code / trade_date / qlib_code are identity/date columns. Prefixing
    them would break the downstream groupby(ts_code) and reindex(trade_date)
    calls inside _materialize_daily_dataset.
    """
    assert "ts_code" in _EVENT_LIKE_RESERVED_COLUMNS
    assert "trade_date" in _EVENT_LIKE_RESERVED_COLUMNS
    assert "qlib_code" in _EVENT_LIKE_RESERVED_COLUMNS


def test_payload_numeric_columns_sees_prefixed_names_after_rename():
    """End-to-end shape check: after renaming, payload_numeric_columns returns
    the prefixed names — the downstream `numeric_fields` list that drives the
    per-stock reindex/write loop is therefore namespaced by construction.
    """
    for dataset_name in sorted(EVENT_LIKE_DAILY_DATASETS):
        prefix = EVENT_LIKE_DAILY_FIELD_PREFIX[dataset_name]
        frame = _build_synthetic_daily(dataset_name)
        rename_map = {
            column: f"{prefix}{column}"
            for column in frame.columns
            if column not in _EVENT_LIKE_RESERVED_COLUMNS
        }
        renamed = frame.rename(columns=rename_map)
        numerics = set(payload_numeric_columns(renamed))
        original_numerics = set(_SYNTHETIC_PAYLOADS[dataset_name])
        assert numerics == {f"{prefix}{col}" for col in original_numerics}, (
            f"{dataset_name}: payload_numeric_columns returned {sorted(numerics)}, "
            f"expected {sorted(f'{prefix}{c}' for c in original_numerics)}"
        )
