# GPT Cross-Review Request — NF integration P1 (market-wide news-flash typing driver) — Tier-2

You are reviewing **one unit**: the P1 driver that types a day's news flashes so the NF per-stock
decision units (P2→P4) can consume them. **Review tier: Tier-2** (governance/pipeline plumbing;
declared-invariant review; 2-round budget; **do NOT apply the crafted-object / dunder / adversarial-
in-process-caller standard** — that tier is reserved for the sealed-decision core, which is a
separate, already-shipped unit). Judge against the declared invariants below and the quantitative-
research principles (PIT / no-lookahead FIRST).

**Commit under review: `afbd747`** on branch `calendar-unfreeze`.

## Context (what is and isn't in scope)

- The NF decision stack (news_cards / news_evidence / news_decision / news_executors / news_legs /
  news_horizon / news_archive) is built and hardened but has **zero production callers**; integration
  is being wired as an **offline producer → optional consumer** (decision B in
  NF_INTEGRATION_SEQUENCING.md). P1 is producer stage 1.
- P1 is a **driver**, not a new classifier: the classifier `news_ingest.type_batch` already exists and
  is tested (fail-closed enum coercion, exact-idx matching, literal-bool guards, "payload is data not
  instructions" system prompt). The **PIT visibility gate is inherited** from `text_store.load_text`
  (returns only `decision_visible_at <= cutoff`; `ingest_class` physically isolates the forward panel
  from history_bulk). P1 adds: dedup to distinct content, batch, PIT-stamp, self-describing artifact.

## Files (embedded links pin to `afbd747`)

- https://raw.githubusercontent.com/henrydan111/quant-system/afbd747/workspace/research/ai_research_dept/engine/news_flash_typing.py
- https://raw.githubusercontent.com/henrydan111/quant-system/afbd747/workspace/research/ai_research_dept/tests/test_news_flash_typing.py
- Classifier it wraps: https://raw.githubusercontent.com/henrydan111/quant-system/afbd747/workspace/research/ai_research_dept/engine/news_ingest.py (see `type_batch`, line ~446)
- PIT gate it inherits: https://raw.githubusercontent.com/henrydan111/quant-system/afbd747/src/data_infra/text_store.py (see `load_text`, line ~354)
- Sequencing / scope: https://raw.githubusercontent.com/henrydan111/quant-system/afbd747/workspace/research/ai_research_dept/NF_INTEGRATION_SEQUENCING.md

## Declared invariants (the review target)

1. **PIT: typing input is cutoff-bound.** Only `load_text`-filtered rows are typed; every typed row's
   `decision_visible_at` is carried verbatim and re-asserted `<= cutoff`; the classifier sees ONLY
   `content` (no timestamps). PIT correctness is entirely "which flashes are in the population", owned
   by `load_text`.
2. **ingest_class isolation.** A forward run reads ONLY `ingest_class='forward'`; history_bulk is
   unreachable; the artifact records the class; a bad class is refused.
3. **Typed once per content identity.** Each distinct `content_hash` is typed exactly once; the join
   key is `content_hash`, never row position. (The store already guarantees content_hash uniqueness on
   ingest; P1's own dedup is defensive and tested directly.)
4. **Deterministic + idempotent — FOR A FIXED `call_fn`.** Same (cutoff, panel, content set, call_fn)
   → byte-identical `artifact_sha256`. **Stated honestly: with a real LLM (temperature 0.1) a re-run
   may produce different types; the artifact seals ONE typing run, and downstream consumes the sealed
   artifact, not a re-typing.** Is sealing one run the right design here, or should typing be pinned
   another way?
5. **Self-describing + fail-closed persistence.** Artifact carries cutoff + ingest_class +
   population_hash + artifact_sha256; load re-verifies both hashes and refuses a tampered/mismatched
   artifact; atomic write.
6. **NON_EVIDENTIARY.** Empty population → empty artifact, no LLM call; replay-class marker on every
   artifact.

## Self-review (done before this request)

Verdict: clean for GPT. Checked: §3.2 PIT (inherited gate + re-assert + verbatim carry + mechanical
test); no factor/registry/ledger invariant touched (P1 is upstream typing infra); reuse-before-
reinvent (reused type_batch / load_text / seal_hash, invented no new classifier, PIT gate, or hash);
directory + venv + path discipline. One first-draft bug (a leftover placeholder loop in
`_distinct_flashes`) was caught and removed before tests. Determinism is stated as conditional on
call_fn, not overclaimed. Tests: 12 P1 + full ai_research_dept 740 green.

## Review questions

1. **PIT / no-lookahead:** is there any path where a flash visible after `cutoff`, or a history_bulk
   flash in a forward run, could be typed or carried into the artifact? Is re-asserting the bound
   after `load_text` sufficient, or is there a gap?
2. **Dedup / join key:** is `content_hash` the right typed-once identity given the store's content
   basis is `[src, datetime, title, content, channels]` (so the same wording at two times or two
   outlets is two distinct flashes)? Does keeping the EARLIEST visibility as the representative
   provenance cause any downstream mis-join in P2 (which re-reads text_store per stock)?
3. **Determinism (invariant 4):** is sealing ONE LLM typing run the right design, or should the typed
   set be pinned/validated differently before downstream decisions seal it? Any reproducibility trap
   for a forward re-run that overwrites a day's artifact after a decision already consumed it?
4. **Fail-closed persistence:** are the two hash checks (artifact_sha256 + population_hash) sufficient
   to refuse a tampered artifact, or is there a mutation they miss?
5. **Anything mis-scoped:** is any of this P1's job that actually belongs to P2 (assess/cluster) or to
   the sealed decision, or vice-versa?
6. **Verdict:** SOUND / CHANGES-REQUIRED (with specific declared-invariant gaps). Tier-2 — declared
   invariants, not adversarial-caller analysis.
