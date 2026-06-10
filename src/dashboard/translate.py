"""Read the Sonnet-generated bilingual description cache.

`translations.json` is produced by a Claude Sonnet pass over the factor /
category / strategy / research-thread inventory (see `tools/run_translation.md`
and the generator). The dashboard build only READS it here — fast, offline, no
API key. Missing keys degrade to an empty string (the UI shows the raw id),
so a not-yet-translated new factor never breaks the build.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from .util import read_json, PROJECT_ROOT

CACHE = PROJECT_ROOT / "src" / "dashboard" / "translations.json"


@lru_cache(maxsize=1)
def _load() -> dict[str, Any]:
    d = read_json(CACHE)
    return d if isinstance(d, dict) else {}


def _pair(section: str, key: str) -> tuple[str, str]:
    rec = (_load().get(section) or {}).get(key) or {}
    return rec.get("en", "") or "", rec.get("cn", "") or ""


def factor_desc(fid: str) -> tuple[str, str]:
    return _pair("factors", fid)


def category_label(cat: str) -> tuple[str, str]:
    en, cn = _pair("categories", cat)
    return (en or cat, cn)


def strategy_desc(name: str) -> tuple[str, str]:
    return _pair("strategies", name)


def thread_desc(name: str) -> tuple[str, str]:
    return _pair("research_threads", name)


def dim_label(key: str) -> tuple[str, str]:
    """arXiv-framework research-dimension label (en, cn). Sonnet-translated."""
    return _pair("knowledge_dims", key)


def direction_desc(did: str) -> tuple[str, str]:
    """Curated research-direction one-liner (en, cn). Sonnet-translated."""
    return _pair("knowledge_directions", did)


def paper_gloss(aid: str) -> str:
    """One-line Chinese gloss of a ranked arXiv paper (cn only; title stays EN)."""
    return ((_load().get("knowledge_papers") or {}).get(aid) or {}).get("cn", "") or ""


def coverage() -> dict[str, int]:
    d = _load()
    return {k: len(v) for k, v in d.items() if isinstance(v, dict) and k != "_meta"}


def is_present() -> bool:
    return bool(_load().get("factors"))
