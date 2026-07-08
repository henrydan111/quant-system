# SCRIPT_STATUS: ACTIVE — MVP forward paper-live cycle runner (B4 R1 + R2 rework)
"""One pre-registered forward decision cycle: 金股 pool -> quant top-K -> AI overlay.

THE decision-producing entry point for FORWARD_PREREG.md (mvp_pool_rerank_v2).
First true cycle: 202608. Evidence-grade rules (GPT impl-review #2):

  - **Asia/Shanghai is the ONLY decision timezone** (Blocker-5): decision_time
    is tz-aware CN; the fill-open cutoff (09:25) is CN wall time; manifests
    carry the +08:00 offset.
  - **Attempt ledger BEFORE any LLM spend** (Blocker-2): after the pure gates
    pass, an immutable ``cycles/<cycle>/attempt_<decision_id>/`` directory is
    created and registered in ``attempts_ledger.jsonl``; every per-name LLM
    request/response/validated-scorecard streams to disk AS IT HAPPENS; a
    failed attempt is marked failed and NEVER deleted; a rerun of the same
    cycle is refused unless ``--new-attempt <reason>`` (counted in the ledger);
    a cycle with a PUBLISHED attempt can never be decided again.
  - **Manifest pins EVERY input by content hash** (Blocker-3): provider build /
    calendars / factor registry+expressions / pool / industry map / quant
    scores / config+prompts+models / per-source text stores + in-window row
    hashes / per-name dossier + raw-LLM + validated-scorecard hashes /
    artifact hashes. ``git_worktree_clean`` is a HARD gate.
  - **Provider as-of upper bound** (Blocker-4): provider calendar end must be
    <= the last open day STRICTLY BEFORE the fill date, and the quant
    composite re-checks it internally.
  - **Required text sources must EXIST** (Blocker-6): a missing store file or
    a pull manifest without ok per-source status refuses the cycle — silent
    no-text is not a thing.
  - **Caps are explicit gates** (Major-4): name weight / AI one-way turnover /
    L1 active / industry weight raise ForwardGateError, never bare assert.
  - ``--record-fills`` appends observed open-fill tradability into the
    PUBLISHED attempt (append-only). NOTE (Major-3, recorded): from cycle #2 a
    full transition fill ledger (sell/buy deltas, limit-down sell failures,
    suspension carry, cash drag) must replace this buy-side-only record.

Usage:
  venv/Scripts/python.exe workspace/research/mvp_pool_book/run_forward_cycle.py --cycle 202608
  ... --cycle 202608 --new-attempt "reason"   # after a FAILED attempt only
  ... --cycle 202608 --record-fills           # after the monthly 5-B bump
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

CN_TZ = "Asia/Shanghai"
FORWARD_ROOT = PROJECT_ROOT / "workspace" / "outputs" / "mvp_forward"
CYCLES_ROOT = FORWARD_ROOT / "cycles"
ATTEMPTS_LEDGER = FORWARD_ROOT / "attempts_ledger.jsonl"
PULL_MANIFEST_LATEST = PROJECT_ROOT / "logs" / "text_pull" / "pull_manifest_latest.json"
POOL_DIR = PROJECT_ROOT / "data" / "analyst" / "broker_recommend"
TRADE_CAL = PROJECT_ROOT / "data" / "reference" / "trade_cal.parquet"
PROVIDER_MANIFEST = PROJECT_ROOT / "data" / "qlib_data" / "metadata" / "provider_build.json"
QLIB_CALENDAR = PROJECT_ROOT / "data" / "qlib_data" / "calendars" / "day.txt"
FACTOR_REGISTRY = PROJECT_ROOT / "data" / "factor_registry" / "factor_master.parquet"
STOCK_BASIC = PROJECT_ROOT / "data" / "reference" / "stock_basic.parquet"

MAX_CALENDAR_STALENESS_TRADING_DAYS = 5     # FORWARD_PREREG freshness rule
MAX_PULL_AGE_HOURS = 48.0
TEXT_MIGRATION_MANIFEST = PROJECT_ROOT / "data" / "text_store" / "migration_manifest.json"
PULL_MANIFEST_DIR = PROJECT_ROOT / "logs" / "text_pull"

#: R3 Blocker-1: attempt states. `started` is NON-TERMINAL — it can never be
#: bypassed by an ordinary --new-attempt; only a dedicated, attested
#: --abandon-started-attempt transitions it to a terminal retryable state.
TERMINAL_RETRYABLE = frozenset({"failed", "abandoned_due_to_crash"})
TERMINAL_FINAL = frozenset({"published"})

#: R3 Major-2: worktree-clean whitelist — generated logs/outputs and local
#: secrets ONLY. Never data/, config/, src/, tests/, prereg, registries.
WORKTREE_CLEAN_WHITELIST = ("logs/", "workspace/outputs/", ".env")

#: R2 Blocker-3 / Major-5: manifest completeness is CODE-enforced — a manifest
#: missing any of these fields refuses to build (tests pin this set).
REQUIRED_MANIFEST_FIELDS = frozenset({
    "decision_id", "strategy_id", "cycle", "decision_time", "fill_date",
    "git_commit", "git_worktree_clean",
    "provider_build_id", "calendar_policy_id", "provider_calendar_end",
    "calendar_staleness_trading_days", "latest_allowed_asof",
    "provider_manifest_sha256", "trade_cal_sha256", "qlib_calendar_sha256",
    "factor_registry_sha256", "factor_list", "factor_expression_hashes",
    "golden_stock_events_hash", "pool_parquet_hash", "industry_map_hash",
    "quant_scores_hash",
    "config_hash", "prompt_hashes", "model_ids",
    "text_store_hash_by_required_source", "input_row_hashes_by_source",
    "dossier_hash_by_ts_code", "llm_artifact_hash_by_ts_code",
    "validated_scorecard_hash_by_ts_code",
    "overlay_audit_hash", "decision_json_hash", "scorecards_parquet_hash",
    "text_pull_manifest", "prereg",
    # R3 Blocker-3 / Major-1
    "text_coverage_manifest_hash", "text_coverage_window",
    "text_coverage_required_sources",
    "text_store_migration_manifest_hash", "text_store_migration_id",
})

#: R3 Blocker-2: per-name artifacts the manifest must pin — by DIRECTORY SCAN,
#: never by trusting the success path (failed/partial spends are spends too).
PER_NAME_ARTIFACTS = (
    "extract_request.json",
    "extract_response_raw.json",
    "score_request.json",
    "score_response_raw.json",
    "validated_scorecard.json",
    "failure.json",
)


class ForwardGateError(Exception):
    """A fail-closed forward gate refused the cycle."""


# ------------------------------------------------------------- hash helpers

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_json_atomic(path: Path, obj) -> None:
    fd, tmp = tempfile.mkstemp(suffix=".json.tmp", dir=path.parent)
    os.close(fd)
    try:
        Path(tmp).write_text(json.dumps(obj, indent=2, ensure_ascii=False),
                             encoding="utf-8")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------- pure gates

def compute_decision_id(cycle: str, decision_time: str, config_hash: str,
                        git_commit: str) -> str:
    payload = f"{cycle}|{decision_time}|{config_hash}|{git_commit}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def previous_open_day(fill_date, trade_cal: pd.DataFrame) -> pd.Timestamp:
    """Last OPEN trading day STRICTLY before fill_date (the quant as-of bound)."""
    cal = trade_cal.loc[trade_cal["is_open"] == 1, "cal_date"].astype(str)
    fill = pd.Timestamp(fill_date).strftime("%Y%m%d")
    prev = cal[cal < fill]
    if prev.empty:
        raise ForwardGateError(f"no open day before fill date {fill} in trade_cal")
    return pd.Timestamp(prev.max())


def check_provider_asof_bound(provider_end, latest_allowed_asof) -> None:
    """R2 Blocker-4: provider data on/after the fill day must never rank names."""
    p = pd.Timestamp(provider_end).normalize()
    a = pd.Timestamp(latest_allowed_asof).normalize()
    if p > a:
        raise ForwardGateError(
            f"provider calendar end {p.date()} exceeds the latest allowed as-of "
            f"{a.date()} (last open day before fill) — same/future-day factor "
            f"rows would leak into the ranking; refusing")


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
                        required_sources: list[str] | None = None,
                        max_age_hours: float = MAX_PULL_AGE_HOURS) -> None:
    """The latest daily text pull must be CLEAN, FRESH, and cover every
    required source with an ok status (R2 Blocker-6)."""
    if not manifest.get("ok", False):
        raise ForwardGateError(
            f"latest text pull manifest reports failures: {manifest.get('failures')} "
            f"— text inputs incomplete, refusing the cycle")
    run_ts = pd.Timestamp(manifest["run_ts"])
    if run_ts.tzinfo is None:                     # legacy naive = CN wall time
        run_ts = run_ts.tz_localize(CN_TZ)
    dt = decision_time if decision_time.tzinfo else decision_time.tz_localize(CN_TZ)
    age_h = (dt - run_ts).total_seconds() / 3600.0
    if age_h > max_age_hours or age_h < 0:
        raise ForwardGateError(
            f"latest text pull is {age_h:.1f}h old (max {max_age_hours}h) — "
            f"run text_daily_pull before deciding")
    if required_sources:
        status = manifest.get("source_status", {})
        bad = [s for s in required_sources
               if not str(status.get(s, "missing")).startswith("ok_")]
        if bad:
            raise ForwardGateError(
                f"required sources without ok pull status: {bad} "
                f"(statuses: { {s: status.get(s, 'missing') for s in bad} })")


def check_config_hash(actual: str, expected: str) -> None:
    if actual != expected:
        raise ForwardGateError(
            f"config hash {actual} != prereg-pinned {expected} — a frozen "
            f"artifact changed; amend FORWARD_PREREG (new version) instead")


def check_decision_before_fill_open(decision_time: pd.Timestamp,
                                    fill_date: pd.Timestamp) -> None:
    """C5: the decision must exist BEFORE the fill day's 09:25 CN open."""
    fill_open = (pd.Timestamp(pd.Timestamp(fill_date).date()).tz_localize(CN_TZ)
                 + pd.Timedelta(hours=9, minutes=25))
    dt = decision_time if decision_time.tzinfo else decision_time.tz_localize(CN_TZ)
    if dt >= fill_open:
        raise ForwardGateError(
            f"decision_time {dt} is not strictly before the {fill_open} CN open "
            f"— a post-open 'decision' is a backfill (C5), refused")


def check_worktree_clean(porcelain_output: str) -> None:
    """R2 Blocker-3: a dirty worktree makes the recorded commit meaningless.

    R3 Major-2: an explicit whitelist covers GENERATED paths only (logs,
    forward outputs, local secrets) — any dirty code/config/data/test/prereg
    path still refuses.
    """
    offending = []
    for line in porcelain_output.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip().strip('"').replace("\\", "/")
        # rename entries look like "old -> new"; judge the destination
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if any(path == w.rstrip("/") or path.startswith(w)
               for w in WORKTREE_CLEAN_WHITELIST):
            continue
        offending.append(line.rstrip())
    if offending:
        raise ForwardGateError(
            "git worktree is DIRTY — commit or stash before a forward decision; "
            "the recorded commit must byte-identify the deciding code:\n"
            + "\n".join(offending)[:800])


def load_attempt_index(cycles_root: Path, ledger_path: Path,
                       cycle: str) -> dict[str, dict]:
    """R3 Blocker-1: cross-check attempt DIRECTORIES against the append-only
    LEDGER — the ledger is a start-gate, not just an audit trail.

    - an attempt dir without attempt_manifest.json = refused (torn attempt);
    - a ledger-referenced attempt whose dir is GONE = refused (manual
      deletion/loss is an evidence breach, never a fresh cycle).
    """
    by_id: dict[str, dict] = {}
    cycle_dir = cycles_root / cycle
    for d in (sorted(cycle_dir.glob("attempt_*")) if cycle_dir.exists() else []):
        attempt_id = d.name.removeprefix("attempt_")
        am = d / "attempt_manifest.json"
        if not am.exists():
            raise ForwardGateError(
                f"attempt dir {d} lacks attempt_manifest.json — torn attempt, refusing")
        m = json.loads(am.read_text(encoding="utf-8"))
        by_id.setdefault(attempt_id, {})["dir"] = d
        by_id[attempt_id]["dir_status"] = m.get("status")
    if ledger_path.exists():
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            ev = json.loads(line)
            if ev.get("cycle") != cycle:
                continue
            attempt_id = ev.get("decision_id")
            by_id.setdefault(attempt_id, {})["ledger_seen"] = True
            by_id[attempt_id].setdefault("ledger_events", []).append(ev.get("event"))
    missing_dirs = [aid for aid, x in by_id.items()
                    if x.get("ledger_seen") and "dir_status" not in x]
    if missing_dirs:
        raise ForwardGateError(
            f"attempt ledger references missing attempt dirs {missing_dirs} for "
            f"cycle {cycle} — manual deletion/loss is an evidence breach, "
            f"refusing silent rerun")
    return by_id


def ensure_attempt_allowed(cycles_root: Path, cycle: str, *,
                           new_attempt: bool = False,
                           ledger_path: Path | None = None) -> None:
    """Append-only attempt discipline (R2 Blocker-2 + R3 Blocker-1):

    - a PUBLISHED attempt exists -> ALWAYS refuse (the decision exists);
    - a NON-TERMINAL (`started`) attempt exists -> ALWAYS refuse, even with
      --new-attempt: a partial LLM spend must first be terminally abandoned
      via --abandon-started-attempt (attested, ledger-counted);
    - terminally failed/abandoned attempts exist -> refuse unless
      ``new_attempt`` (an explicit, ledger-counted retry).
    """
    ledger = ledger_path if ledger_path is not None else ATTEMPTS_LEDGER
    attempts = load_attempt_index(cycles_root, ledger, cycle)
    published = [aid for aid, x in attempts.items()
                 if x.get("dir_status") in TERMINAL_FINAL]
    if published:
        raise ForwardGateError(
            f"cycle {cycle} already has a PUBLISHED decision {published} — "
            f"forward decisions are append-only, never re-made")
    nonterminal = [aid for aid, x in attempts.items()
                   if x.get("dir_status") not in TERMINAL_RETRYABLE]
    if nonterminal:
        raise ForwardGateError(
            f"cycle {cycle} has NON-TERMINAL attempt(s) {nonterminal} — a "
            f"partial LLM spend can never be bypassed; terminally abandon it "
            f"first via --abandon-started-attempt <id> --new-attempt <reason>")
    if attempts and not new_attempt:
        raise ForwardGateError(
            f"cycle {cycle} has prior failed/abandoned attempt(s) "
            f"{sorted(attempts)} — retry requires an explicit "
            f"--new-attempt <reason> (ledger-counted); silent retries are a "
            f"selection channel")


def collect_llm_artifact_hashes(names_dir: Path, status_by_code: dict[str, str],
                                dir_name_of: dict[str, str]) -> dict[str, dict]:
    """R3 Blocker-2: hash EVERY attempted LLM artifact by scanning the per-name
    dirs — success, scorecard violation, parse failure, all pinned; a
    replaced/removed artifact after publication becomes a manifest mismatch.

    Consistency rules: status ok requires the full 5-artifact chain; any
    failure status requires at least failure.json; no_text is pinned as an
    explicit no-attempt. Missing artifacts REFUSE the publication.
    """
    out: dict[str, dict] = {}
    for code, status in status_by_code.items():
        entry: dict = {"status": status}
        if status == "no_text":
            entry["llm_attempted"] = False
            out[code] = entry
            continue
        name_dir = names_dir / dir_name_of[code]
        if not name_dir.exists():
            raise ForwardGateError(
                f"missing per-name artifact dir for attempted name {code}")
        entry["llm_attempted"] = True
        entry["artifacts"] = {fn: sha256_file(name_dir / fn)
                              for fn in PER_NAME_ARTIFACTS
                              if (name_dir / fn).exists()}
        if status == "ok":
            required = {"extract_request.json", "extract_response_raw.json",
                        "score_request.json", "score_response_raw.json",
                        "validated_scorecard.json"}
        else:
            required = {"failure.json"}
        missing = required - set(entry["artifacts"])
        if missing:
            raise ForwardGateError(
                f"{code} status={status} is missing artifact hashes {sorted(missing)} "
                f"— an unpinned LLM spend cannot be published")
        out[code] = entry
    return out


def check_text_coverage_history(manifest_dir: Path, *,
                                decision_time: pd.Timestamp,
                                lookback_days: int,
                                required_sources: list[str]) -> dict:
    """R3 Blocker-3: a fresh, clean LATEST pull does not prove the 30-day
    dossier window is complete — every calendar day in the lookback must be
    covered by some ok pull manifest (or the pre-start bootstrap manifest)
    with an ok_ per-source status for EVERY required source.

    A failed manifest does not poison the gate by itself IF later overlapping
    clean pulls re-covered its dates (the 4-day-lookback design exists for
    exactly that); it is recorded for audit. Uncovered dates REFUSE.
    """
    dt = decision_time if decision_time.tzinfo else decision_time.tz_localize(CN_TZ)
    dt = dt.tz_convert(CN_TZ)
    end = dt.date()
    start = (dt - pd.Timedelta(days=lookback_days - 1)).date()

    covered: dict[str, set] = {s: set() for s in required_sources}
    bad_manifests: list[dict] = []
    used: list[str] = []
    for p in sorted(manifest_dir.glob("pull_manifest_*.json")):
        if p.name == "pull_manifest_latest.json":
            continue
        m = json.loads(p.read_text(encoding="utf-8"))
        w = m.get("window", {})
        if not w.get("start") or not w.get("end"):
            continue
        ws, we = pd.Timestamp(w["start"]).date(), pd.Timestamp(w["end"]).date()
        if we < start or ws > end:
            continue                              # outside the dossier window
        if not m.get("ok", False):
            bad_manifests.append({"manifest": p.name,
                                  "failures": m.get("failures", [])[:5]})
            continue
        status = m.get("source_status", {})
        used.append(p.name)
        d = ws
        while d <= we:
            if start <= d <= end:
                for s in required_sources:
                    if str(status.get(s, "missing")).startswith("ok_"):
                        covered[s].add(d)
            d += pd.Timedelta(days=1)

    all_days = [d.date() for d in pd.date_range(start, end)]
    missing = {s: [str(d) for d in all_days if d not in covered[s]]
               for s in required_sources}
    missing = {s: v for s, v in missing.items() if v}
    if missing:
        raise ForwardGateError(
            f"text coverage incomplete over the dossier lookback "
            f"{start}..{end}: missing={missing}; unre-covered failed "
            f"manifests={bad_manifests} — a gap changes no_text/coverage/"
            f"selection while looking valid; refusing")
    return {"window_start": str(start), "window_end": str(end),
            "required_sources": list(required_sources),
            "manifest_files_used": used,
            "failed_manifests_recovered_later": bad_manifests,
            "coverage_ok": True}


def build_manifest(fields: dict) -> dict:
    """R2 Blocker-3: refuse to build a manifest missing ANY required field."""
    missing = sorted(REQUIRED_MANIFEST_FIELDS - set(fields))
    if missing:
        raise ForwardGateError(f"manifest is missing required fields: {missing}")
    blank = sorted(k for k in REQUIRED_MANIFEST_FIELDS
                   if fields[k] is None or fields[k] == "")
    if blank:
        raise ForwardGateError(f"manifest has blank required fields: {blank}")
    return dict(fields)


# ------------------------------------------------------------- orchestration

def _load_dryrun_module():
    """Reuse the validated chain pieces (config/composite/dossier builders)."""
    spec = importlib.util.spec_from_file_location(
        "mvp_rerank_chain", Path(__file__).parent / "run_ai_rerank_dryrun.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(*args: str) -> str:
    out = subprocess.run(["git", *args], cwd=PROJECT_ROOT,
                         capture_output=True, text=True, check=True)
    return out.stdout


def _load_pinned_hash() -> str:
    """The prereg pins the hash inside FORWARD_PREREG.md as `config_hash_v2: <h>`."""
    prereg = Path(__file__).parent / "FORWARD_PREREG.md"
    for line in prereg.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("config_hash_v2:"):
            return line.split(":", 1)[1].strip().strip("`")
    raise ForwardGateError("FORWARD_PREREG.md lacks a pinned config_hash_v2 line")


def _ledger_append(event: dict) -> None:
    ATTEMPTS_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(ATTEMPTS_LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


def _reply_is_pure_json(text: str) -> bool:
    try:
        json.loads(text.strip())
        return True
    except json.JSONDecodeError:
        return False


def run_decision(cycle: str, *, new_attempt_reason: str | None = None) -> int:
    chain = _load_dryrun_module()
    from data_infra.golden_stock_universe import load_golden_stock_events
    from data_infra.text_store import DEFAULT_STORE_DIR, load_text
    from portfolio_risk.rank_book_construction import apply_rank_overlay
    from ai_layer.ark_client import ArkClientError, chat, parse_json_reply
    from ai_layer.prompt_render import render_extract_messages, render_score_messages
    from ai_layer.scorecard import (ScorecardViolation, compute_scorecard_final,
                                    validate_scorecard_record)

    # -------- pure gates (NOTHING is spent before all of these pass) --------
    decision_time = pd.Timestamp.now(tz=CN_TZ)
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
    trade_cal = pd.read_parquet(TRADE_CAL)
    latest_allowed_asof = previous_open_day(fill_date, trade_cal)
    check_provider_asof_bound(calendar_end, latest_allowed_asof)
    staleness = check_calendar_freshness(calendar_end, fill_date.strftime("%Y%m%d"),
                                         trade_cal)

    required_sources = list(cfg["dossier"]["sources"])
    if not PULL_MANIFEST_LATEST.exists():
        raise ForwardGateError("no text pull manifest — text_daily_pull has never run")
    pull_manifest = json.loads(PULL_MANIFEST_LATEST.read_text(encoding="utf-8"))
    check_pull_manifest(pull_manifest, decision_time, required_sources)
    # R3 Blocker-3: the WHOLE dossier lookback must be covered, not just the tail
    coverage_record = check_text_coverage_history(
        PULL_MANIFEST_DIR, decision_time=decision_time,
        lookback_days=int(cfg["dossier"]["lookback_days"]),
        required_sources=required_sources)
    # R3 Major-1: the PIT-preserving migration proof must exist and be pinned
    if not TEXT_MIGRATION_MANIFEST.exists():
        raise ForwardGateError(
            f"text store migration manifest missing: {TEXT_MIGRATION_MANIFEST}")
    migration_manifest = json.loads(TEXT_MIGRATION_MANIFEST.read_text(encoding="utf-8"))
    migration_id = migration_manifest["migrations"][-1]["migration_id"]

    text_store_paths = {s: Path(DEFAULT_STORE_DIR) / s / f"text_{s}.parquet"
                        for s in required_sources}
    missing_stores = [s for s, p in text_store_paths.items() if not p.exists()]
    if missing_stores:                                    # R2 Blocker-6
        raise ForwardGateError(f"required text stores missing: {missing_stores}")
    text_store_hashes = {s: sha256_file(p) for s, p in text_store_paths.items()}

    git_commit = _git("rev-parse", "HEAD").strip()
    check_worktree_clean(_git("status", "--porcelain"))    # R2 Blocker-3

    pool_path = POOL_DIR / f"broker_recommend_{cycle}.parquet"
    if not pool_path.exists():
        raise ForwardGateError(f"pool parquet missing: {pool_path}")

    # -------- attempt reservation BEFORE any LLM spend (R2 Blocker-2) --------
    decision_id = compute_decision_id(cycle, decision_time.isoformat(),
                                      cfg_hash, git_commit)
    ensure_attempt_allowed(CYCLES_ROOT, cycle,
                           new_attempt=new_attempt_reason is not None)
    attempt_dir = CYCLES_ROOT / cycle / f"attempt_{decision_id}"
    attempt_dir.mkdir(parents=True, exist_ok=False)
    attempt_manifest_path = attempt_dir / "attempt_manifest.json"
    attempt_state = {
        "status": "started", "cycle": cycle, "decision_id": decision_id,
        "decision_time": decision_time.isoformat(), "git_commit": git_commit,
        "config_hash": cfg_hash, "pure_gate_status": "passed",
        "new_attempt_reason": new_attempt_reason,
        "pid": os.getpid(),                     # liveness hint for --abandon
    }
    write_json_atomic(attempt_manifest_path, attempt_state)
    _ledger_append({"event": "attempt_started", "cycle": cycle,
                    "decision_id": decision_id,
                    "decision_time": decision_time.isoformat(),
                    "new_attempt_reason": new_attempt_reason})
    pool = sorted(set(cyc["ts_code"]))
    print(f"[gates] ALL PASS — cycle={cycle} fill={fill_date.date()} "
          f"asof<={latest_allowed_asof.date()} staleness={staleness}d "
          f"pool={len(pool)} attempt={decision_id}", flush=True)

    try:
        return _run_attempt_body(
            chain=chain, cfg=cfg, cfg_hash=cfg_hash, cycle=cycle, pool=pool,
            cyc=cyc, decision_time=decision_time, decision_id=decision_id,
            fill_date=fill_date, latest_allowed_asof=latest_allowed_asof,
            calendar_end=calendar_end, staleness=staleness,
            provider_manifest=provider_manifest, pull_manifest=pull_manifest,
            coverage_record=coverage_record, migration_id=migration_id,
            text_store_paths=text_store_paths, text_store_hashes=text_store_hashes,
            git_commit=git_commit, pool_path=pool_path,
            required_sources=required_sources, attempt_dir=attempt_dir,
            attempt_state=attempt_state, load_text=load_text,
            apply_rank_overlay=apply_rank_overlay, chat=chat,
            parse_json_reply=parse_json_reply, ArkClientError=ArkClientError,
            render_extract_messages=render_extract_messages,
            render_score_messages=render_score_messages,
            ScorecardViolation=ScorecardViolation,
            compute_scorecard_final=compute_scorecard_final,
            validate_scorecard_record=validate_scorecard_record,
        )
    except BaseException as e:
        attempt_state.update({"status": "failed",
                              "stage": "attempt_body",
                              "error": f"{type(e).__name__}: {e}"[:500]})
        write_json_atomic(attempt_manifest_path, attempt_state)
        _ledger_append({"event": "attempt_failed", "cycle": cycle,
                        "decision_id": decision_id,
                        "error": f"{type(e).__name__}: {e}"[:300]})
        raise


def _run_attempt_body(*, chain, cfg, cfg_hash, cycle, pool, cyc, decision_time,
                      decision_id, fill_date, latest_allowed_asof, calendar_end,
                      staleness, provider_manifest, pull_manifest,
                      coverage_record, migration_id,
                      text_store_paths, text_store_hashes, git_commit, pool_path,
                      required_sources, attempt_dir, attempt_state, load_text,
                      apply_rank_overlay, chat, parse_json_reply, ArkClientError,
                      render_extract_messages, render_score_messages,
                      ScorecardViolation, compute_scorecard_final,
                      validate_scorecard_record) -> int:
    from data_infra.provider_metadata import tushare_to_qlib_canonical
    attempt_manifest_path = attempt_dir / "attempt_manifest.json"

    comp = chain.quant_composite_for_pool(pool, asof_end=latest_allowed_asof)
    quant_scores_hash = sha256_text(
        "\n".join(f"{c}={comp[c]:.10f}" for c in sorted(comp.index)))

    cutoff = decision_time.tz_localize(None) - pd.Timedelta(
        days=cfg["dossier"]["lookback_days"])
    texts, input_row_hashes = {}, {}
    for s in required_sources:
        df = load_text(s, decision_time, require_exists=True)   # R2 Blocker-6
        df = df[df["decision_visible_at"] >= cutoff] if not df.empty else df
        texts[s] = df
        input_row_hashes[s] = sha256_text(
            "\n".join(sorted(df["content_hash"])) if not df.empty else "")

    floor_names = comp.sort_values(ascending=False).head(
        cfg["book"]["promotion_floor"]).index.tolist()
    sb = pd.read_parquet(STOCK_BASIC, columns=["ts_code", "industry"])
    industry_of = {t: (i if isinstance(i, str) and i else None)
                   for t, i in zip(sb["ts_code"], sb["industry"])}

    weights, tilt_cap = cfg["weights"], float(cfg["tilt"]["tilt_cap"])
    records = []
    dossier_hashes, scorecard_hashes = {}, {}
    dir_name_of: dict[str, str] = {}
    names_dir = attempt_dir / "names"
    for n, code in enumerate(floor_names, 1):
        dossier = chain.build_dossier(code, texts, cfg)
        row = {"ts_code": code, "quant_score": float(comp[code]),
               "n_chars": len(dossier)}
        if not dossier.strip():
            row.update({"status": "no_text", "final": None})
            records.append(row)
            continue
        dir_name_of[code] = tushare_to_qlib_canonical(code)
        name_dir = names_dir / dir_name_of[code]
        name_dir.mkdir(parents=True, exist_ok=True)
        dossier_hashes[code] = sha256_text(dossier)
        try:
            # ---- stream EVERY LLM artifact as it happens (R2 Blocker-2) ----
            msgs1 = render_extract_messages(cfg["_prompt_extract"], dossier)
            write_json_atomic(name_dir / "extract_request.json", msgs1)
            r1 = chat(msgs1, model=cfg["models"]["quick"],
                      thinking=cfg["models"]["thinking"],
                      temperature=cfg["models"]["temperature"], max_tokens=1200)
            write_json_atomic(name_dir / "extract_response_raw.json", r1.raw)
            digest = parse_json_reply(r1.text)

            spans = dossier[:1200]
            msgs2 = render_score_messages(cfg["_prompt_score"], digest, spans)
            write_json_atomic(name_dir / "score_request.json", msgs2)
            r2 = chat(msgs2, model=cfg["models"]["deep"],
                      thinking=cfg["models"]["thinking"],
                      temperature=cfg["models"]["temperature"], max_tokens=1500)
            write_json_atomic(name_dir / "score_response_raw.json", r2.raw)
            rec = parse_json_reply(r2.text)

            evidence_context = dossier          # B1+: RAW source text only
            validate_scorecard_record(rec, weights=weights)
            final = compute_scorecard_final(rec, weights=weights,
                                            evidence_context=evidence_context)
            write_json_atomic(name_dir / "validated_scorecard.json", rec)
            scorecard_hashes[code] = sha256_text(
                json.dumps(rec, ensure_ascii=False, sort_keys=True))
            row.update({"status": "ok", "final": final,
                        "reply_pure_json": _reply_is_pure_json(r2.text),
                        "scorecard": json.dumps(rec, ensure_ascii=False)})
        except (ArkClientError, ScorecardViolation) as e:
            write_json_atomic(name_dir / "failure.json",
                              {"error": f"{type(e).__name__}: {e}"[:500]})
            row.update({"status": f"fail:{type(e).__name__}", "final": None,
                        "err": str(e)[:200]})
        records.append(row)
        if n % 10 == 0:
            print(f"[llm] {n}/{len(floor_names)}", flush=True)

    det = pd.DataFrame(records)
    # R3 Blocker-2: pin EVERY attempted LLM artifact by directory scan —
    # failed/partial spends included; missing artifacts refuse publication
    llm_artifact_hashes = collect_llm_artifact_hashes(
        names_dir, dict(zip(det["ts_code"], det["status"])), dir_name_of)
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

    # ---- R2 Major-4: caps are EXPLICIT gates, never bare assert ----
    caps, k = cfg["portfolio_caps"], cfg["book"]["k"]
    observed = {
        "max_name_weight": 1.0 / k,
        "ai_oneway_turnover": len(res.swaps_in) / k,
        "ai_l1_active_weight": 2.0 * len(res.swaps_in) / k,
    }
    ind_counts: dict[str, int] = {}
    for c in res.final:
        ind = industry_of.get(c)
        if ind:
            ind_counts[ind] = ind_counts.get(ind, 0) + 1
    observed["max_industry_weight"] = max(ind_counts.values(), default=0) / k
    for obs_key, cap_key in (("max_name_weight", "max_name_weight"),
                             ("ai_oneway_turnover", "max_ai_oneway_turnover"),
                             ("ai_l1_active_weight", "max_ai_l1_active_weight"),
                             ("max_industry_weight", "max_industry_weight")):
        if observed[obs_key] > float(caps[cap_key]) + 1e-9:
            raise ForwardGateError(
                f"portfolio cap breached: {obs_key}={observed[obs_key]:.4f} > "
                f"{cap_key}={caps[cap_key]} — refusing to publish")

    ew = 1.0 / k
    overlay_audit = {
        "swaps_in": res.swaps_in, "swaps_out": res.swaps_out,
        "clamped": res.clamped, "vetoes": res.vetoes,
        "veto_removed": res.veto_removed,
        "veto_backfill_in": res.veto_backfill_in,
        "tilt_swaps": res.tilt_swaps,
        "industry_cap_skipped_entrants": res.industry_cap_skipped_entrants,
        "coverage_scored_pct": scored_pct,
        "overlay_disabled_for_cycle": overlay_disabled,
        "portfolio_caps_observed": observed,
        "portfolio_caps_config": dict(caps),
    }
    decision = {
        "decision_id": decision_id,
        "cycle": cycle, "decision_time": decision_time.isoformat(),
        "strategy_version": "mvp_pool_rerank_v2",
        "legs": {"quant_book": res.quant_book, "ai_book": res.final,
                 "pool_ew": pool},
        "overlay_audit": overlay_audit,
        "fill_plan": {"fill_date": fill_date.strftime("%Y-%m-%d"),
                      "fill_price_basis": "next_open_paper",
                      "weights": {c: ew for c in res.final}},
    }

    det.to_parquet(attempt_dir / "scorecards.parquet", index=False)
    write_json_atomic(attempt_dir / "decision.json", decision)

    # ---- factor expression identity (R2 Blocker-3) ----
    from alpha_research.factor_library.catalog import get_factor_catalog
    cat = get_factor_catalog(include_new_data=True)
    factor_expr_hashes = {f: sha256_text(str(cat[f]))[:16] for f in chain.FACTORS7}
    events_hash = sha256_text("\n".join(sorted(
        f"{r.ts_code}|{r.month}|{r.activation_date}|{r.expiry_date}"
        for r in cyc.itertuples())))

    manifest = build_manifest({
        "decision_id": decision_id,
        "strategy_id": "mvp_pool_rerank_v2",
        "cycle": cycle,
        "decision_time": decision_time.isoformat(),
        "fill_date": fill_date.strftime("%Y-%m-%d"),
        "git_commit": git_commit,
        "git_worktree_clean": True,               # hard-gated above
        "provider_build_id": provider_manifest.get("provider_build_id"),
        "calendar_policy_id": provider_manifest.get("calendar_policy_id"),
        "provider_calendar_end": calendar_end,
        "calendar_staleness_trading_days": staleness,
        "latest_allowed_asof": latest_allowed_asof.strftime("%Y-%m-%d"),
        "provider_manifest_sha256": sha256_file(PROVIDER_MANIFEST),
        "trade_cal_sha256": sha256_file(TRADE_CAL),
        "qlib_calendar_sha256": sha256_file(QLIB_CALENDAR),
        "factor_registry_sha256": sha256_file(FACTOR_REGISTRY),
        "factor_list": list(chain.FACTORS7),
        "factor_expression_hashes": factor_expr_hashes,
        "golden_stock_events_hash": events_hash,
        "pool_parquet_hash": sha256_file(pool_path),
        "industry_map_hash": sha256_file(STOCK_BASIC),
        "quant_scores_hash": quant_scores_hash,
        "config_hash": cfg_hash,
        "prompt_hashes": {
            "extract": sha256_text(cfg["_prompt_extract"]),
            "score": sha256_text(cfg["_prompt_score"]),
        },
        "model_ids": {"quick": cfg["models"]["quick"],
                      "deep": cfg["models"]["deep"]},
        "text_store_hash_by_required_source": text_store_hashes,
        "input_row_hashes_by_source": input_row_hashes,
        "dossier_hash_by_ts_code": dossier_hashes,
        "llm_artifact_hash_by_ts_code": llm_artifact_hashes,
        "validated_scorecard_hash_by_ts_code": scorecard_hashes,
        "text_coverage_manifest_hash": sha256_text(
            json.dumps(coverage_record, ensure_ascii=False, sort_keys=True)),
        "text_coverage_window": {"start": coverage_record["window_start"],
                                 "end": coverage_record["window_end"]},
        "text_coverage_required_sources": coverage_record["required_sources"],
        "text_store_migration_manifest_hash": sha256_file(TEXT_MIGRATION_MANIFEST),
        "text_store_migration_id": migration_id,
        "overlay_audit_hash": sha256_text(
            json.dumps(overlay_audit, ensure_ascii=False, sort_keys=True)),
        "decision_json_hash": sha256_file(attempt_dir / "decision.json"),
        "scorecards_parquet_hash": sha256_file(attempt_dir / "scorecards.parquet"),
        "text_pull_manifest": pull_manifest,
        "prereg": "workspace/research/mvp_pool_book/FORWARD_PREREG.md",
    })
    write_json_atomic(attempt_dir / "manifest.json", manifest)

    attempt_state.update({"status": "published"})
    write_json_atomic(attempt_manifest_path, attempt_state)
    _ledger_append({"event": "attempt_published", "cycle": cycle,
                    "decision_id": decision_id})
    print(f"[published] {attempt_dir} decision_id={decision_id} "
          f"overlay_disabled={overlay_disabled}", flush=True)
    return 0


def _pid_alive(pid: int) -> bool | None:
    """Best-effort liveness check; None = unverifiable on this host."""
    try:
        import psutil  # type: ignore
        return psutil.pid_exists(pid)
    except ImportError:
        return None


def run_abandon_attempt(cycle: str, attempt_id: str, reason: str) -> int:
    """R3 Blocker-1: the ONLY door out of a `started` attempt — terminal
    ``abandoned_due_to_crash`` with attestation; artifacts preserved forever."""
    if not reason or not reason.strip():
        raise ForwardGateError("--abandon-started-attempt requires a non-empty reason")
    attempt_dir = CYCLES_ROOT / cycle / f"attempt_{attempt_id}"
    am = attempt_dir / "attempt_manifest.json"
    if not am.exists():
        raise ForwardGateError(f"no attempt manifest at {am}")
    state = json.loads(am.read_text(encoding="utf-8"))
    if state.get("status") != "started":
        raise ForwardGateError(
            f"attempt {attempt_id} is '{state.get('status')}', not 'started' — "
            f"only a live-crashed attempt can be abandoned")
    pid = state.get("pid")
    alive = _pid_alive(pid) if pid else None
    if alive is True:
        raise ForwardGateError(
            f"attempt {attempt_id} PID {pid} is STILL RUNNING — abandoning a "
            f"live attempt is a selection channel; wait or kill it first")
    state.update({
        "status": "abandoned_due_to_crash",
        "abandon_reason": reason.strip(),
        "abandoned_at": pd.Timestamp.now(tz=CN_TZ).isoformat(),
        "pid_liveness_at_abandon": ("dead" if alive is False
                                    else "unverified_no_psutil"),
    })
    write_json_atomic(am, state)
    _ledger_append({"event": "attempt_abandoned", "cycle": cycle,
                    "decision_id": attempt_id, "reason": reason.strip()})
    print(f"[abandoned] {attempt_dir} (artifacts preserved)", flush=True)
    return 0


def _published_attempt_dir(cycle: str) -> Path:
    cycle_dir = CYCLES_ROOT / cycle
    if not cycle_dir.exists():
        raise ForwardGateError(f"no decision published for cycle {cycle}")
    for a in sorted(cycle_dir.glob("attempt_*")):
        am = a / "attempt_manifest.json"
        if am.exists() and json.loads(am.read_text(encoding="utf-8")).get(
                "status") == "published":
            return a
    raise ForwardGateError(f"cycle {cycle} has no PUBLISHED attempt")


def run_record_fills(cycle: str) -> int:
    """After the monthly 5-B bump covers the fill date: observed tradability (M5).

    Major-3 (recorded): buy-side only; from cycle #2 a transition fill ledger
    (sell/buy deltas, limit-down sell failure, suspension carry) must land.
    """
    attempt_dir = _published_attempt_dir(cycle)
    fills_path = attempt_dir / "fill_record.json"
    if fills_path.exists():
        raise ForwardGateError(f"{fills_path} already exists — fill records are append-only")
    decision = json.loads((attempt_dir / "decision.json").read_text(encoding="utf-8"))
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
              "recorded_at": pd.Timestamp.now(tz=CN_TZ).isoformat(),
              "provider_calendar_end": chain.provider_calendar_end(),
              "fills": fills}
    write_json_atomic(fills_path, record)
    print(f"[fills] recorded -> {fills_path}", flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycle", required=True, help="pool month, e.g. 202608")
    ap.add_argument("--record-fills", action="store_true")
    ap.add_argument("--new-attempt", metavar="REASON", default=None,
                    help="explicit ledger-counted retry after a TERMINAL "
                         "failed/abandoned attempt (never bypasses 'started')")
    ap.add_argument("--abandon-started-attempt", metavar="ATTEMPT_ID", default=None,
                    help="terminally abandon a crashed 'started' attempt "
                         "(requires --new-attempt REASON as the attestation)")
    args = ap.parse_args()
    FORWARD_ROOT.mkdir(parents=True, exist_ok=True)
    try:
        if args.abandon_started_attempt:
            return run_abandon_attempt(args.cycle, args.abandon_started_attempt,
                                       args.new_attempt or "")
        if args.record_fills:
            return run_record_fills(args.cycle)
        return run_decision(args.cycle, new_attempt_reason=args.new_attempt)
    except ForwardGateError as e:
        print(f"[REFUSED] {e}", file=sys.stderr, flush=True)
        return 2
    except Exception as e:  # noqa: BLE001 — attempt already marked failed
        print(f"[ATTEMPT FAILED] {type(e).__name__}: {e}", file=sys.stderr, flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
