"""Follow-up Plan #1 — Pre/post factor-library-fix diff report.

One-off helper that compares two screening runs and emits a markdown
report with grade migration, top-20 factor comparison, and flagged-
factor lists. Meant to be archived under the post-fix run directory
after execution.

Flagging rule (per plan Step 9, with Codex MEDIUM revision):
  - Grade changed by >=1 bucket (either direction), OR
  - |rank_icir_5d| changed by >=20% relative AND absolute delta
    |Δrank_icir_5d| >= 0.005, OR
  - monotonic flipped

The absolute-floor guard at 0.005 prevents near-zero baseline ICIRs
from triggering noisy relative-change flags.

Usage:
    python generate_post_fix_diff.py \\
        --baseline workspace/research/alpha_mining/latest_backend_screening_20260401_new_data \\
        --post-fix workspace/research/alpha_mining/post_fix_screening_20260411 \\
        --output   workspace/research/alpha_mining/post_fix_screening_20260411/post_fix_screening_diff.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd


GRADE_ORDER = ["A", "B", "C", "D"]
GRADE_LABEL = {"A": "A (Graduated)", "B": "B (Strong IC)", "C": "C (Moderate)", "D": "D (Weak)"}


def _load_results(run_dir: Path) -> pd.DataFrame:
    """Load ``factor_screening_results.parquet`` from a run directory."""
    path = run_dir / "factor_screening_results.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing screening results: {path}")
    df = pd.read_parquet(path)
    if "factor" not in df.columns and df.index.name != "factor":
        raise ValueError(
            f"Unexpected schema in {path}: no 'factor' column or index"
        )
    if df.index.name == "factor":
        df = df.reset_index()
    return df


def _normalize_grade(value: object) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    return s[0].upper() if s[0].upper() in GRADE_ORDER else s


def _grade_delta_buckets(pre: str | None, post: str | None) -> int | None:
    """Positive = upgraded (C->B), negative = downgraded (A->B->C->D)."""
    if pre is None or post is None:
        return None
    if pre not in GRADE_ORDER or post not in GRADE_ORDER:
        return None
    # A=0, B=1, C=2, D=3 — lower index = better grade
    return GRADE_ORDER.index(pre) - GRADE_ORDER.index(post)


def _pick_icir_column(df: pd.DataFrame) -> str:
    """Find the canonical 5-day rank ICIR column (names may vary)."""
    candidates = ["rank_icir_5d", "rankic_icir_5", "rankic_icir_5d", "icir_rank_5"]
    for c in candidates:
        if c in df.columns:
            return c
    for c in df.columns:
        low = c.lower()
        if "icir" in low and "5" in low and "rank" in low:
            return c
    raise KeyError(
        f"No rank_icir_5d column found in columns: {list(df.columns)}"
    )


def _build_diff(baseline_df: pd.DataFrame, post_df: pd.DataFrame) -> pd.DataFrame:
    """Inner-join on factor name and compute per-factor deltas."""
    bl = baseline_df.copy()
    pf = post_df.copy()

    bl_icir = _pick_icir_column(bl)
    pf_icir = _pick_icir_column(pf)

    bl["_icir_5d"] = bl[bl_icir].astype(float)
    pf["_icir_5d"] = pf[pf_icir].astype(float)

    bl["_grade"] = bl.get("grade", pd.Series([None] * len(bl))).map(_normalize_grade)
    pf["_grade"] = pf.get("grade", pd.Series([None] * len(pf))).map(_normalize_grade)

    bl["_monotonic"] = bl.get("monotonic", pd.Series([None] * len(bl)))
    pf["_monotonic"] = pf.get("monotonic", pd.Series([None] * len(pf)))

    merged = bl[["factor", "_icir_5d", "_grade", "_monotonic"]].merge(
        pf[["factor", "_icir_5d", "_grade", "_monotonic"]],
        on="factor",
        how="outer",
        suffixes=("_pre", "_post"),
    )

    merged["icir_abs_delta"] = merged["_icir_5d_post"].sub(merged["_icir_5d_pre"])
    denom = merged["_icir_5d_pre"].abs().replace(0.0, float("nan"))
    merged["icir_rel_delta"] = merged["icir_abs_delta"].abs() / denom
    merged["grade_bucket_delta"] = [
        _grade_delta_buckets(p, po)
        for p, po in zip(merged["_grade_pre"], merged["_grade_post"])
    ]
    merged["monotonic_flipped"] = (
        merged["_monotonic_pre"] != merged["_monotonic_post"]
    ) & merged["_monotonic_pre"].notna() & merged["_monotonic_post"].notna()

    return merged


def _flag_factors(diff: pd.DataFrame) -> pd.DataFrame:
    """Apply the plan's flagging rule."""
    cond_grade = diff["grade_bucket_delta"].fillna(0).abs() >= 1
    cond_icir = (
        (diff["icir_rel_delta"] >= 0.20) & (diff["icir_abs_delta"].abs() >= 0.005)
    )
    cond_monotonic = diff["monotonic_flipped"].fillna(False)
    mask = cond_grade | cond_icir | cond_monotonic
    return diff[mask].copy()


def _grade_migration_matrix(diff: pd.DataFrame) -> pd.DataFrame:
    """Build a pre-vs-post grade confusion matrix."""
    rows = {g: {g2: 0 for g2 in GRADE_ORDER + ["missing"]} for g in GRADE_ORDER + ["missing"]}
    for _, row in diff.iterrows():
        pre = row["_grade_pre"] if row["_grade_pre"] in GRADE_ORDER else "missing"
        post = row["_grade_post"] if row["_grade_post"] in GRADE_ORDER else "missing"
        rows[pre][post] += 1
    return pd.DataFrame(rows).T


def _render_markdown(
    diff: pd.DataFrame,
    flagged: pd.DataFrame,
    migration: pd.DataFrame,
    baseline_dir: Path,
    post_fix_dir: Path,
) -> str:
    lines: list[str] = []
    lines.append("# Factor Library Pre/Post Leakage Fix Diff Report")
    lines.append("")
    lines.append(f"- **Baseline run**: `{baseline_dir}`")
    lines.append(f"- **Post-fix run**: `{post_fix_dir}`")
    lines.append(f"- **Factors compared**: {len(diff)}")
    lines.append(f"- **Factors flagged**: {len(flagged)}")
    lines.append("")
    lines.append("## 1. Grade migration matrix (pre rows \u2192 post columns)")
    lines.append("")
    lines.append(migration.to_markdown())
    lines.append("")
    lines.append("## 2. Grade counts pre vs post")
    lines.append("")
    pre_counts = diff["_grade_pre"].value_counts().reindex(GRADE_ORDER, fill_value=0)
    post_counts = diff["_grade_post"].value_counts().reindex(GRADE_ORDER, fill_value=0)
    grade_tbl = pd.DataFrame({"pre": pre_counts, "post": post_counts})
    grade_tbl["delta"] = grade_tbl["post"] - grade_tbl["pre"]
    lines.append(grade_tbl.to_markdown())
    lines.append("")

    lines.append("## 3. Top 20 factors by |rank_icir_5d|")
    lines.append("")
    lines.append("### 3a. Baseline top 20")
    top_pre = diff.dropna(subset=["_icir_5d_pre"]).copy()
    top_pre = top_pre.loc[top_pre["_icir_5d_pre"].abs().sort_values(ascending=False).index]
    lines.append(
        top_pre[["factor", "_icir_5d_pre", "_grade_pre"]]
        .head(20)
        .to_markdown(index=False)
    )
    lines.append("")
    lines.append("### 3b. Post-fix top 20")
    top_post = diff.dropna(subset=["_icir_5d_post"]).copy()
    top_post = top_post.loc[top_post["_icir_5d_post"].abs().sort_values(ascending=False).index]
    lines.append(
        top_post[["factor", "_icir_5d_post", "_grade_post"]]
        .head(20)
        .to_markdown(index=False)
    )
    lines.append("")

    downgraded = flagged[flagged["grade_bucket_delta"].fillna(0) < 0].copy()
    lines.append("## 4. HIGH-RISK: factors DOWNGRADED by >=1 bucket")
    lines.append("")
    lines.append(
        "These factors appeared stronger pre-fix than they actually are. "
        "Downstream research that selected them is at highest risk of "
        "contamination."
    )
    lines.append("")
    if downgraded.empty:
        lines.append("_None._")
    else:
        lines.append(
            downgraded.sort_values("grade_bucket_delta")[
                [
                    "factor",
                    "_grade_pre",
                    "_grade_post",
                    "_icir_5d_pre",
                    "_icir_5d_post",
                    "icir_abs_delta",
                ]
            ].to_markdown(index=False)
        )
    lines.append("")

    upgraded = flagged[flagged["grade_bucket_delta"].fillna(0) > 0].copy()
    lines.append("## 5. Factors UPGRADED by >=1 bucket")
    lines.append("")
    lines.append(
        "These factors were penalized by leakage-induced noise in the "
        "baseline screening and are actually better than reported."
    )
    lines.append("")
    if upgraded.empty:
        lines.append("_None._")
    else:
        lines.append(
            upgraded.sort_values("grade_bucket_delta", ascending=False)[
                [
                    "factor",
                    "_grade_pre",
                    "_grade_post",
                    "_icir_5d_pre",
                    "_icir_5d_post",
                    "icir_abs_delta",
                ]
            ].to_markdown(index=False)
        )
    lines.append("")

    strong_abs = flagged[
        flagged["grade_bucket_delta"].fillna(0) == 0
    ].sort_values("icir_abs_delta", key=lambda s: s.abs(), ascending=False)
    lines.append("## 6. Large |\u0394rank_icir_5d| changes (no grade crossing)")
    lines.append("")
    if strong_abs.empty:
        lines.append("_None._")
    else:
        lines.append(
            strong_abs[
                [
                    "factor",
                    "_grade_pre",
                    "_grade_post",
                    "_icir_5d_pre",
                    "_icir_5d_post",
                    "icir_abs_delta",
                    "icir_rel_delta",
                ]
            ].head(30).to_markdown(index=False)
        )
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "Report generated by `workspace/research/alpha_mining/generate_post_fix_diff.py` "
        "as part of follow-up plan #1 (factor library same-day leakage fix)."
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Factor screening pre/post diff report")
    parser.add_argument("--baseline", type=Path, required=True, help="Baseline run directory")
    parser.add_argument("--post-fix", type=Path, required=True, help="Post-fix run directory")
    parser.add_argument("--output", type=Path, required=True, help="Markdown output path")
    args = parser.parse_args()

    baseline_df = _load_results(args.baseline)
    post_df = _load_results(args.post_fix)
    diff = _build_diff(baseline_df, post_df)
    flagged = _flag_factors(diff)
    migration = _grade_migration_matrix(diff)
    report = _render_markdown(diff, flagged, migration, args.baseline, args.post_fix)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"Wrote diff report to: {args.output}")
    print(f"  {len(diff)} factors compared")
    print(f"  {len(flagged)} factors flagged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
