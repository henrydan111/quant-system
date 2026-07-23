# GPT Cross-Review Request — NF integration P3a (market-wide D7 attribute splitter) — Tier-2

Reviewing **one unit**: the P3a splitter that produces the D7 attribute texts every
`importance >= 4` positive base fact must have, so the per-stock D7 assembly (P3b) can run.

## ⚠ FROZEN REVIEW TIER — Tier-2

Per CLAUDE.md §10 review-tiering: the tier is set at design freeze and **the reviewer must not
escalate it mid-arc**.

- **Tier-2 = declared-invariant review**, judged against the declared invariants and the
  quantitative-research principles (PIT / no-lookahead first), assuming **ordinary well-formed
  in-process inputs**.
- **Tier-1 analysis is OUT OF TIER** — crafted objects, subclass overrides, dunder/metaclass attacks,
  adversarial in-process callers. Reserved (by user decision) for seal spend / holdout access / PIT
  kernels / the sealed-archive commitment. If you find such an issue, record it as an **OUT-OF-TIER
  note** (tracked, not gating); if you believe P3a warrants Tier-1, raise it as a **recommendation to
  the user**, whose decision the tier is.

**Commit under review: `e62695e`** on branch `calendar-unfreeze`.

## Context

- Offline producer chain, decision B: P1 typing (SOUND) → P2 cluster/route/assess (SOUND) → **P3a
  split** → P3b per-stock D7 assembly → P4 record/execute/seal → C1 session embedding.
- `verify_d7_artifact` enforces **total split coverage**: every positive base fact with
  `importance >= D7_IMPORTANCE_FLOOR` must be split exactly once (zero/missing/duplicate all refuse).
  **No producer of those splits existed** — they were hand-authored in tests only. So unlike P1 (which
  wrapped the existing `type_batch` classifier), P3a is a genuinely **new LLM extraction step**.
- **Market-wide, keyed by `fact_occurrence_id`.** Verified before designing:
  `render_news_flash_section` mints each base fact with `fact_cluster_id == cluster.fact_occurrence_id`,
  so a flash relevant to 50 stocks is split ONCE and P3b joins the minted `base_record_id` through that
  key — no per-stock multiplication.

## Files (pin to `e62695e`)

- https://raw.githubusercontent.com/henrydan111/quant-system/e62695e/workspace/research/ai_research_dept/engine/news_flash_split.py
- https://raw.githubusercontent.com/henrydan111/quant-system/e62695e/workspace/research/ai_research_dept/tests/test_news_flash_split.py
- downstream contract: https://raw.githubusercontent.com/henrydan111/quant-system/e62695e/workspace/research/ai_research_dept/engine/news_cards.py (`build_attribute_bundle`, `_build_attribute_records`, `verify_d7_artifact`'s coverage gate)
- attribute→dimension registry: https://raw.githubusercontent.com/henrydan111/quant-system/e62695e/workspace/research/ai_research_dept/engine/news_evidence.py (`ATTRIBUTE_DIMENSIONS`)

## Declared invariants (the review target)

1. **No dated source of its own; PIT inherited.** P3a opens no dated source. It consumes the verified
   P2 artifact plus the flash texts **injected** by the caller (`contents`, keyed by `content_hash` —
   P2's sealed record carries the hash, not the text), and requires its `(cutoff, ingest_class)` to
   equal P2's. Coverage of `contents` over the derived population is checked, so a silent empty
   extraction is impossible.
2. **P2 binding.** The P2 artifact is fully verified whether dict or path (`verify_assessed_flash_
   artifact`, newly extracted); identity must match; `artifact_sha256` bound into P3a's artifact.
3. **Population DERIVED, never caller-supplied**: exactly
   `{assessed : evidence_class ∈ {NFD,NFI,NFA} and typing.importance >= D7_IMPORTANCE_FLOOR}`.
4. **`source_status` is DERIVED, never model-authored.** It is a PENALTY-bearing attribute
   (`allowed_uses={penalty,bear}`, dimension `confidence_cap`), so it is rendered deterministically
   from the verified `verification_status`/`is_rumor`. The LLM produces only `fact` and
   `economic_linkage`.
5. **Every attribute text exact-`str` + substantive** (frozen `sanitize_text`/`has_substantive_text`
   predicate); `fact` mandatory (the D7 rebuild refuses a split without it); an unsupported
   `economic_linkage` must be an EMPTY STRING (attribute omitted), never invented.
6. **Deterministic for a fixed `call_fn`; immutable write-once artifact** (canonical microsecond
   cutoff path). With a real LLM the artifact seals ONE extraction run; downstream consumes the seal.
7. **NON_EVIDENTIARY**; empty population → empty artifact, no LLM call.

## Declared deferral

`timing` (dimensions `catalyst_timing` + `tradeability_at_horizon`) is NOT extracted in P3a v1 — only
`fact`, `economic_linkage` (LLM) and `source_status` (derived). Structurally fine (`_build_attribute_
records` builds whatever attributes are supplied; only `fact` is mandatory). Flag if you disagree.

## Self-review (done)

Clean for GPT. Two things the self-review caught and fixed before tests: (a) `verify_assessed_flash_
artifact` did not exist in P2 (only the path loader), so an injected dict would have bypassed the seal
check — extracted it (pure extraction, P2's 30 tests unchanged); (b) my first draft tried to read the
flash text from P2's artifact, which does **not** carry it — rather than bolt a `text_store` read onto
P3a (which would have broken invariant 1) or re-open the frozen P2, the texts are injected and coverage-
checked. Tests: 18 P3a + full ai_research_dept **795** green.

## Review questions

1. **PIT:** with no dated source of its own and an identity-matched P2 artifact, is P3a PIT-safe? Is
   the injected-`contents` boundary sound, or does it move a PIT obligation onto the caller in a way
   that needs an explicit binding (e.g. hashing the supplied texts into the artifact)?
2. **Coverage:** does the derived population exactly match what `verify_d7_artifact`'s split-coverage
   gate will demand downstream (positive classes × importance floor), so P3b cannot be handed a set
   that fails that gate?
3. **`source_status` derivation:** is deriving the penalty-bearing attribute (rather than letting the
   model write it) correct, and is the mapping from `verification_status` faithful?
4. **Extraction safety:** is the prompt/validation adequate for a NON_EVIDENTIARY replay — mandatory
   `fact`, empty-not-invented `economic_linkage`, substantive-text validation, exactly-one-result-per-
   idx? What would you require before this prompt is FROZEN for forward use?
5. **Verdict:** SOUND-TO-PROCEED (to P3b) or a specific in-tier declared-invariant gap.
