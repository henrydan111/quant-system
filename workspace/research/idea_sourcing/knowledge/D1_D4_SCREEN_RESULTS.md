# arXiv D1-D4 frontier exploration — sandbox screen + marginal gate results

*Run 2026-06-10. Scripts: [build/probe_d1d4_fields.py](../build/probe_d1d4_fields.py) (field probe),
[build/eval_arxiv_d1d4.py](../build/eval_arxiv_d1d4.py) (4 direction screens),
[build/eval_arxiv_marginal_test.py](../build/eval_arxiv_marginal_test.py) (decisive gate).
Outputs: `workspace/outputs/idea_sourcing_arxiv/`. All Class-D sandbox evidence — IS-only
(2014/2017/2018..2020-12-31), ZERO OOS consumption, nothing registered.*

## Method

The gauntlet that validated `eps_diffusion`: field probe → sandbox custom-dict screen (raw +
size-neutralized RankIC/ICIR, fwd 5d+20d, every served field `Ref(...,1)`-wrapped) → the decisive
size-neutralized **marginal-contribution gate** vs the cached 31-factor book (combined RankICIR
0.791 full-window; the house rule: marginal IC × low correlation, NOT standalone ICIR). IS ends
2020-12-31 (house standard — keeps the 2021-2026 sealed-OOS window UNBURNED; deliberately NOT the
"2018-2021 IS" sketched in TOP_DIRECTIONS). Short-coverage candidates (D1 2018+, D4 2017+) are
judged on the **overlap-window** increment (base book ICIR recomputed on covered dates: 0.687-0.695
for 2018-2020, 0.78-0.82 for 2017-2020).

## Corrections to TOP_DIRECTIONS discovered en route

1. **"Unmined" was wrong at the catalog level**: catalog Cat 11/12/15 already define 7 moneyflow +
   5 northbound + 5 chip factors; `alpha_chip_weight_avg_dev` IS the Grinblatt-Han CGO verbatim and
   `north_hold_change_20d` IS D4's proposed form. The unified-eval full-catalog run (in flight)
   covers those; this exploration adds the paper-specific NEW forms + the book-marginal verdicts.
2. **hk_hold's served column is the BARE `$ratio`**, not `$hk_hold__ratio`.
3. **`$ratio` is zero-densified**: the builder writes 0 for non-Connect names (verified 2019-01-02:
   served = 1696 positives exactly matching raw A-share rows + 1856 zeros). All existing catalog
   northbound factors carry this zero-inflation tie mass → within-coverage (`ratio>0`-masked)
   variants fix it (size-neut ICIR of the 20d change: 0.20 unmasked → **0.47 masked**).
4. **Classic 8-quarter SUE is not buildable**: income family serves `n_income_sq_q0..q3` +
   `n_income_attr_p_sq_{q0,q4}` only → mcap/asset-scaled surprise forms instead.

## Screen results (primary metric: size-neut RankICIR, fwd_20d)

| rank | factor | dir | neut ICIR | \|t\| | pred. sign | note |
|---|---|---|---|---|---|---|
| 1 | sue_ni_mcap | D3 | **+0.502** | 20.7 | + ✓ | strongest standalone of the run |
| 2 | sue_rev_mcap | D3 | +0.461 | 19.0 | + ✓ | revenue surprise |
| 3 | behav_cost_disp | D1 | +0.430 | 11.6 | expl→+ | chip cost dispersion (85-15pct)/50pct |
| 4 | behav_cgo_smooth_20 | D1 | +0.348 | 9.3 | + ✓ | **Grinblatt-Han CGO holds in A-shares** |
| 5 | north_chg_60 | D4 | +0.334 | 10.1 | + ✓ | 60d northbound accumulation |
| 6 | north_level | D4 | +0.308 | 9.6 | expl | foreign-holding level |
| 7 | behav_cgo | D1 | +0.302 | 8.2 | + ✓ | unsmoothed CGO |
| — | ni_yoy_growth (control) | D3 | +0.298 | 12.3 | + | SUE beats plain growth by +0.20 ICIR |
| 9 | flow_sm_net_5 | D2 | −0.193 | 8.0 | − ✓ | retail net buying → reversal |
| — | behav_winner_rate | D1 | −0.170 | 4.6 | + → **FLIPPED** | high winner share → profit-taking ↓ |
| ✗ | flow_lg_net_5/20 | D2 | ~+0.05 | <2.5 | + | **informed-large-order hypothesis FAILS** |
| ✗ | north_accel_20 | D4 | −0.02 | 0.6 | + | acceleration term adds nothing |

## Marginal gate (decisive; vs the 31-factor book)

Full table: `workspace/outputs/idea_sourcing_arxiv/arxiv_marginal_test.{csv,json}`. Highlights
(verdicts on overlap-window increment; bar from precedent: GP +0.022, eps_diffusion +0.011):

| candidate | size-neut ICIR | max payoff corr (to) | inc (overlap) | verdict |
|---|---|---|---|---|
| **behav_cgo_smooth_20** | 0.347 | 0.88 (qual_roa) | **+0.0469** | PARTIAL — biggest marginal increment ever recorded in the idea-sourcing program |
| **behav_cgo** | 0.301 | 0.87 (qual_roa) | **+0.0430** | PARTIAL |
| north_level | 0.307 | 0.97 (size_ln_mcap) | +0.0367 | PARTIAL — near size clone, distrust |
| north_level_cov | 0.386 | 0.87 (qual_roe) | +0.0324 | PARTIAL |
| sue_ni_assets | 0.296 | 0.95 (grow_netprofit_yoy) | +0.0201 | PARTIAL — growth refinement |
| north_chg_60_cov | 0.530 | 0.75 (qual_roa) | +0.0195 | PARTIAL |
| **north_chg_20_cov** | 0.471 | **0.556** (qual_roa) | +0.0191 | PARTIAL — a hair over the 0.55 orthogonal line |
| sue_ni_mcap / sue_rev_mcap | 0.503 / 0.462 | 0.92 / 0.89 (grow_netprofit_yoy) | +0.0153 / +0.0156 | PARTIAL — growth refinements |
| flow_sm_net_5/20 | 0.19 / 0.18 | 0.79 / 0.77 (rev_return_5d / tech_rsi_14) | +0.013 / +0.011 | PARTIAL — reversal repackaged |
| behav_cost_disp | 0.432 | 0.55 (liq_turnover_20d) | +0.0078 | PARTIAL — low corr but below bar |
| flow_lg_net_5/20 | 0.06 / 0.04 | 0.81 / 0.80 | +0.005 / +0.003 | **REDUNDANT** |
| behav_winner_rate | 0.175 | 0.76 (tech_rsi_14) | **−0.0140** | **REDUNDANT** (and sign-flipped) |

## Per-direction verdicts

- **D1 (CGO / chip distribution): WINNER — build next.** `behav_cgo_smooth_20` adds +0.047 to the
  book (2× GP's increment), the paper's sign confirms in A-shares, and the dataset was factor-unused.
  Caveats to carry into the lifecycle: IS is only 2018-2020 (729 days, coverage floor) and the
  0.88 payoff-corr to `qual_roa` is period-confounded (the 2018-2020 白马/quality rally — winners sat
  on gains AND were profitable). The sign-flipped `behav_winner_rate` (gain-realization pressure) is
  a real behavioral observation but redundant as a factor. `behav_cost_disp` (corr 0.55) is a
  candidate for a later variant pass, below bar today.
- **D2 (informed large-order flow): DROP.** The lg+elg "informed money" hypothesis fails outright
  (ICIR ~0.05, REDUNDANT); only the retail small-order reversal side has signal and it is
  `rev_return_5d`/RSI repackaged (corr ~0.78, inc +0.013). The moneyflow dimension's information is
  already spanned by the book's reversal/technical factors at 20d horizon. (Intraday/shorter-horizon
  uses remain untested — out of scope here.)
- **D3 (SUE / PEAD): refinement, not a new dimension.** Strongest standalone (0.50) and the
  mcap-scaling genuinely beats plain YoY growth (+0.20 ICIR), but payoff corr 0.89-0.95 to
  `grow_netprofit_yoy` says it's a better-scaled GROWTH factor. `sue_ni_assets` clears the +0.02 bar
  exactly. Worth a lifecycle attempt AFTER D1, with the explicit framing "growth-family upgrade".
- **D4 (northbound): keep the within-coverage change forms.** Masking the zero-densified rows is
  the real finding: `north_chg_20_cov` (corr 0.556, neut ICIR 0.47) is the closest thing to
  orthogonal in this run but its increment (+0.019) is just under the bar; `north_chg_60_cov`
  similar. `north_level` is a size/quality clone (corr 0.97) — distrust its big increment. The
  existing catalog north factors should be re-examined with the coverage mask; a combined D4 verdict
  should also wait for the unified-eval Tier-1 results on the unmasked catalog forms.

## Lifecycle outcome (2026-06-10, same day)

User-approved follow-through: the winner + both borderline groups were added to the catalog as
drafts and run through the formal `factor_lifecycle` IS gate (temp-registry validation first,
then live). **All 5 passed draft→candidate**:

| factor | heldout RankICIR | sign-consistency | heldout blocks |
|---|---|---|---|
| `north_hold_change_20d_cov` | **+0.597** | 1.00 | 4 |
| `north_hold_change_60d_cov` | +0.541 | 1.00 | 4 |
| `earn_sue_ni_mcap` | +0.409 | 1.00 | 7 |
| `earn_sue_ni_assets` | +0.354 | 0.86 | 7 |
| `alpha_chip_cgo_smooth_20d` | +0.337 | 1.00 | 3 |

Registry after publish: 190 current = **93 candidate + 89 draft + 8 approved**. Selection class:
**a_priori IS-only** (NOT oos_informed_backfill — 2021-2026 unburned by our own statistics;
literature-informed caveat recorded). Full provenance:
[arxiv_d1d4_selection_provenance.json](../arxiv_d1d4_selection_provenance.json); runs under
`workspace/outputs/phase6_factor_lifecycle_{temp,live}_arxiv_d1d4/`. Ops note: the first live
attempt failed with a transient all-false field-eligibility (fail-closed working as designed);
clean re-run reproduced the temp verdicts bit-identically.

## Recommended next actions (in order)

1. **D1 → catalog draft + formal lifecycle**: add a smoothed-CGO draft (note:
   `alpha_chip_weight_avg_dev` already IS raw CGO — the new information is the 20d smoothing and the
   marginal evidence; decide add-variant vs annotate-existing at catalog-edit time), run
   `factor_lifecycle` (draft→candidate IS gate), then single-shot sealed-OOS. Watch the qual_roa
   confound in the heldout window.
2. **D4**: re-screen the EXISTING catalog north factors with the `ratio>0` mask once unified-eval
   publishes their unmasked Tier-1 rows (comparison evidence); promote a `_cov` variant only if the
   masked form's marginal increment improves on +0.019.
3. **D3**: optional lifecycle attempt for `sue_ni_mcap`/`sue_ni_assets` framed as growth-family
   refinement (expect high correlation flags).
4. **D2**: close the direction; record the negative result (this file) so it is not re-mined.
