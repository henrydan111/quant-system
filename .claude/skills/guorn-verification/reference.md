# 果仁 Verification — reference (the consolidated map / 收口)

Detail for the lean [SKILL.md](SKILL.md). 果仁 = trusted benchmark; local = under test. All NON-FORMAL.

## Doc & tool index — go here first

| For… | Use |
|---|---|
| **web factor-verification flow** (export 果仁's EXACT per-stock values, any factor/date) | [GUORN_WEB_FACTOR_VERIFICATION_GUIDE.md](workspace/research/idea_sourcing/guorn/GUORN_WEB_FACTOR_VERIFICATION_GUIDE.md) |
| **the per-stock comparator** (字段级 fidelity check) | [guorn_factor_parity.py](workspace/scripts/guorn_factor_parity.py) |
| **which local field/expr reproduces a 果仁 indicator** (parity status + conventions) | [guorn_local_field_mapping.md](workspace/research/idea_sourcing/guorn/guorn_local_field_mapping.md) — CANONICAL for **penny/structure-exact** mappings; vendor-approximate ones (e.g. 评级机构数) are flagged **rank-faithful / ranking-use-only** in their own row, not penny-exact |
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

It joins 果仁's export to a **POINTWISE** local qlib expression (raw fields / arithmetic / time-series ops only — qlib expressions are per-instrument, so the export-codes-only fetch is exact; it REFUSES cross-sectional / group / neutralized / composite tokens, which belong to the 综合级 harness), maps 6-digit→Qlib via the provider instrument list (codes zero-padded), validates `--date` is a trading day ≤ the provider calendar max (read at runtime, printed), reads at the signal-date lag, and prints coverage / median rel-err / within-0.1·1·5% / sign / Spearman·Pearson / (counts) exact-match + corr-on-non-zero + frac>0.
**Coverage gate (`--min-coverage`, default 0.98): below it the verdict is forced to `✗ coverage gap`** — a high score on a partial matched panel can be survivorship- or join-broken, so prove the candidate set is intact first; lower the floor ONLY with a documented reason in the command. Verdict tiers — value: `✅ penny/display-exact` · `◑ structure-exact` · `✗ divergence`; count: `✅ same-vendor count-exact` (exact≥95% + matching >0 breadth) · `◑ vendor-approx rank-faithful` (tracks at corr≥0.95 — **ranking/composite use ONLY, NOT a threshold filter or exact audit**) · `✗`.
Validated worked cases: 总市值(亿) vs `$total_mv/1e4` → 100% cov, Spearman 0.999 / Pearson 1.000 → ◑ structure-exact (2-dec 亿 display-round on tiny caps); 评级机构数 vs `$report_rc__n_active_orgs` → **92% cov (355 果仁 names absent from the frozen provider — likely recent listings; rerun with `--min-coverage 0.90` + that documented reason), exact 70.8% / corr-nonzero 0.990 / Spearman 0.982 → `◑ vendor-approx rank-faithful`** (usable as a ranking factor, NOT a threshold/audit value). Conventions (mapping doc §0): lag **T−1** displayed / **lag-0** PIT-gated; units (总市值万元→亿 `/1e4`; 成交额千元→亿 `/1e5`; BP `×1e4`); 后复权 `$close×$adj_factor` (price RATIOs 复权-invariant).

## 综合级 — 总排名分

果仁's 综合排名分 = Σ(per-factor 排名分 × 权重); 排名分 = (N−rank+1)/N×100, NaN→bottom. **The 字段级 comparator does NOT apply here** — a rank/composite changes with the instrument set, so compute it on the FULL intended candidate universe with the harness `_composite_row` pattern, then join to the export. **范围 is value-invariant**: the exported indicator column is the RAW value even at 范围=一级行业内; 范围 changes only 总排名分 → compare factor VALUES directly; reproduce within-industry grouping (`cs_mean($f grouped by $sw2021_l1)`) only for the composite.

## 策略级 — reproduce a deployed book (the path to ~果仁 returns)

1. **Recipe** — read the book's row in `deployed_20_recipes.md` (universe dict + 筛选 + 排名 + weights) and its trade model in `deployed_20_trade_models.md`.
2. **Universe (一个不漏, see below)** — build the candidate set, then mask (never row-drop before ranking, §8.1). **Classify boards with the shared `board_of()` (`workspace/research/jq_replication/jq_rep_utils.py`) — the future-proof classifier (handles ChiNext `30xxxx`, BSE via `.BJ`/`920`/`4x`/`8x`).** The validated 果仁-book snapshot: main+中小板+创业板 EXCLUDES 688/689 (STAR) and BSE; 包含科创板 adds `688 689`; 双创 = 创业板+科创板. The harness `MAIN_PREFIXES` tuples (`600 601 603 605 000 001 002 003 300 301`, …) are a convenience snapshot — **assert they equal `board_of()` on the frozen provider before relying on them** (a bare prefix list silently drifts as new prefixes appear).
3. **Factors** — map each ranking/filter indicator to its local expr via `guorn_local_field_mapping.md` (use the validated row; if missing, validate it 字段级 FIRST). Single-quarter = `$<f>_sq_q0`; TTM = Σ`_sq_q0..q3`.
4. **Trade model** — model-II band (个股仓位 → ~target_n holds), 备选, sell-rank, rebuy cooldown, 涨停不卖 (`hold_on_limit_up`); event-driven **total return**. **Read the book's cost from `deployed_20_trade_models.md` — do NOT hard-code it.** The recipes record `平台默认成本(单边千分之二或千分之五)` = 0.2% OR 0.5%/side (not one value) → run BOTH as a sensitivity and label the chosen cost in the output (a wrong cost can flip a replay gap between selection and execution). Mirror an existing `ModelII*Strategy`.
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

- **A return/overlap gap** → run the **replay decomposition** (`_verify*_replay.py` pattern): feed 果仁's exact held names AND the closest reproducible weights / rebalance / fill / cost through the engine (if weights are unavailable, label it **names-only replay**). replay ≈ 果仁 ⇒ local **selection is the DOMINANT residual**; replay gap ⇒ the execution / weights / cost / fill / corporate-action path is unlocalized. Names alone do NOT isolate selection — never claim "the gap IS selection" from a names-only replay; say "selection is dominant" and flag what stays unverified.
- **A per-stock value gap** → rule out **lag → unit → 复权 → calendar/suspension/window-membership → vendor → bug, in order**. (Window-membership / suspension-calendar convention causes proven residuals on long-window factors — e.g. 250日涨幅, 乖离率 — that are NOT vendor or data errors; check it before blaming the vendor.) 果仁 朝阳永续 / 复权 / calendar legitimately differ; 中性化 / 壳价值 / 退市风险 screens are irreducible (can't penny-match).

## Hard constraints

- **NON-FORMAL** — a fidelity diagnostic, not a formal gate. It reads the published PROVIDER (`D.features`, already PIT-aligned at build time, like the harnesses), which is fine for parity; the §3 guards still bind — never read `data/pit_ledger/*` raw, never hand-roll PIT alignment or string-compare dates. Any FORMAL factor work routes through `pit_research_loader` / `qlib_windowed_features` + `get_factor_catalog()` (the sanctioned doors).
- 选股日期 / compare window ≤ the frozen-calendar max (confirm via `project_state.md` / `data/reference/trade_cal.parquet`).
- Don't hard-code volatile facts (approved-field list, registry counts) — cite `config/field_registry/field_status.yaml` / `project_state.md` and read them.
- Run backends with `venv/Scripts/python.exe`.
