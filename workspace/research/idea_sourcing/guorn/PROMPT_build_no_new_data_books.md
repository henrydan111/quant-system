# Dispatch prompt — build the remaining no-new-data 果仁 GREEN books (#4, #15, #5)

> Paste the block below into a FRESH Claude Code session in `E:\量化系统`. It is self-contained (the
> receiving session has NOT seen the originating conversation). It runs IN PARALLEL with a session building
> #18 (which uses the new report_rc consensus data) — the book sets are DISJOINT, so no collision; the only
> shared files are the tracker / project_state / memory (append, don't rewrite; note it in your commit).

---

```text
ROLE & GOAL
You are continuing the 果仁 (guorn.com) deployed-20 parity campaign on this A-share quant system. 果仁 is a
TRUSTED benchmark; the LOCAL system is UNDER TEST. The goal is to reproduce real deployed 果仁 strategies
faithfully through the local engine and compare to 果仁's own backtest (yearly returns + holdings overlap) —
a match validates local data + universe + PIT + the event-driven engine. Build THREE more books that do NOT
rely on the newly-materialized report_rc consensus/rating data: #4 sm_GARP_illiq (xlsx 09), #15
成长_双创_GARP@周期 (xlsx 44), #5 sm_双创研发强度 (xlsx 10). NON-FORMAL parity research.

ENV: venv = E:\量化系统\venv\Scripts\python.exe. Windows; forward-slash paths; bash-style redirects.

MANDATORY CONTEXT REFRESH (read IN FULL before any code, in order):
1. CLAUDE.md  (§3 hard invariants — esp §3.2 PIT, §3.3 execution/limit gate, §8 four-layer backtest; §13 risky actions)
2. project_state.md  (read the latest 2026-06-27* notes — the 成长 cluster + report_rc state)
3. Memory: C:\Users\henry\.claude\projects\E------\memory\project_guorn_parity.md  (the FULL parity-ladder + deployed-20 history, incl. the 成长 cluster results + the recurring lessons)
4. workspace/research/idea_sourcing/guorn/deployed_20_VERIFICATION_TRACKER.md  (the campaign hub: triage, trade-model spec, weight-handling invariant, 成长-cluster section)
5. workspace/research/idea_sourcing/guorn/deployed_20_recipes.md  (the FULL 8-field recipes — your #4 = section "## 4.", #15 = "## 15.", #5 = "## 5.")
6. workspace/research/idea_sourcing/guorn/guorn_local_field_mapping.md  (the validated rung 1-5 果仁-indicator -> local-field/expression ledger + the doc-error corrections + conventions — THE map for which local field reproduces each 果仁 indicator)

THE PROVEN HARNESS PATTERN (clone it — do NOT reinvent):
- The 成长 cluster harnesses are guorn_verify_01_growth.py (full build/schedule/run), guorn_verify_02_growth.py
  (cache-reuse variant), guorn_verify_06_growth.py (TMT mask + 2 new factors). Read all three.
- Reusable pieces: ModelIIPosProfitStrategy (workspace/scripts/guorn_parity_rung2_posprofit.py — daily
  model-II rank-band, max_holds cap, hold_on_limit_up via the engine), research_utils (trading_calendar /
  st_codes_on / goal_metrics / sharpe), _guorn_overlap.py (selection overlap vs 果仁 holdings) and
  _guorn_redisplay.py (yearly LOCAL-vs-果仁 table; 果仁 年度收益统计 stores DECIMALS — 3.4035 = +340%, NEVER /100).
- Shape per book: (build) pull fields via Qlib D.features on the FULL 沪深 universe (Layer-1, universe-agnostic)
  -> compute the recipe's factor frames; (schedule) apply the eligibility mask (Layer-2) + the 果仁-EXACT
  composite [排名分 = (N-rank+1)/N*100 per factor in its recipe direction, NaN factor -> ranked LAST via
  na_option="bottom"; 综合 = Σ(排名分 × recipe weight); 市值 一级行业内 ranks within 申万L1] -> daily top-N
  schedule; (run) EventDrivenBacktester + ModelIIPosProfitStrategy, CostConfig 0.2%/side (no slippage/stamp/
  transfer), hold_on_limit_up=True, preload incl $up_limit/$down_limit; (compare) yearly vs 果仁 xlsx +
  _guorn_overlap.

NON-NEGOTIABLE LESSONS (these already cost the campaign):
- CONSUME ALL 8 RECIPE SUB-FIELDS: universe, filters, rankings, trade_model, buy_limit, sell_conditions,
  hold_keep_conditions, market_timing. (The #1 gap was an extractor that dropped buy_limit/sell_conditions/
  hold_keep_conditions -> it MISSED 不卖条件 涨停不卖 = hold limit-up winners, worth +8pp.) Each ranking
  factor has a TRAILING WEIGHT in the recipe (the number after dir/scope) — read it; weights are non-uniform;
  duplicate indicators (e.g. 总市值 ×2 at different scopes) are SEPARATE weighted terms, summed.
- INDUSTRY is NOT a Qlib field. `$sw2021_l1` returns all-NaN. For any 一级行业内 (within-SW-L1) ranking, build
  the industry frame via provider_metadata.build_industry_series_asof(index, level="L1") (see
  workspace/scripts/_fix_industry_cache.py). A fiscal-year/global fallback silently corrupts the term.
- PIT: every fundamental read is as-of effective_date; predictive factors wrap fields in Ref(...,1). Adjusted
  prices for cross-day returns, raw for accounting ratios. Use the rung 1-5 mapping for the exact local field.
- ⚠ DO NOT USE the new report_rc consensus/rating fields ($report_rc__np_fy1 / op_rt_fy1 / n_active_orgs /
  rating_up / rating_dn). They are QUARANTINE and owned by a PARALLEL session (P5). Your three books are
  chosen to NOT need them.

OMISSION DISCIPLINE (these books have irreducible/unavailable factors — OMIT with documentation, measure impact):
- #4 sm_GARP_illiq (23 ranking factors): most are validated statement/价量 ratios (SalesQGr, CoreProfitQGr,
  ROETTMDiffPQ, EpsExclXorQGr, GrossProfit%AssetsQ, FCFQ_重算 growths, RnDQGR, EBITDAQ%EV, 总市值, ILLIQ filter,
  业绩预告 ✓). OMIT (irreducible): the 3 中性化 factors (指标标准化后中性化MI(RNDQP), 指标1指标2中性化(EPCOREPROFITQ,
  总市值), BP筹资市值比调整 — HNeutralize industry regression), 业绩快报归母净利QGr%PY (express — NOT materialized).
  波动率_季度指标(CoreProfitQGr%PY,12) = StdevQ over 12q — OMIT unless you reuse the quality_stability pattern
  (out of scope; just omit + note). ILLIQ(5) rank 0-65% is a FILTER (eligibility), not a ranking.
- #15 成长_双创_GARP@周期 = the #4 GARP factor base on the 创业板 (双创) universe — same omissions, 创业板 mask.
- #5 sm_双创研发强度 (15 ranking factors, 创业板+科创板 universe): keep 总市值, 振幅, RND%Assets, RnDTTMGr%PY,
  研发销售比率, RoeQ, ROETTMDiffPQ, 财报预约公布天数, 未来60日新增流通股(skip-lookahead -> omit), 业绩预告 ✓.
  OMIT: 评级调高家数 (report_rc rating — the new-data field, do NOT use), 10日融资偿还金额 (margin repayment
  $rzche — QUARANTINE), BP带壳01 (壳价值 — irreducible), 机构持股比例 + 管理层持股比例 (not materialized).
  #5 is the heaviest on omissions — document each + expect a larger residual.
- For EVERY omission: list it in the harness docstring + the result JSON, and state it's a documented gap.

ACCURACY MANDATE (the campaign's standing rule):
- For each book, compare LOCAL vs its 果仁 xlsx (Knowledge/果仁回测结果/{09,44,10}_*.xlsx): the corrected yearly
  table (_guorn_redisplay pattern) AND the selection overlap (_guorn_overlap pattern: my top-N ∩ 果仁 held /
  果仁, by year). HIGH overlap (the 成长 cluster got 40-48% top-N) = faithful selection -> any return gap is
  execution (果仁's microcap-fill optimism in bull years, the quantified rung-1 finding), NOT a defect.
- No hedge words: state the gap's cause with the data, or mark it unverified + name the test. The deployable
  number is the 1× event-driven total-return figure; never quote a levered number.

DELIVERABLES:
- guorn_verify_04_garp.py / guorn_verify_15_*.py / guorn_verify_05_*.py (clone the 成长-cluster pattern).
- For each: the LOCAL-vs-果仁 yearly table + overall annual/Sharpe/MDD + the top-N overlap.
- Update deployed_20_VERIFICATION_TRACKER.md (the 3 rows -> VERIFIED with numbers + omissions) — APPEND to
  the 成长-cluster section; a parallel session may also be editing this file + project_state + the memory, so
  keep your edits localized and note "parallel #18 session" in your commit message.
- Update memory project_guorn_parity.md (concise: the 3 books' results + any new lesson).
- Commit on branch report-rc-registration with a descriptive message ending:
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  (Commit ONLY when done + self-reviewed; do not push without the user's OK per §13 — the cross-review push
  exception does not apply here since these NON-FORMAL parity harnesses need no GPT §10 gate.)

START by reading the 6 context files, then build #4 first (cleanest), validate it vs 果仁 xlsx 09, then #15, then #5.
```
