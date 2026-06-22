# Writing Skills — reference

Detail for the lean [SKILL.md](SKILL.md).

## Match the failure type to the form

| The agent… | Right form | Wrong form |
|---|---|---|
| Skips a rule under pressure | Prohibition + rationalization table + red flags | Soft "consider…" guidance |
| Produces the wrong shape | Positive recipe / template contract | A list of don'ts |
| Omits a required element | A literal template slot | A prose reminder |
| Should branch on a condition | Observable predicate ("if X, do Y") | Unconditional rule + exceptions |

## Minimal SKILL.md shape

```markdown
---
name: skill-name-with-hyphens
description: Use when [observable trigger, not workflow summary]   # frontmatter ≤1024 chars total; description <500 if possible; third person
---

# Skill Name

## Core rule
One or two sentences.

## Required behavior
Use the form that matches the baseline failure: prohibition table, positive template, required slots, or observable conditional.

## Stop conditions / common rationalizations
Only for discipline failures; use rationalizations observed in RED tests.
```

Add a quick-reference table only if it removes more text than it adds. Put heavy examples, APIs, and computation in supporting files or `src/`.

## Project-specific rules (non-negotiable)

- **Never instruct a path that bypasses CLAUDE.md §3 invariants.** PIT reads go through `src/data_infra/pit_research_loader.py` / `src/research_orchestrator/qlib_windowed_features.py`; never hand-roll alignment or read `data/pit_ledger/*` raw. Sealed-OOS / spend-limited evidence is never re-run to verify; read existing artifacts / seal ledger / provenance or use strict same-run resume (`run_dir` + `step_id` + matching `request_hash`/`plan_hash`), and never work around resume refusal. Factor definitions come from `get_factor_catalog()` (authoritative for all discovery/sandbox, ignores status); formal validation resolves registry status through orchestrator gates. Don't inline factor formulas or edit registry tables outside the publish path.
- **Don't hard-code volatile repo facts.** Restate invariant rules only. For counts, field lists, calendar bounds, registry state, backend ids, and canonical entry points, cite the source of truth (`project_state.md`, `config/field_registry/field_status.yaml`, `config.yaml`, `src/system.md` §0) and tell the agent to read it.
- **Keep contracts in sync (§11.2):** a workflow change updates CLAUDE.md + AGENTS.md + `project_state.md` in the same pass.
- **Run backends with `venv/Scripts/python.exe`.**

## Token budget

Getting-started skills <150 words; frequently-loaded <200; normal <500. If `wc -w .claude/skills/<name>/SKILL.md` exceeds 500, delete examples/tables first, then move computation or references to `src/` or supporting files. (reference.md and other supporting files load on demand and don't count against the SKILL.md budget.)
