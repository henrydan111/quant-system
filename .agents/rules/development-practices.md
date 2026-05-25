---
trigger: always_on
---

# Development Practices

Standards for writing robust, maintainable, and reproducible code in this quantitative trading system.

## 1. No Hardcoded Paths in `src/`

- All file paths in `src/` modules must derive from `config.yaml` or use project-root-relative references.
- Hardcoded absolute paths are acceptable only in one-off `workspace/scripts/` or `scripts/` utilities, never in reusable library code.
- When constructing paths, use `pathlib` or `os.path.join()` rather than string concatenation.

## 2. Configuration Management

- All tunable parameters such as API tokens, risk limits, model hyperparameters, and file paths should live in `config.yaml`.
- Never commit real API tokens or credentials. Use environment variables or a `.env` file for secrets.
- When adding a new configurable parameter, document its purpose with a nearby YAML comment or in the relevant README.

## 3. Naming Conventions

- **Python files**: `snake_case.py`
- **Classes**: `PascalCase`
- **Functions and methods**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`
- **Factor names**: `{category}_{name}_{lookback}` when the factor is horizon-specific

## 4. Module Boundaries

- Each `src/` module should import through public interfaces rather than reaching into another module's internals.
- New utility functions should be placed in the appropriate existing module, not scattered as standalone scripts.
- Finalized reusable research logic belongs in `src/`, not `workspace/`.

## 4.1 Research Performance Conventions

- Prefer the existing Phase 3 factor framework over new ad-hoc pipelines:
  - `src/alpha_research/factor_library/operators.py`
  - `src/alpha_research/factor_library/catalog.py`
  - `compute_factors()`
  - `add_composites()`
- Keep Layer 1 factor computation in Qlib expressions when an operator already exists. Use pandas mainly for Layer 2 cross-sectional transforms, composites, neutralization, or ranking.
- Avoid large `groupby().apply()` pipelines for factor generation when a Qlib expression equivalent is available; the expression engine is materially faster and scales better for full-market screening.
- Reuse existing helpers from `factor_eval`, `factor_library`, and `result_analysis` before introducing new local implementations.
- When documenting or adding a factor, state whether it uses adjusted prices, raw prices, or reported fundamentals so the price basis is unambiguous.

## 5. Dependency Management

- Install new Python packages with `E:\量化系统\venv\Scripts\pip.exe`.
- Pin exact versions in `requirements.txt`.
- Before adding a new dependency, verify whether Qlib, pandas, numpy, scipy, or another existing package already provides the needed functionality.
- Keep `requirements.txt` aligned with actual imports and remove stale packages when they are no longer used.

## 6. Error Handling and Logging

- Use Python's `logging` module, not `print()`, for operational output in reusable code.
- Wrap API calls and file I/O in try/except blocks with meaningful error messages where failures are recoverable or operationally important.
- Use appropriate log levels: `INFO`, `WARNING`, `ERROR`.
- Long-running or recurring scripts should write to `logs/` with rotation.
- Any script expected to run for a substantial amount of time should show a visible progress tracker and keep printing current progress to the console at regular intervals. Prefer `tqdm` or periodic logging with completed/total counts and ETA when practical.

## 7. Code Documentation

- Add module-level and public-API docstrings where they improve maintainability.
- When implementing financial formulas, document the underlying definition or notation.
- Document any non-obvious data-basis choice, especially adjusted-vs-raw price handling and point-in-time constraints.

## 8. Script Discipline

- One-off debugging scripts should be cleaned up after use.
- If a script is worth keeping, give it a descriptive name and document it in `scripts/README.md` or `workspace/README.md`.
- Avoid numbered variants of the same script; consolidate them instead.
- Utility scripts that operate on durable datasets belong in `scripts/` or `workspace/scripts/`, not in `data/` or the project root.

## 9. Version Control Hygiene

- Keep `.gitignore` excluding `venv/`, `data/`, `mlruns/`, `logs/`, `*.log`, `*.pyc`, `__pycache__/`, `.env`, and credential-bearing files.
- Never commit Parquet data, Qlib binary files, or large model artifacts.
- Temporary outputs such as audits, dumps, and build logs should live in `logs/` or `workspace/outputs/`, not beside source files.
