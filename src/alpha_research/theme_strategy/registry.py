from __future__ import annotations

from dataclasses import dataclass

from .schema import SignalRecipe, ThemeSpec, UniverseCandidate


@dataclass(frozen=True)
class FieldDefinition:
    field_name: str
    qlib_expression: str
    field_family: str
    provider_source: str
    freq_type: str
    pit_safe: bool
    theme_tags: tuple[str, ...]


@dataclass(frozen=True)
class RecipeSeedDefinition:
    recipe_id: str
    theme_id: str
    component_ids: tuple[str, ...]
    selection_note: str


FIELD_DEFINITIONS: tuple[FieldDefinition, ...] = (
    FieldDefinition("open", "Ref($open, 1)", "market_daily", "market_daily", "daily", True, ("small_cap", "st", "flow_northbound", "growth")),
    FieldDefinition("high", "Ref($high, 1)", "market_daily", "market_daily", "daily", True, ("small_cap", "st", "flow_northbound", "growth")),
    FieldDefinition("low", "Ref($low, 1)", "market_daily", "market_daily", "daily", True, ("small_cap", "st", "flow_northbound", "growth")),
    FieldDefinition("close", "Ref($close, 1)", "market_daily", "market_daily", "daily", True, ("small_cap", "st", "flow_northbound", "growth")),
    FieldDefinition("pre_close", "Ref($pre_close, 1)", "market_daily", "market_daily", "daily", True, ("small_cap", "st", "flow_northbound", "growth")),
    FieldDefinition("pct_chg", "Ref($pct_chg, 1)", "market_daily", "market_daily", "daily", True, ("small_cap", "st", "flow_northbound", "growth")),
    FieldDefinition("vol", "Ref($vol, 1)", "market_daily", "market_daily", "daily", True, ("small_cap", "st", "flow_northbound", "growth")),
    FieldDefinition("amount", "Ref($amount, 1)", "market_daily", "market_daily", "daily", True, ("small_cap", "st", "flow_northbound", "growth")),
    FieldDefinition("adj_factor", "Ref($adj_factor, 1)", "market_daily", "market_daily", "daily", True, ("small_cap", "st", "flow_northbound", "growth")),
    FieldDefinition("turnover_rate", "Ref($turnover_rate, 1)", "market_daily", "market_daily", "daily", True, ("small_cap", "st")),
    FieldDefinition("turnover_rate_f", "Ref($turnover_rate_f, 1)", "market_daily", "market_daily", "daily", True, ("small_cap", "st")),
    FieldDefinition("volume_ratio", "Ref($volume_ratio, 1)", "market_daily", "market_daily", "daily", True, ("small_cap", "st", "flow_northbound", "growth")),
    FieldDefinition("total_mv", "Ref($total_mv, 1)", "valuation_size", "daily_basic", "daily", True, ("small_cap", "st", "flow_northbound", "growth")),
    FieldDefinition("circ_mv", "Ref($circ_mv, 1)", "valuation_size", "daily_basic", "daily", True, ("small_cap", "st", "flow_northbound", "growth")),
    FieldDefinition("free_share", "Ref($free_share, 1)", "valuation_size", "daily_basic", "daily", True, ("small_cap", "st")),
    FieldDefinition("pe_ttm", "Ref($pe_ttm, 1)", "valuation_size", "daily_basic", "daily", True, ("small_cap",)),
    FieldDefinition("pb", "Ref($pb, 1)", "valuation_size", "daily_basic", "daily", True, ("small_cap",)),
    FieldDefinition("ps_ttm", "Ref($ps_ttm, 1)", "valuation_size", "daily_basic", "daily", True, ("small_cap",)),
    FieldDefinition("dv_ttm", "Ref($dv_ttm, 1)", "valuation_size", "daily_basic", "daily", True, ("small_cap",)),
    FieldDefinition("grossprofit_margin", "Ref($grossprofit_margin, 1)", "financial_snapshot", "fina_indicator", "daily", True, ("small_cap",)),
    FieldDefinition("netprofit_margin", "Ref($netprofit_margin, 1)", "financial_snapshot", "fina_indicator", "daily", True, ("small_cap",)),
    FieldDefinition("roe", "Ref($roe, 1)", "financial_snapshot", "fina_indicator", "daily", True, ("small_cap",)),
    FieldDefinition("roa", "Ref($roa, 1)", "financial_snapshot", "fina_indicator", "daily", True, ("small_cap",)),
    FieldDefinition("roic", "Ref($roic, 1)", "financial_snapshot", "fina_indicator", "daily", True, ("small_cap",)),
    FieldDefinition("debt_to_assets", "Ref($debt_to_assets, 1)", "financial_snapshot", "fina_indicator", "daily", True, ("small_cap",)),
    FieldDefinition("current_ratio", "Ref($current_ratio, 1)", "financial_snapshot", "fina_indicator", "daily", True, ("small_cap",)),
    FieldDefinition("quick_ratio", "Ref($quick_ratio, 1)", "financial_snapshot", "fina_indicator", "daily", True, ("small_cap",)),
    FieldDefinition("n_income_attr_p", "Ref($n_income_attr_p, 1)", "financial_snapshot", "income", "daily", True, ("small_cap", "growth")),
    FieldDefinition("operate_profit", "Ref($operate_profit, 1)", "financial_snapshot", "income", "daily", True, ("small_cap", "st")),
    FieldDefinition("eps", "Ref($eps, 1)", "financial_snapshot", "income", "daily", True, ("small_cap",)),
    FieldDefinition("ocfps", "Ref($ocfps, 1)", "financial_snapshot", "cashflow", "daily", True, ("small_cap",)),
    FieldDefinition("or_yoy", "Ref($or_yoy, 1)", "growth_pit", "fina_indicator", "daily", True, ("small_cap",)),
    FieldDefinition("netprofit_yoy", "Ref($netprofit_yoy, 1)", "growth_pit", "fina_indicator", "daily", True, ("small_cap",)),
    FieldDefinition("basic_eps_yoy", "Ref($basic_eps_yoy, 1)", "growth_pit", "fina_indicator", "daily", True, ("small_cap", "st")),
    FieldDefinition("q_op_qoq", "Ref($q_op_qoq, 1)", "growth_pit", "fina_indicator", "daily", True, ("small_cap", "st")),
    FieldDefinition("pit_or_yoy", "Ref($pit_or_yoy, 1)", "growth_pit", "pit_provider", "daily", True, ("small_cap",)),
    FieldDefinition("pit_netprofit_yoy", "Ref($pit_netprofit_yoy, 1)", "growth_pit", "pit_provider", "daily", True, ("small_cap", "st")),
    FieldDefinition("pit_basic_eps_yoy", "Ref($pit_basic_eps_yoy, 1)", "growth_pit", "pit_provider", "daily", True, ("small_cap", "st")),
    FieldDefinition("pit_q_sales_yoy", "Ref($pit_q_sales_yoy, 1)", "growth_pit", "pit_provider", "daily", True, ("small_cap", "st")),
    FieldDefinition("pit_q_op_qoq", "Ref($pit_q_op_qoq, 1)", "growth_pit", "pit_provider", "daily", True, ("small_cap", "st")),
    FieldDefinition("pit_ocf_yoy", "Ref($pit_ocf_yoy, 1)", "growth_pit", "pit_provider", "daily", True, ("small_cap",)),
    FieldDefinition("revenue_q", "Ref($revenue_q, 1)", "quarterly", "single_quarter", "daily", True, ("small_cap", "st")),
    FieldDefinition("core_profit_q", "Ref($core_profit_q, 1)", "quarterly", "single_quarter", "daily", True, ("st",)),
    FieldDefinition("net_mf_amount", "Ref($net_mf_amount, 1)", "moneyflow", "moneyflow", "daily", True, ("st", "flow_northbound")),
    FieldDefinition("buy_lg_amount", "Ref($buy_lg_amount, 1)", "moneyflow", "moneyflow", "daily", True, ("st", "flow_northbound")),
    FieldDefinition("sell_lg_amount", "Ref($sell_lg_amount, 1)", "moneyflow", "moneyflow", "daily", True, ("st", "flow_northbound")),
    FieldDefinition("buy_sm_amount", "Ref($buy_sm_amount, 1)", "moneyflow", "moneyflow", "daily", True, ("st", "flow_northbound")),
    FieldDefinition("sell_sm_amount", "Ref($sell_sm_amount, 1)", "moneyflow", "moneyflow", "daily", True, ("st", "flow_northbound")),
    FieldDefinition("ratio", "Ref($ratio, 1)", "northbound", "hk_hold", "daily", True, ("flow_northbound",)),
    FieldDefinition("rzye", "Ref($rzye, 1)", "margin", "margin_detail", "daily", True, ("st", "flow_northbound")),
    FieldDefinition("rqye", "Ref($rqye, 1)", "margin", "margin_detail", "daily", True, ("st", "flow_northbound")),
    FieldDefinition("rzmre", "Ref($rzmre, 1)", "margin", "margin_detail", "daily", True, ("st", "flow_northbound")),
    FieldDefinition("rzche", "Ref($rzche, 1)", "margin", "margin_detail", "daily", True, ("st", "flow_northbound")),
    FieldDefinition("rqyl", "Ref($rqyl, 1)", "margin", "margin_detail", "daily", True, ("st", "flow_northbound")),
    FieldDefinition("rqmcl", "Ref($rqmcl, 1)", "margin", "margin_detail", "daily", True, ("st", "flow_northbound")),
    FieldDefinition("rqchl", "Ref($rqchl, 1)", "margin", "margin_detail", "daily", True, ("st", "flow_northbound")),
    FieldDefinition("holder_num", "Ref($holder_num, 1)", "event_holder", "holder_number", "daily", True, ("st",)),
    FieldDefinition("p_change_min", "Ref($p_change_min, 1)", "event_forecast", "forecast", "daily", True, ("st",)),
    FieldDefinition("p_change_max", "Ref($p_change_max, 1)", "event_forecast", "forecast", "daily", True, ("st",)),
    FieldDefinition("up_limit", "Ref($up_limit, 1)", "limit_price", "stk_limit", "daily", True, ("st",)),
    FieldDefinition("down_limit", "Ref($down_limit, 1)", "limit_price", "stk_limit", "daily", True, ("st",)),
    # ── Growth theme (added 2026-04-22 for hyp_20260421_001 and hyp_20260421_002) ──
    # Each field embeds the full Qlib expression for the corresponding catalog
    # factor. They are PIT-safe (every $field is wrapped in Ref(...)).
    # ComponentSpecs use raw_field + level_rank/direct to consume them as-is.
    FieldDefinition("g_alpha_inst_net_buy_20d", "Sum(Ref($top_inst__net_buy, 1), 20)", "growth_signal", "alpha_endpoint", "daily", True, ("growth",)),
    FieldDefinition("g_grow_roe_yoy", "Ref($roe_yoy, 1)", "growth_signal", "fina_indicator", "daily", True, ("growth",)),
    FieldDefinition("g_grow_opprofit_yoy", "Ref($op_yoy, 1)", "growth_signal", "fina_indicator", "daily", True, ("growth",)),
    FieldDefinition("g_grow_eps_yoy", "Ref($basic_eps_yoy, 1)", "growth_signal", "fina_indicator", "daily", True, ("growth",)),
    FieldDefinition("g_grow_opprofit_qoq", "Ref($q_op_qoq, 1)", "growth_signal", "fina_indicator", "daily", True, ("growth",)),
    FieldDefinition("g_grow_netprofit_yoy", "Ref($netprofit_yoy, 1)", "growth_signal", "fina_indicator", "daily", True, ("growth",)),
    FieldDefinition("g_grow_rev_trend", "Slope(Ref($or_yoy, 1), 4)", "growth_signal", "fina_indicator", "daily", True, ("growth",)),
    FieldDefinition("g_qual_roe", "Ref($roe, 1)", "growth_signal", "fina_indicator", "daily", True, ("growth",)),
    FieldDefinition("g_qual_roe_stability", "0 - Std(Ref($roe, 1), 60)", "growth_signal", "fina_indicator", "daily", True, ("growth",)),
    FieldDefinition("g_qual_margin_trend", "Slope(Ref($grossprofit_margin, 1), 4)", "growth_signal", "fina_indicator", "daily", True, ("growth",)),
    FieldDefinition("g_val_ep_ttm", "1.0 / Ref($pe_ttm, 1)", "growth_signal", "daily_basic", "daily", True, ("growth",)),
    FieldDefinition("g_mom_return_60d", "Ref(($close * $adj_factor), 1) / Ref(($close * $adj_factor), 61) - 1", "growth_signal", "market_daily", "daily", True, ("growth",)),
    # Execution guardrail
    FieldDefinition("g_amount_adv20", "Mean(Ref($amount, 1), 20)", "growth_signal", "market_daily", "daily", True, ("growth",)),
)


RECIPE_SEEDS: dict[str, RecipeSeedDefinition] = {
    "size_only": RecipeSeedDefinition(
        recipe_id="size_only",
        theme_id="small_cap",
        component_ids=("small_cap_total_mv_small_rank",),
        selection_note="最纯粹的小市值暴露，作为 universe 对比的锚点。",
    ),
    "small_value": RecipeSeedDefinition(
        recipe_id="small_value",
        theme_id="small_cap",
        component_ids=("small_cap_total_mv_small_rank", "small_cap_pb_value_rank"),
        selection_note="小市值 + 低 PB，检验估值是否为有效确认项。",
    ),
    "small_quality_lowvol": RecipeSeedDefinition(
        recipe_id="small_quality_lowvol",
        theme_id="small_cap",
        component_ids=("small_cap_total_mv_small_rank", "small_cap_roe_rank", "small_cap_low_vol_20d"),
        selection_note="小市值 + 质量 + 低波动，检验是否能改善回撤与持有体验。",
    ),
    "mv_revenue": RecipeSeedDefinition(
        recipe_id="mv_revenue",
        theme_id="st",
        component_ids=("st_total_mv_small_rank", "st_revenue_q_rank"),
        selection_note="困境反身性里叠加单季度营收修复。",
    ),
    "reversal_revenue": RecipeSeedDefinition(
        recipe_id="reversal_revenue",
        theme_id="st",
        component_ids=("st_short_reversal_5d", "st_revenue_q_rank"),
        selection_note="超跌反弹 + 单季度营收修复。",
    ),
    "reversal_liquidity_revenue": RecipeSeedDefinition(
        recipe_id="reversal_liquidity_revenue",
        theme_id="st",
        component_ids=("st_short_reversal_5d", "st_revenue_q_rank", "st_turnover_20d_rank"),
        selection_note="超跌反弹 + 修复 + 流动性确认。",
    ),
    "north_follow": RecipeSeedDefinition(
        recipe_id="north_follow",
        theme_id="flow_northbound",
        component_ids=("flow_northbound_hold_change_5d", "flow_northbound_accumulation_20d"),
        selection_note="跟随北向增持与持续性。",
    ),
    "flow_follow": RecipeSeedDefinition(
        recipe_id="flow_follow",
        theme_id="flow_northbound",
        component_ids=("flow_northbound_net_inflow_20d", "flow_northbound_large_small_ratio"),
        selection_note="跟随主力资金净流入与大小单分歧。",
    ),
    "flow_north_defensive": RecipeSeedDefinition(
        recipe_id="flow_north_defensive",
        theme_id="flow_northbound",
        component_ids=("flow_northbound_hold_change_5d", "flow_northbound_net_inflow_20d", "flow_northbound_low_vol_20d"),
        selection_note="北向 + 内资共振，再用低波动做执行约束。",
    ),
    # ── Growth theme seeds (2026-04-22, hyp_20260421_001 + hyp_20260421_002) ──
    # Construction is equal-weight at the seed level; theme_strategy's
    # signal_search will explore structural variants (1core + N confirmation).
    # The original hypothesis weight vectors are documented intent; equal-weight
    # is the operational baseline (see Phase 2 audit notes in plan file).
    "growth_quality_momentum": RecipeSeedDefinition(
        recipe_id="growth_quality_momentum",
        theme_id="growth",
        component_ids=(
            "growth_alpha_inst_net_buy_20d",
            "growth_grow_roe_yoy",
            "growth_grow_netprofit_yoy",
            "growth_grow_opprofit_yoy",
            "growth_grow_eps_yoy",
            "growth_grow_opprofit_qoq",
            "growth_qual_roe_stability",
            "growth_mom_return_60d",
        ),
        selection_note="Hypothesis A: institutional accumulation + multi-source profit growth + quality/momentum confirmation. Components are the Phase-1 survivors that exhibit BOTH positive rank_icir AND positive long-short Sharpe pre-cost.",
    ),
    "garp_confirmation": RecipeSeedDefinition(
        recipe_id="garp_confirmation",
        theme_id="growth",
        component_ids=(
            "growth_grow_netprofit_yoy",
            "growth_grow_rev_trend",
            "growth_val_ep_ttm",
            "growth_qual_roe",
            "growth_qual_margin_trend",
        ),
        selection_note="Hypothesis B: Growth-at-Reasonable-Price composite — current growth + growth persistence + value + quality + margin trend.",
    ),
}


THEME_SPECS: dict[str, ThemeSpec] = {
    "small_cap": ThemeSpec(
        theme_id="small_cap",
        thesis="A 股小市值并不一定需要复杂加权，关键是先把可交易、非噪音、能代表小票风险溢价的股票池定义对。",
        benchmark="000852.SH",
        data_start="2012-01-01",
        universe_candidates=(
            UniverseCandidate("sc_u1", "csi1000", "mainboard", "exclude", 375, 1_000_000_000, 10_000_000_000, 50.0, 20_000_000.0, 100_000_000.0, False, "n_income_attr_p", True),
            UniverseCandidate("sc_u2", "csi1000", "mainboard", "exclude", 375, 1_000_000_000, 20_000_000_000, 50.0, 20_000_000.0, 100_000_000.0, False, "n_income_attr_p", True),
            UniverseCandidate("sc_u3", "csi1000", "mainboard", "exclude", 375, 1_000_000_000, 20_000_000_000, None, 20_000_000.0, 100_000_000.0, False, "n_income_attr_p", True),
            UniverseCandidate("sc_u4", "all_market", "mainboard", "exclude", 375, 1_000_000_000, 10_000_000_000, None, 20_000_000.0, 100_000_000.0, False, "n_income_attr_p", True),
            UniverseCandidate("sc_u5", "all_market", "mainboard", "exclude", 375, 1_000_000_000, 20_000_000_000, None, 20_000_000.0, 100_000_000.0, False, "n_income_attr_p", True),
            UniverseCandidate("sc_u6", "all_market", "mainboard", "exclude", 120, 1_000_000_000, 30_000_000_000, None, 5_000_000.0, None, False, None, False),
        ),
        anchor_recipes=("size_only", "small_value"),
        event_driven_defaults={"capital": 2_000_000.0, "slippage_rate": 0.0005, "participation_cap": 0.02},
        topk_grid=(4, 10),
        rebalance_grid=(5, 10),
        recipe_seeds=("size_only", "small_value", "small_quality_lowvol"),
        diagnostic_rebalance_days=5,
        notes="第一版先验证小市值本体与质量/价值确认项，不上黑箱学权重。",
    ),
    "st": ThemeSpec(
        theme_id="st",
        thesis="ST 机会核心不是广撒网找因子，而是把困境修复、情绪过度和执行约束同时放进股票池与 component 设计里。",
        benchmark="000001.SH",
        data_start="2012-01-01",
        universe_candidates=(
            UniverseCandidate("st_u1", "st_only", "all", "include_only", 60),
            UniverseCandidate("st_u2", "st_only", "all", "include_only", 60, ret250_pctile_max=0.90),
            UniverseCandidate("st_u3", "st_only", "all", "include_only", 60, ret250_pctile_max=0.75),
            UniverseCandidate("st_u4", "st_only", "all", "include_only", 60, liquidity_floor=1_000_000.0, ret250_pctile_max=0.75),
            UniverseCandidate("st_u5", "st_only", "all", "include_only", 120, liquidity_floor=5_000_000.0, ret250_pctile_max=0.75),
            UniverseCandidate("st_u6", "st_only", "all", "include_only", 120, price_cap=20.0, liquidity_floor=5_000_000.0, ret250_pctile_max=0.60),
        ),
        anchor_recipes=("mv_revenue", "reversal_revenue"),
        event_driven_defaults={"capital": 2_000_000.0, "slippage_rate": 0.0005, "participation_cap": 0.02},
        topk_grid=(5, 10),
        rebalance_grid=(1, 5),
        recipe_seeds=("mv_revenue", "reversal_revenue", "reversal_liquidity_revenue"),
        diagnostic_rebalance_days=1,
        notes="ST 主题的 ST 身份识别必须只信 st_stocks.txt。",
    ),
    "growth": ThemeSpec(
        theme_id="growth",
        thesis="A 股成长股策略：单因子成长信号在 leakage-fix 后普遍偏弱（Phase 1 quick-kill 显示无 A/B 级），但通过(1)机构席位确认 + 多源利润增长 + 质量/动量验证 (Hyp A) 或 (2) GARP 多元复合 (Hyp B) 仍可能挖掘出可交易的成长溢价。Layer 2 用 mainboard + 市值/流动性/盈利门槛过滤，Layer 3 让 signal_search 在 8 个 Hyp A 组件 + 5 个 Hyp B 组件中搜索结构变体（equal-weight + 1core+Nconfirmation）。",
        benchmark="000905.SH",
        data_start="2014-01-01",
        universe_candidates=(
            UniverseCandidate("gr_u1", "all_market", "mainboard", "exclude", 250, 3_000_000_000, None, None, 20_000_000.0, None, False, "n_income_attr_p", True),
            UniverseCandidate("gr_u2", "all_market", "mainboard", "exclude", 250, 5_000_000_000, None, None, 30_000_000.0, None, False, "n_income_attr_p", True),
            UniverseCandidate("gr_u3", "all_market", "mainboard", "exclude", 250, 5_000_000_000, None, None, 30_000_000.0, None, False, None, False),
            UniverseCandidate("gr_u4", "all_market", "mainboard", "exclude", 250, 10_000_000_000, None, None, 50_000_000.0, None, False, "n_income_attr_p", True),
            UniverseCandidate("gr_u5", "csi500", "mainboard", "exclude", 250, None, None, None, None, None, False, "n_income_attr_p", True),
            UniverseCandidate("gr_u6", "csi300", "mainboard", "exclude", 250, None, None, None, None, None, False, "n_income_attr_p", True),
        ),
        anchor_recipes=("growth_quality_momentum", "garp_confirmation"),
        event_driven_defaults={"capital": 2_000_000.0, "slippage_rate": 0.001, "participation_cap": 0.02},
        topk_grid=(20, 50),
        rebalance_grid=(5, 10),
        recipe_seeds=("growth_quality_momentum", "garp_confirmation"),
        diagnostic_rebalance_days=10,
        notes="2026-04-22 added per growth-stock plan jolly-seeking-lollipop.md. Component weights flattened to equal at recipe-seed construction (system limitation); structural variants searched by theme_signal_search.",
    ),
    "flow_northbound": ThemeSpec(
        theme_id="flow_northbound",
        thesis="北向和内资共振并不是同一件事，这个主题要先把覆盖完整、容量足够、非 ST 的股票池定出来，再验证共振 component。",
        benchmark="000300.SH",
        data_start="2017-01-03",
        universe_candidates=(
            UniverseCandidate("fn_u1", "all_market", "mainboard", "exclude", 120, liquidity_floor=20_000_000.0),
            UniverseCandidate("fn_u2", "all_market", "mainboard", "exclude", 120, liquidity_floor=20_000_000.0, northbound_required=True),
            UniverseCandidate("fn_u3", "all_market", "mainboard", "exclude", 120, liquidity_floor=50_000_000.0, northbound_required=True),
            UniverseCandidate("fn_u4", "csi300", "all", "exclude", 120, liquidity_floor=50_000_000.0),
            UniverseCandidate("fn_u5", "csi300", "all", "exclude", 120, liquidity_floor=50_000_000.0, northbound_required=True),
            UniverseCandidate("fn_u6", "all_market", "mainboard", "exclude", 250, market_cap_min=10_000_000_000.0, liquidity_floor=50_000_000.0, northbound_required=True),
        ),
        anchor_recipes=("north_follow", "flow_follow"),
        event_driven_defaults={"capital": 2_000_000.0, "slippage_rate": 0.0005, "participation_cap": 0.02},
        topk_grid=(20, 50),
        rebalance_grid=(5, 10),
        recipe_seeds=("north_follow", "flow_follow", "flow_north_defensive"),
        diagnostic_rebalance_days=5,
        notes="北向覆盖不允许用未来数据补齐。",
    ),
}


def get_theme_spec(theme_id: str) -> ThemeSpec:
    return THEME_SPECS[theme_id]


def get_theme_specs() -> dict[str, ThemeSpec]:
    return dict(THEME_SPECS)


def get_field_definitions() -> tuple[FieldDefinition, ...]:
    return FIELD_DEFINITIONS


def get_recipe_seed(recipe_id: str) -> RecipeSeedDefinition:
    return RECIPE_SEEDS[recipe_id]


def build_seed_recipe(recipe_id: str) -> SignalRecipe:
    seed = get_recipe_seed(recipe_id)
    if not seed.component_ids:
        raise ValueError(f"Recipe seed {recipe_id} has no component ids")
    weight = 1.0 / len(seed.component_ids)
    return SignalRecipe(
        recipe_id=seed.recipe_id,
        theme_id=seed.theme_id,
        component_ids=seed.component_ids,
        weights=tuple(weight for _ in seed.component_ids),
        construction_rule="equal_weight_seed",
        selection_note=seed.selection_note,
    )
