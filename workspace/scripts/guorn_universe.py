"""Shared 果仁-book universe membership via the CANONICAL board_of() classifier.

Replaces the drift-prone hard-coded prefix tuples (MAIN_PREFIXES / SHUANGCHUANG / …) the guorn_verify_* /
guorn_parity_rung* harnesses used to carry. board_of() (workspace/research/jq_replication/jq_rep_utils.py)
catches the WHOLE 30xxxx ChiNext block — incl. 302xxx names the 300/301 prefix snapshot silently missed
(e.g. 302132_SZ) — and handles STAR (688/689) and 北证/BSE (.BJ/920/4x/8x) robustly. 果仁 `全部股票` excludes
北证/BSE and B-shares, which board_of's bucketing gives for free.

board_of(code) returns one of: 'main' / 'chinext' / 'star' / 'bse' / 'bshare' / 'other'.

NON-FORMAL parity tooling.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "workspace" / "research" / "jq_replication"))
from jq_rep_utils import board_of  # noqa: E402  (the single canonical board classifier)

EXCL_STAR = ("main", "chinext")             # 果仁 排除科创板: 沪深主板+中小板+创业板 (excl 北证/BSE/B-share)
INCL_STAR = ("main", "chinext", "star")     # 果仁 包含科创板: + 科创板
SHUANGCHUANG = ("chinext", "star")          # 双创 = 创业板 + 科创板


def in_guorn_universe(code: str, *, include_star: bool = False, boards=None) -> bool:
    """True if `code` (qlib form, e.g. 000001_SZ) is in the 果仁 candidate universe.

    Default = 果仁 排除科创板 (main+中小板+创业板; 北证/BSE/B-share always excluded — 果仁's 全部股票 excludes them).
    `include_star=True` adds 科创板 (果仁 包含科创板). Pass an explicit `boards` tuple of board_of labels to
    override, e.g. `boards=("chinext","star")` for the 双创 universe.
    """
    if boards is not None:
        return board_of(code) in boards
    return board_of(code) in (INCL_STAR if include_star else EXCL_STAR)
