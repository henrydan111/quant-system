"""Phase-bound data-access guards for the pre-open strategy context.

The pre-open hook ``before_market_open`` must not read same-day data (the
no-lookahead contract). Withholding ``day_data``/``day_data_indexed`` is NOT
enough on its own — the raw feeder (``context.feeder.get_features``) and the
exchange's ``_feeder`` are same-day side channels that bypass the empty frames.

These wrappers, used ONLY for the pre-open (and initialize) context, bound feeder
reads to ``end_time <= max_datetime`` (the previous trading day) and hide the
exchange's ``_feeder`` / direct data-fetch path, while forwarding the legitimate
tradability methods (``is_suspended`` / ``is_limit_up`` / ``can_buy`` /
``get_lot_size`` / ...). The engine restores the raw feeder + exchange for the
``on_bar`` (EOD) phase, where same-day data IS knowable.

GPT cross-review R2 Blocker-1 (2026-06-22).
"""
from __future__ import annotations

import pandas as pd


class PreOpenLookaheadError(RuntimeError):
    """Raised when pre-open strategy code attempts to read same-day/future data."""


class PhaseBoundFeeder:
    """Feeder view for the pre-open phase. ``get_features`` is allowed only when
    ``end_time <= max_datetime`` (the last visible / previous trading day); any
    other feeder access is refused (no strategy needs the raw feeder pre-open)."""

    def __init__(self, inner, max_datetime):
        object.__setattr__(self, "_inner", inner)
        object.__setattr__(self, "_max",
                           pd.Timestamp(max_datetime) if max_datetime is not None else None)

    def get_features(self, instruments, fields, start_time, end_time, *args, **kwargs):
        mx = object.__getattribute__(self, "_max")
        if mx is None or pd.Timestamp(end_time) > mx:
            raise PreOpenLookaheadError(
                f"pre_open: cannot read features through {end_time} "
                f"(max visible date = {None if mx is None else mx.date()})")
        return object.__getattribute__(self, "_inner").get_features(
            instruments, fields, start_time, end_time, *args, **kwargs)

    def __getattr__(self, name):
        raise PreOpenLookaheadError(f"pre_open: feeder access {name!r} is not allowed")


class StrategyExchangeView:
    """Exchange view for the pre-open phase. Forwards PUBLIC tradability methods
    but refuses the raw ``_feeder`` and direct data-fetch side channels."""

    _BLOCKED = ("get_features", "preload", "preload_features")

    def __init__(self, inner):
        object.__setattr__(self, "_inner", inner)

    def __getattr__(self, name):
        if name.startswith("_") or name in StrategyExchangeView._BLOCKED:
            raise PreOpenLookaheadError(f"pre_open: exchange access {name!r} is not allowed")
        return getattr(object.__getattribute__(self, "_inner"), name)
