"""
Factor Library (因子库)

Two-layer factor computation system for A-share multi-factor research.

Layer 1 — Qlib Expression Operators (C speed):
    Functions returning Qlib expression strings, computed via D.features().

Layer 2 — DataFrame Operators (vectorized pandas):
    Cross-sectional ranking, z-scoring, composites, neutralization.

Quick Start:
    >>> from src.alpha_research.factor_library import (
    ...     get_factor_catalog, compute_factors, add_composites
    ... )
    >>> catalog = get_factor_catalog()
    >>> factors_df, fwd_df = compute_factors(catalog, '2012-01-01', '2025-12-31')
    >>> factors_df = add_composites(factors_df)
"""

from .catalog import (
    get_factor_catalog,
    get_composite_defs,
    get_category_map,
    get_industry_relative_defs,
)
from .hypothesis_factors import (
    HYPOTHESIS_FACTOR_SCHEMA,
    HypothesisFactorSpec,
    compute_spec_hash,
    list_hypothesis_factors,
    load_hypothesis_factor,
)
from .operators import (
    compute_factors,
    add_composites,
    add_industry_relative_composites,
    cs_rank,
    cs_zscore,
    cs_demean,
    composite,
    neutralize,
    winsorize,
)
from .selection import (
    get_factors,
    get_factor_selection,
    sync_catalog_to_registry,
    FactorSelection,
    FactorRecord,
    SANDBOX_STAGES,
    FORMAL_STAGES,
    FormalStageNotAllowedError,
    RegistryNotSyncedError,
    FactorSelectionDriftError,
)

__all__ = [
    # Catalog
    'get_factor_catalog',
    'get_composite_defs',
    'get_category_map',
    'get_industry_relative_defs',
    'HypothesisFactorSpec',
    'HYPOTHESIS_FACTOR_SCHEMA',
    'compute_spec_hash',
    'load_hypothesis_factor',
    'list_hypothesis_factors',
    # Phase 3 — status-aware selection over the formal registry (sandbox-only)
    'get_factors',
    'get_factor_selection',
    'sync_catalog_to_registry',
    'FactorSelection',
    'FactorRecord',
    'SANDBOX_STAGES',
    'FORMAL_STAGES',
    'FormalStageNotAllowedError',
    'RegistryNotSyncedError',
    'FactorSelectionDriftError',
    # Computation
    'compute_factors',
    'add_composites',
    'add_industry_relative_composites',
    # Layer 2 operators
    'cs_rank',
    'cs_zscore',
    'cs_demean',
    'composite',
    'neutralize',
    'winsorize',
]
