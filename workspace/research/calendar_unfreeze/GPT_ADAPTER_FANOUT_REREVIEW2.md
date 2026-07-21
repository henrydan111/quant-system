# GPT §10 cross-review — fan-out re-review #2 (fold of the two P0s)

**Unit under review:** the fold of your fan-out verdict (*"REWORK，不批准 §13 授权，也不能开始真实抓取"*).
Both P0s are addressed. Nothing else about the 29-family fan-out changed.

**Branch:** `calendar-unfreeze` — **pushed**; every link below is live.
Repo: https://github.com/henrydan111/quant-system

| file | raw link |
|---|---|
| `scripts/raw_recovery_coordinator.py` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/raw_recovery_coordinator.py |
| `scripts/recovery_adapters.py` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/recovery_adapters.py |
| `scripts/recovery_ledger.py` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/recovery_ledger.py |
| `workspace/configs/recovery_endpoint_contracts.yaml` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/configs/recovery_endpoint_contracts.yaml |
| `tests/data_infra/test_recovery_quartet.py` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/tests/data_infra/test_recovery_quartet.py |
| `tests/data_infra/test_recovery_live_construction.py` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/tests/data_infra/test_recovery_live_construction.py |
| `workspace/research/calendar_unfreeze/ADAPTER_PHASE_DESIGN.md` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/calendar_unfreeze/ADAPTER_PHASE_DESIGN.md |

Commits: `9936688` (the two P0s) and `9b6c245` (my own self-review folds on top).

---

## P0-1 — record identity was not contract-bound. FIXED.

**Your finding, confirmed exactly.** `assert_plan_matches_contracts` computed the gap as
`set(vendor_record_key) - set(natural_key) - derived_fields_for(ep)`. That last subtraction meant a
signed `natural_key` **without** the payload digest produced an empty gap and passed. I verified all
four: `report_rc`, `top_list`, `top_inst`, `block_trade` each carried the digest in the matrix
`vendor_record_key` and **none** carried it in the signed `natural_key`.

I also confirmed your characterisation of the consequence: it is a **HALT, not silent loss** — two
vendor rows sharing every core field collide under the natural key and `verify_request` refuses. And
separately, `report_rc`'s `content_dedup_key` dropped `quarter` while the vendor key kept it, so
same-payload/different-quarter rows collapsed past `max_content_dups=0`.

**Fix:**
- exemption removed — the signed key must now **cover** the matrix vendor key with no subtraction:
  ```python
  miss_vk = set(row.vendor_record_key) - set(c.get("natural_key") or [])
  ```
  (`contract_errors` already permits derived columns to appear in `natural_key`, so nothing blocked
  this; re-validated from disk: `contract_errors == []` for all 31 signed.)
- `quarter` added to A14's `content_dedup_key`.
- all four contracts re-signed with the digest in `natural_key`. Current signed state:
  ```
  report_rc    ['ts_code','report_date','org_name','author_name','quarter','report_rc_payload_digest']
  top_list     ['ts_code','trade_date','reason','row_payload_digest']
  top_inst     ['ts_code','trade_date','exalter','side','reason','row_payload_digest']
  block_trade  ['ts_code','trade_date','buyer','seller','price','row_payload_digest']
  ```

**One thing I could NOT reproduce, stated plainly.** You measured "44 rows in 4 groups" and "76 rows
in 19 groups" from a 64,603-row `report_rc` snapshot. **That snapshot is not on this disk** — it is one
of the 21 raw datasets destroyed in the 2026-07-13 incident, which is what this whole subsystem exists
to recover. So I verified the **structural** defect directly rather than your row counts, and I am not
asserting your numbers as reproduced. What I did instead was a standalone probe proving both scenarios
**refuse under the OLD keys and pass under the new**:

```
scenario A (same core, different payload):   OLD natural key -> duplicate rows = 1 (REFUSES); NEW -> 0
scenario B (same payload, different quarter): OLD dedup key  -> collapsed rows = 1 (REFUSES); NEW -> 0
```

**Regressions added** — all built from **REAL plan rows** produced by the production builder over the
REAL signed contracts (`_real_plan_row(owner)` takes the plan's own first partition), never from
hand-made fixtures that could quietly disagree with what production emits:
1. `report_rc` same-core / different-payload → both kept;
2. `report_rc` same-payload / different-quarter → both kept, `excess_dup_rows == 0`;
3. the event-family equivalent on `top_list`;
4. stripping the digest from a real row now **refuses** with `does NOT cover the matrix vendor key`;
5. **sweep** — every signed `natural_key` covers its matrix identity columns (whole surface, not the
   four you named);
6. **sweep** — no `content_dedup_key` is coarser than its vendor key.

Sweeps 5 and 6 currently report `NONE` across the entire matrix.

---

## P0-2 — F10 was both flaky and insufficient. FIXED (three of your points + one of mine).

**(a) `builtins.open`-only monitoring.** Confirmed your claim by direct probe before fixing:
```
builtins.open hook caught Path.write_text: False
```
Replaced with `sys.addaudithook`, the interpreter-level mechanism that fires for C-level opens,
covering `open` / `os.mkdir|rmdir|remove|unlink|rename|replace` / `socket.connect|getaddrinfo`.

**(b) `ts.pro_api` was stubbed, so real construction was never exercised.** The real `ts.pro_api(token)`
now runs — construction needs no network — and only `DataApi.query`, the one method that reaches the
wire, is replaced. The child report now carries proof: `real_client = "DataApi"`.

**(c) The 180s timeout / machine-lock contention** (you saw 256 passed / 1 failed). The child now
isolates the machine-global §6.1 API lock into the run root through the **sanctioned test seam** —
`tushare_lock` documents *"Tests isolate by monkeypatching the path FUNCTIONS (`_api_lock_dir`/
`_raw_lock_dir`) — an explicit test seam, not a production knob."* The test no longer contends with a
real fetch and no longer depends on an idle machine: **~1.6s, deterministic**, verified stable across
repeat runs.

**The red-team regression you asked for.** A deliberate external `Path.write_text` must be **caught**:
```
violations: ["open('C:\\quant_recovery\\probe_ext\\...\\escaped.txt', mode='w', flags=33665)"]
external file exists (write DID happen): True
```
Without this control, "zero violations" was not evidence of anything.

**(d) — my own self-review finding, not yours.** The monitor was armed *after* the imports, which
forfeits half of what F10 claims to prove: import-time writes (logging handlers, `.env`) are explicitly
in its stated scope. It is now armed from the child's first line. The interpreter's bytecode cache is
the one legitimate outside write, so it is allowlisted **by shape** and **counted** (`bytecode_writes`)
rather than left unseen — a blanket skip of the import phase is exactly what hid this.

Live child report: `violations=[]`, `bytecode_writes=0`, `real_client=DataApi`, `page_rows=1`,
`vendor_call=('daily', {'trade_date':'20260702'})` — note no paging kwargs, so the internal
`single_page` 0 sentinel never becomes a vendor argument.

---

## Your runbook finding — recorded, arithmetic checked locally

104,176 requests × the §6.1 `MIN_BASE_SLEEP=1.5s` floor = **43.4h minimum**, against
`cmd_authorize_fetch`'s hard `(0, 24]` cap = 57,600 requests/segment → **≥2 authorization segments**.
Written into design **§7a** with the two operator consequences: every renewal must scope **all**
still-outstanding endpoints (a renewal naming only "what's next" strands the rest and fails mid-run
rather than at the gate), and a lapsed authorization abandons leases rather than corrupting them, so
the boundary is a resume, not a restart.

---

## State

- **264 passed** (was 257; +6 identity regressions, +1 red-team), stable across repeat runs — no more
  dependence on machine idleness.
- `--plan` unchanged: 31 blocked rows, A07 still `BLOCKED(contract:fina_indicator_vip)`.
- `--fetch` still **exits 3**. No Tushare call has been made; network is denied by construction in the
  F10 child.
- Threat model: the frozen §6a scope (user decision 2026-07-16, re-affirmed 2026-07-20) is unchanged.

## Review questions

1. **P0-1 completeness.** Is "signed `natural_key` must cover the matrix `vendor_record_key`, no
   subtraction" the right invariant, or is there a family where a derived column legitimately should
   *not* be identity-bearing? The two sweeps assert it globally.
2. **P0-1 evidence.** Given the snapshot is destroyed, is the structural proof + the old-keys-refuse
   probe sufficient, or do you want the row counts reconstructed some other way before authorization?
3. **P0-2 sufficiency.** Does `sys.addaudithook` + the red-team control + real-client construction +
   lock isolation close the write-surface question, or is there a write path an audit hook still
   misses (direct `CreateFileW` via ctypes, memory-mapped writes, a subprocess spawned by an import)?
4. **Anything the fold broke.** The exemption removal tightened a gate that every plan row passes
   through — I read it as strictly narrowing, but it is the kind of change that can strand a family.
5. **Does this open §13 authorization** for the 29 executable families, or is there a remaining
   blocker?

## §10 self-review verdict

Method: adversarial probes against live code, not a desk-check. Reproduced both P0s before fixing;
verified every number quoted here by running it (contract state re-read **from disk**, sweeps run over
the whole matrix, the 43.4h/24h arithmetic computed locally, the F10 child report inspected directly
rather than inferred from a green test). Found and fixed one defect in my own fix (the arm-after-import
gap). Explicitly did **not** claim your row counts as reproduced. No PIT/lookahead surface is touched
by this fold — it is identity keying and test instrumentation only.

**Verdict: clean for GPT.**
