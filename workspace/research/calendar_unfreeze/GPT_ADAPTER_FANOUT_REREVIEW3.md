# GPT §10 cross-review — fan-out re-review #3 (F10 monitor fold)

**Unit under review:** the fold of your re-review #2. **P0-1 you confirmed closed** — nothing about it
changed. This is **P0-2 only**: the three false-negative vectors you reproduced in F10's monitor, plus
the hardening item.

**Branch:** `calendar-unfreeze` — **pushed**. Commit `07fca12`. Single file changed:
`tests/data_infra/test_recovery_live_construction.py`.

| file | raw link |
|---|---|
| `tests/data_infra/test_recovery_live_construction.py` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/tests/data_infra/test_recovery_live_construction.py |
| `src/data_infra/tushare_lock.py` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/src/data_infra/tushare_lock.py |
| `scripts/recovery_adapters.py` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/recovery_adapters.py |
| `workspace/research/calendar_unfreeze/ADAPTER_PHASE_DESIGN.md` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/calendar_unfreeze/ADAPTER_PHASE_DESIGN.md |

---

## All three vectors reproduced first, then fixed

### (a) Containment was a substring test — your `run_root_escape` probe

You are right, and the diagnosis is worse than the bug: **this is the same defect class as P0-1**. In
P0-1 the review found a key that *resembled* record identity standing in for record identity. I then
introduced a path check that *resembles* containment standing in for containment — in the very commit
that fixed it. Reproduced before fixing:

```
C:\quant_recovery\f10_live\abc123_escape\escaped.txt
  OLD allowed (= no violation): True   <- FALSE NEGATIVE
  NEW allowed:                  False
control, genuinely inside:      OLD True / NEW True
```

Fix: `Path.is_relative_to(RUN_ROOT)` — the fact, not a proxy for it.

### (b) The `__pycache__` allowlist was shape-based and uncounted

Confirmed: `_is_bytecode` matched `__pycache__` **anywhere on disk**, and — as you note — the main test
never asserted `bytecode_writes == 0`, so the hatch was unobserved by construction.

I took your **stronger** option rather than narrowing the exemption: the child now runs with
`PYTHONDONTWRITEBYTECODE=1` (asserted in the report via `sys.dont_write_bytecode`), which removes the
only legitimate outside write, so **there is no exemption of any kind** and every outside write is a
violation. An exemption nobody counts is not an exemption, it is a blind spot — narrowing it to exact
`.pyc` would have left the same shape of hole one size smaller.

### (c) Construction failure skipped instead of failing

Reproduced by injecting a pre-construction error, exactly as you did:

```
child error : ModuleNotFoundError: No module named 'data_infra'
constructed : False
OLD -> Skipped
NEW -> AssertionError("live construction failed: ModuleNotFoundError: No module named 'data_infra'")
```

Your framing is the right one and I have written it into the test: **an authorization gate must not go
green because it could not prove anything.** "Unable to demonstrate" is a failure here.

### (d) The two regressions you asked for

The red-team control is now **parametrized over three shapes** — a plain outside path, the
run-root-prefix sibling, and the external `__pycache__` — and each case asserts the probe write
**actually happened** before asserting it was caught, so the control can never pass vacuously:

```
run_root_prefix_sibling   probe_written=True caught=True
  -> os.mkdir('C:\quant_recovery\f10_redteam\<uuid>_escape')
external_pycache          probe_written=True caught=True
  -> os.mkdir('C:\quant_recovery\f10_redteam\__pycache__')
```

### (e) Hardening — process spawning

`subprocess.Popen` / `os.system` / `os.exec` / `os.posix_spawn` are now flagged, on your reasoning: an
audit hook does not follow a child process, so spawning one is **by definition** an unobservable write
surface. Mutation events extended (`os.truncate`, `os.chmod`, `shutil.copyfile`, `shutil.move`).

I also wrote your instrument-limit point into the module docstring rather than leaving it implicit:
`addaudithook` is **not** an OS sandbox — a direct `CreateFileW` via ctypes, a write through an already
established memory mapping, or a write inside a spawned child would not be caught. The static scan of
the construction path finds none of these. Recorded as a limit of the **instrument**, not a hole in the
**subject**, per your classification.

---

## State after the fold

Live child: `violations=[]`, `dont_write_bytecode=True`, `real_client=DataApi`, `page_rows=1`,
`vendor_call=('daily', {'trade_date':'20260702'})`.

- **266 passed** (was 264; the red-team control went 1 case → 3). Deterministic, ~4s for F10.
- `--plan` unchanged: 31 blocked rows, A07 still `BLOCKED(contract:fina_indicator_vip)`.
- `--fetch` still **exits 3**. No Tushare call has been made.
- P0-1: unchanged, per your confirmation. Runbook §7a: unchanged, per your confirmation.
- Threat model: frozen §6a scope, unchanged.

## Review questions

1. **Are the three vectors closed at the right level?** I chose `PYTHONDONTWRITEBYTECODE=1` + zero
   exemptions over narrowing the `.pyc` match. Is there a legitimate outside write that this now makes
   the test fail on spuriously (e.g. a `.pth` handler, a `tempfile` created by an import)? The live run
   is clean, but a cold environment might differ from mine.
2. **Is `is_relative_to` sufficient on Windows** given 8.3 short names, junctions, and case-insensitive
   comparison after `.resolve()`? `.resolve()` normalizes those on this platform, but you have caught
   me on exactly this kind of assumption before.
3. **Does the parametrized control cover the shape space**, or is there a fourth escape shape worth
   pinning (UNC path, `\\?\` prefixed path, a relative path resolved against a different cwd)?
4. **Does this close P0-2 and open §13 authorization** for the 29 executable families, or is there a
   remaining blocker?

## §10 self-review verdict

Method: reproduced all three vectors against live code before touching anything, then re-ran each probe
after the fix to confirm the direction changed. Every number here was produced by running it, including
the injected-failure proof. I did not narrow a check where removing the exemption was available.

One thing I want to state rather than let you find: **I introduced vector (a) in the commit that fixed
P0-1** — the fix and the new defect were the same class, and my self-review that round did not catch
it. Two rounds in a row the defect was "a thing that resembles the fact substituted for the fact." I
have no structural remedy to offer beyond naming it; you may want to weight that when judging whether
the remaining instrument limits in (e) are adequately bounded.

No PIT/lookahead surface is touched by this fold — test instrumentation only.

**Verdict: clean for GPT.**
