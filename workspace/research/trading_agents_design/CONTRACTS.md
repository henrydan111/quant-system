# CONTRACTS — binding gates for the trading-agents design (GPT-review-applied)

**Date:** 2026-06-28
**Status:** DESIGN contract spec — supersedes the 4 design docs + ROADMAP where they conflict.
**Origin:** GPT-5.5 Pro §10 cross-review (verdict REVISE). Every finding below was ACCEPTED.
These are the machine-checkable contracts + the tests that gate each phase's build approval.

> Convention: a Phase cannot start building until its contracts here have passing tests.
> `fail closed` everywhere — missing/ambiguous metadata = reject, never default-accept.

---

## C1 · Text visibility PIT (B1 + M5) — gates Phase 2A
**Rule:** `trade_date` / `report_date` / `ann_date` / title date / event date are **NEVER** accepted as
visibility time. Every text row carries an immutable **`visible_at` = earliest of (verified source
publication timestamp, first successful project ingestion timestamp)**, plus `ingested_at`,
`source_url_or_doc_id`, `content_hash`, `vendor_snapshot_id`, `revision_id`. The text loader **fails
closed** when `visible_at` is missing, ambiguous, later revised, or after the decision timestamp.
Historical re-downloads are **engineering fixtures only** unless matched to an immutable as-of snapshot.

**Source-adapter contract (M5):** every news/research/announcement/tool adapter returns
`source_published_at, source_updated_at, retrieved_at, content_hash, query_hash, asof_decision_time`.
Fail closed if `source_published_at` missing, `source_updated_at > decision_time` without an archived
prior version, or `retrieved_at` after a replay decision. Live forward decisions record actual retrieval
time + immutable raw payload.

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
- **`clean_llm_text_factor`** — requires
  `decision_date > max(model_training_cutoff, model_release_date, prompt_freeze_time, data_snapshot_freeze_time)`,
  evaluated ONLY through pre-registered forward or post-cutoff OOS.

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

**Required tests (if/when unparked):** `tests/universe/test_ipo_applicant_survivorship.py` ·
`tests/pit/test_ipo_filing_visible_at.py` · `tests/execution/test_ipo_first_tradable_date.py`.

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

## C7 · AI overlay caps in portfolio terms (M6) — Phase 2B/3
The overlay may ONLY: (a) reduce a name to zero via a documented risk veto, or (b) apply a signed tilt
within `max_name_delta, max_sector_delta, max_turnover_delta, max_active_risk_delta` relative to the
quant-only portfolio. It cannot introduce names outside the PIT universe, cannot override
no-leverage/gross≤1×, cannot increase exposure to untradable securities. ("Bounded" is executable, not
prose.)

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

**Re-review:** these contracts answer the REVISE blockers; the corpus goes back to GPT for a clearing pass.
