# GPT Cross-Review Request — B1/B2 forward text-pull ops hardening — Tier-3 (single pass)

Reviewing **one unit**: operational hardening of the daily text pull that feeds the
`mvp_pool_rerank_v2` forward runner's pre-registered text gates, plus a read-only daily
gate rehearsal. **This unit must be gate-semantics-neutral** — that neutrality is the
main thing to review.

## ⚠ FROZEN REVIEW TIER — Tier-3

Per CLAUDE.md §10 tiering: workspace ops scripts — self-review + **at most one GPT pass**.
No adversarial-caller / crafted-object analysis; findings at that bar = tracked notes only.
Verdict vocabulary: SOUND / CHANGES REQUIRED (+ tracked notes).

**Commit under review: `30780a2`** on branch `calendar-unfreeze`.

## Quantitative-research principles first (PIT / no-lookahead)

- The forward experiment is PRE-REGISTERED and frozen ([FORWARD_PREREG.md](https://raw.githubusercontent.com/henrydan111/quant-system/30780a2/workspace/research/mvp_pool_book/FORWARD_PREREG.md)):
  config/prompts/gates/judgment rules untouchable; ops repair is the sanctioned channel
  (§3), logged in OPS_AUDIT_LOG.md.
- The runner's two text gates are the protected surface:
  `check_pull_manifest` (latest full pull ok+fresh+per-source ok) and
  `check_text_coverage_history` (every calendar day × required source in the 30d dossier
  lookback covered by an ok manifest) — in
  [run_forward_cycle.py](https://raw.githubusercontent.com/henrydan111/quant-system/30780a2/workspace/research/mvp_pool_book/run_forward_cycle.py)
  (lines ~210-237, ~536-621). **This unit does not edit that file.**

## What changed (the unit)

1. **B1 — [workspace/scripts/text_daily_pull.py](https://raw.githubusercontent.com/henrydan111/quant-system/30780a2/workspace/scripts/text_daily_pull.py)** (rewrite of the pull loop):
   - per-source in-run circuit breaker (>=2 consecutive exception failures → skip that
     source's remaining days this pass, still recorded as failures);
   - end-of-run retry pass: one sequential re-attempt per exception/skipped (source, day)
     after a cooldown; truncated days (page-cap) are NOT retried;
   - additive manifest audit fields: `attempts`, `breaker_events`, `retry_pass`,
     `partial_run`, `sources_pulled` (existing fields unchanged);
   - `--sources` targeted manual re-pull: a partial run **never writes
     pull_manifest_latest.json** and un-attempted sources get status `not_attempted`
     (never `ok_*`);
   - exit contract preserved: ANY residual failure → non-zero (B5).
2. **B2 — [workspace/scripts/text_coverage_preflight.py](https://raw.githubusercontent.com/henrydan111/quant-system/30780a2/workspace/scripts/text_coverage_preflight.py)** (new, read-only):
   rehearses "if today were the activation day, would the text gates refuse?" by importing
   and calling the runner's own gate functions verbatim (a test pins that it has NO local
   reimplementation); on failure writes `logs/text_coverage_alert_<CN-date>.flag`
   (recovered same-day run clears it) + exits 1. Chained (subprocess, exit-code-isolated)
   after full script pulls only.
3. Tests: [test_text_daily_pull_retry_and_breaker.py](https://raw.githubusercontent.com/henrydan111/quant-system/30780a2/tests/text/test_text_daily_pull_retry_and_breaker.py) (6) +
   [test_text_coverage_preflight.py](https://raw.githubusercontent.com/henrydan111/quant-system/30780a2/tests/text/test_text_coverage_preflight.py) (6) +
   pre-existing [test_daily_pull_fails_on_partial_source_failure.py](https://raw.githubusercontent.com/henrydan111/quant-system/30780a2/tests/text/test_daily_pull_fails_on_partial_source_failure.py) (3, unmodified, green) +
   forward harness test file — **40 green** total.
4. Audit entry: [OPS_AUDIT_LOG.md](https://raw.githubusercontent.com/henrydan111/quant-system/30780a2/workspace/research/mvp_pool_book/OPS_AUDIT_LOG.md)
   (includes the first real preflight's FINDING: daily pulls never ran for real; 07-09+
   coverage gap; recovery path recorded).

## Declared invariants (the review target)

1. **Gate-semantics neutrality**: both runner gates read only
   `ok/run_ts/window/source_status/failures` (+ `bootstrap/coverage_by_day`); every new
   manifest field is additive; a partial run can never (a) overwrite the latest manifest
   the freshness gate reads, nor (b) earn coverage credit for a source it did not attempt.
2. **No silent success**: breaker-skipped and truncated (source, day) pairs stay failures
   unless a retry genuinely succeeds; exit non-zero on any residual failure.
3. **Tushare discipline (§6.1)**: strictly sequential; breaker reduces hammering during
   outages; retry adds at most one extra attempt per failed pair after a cooldown.
4. **Preflight is read-only rehearsal**: verbatim reuse of the runner's gates (drift
   impossible by construction); it writes only its own status/flag files whose names can
   never match the gate's `pull_manifest_*.json` glob... (note: `coverage_preflight_latest.json`
   does not match; the alert flag lives outside the manifest dir).

## Review questions

1. Any path where the new manifest semantics could make the coverage gate credit a day/source
   that was not actually pulled ok (e.g. `not_attempted` string interactions, partial-run
   manifests being window-form, retry-pass bookkeeping)?
2. Any way a partial (`--sources`) run weakens the latest-manifest freshness gate — including
   operator-error sequences (partial run after a failed full run, etc.)?
3. Does the retry/breaker logic ever convert a should-fail day into silent success, or mask
   truncation?
4. Preflight: any divergence channel between rehearsal and the real gate despite verbatim
   reuse (e.g. config values read differently, decision_time semantics, tz)?
5. Anything in the §6.1 Tushare-safety direction (sequencing, backoff) made worse?

## Self-review

Clean for GPT: §3 invariants untouched (no PIT/seal/provider surface); gates un-edited and
their test files run whole (40 green); the two initially-suspicious findings during my own
mechanical verification were adjudicated as my re-implementation gaps, not archive/gate
defects. No OOS reference of any kind in this unit.
