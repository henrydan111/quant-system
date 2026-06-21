# E-wave family-aware selection v2 — corrected selection + single-shot sealed OOS

> Supersedes `E_WAVE_SELECTION_v1.md` / `EWaveSelectedSet_v1.json`. v1 was assembled by hand and had
> two **verified** defects; v2 fixes both, runs the canonical marginal selection on actual factor
> values, and spends the one mandated sealed OOS. IS-only selection (2010-2020); OOS is now spent.

## Why v1 was wrong (both verified against the matrix data)

1. **Mislabeled basis.** v1's `style_resid_ic` column was actually the raw `heldout_rank_icir` (verified
   for all 9: e.g. corr_ret_turnd −0.782 = its heldout ICIR; its *true* `resid_ic_vs_style_controls_v1`
   is −0.036). v1 therefore selected by raw ICIR — exactly what its own protocol step 2 forbids.
2. **No redundancy pruning.** No selection script or correlation artifact ever existed, and v1 saturated
   *every* family cap (2+2+2+2+1=9) — the (1−maxcorr) penalty pruned nothing.

## The (a)/(b) decomposition (resolved the "is the E-wave just style?" question)

Net of a generic 14-factor style book (`STYLE_CONTROLS_V1`), the E-wave factors' residual IC looks near-
zero — BUT that book **contains a volatility style (`risk_vol_20d`) + 3 liquidity styles**, which overlap
the E-wave families. Proper IC-level retention (residual IC ÷ raw mean IC):

- **vs the approved BOOK (what we actually deploy alongside): all 6 reps retain 55–141%** → genuinely
  independent, not duplication.
- **vs the 14 generic styles:** corr/flow families retain (55%/222% median, no sign flips); vol/liq/mmt
  collapse — but that collapse is **(a) structural control-overlap** (netting a vol factor against a vol
  style), concentrated in exactly the overlapping families, **not (b) emptiness**.
- size+industry neutralization *strengthens* most of them → not a size/sector bet.

→ The style-residual is annotation-only, NOT a selection gate (using it as the basis would tautologically
nuke vol/liq).

## Exposure-correlation structure (input B — computed, not asserted)

69×69 month-end Spearman over the 2010-2020 IS panel ([select_e_wave_marginal.py](../../scripts/select_e_wave_marginal.py)):
within-family redundancy is high (**vol 0.63, liq 0.48, flow 0.43**, corr/mmt 0.33; some pairs 0.96–0.98);
cross-family is low (mean 0.07–0.26). → **5 genuinely orthogonal families, dense redundancy inside each.**

## Method + result (EWaveSelectedSet_v2)

quality = `|heldout_rank_icir|`; greedy marginal = `|icir|·(1−maxcorr to selected ∪ {rev_up_down_ratio_20d})`;
style-aware family caps (**vol≤1**, corr/flow/liq≤2, mmt≤1); the **6-core** = picks above the natural
marginal break (≥0.27; #7–8 drop to ~0.16 and are the most book-redundant).

| # | factor | family | held | IS icir | marginal |
|---|---|---|---|---|---|
| 1 | corr_ret_turnd_20d | corr | short | −0.782 | 0.661 |
| 2 | liq_vstd_20d | liq | short | −0.557 | 0.530 |
| 3 | vol_w_downshadow_std_60d | vol | short | −0.531 | 0.452 |
| 4 | corr_price_turn_post_20d | corr | short | −0.517 | 0.410 |
| 5 | flow_act_buy_shift_dist_xl_20d | flow | short | −0.492 | 0.345 |
| 6 | liq_shortcut_avg_20d | liq | long | +0.528 | 0.271 |

**vs v1:** 7 of v1's 9 confirmed; the **vol family is the only thing that changed** — v1's 2 redundant vol
picks (vol_highlow_std + vol_up_std) → 1 orthogonal pick (vol_w_downshadow_std_60d). (Other families are
cross-orthogonal, so raw-ICIR and marginal ranking agreed there.) Momentum (`mmt_route`) dropped: weakest
marginal + ρ=0.56 to the existing reversal factor.

## Single-shot sealed OOS — SPENT (`frozen_set_hash 316b17bc…9672f2`)

ONE `FrozenSelectionSet` → ONE real holdout-seal claim ([e_wave_v2_sealed_oos.json](e_wave_v2_sealed_oos.json),
`data/holdout_seals`). OOS 2021-01-01..2026-02-27, decile, direction-aligned, full provider universe.

| factor | held | OOS rank_icir | aligned LS Sharpe | bar |
|---|---|---|---|---|
| corr_ret_turnd_20d | short | −0.613 | 3.76 | PASS |
| liq_vstd_20d | short | −0.612 | 4.03 | PASS |
| vol_w_downshadow_std_60d | short | −0.516 | 1.57 | PASS |
| corr_price_turn_post_20d | short | −0.471 | 2.79 | PASS |
| flow_act_buy_shift_dist_xl_20d | short | −0.963 | 5.93 | PASS |
| liq_shortcut_avg_20d | long | +0.512 | 3.07 | PASS |

**6/6 PASS, all sign-stable, OOS ICIR ≈ IS (minimal decay) — the first clean sweep in this project's
sealed-OOS history** (GP 0/1, arXiv 1/5, eps canary-contingent). The IS-only family-aware selection
**generalized**.

## The hard caveat — NOT a tradable result

The LS Sharpes (1.6–5.9) are **gross, 5-day, decile, full-provider-universe** (incl. illiquid microcaps) —
the **registration bar, explicitly not a tradability metric** (the harness says so). eps_diffusion passed
this exact bar (LS 7.24) → collapsed to +4.5% CAGR / −62% MDD on the liquid universe. The high magnitude is
**plausibly** microcap/illiquidity-driven (not yet decomposed by size). **The deployment gate is the real
test.**

## Deployment gate (2026-06-21): FAILED — not deployable

The 6 as a direction-aligned equal-weight z-score **composite**, long-only top-K, **liquid top-300 by 20d
$-vol**, EventDrivenBacktester 1× realistic-China costs, OOS 2021-01→2026-02 vs CSI300
([eval_e_wave_v2_deployment.py](../../scripts/eval_e_wave_v2_deployment.py)):

| config | CAGR | MDD | Sharpe | turnover/mo |
|---|---|---|---|---|
| top30 / realistic | −3.63% | −52.6% | −0.05 | 74% |
| top50 / realistic | −2.89% | −51.4% | −0.02 | 69% |
| top30 / JoinQuant (optimistic) | −3.85% | −52.9% | −0.06 | 74% |

**Negative CAGR, ~0 Sharpe, −52% MDD, even with optimistic costs.** The gross sealed-OOS LS Sharpes
(1.6–5.9) were **confirmed illiquidity/microcap-driven** — restricting to liquid names and taking the
deployable long-only leg with real costs makes the alpha vanish. Same outcome as eps_diffusion (+4.5%/−62%).

## Verdict

**The E-wave 6-core is a VALIDATED evidence/replication library, NOT a deployable strategy.** The mandate's
fork resolved to the latter (OOS passed 6/6; deployment gate failed). A research success even though the
strategy failed: the sealed OOS validated the selection *method* (it generalized), the deployment gate caught
the *non-tradability* (microcap-bound) — both true, caught **before any capital**. Not rescued by re-
engineering the composite (that would overfit the spent OOS). OOS spent; the 6 stay `candidate` (not promoted).
