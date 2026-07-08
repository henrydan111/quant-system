"""B7/B2 (C8): hand-rolled Tushare→Qlib code conversion is BANNED on the MVP
surface — the ONLY sanctioned door is
``provider_metadata.tushare_to_qlib_canonical`` (upper form).

Scope = the AI-layer / 金股 MVP files under review (legacy scripts under
workspace/scripts/archive and pre-existing modules keep their history; new
work must go through the canonical converter).
"""
from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

#: hand-rolled conversion patterns (either quote style, optional .upper())
_HANDROLLED = re.compile(r"""\.replace\(\s*['"]\.['"]\s*,\s*['"]_['"]\s*\)""")

#: the MVP review surface (files + directories); the sanctioned implementation
#: itself is excluded.
SURFACE = [
    "src/ai_layer",
    "src/data_infra/golden_stock_universe.py",
    "src/data_infra/text_store.py",
    "src/data_infra/fetchers",
    "src/portfolio_risk/rank_book_construction.py",
    "workspace/research/mvp_pool_book",
    "workspace/research/phase0_golden_pool",
    "workspace/scripts/text_daily_pull.py",
    "workspace/scripts/fetch_text_mvp.py",
]
SANCTIONED = {PROJECT_ROOT / "src" / "data_infra" / "provider_metadata.py"}


def _surface_files():
    for entry in SURFACE:
        p = PROJECT_ROOT / entry
        if p.is_file():
            yield p
        elif p.is_dir():
            yield from p.rglob("*.py")


def test_no_handrolled_conversion_on_mvp_surface():
    offenders = []
    for path in _surface_files():
        if path in SANCTIONED:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), start=1):
            if _HANDROLLED.search(line):
                offenders.append(f"{path.relative_to(PROJECT_ROOT)}:{i}: {line.strip()}")
    assert not offenders, (
        "hand-rolled Tushare→Qlib conversion (C8 breach) — use "
        "provider_metadata.tushare_to_qlib_canonical:\n" + "\n".join(offenders)
    )


def test_surface_entries_exist_or_are_known_optional():
    # guard against the lint silently scanning nothing after a rename
    required = [
        "src/ai_layer",
        "src/data_infra/golden_stock_universe.py",
        "src/data_infra/text_store.py",
        "workspace/research/mvp_pool_book",
    ]
    missing = [e for e in required if not (PROJECT_ROOT / e).exists()]
    assert not missing, f"C8 lint surface entries vanished (rename?): {missing}"
