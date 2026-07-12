# Data Dictionary (数据字典)

This document provides an **exhaustive** dictionary of all data features available in the local Parquet cache. It corresponds to every single column present in the raw files.

## 0. Suspension Data (停复牌数据 — P1-1, NOT YET BOOTSTRAPPED)

### suspend_d (每日停复牌明细)
Total Columns: 4

Authoritative Tushare suspension table. Populated by
`scripts/fetch_suspend_d_historical.py` (one-time bootstrap). Stored under
`data/market/suspension/suspension_YYYY.parquet` with per-year partitions
and a consolidated range-lookup at `data/market/suspension/suspension_ranges.parquet`.
Consumed by `provider_metadata.SuspensionLookup` and
`backtest_engine/event_driven/exchange.Exchange.is_suspended()` as the
authoritative source, with `vol == 0` as the legacy fallback only.
The high-level `EventDrivenBacktester` passes this range file into `Exchange`
automatically when it exists and logs the `vol == 0` fallback when it does not.

**Live per-date store (Phase 5-C)**: the daily raw job + the monthly bump's catch-up
write a per-date snapshot at `data/market/suspend_d/<year>/suspend_d_<YYYYMMDD>.parquet`
(columns `ts_code, trade_date, suspend_type, suspend_timing`) via
`DailyDataUpdater.write_suspend_d` — an atomic overwrite that PRESERVES `suspend_timing`
(a full-day suspension has empty timing; an intraday halt is timed like `09:30-10:00`).
This timing is load-bearing for the monthly-bump daily-completeness proof
(`monthly_calendar_bump.assert_endpoints_complete_range`), which fails closed on a
`suspend_d` file that has `S` rows but no `suspend_timing` column. Consumers of the
per-date store must recurse the year partitions (e.g. `ai_research_dept` reads
`suspend_d/<year>/suspend_d_<date>.parquet` per requested day), NOT a root-level glob.
The `data/market/suspension/` range store above is the separate historical-bootstrap
layout; reconciling the two is a follow-up.

| Column | English | Chinese |
|--------|---------|---------|
| `ts_code` | TS Stock Code | TS代码 |
| `trade_date` | Trade Date | 交易日期 (YYYYMMDD) |
| `suspend_timing` | Suspend Timing | 停牌时段 (e.g. 全天停牌) |
| `suspend_type` | Suspend Type | 停牌类型 |

Consolidated range lookup (`suspension_ranges.parquet`):

| Column | English | Chinese |
|--------|---------|---------|
| `ts_code` | TS Stock Code | TS代码 |
| `suspend_start` | First Suspension Date | 停牌起始日期 |
| `suspend_end` | Last Suspension Date | 停牌结束日期 |
| `suspend_reason` | Reason / Timing | 停牌原因/时段 |

## 1. Reference Data (参考数据)

### stock_basic (股票基础信息)
Total Columns: 15

| Column | English | Chinese |
|--------|---------|---------|
| `ts_code` | TS Stock Code | TS代码 |
| `symbol` | Stock Symbol | 股票代码 |
| `name` | Stock Name | 股票名称 |
| `area` | Area | 所在地域 |
| `industry` | Industry | 所属行业 |
| `fullname` | Full Name | 股票全称 |
| `enname` | English Name | 英文全称 |
| `cnspell` | Pinyin | 拼音缩写 |
| `market` | Market | 市场类型 |
| `exchange` | Exchange | 交易所代码 |
| `curr_type` | Currency Type | 交易货币 |
| `list_status` | Listing Status | 上市状态 |
| `list_date` | Listing Date | 上市日期 |
| `delist_date` | Delisting Date | 退市日期 |
| `is_hs` | Connect Status | 是否沪深港通标的 |

### trade_cal (交易日历)
Total Columns: 4

| Column | English | Chinese |
|--------|---------|---------|
| `exchange` | Exchange | 交易所代码 |
| `cal_date` | Cal Date | 日历日期 |
| `is_open` | Is Open | 是否交易日 |
| `pretrade_date` | Pretrade Date | 上一交易日 |

### namechange (股票名称变更记录)
Total Columns: 6

Tracks all historical name changes, including ST designation/removal events. Use `change_reason` to identify ST transitions.

| Column | English | Chinese |
|--------|---------|---------|
| `ts_code` | TS Stock Code | TS代码 |
| `name` | New Name | 变更后名称 |
| `start_date` | Start Date | 变更开始日期 (YYYYMMDD) |
| `end_date` | End Date | 变更结束日期 (YYYYMMDD, None=current) |
| `ann_date` | Announcement Date | 公告日期 |
| `change_reason` | Change Reason | 变更原因 |

**`change_reason` values**: `ST`, `*ST`, `撤销ST`, `撤销*ST`, `摘星`, `摘帽`, `改名`, `完成股改`, `摘G`, `未股改加S`, `终止上市`, `恢复上市`, `恢复上市加N`, `摘星改名`, `暂停上市`, `更名`, `其他`

### stock_st_daily (每日ST股票清单)
Total Columns: 5

Daily-level ST status. Each row indicates a stock was marked ST/\*ST on that trading day. If a stock does **not** appear on a given date, it is **not** ST.

| Column | English | Chinese |
|--------|---------|---------|
| `ts_code` | TS Stock Code | TS代码 |
| `name` | Stock Name (with ST prefix) | 股票名称 (含ST标识) |
| `trade_date` | Trade Date | 交易日期 (YYYYMMDD) |
| `type` | Type | 类型 (always "ST") |
| `type_name` | Type Name | 类型名称 (always "风险警示板") |

> [!WARNING]
> **Known data gap**: 2020-01-02 is completely missing from this file (0 rows) despite being a valid trading day. Adjacent dates (2019-12-31 and 2020-01-03) are present. This is a Tushare API data gap. Use `st_stocks.txt` (Qlib instruments) as the authoritative ST source for backtesting.

## 2. Market Daily Data (市场日线数据)

### daily_price_repair_overrides (日线修复覆盖清单)

Curated row-level repair manifest for persistent Tushare daily-bar anomalies that cannot be corrected by re-fetch. These overrides are applied only in normalization and staged price export; the raw Parquet files remain unchanged.

| Column | English | Chinese |
|--------|---------|---------|
| `dataset` | Dataset Name | 数据集名称 |
| `file_name` | Raw File Name | 原始分区文件名 |
| `ts_code` | TS Stock Code | TS代码 |
| `trade_date` | Trade Date | 交易日期 |
| `column` | Repaired Column | 修复字段 |
| `repaired_value` | Repaired Value | 修复后的值 |
| `reason` | Repair Reason | 修复原因 |

### daily (日线行情 & 每日指标)
Total Columns: 27

| Column | English | Chinese |
|--------|---------|---------|
| `ts_code` | TS Stock Code | TS代码 |
| `trade_date` | Trade Date | 交易日期 |
| `open` | Open Price | 开盘价 |
| `high` | High Price | 最高价 |
| `low` | Low Price | 最低价 |
| `close` | Close Price | 收盘价 |
| `pre_close` | Previous Close Price | 昨收价 |
| `change` | Price Change | 涨跌额 |
| `pct_chg` | Percentage Change | 涨跌幅 |
| `vol` | Volume (lots) | 成交量(手) |
| `amount` | Amount (thousands) | 成交额(千元) |
| `turnover_rate` | Turnover Rate (%) | 换手率(%) |
| `turnover_rate_f` | Turnover Rate Free Float (%) | 换手率(自由流通股)(%) |
| `volume_ratio` | Volume Ratio | 量比 |
| `pe` | PE Ratio | 市盈率 |
| `pe_ttm` | PE Ratio TTM | 市盈率TTM |
| `pb` | PB Ratio | 市净率(总市值/净资产) |
| `ps` | PS Ratio | 市销率 |
| `ps_ttm` | PS Ratio TTM | 市销率TTM |
| `dv_ratio` | Dividend Yield (%) | 股息率(%) |
| `dv_ttm` | Dividend Yield TTM (%) | 股息率TTM(%) |
| `total_share` | Total Shares (10k) | 总股本(万股) |
| `float_share` | Float Shares (10k) | 流通股本(万股) |
| `free_share` | Free Float Shares (10k) | 自由流通股本(万股) |
| `total_mv` | Total Market Value (10k) | 总市值(万元) |
| `circ_mv` | Circulating Market Value (10k) | 流通市值(万元) |
| `adj_factor` | Adjustment Factor | 复权因子 |

> **Provider bare share-capital bins (`$total_share` / `$float_share` / `$free_share`) — EFFECTIVE-DATE anchored
> from THESE daily columns (fixed 2026-07-01).** Materialized by `PITBackend._materialize_share_capital_daily`
> (shared kernel `share_capital_daily_arrays`; one-time in-place fix `scripts/fix_share_capital_bins.py`).
> Before the fix, the balancesheet snapshot family's bare compat alias clobbered `$total_share` with the
> REPORT-anchored q0 series — 1-2 months late vs real share changes and inconsistent with `$total_mv`
> (found in the 果仁 parity battle; BYD 002594's 2025 3× change was in raw daily from 2025-07-29 but in the
> bin only from 2025-11-03). Units are LEGACY-preserving and deliberately asymmetric: **`$total_share` is in
> 股** (raw 万股 × 1e4 — `earn_q_eps` divides 元 by it), **`$float_share`/`$free_share` stay in 万股** (raw
> verbatim). Values forward-fill across suspension gaps (share capital is a state variable) but are NaN
> before the first daily_basic observation — notably BSE names' pre-listing NEEQ era, where the whole
> daily_basic block (incl. `$total_mv`) has no coverage. The report-period balance-sheet series remains
> available as `$total_share_q0..qN` (that family is CORRECTLY report-anchored — do not "fix" it).

### index (指数行情)
Total Columns: 11

| Column | English | Chinese |
|--------|---------|---------|
| `ts_code` | TS Stock Code | TS代码 |
| `trade_date` | Trade Date | 交易日期 |
| `close` | Close Price | 收盘价 |
| `open` | Open Price | 开盘价 |
| `high` | High Price | 最高价 |
| `low` | Low Price | 最低价 |
| `pre_close` | Previous Close Price | 昨收价 |
| `change` | Price Change | 涨跌额 |
| `pct_chg` | Percentage Change | 涨跌幅 |
| `vol` | Volume (lots) | 成交量(手) |
| `amount` | Amount (thousands) | 成交额(千元) |

## 3. Fundamentals Data (财务基础数据)

### income (利润表)
Total Columns: 85

| Column | English | Chinese |
|--------|---------|---------|
| `ts_code` | TS Stock Code | TS代码 |
| `ann_date` | Announcement Date | 公告日期 |
| `f_ann_date` | Actual Announcement Date | 实际公告日期 |
| `end_date` | Report Period End Date | 报告期 |
| `report_type` | Report Type | 报表类型 |
| `comp_type` | Company Type | 公司类型(1一般工商业2银行3保险4证券) |
| `end_type` | End Type | 报告期类型 |
| `basic_eps` | Basic EPS | 基本每股收益 |
| `diluted_eps` | Diluted EPS | 稀释每股收益 |
| `total_revenue` | Total Revenue | 营业总收入 |
| `revenue` | Operating Revenue | 营业收入 |
| `int_income` | Interest Income | 利息收入 |
| `prem_earned` | Premiums Earned | 已赚保费 |
| `comm_income` | Commission Income | 手续费及佣金收入 |
| `n_commis_income` | Net Commission Income | 手续费及佣金净收入 |
| `n_oth_income` | Net Other Income | 其他经营净收益 |
| `n_oth_b_income` | Net Other Business Income | 加:其他业务净收益 |
| `prem_income` | Premium Income | 保费业务收入 |
| `out_prem` | Outward Premiums | 减:分出保费 |
| `une_prem_reser` | Unearned Premium Reserve | 提取未到期责任准备金 |
| `reins_income` | Reinsurance Income | 其中:分保费收入 |
| `n_sec_tb_income` | Net Sec Trading Brokerage Inc | 代理买卖证券业务净收入 |
| `n_sec_uw_income` | Net Sec Underwriting Inc | 证券承销业务净收入 |
| `n_asset_mg_income` | Net Asset Mgmt Income | 受托客户资产管理业务净收入 |
| `oth_b_income` | Other Business Income | 其他业务收入 |
| `fv_value_chg_gain` | Fair Value Change Gain | 加:公允价值变动净收益 |
| `invest_income` | Investment Income | 加:投资净收益 |
| `ass_invest_income` | Associate Investment Income | 其中:对联营企业和合营企业的投资收益 |
| `forex_gain` | Forex Gain | 加:汇兑净收益 |
| `total_cogs` | Total COGS | 营业总成本 |
| `oper_cost` | Operating Cost | 营业成本 |
| `int_exp` | Interest Expense | 利息支出 |
| `comm_exp` | Commission Expense | 手续费及佣金支出 |
| `biz_tax_surchg` | Business Tax Surcharges | 营业税金及附加 |
| `sell_exp` | Selling Expense | 销售费用 |
| `admin_exp` | Admin Expense | 管理费用 |
| `fin_exp` | Financial Expense | 财务费用 |
| `assets_impair_loss` | Assets Impairment Loss | 资产减值损失 |
| `prem_refund` | Premium Refund | 退保金 |
| `compens_payout` | Compensation Payout | 赔付总支出 |
| `reser_insur_liab` | Reserve Insurance Liab | 提取保险责任准备金 |
| `div_payt` | Dividend Payout | 保户红利支出 |
| `reins_exp` | Reinsurance Expense | 分保费用 |
| `oper_exp` | Operating Expense | 营业支出 |
| `compens_payout_refu` | Compensation Payout Refund | 减:摊回赔付支出 |
| `insur_reser_refu` | Insurance Reserve Refund | 减:摊回保险责任准备金 |
| `reins_cost_refund` | Reinsurance Cost Refund | 减:摊回分保费用 |
| `other_bus_cost` | Other Business Cost | 其他业务成本 |
| `operate_profit` | Operating Profit | 营业利润 |
| `non_oper_income` | Non-operating Income | 加:营业外收入 |
| `non_oper_exp` | Non-operating Expense | 减:营业外支出 |
| `nca_disploss` | Non-current Asset Disp Loss | 其中:减:非流动资产处置净损失 |
| `total_profit` | Total Profit | 利润总额 |
| `income_tax` | Income Tax | 所得税费用 |
| `n_income` | Net Income | 净利润(含少数股东损益) |
| `n_income_attr_p` | Net Income Attrib. to Parent | 归属于母公司所有者的净利润 |
| `minority_gain` | Minority Interest Income | 少数股东损益 |
| `oth_compr_income` | Other Comprehensive Income | 其他综合收益 |
| `t_compr_income` | Total Comprehensive Income | 综合收益总额 |
| `compr_inc_attr_p` | Comprehensive Inc Attrib. to Parent | 归属于母公司所有者的综合收益总额 |
| `compr_inc_attr_m_s` | Comprehensive Inc Attrib. to Minority | 归属于少数股东的综合收益总额 |
| `ebit` | EBIT | 息税前利润 |
| `ebitda` | EBITDA | 息税折旧摊销前利润 |
| `insurance_exp` | Insurance Expense | 保险业务支出 |
| `undist_profit` | Undistributed Profit | 年初未分配利润 |
| `distable_profit` | Distributable Profit | 可分配利润 |
| `rd_exp` | R&D Expense | 研发费用 |
| `fin_exp_int_exp` | Financial Expense - Interest Exp | 财务费用:利息费用 |
| `fin_exp_int_inc` | Financial Expense - Interest Inc | 财务费用:利息收入 |
| `transfer_surplus_rese` | Transfer Surplus Reserve | 盈余公积转入 |
| `transfer_housing_imprest` | Transfer Housing Imprest | 住房周转金转入 |
| `transfer_oth` | Transfer Other | 其他转入 |
| `adj_lossgain` | Adjustment Loss/Gain | 调整以前年度损益 |
| `withdra_legal_surplus` | Withdraw Legal Surplus | 提取法定盈余公积 |
| `withdra_legal_pubfund` | Withdraw Legal Public Fund | 提取法定公益金 |
| `withdra_biz_devfund` | Withdraw Biz Dev Fund | 提取企业发展基金 |
| `withdra_rese_fund` | Withdraw Reserve Fund | 提取储备基金 |
| `withdra_oth_ersu` | Withdraw Other Surplus | 提取任意盈余公积金 |
| `workers_welfare` | Workers Welfare | 职工奖金福利 |
| `distr_profit_shrhder` | Distributed Profit to Shrhder | 可供股东分配的利润 |
| `prfshare_payable_dvd` | Pref Share Payable Dividend | 应付优先股股利 |
| `comshare_payable_dvd` | Common Share Payable Dividend | 应付普通股股利 |
| `capit_comstock_div` | Capital Common Stock Dividend | 转作股本的普通股股利 |
| `continued_net_profit` | Continued Net Profit | 持续经营净利润 |
| `update_flag` | Update Flag | 更新标识 |

### balancesheet (资产负债表)
Total Columns: 152

| Column | English | Chinese |
|--------|---------|---------|
| `ts_code` | TS Stock Code | TS代码 |
| `ann_date` | Announcement Date | 公告日期 |
| `f_ann_date` | Actual Announcement Date | 实际公告日期 |
| `end_date` | Report Period End Date | 报告期 |
| `report_type` | Report Type | 报表类型 |
| `comp_type` | Company Type | 公司类型(1一般工商业2银行3保险4证券) |
| `end_type` | End Type | 报告期类型 |
| `total_share` | Total Shares (10k) | 总股本(万股) |
| `cap_rese` | Capital Reserve | 资本公积 |
| `undistr_porfit` | Undistributed Profit | 未分配利润 |
| `surplus_rese` | Surplus Reserve | 盈余公积 |
| `special_rese` | Special Reserve | 专项储备 |
| `money_cap` | Monetary Capital | 货币资金 |
| `trad_asset` | Trading Financial Assets | 交易性金融资产 |
| `notes_receiv` | Notes Receivable | 应收票据 |
| `accounts_receiv` | Accounts Receivable | 应收账款 |
| `oth_receiv` | Other Receivables | 其他应收款 |
| `prepayment` | Prepayments | 预付款项 |
| `div_receiv` | Dividends Receivable | 应收股利 |
| `int_receiv` | Interest Receivable | 应收利息 |
| `inventories` | Inventories | 存货 |
| `amor_exp` | Amortized Expenses | 待摊费用 |
| `nca_within_1y` | Non-current Assets w/i 1 Year | 一年内到期的非流动资产 |
| `sett_rsrv` | Settlement Reserve | 结算备付金 |
| `loanto_oth_bank_fi` | Loans to Other Banks/FI | 拆出资金 |
| `premium_receiv` | Premium Receivable | 应收保费 |
| `reinsur_receiv` | Reinsurance Receivable | 应收分保账款 |
| `reinsur_res_receiv` | Reinsur Reserve Receivable | 应收分保合同准备金 |
| `pur_resale_fa` | Purchased Resale Financial Assets | 买入返售金融资产 |
| `oth_cur_assets` | Other Current Assets | 其他流动资产 |
| `total_cur_assets` | Total Current Assets | 流动资产合计 |
| `fa_avail_for_sale` | AFS Financial Assets | 可供出售金融资产 |
| `htm_invest` | HTM Investments | 持有至到期投资 |
| `lt_eqt_invest` | LT Equity Investments | 长期股权投资 |
| `invest_real_estate` | Investment Real Estate | 投资性房地产 |
| `time_deposits` | Time Deposits | 定期存款 |
| `oth_assets` | Other Assets | 其他资产 |
| `lt_rec` | Long-term Receivables | 长期应收款 |
| `fix_assets` | Fixed Assets | 固定资产 |
| `cip` | Construction in Progress | 在建工程 |
| `const_materials` | Construction Materials | 工程物资 |
| `fixed_assets_disp` | Fixed Assets Disposal | 固定资产清理 |
| `produc_bio_assets` | Productive Bio Assets | 生产性生物资产 |
| `oil_and_gas_assets` | Oil & Gas Assets | 油气资产 |
| `intan_assets` | Intangible Assets | 无形资产 |
| `r_and_d` | R&D Assets | 开发支出 |
| `goodwill` | Goodwill | 商誉 |
| `lt_amor_exp` | LT Amortized Expenses | 长期待摊费用 |
| `defer_tax_assets` | Deferred Tax Assets | 递延所得税资产 |
| `decr_in_disbur` | Decrease in Disbursement | 发放贷款及垫款 |
| `oth_nca` | Other Non-current Assets | 其他非流动资产 |
| `total_nca` | Total Non-current Assets | 非流动资产合计 |
| `cash_reser_cb` | Cash Reserve Central Bank | 存放中央银行款项 |
| `depos_in_oth_bfi` | Deposits in Other Bank/FI | 存放同业和其它金融机构款项 |
| `prec_metals` | Precious Metals | 贵金属 |
| `deriv_assets` | Derivative Assets | 衍生金融资产 |
| `rr_reins_une_prem` | Reinsur Rsv Unearned Prem | 应收分保未到期责任准备金 |
| `rr_reins_outstd_cla` | Reinsur Rsv Outst Claims | 应收分保未决赔款准备金 |
| `rr_reins_lins_liab` | Reinsur Rsv Life Ins Liab | 应收分保寿险责任准备金 |
| `rr_reins_lthins_liab` | Reinsur Rsv LT Health Ins Liab | 应收分保长期健康险责任准备金 |
| `refund_depos` | Refundable Deposits | 存出保证金 |
| `ph_pledge_loans` | Policy House Pledge Loans | 保户质押贷款 |
| `refund_cap_depos` | Refund Capital Deposits | 存出资本保证金 |
| `indep_acct_assets` | Independent Account Assets | 独立账户资产 |
| `client_depos` | Client Deposits | 其中：客户资金存款 |
| `client_prov` | Client Provision | 其中：客户备付金 |
| `transac_seat_fee` | Transaction Seat Fee | 其中:交易席位费 |
| `invest_as_receiv` | Investments as Receiv | 应收款项类投资 |
| `total_assets` | Total Assets | 资产总计 |
| `lt_borr` | Long-term Borrowings | 长期借款 |
| `st_borr` | Short-term Borrowings | 短期借款 |
| `cb_borr` | Central Bank Borrowings | 向中央银行借款 |
| `depos_ib_deposits` | IB Deposits | 吸收存款及同业存放 |
| `loan_oth_bank` | Loans from Other Banks | 拆入资金 |
| `trading_fl` | Trading Financial Liab | 交易性金融负债 |
| `notes_payable` | Notes Payable | 应付票据 |
| `acct_payable` | Accounts Payable | 应付账款 |
| `adv_receipts` | Advance Receipts | 预收款项 |
| `sold_for_repur_fa` | Sold for Repurchase FA | 卖出回购金融资产款 |
| `comm_payable` | Commission Payable | 应付手续费及佣金 |
| `payroll_payable` | Payroll Payable | 应付职工薪酬 |
| `taxes_payable` | Taxes Payable | 应交税费 |
| `int_payable` | Interest Payable | 应付利息 |
| `div_payable` | Dividend Payable | 应付股利 |
| `oth_payable` | Other Payables | 其他应付款 |
| `acc_exp` | Accrued Expenses | 预提费用 |
| `deferred_inc` | Deferred Income | 递延收益 |
| `st_bonds_payable` | Short-term Bonds Payable | 应付短期债券 |
| `payable_to_reinsurer` | Payable to Reinsurer | 应付分保账款 |
| `rsrv_insur_cont` | Reserve Insurance Contracts | 保险合同准备金 |
| `acting_trading_sec` | Acting Trading Sec | 代理买卖证券款 |
| `acting_uw_sec` | Acting Underwriting Sec | 代理承销证券款 |
| `non_cur_liab_due_1y` | Non-current Liab Due 1 Year | 一年内到期的非流动负债 |
| `oth_cur_liab` | Other Current Liab | 其他流动负债 |
| `total_cur_liab` | Total Current Liab | 流动负债合计 |
| `bond_payable` | Bonds Payable | 应付债券 |
| `lt_payable` | Long-term Payables | 长期应付款 |
| `specific_payables` | Specific Payables | 专项应付款 |
| `estimated_liab` | Estimated Liabilities | 预计负债 |
| `defer_tax_liab` | Deferred Tax Liab | 递延所得税负债 |
| `defer_inc_non_cur_liab` | Deferred Income Non-current Liab | 递延收益-非流动负债 |
| `oth_ncl` | Other Non-current Liab | 其他非流动负债 |
| `total_ncl` | Total Non-current Liab | 非流动负债合计 |
| `depos_oth_bfi` | Deposits from Other Bank/FI | 同业和其它金融机构存放款项 |
| `deriv_liab` | Derivative Liabilities | 衍生金融负债 |
| `depos` | Deposits | 吸收存款 |
| `agency_bus_liab` | Agency Business Liab | 代理业务负债 |
| `oth_liab` | Other Liabilities | 其他负债 |
| `prem_receiv_adva` | Premium Received in Advance | 预收保费 |
| `depos_received` | Deposits Received | 存入保证金 |
| `ph_invest` | Policy Holder Investments | 保户储金及投资款 |
| `reser_une_prem` | Reserve Unearned Premium | 未到期责任准备金 |
| `reser_outstd_claims` | Reserve Outstd Claims | 未决赔款准备金 |
| `reser_lins_liab` | Reserve Life Ins Liab | 寿险责任准备金 |
| `reser_lthins_liab` | Reserve LT Health Ins Liab | 长期健康险责任准备金 |
| `indept_acc_liab` | Independent Account Liab | 独立账户负债 |
| `pledge_borr` | Pledge Borrowings | 其中:质押借款 |
| `indem_payable` | Indemnity Payable | 应付赔付款 |
| `policy_div_payable` | Policy Dividend Payable | 应付保单红利 |
| `total_liab` | Total Liabilities | 负债合计 |
| `treasury_share` | Treasury Shares | 减:库存股 |
| `ordin_risk_reser` | Ordinary Risk Reserve | 一般风险准备 |
| `forex_differ` | Forex Difference | 外币报表折算差额 |
| `invest_loss_unconf` | Investment Loss Unconfirmed | 未确认的投资损失 |
| `minority_int` | Minority Interests | 少数股东权益 |
| `total_hldr_eqy_exc_min_int` | Total Hldr Eqy Excl. Minority Int | 归属于母公司所有者权益合计 |
| `total_hldr_eqy_inc_min_int` | Total Hldr Eqy Incl. Minority Int | 所有者权益(或股东权益)合计 |
| `total_liab_hldr_eqy` | Total Liab & Hldr Eqy | 负债和所有者权益(或股东权益)总计 |
| `lt_payroll_payable` | LT Payroll Payable | 长期应付职工薪酬 |
| `oth_comp_income` | Other Comprehensive Income | 其他综合收益 |
| `oth_eqt_tools` | Other Equity Tools | 其他权益工具 |
| `oth_eqt_tools_p_shr` | Other Eqt Tools Pref Share | 其他权益工具:优先股 |
| `lending_funds` | Lending Funds | 融出资金 |
| `acc_receivable` | Accounts Receivable | 应收款项 |
| `st_fin_payable` | ST Financial Payable | 应付短期融资款 |
| `payables` | Payables | 应付款项 |
| `hfs_assets` | Held For Sale Assets | 持有待售的资产 |
| `hfs_sales` | Held For Sale Sales | 持有待售的负债 |
| `cost_fin_assets` | Cost of Financial Assets | 其中：以摊余成本计量的金融资产 |
| `fair_value_fin_assets` | Fair Value Financial Assets | 其中：以公允价值计量的金融资产 |
| `contract_assets` | Contract Assets | 合同资产 |
| `contract_liab` | Contract Liabilities | 合同负债 |
| `accounts_receiv_bill` | Accounts Receivable Bill | 应收票据及应收账款 |
| `accounts_pay` | Accounts Payable | 应付票据及应付账款 |
| `oth_rcv_total` | Other Receivables Total | 其他应收款(合计) |
| `fix_assets_total` | Fixed Assets Total | 固定资产(合计) |
| `cip_total` | Construction in Progress Total | 在建工程(合计) |
| `oth_pay_total` | Other Payables Total | 其他应付款(合计) |
| `long_pay_total` | Long-term Payables Total | 长期应付款(合计) |
| `debt_invest` | Debt Investments | 债权投资 |
| `oth_debt_invest` | Other Debt Investments | 其他债权投资 |
| `update_flag` | Update Flag | 更新标识 |

### indicators (财务指标)
Total Columns: 109

| Column | English | Chinese |
|--------|---------|---------|
| `ts_code` | TS Stock Code | TS代码 |
| `ann_date` | Announcement Date | 公告日期 |
| `end_date` | Report Period End Date | 报告期 |
| `eps` | Earnings Per Share | 基本每股收益 |
| `dt_eps` | Diluted EPS | 稀释每股收益 |
| `total_revenue_ps` | Total Revenue PS | 每股营业总收入 |
| `revenue_ps` | Revenue PS | 每股营业收入 |
| `capital_rese_ps` | Capital Reserve PS | 每股资本公积 |
| `surplus_rese_ps` | Surplus Reserve PS | 每股盈余公积 |
| `undist_profit_ps` | Undistributed Profit PS | 每股未分配利润 |
| `extra_item` | Extraordinary Items | 非经常性损益 |
| `profit_dedt` | Profit Deducting Extra | 扣除非经常性损益后的净利润 |
| `gross_margin` | Gross Margin | 毛利 |
| `current_ratio` | Current Ratio | 流动比率 |
| `quick_ratio` | Quick Ratio | 速动比率 |
| `cash_ratio` | Cash Ratio | 保守速动比率 |
| `ar_turn` | AR Turnover | 应收账款周转率 |
| `ca_turn` | CA Turnover | 流动资产周转率 |
| `fa_turn` | FA Turnover | 固定资产周转率 |
| `assets_turn` | Total Assets Turnover | 总资产周转率 |
| `op_income` | Operating Income | 经营活动净收益 |
| `ebit` | EBIT | 息税前利润 |
| `ebitda` | EBITDA | 息税折旧摊销前利润 |
| `fcff` | FCFF | 企业自由现金流量 |
| `fcfe` | FCFE | 股权自由现金流量 |
| `current_exint` | Current Ex-Int | 无息流动负债 |
| `noncurrent_exint` | Non-current Ex-Int | 无息非流动负债 |
| `interestdebt` | Interest Bearing Debt | 带息债务 |
| `netdebt` | Net Debt | 净债务 |
| `tangible_asset` | Tangible Assets | 有形资产 |
| `working_capital` | Working Capital | 营运资金 |
| `networking_capital` | Net Working Capital | 营运资本 |
| `invest_capital` | Invested Capital | 投入资本 |
| `retained_earnings` | Retained Earnings | 留存收益 |
| `diluted2_eps` | Diluted2 EPS | 期末摊薄每股收益 |
| `bps` | Book Value Per Share | 每股净资产 |
| `ocfps` | Operating CF PS | 每股经营活动产生的现金流量净额 |
| `retainedps` | Retained Earnings PS | 每股留存收益 |
| `cfps` | Cash Flow PS | 每股现金流量净额 |
| `ebit_ps` | EBIT PS | 每股息税前利润 |
| `fcff_ps` | FCFF PS | 每股企业自由现金流量 |
| `fcfe_ps` | FCFE PS | 每股股东自由现金流量 |
| `netprofit_margin` | Net Profit Margin | 销售净利率 |
| `grossprofit_margin` | Gross Profit Margin | 销售毛利率 |
| `cogs_of_sales` | COGS to Sales | 销售成本率 |
| `expense_of_sales` | Expense to Sales | 销售期间费用率 |
| `profit_to_gr` | Profit to Gross Revenue | 净利润/营业总收入 |
| `saleexp_to_gr` | Sell Exp to Gross Revenue | 销售费用/营业总收入 |
| `adminexp_of_gr` | Admin Exp to Gross Revenue | 管理费用/营业总收入 |
| `finaexp_of_gr` | Fin Exp to Gross Revenue | 财务费用/营业总收入 |
| `impai_ttm` | Impairment TTM | 资产减值损失/营业总收入 |
| `gc_of_gr` | Gross Cost of Gross Revenue | 营业总成本/营业总收入 |
| `op_of_gr` | Op Profit of Gross Revenue | 营业利润/营业总收入 |
| `ebit_of_gr` | EBIT to Gross Revenue | 息税前利润/营业总收入 |
| `roe` | ROE | 净资产收益率 |
| `roe_waa` | ROE WAA | 加权平均净资产收益率 |
| `roe_dt` | ROE Deduct | 扣除非经常损益后的净资产收益率 |
| `roa` | ROA | 总资产报酬率 |
| `npta` | Net Profit to Total Assets | 总资产净利润 |
| `roic` | ROIC | 投入资本回报率 |
| `roe_yearly` | ROE Yearly | 年化净资产收益率 |
| `roa2_yearly` | ROA2 Yearly | 年化总资产报酬率 |
| `debt_to_assets` | Debt to Assets Ratio | 资产负债率 |
| `assets_to_eqt` | Assets to Equity | 权益乘数 |
| `dp_assets_to_eqt` | DP Assets to Equity | 权益乘数(杜邦分析) |
| `ca_to_assets` | CA to Assets | 流动资产/总资产 |
| `nca_to_assets` | NCA to Assets | 非流动资产/总资产 |
| `tbassets_to_totalassets` | Tangible Assets to Total Assets | 有形资产/总资产 |
| `int_to_talcap` | Int Bear Debt to Total Cap | 带息债务/全部投入资本 |
| `eqt_to_talcapital` | Eqt to Total Capital | 归属于母公司的股东权益/全部投入资本 |
| `currentdebt_to_debt` | Current Debt to Debt | 流动负债/负债合计 |
| `longdeb_to_debt` | Long Debt to Debt | 非流动负债/负债合计 |
| `ocf_to_shortdebt` | OCF to Short Debt | 经营活动产生的现金流量净额/流动负债 |
| `debt_to_eqt` | Debt to Equity | 产权比率 |
| `eqt_to_debt` | Equity to Debt | 归属于母公司的股东权益/负债合计 |
| `eqt_to_interestdebt` | Equity to Interest Debt | 归属于母公司的股东权益/带息债务 |
| `tangibleasset_to_debt` | Tangible Asset to Debt | 有形资产/负债合计 |
| `tangasset_to_intdebt` | Tangible Asset to Int Debt | 有形资产/带息债务 |
| `tangibleasset_to_netdebt` | Tangible Asset to Net Debt | 有形资产/净债务 |
| `ocf_to_debt` | OCF to Debt | 经营活动产生的现金流量净额/负债合计 |
| `turn_days` | Turnover Days | 营业周期(天) |
| `roa_yearly` | ROA Yearly | 年化总资产净利率 |
| `roa_dp` | ROA DP | 总资产净利率(杜邦分析) |
| `fixed_assets` | Fixed Assets | 固定资产合计 |
| `profit_to_op` | Profit to Op Profit | 利润总额/营业收入 |
| `q_saleexp_to_gr` | Q Sell Exp to Gross Rev | 单季度销售费用/单季度营业总收入 |
| `q_gc_to_gr` | Q Gross Cost to Gross Rev | 单季度营业总成本/单季度营业总收入 |
| `q_roe` | Q ROE | 单季度净资产收益率 |
| `q_dt_roe` | Q ROE Deduct | 单季度扣非净资产收益率 |
| `q_npta` | Q Net Profit to Total Assets | 单季度总资产净利润率 |
| `q_ocf_to_sales` | Q OCF to Sales | 单季度经营活动产生的现金流量净额/单季度营业收入 |
| `basic_eps_yoy` | Basic EPS YoY | 基本每股收益同比增长率(%) |
| `dt_eps_yoy` | Diluted EPS YoY | 稀释每股收益同比增长率(%) |
| `cfps_yoy` | CFPS YoY | 每股经营活动产生的现金流量净额同比增长率(%) |
| `op_yoy` | Op Profit YoY | 营业利润同比增长率(%) |
| `ebt_yoy` | EBT YoY | 利润总额同比增长率(%) |
| `netprofit_yoy` | Net Profit YoY | 归属母公司股东的净利润同比增长率(%) |
| `dt_netprofit_yoy` | Diluted Net Profit YoY | 归属母公司股东的净利润-扣除非经常损益同比增长率(%) |
| `ocf_yoy` | OCF YoY | 经营活动产生的现金流量净额同比增长率(%) |
| `roe_yoy` | ROE YoY | 净资产收益率(摊薄)同比增长率(%) |
| `bps_yoy` | BPS YoY | 每股净资产相对年初增长率(%) |
| `assets_yoy` | Assets YoY | 资产总计相对年初增长率(%) |
| `eqt_yoy` | Equity YoY | 归属母公司的股东权益相对年初增长率(%) |
| `tr_yoy` | Total Revenue YoY | 营业总收入同比增长率(%) |
| `or_yoy` | Op Revenue YoY | 营业收入同比增长率(%) |
| `q_sales_yoy` | Q Sales YoY | 营业收入单季度同比增长率(%) |
| `q_op_qoq` | Q Op Profit QoQ | 营业利润单季度环比增长率(%) |
| `equity_yoy` | Equity YoY | 净资产同比增长率 |
| `update_flag` | Update Flag | 更新标识 |

## 4. Corporate Actions (公司事件)

### dividends (分红送股)
Total Columns: 14

> [!CAUTION]
> The Tushare API documentation labels `cash_div` as "派息(每10股)" and bonus columns as "比例". However, **verified against actual ex-rights price gaps, all values are per-share**. Confirmed across 5+ stocks: `cash_div=0.719` matched a price gap of `-0.720`, and `stk_co_rate=0.4` matched a 40% ex-rights price drop.

| Column | English | Chinese | Verified Unit |
|--------|---------|---------|---------|
| `ts_code` | TS Stock Code | TS代码 | |
| `end_date` | Report Period End Date | 报告期 | |
| `ann_date` | Announcement Date | 公告日期 | |
| `div_proc` | Dividend Process | 实施进度 | |
| `stk_div` | Stock Dividend | 送股比例 | **Per share** |
| `stk_bo_rate` | Bonus Stock Rate | 转增比例 | **Per share** |
| `stk_co_rate` | Stock CO Rate | 配股比例 | **Per share** |
| `cash_div` | Cash Dividend | 派息 | **Per share (¥)** |
| `cash_div_tax` | Cash Dividend Tax | 派息(税后) | **Per share (¥)** |
| `record_date` | Record Date | 股权登记日 | |
| `ex_date` | Ex-Dividend Date | 除权除息日 | |
| `pay_date` | Payment Date | 派息日 | |
| `div_listdate` | Dividend Listing Date | 红股上市日 | |
| `imp_ann_date` | Implementation Announcement Date | 实施公告日 | |

## 5. Universe & Reference (基准与成分股)

### index_weights (指数权重)
Total Columns: 4

| Column | English | Chinese |
|--------|---------|---------|
| `index_code` | Index Code | 指数代码 |
| `con_code` | Constituent Code | 成分股代码 |
| `trade_date` | Trade Date | 交易日期 |
| `weight` | Weight | 权重 |

**Vendor quirk (verified 2026-06-11)**: Tushare `index_weight` returns EMPTY for `000300.SH`
before ~2016; the SZSE mirror code `399300.SZ` serves the SAME index (member sets and weights
verified identical on 2024-01-31) back to 2008-01, with DAILY snapshots pre-2016 (monthly after).
The 2008-01..2015-12 CSI300 hole was backfilled 2026-06-11 via
`scripts/backfill_index_weights.py --index 399300.SZ --relabel-as 000300.SH` (rows stored under
the canonical `000300.SH`). Snapshot cadence is otherwise monthly (doc_id=96) — daily constituent
data does not exist upstream post-2016; consumers as-of carry-forward (see
`src/data_infra/universe_membership.py` for the PIT semantics and the semi-annual-rebalance
staleness note).

### industry_sw2021 (申万行业2021)
Total Columns: 7

| Column | English | Chinese |
|--------|---------|---------|
| `index_code` | Index Code | 指数代码 |
| `industry_name` | Industry Name | 行业名称 |
| `level` | Level | 行业级别 |
| `industry_code` | Industry Code | 行业代码 |
| `is_pub` | Is Published | 是否发布 |
| `parent_code` | Parent Code | 父级代码 |
| `src` | Source | 来源 |

### industry_sw2021_members (申万行业2021历史成员)
Storage: `data/universe/industry_sw2021_members/industry_sw2021_members.parquet`
Total Columns: 11

Time-varying stock-to-industry membership for the SW2021 standard,
fetched from Tushare's `pro.index_member_all` (VIP tier). Combines
`is_new='Y'` (current) and `is_new='N'` (historical) to provide full
history. One row per stock per disjoint membership interval (a stock
can have multiple rows if it was reclassified across industries).
Bootstrap script: `scripts/fetch_sw_industry_members.py`.

| Column | English | Chinese |
|--------|---------|---------|
| `l1_code` | L1 Industry Code (SW2021 primary, e.g. `801780.SI` 银行) | 申万一级行业代码 |
| `l1_name` | L1 Industry Name | 一级行业名称 |
| `l2_code` | L2 Industry Code (SW2021 secondary) | 申万二级行业代码 |
| `l2_name` | L2 Industry Name | 二级行业名称 |
| `l3_code` | L3 Industry Code (SW2021 tertiary) | 申万三级行业代码 |
| `l3_name` | L3 Industry Name | 三级行业名称 |
| `ts_code` | Tushare Stock Code (e.g. `000001.SZ`) | TS代码 |
| `name` | Stock Name | 股票名称 |
| `in_date` | Membership Start (datetime) | 纳入日期 |
| `out_date` | Membership End (datetime; `2099-12-31` sentinel = still active) | 剔除日期 |
| `is_new` | `Y` = current member, `N` = historical | 是否当前成员 |

**Coverage caveat (2026-04-27):** pre-2014 coverage is 94-97% of the
daily trading universe due to Shenwan's own backfill thinness — NOT
survivorship bias. Empirical verification at
`workspace/outputs/sw_industry_coverage_audit_20260427.md`. Stocks
without an SW2021 entry covering the as-of date return `None` from
`provider_metadata.industry_as_of()`; research code treats null industry
as "skip from industry-aware computations" via the existing notna() mask
in `factor_eval.neutralization`. Strict-coverage research should
restrict to dates >= 2014-01-01 (≥96.80% coverage from then onward).

**Lookup helpers:** `provider_metadata.industry_as_of(ts_code, date, level)`
for per-stock lookup; `provider_metadata.build_industry_series_asof(index, level)`
for vectorized MultiIndex alignment (1.25M rows in <1 second).

---

## 7. Phase 3: Factor Research Data Sources

### cashflow (现金流量表)
Storage: `data/fundamentals/cashflow/cashflow_{end_date}.parquet`

| Column | English | Chinese |
|--------|---------|---------|
| `ts_code` | TS Stock Code | TS代码 |
| `ann_date` | Announcement Date | 公告日期 |
| `f_ann_date` | Actual Announcement Date | 实际公告日期 |
| `end_date` | Reporting Period End | 报告期 |
| `comp_type` | Company Type | 公司类型 |
| `report_type` | Report Type | 报表类型 |
| `n_cashflow_act` | Net OCF (Operating Cash Flow) | 经营活动现金流净额 |
| `n_cashflow_inv_act` | Net Investing Cash Flow | 投资活动现金流净额 |
| `n_cash_flows_fnc_act` | Net Financing Cash Flow | 筹资活动现金流净额 |
| `c_pay_acq_const_fiolta` | CapEx (Fixed Assets/Intangibles) | 购建固定资产/无形资产支付的现金 |
| `c_recp_borrow` | Cash Received from Borrowing | 取得借款收到的现金 |
| `c_fr_sale_sg` | Cash from Selling Goods/Services | 销售商品/提供劳务收到的现金 |
| `n_incr_cash_cash_equ` | Net Increase in Cash | 现金及现金等价物净增加额 |

### forecast (业绩预告)
Storage: `data/fundamentals/forecast/forecast_{end_date}.parquet`

| Column | English | Chinese |
|--------|---------|---------|
| `ts_code` | TS Stock Code | TS代码 |
| `ann_date` | Announcement Date | 公告日期 |
| `end_date` | Reporting Period End | 报告期 |
| `type` | Forecast Type | 业绩预告类型 (预增/预减/略增/略减/续盈/亏损/扭亏) |
| `p_change_min` | Min Change % | 预告净利润变动幅度下限(%) |
| `p_change_max` | Max Change % | 预告净利润变动幅度上限(%) |
| `net_profit_min` | Min Net Profit | 预告净利润下限(万元) |
| `net_profit_max` | Max Net Profit | 预告净利润上限(万元) |
| `last_parent_net` | Last Year Net Profit | 上年同期净利润(万元) |
| `summary` | Forecast Summary | 业绩预告摘要 |

### moneyflow (个股资金流向)
Storage: `data/market/moneyflow/YYYY/moneyflow_YYYYMMDD.parquet`

| Column | English | Chinese |
|--------|---------|---------|
| `ts_code` | TS Stock Code | TS代码 |
| `trade_date` | Trade Date | 交易日期 |
| `buy_sm_vol` | Small Buy Volume | 小单买入量(手) |
| `buy_sm_amount` | Small Buy Amount | 小单买入金额(万元) |
| `sell_sm_vol` | Small Sell Volume | 小单卖出量(手) |
| `sell_sm_amount` | Small Sell Amount | 小单卖出金额(万元) |
| `buy_md_vol` | Medium Buy Volume | 中单买入量(手) |
| `buy_md_amount` | Medium Buy Amount | 中单买入金额(万元) |
| `sell_md_vol` | Medium Sell Volume | 中单卖出量(手) |
| `sell_md_amount` | Medium Sell Amount | 中单卖出金额(万元) |
| `buy_lg_vol` | Large Buy Volume | 大单买入量(手) |
| `buy_lg_amount` | Large Buy Amount | 大单买入金额(万元) |
| `sell_lg_vol` | Large Sell Volume | 大单卖出量(手) |
| `sell_lg_amount` | Large Sell Amount | 大单卖出金额(万元) |
| `buy_elg_vol` | Extra-Large Buy Volume | 特大单买入量(手) |
| `buy_elg_amount` | Extra-Large Buy Amount | 特大单买入金额(万元) |
| `sell_elg_vol` | Extra-Large Sell Volume | 特大单卖出量(手) |
| `sell_elg_amount` | Extra-Large Sell Amount | 特大单卖出金额(万元) |
| `net_mf_vol` | Net Capital Flow Volume | 净流入量(手) |
| `net_mf_amount` | Net Capital Flow Amount | 净流入额(万元) |

> **Status (2026-06-04): `approved` for formal research** (`config/field_registry/approvals/2026-06-04_moneyflow_quarantine_to_approved.yaml`). Review notes:
> - **Coverage** is 100% from 2014; **2008 is partial (31.5%)** — factors should start ~2014 or tolerate pre-2014 nulls.
> - The 16 buy/sell component columns (`{buy,sell}_{sm,md,lg,elg}_{vol,amount}`) are a **balanced turnover decomposition** (Σbuy ≈ Σsell), all ≥0 — the reliable basis for factors (e.g. main-force imbalance = `(buy_lg+buy_elg − sell_lg−sell_elg)/turnover`).
> - **⚠ `net_mf_amount` / `net_mf_vol` are OPAQUE vendor nets** — they do NOT reconcile from the component columns (best corr ~0.51/0.55 to the main-force net, 0% exact match). Treat them as Tushare's proprietary net-inflow signal; do not assume they equal any component formula.
> - **PIT:** same-day-realized daily OUTCOME (known only at session close T) → every field MUST be wrapped in `Ref(...,1)` in a factor expression (enforced by the factor-library PIT-safety lint). NOT an execution field.

### hk_hold (沪深港通持股明细)
Storage: `data/market/northbound/YYYY/northbound_YYYYMMDD.parquet`

> [!WARNING]
> The staged 2026-03-30 audit found that recent raw files contain mixed `.HK` rows and other code contamination. The staged PIT backend filters to validated A-share `ts_code`s before Qlib materialization and treats the recent mixed raw state as an integrity issue, not as trusted equity data.

> **Status (2026-06-05): approved.** The raw mixes northbound A-share rows (`exchange=SH/SZ` — the wanted foreign-holding data) with southbound HK rows (`exchange=HK`, 港股通); the staged backend filters to valid A-share `ts_code`s, so the served `$ratio` is **A-share-only** (the `.HK` rows are legitimate southbound, NOT contamination — correcting the earlier note). Served `$ratio` clean + parity-verified **2017–2025**. COVERAGE CAVEAT: the 2026 tail (Jan–Feb) has no SH/SZ northbound rows — likely a genuine northbound-disclosure cutoff (~end-2025); negligible for research. PIT: end-of-day fact → wrap `$ratio` in `Ref(...,1)`.

| Column | English | Chinese |
|--------|---------|---------|
| `code` | Stock Code | 原始代码 |
| `ts_code` | TS Stock Code | TS代码 |
| `trade_date` | Trade Date | 交易日期 |
| `name` | Stock Name | 股票名称 |
| `vol` | Holding Volume (shares) → provider `$north_hold_vol` | 持股数量(股) |
| `ratio` | Holding % of **Issued** Shares (doc 188; NOT free-float) → provider `$ratio` | 持股占比(%，占已发行股份) |
| `exchange` | Exchange (SH/SZ) | 交易所 |

> **Provider fields (2026-06-20):** `$ratio` (issued-share %, approved 2026-06-05) + `$north_hold_vol` (holding shares, approved 2026-06-20 — raw `vol` renamed via `NORTHBOUND_RENAMES` to avoid the kline `$vol` collision; bin already materialized, registry flip only). ⚠ `$ratio` is **% of ISSUED shares** per Tushare doc 188 (the earlier "Free Float" label was wrong) — close to but not exact to CICC chart-76's `持仓量/流通股本` wording. Daily northbound disclosure **stopped 2024-08-20** (doc 188: switched to quarterly) → daily series effectively 2017..2024-08; PIT: end-of-day fact → `Ref(...,1)`.

### margin_detail (融资融券交易明细)
Storage: `data/market/margin/YYYY/margin_YYYYMMDD.parquet`

> **Status (2026-06-04): PARTIAL approved.** The 5 balance/buy fields (`$rzye` 融资余额, `$rqye` 融券余额, `$rzmre`, `$rzrqye`, `$rqmcl`) are approved (coverage 99.8-100% from 2010, 0 negatives). The 2 repayment fields (`$rzche`, `$rqchl`) are **HELD at quarantine** (`margin_detail_repayment` entry) — 28,127/799 negative rows in 2024, all `.BJ` (BSE) names. `rqyl` (融券余量) is in the raw but unregistered. PIT: exchange publishes day-T balances after close → predictive factors need `Ref(...,1)`.

| Column | English | Chinese |
|--------|---------|---------|
| `ts_code` | TS Stock Code | TS代码 |
| `trade_date` | Trade Date | 交易日期 |
| `rzye` | Margin Balance | 融资余额(元) |
| `rqye` | Short-Selling Balance | 融券余额(元) |
| `rzmre` | Margin Buy Amount | 融资买入额(元) |
| `rqyl` | Short-Sell Volume | 融券余量(股) |
| `rqmcl` | Short-Sell Sell Volume | 融券卖出量(股) |
| `rzche` | Margin Repay Amount | 融资偿还额(元) |
| `rqchl` | Short-Cover Volume | 融券偿还量(股) |

### stk_holdernumber (股东人数)
Storage: `data/corporate/holder_number/holder_number_{year}.parquet`

> [!NOTE]
> Observed raw schema on 2026-03-30 contains `ts_code`, `ann_date`, `end_date`, `holder_num`. The previously documented `holder_num_change` field is not present in the downloaded Parquet files and is not assumed by the staged PIT backend.

| Column | English | Chinese |
|--------|---------|---------|
| `ts_code` | TS Stock Code | TS代码 |
| `ann_date` | Announcement Date | 公告日期 |
| `end_date` | Reporting Period End | 截止日期 |
| `holder_num` | Number of Shareholders | 股东户数 |

### stk_limit (每日涨跌停价格)
Storage: `data/market/stk_limit/YYYY/stk_limit_YYYYMMDD.parquet`

> [!NOTE]
> Observed raw schema on 2026-03-30 contains `trade_date`, `ts_code`, `up_limit`, `down_limit`. The staged PIT backend does not assume a `pre_close` column unless it is actually present in the raw Parquet.
>
> **Consumer (2026-06-02)**: materialized as the bare-name Qlib day bins `$up_limit` / `$down_limit`; the `EventDrivenBacktester` uses them as the **primary** limit-up/limit-down source via `Exchange.resolve_limit_prices()` (computed-band fallback for coverage holes). Promoted in the field registry `quarantine → approved` — see `config/field_registry/approvals/2026-06-02_stk_limit_quarantine_to_approved.yaml`.

| Column | English | Chinese |
|--------|---------|---------|
| `ts_code` | TS Stock Code | TS代码 |
| `trade_date` | Trade Date | 交易日期 |
| `up_limit` | Upper Limit Price | 涨停价 |
| `down_limit` | Lower Limit Price | 跌停价 |

### top_list (龙虎榜每日明细)
Storage: `data/market/top_list/YYYY/top_list_YYYYMMDD.parquet`

> **Status (2026-06-04): approved** (sparse event, 龙虎榜). Materialized as `$top_list__<col>` day bins. PIT: published after close T → wrap in `Ref(...,1)` + apply explicit staleness/decay handling (the signal exists only on event days). Text columns (`name`, `reason`) are NOT materialized.

Qlib provider names: event-like payload columns are exposed as
`$top_list__{column}` to avoid collisions with canonical market fields such as
`$close` and `$amount`.

| Column | English | Chinese |
|--------|---------|---------|
| `ts_code` | TS Stock Code | TS代码 |
| `trade_date` | Trade Date | 交易日期 |
| `close` | Event Close Price | 龙虎榜相关收盘价 |
| `pct_change` | Percent Change | 涨跌幅 |
| `turnover_rate` | Turnover Rate | 换手率 |
| `amount` | Total Trading Amount | 成交额 |
| `l_sell` | Large Sell Amount | 龙虎榜卖出额 |
| `l_buy` | Large Buy Amount | 龙虎榜买入额 |
| `l_amount` | Large Total Amount | 龙虎榜成交额 |
| `net_amount` | Net Buy Amount | 净买入额 |
| `net_rate` | Net Buy Rate | 净买入占比 |
| `amount_rate` | Amount Rate | 成交额占比 |
| `float_values` | Float Market Value | 流通市值 |
| `reason` | List Reason | 上榜原因 |

### top_inst (龙虎榜机构明细)
Storage: `data/market/top_inst/YYYY/top_inst_YYYYMMDD.parquet`

> **Status (2026-06-04): approved** (sparse event, 机构席位). `$top_inst__<col>`. CAVEAT: values are large-scale (institutional seat amounts) → normalize (e.g. `net_buy/turnover`), don't use raw levels. PIT: `Ref(...,1)` + staleness handling. Text columns (`exalter`, `side`, `reason`) not materialized.

Qlib provider names: `$top_inst__buy`, `$top_inst__sell`,
`$top_inst__net_buy`, `$top_inst__buy_rate`, `$top_inst__sell_rate`.

| Column | English | Chinese |
|--------|---------|---------|
| `ts_code` | TS Stock Code | TS代码 |
| `trade_date` | Trade Date | 交易日期 |
| `buy` | Institution Buy Amount | 机构买入额 |
| `buy_rate` | Institution Buy Rate | 机构买入占比 |
| `sell` | Institution Sell Amount | 机构卖出额 |
| `sell_rate` | Institution Sell Rate | 机构卖出占比 |
| `net_buy` | Institution Net Buy Amount | 机构净买入额 |

### block_trade (大宗交易)
Storage: `data/market/block_trade/YYYY/block_trade_YYYYMMDD.parquet`

> **Status (2026-06-04): approved** (sparse event, 大宗交易, 2008+). `$block_trade__<col>`. Value sanity clean (0 negative amounts). PIT: reported day T → `Ref(...,1)` + staleness handling. Text columns (`buyer`, `seller`) not materialized.

Qlib provider names: `$block_trade__price`, `$block_trade__vol`,
`$block_trade__amount`. This endpoint is sparse by design.

| Column | English | Chinese |
|--------|---------|---------|
| `ts_code` | TS Stock Code | TS代码 |
| `trade_date` | Trade Date | 交易日期 |
| `price` | Block Trade Price | 大宗交易成交价 |
| `vol` | Block Trade Volume | 大宗交易成交量 |
| `amount` | Block Trade Amount | 大宗交易成交额 |
| `buyer` | Buyer Seat | 买方营业部 |
| `seller` | Seller Seat | 卖方营业部 |

### cyq_perf (筹码分布)
Storage: `data/market/cyq_perf/YYYY/cyq_perf_YYYYMMDD.parquet`

> **Status (2026-06-04): approved** (daily-dense, 筹码分布, 2018+). `$cyq_perf__<col>`. Cost percentiles are monotonic-ordered (cost_5≤15≤50≤85≤95); `winner_rate` in [0,100] (max 100.41 = negligible rounding). PIT: computed for day T → `Ref(...,1)`.

Qlib provider names: dense daily payloads are exposed as
`$cyq_perf__{column}`.

| Column | English | Chinese |
|--------|---------|---------|
| `ts_code` | TS Stock Code | TS代码 |
| `trade_date` | Trade Date | 交易日期 |
| `his_low` | Historical Low Cost | 历史低位成本 |
| `his_high` | Historical High Cost | 历史高位成本 |
| `cost_5pct` | 5th Percentile Cost | 5%成本分位 |
| `cost_15pct` | 15th Percentile Cost | 15%成本分位 |
| `cost_50pct` | 50th Percentile Cost | 50%成本分位 |
| `cost_85pct` | 85th Percentile Cost | 85%成本分位 |
| `cost_95pct` | 95th Percentile Cost | 95%成本分位 |
| `weight_avg` | Weighted Average Cost | 加权平均成本 |
| `winner_rate` | Winner Rate | 获利比例 |

### stk_holdertrade (股东增减持)
Storage: `data/corporate/stk_holdertrade/stk_holdertrade_{year}.parquet`

> **Status (2026-06-04): approved** (股东增减持). Aggregated to `$holdertrade_net_vol`/`_gross_vol`/`_net_ratio`/`_events`. **PROPERLY PIT-anchored** — the ledger carries `ann_date` + `disclosure_date` + `effective_date` (effective_date is the visibility anchor), unlike the daily endpoints. Sparse holder events → apply staleness/decay handling.

Per-holder raw rows remain in the PIT ledger. The Qlib provider exposes
per-day aggregates as `$holdertrade_net_vol`, `$holdertrade_gross_vol`,
`$holdertrade_net_ratio`, and `$holdertrade_events`.

> **高管 directional signals (added 2026-06-24, build `phase1_qfields_holdertrade_20260623`):**
> `_materialize_stk_holdertrade` also emits per-day **高管 (holder_type=G, 董监高) DIRECTIONAL**
> aggregates: `$holdertrade_mgr_in_{vol,amount,events,ratio}` (增持/IN) and
> `$holdertrade_mgr_de_{vol,amount,events,ratio}` (减持/DE). `vol` = Σ|change_vol| (shares),
> `ratio` = Σ change_ratio (占流通 %), `events` = transaction count — all COMPLETE for the event rows.
> **`amount` = Σ(|change_vol|·avg_price) over PRICED events only (元)**: `avg_price` is ~71% covered, so
> if some events on a day lack `avg_price` the amount is a **lower-bound priced-event sum** (vol/ratio/events
> stay complete); if ALL same-day directional events lack `avg_price`, amount is served as **NaN, not 0.0**
> (`min_count=1`). Each field is non-NaN ONLY on a day carrying that direction's 高管 event (sparse), so the
> 果仁-style rolling signal **`高管过去N日增持股数 = Sum($holdertrade_mgr_in_vol, N)`** (NaN-skipping window
> sum) is exact. Predictive use → `Ref(...,1)`. 大股东(C)/个人(P) splits are NOT materialized — read the
> ledger for those.

| Column | English | Chinese |
|--------|---------|---------|
| `ts_code` | TS Stock Code | TS代码 |
| `ann_date` | Announcement Date | 公告日期 |
| `holder_name` | Holder Name | 股东名称 |
| `holder_type` | Holder Type (G高管 / P个人 / C公司) | 股东类型 |
| `in_de` | Increase / Decrease Direction (IN/DE) | 增持/减持 |
| `change_vol` | Changed Shares | 变动股数 |
| `change_ratio` | Changed Share Ratio (% of float) | 占流通比例(%) |
| `after_share` | Shares After Change | 变动后持股 |
| `after_ratio` | Holding Ratio After Change | 变动后占流通比例(%) |
| `avg_price` | Average Transaction Price | 平均价格 |
| `total_share` | Total Holding Shares | 持股总数 |

### broker_recommend (券商月度金股)
Storage: `data/analyst/broker_recommend/broker_recommend_{YYYYMM}.parquet` (one file per month).
Endpoint `broker_recommend` (doc_id=267), 6000积分, queried per-month. Ingested by
[scripts/fetch_broker_recommend_historical.py](../scripts/fetch_broker_recommend_historical.py).

> **Status (2026-06-28): RAW, validation-stage.** NOT normalized, NOT in the PIT ledger, NOT in the
> Qlib provider, NOT in `field_status.yaml`. Being validated as the Option-A "券商金股 mother signal"
> ([workspace/research/broker_recommend_alpha/](../workspace/research/broker_recommend_alpha/)). Formal
> materialization (as an **as-of monthly membership table**, NOT a daily bin / statement ledger) is gated
> on the validation result + GPT cross-review.

> **PIT (CRITICAL — no per-row disclosure date):** the ONLY date is `month` (YYYYMM) = the
> **recommendation** month, NOT a visible-at timestamp. Tushare populates month M within its first
> **1–3 days** ("一般1日~3日内更新当月数据"), so a month-M list must be anchored to the first trading day
> **on/after ~day 4 of month M** — never month start (that would be lookahead). No `ann_date`/`f_ann_date`,
> no restatement.

> **Coverage / quality:** history effectively **starts 2020-07** (earlier months return empty). 72 months
> (2020-07..2026-06), 16,706 rows, 2,236 distinct stocks, 80 distinct brokers. **Broker coverage is
> unstable month-to-month (10–44 brokers, 78–335 stocks; median 22 brokers)** → conviction is comparable
> only **cross-sectionally within a month**, never across months. **Conviction is sparse**: mean 1.30
> brokers/stock-month, **81% of picks are single-broker**, max 13 → the signal is closer to *membership*
> than graded conviction. `ts_code` is **Tushare format** (`000001.SZ`) → `.`→`_` before any Qlib join.

| Column | English | Chinese |
|--------|---------|---------|
| `month` | Recommendation Month (YYYYMM) | 推荐月度 |
| `broker` | Broker Name | 券商名称 |
| `ts_code` | TS Stock Code | TS股票代码 |
| `name` | Stock Short Name | 股票简称 |

## 8. Bucket A — 15000积分 Expansion (downloaded 2026-06-08, RAW)

Eight deep-history endpoints from the Tushare 5000→15000积分 upgrade, fetched by
[scripts/fetch_bucket_a.py](../scripts/fetch_bucket_a.py). MOST remain RAW only — not yet normalized /
PIT-aligned / in the Qlib provider. **EXCEPTION: `report_rc`** is fully PIT-ledger + Qlib-provider
materialized (create_time/+2-open-day `effective_date` anchor) — 4 approved `$report_rc__eps_*` primitives
+ 5 quarantined consensus/rating aggregates `$report_rc__{np_fy1,op_rt_fy1,n_active_orgs,rating_up,rating_dn}`
(see §report_rc below). Coverage table + PIT notes: [data_tracker.md](data_tracker.md) §11.

### report_rc (卖方盈利预测明细 — analyst forecasts)
Total Columns: 21. `data/analyst/report_rc/report_rc_{YYYY}.parquet`. Each row = one analyst's forecast
for one stock × one forecast `quarter`. **PIT visibility anchor (resolved 2026-06-08)** = ledger
`effective_date` = a CONTEMPORANEOUS `create_time` (gap ≤ 45 cal days → `max(report_date, create_time)`)
else `report_date + 2 open days` (validated market-wide vs the JoinQuant 朝阳永续 oracle; breadth canary
ran 2026-06-14). **Materialized** into the PIT ledger + Qlib provider: the 4 `$report_rc__eps_*` event-flow
primitives (approved) + the 5 consensus/rating aggregates `$report_rc__{np_fy1, op_rt_fy1, n_active_orgs,
rating_up, rating_dn}` (quarantine until the bound output canary passes). Predictive use MUST `Ref(...,1)`.
Sparse fields (expected NaN): `tp`, `op_pr`, `rd`, `max_price`, `min_price`.

| Column | English | Chinese |
|--------|---------|---------|
| `ts_code` | TS Stock Code | TS代码 |
| `name` | Stock Name | 股票名称 |
| `report_date` | Report Publish Date (visibility anchor) | 研报发布日期 |
| `report_title` | Report Title | 报告标题 |
| `report_type` | Report Type | 报告类型 |
| `classify` | Report Classification | 报告分类 |
| `org_name` | Institution (broker) Name | 机构名称 |
| `author_name` | Analyst Author(s) | 研究员 |
| `quarter` | Forecast Period (e.g. 2026Q4) | 预测年度/季度 |
| `op_rt` | Forecast Operating Revenue | 预测营业收入(万元) |
| `op_pr` | Forecast Operating Profit | 预测营业利润(万元) |
| `tp` | Target Price | 目标价 |
| `np` | Forecast Net Profit | 预测净利润(万元) |
| `eps` | Forecast EPS | 预测每股收益 |
| `pe` | Forecast P/E | 预测市盈率 |
| `rd` | Forecast R&D Expense | 预测研发支出 |
| `roe` | Forecast ROE | 预测净资产收益率 |
| `ev_ebitda` | Forecast EV/EBITDA | 预测EV/EBITDA |
| `rating` | Analyst Rating (买入/增持/Buy/Overweight…) | 卖方评级 |
| `max_price` | Target Price High | 目标价上限 |
| `min_price` | Target Price Low | 目标价下限 |

### express (业绩快报 — preliminary earnings, via express_vip)
Total Columns: 17. `data/fundamentals/express/express_{period}.parquet`. Anchor: `ann_date`.

| Column | English | Chinese |
|--------|---------|---------|
| `ts_code` | TS Stock Code | TS代码 |
| `ann_date` | Announcement Date | 公告日期 |
| `end_date` | Report Period End | 报告期 |
| `revenue` | Operating Revenue | 营业收入 |
| `operate_profit` | Operating Profit | 营业利润 |
| `total_profit` | Total Profit | 利润总额 |
| `n_income` | Net Income | 净利润 |
| `total_assets` | Total Assets | 总资产 |
| `total_hldr_eqy_exc_min_int` | Shareholders' Equity (excl. minority) | 股东权益(不含少数股东) |
| `diluted_eps` | Diluted EPS | 摊薄每股收益 |
| `diluted_roe` | Diluted ROE | 摊薄净资产收益率 |
| `yoy_net_profit` | YoY Net Profit | 去年同期净利润 / 同比 |
| `bps` | Book Value per Share | 每股净资产 |
| `open_net_assets` | Opening Net Assets | 期初净资产 |
| `open_bps` | Opening BPS | 期初每股净资产 |
| `perf_summary` | Performance Summary (text) | 业绩简要说明 |
| `update_flag` | Update Flag | 更新标识 |

### disclosure_date (财报披露计划日期)
Total Columns: 5. `data/fundamentals/disclosure_date/disclosure_date_{period}.parquet`.

| Column | English | Chinese |
|--------|---------|---------|
| `ts_code` | TS Stock Code | TS代码 |
| `ann_date` | Latest Announcement Date | 最新公告日期 |
| `end_date` | Report Period End | 报告期 |
| `pre_date` | Planned Disclosure Date | 预计披露日期 |
| `actual_date` | Actual Disclosure Date | 实际披露日期 |

### fina_mainbz (主营业务构成 — segment revenue, via fina_mainbz_vip)
Total Columns: 8. `data/fundamentals/fina_mainbz/fina_mainbz_{period}.parquet`. Multiple segment rows
per stock×period. Anchor: owning report's disclosure (`ann_date` joined from the statement).

| Column | English | Chinese |
|--------|---------|---------|
| `ts_code` | TS Stock Code | TS代码 |
| `end_date` | Report Period End | 报告期 |
| `bz_item` | Business Segment Item | 主营业务来源(项目) |
| `bz_code` | Segment Code | 项目代码 |
| `bz_sales` | Segment Revenue | 主营业务收入 |
| `bz_profit` | Segment Profit | 主营业务利润 |
| `bz_cost` | Segment Cost | 主营业务成本 |
| `curr_type` | Currency | 货币代码 |

### repurchase (股票回购)
Total Columns: 9. `data/corporate/repurchase/repurchase_{YYYY}.parquet`. Anchor: `ann_date`. `exp_date`
sparse (~97% NaN).

| Column | English | Chinese |
|--------|---------|---------|
| `ts_code` | TS Stock Code | TS代码 |
| `ann_date` | Announcement Date | 公告日期 |
| `end_date` | Period End | 截止日期 |
| `proc` | Process Status | 进度(预案/实施/完成…) |
| `exp_date` | Expiry Date | 过期日期 |
| `vol` | Repurchase Volume | 回购数量 |
| `amount` | Repurchase Amount | 回购金额 |
| `high_limit` | Price Cap | 回购最高价 |
| `low_limit` | Price Floor | 回购最低价 |

### pledge_stat (股权质押统计)
Total Columns: 7. `data/corporate/pledge_stat/pledge_stat_{YYYY}.parquet`. ⚠ Only `end_date` (weekly
exchange statistic date, NOT a disclosure date) → visibility semantics need a check before formal use.

| Column | English | Chinese |
|--------|---------|---------|
| `ts_code` | TS Stock Code | TS代码 |
| `end_date` | Statistic Date (weekly) | 截止日期(周) |
| `pledge_count` | Number of Pledges | 质押次数 |
| `unrest_pledge` | Unrestricted Pledged Shares | 无限售股质押数量 |
| `rest_pledge` | Restricted Pledged Shares | 限售股质押数量 |
| `total_share` | Total Shares | 总股本 |
| `pledge_ratio` | Pledge Ratio | 质押比例 |

### top10_floatholders (前十大流通股东)
Total Columns: 9. `data/corporate/top10_floatholders/top10_floatholders_{period}.parquet`. Anchor:
`ann_date`. Up to 10 holder rows per stock×period.

| Column | English | Chinese |
|--------|---------|---------|
| `ts_code` | TS Stock Code | TS代码 |
| `ann_date` | Announcement Date | 公告日期 |
| `end_date` | Report Period End | 报告期 |
| `holder_name` | Holder Name | 股东名称 |
| `hold_amount` | Shares Held | 持股数量 |
| `hold_ratio` | Holding Ratio (total) | 占总股本比例 |
| `hold_float_ratio` | Holding Ratio (float) | 占流通股本比例 |
| `hold_change` | Change in Holding | 持股变动 |
| `holder_type` | Holder Type | 股东类型 |

### fina_audit (财务审计意见)
Total Columns: 7. `data/fundamentals/fina_audit/fina_audit.parquet` (single consolidated file).
Anchor: `ann_date`. Annual only.

| Column | English | Chinese |
|--------|---------|---------|
| `ts_code` | TS Stock Code | TS代码 |
| `ann_date` | Announcement Date | 公告日期 |
| `end_date` | Report Period End | 报告期 |
| `audit_result` | Audit Opinion (标准无保留意见…) | 审计结果 |
| `audit_fees` | Audit Fees | 审计总费用(元) |
| `audit_agency` | Audit Firm | 会计事务所 |
| `audit_sign` | Signing Auditors | 签字会计师 |

---

## Text sources (大模型语料专题, doc 142 family) — Phase-2A, C1-stamped

> **Storage & PIT (ALL four):** ingested ONLY through `src/data_infra/text_store.py`
> (`data/text_store/{source}/text_{source}.parquet`, append-only, hash-versioned).
> Every row gets `decision_visible_at = max(source_published_at, first_ingested_at)`
> (CONTRACTS C1); nominal dates are NEVER visibility. Historical backfills are
> fixture-only (visible from ingestion) — the clean panel accumulates FORWARD.
> Access permission: 单独权限 (unlocked 1-year, 2026-06-30), not 积分-based.

### research_report (券商研究报告, doc_id=415)
Endpoint `research_report`; history from 2017-01-01; **增量每天两次更新**; 1000 rows/call
(loop by date). Fields: `trade_date`(研报发布时间) `abstr`(摘要) `title` `report_type`
(个股研报/行业研报) `author` `name` `ts_code` `inst_csname`(机构) `ind_name`(行业) `url`(PDF).
**⚠ PIT: `trade_date` is a NOMINAL date (no timestamp) with twice-daily vendor updates —
the report_rc-class backfill trap. `published_col=None` → visible = first ingestion.**
Content = abstract only (PDF not parsed in v1). Trust tier: 中 (sell-side).

### irm_qa_sh (上证e互动, doc_id=366)
Endpoint `irm_qa_sh`; history from 2023-06; 3000 rows/call. Fields: `ts_code` `name`
`trade_date` `q`(问题) `a`(回复) `pub_time`(回复时间, datetime). **PIT anchor = `pub_time`**
(real timestamp, `published_col="pub_time"`). Full text. Trust tier: 强 (exchange platform).

### irm_qa_sz (深证互动易, doc_id=367)
Endpoint `irm_qa_sz`; history from 2010-10; 3000 rows/call. Fields: `ts_code` `name`
`trade_date`(发布时间) `q` `a` `pub_time`(答复时间) `industry`(涉及行业). **PIT anchor =
`pub_time`.** Full text + industry. Trust tier: 强.

### anns_d (上市公司全量公告, doc_id=176)
Endpoint `anns_d`; 2000 rows/call (loop by `ann_date`). Fields: `ann_date` `ts_code` `name`
`title` `url`(PDF 下载链接) `rec_time`(发布时间, datetime, **NON-default → must request via
`fields=`**). **PIT anchor = `rec_time`** for the title record; any future PDF-derived text
needs its OWN `pdf_visible_at` (C1/R5-B1). Title+URL only in v1. Trust tier: 强 (official).

### news (新闻快讯/短讯, doc_id=143) — NF wave (design v1.12 APPROVED 2026-07-12)
Endpoint `news`; 6+ years history; **单次最大 1500 行,按时间窗循环**(NF fetcher: per-source
watermark + recursive window split on the 1500 cap). Doc-143 verified 2026-07-11. Inputs
`start_date`/`end_date`(datetime `'2018-11-20 09:00:00'`, **both required**), `src`(**required
input, NOT an output column** → the fetcher injects `src` as its own stamped column, doc-m2).
Sources (whitelist): `sina`/`wallstreetcn`/`10jqka`/`eastmoney`(live-probed 2026-07-11);
`cls`(财联社) DISABLED pending sub-permission (probe returned 0 rows). Output columns:
`datetime`(发布时间) `content` `title` `channels`(分类栏, **default N → MUST request via
`fields='datetime,content,title,channels'`**, doc-143 check). **PIT anchor = `datetime`**
(publication time; `published_col="datetime"`). ⚠ **No ★ create_time/update_flag field** →
Tushare history backfill is undetectable from any column → the design's `history_bulk` physical
separation (forward flow uses only genuinely-timestamped members, effective_at≤cutoff) is the
required defense. Access: 单独权限 (endpoint-gated). Trust tier: T1 `cls`/`wallstreetcn`,
T2 `sina`/`eastmoney`/`10jqka` (needs measured reliability evidence per design m2). Ingested
through `text_store.py` (source=`news`); all NF noise-removal / clustering / routing / typing
happens downstream in `news_ingest.py`, never in the raw store.
