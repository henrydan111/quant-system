# Tushare 15000积分 — Data Expansion Analysis & Plan

*Authored 2026-06-07. Ground truth = live API access probe, not memorized point tiers.*

> **⚠ SUPERSEDED ON COVERAGE (2026-06-07, same day).** This doc was written off the *access* probe
> only. A follow-up *history-coverage* probe overturns the Wave 2/3 sequencing: `limit_list_d` is
> 2020+ only, `moneyflow_dc`/`hm_detail` are 2024+ only, and concept membership has **no** deep
> history in Tushare (`ths_member` current-only, `dc_member` 2025-snapshot) — so Waves 2/3 **cannot**
> run the standard IS-2014-20 protocol, and `dc_member` is **not** a viable as-of-membership source
> (route concept membership through the existing JoinQuant PIT cache instead). Wave 1 (analyst/
> earnings) and most of Wave 4 (governance) survive with deep history. The corrected view + verified
> coverage table live in [cross_review_for_gpt.md](cross_review_for_gpt.md) §2.2–§3.

## 0. Method (why this is verified, not guessed)

The account was upgraded 5000 → 15000 积分. To answer "what new data can I acquire" without
relying on memorized/stale point tiers (research-integrity §7.10: no plausible guesses), I ran a
**strictly-sequential, read-only access probe** against the live API:
[probe_tushare_endpoints.py](../../scripts/probe_tushare_endpoints.py) — 55 high-value endpoints the
system does **not** currently ingest, one minimal call each (single date / single code), capturing
the exact permission message Tushare returns.

**Result: 54/55 `ACCESS`, 1 `ACCESS_PARAM` (missing arg only — permission OK), 0 `DENIED`.**
Raw report: [tushare_endpoint_probe_20260607T084742Z.json](../../outputs/tushare_endpoint_probe_20260607T084742Z.json).

> Honest scope caveat: the account is already upgraded, so I cannot re-test the old 5000 ceiling.
> The deciding fact is not "which tier gated it" but "we don't ingest it and it's now callable" — so
> every endpoint below is a real expansion candidate. Per Tushare's published tiers + this repo's own
> fetcher notes, the bolded flagships (`report_rc`, `stk_factor_pro`, the `ths_*`/`dc_*` concept+flow
> family, `limit_list_*`, `kpl_*`, `hm_*`, `stk_surv`, `moneyflow_hsgt`, `*_vip` bulk) sit above the
> 5000 line; that attribution is documentation-sourced, the access result is tested.

## 1. What the current system already ingests (baseline)

From [fetchers/__init__.py](../../../src/data_infra/fetchers/__init__.py) +
[data_tracker.md](../../../data/data_tracker.md):

- Market daily: `daily`, `adj_factor`, `daily_basic`, `stk_limit`, `suspend_d`
- Index: `index_daily`, `index_weight`, `index_basic`, `index_classify` (SW2021), `index_member_all`
- Fundamentals (PIT ledger): `income(_vip)`, `balancesheet(_vip)`, `cashflow(_vip)`,
  `fina_indicator(_vip)`, `forecast`, `dividend`
- Alpha/flow (5000 tier, approved 2026-06-04): `moneyflow`, `hk_hold` (northbound), `margin_detail`,
  `stk_holdernumber`, `top_list`, `top_inst`, `block_trade`, `stk_holdertrade`, `cyq_perf`
- Reference: `stock_basic`, `trade_cal`, `namechange`, SW industry members

So the system is rich in **price + fundamentals + moneyflow + LHB/chip**, and notably **missing
analyst/consensus, concept-theme membership, limit-board/打板 sentiment, governance events, and a
second flow vendor.** The recent new-data factor screen (0/8 cleared the bar — moneyflow-derived)
argues for adding *orthogonal* sources, not more of the same family.

## 2. Newly-acquirable data, ranked by orthogonal-alpha value

### Tier A — orthogonal fundamental/event alpha (PIT-clean, literature-backed)

| Endpoint | What it is | Key fields (probed) | Why it matters | PIT anchor |
|---|---|---|---|---|
| **`report_rc`** | Sell-side analyst earnings forecasts + ratings | `report_date, eps, np, tp(target price), rating, roe, pe, op_pr, quarter, org_name` | The classic A-share orthogonal alpha: **EPS-revision, consensus dispersion, rating change, target-price implied return, SUE vs consensus**. Not derivable from anything we own. | `report_date` (forward consensus — anchor strictly, never use the forecast period's future) |
| `express`, `express_vip` | 业绩快报 (preliminary earnings) | `ann_date, end_date, revenue, n_income, total_assets, eps, ...` | Earnings land **earlier** than the full statement → earlier earnings-surprise/drift signal. Slots into existing PIT ledger. | `ann_date` (max with f_ann_date) |
| `fina_mainbz(_vip)` | Main-business / segment revenue breakdown | `end_date, bz_item, bz_sales, bz_profit, bz_cost` | Segment growth, revenue concentration (HHI), thematic exposure mapping. | report disclosure (`ann_date` joined from statement) |
| `disclosure_date` | Scheduled report-release calendar | `ts_code, end_date, actual/plan dates` | **PIT/event infrastructure**: pre-announcement drift windows, "report due" gating. Cheap, enables better event timing for everything else. | plan date is forward-known |
| `fina_audit` | Audit opinion | `audit_result, audit_agency` | Non-standard opinion = hard risk flag. Cheap, sparse. | `ann_date` |

### Tier B — A-share sentiment / flow style (a *new style*, addresses the 100%-long-only gap)

| Endpoint | What it is | Key fields | Why it matters | PIT |
|---|---|---|---|---|
| **`limit_list_d`** | Daily limit-up/down board | `limit_times(连板), fd_amount(封单), open_times, up_stat, first_time, last_time, limit` | Core to 打板/连板/sentiment-momentum — a style **distinct** from our value/quality book. Sealing strength, streak, failed-limit reversal. | trade_date outcome → `Ref(...,1)` |
| `moneyflow_dc` | 个股资金流 (东方财富) — full market | `net_amount, buy_elg/lg/md/sm_amount(+rate)` | A **second, independent flow vendor** vs the `moneyflow` we already approved → cross-vendor robustness; their nets may be cleaner (our `$net_mf_amount` is an opaque vendor net). | trade_date → `Ref(...,1)` |
| `moneyflow_ind_dc`, `moneyflow_mkt_dc` | Sector & market flow (东财) | sector/market net flows | Sector-rotation and market-breadth/timing signals. | trade_date → `Ref(...,1)` |
| `hm_list`, `hm_detail` | 游资 (named hot-money) daily activity | `hm_name, ts_code, buy_amount, sell_amount, net_amount` | A-share-specific sentiment; named-desk participation. Sparse event. | trade_date → `Ref(...,1)` |
| `stk_surv` | Institutional research surveys (调研) | `surv_date, org_type, fund_visitors, rece_org` | Documented positive event signal (institutions visiting). Sparse. | `surv_date` |
| `kpl_list`, `kpl_concept(_cons)` | 开盘啦 打板 list + concept tags | board lists, concept membership | Retail-sentiment / theme tags. Overlaps `ths_*`. | trade_date → `Ref(...,1)` |

### Tier C — concept/theme membership infrastructure (high value, PIT-hazardous)

| Endpoint | What it is | Fields | Note |
|---|---|---|---|
| `ths_index` (1725 indices), `ths_member`, `ths_daily` | 同花顺 concept/industry universe, membership, daily index OHLC | `ts_code, con_code, con_name`; daily index bars | We only have **SW industry** today. Concepts unlock theme-rotation + concept-momentum and feed the existing `theme_strategy` profile. |
| `dc_index`, `dc_member` | 东方财富 concepts + membership | `trade_date, con_code, name` | `dc_member` carries `trade_date` → easier point-in-time than `ths_member` (current-only). |

⚠ **PIT hazard:** `ths_member` returns **current** membership → survivorship + lookahead if used naively.
Must be built into an **as-of membership table with in/out dates** exactly like the SW-members work
([fetch_sw_industry_members.py](../../../scripts/fetch_sw_industry_members.py),
`industry_as_of()`). `dc_member`'s per-day `trade_date` makes it the safer first target.

### Tier D — governance / ownership events (sparse event alpha + risk overlays)

| Endpoint | Signal type | PIT |
|---|---|---|
| `repurchase` | Buyback announced → positive | `ann_date` (forward-known exp_date) |
| `share_float` | 限售解禁 unlock → supply overhang (negative) | `float_date` is announced ahead → tradable forward calendar (clean PIT) |
| `pledge_stat`, `pledge_detail` | Share-pledge ratio → tail risk overlay | `end_date`/`ann_date` |
| `top10_holders`, `top10_floatholders` | Ownership concentration, holder Δ | `ann_date`/`period` |
| `stk_managers`, `stk_rewards` | Governance/insider comp (lower priority) | `ann_date` |

### Tier E — context / convenience (low marginal alpha, cheap & useful)

- `index_dailybasic` — index PE/PB/turnover → market valuation regime / timing. Tiny.
- `sw_daily` — 申万 sector index daily → sector-relative returns, neutralization. Small.
- `stk_factor_pro` — **261** pre-computed technical factors (incl. 复权 variants). We compute our own
  via Qlib operators, so marginal; value = fast feature pack / cross-check. **Heavy** (261 cols × full
  history). `stk_factor` is the lighter 35-col version.
- `bak_daily` — 备用行情 with `selling`/`buying`/`swing` → a buy/sell pressure proxy.
- `daily_info` — market-wide breadth stats.

### Tier F — explicit defer / out-of-scope (available, but not now)

- `stk_mins` (1/5/15/30/60-min bars) — **accessible**, but intraday is a different research paradigm +
  large storage. Park unless we open an intraday track.
- `cyq_chips` — per-price-level chip distribution; we already have the `cyq_perf` summary → redundant
  for now, heavy.
- `ccass_hold(_detail)` — overlaps northbound `hk_hold` we already serve.
- `cb_daily` (convertible bonds), `fund_nav` (funds/ETF) — new asset classes, out of equity scope.
- `index_global`, `broker_recommend` — nice-to-have macro/overlay, low priority.
- `hsgt_top10`, `ggt_top10`, `moneyflow_hsgt` — coarse connect aggregates; we have per-stock `hk_hold`.

## 3. Integration cost — every endpoint pays the same governance toll

Adding a source is **not** just a download. The established path (CLAUDE.md §3.4/§6, field-registry
governance) per endpoint:

1. **Fetch script** — idempotent per-year, strictly sequential, `base_sleep≥1.5`, `tqdm`/log progress,
   `--dry-run` (mirror [fetch_new_alpha_endpoints.py](../../../scripts/fetch_new_alpha_endpoints.py)).
2. **Raw Parquet** under `data/` (per-date `YYYY/...` or per-stock/year), + `data_dictionary.md` +
   `data_tracker.md` updates.
3. **Normalize** → `data/normalized/`; fundamentals/events also get a **PIT ledger** entry with the
   correct disclosure anchor, fed through `pit_alignment_core`.
4. **Qlib materialization** — event-like daily endpoints **must** be namespaced `{dataset}__{col}`
   (and listed in `EVENT_LIKE_DAILY_DATASETS`/`_FIELD_PREFIX`) to avoid shadowing OHLCV bins.
5. **Field-registry governance** — add to [field_status.yaml](../../../config/field_registry/field_status.yaml)
   as `quarantine`/`pending_review`; run coverage + live-provider parity audit; promote with an
   append-only `field_approval_log.jsonl` entry + a per-promotion YAML under `approvals/`.
6. **PIT discipline** — same-day daily outcomes (flow, limit board, LHB) are knowable only at close T →
   predictive factors **must** wrap every field in `Ref(...,1)` (enforced by the PIT-safety lint).

**Time cost note:** per-stock full-history endpoints over ~5,800 names at 1.5 s/call ≈ **2–2.5 h per
pass**. `report_rc` is the heaviest (one stock already returns 5,000 paginated rows → full-market is
millions of rows; fetch by `report_date` ranges, not per-stock-then-paginate). Budget accordingly.

## 4. Proposed phased plan

Sequenced by (orthogonal alpha × PIT-cleanliness ÷ integration cost). Each wave is independently
shippable and ends at a registry promotion.

**Wave 1 — Analyst & earnings-timing (flagship orthogonal alpha).**
`report_rc` + `express`/`express_vip` + `disclosure_date` + `fina_audit`.
- Highest expected orthogonal alpha; all PIT-clean (disclosure-anchored), reuse the existing PIT-ledger
  machinery. Deliver `report_rc` first as a standalone consensus panel + a revision/SUE-vs-consensus
  draft factor family; pre-register before screening (research-integrity §7).

**Wave 2 — Sentiment/flow style (new style for the long-only-only book).**
`limit_list_d` + `moneyflow_dc`(+`_ind_dc`,`_mkt_dc`) + `stk_surv` + `hm_detail`/`hm_list`.
- All same-day outcomes → `Ref(...,1)` + namespaced bins. `moneyflow_dc` doubles as a robustness
  cross-check on our existing (caveated) `moneyflow` nets.

**Wave 3 — Concept/theme membership (careful PIT).**
`dc_index`+`dc_member` first (per-day → safer as-of), then `ths_index`+`ths_member`+`ths_daily` built
into an **as-of in/out-date membership table** (reuse the SW-members pattern). Feeds `theme_strategy`.

**Wave 4 — Governance/risk + context (cheap overlays).**
`repurchase`, `share_float`, `pledge_stat` (events) + `index_dailybasic`, `sw_daily` (context).
- `share_float` is genuinely clean PIT (forward-announced unlock calendar) → good risk overlay.

**Park:** `stk_mins`, `cyq_chips`, `stk_factor_pro`, `cb_daily`, `fund_nav`, `ccass_hold`, connect
aggregates — available, revisit only if a specific research track needs them.

## 5. Honest expectation setting

Acquiring data **expands the search space; it does not promise alpha** — the last new-data screen
returned 0/8. The argument for Wave 1/2 is *orthogonality* (analyst consensus and limit-board sentiment
are uncorrelated with the price+fundamentals+moneyflow factors already screened), which is where new
information, if any, will live. Every factor built on this data still goes through the full IS-only
gate → sealed-OOS lifecycle. The flagship single best bet is **`report_rc`**.
