# PIT Lookahead Bug — Prevention Plan **v4** (post GPT 5.5 Pro round-3 review)

**Date:** 2026-05-29 · **Supersedes:** v3/v2/v1 (all retained for the review trail).
**Review status:** round-3 verdict was *"approve v3 as implementation baseline"* with **3 blocking + 4 recommended** edits. All 7 are folded in below and each repo/data claim was **verified locally** (§0.1). This is the **implementation baseline.**
**Thesis (stable):** one PIT-semantics *contract*, two implementations, one oracle. New `pit_alignment_core` backs the sandbox `pit_research_loader`; the production provider stays the **oracle**, bound by a differential parity test (no provider surgery now). Front doors: `qlib_windowed_features` (formal), `pit_research_loader` (sandbox).

---

## 0. Response to round-3 (v3 → v4 deltas)

| # | Round-3 edit | v4 change | Status |
|---|---|---|---|
| **Blocking 1** | `max_end_date` is not a *complete* duplicate policy — split "latest visible fiscal period" (Case A) vs "true same-period conflict" (Case C) | §6.2b: `duplicate_policy ∈ {error, provider_q0_max_end_date, provider_canonicalize_snapshot}`; two distinct canaries | Accepted + **verified prevalence (§0.1)** |
| **Blocking 2** | Literal `pit_ledger` substring scan will false-positive real code (e.g. `provider_metadata` docstring) | §6.3: AST + **token/code-aware** scan that skips docstrings/comments/markdown; `provider_metadata.py` added as a "must-not-flag" fixture | Accepted + **verified false-positive (§0.1)** |
| **Blocking 3** | "Independent reproduction = a second engine" is too weak — a leaked signal survives a second backtester | §6.7: reproduction must independently **rebuild the signal/factor panel** via a PIT-correct data path; feeding a sandbox signal matrix into EventDrivenBacktester is explicitly insufficient | Accepted |
| Rec 4 | PIT001 must be **sink-aware** (date-stringify is fine at export/display) | §6.3 | Accepted |
| Rec 5 | Signal layer needs a **stricter** availability assertion than as-of | §6.5.4 | Accepted |
| Rec 6 | Define **q0 vs slot** field mapping explicitly; keep loader v1 narrow | §6.2d | Accepted |
| Rec 7 | Make the **promotion/QA artifact schema concrete** + git-SHA/dirty-tree checks | §6.7 | Accepted |
| Seq | Move a **minimal linter shell + allowlist schema early** (before kernel/loader) | §9 step 2 | Accepted |

(Round-2's stale-`project_state.md` blocker remains **N/A** — applied locally this session, pending merge.)

### 0.1 Verification of round-3's claims (done this session)

- **Duplicate structure (decides the whole duplicate-policy design):**
  - `(ts_code, effective_date)` duplicates = **88,625 / 305,978 (29%)** → **Case A** pool (multiple fiscal periods sharing one `effective_date`, different `end_date`). The 29% workhorse.
  - `(ts_code, effective_date, end_date)` duplicates = **32 rows (0.0%)** → Case B/C pool (same fiscal period repeated). Of those, **0 groups have conflicting `roa`**.
  - **Conclusion:** GPT's three-case split is the correct *design*; empirically Case A dominates and **Case C (true same-period conflict) is a negligible fail-closed tail today**. The policy must still *distinguish* them (the provider has full canonicalization logic for a reason, and the tail can grow).
- **Literal-scan false-positive confirmed:** `provider_metadata.py:106` docstring contains `data/pit_ledger/` — a naive substring scan over `src/**/*.py` would flag the exact safety helper the loader must use. The token/code-aware scan is required.

---

## 1–5. Bug context (stable; condensed — full detail in bug report §9 and v3)

Lookahead in ~58 `sandbox_v*` loaders: dashed `effective_date` ("2018-10-30") lexically compared to compact `trade_date` ("20180607"); `-`<digits ⇒ ffill served the year's last quarter (≈Q3) from January (~9mo foresight). Same engine, loader-only change: v33 champion OOS **188.7%→2.0%** (MDD −33.8%→−76.3%); val_heavy **+81.9%→+9.6%**, WF **+82.4%→−3.4%**. Production backend / both backtesters / orchestrator / live JoinQuant script are PIT-correct (proven) — sandbox-only bug. **Two latent defects:** the date-sort leak (fixed) **and** a 29%-prevalence non-deterministic duplicate collapse (`aggfunc="last"`), now addressed by §6.2b. Durable records updated locally.

---

## 6. Prevention architecture (v4)

### 6.0 Enforcement hierarchy (strongest first)

```
1. Offline CI required check   — lint + synthetic-only tests; NO live data (public-repo-safe)
2. git pre-commit              — portable local net (--no-verify-bypassable → §6.7 backstops)
3. Stop hook (agent)           — scans changed + untracked .py/.ipynb before stop (catches Bash / multi-file / notebook writes)
4. PostToolUse Edit|Write|NotebookEdit — fast author-time feedback (NOT the boundary)
5. Live-local QA / promotion   — provider parity, real-data regression, snapshot/hash (needs gitignored provider; never public CI)
6. CLAUDE.md / AGENTS.md        — explanatory contract, not enforcement
```

### 6.1 `pit_alignment_core` — semantics kernel (new)

`align_ledger_to_calendar(ledger_df, fields, calendar, *, availability_lag_bars, duplicate_policy)`: normalize→tz-naive `datetime64`; duplicate handling per §6.2b; `searchsorted` onto the calendar; apply lag. **The provider is the oracle** (§6.5.5 parity certifies the kernel). Provider→kernel refactor is a deferred, optional follow-up, not in this plan.

### 6.2 `pit_research_loader` — sandbox front door (thin adapter)

**(a) Lag — two layers; research default is NOT 0** (repo bans same-day raw fundamentals; requires `Ref(.,1)`/shift):
```
kernel / provider-parity:           availability_lag_bars = 0   (data-as-of, matches provider)
research helper (load_pit_signal_panel): signal_lag_bars = 1     (or explicit-required; no silent 0)
```
Expose `load_pit_asof_panel(availability_lag_bars=0)` (data parity) and `load_pit_signal_panel(signal_lag_bars=1)` (research). lag=0 must never be the easy path for signal construction.

**(b) Duplicate policy — fail-closed, three cases (blocking 1; prevalence verified §0.1):**
```
duplicate_policy: Literal["error", "provider_q0_max_end_date", "provider_canonicalize_snapshot"]   # default "error"
```
- **Case A** — same `(ts,eff)`, different `end_date` (the 29% workhorse): `provider_q0_max_end_date` selects the latest fiscal period = q0; **parity-certified against the provider's q0 alias.** Answers *"which fiscal period is q0?"*
- **Case B** — same `(ts,eff,end,field)`, identical value: de-duplicate deterministically, record the count.
- **Case C** — same `(ts,eff,end,field)`, *conflicting* value (today: 32-row pool, 0 conflicting for `roa` — a negligible tail, but must be distinguished): **fail closed** unless `provider_canonicalize_snapshot` implements the provider's exact version logic (update_flag → disclosure/f_ann/ann date → non-null payload count → deterministic tail/row-hash). Answers *"which row wins for the same fiscal period?"*

Silent `pivot_table(..., aggfunc="last")` is **forbidden**. `_src_ordinal`/`_src_file` are absent from the served ledger (verified v3 §0.1), so no policy may key on them.

**(c) Universe/listing bounds:** `apply_provider_bounds=True` default → `provider_metadata.stock_basic_bounds()` (delist + 90-day IPO lag), or require an explicit PIT-safe universe. Closes a *separate* survivorship/listing leak that direct-ledger reads (incl. the old sandbox) otherwise carry.

**(d) Field mapping — explicit, narrow v1 (rec 6):** `fields=["roa"]` returns the **provider-compatible q0 alias** (ledger payload column at q0). Slot-depth fields (`roa_q0`, `roa_q1`, …) are **out of scope for loader v1** unless explicitly requested *and* parity-tested.

**Input validation (fail loudly):** `sim_dates` sorted/unique/compact `YYYYMMDD` ⊆ calendar; `effective_date`→tz-naive Timestamp; `fields` PIT-approved in the field registry; unknown `ledger` rejected; duplicates per (b).

### 6.3 Lint `lint_no_unsafe_pit_dates.py` — AST + token/code-aware (blocking 2 + rec 4)

- **PIT002 raw-ledger read** (keystone, always error):
  - **AST pass:** `pd.read_parquet`, `pyarrow.parquet.read_table`, `pl.read_parquet`/`scan_parquet`, `duckdb…read_parquet`, `glob(...)`, `Path("…pit_ledger…")`.
  - **Token pass (NOT literal text):** flag `STRING` tokens containing `pit_ledger` **only when not inside a docstring/comment/markdown cell** (`collect_docstring_ranges(tree)` + `tokenize`; skip enumerated narrow doc fixtures). Still catches `ROOT/"data"/"pit_ledger"` and read-string args; does **not** flag `provider_metadata.py:106`'s safety docstring (verified §0.1) — that file is a permanent "must-not-flag" regression fixture.
- **PIT001 unsafe date stringify — sink-aware (rec 4):** `.astype(str)`/`.astype("string")`/`.map(str)`/`.apply(str)`/`.dt.strftime(...)`/`np.datetime_as_string(...)` on a known date column is an **error only when the result flows into an alignment sink** (sort/`sorted`, merge/join/`merge_asof` key, comparison, reindex/union/`Index(...)`, ffill/bfill, or assignment back into a date column used downstream). Export/display/API/filename boundaries → reason-required inline suppression (the repo legitimately strftime's dates at provider-build/instruments-export boundaries). Pragmatic fallback if full data-flow analysis is deferred: warn on the stringify, error on a detected sink in the same function.
- **Scope:** `src/**/*.py`, `workspace/**/*.py`, `workspace/**/*.ipynb` (code cells via `nbformat`). No broad globs.

### 6.4 Allowlist governance (schema-validated)

`config/lint/unsafe_pit_dates_allowlist.yaml` is the only PIT002 exemption (no inline `noqa` for ledger reads). Entry: `path, rule, owner, reason, expires, permanent(bool), link`. **Schema-validated**; QA/CI fail on **expired** entries and on entries whose **path no longer exists**. PIT001 export-boundary suppressions are reason-required inline.

### 6.5 Behavioral invariants (tests)

1. **Synthetic lookahead canary** — Q3 effective Oct; June sees Q1 (the original bug). *(offline)*
2. **Restatement canary** — original May / restatement July; June sees original, Aug may see restated. *(offline)*
3. **Duplicate canaries — two (blocking 1):** (A) same `eff`, different `end_date` → q0 = max `end_date`, matches provider alias; (C) same `eff`+`end_date`, conflicting value → default **errors**, `provider_canonicalize_snapshot` matches the provider exactly. *(offline synthetic; A also live-parity'd)*
4. **Availability assertion — layer-specific (rec 5):**
   - as-of layer: `source_effective_date ≤ decision_date`.
   - signal layer (lag 1): `source_effective_date < decision_date` **or** `≤ previous_trading_date(decision_date)`. *(offline)*
5. **Loader↔provider parity (the oracle test)** *(live-local only)* — sampled grid spanning **multiple fields incl. sparse; multiple securities incl. delisted/IPO-edge; dates before-first / between / on-effective / after-restatement; both lag 0 and 1.** Certifies kernel == provider and that Case-A q0 collapse is correct.

No broad semantic "leakage lint" yet.

### 6.6 Gates: offline CI vs live-local QA

- **Offline CI** (`.github/workflows/ci.yml`, public-safe, no data): lint + its AST/token/notebook tests; canaries 1–4; availability assertion; release-gate schema/unit tests.
- **Live-local QA** (`run_daily_qa.py`, needs the gitignored provider): parity test (5); real 600519 regression; data snapshot/hash; + `_unsafe_pit_dates_lint_check()`.
- **pre-commit**: lint on changed files.
- **Stop hook**: scan `git` changed + untracked `.py`/`.ipynb` before stop.
- **PostToolUse `Edit|Write|NotebookEdit`**: feedback only; `{ "decision":"block","reason":…, "hookSpecificOutput": {"hookEventName":"PostToolUse","additionalContext":…} }`; narrow via `if: Edit(*.py)` (v2.1.85+); `$CLAUDE_PROJECT_DIR`; short timeout.
- **`.claude/settings.json` (new, committed)**: project-shareable hooks only; machine perms/paths stay in `settings.local.json` (which today carries `bypassPermissions` + local Windows paths — exactly why hooks are feedback, not authority).

### 6.7 Promotion / release gate (blocking 3 + rec 7)

Extend the existing `release_gate.py` + `ArtifactProvenance`. A privileged label (`champion`/`deployment_candidate`/`live_candidate`/`approved`) requires an **independent PIT-correct reproduction that rebuilds the signal/factor panel through an independent data path** — one of:
1. the formal provider path via `qlib_windowed_features`,
2. JoinQuant native PIT fundamentals with `pubDate` filtering,
3. another audited PIT source declared in provenance.

**Explicitly insufficient:** passing a sandbox-produced signal matrix into a second execution engine (EventDrivenBacktester). A leaked signal survives a second backtester that only re-validates fills/costs/execution — the reproduction must reconstruct the *inputs*. Required for **all** candidates (leakage can be modest); extraordinary results (OOS CAGR > 50% / Sharpe > 2) additionally **quarantine** pending reproduction. Concrete promotion/QA artifact:
```json
{ "git_sha": "...", "dirty_tree": false,
  "unsafe_pit_dates_lint": "passed",
  "synthetic_lookahead_canary": "passed", "restatement_canary": "passed",
  "duplicate_canary_A": "passed", "duplicate_canary_C": "passed",
  "availability_assertion": "passed",
  "live_provider_parity": "passed | not_required_for_label",
  "independent_reproduction": "qlib_windowed_features | joinquant | <audited_source> | none",
  "generated_at": "..." }
```
`promote_strategy` rejects if `artifact.git_sha != git rev-parse HEAD`, if `dirty_tree` (uncommitted changes in scanned paths), or if `independent_reproduction == none`.

### 6.8 Rule layer (documentation, demoted)

CLAUDE.md §3 + AGENTS.md mirror: consume PIT fundamentals only via `qlib_windowed_features` (formal) or `pit_research_loader` (sandbox); raw ledger access restricted to builder/loader/audited tools (exceptions in the allowlist YAML); never string-compare date columns; same-day raw fundamental use disallowed (research defaults to signal lag 1); enforced by `lint_no_unsafe_pit_dates.py` + CI/QA/hooks.

### 6.9 Legacy scripts

Migrate a proof set to the loader — (1) one v33/v31 champion-reproduction, (2) one val_heavy candidate, (3) one minimal ergonomics example — then archive the remaining ~55 to `workspace/scripts/archive/pit_lookahead_legacy_2026_05/` (exact-path-allowlisted, "passes because archived" = weaker than migrated). Extend the existing archived-not-referenced-from-`src` arch test so **live `workspace/` code also may not import / shell / path-reference** archived leakage scripts.

---

## 7. Reviewer questions — all resolved

v2's three questions answered in round-2 (parity-as-contract ✓; archive-most-migrate-few ✓; lag kernel-0/research-1 ✓). Round-3 added no new open questions — only the 3 blocking + 4 recommended edits, all incorporated above. **No open decisions remain;** §8 lists residual risks only.

## 8. Residual coverage gaps (honest)

- Pattern-bound lint misses mixed-format merges with no stringify, same-day signal use, random-split leakage — covered by invariants + promotion gate, not the lint.
- The kernel is a 2nd implementation until/unless the provider is refactored; the parity grid (§6.5.5) is the only drift guard, so it must stay broad.
- Sink-aware PIT001 needs real data-flow analysis; the pragmatic same-function fallback may both miss cross-function sinks and over-flag — tune against the repo before turning it to error.
- Case C is empirically empty today (32-row tail, 0 conflicts); the fail-closed default + canary guard it if it grows.
- Stop-hook / pre-commit are bypassable; durable backstops are offline CI + the promotion gate's git-SHA/repro check.
- Untracked/local `sandbox_v*` files are invisible to public CI; Stop hook + pre-commit + promotion gate cover them.

## 9. Implementation sequence (round-3 reorder)

```
0. (done locally) durable invalidation — ensure merged to the agent branch.
1. Offline CI skeleton (.github/workflows/ci.yml): lint + synthetic tests only.
2. Linter MINIMAL shell + schema-validated allowlist (before kernel/loader → early false-positive feedback).
3. pit_alignment_core + synthetic tests.
4. pit_research_loader: as-of(0) vs signal(1) APIs; apply_provider_bounds; duplicate_policy="error"; q0-alias fields only.
5. Duplicate/provider-q0 + restatement + availability tests (offline).
6. Live provider parity test (live/local) → run_daily_qa.py (NOT public CI).
7. Full linter expansion (sink-aware PIT001) + notebook parser + provider_metadata "must-not-flag" fixture.
8. Migrate 2–3 live-relevant sandbox scripts (ergonomics proof).
9. Archive remaining legacy scripts; exact-allowlist; extend archive-boundary arch test to live workspace.
10. pre-commit + run_daily_qa integration.
11. Promotion/release-gate extension (independent-repro + artifact schema) + promote_strategy refusal.
12. .claude/settings.json hooks (PostToolUse + Stop) last, as feedback.
```

## 10. Acceptance criteria

- Lint flags the original buggy line, all listed raw-read forms, and `pit_ledger` **string-literal-in-code** (not docstrings); **does not flag `provider_metadata.py:106`**; passes on `load_pit_*` + allowlisted boundaries.
- Lint **errors** on any live (non-archived) `workspace/` file reading the ledger raw; legacy scripts pass **only because** archived+exact-allowlisted (labeled weaker than migrated); no `sandbox_v*` glob.
- **Offline CI** runs lint + canaries 1–4 with no live data.
- **Live parity** (5) + 600519 regression required by `run_daily_qa.py` + promotion, not public CI.
- Loader **fails closed** on a Case-C conflict (and on any tie-break needing an absent column); silent `aggfunc="last"` gone; Case-A q0 = max `end_date` matches provider.
- Research loader defaults to **signal lag 1** or requires explicit lag; signal-layer availability assertion is the stricter `<`/prev-trading-day form.
- Loader applies provider universe/listing bounds (or explicit PIT-safe universe); returns **q0 aliases only** in v1.
- **≥1 live-relevant sandbox strategy migrated** before the rest are archived; archived scripts not importable/executable/path-referenced by live `src/` **or** live `workspace/`.
- **`.claude/settings.json` exists**, shareable hook logic only; machine perms/paths stay local.
- PostToolUse block fires on a new `df["effective_date"].astype(str)` feeding a sort/merge; Stop hook catches a `Bash`-introduced ledger read.
- Promotion to `deployment_candidate`+ **fails without an independent-reproduction artifact that rebuilt the panel via a PIT-correct data path** (a second engine on the same signal matrix does not qualify).
- Existing suites green; `lint_no_bare_qlib_features.py src/` clean.

---

*Evidence: bug report §9; logs `v32_rerun_fixed.log`, `v15o_rerun_fixed.log`; `project_state.md` note (2026-05-29). Round-2/3 repo+data claims verified locally (§0.1 here and in v3). v1–v3 retained for the review trail.*
