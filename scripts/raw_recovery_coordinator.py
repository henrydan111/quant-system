# SCRIPT_STATUS: ACTIVE — 2026-07-13 junction-deletion incident: C:-staged raw-store recovery coordinator (v3)
"""Recovery coordinator v3 (post GPT recovery re-review #2 REWORK — RAW_STORE_RECOVERY_PLAN.md v4).

v3 closes the re-review's Blockers:
- B1: run_id is a validated single component; containment is LEXICAL-FIRST (validate under RECOVERY_ROOT
  before any resolve — `..\\escape` and `..\\..\\Users\\...` refuse at the regex), reparse points are
  inspected per-component WITHOUT resolving first (resolve() would follow a junction and erase the
  evidence), root/tmp/.lock creation all route through the same authority, resume validates the
  original `run_created` ledger record (run_id + pinned baseline hash).
- B3: the ledger is a TYPED, TRANSITION-ENFORCED store: a frozen hashed request plan, per-kind schemas
  (lifecycle / attempt / verdict), stable request ids, enforced planned->fetched|failed->
  verified|confirmed_empty transitions under the file lock, verification that checks the actual output
  (existence, containment, sha256) before accepting `verified`, dense-empty refusal, torn-tail
  fail-closed, and a consolidation gate requiring every planned constituent terminal-valid.
- B4: the endpoint doc gate validates STRUCTURE: doc_path resolved under the offline mirror with
  traversal/reparse rejection, doc_sha256 recomputed, structured fields, ISO reviewed_at (not future),
  non-placeholder reviewer.
- B2: ADAPTER_SPECS is replaced by ENDPOINT_MATRIX — one machine-readable row per endpoint/output
  family (endpoint, callable, outputs, partitioner, pagination, natural key, empty policy,
  consolidation, tail rule, UNIQUE owner, generated sidecars). Corrections: dividends are fetched
  INSIDE FundamentalsInitializer.download_fundamentals (per stock, together with income+balancesheet);
  cashflow/forecast/holder_number belong to init_factor_data (CLAUDE §6.2); index_daily is per-index
  RANGE; stk_holdertrade/cyq_perf are per-stock (cyq repartitioned per-date); indicators have ONE owner
  (A07, refresh_indicator_history); generic L9 is GONE — every row carries its own tail_rule.

Fetch remains REFUSED. Sequencing (GPT M3): contracts are reviewed+signed BEFORE that endpoint's
adapter/partition logic is written; only generic containment/ledger infrastructure (this file) may
precede contract review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

E_ROOT = Path(r"E:\量化系统")
E_DATA = E_ROOT / "data"
DOC_MIRROR = E_ROOT / "Tushare数据接口" / "content"
MANIFEST = E_DATA / "qlib_builds" / "thaw_step1_20260703c" / "manifest.json"
MANIFEST_SHA256 = "fbc4aec076fda8ab200cc09ef2d1fff07d28ae4491b8020123faf179e467627f"
LIVE_PROVIDER_SOURCE_COMMIT = "f93cb9d20ebd4d68f15d31c34caac78b2da17be2"
RECOVERY_ROOT = Path(r"C:\quant_recovery") / "runs"
CONTRACTS_YAML = E_ROOT / "workspace" / "configs" / "recovery_endpoint_contracts.yaml"
MIN_STAGING_FREE_GB = 200
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_PLACEHOLDERS = {"", "x", "xx", "tbd", "todo", "na", "n/a", "-", "?", "pending"}

SURVIVOR_TREES = ["reference", "universe"]
EVIDENCE_GLOBS = [
    "data/raw_cache/**/*", "workspace/outputs/calendar_unfreeze/*.json",
    "logs/update_daily_data_202607.log", "logs/catchup_daily_unfreeze.log",
    "logs/catchup_fundamentals_unfreeze.log",
]
IRRECOVERABLE = [
    ("indicator_history_archives", "staged update_flag revision archives — capture times unreproducible"),
    ("report_rc_revision_baseline", "pre-incident retrograde baseline gone; rebuilt only after live-provider parity"),
    ("report_rc_first_seen", "raw_fetch_ts stamps 2026-07-01..incident — only CONTENT-BOUND retained evidence "
                             "(natural key + content hash + timestamp) is admissible; else recovery-time floor/quarantine"),
]

# ── B2: machine-readable endpoint matrix (one row per endpoint/output family; UNIQUE owner) ─────────
# callable = the code the adapter wraps (bound to the exact method at adapter build, AFTER the
# endpoint's contract is reviewed — GPT M3). empty: dense_refuse = an empty response can never be
# accepted; sparse_canary = confirmed_empty needs contract permission + a same-session nonempty canary.
def _row(owner, endpoint, callable_ref, outputs, partitioner, pagination, natural_key, empty,
         consolidation, tail_rule, sidecars=()):
    return {"owner": owner, "endpoint": endpoint, "callable": callable_ref, "outputs": outputs,
            "partitioner": partitioner, "pagination": pagination, "natural_key": natural_key,
            "empty": empty, "consolidation": consolidation, "tail_rule": tail_rule,
            "sidecars": list(sidecars)}


ENDPOINT_MATRIX = [
    _row("A01", "daily", "MarketDataInitializer.download_daily_data (bypass main(): it always refetches reference)",
         ["market/daily/<yr>/daily_<date>.parquet"], "per open trade_date (survivor trade_cal)",
         "single page per date (verify vs contract)", ["ts_code", "trade_date"], "dense_refuse",
         "per-date file complete when daily+daily_basic+adj_factor merged (100% adj rule)",
         "sessions 20260702..last-complete"),
    _row("A01", "daily_basic", "same fetch as A01 daily merge leg", ["merged into daily_<date>.parquet"],
         "per open trade_date", "single page per date", ["ts_code", "trade_date"], "dense_refuse",
         "merged column set present (payload coverage rule)", "with A01"),
    _row("A01", "adj_factor", "same fetch as A01 daily merge leg", ["merged into daily_<date>.parquet"],
         "per open trade_date", "single page per date", ["ts_code", "trade_date"], "dense_refuse",
         "100% positive coverage of priced codes", "with A01"),
    _row("A02", "index_daily", "MarketDataInitializer index leg — per-index RANGE fetch (not per date)",
         ["market/index/index_<code>.parquet"], "per index code × full range", "range paging per contract",
         ["ts_code", "trade_date"], "dense_refuse", "per-index file spans manifest range 20080102..",
         "range end extends to last-complete"),
    _row("A03", "income_vip+balancesheet_vip+dividend", "FundamentalsInitializer.download_fundamentals — "
         "per STOCK, fetches income+balancesheet+DIVIDENDS together (no separate statement methods); "
         "adapter must SKIP industry/index_weights (survivors)",
         ["fundamentals/income/*.parquet", "fundamentals/balancesheet/*.parquet", "corporate/dividends/*.parquet"],
         "per ts_code over survivor stock_basic (incl. delisted)", "per-stock full history, no offset",
         ["ts_code", "end_date", "(dividends: ts_code, end_date, div_proc)"], "sparse_canary",
         "periodic files only after ALL stocks terminal-valid (per-stock failures currently swallowed — ledger gates)",
         "ann_date-window sweep for the tail (calendar-day, not session)"),
    _row("A04", "income_vip(q)+cashflow_vip(q)", "scripts/fetch_quarterly_statements.py (direct-quarter "
         "report_type combine)", ["fundamentals/income_quarterly/*.parquet", "fundamentals/cashflow_quarterly/*.parquet"],
         "per period × report_type", "VIP 10k page fallback offset", ["ts_code", "end_date", "report_type"],
         "dense_refuse (past periods)", "per-period complete only after both report_types verified",
         "current period via ann_date window"),
    _row("A05", "cashflow_vip", "FactorDataInitializer cashflow leg (CLAUDE §6.2: cashflow is Phase-3/"
         "init_factor scope; bind exact method at adapter build)", ["fundamentals/cashflow/*.parquet"],
         "per period (cumulative)", "VIP page fallback", ["ts_code", "end_date"], "dense_refuse (past periods)",
         "per-period", "ann_date window"),
    _row("A06", "forecast_vip", "FactorDataInitializer forecast leg", ["fundamentals/forecast/*.parquet"],
         "per ann_date window", "VIP page fallback", ["ts_code", "end_date", "ann_date"], "sparse_canary",
         "per-window", "ann_date calendar-day window"),
    _row("A07", "fina_indicator_vip", "refresh_indicator_history (SOLE indicator owner — update_flag "
         "revision capture; historical archives = irrecoverable evidence)", ["fundamentals/indicators/*.parquet"],
         "per period", "VIP 10k limit + offset fallback", ["ts_code", "end_date", "update_flag"], "dense_refuse",
         "per-period after profiler parity", "current period refresh"),
    _row("A08", "moneyflow", "FactorDataInitializer moneyflow leg", ["market/moneyflow/<yr>/moneyflow_<date>.parquet"],
         "per open trade_date", "single page per date", ["ts_code", "trade_date"], "sparse_canary",
         "per-date; known-empty dates live in the sidecar", "sessions tail",
         sidecars=["reference/moneyflow_known_empty_dates.txt (FIRST-CLASS output: updates are recovery artifacts)"]),
    _row("A08", "stk_limit", "FactorDataInitializer stk_limit leg", ["market/stk_limit/<yr>/stk_limit_<date>.parquet"],
         "per open trade_date", "single page per date", ["ts_code", "trade_date"], "dense_refuse",
         "per-date", "sessions tail"),
    _row("A08", "margin_detail", "FactorDataInitializer margin leg (lands in market/margin/ = manifest "
         "dataset 'margin' — NOT a separate store)", ["market/margin/<yr>/margin_<date>.parquet"],
         "per open trade_date (2010+)", "single page per date", ["ts_code", "trade_date"], "dense_refuse (2010+)",
         "per-date", "sessions tail"),
    _row("A08", "hk_hold", "FactorDataInitializer northbound leg", ["market/northbound/<yr>/..."],
         "per open trade_date (2017+; nonconnect days sidecar)", "single page per date", ["ts_code", "trade_date"],
         "sparse_canary", "per-date", "sessions tail",
         sidecars=["reference/northbound_nonconnect_days.txt (FIRST-CLASS output)"]),
    _row("A09", "stk_holdernumber", "FactorDataInitializer holder leg", ["corporate/holder_number/*.parquet"],
         "per ann_date window / per stock (bind at build)", "page fallback", ["ts_code", "ann_date", "end_date"],
         "sparse_canary", "periodic consolidation after all constituents verified", "ann_date window"),
    _row("A10", "suspend_d", "fetch_suspend_d_historical (yearly market/suspension/suspension_<yr>.parquet) "
         "+ per-date write_suspend_d store + --ranges-only DERIVED rebuild LAST",
         ["market/suspension/suspension_<yr>.parquet", "market/suspend_d/<yr>/suspend_d_<date>.parquet",
          "market/suspension/suspension_ranges.parquet (derived)"],
         "per year, then per open trade_date", "single page", ["ts_code", "trade_date", "suspend_type"],
         "sparse_canary", "ranges derived only after yearly+per-date verified", "per-date tail"),
    _row("A11", "top_list", "fetch_new_alpha_endpoints top_list leg", ["market/top_list/<yr>/..."],
         "per open trade_date", "single page", ["ts_code", "trade_date"], "sparse_canary", "per-date",
         "sessions tail"),
    _row("A11", "top_inst", "fetch_new_alpha_endpoints top_inst leg", ["market/top_inst/<yr>/..."],
         "per open trade_date (2012+)", "single page", ["ts_code", "trade_date"], "sparse_canary", "per-date",
         "sessions tail"),
    _row("A11", "block_trade", "fetch_new_alpha_endpoints block_trade leg", ["market/block_trade/<yr>/..."],
         "per open trade_date", "single page", ["ts_code", "trade_date"], "sparse_canary", "per-date",
         "sessions tail"),
    _row("A12", "stk_holdertrade", "fetch_new_alpha_endpoints — PER STOCK then yearly consolidation "
         "(current code swallows per-stock failures at line 143 — the ledger gate makes that impossible)",
         ["corporate/stk_holdertrade/stk_holdertrade_<yr>.parquet"], "per ts_code (full history)",
         "per-stock, no offset", ["ts_code", "ann_date", "holder_name"], "sparse_canary",
         "yearly files only after ALL stocks terminal-valid", "ann_date window"),
    _row("A13", "cyq_perf", "fetch_new_alpha_endpoints — PER STOCK, repartitioned to per-date",
         ["market/cyq_perf/<yr>/cyq_perf_<date>.parquet"], "per ts_code (2018+), repartition per-date",
         "per-stock range paging", ["ts_code", "trade_date"], "dense_refuse (2018+)",
         "per-date files only after all stocks verified + repartition row-conserving", "per-stock range tail"),
    _row("A14", "report_rc", "scripts/fetch_bucket_a.py report_rc leg (month-chunked, cap 5000/page)",
         ["analyst/report_rc/report_rc_<yr>.parquet"], "per report_date month", "offset pages to cap; "
         "page-count + termination reason ledgered", ["ts_code", "report_date", "org_name", "quarter"],
         "dense_refuse (2010+)", "yearly consolidation after all months verified; raw_fetch_ts stamped per row",
         "TTL halo replay per Phase 5-A availability contract"),
] + [
    _row("A15", ep, f"scripts/fetch_bucket_a.py {ep} leg", [f"(per bucket-A layout for {ep})"],
         "per period / window (bind at build)", "offset pages", ["ts_code", "(per contract)"],
         "sparse_canary", "per-partition", "ann_date/period window — NEW raw generation identity")
    for ep in ("express", "disclosure_date", "fina_mainbz", "fina_audit", "repurchase", "pledge_stat",
               "top10_floatholders")
] + [
    _row("A16", "broker_recommend", "scripts/fetch_broker_recommend_historical.py (EXISTS; E: paths → inject)",
         ["analyst/broker_recommend/broker_recommend_<YYYYMM>.parquet"], "per month", "single page per month",
         ["month", "broker", "ts_code"], "sparse_canary", "per-month", "monthly tail"),
]
# generated provenance manifests are first-class recovery outputs on EVERY row:
GLOBAL_SIDECARS = ["raw_cache/manifests/* (ingest provenance manifests regenerated during recovery are "
                   "recovery outputs — ledgered + hashed like data files)"]


# ── B1: path authority ───────────────────────────────────────────────────────────────────────────
def _lex_components(p: Path):
    """Lexical components WITHOUT resolving (resolve() would follow a junction before we can see it).
    Includes the LEAF itself — the guard must inspect the exact node it was handed, not only ancestors."""
    q = Path(os.path.normpath(str(p)))
    comps = [Path(q.anchor)]
    for i in range(1, len(q.parts)):
        comps.append(Path(q.anchor).joinpath(*q.parts[1:i + 1]))
    return q, comps


def _reject_reparse_lexical(p: Path) -> None:
    """Inspect every EXISTING component with lstat semantics — a junction/symlink anywhere refuses.
    Inspection failure on an existing component also refuses (fail closed)."""
    _, comps = _lex_components(p)
    for anc in comps:
        try:
            if not anc.exists():
                continue  # not-yet-created components are fine — they'll be created by the authority
            if anc.is_symlink() or (hasattr(anc, "is_junction") and anc.is_junction()):
                raise RuntimeError(f"REFUSED: reparse point in ancestry: {anc}")
        except RuntimeError:
            raise
        except OSError as exc:
            raise RuntimeError(f"REFUSED: cannot inspect {anc}: {exc}")


def validate_run_id(run_id: str) -> str:
    if not _RUN_ID_RE.fullmatch(run_id or ""):
        raise SystemExit(f"REFUSED: invalid run_id {run_id!r} (single component, [A-Za-z0-9][A-Za-z0-9._-]*, "
                         f"max 64 — no separators/UNC/device/ADS/traversal)")
    return run_id


class RecoveryPaths:
    """Injected path authority (GPT re-review B1). Lexical containment FIRST, reparse inspection on
    unresolved components, realpath cross-check second; root/tmp/.lock creation all in here."""

    def __init__(self, run_id: str):
        self.run_id = validate_run_id(run_id)
        candidate = RECOVERY_ROOT / self.run_id
        norm, _ = _lex_components(candidate)
        if norm.parent != Path(os.path.normpath(str(RECOVERY_ROOT))):
            raise SystemExit(f"REFUSED: run root {norm} escapes {RECOVERY_ROOT}")
        _reject_reparse_lexical(norm)
        self.root = norm
        self.staging_data = self.root / "staging_data"
        self.ledger_path = self.root / "ledger" / "recovery_ledger.jsonl"
        self.plan_path = self.root / "ledger" / "request_plan.json"
        self.reports = self.root / "reports"
        self.logs = self.root / "logs"
        self.evidence = self.root / "evidence"

    def create_root(self) -> None:
        _reject_reparse_lexical(self.root.parent)
        self.root.mkdir(parents=True, exist_ok=False)

    def assert_write(self, p: Path) -> Path:
        norm, _ = _lex_components(Path(p) if Path(p).is_absolute() else self.root / p)
        try:
            norm.relative_to(self.root)
        except ValueError:
            raise RuntimeError(f"REFUSED: write target {norm} outside run root {self.root}")
        if str(norm).upper().startswith("E:") or str(norm).upper().startswith("\\\\"):
            raise RuntimeError(f"REFUSED: {norm} on E:/UNC")
        _reject_reparse_lexical(norm.parent if not norm.exists() else norm)
        # belt: realpath must ALSO land inside realpath(root) (catches a reparse racing past the scan)
        rr = Path(os.path.realpath(str(norm)))
        if not str(rr).startswith(os.path.realpath(str(self.root))):
            raise RuntimeError(f"REFUSED: realpath {rr} escaped run root")
        return norm

    def write_json(self, path: Path, obj) -> None:
        path = self.assert_write(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.assert_write(path.with_suffix(path.suffix + f".{os.getpid()}.tmp"))
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, ensure_ascii=False, indent=1)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)

    def _lock(self):
        from filelock import FileLock
        return FileLock(str(self.assert_write(Path(str(self.ledger_path) + ".lock"))))


# ── B3: typed, transition-enforced ledger ─────────────────────────────────────────────────────────
LEDGER_KINDS = {
    "lifecycle": {"event"},                                     # run_created / plan_frozen / preflight_ok...
    "attempt": {"request_id", "endpoint", "params", "page", "termination", "response_ts"},
    "verdict": {"request_id", "state"},                         # + per-state evidence below
}
_TERMINAL = {"verified", "confirmed_empty"}
_TRANSITIONS = {None: {"planned"}, "planned": {"fetched", "failed"},
                "fetched": {"verified", "confirmed_empty", "failed"},
                "failed": {"fetched"},  # retry re-fetches; failed is never terminal-valid
                "verified": set(), "confirmed_empty": set()}


def request_id(endpoint: str, params: dict, partition: str) -> str:
    canon = json.dumps({"e": endpoint, "p": params, "part": partition}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canon.encode()).hexdigest()[:24]


class RecoveryLedger:
    """Read-check-append under the run file lock. Torn/malformed tail = fail closed. Verdicts are
    validated against the FROZEN request plan + the actual output on disk."""

    def __init__(self, rp: RecoveryPaths):
        self.rp = rp

    def _load(self) -> list:
        p = self.rp.ledger_path
        if not p.exists():
            return []
        rows = []
        raw = p.read_text(encoding="utf-8")
        for i, line in enumerate(raw.splitlines()):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                raise RuntimeError(f"REFUSED: ledger torn/malformed at line {i + 1} — manual inspection required")
            kind = row.get("kind")
            if kind not in LEDGER_KINDS or not LEDGER_KINDS[kind] <= set(row):
                raise RuntimeError(f"REFUSED: ledger row {i + 1} malformed for kind={kind!r}")
            rows.append(row)
        return rows

    def _append(self, row: dict) -> None:
        p = self.rp.assert_write(self.rp.ledger_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": datetime.now().isoformat(timespec="seconds"), **row},
                                ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def event(self, name: str, **kw) -> None:
        with self.rp._lock():
            self._load()
            self._append({"kind": "lifecycle", "event": name, **kw})

    def freeze_plan(self, plan_rows: list) -> str:
        """plan_rows: [{request_id, endpoint, dataset, params, partition, empty_policy}]. Hash-frozen
        BEFORE the first API call; requests outside the plan are refused forever after."""
        with self.rp._lock():
            if self.rp.plan_path.exists():
                raise RuntimeError("REFUSED: request plan already frozen for this run")
            for r in plan_rows:
                need = {"request_id", "endpoint", "dataset", "params", "partition", "empty_policy"}
                if not need <= set(r):
                    raise RuntimeError(f"REFUSED: plan row missing {need - set(r)}")
            blob = json.dumps(plan_rows, sort_keys=True, ensure_ascii=False)
            sha = hashlib.sha256(blob.encode()).hexdigest()
            self.rp.write_json(self.rp.plan_path, {"sha256": sha, "rows": plan_rows})
            self._append({"kind": "lifecycle", "event": "plan_frozen", "plan_sha256": sha,
                          "request_count": len(plan_rows)})
            return sha

    def _plan(self) -> dict:
        if not self.rp.plan_path.exists():
            raise RuntimeError("REFUSED: no frozen request plan")
        plan = json.loads(self.rp.plan_path.read_text(encoding="utf-8"))
        blob = json.dumps(plan["rows"], sort_keys=True, ensure_ascii=False)
        if hashlib.sha256(blob.encode()).hexdigest() != plan["sha256"]:
            raise RuntimeError("REFUSED: request plan hash mismatch (tampered)")
        return {r["request_id"]: r for r in plan["rows"]}

    def _state_of(self, rows: list, rid: str):
        st = "planned" if rid in self._plan() else None
        for r in rows:
            if r.get("request_id") != rid:
                continue
            if r["kind"] == "attempt":
                st = "fetched" if r.get("termination") == "success" else "failed"
            elif r["kind"] == "verdict":
                st = r["state"]
        return st

    def record_attempt(self, rid: str, endpoint: str, params: dict, page: int, termination: str,
                       response_ts: str, raw_page_sha256: str = "", exception: str = "") -> None:
        with self.rp._lock():
            rows = self._load()
            plan = self._plan()
            if rid not in plan:
                raise RuntimeError(f"REFUSED: request {rid} not in the frozen plan")
            cur = self._state_of(rows, rid)
            if cur in _TERMINAL:
                raise RuntimeError(f"REFUSED: request {rid} already terminal ({cur})")
            self._append({"kind": "attempt", "request_id": rid, "endpoint": endpoint, "params": params,
                          "page": page, "termination": termination, "response_ts": response_ts,
                          "raw_page_sha256": raw_page_sha256, "exception": exception})

    def record_verdict(self, rid: str, state: str, *, output_path: str = "", output_sha256: str = "",
                       schema_fingerprint: str = "", key_stats: dict | None = None,
                       canary_request_id: str = "", repeat_confirmed: bool = False) -> None:
        with self.rp._lock():
            rows = self._load()
            plan = self._plan()
            if rid not in plan:
                raise RuntimeError(f"REFUSED: request {rid} not in the frozen plan")
            cur = self._state_of(rows, rid)
            if state not in _TRANSITIONS.get(cur, set()):
                raise RuntimeError(f"REFUSED: invalid transition {cur} -> {state} for {rid}")
            if state == "verified":
                out = Path(output_path)
                ok = output_path and out.is_file()
                if ok:
                    self.rp.assert_write(out)  # containment
                    ok = sha256_file(out) == output_sha256 and bool(schema_fingerprint) and key_stats is not None
                if not ok:
                    raise RuntimeError(f"REFUSED: 'verified' without a contained, hash-matching output "
                                       f"+ schema fingerprint + key stats ({rid})")
            if state == "confirmed_empty":
                pol = plan[rid].get("empty_policy")
                if pol != "sparse_canary":
                    raise RuntimeError(f"REFUSED: dataset is {pol} — an empty result can NEVER be accepted ({rid})")
                if not canary_request_id or not repeat_confirmed:
                    raise RuntimeError(f"REFUSED: confirmed_empty needs a same-session nonempty canary "
                                       f"request id AND a repeated identical empty query ({rid})")
            self._append({"kind": "verdict", "request_id": rid, "state": state, "output_path": output_path,
                          "output_sha256": output_sha256, "schema_fingerprint": schema_fingerprint,
                          "key_stats": key_stats or {}, "canary_request_id": canary_request_id,
                          "repeat_confirmed": repeat_confirmed})

    def consolidation_allowed(self, dataset: str):
        rows = self._load()
        plan = self._plan()
        pend = [rid for rid, r in plan.items() if r["dataset"] == dataset
                and self._state_of(rows, rid) not in _TERMINAL]
        return (len(pend) == 0, pend)


# ── B4: structural doc-contract gate ─────────────────────────────────────────────────────────────
CONTRACT_REQUIRED = ("doc_path", "doc_sha256", "required_fields", "natural_key", "pagination",
                     "rate_limit", "cadence", "pit_anchors", "empty_policy", "reviewed_by", "reviewed_at")


def contract_errors(endpoint: str, c: dict) -> list:
    errs = []
    if not isinstance(c, dict) or not c:
        return [f"{endpoint}: contract missing/empty"]
    for k in CONTRACT_REQUIRED:
        v = c.get(k)
        if v in (None, [], {}) or (isinstance(v, str) and v.strip().lower() in _PLACEHOLDERS):
            errs.append(f"{endpoint}: field {k} missing/placeholder")
    if errs:
        return errs
    # doc under the offline mirror, no traversal/reparse, hash recomputed
    doc = Path(os.path.normpath(str(E_ROOT / c["doc_path"])))
    try:
        doc.relative_to(DOC_MIRROR)
    except ValueError:
        errs.append(f"{endpoint}: doc_path escapes the offline mirror ({doc})")
        return errs
    try:
        _reject_reparse_lexical(doc)
    except RuntimeError as e:
        return [f"{endpoint}: {e}"]
    if not doc.is_file():
        errs.append(f"{endpoint}: doc file missing: {doc}")
    elif sha256_file(doc) != str(c["doc_sha256"]).lower():
        errs.append(f"{endpoint}: doc_sha256 mismatch (doc changed since review)")
    if not isinstance(c["required_fields"], list) or len(c["required_fields"]) < 2:
        errs.append(f"{endpoint}: required_fields must be a real field list")
    if not isinstance(c["natural_key"], list) or not c["natural_key"]:
        errs.append(f"{endpoint}: natural_key must be a non-empty list")
    if c["empty_policy"] not in ("dense_refuse", "sparse_canary"):
        errs.append(f"{endpoint}: empty_policy must be dense_refuse|sparse_canary")
    if len(str(c["reviewed_by"]).strip()) < 3:
        errs.append(f"{endpoint}: reviewed_by placeholder")
    try:
        ts = datetime.fromisoformat(str(c["reviewed_at"]))
        if ts.replace(tzinfo=ts.tzinfo or timezone.utc) > datetime.now(timezone.utc):
            errs.append(f"{endpoint}: reviewed_at in the future")
    except ValueError:
        errs.append(f"{endpoint}: reviewed_at not ISO-parseable")
    return errs


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_baseline() -> dict:
    got = sha256_file(MANIFEST)
    if got != MANIFEST_SHA256:
        raise RuntimeError(f"baseline manifest sha256 {got} != pinned — refusing")
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["profiled_datasets"]


def open_run(run_id: str, *, new: bool) -> tuple:
    rp = RecoveryPaths(run_id)
    led = RecoveryLedger(rp)
    if new:
        if rp.root.exists():
            raise SystemExit(f"REFUSED: run {run_id} already exists — immutable runs")
        rp.create_root()
        led.event("run_created", run_id=run_id, baseline_manifest_sha256=MANIFEST_SHA256,
                  live_provider_source_commit=LIVE_PROVIDER_SOURCE_COMMIT)
    else:
        if not rp.root.exists():
            raise SystemExit(f"REFUSED: run {run_id} does not exist")
        rows = led._load()
        created = next((r for r in rows if r.get("event") == "run_created"), None)
        if not created or created.get("run_id") != run_id \
                or created.get("baseline_manifest_sha256") != MANIFEST_SHA256:
            raise SystemExit("REFUSED: resume without a valid run_created record matching this run id "
                             "and the pinned baseline (GPT B1 resume rule)")
    return rp, led


# ── modes (network-free) ─────────────────────────────────────────────────────────────────────────
def cmd_inventory(rp: RecoveryPaths, led: RecoveryLedger) -> int:
    base = load_baseline()
    sys.path.insert(0, str(E_ROOT / "src"))
    from data_infra.pit_backend import DATASET_SPECS
    import glob as _g
    rows, lost_rows = [], 0
    for name, prof in sorted(base.items()):
        spec = DATASET_SPECS.get(name)
        pat = getattr(spec, "raw_pattern", "") if spec else ""
        live = len(_g.glob(str(E_DATA / pat), recursive=True)) if pat else 0
        presence = "present_count_scan" if (live and live >= prof.get("file_count", 0)) else (
            "partial_count_scan" if live else "lost")
        if presence != "present_count_scan":
            lost_rows += prof.get("row_count", 0)
        rows.append({"dataset": name, "baseline_files": prof.get("file_count"),
                     "baseline_rows": prof.get("row_count"), "live_files": live, "presence": presence})
    inv = {"note": "presence = COARSE COUNT SCAN; restoration proof = frozen plan + typed ledger + profiler",
           "baseline": {"manifest": str(MANIFEST), "sha256": MANIFEST_SHA256},
           "lost_rows_estimate": lost_rows, "datasets": rows,
           "endpoint_matrix_rows": len(ENDPOINT_MATRIX), "global_sidecars": GLOBAL_SIDECARS,
           "irrecoverable_evidence": [{"id": a, "why": b} for a, b in IRRECOVERABLE]}
    rp.write_json(rp.reports / "inventory.json", inv)
    print(f"lost-estimate {lost_rows:,} rows across "
          f"{len([r for r in rows if r['presence'] == 'lost'])} datasets; matrix {len(ENDPOINT_MATRIX)} rows; "
          f"report -> {rp.reports / 'inventory.json'}")
    return 0


def cmd_preflight(rp: RecoveryPaths, led: RecoveryLedger) -> int:
    free_gb = shutil.disk_usage(str(RECOVERY_ROOT.drive + "\\"))[2] // 2**30
    if free_gb < MIN_STAGING_FREE_GB:
        print(f"FAIL: C: free {free_gb}GB < {MIN_STAGING_FREE_GB}GB")
        return 2
    manifest_rows, ev_rows = [], []
    for tree in SURVIVOR_TREES:
        for src in sorted((E_DATA / tree).rglob("*")):
            if not src.is_file():
                continue
            rel = src.relative_to(E_DATA)
            dst = rp.assert_write(rp.staging_data / rel)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            manifest_rows.append({"path": str(rel).replace("\\", "/"), "sha256": sha256_file(dst),
                                  "size": dst.stat().st_size})
    import glob as _g
    for pat in EVIDENCE_GLOBS:
        for f in _g.glob(str(E_ROOT / pat), recursive=True):
            fp = Path(f)
            if fp.is_file():
                rel = fp.relative_to(E_ROOT)
                dst = rp.assert_write(rp.evidence / rel)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(fp, dst)
                ev_rows.append({"path": str(rel).replace("\\", "/"), "sha256": sha256_file(dst)})
    import pandas as pd
    base = load_baseline()
    for name, rel in (("trade_cal", "reference/trade_cal.parquet"), ("stock_basic", "reference/stock_basic.parquet")):
        if len(pd.read_parquet(rp.staging_data / rel)) < base[name]["row_count"]:
            print(f"FAIL: staged {name} shrank vs baseline")
            return 2
    rp.write_json(rp.reports / "survivor_manifest.json", {"files": manifest_rows, "evidence": ev_rows})
    led.event("preflight_ok", c_free_gb=free_gb, survivor_files=len(manifest_rows), evidence_files=len(ev_rows))
    print(f"preflight OK: {len(manifest_rows)} survivor files, {len(ev_rows)} evidence files, C: {free_gb}GB")
    return 0


def cmd_plan(rp: RecoveryPaths, led: RecoveryLedger) -> int:
    import yaml
    contracts = yaml.safe_load(CONTRACTS_YAML.read_text(encoding="utf-8")) or {} if CONTRACTS_YAML.exists() else {}
    owners: dict = {}
    problems = 0
    for row in ENDPOINT_MATRIX:
        key = (row["endpoint"], tuple(row["outputs"]))
        owners.setdefault(key, []).append(row["owner"])
    dup = {k: v for k, v in owners.items() if len(set(v)) > 1}
    if dup:
        print(f"MATRIX ERROR: multiple owners: {dup}")
        problems += 1
    for row in ENDPOINT_MATRIX:
        for ep in row["endpoint"].replace("(q)", "").split("+"):
            errs = contract_errors(ep.strip(), contracts.get(ep.strip(), {}))
            state = "BLOCKED" if errs else "contract-OK"
            if errs:
                problems += 1
            print(f"  {row['owner']:<5} {ep.strip():<22} {state}")
    print(f"\n{problems} blocked/problem rows; fetch remains REFUSED (adapters unbuilt; contracts unreviewed; "
          f"§13 pending). Contract review MUST precede that endpoint's adapter logic (GPT M3).")
    return 0


def cmd_fetch(_rp, _led) -> int:
    print("REFUSED: no fetch adapter exists. Order (GPT answer 7): containment/ledger fixes -> contract "
          "review+sign per endpoint -> adapters from the unique-owner matrix -> pre-fetch test matrix -> "
          "explicit user fetch authorization.", file=sys.stderr)
    return 3


def main() -> int:
    ap = argparse.ArgumentParser(description="C:-staged raw-store recovery coordinator v3 (fetch §13-gated)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--new-run", metavar="RUN_ID")
    g.add_argument("--run", metavar="RUN_ID")
    ap.add_argument("--inventory", action="store_true")
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--fetch", action="store_true")
    a = ap.parse_args()
    rp, led = open_run(a.new_run or a.run, new=bool(a.new_run))
    if a.inventory:
        return cmd_inventory(rp, led)
    if a.preflight:
        return cmd_preflight(rp, led)
    if a.plan:
        return cmd_plan(rp, led)
    if a.fetch:
        return cmd_fetch(rp, led)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
