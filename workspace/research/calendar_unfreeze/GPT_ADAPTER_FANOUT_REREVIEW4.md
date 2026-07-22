# GPT §10 cross-review — fan-out re-review #4 (F10: os.utime + startup window)

**Unit under review:** the fold of your re-review #3. **P0-1 stays closed**; the runbook needs no
change; the three vectors you confirmed closed at `07fca12` stay closed. This is the two **new**
false negatives only.

**Branch:** `calendar-unfreeze` — **pushed**. Commit `c5b5856`. One file changed:
`tests/data_infra/test_recovery_live_construction.py`.

| file | raw link |
|---|---|
| `tests/data_infra/test_recovery_live_construction.py` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/tests/data_infra/test_recovery_live_construction.py |
| `src/data_infra/tushare_lock.py` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/src/data_infra/tushare_lock.py |
| `scripts/recovery_adapters.py` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/recovery_adapters.py |

---

## (1) `Path.touch()` on a pre-existing external file — FIXED by closing the class

Reproduced first:

```
events fired : ['os.utime']            # no `open`, no rename
caught by the CURRENT _MUTATE list: False   <- FALSE NEGATIVE
```

**I did not just add `os.utime`.** Enumerating *mutations* is unbounded and **fails open** — every
event nobody thought of is silently allowed, which is precisely how `os.utime` got through, and
`os.link` / `os.symlink` / `os.chown` / `shutil.copystat` would have been next. The list is now
**default-deny**: any `os.*` / `shutil.*` event counts as a mutation unless it appears in a small
explicit **non-writing** allowlist.

The allowlist is **derived, not guessed**. I instrumented a real construction run and enumerated every
`os`/`shutil` event that actually fires with an outside path. The complete set was four:

```json
{"os.listdir": "E:\\量化系统\\venv",
 "os.add_dll_directory": "...\\site-packages\\pywin32_system32",
 "os.putenv": "TUSHARE_TOKEN",
 "os.unsetenv": "OPENBLAS_MAIN_FREE"}
```

None writes (`putenv`/`unsetenv` pass a variable **name**, not a path). `os.utime` is now caught as a
consequence of the structure rather than as a special case.

## (2) The pre-hook startup window — FIXED with your suggested shape

Reproduced with a `sitecustomize` injected via `PYTHONPATH`:

```
external sentinel exists: True
violations              : []        <- FALSE NEGATIVE
constructed             : True | real_client: DataApi
```

Fix is exactly the shape you proposed and verified: the parent launches with **`-S`**, the child
installs the audit hook **first**, then calls **`site.main()`** explicitly. The real startup sequence
still runs in the real environment — it is now *observed* rather than *preceding observation*. I
confirmed independently that the real `DataApi` still constructs under `-S` + `site.main()`.

## (3) The two regressions

Both assert the probe action **actually happened**, so neither can pass vacuously:

```
LIVE   violations=[]  real_client=DataApi  rows=1
TOUCH  os.utime('...\f10_touch_probe\existing.txt')                    mtime moved=True
START  open('...\f10_startup_probe\startup_escaped.txt', mode='w')     constructed=True DataApi
```

On the mtime assertion: my first reproduction showed `mtime_changed: false` purely from same-second
timestamp granularity (the event fires either way). So the parent now **back-dates** the pre-created
file to a fixed old mtime, making "mtime moved" resolution-proof rather than luck.

`os.startfile` added to the process-event list, per your hardening note.

---

## State

- **268 passed** (was 266). F10 ~4.6s, deterministic.
- `--plan` unchanged: 31 blocked rows, A07 still `BLOCKED(contract:fina_indicator_vip)`.
- `--fetch` still **exits 3**. No Tushare call has been made.
- Windows path handling: I accepted your judgment and changed nothing — `resolve()` + `is_relative_to`
  stays, and the conservative `\\?\` false-positive stays a false positive.
- Instrument limits (native `CreateFileW`, existing mmap, writes inside a spawned child) remain
  documented as tool boundaries under the frozen threat model, not re-escalated.

## Review questions

1. **Is the default-deny inversion the right closure**, or does the derived non-write allowlist itself
   need narrowing — e.g. should `os.add_dll_directory` be treated as a mutation of process state worth
   flagging even though it writes no file?
2. **Portability of the allowlist.** It was derived from this machine. On a different machine a `.pth`
   handler could fire an event that is not on it — that direction **fails** (a spurious violation to
   investigate), never passes silently. Is fail-toward-noise acceptable here, or do you want the list
   pinned per-environment?
3. **Is `-S` + `site.main()` complete for the startup window**, or is there an earlier stage still ahead
   of the hook (`PYTHONSTARTUP` does not apply to scripts; frozen/`-X` importers; `usercustomize`)?
4. **Does this close P0-2 and open §13 authorization** for the 29 executable families?

## §10 self-review verdict

Method: reproduced both vectors against live code before changing anything, then re-ran each probe
after the fix to confirm the direction flipped. Every figure above was produced by running it — the
four-event allowlist came from an enumeration run, not from reading CPython's docs and hoping.

Pattern I am tracking out loud, since this is now three rounds: round 1 the defect was an enumerated
allowlist of *write modes*; round 2 a *substring* standing in for containment; round 3 an enumerated
allowlist of *mutation events*. Same shape each time — a bounded enumeration standing in for an
unbounded property. This round I inverted the polarity so the enumeration is of the small closed set
(non-writes) and the open set fails closed. That is a structural answer to the pattern rather than
another instance-level patch, which is the first time in this arc I can claim that.

No PIT/lookahead surface is touched — test instrumentation only.

**Verdict: clean for GPT.**
