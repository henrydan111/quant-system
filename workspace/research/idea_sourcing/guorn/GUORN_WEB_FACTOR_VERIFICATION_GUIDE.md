# 果仁网 web platform — direct factor / selection VERIFICATION guide

> **Validated end-to-end 2026-06-27** (Claude drove the live UI: navigate → add ranking → 每日选股 → 导出 →
> rename → confirm 4597-row xlsx). This is the most powerful parity tool we have: it returns 果仁's EXACT
> stock list + **总排名分 (composite rank score)** for ANY 筛选/排名 condition on ANY date — directly
> comparable to a local factor/composite reproduction. Use it to settle "does my factor reproduce 果仁?"
> at the stock level (the #18 lesson: prove a field by direct comparison, not by a book's return).

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
3. **Add a 排名条件:** click the **排名条件** tab in the 选股条件 panel → type the indicator in the
   **选股指标** search box (`搜索财务选项与指标`) → a dropdown lists matches as `category--group--name`
   (e.g. `行情--股本和市值--总市值`; custom factors appear as `自定义--...`) → click the right one. It adds a
   row with **次序** (从小到大 `asc` / 从大到小 `des`), **范围** (全部 `0` / 一级行业内 `1` / 二级行业内 `2`),
   **权重** (text, default 1), and an enable checkbox. **The trailing number in a 果仁 recipe IS the 权重** —
   set it. Duplicate the same indicator at different 范围 for the book's split terms (e.g. 总市值 全部 + 总市值
   一级行业内 are two rows).
4. **Add a 筛选条件 (if any):** click the **筛选条件** tab → search + click the indicator → set **比较符**
   (>, <, 区间, 排名%区间, 排名%最大/最小, =, …), **范围**, and **值**. ⚠ Filter direction is indicator-specific
   — for a `排名%区间 0%–65%` style filter, verify against 果仁's actual holdings which end it lands on (the
   #4 ILLIQ bug: "0–65%" was DESCENDING = keep the most-illiquid 65%, not the most-liquid).
5. **每日选股:** click the **每日选股** bottom tab → set **选股日期** (any historical trading day;
   reproducibility ⇒ pin a specific date) → **开始选股**. The list renders below: `序号 | 股票 | 行业分类 |
   收盘价 | 当日成交量(万) | 1日涨幅 | <ranking indicators…> | 总排名分`. Header shows
   `符合条件股票 N 只`.
   - The indicator columns shown = the 排名条件 indicators (so a multi-factor composite shows each factor's
     value per stock — direct factor-level parity, like the xlsx 各阶段持仓详单 export but for ANY date).
6. **导出 + rename:** click **↓导出** (top-right of the results table) → an `.xlsx` downloads to
   `Knowledge\果仁验证因子\<hash>.xlsx`. **Immediately rename** to the convention
   **`果仁_{选股日期YYYYMMDD}_{universe}_{条件描述}.xlsx`** (e.g.
   `果仁_20260626_全部股票_排名-总市值降序.xlsx`, `果仁_20240628_仅有ST_筛选涨幅250rank0-75_排名6因子.xlsx`).
   The hash name is not traceable — never leave it.

## Export format (the verification payload)
`pd.read_excel` → columns: `股票代码, 股票名, 行业大类, 二级行业, 收盘价, 当日成交额(万), 1日涨幅,
<each 排名指标>, 总市值(亿)…, 总排名分`. 总排名分 = 果仁's 综合排名分 = Σ(per-factor 排名分 × 权重),
0–100 (100 = top). **This is the ground truth for the local composite** — compare:
- membership/overlap (果仁's top-N stock codes vs the local schedule's top-N), and
- per-stock 总排名分 vs the local composite score (Spearman), and
- per-factor value parity (the indicator columns vs the local factor frame at the same date, signal-lag T−1).

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

## Caveats
- 果仁 web uses its OWN data/vendor (朝阳永续 for 评级/预期; its own 复权/calendar). A local↔果仁 value gap can
  be a vendor difference, not a local bug — that's the point of the comparison (localize it). Match the
  signal-date lag (果仁 displays as-of T−1 vs the buy day; see guorn_local_field_mapping.md §0).
- NON-FORMAL research tooling. Pin the 选股日期 for reproducibility; record the exact 筛选/排名/权重/universe in
  the filename + a sidecar note so a result is re-runnable.
