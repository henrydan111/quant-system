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
    """Single-quarter YoY: ratio of the latest single-quarter snapshot to the
    same quarter one year earlier (4 quarter-lags), using the provider-aligned
    ``_sq_q0`` / ``_sq_q4`` series.
    """
    return f"Ref(${field}_sq_q0, 1) / Ref(${field}_sq_q4, 1) - 1"


def _qoq_q(field: str) -> str:
    return f"Ref(${field}_sq_q0, 1) / Ref(${field}_sq_q1, 1) - 1"


def _ttm(field: str) -> str:
    """Trailing-twelve-month sum of a flow field from the 4 latest single-quarter
    snapshots (``_sq_q0..q3``). Per data_tracker, ``_cum_q0`` is YTD-cumulative
    (Q1=3mo, Q3=9mo) and therefore quarter-seasonality-contaminated; the TTM sum
    is the seasonality-free flow quantity for ratios. (GPT 5.5 Pro review, §5.)
    """
    return (
        f"(Ref(${field}_sq_q0, 1) + Ref(${field}_sq_q1, 1) "
        f"+ Ref(${field}_sq_q2, 1) + Ref(${field}_sq_q3, 1))"
    )


def build_families() -> list[dict]:
    """Return the full family registry (templates, not yet expanded)."""
    fams: list[dict] = []

    # ─────────── VALUE (extend) ───────────
    # EV bridge reused across EV-yield families. Stock terms use _q0 snapshot;
    # flow terms use TTM (_sq sum) per the GPT review seasonality fix.
    EV = "(Ref($total_mv, 1) * 10000 + Ref($total_liab_q0, 1) - Ref($money_cap_q0, 1))"
    # GPT Round-5 §3: DROPPED — $ebitda has 3.3% non-null coverage in the live
    # indicators provider (verified: 6,717/202,380 in 2018). The TTM _sq_q0..q3
    # collapses to 100% NaN. Use val_ebit_ev_ttm instead (ebit_sq_* has 98%
    # coverage). Block until ebitda is re-materialized or rebuilt from
    # statement line-items.
    # fams.append(dict(name_tmpl="val_ebitda_ev_ttm", ...))
    fams.append(dict(
        name_tmpl="val_ebit_ev_ttm",
        expr_fn=lambda: f"{_ttm('ebit')} / {EV}",
        category="Value", price_basis="mixed",
        sign="+", decay_days=120, neutralize="industry",
        rationale="Greenblatt earnings yield (EBIT/EV), TTM single-quarter flow.",
        requires=["ebit", "total_liab", "money_cap"],
    ))
    fams.append(dict(
        name_tmpl="val_fcf_ev_ttm",
        expr_fn=lambda: (
            f"({_ttm('n_cashflow_act')} - {_ttm('c_pay_acq_const_fiolta')}) / {EV}"
        ),
        category="Value", price_basis="mixed",
        sign="+", decay_days=120, neutralize="industry",
        rationale="FCF/EV yield (TTM OCF - TTM CapEx); cross-capital-structure "
                  "comparable. Replaces FCF/market-cap per GPT review.",
        requires=["n_cashflow_act", "c_pay_acq_const_fiolta", "total_liab", "money_cap"],
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
    # average total assets (stock) for flow/avg-assets ratios
    _AVG_TA = "((Ref($total_assets_q0, 1) + Ref($total_assets_q4, 1)) / 2)"
    # GPT Round-3 §B: gross profitability must use TTM single-quarter flows over
    # AVERAGE assets, not _cum_q0 (YTD, quarter-seasonal) over end assets. Decay
    # 120→250 (structural quality, not a short event signal).
    fams.append(dict(
        name_tmpl="qual_gross_profitability_ttm",
        expr_fn=lambda: (
            f"({_ttm('total_revenue')} - {_ttm('oper_cost')}) / {_AVG_TA}"
        ),
        category="Quality", price_basis="raw",
        sign="+", decay_days=250, neutralize="industry",
        rationale="Novy-Marx gross profitability (TTM gross profit / avg assets); "
                  "TTM + avg-assets per GPT Round-3 (was _cum_q0/end-assets).",
        requires=["total_revenue", "oper_cost", "total_assets"],
    ))
    # GPT Round-3 §C: qual_cash_roa DROPPED — it was _cum_q0/end-assets and is
    # redundant with acc_cash_roa_ttm (TTM OCF / avg assets) below. Do not keep both.
    # NOTE (GPT review §4 dedup): qual_dupont_margin / qual_dupont_turnover and
    # the qual_margin_{grossprofit_margin,netprofit_margin} ladder members were
    # DROPPED — they duplicate existing catalog factors qual_net_margin /
    # qual_asset_turnover / qual_gross_margin. Only the margin-ladder members the
    # catalog does NOT already have are retained.
    for f in ["op_of_gr", "ebit_of_gr", "profit_to_gr"]:
        fams.append(dict(
            name_tmpl=f"qual_margin_{f}",
            expr_fn=(lambda fld=f: f"Ref(${fld}, 1)"),
            category="Quality", price_basis="raw",
            sign="+", decay_days=120, neutralize="industry",
            rationale=f"Margin ladder member not in current catalog: {f}.",
            requires=[f],
        ))

    # ─────────── ACCRUALS / EARNINGS QUALITY (new, biggest gap) ───────────
    # GPT review §5: flow fields in a ratio must be TTM (_sq sum), not _cum_q0
    # (which is YTD and quarter-seasonal). Denominator total_assets is a stock →
    # use average of current + year-ago snapshot.
    AVG_TA = "((Ref($total_assets_q0, 1) + Ref($total_assets_q4, 1)) / 2)"
    fams.append(dict(
        name_tmpl="acc_total_accruals_ttm",
        expr_fn=lambda: (
            f"({_ttm('n_income')} - {_ttm('n_cashflow_act')}) / {AVG_TA}"
        ),
        category="Accruals", price_basis="raw",
        sign="-", decay_days=250, neutralize="industry",
        rationale="Sloan total accruals (TTM NI - TTM OCF) / avg assets; "
                  "seasonality-free per GPT review.",
        requires=["n_income", "n_cashflow_act", "total_assets"],
    ))
    fams.append(dict(
        name_tmpl="acc_cash_roa_ttm",
        expr_fn=lambda: f"{_ttm('n_cashflow_act')} / {AVG_TA}",
        category="Accruals", price_basis="raw",
        sign="+", decay_days=120, neutralize="industry",
        rationale="Cash ROA (TTM OCF / avg assets); cash-backed profitability.",
        requires=["n_cashflow_act", "total_assets"],
    ))
    fams.append(dict(
        name_tmpl="acc_cfo_to_ni_ttm",
        expr_fn=lambda: f"{_ttm('n_cashflow_act')} / {_ttm('n_income')}",
        category="Accruals", price_basis="raw",
        sign="+", decay_days=120, neutralize="industry",
        rationale="Cash-flow backing of earnings (TTM OCF / TTM NI); higher is "
                  "cleaner. TTM form per GPT review (note: unstable when NI~0).",
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
        name_tmpl="acc_capex_intensity_ttm",
        expr_fn=lambda: f"{_ttm('c_pay_acq_const_fiolta')} / {AVG_TA}",
        category="Accruals", price_basis="raw",
        sign="-", decay_days=250, neutralize="industry",
        rationale="CapEx intensity (TTM CapEx / avg assets); industry-neutralize "
                  "(GPT review: sign not universally negative — separate from growth).",
        requires=["c_pay_acq_const_fiolta", "total_assets"],
    ))
    fams.append(dict(
        name_tmpl="acc_rd_intensity_ttm",
        expr_fn=lambda: f"{_ttm('rd_exp')} / {_ttm('total_revenue')}",
        category="Accruals", price_basis="raw",
        sign="+", decay_days=250, neutralize="industry",
        rationale="R&D intensity (TTM R&D / TTM revenue); intangible-investment "
                  "premium; industry/stage-neutralize.",
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
    # GPT review §5: raw QoQ statement growth is seasonality-contaminated →
    # keep single-quarter YoY (compares same quarter) + YoY acceleration; drop
    # the bare QoQ variants.
    for f in ["revenue", "operate_profit", "n_income_attr_p", "total_revenue"]:
        fams.append(dict(
            name_tmpl=f"grow_{f}_yoy_q",
            expr_fn=(lambda fld=f: _yoy_q(fld)),
            category="Growth", price_basis="raw",
            sign="+", decay_days=90, neutralize="industry",
            rationale=f"Single-quarter YoY growth of {f} (same-quarter comparison).",
            requires=[f],
        ))
        fams.append(dict(
            name_tmpl=f"grow_{f}_yoy_accel_q",
            # GPT Round-3 §D: the previous `q0/q4 - q1/q4` was NOT YoY accel (prior-
            # quarter YoY needs q1/q5, and _sq_q5 is not materialized). Correct form
            # is a 1-quarter (~63 trading day) time-series Delta of the current YoY
            # rate — equivalent to (YoY_now - YoY_one_quarter_ago) without needing q5.
            expr_fn=(lambda fld=f: (
                f"Delta(Ref(${fld}_sq_q0, 1) / Ref(${fld}_sq_q4, 1) - 1, 63)"
            )),
            category="Growth", price_basis="raw",
            sign="+", decay_days=60, neutralize="industry",
            rationale=f"YoY-growth acceleration of {f}: 1-quarter Delta of the YoY "
                      f"rate (GPT Round-3 fix; avoids the unmaterialized _sq_q5).",
            requires=[f],
        ))

    # ─────────── LEVERAGE / SOLVENCY (extend) ───────────
    # GPT Round-5 §3: lev_net_debt_to_ebitda_ttm DROPPED — $ebitda is 3.3%-covered;
    # lev_interest_coverage_ttm DROPPED — $fin_exp_int_exp is 0%-covered (bin file
    # exists but contains no data). Both render to 100% NaN at compute time despite
    # passing static field-existence validation (F5 blind spot). Re-introduce when
    # the indicators provider re-materializes these fields, OR via $int_exp from
    # the income statement after a coverage audit.

    # ─────────── MOMENTUM / REVERSAL (extend) ───────────
    fams.append(dict(
        name_tmpl="mom_52w_high_proximity",
        expr_fn=lambda: f"{C1} / Max({op.ADJ_HIGH_T1}, 250)",
        category="Momentum", price_basis="adjusted",
        sign="+", decay_days=60, neutralize="industry",
        rationale="George-Hwang 52-week-high proximity (decay 60d per GPT review — "
                  "medium-term anchor, not a 1y-stale signal).",
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
    # GPT review §4/§5: the previous risk_parkinson_{w}d was (high-low)/close — a
    # range RATIO that duplicates the catalog's risk_range_ratio_20d and is NOT
    # Parkinson volatility. Replaced with the true log-range Parkinson estimator.
    for w in W_MED:
        fams.append(dict(
            name_tmpl=f"risk_parkinson_logrange_{w}d",
            expr_fn=(lambda ww=w: (
                f"Mean(Power(Log({op.ADJ_HIGH_T1} / {op.ADJ_LOW_T1}), 2), {ww})"
            )),
            category="Volatility", price_basis="adjusted",
            # GPT Round-3 §D: decay should track the lookback window, not a flat 20.
            sign="-", decay_days=w, neutralize="size",
            rationale=f"True Parkinson log high-low range variance ({w}d); fixes the "
                      "range-ratio mislabel (GPT review §4) + per-window decay (§D).",
            requires=["high", "low", "adj_factor"],
        ))
    fams.append(dict(
        name_tmpl="risk_gap_vol_20d",
        expr_fn=lambda: f"Std({op.ADJ_OPEN_T1} / Ref({op.ADJ_CLOSE}, 2) - 1, 20)",
        category="Volatility", price_basis="adjusted",
        sign="-", decay_days=20, neutralize="size",
        rationale="Overnight/T+1 gap risk; distinct from intraday vol (GPT review §1).",
        requires=["open", "close", "adj_factor"],
    ))

    # ─────────── LIQUIDITY / MICROSTRUCTURE (extend) ───────────
    # NOTE (screening diagnostic 2026-05-30): Qlib `Count(cond, N)` in this build
    # returns N (count of non-NaN obs), IGNORING the condition — verified
    # empirically (Count(ret>0,20) ≡ 20 for all stocks). It collapses any
    # Count-based factor to a cross-sectional constant (zero RankIC days). Use
    # `Sum(If(cond, 1, 0), N)` for conditional counts instead.
    for w in W_SHORT:
        fams.append(dict(
            name_tmpl=f"liq_zero_ret_days_{w}d",
            expr_fn=(lambda ww=w: f"Sum(If(Abs({RET}) < 0.0001, 1, 0), {ww}) / {ww}"),
            category="Liquidity", price_basis="adjusted",
            sign="-", decay_days=20, neutralize="size",
            rationale="Zero-return days (Lesmond illiquidity); Sum(If(...)) form — "
                      "Qlib Count() ignores the condition in this build.",
            requires=["close", "adj_factor"],
        ))

    # ─────────── CAPITAL FLOW (moneyflow — quarantine) ───────────
    # GPT Round-3 §F unit fix: moneyflow amount fields are in 万元 (10k yuan)
    # while daily $amount is in 千元 (thousand yuan) — a factor-of-10 mismatch.
    # Divide by ($amount / 10) so numerator and denominator share the 万元 basis.
    for w in W_SHORT:
        fams.append(dict(
            name_tmpl=f"flow_elg_net_pct_{w}d",
            expr_fn=(lambda ww=w: (
                f"Mean(Ref((($buy_elg_amount - $sell_elg_amount) / ($amount / 10)), 1), {ww})"
            )),
            category="CapitalFlow", price_basis="raw",
            sign="+", decay_days=10, neutralize="size",
            rationale="Extra-large order net inflow share (institutional flow); "
                      "unit-corrected ($amount/10 to match 万元 moneyflow basis).",
            requires=["buy_elg_amount", "sell_elg_amount", "amount"],
        ))
    # Institutional-minus-retail order-flow divergence (GPT Round-3 add, unit-fixed):
    # (large+elg net) - (small net), normalized by 万元-basis amount.
    fams.append(dict(
        name_tmpl="flow_inst_retail_divergence_20d",
        expr_fn=lambda: (
            "Mean(Ref(((($buy_lg_amount + $buy_elg_amount - $sell_lg_amount "
            "- $sell_elg_amount) - ($buy_sm_amount - $sell_sm_amount)) "
            "/ ($amount / 10)), 1), 20)"
        ),
        category="CapitalFlow", price_basis="raw",
        sign="+", decay_days=10, neutralize="size",
        rationale="Institutional (large+elg) minus retail (small) net order-flow "
                  "divergence; unit-corrected ($amount/10). GPT Round-3 add.",
        requires=["buy_lg_amount", "buy_elg_amount", "sell_lg_amount",
                  "sell_elg_amount", "buy_sm_amount", "sell_sm_amount", "amount"],
    ))

    # ─────────── LIMIT BOARDS (stk_limit — quarantine) ───────────
    # GPT Round-5: replaces the Round-2 Count-based limit_up_hit / limit_down_hit
    # rows (caught by the Count lint as silently degenerate).
    fams.append(dict(
        name_tmpl="limit_up_hit_5d",
        expr_fn=lambda: (
            "Sum(If(Ref($close, 1) >= Ref($up_limit, 1) * 0.999, 1, 0), 5) / 5"
        ),
        category="LimitBoard", price_basis="raw",
        sign="+", decay_days=5, neutralize="industry,size,liquidity",
        rationale="Exact limit-board continuation candidate (Sum(If) form per F1 lint). "
                  "Replaces the Count-based Round-2 row.",
        requires=["close", "up_limit"],
    ))
    fams.append(dict(
        name_tmpl="limit_down_hit_20d",
        expr_fn=lambda: (
            "Sum(If(Ref($close, 1) <= Ref($down_limit, 1) * 1.001, 1, 0), 20) / 20"
        ),
        category="LimitBoard", price_basis="raw",
        sign="-", decay_days=10, neutralize="industry,size,liquidity",
        rationale="Limit-down overhang / trading-interference risk (Sum(If) form per F1 lint).",
        requires=["close", "down_limit"],
    ))

    # ─────────── MARGIN (margin_detail — quarantine) ───────────
    # GPT Round-3 §E unit fix: rzmre/rzche are in 元 (yuan) while circ_mv is in
    # 万元 (10k yuan) — scale circ_mv by 10000 so the ratio is dimensionless.
    fams.append(dict(
        name_tmpl="margin_net_buy_ratio_20d",
        expr_fn=lambda: "Mean(Ref(($rzmre - $rzche), 1), 20) / (Ref($circ_mv, 1) * 10000)",
        category="Margin", price_basis="raw",
        sign="+", decay_days=20, neutralize="size",
        rationale="Net financing-buy intensity scaled by float cap; unit-corrected "
                  "(circ_mv * 10000 to match the 元 margin basis).",
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
    # GPT review finding #0: the previous `val_payout_ratio` referenced
    # `$cash_div_q0`, which is NOT materialized — the dividends endpoint writes
    # only flat `cash_div` / `cash_div_tax` (no _q0..q4 PIT variants, because it
    # is event-based, not a periodic statement). DROPPED. Dividend YIELD is
    # already covered by approved `dv_ttm` / `dv_ratio` in the existing catalog
    # (val_div_yield / val_div_ratio). A raw payout ratio needs the dividends
    # endpoint registered + event-timing validation before use.

    # ─────────── GPT Round-3 approved additions (price/volume only) ───────────
    # All use only approved OHLCV / daily_basic fields → formal-eligible today.
    fams.append(dict(
        name_tmpl="mom_skip5d_120d",
        expr_fn=lambda: f"Ref({op.ADJ_CLOSE}, 6) / Ref({op.ADJ_CLOSE}, 121) - 1",
        category="Momentum", price_basis="adjusted",
        sign="+", decay_days=60, neutralize="industry",
        rationale="Skip-last-week 120d momentum; drops the most recent 5 days to "
                  "reduce short-term-reversal / T+1-crowding contamination.",
        requires=["close", "adj_factor"],
    ))
    fams.append(dict(
        name_tmpl="risk_garman_klass_20d",
        expr_fn=lambda: (
            "Mean(0.5 * Power(Log(" + op.ADJ_HIGH_T1 + " / " + op.ADJ_LOW_T1 + "), 2) "
            "- 0.38629436112 * Power(Log(" + op.ADJ_CLOSE_T1 + " / " + op.ADJ_OPEN_T1 + "), 2), 20)"
        ),
        category="Volatility", price_basis="adjusted",
        sign="-", decay_days=20, neutralize="industry",
        rationale="Garman-Klass OHLC volatility estimator; uses open-close info on "
                  "top of the high-low range (GPT Round-3 add).",
        requires=["high", "low", "close", "open", "adj_factor"],
    ))
    fams.append(dict(
        name_tmpl="rev_turnover_spike_5d",
        expr_fn=lambda: (
            f"0 - ((Ref({op.ADJ_CLOSE}, 1) / Ref({op.ADJ_CLOSE}, 6) - 1) "
            "* (Mean(Ref($turnover_rate_f, 1), 5) / Mean(Ref($turnover_rate_f, 1), 60)))"
        ),
        category="Reversal", price_basis="adjusted",
        sign="+", decay_days=5, neutralize="industry",
        rationale="5d reversal conditioned on a free-float turnover spike; targets "
                  "retail/crowding overreaction (GPT Round-3 add).",
        requires=["close", "adj_factor", "turnover_rate_f"],
    ))
    # GPT Round-5 §2/§5: tech_high_breakout_age_250d (GPT Round-2) used
    # `0 - IdxMax(...)` which is SIGN-INVERTED under this build's IdxMax
    # convention (1-indexed from oldest: fresh high → high IdxMax → low after
    # negation, which is backwards). Replaced by a freshness factor that
    # ranks fresh highs HIGH using IdxMax directly. The Round-2 name is
    # superseded by the merge script.
    fams.append(dict(
        name_tmpl="tech_high_breakout_freshness_250d",
        expr_fn=lambda: f"IdxMax({op.ADJ_HIGH_T1}, 250)",
        category="Technical", price_basis="adjusted",
        sign="+", decay_days=30, neutralize="industry",
        rationale="52-week-high freshness: Qlib IdxMax is 1-indexed from the "
                  "oldest bar, so higher values mean the high occurred more "
                  "recently. Replaces the sign-inverted tech_high_breakout_age_250d.",
        requires=["high", "adj_factor"],
    ))
    fams.append(dict(
        name_tmpl="mom_continuous_info_252d_dir",
        # Da-Gurun-Warachka information discreteness, direction-correct (GPT Round-3
        # §G fix: the un-Abs'd form ranked smooth losers high because Sign<0 × count<0
        # → positive). Abs() on the up-minus-down count restores the intended sign:
        # continuous winners high, continuous losers low.
        # Count() is broken in this Qlib build (ignores the condition, returns N) —
        # use Sum(If(cond,1,0),N) for the up/down day counts. Verified 2026-05-30.
        expr_fn=lambda: (
            f"Sign(Ref({op.ADJ_CLOSE}, 1) / Ref({op.ADJ_CLOSE}, 253) - 1) "
            f"* Abs((Sum(If({RET} > 0, 1, 0), 252) - Sum(If({RET} < 0, 1, 0), 252)) / 252)"
        ),
        category="Momentum", price_basis="adjusted",
        sign="+", decay_days=60, neutralize="industry",
        rationale="Directional information-discreteness (frog-in-the-pan); smooth "
                  "trends rank by direction. GPT Round-3 sign fix + Sum(If) count fix.",
        requires=["close", "adj_factor"],
    ))

    return fams


def expand_families(
    families: list[dict], base_stems: set[str], raw_stems: set[str]
) -> list[dict]:
    """Expand templates into concrete candidate rows, gated on field existence.

    Two-layer gate (hardened after GPT 5.5 Pro review finding #0, which caught
    ``$cash_div_q0`` — a base stem that exists but whose PIT variant was never
    materialized):

    1. ``requires`` base stems must exist (coarse pre-check).
    2. **Every ``$field`` token in the BUILT expression must exist in the RAW
       materialized bin set.** This is the authoritative check — it validates the
       exact PIT variant (`_q0`, `_sq_q0`, `_cum_q0`, …), not the collapsed base.
    """
    rows: list[dict] = []
    skipped: list[str] = []
    for fam in families:
        missing = [r for r in fam.get("requires", []) if r not in base_stems]
        if missing:
            skipped.append(f"{fam['name_tmpl']} (missing base stem {missing})")
            continue
        expr = fam["expr_fn"]()
        # Authoritative gate: every raw $field token must be materialized.
        tokens = [t[1:] for t in extract_qlib_fields(expr)]
        missing_tok = sorted(t for t in tokens if t not in raw_stems)
        if missing_tok:
            skipped.append(f"{fam['name_tmpl']} (non-materialized variant {missing_tok})")
            continue
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
    rows = expand_families(families, set(base_stems), set(raw_stems))
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
