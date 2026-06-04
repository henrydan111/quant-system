# ──────────────────────────────────────────────────────────────────────
# Anomaly review — daily-dense quarantine datasets: hk_hold + margin_detail.
# script_status: historical_investigation
# formal_research_allowed: false
# deployment_target: research
# requires_provider_manifest: false
# requires_preload_strict: false
# pr2_audit_class: B
# notes: |
#   Batch review (group 1 of 2) of the gated daily-dense datasets, mirroring the
#   moneyflow review. Read-only. Per dataset: coverage (non-null % by year),
#   value sanity (ranges/signs), and dataset-specific checks —
#     hk_hold: .HK / non-A-share CONTAMINATION in the raw code/exchange columns
#              (data_dictionary 2026-03-30 WARNING) + ratio range [0,100];
#     margin_detail: balances >= 0 + the rzye/rqye fields + a PIT-DISCLOSURE flag
#              (exchange publishes day-T margin balances after close / next AM).
# ──────────────────────────────────────────────────────────────────────
"""hk_hold + margin_detail anomaly review (coverage + sanity + contamination/PIT)."""
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

HK_DIR = ROOT / "data" / "market" / "northbound"
MG_DIR = ROOT / "data" / "market" / "margin"
MG_FIELDS = ["rzye", "rqye", "rzmre", "rzche", "rzrqye", "rqmcl", "rqchl"]  # field_status set


def _load_year(d: Path, prefix: str, year: str) -> pd.DataFrame:
    fs = sorted(glob.glob(str(d / year / f"{prefix}_*.parquet")))
    if not fs:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True)


def _valid_ashare(ts: pd.Series) -> pd.Series:
    s = ts.astype(str).str.upper()
    return s.str.match(r"^\d{6}\.(SZ|SH|BJ)$")


def review_hk_hold() -> dict:
    out = {"dataset": "hk_hold", "approved_field": "$ratio", "start": "2017"}
    cov = {}
    for y in ["2017", "2020", "2024", "2026"]:
        df = _load_year(HK_DIR, "northbound", y)
        if df.empty:
            cov[y] = {"files": 0}; continue
        valid = _valid_ashare(df["ts_code"]) if "ts_code" in df.columns else pd.Series(False, index=df.index)
        contam = int((~valid).sum())
        rat = pd.to_numeric(df.get("ratio"), errors="coerce")
        cov[y] = {
            "rows": len(df),
            "ratio_nonnull_pct": round(float(rat.notna().mean() * 100), 3),
            "ratio_min": round(float(rat.min()), 4), "ratio_max": round(float(rat.max()), 4),
            "contaminated_ts_code_rows": contam,
            "contaminated_pct": round(contam / len(df) * 100, 4),
            "sample_contam_codes": sorted(df.loc[~valid, "ts_code"].astype(str).unique().tolist())[:5] if contam else [],
        }
    out["coverage_and_contamination"] = cov
    out["ratio_units"] = "percent (foreign-holding ratio, expect [0,100])"
    out["pit_note"] = ("Northbound holdings — end-of-day fact, anchored on trade_date, knowable at "
                       "session close T. Predictive factors need Ref(...,1). Provider materializes "
                       "$ratio for VALID A-share ts_codes only (the staged backend filters .HK / "
                       "contaminated rows before Qlib materialization — verify the served data is clean).")
    return out


def review_margin() -> dict:
    out = {"dataset": "margin_detail", "approved_fields": MG_FIELDS, "start": "2010-03-31"}
    cov = {}
    for y in ["2010", "2014", "2018", "2024", "2026"]:
        df = _load_year(MG_DIR, "margin", y)
        if df.empty:
            cov[y] = {"files": 0}; continue
        present = [f for f in MG_FIELDS if f in df.columns]
        nn = {f: round(float(pd.to_numeric(df[f], errors="coerce").notna().mean() * 100), 2) for f in present}
        neg = int(sum(int((pd.to_numeric(df[f], errors="coerce") < 0).sum()) for f in present))
        cov[y] = {"rows": len(df), "fields_present": present,
                  "min_nonnull_pct": round(min(nn.values()), 2) if nn else None,
                  "per_field_nonnull_pct": nn, "negative_value_rows": neg}
    out["coverage"] = cov
    raw_extra = []
    df18 = _load_year(MG_DIR, "margin", "2018")
    if not df18.empty:
        raw_extra = [c for c in df18.columns if c not in (["trade_date", "ts_code"] + MG_FIELDS)]
    out["raw_columns_not_in_field_status"] = raw_extra  # e.g. rqyl (融券余量) present in raw but unregistered
    out["pit_note"] = ("Margin balances (融资余额 rzye / 融券余额 rqye / …) — anchored on trade_date, but the "
                       "exchange PUBLISHES day-T balances AFTER the close (often next morning). So day-T "
                       "margin is NOT safely knowable intraday-T; a predictive factor must use Ref(...,1) "
                       "AT MINIMUM (treat as a T-disclosed-after-close outcome). FLAG for the approval: "
                       "confirm the materialized anchor is trade_date and that Ref(...,1) is the documented contract.")
    return out


def _parity_spotcheck() -> dict:
    res = {}
    try:
        import qlib
        from qlib.data import D
        qlib.init(provider_uri=str(ROOT / "data" / "qlib_data"), region="cn", kernels=1)
        prov = D.features(["000001_sz", "600519_sh"], ["$ratio", "$rzye", "$rqye"],
                          start_time="2024-01-02", end_time="2024-01-10", freq="day")
        res["provider_fields_served"] = {c: int(prov[c].notna().sum()) for c in prov.columns}
        res["note"] = "non-zero served counts confirm $ratio (hk_hold) + $rzye/$rqye (margin) materialized + queryable."
    except Exception as e:
        res["error"] = str(e)[:200]
    return res


def main() -> int:
    out = {"hk_hold": review_hk_hold(), "margin_detail": review_margin(),
           "provider_parity": _parity_spotcheck()}
    (OUT / "daily_dense_review.json").write_text(json.dumps(out, indent=2, default=str))

    print("=== hk_hold ===")
    for y, c in out["hk_hold"]["coverage_and_contamination"].items():
        print(f"  {y}: ratio_nonnull={c.get('ratio_nonnull_pct')}% range=[{c.get('ratio_min')},{c.get('ratio_max')}] "
              f"contam={c.get('contaminated_pct')}% {c.get('sample_contam_codes')}")
    print("\n=== margin_detail ===")
    for y, c in out["margin_detail"]["coverage"].items():
        print(f"  {y}: min_nonnull={c.get('min_nonnull_pct')}% neg_rows={c.get('negative_value_rows')} fields={len(c.get('fields_present',[]))}")
    print(f"  raw cols not in field_status: {out['margin_detail']['raw_columns_not_in_field_status']}")
    print(f"\nprovider parity: {out['provider_parity']}")
    print(f"\n[saved] {OUT / 'daily_dense_review.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
