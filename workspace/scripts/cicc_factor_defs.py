# SCRIPT_STATUS: ACTIVE — Phase D CICC fundamental factor definitions
"""CICC fundamental-factor replication expressions (Phase D batch 1).

Each entry: CICC code -> CiccFactorDef(expr, category, tier, caveat, dedup).
Tiers: exact (semantics match the CICC formula with registered fields) / approx
(vendor cumulative-period indicators or derived equity; per-factor caveat).
blocked-slots / blocked-data factors are NOT here — see PHASE_D_PLAN.md.

Conventions (frozen by the Phase-C calibration, CALIBRATION_REPORT.md):
- CICC-protocol sampling is month-end same-day (no Ref lag) — these expressions
  are for the truth-comparison layer. CATALOG registration later wraps fields in
  Ref(...,1) per §3.2 (predictive next-day convention) — do NOT paste these into
  operators.py unchanged.
- Statement units are 元; $total_mv/$circ_mv are 万元 (scale 1e4 where mixed).
- D-suffix (当期−上期) means prior QUARTER (empirically certified via GPMD).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CiccFactorDef:
    code: str            # CICC code, as in the truth tables
    category: str        # 盈利/成长/营运/盈余/安全/治理/估值/规模/价量
    expr: str            # Qlib expression (truth-comparison layer, same-day)
    tier: str            # exact | approx
    caveat: str = ""     # construction deviation from the CICC formula
    dedup: str = ""      # existing catalog factor with the same semantics
    negative: bool = False  # CICC direction is negative (IC < 0 expected)


# ---- TTM / balance building blocks (exact) ---------------------------------
NI_TTM = "($n_income_sq_q0 + $n_income_sq_q1 + $n_income_sq_q2 + $n_income_sq_q3)"
REV_TTM = "($total_revenue_sq_q0 + $total_revenue_sq_q1 + $total_revenue_sq_q2 + $total_revenue_sq_q3)"
REV_TTM_PREV = "($total_revenue_sq_q1 + $total_revenue_sq_q2 + $total_revenue_sq_q3 + $total_revenue_sq_q4)"
COST_TTM = "($oper_cost_sq_q0 + $oper_cost_sq_q1 + $oper_cost_sq_q2 + $oper_cost_sq_q3)"
COST_TTM_PREV = "($oper_cost_sq_q1 + $oper_cost_sq_q2 + $oper_cost_sq_q3 + $oper_cost_sq_q4)"
OCF_TTM = "($n_cashflow_act_sq_q0 + $n_cashflow_act_sq_q1 + $n_cashflow_act_sq_q2 + $n_cashflow_act_sq_q3)"
EBIT_TTM = "($ebit_sq_q0 + $ebit_sq_q1 + $ebit_sq_q2 + $ebit_sq_q3)"
CAPEX_TTM = ("($c_pay_acq_const_fiolta_sq_q0 + $c_pay_acq_const_fiolta_sq_q1 + "
             "$c_pay_acq_const_fiolta_sq_q2 + $c_pay_acq_const_fiolta_sq_q3)")
AVG_ASSETS = "(($total_assets_q0 + $total_assets_q4) / 2)"
AVG_INV = "(($inventories_q0 + $inventories_q4) / 2)"
AVG_AR = "(($accounts_receiv_q0 + $accounts_receiv_q4) / 2)"
EQUITY = "($bps * $total_share * 10000)"   # vendor 每股净资产 × 总股本(万股) -> 元
MV_YUAN = "($total_mv * 10000)"
EQUITY_CAVEAT = "净资产=vendor bps×总股本(近似归母权益,ann_date锚)"
NI_MINORITY_CAVEAT = "净利TTM含少数股东(归母单季仅q0/q4)"
CUM_YOY_CAVEAT = "indicators累计口径同比,非严格TTM同比(ann_date锚)"

_Z_WIN = 500  # ~2y trading days for time-series z-scores of step-like yoy series


def _z(expr: str) -> str:
    return f"(({expr}) - Mean({expr}, {_Z_WIN})) / Std({expr}, {_Z_WIN})"


_DEFS: list[CiccFactorDef] = [
    # ── 盈利能力 ────────────────────────────────────────────────────────────
    CiccFactorDef("CFOA", "盈利", f"{OCF_TTM} / $total_assets_q0", "exact"),
    CiccFactorDef("ROA_TTM", "盈利", f"{NI_TTM} / $total_assets_q0", "exact",
                  caveat=NI_MINORITY_CAVEAT),
    CiccFactorDef("ROE_TTM", "盈利", f"{NI_TTM} / {EQUITY}", "approx",
                  caveat=f"{NI_MINORITY_CAVEAT}; {EQUITY_CAVEAT}", dedup="qual_roe 族"),
    CiccFactorDef("ROIC_TTM", "盈利",
                  f"{EBIT_TTM} * (1 - $tax_to_ebt/100) / ({EQUITY} + $lt_borr_q0 + $st_borr_q0)",
                  "approx", caveat=f"税率用$tax_to_ebt;投入资本={EQUITY_CAVEAT}+长短期借款"),
    # ── 成长 ────────────────────────────────────────────────────────────────
    CiccFactorDef("NP_Q_YOY", "成长",
                  "($n_income_attr_p_sq_q0 - $n_income_attr_p_sq_q4) / Abs($n_income_attr_p_sq_q4)",
                  "exact", dedup="grow_n_income_attr_p_yoy_accel_q 的基础项"),
    CiccFactorDef("NP_QOQ", "成长",
                  "($n_income_sq_q0 - $n_income_sq_q1) / Abs($n_income_sq_q1)",
                  "exact", caveat="单季环比用含少数净利(归母q1槽缺)"),
    CiccFactorDef("OP_Q_YOY", "成长",
                  "($operate_profit_sq_q0 - $operate_profit_sq_q4) / Abs($operate_profit_sq_q4)",
                  "exact", dedup="grow_operate_profit_yoy_accel_q 的基础项"),
    CiccFactorDef("OP_QOQ", "成长", "$q_op_qoq", "exact",
                  caveat="vendor单季环比字段(语义一致)"),
    CiccFactorDef("OR_Q_YOY", "成长",
                  "($total_revenue_sq_q0 - $total_revenue_sq_q4) / Abs($total_revenue_sq_q4)",
                  "exact", caveat="营业总收入口径", dedup="grow_total_revenue_yoy_accel_q 的基础项"),
    CiccFactorDef("TA_YOY", "成长",
                  "($total_assets_q0 - $total_assets_q4) / Abs($total_assets_q4)", "exact"),
    CiccFactorDef("EPS_YOY", "成长", "$basic_eps_yoy", "approx", caveat=CUM_YOY_CAVEAT),
    CiccFactorDef("NP_Deducted_YOY", "成长", "$dt_netprofit_yoy", "approx", caveat=CUM_YOY_CAVEAT),
    CiccFactorDef("NP_YOY", "成长", "$netprofit_yoy", "approx", caveat=CUM_YOY_CAVEAT),
    CiccFactorDef("NP_Z", "成长", _z("$netprofit_yoy"), "approx",
                  caveat=f"{CUM_YOY_CAVEAT}; z窗={_Z_WIN}交易日(~2y)"),
    CiccFactorDef("OP_YOY", "成长", "$op_yoy", "approx", caveat=CUM_YOY_CAVEAT),
    CiccFactorDef("OP_Z", "成长", _z("$op_yoy"), "approx",
                  caveat=f"{CUM_YOY_CAVEAT}; z窗={_Z_WIN}"),
    CiccFactorDef("OR_YOY", "成长", "$or_yoy", "approx", caveat=CUM_YOY_CAVEAT),
    CiccFactorDef("ROE_YOY", "成长", "$roe_yoy", "approx", caveat=CUM_YOY_CAVEAT),
    # ── 营运效率 ────────────────────────────────────────────────────────────
    CiccFactorDef("AT", "营运", f"{REV_TTM} / {AVG_ASSETS}", "exact"),
    CiccFactorDef("ATD", "营运", f"({REV_TTM} - {REV_TTM_PREV}) / {AVG_ASSETS}", "approx",
                  caveat="上期周转率的分母近似用当期平均资产(资产q1槽缺)"),
    CiccFactorDef("GPMD", "营运",
                  f"(1 - {COST_TTM}/{REV_TTM}) - (1 - {COST_TTM_PREV}/{REV_TTM_PREV})", "exact"),
    CiccFactorDef("INVT", "营运", f"{COST_TTM} / {AVG_INV}", "exact"),
    CiccFactorDef("INVTD", "营运", f"({COST_TTM} - {COST_TTM_PREV}) / {AVG_INV}", "approx",
                  caveat="同 ATD 的分母近似"),
    CiccFactorDef("NPM_TTM", "营运", f"{NI_TTM} / {REV_TTM}", "exact",
                  caveat=NI_MINORITY_CAVEAT),
    CiccFactorDef("OPM_TTM", "营运", "$op_of_gr", "approx",
                  caveat="vendor累计口径营业利润/营业总收入(OP单季槽缺q1-q3)"),
    CiccFactorDef("RAT", "营运", f"{REV_TTM} / {AVG_AR}", "exact",
                  caveat="缺应收票据科目,仅应收账款"),
    CiccFactorDef("RATD", "营运", f"({REV_TTM} - {REV_TTM_PREV}) / {AVG_AR}", "approx",
                  caveat="同 ATD 的分母近似"),
    # ── 盈余质量 ────────────────────────────────────────────────────────────
    CiccFactorDef("CSR", "盈余", "$money_cap_q0 / $total_cur_liab_q0", "exact"),
    # ── 安全性 ──────────────────────────────────────────────────────────────
    CiccFactorDef("CCR", "安全", f"{OCF_TTM} / $total_cur_liab_q0", "exact"),
    CiccFactorDef("CUR", "安全", "$total_cur_assets_q0 / $total_cur_liab_q0", "exact"),
    CiccFactorDef("QR", "安全", "$quick_ratio", "exact",
                  caveat="vendor速动比率(与中金扣减项细节或异)"),
    CiccFactorDef("Debt_Asset", "安全", "$total_liab_q0 / $total_assets_q0", "exact",
                  dedup="lev_* 族", negative=True),
    CiccFactorDef("DTE", "安全", f"$total_liab_q0 / {EQUITY}", "approx",
                  caveat=EQUITY_CAVEAT, negative=True),
    # ── 治理 ────────────────────────────────────────────────────────────────
    CiccFactorDef("DPR_TTM", "治理", f"($dv_ttm/100) * {MV_YUAN} / {NI_TTM}", "approx",
                  caveat="分红总额=股息率TTM×市值(vendor); 分母含少数净利"),
    # ── 估值 ────────────────────────────────────────────────────────────────
    CiccFactorDef("BP_LR", "估值", "1 / $pb", "exact",
                  caveat="vendor pb=价格/最新财报每股净资产(LR口径吻合)", dedup="val_bp 类"),
    CiccFactorDef("EP_TTM", "估值", f"{NI_TTM} / {MV_YUAN}", "exact",
                  caveat=f"{NI_MINORITY_CAVEAT}(1/pe_ttm会丢亏损股,不用)", dedup="val_ep_ttm"),
    CiccFactorDef("DP", "估值", "$dv_ttm", "exact",
                  caveat="非分红股填0(C阶段冻结)", dedup="val_div_yield"),
    CiccFactorDef("FCFP_TTM", "估值", f"({OCF_TTM} - {CAPEX_TTM}) / {MV_YUAN}", "exact",
                  caveat="FCF=OCF−购建固资现金(简化口径)", dedup="val_cftp 类"),
    CiccFactorDef("OCFP_TTM", "估值", f"{OCF_TTM} / {MV_YUAN}", "exact"),
    CiccFactorDef("SP_TTM", "估值", f"{REV_TTM} / {MV_YUAN}", "exact",
                  caveat="营业总收入口径", dedup="val_sp_ttm"),
    CiccFactorDef("PEG_TTM", "估值", "$pe_ttm / $netprofit_yoy", "approx",
                  caveat="分母为累计口径同比;负增长/亏损为NaN由排名自然处理", negative=True),
    # ── 规模 ────────────────────────────────────────────────────────────────
    CiccFactorDef("MC", "规模", "$total_mv", "exact", negative=True),
    CiccFactorDef("Ln_MC", "规模", "Log($total_mv)", "exact",
                  dedup="size_ln_mcap", negative=True),
    CiccFactorDef("FC", "规模", "$circ_mv", "exact", negative=True),
    CiccFactorDef("Ln_FC", "规模", "Log($circ_mv)", "exact",
                  dedup="size_ln_circmv", negative=True),
    CiccFactorDef("FC_MC", "规模", "$circ_mv / $total_mv", "exact"),
    # ── 价量(C 阶段锚,保留在批中作回归监控) ───────────────────────────────
    CiccFactorDef("mmt_normal_M", "价量",
                  "$close*$adj_factor / Ref($close*$adj_factor, 20) - 1", "exact",
                  negative=True),
    # mmt_range_M 在驱动里以 pandas 计算(条件滚动和)
]

CICC_FACTOR_DEFS: dict[str, CiccFactorDef] = {d.code: d for d in _DEFS}


def exprs(tier: str | None = None) -> dict[str, str]:
    """code -> expression, optionally filtered by tier."""
    return {d.code: d.expr for d in _DEFS if tier is None or d.tier == tier}


if __name__ == "__main__":
    from collections import Counter
    print(f"{len(_DEFS)} defs:", dict(Counter(d.tier for d in _DEFS)))
    print("by category:", dict(Counter(d.category for d in _DEFS)))
