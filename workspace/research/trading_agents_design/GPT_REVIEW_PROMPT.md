# GPT-5.5 Pro 跨审 prompt — trading-agents 设计语料(§10 gate)

**RE-REVIEW #2**(review #1 = REVISE,6 Blocker + 7 Major + 3 Minor 全部已接受并应用 → CONTRACTS.md / evidence_registry.md)。复制下面分隔线以下的全部内容,发给 GPT-5.5 Pro 做**清场审**。它会 fetch 7 个 raw 链接(CLAUDE.md + ROADMAP + CONTRACTS + evidence_registry + 4 设计文档)。跑完贴回结论——仍有 Blocker 我继续改,SHIP 我记入 project_state.md 定稿。

---

ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. A single lookahead, a spent out-of-sample window, or a survivorship-filtered universe invalidates the result even if every test passes. Be skeptical, surface blockers, and do not rubber-stamp. These are DESIGN documents (no code yet) — judge whether building to them would honor the contract, and whether the design itself has a fatal flaw.

REPO (public — fetch any file to verify against live code)
https://github.com/henrydan111/quant-system   (branch: trading-agents-design)
Raw file form: https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/<path>

RE-REVIEW #2 — this corpus already passed cross-review #1 (verdict REVISE: 6 Blocker + 7 Major + 3 Minor); ALL findings were ACCEPTED and applied. The binding resolutions are in CONTRACTS.md (C1–C13) + evidence_registry.md. YOUR JOB THIS PASS: (a) confirm each Blocker is fully closed by its mapped contract; (b) flag any residual gap OR any NEW blocker the contracts themselves introduce; (c) re-issue SHIP / REVISE / REWORK. Closure map — B1→C1, B2→C2, B3→C3, B4→C4(parked), B5→INTEGRATION_RDAGENT F3-unpark + C2, B6→C5; M1→C2, M2→C6, M3→C10, M4→C8, M5→C1, M6→C7, M7→C9; m1→C13+evidence_registry, m2→C11, m3→C12.

CONTEXT — fetch and read these:
- CLAUDE.md (hard invariants §3, PIT §3.2, sealed-OOS §3.4/§3.5, research integrity §7, no-hedge §7.10, no-leverage §7.11)
  https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/CLAUDE.md
- ROADMAP.md  (PLAN OF RECORD — read first; sequences the 4 design docs and supersedes their implicit ordering)
  https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/workspace/research/trading_agents_design/ROADMAP.md
- CONTRACTS.md  (BINDING — the C1–C13 gates that resolve review #1; supersedes the docs on conflict)
  https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/workspace/research/trading_agents_design/CONTRACTS.md
- evidence_registry.md  (literature verification status, finding m1)
  https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/workspace/research/trading_agents_design/evidence_registry.md
- BLUEPRINT.md
  https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/workspace/research/trading_agents_design/BLUEPRINT.md
- INSTITUTIONAL_WORKFLOW.md
  https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/workspace/research/trading_agents_design/INSTITUTIONAL_WORKFLOW.md
- INTEGRATION_RDAGENT.md
  https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/workspace/research/trading_agents_design/INTEGRATION_RDAGENT.md
- HARNESS_FORWARD_AI_TRADER.md
  https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/workspace/research/trading_agents_design/HARNESS_FORWARD_AI_TRADER.md

SELF-REVIEW PREFLIGHT — completed before this request: verdict = clean for GPT. Checked all 4 docs against CLAUDE.md §3 invariants + the 9 quantitative-research principles below. PIT/no-lookahead: foregrounded throughout (LLM confined to extraction on PIT-controlled inputs; RD-Agent F1 window-isolation + F2 Ref()/field-registry gate + F4 cutoff-overlap flag; HARNESS forward-only + 6 anti-lookahead rules). OOS-sealed: all AI outputs routed through the existing draft→candidate→approved sealed-OOS ladder; HARNESS pre-registration + immutable forward log = OOS spent once. No-leverage + four-layer pipeline + marginal-contribution selection: all honored. Fixes made: corrected a StockBench summary (abstract "struggle to outperform" → full-text "most beat a near-flat +0.4% baseline by small margins"; the doc reflects the calibrated read). The latest ROADMAP revision is incorporated (RD-Agent dropped → PARKED; Phase 2 deepened with multi-source external text + Tushare-text-permission and calendar-unfreeze data prerequisites). Residual concerns flagged for you below (Q5–Q8).

WHAT CHANGED (the design under review = ROADMAP.md [plan of record] + 4 design docs at the raw links above; concise summaries here for context — the raw files are authoritative)

REVISIONS in the latest ROADMAP (supersede the 4 docs where they differ): (a) RD-Agent AI factor mining is DROPPED from the active line — INTEGRATION_RDAGENT.md is retained but PARKED; review it only as a deferred option. (b) The AI-analyst phase is deepened (now Phase 2) to ingest multi-source EXTERNAL text (Tushare research_report/news/major_news/npr/anns_d — the doc-142 大模型语料 set), not just local report_rc. Two hard data prerequisites are recorded: Tushare text-data permission/credits (Phase 2A), and calendar unfreeze + daily ingestion resumed (Phase 3).

Cross-cutting thesis: this session's deep research established that LLM-agent trading alpha is largely a training-cutoff memorization artifact (Profit Mirage arXiv 2510.07920; LiveTradeBench 2511.03628; StockBench 2510.02209; Look-Ahead-Bench 2601.13770). The corpus therefore confines AI to roles where memorization cannot leak, and routes every AI output through the EXISTING sealed-OOS governance. Three AI directions share ONE foundation: a quant screen on the 券商金股 pool validated via sealed-OOS ("Phase 0").

0) ROADMAP.md (PLAN OF RECORD) — Sequences the work: Phase 0 quant母信号 (no AI, foundation) → Phase 1 portfolio engine (no AI, the real institutional gap; wakes dormant portfolio_risk; = the existing capital_allocation_buildout roadmap) → Phase 2 multi-source text + AI multi-analyst (deepened; 2A text-data infra with a NEW text visible-time PIT firewall + a new text store, gated on Tushare text permission; 2B persona agents → text-to-factor via sealed-OOS + bounded overlay) → Phase 3 forward AI-trader harness (gated on calendar unfreeze). Key planning claim: the next-largest value is Phase 0-1 (NO AI), not the AI layer; AI phases are evidence-gated exploration with explicit off-ramps.

1) BLUEPRINT.md — Core decision: the LLM is NOT the alpha engine; the quant factor model is. Architecture: 金股 candidate pool → quant alpha (sealed-OOS validated) → AI multi-analyst layer as a BOUNDED conviction/risk overlay (capped tilt + veto, NEVER a return forecast, ONLY PIT-controlled inputs) → decision → event-driven backtest → governance. AI allowed only in: structured doc extraction, narrative/policy/macro dimensions quant can't see, explainable rationales. Data finding: NO raw news/text is ingested — the 消息面 layer's first fuel is report_rc analyst revisions. Staged Phase 0–3; LLM enters late.

2) INSTITUTIONAL_WORKFLOW.md — Models a professional institution as 4 layers / 9 stages (Data → Research → Independent Validation[sealed-OOS] → Forecast+Risk-model → Portfolio construction → Execution → Independent Risk/veto → Attribution → Investment Committee/capital allocation). Principle: separation of duties + gates + attribution = anti-self-deception. For a solo operator, AI agents simulate the desks/committees you can't staff (governance/independent challenge, NOT alpha). Slow loop (research/capital) vs fast loop (execution/risk) must not cross (org-level lookahead protection). Finding: the institutional gaps (portfolio engine, independent risk, IC) equal the existing capital_allocation_buildout roadmap — the real next gap is the portfolio engine, not the AI layer.

3) INTEGRATION_RDAGENT.md [PARKED — deferred per the ROADMAP; review as a future option, not active] — Plugs Microsoft RD-Agent(Q) (NeurIPS 2025, Qlib-native LLM factor mining; arXiv 2505.15155) into factor_lifecycle as a SANDBOXED DRAFT FACTORY; the existing sealed-OOS ladder is the gate. RD-Agent's 5 self-admitted gaps (no multiple-testing correction, validation-set reuse across iterations, no factor-level PIT discussion, no slippage/impact/capacity, overfit control = only IC≥0.99 dedup) = exactly the existing governance layer. Four firewalls: F1 window isolation (RD-Agent never sees the sealed OOS; reconfigure its splits to IS-only ≤is_end); F2 translation/PIT gate (field-registry eligibility + Ref()-safety lint + definition_hash, fail-closed; constrain RD-Agent to the existing operator vocabulary so factors satisfy the §3.5 catalog-binding invariant); F3 multiple-testing (log the mining count → deflated Sharpe + marginal-contribution selection + FrozenSelectionSet one-shot OOS); F4 LLM-cutoff lookahead (the sealed-OOS window 2021+ partly overlaps the decision-LLM's training knowledge → a WEAKER test for LLM-generated factors → tag llm_generated provenance + a-priori mechanism audit + ideally a post-cutoff forward window).

4) HARNESS_FORWARD_AI_TRADER.md — A "quant screen → AI trader → forward paper-live validation" harness for the "AI makes the final decision" architecture. Premise: the AI's final decisions CANNOT be cleanly backtested (training-cutoff lookahead) → forward validation is the only honest path. Three parts: Part 1 quant pre-screen (sealed-OOS, historically validated shortlist); Part 2 AI decision layer (AlphaAgents debate→consensus + FinMem layered-memory templates; PIT inputs; frozen prompt+model hash); Part 3 forward paper-live (StockBench contamination-free protocol; the event-driven engine as paper executor). Decisive comparison: AI-on-shortlist vs quant-only-on-shortlist vs equal-weight buy-and-hold — if AI ≤ quant-only, AI is an explainer, not alpha. Six anti-lookahead rules + pre-registration. Practical blocker: the project's trading calendar is frozen at 2026-02-27 → true forward needs daily data ingestion resumed. Honest expectation: StockBench's clean window is weak/mixed/short evidence; expect little independent AI alpha.

QUANTITATIVE-RESEARCH PRINCIPLES — check the design against EACH; a violation is a Blocker
1. PIT / NO-LOOKAHEAD (cardinal). Does any value at time t use information not knowable at t — including the LLM's parametric memory of post-t events? Are research PIT reads confined to the sanctioned doors (pit_research_loader / qlib_windowed_features), never raw ledger or hand-rolled alignment? Are predictive fields Ref(...,1)-wrapped?
2. OUT-OF-SAMPLE SEALED. Temporal splits only; holdout single-shot/spend-on-attempt; never re-run a sealed OOS to "verify"; no factor/parameter selected on OOS results.
3. SURVIVORSHIP. Universes include delisted + suspended names.
4. FACTOR-EVAL STANDARD. IC/RankIC/ICIR/quantile-spread/monotonicity/decay/turnover; selection by MARGINAL orthogonal contribution, not standalone ICIR; min-IC floor.
5. EXECUTION & COST REALISM. T+1, limits, suspension, corporate actions; event-driven total-return 1× with realistic costs is the deployable number; never compare a vectorized price-return screen to it for a dividend book.
6. NO LEVERAGE. Every strategy unlevered (gross ≤ 1×).
7. NO HEDGE WORDS. Every quantitative claim is backed by a named source or marked unverified.
8. FOUR-LAYER PIPELINE. factor(full market) → universe(boolean masks) → signal(rank within sub-universe) → execution(tradability ONLY here).
9. MULTIPLE TESTING. Count effective trials (families/correlated clusters); guard with DSR/PSR/FDR/PBO where relevant.

REVIEW QUESTIONS
1. Correctness/soundness — any design step that, if built, would silently violate a principle above? Silent traps: Tushare(000001.SZ) vs Qlib(000001_SZ) format, MultiIndex(instrument,datetime) order, decile-vs-quintile, NaN/sign propagation.
2. Governance — does each doc honor the §3 invariants and route AI outputs through the sanctioned doors (get_factor_catalog; the orchestrator publish path; sealed-OOS ladder)? Any banned anti-pattern?
3. Design — simpler/more robust approach? Hidden coupling, drift from conventions, or reinventing something already in the repo?
4. Evidence — what proof is missing; the exact test/command to confirm a claim.
5. (INTEGRATION_RDAGENT F4) Is the claim correct that a sealed-OOS window partially inside the decision-LLM's training knowledge is a WEAKER test for LLM-generated factors? Is "mechanism audit + post-cutoff forward window" sufficient, or is there a stronger mitigation (e.g., constraining RD-Agent to a sealed window entirely pre-cutoff)?
6. (HARNESS) Are there hidden lookahead channels in "forward paper-live" beyond the 6 rules — e.g., the agent's parametric knowledge of recent macro/events even at the present edge, or news-API recency leakage? Should the quasi-forward replay mode be dropped as unsound?
7. (INTEGRATION_RDAGENT F3) Is deflated Sharpe + marginal-contribution + FrozenSelectionSet enough when the generator proposes hundreds of correlated factor families, or is explicit FDR/PBO required?
8. (Coherence/altitude) Is the BLUEPRINT "bounded veto/tilt" vs HARNESS "AI-decides" a coherent spectrum or a contradiction? Is the INSTITUTIONAL separation-of-duties over-engineered for a solo operator, or correctly load-bearing?
9. (ROADMAP) Is the phase sequencing and the per-phase gate/off-ramp sound? Is the claim "Phase 0-1 (no AI) is the larger value than the AI layer" correct? For the deepened Phase 2: is the text visible-time PIT firewall (consume only text whose visible_time ≤ decision date; note research_report.trade_date may NOT equal the true visible date) sufficient to prevent text lookahead — and is "text → factor → sealed-OOS" a valid way to validate AI-extracted text signals given the LLM's own training-cutoff overlap with the historical text corpus?

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor; each quotes the offending design claim (with the doc name) and gives an exact suggested replacement; map every Blocker to the principle/invariant it violates.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.
