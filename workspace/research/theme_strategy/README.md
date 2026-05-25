# Theme Strategy Research

This research entrypoint is now treated as a first-class research workflow instead of a one-off script under `strategy_dev`.

## What lives here

- `theme_strategy_research.py`: the formal entrypoint for theme-driven research
- reusable logic still lives under `src/alpha_research/theme_strategy/`
- the old path `workspace/research/strategy_dev/theme_strategy_research.py` remains as a compatibility wrapper

## Where run results go

Theme-strategy runs still write their generated artifacts under:

- `workspace/outputs/theme_strategy/`

This keeps the workflow aligned with the workspace rule that generated artifacts should stay under `workspace/outputs/`.

## What each run now includes

Each run directory now includes:

- `run_console.log`
- `run_metadata.json`
- `artifact_manifest.json`
- the normal theme artifacts such as `field_inventory.csv`, `signal_recipe_summary.csv`, and `theme_review_zh.md`

The output root also keeps a lightweight discovery file:

- `workspace/outputs/theme_strategy/latest_runs.json`

## Example

```powershell
E:\量化系统\venv\Scripts\python.exe `
  E:\量化系统\workspace\research\theme_strategy\theme_strategy_research.py `
  --theme small_cap `
  --stage recipe
```
