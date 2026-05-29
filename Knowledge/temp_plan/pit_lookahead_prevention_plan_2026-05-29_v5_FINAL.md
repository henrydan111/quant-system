# PIT Lookahead Bug — Prevention Plan **v5 (FINAL / approved baseline)**

**Date:** 2026-05-29 · **Supersedes:** v4/v3/v2/v1 (retained for the review trail).
**Review status:** **APPROVED for implementation.** GPT 5.5 Pro round-4: *"After the three blocking implementation edits above, I would stop iterating the plan and start implementation."* All 3 blocking + 6 cleanup items are folded in below. No open design questions remain.
**Round-5 sign-off (final):** GPT 5.5 Pro: *"Approve v5. No new architecture blockers. I would not add another design-review round."* Three implementation-precision notes applied: (1) `duplicate_policy` value renamed `provider_q0_max_end_date` → **`provider_stateful_q0`** so the name cannot invite the local-`max(end_date)` mistake the stateful contract forbids; (2) un-track / sanitize the committed `.claude/settings.local.json` before the hooks land (§6.6, §9 step 12); (3) keep PIT001 genuinely warning-first (§6.3 — already specified). The review loop is CLOSED.
**Thesis (stable):** one PIT-semantics *contract*, two implementations, one oracle. New `pit_alignment_core` backs the sandbox `pit_research_loader`; the production provider stays the **oracle**, bound by a differential parity test (no provider surgery now). Front doors: `qlib_windowed_features` (formal), `pit_research_loader` (sandbox).

---

## 0. Response to round-4 (v4 → v5 deltas)

| # | Round-4 edit | v5 change | §ref |
|---|---|---|---|
| **Blocking 1** | q0 must be **stateful** across all visible fiscal periods, not "max `end_date` among rows sharing the current `effective_date`"; a restatement of an *older* period must not demote q0; do not drop NaN before determining q0 | §6.2b rewritten to a running-state q0 contract; **two new canaries** (stateful-restatement q0, missing-field q0) | §6.2b, §6.5.3 |
| **Blocking 2** | Hook `if: Edit(*.py)` on a combined matcher can silently drop `Write`/`NotebookEdit` and `.ipynb` | §6.6: single matcher `Edit\|Write\|NotebookEdit` with **no `if`** (script filters by `tool_name`/`file_path`/changed files) — or separate per-tool handlers; `NotebookEdit` carries no `*.py` filter; test proves Write+NotebookEdit covered | §6.6 |
| **Blocking 3** | `provider_canonicalize_snapshot` is incomplete — provider uses **`report_type` priority before `update_flag`** for statement families | §6.2b: **not user-exposed in v1**; default `error`; `provider_stateful_q0` only for Case A; canonicalization is dataset-specific + parity-tested before exposure | §6.2b |
| Cleanup 1 | Stale-merge note outdated — invalidation banner is now on public `main` | §1 note updated to "merged to public main 2026-05-29; keep local agent branches rebased" | §1 |
| Cleanup 2 | Define when `live_provider_parity: not_required_for_label` is legal | §6.7 | §6.7 |
| Cleanup 3 | Vectorize/memoize provider bounds (don't call per cell) | §6.2c | §6.2c |
| Cleanup 4 | Stage PIT001 (PIT002 hard-error first; PIT001 warn→error) | §6.3 | §6.3 |
| Cleanup 5 | Field-registry mapping test — `fields=["roa"]` ≡ `$roa`/q0 identity; can't bypass field-status governance by dropping `$` | §6.2d, §10 | §6.2d |
| Cleanup 6 | Add round-4 acceptance criteria | §10 | §10 |

All round-4 repo claims (provider stateful materialization, `report_type` priority, public-main banner, `.claude/` state, release-gate alignment, QA integration point) match what was verified locally in v3/v4 §0.1; no new probes required (these are design constraints certified by the parity test, §6.5.5).

---

## 1. Bug context (stable; condensed — full detail in bug report §9)

Lookahead in ~58 `sandbox_v*` loaders: dashed `effective_date` ("2018-10-30") lexically compared to compact `trade_date` ("20180607"); `-`<digits ⇒ ffill served the year's last quarter (≈Q3) from January (~9mo foresight). Same engine, loader-only change: v33 champion OOS **188.7%→2.0%** (MDD −33.8%→−76.3%); val_heavy **+81.9%→+9.6%**, WF **+82.4%→−3.4%**. Production backend / both backtesters / orchestrator / live JoinQuant script are PIT-correct (proven) — sandbox-only bug. Two latent defects: the date-sort leak (fixed) **and** a 29%-prevalence non-deterministic duplicate collapse (`aggfunc="last"`), addressed by §6.2b. **Durable invalidation merged to public `main` 2026-05-29** (keep local agent branches rebased).

---

## 6. Prevention architecture (v5)

### 6.0 Enforcement hierarchy (strongest first)

```
1. Offline CI required check    — lint + synthetic-only tests; NO live data (public-repo-safe)
2. git pre-commit               — portable local net
3. Stop hook (agent)            — scans changed + untracked .py/.ipynb before stop (catches Bash / multi-file / notebook writes)
4. PostToolUse Edit|Write|NotebookEdit — fast author-time feedback (NOT the boundary)
5. Live-local QA / promotion    — provider parity, real-data regression, snapshot/hash (gitignored provider; never public CI)
6. CLAUDE.md / AGENTS.md         — explanatory contract, not enforcement
```

### 6.1 `pit_alignment_core` — semantics kernel (new)

`align_ledger_to_calendar(ledger_df, fields, calendar, *, availability_lag_bars, duplicate_policy)`: normalize→tz-naive `datetime64`; **stateful q0** per §6.2b; `searchsorted` onto the calendar; apply lag. The provider is the **oracle** (§6.5.5 parity certifies the kernel). Provider→kernel refactor is a deferred, optional follow-up, not in this plan.

### 6.2 `pit_research_loader` — sandbox front door (thin adapter)

**(a) Lag — two layers; research default is NOT 0** (repo bans same-day raw fundamentals; requires `Ref(.,1)`/shift):
```
kernel / provider-parity:                 availability_lag_bars = 0   (data-as-of, matches provider)
research helper (load_pit_signal_panel):  signal_lag_bars = 1         (or explicit-required; no silent 0)
```
`load_pit_asof_panel(availability_lag_bars=0)` (data parity) and `load_pit_signal_panel(signal_lag_bars=1)` (research). lag=0 must never be the easy path for signal construction.

**(b) Duplicate / q0 — fail-closed, STATEFUL (blocking 1 + 3):**
```
duplicate_policy: Literal["error", "provider_stateful_q0"]   # default "error"
# "provider_canonicalize_snapshot" is NOT exposed in v1 (blocking 3)
```
- **Case A — multiple fiscal periods visible (the 29% workhorse).** q0 is determined by a **running state machine**, mirroring the provider's `materialize_visibility_segments`: maintain per-`end_date` latest-known state over the as-of window; at date T, **q0 = the value for the maximum `end_date` whose disclosure is visible by T**. A later restatement of an *older* `end_date` updates that older period's state but **does NOT demote q0** while a newer `end_date` is already visible. This is NOT a per-`effective_date` local `max(end_date)` collapse + ffill (which would wrongly demote q0 on an old-period restatement). **q0 is selected by `end_date` visibility, then the field value is read (NaN included) — never `dropna(subset=[field])` before q0 selection** (the provider fills NaN and only updates a segment on a non-null slot row; pre-filtering would select an older period and diverge).
- **Case B — identical same-`(ts,eff,end,field)` repeats** (verified: 32-row pool, 0 conflicting `roa`): de-duplicate deterministically, record count.
- **Case C — conflicting same-`(ts,eff,end,field)`** (verified: ~0 today): **fail closed** (`error`). The provider's true canonicalization is dataset-specific — `canonicalize_report_variants` orders by **`report_type` priority → `update_flag` → disclosure/f_ann/ann date → non-null payload count → deterministic tail/row-hash** — and statement families (e.g. `balancesheet`) differ from `indicators`. `provider_canonicalize_snapshot(dataset=...)` is therefore **not exposed until encoded + parity-tested per dataset**.

Silent `pivot_table(aggfunc="last")` forbidden. `_src_ordinal`/`_src_file` are absent from the served ledger (verified) → no policy may key on them.

**(c) Universe/listing bounds — vectorized (cleanup 3):** `apply_provider_bounds=True` default. Precompute `ts_code → (effective_list_date, delist_date)` once via `provider_metadata.stock_basic_bounds()`/`build_all_stocks_universe()`, then mask the panel **vectorized by date index** (never per-`(ts,date)` cell — keep the safe loader fast so agents don't route around it). Closes the separate survivorship/IPO-lag leak that direct-ledger reads carry. Alternatively the caller passes an explicit PIT-safe universe.

**(d) Field mapping — explicit, governed, narrow v1 (cleanup 5):** `fields=["roa"]` returns the **provider-compatible q0 alias** (ledger payload column at q0) and resolves to the **same field identity as `$roa`** — a raw loader field name must NOT bypass field-status governance merely by lacking the Qlib `$` prefix (regression-tested). Slot-depth fields (`roa_q0`, `roa_q1`, …) are out of scope for loader v1 unless explicitly requested *and* parity-tested.

**Input validation (fail loudly):** `sim_dates` sorted/unique/compact `YYYYMMDD` ⊆ calendar; `effective_date`→tz-naive Timestamp; `fields` PIT-approved in the field registry; unknown `ledger` rejected; duplicates per (b).

### 6.3 Lint `lint_no_unsafe_pit_dates.py` — AST + token-aware, staged (cleanup 4)

- **PIT002 raw-ledger read — keystone, HARD ERROR from day one:**
  - **AST pass:** `pd.read_parquet`, `pyarrow.parquet.read_table`, `pl.read_parquet`/`scan_parquet`, `duckdb…read_parquet`, `glob(...)`, `Path("…pit_ledger…")`.
  - **Token pass (NOT literal text):** flag `STRING` tokens containing `pit_ledger` only when **not** inside a docstring/comment/markdown cell (`collect_docstring_ranges(tree)` + `tokenize`). Verified: does NOT flag `provider_metadata.py:106`'s safety docstring (permanent must-not-flag fixture).
- **PIT001 unsafe date stringify — sink-aware, STAGED:** detect `.astype(str)`/`.astype("string")`/`.map(str)`/`.apply(str)`/`.dt.strftime(...)`/`np.datetime_as_string(...)` on a known date column. **Phase 1:** warning, + hard error only when the result flows into an alignment sink *within the same function* (sort/`sorted`, merge/join/`merge_asof` key, comparison, reindex/union/`Index(...)`, ffill/bfill, assignment back to a date column used downstream). **Phase 2:** promote to hard error after tuning against repo fixtures. Export/display/API/filename boundaries → reason-required inline suppression.
- **Scope:** `src/**/*.py`, `workspace/**/*.py`, `workspace/**/*.ipynb` (code cells via `nbformat`). No broad globs.

### 6.4 Allowlist governance (schema-validated)

`config/lint/unsafe_pit_dates_allowlist.yaml` is the only PIT002 exemption (no inline `noqa` for ledger reads). Entry: `path, rule, owner, reason, expires, permanent(bool), link`. Schema-validated; QA/CI fail on **expired** entries and entries whose **path no longer exists**. PIT001 export-boundary suppressions are reason-required inline.

### 6.5 Behavioral invariants (tests)

1. **Synthetic lookahead canary** — Q3 effective Oct; June sees Q1. *(offline)*
2. **Restatement canary** — original May / restatement July; June sees original, Aug may see restated. *(offline)*
3. **q0 canaries — three (blocking 1):**
   - **(A) multi-period:** same `eff`, different `end_date` → q0 = latest visible `end_date`, matches provider alias.
   - **(stateful restatement):** eff 2020-05-01 Q1=10; eff 2020-08-01 Q2=20; eff 2020-09-01 restated Q1=11 → on 2020-09-15 the **q0 alias stays Q2=20** (older restatement updates the older slot, does not demote q0).
   - **(missing-field):** latest visible period's requested field is NaN → q0 alias matches provider (no `dropna` before q0 selection). *(offline synthetic; A also live-parity'd)*
4. **Availability assertion — layer-specific:** as-of: `source_effective_date ≤ decision_date`; signal (lag 1): `source_effective_date < decision_date` or `≤ previous_trading_date(decision_date)`. *(offline)*
5. **Loader↔provider parity (the oracle test)** *(live-local only)* — sampled grid spanning multiple fields incl. sparse; multiple securities incl. delisted/IPO-edge; dates before-first / between / on-effective / **after-restatement**; both lag 0 and 1. Certifies kernel == provider, incl. the stateful-q0 behavior.

(Case C / true-conflict canary: default `error` fires; provider-canonical mode is deferred with the feature.)

### 6.6 Gates: offline CI vs live-local QA (+ hook config fix, blocking 2)

- **Offline CI** (`.github/workflows/ci.yml`, public-safe): lint + AST/token/notebook tests; canaries 1–4; availability assertion; release-gate schema/unit tests. No live data.
- **Live-local QA** (`run_daily_qa.py`): parity test (5); real 600519 regression; data snapshot/hash; + `_unsafe_pit_dates_lint_check()`.
- **pre-commit**: lint on changed files. **Stop hook**: scan `git` changed + untracked `.py`/`.ipynb` before stop (catches Bash-created files that bypass Edit/Write/NotebookEdit).
- **PostToolUse hook (blocking 2):** **single matcher `Edit|Write|NotebookEdit` with NO `if`** — the hook script inspects `tool_name` + `tool_input.file_path` (+ changed files) and filters by extension itself. (Avoids the trap where `if: Edit(*.py)` on a combined matcher fires only for `Edit` and misses `Write`/`.ipynb`.) If `if` is used, it must be **separate per-tool handlers**, and the `NotebookEdit` handler carries no `*.py` filter. Output shape: `{ "decision":"block", "reason":…, "hookSpecificOutput": {"hookEventName":"PostToolUse","additionalContext":…} }`; `$CLAUDE_PROJECT_DIR`; short timeout. A test must prove Write- and NotebookEdit-created violations are caught.
- **`.claude/settings.json` (new, committed)**: project-shareable hooks only; machine perms/paths stay in `settings.local.json`. **Hygiene (round-5 note 2):** `settings.local.json` is currently *tracked* on `main` and carries `bypassPermissions` + local Windows paths — un-track it (gitignore) or replace with a sanitized `settings.local.example.json` before the hooks land. This is exactly why hooks are feedback, not authority.

### 6.7 Promotion / release gate (independent input reconstruction + artifact)

Extend the existing `release_gate.py` + `ArtifactProvenance` (schema v2). A privileged label (`champion`/`deployment_candidate`/`live_candidate`/`approved`) requires an **independent PIT-correct reproduction that rebuilds the signal/factor panel through an independent data path** — one of: (1) formal provider via `qlib_windowed_features`, (2) JoinQuant native PIT + `pubDate`, (3) another audited PIT source declared in provenance. **Insufficient:** passing a sandbox-produced signal matrix into a second execution engine. Required for all candidates; extraordinary results (OOS CAGR > 50% / Sharpe > 2) additionally **quarantine** pending reproduction. Artifact:
```json
{ "git_sha": "...", "dirty_tree": false,
  "unsafe_pit_dates_lint": "passed",
  "synthetic_lookahead_canary": "passed", "restatement_canary": "passed",
  "q0_canary_multiperiod": "passed", "q0_canary_stateful_restatement": "passed", "q0_canary_missing_field": "passed",
  "availability_assertion": "passed",
  "live_provider_parity": "passed | not_required_for_label",
  "independent_reproduction": "qlib_windowed_features | joinquant | <audited_source> | none",
  "generated_at": "..." }
```
**`live_provider_parity: not_required_for_label` is legal ONLY when** (cleanup 2): the primary artifact did not use `pit_research_loader`, AND the independent reproduction used `qlib_windowed_features` or JoinQuant-native PIT, AND no sandbox-produced PIT panel enters the promoted result. If `pit_research_loader` is used anywhere in the primary or reproduction path → must be `passed`. `promote_strategy` rejects if `artifact.git_sha != git rev-parse HEAD`, if `dirty_tree` (uncommitted changes in scanned paths), or if `independent_reproduction == none`.

### 6.8 Rule layer (documentation, demoted) & 6.9 legacy

Rule layer: CLAUDE.md §3 + AGENTS.md mirror — consume PIT fundamentals only via `qlib_windowed_features` (formal) / `pit_research_loader` (sandbox); raw ledger access restricted to builder/loader/audited tools (exceptions in allowlist YAML); never string-compare date columns; research defaults to signal lag 1; enforced by the lint + CI/QA/hooks.
Legacy: migrate a proof set — (1) one v33/v31 champion-reproduction, (2) one val_heavy candidate, (3) one minimal ergonomics example — then archive the remaining ~55 to `workspace/scripts/archive/pit_lookahead_legacy_2026_05/` (exact-path-allowlisted, "passes because archived" = weaker than migrated). Extend the archived-not-referenced arch test so **live `workspace/`** code also may not import/shell/path-reference archived leakage scripts.

---

## 8. Residual coverage gaps (honest)

- Pattern-bound lint misses mixed-format merges with no stringify, same-day signal use, random-split leakage — covered by invariants + promotion gate, not the lint.
- Kernel is a 2nd implementation until/unless the provider is refactored; the broad parity grid (§6.5.5) is the only drift guard.
- Sink-aware PIT001 may miss cross-function sinks / over-flag — the staged rollout (warn→error) mitigates before it can be distrusted.
- Case C is empirically ~empty; fail-closed default + the deferred dataset-specific canonicalization handle growth.
- Stop-hook / pre-commit are bypassable; durable backstops are offline CI + the promotion gate's git-SHA/independent-repro check.
- Untracked/local `sandbox_v*` files are invisible to public CI; Stop hook + pre-commit + promotion gate cover them.

## 9. Implementation sequence

```
0. (done, merged to main) durable invalidation — keep local agent branches rebased.
1. Offline CI skeleton (.github/workflows/ci.yml): lint + synthetic tests only.
2. Linter MINIMAL shell (PIT002 hard-error) + schema-validated allowlist — early, before kernel/loader (false-positive feedback first).
3. pit_alignment_core (stateful q0) + synthetic tests.
4. pit_research_loader: as-of(0) vs signal(1); apply_provider_bounds (vectorized); duplicate_policy default "error", "provider_stateful_q0" Case A only; q0-alias fields only (field-identity governed).
5. q0 canaries (multiperiod + stateful-restatement + missing-field) + restatement + availability tests (offline).
6. Live provider parity (live/local) → run_daily_qa.py (NOT public CI).
7. Full linter expansion (sink-aware PIT001 phase 1) + notebook parser + provider_metadata must-not-flag fixture + field-identity test.
8. Migrate 2–3 live-relevant sandbox scripts (ergonomics proof).
9. Archive remaining legacy scripts; exact-allowlist; extend archive-boundary arch test to live workspace.
10. pre-commit + run_daily_qa integration.
11. Promotion/release-gate extension (independent-repro + artifact schema) + promote_strategy refusal.
12. .claude/settings.json hooks (PostToolUse single-matcher + Stop) last, as feedback; un-track / sanitize the committed settings.local.json in the same step. Then PIT001 phase 2 (hard error) after fixture tuning.
```

## 10. Acceptance criteria

- Lint flags the original buggy line, all listed raw-read forms, and `pit_ledger` string-literals-in-code (not docstrings); **does not flag `provider_metadata.py:106`**; passes on `load_pit_*` + allowlisted boundaries.
- Lint **errors** on any live (non-archived) `workspace/` file reading the ledger raw; legacy scripts pass only because archived+exact-allowlisted (labeled weaker than migrated); no `sandbox_v*` glob.
- Offline CI runs lint + canaries 1–4 with no live data; live parity (5) + 600519 regression required by `run_daily_qa.py` + promotion, not public CI.
- **Stateful-q0 canary:** a later restatement of an older `end_date` updates the older state but does not become q0 while a newer `end_date` is visible.
- **Missing-field q0 canary:** loader does not `dropna` before determining q0; NaN behavior matches provider.
- Loader **fails closed** on Case C and on any tie-break needing an absent column; silent `aggfunc="last"` gone; Case-A q0 = stateful latest visible `end_date` matches provider; **`provider_canonicalize_snapshot` not exposed in v1** unless dataset-specific + parity-tested.
- Research loader defaults to **signal lag 1** or requires explicit lag; signal-layer availability assertion is the stricter `<`/prev-trading-day form.
- Loader applies provider bounds **vectorized** (or explicit universe); returns **q0 aliases only** in v1; `fields=["roa"]` resolves to the same field identity as `$roa` and cannot bypass field-status governance.
- **≥1 live-relevant sandbox strategy migrated** before the rest are archived; archived scripts not importable/executable/path-referenced by live `src/` **or** live `workspace/`.
- **`.claude/settings.json` exists**, shareable hook logic only; machine perms/paths stay local. **Hook test proves Write- and NotebookEdit-created violations are caught** (not just Edit); Stop hook catches a `Bash`-introduced ledger read.
- Promotion to `deployment_candidate`+ **fails without an independent-reproduction artifact that rebuilt the panel via a PIT-correct data path**; `not_required_for_label` only when no `pit_research_loader` panel enters primary or reproduction.
- Existing suites green; `lint_no_bare_qlib_features.py src/` clean.

---

*Evidence: bug report §9; logs `v32_rerun_fixed.log`, `v15o_rerun_fixed.log`; `project_state.md` note (merged to main 2026-05-29). Repo/data claims verified locally (v3/v4 §0.1). v1–v4 retained for the review trail. **Status: APPROVED — ready to implement per §9.***
