---
name: guorn-verification
description: Use when reproducing a 果仁 (guorn.com) strategy/book locally, verifying a local A-share factor or dataset against 果仁, diagnosing a local-vs-果仁 return or selection-overlap gap, or judging whether local data/engine is accurate against the 果仁 benchmark.
---

# 果仁 Verification (guorn parity)

果仁 = the trusted external benchmark; the local system is **under test**. Goal: reproduce 果仁 books, verify local factors/data, and land returns approximating 果仁's official backtest. This is **NON-FORMAL** diagnostic work: it reads the published PROVIDER (`D.features`, already PIT-aligned at build time, like the `guorn_verify_*` harnesses), and still honors CLAUDE.md §3 — never read raw `data/pit_ledger/*`, never hand-roll PIT alignment or string-compare dates; any FORMAL factor work routes through the sanctioned wrappers + `get_factor_catalog()`.

## Core model: fidelity BEFORE alpha

Verification answers two orthogonal questions, **in order**: (1) **保真度** — is the value/selection COMPUTED correctly (vs 果仁, per-stock, PIT-safe)? then (2) **alpha** — does it predict (the separate formal lifecycle)? A high return/IC on a mis-computed factor is meaningless (the v31/v32 lookahead lesson). Never report alpha on an unverified computation.

## Three-level ladder (climb in order)

- **字段级** — one factor's per-stock value vs 果仁's export → `workspace/scripts/guorn_factor_parity.py`.
- **综合级** — 总排名分 (weighted rank) vs the local composite.
- **策略级** — a deployed book's selection + return vs 果仁's xlsx → the `guorn_verify_*` / `guorn_parity_rung*` harnesses.

## Required behavior — the four disciplines (each has burned us)

| Rationalization (do NOT) | Required instead |
|---|---|
| "The book runs and the return is close, so the field is right." | Prove a FIELD by **per-stock value comparison** (the comparator), never by a book's return — a field can be degenerate on that book's universe (#18 评级机构数 on ST). |
| "板块=全部, so the universe is all stocks incl 科创板." | Replicate the **投资域 一个不漏**. 科创板 is a SEPARATE knob from 板块 — `板块=全部` does NOT include 688/689; the 科创板 dropdown removes them. 果仁 全部股票 also excludes 北证/BSE. |
| "The gap is execution / costs / limit-ups." (stated without testing) | **Decompose by REPLAY first**: feed 果仁's exact held names through the engine. replay ≈ 果仁 ⇒ the gap is SELECTION, not execution. Never attribute a gap without the decomposition. |
| "Local ≠ 果仁, so our data is wrong." | Read the residual **lag → unit → 复权 → vendor → bug, in that order**. 果仁's vendor (朝阳永续) / 复权 / calendar legitimately differ; localize before claiming a bug. |

Signal lag = **T−1** (display) unless a value is PIT-gated (lag-0). Zero-pad 果仁 codes to 6 digits (integer export drops SZ/BSE leading zeros). 选股日期 must be ≤ the frozen-calendar max (confirm via `project_state.md`). Don't hard-code volatile facts (registry/field counts, approved-field list) — cite the source of truth and read it.

## Start here

**Read [reference.md](reference.md)** for the consolidated doc/tool index (收口), the comparator CLI + worked examples, the 投资域 checklist, the book-reproduction recipe, and the residual/gap discipline.
