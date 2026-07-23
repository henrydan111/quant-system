# GPT Re-review #3 — NF integration P3b — Tier-2 — FINAL pre-SHIP round

Round **3 of 3** (the unit's round budget under CLAUDE.md §10). Per the same section, the final
pre-SHIP round reverts to a **full-unit open sweep** (open sweeps happen exactly twice: round 1 and
this one). **Tier stays Tier-2** — crafted-object / subclass / dunder analysis is out of tier; raise a
tier change as a recommendation to the user, not as a finding.

If your verdict here is not SOUND-TO-PROCEED, I stop folding and take the divergence to the user with
three options (re-scope the threat model, switch to a structural mechanism, or accept the residual as
tracked debt) rather than opening a round 4.

**Fold commit: `2ac7192`** (you reviewed `4caf4a2`). Verdict folded: **REVISE, 1 P2** — zero declines.

## Your P2, folded in full

| hole | fold |
|---|---|
| `assembly_hash` truthiness — `None`/`False`/`0` treated as "not supplied", recomputed, accepted | exact `str` only; `""` is the **sole** "not yet computed" sentinel; `verify_assembly_provenance` refuses `""` outright (accepting it would make verification unconditional) |
| fact ids: a bare `str` exploded by `tuple()` into per-character placeholders; duplicates; unsorted | exact `tuple` (str/list/generator refused), non-empty, **duplicate-free**, **ascending** — so one fact set has exactly one hash |
| `n_splits_used=2` with 1 selected fact accepted | bounded by the fact count at construction **and** cross-checked **exactly** in `require_assembly_for` against the artifact's real `importance >= 4` base facts — the renderer mints those and the caller cannot supply them, so they are the authority |
| — (added) | containment check: every `fact_cluster_id` on the artifact's base facts must appear in the provenance's fact set, so a provenance cannot describe a different batch of facts (subset, not equality: NFR / news_context rows mint no base fact) |

`n_selected` stays derived, not stored — agreed.

## A correction to my own round-2 reasoning (verified, not assumed)

I justified the uniqueness rule by claiming two selected flashes can legitimately share a fact
occurrence, so a plain "require unique" would over-refuse. **I probed it instead of asserting it, and
I was wrong**: the same wording from two outlets clusters into ONE snapshot (`n_outlets=2`, a single
assessed entry), so P2 emits at most one assessed per placeholder and a duplicate is *structurally
impossible* on that path. The gate is therefore an **identity-stability** gate, not tolerance of a
legitimate duplicate — and the field's doc comment now says so.

Worse, my test asserting the shared case was **passing for the wrong reason**: the two probe texts
clustered into *different* families, so it never exercised the shared path at all. Replaced with
`test_multi_outlet_flash_is_ONE_fact_occurrence`, which asserts the real collapse (2 flashes → 1 fact,
`n_outlets == 2`) end to end.

## Verification — this time genuinely fail-pre-fix

Unlike round 1 (new API, so no apples-to-apples comparison was possible), these probes construct
`AssemblyProvenance` with the **same signature** as the pre-fold code. Checked out `4caf4a2`'s module
under the new tests:

```
9 failed, 23 passed
  test_falsy_assembly_hash_is_not_a_free_pass[None] / [False] / [0]
  test_empty_hash_sentinel_refused_on_read_back
  test_bare_string_fact_ids_refused
  test_duplicate_and_unsorted_fact_ids_refused
  test_split_count_cannot_exceed_the_fact_set
  test_split_count_cross_checked_against_the_artifact
  test_provenance_claiming_unrelated_facts_refused
```

All 9 fail pre-fix, all pass post-fix. (`test_multi_outlet_flash_is_ONE_fact_occurrence` passes on
both by design — it asserts a structural property, not a fix.) Post-fold: **32** P3b tests + full
`ai_research_dept` **847** green.

## Standing context for the sweep

- **The P4 split you approved holds**: P3b seals nothing on disk; P4 is the sole persistence boundary
  and still owes the five frozen obligations (require, bind, ledger `assembly_hash`, archive
  `_ARCHIVE_SCHEMA` v1→v2 with read-back verification, refusal tests). Recorded verbatim in both the
  design doc and the module docstring.
- Round-1 findings you cleared and I have not touched: PIT/no-lookahead, the P2↔P3a chain binding,
  D7 split coverage, and the `ClusterSnapshot` reconstruction (bound by P2's artifact seal, no P2
  schema change).
- The unit is NON_EVIDENTIARY with zero production callers until FORWARD_PREREG.

## Files (pin to `2ac7192`)

- https://raw.githubusercontent.com/henrydan111/quant-system/2ac7192/workspace/research/ai_research_dept/engine/news_flash_assemble.py
- https://raw.githubusercontent.com/henrydan111/quant-system/2ac7192/workspace/research/ai_research_dept/tests/test_news_flash_assemble.py
- https://raw.githubusercontent.com/henrydan111/quant-system/2ac7192/workspace/research/ai_research_dept/NF_UNIT_P3B_DESIGN.md

## Open-sweep questions (final round)

1. **Identity completeness.** Is the `AssemblyProvenance` hash body now exactly right — nothing
   missing that a future auditor would need, nothing in it that shouldn't be (e.g. is including
   `ingest_class` and `cutoff` alongside `assessed_sha`/`split_sha` redundant in a way that could ever
   disagree with itself)?
2. **Value domain.** Any remaining ordinary-base-type value that gets in and shouldn't, on any of the
   three doors (`__post_init__`, `verify_assembly_provenance`, `require_assembly_for`)?
3. **The new cross-checks.** The exact `n_splits_used == len(high-importance base facts)` equality and
   the subset containment — are those the right relations, or does either over-constrain a legitimate
   case (e.g. a fact whose base row is NFR/context, or an artifact with zero high-importance facts)?
4. **Anything in the unit as a whole** that the two prior rounds' narrower focus let through.
5. **Verdict:** SOUND-TO-PROCEED (to P4, obligations frozen) or a specific in-tier gap.
