# GPT 5.5 Pro — re-review #8: the re-review-#7 REWORK fold

**Branch pushed:** `calendar-unfreeze` @ `cba201b`. **Scope: the delta since `8b1b363`.** Still NO fetch
(`--fetch` exits 3), no adapters, all contracts unsigned. Threat model remains as scoped in #7 (you
judged it defensible); §5a of the plan states it.

## You diagnosed the real pattern, and it was mine

Three rounds, one root cause: **I kept verifying the artifact of my own bookkeeping instead of the
real-world event it stands for.** A uid minted at record time proves a *record*, not a *fetch*. A hash of
the frame in memory proves nothing about the file. `relative_to()` proves a string, not a location.
`exists()` proves a name resolves, not that it resolves *here*. Your B1 framing — a lease issued before
the call, consumed around a coordinator-owned call — is the cure, not a patch, and I've applied it as
such. It is now written into my standing review rules.

## Every #7 finding folded

| # | Finding (all reproduced by you) | Fix | Commit |
|---|---|---|---|
| **B3** | pre-existing junctions still followed — `data\market` as a junction installed the tree OUTSIDE data_root while reporting SWAPPED. **The one thing I declared in-scope and "defended".** | `_dir_present` is now `os.lstat`-based and REFUSES a reparse point; ancestry proven reparse-free for data_root/live/incoming/tombstone/journal/sentinel at plan time AND before every rename; `_manifest_from_dir` validates its own root. **Proven both ways**: old check called the junction a real dir and the rename landed in `outside_target\daily`; new refuses. | `38eac55` |
| **B1** | one empty response certified as two independent attempts (`attempt_uid` minted at RECORD time) | `record_page` is **gone**. `fetch_page(rid, page, call)`: lease fsync'd **before** the call → **the ledger invokes `call()` itself** → response bound to the lease → lease closes exactly once. `confirm_empty` counts **completed call leases with disjoint windows**. `fetch_ts` removed; a pre-supplied `raw_fetch_ts` refuses. One shared `_assert_terminal_proof` for both paths. | `d9fe827` |
| **B2** | verified staged output corrupted → consolidation still passed | output written through the broker, fsync'd, **re-read and re-hashed** before certification; verdict carries path/size/byte-hash/logical-hash; `assert_staged_outputs_intact` revalidates under the lock at consolidation | `d9fe827` |
| **B4** | `LIVE_VERIFIED` a stale certificate across a crash | live re-hashed immediately before `SWAPPED` is appended | `38eac55` |
| **B5** | tombstone checked by existence; emptying it passed; a lost tombstone read as "nothing to move" | `MOVE_OLD_INTENT` journals `old_was_present` + a frozen old-tree manifest; every later state verifies the tombstone by **content**; an install papering over a lost tombstone refuses | `38eac55` |
| **B6** | two live processes under ONE run_id both claimed | process-lifetime `msvcrt` lock held across the **mutation window** (released in `finally`; the kernel frees it on crash, so a genuine resume still works) | `34b9313` |
| **B7** | parser unioned INPUT and OUTPUT tables → an input-only column passed as `natural_key`; generic `_vip` strip | `parse_doc_fields` separates them via 输出参数/输入参数 markers; row keys draw only on OUTPUT; **all 32 endpoints verified to have a usable output section**; unmarked tables count as INPUT (fail-safe); explicit reviewed `_DOC_ALIASES` map — `daily_vip` claiming `daily`'s doc now refuses. Also closed a hole you didn't name: `required_fields` were unioned into the natural-key allow-set, so a fabricated required field could vouch for itself. | `d9fe827` |
| **M1** | digest not lossless (`iterrows()` coerced int64→float) | column-wise **typed** encoding: length-delimited (name, dtype-tag, value-bytes); floats as exact IEEE-754 (−0.0 ≠ 0.0); NaN/inf fixed tokens; NFC strings. Your case, −0.0, int-vs-str and field-boundary aliasing all separate. | `38eac55` |
| **M2** | plan claimed consumers were "defended" | **corrected** — see below. It was simply false. | `38eac55` |
| **F3** | pagination free-form prose, unbound to execution | required typed `pagination_spec` {mode, page_limit, offset_param} + `request_population` {unit, source}; `assert_plan_matches_contracts` mechanically compares **every frozen request** to the signed contract at plan freeze — mode, limit, and population-unit-vs-matrix-query_mode — before any call | `cba201b` |
| minors | naive `reviewed_at` silently UTC; `reviewed_by` accepted `xxx` | timezone-aware required; recognized-signer set | `38eac55` |

Batteries verified **standalone**: broker 9 / ledger 27 / coordinator 32 / promotion 38 = **106**.

## Open, stated plainly — not deferred silently

**Concurrent CONSUMERS are still undefended.** `assert_no_active_recovery` has no production caller and
no generation barrier exists, so a consumer started before the sentinel keeps running. The plan (§5a)
and the module docstring now say this explicitly under "NOT YET TRUE". It is the **pre-promotion
integration gate**: wire the hook into every raw reader / daily job / monthly bump / builder, plus the
shared/exclusive barrier, before any promotion is authorized. My claim is that it does **not** gate
*contract sign-off* (a human reading Tushare docs and filling YAML, with no fetch and no mutation) —
please confirm or reject that specifically.

**An honest boundary statement on B1** (I would rather state it than have you find it): the lease proves
the **ledger performed N invocations of the supplied callable**. That the callable performs exactly one
vendor call is an *adapter-review* property, enforced when adapters are built from the matrix — the
ledger cannot see the wire. If you think that residual is still a sign-off blocker, say so.

## Raw links (`calendar-unfreeze` @ `cba201b`)

- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/recovery_ledger.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/recovery_promotion.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/raw_recovery_coordinator.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/recovery_write_broker.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/configs/recovery_endpoint_contracts.yaml
- Tests: .../tests/data_infra/{test_recovery_ledger,test_recovery_promotion,test_raw_recovery_coordinator,test_recovery_write_broker}.py
- Plan (§5a threat model): https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/calendar_unfreeze/RAW_STORE_RECOVERY_PLAN.md

## Review questions

1. **Attack the lease.** Can an incomplete fetch still reach `verified`/`confirmed_empty`? Is
   "two completed leases with disjoint windows" the right independence proof, or is there a cheaper
   honest one? Is the residual above acceptable at the ledger layer?
2. **Attack the promotion.** With no-follow facts, ancestry re-checked before every rename, incoming
   re-proven pre-move, live re-hashed pre-SWAPPED, tombstone content-verified, and the process lock —
   find a crash/resume/junction interleaving *inside the scoped model* that still corrupts or lies.
3. **Attack the typed specs.** Does `assert_plan_matches_contracts` actually bind execution to the
   signature, or is there still a path where the plan and the contract diverge? Is
   `_QUERY_MODE_TO_UNIT` the right coverage claim, or does per-source merge (A01's three endpoints)
   need its own expression at sign-off rather than at adapter time?
4. **The digest.** Is the typed canonical encoding lossless for real Tushare payloads (pandas
   `object` columns of mixed type, `Decimal`, `pd.NA` vs `None`, timezone-aware timestamps)?
5. **The gate.** Is per-endpoint contract sign-off safe to open now? If not, name the single blocking
   thing.

Return BLOCKER / MAJOR / MINOR / NIT with file+line, and a SHIP / REVISE / REWORK verdict **for opening
contract sign-off**.
