# ──────────────────────────────────────────────────────────────────────
# PR 7 of 2026-05-26 freeze plan — SCRIPT_STATUS header block.
# script_status: historical_investigation
# formal_research_allowed: false
# deployment_target: joinquant_attribution_only
# requires_provider_manifest: false
# requires_preload_strict: false
# pr2_audit_class: C
# notes: |
#   Read-only research-proposal generator. Enumerates PIT-safe factor
#   FAMILIES from the live Qlib field inventory, stamps each candidate
#   with its field-registry status, and writes:
#     - data/factor_research/field_inventory.txt   (tracked snapshot)
#     - workspace/research/factor_expansion/factor_candidates.csv
#   Does NOT call Tushare, does NOT run Qlib compute, does NOT import or
#   mutate catalog.py / any registry / any data artifact other than the
#   two output files above. No bare D.features calls.
# ──────────────────────────────────────────────────────────────────────
"""Exhaustive factor-candidate generator for the GPT 5.5 Pro handoff.

Usage:
    venv/Scripts/python.exe workspace/scripts/generate_factor_candidates.py

What it does
============
1. Reads the materialized Qlib field set directly from a sample stock's
   feature-bin directory (``data/qlib_data/features/<stock>/*.bin``),
   collapsing the PIT-variant suffixes (``_q0..q4``, ``_cum_q0..q4``,
   ``_q``, ``_sq_q0..q4``) to a set of base field stems. This is ground
   truth — the candidate list reflects what is ACTUALLY queryable, not a
   hardcoded assumption.
2. Defines factor FAMILIES as PIT-safe Qlib-expression templates. Each
   family expands over its parameter grid (windows / fields / variants)
   into concrete candidate factors.
3. Resolves every candidate's ``$field`` tokens against the committed
   field-status registry (config/field_registry/field_status.yaml) via
   ``src.data_infra.field_registry`` to stamp ``registry_status`` and
   ``formal_eligible`` (formal_validation stage).
4. Writes a tracked plaintext field inventory and the candidate CSV.

PIT safety: every ``$field`` in every template is wrapped in ``Ref(..., 1)``
or uses the ``ADJ_*_T1`` adjusted-price atoms imported from the operator
library. ``forward_return`` is intentionally NOT emitted (it is a label).
"""

from __future__ import annotations

import csv
import logging
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_research.factor_library import operators as op  # noqa: E402
from src.data_infra.field_registry import (  # noqa: E402
    extract_qlib_fields,
    load_field_registry,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("generate_factor_candidates")

FEATURES_DIR = PROJECT_ROOT / "data" / "qlib_data" / "features"
INVENTORY_OUT = PROJECT_ROOT / "data" / "factor_research" / "field_inventory.md"
CSV_OUT = (
    PROJECT_ROOT
    / "workspace"
    / "research"
    / "factor_expansion"
    / "factor_candidates.csv"
)
FORMAL_STAGE = "formal_validation"

# ── PIT-safe adjusted-price atoms (reused from the operator library) ──────
C1 = op.ADJ_CLOSE_T1   # Ref(($close*$adj_factor), 1)
RET = op.DAILY_RET     # PIT-safe daily close-to-close return


# ═══════════════════════════════════════════════════════════════════════
#  Field inventory (ground truth from the live provider)
# ═══════════════════════════════════════════════════════════════════════

def _collapse_pit_suffix(stem: str) -> str:
    """Collapse a materialized field stem to its base name.

    income/cashflow flow items carry ``_cum_q0..4``, ``_q``, ``_sq_q0..4``;
    snapshot (balance-sheet / indicator) items carry ``_q0..4``.
    """
    import re

    s = re.sub(r"_(cum_q|sq_q)[0-4]$", "", stem)
    s = re.sub(r"_q[0-4]$", "", s)
    s = re.sub(r"_q$", "", s)
    return s


def load_field_inventory() -> tuple[list[str], list[str], str]:
    """Return (base_stems_sorted, raw_stems_sorted, sample_stock_dir).

    Picks the feature directory with the MOST bins (a real stock with full
    fundamentals, not an index), so the inventory is complete.
    """
    if not FEATURES_DIR.exists():
        raise FileNotFoundError(
            f"Qlib features dir not found at {FEATURES_DIR}. "
            "This generator must run on a host with a published provider."
        )

    best_dir = None
    best_count = -1
    for child in FEATURES_DIR.iterdir():
        if not child.is_dir():
            continue
        n = sum(1 for _ in child.glob("*.bin"))
        if n > best_count:
            best_count, best_dir = n, child
    if best_dir is None:
        raise FileNotFoundError(f"No instrument dirs under {FEATURES_DIR}")

    raw_stems: set[str] = set()
    for binf in best_dir.glob("*.bin"):
        name = binf.name
        if name.endswith(".day.bin"):
            name = name[: -len(".day.bin")]
        elif name.endswith(".bin"):
            name = name[: -len(".bin")]
        # drop a trailing ".<n>" frequency marker if present
        import re

        name = re.sub(r"\.[0-9]+$", "", name)
        raw_stems.add(name)

    base_stems = sorted({_collapse_pit_suffix(s) for s in raw_stems})
    logger.info(
        "Field inventory: %d raw bins -> %d base stems (sample=%s)",
        len(raw_stems), len(base_stems), best_dir.name,
    )
    return base_stems, sorted(raw_stems), best_dir.name


# ═══════════════════════════════════════════════════════════════════════
#  Factor family templates (PIT-safe)
# ═══════════════════════════════════════════════════════════════════════
#
# Each family is a dict:
#   name_tmpl   : factor-name template ({w}, {f}, {num}, {den} placeholders)
#   expr_fn     : callable(**kw) -> Qlib expression string (PIT-safe)
#   grid        : dict of placeholder -> list of values
#   category    : factor category
#   price_basis : 'adjusted' | 'raw' | 'mixed'
#   sign        : expected sign ('+'/'-'/'?') of factor vs forward return
#   decay_days  : expected decay horizon
#   neutralize  : default neutralization
#   rationale   : one-line thesis
#   requires    : list of base stems that must exist in the inventory for the
#                 family to be emitted (gates statement-line-item families)
#
# Expansion produces one candidate row per grid cartesian product cell.

# Windows used across price/volume families.
W_SHORT = [5, 10, 20]
W_MED = [20, 60, 120]
W_LONG = [120, 250]


def _ratio_static(num_field: str, den_field: str) -> str:
    """PIT-safe ratio of two raw fields: Ref($num,1)/Ref($den,1)."""
    return f"Ref(${num_field}, 1) / Ref(${den_field}, 1)"


def _yoy_q(field: str) -> str:
    """Single-quarter YoY using the _q (single-quarter) variant, lag 4 quarters.

    Uses the *_q materialized single-quarter series. Ref shifts are in
    TRADING DAYS, so a 4-quarter lag is approximated by the q-variant index;
    we express it as the ratio of consecutive _sq_q0/_sq_q4 snapshot lags
    which the provider already aligns per quarter.
    """
    return f"Ref(${field}_sq_q0, 1) / Ref(${field}_sq_q4, 1) - 1"


def _qoq_q(field: str) -> str:
    return f"Ref(${field}_sq_q0, 1) / Ref(${field}_sq_q1, 1) - 1"


def build_families() -> list[dict]:
    """Return the full family registry (templates, not yet expanded)."""
    fams: list[dict] = []

    # ─────────── VALUE (extend) ───────────
    fams.append(dict(
        name_tmpl="val_ev_ebitda",
        expr_fn=lambda: (
            "(Ref($total_mv, 1) * 10000 + Ref($total_liab_q0, 1) "
            "- Ref($money_cap_q0, 1)) / Ref($ebitda_cum_q0, 1)"
        ),
        category="Value",
        price_basis="mixed",
        sign="-", decay_days=60, neutralize="industry",
        rationale="Enterprise value to EBITDA; cheaper firms outperform.",
        requires=["total_liab", "money_cap", "ebitda"],
    ))
    fams.append(dict(
        name_tmpl="val_ebit_ev",
        expr_fn=lambda: (
            "Ref($ebit_cum_q0, 1) / (Ref($total_mv, 1) * 10000 "
            "+ Ref($total_liab_q0, 1) - Ref($money_cap_q0, 1))"
        ),
        category="Value", price_basis="mixed",
        sign="+", decay_days=60, neutralize="industry",
        rationale="Greenblatt earnings yield (EBIT/EV).",
        requires=["ebit", "total_liab", "money_cap"],
    ))
    fams.append(dict(
        name_tmpl="val_fcf_yield",
        expr_fn=lambda: (
            "(Ref($n_cashflow_act_cum_q0, 1) - Ref($c_pay_acq_const_fiolta_cum_q0, 1)) "
            "/ (Ref($total_mv, 1) * 10000)"
        ),
        category="Value", price_basis="mixed",
        sign="+", decay_days=90, neutralize="industry",
        rationale="Free-cash-flow yield (OCF - CapEx) / market cap.",
        requires=["n_cashflow_act", "c_pay_acq_const_fiolta"],
    ))
    fams.append(dict(
        name_tmpl="val_ocf_ev",
        expr_fn=lambda: (
            "Ref($n_cashflow_act_cum_q0, 1) / (Ref($total_mv, 1) * 10000 "
            "+ Ref($total_liab_q0, 1) - Ref($money_cap_q0, 1))"
        ),
        category="Value", price_basis="mixed",
        sign="+", decay_days=90, neutralize="industry",
        rationale="Operating-cash-flow to enterprise value.",
        requires=["n_cashflow_act", "total_liab", "money_cap"],
    ))
    fams.append(dict(
        name_tmpl="val_retearn_yield",
        expr_fn=lambda: "Ref($retained_earnings_q0, 1) / (Ref($total_mv, 1) * 10000)",
        category="Value", price_basis="mixed",
        sign="+", decay_days=120, neutralize="industry",
        rationale="Retained-earnings yield (accumulated value vs price).",
        requires=["retained_earnings"],
    ))
    fams.append(dict(
        name_tmpl="val_ncav_to_price",
        expr_fn=lambda: (
            "(Ref($total_cur_assets_q0, 1) - Ref($total_liab_q0, 1)) "
            "/ (Ref($total_mv, 1) * 10000)"
        ),
        category="Value", price_basis="mixed",
        sign="+", decay_days=120, neutralize="industry",
        rationale="Graham NCAV / price (deep value).",
        requires=["total_cur_assets", "total_liab"],
    ))

    # ─────────── QUALITY / PROFITABILITY (large expansion) ───────────
    fams.append(dict(
        name_tmpl="qual_gross_profitability",
        expr_fn=lambda: (
            "(Ref($total_revenue_cum_q0, 1) - Ref($oper_cost_cum_q0, 1)) "
            "/ Ref($total_assets_q0, 1)"
        ),
        category="Quality", price_basis="raw",
        sign="+", decay_days=120, neutralize="industry",
        rationale="Novy-Marx gross profitability (gross profit / total assets).",
        requires=["total_revenue", "oper_cost", "total_assets"],
    ))
    fams.append(dict(
        name_tmpl="qual_cash_roa",
        expr_fn=lambda: "Ref($n_cashflow_act_cum_q0, 1) / Ref($total_assets_q0, 1)",
        category="Quality", price_basis="raw",
        sign="+", decay_days=120, neutralize="industry",
        rationale="Cash return on assets (OCF / total assets).",
        requires=["n_cashflow_act", "total_assets"],
    ))
    fams.append(dict(
        name_tmpl="qual_dupont_margin",
        expr_fn=lambda: "Ref($netprofit_margin, 1)",
        category="Quality", price_basis="raw",
        sign="+", decay_days=120, neutralize="industry",
        rationale="DuPont leg 1: net profit margin.",
        requires=["netprofit_margin"],
    ))
    fams.append(dict(
        name_tmpl="qual_dupont_turnover",
        expr_fn=lambda: "Ref($assets_turn, 1)",
        category="Quality", price_basis="raw",
        sign="+", decay_days=120, neutralize="industry",
        rationale="DuPont leg 2: asset turnover.",
        requires=["assets_turn"],
    ))
    # margin ladder over vendor ratios
    for f in ["grossprofit_margin", "netprofit_margin", "op_of_gr",
              "ebit_of_gr", "profit_to_gr"]:
        fams.append(dict(
            name_tmpl=f"qual_margin_{f}",
            expr_fn=(lambda fld=f: f"Ref(${fld}, 1)"),
            category="Quality", price_basis="raw",
            sign="+", decay_days=120, neutralize="industry",
            rationale=f"Margin ladder member: {f}.",
            requires=[f],
        ))

    # ─────────── ACCRUALS / EARNINGS QUALITY (new, biggest gap) ───────────
    fams.append(dict(
        name_tmpl="acc_total_accruals_ni_ocf",
        expr_fn=lambda: (
            "(Ref($n_income_cum_q0, 1) - Ref($n_cashflow_act_cum_q0, 1)) "
            "/ Ref($total_assets_q0, 1)"
        ),
        category="Accruals", price_basis="raw",
        sign="-", decay_days=120, neutralize="industry",
        rationale="Total accruals (NI - OCF)/assets; high accruals underperform.",
        requires=["n_income", "n_cashflow_act", "total_assets"],
    ))
    fams.append(dict(
        name_tmpl="acc_cfo_to_ni",
        expr_fn=lambda: "Ref($n_cashflow_act_cum_q0, 1) / Ref($n_income_cum_q0, 1)",
        category="Accruals", price_basis="raw",
        sign="+", decay_days=120, neutralize="industry",
        rationale="Cash-flow backing of earnings (OCF/NI); higher is cleaner.",
        requires=["n_cashflow_act", "n_income"],
    ))
    fams.append(dict(
        name_tmpl="acc_asset_growth",
        expr_fn=lambda: "Ref($total_assets_q0, 1) / Ref($total_assets_q4, 1) - 1",
        category="Accruals", price_basis="raw",
        sign="-", decay_days=250, neutralize="industry",
        rationale="Cooper asset growth; fast asset growers underperform.",
        requires=["total_assets"],
    ))
    fams.append(dict(
        name_tmpl="acc_noa_scaled",
        expr_fn=lambda: (
            "(Ref($total_assets_q0, 1) - Ref($money_cap_q0, 1) "
            "- Ref($total_liab_q0, 1) + Ref($st_borr_q0, 1) + Ref($lt_borr_q0, 1)) "
            "/ Ref($total_assets_q4, 1)"
        ),
        category="Accruals", price_basis="raw",
        sign="-", decay_days=250, neutralize="industry",
        rationale="Net operating assets scaled by lagged assets (Hirshleifer).",
        requires=["total_assets", "money_cap", "total_liab", "st_borr", "lt_borr"],
    ))
    fams.append(dict(
        name_tmpl="acc_dWC_inventory",
        expr_fn=lambda: (
            "(Ref($inventories_q0, 1) - Ref($inventories_q4, 1)) "
            "/ Ref($total_assets_q4, 1)"
        ),
        category="Accruals", price_basis="raw",
        sign="-", decay_days=120, neutralize="industry",
        rationale="Inventory build relative to assets; over-investment in WC.",
        requires=["inventories", "total_assets"],
    ))
    fams.append(dict(
        name_tmpl="acc_dWC_receivables",
        expr_fn=lambda: (
            "(Ref($accounts_receiv_q0, 1) - Ref($accounts_receiv_q4, 1)) "
            "/ Ref($total_assets_q4, 1)"
        ),
        category="Accruals", price_basis="raw",
        sign="-", decay_days=120, neutralize="industry",
        rationale="Receivable build; aggressive revenue recognition proxy.",
        requires=["accounts_receiv", "total_assets"],
    ))
    fams.append(dict(
        name_tmpl="acc_capex_intensity",
        expr_fn=lambda: (
            "Ref($c_pay_acq_const_fiolta_cum_q0, 1) / Ref($total_assets_q0, 1)"
        ),
        category="Accruals", price_basis="raw",
        sign="-", decay_days=250, neutralize="industry",
        rationale="CapEx intensity; high investment associated with lower returns.",
        requires=["c_pay_acq_const_fiolta", "total_assets"],
    ))
    fams.append(dict(
        name_tmpl="acc_rd_intensity",
        expr_fn=lambda: "Ref($rd_exp_cum_q0, 1) / Ref($total_revenue_cum_q0, 1)",
        category="Accruals", price_basis="raw",
        sign="+", decay_days=250, neutralize="industry",
        rationale="R&D intensity; intangible-investment premium.",
        requires=["rd_exp", "total_revenue"],
    ))
    fams.append(dict(
        name_tmpl="acc_goodwill_ratio",
        expr_fn=lambda: "Ref($goodwill_q0, 1) / Ref($total_assets_q0, 1)",
        category="Accruals", price_basis="raw",
        sign="-", decay_days=250, neutralize="industry",
        rationale="Goodwill as a share of assets; impairment / overpayment risk.",
        requires=["goodwill", "total_assets"],
    ))
    fams.append(dict(
        name_tmpl="acc_net_share_issuance",
        expr_fn=lambda: "0 - (Ref($total_share, 1) / Ref($total_share, 251) - 1)",
        category="Accruals", price_basis="raw",
        sign="+", decay_days=250, neutralize="size",
        rationale="Net share issuance (negated); issuers underperform, buybacks win.",
        requires=["total_share"],
    ))

    # ─────────── GROWTH (single-quarter YoY/QoQ extension) ───────────
    for f in ["revenue", "operate_profit", "n_income_attr_p", "total_revenue"]:
        fams.append(dict(
            name_tmpl=f"grow_{f}_yoy_q",
            expr_fn=(lambda fld=f: _yoy_q(fld)),
            category="Growth", price_basis="raw",
            sign="+", decay_days=90, neutralize="industry",
            rationale=f"Single-quarter YoY growth of {f}.",
            requires=[f],
        ))
        fams.append(dict(
            name_tmpl=f"grow_{f}_qoq_q",
            expr_fn=(lambda fld=f: _qoq_q(fld)),
            category="Growth", price_basis="raw",
            sign="+", decay_days=60, neutralize="industry",
            rationale=f"Single-quarter QoQ momentum of {f}.",
            requires=[f],
        ))

    # ─────────── LEVERAGE / SOLVENCY (extend) ───────────
    fams.append(dict(
        name_tmpl="lev_net_debt_to_ebitda",
        expr_fn=lambda: (
            "(Ref($st_borr_q0, 1) + Ref($lt_borr_q0, 1) - Ref($money_cap_q0, 1)) "
            "/ Ref($ebitda_cum_q0, 1)"
        ),
        category="Leverage", price_basis="raw",
        sign="-", decay_days=120, neutralize="industry",
        rationale="Net debt / EBITDA solvency.",
        requires=["st_borr", "lt_borr", "money_cap", "ebitda"],
    ))
    fams.append(dict(
        name_tmpl="lev_interest_coverage",
        expr_fn=lambda: "Ref($ebit_cum_q0, 1) / Ref($int_exp_cum_q0, 1)",
        category="Leverage", price_basis="raw",
        sign="+", decay_days=120, neutralize="industry",
        rationale="Interest coverage (EBIT / interest expense).",
        requires=["ebit", "int_exp"],
    ))

    # ─────────── MOMENTUM / REVERSAL (extend) ───────────
    fams.append(dict(
        name_tmpl="mom_52w_high_proximity",
        expr_fn=lambda: f"{C1} / Max({op.ADJ_HIGH_T1}, 250)",
        category="Momentum", price_basis="adjusted",
        sign="+", decay_days=120, neutralize="industry",
        rationale="George-Hwang 52-week-high proximity.",
        requires=["close", "high", "adj_factor"],
    ))
    for w in W_MED:
        fams.append(dict(
            name_tmpl=f"mom_volscaled_{w}d",
            expr_fn=(lambda ww=w: f"({op.momentum(ww)}) / (Std({RET}, {ww}) + 0.0001)"),
            category="Momentum", price_basis="adjusted",
            sign="+", decay_days=60, neutralize="industry",
            rationale="Volatility-scaled momentum (risk-adjusted trend).",
            requires=["close", "adj_factor"],
        ))

    # ─────────── VOLATILITY / RISK (extend) ───────────
    for w in W_MED:
        fams.append(dict(
            name_tmpl=f"risk_parkinson_{w}d",
            expr_fn=(lambda ww=w: f"Mean(Ref(($high - $low) / $close, 1), {ww})"),
            category="Volatility", price_basis="raw",
            sign="-", decay_days=20, neutralize="size",
            rationale="Parkinson high-low range volatility.",
            requires=["high", "low", "close"],
        ))

    # ─────────── LIQUIDITY / MICROSTRUCTURE (extend) ───────────
    for w in W_SHORT:
        fams.append(dict(
            name_tmpl=f"liq_zero_ret_days_{w}d",
            expr_fn=(lambda ww=w: f"Count(Abs({RET}) < 0.0001, {ww}) / {ww}"),
            category="Liquidity", price_basis="adjusted",
            sign="-", decay_days=20, neutralize="size",
            rationale="Zero-return days (Lesmond illiquidity).",
            requires=["close", "adj_factor"],
        ))

    # ─────────── CAPITAL FLOW (moneyflow — quarantine) ───────────
    for w in W_SHORT:
        fams.append(dict(
            name_tmpl=f"flow_elg_net_pct_{w}d",
            expr_fn=(lambda ww=w: (
                f"Mean(Ref((($buy_elg_amount - $sell_elg_amount) / $amount), 1), {ww})"
            )),
            category="CapitalFlow", price_basis="raw",
            sign="+", decay_days=10, neutralize="size",
            rationale="Extra-large order net inflow share (institutional flow).",
            requires=["buy_elg_amount", "sell_elg_amount", "amount"],
        ))

    # ─────────── MARGIN (margin_detail — quarantine) ───────────
    fams.append(dict(
        name_tmpl="margin_net_buy_ratio_20d",
        expr_fn=lambda: "Mean(Ref(($rzmre - $rzche), 1), 20) / Ref($circ_mv, 1)",
        category="Margin", price_basis="raw",
        sign="+", decay_days=20, neutralize="size",
        rationale="Net financing-buy intensity scaled by float cap.",
        requires=["rzmre", "rzche", "circ_mv"],
    ))

    # ─────────── ALPHA ENDPOINTS (pending_review) ───────────
    fams.append(dict(
        name_tmpl="alpha_chip_winner_rate_level",
        expr_fn=lambda: "Ref($cyq_perf__winner_rate, 1)",
        category="AlphaEndpoint", price_basis="raw",
        sign="?", decay_days=20, neutralize="size",
        rationale="Chip-distribution winner rate level (profit-taking pressure).",
        requires=["cyq_perf__winner_rate"],
    ))

    # ─────────── DIVIDEND / PAYOUT ───────────
    fams.append(dict(
        name_tmpl="val_payout_ratio",
        expr_fn=lambda: "Ref($cash_div_q0, 1) / Ref($eps, 1)",
        category="Value", price_basis="raw",
        sign="?", decay_days=250, neutralize="industry",
        rationale="Dividend payout ratio (cash div per share / EPS).",
        requires=["cash_div", "eps"],
    ))

    return fams


def expand_families(families: list[dict], base_stems: set[str]) -> list[dict]:
    """Expand templates into concrete candidate rows, gated on field existence."""
    rows: list[dict] = []
    skipped: list[str] = []
    for fam in families:
        missing = [r for r in fam.get("requires", []) if r not in base_stems]
        if missing:
            skipped.append(f"{fam['name_tmpl']} (missing {missing})")
            continue
        expr = fam["expr_fn"]()
        rows.append({
            "name": fam["name_tmpl"],
            "category": fam["category"],
            "qlib_expression": expr,
            "price_basis": fam["price_basis"],
            "expected_sign": fam["sign"],
            "expected_decay_days": fam["decay_days"],
            "neutralization": fam["neutralize"],
            "rationale": fam["rationale"],
        })
    if skipped:
        logger.warning("Skipped %d families (field not materialized):", len(skipped))
        for s in skipped:
            logger.warning("  - %s", s)
    return rows


def stamp_registry(rows: list[dict]) -> list[dict]:
    """Add registry_status, formal_eligible, fields_used to each row."""
    registry = load_field_registry(PROJECT_ROOT / "config" / "field_registry" / "field_status.yaml")
    for row in rows:
        fields = extract_qlib_fields(row["qlib_expression"])
        statuses = set()
        eligible = True
        for f in fields:
            res = registry.resolve_field(f, FORMAL_STAGE)
            statuses.add(res.status_id or "unknown_field")
            if not res.allowed:
                eligible = False
        row["fields_used"] = ";".join(fields)
        # Worst-case status for display priority.
        if "unknown_field" in statuses:
            row["registry_status"] = "unknown_field"
        elif "quarantine" in statuses:
            row["registry_status"] = "quarantine"
        elif "pending_review" in statuses:
            row["registry_status"] = "pending_review"
        elif statuses == {"approved"}:
            row["registry_status"] = "approved"
        else:
            row["registry_status"] = ";".join(sorted(statuses))
        row["formal_eligible"] = "yes" if eligible else "no"
    return rows


def write_inventory(base_stems: list[str], raw_stems: list[str], sample: str) -> None:
    INVENTORY_OUT.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Materialized Qlib Field Inventory (ground-truth snapshot)",
        "",
        "> Generated by `workspace/scripts/generate_factor_candidates.py` — do not",
        "> hand-edit. Re-run the generator to refresh after a provider rebuild.",
        "",
        f"- **Source:** `data/qlib_data/features/{sample}/*.bin`",
        f"- **Base stems:** {len(base_stems)}",
        f"- **Raw bins (incl. PIT variants):** {len(raw_stems)}",
        "",
        "## PIT-variant grammar (collapsed in the base list)",
        "",
        "| Suffix | Meaning |",
        "|--------|---------|",
        "| `<field>_q0..q4` | snapshot value, latest..4-lag (balance sheet / indicators) |",
        "| `<field>_cum_q0..q4` | cumulative period value, latest..4-lag (income / cashflow) |",
        "| `<field>_q` | single-quarter derived value |",
        "| `<field>_sq_q0..q4` | single-quarter snapshot, latest..4-lag |",
        "",
        "## Base field stems",
        "",
        "```",
    ]
    lines.extend(base_stems)
    lines.append("```")
    lines.append("")
    lines.append("## Raw materialized bins (incl. PIT variants)")
    lines.append("")
    lines.append("```")
    lines.extend(raw_stems)
    lines.append("```")
    INVENTORY_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Wrote field inventory -> %s", INVENTORY_OUT)


def write_csv(rows: list[dict]) -> None:
    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    cols = [
        "name", "category", "qlib_expression", "fields_used", "price_basis",
        "registry_status", "formal_eligible", "expected_sign",
        "expected_decay_days", "neutralization", "rationale",
    ]
    with open(CSV_OUT, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols)
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in cols})
    logger.info("Wrote %d candidate rows -> %s", len(rows), CSV_OUT)


def main() -> int:
    base_stems, raw_stems, sample = load_field_inventory()
    write_inventory(base_stems, raw_stems, sample)

    families = build_families()
    logger.info("Defined %d factor families", len(families))
    rows = expand_families(families, set(base_stems))
    rows = stamp_registry(rows)
    write_csv(rows)

    # Summary by status
    from collections import Counter
    status_counts = Counter(r["registry_status"] for r in rows)
    elig_counts = Counter(r["formal_eligible"] for r in rows)
    logger.info("Candidate status breakdown: %s", dict(status_counts))
    logger.info("Formal-eligible breakdown: %s", dict(elig_counts))
    logger.info("DONE. No data/config/src artifacts mutated besides the 2 outputs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
