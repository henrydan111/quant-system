# GPT 5.5 Pro RE-review #6 — Phase 5-C (post-REWORK-5)

Status: ready to send. Branch `calendar-unfreeze` HEAD `3d2ac0f`. Raw links pinned to the commit sha; embedded delta authoritative.

---

```text
ROLE
Senior reviewer for an A-share quant system where research validity outranks code that runs. You have
reviewed Phase 5-C (the unattended daily raw job) six times. Re-review #5 (HEAD d9b04b0) returned
REWORK: the official battery passed (431 green) but INDEPENDENT PROBES reproduced 3 Blockers — the
fixes were too shallow (the env-BOOLEAN was removed but the env-DIRECTORY QUANT_LOCK_DIR stayed
forgeable; a SECOND fillna(1.0) path survived plus a settable env escape; the raw manifest covered only
6 of 27 consumed datasets). This RE-REVIEW #6 verifies the deeper closure. The daily job keeps the RAW
layer current between the human-gated monthly formal bumps and must NEVER touch the Qlib provider/
calendar. spent_oos_end stays frozen at 2026-02-27; the post-freeze window is born sealed.

REPO https://github.com/henrydan111/quant-system  (branch calendar-unfreeze, HEAD 3d2ac0f)
Files (raw, pinned):
- tushare_lock (immutable lock dir + isfinite spacing): https://raw.githubusercontent.com/henrydan111/quant-system/3d2ac0f/src/data_infra/tushare_lock.py
- pit_backend (shared adj-factor guard, both paths): https://raw.githubusercontent.com/henrydan111/quant-system/3d2ac0f/src/data_infra/pit_backend.py  (see _require_valid_adj_factor, _load_price_frame, _normalize_daily_partition)
- daily updater (shared frame validator + 100% adj): https://raw.githubusercontent.com/henrydan111/quant-system/3d2ac0f/src/data_infra/pipeline/update_daily_data.py
- daily ops (provider_floor + attempt + compute/persist): https://raw.githubusercontent.com/henrydan111/quant-system/3d2ac0f/src/data_infra/pipeline/daily_ops.py
- daily orchestrator (attempt-bound heartbeat + defer code): https://raw.githubusercontent.com/henrydan111/quant-system/3d2ac0f/scripts/daily_raw_job.py
- watchdog (latest-attempt + shared floor): https://raw.githubusercontent.com/henrydan111/quant-system/3d2ac0f/scripts/daily_job_watchdog.py
- monthly bump (full-readset manifest + CAS gate): https://raw.githubusercontent.com/henrydan111/quant-system/3d2ac0f/scripts/monthly_calendar_bump.py  (see _full_raw_manifest, _verify_raw_manifest, phase_publish)
- task manager (typed export + rollback): https://raw.githubusercontent.com/henrydan111/quant-system/3d2ac0f/scripts/register_daily_raw_task.py
- PRO001 lint (blanket tushare-import ban): https://raw.githubusercontent.com/henrydan111/quant-system/3d2ac0f/scripts/lint_no_bare_pro.py
- tests: https://raw.githubusercontent.com/henrydan111/quant-system/3d2ac0f/tests/data_infra/test_daily_update_5c.py , https://raw.githubusercontent.com/henrydan111/quant-system/3d2ac0f/tests/data_infra/test_pit_backend.py , https://raw.githubusercontent.com/henrydan111/quant-system/3d2ac0f/tests/data_infra/test_monthly_calendar_bump.py
Self-review (round 7, per-finding table + B3 residual): workspace/research/calendar_unfreeze/PHASE5C_SELF_REVIEW.md

HOW EACH BLOCKER + MAJOR FROM REWORK-5 WAS CLOSED

Blocker 1 (lock namespace forgeable via QUANT_LOCK_DIR): the env override is REMOVED — _LOCK_DIR is a
fixed immutable project-root path, resolved with no ambient env read. A process pointing QUANT_LOCK_DIR
at a different directory no longer acquires a different-namespace lock. Tests inject isolation via the
module attribute (monkeypatch _LOCK_DIR; a spawned holder reassigns tl._LOCK_DIR in its own code), never
a production-readable env var. Test: a live holder + the parent WITH QUANT_LOCK_DIR forged elsewhere
still contends on the same lock and times out.

Blocker 2 (missing adj_factor -> 1.0, two paths + env escape): the QUANT_ALLOW_UNIT_ADJ_FACTOR escape is
GONE, and BOTH raw-consuming sites (_load_price_frame AND _normalize_daily_partition, the second fillna
you found) now route through one _require_valid_adj_factor that raises BuildGateError on a missing
column / null / non-numeric / NON-POSITIVE value. No production default; a legacy repair would be a
separate audited workflow. Tests cover null / non-positive / missing-column (the last even with the old
env var set — it is ignored).

Blocker 3 (provider not bound to the complete input cut): _full_raw_manifest now hashes the builder's
ACTUAL read set — every DATASET_SPECS dataset (27, incl. fundamentals/income/statements) PLUS every
reference file — snapshotted as a FIXED file list (path, sha256, size) under the raw lock at build time.
_verify_raw_manifest re-hashes exactly those listed files (not a re-glob, so forward daily progress after
target_end can't false-fail). phase_publish now (a) refuses unless the live provider_build/policy is
STILL the report's parent (compare-and-swap) and (b) re-verifies the full manifest, all under the raw
lock, fail closed. Test: mutating an income file changes the root AND fails verify.
  RESIDUAL — I am DISCLOSING this rather than doing it blind, and asking for your call: (i) binding the
  manifest root INTO the published provider_build.json + making it required by provider_build.schema.json
  touches the LIVE provider_build.json (which lacks the key today — a hard-required field would make the
  manifest loader reject the live provider) + the manifest loader, needing a migration; (ii) replacing
  the MANUAL §13 swap (_depth9_safe_publish.py + _rebind_approvals) with ONE automated atomic transaction
  (verification and os.replace inseparable) touches the live 241GB formal provider and CANNOT be
  integration-tested in this session (there is no staged build to publish). phase_publish is currently a
  FAIL-CLOSED gate (parent CAS + full re-verify; refuses on any drift) and the handoff explicitly records
  that the swap must re-run the verify atomically before os.replace. I propose landing this and doing the
  automated-atomic-publish + schema binding as a focused Phase 5-B follow-up when a staged build is
  available to test against, rather than blind-editing the most load-bearing artifact. Is that acceptable
  (ship with a tracked follow-up), or do you consider the non-atomic manual swap a hard blocker that must
  be automated now despite being untestable here?

Major 1 (MarketDataError certified malformed sessions): one shared _validate_endpoint_frame (schema +
target-date + natural-key uniqueness), full daily OHLCV schema, adj_factor coverage == 100% of priced
codes with a positive value, post-merge daily_basic payload coverage + output-key uniqueness. Tests: the
wrong-date daily_basic, duplicate adj keys, and 98%-with-nulls probes all raise.
Major 2 (stale heartbeat certified a failed run): an attempt record (uuid) is written and the prior
heartbeat invalidated BEFORE any mutation; the success heartbeat binds attempt_id + provider ids + floor
+ manifest digest; the watchdog requires the LATEST attempt certified (a stale heartbeat with an older
attempt_id can't green a failed run). provider_floor is a shared helper used by both the job and the
watchdog; floor==expected greens (provider current), floor>expected reds (poisoned).
Major 3 (contention reported as success): the soft-skip returns EX_TEMPFAIL (75) so RestartOnFailure
retries in ~30min; a deferral record (not an alert) is written.
Major 4 (lint missed aliases): PRO001 bans EVERY `import tushare` / `from tushare` outside the fetcher
(defeating `import tushare as ts; make = ts.pro_api; make()`) + flags the introspection string literals
(_real/_base_sleep/__closure__) passed to any call.
Major 5 (rollback could delete a working task): _task_exists uses LIST membership (not a localized
error string); _export_task returns typed ABSENT/PRESENT/QUERY_FAILED; the installer aborts BEFORE any
mutation on QUERY_FAILED, exports both tasks, and a Password prev-task without old credentials is a
distinct fatal restore-failure.
Minors: rate-spacing rejects NaN/non-finite (isfinite + range) and writes state atomically; the monthly
bump's _open_trading_days routes through the canonical _validate_trade_cal + dedup.

VERIFICATION
430 tests pass + 9 skipped across tests/data_infra/ (incl. namespace-not-env-forgeable, adj null/
non-positive/missing-column, the three M1 probes, latest-attempt + provider-current watchdog, NaN-state
spacing, full-manifest income-mutation). PRO001 lint clean + positively catches all four bypass probes.
10 files compile + 4 script import-smoke. C-4 scheduled-task registration stays HELD for the operator.

RE-REVIEW QUESTIONS
1. Blocker 1: is a fixed immutable _LOCK_DIR + attribute injection for tests the right shape, or do you
   want config-central resolution for a shared-volume deploy (fail-closed on mismatch)? Any remaining
   ambient path that splits the namespace?
2. Blocker 2: does routing both sites through _require_valid_adj_factor (raise on missing/null/non-
   positive, no env escape) fully close it? Is rejecting non-positive correct (are there any legitimate
   zero/negative adj_factor rows in A-share Tushare)?
3. Blocker 3 + the RESIDUAL question above: is the full-readset manifest + parent-CAS + full re-verify
   gate sufficient to SHIP with a tracked follow-up for the atomic-swap + schema binding, or a hard
   blocker? If a blocker, what is the minimal safe automated transaction given the swap/rebind are
   existing proven scripts and I cannot test a real publish here?
4. Major 1/2: is adj coverage == 100% the right bar (vs enumerated exceptions)? Is the attempt-id +
   provider-id + digest heartbeat binding cross-run safe, and is floor==expected -> green (no heartbeat
   required) correct after a monthly publish?
5. Any NEW hole from this round: the shared _require_valid_adj_factor on the normalize path (does it
   change any legitimate build output?), the manifest's whole-tree hash cost, the watchdog's dependence
   on the attempt record, the M5 CSV list-membership parse.

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending code quoted + exact fix. Map every
  Blocker to the principle/invariant it violates.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk.
```
