# CONTRACTS — binding gates for the trading-agents design (GPT-review-applied)

**Date:** 2026-06-28
**Status:** DESIGN contract spec — supersedes the 4 design docs + ROADMAP where they conflict.
**Origin:** GPT-5.5 Pro §10 cross-review — reviews #1-#3 = REVISE (all findings applied), **re-review #4 = SHIP (2026-06-30, clearing pass; 0 Blocker / 0 Major / 1 Minor)**. Every finding accepted.
These are the machine-checkable contracts + the tests that gate each phase's build approval.

> Convention (status lattice — see C14): **implementation may start at `test_stub`; phase build approval and
> any alpha evidence require `enforced` / `evidence_ready`** as specified by C14 (this supersedes the earlier
> "passing tests before build" wording, which was not machine-checkable).
> `fail closed` everywhere — missing/ambiguous metadata = reject, never default-accept.

---

## C1 · Text visibility PIT (B1 + M5) — gates Phase 2A
**Rule:** `trade_date` / `report_date` / `ann_date` / title date / event date are **NEVER** accepted as
visibility time. Every text row carries an immutable **`visible_at` = max(verified source publication
timestamp, first ingestion timestamp)** — **R5-B1 fix: `max`, NOT `earliest`** (information is actionable
only once it is BOTH published AND in our system; `earliest()` would admit post-ingestion data into a
pre-ingestion decision = lookahead). Fail-closed to `first_ingested_at` when source time is absent /
nominal-only / date-only / ambiguous / revised / vendor-backfilled. Also store `ingested_at`,
`source_url_or_doc_id`, `content_hash`, `vendor_snapshot_id`, `revision_id`. The text loader **fails
closed** when `visible_at` is missing, ambiguous, later revised, or after the decision timestamp.
Historical re-downloads are **engineering fixtures only** unless matched to an immutable as-of snapshot.

**Source-adapter contract (M5):** every news/research/announcement/tool adapter returns
`source_published_at, source_updated_at, retrieved_at, content_hash, query_hash, asof_decision_time`.
Fail closed if `source_published_at` missing, `source_updated_at > decision_time` without an archived
prior version, or `retrieved_at` after a replay decision. Live forward decisions record actual retrieval
time + immutable raw payload. **Live-source byte-replay (M3):** adapters also emit `raw_payload_hash`, `archive_or_vendor_snapshot_id`; the forward harness **fails closed if the raw payload cannot be replayed byte-identically** from the audit log, or content was updated after decision time without an archived prior version.

**Required tests (before Phase 2A build):**
`tests/pit/test_text_visible_time_gate.py` · `tests/pit/test_text_backfill_rejection.py` ·
`tests/pit/test_text_revision_hash_freeze.py` (must include a row with `trade_date ≤ decision_date`
but `ingested_at > decision_date` → excluded).

> Practical consequence: **historical text alpha is largely non-validatable** without a PIT archive →
> the clean path is forward (ingest now, stamp `ingested_at`). This converges with C2 + C5.

---

## C2 · LLM text-factor evidence labels (B2 + M1) — gates Phase 2B
Two labels, fail-closed:
- **`historical_llm_text_factor`** — allowed ONLY for schema dev, extraction QA, plumbing. **NOT alpha
  evidence** if the decision model's training cutoff is after any evaluated decision date.
- **`clean_llm_text_factor`** — requires `decision_date > max(` **cutoff∨release∨freeze of EVERY
  learned/parametric component** that can affect document inclusion / extraction / entity-linking /
  retrieval / dedup / clustering / rerank / OCR-layout / summarization / scoring / analysis `)` — incl.
  `Qwen_cutoff, Claude_cutoff, embedding_model_cutoff, reranker_cutoff, entity_linker_cutoff,
  OCR_layout_cutoff, prompt_freeze, schema_freeze, data_snapshot_freeze` **(R5-B2: not just "the decision
  model")**. Any unknown / mutable / post-decision component → `historical_*` only. Evaluated ONLY through
  pre-registered forward or post-cutoff OOS.

Historical sealed-OOS may validate **deterministic non-LLM parsers** or **frozen pre-cutoff models** —
**not** current LLM semantic factor generation. **M1 correction:** a sealed window *entirely pre-cutoff*
is NOT stronger — it is fully inside parametric memory. Clean = all decision dates **strictly after** the
generator model's cutoff + prompt/tool/data freeze. Mechanism audit is necessary, never sufficient.

**Required tests:** `tests/governance/test_llm_cutoff_blocks_historical_alpha.py` ·
`tests/governance/test_llm_text_factor_evidence_labels.py` (reject any
`factor_provenance=llm_generated ∧ eval_end ≤ model_training_cutoff`).

---

## C3 · 金股 PIT universe ledger (B3) — gates Phase 0
`golden_stock_universe(date)` is a **PIT boolean mask** built ONLY from recommendation events with
`published_at ≤ decision_time`, carrying source doc hash, broker, analyst, original security identifier,
as-of symbol mapping. Universe **includes delisted, suspended, renamed, ST, merged, later-untradable**
names. A recommendation enters no earlier than the next eligible trading decision after verified
visibility. Tradability (suspension, limit-up/down, T+1, liquidity) is applied **only in execution**,
never by deleting names from the research universe.

> Wire through existing survivorship infra (`provider_metadata` / `all_stocks.txt` / `namechange.parquet`
> / `st_stocks.txt`) — do NOT rebuild the 金股 pool from a current vendor table.

**Required tests:** `tests/universe/test_golden_stock_pit_membership.py` ·
`tests/universe/test_golden_stock_delisted_survivors.py` ·
`tests/execution/test_golden_stock_activation_after_publication.py` (fixture: recommended → later
delisted → absent from today's master → must still appear historically).

---

## C4 · IPO applicant ledger (B4) — PARKED (Option B, not in active line)
IPO is a **separate applicant-event pipeline**, not a stock-screen extension. Ledger = all accepted +
withdrawn/rejected/suspended/delayed applicants, inquiry replies, registration status, issue price,
listing date, first tradable date, board, lock-up, every filing's `visible_at`/`content_hash`.
Fundamentals computed on the full applicant ledger; execution begins only after first tradable date with
A-share IPO constraints. **Backtests including only successfully-listed IPOs are banned.** (Constraint
recorded now; IPO path is deferred like RD-Agent.)
**Scope (M2):** IPO is `PARKED_NON_EVIDENTIARY` — **no roadmap / README / CLI / report / investor-facing
artifact may describe IPO alpha as active** until C4 is unparked.

**Unpark gate (R3-Minor-2):** C4 can be unparked ONLY by a signed `IPO_UNPARK_REQUEST.md` that flips the C14
status from `parked` → `test_stub`, names the owner modules, and lists the applicant-ledger source plan —
before any IPO alpha work begins. README / ROADMAP drift cannot reopen it.

**Required tests (if/when unparked):** `tests/universe/test_ipo_applicant_survivorship.py` ·
`tests/pit/test_ipo_filing_visible_at.py` · `tests/execution/test_ipo_first_tradable_date.py` ·
`tests/docs/test_ipo_unpark_requires_signed_request.py`.

---

## C5 · Forward-harness evidentiary rule (B6) — gates Phase 3
**Quasi-forward replay is NON-evidentiary** — usable ONLY for interface, latency, audit-log, and
execution-simulator tests. It must **never** be reported as alpha / OOS / AI-trader performance. The ONLY
evidentiary harness for an `AI final decision` is **pre-registered forward paper-live** with immutable
decision logs, frozen prompt/model/tool hashes, source snapshots captured before the decision, and
baselines = quant-only + equal-weight.

**Required tests:** `tests/harness/test_quasi_forward_marked_non_evidentiary.py` ·
`tests/harness/test_forward_log_immutable.py` · `tests/harness/test_news_retrieval_no_future_articles.py`.

---

## C6 · Two mutually-exclusive AI modes (M2) — cross-cutting
`bounded_overlay_production_candidate` (deployable architecture) and `ai_final_decider_shadow` (shadow
experiment) have **separate** strategy IDs, pre-registration records, prompt/model hashes, OOS-spend
ledgers, baselines, promotion gates. **Results from one mode cannot tune, justify, or approve the other.**
**Reporting (m3):** separate report sections + strategy IDs per mode; no Sharpe/IC/drawdown/promotion
conclusion is pooled across modes.

## C7 · AI overlay caps in portfolio terms (M6 + R3-Major-1) — Phase 2B/3
The overlay may ONLY: (a) reduce a name to zero via a documented risk veto, or (b) apply a signed tilt
within `max_name_delta, max_sector_delta, max_turnover_delta, max_active_risk_delta` relative to the
quant-only portfolio. It cannot introduce names outside the PIT universe, cannot override
no-leverage/gross≤1×, cannot increase exposure to untradable securities.

**Fail-closed numeric caps (R3-Major-1) — "bounded" is a pre-registered number, not a word.** The overlay cap
config is an **immutable pre-registered artifact committed before any Phase 2B/3 evaluation**.
`max_name_delta`, `max_sector_delta`, `max_turnover_delta`, `max_active_risk_delta` MUST be **finite numeric
values with explicit units and hard upper bounds declared in the strategy registry**. **Missing, null,
unbounded, post-hoc-modified, or OOS-tuned cap values FAIL CLOSED** (no default-accept). Any cap large enough
to let the overlay dominate the quant-only ranking **reclassifies the strategy as `ai_final_decider_shadow`,
NOT `bounded_overlay_production_candidate`** (C6) — the LLM must not silently become the alpha engine.

**Required tests:** `tests/portfolio_risk/test_overlay_caps_required_numeric.py` ·
`tests/portfolio_risk/test_overlay_caps_frozen_before_eval.py` ·
`tests/portfolio_risk/test_overlay_dominance_reclassifies_strategy.py`.

## C8 · Identifier + panel contracts (M4) — before any Phase 2 join
All external identifiers enter through `SecurityMaster.translate(source, raw_code, asof)`; every factor
panel passes `assert_factor_panel_contract`: canonical instrument, canonical calendar, canonical
MultiIndex order `(instrument, datetime)`, no duplicate `(datetime,instrument)`, explicit NaN policy,
explicit sign convention, declared bucket count. **Hand-rolled `.replace('.', '_')` / ad-hoc joins are
banned** (extends the §3.1 Tushare↔Qlib invariant to the new text joins).

**Required tests:** `tests/contracts/test_security_master_roundtrip.py` ·
`tests/contracts/test_factor_panel_multiindex_order.py` · `tests/contracts/test_nan_and_sign_policy.py` ·
`tests/contracts/test_bucket_count_declared.py`.

## C9 · Phase-0 reporting discipline (M7)
Phase 0 reports IC/RankIC/ICIR/monotonicity/turnover/quantile-spread as **research diagnostics only**.
**No deployable performance claim** until Phase 1 event-driven **total-return** backtest applies T+1,
limit-up/down, suspension, corporate actions, realistic costs, gross≤1× (the §3.3 price-return vs
total-return distinction).

## C10 · Solo minimum-viable governance (M3)
Solo mode = immutable research registry + independent validation script + frozen selection set + IC/risk
attribution report + independent challenge memo + promotion checklist. **AI committee agents may comment
but cannot modify** factor definitions, OOS labels, model parameters, or approval state.

## C11 · Bucket-count freeze (m2)
Every factor-eval artifact records `bucket_count, bucket_method, rebalance_frequency, min_names_per_bucket`;
cross-bucket-definition comparisons prohibited unless labeled a separate experiment family (aligns with
the §3.5 unified-10-group standard).

## C12 · AI analyst typed output (m3)
Each AI analyst output is a typed record: `claim, evidence_span_ids, visible_at_max, affected_instruments,
direction, confidence_bucket, risk_type, expiry_date, non_actionable_reason`. Free-form rationale is
optional and non-trading.

## C13 · Evidence registry (m1)
Literature claims live in [evidence_registry.md](evidence_registry.md): claim · paper · URL/arXiv ·
verified_date · supported/contradicted/partial · design implication. **Unverified papers may motivate
caution but cannot be cited as named evidence for a quantitative claim.**

---

## C15 · Anti-manipulation / source-trust + injection isolation (R5-M2 + R6-m4) — gates Phase 2B
Every text object carries a `source_trust_tier`: **strong** (`anns_d` / `irm_qa` / `npr` / `monetary_policy`,
official) · **medium** (`research_report` broker / `news`/`major_news` media) · **weak** (social — not
ingested). **A weak-tier source is a lead only; it can NEVER be sole evidence for a score.** Red-flag
manipulation detectors (receivables/inventory growth > revenue; scarcity claim without margin improvement;
price driven by social heat; single unnamed customer; …) feed `penalty_scores`.
**Injection isolation (FULL PATH):** external text is **untrusted data at EVERY stage** (Qwen / Dossier /
Claude / Risk Judge / audit-replay tools); passed only as quoted/escaped fields, NEVER as system/developer
instructions or concatenated into executable prompts. **No LLM, prompt content, evidence span, or PDF/URL
text may trigger ad-hoc tool calls, URL fetching, PDF fetching, order generation, file writes, config
changes, or prompt/schema changes.** **(R6-m4)** Whitelisted source adapters MAY fetch official fields (e.g.
`anns_d` PDF URLs) ONLY through deterministic, pre-registered ingestion jobs (`adapter_id`, allowlist,
`retrieved_at`, `pdf_hash`, `pdf_visible_at`, `content_hash`, audit log) — adapter fetches are **data
ingestion, NOT LLM/tool actions**, and extracted PDF text remains untrusted under C15. Instruction-like
spans → `risk_flags=[injection]`, may only reduce trust / block, never drive action. **Anti-herding
(Fin-Bias ✅me):** broker/KOL opinions enter as *evidence*, never as *conclusions*. ⚠️ **A-share-specific
anti-manipulation empirical is ABSENT → design-only / forward-calibrated** (honestly labeled; not a gate).
**Required tests:** `tests/text/test_injection_isolation_full_path.py` ·
`tests/text/test_source_trust_weak_not_sole_evidence.py`.

## C16 · LLM-score containment (R5-B3) — gates Phase 2B
**Deterministic aggregation is NOT an alpha firewall.** Every LLM sub-score (`factor_score` / `penalty` /
persona) is itself a model output = a **candidate factor**; `final = clamp(Σ factor·w − Σ penalty·2)` only
*launders* an LLM decision unless every sub-score family: (1) is **pre-registered immutable** (name / rubric
/ evidence types / source-trust / horizon / universe / window / `prompt_hash` / `model_id` / weights);
(2) is **C2-clean** for historical evidence, else forward-only; (3) enters the **text candidate-factor
registry** and passes **marginal orthogonal contribution over the pure-quant baseline after costs +
DSR/PSR/FDR/PBO** (C16b multiplicity); (4) is produced by a scorer **BLIND to** realized returns / target
labels / desired action / future portfolio outcomes (quant-rank exposure only in a pre-registered
bounded-overlay test); (5) carries `evidence_spans` + passes deterministic schema/trust/timestamp
validation — **invalid → no-score, NOT neutral-positive**; (6) maps to tilt/veto/action ONLY through
deterministic **C7-bounded** logic — **the LLM never emits the final number / decision**; any guard failure
→ no AI tilt/veto for that object.
**C16b · text multiple-testing:** register `CandidateID = source_type × parser/model_id × prompt_hash ×
schema_version × scorecard_factor × persona/role × entity_scope × horizon × universe × aggregation_window`;
ALL explored variants/discarded prompts/thresholds count toward effective trials; approved → `FrozenSelectionSet`
before OOS/forward; no post-hoc merge/relabel/threshold-move within a frozen cycle.
**Required tests:** `tests/text/test_llm_subscore_is_candidate_factor.py` ·
`tests/text/test_deterministic_action_mapping_c7_bounded.py` · `tests/text/test_text_candidate_multiplicity_registry.py`.

---

## C14 · Contract implementation matrix (M1 + R3-Major-2)
**Status enum (R3-#4 m1):** `parked` + the ordered active lattice `design_only < test_stub < enforced < evidence_ready`. **`parked` is a non-active, fail-closed sentinel** — NOT comparable for phase advancement and **never eligible for alpha evidence**; a parked contract moves to `test_stub` ONLY through its explicit signed unpark gate (e.g. C4 → `IPO_UNPARK_REQUEST.md`). CI treats `parked` as a known sentinel, never an unknown value.
- `design_only` — contract text exists; no committed test.
- `test_stub` — a **committed, CI-discovered test exists and fails or xfails** against the missing
  implementation. Permits **implementation work only — NOT phase build approval.**
- `enforced` — the test **passes in CI and is required for merge.**
- `evidence_ready` — **all** phase-relevant contracts are `enforced` AND the experiment registry + OOS-spend
  ledger are frozen.

**Gates:** a phase advances design→build only when its required contracts are ≥ `test_stub`; it may produce
**alpha evidence** only when they are `enforced` (and the phase is `evidence_ready`). A `.md` artifact existing
is NOT `test_stub` (test_stub requires a committed failing/xfail CI test). **Current status (design stage): all active contracts `design_only`; C4 `parked` (non-active sentinel).**

**Required tests:** `tests/contracts/test_contract_status_lattice.py` ·
`tests/contracts/test_design_to_build_requires_test_stub_only.py` ·
`tests/contracts/test_alpha_evidence_requires_evidence_ready.py`.

| Contract | Risk | Phase gate | Status | Owner module (planned) | Last verified commit |
|---|---|---|---|---|---|
| C1 text visible-time PIT | lookahead | Phase 2A | design_only | data_infra/text_store | — |
| C2 LLM evidence labels | lookahead/leakage | Phase 2B | design_only | research_orchestrator | — |
| C3 金股 PIT universe | survivorship | Phase 0 | design_only | data_infra/provider_metadata | — |
| C4 IPO ledger | survivorship | PARKED | parked | — | — |
| C5 forward-only evidence | lookahead | Phase 3 | design_only | harness | — |
| C6 two-mode ledgers | overfitting | Phase 2B/3 | design_only | strategy_registry | — |
| C7 overlay caps | risk | Phase 2B | design_only | portfolio_risk | — |
| C8 id/panel contracts | corruption | Phase 2 | design_only | data_infra | — |
| C9 Phase-0 diagnostics-only | cost-realism | Phase 0 | design_only | result_analysis | — |
| C10 solo MVG | governance | all | design_only | research_orchestrator | — |
| C11 bucket freeze | comparability | all eval | design_only | alpha_research | — |
| C12 analyst typed output | auditability | Phase 2B | design_only | ai_layer (new) | — |
| C13 evidence registry | integrity | all | design_only (md exists; test pending) | docs | — |
| C15 anti-manip / injection | manipulation/injection | Phase 2B | design_only | data_infra/text_store + ai_layer | — |
| C16 LLM-score containment | overfitting / alpha-firewall | Phase 2B | design_only | ai_layer + alpha_research | — |

---

**Re-review #4 = SHIP (2026-06-30).** Minor m1 applied (`parked` explicit sentinel, C14 above). **GPT's single residual risk = implementation drift:** C1-C14 are `design_only` prose — before any phase build approval or alpha evidence, convert the phase-gating contracts into CI-discovered `test_stub` tests, then `enforced`.

**Re-review #5 (Phase-2 increment) = REVISE → all applied; re-review #6 = SHIP (2026-06-30).** Added **C15**
(anti-manipulation / full-path injection isolation; R5-M2 + R6-m4) + **C16** (LLM-score containment; R5-B3)
→ CONTRACTS now **C1-C16**; C2 extended to ALL learned components (R5-B2); **B1 `earliest`→`max` PIT bug
fixed in C1** (it was latent in the #4-SHIP'd C1). Same residual risk: implementation drift — esp. treating
C16-registered LLM sub-scores as "validated" before they pass forward/sealed evidence + marginal-contribution
+ multiple-testing.
