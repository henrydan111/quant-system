# GPT 跨审 prompt — 输入卡/Prompt 专业审计 v1(复制以下全文发给 GPT-5.5 Pro)

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. A single lookahead, a spent out-of-sample window, or a survivorship-filtered universe invalidates the result even if every test passes. Be skeptical, surface blockers, and do not rubber-stamp. You are additionally asked to review AS a senior buy-side PM / trader: the artifact under review is the INPUT SPEC (cards + prompts) of an LLM stock-scoring product, and information design quality is a first-class review dimension.

REPO (public — fetch any file to verify against the live code)
https://github.com/henrydan111/quant-system   (branch: calendar-unfreeze)
Raw file form: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/<path>

CONTEXT — read these to judge the change against the contract:
- CLAUDE.md (hard invariants §3, PIT §3.2, research integrity §7, no-hedge §7.10)
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/CLAUDE.md
- The product's shipped design (universal layer, C15/C16 containment, seat architecture):
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/README.md
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/VIRTUAL_RESEARCH_DEPT_DESIGN_v1.md
- Current implementation the proposal modifies:
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/regime_brief.py
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/cards.py
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/fact_table.py
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/pv_pack.py
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/retrieval.py
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/analyst_chain.py
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/prompts/fund_analyst_v1.txt
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/prompts/tech_analyst_v1.txt
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/prompts/news_analyst_v1.txt
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/prompts/bear_analyst_v1.txt
- The proposal under review (also embedded below, authoritative):
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/INPUT_PROMPT_AUDIT_v1.md

SELF-REVIEW PREFLIGHT — completed before this GPT request (adversarial second pass, doc §7): first-pass "clean" was premature; second pass found 5 Majors, ALL applied into the embedded doc: F1 margin-trend item's data window must END at D-1 (a label alone is not PIT); F2 PRE-EXISTING defect in the LIVE pv card — four items (融资余额20d变动/融资买入占比分位/北向持股比/北向20d变动) read window ≤D although their day-D values are disclosed next morning (one-publication-day lookahead in the current LLM input; flagged as v2.0 P0 fix, verified against pv_pack.py lines 36-167); F3 8-quarter series single-vintage rule (as-known-at-D preferred; never silently mix vintages given §3.2 restatement semantics); F4 new knowability-class framework (§6.3a: close-derived ≤D / evening-disclosed ≤D-1 / next-morning-disclosed ≤D-1 / ann-anchored); F5 the "true cross-sectional aggregate" line is NOT computable render-side (retrieval parquet caps non-direct at 25) — split into within-returned aggregation (render layer, P0) vs retrieval-layer aggregates (retr_v0.3 version bump, P1.5), amending the §6.5 boundary claim. Verified facts: $ps_ttm/$dv_ratio approved (field_status.yaml daily_basic); Tushare doc mirror does not state margin disclosure hour — conservative ≤D-1 rule is robust to that. Residual concerns handed to reviewer: the five questions in doc §7.3. THIRD PASS (user-directed): §8 systematic PIT sweep — all 23 pv preload fields + fact/regime/retrieval sources classified into knowability classes; no replay-mode lookahead beyond F2's four items; forward-mode evening-vendor data (moneyflow/cyq_perf/top_list) moved from "assume on-time" to a runtime data-readiness gate with ≤D-1 fallback (cyq_perf update hour 18-19h verified from the Tushare doc mirror; moneyflow/top_list hour absent from the mirror — stated as unverified, gate is robust to it). §9 adds the LLM-extraction program (input-side information design + inference-side elicitation + measurement discipline + explicit non-goals).

WHAT CHANGED (authoritative — the full proposal document is embedded below; treat it as the source of truth, links cross-check the surrounding code)
<<< 在此处粘贴 INPUT_PROMPT_AUDIT_v1.md 全文 >>>

QUANTITATIVE-RESEARCH PRINCIPLES — check the change against EACH; a violation is a Blocker
1. PIT / NO-LOOKAHEAD (the cardinal rule). Every proposed card item must be knowable at D close (the product's decision point is post-close of D, action earliest next open trading day). Scrutinize the per-item PIT table in §6.3 — especially: margin balance T+1 disclosure semantics; "昨日涨停今日溢价" (D-1 limit-up list × D performance — is it D-close knowable? yes, but verify the claim); the 8-quarter fundamental series (must come from the lag-1 PIT loader panels, never raw statements); the deferred share_float unlock calendar (announcement-anchored).
2. OUT-OF-SAMPLE IS SACRED. Not directly applicable (no factor selection), but verify: composite stays research_summary / banned from ranking; nothing in the proposal creates a feedback loop from scores to inputs (check: the regime card deliberately does NOT feed the LLM its own prior labels).
3. SURVIVORSHIP. Market breadth / limit-temperature aggregates must be computed over the full market including suspended/delisted names present in the panel (NaN rows excluded only day-wise).
4-6. Factor-eval / execution realism / leverage — not applicable (no strategy claims made); flag if the proposal accidentally makes one.
7. NO HEDGE WORDS. The document's empirical claims (e.g. "15/15 概念预告刷屏") cite live-platform inspections; flag any claim that is neither verified nor labeled unverified.
8. C15/C16 CONTAINMENT (product-specific hard rule). LLM output schema unchanged; deterministic judge unchanged; totals/advice never from LLM; payload remains untrusted data. Any proposal item that weakens containment is a Blocker.
9. VERSIONING DISCIPLINE. Card/prompt changes ride a single chain_v2.0 bump; retrieval config & snapshot untouched (render-layer boundary argued in §6.5) — judge whether that boundary argument actually holds, or whether e.g. the per-type quota + aggregation is a de-facto retrieval-relevance change that should be versioned as a RetrievalConfig candidate under C16b.

REVIEW QUESTIONS (answer each explicitly)
Q1 (user-mandated core): Is the three-section regime card v0.2 (snapshot/trend/persistence, §1.2) the right professional structure? What would a senior A-share PM add/remove? Is deliberately withholding the LLM's own prior regime labels (persistence expressed only via deterministic sub-state rows) the right call versus feeding label history?
Q2: §6.4 double-counting — rule A (full forecast row + prompt fence), B (direction-only status row), or C (keep fund seat blind)? Decide and justify against both information quality and composite integrity.
Q3: News card v0.3 — do per-line age+importance, per-type quota (≤3) and aggregate lines fix the flooding without distorting what the retrieval layer ranked? Is the render-layer/retrieval-layer boundary argument (§6.5) sound, or does the quota belong under C16b retrieval-config versioning?
Q4: Bear seat v2 — full scorecards instead of top-2 claims, plus the falsifier-verification mechanic (check each seat's what_could_weaken against the cards, strength-5 if already satisfied). Sound and containment-safe? Token cost worth it?
Q5: Fund card 8-quarter series with code-stamped acceleration labels — right granularity (4 vs 8 quarters)? Anything in the trajectory rendering that could smuggle lookahead (e.g. restated quarters — note the ledger's cumulative→quarterly late-restatement semantics in CLAUDE.md §3.2)?
Q6: Formatting standard (§6.1) — any remaining LLM-misread vectors (scientific notation, unit ambiguity, negative-PE display)?
Q7: What is MISSING that a professional analyst/trader would demand and the data plausibly supports (fields already ingested per the repo)? List concretely, mark each with its PIT anchor.
Q8: Priority ordering P0/P1/P2 (§6.6) — would you re-order? What is the minimum set that must land before the #10 full-month replay to make its archives worth reading?
Q9: The knowability-class table (§6.3a) — is it complete and correctly assigned? Specifically verify: 龙虎榜/block-trade evening disclosure handling, hk_hold CCASS T+1 morning, margin T+1 morning, and hunt for any OTHER item in the live cards (pv_pack.py PRELOAD list / regime card / fact table) whose day-D value is not actually knowable at the D-evening session — the systematic sweep (§8) classified all 23 preload fields and found four violations (F2); falsify that sweep if you can.
Q10: The data-readiness gate (§6.3a class ①b + §8) — is runtime per-dataset ingest verification with graceful ≤D-1 fallback the right forward-mode contract for evening-published vendor data (cyq_perf 18-19h documented, moneyflow/top_list hour-unguaranteed)? Any failure mode it misses (partial ingest, vendor restatement of same-day rows)?
Q11: LLM-extraction proposals (§9) — rank by expected value: line-ID evidence quoting (exact-match grounding), deterministic anomaly flags (⚑), absence-of-red-flags statements, peer-benchmark rows, evidence-BEFORE-score JSON field order, checklist-style seat procedures, structured falsifiers, adaptive k=3 ensembling gated on measured test-retest variance. Which are wrong or risky (e.g. do ⚑ flags bias the LLM toward code-selected evidence and effectively pre-score dimensions? does the absence statement risk false-negative grounding when event coverage is incomplete)?
Q12: Measurement discipline (§9.3) — is the process-metric vs predictive-metric split airtight against replay-tuning leakage? Is the golden-set (~50 hand-labeled name-days) the right pre-forward benchmark, and what labeling protocol would you mandate to keep it from becoming a fit-to-Claude's-own-priors exercise?

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending line quoted and an exact suggested replacement. Map every Blocker to the principle or invariant it violates.
- Answer Q1-Q8 explicitly (short verdicts fine where clean).
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.
```
