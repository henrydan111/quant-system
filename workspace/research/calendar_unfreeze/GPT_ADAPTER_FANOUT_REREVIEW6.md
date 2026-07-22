# GPT §10 cross-review — fan-out re-review #6 (F10: socket surface default-deny)

**Unit under review:** the fold of your re-review #5. Everything you confirmed stays confirmed —
P0-1, the runbook, the Windows-path judgement, `sys` as sole first import, `-S` + `site.main()`, the
buffer-then-replay design, the `json.py` shadow regression. This is the **network classifier** only.

**Branch:** `calendar-unfreeze` — **pushed**. Commit `1cafa8d`. One file changed:
`tests/data_infra/test_recovery_live_construction.py`.

| file | raw link |
|---|---|
| `tests/data_infra/test_recovery_live_construction.py` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/tests/data_infra/test_recovery_live_construction.py |
| `scripts/recovery_adapters.py` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/recovery_adapters.py |
| `src/data_infra/fetchers/__init__.py` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/src/data_infra/fetchers/__init__.py |

---

## The finding — and the honest diagnosis

Enumerated the socket surface of a real construction run before changing anything. Your description was
exact:

```
socket events during a REAL construction run:
   socket.__new__   (<socket.socket fd=-1, family=0, type=0, proto=0>, 23, 1, 0)
   socket.bind      (<socket.socket fd=1800, family=23, type=1, proto=0>, ('::1', 0))
event fired by gethostbyname: ['socket.gethostbyname']
```

**This is the same defect as the previous round.** I inverted `os.*`/`shutil.*` to default-deny and left
`socket.*` as the enumerated pair — the fix was applied to an *instance* of the surface rather than to
the surface. Enumerating the forbidden set fails open on everything not named, which is precisely how
`os.utime` got through one round earlier. I do not have a defence for that; I had the correct principle
in hand and did not carry it across.

## The fix

`socket.*` is now default-deny on the same principle. The two events a clean run performs are permitted
under a **strict condition on their arguments**, not by name:

- `socket.__new__` — allocating a socket object is not I/O; every *use* of it is judged;
- `socket.bind` — only when the address is a **loopback literal** (`::1` / `127.x` / `localhost`), which
  cannot leave the host. A bind to a routable address fails.

Everything else — all name resolution, all connects, all sends — is a violation.

**Enforcement added alongside recording**, since recording alone would let a resolution actually reach
DNS before the test noticed after the fact: `gethostbyname`, `gethostbyname_ex`, `getaddrinfo` and
`create_connection` now record **and raise**. `_NoNet` only ever covered `connect`/`connect_ex`.

## The regression — proven, and driven through the bootstrap path

```
bootstrap gethostbyname("localhost") against:
  PRE-FIX  caught=False  constructed=True  client=DataApi  rows=1   <- silent
  FIXED    caught=True   constructed=True  client=DataApi  rows=1
```

Driven from the shadowed `json.py` so it also exercises buffer-then-replay, and it asserts exactly what
you asked: the violation is recorded, and the real `DataApi` plus the single-page execution still
complete.

Live run, confirming no false positive from the loopback allowance:

```
LIVE violations=[]  client=DataApi  rows=1  bootstrap_events_buffered=32
```

---

## State

- **270 passed** (was 269). F10 ~6.3s, deterministic.
- `--plan` unchanged: 31 blocked rows, A07 still `BLOCKED(contract:fina_indicator_vip)`.
- `--fetch` still **exits 3**. No Tushare call has been made.

## Review questions

1. **Is the loopback-bind allowance conditioned tightly enough?** I allow any port on a loopback
   literal, reasoning that a loopback bind cannot egress regardless of port. Would you restrict it to
   the observed port 0?
2. **Should `socket.__new__` be conditioned too** (e.g. on family/type), or is "allocation is not I/O,
   every use is judged" the right boundary?
3. **Is there a third surface I have still left enumerated?** That is the actual question this round
   raises. `open` is mode/flag-based, `os.*`/`shutil.*` and `socket.*` are now default-deny, `_PROCESS`
   is an enumerated *deny* list (failing open only toward *more* spawning being allowed — the opposite
   polarity, but I would rather you check my reasoning than take it).
4. **Does this close P0-2 and open §13 authorization** for the 29 executable families?

## §10 self-review verdict

Method: enumerated the real socket surface before designing the allowlist (as with os/shutil), then
proved the regression **fails on pre-fix code and passes on fixed code** rather than only observing it
green. Every figure was produced by running it.

I want to be direct about the arc rather than presentational: five rounds, and the last two were the
same mistake — a bounded enumeration standing in for an unbounded property, then that same fix not
carried across to a sibling surface. Question 3 above is me asking you to check the thing I keep
getting wrong, rather than asserting I have finally covered it. The one structural claim I will make is
that all four surfaces now share a single classifier with a single start time, so a future gap should be
visible as a missing *surface* rather than a missing *event*.

No PIT/lookahead surface is touched — test instrumentation only.

**Verdict: clean for GPT.**
