# GPT cross-review packet — `guorn-verification` skill + `guorn_factor_parity.py` comparator

> §10 gate. Pushed branch: **`report-rc-registration`** (HEAD `4430deb`). Copy the block below to GPT-5.5 Pro.
> Apply findings → re-review until no Blocker → record verdict in project_state.md.

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. You are reviewing a new repo SKILL (a process/discipline + routing document) plus the one new tool it makes canonical. A skill that reads well but instructs an agent toward a lookahead, a §3 bypass, or a subtly-wrong method is invalid, not "mostly fine." Judge it on BOTH (a) the quantitative-research principles it instructs, and (b) skill-craft per the repo's own writing-skills meta-skill. Be skeptical; surface blockers; do not rubber-stamp.

REPO (public — fetch any file to verify against live code)
https://github.com/henrydan111/quant-system   (branch: report-rc-registration)
Raw file form: https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/<path>

CONTEXT — read these to judge the change against the contract:
- CLAUDE.md (hard invariants §3, PIT §3.2, sealed-OOS §3.4, research integrity §7, no-hedge §7.10)
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/CLAUDE.md
- writing-skills meta-skill (the skill-craft contract the new skill must conform to) — SKILL + reference
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/.claude/skills/writing-skills/SKILL.md
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/.claude/skills/writing-skills/reference.md
- THE ARTIFACT under review — guorn-verification SKILL + reference
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/.claude/skills/guorn-verification/SKILL.md
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/.claude/skills/guorn-verification/reference.md
- THE TOOL it makes canonical — the per-stock comparator
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/workspace/scripts/guorn_factor_parity.py
- Consolidated docs the skill routes to (referenced; fetch if needed)
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/workspace/research/idea_sourcing/guorn/GUORN_WEB_FACTOR_VERIFICATION_GUIDE.md
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/workspace/research/idea_sourcing/guorn/guorn_local_field_mapping.md

SELF-REVIEW PREFLIGHT — completed before this request: VERDICT = clean for GPT.
Checked: §3 (PIT §3.2 — the skill reads the already-PIT-aligned PROVIDER via D.features and forbids raw data/pit_ledger reads + hand-rolled alignment; formats §3.1 — 6-digit→Qlib join, code zero-pad, st_stocks.txt authoritative ST; get_factor_catalog door); §7 (no-lookahead — lag T−1 display / lag-0 PIT-gated, fidelity-before-alpha; no-hedge §7.10 — replay decomposition REQUIRED before attributing a gap; survivorship — "candidate set then mask"); writing-skills (description=trigger; SKILL.md 484 words <500; failure-matched rationalization table; volatile facts cited to source not hard-coded); §10 (this review).
Fixes made during build/self-review: (1) comparator verdict rubric — added a "reproduces (vendor-approximate)" tier so a count tracking at corr≥0.95 isn't mislabeled ✗ by off-by-one exact-match; (2) code zero-pad — 果仁 exports codes as integers, dropping SZ/BSE leading zeros (001270→1270); a naive (\d{6}) regex silently dropped 96/170 rows before the fix (`_code6`); (3) clarified the NON-FORMAL provider-read vs §3 wording.
Residual concerns for reviewer:
(a) Empirically (2 fresh-agent RED tests) the baseline agents SUCCEED on the disciplines — the repo's artifacts already encode them; the skill's measured value is CONSOLIDATION/discoverability (108k→68k tokens, and it surfaced the comparator the baseline MISSED), not preventing total failure. Is the discipline rationalization table right-sized, or over-built?
(b) The skill makes the harness PREFIXES (MAIN_PREFIXES = main+中小板+创业板; +688/689 for 科创板) canonical for 果仁 books over the existing board_of() classifier in workspace/research/jq_replication/jq_rep_utils.py. Right call, or should the two be unified (scope creep)?
(c) The comparator reads via bare D.features (the provider), like every guorn_verify_* harness. Acceptable for a NON-FORMAL diagnostic, or should even diagnostics route through qlib_windowed_features?
(d) The 过滤停牌 proxy = close.loc[pday].notna() on the T−1 signal day, approximating 果仁's trade-day-d suspension filter; the engine can_buy gate backstops it (flagged bounded/second-order). Acceptable?

WHAT CHANGED (authoritative — embedded text is the source of truth; the links cross-check)

=== FILE 1: .claude/skills/guorn-verification/SKILL.md ===
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
| "The book runs and the return is close, so the field is right." | Prove a FIELD by per-stock value comparison (the comparator), never by a book's return — a field can be degenerate on that book's universe (#18 评级机构数 on ST). |
| "板块=全部, so the universe is all stocks incl 科创板." | Replicate the 投资域 一个不漏. 科创板 is a SEPARATE knob from 板块 — 板块=全部 does NOT include 688/689; the 科创板 dropdown removes them. 果仁 全部股票 also excludes 北证/BSE. |
| "The gap is execution / costs / limit-ups." (stated without testing) | Decompose by REPLAY first: feed 果仁's exact held names through the engine. replay ≈ 果仁 ⇒ the gap is SELECTION, not execution. Never attribute a gap without the decomposition. |
| "Local ≠ 果仁, so our data is wrong." | Read the residual lag → unit → 复权 → vendor → bug, in that order. 果仁's vendor (朝阳永续) / 复权 / calendar legitimately differ; localize before claiming a bug. |

Signal lag = T−1 (display) unless a value is PIT-gated (lag-0). Zero-pad 果仁 codes to 6 digits. 选股日期 ≤ frozen-calendar max (confirm via project_state.md). Don't hard-code volatile facts (registry/field counts) — cite the source of truth and read it.

## Start here
Read reference.md for the consolidated doc/tool index (收口), the comparator CLI + worked examples, the 投资域 checklist, the book-reproduction recipe, and the residual/gap discipline.

=== FILE 2: .claude/skills/guorn-verification/reference.md ===
[Full text at the raw link above. Sections: Doc & tool index (收口 — maps each task to its doc/tool); 字段级 comparator (CLI + worked cases 总市值 Spearman 0.999 / 评级机构数 vendor-approximate corr 0.990 + verdict tiers + lag/unit/复权 conventions); 综合级 总排名分 (formula + the proven 范围-value-invariance); 策略级 6-step book-reproduction recipe (recipe→universe PREFIXES→factors via mapping ledger→model-II+cost→EventDrivenBacktester fill mode→compare to xlsx, ~10% normal-regime residual expected); 投资域 一个不漏 (the 3 load-bearing filters + the 科创板≠板块 trap + 北证/BSE exclusion); gap/residual discipline (replay decomposition; lag→unit→复权→vendor→bug); hard constraints (NON-FORMAL provider-read, frozen calendar, no volatile facts, venv).]

=== FILE 3: workspace/scripts/guorn_factor_parity.py (the canonical tool; full text at the raw link) ===
Reusable comparator: loads a 果仁 每日选股 export xlsx (GBK-garble-safe → columns by position; `_code6` zero-pads integer-truncated codes), joins to a local qlib expression read via D.features at the (lag)-th trading day on/before --date (6-digit→Qlib via the provider instrument list {c.split('_')[0]: c}), and prints coverage / median rel-err / within-0.1·1·5% / sign / Spearman·Pearson; for --kind count: exact-match + corr-on-non-zero + frac>0; then a verdict (✅ display-exact · ✅ reproduces vendor-approximate [count tracks at corr≥0.95] · ◑ structure-exact · ✗ divergence). --lag default 1 (T−1 display); --lag 0 for PIT-gated. --guorn-scale lifts 果仁 onto the local unit. Validated: 总市值/1e4 → 100% cov / Spearman 0.999; $report_rc__n_active_orgs → 70.8% exact / corr-nonzero 0.990 → ✅ vendor-approximate.

QUANTITATIVE-RESEARCH PRINCIPLES — check the skill's instructions against EACH; a violation is a Blocker
1. PIT / NO-LOOKAHEAD. Does any instructed step let a value at t use info not knowable at t? Is the lag rule (T−1 display vs lag-0 PIT-gated) correct? Does reading the provider via D.features (vs the wrappers) risk anything for a NON-FORMAL diagnostic?
2. OUT-OF-SAMPLE / SEALED. (Skill is fidelity, not OOS — but does anything it says undercut the separate sealed-OOS gate, or blur "fidelity-validated" into "alpha-validated"?)
3. SURVIVORSHIP. The universe recipe is "candidate set then boolean mask" — does it preserve delisted/suspended names for ranking context (§8.1), or risk pre-filtering?
4. FACTOR-EVAL STANDARD. (Out of scope — fidelity precedes alpha here.)
5. EXECUTION & COST REALISM. Is the 策略级 recipe (model-II band, 0.2%/side, total return, fill mode, 涨停不卖) sound? Is the "compare vectorized-price vs event-driven-total" trap avoided?
6. NO LEVERAGE. (n/a — flag if any instruction implies it.)
7. NO HEDGE WORDS. The replay-decomposition-before-attributing rule operationalizes §7.10 — is it correctly framed (does replay truly separate selection from execution)?
8. FOUR-LAYER PIPELINE. factor → universe(mask) → signal(rank in sub-universe) → execution(tradability only). Does the skill keep these separated?
9. MULTIPLE TESTING. (n/a for a fidelity check.)

REVIEW QUESTIONS
1. Correctness/accuracy — does the skill DESCRIBE its tools correctly? In particular: the lag T−1/lag-0 split, the 科创板≠板块 rule, the MAIN_PREFIXES set (does it correctly exclude 688/689 AND 北证/BSE 8xx/920/.BJ?), the 总排名分 formula, the residual order, and the comparator's join/verdict logic (fetch guorn_factor_parity.py). Any subtly-wrong instruction an agent would follow into an error?
2. Governance / §3 — does any instruction lead an agent to bypass §3 (raw-ledger read, hand-rolled PIT alignment, bare D.features in FORMAL code, editing registries outside the publish path)? Is the NON-FORMAL boundary drawn correctly, and does the comparator honor it?
3. Skill-craft (per writing-skills) — is the description a precise TRIGGER (fires on the right tasks; over/under-trigger risk)? Is the rationalization table matched to real failures and not soft "consider…"? Anything VOLATILE hard-coded that should cite a source (the PREFIXES, the frozen-date, the parity numbers)? Within the <500-word budget appropriately, or is content that belongs in reference.md/src in SKILL.md (or vice-versa)?
4. Design / consolidation — does it route each task to the RIGHT canonical doc/tool? Is making the harness PREFIXES canonical over board_of() correct, or should they be unified? Hidden coupling, drift from conventions, or reinventing something already in the repo?
5. Evidence — what proof is missing, and the exact test/command you'd run to confirm the skill changes agent behavior correctly (beyond the 1 GREEN rep already run).

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending line quoted and an exact suggested replacement. Map every Blocker to the principle or invariant it violates.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.
```
