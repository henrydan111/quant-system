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
- M1: ENDPOINT_MATRIX is a TYPED `EndpointRow` table — one row per physical `output_family`, owned by
  EXACTLY ONE row (assert_unique_output_owner). Each row declares `source_endpoints` (the API calls the
  output requires — A01 market/daily draws daily+daily_basic+adj_factor), `vendor_record_key` (true
  per-row identity), `pit_version_key` (ann_date/f_ann_date/update_flag — a restatement is a NEW row, not
  a dup), `content_dedup_key`, `profile_key`, `allowed_baseline_dups`, `consolidation_group`, and an
  UNBOUND `callable` (bound only post-contract). `matrix_source_endpoints()` MUST equal the contract-YAML
  key set (cmd_plan reconciles — the forecast/forecast_vip drift is caught here). Corrections: dividends
  fetched INSIDE FundamentalsInitializer.download_fundamentals (per stock); cashflow/forecast/
  holder_number belong to init_factor_data (CLAUDE §6.2); index_daily is per-index RANGE; suspend_d feeds
  TWO distinct output families (yearly suspension + per-date store); stk_holdertrade key INCLUDES
  change_vol; report_rc identity = normalized analyst + report_rc_payload_digest (NOT author_name alone);
  indicators have ONE owner (A07); event datasets (top_inst/block_trade/top_list) carry
  allowed_baseline_dups; A15 bucket-A siblings are wholly UNBOUND placeholders that hard-block.

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

# ── M1: TYPED endpoint matrix — one row per (output_family), GPT re-review #4 M1 ───────────────
# A row models ONE physical output family and is OWNED uniquely by it (assert_unique_output_owner).
# `source_endpoints` = the API endpoint(s) whose fetch this output requires (A01 needs three); every
# source endpoint must have a signed contract before its adapter is built. `vendor_record_key` = the
# vendor's true per-row identity; `pit_version_key` = version/PIT columns (ann_date/f_ann_date/
# update_flag) whose changes are NEW rows not dups; `content_dedup_key` = the identity used to dedup a
# consolidated file; `profile_key` = the coarse key the manifest profiler aggregates on;
# `allowed_baseline_dups` = manifest rows that legitimately repeat under profile_key (a per-key COUNT
# check, not uniqueness). `callable` stays UNBOUND until the endpoint's contract is signed (a BLOCKING
# state, never an adapter input). A15 rows are wholly UNBOUND placeholders that hard-block.
from dataclasses import dataclass, field as _dcfield


@dataclass(frozen=True)
class EndpointRow:
    owner: str
    output_family: str
    source_endpoints: tuple
    query_mode: str          # per_open_trade_date|per_index_range|per_stock|per_period_report_type|per_month|UNBOUND
    vendor_record_key: tuple
    pit_version_key: tuple
    content_dedup_key: tuple
    profile_key: tuple
    empty_policy: str        # dense_refuse | sparse_canary
    allowed_baseline_dups: bool
    consolidation_group: str
    tail_rule: str
    callable: str = "UNBOUND (bind post-contract)"
    note: str = ""
    sidecars: tuple = ()


def _r(**kw):
    return EndpointRow(**kw)


ENDPOINT_MATRIX = [
    # market
    _r(owner="A01", output_family="market/daily", source_endpoints=("daily", "daily_basic", "adj_factor"),
       query_mode="per_open_trade_date", vendor_record_key=("ts_code", "trade_date"),
       pit_version_key=(), content_dedup_key=("ts_code", "trade_date"), profile_key=("ts_code", "trade_date"),
       empty_policy="dense_refuse", allowed_baseline_dups=False, consolidation_group="daily_per_date",
       tail_rule="sessions 20260702..last-complete",
       note="THREE source endpoints merged into one per-date file; bypass init_market_data.main()"),
    _r(owner="A02", output_family="market/index", source_endpoints=("index_daily",), query_mode="per_index_range",
       vendor_record_key=("ts_code", "trade_date"), pit_version_key=(), content_dedup_key=("ts_code", "trade_date"),
       profile_key=("ts_code", "trade_date"), empty_policy="dense_refuse", allowed_baseline_dups=False,
       consolidation_group="index_per_code", tail_rule="range end -> last-complete",
       note="per-index RANGE fetch, not per trade_date"),
    _r(owner="A08a", output_family="market/moneyflow", source_endpoints=("moneyflow",),
       query_mode="per_open_trade_date", vendor_record_key=("ts_code", "trade_date"), pit_version_key=(),
       content_dedup_key=("ts_code", "trade_date"), profile_key=("ts_code", "trade_date"),
       empty_policy="sparse_canary", allowed_baseline_dups=False, consolidation_group="moneyflow_per_date",
       tail_rule="sessions tail", sidecars=("reference/moneyflow_known_empty_dates.txt",)),
    _r(owner="A08b", output_family="market/stk_limit", source_endpoints=("stk_limit",),
       query_mode="per_open_trade_date", vendor_record_key=("ts_code", "trade_date"), pit_version_key=(),
       content_dedup_key=("ts_code", "trade_date"), profile_key=("ts_code", "trade_date"),
       empty_policy="dense_refuse", allowed_baseline_dups=False, consolidation_group="stk_limit_per_date",
       tail_rule="sessions tail"),
    _r(owner="A08c", output_family="market/margin", source_endpoints=("margin_detail",),
       query_mode="per_open_trade_date", vendor_record_key=("ts_code", "trade_date"), pit_version_key=(),
       content_dedup_key=("ts_code", "trade_date"), profile_key=("ts_code", "trade_date"),
       empty_policy="dense_refuse", allowed_baseline_dups=False, consolidation_group="margin_per_date",
       tail_rule="sessions tail", note="lands in market/margin = manifest dataset 'margin'; 2010+"),
    _r(owner="A08d", output_family="market/northbound", source_endpoints=("hk_hold",),
       query_mode="per_open_trade_date", vendor_record_key=("ts_code", "trade_date"), pit_version_key=(),
       content_dedup_key=("ts_code", "trade_date"), profile_key=("ts_code", "trade_date"),
       empty_policy="sparse_canary", allowed_baseline_dups=False, consolidation_group="northbound_per_date",
       tail_rule="sessions tail", sidecars=("reference/northbound_nonconnect_days.txt",)),
    _r(owner="A10a", output_family="market/suspension", source_endpoints=("suspend_d",),
       query_mode="per_year", vendor_record_key=("ts_code", "trade_date", "suspend_type"), pit_version_key=(),
       content_dedup_key=("ts_code", "trade_date", "suspend_type"), profile_key=("ts_code", "trade_date"),
       empty_policy="sparse_canary", allowed_baseline_dups=False, consolidation_group="suspension_yearly",
       tail_rule="per-year", note="yearly suspension_<yr> files; DISTINCT output family from the per-date store"),
    _r(owner="A10b", output_family="market/suspend_d", source_endpoints=("suspend_d",),
       query_mode="per_open_trade_date", vendor_record_key=("ts_code", "trade_date", "suspend_type"),
       pit_version_key=(), content_dedup_key=("ts_code", "trade_date", "suspend_type"),
       profile_key=("ts_code", "trade_date"), empty_policy="sparse_canary", allowed_baseline_dups=False,
       consolidation_group="suspend_d_per_date", tail_rule="per-date tail",
       note="per-date store (timing-preserving write_suspend_d); suspension_ranges is DERIVED afterward"),
    _r(owner="A11a", output_family="market/top_list", source_endpoints=("top_list",),
       query_mode="per_open_trade_date", vendor_record_key=("ts_code", "trade_date", "reason"),
       pit_version_key=(), content_dedup_key=("ts_code", "trade_date", "reason"),
       profile_key=("ts_code", "trade_date"), empty_policy="sparse_canary", allowed_baseline_dups=True,
       consolidation_group="top_list_per_date", tail_rule="sessions tail",
       note="multi-row event: multiple reasons per (ts_code,trade_date)"),
    _r(owner="A11b", output_family="market/top_inst", source_endpoints=("top_inst",),
       query_mode="per_open_trade_date", vendor_record_key=("ts_code", "trade_date", "exalter", "side", "reason"),
       pit_version_key=(), content_dedup_key=("ts_code", "trade_date", "exalter", "side", "reason"),
       profile_key=("ts_code", "trade_date"), empty_policy="sparse_canary", allowed_baseline_dups=True,
       consolidation_group="top_inst_per_date", tail_rule="sessions tail",
       note="MULTI-ROW event: baseline 2,636,668 dup rows under (ts_code,trade_date); key adds exalter+side+reason"),
    _r(owner="A11c", output_family="market/block_trade", source_endpoints=("block_trade",),
       query_mode="per_open_trade_date", vendor_record_key=("ts_code", "trade_date", "buyer", "seller", "price"),
       pit_version_key=(), content_dedup_key=("ts_code", "trade_date", "buyer", "seller", "price"),
       profile_key=("ts_code", "trade_date"), empty_policy="sparse_canary", allowed_baseline_dups=True,
       consolidation_group="block_trade_per_date", tail_rule="sessions tail",
       note="MULTI-ROW event: baseline 180,262 dup rows under the 2-col key"),
    _r(owner="A13", output_family="market/cyq_perf", source_endpoints=("cyq_perf",),
       query_mode="per_stock_repartition", vendor_record_key=("ts_code", "trade_date"), pit_version_key=(),
       content_dedup_key=("ts_code", "trade_date"), profile_key=("ts_code", "trade_date"),
       empty_policy="dense_refuse", allowed_baseline_dups=False, consolidation_group="cyq_per_date",
       tail_rule="per-stock range tail", note="per-stock (2018+) repartitioned per-date, row-conserving"),
    # fundamentals (statements: pit_version_key = ann_date/f_ann_date/update_flag)
    _r(owner="A03a", output_family="fundamentals/income", source_endpoints=("income",), query_mode="per_stock",
       vendor_record_key=("ts_code", "ann_date", "f_ann_date", "end_date", "report_type", "update_flag"),
       pit_version_key=("ann_date", "f_ann_date", "update_flag"),
       content_dedup_key=("ts_code", "end_date", "report_type", "f_ann_date", "update_flag"),
       profile_key=("ts_code", "end_date"), empty_policy="sparse_canary", allowed_baseline_dups=True,
       consolidation_group="income_period", tail_rule="ann_date window",
       note="pro.income STANDARD (not VIP); a restatement is a NEW row (version key), not a dup"),
    _r(owner="A03b", output_family="fundamentals/balancesheet", source_endpoints=("balancesheet",),
       query_mode="per_stock",
       vendor_record_key=("ts_code", "ann_date", "f_ann_date", "end_date", "report_type", "update_flag"),
       pit_version_key=("ann_date", "f_ann_date", "update_flag"),
       content_dedup_key=("ts_code", "end_date", "report_type", "f_ann_date", "update_flag"),
       profile_key=("ts_code", "end_date"), empty_policy="sparse_canary", allowed_baseline_dups=True,
       consolidation_group="balancesheet_period", tail_rule="ann_date window", note="pro.balancesheet STANDARD"),
    _r(owner="A05", output_family="fundamentals/cashflow", source_endpoints=("cashflow",), query_mode="per_stock",
       vendor_record_key=("ts_code", "ann_date", "f_ann_date", "end_date", "report_type", "update_flag"),
       pit_version_key=("ann_date", "f_ann_date", "update_flag"),
       content_dedup_key=("ts_code", "end_date", "report_type", "f_ann_date", "update_flag"),
       profile_key=("ts_code", "end_date"), empty_policy="sparse_canary", allowed_baseline_dups=True,
       consolidation_group="cashflow_period", tail_rule="ann_date window", note="init_factor scope, per stock"),
    _r(owner="A04a", output_family="fundamentals/income_quarterly", source_endpoints=("income_vip",),
       query_mode="per_period_report_type",
       vendor_record_key=("ts_code", "end_date", "report_type", "f_ann_date", "update_flag"),
       pit_version_key=("f_ann_date", "update_flag"),
       content_dedup_key=("ts_code", "end_date", "report_type", "f_ann_date", "update_flag"),
       profile_key=("ts_code", "end_date", "report_type"), empty_policy="dense_refuse", allowed_baseline_dups=True,
       consolidation_group="income_q_period", tail_rule="ann_date window", note="fetch_quarterly_statements"),
    _r(owner="A04b", output_family="fundamentals/cashflow_quarterly", source_endpoints=("cashflow_vip",),
       query_mode="per_period_report_type",
       vendor_record_key=("ts_code", "end_date", "report_type", "f_ann_date", "update_flag"),
       pit_version_key=("f_ann_date", "update_flag"),
       content_dedup_key=("ts_code", "end_date", "report_type", "f_ann_date", "update_flag"),
       profile_key=("ts_code", "end_date", "report_type"), empty_policy="dense_refuse", allowed_baseline_dups=True,
       consolidation_group="cashflow_q_period", tail_rule="ann_date window"),
    _r(owner="A06", output_family="fundamentals/forecast", source_endpoints=("forecast",), query_mode="per_stock",
       vendor_record_key=("ts_code", "ann_date", "end_date", "type"), pit_version_key=("ann_date",),
       content_dedup_key=("ts_code", "ann_date", "end_date", "type"), profile_key=("ts_code", "end_date"),
       empty_policy="sparse_canary", allowed_baseline_dups=True, consolidation_group="forecast_period",
       tail_rule="ann_date window", note="init_factor per stock; multiple forecasts per (ts_code,end_date)"),
    _r(owner="A07", output_family="fundamentals/indicators", source_endpoints=("fina_indicator_vip",),
       query_mode="per_period", vendor_record_key=("ts_code", "end_date", "ann_date", "update_flag"),
       pit_version_key=("ann_date", "update_flag"),
       content_dedup_key=("ts_code", "end_date", "ann_date", "update_flag"), profile_key=("ts_code", "end_date"),
       empty_policy="dense_refuse", allowed_baseline_dups=True, consolidation_group="indicators_period",
       tail_rule="current period refresh", note="SOLE indicator owner; update_flag revisions => NEW rows; "
       "historical staged archives IRRECOVERABLE"),
    # corporate
    _r(owner="A03c", output_family="corporate/dividends", source_endpoints=("dividend",), query_mode="per_stock",
       vendor_record_key=("ts_code", "end_date", "ann_date", "div_proc"), pit_version_key=("ann_date", "div_proc"),
       content_dedup_key=("ts_code", "end_date", "ann_date", "div_proc"), profile_key=("ts_code", "end_date"),
       empty_policy="sparse_canary", allowed_baseline_dups=True, consolidation_group="dividends_period",
       tail_rule="ann_date window", note="multiple div records per (ts_code,end_date) across proc stages"),
    _r(owner="A09", output_family="corporate/holder_number", source_endpoints=("stk_holdernumber",),
       query_mode="per_stock", vendor_record_key=("ts_code", "ann_date", "end_date"), pit_version_key=("ann_date",),
       content_dedup_key=("ts_code", "ann_date", "end_date"), profile_key=("ts_code", "end_date"),
       empty_policy="sparse_canary", allowed_baseline_dups=False, consolidation_group="holder_number_period",
       tail_rule="ann_date window", note="init_factor per stock"),
    _r(owner="A12", output_family="corporate/stk_holdertrade", source_endpoints=("stk_holdertrade",),
       query_mode="per_stock",
       vendor_record_key=("ts_code", "ann_date", "holder_name", "in_de", "change_vol", "begin_date"),
       pit_version_key=("ann_date",),
       content_dedup_key=("ts_code", "ann_date", "holder_name", "in_de", "change_vol", "begin_date"),
       profile_key=("ts_code", "ann_date"), empty_policy="sparse_canary", allowed_baseline_dups=True,
       consolidation_group="stk_holdertrade_yearly", tail_rule="ann_date window",
       note="per stock; key INCLUDES change_vol (canonical PIT key); current fetch swallows per-stock failures"),
    # analyst
    _r(owner="A14", output_family="analyst/report_rc", source_endpoints=("report_rc",),
       query_mode="per_report_date_month",
       vendor_record_key=("ts_code", "report_date", "org_name", "author_name", "quarter", "report_rc_payload_digest"),
       pit_version_key=("create_time", "raw_fetch_ts"),
       content_dedup_key=("ts_code", "report_date", "org_name", "author_name", "report_rc_payload_digest"),
       profile_key=("ts_code", "report_date"), empty_policy="dense_refuse", allowed_baseline_dups=True,
       consolidation_group="report_rc_yearly", tail_rule="TTL halo replay per Phase 5-A",
       note="doc cap 3000/page; identity = normalized analyst (org+author) + report_rc_payload_digest "
       "(current PIT logic), NOT author_name alone; NEW raw generation, provider bins PRESERVED as legacy"),
    _r(owner="A16", output_family="analyst/broker_recommend", source_endpoints=("broker_recommend",),
       query_mode="per_month", vendor_record_key=("month", "broker", "ts_code"), pit_version_key=(),
       content_dedup_key=("month", "broker", "ts_code"), profile_key=("month", "broker"),
       empty_policy="sparse_canary", allowed_baseline_dups=False, consolidation_group="broker_recommend_monthly",
       tail_rule="monthly tail", note="fetch_broker_recommend_historical EXISTS; inject E: paths"),
] + [
    # A15: bucket-A siblings — WHOLLY UNBOUND placeholders that HARD-BLOCK until their contract is signed
    _r(owner=f"A15_{ep}", output_family=f"UNBOUND/{ep}", source_endpoints=(ep,), query_mode="UNBOUND",
       vendor_record_key=("UNBOUND",), pit_version_key=(), content_dedup_key=("UNBOUND",),
       profile_key=("UNBOUND",), empty_policy="sparse_canary", allowed_baseline_dups=False,
       consolidation_group=f"UNBOUND_{ep}", tail_rule="UNBOUND", callable="UNBOUND (contract unsigned)",
       note="output family / keys UNRESOLVED until the signed contract defines them")
    for ep in ("express", "disclosure_date", "fina_mainbz", "fina_audit", "repurchase", "pledge_stat",
               "top10_floatholders")
]

GLOBAL_SIDECARS = ("raw_cache/manifests/* (ingest provenance manifests regenerated during recovery are "
                   "recovery outputs — ledgered + hashed like data files)",)


def matrix_source_endpoints() -> set:
    """Every API endpoint that needs a signed contract (union over source_endpoints)."""
    return {e for row in ENDPOINT_MATRIX for e in row.source_endpoints}


def assert_unique_output_owner():
    """Each physical output_family is owned by exactly ONE row (GPT M1) — never let two requests/rows
    lay claim to one output path."""
    seen = {}
    for row in ENDPOINT_MATRIX:
        if row.output_family in seen:
            raise RuntimeError(f"output_family {row.output_family} owned by both {seen[row.output_family]} "
                               f"and {row.owner}")
        seen[row.output_family] = row.owner



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


# ── B2/B3 ledger: the page-receipt ledger (coordinator-owned receipts + external hash chain) lives in
# scripts/recovery_ledger.py (GPT re-review #4 B2). request_id/LedgerError are re-exported for callers.
from recovery_ledger import PageReceiptLedger, LedgerError, request_id  # noqa: E402,F401


def _coordinator_commit() -> str:
    """The coordinator source identity bound into every ledger chain (falls back to the file hash if
    git is unavailable)."""
    import subprocess
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(E_ROOT), capture_output=True,
                             text=True, timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:  # noqa: BLE001
        pass
    return sha256_file(Path(__file__)) + ':' + sha256_file(E_ROOT / 'scripts' / 'recovery_ledger.py')


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
    led = PageReceiptLedger(rp, coordinator_commit=_coordinator_commit(),
                            adapter_bundle_hash="adapters_unbuilt")  # bound once adapters exist
    if new:
        if rp.root.exists():
            raise SystemExit(f"REFUSED: run {run_id} already exists — immutable runs")
        rp.create_root()
        led.event("run_created", run_id=run_id, baseline_manifest_sha256=MANIFEST_SHA256,
                  live_provider_source_commit=LIVE_PROVIDER_SOURCE_COMMIT)
    else:
        if not rp.root.exists():
            raise SystemExit(f"REFUSED: run {run_id} does not exist")
        try:
            rows = led._load()  # verifies the hash chain vs the external head (tamper -> LedgerError)
        except LedgerError as exc:
            raise SystemExit(f"REFUSED: resume — ledger integrity failed ({exc})")
        created = next((r for r in rows if r.get("event") == "run_created"), None)
        if not created or created.get("run_id") != run_id \
                or created.get("baseline_manifest_sha256") != MANIFEST_SHA256:
            raise SystemExit("REFUSED: resume without a valid run_created record matching this run id "
                             "and the pinned baseline (GPT B1 resume rule)")
    return rp, led


# ── modes (network-free) ─────────────────────────────────────────────────────────────────────────
def cmd_inventory(rp: RecoveryPaths, led: "PageReceiptLedger") -> int:
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


def cmd_preflight(rp: RecoveryPaths, led: "PageReceiptLedger") -> int:
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


def cmd_plan(rp: RecoveryPaths, led: "PageReceiptLedger") -> int:
    import yaml
    contracts = yaml.safe_load(CONTRACTS_YAML.read_text(encoding="utf-8")) or {} if CONTRACTS_YAML.exists() else {}
    problems = 0
    # M1: every physical output_family is owned by exactly ONE row (no two requests claim one path).
    try:
        assert_unique_output_owner()
    except RuntimeError as e:
        print(f"MATRIX ERROR: {e}")
        problems += 1
    # M2 (endpoint-set reconciliation): the matrix's source-endpoint set MUST equal the contract-YAML
    # key set — a source endpoint with no contract stanza, or an orphan stanza, is a blocking mismatch.
    matrix_eps = matrix_source_endpoints()
    yaml_eps = set(contracts.keys())
    if matrix_eps - yaml_eps:
        print(f"CONTRACT GAP: {len(matrix_eps - yaml_eps)} source endpoints have no contract stanza: "
              f"{sorted(matrix_eps - yaml_eps)}")
        problems += 1
    if yaml_eps - matrix_eps:
        print(f"CONTRACT ORPHAN: {len(yaml_eps - matrix_eps)} contract stanzas match no matrix endpoint: "
              f"{sorted(yaml_eps - matrix_eps)}")
        problems += 1
    # per-row readiness: a row is 'ready' only when EVERY source endpoint is contract-clean AND its
    # callable is bound (post-contract). An UNBOUND callable or any unsigned source endpoint BLOCKS.
    for row in ENDPOINT_MATRIX:
        unbound = row.callable.startswith("UNBOUND")
        blocked_eps = [ep for ep in row.source_endpoints if contract_errors(ep, contracts.get(ep, {}))]
        if blocked_eps:
            state = f"BLOCKED(contract:{','.join(blocked_eps)})"
        elif unbound:
            state = "BLOCKED(UNBOUND callable)"
        else:
            state = "ready"
        if blocked_eps or unbound:
            problems += 1
        print(f"  {row.owner:<7} {row.output_family:<28} {state}")
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
