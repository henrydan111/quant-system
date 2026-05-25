"""Human-readable HTML review report for the candidate registry."""

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
        chars.append(char.lower() if char.isalnum() else "-")
    slug = "".join(chars).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "candidate"


def _loads_json_list(value: Any) -> list[Any]:
    text = _fmt_text(value).strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    return payload if isinstance(payload, list) else []


def _badge(label: str, css_class: str) -> str:
    if not label:
        return ""
    return f'<span class="badge {css_class} badge-{_slug(label)}">{_escape(label)}</span>'


def _stat_card(label: str, value: str, note: str = "") -> str:
    note_html = f'<div class="stat-note">{_escape(note)}</div>' if note else ""
    return (
        '<div class="stat-card">'
        f'<div class="stat-label">{_escape(label)}</div>'
        f'<div class="stat-value">{_escape(value)}</div>'
        f"{note_html}</div>"
    )


def _detail_definition_block(row: pd.Series) -> str:
    source_fields = _loads_json_list(row["source_fields_json"])
    component_ids = _loads_json_list(row["component_ids_json"])
    weights = _loads_json_list(row["weights_json"])
    rows = []
    if source_fields:
        rows.append(
            "<div class='kv'><span>Source fields</span><div>"
            + ", ".join(f"<code>{_escape(item)}</code>" for item in source_fields)
            + "</div></div>"
        )
    if component_ids:
        pairs = []
        for idx, component_id in enumerate(component_ids):
            weight = weights[idx] if idx < len(weights) else ""
            pairs.append(f"<code>{_escape(component_id)}</code> ({_fmt_num(weight, 4)})" if weight != "" else f"<code>{_escape(component_id)}</code>")
        rows.append("<div class='kv'><span>Recipe inputs</span><div>" + ", ".join(pairs) + "</div></div>")
    rows.extend(
        [
            f"<div class='kv'><span>Source type</span><strong>{_escape(row['source_type'])}</strong></div>",
            f"<div class='kv'><span>Transform family</span><strong>{_escape(row['transform_family'])}</strong></div>",
            f"<div class='kv'><span>Construction rule</span><strong>{_escape(row['construction_rule'])}</strong></div>",
            f"<div class='kv'><span>Expected sign</span><strong>{_escape(row['expected_sign'])}</strong></div>",
            f"<div class='kv'><span>Economic role</span><strong>{_escape(row['economic_role'])}</strong></div>",
            f"<div class='kv'><span>Coverage tier</span><strong>{_escape(row['coverage_tier'])}</strong></div>",
            f"<div class='kv'><span>Linked formal factor</span><strong>{_escape(row['linked_formal_factor_id'])}</strong></div>",
        ]
    )
    return "".join(rows)


def build_candidate_registry_review_html(
    *,
    registry_metadata: dict[str, Any],
    candidate_master: pd.DataFrame,
    candidate_evidence: pd.DataFrame,
    run_index: pd.DataFrame,
    status_history: pd.DataFrame,
) -> str:
    current_df = candidate_master[candidate_master["is_current"].fillna(False)].copy()
    current_df = current_df.sort_values(
        ["object_type", "theme_id", "recommended_status", "object_name"],
        ascending=[True, True, True, True],
        na_position="last",
    )

    object_counts = current_df["object_type"].fillna("").value_counts().to_dict()
    theme_counts = current_df["theme_id"].fillna("").value_counts().to_dict()
    recommended_counts = current_df["recommended_status"].fillna("observed").value_counts().to_dict()
    manual_counts = current_df["status"].fillna("observed").value_counts().to_dict()

    object_options = "".join(
        f"<option value='{_escape(value)}'>{_escape(value)}</option>"
        for value in sorted(current_df["object_type"].dropna().astype(str).unique().tolist())
    )
    theme_options = "".join(
        f"<option value='{_escape(value)}'>{_escape(value)}</option>"
        for value in sorted(current_df["theme_id"].dropna().astype(str).unique().tolist())
    )

    overview_rows = []
    detail_blocks = []
    for _, row in current_df.iterrows():
        candidate_id = _fmt_text(row["candidate_id"])
        object_name = _fmt_text(row["object_name"])
        slug = _slug(candidate_id)
        search_blob = " ".join(
            [
                candidate_id,
                object_name,
                _fmt_text(row["theme_id"]),
                _fmt_text(row["object_type"]),
                _fmt_text(row["recommended_status"]),
                _fmt_text(row["status"]),
                _fmt_text(row["source_type"]),
                _fmt_text(row["transform_family"]),
                _fmt_text(row["construction_rule"]),
                _fmt_text(row["linked_formal_factor_id"]),
            ]
        ).lower()
        overview_rows.append(
            "<tr "
            f"data-search='{_escape(search_blob)}' "
            f"data-theme='{_escape(row['theme_id'])}' "
            f"data-object-type='{_escape(row['object_type'])}' "
            f"data-recommended='{_escape(row['recommended_status'])}' "
            f"data-status='{_escape(row['status'])}'>"
            f"<td><a href='#{slug}'><code>{_escape(object_name)}</code></a></td>"
            f"<td>{_escape(row['theme_id'])}</td>"
            f"<td>{_badge(_fmt_text(row['object_type']), 'badge-kind')}</td>"
            f"<td>{_badge(_fmt_text(row['recommended_status']), 'badge-recommended')}</td>"
            f"<td>{_badge(_fmt_text(row['status']), 'badge-status')}</td>"
            f"<td>{_fmt_num(row['latest_rank_icir'])}</td>"
            f"<td>{_fmt_bool(row['latest_selected_for_recipe'])}</td>"
            f"<td>{_fmt_num(row['latest_holdout_relative_excess_return'])}</td>"
            f"<td>{_fmt_num(row['latest_event_relative_excess_return'])}</td>"
            "</tr>"
        )
        detail_blocks.append(
            f"""
<details class="detail-card" id="{slug}">
  <summary>
    <code>{_escape(object_name)}</code>
    {_badge(_fmt_text(row['theme_id']), 'badge-kind')}
    {_badge(_fmt_text(row['object_type']), 'badge-kind')}
    {_badge(_fmt_text(row['recommended_status']), 'badge-recommended')}
    {_badge(_fmt_text(row['status']), 'badge-status')}
  </summary>
  <div class="detail-grid">
    <div class="panel">
      <h3>Definition</h3>
      {_detail_definition_block(row)}
      <div class="kv"><span>Hash</span><code class="hash">{_escape(row['definition_hash'])}</code></div>
      <div class="kv"><span>Created</span><strong>{_escape(row['created_at'])}</strong></div>
      <div class="kv"><span>Updated</span><strong>{_escape(row['updated_at'])}</strong></div>
    </div>
    <div class="panel">
      <h3>Latest Evidence</h3>
      <div class="kv"><span>Stage</span><strong>{_escape(row['latest_run_stage'])}</strong></div>
      <div class="kv"><span>Universe</span><strong>{_escape(row['latest_universe_id'])}</strong></div>
      <div class="kv"><span>Coverage ratio</span><strong>{_fmt_num(row['latest_coverage_ratio'])}</strong></div>
      <div class="kv"><span>Rank ICIR</span><strong>{_fmt_num(row['latest_rank_icir'])}</strong></div>
      <div class="kv"><span>Selected for recipe</span><strong>{_fmt_bool(row['latest_selected_for_recipe'])}</strong></div>
      <div class="kv"><span>Holdout excess</span><strong>{_fmt_num(row['latest_holdout_relative_excess_return'])}</strong></div>
      <div class="kv"><span>Event excess</span><strong>{_fmt_num(row['latest_event_relative_excess_return'])}</strong></div>
      <div class="kv"><span>Last run</span><code>{_escape(row['last_seen_run_id'])}</code></div>
    </div>
    <div class="panel">
      <h3>Workflow</h3>
      <div class="kv"><span>Recommended</span><strong>{_escape(row['recommended_status'])}</strong></div>
      <div class="kv"><span>Manual status</span><strong>{_escape(row['status'])}</strong></div>
      <div class="kv"><span>Notes</span><div>{_escape(row['notes']) or '<span class="empty-inline">No notes</span>'}</div></div>
      <div class="kv"><span>Review reason</span><div>{_escape(row['review_reason']) or '<span class="empty-inline">No review note</span>'}</div></div>
      <div class="kv"><span>Latest rejection</span><div>{_escape(row['latest_rejection_reason']) or '<span class="empty-inline">Not rejected</span>'}</div></div>
    </div>
  </div>
</details>
"""
        )

    run_rows = []
    for _, row in run_index.sort_values("generated_at", ascending=False).head(12).iterrows():
        run_rows.append(
            "<tr>"
            f"<td>{_escape(row['generated_at'])}</td>"
            f"<td>{_escape(row['theme'])}</td>"
            f"<td>{_escape(row['stage'])}</td>"
            f"<td><code>{_escape(row['run_id'])}</code></td>"
            f"<td>{_fmt_int(row['artifact_count'])}</td>"
            f"<td>{_escape(row['status'])}</td>"
            f"<td class='path-cell'>{_escape(row['run_dir'])}</td>"
            "</tr>"
        )

    status_rows = []
    for _, row in status_history.sort_values("changed_at", ascending=False).head(20).iterrows():
        status_rows.append(
            "<tr>"
            f"<td>{_escape(row['changed_at'])}</td>"
            f"<td><code>{_escape(row['candidate_id'])}</code></td>"
            f"<td>{_badge(_fmt_text(row['old_status']), 'badge-status')}</td>"
            f"<td>{_badge(_fmt_text(row['new_status']), 'badge-status')}</td>"
            f"<td>{_escape(row['reason'])}</td>"
            "</tr>"
        )

    stats = [
        _stat_card("Current candidates", _fmt_int(len(current_df))),
        _stat_card("Theme runs", _fmt_int(registry_metadata.get("theme_run_count", 0))),
        _stat_card("Theme components", _fmt_int(object_counts.get("theme_component", 0))),
        _stat_card("Theme recipes", _fmt_int(object_counts.get("theme_recipe", 0))),
        _stat_card("Recommended candidate+", _fmt_int(sum(int(recommended_counts.get(key, 0)) for key in ("candidate", "under_review", "promoted")))),
        _stat_card("Last theme sync", _fmt_text(registry_metadata.get("last_theme_sync_at")) or "Not synced"),
    ]

    summary_pills = "".join(
        f"<span class='pill'>{_escape(theme_id)}: <strong>{count}</strong></span>"
        for theme_id, count in theme_counts.items()
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Candidate Registry Review</title>
  <style>
    :root {{
      --bg: #f5f1ea; --panel: #fffdf9; --line: #ddd4c4; --ink: #1f2937; --muted: #6b7280;
      --shadow: 0 10px 28px rgba(31,41,55,.08); --green: #14532d; --amber: #b45309; --blue: #1d4ed8; --red: #991b1b;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: "Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; background: linear-gradient(180deg,#fbfaf7 0%,var(--bg) 100%); color: var(--ink); }}
    .page {{ max-width: 1440px; margin: 0 auto; padding: 28px 22px 56px; }}
    .hero,.panel,.stat-card,.table-wrap,.detail-card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 18px; box-shadow: var(--shadow); }}
    .hero {{ padding: 24px; }}
    .stats {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(180px,1fr)); gap: 14px; margin-top: 18px; }}
    .stat-card {{ padding: 16px; }}
    .stat-label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .05em; }}
    .stat-value {{ margin-top: 8px; font-size: 28px; font-weight: 700; }}
    .section {{ margin-top: 24px; }}
    .toolbar {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 14px 0; align-items: center; }}
    .toolbar input,.toolbar select {{ min-width: 180px; padding: 10px 12px; border: 1px solid var(--line); border-radius: 12px; background: white; }}
    .toolbar .result-count {{ margin-left: auto; color: var(--muted); }}
    .pill {{ display: inline-flex; gap: 6px; padding: 7px 12px; margin: 6px 8px 0 0; border-radius: 999px; border: 1px solid var(--line); background: white; font-size: 13px; }}
    .table-wrap {{ overflow: auto; max-height: 620px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th,td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #ece5d8; vertical-align: top; }}
    th {{ position: sticky; top: 0; background: #faf7ef; color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
    .badge {{ display: inline-flex; align-items: center; padding: 4px 10px; border-radius: 999px; border: 1px solid transparent; font-size: 12px; font-weight: 600; }}
    .badge-kind {{ background: #eef2ff; color: #3730a3; border-color: #c7d2fe; }}
    .badge-recommended,.badge-status {{ text-transform: capitalize; }}
    .badge-observed {{ background: #e2e8f0; color: #475569; border-color: #cbd5e1; }}
    .badge-candidate {{ background: #fef3c7; color: var(--amber); border-color: #fcd34d; }}
    .badge-under-review,.badge-promoted {{ background: #dcfce7; color: var(--green); border-color: #86efac; }}
    .badge-rejected,.badge-archived {{ background: #fee2e2; color: var(--red); border-color: #fca5a5; }}
    .badge-already-formal {{ background: #dbeafe; color: var(--blue); border-color: #93c5fd; }}
    .detail-card {{ margin-bottom: 14px; overflow: hidden; }}
    .detail-card summary {{ cursor: pointer; list-style: none; padding: 16px 18px; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; border-bottom: 1px solid #efe8db; }}
    .detail-card summary::-webkit-details-marker {{ display: none; }}
    .detail-grid {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(320px,1fr)); gap: 14px; padding: 16px; }}
    .panel {{ padding: 16px; }}
    .kv {{ display: grid; grid-template-columns: 140px 1fr; gap: 10px; padding: 7px 0; border-bottom: 1px dashed #ece5d8; }}
    .kv:last-child {{ border-bottom: 0; }}
    .kv span {{ color: var(--muted); font-size: 13px; }}
    code {{ font-family: Consolas,"SFMono-Regular",monospace; }}
    .hash,.path-cell {{ word-break: break-all; }}
    .empty-inline {{ color: var(--muted); font-style: italic; }}
    @media (max-width: 1080px) {{ .toolbar .result-count {{ margin-left: 0; }} }}
  </style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <h1>Candidate Registry Review</h1>
      <p>这是候选池的人读视图。这里会把 theme strategy 研究里的 component 和 recipe 候选统一收口，方便你看当前有哪些候选、它们最近的证据如何、以及哪些已经值得继续跟进。</p>
      <div class="stats">{''.join(stats)}</div>
    </section>

    <section class="section panel">
      <h2>Theme Distribution</h2>
      <div>{summary_pills}</div>
    </section>

    <section class="section">
      <h2>All Current Candidates</h2>
      <div class="toolbar">
        <input id="filter-query" type="search" placeholder="Search name, theme, type, linked formal factor...">
        <select id="filter-theme"><option value="">All themes</option>{theme_options}</select>
        <select id="filter-type"><option value="">All object types</option>{object_options}</select>
        <select id="filter-recommended">
          <option value="">All recommended statuses</option>
          <option value="observed">observed</option>
          <option value="candidate">candidate</option>
          <option value="under_review">under_review</option>
          <option value="promoted">promoted</option>
          <option value="rejected">rejected</option>
          <option value="archived">archived</option>
          <option value="already_formal">already_formal</option>
        </select>
        <select id="filter-status">
          <option value="">All manual statuses</option>
          <option value="observed">observed</option>
          <option value="candidate">candidate</option>
          <option value="under_review">under_review</option>
          <option value="promoted">promoted</option>
          <option value="rejected">rejected</option>
          <option value="archived">archived</option>
          <option value="already_formal">already_formal</option>
        </select>
        <div class="result-count">Showing <strong id="visible-count">{len(current_df)}</strong> of {len(current_df)}</div>
      </div>
      <div class="table-wrap">
        <table id="candidate-table">
          <thead>
            <tr>
              <th>Name</th><th>Theme</th><th>Type</th><th>Recommended</th><th>Manual</th><th>Rank ICIR</th><th>Selected</th><th>Holdout Excess</th><th>Event Excess</th>
            </tr>
          </thead>
          <tbody>{''.join(overview_rows)}</tbody>
        </table>
      </div>
    </section>

    <section class="section">
      <h2>Detail Cards</h2>
      {''.join(detail_blocks)}
    </section>

    <section class="section panel">
      <h2>Recent Imported Runs</h2>
      <div class="table-wrap"><table><thead><tr><th>Generated</th><th>Theme</th><th>Stage</th><th>Run ID</th><th>Artifacts</th><th>Status</th><th>Run Dir</th></tr></thead><tbody>{''.join(run_rows) or "<tr><td colspan='7'>No runs imported yet.</td></tr>"}</tbody></table></div>
    </section>

    <section class="section panel">
      <h2>Manual Status History</h2>
      <div class="table-wrap"><table><thead><tr><th>Changed</th><th>Candidate</th><th>Old</th><th>New</th><th>Reason</th></tr></thead><tbody>{''.join(status_rows) or "<tr><td colspan='5'>No manual status changes yet.</td></tr>"}</tbody></table></div>
    </section>
  </div>
  <script>
    (() => {{
      const queryInput = document.getElementById("filter-query");
      const themeInput = document.getElementById("filter-theme");
      const typeInput = document.getElementById("filter-type");
      const recommendedInput = document.getElementById("filter-recommended");
      const statusInput = document.getElementById("filter-status");
      const rows = Array.from(document.querySelectorAll("#candidate-table tbody tr"));
      const visibleCount = document.getElementById("visible-count");
      function applyFilters() {{
        const query = queryInput.value.trim().toLowerCase();
        const theme = themeInput.value;
        const objectType = typeInput.value;
        const recommended = recommendedInput.value;
        const status = statusInput.value;
        let visible = 0;
        rows.forEach((row) => {{
          const matchQuery = !query || (row.dataset.search || "").includes(query);
          const matchTheme = !theme || row.dataset.theme === theme;
          const matchType = !objectType || row.dataset.objectType === objectType;
          const matchRecommended = !recommended || row.dataset.recommended === recommended;
          const matchStatus = !status || row.dataset.status === status;
          const show = matchQuery && matchTheme && matchType && matchRecommended && matchStatus;
          row.hidden = !show;
          if (show) visible += 1;
        }});
        visibleCount.textContent = String(visible);
      }}
      [queryInput, themeInput, typeInput, recommendedInput, statusInput].forEach((node) => {{
        node.addEventListener("input", applyFilters);
        node.addEventListener("change", applyFilters);
      }});
      applyFilters();
    }})();
  </script>
</body>
</html>"""
