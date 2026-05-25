from __future__ import annotations

import itertools
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.alpha_research.walk_forward import (
    FoldSpec,
    HoldoutSpec,
    STEP_YEARS as WALK_FORWARD_STEP_YEARS,
    TEST_YEARS as WALK_FORWARD_TEST_YEARS,
    TRAIN_YEARS as WALK_FORWARD_TRAIN_YEARS,
    VALIDATION_YEARS as WALK_FORWARD_VALIDATION_YEARS,
    build_walk_forward_folds as shared_build_walk_forward_folds,
)
from src.alpha_research.factor_eval import compute_factor_correlation, compute_ic_series, compute_ic_summary, compute_marginal_ic
from src.result_analysis.metrics import (
    calculate_max_drawdown,
    calculate_monthly_return_table,
    calculate_total_return,
    calculate_yearly_returns,
    generate_performance_report,
)

from .components import ComponentEngine, build_seed_recipes_for_theme, generate_component_specs, rank_component_within_universe
from .data import QlibFieldProvider, ResearchSupport, build_support, is_st_on_date
from .registry import get_field_definitions, get_theme_spec, get_theme_specs
from .schema import ComponentDiagnostic, ComponentSpec, FieldInventoryRow, SignalRecipe, ThemeSpec, UniverseCandidate, VariantSummary


LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
TRAIN_YEARS = WALK_FORWARD_TRAIN_YEARS
VALIDATION_YEARS = WALK_FORWARD_VALIDATION_YEARS
TEST_YEARS = WALK_FORWARD_TEST_YEARS
STEP_YEARS = WALK_FORWARD_STEP_YEARS
COMPONENT_CORR_THRESHOLD = 0.70
MARGINAL_ICIR_THRESHOLD = 0.02
TOP_ROLE_LIMITS = {
    "core_thesis": 4,
    "confirmation": 6,
    "execution_guardrail": 3,
}


@dataclass
class ThemeArtifacts:
    theme_spec: ThemeSpec
    support: ResearchSupport
    end_date: str
    field_inventory: list
    raw_fields: dict[str, pd.Series]
    component_specs: list[ComponentSpec]
    component_engine: ComponentEngine


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def write_markdown(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_series_parquet(series: pd.Series, path: Path, column: str = "value") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    series.astype(np.float32).to_frame(column).to_parquet(path)


def read_series_parquet(path: Path, column: str = "value") -> pd.Series:
    frame = pd.read_parquet(path)
    if isinstance(frame, pd.Series):
        series = frame
    else:
        use_column = column if column in frame.columns else frame.columns[0]
        series = frame[use_column]
    if isinstance(series.index, pd.MultiIndex) and series.index.names[0] == "instrument":
        series = series.swaplevel().sort_index()
    elif not series.index.is_monotonic_increasing:
        series = series.sort_index()
    return series.astype(np.float32)


def prepared_theme_cache_dir(theme_dir: Path) -> Path:
    return theme_dir / "cache" / "prepared_theme"


def prepared_theme_manifest_path(theme_dir: Path) -> Path:
    return prepared_theme_cache_dir(theme_dir) / "prepared_theme.json"


def write_prepared_theme_cache(artifacts: ThemeArtifacts, theme_dir: Path) -> Path:
    cache_dir = prepared_theme_cache_dir(theme_dir)
    raw_field_dir = cache_dir / "raw_fields"
    raw_field_dir.mkdir(parents=True, exist_ok=True)
    field_files: dict[str, str] = {}
    for field_name, series in artifacts.raw_fields.items():
        filename = f"{field_name}.parquet"
        write_series_parquet(series, raw_field_dir / filename)
        field_files[field_name] = f"raw_fields/{filename}"
    manifest = {
        "theme_id": artifacts.theme_spec.theme_id,
        "benchmark": artifacts.theme_spec.benchmark,
        "data_start": artifacts.theme_spec.data_start,
        "end_date": artifacts.end_date,
        "field_inventory": [asdict(item) for item in artifacts.field_inventory],
        "raw_field_files": field_files,
    }
    write_json(prepared_theme_manifest_path(theme_dir), manifest)
    return prepared_theme_manifest_path(theme_dir)


def load_prepared_theme_cache(
    theme_spec: ThemeSpec,
    theme_dir: Path,
    provider: QlibFieldProvider | None = None,
) -> ThemeArtifacts:
    manifest_path = prepared_theme_manifest_path(theme_dir)
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Prepared theme cache not found for theme={theme_spec.theme_id}: {manifest_path}"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    field_inventory = [
        FieldInventoryRow(
            field_name=str(item["field_name"]),
            field_family=str(item["field_family"]),
            provider_source=str(item["provider_source"]),
            coverage_start=str(item.get("coverage_start", "")),
            coverage_end=str(item.get("coverage_end", "")),
            coverage_ratio=float(item.get("coverage_ratio", 0.0)),
            freq_type=str(item.get("freq_type", "")),
            pit_safe=bool(item.get("pit_safe", False)),
            theme_tags=tuple(item.get("theme_tags", [])),
        )
        for item in manifest.get("field_inventory", [])
    ]
    raw_fields = {
        field_name: read_series_parquet(prepared_theme_cache_dir(theme_dir) / relative_path)
        for field_name, relative_path in manifest.get("raw_field_files", {}).items()
    }
    support = build_support(
        theme_spec.benchmark,
        qlib_dir=(provider.qlib_dir if isinstance(provider, QlibFieldProvider) else None),
    )
    component_specs = generate_component_specs(theme_spec.theme_id, field_inventory)
    component_engine = ComponentEngine(raw_fields)
    return ThemeArtifacts(
        theme_spec=theme_spec,
        support=support,
        end_date=str(manifest.get("end_date") or support.trade_calendar[-1].strftime("%Y-%m-%d")),
        field_inventory=field_inventory,
        raw_fields=raw_fields,
        component_specs=component_specs,
        component_engine=component_engine,
    )


def build_walk_forward_folds(
    start_date: str,
    end_date: str,
    train_years: int = TRAIN_YEARS,
    validation_years: int = VALIDATION_YEARS,
    test_years: int = TEST_YEARS,
    step_years: int = STEP_YEARS,
) -> tuple[list[FoldSpec], HoldoutSpec | None]:
    return shared_build_walk_forward_folds(
        start_date=start_date,
        end_date=end_date,
        train_years=train_years,
        validation_years=validation_years,
        test_years=test_years,
        step_years=step_years,
    )


def build_rebalance_dates(calendar: list[pd.Timestamp], rebalance_days: int) -> list[pd.Timestamp]:
    if rebalance_days <= 0:
        raise ValueError("rebalance_days must be positive")
    return list(calendar[::rebalance_days])


def assign_corr_clusters(corr_matrix: pd.DataFrame, threshold: float = COMPONENT_CORR_THRESHOLD) -> dict[str, str]:
    if corr_matrix.empty:
        return {}
    factors = list(corr_matrix.index)
    adjacency: dict[str, set[str]] = {factor: set() for factor in factors}
    for i, left in enumerate(factors):
        for right in factors[i + 1:]:
            corr = corr_matrix.loc[left, right]
            if pd.notna(corr) and abs(float(corr)) >= threshold:
                adjacency[left].add(right)
                adjacency[right].add(left)
    clusters: dict[str, str] = {}
    cluster_num = 1
    for factor in factors:
        if factor in clusters:
            continue
        queue = [factor]
        while queue:
            current = queue.pop()
            if current in clusters:
                continue
            clusters[current] = f"cluster_{cluster_num:02d}"
            queue.extend(adjacency[current] - set(clusters))
        cluster_num += 1
    return clusters


def sort_variant_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    work = df.copy()
    if "rank" in work.columns:
        work = work.drop(columns=["rank"])
    work = work.sort_values(
        by=[
            "stitched_relative_excess_return",
            "positive_excess_folds",
            "holdout_relative_excess_return",
            "worst_max_drawdown",
            "avg_turnover",
        ],
        ascending=[False, False, False, False, True],
    ).reset_index(drop=True)
    work.insert(0, "rank", np.arange(1, len(work) + 1))
    return work


def sort_universe_summary_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    work = df.copy()
    if "rank" in work.columns:
        work = work.drop(columns=["rank"])
    work = work.sort_values(
        by=[
            "median_stitched_relative_excess_return",
            "median_positive_excess_folds",
            "median_holdout_relative_excess_return",
            "median_worst_max_drawdown",
            "median_avg_turnover",
        ],
        ascending=[False, False, False, False, True],
    ).reset_index(drop=True)
    work.insert(0, "rank", np.arange(1, len(work) + 1))
    return work


def safe_median(values: pd.Series) -> float:
    values = pd.Series(values, dtype=float).dropna()
    return float(values.median()) if not values.empty else np.nan


def render_field_inventory_md(theme_spec: ThemeSpec, field_inventory: list) -> str:
    lines = [
        f"# {theme_spec.theme_id} 字段审计",
        "",
        f"- 主题假设：{theme_spec.thesis}",
        f"- 可用字段数：{len(field_inventory)}",
        "",
        "| 字段 | 家族 | 来源 | 覆盖率 | 起始 | 结束 |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for row in field_inventory:
        lines.append(
            f"| {row.field_name} | {row.field_family} | {row.provider_source} | {row.coverage_ratio:.1%} | {row.coverage_start or '-'} | {row.coverage_end or '-'} |"
        )
    return "\n".join(lines)


def format_percent(value: float | int | None, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):.{digits}%}"


def format_number(value: float | int | None, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):.{digits}f}"


def format_count(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "-"
    if float(value).is_integer():
        return str(int(value))
    return f"{float(value):.1f}"


def format_cny_amount(value: float | None) -> str:
    if value is None:
        return "不限"
    value = float(value)
    if abs(value) >= 100_000_000:
        return f"{value / 100_000_000:.1f}亿元"
    if abs(value) >= 10_000:
        return f"{value / 10_000:.1f}万元"
    return f"{value:.0f}元"


def describe_universe_candidate(candidate: UniverseCandidate) -> str:
    membership_map = {
        "all_market": "全市场",
        "csi300": "沪深300成分",
        "csi500": "中证500成分",
        "csi1000": "中证1000成分",
        "st_only": "仅 ST 股票",
    }
    board_map = {
        "all": "不限制板块",
        "mainboard": "仅主板",
    }
    st_map = {
        "exclude": "排除 ST",
        "include_only": "仅保留 ST",
        "ignore": "不处理 ST",
    }
    parts = [
        membership_map.get(candidate.membership_source, candidate.membership_source),
        board_map.get(candidate.board_policy, candidate.board_policy),
        st_map.get(candidate.st_mode, candidate.st_mode),
        f"上市至少 {candidate.min_listing_days} 个交易日",
    ]
    if candidate.market_cap_min is not None or candidate.market_cap_max is not None:
        cap_min = format_cny_amount(candidate.market_cap_min)
        cap_max = format_cny_amount(candidate.market_cap_max)
        if candidate.market_cap_min is not None and candidate.market_cap_max is not None:
            parts.append(f"总市值 {cap_min} 到 {cap_max}")
        elif candidate.market_cap_min is not None:
            parts.append(f"总市值不低于 {cap_min}")
        else:
            parts.append(f"总市值不高于 {cap_max}")
    if candidate.price_cap is not None:
        parts.append(f"股价不高于 {candidate.price_cap:.2f} 元")
    if candidate.liquidity_floor is not None:
        parts.append(f"20日成交额不低于 {format_cny_amount(candidate.liquidity_floor)}")
    if candidate.revenue_floor is not None:
        parts.append(f"单季度营收不低于 {format_cny_amount(candidate.revenue_floor)}")
    if candidate.profitability_positive and candidate.profitability_field:
        parts.append(f"`{candidate.profitability_field}` 必须为正")
    if candidate.northbound_required:
        parts.append("要求北向覆盖可用")
    if candidate.ret250_pctile_max is not None:
        parts.append(f"250日收益全市场分位不高于 {candidate.ret250_pctile_max:.0%}")
    if candidate.special_filters:
        parts.append(f"特殊过滤：{', '.join(candidate.special_filters)}")
    return "；".join(parts)


def render_universe_selection_md(theme_spec: ThemeSpec, universe_summary: pd.DataFrame) -> str:
    lines = [
        f"# {theme_spec.theme_id} Universe 选择说明",
        "",
        f"- 主题假设：{theme_spec.thesis}",
        f"- 基准：{theme_spec.benchmark}",
        f"- 起始日期：{theme_spec.data_start}",
        f"- 本阶段只比较 Universe，锚点 recipe：{', '.join(theme_spec.anchor_recipes)}",
        "- 排序规则：先看样本外相对超额收益，再看正收益 fold 覆盖、holdout 和回撤。",
        "",
        "## 候选 Universe 定义",
        "",
    ]
    for candidate in theme_spec.universe_candidates:
        lines.append(f"- `{candidate.candidate_id}`：{describe_universe_candidate(candidate)}")

    if universe_summary.empty:
        lines.extend(["", "## 排序结果", "", "当前没有可用的 Universe 排名结果。"])
        return "\n".join(lines)

    lines.extend(
        [
            "",
            "## 排序结果",
            "",
            "| 排名 | Universe | 中位样本外相对超额 | 中位正收益 folds | 中位 holdout 相对超额 | 中位最差回撤 | 中位换手 |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for _, row in universe_summary.iterrows():
        lines.append(
            "| {rank} | {universe_id} | {oos} | {folds} | {holdout} | {drawdown} | {turnover} |".format(
                rank=int(row["rank"]),
                universe_id=row["universe_id"],
                oos=format_percent(row["median_stitched_relative_excess_return"]),
                folds=format_count(row["median_positive_excess_folds"]),
                holdout=format_percent(row["median_holdout_relative_excess_return"]),
                drawdown=format_percent(row["median_worst_max_drawdown"]),
                turnover=format_percent(row["median_avg_turnover"]),
            )
        )

    top_universe_ids = universe_summary.head(2)["universe_id"].tolist()
    lines.extend(["", "## 结论", "", f"- 入围 Universe：`{'`、`'.join(top_universe_ids)}`"])

    if theme_spec.theme_id == "small_cap":
        rank_map = universe_summary.set_index("universe_id")
        if {"sc_u1", "sc_u2", "sc_u3", "sc_u4", "sc_u5", "sc_u6"}.issubset(set(rank_map.index)):
            best_csi1000 = rank_map.loc[["sc_u1", "sc_u2", "sc_u3"], "median_stitched_relative_excess_return"].max()
            best_all_market = rank_map.loc[["sc_u4", "sc_u5", "sc_u6"], "median_stitched_relative_excess_return"].max()
            if pd.notna(best_all_market) and pd.notna(best_csi1000) and best_all_market > best_csi1000:
                lines.append("- 更强的机会来自“全市场主板小盘”，而不是只限定在中证1000成分内，说明指数成分约束反而削弱了这个主题。")
            sc_u4 = rank_map.loc["sc_u4"]
            sc_u5 = rank_map.loc["sc_u5"]
            sc_u6 = rank_map.loc["sc_u6"]
            if sc_u4["median_stitched_relative_excess_return"] >= sc_u5["median_stitched_relative_excess_return"]:
                lines.append("- `sc_u4` 略强于 `sc_u5`，说明把市值上限压在 100 亿以内，可能比放宽到 200 亿更能保留纯粹的小票暴露。")
            if sc_u6["median_holdout_relative_excess_return"] > sc_u5["median_holdout_relative_excess_return"]:
                lines.append("- `sc_u6` 的 holdout 不差，但整体样本外收益和回撤都弱于 `sc_u4/sc_u5`，说明过度放宽盈利和营收门槛会增加不稳定性。")

    return "\n".join(lines)


def render_market_summary_md(output_root: Path, ranking_df: pd.DataFrame, stage: str) -> str:
    lines = [
        "# 市场机会总览",
        "",
        f"- 本次运行阶段：{stage}",
        f"- 覆盖主题数：{len(ranking_df)}",
        "- 这份总表的目的，是帮助快速判断下一步应该在哪些主题和股票池上继续深挖。",
    ]
    if ranking_df.empty:
        lines.extend(["", "当前没有可汇总的主题结果。"])
        return "\n".join(lines)

    for _, row in ranking_df.iterrows():
        theme_id = row.get("theme_id", "-")
        lines.extend(["", f"## {theme_id}", ""])
        theme_dir = output_root / str(theme_id)
        universe_path = theme_dir / "universe_search_summary.csv"
        if universe_path.exists():
            universe_summary = pd.read_csv(universe_path)
            if not universe_summary.empty:
                top = universe_summary.iloc[0]
                second = universe_summary.iloc[1] if len(universe_summary) >= 2 else None
                lines.append(f"- 当前最优 Universe：`{top['universe_id']}`，中位样本外相对超额为 {format_percent(top['median_stitched_relative_excess_return'])}。")
                if second is not None:
                    lines.append(f"- 第二名是 `{second['universe_id']}`，中位样本外相对超额为 {format_percent(second['median_stitched_relative_excess_return'])}。")
                lines.append(f"- 当前建议：先在 `{'` 和 `'.join(universe_summary.head(2)['universe_id'].tolist())}` 上继续做 component diagnostics 和 recipe search。")
                continue
        lines.append(f"- 当前最优 Universe：`{row.get('best_universe_id', '-')}`。")

    return "\n".join(lines)


def render_future_backlog_md(stage: str, ranking_df: pd.DataFrame) -> str:
    lines = [
        "# Future Theme Backlog",
        "",
    ]
    if stage == "universe" and not ranking_df.empty:
        for _, row in ranking_df.iterrows():
            if row.get("best_universe_id"):
                lines.append(f"- `{row['theme_id']}`：Universe 已选出 `{row['best_universe_id']}`，下一步进入 component diagnostics、白名单筛选和 recipe search。")
    lines.append("- `AH premium`：先补齐 H 股/AH 配对、汇率和联动可交易性数据，再进入正式框架。")
    return "\n".join(lines)


def role_label(role: str) -> str:
    return {
        "core_thesis": "核心",
        "confirmation": "确认",
        "execution_guardrail": "执行约束",
        "diagnostic_only": "仅诊断",
    }.get(role, role)


def render_component_selection_md(
    theme_spec: ThemeSpec,
    component_card_df: pd.DataFrame,
    specs_by_id: dict[str, ComponentSpec],
    top_universe_ids: list[str],
) -> str:
    lines = [
        f"# {theme_spec.theme_id} Component 选择说明",
        "",
        f"- 主题：{theme_spec.theme_id}",
        f"- 进入本阶段的 Universe：{', '.join(top_universe_ids) if top_universe_ids else '无'}",
        "- 硬门槛：覆盖率至少 25%，样本外方向不能明显反着来；高相关 component 必须证明自己有增量信息。",
        "- 目标：先形成可解释的 component 白名单，再交给 recipe search 做组合比较。",
    ]

    if component_card_df.empty:
        lines.extend(["", "当前没有可写入的 component diagnostics 结果。"])
        return "\n".join(lines)

    work = component_card_df.copy()
    work["economic_role"] = work["component_id"].map(lambda cid: specs_by_id[cid].economic_role if cid in specs_by_id else "")
    work["notes"] = work["component_id"].map(lambda cid: specs_by_id[cid].notes if cid in specs_by_id else "")
    work["source_fields"] = work["component_id"].map(
        lambda cid: ", ".join(specs_by_id[cid].source_fields) if cid in specs_by_id else ""
    )

    selected_total = int(work["selected_for_recipe"].sum())
    lines.append(f"- 当前进入 recipe 白名单的 component 数量：{selected_total}")

    for universe_id in top_universe_ids:
        universe_df = work.loc[work["universe_id"] == universe_id].copy()
        if universe_df.empty:
            continue
        selected_df = universe_df.loc[universe_df["selected_for_recipe"]].copy()
        role_counts = (
            selected_df["economic_role"].value_counts().to_dict()
            if not selected_df.empty
            else {}
        )
        lines.extend(
            [
                "",
                f"## {universe_id}",
                "",
                f"- 候选 component 数：{len(universe_df)}",
                f"- 进入白名单数：{len(selected_df)}",
                f"- 角色分布：核心 {role_counts.get('core_thesis', 0)}，确认 {role_counts.get('confirmation', 0)}，执行约束 {role_counts.get('execution_guardrail', 0)}",
            ]
        )

        if not selected_df.empty:
            top_selected = selected_df.sort_values(
                by=["selection_score", "rank_icir", "mean_rank_ic"],
                ascending=[False, False, False],
            ).head(8)
            lines.extend(
                [
                    "",
                    "| component | 角色 | coverage | rank_ic | rank_icir | cluster | 说明 |",
                    "| --- | --- | ---: | ---: | ---: | --- | --- |",
                ]
            )
            for _, row in top_selected.iterrows():
                lines.append(
                    "| {component_id} | {role} | {coverage} | {rank_ic} | {rank_icir} | {cluster} | {notes} |".format(
                        component_id=row["component_id"],
                        role=role_label(str(row["economic_role"])),
                        coverage=format_percent(row["coverage_ratio"]),
                        rank_ic=format_percent(row["mean_rank_ic"]),
                        rank_icir=format_number(row["rank_icir"]),
                        cluster=row["cluster_id"] or "-",
                        notes=row["notes"] or "-",
                    )
                )

        rejected = universe_df.loc[~universe_df["selected_for_recipe"]].copy()
        if not rejected.empty:
            top_reasons = rejected["rejection_reason"].fillna("").replace("", "其他").value_counts().head(3)
            lines.extend(["", "- 主要淘汰原因："])
            for reason, count in top_reasons.items():
                lines.append(f"- {reason}（{count} 个）")

    return "\n".join(lines)


def render_signal_selection_md(theme_spec: ThemeSpec, recipe_summary: pd.DataFrame) -> str:
    lines = [
        f"# {theme_spec.theme_id} Signal 选择说明",
        "",
        f"- 主题：{theme_spec.theme_id}",
        "- 规则：每个 recipe 至少包含 1 个核心 component，可再叠加确认项和执行约束，第一版统一等权。",
        f"- topk 搜索范围：{list(theme_spec.topk_grid)}",
        f"- 调仓频率搜索范围：{list(theme_spec.rebalance_grid)}",
    ]

    if recipe_summary.empty:
        lines.extend(["", "当前没有可写入的 recipe 排名结果。"])
        return "\n".join(lines)

    best_row = recipe_summary.iloc[0]
    lines.extend(
        [
            "",
            "## 最优结果",
            "",
            f"- 当前最优组合：`{best_row['recipe_id']}`，来自 `{best_row['universe_id']}`。",
            f"- 组件：`{str(best_row['component_ids']).replace('|', '` + `')}`",
            f"- 参数：topk = {int(best_row['topk'])}，rebalance_days = {int(best_row['rebalance_days'])}",
            f"- 中位样本外相对超额：{format_percent(best_row['stitched_relative_excess_return'])}",
            f"- 中位 holdout 相对超额：{format_percent(best_row['holdout_relative_excess_return'])}",
            f"- 最差 fold 回撤：{format_percent(best_row['worst_max_drawdown'])}",
            f"- 平均换手：{format_percent(best_row['avg_turnover'])}",
        ]
    )
    if best_row.get("selection_note"):
        lines.append(f"- 设计说明：{best_row['selection_note']}")

    lines.extend(
        [
            "",
            "## 前十名配方",
            "",
            "| 排名 | Universe | Recipe | 组件 | topk | 调仓天数 | 样本外相对超额 | holdout 相对超额 | 最差回撤 | 换手 |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for _, row in recipe_summary.head(10).iterrows():
        lines.append(
            "| {rank} | {universe} | {recipe} | {components} | {topk} | {rebalance} | {oos} | {holdout} | {drawdown} | {turnover} |".format(
                rank=int(row["rank"]),
                universe=row["universe_id"],
                recipe=row["recipe_id"],
                components=str(row["component_ids"]).replace("|", " + "),
                topk=int(row["topk"]),
                rebalance=int(row["rebalance_days"]),
                oos=format_percent(row["stitched_relative_excess_return"]),
                holdout=format_percent(row["holdout_relative_excess_return"]),
                drawdown=format_percent(row["worst_max_drawdown"]),
                turnover=format_percent(row["avg_turnover"]),
            )
        )

    best_by_universe = recipe_summary.groupby("universe_id", sort=False).head(1)
    lines.extend(["", "## 按 Universe 看最优 Recipe", ""])
    for _, row in best_by_universe.iterrows():
        lines.append(
            f"- `{row['universe_id']}`：最佳 recipe 是 `{row['recipe_id']}`，样本外相对超额 {format_percent(row['stitched_relative_excess_return'])}，holdout 相对超额 {format_percent(row['holdout_relative_excess_return'])}。"
        )

    return "\n".join(lines)


def sort_event_summary_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    work = df.copy()
    if "rank" in work.columns:
        work = work.drop(columns=["rank"])
    work = work.sort_values(
        by=["relative_excess_return", "max_drawdown", "avg_turnover", "trade_count"],
        ascending=[False, False, True, False],
    ).reset_index(drop=True)
    work.insert(0, "rank", np.arange(1, len(work) + 1))
    return work


def render_theme_review_md(
    theme_spec: ThemeSpec,
    top_universe_ids: list[str],
    component_card_df: pd.DataFrame,
    recipe_summary: pd.DataFrame,
    event_summary: pd.DataFrame,
) -> str:
    lines = [
        f"# {theme_spec.theme_id} 主题复盘",
        "",
        f"- 主题假设：{theme_spec.thesis}",
        f"- Universe 入围：{', '.join(top_universe_ids) if top_universe_ids else '无'}",
        f"- Component 白名单数量：{int(component_card_df['selected_for_recipe'].sum()) if not component_card_df.empty else 0}",
        f"- Recipe 候选数：{len(recipe_summary)}",
        f"- Event-driven 确认数：{len(event_summary)}",
    ]

    if not recipe_summary.empty:
        best_recipe = recipe_summary.iloc[0]
        lines.extend(
            [
                "",
                "## 最优向量化结果",
                "",
                f"- 最优 Universe / Recipe：`{best_recipe['universe_id']}` / `{best_recipe['recipe_id']}`",
                f"- 组件：`{str(best_recipe['component_ids']).replace('|', '` + `')}`",
                f"- 样本外相对超额：{format_percent(best_recipe['stitched_relative_excess_return'])}",
                f"- holdout 相对超额：{format_percent(best_recipe['holdout_relative_excess_return'])}",
                f"- 最差回撤：{format_percent(best_recipe['worst_max_drawdown'])}",
                f"- 平均换手：{format_percent(best_recipe['avg_turnover'])}",
            ]
        )

    if not event_summary.empty:
        best_event = event_summary.iloc[0]
        lines.extend(
            [
                "",
                "## Event-Driven 确认",
                "",
                f"- 最优事件驱动组合：`{best_event['recipe_id']}`（{best_event['universe_id']}）",
                f"- 相对超额：{format_percent(best_event['relative_excess_return'])}",
                f"- 最大回撤：{format_percent(best_event['max_drawdown'])}",
                f"- 平均换手：{format_percent(best_event['avg_turnover'])}",
                f"- 交易笔数：{format_count(best_event['trade_count'])}",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "## Event-Driven 确认",
                "",
                "- 当前还没有事件驱动确认结果，下一步应把前两名 recipe 带入真实执行回测做最终确认。",
            ]
        )

    return "\n".join(lines)


class ThemeStrategyPipeline:
    def __init__(
        self,
        provider: QlibFieldProvider | None = None,
        output_root: Path | None = None,
    ):
        self.provider = provider or QlibFieldProvider()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_root = output_root or (
            PROJECT_ROOT / "workspace" / "outputs" / "theme_strategy" / f"theme_strategy_{stamp}"
        )
        self.output_root.mkdir(parents=True, exist_ok=True)

    def prepare_theme(
        self,
        theme_spec: ThemeSpec,
        *,
        start_override: str | None = None,
        end_override: str | None = None,
    ) -> ThemeArtifacts:
        support = build_support(theme_spec.benchmark, qlib_dir=self.provider.qlib_dir if isinstance(self.provider, QlibFieldProvider) else None)
        effective_start = str(theme_spec.data_start)
        if start_override:
            effective_start = max(pd.Timestamp(theme_spec.data_start), pd.Timestamp(start_override)).strftime("%Y-%m-%d")
        end_date = support.trade_calendar[-1].strftime("%Y-%m-%d")
        if end_override:
            end_date = min(pd.Timestamp(end_date), pd.Timestamp(end_override)).strftime("%Y-%m-%d")
        if pd.Timestamp(effective_start) > pd.Timestamp(end_date):
            raise ValueError(
                f"Theme field-audit window is empty after hypothesis clamp: start={effective_start}, end={end_date}"
            )
        field_defs = [field_def for field_def in get_field_definitions() if theme_spec.theme_id in field_def.theme_tags]
        field_inventory, raw_fields = self.provider.audit_fields(
            field_defs,
            effective_start,
            end_date,
            sample_start=max(effective_start, (support.trade_calendar[-60]).strftime("%Y-%m-%d")) if len(support.trade_calendar) > 60 else effective_start,
            sample_end=end_date,
        )
        component_specs = generate_component_specs(theme_spec.theme_id, field_inventory)
        component_engine = ComponentEngine(raw_fields)
        return ThemeArtifacts(
            theme_spec=theme_spec,
            support=support,
            end_date=end_date,
            field_inventory=field_inventory,
            raw_fields=raw_fields,
            component_specs=component_specs,
            component_engine=component_engine,
        )

    def _calendar_slice(self, artifacts: ThemeArtifacts, start: str, end: str) -> list[pd.Timestamp]:
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        return [date for date in artifacts.support.trade_calendar if start_ts <= date <= end_ts]

    def _listing_days_ok(self, support: ResearchSupport, code: str, date: pd.Timestamp, min_listing_days: int) -> bool:
        if code not in support.stock_basic_map.index:
            return False
        ref = support.stock_basic_map.loc[code]
        list_date = ref.get("list_date")
        delist_date = ref.get("delist_date")
        if pd.notna(delist_date) and pd.Timestamp(date) > pd.Timestamp(delist_date):
            return False
        if pd.isna(list_date):
            return False
        list_pos = support.trade_calendar_index.searchsorted(pd.Timestamp(list_date), side="left")
        date_pos = support.trade_pos_by_date.get(pd.Timestamp(date))
        if date_pos is None:
            return False
        return int(date_pos - list_pos) >= int(min_listing_days)

    def _build_forward_return_series(
        self,
        artifacts: ThemeArtifacts,
        rebalance_days: int,
    ) -> pd.Series:
        close = artifacts.raw_fields["close"]
        adj_factor = artifacts.raw_fields.get("adj_factor")
        prices = close if adj_factor is None else close * adj_factor
        dates = build_rebalance_dates(self._calendar_slice(artifacts, artifacts.theme_spec.data_start, artifacts.end_date), rebalance_days)
        if len(dates) < 2:
            empty_index = pd.MultiIndex.from_arrays([[], []], names=["datetime", "instrument"])
            return pd.Series(dtype=np.float32, index=empty_index, name=f"fwd_{rebalance_days}d")
        labels: list[pd.Series] = []
        for idx, date in enumerate(dates[:-1]):
            next_date = dates[idx + 1]
            try:
                start_px = prices.xs(date, level="datetime")
                end_px = prices.xs(next_date, level="datetime")
            except KeyError:
                continue
            period_ret = (end_px / start_px) - 1.0
            period_ret.index = pd.MultiIndex.from_product([[pd.Timestamp(date)], period_ret.index], names=["datetime", "instrument"])
            labels.append(period_ret.astype(np.float32))
        if not labels:
            empty_index = pd.MultiIndex.from_arrays([[], []], names=["datetime", "instrument"])
            return pd.Series(dtype=np.float32, index=empty_index, name=f"fwd_{rebalance_days}d")
        return pd.concat(labels).sort_index().rename(f"fwd_{rebalance_days}d")

    def _build_universe_eligible_map(
        self,
        artifacts: ThemeArtifacts,
        universe: UniverseCandidate,
        rebal_dates: list[pd.Timestamp],
    ) -> dict[pd.Timestamp, set[str]]:
        # jolly-seeking-lollipop Gate C: delegate to the module-level
        # `build_universe_eligibility` so prescription_runtime can reuse the
        # exact same logic. The free function takes plain raw_fields/support
        # and a callable for listing-days check, avoiding the need to
        # construct a ThemeArtifacts in non-theme contexts.
        return build_universe_eligibility(
            raw_fields=artifacts.raw_fields,
            support=artifacts.support,
            universe=universe,
            rebal_dates=rebal_dates,
            listing_days_ok=lambda code, date: self._listing_days_ok(
                artifacts.support, code, date, universe.min_listing_days
            ),
        )

    def _combine_recipe_signal(
        self,
        artifacts: ThemeArtifacts,
        specs_by_id: dict[str, ComponentSpec],
        recipe: SignalRecipe,
        eligible_map: dict[pd.Timestamp, set[str]],
    ) -> pd.Series:
        component_frames: list[pd.Series] = []
        for component_id, weight in zip(recipe.component_ids, recipe.weights, strict=True):
            spec = specs_by_id[component_id]
            series = artifacts.component_engine.get_series(spec)
            ranked = rank_component_within_universe(series, eligible_map, spec.expected_sign)
            if ranked.empty:
                continue
            component_frames.append(ranked * float(weight))
        if not component_frames:
            return pd.Series(dtype=np.float32)
        signal = pd.concat(component_frames, axis=1).sum(axis=1, min_count=1).astype(np.float32)
        signal.name = recipe.recipe_id
        return signal

    def _simulate_portfolio(
        self,
        artifacts: ThemeArtifacts,
        signal: pd.Series,
        rebal_dates: list[pd.Timestamp],
        topk: int,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        prices = artifacts.raw_fields["close"] * artifacts.raw_fields.get("adj_factor", 1.0)
        bench_close = artifacts.support.benchmark_close
        prev_weights: dict[str, float] = {}
        perf_rows: list[dict[str, Any]] = []
        signal_rows: list[dict[str, Any]] = []
        for idx, date in enumerate(rebal_dates[:-1]):
            next_date = rebal_dates[idx + 1]
            try:
                daily_signal = signal.xs(date, level="datetime").dropna().sort_values(ascending=False).head(topk)
            except KeyError:
                continue
            if daily_signal.empty:
                continue
            try:
                start_px = prices.xs(date, level="datetime").reindex(daily_signal.index)
                end_px = prices.xs(next_date, level="datetime").reindex(daily_signal.index)
            except KeyError:
                continue
            period_returns = (end_px / start_px) - 1.0
            period_returns = period_returns.replace([np.inf, -np.inf], np.nan).dropna()
            if period_returns.empty:
                continue
            selected_codes = period_returns.index.tolist()
            weights = {code: 1.0 / len(selected_codes) for code in selected_codes}
            strategy_return = float(np.mean(period_returns.loc[selected_codes]))
            bench_return = float(bench_close.loc[next_date] / bench_close.loc[date] - 1.0) if date in bench_close.index and next_date in bench_close.index else np.nan
            turnover = 0.5 * sum(abs(weights.get(code, 0.0) - prev_weights.get(code, 0.0)) for code in set(weights) | set(prev_weights))
            perf_rows.append(
                {
                    "date": next_date,
                    "period_start": date,
                    "period_end": next_date,
                    "return": strategy_return,
                    "bench": bench_return,
                    "turnover": turnover,
                }
            )
            for code in selected_codes:
                signal_rows.append(
                    {
                        "date": date,
                        "instrument": code.replace("_", "."),
                        "score": float(daily_signal.get(code, np.nan)),
                        "target_weight": float(weights[code]),
                    }
                )
            prev_weights = weights
        return pd.DataFrame(perf_rows), pd.DataFrame(signal_rows)

    def _summarize_variant(
        self,
        theme_id: str,
        stage: str,
        universe_id: str,
        recipe_id: str,
        topk: int,
        rebalance_days: int,
        folds: list[FoldSpec],
        holdout: HoldoutSpec | None,
        fold_perf: dict[str, pd.DataFrame],
    ) -> VariantSummary:
        test_frames = [fold_perf[fold.fold_id] for fold in folds if fold.fold_id in fold_perf]
        if test_frames:
            combined = pd.concat(test_frames, ignore_index=True)
            stitched_strategy = float(np.prod(1.0 + combined["return"].astype(float)) - 1.0)
            stitched_bench = float(np.prod(1.0 + combined["bench"].fillna(0.0).astype(float)) - 1.0)
            positive_excess_folds = int(sum(frame["return"].sum() > frame["bench"].fillna(0.0).sum() for frame in test_frames if not frame.empty))
            worst_max_drawdown = float(min(calculate_max_drawdown(frame["return"].astype(float)) if not frame.empty else 0.0 for frame in test_frames))
            avg_turnover = float(np.mean([frame["turnover"].mean() for frame in test_frames if not frame.empty])) if test_frames else np.nan
        else:
            stitched_strategy = np.nan
            stitched_bench = np.nan
            positive_excess_folds = 0
            worst_max_drawdown = np.nan
            avg_turnover = np.nan
        holdout_relative_excess_return = np.nan
        if holdout is not None and holdout.window_type in fold_perf and not fold_perf[holdout.window_type].empty:
            holdout_frame = fold_perf[holdout.window_type]
            holdout_strategy = float(np.prod(1.0 + holdout_frame["return"].astype(float)) - 1.0)
            holdout_bench = float(np.prod(1.0 + holdout_frame["bench"].fillna(0.0).astype(float)) - 1.0)
            holdout_relative_excess_return = holdout_strategy - holdout_bench
        return VariantSummary(
            theme_id=theme_id,
            stage=stage,
            universe_id=universe_id,
            recipe_id=recipe_id,
            topk=topk,
            rebalance_days=rebalance_days,
            stitched_relative_excess_return=stitched_strategy - stitched_bench if pd.notna(stitched_strategy) and pd.notna(stitched_bench) else np.nan,
            positive_excess_folds=positive_excess_folds,
            holdout_relative_excess_return=holdout_relative_excess_return,
            worst_max_drawdown=worst_max_drawdown,
            avg_turnover=avg_turnover,
        )

    def evaluate_recipe_variant(
        self,
        artifacts: ThemeArtifacts,
        universe: UniverseCandidate,
        recipe: SignalRecipe,
        topk: int,
        rebalance_days: int,
        folds: list[FoldSpec],
        holdout: HoldoutSpec | None,
        specs_by_id: dict[str, ComponentSpec],
    ) -> tuple[VariantSummary, dict[str, pd.DataFrame]]:
        full_dates = build_rebalance_dates(self._calendar_slice(artifacts, artifacts.theme_spec.data_start, artifacts.end_date), rebalance_days)
        eligible_map = self._build_universe_eligible_map(artifacts, universe, full_dates)
        signal = self._combine_recipe_signal(artifacts, specs_by_id, recipe, eligible_map)
        fold_perf: dict[str, pd.DataFrame] = {}
        if signal.empty:
            summary = self._summarize_variant(
                theme_id=artifacts.theme_spec.theme_id,
                stage="recipe",
                universe_id=universe.candidate_id,
                recipe_id=recipe.recipe_id,
                topk=topk,
                rebalance_days=rebalance_days,
                folds=folds,
                holdout=holdout,
                fold_perf=fold_perf,
            )
            return summary, fold_perf
        for fold in folds:
            fold_dates = [date for date in full_dates if pd.Timestamp(fold.test_start) <= date <= pd.Timestamp(fold.test_end)]
            if len(fold_dates) < 2:
                continue
            fold_signal = signal.loc[signal.index.get_level_values("datetime").isin(fold_dates)]
            perf_df, _ = self._simulate_portfolio(artifacts, fold_signal, fold_dates, topk)
            fold_perf[fold.fold_id] = perf_df
        if holdout is not None:
            holdout_dates = [date for date in full_dates if pd.Timestamp(holdout.start) <= date <= pd.Timestamp(holdout.end)]
            if len(holdout_dates) >= 2:
                holdout_signal = signal.loc[signal.index.get_level_values("datetime").isin(holdout_dates)]
                holdout_perf, _ = self._simulate_portfolio(artifacts, holdout_signal, holdout_dates, topk)
                fold_perf[holdout.window_type] = holdout_perf
        summary = self._summarize_variant(
            theme_id=artifacts.theme_spec.theme_id,
            stage="recipe",
            universe_id=universe.candidate_id,
            recipe_id=recipe.recipe_id,
            topk=topk,
            rebalance_days=rebalance_days,
            folds=folds,
            holdout=holdout,
            fold_perf=fold_perf,
        )
        return summary, fold_perf

    def compute_component_diagnostics(
        self,
        artifacts: ThemeArtifacts,
        universe: UniverseCandidate,
        specs_by_id: dict[str, ComponentSpec],
        folds: list[FoldSpec],
    ) -> tuple[list[ComponentDiagnostic], dict[str, str]]:
        rebal_dates = build_rebalance_dates(self._calendar_slice(artifacts, artifacts.theme_spec.data_start, artifacts.end_date), artifacts.theme_spec.diagnostic_rebalance_days)
        eligible_map = self._build_universe_eligible_map(artifacts, universe, rebal_dates)
        label = self._build_forward_return_series(artifacts, artifacts.theme_spec.diagnostic_rebalance_days)
        ranked_map: dict[str, pd.Series] = {}
        coverage_base = float(sum(len(codes) for codes in eligible_map.values())) or np.nan
        for spec in artifacts.component_specs:
            ranked_map[spec.component_id] = rank_component_within_universe(
                artifacts.component_engine.get_series(spec),
                eligible_map,
                spec.expected_sign,
            )
        corr_input = {key: value for key, value in ranked_map.items() if not value.empty}
        corr_matrix = compute_factor_correlation(corr_input, method="spearman", min_obs=5) if len(corr_input) >= 2 else pd.DataFrame()
        cluster_map = assign_corr_clusters(corr_matrix, threshold=COMPONENT_CORR_THRESHOLD)
        diagnostics: list[ComponentDiagnostic] = []
        selected_series: dict[str, pd.Series] = {}
        ranked_specs = sorted(
            artifacts.component_specs,
            key=lambda spec: (
                corr_input.get(spec.component_id, pd.Series(dtype=float)).notna().mean(),
                spec.economic_role != "diagnostic_only",
            ),
            reverse=True,
        )
        combined_validation_dates: list[pd.Timestamp] = []
        for fold in folds:
            combined_validation_dates.extend([date for date in rebal_dates if pd.Timestamp(fold.validation_start) <= date <= pd.Timestamp(fold.validation_end)])
        combined_validation_dates = sorted(set(combined_validation_dates))
        validation_label = label.loc[label.index.get_level_values("datetime").isin(combined_validation_dates)] if not label.empty else pd.Series(dtype=float)
        for spec in ranked_specs:
            ranked = ranked_map.get(spec.component_id, pd.Series(dtype=float))
            coverage_ratio = float(len(ranked) / coverage_base) if coverage_base and not np.isnan(coverage_base) else 0.0
            fold_scores: list[float] = []
            positive_folds = 0
            for fold in folds:
                fold_dates = [date for date in rebal_dates if pd.Timestamp(fold.validation_start) <= date <= pd.Timestamp(fold.validation_end)]
                if not fold_dates:
                    continue
                signal_slice = ranked.loc[ranked.index.get_level_values("datetime").isin(fold_dates)]
                label_slice = label.loc[label.index.get_level_values("datetime").isin(fold_dates)] if not label.empty else pd.Series(dtype=float)
                if signal_slice.empty or label_slice.empty:
                    continue
                summary = compute_ic_summary(compute_ic_series(signal_slice, label_slice, min_obs=5))
                score = float(summary.get("mean_rank_ic", np.nan))
                if pd.notna(score):
                    fold_scores.append(score)
                    if score > 0:
                        positive_folds += 1
            total_validation_folds = len(fold_scores)
            valid_fold_scores = [value for value in fold_scores if pd.notna(value)]
            mean_rank_ic = float(np.mean(valid_fold_scores)) if valid_fold_scores else np.nan
            std_fold_score = float(np.std(valid_fold_scores)) if len(valid_fold_scores) >= 2 else 0.0
            rank_icir = float((mean_rank_ic / std_fold_score) if valid_fold_scores and std_fold_score > 0 else 0.0)
            direction_consistent = bool(total_validation_folds > 0 and positive_folds / total_validation_folds >= 0.5 and (pd.isna(mean_rank_ic) or mean_rank_ic >= 0))
            selection_score = float((0.5 * coverage_ratio) + rank_icir + (positive_folds / total_validation_folds if total_validation_folds else 0.0))
            max_abs_corr = 0.0
            marginal_rank_icir = np.nan
            rejection_reason = ""
            selected_for_recipe = False
            if spec.economic_role == "diagnostic_only":
                rejection_reason = "diagnostic_only 角色只保留做解释，不进入正式 recipe。"
            elif coverage_ratio < 0.25:
                rejection_reason = "覆盖率低于 25%。"
            elif not direction_consistent:
                rejection_reason = "样本外方向稳定性不足。"
            else:
                corr_blockers = []
                for selected_id, selected_signal in selected_series.items():
                    if corr_matrix.empty or spec.component_id not in corr_matrix.index or selected_id not in corr_matrix.columns:
                        continue
                    corr_value = corr_matrix.loc[spec.component_id, selected_id]
                    if pd.notna(corr_value):
                        max_abs_corr = max(max_abs_corr, abs(float(corr_value)))
                        if abs(float(corr_value)) >= COMPONENT_CORR_THRESHOLD:
                            corr_blockers.append(selected_id)
                if corr_blockers and not validation_label.empty:
                    _, marginal_summary = compute_marginal_ic(
                        {**selected_series, spec.component_id: ranked},
                        validation_label,
                        list(selected_series.keys()),
                        spec.component_id,
                        min_obs=5,
                    )
                    marginal_rank_icir = float(marginal_summary.get("rank_icir", np.nan))
                    if pd.isna(marginal_rank_icir) or marginal_rank_icir <= MARGINAL_ICIR_THRESHOLD:
                        rejection_reason = f"与更强 component 高相关，且 marginal ICIR 不足 ({marginal_rank_icir:.3f})。"
                if not rejection_reason:
                    selected_for_recipe = True
                    selected_series[spec.component_id] = ranked
            diagnostics.append(
                ComponentDiagnostic(
                    component_id=spec.component_id,
                    theme_id=spec.theme_id,
                    coverage_ratio=coverage_ratio,
                    coverage_tier=spec.coverage_tier,
                    mean_rank_ic=mean_rank_ic,
                    rank_icir=rank_icir,
                    positive_validation_folds=positive_folds,
                    total_validation_folds=total_validation_folds,
                    direction_consistent=direction_consistent,
                    max_abs_corr=max_abs_corr,
                    marginal_rank_icir=float(marginal_rank_icir) if pd.notna(marginal_rank_icir) else np.nan,
                    cluster_id=cluster_map.get(spec.component_id, ""),
                    selection_score=selection_score,
                    selected_for_recipe=selected_for_recipe,
                    rejection_reason=rejection_reason,
                )
            )
        diagnostics.sort(key=lambda item: item.selection_score, reverse=True)
        return diagnostics, cluster_map

    def _build_recipe_candidates(
        self,
        theme_spec: ThemeSpec,
        specs_by_id: dict[str, ComponentSpec],
        diagnostics: list[ComponentDiagnostic],
    ) -> list[SignalRecipe]:
        selected = [item for item in diagnostics if item.selected_for_recipe]
        selected_by_role: dict[str, list[ComponentDiagnostic]] = {"core_thesis": [], "confirmation": [], "execution_guardrail": []}
        for item in selected:
            role = specs_by_id[item.component_id].economic_role
            if role in selected_by_role:
                selected_by_role[role].append(item)
        for role, limit in TOP_ROLE_LIMITS.items():
            selected_by_role[role] = selected_by_role[role][:limit]
        whitelist_ids = {item.component_id for item in selected}
        recipes = build_seed_recipes_for_theme(theme_spec.theme_id, whitelist_ids)
        seen_sets = {tuple(sorted(recipe.component_ids)) for recipe in recipes}
        auto_num = 1
        for core in selected_by_role["core_thesis"]:
            for conf in selected_by_role["confirmation"]:
                members = tuple(sorted((core.component_id, conf.component_id)))
                if len(set(members)) < 2 or members in seen_sets:
                    continue
                seen_sets.add(members)
                weight = 1.0 / len(members)
                recipes.append(
                    SignalRecipe(
                        recipe_id=f"auto_{theme_spec.theme_id}_{auto_num:02d}",
                        theme_id=theme_spec.theme_id,
                        component_ids=members,
                        weights=tuple(weight for _ in members),
                        construction_rule="1core_1confirmation_equal",
                        selection_note="\u81ea\u52a8\u7ec4\u5408\uff1a1 \u4e2a\u6838\u5fc3 component + 1 \u4e2a\u786e\u8ba4 component\u3002",
                    )
                )
                auto_num += 1
            for conf_left, conf_right in itertools.combinations(selected_by_role["confirmation"], 2):
                cluster_left = next((item.cluster_id for item in diagnostics if item.component_id == conf_left.component_id), "")
                cluster_right = next((item.cluster_id for item in diagnostics if item.component_id == conf_right.component_id), "")
                if cluster_left and cluster_left == cluster_right:
                    continue
                members = tuple(sorted((core.component_id, conf_left.component_id, conf_right.component_id)))
                if members in seen_sets:
                    continue
                seen_sets.add(members)
                weight = 1.0 / len(members)
                recipes.append(
                    SignalRecipe(
                        recipe_id=f"auto_{theme_spec.theme_id}_{auto_num:02d}",
                        theme_id=theme_spec.theme_id,
                        component_ids=members,
                        weights=tuple(weight for _ in members),
                        construction_rule="1core_2confirmation_equal",
                        selection_note="\u81ea\u52a8\u7ec4\u5408\uff1a1 \u4e2a\u6838\u5fc3 component + 2 \u4e2a\u786e\u8ba4 component\u3002",
                    )
                )
                auto_num += 1
            for guard in selected_by_role["execution_guardrail"]:
                for conf in selected_by_role["confirmation"]:
                    members = tuple(sorted((core.component_id, conf.component_id, guard.component_id)))
                    if len(set(members)) < 3 or members in seen_sets:
                        continue
                    seen_sets.add(members)
                    weight = 1.0 / len(members)
                    recipes.append(
                        SignalRecipe(
                            recipe_id=f"auto_{theme_spec.theme_id}_{auto_num:02d}",
                            theme_id=theme_spec.theme_id,
                            component_ids=members,
                            weights=tuple(weight for _ in members),
                            construction_rule="1core_1confirmation_1guard_equal",
                            selection_note="\u81ea\u52a8\u7ec4\u5408\uff1a\u6838\u5fc3 + \u786e\u8ba4 + \u6267\u884c\u7ea6\u675f\u3002",
                        )
                    )
                    auto_num += 1
        return recipes

    def _run_event_driven_confirmation(
        self,
        artifacts: ThemeArtifacts,
        specs_by_id: dict[str, ComponentSpec],
        recipe_summary: pd.DataFrame,
        theme_dir: Path,
    ) -> pd.DataFrame:
        if recipe_summary.empty:
            return pd.DataFrame()
        from workspace.research.alpha_mining.event_driven_strategy_research import run_event_driven_window
        from workspace.research.alpha_mining.event_driven_strategy_report import render_simple_backtest_html

        rows: list[dict[str, Any]] = []
        full_calendar = self._calendar_slice(artifacts, artifacts.theme_spec.data_start, artifacts.end_date)
        for _, row in recipe_summary.head(2).iterrows():
            universe = next(item for item in artifacts.theme_spec.universe_candidates if item.candidate_id == row["universe_id"])
            recipe = SignalRecipe(
                recipe_id=row["recipe_id"],
                theme_id=artifacts.theme_spec.theme_id,
                component_ids=tuple(row["component_ids"].split("|")),
                weights=tuple(float(item) for item in row["weights"].split("|")),
                construction_rule=row["construction_rule"],
                selection_note=row.get("selection_note", ""),
            )
            rebal_dates = build_rebalance_dates(full_calendar, int(row["rebalance_days"]))
            eligible_map = self._build_universe_eligible_map(artifacts, universe, rebal_dates)
            signal = self._combine_recipe_signal(artifacts, specs_by_id, recipe, eligible_map)
            perf_df, signal_df = self._simulate_portfolio(artifacts, signal, rebal_dates, int(row["topk"]))
            if signal_df.empty:
                continue
            schedule = {
                pd.Timestamp(date): {instrument: float(group.iloc[idx]["target_weight"]) for idx, instrument in enumerate(group["instrument"])}
                for date, group in signal_df.groupby("date")
            }
            try:
                bt_result = run_event_driven_window(
                    schedule=schedule,
                    start=artifacts.theme_spec.data_start,
                    end=artifacts.end_date,
                    benchmark=artifacts.theme_spec.benchmark,
                    capital=float(artifacts.theme_spec.event_driven_defaults.get("capital", 2_000_000.0)),
                    slippage_rate=float(artifacts.theme_spec.event_driven_defaults.get("slippage_rate", 0.0005)),
                )
            except Exception as exc:
                LOGGER.warning("Event-driven confirmation failed for %s/%s: %s", row["universe_id"], row["recipe_id"], exc)
                continue
            report = bt_result.report.copy()
            net_returns = (report["return"] - report["cost"]).astype(float)
            benchmark_returns = report["bench"].astype(float) if "bench" in report.columns else None
            perf_report = generate_performance_report(net_returns, benchmark_returns)
            yearly = calculate_yearly_returns(net_returns).to_frame("Strategy")
            monthly = calculate_monthly_return_table(net_returns)
            html = render_simple_backtest_html(
                title=f"{artifacts.theme_spec.theme_id} - {row['recipe_id']}",
                performance_report=perf_report,
                yearly_returns=yearly,
                monthly_table=monthly,
            )
            if not (theme_dir / "best_backtest_report.html").exists():
                write_markdown(theme_dir / "best_backtest_report.html", html)
                signal_df.to_parquet(theme_dir / "best_signal.parquet", index=False)
            rows.append(
                {
                    "theme_id": artifacts.theme_spec.theme_id,
                    "universe_id": row["universe_id"],
                    "recipe_id": row["recipe_id"],
                    "topk": int(row["topk"]),
                    "rebalance_days": int(row["rebalance_days"]),
                    "relative_excess_return": float(calculate_total_return(report["return"]) - calculate_total_return(report["bench"])) if "bench" in report.columns else np.nan,
                    "max_drawdown": float(calculate_max_drawdown(net_returns)),
                    "avg_turnover": float(report["turnover"].mean()) if "turnover" in report.columns else np.nan,
                    "trade_count": int(len(bt_result.trades)),
                }
            )
        return sort_event_summary_frame(pd.DataFrame(rows)) if rows else pd.DataFrame()

    def _resolve_recipe_source_theme_dir(self, recipe_source_run_dir: str | Path, theme_id: str) -> Path:
        source_root = Path(recipe_source_run_dir).resolve()
        if (source_root / "signal_recipe_summary.csv").exists():
            return source_root
        theme_dir = source_root / theme_id
        if theme_dir.exists():
            return theme_dir
        raise FileNotFoundError(
            f"Could not find theme recipe outputs for theme={theme_id} under {source_root}."
        )

    def _load_recipe_source_frames(
        self,
        *,
        theme_id: str,
        recipe_source_run_dir: str | Path,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        source_theme_dir = self._resolve_recipe_source_theme_dir(recipe_source_run_dir, theme_id)
        universe_path = source_theme_dir / "universe_search_summary.csv"
        component_path = source_theme_dir / "component_card.csv"
        recipe_path = source_theme_dir / "signal_recipe_summary.csv"
        cluster_path = source_theme_dir / "component_cluster_map.csv"
        required = [universe_path, component_path, recipe_path]
        missing = [str(path) for path in required if not path.exists()]
        if missing:
            raise FileNotFoundError(
                f"Quick event-driven mode is missing required recipe-stage artifacts: {missing}"
            )
        universe_summary = sort_universe_summary_frame(pd.read_csv(universe_path))
        component_card_df = pd.read_csv(component_path)
        recipe_summary = sort_variant_frame(pd.read_csv(recipe_path))
        if cluster_path.exists():
            cluster_df = pd.read_csv(cluster_path)
        else:
            cluster_cols = [item for item in ["universe_id", "component_id", "cluster_id"] if item in component_card_df.columns]
            cluster_df = component_card_df[cluster_cols].drop_duplicates().copy() if len(cluster_cols) == 3 else pd.DataFrame()
        return universe_summary, component_card_df, recipe_summary, cluster_df

    def _run_theme_event_driven_from_recipe_source(
        self,
        theme_spec: ThemeSpec,
        theme_dir: Path,
        recipe_source_run_dir: str | Path,
    ) -> dict[str, Any]:
        LOGGER.info(
            "Quick event-driven mode for %s: reusing recipe outputs from %s",
            theme_spec.theme_id,
            recipe_source_run_dir,
        )
        artifacts = self.prepare_theme(theme_spec)
        LOGGER.info(
            "Prepared theme artifacts: theme=%s fields=%d components=%d end_date=%s",
            theme_spec.theme_id,
            len(artifacts.field_inventory),
            len(artifacts.component_specs),
            artifacts.end_date,
        )
        pd.DataFrame([asdict(item) for item in artifacts.field_inventory]).to_csv(theme_dir / "field_inventory.csv", index=False, encoding="utf-8-sig")
        write_markdown(theme_dir / "field_inventory_zh.md", render_field_inventory_md(theme_spec, artifacts.field_inventory))
        pd.DataFrame([asdict(item) for item in artifacts.component_specs]).to_csv(theme_dir / "component_registry.csv", index=False, encoding="utf-8-sig")

        specs_by_id = {spec.component_id: spec for spec in artifacts.component_specs}
        universe_summary, component_card_df, recipe_summary, cluster_df = self._load_recipe_source_frames(
            theme_id=theme_spec.theme_id,
            recipe_source_run_dir=recipe_source_run_dir,
        )

        universe_summary.to_csv(theme_dir / "universe_search_summary.csv", index=False, encoding="utf-8-sig")
        top_universe_ids = universe_summary.head(2)["universe_id"].tolist() if not universe_summary.empty else []
        write_markdown(theme_dir / "universe_selection_rationale_zh.md", render_universe_selection_md(theme_spec, universe_summary))

        component_card_df.to_csv(theme_dir / "component_card.csv", index=False, encoding="utf-8-sig")
        cluster_df.to_csv(theme_dir / "component_cluster_map.csv", index=False, encoding="utf-8-sig")
        write_markdown(
            theme_dir / "component_selection_rationale_zh.md",
            render_component_selection_md(theme_spec, component_card_df, specs_by_id, top_universe_ids),
        )
        LOGGER.info(
            "Quick event-driven mode %s: loaded %d selected component rows from prior run",
            theme_spec.theme_id,
            int(component_card_df["selected_for_recipe"].sum()) if not component_card_df.empty and "selected_for_recipe" in component_card_df.columns else 0,
        )

        recipe_summary.to_csv(theme_dir / "signal_recipe_summary.csv", index=False, encoding="utf-8-sig")
        write_markdown(theme_dir / "signal_selection_rationale_zh.md", render_signal_selection_md(theme_spec, recipe_summary))
        LOGGER.info(
            "Quick event-driven mode %s: loaded %d recipe variants from prior run",
            theme_spec.theme_id,
            len(recipe_summary),
        )

        event_summary = self._run_event_driven_confirmation(artifacts, specs_by_id, recipe_summary, theme_dir)
        event_summary.to_csv(theme_dir / "event_driven_variant_summary.csv", index=False, encoding="utf-8-sig")
        write_markdown(
            theme_dir / "theme_review_zh.md",
            render_theme_review_md(theme_spec, top_universe_ids, component_card_df, recipe_summary, event_summary),
        )
        LOGGER.info("Theme %s finished quick event-driven confirmation", theme_spec.theme_id)
        best_row = recipe_summary.iloc[0].to_dict() if not recipe_summary.empty else {}
        return {
            "theme_id": theme_spec.theme_id,
            "best_universe_id": best_row.get("universe_id"),
            "best_recipe_id": best_row.get("recipe_id"),
            "best_stitched_relative_excess_return": best_row.get("stitched_relative_excess_return"),
            "best_holdout_relative_excess_return": best_row.get("holdout_relative_excess_return"),
        }

    def _load_universe_summary(self, theme_dir: Path) -> pd.DataFrame:
        path = theme_dir / "universe_search_summary.csv"
        if not path.exists():
            return pd.DataFrame()
        return sort_universe_summary_frame(pd.read_csv(path))

    def _load_component_card(self, theme_dir: Path) -> pd.DataFrame:
        path = theme_dir / "component_card.csv"
        if not path.exists():
            return pd.DataFrame()
        return pd.read_csv(path)

    def _load_recipe_summary(self, theme_dir: Path) -> pd.DataFrame:
        path = theme_dir / "signal_recipe_summary.csv"
        if not path.exists():
            return pd.DataFrame()
        return sort_variant_frame(pd.read_csv(path))

    def _component_diagnostics_from_frame(
        self,
        theme_spec: ThemeSpec,
        component_rows: pd.DataFrame,
    ) -> list[ComponentDiagnostic]:
        diagnostics: list[ComponentDiagnostic] = []
        if component_rows.empty:
            return diagnostics
        for _, row in component_rows.iterrows():
            diagnostics.append(
                ComponentDiagnostic(
                    component_id=str(row["component_id"]),
                    theme_id=theme_spec.theme_id,
                    coverage_ratio=float(row["coverage_ratio"]),
                    coverage_tier=str(row["coverage_tier"]),
                    mean_rank_ic=float(row["mean_rank_ic"]) if pd.notna(row["mean_rank_ic"]) else np.nan,
                    rank_icir=float(row["rank_icir"]) if pd.notna(row["rank_icir"]) else np.nan,
                    positive_validation_folds=int(row["positive_validation_folds"]),
                    total_validation_folds=int(row["total_validation_folds"]),
                    direction_consistent=bool(row["direction_consistent"]),
                    max_abs_corr=float(row["max_abs_corr"]) if pd.notna(row["max_abs_corr"]) else np.nan,
                    marginal_rank_icir=float(row["marginal_rank_icir"]) if pd.notna(row["marginal_rank_icir"]) else np.nan,
                    cluster_id=str(row["cluster_id"]),
                    selection_score=float(row["selection_score"]) if pd.notna(row["selection_score"]) else np.nan,
                    selected_for_recipe=bool(row["selected_for_recipe"]),
                    rejection_reason=str(row.get("rejection_reason", "") or ""),
                )
            )
        return diagnostics

    def run_field_audit_stage(
        self,
        theme_spec: ThemeSpec,
        theme_dir: Path,
        *,
        start_override: str | None = None,
        end_override: str | None = None,
    ) -> dict[str, Any]:
        artifacts = self.prepare_theme(
            theme_spec,
            start_override=start_override,
            end_override=end_override,
        )
        LOGGER.info(
            "Prepared theme artifacts: theme=%s fields=%d components=%d end_date=%s",
            theme_spec.theme_id,
            len(artifacts.field_inventory),
            len(artifacts.component_specs),
            artifacts.end_date,
        )
        pd.DataFrame([asdict(item) for item in artifacts.field_inventory]).to_csv(
            theme_dir / "field_inventory.csv",
            index=False,
            encoding="utf-8-sig",
        )
        write_markdown(
            theme_dir / "field_inventory_zh.md",
            render_field_inventory_md(theme_spec, artifacts.field_inventory),
        )
        pd.DataFrame([asdict(item) for item in artifacts.component_specs]).to_csv(
            theme_dir / "component_registry.csv",
            index=False,
            encoding="utf-8-sig",
        )
        manifest_path = write_prepared_theme_cache(artifacts, theme_dir)
        return {
            "artifacts": artifacts,
            "cache_manifest_path": str(manifest_path),
            "field_count": len(artifacts.field_inventory),
            "component_count": len(artifacts.component_specs),
            "start_date": start_override or theme_spec.data_start,
            "end_date": artifacts.end_date,
        }

    def run_universe_stage(
        self,
        theme_spec: ThemeSpec,
        theme_dir: Path,
        artifacts: ThemeArtifacts | None = None,
    ) -> dict[str, Any]:
        artifacts = artifacts or load_prepared_theme_cache(theme_spec, theme_dir, provider=self.provider)
        folds, holdout = build_walk_forward_folds(theme_spec.data_start, artifacts.end_date)
        specs_by_id = {spec.component_id: spec for spec in artifacts.component_specs}
        seed_recipes = build_seed_recipes_for_theme(theme_spec.theme_id, set(specs_by_id))

        universe_rows: list[dict[str, Any]] = []
        total_universes = len(theme_spec.universe_candidates)
        for universe_idx, universe in enumerate(theme_spec.universe_candidates, start=1):
            LOGGER.info(
                "Universe search %s: evaluating universe %s (%d/%d)",
                theme_spec.theme_id,
                universe.candidate_id,
                universe_idx,
                total_universes,
            )
            anchor_rows: list[dict[str, Any]] = []
            for recipe in seed_recipes:
                if recipe.recipe_id not in theme_spec.anchor_recipes:
                    continue
                for topk, rebalance_days in itertools.product(
                    theme_spec.topk_grid,
                    theme_spec.rebalance_grid,
                ):
                    summary, _ = self.evaluate_recipe_variant(
                        artifacts,
                        universe,
                        recipe,
                        topk,
                        rebalance_days,
                        folds,
                        holdout,
                        specs_by_id,
                    )
                    anchor_rows.append(asdict(summary))
            if anchor_rows:
                anchor_df = pd.DataFrame(anchor_rows)
                universe_rows.append(
                    {
                        "theme_id": theme_spec.theme_id,
                        "universe_id": universe.candidate_id,
                        "median_stitched_relative_excess_return": safe_median(anchor_df["stitched_relative_excess_return"]),
                        "median_positive_excess_folds": safe_median(anchor_df["positive_excess_folds"]),
                        "median_holdout_relative_excess_return": safe_median(anchor_df["holdout_relative_excess_return"]),
                        "median_worst_max_drawdown": safe_median(anchor_df["worst_max_drawdown"]),
                        "median_avg_turnover": safe_median(anchor_df["avg_turnover"]),
                    }
                )
                LOGGER.info(
                    "Universe search %s: universe %s finished with median OOS excess %.4f",
                    theme_spec.theme_id,
                    universe.candidate_id,
                    safe_median(anchor_df["stitched_relative_excess_return"]),
                )

        universe_summary = pd.DataFrame(universe_rows)
        if not universe_summary.empty:
            universe_summary = sort_universe_summary_frame(universe_summary)
        universe_summary.to_csv(
            theme_dir / "universe_search_summary.csv",
            index=False,
            encoding="utf-8-sig",
        )
        top_universe_ids = (
            universe_summary.head(2)["universe_id"].tolist() if not universe_summary.empty else []
        )
        write_markdown(
            theme_dir / "universe_selection_rationale_zh.md",
            render_universe_selection_md(theme_spec, universe_summary),
        )
        LOGGER.info(
            "Universe search %s: selected top universes=%s",
            theme_spec.theme_id,
            top_universe_ids,
        )
        return {
            "artifacts": artifacts,
            "universe_summary": universe_summary,
            "top_universe_ids": top_universe_ids,
        }

    def run_component_stage(
        self,
        theme_spec: ThemeSpec,
        theme_dir: Path,
        artifacts: ThemeArtifacts | None = None,
        universe_summary: pd.DataFrame | None = None,
    ) -> dict[str, Any]:
        artifacts = artifacts or load_prepared_theme_cache(theme_spec, theme_dir, provider=self.provider)
        universe_summary = universe_summary if universe_summary is not None else self._load_universe_summary(theme_dir)
        top_universe_ids = (
            universe_summary.head(2)["universe_id"].tolist() if not universe_summary.empty else []
        )
        folds, _ = build_walk_forward_folds(theme_spec.data_start, artifacts.end_date)
        specs_by_id = {spec.component_id: spec for spec in artifacts.component_specs}
        component_cards: list[dict[str, Any]] = []
        cluster_rows: list[dict[str, Any]] = []
        total_selected_universes = len(top_universe_ids)
        for universe_rank, universe_id in enumerate(top_universe_ids, start=1):
            LOGGER.info(
                "Component search %s: diagnostics for universe %s (%d/%d)",
                theme_spec.theme_id,
                universe_id,
                universe_rank,
                total_selected_universes,
            )
            universe = next(
                item for item in theme_spec.universe_candidates if item.candidate_id == universe_id
            )
            diagnostics, cluster_map = self.compute_component_diagnostics(
                artifacts,
                universe,
                specs_by_id,
                folds,
            )
            component_cards.extend(
                [asdict(item) | {"universe_id": universe_id} for item in diagnostics]
            )
            cluster_rows.extend(
                [
                    {
                        "universe_id": universe_id,
                        "component_id": component_id,
                        "cluster_id": cluster_id,
                    }
                    for component_id, cluster_id in cluster_map.items()
                ]
            )

        component_card_df = pd.DataFrame(component_cards)
        cluster_df = pd.DataFrame(cluster_rows)
        component_card_df.to_csv(
            theme_dir / "component_card.csv",
            index=False,
            encoding="utf-8-sig",
        )
        cluster_df.to_csv(
            theme_dir / "component_cluster_map.csv",
            index=False,
            encoding="utf-8-sig",
        )
        write_markdown(
            theme_dir / "component_selection_rationale_zh.md",
            render_component_selection_md(theme_spec, component_card_df, specs_by_id, top_universe_ids),
        )
        LOGGER.info(
            "Component search %s: selected-for-recipe count=%d",
            theme_spec.theme_id,
            int(component_card_df["selected_for_recipe"].sum()) if not component_card_df.empty else 0,
        )
        return {
            "artifacts": artifacts,
            "component_card_df": component_card_df,
            "cluster_df": cluster_df,
            "top_universe_ids": top_universe_ids,
            "specs_by_id": specs_by_id,
        }

    def run_recipe_stage(
        self,
        theme_spec: ThemeSpec,
        theme_dir: Path,
        artifacts: ThemeArtifacts | None = None,
        universe_summary: pd.DataFrame | None = None,
        component_card_df: pd.DataFrame | None = None,
    ) -> dict[str, Any]:
        artifacts = artifacts or load_prepared_theme_cache(theme_spec, theme_dir, provider=self.provider)
        universe_summary = universe_summary if universe_summary is not None else self._load_universe_summary(theme_dir)
        component_card_df = component_card_df if component_card_df is not None else self._load_component_card(theme_dir)
        top_universe_ids = (
            universe_summary.head(2)["universe_id"].tolist() if not universe_summary.empty else []
        )
        folds, holdout = build_walk_forward_folds(theme_spec.data_start, artifacts.end_date)
        specs_by_id = {spec.component_id: spec for spec in artifacts.component_specs}
        recipe_rows: list[dict[str, Any]] = []
        total_selected_universes = len(top_universe_ids)
        for universe_rank, universe_id in enumerate(top_universe_ids, start=1):
            LOGGER.info(
                "Recipe search %s: preparing recipes for universe %s (%d/%d)",
                theme_spec.theme_id,
                universe_id,
                universe_rank,
                total_selected_universes,
            )
            universe = next(
                item for item in theme_spec.universe_candidates if item.candidate_id == universe_id
            )
            diagnostics = self._component_diagnostics_from_frame(
                theme_spec,
                component_card_df.loc[component_card_df["universe_id"] == universe_id].copy(),
            )
            recipe_candidates = self._build_recipe_candidates(theme_spec, specs_by_id, diagnostics)
            total_recipe_variants = (
                len(recipe_candidates) * len(theme_spec.topk_grid) * len(theme_spec.rebalance_grid)
            )
            LOGGER.info(
                "Recipe search %s: built %d candidate recipes for universe %s, %d vectorized variants to score",
                theme_spec.theme_id,
                len(recipe_candidates),
                universe_id,
                total_recipe_variants,
            )
            recipe_eval_count = 0
            for recipe in recipe_candidates:
                for topk, rebalance_days in itertools.product(
                    theme_spec.topk_grid,
                    theme_spec.rebalance_grid,
                ):
                    summary, _ = self.evaluate_recipe_variant(
                        artifacts,
                        universe,
                        recipe,
                        topk,
                        rebalance_days,
                        folds,
                        holdout,
                        specs_by_id,
                    )
                    recipe_rows.append(
                        asdict(summary)
                        | {
                            "component_ids": "|".join(recipe.component_ids),
                            "weights": "|".join(str(weight) for weight in recipe.weights),
                            "construction_rule": recipe.construction_rule,
                            "selection_note": recipe.selection_note,
                        }
                    )
                    recipe_eval_count += 1
                    if recipe_eval_count == total_recipe_variants or recipe_eval_count % 10 == 0:
                        LOGGER.info(
                            "Recipe search %s: scored %d/%d variants for universe %s",
                            theme_spec.theme_id,
                            recipe_eval_count,
                            total_recipe_variants,
                            universe_id,
                        )

        recipe_summary = sort_variant_frame(pd.DataFrame(recipe_rows))
        recipe_summary.to_csv(
            theme_dir / "signal_recipe_summary.csv",
            index=False,
            encoding="utf-8-sig",
        )
        write_markdown(
            theme_dir / "signal_selection_rationale_zh.md",
            render_signal_selection_md(theme_spec, recipe_summary),
        )
        LOGGER.info(
            "Recipe search %s: total scored variants=%d",
            theme_spec.theme_id,
            len(recipe_summary),
        )
        return {
            "artifacts": artifacts,
            "recipe_summary": recipe_summary,
            "component_card_df": component_card_df,
            "top_universe_ids": top_universe_ids,
            "specs_by_id": specs_by_id,
        }

    def run_event_driven_stage(
        self,
        theme_spec: ThemeSpec,
        theme_dir: Path,
        artifacts: ThemeArtifacts | None = None,
        universe_summary: pd.DataFrame | None = None,
        component_card_df: pd.DataFrame | None = None,
        recipe_summary: pd.DataFrame | None = None,
    ) -> dict[str, Any]:
        artifacts = artifacts or load_prepared_theme_cache(theme_spec, theme_dir, provider=self.provider)
        universe_summary = universe_summary if universe_summary is not None else self._load_universe_summary(theme_dir)
        component_card_df = component_card_df if component_card_df is not None else self._load_component_card(theme_dir)
        recipe_summary = recipe_summary if recipe_summary is not None else self._load_recipe_summary(theme_dir)
        top_universe_ids = (
            universe_summary.head(2)["universe_id"].tolist() if not universe_summary.empty else []
        )
        specs_by_id = {spec.component_id: spec for spec in artifacts.component_specs}
        event_summary = self._run_event_driven_confirmation(
            artifacts,
            specs_by_id,
            recipe_summary,
            theme_dir,
        )
        event_summary.to_csv(
            theme_dir / "event_driven_variant_summary.csv",
            index=False,
            encoding="utf-8-sig",
        )
        write_markdown(
            theme_dir / "theme_review_zh.md",
            render_theme_review_md(
                theme_spec,
                top_universe_ids,
                component_card_df,
                recipe_summary,
                event_summary,
            ),
        )
        LOGGER.info("Theme %s finished event-driven confirmation", theme_spec.theme_id)
        return {
            "artifacts": artifacts,
            "event_summary": event_summary,
            "component_card_df": component_card_df,
            "recipe_summary": recipe_summary,
            "top_universe_ids": top_universe_ids,
            "specs_by_id": specs_by_id,
        }

    def run_theme(
        self,
        theme_id: str,
        stage: str = "all",
        recipe_source_run_dir: str | Path | None = None,
    ) -> dict[str, Any]:
        theme_spec = get_theme_spec(theme_id)
        theme_dir = self.output_root / theme_spec.theme_id
        theme_dir.mkdir(parents=True, exist_ok=True)
        LOGGER.info("Starting theme run: theme=%s stage=%s output=%s", theme_id, stage, theme_dir)
        if recipe_source_run_dir and stage == "event_driven":
            return self._run_theme_event_driven_from_recipe_source(
                theme_spec,
                theme_dir,
                recipe_source_run_dir,
            )
        field_result = self.run_field_audit_stage(theme_spec, theme_dir)
        artifacts = field_result["artifacts"]
        if stage == "field_audit":
            LOGGER.info("Field audit stage finished for theme=%s", theme_spec.theme_id)
            return {"theme_id": theme_spec.theme_id}

        universe_result = self.run_universe_stage(theme_spec, theme_dir, artifacts=artifacts)
        universe_summary = universe_result["universe_summary"]
        top_universe_ids = universe_result["top_universe_ids"]
        if stage == "universe":
            return {
                "theme_id": theme_spec.theme_id,
                "best_universe_id": top_universe_ids[0] if top_universe_ids else None,
            }

        component_result = self.run_component_stage(
            theme_spec,
            theme_dir,
            artifacts=artifacts,
            universe_summary=universe_summary,
        )
        component_card_df = component_result["component_card_df"]
        if stage == "component":
            return {
                "theme_id": theme_spec.theme_id,
                "best_universe_id": top_universe_ids[0] if top_universe_ids else None,
                "selected_components": int(component_card_df["selected_for_recipe"].sum()) if not component_card_df.empty else 0,
            }

        recipe_result = self.run_recipe_stage(
            theme_spec,
            theme_dir,
            artifacts=artifacts,
            universe_summary=universe_summary,
            component_card_df=component_card_df,
        )
        recipe_summary = recipe_result["recipe_summary"]
        if stage == "recipe":
            best_row = recipe_summary.iloc[0].to_dict() if not recipe_summary.empty else {}
            return {
                "theme_id": theme_spec.theme_id,
                "best_universe_id": best_row.get("universe_id"),
                "best_recipe_id": best_row.get("recipe_id"),
                "best_stitched_relative_excess_return": best_row.get("stitched_relative_excess_return"),
                "best_holdout_relative_excess_return": best_row.get("holdout_relative_excess_return"),
            }

        self.run_event_driven_stage(
            theme_spec,
            theme_dir,
            artifacts=artifacts,
            universe_summary=universe_summary,
            component_card_df=component_card_df,
            recipe_summary=recipe_summary,
        )
        LOGGER.info("Theme %s finished all stages", theme_spec.theme_id)
        best_row = recipe_summary.iloc[0].to_dict() if not recipe_summary.empty else {}
        return {
            "theme_id": theme_spec.theme_id,
            "best_universe_id": best_row.get("universe_id"),
            "best_recipe_id": best_row.get("recipe_id"),
            "best_stitched_relative_excess_return": best_row.get("stitched_relative_excess_return"),
            "best_holdout_relative_excess_return": best_row.get("holdout_relative_excess_return"),
        }

    def run(
        self,
        theme: str = "all",
        stage: str = "all",
        recipe_source_run_dir: str | Path | None = None,
    ) -> Path:
        theme_ids = list(get_theme_specs().keys()) if theme == "all" else [theme]
        ranking_rows: list[dict[str, Any]] = []
        for theme_id in theme_ids:
            ranking_rows.append(
                self.run_theme(
                    theme_id,
                    stage=stage,
                    recipe_source_run_dir=recipe_source_run_dir,
                )
            )
        ranking_df = pd.DataFrame(ranking_rows)
        ranking_df.to_csv(self.output_root / "theme_opportunity_ranking.csv", index=False, encoding="utf-8-sig")
        write_markdown(self.output_root / "market_opportunity_summary_zh.md", render_market_summary_md(self.output_root, ranking_df, stage))
        write_markdown(self.output_root / "future_theme_backlog.md", render_future_backlog_md(stage, ranking_df))
        return self.output_root


def build_universe_eligibility(
    *,
    raw_fields,
    support,
    universe,
    rebal_dates,
    listing_days_ok,
):
    """Public reusable eligibility-map builder (jolly-seeking-lollipop Gate C).

    Extracted from ThemeStrategyPipeline._build_universe_eligible_map so that
    prescription_runtime.materialize_universe can call it directly for both
    themed and broad universes.

    Args:
        raw_fields: dict of {field_name: Series} as in ThemeArtifacts.raw_fields.
            At minimum needs close, adj_factor, total_mv, amount; other keys
            are referenced only when the corresponding universe filter is set
            (e.g., revenue_q only used if revenue_floor is set).
        support: ResearchSupport bundle with stock_basic_map, st_ranges,
            listing_dates_map, index_membership_store.
        universe: a UniverseCandidate describing the filter set.
        rebal_dates: trading-day timestamps for which to materialize the map.
        listing_days_ok: callable (code, date) -> bool that checks the
            min_listing_days predicate. Passed in so callers can plug in
            their own listing-age logic without duplicating ResearchSupport.

    Returns:
        dict[date -> set of qlib_code]: eligible instruments per rebalance date.
    """
    close = raw_fields.get("close")
    total_mv = raw_fields.get("total_mv")
    revenue_q = raw_fields.get("revenue_q")
    ratio = raw_fields.get("ratio")
    amount = raw_fields.get("amount")
    adv20 = (
        None if amount is None
        else amount.groupby(level="instrument").transform(
            lambda values: values.rolling(20, min_periods=10).mean()
        ) * 1000.0
    )
    profit_field = (
        raw_fields.get(universe.profitability_field)
        if universe.profitability_field else None
    )
    ret250_pctile = None
    if close is not None:
        price_series = close * raw_fields.get("adj_factor", 1.0)
        ret250 = price_series.groupby(level="instrument").pct_change(250, fill_method=None)
        ret250_pctile = ret250.groupby(level="datetime").rank(pct=True)
    eligible_map = {}
    for date in rebal_dates:
        try:
            daily_close = (
                close.xs(date, level="datetime").dropna()
                if close is not None else pd.Series(dtype=float)
            )
        except KeyError:
            eligible_map[date] = set()
            continue
        daily_total_mv = (
            total_mv.xs(date, level="datetime") if total_mv is not None else pd.Series(dtype=float)
        )
        daily_adv20 = (
            adv20.xs(date, level="datetime") if adv20 is not None else pd.Series(dtype=float)
        )
        daily_revenue_q = (
            revenue_q.xs(date, level="datetime") if revenue_q is not None else pd.Series(dtype=float)
        )
        daily_profit = (
            profit_field.xs(date, level="datetime") if profit_field is not None else pd.Series(dtype=float)
        )
        daily_ratio = (
            ratio.xs(date, level="datetime") if ratio is not None else pd.Series(dtype=float)
        )
        daily_ret250_pctile = (
            ret250_pctile.xs(date, level="datetime") if ret250_pctile is not None else pd.Series(dtype=float)
        )
        codes = set(daily_close.index.tolist())
        if universe.membership_source == "csi300":
            codes &= support.index_membership_store.members_on("000300.SH", date)
        elif universe.membership_source == "csi500":
            codes &= support.index_membership_store.members_on("000905.SH", date)
        elif universe.membership_source == "csi1000":
            codes &= support.index_membership_store.members_on("000852.SH", date)
        filtered = set()
        for code in codes:
            if not listing_days_ok(code, date):
                continue
            ref = (
                support.stock_basic_map.loc[code]
                if code in support.stock_basic_map.index else None
            )
            if ref is None:
                continue
            if universe.board_policy == "mainboard" and str(ref.get("market", "")) != "\u4e3b\u677f":
                continue
            is_st = is_st_on_date(code, date, support.st_ranges)
            if universe.st_mode == "exclude" and is_st:
                continue
            if universe.st_mode == "include_only" and not is_st:
                continue
            if universe.price_cap is not None and float(daily_close.get(code, np.nan)) > float(universe.price_cap):
                continue
            if universe.market_cap_min is not None and total_mv is not None:
                market_cap_cny = float(daily_total_mv.get(code, np.nan)) * 10_000.0
                if market_cap_cny < float(universe.market_cap_min):
                    continue
            if universe.market_cap_max is not None and total_mv is not None:
                market_cap_cny = float(daily_total_mv.get(code, np.nan)) * 10_000.0
                if market_cap_cny > float(universe.market_cap_max):
                    continue
            if universe.liquidity_floor is not None and adv20 is not None:
                if float(daily_adv20.get(code, np.nan)) < float(universe.liquidity_floor):
                    continue
            if universe.revenue_floor is not None and revenue_q is not None:
                if float(daily_revenue_q.get(code, np.nan)) < float(universe.revenue_floor):
                    continue
            if universe.profitability_positive and profit_field is not None:
                if float(daily_profit.get(code, np.nan)) <= 0.0:
                    continue
            if universe.northbound_required and ratio is not None:
                if pd.isna(daily_ratio.get(code, np.nan)):
                    continue
            if universe.ret250_pctile_max is not None and ret250_pctile is not None:
                if float(daily_ret250_pctile.get(code, np.nan)) > float(universe.ret250_pctile_max):
                    continue
            filtered.add(code)
        eligible_map[pd.Timestamp(date)] = filtered
    return eligible_map

