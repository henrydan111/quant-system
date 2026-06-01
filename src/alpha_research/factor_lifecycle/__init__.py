"""Factor-lifecycle revalidation modules (Phase 4).

Tested ports of the walk-forward factor-revalidation scripts. Two strictly-separated
modes (the separation is the leakage guard — see ``revalidation.py``):

  * ``run_is_walk_forward`` — FORMAL IS-only walk-forward for the ``draft -> candidate``
    decision; structurally bounded so neither OOS prices NOR OOS-realizing labels are
    ever loaded (the forward-return label is future-looking).
  * ``run_historical_revalidation`` — NON-formal full-window (IS + OOS) investigation;
    a faithful port of the legacy scripts, labeled ``historical_investigation``.

Pure metric builders live in ``metrics.py``; the split status rules in ``status_rules.py``.
"""

from .metrics import (
    factor_ic,
    rank_icir,
    yearly_sign_consistency,
    yearly_fold_count,
    long_only_topbucket,
)
from .status_rules import (
    assign_historical_status,
    assign_candidate_status,
)
from .revalidation import (
    revalidate_panel,
    run_historical_catalog_revalidation,
    run_historical_derived_revalidation,
    RESULT_EVIDENCE_CLASS,
)
from .walk_forward_validation import (
    run_is_walk_forward,
    load_is_windowed_panel,
    build_is_windowed_panel,
    IsWindowedPanel,
    WalkForwardResult,
    IsEndLeakageError,
    NoHeldoutBlockError,
    realization_date,
    last_usable_factor_date,
    load_open_trading_days,
)
from . import report

__all__ = [
    "factor_ic",
    "rank_icir",
    "yearly_sign_consistency",
    "yearly_fold_count",
    "long_only_topbucket",
    "assign_historical_status",
    "assign_candidate_status",
    "revalidate_panel",
    "run_historical_catalog_revalidation",
    "run_historical_derived_revalidation",
    "RESULT_EVIDENCE_CLASS",
    "run_is_walk_forward",
    "load_is_windowed_panel",
    "build_is_windowed_panel",
    "IsWindowedPanel",
    "WalkForwardResult",
    "IsEndLeakageError",
    "NoHeldoutBlockError",
    "realization_date",
    "last_usable_factor_date",
    "load_open_trading_days",
    "report",
]
