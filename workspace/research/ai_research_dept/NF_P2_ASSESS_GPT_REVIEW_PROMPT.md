# GPT Cross-Review Request — NF integration P2 (market-wide cluster+route+assess) — Tier-2

Reviewing **one unit**: the P2 driver that clusters, routes, and assesses a day's news flashes
market-wide, consuming P1's typed-flash artifact and producing a sealed assessed-flash artifact for
the per-stock decision units (P3→P4). **Tier-2** — declared-invariant review; 2-round budget; do NOT
apply the crafted-object / dunder / adversarial-in-process-caller standard (that tier is the
sealed-decision core, a separate shipped unit). Judge against the declared invariants and the
quantitative-research principles (PIT / no-lookahead FIRST).

**Commit under review: `9ec365a`** on branch `calendar-unfreeze`.

## Context

- Offline producer → optional consumer wiring (decision B). P1 (flash typing) already SOUND.
- P2 is **wiring around existing, tested pieces**: `text_store.load_text` (PIT gate + forward
  fail-closed), `news_ingest.build_cluster_snapshots` (sealed clusters), `news_routing.route_cluster`
  over `AliasRegistry` (deterministic, alias-based, as-of cutoff), `news_cards.assess_flash`
  (verify-not-trust evidence class). The reference inputs (alias registry, industry/concept term sets)
  are **injected** so the core is testable.
- **Scope: P2 is MARKET-WIDE, not per-stock** — routing (not clustering) associates a flash to stocks;
  one flash mentions many. Per-stock selection is P3.

## Files (pin to `9ec365a`)

- https://raw.githubusercontent.com/henrydan111/quant-system/9ec365a/workspace/research/ai_research_dept/engine/news_flash_assess.py
- https://raw.githubusercontent.com/henrydan111/quant-system/9ec365a/workspace/research/ai_research_dept/tests/test_news_flash_assess.py
- Design + declared invariants: https://raw.githubusercontent.com/henrydan111/quant-system/9ec365a/workspace/research/ai_research_dept/NF_UNIT_P2_DESIGN.md
- Pieces it wires: news_routing.py (`route_cluster`, `build_alias_registry`, `AliasRegistry.resolve_codes`), news_ingest.py (`build_cluster_snapshots`), news_cards.py (`assess_flash`) — all at `9ec365a`.

## Declared invariants (review target)

1. **PIT inherited + one canonical cutoff.** `load_text` cutoff filter + forward fail-closed; the same
   `_canonical_cutoff` (microsecond-max, from P1) drives load, clustering, routing as-of;
   `build_cluster_snapshots` re-asserts `effective_at <= cutoff`; an alias listed after cutoff doesn't
   resolve.
2. **P1 binding — same identity, full coverage, fail-closed.** Consumed P1 artifact must be the exact
   (cutoff, ingest_class); its `artifact_sha256` is verified and bound into P2's artifact; every
   cluster representative's `content_hash` MUST be in the P1 typing index — a miss is a hard error,
   never a default typing.
3. **Deterministic PIT routing, no LLM.** Registry version + `content_hash` recorded so P3/P4 bind the
   routing basis.
4. **evidence_class verify-not-trust** (`assess_flash` recomputes from typing+route).
5. **Macro-routed flashes kept but flagged** (`news_render_eligible=False`; news render excludes them;
   macro seat separate).
6. **Immutable write-once persistence** (microsecond-cutoff path, first-write-wins under a lock — same
   as P1).
7. **NON_EVIDENTIARY** empty day → empty artifact.

## Disclosed simplifications (honest, not hidden — please rule on whether either blocks P2)

- **CLI reference assembly is an explicit `NotImplementedError` seam.** The testable core takes the
  alias registry / industry-term set / concept-term set injected; `_build_reference_inputs` (the CLI
  assembly from `stock_basic` as-of / SW L1 industry names / THS concept names) is wired at the first
  real offline run — it depends on live reference files (some affected by the 2026-07-13 incident) and
  per-source PIT details. All term sources are confirmed to exist. Is the injected-core boundary the
  right reviewable unit, or must the CLI assembly land in P2?
- **`coordination_fired` is inert in P2 v1.** P2 calls `assess_flash` without a coordination flag, so
  the NFC coordination/pump negative-evidence path is not exercised (`coordination_flag` needs
  `structured_backing_status` from the event store — a §6 wiring). Is deferring coordination to its own
  unit acceptable, or does P2 need it now?

## Self-review (done)

Verdict: clean for GPT. §3.2 PIT (inherited gate + same canonical cutoff + as-of registry + re-assert,
tested via alias-after-cutoff); reuse-before-reinvent (reused load_text / build_cluster_snapshots /
route_cluster / assess_flash / _canonical_cutoff / seal_hash / load_typed_flash_artifact — no new
routing/clustering/typing); no factor/registry/ledger invariant touched. Both simplifications above are
disclosed, not hidden. Tests: 10 P2 + full ai_research_dept 757 green.

## Review questions

1. **PIT:** any path where a post-cutoff flash or a post-cutoff alias could enter the assessed set or
   route to a stock? Is routing genuinely as-of the same canonical cutoff as load+cluster?
2. **P1 binding:** is the (cutoff, ingest_class) + full-content_hash-coverage check sufficient to
   guarantee P2 assesses exactly the P1-typed population, with the consumed SHA bound so P3/P4 can
   verify the chain?
3. **Representative-member approximation:** typing+routing use `members[0]` of each cluster. Is that a
   correctness risk (a cluster whose members mention different stocks), or acceptable given members
   share a wording family? If a risk, is it P2's to fix or a routing-semantics unit of its own?
4. **The two disclosed simplifications:** does either (CLI seam; inert coordination) block P2, or are
   they correctly deferred?
5. **Determinism / persistence:** any nondeterminism in the assembled artifact, or a persistence gap
   beyond what P1's contract already covers?
6. **Verdict:** SOUND-TO-PROCEED (to P3) or CHANGES-REQUIRED with specific declared-invariant gaps.
