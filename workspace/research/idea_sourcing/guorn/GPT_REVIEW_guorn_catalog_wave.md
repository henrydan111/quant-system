# GPT 5.5 Pro 跨审 Prompt — 果仁复刻因子 catalog 波(12 grn_* draft + 67 字段枚举扩展)

> 使用方式:推送分支后(`git push origin calendar-unfreeze`,commit 见下)把本文全文交给 GPT 5.5 Pro。
> 嵌入文本为权威;链接供对照。公共仓库 https://github.com/henrydan111/quant-system(分支 calendar-unfreeze)。

---

你是独立评审。请审查一个 A 股量化系统的**因子目录扩展**:把果仁(guorn.com)deployed-20 复刻战役中
经 xlsx 真值逐股验证的 12 个因子口径,注册为 factor catalog 的 draft 因子,并为此扩展字段注册表
(income +42 / balancesheet +24 / indicators +1,全部是已批准家族的枚举扩展,无状态迁移、无新数据摄取)。

## 必须对照的量化研究原则(按优先级)

1. **PIT / 无前视**:每个 `$field` 是否都在 `Ref(...,1)` 帧内(T-1);报告期槽位(`_sq_qN`/`_qN`)由
   provider 的 effective_date>disclosure 严格锚定内核物化(深度9 扩展已于 2026-06-30 获你方 APPROVE)。
2. **口径忠实**:表达式是否逐字对应果仁验证过的口径(证据 = 果仁自家 xlsx 持仓详单的因子真值列)。
3. **治理**:仅 draft(无 alpha 断言)、目录↔registry 平价、字段门正式可解析、计数派生不硬编码。

## 审查对象

**文件 1:`src/alpha_research/factor_library/catalog.py`** — 新增 `_grn_zf` / `_grn_core_sq` /
`_add_guorn_replication_factors`(12 因子)+ category map 'grn' 项。关键构造:

- **0-fill 惯用式** `If(Eq(x, x), x, 0)`:此 qlib 版本无 IsNull;NaN==NaN 逐元素为 False → 仅 NaN→0,
  **负值保留**(fin_exp 利息收入为负,必须保留)。实证:银行(缺 oper_cost/sell/fin 行)
  grn_core_profit_qgr@601939/2014-01-09 = 0.0971,与复刻 harness 的 pandas fillna(0) 值一致,
  果仁 xlsx 同日 0.0993(结构级一致,差异=重述时点)。
- **grn_core_qoq_minus_ttm**:TTM(x,4)=前移 4 季(一年前 4 季和,果仁官方 自定义函数列表 L610),
  表达式 ~9.7KB(core 块出现 8 次)——已冒烟求值通过。
- **grn_ato_diff_py**:分母=4 季均资产(caliber A;#16 xlsx penny 0.0005/sp 0.983,首末均 B 被否 0.879)。
- **grn_roe_ttm_diff_q**:加权平均净资产代理 (0.5·q4+q3+q2+q1+0.5·q0)/4;docstring 标注选股级脆弱。
- **grn_gp_ev**:EV **逐字复刻果仁作者公式含"货币资金减两次"bug**(#4 xlsx sp 0.981 证明部署书交易的
  就是这个形态;docstring 写明)。$total_mv 万元×1e4 对齐元。
- **grn_onmom_{250,120}_20**:`Sum(If(Eq(Ref($limit_status,1),1), 0, Log(...)), w) − Sum(...,20)`;
  qlib Sum 部分窗口语义已实证(IPO 后 60 交易日有值 = 果仁 min_periods=1 caliber)。
- 去重记录:250日涨幅==mom_return_250d、SalesQGr≈grow_rev_q_yoy(分母 |q0| vs |q4|)未重复注册;
  onmom 与 mom_overnight_20d(20日均值、无涨停排除、无窗口差)构造不同。
- 明确排除:report_rc 聚合(数据集 quarantine)、EBITDAQ/FCF 族(D&A cum 差分待物化)、分红族
  (需 declared-dividend provider 字段)、历史贝塔(跨序列回归)、HneutralizeMI(语义未解,平价 sp −0.18)。

**文件 2:`config/field_registry/field_status.yaml`** + **approvals/2026-07-03_guorn_catalog_field_extension.yaml**
+ **field_approval_log.jsonl 尾行** — 67 字段清单、逐字段价值证据、provider_build_id/calendar_policy_id
绑定(approval-evidence binding 测试通过)。

## 已执行的验证(结果全绿)

- PIT 三件套:test_factor_library_pit_safety / test_operator_expressions / test_operator_behavioral_pit = 80 passed
- tests/alpha_research/test_factor_registry.py 全文件 = 32 passed(含 TestFormalFactorCompatibility:
  12 个 grn 在扩展后字段门下正式可解析)——同步前后各跑一次
- tests/data_infra/test_field_registry.py + test_approval_evidence.py = 91 passed
- lint_no_bare_qlib_features 干净;lint_no_unsafe_pit_dates 的 1 个 PIT002 违规在
  workspace/scripts/audit_thaw_frozen_prefix.py(日历解冻工作流的工具,非本波,已知悉待其会话处置)
- sync_catalog_to_registry:dry-run 恰好 12 new_drafts / 0 其它漂移 → 执行后 parity_ok=True
- 12 表达式逐一 D.features 冒烟(银行+白酒双样本),与 xlsx 验证过的 harness 值逐点一致

## 结构化自审(§10,verdict: clean for GPT)

- §3.2:全部 $field Ref(...,1) ✓(解析器栈扫测试过);forward_return 未触碰 ✓
- §3.5:仅 draft、writer gate 未触碰、计数派生 ✓
- 字段扩展 = 同家族同内核,provider bin 存在性经本会话 D.features 实际消费证实 ✓
- 口径出处逐条可溯(DEPLOYED20_REPLICATION_REPORT §2 registry #7/#9/#11/#12/#13)✓
- 无对冲词;所有数字来自运行输出 ✓

## 请你重点回答

1. `If(Eq(x,x), x, 0)` 0-fill 惯用式有无边角(±inf?元素级 Eq 语义在该 qlib 版本的 rolling 组合下)?
2. 9.7KB 表达式(grn_core_qoq_minus_ttm)有无解析/性能/数值风险,是否建议改为 operator 函数封装?
3. EV 的 verbatim author-bug 复刻:作为 draft 因子进入 alpha 研究是否应同时注册"修正版"(单次货币资金)
   以免 bug 形态被误当经济含义?(我方倾向:draft 阶段保持单一 verbatim 版,IS-gate 用数据说话。)
4. 67 字段枚举扩展的治理:同家族扩展不走 quarantine→approved 流程是否成立(先例 2026-06-24 Phase-B)?
5. grn_roe_ttm_diff_q 已知选股级脆弱(果仁侧 median |val|=1pp)——draft 注册是否需要额外 caveat 机制?
6. 其它任何 PIT / 口径 / 治理问题。

裁决格式:APPROVE / CHANGES REQUIRED(逐条,标 blocker/major/minor)。
