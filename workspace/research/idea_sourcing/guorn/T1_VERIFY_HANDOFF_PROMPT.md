# Handoff prompt — verify the T1 果仁 factors (paste into a fresh Chrome-connected Claude Code session)

---

You are continuing a 果仁 (guorn.com) parity-verification campaign on the A-share quant system at `E:\量化系统`
(果仁 = trusted benchmark; the local Tushare+Qlib system is under test). A prior session BUILT the local
reproductions of 6 "Tier-1" derived factors but could not verify them because the Claude-in-Chrome MCP had
dropped. **Your job: drive the 果仁 web UI to export each factor, run the comparator, and record the verdict.**
NON-FORMAL parity work (no publish / no registry / no field_status writes).

## First, read these (context + protocol + the exact commands)
- `workspace/research/idea_sourcing/guorn/T1_DERIVED_FACTORS.md` — **the runbook: each factor's local reproduction + the exact verify command.**
- `workspace/research/idea_sourcing/guorn/GUORN_WEB_FACTOR_VERIFICATION_GUIDE.md` — the full, validated 果仁-web protocol (navigate → universe → 排名条件 → 每日选股 → 导出 → rename).
- `workspace/research/idea_sourcing/guorn/guorn_web_validation_campaign.md` — the campaign tracker to update (rows #5, #32, #23, #21, #51, #47; #43 RnDTTMGr%PY is already done).
- Comparator: `workspace/scripts/guorn_factor_parity.py` (now supports `--local-series <parquet>` AND `--local-expr`).

## Setup
1. `list_connected_browsers` → `select_browser` → confirm logged into guorn.com (account "leodan").
2. Generate the local series (full universe, not the prior --limit sample):
   ```
   venv/Scripts/python.exe workspace/scripts/guorn_days_listed.py --date 2025-12-31
   venv/Scripts/python.exe workspace/scripts/guorn_beta.py --date 2025-12-31 --n 250          # may be slow → run_in_background
   ```
   (ATR% + EpsTTMGr% are `--local-expr`, no pre-compute.)

## The 果仁 web flow (per factor — see the GUIDE for depth; key points)
Navigate `https://guorn.com/stock?category=stock`. Then:
- **Universe** (LOAD-BEARING): set **ST股票 = 排除ST** (`form_input` the select to value `"1"`); **科创板 = 排除科创板** (usually already the default `"1"`); leave everything else 全部. This is the broad universe → the result header must read **符合条件股票 4412 只**.
- Click the **排名条件 tab FIRST** (else the indicator is added as a *filter*, not a ranking).
- Add the ONE indicator in the **选股指标** search box. ⚠ **Chinese indicator names (上市天数, 交易天数, 贝塔N日, 历史贝塔, ATR%收盘价N日) CANNOT be typed (no IME)** — JS-set the input value + dispatch an `input` event via `javascript_tool`, then click the dropdown match; OR pick it from the category tree (e.g. 上市天数 is directly under the 行情 tab). (ASCII names like `EpsTTMGr%` can be typed.) Confirm the **排名条件 badge = 1** (exactly one condition).
- Set 次序 = 从大到小 (or 从小到大 for a "smallest" factor — irrelevant to the exported value column, which is direction-invariant; the comparator re-ranks).
- **每日选股 tab → 选股日期 = 2025/12/31** (`form_input`; a calendar popup may open — press Escape to dismiss, the field value holds) → **开始选股**. Confirm the header count = 4412 before exporting.
- **↓导出** → a hash-named `.xlsx` downloads silently to `Knowledge\果仁验证因子\`. **Immediately rename** to `果仁_20251231_排除ST排除科创_排名-<indicator>.xlsx`.
- **To clear conditions between factors: RELOAD the page** (JS-delete is unreliable — React reverts). Then redo the universe + the next indicator.

⚠ **CAPTCHA:** 果仁 rate-limits after ~15 runs with a per-run CAPTCHA. **You must NOT solve captchas (bot-detection policy)** — ask the user to clear it; their solve completes the pending run. (6 factors ≈ 6 runs, likely under the threshold.)

## Verify each (exact commands in T1_DERIVED_FACTORS.md; --guorn-col = the indicator name)
| # | 果仁 indicator | local | expected |
|---|---|---|---|
| 5 | 上市天数 | `--local-series …/days_listed_cal_20251231.parquet` (try `_trd_` if cal diverges) | clean top-K |
| 32 | 交易天数 | `--local-series …/days_listed_trd_20251231.parquet` | trd capped pre-2008 → may mismatch |
| 23 | 贝塔N日(000001,250) | `--local-series …/beta_000001_sh_250_20251231.parquet` | clean top-K |
| 21 | 历史贝塔 | try the beta parquet FIRST; if it diverges, 果仁 likely uses a different index (沪深300 `--index 000300_sh`) or window — re-run guorn_beta.py | verify params |
| 51 | ATR%收盘价N日(20) | `--local-expr 'Mean(Greater(Greater($high-$low,Abs($high-Ref($close,1))),Abs($low-Ref($close,1))),20)/$close' --lag 0` | clean top-K |
| 47 | EpsTTMGr% | `--local-expr '(...basic_eps_sq_q0..3... - ...q4..7...)/Abs(...q4..7...)' --lag 1` (see runbook) | **VALUE-exact but top-K DIVERGED** (unstable-denom; book-immaterial — expected, don't chase) |

Run: `venv/Scripts/python.exe workspace/scripts/guorn_factor_parity.py --xlsx "Knowledge/果仁验证因子/<export>.xlsx" --date 2025-12-31 --guorn-col <indicator> [--local-series <parquet> | --local-expr '<expr>' --lag <0|1>] --min-coverage 0.90`

The comparator prints coverage / pointwise parity / Spearman / **top-5/10/20 selection overlap** + an OVERALL
verdict (machine-gated, default 0.8). A factor is verified iff pointwise AND top-K pass.

## Record + finish
- Update the campaign row for each factor in `guorn_web_validation_campaign.md` (status + verdict + the export filename), mirroring the existing #25/#43 rows. Re-run `guorn_campaign_mark.py` if it's the update path.
- ⚠ **Read a residual before calling it a local bug**, in order: lag (T−1 vs lag-0), unit/scale, 后复权 base, calendar/suspension, vendor (果仁 朝阳永续 / its own 复权), THEN a local bug.
- `#43 RnDTTMGr%PY` is already verified (◑ value-exact/top-K-diverged); its export `果仁_20251231_排除ST排除科创_排名-RnDTTMGrPY.xlsx` is on disk if you want to re-confirm.
- Commit the campaign updates. Do NOT `git push` / merge without the user's OK.

Everything the prior session built is committed (comparator `--local-series` + `guorn_days_listed.py` +
`guorn_beta.py` = commits c8fe2a9 / d5a7be5). Ask the user before any push, merge, or provider change.
