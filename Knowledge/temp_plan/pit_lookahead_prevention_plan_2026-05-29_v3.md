# PIT Lookahead Bug — Prevention Plan **v3** (post GPT 5.5 Pro round-2 review)

**Date:** 2026-05-29 · **Supersedes:** v2 (`..._v2.md`), v1 (`...md`). All retained for the review trail.
**Status of the immediate bug:** FOUND, FIXED, RE-MEASURED (done). This is the prevention architecture for the bug *class*; not yet implemented.
**Thesis (refined per round-2):** **one PIT-semantics _contract_, two implementations, one oracle.** A new `pit_alignment_core` backs the sandbox `pit_research_loader`; the production provider remains the **oracle** and is bound to the kernel by a differential **parity test** (not refactored on day one). Two sanctioned front doors: `qlib_windowed_features` (formal) and `pit_research_loader` (sandbox).

---

## 0. Response to round-2 review (v2 → v3 deltas)

Round-2 was repo-grounded; I **verified every factual claim against the local repo/data** before encoding it (results in §0.1). All accepted. One point is dismissed per the user.

| # | Round-2 point | v3 action | Status |
|---|---|---|---|
| Blocker 1 | `project_state.md` on public `main` still shows the invalidated "CURRENT CHAMPION" | **N/A — dismissed per user:** the invalidation *was* applied locally this session; `main` is stale only because the updated file is **not yet merged**. No plan change; ensure the branch agents use carries it. | Dismissed (merge-timing) |
| Blocker 2 | "CI required check" is aspirational — no `.github/workflows`; provider data is gitignored | **Split offline CI vs live-local QA** (§6.6); add an offline-only `ci.yml`; provider-parity stays in `run_daily_qa.py` + promotion gate | Accepted |
| Dup policy | `last_by_src_ordinal` may not work — those columns are stripped | **Verified: they ARE absent from the ledger (§0.1).** Default → `duplicate_policy="error"` (fail-closed); silent `aggfunc="last"` forbidden (§6.2) | Accepted + verified |
| Parity cond. | Provider is the oracle; widen the parity grid; don't say "single layer" literally yet | Reframed thesis; parity grid expanded (§6.5) | Accepted |
| Lag | Don't make `lag=0` the ergonomic research default (repo bans same-day raw fundamentals) | **Two-layer API**: kernel/parity default 0; research-facing default **1 or explicit-required** (§6.2) | Accepted |
| Universe | Loader reads ledger directly → must apply delist/IPO-lag bounds itself | `apply_provider_bounds=True` via `stock_basic_bounds` (verified exists); closes a *separate* survivorship leak (§6.2) | Accepted + verified |
| Archive | Migrate a live-relevant proof set before freezing the rest; extend archive-boundary test to live `workspace/` | §6.4 + §6.9 | Accepted |
| Lint | Schema-validate the allowlist; fail QA on expired/dangling entries; narrow doc/fixture text-scan exceptions | §6.3, §6.4 | Accepted |
| Settings | Create shareable `.claude/settings.json` (hooks only); keep machine perms/paths in `settings.local.json` | §6.6; verified only `settings.local.json` exists today | Accepted + verified |

### 0.1 Verification of round-2's repo claims (done this session)

- **`_src_ordinal` / `_src_file` are NOT in `data/pit_ledger/indicators/indicators.parquet`** (`False`/`False`). Confirmed: any tie-break policy keyed on those columns is unimplementable against the served ledger.
- **Duplicate `(ts_code, effective_date)` rows = 88,625 / 305,978 = 29%.** This is **not** an edge case. The old sandbox's `pivot_table(..., aggfunc="last")` collapsed ~29% of rows in pandas-internal order — **a second latent non-determinism bug** independent of the date bug. The duplicate policy is load-bearing and must be explicit + fail-closed.
- **`provider_metadata.stock_basic_bounds()` and `build_all_stocks_universe()` exist** (lines 96 / 184) — the universe-bounds requirement is actionable.
- **No `.github/workflows/`** on disk; **`.claude/` contains only `settings.local.json`** — the CI-split and settings-split points are real.

---

## 1–5. Bug context (unchanged from v2; condensed)

A lookahead bug in ~58 `workspace/scripts/sandbox_v*.py` loaders aligned fundamentals by lexically comparing dashed `effective_date` (`"2018-10-30"`) against compact `trade_date` (`"20180607"`); since `-`(0x2D) < `0`(0x30), the ffill served the year's last-published quarter (≈Q3) from January, i.e. up to ~9 months of earnings foresight. Same engine, loader-only change: v33 champion OOS **188.7%→2.0%** (MDD −33.8%→−76.3%); val_heavy candidate **+81.9%→+9.6%**, WF **+82.4%→−3.4%**. Production backend / both backtesters / orchestrator / live JoinQuant script are PIT-correct (proven) — bug was sandbox-only. Root cause: hand-rolled alignment **outside** the formal PIT perimeter, with no author/commit-time gate and no skepticism of extraordinary output. Full detail: bug report §9. Durable records already updated locally (project_state.md note, spec banners, agent memory → INVALIDATED).

**New (v3):** the duplicate-collapse finding (§0.1) means the sandbox had *two* latent defects — the date-sort leak (fixed) **and** a 29%-prevalence non-deterministic duplicate collapse. The prevention layer must close both.

---

## 6. Prevention architecture (v3)

### 6.0 Enforcement hierarchy (strongest first)

```
1. Offline CI required check  — lint + synthetic-only tests; runs WITHOUT live data (public-repo-safe)
2. git pre-commit hook        — portable local net (bypassable via --no-verify → §6.7 promotion guard backstops it)
3. Stop hook (agent)          — scans changed + untracked .py/.ipynb before the agent stops (catches Bash / multi-file / notebook writes)
4. PostToolUse Edit|Write|NotebookEdit — fast author-time feedback (NOT the boundary)
5. Live-local QA / promotion gate — provider parity, real-data regression, snapshot/hash (needs the gitignored provider; never public CI)
6. CLAUDE.md / AGENTS.md       — explanatory contract, not enforcement
```

### 6.1 `pit_alignment_core` — the semantics kernel (new)

`src/data_infra/pit_alignment_core.py::align_ledger_to_calendar(ledger_df, fields, calendar, *, availability_lag_bars, duplicate_policy)`: normalize/validate effective dates → tz-naive `datetime64`; deterministic duplicate handling; `searchsorted` onto the trading calendar; apply availability lag. **The provider is the oracle** (§6.5 parity); the kernel is *new code that must prove itself against the provider*. Refactoring the provider to call the kernel is a deferred, optional follow-up — not in this plan.

### 6.2 `pit_research_loader` — sandbox front door (thin adapter)

Reads approved ledger parquet (the **only** sanctioned raw reader) → delegates to the kernel. Three contracts hardened per round-2:

**(a) Lag — two layers, research default is NOT 0.** The repo's indicators-approval contract requires `Ref($field,1)` or stricter and **disallows same-day raw fundamental use**. Therefore:
```
kernel default / provider-parity test:  availability_lag_bars = 0   (data-as-of, matches provider)
research-facing helper default:          signal_lag_bars = 1         (or an EXPLICIT required arg, no default)
```
Concretely, expose `load_pit_asof_panel(..., availability_lag_bars=0)` (data parity) and `load_pit_signal_panel(..., signal_lag_bars=1)` (research ranking). lag=0 must never be the path of least resistance for signal construction. (My re-measurement used the historical sandbox's effective lag=1, so the corrected numbers are if anything marginally conservative — the verdict is unchanged.)

**(b) Duplicate policy — fail-closed (verified necessary, §0.1).** Default `duplicate_policy="error"`. Silent `pivot_table(..., aggfunc="last")` is forbidden. `_src_ordinal`/`_src_file` are absent from the served ledger, so policies keyed on them are unavailable. The documented *correct* policy is `"max_end_date"` (at each `(ts_code, effective_date)`, take the most-recent fiscal period = the current PIT state), and the **parity test certifies it matches the provider**. Given 29% of rows are duplicates, this is a primary code path, not a corner case.

**(c) Universe/listing bounds — closes a separate leak.** Because the loader reads the ledger directly, it bypasses the instruments-sidecar delist/IPO-lag guard. It MUST apply `provider_metadata.stock_basic_bounds()` (`apply_provider_bounds=True` default) or require an explicit PIT-safe universe object. Otherwise the sanctioned path would still carry a survivorship/listing leak (which the old sandbox scripts also had).

**Input validation (fail loudly):** `sim_dates` sorted/unique/compact `YYYYMMDD` ⊆ trading calendar; `effective_date` → tz-naive Timestamp; `fields` PIT-approved in the field registry; unknown `ledger` rejected; duplicates per (b).

### 6.3 Lint `lint_no_unsafe_pit_dates.py` (AST + text/path)

Modeled on `lint_no_bare_qlib_features.py` but **without its weak escape hatches**.
- **PIT002 raw-ledger read** (keystone, always error): AST detection across `pd.read_parquet`, `pyarrow.parquet.read_table`, `pl.read_parquet`/`pl.scan_parquet`, `duckdb...read_parquet`, `glob(...)`, `Path("...pit_ledger...")`; **plus a text/path pass** for the literal substring `pit_ledger`.
- **PIT001 unsafe date stringify** (error in alignment code; permitted at export boundaries via allowlist): `.astype(str)`/`.astype("string")`/`.map(str)`/`.apply(str)`/`.dt.strftime(...)`/`np.datetime_as_string(...)` on a known date column.
- **Scope:** `src/**/*.py`, `workspace/**/*.py`, `workspace/**/*.ipynb` (parse code cells via `nbformat`). No broad globs.
- **Text-scan exceptions** for docs/test-fixtures are **explicit and narrow** (enumerated paths), never globbed.

### 6.4 Allowlist governance (schema-validated)

`config/lint/unsafe_pit_dates_allowlist.yaml` is the **only** exemption mechanism for PIT002 (no inline `noqa` for ledger reads). Each entry: `path, rule, owner, reason, expires, permanent(bool), link`. The allowlist is **schema-validated**, and QA/CI **fail on expired entries and on any entry whose path no longer exists**. Inline reason-required suppression allowed only for PIT001 at export boundaries. Mirrors the repo's existing `config/field_registry/approvals/*.yaml` governance.

### 6.5 Behavioral invariants (tests — the real semantics guarantee)

1. **Synthetic lookahead canary** — Q3 effective in Oct; June must see Q1 (the original bug; 600519 case). *(offline)*
2. **Restatement canary** — original effective May, restatement effective July: June sees original, August may see restated. *(offline)*
3. **Duplicate canary** — duplicate `(ts_code, effective_date, field)` either errors or resolves by the documented tie-break; exercises the 29%-prevalence path. *(offline)*
4. **Availability assertion** — every served cell's `effective_date ≤ decision_date` (chronologically). *(offline, synthetic)*
5. **Loader↔provider parity (the oracle test)** *(live-local only)* — for a sampled grid: **multiple fields incl. sparse; multiple securities incl. delisted/IPO-edge; dates before-first-report / between / on-effective-date / after-restatement; both lag 0 and lag 1.** Certifies the kernel matches the provider and that `max_end_date` collapse is correct.

No broad semantic "leakage lint" yet; add classes later only after each proves low false-positive.

### 6.6 Gates: offline CI vs live-local QA (round-2 Blocker 2)

- **Offline CI** (`.github/workflows/ci.yml`, public-safe, **no live data**): the lint + its AST/text/notebook parser tests; canaries 1–4; availability assertion (synthetic); release-gate schema/unit tests.
- **Live-local QA** (`run_daily_qa.py`, needs the gitignored provider): the loader↔provider parity test (5); real 600519 regression; data snapshot/hash. Add `checks.append(_unsafe_pit_dates_lint_check())` to QA too.
- **pre-commit**: run the lint on changed files (portable; `--no-verify`-bypassable → §6.7 backstops).
- **Stop hook**: scan `git` changed + untracked `.py`/`.ipynb` before the agent stops.
- **PostToolUse `Edit|Write|NotebookEdit`** (note: include `NotebookEdit` so notebook edits are caught): fast feedback only, emit `{ "decision":"block", "reason":..., "hookSpecificOutput": { "hookEventName":"PostToolUse", "additionalContext":... } }`; narrow with `if: Edit(*.py)` (v2.1.85+); `$CLAUDE_PROJECT_DIR` paths; short timeout.
- **`.claude/settings.json` (new, committed)** holds **only project-shareable hook logic**; machine-local permissions/paths stay in `settings.local.json`. The current `settings.local.json` carries `bypassPermissions` + broad perms + local Windows paths — which is exactly why hooks are feedback, not authority, and why the shared safety file must not contain perms/paths.

### 6.7 Promotion / release gate (round-2 Q5 — highest-value control)

Extend the **existing** `release_gate.py` + `ArtifactProvenance` (schema-versioned). A privileged label (`champion`, `deployment_candidate`, `live_candidate`, `approved`) requires: primary backtest artifact; **independent PIT-correct reproduction artifact** (a second engine — EventDrivenBacktester or JoinQuant — not the sandbox loader); data snapshot/hash; loader/provider version + `profile_hash`; git SHA; PIT validation status. Required for **all** candidates regardless of magnitude (leakage can be modest); extraordinary results (e.g. OOS CAGR > 50% / Sharpe > 2) additionally **quarantine** pending reproduction. `promote_strategy` refuses unless the `unsafe_pit_dates` lint + invariants passed on the current git SHA (this is what backstops `--no-verify`).

### 6.8 Rule layer (documentation, demoted)

CLAUDE.md §3 + mirrored AGENTS.md: *"Research consumes PIT fundamentals only via `qlib_windowed_features` (formal) or `pit_research_loader` (sandbox). Raw ledger access restricted to builder/loader/audited tools; exceptions in `config/lint/unsafe_pit_dates_allowlist.yaml` (reason+expiry). Never string-compare date columns. Same-day raw fundamental use is disallowed — research panels default to signal lag 1. Enforced by `lint_no_unsafe_pit_dates.py` + CI/QA/hooks."*

### 6.9 Legacy scripts (round-2 archive answer)

**Migrate a proof set, then archive the rest.** Migrate to `pit_research_loader`: (1) one v33/v31-style champion-reproduction script, (2) one val_heavy deployment-candidate script, (3) one minimal example showing correct loader ergonomics — this proves the safe path is usable for the exact workflows that bred the bug. **Archive** the remaining ~55 to `workspace/scripts/archive/pit_lookahead_legacy_2026_05/` and exact-path-allowlist that dir (frozen/historical; "passes because archived," explicitly weaker than migrated). Extend the existing archived-not-referenced-from-`src` architecture test so that **live `workspace/` code also may not import / shell out to / path-reference** archived leakage scripts.

---

## 7. Resolved reviewer questions (from v2 §7)

1. **Parity-as-contract vs provider refactor:** parity-as-contract is sufficient for v1 of the implementation; do **not** refactor the provider now (it is the oracle). *Confirmed by reviewer.*
2. **Archive vs migrate:** archive most, migrate the live-relevant few (§6.9). *Confirmed.*
3. **Lag default:** kernel/parity 0; research-facing 1-or-explicit (§6.2a). *Confirmed.*

No open reviewer questions remain; the items below are residual risks, not decisions.

## 8. Residual coverage gaps (honest)

- Pattern-bound lint misses mixed-format merges with no stringify, same-day signal use, random-split leakage — mitigated by the behavioral invariants + promotion gate, not the lint.
- The kernel is a second implementation until/unless the provider is refactored to call it; the parity test is the only thing preventing drift, so the parity grid (§6.5.5) must stay broad.
- Stop-hook / pre-commit are bypassable; the durable backstops are offline CI + the promotion gate's git-SHA check.
- Untracked/local sandbox files (much of the `sandbox_v*` family is local, not on `main`) are invisible to public CI — the Stop hook + pre-commit + promotion gate are what cover them.
- Notebook scanning parses code cells only (outputs/widgets ignored).

## 9. Implementation sequence (round-2 ordering; invalidation already done)

```
0. (done locally this session) durable invalidation in project_state.md / specs / memory — ensure merged to the agent branch.
1. Offline CI workflow skeleton (.github/workflows/ci.yml), lint + synthetic tests only.
2. pit_alignment_core, synthetic-only tests.
3. pit_research_loader with separate as-of (lag 0) vs signal (lag 1 default/explicit) APIs; apply_provider_bounds; duplicate_policy="error" default.
4. Synthetic + restatement + duplicate + availability tests (offline).
5. Loader↔provider parity test (live/local), wired into run_daily_qa.py (NOT public CI).
6. lint_no_unsafe_pit_dates.py + schema-validated allowlist.
7. Notebook (.ipynb) parsing in lint + tests.
8. Migrate 2–3 live-relevant sandbox scripts to the loader (ergonomics proof).
9. Archive remaining legacy scripts; exact-allowlist the archive; extend the archive-boundary arch test to live workspace.
10. pre-commit + run_daily_qa integration.
11. Promotion/release-gate provenance extension + promote_strategy refusal logic.
12. .claude/settings.json hooks (PostToolUse + Stop) last, as feedback.
```

## 10. Acceptance criteria (v2 set + round-2 additions; contradiction fixed)

- Lint flags the original buggy line, all listed raw-read forms, and the literal `pit_ledger` text; passes on `load_pit_*` and allowlisted boundary code.
- Lint **errors** on any live (non-archived) `workspace/` file reading the ledger raw; the legacy scripts pass **only because** archived + exact-allowlisted (labeled weaker than migrated); no `sandbox_v*` glob exists.
- **Offline CI** runs the lint + synthetic canaries (1–4) with **no live data**.
- **Live provider parity** (5) + real 600519 regression are required by `run_daily_qa.py` + promotion, **not** public CI (unless a self-hosted data runner exists).
- Loader **fails closed** if duplicate effective-date rows need a tie-break column the ledger lacks (verified: `_src_ordinal` absent); silent `aggfunc="last"` is gone.
- Research-facing loader defaults to **signal lag 1** or requires an explicit lag choice.
- Loader applies provider universe/listing bounds (or requires an explicit PIT-safe universe).
- **≥1 formerly-live sandbox strategy migrated** to the loader before the rest are archived.
- Archived legacy scripts cannot be imported / executed / path-referenced by live `src/` **or live `workspace/`** code.
- **`.claude/settings.json` exists** and contains only project-shareable hook logic; machine-local perms/paths remain in `settings.local.json`.
- A deliberately-written `df["effective_date"].astype(str)` in a new file triggers the PostToolUse block; a ledger read introduced via `Bash` is caught by the Stop hook.
- Promotion of any strategy to `deployment_candidate`+ fails without an independent-reproduction artifact.
- Existing suites stay green; `lint_no_bare_qlib_features.py src/` stays clean.

---

*Evidence: bug report §9; logs `workspace/outputs/v32_rerun_fixed.log`, `v15o_rerun_fixed.log`; `project_state.md` top note (2026-05-29). Round-2 repo claims verified locally this session (§0.1). v1/v2 retained for the review trail.*
