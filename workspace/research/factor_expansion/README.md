# Factor Expansion — GPT 5.5 Pro Handoff

This directory is a **research-proposal handoff** for GPT 5.5 Pro to review and
complement the A-share factor library. Nothing here is wired into the production
catalog, registries, or backend — it is a review surface only.

**Round 2 update (2026-05-30):** GPT 5.5 Pro has reviewed Round 1; its findings are
integrated. The canonical artifact is now the **merged CSV (68 factors)**. See the
"Round 2" section in the proposal for what changed (1 confirmed bug fixed, TTM/dedup
methodology fixes applied, GPT's 27 candidates merged).

## Read in this order

1. **[`exhaustive_factor_proposal.md`](exhaustive_factor_proposal.md)** — the main
   document. Round-2 integration summary, backend field inventory, gap analysis (171
   catalog factors vs 518 materialized fields), factor families by category with PIT-safe
   Qlib skeletons + field-registry status, promotion caveats, GPT's promotion-priority
   ranking + A-share notes (§7).
2. **[`factor_candidates_merged.csv`](factor_candidates_merged.csv)** — **canonical set:
   68 unique factors** (47 Claude-v2 + 21 GPT, deduplicated), each re-stamped with live
   registry status + a `source` column. **Source of truth for exact expressions.** All
   rows pass raw-field-existence + PIT-safety validation.
   - [`factor_candidates.csv`](factor_candidates.csv) — Claude-only set (47 rows).
   - [`../../../Knowledge/factor_expansion_gpt_review_new_candidates.csv`](../../../Knowledge/factor_expansion_gpt_review_new_candidates.csv) — GPT's 27 raw rows.
3. **[`../../../data/factor_research/field_inventory.md`](../../../data/factor_research/field_inventory.md)**
   — the 518 base field stems / 3,649 raw bins actually materialized in the live Qlib
   provider (ground truth; the system does not ship the binary data itself).

## Repo context GPT should consult (all committed)

| What | Path |
|---|---|
| Current factor catalog (171 factors) | [`src/alpha_research/factor_library/catalog.py`](../../../src/alpha_research/factor_library/catalog.py) |
| Operator vocabulary + PIT-safe atoms | [`src/alpha_research/factor_library/operators.py`](../../../src/alpha_research/factor_library/operators.py) |
| Qlib expression syntax + pitfalls | [`src/alpha_research/factor_library/qlib_expr_guide.md`](../../../src/alpha_research/factor_library/qlib_expr_guide.md) |
| Field-status registry (the formal gate) | [`config/field_registry/field_status.yaml`](../../../config/field_registry/field_status.yaml) |
| Field-registry resolver API | [`src/data_infra/field_registry.py`](../../../src/data_infra/field_registry.py) |
| Full column dictionary (EN/中文, units, PIT) | [`data/data_dictionary.md`](../../../data/data_dictionary.md) |
| Data coverage / sync status | [`data/data_tracker.md`](../../../data/data_tracker.md) |
| Hard invariants (PIT, negation, adj/raw) | [`CLAUDE.md`](../../../CLAUDE.md) §3 |
| PIT-safety enforcement test | [`tests/alpha_research/test_factor_library_pit_safety.py`](../../../tests/alpha_research/test_factor_library_pit_safety.py) |

## Reproduce the artifacts

```bash
# 1. generate the Claude candidate set + field inventory from the live backend
venv/Scripts/python.exe workspace/scripts/generate_factor_candidates.py
# 2. validate any candidate CSV (raw-token field existence + PIT parser + registry)
venv/Scripts/python.exe workspace/scripts/validate_factor_candidates.py
# 3. merge Claude + GPT sets into the canonical deduplicated CSV
venv/Scripts/python.exe workspace/scripts/merge_factor_candidates.py
```

All read-only. They read the live field bins + the committed registry; they write only
`data/factor_research/field_inventory.md` and the CSVs under this directory. No Tushare,
no Qlib compute, no mutation of `data/`/`config/`/`src/`.

**Validation gate (hardened in Round 2):** `validate_factor_candidates.py` checks every
`$field` token against the **raw materialized bin set** (not collapsed base stems — this is
what catches non-existent PIT variants like `$cash_div_q0`), runs the project's
`find_unwrapped_field_references` PIT parser, and resolves registry status. It exits
non-zero on any field-existence or PIT-safety failure.

## Hard constraints any proposed factor must satisfy

- **PIT safety:** every `$field` wrapped in `Ref(..., 1)` (or the `ADJ_*_T1` atoms);
  `forward_return` is the only allowed unshifted exception (it is a label).
- **Negation:** `0 - Operator(...)`, never `-Operator(...)`.
- **Adjusted vs raw:** adjusted price for cross-day returns/momentum; raw values for PIT
  accounting ratios.
- **Formal eligibility** requires every referenced field to be `approved` in
  `field_status.yaml`. `unknown_field` / `quarantine` / `pending_review` families are
  exploration-only until promoted via `config/field_registry/approvals/`.

## What we want back

Concretely: additional factor families, A-share-specific anomalies, a promotion-priority
ranking for the `unknown_field` statement line-items, and a redundancy/collinearity review
against the existing 171. See §6 of the proposal for the full prompt.
