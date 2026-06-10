"""Collect and summarize Claude Code session transcripts for this project.

Each ``*.jsonl`` transcript under ``~/.claude/projects/<encoded>/`` is parsed
into a compact per-session record (timestamps, branch, first prompt, tool
histogram, files touched, commits, last TodoWrite state, a synthesized summary).
Parsing is cached by (mtime, size) so the only files reparsed on a rebuild are
the ones that changed since last time — the per-session-stop hook stays fast.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .util import (
    SESSIONS_CACHE,
    read_json,
    resolve_sessions_dir,
)

EDIT_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}
SUBAGENT_TOOLS = {"Task", "Agent"}
SHELL_TOOLS = {"Bash", "PowerShell"}
_CMD_RE = re.compile(r"<command-(?:name|message|args)>(.*?)</command-[a-z]+>", re.S)
_TAG_RE = re.compile(r"<[^>]+>")


def _clean_prompt(text: str) -> tuple[str, bool]:
    """Return (display_text, is_slash_command). Strips command/system wrappers."""
    is_cmd = "<command-name>" in text
    if is_cmd:
        names = _CMD_RE.findall(text)
        joined = " ".join(p.strip() for p in names if p.strip())
        text = joined or text
    # drop any residual xml-ish tags and reminder blocks
    text = re.sub(r"<system-reminder>.*?</system-reminder>", " ", text, flags=re.S)
    text = _TAG_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text, is_cmd


def _iter_text_parts(content: Any):
    if isinstance(content, str):
        yield content
    elif isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text" and part.get("text"):
                yield part["text"]


def _iter_tool_uses(content: Any):
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") == "tool_use":
                yield part.get("name", "?"), part.get("input", {}) or {}


def parse_transcript(path: Path) -> dict:
    rec: dict[str, Any] = {
        "session_id": path.stem,
        "first_prompt": "",
        "is_command": False,
        "branch": None,
        "start": None,
        "end": None,
        "n_user": 0,
        "n_assistant": 0,
        "tools": {},
        "files_edited": [],
        "commits": [],
        "subagents": 0,
        "todos": [],
        "summary": "",
        "out_tokens": 0,
        "entrypoint": None,
        "version": None,
        "lines": 0,
    }
    files: dict[str, int] = {}
    last_text = ""
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                o = __import__("json").loads(line)
            except Exception:
                continue
            rec["lines"] += 1
            ts = o.get("timestamp")
            if ts:
                if rec["start"] is None:
                    rec["start"] = ts
                rec["end"] = ts
            if o.get("gitBranch"):
                rec["branch"] = o["gitBranch"]
            if o.get("entrypoint"):
                rec["entrypoint"] = o["entrypoint"]
            if o.get("version"):
                rec["version"] = o["version"]

            ty = o.get("type")
            msg = o.get("message") or {}
            content = msg.get("content")

            if ty == "user" and o.get("userType") == "external" and not o.get("isSidechain"):
                # a *real* prompt has text content and is not a tool_result echo
                if "toolUseResult" not in o:
                    texts = list(_iter_text_parts(content))
                    if texts:
                        rec["n_user"] += 1
                        if not rec["first_prompt"]:
                            disp, is_cmd = _clean_prompt(texts[0])
                            rec["first_prompt"] = disp
                            rec["is_command"] = is_cmd

            elif ty == "assistant":
                rec["n_assistant"] += 1
                usage = msg.get("usage") or {}
                rec["out_tokens"] += int(usage.get("output_tokens") or 0)
                for t in _iter_text_parts(content):
                    last_text = t
                for name, inp in _iter_tool_uses(content):
                    rec["tools"][name] = rec["tools"].get(name, 0) + 1
                    if name in EDIT_TOOLS:
                        fp = inp.get("file_path") or inp.get("notebook_path")
                        if fp:
                            files[fp] = files.get(fp, 0) + 1
                    elif name in SUBAGENT_TOOLS:
                        rec["subagents"] += 1
                    elif name in SHELL_TOOLS:
                        cmd = str(inp.get("command", ""))
                        if "git commit" in cmd:
                            m = re.search(r"-m\s+['\"]?([^'\"]{4,120})", cmd)
                            rec["commits"].append(m.group(1).strip() if m else "(git commit)")
                    if name == "TodoWrite":
                        todos = inp.get("todos")
                        if isinstance(todos, list):
                            rec["todos"] = todos  # keep the latest snapshot

    rec["files_edited"] = sorted(files, key=lambda k: -files[k])
    if last_text:
        clean = _TAG_RE.sub(" ", last_text)
        rec["summary"] = re.sub(r"\s+", " ", clean).strip()[:400]
    return rec


def collect_sessions() -> dict:
    """Return {sessions: [record...], dir: str|None, count, error}.

    Records are sorted newest-end-first. Uses an mtime/size cache.
    """
    sdir = resolve_sessions_dir()
    if sdir is None:
        return {"sessions": [], "dir": None, "count": 0, "error": "session dir not found"}

    cache = read_json(SESSIONS_CACHE) or {}
    cache = cache if isinstance(cache, dict) else {}
    new_cache: dict[str, Any] = {}
    records: list[dict] = []

    for jl in sdir.glob("*.jsonl"):
        try:
            st = jl.stat()
            key = jl.stem
            sig = f"{int(st.st_mtime)}:{st.st_size}"
            cached = cache.get(key)
            if cached and cached.get("_sig") == sig:
                rec = cached
            else:
                rec = parse_transcript(jl)
                rec["_sig"] = sig
                rec["mtime"] = int(st.st_mtime)
                rec["size"] = st.st_size
            new_cache[key] = rec
            records.append(rec)
        except Exception:
            continue

    # persist cache (before attaching tasks, so the volatile task state is never cached)
    try:
        SESSIONS_CACHE.parent.mkdir(parents=True, exist_ok=True)
        SESSIONS_CACHE.write_text(
            __import__("json").dumps(new_cache, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass

    # attach Task-tool tasks per session — fresh each build (they change
    # independently of the transcript; not all sessions use them).
    for rec in records:
        rec["tasks"] = _session_tasks(rec["session_id"])

    records.sort(key=lambda r: r.get("end") or "", reverse=True)
    return {"sessions": records, "dir": str(sdir), "count": len(records), "error": None}


def _session_tasks(session_id: str) -> list[dict]:
    """Read the Task-tool store for a session → [{subject, status}], file order."""
    d = Path.home() / ".claude" / "tasks" / session_id
    if not d.exists():
        return []
    out: list[dict] = []
    files = sorted(d.glob("*.json"), key=lambda p: (len(p.stem), p.stem))
    for jf in files:
        t = read_json(jf)
        if isinstance(t, dict) and t.get("subject"):
            out.append({"subject": t["subject"], "status": str(t.get("status", "") or "")})
    return out
