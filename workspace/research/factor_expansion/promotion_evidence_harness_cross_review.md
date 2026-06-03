# DESIGN Cross-Review (for GPT) — the promotion-evidence reproduction harness (+ C2)

You GO'd (Conditional) promoting the 6 sealed-OOS winners straight to `approved` (C2), with a
must-fix: build a real promotion-evidence reproduction harness, not a hand-built blob. Investigation
then found the deeper issue: **the gate's 7 required canaries have NO producer** — they exist only
in the gate (consumer) and in test fixtures. So C2's true prerequisite is **building a reusable
promotion-evidence producer**. This reviews that harness design. No repo access — all embedded.
Attack the canary fidelity and the reproduction legitimacy; a NO-GO with specifics beats a GO.

## 0. The gate's hard requirement (verified in `release_gate.py`)
`evaluate_promotion_artifact` accepts only if ALL are present + `"passed"` (fail-closed on any
missing key), source ∈ {qlib_windowed_features, joinquant_native_pit, audited_pit_source},
`dirty_tree=False`, and `git_sha == current_git_sha`:
```
independent_reproduction.source, unsafe_pit_dates_lint, synthetic_lookahead_canary,
restatement_canary, q0_canary_multiperiod, q0_canary_stateful_restatement,
q0_canary_missing_field, availability_assertion, live_provider_parity, dirty_tree, git_sha
```
**Nothing in src/scripts/workspace produces these** (only `run_daily_qa` emits the 1 lint; the rest
appear only as test fixtures). That is the gap this harness fills.

## 1. Harness architecture (2 new modules)
**`src/data_infra/pit_canaries.py`** — 6 canaries, each a pure function over a **controlled synthetic
ledger fixture** → `"passed"`/`"failed"`. Each PACKAGES already-tested correctness logic (it does
NOT re-implement it):

| canary | attests | reused tested logic |
|---|---|---|
| availability_assertion | `effective_date > disclosure_date` STRICTLY | `strictly_next_open_trade_day` (test_pit_backend.py) |
| restatement_canary | late prior-quarter restatement updates the derived value at its effective date, not before | `derive_single_quarter_value` (test_flow_single_quarter_derivation_tracks_late_revision) |
| q0_canary_multiperiod | stateful-q0 multi-period uses best-known visible state | pit_alignment_core stateful-q0 |
| q0_canary_stateful_restatement | stateful-q0 under restatement | same kernel, restatement fixture |
| q0_canary_missing_field | per-field fallback when the direct quarter misses a field | canonicalize_report_variants |
| synthetic_lookahead_canary | a value disclosed at D is NOT visible until `effective_date > D` (inject-and-confirm-blocked) | strictly_next_open + visible-period walk |

Each canary FAILS on an injected-leak fixture (the fail-closed proof, mirroring the Phase-7 leak test).

**`src/research_orchestrator/promotion_evidence.py`** — `build_promotion_evidence(...)` runs: the 6
canaries + `unsafe_pit_dates_lint` (the existing `lint_no_unsafe_pit_dates.py`) + `live_provider_parity`
(the existing lag-0/lag-1 `test_pit_loader_provider_parity`, as `run_daily_qa` does) + the sealed OOS
re-run (§2) + clean-tree/git-sha capture → assembles the artifact → **self-verifies** via
`evaluate_promotion_artifact(artifact, current_git_sha=HEAD)`, raising if not eligible. So it can only
ever emit a gate-passing artifact, and only on a clean committed tree.

## 2. The sealed-OOS reproduction
The old `run_sealed_oos.py` is `historical_investigation`/`formal_research_allowed:false` and installs
NO `ResearchAccessContext`, so `qlib_windowed_features` did not enforce the window. The harness instead
loads the **frozen 13-factor set verbatim** (from `oos_frozen_topset.json`, commit `73d556a`) — **no
reselection** — installs a `ResearchAccessContext` (stage=`oos_test`, allowed window = 2021-01-01…
2026-02-27), computes via `qlib_windowed_features` (→ `source=qlib_windowed_features`), and recomputes
the OOS ICIR/LS-Sharpe for the 6 as the reproduction evidence. This reproduces an **already-spent,
pre-registered** window (selection was IS-only + frozen by a written rule before the one-time OOS) —
verification, not new selection.

## 3. C2 onboarding (after a passing artifact)
Catalog +6 `Ref`-wrapped exprs (147→153 base / 171→177 surface; default `get_factor_catalog()` stays
111) with PIT-parser + field-gate + tests; sync→draft; `set_status('approved', current_git_sha=HEAD,
promotion_evidence=<artifact>)`; persist `sealed_oos_winners_promotion.json` + a ledger event +
`source_run_id`; `set_expected_direction` from the **signed OOS ICIR** (not the CSV column).

## 4. The questions I most want you to attack
1. **Canary fidelity — the crux.** Each logic canary (lookahead/restatement/q0) runs on a SYNTHETIC
   fixture and proves the *kernel* is correct; the LIVE pipeline's correctness is covered separately by
   `live_provider_parity` (loader vs provider agree on real data). Is "synthetic-fixture logic canaries
   + live-provider parity" a sufficient attestation for an `approved`-grade write, or is there a gap a
   **live-data canary** would close (e.g. a live-provider bug a synthetic fixture can't exercise)? This
   is the decision I'm least sure of.
2. **Reproduction legitimacy.** Is re-running the *same already-spent* 2021–2026 window (frozen set, no
   reselection, formal sealed path) a legitimate `approved`-grade reproduction, or circular? My claim:
   legitimate — the OOS was spent once under a pre-registered IS-only freeze; reproducing it through the
   formal chokepoint verifies the number was producible the sanctioned way. Counter-argument?
3. **"Package tested logic" vs re-implement.** Is reusing the `test_pit_backend` correctness logic
   inside the canaries sound, or does that risk the canary passing because it shares code with the thing
   it attests (tautology)? (My view: the canary asserts an OBSERVABLE property — a future-dated value is
   not visible — on a fixture with a known-correct answer; it's not asserting "the code equals itself.")
4. **Fail-closed completeness.** The harness self-verifies via the gate and refuses on dirty tree / any
   failing canary / missing key. Any path by which it could emit a passing artifact while the pipeline
   is actually unsafe?
5. **Scope:** the harness is a net-new formal capability that unblocks ALL future `approved`s. Build it
   now as designed, or is there a smaller sufficient version?

## 5. Verdict requested
GO to build the harness as designed (with any required changes — e.g. "add a live-data canary",
"module X belongs in Y"), or NO-GO with the specific soundness gap. Build arc: harness + tests →
review → C2 → dry-run → temp validation → live `approved` write behind explicit approval on a clean tree.
