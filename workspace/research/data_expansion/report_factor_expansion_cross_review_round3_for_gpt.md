# Cross-Review ROUND 3 (final design sign-off) for GPT 5.5 Pro — Report-Factor Expansion **v3**

**Date:** 2026-06-08.
**Repository:** https://github.com/henrydan111/quant-system (public).
**Scope:** FINAL design sign-off before P1 coding. The plan has converged — rounds 1 and 2 were both
"GO-with-conditions on the P1 plumbing slice", **every checkable claim you made was verified against the
live code/data** and folded into **v3**. This round is deliberately narrow: (A) confirm the round-2
conditions landed *correctly* in v3, (B) resolve the 2-3 genuinely-open technical items, (C) give a clear
**P1-CODING GO / STILL-BLOCKED** verdict so we can stop reviewing and start the plumbing slice. Please do
NOT re-open settled architecture unless v3 actually got it wrong.

**Read (raw):**
- **v3 plan (under review):**
  https://raw.githubusercontent.com/henrydan111/quant-system/report-factor-expansion-review/workspace/research/data_expansion/report_factor_expansion_plan.md
- Operator set + PIT-safety rules (for the Part-B Qlib-expression question):
  https://raw.githubusercontent.com/henrydan111/quant-system/main/src/alpha_research/factor_library/operators.py
- The PIT-safety static lint the catalog expression must pass:
  https://raw.githubusercontent.com/henrydan111/quant-system/main/tests/alpha_research/test_factor_library_pit_safety.py
- Backend (`build_ledger` L2042/L2080, `materialize_provider` hook L2829):
  https://raw.githubusercontent.com/henrydan111/quant-system/main/src/data_infra/pit_backend.py

Round-2 verification (for your confidence — all confirmed): ledger-collapse real (`build_ledger` `else`
→ `(ts_code,end_date,disclosure_date)`, no `end_date` on report_rc, L2080); `tp` = total profit not target
price (data: median 128,700, range −3.9M…52M; target price = `max_price`/`min_price`); `create_time` absent
from the 21-col download; `_src_*` stripped before normalized write.

---

## Part A — confirm round-2 conditions landed correctly in v3
| R2 condition | v3 location |
|---|---|
| Explicit `report_rc` `build_ledger` key branch + row-count-preservation test | §2, §9-P1.1 |
| `tp` ≠ target price; `max_price`/`min_price` are; defer target-implied | §8 (T7) |
| `create_time` re-fetch + `max(next_open(report_date), next_open(create_time))`, else fixed `=2` lag | §5 |
| `_src_*` stripped → content-hash / durable provenance tie-break | §3, §9-P1.3 |
| Formula = MASK not clamp: `If(eligible,(up−dn)/n,NaN)`, null-safe `Sum(If(IsNull,0,…))`, `Sum(If)` not `Count` | §3 |
| FY1 first-visible **sidecar** `report_rc_fy1_boundary.parquet`; oracle rebuilds independently | §4 |
| `normalized_analyst_id` concrete rule + golden tests + `analyst_id_quality` | §3, §9-P1.4 |
| `n_active_analysts` live/TTL definition; `eps_change_epsilon` tolerance | §3 |
| `eps_fy1_dispersion` std/|mean| unstable → floor/MAD or quarantine | §8 |
| 9-item P1 acceptance gate (canaries+parity, not IC) | §9-P1 |

**Q-A1:** any of these only *appears* resolved but is wrong/incomplete as written in v3?

## Part B — resolve the last open technical items
1. **The masked Qlib expression must pass the static PIT-safety lint.** v3's intended factor is
   `eps_rev_breadth_W = Ref( If(eligible, (up_W − dn_W)/n_W, NaN), 1 )` with
   `eligible = (n_W >= 3) & (Ref($report_rc__n_active_analysts,1) >= 2)`. Checking `operators.py` +
   `test_factor_library_pit_safety.py`: **does this repo's expression engine support `If`, comparison
   (`>=`), and boolean `&` in catalog factors, and will every `$report_rc__*` reference satisfy the
   "every `$field` inside a `Ref(...)` frame" lint?** Give the exact repo-compatible expression (or the
   minimal operator additions needed), and confirm the `Ref(..., 1)` placement is lint-valid when the
   field already appears inside `Sum`/`If`.
2. **`eps_fy1_dispersion` robust definition.** Pick one to register (or keep quarantined): MAD/median,
   std with an EPS-magnitude floor, or unscaled std. Which is least gameable for an analyst-dispersion
   field, and what's the floor?
3. **Anything residual** — e.g. the content-hash tie-break determinism across machines, the
   `n_active_analysts` TTL value, or the eligibility-coverage reporting that the NaN-mask requires.

## Part C — final verdict
**Q-C1:** Is v3 ready to start P1 coding (the no-alpha plumbing slice), or is anything still a hard
blocker? If GO, name the **single test to write first** (we propose the ledger row-count-preservation
test on the 2-org/2-author/3-quarter same-date fixture). Give an explicit
**P1-CODING GO / GO-WITH-NITS / STILL-BLOCKED**.

## Consolidated questions
1. (A1) Any round-2 fix only superficially resolved in v3?
2. (B1) Exact repo-compatible, lint-passing Qlib expression for the masked `eps_rev_breadth_W` (or the
   minimal operator additions)?
3. (B2) Robust `eps_fy1_dispersion` definition + floor?
4. (B3) Any residual determinism / definitional defect?
5. (C1) **P1-CODING GO / GO-WITH-NITS / STILL-BLOCKED**, and the first test to write?
