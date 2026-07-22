# -*- coding: utf-8 -*-
"""Recovery adapters — the declarative fetch layer over the page-receipt ledger (adapter design v4).

Everything fetch-affecting here is DATA, frozen into the plan and content-hashed into the adapter
bundle manifest: CallRecipes (vendor method + parameter maps — no code, no thunks), response scopes
(request-bound row-membership rules), family specs (partition/output layout) and consolidation specs
(physical layout + typed conservation). The LEDGER owns every mutating step (leases, the one wire call,
preparation, scope, receipts, terminals, resume); this module owns only the declarative registry, the
plan builder, the executors, and the run/consolidate orchestration loops.

The quartet (interface-freeze unit): A01 market/daily (dense per-date, 3-leg merge), A03a income
(sparse per-stock, offset-paged, per-end_date repartition), A11a top_list (event, derived
row_payload_digest, omit-empty), A16 broker_recommend (monthly). Fan-out to the other families is a
SEPARATE unit after this one passes review.

NO Tushare call happens in this module without: a live_authorized run mode, a hash-chained
fetch_authorized ledger event (the §13 authority — written only by the authorize-fetch CLI), and a
LiveExecutor whose fetcher the caller constructed. The pre-fetch battery drives everything with a
SyntheticExecutor, which cannot reach the vendor (no fetcher exists on that path).
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import raw_recovery_coordinator as rrc          # noqa: E402
import recovery_ledger as rl                    # noqa: E402


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# ── CallRecipes (design v4 §2a — declarative data, no thunks) ────────────────────────────────────
@dataclass(frozen=True)
class CallRecipe:
    recipe_id: str
    vendor_method: str
    request_parameter_map: tuple                 # ((request_key, vendor_kwarg), ...) — rename/copy ONLY
    constant_kwargs: tuple                       # ((kwarg, json-scalar), ...) — content-hashed constants
    pagination_binding: object                   # "none" | ("limit_kw", "offset_kw")

    def as_registry_entry(self) -> dict:
        return {"recipe_id": self.recipe_id, "vendor_method": self.vendor_method,
                "request_parameter_map": list(map(list, self.request_parameter_map)),
                "constant_kwargs": list(map(list, self.constant_kwargs)),
                "pagination_binding": (self.pagination_binding if self.pagination_binding == "none"
                                       else list(self.pagination_binding))}


# The fixed report_rc projection (constant_kwargs case; carries create_time, the PIT anchor —
# machine-required in the signed contract since design re-review #3).
REPORT_RC_FIELDS = ("ts_code,name,report_date,report_title,report_type,classify,org_name,"
                    "author_name,quarter,op_rt,op_pr,tp,np,eps,pe,rd,roe,ev_ebitda,rating,"
                    "max_price,min_price,create_time")

RECIPES: dict = {r.recipe_id: r for r in [
    CallRecipe("daily_by_trade_date", "daily",
               (("trade_date", "trade_date"),), (), "none"),
    CallRecipe("daily_basic_by_trade_date", "daily_basic",
               (("trade_date", "trade_date"),), (), "none"),
    CallRecipe("adj_factor_by_trade_date_paged", "adj_factor",
               (("trade_date", "trade_date"),), (), ("limit", "offset")),
    CallRecipe("income_by_stock_paged", "income",
               (("ts_code", "ts_code"),), (), ("limit", "offset")),
    CallRecipe("top_list_by_trade_date", "top_list",
               (("trade_date", "trade_date"),), (), "none"),
    CallRecipe("broker_recommend_by_month", "broker_recommend",
               (("month", "month"),), (), "none"),
    CallRecipe("report_rc_month_range_paged", "report_rc",
               (("start_date", "start_date"), ("end_date", "end_date")),
               (("fields", ",".join(REPORT_RC_FIELDS.split(","))),), ("limit", "offset")),
    # ── fan-out batch 1 ───────────────────────────────────────────────────────────────────────────
    # per-open-session market legs (single call per session; see each signed pagination_spec)
    CallRecipe("moneyflow_by_trade_date", "moneyflow", (("trade_date", "trade_date"),), (), "none"),
    CallRecipe("stk_limit_by_trade_date_paged", "stk_limit",
               (("trade_date", "trade_date"),), (), ("limit", "offset")),
    CallRecipe("margin_detail_by_trade_date", "margin_detail",
               (("trade_date", "trade_date"),), (), "none"),
    CallRecipe("hk_hold_by_trade_date", "hk_hold", (("trade_date", "trade_date"),), (), "none"),
    CallRecipe("suspend_d_by_trade_date", "suspend_d", (("trade_date", "trade_date"),), (), "none"),
    CallRecipe("top_inst_by_trade_date", "top_inst", (("trade_date", "trade_date"),), (), "none"),
    CallRecipe("block_trade_by_trade_date_paged", "block_trade",
               (("trade_date", "trade_date"),), (), ("limit", "offset")),
    # per-index range
    CallRecipe("index_daily_by_code_range", "index_daily",
               (("ts_code", "ts_code"), ("start_date", "start_date"), ("end_date", "end_date")),
               (), "none"),
    # per-stock legs
    CallRecipe("balancesheet_by_stock_paged", "balancesheet",
               (("ts_code", "ts_code"),), (), ("limit", "offset")),
    CallRecipe("cashflow_by_stock_paged", "cashflow", (("ts_code", "ts_code"),), (), ("limit", "offset")),
    CallRecipe("forecast_by_stock", "forecast", (("ts_code", "ts_code"),), (), "none"),
    CallRecipe("dividend_by_stock", "dividend", (("ts_code", "ts_code"),), (), "none"),
    CallRecipe("stk_holdernumber_by_stock", "stk_holdernumber", (("ts_code", "ts_code"),), (), "none"),
    CallRecipe("fina_audit_by_stock", "fina_audit", (("ts_code", "ts_code"),), (), "none"),
    # per-stock + range (chip distribution)
    CallRecipe("cyq_perf_by_stock_range", "cyq_perf",
               (("ts_code", "ts_code"), ("start_date", "start_date"), ("end_date", "end_date")),
               (), "none"),
    # direct-quarter VIP (period x report_type)
    CallRecipe("income_vip_by_period_type_paged", "income_vip",
               (("period", "period"), ("report_type", "report_type")), (), ("limit", "offset")),
    CallRecipe("cashflow_vip_by_period_type_paged", "cashflow_vip",
               (("period", "period"), ("report_type", "report_type")), (), ("limit", "offset")),
    # per-period fundamentals (VIP full-market where the caller used the _vip method)
    CallRecipe("express_by_period", "express_vip", (("period", "period"),), (), "none"),
    CallRecipe("fina_mainbz_by_period_paged", "fina_mainbz_vip",
               (("period", "period"),), (), ("limit", "offset")),
    CallRecipe("top10_floatholders_by_period_paged", "top10_floatholders",
               (("period", "period"),), (), ("limit", "offset")),
    # quarter-stamp / weekly legs (the stamp is sent AS end_date)
    CallRecipe("disclosure_date_by_quarter_paged", "disclosure_date",
               (("end_date", "end_date"),), (), ("limit", "offset")),
    CallRecipe("pledge_stat_by_week_paged", "pledge_stat",
               (("end_date", "end_date"),), (), ("limit", "offset")),
    # ── fan-out batch 2 ───────────────────────────────────────────────────────────────────────────
    CallRecipe("stk_holdertrade_by_stock", "stk_holdertrade", (("ts_code", "ts_code"),), (), "none"),
    CallRecipe("repurchase_by_year_range_paged", "repurchase",
               (("start_date", "start_date"), ("end_date", "end_date")), (), ("limit", "offset")),
]}

#: endpoint -> its ONE frozen recipe (the plan builder refuses an endpoint without one)
ENDPOINT_RECIPE: dict = {
    "daily": "daily_by_trade_date",
    "daily_basic": "daily_basic_by_trade_date",
    "adj_factor": "adj_factor_by_trade_date_paged",
    "income": "income_by_stock_paged",
    "top_list": "top_list_by_trade_date",
    "broker_recommend": "broker_recommend_by_month",
    "report_rc": "report_rc_month_range_paged",
    # fan-out batch 1
    "moneyflow": "moneyflow_by_trade_date",
    "stk_limit": "stk_limit_by_trade_date_paged",
    "margin_detail": "margin_detail_by_trade_date",
    "hk_hold": "hk_hold_by_trade_date",
    "suspend_d": "suspend_d_by_trade_date",
    "top_inst": "top_inst_by_trade_date",
    "block_trade": "block_trade_by_trade_date_paged",
    "index_daily": "index_daily_by_code_range",
    "balancesheet": "balancesheet_by_stock_paged",
    "cashflow": "cashflow_by_stock_paged",
    "forecast": "forecast_by_stock",
    "dividend": "dividend_by_stock",
    "stk_holdernumber": "stk_holdernumber_by_stock",
    "fina_audit": "fina_audit_by_stock",
    "cyq_perf": "cyq_perf_by_stock_range",
    "income_vip": "income_vip_by_period_type_paged",
    "cashflow_vip": "cashflow_vip_by_period_type_paged",
    "express": "express_by_period",
    "fina_mainbz": "fina_mainbz_by_period_paged",
    "top10_floatholders": "top10_floatholders_by_period_paged",
    "disclosure_date": "disclosure_date_by_quarter_paged",
    "pledge_stat": "pledge_stat_by_week_paged",
    # fan-out batch 2
    "stk_holdertrade": "stk_holdertrade_by_stock",
    "repurchase": "repurchase_by_year_range_paged",
}


def validate_recipe(recipe: CallRecipe) -> None:
    """Freeze-time recipe hygiene (design v4 §2a): request-map / constant / paging keys pairwise
    DISJOINT; the map is rename/copy only (no code exists to validate — that IS the guarantee)."""
    req_kws = [v for _, v in recipe.request_parameter_map]
    const_kws = [k for k, _ in recipe.constant_kwargs]
    page_kws = [] if recipe.pagination_binding == "none" else list(recipe.pagination_binding)
    all_kws = req_kws + const_kws + page_kws
    if len(all_kws) != len(set(all_kws)):
        raise RuntimeError(f"recipe {recipe.recipe_id}: vendor kwargs collide across "
                           f"request/constant/paging ({all_kws}) — the disjointness rule is violated")


# ── response scopes (design v4 §2d — frozen per plan row, concrete values) ───────────────────────
#: EXPLICIT per-endpoint response-scope rules (fan-out): which RESPONSE column must match which
#: REQUEST key, and how. Declared per endpoint rather than guessed from the request's shape — the
#: heuristic version silently mis-scoped families whose response column differs from the request key
#: (e.g. a `period` request whose rows carry `end_date`, or a year range matched on `ann_date` vs
#: `report_date`). Unknown endpoint => fail closed.
#:   ("eq", response_col, request_key)                    -> every row's col == the requested value
#:   ("date_in_range", response_col, lo_key, hi_key)      -> typed date containment
_SCOPE_RULES: dict = {
    # per-open-session market: the response's trade_date IS the requested session
    **{ep: [("eq", "trade_date", "trade_date")] for ep in (
        "daily", "daily_basic", "adj_factor", "moneyflow", "stk_limit", "margin_detail",
        "hk_hold", "suspend_d", "top_list", "top_inst", "block_trade")},
    # per-stock legs: the response's ts_code IS the requested stock
    **{ep: [("eq", "ts_code", "ts_code")] for ep in (
        "income", "balancesheet", "cashflow", "forecast", "dividend", "stk_holdernumber",
        "stk_holdertrade", "fina_audit")},
    # per-stock + range: the stock must match AND every row's date must fall inside the window
    "cyq_perf": [("eq", "ts_code", "ts_code"),
                 ("date_in_range", "trade_date", "start_date", "end_date")],
    "index_daily": [("eq", "ts_code", "ts_code"),
                    ("date_in_range", "trade_date", "start_date", "end_date")],
    # per-period fundamentals: the request sends `period`, the ROWS carry `end_date`
    **{ep: [("eq", "end_date", "period")] for ep in ("express", "fina_mainbz", "top10_floatholders")},
    # direct-quarter VIP: period AND the requested report_type must both match
    **{ep: [("eq", "end_date", "period"), ("eq", "report_type", "report_type")]
       for ep in ("income_vip", "cashflow_vip")},
    # quarter-stamp / weekly legs send the stamp AS end_date
    "disclosure_date": [("eq", "end_date", "end_date")],
    "pledge_stat": [("eq", "end_date", "end_date")],
    # month/range legs
    "broker_recommend": [("eq", "month", "month")],
    "report_rc": [("date_in_range", "report_date", "start_date", "end_date")],
    "repurchase": [("date_in_range", "ann_date", "start_date", "end_date")],
}


def response_scope_of(endpoint: str, request: dict) -> dict:
    """The request-bound row-membership rule frozen into the plan row, built from the endpoint's
    DECLARED rule with the request's CONCRETE values substituted. Fail-closed: an endpoint with no
    declared rule, or a rule naming a request key this request lacks, refuses — an unscoped request
    must never be frozen."""
    rules = _SCOPE_RULES.get(endpoint)
    if not rules:
        raise RuntimeError(f"{endpoint}: no declared response-scope rule — an unscoped request must "
                           f"never be frozen (fail closed); declare one in _SCOPE_RULES")
    checks = []
    for rule in rules:
        if rule[0] == "eq":
            _, col, key = rule
            if key not in request:
                raise RuntimeError(f"{endpoint}: scope rule needs request key {key!r}, absent from "
                                   f"{sorted(request)}")
            checks.append([col, "eq", str(request[key])])
        elif rule[0] == "date_in_range":
            _, col, lo_key, hi_key = rule
            if lo_key not in request or hi_key not in request:
                raise RuntimeError(f"{endpoint}: scope rule needs {lo_key!r}/{hi_key!r}, absent from "
                                   f"{sorted(request)}")
            checks.append([col, "date_in_range", [str(request[lo_key]), str(request[hi_key])]])
        else:
            raise RuntimeError(f"{endpoint}: unknown scope rule mode {rule[0]!r}")
    return {"rule_id": f"{endpoint}_scope", "checks": checks}


# ── family + consolidation specs (design v4 §2c/§2e) ─────────────────────────────────────────────
@dataclass(frozen=True)
class ConsolidationSpec:
    recipe_id: str                              # merge/repartition recipe (hashed into the bundle)
    output_partition_col: str                   # row -> output partition key column
    output_path_fmt: str                        # format(partition=...) -> relative consolidated path
    conservation_mode: str                      # multiset_identity | base_key_preserving_merge
    empty_contribution: str                     # zero_rows | omit_output
    partition_transform: str = "identity"       # identity | year  (fan-out batch 2)
    label: str = ""                             # output-family label when a fetch feeds >1 layout

    def partition_of_value(self, value: str) -> str:
        """Map a row's partition-column VALUE to its output partition. `year` implements the
        matrix's *_yearly consolidation groups (report_rc_yearly, repurchase_yearly,
        stk_holdertrade_yearly, suspension_yearly), where many rows/requests fold into one file per
        YEAR of a date column — expressed as DECLARATIVE data, not code in the adapter."""
        v = str(value)
        if self.partition_transform == "year":
            if len(v) < 4 or not v[:4].isdigit():
                raise RuntimeError(f"partition_transform=year needs a YYYY-prefixed date, got {v!r}")
            return v[:4]
        if self.partition_transform != "identity":
            raise RuntimeError(f"unknown partition_transform {self.partition_transform!r}")
        return v

    def family_output_of(self, partition: str) -> str:
        return self.output_path_fmt.format(partition=partition, yyyy=str(partition)[:4])


@dataclass(frozen=True)
class FamilySpec:
    owner: str
    output_family: str
    endpoints: tuple
    partition_key: object                       # a request key, or a TUPLE of keys (composite)
    consolidation: object                       # ConsolidationSpec | tuple[ConsolidationSpec, ...]

    @property
    def consolidations(self) -> tuple:
        """One FETCH family may feed SEVERAL physical layouts (fan-out batch 2). suspend_d is the
        case: the matrix declares both `market/suspend_d` (per-date store) and `market/suspension`
        (yearly files) over the SAME population, so planning them as two families would mint an
        IDENTICAL request_id for every session. The population is fetched ONCE and consolidated
        TWICE, each layout labelled."""
        c = self.consolidation
        return tuple(c) if isinstance(c, (tuple, list)) else (c,)

    def partition_of(self, request: dict) -> str:
        """DELEGATES to the coordinator's canonical per-unit label deriver — the SAME function the
        freeze door's honesty check uses — so the planner and the check cannot disagree.

        They had, in both directions, and no per-family test caught it because each side was
        self-consistent: the VIP families planned on (period, report_type) while the check derived from
        `period` alone, and A14/A15e planned on the raw `start_date` while the signed label is a month
        / a year. Restating a derivation is the same defect class as restating the report_rc digest
        field list or the daily merge. `partition_key` remains the DECLARATION of the axes (it is what
        the registry entry and the composite-uniqueness reasoning read); the derivation itself has one
        home. The fallback covers a family whose owner has no matrix unit."""
        deriver = rrc.unit_label_deriver_for_owner(self.owner)
        if deriver is not None:
            return deriver(request)
        if isinstance(self.partition_key, (tuple, list)):
            return "_".join(str(request[k]) for k in self.partition_key)
        return str(request[self.partition_key])

    def request_output_of(self, endpoint: str, request: dict) -> str:
        return f"requests/{self.owner}/{endpoint}/{self.partition_of(request)}.parquet"

    def as_registry_entry(self) -> dict:
        c = self.consolidation
        return {"owner": self.owner, "output_family": self.output_family,
                "endpoints": list(self.endpoints), "partition_key": self.partition_key,
                "consolidation": {"recipe_id": c.recipe_id,
                                  "output_partition_col": c.output_partition_col,
                                  "output_path_fmt": c.output_path_fmt,
                                  "conservation_mode": c.conservation_mode,
                                  "empty_contribution": c.empty_contribution}}


QUARTET: dict = {s.owner: s for s in [
    FamilySpec("A01", "market/daily", ("daily", "daily_basic", "adj_factor"), "trade_date",
               ConsolidationSpec("merge_daily_legs_v1", "trade_date",
                                 "consolidated/market/daily/{yyyy}/daily_{partition}.parquet",
                                 "base_key_preserving_merge", "zero_rows")),
    FamilySpec("A03a", "fundamentals/income", ("income",), "ts_code",
               ConsolidationSpec("repartition_by_end_date_v1", "end_date",
                                 "consolidated/fundamentals/income/income_{partition}.parquet",
                                 "multiset_identity", "zero_rows")),
    FamilySpec("A11a", "market/top_list", ("top_list",), "trade_date",
               ConsolidationSpec("repartition_by_trade_date_v1", "trade_date",
                                 "consolidated/market/top_list/{yyyy}/top_list_{partition}.parquet",
                                 "multiset_identity", "omit_output")),
    FamilySpec("A16", "analyst/broker_recommend", ("broker_recommend",), "month",
               ConsolidationSpec("repartition_by_month_v1", "month",
                                 "consolidated/analyst/broker_recommend/broker_recommend_{partition}.parquet",
                                 "multiset_identity", "omit_output")),
]}

# ── fan-out batch 1: the 22 families whose declared layout maps onto the frozen interface ─────────
# Layouts are NOT guessed: each ConsolidationSpec follows the matrix row's own `consolidation_group`
# (*_per_date -> trade_date, *_period -> end_date, *_per_code -> ts_code, *_weekly -> the Friday
# end_date). The 4 families whose group is *_yearly (A12 stk_holdertrade, A15e repurchase, A14
# report_rc) or which share an endpoint (A10a suspension, same suspend_d population as A10b) are
# DEFERRED to batch 2 — they need a declarative partition transform / multi-consolidation support,
# and adding either silently mid-fan-out would be exactly the interface drift the freeze exists to
# prevent. A07 indicators stays BLOCKED(contract) pending its §13 period-discovery probe.
def _per_date(owner, family, endpoint, path_fmt, empty):
    return FamilySpec(owner, family, (endpoint,), "trade_date",
                      ConsolidationSpec(f"repartition_by_trade_date_{owner}", "trade_date",
                                        path_fmt, "multiset_identity", empty))


def _per_period(owner, family, endpoint, path_fmt, partition_key="ts_code"):
    return FamilySpec(owner, family, (endpoint,), partition_key,
                      ConsolidationSpec(f"repartition_by_end_date_{owner}", "end_date",
                                        path_fmt, "multiset_identity", "omit_output"))


FANOUT_BATCH1: dict = {s.owner: s for s in [
    # ── per-open-session market (request partition == output partition == trade_date) ────────────
    _per_date("A08a", "market/moneyflow", "moneyflow",
              "consolidated/market/moneyflow/{yyyy}/moneyflow_{partition}.parquet", "omit_output"),
    _per_date("A08b", "market/stk_limit", "stk_limit",
              "consolidated/market/stk_limit/{yyyy}/stk_limit_{partition}.parquet", "zero_rows"),
    _per_date("A08c", "market/margin", "margin_detail",
              "consolidated/market/margin/{yyyy}/margin_{partition}.parquet", "zero_rows"),
    _per_date("A08d", "market/northbound", "hk_hold",
              "consolidated/market/northbound/{yyyy}/northbound_{partition}.parquet", "omit_output"),
    _per_date("A11b", "market/top_inst", "top_inst",
              "consolidated/market/top_inst/{yyyy}/top_inst_{partition}.parquet", "omit_output"),
    _per_date("A11c", "market/block_trade", "block_trade",
              "consolidated/market/block_trade/{yyyy}/block_trade_{partition}.parquet", "omit_output"),
    # ── per-stock REQUEST -> per-date OUTPUT (the cyq repartition; grp=cyq_per_date) ─────────────
    FamilySpec("A13", "market/cyq_perf", ("cyq_perf",), "ts_code",
               ConsolidationSpec("repartition_by_trade_date_A13", "trade_date",
                                 "consolidated/market/cyq_perf/{yyyy}/cyq_perf_{partition}.parquet",
                                 "multiset_identity", "omit_output")),
    # ── per-index-code range (grp=index_per_code -> one output per CODE) ─────────────────────────
    FamilySpec("A02", "market/index", ("index_daily",), "ts_code",
               ConsolidationSpec("repartition_by_code_A02", "ts_code",
                                 "consolidated/market/index/index_{partition}.parquet",
                                 "multiset_identity", "omit_output")),
    # ── per-stock REQUEST -> per-period OUTPUT (grp=*_period) ────────────────────────────────────
    _per_period("A03b", "fundamentals/balancesheet", "balancesheet",
                "consolidated/fundamentals/balancesheet/balancesheet_{partition}.parquet"),
    _per_period("A05", "fundamentals/cashflow", "cashflow",
                "consolidated/fundamentals/cashflow/cashflow_{partition}.parquet"),
    _per_period("A06", "fundamentals/forecast", "forecast",
                "consolidated/fundamentals/forecast/forecast_{partition}.parquet"),
    _per_period("A03c", "corporate/dividends", "dividend",
                "consolidated/corporate/dividends/dividends_{partition}.parquet"),
    _per_period("A09", "corporate/holder_number", "stk_holdernumber",
                "consolidated/corporate/holder_number/holder_number_{partition}.parquet"),
    # grp=fina_audit_stock -> one output per STOCK
    FamilySpec("A15d", "fundamentals/fina_audit", ("fina_audit",), "ts_code",
               ConsolidationSpec("repartition_by_stock_A15d", "ts_code",
                                 "consolidated/fundamentals/fina_audit/fina_audit_{partition}.parquet",
                                 "multiset_identity", "omit_output")),
    # ── per-period REQUEST -> per-period OUTPUT ──────────────────────────────────────────────────
    _per_period("A15a", "fundamentals/express", "express",
                "consolidated/fundamentals/express/express_{partition}.parquet", "period"),
    _per_period("A15c", "fundamentals/fina_mainbz", "fina_mainbz",
                "consolidated/fundamentals/fina_mainbz/fina_mainbz_{partition}.parquet", "period"),
    _per_period("A15g", "corporate/top10_floatholders", "top10_floatholders",
                "consolidated/corporate/top10_floatholders/top10_floatholders_{partition}.parquet",
                "period"),
    # ── direct-quarter VIP: (period, report_type) requests -> ONE per-period output ──────────────
    FamilySpec("A04a", "fundamentals/income_quarterly", ("income_vip",), ("period", "report_type"),
               ConsolidationSpec("repartition_by_end_date_A04a", "end_date",
                                 "consolidated/fundamentals/income_quarterly/income_quarterly_{partition}.parquet",
                                 "multiset_identity", "omit_output")),
    FamilySpec("A04b", "fundamentals/cashflow_quarterly", ("cashflow_vip",), ("period", "report_type"),
               ConsolidationSpec("repartition_by_end_date_A04b", "end_date",
                                 "consolidated/fundamentals/cashflow_quarterly/cashflow_quarterly_{partition}.parquet",
                                 "multiset_identity", "omit_output")),
    # ── quarter-stamp / weekly legs (the stamp IS the request key AND the output partition) ──────
    FamilySpec("A15b", "fundamentals/disclosure_date", ("disclosure_date",), "end_date",
               ConsolidationSpec("repartition_by_end_date_A15b", "end_date",
                                 "consolidated/fundamentals/disclosure_date/disclosure_date_{partition}.parquet",
                                 "multiset_identity", "omit_output")),
    FamilySpec("A15f", "corporate/pledge_stat", ("pledge_stat",), "end_date",
               ConsolidationSpec("repartition_by_end_date_A15f", "end_date",
                                 "consolidated/corporate/pledge_stat/pledge_stat_{partition}.parquet",
                                 "multiset_identity", "omit_output")),
]}

# ── fan-out batch 2: the families needing the year transform / multi-consolidation ───────────────
FANOUT_BATCH2: dict = {s.owner: s for s in [
    # per-stock REQUEST -> YEARLY output on ann_date (grp=stk_holdertrade_yearly)
    FamilySpec("A12", "corporate/stk_holdertrade", ("stk_holdertrade",), "ts_code",
               ConsolidationSpec("repartition_by_year_A12", "ann_date",
                                 "consolidated/corporate/stk_holdertrade/stk_holdertrade_{partition}.parquet",
                                 "multiset_identity", "omit_output", partition_transform="year")),
    # per-YEAR-range REQUEST -> yearly output on ann_date (grp=repurchase_yearly)
    FamilySpec("A15e", "corporate/repurchase", ("repurchase",), "start_date",
               ConsolidationSpec("repartition_by_year_A15e", "ann_date",
                                 "consolidated/corporate/repurchase/repurchase_{partition}.parquet",
                                 "multiset_identity", "omit_output", partition_transform="year")),
    # MONTHLY range requests -> YEARLY files on report_date (grp=report_rc_yearly): a genuine
    # many-to-one repartition (12 monthly requests fold into one year file). Its
    # report_rc_payload_digest producer is now registered in the ledger's prepare registry.
    FamilySpec("A14", "analyst/report_rc", ("report_rc",), "start_date",
               ConsolidationSpec("repartition_by_year_A14", "report_date",
                                 "consolidated/analyst/report_rc/report_rc_{partition}.parquet",
                                 "multiset_identity", "zero_rows", partition_transform="year")),
    # ── ONE fetch, TWO layouts (A10b + A10a) ─────────────────────────────────────────────────────
    # The matrix declares market/suspend_d (per-date store) and market/suspension (yearly files) over
    # the SAME suspend_d population. Planning both as families would mint an IDENTICAL request_id per
    # session (the freeze refuses it), so the population is fetched ONCE under market/suspend_d and
    # consolidated TWICE — each layout labelled so the verdict attributes its outputs correctly.
    FamilySpec("A10", "market/suspend_d", ("suspend_d",), "trade_date",
               (ConsolidationSpec("repartition_by_trade_date_A10b", "trade_date",
                                  "consolidated/market/suspend_d/{yyyy}/suspend_d_{partition}.parquet",
                                  "multiset_identity", "omit_output", label="market/suspend_d"),
                ConsolidationSpec("repartition_by_year_A10a", "trade_date",
                                  "consolidated/market/suspension/suspension_{partition}.parquet",
                                  "multiset_identity", "omit_output", partition_transform="year",
                                  label="market/suspension"))),
]}

#: every family the adapter layer can currently execute (quartet + batch 1 + batch 2)
ALL_FAMILIES: dict = {**QUARTET, **FANOUT_BATCH1, **FANOUT_BATCH2}

#: STILL deferred after batch 2, with the reason (never silently absent)
DEFERRED_FAMILIES: dict = {
    "A07": "indicators — fina_indicator_vip is UNSIGNED: the surviving manifest records 98 partitions "
           "but only 73 standard quarter-ends are reconstructible, so the contract is held at "
           "BLOCKED(contract) pending a §13 period-discovery probe that enumerates the served periods",
}

#: families the matrix declares that are produced as a SECOND layout of another family's fetch,
#: rather than as their own plan rows (documented so a reader does not read absence as an omission)
CONSOLIDATED_AS_SECOND_LAYOUT: dict = {
    "A10a": "market/suspension — the yearly layout of the A10 (suspend_d) fetch; see FANOUT_BATCH2",
}


# ── the canonical A01 merger (design v4 F9 — shared pure function) ───────────────────────────────
def merge_daily_legs(df_daily, df_basic, df_adj, target_date: str):
    """Delegates to the ONE canonical merger that the production daily pipeline also calls
    (`data_infra.daily_merge`), so a recovered `market/daily` file and a live one are produced by
    identical code — the F9 rider, now closed on both sides.

    Restating the merge here would let the recovered store drift from the live store exactly the way a
    restated field list would let the report_rc recovery digest drift from the SERVING digest. Imported
    lazily, matching how the ledger reaches `pit_backend.report_rc_payload_digest`.

    The consolidation was NOT cosmetic: this side was missing production's post-merge payload check, so
    a mis-keyed daily_basic that left-merged to all-NULL would have been written into the recovered
    store while passing every check that used to be here."""
    _src = str(Path(__file__).resolve().parents[1] / "src")
    if _src not in sys.path:
        sys.path.insert(0, _src)
    from data_infra.daily_merge import merge_daily_legs as _canonical
    return _canonical(df_daily, df_basic, df_adj, target_date)


# ── bundle manifest (design v4 Q1 — content-hashed, not git HEAD) ────────────────────────────────
_BUNDLE_FILES = (
    "scripts/recovery_adapters.py",
    "scripts/recovery_ledger.py",
    "scripts/recovery_write_broker.py",
    "scripts/raw_recovery_coordinator.py",
    "src/data_infra/fetchers/__init__.py",
    # the canonical A01 merger now lives in src/ and is shared with the production daily pipeline —
    # it decides what a recovered market/daily file CONTAINS, so a change to it must invalidate the
    # frozen bundle exactly like a change to a recipe does
    "src/data_infra/daily_merge.py",
)


def compute_bundle_manifest() -> dict:
    """Relative path + sha256 of every fetch-affecting module PLUS the canonical declarative registry
    entries. Recomputed at freeze, resume, and before live execution — a dirty relevant file changes
    the hash where a git commit lookup would not."""
    root = _HERE.parent
    files = {}
    for rel in _BUNDLE_FILES:
        p = root / rel
        files[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    registry = {
        "recipes": {rid: r.as_registry_entry() for rid, r in sorted(RECIPES.items())},
        "endpoint_recipe": dict(sorted(ENDPOINT_RECIPE.items())),
        "families": {o: s.as_registry_entry() for o, s in sorted(QUARTET.items())},
        "scope_rules": ["eq_trade_date", "eq_ts_code", "eq_month", "report_date_in_range",
                        "eq_ts_code_ranged"],
    }
    return {"files": files, "registry_sha256": _sha(_canon(registry))}


def compute_bundle_hash() -> str:
    return _sha(_canon(compute_bundle_manifest()))


# ── plan builder (design v4 §2c) ─────────────────────────────────────────────────────────────────
def build_plan_rows(spec: FamilySpec, contracts: dict) -> list:
    """One plan row per (endpoint, resolved request): population from the SIGNED contract's executable
    resolver; execution facts from the contract's pagination_spec; identity keys from the contract +
    matrix; the frozen recipe + the request-bound response scope. The coordinator's
    freeze_request_plan re-validates ALL of it against the live contracts + matrix."""
    mrow = next(r for r in rrc.ENDPOINT_MATRIX if r.output_family == spec.output_family)
    rows = []
    for ep in spec.endpoints:
        c = contracts.get(ep)
        if not c:
            raise RuntimeError(f"{ep}: no signed contract — a plan row cannot be built (fail closed)")
        rid_recipe = ENDPOINT_RECIPE.get(ep)
        if not rid_recipe:
            raise RuntimeError(f"{ep}: no frozen CallRecipe — bind one before planning (fail closed)")
        recipe = RECIPES[rid_recipe]
        validate_recipe(recipe)
        ps = c["pagination_spec"]
        # recipe/pagination coherence: a single_page contract must bind a none-paginated recipe
        if (ps["mode"] == "single_page") != (recipe.pagination_binding == "none"):
            raise RuntimeError(f"{ep}: recipe {rid_recipe} pagination_binding "
                               f"{recipe.pagination_binding!r} contradicts the signed mode {ps['mode']!r}")
        # every frozen request parameter must be mapped exactly once (design v4 §2a totality)
        mapped = {k for k, _ in recipe.request_parameter_map}
        for request in sorted(rrc.resolve_population(c["request_population"]),
                              key=lambda r: _canon(dict(r))):
            req = dict(request)
            if set(req) != mapped:
                raise RuntimeError(f"{ep}: request keys {sorted(req)} != recipe-mapped keys "
                                   f"{sorted(mapped)} — every frozen parameter maps exactly once")
            partition = spec.partition_of(req)
            rows.append({
                "request_id": rl.request_id(ep, req, partition),
                "endpoint": ep, "dataset": spec.output_family, "params": req,
                "partition": partition, "empty_policy": c["empty_policy"],
                "receipt_output": spec.request_output_of(ep, req),
                "natural_key": list(c["natural_key"]),
                "content_dedup_key": list(mrow.content_dedup_key),
                "max_content_dups": mrow.max_content_dups,
                "page_limit": int(ps["page_limit"]), "pagination_mode": ps["mode"],
                "contract_sha256": rrc.canonical_contract_sha256(c),
                "doc_sha256": c["doc_sha256"],
                "recipe_id": rid_recipe,
                "response_scope": response_scope_of(ep, req),
            })
    return rows


def freeze_run_plan(ledger, specs: list, contracts: dict) -> str:
    """ONCE per run (design v4 F6): every family's rows in ONE frozen plan, through the coordinator's
    sanctioned freeze door (full contract + matrix + population + merge-coverage validation)."""
    rows, declared = [], set()
    for spec in specs:
        rows.extend(build_plan_rows(spec, contracts))
        declared.add(spec.output_family)
    return rrc.freeze_request_plan(ledger, rows, contracts, declared_families=declared)


# ── executors (design v4 §2b) ────────────────────────────────────────────────────────────────────
def _params_key(base_params: dict) -> str:
    return _canon(dict(base_params))


class SyntheticExecutor:
    """Canned pages for the pre-fetch battery. mode declares it: the run is synthetic and NON-promotable
    (the ledger's run-mode firewall, not this class, is the authority). Cannot reach the vendor: no
    fetcher exists on this path."""
    mode = "synthetic_nonpromotable"

    def __init__(self, fixtures: dict):
        # (endpoint, canonical-params-json, offset) -> DataFrame ; a missing key returns EMPTY
        self._fx = dict(fixtures)
        self.calls = []                          # observability for the battery

    def run_page(self, spec: dict):
        import pandas as pd
        self.calls.append(dict(spec))
        df = self._fx.get((spec["endpoint"], _params_key(spec["base_params"]), int(spec["offset"])))
        return df.copy() if df is not None else pd.DataFrame()


class LiveExecutor:
    """The ONLY path to a real vendor call. Builds kwargs purely from the frozen recipe + the
    ledger-claimed cursor and makes EXACTLY ONE wire call via fetcher.fetch_page_once (the §6.1
    throttle lives in the fetcher's locked proxy).

    GPT impl re-review #2: run_page is NOT directly usable — it demands a ONE-SHOT dispatch token the
    LEDGER minted inside fetch_claimed_page's dispatch critical section. A direct call (no token, a
    guessed token, or a replayed token) refuses before touching the fetcher. Like _LockedPro this is
    DISCIPLINE against casual/accidental misuse, not an in-process security boundary — the scoped
    threat model excludes adversarial in-process races; deliberate bypasses are the lint's job."""
    mode = "live_authorized"

    def __init__(self, fetcher, ledger):
        self._fetcher = fetcher
        self._ledger = ledger

    def run_page(self, spec: dict):
        # the ledger checks BOTH the one-shot token AND that this exact request was the one dispatched
        # (endpoint/recipe/params/cursor) — a wrapping executor cannot keep a valid token and swap the
        # request to escape the §13 endpoint scope (GPT impl re-review #3 P0). A spec mismatch RAISES
        # LedgerError inside consume; a missing/replayed token returns False.
        if not self._ledger.consume_dispatch_token(spec.get("dispatch_token", ""), spec):
            raise RuntimeError("LiveExecutor.run_page REFUSED: no valid one-shot dispatch token — the "
                               "raw vendor door only opens for a ledger-dispatched call "
                               "(fetch_claimed_page); direct invocation is not a thing")
        recipe = RECIPES.get(spec["recipe_id"])
        if recipe is None:
            raise RuntimeError(f"unknown recipe {spec['recipe_id']!r} — the frozen plan names a recipe "
                               f"this bundle does not carry (bundle drift)")
        kwargs = {vendor_kw: spec["base_params"][req_kw]
                  for req_kw, vendor_kw in recipe.request_parameter_map}
        kwargs.update(dict(recipe.constant_kwargs))
        if recipe.pagination_binding != "none":
            limit_kw, offset_kw = recipe.pagination_binding
            kwargs[limit_kw] = int(spec["limit"])
            kwargs[offset_kw] = int(spec["offset"])
        return self._fetcher.fetch_page_once(recipe.vendor_method, **kwargs)


# ── orchestration (design v4 §4) ─────────────────────────────────────────────────────────────────
_RUNAWAY_CAP = 200_000            # hard backstop on claim iterations per family, far above any real run


def run_family(spec: FamilySpec, ledger, executor) -> dict:
    """Execute the family's already-frozen subset via the atomic claim loop. Consolidation is a
    SEPARATE step (consolidate_family). Live mode recomputes the bundle hash first — a dirty
    fetch-affecting file refuses before any wire call (design v4 Q1)."""
    if getattr(executor, "mode", None) == "live_authorized":
        live_hash = compute_bundle_hash()
        if live_hash != ledger.adapter_bundle_hash:
            raise RuntimeError(f"adapter bundle drifted since freeze ({live_hash[:12]} != "
                               f"{ledger.adapter_bundle_hash[:12]}) — refusing live execution")
    plan = ledger._plan()
    rids = sorted(r for r, row in plan.items() if row["dataset"] == spec.output_family)
    summary = {"verified": [], "confirmed_empty": [], "deferred": [], "failed": [], "in_flight": []}
    deferred = []

    def _drive(rid) -> str:
        for _ in range(_RUNAWAY_CAP):
            claim = ledger.claim_next_fetch(rid, getattr(executor, "mode", None))
            k = claim.kind
            if k in ("FETCH", "RETRY_PAGE", "RETRY_EMPTY_CONFIRM"):
                ledger.fetch_claimed_page(rid, claim, executor)
                continue
            if k == "VERIFY":
                ledger.verify_request(rid)
                return "verified"
            if k == "CONFIRM_EMPTY":
                ledger.confirm_empty(rid, canary_request_id=claim.canary_request_id)
                return "confirmed_empty"
            if k == "WAIT_FOR_CANARY":
                return "deferred"
            if k == "SKIP_TERMINAL":
                return "verified"                # already terminal from a prior run (resume)
            if k == "IN_FLIGHT":
                return "in_flight"
            raise RuntimeError(f"unknown claim kind {k!r}")
        raise RuntimeError(f"{rid}: runaway claim loop (> {_RUNAWAY_CAP}) — refusing")

    for rid in rids:
        try:
            outcome = _drive(rid)
        except Exception as exc:
            summary["failed"].append((rid, f"{type(exc).__name__}: {exc}"))
            continue
        summary[outcome if outcome != "deferred" else "deferred"].append(rid)
        if outcome == "deferred":
            deferred.append(rid)
    # second pass: a canary may have verified since
    still = []
    for rid in deferred:
        try:
            outcome = _drive(rid)
        except Exception as exc:
            summary["failed"].append((rid, f"{type(exc).__name__}: {exc}"))
            continue
        if outcome == "deferred":
            still.append(rid)
        else:
            summary[outcome].append(rid)
            summary["deferred"].remove(rid)
    summary["deferred"] = still
    return summary


def _digest_multiset(df):
    """Canonical row-hash multiset (design v4 §2e): REUSES the ledger's lossless row encoder over the
    identical (vendor) column set on both sides of the conservation check."""
    from collections import Counter
    if df is None or not len(df):
        return Counter()
    return Counter(rl.PageReceiptLedger.add_row_payload_digest(df)["row_payload_digest"].tolist())


def consolidate_family(spec: FamilySpec, ledger) -> dict:
    """The SEPARATE consolidation step (design v4 F7): inputs are the immutable VERIFIED per-request
    outputs (byte-rebound via consolidation_allowed); the physical layout + conservation come from the
    frozen ConsolidationSpec; every output is written through the broker and bound into a hash-chained
    consolidation verdict."""
    import pandas as pd
    # GPT impl-review B3 + re-review #2: consolidation is as fetch-affecting as fetching, and its
    # singleton check must be ATOMIC with the work + the final event. The WHOLE body runs under the
    # cross-process run-execution lock (mutual exclusion with fetch workers AND other consolidators):
    # two processes serialize at the lock, and the second one re-reads the ledger INSIDE it and sees
    # the first's family_consolidated event -> "exactly once" cannot race. A crash mid-consolidation
    # leaves NO event -> a re-run redoes the deterministic outputs (idempotent), never a half-claim.
    with ledger.execution_guard():
        return _consolidate_family_locked(spec, ledger, pd)


def _consolidate_family_locked(spec: FamilySpec, ledger, pd) -> dict:
    # (a) recompute the content-hashed bundle — a drifted merge/repartition recipe must refuse HERE,
    # not only at run_family; (b) SINGLETON per family — checked inside the execution lock.
    live_hash = compute_bundle_hash()
    if live_hash != ledger.adapter_bundle_hash:
        raise RuntimeError(f"{spec.output_family}: adapter bundle drifted since freeze "
                           f"({live_hash[:12]} != {ledger.adapter_bundle_hash[:12]}) — refusing "
                           f"consolidation")
    if any(r.get("kind") == "lifecycle" and r.get("event") == "family_consolidated"
           and r.get("family") == spec.output_family for r in ledger._load()):
        raise RuntimeError(f"{spec.output_family}: already consolidated — a family consolidates "
                           f"exactly once per run (repeat writes refused)")
    ok, pending = ledger.consolidation_allowed(spec.output_family)
    if not ok:
        raise RuntimeError(f"{spec.output_family}: consolidation refused — {len(pending)} requests not "
                           f"terminal (e.g. {pending[:3]})")
    plan = ledger._plan()
    rows_led = ledger._load()
    fam = {r: row for r, row in plan.items() if row["dataset"] == spec.output_family}
    inputs, input_bind = {}, []
    for rid, row in sorted(fam.items()):
        st = ledger._state_of(rows_led, rid)
        if st == "confirmed_empty":
            input_bind.append({"request_id": rid, "state": st, "rows": 0})
            continue                              # contributes zero rows (both empty policies)
        ev = ledger.verdict_of(rows_led, rid) or {}
        p = ledger.rp.staging_data / ev["output_path"]
        df = pd.read_parquet(p)
        inputs.setdefault(row["endpoint"], []).append((rid, row, df))
        input_bind.append({"request_id": rid, "state": st, "rows": int(len(df)),
                           "output_bytes_sha256": ev.get("output_bytes_sha256")})
    results = []
    for cons in spec.consolidations:
        results.append(_consolidate_one_layout(spec, ledger, pd, cons, inputs))
    ledger.event("family_consolidated", family=spec.output_family, inputs=input_bind,
                 layouts=[{"label": r["label"], "conservation_mode": r["conservation_mode"],
                           "outputs": r["outputs"]} for r in results])
    return {"inputs": input_bind, "layouts": results,
            "outputs": [o for r in results for o in r["outputs"]]}


def _consolidate_one_layout(spec: FamilySpec, ledger, pd, cons: ConsolidationSpec, inputs: dict) -> dict:
    """Produce ONE physical layout from the family's verified request outputs."""
    outputs = []
    if cons.conservation_mode == "base_key_preserving_merge":
        # A01: per-partition 3-leg merge via the canonical merger
        by_part: dict = {}
        for ep, lst in inputs.items():
            for rid, row, df in lst:
                by_part.setdefault(row["partition"], {})[ep] = df
        for part in sorted(by_part):
            legs = by_part[part]
            missing = set(spec.endpoints) - set(legs)
            if missing:
                raise RuntimeError(f"{spec.output_family} {part}: leg(s) {sorted(missing)} have no "
                                   f"verified input — a merged partition needs every leg")
            merged = merge_daily_legs(legs["daily"], legs["daily_basic"], legs["adj_factor"], part)
            outputs.append((part, merged))
    elif cons.conservation_mode == "multiset_identity":
        all_frames = [df for lst in inputs.values() for _, _, df in lst]
        whole = pd.concat(all_frames, ignore_index=True) if all_frames else pd.DataFrame()
        in_rows = int(len(whole))
        in_ms = _digest_multiset(whole)
        if len(whole):
            col = cons.output_partition_col
            if col not in whole.columns:
                raise RuntimeError(f"{spec.output_family}: rows lack the output partition column "
                                   f"{col!r} — cannot repartition")
            keys = whole[col].astype(str).map(cons.partition_of_value)
            for part, grp in whole.groupby(keys, sort=True):
                outputs.append((str(part), grp.reset_index(drop=True)))
        out_rows = sum(len(df) for _, df in outputs)
        from collections import Counter as _C
        out_ms = _C()
        for _, df in outputs:
            out_ms.update(_digest_multiset(df))
        if in_rows != out_rows or in_ms != out_ms:
            raise RuntimeError(f"{spec.output_family}: MULTISET conservation violated "
                               f"({in_rows} in vs {out_rows} out; content multisets "
                               f"{'equal' if in_ms == out_ms else 'DIFFER'}) — a drop+duplicate at "
                               f"equal count cannot pass this")
    else:
        raise RuntimeError(f"{spec.output_family}: unknown conservation_mode "
                           f"{cons.conservation_mode!r} — fail closed")
    written = []
    for part, df in outputs:
        rel = cons.family_output_of(part)
        out = ledger.rp.assert_write(ledger.rp.staging_data / rel)
        ledger.rp.broker().mkdirs(out.parent)
        import io as _io
        import os as _os
        buf = _io.BytesIO()
        df.reset_index(drop=True).to_parquet(buf, index=False)
        payload = buf.getvalue()
        want = hashlib.sha256(payload).hexdigest()
        with ledger.rp.broker().open_for_write(out, "wb") as fh:
            fh.write(payload)
            fh.flush()
            _os.fsync(fh.fileno())                # durable BEFORE binding it into the verdict
        # GPT impl-review B3: bind the RE-READ bytes, never the buffer we hoped we wrote
        got = hashlib.sha256(out.read_bytes()).hexdigest()
        if got != want:
            raise RuntimeError(f"{spec.output_family} {part}: consolidated output on disk "
                               f"({got[:12]}) != what was written ({want[:12]}) — refusing to record")
        written.append({"partition": part, "path": rel, "rows": int(len(df)),
                        "bytes_sha256": want})
    return {"label": cons.label or spec.output_family,
            "conservation_mode": cons.conservation_mode, "outputs": written}
