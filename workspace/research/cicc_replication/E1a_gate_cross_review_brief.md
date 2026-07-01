# CICC Wave E1a — 7-domain matrix + P-GATE adjudication cross-review brief (for GPT 5.5 Pro)

**Gate:** APPROVE to run the `--live` P-GATE ceiling adjudication for the 6 E1a `mmt_*` factors
(→ `candidate_ceiling`, evidence-only, NO promotion) / CHANGES REQUIRED. This is task #34; the matrix
was rebuilt under the just-CLOSED residual-control-scope arc, so the 6 factors' 7-domain evidence is
fresh. Nothing has been gated yet — this is the pre-gate state for your sign-off.

**Repo:** https://github.com/henrydan111/quant-system  **Reviewed commit:** `58cc13c` on `report-rc-registration`
**Your E1a registration APPROVE** (the predecessor) was explicit that this is **NOT** formal-IS
approval and that warmup enforcement + the per-window cert payload are #34 prerequisites.

## Prerequisite (a) — warmup enforcement: RESOLVED (the headline of this brief)

Your "+finding": *"the gate must drop partial-window rows, not a generic 60d buffer."* The resolution
is **not** a row drop (which loses data) — the windowed factors are warmed because the **IS window
starts 490 trading days inside the provider calendar**, so Qlib's rolling operators warm every window
from the pre-IS runway. Two checks, both green
([verify_e1a_warmup_runway.py](https://github.com/henrydan111/quant-system/blob/58cc13c/workspace/scripts/verify_e1a_warmup_runway.py)):

- **(A) Runway guard** — calendar start `2008-01-02` → IS start `2010-01-01` = **490 trading days**, vs the deepest E1a window **271** (`mmt_time_rank_20d` = Rank(.,250)→Mean(.,20)). **490 ≥ 271 PASS.**
- **(B) Start-date invariance** — for all 6 `mmt_*`, the IS-window values requested from `2008-01-02` (fully warmed) vs from `2010-01-01` (warmed only via Qlib's internal window-extension) are **byte-identical: max|diff| = 0.000e+00** over [2010-01-01, 2011-12-31], including early 2010 (≤2010-02-15) where under-warming would show. This proves the rebuilt matrix evidence (computed from `is_start`) carries **no under-warmed rows**.

A fast structural regression guard (no qlib) locks invariant (A):
[test_e1a_warmup_runway.py](https://github.com/henrydan111/quant-system/blob/58cc13c/tests/alpha_research/test_e1a_warmup_runway.py)
(1 passed) — fails if anyone moves the IS start earlier or adds a deeper-window factor without
extending the calendar.

## Prerequisite (b) — per-window cert payload: status

Your non-blocking cleanup: `certify_e1a_operators.py --live` persisted only the `W=250` result (with a
both-window note). The 4 P-OP operators (`path_adjusted_momentum`, `up_down_day_share`,
`days_since_high`, `ts_rank`) **are certified** (the gate's `has_uncertified_operator` check passes),
so this does not block the ceiling. **Question 3 below:** do you want the both-window aggregate payload
persisted *before* the `--live` gate, or is it acceptable to gate now and backfill the payload (the
operators are already certified either way)?

## Gate inputs (all verified at `univ_all`)

- **Coverage**: `coverage_tier='full'`, `effective_ic_days=2654` for all 6 (the rebuild produced their 7-domain evidence).
- **Operators**: all 4 certified.
- **Only mechanical blocker**: `missing_domain_claim`. Registering a univ_all `FactorDomainClaim` → `candidate_ceiling` (truth-observed `2022-07-01` → the standard `short_oos_power_floor_fail` cap, exactly like the 10 D4a factors). Driver: [gate_cohort_factors.py](https://github.com/henrydan111/quant-system/blob/58cc13c/workspace/scripts/gate_cohort_factors.py); manifest rows: [cicc_price_volume_cohort_v2.yaml](https://github.com/henrydan111/quant-system/blob/58cc13c/config/replication/cicc_price_volume_cohort_v2.yaml).

## Honest IS strength (umj heldout ICIR / sign-consistency) — informational, NOT the ceiling

All signs **negative** ⇒ these are A-share **reversal** signals (path-adjusted momentum, up/down-day share, time-rank all invert at A-share horizons):

| factor | heldout ICIR | sign-consist | neutralized ICIR | IS bar (\|ICIR\|≥0.10 ∧ sign≥0.70) |
|---|---|---|---|---|
| **mmt_route_20d** | **−0.354** | 1.00 | −0.514 | **PASS** (strong; decay-stable −0.32…−0.35) |
| mmt_route_250d | −0.189 | 0.73 | −0.306 | PASS |
| mmt_discrete_20d | −0.143 | 0.82 | −0.252 | PASS (manifest-flagged near-dup of `rev_up_down_ratio_20d`) |
| mmt_discrete_250d | +0.077 | 0.45 | −0.083 | fail |
| mmt_time_rank_20d | −0.158 | 0.64 | −0.200 | fail (sign 0.64 < 0.70) |
| mmt_highest_days_250d | +0.009 | 0.45 | +0.091 | fail (≈ zero) |

**3 pass / 3 fail** the IS bar. Per the D4a precedent, the **P-GATE ceiling is a governance upper
bound, not an IS verdict**: the plan gates all 6 to `candidate_ceiling` (evidence-only); the separate
downstream `factor_lifecycle` IS gate (draft→candidate, orchestrator + human) is what would later pass
the 3 and stop the 3. Nothing here promotes anything.

## The plan (pending your APPROVE)

1. (optional, Q3) persist the both-window cert payload.
2. `gate_cohort_factors.py --live --factors mmt_route_20d,mmt_route_250d,mmt_discrete_20d,mmt_discrete_250d,mmt_time_rank_20d,mmt_highest_days_250d` → registers 6 univ_all claims + `_cohort_ceiling` + persists 6 `ReplicationGovernanceRecord`s (`candidate_ceiling`) + F3 cohort stamp + F11 linkage. Evidence-only, resolve-but-label.
3. Tests + project_state + commit.

## Specific questions

1. **Is the warmup-via-runway resolution acceptable** in lieu of an explicit partial-row drop? (max|diff|=0.0 proves identity; the runway guard + regression test lock it.) Or do you still want a hard row-drop in the eval harness?
2. **Gate all 6, or only the 3 IS-passers?** I recommend all 6 (ceiling = governance bound; the IS gate filters downstream — consistent with how all 10 D4a factors were gated regardless of IS strength). Gating only passers would conflate the ceiling with the IS verdict.
3. **Cert payload (prereq b) before or after** the `--live` gate? (Operators are already certified; the gate passes either way.)
4. **`mmt_discrete_20d` near-duplicate of `rev_up_down_ratio_20d`** (manifest-flagged): gate it normally with the dedup recorded, or hold it out of the cohort adjudication?
