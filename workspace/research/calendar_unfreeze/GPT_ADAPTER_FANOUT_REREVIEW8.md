# GPT §10 cross-review — fan-out re-review #8 (F10: full audit-namespace enumeration)

**Unit under review:** the fold of your re-review #7. Everything you have confirmed stays confirmed.
This is the three findings — `_winapi.CreateProcess`, `winreg`, `O_TEMPORARY` — plus the docstring
correction you asked for.

**Branch:** `calendar-unfreeze` — **pushed**. Commit `b627a42`. One file changed:
`tests/data_infra/test_recovery_live_construction.py`.

| file | raw link |
|---|---|
| `tests/data_infra/test_recovery_live_construction.py` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/tests/data_infra/test_recovery_live_construction.py |
| `scripts/recovery_write_broker.py` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/recovery_write_broker.py |
| `scripts/recovery_adapters.py` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/recovery_adapters.py |

---

## What I did differently this round

Reproduced all three, then **stopped patching named surfaces and enumerated the whole audit-event
namespace of a clean run** — which is what I should have done four rounds ago. It immediately found two
more surfaces nobody had named:

```
=== every non-import event, clean run THROUGH the executor page ===
  ctypes.dlopen            x7    ('kernel32',)
  ctypes.dlsym             x24   (<WinDLL 'kernel32'...>, 'GetLastError')
  ctypes.get_last_error    x1    ()
  msvcrt.locking           x2    (3, 2, 1)
  open                     x840
  os.add_dll_directory     x4  / os.listdir x122 / os.mkdir x3 / os.putenv x4 / os.unsetenv x2
  os.remove                x1    (in-root api_lock)      os.rename x1 (in-root)
  socket.__new__           x1  / socket.bind x1 ('::1', 0)
  tempfile.mkstemp         x1    (in-root)
  winreg.ConnectRegistry   x2  / OpenKey x2 / OpenKey/result x2 / EnumValue x7 / QueryInfoKey x1
```

**My first enumeration was itself wrong** — it stopped at construction instead of running the executor
page, so it missed `msvcrt`, `tempfile` and `ctypes.get_last_error`. I caught that because adding the
`ctypes` branch made the live test FAIL on `ctypes.get_last_error`; I re-ran the enumeration through the
full page path rather than adding the one event that broke.

Watched now: `os` / `shutil` / `tempfile` / `socket` / `subprocess` / `_winapi` / `winreg` / `ctypes` /
`msvcrt`.

## The three findings

1. **`_winapi.CreateProcess`** — added to the process family and the watched set. Your point stands:
   Windows `multiprocessing` calls it directly, never through `subprocess.Popen`.
2. **`winreg`** — default-deny with the READ set enumerated, same polarity as os/socket.
3. **`O_TEMPORARY`** — reproduced exactly: file gone, `flags=192`, old mask silent. The mask now covers
   `O_TRUNC` / `O_TEMPORARY` / `O_TMPFILE`. Destruction is not the same predicate as writing.

**Allowances are principled, not conveniences** — worth your scrutiny since this is where the previous
rounds went wrong:
- `ctypes.dlopen` / `dlsym` / `get_last_error` — loading and resolving are not calling;
- `msvcrt` fd-scoped events carry a **descriptor**, not a path, so they cannot be path-judged — but the
  `open` that produced the descriptor already was, so a lock on an in-root fd is in-root by
  construction;
- `winreg` reads, enumerated.

## Docstring correction

You were right that the old wording over-claimed. It now says: the clean path **does** load and resolve
native symbols (`ctypes.dlopen` x7, `dlsym` x24, including the broker's `CreateFileW`/`NtCreateFile`);
invoking an already-resolved `WinDLL` attribute fires **no** audit event, so F10 **cannot** prove no
native write occurred — it proves this path makes no raw `ctypes.call_function`-style call and no
un-audited namespace event.

## Regressions — all three proven against pre-fix code

```
_winapi.CreateProcess (in-root, nonexistent program):
  PRE caught=False  ->  FIX caught=True
winreg.DeleteKey (nonexistent key):
  PRE caught=False  ->  FIX caught=True
os.open(O_RDONLY | O_TEMPORARY) on a pre-existing external file:
  PRE caught=False probe_destroyed=True  ->  FIX caught=True probe_destroyed=True
```

All three keep `constructed=True`, `rows=1`. Live: `violations=[]`, `client=DataApi`, `rows=1`, 32
bootstrap events buffered.

---

## State

- **275 passed** (was 272). F10 14 tests, ~11s, stable across repeat runs.
- `--plan` unchanged: 31 blocked rows, A07 still `BLOCKED(contract:fina_indicator_vip)`.
- `--fetch` still **exits 3**. No Tushare call. Probes used a nonexistent program path, a nonexistent
  registry key, a loopback bind, and purpose-made probe files.

## Review questions

1. **Is the enumeration now the right basis?** Every allowance is derived from the clean run rather than
   from my expectations, and the watched set is the union of what fires plus the reachable-but-unfired
   namespaces. Is there a namespace that would only appear under a *different* endpoint's adapter (the
   other 28 families) and so is absent from this one-page enumeration?
2. **`msvcrt` fd-scoped reasoning** — is "the fd's originating open was already judged" sound, or can a
   descriptor reach the child without a judged `open` (inherited handle, `open_osfhandle` on a raw
   handle)?
3. **Is `ctypes` default-deny worth keeping** given it cannot see the calls that matter, or does
   partial coverage risk reading as more assurance than it gives? I kept it plus an explicit limit
   statement; I would rather you rule on that than have me choose.
4. **Does this close P0-2 and open §13 authorization** for the 29 executable families?

## §10 self-review verdict

Method: reproduced all three, enumerated the full namespace, caught and fixed an error in my own
enumeration (it stopped at construction), then proved each regression fails pre-fix and passes post-fix.

On the arc: this is round 8, and the previous seven each closed a surface the round before had not
looked at. The change this round is that the basis is no longer "the surface the reviewer named" but
"every namespace the process actually emits", which is why it found `msvcrt` and `tempfile` before you
did. Question 1 is the honest residual — a one-endpoint enumeration cannot see what a different
adapter's code path might emit, and I would rather name that than let 275 green tests imply otherwise.

No PIT/lookahead surface is touched — test instrumentation only.

**Verdict: clean for GPT.**
