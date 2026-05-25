# Alpha Research Rules

These rules apply to everything under `src/alpha_research/`.

## 1. Point-in-Time Integrity

- All features and labels must remain point-in-time correct.
- Fundamental data must align on `ann_date`, not `end_date`.
- Predictive expressions must use lagging where required; in Qlib expressions prefer `Ref(..., 1)` rather than same-day references when the signal is intended for next-day trading.
- Preserve survivorship-bias-free inputs. Do not restrict research universes to currently listed names only.

## 2. Phase 3 Factor Framework

- Prefer the two-layer factor system already in the repo:
  - Layer 1: Qlib expression operators in `factor_library/operators.py`
  - Layer 2: pandas cross-sectional transforms and composites
- Use `get_factor_catalog()`, `compute_factors()`, and `add_composites()` instead of rebuilding large ad-hoc factor pipelines from scratch.
- Prefer Qlib's expression engine over slow pandas `groupby().apply()` implementations when an equivalent operator already exists.

## 3. Expression Conventions

- Use adjusted prices for cross-day return and momentum-style comparisons when required by the factor definition.
- Use raw values for PIT accounting ratios or fields that should reflect reported, non-adjusted quantities.
- Keep `factor_library/qlib_expr_guide.md` aligned with live implementation rules.
- Work around the unary-negation parsing bug with `0 - Operator(...)` rather than `-Operator(...)`.

## 4. Research Process

- Enforce temporal train/validation/test splits. Do not use random splits for time-series research.
- Use `ExperimentTracker` / MLflow for substantive experiments and backtests performed from research code.
- Keep standardized performance analysis inside `src/result_analysis/`; do not add duplicate Sharpe/MDD/turnover helpers in notebooks or one-off scripts unless they are being promoted into that module.
