# GPT §10 cross-review — recovery ledger: persisted genesis anchor + verification caching

## REVIEW TIER & ROUND (per the 2026-07-22 convergence protocol)

- **Tier: 1.** This is the recovery ledger's integrity core — chain anchor and chain/plan verification.
  The unit's whole acceptance bar is adversarial-shaped ("a tamper must never be masked").
- **Round budget: 3.** If round 3 is not SHIP, I stop folding and take the divergence to the user with
  three options (re-scope / structural mechanism / tracked debt).
- **Round: 1 of 3.** Full open sweep of this unit is in scope this round.
- **One review unit**: the ledger changes below. The `--fetch` wiring and the shared daily merger are
  NOT in this unit (they shipped separately; flag anything you see, but they do not gate this).

## FROZEN THREAT MODEL (unchanged; user decision 2026-07-16, re-affirmed 2026-07-20)

Authoritative record: `ADAPTER_PHASE_DESIGN.md` §6a; the limitation also lives in
`recovery_write_broker.py`'s module docstring.

**IN scope** — pre-existing/broken NTFS junctions (the incident's actual cause), crashes, torn or
partial writes, staged-byte corruption, concurrency between recovery processes, mis-certified fetches.

**OUT of scope** — a mid-operation ACTIVE LOCAL ADVERSARY. Rationale: single-user workstation; local
write access can destroy the store outright without racing, which is exactly what happened on
2026-07-13 with no adversary present.

**Finding admissibility**: a finding gates this round iff it demonstrates an in-scope failure class
with a probe that needs no out-of-scope capability. Please classify every finding in/out-of-scope and
return a scope-bounded verdict. "SHIP with out-of-scope proposals recorded" is a first-class expected
verdict.

**Acceptance criterion per class**, for this unit specifically:
1. A crash-torn or truncated ledger must refuse, warm cache or cold.
2. An in-place rewrite of any already-verified ledger row must refuse at the next process start, and
   within a process must not be masked indefinitely.
3. A rewritten `request_plan.json` must refuse, warm cache or cold.
4. A ledger from another run must not be adoptable.
5. `_load()` must return the same rows whether the cache is warm or cold.
6. Normal repo activity (commits touching nothing in the recovery) must NOT break an in-flight run.

---

## Why this change exists

The first live fetch ran 13 minutes and was stopped deliberately. It banked 85 verified requests /
273,436 rows, and exposed four defects. Two of them are in this unit.

**Measured, not assumed**: 9.49 s/request, against a 1.60s vendor call and the 1.50s §6.1 floor —
**6.4 s/request was our own overhead**. Projections at that rate: `market/daily` 35.5h, full set 274h
(11.4 days). After the fix: **0.26 s/request**, `market/daily` 12.6h, full set ~97h (~4 days).

**The genesis defect is the one that actually bit.** `_genesis()` was RE-DERIVED on every open from
`coordinator_commit` = repo-wide `git rev-parse HEAD`. While the fetch was running, three commits from
a **parallel session** (NF-wave threat-model docs, touching nothing in the recovery) moved HEAD, and
the run stopped opening: `ledger hash-chain break at line 1`. The chain was intact — it re-verified
350/350 under its original anchor. A recovery that runs for days across multiple authorization
segments cannot require that nobody commits to the repo.

## What changed

**Branch `calendar-unfreeze`, pushed.** Commits `a8d159c` (the four fixes) and `844ad16` (a bug my own
self-review then found in that fix).

| file | raw link |
|---|---|
| `scripts/recovery_ledger.py` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/recovery_ledger.py |
| `scripts/raw_recovery_coordinator.py` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/raw_recovery_coordinator.py |
| `scripts/recovery_adapters.py` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/recovery_adapters.py |
| `tests/data_infra/test_recovery_quartet.py` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/tests/data_infra/test_recovery_quartet.py |
| `ADAPTER_PHASE_DESIGN.md` (§6a threat model) | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/calendar_unfreeze/ADAPTER_PHASE_DESIGN.md |

**1. Genesis is a persisted per-run constant.** Minted once at run creation into
`ledger/chain_genesis.json` (with the creating coordinator/bundle identity kept alongside as
evidence), read back thereafter, and refusing an anchor whose `run` field names a different run. Code
identity is still bound where it must stay live: the §13 authorization binds `bundle_sha256` and
`run_family` refuses on live bundle drift, so an adapter change still forces **re-authorization** —
which is deliberate. Bricking **resumption** was not.

**2. Plan verification is cached, stat-guarded.** The frozen plan is 102 MB / 104,176 rows; verifying
it re-reads, re-parses, re-canonicalises and re-hashes every row, and that ran ~4x per request. Cache
key = (size, mtime_ns, chain-attested hash). Measured **1.252s → 1.00ms (1248x)**. Any change to the
file falls through to the full verification.

**3. Chain verification keeps a verified prefix, advanced in ONE place.** `_append` is the sole writer
and holds the lock; it advances the cache with the record it just wrote. `_load()` trusts the cache
**only** when (size, mtime_ns) match exactly, and otherwise replays from genesis. A budget
(`_FULL_REVERIFY_EVERY = 2000` appended rows) forces a periodic full replay, and every process start
— i.e. every `--fetch` segment — replays fully.

**I got this wrong on the first attempt, and the existing tamper test caught it.** My first version
inferred "the file grew, therefore it was appended to" and verified only the tail. Rewriting line 1
also grows the file, so a genuine corruption took the incremental path — it still failed closed, but
on the wrong evidence, and the incremental path had been entered on an in-scope corruption. Nothing is
inferred from the file's shape now.

**4. Then my §10 self-review found a second bug in my own fix.** A probe compared cached rows against
a full replay: they were not equal. `_append` cached the in-memory record while `_load()` returns the
`json.loads` round-trip — a tuple value is written as a JSON array and read back as a **list**. So
`_load()` returned a tuple with a warm cache and a list with a cold one: the same call returning
different types depending on nothing but timing. No existing test caught it, because every other test
appends only JSON-native scalars. Fixed by caching `json.loads(_canon(rec))`, so the cached view is
the round-tripped view **by construction**.

## Self-review probes (all passing; adversarial, run against live code)

```
[PASS] cached rows == full replay (JSON round-trip safe)
[PASS] budget forces a periodic full replay            since_full=2 after 12 appends at budget 5
[PASS] another writer's append is seen (stat guard)    2 -> 3 rows
[PASS] truncated tail is refused                       "head does not match the chain tail"
[PASS] genesis stable across identity change
[PASS] genesis anchor persisted
[PASS] anchor deletion + identity drift refuses        "hash-chain break at line 1"
```

Also verified mechanically: the ledger file has exactly ONE writer (`_append`, line 403); `_chain_cache`
is assigned in exactly two functions (`_append` and `_load`'s full-replay branch) with no
inference-from-shape path remaining.

Suites: 268 passed across quartet / ledger / coordinator / promotion / broker.

## Review questions

1. **Acceptance criterion 2 is the one I am least sure of.** Within a single long-lived process, an
   in-place rewrite of an already-verified row is detected only at the next full replay (≤2000 appended
   rows ≈ 500 requests) or the next process start. Is that bound acceptable under the frozen model
   (in-scope: crashes, staged-byte corruption; out-of-scope: an adversary)? If not, what is the cheapest
   sound alternative — I considered re-hashing the prefix bytes each load, but that is O(n) and
   reintroduces the O(n²) this change removed.
2. **Is (size, mtime_ns) a sufficient staleness guard** for the in-scope classes on NTFS, given mtime
   granularity? My reasoning: `_append` is the only writer, holds the lock, and records the stat it
   just produced; anything else touching the file changes size or mtime, and a change that preserves
   both is an adversary. Do you agree, or is there a crash/corruption shape that preserves both?
3. **Genesis persistence.** Does moving the anchor from "re-derived" to "stored next to the ledger"
   weaken anything in scope? My argument: it never protected against an adversary (who could rewrite
   both), and the run-id check plus the chain plus the external head still cover substitution,
   truncation and tamper. But this is the change I would most want a second opinion on.
4. **Anything the perf work broke** that the 268 tests do not cover.

## §10 self-review verdict

Method: reproduced each defect against live code before fixing, measured every number quoted (nothing
extrapolated from the 1.5s floor this time — that assumption is precisely what was wrong), then wrote
adversarial probes against my own fix rather than only re-running the suite. Those probes found a real
bug I had just introduced, which I have fixed and pinned.

Two rounds in a row now, the defect in my own work was "a cheaper thing standing in for the real
thing" — inferring append from file growth, then caching an object that is not what the reader
returns. Question 1 asks you to check whether the third instance of that shape is still present in the
budget-bounded prefix trust.

No PIT/lookahead surface is touched: this is recovery-ledger integrity and orchestration only.

**Verdict: clean for GPT.**
