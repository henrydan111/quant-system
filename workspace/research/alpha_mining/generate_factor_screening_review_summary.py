"""
Build a review-friendly markdown summary for batch factor screening runs.

The generated document is intended for human review:
- high-level takeaways at the top
- all factors visible in the body
- graceful fallback to a failure report when the run did not complete
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Iterable

import pandas as pd


TITLE = "Batch Factor Screening Review (Latest Backend, New-Data Included)"
GRADE_ORDER = [
    "A (Graduated)",
    "B (Strong IC)",
    "C (Moderate)",
    "D (Weak)",
]
NEW_DATA_PREFIXES = ("flow_", "north_", "margin_", "earn_")
NEW_DATA_KEYWORDS = ("forecast", "holder", "limit")
SUCCESS_ARTIFACTS = [
    "factor_screening_results.parquet",
    "factor_screening_report.csv",
    "factor_screening_summary.txt",
    "factor_screening_run_metadata.json",
    "run_console.log",
    "factor_screening_review_summary.md",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate factor screening review markdown")
    parser.add_argument(
        "--run-dir",
        required=True,
        help="Directory containing one screening run's artifacts",
    )
    parser.add_argument(
        "--summary-path",
        default=None,
        help="Optional explicit output path for the markdown summary",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def artifact_status(run_dir: Path) -> list[tuple[str, bool, int]]:
    status = []
    for name in SUCCESS_ARTIFACTS:
        path = run_dir / name
        status.append((name, path.exists(), path.stat().st_size if path.exists() else 0))
    return status


def normalize_metadata(metadata: dict) -> dict:
    requested = metadata.get("requested_kernels")
    effective = metadata.get("effective_kernels")
    legacy = metadata.get("kernels")
    if requested is None and legacy is not None:
        requested = str(legacy)
    if effective is None and legacy is not None:
        effective = str(legacy)
    metadata = dict(metadata)
    metadata["requested_kernels"] = requested or "unknown"
    metadata["effective_kernels"] = effective or metadata["requested_kernels"]
    return metadata


def load_report(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "Unnamed: 0" in df.columns and "factor" not in df.columns:
        df = df.rename(columns={"Unnamed: 0": "factor"})
    if "factor" not in df.columns:
        raise ValueError("factor_screening_report.csv does not contain a factor column")
    if "abs_icir" not in df.columns:
        fallback_cols = [c for c in df.columns if c.startswith("rank_icir_")]
        if fallback_cols:
            df["abs_icir"] = df[fallback_cols[0]].abs()
        else:
            df["abs_icir"] = 0.0
    return df.sort_values(["abs_icir", "factor"], ascending=[False, True]).reset_index(drop=True)


def read_log_tail(log_path: Path, max_lines: int = 80) -> list[str]:
    if not log_path.exists():
        return []
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-max_lines:]


def last_error_excerpt(lines: list[str]) -> list[str]:
    if not lines:
        return []
    error_markers = ("Traceback", "ERROR", "Exception", "PermissionError", "OSError")
    start = None
    for idx in range(len(lines) - 1, -1, -1):
        if any(marker in lines[idx] for marker in error_markers):
            start = idx
            break
    if start is None:
        return lines[-20:]
    return lines[start:]


def is_new_data_factor(name: str) -> bool:
    return name.startswith(NEW_DATA_PREFIXES) or any(keyword in name for keyword in NEW_DATA_KEYWORDS)


def stringify_bool(value) -> str:
    if pd.isna(value):
        return ""
    return "Y" if bool(value) else "N"


def format_value(column: str, value) -> str:
    if pd.isna(value):
        return ""
    if column in {"factor", "grade", "warning_flags"}:
        return str(value)
    if column == "monotonic":
        return stringify_bool(value)
    if column == "ls_ann_return":
        return f"{float(value):+.1%}"
    if column.startswith("ic_hit_rate_") or column.endswith("_coverage_primary"):
        return f"{float(value):.1%}"
    if column.startswith("rank_icir_") or column.startswith("mean_rank_ic_") or column == "abs_icir":
        return f"{float(value):+.3f}"
    return str(value)


def markdown_table(df: pd.DataFrame, columns: list[str], rename: dict[str, str] | None = None) -> str:
    rename = rename or {}
    available = [column for column in columns if column in df.columns]
    header = [rename.get(column, column) for column in available]
    rows = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * len(header)) + " |"]
    for _, row in df[available].iterrows():
        cells = [format_value(column, row[column]) for column in available]
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def warning_counter(series: Iterable[str]) -> Counter:
    counter: Counter = Counter()
    for value in series:
        if pd.isna(value) or not str(value).strip():
            continue
        for flag in str(value).split(","):
            cleaned = flag.strip()
            if cleaned:
                counter[cleaned] += 1
    return counter


def family_label(name: str) -> str:
    if name.startswith("flow_"):
        return "moneyflow / flow"
    if name.startswith("north_"):
        return "northbound / north"
    if name.startswith("margin_"):
        return "margin"
    if name.startswith("earn_"):
        return "earnings"
    if "forecast" in name:
        return "forecast"
    if "holder" in name:
        return "holder"
    if "limit" in name:
        return "limit"
    return "other new-data"


def build_success_summary(run_dir: Path, report_df: pd.DataFrame, metadata: dict) -> str:
    horizons = metadata.get("horizons") or [5, 10, 20]
    primary_h = horizons[0]
    rank_icir_primary = f"rank_icir_{primary_h}d"
    mean_rank_ic_primary = f"mean_rank_ic_{primary_h}d"
    hit_rate_primary = f"ic_hit_rate_{primary_h}d"
    requested_kernels = metadata["requested_kernels"]
    effective_kernels = metadata["effective_kernels"]
    grade_counts = metadata.get("grade_counts") or report_df["grade"].value_counts().to_dict()
    top_factor = report_df.iloc[0]["factor"] if not report_df.empty else "n/a"
    warning_counts = warning_counter(report_df.get("warning_flags", pd.Series(dtype=object)))

    lines: list[str] = [f"# {TITLE}", ""]
    lines.extend(
        [
            "## Executive Summary",
            f"- This run screened **{len(report_df)}** factors from the latest backend with `include_new_data = {metadata.get('include_new_data', False)}`.",
            f"- The strongest factor by `|Rank ICIR|` was **{top_factor}**.",
            f"- Requested kernels: **{requested_kernels}**; effective kernels: **{effective_kernels}**.",
            f"- Grade split: A={grade_counts.get('A (Graduated)', 0)}, B={grade_counts.get('B (Strong IC)', 0)}, C={grade_counts.get('C (Moderate)', 0)}, D={grade_counts.get('D (Weak)', 0)}.",
            "",
            "## Run Metadata",
            f"- Generated at: `{metadata.get('generated_at', 'unknown')}`",
            f"- Date window: `{metadata.get('start_date', 'unknown')}` to `{metadata.get('end_date', 'unknown')}`",
            f"- Horizons: `{', '.join(str(h) for h in horizons)}`",
            f"- Engine: `{metadata.get('engine', 'unknown')}`",
            f"- Include new data: `{metadata.get('include_new_data', False)}`",
            f"- Qlib provider: `{metadata.get('qlib_dir', 'unknown')}`",
            f"- Cache mode: `{metadata.get('cache_mode', 'unknown')}`",
            f"- Requested kernels: `{requested_kernels}`",
            f"- Effective kernels: `{effective_kernels}`",
            "",
            "## Grade Distribution",
            "| Grade | Count |",
            "| --- | --- |",
        ]
    )
    for grade in GRADE_ORDER:
        lines.append(f"| {grade} | {grade_counts.get(grade, 0)} |")

    lines.extend(
        [
            "",
            "## Top 20 Factors",
            markdown_table(
                report_df.head(20),
                ["factor", "grade", rank_icir_primary, "monotonic", "ls_ann_return", "warning_flags"],
                rename={rank_icir_primary: f"rank_icir_{primary_h}d"},
            ),
            "",
            "## A / B Grade Candidates",
        ]
    )
    ab_df = report_df[report_df["grade"].isin({"A (Graduated)", "B (Strong IC)"})].copy()
    if ab_df.empty:
        lines.append("No A/B candidates were produced in this run.")
    else:
        lines.append(
            markdown_table(
                ab_df,
                ["factor", "grade", rank_icir_primary, "monotonic", "ls_ann_return", "warning_flags"],
                rename={rank_icir_primary: f"rank_icir_{primary_h}d"},
            )
        )

    lines.extend(["", "## New-Data Factor Highlights"])
    new_data_df = report_df[report_df["factor"].map(is_new_data_factor)].copy()
    if new_data_df.empty:
        lines.append("No new-data factor rows were found in this run.")
    else:
        new_data_df["family"] = new_data_df["factor"].map(family_label)
        lines.append(
            markdown_table(
                new_data_df[
                    ["family", "factor", "grade", rank_icir_primary, "monotonic", "ls_ann_return", "warning_flags"]
                ],
                ["family", "factor", "grade", rank_icir_primary, "monotonic", "ls_ann_return", "warning_flags"],
                rename={rank_icir_primary: f"rank_icir_{primary_h}d"},
            )
        )
        covered_families = sorted(new_data_df["family"].unique())
        expected = ["moneyflow / flow", "northbound / north", "margin", "earnings", "forecast", "holder", "limit"]
        missing = [name for name in expected if name not in covered_families]
        lines.append("")
        lines.append(f"Covered families in this run: `{', '.join(covered_families)}`")
        if missing:
            lines.append(f"Families with no matching factor names in this run: `{', '.join(missing)}`")

    lines.extend(["", "## Warnings And Caveats"])
    lines.append("- `L/S` is a diagnostic based on overlapping forward returns, not a directly tradable return estimate.")
    lines.append(
        f"- Kernel mode in this run was `requested_kernels = {requested_kernels}` and `effective_kernels = {effective_kernels}`."
    )
    if requested_kernels != effective_kernels:
        lines.append("- The worker setting fell back during execution. That means the runtime switched to a safer mode; it does not by itself invalidate factor results.")
    if warning_counts:
        lines.append("- Warning flag frequency:")
        for flag, count in warning_counts.most_common():
            lines.append(f"  - `{flag}`: {count}")
    else:
        lines.append("- No warning flags were recorded in `warning_flags`.")

    lines.extend(["", "## All Factor Performance"])
    all_factor_columns = [
        "factor",
        "grade",
        "rank_icir_5d",
        "rank_icir_10d",
        "rank_icir_20d",
        "mean_rank_ic_5d",
        "ic_hit_rate_5d",
        "monotonic",
        "ls_ann_return",
        "warning_flags",
        "obs_coverage_primary",
        "rankic_coverage_primary",
    ]
    for grade in GRADE_ORDER:
        section_df = report_df[report_df["grade"] == grade].copy()
        lines.extend(["", f"### {grade}"])
        if section_df.empty:
            lines.append("No factors in this grade.")
        else:
            lines.append(markdown_table(section_df, all_factor_columns))

    lines.extend(["", "## Artifacts"])
    for name, exists, size in artifact_status(run_dir):
        state = "present" if exists else "missing"
        lines.append(f"- `{run_dir / name}` - {state}" + (f", {size} bytes" if exists else ""))

    return "\n".join(lines) + "\n"


def build_failure_summary(run_dir: Path, metadata: dict | None) -> str:
    lines = [f"# {TITLE}", "", "## Executive Summary", "- This run did not produce a complete screening result set.", ""]
    if metadata is not None:
        requested = metadata.get("requested_kernels", "unknown")
        effective = metadata.get("effective_kernels", requested)
        lines.extend(
            [
                "## Run Metadata",
                f"- Generated at: `{metadata.get('generated_at', 'unknown')}`",
                f"- Date window: `{metadata.get('start_date', 'unknown')}` to `{metadata.get('end_date', 'unknown')}`",
                f"- Engine: `{metadata.get('engine', 'unknown')}`",
                f"- Requested kernels: `{requested}`",
                f"- Effective kernels: `{effective}`",
                "",
            ]
        )

    log_path = run_dir / "run_console.log"
    tail = last_error_excerpt(read_log_tail(log_path))
    lines.extend(["## Failure Stage And Last Error"])
    if tail:
        lines.append("```text")
        lines.extend(tail)
        lines.append("```")
    else:
        lines.append("No console log was available, so the last error could not be extracted.")

    lines.extend(["", "## Existing Artifacts"])
    for name, exists, size in artifact_status(run_dir):
        state = "present" if exists else "missing"
        lines.append(f"- `{run_dir / name}` - {state}" + (f", {size} bytes" if exists else ""))

    lines.extend(
        [
            "",
            "## Next Likely Action",
            "- Check the log excerpt above first. If the failure happened during factor compute and `effective_kernels` changed from `qlib default` to `1`, that was the worker fallback doing its job.",
            "- If the failure happened after factor compute, the next step is usually to inspect the CSV/parquet write stage or the report-generation stage.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    run_dir = Path(args.run_dir).resolve()
    summary_path = Path(args.summary_path).resolve() if args.summary_path else run_dir / "factor_screening_review_summary.md"

    metadata_path = run_dir / "factor_screening_run_metadata.json"
    report_path = run_dir / "factor_screening_report.csv"

    metadata = normalize_metadata(load_json(metadata_path)) if metadata_path.exists() else None

    if metadata is not None:
        success_required = [
            run_dir / "factor_screening_results.parquet",
            report_path,
            run_dir / "factor_screening_summary.txt",
        ]
        run_complete = all(path.exists() for path in success_required)
    else:
        run_complete = False

    if run_complete:
        report_df = load_report(report_path)
        summary_text = build_success_summary(run_dir, report_df, metadata)
    else:
        summary_text = build_failure_summary(run_dir, metadata)

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(summary_text, encoding="utf-8")
    print(summary_path)


if __name__ == "__main__":
    main()
