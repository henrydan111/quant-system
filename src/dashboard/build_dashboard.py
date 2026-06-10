"""Build the centralized HTML dashboard for the 量化系统 research system.

Reads every machine-readable source (registries, field governance, factor
catalog, research/output artifacts, project_state memory) plus the Claude Code
session transcripts, and renders a single self-contained HTML board.

Usage:
    venv/Scripts/python.exe src/dashboard/build_dashboard.py [--quiet] [--open]

The build is a read-only projection — it never mutates project data. It is safe
to run from a SessionEnd hook or a scheduled task; every source degrades
gracefully. Run-location independent: it bootstraps sys.path from its own path.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import webbrowser
from pathlib import Path

# src/dashboard/build_dashboard.py -> parents[2] == project root
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))                 # enable `import src.dashboard...` / `import src...`

from src.dashboard.actions import derive_actions, load_board      # noqa: E402
from src.dashboard.content import (                                # noqa: E402
    collect_data, collect_factors, collect_knowledge,
    collect_research, collect_strategy,
)
from src.dashboard.governance import collect_governance            # noqa: E402
from src.dashboard.health import collect_health                    # noqa: E402
from src.dashboard.render import render_html                       # noqa: E402
from src.dashboard.sessions import collect_sessions                # noqa: E402
from src.dashboard.util import (                                   # noqa: E402
    HTML_OUTPUT, OUTPUT_DIR, git_branch, git_status_clean, now_iso, rel,
)

log = logging.getLogger("dashboard")


def build(quiet: bool = False) -> Path:
    # NOTE: logging is unconditional here — the file handler always records the
    # summary (observability for the hook + scheduled task); the --quiet flag
    # only raises the *console* handler level, it does not silence the file.
    t0 = time.time()
    log.info("collecting sources…")

    board = load_board()
    sessions = collect_sessions()
    knowledge = collect_knowledge()
    data = collect_data()
    factors = collect_factors()
    research = collect_research()
    strategy = collect_strategy(board)
    actions = derive_actions(sessions, factors, strategy, board)
    health = collect_health(factors, research)
    governance = collect_governance()

    ctx = {
        "build": {
            "generated": now_iso(),
            "branch": git_branch(),
            "git_clean": git_status_clean(),
            "build_secs": round(time.time() - t0, 1),
        },
        "knowledge": knowledge, "data": data, "factors": factors,
        "research": research, "strategy": strategy,
        "sessions": sessions, "actions": actions, "health": health,
        "governance": governance,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    html_path = HTML_OUTPUT  # the board body lives at the project root
    html_path.write_text(render_html(ctx), encoding="utf-8")
    # tiny build-id sentinel polled by the page's lightweight auto-refresh (render.py JS)
    (HTML_OUTPUT.parent / "build_id.txt").write_text(ctx["build"]["generated"], encoding="utf-8")
    # machine snapshot (drop the heavy per-session cache fields)
    snap = dict(ctx)
    snap["sessions"] = {k: v for k, v in sessions.items() if k != "sessions"}
    snap["sessions"]["records"] = [
        {kk: vv for kk, vv in s.items() if kk not in ("_sig",)} for s in sessions.get("sessions", [])
    ]
    (OUTPUT_DIR / "data.json").write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")

    st = factors.get("status_tally", {})
    log.info("factors: %s rows (approved %s / candidate %s / draft %s) · catalog %s",
             factors.get("total_rows", 0), st.get("approved", 0), st.get("candidate", 0),
             st.get("draft", 0), factors.get("catalog", {}).get("total", "?"))
    log.info("data: %s governed datasets · %s qlib instruments",
             len(data.get("datasets", [])), data.get("qlib", {}).get("instruments", "?"))
    log.info("sessions: %s transcripts collected", sessions.get("count", 0))
    log.info("built in %.1fs -> %s", ctx["build"]["build_secs"], rel(html_path))
    return html_path


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the centralized HTML dashboard")
    ap.add_argument("--quiet", action="store_true", help="suppress progress logging (for hooks)")
    ap.add_argument("--open", action="store_true", help="open the dashboard in a browser after building")
    args = ap.parse_args()

    # File handler always logs INFO (observability for the hook + scheduled task,
    # which run with no console); console handler honors --quiet.
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    (ROOT / "logs").mkdir(exist_ok=True)
    fh = logging.FileHandler(ROOT / "logs" / "dashboard_build.log", encoding="utf-8")
    fh.setLevel(logging.INFO); fh.setFormatter(fmt)
    sh = logging.StreamHandler()
    sh.setLevel(logging.WARNING if args.quiet else logging.INFO); sh.setFormatter(fmt)
    logging.basicConfig(level=logging.INFO, handlers=[fh, sh])
    try:
        path = build(quiet=args.quiet)
    except Exception:
        log.exception("dashboard build failed")
        return 1
    if args.open:
        webbrowser.open(path.as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
