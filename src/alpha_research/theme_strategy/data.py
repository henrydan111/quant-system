from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import yaml
from src.research_orchestrator.cache_manifest import CacheContext
from src.research_orchestrator.qlib_windowed_features import qlib_windowed_features

from .registry import FieldDefinition
from .schema import FieldInventoryRow


LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def load_config() -> dict:
    return yaml.safe_load((PROJECT_ROOT / "config.yaml").read_text(encoding="utf-8"))


def resolve_data_root() -> Path:
    config = load_config()
    data_root = Path(config["storage"]["data_root"])
    if not data_root.is_absolute():
        data_root = PROJECT_ROOT / data_root
    return data_root.resolve()


def resolve_qlib_dir() -> Path:
    config = load_config()
    qlib_dir = Path(config["storage"]["qlib_data_dir"])
    if not qlib_dir.is_absolute():
        qlib_dir = PROJECT_ROOT / qlib_dir
    return qlib_dir.resolve()


def normalize_multiindex(obj: pd.Series | pd.DataFrame) -> pd.Series | pd.DataFrame:
    if isinstance(obj.index, pd.MultiIndex) and obj.index.names[0] == "instrument":
        return obj.swaplevel().sort_index()
    if not obj.index.is_monotonic_increasing:
        return obj.sort_index()
    return obj


def qlib_to_ts_code(code: str) -> str:
    return str(code).replace("_", ".")


def ts_to_qlib_code(code: str) -> str:
    return str(code).replace(".", "_")


def chunked(items: Iterable, size: int) -> Iterable[list]:
    bucket: list = []
    for item in items:
        bucket.append(item)
        if len(bucket) >= size:
            yield bucket
            bucket = []
    if bucket:
        yield bucket


def coverage_tier_from_ratio(coverage_ratio: float) -> str:
    if coverage_ratio >= 0.70:
        return "A"
    if coverage_ratio >= 0.40:
        return "B"
    if coverage_ratio >= 0.25:
        return "C"
    return "D"


@dataclass(frozen=True)
class ProjectPaths:
    data_root: Path
    qlib_dir: Path
    st_path: Path


@dataclass
class ResearchSupport:
    project_paths: ProjectPaths
    trade_calendar: list[pd.Timestamp]
    trade_calendar_index: pd.DatetimeIndex
    trade_pos_by_date: dict[pd.Timestamp, int]
    stock_basic: pd.DataFrame
    stock_basic_map: pd.DataFrame
    benchmark_returns: pd.Series
    benchmark_close: pd.Series
    st_ranges: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]]
    index_membership_store: "IndexMembershipStore"


class QlibFieldProvider:
    """Small wrapper around Qlib D.features used by this theme framework."""

    def __init__(self, qlib_dir: Path | None = None):
        self.qlib_dir = (qlib_dir or resolve_qlib_dir()).resolve()
        self._qlib_initialized = False

    def _ensure_qlib(self) -> None:
        if self._qlib_initialized:
            return
        import qlib
        from qlib.config import REG_CN

        qlib.init(provider_uri=str(self.qlib_dir), region=REG_CN, kernels=1)
        self._qlib_initialized = True

    def load_named_expressions(
        self,
        expressions: dict[str, str],
        start_date: str,
        end_date: str,
        stage: str = "is_only",
    ) -> dict[str, pd.Series]:
        """Load named Qlib expressions over a window.

        Args:
            expressions: dict of {name: qlib_expression_string}.
            start_date / end_date: window bounds.
            stage: ``"is_only"`` (default, backward compat) or ``"oos_test"``.
                Threaded into ``qlib_windowed_features`` so that cache_manifest
                enforcement and window safety are correctly stage-tagged. Plan
                ref: jolly-seeking-lollipop Gate 0 (fix for pre-existing OOS
                leak where stage was hardcoded to ``"is_only"`` regardless of
                actual run window).
        """
        if not expressions:
            return {}
        self._ensure_qlib()
        from qlib.data import D

        frame = qlib_windowed_features(
            instruments=D.instruments(market="all_stocks"),
            fields=list(expressions.values()),
            start_time=start_date,
            end_time=end_date,
            cache_context=CacheContext(),
            stage=stage,
        )
        frame.columns = list(expressions.keys())
        frame = normalize_multiindex(frame).astype(np.float32)
        return {name: frame[name].rename(name) for name in frame.columns}

    def audit_fields(
        self,
        field_defs: Iterable[FieldDefinition],
        start_date: str,
        end_date: str,
        *,
        sample_start: str | None = None,
        sample_end: str | None = None,
        bulk_chunk_size: int = 16,
    ) -> tuple[list[FieldInventoryRow], dict[str, pd.Series]]:
        sample_start = sample_start or start_date
        sample_end = sample_end or min(end_date, pd.Timestamp(start_date).strftime("%Y-%m-%d"))
        field_defs = list(field_defs)
        LOGGER.info(
            "Starting field audit for %d candidate fields (%s -> %s, sample %s -> %s)",
            len(field_defs),
            start_date,
            end_date,
            sample_start,
            sample_end,
        )
        available_defs: list[FieldDefinition] = []
        total_defs = len(field_defs)
        for idx, field_def in enumerate(field_defs, start=1):
            try:
                self.load_named_expressions(
                    {field_def.field_name: field_def.qlib_expression},
                    sample_start,
                    sample_end,
                )
                available_defs.append(field_def)
                LOGGER.info(
                    "Field audit sample check %d/%d passed: %s",
                    idx,
                    total_defs,
                    field_def.field_name,
                )
            except Exception as exc:
                LOGGER.info(
                    "Field audit sample check %d/%d skipped unavailable field %s: %s",
                    idx,
                    total_defs,
                    field_def.field_name,
                    exc,
                )

        full_series: dict[str, pd.Series] = {}
        total_chunks = max((len(available_defs) + bulk_chunk_size - 1) // bulk_chunk_size, 1)
        for chunk_num, chunk in enumerate(chunked(available_defs, bulk_chunk_size), start=1):
            mapping = {item.field_name: item.qlib_expression for item in chunk}
            LOGGER.info(
                "Field audit loading full history chunk %d/%d with %d fields",
                chunk_num,
                total_chunks,
                len(mapping),
            )
            full_series.update(self.load_named_expressions(mapping, start_date, end_date))
            LOGGER.info(
                "Field audit finished chunk %d/%d",
                chunk_num,
                total_chunks,
            )

        inventory_rows: list[FieldInventoryRow] = []
        for field_def in available_defs:
            series = full_series.get(field_def.field_name)
            if series is None:
                continue
            valid = series.dropna()
            coverage_ratio = float(valid.notna().mean()) if not series.empty else 0.0
            if valid.empty:
                coverage_start = ""
                coverage_end = ""
            else:
                dates = valid.index.get_level_values("datetime")
                coverage_start = pd.Timestamp(dates.min()).strftime("%Y-%m-%d")
                coverage_end = pd.Timestamp(dates.max()).strftime("%Y-%m-%d")
            inventory_rows.append(
                FieldInventoryRow(
                    field_name=field_def.field_name,
                    field_family=field_def.field_family,
                    provider_source=field_def.provider_source,
                    coverage_start=coverage_start,
                    coverage_end=coverage_end,
                    coverage_ratio=coverage_ratio,
                    freq_type=field_def.freq_type,
                    pit_safe=field_def.pit_safe,
                    theme_tags=field_def.theme_tags,
                )
            )
        inventory_rows.sort(key=lambda row: (row.field_family, row.field_name))
        LOGGER.info(
            "Field audit completed: %d available fields out of %d candidates",
            len(inventory_rows),
            total_defs,
        )
        return inventory_rows, full_series


class IndexMembershipStore:
    """Monthly index-weight snapshots converted into as-of membership sets."""

    def __init__(self, data_root: Path):
        self.data_root = data_root
        self.index_weight_dir = data_root / "universe" / "index_weights"
        self._monthly_cache: dict[str, dict[pd.Timestamp, set[str]]] = {}

    def _load_index_membership(self, index_code: str) -> dict[pd.Timestamp, set[str]]:
        if index_code in self._monthly_cache:
            return self._monthly_cache[index_code]
        monthly_map: dict[pd.Timestamp, set[str]] = {}
        if not self.index_weight_dir.exists():
            self._monthly_cache[index_code] = monthly_map
            return monthly_map
        for path in sorted(self.index_weight_dir.glob("index_weights_*.parquet")):
            df = pd.read_parquet(path)
            df = df.loc[df["index_code"] == index_code, ["con_code", "trade_date"]].copy()
            if df.empty:
                continue
            df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d", errors="coerce")
            asof_date = pd.Timestamp(df["trade_date"].max())
            members = {ts_to_qlib_code(code) for code in df["con_code"].dropna().astype(str).unique().tolist()}
            monthly_map[asof_date] = members
        self._monthly_cache[index_code] = monthly_map
        return monthly_map

    def members_on(self, index_code: str, date: pd.Timestamp) -> set[str]:
        monthly_map = self._load_index_membership(index_code)
        if not monthly_map:
            return set()
        valid_dates = [key for key in monthly_map if key <= pd.Timestamp(date)]
        if not valid_dates:
            return set()
        return monthly_map[max(valid_dates)]


def parse_st_ranges(st_path: Path) -> dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]]:
    ranges: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]] = defaultdict(list)
    if not st_path.exists():
        return {}
    for line in st_path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split("\t")
        if len(parts) < 3:
            continue
        code, start_str, end_str = parts[0], parts[1], parts[2]
        ranges[code].append((pd.Timestamp(start_str), pd.Timestamp(end_str)))
    return dict(ranges)


def is_st_on_date(
    code: str,
    date: pd.Timestamp,
    st_ranges: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]],
) -> bool:
    for start, end in st_ranges.get(code, []):
        if start <= date <= end:
            return True
    return False


def load_trade_calendar(data_root: Path) -> tuple[list[pd.Timestamp], pd.DatetimeIndex, dict[pd.Timestamp, int]]:
    trade_cal = pd.read_parquet(data_root / "reference" / "trade_cal.parquet").copy()
    trade_cal["cal_date"] = pd.to_datetime(trade_cal["cal_date"], format="%Y%m%d")
    calendar = trade_cal.loc[trade_cal["is_open"] == 1, "cal_date"].sort_values().tolist()
    calendar_index = pd.DatetimeIndex(calendar)
    return calendar, calendar_index, {date: idx for idx, date in enumerate(calendar)}


def load_stock_basic(data_root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    stock_basic = pd.read_parquet(data_root / "reference" / "stock_basic.parquet").copy()
    stock_basic["qlib_code"] = stock_basic["ts_code"].map(ts_to_qlib_code)
    stock_basic["list_date"] = pd.to_datetime(stock_basic["list_date"], format="%Y%m%d", errors="coerce")
    stock_basic["delist_date"] = pd.to_datetime(stock_basic["delist_date"], format="%Y%m%d", errors="coerce")
    stock_basic_map = stock_basic.set_index("qlib_code").sort_index()
    return stock_basic, stock_basic_map


def load_benchmark_series(data_root: Path, benchmark: str) -> tuple[pd.Series, pd.Series]:
    path = data_root / "market" / "index" / f"index_{benchmark}.parquet"
    frame = pd.read_parquet(path).copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], format="%Y%m%d", errors="coerce")
    frame = frame.sort_values("trade_date")
    close = frame.set_index("trade_date")["close"].astype(float)
    returns = (close / close.shift(1) - 1.0).dropna()
    returns.name = benchmark
    close.name = benchmark
    return returns, close


def build_support(benchmark: str, qlib_dir: Path | None = None) -> ResearchSupport:
    data_root = resolve_data_root()
    qlib_path = (qlib_dir or resolve_qlib_dir()).resolve()
    st_path = qlib_path / "instruments" / "st_stocks.txt"
    trade_calendar, trade_calendar_index, trade_pos_by_date = load_trade_calendar(data_root)
    stock_basic, stock_basic_map = load_stock_basic(data_root)
    benchmark_returns, benchmark_close = load_benchmark_series(data_root, benchmark)
    return ResearchSupport(
        project_paths=ProjectPaths(data_root=data_root, qlib_dir=qlib_path, st_path=st_path),
        trade_calendar=trade_calendar,
        trade_calendar_index=trade_calendar_index,
        trade_pos_by_date=trade_pos_by_date,
        stock_basic=stock_basic,
        stock_basic_map=stock_basic_map,
        benchmark_returns=benchmark_returns,
        benchmark_close=benchmark_close,
        st_ranges=parse_st_ranges(st_path),
        index_membership_store=IndexMembershipStore(data_root),
    )
