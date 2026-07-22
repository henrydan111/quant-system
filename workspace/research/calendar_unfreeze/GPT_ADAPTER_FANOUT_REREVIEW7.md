# GPT §10 cross-review — fan-out re-review #7 (F10: process family + numeric loopback)

**Unit under review:** the fold of your re-review #6. Everything you have confirmed stays confirmed —
P0-1 (record identity), the runbook, the Windows-path judgement, `sys` as sole first import,
`-S` + `site.main()`, buffer-then-replay, the `json.py` shadow and DNS regressions. This is the
**process surface** and the **loopback predicate** only.

**Branch:** `calendar-unfreeze` — **pushed**. Commit `3235b8e`. One file changed:
`tests/data_infra/test_recovery_live_construction.py`.

| file | raw link |
|---|---|
| `tests/data_infra/test_recovery_live_construction.py` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/tests/data_infra/test_recovery_live_construction.py |
| `scripts/recovery_adapters.py` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/recovery_adapters.py |
| `scripts/recovery_ledger.py` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/recovery_ledger.py |

---

## P0-1 — process surface: matched by family now

You answered my question 3 with a yes, and the reading is correct: an enumerated *deny* list fails open
toward more spawning being permitted, which is not a safe opposite polarity. I accept that without
qualification.

Two things were wrong, and the second is the worse one. `os.spawnv` fires `os.spawn`, which the
exact-name list did not contain — and the unmatched event then fell into the **generic `os.*` path
check**, which *allowed* it because the program path was inside the run root. An audit hook does not
follow a child process, so the child's writes are invisible no matter where its executable lives:
**location cannot be the test**.

Now matched by family — `subprocess.*`, `os.spawn*`, `os.exec*`, `os.posix_spawn*`, `os.startfile*`,
plus `os.system` / `os.fork` / `os.forkpty` — and kept ahead of the generic path branch.

## P0-2 — loopback: a parse, not a shape

Verified your mechanism directly before changing anything:

```
bind(("localhost", 0)) SUCCEEDED despite the getaddrinfo interceptor
  event: socket.bind (<socket ...>, ('localhost', 0))
  ip_address('localhost').is_loopback                     -> ValueError -> rejected
  ip_address('127.not-a-numeric-literal.invalid')         -> ValueError -> rejected
  ip_address('::1').is_loopback                           -> True
  ip_address('127.0.0.1').is_loopback                     -> True
```

So bind resolves a **name** below the Python layer, where the interceptor cannot reach — the old
`host == "localhost" or host.startswith("127.")` was a shape test on a string standing in for an
address. The allowance now requires `ipaddress.ip_address(host).is_loopback`, and the real
construction's `('::1', 0)` still passes.

## Regressions — both proven against pre-fix code

Driven through the shadowed-`json.py` shim so they exercise buffer-then-replay as well:

```
os.spawn of a program INSIDE the run root:
  PRE-FIX  caught=False constructed=True client=DataApi rows=1   <- silent
  FIXED    caught=True  constructed=True client=DataApi rows=1
bind(("localhost", 0)):
  PRE-FIX  caught=False constructed=True client=DataApi rows=1   <- silent
  FIXED    caught=True  constructed=True client=DataApi rows=1
```

**One honest limitation, recorded in the code as well as here.** I first wrote the bind payload with
`127.not-a-numeric-literal.invalid` and the test FAILED — no violation. Diagnosis: on this machine that
name's resolution fails *before* `socket.bind` fires, so there is no event to catch and the vector
cannot be driven end to end. Only the `localhost` form is reachable as a live regression. Both strings
are rejected by the same `ipaddress` parse (probe above), but I am not claiming an end-to-end test I do
not have.

Your other answers applied as given: port is not restricted (a numeric loopback address cannot egress at
any port), and `socket.__new__` stays permitted.

Live run: `violations=[]`, `client=DataApi`, `rows=1`, 32 bootstrap events buffered — the `('::1', 0)`
bind is still allowed, so no false positive.

---

## State

- **272 passed** (was 270). F10 11 tests, ~9.6s, deterministic.
- `--plan` unchanged: 31 blocked rows, A07 still `BLOCKED(contract:fina_indicator_vip)`.
- `--fetch` still **exits 3**. No Tushare call; every probe used a nonexistent program path, a
  loopback-only bind, or a fake query.

## Review questions

1. **Is the process family list complete** for Windows — `os.startfile` is covered by prefix, but is
   there a spawn-shaped event outside the `subprocess.` / `os.spawn|exec|posix_spawn|startfile` families
   (`_winapi.CreateProcess`, `os.popen` via `subprocess`, `multiprocessing` spawn paths)?
2. **Is `ipaddress.ip_address(...).is_loopback` the right predicate**, or should the allowance be
   narrowed further to the exact addresses observed (`::1`, `127.0.0.1`)? `is_loopback` admits the whole
   `127.0.0.0/8` block, all of which is non-routable.
3. **Surfaces now**: `open` (mode/flag based), `os.*`/`shutil.*` (default-deny), `socket.*`
   (default-deny), process (family deny, checked first). Is there a fifth surface — `ctypes`
   (`ctypes.dlopen`, `ctypes.call_function`), `mmap`, `winreg`?
4. **Does this close P0-2 and open §13 authorization** for the 29 executable families?

## §10 self-review verdict

Method: reproduced both findings, then proved each new regression **fails on pre-fix code and passes on
fixed code**. The bind payload that did not work is reported as such rather than quietly swapped —
that failure is the reason I know the `127.`-shaped variant is unreachable here.

On the arc: this is the third consecutive round where the finding was "a bounded enumeration or a shape
test standing in for the real property," and the second where I had already applied the correct
inversion elsewhere and failed to carry it across. Question 3 is again me asking you to check the class
rather than asserting closure. What I can say concretely: `open` is now the only surface not expressed
as default-deny, and it is flag-based rather than name-based, so it has no unenumerated-name failure
mode — if you disagree with that reading, that is the next thing I would want challenged.

No PIT/lookahead surface is touched — test instrumentation only.

**Verdict: clean for GPT.**
