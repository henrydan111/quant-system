# CICC factor-logic cross-review — response & fold-in (R3)

> 2026-06-14. GPT 5.5 Pro reviewed the factor LOGIC (not the governance infra) of the D4a / D-COMP
> factors built this session and returned **CHANGES REQUIRED before any formal CICC factor evidence /
> candidate promotion** with 10 findings (5 blocking). Brief: [FACTOR_LOGIC_cross_review_brief.md](FACTOR_LOGIC_cross_review_brief.md).
> Nothing was ever promoted — all D4a/D-COMP factors are drafts at `candidate_ceiling`. This doc triages
> every finding and records the fold-in. Verdict opening (verbatim): *"CHANGES REQUIRED … Keeping these
> as drafts at candidate_ceiling is fine. But the current factor logic should not be treated as faithful
> CICC replication yet."* GPT also stated CFOAD/ROAD/CCRD/CSRD/DAD/CURD are "mechanically close enough to
> continue into controlled formal evaluation"; APRD/ROED/DTED/QRD/comp_cicc_profit "should not enter
> exact-tier CICC evaluation as currently written."

## Triage table

| # | GPT finding (blocking?) | Verdict | Action |
|---|---|---|---|
| 1 | `qual_aprd` is payables-turnover, NOT CICC accruals ratio; AND the proposed `(NI−OCF)/total_assets` fix is also wrong (CICC APR = 应计利润TTM / **营业利润TTM**) (BLOCKING) | **Accept** | `qual_aprd` **removed** from the catalog; manifest APRD row **unlinked** + `exclusion_reason`. Not rebuilt (see §1). |
| 2 | `comp_cicc_profit` mixes PIT-TTM CFOA with vendor cumulative-YTD ROE/ROIC (basis mismatch) (BLOCKING) | **Accept** | Downgraded to `proxy_approx` (hard candidate cap) in cohort **v2**. Exact TTM-ROIC not cleanly buildable (handbook itself flags ROIC ⚠️ 投入资本口径). |
| 3 | `qual_roed` / `qual_dted` use incl-minority equity; CICC ROE/产权比率 are 归母 (exc-minority) (BLOCKING) | **Accept** | Both downgraded to `proxy_approx` in v2. 归母 equity slots + 归母-NI single-quarter slots are unregistered → faithful form not buildable yet. |
| 4 | `qual_qrd` is inventory-only; CICC quick ratio subtracts more (1年内到期非流动资产 + 待摊费用 + 预付款) (BLOCKING) | **Accept** | Downgraded to `proxy_approx` in v2; missing quick-asset lines have no registered slots. |
| 5 | The new q1/q4 slots need an INDEPENDENT value-parity check (q0=latest, q1=prior, q4=4th-prior, no future ann) — "same derivation" is not sufficient (BLOCKING) | **Accept — built & run** | [canary_qslot_value_parity.py](../../scripts/canary_qslot_value_parity.py): **PASS**. See §5. |
| 6 | The 4 "strong" D4a are likely ~2 signals (ΔROE&ΔROA share NI_TTM; ΔCFOA&ΔCCR share OCF_TTM), not 4 (non-blocking) | **Accept — confirmed** | [redundancy_strong_d4a.py](../../scripts/redundancy_strong_d4a.py): within-group ρ≈0.86, cross-group ρ≈0.14. See §6. |
| 7 | Clean up stale catalog comments + the `accounts_pay` approval rationale (non-blocking) | **Accept** | catalog D4a comments rewritten; `accounts_pay` approval YAML annotated as unconsumed. See §7. |

## §1 — APRD removed (not rebuilt)

GPT confirmed my self-caught error AND rejected my proposed fix. The handbook truth ([CICC_基本面因子定义.md](../../../Knowledge/AI量化增强/CICC_基本面因子定义.md) §4): `APR_TTM = 应计利润TTM / 营业利润TTM`; `APRD = 当期 − 上期`. Two problems with building it faithfully now:
1. **Denominator** = 营业利润TTM (operating profit TTM). `operate_profit_sq` has only **q0 and q4** registered (confirmed in [field_status.yaml](../../../config/field_registry/field_status.yaml)) — q1/q2/q3 are absent, so operating-profit TTM (q0+q1+q2+q3) is **not buildable** with registered fields.
2. **Numerator** = 应计利润 (accruals); the handbook does not transcribe the exact form (standard is `NI_TTM − OCF_TTM`, but unconfirmed). `qual_accruals` in the catalog is `ocfps/eps` — a different (cash-realization) ratio, not the Sloan accruals ratio.

Rather than ship a third guess, `qual_aprd` is **removed**. The faithful build is deferred (needs `operate_profit_sq` q1-q3 registration + a transcribed 应计利润 numerator). The `accounts_pay_q0/q1` slots registered for the wrong interpretation are now **unconsumed** (a registered-but-unused approved field is harmless; rationale annotated, §7).

## §2-4 — proxy_approx downgrades (cohort v2)

Per the frozen-manifest contract ("revise by bumping to a new version file, never silently edit"), the tier corrections live in a new **[cicc_fundamental_cohort_v2.yaml](../../../config/replication/cicc_fundamental_cohort_v2.yaml)** (sha `ba94f3bcb0cf5fc1`); v1 is preserved unchanged under `config/replication/archive/` (and out of the gate's `*.yaml` glob). `source_cohort_id` is unchanged so the governance records stay keyed. The DENOMINATORS are unchanged — this is a conservative fidelity DOWNGRADE made before any OOS result (the opposite of p-hacking).

`proxy_approx` is a **hard `candidate_ceiling` cap** in `resolve_replication_ceiling` (must be REMOVED to advance), unlike `formula_equivalent_pending` (no tier cap — advanceable). Gate re-run confirms `comp_cicc_profit / qual_roed / qual_dted / qual_qrd` now resolve `ceiling=candidate_ceiling blocking=proxy_approx,…`. They can never enter exact-tier CICC evaluation until rebuilt faithfully (which removes the cap). The 6 mechanically-faithful D4a (CFOAD/ROAD/CCRD/CSRD/DAD/CURD) keep `formula_equivalent_pending` per GPT's "mechanically close enough."

## §5 — q-slot value-parity canary: PASS

[canary_qslot_value_parity.py](../../scripts/canary_qslot_value_parity.py) reads the materialized slot bins via `D.features` (no hand-rolled PIT alignment) and tests the **roll-forward identity** — when a new period rolls in, what was `q0` must become `q1` (`q1[t]==q0[t-1]`), and the single-quarter stack shifts (`q4[t]==q3[t-1]`). A future-ann leak would break this; so a high identity rate is simultaneously the "q1=prior / q4=4th-prior" and the no-lookahead proof.

**Result (82-name diverse basket, 2018-2022):**
- **Clean-stock value-run identity = EXACT** (600519/000002/600036/601318, each 20/20 on q1, q4, AND total_assets) — the decisive positional proof.
- **Basket clean-window (months outside Apr-May) q1==q0[t-1]: 99.7–100%** across all 10 fields.
- **Basket clean-window q4==q3[t-1]: 92–95%** (income/cashflow) — looser because the DEEPEST slot has the most cumulative-restatement exposure; positional correctness is independently proven by the clean-stock run-identity, so the basket residual is restatement noise, not an off-by-one.
- **slot-distinctness**: q1≠q0 on ~99% of rows (slots aren't q0 copies).
- The Apr-May rate (~70%) is the **annual-report + Q1 dual-disclosure / audit-restatement window** (q0 leapfrogs a period, or the held annual is audit-restated). Diagnosed empirically: 98% of identity breaks fall in months 4-5; e.g. `000333 2020-05-06` `q1`=audited-2019-annual vs `q0[t-1]`=express-2019-annual — q1 holds the genuine prior period, just restated. This is the documented PIT late-restatement behavior (CLAUDE.md §3.2), not a bug.

**OPEN ITEM (honest, unverified):** the q4 deep-slot basket residual (~5-8% on clean boundaries, e.g. `000538`'s 2019 reverse-merger restating 4Q of history) is *consistent with* cumulative restatement but I have not exhaustively root-caused every case. It affects only the deepest of the 4 prior-TTM summands used by CFOAD/ROAD/CCRD/ROED, at QoQ boundaries. The resolving test if it ever matters: trace each clean-window q4 break to a specific restatement event in the raw ledger. Not blocking for the current draft state.

## §6 — strong-D4a redundancy: ~2 signals, not 4 (confirmed)

[redundancy_strong_d4a.py](../../scripts/redundancy_strong_d4a.py), average per-date cross-sectional rank correlation, 700-name universe × 60 months:

| pair | ρ | group |
|---|---|---|
| qual_road ~ qual_roed | **+0.867** | within (NI_TTM) |
| qual_cfoad ~ qual_ccrd | **+0.855** | within (OCF_TTM) |
| all cross pairs | +0.09 … +0.16 | cross (mean +0.136) |

GPT's hypothesis is correct: the 4 "strong" D4a (IS heldout ΔROE 0.48 / ΔROA 0.46 / ΔCFOA 0.26 / ΔCCR 0.18) are **two near-orthogonal signals** — *net-income acceleration* (ΔROA≈ΔROE) and *cash-flow acceleration* (ΔCFOA≈ΔCCR). Per the project's selection rule (marginal orthogonal contribution, not standalone ICIR — [reference memory]), they must be treated as ~2 discoveries: keep one representative per group (or the orthogonalized residual), do not count near-duplicates as separate wins. This is recorded for the eventual factor-selection step; it changes no status now (all are capped at candidate).

## §7 — cleanup

- [catalog.py](../../../src/alpha_research/factor_library/catalog.py) D4a block: comments rewritten to state the fidelity tiers, the qrd/roed/dted proxy caveats, and the APRD removal rationale; removed the stale "deferred" / "payables-turnover period-matched" comments.
- `accounts_pay` approval YAML: annotated that the slots are currently unconsumed (APRD removed); the field stays approved (harmless, valid PIT field).

## Net state after fold-in

- D4a: **9 catalog factors** (was 10; APRD removed). 6 `formula_equivalent_pending` (CFOAD/ROAD/CCRD/CSRD/DAD/CURD), 3 `proxy_approx` (ROED/DTED/QRD).
- D-COMP: `comp_cicc_profit` → `proxy_approx`.
- All still drafts at `candidate_ceiling`; none promoted. The proxy_approx ones are now hard-capped (cannot reach exact-tier without a faithful rebuild).
- q1 slot positioning proven; q4 deep-slot residual flagged as an open (non-blocking) item.
- Strong-D4a redundancy recorded for the selection step.

GPT's gate ("CFOAD/ROAD/CCRD/CSRD/DAD/CURD may continue into controlled formal evaluation; APRD/ROED/DTED/QRD/comp_cicc_profit must not enter exact-tier as written") is now enforced mechanically by the v2 tiers.

## R3 round-2 — APPROVE WITH CONDITIONS fold-in (commit after 0c1fb5c)

GPT reviewed the fold-in and returned **APPROVE WITH CONDITIONS** ("comfortable continuing controlled draft/candidate-ceiling work"). All 4 conditions folded in:

| Cond | GPT condition | Action |
|---|---|---|
| 1 | Stale `comp_cicc_profit` catalog comment still says "first faithfully-constructible" | **Rewritten** to mark it `proxy_approx` / hard candidate cap, basis-mismatch reason, "do NOT trust this prose as faithful; manifest tier is source of truth". |
| 2 | Keep q4 parity open; **attribute** the clean-window q4 residual (or reconstruct from raw) before exact-tier | **Attributed** ([attribute_q4_breaks.py](../../scripts/attribute_q4_breaks.py)): **100%** of clean-window mature q4 breaks are deep-slot-specific (q1 CLEAN at the same date, **0%** stack-wide), relerr p50 ~9-10% → verified OLD-period restatement (audited annual revising year-old interim quarters), NOT an off-by-one. Raw-cumulative reconstruction remains the documented gold-standard before exact-tier. |
| 3 | CSRD `money_cap` fidelity rests on the D5 CSR source-line assumption | **Caveat added** to the `qual_csrd` catalog comment + the manifest CSRD row (inherits qual_csr CSR=money_cap parity; kept `formula_equivalent_pending` per GPT). |
| 4 | APRD's unlinked row reads as buildable `formula_equivalent_pending` | **New tier** `formula_unbuilt_pending_source_transcription` added to `REPLICATION_TIERS` (hard-blocked via `missing_required_field`; stays a formalization candidate so the frozen denominator stays 46, unlike `not_replicable`). APRD row set to it. v2 sha re-pinned `ba94f3bcb0cf5fc1 → 721e1be4c3fcd788`. |

**Verified attribution result (Cond 2 — the strongest remaining item):**
```
n_income_sq:       29 clean-window mature q4 breaks → 29/29 deep-slot-specific (q1 clean), 0 stack-wide; relerr p50 8.7% / p90 68.3%
n_cashflow_act_sq: 49 clean-window mature q4 breaks → 49/49 deep-slot-specific (q1 clean), 0 stack-wide; relerr p50 10.4% / p90 124.2%
```
A positional/off-by-one bug would break q1 too (q1 is 99.7-100% clean) or hit clean stocks (20/20). It does neither. The q4 residual is 100% old-period restatement — verified, no longer asserted.

**Status:** all 4 conditions satisfied; GPT's draft/candidate-ceiling continuation is unblocked. q4 raw-cumulative reconstruction stays the documented prerequisite before any exact-tier formal evidence (none is claimed). R wave: R1 P-GATE impl → R2 → R3 factor-logic (CHANGES REQUIRED → fold-in → APPROVE WITH CONDITIONS → conditions folded).
