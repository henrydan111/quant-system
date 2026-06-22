# Systematic Debugging — reference

Detail for the lean [SKILL.md](SKILL.md). Read before Phase 2. The two irreversible-harm guards (no raw `pit_ledger` reads; never re-run sealed OOS) live in SKILL.md and bind even before this file is read.

## Known-contract cases — a match is a hypothesis, not a cause

To state the cause, name the diagnostic that proves the mechanism; otherwise write `unverified — test Y resolves it`.

- **Vectorized vs event-driven gap on a dividend-paying book** → documented contract, not automatic proof: vectorized uses raw `$close` price return; event-driven credits post-tax cash dividends + bonus shares on ex-date. Prove by reconciling the run's corporate-action contribution.
- **0-row / 0-match join** → first hypothesis is code format: Tushare `000001.SZ` vs Qlib `000001_SZ`. Prove with key samples/counts before claiming empty data.
- **`groupby(level=0)` ranks by date** → first hypothesis is swapped MultiIndex (`D.features()` is `(instrument, datetime)`). Prove level names/order first.
- **Decile LS-Sharpe differs from historical evidence** → first hypothesis is group-count: current standard is 10 groups; pre-2026-06-11 evidence may need `n_quantiles=5`.
- **A metric implausible for its universe/horizon** (e.g. gross 5d sub-universe LS Sharpe far above peers, sign-perfect OOS, IC outside historical scale) → contamination/lookahead alarm. Untrusted until PIT canaries and label-boundary checks pass; for OOS evidence, use only legally existing sealed artifacts/provenance or the proper promotion gate — never spend OOS just to debug a suspicious metric.

## The five phases — full steps

### Phase 1 — Root-cause investigation
1. Read the actual number/error — exact value, stack line, file. Not the gist.
2. Reproduce deterministically **without changing governance state**. Normal runs: pin `run_dir`/seed/window/provider build/calendar policy/execution profile. Sealed-OOS runs: use existing artifacts or orchestrator resume only. Resume must use the same `run_dir` + `step_id` with matching `request_hash` + `plan_hash`; if resume refuses, stop — never start a fresh OOS run or work around the refusal.
3. Check recent changes (`git diff`): did the ledger/provider rebuild, calendar policy, or field registry change? A factor value can change retroactively on a ledger rebuild.
4. **Instrument sanctioned boundaries only.** Log inputs/outputs for **factor → universe → signal → execution**. For PIT data, inspect through `pit_research_loader.py` or `qlib_windowed_features` — never read `data/pit_ledger/*` raw or hand-roll alignment. The failing layer is where good-in / bad-out flips.
5. Trace the bad value backward to its origin.

### Phase 2 — Pattern analysis
1. Find a *working* comparable (a passing factor, the other engine, a prior green run); read it completely.
2. List **every** difference: code format, MultiIndex level names/order, raw vs adjusted price basis, `deal_price`, execution profile id/hash, `CostConfig`, slippage preset, provider build, calendar policy, `n_quantiles`, horizon, universe mask, rank scope, `Ref(...,1)` wrapping, lag-0 vs lag-1 loader, seal key/run identity.

### Phase 3 — Hypothesis and testing
1. Form **one** hypothesis: "X is root cause because Y." Label it a hypothesis with a falsification plan — never the answer.
2. Test minimally — **one variable**. Example: a temporary diagnostic script/monkeypatch that no-ops `CorporateActionHandler.process` to isolate dividend contribution; never commit the no-op as a fix.
3. Confirm before proceeding; if wrong, form a new hypothesis — don't stack fixes. "I don't understand X yet" is valid.

### Phase 4 — Implementation
1. Write a **failing test** first (the `tests/` pattern that pins the invariant).
2. Implement a **single** fix at the root cause only.
3. Run the **WHOLE test file(s)** that drive the changed gate/handler, not just the new test.
4. **3-strikes:** <3 failed attempts → back to Phase 1; ≥3 → stop, the design is unsound, raise it.

### Phase 5 — Verification before completion
No completion or cause claim without evidence.
1. **Normal code/test claim:** run the full proving command in this session, read the complete output + exit code, then state the claim with the command/output.
2. **Sealed-OOS / spend-limited claim:** do **not** re-run to verify. Read the existing sealed artifact, seal ledger, provenance JSON, and run metadata. Resume only through the orchestrator with the same `run_dir` + `step_id` and matching `request_hash` + `plan_hash`; if resume refuses, stop — never work around it with a fresh OOS run.
3. **Cause claim:** state only as `[claim] proven by [dataset/script/output + exit code or artifact hash]`. No artifact, no claim.

## Rationalizations that do not authorize skipping Phase 1

| Excuse | Required response |
|---|---|
| "It's probably dividends/costs/survivorship." | Mark HYPOTHESIS; run the isolating diagnostic. |
| "Just shift one more day." | Stop; identify the wrong visibility anchor; add a PIT test before changing lag. |
| "0 rows means no data." | Prove code-format keys and join samples first. |
| "OOS Sharpe 7 — ship it." | Contamination alarm; verify PIT/OOS provenance + deployment gate. |
| "One more fix." | At attempt 3, stop and question architecture. |
| "Looks fixed." / "Stop guessing." | Phase 5 evidence or no claim. |
