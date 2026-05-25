"""Historical indicator VIP refresh helpers.

This module provides the reusable logic for refreshing the raw
``data/fundamentals/indicators/`` store from ``fina_indicator_vip`` using
period-based all-stock pulls. It stages refreshed period files first, validates
them, and only then swaps them into the live raw store.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd
from tqdm import tqdm

from data_infra.fetchers import TushareFetcher
from data_infra.storage import StorageManager

PROJECT_ROOT = Path(__file__).resolve().parents[3]
INDICATOR_FILE_RE = re.compile(r"indicators_(\d{8})\.parquet$")
INDICATOR_REQUIRED_COLUMNS = ("ts_code", "ann_date", "end_date", "update_flag")


def quarter_end_periods(start_year: int, end_year: int) -> list[str]:
    """Return quarter-end periods in ``YYYYMMDD`` format."""
    periods: list[str] = []
    for year in range(start_year, end_year + 1):
        for mmdd in ("0331", "0630", "0930", "1231"):
            periods.append(f"{year}{mmdd}")
    return periods


def discover_indicator_periods(indicator_dir: str | Path) -> list[str]:
    """Discover ordered indicator periods from existing raw partitions."""
    base = Path(indicator_dir)
    periods = []
    for path in sorted(base.glob("indicators_*.parquet")):
        match = INDICATOR_FILE_RE.fullmatch(path.name)
        if match:
            periods.append(match.group(1))
    return sorted(dict.fromkeys(periods))


def filter_periods(
    periods: Iterable[str],
    start_period: str | None = None,
    end_period: str | None = None,
) -> list[str]:
    """Filter period strings inclusively."""
    selected = sorted(dict.fromkeys(str(period) for period in periods))
    if start_period:
        selected = [period for period in selected if period >= start_period]
    if end_period:
        selected = [period for period in selected if period <= end_period]
    return selected


def _normalize_period_series(series: pd.Series) -> pd.Series:
    normalized = pd.to_datetime(series, errors="coerce")
    return normalized.dt.strftime("%Y%m%d")


@dataclass
class IndicatorPeriodSummary:
    period: str
    row_count: int
    column_count: int
    duplicate_rows: int
    duplicate_groups: int
    has_update_flag: bool
    file_path: str


class IndicatorVipHistoryRefresher:
    """Refresh the historical indicator raw store from ``fina_indicator_vip``."""

    def __init__(
        self,
        *,
        config_path: str | None = None,
        data_root: str | None = None,
        build_id: str | None = None,
        output_root: str | None = None,
        fetcher: TushareFetcher | None = None,
        storage: StorageManager | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.storage = storage or StorageManager(data_root=data_root)
        self.fetcher = fetcher or TushareFetcher(config_path=config_path or str(PROJECT_ROOT / "config.yaml"))
        self.build_id = build_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.live_dir = Path(self.storage.data_root) / "fundamentals" / "indicators"
        self.stage_dir = Path(self.storage.data_root) / "fundamentals" / f"indicators__stage_{self.build_id}"
        self.archive_dir = Path(self.storage.data_root) / "fundamentals" / "_archive" / f"indicators_pre_{self.build_id}"
        base_output_root = Path(output_root) if output_root else (PROJECT_ROOT / "workspace" / "outputs" / "indicator_refresh")
        self.output_dir = base_output_root / self.build_id
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def resolve_periods(
        self,
        *,
        explicit_periods: Iterable[str] | None = None,
        start_period: str | None = None,
        end_period: str | None = None,
    ) -> list[str]:
        periods = list(explicit_periods) if explicit_periods is not None else discover_indicator_periods(self.live_dir)
        return filter_periods(periods, start_period=start_period, end_period=end_period)

    def fetch_period(self, period: str) -> pd.DataFrame:
        df = self.fetcher.fetch_fina_indicator_vip(period=period)
        if df is None or df.empty:
            return pd.DataFrame()
        return df.dropna(how="all", axis=1).copy()

    def validate_frame(self, period: str, df: pd.DataFrame, file_path: str) -> tuple[IndicatorPeriodSummary, list[str]]:
        errors: list[str] = []
        if df.empty:
            errors.append(f"{period}: no rows returned")
        missing_columns = [column for column in INDICATOR_REQUIRED_COLUMNS if column not in df.columns]
        if missing_columns:
            errors.append(f"{period}: missing required columns {missing_columns}")
        if "end_date" in df.columns:
            end_dates = _normalize_period_series(df["end_date"]).dropna().unique().tolist()
            mismatched = [value for value in end_dates if value != period]
            if mismatched:
                errors.append(f"{period}: end_date mismatch {sorted(mismatched)[:5]}")
        keys = [column for column in ("ts_code", "ann_date", "end_date") if column in df.columns]
        duplicate_rows = duplicate_groups = 0
        if keys:
            duplicate_mask = df.duplicated(subset=keys, keep=False)
            duplicate_rows = int(duplicate_mask.sum())
            if duplicate_rows:
                grouped = df.loc[duplicate_mask].groupby(keys, dropna=False).size()
                duplicate_groups = int((grouped > 1).sum())
        summary = IndicatorPeriodSummary(
            period=period,
            row_count=len(df),
            column_count=len(df.columns),
            duplicate_rows=duplicate_rows,
            duplicate_groups=duplicate_groups,
            has_update_flag="update_flag" in df.columns,
            file_path=file_path,
        )
        return summary, errors

    def _stage_period_file(self, period: str, df: pd.DataFrame) -> str:
        self.stage_dir.mkdir(parents=True, exist_ok=True)
        out_path = self.stage_dir / f"indicators_{period}.parquet"
        df.to_parquet(out_path, index=False)
        return str(out_path)

    def _validate_directory(self, base_dir: Path, periods: Iterable[str], *, desc: str) -> tuple[list[IndicatorPeriodSummary], list[str]]:
        summaries: list[IndicatorPeriodSummary] = []
        errors: list[str] = []
        ordered_periods = list(periods)
        for period in tqdm(ordered_periods, desc=desc, unit="period", dynamic_ncols=True, leave=False):
            path = base_dir / f"indicators_{period}.parquet"
            if not path.exists():
                errors.append(f"{period}: missing parquet file in {base_dir}")
                continue
            df = pd.read_parquet(path)
            summary, frame_errors = self.validate_frame(period, df, str(path))
            summaries.append(summary)
            errors.extend(frame_errors)
        return summaries, errors

    def _write_summary(self, *, periods: list[str], summaries: list[IndicatorPeriodSummary], source_dir: str, status: str) -> None:
        summary_path = self.output_dir / "summary.json"
        csv_path = self.output_dir / "period_summary.csv"
        payload = {
            "build_id": self.build_id,
            "status": status,
            "source_dir": source_dir,
            "period_count": len(periods),
            "periods": periods,
            "period_summaries": [asdict(summary) for summary in summaries],
            "written_at": datetime.now().isoformat(timespec="seconds"),
        }
        summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        if summaries:
            pd.DataFrame([asdict(summary) for summary in summaries]).to_csv(csv_path, index=False, encoding="utf-8-sig")

    def _swap_live_directory(self, summaries: list[IndicatorPeriodSummary]) -> None:
        self.archive_dir.parent.mkdir(parents=True, exist_ok=True)
        if self.archive_dir.exists():
            raise FileExistsError(f"Archive directory already exists: {self.archive_dir}")
        original_exists = self.live_dir.exists()
        if original_exists:
            os.rename(self.live_dir, self.archive_dir)
        try:
            os.rename(self.stage_dir, self.live_dir)
        except Exception:
            if original_exists and self.archive_dir.exists() and not self.live_dir.exists():
                os.rename(self.archive_dir, self.live_dir)
            raise

        total_rows = sum(summary.row_count for summary in summaries)
        file_paths = [str(self.live_dir / f"indicators_{summary.period}.parquet") for summary in summaries]
        self.storage._record_ingest_manifest(
            "indicators",
            file_paths,
            total_rows,
            source_params={
                "source": "tushare_fina_indicator_vip_refresh",
                "build_id": self.build_id,
                "period_start": summaries[0].period if summaries else None,
                "period_end": summaries[-1].period if summaries else None,
                "period_count": len(summaries),
            },
        )

    def run(
        self,
        *,
        explicit_periods: Iterable[str] | None = None,
        start_period: str | None = None,
        end_period: str | None = None,
        dry_run: bool = False,
        validate_only: bool = False,
    ) -> list[IndicatorPeriodSummary]:
        periods = self.resolve_periods(
            explicit_periods=explicit_periods,
            start_period=start_period,
            end_period=end_period,
        )
        if not periods:
            raise ValueError("No indicator periods selected for refresh")

        if dry_run:
            self.logger.info("Indicator VIP refresh dry-run selected for %d periods", len(periods))
            self._write_summary(periods=periods, summaries=[], source_dir=str(self.live_dir), status="dry-run")
            return []

        if validate_only:
            target_dir = self.stage_dir if self.stage_dir.exists() else self.live_dir
            summaries, errors = self._validate_directory(target_dir, periods, desc="Validate indicators")
            self._write_summary(periods=periods, summaries=summaries, source_dir=str(target_dir), status="validated")
            if errors:
                raise ValueError("Indicator validation failed:\n- " + "\n- ".join(errors[:20]))
            return summaries

        if self.stage_dir.exists():
            shutil.rmtree(self.stage_dir)
        self.stage_dir.mkdir(parents=True, exist_ok=True)

        fetch_summaries: list[IndicatorPeriodSummary] = []
        fetch_errors: list[str] = []
        for period in tqdm(periods, desc="Fetch indicator periods", unit="period", dynamic_ncols=True):
            df = self.fetch_period(period)
            file_path = self._stage_period_file(period, df) if not df.empty else str(self.stage_dir / f"indicators_{period}.parquet")
            summary, errors = self.validate_frame(period, df, file_path)
            fetch_summaries.append(summary)
            fetch_errors.extend(errors)
            if not errors:
                self.logger.info("Indicators %s: %d rows, %d cols", period, summary.row_count, summary.column_count)

        if fetch_errors:
            self._write_summary(periods=periods, summaries=fetch_summaries, source_dir=str(self.stage_dir), status="fetch_failed")
            raise ValueError("Indicator VIP refresh failed during fetch:\n- " + "\n- ".join(fetch_errors[:20]))

        summaries, errors = self._validate_directory(self.stage_dir, periods, desc="Validate staged indicators")
        self._write_summary(periods=periods, summaries=summaries, source_dir=str(self.stage_dir), status="staged")
        if errors:
            raise ValueError("Indicator staged validation failed:\n- " + "\n- ".join(errors[:20]))

        self._swap_live_directory(summaries)
        for summary in summaries:
            summary.file_path = str(self.live_dir / f"indicators_{summary.period}.parquet")
        self._write_summary(periods=periods, summaries=summaries, source_dir=str(self.live_dir), status="published_raw")
        return summaries
