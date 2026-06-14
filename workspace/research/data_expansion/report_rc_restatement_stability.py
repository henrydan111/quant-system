"""report_rc restatement-stability for the eps_diffusion BREADTH residual (2026-06-14).

The deployed report_rc anchor (create_time / report_date+2) handles LATE ARRIVAL. The one residual
neither create_time (first-ingestion only) nor the JQ oracle (consensus-level) covers is RESTATEMENT:
a report's payload (eps/tp/rating/...) changed AFTER first ingestion, which the provider's
best-known-state re-dates to neither create_time nor the +2 buffer → a small retroactive change to
breadth. Breadth = net % of analysts RAISING FY1 EPS, so only **eps** restatements above the
revision epsilon (EPS_REVISION_EPSILON=1e-4) are breadth-relevant; tp/rating/np/etc. changes are not.

This measures, from the two canary snapshots already on disk (SNAP1 06-07 vs SNAP2 06-14), the
observed 1-week restatement: which payload fields change on a stable report identity (row_id), how
many touch eps materially, and the magnitude — i.e. how contaminated breadth is by restatement.

LIMITATION: one 1-week window on the recent universe. A full restatement-lag distribution needs
periodic snapshots over time; this is a spot estimate / rate prior, not the full distribution.

Run: venv/Scripts/python.exe workspace/research/data_expansion/report_rc_restatement_stability.py
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
S = ROOT / "data" / "external" / "report_rc_canary"
SNAP1 = S / "snapshot_20260607T164452Z.parquet"
SNAP2 = S / "snapshot_20260614T150700Z.parquet"
EPS_REVISION_EPSILON = 1e-4    # matches pit_backend
PAYLOAD = ["op_rt", "op_pr", "tp", "np", "eps", "pe", "rd", "roe", "ev_ebitda",
           "rating", "max_price", "min_price"]


def main() -> int:
    old = pd.read_parquet(SNAP1)
    new = pd.read_parquet(SNAP2)
    # rows present in BOTH (same report identity row_id) — restatement candidates
    j = old.merge(new, on="row_id", suffixes=("_o", "_n"))
    n_both = len(j)
    restated = j[j["payload_hash_o"] != j["payload_hash_n"]]
    print(f"rows in BOTH snapshots: {n_both}   payload-restated: {len(restated)} "
          f"({len(restated)/n_both*100:.3f}% over 1 week)")

    # which payload fields changed, on the restated rows
    print("\n=== which payload field changed (restated rows) ===")
    field_changes = {}
    for c in PAYLOAD:
        co, cn = f"{c}_o", f"{c}_n"
        if co not in restated or cn not in restated:
            continue
        a = pd.to_numeric(restated[co], errors="coerce")
        b = pd.to_numeric(restated[cn], errors="coerce")
        if c == "rating":          # categorical-ish; compare as string
            changed = restated[co].astype(str) != restated[cn].astype(str)
        else:
            changed = ~np.isclose(a, b, rtol=1e-6, atol=1e-9, equal_nan=True)
        field_changes[c] = int(changed.sum())
    for c, n in sorted(field_changes.items(), key=lambda x: -x[1]):
        print(f"   {c:12} changed on {n:3d} / {len(restated)} restated rows")

    # eps specifically — the ONLY breadth-relevant field
    eo = pd.to_numeric(restated["eps_o"], errors="coerce")
    en = pd.to_numeric(restated["eps_n"], errors="coerce")
    eps_delta = (en - eo).abs()
    eps_material = restated[(eps_delta > EPS_REVISION_EPSILON) & eo.notna() & en.notna()]
    print(f"\n=== eps (breadth-relevant) ===")
    print(f"   eps changed > epsilon({EPS_REVISION_EPSILON}): {len(eps_material)} / {len(restated)} restated "
          f"= {len(eps_material)/n_both*100:.4f}% of all in-both rows")
    if len(eps_material):
        rel = ((pd.to_numeric(eps_material['eps_n']) - pd.to_numeric(eps_material['eps_o'])).abs()
               / pd.to_numeric(eps_material['eps_o']).abs().clip(lower=1e-6))
        print(f"   eps-restatement relative magnitude: p50={rel.median():.1%} p90={rel.quantile(.9):.1%} max={rel.max():.1%}")
        print(eps_material[["ts_code_o", "report_date_o", "org_name_o", "quarter_o", "eps_o", "eps_n"]]
              .head(12).to_string(index=False))

    print("\nVerdict reading: if eps-material restatements are ~0 / tiny vs the in-both base, breadth is "
          "restatement-stable and the residual is negligible (the tp/rating/np churn does not touch "
          "eps_diffusion). A non-trivial eps-restatement rate => breadth carries a real retroactive-"
          "revision residual and needs an as-of (vintage) eps for deployment.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
