# SCRIPT_STATUS: ACTIVE — 2026-07-13 junction-deletion incident: C:-staged raw-store recovery coordinator (v3.1)
"""Recovery coordinator v3.1 (post GPT recovery re-review #3 REWORK — RAW_STORE_RECOVERY_PLAN.md v4).

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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from recovery_write_broker import (NoFollowWriteBroker, WriteBrokerError,  # noqa: E402
                                   assert_no_reparse_source, walk_no_follow)

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

# ── B2/M1: typed endpoint matrix — ONE row per (endpoint, query_mode, output_family) ───────────────
# Every `callable` is UNBOUND (GPT re-review #3 M1): exact method binding follows contract review, and
# adapter construction stays BLOCKED until it is pinned. `row_identity_key` = the true per-row unique
# key; `agg_key` = the coarser profiling key; `baseline_dups` = duplicate rows the manifest legitimately
# holds under agg_key (a per-agg-key count check, NOT uniqueness, for multi-row event datasets). empty:
# dense_refuse (an empty response can NEVER be accepted) | sparse_canary (needs a verified nonempty
# same-endpoint canary + >=2 stored empty receipts).
def _row(owner, endpoint, query_mode, outputs, row_identity_key, agg_key, empty, tail_rule,
         *, baseline_dups=False, callable_="UNBOUND (bind post-contract)", note="", sidecars=()):
    return {"owner": owner, "endpoint": endpoint, "query_mode": query_mode, "callable": callable_,
            "outputs": outputs, "row_identity_key": row_identity_key, "agg_key": agg_key,
            "empty": empty, "tail_rule": tail_rule, "baseline_dups": baseline_dups, "note": note,
            "sidecars": list(sidecars)}


ENDPOINT_MATRIX = [
    _row("A01", "daily", "per_open_trade_date", ["market/daily/<yr>/daily_<date>.parquet"],
         ["ts_code", "trade_date"], ["ts_code", "trade_date"], "dense_refuse", "sessions 20260702..last-complete",
         note="bypass init_market_data.main() (always refetches reference); merges daily_basic+adj_factor"),
    _row("A02", "index_daily", "per_index_range", ["market/index/index_<code>.parquet"],
         ["ts_code", "trade_date"], ["ts_code", "trade_date"], "dense_refuse", "range end -> last-complete",
         note="per-index RANGE fetch, NOT per trade_date"),
    _row("A03", "income", "per_stock", ["fundamentals/income/*.parquet"], ["ts_code", "end_date", "report_type"],
         ["ts_code", "end_date"], "sparse_canary", "ann_date calendar-day window",
         note="download_fundamentals uses pro.income (STANDARD, not income_vip); income+balancesheet+dividend "
              "fetched together per stock — split into 3 rows"),
    _row("A03", "balancesheet", "per_stock", ["fundamentals/balancesheet/*.parquet"],
         ["ts_code", "end_date", "report_type"], ["ts_code", "end_date"], "sparse_canary",
         "ann_date window", note="pro.balancesheet (STANDARD, not VIP)"),
    _row("A03", "dividend", "per_stock", ["corporate/dividends/*.parquet"], ["ts_code", "end_date", "div_proc"],
         ["ts_code", "end_date"], "sparse_canary", "ann_date window", baseline_dups=True,
         note="multiple dividend records per (ts_code,end_date)"),
    _row("A04", "income_vip", "per_period_report_type", ["fundamentals/income_quarterly/*.parquet"],
         ["ts_code", "end_date", "report_type"], ["ts_code", "end_date", "report_type"], "dense_refuse",
         "current period via ann_date window", note="fetch_quarterly_statements direct-quarter combine"),
    _row("A04", "cashflow_vip", "per_period_report_type", ["fundamentals/cashflow_quarterly/*.parquet"],
         ["ts_code", "end_date", "report_type"], ["ts_code", "end_date", "report_type"], "dense_refuse",
         "ann_date window", note="direct-quarter"),
    _row("A05", "cashflow", "per_stock", ["fundamentals/cashflow/*.parquet"], ["ts_code", "end_date", "report_type"],
         ["ts_code", "end_date"], "dense_refuse", "ann_date window",
         note="init_factor scope (CLAUDE §6.2); driver iterates PER STOCK (not per period)"),
    _row("A06", "forecast", "per_stock", ["fundamentals/forecast/*.parquet"], ["ts_code", "end_date", "ann_date", "type"],
         ["ts_code", "end_date"], "sparse_canary", "ann_date window", baseline_dups=True,
         note="init_factor; PER STOCK iteration; multiple forecast rows per (ts_code,end_date)"),
    _row("A07", "fina_indicator_vip", "per_period", ["fundamentals/indicators/*.parquet"],
         ["ts_code", "end_date", "update_flag"], ["ts_code", "end_date"], "dense_refuse", "current period refresh",
         baseline_dups=True, note="SOLE indicator owner (refresh_indicator_history); update_flag revisions => "
         "multiple rows per (ts_code,end_date); historical staged archives = IRRECOVERABLE evidence"),
    _row("A08", "moneyflow", "per_open_trade_date", ["market/moneyflow/<yr>/moneyflow_<date>.parquet"],
         ["ts_code", "trade_date"], ["ts_code", "trade_date"], "sparse_canary", "sessions tail",
         sidecars=["reference/moneyflow_known_empty_dates.txt (FIRST-CLASS recovery output)"]),
    _row("A08", "stk_limit", "per_open_trade_date", ["market/stk_limit/<yr>/stk_limit_<date>.parquet"],
         ["ts_code", "trade_date"], ["ts_code", "trade_date"], "dense_refuse", "sessions tail"),
    _row("A08", "margin_detail", "per_open_trade_date", ["market/margin/<yr>/margin_<date>.parquet"],
         ["ts_code", "trade_date"], ["ts_code", "trade_date"], "dense_refuse", "sessions tail",
         note="lands in market/margin/ = manifest dataset 'margin' (NOT a separate store); 2010+"),
    _row("A08", "hk_hold", "per_open_trade_date", ["market/northbound/<yr>/..."], ["ts_code", "trade_date"],
         ["ts_code", "trade_date"], "sparse_canary", "sessions tail",
         sidecars=["reference/northbound_nonconnect_days.txt (FIRST-CLASS recovery output)"]),
    _row("A09", "stk_holdernumber", "per_stock", ["corporate/holder_number/*.parquet"],
         ["ts_code", "ann_date", "end_date"], ["ts_code", "end_date"], "sparse_canary", "ann_date window",
         note="init_factor; PER STOCK iteration"),
    _row("A10", "suspend_d", "per_year_then_per_date",
         ["market/suspension/suspension_<yr>.parquet", "market/suspend_d/<yr>/suspend_d_<date>.parquet"],
         ["ts_code", "trade_date", "suspend_type"], ["ts_code", "trade_date"], "sparse_canary", "per-date tail",
         note="suspension_ranges.parquet is DERIVED via --ranges-only AFTER yearly+per-date verified"),
    _row("A11", "top_list", "per_open_trade_date", ["market/top_list/<yr>/..."], ["ts_code", "trade_date", "reason"],
         ["ts_code", "trade_date"], "sparse_canary", "sessions tail", baseline_dups=True,
         note="multi-row event: multiple list reasons per (ts_code,trade_date)"),
    _row("A11", "top_inst", "per_open_trade_date", ["market/top_inst/<yr>/..."], ["ts_code", "trade_date", "exalter"],
         ["ts_code", "trade_date"], "sparse_canary", "sessions tail", baseline_dups=True,
         note="MULTI-ROW event: baseline has 2,636,668 rows dup under (ts_code,trade_date) — per-seat rows; "
              "row_identity_key adds exalter"),
    _row("A11", "block_trade", "per_open_trade_date", ["market/block_trade/<yr>/..."],
         ["ts_code", "trade_date", "buyer", "seller", "price"], ["ts_code", "trade_date"], "sparse_canary",
         "sessions tail", baseline_dups=True, note="MULTI-ROW event: baseline 180,262 dup rows under 2-col key"),
    _row("A12", "stk_holdertrade", "per_stock", ["corporate/stk_holdertrade/stk_holdertrade_<yr>.parquet"],
         ["ts_code", "ann_date", "holder_name", "in_de"], ["ts_code", "ann_date"], "sparse_canary", "ann_date window",
         baseline_dups=True, note="PER STOCK; current fetch_new_alpha_endpoints swallows per-stock failures "
         "(line 143) — the ledger gate makes a silent partial impossible"),
    _row("A13", "cyq_perf", "per_stock_repartition_per_date", ["market/cyq_perf/<yr>/cyq_perf_<date>.parquet"],
         ["ts_code", "trade_date"], ["ts_code", "trade_date"], "dense_refuse", "per-stock range tail",
         note="PER STOCK (2018+), repartitioned to per-date; repartition must be row-conserving"),
    _row("A14", "report_rc", "per_report_date_month", ["analyst/report_rc/report_rc_<yr>.parquet"],
         ["ts_code", "report_date", "org_name", "author_name", "quarter"], ["ts_code", "report_date"],
         "dense_refuse", "TTL halo replay per Phase 5-A", baseline_dups=True,
         note="doc cap = 3000/page (NOT 5000); natural_key INCLUDES author_name (pit_backend canonical); "
              "raw_fetch_ts stamped per row; NEW raw generation — provider bins PRESERVED as legacy (§5)"),
] + [
    _row("A15", ep, "UNBOUND", ["UNBOUND"], ["UNBOUND"], ["UNBOUND"], "sparse_canary", "UNBOUND",
         note="query_mode/keys/outputs UNRESOLVED until the contract is signed (was a placeholder row)")
    for ep in ("express", "disclosure_date", "fina_mainbz", "fina_audit", "repurchase", "pledge_stat",
               "top10_floatholders")
] + [
    _row("A16", "broker_recommend", "per_month", ["analyst/broker_recommend/broker_recommend_<YYYYMM>.parquet"],
         ["month", "broker", "ts_code"], ["month", "broker"], "sparse_canary", "monthly tail",
         note="fetch_broker_recommend_historical EXISTS; inject E: paths"),
]
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


import stat as _stat
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400


def _reparse_state(anc: Path):
    """True=reparse point, False=plain existing, None=truly absent — via os.lstat (NEVER follows the
    target; Path.exists() follows a junction and returns False for a BROKEN one, skipping it — GPT
    re-review #3 B3). Only FileNotFoundError means absent; any other OSError => caller fails closed."""
    try:
        st = os.lstat(anc)
    except FileNotFoundError:
        return None
    if (getattr(st, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT) or _stat.S_ISLNK(st.st_mode):
        return True
    return False


def _reject_reparse_lexical(p: Path) -> None:
    """Reject a reparse point at ANY component (incl. a BROKEN junction) — os.lstat, no follow. An
    lstat error other than FileNotFoundError refuses (fail closed)."""
    _, comps = _lex_components(p)
    for anc in comps:
        try:
            r = _reparse_state(anc)
        except OSError as exc:
            raise RuntimeError(f"REFUSED: cannot lstat {anc}: {exc}")
        if r is True:
            raise RuntimeError(f"REFUSED: reparse point in ancestry: {anc}")


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

    def broker(self) -> NoFollowWriteBroker:
        """The handle-based no-follow write broker (GPT B3) — the ONLY sanctioned write surface. Every
        write-capable mode requires it; if it can't be constructed (non-Windows / missing API) the write
        FAILS CLOSED. Constructed lazily (the run root must exist first)."""
        b = getattr(self, "_broker", None)
        if b is None:
            b = NoFollowWriteBroker(self.root)  # raises WriteBrokerError -> fail closed
            self._broker = b
        return b

    def assert_write(self, p: Path) -> Path:
        norm, _ = _lex_components(Path(p) if Path(p).is_absolute() else self.root / p)
        try:
            norm.relative_to(self.root)
        except ValueError:
            raise RuntimeError(f"REFUSED: write target {norm} outside run root {self.root}")
        if str(norm).upper().startswith("E:") or str(norm).upper().startswith("\\\\"):
            raise RuntimeError(f"REFUSED: {norm} on E:/UNC")
        _reject_reparse_lexical(norm)  # cheap lexical pre-check (lstat, no follow)
        # AUTHORITATIVE check: handle-based no-follow ancestry validation (closes the scan->write TOCTOU
        # + broken-junction realpath escape). Fails closed if the broker is unavailable (GPT #4 B3).
        self.broker().validate_ancestry(norm)
        return norm

    def write_json(self, path: Path, obj) -> None:
        path = self.assert_write(path)
        b = self.broker()
        tmp = self.assert_write(path.with_suffix(path.suffix + f".{os.getpid()}.tmp"))
        with b.open_for_write(tmp, "w") as fh:  # broker validates + creates parents no-follow
            json.dump(obj, fh, ensure_ascii=False, indent=1)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)

    def _lock(self):
        from filelock import FileLock
        lock_path = self.assert_write(Path(str(self.ledger_path) + ".lock"))
        self.broker().mkdirs(lock_path.parent)
        return FileLock(str(lock_path))


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
        with self.rp.broker().open_for_write(p, "a") as fh:  # no-follow validated append
            fh.write(json.dumps({"at": datetime.now().isoformat(timespec="seconds"), **row},
                                ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def event(self, name: str, **kw) -> None:
        with self.rp._lock():
            self._load()
            self._append({"kind": "lifecycle", "event": name, **kw})

    def freeze_plan(self, plan_rows: list) -> str:
        """plan_rows: each REQUIRES request_id, endpoint, dataset, params, partition, empty_policy,
        expected_output (staging-relative path this request must write), natural_key (from the signed
        contract). Frozen ONCE; the request_id must equal request_id(endpoint,params,partition) — a
        mislabelled row refuses; duplicate ids refuse (GPT re-review #3 B2). Endpoint/params/output are
        thereafter derived from HERE, never from the caller."""
        with self.rp._lock():
            if self.rp.plan_path.exists():
                raise RuntimeError("REFUSED: request plan already frozen for this run")
            seen = set()
            for r in plan_rows:
                need = {"request_id", "endpoint", "dataset", "params", "partition", "empty_policy",
                        "expected_output", "natural_key"}
                if not need <= set(r):
                    raise RuntimeError(f"REFUSED: plan row missing {need - set(r)}")
                if r["request_id"] != request_id(r["endpoint"], r["params"], r["partition"]):
                    raise RuntimeError(f"REFUSED: request_id does not match endpoint+params+partition ({r['request_id']})")
                if r["request_id"] in seen:
                    raise RuntimeError(f"REFUSED: duplicate request_id {r['request_id']}")
                if r["empty_policy"] not in ("dense_refuse", "sparse_canary"):
                    raise RuntimeError(f"REFUSED: bad empty_policy {r['empty_policy']}")
                seen.add(r["request_id"])
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
                st = "failed" if r.get("exception") else "fetched"  # termination is the PAGE reason, not the state
            elif r["kind"] == "verdict":
                st = r["state"]
        return st

    def record_attempt(self, rid: str, *, page: int, row_count: int, termination: str,
                       response_ts: str, raw_page_sha256: str, exception: str = "") -> None:
        """An attempt receipt. endpoint/params are DERIVED from the frozen plan (not accepted from the
        caller — GPT re-review #3 B2). row_count + raw_page_sha256 are the page receipt used later to
        prove contiguous coverage / a real empty."""
        with self.rp._lock():
            rows = self._load()
            plan = self._plan()
            if rid not in plan:
                raise RuntimeError(f"REFUSED: request {rid} not in the frozen plan")
            cur = self._state_of(rows, rid)
            if cur in _TERMINAL:
                raise RuntimeError(f"REFUSED: request {rid} already terminal ({cur})")
            row = plan[rid]
            self._append({"kind": "attempt", "request_id": rid, "endpoint": row["endpoint"],
                          "params": row["params"], "page": int(page), "row_count": int(row_count),
                          "termination": termination, "response_ts": response_ts,
                          "raw_page_sha256": raw_page_sha256, "exception": exception})

    def _attempts(self, rows, rid):
        return [r for r in rows if r.get("kind") == "attempt" and r.get("request_id") == rid]

    def _profile_output(self, out: Path, natural_key: list) -> dict:
        """Independently open the output and compute schema + key stats — never trust caller strings."""
        import pandas as pd
        df = pd.read_parquet(out)  # raises if not a real parquet (kills the b"DATA" probe)
        schema = ";".join(f"{c}:{df[c].dtype}" for c in sorted(map(str, df.columns)))
        fp = hashlib.sha256(schema.encode()).hexdigest()[:16]
        miss = [k for k in natural_key if k not in df.columns]
        if miss:
            raise RuntimeError(f"output missing natural-key columns {miss}")
        null_keys = int(df[natural_key].isna().any(axis=1).sum())
        dup_groups = int(df.duplicated(subset=natural_key).sum())
        return {"rows": int(len(df)), "schema_fingerprint": fp, "null_keys": null_keys,
                "dup_groups": dup_groups, "sha256": sha256_file(out)}

    def record_verdict(self, rid: str, state: str, *, output_path: str = "", canary_request_id: str = "") -> None:
        with self.rp._lock():
            rows = self._load()
            plan = self._plan()
            if rid not in plan:
                raise RuntimeError(f"REFUSED: request {rid} not in the frozen plan")
            row = plan[rid]
            cur = self._state_of(rows, rid)
            if state not in _TRANSITIONS.get(cur, set()):
                raise RuntimeError(f"REFUSED: invalid transition {cur} -> {state} for {rid}")
            evidence = {}
            if state == "verified":
                exp = self.rp.assert_write(self.rp.staging_data / row["expected_output"])
                if Path(os.path.normpath(output_path)) != exp:
                    raise RuntimeError(f"REFUSED: output_path != the plan-bound expected_output ({rid})")
                if not exp.is_file():
                    raise RuntimeError(f"REFUSED: 'verified' but the bound output is missing ({rid})")
                atts = self._attempts(rows, rid)
                if not any(a.get("termination") in ("single_page", "last_page", "complete") for a in atts):
                    raise RuntimeError(f"REFUSED: 'verified' without a proven termination attempt ({rid})")
                prof = self._profile_output(exp, list(row["natural_key"]))  # INDEPENDENT computation
                if prof["rows"] == 0 and row["empty_policy"] == "dense_refuse":
                    raise RuntimeError(f"REFUSED: dense dataset verified with 0 rows ({rid})")
                evidence = prof
            if state == "confirmed_empty":
                if row["empty_policy"] != "sparse_canary":
                    raise RuntimeError(f"REFUSED: dense dataset — an empty result can NEVER be accepted ({rid})")
                empties = [a for a in self._attempts(rows, rid) if int(a.get("row_count", -1)) == 0]
                if len(empties) < 2:
                    raise RuntimeError(f"REFUSED: confirmed_empty needs >=2 stored empty response receipts ({rid})")
                can = plan.get(canary_request_id)
                if not can or can["endpoint"] != row["endpoint"]:
                    raise RuntimeError(f"REFUSED: canary must be a planned SAME-endpoint request ({rid})")
                cstate = self._state_of(rows, canary_request_id)
                cnonempty = any(int(a.get("row_count", 0)) > 0 for a in self._attempts(rows, canary_request_id))
                if cstate != "verified" or not cnonempty:
                    raise RuntimeError(f"REFUSED: canary {canary_request_id} must be verified AND nonempty ({rid})")
            self._append({"kind": "verdict", "request_id": rid, "state": state, "output_path": output_path,
                          "canary_request_id": canary_request_id, "evidence": evidence})

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
    elif any(str(x).strip().lower() in _PLACEHOLDERS for x in c["required_fields"]):
        errs.append(f"{endpoint}: required_fields contains placeholder elements (['x',...])")
    if not isinstance(c["natural_key"], list) or not c["natural_key"]:
        errs.append(f"{endpoint}: natural_key must be a non-empty list")
    elif any(str(x).strip().lower() in _PLACEHOLDERS for x in c["natural_key"]):
        errs.append(f"{endpoint}: natural_key contains placeholder elements")
    # NOTE: required_fields ⊆ the pinned doc's field list + typed pagination/limit parsing are the
    # adapter-phase deepening (they need the doc parsed); this structural gate blocks placeholders.
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
    b = rp.broker()  # fail closed here if the no-follow broker is unavailable (before any write)
    manifest_rows, ev_rows = [], []
    for tree in SURVIVOR_TREES:
        for src in sorted(walk_no_follow(E_DATA / tree)):  # refuses a reparse point in the SOURCE tree
            rel = src.relative_to(E_DATA)
            dst = rp.assert_write(rp.staging_data / rel)
            b.copy_into(src, dst)  # no-follow source + broker-validated dest
            manifest_rows.append({"path": str(rel).replace("\\", "/"), "sha256": sha256_file(dst),
                                  "size": dst.stat().st_size})
    import glob as _g
    for pat in EVIDENCE_GLOBS:
        for f in _g.glob(str(E_ROOT / pat), recursive=True):
            fp = Path(f)
            if fp.is_file():
                assert_no_reparse_source(fp)
                rel = fp.relative_to(E_ROOT)
                dst = rp.assert_write(rp.evidence / rel)
                b.copy_into(fp, dst)
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
        ep = row["endpoint"]
        unbound = row["callable"].startswith("UNBOUND")
        errs = contract_errors(ep, contracts.get(ep, {}))
        state = "BLOCKED(contract)" if errs else ("BLOCKED(UNBOUND callable)" if unbound else "ready")
        if errs or unbound:
            problems += 1
        print(f"  {row['owner']:<5} {ep:<22} {state}")
    print(f"\n{problems} blocked/problem rows; fetch remains REFUSED (adapters unbuilt; contracts unreviewed; "
          f"§13 pending). Contract review MUST precede that endpoint's adapter logic (GPT M3).")
    return 1 if problems else 0  # nonzero while any row is blocked (GPT re-review #3 M2)


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
