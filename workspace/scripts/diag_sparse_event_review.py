# ──────────────────────────────────────────────────────────────────────
# Anomaly review — pending_review alpha endpoints (group 2 of 2).
# script_status: historical_investigation
# formal_research_allowed: false
# deployment_target: research
# requires_provider_manifest: false
# requires_preload_strict: false
# pr2_audit_class: B
# notes: |
#   Read-only review of the 5 pending_review alpha endpoints. Unlike the
#   daily-dense datasets, top_list/top_inst/block_trade are SPARSE EVENTS (only
#   event days populated) and stk_holdertrade is a PIT ledger; cyq_perf is in
#   fact daily-dense (per-stock chip distribution). Per dataset: event coverage
#   (event-days/events/distinct stocks by year), numeric-field sanity, the
#   non-numeric columns that are NOT materialized (e.g. `reason`, `buyer`), and
#   the PIT anchor (these post-close events need Ref(...,1); stk_holdertrade
#   already carries disclosure_date/effective_date).
# ──────────────────────────────────────────────────────────────────────
"""Sparse alpha-endpoint anomaly review: top_list, top_inst, block_trade, cyq_perf, stk_holdertrade."""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

OUT = ROOT / "workspace" / "outputs" / "gated_review"
OUT.mkdir(parents=True, exist_ok=True)
MKT = ROOT / "data" / "market"
YEARS = ["2014", "2018", "2021", "2024", "2026"]

# numeric fields that get materialized as $<ds>__<col> (text/id cols are skipped)
NUMERIC = {
    "top_list": ["close", "pct_change", "turnover_rate", "amount", "l_sell", "l_buy", "l_amount", "net_amount", "net_rate", "amount_rate", "float_values"],
    "top_inst": ["buy", "buy_rate", "sell", "sell_rate", "net_buy"],
    "block_trade": ["price", "vol", "amount"],
    "cyq_perf": ["his_low", "his_high", "cost_5pct", "cost_15pct", "cost_50pct", "cost_85pct", "cost_95pct", "weight_avg", "winner_rate"],
}
NON_MATERIALIZED = {"top_list": ["name", "reason"], "top_inst": ["exalter", "side", "reason"],
                    "block_trade": ["buyer", "seller"], "cyq_perf": []}


def _files(ds, year):
    return sorted(glob.glob(str(MKT / ds / year / f"{ds}_*.parquet")))


def review_event(ds) -> dict:
    out = {"dataset": ds, "type": "daily_dense" if ds == "cyq_perf" else "sparse_event",
           "materialized_numeric_fields": [f"${ds}__{c}" for c in NUMERIC[ds]],
           "non_materialized_cols": NON_MATERIALIZED[ds], "by_year": {}}
    for y in YEARS:
        fs = _files(ds, y)
        if not fs:
            out["by_year"][y] = {"event_days": 0}; continue
        df = pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True)
        present = [c for c in NUMERIC[ds] if c in df.columns]
        nn = {c: round(float(pd.to_numeric(df[c], errors="coerce").notna().mean() * 100), 2) for c in present}
        out["by_year"][y] = {
            "event_days": len(fs), "event_rows": len(df),
            "distinct_stocks": int(df["ts_code"].nunique()),
            "min_numeric_nonnull_pct": round(min(nn.values()), 2) if nn else None,
        }
    # value sanity on a recent deep year
    deep = "2024"
    fs = _files(ds, deep)
    sanity = {}
    if fs:
        df = pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True)
        if ds == "cyq_perf":
            # cost percentiles must be ordered; winner_rate a fraction/percent
            ordered = (df[["cost_5pct", "cost_15pct", "cost_50pct", "cost_85pct", "cost_95pct"]]
                       .apply(lambda r: r.is_monotonic_increasing, axis=1))
            sanity = {"cost_pctiles_ordered_pct": round(float(ordered.mean() * 100), 2),
                      "winner_rate_range": [round(float(df["winner_rate"].min()), 3), round(float(df["winner_rate"].max()), 3)]}
        elif ds == "block_trade":
            sanity = {"price_min": round(float(df["price"].min()), 3), "vol_min": round(float(df["vol"].min()), 1),
                      "amount_min": round(float(df["amount"].min()), 2),
                      "neg_amount_rows": int((pd.to_numeric(df["amount"], errors="coerce") < 0).sum())}
        elif ds == "top_list":
            sanity = {"net_amount_range": [round(float(df["net_amount"].min()), 1), round(float(df["net_amount"].max()), 1)],
                      "l_buy_min": round(float(df["l_buy"].min()), 1), "l_sell_min": round(float(df["l_sell"].min()), 1)}
        elif ds == "top_inst":
            sanity = {"net_buy_range": [round(float(df["net_buy"].min()), 1), round(float(df["net_buy"].max()), 1)],
                      "buy_min": round(float(df["buy"].min()), 1), "sell_min": round(float(df["sell"].min()), 1)}
    out["value_sanity_2024"] = sanity
    out["pit_note"] = ("Event published after close of trade_date T (龙虎榜/机构/大宗) or computed for day T "
                       "(cyq_perf) -> knowable at session close T -> predictive factors need Ref(...,1). "
                       "Sparse events also need explicit staleness/decay handling (a factor must define how "
                       "long an event signal persists between events).")
    return out


def review_stk_holdertrade() -> dict:
    p = ROOT / "data" / "pit_ledger" / "stk_holdertrade" / "stk_holdertrade.parquet"
    out = {"dataset": "stk_holdertrade", "type": "pit_ledger_event",
           "materialized_fields": ["$holdertrade_net_vol", "$holdertrade_gross_vol", "$holdertrade_net_ratio", "$holdertrade_events"]}
    if not p.exists():
        out["error"] = "ledger not found"; return out
    df = pd.read_parquet(p)
    out["rows"] = len(df)
    out["has_disclosure_anchor"] = bool({"ann_date", "disclosure_date", "effective_date"} <= set(df.columns))
    out["distinct_stocks"] = int(df["ts_code"].nunique()) if "ts_code" in df.columns else None
    if "effective_date" in df.columns:
        ed = pd.to_datetime(df["effective_date"], errors="coerce")
        out["effective_date_range"] = [str(ed.min().date()), str(ed.max().date())]
    if "in_de" in df.columns:
        out["in_de_values"] = df["in_de"].astype(str).value_counts().to_dict()
    out["pit_note"] = ("Carries ann_date + disclosure_date + effective_date -> PROPERLY PIT-anchored "
                       "(unlike the daily endpoints). The aggregator emits bare $holdertrade_* columns. "
                       "effective_date is the visibility anchor.")
    return out


def main() -> int:
    out = {ds: review_event(ds) for ds in ["top_list", "top_inst", "block_trade", "cyq_perf"]}
    out["stk_holdertrade"] = review_stk_holdertrade()
    (OUT / "sparse_event_review.json").write_text(json.dumps(out, indent=2, default=str))
    for ds in ["top_list", "top_inst", "block_trade", "cyq_perf"]:
        r = out[ds]
        yrs = {y: f"{v.get('event_days','-')}d/{v.get('distinct_stocks','-')}st" for y, v in r["by_year"].items()}
        print(f"{ds} ({r['type']}): {yrs}")
        print(f"   sanity24: {r['value_sanity_2024']}")
    h = out["stk_holdertrade"]
    print(f"stk_holdertrade: rows={h.get('rows')} disclosure_anchor={h.get('has_disclosure_anchor')} "
          f"eff_range={h.get('effective_date_range')} in_de={h.get('in_de_values')}")
    print(f"\n[saved] {OUT / 'sparse_event_review.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
