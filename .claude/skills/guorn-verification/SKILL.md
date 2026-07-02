---
name: guorn-verification
description: Use when reproducing a 果仁 (guorn.com) strategy/book locally, verifying a local A-share factor or dataset against 果仁, diagnosing a local-vs-果仁 return or selection-overlap gap, or judging whether local data/engine is accurate against the 果仁 benchmark.
---

# 果仁 Verification (guorn parity)

果仁 = the trusted benchmark; the local system is **under test**. Goal: reproduce 果仁 books, verify local factors/data, approximate 果仁's returns. **NON-FORMAL** — reads the published `D.features` provider (PIT-aligned at build, like the harnesses); honor CLAUDE.md §3: never read raw `data/pit_ledger/*` or hand-roll PIT; FORMAL work routes through `get_factor_catalog()` + the sanctioned wrappers.

## Core model: fidelity BEFORE alpha

Two questions, **in order**: (1) **保真度** — is the value/selection COMPUTED correctly (vs 果仁, per-stock + top-K, PIT-safe)? (2) **alpha** — does it predict (separate formal lifecycle)? A high IC on a mis-computed factor is meaningless (v31/v32 lookahead); never report alpha on an unverified computation.

## Three-level ladder (climb in order)

- **字段级** — one factor's per-stock value vs 果仁's export → `guorn_factor_parity.py`; **complete only with a passing top-5/10/20 overlap** (see disciplines below).
- **综合级** — 总排名分 (weighted rank) vs the local composite.
- **策略级** — a deployed book's selection + return vs 果仁's xlsx → the `guorn_verify_*` / `guorn_parity_rung*` harnesses.

## Required behavior — the four disciplines (each has burned us)

| Rationalization (do NOT) | Required instead |
|---|---|
| "The book runs and the return is close, so the field is right." | Prove a FIELD by **per-stock value comparison** (the comparator), never by a book's return — a field can be degenerate on that book's universe (#18 评级机构数 on ST). |
| "Value parity is high (Spearman 0.99 / penny median), so the field is verified." | **字段级 COMPLETES only with a reported top-5/10/20 overlap that clears the bar** — value parity is necessary, NOT sufficient (净资产收益率: Spearman 0.991 / 0.22pp yet **top-5 = 0%**). Top-K IS the verdict: high value + weak top-K = *selection-DIVERGED* (not verified); **no top-K number = INCOMPLETE → re-run.** |
| "板块=全部, so the universe is all stocks incl 科创板." | Replicate the **投资域 一个不漏**. 科创板 is a SEPARATE knob from 板块 — `板块=全部` does NOT include 688/689; the 科创板 dropdown removes them. 果仁 全部股票 also excludes 北证/BSE. |
| "The gap is execution / costs / limit-ups." (untested) | **REPLAY first** (reference.md): run 果仁's exact held names through the engine — replay ≈ 果仁 ⇒ selection dominates; gap ⇒ execution. Never attribute without it. |
| "Local ≠ 果仁, so our data is wrong." | Localize in order **lag → unit → 复权 → calendar/window → vendor → bug** (reference.md); 果仁's vendor (朝阳永续)/复权/calendar legitimately differ — localize before blaming data. |

Quick rules (detail in reference.md): signal lag **T−1** display / lag-0 PIT-gated; zero-pad 果仁 codes to 6 digits; 选股日期 ≤ frozen-calendar max; don't hard-code volatile facts (counts / field-lists) — read the source.

## Start here

**Read [reference.md](reference.md)** — doc/tool index (收口), comparator CLI + examples, 投资域 checklist, book-reproduction recipe, residual/gap discipline.

**果仁's OFFICIAL platform help docs — [Knowledge/果仁帮助文档/](Knowledge/果仁帮助文档/) — are a REQUIRED reference when replicating a 果仁 自定义指标** (custom-composed indicator). They are 果仁's own ground truth for operator semantics (`Ref`/`BarRef`/`RefQ`/`TTM`/`MA`/`EMA`/`Level`/`KLast`/`hSum`/`dayslast`…) and financial-ratio definitions (市盈率 / 净资产收益率 / RefQ-growth …). Resolve every operator + ratio from 果仁's own definition BEFORE writing the local qlib expr — do NOT guess 果仁's function behavior (its gotchas bite: `Ref` counts 停牌 days but `BarRef` skips them; `RefQ(x,4)` = same quarter a year ago; TTM ratios divide by `AvgQ(…,4,1)`). Key files + the full list are in reference.md.
