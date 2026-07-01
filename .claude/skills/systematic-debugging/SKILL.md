---
name: systematic-debugging
description: Use when debugging unexpected behavior in this repo: failed tests, backtest/factor anomalies, engine disagreements, PIT/lookahead suspicion, suspiciously-good metrics, NaN/sign flips, coverage collapse, 0-row Tushare/Qlib joins, or any quantitative result needing a cause before a fix or claim.
---

# Systematic Debugging (quant edition)

## The Iron Law

**NO FIX, AND NO STATED CAUSE, WITHOUT ROOT-CAUSE EVIDENCE FIRST.** A symptom fix is a failure; a plausible guess presented as an answer is the §7.10 cardinal sin. Either name the dataset/script/output that proves the cause, or write `unverified — test Y resolves it`.

## Two irreversible-harm guards — never break, even mid-debug

- **PIT data:** inspect only through `pit_research_loader.py` / `qlib_windowed_features`. Never read `data/pit_ledger/*` raw or hand-roll alignment (PIT002 lint hard-error).
- **Sealed OOS:** never re-run or "reproduce" a sealed-OOS result to verify it — that can spend a holdout seal or create an illegal second attempt. Read existing artifacts / seal ledger / provenance; resume only through the orchestrator with the same `run_dir` + `step_id` and matching `request_hash` + `plan_hash`. If resume refuses, stop — never work around it with a fresh OOS run.

## Process (sequential gates — don't advance early)

A documented-contract match (vectorized-vs-event-driven dividend gap, 0-row code-format join, swapped MultiIndex, decile-vs-quintile, too-good metric) is a **hypothesis, not a cause** — still run the diagnostic that proves the mechanism.

1. **Root cause** — read the exact number/error; reproduce *without changing governance state*; check recent rebuilds; instrument factor → universe → signal → execution; trace the bad value backward.
2. **Pattern** — find a working comparable; list every difference.
3. **Hypothesis** — one hypothesis + falsification plan; test one variable; never stack fixes.
4. **Implement** — failing test first; single root fix; run the whole test file; 3-strikes → question the architecture.
5. **Verify** — normal claim: run the proving command fresh + read exit code; sealed-OOS claim: read artifacts only; state a cause only as `[claim] proven by [artifact]`.

After Phase 1, **STOP and read [reference.md](reference.md) before Phase 2** — the known-contract cases, the full per-phase steps, the Phase-2 diff checklist, and the rationalization table. Do not form, test, or implement a hypothesis until you have.
