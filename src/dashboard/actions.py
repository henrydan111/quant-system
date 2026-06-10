"""Derive the three action sections (进行中 / 待办 / 推荐).

Each section = auto-derived signals + a human-curated overlay from
``workspace/configs/dashboard_board.yaml``. Auto signals come from: the current
git branch, recent session activity, unfinished TodoWrite snapshots, open
Task-tool tasks, and a few registry/coverage heuristics. The curated overlay is
always listed first and marked as such.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .util import (
    git_branch,
    git_status_clean,
    read_json,
    read_yaml,
    BOARD_YAML,
)

_DONE = {"completed", "cancelled", "canceled", "done"}


def load_board() -> dict:
    data = read_yaml(BOARD_YAML)
    return data if isinstance(data, dict) else {}


def _open_tasks(session_ids: list[str]) -> list[dict]:
    """Read the Task-tool store for recent sessions; return non-completed tasks."""
    tasks_root = Path.home() / ".claude" / "tasks"
    out: list[dict] = []
    if not tasks_root.exists():
        return out
    for sid in session_ids:
        d = tasks_root / sid
        if not d.exists():
            continue
        for jf in d.glob("*.json"):
            t = read_json(jf)
            if isinstance(t, dict) and str(t.get("status", "")).lower() not in _DONE:
                subj = t.get("subject") or t.get("description") or ""
                if subj:
                    out.append({"text": subj, "status": t.get("status", "?"), "session": sid[:8]})
    return out


def _unfinished_todos(sessions: list[dict], k: int = 4) -> list[dict]:
    """Latest unfinished TodoWrite items from the k most recent sessions."""
    out: list[dict] = []
    seen: set[str] = set()
    for s in sessions[:k]:
        for td in s.get("todos", []) or []:
            if not isinstance(td, dict):
                continue
            if str(td.get("status", "")).lower() in _DONE:
                continue
            content = td.get("content") or td.get("activeForm") or ""
            if content and content not in seen:
                seen.add(content)
                out.append({"text": content, "status": td.get("status", "pending"), "session": s["session_id"][:8]})
    return out


def derive_actions(sessions_result: dict, factors: dict, strategy: dict, board: dict) -> dict:
    sessions = sessions_result.get("sessions", [])
    branch = git_branch()
    recent_ids = [s["session_id"] for s in sessions[:8]]

    # ---- 进行中 ---------------------------------------------------------- #
    in_progress: list[dict] = []
    for item in board.get("in_progress", []) or []:
        in_progress.append({"text": str(item), "src": "board"})
    in_progress.extend({**t, "src": "todo"} for t in _unfinished_todos(sessions))
    in_progress.extend({**t, "src": "task"} for t in _open_tasks(recent_ids))

    # ---- 待办 ------------------------------------------------------------ #
    todo: list[dict] = []
    for item in board.get("todo", []) or []:
        todo.append({"text": str(item), "src": "board"})
    if git_status_clean() is False:
        todo.append({"text": f"工作树有未提交改动（分支 {branch}）— 决定提交或还原", "src": "auto"})

    # ---- 推荐 ------------------------------------------------------------ #
    rec: list[dict] = []
    for item in board.get("recommended", []) or []:
        rec.append({"text": str(item), "src": "board"})
    reg = strategy.get("registry", {})
    if reg.get("strategies", 0) == 0:
        rec.append({"text": "策略注册表为空：把已验证可部署的策略（如 大市值价值 top10）沉淀进 strategy_registry，让策略层不再只靠 FINDINGS", "src": "auto"})
    if strategy.get("models", 0) == 0:
        rec.append({"text": "模型层为空：substantive 的 ML 训练应经 ExperimentTracker 登记并写入 model_registry", "src": "auto"})
    cand = factors.get("status_tally", {}).get("candidate", 0)
    if cand:
        rec.append({"text": f"{cand} 个 candidate 因子待评估：用 marginal/orthogonal IC（非 standalone ICIR）排序后再走 sealed-OOS", "src": "auto"})

    return {
        "branch": branch,
        "in_progress": in_progress,
        "todo": todo,
        "recommended": rec,
    }
