# PIT Lookahead Bug — Postmortem & Prevention Plan (for GPT 5.5 Pro cross-review)

**Date:** 2026-05-29
**Status of the immediate bug:** FOUND, FIXED, RE-MEASURED (done). This plan is about **preventing the entire bug CLASS from recurring**, which is NOT yet implemented.
**What I want from this review:** adversarial critique of the prevention architecture in §6, the alternatives in §7, and especially the open decision points in §9. Tell me where this is over-engineered, where it has coverage gaps, and whether the architectural premise (a lightweight sandbox loader should exist at all) is correct.

---

## 0. How to read this document

This repo is an A-share quantitative research system (Tushare ingestion → Parquet → a custom Qlib provider → factor library → backtest engines → research orchestrator). It is operated almost entirely by an AI coding agent (Claude Code). The relevant fact for this review: the production data path already has ~6 layers of point-in-time (PIT) enforcement built over a multi-PR "freeze plan" (field registry, a mandatory `qlib_windowed_features` data-access chokepoint, an AST lint banning bare `D.features`, holdout seals, behavioral PIT tests). **The bug occurred in the ONE category of code that bypasses all of that: hand-rolled research/sandbox scripts that read the raw PIT ledger Parquet directly.**

You do not need the repo open. Everything needed to evaluate the plan is inline.

---

## 1. Executive summary

A PIT **lookahead (data-leakage)** bug lived in ~58 research scripts under `workspace/scripts/sandbox_v*.py`. Each script hand-rolled the alignment of fundamental factors onto trading dates and did it wrong: it compared a **dashed** date string (`"2018-10-30"`) against a **compact** date string (`"20180607"`) lexically. Because ASCII `-` (0x2D) sorts below every digit `0–9` (0x30+), every dashed report-effective-date sorted *below* even January's compact trade dates, so the forward-fill served the calendar year's **last-published quarter** (≈Q3, disclosed late October) from **January onward** — up to ~9 months of forward knowledge of earnings on every fundamental factor and on the universe-eligibility filter.

The leakage inflated performance enormously. On the same backtest engine, with the loader as the **only** changed variable:

| Strategy | Metric | Contaminated | Corrected (true PIT) |
|---|---|---|---|
| v33 champion (11F+roe_waa) | OOS CAGR | 188.7% | **2.0%** |
| | Max drawdown | −33.8% | **−76.3%** |
| | Walk-forward avg | ~213% | **16.9%** |
| val_heavy (deployment candidate) | CAGR | +81.9% | **+9.6%** |
| | Max drawdown | −29.2% | **−65.1%** |
| | Walk-forward avg | +82.4% | **−3.4% (negative)** |

A strategy was about to be (or had been) selected for live JoinQuant deployment on the strength of the +81.9%/+82.4% numbers. Those numbers were almost entirely earnings foresight, not tradable alpha. **This is the cost of not fixing the class: near-deployment of capital onto a phantom edge.**

The production backend, both backtest engines, the research orchestrator, AND the live JoinQuant deployment script are all PIT-correct and were never affected (proof in §2.3). The bug was confined to the bypass path.

---

## 2. The bug

### 2.1 Mechanism

The offending helper (one representative copy; the pattern repeated across the family):

```python
ind_df["effective_date"] = ind_df["effective_date"].astype(str)   # datetime64 -> "2018-10-30" (DASHED)
# ... daily panel ...
raw["trade_date"] = raw["trade_date"].astype(str)                 # -> "20180607" (COMPACT)

def build_pit_pivot(df, col):
    sub = df[["ts_code", "effective_date", col]].dropna(subset=[col])
    pv  = sub.pivot_table(index="effective_date", columns="ts_code", values=col, aggfunc="last").sort_index()
    all_d = sorted(set(pv.index.tolist()) | set(sim_dates_loc))   # MIXES dashed + compact, sorts LEXICALLY
    res = pv.reindex(all_d).ffill().reindex(sim_dates_loc)        # ffill over a non-chronological index
    return res[all_cols].shift(1)
```

`effective_date` is stored as `datetime64[ns]`; `.astype(str)` renders it ISO-dashed. The trade dates are compact `YYYYMMDD`. The lexical union sort places **all** of year Y's dashed report dates *before* `"Y0102"`, so an `ffill()` at any trade date in year Y reaches back to the **largest dashed string of that year** = Q3 (effective late-Oct), i.e. forward in real time. The trailing `.shift(1)` (a 1-trading-day buffer) does not reorder anything and does not help.

PIT-correctness is a property of **(data + alignment)**, not the data alone. The ledger's `effective_date` column is itself correct (it is `strictly_next_open_trade_day(disclosure_date)`). The hand-rolled alignment destroyed that correctness via the sort key.

### 2.2 Evidence (reproduced on disk)

For 600519.SH (贵州茅台), `roa` served by rebalance date:

| Rebalance date | Buggy serves | Quarter | Correct PIT | Quarter |
|---|---|---|---|---|
| 2018-01-08 | 25.25 | 2018Q3 | 23.64 | 2017Q3 |
| 2018-06-07 | 25.25 | 2018Q3 | **9.05** | 2018Q1 |
| 2018-09-03 | 25.25 | 2018Q3 | 17.17 | 2018Q2 |
| 2018-11-01 | 25.25 | 2018Q3 | 25.25 | 2018Q3 (now genuinely public) |

Confirmed: `"2018-10-30" < "20180607"` evaluates `True`. The minimal fix (normalize `effective_date` to compact `%Y%m%d` so lexical order = chronological order) was proven **full-series identical** to a `datetime64`-join reference.

### 2.3 Scope verdict — the bug is sandbox-only; the backend is clean

This was the load-bearing question (could the leak be in the production provider that feeds the realistic backtester?). Answer: **no.** Proof, two independent ways:

1. **Code.** Every PIT alignment in `src/` normalizes dates via `normalize_date_series()` → `datetime64`, then aligns with `calendar.searchsorted()` on a `pd.DatetimeIndex`. Comparisons are between `pd.Timestamp` objects, never strings. The only date-related `sorted(set | set)` in `src/` operates on already-normalized Timestamp keys. No `src/` module outside the (datetime-correct) builder reads the raw ledger.
2. **On-disk.** Querying the live Qlib provider, `$roa` for 600519 steps **exactly on each report's `effective_date`** (2018-05-02→9.05, 2018-08-03→17.17, 2018-10-30→25.25). June-2018 = Q1 = 9.05, not Q3.

Also verified clean: the live JoinQuant deployment script sources fundamentals via JoinQuant's native PIT API (`get_fundamentals(date=...)` + `pubDate` filtering) — point-in-time by construction, no string-date comparison. **Implication:** the live JQ code will not leak, but because it is correct it will also NOT reproduce the +82% it was selected on; a real JQ backtest would show the weak de-contaminated profile.

---

## 3. Why we must fix the class (not just the instance)

- **The instance is fixed but the gap is not.** All 58 scripts were patched (compact normalization + a per-script `assert effective_date matches \d{8}`). But the per-script assertion is narrow (catches only the exact dashed regression) and only fires if the script is run. Nothing stops the **next** session from writing `sandbox_v34.py` with the same or an adjacent leakage pattern.
- **The blast radius was real.** The bug propagated across ~30+ script iterations over an extended research arc and produced a deployment-candidate strategy whose true walk-forward is **negative**. One more step and capital would have been committed.
- **Silent failure.** Like the project's other documented "silent" traps (wrong code-format joins returning 0 rows), this produced no error — just plausible, wrong, *great-looking* numbers. Plausible-but-wrong is the worst failure mode for a research system.
- **The agent is the operator.** This system is driven by an AI agent. The fix must be robust against an *agent's* failure modes specifically (see §4), which differ from a human team's.

---

## 4. Root-cause analysis (including why existing guards missed it)

1. **Reinvention of a solved problem.** A correct, tested PIT alignment already exists in the production backend. The sandbox scripts re-implemented it by hand for speed/lightness, and got the sort key wrong. The repo's rules already say "reuse before reinvent" (CLAUDE.md §10) and "prefer the factor framework over bespoke pipelines" (§7.9) — **and the agent ignored them.** This is the critical datum: a rule in the always-loaded contract was insufficient.
2. **Bypass of the enforcement perimeter.** The PR1–PR9c freeze plan hardened the *formal* path (the orchestrator → `qlib_windowed_features` → provider). Sandbox exploration is intentionally outside that perimeter (it reads Parquet directly, no `qlib.init`, no provider build). So none of the 6 production guards applied.
3. **No author-time or commit-time gate.** The one existing lint (`lint_no_bare_qlib_features.py`) runs only inside the manual `run_daily_qa.py`. During rapid sandbox iteration, daily QA is not run. So even the analogous guard would not have fired.
4. **No skepticism of extraordinary output.** A 188% OOS CAGR was recorded as a "champion" rather than triaged as suspected leakage. The independent JoinQuant cross-check that finally surfaced the bug happened *after* the strategy was already promoted.

**Synthesis:** the only controls that would have stopped this are ones the harness/CI enforces automatically — not ones the model must remember to honor or to run.

---

## 5. Already done (immediate remediation — for context, not for review)

- Fixed all 58 `sandbox_v*` loaders: `effective_date = pd.to_datetime(...).dt.strftime("%Y%m%d")` + a permanent `assert effective_date.dropna().str.fullmatch(r"\d{8}").all()`.
- Re-measured v33 champion and val_heavy (numbers in §1); both fail every gate under true PIT.
- Updated durable records: `project_state.md` top note, the bug report (`workspace/research/jq_deployment/v33_PIT_lookahead_bug_report.md` §9), invalidation banners on v31/v33 specs, and the agent's saved memory (flipped "breakthrough" → "INVALIDATED").

---

## 6. Proposed prevention plan

### 6.1 Design principle

**Robust against an agent = enforced by the harness/CI, fired automatically, ideally at authorship time — never dependent on the model remembering a rule or remembering to run QA.** Rules and tests-you-must-run are necessary but demonstrably insufficient (§4). The plan therefore centers on automated chokepoint enforcement and mirrors the repo's own proven pattern (PR-6's `qlib_windowed_features` chokepoint + `lint_no_bare_qlib_features.py`).

### 6.2 Component A — a blessed PIT research loader *(removes the reason to hand-roll)*

New `src/data_infra/pit_research_loader.py`, the single sanctioned way for research/sandbox code to align ledger fundamentals onto a trading-date axis:

```python
def load_pit_factor_panel(fields, sim_dates, *, ledger="indicators", shift=1):
    led = pd.read_parquet(_ledger_path(ledger), columns=["ts_code", "effective_date", *fields])
    led["effective_date"] = normalize_date_series(led["effective_date"])     # reuse the backend normalizer
    sim_idx = pd.to_datetime(pd.Index(sim_dates), format="%Y%m%d")
    # pivot on datetime64 index, reindex(union(sim_idx)).ffill().reindex(sim_idx).shift(shift)
    # return panel labeled back to the caller's compact sim_dates
```

Key property: it **reuses `normalize_date_series()`** — the exact function the production backend uses — so its date semantics cannot diverge from the backend's. The lint (Component B) bans the raw-ledger read that this replaces.

### 6.3 Component B — AST lint `lint_no_unsafe_pit_dates.py` *(the keystone)*

A near-clone of `lint_no_bare_qlib_features.py` (same CLI, exit codes `0`/`1`/`2`, `--allow` globs, `# noqa: unsafe-pit-dates` per-line opt-out, `project_root` resolution). It flags two patterns:

1. **`df["<date_col>"].astype(str)`** (and the `X[c] = X[c].astype(str)` assignment form) for any known date column: `effective_date`, `ann_date`, `f_ann_date`, `disclosure_date`, `end_date`, `trade_date`, `pubDate`, `statDate`. → "stringifying a date column enables lexical-vs-chronological leakage; use `pd.to_datetime`/the loader."
2. **Direct reads of `data/pit_ledger/**.parquet`** anywhere under `workspace/` (and `src/` except the loader and the builder). → "route ledger access through `pit_research_loader.load_pit_factor_panel()`."

Rule #2 is the strong one: it eliminates the whole bug class by forcing all ledger access through one tested chokepoint, exactly as the existing lint forces all `D.features` through the windowed wrapper.

### 6.4 Component C — PostToolUse hook *(author-time gate; the agent-proofing layer)*

Wire the lint as a Claude Code `PostToolUse` hook in `settings.json` so it fires automatically the instant the agent writes/edits a Python file. **Verified hook contract** (confirmed against current Claude Code docs):

- A single matcher `"Edit|Write"` is valid; optional `"if": "Edit(*.py)"` narrows to Python files (v2.1.85+) and avoids spawning on non-Python edits.
- The hook command receives JSON on **stdin**; the edited path is `tool_input.file_path`.
- PostToolUse fires **after** the write (it cannot veto the write pre-hoc), but on `exit 0` it may emit stdout JSON `{"decision":"block","reason":"...","additionalContext":"<fix guidance>"}`. `decision:"block"` halts the turn and surfaces `reason`; **`additionalContext` is injected into the model's context as a system reminder** that drives self-correction before work proceeds.
- `$CLAUDE_PROJECT_DIR` resolves repo-relative paths; default timeout is generous (override to ~15s); multiple matching hooks run in parallel.

Net effect: the moment a future session writes a raw-ledger read or a date `.astype(str)`, the harness blocks the turn and tells the model exactly what to use instead — no reliance on the model recalling CLAUDE.md.

### 6.5 Component D — QA + pre-commit backstops *(defense in depth)*

- Add the same lint to `run_daily_qa.py` as a new `checks.append(_unsafe_pit_dates_lint_check())` audit block (mirrors the existing `_provider_manifest_check` / `_approval_evidence_binding_check` pattern; non-zero exit fails QA).
- Offer it as a git pre-commit hook so the pattern cannot be *committed* even if the live PostToolUse hook is absent (e.g., a fresh clone, or a different operator).

Three gates: author-time (hook), QA-time, commit-time.

### 6.6 Component E — synthetic-lookahead canary test *(locks the loader forever)*

A pytest mirroring the backend's behavioral PIT test: a tiny synthetic ledger with a Q3 report effective in October; assert `load_pit_factor_panel` serves Q1 (not Q3) on a June date — the exact 600519 case from §2.2. Any future regression in the loader fails CI loudly.

### 6.7 Component F — rule layer (soft, but cheap and always-loaded)

- A new CLAUDE.md §3 hard-invariant (and the mirrored AGENTS.md entry): "No hand-rolled PIT alignment; never string-compare date columns; ledger access goes through `pit_research_loader` (sandbox) or `qlib_windowed_features` (formal). Enforced by `lint_no_unsafe_pit_dates.py`."
- A new §7 research-integrity rule generalizing beyond dates: "Any result above a sanity threshold (e.g. OOS CAGR > 50% or Sharpe > 2) is **suspected leakage until reproduced on an independent PIT-correct engine** (EventDrivenBacktester or JoinQuant). Do not record extraordinary numbers as findings — and never as deployment candidates — before that cross-check." (This is the catch-all that would have flagged the 188% before promotion.)

---

## 7. Alternatives considered & rejected (please challenge these)

1. **Rule-only (just add CLAUDE.md text).** Rejected as primary: the agent already had the relevant rules and ignored them (§4). Kept as the soft layer F.
2. **Per-script assertion only (what was done in remediation).** Rejected as the durable answer: narrow (only the dashed regression), and only fires if the script runs. Kept as a cheap in-script tripwire.
3. **PreToolUse hook to veto the write.** Rejected: PreToolUse would have to parse intended file content (not reliably available pre-write for Edit), and we *want* the file written so the lint can scan it. PostToolUse + block-and-inject is the correct shape.
4. **Force ALL research through the existing `qlib_windowed_features` provider path (no separate sandbox loader).** This is the strongest alternative and I want the reviewer's opinion. Pro: single source of truth, no duplicated alignment logic, inherits the full PR1–9c perimeter. Con: heavyweight — requires a built Qlib provider, `qlib.init`, and is far slower for quick basket exploration, which is precisely why the bypass exists. The plan instead provides a lightweight-but-correct loader (Component A). **Is the lightweight loader a pragmatic necessity, or a second alignment implementation that will inevitably drift from the backend and become the next bug?**
5. **Type-level prevention (forbid string dates entirely; wrap dates in a `TradingDate` type).** Rejected as too invasive for a research codebase that leans on raw pandas.

---

## 8. Risks, limitations, known coverage gaps (honest)

- **Lint coverage is pattern-bound, not semantic.** Component B catches the *known* footguns (date `.astype(str)`, raw-ledger reads). It does NOT catch: merging on mixed-format keys with no `astype` (e.g. a future ledger that stores `effective_date` as a compact string while another column is dashed), same-day signal use, or other leakage forms. It narrows the class, it does not close all leakage.
- **`# noqa` abuse.** An agent under pressure could append the noqa marker to silence the lint and reintroduce the bug. Mitigation options to discuss: require a reason string after the marker; have the QA/commit gate separately report any *new* noqa additions for human review.
- **Hook fires post-write.** The bad code touches disk momentarily before the block/feedback. Acceptable (the QA + commit gates are the durable nets), but worth noting it is not a hard pre-veto.
- **Hook is local to this environment.** `settings.json` hooks do not travel with a fresh clone. "Prevent Claude Code globally" is not achievable; the achievable goal is "this repo's PIT path is un-bypassable through automated gates at author/QA/commit time." The pre-commit hook (Component D) is the most portable piece.
- **Loader duplication risk** (the §7.4 question): a second alignment implementation can drift. Mitigated by reusing `normalize_date_series` and the canary test, but not eliminated.
- **Hook latency.** A venv Python startup + AST parse on every `Edit`/`Write` adds ~200–500ms/edit. Narrowing with `if: Edit(*.py)` and a tight timeout keeps it acceptable; quantify before committing.
- **Cross-check rule threshold is arbitrary** and unenforced by machinery (it is a soft rule). 50% CAGR / Sharpe 2 are placeholders.

---

## 9. Open questions for the reviewer (where your input matters most)

1. **Architecture:** §7.4 — lightweight blessed loader vs. forcing everything through the provider. Which is the right long-term call for an agent-operated research system?
2. **Lint scope:** should rule #2 (ban raw `pit_ledger` reads) apply to `workspace/research/` notebooks too, or only `workspace/scripts/`? How many legitimate exploratory reads will it break, and is `--allow`/noqa friction acceptable?
3. **noqa governance:** what is the minimal mechanism to prevent the escape hatch from becoming the new default? (reason-required? QA reports new noqas? no noqa at all and rely on `--allow` files?)
4. **Generalization:** is it worth investing now in a broader "leakage lint" (same-day `$field` use without `Ref`, random-split detection, etc.), or is the date-specific lint the right scope and the rest handled by the existing factor-library PIT tests?
5. **Cross-check rule:** is a soft §7 rule enough, or should "extraordinary result → mandatory independent reproduction" be encoded as an orchestrator/release-gate check with a concrete threshold?
6. **Hook vs. pre-commit emphasis:** given the hook is local and post-write, should the pre-commit gate be the primary enforcement and the hook a convenience, or vice-versa?

---

## 10. Implementation sequencing & acceptance criteria

Proposed order (each independently shippable):

1. **Component A** (loader) + **Component E** (canary) — establishes the correct path and its test.
2. **Component B** (lint) with `--allow` for the (now-fixed) legacy `sandbox_v*` files initially, tightening over time.
3. **Component D** (QA block + pre-commit) — wire the lint into the existing gates.
4. **Component C** (PostToolUse hook) — author-time enforcement (touches `settings.json`; do via the sanctioned config path).
5. **Component F** (CLAUDE.md/AGENTS.md invariants + cross-check rule) — same edit pass, per the repo's "update both contracts together" rule.

Acceptance criteria:

- The lint flags the original buggy line and the raw-ledger read, and passes on the fixed scripts and on `load_pit_factor_panel`.
- The canary test fails on a reintroduced dashed-string regression and passes on the loader.
- `run_daily_qa.py` exits non-zero if any unsafe pattern exists in `workspace/` or `src/`.
- A deliberately-written `df["effective_date"].astype(str)` in a new file triggers the PostToolUse block with actionable `additionalContext` within the hook timeout.
- Re-running the full existing test suite (`tests/...`) stays green; `lint_no_bare_qlib_features.py src/` stays clean.

---

*End of plan. Evidence artifacts: `workspace/research/jq_deployment/v33_PIT_lookahead_bug_report.md` §9; re-measurement logs `workspace/outputs/v32_rerun_fixed.log`, `workspace/outputs/v15o_rerun_fixed.log`; `project_state.md` top note (2026-05-29).*
