# 果仁 Verification — reference (the consolidated map / 收口)

Detail for the lean [SKILL.md](SKILL.md). 果仁 = trusted benchmark; local = under test. All NON-FORMAL.

## Doc & tool index — go here first

| For… | Use |
|---|---|
| **web factor-verification flow** (export 果仁's EXACT per-stock values, any factor/date) | [GUORN_WEB_FACTOR_VERIFICATION_GUIDE.md](workspace/research/idea_sourcing/guorn/GUORN_WEB_FACTOR_VERIFICATION_GUIDE.md) |
| **the per-stock comparator** (字段级 fidelity check) | [guorn_factor_parity.py](workspace/scripts/guorn_factor_parity.py) |
| **which local field/expr reproduces a 果仁 indicator** (+ validated parity status, conventions) | [guorn_local_field_mapping.md](workspace/research/idea_sourcing/guorn/guorn_local_field_mapping.md) — CANONICAL (`.json` = derived) |
| **deployed-20 book recipes** (universe / factors / weights / trade model) | [deployed_20_recipes.md](workspace/research/idea_sourcing/guorn/deployed_20_recipes.md) + [deployed_20_trade_models.md](workspace/research/idea_sourcing/guorn/deployed_20_trade_models.md) |
| **book-reproduction harnesses** (worked 策略级 templates) | `workspace/scripts/guorn_verify_*.py`, `guorn_parity_rung*.py` |
| **果仁 xlsx ground-truth loader** (年度收益统计 / 各阶段持仓详单) | [guorn_xlsx_ground_truth.py](workspace/scripts/guorn_xlsx_ground_truth.py); xlsx in `Knowledge/果仁回测结果/` |
| **raw 果仁 indicator formulas** | `indicator_reference_auto.md`, `guorn_aichat_indicator_defs.md`, `内联公式85条拆解.md` (same dir) |
| **methodology + lessons + current state** | memory `project_guorn_parity` + `project_state.md` |

## 字段级 — the comparator (the default fidelity check)

```
venv/Scripts/python.exe workspace/scripts/guorn_factor_parity.py \
    --xlsx Knowledge/果仁验证因子/<export>.xlsx --date YYYY-MM-DD \
    --local-expr '<qlib expr in 果仁 display unit>' --guorn-col <name|idx> [--lag 1|0] [--kind value|count]
```

It joins 果仁's export to a local qlib expression (6-digit→Qlib via the provider instrument list; codes zero-padded), at the signal-date lag, and prints coverage / median rel-err / within-0.1·1·5% / sign / Spearman·Pearson / (counts) exact-match + corr-on-non-zero, with a verdict. Validated worked cases: 总市值(亿) vs `$total_mv/1e4` → Spearman 0.999; 评级机构数 vs `$report_rc__n_active_orgs` → ✅ vendor-approximate (corr-nonzero 0.990). Verdict tiers: ✅ display-exact · ✅ reproduces (vendor-approximate) · ◑ structure-exact · ✗ divergence. Conventions (from the mapping doc §0): lag **T−1** for displayed factors, **lag-0** for PIT-gated fundamentals; units (总市值万元→亿 `/1e4`; 成交额千元→亿 `/1e5`; BP `×1e4`); 后复权 `$close×$adj_factor` (price RATIOs are 复权-invariant).

## 综合级 — 总排名分

果仁's 综合排名分 = Σ(per-factor 排名分 × 权重); 排名分 = (N−rank+1)/N×100, NaN→bottom. Reproduce with the harness `_composite_row` pattern. **范围 is value-invariant**: the exported indicator column is the RAW value even at 范围=一级行业内; 范围 changes only 总排名分 → compare factor VALUES directly; reproduce within-industry grouping (`cs_mean($f grouped by $sw2021_l1)`) only for the composite.

## 策略级 — reproduce a deployed book (the path to ~果仁 returns)

1. **Recipe** — read the book's row in `deployed_20_recipes.md` (universe dict + 筛选 + 排名 + weights) and its trade model in `deployed_20_trade_models.md`.
2. **Universe (一个不漏, see below)** — build the candidate set, then mask. Validated 果仁-book prefixes (from the harnesses): `MAIN_PREFIXES = 600 601 603 605 000 001 002 003 300 301` (沪深 main+中小板+创业板, = 排除科创板 + 排除北证); add `688 689` for 包含科创板; `300 301 688 689` for 双创. (`board_of()` in `workspace/research/jq_replication/jq_rep_utils.py` is an equivalent classifier; for 果仁 books prefer the harness prefixes — that's the validated path.)
3. **Factors** — map each ranking/filter indicator to its local expr via `guorn_local_field_mapping.md` (use the validated row; if missing, validate it 字段级 FIRST). Single-quarter = `$<f>_sq_q0`; TTM = Σ`_sq_q0..q3`.
4. **Trade model** — model-II band (个股仓位 → ~target_n holds), 备选, sell-rank, rebuy cooldown, 涨停不卖 (`hold_on_limit_up`); cost = 0.2%/side + total return. Mirror an existing `ModelII*Strategy`.
5. **Engine** — `EventDrivenBacktester` with `preload_features`; choose the fill mode the book trades at (09:35 open fill vs `jq_daily_avg` daily-average). Use `FixedSlippage(0.0)` for parity, realistic for deployment.
6. **Compare to 果仁** — yearly returns + selection overlap (top-N codes) vs the xlsx (`guorn_xlsx_ground_truth.py`). A normal-regime residual ~10% is expected (weekly-vs-daily cadence + omitted-recipe-weight + 果仁 bull-year limit-up fill optimism). Use `guorn_verify_18_stbigcap.py` or `guorn_parity_rung6_quality59.py` as the template.

## 投资域 — replicate every field (一个不漏)

12 universe-dict fields; one wrong knob silently changes the candidate set. The 3 load-bearing filters + local mapping:

| 果仁 dropdown | semantics | local |
|---|---|---|
| **ST股票** 包含/排除/仅有 | both / drop ST·*ST / only ST·*ST | `ru.st_codes_on(d)` from range-form `data/qlib_data/instruments/st_stocks.txt` (§3.1) |
| **科创板** 排除/包含/仅有 | drop / keep / only 688·689 | prefix gate (see step 2) |
| **过滤停牌** 是/否 | drop suspended on the date | `close.loc[pday].notna()` proxy + engine `can_buy` gate |

**★ 科创板 ≠ 板块.** `板块=全部` does NOT include STAR; the 科创板 field independently removes 688/689. Most deployed books are `板块:全部 + 科创板:排除` ⇒ STAR EXCLUDED. 果仁 `全部股票` also excludes 北证/BSE (8xx/920/.BJ). Cross-check the result count against the book's universe before trusting it.

## Gap / residual discipline

- **A return/overlap gap** → run the **replay decomposition** (`_verify*_replay.py` pattern): feed 果仁's exact names through the engine equal-weight. replay ≈ 果仁 ⇒ SELECTION gap (your factor stack picks different names); replay ≪ 果仁 ⇒ execution/engine. Never attribute a gap without this.
- **A per-stock value gap** → rule out **lag → unit → 复权 → vendor → bug, in order**. 果仁 朝阳永续 / 复权 / calendar legitimately differ (report_rc is vendor-approximate; 中性化 / 壳价值 / 退市风险 screens are irreducible — can't penny-match).

## Hard constraints

- **NON-FORMAL** — a fidelity diagnostic, not a formal gate. It reads the published PROVIDER (`D.features`, already PIT-aligned at build time, like the harnesses), which is fine for parity; the §3 guards still bind — never read `data/pit_ledger/*` raw, never hand-roll PIT alignment or string-compare dates. Any FORMAL factor work routes through `pit_research_loader` / `qlib_windowed_features` + `get_factor_catalog()` (the sanctioned doors).
- 选股日期 / compare window ≤ the frozen-calendar max (confirm via `project_state.md` / `data/reference/trade_cal.parquet`).
- Don't hard-code volatile facts (approved-field list, registry counts) — cite `config/field_registry/field_status.yaml` / `project_state.md` and read them.
- Run backends with `venv/Scripts/python.exe`.
