"""Shared helpers for the dashboard generator: path resolution, safe readers,
and small git/format utilities.

All readers are *fail-soft*: they return ``None``/empty plus an error string
rather than raising, so a single broken source never aborts the whole build.
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# src/dashboard/util.py -> parents[2] == project root (E:\量化系统)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# The board body lives at the project root (per user request); the machine
# snapshot + the incremental session cache stay under workspace/outputs.
HTML_OUTPUT = PROJECT_ROOT / "index.html"
OUTPUT_DIR = PROJECT_ROOT / "workspace" / "outputs" / "dashboard"
BOARD_YAML = PROJECT_ROOT / "workspace" / "configs" / "dashboard_board.yaml"
SESSIONS_CACHE = OUTPUT_DIR / ".sessions_cache.json"


# --------------------------------------------------------------------------- #
# Claude Code session-storage resolution
# --------------------------------------------------------------------------- #
def _encode_project_dirname(project_path: Path) -> str:
    """Replicate Claude Code's project-dir encoding: lowercase, every char
    outside [a-z0-9] becomes '-'. ``E:\\量化系统`` -> ``e------``."""
    return re.sub(r"[^a-zA-Z0-9]", "-", str(project_path)).lower()


def resolve_sessions_dir() -> Path | None:
    """Locate the Claude Code transcript directory for this project.

    Strategy: (1) computed encoded name under ~/.claude/projects; (2) if that
    is absent, scan every project dir and pick the one whose transcripts'
    ``cwd`` field matches our project root. Returns ``None`` if nothing matches.
    """
    projects_root = Path.home() / ".claude" / "projects"
    if not projects_root.exists():
        return None

    candidate = projects_root / _encode_project_dirname(PROJECT_ROOT)
    if candidate.exists():
        return candidate

    target = str(PROJECT_ROOT).lower()
    for d in projects_root.iterdir():
        if not d.is_dir():
            continue
        for jl in d.glob("*.jsonl"):
            try:
                with jl.open(encoding="utf-8", errors="replace") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        cwd = json.loads(line).get("cwd")
                        if cwd and str(cwd).lower() == target:
                            return d
                        break  # only need the first row's cwd
            except Exception:
                continue
    return None


# --------------------------------------------------------------------------- #
# Fail-soft readers
# --------------------------------------------------------------------------- #
def read_text(path: Path, limit: int | None = None) -> str | None:
    try:
        txt = path.read_text(encoding="utf-8", errors="replace")
        return txt[:limit] if limit else txt
    except Exception:
        return None


def read_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def read_jsonl(path: Path) -> list[dict]:
    out: list[dict] = []
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        continue
    except Exception:
        return out
    return out


def read_yaml(path: Path) -> Any | None:
    try:
        import yaml  # local import: keep base import light
        return yaml.safe_load(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def read_parquet(path: Path):
    """Return a DataFrame or ``None``. Falls back to a sibling .csv if the
    parquet read fails (every registry ships both)."""
    try:
        import pandas as pd
        return pd.read_parquet(path)
    except Exception:
        try:
            import pandas as pd
            csv = path.with_suffix(".csv")
            if csv.exists():
                return pd.read_csv(csv)
        except Exception:
            return None
    return None


# --------------------------------------------------------------------------- #
# git helpers
# --------------------------------------------------------------------------- #
def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        return None
    return None


def git_branch() -> str:
    return _git("rev-parse", "--abbrev-ref", "HEAD") or "?"


def git_recent_commits(n: int = 12) -> list[dict]:
    raw = _git("log", f"-{n}", "--pretty=format:%h%x1f%cI%x1f%s%x1f%an")
    rows: list[dict] = []
    if not raw:
        return rows
    for line in raw.splitlines():
        parts = line.split("\x1f")
        if len(parts) == 4:
            rows.append({"sha": parts[0], "date": parts[1][:10], "subject": parts[2], "author": parts[3]})
    return rows


def git_status_clean() -> bool | None:
    s = _git("status", "--porcelain")
    if s is None:
        return None
    return s.strip() == ""


# --------------------------------------------------------------------------- #
# misc
# --------------------------------------------------------------------------- #
def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def rel(path: Path) -> str:
    """Project-relative POSIX path for display/links."""
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except Exception:
        return str(path)


def human_size(n: int) -> str:
    f = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if f < 1024 or unit == "GB":
            return f"{f:.0f}{unit}" if unit == "B" else f"{f:.1f}{unit}"
        f /= 1024
    return f"{f:.1f}GB"
