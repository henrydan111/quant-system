"""Self-audit of the dashboard's source freshness / consistency.

Read-only. The dashboard can only ever show what its source files say; this
module surfaces *drift between live code and those sources* (and how stale each
source is) so a lagging source becomes a visible warning on the board instead of
a silent wrong number. Nothing here mutates anything.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from . import translate
from .util import PROJECT_ROOT, git_recent_commits, read_json, rel


def _age_secs(p: Path):
    try:
        return time.time() - p.stat().st_mtime
    except Exception:
        return None


def _fmt_age(secs) -> str:
    if secs is None:
        return "—"
    if secs < 3600:
        return f"{int(secs // 60)} 分钟前"
    if secs < 86400:
        return f"{secs / 3600:.1f} 小时前"
    return f"{secs / 86400:.1f} 天前"


def collect_health(factors: dict, research: dict) -> dict:
    out: dict[str, Any] = {"checks": [], "files": [], "summary": {}, "error": None}
    try:
        checks = out["checks"]

        # 1) catalog (live from code) vs registry current factor count
        cat = (factors.get("catalog") or {}).get("total")
        cur = len(factors.get("factors") or [])
        if isinstance(cat, int):
            if cat == cur:
                checks.append(dict(label="catalog ↔ registry 一致", level="ok",
                                   value=f"{cat} = {cur}", hint="代码因子数与 registry 当前数一致"))
            elif cat > cur:
                checks.append(dict(label="catalog 有未同步因子", level="warn",
                                   value=f"catalog {cat} > registry {cur}",
                                   hint="catalog.py 新增了因子但 registry 未同步——运行 sync_catalog"))
            else:
                checks.append(dict(label="registry 含 catalog 外因子", level="info",
                                   value=f"catalog {cat} < registry {cur}",
                                   hint="registry 有 catalog 之外的注册项（如 new-data draft），通常正常"))

        # 2) Sonnet translation coverage of the current factor set
        ids = [f["id"] for f in (factors.get("factors") or [])]
        have = set((translate._load().get("factors") or {}).keys())
        missing = [i for i in ids if i not in have]
        if ids and not missing:
            checks.append(dict(label="Sonnet 翻译覆盖", level="ok",
                               value=f"{len(ids)}/{len(ids)} 全覆盖", hint="全部当前因子都有中英文描述"))
        elif missing:
            checks.append(dict(label="Sonnet 翻译缺口", level="warn",
                               value=f"{len(missing)} 个因子未翻译",
                               hint="新因子缺中英文描述，需重跑 Sonnet 补译。例: " + ", ".join(missing[:5])))

        # 3) project_state.md freshness vs the latest git commit
        ms = research.get("milestones") or []
        note_date = ms[0]["date"] if ms else None
        commits = git_recent_commits(1)
        commit_date = commits[0]["date"] if commits else None
        if note_date and commit_date:
            if note_date >= commit_date:
                checks.append(dict(label="project_state 新鲜度", level="ok",
                                   value=f"记录 {note_date} ≥ 提交 {commit_date}",
                                   hint="顶部 Update Note 不落后于最新提交"))
            else:
                checks.append(dict(label="project_state 可能落后", level="warn",
                                   value=f"记录 {note_date} < 提交 {commit_date}",
                                   hint="有更新的提交但 project_state 顶部 Update Note 未更新（CLAUDE.md §11.1）"))

        # 4) last run_daily_qa result
        logs = PROJECT_ROOT / "logs"
        qa = (sorted(logs.glob("qa_report_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
              if logs.exists() else [])
        if not qa:
            checks.append(dict(label="run_daily_qa", level="warn", value="无记录",
                               hint="logs 下没有 qa_report——建议跑 scripts/run_daily_qa.py"))
        else:
            newest = qa[0]
            d = read_json(newest) or {}
            cl = d.get("checks") or []
            n_ok = sum(1 for c in cl if c.get("ok"))
            n = len(cl)
            secs = _age_secs(newest)
            allok = bool(n) and n_ok == n
            stale = (secs or 0) > 7 * 86400
            checks.append(dict(label="最近 run_daily_qa",
                               level=("ok" if (allok and not stale) else "warn"),
                               value=f"{n_ok}/{n} 通过 · {_fmt_age(secs)}",
                               hint=rel(newest) + ("（>7 天未跑）" if stale else "")))

        # file mtimes — how stale each key source is (info)
        for label, p in [
            ("factor_master", "data/factor_registry/factor_master.parquet"),
            ("field_status", "config/field_registry/field_status.yaml"),
            ("project_state", "project_state.md"),
            ("qlib 日历", "data/qlib_data/calendars/day.txt"),
            ("board.yaml", "workspace/configs/dashboard_board.yaml"),
            ("translations", "src/dashboard/translations.json"),
        ]:
            fp = PROJECT_ROOT / p
            out["files"].append(dict(label=label, path=p, age=_fmt_age(_age_secs(fp)), exists=fp.exists()))

        for c in checks:
            out["summary"][c["level"]] = out["summary"].get(c["level"], 0) + 1
    except Exception as e:  # pragma: no cover
        out["error"] = f"{type(e).__name__}: {e}"
    return out
