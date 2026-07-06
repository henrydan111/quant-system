"""C9 · Phase-0 reporting discipline (CONTRACTS.md C9) — diagnostics ONLY.

Phase 0 reports IC / RankIC / ICIR / monotonicity / turnover / quantile-spread
as **research diagnostics only**. No deployable performance claim (CAGR,
Sharpe, max drawdown, annual/net return) is allowed until the Phase-1
event-driven total-return backtest applies T+1, limit-up/down, suspension,
corporate actions, realistic costs and gross<=1x (§3.3 price-return vs
total-return distinction).

Enforcement is fail-closed via a metric-key ALLOWLIST: any key outside the
diagnostic vocabulary raises ``Phase0DisciplineError`` — never silently
accepted. Enforced by tests/result_analysis/test_phase0_diagnostics_only.py.
"""
from __future__ import annotations

import copy
import re
from numbers import Number

#: Diagnostic vocabulary (C9). A metric key is allowed iff it equals a token or
#: starts with ``token + "_"``. Order longest-first so ``rank_icir`` wins over ``ic``.
PHASE0_METRIC_ALLOWLIST: tuple[str, ...] = (
    "quantile_spread",
    "monotonicity",
    "rank_icir",
    "rank_ic",
    "turnover",
    "coverage",
    "decay",
    "icir",
    "n_obs",
    "n_names",
    "ic",
)

#: Nested breakdown buckets: their values must be dicts, validated recursively.
_BUCKET_KEYS = {"by_year", "by_month", "by_half", "by_universe", "by_horizon", "by_regime"}
_BUCKET_LABEL_RE = re.compile(r"^\d{4}([-_]?\d{2})?(H[12])?$")

_ENVELOPE = {
    "phase": "phase0",
    "evidence_class": "research_diagnostics_only",
    "deployable_claim": False,
    "contract": "C9",
}


class Phase0DisciplineError(Exception):
    """A Phase-0 report tried to carry a non-diagnostic (deployable) metric."""


def _key_allowed(key: str) -> bool:
    k = key.lower()
    return any(k == tok or k.startswith(tok + "_") for tok in PHASE0_METRIC_ALLOWLIST)


def _is_bucket_label(key: str) -> bool:
    return key.lower() in _BUCKET_KEYS or bool(_BUCKET_LABEL_RE.match(key))


def _validate_metrics(metrics: dict, path: str = "") -> None:
    if not isinstance(metrics, dict):
        raise Phase0DisciplineError(f"metrics at '{path or '.'}' must be a dict")
    for key, value in metrics.items():
        where = f"{path}.{key}" if path else key
        if isinstance(value, dict):
            if not (_is_bucket_label(key) or _key_allowed(key)):
                raise Phase0DisciplineError(
                    f"non-diagnostic breakdown key '{where}' (C9 fail-closed)"
                )
            _validate_metrics(value, where)
            continue
        if not _key_allowed(key):
            raise Phase0DisciplineError(
                f"metric '{where}' is not in the Phase-0 diagnostic allowlist "
                f"{PHASE0_METRIC_ALLOWLIST} — deployable claims (CAGR/Sharpe/MDD/"
                f"returns) require the Phase-1 event-driven total-return gate (C9)"
            )
        if not isinstance(value, Number):
            raise Phase0DisciplineError(f"metric '{where}' must be numeric, got {type(value)}")


def build_phase0_report(
    metrics: dict,
    *,
    universe: str,
    window: str,
    notes: str = "",
) -> dict:
    """Build a diagnostics-only Phase-0 report envelope (fail-closed)."""
    _validate_metrics(metrics)
    report = dict(_ENVELOPE)
    report.update(
        {
            "universe": universe,
            "window": window,
            "notes": notes,
            "metrics": copy.deepcopy(metrics),
        }
    )
    return report


def assert_phase0_report(report: dict) -> None:
    """Validate a (possibly persisted/tampered) Phase-0 report. Raises on violation."""
    if not isinstance(report, dict):
        raise Phase0DisciplineError("report must be a dict")
    for key, expected in _ENVELOPE.items():
        if report.get(key) != expected:
            raise Phase0DisciplineError(
                f"envelope field '{key}' must be {expected!r}, got {report.get(key)!r}"
            )
    _validate_metrics(report.get("metrics", {}))
