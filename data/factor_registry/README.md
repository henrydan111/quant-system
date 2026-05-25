# Formal Factor Registry V1

This directory is the governance layer for the official factor catalog.

What lives here:

- `factor_master.csv` / `factor_master.parquet`
  - one row per `(factor_id, version)`
  - the current "main sheet" for status, latest evidence, and recommendation
- `factor_evidence.csv` / `factor_evidence.parquet`
  - one row per imported run and factor version
  - keeps screening, research, and catalog-sync history
- `run_index.csv` / `run_index.parquet`
  - one row per imported run
- `status_history.csv` / `status_history.parquet`
  - manual status change audit log
- `factor_registry_review.html`
  - human-readable browser view of the current registry
- `registry_metadata.json`
  - schema version and latest catalog sync counts

Important scope limits for V1:

- `catalog.py` stays the formula source of truth
- this registry only manages official base and composite factors
- candidate / draft factor pools are not part of V1
- factor values are still stored in the existing Qlib and research caches

Typical workflow:

1. `python workspace/scripts/factor_registry_cli.py sync-catalog`
2. `python workspace/scripts/factor_registry_cli.py import-screening --run-dir <screening_dir>`
3. `python workspace/scripts/factor_registry_cli.py import-research --run-dir <research_dir>`
4. `python workspace/scripts/factor_registry_cli.py summary`
5. `python workspace/scripts/factor_registry_cli.py set-status --factor <id> --status <status> --reason <text>`
6. `python workspace/scripts/factor_registry_cli.py render-html`

The HTML page is also regenerated automatically whenever the registry is saved
through the CLI workflows above.

Version binding:

- If an imported run carries matching catalog hashes, the binding is `verified`.
- If the imported run does not carry hashes, or the registry cannot match that
  snapshot to a known catalog sync, the binding falls back to
  `legacy_best_effort`.
