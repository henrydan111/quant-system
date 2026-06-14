# CICC Wave E1a — factor-logic cross-review brief (for GPT 5.5 Pro)

**Reviewed commit:** `3e75b5c` on branch `report-rc-registration`
**Repo:** https://github.com/henrydan111/quant-system

**What this is:** the first price-volume replication tranche (CICC《价量因子手册》系列7 图表4 — 动量&反转).
Operators are **P-OP certified**; the 6 factor definitions are committed to the catalog but **NOT yet
registered** (draft registration + manifest `catalog_factor_id` linkage are held pending your verdict
and a §13 authorization). Please verify the **factor logic + operator→Qlib binding + dedup/deferral
governance** before I spend a single registry write.

This is a **verification** review (semantics/PIT/binding), not a truth-parity review — no OOS window is
touched by anything here (operator certification consults no truth table by design).

---

## Files to review (permalinks)

| What | Link |
|---|---|
| Operator certification script (the 4 operators' reference/vectorized/golden/property/PIT) | [certify_e1a_operators.py](https://github.com/henrydan111/quant-system/blob/3e75b5c/workspace/scripts/certify_e1a_operators.py) |
| Operator builders (Qlib expression strings) | [operators.py#L335-L412](https://github.com/henrydan111/quant-system/blob/3e75b5c/src/alpha_research/factor_library/operators.py#L335-L412) |
| Catalog factor definitions (E1a block) | [catalog.py#L78-L92](https://github.com/henrydan111/quant-system/blob/3e75b5c/src/alpha_research/factor_library/catalog.py#L78-L92) |
| Frozen PV cohort manifest (the governance contract) | [cicc_price_volume_cohort_v1.yaml](https://github.com/henrydan111/quant-system/blob/3e75b5c/config/replication/cicc_price_volume_cohort_v1.yaml) |
| Handbook source (逐字转录) | `Knowledge/AI量化增强/CICC_价量因子定义.md` §1 (图表4), lines 13–37 |

---

## The 6 factors (all genuinely-new; `_M`=1月=20d, `_A`=1年=250d)

| catalog_factor_id | handbook | handbook 构建方式 | Qlib expression (committed) |
|---|---|---|---|
| `mmt_route_20d` / `_250d` | mmt_route_M/A | 过去N内收益率 / 过去N内日度涨跌幅绝对值之和 | `If(Sum(Abs(ret),W)>0, Sum(ret,W)/Sum(Abs(ret),W), 0)` |
| `mmt_discrete_20d` / `_250d` | mmt_discrete_M/A | 上涨天数占比 − 下跌天数占比 | `Mean(Sign(ret), W)` |
| `mmt_time_rank_20d` | mmt_time_rank_M | 每日个股价格在时序(1年内)排名，取过去20交易日均值 | `Mean(Rank(adj_close_{t-1}, 250), 20)` |
| `mmt_highest_days_250d` | mmt_highest_days_A | 过去1年最高价距今天数 | `250 - IdxMax(adj_high_{t-1}, 250)` |

`ret` = `DAILY_RET` = `Ref(adj_close,1)/Ref(adj_close,2) − 1` (PIT-safe close-to-close).

---

## What I already verified (so you can focus on what I might have gotten wrong)

1. **Qlib primitive conventions** — checked against `venv/.../qlib/data/ops.py` source (these are the
   **first uses** of `Rank`/`IdxMax`/`Sign` anywhere in this catalog, so I did not trust the guide alone):
   - `Rank(x,N)` = `rolling(N).rank(pct=True)` (average-tie) → matches my certified `tsr_ref`
     `(less+(equal+1)/2)/N`.
   - `IdxMax(x,N)` = `rolling(N).apply(argmax()+1)` (1-indexed, today=N) → `N − IdxMax` = `(N−1) − argmax₀`
     = my certified `dsh_ref` (first-occurrence tie-break, same as `np.argmax`).
   - `Sign(x)` = `np.sign` (`sign(0)=0`) → `Mean(Sign(ret),N)` = my certified `ud_vec`.
   - Only divergence: Qlib uses `min_periods=1`, my cert used `min_periods=W` → differs **only in the
     warmup region**, which the eval warmup buffer always drops.
2. **PIT-safety** — every `$field` sits inside a `Ref(...,1)` frame (via `DAILY_RET` / `ADJ_*_T1`
   constants). Parser stack-walk test + operator-string-lock test: **75 passed**.
3. **Certification** — all 4 operators: `golden_panel`/`property_based`/`reference_vs_vectorized_random`/
   `pit_alignment` = True.

---

## Verification points — please challenge each

**Q1 — `path_adjusted_momentum` numerator.** The handbook says "过去N内收益率" (a *period* return). My
certified operator + Qlib expression use **Σ of daily simple returns** (`Sum(ret,W)`), not the compounded
period return `adj_close_{t-1}/adj_close_{t-W-1} − 1`. I chose Σ-daily-returns because (a) it is the
Kaufman efficiency-ratio numerator that pairs with the Σ|ret| denominator, and (b) it is what the
certified operator fixes. **Is Σ-daily-returns an acceptable `formula_equivalent_pending` reading of
"收益率", or is the compounding gap material enough that the numerator must be the period return?**

**Q2 — the `If(den>0, …, 0)` guard.** Matches the cert's `.mask(den==0, 0.0)`. Qlib `If` is `np.where`,
which evaluates *both* branches, so `num/den` is computed (→ inf/NaN + a RuntimeWarning) even when
`den==0` before `np.where` selects 0. Result is correct (0). **Acceptable, or do you want the
division itself guarded (e.g. `Sum(ret,W)/(Sum(Abs(ret),W)+ε)`) to avoid the dead inf?**

**Q3 — `mmt_time_rank` window split.** I read "个股价格在时序(1年内)的排名，取过去20交易日均值" as
**inner `Rank` window = 250 (1年)**, **outer `Mean` window = 20 (过去20交易日)** → `Mean(Rank(close,250),20)`.
Confirm the 250/20 split (not 20/20 or 250/250).

**Q4 — `mmt_highest_days` price basis.** I use **adjusted** high (`ADJ_HIGH_T1`). Within a 250-day
window a split/dividend rescales prices, but `adj_factor` is monotonic so the **argmax position is
unchanged** vs raw high → adjusted is safe and PIT-correct. Agree, or is there a case where adjusted vs
raw high changes the days-since-high count?

**Q5 — window-agnostic certification.** Operators were certified at **W=20 only**, then used at **W=250**
(`mmt_route_250d`, `mmt_discrete_250d`, the 250 inner rank, the 250 IdxMax). My claim: the operator
semantics are **window-parametric** (the reference-vs-vectorized identity holds for any W; window is a
factor-definition parameter, not an operator-semantics parameter), so one certified window suffices.
**Do you accept that, or should the cert sweep multiple windows (e.g. add a W=250 pass) before the 250d
factors are gate-eligible?**

**Q6 — `mmt_discrete_20d` dedup.** `up_down_day_share` = `Mean(Sign(ret),W)` is **rank-equivalent to the
existing `rev_up_down_ratio_20d`** (`Sum(If(ret>0,1,0),W)/W`) **except for flat-day handling** (sign
counts ret==0 as 0; the fraction ignores it). I chose to **register it anyway** and let the gate's
`resid_ic_vs_controls` (marginal-orthogonal-contribution) adjudicate the redundancy empirically, rather
than pre-excluding it. **Right call, or should a known ~0.98-correlated factor be excluded at
registration?** (`mmt_discrete_250d` has no existing 250d analogue → unambiguously new.)

**Q7 — `mmt_range` deferral + frozen-manifest accuracy (the subtle one).** The frozen manifest rows
`mmt_range_M/A` declare `required_operators: [amplitude_conditional_sum]`. But the **already-certified**
`amplitude_conditional_sum` uses a **fixed 4% amplitude threshold** (`rolling_sum(ret where amp>0.04)`),
whereas the handbook `mmt_range` is **"振幅大的前20% − 振幅小的后20%"** — a *rank-quantile, top-minus-bottom*
construction. They are **not the same operator**. I therefore **deferred `mmt_range`** from this tranche
and plan to **re-certify `amplitude_conditional_sum` to the true top/bottom-20%-by-rank formula** (keeping
the operator name) before building it.
**Is "keep the operator name, fix its certified formula later" acceptable, or does the frozen manifest's
now-known-inaccurate `required_operators` binding require a versioned `v2` manifest revision now (since
the manifest is the anti-p-hacking contract and currently names an operator whose certified semantics
don't match the row it gates)?**

**Q8 — registration mechanics / pre-gate state.** Plan: `sync_catalog()` adds 6 `draft` rows to
`factor_master` (non-privileged), then I add `catalog_factor_id` to the 6 manifest rows (sha-safe —
`catalog_factor_id` is excluded from `manifest_sha` by design). The **cohort-stamp (F3 reverse-stamp)**
and **linkage-ledger write (F11, definition_hash-bound)** happen later, **at gate time** (task #34), via
the handler. **Confirm this is the correct pre-gate state** — i.e. drafts + manifest linkage now, F3/F11
recording deferred to the IS-gate handler, not done eagerly at registration.

---

## Requested verdict format

Per-question: **OK** / **CHANGES REQUIRED** (+ the exact fix). Plus an overall gate:
**APPROVE to register the 6 drafts + link the manifest** / **CHANGES REQUIRED before any registry write**.
