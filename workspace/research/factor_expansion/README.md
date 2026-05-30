# Factor Expansion — GPT 5.5 Pro Handoff

This directory is a **research-proposal handoff** for GPT 5.5 Pro to review and
complement the A-share factor library. Nothing here is wired into the production
catalog, registries, or backend — it is a review surface only.

## Read in this order

1. **[`exhaustive_factor_proposal.md`](exhaustive_factor_proposal.md)** — the main
   document. Backend field inventory, gap analysis (171 catalog factors vs 518
   materialized fields), exhaustive factor families by category with PIT-safe Qlib
   expression skeletons + field-registry status, promotion caveats, and the explicit
   review questions for you (§6).
2. **[`factor_candidates.csv`](factor_candidates.csv)** — machine-readable expansion of
   the families into 51 representative concrete instances. Columns: `name, category,
   qlib_expression, fields_used, price_basis, registry_status, formal_eligible,
   expected_sign, expected_decay_days, neutralization, rationale`. **Source of truth for
   exact expressions.**
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
venv/Scripts/python.exe workspace/scripts/generate_factor_candidates.py
```

Read-only. Reads the live field bins + the committed registry; writes only
`data/factor_research/field_inventory.md` and `factor_candidates.csv`. No Tushare, no
Qlib compute, no mutation of `data/`/`config/`/`src/`.

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
