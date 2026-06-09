---
trigger: model_decision
description: this rule should be applied when user prompt is related to quantitative strategy research
---

# Research Integrity

Rules to ensure all quantitative research produced by this system is scientifically rigorous and free from common data-snooping pitfalls. These rules are non-negotiable.

## 1. No Lookahead Bias Ever

- Any feature engineering or signal generation must strictly use point-in-time data.
- When mapping fundamental data to the trading calendar, always use `ann_date`, never `end_date`.
- Apply `shift(1)` after `merge_asof` where same-day leakage would otherwise occur.
- Any new data pipeline touching fundamentals must document its PIT compliance explicitly.

## 2. Train / Validation / Test Split Discipline

- Never evaluate on data used for training or hyperparameter tuning.
- Enforce temporal splits, not random splits.
- Rolling walk-forward validation is preferred over a single static split.
- The test-set boundary should be declared before experimentation and logged in MLflow.

## 3. Out-of-Sample is Sacred

- The final test set should only be run once per strategy variant.
- The workflow now has a mechanical seal at `src/research_orchestrator/holdout_seal.py`; do not treat OOS discipline as a soft convention.
- If iteration is driven by test results, it is no longer out-of-sample and that must be disclosed.
- Log the first test result before making follow-up adjustments.

## 4. Factor Evaluation Standards

- Evaluate candidate factors with at least IC, RankIC, ICIR, quantile spread return, and turnover before adoption.
- Factors with weak ICIR should be challenged or discarded rather than promoted by narrative alone.

## 5. Factor Documentation

- Factors in `src/alpha_research/factor_library/` should document formula, data source, decay horizon, and whether they are raw, neutralized, or transformed.
- Track raw factors and neutralized variants distinctly.

## 6. Experiment Logging is Mandatory

- Substantive model-training or backtest runs in `workspace/` should use `ExperimentTracker` / MLflow.
- Log parameters, metrics, and key artifacts so research decisions remain reproducible.

## 7. Survivorship Bias Awareness

- Use historical universes that include delisted names when constructing factors and backtests.
- Do not filter to currently listed stocks only.
- State clearly whether delisted stocks were included when reporting results.

## 8. Centralized Performance Analysis

- All serious backtest evaluation should use `src/result_analysis/`.
- Do not create notebook-local Sharpe, MDD, turnover, or trading-stat implementations when a standardized helper already exists.
- If a missing metric is genuinely needed, add it to `src/result_analysis/metrics.py` rather than inlining it in research code.

## 8a. No hedge words in quantitative analysis

This is non-negotiable. When analyzing a strategy result, a discrepancy between two backtests, a factor performance number, a portfolio drawdown, or any quantitative claim:

- **Banned vocabulary**: "likely", "possibly", "probably", "I think", "it appears", "seems to", "could be", "might be", "perhaps", "presumably", "plausibly", "presumably". Also banned: any sentence that asserts causation without naming the dataset/script/output that proves it.
- **Required form**: either (a) cite the exact data and computation that establishes the claim with certainty, or (b) explicitly mark the claim as unverified, name the specific test that would resolve it, and run that test before concluding.
- **The unacceptable failure mode**: presenting a plausible-sounding guess about WHY a result occurred as if it were the answer. Quantitative finance does not allow plausibility — it requires the actual data or an explicit "I do not know, here is exactly how I will find out".
- **The acceptable failure mode**: "I have not verified X yet. The test that would resolve it is Y (file Z, script W). Running it now."
- **Hypothesis labeling**: speculation is allowed but must be explicitly labeled "HYPOTHESIS:" and paired with a stated falsification plan. Unlabeled speculation that reads as a conclusion is a contract violation.
- **Diagnostic provenance**: when attributing a divergence between two backtests to a specific mechanism, name the exact dataset/script/output that proves the mechanism is responsible. Reference the diagnostic in `Knowledge/temp_plan/` or the equivalent run directory.

This rule applies to ALL responses about quantitative results, including trade comparisons, performance attribution, regime analysis, and gap decompositions. The CLAUDE.md mirror lives in §7 item 10.

## 8b. No leverage in strategy research (added 2026-06-08)

Leverage is NOT a viable option in strategy research. This is non-negotiable.

- Research, evaluate, and report every strategy **unlevered**: gross exposure ≤ 1× capital, no margin financing / borrowing to exceed 100% invested.
- Never propose leverage as a path to a return (CAGR) target, and never quote a **levered** figure as the headline / deployable result — the deployable number is the **1× number**.
- A long-only book is fully-invested-or-cash. A market-neutral book is sized at its natural 1× (funded long vs short, gross ≈ 1×); do not scale it up to chase a return target.
- Rationale: leverage adds no edge — it only multiplies volatility and drawdown proportionally — and the deployment context does not assume access to it. Return must be earned via Sharpe at native volatility, not borrowed. (Empirically, leverage on a high-vol long-only book is self-defeating: vol-drag + borrow cap the geometric CAGR while drawdown explodes.)
- `config.yaml risk.max_leverage` is a legacy field; it is NOT license to lever in research.
- The CLAUDE.md mirror lives in §7 item 11; the AGENTS.md mirror lives in §2a.3.

## 9. Phase 3 Factor Implementation Rules

- Use the two-layer factor framework in `src/alpha_research/factor_library/`:
  - Layer 1 Qlib expressions in `operators.py`
  - Layer 2 pandas cross-sectional transforms and composites
- Prefer `get_factor_catalog()`, `compute_factors()`, and `add_composites()` over rebuilding bespoke factor pipelines.
- Prefer Qlib expressions to slow pandas `groupby().apply()` logic whenever an equivalent operator exists.
- Use adjusted prices for cross-day return and momentum-style computations when the factor requires corporate-action-aware comparisons.
- Use raw values for PIT accounting ratios and other reported quantities that should not be price-adjusted.
- For predictive Qlib expressions, prefer `Ref(..., 1)` rather than same-day values when the signal is used for next-day trading.
- Keep `qlib_expr_guide.md` aligned with live implementation rules.
- Work around the unary negation parser issue with `0 - Operator(...)` instead of `-Operator(...)`.

## 10. Hypothesis Workflow

The formal workflow is hypothesis-driven. Profiles are execution paths inside this workflow; they are not the workflow itself.

### 10.1 The 10-stage workflow

1. Idea intake
2. Hypothesis formalization
3. Pre-registration
4. Quick-kill screen
5. Formal in-sample test
6. Robustness battery
7. Sealed OOS test
8. Portfolio integration
9. Capacity / paper validation
10. Live-small / terminal decision

Practical mapping in v1:

- `factor_screening` is the cheap quick-kill stage.
- `event_driven_signal_research` is the main formal research path for IS / OOS promotion in v1.
- `theme_strategy`, `ml_signal_model_research`, and `strategy_improvement` are still formal profiles, but they should be understood as stage executors inside the same lifecycle.
- **`hypothesis_validation` (added 2026-04-28, plan `jolly-seeking-lollipop`)** is the validation profile for stages 5-7 (Formal IS → Robustness → Sealed OOS) when the recipe is fully specified up front. It runs `hypothesis.prescription` (a `PrescribedRecipe` with universe + components + weights + topk + rebalance + cost model) verbatim through IS+gate+OOS+publish with no auto-search. Use this when prior research has already chosen the recipe and the goal is to confirm it survives sealed OOS testing. The discovery profiles (factor_screening, theme_strategy, event_driven_signal_research, ml_signal_model_research, strategy_improvement) ignore the prescription field and continue to auto-search their respective recipe spaces. Register validation hypotheses with `hypothesis_cli.py register --profile-id hypothesis_validation` for profile-aware floor validation; `verify-seal --expect-claims N` enforces an exact-count assertion on OOS claim events.

### 10.2 The 5 human gates

1. Pre-registration gate
2. Quick-kill promotion gate
3. IS promotion gate
4. OOS open / OOS review gate
5. Publish / terminal gate

### 10.3 Pre-registration rule

- Formal non-audit orchestrator runs must carry a `Hypothesis`.
- The load-bearing hash is `design_hash`, not a prose hash.
- Rewording the thesis must not create a new sealed test.
- The implementation anchor is `src/research_orchestrator/hypothesis.py`.
- Human workflow entrypoint is `workspace/scripts/hypothesis_cli.py`.

### 10.4 Sealed-OOS rule

- The final holdout is sacred and must be mechanically protected.
- Only DAG steps explicitly marked as `stage == "oos_test"` may open the sealed holdout; `TimeSplit` defines the committed windows, but stage ownership now lives on the executing step.
- First access must be logged.
- Re-opening the same holdout for the same `design_hash` must be blocked.
- Mechanical seal implementation lives at `src/research_orchestrator/holdout_seal.py`.

### 10.5 Multiple-testing rule

- Every formal test attempt must be written to the testing ledger.
- The effective family count must come from hypothesis content, not a free-text label.
- Renaming a factor or thesis must not reset the family count.
- Testing-ledger implementation lives at `src/alpha_research/testing_ledger.py`.

### 10.6 Gate and runtime operations

- Formal non-audit DAGs now insert `gate_evaluation -> gate_concern_scoring -> gate_review` before publication.
- `gate_concern_scoring` pauses the run with `pause_for_input`, carries a typed `PauseForInputPayload` in memory, and expects a schema-validated `gate_concern_scores.json`.
- `gate_review` writes `gate_report.json` / `gate_report.md`, records the automated verdict, then pauses with `pause_for_gate` until a human `approved`, `rejected`, or `quarantined` decision exists.
- Seal-aware backtest execution is centralized in `src/research_orchestrator/sealed_backtest_runner.py`.
- The first date clamp before orchestrator-owned data loading lives in `src/research_orchestrator/window_enforcement.py`.
- Window-aware Qlib feature access is then guarded by `src/research_orchestrator/cache_manifest.py` and `src/research_orchestrator/qlib_windowed_features.py`.
- Human workflow templates for drafting hypotheses now live under `workspace/scripts/templates/`.
- `workspace/scripts/hypothesis_cli.py verify-seal` is the machine-check entrypoint: exit `0` means untouched, `1` means OOS already touched, `2` means malformed design hash.

### 10.7 YAML factor spec pointers

- Hypothesis-only YAML factor specs are defined by `src/alpha_research/factor_library/hypothesis_factors.py`.
- The schema anchor is `HYPOTHESIS_FACTOR_SCHEMA`.
- Immutable files live at `data/hypothesis_factors/{spec_hash}.yaml`.

