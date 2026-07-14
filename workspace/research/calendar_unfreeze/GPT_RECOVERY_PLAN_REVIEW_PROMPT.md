# GPT 5.5 Pro RE-review #4 — raw-store RECOVERY design (plan v5 + coordinator v3.1, post re-review #3 REWORK)

Status: ready to send. Branch `calendar-unfreeze`, artifacts pinned to commit `dac4db2`. Still NO fetch; adapters still unbuilt (contracts-first).

**Self-review (§10, done):** your three probes reproduced against the last pin, then pinned as tests against v3.1 — the broken junction (`CreateJunction` then delete the target; `Path.exists()` returns False and skipped it — now `os.lstat` catches it), the cross-endpoint canary, and the `b"DATA"`-as-parquet verify (both were weaknesses in MY committed tests — the new ledger opens the parquet independently so `b"DATA"` raises, and requires a same-endpoint verified-nonempty canary). B1 re-examined: since the live provider's report_rc bins survived, recovery doesn't rebuild them — the parity/first-seen contradiction dissolves (no re-anchoring into sealed bins). Driver facts re-verified in code (download_fundamentals -> pro.income/pro.balancesheet standard, L189/L275; cashflow/forecast/holder per-stock init_factor; report_rc doc cap 3000 at doc 292 L4; author_name in the canonical key at pit_backend L723; top_inst/block_trade baseline dup counts from the manifest). 18-test coordinator battery + 52 green; no Tushare call. Verdict: clean for GPT.

---

```text
ROLE
Senior reviewer for an A-share quant system where research validity outranks code that runs. Recovery
context: an accidental `git worktree remove --force` deleted 21/27 raw provider-input datasets
(~77.5M rows) through junctions; live provider + reference/ + universe/ intact; recovery = C:-staged
re-fetch. Re-review #3 (commit ee94dc5) returned REWORK: B1 the mandated f93cb9d2 builder ignores
recovery first-seen (report_rc backdating), B2 the ledger certified a different request/arbitrary
bytes/false empty, B3 a broken junction was accepted + TOCTOU, M1 matrix still factually wrong, M2
scaffold/validator schema drift + placeholder-passable + cmd_plan always 0, M3 promotion quiescence/
resume gaps, minors (rate_limit_backoff non-finite, contract test writes to the live E: mirror). This
RE-REVIEW #4 verifies the fold. Fetch remains REFUSED; adapters unbuilt pending your verdict + signed
contracts.

REPO https://github.com/henrydan111/quant-system  (branch calendar-unfreeze, commit dac4db2)
- Plan v5:        https://raw.githubusercontent.com/henrydan111/quant-system/dac4db2/workspace/research/calendar_unfreeze/RAW_STORE_RECOVERY_PLAN.md
- Coordinator v3.1: https://raw.githubusercontent.com/henrydan111/quant-system/dac4db2/scripts/raw_recovery_coordinator.py
- Coordinator battery (18): https://raw.githubusercontent.com/henrydan111/quant-system/dac4db2/tests/data_infra/test_raw_recovery_coordinator.py
- Contract scaffold (schema-aligned, unsigned): https://raw.githubusercontent.com/henrydan111/quant-system/dac4db2/workspace/configs/recovery_endpoint_contracts.yaml
- Throttle (isfinite base_sleep + rate_limit_backoff): https://raw.githubusercontent.com/henrydan111/quant-system/dac4db2/src/data_infra/tushare_lock.py

HOW EACH FINDING WAS FOLDED

B1 — DISSOLVED, not chosen: the live provider's report_rc bins SURVIVED, so recovery does NOT rebuild
report_rc provider fields. (a) intact live $report_rc__* bins preserved as legacy evidence; (b)
re-fetched report_rc RAW is a NEW generation (today's content + per-row raw_fetch_ts) feeding only
FORWARD ledger rebuilds under current first-seen-safe code (effective_date >= raw_fetch_ts); (c)
report_rc EXCLUDED from the exact full-bin parity oracle — neither backdating (we never re-anchor bulk
rows into the sealed bins) nor divergence-vs-parity applies. Two explicit C-side builds: a
legacy-parity DIAGNOSTIC build on f93cb9d2 (deterministic-anchoring datasets only; report_rc +
raw_fetch_ts-dependent fields excluded; non-promotable) and a FORWARD recovery build on a reviewed
current commit. Plan §5.
B2 — record_attempt takes only (rid + page receipt) and derives endpoint/params from the frozen plan;
freeze_plan rejects a request_id that != request_id(endpoint,params,partition) and rejects duplicate
ids; 'verified' requires output_path == the plan-bound expected_output, opens the parquet INDEPENDENTLY
(pandas — b"DATA" raises), computes schema fingerprint + null/dup on the plan natural_key, and requires
a proven-termination attempt (single_page/last_page/complete); dense datasets can never verify 0 rows;
confirmed_empty requires empty_policy==sparse + >=2 stored empty receipts + a canary that is a planned
SAME-endpoint request in state verified with a nonempty attempt. My own flawed tests (b"DATA",
cross-endpoint canary) are replaced with real-parquet + refusal tests.
B3 — _reject_reparse_lexical uses os.lstat: only FileNotFoundError = absent; a BROKEN junction (target
deleted; Path.exists() False) is now caught (pinned test creates one via CreateJunction + rmdir); the
realpath belt is component-aware relative_to (not str startswith, which <root>_evil defeats). The full
no-follow handle-based write broker for the residual TOCTOU is specified as the adapter-phase
requirement (plan §2); the coordinator's own writes go through the authority + lstat scan.
M1 — ENDPOINT_MATRIX rebuilt: one typed row per (endpoint, query_mode, output_family), EVERY callable
UNBOUND (bind post-contract; adapter construction stays blocked until pinned). Corrected: income /
balancesheet are STANDARD (pro.income/pro.balancesheet, not VIP); cashflow/forecast/holder_number are
per-stock init_factor scope; report_rc doc cap = 3000 (not 5000) and natural_key includes author_name;
A15 placeholder rows are explicitly UNBOUND; row_identity_key vs agg_key + baseline_dups added for the
multi-row event datasets (top_inst 2,636,668 / block_trade 180,262 baseline dup rows under the 2-col
key; top_list/dividend/forecast/indicators/stk_holdertrade too).
M2 — the contract scaffold is regenerated to the validator's exact CONTRACT_REQUIRED keys (one source
of truth, no drift); contract_errors rejects placeholder LIST ELEMENTS (['x','x'] refuses); cmd_plan
returns nonzero while any row is blocked (verified: exit 1).
M3 — plan §6 quiescence contract: every raw consumer holds a generation barrier for its WHOLE
operation and re-checks the RECOVERY_IN_PROGRESS sentinel AFTER acquiring it; promotion takes the
barrier exclusive first; the family set is a frozen disjoint list; write-ahead MOVE_OLD_INTENT/
INSTALL_NEW_INTENT before each rename; an explicit OLD_ABSENT state for already-empty incident targets;
owned-resume (a pre-existing incoming/tombstone is refused unless this run's own intent + hash owns it);
a full state x path x hash recovery table drives deterministic roll-forward/rollback.
Minors — spaced_call normalizes rate_limit_backoff via float()+isfinite (an inf backoff persisted inf
as next-allowed) and floors it to >= base_sleep; the contract test runs entirely under tmp_path
(monkeypatched E_ROOT/DOC_MIRROR), no writes to the live mirror.

DISCLOSED LIMITS (unchanged intent): adapters + the no-follow handle write broker + the allowlist
monitor + the full C-side build/oracle/promotion executables are the ADAPTER PHASE, gated by this
review + signed contracts; the ~20 data-dependent tests in tests/data_infra still fail against the
empty live store (incident blast radius, not regressions).

RE-REVIEW QUESTIONS
1. B1: is preserve-live-bins-as-legacy + report_rc-excluded-from-parity + two explicit builds the
   correct resolution, or is there a research-integrity hazard in keeping the legacy f93cb9d2-anchored
   report_rc bins live while the rebuilt ledger uses first-seen-safe raw?
2. B2: is the ledger now a sound restoration-proof substrate? Remaining gaps in the attempt/verdict
   evidence (page contiguity proof, response-hash chaining) you'd require before fetch?
3. B3: is os.lstat + component-aware containment sufficient for the COORDINATOR's own writes, with the
   handle-based no-follow broker correctly deferred to the adapter phase — or must the broker exist
   before ANY staging write (preflight survivor copy)?
4. M1: any remaining factual error in the rebuilt matrix? Is UNBOUND-until-contract the right gate?
5. M3: is the quiescence + write-ahead + OLD_ABSENT + owned-resume + recovery-table contract complete
   enough to implement, or still underspecified anywhere?
6. Readiness: can the two no-fetch workstreams now BEGIN — (a) signing the 30 endpoint contracts into
   this schema, (b) building the containment/ledger/promotion executables + their test matrix — while
   the fetch authorization waits? If not, name the blocker.

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending text/code quoted + exact fix.
- Answer the 6 questions explicitly.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk before contract signing
  + executable construction begin.
```
