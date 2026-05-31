"""Status-aware factor selection over the formal factor registry (Phase 3).

``get_factors`` / ``get_factor_selection`` are **SANDBOX / DISCOVERY convenience
readers** that select factors from the formal registry by lifecycle status. They are
explicitly **NOT** the formal gate: formal validation resolves through the registry
**resolver allow-set** (P1.2, ``handle_validation_object_resolver``) plus the
**definition-binding gate** (P1.3, ``_assert_no_definition_drift``). To make misuse
loud, both readers REQUIRE an explicit ``stage`` and refuse the formal stages at
runtime; an AST-usage architecture test additionally forbids formal-path modules from
referencing these names.

Design contract (factor_lifecycle_phase3_spec.md, review-confirmed):
  * Registry supplies the status FILTER; the code catalog supplies the COMPUTABLE
    expression (``get_factor_catalog`` for base; ``get_composite_defs`` /
    ``get_industry_relative_defs`` for the two-stage composite compute). Registry
    pseudo-expressions (``COMPOSITE(...)``) are NEVER returned for computation.
  * ``get_factors`` returns BASE expressions only -- a compute-ready drop-in for
    ``compute_factors``. ``get_factor_selection`` returns a richer ``FactorSelection``
    that also carries the selected composites' / industry-relative defs + per-factor
    records, and -- for compute-readiness -- auto-includes the base DEPENDENCIES of any
    selected composite (tagged ``selection_role='dependency'`` so they can never be
    confused with a status-matched selection).
  * Reads never mutate: an empty registry RAISES ``RegistryNotSyncedError`` (it must
    not masquerade as a valid empty filter); a true no-match returns ``{}``.
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from .catalog import (
    get_composite_defs,
    get_factor_catalog,
    get_industry_relative_defs,
)

LOGGER = logging.getLogger(__name__)

# These two tuples PARTITION ``field_registry._STAGES``. Sandbox stages are the only
# ones the convenience readers accept; the formal stages are refused at runtime.
SANDBOX_STAGES: tuple[str, ...] = ("sandbox_screening", "vectorized_screening")
FORMAL_STAGES: tuple[str, ...] = ("formal_validation", "oos_test", "registry_publish")

VALID_SELECTION_STATUSES: tuple[str, ...] = ("draft", "candidate", "approved", "deprecated")
VALID_ON_DRIFT: tuple[str, ...] = ("skip", "code_warn", "raise")

# long_only_viable_provisional ordering for ``prioritize`` (best first).
_VIABILITY_ORDER = {"viable": 0, "review_only": 1, "non_viable": 2}
_PRIORITIZE_KEYS = ("latest_oos_rank_icir", "long_only_viable_provisional", "signal_role_suggested")


class FormalStageNotAllowedError(RuntimeError):
    """A sandbox-only reader was called with a formal ``stage``. Formal factor
    resolution must go through the resolver allow-set (P1.2) + definition-binding
    (P1.3), never ``get_factors`` / ``get_factor_selection``."""


class RegistryNotSyncedError(RuntimeError):
    """The factor registry has no current rows -- run ``sync_catalog_to_registry()``
    first. Returning an empty dict would let an unsynced registry masquerade as a
    legitimate empty filter result."""


class FactorSelectionDriftError(RuntimeError):
    """A selected factor's registry ``definition_hash`` differs from the current code
    catalog hash and ``on_drift='raise'`` was requested."""


@dataclass(frozen=True)
class FactorRecord:
    """One row of a :class:`FactorSelection`. ``selected`` / ``selection_role`` /
    ``dependency_included`` make a dependency-only base (pulled in to make a selected
    composite computable) impossible to confuse with a status-matched selection."""

    factor_id: str
    kind: str  # base / composite / industry_relative
    status: str
    approval_validity: str
    signal_role: str
    signal_role_suggested: str
    long_only_viable_provisional: str
    latest_oos_rank_icir: float | None
    definition_hash: str
    drift_state: str  # in_sync / drifted / absent_from_code
    selected: bool
    selection_role: str  # "selected" | "dependency"
    dependency_included: bool


@dataclass(frozen=True)
class FactorSelection:
    """Status-aware factor selection. ``base_expressions`` is compute-ready (selected
    base factors PLUS the base dependencies of selected composites); ``composite_defs``
    / ``industry_relative_defs`` are the code defs filtered to selected names (fed to
    ``add_composites`` / ``add_industry_relative_composites``); ``records`` carries the
    per-factor metadata + the dependency tagging."""

    base_expressions: "OrderedDict[str, str]"
    composite_defs: list = field(default_factory=list)
    industry_relative_defs: list = field(default_factory=list)
    records: list = field(default_factory=list)

    def get_factor_records(self) -> list:
        return list(self.records)


def _default_registry_dir() -> Path:
    # selection.py -> parents[3] is the project root (mirrors factor_registry_cli.py).
    return Path(__file__).resolve().parents[3] / "data" / "factor_registry"


def _coerce_status_set(status_in: Iterable[str]) -> set[str]:
    if isinstance(status_in, str):
        # A bare string is almost always a mistake ("approved" would become a char set).
        raise ValueError("status_in must be an explicit iterable of statuses, not a bare string")
    statuses = {str(s).strip().lower() for s in status_in if str(s).strip()}
    if not statuses:
        raise ValueError("status_in is required and must be a non-empty set of statuses")
    bad = statuses - set(VALID_SELECTION_STATUSES)
    if bad:
        raise ValueError(f"Unknown status(es) in status_in: {sorted(bad)}; allowed {VALID_SELECTION_STATUSES}")
    return statuses


def _drift_state(factor_id: str, registry_hash: str, code_hashes: dict[str, str]) -> str:
    code_hash = code_hashes.get(factor_id)
    if code_hash is None:
        return "absent_from_code"
    if not registry_hash or registry_hash != code_hash:
        return "drifted"
    return "in_sync"


def _opt_float(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _row_str(row: pd.Series, column: str) -> str:
    value = row.get(column)
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value)


def _prioritized(rows: pd.DataFrame, prioritize: str | None) -> pd.DataFrame:
    """Order selected rows for stable, useful insertion order. ``None`` preserves the
    registry's current-row order; the two metric keys sort best-first."""
    if prioritize is None:
        return rows
    if prioritize not in _PRIORITIZE_KEYS:
        raise ValueError(f"Unknown prioritize={prioritize!r}; allowed {_PRIORITIZE_KEYS} or None")
    if prioritize == "latest_oos_rank_icir":
        key = rows[prioritize].map(_opt_float)
        return rows.assign(_k=key.fillna(float("-inf"))).sort_values("_k", ascending=False, kind="stable").drop(columns="_k")
    if prioritize == "long_only_viable_provisional":
        key = rows[prioritize].map(lambda v: _VIABILITY_ORDER.get(str(v), 99))
        return rows.assign(_k=key).sort_values("_k", ascending=True, kind="stable").drop(columns="_k")
    # signal_role_suggested: group by role, stable within
    key = rows[prioritize].map(lambda v: str(v))
    return rows.assign(_k=key).sort_values("_k", ascending=True, kind="stable").drop(columns="_k")


def _make_record(row: pd.Series, *, drift_state: str, selected: bool, selection_role: str) -> FactorRecord:
    return FactorRecord(
        factor_id=_row_str(row, "factor_id"),
        kind=_row_str(row, "factor_kind"),
        status=_row_str(row, "status"),
        approval_validity=_row_str(row, "approval_validity"),
        signal_role=_row_str(row, "signal_role"),
        signal_role_suggested=_row_str(row, "signal_role_suggested"),
        long_only_viable_provisional=_row_str(row, "long_only_viable_provisional"),
        latest_oos_rank_icir=_opt_float(row.get("latest_oos_rank_icir")),
        definition_hash=_row_str(row, "definition_hash"),
        drift_state=drift_state,
        selected=selected,
        selection_role=selection_role,
        dependency_included=(selection_role == "dependency"),
    )


def get_factor_selection(
    *,
    stage: str,
    status_in: Iterable[str],
    prioritize: str | None = None,
    include_new_data: bool = False,
    registry_dir: str | Path | None = None,
    on_drift: str = "skip",
) -> FactorSelection:
    """Status-aware SANDBOX/DISCOVERY factor selection over the formal registry.

    See module docstring for the full contract. Returns a :class:`FactorSelection`
    (compute-ready ``base_expressions`` + selected composite/industry-relative defs +
    per-factor ``records``).

    Args:
        stage: REQUIRED; must be in :data:`SANDBOX_STAGES`. A formal stage raises
            :class:`FormalStageNotAllowedError`.
        status_in: REQUIRED explicit iterable of lifecycle statuses (no default).
        prioritize: optional ordering key (one of :data:`_PRIORITIZE_KEYS`) or ``None``.
        include_new_data: passed to ``get_factor_catalog`` (the definition source).
        registry_dir: registry root (default ``data/factor_registry``).
        on_drift: ``"skip"`` (default) | ``"code_warn"`` | ``"raise"`` -- how to treat a
            SELECTED factor whose registry ``definition_hash`` differs from the current
            code hash. Dependency-only bases are always included with the code
            expression (compute-readiness) and carry their own ``drift_state``.

    Raises:
        FormalStageNotAllowedError, RegistryNotSyncedError, FactorSelectionDriftError,
        ValueError.
    """
    if stage not in SANDBOX_STAGES:
        raise FormalStageNotAllowedError(
            f"get_factor_selection is sandbox-only; stage={stage!r} not in {SANDBOX_STAGES}. "
            f"Formal validation must resolve through the resolver allow-set (P1.2) + "
            f"definition-binding (P1.3), not this convenience reader."
        )
    statuses = _coerce_status_set(status_in)
    if on_drift not in VALID_ON_DRIFT:
        raise ValueError(f"Unknown on_drift={on_drift!r}; allowed {VALID_ON_DRIFT}")

    from src.alpha_research.factor_registry import FactorRegistryStore  # lazy: avoid catalog<->registry cycle

    root = Path(registry_dir) if registry_dir is not None else _default_registry_dir()
    store = FactorRegistryStore(root)
    master = store.factor_master
    current = master[master["is_current"].fillna(False)] if not master.empty else master
    if current.empty:
        raise RegistryNotSyncedError(
            f"factor registry at {root} has no current rows -- run sync_catalog_to_registry() first "
            f"(an empty registry must not masquerade as a valid empty filter)"
        )

    base_catalog = get_factor_catalog(include_new_data=include_new_data)
    composite_defs_all = {str(d["name"]): d for d in get_composite_defs()}
    industry_defs_all = {str(d["name"]): d for d in get_industry_relative_defs()}
    code_hashes = store.current_catalog_definition_hashes()

    base_expressions: "OrderedDict[str, str]" = OrderedDict()
    composite_defs: list = []
    industry_relative_defs: list = []
    records: list = []
    selected_base_ids: set[str] = set()
    pending_deps: "OrderedDict[str, str]" = OrderedDict()  # dep_factor_id -> needed_by

    selected_rows = _prioritized(current[current["status"].isin(statuses)].copy(), prioritize)

    def _handle_selected_drift(factor_id: str, kind: str, drift: str) -> bool:
        """Return True to KEEP the selected factor, False to skip it (on_drift policy)."""
        if drift not in ("drifted", "absent_from_code"):
            return True
        if on_drift == "raise":
            raise FactorSelectionDriftError(
                f"{kind} {factor_id!r} drift_state={drift}: registry definition_hash != current code hash "
                f"(on_drift='raise')"
            )
        if on_drift == "skip":
            LOGGER.warning("get_factor_selection: skipping %s %s (drift_state=%s, on_drift=skip)", kind, factor_id, drift)
            return False
        LOGGER.warning("get_factor_selection: %s %s drift_state=%s -- using code definition (on_drift=code_warn)", kind, factor_id, drift)
        return True

    for _, row in selected_rows.iterrows():
        factor_id = _row_str(row, "factor_id")
        kind = _row_str(row, "factor_kind")
        reg_hash = _row_str(row, "definition_hash")
        drift = _drift_state(factor_id, reg_hash, code_hashes)

        if kind == "base":
            if not _handle_selected_drift(factor_id, kind, drift):
                continue
            if factor_id not in base_catalog:
                LOGGER.warning(
                    "get_factor_selection: base %s is a current registry row but absent from the code catalog "
                    "(include_new_data=%s) -- dropped (cannot compute)", factor_id, include_new_data,
                )
                continue
            base_expressions[factor_id] = base_catalog[factor_id]
            selected_base_ids.add(factor_id)
            records.append(_make_record(row, drift_state=drift, selected=True, selection_role="selected"))
        elif kind == "composite":
            cdef = composite_defs_all.get(factor_id)
            if cdef is None:
                LOGGER.warning("get_factor_selection: composite %s absent from code composite defs -- dropped", factor_id)
                continue
            if not _handle_selected_drift(factor_id, kind, drift):
                continue
            composite_defs.append(cdef)
            records.append(_make_record(row, drift_state=drift, selected=True, selection_role="selected"))
            for dep in cdef.get("components", []):
                pending_deps.setdefault(str(dep), factor_id)
        elif kind == "industry_relative":
            idef = industry_defs_all.get(factor_id)
            if idef is None:
                LOGGER.warning("get_factor_selection: industry-relative %s absent from code defs -- dropped", factor_id)
                continue
            if not _handle_selected_drift(factor_id, kind, drift):
                continue
            industry_relative_defs.append(idef)
            records.append(_make_record(row, drift_state=drift, selected=True, selection_role="selected"))
            pending_deps.setdefault(str(idef["base"]), factor_id)
        else:
            LOGGER.warning("get_factor_selection: unknown factor_kind=%r for %s -- dropped", kind, factor_id)

    # Pass 2: base DEPENDENCIES of selected composites/industry-relative factors, for
    # compute-readiness. Included with the CODE expression regardless of their own
    # status/drift, but tagged selection_role="dependency" so they are never mistaken
    # for a status-matched selection.
    for dep_id, needed_by in pending_deps.items():
        if dep_id in selected_base_ids or dep_id in base_expressions:
            continue
        if dep_id not in base_catalog:
            LOGGER.warning(
                "get_factor_selection: dependency base %s (needed by %s) absent from the code catalog "
                "(include_new_data=%s) -- %s may not compute", dep_id, needed_by, include_new_data, needed_by,
            )
            continue
        base_expressions[dep_id] = base_catalog[dep_id]
        dep_rows = current[current["factor_id"] == dep_id]
        if not dep_rows.empty:
            dep_row = dep_rows.iloc[0]
            drift = _drift_state(dep_id, _row_str(dep_row, "definition_hash"), code_hashes)
            records.append(_make_record(dep_row, drift_state=drift, selected=False, selection_role="dependency"))
        else:
            records.append(FactorRecord(
                factor_id=dep_id, kind="base", status="", approval_validity="",
                signal_role="", signal_role_suggested="", long_only_viable_provisional="",
                latest_oos_rank_icir=None, definition_hash="", drift_state="absent_from_registry",
                selected=False, selection_role="dependency", dependency_included=True,
            ))

    return FactorSelection(
        base_expressions=base_expressions,
        composite_defs=composite_defs,
        industry_relative_defs=industry_relative_defs,
        records=records,
    )


def get_factors(
    *,
    stage: str,
    status_in: Iterable[str],
    prioritize: str | None = None,
    include_new_data: bool = False,
    registry_dir: str | Path | None = None,
    on_drift: str = "skip",
) -> "OrderedDict[str, str]":
    """Status-aware SANDBOX/DISCOVERY reader returning BASE expressions only -- a
    compute-ready ``OrderedDict{factor_id: qlib_expression}`` drop-in for
    ``compute_factors``. Composites / industry-relative + metadata come from
    :func:`get_factor_selection`.

    This is the STRICT base-status filter: a base pulled in only as a dependency of a
    selected composite (``selection_role='dependency'``) is EXCLUDED here, so the plain
    API never surprises a caller with an off-status factor. NOT a formal gate -- sandbox
    stages only (see module docstring; P1.2/P1.3 own the formal path).
    """
    selection = get_factor_selection(
        stage=stage,
        status_in=status_in,
        prioritize=prioritize,
        include_new_data=include_new_data,
        registry_dir=registry_dir,
        on_drift=on_drift,
    )
    selected_base = {r.factor_id for r in selection.records if r.kind == "base" and r.selected}
    return OrderedDict(
        (fid, expr) for fid, expr in selection.base_expressions.items() if fid in selected_base
    )


def sync_catalog_to_registry(
    *,
    registry_dir: str | Path | None = None,
    record_run: bool = True,
    dry_run: bool = False,
) -> dict:
    """Staged catalog->registry cutover entry (Phase 3 P3.2).

    Thin wrapper over ``FactorRegistryStore.sync_catalog`` plus a PARITY diff so a
    cutover operator sees exactly what changed. NEVER auto-run inside a read
    (``get_factors`` stays a pure read); NEVER writes ``approved`` (the Phase-1 writer
    gate stands -- sync only ever creates ``draft`` rows / new versions).

    Args:
        registry_dir: registry root (default ``data/factor_registry``).
        record_run: pass-through to ``sync_catalog`` (records a catalog_sync run row).
        dry_run: if True, compute + return the parity diff WITHOUT writing anything.

    Returns dict: ``{dry_run, synced, new_drafts, new_versions, catalog_only,
    registry_only, parity_ok}``. ``new_drafts`` / ``new_versions`` are the PRE-sync diff
    the sync applies (on a dry run, the would-be changes); ``catalog_only`` /
    ``registry_only`` are the POST-sync residual (both empty when in parity).
    """
    from src.alpha_research.factor_registry import FactorRegistryStore  # lazy: avoid cycle

    root = Path(registry_dir) if registry_dir is not None else _default_registry_dir()
    store = FactorRegistryStore(root)

    def _parity() -> tuple[list[str], list[str], list[str]]:
        code_hashes = store.current_catalog_definition_hashes()
        master = store.factor_master
        current = master[master["is_current"].fillna(False)] if not master.empty else master
        reg = (
            {}
            if current.empty
            else {str(f): str(h) for f, h in zip(current["factor_id"], current["definition_hash"])}
        )
        code_ids, reg_ids = set(code_hashes), set(reg)
        catalog_only = sorted(code_ids - reg_ids)
        registry_only = sorted(reg_ids - code_ids)
        drifted = sorted(fid for fid in (code_ids & reg_ids) if reg.get(fid) != code_hashes.get(fid))
        return catalog_only, registry_only, drifted

    pre_catalog_only, pre_registry_only, pre_drifted = _parity()
    if dry_run:
        return {
            "dry_run": True,
            "synced": 0,
            "new_drafts": pre_catalog_only,
            "new_versions": pre_drifted,
            "catalog_only": pre_catalog_only,
            "registry_only": pre_registry_only,
            "parity_ok": not pre_catalog_only and not pre_drifted,
        }

    result = store.sync_catalog(record_run=record_run)
    store.save()
    post_catalog_only, post_registry_only, post_drifted = _parity()
    return {
        "dry_run": False,
        "synced": int(result.get("current_factor_count", 0)),
        "new_drafts": pre_catalog_only,
        "new_versions": pre_drifted,
        "catalog_only": post_catalog_only,
        "registry_only": post_registry_only,
        "parity_ok": not post_catalog_only and not post_drifted,
    }
