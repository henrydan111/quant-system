---
name: writing-skills
description: Use when authoring or editing a repo skill, slash command, or reusable agent workflow; deciding skill vs CLAUDE/AGENTS rule vs src backend; or fixing a skill that fails to trigger, over-triggers, bloats context, or lets agents rationalize violations under pressure.
---

# Writing Skills (this repo)

## Overview

Writing a skill is **TDD applied to process documentation**: document a baseline failure first, write the minimal instruction that fixes it, then harden against rationalizations. A skill or edit without a fresh-agent RED test is not deployable — if you wrote the SKILL.md change before observing the baseline failure, revert it and start over. No exceptions.

Two parts: a thin `.claude/skills/<name>/SKILL.md` (frontmatter for discovery, body once selected) + an optional `src/` backend for computation — example `src/alpha_research/factor_eval_skill/`. Executable/computational logic lives in `src/`; SKILL.md holds triggers, required behavior, templates, and stop conditions.

## Decide the artifact first

- **Judgment/discipline agents skip under pressure** → skill.
- **Repeatable user-invoked operation** → slash command (logic in `src/` / `workspace/scripts/`).
- **Mechanically checkable rule** → lint/test/gate first; a skill may explain it but must not be the only enforcement.
- **Hard invariant** → CLAUDE.md §3 + AGENTS/.agents mirror + enforcing test + `project_state.md` note.
- **Reusable computation** → `src/` backend; a `src/system.md` §0 row only if a canonical entry point.
- **One-off / dated rationale** → `project_state.md`, not SKILL.md.

## The description is a trigger, not a summary

Description = **WHEN to use** (concrete symptoms), never what the skill does — it is the only thing that decides selection. Start with "Use when…", third person, no process steps.

## Test it (RED → GREEN → REFACTOR)

**RED:** fresh subagent with no new skill/edit applied — no skill for a new skill, the old skill for an edit — on a pressure scenario (e.g. "this factor's OOS Sharpe is 7, ship it"); record the wrong behavior + its rationalizations. **GREEN:** minimal counter; confirm the behavior changed. **REFACTOR:** a no-guidance control + 5+ fresh-context reps per wording variant, combined pressure (time + authority + sunk cost); read failures manually (template echoes don't count).

## Repo guard — never bypass §3

PIT reads go only through `src/data_infra/pit_research_loader.py` / `src/research_orchestrator/qlib_windowed_features.py`; never read `data/pit_ledger/*` raw or hand-roll alignment. Sealed-OOS verification must read existing artifacts / seal ledger / provenance, or use strict same-run resume (`run_dir` + `step_id` + matching `request_hash`/`plan_hash`). If resume refuses, stop — never work around the refusal and never instruct a fresh OOS rerun. Factor definitions come from `get_factor_catalog()` (ignores status); don't edit registry tables outside the publish path; don't hard-code volatile facts (counts/dates/lists).

Before drafting or editing any skill body, **read [reference.md](reference.md)** for match-failure-to-form, the minimal template, project rules, and budget; then edit only the sections required by the RED failure.
