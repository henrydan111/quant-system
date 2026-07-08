# SCRIPT_STATUS: ACTIVE — MVP forward paper-live cycle runner (B4, impl-review #1)
"""One pre-registered forward decision cycle: 金股 pool -> quant top-K -> AI overlay.

THE decision-producing entry point for FORWARD_PREREG.md (mvp_pool_rerank_v2).
First true cycle: 202608 (activation 2026-08-04). Everything here is
fail-closed and append-only:

  - decision_id = sha256(cycle|decision_time|config_hash|git_commit)[:16]
  - cycles/<cycle>/ is APPEND-ONLY: an existing dir REFUSES the run (no
    overwrite, no silent re-decision); outputs are staged in a tmp dir and
    published by ONE atomic os.replace rename
  - gates BEFORE any LLM call: provider manifest present; provider calendar
    staleness <= 5 trading days vs the fill date (FORWARD_PREREG freshness
    rule); latest text pull manifest ok==True and fresh (<48h); config hash ==
    the prereg-pinned EXPECTED_CONFIG_HASH; decision strictly BEFORE the fill
    day's open (C5: no backfilled "decisions")
  - manifest.json records ALL input hashes (provider build, config+prompts,
    pool parquet, per-source text stores, pull manifest, git commit)
  - M5: decision.json carries the fill plan (next-open EW) + a decision-time
    tradability snapshot; `--record-fills` later appends fill_record.json
    (append-only) with observed open-fill tradability once the provider covers
    the fill date.

Usage:
  venv/Scripts/python.exe workspace/research/mvp_pool_book/run_forward_cycle.py --cycle 202608
  venv/Scripts/python.exe ... --cycle 202608 --record-fills   # after the monthly 5-B bump
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

FORWARD_ROOT = PROJECT_ROOT / "workspace" / "outputs" / "mvp_forward"
CYCLES_ROOT = FORWARD_ROOT / "cycles"
PULL_MANIFEST_LATEST = PROJECT_ROOT / "logs" / "text_pull" / "pull_manifest_latest.json"
POOL_DIR = PROJECT_ROOT / "data" / "analyst" / "broker_recommend"
TRADE_CAL = PROJECT_ROOT / "data" / "reference" / "trade_cal.parquet"
PROVIDER_MANIFEST = PROJECT_ROOT / "data" / "qlib_data" / "metadata" / "provider_build.json"

#: prereg-pinned config identity (FORWARD_PREREG.md mvp_pool_rerank_v2).
#: Recomputed at run time from config/ai_layer/rerank_v2.yaml + the v2 prompts;
#: mismatch = REFUSE (someone edited a frozen artifact).
EXPECTED_CONFIG_HASH = "PINNED_IN_PREREG"   # overwritten below by _load_pinned_hash()

MAX_CALENDAR_STALENESS_TRADING_DAYS = 5     # FORWARD_PREREG freshness rule
MAX_PULL_AGE_HOURS = 48.0


class ForwardGateError(Exception):
    """A fail-closed forward gate refused the cycle."""


# ---------------------------------------------------------------- pure gates

def compute_decision_id(cycle: str, decision_time: str, config_hash: str,
                        git_commit: str) -> str:
    payload = f"{cycle}|{decision_time}|{config_hash}|{git_commit}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def ensure_cycle_dir_free(cycles_root: Path, cycle: str) -> Path:
    """Append-only: an existing cycle dir is a completed decision — REFUSE."""
    final_dir = cycles_root / cycle
    if final_dir.exists():
        raise ForwardGateError(
            f"cycle dir {final_dir} already exists — forward decisions are "
            f"append-only; a re-decision needs a NEW cycle id, never an overwrite")
    return final_dir


def atomic_publish(tmp_dir: Path, final_dir: Path) -> None:
    """Publish the staged cycle by one atomic rename (same volume)."""
    if final_dir.exists():
        raise ForwardGateError(f"{final_dir} appeared during staging — refusing")
    os.replace(tmp_dir, final_dir)


def check_calendar_freshness(calendar_end: str, fill_date: str,
                             trade_cal: pd.DataFrame,
                             max_staleness: int = MAX_CALENDAR_STALENESS_TRADING_DAYS) -> int:
    """Staleness = OPEN trading days in (calendar_end, fill_date). > max -> refuse."""
    cal = trade_cal.loc[trade_cal["is_open"] == 1, "cal_date"].astype(str)
    stale = cal[(cal > str(calendar_end).replace("-", "")[:8])
                & (cal < str(fill_date).replace("-", "")[:8])]
    staleness = int(len(stale))
    if staleness > max_staleness:
        raise ForwardGateError(
            f"provider calendar end {calendar_end} is {staleness} trading days "
            f"stale vs fill date {fill_date} (max {max_staleness}) — run the "
            f"monthly 5-B calendar bump before deciding")
    return staleness


def check_pull_manifest(manifest: dict, decision_time: pd.Timestamp,
                        max_age_hours: float = MAX_PULL_AGE_HOURS) -> None:
    """The latest daily text pull must be CLEAN and FRESH (B5 evidence)."""
    if not manifest.get("ok", False):
        raise ForwardGateError(
            f"latest text pull manifest reports failures: {manifest.get('failures')} "
            f"— text inputs incomplete, refusing the cycle")
    run_ts = pd.Timestamp(manifest["run_ts"])
    age_h = (decision_time - run_ts).total_seconds() / 3600.0
    if age_h > max_age_hours or age_h < 0:
        raise ForwardGateError(
            f"latest text pull is {age_h:.1f}h old (max {max_age_hours}h) — "
            f"run text_daily_pull before deciding")


def check_config_hash(actual: str, expected: str) -> None:
    if actual != expected:
        raise ForwardGateError(
            f"config hash {actual} != prereg-pinned {expected} — a frozen "
            f"artifact changed; amend FORWARD_PREREG (new version) instead")


def check_decision_before_fill_open(decision_time: pd.Timestamp,
                                    fill_date: pd.Timestamp) -> None:
    """C5: the decision must exist BEFORE the fill day's open (09:25 auction)."""
    open_cutoff = fill_date.normalize() + pd.Timedelta(hours=9, minutes=25)
    if decision_time >= open_cutoff:
        raise ForwardGateError(
            f"decision_time {decision_time} is not strictly before the "
            f"{fill_date.date()} 09:25 open — a post-open 'decision' is a "
            f"backfill (C5), refused")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(*, cycle: str, decision_time: pd.Timestamp, config_hash: str,
                   git_commit: str, provider_manifest: dict, calendar_end: str,
                   staleness_days: int, pool_path: Path,
                   text_store_paths: dict[str, Path],
                   pull_manifest: dict) -> dict:
    """Every input the decision depended on, by content hash (B4)."""
    decision_id = compute_decision_id(cycle, decision_time.isoformat(),
                                      config_hash, git_commit)
    return {
        "decision_id": decision_id,
        "cycle": cycle,
        "decision_time": decision_time.isoformat(),
        "git_commit": git_commit,
        "config_hash": config_hash,
        "provider_build_id": provider_manifest.get("provider_build_id"),
        "calendar_policy_id": provider_manifest.get("calendar_policy_id"),
        "provider_calendar_end": calendar_end,
        "calendar_staleness_trading_days": staleness_days,
        "input_hashes": {
            "pool_parquet": {"path": str(pool_path), "sha256": sha256_file(pool_path)},
            "text_stores": {s: {"path": str(p), "sha256": sha256_file(p)}
                            for s, p in text_store_paths.items() if p.exists()},
        },
        "text_pull_manifest": pull_manifest,
        "prereg": "workspace/research/mvp_pool_book/FORWARD_PREREG.md",
        "strategy_version": "mvp_pool_rerank_v2",
    }


# ------------------------------------------------------------- orchestration

def _load_dryrun_module():
    """Reuse the validated chain pieces (config/composite/dossier builders)."""
    spec = importlib.util.spec_from_file_location(
        "mvp_rerank_chain", Path(__file__).parent / "run_ai_rerank_dryrun.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git_commit() -> str:
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT,
                         capture_output=True, text=True, check=True)
    return out.stdout.strip()


def _load_pinned_hash() -> str:
    """The prereg pins the hash inside FORWARD_PREREG.md as `config_hash_v2: <h>`."""
    prereg = Path(__file__).parent / "FORWARD_PREREG.md"
    for line in prereg.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("config_hash_v2:"):
            return line.split(":", 1)[1].strip().strip("`")
    raise ForwardGateError("FORWARD_PREREG.md lacks a pinned config_hash_v2 line")


def run_decision(cycle: str) -> int:
    chain = _load_dryrun_module()
    from data_infra.golden_stock_universe import load_golden_stock_events
    from data_infra.text_store import DEFAULT_STORE_DIR
    from portfolio_risk.rank_book_construction import apply_rank_overlay
    from ai_layer.ark_client import ArkClientError, chat, parse_json_reply
    from ai_layer.prompt_render import render_extract_messages, render_score_messages
    from ai_layer.scorecard import (ScorecardViolation, compute_scorecard_final,
                                    validate_scorecard_record)

    decision_time = pd.Timestamp.now()
    cfg, cfg_hash = chain.load_config()
    check_config_hash(cfg_hash, _load_pinned_hash())

    events = load_golden_stock_events()
    cyc = events.loc[events["month"] == cycle]
    if cyc.empty:
        raise ForwardGateError(f"no pool rows for cycle {cycle} — pull the month first")
    fill_date = pd.Timestamp(cyc["activation_date"].iloc[0])
    check_decision_before_fill_open(decision_time, fill_date)

    if not PROVIDER_MANIFEST.exists():
        raise ForwardGateError("provider_build.json missing — no attested provider")
    provider_manifest = json.loads(PROVIDER_MANIFEST.read_text(encoding="utf-8"))
    calendar_end = chain.provider_calendar_end()
    staleness = check_calendar_freshness(calendar_end, fill_date.strftime("%Y%m%d"),
                                         pd.read_parquet(TRADE_CAL))
    if not PULL_MANIFEST_LATEST.exists():
        raise ForwardGateError("no text pull manifest — text_daily_pull has never run")
    pull_manifest = json.loads(PULL_MANIFEST_LATEST.read_text(encoding="utf-8"))
    check_pull_manifest(pull_manifest, decision_time)

    final_dir = ensure_cycle_dir_free(CYCLES_ROOT, cycle)
    CYCLES_ROOT.mkdir(parents=True, exist_ok=True)

    pool = sorted(set(cyc["ts_code"]))
    print(f"[gates] ALL PASS — cycle={cycle} fill={fill_date.date()} "
          f"staleness={staleness}d pool={len(pool)}", flush=True)

    comp = chain.quant_composite_for_pool(pool)
    cutoff = decision_time - pd.Timedelta(days=cfg["dossier"]["lookback_days"])
    from data_infra.text_store import load_text
    texts = {}
    for s in cfg["dossier"]["sources"]:
        df = load_text(s, decision_time)
        texts[s] = df[df["decision_visible_at"] >= cutoff] if not df.empty else df

    floor_names = comp.sort_values(ascending=False).head(
        cfg["book"]["promotion_floor"]).index.tolist()
    sb = pd.read_parquet(PROJECT_ROOT / "data" / "reference" / "stock_basic.parquet",
                         columns=["ts_code", "industry"])
    industry_of = {t: (i if isinstance(i, str) and i else None)
                   for t, i in zip(sb["ts_code"], sb["industry"])}

    weights, tilt_cap = cfg["weights"], float(cfg["tilt"]["tilt_cap"])
    records = []
    for n, code in enumerate(floor_names, 1):
        dossier = chain.build_dossier(code, texts, cfg)
        row = {"ts_code": code, "quant_score": float(comp[code]), "n_chars": len(dossier)}
        if not dossier.strip():
            row.update({"status": "no_text", "final": None})
            records.append(row)
            continue
        try:
            r1 = chat(render_extract_messages(cfg["_prompt_extract"], dossier),
                      model=cfg["models"]["quick"], thinking=cfg["models"]["thinking"],
                      temperature=cfg["models"]["temperature"], max_tokens=1200)
            digest = parse_json_reply(r1.text)
            spans = dossier[:1200]
            r2 = chat(render_score_messages(cfg["_prompt_score"], digest, spans),
                      model=cfg["models"]["deep"], thinking=cfg["models"]["thinking"],
                      temperature=cfg["models"]["temperature"], max_tokens=1500)
            rec = parse_json_reply(r2.text)
            evidence_context = json.dumps(digest, ensure_ascii=False) + "\n" + spans
            validate_scorecard_record(rec, weights=weights,
                                      evidence_context=evidence_context)
            final = compute_scorecard_final(rec, weights=weights,
                                            evidence_context=evidence_context)
            row.update({"status": "ok", "final": final, "dossier": dossier,
                        "scorecard": json.dumps(rec, ensure_ascii=False)})
        except (ArkClientError, ScorecardViolation) as e:
            row.update({"status": f"fail:{type(e).__name__}", "final": None,
                        "err": str(e)[:200]})
        records.append(row)
        if n % 10 == 0:
            print(f"[llm] {n}/{len(floor_names)}", flush=True)

    det = pd.DataFrame(records)
    ok_mask = det["status"] == "ok"
    scored_pct = float(ok_mask.sum()) / max(1, len(floor_names))
    overlay_disabled = scored_pct < float(cfg["coverage"]["min_scored_floor_pct"])
    if overlay_disabled:
        det["tilt"] = 0.0
    else:
        scored_mean = float(det.loc[ok_mask, "final"].mean())
        det["tilt"] = det["final"].map(
            lambda f: tilt_cap * (float(f) - scored_mean) / 50.0 if f is not None else 0.0
        ).fillna(0.0)
        det.loc[~ok_mask, "tilt"] = 0.0
    tilts = dict(zip(det["ts_code"], det["tilt"]))

    res = apply_rank_overlay(
        comp, pd.Series(tilts), k=cfg["book"]["k"],
        max_swap_count=cfg["book"]["max_swap_count"],
        promotion_floor=cfg["book"]["promotion_floor"],
        industry_of=industry_of, max_per_industry=cfg["book"]["max_per_industry"])

    # M4 caps (same assertions as the dry run)
    caps, k = cfg["portfolio_caps"], cfg["book"]["k"]
    oneway = len(res.swaps_in) / k
    assert oneway <= caps["max_ai_oneway_turnover"] + 1e-9

    # M5: fill plan + decision-time tradability snapshot (provider last day)
    ew = 1.0 / k
    fill_plan = {"fill_date": fill_date.strftime("%Y-%m-%d"),
                 "fill_price_basis": "next_open_paper",
                 "weights": {c: ew for c in res.final}}

    git_commit = _git_commit()
    manifest = build_manifest(
        cycle=cycle, decision_time=decision_time, config_hash=cfg_hash,
        git_commit=git_commit, provider_manifest=provider_manifest,
        calendar_end=calendar_end, staleness_days=staleness,
        pool_path=POOL_DIR / f"broker_recommend_{cycle}.parquet",
        text_store_paths={s: Path(DEFAULT_STORE_DIR) / s / f"text_{s}.parquet"
                          for s in cfg["dossier"]["sources"]},
        pull_manifest=pull_manifest)

    decision = {
        "decision_id": manifest["decision_id"],
        "cycle": cycle, "decision_time": decision_time.isoformat(),
        "strategy_version": "mvp_pool_rerank_v2",
        "legs": {"quant_book": res.quant_book, "ai_book": res.final,
                 "pool_ew": pool},
        "overlay_audit": {
            "swaps_in": res.swaps_in, "swaps_out": res.swaps_out,
            "clamped": res.clamped, "vetoes": res.vetoes,
            "veto_removed": res.veto_removed,
            "veto_backfill_in": res.veto_backfill_in,
            "tilt_swaps": res.tilt_swaps,
            "industry_cap_skipped_entrants": res.industry_cap_skipped_entrants,
            "coverage_scored_pct": scored_pct,
            "overlay_disabled_for_cycle": overlay_disabled},
        "fill_plan": fill_plan,
    }

    tmp = Path(tempfile.mkdtemp(prefix=f"cycle_{cycle}_", dir=FORWARD_ROOT))
    try:
        det.to_parquet(tmp / "scorecards.parquet", index=False)
        (tmp / "decision.json").write_text(
            json.dumps(decision, indent=2, ensure_ascii=False), encoding="utf-8")
        (tmp / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        atomic_publish(tmp, final_dir)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    print(f"[published] {final_dir} decision_id={manifest['decision_id']} "
          f"overlay_disabled={overlay_disabled}", flush=True)
    return 0


def run_record_fills(cycle: str) -> int:
    """After the monthly 5-B bump covers the fill date: observed tradability (M5)."""
    cyc_dir = CYCLES_ROOT / cycle
    fills_path = cyc_dir / "fill_record.json"
    if not cyc_dir.exists():
        raise ForwardGateError(f"no decision published for cycle {cycle}")
    if fills_path.exists():
        raise ForwardGateError(f"{fills_path} already exists — fill records are append-only")
    decision = json.loads((cyc_dir / "decision.json").read_text(encoding="utf-8"))
    fill_date = decision["fill_plan"]["fill_date"]

    chain = _load_dryrun_module()
    if chain.provider_calendar_end().replace("-", "") < fill_date.replace("-", ""):
        raise ForwardGateError(
            f"provider calendar does not cover fill date {fill_date} yet — "
            f"run the monthly 5-B bump first")

    from data_infra.provider_metadata import tushare_to_qlib_canonical
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(PROJECT_ROOT / "data" / "qlib_data"),
              region=REG_CN, kernels=1)
    codes = sorted(set(decision["legs"]["ai_book"]) | set(decision["legs"]["quant_book"]))
    qmap = {tushare_to_qlib_canonical(c): c for c in codes}
    df = D.features(list(qmap.keys()),
                    ["$open", "$vol", "$up_limit", "$down_limit"],
                    start_time=fill_date, end_time=fill_date, freq="day")
    fills = {}
    for qcode, ts in qmap.items():
        try:
            row = df.xs(qcode, level=0).iloc[0]
        except (KeyError, IndexError):
            fills[ts] = {"status": "no_data"}
            continue
        suspended = pd.isna(row["$open"]) or (row["$vol"] == 0 or pd.isna(row["$vol"]))
        locked_up = (not suspended and pd.notna(row["$up_limit"])
                     and float(row["$open"]) >= float(row["$up_limit"]) - 1e-6)
        fills[ts] = {"status": ("suspended" if suspended
                                else "open_limit_up_unbuyable" if locked_up
                                else "filled_at_open"),
                     "open": None if pd.isna(row["$open"]) else float(row["$open"])}
    record = {"cycle": cycle, "fill_date": fill_date,
              "recorded_at": pd.Timestamp.now().isoformat(),
              "provider_calendar_end": chain.provider_calendar_end(),
              "fills": fills}
    fills_path.write_text(json.dumps(record, indent=2, ensure_ascii=False),
                          encoding="utf-8")
    print(f"[fills] recorded -> {fills_path}", flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycle", required=True, help="pool month, e.g. 202608")
    ap.add_argument("--record-fills", action="store_true")
    args = ap.parse_args()
    FORWARD_ROOT.mkdir(parents=True, exist_ok=True)
    try:
        if args.record_fills:
            return run_record_fills(args.cycle)
        return run_decision(args.cycle)
    except ForwardGateError as e:
        print(f"[REFUSED] {e}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
