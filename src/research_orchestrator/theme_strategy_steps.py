from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.alpha_research.theme_strategy.pipeline import (
    ThemeStrategyPipeline,
    render_future_backlog_md,
    render_market_summary_md,
)
from src.alpha_research.theme_strategy.registry import get_theme_spec, get_theme_specs


def resolve_theme_ids(theme: str) -> list[str]:
    return list(get_theme_specs().keys()) if theme == "all" else [theme]


def _write_stage_root_outputs(
    *,
    output_root: Path,
    ranking_rows: list[dict[str, Any]],
    stage: str,
) -> pd.DataFrame:
    ranking_df = pd.DataFrame(ranking_rows)
    ranking_df.to_csv(
        output_root / "theme_opportunity_ranking.csv",
        index=False,
        encoding="utf-8-sig",
    )
    (output_root / "market_opportunity_summary_zh.md").write_text(
        render_market_summary_md(output_root, ranking_df, stage),
        encoding="utf-8",
    )
    (output_root / "future_theme_backlog.md").write_text(
        render_future_backlog_md(stage, ranking_df),
        encoding="utf-8",
    )
    return ranking_df


def run_theme_dataset_build_step(
    *,
    output_root: Path,
    theme: str,
    start_override: str | None = None,
    end_override: str | None = None,
) -> dict[str, Any]:
    pipeline = ThemeStrategyPipeline(output_root=output_root)
    theme_ids = resolve_theme_ids(theme)
    ranking_rows: list[dict[str, Any]] = []
    for theme_id in theme_ids:
        theme_spec = get_theme_spec(theme_id)
        theme_dir = output_root / theme_spec.theme_id
        theme_dir.mkdir(parents=True, exist_ok=True)
        field_result = pipeline.run_field_audit_stage(
            theme_spec,
            theme_dir,
            start_override=start_override,
            end_override=end_override,
        )
        ranking_rows.append(
            {
                "theme_id": theme_spec.theme_id,
                "field_count": int(field_result["field_count"]),
                "component_count": int(field_result["component_count"]),
                "start_date": str(field_result["start_date"]),
                "end_date": str(field_result["end_date"]),
            }
        )
    ranking_df = _write_stage_root_outputs(output_root=output_root, ranking_rows=ranking_rows, stage="field_audit")
    return {
        "run_dir": output_root,
        "theme_ids": theme_ids,
        "stage": "field_audit",
        "ranking_rows": len(ranking_df),
        "ranking": ranking_rows,
    }


def run_theme_universe_step(
    *,
    output_root: Path,
    theme: str,
) -> dict[str, Any]:
    pipeline = ThemeStrategyPipeline(output_root=output_root)
    theme_ids = resolve_theme_ids(theme)
    ranking_rows: list[dict[str, Any]] = []
    for theme_id in theme_ids:
        theme_spec = get_theme_spec(theme_id)
        theme_dir = output_root / theme_spec.theme_id
        theme_dir.mkdir(parents=True, exist_ok=True)
        universe_result = pipeline.run_universe_stage(theme_spec, theme_dir)
        top_universe_ids = universe_result["top_universe_ids"]
        ranking_rows.append(
            {
                "theme_id": theme_spec.theme_id,
                "best_universe_id": top_universe_ids[0] if top_universe_ids else None,
            }
        )
    ranking_df = _write_stage_root_outputs(output_root=output_root, ranking_rows=ranking_rows, stage="universe")
    return {
        "run_dir": output_root,
        "theme_ids": theme_ids,
        "stage": "universe",
        "ranking_rows": len(ranking_df),
        "ranking": ranking_rows,
    }


def run_theme_component_step(
    *,
    output_root: Path,
    theme: str,
) -> dict[str, Any]:
    pipeline = ThemeStrategyPipeline(output_root=output_root)
    theme_ids = resolve_theme_ids(theme)
    ranking_rows: list[dict[str, Any]] = []
    for theme_id in theme_ids:
        theme_spec = get_theme_spec(theme_id)
        theme_dir = output_root / theme_spec.theme_id
        theme_dir.mkdir(parents=True, exist_ok=True)
        universe_summary = pipeline._load_universe_summary(theme_dir)
        top_universe_ids = universe_summary.head(2)["universe_id"].tolist() if not universe_summary.empty else []
        component_result = pipeline.run_component_stage(
            theme_spec,
            theme_dir,
            universe_summary=universe_summary,
        )
        component_card_df = component_result["component_card_df"]
        ranking_rows.append(
            {
                "theme_id": theme_spec.theme_id,
                "best_universe_id": top_universe_ids[0] if top_universe_ids else None,
                "selected_components": int(component_card_df["selected_for_recipe"].sum())
                if not component_card_df.empty
                else 0,
            }
        )
    ranking_df = _write_stage_root_outputs(output_root=output_root, ranking_rows=ranking_rows, stage="component")
    return {
        "run_dir": output_root,
        "theme_ids": theme_ids,
        "stage": "component",
        "ranking_rows": len(ranking_df),
        "ranking": ranking_rows,
    }


def run_theme_recipe_step(
    *,
    output_root: Path,
    theme: str,
) -> dict[str, Any]:
    pipeline = ThemeStrategyPipeline(output_root=output_root)
    theme_ids = resolve_theme_ids(theme)
    ranking_rows: list[dict[str, Any]] = []
    for theme_id in theme_ids:
        theme_spec = get_theme_spec(theme_id)
        theme_dir = output_root / theme_spec.theme_id
        theme_dir.mkdir(parents=True, exist_ok=True)
        universe_summary = pipeline._load_universe_summary(theme_dir)
        component_card_df = pipeline._load_component_card(theme_dir)
        recipe_result = pipeline.run_recipe_stage(
            theme_spec,
            theme_dir,
            universe_summary=universe_summary,
            component_card_df=component_card_df,
        )
        recipe_summary = recipe_result["recipe_summary"]
        best_row = recipe_summary.iloc[0].to_dict() if not recipe_summary.empty else {}
        ranking_rows.append(
            {
                "theme_id": theme_spec.theme_id,
                "best_universe_id": best_row.get("universe_id"),
                "best_recipe_id": best_row.get("recipe_id"),
                "best_stitched_relative_excess_return": best_row.get(
                    "stitched_relative_excess_return"
                ),
                "best_holdout_relative_excess_return": best_row.get(
                    "holdout_relative_excess_return"
                ),
            }
        )
    ranking_df = _write_stage_root_outputs(output_root=output_root, ranking_rows=ranking_rows, stage="recipe")
    return {
        "run_dir": output_root,
        "theme_ids": theme_ids,
        "stage": "recipe",
        "ranking_rows": len(ranking_df),
        "ranking": ranking_rows,
    }


def run_theme_event_driven_step(
    *,
    output_root: Path,
    theme: str,
    recipe_source_run_dir: str | Path | None = None,
    stage: str = "is_only",
) -> dict[str, Any]:
    del stage
    pipeline = ThemeStrategyPipeline(output_root=output_root)
    theme_ids = resolve_theme_ids(theme)
    ranking_rows: list[dict[str, Any]] = []
    for theme_id in theme_ids:
        theme_spec = get_theme_spec(theme_id)
        theme_dir = output_root / theme_spec.theme_id
        theme_dir.mkdir(parents=True, exist_ok=True)
        if recipe_source_run_dir:
            ranking_rows.append(
                pipeline._run_theme_event_driven_from_recipe_source(
                    theme_spec,
                    theme_dir,
                    recipe_source_run_dir,
                )
            )
            continue

        universe_summary = pipeline._load_universe_summary(theme_dir)
        component_card_df = pipeline._load_component_card(theme_dir)
        recipe_summary = pipeline._load_recipe_summary(theme_dir)
        event_result = pipeline.run_event_driven_stage(
            theme_spec,
            theme_dir,
            universe_summary=universe_summary,
            component_card_df=component_card_df,
            recipe_summary=recipe_summary,
        )
        best_recipe_row = recipe_summary.iloc[0].to_dict() if not recipe_summary.empty else {}
        best_event_row = (
            event_result["event_summary"].iloc[0].to_dict()
            if not event_result["event_summary"].empty
            else {}
        )
        ranking_rows.append(
            {
                "theme_id": theme_spec.theme_id,
                "best_universe_id": best_recipe_row.get("universe_id"),
                "best_recipe_id": best_recipe_row.get("recipe_id"),
                "best_stitched_relative_excess_return": best_recipe_row.get(
                    "stitched_relative_excess_return"
                ),
                "best_holdout_relative_excess_return": best_recipe_row.get(
                    "holdout_relative_excess_return"
                ),
                "best_event_relative_excess_return": best_event_row.get(
                    "relative_excess_return"
                ),
                "best_event_max_drawdown": best_event_row.get("max_drawdown"),
            }
        )
    ranking_df = _write_stage_root_outputs(
        output_root=output_root,
        ranking_rows=ranking_rows,
        stage="event_driven",
    )
    return {
        "run_dir": output_root,
        "theme_ids": theme_ids,
        "stage": "event_driven",
        "ranking_rows": len(ranking_df),
        "ranking": ranking_rows,
    }


def run_theme_stage(
    *,
    output_root: Path,
    theme: str,
    stage: str,
    recipe_source_run_dir: str | Path | None = None,
) -> dict[str, Any]:
    if stage == "field_audit":
        return run_theme_dataset_build_step(output_root=output_root, theme=theme)
    if stage == "universe":
        return run_theme_universe_step(output_root=output_root, theme=theme)
    if stage == "component":
        return run_theme_component_step(output_root=output_root, theme=theme)
    if stage == "recipe":
        return run_theme_recipe_step(output_root=output_root, theme=theme)
    if stage in {"event_driven", "all"}:
        return run_theme_event_driven_step(
            output_root=output_root,
            theme=theme,
            recipe_source_run_dir=recipe_source_run_dir,
        )
    raise ValueError(f"Unsupported theme stage: {stage}")
