# GPT Re-review #4 — NF integration P4a — CONFIRMATION round under the re-scoped model

Round 3 reached the §10 budget with 2 P1s; per protocol the divergence went to **user arbitration**.
This round is a **confirmation round**, scoped to exactly two things: the P1#2 fix diff, and the
formally re-scoped threat model that resolves P1#1. It is NOT a fresh open sweep.

**Fold commit: `5d3d0be`** (you reviewed `166813c`).

## THE RE-SCOPED FROZEN THREAT MODEL — v3 (the user's decision, per §10)

https://raw.githubusercontent.com/henrydan111/quant-system/5d3d0be/workspace/research/ai_research_dept/NF_ARCHIVE_THREAT_MODEL.md

Your P1#1 said exactly: *"若根确实应是运营方配置…冻结模型若要把根选择排除在外,需正式 re-scope."* The
user chose that formal re-scope (over a config-binding mechanism and over tracked debt). **v3 rules
root selection out of scope:**

- All five operator root dirs (`ledger_dir`, `prov_dir`, `archive_dir`, `store_dir`, `artifact_dir`)
  are ONE trust class; the boundary's guarantees are **relative to a fixed root set** — "no
  forged/decoupled value is sealed or accepted *within the operator's world*".
- A caller who designates its own roots and runs the genuine pipeline has built its own world, not
  forged the operator's — the same caller could equally point `ledger_dir` itself at a fresh
  directory, and caller-distinguishing inside one process is the documented combinatorial trap
  (ledger-integrity arc, user decision 2026-07-22).
- **Production-root binding is a FORWARD_PREREG deployment obligation** — a governed runner pins the
  roots (the `book_seal.py` live-refusal pattern). The pipeline remains NON_EVIDENTIARY with zero
  production callers until then.
- Admissibility rule (v3): an in-scope finding must demonstrate forgery / decoupling / mutation /
  leak **within one fixed root set**.

## The P1#2 fold (your probe, closed)

`resolve_committed_evidence`'s P1←store binding is now **exact-SET equality in both directions**
(was subset-only): `claimed - recomputed` refuses as before (a P1 minted over a different store),
and `recomputed - claimed` now also refuses — a store row not covered by the committed P1 means the
chain no longer represents the store (grown-after-commit or partial coverage). This matches the P2
production path's own population equality gate, as you prescribed.

Regression — your probe verbatim: `test_store_grown_after_p1_commit_refused` builds a real 2-row
store, commits the full genuine chain, ingests a third pre-cutoff row, then records → refused with
**no ledger file created**. 25 P4a tests, full `ai_research_dept` suite **872** green.

## Files (pin to `5d3d0be`)

- https://raw.githubusercontent.com/henrydan111/quant-system/5d3d0be/workspace/research/ai_research_dept/engine/news_flash_assemble.py
- https://raw.githubusercontent.com/henrydan111/quant-system/5d3d0be/workspace/research/ai_research_dept/engine/news_decision.py (unchanged this round — context)
- https://raw.githubusercontent.com/henrydan111/quant-system/5d3d0be/workspace/research/ai_research_dept/tests/test_news_p4a_chain_binding.py
- arbitration record: https://raw.githubusercontent.com/henrydan111/quant-system/5d3d0be/workspace/research/ai_research_dept/NF_UNIT_P4_DESIGN.md

## The confirmation questions

1. **P1#2:** does the two-directional exact-set gate close your probe, and does the new
   `recomputed - claimed` branch over-refuse any legitimate case you can see (e.g. an empty panel —
   both sets empty — must still pass)?
2. **P1#1 under v3:** with root selection formally out of scope and the admissibility rule holding
   the root set fixed, is your round-3 P1#1 resolved as OUT-OF-SCOPE — and do you see any finding
   that survives *within one fixed root set*?
3. **Verdict:** SOUND-TO-PROCEED (to P4b, under the v3 model, with the FORWARD_PREREG root-binding
   obligation recorded) or a specific in-scope-under-v3 gap.
