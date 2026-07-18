# GPT §10 DESIGN review — adapter phase (interface + A01 reference unit)

Independent GPT‑5.5 Pro reviewer. This is a DESIGN-STAGE review (no implementation yet), per the
"threat-model-before-implementation" discipline for fetch-path code. The contract sign-off gate is open;
this designs the adapters that turn a signed contract into a fetched-and-verified raw store, with the
real Tushare call §13-gated.

Repo `https://github.com/henrydan111/quant-system` · Branch **`calendar-unfreeze`** · HEAD after push.
Design: `…/workspace/research/calendar_unfreeze/ADAPTER_PHASE_DESIGN.md` (read this first — full).
Grounding: `…/scripts/recovery_ledger.py` (`fetch_page` call contract at ~395; plan-row `_PLAN_REQUIRED`
at ~165), `…/scripts/raw_recovery_coordinator.py` (`RecoveryPaths` ~427, `freeze_request_plan` ~1292,
`resolve_population` ~990, `cmd_fetch` stub ~1550), `…/workspace/research/calendar_unfreeze/RAW_STORE_RECOVERY_PLAN.md`
(§ adapter requirements: write-surface allowlist, no-default paths, drive class methods not main(),
E:-write-denied tests, the pre-fetch test matrix list).

## The design in one paragraph
The adapter is a PURE fetch function (`call() -> DataFrame`, in memory); the ledger + no-follow broker own
ALL persistence under `staging_data`, so the verified E: leak points (import-time handlers, StorageManager
writes, `main()` reference downloads) are structurally avoided, not patched. Three pieces: a declarative
`AdapterSpec` (partition_of / receipt_output_of / tushare_call / merge), a plan-builder
(resolve_population → plan_rows), and a fetch-orchestrator (`run_family`) that freezes the plan and
page-drives each request through `ledger.fetch_page(call)` then `verify_request`/`confirm_empty`. The §13
gate is the `call_provider` seam: a `synthetic_call_provider` (canned frames, no tushare) drives 100% of
adapter logic in tests; a `live_call_provider` binds `fetcher.fetch_*` and is constructed ONLY with an
explicit user §13 authorization (no fetcher → no possible call). A01 (`market/daily` = daily+daily_basic+
adj_factor, merged per trade_date) is the concrete first unit; fan-out is a separate later unit.

## Self-review (mine, before you)
Checked §3 invariants: PIT — adapters re-fetch RAW only, alignment stays downstream, fina_mainbz's
formal-PIT quarantine is preserved as a promotion precondition (not lifted here); §3.4 governance — the
§13 gate + ledger-owns-persistence + write-surface allowlist align with the freeze plan; §6.1 — adapters
drive class methods with the doc already read/signed. Threat model frozen (trusted: ledger/broker/contracts/
RecoveryPaths; untrusted: the call RESULT [ledger hashes it], the fetcher-as-driver [paths injected], the
vendor schema [checked vs required_fields]; in-scope: E: leaks/path-defaults/truncation/crash-resume/
empties/schema-drift/mid-flight contract edit; out-of-scope per the 2026-07-16 user directive: mid-op
adversarial races). Verdict: clean for design review; three open questions below are genuine.

## Review questions
1. **Trust boundary — "adapter never touches disk; ledger owns all persistence."** Is this the right
   boundary? Does any family need adapter-side staging BEFORE the receipt (e.g. a transform that can't be
   expressed as a pure fetch), or is pure-fetch-in-memory + ledger-owned-write correct for all 30?
2. **§13 chokepoint — the `call_provider` seam.** Is gating at "construct the fetcher only with an
   explicit §13 authorization" the right chokepoint, or should the token gate sit LOWER (inside
   `fetch_page`) so even a mis-wired orchestrator can't call the vendor? Trade-offs?
3. **A01 multi-source merge timing.** 3 leg receipts + merge at CONSOLIDATION vs merging at fetch. Given
   `assert_multi_source_merge_coverage` already validates the 3 legs cover the same population, is
   per-leg-receipt + consolidation-merge correct, or does merging-at-fetch better preserve row identity?
4. **Pagination-drive correctness.** The orchestrator loop stops on `n < page_limit` (offset) or after
   page 1 (single). The ledger separately enforces the trailing-empty rule for an exact-`page_limit` last
   page. Is the split (orchestrator stops / ledger proves terminal) sound, or can a page exactly equal to
   `page_limit` at the true end desync them?
5. **Write-surface monitor.** Is an allowlist (run-root + api-lock namespace only) over a full synthetic
   A01 run a sufficient proof of no-E:-leak, given the fetcher construction is the one residual surface?
6. **Anything mis-scoped for a first review unit** — should A01 alone be the unit, or must a per-stock
   (income) and an event (top_list, `row_payload_digest`) representative be in the same unit to lock the
   interface before fan-out?

Return per finding: severity, whether it blocks implementation, and the concrete change. This is a design
gate — approving it FREEZES the interface + threat model against which the A01 implementation is then
reviewed.
