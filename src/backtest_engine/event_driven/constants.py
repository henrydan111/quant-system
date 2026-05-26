"""Shared constants for the event-driven backtester.

Lives in its own module to avoid circular imports — both ``engine.py`` and the
high-level wrapper in ``__init__.py`` need to read ``ENGINE_REQUIRED_FIELDS``.
"""

from __future__ import annotations


# Canonical list of Qlib expressions the BacktestEngine itself fetches every
# trading day inside ``_fetch_day_data``. Formal runs MUST preload these
# (plus any strategy-specific factor fields) before the day loop starts;
# otherwise every day pays a per-day ``D.features`` round trip.
#
# Defined as a tuple so it can be used as a default argument without aliasing,
# and exported as a frozenset for set-membership assertions in tests.
ENGINE_REQUIRED_FIELDS: tuple[str, ...] = (
    "$open",
    "$close",
    "$high",
    "$low",
    "$vol",
    "$amount",
    "$pre_close",
    "$adj_factor",
)
ENGINE_REQUIRED_FIELDS_SET: frozenset[str] = frozenset(ENGINE_REQUIRED_FIELDS)


# Formal run modes auto-enable strict preload + provenance recording.
# Sandbox / historical-investigation runs may leave run_mode=None.
FORMAL_RUN_MODES: frozenset[str] = frozenset(
    {"formal", "oos_test", "joinquant_replication"}
)
