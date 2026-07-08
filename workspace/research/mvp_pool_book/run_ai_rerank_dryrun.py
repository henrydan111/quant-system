# SCRIPT_STATUS: ACTIVE — MVP block-3 END-TO-END DRY RUN (pipeline validation, NOT a decision)
"""AI re-rank chain dry run: July pool + July text + frozen-provider quant scores.

Chain: 202607 pool -> quant composite (LAST provider day, frozen 2026-02-27 —
STALE, explicitly a pipeline-validation stand-in; real forward needs 5-C
unfreeze publishing) -> per-name dossier (text_store, 30d lookback) ->
quick(lite) digest -> deep(pro) dimension scores -> scorecard validation +
deterministic final -> tilt = tilt_cap*(final-50)/50 -> apply_rank_overlay
(K=25, max_swap=8, floor=50, industry cap 9, no vetoes v1) -> AI book vs quant book.

Config = config/ai_layer/rerank_v1.yaml (pre-registered; config_hash logged).
Artifacts -> workspace/outputs/mvp_rerank_dryrun/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from data_infra.golden_stock_universe import load_golden_stock_events  # noqa: E402
from data_infra.text_store import load_text  # noqa: E402
from ai_layer.ark_client import ArkClientError, chat, parse_json_reply  # noqa: E402
from ai_layer.scorecard import (  # noqa: E402
    ScorecardViolation, compute_scorecard_final, validate_scorecard_record,
)
from portfolio_risk.rank_book_construction import apply_rank_overlay  # noqa: E402
from alpha_research.factor_library.catalog import get_factor_catalog  # noqa: E402

OUT_DIR = PROJECT_ROOT / "workspace" / "outputs" / "mvp_rerank_dryrun"
CONFIG_PATH = PROJECT_ROOT / "config" / "ai_layer" / "rerank_v1.yaml"
REGISTRY = PROJECT_ROOT / "data" / "factor_registry" / "factor_master.parquet"
POOL_MONTH = "202607"

FACTORS7 = [
    "liq_zero_ret_days_10d", "rev_turnover_spike_5d", "qual_piotroski_fscore_9pt",
    "earn_sue_ni_assets", "grow_total_revenue_yoy_accel_q",
    "grow_n_income_attr_p_yoy_accel_q", "grow_operate_profit_yoy_accel_q",
]


def load_config() -> tuple[dict, str]:
    cfg_text = CONFIG_PATH.read_text(encoding="utf-8")
    cfg = yaml.safe_load(cfg_text)
    p_ext = (PROJECT_ROOT / cfg["prompts"]["extract"]).read_text(encoding="utf-8")
    p_sco = (PROJECT_ROOT / cfg["prompts"]["score"]).read_text(encoding="utf-8")
    cfg["_prompt_extract"], cfg["_prompt_score"] = p_ext, p_sco
    h = hashlib.sha256((cfg_text + p_ext + p_sco).encode("utf-8")).hexdigest()[:16]
    return cfg, h


def provider_calendar_end() -> str:
    day_txt = PROJECT_ROOT / "data" / "qlib_data" / "calendars" / "day.txt"
    return day_txt.read_text().strip().splitlines()[-1].strip()


def quant_composite_for_pool(pool_codes: list[str]) -> pd.Series:
    """Oriented 7-factor composite at the LAST PUBLISHED provider day (dynamic)."""
    reg = pd.read_parquet(REGISTRY)
    id_col = "factor_id" if "factor_id" in reg.columns else "name"
    cur = reg.sort_values(id_col).drop_duplicates(subset=[id_col], keep="last")
    dirs = {}
    for f in FACTORS7:
        d = str(cur.loc[cur[id_col] == f, "expected_direction"].iloc[0]).lower()
        dirs[f] = -1 if ("inverse" in d or "neg" in d) else 1

    end = provider_calendar_end()
    print(f"[quant] provider calendar end = {end} (dynamic, thaw-aware)", flush=True)
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(PROJECT_ROOT / "data" / "qlib_data"), region=REG_CN, kernels=1)
    avail = {i.upper(): i for i in D.list_instruments(
        D.instruments("all"), start_time="2025-06-01", end_time=end, as_list=True)}
    qcodes = {c: avail[c.replace(".", "_").upper()] for c in pool_codes
              if c.replace(".", "_").upper() in avail}
    cat = get_factor_catalog(include_new_data=True)
    df = D.features(list(qcodes.values()), [cat[f] for f in FACTORS7],
                    start_time="2025-06-01", end_time=end, freq="day")
    df.columns = FACTORS7
    last = df.groupby(level=0).tail(1).droplevel(1)          # last row per instrument
    last.index = [i.upper() for i in last.index]
    back = {v.upper(): k for k, v in qcodes.items()}         # qlib -> ts_code
    comp = pd.Series(0.0, index=[back[i] for i in last.index])
    for f in FACTORS7:
        r = last[f].rank(pct=True)
        if dirs[f] < 0:
            r = 1.0 - r
        comp = comp.add(pd.Series(r.values, index=comp.index).fillna(0.5), fill_value=0.0)
    return comp / len(FACTORS7)


def build_dossier(ts_code: str, texts: dict[str, pd.DataFrame], cfg: dict) -> str:
    items: list[tuple[pd.Timestamp, str]] = []
    for source, df in texts.items():
        sub = df[df["ts_code"] == ts_code]
        for _, r in sub.iterrows():
            t = r["decision_visible_at"]
            if source == "anns_d":
                items.append((t, f"[公告 {str(r.get('ann_date',''))[:8]}] {r.get('title','')}"))
            elif source.startswith("irm_qa"):
                q = str(r.get("q", ""))[:120]
                a = str(r.get("a", ""))[:200]
                items.append((t, f"[互动易] 问:{q} 答:{a}"))
            elif source == "research_report":
                items.append((t, f"[研报 {r.get('inst_csname','')}] {r.get('title','')} "
                                 f"{str(r.get('abstr',''))[:200]}"))
    items.sort(key=lambda x: x[0], reverse=True)
    return "\n".join(s for _, s in items[: cfg["dossier"]["max_items"]])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--names", type=int, default=0, help="limit floor names (0 = full floor)")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cfg, cfg_hash = load_config()
    print(f"[config] {cfg['version']} hash={cfg_hash} models={cfg['models']}", flush=True)

    events = load_golden_stock_events()
    pool = sorted(set(events.loc[events["month"] == POOL_MONTH, "ts_code"]))
    print(f"[pool] {POOL_MONTH}: {len(pool)} names", flush=True)

    comp = quant_composite_for_pool(pool)
    print(f"[quant] composite for {len(comp)} in-provider names "
          f"(STALE frozen-provider scores — pipeline validation only)", flush=True)

    now = pd.Timestamp.now()
    cutoff = now - pd.Timedelta(days=cfg["dossier"]["lookback_days"])
    texts = {}
    for s in cfg["dossier"]["sources"]:
        df = load_text(s, now)
        texts[s] = df[df["decision_visible_at"] >= cutoff] if not df.empty else df
    print(f"[text] rows in lookback: { {s: len(d) for s, d in texts.items()} }", flush=True)

    floor_n = cfg["book"]["promotion_floor"]
    floor_names = comp.sort_values(ascending=False).head(floor_n).index.tolist()
    if args.names:
        floor_names = floor_names[: args.names]

    industry_of = {}
    sb = pd.read_parquet(PROJECT_ROOT / "data" / "reference" / "stock_basic.parquet",
                         columns=["ts_code", "industry"])
    industry_of = {t: (i if isinstance(i, str) and i else None)
                   for t, i in zip(sb["ts_code"], sb["industry"])}

    weights = cfg["weights"]
    tilt_cap = float(cfg["tilt"]["tilt_cap"])
    records, tilts = [], {}
    t_start = time.time()
    for n, code in enumerate(floor_names, 1):
        dossier = build_dossier(code, texts, cfg)
        row = {"ts_code": code, "quant_score": float(comp[code]), "n_chars": len(dossier)}
        if not dossier.strip():
            row.update({"status": "no_text", "final": None})
            records.append(row); tilts[code] = 0.0
            continue
        try:
            r1 = chat([{"role": "user",
                        "content": cfg["_prompt_extract"].replace("{DOSSIER}", dossier)}],
                      model=cfg["models"]["quick"], thinking=cfg["models"]["thinking"],
                      temperature=cfg["models"]["temperature"], max_tokens=1200)
            digest = parse_json_reply(r1.text)
            spans = dossier[:1200]
            r2 = chat([{"role": "user",
                        "content": cfg["_prompt_score"]
                        .replace("{DIGEST}", json.dumps(digest, ensure_ascii=False))
                        .replace("{SPANS}", spans)}],
                      model=cfg["models"]["deep"], thinking=cfg["models"]["thinking"],
                      temperature=cfg["models"]["temperature"], max_tokens=1500)
            rec = parse_json_reply(r2.text)
            validate_scorecard_record(rec, weights=weights)
            final = compute_scorecard_final(rec, weights=weights)
            tilt = tilt_cap * (final - 50.0) / 50.0
            row.update({"status": "ok", "final": final, "tilt": tilt,
                        "n_events": len(digest.get("events", [])),
                        "usage_quick": r1.usage.get("total_tokens"),
                        "usage_deep": r2.usage.get("total_tokens"),
                        "scorecard": json.dumps(rec, ensure_ascii=False)})
            tilts[code] = tilt
        except (ArkClientError, ScorecardViolation) as e:
            row.update({"status": f"fail:{type(e).__name__}", "final": None,
                        "err": str(e)[:200]})
            tilts[code] = 0.0   # fail-closed: no influence
        records.append(row)
        if n % 10 == 0:
            print(f"[llm] {n}/{len(floor_names)} elapsed={time.time()-t_start:.0f}s", flush=True)

    det = pd.DataFrame(records)
    det.to_parquet(OUT_DIR / "scorecards.parquet", index=False)

    res = apply_rank_overlay(
        comp, pd.Series(tilts), k=cfg["book"]["k"],
        max_swap_count=cfg["book"]["max_swap_count"],
        promotion_floor=cfg["book"]["promotion_floor"],
        industry_of=industry_of, max_per_industry=cfg["book"]["max_per_industry"],
    )
    audit = {"config_version": cfg["version"], "config_hash": cfg_hash,
             "pool_month": POOL_MONTH, "run_type": "PIPELINE_DRY_RUN_NOT_A_DECISION",
             "quant_book": res.quant_book, "ai_book": res.final,
             "swaps_in": res.swaps_in, "swaps_out": res.swaps_out,
             "clamped": res.clamped,
             "n_scored": int((det["status"] == "ok").sum()),
             "n_no_text": int((det["status"] == "no_text").sum()),
             "n_fail": int(det["status"].str.startswith("fail").sum())}
    (OUT_DIR / "overlay_audit.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n[scored] ok={audit['n_scored']} no_text={audit['n_no_text']} fail={audit['n_fail']}", flush=True)
    ok = det[det["status"] == "ok"]
    if not ok.empty:
        print(f"[finals] mean={ok['final'].mean():.1f} min={ok['final'].min():.0f} "
              f"max={ok['final'].max():.0f}", flush=True)
    print(f"[overlay] swaps_in={res.swaps_in} swaps_out={res.swaps_out} clamped={res.clamped}", flush=True)
    print(f"wrote -> {OUT_DIR}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
