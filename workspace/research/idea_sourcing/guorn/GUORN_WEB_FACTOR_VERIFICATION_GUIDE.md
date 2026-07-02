# 果仁网 web platform — direct factor / selection VERIFICATION guide

> **Validated end-to-end 2026-06-27** (Claude drove the live UI: navigate → add ranking → 每日选股 → 导出 →
> rename → confirm 4597-row xlsx; then re-validated the two load-bearing knobs — **ST股票=仅有ST** collapsed
> 4597 → **170 ST names**, and **选股日期=2025/12/31** (a locally-covered date) ran + exported cleanly). This
> is the most powerful parity tool we have: it returns 果仁's EXACT stock list + **总排名分 (composite rank
> score)** for ANY 筛选/排名 condition on ANY date — directly comparable to a local factor/composite
> reproduction. Use it to settle "does my factor reproduce 果仁?" at the stock level (the #18 lesson: prove a
> field by direct comparison, not by a book's return). **The LOCAL half (compute → join → compare → verdict) is
> closed by [`guorn_factor_parity.py`](../../../scripts/guorn_factor_parity.py) + the "Closing the loop" section
> below — together they make this an END-TO-END consistency check, not just a capture.**
>
> **Two settings silently break parity if left at default — always set them first:**
> 1. **Universe dropdowns** (esp. **ST股票=仅有ST** for an ST book) — default 全部 returns the whole ~4600 market.
> 2. **选股日期** — default is *today* (outside our frozen local calendar); pick a trading day **≤ the local
>    provider calendar max** — read it from `data/reference/trade_cal.parquet` or let `guorn_factor_parity.py`
>    print it at runtime (don't rely on a date shown in a historical example).

## What it can verify (3 modes)
1. **筛选条件 only** — the full set of stocks passing a filter (e.g. `ILLIQ(5) rank 0–65%`). Validates a
   FILTER's membership + direction.
2. **排名条件 only** — all stocks ranked by an indicator (or a weighted multi-indicator composite), with the
   per-stock **总排名分**. Validates a RANKING factor + its 综合排名分 against the local composite.
3. **筛选 + 排名 stacked** — the ranking WITHIN the filtered universe (the real strategy form).

## Prerequisites
- Logged into **guorn.com** in the user's Chrome (the account "leodan" — has the deployed strategies + saved
  pools). The Claude-in-Chrome extension must be connected (`list_connected_browsers`).
- Export download location is preset to **`E:\量化系统\Knowledge\果仁验证因子`** (Chrome auto-downloads there,
  no Save-As dialog). The downloaded filename is a GARBLED HASH — rename it immediately (step 6).

## The workflow (step by step — validated)
1. **Navigate:** `https://guorn.com/stock?category=stock` → the 股票策略 builder (择股设置 tab).
2. **Universe** (top dropdowns — set to match the book): 我的股票池 / 系统股票池, 指数成份, 上市板块,
   行业标准 (申万 2014 / 2021), 一级/二级行业, 企业性质, 融资融券, **ST股票** (包含ST / 排除ST / **仅有ST**),
   **科创板** (排除 / 包含 / 仅有科创板), 过滤停牌股票 (checkbox). These are plain `<select>`s — set by value:
   ST `包含ST=0 / 排除ST=1 / 仅有ST=-1`; 科创板 `排除=1 / 包含=0 / 仅有=-1`; 行业标准 `申万2014=0 / 2021=1`.
   ⚠ 我的股票池 also holds many SAVED pools (e.g. `ST股票`, `ST股票_大市值50`, `评级机构数最多600`,
   `市值最小10pct_pe大于0`) — a one-click way to reproduce a book's exact universe.

   **⚠ The universe dropdowns are LOAD-BEARING — set them to match the book BEFORE 开始选股, or the result is
   the full ~4600-name market, not the book's universe.** Validated 2026-06-27: setting **ST股票=仅有ST**
   collapsed the result from **4597 → 170 ST names** (e.g. `form_input{ref_ST_select, "仅有ST"}` then re-run).
   An **ST book (like #18) MUST use 仅有ST** — leaving it at 包含ST silently mixes in ~4400 non-ST names and the
   parity is meaningless (this is exactly the kind of universe-spec error that the #18/北证 lessons warn about).
   The same applies to 科创板 / 上市板块 / 行业 — a 果仁 book that excludes 北证/科创 or pins a 申万 industry must
   have those dropdowns set, not left at 全部. **Confirm the universe count in the result header
   (`符合条件股票 N 只`) matches the book's universe size before trusting the export.**

### 2a. 投资域 (投资域) — the FULL replication checklist (一个不漏)
A book's `universe` dict has **~12 fields**; to test whether a factor matches, EVERY one must be replicated —
not just the ranking/filter factors. A single mismatched universe knob silently changes the candidate set and
makes any factor/overlap comparison meaningless. The full checklist (from `deployed_20_recipes.md`):
`股票池 · 系统股票池 · 指数 · 板块 · 行业标准(申万2014/2021) · 行业 · 二级行业 · 交易所 · 地区省份 ·
企业性质 · 融资融券 · ST股票 · 科创板 · 过滤停牌股票`.

**The three load-bearing filters at the top of the page — exact semantics + local mapping:**

| 果仁 dropdown | options (select value) | what it does | LOCAL equivalent |
|---|---|---|---|
| **ST股票** | 包含ST `0` / 排除ST `1` / **仅有ST** `-1` | keep both / drop ST·*ST / keep ONLY ST·*ST | `ru.st_codes_on(d)` from the authoritative range-form `data/qlib_data/instruments/st_stocks.txt` (§3.1). 排除→`code not in st`; 仅有→`code in st`. |
| **科创板** | **排除科创板** `1` / 包含科创板 `0` / 仅有科创板 `-1` | drop 688/689 / keep / keep ONLY STAR | use the shared `board_of()` (`workspace/research/jq_replication/jq_rep_utils.py`): STAR = `board_of(c)=="star"`; 排除→drop STAR; 包含→keep; 仅有→keep only STAR. **Do NOT build universes from bare prefix tuples** — `MAIN_PREFIXES`-style snapshots drift (they miss new 30xxxx ChiNext names, e.g. 302xxx); a legacy prefix list must be asserted == `board_of()` on the frozen provider first. |
| **过滤停牌股票** | 是 (checked) / 否 | drop names 停牌 on the date / keep | schedule proxy `close_raw.loc[pday].notna()` (suspended ⇒ NaN OHLCV row ⇒ dropped) + the engine's `can_buy` tradability gate on `d`. |

**★★ THE TRAP — 科创板 is a SEPARATE knob from 板块.** `板块=全部` does **NOT** put STAR (688/689) in the
universe — the **科创板 dropdown independently removes it**. Across the deployed-20, MOST books are
`板块:全部 + 科创板:排除科创板` ⇒ **STAR is excluded even though "all boards" is selected** (#1/#2/#4/#6/#7/#8/#9…).
Only #3/#5/#15/#18 use `包含科创板`. So when reading a recipe, the 688/689 membership is decided by the **科创板**
field, never by 板块. (Symmetrically, 果仁's `全部股票` already excludes **北证/BSE** — 8xx/920/.BJ are never in
it, proven via holdings; locally enforce this with `board_of(c) != "bse"`, NOT a bare prefix tuple — legacy
`MAIN_PREFIXES` snapshots are drift-prone and currently miss 30xxxx ChiNext extensions such as 302xxx.)

**过滤停牌 timing note (honest, not bit-exact):** 果仁's 过滤停牌:是 evaluates suspension as-of the trade day
`d`; our schedule proxy evaluates `notna()` on the T−1 signal day `pday`. The residual case (trades on pday,
halts at the open of `d`) is caught by the engine's `can_buy` NaN/`vol==0` guard (the name simply can't be
bought), so the net behavior matches — but a slot 果仁 would refill from rank-6 may go unfilled locally. Bounded,
second-order. If a book sets **过滤停牌:否** (e.g. #14), do NOT apply the `notna()` drop in that harness.
3. **Add a 排名条件:** ⚠ **click the 排名条件 tab FIRST** — selecting an indicator from the search adds it to
   whichever tab (筛选条件 / 排名条件) is ACTIVE, and the default-active tab is 筛选条件, so skipping this adds
   your factor as a *filter* `> 0` (seen 2026-06-27 — had to delete it and redo). With 排名条件 active: type the
   indicator in the **选股指标** search box (`搜索财务选项与指标`) → a dropdown lists matches as
   `category--group--name` (e.g. `行情--股本和市值--总市值`; `分析师--评级--评级机构数`; custom factors appear as
   `自定义--...` — pick the right one, NOT a `..中性化` variant) → click it. It adds a row with **次序** (从小到大
   `asc` / 从大到小 `des`), **范围** (全部 `0` / 一级行业内 `1` / 二级行业内 `2`), **权重** (text, default 1), and
   an enable checkbox. **The trailing number in a 果仁 recipe IS the 权重** — set it. Duplicate the same indicator
   at different 范围 for the book's split terms (e.g. 总市值 全部 + 总市值 一级行业内 are two rows). **范围 changes
   only the 总排名分, not the displayed indicator value** (PROVEN — see Export format).
4. **Add a 筛选条件 (if any):** click the **筛选条件** tab → search + click the indicator → set **比较符**
   (>, <, 区间, 排名%区间, 排名%最大/最小, =, …), **范围**, and **值**. ⚠ Filter direction is indicator-specific
   — for a `排名%区间 0%–65%` style filter, verify against 果仁's actual holdings which end it lands on (the
   #4 ILLIQ bug: "0–65%" was DESCENDING = keep the most-illiquid 65%, not the most-liquid).
5. **每日选股:** click the **每日选股** bottom tab → set **选股日期** → **开始选股**.
   **⚠ CRITICAL — the 选股日期 MUST be within LOCAL data coverage to be reproducible.** The field DEFAULTS to
   *today* (e.g. `2026/06/26`), which is OUTSIDE our frozen local calendar — a selection on that default date can
   NOT be matched by any local reproduction (we have no data past the freeze). **Always set 选股日期 to a trading
   day ≤ the local provider calendar max** — `guorn_factor_parity.py` reads it from `data/reference/trade_cal.parquet`
   and prints it at runtime, and fails closed on a non-trading or out-of-range date (don't rely on a date shown
   in a historical example).
   Validated 2026-06-27 with **`2025/12/31`**
   (`form_input{ref_date, "2025/12/31"}` → confirm it changed off `2026/06/26` → 开始选股). It ran and the
   export is locally re-runnable.
   - ⚠ For a PAST date 果仁 adds a **未来5日涨幅** (realized forward 5-day return) column — useful as an
     eyeball sanity check, but it is **LOOKAHEAD**; never feed it into a factor or selection.
   - ⚠ The 开始选股 button MOVES as the page re-renders/scrolls after a 选股日期 change. A stale-coordinate
     click misses silently and you see the OLD result (e.g. still `4597只`). Re-screenshot for fresh
     coordinates (or click by `ref`) and confirm the header count changed before exporting.

   The list renders below: `序号 | 股票 | 行业分类 | 收盘价 | 当日成交量(万) | 1日涨幅 | <ranking indicators…> |
   总排名分`. Header shows `符合条件股票 N 只` — **cross-check N against the intended universe** (170 for 仅有ST,
   ~4600 for 全部) as the proof the universe + date took effect.
   - The indicator columns shown = the 排名条件 indicators (so a multi-factor composite shows each factor's
     value per stock — direct factor-level parity, like the xlsx 各阶段持仓详单 export but for ANY date).
6. **导出 + rename:** click **↓导出** (top-right of the results table) → an `.xlsx` downloads to
   `Knowledge\果仁验证因子\<hash>.xlsx`. **Immediately rename** to the convention
   **`果仁_{选股日期YYYYMMDD}_{universe}_{条件描述}.xlsx`** (e.g.
   `果仁_20260626_全部股票_排名-总市值降序.xlsx`, `果仁_20251231_仅有ST_排名-总市值降序.xlsx` ← validated value
   example, `果仁_20251231_排除ST排除科创_排名-评级机构数.xlsx` ← validated count example (the comparator's
   worked cases), `果仁_20240628_仅有ST_筛选涨幅250rank0-75_排名6因子.xlsx`). The hash name is not traceable —
   never leave it. Put the `仅有ST`/`科创` etc. universe in the filename so the universe knob is self-documenting.

## Export format (the verification payload)
`pd.read_excel` → columns: `股票代码, 股票名, 行业大类, 二级行业, 收盘价, 当日成交额(万), 1日涨幅,
[未来5日涨幅 if past date], <each 排名指标>, 总市值(亿)…, 总排名分`. 总排名分 = 果仁's 综合排名分 =
Σ(per-factor 排名分 × 权重), 0–100 (100 = top). **This is the ground truth for the local composite** — compare:
- ⚠ **Header/name strings may come back GBK-garbled** under a default `pd.read_excel` (seen on the 仅有ST
  export: `股票代码`→`��Ʊ����`). The numeric **股票代码 and all value columns are clean** — key joins on the
  6-digit code (col 0) and identify columns by POSITION, not the garbled header text. (The 全部股票 export read
  cleanly — the garbling is inconsistent, so always position-key to be safe.)
- ⚠⚠ **股票代码 is stored as an INTEGER → SZ/BSE codes LOSE their leading zeros** (`001270`→`1270`,
  `000656`→`656`). A naive `(\d{6})` regex SILENTLY DROPS every such row — in a real run this dropped **96 of
  170** before it was caught. ALWAYS zero-pad: `f"{int(x):06d}"` (or `.str.zfill(6)` after stripping non-digits).
  `guorn_factor_parity.py::_code6` does this; reuse it.
- ⚠ **The indicator value column is 范围-INVARIANT** (PROVEN 2026-06-27: 评级机构数 column byte-identical between
  范围=全部 and 范围=一级行业内, max diff 0.0). 范围 changes ONLY the **总排名分** (within-industry vs global rank;
  2345/4412 scores differed). ⇒ to verify a factor **VALUE**, compare the indicator column directly even when
  the book uses 范围≠全部; to verify a **composite / 总排名分**, you must reproduce the within-industry grouping
  locally (`cs_mean($f grouped by $sw2021_l1)`, the HAVG note in guorn_local_field_mapping.md §1b).
- membership/overlap (果仁's top-N stock codes vs the local schedule's top-N), and
- per-stock 总排名分 vs the local composite score (Spearman), and
- per-factor value parity (the indicator columns vs the local factor frame at the same date, signal-lag T−1).

## Closing the loop — the LOCAL side + the `guorn_factor_parity.py` comparator
Capturing 果仁's export is only HALF of a consistency check; you must also (a) compute the matching LOCAL
factor, (b) join on code, (c) compare with a metric. **Reusable comparator:**
[workspace/scripts/guorn_factor_parity.py](../../../scripts/guorn_factor_parity.py) —
`(export.xlsx, local qlib expression, date) → parity metrics + verdict`. NON-FORMAL diagnostic.

```
venv/Scripts/python.exe workspace/scripts/guorn_factor_parity.py \
    --xlsx Knowledge/果仁验证因子/<export>.xlsx --date YYYY-MM-DD \
    --local-expr '<qlib expr in 果仁 display unit>' --guorn-col <name|idx> [--lag 1|0] [--kind value|count]
```

**Validated worked examples (2026-06-27):**
- VALUE — `总市值(亿)` vs `$total_mv/1e4`, 170 ST names @2025-12-31: coverage 100%, **Spearman 0.999 / Pearson
  1.000 / sign 100%**, median rel-err 1.08% → ◑ structure-exact (residual = 果仁's 2-dec 亿 display-round on
  tiny ST caps; 总市值 reproduces).
- COUNT — `评级机构数` vs `$report_rc__n_active_orgs` @2025-12-31: **92% coverage** (4057/4412; 355 果仁 names
  absent from the frozen provider → the default `--min-coverage 0.98` returns `✗ coverage gap`; rerun with
  `--min-coverage 0.90` + that documented reason), **exact 70.8% / corr-on-non-zero 0.990 / Spearman 0.982 /
  frac>0 57.7% vs 57.4%** → **`◑ vendor-approx rank-faithful`** (usable as a RANKING factor; NOT a threshold/audit
  value — the 29% non-exact = Tushare 卖方研报 ≠ 果仁 朝阳永续, ±1–2 analysts). Re-confirms the #18 field at the
  RANK level, with the coverage gap surfaced (not a blanket ✅).

### The LOCAL side — which field/expression (the canonical map)
**[guorn_local_field_mapping.md](guorn_local_field_mapping.md) is the canonical 果仁-indicator → local-field
ledger** (§1 = ~25 validated mappings with parity status; §0 = the conventions). The load-bearing conventions
every comparison must apply:
- **Signal lag** — 果仁 displays each factor as-of the SIGNAL day = **T−1** (trading day before the buy day);
  `--lag 1` (default). PIT-gated fundamentals gate lag-0 → `--lag 0`.
- **Units** — land the local expr on 果仁's DISPLAYED unit: 总市值(亿)=`$total_mv/1e4` (万元→亿);
  成交额(亿)=`$amount/1e5` (千元→亿); BP needs `×1e4` (equity元 / mktcap万元). Or pass `--guorn-scale`.
- **后复权** — `$close × $adj_factor`; for a price RATIO (e.g. 250日涨幅) it is 复权-base-invariant; raw close is wrong.
- **single-quarter** — `$<field>_sq_q0` = latest single Q; TTM = Σ(`_sq_q0.._q3`); 去年同期 single-Q = `_sq_q4`.
- **POINTWISE qlib expressions only** (`--local-expr '($revenue_sq_q0-$oper_cost_sq_q0)/$total_assets_q0'`) —
  raw fields / arithmetic / time-series ops, which qlib evaluates per-instrument, so the export-codes-only fetch
  is exact. The comparator **REFUSES cross-sectional / group / neutralized / composite** expressions (`cs_`,
  HAVG, neutralize) — those change with the instrument set; verify them on the FULL universe via the 综合级 harness.

### The JOIN — 6-digit 果仁 code → Qlib instrument
果仁 exports a bare 6-digit code; local frames are Qlib form (`603268_SH`). The comparator maps via the
PROVIDER instrument list (`{c.split('_')[0]: c}` from `D.list_instruments('all')` — robust, no fragile prefix
table). Human-readable suffix rule (reference): SH = `600/601/603/605/688/689/900`; SZ =
`000/001/002/003/300/301/200`; BSE/`.BJ` = `43x/83x/87x/88x/920`. ⚠ Zero-pad the 6-digit FIRST (int-truncation trap).

### Acceptance rubric (the de-facto rung-4 standard)
| metric (comparator prints) | for | "reproduces" looks like |
|---|---|---|
| coverage (GATE) | all | ≥ `--min-coverage` (default 0.98) before ANY ✅ — below it the verdict is forced to `✗ coverage gap` (a high score on a partial panel can be survivorship/join-broken). Lower only with a documented reason. |
| median \|rel-err\|, within 0.1/1/5% | continuous | med ≤ 1% & within-5% ≥ 90% = display-exact |
| sign-agreement | signed | ≥ 97% (a sign flip = wrong direction = real bug) |
| Spearman / Pearson | all | ≥ 0.95 = same factor; low = real divergence |
| EXACT-match + frac>0 breadth | integer/count | ≥ 95% & breadth-match = same-vendor exact; lower + corr≥0.95 = vendor-approx **rank-faithful (ranking-only, NOT threshold)** |
| corr-on-non-zero | sparse/count | the real test for a sparse field (≥ 0.95 = tracks) |

Verdict tiers — value: **✅ penny/display-exact** · **◑ structure-exact** · **✗ divergence**; count: **✅ same-vendor
count-exact** (exact≥95% + matching >0 breadth) · **◑ vendor-approx rank-faithful** (corr≥0.95 — ranking/composite
use ONLY, NOT threshold/value-exact) · **✗**. Any tier is OVERRIDDEN to **✗ coverage gap** when coverage < `--min-coverage`.
**Reading a residual (the discipline):** a gap is NOT automatically a local bug — rule out, IN ORDER, (1) lag
mismatch (T−1 vs lag-0), (2) unit/scale, (3) 后复权 base, (4) **calendar / suspension / window-membership
convention** (proven to drive long-window residuals — 250日涨幅, 乖离率 — that are NOT data/vendor errors),
(5) **vendor** (果仁 朝阳永续 / its own 复权 — legitimately different), THEN (6) a local bug. Localize before you
claim. (The #18 lesson: prove a field by this DIRECT comparison, never by a book's return.)

## Using it for parity (the high-value play)
- **Field validation** (e.g. did `$report_rc__n_active_orgs` reproduce 评级机构数?): rank-only on 评级机构数,
  export, compare the per-stock value to the local field at T−1. (Beats inferring from a book's return —
  the #18 trap: that book's field was degenerate on ST.)
- **Composite validation**: stack the book's full 筛选+排名 with the recipe weights, export the 总排名分,
  and compare to the local `_composite_row` output → isolates "selection-divergence is factor-X" exactly,
  on the exact date — no backtest needed.
- **Filter direction**: export filter-only membership to confirm a 排名%区间 direction before trusting a harness.

## Automation notes (Claude-in-Chrome)
- `tabs_context_mcp{createIfEmpty:true}` → `navigate` → `read_page{filter:"interactive"}` to get fresh
  element `ref_`s (they are session/render-specific — re-read after each major UI change), then
  `form_input{ref,value}` for `<select>`/text and `computer{left_click, ref|coordinate}` for tabs/buttons.
  `find{query}` locates an element by description but can match the wrong one of several same-named controls
  (there are multiple 次序 dropdowns — disambiguate via `read_page`).
- Batch predictable click→type→screenshot sequences with `browser_batch`. The viewport can resize between
  calls (a coordinate from an earlier screenshot may miss) — screenshot fresh before a precise click.
- The 导出 download is silent (no dialog) → confirm by `ls -lt Knowledge/果仁验证因子/` and rename.
- **导出 is async + can be flaky (observed 2026-07-01):** the click fires `POST /stock/export/screen` → `GET /file/<hash>.xlsx`; that GET may **503 (not ready) → briefly 200 → 404**. The browser's own GET often loses the race, but **the file still lands in `Knowledge/果仁验证因子/` as `<hash>.xlsx`** — just re-click 导出 and re-check `ls -t`. A real file is **~300KB+**; a 69-byte file is the 404-HTML stub (discard). Do NOT try to blob-fetch `/file/<hash>` in JS (same race/expiry) — read the saved `.xlsx` from disk. Fire 导出 with a full `mousedown→mouseup→click` MouseEvent sequence (a bare `.click()` may not fire the handler).

## Caveats
- 果仁 web uses its OWN data/vendor (朝阳永续 for 评级/预期; its own 复权/calendar). A local↔果仁 value gap can
  be a vendor difference, not a local bug — that's the point of the comparison (localize it). Match the
  signal-date lag (果仁 displays as-of T−1 vs the buy day; see guorn_local_field_mapping.md §0).
- NON-FORMAL research tooling. Pin the 选股日期 for reproducibility; record the exact 筛选/排名/权重/universe in
  the filename + a sidecar note so a result is re-runnable.
