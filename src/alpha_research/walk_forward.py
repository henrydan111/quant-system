from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

import pandas as pd


TRAIN_YEARS = 5
VALIDATION_YEARS = 2
TEST_YEARS = 1
STEP_YEARS = 1


@dataclass(frozen=True)
class FoldSpec:
    fold_id: str
    train_start: str
    train_end: str
    validation_start: str
    validation_end: str
    test_start: str
    test_end: str


@dataclass(frozen=True)
class HoldoutSpec:
    window_type: str
    train_start: str
    train_end: str
    validation_start: str
    validation_end: str
    start: str
    end: str


@dataclass(frozen=True)
class TimeSplit:
    is_start: str
    is_end: str
    oos_start: str
    oos_end: str
    walk_forward_config: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        try:
            is_start = pd.Timestamp(self.is_start)
            is_end = pd.Timestamp(self.is_end)
            oos_start = pd.Timestamp(self.oos_start)
            oos_end = pd.Timestamp(self.oos_end)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"TimeSplit dates must be parseable by pd.Timestamp: {exc}") from exc
        if is_start >= is_end:
            raise ValueError(
                f"TimeSplit invariant: is_start ({self.is_start}) must be strictly before is_end ({self.is_end})"
            )
        if oos_start >= oos_end:
            raise ValueError(
                f"TimeSplit invariant: oos_start ({self.oos_start}) must be strictly before oos_end ({self.oos_end})"
            )
        if is_end >= oos_start:
            raise ValueError(
                f"TimeSplit invariant: is_end ({self.is_end}) must be strictly before oos_start ({self.oos_start})"
            )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TimeSplit":
        valid_keys = {"is_start", "is_end", "oos_start", "oos_end", "walk_forward_config"}
        filtered = {key: value for key, value in dict(payload).items() if key in valid_keys}
        return cls(**filtered)

    def with_stage(self, stage: str) -> dict[str, object]:
        if stage not in ("is_only", "is_val", "oos_test"):
            raise ValueError(f"stage must be one of is_only|is_val|oos_test, got {stage!r}")
        return {**self.to_dict(), "stage": stage}


def build_walk_forward_folds(
    start_date: str,
    end_date: str,
    train_years: int = TRAIN_YEARS,
    validation_years: int = VALIDATION_YEARS,
    test_years: int = TEST_YEARS,
    step_years: int = STEP_YEARS,
) -> tuple[list[FoldSpec], HoldoutSpec | None]:
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)
    full_test_last_year = end_ts.year if (end_ts.month == 12 and end_ts.day == 31) else end_ts.year - 1
    train_start_year = start_ts.year
    folds: list[FoldSpec] = []
    fold_num = 1

    while True:
        train_end_year = train_start_year + train_years - 1
        validation_start_year = train_end_year + 1
        validation_end_year = validation_start_year + validation_years - 1
        test_start_year = validation_end_year + 1
        test_end_year = test_start_year + test_years - 1
        if test_end_year > full_test_last_year:
            break
        folds.append(
            FoldSpec(
                fold_id=f"fold_{fold_num:02d}_{test_start_year}",
                train_start=f"{train_start_year}-01-01",
                train_end=f"{train_end_year}-12-31",
                validation_start=f"{validation_start_year}-01-01",
                validation_end=f"{validation_end_year}-12-31",
                test_start=f"{test_start_year}-01-01",
                test_end=f"{test_end_year}-12-31",
            )
        )
        fold_num += 1
        train_start_year += step_years

    holdout: HoldoutSpec | None = None
    full_test_end = pd.Timestamp(f"{full_test_last_year}-12-31")
    if end_ts > full_test_end:
        holdout_train_start = full_test_last_year - (train_years + validation_years - 1)
        holdout_train_end = holdout_train_start + train_years - 1
        holdout_validation_start = holdout_train_end + 1
        holdout_validation_end = holdout_validation_start + validation_years - 1
        holdout = HoldoutSpec(
            window_type="holdout",
            train_start=f"{holdout_train_start}-01-01",
            train_end=f"{holdout_train_end}-12-31",
            validation_start=f"{holdout_validation_start}-01-01",
            validation_end=f"{holdout_validation_end}-12-31",
            start=f"{full_test_last_year + 1}-01-01",
            end=end_ts.strftime("%Y-%m-%d"),
        )
    return folds, holdout
