# GPT §10 cross-review — fan-out re-review #5 (F10: the bootstrap-import window)

**Unit under review:** the fold of your re-review #4. P0-1, the runbook, the Windows-path judgement,
the default-deny direction and the `os.utime` / `site.main()` fixes are all unchanged and confirmed by
you. This is the **one remaining P0** — the child's own bootstrap imports running ahead of the hook.

**Branch:** `calendar-unfreeze` — **pushed**. Commit `e27d040`. One file changed:
`tests/data_infra/test_recovery_live_construction.py`.

| file | raw link |
|---|---|
| `tests/data_infra/test_recovery_live_construction.py` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/tests/data_infra/test_recovery_live_construction.py |
| `scripts/recovery_adapters.py` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/recovery_adapters.py |
| `src/data_infra/tushare_lock.py` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/src/data_infra/tushare_lock.py |

---

## The window — confirmed, then closed

Verified your premise independently before changing anything:

```
PYTHONPATH entry on sys.path under -S: True
```

So `-S` defers site initialisation but leaves `PYTHONPATH` in place, and the child's own
`import json, os, socket` / `from pathlib import Path` at line 67 ran before the hook at line 144.

**Fix, in the shape you specified.** Only `sys` is imported first — it is a **built-in** module,
satisfied from the interpreter itself and never resolvable from `PYTHONPATH`, whereas every other
import can be shadowed. The hook installs immediately in **buffering** mode, because no path judgement
is possible before `os`/`pathlib` exist: events are **recorded, not dropped**. Then `json/os/socket/
pathlib` are imported, `RUN_ROOT` and `_allowed()` are established, and the buffer is **replayed
through `_classify`** — the same classifier steady-state uses, so the pre-bootstrap path cannot drift
from the normal one. The live run buffers **32** bootstrap events and still reports `violations=[]`.

## The regression — proven to be a regression, not just a passing test

I simulated the pre-fix import order and ran the identical shadowed-stdlib injection against both:

```
shadowed PYTHONPATH/json.py against:
  PRE-FIX  probe_written=True  caught=False  constructed=True  client=DataApi   <- silent escape
  FIXED    probe_written=True  caught=True   constructed=True  client=DataApi
```

The shim writes the external sentinel and **then proxies the real stdlib `json`** (drops its own
directory from `sys.path`, re-imports, republishes into `sys.modules`), so the interpreter keeps working
end to end — the escape is silent by construction, which is what makes it worth pinning. The test
asserts all four things you asked for: the write really happened, it was caught, bootstrap events were
actually buffered, and the real `DataApi` plus the single-page execution still completed.

```
LIVE   violations=[]  bootstrap_events_buffered=32  client=DataApi  rows=1
SHADOW open('...\f10_shadow_probe\bootstrap_escaped.txt', mode='w')  constructed=True  rows=1
```

## Your other rulings, applied as given

- **`os.add_dll_directory`** — agreed, it is process DLL-search-path state, not a disk write. It stays
  in the non-write set, with that reasoning written next to it instead of left implicit.
- **No per-machine relaxation** of the non-write list. Failing on an unknown event is the intended
  direction; I have not added an escape hatch.
- **`-S` + `site.main()`** stands as complete for the site-managed stage, per your analysis.

---

## State

- **269 passed** (was 268). F10 ~5.8s, deterministic.
- `--plan` unchanged: 31 blocked rows, A07 still `BLOCKED(contract:fina_indicator_vip)`.
- `--fetch` still **exits 3**. No Tushare call has been made.

## Review questions

1. **Is the buffer-then-replay boundary correct?** The buffering predicate uses only `str` methods
   (`event == "open"` or `startswith(("os.","shutil.","socket.","subprocess."))`) since no imports
   exist yet. Is there an event class worth buffering that this predicate misses?
2. **Is `sys` genuinely the only safe first import** for this purpose, or would you also accept
   `_frozen_importlib`-level checks? I took built-in-only as the invariant.
3. **Anything still ahead of `import sys`** in a script launch — `-X` importers, a frozen/embedded
   bootstrap, `PYTHONHOME` effects?
4. **Does this close P0-2 and open §13 authorization** for the 29 executable families?

## §10 self-review verdict

Method: verified the `-S`/`PYTHONPATH` premise, reproduced the escape, fixed it, then proved the new
test **fails on the pre-fix code and passes on the fixed code** rather than only observing it green.
Every figure quoted was produced by running it.

Round-shape note, continuing the one I flagged last time: rounds 1–3 were bounded enumerations standing
in for unbounded properties, and I claimed the default-deny inversion was the structural answer. This
round's defect was a different class — not the classifier's *coverage* but its *start time*. The
inversion was still correct; it just did not reach a hook that had not been installed yet. Both fixes
now share one classifier and one start point, which is the property I would want a reviewer to attack
next if anything remains.

No PIT/lookahead surface is touched — test instrumentation only.

**Verdict: clean for GPT.**
