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
- B4/M2: the endpoint doc gate validates STRUCTURE **and doc-field MEMBERSHIP**: doc_path resolved
  under the offline mirror with traversal/reparse rejection, doc_sha256 recomputed, ISO reviewed_at
  (not future), non-placeholder reviewer, AND every required_fields/natural_key column parsed as a real
  field of the pinned doc (parse_doc_field_vocabulary over the 名称 markdown tables) — a fabricated
  field list or a doc with no field table refuses; natural_key may name coordinator-DERIVED columns.
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
_PLACEHOLDERS = {"", "x", "xx", "xxx", "tbd", "todo", "na", "n/a", "-", "?", "pending"}
# Contracts are signed by a HUMAN who read the Tushare doc; the signature must name one.
_KNOWN_SIGNERS = {"henry"}

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
    profile_key_dups_expected: bool  # the MANIFEST legitimately repeats under profile_key (event data)
    consolidation_group: str
    tail_rule: str
    max_content_dups: int = 0  # DECLARED bound the ledger enforces under content_dedup_key (0 = none)
    # REQUIRED when len(source_endpoints) > 1 (GPT re-review #8): the EXPLICIT join/output rule.
    #   {join_on: (cols...), base: <endpoint>, how: left|inner}
    merge_spec: dict = _dcfield(default_factory=dict)
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
       empty_policy="dense_refuse", profile_key_dups_expected=False, consolidation_group="daily_per_date",
       tail_rule="sessions 20260702..last-complete",
       merge_spec={"join_on": ("ts_code", "trade_date"), "base": "daily", "how": "left"},
       note="THREE source endpoints merged into one per-date file over ONE population snapshot "
            "(identical trade_date partitions per leg); bypass init_market_data.main()"),
    _r(owner="A02", output_family="market/index", source_endpoints=("index_daily",), query_mode="per_index_range",
       vendor_record_key=("ts_code", "trade_date"), pit_version_key=(), content_dedup_key=("ts_code", "trade_date"),
       profile_key=("ts_code", "trade_date"), empty_policy="dense_refuse", profile_key_dups_expected=False,
       consolidation_group="index_per_code", tail_rule="range end -> last-complete",
       note="per-index RANGE fetch, not per trade_date"),
    _r(owner="A08a", output_family="market/moneyflow", source_endpoints=("moneyflow",),
       query_mode="per_open_trade_date", vendor_record_key=("ts_code", "trade_date"), pit_version_key=(),
       content_dedup_key=("ts_code", "trade_date"), profile_key=("ts_code", "trade_date"),
       empty_policy="sparse_canary", profile_key_dups_expected=False, consolidation_group="moneyflow_per_date",
       tail_rule="sessions tail", sidecars=("reference/moneyflow_known_empty_dates.txt",)),
    _r(owner="A08b", output_family="market/stk_limit", source_endpoints=("stk_limit",),
       query_mode="per_open_trade_date", vendor_record_key=("ts_code", "trade_date"), pit_version_key=(),
       content_dedup_key=("ts_code", "trade_date"), profile_key=("ts_code", "trade_date"),
       empty_policy="dense_refuse", profile_key_dups_expected=False, consolidation_group="stk_limit_per_date",
       tail_rule="sessions tail"),
    _r(owner="A08c", output_family="market/margin", source_endpoints=("margin_detail",),
       query_mode="per_open_trade_date", vendor_record_key=("ts_code", "trade_date"), pit_version_key=(),
       content_dedup_key=("ts_code", "trade_date"), profile_key=("ts_code", "trade_date"),
       empty_policy="dense_refuse", profile_key_dups_expected=False, consolidation_group="margin_per_date",
       tail_rule="sessions tail", note="lands in market/margin = manifest dataset 'margin'; 2010+"),
    _r(owner="A08d", output_family="market/northbound", source_endpoints=("hk_hold",),
       query_mode="per_open_trade_date", vendor_record_key=("ts_code", "trade_date"), pit_version_key=(),
       content_dedup_key=("ts_code", "trade_date"), profile_key=("ts_code", "trade_date"),
       empty_policy="sparse_canary", profile_key_dups_expected=False, consolidation_group="northbound_per_date",
       tail_rule="sessions tail", sidecars=("reference/northbound_nonconnect_days.txt",)),
    # GPT re-review #10: query_mode was `per_year`, but `year` is NOT an official suspend_d input — the
    # doc's params are ts_code / trade_date / start_date / end_date / suspend_type. The yearly
    # suspension_<yr>.parquet files are an OUTPUT PARTITIONING (consolidation_group), never a request
    # unit; the population is the open trading sessions, exactly as for the per-date store (A10b).
    _r(owner="A10a", output_family="market/suspension", source_endpoints=("suspend_d",),
       query_mode="per_open_trade_date", vendor_record_key=("ts_code", "trade_date", "suspend_type"),
       pit_version_key=(),
       content_dedup_key=("ts_code", "trade_date", "suspend_type"), profile_key=("ts_code", "trade_date"),
       empty_policy="sparse_canary", profile_key_dups_expected=False, consolidation_group="suspension_yearly",
       tail_rule="per-year", note="yearly suspension_<yr> files; DISTINCT output family from the per-date store"),
    _r(owner="A10b", output_family="market/suspend_d", source_endpoints=("suspend_d",),
       query_mode="per_open_trade_date", vendor_record_key=("ts_code", "trade_date", "suspend_type"),
       pit_version_key=(), content_dedup_key=("ts_code", "trade_date", "suspend_type"),
       profile_key=("ts_code", "trade_date"), empty_policy="sparse_canary", profile_key_dups_expected=False,
       consolidation_group="suspend_d_per_date", tail_rule="per-date tail",
       note="per-date store (timing-preserving write_suspend_d); suspension_ranges is DERIVED afterward"),
    _r(owner="A11a", output_family="market/top_list", source_endpoints=("top_list",),
       query_mode="per_open_trade_date", vendor_record_key=("ts_code", "trade_date", "reason", "row_payload_digest"),
       pit_version_key=(), content_dedup_key=("ts_code", "trade_date", "reason", "row_payload_digest"),
       profile_key=("ts_code", "trade_date"), empty_policy="sparse_canary", profile_key_dups_expected=True,
       consolidation_group="top_list_per_date", tail_rule="sessions tail",
       note="multi-row event: multiple reasons per (ts_code,trade_date)"),
    _r(owner="A11b", output_family="market/top_inst", source_endpoints=("top_inst",),
       query_mode="per_open_trade_date", vendor_record_key=("ts_code", "trade_date", "exalter", "side", "reason", "row_payload_digest"),
       pit_version_key=(),
       content_dedup_key=("ts_code", "trade_date", "exalter", "side", "reason", "row_payload_digest"),
       profile_key=("ts_code", "trade_date"), empty_policy="sparse_canary", profile_key_dups_expected=True,
       consolidation_group="top_inst_per_date", tail_rule="sessions tail",
       note="MULTI-ROW event: baseline 2,636,668 dup rows under (ts_code,trade_date); key adds exalter+side+reason"),
    _r(owner="A11c", output_family="market/block_trade", source_endpoints=("block_trade",),
       query_mode="per_open_trade_date", vendor_record_key=("ts_code", "trade_date", "buyer", "seller", "price", "row_payload_digest"),
       pit_version_key=(),
       content_dedup_key=("ts_code", "trade_date", "buyer", "seller", "price", "row_payload_digest"),
       profile_key=("ts_code", "trade_date"), empty_policy="sparse_canary", profile_key_dups_expected=True,
       consolidation_group="block_trade_per_date", tail_rule="sessions tail",
       note="MULTI-ROW event: baseline 180,262 dup rows under the 2-col key"),
    _r(owner="A13", output_family="market/cyq_perf", source_endpoints=("cyq_perf",),
       query_mode="per_stock_repartition", vendor_record_key=("ts_code", "trade_date"), pit_version_key=(),
       content_dedup_key=("ts_code", "trade_date"), profile_key=("ts_code", "trade_date"),
       empty_policy="sparse_canary", profile_key_dups_expected=False, consolidation_group="cyq_per_date",
       tail_rule="per-stock range tail",
       note="per-stock (2018+) repartitioned per-date, row-conserving. REQUEST-level empty_policy is "
            "sparse_canary: a lifetime-non-overlapping stock (delisted pre-2018 / listed after the "
            "window) returns an empty per-stock response, which is a valid outcome — NOT dense_refuse "
            "(GPT sign-off HOLD BLOCKER-2). Per-DATE output density (every required open session 2018+ "
            "non-empty in the consolidated output) MUST BE enforced after repartition — NOT yet "
            "implemented; a promotion precondition, not a current gate (GPT re-review #2)."),
    # fundamentals (statements: pit_version_key = ann_date/f_ann_date/update_flag)
    _r(owner="A03a", output_family="fundamentals/income", source_endpoints=("income",), query_mode="per_stock",
       vendor_record_key=("ts_code", "ann_date", "f_ann_date", "end_date", "report_type", "update_flag"),
       pit_version_key=("ann_date", "f_ann_date", "update_flag"),
       content_dedup_key=("ts_code", "ann_date", "end_date", "report_type", "f_ann_date", "update_flag"),
       profile_key=("ts_code", "end_date"), empty_policy="sparse_canary", profile_key_dups_expected=True,
       consolidation_group="income_period", tail_rule="ann_date window",
       note="pro.income STANDARD (not VIP); a restatement is a NEW row (version key), not a dup"),
    _r(owner="A03b", output_family="fundamentals/balancesheet", source_endpoints=("balancesheet",),
       query_mode="per_stock",
       vendor_record_key=("ts_code", "ann_date", "f_ann_date", "end_date", "report_type", "update_flag"),
       pit_version_key=("ann_date", "f_ann_date", "update_flag"),
       content_dedup_key=("ts_code", "ann_date", "end_date", "report_type", "f_ann_date", "update_flag"),
       profile_key=("ts_code", "end_date"), empty_policy="sparse_canary", profile_key_dups_expected=True,
       consolidation_group="balancesheet_period", tail_rule="ann_date window", note="pro.balancesheet STANDARD"),
    _r(owner="A05", output_family="fundamentals/cashflow", source_endpoints=("cashflow",), query_mode="per_stock",
       vendor_record_key=("ts_code", "ann_date", "f_ann_date", "end_date", "report_type", "update_flag"),
       pit_version_key=("ann_date", "f_ann_date", "update_flag"),
       content_dedup_key=("ts_code", "ann_date", "end_date", "report_type", "f_ann_date", "update_flag"),
       profile_key=("ts_code", "end_date"), empty_policy="sparse_canary", profile_key_dups_expected=True,
       consolidation_group="cashflow_period", tail_rule="ann_date window", note="init_factor scope, per stock"),
    _r(owner="A04a", output_family="fundamentals/income_quarterly", source_endpoints=("income_vip",),
       query_mode="per_period_report_type",
       vendor_record_key=("ts_code", "end_date", "report_type", "f_ann_date", "update_flag"),
       pit_version_key=("f_ann_date", "update_flag"),
       content_dedup_key=("ts_code", "end_date", "report_type", "f_ann_date", "update_flag"),
       profile_key=("ts_code", "end_date", "report_type"), empty_policy="sparse_canary", profile_key_dups_expected=True,
       consolidation_group="income_q_period", tail_rule="ann_date window",
       note="fetch_quarterly_statements. REQUEST unit is (period, report_type) and the original wrapper "
            "(_fetch_statement_report_types) SKIPS an empty report_type leg — so an empty (period, "
            "report_type=3 调整单季) response is a valid outcome, NOT dense_refuse (GPT sign-off HOLD "
            "MAJOR). Per-PERIOD output density (>=1 report_type non-empty per period) MUST BE enforced "
            "after consolidation — NOT yet implemented; a promotion precondition, not per request "
            "and not a current gate (GPT re-review #2)."),
    _r(owner="A04b", output_family="fundamentals/cashflow_quarterly", source_endpoints=("cashflow_vip",),
       query_mode="per_period_report_type",
       vendor_record_key=("ts_code", "end_date", "report_type", "f_ann_date", "update_flag"),
       pit_version_key=("f_ann_date", "update_flag"),
       content_dedup_key=("ts_code", "end_date", "report_type", "f_ann_date", "update_flag"),
       profile_key=("ts_code", "end_date", "report_type"), empty_policy="sparse_canary", profile_key_dups_expected=True,
       consolidation_group="cashflow_q_period", tail_rule="ann_date window",
       note="fetch_quarterly_statements. REQUEST-level sparse_canary for the same reason as "
            "income_quarterly (empty report_type=3 leg is valid); per-period output density MUST BE "
            "enforced after consolidation — NOT yet implemented; a promotion precondition (GPT "
            "sign-off HOLD MAJOR; re-review #2)."),
    _r(owner="A06", output_family="fundamentals/forecast", source_endpoints=("forecast",), query_mode="per_stock",
       vendor_record_key=("ts_code", "ann_date", "end_date", "type"), pit_version_key=("ann_date",),
       content_dedup_key=("ts_code", "ann_date", "end_date", "type"), profile_key=("ts_code", "end_date"),
       empty_policy="sparse_canary", profile_key_dups_expected=True, consolidation_group="forecast_period",
       tail_rule="ann_date window", note="init_factor per stock; multiple forecasts per (ts_code,end_date)"),
    _r(owner="A07", output_family="fundamentals/indicators", source_endpoints=("fina_indicator_vip",),
       query_mode="per_period", vendor_record_key=("ts_code", "end_date", "ann_date", "update_flag"),
       pit_version_key=("ann_date", "update_flag"),
       content_dedup_key=("ts_code", "end_date", "ann_date", "update_flag"), profile_key=("ts_code", "end_date"),
       empty_policy="dense_refuse", profile_key_dups_expected=True, consolidation_group="indicators_period",
       tail_rule="current period refresh", note="SOLE indicator owner; update_flag revisions => NEW rows; "
       "historical staged archives IRRECOVERABLE"),
    # corporate
    _r(owner="A03c", output_family="corporate/dividends", source_endpoints=("dividend",), query_mode="per_stock",
       vendor_record_key=("ts_code", "ann_date", "end_date", "record_date", "ex_date", "pay_date", "div_proc"),
       pit_version_key=("ann_date", "div_proc"),
       content_dedup_key=("ts_code", "ann_date", "end_date", "record_date", "ex_date", "pay_date", "div_proc"),
       profile_key=("ts_code", "end_date"),
       empty_policy="sparse_canary", profile_key_dups_expected=True, consolidation_group="dividends_period",
       tail_rule="ann_date window", note="multiple div records per (ts_code,end_date) across proc stages"),
    _r(owner="A09", output_family="corporate/holder_number", source_endpoints=("stk_holdernumber",),
       query_mode="per_stock", vendor_record_key=("ts_code", "ann_date", "end_date"), pit_version_key=("ann_date",),
       content_dedup_key=("ts_code", "ann_date", "end_date"), profile_key=("ts_code", "end_date"),
       empty_policy="sparse_canary", profile_key_dups_expected=False, consolidation_group="holder_number_period",
       tail_rule="ann_date window", note="init_factor per stock"),
    _r(owner="A12", output_family="corporate/stk_holdertrade", source_endpoints=("stk_holdertrade",),
       query_mode="per_stock",
       vendor_record_key=("ts_code", "ann_date", "holder_name", "in_de", "change_vol", "begin_date"),
       pit_version_key=("ann_date",),
       content_dedup_key=("ts_code", "ann_date", "holder_name", "in_de", "change_vol", "begin_date"),
       profile_key=("ts_code", "ann_date"), empty_policy="sparse_canary", profile_key_dups_expected=True,
       consolidation_group="stk_holdertrade_yearly", tail_rule="ann_date window",
       note="per stock; key INCLUDES change_vol (canonical PIT key); current fetch swallows per-stock failures"),
    # analyst
    _r(owner="A14", output_family="analyst/report_rc", source_endpoints=("report_rc",),
       query_mode="per_report_date_month",
       vendor_record_key=("ts_code", "report_date", "org_name", "author_name", "quarter", "report_rc_payload_digest"),
       pit_version_key=("create_time", "raw_fetch_ts"),
       content_dedup_key=("ts_code", "report_date", "org_name", "author_name", "report_rc_payload_digest"),
       profile_key=("ts_code", "report_date"), empty_policy="dense_refuse", profile_key_dups_expected=True,
       consolidation_group="report_rc_yearly", tail_rule="TTL halo replay per Phase 5-A",
       note="doc cap 3000/page; identity = normalized analyst (org+author) + report_rc_payload_digest "
       "(current PIT logic), NOT author_name alone; NEW raw generation, provider bins PRESERVED as legacy"),
    _r(owner="A16", output_family="analyst/broker_recommend", source_endpoints=("broker_recommend",),
       query_mode="per_month", vendor_record_key=("month", "broker", "ts_code"), pit_version_key=(),
       content_dedup_key=("month", "broker", "ts_code"), profile_key=("month", "broker"),
       empty_policy="sparse_canary", profile_key_dups_expected=False, consolidation_group="broker_recommend_monthly",
       tail_rule="monthly tail", note="fetch_broker_recommend_historical EXISTS; inject E: paths"),
]

# ── A15: the bucket-A siblings, BOUND to their real request shapes ───────────────────────────────
# GPT sign-off HOLD #3 (reproduced): these were UNBOUND placeholders, so endpoint_expected_resolvers()
# returned an EMPTY set and the fail-open check let ANY resolver be signed — disclosure_date +
# calendar_months -> {month: 202607} returned zero errors though its real caller sends end_date. Each
# shape below is read from its ACTUAL caller (scripts/fetch_bucket_a.py) and cross-checked against the
# pinned doc's input params. `callable` stays UNBOUND: the shape is known, the adapter is not.
ENDPOINT_MATRIX += [
    _r(owner="A15a", output_family="fundamentals/express", source_endpoints=("express",),
       query_mode="per_period", vendor_record_key=("ts_code", "ann_date", "end_date"),
       pit_version_key=("ann_date",), content_dedup_key=("ts_code", "ann_date", "end_date"),
       profile_key=("ts_code", "end_date"), empty_policy="sparse_canary",
       profile_key_dups_expected=True, consolidation_group="express_period",
       tail_rule="quarterly periods",
       note="express_vip(period=<quarter end>) per fetch_bucket_a._fetch_by_period"),
    _r(owner="A15b", output_family="fundamentals/disclosure_date", source_endpoints=("disclosure_date",),
       query_mode="per_quarter_end_date", vendor_record_key=("ts_code", "end_date", "ann_date"),
       pit_version_key=("ann_date", "actual_date", "modify_date"),
       content_dedup_key=("ts_code", "end_date", "ann_date"), profile_key=("ts_code", "end_date"),
       empty_policy="sparse_canary", profile_key_dups_expected=True,
       consolidation_group="disclosure_date_period", tail_rule="quarterly end_dates",
       note="disclosure_date(end_date=<quarter end>) — the quarter goes in end_date, NOT period"),
    _r(owner="A15c", output_family="fundamentals/fina_mainbz", source_endpoints=("fina_mainbz",),
       query_mode="per_period", vendor_record_key=("ts_code", "end_date", "bz_item", "bz_code"),
       pit_version_key=(), content_dedup_key=("ts_code", "end_date", "bz_item", "bz_code"),
       profile_key=("ts_code", "end_date"), empty_policy="sparse_canary",
       profile_key_dups_expected=True, consolidation_group="fina_mainbz_period",
       tail_rule="quarterly periods", max_content_dups=0,
       note="fina_mainbz_vip(period=<quarter end>), paginated (doc cap 10000); multi-row per period. "
            "The P/D/I breakdown dimension is the OUTPUT column `bz_code` (doc 81 输出参数), NOT the "
            "`type` INPUT param — keying on the input name mis-identified rows (sign-off fix 2026-07-17)"),
    _r(owner="A15d", output_family="fundamentals/fina_audit", source_endpoints=("fina_audit",),
       query_mode="per_stock", vendor_record_key=("ts_code", "end_date", "ann_date"),
       pit_version_key=("ann_date",), content_dedup_key=("ts_code", "end_date", "ann_date"),
       profile_key=("ts_code", "end_date"), empty_policy="sparse_canary",
       profile_key_dups_expected=True, consolidation_group="fina_audit_stock",
       tail_rule="per stock", note="fina_audit(ts_code=<code>) per stock — full history per call"),
    _r(owner="A15e", output_family="corporate/repurchase", source_endpoints=("repurchase",),
       query_mode="per_year_range", vendor_record_key=("ts_code", "ann_date", "end_date", "proc"),
       pit_version_key=("ann_date",),
       content_dedup_key=("ts_code", "ann_date", "end_date", "proc"),
       profile_key=("ts_code", "ann_date"), empty_policy="sparse_canary",
       profile_key_dups_expected=True, consolidation_group="repurchase_yearly",
       tail_rule="per year range",
       note="repurchase(start_date=YYYY0101, end_date=YYYY1231) per YEAR, paginated (cap 2000+)"),
    _r(owner="A15f", output_family="corporate/pledge_stat", source_endpoints=("pledge_stat",),
       query_mode="per_weekly_friday", vendor_record_key=("ts_code", "end_date"), pit_version_key=(),
       content_dedup_key=("ts_code", "end_date"), profile_key=("ts_code", "end_date"),
       empty_policy="sparse_canary", profile_key_dups_expected=False,
       consolidation_group="pledge_stat_weekly", tail_rule="weekly Fridays",
       note="pledge_stat(end_date=<Friday>) per week, paginated (HARD cap 3000)"),
    _r(owner="A15g", output_family="corporate/top10_floatholders",
       source_endpoints=("top10_floatholders",), query_mode="per_period",
       vendor_record_key=("ts_code", "end_date", "holder_name"), pit_version_key=("ann_date",),
       content_dedup_key=("ts_code", "end_date", "holder_name"), profile_key=("ts_code", "end_date"),
       empty_policy="sparse_canary", profile_key_dups_expected=True,
       consolidation_group="top10_floatholders_period", tail_rule="quarterly periods",
       note="top10_floatholders(period=<quarter end>), paginated (cap 6000); 10 rows per period"),
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
        # GPT impl re-review #4 (P0): the OS lock is taken on a HANDLE opened through the no-follow
        # broker chain, not a pathname handed to FileLock — this closes the same validate-then-reopen
        # TOCTOU that execution_guard had (a junction swapped in at <run>/ledger after assert_write
        # would otherwise be followed by FileLock). One lock primitive, no second "validate then open
        # by path" implementation.
        lock_path = Path(str(self.ledger_path) + ".lock")
        return self.broker().file_lock(lock_path, timeout=120.0)


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
# GPT re-review #6 F4: doc_id was OPTIONAL, so a contract that simply omitted it skipped the doc-id
# binding check entirely (a valid contract with no doc_id produced no errors). It is REQUIRED now.
# GPT re-review #7 F3: `pagination` was free-form PROSE while the ledger independently received
# `pagination_mode`/`page_limit` — nothing proved that what executes is what the human signed. The
# contract now carries TYPED specs and `assert_plan_matches_contracts` compares every frozen ledger
# request against them before a single call is made.
CONTRACT_REQUIRED = ("doc_path", "doc_id", "doc_sha256", "required_fields", "natural_key", "pagination",
                     "pagination_spec", "request_population", "rate_limit", "cadence", "pit_anchors",
                     "empty_policy", "reviewed_by", "reviewed_at")
_PAGINATION_MODES = {"single_page", "offset_paged"}
# The unit a request set is enumerated over — must match the matrix row's query_mode.
# NOTE: no `year` — it was fictional (suspend_d has no such vendor input); the yearly suspension files
# are an output partitioning, not a request unit (GPT re-review #10).
_POPULATION_UNITS = {"open_trade_date", "index_range", "stock", "period_report_type", "period",
                     "month", "report_date_month", "stock_repartition", "quarter_end_date",
                     "year_range", "weekly_friday"}
# matrix query_mode -> the population unit a signed contract must declare for it
_QUERY_MODE_TO_UNIT = {
    "per_open_trade_date": "open_trade_date", "per_index_range": "index_range",
    "per_stock": "stock", "per_period_report_type": "period_report_type", "per_period": "period",
    "per_month": "month", "per_report_date_month": "report_date_month",
    "per_stock_repartition": "stock_repartition",
    "per_quarter_end_date": "quarter_end_date", "per_year_range": "year_range",
    "per_weekly_friday": "weekly_friday",
}

# Coordinator-DERIVED key columns: legitimate in a natural_key WITHOUT appearing in the vendor doc
# (they are computed during ingest). report_rc_payload_digest is the PIT identity digest; raw_fetch_ts is
# the first-seen stamp; _src_file/_src_ordinal are the deterministic tie-break columns (§6.3 P0-4).
# GPT re-review #5 F4: a GLOBAL derived allowlist let ANY derived field be keyed on ANY endpoint (e.g.
# report_rc's payload digest keying `daily`). Derived fields are now ENDPOINT-SCOPED with a declared
# computation/provenance; only genuinely ingest-universal stamps stay universal.
_DERIVED_UNIVERSAL = {
    "raw_fetch_ts": "coordinator first-seen stamp written at page receipt time (PIT visibility floor)",
    "_src_file": "deterministic tie-break column injected by _normalize_periodic_dataset (§6.3 P0-4)",
    "_src_ordinal": "deterministic tie-break ordinal injected by _normalize_periodic_dataset (§6.3 P0-4)",
}
_DERIVED_BY_ENDPOINT = {
    "report_rc": {"report_rc_payload_digest":
                  "sha256 over the normalized analyst-forecast payload; the production PIT identity "
                  "(pit_backend report_rc handling) — NOT author_name alone"},
    "top_list": {"row_payload_digest": "sha256 over the FULL vendor row; lossless identity because the "
                                       "doc establishes no transaction id and (ts_code,trade_date) repeats"},
    "top_inst": {"row_payload_digest": "sha256 over the FULL vendor row (see top_list rationale)"},
    "block_trade": {"row_payload_digest": "sha256 over the FULL vendor row (see top_list rationale)"},
}


def derived_fields_for(endpoint: str) -> set:
    """The derived columns THIS endpoint may legitimately key on (universal ingest stamps + its own
    declared derivations). An endpoint may never borrow another's derived field."""
    return set(_DERIVED_UNIVERSAL) | set(_DERIVED_BY_ENDPOINT.get(endpoint, {}))


_FIELD_HEADERS = frozenset({"名称", "name", "参数名", "字段", "字段名"})  # markdown field-table header first cell
_DOC_IDENT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)")
_DOC_ID_RE = re.compile(r"doc_id=(\d+)")
_DOC_API_RE = re.compile(r"接口\s*(?:名称)?\s*[：:]\s*([A-Za-z_][A-Za-z0-9_]*)")


def parse_doc_identity(doc: Path) -> dict:
    """Extract the doc's OWN declared identity: its `doc_id=NNN` header and the `接口：<api>` name it
    documents. GPT re-review #5 F4: the gate checked path+sha but never proved the doc BELONGS to the
    declared endpoint, so a valid field table from the WRONG API could approve a contract."""
    text = doc.read_text(encoding="utf-8")
    mi, ma = _DOC_ID_RE.search(text), _DOC_API_RE.search(text)
    return {"doc_id": mi.group(1) if mi else None, "api_name": ma.group(1) if ma else None}


# GPT re-review #7 B7: a GENERIC `_vip` suffix strip let ANY `<x>_vip` endpoint claim `<x>`'s doc,
# including combinations nobody reviewed. Aliases are now an EXPLICIT, reviewed map — one line per
# accepted (endpoint -> documenting api) pair, with the reason it is legitimate.
_DOC_ALIASES = {
    # VIP bulk variants share their base interface's response schema; only the query/permission
    # envelope differs, so the base doc IS the authority for their output fields.
    "income_vip": "income",
    "cashflow_vip": "cashflow",
    "fina_indicator_vip": "fina_indicator",
}


def doc_declares_endpoint(api_name: str, endpoint: str) -> bool:
    """A doc matches an endpoint if it documents that api exactly, or is that endpoint's EXPLICITLY
    reviewed alias (no generic suffix stripping — see _DOC_ALIASES)."""
    if not api_name:
        return False
    return api_name == endpoint or api_name == _DOC_ALIASES.get(endpoint)


_OUTPUT_MARKERS = frozenset({"输出参数", "输出指标", "返回参数", "返回指标"})
_INPUT_MARKERS = frozenset({"输入参数", "请求参数"})


def parse_doc_fields(doc: Path) -> dict:
    """Parse a Tushare interface doc into its INPUT and OUTPUT field sets, kept SEPARATE.

    GPT re-review #7 B7 (reproduced): this used to UNION the input and output tables, so a column that
    exists only as a QUERY PARAMETER passed as a `natural_key` — e.g. `trade_date` is an input to
    top_inst and appears in no output row, yet a contract keying on it validated clean. A row-identity
    key must name a column the response actually CONTAINS.

    Section markers (输出参数/输出指标/返回参数 vs 输入参数/请求参数) select which set a following
    field table feeds. Tables before any marker are treated as INPUT — never silently as output."""
    out, inp = set(), set()
    section, armed = "input", False   # fail-safe default: unmarked tables are NOT output
    for line in doc.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s in _OUTPUT_MARKERS:
            section, armed = "output", False
            continue
        if s in _INPUT_MARKERS:
            section, armed = "input", False
            continue
        if not s.startswith("|"):
            armed = False  # any non-table line ends the current table
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        first = cells[0] if cells else ""
        if first in _FIELD_HEADERS:
            armed = True  # header row of a field table — arm collection
            continue
        if first and set(first) <= {"-", ":"}:
            continue  # separator row (| --- |) — stay armed
        if armed:
            m = _DOC_IDENT.match(first)
            if m:
                (out if section == "output" else inp).add(m.group(1))
    return {"output": out, "input": inp,
            "has_output_section": bool(out)}


def parse_doc_field_vocabulary(doc: Path) -> set:
    """The doc's OUTPUT (response) field set — the only vocabulary a row-identity key may draw on.
    Empty when the doc declares no output section (wrong doc cited) → the membership check refuses."""
    return parse_doc_fields(doc)["output"]


def _pagination_spec_errors(endpoint: str, spec) -> list:
    """A TYPED pagination contract (GPT re-review #7 F3): the mode and page limit the human signed,
    machine-comparable against what the ledger will actually execute."""
    if not isinstance(spec, dict):
        return [f"{endpoint}: pagination_spec must be a typed mapping "
                f"{{mode, page_limit[, offset_param]}}, not prose"]
    errs = []
    mode = spec.get("mode")
    if mode not in _PAGINATION_MODES:
        errs.append(f"{endpoint}: pagination_spec.mode must be one of {sorted(_PAGINATION_MODES)}")
    limit = spec.get("page_limit")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 0:
        errs.append(f"{endpoint}: pagination_spec.page_limit must be a non-negative int")
    elif mode == "single_page" and limit != 0:
        errs.append(f"{endpoint}: single_page requires page_limit == 0 (got {limit})")
    elif mode == "offset_paged":
        if limit <= 0:
            errs.append(f"{endpoint}: offset_paged requires a POSITIVE page_limit (the doc's cap)")
        if not str(spec.get("offset_param") or "").strip():
            errs.append(f"{endpoint}: offset_paged requires the doc's offset_param name")
    return errs


def _population_spec_errors(endpoint: str, spec) -> list:
    """How the request SET is enumerated — EXECUTABLE, not prose (GPT re-review #10 BLOCKER-1: `source`
    was unenforced text, so "trade_cal open sessions" was a claim nobody could check and a plan of
    SUNDAYS passed). The signature must name a resolver the code can RUN, its bounds, and the sha256 of
    the population that resolves — so the human signs a specific, reproducible set."""
    if not isinstance(spec, dict):
        return [f"{endpoint}: request_population must be a typed mapping "
                f"{{resolver, bounds, expected_set_sha256}}, not prose"]
    errs = []
    if spec.get("resolver") not in _POPULATION_RESOLVERS:
        errs.append(f"{endpoint}: request_population.resolver must be one of "
                    f"{sorted(_POPULATION_RESOLVERS)} — an executable resolver, not a description")
    else:
        # ENDPOINT-AWARE and FAIL-CLOSED: the resolver must be one THIS endpoint's matrix rows imply,
        # checked at SIGN-OFF. GPT sign-off HOLD #3: this read `if allowed and ...`, so an endpoint with
        # NO binding (the UNBOUND A15 rows) admitted ANY known resolver — a fail-open guard in the one
        # place whose whole job is to refuse. An absent binding is now an ERROR, not a free pass.
        allowed = endpoint_expected_resolvers(endpoint)
        if not allowed:
            errs.append(f"{endpoint}: NO request-shape binding — its matrix rows declare no query_mode, "
                        f"so nothing establishes what a request for it even looks like. Bind it in the "
                        f"matrix before signing; an unbound endpoint must never be signable.")
        elif spec.get("resolver") not in allowed:
            errs.append(f"{endpoint}: resolver {spec.get('resolver')!r} does not belong to this endpoint "
                        f"— its matrix rows enumerate {sorted(allowed)}. Signing it would bind the wrong "
                        f"request recipe.")
    bounds = spec.get("bounds")
    if not isinstance(bounds, dict) or not bounds:
        errs.append(f"{endpoint}: request_population.bounds must state the selection rule "
                    f"(e.g. {{start, end}} / {{codes: [...]}} / {{list_status}})")
    sha = str(spec.get("expected_set_sha256") or "")
    if len(sha) != 64:
        errs.append(f"{endpoint}: request_population.expected_set_sha256 must pin the COMPLETE REQUEST "
                    f"SET the reviewer signed (sha256 over every parameter of every request, not a "
                    f"member list)")
    if errs:
        return errs
    try:
        resolved = resolve_population(spec)
    except Exception as exc:                       # a resolver that cannot run cannot be signed
        return [f"{endpoint}: request_population does not resolve: {exc}"]
    if not resolved:
        return [f"{endpoint}: request_population resolves to an EMPTY set — nothing would be fetched"]
    got = request_set_sha256(resolved)
    if got != sha:
        errs.append(f"{endpoint}: request_population resolves to {len(resolved)} COMPLETE REQUESTS "
                    f"hashing {got[:12]}, but the contract signs {sha[:12]} — sign the request set that "
                    f"resolves")
    return errs


def canonical_contract_sha256(c: dict) -> str:
    """The identity of the SIGNED contract (GPT re-review #8 BLOCKER-1: plan rows carry a
    `contract_sha256` that nothing ever checked). Canonical = sorted keys, stable separators, over the
    whole signed mapping — so any edit to what was signed changes the hash and every plan row bound to
    it refuses."""
    return hashlib.sha256(
        json.dumps(c, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


# ── EXECUTABLE population resolvers — COMPLETE REQUESTS, not member scalars ──────────────────────
# GPT sign-off HOLD: "complete request tuples are constructed, then discarded". The tuple was built and
# then projected to `k[0]`, so the "exact" comparison verified only the PRIMARY AXIS. Reproduced through
# the fully signed gate: income_vip(period=20260331, report_type=999) accepted (the real recipe uses 2/3);
# signed index code 000300.SH accepted an unsigned 2099 range; 5,861 signed stocks accepted arbitrary
# 2099 cyq_perf ranges. I computed the fact and threw it away on the next line.
#
# A resolver now yields the FULL canonical request — every varying AND constant parameter — and the plan
# is compared to that set whole. Reference-derived axes are PINNED by `reference_sha256`: reading live
# reference data would force re-signing on every calendar/listing refresh (GPT's answer 2), so the
# contract binds the exact reference bytes it was signed against.


def _canon_request(params: dict) -> tuple:
    """A complete, canonical, hashable request identity: EVERY parameter, sorted. Never a projection."""
    return tuple(sorted((str(k), str(v)) for k, v in dict(params).items()))


def request_set_sha256(requests) -> str:
    """Identity of a resolved request SET — what the human actually signed."""
    payload = "\n".join(sorted("&".join(f"{k}={v}" for k, v in r) for r in requests))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# back-compat alias: the population IS the request set now
population_set_sha256 = request_set_sha256


def _pinned_reference(rel: str, bounds: dict, label: str):
    """Load a reference table ONLY at the exact bytes the contract was signed against. GPT: resolving
    from live reference data 'will otherwise force re-signing whenever listings/statuses change' — so a
    contract pins the sha256 it saw, and a refreshed reference refuses until re-signed deliberately."""
    import pandas as pd
    path = E_DATA / rel
    want = str(bounds.get("reference_sha256") or "")
    if len(want) != 64:
        raise RuntimeError(f"{label}: bounds.reference_sha256 must pin the reference file this "
                           f"population is derived from ({rel})")
    if not path.is_file():
        raise RuntimeError(f"{label}: reference {rel} is missing")
    got = sha256_file(path)
    if got != want:
        raise RuntimeError(f"{label}: {rel} is now {got[:12]} but the contract pins {want[:12]} — the "
                           f"reference data changed since signing; re-sign against the new bytes")
    return pd.read_parquet(path)


def _resolve_open_sessions(bounds: dict) -> set:
    """The REAL open trading sessions from the pinned trade_cal — one request per session."""
    cal = _pinned_reference("reference/trade_cal.parquet", bounds, "trade_cal_open_sessions")
    exch = str(bounds.get("exchange") or "SSE")
    sel = cal[(cal["exchange"] == exch) & (cal["is_open"] == 1)]
    lo, hi = str(bounds["start"]), str(bounds["end"])
    return {_canon_request({"trade_date": str(d)}) for d in sel["cal_date"] if lo <= str(d) <= hi}


def _listed_codes(bounds: dict, label: str) -> set:
    sb = _pinned_reference("reference/stock_basic.parquet", bounds, label)
    want = set(str(bounds.get("list_status") or "L,D,P").split(","))
    # GPT sign-off HOLD #4 (latent fail-open): this SKIPPED the filter when `list_status` was absent, so
    # a reference missing the column would silently sign the full universe as if it were the declared
    # subset. The column is required — a population that filters on data the pinned reference does not
    # carry cannot be signed against it.
    if "list_status" not in sb.columns:
        raise RuntimeError(f"{label}: the pinned stock_basic has no `list_status` column — the "
                           f"declared list_status filter cannot be applied to it; the population is "
                           f"not resolvable against this reference")
    return {str(c) for c in sb[sb["list_status"].astype(str).isin(want)]["ts_code"]}


def _resolve_stock_codes(bounds: dict) -> set:
    """Per-stock legs whose request is the code alone (statements, forecast, dividends, holders)."""
    return {_canon_request({"ts_code": c}) for c in _listed_codes(bounds, "stock_basic_codes")}


def _resolve_stock_ranges(bounds: dict) -> set:
    """Per-stock legs whose request ALSO carries a date range (cyq_perf takes ts_code + start_date +
    end_date — GPT: the range was unbound, so 5,861 signed stocks accepted arbitrary 2099 dates)."""
    lo, hi = str(bounds["start_date"]), str(bounds["end_date"])
    return {_canon_request({"ts_code": c, "start_date": lo, "end_date": hi})
            for c in _listed_codes(bounds, "stock_basic_ranges")}


def _resolve_index_ranges(bounds: dict) -> set:
    """Index legs are per-code RANGES: the signed request includes its bounds (GPT: signed 000300.SH
    accepted an unsigned 20990101..20990102 range)."""
    codes = bounds.get("codes")
    if not isinstance(codes, list) or not codes:
        raise RuntimeError("index_code_ranges requires an explicit signed `codes` list")
    lo, hi = str(bounds["start_date"]), str(bounds["end_date"])
    return {_canon_request({"ts_code": str(c), "start_date": lo, "end_date": hi}) for c in codes}


def _month_strings(bounds: dict) -> set:
    lo, hi = str(bounds["start"]), str(bounds["end"])
    y, mth, out = int(lo[:4]), int(lo[4:6]), set()
    while f"{y:04d}{mth:02d}" <= hi:
        out.add(f"{y:04d}{mth:02d}")
        mth += 1
        if mth > 12:
            y, mth = y + 1, 1
    return out


def _resolve_calendar_months(bounds: dict) -> set:
    return {_canon_request({"month": m}) for m in _month_strings(bounds)}


def _resolve_report_rc_month_ranges(bounds: dict) -> set:
    """report_rc's REAL monthly recipe is a RANGE: report_rc(start_date=YYYYMM01, end_date=<month end>)
    (scripts/fetch_bucket_a.py). GPT sign-off HOLD #2: this used to emit {"report_date": "YYYYMM"} — but
    the pinned doc's `report_date` is an EXACT report date, not a month, so the monthly PARTITION LABEL
    was standing in for the vendor request. The label is derived from the range, never sent as one."""
    import calendar as _cal
    out = set()
    for m in _month_strings(bounds):
        y, mth = int(m[:4]), int(m[4:6])
        last = _cal.monthrange(y, mth)[1]
        out.add(_canon_request({"start_date": f"{m}01", "end_date": f"{m}{last:02d}"}))
    return out


def _period_strings(bounds: dict) -> set:
    """Quarter-ends between the bounds, OR an EXPLICIT signed list. GPT: `report_periods` generated only
    standard quarter ends (73 for 20080331..20260331) while the baseline holds 98 indicator partitions —
    data_tracker records that legacy Tushare indicator history contains NON-QUARTER periods. A generated
    calendar cannot describe vendor-reported reality, so the contract may sign the period list itself."""
    explicit = bounds.get("periods")
    if explicit is not None:
        if not isinstance(explicit, list) or not explicit:
            raise RuntimeError("request_population.bounds.periods must be a non-empty signed list")
        return {str(p) for p in explicit}
    lo, hi = str(bounds["start"]), str(bounds["end"])
    return {f"{y}{md}" for y in range(int(lo[:4]), int(hi[:4]) + 1)
            for md in ("0331", "0630", "0930", "1231") if lo <= f"{y}{md}" <= hi}


def _resolve_report_periods(bounds: dict) -> set:
    return {_canon_request({"period": p}) for p in _period_strings(bounds)}


def _resolve_report_periods_x_types(bounds: dict) -> set:
    """periods x report_types — the Cartesian product GPT specified: report_type was unbound, so
    income_vip(period=20260331, report_type=999) was accepted though the real recipe uses ("2","3")
    (scripts/fetch_quarterly_statements.py)."""
    types = bounds.get("report_types")
    if not isinstance(types, list) or not types:
        raise RuntimeError("period_report_type populations must sign an explicit `report_types` list "
                           "(the direct-quarter recipe uses ['2', '3'])")
    return {_canon_request({"period": p, "report_type": str(t)})
            for p in _period_strings(bounds) for t in types}


def _resolve_quarter_end_dates(bounds: dict) -> set:
    """disclosure_date(end_date=<quarter end>) — the quarter stamp is sent as `end_date`, NOT `period`
    (scripts/fetch_bucket_a.py fetch_disclosure_date)."""
    return {_canon_request({"end_date": p}) for p in _period_strings(bounds)}


def _resolve_year_ranges(bounds: dict) -> set:
    """repurchase(start_date=YYYY0101, end_date=YYYY1231) — one request per YEAR
    (scripts/fetch_bucket_a.py fetch_repurchase)."""
    lo, hi = int(str(bounds["start"])[:4]), int(str(bounds["end"])[:4])
    if hi < lo:
        raise RuntimeError("year_ranges: end year precedes start year")
    return {_canon_request({"start_date": f"{y}0101", "end_date": f"{y}1231"})
            for y in range(lo, hi + 1)}


def _resolve_weekly_friday_end_dates(bounds: dict) -> set:
    """pledge_stat(end_date=<Friday>) — one request per weekly Friday
    (scripts/fetch_bucket_a.py fetch_pledge_stat)."""
    import datetime as _dt
    lo = _dt.datetime.strptime(str(bounds["start"]), "%Y%m%d").date()
    hi = _dt.datetime.strptime(str(bounds["end"]), "%Y%m%d").date()
    if hi < lo:
        raise RuntimeError("weekly_friday_end_dates: end precedes start")
    first = lo + _dt.timedelta(days=(4 - lo.weekday()) % 7)   # 4 = Friday
    out, d = set(), first
    while d <= hi:
        out.add(_canon_request({"end_date": d.strftime("%Y%m%d")}))
        d += _dt.timedelta(days=7)
    return out


_POPULATION_RESOLVERS = {
    "trade_cal_open_sessions": _resolve_open_sessions,
    "stock_basic_codes": _resolve_stock_codes,
    "stock_basic_ranges": _resolve_stock_ranges,
    "index_code_ranges": _resolve_index_ranges,
    "calendar_months": _resolve_calendar_months,
    "report_rc_month_ranges": _resolve_report_rc_month_ranges,
    "report_periods": _resolve_report_periods,
    "report_periods_x_types": _resolve_report_periods_x_types,
    "quarter_end_dates": _resolve_quarter_end_dates,
    "year_ranges": _resolve_year_ranges,
    "weekly_friday_end_dates": _resolve_weekly_friday_end_dates,
}

# which resolver legitimately produces each unit's COMPLETE request set
_UNIT_RESOLVERS = {
    "open_trade_date": "trade_cal_open_sessions",
    "stock": "stock_basic_codes",
    "stock_repartition": "stock_basic_ranges",
    "index_range": "index_code_ranges",
    "month": "calendar_months",
    "report_date_month": "report_rc_month_ranges",
    "period": "report_periods",
    "period_report_type": "report_periods_x_types",
    "quarter_end_date": "quarter_end_dates",
    "year_range": "year_ranges",
    "weekly_friday": "weekly_friday_end_dates",
}
# How a `partition` LABEL is DERIVED from the request it names (honesty check only — the label is
# NEVER the comparison key). GPT sign-off HOLD #2: report_date_month's label is a MONTH while its
# request is a start_date/end_date RANGE — a label is not always a parameter, so deriving it is the only
# honest way to check one. Each entry raises if the request lacks what the label is derived from.
def _label_from_param(name):
    def _f(params):
        if name not in params:
            raise RuntimeError(f"request {params} carries no {name!r} — its partition label is named by it")
        return str(params[name])
    return _f


def _label_from_month_range(params):
    if "start_date" not in params:
        raise RuntimeError(f"request {params} carries no 'start_date' — its monthly label derives from it")
    return str(params["start_date"])[:6]


_UNIT_LABEL_FROM_REQUEST = {
    "open_trade_date": _label_from_param("trade_date"), "stock": _label_from_param("ts_code"),
    "stock_repartition": _label_from_param("ts_code"), "index_range": _label_from_param("ts_code"),
    "month": _label_from_param("month"), "report_date_month": _label_from_month_range,
    "period": _label_from_param("period"), "period_report_type": _label_from_param("period"),
    # disclosure_date labels its partition by the quarter it asks for, which it sends as end_date
    "quarter_end_date": _label_from_param("end_date"),
    # repurchase's yearly file is named by the year its range covers
    "year_range": lambda params: _label_from_param("start_date")(params)[:4],
    "weekly_friday": _label_from_param("end_date"),
}


def endpoint_expected_resolvers(endpoint: str) -> set:
    """The resolver(s) this endpoint's own matrix rows imply. GPT sign-off HOLD #2: contract_errors
    accepted ANY known resolver — a valid `daily` contract using `calendar_months` returned ZERO errors,
    and the mismatch surfaced only once an adapter supplied a plan, which is far too late for a HUMAN
    to be signing the thing."""
    out = set()
    for r in ENDPOINT_MATRIX:
        if endpoint in r.source_endpoints and r.query_mode != "UNBOUND":
            res = _UNIT_RESOLVERS.get(_QUERY_MODE_TO_UNIT.get(r.query_mode))
            if res:
                out.add(res)
    return out


def resolve_population(spec: dict) -> set:
    """Execute the signed resolver and return the EXACT expected set of COMPLETE requests."""
    fn = _POPULATION_RESOLVERS.get(spec.get("resolver"))
    if fn is None:
        raise RuntimeError(f"unknown population resolver {spec.get('resolver')!r}; known: "
                           f"{sorted(_POPULATION_RESOLVERS)}")
    return fn(spec.get("bounds") or {})


def _request_population_key(pr: dict, row) -> tuple:
    """The COMPLETE canonical request this plan row actually makes — every parameter, from its own
    params. The `partition` label is checked for honesty against the unit's naming axis but is NEVER
    the comparison key (GPT: the label is not evidence about the request)."""
    unit = _QUERY_MODE_TO_UNIT.get(row.query_mode)
    params = pr.get("params") or {}
    if not isinstance(params, dict) or not params:
        raise RuntimeError(f"plan row {pr.get('request_id')}: no params — a request with no parameters "
                           f"cannot be proven to cover anything")
    deriver = _UNIT_LABEL_FROM_REQUEST.get(unit)
    if deriver is None:
        raise RuntimeError(f"plan row {pr.get('request_id')}: unit {unit!r} declares no label derivation; "
                           f"add it to _UNIT_LABEL_FROM_REQUEST before planning this endpoint")
    try:
        want_label = deriver(params)
    except RuntimeError as exc:
        raise RuntimeError(f"plan row {pr.get('request_id')} ({pr.get('endpoint')}): {exc}")
    if str(pr.get("partition")) != want_label:
        raise RuntimeError(f"plan row {pr.get('request_id')} ({pr.get('endpoint')}): partition label "
                           f"{pr.get('partition')!r} but the request derives label {want_label!r} — the "
                           f"label is not evidence about the request")
    return _canon_request(params)


def assert_population_is_correct(plan_rows: list, contracts: dict) -> None:
    """The plan's COMPLETE requests must equal the RESOLVED request set EXACTLY.

    GPT sign-off HOLD: the previous version reduced each request tuple to `k[0]`, so the comparison
    established only the primary axis — an unsigned report_type/range/filter rode along free. There is
    no projection here: `asked == expected`, whole requests both sides."""
    by_family = {r.output_family: r for r in ENDPOINT_MATRIX}
    seen = {}
    for pr in plan_rows:
        row = by_family.get(pr.get("dataset"))
        if row is None:
            continue
        seen.setdefault((pr["endpoint"], pr["dataset"]), set()).add(_request_population_key(pr, row))
    for (ep, fam), asked in seen.items():
        c = contracts.get(ep) or {}
        spec = c.get("request_population") or {}
        row = by_family[fam]
        unit = _QUERY_MODE_TO_UNIT.get(row.query_mode)
        want_resolver = _UNIT_RESOLVERS.get(unit)
        if spec.get("resolver") != want_resolver:
            raise RuntimeError(f"{ep}/{fam}: enumerates {unit!r} which resolves via {want_resolver!r}, "
                               f"but the signed contract declares resolver {spec.get('resolver')!r}")
        expected = resolve_population(spec)
        got_sha = request_set_sha256(expected)
        if spec.get("expected_set_sha256") != got_sha:
            raise RuntimeError(f"{ep}: the resolved request set ({len(expected)} requests, "
                               f"{got_sha[:12]}) is not the one signed "
                               f"({str(spec.get('expected_set_sha256'))[:12]}) — the bounds or the "
                               f"pinned reference no longer describe it")
        missing, extra = expected - asked, asked - expected
        if missing or extra:
            def _fmt(rs):
                return [dict(r) for r in sorted(rs)[:2]]
            raise RuntimeError(
                f"{ep}/{fam}: the plan does not make the signed REQUESTS — {len(missing)} missing "
                f"(e.g. {_fmt(missing)}), {len(extra)} NOT signed (e.g. {_fmt(extra)}). Comparison is on "
                f"COMPLETE requests: an unsigned report_type, range bound or filter is an unsigned "
                f"request even when its primary axis matches.")


def assert_multi_source_merge_coverage(plan_rows: list, contracts: dict) -> None:
    """A multi-source output (A01 `market/daily` = daily + daily_basic + adj_factor) is only correct if
    the three legs cover the SAME population, partition-for-partition, and the row declares how they
    join (GPT re-review #8 BLOCKER-1: 'A01 三来源分别使用不同交易日的计划' was ACCEPTED —
    `_QUERY_MODE_TO_UNIT` proves category consistency, NOT coverage or merge consistency)."""
    by_family = {r.output_family: r for r in ENDPOINT_MATRIX}
    for fam, row in by_family.items():
        if len(row.source_endpoints) < 2:
            continue
        legs = {}
        for pr in plan_rows:
            if pr.get("dataset") != fam:
                continue
            # GPT re-review #9 BLOCKER-2 (reproduced): this grouped on pr["partition"] — a LABEL the
            # planner writes — so legs that all CLAIMED "20260702" while daily_basic actually requested
            # "20260703" were accepted. Group on the REQUEST ITSELF, and prove the label is not lying.
            legs.setdefault(pr["endpoint"], set()).add(_request_population_key(pr, row))
        if not legs:
            continue
        missing = set(row.source_endpoints) - set(legs)
        if missing:
            raise RuntimeError(f"{fam}: the plan omits source leg(s) {sorted(missing)} — a merged output "
                               f"whose legs are not all planned cannot be complete")
        extra = set(legs) - set(row.source_endpoints)
        if extra:
            raise RuntimeError(f"{fam}: the plan carries unexpected source leg(s) {sorted(extra)}")
        ref_ep = row.source_endpoints[0]
        ref = legs[ref_ep]
        for ep, parts in legs.items():
            if parts != ref:
                only_ref, only_ep = sorted(ref - parts)[:3], sorted(parts - ref)[:3]
                raise RuntimeError(
                    f"{fam}: source legs REQUEST different populations — {ref_ep} has {len(ref)} and {ep} "
                    f"has {len(parts)} (only in {ref_ep}: {only_ref}; only in {ep}: {only_ep}). The legs "
                    f"of a merged output must be fetched over one identical population snapshot.")
        # the legs must also agree on WHAT population they claim to enumerate
        pops = {ep: (contracts.get(ep) or {}).get("request_population") for ep in row.source_endpoints}
        distinct = {json.dumps(v, sort_keys=True) for v in pops.values()}
        if len(distinct) != 1:
            raise RuntimeError(f"{fam}: source legs declare DIFFERENT request_population specs {pops} — "
                               f"they must share one population snapshot to merge row-for-row")
        if not isinstance(row.merge_spec, dict) or not row.merge_spec.get("join_on"):
            raise RuntimeError(f"{fam}: draws {len(row.source_endpoints)} sources but declares no "
                               f"merge_spec.join_on — the join/output rule must be explicit, not implied")


def assert_plan_matches_contracts(plan_rows: list, contracts: dict) -> None:
    """MECHANICALLY bind every frozen ledger request to the SIGNED contract, before any call.

    GPT re-review #8 BLOCKER-1: this used to compare ONLY the pagination axis and the population unit —
    it never called `contract_errors` and never checked the plan's `contract_sha256`, so a plan backed
    by a contract with no doc, no signer and no field constraints was ACCEPTED. Checking two fields of
    a contract is not checking the contract. Now:
      * the contract must be fully VALID+SIGNED (contract_errors == []) — the same gate `--plan` runs;
      * the row's `contract_sha256` must equal the canonical hash of that signed contract;
      * pagination mode/limit must equal the signed pagination_spec;
      * the declared population unit must match the matrix query_mode;
      * multi-source outputs must prove merge coverage (see assert_multi_source_merge_coverage).
    Raises on the first divergence."""
    if not plan_rows:
        raise RuntimeError("assert_plan_matches_contracts called with an EMPTY plan — it would pass "
                           "vacuously; an empty plan is refused at the freeze door")
    by_family = {r.output_family: r for r in ENDPOINT_MATRIX}
    validated: dict = {}
    for pr in plan_rows:
        ep = pr["endpoint"]
        c = contracts.get(ep) or {}
        if ep not in validated:
            errs = contract_errors(ep, c)
            if errs:
                raise RuntimeError(f"plan row {pr['request_id']} ({ep}): its contract is NOT a valid "
                                   f"signature — {errs}")
            validated[ep] = canonical_contract_sha256(c)
        want_hash = validated[ep]
        got_hash = str(pr.get("contract_sha256") or "")
        if got_hash != want_hash:
            raise RuntimeError(f"plan row {pr['request_id']} ({ep}): contract_sha256 {got_hash[:12]!r} "
                               f"!= the canonical hash of the signed contract {want_hash[:12]!r} — the "
                               f"plan is bound to a contract that is not the one on disk")
        # GPT re-review #9 BLOCKER-1 (reproduced): the hash proved the contract was UNCHANGED, never
        # that the PLAN IMPLEMENTS IT — a fully valid contract was accepted beside a plan that changed
        # empty_policy, natural_key and doc_sha256. Every contract-derived execution field must AGREE.
        for field in ("empty_policy", "doc_sha256"):
            if str(pr.get(field)) != str(c.get(field)):
                raise RuntimeError(f"plan row {pr['request_id']} ({ep}): {field} {pr.get(field)!r} != "
                                   f"signed {c.get(field)!r} — the plan does not implement its contract")
        if list(pr.get("natural_key") or []) != list(c.get("natural_key") or []):
            raise RuntimeError(f"plan row {pr['request_id']} ({ep}): natural_key "
                               f"{list(pr.get('natural_key') or [])} != signed "
                               f"{list(c.get('natural_key') or [])} — the plan does not implement its "
                               f"contract")
        spec = c["pagination_spec"]
        if pr.get("pagination_mode") != spec.get("mode"):
            raise RuntimeError(f"plan row {pr['request_id']} ({ep}): pagination_mode "
                               f"{pr.get('pagination_mode')!r} != signed {spec.get('mode')!r}")
        if int(pr.get("page_limit") or 0) != int(spec.get("page_limit") or 0):
            raise RuntimeError(f"plan row {pr['request_id']} ({ep}): page_limit "
                               f"{pr.get('page_limit')!r} != signed {spec.get('page_limit')!r}")
        row = by_family.get(pr.get("dataset"))
        if row is not None:
            # GPT re-review #10 BLOCKER (reproduced): the comparator accepted a moneyflow contract as
            # OWNER of market/stk_limit, a sparse contract for a dense matrix row, and a natural_key
            # NARROWER than the matrix vendor key. Bind endpoint ownership + empty policy + the complete
            # key EXACTLY to the matrix row.
            if ep not in row.source_endpoints:
                raise RuntimeError(f"plan row {pr['request_id']} ({ep}): endpoint does not OWN family "
                                   f"{row.output_family} — it draws only {sorted(row.source_endpoints)}")
            if str(c.get("empty_policy")) != str(row.empty_policy):
                raise RuntimeError(f"plan row {pr['request_id']} ({ep}): signed empty_policy "
                                   f"{c.get('empty_policy')!r} != the matrix's {row.empty_policy!r} "
                                   f"(a sparse contract for a dense row, or vice versa)")
            miss_vk = set(row.vendor_record_key) - derived_fields_for(ep) - set(c.get("natural_key") or [])
            if miss_vk:
                raise RuntimeError(f"plan row {pr['request_id']} ({ep}): signed natural_key "
                                   f"{list(c.get('natural_key') or [])} does NOT cover the matrix vendor "
                                   f"key column(s) {sorted(miss_vk)} — a narrower key collapses distinct "
                                   f"vendor rows")
            if list(pr.get("content_dedup_key") or []) != list(row.content_dedup_key):
                raise RuntimeError(f"plan row {pr['request_id']} ({ep}): content_dedup_key "
                                   f"{list(pr.get('content_dedup_key') or [])} != the matrix's "
                                   f"{list(row.content_dedup_key)}")
            if int(pr.get("max_content_dups") or 0) != int(row.max_content_dups):
                raise RuntimeError(f"plan row {pr['request_id']} ({ep}): max_content_dups "
                                   f"{pr.get('max_content_dups')!r} != the matrix's "
                                   f"{row.max_content_dups!r}")
            want = _UNIT_RESOLVERS.get(_QUERY_MODE_TO_UNIT.get(row.query_mode))
            got = (c.get("request_population") or {}).get("resolver")
            if want and got != want:
                raise RuntimeError(f"plan row {pr['request_id']} ({ep}): the matrix enumerates "
                                   f"{row.query_mode!r}, whose population resolves via {want!r}, but the "
                                   f"signed contract declares resolver {got!r}")
    assert_population_is_correct(plan_rows, contracts)   # EXACT set vs the signed resolver
    assert_multi_source_merge_coverage(plan_rows, contracts)


def load_signed_contracts() -> dict:
    """Read the LIVE signed contracts from disk (the fact), never a cached copy."""
    import yaml
    if not CONTRACTS_YAML.exists():
        return {}
    return yaml.safe_load(CONTRACTS_YAML.read_text(encoding="utf-8")) or {}


def assert_response_has_required_fields(endpoint: str, columns, *, contracts=None) -> None:
    """The FETCHED response must contain every field the signed contract declared as required (GPT
    re-review #10 BLOCKER: signed `required_fields` were never checked against the actual response, so a
    vendor schema change dropping a column would pass verification). Reads the LIVE contract INTERNALLY;
    `contracts` is a TEST seam only."""
    live = (contracts if contracts is not None else load_signed_contracts()).get(endpoint) or {}
    required = [str(f) for f in (live.get("required_fields") or [])]
    if not required:
        return  # no signed requirement (e.g. below the full contract layer) — nothing to enforce
    missing = [f for f in required if f not in set(map(str, columns))]
    if missing:
        raise RuntimeError(f"{endpoint}: the fetched response is MISSING signed required_fields "
                           f"{missing} — the vendor schema changed or the wrong endpoint answered")


def revalidate_contract_for_fetch(row: dict, *, contracts=None) -> None:
    """Re-prove at FETCH time that the endpoint's signed contract is STILL VALID and STILL the one the
    plan froze against — reading the LIVE contracts INTERNALLY (GPT re-review #10 BLOCKER: the binding
    used a PUBLIC MUTABLE `ledger.contract_loader` that production trusted, so swapping it hid a changed
    contract; and it only re-hashed the canonical form, never re-running doc validation, so editing the
    referenced doc did not stop the fetch). `contracts` is a TEST seam only — production passes nothing
    and the live YAML is read here, with no caller-replaceable state.

    FULL `contract_errors` re-run catches an edited doc (its `doc_sha256` no longer matches); the
    canonical-hash check catches a swapped contract."""
    ep = row["endpoint"]
    live = (contracts if contracts is not None else load_signed_contracts()).get(ep)
    if not live:
        raise RuntimeError(f"{ep}: no live contract at fetch time — it was signed when the plan froze "
                           f"and is gone now; refusing to fetch")
    errs = contract_errors(ep, live)
    if errs:
        raise RuntimeError(f"{ep}: the signed contract is NO LONGER VALID at fetch time (an edited doc "
                           f"or reference?) — {errs}")
    now = canonical_contract_sha256(live)
    if now != row.get("contract_sha256"):
        raise RuntimeError(f"{ep}: the signed contract CHANGED since the plan froze "
                           f"({str(row.get('contract_sha256'))[:12]} -> {now[:12]}); a frozen hash proves "
                           f"what WAS signed, not what is signed now — re-validate and re-freeze.")


def assert_plan_scope_is_complete(plan_rows: list, declared_families) -> None:
    """A plan must SAY what it covers, and cover it (GPT sign-off HOLD #2 MAJOR): the population check
    iterates the groups it FINDS, so an empty plan compared vacuously true and an omitted family was
    simply invisible. Nothing can verify a request that was never planned — only a declared scope makes
    absence detectable."""
    if not plan_rows:
        raise RuntimeError("empty plan: there is nothing to verify, and 'nothing' is not a recovery. "
                           "An empty plan previously passed every check vacuously.")
    declared = set(declared_families or ())
    if not declared:
        raise RuntimeError("freeze requires an explicit declared_families scope — without it an omitted "
                           "family is indistinguishable from one that was never intended")
    known = {r.output_family for r in ENDPOINT_MATRIX}
    unknown = declared - known
    if unknown:
        raise RuntimeError(f"declared_families names families the matrix does not own: {sorted(unknown)}")
    covered = {pr.get("dataset") for pr in plan_rows}
    missing = declared - covered
    if missing:
        raise RuntimeError(f"the plan declares {sorted(declared)} but has NO requests for "
                           f"{sorted(missing)} — a declared family with no requests is an omission, not "
                           f"an empty one")
    undeclared = covered - declared
    if undeclared:
        raise RuntimeError(f"the plan carries requests for {sorted(undeclared)}, which it does not "
                           f"declare — every fetched family must be in the declared scope")
    # every SOURCE LEG of each declared family must be planned (single-source families too; the
    # multi-source merge check only sees families that already have legs present)
    by_family = {r.output_family: r for r in ENDPOINT_MATRIX}
    for fam in sorted(declared):
        row = by_family[fam]
        legs = {pr["endpoint"] for pr in plan_rows if pr.get("dataset") == fam}
        # GPT sign-off HOLD #4 (reproduced): this checked only for MISSING legs, so a plan declaring
        # market/moneyflow but carrying fully-signed moneyflow AND hk_hold rows under that family passed
        # both scope and contract. Ownership must be EXACT — legs == the row's source_endpoints — or a
        # foreign endpoint's requests ride in under a family that does not own them.
        want = set(row.source_endpoints)
        absent, foreign = want - legs, legs - want
        if absent:
            raise RuntimeError(f"{fam}: declared but source leg(s) {sorted(absent)} have no requests")
        if foreign:
            raise RuntimeError(f"{fam}: carries requests for endpoint(s) {sorted(foreign)} that this "
                               f"family does not own — it draws only {sorted(want)}")


def freeze_request_plan(ledger, plan_rows: list, contracts: dict, *, declared_families=None) -> str:
    """THE single, non-bypassable door to freezing a request plan (GPT re-review #8 BLOCKER-1: contract
    validation, the canonical contract hash, the population snapshot and freeze_plan were separate, so
    a plan could be frozen without any of them). Validate-then-freeze, in one call; the ledger's
    freeze_plan is never invoked directly by recovery code."""
    assert_plan_scope_is_complete(plan_rows, declared_families)   # an empty/partial plan is not a plan
    assert_plan_matches_contracts(plan_rows, contracts)
    # No loader is installed on the ledger (GPT re-review #10 BLOCKER): fetch-time re-binding reads the
    # LIVE contracts INTERNALLY via revalidate_contract_for_fetch — there is no caller-replaceable state
    # to swap. Validation at freeze proves what WAS signed; every later page re-proves it is STILL signed
    # and still valid (a doc edit refuses).
    return ledger._freeze_plan_unvalidated(plan_rows)


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
    doc_ok = False
    if not doc.is_file():
        errs.append(f"{endpoint}: doc file missing: {doc}")
    elif sha256_file(doc) != str(c["doc_sha256"]).lower():
        errs.append(f"{endpoint}: doc_sha256 mismatch (doc changed since review)")
    else:
        doc_ok = True
    rf_ok = isinstance(c["required_fields"], list) and len(c["required_fields"]) >= 2
    if not rf_ok:
        errs.append(f"{endpoint}: required_fields must be a real field list")
    elif any(str(x).strip().lower() in _PLACEHOLDERS for x in c["required_fields"]):
        errs.append(f"{endpoint}: required_fields contains placeholder elements (['x',...])")
        rf_ok = False
    nk_ok = isinstance(c["natural_key"], list) and bool(c["natural_key"])
    if not nk_ok:
        errs.append(f"{endpoint}: natural_key must be a non-empty list")
    elif any(str(x).strip().lower() in _PLACEHOLDERS for x in c["natural_key"]):
        errs.append(f"{endpoint}: natural_key contains placeholder elements")
        nk_ok = False
    # M2: field membership — required_fields/natural_key must be REAL columns of the pinned doc (a
    # fabricated field list no longer passes). natural_key may also name a coordinator-DERIVED column.
    if doc_ok:
        # F4: the doc must PROVE it documents THIS endpoint — a real field table from another API
        # would otherwise approve the wrong contract.
        ident = parse_doc_identity(doc)
        if not ident["api_name"]:
            errs.append(f"{endpoint}: doc {doc.name} declares no 接口 name — cannot prove it documents "
                        f"this endpoint")
        elif not doc_declares_endpoint(ident["api_name"], endpoint):
            errs.append(f"{endpoint}: doc {doc.name} documents endpoint '{ident['api_name']}' — WRONG "
                        f"doc cited for '{endpoint}'")
        if not ident["doc_id"]:
            errs.append(f"{endpoint}: doc {doc.name} carries no doc_id header — cannot bind the "
                        f"contract to a specific interface document")
        elif str(c["doc_id"]) != ident["doc_id"]:
            errs.append(f"{endpoint}: contract doc_id {c['doc_id']} != doc's own doc_id "
                        f"{ident['doc_id']}")
    if doc_ok and (rf_ok or nk_ok):
        vocab = parse_doc_field_vocabulary(doc)
        if not vocab:
            errs.append(f"{endpoint}: no field table parsed from doc (wrong doc cited? cite the output-fields doc)")
        else:
            if rf_ok:
                missing = [f for f in c["required_fields"] if str(f) not in vocab]
                if missing:
                    errs.append(f"{endpoint}: required_fields not in doc field list: {missing}")
            if nk_ok:
                # derived columns are ENDPOINT-SCOPED (F4): an endpoint cannot borrow another's.
                # required_fields are NOT unioned in — they are themselves validated against `vocab`
                # above, so including them would let a FABRICATED required field vouch for a key.
                allowed = vocab | derived_fields_for(endpoint)
                bad = [f for f in c["natural_key"] if str(f) not in allowed]
                if bad:
                    errs.append(f"{endpoint}: natural_key columns not in doc field list nor this "
                                f"endpoint's declared derived fields: {bad}")
    if c["empty_policy"] not in ("dense_refuse", "sparse_canary"):
        errs.append(f"{endpoint}: empty_policy must be dense_refuse|sparse_canary")
    errs.extend(_pagination_spec_errors(endpoint, c.get("pagination_spec")))
    errs.extend(_population_spec_errors(endpoint, c.get("request_population")))
    # GPT re-review #7 minor: a RECOGNIZED signer, not merely a >=3-char string ("xxx" passed).
    if str(c["reviewed_by"]).strip().lower() not in _KNOWN_SIGNERS:
        errs.append(f"{endpoint}: reviewed_by {c['reviewed_by']!r} is not a recognized signer "
                    f"({sorted(_KNOWN_SIGNERS)}) — a contract signature must name a real reviewer")
    # GPT re-review #7 minor: a timezone-NAIVE reviewed_at was silently assigned UTC, so a local
    # timestamp could read as up to a day off (and slip a future review past the check).
    try:
        ts = datetime.fromisoformat(str(c["reviewed_at"]))
        if ts.tzinfo is None or ts.tzinfo.utcoffset(ts) is None:
            errs.append(f"{endpoint}: reviewed_at must be timezone-AWARE (got a naive timestamp; it "
                        f"was previously assumed UTC, which silently accepts a wrong instant)")
        elif ts > datetime.now(timezone.utc):
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
