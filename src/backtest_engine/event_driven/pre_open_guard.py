"""Phase-bound data-access guards for the pre-open strategy context.

The pre-open hook ``before_market_open`` must not read same-day data (the
no-lookahead contract). Withholding ``day_data``/``day_data_indexed`` is NOT
enough on its own — the raw feeder (``context.feeder.get_features``) and the
exchange's ``_feeder`` are same-day side channels that bypass the empty frames.

These wrappers, used ONLY for the pre-open (and initialize) context, bound feeder
reads to ``end_time <= max_datetime`` (the previous trading day) and hide the
exchange's ``_feeder`` / direct data-fetch path, while forwarding the legitimate
tradability methods. The engine restores the raw feeder + exchange for the
``on_bar`` (EOD) phase, where same-day data IS knowable.

Implemented with ``__getattribute__`` + ``__slots__`` (NOT just ``__getattr__``):
``__getattr__`` fires only AFTER normal lookup fails, so the wrapper's own stored
``_inner`` would still be readable through ``context.feeder._inner`` — the
side-channel the wrapper exists to close. ``__getattribute__`` intercepts EVERY
access and refuses private/raw names. This is not a malicious-code sandbox (Python
introspection can always be abused) — it closes the structural escape the wrapper
itself creates. GPT cross-review R2 Blocker-1 + R3 Blocker-1 (2026-06-22).
"""
from __future__ import annotations

import pandas as pd


class PreOpenLookaheadError(RuntimeError):
    """Raised when pre-open strategy code attempts to read same-day/future data."""


class PhaseBoundFeeder:
    """Feeder view for the pre-open phase. ``get_features`` is allowed only when
    ``end_time <= max_datetime`` (the last visible / previous trading day); EVERY
    other access — including the wrapper's own ``_inner``/``_max``/``__dict__`` — is
    refused, so the raw feeder cannot escape via ``context.feeder._inner``."""

    __slots__ = ("_inner", "_max")

    def __init__(self, inner, max_datetime):
        object.__setattr__(self, "_inner", inner)
        object.__setattr__(self, "_max",
                           pd.Timestamp(max_datetime) if max_datetime is not None else None)

    def __getattribute__(self, name):
        if name == "__dict__" or (name.startswith("_") and not name.startswith("__")):
            raise PreOpenLookaheadError(f"pre_open: feeder access {name!r} is not allowed")
        return object.__getattribute__(self, name)

    def __getattr__(self, name):
        raise PreOpenLookaheadError(f"pre_open: feeder access {name!r} is not allowed")

    def get_features(self, instruments, fields, start_time, end_time, *args, **kwargs):
        mx = object.__getattribute__(self, "_max")
        if mx is None or pd.Timestamp(end_time) > mx:
            raise PreOpenLookaheadError(
                f"pre_open: cannot read features through {end_time} "
                f"(max visible date = {None if mx is None else mx.date()})")
        inner = object.__getattribute__(self, "_inner")
        return inner.get_features(instruments, fields, start_time, end_time, *args, **kwargs)


class StrategyExchangeView:
    """Exchange view for the pre-open phase. Forwards PUBLIC tradability methods
    (``is_suspended`` / ``is_limit_up`` / ``can_buy`` / ``get_lot_size`` / ...) but
    refuses the raw ``_feeder`` / ``_inner`` / direct data-fetch side channels."""

    __slots__ = ("_inner",)
    _BLOCKED = frozenset({"get_features", "preload", "preload_features"})

    def __init__(self, inner):
        object.__setattr__(self, "_inner", inner)

    def __getattribute__(self, name):
        if name == "__dict__" or (name.startswith("_") and not name.startswith("__")):
            raise PreOpenLookaheadError(f"pre_open: exchange access {name!r} is not allowed")
        if name in type(self)._BLOCKED:
            raise PreOpenLookaheadError(f"pre_open: exchange access {name!r} is not allowed")
        try:
            return object.__getattribute__(self, name)
        except AttributeError:
            inner = object.__getattribute__(self, "_inner")
            return getattr(inner, name)
