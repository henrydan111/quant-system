"""Human-readable HTML review report for the formal factor registry."""

from __future__ import annotations

import html
import json
from typing import Any

import pandas as pd


def _fmt_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value)


def _fmt_num(value: Any, digits: int = 3) -> str:
    if value is None or pd.isna(value):
        return ""
    return f"{float(value):.{digits}f}"


def _fmt_int(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return f"{int(value):,}"


def _fmt_bool(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return "Yes" if bool(value) else "No"


def _escape(value: Any) -> str:
    return html.escape(_fmt_text(value))


def _slug(value: str) -> str:
    chars = []
    for char in value:
        if char.isalnum():
            chars.append(char.lower())
        else:
            chars.append("-")
    slug = "".join(chars).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "factor"


def _loads_json_list(text: Any) -> list[Any]:
    raw = _fmt_text(text).strip()
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, list):
        return payload
    return []


def _badge(label: str, css_class: str) -> str:
    if not label:
        return ""
    variant_class = f"badge-{_slug(label)}"
    return f'<span class="badge {css_class} {variant_class}">{_escape(label)}</span>'


def _recommended_priority(value: str) -> int:
    mapping = {"approved": 0, "candidate": 1, "draft": 2, "deprecated": 3}
    return mapping.get(_fmt_text(value), 9)


def _binding_priority(value: str) -> int:
    mapping = {"verified": 0, "legacy_best_effort": 1}
    return mapping.get(_fmt_text(value), 9)


def _render_stat_card(label: str, value: str, note: str = "") -> str:
    note_html = f'<div class="stat-note">{_escape(note)}</div>' if note else ""
    return (
        '<div class="stat-card">'
        f'<div class="stat-label">{_escape(label)}</div>'
        f'<div class="stat-value">{_escape(value)}</div>'
        f"{note_html}"
        "</div>"
    )


def _render_counts_block(title: str, counts: dict[str, int], css_prefix: str) -> str:
    rows = []
    for key, value in counts.items():
        rows.append(
            '<div class="count-row">'
            f'<span>{_badge(key, css_prefix)}</span>'
            f'<strong>{value}</strong>'
            "</div>"
        )
    return (
        '<div class="panel small-panel">'
        f"<h3>{_escape(title)}</h3>"
        + "".join(rows)
        + "</div>"
    )


def _render_run_table(run_index: pd.DataFrame) -> str:
    if run_index.empty:
        return "<p class='empty'>No imported runs yet.</p>"
    rows = []
    for _, row in run_index.sort_values("generated_at", ascending=False).head(12).iterrows():
        rows.append(
            "<tr>"
            f"<td>{_escape(row['generated_at'])}</td>"
            f"<td>{_escape(row['run_type'])}</td>"
            f"<td><code>{_escape(row['run_id'])}</code></td>"
            f"<td>{_escape(row['start_date'])} to {_escape(row['end_date'])}</td>"
            f"<td>{_escape(row['benchmark'])}</td>"
            f"<td>{_escape(row['effective_kernels'])}</td>"
            f"<td class='path-cell'>{_escape(row['run_dir'])}</td>"
            "</tr>"
        )
    return (
        "<table class='data-table compact-table'><thead><tr>"
        "<th>Generated</th><th>Type</th><th>Run ID</th><th>Window</th><th>Benchmark</th><th>Kernels</th><th>Run Dir</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _render_status_history(status_history: pd.DataFrame) -> str:
    if status_history.empty:
        return "<p class='empty'>No manual status changes yet.</p>"
    rows = []
    for _, row in status_history.sort_values("changed_at", ascending=False).head(20).iterrows():
        rows.append(
            "<tr>"
            f"<td>{_escape(row['changed_at'])}</td>"
            f"<td><code>{_escape(row['factor_id'])}</code></td>"
            f"<td>{_badge(_fmt_text(row['old_status']), 'badge-status')}</td>"
            f"<td>{_badge(_fmt_text(row['new_status']), 'badge-status')}</td>"
            f"<td>{_escape(row['reason'])}</td>"
            f"<td><code>{_escape(row['source_run_id'])}</code></td>"
            "</tr>"
        )
    return (
        "<table class='data-table compact-table'><thead><tr>"
        "<th>Changed</th><th>Factor</th><th>Old</th><th>New</th><th>Reason</th><th>Source Run</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def build_factor_registry_review_html(
    *,
    registry_metadata: dict[str, Any],
    factor_master: pd.DataFrame,
    factor_evidence: pd.DataFrame,
    run_index: pd.DataFrame,
    status_history: pd.DataFrame,
) -> str:
    current_df = factor_master[factor_master["is_current"].fillna(False)].copy()
    current_df["abs_rank_icir_5d"] = current_df["latest_rank_icir_5d"].astype("Float64").abs()
    current_df["recommended_priority"] = current_df["recommended_status"].map(_recommended_priority)
    current_df["binding_priority"] = current_df["definition_binding"].map(_binding_priority)
    current_df = current_df.sort_values(
        ["recommended_priority", "binding_priority", "abs_rank_icir_5d", "factor_id"],
        ascending=[True, True, False, True],
        na_position="last",
    )

    recommended_counts = (
        current_df["recommended_status"].fillna("draft").value_counts().reindex(
            ["approved", "candidate", "draft", "deprecated"],
            fill_value=0,
        )
    )
    status_counts = (
        current_df["status"].fillna("draft").value_counts().reindex(
            ["approved", "candidate", "draft", "deprecated"],
            fill_value=0,
        )
    )
    binding_counts = current_df["definition_binding"].fillna("").value_counts().to_dict()
    category_counts = current_df["category"].fillna("").value_counts().sort_values(ascending=False)

    summary_cards = [
        _render_stat_card("Current formal factors", _fmt_int(len(current_df))),
        _render_stat_card("Recommended approved", _fmt_int(int(recommended_counts.get("approved", 0)))),
        _render_stat_card("Recommended candidate", _fmt_int(int(recommended_counts.get("candidate", 0)))),
        _render_stat_card("Manual approved", _fmt_int(int(status_counts.get("approved", 0)))),
        _render_stat_card("Verified bindings", _fmt_int(int(binding_counts.get("verified", 0)))),
        _render_stat_card(
            "Last catalog sync",
            _fmt_text(registry_metadata.get("catalog_sync_last_at")) or "Not synced",
            note=f"Schema v{registry_metadata.get('schema_version', '')}",
        ),
    ]

    spotlight_rows = []
    spotlight_df = current_df[
        current_df["recommended_status"].isin(["approved", "candidate"])
    ].head(20)
    for _, row in spotlight_df.iterrows():
        spotlight_rows.append(
            "<tr>"
            f"<td><a href='#{_slug(_fmt_text(row['factor_id']))}'><code>{_escape(row['factor_id'])}</code></a></td>"
            f"<td>{_escape(row['category'])}</td>"
            f"<td>{_badge(_fmt_text(row['recommended_status']), 'badge-recommended')}</td>"
            f"<td>{_badge(_fmt_text(row['status']), 'badge-status')}</td>"
            f"<td>{_escape(row['latest_screening_grade'])}</td>"
            f"<td>{_fmt_num(row['latest_rank_icir_5d'])}</td>"
            f"<td>{_fmt_int(row['latest_validation_pass_count'])}</td>"
            f"<td>{_fmt_int(row['latest_selected_fold_count'])}</td>"
            "</tr>"
        )

    category_pills = "".join(
        f"<span class='category-pill'>{_escape(name)}: <strong>{count}</strong></span>"
        for name, count in category_counts.items()
    )

    category_options = "".join(
        f"<option value='{_escape(value)}'>{_escape(value)}</option>"
        for value in sorted(current_df["category"].dropna().astype(str).unique().tolist())
    )

    overview_rows = []
    detail_blocks = []
    for _, row in current_df.iterrows():
        factor_id = _fmt_text(row["factor_id"])
        factor_slug = _slug(factor_id)
        category = _fmt_text(row["category"])
        recommended_status = _fmt_text(row["recommended_status"])
        manual_status = _fmt_text(row["status"])
        factor_kind = _fmt_text(row["factor_kind"])
        binding = _fmt_text(row["definition_binding"])
        search_blob = " ".join(
            [
                factor_id,
                category,
                factor_kind,
                recommended_status,
                manual_status,
                _fmt_text(row["latest_screening_grade"]),
                _fmt_text(row["expression"]),
                _fmt_text(row["display_name_zh"]),
            ]
        ).lower()

        overview_rows.append(
            "<tr "
            f"data-category='{_escape(category)}' "
            f"data-recommended='{_escape(recommended_status)}' "
            f"data-status='{_escape(manual_status)}' "
            f"data-search='{_escape(search_blob)}'>"
            f"<td><a href='#{factor_slug}'><code>{_escape(factor_id)}</code></a></td>"
            f"<td>{_escape(category)}</td>"
            f"<td>{_badge(factor_kind, 'badge-kind')}</td>"
            f"<td>{_badge(recommended_status, 'badge-recommended')}</td>"
            f"<td>{_badge(manual_status, 'badge-status')}</td>"
            f"<td>{_escape(row['latest_screening_grade'])}</td>"
            f"<td>{_fmt_num(row['latest_rank_icir_5d'])}</td>"
            f"<td>{_fmt_int(row['latest_validation_pass_count'])}</td>"
            f"<td>{_fmt_int(row['latest_selected_fold_count'])}</td>"
            f"<td>{_badge(binding, 'badge-binding')}</td>"
            "</tr>"
        )

        components = _loads_json_list(row["components_json"])
        weights = _loads_json_list(row["weights_json"])
        negate = _loads_json_list(row["negate_json"])
        if components:
            component_rows = []
            for idx, component in enumerate(components):
                weight = weights[idx] if idx < len(weights) else ""
                negate_flag = negate[idx] if idx < len(negate) else ""
                component_rows.append(
                    "<tr>"
                    f"<td><code>{_escape(component)}</code></td>"
                    f"<td>{_fmt_num(weight, 4) if weight != '' else ''}</td>"
                    f"<td>{_fmt_bool(negate_flag)}</td>"
                    "</tr>"
                )
            components_html = (
                "<table class='data-table compact-table'><thead><tr>"
                "<th>Component</th><th>Weight</th><th>Negate</th>"
                "</tr></thead><tbody>"
                + "".join(component_rows)
                + "</tbody></table>"
            )
        else:
            components_html = "<p class='empty'>Base factor. No composite components.</p>"

        detail_blocks.append(
            f"""
<details class="factor-detail" id="{factor_slug}">
  <summary>
    <code>{_escape(factor_id)}</code>
    {_badge(category, 'badge-kind')}
    {_badge(recommended_status, 'badge-recommended')}
    {_badge(manual_status, 'badge-status')}
    {_badge(binding, 'badge-binding')}
  </summary>
  <div class="detail-grid">
    <div class="panel">
      <h3>Definition</h3>
      <div class="key-value"><span>Version</span><strong>{_fmt_int(row['version'])}</strong></div>
      <div class="key-value"><span>Kind</span><strong>{_escape(factor_kind)}</strong></div>
      <div class="key-value"><span>Family</span><strong>{_escape(row['family'])}</strong></div>
      <div class="key-value"><span>Display Name</span><strong>{_escape(row['display_name_zh'])}</strong></div>
      <div class="key-value"><span>Expression</span></div>
      <pre>{_escape(row['expression'])}</pre>
      <h4>Composite Details</h4>
      {components_html}
    </div>
    <div class="panel">
      <h3>Latest Evidence</h3>
      <div class="key-value"><span>Screening grade</span><strong>{_escape(row['latest_screening_grade'])}</strong></div>
      <div class="key-value"><span>5d Rank ICIR</span><strong>{_fmt_num(row['latest_rank_icir_5d'])}</strong></div>
      <div class="key-value"><span>Monotonic</span><strong>{_fmt_bool(row['latest_monotonic'])}</strong></div>
      <div class="key-value"><span>Best decay horizon</span><strong>{_fmt_int(row['latest_best_decay_horizon'])}</strong></div>
      <div class="key-value"><span>Validation pass count</span><strong>{_fmt_int(row['latest_validation_pass_count'])}</strong></div>
      <div class="key-value"><span>Selected fold count</span><strong>{_fmt_int(row['latest_selected_fold_count'])}</strong></div>
      <div class="key-value"><span>First seen run</span><code>{_escape(row['first_seen_run_id'])}</code></div>
      <div class="key-value"><span>Last seen run</span><code>{_escape(row['last_seen_run_id'])}</code></div>
      <div class="key-value"><span>Definition binding</span><strong>{_escape(binding)}</strong></div>
      <div class="key-value"><span>Definition hash</span><code class="hash">{_escape(row['definition_hash'])}</code></div>
    </div>
    <div class="panel">
      <h3>Workflow Status</h3>
      <div class="key-value"><span>Recommended</span><strong>{_escape(recommended_status)}</strong></div>
      <div class="key-value"><span>Manual status</span><strong>{_escape(manual_status)}</strong></div>
      <div class="key-value"><span>Notes</span><div>{_escape(row['notes']) or '<span class="empty-inline">No notes</span>'}</div></div>
      <div class="key-value"><span>Deprecated reason</span><div>{_escape(row['deprecated_reason']) or '<span class="empty-inline">Not deprecated</span>'}</div></div>
      <div class="key-value"><span>Created at</span><strong>{_escape(row['created_at'])}</strong></div>
      <div class="key-value"><span>Updated at</span><strong>{_escape(row['updated_at'])}</strong></div>
    </div>
  </div>
</details>
"""
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Formal Factor Registry Review</title>
  <style>
    :root {{
      --bg: #f6f4ef;
      --panel: #fffdf8;
      --ink: #1e2430;
      --muted: #6b7280;
      --line: #d8d2c4;
      --accent: #14532d;
      --accent-soft: #d1fae5;
      --candidate: #b45309;
      --candidate-soft: #fef3c7;
      --draft: #475569;
      --draft-soft: #e2e8f0;
      --danger: #991b1b;
      --danger-soft: #fee2e2;
      --binding-soft: #dbeafe;
      --binding: #1d4ed8;
      --shadow: 0 10px 30px rgba(30, 36, 48, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      background: linear-gradient(180deg, #fcfbf7 0%, var(--bg) 100%);
      color: var(--ink);
      line-height: 1.5;
    }}
    .page {{
      max-width: 1440px;
      margin: 0 auto;
      padding: 32px 24px 64px;
    }}
    h1, h2, h3, h4 {{ margin: 0 0 12px; }}
    .hero {{
      background: radial-gradient(circle at top left, #f0fdf4, #fffdf8 60%);
      border: 1px solid var(--line);
      border-radius: 24px;
      padding: 28px;
      box-shadow: var(--shadow);
    }}
    .hero p {{
      margin: 10px 0 0;
      color: var(--muted);
      max-width: 960px;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 14px;
      margin-top: 22px;
    }}
    .stat-card, .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 18px;
      box-shadow: var(--shadow);
    }}
    .stat-label {{
      color: var(--muted);
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .stat-value {{
      font-size: 28px;
      font-weight: 700;
      margin-top: 8px;
    }}
    .stat-note {{
      margin-top: 8px;
      color: var(--muted);
      font-size: 13px;
    }}
    .section {{
      margin-top: 26px;
    }}
    .section-grid {{
      display: grid;
      grid-template-columns: minmax(0, 1.7fr) minmax(280px, 0.9fr) minmax(280px, 0.9fr);
      gap: 16px;
      align-items: start;
    }}
    .small-panel h3 {{
      font-size: 16px;
      margin-bottom: 14px;
    }}
    .count-row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 8px 0;
      border-bottom: 1px dashed #e8e2d7;
    }}
    .count-row:last-child {{ border-bottom: 0; }}
    .badge {{
      display: inline-flex;
      align-items: center;
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 0.01em;
      border: 1px solid transparent;
      white-space: nowrap;
    }}
    .badge-kind {{
      background: #f3f4f6;
      color: #1f2937;
      border-color: #d1d5db;
    }}
    .badge-recommended {{
      background: var(--draft-soft);
      color: var(--draft);
      border-color: #cbd5e1;
    }}
    .badge-status {{
      background: #f8fafc;
      color: #334155;
      border-color: #cbd5e1;
    }}
    .badge-binding {{
      background: var(--binding-soft);
      color: var(--binding);
      border-color: #bfdbfe;
    }}
    .badge-recommended, .badge-status {{
      text-transform: capitalize;
    }}
    .badge-approved {{
      background: var(--accent-soft);
      color: var(--accent);
      border-color: #86efac;
    }}
    .badge-candidate {{
      background: var(--candidate-soft);
      color: var(--candidate);
      border-color: #fcd34d;
    }}
    .badge-draft {{
      background: var(--draft-soft);
      color: var(--draft);
      border-color: #cbd5e1;
    }}
    .badge-deprecated {{
      background: var(--danger-soft);
      color: var(--danger);
      border-color: #fca5a5;
    }}
    .badge-verified {{
      background: #dcfce7;
      color: #166534;
      border-color: #86efac;
    }}
    .badge-legacy-best-effort {{
      background: var(--binding-soft);
      color: var(--binding);
      border-color: #bfdbfe;
    }}
    .category-pills {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 10px;
    }}
    .category-pill {{
      padding: 8px 12px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: #fff;
      font-size: 13px;
    }}
    .data-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    .data-table th, .data-table td {{
      text-align: left;
      vertical-align: top;
      padding: 10px 12px;
      border-bottom: 1px solid #ebe5d8;
    }}
    .data-table th {{
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--muted);
      background: #faf7ef;
      position: sticky;
      top: 0;
      z-index: 1;
    }}
    .compact-table th, .compact-table td {{
      padding: 8px 10px;
      font-size: 13px;
    }}
    .table-wrap {{
      overflow: auto;
      max-height: 660px;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: var(--panel);
      box-shadow: var(--shadow);
    }}
    .toolbar {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin: 14px 0 16px;
      align-items: center;
    }}
    .toolbar input, .toolbar select {{
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 10px 12px;
      background: #fff;
      min-width: 180px;
      font-size: 14px;
    }}
    .toolbar .result-count {{
      color: var(--muted);
      font-size: 14px;
      margin-left: auto;
    }}
    .factor-detail {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      margin-bottom: 14px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    .factor-detail summary {{
      list-style: none;
      cursor: pointer;
      padding: 16px 18px;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      background: #fffdf8;
      border-bottom: 1px solid #efe8db;
    }}
    .factor-detail summary::-webkit-details-marker {{ display: none; }}
    .detail-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 14px;
      padding: 18px;
    }}
    .key-value {{
      display: grid;
      grid-template-columns: 140px 1fr;
      gap: 10px;
      padding: 8px 0;
      border-bottom: 1px dashed #ebe5d8;
      align-items: start;
    }}
    .key-value:last-child {{ border-bottom: 0; }}
    .key-value span {{
      color: var(--muted);
      font-size: 13px;
    }}
    pre {{
      margin: 10px 0 0;
      padding: 12px;
      border-radius: 12px;
      background: #fbfaf6;
      border: 1px solid #ede6d7;
      overflow: auto;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    code {{
      font-family: Consolas, "SFMono-Regular", monospace;
      font-size: 0.92em;
    }}
    .hash {{
      word-break: break-all;
    }}
    .empty, .empty-inline {{
      color: var(--muted);
      font-style: italic;
    }}
    .path-cell {{
      word-break: break-all;
      max-width: 380px;
    }}
    .note-box {{
      margin-top: 14px;
      padding: 14px 16px;
      border-radius: 16px;
      background: #fff8e8;
      border: 1px solid #f2dfb3;
      color: #7c5a10;
    }}
    @media (max-width: 1080px) {{
      .section-grid {{
        grid-template-columns: 1fr;
      }}
      .toolbar .result-count {{
        margin-left: 0;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <h1>Formal Factor Registry Review</h1>
      <p>
        This page is the human-readable view of the official factor registry.
        It highlights the current formal factors, their latest screening and research evidence,
        and the difference between automatic recommendations and manual promotion status.
      </p>
      <div class="note-box">
        Manual status is what you have formally approved.
        Recommended status is what the system suggests from the latest evidence.
      </div>
      <div class="stats">
        {''.join(summary_cards)}
      </div>
    </section>

    <section class="section">
      <div class="section-grid">
        <div class="panel">
          <h2>Category Distribution</h2>
          <p class="empty">How the current formal factors are spread across research families.</p>
          <div class="category-pills">{category_pills}</div>
        </div>
        {_render_counts_block("Recommended Status", recommended_counts.to_dict(), "badge-recommended")}
        {_render_counts_block("Manual Status", status_counts.to_dict(), "badge-status")}
      </div>
    </section>

    <section class="section">
      <div class="panel">
        <h2>Priority View</h2>
        <p class="empty">Fast review list for factors the system currently considers worth extra attention.</p>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>Factor</th>
                <th>Category</th>
                <th>Recommended</th>
                <th>Manual</th>
                <th>Screening Grade</th>
                <th>5d Rank ICIR</th>
                <th>Validation Passes</th>
                <th>Selected Folds</th>
              </tr>
            </thead>
            <tbody>
              {''.join(spotlight_rows) or "<tr><td colspan='8' class='empty'>No approved or candidate recommendations yet.</td></tr>"}
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <section class="section">
      <h2>All Current Factors</h2>
      <div class="toolbar">
        <input id="filter-query" type="search" placeholder="Search factor name, category, expression...">
        <select id="filter-category">
          <option value="">All categories</option>
          {category_options}
        </select>
        <select id="filter-recommended">
          <option value="">All recommended statuses</option>
          <option value="approved">approved</option>
          <option value="candidate">candidate</option>
          <option value="draft">draft</option>
          <option value="deprecated">deprecated</option>
        </select>
        <select id="filter-status">
          <option value="">All manual statuses</option>
          <option value="approved">approved</option>
          <option value="candidate">candidate</option>
          <option value="draft">draft</option>
          <option value="deprecated">deprecated</option>
        </select>
        <div class="result-count">Showing <strong id="visible-count">{len(current_df)}</strong> of {len(current_df)} factors</div>
      </div>
      <div class="table-wrap">
        <table class="data-table" id="overview-table">
          <thead>
            <tr>
              <th>Factor</th>
              <th>Category</th>
              <th>Kind</th>
              <th>Recommended</th>
              <th>Manual</th>
              <th>Screening Grade</th>
              <th>5d Rank ICIR</th>
              <th>Validation Passes</th>
              <th>Selected Folds</th>
              <th>Binding</th>
            </tr>
          </thead>
          <tbody>
            {''.join(overview_rows)}
          </tbody>
        </table>
      </div>
    </section>

    <section class="section">
      <h2>Factor Detail Cards</h2>
      <p class="empty">Open any factor below to see its formula, composite makeup, latest evidence, and workflow status.</p>
      {''.join(detail_blocks)}
    </section>

    <section class="section">
      <div class="panel">
        <h2>Recent Imported Runs</h2>
        {_render_run_table(run_index)}
      </div>
    </section>

    <section class="section">
      <div class="panel">
        <h2>Manual Status History</h2>
        {_render_status_history(status_history)}
      </div>
    </section>
  </div>
  <script>
    (() => {{
      const queryInput = document.getElementById("filter-query");
      const categoryInput = document.getElementById("filter-category");
      const recommendedInput = document.getElementById("filter-recommended");
      const statusInput = document.getElementById("filter-status");
      const rows = Array.from(document.querySelectorAll("#overview-table tbody tr"));
      const visibleCount = document.getElementById("visible-count");

      function applyFilters() {{
        const query = queryInput.value.trim().toLowerCase();
        const category = categoryInput.value;
        const recommended = recommendedInput.value;
        const status = statusInput.value;
        let visible = 0;

        rows.forEach((row) => {{
          const matchesQuery = !query || (row.dataset.search || "").includes(query);
          const matchesCategory = !category || row.dataset.category === category;
          const matchesRecommended = !recommended || row.dataset.recommended === recommended;
          const matchesStatus = !status || row.dataset.status === status;
          const show = matchesQuery && matchesCategory && matchesRecommended && matchesStatus;
          row.hidden = !show;
          if (show) {{
            visible += 1;
          }}
        }});
        visibleCount.textContent = String(visible);
      }}

      [queryInput, categoryInput, recommendedInput, statusInput].forEach((node) => {{
        node.addEventListener("input", applyFilters);
        node.addEventListener("change", applyFilters);
      }});
      applyFilters();
    }})();
  </script>
</body>
</html>"""
