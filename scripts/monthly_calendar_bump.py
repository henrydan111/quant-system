# SCRIPT_STATUS: ACTIVE — calendar-unfreeze Phase 5-B: monthly provider freeze-bump driver
"""Monthly calendar freeze-bump: package the manual thaw Phase 1-4 into a repeatable,
--dry-run-able driver with a HARD human sign-off gate before publish.

UNFREEZE_PLAN.md Phase 5-B (GPT §10 SHIP). Three modes:

  --plan            Preflight + determine target_end + print the plan. No execution.
  (default execute) Catch up raw -> new policy YAML -> full rebuild (staged) -> frozen-prefix
                    audit + FRESH-WINDOW SURVIVORSHIP audit -> dry-run report. STOPS before
                    publish (prints the --publish-approved instruction).
  --publish-approved  The ATOMIC publish transaction (Phase 5-B B3; only after a human
                    reviewed the dry-run report): under raw+publish locks, re-verify
                    parent CAS + raw manifest + audit/staged attestations IMMEDIATELY
                    before the safe staged-first swap, emit provider_build.json with
                    raw_input_manifest_root + parent binding, rebind the approval YAMLs
                    (rollback-on-failure), then post-publish QA. §13 risk action —
                    human-invoked only, NEVER in the automated flow.

Design invariants honored:
  - spent_oos_end STAYS 2026-02-27 across every bump (D3 §6); only calendar_end advances,
    so the born-sealed fresh window grows monotonically.
  - target_end = last COMPLETE trading day passing an endpoint-readiness contract (M1),
    never wall-clock (a partial day must never enter a formal provider).
  - the frozen-prefix audit (bin byte-identity + calendar append-only + sidecar membership)
    AND a fresh-window universe/survivorship audit (M2, no blanket exceptions) both gate.
  - approved exceptions are typed, per-bump, trend-reported (M3); the same type recurring two
    bumps in a row must be a permanent migration, not a silent re-approval.
  - the policy id is passed explicitly (no module default; publish is fail-closed on blank).

The heavy steps (rebuild, publish) delegate to the proven pit_backend / safe-publish paths;
this driver is the ORCHESTRATION + the two new audits + the gates.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
# ROOT itself is needed for the `src.`-prefixed import form. research_orchestrator MUST be
# imported as `src.research_orchestrator...` here: the plain top-level name is shadowed in
# any pytest process that collects tests/research_orchestrator/ (that dir has an
# __init__.py, so pytest binds sys.modules['research_orchestrator'] to the TESTS package).
sys.path.insert(0, str(PROJECT_ROOT))

SPENT_OOS_END = "2026-02-27"        # D3 §6: FROZEN across every bump
FRESH_HOLDOUT_START = "2026-02-28"  # must equal REPORT_RC_FRESH_HOLDOUT_START
POLICY_DIR = PROJECT_ROOT / "config" / "calendar_policies"
APPROVALS_DIR = PROJECT_ROOT / "config" / "field_registry" / "approvals"
OUT_DIR = PROJECT_ROOT / "workspace" / "outputs" / "calendar_unfreeze"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger("monthly_bump")


# ── M1: endpoint-readiness target_end ────────────────────────────────────────
# Each required endpoint family has a post-close vendor-update time (CST hour). target_end
# is the latest open trading day for which (a) the day is closed past every family's update
# hour, and (b) the daily endpoint is non-empty with a plausible name count. Clock+calendar
# alone MAY schedule raw ingest but MUST NOT authorize a formal target_end.
ENDPOINT_UPDATE_HOUR_CST = {"daily": 16, "cyq_perf": 19, "report_rc": 22, "moneyflow": 19}
MIN_PLAUSIBLE_DAILY_ROWS = 4000  # A-share市场级 daily should carry ~5k names; a partial pull is far below


def _open_trading_days(upto: str | None = None) -> list[str]:
    # The formal bump must NOT trust an invalid on-disk calendar merely because a prior writer was
    # expected to validate it (GPT REWORK-5 m2): route through the SAME canonical validator the daily
    # job uses (_validate_trade_cal — SSE-only, continuity, real 8-digit dates) and return UNIQUE ordered
    # open dates.
    from data_infra.pipeline.update_daily_data import _validate_trade_cal
    f = PROJECT_ROOT / "data" / "reference" / "trade_cal.parquet"
    if not f.exists():
        return []
    cal = _validate_trade_cal(pd.read_parquet(f), fresh=False)
    days = sorted({d for d in cal.loc[cal["is_open"] == 1, "cal_date"].astype(str)})
    return [d for d in days if (upto is None or d <= upto)]


def now_cst() -> datetime:
    """Wall-clock in China time — the vendor-update hours are CST, so the readiness check
    must not use the host's local time (GPT B2)."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Shanghai"))
    except Exception:  # pragma: no cover — zoneinfo always present on 3.9+
        return datetime.now()


def determine_target_end(now: datetime, *, probe_ready=None) -> tuple[str | None, dict]:
    """Return (target_end, evidence). The latest open trading day whose data is complete:
    the day is past the LATEST required endpoint update hour AND, when probe_ready is given,
    every required endpoint family passes its readiness/coverage probe. Rolls back to the
    previous open day otherwise. probe_ready(date) -> (ok: bool, evidence: dict) is injectable
    for tests; None skips the probe (schedule/plan use). A formal execute REQUIRES probe_ready
    — daily row count alone cannot authorize a formal target_end (GPT B2)."""
    today = now.strftime("%Y%m%d")
    latest_hour = max(ENDPOINT_UPDATE_HOUR_CST.values())
    candidates = _open_trading_days(upto=today)
    evidence: dict = {"evaluated": [], "latest_required_hour_cst": latest_hour}
    for d in reversed(candidates):
        rec: dict = {"date": d}
        # a day is complete only once we are past its vendor-update window; for `today`
        # that means now (CST) must be past latest_hour, for past days it is trivially so.
        if d == today and now.hour < latest_hour:
            rec["reason"] = f"today not past update hour {latest_hour}:00 CST"
            evidence["evaluated"].append(rec)
            continue
        if probe_ready is not None:
            ok, ep_ev = probe_ready(d)
            rec.update(ep_ev)
            if not ok:
                evidence["evaluated"].append(rec)
                continue
        rec["ok"] = True
        evidence["evaluated"].append(rec)
        return d, evidence
    return None, evidence


# ── policy YAML generation (D1 append-only; spent_oos_end frozen) ─────────────
def next_thaw_step_number() -> int:
    existing = list(POLICY_DIR.glob("frozen_*_thaw_step*.yaml"))
    steps = []
    for p in existing:
        try:
            steps.append(int(p.stem.rsplit("thaw_step", 1)[1]))
        except (IndexError, ValueError):
            continue
    return (max(steps) + 1) if steps else 1


def generate_thaw_policy(target_end: str, parent_build_id: str, *, write: bool) -> tuple[str, Path]:
    """Create a NEW append-only frozen policy at target_end. spent_oos_end/fresh_holdout_start
    stay FROZEN (D3 §6). Returns (policy_id, path). Never edits an existing policy file."""
    end_iso = f"{target_end[:4]}-{target_end[4:6]}-{target_end[6:]}"
    step = next_thaw_step_number()
    policy_id = f"frozen_{target_end}_thaw_step{step}"
    path = POLICY_DIR / f"{policy_id}.yaml"
    if path.exists():
        raise SystemExit(f"policy {policy_id} already exists — refusing to overwrite (append-only)")
    body = {
        "policy_id": policy_id, "policy_schema_version": 1,
        "calendar_start_date": "2008-01-02", "calendar_end_date": end_iso, "data_end_date": end_iso,
        "frozen": True, "reason": f"thaw_step{step}_monthly_freeze_bump",
        "established_at": end_iso,
        "spent_oos_end": SPENT_OOS_END, "fresh_holdout_start": FRESH_HOLDOUT_START,
        # Phase 5-B B3.2: every bump-minted policy makes the raw-input attestation
        # LOAD-BEARING — formal runs under it require the live provider_build.json to
        # carry raw_input_manifest_root (release_gate.assert_provider_raw_attestation).
        "require_raw_input_attestation": True,
        "allowed_modes": ["sandbox", "joinquant_replication", "formal_research_with_explicit_freeze",
                          "joinquant_daily", "joinquant_open_close_replica", "formal", "oos_test"],
        "default_formal_behavior": "require_explicit_policy",
        "notes": [f"Monthly freeze-bump thaw step {step}; parent provider build = {parent_build_id}.",
                  f"spent_oos_end frozen at {SPENT_OOS_END}; the born-sealed fresh window "
                  f"[{FRESH_HOLDOUT_START}, {end_iso}] grows with the calendar (D3)."],
    }
    if write:
        path.write_text(yaml.safe_dump(body, allow_unicode=True, sort_keys=False), encoding="utf-8")
        logger.info("wrote new policy %s", path)
    return policy_id, path


# ── M2: fresh-window survivorship / universe-completeness audit ───────────────
def _membership_from_all_stocks(instruments_dir: Path, cal: pd.DatetimeIndex) -> pd.DataFrame:
    """Daily membership matrix from all_stocks.txt (code, list, delist ranges)."""
    import numpy as np

    rows = []
    for line in (instruments_dir / "all_stocks.txt").read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 3:
            rows.append((parts[0].upper(), parts[1], parts[2]))
    if not rows:
        return pd.DataFrame(index=cal)
    codes = sorted({r[0] for r in rows})
    cidx = {c: i for i, c in enumerate(codes)}
    lo = cal.searchsorted(pd.to_datetime([r[1] for r in rows]), side="left")
    hi = cal.searchsorted(pd.to_datetime([r[2] for r in rows]), side="right")
    mat = np.zeros((len(cal), len(codes)), dtype=bool)
    for (c, _, _), a, b in zip(rows, lo, hi):
        mat[a:b, cidx[c]] = True
    return pd.DataFrame(mat, index=cal, columns=codes)


# core price/volume bins every tradable code must carry (the engine-required kline set); a
# features/<code>/ dir missing any of these is feature-incomplete, not merely present.
REQUIRED_PRICE_BINS = ("open.day.bin", "high.day.bin", "low.day.bin", "close.day.bin",
                       "vol.day.bin", "amount.day.bin", "adj_factor.day.bin")


def _feature_code_paths(features_dir: Path) -> dict[str, Path]:
    """UPPER-code -> feature dir, for codes whose dir carries EVERY core price bin (a bare/partial
    dir does not count). Returns the actual (lowercase on disk) path so bins can be decoded."""
    out: dict[str, Path] = {}
    for p in features_dir.iterdir():
        if p.is_dir() and all((p / b).exists() for b in REQUIRED_PRICE_BINS):
            out[p.name.upper()] = p
    return out


def _bin_span(bin_path: Path) -> tuple[int, int]:
    """(start_pos, last_pos) a Qlib .day.bin covers. Format: float32[0] = start_index (calendar
    position of the first value), float32[1:] = values -> last_pos = start_index + nvalues - 1. A
    per-code bin spans [listing, last-data], NOT the whole calendar — decoding the header is the
    only correct coverage test (a size-vs-full-calendar check false-flags every post-2008 listing).
    Returns (-1, -1) if unreadable/empty/misaligned."""
    import struct
    try:
        size = bin_path.stat().st_size
    except OSError:
        return -1, -1
    nvalues = size // 4 - 1  # minus the 1-float header
    if nvalues <= 0 or size % 4 != 0:  # a non-4-multiple is a corrupt/truncated bin
        return -1, -1
    with open(bin_path, "rb") as fh:
        start_pos = int(struct.unpack("<f", fh.read(4))[0])
    return start_pos, start_pos + nvalues - 1


def fresh_window_survivorship_audit(provider_dir: Path, fresh_start: str, target_end: str) -> dict:
    """M2: for [fresh_start, target_end], EVERY ts_code with a raw daily price row must be in
    the provider all_stocks universe on that day (raw-price-vs-sidecar contradiction = FAIL,
    a universe-contract inconsistency; NO blanket exceptions). This protects the future
    holdout window from survivorship bias (a missing delisted/suspended name biases it)."""
    import numpy as np

    daily_root = PROJECT_ROOT / "data" / "market" / "daily"
    cal = pd.read_parquet(PROJECT_ROOT / "data" / "reference" / "trade_cal.parquet")
    fresh_days = cal[(cal["is_open"] == 1) & (cal["cal_date"] >= fresh_start.replace("-", ""))
                     & (cal["cal_date"] <= target_end.replace("-", ""))]["cal_date"].astype(str).tolist()
    cal_idx = pd.to_datetime(fresh_days)
    members = _membership_from_all_stocks(provider_dir / "instruments", cal_idx)
    # B4/M1: provider feature-COMPLETENESS — membership alone is not completeness, a bare
    # features/<code>/ dir is not either, and neither is a dir whose bins are TRUNCATED before the
    # day the code is raw-priced. (i) present = dir carries every core price bin; (ii) each
    # raw-priced code's close.day.bin must COVER that trading day (decode the Qlib header).
    features_dir = provider_dir / "features"
    feature_paths = _feature_code_paths(features_dir) if features_dir.is_dir() else {}
    feature_codes = set(feature_paths)
    # provider calendar position by YYYYMMDD (day.txt is ISO) — for the bin-coverage check.
    prov_cal = (provider_dir / "calendars" / "day.txt").read_text(encoding="utf-8").split()
    prov_pos = {d.replace("-", ""): i for i, d in enumerate(prov_cal)}
    _span: dict[tuple, tuple] = {}

    def span_of(code: str, binname: str) -> tuple[int, int]:
        key = (code, binname)
        if key not in _span:
            p = feature_paths.get(code)
            _span[key] = _bin_span(p / binname) if p else (-1, -1)
        return _span[key]

    violations: list[dict] = []
    checked_days = 0
    for d in fresh_days:
        f = daily_root / d[:4] / f"daily_{d}.parquet"
        if not f.exists():
            violations.append({"date": d, "type": "missing_raw_daily"})
            continue
        checked_days += 1
        raw = pd.read_parquet(f, columns=["ts_code"])
        # provider code form 000001_SZ (underscore); raw is 000001.SZ / 830001.BJ etc.
        raw_codes = {c.replace(".", "_").upper() for c in raw["ts_code"].dropna().astype(str)}
        day_ts = pd.Timestamp(d)
        if day_ts not in members.index:
            continue
        present = set(members.columns[members.loc[day_ts].values])
        # (a) raw-priced code missing from all_stocks membership on that day
        not_in_universe = sorted(raw_codes - present)
        if not_in_universe:
            violations.append({"date": d, "type": "raw_price_not_in_universe",
                               "n": len(not_in_universe), "examples": not_in_universe[:10]})
        # (b) raw-priced code missing from the provider feature tree (or missing a core bin)
        not_in_features = sorted(raw_codes - feature_codes)
        if not_in_features:
            violations.append({"date": d, "type": "raw_price_not_in_feature_tree",
                               "n": len(not_in_features), "examples": not_in_features[:10]})
        # (c) a fresh raw-priced day MUST be in the staged provider calendar — else the provider
        # cannot support the claimed target_end (fail closed, GPT M1).
        pos_d = prov_pos.get(d)
        if pos_d is None:
            violations.append({"date": d, "type": "raw_price_day_not_in_provider_calendar",
                               "n": len(raw_codes), "examples": sorted(raw_codes)[:10]})
            continue
        # (d) raw-priced code whose ANY core bin does NOT span this trading day (truncated bin) —
        # every required bin must contain pos_d, not just close (vol/amount/adj_factor matter too).
        too_short = sorted(c for c in (raw_codes & feature_codes)
                           if any(not (span_of(c, b)[0] <= pos_d <= span_of(c, b)[1])
                                  for b in REQUIRED_PRICE_BINS))
        if too_short:
            violations.append({"date": d, "type": "raw_price_bins_short_through_day",
                               "n": len(too_short), "examples": too_short[:10]})
    return {"fresh_days": len(fresh_days), "checked_days": checked_days,
            "feature_tree_codes": len(feature_codes),
            "ok": not violations, "violations": violations[:50]}


# ── M3: typed approved-exceptions registry ───────────────────────────────────
class ExceptionRegistry:
    """Typed, append-only, per-bump approved exceptions for the frozen-prefix audit. The
    fresh-window survivorship audit has NO exceptions. A type recurring for two consecutive
    bumps must become a permanent migration (not re-approved by count)."""

    def __init__(self, path: Path):
        self.path = path
        self.rows = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []

    def add(self, *, exc_type: str, root_cause: str, dataset: str, symbols, date_range: str,
            gross: int, net_after: int, reviewer: str, expiry: str, evidence: str, diff_hash: str):
        if symbols in ("*", "all") or date_range in ("*", "all"):
            raise ValueError("wildcard symbols/date_range are forbidden in an approved exception")
        self.rows.append({
            "exc_type": exc_type, "root_cause": root_cause, "dataset": dataset,
            "symbols": symbols, "date_range": date_range, "gross_diff": gross,
            "net_diff_after_exception": net_after, "reviewer": reviewer,
            "expiry_condition": expiry, "evidence": evidence, "diff_hash": diff_hash,
        })

    def recurring_types(self) -> list[str]:
        from collections import Counter
        c = Counter(r["exc_type"] for r in self.rows)
        return [t for t, n in c.items() if n >= 2]

    def commit(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.rows, ensure_ascii=False, indent=1), encoding="utf-8")


def _live_paths():
    """The ONE canonical path resolution for everything this driver reads/mutates on the
    live side (GPT re-review #4 P0: PROJECT_ROOT/data hardcodes diverge from a config that
    relocates storage.data_root / storage.qlib_data_dir). Returns the pit_backend
    BuildPaths (data_root, qlib_dir, ...). Tests monkeypatch THIS function."""
    from data_infra.pit_backend import resolve_build_paths
    return resolve_build_paths()


def _assert_standard_layout() -> bool:
    """This driver currently supports ONLY the standard layout (qlib_dir directly under
    data_root, both under the project); a split-root configuration REFUSES up front (the
    GPT-sanctioned alternative to threading BuildPaths through every raw reader). The
    provider lock itself is already keyed by the canonical qlib_dir regardless."""
    p = _live_paths()
    data_root = Path(p.data_root).resolve()
    qlib_dir = Path(p.qlib_dir).resolve()
    expected_data = (PROJECT_ROOT / "data").resolve()
    if data_root != expected_data or qlib_dir != data_root / "qlib_data":
        logger.error("non-standard storage layout (data_root=%s, qlib_dir=%s; expected %s and "
                     "%s) — this driver refuses under a split/relocated layout.",
                     data_root, qlib_dir, expected_data, expected_data / "qlib_data")
        return False
    return True


def _tx_dir() -> Path:
    """CANONICAL SHARED transaction directory, adjacent to the provider inside the shared
    store (GPT re-review #4 P0: checkout-local OUT_DIR state let a second checkout inherit
    an un-QA'd child after a hard crash). Intent, per-transaction records, and the report
    snapshot live HERE; publish/finalize/restore read ONLY from here."""
    d = Path(_live_paths().data_root) / "qlib_transactions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def live_provider_ids() -> tuple[str, str]:
    m = json.loads((Path(_live_paths().qlib_dir) / "metadata" / "provider_build.json")
                   .read_text(encoding="utf-8"))
    return m["provider_build_id"], m["calendar_policy_id"]


def _disk_free_gb() -> int:
    return shutil.disk_usage(str(PROJECT_ROOT))[2] // 2**30


def _sha256_file(path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _manifest_root(files: list) -> str:
    import hashlib
    return hashlib.sha256("\n".join(f"{r['path']}:{r['sha256']}:{r['size']}"
                                    for r in files).encode()).hexdigest()


def _full_raw_manifest(data_root=None) -> dict:
    """Full-CONTENT SHA-256 manifest over the builder's ACTUAL read set — EVERY raw dataset file
    (DATASET_SPECS.raw_pattern) PLUS every reference/universe file under data/reference. This is the
    exact data generation the formal provider consumes; the old hand-maintained 6-dataset subset let a
    mutated income/statements/reference file pass unattested (GPT REWORK-5 Blocker 3). The result is a
    FIXED list snapshotted under the raw lock at build time; verify-before-publish re-hashes exactly
    these paths (NOT a re-glob), so legitimate forward daily progress after target_end adds files that
    aren't in the list and cannot false-fail the re-verify."""
    import glob as _glob
    from data_infra.pit_backend import DATASET_SPECS
    root_dir = Path(data_root) if data_root is not None else (PROJECT_ROOT / "data")
    paths = set()
    for spec in DATASET_SPECS.values():
        pattern = getattr(spec, "raw_pattern", None)
        if pattern:
            paths.update(_glob.glob(str(root_dir / pattern), recursive=True))
    ref = root_dir / "reference"
    if ref.exists():
        paths.update(str(p) for p in ref.rglob("*") if p.is_file())
    files = []
    for f in sorted(paths):
        p = Path(f)
        if not p.is_file():
            continue
        files.append({"path": os.path.relpath(f, root_dir).replace("\\", "/"),
                      "sha256": _sha256_file(p), "size": p.stat().st_size})
    files.sort(key=lambda r: r["path"])
    return {"algo": "sha256", "root": _manifest_root(files), "file_count": len(files), "files": files}


def _verify_raw_manifest(manifest: dict, data_root=None) -> tuple[bool, str]:
    """Re-hash exactly the files the manifest lists and confirm the recorded root — a mismatch means the
    raw cut the staged build consumed moved out-of-band since the build (GPT REWORK-5 Blocker 3)."""
    root_dir = Path(data_root) if data_root is not None else (PROJECT_ROOT / "data")
    for r in manifest.get("files", []):
        p = root_dir / r["path"]
        if not p.is_file():
            return False, f"missing consumed file {r['path']}"
        if _sha256_file(p) != r["sha256"]:
            return False, f"changed consumed file {r['path']}"
    recomputed = _manifest_root(manifest.get("files", []))
    if recomputed != manifest.get("root"):
        return False, "manifest sidecar root does not match its own file list (tampered sidecar)"
    return True, "ok"


# ── Phase 5-B B3.3-5: atomic publish transaction helpers ─────────────────────
class PublishTransactionError(RuntimeError):
    """A publish-transaction invariant failed (fail closed; nothing durable mutated
    unless the message says otherwise)."""


from contextlib import contextmanager


@contextmanager
def _defer_sigint(span: str):
    """Defer Ctrl-C across the CRITICAL transaction span. SEMANTICS (re-review #3,
    documented honestly): a REAL SIGINT during the span does NOT roll back — the span
    runs to completion (the consistent core transaction COMMITS: swap + rebind +
    pending_qa marker + records), and KeyboardInterrupt is raised at span exit; the
    operator resumes with --finalize-qa. This is deliberate: aborting mid-span is the
    hazard, a committed-but-quarantined core is safe. In-flow exceptions/interrupts
    RAISED inside the span (crash-like: SystemExit, injected KeyboardInterrupt) are
    handled by the BaseException rollback instead. No-op outside the main thread
    (signal handlers are main-thread-only; the BaseException belt still applies)."""
    import signal
    import threading
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    received: list = []

    def _handler(signum, frame):  # noqa: ARG001
        received.append(signum)
        logger.warning("SIGINT received during the %s span — DEFERRED until the "
                       "transaction reaches a consistent state.", span)

    previous = signal.signal(signal.SIGINT, _handler)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, previous)
        if received:
            raise KeyboardInterrupt(f"deferred SIGINT after the {span} span")


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    import tempfile
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, str(path))
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _staged_content_attestation(tree, *, workers: int = 8, exclude: tuple[str, ...] = (),
                                build_manifest_path=None) -> dict:
    """FULL-CONTENT attestation over an ENTIRE provider tree (GPT re-review Blocker 4: the
    published feature bytes themselves must be proven, not just identity files).

    Every file under the tree (features/*.bin included) AND the build manifest.json is
    content-hashed (sha256; a shared thread pool — 23M small files are open-latency-bound).
    STREAMING BY GROUP (re-review P1: materializing 23M paths+digests+lines at once would
    exhaust memory): each top-level entry / features/<code> dir is walked, hashed, reduced
    to ONE group digest over its sorted "relpath:size:sha256" lines, and released before
    the next group; only the ~5.8k group digests are retained. The root is the sha256 over
    the sorted group map.

    ``exclude`` (tree-relative forward-slash paths) lets the READY-gate re-verification
    skip exactly the files the publish itself adds to the live tree
    (metadata/provider_build.json, metadata/publish_state.json). ``build_manifest_path``
    defaults to <tree_parent>/manifest.json (the staged layout); the live-tree ready check
    passes the retained build root's manifest explicitly."""
    import hashlib
    from concurrent.futures import ThreadPoolExecutor

    prov = Path(tree)
    if not prov.is_dir():
        return {"algo": "sha256_grouped_full_content", "root": "MISSING_STAGED_DIR",
                "file_count": 0, "total_bytes": 0, "groups": {}}
    excluded = set(exclude)
    groups: dict[str, str] = {}
    file_count = 0
    total_bytes = 0

    def _rel(p: Path) -> str:
        return str(p.relative_to(prov)).replace("\\", "/")

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        def hash_group(name: str, paths: list) -> None:
            nonlocal file_count, total_bytes
            rels = [_rel(p) if not isinstance(p, tuple) else p[0] for p in paths]
            fps = [p if not isinstance(p, tuple) else p[1] for p in paths]
            digests = list(pool.map(_sha256_file, fps))
            lines = []
            for rel, fp, dg in zip(rels, fps, digests):
                size = fp.stat().st_size
                total_bytes += size
                lines.append(f"{rel}:{size}:{dg}")
            file_count += len(lines)
            groups[name] = hashlib.sha256("\n".join(sorted(lines)).encode("utf-8")).hexdigest()

        def files_under(d: Path) -> list:
            return [p for p in sorted(d.rglob("*")) if p.is_file() and _rel(p) not in excluded]

        for entry in sorted(prov.iterdir(), key=lambda p: p.name):
            if entry.is_file():
                if _rel(entry) not in excluded:
                    hash_group(f"<top>/{entry.name}", [entry])
            elif entry.name == "features":
                direct = [p for p in sorted(entry.iterdir())
                          if p.is_file() and _rel(p) not in excluded]
                if direct:
                    hash_group("features", direct)
                for code_dir in sorted(p for p in entry.iterdir() if p.is_dir()):
                    fs = files_under(code_dir)
                    if fs:
                        hash_group(f"features/{code_dir.name}", fs)
            else:
                fs = files_under(entry)
                if fs:
                    hash_group(entry.name, fs)

        build_manifest = (Path(build_manifest_path) if build_manifest_path is not None
                          else prov.parent / "manifest.json")
        if build_manifest.is_file():
            hash_group("<build_root>", [("<build_root>/manifest.json", build_manifest)])

    root = hashlib.sha256(
        "\n".join(f"{g}:{h}" for g, h in sorted(groups.items())).encode("utf-8")
    ).hexdigest()
    return {"algo": "sha256_grouped_full_content", "root": root,
            "file_count": file_count, "total_bytes": total_bytes, "groups": groups}


def _approvals_attestation() -> dict:
    """Pin the approvals GOVERNANCE SET: sorted *.yaml filenames, per-file sha256, bound
    count. The publish transaction requires EXACT equality with the execute-time pin AND a
    non-empty bound set — closing the fail-open where deleting (or adding) approval YAMLs
    between execute and publish still published with `approvals_rebound: 0` (GPT re-review
    Blocker 3: the loader returns [] for a missing/emptied directory)."""
    import hashlib
    files = {p.name: _sha256_file(p) for p in sorted(APPROVALS_DIR.glob("*.yaml"))} \
        if APPROVALS_DIR.is_dir() else {}
    from data_infra.approval_evidence import ApprovalEvidenceConfigError, load_approval_bindings
    try:
        bound = len(load_approval_bindings(APPROVALS_DIR))
    except ApprovalEvidenceConfigError:
        bound = -1  # malformed governance dir — roots will still match only if unchanged
    root = hashlib.sha256(
        "\n".join(f"{n}:{h}" for n, h in sorted(files.items())).encode("utf-8")
    ).hexdigest()
    return {"algo": "sha256", "root": root, "file_count": len(files), "bound_count": bound}


def _git_state() -> tuple[str, str]:
    """(HEAD sha, dirty digest) of the source tree — captured at EXECUTE so the published
    manifest attributes the build to the commit that actually produced the bytes; publish
    REQUIRES equality (GPT re-review Major 2: a publish-time rev-parse misattributes the
    build when code moved in between). The dirty digest is 'clean' or a sha256 over
    `git status --porcelain` so an uncommitted-change flip also refuses."""
    import hashlib
    import subprocess
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True,
                                   cwd=str(PROJECT_ROOT)).strip()
    porcelain = subprocess.check_output(["git", "status", "--porcelain"], text=True,
                                        cwd=str(PROJECT_ROOT))
    dirty = "clean" if not porcelain.strip() else hashlib.sha256(porcelain.encode("utf-8")).hexdigest()
    return head, dirty


def _approvals_all_bound_to(pb: str, cp: str) -> tuple[bool, str]:
    """Approvals compare-and-swap precondition: every NON-exempt approval YAML must be
    bound to exactly the parent (pb, cp) so the post-swap rebind is a clean two-token
    rewrite. Any other binding means an approval was added/rebound out-of-band since
    the report — refuse (fail closed). Uses the strict governance loader, so a
    malformed approval also refuses here."""
    from data_infra.approval_evidence import ApprovalEvidenceConfigError, load_approval_bindings
    try:
        bindings = load_approval_bindings(APPROVALS_DIR)
    except ApprovalEvidenceConfigError as exc:
        return False, f"approvals directory fails the governance loader: {exc}"
    bad = [b for b in bindings
           if b.declared_provider_build_id != pb or b.declared_calendar_policy_id != cp]
    if bad:
        detail = "; ".join(
            f"{Path(b.approval_file).name}=({b.declared_provider_build_id}/"
            f"{b.declared_calendar_policy_id})" for b in bad[:5])
        return False, (f"{len(bad)}/{len(bindings)} approval YAML(s) are NOT bound to the "
                       f"parent ({pb}/{cp}): {detail}")
    return True, f"{len(bindings)} bound approval YAML(s) verified against the parent ids"


def _sub_binding_token(data: bytes, key: str, old: str, new: str, path: Path) -> bytes:
    """Replace the single `key: <old>` binding VALUE in a YAML's raw bytes, preserving
    every other byte (quoting style, EOLs, comments). Requires exactly ONE such line —
    zero or multiple means the file drifted from the loader-validated shape (refuse)."""
    import re
    pat = re.compile(
        rb"(?m)^(" + key.encode("utf-8") + rb":[ \t]*)([\"']?)"
        + re.escape(old.encode("utf-8")) + rb"([\"']?)([ \t]*\r?)$"
    )
    hits = pat.findall(data)
    if len(hits) != 1:
        raise PublishTransactionError(
            f"{path.name}: expected exactly 1 '{key}: {old}' binding line, found {len(hits)} "
            "— the file drifted from its loader-validated shape; refusing the rebind."
        )
    return pat.sub(rb"\g<1>\g<2>" + new.encode("utf-8") + rb"\g<3>\g<4>", data, count=1)


def _plan_rebind(old_pb: str, old_cp: str, new_pb: str, new_cp: str,
                 ) -> tuple[list[tuple[Path, bytes]], dict[Path, bytes]]:
    """PURE rebind planner (writes NOTHING — GPT re-review Blocker 2: the caller must hold
    the originals BEFORE any write so restoration lives in exactly one verified place).
    Plans every substitution in memory and re-parses each result (the rebound YAML must
    parse to exactly the new ids). Returns (plan, originals)."""
    from data_infra.approval_evidence import load_approval_bindings
    bindings = load_approval_bindings(APPROVALS_DIR)
    plan: list[tuple[Path, bytes]] = []
    originals: dict[Path, bytes] = {}
    for b in bindings:
        p = Path(b.approval_file)
        data = p.read_bytes()
        nd = _sub_binding_token(data, "provider_build_id", old_pb, new_pb, p)
        nd = _sub_binding_token(nd, "calendar_policy_id", old_cp, new_cp, p)
        parsed = yaml.safe_load(nd.decode("utf-8"))
        if (not isinstance(parsed, dict) or parsed.get("provider_build_id") != new_pb
                or parsed.get("calendar_policy_id") != new_cp):
            raise PublishTransactionError(
                f"{p.name}: rebound YAML does not parse back to the new ids — refusing."
            )
        originals[p] = data
        plan.append((p, nd))
    return plan, originals


def _restore_approval_files(written: list[Path], originals: dict[Path, bytes]) -> list[str]:
    """Restore the WRITTEN approval files from their original bytes and VERIFY each
    restoration by re-reading (GPT re-review Blocker 2: an exit-4 'fully rolled back'
    claim must be proven, not assumed). Returns the list of failures (empty = verified)."""
    failures: list[str] = []
    for p in written:
        try:
            _atomic_write_bytes(p, originals[p])
            if p.read_bytes() != originals[p]:
                failures.append(f"{p.name}: post-restore bytes differ from original")
        except Exception as exc:  # noqa: BLE001 — collect, never mask a partial restore
            failures.append(f"{p.name}: restore failed: {exc}")
    return failures


def _make_publish_builder(staged_build_id: str):
    """Builder handle for the proven safe staged-first swap primitive
    (StagedQlibBackendBuilder.publish). Tests inject a tmp-rooted builder here."""
    from data_infra.pit_backend import StagedQlibBackendBuilder
    return StagedQlibBackendBuilder(build_id=staged_build_id)


def _rollback_swap(builder) -> tuple[bool, str]:
    """Best-effort inverse of StagedQlibBackendBuilder.publish(): NEW live -> adjacent,
    backup -> live (parent restored), NEW tree -> back to the staged provider_dir.
    Returns (live_restored, message). Only the middle rename is CRITICAL — after it the
    parent provider is live again; a stranded NEW tree is loudly named, never silent."""
    qlib = str(builder.paths.qlib_dir)
    bak = f"{qlib}.bak_{builder.build_id}"
    staging = f"{qlib}.new_{builder.build_id}"
    if not os.path.isdir(bak):
        return False, f"cannot roll back: parent backup missing at {bak}"
    if os.path.exists(staging):
        return False, f"cannot roll back: stale {staging} exists — resolve manually"
    try:
        os.replace(qlib, staging)  # NEW live -> adjacent (parent still safe in bak)
    except OSError as exc:
        return False, f"rollback live->staging rename failed ({exc}); the NEW build is still live"
    try:
        os.replace(bak, qlib)  # backup -> live: the CRITICAL restore
    except OSError as exc:
        return False, (f"CRITICAL: live provider MISSING — recover manually: move {bak!r} -> "
                       f"{qlib!r} (the NEW build sits at {staging!r}); restore rename failed: {exc}")
    try:
        os.replace(staging, builder.paths.provider_dir)
        note = "the NEW tree is back at the staged provider_dir for a clean retry"
    except OSError:
        note = (f"parent live restored; the NEW tree remains at {staging} — move it back to "
                f"{builder.paths.provider_dir} before retrying")
    return True, f"rolled back to the parent live provider; {note}"


def _verify_live_manifest(qlib_dir, *, build_id: str, policy_id: str, raw_root: str,
                          parent_pb: str, source_git_commit: str | None = None,
                          ) -> tuple[bool, str]:
    """Post-swap check: the LIVE provider_build.json must attest exactly this
    transaction (build id, policy, raw-input root, parent, and — Major 2 — the
    EXECUTE-time source commit). Catches the emit path failing silently (it is
    deliberately non-raising for legacy callers)."""
    from data_infra.provider_manifest import ProviderManifestError, load_provider_manifest
    try:
        m = load_provider_manifest(qlib_dir)
    except ProviderManifestError as exc:
        return False, f"live manifest absent/unreadable after the swap: {exc}"
    problems = []
    if m.provider_build_id != build_id:
        problems.append(f"provider_build_id={m.provider_build_id!r} != {build_id!r}")
    if m.calendar_policy_id != policy_id:
        problems.append(f"calendar_policy_id={m.calendar_policy_id!r} != {policy_id!r}")
    if m.raw_input_manifest_root != raw_root:
        problems.append(f"raw_input_manifest_root={m.raw_input_manifest_root!r} != {raw_root!r}")
    if m.parent_provider_build_id != parent_pb:
        problems.append(f"parent_provider_build_id={m.parent_provider_build_id!r} != {parent_pb!r}")
    if source_git_commit is not None and m.source_git_commit != source_git_commit:
        problems.append(f"source_git_commit={m.source_git_commit!r} != {source_git_commit!r}")
    return (not problems), ("; ".join(problems) or "ok")


def _write_journal(journal: dict) -> None:
    """NON-RAISING journal write (GPT re-review Blocker 1: a journal-write failure after a
    successful swap must never abort the transaction outside the rollback domain — the
    journal is a recovery breadcrumb, not a gate; a genuinely broken disk still fails the
    transaction through the guarded record writes)."""
    try:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        journal["updated_cst"] = now_cst().isoformat(timespec="seconds")
        _atomic_write_bytes(TRANSACTION_JOURNAL_PATH,
                            json.dumps(journal, ensure_ascii=False, indent=1).encode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.error("journal write failed (non-fatal breadcrumb): %s", exc)


def _read_publish_state(qlib_dir) -> dict:
    """The parsed marker, or {} when absent/unreadable (callers treat unknown as refusal)."""
    p = Path(qlib_dir) / "metadata" / "publish_state.json"
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_publish_state(qlib_dir, state: str, build_id: str, **extra) -> None:
    """Atomic publish-state marker write (<qlib_dir>/metadata/publish_state.json — the B6
    QA quarantine read by release_gate.assert_provider_publish_state). Carries the
    transaction id and the active QA attempt forward from the current marker unless the
    caller overrides them (re-review #3: state transitions must stay attributable)."""
    meta = Path(qlib_dir) / "metadata"
    meta.mkdir(parents=True, exist_ok=True)
    current = _read_publish_state(qlib_dir)
    payload = {"state": state, "provider_build_id": build_id,
               "updated_cst": now_cst().isoformat(timespec="seconds")}
    # every binding field survives a state transition unless explicitly overridden — the
    # record digest in particular anchors the READY gate across attempt rewrites.
    for carried in ("transaction_id", "active_qa_attempt", "record_sha256", "parent_build_id"):
        if carried in current:
            payload[carried] = current[carried]
    payload.update(extra)
    _atomic_write_bytes(meta / "publish_state.json",
                        json.dumps(payload, ensure_ascii=False, indent=1).encode("utf-8"))


# ── re-review #3/#4: durable SHARED intent journal + disk-truth swap classification ──
def _intent_path() -> Path:
    return _tx_dir() / "publish_intent.json"


def _read_intent() -> dict:
    try:
        payload = json.loads(_intent_path().read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_intent(payload: dict) -> None:
    payload = {**payload, "updated_cst": now_cst().isoformat(timespec="seconds")}
    _atomic_write_bytes(_intent_path(),
                        json.dumps(payload, ensure_ascii=False, indent=1).encode("utf-8"))


def _disk_swap_state(builder, parent_pb: str) -> str:
    """'child_live' | 'parent_live' | 'unknown' — classified from DISK FACTS (live
    manifest + backup dir), never from in-process booleans (re-review #3 P0: an exception
    landing between publish() returning and a flag assignment mis-classified a live child
    as pre-swap and skipped the rollback)."""
    qlib = Path(builder.paths.qlib_dir)
    backup = os.path.isdir(f"{builder.paths.qlib_dir}.bak_{builder.build_id}")
    try:
        live = json.loads((qlib / "metadata" / "provider_build.json")
                          .read_text(encoding="utf-8")).get("provider_build_id")
    except (OSError, json.JSONDecodeError):
        live = None  # post-swap pre-emit: the child tree carries no manifest yet
    if backup and live != parent_pb:
        return "child_live"
    if not backup and live == parent_pb:
        return "parent_live"
    return "unknown"


# ── re-review #3: read-only generation seal (the READY-gate immutability) ────
def _seal_tree_readonly(qlib_dir, exclude_rel: tuple = ("metadata/publish_state.json",)) -> int:
    """Set every file in the tree read-only EXCEPT the exact control-plane path(s) —
    TREE-RELATIVE comparison, not basename (GPT re-review #4 P0: a basename exemption left
    any attested payload file that happened to be NAMED publish_state.json writable after
    certification). Sealing happens BEFORE the READY-gate content hash, so the certified
    bytes cannot be modified by any attribute-respecting writer. Returns files sealed."""
    import stat
    root = Path(qlib_dir)
    excluded = set(exclude_rel)
    n = 0
    for p in root.rglob("*"):
        if p.is_file() and str(p.relative_to(root)).replace("\\", "/") not in excluded:
            os.chmod(p, stat.S_IREAD)
            n += 1
    return n


def _unseal_tree(qlib_dir) -> int:
    """Clear the read-only seal (used by --restore-parent before undoing a publish)."""
    import stat
    n = 0
    for p in Path(qlib_dir).rglob("*"):
        if p.is_file():
            os.chmod(p, stat.S_IREAD | stat.S_IWRITE)
            n += 1
    return n


# ── re-review #3: QA attempt lease (a stale worker must never overwrite state) ─
def _begin_qa_attempt(builder, rep: dict) -> str | None:
    """Register THIS worker as the active QA attempt (last-starter-wins lease) under the
    publish lock. Returns the attempt id, or None when the marker/build state does not
    admit a QA attempt."""
    import uuid
    from data_infra.tushare_lock import provider_publish_lock
    with provider_publish_lock(qlib_dir=builder.paths.qlib_dir):
        marker = _read_publish_state(builder.paths.qlib_dir)
        if (marker.get("state") not in ("pending_qa", "qa_failed")
                or marker.get("provider_build_id") != rep["staged_build_id"]):
            return None
        attempt = uuid.uuid4().hex[:16]
        _write_publish_state(builder.paths.qlib_dir, marker["state"], rep["staged_build_id"],
                             active_qa_attempt=attempt)
        return attempt


def _record_qa_failure(builder, rep: dict, attempt: str, qa_rc: int, j) -> int:
    """Persist qa_failed ONLY if this worker still holds the lease and the live state is
    still non-ready for the same build — a stale worker records 'superseded' and changes
    NOTHING (re-review #3 Major: a delayed failing QA overwrote a newer 'ready')."""
    from data_infra.tushare_lock import provider_publish_lock
    with provider_publish_lock(qlib_dir=builder.paths.qlib_dir):
        marker = _read_publish_state(builder.paths.qlib_dir)
        if (marker.get("active_qa_attempt") != attempt
                or marker.get("provider_build_id") != rep["staged_build_id"]
                or marker.get("state") not in ("pending_qa", "qa_failed")):
            j("qa", "superseded", attempt=attempt, marker_state=marker.get("state"),
              marker_attempt=marker.get("active_qa_attempt"))
            logger.warning("stale QA attempt %s superseded (marker state=%r attempt=%r) — "
                           "recording nothing.", attempt, marker.get("state"),
                           marker.get("active_qa_attempt"))
            return 7
        _write_publish_state(builder.paths.qlib_dir, "qa_failed", rep["staged_build_id"],
                             qa_returncode=qa_rc)
    j("qa", "failed", returncode=qa_rc, attempt=attempt)
    logger.critical("PUBLISHED but post-publish QA FAILED (exit %d) — the provider stays live "
                    "but publish-state 'qa_failed' QUARANTINES gated reads until "
                    "--finalize-qa passes. Parent retained as .bak.", qa_rc)
    return 6


def _run_post_publish_qa() -> int:
    import subprocess
    py = str(PROJECT_ROOT / "venv" / "Scripts" / "python.exe")
    return subprocess.run([py, str(PROJECT_ROOT / "scripts" / "run_daily_qa.py")]).returncode


def _write_rebind_record(*, path: Path, new_pb: str, new_cp: str, old_pb: str, old_cp: str,
                         n_files: int, raw_root: str, raw_files: int, backup_dir: str) -> Path:
    """Committed governance record of the rebind (mirrors the 2026-07-01/2026-07-04
    precedent .md files). The PATH is computed once by the transaction (before the
    protected domain) so rollback cleanup can address it from disk without booleans."""
    body = (
        f"# Re-bind to the monthly thaw publish ({new_pb} / {new_cp})\n\n"
        f"Written by the ATOMIC publish transaction (`scripts/monthly_calendar_bump.py "
        f"--publish-approved`, Phase 5-B B3) on {now_cst().isoformat(timespec='seconds')}.\n\n"
        f"{n_files} approval YAMLs re-bound on BOTH ids (provider `{old_pb}` -> `{new_pb}`; "
        f"policy `{old_cp}` -> `{new_cp}`) inside the same lock scope as the swap: the parent "
        f"compare-and-swap, the full-readset raw-input manifest re-hash (root `{raw_root}`, "
        f"{raw_files} files), the audit-artifact hashes, and the staged attestation were all "
        f"re-verified IMMEDIATELY before the safe staged-first swap "
        f"(StagedQlibBackendBuilder.publish), under raw_maintenance_lock + "
        f"provider_publish_lock.\n\n"
        f"`raw_input_manifest_root` + `parent_provider_build_id` are bound into the published "
        f"`data/qlib_data/metadata/provider_build.json`. "
        f"`evaluate_approval_evidence_bindings()` -> 0 drift after the rebind. Prior live "
        f"retained as `{backup_dir}` (one rename from restore). Transaction record: "
        f"`workspace/outputs/calendar_unfreeze/publish_record.json`; journal: "
        f"`publish_transaction_journal.json`.\n"
    )
    _atomic_write_bytes(path, body.encode("utf-8"))
    return path


def _prune_cyq_state(suffix: str) -> None:
    """On a post-catch-up completeness failure, drop the Stage-D cyq_perf resume keys from the
    catch-up state file so a rerun RE-FETCHES cyq (m1): a zero-row cyq fetch from a late endpoint
    is marked 'done' and would otherwise be SKIPPED on rerun, leaving the bump unrecoverable
    without manual state deletion. The state file is scoped by --state-suffix=target_end."""
    sp = OUT_DIR / f"catchup_fund_state_{suffix}.json"
    if not sp.exists():
        return
    try:
        st = json.loads(sp.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    pruned = {k: v for k, v in st.items() if not (k.startswith("D:cyq") or k == "D:cyq_repartition")}
    if len(pruned) != len(st):
        sp.write_text(json.dumps(pruned, ensure_ascii=False, indent=1), encoding="utf-8")
        logger.warning("pruned %d Stage-D cyq resume keys from %s so a rerun refetches cyq_perf",
                       len(st) - len(pruned), sp.name)


# Endpoint-readiness contract (M1/B2). Existence != completeness — an empty/partial per-day file
# must not authorize a formal calendar_end. Two tiers, because coverage-lag differs:
#   - DAILY-FRESH (daily OHLCV, moneyflow, stk_limit): refreshed same-day, so they exist for a
#     candidate target_end BEFORE the monthly catch-up -> they GATE target_end on ROW COUNT.
#   - LAGGING (cyq_perf, per-symbol Stage-D fetch): brought current by the monthly catch-up
#     ITSELF, so a pre-catch-up existence check is meaningless -> verified POST-catch-up
#     (assert_endpoints_complete). Confirmed live: cyq_perf lagged 07-01 while daily/moneyflow/
#     stk_limit were current to 07-03.
#   - report_rc: a window-anchored year-file; completeness = the Stage-E halo fetch failing closed
#     on an all-zero replay (not a per-day file).
#   - northbound (hk_hold): inherently partial + declining coverage -> NOT a hard gate.
READINESS_DAILY_FRESH = {"moneyflow": "market/moneyflow", "stk_limit": "market/stk_limit"}
READINESS_POSTCATCHUP = {"cyq_perf": "market/cyq_perf"}
MIN_ENDPOINT_ROWS = 3000  # cheap empty/corruption guard ONLY — completeness is the coverage ratio
# Per-endpoint completeness = |endpoint ∩ COMPLETE daily universe| / |daily| >= floor. Floors from a
# measured COMPLETE day (2026-06-30): moneyflow 0.94 (low-liquidity names lack flow) / stk_limit
# 1.00 / cyq_perf 1.00. But the denominator MUST be a *proven-complete* daily — otherwise a partial
# daily lets every endpoint cover that same partial universe at 100% (GPT B1).
ENDPOINT_COVERAGE_FLOOR = {"moneyflow": 0.90, "stk_limit": 0.95, "cyq_perf": 0.95}
# Daily universe count is stable day-to-day (~5510, <0.3% variation), so a PARTIAL daily above the
# absolute floor is caught by comparing to the median of recent complete sessions.
DAILY_BASELINE_FLOOR = 0.98
DAILY_BASELINE_WINDOW = 10


def _endpoint_rows(sub: str, ep: str, date: str) -> int:
    """O(1) parquet row count (footer metadata) for a per-day endpoint file; 0 if absent."""
    import pyarrow.parquet as pq
    f = PROJECT_ROOT / "data" / sub / date[:4] / f"{ep}_{date}.parquet"
    if not f.exists():
        return 0
    try:
        return pq.ParquetFile(f).metadata.num_rows
    except Exception:  # noqa: BLE001 — a corrupt/half-written file reads as 0 rows (not complete)
        return 0


def _read_codes_for_trade_date(sub: str, ep: str, date: str) -> tuple[set[str], dict]:
    """ts_codes whose row's trade_date == date, plus diagnostics. date_ok proves the file is NOT a
    stale/mispartitioned file carrying a different trade_date (GPT B1 second form)."""
    f = PROJECT_ROOT / "data" / sub / date[:4] / f"{ep}_{date}.parquet"
    if not f.exists():
        return set(), {"rows": 0, "date_ok": False, "trade_dates": [], "reason": "missing"}
    try:
        df = pd.read_parquet(f, columns=["ts_code", "trade_date"])
    except Exception:  # noqa: BLE001 — unreadable or no trade_date column = not provably complete
        return set(), {"rows": 0, "date_ok": False, "trade_dates": [], "reason": "unreadable/no trade_date"}
    td = df["trade_date"].astype(str).str.replace("-", "", regex=False)
    trade_dates = set(td.unique())
    codes = {str(x).upper().strip() for x in df.loc[td == date, "ts_code"].dropna()}
    return codes, {"rows": int(len(df)), "date_ok": trade_dates == {date},
                   "trade_dates": sorted(trade_dates)[:5]}


def _daily_row_count(date: str) -> int:
    return _endpoint_rows("market/daily", "daily", date)


def _daily_universe(date: str) -> tuple[set[str], bool, dict]:
    """The COMPLETE daily universe for `date` — the denominator every endpoint coverage is measured
    against. daily is a completeness OBJECT, not just a count: (1) file trade_date == date; (2) code
    count >= the absolute floor; (3) code count >= DAILY_BASELINE_FLOOR x the median of the last
    DAILY_BASELINE_WINDOW complete sessions (catches a partial daily still above the absolute floor
    — the GPT B1 residual). Returns (codes, ok, evidence)."""
    codes, diag = _read_codes_for_trade_date("market/daily", "daily", date)
    ev: dict = {"daily_codes": len(codes), "daily_rows": diag["rows"], "daily_date_ok": diag["date_ok"]}
    if not diag["date_ok"]:
        ev["reason"] = f"daily file trade_date mismatch: {diag.get('trade_dates')}"
        return codes, False, ev
    if len(codes) < MIN_PLAUSIBLE_DAILY_ROWS:
        ev["reason"] = f"daily codes {len(codes)} < {MIN_PLAUSIBLE_DAILY_ROWS}"
        return codes, False, ev
    # baseline uses the SAME trade_date-filtered code count as the target (not the raw footer row
    # count) so the ratio is apples-to-apples; only date-correct prior sessions above the floor count.
    prior = [d for d in _open_trading_days(upto=date) if d < date][-DAILY_BASELINE_WINDOW:]
    base = []
    for d in prior:
        pc, pdiag = _read_codes_for_trade_date("market/daily", "daily", d)
        if pdiag["date_ok"] and len(pc) >= MIN_PLAUSIBLE_DAILY_ROWS:
            base.append(len(pc))
    if base:
        import statistics
        baseline = statistics.median(base)
        ratio = len(codes) / max(1, baseline)
        ev["daily_baseline_median"] = baseline
        ev["daily_baseline_ratio"] = round(ratio, 4)
        if ratio < DAILY_BASELINE_FLOOR:
            ev["reason"] = (f"daily universe PARTIAL: {len(codes)} vs baseline {baseline} "
                            f"(ratio {ratio:.4f} < {DAILY_BASELINE_FLOOR})")
            return codes, False, ev
    return codes, True, ev


def _norm_codes(s) -> set[str]:
    """Dotted-upper code form (000001.SZ) matching _read_codes_for_trade_date — NO dot->underscore."""
    return {str(x).upper().strip() for x in s.dropna()}


def _suspended_full_day(date: str) -> tuple[set[str], set[str], bool, dict]:
    """(full_day_suspended, resumed, ok, ev) from suspend_d(date). Verifies trade_date == date
    (stale-file guard, GPT B1-b). A suspension only EXCUSES an absent daily row when it is FULL-DAY
    (no price) — an INTRADAY halt (suspend_timing like '09:30-10:00') still trades, so treating
    every S as full-day would wrongly excuse an intraday-halted name missing from a partial daily.
    Full-day = suspend_type S with an empty/None suspend_timing. If the stored file lacks the
    suspend_timing column (legacy schema — a FRESH catch-up fetch stores it, since fetch_suspend_d
    returns Tushare's default fields and insert_market_data keeps all columns), fall back to
    treating every S as full-day with a warning."""
    susp_f = PROJECT_ROOT / "data" / "market" / "suspend_d" / date[:4] / f"suspend_d_{date}.parquet"
    if not susp_f.exists():
        return set(), set(), False, {"reason": f"suspend_d for {date} absent - cannot prove completeness"}
    sd = pd.read_parquet(susp_f)
    missing_cols = {"ts_code", "trade_date", "suspend_type"} - set(sd.columns)
    if missing_cols:
        return set(), set(), False, {"reason": f"suspend_d {date} missing required columns {sorted(missing_cols)}"}
    if len(sd):  # an empty file (no suspensions that day) is legitimate; skip the date check
        td = set(sd["trade_date"].astype(str).str.replace("-", "", regex=False).dropna().unique())
        if td != {date}:
            return set(), set(), False, {"reason": f"suspend_d {date} trade_date mismatch: {sorted(td)[:5]}"}
    stype = sd["suspend_type"].astype(str).str.upper()
    resumed = _norm_codes(sd.loc[stype == "R", "ts_code"])
    if "suspend_timing" not in sd.columns:
        # legacy no-timing: an S row is AMBIGUOUS (full-day vs intraday). Treating it as full-day
        # could wrongly excuse an intraday-halted name missing from a partial daily -> FAIL CLOSED
        # when any S rows exist (a fresh catch-up fetch stores suspend_timing; re-fetch this date).
        if (stype == "S").any():
            return set(), set(), False, {
                "reason": (f"suspend_d {date} has S rows but NO suspend_timing - cannot distinguish "
                           "full-day suspension from intraday halt; re-fetch suspend_d for this date")}
        return set(), resumed, True, {"suspend_timing_present": False, "full_day_suspended": 0}
    # FULL-DAY only: an S with empty/None suspend_timing has no price all day (excuses absence); an
    # intraday halt (timing like 09:30-10:00) still trades and must NOT excuse an absent daily row.
    timing = sd["suspend_timing"].astype("string").fillna("").str.strip().str.upper()
    full = (stype == "S") & timing.isin(["", "NONE", "NAN", "NULL"])
    return (_norm_codes(sd.loc[full, "ts_code"]), resumed, True,
            {"suspend_timing_present": True, "full_day_suspended": int(full.sum())})


def _daily_set_continuity_from_prior(date: str, prior_date: str, prior_codes: set[str],
                                     daily_codes: set[str], sb) -> tuple[bool, dict]:
    """SET-LEVEL completeness step against an EXPLICIT VERIFIED prior (GPT B1-a — never an
    unverified read). A name that TRADED on prior_date (so it was listed and NOT suspended then)
    must trade today UNLESS it delisted (stock_basic.delist_date <= date) or NEWLY full-day
    suspended (suspend_d S event today). Because a prior-session name was trading, the ONLY PIT
    reasons it can vanish are delist or a same-day full-day suspension — no historical
    suspension-state reconstruction is needed. Any name vanishing without such a reason is a
    survivorship hole. Fail-CLOSED. `sb` is stock_basic (read once by the caller)."""
    delisted = _norm_codes(sb.loc[sb["delist_date"].notna() & (sb["delist_date"].astype(str) <= date), "ts_code"])
    ipo_today = _norm_codes(sb.loc[sb["list_date"].astype(str) == date, "ts_code"])
    suspended, resumed, sok, sev = _suspended_full_day(date)
    ev: dict = {"prior_date": prior_date, "prior_codes": len(prior_codes), **sev}
    if not sok:
        ev["reason"] = sev["reason"]
        return False, ev
    expected = (prior_codes - delisted - suspended) | (ipo_today - suspended)
    missing = sorted(expected - daily_codes)
    unexpected = sorted(daily_codes - prior_codes - ipo_today - resumed)
    ev.update({"expected": len(expected), "delisted_by_date": len(delisted),
               "ipo_today": len(ipo_today), "missing": len(missing), "unexpected": len(unexpected)})
    if missing:
        ev["reason"] = (f"daily universe incomplete vs {prior_date}: {len(missing)} expected names "
                        f"absent without a delist/suspend reason; examples={missing[:10]}")
        return False, ev
    if unexpected:
        logger.warning("daily %s: %d names appeared vs %s w/o IPO/resume evidence: %s",
                       date, len(unexpected), prior_date, unexpected[:10])
    return True, ev


def assert_endpoints_complete_range(parent_end: str, target_end: str) -> tuple[bool, dict]:
    """POST-catch-up FORMAL completeness gate over (parent_end, target_end] (GPT B1-a). Chains the
    set-level continuity proof from the VERIFIED published-parent anchor forward through EVERY new
    trading day — so a survivorship hole cannot be inherited from an unverified prior daily, and no
    intermediate new day escapes the proof. Each day also re-proves daily (trade_date + baseline) +
    daily-fresh coverage; cyq_perf coverage is checked at target_end. Fail-CLOSED throughout."""
    ev: dict = {"parent_end": parent_end, "target_end": target_end, "checked_days": []}
    # anchor: the parent's calendar_end daily is the trusted reference (already published+audited);
    # require it date-correct + above floor before chaining from it.
    prior_codes, pdiag = _read_codes_for_trade_date("market/daily", "daily", parent_end)
    if not pdiag["date_ok"] or len(prior_codes) < MIN_PLAUSIBLE_DAILY_ROWS:
        ev["reason"] = f"parent_end {parent_end} is not a verified anchor: {pdiag}"
        return False, ev
    sb = pd.read_parquet(PROJECT_ROOT / "data" / "reference" / "stock_basic.parquet",
                         columns=["ts_code", "list_date", "delist_date"])
    prior_date = parent_end
    days = [d for d in _open_trading_days(upto=target_end) if parent_end < d <= target_end]
    for d in days:
        daily_codes, daily_ok, dev = _daily_universe(d)
        if not daily_ok:
            ev["reason"] = f"daily_universe failed for {d}: {dev.get('reason')}"
            ev["day"] = d
            return False, ev
        cok, cev = _daily_set_continuity_from_prior(d, prior_date, prior_codes, daily_codes, sb)
        ev["checked_days"].append({"date": d, "continuity": cev})
        if not cok:
            ev["reason"] = cev.get("reason")
            ev["day"] = d
            return False, ev
        if not _coverage_gate(d, READINESS_DAILY_FRESH, ev.setdefault("coverage_by_day", {}).setdefault(d, {}), daily_codes):
            ev["reason"] = f"daily-fresh endpoint coverage failed for {d}: {ev['coverage_by_day'][d].get('reason')}"
            ev["day"] = d
            return False, ev
        # cyq_perf (post-catch-up lagging endpoint) per NEW day (GPT M1) — not target_end only; the
        # catch-up backfills cyq over the whole gap, so an intermediate partial day must also fail.
        if not _coverage_gate(d, READINESS_POSTCATCHUP, ev.setdefault("cyq_by_day", {}).setdefault(d, {}), daily_codes):
            ev["reason"] = f"cyq_perf coverage failed for {d}: {ev['cyq_by_day'][d].get('reason')}"
            ev["day"] = d
            return False, ev
        prior_codes, prior_date = daily_codes, d
    return True, ev


def _coverage_gate(date: str, endpoints: dict, ev: dict, daily_codes: set[str]) -> bool:
    """True iff every endpoint file is date-correct AND covers the PROVEN-complete daily universe
    above its floor. Mutates ev with per-endpoint diagnostics + a reason on failure."""
    cov = ev.setdefault("endpoint_coverage", {})
    for ep, sub in endpoints.items():
        codes, diag = _read_codes_for_trade_date(sub, ep, date)
        ratio = len(codes & daily_codes) / max(1, len(daily_codes))
        cov[ep] = {"rows": diag["rows"], "codes": len(codes), "coverage": round(ratio, 4),
                   "date_ok": diag["date_ok"], "missing_examples": sorted(daily_codes - codes)[:8]}
        floor = ENDPOINT_COVERAGE_FLOOR.get(ep, 0.95)
        if not diag["date_ok"] or ratio < floor or diag["rows"] < MIN_ENDPOINT_ROWS:
            ev["reason"] = (f"{ep} incomplete: coverage {cov[ep]['coverage']} < {floor} "
                            f"(rows {diag['rows']}, date_ok {diag['date_ok']})")
            return False
    return True


def endpoint_ready(date: str) -> tuple[bool, dict]:
    """PRE-catch-up target_end gate: the daily universe is PROVEN complete (date-correct + not a
    partial vs the recent baseline) AND every DAILY-FRESH endpoint (moneyflow, stk_limit) covers it
    above floor. Lagging endpoints (cyq_perf) + the report_rc halo are verified POST-catch-up."""
    daily_codes, daily_ok, ev = _daily_universe(date)
    if not daily_ok:
        return False, ev
    return _coverage_gate(date, READINESS_DAILY_FRESH, ev, daily_codes), ev


def assert_endpoints_complete(parent_end: str, target_end: str) -> tuple[bool, dict]:
    """POST-catch-up FORMAL completeness gate: the chained set-level proof over (parent_end,
    target_end] from the verified parent anchor (GPT B1-a) — daily universe + set-continuity +
    daily-fresh coverage per new day, cyq_perf at target_end. Fail-closed. The rolling baseline in
    _daily_universe is only a cheap early detector; THIS is the gate before a policy is minted."""
    return assert_endpoints_complete_range(parent_end, target_end)


# ── phases ───────────────────────────────────────────────────────────────────
def phase_plan(args) -> dict:
    if not _assert_standard_layout():
        raise SystemExit(2)
    parent_build, parent_policy = live_provider_ids()
    target_end, evidence = determine_target_end(now_cst(), probe_ready=None)
    plan = {
        "mode": "plan", "generated": datetime.now().isoformat(timespec="seconds"),
        "parent_build_id": parent_build, "parent_policy_id": parent_policy,
        "target_end": target_end, "target_end_evidence": evidence,
        "spent_oos_end": SPENT_OOS_END, "fresh_holdout_start": FRESH_HOLDOUT_START,
        "next_policy_id": f"frozen_{target_end}_thaw_step{next_thaw_step_number()}" if target_end else None,
        "disk_free_gb": _disk_free_gb(),
        "catchup_range": f"{parent_policy} end +1 .. {target_end}",
        "notes": ["spent_oos_end frozen (D3); fresh window grows.",
                  "execute (default) runs catch-up->rebuild->audits->dry-run report, STOPS before publish.",
                  "publish is a §13 human-gated action: --publish-approved after reviewing the report."],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "monthly_bump_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(plan, ensure_ascii=False, indent=1))
    return plan


DRYRUN_REPORT_PATH = OUT_DIR / "monthly_bump_dryrun_report.json"
FRESH_AUDIT_PATH = OUT_DIR / "fresh_window_survivorship_audit.json"
PUBLISH_RECORD_PATH = OUT_DIR / "publish_record.json"
TRANSACTION_JOURNAL_PATH = OUT_DIR / "publish_transaction_journal.json"
RAW_MANIFEST_PATH = OUT_DIR / "raw_input_manifest.json"
# the SHARED intent journal / per-transaction records live in the store's transaction
# dir (_tx_dir(), adjacent to the provider) — NOT in this checkout's workspace.


def _report_rc_halo_start(target_end: str) -> str:
    """report_rc replay must cover a pre-boundary halo (Phase 5-A contract): a forecast
    dated up to REPORT_RC_ACTIVE_TTL_OPEN_DAYS before the boundary can carry INTO the fresh
    window, and a create_time gap up to REPORT_RC_BACKFILL_GAP_DAYS matters. Replay from
    fresh_holdout_start - (TTL open days + backfill guard) through target_end."""
    from data_infra.pit_backend import REPORT_RC_ACTIVE_TTL_OPEN_DAYS, REPORT_RC_BACKFILL_GAP_DAYS
    opens = _open_trading_days(upto=target_end)
    fresh = FRESH_HOLDOUT_START.replace("-", "")
    pos = next((i for i, d in enumerate(opens) if d >= fresh), len(opens))
    halo_pos = max(0, pos - REPORT_RC_ACTIVE_TTL_OPEN_DAYS)
    start = opens[halo_pos] if opens else fresh
    # subtract the backfill guard in CALENDAR days as a conservative extra margin
    return (pd.Timestamp(start) - pd.Timedelta(days=REPORT_RC_BACKFILL_GAP_DAYS)).strftime("%Y%m%d")


def phase_execute(args) -> int:
    """Catch up raw -> new policy -> full staged rebuild -> audits -> dry-run report (multi-hour;
    STOPS before publish). The catch-up subprocesses each SELF-acquire raw_maintenance_lock; there is
    NO parent env-barrier (that was a forgeable + orphan-prone bypass — a boolean env var isn't tied to
    the kernel-lock holder, so a forged value or an orphaned inheriting child could enter raw
    maintenance while a real writer holds the lock; GPT REWORK-4 Blocker 1). The build + input manifest
    + audits then run UNDER a single IN-PROCESS raw_maintenance_lock (no lock-acquiring subprocess is
    nested inside it), so the raw cut the formal build reads and attests cannot be mutated mid-build."""
    return _phase_execute_impl(args)


def _phase_execute_impl(args) -> int:
    """Pre-lock leg: parent-policy guard -> target_end -> disk floor -> catch-up (each subprocess
    self-locks). Then hands off to _build_under_lock."""
    import subprocess

    if not _assert_standard_layout():
        return 2
    parent_build, parent_policy = live_provider_ids()

    # M1: the parent policy MUST still be in the Phase-5 frozen regime (spent_oos_end /
    # fresh_holdout_start match the constants) before we mint a child — a Phase-6 release
    # policy must not be silently regressed. Route through the typed loader so the YAML-parsed
    # ISO dates are normalized to strings (a bare yaml.safe_load yields datetime.date objects,
    # which would false-fail a string compare) and the loader's own validation runs.
    from src.research_orchestrator.calendar_policy import load_calendar_policy
    parent_pol = load_calendar_policy(parent_policy)
    if parent_pol.spent_oos_end != SPENT_OOS_END:
        logger.error("parent policy spent_oos_end %s != Phase-5 constant %s — refusing",
                     parent_pol.spent_oos_end, SPENT_OOS_END)
        return 2
    if parent_pol.fresh_holdout_start != FRESH_HOLDOUT_START:
        logger.error("parent policy fresh_holdout_start %s != Phase-5 constant %s — refusing",
                     parent_pol.fresh_holdout_start, FRESH_HOLDOUT_START)
        return 2
    parent_end = parent_pol.calendar_end_date.replace("-", "")

    # Approvals compare-and-swap PRECONDITION (Phase 5-B): surface a stale/out-of-band
    # approval binding BEFORE the multi-hour build, not at publish time. The publish
    # transaction re-checks the same condition under its locks.
    ok_bind, bind_msg = _approvals_all_bound_to(parent_build, parent_policy)
    if not ok_bind:
        logger.error("approval-binding precondition FAILED: %s — commit/repair the approval "
                     "rebind to the live parent before bumping.", bind_msg)
        return 2
    logger.info("approval-binding precondition OK: %s", bind_msg)

    # B2: target_end via the multi-endpoint readiness contract; validate any override.
    ready_target, ev = determine_target_end(now_cst(), probe_ready=endpoint_ready)
    if args.target_end:
        ok, ov_ev = endpoint_ready(args.target_end)
        if not ok or (ready_target is not None and args.target_end > ready_target):
            logger.error("--target-end %s is not endpoint-complete or later than the complete "
                         "target_end %s; evidence=%s / override=%s", args.target_end, ready_target, ev, ov_ev)
            return 2
        target_end = args.target_end
    else:
        target_end = ready_target
    if target_end is None:
        logger.error("no endpoint-complete trading day found for target_end; evidence=%s", ev)
        return 2
    logger.info("target_end=%s (parent build=%s / policy=%s)", target_end, parent_build, parent_policy)

    if _disk_free_gb() < 400:
        logger.error("disk free %dGB < 400GB floor — prune referenced-safe backups first", _disk_free_gb())
        return 2

    # 1. catch up raw (the two proven drivers; strictly serial, single fetcher). B3: the
    # fundamentals catch-up is bump-scoped (--state-suffix) and report_rc replays the
    # pre-boundary halo, not just parent_end+1 (the Phase-5-A availability contract).
    catchup_start = _open_trading_days()
    lo = next((d for d in catchup_start if d > parent_end and d <= target_end), None)
    if lo is not None:
        py = str(PROJECT_ROOT / "venv" / "Scripts" / "python.exe")
        halo = _report_rc_halo_start(target_end)
        logger.info("catch-up raw %s..%s (report_rc halo from %s)", lo, target_end, halo)
        subprocess.run([py, str(PROJECT_ROOT / "workspace" / "scripts" / "catchup_daily_range.py"),
                        "--start", lo, "--end", target_end], check=True)
        subprocess.run([py, str(PROJECT_ROOT / "workspace" / "scripts" / "catchup_fundamentals_range.py"),
                        "--start", lo, "--end", target_end,
                        "--report-rc-start", halo, "--report-rc-end", target_end,
                        "--state-suffix", target_end], check=True)
    else:
        logger.info("raw already current through %s", target_end)

    # catch-ups (above) have self-locked + returned. The build + audits now run under ONE in-process
    # raw_maintenance_lock so no daily/manual writer can mutate the raw cut the formal build reads.
    return _build_under_lock(args, parent_build, parent_policy, parent_end, target_end)


def _build_under_lock(args, parent_build, parent_policy, parent_end, target_end) -> int:
    from data_infra.tushare_lock import raw_maintenance_lock
    with raw_maintenance_lock():  # real kernel lock; the in-process build below re-acquires nothing
        return _build_impl(args, parent_build, parent_policy, parent_end, target_end)


def _build_impl(args, parent_build, parent_policy, parent_end, target_end) -> int:
    """UNDER raw_maintenance_lock: completeness gate -> new policy YAML -> full staged rebuild + raw
    input manifest -> frozen-prefix + fresh-window audits -> dry-run report. STOPS before publish."""
    import subprocess

    # 1b. POST-catch-up completeness gate (B1): the catch-up just fetched the lagging endpoints
    # (cyq_perf) through target_end — VERIFY the FINAL target_end data is complete across all
    # required endpoints (row counts, not existence) before minting a policy / building a formal
    # provider. Fail-closed: a partial cyq_perf/moneyflow/stk_limit must never enter a formal
    # calendar_end. report_rc halo completeness is enforced inside the catch-up (Stage E fails
    # closed on an all-zero replay).
    ok_complete, complete_ev = assert_endpoints_complete(parent_end, target_end)
    if not ok_complete:
        _prune_cyq_state(target_end)  # m1: let a rerun refetch cyq (don't leave zero-row 'done')
        logger.error("endpoint completeness FAILED over (%s, %s]: %s — bump BLOCKED (vendor may be "
                     "late / a survivorship hole; re-run when complete or pass an earlier "
                     "--target-end).", parent_end, target_end, complete_ev.get("reason", complete_ev))
        return 2
    logger.info("endpoint completeness OK over (%s, %s]: %d days chained-verified",
                parent_end, target_end, len(complete_ev.get("checked_days", [])))

    # 2. new policy YAML (append-only; spent_oos_end frozen).
    policy_id, policy_path = generate_thaw_policy(target_end, parent_build, write=True)

    # 3. full rebuild (staged, NOT published).
    from data_infra.pit_backend import build_qlib_backend
    build_id = f"thaw_{target_end}_{datetime.now().strftime('%H%M%S')}"
    logger.info("full rebuild build_id=%s (staged, no publish)", build_id)
    result = build_qlib_backend(mode="all", stage="full", build_id=build_id, publish=False,
                                calendar_policy_id=policy_id)
    staged_provider = Path(result.provider_dir)

    # 4a. frozen-prefix audit (delegates to the proven audit script against the NEW staged
    # tree via THAW_STAGED_PROVIDER). Its exit code GATES — a frozen-prefix violation blocks
    # the bump (do NOT ignore it: it protects pre-parent-end replay byte-identity). Monthly
    # mode is STRICT (THAW_MONTHLY_MODE): the first-thaw provenance exceptions (indicator
    # refetch SHA drift, sidecar suspension-healing) are one-time and already baked into the
    # SETTLED parent, so a recurring bump must see a byte-identical frozen prefix + identical
    # sidecars — any drift is a real regression, not an exception.
    logger.info("frozen-prefix audit (staged=%s, monthly strict) ...", staged_provider)
    fp_artifact = OUT_DIR / "frozen_prefix_audit.json"
    audit_env = {**os.environ, "THAW_STAGED_PROVIDER": str(staged_provider), "THAW_MONTHLY_MODE": "1"}
    fp = subprocess.run([str(PROJECT_ROOT / "venv" / "Scripts" / "python.exe"),
                         str(PROJECT_ROOT / "workspace" / "scripts" / "audit_thaw_frozen_prefix.py")],
                        env=audit_env)
    if fp.returncode != 0:
        logger.error("FROZEN-PREFIX AUDIT FAILED (exit %d) — bump BLOCKED. Review the audit report "
                     "+ register any legitimate provenance change as a typed exception.", fp.returncode)
        return 1
    # B1 hard guarantee (GPT #1 residual risk): prove the audit actually ran against THIS
    # staged tree, not a stale default — a passing audit against the wrong provider is worse
    # than a failing one. The artifact records the audited `staged` path.
    if not fp_artifact.exists():
        logger.error("frozen-prefix audit produced no artifact at %s — bump BLOCKED.", fp_artifact)
        return 1
    audited = json.loads(fp_artifact.read_text(encoding="utf-8")).get("staged", "")
    if Path(audited).resolve() != staged_provider.resolve():
        logger.error("frozen-prefix audit ran against %s, NOT the staged build %s — bump BLOCKED "
                     "(THAW_STAGED_PROVIDER plumbing failure).", audited, staged_provider)
        return 1
    # 4b. fresh-window survivorship audit (M2, no blanket exceptions).
    logger.info("fresh-window survivorship audit ...")
    fresh = fresh_window_survivorship_audit(staged_provider, FRESH_HOLDOUT_START, target_end)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    FRESH_AUDIT_PATH.write_text(json.dumps(fresh, ensure_ascii=False, indent=1), encoding="utf-8")
    if not fresh["ok"]:
        logger.error("FRESH-WINDOW SURVIVORSHIP AUDIT FAILED (%d violations) — bump BLOCKED. See %s",
                     len(fresh["violations"]), FRESH_AUDIT_PATH)
        return 1

    # 4c. recurring approved-exception GATE (M2): a frozen-prefix exception type recurring
    # two bumps in a row must become a permanent migration (note + tests), not a silent
    # re-approval by count. Block unless the operator explicitly acknowledges the migration.
    recurring = ExceptionRegistry(OUT_DIR / "bump_exceptions.json").recurring_types()
    if recurring and not args.allow_migration_exception:
        logger.error("recurring frozen-prefix exception types require a permanent migration "
                     "(note + tests), not a re-approval by count: %s. Re-run with "
                     "--allow-migration-exception once migrated.", recurring)
        return 1

    # 4d. full-read-set raw-input manifest (Blocker 3) — computed here UNDER the lock, so it attests the
    # exact cut the staged build just consumed (EVERY DATASET_SPECS file + reference, not a 6-dataset
    # subset). Sidecar carries the per-file hashes; the 256-bit root is recorded in the report, re-verified
    # by the publish transaction under its locks, and bound into the published provider_build.json (B3.2).
    raw_manifest = _full_raw_manifest()
    raw_manifest_json = json.dumps(raw_manifest, ensure_ascii=False, indent=1)
    RAW_MANIFEST_PATH.write_text(raw_manifest_json, encoding="utf-8")
    # GPT re-review Major 2: the fixed-name sidecar is overwritten by the next bump — ALSO
    # persist a per-build copy AND ship one inside the provider's own metadata dir (written
    # BEFORE the content attestation below, so it is part of the attested tree and survives
    # with the published/.bak provider as the audit store of its raw cut).
    (OUT_DIR / f"raw_input_manifest_{build_id}.json").write_text(raw_manifest_json, encoding="utf-8")
    staged_meta = staged_provider / "metadata"
    staged_meta.mkdir(parents=True, exist_ok=True)
    (staged_meta / "raw_input_manifest.json").write_text(raw_manifest_json, encoding="utf-8")
    logger.info("raw-input manifest: %d files (full read set), root=%s",
                raw_manifest["file_count"], raw_manifest["root"])

    # 4e. transaction attestations (Phase 5-B): pin the audit artifacts, the FULL staged
    # tree content, the approvals governance set, the minted policy file, and the source
    # git state at execute time; the publish transaction re-verifies ALL of them under its
    # locks IMMEDIATELY before the swap and refuses on any drift.
    logger.info("staged FULL-CONTENT attestation (every file incl. feature bins) ...")
    staged_att = _staged_content_attestation(staged_provider)
    (OUT_DIR / f"staged_content_manifest_{build_id}.json").write_text(
        json.dumps(staged_att, ensure_ascii=False, indent=1), encoding="utf-8")
    logger.info("staged content root=%s over %d files / %.1f GB",
                staged_att["root"], staged_att["file_count"], staged_att["total_bytes"] / 2**30)
    approvals_att = _approvals_attestation()
    if approvals_att["bound_count"] < 1:
        logger.error("approvals attestation found %d bound YAMLs — a bump must rebind a "
                     "non-empty governance set; refusing.", approvals_att["bound_count"])
        return 1
    git_head, git_dirty = _git_state()

    # 5. dry-run report -> STOP for human sign-off.
    report = {
        "target_end": target_end, "new_policy_id": policy_id, "staged_build_id": build_id,
        "staged_provider_dir": str(staged_provider),
        "parent_build_id": parent_build, "parent_policy_id": parent_policy,
        "spent_oos_end": SPENT_OOS_END, "fresh_holdout_start": FRESH_HOLDOUT_START,
        "disk_free_gb": _disk_free_gb(),
        "frozen_prefix_audit_ok": True, "frozen_prefix_audit_artifact": "frozen_prefix_audit.json",
        "frozen_prefix_audit_sha256": _sha256_file(fp_artifact),
        "fresh_window_audit_ok": fresh["ok"], "fresh_window_audit_artifact": str(FRESH_AUDIT_PATH.name),
        "fresh_window_audit_sha256": _sha256_file(FRESH_AUDIT_PATH),
        "staged_content_root": staged_att["root"],
        "staged_content_file_count": staged_att["file_count"],
        "staged_content_total_bytes": staged_att["total_bytes"],
        "staged_content_manifest_artifact": f"staged_content_manifest_{build_id}.json",
        "approvals_attestation_root": approvals_att["root"],
        "approvals_file_count": approvals_att["file_count"],
        "approvals_bound_count": approvals_att["bound_count"],
        "new_policy_sha256": _sha256_file(policy_path),
        "source_git_commit": git_head,
        "git_dirty_digest": git_dirty,
        "report_rc_replay_halo_start": _report_rc_halo_start(target_end),
        "endpoint_completeness": complete_ev,
        "raw_input_manifest_root": raw_manifest["root"],  # full-content input-cut attestation (M3)
        "raw_input_manifest_algo": raw_manifest["algo"],
        "raw_input_manifest_file_count": raw_manifest["file_count"],
        "raw_input_manifest_artifact": str(RAW_MANIFEST_PATH.name),
        "recurring_exception_types": recurring,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "next": "review this report + both audit artifacts, then --publish-approved --i-reviewed-the-dryrun",
    }
    DRYRUN_REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    logger.info("DRY-RUN COMPLETE. Review %s + both audits, then --publish-approved.", DRYRUN_REPORT_PATH)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


def phase_publish(args) -> int:
    """§13 human-gated ATOMIC publish transaction (Phase 5-B B3.3-5: verification and the
    swap are inseparable — "a manual interval after verification cannot be the integrity
    boundary", GPT REWORK-5). Under raw_maintenance_lock + provider_publish_lock, in one
    scope with nothing released in between:

      verify: parent compare-and-swap (live build/policy == report parent) + full-readset
              raw-input manifest re-hash + audit-artifact hashes + staged attestation +
              new-policy re-validation + approvals compare-and-swap
      swap:   StagedQlibBackendBuilder.publish() — the proven safe staged-first 3-rename
              swap (single-failure self-rollback), emitting provider_build.json WITH
              raw_input_manifest_root + parent_provider_build_id (B3.2)
      bind:   re-load + verify the live manifest, byte-preserving rebind of every bound
              approval YAML (two-phase, restore-on-failure), 0-drift assertion, committed
              rebind record, publish record

    then post-publish QA (run_daily_qa) OUTSIDE the locks. Any post-swap failure restores
    the approval bytes AND rolls the swap back to the parent live provider.

    Exit codes: 0 = published + rebound + QA pass + READY-gate certified; 2 = refused
    pre-swap (nothing mutated); 4 = post-swap failure, fully rolled back (verified); 5 =
    CRITICAL inconsistent/suspect state (see the journals for the exact recovery move);
    6 = published + consistent, but post-publish QA failed (quarantined; --finalize-qa);
    7 = this worker's QA attempt was superseded by a newer one (nothing changed)."""
    if not args.i_reviewed_the_dryrun:
        logger.error("publish requires --i-reviewed-the-dryrun (you must have read %s). Refusing.",
                     DRYRUN_REPORT_PATH)
        return 2
    if not _assert_standard_layout():
        return 2
    if not DRYRUN_REPORT_PATH.exists():
        logger.error("no dry-run report at %s — run the execute phase first.", DRYRUN_REPORT_PATH)
        return 2
    rep = json.loads(DRYRUN_REPORT_PATH.read_text(encoding="utf-8"))

    # The transaction refuses a pre-Phase-5-B report (no attestation fields): the whole
    # point is that publish verifies EXACTLY what execute attested.
    required_keys = ("target_end", "new_policy_id", "staged_build_id", "staged_provider_dir",
                     "parent_build_id", "parent_policy_id", "raw_input_manifest_root",
                     "frozen_prefix_audit_sha256", "fresh_window_audit_sha256",
                     "staged_content_root", "approvals_attestation_root",
                     "new_policy_sha256", "source_git_commit", "git_dirty_digest")
    missing = [k for k in required_keys if not rep.get(k)]
    if missing:
        logger.error("dry-run report lacks the Phase-5-B transaction attestations %s — re-run "
                     "--execute with the current driver. Refusing publish.", missing)
        return 2
    if not RAW_MANIFEST_PATH.exists():
        logger.error("no raw-input manifest sidecar at %s — re-run --execute. Refusing publish.", RAW_MANIFEST_PATH)
        return 2
    manifest = json.loads(RAW_MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("root") != rep["raw_input_manifest_root"]:
        logger.error("manifest sidecar root %s != report root %s — inconsistent artifacts; refusing.",
                     manifest.get("root"), rep["raw_input_manifest_root"])
        return 2

    from data_infra.tushare_lock import provider_publish_lock, raw_maintenance_lock
    from src.research_orchestrator.calendar_policy import CalendarPolicyError, load_calendar_policy

    journal: dict = {"transaction": "monthly_provider_publish",
                     "staged_build_id": rep["staged_build_id"],
                     "new_policy_id": rep["new_policy_id"],
                     "parent_build_id": rep["parent_build_id"], "steps": []}

    def j(step: str, status: str, **info) -> None:
        journal["steps"].append({"step": step, "status": status,
                                 "ts_cst": now_cst().isoformat(timespec="seconds"), **info})
        _write_journal(journal)

    # LOCK ORDER (fixed everywhere): raw_maintenance_lock FIRST, then provider_publish_lock
    # (keyed by the canonical live provider dir — re-review #4 P0).
    with raw_maintenance_lock(), provider_publish_lock(qlib_dir=_live_paths().qlib_dir):
        # ── VERIFY: every attestation re-checked here, IMMEDIATELY before the swap, with
        # no lock release in between (the verify↔swap inseparability is the transaction).
        # re-review #3/#4: refuse over an UNRESOLVED prior transaction (the intent journal
        # is SHARED — it lives in the store's transaction dir, so a hard crash in ANOTHER
        # checkout blocks this one too) or a live provider whose marker is not settled.
        intent = _read_intent()
        if intent.get("status") in ("swapping", "rollback_incomplete", "failed_state_unknown",
                                    "restore_interrupted"):
            logger.error("UNRESOLVED prior transaction %s (status=%s) — resolve it first "
                         "(--finalize-qa / --restore-parent / manual per %s). Refusing.",
                         intent.get("transaction_id"), intent.get("status"), _intent_path())
            j("verify", "refused", reason="unresolved_intent")
            return 2
        live_marker = _read_publish_state(_live_paths().qlib_dir)
        if live_marker and live_marker.get("state") != "ready":
            logger.error("live provider publish-state is %r — finalize (--finalize-qa) or "
                         "restore (--restore-parent) before a new publish. Refusing.",
                         live_marker.get("state"))
            j("verify", "refused", reason=f"live_state_{live_marker.get('state')}")
            return 2
        live_build, live_policy = live_provider_ids()
        if live_build != rep["parent_build_id"] or live_policy != rep["parent_policy_id"]:
            logger.error("PARENT DRIFT — live provider is build=%s/policy=%s but the reviewed report "
                         "was computed against parent build=%s/policy=%s. Re-run --execute. Refusing.",
                         live_build, live_policy, rep["parent_build_id"], rep["parent_policy_id"])
            j("verify", "refused", reason="parent_drift")
            return 2
        for artifact, key in (("frozen_prefix_audit.json", "frozen_prefix_audit_sha256"),
                              (FRESH_AUDIT_PATH.name, "fresh_window_audit_sha256")):
            p = OUT_DIR / artifact
            if not p.is_file() or _sha256_file(p) != rep[key]:
                logger.error("AUDIT-ARTIFACT DRIFT — %s missing or hash != the reviewed report's %s. "
                             "Re-run --execute. Refusing.", p, key)
                j("verify", "refused", reason=f"audit_artifact_drift:{artifact}")
                return 2
        staged_dir = Path(rep["staged_provider_dir"])
        if not staged_dir.is_dir():
            logger.error("staged provider missing at %s — refusing.", staged_dir)
            j("verify", "refused", reason="staged_missing")
            return 2
        # Source-tree binding (Major 2): the code publishing must be the code that built.
        git_head, git_dirty = _git_state()
        if git_head != rep["source_git_commit"] or git_dirty != rep["git_dirty_digest"]:
            logger.error("SOURCE DRIFT — git HEAD/dirty now (%s/%s) != at execute (%s/%s). The "
                         "manifest would misattribute the build; re-run --execute. Refusing.",
                         git_head, git_dirty, rep["source_git_commit"], rep["git_dirty_digest"])
            j("verify", "refused", reason="git_state_drift")
            return 2
        try:
            pol = load_calendar_policy(rep["new_policy_id"], root=POLICY_DIR)
        except CalendarPolicyError as exc:
            logger.error("new policy %s no longer loads: %s — refusing.", rep["new_policy_id"], exc)
            j("verify", "refused", reason="policy_load_failed")
            return 2
        policy_file = POLICY_DIR / f"{rep['new_policy_id']}.yaml"
        if _sha256_file(policy_file) != rep["new_policy_sha256"]:
            logger.error("POLICY FILE DRIFT — %s hash != the minted policy the report pinned. "
                         "Refusing.", policy_file)
            j("verify", "refused", reason="policy_file_drift")
            return 2
        end_iso = f"{rep['target_end'][:4]}-{rep['target_end'][4:6]}-{rep['target_end'][6:]}"
        if (pol.spent_oos_end != SPENT_OOS_END or pol.fresh_holdout_start != FRESH_HOLDOUT_START
                or not pol.frozen or pol.calendar_end_date != end_iso
                or pol.require_raw_input_attestation is not True):
            logger.error("new policy %s drifted from the minted contract (spent=%s fresh=%s frozen=%s "
                         "end=%s require_raw_input_attestation=%s) — refusing.", pol.policy_id,
                         pol.spent_oos_end, pol.fresh_holdout_start, pol.frozen,
                         pol.calendar_end_date, pol.require_raw_input_attestation)
            j("verify", "refused", reason="policy_drift")
            return 2
        # Approvals: the governance SET must be exactly the execute-time pin (a deleted or
        # added YAML refuses — Blocker 3 closed the loader's empty-dir fail-open), non-empty,
        # AND every binding must still point at the parent.
        approvals_att = _approvals_attestation()
        if (approvals_att["root"] != rep["approvals_attestation_root"]
                or approvals_att["bound_count"] < 1):
            logger.error("APPROVALS SET DRIFT — attestation root/bound-count (%s/%d) != the "
                         "reviewed report pin (%s/%s). A YAML was added/removed/edited since "
                         "execute; re-run --execute. Refusing.", approvals_att["root"],
                         approvals_att["bound_count"], rep["approvals_attestation_root"],
                         rep.get("approvals_bound_count"))
            j("verify", "refused", reason="approvals_set_drift")
            return 2
        ok_bind, bind_msg = _approvals_all_bound_to(live_build, live_policy)
        if not ok_bind:
            logger.error("APPROVALS DRIFT — %s. Refusing (the post-swap rebind would not be a clean "
                         "parent->child rewrite).", bind_msg)
            j("verify", "refused", reason=f"approvals:{bind_msg}")
            return 2
        # Plan the rebind NOW (pure, no writes): any planning refusal is a pre-swap refusal,
        # and the caller holds every original byte before anything is written (Blocker 2).
        try:
            rebind_plan, originals = _plan_rebind(
                live_build, live_policy, rep["staged_build_id"], rep["new_policy_id"])
        except PublishTransactionError as exc:
            logger.error("rebind planning refused: %s", exc)
            j("verify", "refused", reason=f"rebind_plan:{exc}")
            return 2
        # Raw provenance from the ATTESTED staged copy (re-review P0: the fixed-name OUT_DIR
        # sidecar is mutable and outside any attestation — a regenerated sidecar could make
        # the published manifest claim raw cut R2 while the staged tree was built from R1).
        # The copy inside <staged>/metadata/ is covered by the staged content attestation;
        # it is the source of truth for BOTH the re-verification file list and the root
        # emitted into provider_build.json. Report + sidecar must agree with it exactly.
        staged_raw_copy = staged_dir / "metadata" / "raw_input_manifest.json"
        try:
            staged_raw = json.loads(staged_raw_copy.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("staged raw-input manifest copy missing/unreadable at %s (%s) — the "
                         "staged build predates the attested-transaction contract; re-run "
                         "--execute. Refusing.", staged_raw_copy, exc)
            j("verify", "refused", reason="staged_raw_copy_missing")
            return 2
        if (staged_raw.get("root") != rep["raw_input_manifest_root"]
                or _manifest_root(staged_raw.get("files", [])) != staged_raw.get("root")):
            logger.error("RAW PROVENANCE MISMATCH — staged copy root %s (self-check %s) != "
                         "report root %s. Refusing.", staged_raw.get("root"),
                         _manifest_root(staged_raw.get("files", [])), rep["raw_input_manifest_root"])
            j("verify", "refused", reason="staged_raw_copy_mismatch")
            return 2
        ok, why = _verify_raw_manifest(staged_raw)
        if not ok:
            logger.error("RAW-INPUT MANIFEST MISMATCH (%s) — the raw cut the staged build consumed "
                         "changed since the build. Re-run --execute. Refusing (fail closed).", why)
            j("verify", "refused", reason=f"raw_manifest:{why}")
            return 2
        # FULL-CONTENT staged re-attestation (Blocker 4): every byte about to be published —
        # feature bins included — must equal what the audits attested at execute.
        logger.info("re-attesting staged FULL content (%s files, %.1f GB) ...",
                    rep.get("staged_content_file_count"),
                    (rep.get("staged_content_total_bytes") or 0) / 2**30)
        att = _staged_content_attestation(staged_dir)
        if att["root"] != rep["staged_content_root"]:
            changed_groups = []
            try:
                pinned = json.loads((OUT_DIR / rep["staged_content_manifest_artifact"])
                                    .read_text(encoding="utf-8")).get("groups", {})
                changed_groups = sorted(g for g in set(pinned) | set(att["groups"])
                                        if pinned.get(g) != att["groups"].get(g))[:10]
            except Exception:  # noqa: BLE001 — localization is best-effort diagnostics
                pass
            logger.error("STAGED-CONTENT DRIFT — full-content root %s != the reviewed report's %s "
                         "(bytes changed since the audited build; first changed groups: %s). "
                         "Re-run --execute. Refusing.", att["root"], rep["staged_content_root"],
                         changed_groups)
            j("verify", "refused", reason="staged_content_drift", changed_groups=changed_groups)
            return 2
        builder = _make_publish_builder(rep["staged_build_id"])
        if Path(builder.paths.provider_dir).resolve() != staged_dir.resolve():
            logger.error("report staged_provider_dir %s is not the canonical staged path %s for "
                         "build_id %s — refusing.", staged_dir, builder.paths.provider_dir,
                         rep["staged_build_id"])
            j("verify", "refused", reason="staged_path_mismatch")
            return 2
        j("verify", "ok", raw_files=manifest["file_count"],
          staged_files=att["file_count"], approvals=bind_msg)
        logger.info("verify OK under locks: parent (%s/%s), raw root %s (%d files), staged content "
                    "root %s (%d files), git %s, audits + policy + approvals — swapping now.",
                    live_build, live_policy, manifest["root"], manifest["file_count"],
                    att["root"], att["file_count"], git_head[:12])

        # ── SWAP + BIND. Interrupt semantics (re-review #3, documented honestly): a REAL
        # SIGINT during this span is DEFERRED — the consistent core transaction (swap +
        # rebind + pending_qa marker + records) COMMITS first, then KeyboardInterrupt is
        # raised at span exit; the operator resumes with --finalize-qa. An in-flow
        # exception/interrupt raised INSIDE the domain (crash-like) triggers the verified
        # rollback and then re-raises. The handler classifies swap completion from DISK
        # FACTS (live manifest + backup dir), never from an in-process boolean, and a
        # durable INTENT journal is written before the first rename so an unresolved
        # transaction blocks any later publish until recovered.
        from data_infra.pit_backend import BuildGateError
        import time as _time
        import uuid
        txid = uuid.uuid4().hex[:16]
        journal["transaction_id"] = txid
        record_path = _tx_dir() / f"publish_record_{txid}.json"
        report_snapshot_path = _tx_dir() / f"report_{txid}.json"
        md_path = APPROVALS_DIR / f"{now_cst().strftime('%Y-%m-%d')}_rebind_to_{rep['staged_build_id']}.md"
        try:
            # the SHARED intent journal + the reviewed-report SNAPSHOT must land in the
            # store's transaction dir BEFORE any rename: any checkout can then detect,
            # finalize, or restore this transaction without this checkout's workspace.
            _atomic_write_bytes(report_snapshot_path,
                                json.dumps(rep, ensure_ascii=False, indent=1).encode("utf-8"))
            _write_intent({"transaction_id": txid, "status": "swapping",
                           "parent_build_id": live_build, "parent_policy_id": live_policy,
                           "child_build_id": rep["staged_build_id"],
                           "backup_dir": f"{builder.paths.qlib_dir}.bak_{builder.build_id}",
                           "staged_provider_dir": str(staged_dir),
                           "record_path": str(record_path),
                           "report_snapshot_path": str(report_snapshot_path),
                           "rebind_record_path": str(md_path)})
        except Exception as exc:  # noqa: BLE001 — the durable intent MUST land before any rename
            logger.error("cannot write the shared intent journal / report snapshot (%s) — "
                         "refusing pre-swap.", exc)
            j("verify", "refused", reason="intent_write_failed")
            return 2
        written: list[Path] = []
        with _defer_sigint("swap+bind"):
            try:
                swap_exc: Exception | None = None
                for attempt in range(1, 4):
                    try:
                        builder.publish(calendar_policy_id=rep["new_policy_id"],
                                        raw_input_manifest_root=staged_raw["root"],
                                        parent_provider_build_id=live_build,
                                        source_git_commit=rep["source_git_commit"])
                        swap_exc = None
                        break
                    except BuildGateError as exc:
                        swap_exc = exc
                        break  # deterministic refusal (cross-volume / missing staged / double failure)
                    except OSError as exc:
                        swap_exc = exc
                        if not os.path.isdir(builder.paths.qlib_dir):
                            break  # double failure — do NOT retry over a missing live provider
                        logger.warning("swap attempt %d failed (%s) — pre-publish state restored "
                                       "by the primitive; retrying in 5s", attempt, exc)
                        _time.sleep(5)
                if swap_exc is not None:
                    live_intact = os.path.isdir(builder.paths.qlib_dir)
                    j("swap", "failed", error=str(swap_exc), live_provider_intact=live_intact)
                    if live_intact:
                        _write_intent({**_read_intent(), "status": "aborted"})
                        logger.error("swap failed after retries and the primitive rolled back — "
                                     "live provider intact: %s", swap_exc)
                        return 2
                    _write_intent({**_read_intent(), "status": "failed_state_unknown"})
                    logger.critical("swap DOUBLE failure — live provider MISSING; follow the "
                                    "recovery move in the error: %s", swap_exc)
                    return 5
                j("swap", "ok", backup=f"{builder.paths.qlib_dir}.bak_{builder.build_id}")
                okm, why_m = _verify_live_manifest(
                    builder.paths.qlib_dir, build_id=rep["staged_build_id"],
                    policy_id=rep["new_policy_id"], raw_root=staged_raw["root"],
                    parent_pb=live_build, source_git_commit=rep["source_git_commit"])
                if not okm:
                    raise PublishTransactionError(
                        f"post-swap live manifest verification failed: {why_m}")
                for p, nd in rebind_plan:
                    _atomic_write_bytes(p, nd)
                    written.append(p)
                from data_infra.approval_evidence import evaluate_approval_evidence_bindings
                drifts = evaluate_approval_evidence_bindings(
                    approvals_dir=APPROVALS_DIR,
                    manifest_path=Path(builder.paths.qlib_dir) / "metadata" / "provider_build.json")
                still = [d for d in drifts if d.drift]
                if still:
                    raise PublishTransactionError(
                        f"{len(still)} approval(s) still drift after the rebind: {still[0].reasons()}")
                # B6 QA quarantine: the provider is durable but NOT ready — gated reads
                # refuse until the READY gate (QA pass + full pin re-verification) flips it.
                # ORDER (re-review #4 P0: the record must not be forgeable after the fact):
                # the per-transaction RECORD is written FIRST into the SHARED transaction
                # dir; the marker then binds transaction_id + the record's sha256, so any
                # later record edit breaks the marker binding at the READY gate.
                appr_post = _approvals_attestation()  # post-rebind pin the READY gate re-checks
                record = {
                    "transaction_id": txid,
                    "published_build_id": rep["staged_build_id"],
                    "calendar_policy_id": rep["new_policy_id"],
                    "parent_build_id": live_build, "parent_policy_id": live_policy,
                    "raw_input_manifest_root": staged_raw["root"],
                    "raw_input_manifest_file_count": staged_raw.get("file_count"),
                    "staged_content_root": att["root"],
                    "staged_content_file_count": att["file_count"],
                    "approvals_post_rebind_root": appr_post["root"],
                    "source_git_commit": rep["source_git_commit"],
                    "approvals_rebound": len(written),
                    "backup_dir": f"{builder.paths.qlib_dir}.bak_{builder.build_id}",
                    "reviewed_dryrun_report": str(DRYRUN_REPORT_PATH),
                    "report_snapshot_path": str(report_snapshot_path),
                    "published_cst": now_cst().isoformat(timespec="seconds"),
                }
                record_bytes = json.dumps(record, ensure_ascii=False, indent=1).encode("utf-8")
                _atomic_write_bytes(record_path, record_bytes)   # canonical, per-transaction
                _atomic_write_bytes(PUBLISH_RECORD_PATH, record_bytes)  # human convenience copy
                import hashlib as _hashlib
                _write_publish_state(builder.paths.qlib_dir, "pending_qa", rep["staged_build_id"],
                                     parent_build_id=live_build, transaction_id=txid,
                                     record_sha256=_hashlib.sha256(record_bytes).hexdigest())
                # the committed governance record is written LAST — nothing may claim a
                # completed rebind before every durable step above proved out (Blocker 2b).
                _write_rebind_record(
                    path=md_path,
                    new_pb=rep["staged_build_id"], new_cp=rep["new_policy_id"], old_pb=live_build,
                    old_cp=live_policy, n_files=len(written), raw_root=staged_raw["root"],
                    raw_files=staged_raw.get("file_count") or 0,
                    backup_dir=f"{builder.paths.qlib_dir}.bak_{builder.build_id}")
                _write_intent({**_read_intent(), "status": "committed_core"})
                j("bind", "ok", approvals_rebound=len(written))
            except BaseException as exc:  # noqa: BLE001 — interrupts included (re-review P0)
                # DISK-TRUTH classification (re-review #3 P0): never infer swap completion
                # from an in-process boolean — an exception between publish() returning and
                # a flag assignment would mis-classify a live child as pre-swap.
                dstate = _disk_swap_state(builder, live_build)
                if dstate == "parent_live":
                    # the primitive self-rolled-back (or the failure landed before any
                    # rename) — nothing durable mutated by THIS transaction.
                    _write_intent({**_read_intent(), "status": "aborted"})
                    j("swap", "aborted_pre_completion", error=repr(exc))
                    logger.critical("aborted before the swap completed (%r) — verified from "
                                    "disk: data/qlib_data is the parent.", exc)
                    raise
                if dstate == "unknown":
                    j("swap", "failed_state_unknown", error=repr(exc))
                    logger.critical("DISK STATE UNKNOWN after failure (%r) — neither parent-live "
                                    "nor child-live signature matches; recover manually per the "
                                    "intent journal (%s) + transaction journal (%s).",
                                    exc, _intent_path(), TRANSACTION_JOURNAL_PATH)
                    if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                        raise
                    return 5
                logger.error("post-swap step failed (%r) — restoring approvals + artifacts + "
                             "rolling the swap back.", exc)
                problems: list[str] = []
                problems += _restore_approval_files(written, originals)
                # artifact cleanup is DISK-DRIVEN by transaction id — never gated on
                # in-process booleans (re-review #3 Major: an interrupt after the record's
                # atomic replace but before a flag left a false 'published' record behind).
                for artifact in (record_path, report_snapshot_path, md_path):
                    try:
                        Path(artifact).unlink(missing_ok=True)
                    except OSError as uexc:
                        problems.append(f"could not remove {artifact}: {uexc}")
                try:  # the fixed-name copy: delete ONLY if it belongs to THIS transaction
                    fixed = json.loads(PUBLISH_RECORD_PATH.read_text(encoding="utf-8"))
                    if fixed.get("transaction_id") == txid:
                        PUBLISH_RECORD_PATH.unlink(missing_ok=True)
                except (OSError, json.JSONDecodeError):
                    pass  # absent or foreign — nothing of ours to clean
                # strip THIS transaction's post-swap files from the new tree so the returned
                # staged tree matches its content attestation again for a clean retry
                for name in ("provider_build.json", "publish_state.json"):
                    fpath = Path(builder.paths.qlib_dir) / "metadata" / name
                    try:
                        fpath.unlink(missing_ok=True)
                    except OSError as uexc:
                        problems.append(f"could not remove new-tree {name}: {uexc}")
                ok_rb, rb_msg = _rollback_swap(builder)
                if ok_rb:
                    try:
                        rb_build, rb_policy = live_provider_ids()
                        if (rb_build, rb_policy) != (live_build, live_policy):
                            problems.append(f"post-rollback live ids ({rb_build}/{rb_policy}) != "
                                            f"parent ({live_build}/{live_policy})")
                    except Exception as vexc:  # noqa: BLE001
                        problems.append(f"post-rollback live manifest unreadable: {vexc}")
                else:
                    problems.append(f"swap rollback failed: {rb_msg}")
                _write_intent({**_read_intent(),
                               "status": "aborted" if not problems else "rollback_incomplete"})
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    j("bind", "interrupted_rolled_back" if not problems
                      else "interrupted_rollback_incomplete", error=repr(exc),
                      rollback=rb_msg, problems=problems)
                    logger.critical("INTERRUPTED mid-transaction — rollback %s. Problems: %s",
                                    "VERIFIED complete" if not problems else "INCOMPLETE",
                                    problems or "none")
                    raise
                if not problems:
                    j("bind", "failed_rolled_back", error=str(exc), rollback=rb_msg)
                    logger.error("ROLLED BACK to the parent live provider — VERIFIED (approval "
                                 "bytes re-read identical, parent ids live, artifacts removed): "
                                 "%s. Fix the cause and re-run --publish-approved. Cause: %s",
                                 rb_msg, exc)
                    return 4
                j("bind", "failed_rollback_incomplete", error=str(exc), rollback=rb_msg,
                  problems=problems)
                logger.critical("ROLLBACK INCOMPLETE — resolve manually per the journal (%s). "
                                "Problems: %s. Cause: %s", TRANSACTION_JOURNAL_PATH, problems, exc)
                return 5
    # ── locks released: swap + rebind + metadata are consistent and durable (state=pending_qa).

    logger.info("ATOMIC PUBLISH COMPLETE: %s live under %s (parent %s retained as .bak; publish-state "
                "pending_qa quarantines gated reads). Running post-publish QA ...",
                rep["staged_build_id"], rep["new_policy_id"], live_build)
    return _run_and_record_qa(builder, rep, j)


# files the publish itself adds to the live tree AFTER the content attestation — the
# READY-gate re-verification excludes exactly these (and nothing else).
_LIVE_PUBLISH_FILES = ("metadata/provider_build.json", "metadata/publish_state.json")


def _run_and_record_qa(builder, rep: dict, j) -> int:
    """Register a QA attempt LEASE, run run_daily_qa, then hand the READY decision to
    :func:`_finalize_ready` (PASS) or persist the quarantine through the lease-checked
    :func:`_record_qa_failure` (FAIL -> 'qa_failed', exit 6; stale worker -> 7)."""
    attempt = _begin_qa_attempt(builder, rep)
    if attempt is None:
        logger.error("cannot begin a QA attempt — the marker/build state does not admit one.")
        return 2
    qa_rc = _run_post_publish_qa()
    if qa_rc != 0:
        return _record_qa_failure(builder, rep, attempt, qa_rc, j)
    j("qa", "passed", returncode=0, attempt=attempt)
    return _finalize_ready(builder, rep, j, attempt)


def _finalize_ready(builder, rep: dict, j, attempt: str) -> int:
    """The ONLY transition to publish-state 'ready' (re-review #2 P0-3/P0-4 + #3 P0-2).
    Under the transaction locks: (0) the QA-attempt LEASE is CAS-checked (a stale worker
    records 'superseded' and changes nothing, exit 7); (1) every cheap pin is re-verified
    against the LIVE tree — manifest CAS (build/policy/raw-root/parent/execute-commit),
    minted-policy file hash, post-rebind approvals set (vs this transaction's record,
    located via the marker's transaction id), in-tree raw manifest (root AND file-list
    self-root); (2) the payload is SEALED read-only (every file except the control-plane
    marker) so no attribute-respecting writer can mutate it afterwards; (3) the FULL
    sealed content is re-hashed and must equal the reviewed staged root. Tamper-class
    failures (manifest CAS / content root) transition the marker to 'suspect' — which
    blocks publish AND finalize until --restore-parent — and exit 5; softer pin problems
    (records/policy/approvals) keep the current state for a retryable finalize, exit 5.
    QA is a sampling check; THIS gate is the proof."""
    import hashlib as _hashlib
    from data_infra.tushare_lock import provider_publish_lock, raw_maintenance_lock
    qlib_dir = Path(builder.paths.qlib_dir)
    with raw_maintenance_lock(), provider_publish_lock(qlib_dir=qlib_dir):
        marker = _read_publish_state(qlib_dir)
        if (marker.get("active_qa_attempt") != attempt
                or marker.get("provider_build_id") != rep["staged_build_id"]
                or marker.get("state") not in ("pending_qa", "qa_failed")):
            j("ready", "superseded", attempt=attempt, marker_state=marker.get("state"),
              marker_attempt=marker.get("active_qa_attempt"))
            logger.warning("stale READY attempt %s superseded (marker state=%r attempt=%r) — "
                           "changing nothing.", attempt, marker.get("state"),
                           marker.get("active_qa_attempt"))
            return 7
        tamper: list[str] = []
        soft: list[str] = []
        okm, why_m = _verify_live_manifest(
            qlib_dir, build_id=rep["staged_build_id"], policy_id=rep["new_policy_id"],
            raw_root=rep["raw_input_manifest_root"], parent_pb=rep["parent_build_id"],
            source_git_commit=rep["source_git_commit"])
        if not okm:
            tamper.append(f"live manifest CAS failed: {why_m}")
        policy_file = POLICY_DIR / f"{rep['new_policy_id']}.yaml"
        if not policy_file.is_file() or _sha256_file(policy_file) != rep["new_policy_sha256"]:
            soft.append("minted policy file hash drifted since the reviewed report")
        # The RECORD is only trusted through the marker's digest binding (re-review #4 P0:
        # a rewritten record plus a wrongly rebound approval previously reached ready) —
        # locate it in the SHARED transaction dir via the marker's txid, require its
        # sha256 to equal the one the marker pinned at publish, and cross-check every
        # identity field against the reviewed report.
        txid = marker.get("transaction_id")
        record: dict = {}
        if not txid:
            tamper.append("marker carries no transaction_id — cannot locate this publish's record")
        else:
            record_file = _tx_dir() / f"publish_record_{txid}.json"
            try:
                record_bytes = record_file.read_bytes()
                if _hashlib.sha256(record_bytes).hexdigest() != marker.get("record_sha256"):
                    tamper.append("publish record digest != the marker's pinned record_sha256 "
                                  "(the record was rewritten after publish)")
                record = json.loads(record_bytes.decode("utf-8"))
            except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
                tamper.append(f"publish record for transaction {txid} unreadable: {exc}")
        if record:
            expected_fields = {
                "transaction_id": txid,
                "published_build_id": rep["staged_build_id"],
                "calendar_policy_id": rep["new_policy_id"],
                "parent_build_id": rep["parent_build_id"],
                "raw_input_manifest_root": rep["raw_input_manifest_root"],
                "staged_content_root": rep["staged_content_root"],
                "source_git_commit": rep["source_git_commit"],
            }
            mismatched = [k for k, v in expected_fields.items() if record.get(k) != v]
            if mismatched:
                tamper.append(f"publish record fields {mismatched} do not match the review")
        appr = _approvals_attestation()
        if appr["bound_count"] < 1 or appr["root"] != record.get("approvals_post_rebind_root"):
            soft.append("approvals governance set drifted since the rebind")
        # SEMANTIC binding check (re-review #4 P0): every approval must actually bind to
        # THIS live build/policy — root equality against a record can be forged, the
        # binding evaluation cannot. Any drift is tamper-class.
        try:
            from data_infra.approval_evidence import evaluate_approval_evidence_bindings
            drift = [d for d in evaluate_approval_evidence_bindings(
                approvals_dir=APPROVALS_DIR,
                manifest_path=qlib_dir / "metadata" / "provider_build.json") if d.drift]
            if drift:
                tamper.append(f"{len(drift)} approval binding(s) drift from the live manifest: "
                              f"{drift[0].reasons()}")
        except Exception as exc:  # noqa: BLE001 — governance loader failure = not certifiable
            tamper.append(f"approval binding evaluation failed: {exc}")
        try:
            live_raw = json.loads((qlib_dir / "metadata" / "raw_input_manifest.json")
                                  .read_text(encoding="utf-8"))
            if (live_raw.get("root") != rep["raw_input_manifest_root"]
                    or _manifest_root(live_raw.get("files", [])) != live_raw.get("root")):
                tamper.append("in-tree raw manifest root/file-list inconsistent with the review")
        except (OSError, json.JSONDecodeError) as exc:
            tamper.append(f"in-tree raw manifest unreadable: {exc}")
        if not tamper and not soft:
            # SEAL the generation BEFORE the certifying hash (re-review #3 P0-2: one more
            # hash cannot close the hash->ready window on a mutable tree). Exemption is the
            # EXACT control-plane relpath; the external build manifest — part of the
            # attestation — is sealed too (re-review #4 P0).
            sealed = _seal_tree_readonly(qlib_dir)
            build_manifest = Path(builder.paths.build_root) / "manifest.json"
            if build_manifest.is_file():
                import stat as _stat
                os.chmod(build_manifest, _stat.S_IREAD)
            logger.info("READY gate: sealed %d files read-only; FULL sealed-content "
                        "re-verification (%s files) ...", sealed,
                        rep.get("staged_content_file_count"))
            att = _staged_content_attestation(
                qlib_dir, exclude=_LIVE_PUBLISH_FILES,
                build_manifest_path=build_manifest)
            if att["root"] != rep["staged_content_root"]:
                tamper.append(
                    f"SEALED content root {att['root']} != reviewed {rep['staged_content_root']}"
                    " — the published bytes changed since the audited build")
        if tamper:
            _write_publish_state(qlib_dir, "suspect", rep["staged_build_id"],
                                 reason=tamper[0])
            j("ready", "refused_suspect", problems=tamper + soft)
            logger.critical("READY REFUSED — TAMPER-CLASS failure; publish-state 'suspect' now "
                            "BLOCKS publish AND finalize until --restore-parent. Problems: %s "
                            "(journal %s).", tamper + soft, TRANSACTION_JOURNAL_PATH)
            return 5
        if soft:
            j("ready", "refused", problems=soft)
            logger.critical("READY REFUSED — records/pins incomplete (state unchanged; fix and "
                            "re-run --finalize-qa). Problems: %s.", soft)
            return 5
        _write_publish_state(qlib_dir, "ready", rep["staged_build_id"], qa_returncode=0,
                             qa_attempt=attempt)
    j("ready", "ok", attempt=attempt)
    logger.info("publish-state 'ready' — QA passed AND every pin re-verified against the SEALED "
                "live tree. Publish record: %s", PUBLISH_RECORD_PATH)
    return 0


def _load_tx_report() -> dict | None:
    """The reviewed-report SNAPSHOT for the transaction the LIVE MARKER names — read from
    the SHARED transaction dir (re-review #4 P0: finalize/restore must work from ANY
    checkout, so they load the snapshot bound at publish, never this checkout's
    workspace copy). None when the marker/txid/snapshot chain is broken."""
    marker = _read_publish_state(_live_paths().qlib_dir)
    txid = marker.get("transaction_id")
    if not txid:
        logger.error("live marker carries no transaction_id — no transaction to act on.")
        return None
    snap = _tx_dir() / f"report_{txid}.json"
    try:
        rep = json.loads(snap.read_text(encoding="utf-8"))
        return rep if isinstance(rep, dict) else None
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("report snapshot for transaction %s unreadable at %s (%s).", txid, snap, exc)
        return None


def phase_finalize_qa(args) -> int:
    """Re-run the QA + READY-gate leg for a provider stuck in 'pending_qa'/'qa_failed'
    (crash between swap and QA — including a deferred-SIGINT commit-core — or a QA failure
    now resolved). Works from ANY checkout: the reviewed pins come from the SHARED report
    snapshot the marker's transaction id names. CAS-verifies the live manifest BEFORE
    running QA; the full READY gate (:func:`_finalize_ready` — lease + record digest +
    semantic binding drift + seal + content root) decides afterwards; a provider whose
    bytes changed since the review can NEVER be marked ready by this path (it transitions
    to 'suspect' instead)."""
    if not _assert_standard_layout():
        return 2
    rep = _load_tx_report()
    if rep is None:
        return 2
    required = ("staged_build_id", "new_policy_id", "raw_input_manifest_root",
                "parent_build_id", "source_git_commit", "new_policy_sha256",
                "staged_content_root")
    missing = [k for k in required if not rep.get(k)]
    if missing:
        logger.error("report snapshot lacks %s — cannot finalize. Refusing.", missing)
        return 2
    builder = _make_publish_builder(rep["staged_build_id"])
    from data_infra.tushare_lock import provider_publish_lock, raw_maintenance_lock
    with raw_maintenance_lock(), provider_publish_lock(qlib_dir=builder.paths.qlib_dir):
        live_build, _ = live_provider_ids()
        if live_build != rep["staged_build_id"]:
            logger.error("live build %s is not the report's staged build %s — --finalize-qa only "
                         "finishes the publish this report describes. Refusing.",
                         live_build, rep["staged_build_id"])
            return 2
        state = _read_publish_state(builder.paths.qlib_dir).get("state")
        if state not in ("pending_qa", "qa_failed"):
            logger.error("publish-state is %r — --finalize-qa only applies to pending_qa/"
                         "qa_failed (a 'suspect' provider requires --restore-parent).", state)
            return 2
        okm, why_m = _verify_live_manifest(
            builder.paths.qlib_dir, build_id=rep["staged_build_id"],
            policy_id=rep["new_policy_id"], raw_root=rep["raw_input_manifest_root"],
            parent_pb=rep["parent_build_id"], source_git_commit=rep["source_git_commit"])
        if not okm:
            logger.error("live manifest CAS failed before QA (%s) — refusing to finalize.", why_m)
            return 2

    journal: dict = {"transaction": "finalize_qa", "staged_build_id": rep["staged_build_id"],
                     "steps": []}

    def j(step: str, status: str, **info) -> None:
        journal["steps"].append({"step": step, "status": status,
                                 "ts_cst": now_cst().isoformat(timespec="seconds"), **info})
        _write_journal(journal)

    return _run_and_record_qa(builder, rep, j)


def phase_restore_parent(args) -> int:
    """EXPLICIT recovery from a quarantined/suspect publish (re-review #3 disposition:
    never silently auto-restore; provide a verified command instead). Works from ANY
    checkout (pins come from the SHARED report snapshot). Under the transaction locks and
    a BaseException-safe, SIGINT-deferred domain (re-review #4 P0: an interrupt between
    two reverse approval writes previously left a half-rebound live child that the
    built-in recovery then refused): verifies the live build is the report's child AND
    the .bak parent's manifest matches the parent ids; unseals the (possibly sealed)
    child tree; reverse-rebinds the approval YAMLs child->parent (pure plan first);
    strips the publish-added files; swaps the parent back; verifies parent ids live +
    0 binding drift. On ANY failure/interrupt mid-domain, the already-written reverse
    approvals are restored (byte-verified) so the state returns to uniformly-child-bound
    and --restore-parent can simply be re-run; interrupts journal 'restore_interrupted'
    and re-raise. Exit 0 only when every check passes; else 5 with the journal."""
    if not _assert_standard_layout():
        return 2
    rep = _load_tx_report()
    if rep is None:
        return 2
    builder = _make_publish_builder(rep["staged_build_id"])
    from data_infra.tushare_lock import provider_publish_lock, raw_maintenance_lock

    journal: dict = {"transaction": "restore_parent", "staged_build_id": rep["staged_build_id"],
                     "steps": []}

    def j(step: str, status: str, **info) -> None:
        journal["steps"].append({"step": step, "status": status,
                                 "ts_cst": now_cst().isoformat(timespec="seconds"), **info})
        _write_journal(journal)

    with raw_maintenance_lock(), provider_publish_lock(qlib_dir=builder.paths.qlib_dir):
        qlib_dir = Path(builder.paths.qlib_dir)
        live_build, live_policy = live_provider_ids()
        if live_build != rep["staged_build_id"]:
            logger.error("live build %s is not the report's child %s — nothing to restore.",
                         live_build, rep["staged_build_id"])
            return 2
        marker = _read_publish_state(qlib_dir)
        state = marker.get("state")
        if state not in ("suspect", "pending_qa", "qa_failed"):
            logger.error("publish-state is %r — --restore-parent only undoes an uncertified "
                         "publish (suspect/pending_qa/qa_failed).", state)
            return 2
        backup_dir = Path(f"{builder.paths.qlib_dir}.bak_{builder.build_id}")
        try:
            bak_manifest = json.loads((backup_dir / "metadata" / "provider_build.json")
                                      .read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("backup parent manifest unreadable at %s (%s) — refusing.", backup_dir, exc)
            return 2
        if (bak_manifest.get("provider_build_id") != rep["parent_build_id"]
                or bak_manifest.get("calendar_policy_id") != rep["parent_policy_id"]):
            logger.error("backup at %s is NOT the report's parent (%s/%s) — refusing.",
                         backup_dir, rep["parent_build_id"], rep["parent_policy_id"])
            return 2
        try:
            reverse_plan, current_bytes = _plan_rebind(
                rep["staged_build_id"], rep["new_policy_id"],
                rep["parent_build_id"], rep["parent_policy_id"])
        except PublishTransactionError as exc:
            logger.error("reverse rebind planning refused (%s) — approvals are not uniformly "
                         "bound to the child; repair from git first.", exc)
            return 2
        j("restore", "verified_preconditions", state=state)
        txid = marker.get("transaction_id")
        problems: list[str] = []
        written: list[Path] = []
        with _defer_sigint("restore-parent"):
            try:
                unsealed = _unseal_tree(qlib_dir)
                j("restore", "unsealed", files=unsealed)
                for p, nd in reverse_plan:
                    _atomic_write_bytes(p, nd)
                    written.append(p)
                for name in ("provider_build.json", "publish_state.json"):
                    (qlib_dir / "metadata" / name).unlink(missing_ok=True)
                ok_rb, rb_msg = _rollback_swap(builder)
                if not ok_rb:
                    problems.append(f"swap-back failed: {rb_msg}")
                else:
                    try:
                        rb_build, rb_policy = live_provider_ids()
                        if (rb_build, rb_policy) != (rep["parent_build_id"], rep["parent_policy_id"]):
                            problems.append(
                                f"post-restore live ids ({rb_build}/{rb_policy}) != parent")
                    except Exception as vexc:  # noqa: BLE001
                        problems.append(f"post-restore live manifest unreadable: {vexc}")
                    from data_infra.approval_evidence import evaluate_approval_evidence_bindings
                    drifts = evaluate_approval_evidence_bindings(
                        approvals_dir=APPROVALS_DIR,
                        manifest_path=qlib_dir / "metadata" / "provider_build.json")
                    still = [d for d in drifts if d.drift]
                    if still:
                        problems.append(f"{len(still)} approvals still drift after the restore")
                    if txid:
                        try:
                            (_tx_dir() / f"publish_record_{txid}.json").unlink(missing_ok=True)
                        except OSError as uexc:
                            problems.append(f"could not remove the transaction record: {uexc}")
            except BaseException as exc:  # noqa: BLE001 — interrupts included (re-review #4)
                # un-restore the partial reverse rebind so the state returns to
                # uniformly-child-bound and this command can simply be re-run.
                undo_failures = _restore_approval_files(written, current_bytes)
                _write_intent({**_read_intent(), "status": "restore_interrupted"})
                j("restore", "interrupted" if not undo_failures else "interrupted_incomplete",
                  error=repr(exc), undo_failures=undo_failures)
                logger.critical("RESTORE INTERRUPTED (%r) — partial reverse writes %s; re-run "
                                "--restore-parent. Journal: %s", exc,
                                "undone (byte-verified)" if not undo_failures
                                else f"NOT fully undone: {undo_failures}",
                                TRANSACTION_JOURNAL_PATH)
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    raise
                problems.append(f"restore aborted mid-domain: {exc!r}")
                problems += undo_failures
            # the final bookkeeping stays INSIDE the deferral: a deferred real SIGINT then
            # fires only after the intent reached a settled status (a raise here would
            # otherwise leave 'swapping'-era state blocking every future publish).
            _write_intent({**_read_intent(), "status": "aborted" if not problems
                           else "rollback_incomplete"})
            if problems:
                j("restore", "incomplete", problems=problems)
                logger.critical("RESTORE INCOMPLETE — resolve manually per the journal (%s): %s",
                                TRANSACTION_JOURNAL_PATH, problems)
                return 5
            j("restore", "ok")
    logger.info("RESTORED: the parent provider is live again; the child sits back at the staged "
                "path for investigation. Approvals re-bound to the parent (0 drift).")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Monthly calendar freeze-bump driver")
    ap.add_argument("--plan", action="store_true", help="Preflight + target_end + plan only")
    ap.add_argument("--execute", action="store_true",
                    help="Run catch-up->rebuild->audits->dry-run report (multi-hour); STOPS before publish")
    ap.add_argument("--publish-approved", action="store_true",
                    help="Run the ATOMIC publish transaction (verify+swap+rebind+QA; §13, "
                         "requires --i-reviewed-the-dryrun)")
    ap.add_argument("--i-reviewed-the-dryrun", action="store_true",
                    help="Attest the dry-run report was reviewed (required for --publish-approved)")
    ap.add_argument("--finalize-qa", action="store_true",
                    help="Re-run the post-publish QA + READY-gate leg for a provider "
                         "quarantined at pending_qa/qa_failed (crash/deferred-SIGINT between "
                         "swap and QA, or a resolved QA failure); flips publish-state to "
                         "'ready' only after the full sealed-content re-verification")
    ap.add_argument("--restore-parent", action="store_true",
                    help="EXPLICIT verified recovery: undo an uncertified publish "
                         "(suspect/pending_qa/qa_failed) — reverse-rebind approvals, swap the "
                         ".bak parent back live, verify parent ids + 0 binding drift")
    ap.add_argument("--target-end", type=str, default=None, help="Override target_end (YYYYMMDD)")
    ap.add_argument("--allow-migration-exception", action="store_true",
                    help="Acknowledge that a frozen-prefix exception type recurring 2+ bumps has "
                         "been migrated to a permanent note+tests (M2). Without it, a recurring "
                         "exception type BLOCKS the bump.")
    args = ap.parse_args()

    if args.plan:
        phase_plan(args)
        return 0
    if args.execute:
        return phase_execute(args)
    if args.publish_approved:
        return phase_publish(args)
    if args.finalize_qa:
        return phase_finalize_qa(args)
    if args.restore_parent:
        return phase_restore_parent(args)
    logger.error("choose a mode: --plan (review) | --execute (multi-hour, stops before publish) | "
                 "--publish-approved --i-reviewed-the-dryrun | --finalize-qa | --restore-parent")
    return 2


if __name__ == "__main__":
    sys.exit(main())
