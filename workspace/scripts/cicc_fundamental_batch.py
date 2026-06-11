# SCRIPT_STATUS: ACTIVE — Phase D batch: CICC fundamental factors × frozen protocol × truth
"""Phase D batch runner: 47 replicated CICC fundamental factors through the frozen
CICC protocol (CALIBRATION_REPORT.md) on univ_all / univ_csi300 / univ_csi500 over
2010.01–2022.07, compared cell-by-cell against the transcribed truth tables.

Truth values are PARSED from Knowledge/AI量化增强/CICC_因子表现真值.md (no hand
copying). Tolerances follow Phase C: fundamental IC ±1.5pp, mono ±0.15 (univ_all)
/ ±0.25 (index domains) + sign agreement, long-ann ±2.5pp (geometric or
arithmetic). Per-tier reporting: 'exact' misses point at construction/data
issues; 'approx' misses are expected to skew larger (cumulative-period caveats).

Usage:
    venv/Scripts/python.exe workspace/scripts/cicc_fundamental_batch.py [--quick]
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from src.alpha_research.factor_library import operators as op  # noqa: E402
from src.alpha_research.factor_eval.cicc_protocol import (  # noqa: E402
    CiccProtocolConfig, evaluate_cicc_protocol, month_end_schedule,
)
from src.alpha_research.factor_eval import universes as uv  # noqa: E402
from src.data_infra import universe_membership as um  # noqa: E402
from workspace.scripts.cicc_factor_defs import CICC_FACTOR_DEFS, exprs  # noqa: E402
from workspace.scripts.cicc_anchor_calibration import (  # noqa: E402
    RAW_FIELDS, WINDOW_START, WINDOW_END, WARMUP_START, UNIVERSES,
    BENCH_BY_UNIVERSE, compute_mmt_range_m, load_benchmark_monthly, _wide,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("cicc_batch")

QLIB_DIR = PROJECT_ROOT / "data" / "qlib_data"
OUT_DIR = PROJECT_ROOT / "workspace" / "outputs" / "cicc_fundamental_batch"
TRUTH_MD = PROJECT_ROOT / "Knowledge" / "AI量化增强" / "CICC_因子表现真值.md"

TOL_IC, TOL_LONG = 1.5, 2.5
TOL_MONO = {"univ_all": 0.15, "univ_csi300": 0.25, "univ_csi500": 0.25}
UNIV_BY_LABEL = {"全市场": "univ_all", "沪深300": "univ_csi300", "中证500": "univ_csi500",
                 "中证1000": "univ_csi1000"}


# --------------------------------------------------------------------------- #
def parse_truth_tables(md_path: Path = TRUTH_MD) -> dict[tuple[str, str], dict]:
    """Parse the transcribed truth markdown into {(code, universe_id): metrics}.

    Handles both layouts: per-universe sections (### 全市场（图表N）) and single
    tables with a 域 column. Column aliases are normalized. Values keep the
    table's units (IC%, returns %, mono absolute).
    """
    text = md_path.read_text(encoding="utf-8")
    out: dict[tuple[str, str], dict] = {}
    current_univ: str | None = None
    header: list[str] | None = None
    col_alias = {"IC均值": "ic", "IC均": "ic", "IC_IR": "ic_ir", "t值": "t", "t": "t",
                 "多头年化": "long_ann", "多头超额": "excess", "超额": "excess",
                 "超额回撤": "mdd", "回撤": "mdd", "换手": "turn", "单调性": "mono",
                 "单调": "mono", "因子": "code", "域": "univ"}

    def _num(s: str):
        s = s.replace("**", "").replace("%", "").strip()
        if s in ("", "—", "-", "–"):
            return None
        try:
            return float(s)
        except ValueError:
            return None

    for line in text.splitlines():
        h = re.match(r"^#{2,3}\s*(?:\d+[a-d]?[.、]?\s*)?.*?(全市场|沪深300|中证500|中证1000)", line)
        if line.startswith("#"):
            current_univ = UNIV_BY_LABEL.get(h.group(1)) if h else None
            header = None
            continue
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if all(set(c) <= {"-", ":", " "} for c in cells):
            continue
        first = cells[0].replace("**", "")
        if first in ("因子", "代码") or first.startswith("IC"):
            header = [col_alias.get(c.replace("**", ""), c) for c in cells]
            continue
        if header is None:
            continue
        row = dict(zip(header, cells))
        code = row.get("code", "").replace("**", "").strip()
        if not code:
            continue
        univ = UNIV_BY_LABEL.get(row.get("univ", "").replace("**", "").strip(), current_univ)
        if univ is None:
            continue
        metrics = {k: _num(v) for k, v in row.items() if k in
                   ("ic", "ic_ir", "t", "long_ann", "excess", "mdd", "turn", "mono")}
        if metrics.get("ic") is None:
            continue
        out[(code, univ)] = metrics
    return out


# --------------------------------------------------------------------------- #
def load_batch_panels(start: str, end: str) -> dict[str, pd.DataFrame]:
    catalog = {**exprs(), **RAW_FIELDS}
    # $st_borr_q0 / $bps etc. flow in via expressions; raw fields for masks/prices
    cache = OUT_DIR / f"panel_cache_batch_{start}_{end}.parquet"
    if cache.exists():
        log.info("loading cached panel %s", cache.name)
        panel = pd.read_parquet(cache)
    else:
        t0 = time.time()
        log.info("compute_factors: %d expressions %s..%s", len(catalog), start, end)
        panel, _ = op.compute_factors(catalog=catalog, start_date=start, end_date=end,
                                      horizons=None, qlib_dir=str(QLIB_DIR), kernels=1,
                                      stage="is_only")
        log.info("computed in %.0fs", time.time() - t0)
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        panel[list(catalog)].to_parquet(cache)
    wides = {name: _wide(panel, name) for name in catalog}
    keep = [c for c in wides["close_raw"].columns if not str(c).endswith("_BJ")]
    n_bj = len(wides["close_raw"].columns) - len(keep)
    if n_bj:
        log.info("excluding %d _BJ instruments", n_bj)
        wides = {k: v[keep] for k, v in wides.items()}
    return wides


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="2015-2018 smoke")
    args = ap.parse_args()
    w_start, w_end = ("2015-01-05", "2018-12-28") if args.quick else (WINDOW_START, WINDOW_END)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    truth = parse_truth_tables()
    log.info("parsed %d truth cells", len(truth))

    wides = load_batch_panels(WARMUP_START, w_end)
    dates_all = wides["close_raw"].index
    insts = list(wides["close_raw"].columns)
    close_adj = wides["close_raw"] * wides["adj"]
    schedule = month_end_schedule(dates_all, start=w_start, end=w_end)
    log.info("schedule %d month-ends; %d instruments", len(schedule), len(insts))

    wides["mmt_range_M"] = compute_mmt_range_m(wides["high"], wides["low"], close_adj, schedule)
    wides["DP"] = wides["DP"].fillna(0.0)  # frozen pool semantics

    eval_dates = dates_all[(dates_all >= schedule.min()) & (dates_all <= schedule.max())]
    panel_for_masks = {k: wides[k] for k in ("vol", "high", "low", "up_limit", "down_limit")}
    panel_for_masks["close"] = wides["close_raw"]
    listing = um.listing_status_masks(eval_dates, insts)
    reference = {"st": um.st_mask(eval_dates, insts),
                 "young": listing["young"], "listed": listing["listed"]}
    masks = {uid: uv.build_universe_mask(uid, eval_dates, insts, panel_for_masks,
                                         reference=reference) for uid in UNIVERSES}
    for uid in UNIVERSES:
        log.info("%s mid-window count: %d", uid, masks[uid].loc[schedule[len(schedule)//2]].sum())

    bench = load_benchmark_monthly(schedule)
    factor_ids = list(CICC_FACTOR_DEFS) + ["mmt_range_M"]
    rows = []
    for uid in UNIVERSES:
        bench_m = bench.get(BENCH_BY_UNIVERSE[uid]) if BENCH_BY_UNIVERSE[uid] else None
        tol_mono = TOL_MONO[uid]
        for fid in factor_ids:
            fdef = CICC_FACTOR_DEFS.get(fid)
            wide_f = wides.get(fid)
            if wide_f is None:
                continue
            try:
                res = evaluate_cicc_protocol(wide_f, close_adj, masks[uid], schedule=schedule,
                                             benchmark_monthly=bench_m,
                                             config=CiccProtocolConfig())
            except ValueError as e:
                log.warning("%s × %s: %s", fid, uid, e)
                continue
            row = {"factor": fid, "universe": uid,
                   "tier": fdef.tier if fdef else "exact",
                   "category": fdef.category if fdef else "价量",
                   **res.to_row(), "group_ann": res.group_ann,
                   "group_mean_count": res.group_mean_count}
            t = truth.get((fid, uid))
            if t and not args.quick:
                # pv-handbook mono is direction-oriented (frozen convention)
                mono_cmp = res.monotonicity * res.direction if fid.startswith("mmt") \
                    else res.monotonicity
                d_ic = res.ic_mean * 100 - t["ic"]
                d_mono = (mono_cmp - t["mono"]) if t.get("mono") is not None else None
                d_long = (res.long_ann * 100 - t["long_ann"]) if t.get("long_ann") is not None else None
                d_long_a = (res.long_ann_arith * 100 - t["long_ann"]) if t.get("long_ann") is not None else None
                ok_ic = abs(d_ic) <= TOL_IC
                ok_mono = d_mono is not None and abs(d_mono) <= tol_mono and \
                    (mono_cmp * t["mono"] > 0 if t["mono"] else True)
                ok_long = (d_long is not None and abs(d_long) <= TOL_LONG) or \
                          (d_long_a is not None and abs(d_long_a) <= TOL_LONG)
                row.update({"truth": t, "d_ic_pp": round(d_ic, 2),
                            "d_mono": None if d_mono is None else round(d_mono, 2),
                            "d_long_pp": None if d_long is None else round(d_long, 2),
                            "d_long_arith_pp": None if d_long_a is None else round(d_long_a, 2),
                            "ok_ic": ok_ic, "ok_mono": ok_mono, "ok_long": ok_long,
                            "PASS": ok_ic and ok_mono and ok_long})
            rows.append(row)
            log.info("%s × %s [%s]: IC %.2f%% (truth %s) mono %.2f long %.1f%%%s",
                     fid, uid, row["tier"], res.ic_mean * 100,
                     t["ic"] if t else "—", res.monotonicity, res.long_ann * 100,
                     "" if not t or args.quick else f"  PASS={row.get('PASS')}")

    out_file = OUT_DIR / ("batch_quick.json" if args.quick else "batch_verdicts.json")
    out_file.write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str),
                        encoding="utf-8")
    log.info("wrote %s", out_file)

    if not args.quick:
        scored = [r for r in rows if "PASS" in r]
        by_tier = {}
        for r in scored:
            k = r["tier"]
            by_tier.setdefault(k, [0, 0])
            by_tier[k][1] += 1
            by_tier[k][0] += bool(r["PASS"])
        log.info("=== BATCH VERDICT: %d/%d cells PASS; by tier: %s ===",
                 sum(1 for r in scored if r["PASS"]), len(scored),
                 {k: f"{a}/{b}" for k, (a, b) in by_tier.items()})
        for r in scored:
            if not r["PASS"]:
                log.info("  FAIL %s×%s [%s]: dIC %s dMono %s dLong %s/%s",
                         r["factor"], r["universe"], r["tier"], r["d_ic_pp"],
                         r["d_mono"], r["d_long_pp"], r["d_long_arith_pp"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
