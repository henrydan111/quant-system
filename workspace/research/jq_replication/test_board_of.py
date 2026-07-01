"""Unit test for jq_rep_utils.board_of / is_mainboard board classification.

Pure function, no data dependencies — runnable standalone
(`venv/Scripts/python.exe test_board_of.py`) or under pytest.

Regression focus (surfaced 2026-06-22, 果仁 sm_纯市值01 parity reproduction):
the post-2024 reassigned 北证 listings in the 920xxx range start with "9" but are
NOT B-shares; the old `c[0] == "9" -> bshare` rule misclassified them, leaking
920xxx 北证 names into "沪深主板+创业板" universes. They must classify as "bse".
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jq_rep_utils import board_of, is_mainboard  # noqa: E402

# (qlib code form, expected board). Codes carry the qlib underscore suffix where it
# is load-bearing for the classification (the _BJ catch-all); prefix-only otherwise.
CASES = [
    # --- the bug fix: 920xxx 北证 reassigned codes are BSE, never B-share ---
    ("920145_BJ", "bse"),
    ("920000_BJ", "bse"),
    ("920145", "bse"),          # prefix alone is sufficient (no suffix)
    # --- true B-shares stay B-shares (900 沪 / 200,201 深) ---
    ("900001_SH", "bshare"),
    ("900957", "bshare"),
    ("200011_SZ", "bshare"),
    ("201872", "bshare"),
    # --- other 北交所 / 老三板 prefixes ---
    ("830799_BJ", "bse"),
    ("870508_BJ", "bse"),
    ("430047_BJ", "bse"),
    ("831010", "bse"),
    # --- _BJ suffix is the robust catch-all even if the numeric prefix is novel ---
    ("839999_BJ", "bse"),
    # --- mainboard (incl. former 中小板 002/003) ---
    ("600000_SH", "main"),
    ("601398_SH", "main"),
    ("603259_SH", "main"),
    ("605499_SH", "main"),
    ("000001_SZ", "main"),
    ("001872_SZ", "main"),
    ("002594_SZ", "main"),
    ("003816_SZ", "main"),
    # --- 创业板 / 科创板. 302xxx is the post-2024 ChiNext range expansion (real:
    #     302132_SZ 中航成飞); board_of matches the whole 30xxxx block so it can't
    #     stale-leak a ChiNext name to "other" the way the old 300/301 list did. ---
    ("300750_SZ", "chinext"),
    ("301029_SZ", "chinext"),
    ("302132_SZ", "chinext"),
    ("688981_SH", "star"),
    ("689009_SH", "star"),
    # --- index codes that ride along in the qlib universe stay "other" (not a board) ---
    ("399001_SZ", "other"),
    ("399006_SZ", "other"),
]


def test_board_of_classification():
    for code, expected in CASES:
        got = board_of(code)
        assert got == expected, f"board_of({code!r}) = {got!r}, expected {expected!r}"


def test_920xxx_is_not_bshare():
    # the precise regression: the old `c[0]=='9'` rule returned 'bshare' here.
    assert board_of("920145_BJ") == "bse"
    assert board_of("920145_BJ") != "bshare"


def test_is_mainboard():
    # 北证 920xxx must NOT count as mainboard (the universe-leak this fix prevents),
    # nor do B-shares / chinext / star; real mainboard codes do.
    assert is_mainboard("600000_SH") is True
    assert is_mainboard("000001_SZ") is True
    assert is_mainboard("920145_BJ") is False
    assert is_mainboard("900001_SH") is False
    assert is_mainboard("300750_SZ") is False


def _run():
    failures = 0
    for code, expected in CASES:
        got = board_of(code)
        ok = got == expected
        failures += not ok
        print(f"  {'OK ' if ok else 'FAIL'}  board_of({code:<12}) = {got:<8} (expected {expected})")
    for fn in (test_920xxx_is_not_bshare, test_is_mainboard):
        try:
            fn()
            print(f"  OK   {fn.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"  FAIL {fn.__name__}: {e}")
    print("ALL PASS" if failures == 0 else f"{failures} FAILURE(S)")
    return failures


if __name__ == "__main__":
    sys.exit(1 if _run() else 0)
