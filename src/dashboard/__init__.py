"""Centralized HTML dashboard generator for the 量化系统 research system.

This package reads every machine-readable source in the repo (the five typed
registries, field-governance YAML, the data tracker, the factor catalog, the
research/output artifacts, the durable ``project_state.md`` memory) plus the
Claude Code session transcripts, and renders a single self-contained
``index.html`` board.

Nothing here mutates project data. The board is a *projection* of the existing
sources, rebuilt on demand. Every collector degrades gracefully: a missing or
malformed source becomes a visible warning in its section rather than a failed
build, because the board is regenerated automatically (SessionEnd hook +
scheduled task) and must always produce output.

This package (``src/dashboard/``) is an auxiliary read-only reporting tool — NOT
one of the six research modules; it must never be imported into any formal
research/data path. Entry point: ``src/dashboard/build_dashboard.py`` → writes
``index.html`` at the project root.
"""

__version__ = "1.0.0"
