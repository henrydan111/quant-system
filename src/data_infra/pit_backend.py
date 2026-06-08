"""Observed-data PIT backend builder for the local Qlib provider.

The builder enforces a staged workflow:

1. Raw input profiling with saved artifacts
2. Canonical normalization under ``data/normalized/``
3. Revision-aware PIT ledgers under ``data/pit_ledger/``
4. Staged Qlib provider builds under ``data/qlib_builds/<build_id>/``

It intentionally keeps the raw Parquet layout intact and preserves current
consumer-facing compatibility fields while adding revision-aware slot families.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from glob import glob
from typing import Any, Iterable, Literal

import numpy as np
import pandas as pd
import yaml
from tqdm import tqdm

from data_infra.provider_metadata import (
    build_all_stocks_universe,
    build_index_universes,
    build_st_universe,
    ensure_directory,
    ts_code_to_qlib,
    write_instruments_readme,
)
from data_infra.storage.qlib_bin_utils import get_bin_info, validate_stock_bins, write_qlib_bin

logger = logging.getLogger(__name__)

SLOT_DEPTH_DEFAULT = 5
CORE_METADATA_COLUMNS = {
    "ts_code",
    "qlib_code",
    "symbol",
    "trade_date",
    "date",
    "ann_date",
    "f_ann_date",
    "disclosure_date",
    "effective_date",
    "end_date",
    "report_type",
    "comp_type",
    "end_type",
    "update_flag",
    "type",
    "summary",
    "change_reason",
    "name",
    "exchange",
    "code",
    "record_date",
    "ex_date",
    "pay_date",
    "div_listdate",
    "imp_ann_date",
    "div_proc",
    "first_ann_date",
    "source_file",
    # P0-4: deterministic tie-break provenance columns (stripped before
    # normalized parquet write — see _normalize_periodic_dataset).
    "_src_file",
    "_src_ordinal",
}
NORTHBOUND_RENAMES = {"vol": "north_hold_vol"}
DIVIDEND_COMPAT_FIELDS = {"stk_div", "stk_bo_rate", "stk_co_rate", "cash_div", "cash_div_tax"}
KNOWN_INDEX_CODES = {"000001.SH", "000300.SH", "000688.SH", "000852.SH", "000905.SH"}
PHASE3_DATASETS = {
    "cashflow", "cashflow_quarterly", "forecast", "holder_number",
    "moneyflow", "northbound", "margin", "stk_limit",
    # New alpha endpoints (added 2026-04-14)
    "top_list", "top_inst", "block_trade", "stk_holdertrade", "cyq_perf",
    # 15000积分 expansion (P1, 2026-06-08): analyst forecasts (report_rc).
    "report_rc",
}
PERIODIC_LEDGER_DATASETS = {
    "income",
    "income_quarterly",
    "balancesheet",
    "indicators",
    "cashflow",
    "cashflow_quarterly",
    "forecast",
    "holder_number",
    "dividends",
    # New alpha endpoint (added 2026-04-16): event_periodic with per-holder
    # rows. Ledger key includes holder_name to avoid collapsing distinct
    # transactions on the same ann_date.
    "stk_holdertrade",
    # 15000积分 expansion (P1, 2026-06-08): analyst forecasts. event_periodic
    # with per-(analyst × forecast-quarter) rows; custom build_ledger key branch
    # (ts_code, report_date, normalized_analyst_id, quarter) avoids collapse.
    "report_rc",
}
EXPECTED_EMPTY_DATE_FILES = {
    "moneyflow": "moneyflow_known_empty_dates.txt",
    "northbound": "northbound_nonconnect_days.txt",
}
# daily_fact datasets that are event-driven (a date only has a file when the
# underlying event actually occurred that day): 龙虎榜, 大宗交易, 筹码分布,
# etc. The "expected open-calendar coverage" gate does not apply.
EVENT_LIKE_DAILY_DATASETS = {
    "top_list", "top_inst", "block_trade", "cyq_perf",
}
# Payload columns from these event-like daily endpoints share names with
# canonical kline fields (e.g., top_list has `close` and `amount`;
# block_trade has `vol` and `amount`). `_materialize_daily_dataset`
# writes one `.day.bin` per numeric column using the column name
# verbatim, AFTER `_run_dump_bin` has already written the canonical
# kline bins. Without namespacing, an event-day row silently overwrites
# `$close` / `$vol` / `$amount`. Every dataset in this mapping has its
# numeric columns prefixed with `{dataset}__` before materialization.
# Enforcement: tests/data_infra/test_event_like_daily_namespace.py.
EVENT_LIKE_DAILY_FIELD_PREFIX: dict[str, str] = {
    "top_list": "top_list__",
    "top_inst": "top_inst__",
    "block_trade": "block_trade__",
    "cyq_perf": "cyq_perf__",
}
# Reserved identity / date columns that must NOT receive the dataset
# prefix — the daily materializer joins on `ts_code` / `trade_date` and
# derives `qlib_code` from `ts_code` in `_standardize_common_columns`.
_EVENT_LIKE_RESERVED_COLUMNS = {"ts_code", "qlib_code", "trade_date"}
# Canonical kline fields written by `_run_dump_bin` via dump_bin.py.
# Any numeric column shipped through `_materialize_daily_dataset` that
# matches one of these would silently shadow the kline bin on disk.
CANONICAL_KLINE_FIELDS: frozenset[str] = frozenset({
    "open", "high", "low", "close", "vol", "volume", "amount",
    "vwap", "factor", "pre_close", "change", "pct_chg",
})
HOLDER_NUMBER_UNUSABLE_SUFFIX = "unusable_pit"
PRICE_REPAIR_OVERRIDES_FILE = "daily_price_repair_overrides.csv"


@dataclass(frozen=True)
class DerivedMetricSpec:
    """Canonical PIT-derived periodic metric."""

    output_name: str
    base_field: str
    comparison: Literal["yoy", "qoq"]


@dataclass(frozen=True)
class StatementFamilySpec:
    """Pair cumulative and quarterly ledgers under one financial family."""

    name: str
    kind: Literal["flow", "snapshot"]
    cumulative_dataset: str | None = None
    quarterly_dataset: str | None = None
    snapshot_dataset: str | None = None
    cumulative_metrics: tuple[DerivedMetricSpec, ...] = ()
    quarter_metrics: tuple[DerivedMetricSpec, ...] = ()

    def datasets(self) -> tuple[str, ...]:
        return tuple(
            dataset
            for dataset in (self.cumulative_dataset, self.quarterly_dataset, self.snapshot_dataset)
            if dataset is not None
        )


STATEMENT_FAMILIES: dict[str, StatementFamilySpec] = {
    "income": StatementFamilySpec(
        name="income",
        kind="flow",
        cumulative_dataset="income",
        quarterly_dataset="income_quarterly",
        cumulative_metrics=(
            DerivedMetricSpec("pit_or_yoy", "revenue", "yoy"),
            DerivedMetricSpec("pit_op_yoy", "operate_profit", "yoy"),
            DerivedMetricSpec("pit_netprofit_yoy", "n_income_attr_p", "yoy"),
            DerivedMetricSpec("pit_basic_eps_yoy", "basic_eps", "yoy"),
        ),
        quarter_metrics=(
            DerivedMetricSpec("pit_q_sales_yoy", "revenue", "yoy"),
            DerivedMetricSpec("pit_q_op_qoq", "operate_profit", "qoq"),
        ),
    ),
    "cashflow": StatementFamilySpec(
        name="cashflow",
        kind="flow",
        cumulative_dataset="cashflow",
        quarterly_dataset="cashflow_quarterly",
        cumulative_metrics=(DerivedMetricSpec("pit_ocf_yoy", "n_cashflow_act", "yoy"),),
    ),
    "balancesheet": StatementFamilySpec(
        name="balancesheet",
        kind="snapshot",
        snapshot_dataset="balancesheet",
    ),
}

DATASET_TO_STATEMENT_FAMILY = {
    dataset_name: family_name
    for family_name, family in STATEMENT_FAMILIES.items()
    for dataset_name in family.datasets()
}


@dataclass(frozen=True)
class DatasetSpec:
    """Observed contract for a raw dataset."""

    name: str
    raw_pattern: str
    kind: Literal[
        "price_daily",
        "index_daily",
        "reference",
        "universe",
        "daily_fact",
        "periodic_snapshot",
        "periodic_cumulative",
        "periodic_direct_sq",
        "event_periodic",
        "event_ledger",
    ]
    natural_keys: tuple[str, ...]
    required_columns: tuple[str, ...] = ()
    date_column: str | None = None
    ann_date_column: str | None = None
    f_ann_date_column: str | None = None
    end_date_column: str | None = None
    duplicate_key_columns: tuple[str, ...] = ()
    phase: int = 1
    materialize: bool = True
    allow_missing_raw: bool = False


DATASET_SPECS: dict[str, DatasetSpec] = {
    "trade_cal": DatasetSpec(
        name="trade_cal",
        raw_pattern="reference/trade_cal.parquet",
        kind="reference",
        natural_keys=("exchange", "cal_date"),
        required_columns=("exchange", "cal_date", "is_open"),
        date_column="cal_date",
        phase=1,
        materialize=False,
    ),
    "stock_basic": DatasetSpec(
        name="stock_basic",
        raw_pattern="reference/stock_basic.parquet",
        kind="reference",
        natural_keys=("ts_code",),
        required_columns=("ts_code", "exchange", "list_date"),
        phase=1,
        materialize=False,
    ),
    "namechange": DatasetSpec(
        name="namechange",
        raw_pattern="reference/namechange.parquet",
        kind="reference",
        natural_keys=("ts_code", "start_date", "ann_date", "name"),
        required_columns=("ts_code", "name", "start_date"),
        phase=1,
        materialize=False,
    ),
    "stock_st_daily": DatasetSpec(
        name="stock_st_daily",
        raw_pattern="reference/stock_st_daily.parquet",
        kind="reference",
        natural_keys=("ts_code", "trade_date"),
        required_columns=("ts_code", "trade_date"),
        date_column="trade_date",
        phase=1,
        materialize=False,
    ),
    "daily": DatasetSpec(
        name="daily",
        raw_pattern="market/daily/**/*.parquet",
        kind="price_daily",
        natural_keys=("ts_code", "trade_date"),
        required_columns=("ts_code", "trade_date", "open", "high", "low", "close", "vol", "amount"),
        date_column="trade_date",
        phase=1,
    ),
    "index_daily": DatasetSpec(
        name="index_daily",
        raw_pattern="market/index/*.parquet",
        kind="index_daily",
        natural_keys=("ts_code", "trade_date"),
        required_columns=("ts_code", "trade_date", "open", "high", "low", "close"),
        date_column="trade_date",
        phase=1,
    ),
    "index_weights": DatasetSpec(
        name="index_weights",
        raw_pattern="universe/index_weights/*.parquet",
        kind="universe",
        natural_keys=("index_code", "con_code", "trade_date"),
        required_columns=("index_code", "con_code", "trade_date", "weight"),
        date_column="trade_date",
        phase=2,
        materialize=False,
    ),
    "industry_sw2021": DatasetSpec(
        name="industry_sw2021",
        raw_pattern="universe/industry_sw2021/*.parquet",
        kind="universe",
        natural_keys=("industry_code",),
        required_columns=("industry_code", "industry_name"),
        phase=2,
        materialize=False,
    ),
    "income": DatasetSpec(
        name="income",
        raw_pattern="fundamentals/income/*.parquet",
        kind="periodic_cumulative",
        natural_keys=("ts_code", "ann_date", "end_date", "report_type"),
        required_columns=("ts_code", "ann_date", "end_date"),
        ann_date_column="ann_date",
        f_ann_date_column="f_ann_date",
        end_date_column="end_date",
        duplicate_key_columns=("ts_code", "end_date", "disclosure_date", "report_type"),
        phase=2,
    ),
    "income_quarterly": DatasetSpec(
        name="income_quarterly",
        raw_pattern="fundamentals/income_quarterly/*.parquet",
        kind="periodic_direct_sq",
        natural_keys=("ts_code", "f_ann_date", "end_date", "report_type"),
        required_columns=("ts_code", "end_date"),
        ann_date_column="ann_date",
        f_ann_date_column="f_ann_date",
        end_date_column="end_date",
        duplicate_key_columns=("ts_code", "end_date", "disclosure_date", "report_type"),
        phase=2,
    ),
    "balancesheet": DatasetSpec(
        name="balancesheet",
        raw_pattern="fundamentals/balancesheet/*.parquet",
        kind="periodic_snapshot",
        natural_keys=("ts_code", "ann_date", "end_date", "report_type"),
        required_columns=("ts_code", "ann_date", "end_date"),
        ann_date_column="ann_date",
        f_ann_date_column="f_ann_date",
        end_date_column="end_date",
        duplicate_key_columns=("ts_code", "end_date", "disclosure_date", "report_type"),
        phase=2,
    ),
    "indicators": DatasetSpec(
        name="indicators",
        raw_pattern="fundamentals/indicators/*.parquet",
        kind="periodic_snapshot",
        natural_keys=("ts_code", "ann_date", "end_date"),
        required_columns=("ts_code", "ann_date", "end_date"),
        ann_date_column="ann_date",
        end_date_column="end_date",
        duplicate_key_columns=("ts_code", "end_date", "disclosure_date"),
        phase=2,
    ),
    "dividends": DatasetSpec(
        name="dividends",
        raw_pattern="corporate/dividends/*.parquet",
        kind="event_ledger",
        natural_keys=("ts_code", "ann_date", "end_date", "record_date", "ex_date", "pay_date", "div_proc"),
        required_columns=("ts_code", "ann_date"),
        ann_date_column="ann_date",
        end_date_column="end_date",
        duplicate_key_columns=("ts_code", "end_date", "disclosure_date", "record_date", "ex_date", "pay_date", "div_proc"),
        phase=2,
    ),
    "cashflow": DatasetSpec(
        name="cashflow",
        raw_pattern="fundamentals/cashflow/*.parquet",
        kind="periodic_cumulative",
        natural_keys=("ts_code", "ann_date", "end_date", "report_type"),
        required_columns=("ts_code", "ann_date", "end_date"),
        ann_date_column="ann_date",
        f_ann_date_column="f_ann_date",
        end_date_column="end_date",
        duplicate_key_columns=("ts_code", "end_date", "disclosure_date", "report_type"),
        phase=3,
    ),
    "cashflow_quarterly": DatasetSpec(
        name="cashflow_quarterly",
        raw_pattern="fundamentals/cashflow_quarterly/*.parquet",
        kind="periodic_direct_sq",
        natural_keys=("ts_code", "f_ann_date", "end_date", "report_type"),
        required_columns=("ts_code", "end_date"),
        ann_date_column="ann_date",
        f_ann_date_column="f_ann_date",
        end_date_column="end_date",
        duplicate_key_columns=("ts_code", "end_date", "disclosure_date", "report_type"),
        phase=3,
        allow_missing_raw=True,
    ),
    "forecast": DatasetSpec(
        name="forecast",
        raw_pattern="fundamentals/forecast/*.parquet",
        kind="event_periodic",
        natural_keys=("ts_code", "ann_date", "end_date", "type"),
        required_columns=("ts_code", "ann_date", "end_date", "type"),
        ann_date_column="ann_date",
        end_date_column="end_date",
        duplicate_key_columns=("ts_code", "end_date", "disclosure_date", "type"),
        phase=3,
    ),
    "holder_number": DatasetSpec(
        name="holder_number",
        raw_pattern="corporate/holder_number/*.parquet",
        kind="event_periodic",
        natural_keys=("ts_code", "ann_date", "end_date"),
        required_columns=("ts_code", "end_date"),
        ann_date_column="ann_date",
        end_date_column="end_date",
        duplicate_key_columns=("ts_code", "end_date", "disclosure_date"),
        phase=3,
    ),
    "moneyflow": DatasetSpec(
        name="moneyflow",
        raw_pattern="market/moneyflow/**/*.parquet",
        kind="daily_fact",
        natural_keys=("ts_code", "trade_date"),
        required_columns=("ts_code", "trade_date"),
        date_column="trade_date",
        phase=3,
    ),
    "northbound": DatasetSpec(
        name="northbound",
        raw_pattern="market/northbound/**/*.parquet",
        kind="daily_fact",
        natural_keys=("ts_code", "trade_date"),
        required_columns=("trade_date",),
        date_column="trade_date",
        phase=3,
    ),
    "margin": DatasetSpec(
        name="margin",
        raw_pattern="market/margin/**/*.parquet",
        kind="daily_fact",
        natural_keys=("ts_code", "trade_date"),
        required_columns=("ts_code", "trade_date"),
        date_column="trade_date",
        phase=3,
    ),
    "stk_limit": DatasetSpec(
        name="stk_limit",
        raw_pattern="market/stk_limit/**/*.parquet",
        kind="daily_fact",
        natural_keys=("ts_code", "trade_date"),
        required_columns=("ts_code", "trade_date", "up_limit", "down_limit"),
        date_column="trade_date",
        phase=3,
    ),
    # ── New Alpha Endpoints (added 2026-04-14) ────────────────────────
    "top_list": DatasetSpec(
        name="top_list",
        raw_pattern="market/top_list/**/*.parquet",
        kind="daily_fact",
        natural_keys=("ts_code", "trade_date"),
        required_columns=("ts_code", "trade_date"),
        date_column="trade_date",
        phase=3,
    ),
    "top_inst": DatasetSpec(
        name="top_inst",
        raw_pattern="market/top_inst/**/*.parquet",
        kind="daily_fact",
        natural_keys=("ts_code", "trade_date"),
        required_columns=("ts_code", "trade_date"),
        date_column="trade_date",
        phase=3,
    ),
    "block_trade": DatasetSpec(
        name="block_trade",
        raw_pattern="market/block_trade/**/*.parquet",
        kind="daily_fact",
        natural_keys=("ts_code", "trade_date"),
        required_columns=("ts_code", "trade_date"),
        date_column="trade_date",
        phase=3,
    ),
    "stk_holdertrade": DatasetSpec(
        name="stk_holdertrade",
        raw_pattern="corporate/stk_holdertrade/*.parquet",
        kind="event_periodic",
        natural_keys=("ts_code", "ann_date", "holder_name"),
        required_columns=("ts_code", "ann_date"),
        ann_date_column="ann_date",
        phase=3,
    ),
    "cyq_perf": DatasetSpec(
        name="cyq_perf",
        raw_pattern="market/cyq_perf/**/*.parquet",
        kind="daily_fact",
        natural_keys=("ts_code", "trade_date"),
        required_columns=("ts_code", "trade_date"),
        date_column="trade_date",
        phase=3,
    ),
    # 15000积分 expansion (P1, 2026-06-08): sell-side analyst forecasts.
    # event_periodic, multi-row per (ts_code, report_date): one per analyst ×
    # forecast-quarter. Anchor = next_open(max(report_date, create_time)) — the
    # create_time (vendor update timestamp, after-hours) is the f_ann_date so the
    # generic disclosure_dates() max() captures the real availability lag.
    # duplicate_key_columns is LEFT UNSET so normalize does NOT collapse rows; the
    # custom build_ledger key branch keys on (ts_code, report_date,
    # normalized_analyst_id, quarter) to preserve each distinct forecast.
    "report_rc": DatasetSpec(
        name="report_rc",
        raw_pattern="analyst/report_rc/*.parquet",
        kind="event_periodic",
        natural_keys=("ts_code", "report_date", "org_name", "author_name", "quarter"),
        required_columns=("ts_code", "report_date"),
        ann_date_column="report_date",
        f_ann_date_column="create_time",
        phase=3,
    ),
}


@dataclass
class DatasetProfile:
    """Persisted profile summary for one dataset."""

    name: str
    build_id: str
    file_count: int = 0
    row_count: int = 0
    schema_variants: dict[str, int] = field(default_factory=dict)
    date_min: str | None = None
    date_max: str | None = None
    null_mandatory_keys: dict[str, int] = field(default_factory=dict)
    duplicate_rows: int = 0
    duplicate_groups: int = 0
    unexpected_missing_dates: list[str] = field(default_factory=list)
    sample_conflicts: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass
class BuildPaths:
    """Concrete build paths for the staged backend."""

    project_root: str
    data_root: str
    qlib_dir: str
    normalized_root: str
    pit_ledger_root: str
    qlib_builds_root: str
    workspace_profiles_root: str
    quarantine_root: str
    build_root: str
    provider_dir: str
    metadata_dir: str
    events_dir: str
    manifest_path: str


@dataclass
class BuildResult:
    """Return payload from a staged build."""

    build_id: str
    provider_dir: str
    manifest_path: str
    validation_errors: list[str]
    validation_warnings: list[str]
    profiled_datasets: list[str]
    normalized_datasets: list[str]
    ledgers_built: list[str]


class BuildGateError(RuntimeError):
    """Raised when strict integrity gates fail."""


def _project_root_from_file() -> str:
    current = os.path.abspath(__file__)
    return os.path.abspath(os.path.join(os.path.dirname(current), "..", ".."))


def resolve_build_paths(
    data_root: str | None = None,
    qlib_dir: str | None = None,
    build_id: str | None = None,
) -> BuildPaths:
    """Resolve the canonical repo-relative build paths."""
    project_root = _project_root_from_file()
    config_path = os.path.join(project_root, "config.yaml")
    with open(config_path, "r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    resolved_data_root = (
        os.path.normpath(os.path.join(project_root, config["storage"]["data_root"]))
        if data_root is None
        else os.path.normpath(data_root)
    )
    resolved_qlib_dir = (
        os.path.normpath(os.path.join(project_root, config["storage"]["qlib_data_dir"]))
        if qlib_dir is None
        else os.path.normpath(qlib_dir)
    )
    build_id = build_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    build_root = os.path.join(resolved_data_root, "qlib_builds", build_id)
    return BuildPaths(
        project_root=project_root,
        data_root=resolved_data_root,
        qlib_dir=resolved_qlib_dir,
        normalized_root=os.path.join(resolved_data_root, "normalized"),
        pit_ledger_root=os.path.join(resolved_data_root, "pit_ledger"),
        qlib_builds_root=os.path.join(resolved_data_root, "qlib_builds"),
        workspace_profiles_root=os.path.join(project_root, "workspace", "outputs", "data_profiles"),
        quarantine_root=os.path.join(resolved_data_root, "quarantine"),
        build_root=build_root,
        provider_dir=os.path.join(build_root, "provider"),
        metadata_dir=os.path.join(build_root, "provider", "metadata"),
        events_dir=os.path.join(build_root, "provider", "events"),
        manifest_path=os.path.join(build_root, "manifest.json"),
    )


def iter_progress(
    iterable: Iterable[Any],
    *,
    total: int | None = None,
    desc: str,
    unit: str,
    leave: bool = False,
) -> Iterable[Any]:
    """Wrap an iterable with a visible progress bar for long-running stages."""
    return tqdm(
        iterable,
        total=total,
        desc=desc,
        unit=unit,
        dynamic_ncols=True,
        leave=leave,
        disable=(total is not None and total <= 1),
    )


def normalize_date_series(series: pd.Series) -> pd.Series:
    """Normalize a date-like series to pandas ``Timestamp`` values."""
    if series.empty:
        return pd.to_datetime(series, errors="coerce")
    if pd.api.types.is_datetime64_any_dtype(series):
        return pd.to_datetime(series, errors="coerce")
    as_text = series.astype(str)
    parsed = pd.to_datetime(as_text, format="%Y%m%d", errors="coerce")
    invalid_markers = {"", "NaT", "nan", "None", "<NA>"}
    fallback_mask = parsed.isna() & as_text.notna() & ~as_text.isin(invalid_markers)
    if fallback_mask.any():
        parsed.loc[fallback_mask] = pd.to_datetime(as_text.loc[fallback_mask], errors="coerce")
    return parsed


def normalized_analyst_id(org: pd.Series, author: pd.Series) -> pd.Series:
    """Stable analyst-team identity from messy org/author strings (report_rc P1).

    ``org_norm`` (NFKC, trim, collapse whitespace) + ``"::"`` + sorted author
    tokens (split on ``/ & , ， 、 ; ；``). Missing author -> ``<org>::UNKNOWN_AUTHOR``.
    Multi-author rows are one TEAM identity in P1 (per-member mapping is an
    active-latest refinement, not needed for the event-flow primitives). Used as a
    ledger-key component so each analyst's forecasts stay distinct rather than
    collapsing on ``(ts_code, report_date)``.
    """
    import re
    import unicodedata

    def _clean(x: object) -> str:
        if x is None or (isinstance(x, float) and pd.isna(x)):
            return ""
        return unicodedata.normalize("NFKC", str(x)).strip()

    def _one(o: object, a: object) -> str:
        o_norm = re.sub(r"\s+", " ", _clean(o))
        a_norm = _clean(a)
        if not a_norm or a_norm.lower() in {"nan", "none", "<na>"}:
            return f"{o_norm}::UNKNOWN_AUTHOR"
        tokens = sorted(t.strip() for t in re.split(r"[/&,，、;；]", a_norm) if t.strip())
        return f"{o_norm}::" + "+".join(tokens)

    return pd.Series([_one(o, a) for o, a in zip(org, author)], index=org.index, dtype="object")


def disclosure_dates(df: pd.DataFrame, ann_col: str | None, f_ann_col: str | None) -> pd.Series:
    """Compute conservative disclosure dates."""
    ann = normalize_date_series(df[ann_col]) if ann_col and ann_col in df.columns else pd.Series(pd.NaT, index=df.index)
    f_ann = normalize_date_series(df[f_ann_col]) if f_ann_col and f_ann_col in df.columns else pd.Series(pd.NaT, index=df.index)
    if ann.empty:
        return f_ann
    if f_ann.empty:
        return ann
    return pd.concat([ann, f_ann], axis=1).max(axis=1)


def strictly_next_open_trade_day(dates: pd.Series, open_calendar: pd.DatetimeIndex) -> pd.Series:
    """Shift disclosure dates to the STRICTLY next open trading day.

    This function is the load-bearing anchor for the entire PIT guarantee.
    For every input date ``x``, the result ``y`` satisfies either:
        (a) ``y > x`` and ``y`` is an open trading day, OR
        (b) ``y`` is ``pd.NaT`` (input is NaT, or no open day exists strictly after ``x``).

    The strict inequality is critical: if ``y == x`` for a disclosure on an
    open trading day, same-day leakage is possible downstream. The
    implementation uses ``np.searchsorted(..., side="right")``, which returns
    the insertion index for ``x`` such that all entries to the left are
    ``<= x``. This guarantees ``open_calendar[pos] > x`` for any ``pos``
    returned that is within range.

    DO NOT change this function without updating the PIT invariant tests in
    ``tests/data_infra/test_pit_backend.py`` and the documentation in
    ``CLAUDE.md §3`` ("PIT visibility anchor").

    Args:
        dates: Disclosure dates (coerced to datetime64[ns]).
        open_calendar: Sorted index of open trading days.

    Returns:
        Series aligned with ``dates``, containing the strictly-next open day
        or ``pd.NaT`` when no such day exists.
    """
    clean = pd.to_datetime(dates, errors="coerce")
    values = open_calendar.values
    positions = np.searchsorted(values, clean.values.astype("datetime64[ns]"), side="right")
    out = []
    for source, pos in zip(clean.values, positions):
        if pd.isna(source) or pos >= len(open_calendar):
            out.append(pd.NaT)
            continue
        result = open_calendar[pos]
        # Runtime PIT invariant: result must be STRICTLY later than source.
        # This assert guards against future refactors that accidentally
        # switch searchsorted side from "right" to "left".
        assert result > source, (
            f"PIT invariant violated: strictly_next_open_trade_day({source}) "
            f"returned {result} which is not strictly greater"
        )
        out.append(result)
    return pd.Series(out, index=dates.index)


# Backwards-compatibility alias for external callers that may import the old
# name. New code should use ``strictly_next_open_trade_day`` directly.
next_open_trade_day = strictly_next_open_trade_day


def payload_numeric_columns(df: pd.DataFrame) -> list[str]:
    """Return numeric payload columns excluding metadata keys."""
    numeric = df.select_dtypes(include=[np.number]).columns.tolist()
    return [column for column in numeric if column not in CORE_METADATA_COLUMNS]


def _coerce_update_priority(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.fillna(-1)


# Hidden columns injected during raw ingestion to provide a deterministic
# terminal tie-break key. The columns are:
#   _src_file    — basename of the raw parquet the row came from
#   _src_ordinal — original row index within that file
# These are stripped before the normalized dataset is written to disk.
_SRC_FILE_COLUMN = "_src_file"
_SRC_ORDINAL_COLUMN = "_src_ordinal"
_DETERMINISTIC_TAIL_COLUMNS = (_SRC_FILE_COLUMN, _SRC_ORDINAL_COLUMN)


def _row_content_hash(row: pd.Series, payload_columns: list[str]) -> str:
    """Compute a stable content-based hash for a payload row.

    Used as the deterministic terminal tie-break in ``canonicalize_report_variants``
    when the source-file/ordinal columns are not available (because the dataset
    has already been written to disk and re-read). The hash is stable across
    machines because it serializes NaN as a fixed token and numeric values via
    ``repr``.
    """
    import hashlib

    parts: list[str] = []
    for column in payload_columns:
        if column not in row.index:
            parts.append("<missing>")
            continue
        value = row[column]
        if pd.isna(value):
            parts.append("<nan>")
        else:
            parts.append(repr(value))
    serialized = "|".join(f"{col}={part}" for col, part in zip(payload_columns, parts))
    return hashlib.blake2b(serialized.encode("utf-8"), digest_size=16).hexdigest()


def collapse_duplicate_versions(
    df: pd.DataFrame,
    key_columns: Iterable[str],
    provenance_buffer: list[dict[str, Any]] | None = None,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Collapse duplicate rows sharing the same canonical PIT key.

    Tie-break order (all descending by priority):
      1. ``update_flag`` priority (higher wins)
      2. Max of ``disclosure_date`` / ``f_ann_date`` / ``ann_date`` (later wins)
      3. Non-null payload count (more complete wins)
      4. ``_src_file`` + ``_src_ordinal`` when present (deterministic tail)
      5. Row content hash (deterministic tail for rows lacking _src_* columns)

    The deterministic tail guarantees that the same input data rebuilt on a
    different machine produces identical output, regardless of file glob order
    or Python dict iteration order. A WARNING is logged whenever the tail
    breaks a tie so tie frequency is observable.

    If ``provenance_buffer`` is provided, every backfill event (where a
    missing cell in the winner row is filled from a lower-priority candidate)
    is appended as a dict: ``{ts_code, end_date, disclosure_date, field,
    source_disclosure_date, source_update_flag}``. This powers the P0-5
    backfill provenance sidecar.
    """
    keys = [column for column in key_columns if column in df.columns]
    if not keys or df.empty:
        return df.copy(), []

    payload_columns = [
        column
        for column in df.columns
        if column not in CORE_METADATA_COLUMNS
        and column not in keys
        and column not in _DETERMINISTIC_TAIL_COLUMNS
    ]
    work = df.copy()
    work["_priority_update"] = _coerce_update_priority(work.get("update_flag", pd.Series(dtype=float)))
    work["_priority_non_null"] = work.notna().sum(axis=1)
    meta_dates = pd.Series(pd.NaT, index=work.index)
    for column in ("disclosure_date", "f_ann_date", "ann_date"):
        if column in work.columns:
            meta_dates = pd.concat([meta_dates, normalize_date_series(work[column])], axis=1).max(axis=1)
    work["_priority_date"] = meta_dates

    has_src_tail = _SRC_FILE_COLUMN in work.columns and _SRC_ORDINAL_COLUMN in work.columns

    rows: list[pd.Series] = []
    conflicts: list[dict[str, Any]] = []
    tail_break_count = 0
    for key, group in work.groupby(keys, dropna=False, sort=False):
        if len(group) == 1:
            rows.append(group.iloc[0])
            continue

        # Primary sort keys: descending by domain priority.
        primary_sort_cols = ["_priority_update", "_priority_date", "_priority_non_null"]
        primary_ascending = [False, False, False]

        # Deterministic terminal keys: ascending (lexicographic for strings,
        # numeric for ordinals). When two rows tie on primary keys, the
        # alphabetically-earlier source file and smaller ordinal win — this
        # is arbitrary but reproducible.
        if has_src_tail:
            tail_sort_cols = [_SRC_FILE_COLUMN, _SRC_ORDINAL_COLUMN]
            tail_ascending = [True, True]
        else:
            # Fallback: use content hash when source provenance isn't available.
            work_group = group.copy()
            work_group["_tail_hash"] = work_group.apply(
                lambda row: _row_content_hash(row, payload_columns), axis=1
            )
            group = work_group
            tail_sort_cols = ["_tail_hash"]
            tail_ascending = [True]

        ordered = group.sort_values(
            by=primary_sort_cols + tail_sort_cols,
            ascending=primary_ascending + tail_ascending,
            kind="mergesort",
        )

        # Detect whether the tail keys were needed (i.e., full primary-key tie).
        top_primary = ordered.iloc[0][primary_sort_cols].tolist()
        primary_tied_rows = ordered[
            (ordered["_priority_update"] == top_primary[0])
            & (ordered["_priority_date"].astype("datetime64[ns]") == pd.Timestamp(top_primary[1]))
            & (ordered["_priority_non_null"] == top_primary[2])
        ]
        if len(primary_tied_rows) > 1:
            tail_break_count += 1

        primary = ordered.iloc[0].copy()
        for _, candidate in ordered.iloc[1:].iterrows():
            for column in payload_columns:
                if pd.isna(primary[column]) and not pd.isna(candidate[column]):
                    primary[column] = candidate[column]
                    if provenance_buffer is not None:
                        provenance_buffer.append(
                            {
                                "ts_code": primary.get("ts_code"),
                                "end_date": primary.get("end_date"),
                                "disclosure_date": primary.get("disclosure_date"),
                                "field": column,
                                "source_disclosure_date": candidate.get("disclosure_date"),
                                "source_update_flag": candidate.get("update_flag"),
                            }
                        )
        varying = [column for column in payload_columns if ordered[column].drop_duplicates().shape[0] > 1]
        if varying:
            key_dict = {keys[0]: key} if not isinstance(key, tuple) else {column: value for column, value in zip(keys, key)}
            conflicts.append({"key": key_dict, "row_count": int(len(group)), "varying_columns": varying[:20]})
        rows.append(primary)

    if tail_break_count > 0:
        logging.getLogger(__name__).warning(
            "collapse_duplicate_versions: deterministic tail-key tie-break used %d times "
            "(all primary keys tied). Fix requires rerunning the raw ingest with "
            "_src_file/_src_ordinal columns if not already present.",
            tail_break_count,
        )

    result = pd.DataFrame(rows).drop(
        columns=[
            "_priority_update",
            "_priority_non_null",
            "_priority_date",
            "_tail_hash",
        ],
        errors="ignore",
    )
    return result.reset_index(drop=True), conflicts


def report_type_priority(report_type: Any, variant_kind: Literal["quarterly", "cumulative", "snapshot"]) -> int:
    """Return canonical precedence for Tushare statement report types."""
    if pd.isna(report_type):
        return -1
    value = str(report_type)
    if variant_kind == "quarterly":
        priority_map = {"3": 30, "2": 20, "1": 10, "4": 5, "5": 0}
    elif variant_kind == "cumulative":
        priority_map = {"1": 30, "4": 20, "5": 10, "3": 5, "2": 0}
    else:
        priority_map = {"1": 30, "4": 20, "5": 10, "3": 5, "2": 0}
    return priority_map.get(value, -1)


def canonicalize_report_variants(
    df: pd.DataFrame,
    variant_kind: Literal["quarterly", "cumulative", "snapshot"],
    provenance_buffer: list[dict[str, Any]] | None = None,
) -> pd.DataFrame:
    """Collapse same-date report variants into one canonical row with report-type precedence.

    Tie-break order (all descending by priority):
      1. ``report_type`` priority (3 > 2 > 1 for quarterly; 1 > 4 > 5 > 3 > 2 for cumulative)
      2. ``update_flag`` priority (higher wins)
      3. Max of ``disclosure_date`` / ``f_ann_date`` / ``ann_date`` (later wins)
      4. Non-null payload count (more complete wins)
      5. ``_src_file`` + ``_src_ordinal`` when present, else row content hash
         (deterministic tail for reproducibility)
    """
    if df.empty or "end_date" not in df.columns or "effective_date" not in df.columns:
        return df.copy()

    keys = [column for column in ("effective_date", "end_date") if column in df.columns]
    if not keys:
        return df.copy()

    payload_columns = [
        column
        for column in df.columns
        if column not in CORE_METADATA_COLUMNS
        and column not in keys
        and column not in _DETERMINISTIC_TAIL_COLUMNS
    ]
    work = df.copy()
    work["_report_type_priority"] = work.get("report_type", pd.Series(index=work.index, dtype="object")).map(
        lambda value: report_type_priority(value, variant_kind)
    )
    work["_priority_update"] = _coerce_update_priority(work.get("update_flag", pd.Series(dtype=float)))
    work["_priority_non_null"] = work[payload_columns].notna().sum(axis=1) if payload_columns else 0
    meta_dates = pd.Series(pd.NaT, index=work.index)
    for column in ("disclosure_date", "f_ann_date", "ann_date"):
        if column in work.columns:
            meta_dates = pd.concat([meta_dates, normalize_date_series(work[column])], axis=1).max(axis=1)
    work["_priority_date"] = meta_dates

    has_src_tail = _SRC_FILE_COLUMN in work.columns and _SRC_ORDINAL_COLUMN in work.columns

    primary_sort_cols = [
        "_report_type_priority",
        "_priority_update",
        "_priority_date",
        "_priority_non_null",
    ]
    primary_ascending = [False, False, False, False]

    rows: list[pd.Series] = []
    tail_break_count = 0
    for _, group in work.groupby(keys, dropna=False, sort=False):
        if len(group) == 1:
            rows.append(group.iloc[0])
            continue

        if has_src_tail:
            tail_sort_cols = [_SRC_FILE_COLUMN, _SRC_ORDINAL_COLUMN]
            tail_ascending = [True, True]
            sort_group = group
        else:
            sort_group = group.copy()
            sort_group["_tail_hash"] = sort_group.apply(
                lambda row: _row_content_hash(row, payload_columns), axis=1
            )
            tail_sort_cols = ["_tail_hash"]
            tail_ascending = [True]

        ordered = sort_group.sort_values(
            by=primary_sort_cols + tail_sort_cols,
            ascending=primary_ascending + tail_ascending,
            kind="mergesort",
        )

        top = ordered.iloc[0]
        tied_on_primary = ordered[
            (ordered["_report_type_priority"] == top["_report_type_priority"])
            & (ordered["_priority_update"] == top["_priority_update"])
            & (ordered["_priority_date"].astype("datetime64[ns]") == pd.Timestamp(top["_priority_date"]))
            & (ordered["_priority_non_null"] == top["_priority_non_null"])
        ]
        if len(tied_on_primary) > 1:
            tail_break_count += 1

        primary = ordered.iloc[0].copy()
        for _, candidate in ordered.iloc[1:].iterrows():
            for column in payload_columns:
                if pd.isna(primary[column]) and not pd.isna(candidate[column]):
                    primary[column] = candidate[column]
                    if provenance_buffer is not None:
                        provenance_buffer.append(
                            {
                                "ts_code": primary.get("ts_code"),
                                "effective_date": primary.get("effective_date"),
                                "end_date": primary.get("end_date"),
                                "field": column,
                                "source_report_type": candidate.get("report_type"),
                                "source_disclosure_date": candidate.get("disclosure_date"),
                                "source_update_flag": candidate.get("update_flag"),
                                "variant_kind": variant_kind,
                            }
                        )
        rows.append(primary)

    if tail_break_count > 0:
        logging.getLogger(__name__).warning(
            "canonicalize_report_variants (%s): deterministic tail-key tie-break used %d times",
            variant_kind,
            tail_break_count,
        )

    return pd.DataFrame(rows).drop(
        columns=[
            "_report_type_priority",
            "_priority_update",
            "_priority_non_null",
            "_priority_date",
            "_tail_hash",
        ],
        errors="ignore",
    ).reset_index(drop=True)


def previous_quarter_end(end_date: pd.Timestamp) -> pd.Timestamp | None:
    """Return the previous quarter end for a standard fiscal year."""
    if pd.isna(end_date):
        return None
    month_day = (end_date.month, end_date.day)
    if month_day == (3, 31):
        return None
    if month_day == (6, 30):
        return pd.Timestamp(year=end_date.year, month=3, day=31)
    if month_day == (9, 30):
        return pd.Timestamp(year=end_date.year, month=6, day=30)
    if month_day == (12, 31):
        return pd.Timestamp(year=end_date.year, month=9, day=30)
    return None


def same_period_last_year_end(end_date: pd.Timestamp) -> pd.Timestamp | None:
    """Return the same fiscal period end one year earlier."""
    if pd.isna(end_date):
        return None
    try:
        return pd.Timestamp(year=end_date.year - 1, month=end_date.month, day=end_date.day)
    except ValueError:
        return None


def percent_change(current_value: Any, reference_value: Any) -> np.float32 | float:
    """Compute percentage change using absolute denominator, preserving NaN on invalid inputs."""
    if pd.isna(current_value) or pd.isna(reference_value):
        return np.nan
    reference = float(reference_value)
    if reference == 0.0:
        return np.nan
    return np.float32(((float(current_value) - reference) / abs(reference)) * 100.0)


def derive_single_quarter_value(
    cumulative_state: dict[pd.Timestamp, dict[str, Any]],
    end_date: pd.Timestamp,
    field_name: str,
) -> np.float32 | float:
    """Derive a quarter value from the latest visible cumulative state.

    Computes ``current_cumulative - previous_cumulative`` using whatever is
    currently visible in ``cumulative_state`` for the two fiscal periods.

    **PIT semantics — late restatement behavior.** When a prior quarter's
    cumulative value is RESTATED after the current quarter has already been
    disclosed, this function returns a DIFFERENT derived value at the
    restatement's effective date than before it. This is intentional: the
    visible cumulative state IS the best information available at any given
    time, and the derived single-quarter value should reflect it.

    Example:
        Q2 2024 cumulative first disclosed on 2024-08-30 as 100
        Q3 2024 cumulative first disclosed on 2024-10-30 as 150
            -> derived Q3 = 150 - 100 = 50 (visible from 2024-10-31 onward)
        Q2 2024 cumulative RESTATED on 2024-11-15 to 95
            -> derived Q3 = 150 - 95 = 55 (visible from 2024-11-16 onward)

    This means the same ``(ts_code, end_date=Q3)`` can return different
    values at different query dates. Research code that caches quarter
    values must invalidate on every ledger rebuild. See ``CLAUDE.md §3``
    "PIT for fundamentals" for the full contract.

    For irregular ``end_date`` values that are not Q1/Q2/Q3/Q4 fiscal
    period-ends (e.g. ``2013-07-31``, ``2014-05-31`` present in the legacy
    indicators feed), ``previous_quarter_end`` returns ``None`` and this
    function returns ``NaN``. The downstream serving layer treats this as
    "no derived quarter value available" rather than fabricating one.
    """
    current_row = cumulative_state.get(end_date)
    if current_row is None:
        return np.nan
    current_value = current_row.get(field_name)
    if pd.isna(current_value):
        return np.nan
    prior_end = previous_quarter_end(end_date)
    if prior_end is None:
        return np.float32(current_value) if end_date.month == 3 else np.nan
    prior_row = cumulative_state.get(prior_end)
    if prior_row is None:
        return np.nan
    prior_value = prior_row.get(field_name)
    if pd.isna(prior_value):
        return np.nan
    return np.float32(float(current_value) - float(prior_value))


def materialize_visibility_segments(
    symbol_df: pd.DataFrame,
    calendar: pd.DatetimeIndex,
    slot_depth: int = SLOT_DEPTH_DEFAULT,
) -> list[dict[str, Any]]:
    """Build change-point segments for revision-aware visible-period slots."""
    if symbol_df.empty:
        return [{"start": 0, "end": len(calendar), "slots": [None] * slot_depth, "state": {}}]
    work = symbol_df.copy()
    work["effective_date"] = normalize_date_series(work["effective_date"])
    work["end_date"] = normalize_date_series(work["end_date"])
    work = work.dropna(subset=["effective_date", "end_date"]).sort_values(["effective_date", "end_date"])
    if work.empty:
        return [{"start": 0, "end": len(calendar), "slots": [None] * slot_depth, "state": {}}]

    grouped_events: list[tuple[pd.Timestamp, pd.DataFrame]] = list(work.groupby("effective_date", sort=True))
    segments: list[dict[str, Any]] = []
    state: dict[pd.Timestamp, dict[str, Any]] = {}
    cursor = 0

    def current_slots() -> list[dict[str, Any] | None]:
        ordered = sorted(state.values(), key=lambda row: row["end_date"], reverse=True)
        slots: list[dict[str, Any] | None] = ordered[:slot_depth]
        while len(slots) < slot_depth:
            slots.append(None)
        return slots

    for effective_date, event_rows in grouped_events:
        location = calendar.searchsorted(effective_date)
        if location >= len(calendar):
            continue
        if cursor < location:
            segments.append({"start": cursor, "end": location, "slots": current_slots(), "state": state.copy()})
        for row in event_rows.to_dict("records"):
            row["end_date"] = pd.Timestamp(row["end_date"])
            state[row["end_date"]] = row
        cursor = int(location)

    if cursor < len(calendar):
        segments.append({"start": cursor, "end": len(calendar), "slots": current_slots(), "state": state.copy()})
    if not segments:
        segments.append({"start": 0, "end": len(calendar), "slots": [None] * slot_depth, "state": {}})
    return segments


def arrays_from_snapshot_segments(
    segments: list[dict[str, Any]],
    fields: list[str],
    calendar_size: int,
    slot_depth: int,
) -> dict[str, np.ndarray]:
    """Expand snapshot-style slot segments into dense arrays."""
    result: dict[str, np.ndarray] = {}
    for slot in range(slot_depth):
        for field_name in fields:
            result[f"{field_name}_q{slot}"] = np.full(calendar_size, np.nan, dtype=np.float32)
    for segment in segments:
        for slot, row in enumerate(segment["slots"]):
            if row is None:
                continue
            for field_name in fields:
                value = row.get(field_name)
                if pd.notna(value):
                    result[f"{field_name}_q{slot}"][segment["start"] : segment["end"]] = np.float32(value)
    return result


def arrays_from_flow_segments(
    segments: list[dict[str, Any]],
    fields: list[str],
    calendar_size: int,
    slot_depth: int,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Expand cumulative flow segments into cumulative and derived single-quarter arrays."""
    cumulative: dict[str, np.ndarray] = {}
    single_quarter: dict[str, np.ndarray] = {}
    for slot in range(slot_depth):
        for field_name in fields:
            cumulative[f"{field_name}_cum_q{slot}"] = np.full(calendar_size, np.nan, dtype=np.float32)
            single_quarter[f"{field_name}_sq_q{slot}"] = np.full(calendar_size, np.nan, dtype=np.float32)

    for segment in segments:
        state = segment["state"]
        for slot, row in enumerate(segment["slots"]):
            if row is None:
                continue
            end_date = pd.Timestamp(row["end_date"])
            prior_end = previous_quarter_end(end_date)
            prior_row = state.get(prior_end) if prior_end is not None else None
            for field_name in fields:
                value = row.get(field_name)
                if pd.notna(value):
                    cumulative[f"{field_name}_cum_q{slot}"][segment["start"] : segment["end"]] = np.float32(value)
                if prior_row is None or prior_end is None:
                    if end_date.month == 3 and pd.notna(value):
                        single_quarter[f"{field_name}_sq_q{slot}"][segment["start"] : segment["end"]] = np.float32(value)
                    continue
                prior_value = prior_row.get(field_name)
                if pd.notna(value) and pd.notna(prior_value):
                    single_quarter[f"{field_name}_sq_q{slot}"][segment["start"] : segment["end"]] = np.float32(value - prior_value)
    return cumulative, single_quarter


def materialize_canonical_quarter_segments(
    cumulative_df: pd.DataFrame,
    quarterly_df: pd.DataFrame | None,
    calendar: pd.DatetimeIndex,
    quarter_fields: list[str],
    slot_depth: int = SLOT_DEPTH_DEFAULT,
) -> list[dict[str, Any]]:
    """Build canonical quarter-value segments with direct-quarter precedence and cumulative fallback."""
    cumulative_work = cumulative_df.copy() if cumulative_df is not None else pd.DataFrame()
    quarterly_work = quarterly_df.copy() if quarterly_df is not None else pd.DataFrame()

    for work in (cumulative_work, quarterly_work):
        if work.empty:
            continue
        work["effective_date"] = normalize_date_series(work["effective_date"])
        work["end_date"] = normalize_date_series(work["end_date"])
        work.dropna(subset=["effective_date", "end_date"], inplace=True)
        work.sort_values(["effective_date", "end_date"], inplace=True)

    if not cumulative_work.empty:
        cumulative_work = canonicalize_report_variants(cumulative_work, "cumulative")
    if not quarterly_work.empty:
        quarterly_work = canonicalize_report_variants(quarterly_work, "quarterly")

    cumulative_events = (
        {effective_date: frame for effective_date, frame in cumulative_work.groupby("effective_date", sort=True)}
        if not cumulative_work.empty and "effective_date" in cumulative_work.columns
        else {}
    )
    quarterly_events = (
        {effective_date: frame for effective_date, frame in quarterly_work.groupby("effective_date", sort=True)}
        if not quarterly_work.empty and "effective_date" in quarterly_work.columns
        else {}
    )
    all_event_dates = sorted(set(cumulative_events) | set(quarterly_events))

    cumulative_state: dict[pd.Timestamp, dict[str, Any]] = {}
    quarterly_state: dict[pd.Timestamp, dict[str, Any]] = {}
    segments: list[dict[str, Any]] = []
    cursor = 0

    def canonical_state() -> dict[pd.Timestamp, dict[str, Any]]:
        state: dict[pd.Timestamp, dict[str, Any]] = {}
        for end_date in sorted(set(cumulative_state) | set(quarterly_state), reverse=True):
            row = {"end_date": end_date}
            direct_row = quarterly_state.get(end_date)
            has_payload = False
            for field_name in quarter_fields:
                value = direct_row.get(field_name) if direct_row is not None else np.nan
                if pd.isna(value):
                    value = derive_single_quarter_value(cumulative_state, end_date, field_name)
                if pd.notna(value):
                    row[field_name] = np.float32(value)
                    has_payload = True
            if has_payload:
                state[end_date] = row
        return state

    def current_slots(state: dict[pd.Timestamp, dict[str, Any]]) -> list[dict[str, Any] | None]:
        ordered = sorted(state.values(), key=lambda row: row["end_date"], reverse=True)
        slots: list[dict[str, Any] | None] = ordered[:slot_depth]
        while len(slots) < slot_depth:
            slots.append(None)
        return slots

    for effective_date in all_event_dates:
        location = calendar.searchsorted(effective_date)
        if location >= len(calendar):
            continue
        current_state = canonical_state()
        if cursor < location:
            segments.append({"start": cursor, "end": location, "slots": current_slots(current_state), "state": current_state.copy()})
        for row in cumulative_events.get(effective_date, pd.DataFrame()).to_dict("records"):
            row["end_date"] = pd.Timestamp(row["end_date"])
            cumulative_state[row["end_date"]] = row
        for row in quarterly_events.get(effective_date, pd.DataFrame()).to_dict("records"):
            row["end_date"] = pd.Timestamp(row["end_date"])
            quarterly_state[row["end_date"]] = row
        cursor = int(location)

    final_state = canonical_state()
    if cursor < len(calendar):
        segments.append({"start": cursor, "end": len(calendar), "slots": current_slots(final_state), "state": final_state.copy()})
    if not segments:
        segments.append({"start": 0, "end": len(calendar), "slots": [None] * slot_depth, "state": {}})
    return segments


def arrays_from_metric_segments(
    segments: list[dict[str, Any]],
    specs: Iterable[DerivedMetricSpec],
    calendar_size: int,
    slot_depth: int,
) -> dict[str, np.ndarray]:
    """Expand periodic segments into PIT-derived metric arrays."""
    metrics = list(specs)
    arrays = {
        f"{spec.output_name}_q{slot}": np.full(calendar_size, np.nan, dtype=np.float32)
        for spec in metrics
        for slot in range(slot_depth)
    }
    for segment in segments:
        state = segment["state"]
        for slot, row in enumerate(segment["slots"]):
            if row is None:
                continue
            end_date = pd.Timestamp(row["end_date"])
            for spec in metrics:
                if spec.comparison == "yoy":
                    reference_end = same_period_last_year_end(end_date)
                else:
                    reference_end = previous_quarter_end(end_date)
                if reference_end is None:
                    continue
                reference_row = state.get(reference_end)
                if reference_row is None:
                    continue
                metric_value = percent_change(row.get(spec.base_field), reference_row.get(spec.base_field))
                if pd.notna(metric_value):
                    arrays[f"{spec.output_name}_q{slot}"][segment["start"] : segment["end"]] = metric_value
    return arrays


def provider_calendar(provider_dir: str) -> pd.DatetimeIndex:
    """Load the provider trading calendar."""
    cal_path = os.path.join(provider_dir, "calendars", "day.txt")
    with open(cal_path, "r", encoding="utf-8") as handle:
        values = [line.strip() for line in handle if line.strip()]
    return pd.DatetimeIndex(pd.to_datetime(values))


def profile_to_markdown(profile: DatasetProfile) -> str:
    """Render a profile artifact in readable markdown."""
    lines = [
        f"# Dataset Profile: {profile.name}",
        "",
        f"- Build ID: `{profile.build_id}`",
        f"- Files: `{profile.file_count}`",
        f"- Rows: `{profile.row_count}`",
        f"- Date Range: `{profile.date_min}` -> `{profile.date_max}`",
        f"- Duplicate Rows: `{profile.duplicate_rows}`",
        f"- Duplicate Groups: `{profile.duplicate_groups}`",
    ]
    if profile.warnings:
        lines.extend(["", "## Warnings"])
        lines.extend([f"- {item}" for item in profile.warnings])
    if profile.errors:
        lines.extend(["", "## Errors"])
        lines.extend([f"- {item}" for item in profile.errors])
    if profile.sample_conflicts:
        lines.extend(["", "## Sample Conflicts"])
        for item in profile.sample_conflicts[:5]:
            lines.append(f"- `{json.dumps(item, ensure_ascii=False, default=_json_default)}`")
    return "\n".join(lines) + "\n"


def _json_default(obj):
    """Best-effort fallback for JSON dumps of sample-conflict rows.

    Sample conflicts are pd.Series-to-dict renders of the offending rows and
    routinely contain ``pd.Timestamp`` (datetime columns), ``np.int64``,
    ``np.float64``, and occasional ``bytes`` values. Convert them to strings
    so ``profile_to_markdown`` can always round-trip rather than aborting the
    whole profile stage.
    """
    import datetime as _dt
    if isinstance(obj, (pd.Timestamp, _dt.datetime, _dt.date)):
        return obj.isoformat()
    if hasattr(obj, "item"):
        try:
            return obj.item()
        except Exception:
            pass
    try:
        return str(obj)
    except Exception:
        return None


class StagedQlibBackendBuilder:
    """Staged observed-data PIT builder for the repo's local provider."""

    def __init__(
        self,
        data_root: str | None = None,
        qlib_dir: str | None = None,
        build_id: str | None = None,
        include_phase3: bool = True,
        slot_depth: int = SLOT_DEPTH_DEFAULT,
        field_filter: list[str] | None = None,
        allow_exceptions: bool = False,
        write_compat_aliases: bool = True,
    ) -> None:
        self.paths = resolve_build_paths(data_root=data_root, qlib_dir=qlib_dir, build_id=build_id)
        self.include_phase3 = include_phase3
        self.slot_depth = max(1, slot_depth)
        self.field_filter = set(field_filter or [])
        self.allow_exceptions = allow_exceptions
        self.write_compat_aliases = write_compat_aliases
        ensure_directory(self.paths.build_root)
        ensure_directory(self.paths.workspace_profiles_root)
        ensure_directory(self.paths.normalized_root)
        ensure_directory(self.paths.pit_ledger_root)
        ensure_directory(self.paths.quarantine_root)
        self._stock_basic_cache: pd.DataFrame | None = None
        self._trade_calendar_cache: pd.DataFrame | None = None
        self._open_calendar_cache: pd.DatetimeIndex | None = None
        self._profile_cache: dict[str, DatasetProfile] = {}
        self._bin_ref_cache: dict[str, dict[str, Any] | None] = {}
        self._expected_empty_dates_cache: dict[str, set[str]] = {}
        self._price_repair_overrides_cache: pd.DataFrame | None = None
        # P0-5: accumulating provenance buffer for backfill audit sidecar.
        # Keyed by dataset name; flushed by _flush_backfill_provenance().
        self._backfill_provenance: dict[str, list[dict[str, Any]]] = {}

    @property
    def build_id(self) -> str:
        return os.path.basename(self.paths.build_root)

    def selected_datasets(self, datasets: Iterable[str] | None = None) -> list[str]:
        """Resolve dataset order for the staged workflow."""
        names = list(datasets) if datasets is not None else list(DATASET_SPECS.keys())
        if not self.include_phase3:
            names = [name for name in names if name not in PHASE3_DATASETS]
        ordered = [name for name in DATASET_SPECS if name in names]
        return ordered

    def selected_statement_families(self, datasets: Iterable[str] | None = None) -> list[StatementFamilySpec]:
        """Resolve active statement families from the selected datasets."""
        active = set(self.selected_datasets(datasets))
        families: list[StatementFamilySpec] = []
        for family_name, family in STATEMENT_FAMILIES.items():
            if any(dataset_name in active for dataset_name in family.datasets()):
                families.append(family)
        return families

    def stock_basic(self) -> pd.DataFrame:
        """Load and cache ``stock_basic``."""
        if self._stock_basic_cache is None:
            path = os.path.join(self.paths.data_root, "reference", "stock_basic.parquet")
            frame = pd.read_parquet(path).copy()
            frame["ts_code"] = frame["ts_code"].astype(str)
            frame["qlib_code"] = frame["ts_code"].map(lambda value: ts_code_to_qlib(value, lower=True))
            self._stock_basic_cache = frame
        return self._stock_basic_cache

    def trade_calendar(self) -> pd.DataFrame:
        """Load and cache ``trade_cal``."""
        if self._trade_calendar_cache is None:
            path = os.path.join(self.paths.data_root, "reference", "trade_cal.parquet")
            frame = pd.read_parquet(path).copy()
            frame["cal_date"] = normalize_date_series(frame["cal_date"])
            self._trade_calendar_cache = frame
        return self._trade_calendar_cache

    def open_calendar(self) -> pd.DatetimeIndex:
        """Load and cache the open-day calendar."""
        if self._open_calendar_cache is None:
            cal = self.trade_calendar()
            self._open_calendar_cache = pd.DatetimeIndex(cal.loc[cal["is_open"] == 1, "cal_date"].sort_values().unique())
        return self._open_calendar_cache

    def raw_files(self, dataset_name: str) -> list[str]:
        """Return raw file paths for ``dataset_name``."""
        spec = DATASET_SPECS[dataset_name]
        return sorted(glob(os.path.join(self.paths.data_root, spec.raw_pattern), recursive=True))

    def expected_empty_dates(self, dataset_name: str) -> set[str]:
        """Load confirmed source-empty trading dates for datasets with known API gaps."""
        if dataset_name in self._expected_empty_dates_cache:
            return self._expected_empty_dates_cache[dataset_name]
        reference_file = EXPECTED_EMPTY_DATE_FILES.get(dataset_name)
        if reference_file is None:
            self._expected_empty_dates_cache[dataset_name] = set()
            return set()
        path = os.path.join(self.paths.data_root, "reference", reference_file)
        if not os.path.exists(path):
            self._expected_empty_dates_cache[dataset_name] = set()
            return set()
        with open(path, "r", encoding="utf-8") as handle:
            values = {line.strip() for line in handle if line.strip() and not line.lstrip().startswith("#")}
        self._expected_empty_dates_cache[dataset_name] = values
        return values

    def price_repair_overrides(self) -> pd.DataFrame:
        """Load curated raw-daily repair overrides used by normalization and gates."""
        if self._price_repair_overrides_cache is not None:
            return self._price_repair_overrides_cache
        path = os.path.join(self.paths.data_root, "reference", PRICE_REPAIR_OVERRIDES_FILE)
        if not os.path.exists(path):
            self._price_repair_overrides_cache = pd.DataFrame()
            return self._price_repair_overrides_cache
        overrides = pd.read_csv(path)
        if "dataset" in overrides.columns:
            overrides["dataset"] = overrides["dataset"].astype(str)
        if "file_name" in overrides.columns:
            overrides["file_name"] = overrides["file_name"].astype(str)
        if "ts_code" in overrides.columns:
            overrides["ts_code"] = overrides["ts_code"].astype(str).str.upper()
        if "trade_date" in overrides.columns:
            overrides["trade_date"] = normalize_date_series(overrides["trade_date"])
        if "column" in overrides.columns:
            overrides["column"] = overrides["column"].astype(str)
        if "repaired_value" in overrides.columns:
            overrides["repaired_value"] = pd.to_numeric(overrides["repaired_value"], errors="coerce")
        self._price_repair_overrides_cache = overrides
        return overrides

    def normalized_path(self, dataset_name: str) -> str:
        """Return the canonical normalized path for ``dataset_name``."""
        spec = DATASET_SPECS[dataset_name]
        if spec.kind in {"periodic_snapshot", "periodic_cumulative", "periodic_direct_sq", "event_periodic", "event_ledger"}:
            return os.path.join(self.paths.normalized_root, dataset_name, f"{dataset_name}.parquet")
        if spec.kind in {"reference", "universe"}:
            return os.path.join(self.paths.normalized_root, spec.raw_pattern)
        return os.path.join(self.paths.normalized_root, spec.raw_pattern.split("*", 1)[0].rstrip(os.sep))

    def ledger_path(self, dataset_name: str) -> str:
        """Return the PIT ledger path for ``dataset_name``."""
        return os.path.join(self.paths.pit_ledger_root, dataset_name, f"{dataset_name}.parquet")

    def ledger_sidecar_path(self, dataset_name: str, suffix: str) -> str:
        """Return a sidecar path colocated with the PIT ledger."""
        return os.path.join(self.paths.pit_ledger_root, dataset_name, f"{dataset_name}_{suffix}.parquet")

    def quarantine_file(self, dataset_name: str, source_path: str) -> None:
        """Copy an offending raw file into the quarantine tree."""
        target_dir = os.path.join(self.paths.quarantine_root, dataset_name, self.build_id)
        ensure_directory(target_dir)
        shutil.copy2(source_path, os.path.join(target_dir, os.path.basename(source_path)))

    def _read_raw_file(self, dataset_name: str, source_path: str) -> pd.DataFrame:
        try:
            df = pd.read_parquet(source_path)
        except Exception as exc:
            self.quarantine_file(dataset_name, source_path)
            raise BuildGateError(f"Unreadable raw file for {dataset_name}: {source_path}: {exc}") from exc
        return df

    def _persist_profile(self, profile: DatasetProfile) -> None:
        ensure_directory(self.paths.workspace_profiles_root)
        json_path = os.path.join(self.paths.workspace_profiles_root, f"{profile.name}_{self.build_id}.json")
        md_path = os.path.join(self.paths.workspace_profiles_root, f"{profile.name}_{self.build_id}.md")
        with open(json_path, "w", encoding="utf-8") as handle:
            json.dump(asdict(profile), handle, ensure_ascii=False, indent=2, default=str)
        with open(md_path, "w", encoding="utf-8") as handle:
            handle.write(profile_to_markdown(profile))

    def _profile_json_path(self, dataset_name: str) -> str:
        return os.path.join(self.paths.workspace_profiles_root, f"{dataset_name}_{self.build_id}.json")

    def load_persisted_profile(self, dataset_name: str) -> DatasetProfile | None:
        """Load a saved dataset profile artifact for this build if it exists."""
        json_path = self._profile_json_path(dataset_name)
        if not os.path.exists(json_path):
            return None
        with open(json_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        profile = DatasetProfile(**payload)
        self._profile_cache[dataset_name] = profile
        return profile

    def profile_dataset(self, dataset_name: str) -> DatasetProfile:
        """Generate and persist a profile artifact for one dataset."""
        if dataset_name in self._profile_cache:
            return self._profile_cache[dataset_name]

        spec = DATASET_SPECS[dataset_name]
        files = self.raw_files(dataset_name)
        profile = DatasetProfile(name=dataset_name, build_id=self.build_id, file_count=len(files))
        if not files:
            message = f"No raw files found for {dataset_name}"
            if spec.allow_missing_raw:
                profile.warnings.append(message)
            else:
                profile.errors.append(message)
            self._persist_profile(profile)
            self._profile_cache[dataset_name] = profile
            return profile

        schema_counts: dict[str, int] = {}
        date_values: list[pd.Timestamp] = []
        duplicate_groups = 0
        duplicate_rows = 0
        sample_conflicts: list[dict[str, Any]] = []
        daily_dates_from_files: list[str] = []
        required_columns = set(spec.required_columns)
        open_days = self.open_calendar()

        for file_path in iter_progress(files, total=len(files), desc=f"Profile {dataset_name}", unit="file", leave=False):
            df = self._read_raw_file(dataset_name, file_path)
            profile.row_count += len(df)
            schema_key = "|".join(df.columns.tolist())
            schema_counts[schema_key] = schema_counts.get(schema_key, 0) + 1

            missing_required = required_columns - set(df.columns)
            if missing_required:
                profile.errors.append(
                    f"{os.path.basename(file_path)} missing required columns: {sorted(missing_required)}"
                )

            for column in spec.required_columns:
                if column in df.columns:
                    profile.null_mandatory_keys[column] = profile.null_mandatory_keys.get(column, 0) + int(df[column].isna().sum())

            if spec.date_column and spec.date_column in df.columns:
                current_dates = normalize_date_series(df[spec.date_column]).dropna()
                if not current_dates.empty:
                    date_values.extend(current_dates.tolist())
                    daily_dates_from_files.extend(current_dates.dt.strftime("%Y%m%d").tolist())
            elif spec.end_date_column and spec.end_date_column in df.columns:
                current_dates = normalize_date_series(df[spec.end_date_column]).dropna()
                if not current_dates.empty:
                    date_values.extend(current_dates.tolist())

            keys = [column for column in spec.natural_keys if column in df.columns]
            if keys:
                duplicated_mask = df.duplicated(subset=keys, keep=False)
                duplicate_rows += int(duplicated_mask.sum())
                if duplicated_mask.any():
                    grouped = df.loc[duplicated_mask].groupby(keys, dropna=False, sort=False).size()
                    duplicate_groups += int((grouped > 1).sum())
                    if len(sample_conflicts) < 5:
                        for key_value, count in grouped[grouped > 1].head(5 - len(sample_conflicts)).items():
                            if isinstance(key_value, tuple):
                                key_dict = {column: value for column, value in zip(keys, key_value)}
                            else:
                                key_dict = {keys[0]: key_value}
                            sample_conflicts.append(
                                {
                                    "file": os.path.basename(file_path),
                                    "key": key_dict,
                                    "count": int(count),
                                }
                            )

            if dataset_name == "daily":
                if {"high", "open", "close", "low", "adj_factor"}.issubset(df.columns):
                    checked_price, repair_warnings = self._apply_price_repair_overrides(
                        dataset_name,
                        df,
                        source_name=os.path.basename(file_path),
                    )
                    profile.warnings.extend(repair_warnings)
                    bad_price = checked_price[
                        (checked_price["high"] < checked_price[["open", "close", "low"]].max(axis=1))
                        | (checked_price["low"] > checked_price[["open", "close", "high"]].min(axis=1))
                        | (pd.to_numeric(checked_price["adj_factor"], errors="coerce") <= 0)
                    ]
                    if not bad_price.empty:
                        profile.errors.append(
                            f"{os.path.basename(file_path)} has {len(bad_price)} price-integrity violations"
                        )
                        self.quarantine_file(dataset_name, file_path)

            if dataset_name == "northbound" and "ts_code" in df.columns:
                suffix_counts = df["ts_code"].astype(str).str[-3:].value_counts(dropna=False).to_dict()
                profile.meta.setdefault("suffix_counts", {})
                for suffix, count in suffix_counts.items():
                    profile.meta["suffix_counts"][suffix] = profile.meta["suffix_counts"].get(suffix, 0) + int(count)

        profile.schema_variants = schema_counts
        profile.duplicate_rows = duplicate_rows
        profile.duplicate_groups = duplicate_groups
        profile.sample_conflicts = sample_conflicts
        if date_values:
            profile.date_min = min(date_values).strftime("%Y%m%d")
            profile.date_max = max(date_values).strftime("%Y%m%d")

        if (
            spec.kind in {"price_daily", "daily_fact", "index_daily"}
            and profile.date_min
            and profile.date_max
            and dataset_name not in EVENT_LIKE_DAILY_DATASETS
        ):
            present_dates = set(daily_dates_from_files)
            cal_slice = {
                day.strftime("%Y%m%d")
                for day in open_days
                if profile.date_min <= day.strftime("%Y%m%d") <= profile.date_max
            }
            missing_dates = sorted(cal_slice - present_dates)
            if dataset_name == "margin":
                missing_dates = [date for date in missing_dates if date >= "20100331"]
            expected_empty = self.expected_empty_dates(dataset_name)
            applied_expected = sorted(date for date in missing_dates if date in expected_empty)
            if applied_expected:
                profile.meta["expected_empty_reference"] = EXPECTED_EMPTY_DATE_FILES.get(dataset_name)
                profile.meta["expected_empty_dates_applied"] = applied_expected
            missing_dates = [date for date in missing_dates if date not in expected_empty]
            profile.unexpected_missing_dates = missing_dates

        self._persist_profile(profile)
        self._profile_cache[dataset_name] = profile
        return profile

    def profile_datasets(self, datasets: Iterable[str] | None = None) -> dict[str, DatasetProfile]:
        """Profile the selected datasets and return their summaries."""
        results = {}
        selected = self.selected_datasets(datasets)
        for dataset_name in iter_progress(selected, total=len(selected), desc="Profile datasets", unit="dataset", leave=True):
            results[dataset_name] = self.profile_dataset(dataset_name)
        return results

    def collect_profiles(
        self,
        datasets: Iterable[str] | None = None,
        *,
        use_persisted: bool = False,
    ) -> dict[str, DatasetProfile]:
        """Return dataset profiles, reusing saved profile artifacts when available."""
        results = {}
        for dataset_name in self.selected_datasets(datasets):
            profile = self.load_persisted_profile(dataset_name) if use_persisted else None
            if profile is None:
                profile = self.profile_dataset(dataset_name)
            results[dataset_name] = profile
        return results

    def _standardize_common_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        work = df.copy()
        if "ts_code" in work.columns:
            work["ts_code"] = work["ts_code"].astype(str).str.upper()
            work["qlib_code"] = work["ts_code"].map(lambda value: ts_code_to_qlib(value, lower=True))
        for column in [
            "trade_date",
            "ann_date",
            "f_ann_date",
            "end_date",
            "record_date",
            "ex_date",
            "pay_date",
            "div_listdate",
            "imp_ann_date",
            "first_ann_date",
            "start_date",
            "cal_date",
            "pretrade_date",
        ]:
            if column in work.columns:
                work[column] = normalize_date_series(work[column])
        return work

    def _apply_price_repair_overrides(
        self,
        dataset_name: str,
        df: pd.DataFrame,
        source_name: str | None = None,
    ) -> tuple[pd.DataFrame, list[str]]:
        """Apply approved row-level price repairs without mutating raw storage."""
        if dataset_name != "daily":
            return df.copy(), []
        overrides = self.price_repair_overrides()
        if overrides.empty:
            return df.copy(), []

        applicable = overrides[overrides["dataset"] == dataset_name].copy()
        if source_name is not None and "file_name" in applicable.columns:
            applicable = applicable[applicable["file_name"] == source_name]
        if applicable.empty:
            return df.copy(), []

        work = df.copy()
        if "ts_code" in work.columns:
            work["ts_code"] = work["ts_code"].astype(str).str.upper()
        if "trade_date" in work.columns:
            work["trade_date"] = normalize_date_series(work["trade_date"])

        warnings: list[str] = []
        applied = 0
        for row in applicable.itertuples(index=False):
            column_name = getattr(row, "column", None)
            if column_name not in work.columns:
                warnings.append(f"{source_name}: repair override column missing: {column_name}")
                continue
            mask = (
                work["ts_code"].astype(str).eq(getattr(row, "ts_code"))
                & work["trade_date"].eq(getattr(row, "trade_date"))
            )
            matched = int(mask.sum())
            if matched == 0:
                warnings.append(
                    f"{source_name}: repair override target not found for {getattr(row, 'ts_code')} "
                    f"{pd.Timestamp(getattr(row, 'trade_date')).strftime('%Y-%m-%d')}"
                )
                continue
            work.loc[mask, column_name] = getattr(row, "repaired_value")
            applied += matched
        if applied:
            warnings.append(f"{source_name}: applied {applied} approved daily price repair overrides")
        return work, warnings

    def _normalize_daily_partition(
        self,
        dataset_name: str,
        df: pd.DataFrame,
        source_name: str | None = None,
    ) -> tuple[pd.DataFrame, list[str]]:
        spec = DATASET_SPECS[dataset_name]
        repaired, warnings = self._apply_price_repair_overrides(dataset_name, df, source_name=source_name)
        work = self._standardize_common_columns(repaired)
        if dataset_name == "northbound":
            stock_basic = self.stock_basic()[["ts_code", "symbol", "exchange"]].drop_duplicates()
            valid_ts_codes = set(stock_basic["ts_code"].astype(str))
            exchange_map = {"SSE": "SH", "SZSE": "SZ", "SH": "SH", "SZ": "SZ"}
            if {"code", "exchange"}.issubset(work.columns):
                code_digits = (
                    work["code"]
                    .astype(str)
                    .str.extract(r"(\d{1,6})", expand=False)
                    .str.zfill(6)
                )
                exchange_suffix = work["exchange"].astype(str).str.upper().map(exchange_map)
                candidate_ts = code_digits.where(code_digits.notna() & exchange_suffix.notna(), None)
                candidate_ts = candidate_ts.where(candidate_ts.isna(), candidate_ts + "." + exchange_suffix)
                current_ts = work.get("ts_code", pd.Series(index=work.index, dtype="object")).astype(str).str.upper()
                invalid_current = ~current_ts.isin(valid_ts_codes)
                recoverable = invalid_current & candidate_ts.isin(valid_ts_codes)
                recovered = int(recoverable.sum())
                if recovered:
                    work.loc[recoverable, "ts_code"] = candidate_ts.loc[recoverable]
                    warnings.append(f"Recovered {recovered} northbound rows via code/exchange remap")
                    work["qlib_code"] = work["ts_code"].map(lambda value: ts_code_to_qlib(value, lower=True))
            valid_equity = work["ts_code"].astype(str).str.endswith((".SH", ".SZ"), na=False)
            valid_equity &= work["ts_code"].isin(valid_ts_codes)
            dropped = int((~valid_equity).sum())
            if dropped:
                warnings.append(f"Dropped {dropped} non-equity or unmapped northbound rows")
            work = work.loc[valid_equity].copy()
            if "vol" in work.columns:
                work = work.rename(columns=NORTHBOUND_RENAMES)

        if dataset_name == "daily":
            # ``.get(..., 1.0)`` returns a scalar when the column is missing, and
            # ``pd.to_numeric(1.0)`` returns a scalar ``1.0`` with no ``.fillna``
            # method. Use an index-matched Series default so the chained call
            # works both in production (column present) and in mocks (absent).
            adj_raw = work.get("adj_factor", pd.Series(1.0, index=work.index))
            work["factor"] = pd.to_numeric(adj_raw, errors="coerce").fillna(1.0)
            if "volume" not in work.columns and "vol" in work.columns:
                work["volume"] = work["vol"]

        keys = [column for column in spec.natural_keys if column in work.columns]
        if keys:
            duplicate_mask = work.duplicated(subset=keys, keep=False)
            if duplicate_mask.any():
                if dataset_name == "northbound":
                    duplicate_groups = work.loc[duplicate_mask].groupby(keys, dropna=False).size()
                    bad_keys = duplicate_groups[duplicate_groups > 1].index
                    work = work.set_index(keys)
                    work = work.loc[~work.index.isin(bad_keys)].reset_index()
                    warnings.append(f"Quarantined {len(bad_keys)} conflicting northbound key groups")
                else:
                    work = work.sort_values(keys).drop_duplicates(subset=keys, keep="last")

        return work, warnings

    def _normalize_periodic_dataset(self, dataset_name: str) -> tuple[pd.DataFrame, list[str]]:
        spec = DATASET_SPECS[dataset_name]
        raw_files = self.raw_files(dataset_name)
        frames: list[pd.DataFrame] = []
        for path in iter_progress(
            raw_files,
            total=len(raw_files),
            desc=f"Normalize {dataset_name}",
            unit="file",
            leave=False,
        ):
            frame = self._read_raw_file(dataset_name, path)
            # P0-4: Inject deterministic terminal tie-break keys. These hidden
            # columns survive through collapse_duplicate_versions /
            # canonicalize_report_variants and are stripped before the
            # normalized parquet write so they never appear on disk.
            frame[_SRC_FILE_COLUMN] = os.path.basename(path)
            frame[_SRC_ORDINAL_COLUMN] = np.arange(len(frame), dtype=np.int64)
            frames.append(frame)
        work = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        if work.empty:
            return work, [f"No rows loaded for {dataset_name}"]
        work = self._standardize_common_columns(work)
        if spec.ann_date_column:
            work["disclosure_date"] = disclosure_dates(work, spec.ann_date_column, spec.f_ann_date_column)
        key_columns = [column for column in spec.duplicate_key_columns if column in work.columns]
        # P0-5: accumulate backfill events into this dataset's provenance buffer.
        dataset_buffer = self._backfill_provenance.setdefault(dataset_name, [])
        normalized, conflicts = (
            collapse_duplicate_versions(work, key_columns, provenance_buffer=dataset_buffer)
            if key_columns
            else (work, [])
        )
        # Strip the hidden source-provenance columns before returning to the
        # caller. The normalized parquet on disk must not carry these columns.
        normalized = normalized.drop(
            columns=list(_DETERMINISTIC_TAIL_COLUMNS),
            errors="ignore",
        )
        warnings: list[str] = []
        if conflicts:
            warnings.append(f"Collapsed {len(conflicts)} duplicate canonical groups for {dataset_name}")
        return normalized, warnings

    def normalize_dataset(self, dataset_name: str) -> list[str]:
        """Normalize a raw dataset into ``data/normalized``."""
        spec = DATASET_SPECS[dataset_name]
        warnings: list[str] = []
        if spec.kind in {"periodic_snapshot", "periodic_cumulative", "periodic_direct_sq", "event_periodic", "event_ledger"}:
            normalized, warnings = self._normalize_periodic_dataset(dataset_name)
            output_path = self.normalized_path(dataset_name)
            ensure_directory(os.path.dirname(output_path))
            normalized.to_parquet(output_path, index=False)
            return warnings

        raw_files = self.raw_files(dataset_name)

        if spec.kind in {"reference", "universe"}:
            for source_path in iter_progress(raw_files, total=len(raw_files), desc=f"Normalize {dataset_name}", unit="file", leave=False):
                df = self._standardize_common_columns(self._read_raw_file(dataset_name, source_path))
                relative = os.path.relpath(source_path, self.paths.data_root)
                output_path = os.path.join(self.paths.normalized_root, relative)
                ensure_directory(os.path.dirname(output_path))
                df.to_parquet(output_path, index=False)
            return warnings

        for source_path in iter_progress(raw_files, total=len(raw_files), desc=f"Normalize {dataset_name}", unit="file", leave=False):
            df = self._read_raw_file(dataset_name, source_path)
            normalized, partition_warnings = self._normalize_daily_partition(
                dataset_name,
                df,
                source_name=os.path.basename(source_path),
            )
            warnings.extend(partition_warnings)
            relative = os.path.relpath(source_path, self.paths.data_root)
            output_path = os.path.join(self.paths.normalized_root, relative)
            ensure_directory(os.path.dirname(output_path))
            normalized.to_parquet(output_path, index=False)
        return warnings

    def normalize_datasets(self, datasets: Iterable[str] | None = None) -> dict[str, list[str]]:
        """Normalize selected datasets into the canonical zone."""
        results = {}
        selected = self.selected_datasets(datasets)
        for dataset_name in iter_progress(selected, total=len(selected), desc="Normalize datasets", unit="dataset", leave=True):
            results[dataset_name] = self.normalize_dataset(dataset_name)
        return results

    def collect_normalized_outputs(self, datasets: Iterable[str] | None = None) -> dict[str, list[str]]:
        """Collect normalized outputs already present on disk without rebuilding."""
        results: dict[str, list[str]] = {}
        for dataset_name in self.selected_datasets(datasets):
            normalized_path = self.normalized_path(dataset_name)
            if os.path.isfile(normalized_path):
                results[dataset_name] = [normalized_path]
            elif os.path.isdir(normalized_path):
                pattern = os.path.join(normalized_path, "**", "*.parquet")
                results[dataset_name] = sorted(glob(pattern, recursive=True))
            else:
                results[dataset_name] = []
        return results

    def load_normalized_periodic(self, dataset_name: str) -> pd.DataFrame:
        """Load a normalized periodic dataset."""
        path = self.normalized_path(dataset_name)
        return pd.read_parquet(path) if os.path.exists(path) else pd.DataFrame()

    def load_normalized_daily(self, dataset_name: str) -> pd.DataFrame:
        """Load a normalized daily dataset by concatenating normalized partitions."""
        spec = DATASET_SPECS[dataset_name]
        pattern = os.path.join(self.paths.normalized_root, spec.raw_pattern)
        files = sorted(glob(pattern, recursive=True))
        if not files:
            return pd.DataFrame()
        return pd.concat(
            [
                pd.read_parquet(path)
                for path in iter_progress(
                    files,
                    total=len(files),
                    desc=f"Load normalized {dataset_name}",
                    unit="file",
                    leave=False,
                )
            ],
            ignore_index=True,
        )

    def _holder_number_ledger_status(self) -> dict[str, Any]:
        """Classify holder-number rows that are not yet materializable."""
        ledger_path = self.ledger_path("holder_number")
        sidecar_path = self.ledger_sidecar_path("holder_number", HOLDER_NUMBER_UNUSABLE_SUFFIX)
        status = {
            "holder_number_unusable_pit_rows": 0,
            "holder_number_next_open_beyond_calendar_rows": 0,
            "holder_number_post_calendar_disclosure_rows": 0,
            "holder_number_calendar_end": None,
            "holder_number_unusable_pit_path": sidecar_path if os.path.exists(sidecar_path) else None,
        }
        if os.path.exists(sidecar_path):
            status["holder_number_unusable_pit_rows"] = int(len(pd.read_parquet(sidecar_path)))
        if not os.path.exists(ledger_path):
            return status

        holder_ledger = pd.read_parquet(ledger_path)
        if holder_ledger.empty:
            return status

        disclosure = normalize_date_series(holder_ledger.get("disclosure_date", pd.Series(pd.NaT, index=holder_ledger.index)))
        effective = normalize_date_series(holder_ledger.get("effective_date", pd.Series(pd.NaT, index=holder_ledger.index)))
        calendar_end = self.open_calendar().max()
        pending_mask = effective.isna() & disclosure.notna()
        boundary_mask = pending_mask & (disclosure <= calendar_end)
        future_mask = pending_mask & (disclosure > calendar_end)
        status.update(
            {
                "holder_number_next_open_beyond_calendar_rows": int(boundary_mask.sum()),
                "holder_number_post_calendar_disclosure_rows": int(future_mask.sum()),
                "holder_number_calendar_end": calendar_end.strftime("%Y-%m-%d"),
            }
        )
        return status

    def build_ledger(self, dataset_name: str) -> dict[str, Any]:
        """Build a PIT ledger for one revision-aware dataset."""
        if dataset_name not in PERIODIC_LEDGER_DATASETS:
            return {"dataset": dataset_name, "rows": 0, "skipped": True}
        spec = DATASET_SPECS[dataset_name]
        normalized = self.load_normalized_periodic(dataset_name)
        if normalized.empty:
            return {"dataset": dataset_name, "rows": 0, "skipped": True}
        work = normalized.copy()
        if "disclosure_date" not in work.columns:
            work["disclosure_date"] = disclosure_dates(work, spec.ann_date_column, spec.f_ann_date_column)
        work["effective_date"] = strictly_next_open_trade_day(work["disclosure_date"], self.open_calendar())
        if "ts_code" in work.columns and "qlib_code" not in work.columns:
            work["qlib_code"] = work["ts_code"].map(lambda value: ts_code_to_qlib(value, lower=True))
        unusable_rows = pd.DataFrame()
        if dataset_name == "holder_number" and "disclosure_date" in work.columns:
            unusable_rows = work.loc[work["disclosure_date"].isna()].copy()
            work = work.loc[work["disclosure_date"].notna()].copy()
        if dataset_name == "forecast":
            key_columns = [column for column in ("ts_code", "end_date", "disclosure_date", "type") if column in work.columns]
        elif dataset_name == "dividends":
            key_columns = [
                column
                for column in ("ts_code", "end_date", "disclosure_date", "record_date", "ex_date", "pay_date", "div_proc")
                if column in work.columns
            ]
        elif dataset_name == "stk_holdertrade":
            # Event stream with multi-row per (ts_code, ann_date): one row per
            # holder-transaction. Keying only on (ts_code, disclosure_date)
            # would collapse all distinct holder events into one row and lose
            # ~99% of the data. Include holder_name + in_de + change_vol in the
            # key so each transaction stays distinct while still allowing
            # revisions (same key, different announcement text) to be merged.
            key_columns = [
                column
                for column in ("ts_code", "ann_date", "disclosure_date", "holder_name", "in_de", "change_vol")
                if column in work.columns
            ]
        elif dataset_name == "report_rc":
            # Analyst forecasts: multi-row per (ts_code, report_date) — one per
            # analyst-team × forecast quarter. Keying on (ts_code, end_date,
            # disclosure_date) like the generic branch would collapse all analysts
            # and quarters for a stock-date into ONE row (report_rc has no
            # end_date) — the same ~99% loss the stk_holdertrade branch prevents.
            # Key on a stable analyst-team identity + the forecast quarter; exact
            # duplicate payload rows still merge via collapse_duplicate_versions'
            # content-hash tie-break (the _src_* tail columns are stripped at
            # normalize). effective_date is already next_open(max(report_date,
            # create_time)) from the f_ann_date_column="create_time" spec.
            work["normalized_analyst_id"] = normalized_analyst_id(
                work.get("org_name", pd.Series("", index=work.index)),
                work.get("author_name", pd.Series("", index=work.index)),
            )
            key_columns = [
                column
                for column in ("ts_code", "report_date", "normalized_analyst_id", "quarter")
                if column in work.columns
            ]
        else:
            key_columns = [column for column in ("ts_code", "end_date", "disclosure_date") if column in work.columns]
            if "report_type" in work.columns and spec.kind in {"periodic_snapshot", "periodic_cumulative", "periodic_direct_sq"}:
                key_columns.append("report_type")
        ledger, conflicts = collapse_duplicate_versions(work, key_columns)
        output_path = self.ledger_path(dataset_name)
        ensure_directory(os.path.dirname(output_path))
        ledger.to_parquet(output_path, index=False)
        result = {"dataset": dataset_name, "rows": int(len(ledger)), "conflicts": len(conflicts)}
        if dataset_name == "holder_number":
            sidecar_path = self.ledger_sidecar_path(dataset_name, HOLDER_NUMBER_UNUSABLE_SUFFIX)
            ensure_directory(os.path.dirname(sidecar_path))
            if unusable_rows.empty:
                if os.path.exists(sidecar_path):
                    os.remove(sidecar_path)
            else:
                unusable_rows.to_parquet(sidecar_path, index=False)
            result.update(self._holder_number_ledger_status())
        return result

    def build_ledgers(self, datasets: Iterable[str] | None = None) -> dict[str, dict[str, Any]]:
        """Build ledgers for the selected revision-aware datasets."""
        results = {}
        selected = self.selected_datasets(datasets)
        for dataset_name in iter_progress(selected, total=len(selected), desc="Build ledgers", unit="dataset", leave=True):
            if dataset_name in PERIODIC_LEDGER_DATASETS:
                results[dataset_name] = self.build_ledger(dataset_name)
        return results

    def collect_ledger_outputs(self, datasets: Iterable[str] | None = None) -> dict[str, dict[str, Any]]:
        """Collect existing ledger artifacts without rebuilding them."""
        results: dict[str, dict[str, Any]] = {}
        for dataset_name in self.selected_datasets(datasets):
            if dataset_name not in PERIODIC_LEDGER_DATASETS:
                continue
            ledger_path = self.ledger_path(dataset_name)
            results[dataset_name] = {
                "dataset": dataset_name,
                "path": ledger_path,
                "exists": os.path.exists(ledger_path),
            }
            if dataset_name == "holder_number":
                results[dataset_name].update(self._holder_number_ledger_status())
        return results

    def _load_price_frame(self) -> pd.DataFrame:
        files = self.raw_files("daily")
        if not files:
            raise BuildGateError("No market daily Parquet files found")
        frames = []
        for path in iter_progress(files, total=len(files), desc="Load daily raw", unit="file", leave=False):
            raw = self._read_raw_file("daily", path)
            repaired, _ = self._apply_price_repair_overrides("daily", raw, source_name=os.path.basename(path))
            frames.append(repaired)
        price = pd.concat(frames, ignore_index=True)
        price = self._standardize_common_columns(price)
        price["date"] = price["trade_date"]
        price["symbol"] = price["ts_code"]
        # Same scalar-default bug pattern as _normalize_daily_partition: use an
        # index-matched Series so the chained ``.fillna`` survives a missing
        # column (only hits test mocks; real Tushare daily always has adj_factor).
        adj_raw = price.get("adj_factor", pd.Series(1.0, index=price.index))
        price["factor"] = pd.to_numeric(adj_raw, errors="coerce").fillna(1.0)
        if "volume" not in price.columns and "vol" in price.columns:
            price["volume"] = price["vol"]
        return price

    def _load_index_frame(self) -> pd.DataFrame:
        files = self.raw_files("index_daily")
        if not files:
            return pd.DataFrame()
        frames = [
            self._read_raw_file("index_daily", path)
            for path in iter_progress(files, total=len(files), desc="Load index raw", unit="file", leave=False)
        ]
        index_df = pd.concat(frames, ignore_index=True)
        index_df = self._standardize_common_columns(index_df)
        index_df["date"] = index_df["trade_date"]
        index_df["symbol"] = index_df["ts_code"]
        index_df["factor"] = 1.0
        return index_df

    def _build_price_csvs(self, stage_csv_dir: str, target_symbols: set[str] | None = None) -> pd.DataFrame:
        ensure_directory(stage_csv_dir)
        price = self._load_price_frame()
        index_df = self._load_index_frame()
        if not index_df.empty:
            missing_columns = [column for column in price.columns if column not in index_df.columns]
            for column in missing_columns:
                index_df[column] = np.nan
            price = pd.concat([price, index_df[price.columns]], ignore_index=True)

        if target_symbols is not None:
            price = price[price["ts_code"].isin(target_symbols)].copy()

        price = price.sort_values(["symbol", "date"])
        numeric_fields = price.select_dtypes(include=[np.number]).columns.tolist()
        numeric_fields = [column for column in numeric_fields if column != "date"]
        group_count = price["symbol"].nunique()
        for symbol, group in iter_progress(
            price.groupby("symbol"),
            total=group_count,
            desc="Stage price csvs",
            unit="symbol",
            leave=False,
        ):
            qlib_code = ts_code_to_qlib(symbol, lower=True)
            csv_path = os.path.join(stage_csv_dir, f"{qlib_code}.csv")
            group[["date"] + numeric_fields].to_csv(csv_path, index=False)

        ranges = (
            price.groupby("symbol")["date"]
            .agg(price_start="min", price_end="max")
            .reset_index()
            .rename(columns={"symbol": "ts_code"})
        )
        ranges["qlib_code"] = ranges["ts_code"].map(lambda value: ts_code_to_qlib(value, lower=False))
        return ranges

    def _run_dump_bin(self, csv_dir: str, mode: Literal["all", "update"]) -> None:
        dump_script = os.path.join(self.paths.project_root, "workspace", "scripts", "dump_bin.py")
        verb = "dump_all" if mode == "all" else "dump_update"
        env = os.environ.copy()
        pythonpath_parts = [part for part in env.get("PYTHONPATH", "").split(os.pathsep) if part]
        max_workers = env.get("PIT_DUMP_MAX_WORKERS", "1")
        src_path = os.path.join(self.paths.project_root, "src")
        site_packages = os.path.join(self.paths.project_root, "venv", "Lib", "site-packages")
        for candidate in (src_path, site_packages):
            if os.path.isdir(candidate) and candidate not in pythonpath_parts:
                pythonpath_parts.append(candidate)
        if pythonpath_parts:
            env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
        cmd = [
            sys.executable,
            dump_script,
            verb,
            "--data_path",
            csv_dir,
            "--qlib_dir",
            self.paths.provider_dir,
            "--date_field_name",
            "date",
            "--max_workers",
            str(max_workers),
        ]
        subprocess.run(cmd, check=True, env=env)

    def _write_feature_series(self, feature_dir: str, field_name: str, values: np.ndarray) -> None:
        ref_info = self._bin_ref_cache.get(feature_dir)
        if ref_info is None and feature_dir not in self._bin_ref_cache:
            ref_info = get_bin_info(os.path.join(feature_dir, "close.day.bin"))
            self._bin_ref_cache[feature_dir] = ref_info
        if ref_info is None or not ref_info["valid"]:
            return
        start_index = ref_info["start_index"]
        length = ref_info["data_len"]
        slice_end = start_index + length
        aligned = np.full(length, np.nan, dtype=np.float32)
        available = max(min(len(values), slice_end) - start_index, 0)
        if available > 0:
            aligned[:available] = values[start_index : start_index + available].astype(np.float32)
        write_qlib_bin(os.path.join(feature_dir, f"{field_name}.day.bin"), aligned, start_index=start_index)

    def _apply_field_filter(self, fields: list[str]) -> list[str]:
        if not self.field_filter:
            return fields
        return [field for field in fields if field in self.field_filter]

    def _selected_metric_specs(self, specs: Iterable[DerivedMetricSpec]) -> list[DerivedMetricSpec]:
        metrics = list(specs)
        if not self.field_filter:
            return metrics
        return [spec for spec in metrics if spec.output_name in self.field_filter or spec.base_field in self.field_filter]

    def _build_family_quarter_parity_summary(
        self,
        family: StatementFamilySpec,
        cumulative_ledger: pd.DataFrame,
        quarterly_ledger: pd.DataFrame,
        quarter_fields: list[str],
        target_codes: set[str] | None = None,
    ) -> str | None:
        """Write a parity summary between direct quarterly rows and cumulative-derived quarter values."""
        if cumulative_ledger.empty or quarterly_ledger.empty or not quarter_fields:
            return None

        if target_codes is not None:
            cumulative_ledger = cumulative_ledger.loc[cumulative_ledger["qlib_code"].isin(target_codes)].copy()
            quarterly_ledger = quarterly_ledger.loc[quarterly_ledger["qlib_code"].isin(target_codes)].copy()
            if cumulative_ledger.empty or quarterly_ledger.empty:
                return None

        grouped_cumulative = {
            qlib_code: canonicalize_report_variants(group, "cumulative").sort_values(["effective_date", "end_date"]).to_dict("records")
            for qlib_code, group in cumulative_ledger.groupby("qlib_code")
        }
        summary_rows: list[dict[str, Any]] = []

        for qlib_code, quarter_group in iter_progress(
            quarterly_ledger.groupby("qlib_code"),
            total=quarterly_ledger["qlib_code"].nunique(),
            desc=f"Parity {family.name}",
            unit="symbol",
            leave=False,
        ):
            cumulative_rows = grouped_cumulative.get(qlib_code)
            if not cumulative_rows:
                continue
            quarter_group = canonicalize_report_variants(quarter_group, "quarterly")
            cumulative_state: dict[pd.Timestamp, dict[str, Any]] = {}
            cursor = 0
            field_errors: dict[str, list[float]] = {field_name: [] for field_name in quarter_fields}
            field_exact: dict[str, int] = {field_name: 0 for field_name in quarter_fields}

            for direct_row in quarter_group.sort_values(["effective_date", "end_date"]).to_dict("records"):
                direct_effective = pd.Timestamp(direct_row["effective_date"])
                while cursor < len(cumulative_rows) and pd.Timestamp(cumulative_rows[cursor]["effective_date"]) <= direct_effective:
                    current = cumulative_rows[cursor]
                    current["end_date"] = pd.Timestamp(current["end_date"])
                    cumulative_state[current["end_date"]] = current
                    cursor += 1

                direct_end = pd.Timestamp(direct_row["end_date"])
                for field_name in quarter_fields:
                    direct_value = direct_row.get(field_name)
                    derived_value = derive_single_quarter_value(cumulative_state, direct_end, field_name)
                    if pd.isna(direct_value) or pd.isna(derived_value):
                        continue
                    abs_error = abs(float(direct_value) - float(derived_value))
                    field_errors[field_name].append(abs_error)
                    if np.isclose(direct_value, derived_value, atol=1e-6, rtol=1e-6):
                        field_exact[field_name] += 1

            for field_name, errors in field_errors.items():
                if not errors:
                    continue
                values = np.asarray(errors, dtype=np.float64)
                overlap_count = int(values.size)
                summary_rows.append(
                    {
                        "family": family.name,
                        "qlib_code": qlib_code,
                        "field": field_name,
                        "overlap_count": overlap_count,
                        "exact_match_ratio": float(field_exact[field_name] / overlap_count),
                        "median_abs_error": float(np.nanmedian(values)),
                        "p90_abs_error": float(np.nanpercentile(values, 90)),
                        "max_abs_error": float(np.nanmax(values)),
                    }
                )

        if not summary_rows:
            return None

        audit_dir = os.path.join(self.paths.metadata_dir, "pit_audit")
        ensure_directory(audit_dir)
        output_path = os.path.join(audit_dir, f"{family.name}_quarter_parity.parquet")
        pd.DataFrame(summary_rows).to_parquet(output_path, index=False)
        return output_path

    def _materialize_stk_holdertrade(
        self,
        calendar: pd.DatetimeIndex,
        target_dirs: dict[str, str],
    ) -> list[str]:
        """Custom materializer for the stk_holdertrade event stream.

        Unlike statement data, stk_holdertrade has no ``end_date`` and carries
        multiple rows per (ts_code, ann_date) — one per holder transaction.
        ``materialize_visibility_segments`` assumes a fiscal-period key and is
        not appropriate. Instead aggregate per (qlib_code, effective_date) and
        write per-day time-series bins analogous to the daily-fact path:

          - ``holdertrade_net_vol``    : signed sum (IN = +change_vol, DE = -)
          - ``holdertrade_gross_vol``  : absolute sum of change_vol
          - ``holdertrade_net_ratio``  : signed sum of change_ratio
          - ``holdertrade_events``     : number of holder transactions

        Days with no event stay NaN (same convention as moneyflow /
        block_trade). Researchers who need per-holder detail can read the
        ledger at ``data/pit_ledger/stk_holdertrade/stk_holdertrade.parquet``
        directly.
        """
        ledger_path = self.ledger_path("stk_holdertrade")
        if not os.path.exists(ledger_path):
            return []
        ledger = pd.read_parquet(ledger_path)
        if ledger.empty:
            return []
        target_codes = set(target_dirs)
        if target_codes:
            ledger = ledger[ledger["qlib_code"].isin(target_codes)].copy()
        if ledger.empty:
            return []
        ledger = ledger.dropna(subset=["effective_date"]).copy()
        ledger["effective_date"] = normalize_date_series(ledger["effective_date"])
        ledger = ledger.dropna(subset=["effective_date"]).copy()

        change_vol = pd.to_numeric(ledger.get("change_vol"), errors="coerce")
        change_ratio = pd.to_numeric(ledger.get("change_ratio"), errors="coerce")
        in_de = ledger.get("in_de", pd.Series("", index=ledger.index)).astype(str).str.upper()
        sign = np.where(in_de == "DE", -1.0, 1.0)
        ledger["_signed_vol"] = change_vol * sign
        ledger["_abs_vol"] = change_vol.abs()
        ledger["_signed_ratio"] = change_ratio * sign
        ledger["_event_count"] = 1

        agg = (
            ledger.groupby(["qlib_code", "effective_date"], sort=False)
            .agg(
                holdertrade_net_vol=("_signed_vol", "sum"),
                holdertrade_gross_vol=("_abs_vol", "sum"),
                holdertrade_net_ratio=("_signed_ratio", "sum"),
                holdertrade_events=("_event_count", "sum"),
            )
            .reset_index()
        )
        fields = ["holdertrade_net_vol", "holdertrade_gross_vol", "holdertrade_net_ratio", "holdertrade_events"]
        fields = self._apply_field_filter(fields)
        if not fields:
            return []
        written: list[str] = []
        per_symbol = {code: group.sort_values("effective_date") for code, group in agg.groupby("qlib_code")}
        for qlib_code, feature_dir in iter_progress(
            target_dirs.items(),
            total=len(target_dirs),
            desc="Materialize stk_holdertrade",
            unit="symbol",
            leave=False,
        ):
            symbol_df = per_symbol.get(qlib_code)
            if symbol_df is None or symbol_df.empty:
                continue
            frame = symbol_df.set_index("effective_date")[fields].reindex(calendar).astype(np.float32, copy=False)
            for field_name in fields:
                self._write_feature_series(feature_dir, field_name, frame[field_name].to_numpy(dtype=np.float32))
                written.append(field_name)
        return sorted(set(written))

    def _materialize_snapshot_dataset(
        self,
        dataset_name: str,
        calendar: pd.DatetimeIndex,
        target_dirs: dict[str, str],
    ) -> list[str]:
        ledger = pd.read_parquet(self.ledger_path(dataset_name))
        if dataset_name == "holder_number":
            ledger = ledger.dropna(subset=["effective_date"])
        target_codes = set(target_dirs)
        if target_codes:
            ledger = ledger[ledger["qlib_code"].isin(target_codes)].copy()
        if ledger.empty:
            return []
        numeric_fields = self._apply_field_filter(payload_numeric_columns(ledger))
        written_fields: list[str] = []
        symbol_count = ledger["qlib_code"].nunique()
        for qlib_code, group in iter_progress(
            ledger.groupby("qlib_code"),
            total=symbol_count,
            desc=f"Materialize {dataset_name}",
            unit="symbol",
            leave=False,
        ):
            feature_dir = target_dirs.get(qlib_code)
            if feature_dir is None:
                continue
            canonical_group = canonicalize_report_variants(group, "snapshot") if "report_type" in group.columns else group
            segments = materialize_visibility_segments(canonical_group, calendar, slot_depth=self.slot_depth)
            arrays = arrays_from_snapshot_segments(segments, numeric_fields, len(calendar), self.slot_depth)
            for name, values in arrays.items():
                self._write_feature_series(feature_dir, name, values)
                written_fields.append(name)
            if self.write_compat_aliases:
                for field_name in numeric_fields:
                    self._write_feature_series(feature_dir, field_name, arrays[f"{field_name}_q0"])
                    written_fields.append(field_name)
        return sorted(set(written_fields))

    def _materialize_dividend_compat(
        self,
        calendar: pd.DatetimeIndex,
        target_dirs: dict[str, str],
    ) -> list[str]:
        ledger = pd.read_parquet(self.ledger_path("dividends"))
        target_codes = set(target_dirs)
        if target_codes:
            ledger = ledger[ledger["qlib_code"].isin(target_codes)].copy()
        if ledger.empty:
            return []
        numeric_fields = [field for field in payload_numeric_columns(ledger) if field in DIVIDEND_COMPAT_FIELDS]
        written: list[str] = []
        symbol_count = ledger["qlib_code"].nunique()
        for qlib_code, group in iter_progress(
            ledger.groupby("qlib_code"),
            total=symbol_count,
            desc="Materialize dividends",
            unit="symbol",
            leave=False,
        ):
            feature_dir = target_dirs.get(qlib_code)
            if feature_dir is None:
                continue
            segments = materialize_visibility_segments(group, calendar, slot_depth=1)
            arrays = arrays_from_snapshot_segments(segments, numeric_fields, len(calendar), 1)
            for field_name in numeric_fields:
                self._write_feature_series(feature_dir, field_name, arrays[f"{field_name}_q0"])
                written.append(field_name)
        return written

    def _materialize_flow_family(
        self,
        family: StatementFamilySpec,
        calendar: pd.DatetimeIndex,
        target_dirs: dict[str, str],
    ) -> tuple[list[str], str | None]:
        cumulative_ledger = (
            pd.read_parquet(self.ledger_path(family.cumulative_dataset))
            if family.cumulative_dataset and os.path.exists(self.ledger_path(family.cumulative_dataset))
            else pd.DataFrame()
        )
        quarterly_ledger = (
            pd.read_parquet(self.ledger_path(family.quarterly_dataset))
            if family.quarterly_dataset and os.path.exists(self.ledger_path(family.quarterly_dataset))
            else pd.DataFrame()
        )

        raw_cumulative_fields = self._apply_field_filter(payload_numeric_columns(cumulative_ledger)) if not cumulative_ledger.empty else []
        raw_quarter_fields = self._apply_field_filter(payload_numeric_columns(quarterly_ledger)) if not quarterly_ledger.empty else []
        selected_cumulative_metrics = self._selected_metric_specs(family.cumulative_metrics)
        selected_quarter_metrics = self._selected_metric_specs(family.quarter_metrics)

        cumulative_fields = sorted(
            set(raw_cumulative_fields)
            | {spec.base_field for spec in selected_cumulative_metrics if not cumulative_ledger.empty and spec.base_field in cumulative_ledger.columns}
            | {spec.base_field for spec in selected_quarter_metrics if not cumulative_ledger.empty and spec.base_field in cumulative_ledger.columns}
        )
        quarter_fields = sorted(
            set(raw_quarter_fields)
            | set(raw_cumulative_fields)
            | {spec.base_field for spec in selected_quarter_metrics}
        )

        cumulative_groups = (
            {qlib_code: group for qlib_code, group in cumulative_ledger.groupby("qlib_code")}
            if not cumulative_ledger.empty
            else {}
        )
        quarterly_groups = (
            {qlib_code: group for qlib_code, group in quarterly_ledger.groupby("qlib_code")}
            if not quarterly_ledger.empty
            else {}
        )
        target_codes = set(target_dirs)
        symbol_codes = sorted((set(cumulative_groups) | set(quarterly_groups)) & target_codes)

        written: list[str] = []
        for qlib_code in iter_progress(
            symbol_codes,
            total=len(symbol_codes),
            desc=f"Materialize {family.name}",
            unit="symbol",
            leave=False,
        ):
            feature_dir = target_dirs.get(qlib_code)
            if feature_dir is None:
                continue
            cumulative_group = cumulative_groups.get(qlib_code, pd.DataFrame())
            quarterly_group = quarterly_groups.get(qlib_code, pd.DataFrame())
            if not cumulative_group.empty:
                cumulative_group = canonicalize_report_variants(cumulative_group, "cumulative")
            if not quarterly_group.empty:
                quarterly_group = canonicalize_report_variants(quarterly_group, "quarterly")

            cumulative_segments = materialize_visibility_segments(cumulative_group, calendar, slot_depth=self.slot_depth)
            cumulative_arrays, _ = arrays_from_flow_segments(cumulative_segments, cumulative_fields, len(calendar), self.slot_depth)

            canonical_quarter_segments = materialize_canonical_quarter_segments(
                cumulative_group,
                quarterly_group,
                calendar,
                quarter_fields=quarter_fields,
                slot_depth=self.slot_depth,
            )
            quarter_arrays = arrays_from_snapshot_segments(canonical_quarter_segments, quarter_fields, len(calendar), self.slot_depth)
            canonical_quarters = {
                f"{field_name}_sq_q{slot}": quarter_arrays[f"{field_name}_q{slot}"]
                for field_name in quarter_fields
                for slot in range(self.slot_depth)
            }

            cumulative_metric_arrays = arrays_from_metric_segments(
                cumulative_segments,
                [spec for spec in selected_cumulative_metrics if spec.base_field in cumulative_fields],
                len(calendar),
                self.slot_depth,
            )
            quarter_metric_arrays = arrays_from_metric_segments(
                canonical_quarter_segments,
                [spec for spec in selected_quarter_metrics if spec.base_field in quarter_fields],
                len(calendar),
                self.slot_depth,
            )

            for field_name in raw_cumulative_fields:
                for slot in range(self.slot_depth):
                    name = f"{field_name}_cum_q{slot}"
                    values = cumulative_arrays.get(name)
                    if values is None:
                        continue
                    self._write_feature_series(feature_dir, name, values)
                    written.append(name)
            for field_name in quarter_fields:
                should_write_field = field_name in raw_quarter_fields or field_name in raw_cumulative_fields
                if not should_write_field:
                    continue
                for slot in range(self.slot_depth):
                    name = f"{field_name}_sq_q{slot}"
                    values = canonical_quarters.get(name)
                    if values is None:
                        continue
                    self._write_feature_series(feature_dir, name, values)
                    written.append(name)
            for metric_arrays in (cumulative_metric_arrays, quarter_metric_arrays):
                for name, values in metric_arrays.items():
                    self._write_feature_series(feature_dir, name, values)
                    written.append(name)
                    if name.endswith("_q0"):
                        metric_name = name[:-3]
                        self._write_feature_series(feature_dir, metric_name, values)
                        written.append(metric_name)

            if self.write_compat_aliases:
                for field_name in raw_cumulative_fields:
                    self._write_feature_series(feature_dir, field_name, cumulative_arrays[f"{field_name}_cum_q0"])
                    written.append(field_name)
                for field_name in quarter_fields:
                    if field_name not in raw_quarter_fields and field_name not in raw_cumulative_fields:
                        continue
                    self._write_feature_series(feature_dir, f"{field_name}_q", canonical_quarters[f"{field_name}_sq_q0"])
                    written.append(f"{field_name}_q")

        parity_path = self._build_family_quarter_parity_summary(
            family=family,
            cumulative_ledger=cumulative_ledger,
            quarterly_ledger=quarterly_ledger,
            quarter_fields=[field_name for field_name in quarter_fields if field_name in quarterly_ledger.columns] if not quarterly_ledger.empty else [],
            target_codes=target_codes,
        )
        return sorted(set(written)), parity_path

    def _materialize_daily_dataset(
        self,
        dataset_name: str,
        calendar: pd.DatetimeIndex,
        target_dirs: dict[str, str],
    ) -> list[str]:
        daily = self.load_normalized_daily(dataset_name)
        if daily.empty:
            return []
        daily = self._standardize_common_columns(daily)
        daily["trade_date"] = normalize_date_series(daily["trade_date"])
        daily = daily.dropna(subset=["trade_date"])
        if dataset_name == "northbound":
            valid_ts_codes = set(self.stock_basic()["ts_code"].astype(str))
            invalid_mask = ~daily["ts_code"].astype(str).isin(valid_ts_codes)
            invalid_mask |= ~daily["ts_code"].astype(str).str.endswith((".SH", ".SZ"), na=False)
            invalid_count = int(invalid_mask.sum())
            if invalid_count:
                raise BuildGateError(
                    f"Normalized northbound still has {invalid_count} non-A-share or unmapped rows"
                )
        prefix = EVENT_LIKE_DAILY_FIELD_PREFIX.get(dataset_name)
        if prefix:
            rename_map = {
                column: f"{prefix}{column}"
                for column in daily.columns
                if column not in _EVENT_LIKE_RESERVED_COLUMNS
            }
            if rename_map:
                daily = daily.rename(columns=rename_map)
        numeric_fields = self._apply_field_filter(payload_numeric_columns(daily))
        written: list[str] = []
        available_dates = set(daily["trade_date"].dt.strftime("%Y%m%d"))
        nonconnect_days = self.expected_empty_dates("northbound") if dataset_name == "northbound" else set()
        daily_groups = {ts_code: group.sort_values("trade_date") for ts_code, group in daily.groupby("ts_code")}
        date_strings = pd.Series(calendar.strftime("%Y%m%d"), index=calendar)
        valid_trade_dates = date_strings.isin(available_dates)
        margin_start_mask = calendar >= pd.Timestamp("2010-03-31")

        for qlib_code, feature_dir in iter_progress(
            target_dirs.items(),
            total=len(target_dirs),
            desc=f"Materialize {dataset_name}",
            unit="symbol",
            leave=False,
        ):
            ts_code = qlib_code.replace("_", ".").upper()
            symbol_df = daily_groups.get(ts_code)
            if symbol_df is None and dataset_name not in {"margin", "northbound"}:
                continue
            if symbol_df is None:
                frame = pd.DataFrame(index=calendar, columns=numeric_fields, dtype=np.float32)
            else:
                frame = symbol_df.set_index("trade_date")[numeric_fields].reindex(calendar).astype(np.float32, copy=False)
            if dataset_name == "margin":
                zero_mask = valid_trade_dates & margin_start_mask
                frame.loc[zero_mask] = frame.loc[zero_mask].fillna(0.0)
            elif dataset_name == "northbound":
                for field_name in numeric_fields:
                    series = frame[field_name].copy()
                    if nonconnect_days:
                        connect_mask = date_strings.isin(nonconnect_days)
                        series.loc[connect_mask] = series.ffill().loc[connect_mask]
                    zero_mask = valid_trade_dates & series.isna()
                    series.loc[zero_mask] = 0.0
                    frame[field_name] = series

            for field_name in numeric_fields:
                self._write_feature_series(feature_dir, field_name, frame[field_name].to_numpy(dtype=np.float32))
                written.append(field_name)
        return sorted(set(written))

    def _copy_sidecars(self, price_ranges: pd.DataFrame) -> dict[str, Any]:
        ensure_directory(self.paths.metadata_dir)
        ensure_directory(self.paths.events_dir)
        security_master = self.stock_basic()
        security_master.to_parquet(os.path.join(self.paths.metadata_dir, "security_master.parquet"), index=False)

        industry_path = os.path.join(self.paths.normalized_root, "universe", "industry_sw2021", "industry_sw2021.parquet")
        if os.path.exists(industry_path):
            shutil.copy2(industry_path, os.path.join(self.paths.metadata_dir, "industry_sw2021.parquet"))

        index_weights_pattern = os.path.join(self.paths.normalized_root, "universe", "index_weights", "*.parquet")
        for source_path in glob(index_weights_pattern):
            target = os.path.join(self.paths.metadata_dir, "index_weights", os.path.basename(source_path))
            ensure_directory(os.path.dirname(target))
            shutil.copy2(source_path, target)

        dividend_ledger_path = self.ledger_path("dividends")
        if os.path.exists(dividend_ledger_path):
            shutil.copy2(dividend_ledger_path, os.path.join(self.paths.events_dir, "dividends.parquet"))

        instruments_dir = os.path.join(self.paths.provider_dir, "instruments")
        summary = build_all_stocks_universe(
            security_master=security_master,
            price_ranges=price_ranges,
            instruments_dir=instruments_dir,
            metadata_dir=self.paths.metadata_dir,
        )

        index_weights_frames = [pd.read_parquet(source_path) for source_path in glob(index_weights_pattern)]
        index_summary = {}
        if index_weights_frames:
            index_weights = pd.concat(index_weights_frames, ignore_index=True)
            index_summary = build_index_universes(index_weights, instruments_dir)

        st_rows = build_st_universe(
            stock_st_daily=pd.read_parquet(os.path.join(self.paths.data_root, "reference", "stock_st_daily.parquet")),
            namechange=pd.read_parquet(os.path.join(self.paths.data_root, "reference", "namechange.parquet")),
            trading_calendar=self.open_calendar(),
            output_path=os.path.join(instruments_dir, "st_stocks.txt"),
        )
        readme_path = write_instruments_readme(instruments_dir)
        return {"all_stocks": summary, "index_universes": index_summary, "st_rows": st_rows, "readme": readme_path}

    def _prepare_scoped_update_provider(self, target_symbols: set[str]) -> None:
        """Copy the minimal provider base needed for a touched-symbol validation build."""
        if os.path.isdir(self.paths.provider_dir):
            shutil.rmtree(self.paths.provider_dir)
        ensure_directory(self.paths.provider_dir)

        for subdir in ("calendars", "instruments"):
            source_dir = os.path.join(self.paths.qlib_dir, subdir)
            target_dir = os.path.join(self.paths.provider_dir, subdir)
            if os.path.isdir(source_dir):
                shutil.copytree(source_dir, target_dir)

        source_features = os.path.join(self.paths.qlib_dir, "features")
        target_features = os.path.join(self.paths.provider_dir, "features")
        ensure_directory(target_features)
        target_codes = {ts_code_to_qlib(symbol, lower=True) for symbol in target_symbols}
        for qlib_code in sorted(target_codes):
            source_dir = os.path.join(source_features, qlib_code)
            target_dir = os.path.join(target_features, qlib_code)
            if os.path.isdir(source_dir):
                shutil.copytree(source_dir, target_dir)

    def materialize_provider(
        self,
        mode: Literal["all", "update"] = "all",
        touched_symbols: Iterable[str] | None = None,
        datasets: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        """Build the staged provider and write PIT-aware feature families."""
        target_symbols = set(touched_symbols) if touched_symbols else None
        scoped_update = mode == "update" and target_symbols is not None and os.path.isdir(self.paths.qlib_dir)

        if scoped_update:
            self._prepare_scoped_update_provider(target_symbols)
        elif mode == "update" and os.path.isdir(self.paths.qlib_dir):
            if os.path.isdir(self.paths.provider_dir):
                shutil.rmtree(self.paths.provider_dir)
            shutil.copytree(self.paths.qlib_dir, self.paths.provider_dir)
        else:
            if os.path.isdir(self.paths.provider_dir):
                shutil.rmtree(self.paths.provider_dir)
            ensure_directory(self.paths.provider_dir)
        self._bin_ref_cache = {}

        if scoped_update:
            price_ranges = pd.DataFrame()
        else:
            csv_dir = os.path.join(self.paths.build_root, "csv_temp")
            if os.path.isdir(csv_dir):
                shutil.rmtree(csv_dir)
            price_ranges = self._build_price_csvs(csv_dir, target_symbols=target_symbols)
            self._run_dump_bin(csv_dir, mode=mode)
            shutil.rmtree(csv_dir, ignore_errors=True)

        calendar = provider_calendar(self.paths.provider_dir)
        features_root = os.path.join(self.paths.provider_dir, "features")
        target_dirs = {
            name: os.path.join(features_root, name)
            for name in os.listdir(features_root)
            if os.path.isdir(os.path.join(features_root, name))
        }
        if target_symbols is not None:
            target_qlib_codes = {ts_code_to_qlib(symbol, lower=True) for symbol in target_symbols}
            target_dirs = {name: path for name, path in target_dirs.items() if name in target_qlib_codes}
        written: dict[str, list[str]] = {}
        family_audits: dict[str, str] = {}
        active_datasets = set(self.selected_datasets(datasets))
        for family in self.selected_statement_families(datasets):
            if family.kind == "snapshot" and family.snapshot_dataset and os.path.exists(self.ledger_path(family.snapshot_dataset)):
                written[family.name] = self._materialize_snapshot_dataset(family.snapshot_dataset, calendar, target_dirs)
            elif family.kind == "flow":
                family_written, parity_path = self._materialize_flow_family(family, calendar, target_dirs)
                written[family.name] = family_written
                if parity_path:
                    family_audits[family.name] = parity_path
        if "indicators" in active_datasets and os.path.exists(self.ledger_path("indicators")):
            written["indicators"] = self._materialize_snapshot_dataset("indicators", calendar, target_dirs)
        if "forecast" in active_datasets and os.path.exists(self.ledger_path("forecast")):
            written["forecast"] = self._materialize_snapshot_dataset("forecast", calendar, target_dirs)
        if "holder_number" in active_datasets and os.path.exists(self.ledger_path("holder_number")):
            written["holder_number"] = self._materialize_snapshot_dataset("holder_number", calendar, target_dirs)
        if "stk_holdertrade" in active_datasets and os.path.exists(self.ledger_path("stk_holdertrade")):
            # Custom materializer: event stream (no end_date, multi-row per
            # ann_date). Aggregates to per-day net / gross / ratio / count.
            written["stk_holdertrade"] = self._materialize_stk_holdertrade(calendar, target_dirs)
        if "dividends" in active_datasets and os.path.exists(self.ledger_path("dividends")):
            written["dividends"] = self._materialize_dividend_compat(calendar, target_dirs)
        for dataset_name in (
            "moneyflow", "northbound", "margin", "stk_limit",
            # New alpha endpoints (added 2026-04-16): daily-fact kind,
            # materialize via the generic per-stock .day.bin writer.
            "top_list", "top_inst", "block_trade", "cyq_perf",
        ):
            if dataset_name in active_datasets:
                written[dataset_name] = self._materialize_daily_dataset(dataset_name, calendar, target_dirs)

        sidecars = {"reused_existing_provider_sidecars": scoped_update}
        if not scoped_update:
            sidecars = self._copy_sidecars(price_ranges)
        return {
            "written_fields": written,
            "sidecars": sidecars,
            "family_audits": family_audits,
            "target_symbols": sorted(target_symbols) if target_symbols else [],
            "write_compat_aliases": self.write_compat_aliases,
        }

    def validate_provider(
        self,
        profiled_datasets: dict[str, DatasetProfile],
        touched_symbols: Iterable[str] | None = None,
    ) -> tuple[list[str], list[str]]:
        """Validate the staged provider and return ``(errors, warnings)``."""
        errors: list[str] = []
        warnings: list[str] = []

        for name, profile in profiled_datasets.items():
            if not profile.ok:
                errors.extend([f"{name}: {message}" for message in profile.errors])
            warnings.extend([f"{name}: {message}" for message in profile.warnings])
            if profile.unexpected_missing_dates:
                message = f"{name}: missing {len(profile.unexpected_missing_dates)} expected dates"
                if self.allow_exceptions:
                    warnings.append(message)
                else:
                    errors.append(message)

        features_root = os.path.join(self.paths.provider_dir, "features")
        if not os.path.isdir(features_root):
            errors.append("Missing provider features directory")
            return errors, warnings

        selected_stock_names = sorted(os.listdir(features_root))
        if touched_symbols:
            selected_codes = {ts_code_to_qlib(symbol, lower=True) for symbol in touched_symbols}
            selected_stock_names = [name for name in selected_stock_names if name in selected_codes]
        else:
            selected_stock_names = selected_stock_names[:200]

        for stock_name in selected_stock_names:
            feature_dir = os.path.join(features_root, stock_name)
            if not os.path.isdir(feature_dir):
                continue
            files = [path for path in os.listdir(feature_dir) if path.endswith(".day.bin")]
            if not files:
                continue
            field_names = [path.replace(".day.bin", "") for path in files if path != "close.day.bin"]
            if self.field_filter:
                field_names = [name for name in field_names if name in self.field_filter]
            else:
                field_names = field_names[:200]
            if not field_names:
                continue
            bin_errors = validate_stock_bins(feature_dir, field_names, reference_field="close")
            errors.extend([f"{stock_name}: {message}" for message in bin_errors if "not found" not in message.lower()])

        instruments_dir = os.path.join(self.paths.provider_dir, "instruments")
        for file_name in ["all.txt", "all_stocks.txt", "st_stocks.txt", "csi300.txt", "csi500.txt", "csi1000.txt"]:
            if not os.path.exists(os.path.join(instruments_dir, file_name)):
                errors.append(f"Missing instruments file: {file_name}")

        if os.path.exists(self.ledger_path("holder_number")):
            holder_ledger = pd.read_parquet(self.ledger_path("holder_number"))
            missing_disclosure = int(holder_ledger["disclosure_date"].isna().sum()) if "disclosure_date" in holder_ledger.columns else 0
            if missing_disclosure:
                errors.append(f"holder_number active ledger still has {missing_disclosure} rows without disclosure dates")

        return errors, warnings

    def _write_manifest(
        self,
        profiled_datasets: dict[str, DatasetProfile],
        normalized_datasets: dict[str, list[str]],
        ledgers_built: dict[str, dict[str, Any]],
        provider_result: dict[str, Any],
        validation_errors: list[str],
        validation_warnings: list[str],
    ) -> None:
        manifest = {
            "build_id": self.build_id,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "project_root": self.paths.project_root,
            "data_root": self.paths.data_root,
            "provider_dir": self.paths.provider_dir,
            "profiled_datasets": {name: asdict(profile) for name, profile in profiled_datasets.items()},
            "normalized_datasets": normalized_datasets,
            "ledgers_built": ledgers_built,
            "provider_result": provider_result,
            "validation": {"errors": validation_errors, "warnings": validation_warnings},
        }
        ensure_directory(os.path.dirname(self.paths.manifest_path))
        with open(self.paths.manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2, default=str)

    def _flush_backfill_provenance(self) -> dict[str, str]:
        """P0-5: Write accumulated backfill provenance events to parquet sidecars.

        Called once at the end of the staged build. Produces one parquet file
        per dataset under ``metadata/pit_audit/backfill_provenance/``. The
        buffers are cleared after flush so subsequent builds start fresh.

        Returns:
            dict mapping ``dataset_name -> sidecar_path`` for datasets that
            had at least one backfill event.
        """
        if not self._backfill_provenance:
            return {}
        audit_dir = os.path.join(self.paths.metadata_dir, "pit_audit", "backfill_provenance")
        ensure_directory(audit_dir)
        written: dict[str, str] = {}
        for dataset_name, events in self._backfill_provenance.items():
            if not events:
                continue
            output_path = os.path.join(audit_dir, f"{dataset_name}.parquet")
            pd.DataFrame(events).to_parquet(output_path, index=False)
            written[dataset_name] = output_path
            logger.info(
                "PIT backfill provenance sidecar: %s (%d events)",
                output_path,
                len(events),
            )
        self._backfill_provenance.clear()
        return written

    def publish(
        self,
        *,
        calendar_policy_id: str = "frozen_20260227_system_build",
        emit_manifest: bool = True,
    ) -> None:
        """Atomically promote the staged provider into ``data/qlib_data``.

        Uses ``os.replace()`` which is atomic ONLY when both paths live on the
        same volume (same ``st_dev`` in ``os.stat``). Cross-volume replace
        falls back to copy-then-delete on Windows, which is NOT atomic and
        leaves a window where the Qlib backend is in an inconsistent state.

        This method now enforces the same-volume invariant with a hard error:
        if the staged provider and target live on different drives, publish is
        refused with remediation guidance. See CLAUDE.md §6.3 "Backend Rebuild
        Discipline" for the full contract.

        After the atomic swap, a ``provider_build.json`` manifest is emitted
        under ``<qlib_dir>/metadata/`` so every formal artifact downstream can
        record ``provider_build_id``. Disable with ``emit_manifest=False`` only
        for hot-restore drills where attestation is not desired.
        """
        if not os.path.isdir(self.paths.provider_dir):
            raise BuildGateError("Cannot publish: staged provider directory is missing")

        # P0-6: Cross-volume atomicity guard. Dereference symlinks before
        # the device comparison so symlinked mounts don't trigger false
        # positives. The target parent is the directory that will hold
        # `qlib_dir` after the rename — we check its device, not qlib_dir
        # itself (which may not exist yet on first publish).
        staged_real = os.path.realpath(self.paths.provider_dir)
        staged_stat = os.stat(staged_real)
        target_parent = os.path.dirname(os.path.abspath(self.paths.qlib_dir))
        ensure_directory(target_parent)
        target_real_parent = os.path.realpath(target_parent)
        target_stat = os.stat(target_real_parent)
        if staged_stat.st_dev != target_stat.st_dev:
            raise BuildGateError(
                f"Publish cross-volume detected: staged={staged_real} "
                f"(device {staged_stat.st_dev}), target={target_real_parent} "
                f"(device {target_stat.st_dev}). os.replace() is only atomic "
                f"within the same volume. Move the staged build onto the "
                f"target volume first, or change the target qlib_dir to live "
                f"on the same drive as the staged build."
            )

        backup_dir = f"{self.paths.qlib_dir}.bak_{self.build_id}"
        if os.path.exists(backup_dir):
            shutil.rmtree(backup_dir)
        if os.path.isdir(self.paths.qlib_dir):
            os.replace(self.paths.qlib_dir, backup_dir)
        os.replace(self.paths.provider_dir, self.paths.qlib_dir)
        logger.info("Published staged provider to %s", self.paths.qlib_dir)

        if emit_manifest:
            self._emit_provider_manifest_at_publish(calendar_policy_id=calendar_policy_id)

    def _emit_provider_manifest_at_publish(self, *, calendar_policy_id: str) -> None:
        """Emit data/qlib_data/metadata/provider_build.json after publish.

        Pulls calendar bounds from the freshly-published Qlib provider's
        ``calendars/day.txt`` so the manifest reflects the actual on-disk
        state, not the builder's intended range. Resolves the source git
        commit best-effort.
        """
        try:
            calendars_path = os.path.join(self.paths.qlib_dir, "calendars", "day.txt")
            with open(calendars_path, "r", encoding="utf-8") as handle:
                lines = [line.strip() for line in handle if line.strip()]
            if not lines:
                logger.warning("Calendars file empty; skipping manifest emission")
                return
            calendar_start = lines[0]
            calendar_end = lines[-1]
        except OSError as exc:
            logger.warning("Failed to read calendars/day.txt for manifest emission: %s", exc)
            return

        source_commit: str | None = None
        try:
            import subprocess
            source_commit = (
                subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip() or None
            )
        except (OSError, subprocess.CalledProcessError):
            source_commit = None

        from src.data_infra.provider_manifest import emit_manifest_at_publish
        try:
            emit_manifest_at_publish(
                qlib_dir=self.paths.qlib_dir,
                provider_build_id=self.build_id,
                calendar_policy_id=calendar_policy_id,
                calendar_start_date=calendar_start,
                calendar_end_date=calendar_end,
                data_end_date=calendar_end,
                source_git_commit=source_commit,
                builder_mode="all",
                builder_stage="full",
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to emit provider manifest at publish: %s", exc)

    def run(
        self,
        mode: Literal["all", "update"] = "all",
        publish: bool = False,
        datasets: Iterable[str] | None = None,
        touched_symbols: Iterable[str] | None = None,
        stage: Literal["full", "upstream-only", "provider-only"] = "full",
    ) -> BuildResult:
        """Run the full staged build."""
        if publish and stage == "upstream-only":
            raise BuildGateError("Cannot publish an upstream-only staged build")

        if stage == "provider-only":
            profiled = self.collect_profiles(datasets=datasets, use_persisted=True)
            normalized = self.collect_normalized_outputs(datasets=datasets)
            ledgers = self.collect_ledger_outputs(datasets=datasets)
        else:
            profiled = self.profile_datasets(datasets=datasets)
            normalized = self.normalize_datasets(datasets=datasets)
            ledgers = self.build_ledgers(datasets=datasets)

        if stage == "upstream-only":
            provider_result = {"skipped": True, "stage": stage}
            validation_errors = []
            validation_warnings = []
        else:
            provider_result = self.materialize_provider(mode=mode, touched_symbols=touched_symbols, datasets=datasets)
            validation_errors, validation_warnings = self.validate_provider(profiled, touched_symbols=touched_symbols)

        # P0-5: flush backfill provenance sidecar before the manifest so its
        # paths can be referenced from the manifest itself.
        provenance_sidecars = self._flush_backfill_provenance()
        if provenance_sidecars:
            provider_result = dict(provider_result) if isinstance(provider_result, dict) else {}
            provider_result["backfill_provenance_sidecars"] = provenance_sidecars

        self._write_manifest(profiled, normalized, ledgers, provider_result, validation_errors, validation_warnings)

        if validation_errors and not self.allow_exceptions:
            raise BuildGateError("Staged PIT build failed validation:\n- " + "\n- ".join(validation_errors[:20]))

        if publish:
            self.publish()

        return BuildResult(
            build_id=self.build_id,
            provider_dir=self.paths.provider_dir if not publish else self.paths.qlib_dir,
            manifest_path=self.paths.manifest_path,
            validation_errors=validation_errors,
            validation_warnings=validation_warnings,
            profiled_datasets=list(profiled),
            normalized_datasets=list(normalized),
            ledgers_built=list(ledgers),
        )


def build_qlib_backend(
    data_root: str | None = None,
    qlib_dir: str | None = None,
    mode: Literal["all", "update"] = "all",
    datasets: Iterable[str] | None = None,
    include_phase3: bool = True,
    publish: bool = False,
    build_id: str | None = None,
    slot_depth: int = SLOT_DEPTH_DEFAULT,
    field_filter: list[str] | None = None,
    touched_symbols: Iterable[str] | None = None,
    allow_exceptions: bool = False,
    write_compat_aliases: bool = True,
    stage: Literal["full", "upstream-only", "provider-only"] = "full",
) -> BuildResult:
    """Public helper used by the pipeline entrypoints."""
    builder = StagedQlibBackendBuilder(
        data_root=data_root,
        qlib_dir=qlib_dir,
        build_id=build_id,
        include_phase3=include_phase3,
        slot_depth=slot_depth,
        field_filter=field_filter,
        allow_exceptions=allow_exceptions,
        write_compat_aliases=write_compat_aliases,
    )
    return builder.run(
        mode=mode,
        publish=publish,
        datasets=datasets,
        touched_symbols=touched_symbols,
        stage=stage,
    )
