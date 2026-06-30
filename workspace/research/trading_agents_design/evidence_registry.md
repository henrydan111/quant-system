# Evidence registry — LLM-in-trading literature (contract C13 / finding m1)

**Date:** 2026-06-28. Rule: unverified papers may motivate caution but **cannot be cited as named
evidence for a quantitative claim**. "Verified by me" = fetched the arXiv page directly this session.

**Schema (M4):** the **Claim** column = `paper_claim` (what the paper states); **Design implication** =
`project_inference` (how it maps to a contract). A paper backs a contract ONLY via an explicit inference
row, never an indirect/unverified claim. **Verified** ∈ {✅ me = independently fetched, 🔎 = search-surfaced
→ re-fetch before citing as named evidence}.

**Row-label rule (R3-Minor-1, fail-closed):** any row with `Verified = 🔎` MUST carry `Support =
unverified_pending` and `Design implication = caution_only_until_refetched`. ONLY `Verified = ✅ me` rows may
use `supported` / `partial` / `contradicted` as evidence labels. *Test:*
`tests/docs/test_unverified_registry_rows_not_supported.py`.

| Claim | Paper | arXiv/URL | Verified | Support | Design implication |
|---|---|---|---|---|---|
| LLM-agent backtest returns evaporate past training cutoff (info leakage); SR decay 51–62%, TR decay 50–72% across TradingAgents/FinMem/FinAgent/FinCON/QuantAgent | Profit Mirage | [2510.07920](https://arxiv.org/abs/2510.07920) | ✅ me (title+thesis confirmed) | supported | C2 evidence labels; AI ≠ alpha engine |
| Contamination-free benchmark; most LLM agents only marginally beat a near-flat (+0.4%, 82d) buy-and-hold; financial-QA skill ≠ trading skill | StockBench | [2510.02209](https://arxiv.org/abs/2510.02209) | ✅ me (full-text numbers) | partial (weak/mixed) | C5 forward-only; humble expectations |
| Memorized historical financial data is a lookahead channel that inflates apparent accuracy and collapses OOS | MemGuard-Alpha | [2603.26797](https://arxiv.org/abs/2603.26797) | 🔎 GPT-surfaced (not fetched by me) | unverified_pending | caution_only_until_refetched (motivates C2 cutoff-overlap caution) |
| TradingAgents = multi-agent firm sim (analyst/researcher/bull-bear/trader/risk); 3-mo, 5 mega-caps, post-cutoff window; SR up to 8.21 flagged period-specific | TradingAgents | [2412.20138](https://arxiv.org/abs/2412.20138) | ✅ me | supported (architecture) / caution (results) | governance pattern, not alpha engine |
| RD-Agent(Q) iterative factor/model co-optimization; 2× ARR vs Alpha158/360 w/ ~22% factors; IC≥0.99 dedup; no multiple-testing correction | R&D-Agent-Quant | [2505.15155](https://arxiv.org/abs/2505.15155) | ✅ me | supported (method) | C2/M1; PARKED until B5 controls added |
| LLM "extractor + embedding ruler" turns disclosure drift into alpha, >2× vs NER baseline, ~orthogonal to FF factors | From Text to Alpha | [2510.03195](https://arxiv.org/abs/2510.03195) | ✅ me | supported | Phase 2B text→factor pattern |
| AlphaAgents (BlackRock): fundamental/sentiment/valuation agents debate→consensus BUY/SELL; backtest is itself contaminated (2024, in-cutoff) | AlphaAgents | [2508.11152](https://arxiv.org/abs/2508.11152) | ✅ me | supported (architecture) / caution (validation) | Phase 2B/3 decision template |
| FinMem: Profile + layered Memory + Decision; memory-augmented agent | FinMem | [2311.13743](https://arxiv.org/abs/2311.13743) | 🔎 search-level (html fetch returned wrong content) | unverified_pending | caution_only_until_refetched (Phase 2B memory module — motivation only) |
| Offline LLM-trading eval structurally leaks; stronger LLM ≠ better trading (LMArena corr ≈ 0) | LiveTradeBench | [2511.03628](https://arxiv.org/pdf/2511.03628) | 🔎 deep-research search-surfaced (not re-fetched) | unverified_pending | caution_only_until_refetched (motivates C5 forward eval) |
| Standardized look-ahead-bias benchmark; "Scaling Paradox" (bigger LLM worse OOS) | Look-Ahead-Bench | [2601.13770](https://arxiv.org/pdf/2601.13770) | 🔎 deep-research search-surfaced (not re-fetched) | unverified_pending | caution_only_until_refetched (motivates C2 cutoff risk) |
| arXiv link from user's ChatGPT prompt is REAL but a different paper (CN news→ETF allocation benchmark), not TradingAgents | CN-Buzz2Portfolio | [2603.22305](https://arxiv.org/abs/2603.22305) | ✅ me | n/a (provenance) | not the TradingAgents ref |

**To do at Phase 2 kickoff:** independently fetch the 🔎 rows (LiveTradeBench, Look-Ahead-Bench,
MemGuard-Alpha, FinMem) before citing any of their numbers as named evidence.
