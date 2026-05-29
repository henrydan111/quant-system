# PIT Lookahead Bug — Prevention Plan **v2** (post GPT 5.5 Pro review)

**Date:** 2026-05-29 · **Supersedes:** `pit_lookahead_prevention_plan_2026-05-29.md` (v1)
**Status of the immediate bug:** FOUND, FIXED, RE-MEASURED (done). This plan is the **prevention architecture** for the bug *class*; not yet implemented.
**Reframed thesis (per review):** this is **not** "a new sandbox loader + a lint." It is **one PIT-semantics layer, enforced everywhere, with a lightweight adapter for sandbox use.** One alignment implementation, two sanctioned front doors (`qlib_windowed_features` for formal/provider; `pit_research_loader` for sandbox).

---

## 0. Response to the v1 review (what changed and why)

GPT 5.5 Pro's review was accepted almost in full. Mapping:

| # | Review point | Action in v2 | Accept / Diverge |
|---|---|---|---|
| Main | Loader must not become a 2nd PIT impl; make it a facade over a shared kernel | §6.1 `pit_alignment_core` kernel; loader is a thin adapter; **parity test is the binding contract** | Accept, with **one divergence** (§7.1): I will *not* refactor the working provider to call the kernel on day one — that is risky surgery on the one component that works. The kernel is new; the provider is bound to it by a differential **parity test**, and calling-the-kernel-directly is a later, optional refactor. |
| Q1 | Lightweight loader, as facade | §6.1–6.2 | Accept |
| Q2 | Lint covers `workspace/**/*.py` + `**/*.ipynb` + `src/**`; no broad globs | §6.3, §6.4 | Accept |
| Q2b | Acceptance-criteria contradiction (fixed legacy scripts still read ledger raw → would fail rule #2) | §6.4 + §9: **archive all 58 fixed scripts to `workspace/scripts/archive/` and exact-path-allowlist that dir** (matches existing PR-7 archive convention); resurrecting one requires migrating to the loader. "Passes because archived" is explicitly marked weaker than "passes because migrated." | Accept (contradiction resolved) |
| Q3 | No inline `noqa` for ledger reads; committed allowlist YAML w/ owner+reason+expiry | §6.4 — mirrors the repo's existing `config/field_registry/approvals/*.yaml` governance pattern | Accept |
| Q4 | Keep lint narrow; prefer behavioral invariants over a broad leakage lint | §6.5 | Accept |
| Q5 | Cross-check = release gate, required for ALL deployment candidates (not only extraordinary) | §6.7 — grounded in the **existing** `release_gate.py` + `ArtifactProvenance` machinery (extend, don't reinvent) | Accept |
| Q6 | CI/pre-commit/QA = enforcement; hooks = feedback; add a **Stop hook**; `settings.json` IS shareable if committed | §6.6 (corrected) | Accept (v1 was wrong on shareability) |
| A | Loader: rename `shift`→`availability_lag_bars`; clarify double-lag; aggressive validation; parity tests | §6.2 | Accept (incl. the lag-semantics decision, §6.2) |
| B | Lint: AST **+ text/path** scan; cover pyarrow/polars/duckdb/glob/Path; expand date-conversion set; error only outside boundary code | §6.3 | Accept |
| C | Hook: `hookSpecificOutput.additionalContext` shape; add Stop hook for Bash/multi-file | §6.6 | Accept |
| D | Add explicit CI; promotion command depends on fresh QA artifact | §6.6, §6.7 | Accept |
| E | Add restatement + duplicate-effective-date canaries | §6.5 | Accept |
| F | Keep rules but demote to documentation | §6.8 | Accept |

The §1–5 bug-context sections are unchanged from v1 (the review validated them); condensed here for self-containment.

---

## 1. Executive summary (condensed)

A PIT lookahead bug lived in ~58 `workspace/scripts/sandbox_v*.py` loaders that read the raw PIT ledger directly and aligned fundamentals by **lexically comparing a dashed `effective_date` string (`"2018-10-30"`) against a compact `trade_date` string (`"20180607"`)**. Because `-`(0x2D) < `0`(0x30), every dashed report date sorted below January's compact trade dates, so the forward-fill served the calendar year's last-published quarter from January onward — up to ~9 months of earnings foresight on every fundamental factor and the eligibility filter.

Same engine, loader as the only changed variable: v33 champion OOS CAGR **188.7%→2.0%** (MDD −33.8%→−76.3%); val_heavy deployment candidate **+81.9%→+9.6%** CAGR, WF **+82.4%→−3.4% (negative)**, 0/18 configs pass. The production backend, both backtesters, the orchestrator, and the live JoinQuant script are PIT-correct and were never affected — the bug was confined to the bypass path.

**Why fix the class:** a strategy with negative true walk-forward was a deployment candidate purely on phantom (leaked) numbers. The instance is patched; nothing yet stops the next session from re-creating it.

## 2. Mechanism, evidence, scope (condensed; full detail in the bug report §9)

- **Mechanism / evidence:** `effective_date` is `datetime64`; `.astype(str)` renders dashed ISO, then a lexical `sorted(set(dashed) | set(compact))` + `ffill` mis-orders the timeline. Reproduced on 600519 (June-2018 served Q3 `roa=25.25` vs correct Q1 `9.05`).
- **Scope verdict (proven):** the production path normalizes every date via `normalize_date_series()`→`datetime64` and aligns with `calendar.searchsorted()` on a `DatetimeIndex` (Timestamp comparisons, never strings). The live Qlib provider serves `$roa` stepping exactly on each report's `effective_date`. The JoinQuant deploy script uses native `get_fundamentals(date=)`+`pubDate` filtering. Bug = sandbox-only.

## 3. Root cause (why existing guards missed it)

1. Reinvention of solved logic (the agent ignored the "reuse before reinvent" rule because hand-rolling was faster).
2. The bypass sat **outside** the PR1–9c enforcement perimeter (which only guards the formal `qlib_windowed_features`→provider path).
3. No author-time or commit-time gate (the one existing lint runs only in manually-invoked daily QA, never run during sandbox iteration).
4. No skepticism of extraordinary output (188% OOS was promoted, not quarantined).

**Synthesis:** only controls the harness/CI enforces automatically would have stopped this. Rules-you-must-remember and QA-you-must-run are necessary but insufficient.

## 4. Already done (context only)

58 loaders patched (compact normalization + per-script `\d{8}` assertion); re-measurement logged; durable records updated (`project_state.md`, bug report §9, v31/v33 spec invalidation banners, agent memory flipped to INVALIDATED).

---

## 6. Prevention architecture (v2)

### 6.0 Principle & enforcement hierarchy

One PIT-semantics layer; two front doors. Enforcement is layered by strength (strongest first):

```
1. CI required check        — non-bypassable repository truth (if/when PRs are used)
2. git pre-commit hook      — portable local net (bypassable via --no-verify; see §6.7 promotion guard)
3. Stop hook (agent)        — scans changed + untracked .py/.ipynb before the agent finishes (catches Bash-written / multi-file / notebook changes)
4. PostToolUse Edit|Write   — fast author-time feedback (NOT the primary boundary)
5. CLAUDE.md / AGENTS.md     — explanatory contract, not enforcement
```

### 6.1 `pit_alignment_core` — the single semantics kernel

New `src/data_infra/pit_alignment_core.py` exposing one function:

```python
def align_ledger_to_calendar(ledger_df, fields, calendar, *, availability_lag_bars=0,
                             duplicate_policy="last_by_src_ordinal") -> pd.DataFrame:
    # normalize/validate effective_date -> tz-naive datetime64
    # deterministic duplicate handling on (ts_code, effective_date, field)
    # searchsorted onto the trading calendar; apply availability_lag_bars
    # return panel indexed by calendar dates
```

Both front doors share this kernel's *semantics*. **Divergence from the review (§7.1):** the kernel is a **new** module; the production provider (`pit_backend.py`) is bound to it by a **differential parity test** (§6.5) rather than an immediate refactor, because refactoring the working, heavily-tested provider to call a freshly-extracted kernel is the riskiest possible move against the one component that is correct today. Migrating the provider to call the kernel directly is a later, optional step once the kernel has proven itself in the loader + parity test.

### 6.2 `pit_research_loader` — thin adapter (the sandbox front door)

```python
def load_pit_factor_panel(fields, sim_dates, *, ledger="indicators",
                          availability_lag_bars=0) -> pd.DataFrame:
    # 1. validate inputs (below)
    # 2. read approved ledger parquet (the ONLY sanctioned raw reader)
    # 3. delegate alignment to pit_alignment_core.align_ledger_to_calendar(...)
    # 4. relabel to compact YYYYMMDD for the caller
```

**Lag semantics (review point A — explicit decision):** `effective_date` is `strictly_next_open_trade_day(disclosure_date)` = the first date the value is observable. Therefore the canonical contract is **`availability_lag_bars=0`** (usable *on* `effective_date`), which matches the provider's as-of semantics and is what the parity test enforces. NOTE: the historical sandbox applied `.shift(1)` on top of `effective_date`, i.e. it was effectively `availability_lag_bars=1` (extra-conservative, not leaky). My re-measurement therefore used lag=1; the corrected numbers are if anything marginally *conservative*, and lag=0 would not rescue a −3.4% WF strategy — so the verdict is unchanged. `availability_lag_bars` is an explicit parameter, default 0, with both 0 and 1 covered by tests.

**Input validation (fail loudly):** `sim_dates` sorted/unique/compact `YYYYMMDD` and a subset of the trading calendar; `effective_date` normalizes to tz-naive Timestamp; `fields` exist and are PIT-approved in the field registry; unknown `ledger` rejected; duplicate `(ts_code, effective_date, field)` resolved by a documented deterministic tie-break (reusing the provider's `_src_ordinal` convention) or rejected.

### 6.3 Lint `lint_no_unsafe_pit_dates.py` (AST + text/path)

Two-pass, modeled on the existing `lint_no_bare_qlib_features.py` (same CLI / exit codes / project-root resolution):

- **AST pass:**
  - **PIT002 — raw ledger read:** any read targeting `pit_ledger` via `pd.read_parquet`, `pyarrow.parquet.read_table`, `pl.read_parquet`, `pl.scan_parquet`, `duckdb...read_parquet`, `glob(...)`, or `Path("...pit_ledger...")`.
  - **PIT001 — unsafe date stringify:** `.astype(str)` / `.astype("string")` / `.map(str)` / `.apply(str)` / `.dt.strftime(...)` / `np.datetime_as_string(...)` applied to a known date column (`effective_date`, `ann_date`, `f_ann_date`, `disclosure_date`, `end_date`, `trade_date`, `pubDate`, `statDate`).
- **Text/path pass:** the literal substring `pit_ledger` anywhere in a scanned file outside the allowlist — the hard-to-bypass backstop for read forms the AST misses.
- **Scope:** `src/**/*.py`, `workspace/**/*.py`, `workspace/**/*.ipynb` (parse code cells via `nbformat`). **No broad globs.**
- **Severity nuance:** PIT002 is the keystone (always error). PIT001 errors inside alignment/research code but is permitted at genuine export/display boundaries via the allowlist (§6.4) — date stringification is dangerous only for sort/join/ffill, not for filenames or API payloads.

### 6.4 Allowlist governance (no cheap escape hatch)

A committed `config/lint/unsafe_pit_dates_allowlist.yaml` (mirrors the existing `config/field_registry/approvals/*.yaml` governance, incl. owner / reason / expiry) is the **only** way to exempt a path. **No inline `# noqa` for PIT002 (raw ledger reads).** Inline reason-required suppression is permitted *only* for PIT001 at export boundaries: `# noqa: unsafe-pit-dates[PIT001] reason: export-only`. Default sanctioned entries: `src/data_infra/pit_research_loader.py`, `src/data_infra/pit_backend.py` (the builder), `tools/pit_audit/*` (schema-only). QA/CI fail if a new suppression or allowlist entry appears without `reason` (and `expires` for non-permanent ones).

**Legacy resolution (fixes the v1 contradiction):** the 58 already-fixed sandbox scripts still read the ledger raw, so they would (correctly) trip PIT002. They will be **moved to `workspace/scripts/archive/pit_lookahead_legacy_2026_05/`** (the existing PR-7 archive convention) and that exact directory exact-path-allowlisted as frozen/historical. Any script resurrected from archive must migrate to `load_pit_factor_panel` to leave the archive. This is explicitly "passes because archived," weaker than "passes because migrated."

### 6.5 Behavioral invariants (tests — where the subtle judgment lives)

1. **Synthetic lookahead canary** — Q3 effective in October; a June decision must see Q1, not Q3 (the original failure, the 600519 case).
2. **Loader↔provider parity test** — for a sampled (security, field, date) grid, `load_pit_factor_panel(..., availability_lag_bars=0)` must equal what the live Qlib provider serves. This is the binding contract that prevents semantic drift (and substitutes for refactoring the provider — §7.1).
3. **Restatement canary** — original effective in May, restatement effective in July: June sees original; August may see restated (documents intended best-known-state behavior).
4. **Duplicate-effective-date canary** — duplicate `(ts_code, effective_date, field)` rows either fail loudly or resolve by the documented deterministic tie-break.
5. **Availability assertion** — every served cell's backing `effective_date ≤ decision_date` (chronologically), asserted inside the loader.

No broad semantic "leakage lint" yet (review Q4): add lint classes later, one at a time, only after each proves low false-positive.

### 6.6 Enforcement gates (corrected hierarchy)

- **CI required check** (if/when a PR workflow exists): run the lint + the behavioral invariants; non-bypassable.
- **git pre-commit hook:** run the lint on changed files (portable; bypassable via `--no-verify`, which is why §6.7 adds a promotion guard).
- **`run_daily_qa.py`:** add `checks.append(_unsafe_pit_dates_lint_check())` mirroring the existing `_provider_manifest_check` / `_approval_evidence_binding_check` blocks (non-zero exit fails QA).
- **Stop hook (agent):** scans `git` changed + untracked `.py`/`.ipynb` once before the agent stops — catches Bash-written, generated, copied, and multi-file changes that an `Edit|Write` matcher misses.
- **PostToolUse `Edit|Write` hook:** fast author-time feedback only. On detection, emit the compatibility-safe shape:
  ```json
  { "decision": "block", "reason": "Unsafe PIT pattern: raw pit_ledger read. Use load_pit_factor_panel().",
    "hookSpecificOutput": { "hookEventName": "PostToolUse",
      "additionalContext": "Do not read data/pit_ledger directly from workspace code. Use src.data_infra.pit_research_loader.load_pit_factor_panel(...)." } }
  ```
  Narrow with `"if": "Edit(*.py)"` where available (v2.1.85+); resolve paths via `$CLAUDE_PROJECT_DIR`; short timeout. **Correction vs v1:** committing `.claude/settings.json` *does* make the hook travel with a fresh clone (only `settings.local.json` / user settings are non-shareable) — but a user can still disable hooks, which is exactly why CI/pre-commit/QA are the real boundaries.

### 6.7 Promotion / release gate (review Q5 — the highest-value control)

Extend the **existing** `src/research_orchestrator/release_gate.py` + `ArtifactProvenance` (currently schema v2) rather than adding a soft rule. A strategy may be explored freely, but to carry a privileged label (`champion`, `deployment_candidate`, `live_candidate`, `approved`) the artifact MUST contain: primary backtest artifact; an **independent PIT-correct reproduction artifact** (a second engine — EventDrivenBacktester or JoinQuant — not the sandbox loader); data snapshot/hash; loader/provider version + `profile_hash`; git commit SHA; PIT validation status. Required for **all** deployment candidates regardless of magnitude (leakage can be modest); results above an extraordinary threshold (e.g. OOS CAGR > 50% or Sharpe > 2) are additionally **quarantined** pending the reproduction. Add `promote_strategy` tooling that refuses if the `unsafe_pit_dates` lint + invariants did not pass on the current git SHA.

### 6.8 Rule layer (documentation, demoted)

CLAUDE.md §3 + mirrored AGENTS.md invariant: *"Research code consumes PIT fundamentals only through `qlib_windowed_features` (formal) or `pit_research_loader` (sandbox). Raw PIT ledger access is restricted to the builder, the loader, and audited tools. Exceptions live in `config/lint/unsafe_pit_dates_allowlist.yaml` with reason + expiry. Never string-compare date columns. Enforced by `lint_no_unsafe_pit_dates.py` + CI/QA/hooks."* Explicitly framed as explanation for the automated gates, since rules alone already failed.

---

## 7. Deliberate divergences & decisions for the reviewer

1. **Kernel extraction vs parity test (the one real divergence).** GPT offered "provider also calls the kernel where possible, *or* is covered by differential parity tests." I choose **parity-test-as-contract first; provider refactor later/optional.** Rationale: the provider is the one component proven correct (PR1–9c + on-disk verification); extracting and rewiring its alignment now risks introducing a regression into the safe path to remove duplication from the unsafe path — bad trade. The parity test gives the anti-drift guarantee without the surgery. **Question for reviewer: do you agree parity-as-contract is sufficient, or is shared-call worth the provider-refactor risk?**
2. **Legacy = archive + exact-allowlist, not migrate-all.** Migrating 58 mostly-dead exploration scripts to the loader is low-value churn; archiving + freezing them resolves the lint contradiction at far lower risk. **Question: acceptable, or do you want the live-relevant few (v31/v32/v33, val_heavy) migrated to the loader as proof-of-ergonomics?**
3. **Lag default = 0** (match provider) with lag=1 supported/tested. **Question: should the research default be the tighter 0 or the historically-conservative 1?**

## 8. Residual coverage gaps (honest)

- Pattern-bound lint misses mixed-format merges with no stringify, same-day signal use, random-split leakage — mitigated by the behavioral invariants + the promotion gate, not the lint.
- Notebook scanning depends on parsing `.ipynb` cells; outputs/widgets are ignored.
- Stop-hook relies on the agent session actually stopping in-repo; CI/pre-commit are the durable nets.
- Allowlist drift (entries never expiring) — mitigated by the `expires` field + a QA check for stale entries.

## 9. Revised sequence & acceptance criteria

Sequence (adopts the review's ordering):

1. `pit_alignment_core` (kernel) + its contract/docstring.
2. `pit_research_loader` as a thin adapter over the kernel.
3. Behavioral invariants: synthetic canary + restatement canary + duplicate canary + **loader↔provider parity test** + availability assertion.
4. Lint (AST + text/path), **no broad globs**.
5. Notebook (`.ipynb`) scanning in the lint.
6. CI required check + `run_daily_qa.py` block + pre-commit.
7. PostToolUse `Edit|Write` hook (fast feedback).
8. Stop hook scanning changed/untracked `.py`/`.ipynb`.
9. CLAUDE.md / AGENTS.md invariants (same edit pass, per the repo's dual-contract rule).
10. Promotion/release gate requiring independent PIT reproduction (extends `release_gate.py`).
11. Archive the 58 legacy scripts + seed the allowlist YAML.

Acceptance criteria (contradiction fixed):

- Lint flags the original buggy line, all listed raw-read forms, and the literal `pit_ledger` text; passes on `load_pit_factor_panel` and on allowlisted boundary code.
- Lint **errors** on any live (non-archived) `workspace/` file that reads the ledger raw; the 58 legacy scripts pass **only because** they are archived + exact-allowlisted (weaker, and labeled as such) — no `sandbox_v*` glob exists.
- Parity test: loader (lag=0) matches the live provider across the sampled grid; canaries (synthetic/restatement/duplicate) pass; a reintroduced dashed-string regression fails them.
- `run_daily_qa.py` exits non-zero on any unsafe pattern in non-allowlisted `src/`+`workspace/`.
- A deliberately-written `df["effective_date"].astype(str)` in a new file triggers the PostToolUse block with actionable `additionalContext`; the Stop hook flags a ledger read introduced via `Bash`.
- Promotion of any strategy to `deployment_candidate`+ fails without an independent-reproduction artifact.
- Existing suites stay green; `lint_no_bare_qlib_features.py src/` stays clean.

---

*Evidence: `workspace/research/jq_deployment/v33_PIT_lookahead_bug_report.md` §9; logs `workspace/outputs/v32_rerun_fixed.log`, `v15o_rerun_fixed.log`; `project_state.md` top note (2026-05-29). v1 of this plan retained alongside for the review trail.*
