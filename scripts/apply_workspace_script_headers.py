"""Apply PR 7 SCRIPT_STATUS headers to workspace scripts; archive D-class files.

Reads ``workspace/scripts/_audit/direct_engine_classification.csv`` (produced
by PR 2's audit) and:

* Prepends a SCRIPT_STATUS comment block to every A/B/C-class file.
* Moves every D-class file to
  ``workspace/scripts/archive/p1_jq_g5a2_investigation_2026_05/``.
* Writes a manifest at
  ``workspace/scripts/_audit/pr7_header_application_manifest.json``
  recording every action taken (for review).

Idempotent: re-running skips files that already carry the header (looks for
the ``# script_status:`` marker) and skips moves whose source already lives
in the archive directory.

Usage
=====

    venv/Scripts/python.exe scripts/apply_workspace_script_headers.py --dry-run
    venv/Scripts/python.exe scripts/apply_workspace_script_headers.py --apply
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Literal

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "workspace" / "scripts"
AUDIT_DIR = SCRIPTS_DIR / "_audit"
CSV_PATH = AUDIT_DIR / "direct_engine_classification.csv"
ARCHIVE_DIR = SCRIPTS_DIR / "archive" / "p1_jq_g5a2_investigation_2026_05"
MANIFEST_PATH = AUDIT_DIR / "pr7_header_application_manifest.json"

HeaderClass = Literal["A", "B", "C"]


# Header templates per class. Each block is a self-contained comment block
# that downstream auditors can grep for. Keep the keys lowercase + snake_case
# so machine parsing is straightforward.
_HEADER_TEMPLATES: dict[HeaderClass, str] = {
    "A": (
        "# ──────────────────────────────────────────────────────────────────────\n"
        "# PR 7 of 2026-05-26 freeze plan — SCRIPT_STATUS header block.\n"
        "# script_status: formal_candidate\n"
        "# formal_research_allowed: true\n"
        "# deployment_target: joinquant_daily\n"
        "# execution_profile: joinquant_daily_sim\n"
        "# requires_provider_manifest: true\n"
        "# requires_preload_strict: true\n"
        "# pr2_audit_class: A\n"
        "# notes: |\n"
        "#   Validation runner already on EventDrivenBacktester. PR 3's\n"
        "#   ExecutionProfile contract is now available — when this script is\n"
        "#   next touched, pass execution_profile='joinquant_daily_sim'\n"
        "#   instead of composing fill_mode + cost + slippage individually.\n"
        "# ──────────────────────────────────────────────────────────────────────\n"
    ),
    "B": (
        "# ──────────────────────────────────────────────────────────────────────\n"
        "# PR 7 of 2026-05-26 freeze plan — SCRIPT_STATUS header block.\n"
        "# script_status: formal_candidate\n"
        "# formal_research_allowed: true\n"
        "# deployment_target: joinquant_daily\n"
        "# execution_profile: joinquant_daily_sim\n"
        "# requires_provider_manifest: true\n"
        "# requires_preload_strict: true\n"
        "# pr2_audit_class: B\n"
        "# notes: |\n"
        "#   Uses QlibDataFeeder directly. Must call\n"
        "#   feeder.preload_features(..., strict=True) for engine-required\n"
        "#   fields before any get_features call. See\n"
        "#   src/backtest_engine/event_driven/constants.py::ENGINE_REQUIRED_FIELDS.\n"
        "# ──────────────────────────────────────────────────────────────────────\n"
    ),
    "C": (
        "# ──────────────────────────────────────────────────────────────────────\n"
        "# PR 7 of 2026-05-26 freeze plan — SCRIPT_STATUS header block.\n"
        "# script_status: historical_investigation\n"
        "# formal_research_allowed: false\n"
        "# deployment_target: joinquant_attribution_only\n"
        "# requires_provider_manifest: false\n"
        "# requires_preload_strict: false\n"
        "# pr2_audit_class: C\n"
        "# notes: |\n"
        "#   Sandbox / one-shot diagnostic script. NOT a formal research\n"
        "#   surface. Bare D.features calls inside this file are tolerated\n"
        "#   per scripts/lint_no_bare_qlib_features.py allowlist semantics\n"
        "#   (PR 6) but the script's output is not eligible for the formal\n"
        "#   release gate.\n"
        "# ──────────────────────────────────────────────────────────────────────\n"
    ),
}

# Marker we look for to decide whether the header is already applied.
_HEADER_MARKER = "# script_status:"


@dataclass(frozen=True)
class FileEntry:
    file: str
    cls: str
    rationale: str


def _read_classification() -> list[FileEntry]:
    if not CSV_PATH.exists():
        raise RuntimeError(f"Classification CSV not found at {CSV_PATH}")
    entries: list[FileEntry] = []
    with open(CSV_PATH, "r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            entries.append(FileEntry(
                file=row["file"], cls=row["class"], rationale=row["rationale"],
            ))
    return entries


def _has_header(text: str) -> bool:
    # Only inspect the first 30 lines so we don't false-positive on a comment
    # buried deep in the script.
    head = "\n".join(text.splitlines()[:30])
    return _HEADER_MARKER in head


def _insert_header_after_shebang(text: str, header: str) -> str:
    """Insert ``header`` immediately AFTER the shebang line if one exists,
    else at the very top of the file. Preserves docstrings, imports, and
    everything else verbatim.
    """
    lines = text.splitlines(keepends=True)
    if lines and lines[0].startswith("#!"):
        return lines[0] + header + "".join(lines[1:])
    return header + "".join(lines)


def _apply_header(path: Path, cls: HeaderClass) -> dict:
    template = _HEADER_TEMPLATES[cls]
    original = path.read_text(encoding="utf-8")
    if _has_header(original):
        return {"action": "skip", "reason": "already_headered"}
    new = _insert_header_after_shebang(original, template)
    path.write_text(new, encoding="utf-8")
    return {"action": "header_added", "class": cls}


def _archive_file(src: Path) -> dict:
    if not src.exists():
        return {"action": "skip", "reason": "source_missing"}
    if str(src.resolve()).startswith(str(ARCHIVE_DIR.resolve())):
        return {"action": "skip", "reason": "already_in_archive"}
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    dest = ARCHIVE_DIR / src.name
    if dest.exists():
        return {"action": "skip", "reason": "dest_exists", "dest": str(dest)}
    shutil.move(str(src), str(dest))
    return {"action": "archived", "dest": str(dest.relative_to(PROJECT_ROOT))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true",
                       help="Print every action without writing.")
    group.add_argument("--apply", action="store_true",
                       help="Actually apply the changes.")
    args = parser.parse_args()

    entries = _read_classification()
    manifest_rows: list[dict] = []
    counts = {"A": 0, "B": 0, "C": 0, "D": 0, "skipped": 0}

    for entry in entries:
        cls = entry.cls
        src_path = SCRIPTS_DIR / entry.file
        if cls in ("A", "B", "C"):
            if args.dry_run:
                action = {"action": "would_add_header", "class": cls}
                if _has_header(src_path.read_text(encoding="utf-8")):
                    action = {"action": "would_skip", "reason": "already_headered"}
                    counts["skipped"] += 1
                else:
                    counts[cls] += 1
            else:
                action = _apply_header(src_path, cls)  # type: ignore[arg-type]
                if action.get("action") == "header_added":
                    counts[cls] += 1
                else:
                    counts["skipped"] += 1
        elif cls == "D":
            if args.dry_run:
                if not src_path.exists():
                    action = {"action": "would_skip", "reason": "source_missing"}
                    counts["skipped"] += 1
                else:
                    action = {"action": "would_archive",
                              "dest": str(ARCHIVE_DIR.relative_to(PROJECT_ROOT) / src_path.name)}
                    counts["D"] += 1
            else:
                action = _archive_file(src_path)
                if action.get("action") == "archived":
                    counts["D"] += 1
                else:
                    counts["skipped"] += 1
        else:
            action = {"action": "skip", "reason": f"unknown_class:{cls}"}
            counts["skipped"] += 1

        manifest_rows.append({
            "file": entry.file,
            "class": cls,
            "rationale": entry.rationale,
            **action,
        })

    summary = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "mode": "dry-run" if args.dry_run else "apply",
        "counts": counts,
        "rows": manifest_rows,
    }

    if args.apply:
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        MANIFEST_PATH.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote manifest to {MANIFEST_PATH}")

    print(json.dumps(counts, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
