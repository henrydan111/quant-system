# 交接 Prompt — 果仁复刻因子批量加入 factor catalog(正式化)

> 把本文件全文作为另一个 Claude Code session 的初始指令。工作目录 E:\量化系统。
> ⚠ 这是**正式基础设施变更**(catalog 是 42 个调用点的发现层入口),受 CLAUDE.md §3.2/§3.5/§10 全约束。

---

你在 E:\量化系统。先按 CLAUDE.md §1 刷新上下文,然后精读:
- `workspace/research/idea_sourcing/guorn/DEPLOYED20_REPLICATION_REPORT.md`(**口径 registry §2 是你的
  施工图** —— 13 条口径全部 xlsx 实测钉死,不得偏离)
- `workspace/research/idea_sourcing/guorn/guorn_local_field_mapping.md`(逐因子映射 + 验证状态)
- `src/alpha_research/factor_library/catalog.py` + `src/alpha_research/factor_lifecycle/README.md`
  (状态阶梯 draft→candidate→approved;你只做 **draft** 注册)
- E1a-E1h CICC 波次在 project_state 的先例(它们就是"外部配方 → catalog draft"的标准作业)

## 任务

把 deployed-20 复刻中验证过的果仁因子,按下述三档分诊,把 **A 档全部**作为 draft 加入
`get_factor_catalog()`,B/C 档产出阻塞清单文档。目标:果仁口径成为 catalog 的一个正式因子族
(命名前缀建议 `grn_`,沿用 `{category}_{name}_{lookback}` 约定)。

### A 档 — Qlib 表达式可写 + 字段已注册(直接入 catalog 为 draft)

全部用 provider 字段、逐股时序运算(无横截面、无外部数据);**每个 $field 必须包 `Ref(...,1)`**
(§3.2 PIT lint 硬门,预测用途 T-1;这些因子在平价 harness 里是 lag-0 展示口径,入 catalog 必须加 Ref):

| 因子(果仁名) | 表达式要点(口径 registry 引用) |
|---|---|
| grn_core_profit_qgr | CoreProfitQGr%PY,**金融股 0-fill**(fix#9→§2.9;费用腿 `If(IsNull(x),0,x)` 型守卫,营收必须非空) |
| grn_core_qoq_minus_ttm | QoQ core 增速 − TTM YoY core 增速(q0..q7;fix#8 TTM 前移语义) |
| grn_sales_qgr / grn_eps_dedt_qgr / grn_incometax_qgr / grn_rnd_qgr | 单季同比族(分母 abs 约定见 mapping doc 各行:所得税分母是 **q0** 非 q4!) |
| grn_roe_ttm_diff | ROETTMDiffPQ,**加权平均净资产** (0.5·q4+q3+q2+q1+0.5·q0)/4(§2.11;已知选股级脆弱,备注进 docstring) |
| grn_shares_avg_gr | (Σtotal_share_q0..3)/(Σq4..7)−1 |
| grn_ato_diff | ATO(0)−ATO(4),**分母=4季均资产**(fix#10/caliber A,penny 0.983) |
| grn_gross_profit_assets | (rev−cost)_sq/总资产 |
| grn_ev / grn_gp_ev / grn_ebitda_ev | EV 按果仁公式 **VERBATIM 含货币资金×2**(§2.13,docstring 必须写明这是保真复刻的作者 bug);EBITDAQ 的 D&A 腿=cum 相邻差分(见 `_verify04_upgrade.py::da_sq`,能否纯 Qlib 表达式化需评估——Q1 相位判定 cum==sq 是逐股运算可表达,若表达式过繁则归 B 档) |
| grn_zsfz | 真实负债资产率:负债/(资产−商誉−无形−开发支出),无形三项 NaN→0 |
| grn_onmom_250_20 / grn_onmom_120_20 | Σln(adjopen/Ref(adjclose,1)) 排除涨停日($limit_status),窗口 min_periods=1 语义与 catalog 的 rolling 语义对齐评估;catalog 已有 mom_overnight_20d 先例——去重!新增前 grep catalog 现存 mom_/rev_ 族,**语义重合的做 alias 备注不重复注册** |
| grn_ret250 | 250 日涨幅(adj ratio;已知 ~5.5% 窗口成员残差,rank 可用) |
| grn_org_chg_60 / grn_rating_up | report_rc 聚合字段的 Ref 变化率/水平(vendor-approx rank-faithful 类,docstring 标注 §1c 约束:仅排名/复合用) |

### B 档 — 需先物化数据进 ledger/provider(产出前置需求清单,不入本次 catalog)

⚠ 记忆 `feedback_factors_must_go_through_ledger_qlib`:**不许**在 catalog/正式路径里 hand-roll 原始
parquet 读取。以下因子的平价实现走了 NON-FORMAL 直读,正式化前必须先走 data_infra 物化:

1. **声明制分红族**(股息率TTM/DivGrPY%/近三年分红之和/Div%NetIncY2/DivOP%):需把
   `guorn_dividend_caliber` 的三口径(ann-date TTM / 报告期 byq / FY byfy)物化成 provider 日频字段
   (如 `$declared_div_ttm`、`$declared_div_fy0..2`)—— data_infra 项目,PIT 锚=ann_date,含 stale-预案
   规则(mapping doc 分红块)。
2. **快报族**(express 隐含单季 YoY,平价 penny sp 0.990):express 数据集入 PIT ledger + provider
   (`$express__np_q_yoy` 型,存活窗语义 = 快报期==q0+1)。
3. **历史贝塔**(vs 000300):跨序列回归不是逐股 Qlib 表达式 —— 需物化为日频字段(如 `$beta_250_hs300`)。
4. 深槽 16 因子(FCF stdev12、3Y CAGR 族):等 PROMPT_deepslot16_build 完成且若决定常驻,需 live 深槽。

### C 档 — 横截面/复合(catalog 的 Layer-2/industry-relative 机制,单独评估)

bpfin(BP筹资市值比调整,sp 0.976-0.982)、ep_core_neut、中性换手率 v2 —— 全 A 截面回归残差。
评估 catalog 的 `add_composites()`/industry-relative 层能否表达(cs_* helpers 在 factor_eval 有);
表达不了就归入 B 档式前置清单。**mi_rndqp(HneutralizeMI)语义未解(sp −0.18),禁止入库。**

### 治理硬门(逐条走,不许跳)

1. 全部注册为 **draft**(discovery 可用;不碰 candidate/approved)。catalog 数量是 DERIVED
   (`catalog_composition()`),不要在任何文档写死数字。
2. **PIT lint 三件套必须绿**:`test_factor_library_pit_safety.py`(Ref 包裹栈扫)、
   `test_operator_expressions.py`、`test_operator_behavioral_pit.py`;外加
   `scripts/lint_no_unsafe_pit_dates.py` 与 `lint_no_bare_qlib_features.py`(run_daily_qa 内)。
2b. **⚠ 原生 compute 冒烟必做(2026-07-03 教训 + GPT finding #4)**:PIT/字段门只审表达式 LOGIC,抓不到
   原生 `compute_factors` 的**跨数据集广播崩溃**——分子/分母(或 flag/价格)来自不同 provider 数据集时,
   某股一侧空序列 (0,) 一侧满长 (N,) → qlib `If` 的 np.where 广播崩;deployed-20 harness 的
   `D.features + reindex(grid).ffill()` 会掩盖它,原生逐股求值不掩盖。**每个新因子必须过一次
   `operators.compute_factors(catalog={f: expr}, start='2011-01-01', end='2011-06-30', ...)`**(幼股密集窗,
   深槽 q5+ 与 limit_status 最易缺失;模板见 `_grn_isolate.py`)——0 CRASH 才算过。**跨数据集因子通用规范**:
   守卫作用在已算比值上(`If(Abs(ratio)<cap, ratio, nan)`,cap≫真实量级),或稀疏字段用 `+ Ref($dense,1)*0`
   锚到稠密字段长度。这条**先于**下面的字段门/sync。
3. `sync_catalog` 后跑 `tests/alpha_research/test_factor_registry.py` 全文件(catalog↔registry 平价、
   幂等、TestFormalFactorCompatibility)—— 记忆 `feedback_run_full_test_file_after_gate_change`。
4. 每个因子 docstring:公式、数据源、口径 registry 编号引用、价格基准(adj/raw)、已知残差/脆弱性
   (如 ROETTMDiff 选股级脆弱、ret250 窗口残差、report_rc vendor-approx)。
5. **§10 GPT 跨审必过**(这是 substantial:新因子族 + 0-fill/verbatim-bug 类非常规口径需要独立审)。
   自审→push 分支→canonical template→GPT→修→复审;结论记 project_state。
6. 与现存 catalog 去重:新增前对每个候选 grep 现有因子(liq_/mom_/rev_/grow_/qual_ 族)—— 语义重复的
   记 alias 映射进 mapping doc,不重复注册(E1c 的 dedup 先例)。
7. 完成后:project_state 注记 + deployed_20_replication_status 台账 + 本 prompt 文件标注 DONE。

### 明确的负面清单(不做)

- 不注册:mi_rndqp(语义未解)、退市风险/壳价值/未来20日新增流通股(果仁专有/数据缺)、
  池级宏观闸(策略级择时,非因子)、预期净利润Q 族(季度 consensus 无数据)。
- 不因为"果仁在用"就赋予任何 alpha 预期:入 catalog = 可被发现,之后走正常 IS-gate/sealed-OOS,
  与 E 波次同权。draft ≠ 有效因子。
