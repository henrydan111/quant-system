# ──────────────────────────────────────────────────────────────────────
# script_status: research_tooling
# formal_research_allowed: false
# deployment_target: unified_eval_verification_probe
# requires_provider_manifest: false
# requires_preload_strict: false
# pr2_audit_class: C
# notes: |
#   One-off verification probe for the unified factor-evaluation standard (superseded by
#   unified_eval_driver.py / unified_eval_driver_data.py for production evidence). IS-only,
#   zero OOS spend, read-only w.r.t. all registries.
# ──────────────────────────────────────────────────────────────────────
"""Minimal verification of a UNIFIED IS-only evaluation standard across factor statuses.

Computes the leak-proof walk-forward IS panel (heldout RankICIR + sign-consistency,
factor_origin='a_priori', is_end=2020-12-31) for a representative 7-factor set spanning
approved / candidate / draft, and prints them alongside the currently-STORED evidence
(screening grade / rank_icir_5d vs lifecycle is_rank_icir) so we can confirm the metric
口径 is consistent before any full-catalog recompute. Read-only; no registry writes.
"""
from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_research.factor_library.catalog import get_factor_catalog
from src.alpha_research.factor_lifecycle.walk_forward_validation import (
    load_is_windowed_panel,
    run_is_walk_forward,
)
from src.alpha_research.walk_forward import TimeSplit

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("unified_is_probe")

TIME_SPLIT = TimeSplit("2014-01-01", "2020-12-31", "2021-01-01", "2022-01-01")
HORIZON = 20
QLIB_DIR = PROJECT_ROOT / "data" / "qlib_data"
OUT = PROJECT_ROOT / "workspace" / "outputs" / "unified_is_panel_probe.json"

PICKS = {
    "earn_eps_diffusion_60": "approved",
    "liq_zero_ret_days_10d": "approved",
    "qual_piotroski_fscore_9pt": "approved",
    "liq_vol_cv_20d": "candidate",
    "qual_gross_profitability": "candidate",
    "rev_up_down_ratio_20d": "candidate",
    "qual_q_gross_margin": "draft",
}


def _stored_evidence() -> dict:
    ev = pd.read_parquet(PROJECT_ROOT / "data" / "factor_registry" / "factor_evidence.parquet")
    ev = ev.sort_values("evidence_time")
    out: dict[str, dict] = {}
    for fid in PICKS:
        sub = ev[ev["factor_id"] == fid]
        rec: dict = {}
        # latest screening grade / 5d rank_icir (the current dashboard column)
        scr = sub[sub["grade"].notna() & (sub["grade"].astype(str).str.strip() != "")]
        if len(scr):
            last = scr.iloc[-1]
            rec["screening_grade"] = str(last.get("grade"))
            rec["screening_rank_icir_5d"] = (
                None if pd.isna(last.get("rank_icir_5d")) else float(last.get("rank_icir_5d"))
            )
        # latest lifecycle IS rank icir (if any)
        life = sub[sub["run_type"] == "factor_lifecycle"]
        if len(life):
            last = life.iloc[-1]
            for k in ("is_rank_icir", "avg_validation_rank_icir", "sign_consistency"):
                v = last.get(k)
                rec[f"lifecycle_{k}"] = None if pd.isna(v) else float(v)
        out[fid] = rec
    return out


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    full = get_factor_catalog(include_new_data=True)
    cat = {n: full[n] for n in PICKS}

    t0 = time.time()
    log.info("Building IS-only panel for %d factors over [%s, %s] ...",
             len(cat), TIME_SPLIT.is_start, TIME_SPLIT.is_end)
    panel = load_is_windowed_panel(cat, TIME_SPLIT, horizon=HORIZON, qlib_dir=str(QLIB_DIR))
    log.info("Panel built in %.0fs: shape=%s", time.time() - t0, panel.factor_panel.shape)

    result = run_is_walk_forward(
        panel=panel, time_split=TIME_SPLIT, horizon=HORIZON, factor_origin="a_priori"
    )
    rows = {r["factor"]: dict(r) for r in result.rows}
    stored = _stored_evidence()

    report = []
    for fid, status in PICKS.items():
        r = rows.get(fid, {})
        report.append({
            "factor": fid,
            "registry_status": status,
            "unified_heldout_rank_icir": r.get("heldout_rank_icir"),
            "unified_sign_consistency": r.get("sign_consistency"),
            "unified_is_verdict": r.get("status"),
            "unified_n_blocks": r.get("n_heldout_blocks"),
            "stored": stored.get(fid, {}),
        })

    payload = {
        "window": {"is_start": TIME_SPLIT.is_start, "is_end": TIME_SPLIT.is_end},
        "horizon": HORIZON,
        "evidence_kind": result.evidence_kind,
        "protocol": result.protocol,
        "factors": report,
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    log.info("=== UNIFIED IS-ONLY PANEL (a_priori, is_end=%s) ===", TIME_SPLIT.is_end)
    log.info("%-30s %-10s %12s %10s %-9s", "factor", "status", "heldICIR", "signcons", "verdict")
    for row in report:
        log.info("%-30s %-10s %12s %10s %-9s",
                 row["factor"], row["registry_status"],
                 f'{row["unified_heldout_rank_icir"]:.4f}' if row["unified_heldout_rank_icir"] is not None else "NA",
                 f'{row["unified_sign_consistency"]:.2f}' if row["unified_sign_consistency"] is not None else "NA",
                 row["unified_is_verdict"])
    log.info("wrote %s", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
