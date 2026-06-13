# Phase D — 基本面因子批量复刻:字段矩阵与分档(2026-06-11)

> D1 产物:~99 个基本面因子 × 已注册字段 的可构造性分档。
> 构造等级:**exact**(语义与中金公式一致,槽位/字段齐)/ **approx**(用 indicators
> 累计口径或 vendor 字段近似,带 caveat)/ **blocked-slots**(需扩展 q 槽或注册新字段)/
> **blocked-data**(需新数据源)。
> 经验依据:C 阶段已证 D 后缀(当期−上期)的"上期"= **上一季度**(GPMD 用 q1..q4 vs
> q0..q3 三指纹靶心),因此凡缺 q1 槽的资产负债表项,其 D 因子全部 blocked-slots。

## TTM 构件(全部 exact)

| 构件 | 表达式 | 备注 |
|---|---|---|
| NI_TTM | Σ n_income_sq q0..q3 | 含少数股东(归母仅 q0/q4)— 水平类 caveat |
| REV_TTM / REV_TTM_PREV | Σ total_revenue_sq q0..q3 / q1..q4 | |
| COST_TTM / PREV | Σ oper_cost_sq 同上 | |
| OCF_TTM | Σ n_cashflow_act_sq q0..q3 | 无 q4+ → OCF 同比族 blocked |
| EBIT_TTM | Σ ebit_sq q0..q3 | |
| CAPEX_TTM | Σ c_pay_acq_const_fiolta_sq q0..q3 | |
| AVG_ASSETS / AVG_INV / AVG_AR | (q0+q4)/2 | 平均余额口径 |
| EQUITY | $bps × $total_share × 1e4 | vendor 每股净资产 × 股本(近似归母权益) |
| MV_YUAN | $total_mv × 1e4 | 万元→元 |

## 分档清单

### exact(31:9 锚 + 22 新)

盈利:CFOA✓锚 ROA_TTM✓锚;成长:NP_Q_YOY✓锚 NP_QOQ OP_Q_YOY OP_QOQ($q_op_qoq)
OR_Q_YOY TA_YOY GPMD✓锚;营运:AT INVT NPM_TTM RAT(缺应收票据,仅应收账款);
盈余:CSR;安全:CCR CUR QR($quick_ratio) Debt_Asset(去重 lev_*);估值:BP_LR(=1/$pb,
LR口径吻合) EP_TTM✓锚 DP✓锚 FCFP_TTM(OCF−资本开支) OCFP_TTM SP_TTM(=1/$ps_ttm);
规模:FC FC_MC Ln_FC(去重 size_ln_circmv) Ln_MC✓锚(去重 size_ln_mcap) MC;
价量锚:mmt_normal_m mmt_range_m。

### approx(17,indicators 累计口径或 vendor 近似,逐因子 caveat)

ROE_TTM(NI_TTM/EQUITY) ROIC_TTM(EBIT×(1−$tax_to_ebt)/(EQUITY+lt_borr+st_borr))
DTE(total_liab/EQUITY) EPS_YOY($basic_eps_yoy 累计) NP_Deducted_YOY($dt_netprofit_yoy)
NP_YOY($netprofit_yoy) NP_Z(其 ~500d 滚动 z) OP_YOY($op_yoy) OP_Z OR_YOY($or_yoy)
ROE_YOY($roe_yoy) OPM_TTM($op_of_gr 累计) ATD/INVTD/RATD(分母用当期均值,仅分子换
上期 TTM —— 周转率 D 的近似) DPR_TTM($dv_ttm×MV/NI_TTM) PEG_TTM($pe_ttm/$netprofit_yoy)。

### blocked-slots(12 —— 一次字段注册全部解锁)

CFOAD ROAD ROED CCRD CURD DAD DTED QRD CSRD APRD OCF_Q_YOY OCF_YOY。
**解锁需求**:balancesheet 加 q1 槽(total_assets/total_liab/total_cur_assets/
total_cur_liab/inventories/money_cap)+ cashflow 加 q4..q7(n_cashflow_act)+
income 加 operate_profit q1..q3、n_income_attr_p q1..q3。走标准字段批准流程
(approval YAML + parity),D 批量第一轮结束后做。

### blocked-data(~24)

TOE/TOE_Z/OT_Z/PTCF_Z(应交税费、缴税现金流科目)、LPNP/OCFA(滚动回归+明细)、
EV2EBITDA(income.ebitda 单季 100% 空,已知)、NCFP_TTM(净现金流增量科目)、
NP_SD/OP_SD(稳健增速定义不明)、QPT(分层打分配方未披露,留待逆向)、
Comp_opt/TOP_MANA_INCOME(高管薪酬——新端点,§6.1 先读文档)、
IHN_diff/Ln_IH/LHRD(机构持仓/十大股东明细——新端点)、
分析师 12/16(**blocked-FIELDS,非 blocked-window**——更正 2026-06-13):**report_rc 的
report_date+1 锚点经验证自 2010 起即真 PIT**(create_time=2022-05 只是 Tushare 批量入库戳,
非 report_date 不可信的证据;三测全 PASS:水平对账 corr +0.997、误差对账 Tushare 比 JQ
oracle 更不准 +0.054=无 lookahead、全市场 17,717 点池化 Spearman +0.950 含退市股;详见
[REPORT_RC_PIT_ANCHOR_VALIDATION.md](../data_expansion/REPORT_RC_PIT_ANCHOR_VALIDATION.md))。
所以 CAFR/EEP/FORE_Earning/FORE_EPS/FORE_OP/EEChange/EOPChange 这些**一致预期水平值因子可
覆盖 2010-2026 全历史**——真正的缺口是:目前只注册了 4 个事件流原语
($report_rc__eps_up/eps_dn/eps_revision_count/n_active_analysts),需把一致预期**水平值**
字段(FY1 一致预期盈利/EPS/营收、离散度等;验证里已从 report_date+1 明细重建过,证明可做)
**物化进 ledger+provider 并注册**才能复刻。RatingChange/TargetReturn 另需 report_rc 原始的
评级/目标价列(待核)。EINS_75D/RPP_75D(机构数/报告数)用现有 n_active_analysts/事件计数即可。
⚠ **eps_diffusion(breadth/二阶差分)单独受 6-15 restatement 金丝雀硬门约束**——水平层 PIT
已证,但 breadth 对单条修改记录更敏感,canary PASS 前 OOS 不能动(eps_diffusion 的 provisional
approved 状态不因本次水平验证而解除)。)
NP_SUE0/1 槽深不够(8 季 σ)→ 已有 earn_sue_ni_assets(approved)为同族,不重复造。

### 去重(不重复注册,映射表对照真值)

Ln_MC=size_ln_mcap、Ln_FC=size_ln_circmv、Debt_Asset≈lev_*、NP_SUE≈earn_sue_*、
APR≈qual_accruals、DP=val_div_yield、EP/SP/BP≈val_* 族 —— 复刻表达式仍按中金公式
独立实现跑对照(验证目的),但**入目录前用 definition_hash 比对,语义重复的不注册**,
在映射表记录"目录内对应因子"。

## 执行顺序

1. **D2**:`cicc_factor_defs.py`(48 表达式 + 元数据)→ 批量跑冻结协议 × 3 域 × 真值
   (真值解析器直接读 CICC_因子表现真值.md 的表格,不手抄)
2. **D3**:逐类计分卡(exact 类预期高保真;approx 类带 caveat 判读)
3. **D4**:槽位扩展字段注册(解锁 12 个 D 后缀因子)→ 补跑
4. **D5**:去重 + 入目录(draft)→ 10 组 IS 门(factor_lifecycle)批量
5. 复合因子(Profit/Growth/Safe/Acc/QQC)在成分齐后合成;分析师类独立子阶段(2022+ 窗)
