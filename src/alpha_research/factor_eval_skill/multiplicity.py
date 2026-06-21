"""D6 — system-level OOS-window multiplicity (the §11 self-review gap).

Design: ``workspace/research/factor_eval_methodology/FACTOR_EVAL_PARTG_BUILD_DESIGN.md``
(v2, D6). The 2021-2026 OOS window is shared + bounded; every DISTINCT frozen set that spends
it raises system-level false-discovery risk, and the per-set seal does not adjust for that.

Layer split (GPT cross-review): the SEAL layer (:class:`OosWindowLedgerStore`) only COUNTS +
records spends — it never changes an OOS metric or the per-set bar. THIS module is the
report/approval layer: it reads the count and emits an ACTION by threshold. A fixed per-set
bar can remain, but once enough distinct sets spend the window, an ``approved_signal`` claim
needs an explicit acknowledgement or adjusted-FDR/override context.

This is DISCLOSURE + GUIDANCE, not an automatic bar change: the action tells the approval
path what is required; it does not silently mutate any verdict.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# action codes (escalating).
ACTION_DISCLOSE = "disclose"                       # n < warn: just stamp the denominator
ACTION_ACKNOWLEDGE = "disclose_acknowledge"        # warn <= n < hard: reviewer must acknowledge
ACTION_REQUIRE = "require_adjusted_or_override"     # n >= hard: BH/FDR or max-stat context, or an explicit override

DEFAULT_WARN_THRESHOLD = 5
DEFAULT_HARD_THRESHOLD = 10


@dataclass(frozen=True)
class MultiplicityReport:
    """The system-level OOS-window multiplicity context stamped on a sealed-OOS report."""

    oos_window_id: str
    n_spent: int                 # distinct frozen sets that have spent this window
    by_tier: dict                # distinct-set counts by evidence_tier
    action: str
    warn_threshold: int
    hard_threshold: int
    note: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "oos_window_id": self.oos_window_id, "n_spent": self.n_spent, "by_tier": dict(self.by_tier),
            "action": self.action, "warn_threshold": self.warn_threshold,
            "hard_threshold": self.hard_threshold, "note": self.note,
        }


def _action_for(n: int, warn: int, hard: int) -> str:
    if n < warn:
        return ACTION_DISCLOSE
    if n < hard:
        return ACTION_ACKNOWLEDGE
    return ACTION_REQUIRE


def oos_window_multiplicity(
    ledger,
    oos_window_id: str,
    *,
    warn_threshold: int = DEFAULT_WARN_THRESHOLD,
    hard_threshold: int = DEFAULT_HARD_THRESHOLD,
    pending_self: bool = False,
) -> MultiplicityReport:
    """Compute the multiplicity context for ``oos_window_id`` from the ledger.

    ``pending_self=True`` previews the context as if THIS (not-yet-recorded) seal were added
    — used by ``seal --mode show`` to disclose "you would be the (n+1)th frozen set to spend
    this window" before the spend.
    """
    distinct = ledger.distinct_frozen_sets(oos_window_id)
    n = len(distinct) + (1 if pending_self else 0)
    by_tier = ledger.tier_counts(oos_window_id)
    action = _action_for(n, warn_threshold, hard_threshold)
    nth = "would be the" if pending_self else "is the"
    note = (
        f"this {nth} {n}{_ordinal_suffix(n)} distinct frozen set to spend OOS window "
        f"{oos_window_id} (warn>={warn_threshold}, hard>={hard_threshold}). "
        + {
            ACTION_DISCLOSE: "Disclosure only; per-set bar unchanged.",
            ACTION_ACKNOWLEDGE: "Reviewer acknowledgement required before an approved_signal claim.",
            ACTION_REQUIRE: "An approved_signal claim requires BH/FDR or max-stat context, "
                            "or an explicit SystemOOSMultiplicityOverride.",
        }[action]
    )
    return MultiplicityReport(str(oos_window_id), n, by_tier, action, warn_threshold, hard_threshold, note)


def _ordinal_suffix(n: int) -> str:
    if 10 <= (n % 100) <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
