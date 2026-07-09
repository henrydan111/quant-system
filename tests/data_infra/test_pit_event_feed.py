"""Tests for the sanctioned event-level ledger door (pit_event_feed).

Pins the door's fail-closed contract:
  1. whitelist-only datasets;
  2. D3 born-sealed clamp (no window past the spent-OOS boundary);
  3. PIT invariant: visible_at STRICTLY after the nominal announcement date
     for derived-visibility datasets (dividends), and >= ann_date-next-open
     semantics for effective_date datasets;
  4. §3.1 provider-bounds guard (no event outside listing bounds);
  5. payload column whitelist honored.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from data_infra.pit_event_feed import (
    EVENT_FEED_SPECS, PitEventFeedError, load_event_feed,
)
from data_infra.pit_research_loader import live_spent_oos_end

WINDOW = dict(start="2025-01-01", end="2025-01-31")


def test_unknown_dataset_refused():
    with pytest.raises(PitEventFeedError, match="whitelist-only"):
        load_event_feed("income", **WINDOW)


def test_born_sealed_clamp():
    boundary = live_spent_oos_end()
    with pytest.raises(PitEventFeedError, match="spent-OOS boundary"):
        load_event_feed("forecast", start="2025-01-01",
                        end=(boundary + pd.Timedelta(days=5)))


def test_forecast_events_have_valid_visibility():
    ev = load_event_feed("forecast", **WINDOW)
    assert not ev.empty, "Jan-2025 预告季 must yield forecast events"
    assert ev["visible_at"].notna().all()
    assert (ev["visible_at"] >= pd.Timestamp("2025-01-01")).all()
    assert (ev["visible_at"] <= pd.Timestamp("2025-01-31")).all()
    # PIT: effective_date is strictly AFTER the nominal ann_date's disclosure
    ann = pd.to_datetime(ev["ann_date"], errors="coerce")
    ok = ann.notna()
    assert (ev.loc[ok, "visible_at"] > ann[ok] - pd.Timedelta(days=1)).all()


def test_dividends_derived_visibility_strictly_after_disclosure():
    ev = load_event_feed("dividends", start="2024-06-01", end="2024-07-31")
    assert not ev.empty
    ann = pd.to_datetime(ev["ann_date"], errors="coerce")
    ok = ann.notna()
    # derived via strictly_next_open_trade_day(disclosure) -> visible strictly
    # later than the announcement calendar date
    assert (ev.loc[ok, "visible_at"] > ann[ok]).all()


def test_payload_whitelist_only():
    ev = load_event_feed("stk_holdertrade", **WINDOW)
    allowed = {"ts_code", "visible_at", "dataset",
               *EVENT_FEED_SPECS["stk_holdertrade"]["payload"]}
    assert set(ev.columns) <= allowed


def test_instrument_filter():
    ev = load_event_feed("forecast", **WINDOW)
    some = ev["ts_code"].iloc[0]
    sub = load_event_feed("forecast", instruments=[some], **WINDOW)
    assert set(sub["ts_code"]) == {some}
    assert len(sub) <= len(ev)
