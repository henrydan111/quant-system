# Alpha Research (`src/alpha_research/`)

The Alpha Research module is the library layer for factor engineering, evaluation, model training, and experiment tracking. Active experiments still belong in `workspace/research/`, but the reusable machinery lives here.

## Architecture

```text
alpha_research/
|-- factor_library/
|   |-- __init__.py          # Public API: catalog + compute helpers
|   |-- catalog.py           # 177-factor catalog (153 base + 4 industry-rel + 20 Layer-2) and composite definitions
|   |-- operators.py         # Qlib expression operators + pandas transforms
|   `-- qlib_expr_guide.md   # Expression syntax rules and known pitfalls
|-- factor_eval/             # IC, quantile, neutralization, decay, correlation
|-- model_zoo/               # LightGBM, XGBoost, and future model wrappers
`-- mlflow_tracker.py        # ExperimentTracker
```

## Factor Library

Phase 3 introduced a two-layer factor framework.

- **Layer 1: Qlib expressions**
  - Build time-series factors as expression strings in `operators.py`.
  - Evaluate them in bulk through a single `D.features()` call via `compute_factors()`.
  - This is the preferred path for market-wide batch screening because Qlib deduplicates shared sub-expressions efficiently.
- **Layer 2: pandas transforms**
  - Use cross-sectional ranking, z-scoring, neutralization, and composite construction when the logic is inherently cross-sectional.
  - `add_composites()` applies the default composite definitions after Layer 1 factors are computed.

### Public API

From `src.alpha_research.factor_library`:

- `get_factor_catalog(include_new_data=False)`
- `get_composite_defs()`
- `get_category_map()`
- `compute_factors(catalog, start_date, end_date, horizons=None, qlib_dir=None)`
- `add_composites(factors_df, composite_defs=None)`

## Phase 3 Conventions

- Prefer the shared operator library and catalog over bespoke factor notebooks that rebuild the same formulas.
- Use adjusted prices for cross-day return and momentum-style computations when the factor definition requires corporate-action-aware price history.
- Use raw PIT values for accounting ratios and other reported quantities that should not be adjusted.
- Prevent same-day leakage with lagged expressions such as `Ref(..., 1)` where the factor is meant for next-day trading.
- Work around the Qlib unary-negation parser bug with `0 - Operator(...)` instead of `-Operator(...)`.

## Factor Evaluation Toolkit

`factor_eval/` contains reusable analysis helpers for:

- IC / RankIC / ICIR
- quantile and long-short analysis
- neutralization
- decay analysis
- correlation and redundancy screening
- factor-specific plotting

The toolkit auto-normalizes MultiIndex order internally, but raw pandas code still needs to remember that Qlib returns `(instrument, datetime)`.

## Model Training and Logging

- `model_zoo/` contains reusable model wrappers for cross-sectional prediction.
- `mlflow_tracker.py` provides `ExperimentTracker` for logging parameters, metrics, and artifacts.
- Substantive experiments should use MLflow so research decisions remain reproducible.

## Relationships

```text
data_infra (Qlib backend)
    -> factor_library
    -> factor_eval
    -> model_zoo
    -> backtest_engine
    -> result_analysis
```

## Usage Notes

- Prefer the Phase 3 catalog workflow for batch screens and production-style research.
- Batch factor screening now uses the validated internal engine in `factor_eval/batch_screening.py` by default; keep `reference` only for regression/debug runs and use the parity harness in `workspace/scripts/validate_factor_screening_parity.py` when semantics need to be rechecked.
- Keep ad-hoc notebooks in `workspace/research/`.
- Add new standardized metrics to `src/result_analysis/`, not to research notebooks.
