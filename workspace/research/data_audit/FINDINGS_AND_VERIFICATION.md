# 本地数据 ↔ Tushare 接口 字段一致性审计 — 结论与待验证清单

**日期**: 2026-06-08  **方法**: 对 35 个本地 raw 数据集，把存储的 Parquet 列（跨文件采样并集，抗 schema 漂移）与官方 Tushare 输出参数表（含 `默认显示` Y/N，来自离线语料 `Tushare数据接口/`）做确定性逐字段集合比对。明细见 [FIELD_PARITY_AUDIT.md](FIELD_PARITY_AUDIT.md) / `field_parity_audit.json`；脚本 [audit_field_parity_vs_tushare.py](../../scripts/audit_field_parity_vs_tushare.py)。

> 本轮是 **schema-层（字段存在性 + 默认显示）** 的穷尽比对。**值层语义/单位/覆盖/类型** 不在本轮，列入下方"待验证"。

## 头条结论（先看这条）

- ✅ **PIT 日期锚字段零缺失**：所有应有 `ann_date`/`f_ann_date`/`report_date`/`create_time`/`trade_date`/`end_date`/`imp_ann_date`/`in_date`/`out_date` 的数据集，本地全部具备（`anchor_gap=—` 全数据集）。这是 PIT 正确性最关键的一项，结果干净。
- ✅ **生产主数据集字段完整**：daily/index/moneyflow/hk_hold/top_list/top_inst/block_trade/cyq_perf/cashflow/holder_number/pledge_stat/repurchase/top10_floatholders/index_weights/industry_* 等 **默认字段零缺失、零异常**。
- ⚠️ **唯一真·默认字段缺失** 在 `stock_basic`（2 个）；两个 "quarterly" 标记是**有意的派生子集**，非缺陷。
- ⚠️ **系统性模式**：多数 fetcher **不传 `fields=`** → 只取 Tushare **默认显示=Y** 列，故所有 `默认显示=N` 字段被静默丢弃。多数无害，但 `fina_indicator` 因此漏掉 58 个。

---

## A. 需修复 / 优先验证（真实获取-标准不一致）

### A1. `stock_basic` 漏 2 个默认字段 — **确认为真**
- **缺**: `act_name`(实控人名称), `act_ent_type`(实控人企业性质) — 官方 `默认显示=Y`。
- **根因**: `TushareFetcher.fetch_stock_basic()` 硬编码 15 字段白名单，未含这 2 个（[fetchers/__init__.py:179](../../../src/data_infra/fetchers/__init__.py)）。
- **影响**: 低（实控人字段当前无因子使用），但属"获取方式偏离接口标准"。
- **✅ 已修复 (2026-06-08)**: `fetch_stock_basic` fields 串补入 `act_name,act_ent_type`；重抓 stock_basic（[refetch_stock_basic.py](../../scripts/refetch_stock_basic.py)，旧文件备份）→ 15→17 列，act_name 99.8% / act_ent_type 98.9% 非空。审计复跑 missY 2→0。

### A2. `fina_indicator` 漏 58 个非默认指标 — **需逐项裁决**
- **现状**: 官方 167 字段，本地 109；`refresh_indicator_history.py` 走 `fina_indicator_vip` **未传 `fields=`** → 仅默认列。
- **缺失中的高价值项**: `rd_exp`,`roe_avg`,`inv_turn`,`invturn_days`,`arturn_days`,`total_fa_trun`,`ebit_to_interest`,`ebitda_to_debt`,`ocf_to_or`,`ocf_to_profit`,`ocf_to_interestdebt`,`tax_to_ebt`,`q_eps`,`q_roe`(经 q_* 系列),`q_gr_yoy`,`q_netprofit_yoy`,`q_op_yoy`,`q_profit_to_gr` 等。
- **裁决要点**:
  - 多数 `q_*`（单季同比/环比/利润率）项目**有意不取**——我们自有 PIT 正确的 `pit_*` provider 字段 + `derive_single_quarter_value`，不信任 Tushare 单季计算。→ **维持不取，但记录在案**。
  - `rd_exp` 已由 income 家族的 `$rd_exp_sq_q0` 覆盖（指标版冗余）。
  - **可能想要的 level 指标**: `roe_avg`,`inv_turn`/`invturn_days`,`arturn_days`,`total_fa_trun`,`ebit_to_interest`,`ocf_to_or`。
- **✅ 已修复 (2026-06-08，按用户指示取全量)**: 在 [indicator_history_refresh.py](../../../src/data_infra/pipeline/indicator_history_refresh.py) 加 `FINA_INDICATOR_ALL_FIELDS`（167 字段常量），`fetch_period` 显式传 `fields=`；重跑 staged 历史 refresh（97 期 / 550,537 行，旧数据归档 `_archive/indicators_pre_20260608_230015`）→ 实测 VIP 端点接受全部 167 字段，**union 109→167 列，58 个缺失指标全部回填**（rd_exp 90% / roe_avg 96% / q_eps / q_roe / ebit_to_interest 等）。审计复跑 missN 58→0。
  - ⚠️ **仅入 raw 层**：58 个新字段尚未进 PIT ledger / Qlib provider / 字段注册表——研究/正式路径要用，需 **ledger 重建 → provider 重建 → field_status.yaml 治理** 逐个上线（独立 gated 步骤）。

### A3. `income_quarterly` 的 `ebit` / `ebitda` 列 **100% 全空** — **确认为真（静默坑）**
- **现象**: income_quarterly 把 ebit/ebitda 收进 23 列子集，但**全 72 文件 0/459890 非空（100% NULL）**；累计 income 则 ebit 91.2% / ebitda 50.5% 有值（实测）。
- **根因**: Tushare `income_vip` 的 report_type=2/3（直接单季）行不填 ebit/ebitda。本地保留了空列 → 任何读单季 ebit/ebitda 的因子会**静默拿到 NaN**，比"字段缺失"更隐蔽。
- **✅ 已修复 (2026-06-08)**: 确认无因子读 income_quarterly.ebit/ebitda（catalog 仅注释提及 ebitda，且应取自累计 income）。**源头**：两个单季 fetcher（income/cashflow quarterly）改为 `dropna(how="all", axis=1)`，结构性全空列不再入库。**存量**：[clean_income_quarterly_nulls.py](../../scripts/clean_income_quarterly_nulls.py) 删除全 72 文件的全局全空列（实测正好 `ebit`/`ebitda`，旧目录归档）→ 23→21 列，类型 mismatch 2→0。
  - 注：income_quarterly 审计 missY 仍高（63）是 **B1 curated-子集 vs 累计 income 全量** 的对比假象（非缺陷）；PIT ledger/provider 建议下轮重建以同步去列（不紧急，无消费方）。

---

## B. 有意的派生子集 / 非默认补全（验证充分性，非缺陷）

### B1. `income_quarterly` 仅 23 列（vs 累计 income 94）— **有意curated**
- 23 列 = 单季因子所需核心项（revenue/total_revenue/oper_cost/total_cogs/各费用/operate_profit/total_profit/n_income(_attr_p)/basic_eps/diluted_eps/ebit/ebitda/**rd_exp**/biz_tax_surchg + 锚）。
- 其余字段可由累计 income 经 `derive_single_quarter_value` 现算。→ **非数据丢失**。
- **验证**: 确认 23 列覆盖所有单季因子需求；若某因子需子集外的单季值，确认走 derive 路径而非误读 0。

### B2. `cashflow_quarterly` 漏 5 个（vs 累计 cashflow）
- **缺**: `free_cashflow`,`conv_copbonds_due_within_1y`,`conv_debt_into_cap`,`oth_loss_asset`,`uncon_invest_loss`（累计 cashflow 有，单季版无）。
- **验证**: 查单季 builder 为何丢这 5 个（尤其 `free_cashflow` 有用）；确认是 report_type 2/3 行本就无该列，还是 builder 选择性遗漏。

### B3. `income`(9) / `balancesheet`(6) 漏默认-N 的新会计科目
- income 缺: `oth_income`,`total_opcost`,`asset_disp_income`,`credit_impa_loss`,`oth_impair_loss_assets`,`net_expo_hedging_benefits`,`amodcost_fin_assets`,`end_net_profit`,`net_after_nr_lp_correct`。
- balancesheet 缺: `lease_liab`,`use_right_assets`,`receiv_financing`,`oth_eq_invest`,`oth_eq_ppbond`,`oth_illiq_fin_assets`（IFRS-16 / 金融资产重分类的新科目）。
- **验证**: 默认-N、覆盖稀疏；仅当某因子需要时，传 `fields=` 补取。

### B4. `express`(业绩快报) 漏 16 个默认-N 对比字段
- **缺**: `yoy_sales`,`yoy_op`,`yoy_tp`,`yoy_dedu_np`,`yoy_eps`,`yoy_roe`,`yoy_equity`,`*_last_year`,`growth_*`,`is_audit`,`remark`。
- **验证**: 这些是 Tushare 现成的同比/去年同期；可自算。决定是否补取或自算。

---

## C. 次要 / 记录即可

| 数据集 | 缺(默认-N) | 说明 |
|---|---|---|
| `margin_detail` | `name` | 股票名，冗余 |
| `stk_limit` | `pre_close` | daily 已有 pre_close |
| `dividends` | `base_date`,`base_share` | 分红基数 |
| `stk_holdertrade` | `begin_date`,`close_date` | 增减持交易窗口起止；事件分析或需要 → 偏 MED |
| `disclosure_date` | `modify_date` | 披露计划**修改日**；PIT 时序或相关 → 偏 MED |
| `fina_mainbz` | `update_flag` | 更新标记 |
| `report_rc` | `imp_dg` | 机构关注度（默认-N） |
| `forecast`/`express` | (extra) `update_flag` | 本地有、官方表未列；Tushare 实际返回的元字段，**良性** |

---

## C2. 类型一致性结果（本轮已加做）

脚本已对每个共有字段做 doc 类型 vs Parquet dtype 比对（`doc_kind` vs `arrow_kind`）：

- ✅ **无 HIGH 级**：没有"官方数值字段被本地存成字符串"的隐患（这是最危险的一类，结果为 0）。
- **note 级**：
  - `trade_cal.is_open`：doc=str / local=int64 —— 良性（0/1 标志转 int）。
  - **日期类型跨数据集不统一**：`stk_holdertrade.ann_date` 与 `industry_sw2021_members.in_date/out_date` 存为 `timestamp[ns]`，而其余数据集（income/balancesheet/…）的 `ann_date` 存为 str。→ **验证 ledger/PIT 构造对两种日期表示都正确**（MED；若有任何对日期列做字符串比较的旧代码会出错）。
  - **全空列（field 在、值全 NULL，采样推断为 null 类型）**：除 A3 的 ebit/ebitda 外——income 的 `transfer_surplus_rese`/`transfer_housing_imprest`/`transfer_oth`/`adj_lossgain`/`withdra_legal_pubfund`/`workers_welfare`；balancesheet 的 `agency_bus_liab`；express 的 `bps`/`open_bps`/`open_net_assets`/`perf_summary`。多为稀疏/历史科目；**逐个确认是 Tushare 本就稀疏还是获取丢值**（并入 D 节覆盖核对）。

---

## D. 本轮未覆盖 → 明确的"后续验证"项

1. **类型一致性 ✅ 已完成**（见 C2）：无 HIGH 级；note 级（日期表示不统一、全空列）已记录。
2. **值层语义/单位**：字段同名但口径/单位/符号不同（如金额万元 vs 元、比率 % vs 小数）。需抽样对拍 Tushare 原值。
3. **`daily` 合并碰撞**：`daily`+`adj_factor`+`daily_basic` 三源合并，`close`/`trade_date`/`ts_code` 同名列。并集=27、本地=27 无丢失；但 `close` 取自 daily 还是 daily_basic 的语义需确认（两者应一致，低风险）。
4. **`stock_st_daily` 为派生**（无直接接口，列: ts_code/trade_date/name/type/type_name）：ST 构造逻辑（基于 namechange）单独验证，不在接口比对范围。
5. **`moneyflow` 口径**：本地走 `pro.moneyflow`(doc 170)，另有 THS(348)/DC(349) 变体口径不同；确认因子用的是哪个口径、是否需要区分。
6. **覆盖/起始日期**：字段存在 ≠ 有值；各字段的非空覆盖率与历史起点需对拍 data_tracker。

---

## 一句话总结

逐字段穷尽比对 35 个数据集（字段存在性 + 默认显示 + 类型）：**PIT 日期锚零缺失、生产主数据集字段完整、无数值-存成-字符串隐患**。三个确认的真实问题：(A1) `stock_basic` 漏 2 个默认字段（低危易修）；(A2) `fina_indicator` 因未传 `fields=` 漏 58 个非默认指标（多数 q_* 系我们有意自算，需逐项裁决）；(A3) **`income_quarterly.ebit/ebitda` 100% 全空**（单季端点不填，静默 NaN 坑）。其余为有意派生子集、次要默认-N 缺失、或良性类型转换。值层语义/单位/覆盖率的深度对拍列入 D 节后续验证。

## 待验证字段清单（速查）
| 级别 | 数据集 | 字段 | 动作 |
|---|---|---|---|
| ✅ 已修 | stock_basic | act_name, act_ent_type | 已补入 fields 重抓 (missY 2→0) |
| ✅ 已修 | income_quarterly | ebit, ebitda (全空) | 已删列 + 源头 dropna (typemm 2→0) |
| ✅ 已修 | fina_indicator | 全部 167（含 roe_avg/inv_turn/turnover-days/ebit_to_interest/q_*…）| 已取全量 (missN 58→0)；**下游 ledger/provider/治理待办** |
| 充分性 | cashflow_quarterly | free_cashflow (+4) | 查单季 builder 为何丢 |
| 补取? | express | yoy_*, *_last_year (16) | 自算或补取 |
| MED | disclosure_date | modify_date | 披露计划修改日，PIT 相关 |
| MED | stk_holdertrade | begin_date, close_date; ann_date(timestamp) | 窗口字段 + 日期类型统一 |
| 覆盖 | income/balancesheet/express | 多个全空列（见 C2） | 确认稀疏 vs 丢值 |
