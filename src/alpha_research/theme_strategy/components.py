from __future__ import annotations

import logging
from dataclasses import replace
from functools import lru_cache
from typing import Callable

import numpy as np
import pandas as pd

from src.alpha_research.factor_library.catalog import get_factor_catalog

from .data import coverage_tier_from_ratio, normalize_multiindex
from .registry import build_seed_recipe, get_recipe_seed
from .schema import ComponentSpec, FieldInventoryRow, SignalRecipe


LOGGER = logging.getLogger(__name__)
EPS = 1e-8


def cs_rank(series: pd.Series) -> pd.Series:
    series = normalize_multiindex(series).astype(float)
    return series.groupby(level="datetime").rank(pct=True).astype(np.float32)


def group_rolling_mean(series: pd.Series, window: int) -> pd.Series:
    return normalize_multiindex(series).groupby(level="instrument").transform(
        lambda values: values.rolling(window, min_periods=max(2, window // 2)).mean()
    )


def group_rolling_std(series: pd.Series, window: int) -> pd.Series:
    return normalize_multiindex(series).groupby(level="instrument").transform(
        lambda values: values.rolling(window, min_periods=max(2, window // 2)).std()
    )


def group_pct_change(series: pd.Series, window: int) -> pd.Series:
    return normalize_multiindex(series).groupby(level="instrument").pct_change(window)


def group_diff(series: pd.Series, window: int) -> pd.Series:
    return normalize_multiindex(series).groupby(level="instrument").diff(window)


def group_rolling_max(series: pd.Series, window: int) -> pd.Series:
    return normalize_multiindex(series).groupby(level="instrument").transform(
        lambda values: values.rolling(window, min_periods=max(2, window // 2)).max()
    )


def group_rolling_min(series: pd.Series, window: int) -> pd.Series:
    return normalize_multiindex(series).groupby(level="instrument").transform(
        lambda values: values.rolling(window, min_periods=max(2, window // 2)).min()
    )


def compute_adj_close(raw_fields: dict[str, pd.Series]) -> pd.Series:
    close = raw_fields.get("close")
    adj_factor = raw_fields.get("adj_factor")
    if close is None:
        raise KeyError("close is required for derived price features")
    if adj_factor is None:
        return close.astype(np.float32)
    return (normalize_multiindex(close) * normalize_multiindex(adj_factor)).astype(np.float32)


def compute_amount_rmb(raw_fields: dict[str, pd.Series]) -> pd.Series:
    amount = raw_fields.get("amount")
    if amount is None:
        raise KeyError("amount is required for liquidity-derived features")
    return (normalize_multiindex(amount) * 1000.0).astype(np.float32)


def compute_return_250d(raw_fields: dict[str, pd.Series]) -> pd.Series:
    adj_close = compute_adj_close(raw_fields)
    return group_pct_change(adj_close, 250).astype(np.float32)


def compute_full_market_pctile(series: pd.Series) -> pd.Series:
    return cs_rank(series).astype(np.float32)


def _make_component(
    *,
    theme_id: str,
    component_id: str,
    source_fields: tuple[str, ...],
    source_type: str,
    transform_family: str,
    transform_params: dict,
    expected_sign: int,
    economic_role: str,
    notes: str,
    inventory_map: dict[str, FieldInventoryRow],
) -> ComponentSpec:
    coverage_ratio = min(
        (inventory_map[field].coverage_ratio for field in source_fields if field in inventory_map),
        default=1.0,
    )
    return ComponentSpec(
        component_id=component_id,
        theme_id=theme_id,
        source_fields=source_fields,
        source_type=source_type,  # type: ignore[arg-type]
        transform_family=transform_family,  # type: ignore[arg-type]
        transform_params=transform_params,
        expected_sign=expected_sign,
        economic_role=economic_role,  # type: ignore[arg-type]
        coverage_tier=coverage_tier_from_ratio(float(coverage_ratio)),  # type: ignore[arg-type]
        notes=notes,
    )


def _has_fields(inventory_map: dict[str, FieldInventoryRow], *fields: str) -> bool:
    return all(field in inventory_map for field in fields)


@lru_cache(maxsize=1)
def get_factor_alias_catalog() -> dict[str, str]:
    return get_factor_catalog(include_new_data=True)


class ComponentEngine:
    def __init__(
        self,
        raw_fields: dict[str, pd.Series],
        factor_loader: Callable[[str], pd.Series] | None = None,
    ):
        self.raw_fields = {
            name: normalize_multiindex(series).astype(np.float32)
            for name, series in raw_fields.items()
        }
        self.factor_loader = factor_loader
        self._series_cache: dict[str, pd.Series] = {}

    def get_series(self, spec: ComponentSpec) -> pd.Series:
        if spec.component_id in self._series_cache:
            return self._series_cache[spec.component_id]
        if spec.source_type == "factor_alias":
            if self.factor_loader is None:
                raise ValueError(f"factor_loader is required for factor alias {spec.component_id}")
            alias_name = spec.transform_params["factor_name"]
            series = normalize_multiindex(self.factor_loader(alias_name)).astype(np.float32)
        else:
            series = self._compute_field_transform(spec).astype(np.float32)
        self._series_cache[spec.component_id] = series.rename(spec.component_id)
        return self._series_cache[spec.component_id]

    def _compute_field_transform(self, spec: ComponentSpec) -> pd.Series:
        params = dict(spec.transform_params)
        family = spec.transform_family
        if family == "level_rank":
            return self._compute_level_feature(spec.source_fields[0], params)
        if family == "change":
            return self._compute_change_feature(spec.source_fields, params)
        if family == "acceleration":
            return self._compute_acceleration_feature(spec.source_fields, params)
        if family == "stability":
            return self._compute_stability_feature(spec.source_fields, params)
        if family == "relative_position":
            return self._compute_relative_position_feature(spec.source_fields, params)
        if family == "ratio_spread":
            return self._compute_ratio_spread_feature(spec.source_fields, params)
        if family == "persistence":
            return self._compute_persistence_feature(spec.source_fields, params)
        if family == "interaction":
            return self._compute_interaction_feature(spec.source_fields, params)
        raise NotImplementedError(f"Unsupported transform family: {family}")

    def _field(self, field_name: str) -> pd.Series:
        if field_name not in self.raw_fields:
            raise KeyError(f"Missing raw field: {field_name}")
        return self.raw_fields[field_name]

    def _compute_level_feature(self, field_name: str, params: dict) -> pd.Series:
        mode = params.get("mode", "direct")
        series = self._field(field_name).astype(float)
        if mode == "direct":
            return series
        if mode == "log":
            return np.log(series.clip(lower=EPS))
        if mode == "inverse":
            return 1.0 / series.replace(0.0, np.nan)
        if mode == "adv20":
            return group_rolling_mean(compute_amount_rmb(self.raw_fields), 20)
        raise NotImplementedError(f"Unsupported level mode: {mode}")

    def _compute_change_feature(self, source_fields: tuple[str, ...], params: dict) -> pd.Series:
        mode = params.get("mode")
        window = int(params.get("window", 1))
        if mode == "pct_change":
            base = compute_adj_close(self.raw_fields) if source_fields[0] == "close" else self._field(source_fields[0])
            return group_pct_change(base, window)
        if mode == "diff":
            return group_diff(self._field(source_fields[0]), window)
        if mode == "rolling_mean":
            base = compute_amount_rmb(self.raw_fields) if source_fields[0] == "amount" else self._field(source_fields[0])
            return group_rolling_mean(base, window)
        raise NotImplementedError(f"Unsupported change mode: {mode}")

    def _compute_acceleration_feature(self, source_fields: tuple[str, ...], params: dict) -> pd.Series:
        mode = params.get("mode")
        short_window = int(params.get("short_window", 5))
        long_window = int(params.get("long_window", 20))
        base = compute_amount_rmb(self.raw_fields) if source_fields[0] == "amount" else self._field(source_fields[0])
        if mode == "rolling_mean_diff":
            return group_rolling_mean(base, short_window) - group_rolling_mean(base, long_window)
        if mode == "diff_of_diff":
            diff_short = group_diff(base, short_window)
            diff_long = group_diff(base, long_window)
            return diff_short - diff_long
        raise NotImplementedError(f"Unsupported acceleration mode: {mode}")

    def _compute_stability_feature(self, source_fields: tuple[str, ...], params: dict) -> pd.Series:
        mode = params.get("mode")
        window = int(params.get("window", 20))
        if mode == "rolling_vol":
            adj_close = compute_adj_close(self.raw_fields)
            returns = adj_close.groupby(level="instrument").pct_change().astype(float)
            return group_rolling_std(returns, window)
        raise NotImplementedError(f"Unsupported stability mode: {mode}")

    def _compute_relative_position_feature(self, source_fields: tuple[str, ...], params: dict) -> pd.Series:
        mode = params.get("mode")
        if mode == "full_market_return_pctile":
            return compute_full_market_pctile(compute_return_250d(self.raw_fields))
        base = compute_adj_close(self.raw_fields) if source_fields[0] == "close" else self._field(source_fields[0])
        window = int(params.get("window", 20))
        if mode == "distance_to_high":
            return base / group_rolling_max(base, window) - 1.0
        if mode == "distance_to_low":
            return base / group_rolling_min(base, window) - 1.0
        if mode == "distance_to_limit":
            reference = self._field(params["reference"])
            return (reference - self._field("close")) / self._field("close").replace(0.0, np.nan)
        if mode == "price_to_ma":
            return base / group_rolling_mean(base, window) - 1.0
        raise NotImplementedError(f"Unsupported relative-position mode: {mode}")

    def _compute_ratio_spread_feature(self, source_fields: tuple[str, ...], params: dict) -> pd.Series:
        mode = params.get("mode")
        if mode == "midpoint":
            return (self._field(source_fields[0]) + self._field(source_fields[1])) / 2.0
        if mode == "ratio":
            return self._field(source_fields[0]) / self._field(source_fields[1]).replace(0.0, np.nan)
        if mode == "margin_net_buy_mean":
            return group_rolling_mean(self._field(source_fields[0]) - self._field(source_fields[1]), int(params.get("window", 20)))
        if mode == "large_small_ratio":
            lg = self._field(source_fields[0]) - self._field(source_fields[1])
            sm = self._field(source_fields[2]) - self._field(source_fields[3])
            return group_rolling_mean(lg, int(params.get("window", 20))) / group_rolling_mean(sm, int(params.get("window", 20))).abs().replace(0.0, np.nan)
        if mode == "large_net_pct":
            lg = self._field(source_fields[0]) - self._field(source_fields[1])
            amount = compute_amount_rmb(self.raw_fields)
            return group_rolling_mean(lg, int(params.get("window", 20))) / group_rolling_mean(amount, int(params.get("window", 20))).replace(0.0, np.nan)
        raise NotImplementedError(f"Unsupported ratio-spread mode: {mode}")

    def _compute_persistence_feature(self, source_fields: tuple[str, ...], params: dict) -> pd.Series:
        mode = params.get("mode")
        if mode == "delta_sum":
            base = self._field(source_fields[0])
            delta = group_diff(base, 1)
            return delta.groupby(level="instrument").transform(
                lambda values: values.rolling(int(params.get("window", 20)), min_periods=max(2, int(params.get("window", 20)) // 2)).sum()
            )
        raise NotImplementedError(f"Unsupported persistence mode: {mode}")

    def _compute_interaction_feature(self, source_fields: tuple[str, ...], params: dict) -> pd.Series:
        mode = params.get("mode")
        if mode == "north_flow_resonance":
            north = group_diff(self._field(source_fields[0]), int(params.get("north_window", 5)))
            flow = group_rolling_mean(self._field(source_fields[1]), int(params.get("flow_window", 20)))
            return cs_rank(north) + cs_rank(flow)
        raise NotImplementedError(f"Unsupported interaction mode: {mode}")


def generate_component_specs(theme_id: str, field_inventory: list[FieldInventoryRow]) -> list[ComponentSpec]:
    inventory_map = {row.field_name: row for row in field_inventory}
    specs: list[ComponentSpec] = []
    add = specs.append

    if theme_id == "small_cap":
        if _has_fields(inventory_map, "total_mv"):
            add(_make_component(theme_id=theme_id, component_id="small_cap_total_mv_small_rank", source_fields=("total_mv",), source_type="field_transform", transform_family="level_rank", transform_params={"mode": "direct"}, expected_sign=-1, economic_role="core_thesis", notes="小市值核心暴露，以总市值越小越好。", inventory_map=inventory_map))
            add(_make_component(theme_id=theme_id, component_id="small_cap_total_mv_log_small_rank", source_fields=("total_mv",), source_type="field_transform", transform_family="level_rank", transform_params={"mode": "log"}, expected_sign=-1, economic_role="confirmation", notes="对数规模，降低极端值干扰。", inventory_map=inventory_map))
        if _has_fields(inventory_map, "circ_mv"):
            add(_make_component(theme_id=theme_id, component_id="small_cap_circ_mv_small_rank", source_fields=("circ_mv",), source_type="field_transform", transform_family="level_rank", transform_params={"mode": "direct"}, expected_sign=-1, economic_role="confirmation", notes="流通市值越小越好。", inventory_map=inventory_map))
        if _has_fields(inventory_map, "free_share"):
            add(_make_component(theme_id=theme_id, component_id="small_cap_free_share_small_rank", source_fields=("free_share",), source_type="field_transform", transform_family="level_rank", transform_params={"mode": "log"}, expected_sign=-1, economic_role="confirmation", notes="自由流通股本越小越好。", inventory_map=inventory_map))
        if _has_fields(inventory_map, "pb"):
            add(_make_component(theme_id=theme_id, component_id="small_cap_pb_value_rank", source_fields=("pb",), source_type="field_transform", transform_family="level_rank", transform_params={"mode": "inverse"}, expected_sign=1, economic_role="confirmation", notes="PB 越低越有安全边际。", inventory_map=inventory_map))
        if _has_fields(inventory_map, "pe_ttm"):
            add(_make_component(theme_id=theme_id, component_id="small_cap_pe_value_rank", source_fields=("pe_ttm",), source_type="field_transform", transform_family="level_rank", transform_params={"mode": "inverse"}, expected_sign=1, economic_role="confirmation", notes="PE 越低越偏价值。", inventory_map=inventory_map))
        if _has_fields(inventory_map, "ps_ttm"):
            add(_make_component(theme_id=theme_id, component_id="small_cap_ps_value_rank", source_fields=("ps_ttm",), source_type="field_transform", transform_family="level_rank", transform_params={"mode": "inverse"}, expected_sign=1, economic_role="diagnostic_only", notes="PS 越低越偏价值。", inventory_map=inventory_map))
        if _has_fields(inventory_map, "dv_ttm"):
            add(_make_component(theme_id=theme_id, component_id="small_cap_dividend_rank", source_fields=("dv_ttm",), source_type="field_transform", transform_family="level_rank", transform_params={"mode": "direct"}, expected_sign=1, economic_role="confirmation", notes="股息率越高越好。", inventory_map=inventory_map))
        for field_name, component_id, note in (
            ("roe", "small_cap_roe_rank", "ROE 越高越好。"),
            ("roa", "small_cap_roa_rank", "ROA 越高越好。"),
            ("roic", "small_cap_roic_rank", "ROIC 越高越好。"),
            ("grossprofit_margin", "small_cap_gross_margin_rank", "毛利率越高越好。"),
            ("netprofit_margin", "small_cap_net_margin_rank", "净利率越高越好。"),
        ):
            if _has_fields(inventory_map, field_name):
                add(_make_component(theme_id=theme_id, component_id=component_id, source_fields=(field_name,), source_type="raw_field", transform_family="level_rank", transform_params={"mode": "direct"}, expected_sign=1, economic_role="confirmation", notes=note, inventory_map=inventory_map))
        if _has_fields(inventory_map, "debt_to_assets"):
            add(_make_component(theme_id=theme_id, component_id="small_cap_low_debt_rank", source_fields=("debt_to_assets",), source_type="field_transform", transform_family="level_rank", transform_params={"mode": "direct"}, expected_sign=-1, economic_role="confirmation", notes="资产负债率越低越稳。", inventory_map=inventory_map))
        if _has_fields(inventory_map, "current_ratio"):
            add(_make_component(theme_id=theme_id, component_id="small_cap_current_ratio_rank", source_fields=("current_ratio",), source_type="raw_field", transform_family="level_rank", transform_params={"mode": "direct"}, expected_sign=1, economic_role="confirmation", notes="流动比率越高越稳。", inventory_map=inventory_map))
        if _has_fields(inventory_map, "quick_ratio"):
            add(_make_component(theme_id=theme_id, component_id="small_cap_quick_ratio_rank", source_fields=("quick_ratio",), source_type="raw_field", transform_family="level_rank", transform_params={"mode": "direct"}, expected_sign=1, economic_role="confirmation", notes="速动比率越高越稳。", inventory_map=inventory_map))
        for field_name, component_id, note in (
            ("pit_q_sales_yoy", "small_cap_pit_sales_yoy_rank", "营收改善越强越好。"),
            ("pit_netprofit_yoy", "small_cap_pit_netprofit_yoy_rank", "利润改善越强越好。"),
            ("pit_basic_eps_yoy", "small_cap_pit_eps_yoy_rank", "EPS 改善越强越好。"),
            ("pit_ocf_yoy", "small_cap_pit_ocf_yoy_rank", "现金流改善越强越好。"),
        ):
            if _has_fields(inventory_map, field_name):
                add(_make_component(theme_id=theme_id, component_id=component_id, source_fields=(field_name,), source_type="raw_field", transform_family="level_rank", transform_params={"mode": "direct"}, expected_sign=1, economic_role="confirmation", notes=note, inventory_map=inventory_map))
        if _has_fields(inventory_map, "amount"):
            add(_make_component(theme_id=theme_id, component_id="small_cap_adv20_rank", source_fields=("amount",), source_type="field_transform", transform_family="level_rank", transform_params={"mode": "adv20"}, expected_sign=1, economic_role="execution_guardrail", notes="20 日成交额足够，便于真实执行。", inventory_map=inventory_map))
        if _has_fields(inventory_map, "close", "adj_factor"):
            add(_make_component(theme_id=theme_id, component_id="small_cap_low_vol_20d", source_fields=("close", "adj_factor"), source_type="field_transform", transform_family="stability", transform_params={"mode": "rolling_vol", "window": 20}, expected_sign=-1, economic_role="execution_guardrail", notes="20 日波动越低越利于持有。", inventory_map=inventory_map))
        if _has_fields(inventory_map, "turnover_rate"):
            add(_make_component(theme_id=theme_id, component_id="small_cap_turnover_20d_rank", source_fields=("turnover_rate",), source_type="field_transform", transform_family="change", transform_params={"mode": "rolling_mean", "window": 20}, expected_sign=1, economic_role="execution_guardrail", notes="20 日换手更友好。", inventory_map=inventory_map))

    if theme_id == "st":
        if _has_fields(inventory_map, "total_mv"):
            add(_make_component(theme_id=theme_id, component_id="st_total_mv_small_rank", source_fields=("total_mv",), source_type="field_transform", transform_family="level_rank", transform_params={"mode": "direct"}, expected_sign=-1, economic_role="core_thesis", notes="ST 中偏小市值更容易有修复弹性。", inventory_map=inventory_map))
        if _has_fields(inventory_map, "close", "adj_factor"):
            add(_make_component(theme_id=theme_id, component_id="st_return_250d_deep_pctile", source_fields=("close", "adj_factor"), source_type="field_transform", transform_family="relative_position", transform_params={"mode": "full_market_return_pctile", "window": 250}, expected_sign=-1, economic_role="core_thesis", notes="先在全市场算 250 日收益分位，再判断 ST 是否跌深。", inventory_map=inventory_map))
            add(_make_component(theme_id=theme_id, component_id="st_short_reversal_5d", source_fields=("close", "adj_factor"), source_type="field_transform", transform_family="change", transform_params={"mode": "pct_change", "window": 5}, expected_sign=-1, economic_role="core_thesis", notes="短期跌得越急，越容易出现反身性反弹。", inventory_map=inventory_map))
            add(_make_component(theme_id=theme_id, component_id="st_close_to_low_60d", source_fields=("close", "adj_factor"), source_type="field_transform", transform_family="relative_position", transform_params={"mode": "distance_to_low", "window": 60}, expected_sign=-1, economic_role="confirmation", notes="越接近 60 日低点，越偏超跌。", inventory_map=inventory_map))
            add(_make_component(theme_id=theme_id, component_id="st_close_to_high_120d", source_fields=("close", "adj_factor"), source_type="field_transform", transform_family="relative_position", transform_params={"mode": "distance_to_high", "window": 120}, expected_sign=-1, economic_role="diagnostic_only", notes="离中期高点越远，困境越深。", inventory_map=inventory_map))
        if _has_fields(inventory_map, "close", "up_limit"):
            add(_make_component(theme_id=theme_id, component_id="st_distance_to_up_limit", source_fields=("close", "up_limit"), source_type="field_transform", transform_family="relative_position", transform_params={"mode": "distance_to_limit", "reference": "up_limit"}, expected_sign=-1, economic_role="diagnostic_only", notes="离涨停越近，情绪越强。", inventory_map=inventory_map))
        if _has_fields(inventory_map, "close", "down_limit"):
            add(_make_component(theme_id=theme_id, component_id="st_distance_to_down_limit", source_fields=("close", "down_limit"), source_type="field_transform", transform_family="relative_position", transform_params={"mode": "distance_to_limit", "reference": "down_limit"}, expected_sign=1, economic_role="execution_guardrail", notes="离跌停更远，执行风险更低。", inventory_map=inventory_map))
        if _has_fields(inventory_map, "amount"):
            add(_make_component(theme_id=theme_id, component_id="st_amount_surge_5_20", source_fields=("amount",), source_type="field_transform", transform_family="acceleration", transform_params={"mode": "rolling_mean_diff", "short_window": 5, "long_window": 20}, expected_sign=1, economic_role="confirmation", notes="成交额突然放大常见于困境交易启动。", inventory_map=inventory_map))
            add(_make_component(theme_id=theme_id, component_id="st_adv20_rank", source_fields=("amount",), source_type="field_transform", transform_family="level_rank", transform_params={"mode": "adv20"}, expected_sign=1, economic_role="execution_guardrail", notes="20 日成交额越高越容易真实成交。", inventory_map=inventory_map))
        if _has_fields(inventory_map, "turnover_rate"):
            add(_make_component(theme_id=theme_id, component_id="st_turnover_surge_5_20", source_fields=("turnover_rate",), source_type="field_transform", transform_family="acceleration", transform_params={"mode": "rolling_mean_diff", "short_window": 5, "long_window": 20}, expected_sign=1, economic_role="confirmation", notes="换手抬升说明博弈升温。", inventory_map=inventory_map))
            add(_make_component(theme_id=theme_id, component_id="st_turnover_20d_rank", source_fields=("turnover_rate",), source_type="field_transform", transform_family="change", transform_params={"mode": "rolling_mean", "window": 20}, expected_sign=1, economic_role="execution_guardrail", notes="20 日平均换手越高越易执行。", inventory_map=inventory_map))
        for field_name, component_id, note in (
            ("revenue_q", "st_revenue_q_rank", "单季度营收越高，修复可信度越高。"),
            ("core_profit_q", "st_core_profit_q_rank", "单季度核心利润越高越好。"),
            ("pit_q_sales_yoy", "st_pit_sales_yoy_rank", "单季度营收同比改善越强越好。"),
            ("pit_q_op_qoq", "st_pit_q_op_qoq_rank", "单季度经营利润环比改善越强越好。"),
            ("pit_netprofit_yoy", "st_pit_netprofit_yoy_rank", "利润同比改善越强越好。"),
            ("pit_basic_eps_yoy", "st_pit_basic_eps_yoy_rank", "EPS 同比改善越强越好。"),
        ):
            if _has_fields(inventory_map, field_name):
                add(_make_component(theme_id=theme_id, component_id=component_id, source_fields=(field_name,), source_type="raw_field", transform_family="level_rank", transform_params={"mode": "direct"}, expected_sign=1, economic_role="confirmation", notes=note, inventory_map=inventory_map))
        if _has_fields(inventory_map, "p_change_min", "p_change_max"):
            add(_make_component(theme_id=theme_id, component_id="st_forecast_mid_change_rank", source_fields=("p_change_min", "p_change_max"), source_type="field_transform", transform_family="ratio_spread", transform_params={"mode": "midpoint"}, expected_sign=1, economic_role="confirmation", notes="业绩预告改善越大越好。", inventory_map=inventory_map))
        if _has_fields(inventory_map, "holder_num"):
            add(_make_component(theme_id=theme_id, component_id="st_holder_num_change_rank", source_fields=("holder_num",), source_type="field_transform", transform_family="change", transform_params={"mode": "pct_change", "window": 20}, expected_sign=-1, economic_role="diagnostic_only", notes="股东户数下降常代表筹码集中。", inventory_map=inventory_map))
        if _has_fields(inventory_map, "net_mf_amount"):
            add(_make_component(theme_id=theme_id, component_id="st_net_mf_amount_5d", source_fields=("net_mf_amount",), source_type="field_transform", transform_family="change", transform_params={"mode": "rolling_mean", "window": 5}, expected_sign=1, economic_role="confirmation", notes="净流入抬升常伴随情绪修复。", inventory_map=inventory_map))
        if _has_fields(inventory_map, "rzmre", "rzche"):
            add(_make_component(theme_id=theme_id, component_id="st_margin_net_buy_20d", source_fields=("rzmre", "rzche"), source_type="field_transform", transform_family="ratio_spread", transform_params={"mode": "margin_net_buy_mean", "window": 20}, expected_sign=1, economic_role="diagnostic_only", notes="融资净买入升温代表拥挤度上升。", inventory_map=inventory_map))

    if theme_id == "flow_northbound":
        if _has_fields(inventory_map, "ratio"):
            add(_make_component(theme_id=theme_id, component_id="flow_northbound_hold_pct", source_fields=("ratio",), source_type="raw_field", transform_family="level_rank", transform_params={"mode": "direct"}, expected_sign=1, economic_role="confirmation", notes="北向持股占比越高越好。", inventory_map=inventory_map))
            add(_make_component(theme_id=theme_id, component_id="flow_northbound_hold_change_5d", source_fields=("ratio",), source_type="field_transform", transform_family="change", transform_params={"mode": "diff", "window": 5}, expected_sign=1, economic_role="core_thesis", notes="5 日北向增持越强越好。", inventory_map=inventory_map))
            add(_make_component(theme_id=theme_id, component_id="flow_northbound_hold_change_20d", source_fields=("ratio",), source_type="field_transform", transform_family="change", transform_params={"mode": "diff", "window": 20}, expected_sign=1, economic_role="confirmation", notes="20 日北向增持越强越好。", inventory_map=inventory_map))
            add(_make_component(theme_id=theme_id, component_id="flow_northbound_accumulation_20d", source_fields=("ratio",), source_type="field_transform", transform_family="persistence", transform_params={"mode": "delta_sum", "window": 20}, expected_sign=1, economic_role="core_thesis", notes="20 日累计增持越强越好。", inventory_map=inventory_map))
            add(_make_component(theme_id=theme_id, component_id="flow_northbound_ratio_accel_5_20", source_fields=("ratio",), source_type="field_transform", transform_family="acceleration", transform_params={"mode": "diff_of_diff", "short_window": 5, "long_window": 20}, expected_sign=1, economic_role="confirmation", notes="北向增持加速度越高越好。", inventory_map=inventory_map))
        if _has_fields(inventory_map, "net_mf_amount"):
            add(_make_component(theme_id=theme_id, component_id="flow_northbound_net_inflow_5d", source_fields=("net_mf_amount",), source_type="field_transform", transform_family="change", transform_params={"mode": "rolling_mean", "window": 5}, expected_sign=1, economic_role="confirmation", notes="5 日净流入越强越好。", inventory_map=inventory_map))
            add(_make_component(theme_id=theme_id, component_id="flow_northbound_net_inflow_20d", source_fields=("net_mf_amount",), source_type="field_transform", transform_family="change", transform_params={"mode": "rolling_mean", "window": 20}, expected_sign=1, economic_role="core_thesis", notes="20 日净流入越强越好。", inventory_map=inventory_map))
        if _has_fields(inventory_map, "buy_lg_amount", "sell_lg_amount", "buy_sm_amount", "sell_sm_amount"):
            add(_make_component(theme_id=theme_id, component_id="flow_northbound_large_small_ratio", source_fields=("buy_lg_amount", "sell_lg_amount", "buy_sm_amount", "sell_sm_amount"), source_type="field_transform", transform_family="ratio_spread", transform_params={"mode": "large_small_ratio", "window": 20}, expected_sign=1, economic_role="core_thesis", notes="大单相对小单更强说明主力主导。", inventory_map=inventory_map))
        if _has_fields(inventory_map, "buy_lg_amount", "sell_lg_amount", "amount"):
            add(_make_component(theme_id=theme_id, component_id="flow_northbound_large_net_pct_20d", source_fields=("buy_lg_amount", "sell_lg_amount", "amount"), source_type="field_transform", transform_family="ratio_spread", transform_params={"mode": "large_net_pct", "window": 20}, expected_sign=1, economic_role="confirmation", notes="大单净流入占成交额比例越高越好。", inventory_map=inventory_map))
        if _has_fields(inventory_map, "ratio", "net_mf_amount"):
            add(_make_component(theme_id=theme_id, component_id="flow_northbound_resonance_5_20", source_fields=("ratio", "net_mf_amount"), source_type="field_transform", transform_family="interaction", transform_params={"mode": "north_flow_resonance", "north_window": 5, "flow_window": 20}, expected_sign=1, economic_role="confirmation", notes="北向与内资同向共振。", inventory_map=inventory_map))
        if _has_fields(inventory_map, "rzye", "circ_mv"):
            add(_make_component(theme_id=theme_id, component_id="flow_northbound_margin_balance_pct", source_fields=("rzye", "circ_mv"), source_type="field_transform", transform_family="ratio_spread", transform_params={"mode": "ratio"}, expected_sign=1, economic_role="diagnostic_only", notes="融资余额占流通市值越高，内资杠杆更活跃。", inventory_map=inventory_map))
        if _has_fields(inventory_map, "rzmre", "rzche"):
            add(_make_component(theme_id=theme_id, component_id="flow_northbound_margin_net_buy_20d", source_fields=("rzmre", "rzche"), source_type="field_transform", transform_family="ratio_spread", transform_params={"mode": "margin_net_buy_mean", "window": 20}, expected_sign=1, economic_role="diagnostic_only", notes="融资净买入越强，内资追涨越明显。", inventory_map=inventory_map))
        if _has_fields(inventory_map, "rqye"):
            add(_make_component(theme_id=theme_id, component_id="flow_northbound_short_pressure_change", source_fields=("rqye",), source_type="field_transform", transform_family="change", transform_params={"mode": "diff", "window": 20}, expected_sign=-1, economic_role="execution_guardrail", notes="融券压力下降更有利。", inventory_map=inventory_map))
        if _has_fields(inventory_map, "close", "adj_factor"):
            add(_make_component(theme_id=theme_id, component_id="flow_northbound_low_vol_20d", source_fields=("close", "adj_factor"), source_type="field_transform", transform_family="stability", transform_params={"mode": "rolling_vol", "window": 20}, expected_sign=-1, economic_role="execution_guardrail", notes="低波动更适合承接北向流。", inventory_map=inventory_map))
            add(_make_component(theme_id=theme_id, component_id="flow_northbound_price_to_ma20", source_fields=("close", "adj_factor"), source_type="field_transform", transform_family="relative_position", transform_params={"mode": "price_to_ma", "window": 20}, expected_sign=1, economic_role="confirmation", notes="价格站上 20 日均线更能确认趋势。", inventory_map=inventory_map))
            add(_make_component(theme_id=theme_id, component_id="flow_northbound_close_to_high_20d", source_fields=("close", "adj_factor"), source_type="field_transform", transform_family="relative_position", transform_params={"mode": "distance_to_high", "window": 20}, expected_sign=-1, economic_role="diagnostic_only", notes="离 20 日高点越近，价格确认越充分。", inventory_map=inventory_map))
        if _has_fields(inventory_map, "amount"):
            add(_make_component(theme_id=theme_id, component_id="flow_northbound_adv20_rank", source_fields=("amount",), source_type="field_transform", transform_family="level_rank", transform_params={"mode": "adv20"}, expected_sign=1, economic_role="execution_guardrail", notes="容量足够才适合跟随北向资金。", inventory_map=inventory_map))

    if theme_id == "growth":
        # 2026-04-22: components map to FieldDefinitions whose qlib_expression
        # IS the full Phase-1-survivor factor expression. ComponentSpec uses
        # raw_field/level_rank/direct because the factor value is already
        # baked into the field. Roles are tagged so signal_search can build
        # 1core+Nconfirmation structural variants.
        # Hypothesis A core_thesis: top-2 by Phase 1 LS Sharpe.
        if _has_fields(inventory_map, "g_alpha_inst_net_buy_20d"):
            add(_make_component(theme_id=theme_id, component_id="growth_alpha_inst_net_buy_20d", source_fields=("g_alpha_inst_net_buy_20d",), source_type="raw_field", transform_family="level_rank", transform_params={"mode": "direct"}, expected_sign=1, economic_role="core_thesis", notes="20-day net institutional buy on 龙虎榜 days. Phase 1 LS Sharpe +3.23 (sparse coverage caveat).", inventory_map=inventory_map))
        if _has_fields(inventory_map, "g_grow_roe_yoy"):
            add(_make_component(theme_id=theme_id, component_id="growth_grow_roe_yoy", source_fields=("g_grow_roe_yoy",), source_type="raw_field", transform_family="level_rank", transform_params={"mode": "direct"}, expected_sign=1, economic_role="core_thesis", notes="ROE YoY growth — Phase 1 LS Sharpe +1.89, highest among growth fundamentals.", inventory_map=inventory_map))
        # Hypothesis A confirmation: positive-Sharpe growth fundamentals + quality + momentum.
        if _has_fields(inventory_map, "g_grow_netprofit_yoy"):
            add(_make_component(theme_id=theme_id, component_id="growth_grow_netprofit_yoy", source_fields=("g_grow_netprofit_yoy",), source_type="raw_field", transform_family="level_rank", transform_params={"mode": "direct"}, expected_sign=1, economic_role="core_thesis", notes="Net profit YoY growth — Phase 1 LS Sharpe +1.43. Also Hypothesis B core component.", inventory_map=inventory_map))
        if _has_fields(inventory_map, "g_grow_opprofit_yoy"):
            add(_make_component(theme_id=theme_id, component_id="growth_grow_opprofit_yoy", source_fields=("g_grow_opprofit_yoy",), source_type="raw_field", transform_family="level_rank", transform_params={"mode": "direct"}, expected_sign=1, economic_role="confirmation", notes="Operating profit YoY — Phase 1 LS Sharpe +1.58.", inventory_map=inventory_map))
        if _has_fields(inventory_map, "g_grow_eps_yoy"):
            add(_make_component(theme_id=theme_id, component_id="growth_grow_eps_yoy", source_fields=("g_grow_eps_yoy",), source_type="raw_field", transform_family="level_rank", transform_params={"mode": "direct"}, expected_sign=1, economic_role="confirmation", notes="EPS YoY — Phase 1 LS Sharpe +1.51.", inventory_map=inventory_map))
        if _has_fields(inventory_map, "g_grow_opprofit_qoq"):
            add(_make_component(theme_id=theme_id, component_id="growth_grow_opprofit_qoq", source_fields=("g_grow_opprofit_qoq",), source_type="raw_field", transform_family="level_rank", transform_params={"mode": "direct"}, expected_sign=1, economic_role="confirmation", notes="Quarterly operating profit QoQ — Phase 1 LS Sharpe +1.43.", inventory_map=inventory_map))
        if _has_fields(inventory_map, "g_qual_roe_stability"):
            add(_make_component(theme_id=theme_id, component_id="growth_qual_roe_stability", source_fields=("g_qual_roe_stability",), source_type="raw_field", transform_family="level_rank", transform_params={"mode": "direct"}, expected_sign=1, economic_role="confirmation", notes="ROE stability (negative 60d Std). Quality confirmation that growth is durable.", inventory_map=inventory_map))
        if _has_fields(inventory_map, "g_mom_return_60d"):
            add(_make_component(theme_id=theme_id, component_id="growth_mom_return_60d", source_fields=("g_mom_return_60d",), source_type="raw_field", transform_family="level_rank", transform_params={"mode": "direct"}, expected_sign=1, economic_role="confirmation", notes="60-day price momentum confirmation that fundamental story is being priced.", inventory_map=inventory_map))
        # Hypothesis B GARP-specific components (some shared with A).
        if _has_fields(inventory_map, "g_grow_rev_trend"):
            add(_make_component(theme_id=theme_id, component_id="growth_grow_rev_trend", source_fields=("g_grow_rev_trend",), source_type="raw_field", transform_family="level_rank", transform_params={"mode": "direct"}, expected_sign=1, economic_role="confirmation", notes="4-quarter revenue YoY trend slope. Phase 1 LS Sharpe -0.84 — kept as confirmation per Hyp B intent (growth persistence).", inventory_map=inventory_map))
        if _has_fields(inventory_map, "g_val_ep_ttm"):
            add(_make_component(theme_id=theme_id, component_id="growth_val_ep_ttm", source_fields=("g_val_ep_ttm",), source_type="raw_field", transform_family="level_rank", transform_params={"mode": "direct"}, expected_sign=1, economic_role="core_thesis", notes="Earnings yield (1/PE_TTM) — anchors GARP value leg.", inventory_map=inventory_map))
        if _has_fields(inventory_map, "g_qual_roe"):
            add(_make_component(theme_id=theme_id, component_id="growth_qual_roe", source_fields=("g_qual_roe",), source_type="raw_field", transform_family="level_rank", transform_params={"mode": "direct"}, expected_sign=1, economic_role="core_thesis", notes="ROE level — anchors GARP quality leg.", inventory_map=inventory_map))
        if _has_fields(inventory_map, "g_qual_margin_trend"):
            add(_make_component(theme_id=theme_id, component_id="growth_qual_margin_trend", source_fields=("g_qual_margin_trend",), source_type="raw_field", transform_family="level_rank", transform_params={"mode": "direct"}, expected_sign=1, economic_role="confirmation", notes="4-quarter gross-margin trend slope.", inventory_map=inventory_map))
        # Execution guardrail (universal to both hypotheses).
        if _has_fields(inventory_map, "g_amount_adv20"):
            add(_make_component(theme_id=theme_id, component_id="growth_adv20_rank", source_fields=("g_amount_adv20",), source_type="raw_field", transform_family="level_rank", transform_params={"mode": "direct"}, expected_sign=1, economic_role="execution_guardrail", notes="20-day average daily turnover — only trade names with sufficient liquidity.", inventory_map=inventory_map))

    specs.sort(key=lambda item: item.component_id)
    return specs


def build_seed_recipes_for_theme(theme_id: str, component_ids: set[str]) -> list[SignalRecipe]:
    recipes: list[SignalRecipe] = []
    for recipe_id in (
        "size_only",
        "small_value",
        "small_quality_lowvol",
        "mv_revenue",
        "reversal_revenue",
        "reversal_liquidity_revenue",
        "north_follow",
        "flow_follow",
        "flow_north_defensive",
        "growth_quality_momentum",
        "garp_confirmation",
    ):
        try:
            seed = get_recipe_seed(recipe_id)
        except KeyError:
            continue
        if seed.theme_id != theme_id:
            continue
        if all(component_id in component_ids for component_id in seed.component_ids):
            recipes.append(build_seed_recipe(recipe_id))
    return recipes


def rank_component_within_universe(
    component_series: pd.Series,
    eligible_map: dict[pd.Timestamp, set[str]],
    expected_sign: int,
) -> pd.Series:
    rows: list[pd.Series] = []
    oriented = component_series * float(expected_sign)
    for date, codes in eligible_map.items():
        if not codes:
            continue
        try:
            daily = oriented.xs(date, level="datetime").reindex(sorted(codes))
        except KeyError:
            continue
        daily = daily.dropna()
        if daily.empty:
            continue
        ranked = daily.rank(pct=True).astype(np.float32)
        ranked.index = pd.MultiIndex.from_product([[pd.Timestamp(date)], ranked.index], names=["datetime", "instrument"])
        rows.append(ranked)
    if not rows:
        empty_index = pd.MultiIndex.from_arrays([[], []], names=["datetime", "instrument"])
        return pd.Series(dtype=np.float32, index=empty_index)
    return pd.concat(rows).sort_index()


def enrich_component_coverage(
    specs: list[ComponentSpec],
    actual_coverage: dict[str, float],
) -> list[ComponentSpec]:
    enriched: list[ComponentSpec] = []
    for spec in specs:
        coverage_ratio = actual_coverage.get(spec.component_id)
        if coverage_ratio is None:
            enriched.append(spec)
            continue
        enriched.append(
            replace(
                spec,
                coverage_tier=coverage_tier_from_ratio(float(coverage_ratio)),  # type: ignore[arg-type]
            )
        )
    return enriched
