"""Parse data/data_dictionary.md into structured, bilingual per-dataset column
tables. The dictionary is already authored as ``| Column | English | Chinese |``
tables under ``### dataset_id (中文名)`` headings, grouped by ``## N. Category``
sections — so the data layer's CN/EN requirement needs no translation, only
parsing.
"""
from __future__ import annotations

import re
from typing import Any

from .util import PROJECT_ROOT, read_text

_SECTION = re.compile(r"^##\s+\d+\.\s*(.+?)\s*$")
# "### stock_basic (股票基础信息)"  /  "### income_quarterly (单季利润表)"
_DATASET = re.compile(r"^###\s+([A-Za-z0-9_]+)\s*(?:/\s*[A-Za-z0-9_]+\s*)?\((.+?)\)\s*$")
_TOTAL = re.compile(r"Total Columns:\s*(\d+)")
_ROW = re.compile(r"^\|\s*`?([^|`]+?)`?\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*$")


def parse_data_dictionary() -> dict[str, dict[str, Any]]:
    """Return {dataset_id: {cn_name, category, columns:[{col,en,cn}], note}}.

    Robust to multiple tables under one dataset (columns are accumulated) and to
    headings without a column table (columns stays empty)."""
    out: dict[str, dict[str, Any]] = {}
    txt = read_text(PROJECT_ROOT / "data" / "data_dictionary.md")
    if not txt:
        return out

    section = ""
    cur: dict[str, Any] | None = None
    in_table = False
    for raw in txt.splitlines():
        line = raw.rstrip()
        sm = _SECTION.match(line)
        if sm:
            section = sm.group(1)
            continue
        dm = _DATASET.match(line)
        if dm:
            did, cn = dm.group(1), dm.group(2).strip()
            cur = out.setdefault(did, {"cn_name": cn, "category": section, "columns": [], "note": ""})
            cur["cn_name"] = cur["cn_name"] or cn
            cur["category"] = cur["category"] or section
            in_table = False
            continue
        if cur is None:
            continue
        # column table rows
        rm = _ROW.match(line)
        if rm:
            c1, c2, c3 = (x.strip() for x in rm.groups())
            low = c1.lower()
            if low in ("column", "字段") or set(c1) <= {"-", " ", ":"}:  # header / separator
                in_table = True
                continue
            if c1 and (c2 or c3):
                cur["columns"].append({"col": c1, "en": c2, "cn": c3})
            in_table = True
            continue
        else:
            in_table = False
    return out
