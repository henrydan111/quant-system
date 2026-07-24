# GPT Re-review #3 — Macro wave M1 — Tier-2 — FINAL round (open sweep)

Round **3 of 3** (the unit's §10 budget). Final pre-SHIP round = full-unit open sweep. If the
verdict is not SOUND-TO-PROCEED, I stop folding and take the divergence to the user. **Tier-2**
(frozen; no crafted-object analysis).

**Fold commit: `bb603e8`** (you reviewed `66d87a9`). Verdict folded: **REVISE, 2 P2** (all three
round-1 P1s confirmed closed by you) — zero declines.

## Your two P2s → the folds (both were residual contradictions inside the design doc)

1. **The "Every row" field list omitted `row_id`** while the section header claimed the
   amendment — an M2/M3 implementer reading the list would drop the pairing identity. The list
   now spells out all 12 keys (`row_id` first) and states it matches the implementation's
   `MS_ROW_KEYS` exactly.
2. **The MS02 source-table cell still said "turnover-rate + free-float-mv"** while the
   implementation and the frozen tercile rule use `turnover_20d` only. The cell now reads
   **turnover only**, with the rationale (float_mv already carries the size face in MS01) and the
   rule that a future second MS02 metric = a tercile-rule version bump. The table header is
   "as implemented", no longer "proposal".

No engine or test changes this round — the code was already consistent; the doc now matches it.
19 M1 tests green.

## Files (pin to `bb603e8`)

- https://raw.githubusercontent.com/henrydan111/quant-system/bb603e8/workspace/research/ai_research_dept/NF_UNIT_M1_DESIGN.md (the only file changed this round)
- https://raw.githubusercontent.com/henrydan111/quant-system/bb603e8/workspace/research/ai_research_dept/engine/macro_exposure.py (unchanged — context)
- https://raw.githubusercontent.com/henrydan111/quant-system/bb603e8/workspace/research/ai_research_dept/tests/test_macro_exposure.py (unchanged — context)
- https://raw.githubusercontent.com/henrydan111/quant-system/bb603e8/workspace/research/ai_research_dept/engine/macro_mappings/ms04_policy_channels_v1.yaml
- https://raw.githubusercontent.com/henrydan111/quant-system/bb603e8/workspace/research/ai_research_dept/engine/macro_mappings/ms05_shock_channels_v1.yaml

## Standing context for the sweep

- Round-1 folds you confirmed closed: coherent THS snapshot selection (order-free, latest-eligible
  only), role-labelled C16b bundle (+ snapshot content identity), all-or-nothing metrics, frozen
  tercile tie/minimum rules, the `row_id` amendment.
- The FROZEN M3 OBLIGATIONS stand: (a) pool as-of + content identity sealing, (b) per-day THS
  snapshot identity sealing (the static `ths_snapshot=None` bundle form is registration-only —
  your own condition), (c) absence rendering.
- The two mapping YAMLs remain the user's edit object (your 交通运输/家电 `fx_sensitivity`
  suggestion is queued in their pass); content edits before freeze are free, after freeze a
  version bump.

## Open-sweep questions (final round)

1. **Doc↔code consistency**: a mechanical full-text pass over the design doc + module docstrings —
   any remaining phrase that contradicts the implemented behaviour?
2. **Anything in the whole unit** (builder, mappings loader, snapshot selection, bundle, statuses)
   that the two prior rounds' narrower focus let through.
3. **Verdict:** SOUND-TO-PROCEED (M1 closed → M2, the macro flash section) or specific in-tier
   findings.
