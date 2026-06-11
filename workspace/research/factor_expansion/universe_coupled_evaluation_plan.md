# 因子 × Universe 耦合评估:设计与执行方案(供 Review)

> 版本:Draft-3,2026-06-11(Draft-2 + 用户指令:**入目录即全域体检**——任何因子
> 进 draft 时自动在全部 universe 上评估一遍,见 §3.1b)。作者:Claude(本 session)。
> 覆盖:因子评估链路的 universe 一等公民化设计 + 配套执行计划(Phase D 收尾 → F → G)。
> 已定事项与待批事项分列;待批事项见 §8,**review 时重点看 §3.3 与 §8**。

---

## 1. 目标与设计原则

**目标**:量化策略最重要的筛选之一是 universe 的选择;因子的"有效"从来是"在某个域有效"
(已有证据:月度反转中证1000 IC −5.8% / 沪深300 衰减过半;eps_diffusion 因子层 approved
但流动 top300 域部署即崩;北向因子外资流出期翻转)。本方案把 universe 从"事后切片"
升级为**因子评估身份的一部分**。

**原则**(综合行业范式):

| # | 原则 | 来源范式 |
|---|---|---|
| P1 | 因子 Layer-1 全市场计算,Layer-2 域掩码,绝不先过滤后算 | Barra 估计域/投资域分离;已是本仓铁律(§8.1) |
| P2 | 每因子 × 每域出有效性档案,矩阵常驻可见 | 卖方金工(中金/华泰)按域出表 |
| P3 | 正式评估的 universe **事前声明**,声明域=评估域;扫多域则检验次数按域累计 | WorldQuant:universe 是 alpha 身份 |
| P4 | 策略按目标域(基准)过滤可用因子 | 指数增强:基准即域 |
| P5 | 对外评估分类只有 discovery / formal 两类(refresh 已退役) | 用户指令 2026-06-11 |
| P6 | 自动证据永不驱动状态(`formal_evidence_eligible` 承重墙);OOS 单发花封条 | 本仓既有治理,不动 |

## 2. Universe 框架(已落地,B1)

7 个命名域([universes.py](../../../src/alpha_research/factor_eval/universes.py)),
统一 CICC 剔除屏(ST/停牌/一字板/上市<1年),月度成份 as-of 日频掩码(PIT 安全,
半年度调样 ~9 交易日陈旧窗已文档化),已被 C/D 阶段 144+30 格真值对照实战验证:

| universe_id | 域 | 基底 | 起始 |
|---|---|---|---|
| univ_all | 全市场 | 沪深全A(剔北交所) | 2010-01 |
| univ_csi300 | 大盘 | 沪深300 成份 | 2010-01(成份已补齐 2008+) |
| univ_csi500 | 中盘 | 中证500 成份 | 2010-01 |
| univ_csi1000 | 小盘 | 中证1000 成份 | 2014-11 |
| univ_microcap | 微盘 | 市值最小400,月末刷新 | 2010-01 |
| univ_growth | 成长 | 创业板+科创板(代码段) | 2010-06 |
| univ_liquid_top300 | 可部署 | ADV20 前300,月末刷新 | 2010-01 |

## 3. 因子链路逐环节设计(новое = 加粗)

### 3.0 字段关卡(不变)
每个 `$field` must be approved in field_status.yaml;新数据走 ledger→provider→注册,
禁止手搓 PIT(lint 硬拦)。

### 3.1 入目录 draft(不变 + 一处新增;**Draft-2 修订:声明必填**)
表达式 `Ref(...,1)` 包裹入 factor_library → `sync_catalog` → draft。
**新增(必填):注册时声明 `intended_universe`**(可为列表:主域+备域;天然子域因子
填 univ_all+覆盖说明)。声明时间戳**必须先于该因子的任何 discovery 矩阵证据**——
这是预注册时点:声明(draft)→ 看矩阵(discovery)→ 申请门(formal)的时序锁,
在源头掐死"先看 7 域分数再挑域声明"。
**设计边界(review 已确认)**:universe 进的是**生命周期声明**,不进**计算身份**——
表达式与 definition_hash 保持 universe 无关(P1:同一表达式在任何域评估,计算结果
不变;目录是复用库,绑域会致条目爆炸 + definition_hash 去重语义崩坏)。

### 3.1b 入目录即全域体检(**用户指令 2026-06-11,已定**)
**任何因子进入 draft 时,自动在当前全部 universe 上各评估一遍**(unified discovery
方法学 × 7 域,证据行按 (factor, universe) 落表)——出生证明即全域有效性档案。
- **执行形态**:注册驱动 = 一个事务序列「写目录 + `intended_universe` 声明 →
  sync_catalog → 自动触发 7 域 sweep」;声明时间戳天然先于全部矩阵证据,§3.1 的
  时序锁由机械流程保证而非自觉
- **守门**:daily QA 增加检查——任何现役 draft 在当前 methodology_hash 下缺任一
  域的证据行 → WARNING(不阻断注册本身;评估失败可重跑,身份不悬置)
- **成本**:面板计算共享、域掩码廉价,单因子 ×7 域为分钟级;批量注册(如 D5 的
  ~24 个)合并为一次批跑
- 与 §3.2 的关系:F2 的全目录矩阵 = 存量 190 的一次性回填;本条 = 新增量的常设
  入口规则,两者用同一引擎与口径

### 3.2 discovery(自动,evidence-only)
**升级:全目录 × 7 域矩阵评估**。`universe_id` 进 `EvalMethodology`(入
methodology_hash,每域一个哈希);unified_eval 每因子产出 7 行域限定证据
(heldout RankICIR / HAC-t / 中性化 / 10 组 profile / 换手,全部按域计算)。
证据行新增 `universe_id` 列;dashboard 因子详情 = 7 域有效性档案 + 域切换。
**产物:全目录"因子×域"有效性矩阵**——P2 的落地。状态照旧不动。

### 3.3 IS 门 draft → candidate(**待批的合同修改,§8-D1;Draft-2 修订**)
- hypothesis 注册时**声明评估域**(prescription 增加 `universe_id`,缺省 univ_all
  = 完全向后兼容,现有 candidate 全部等价于"univ_all 域过门")
- **Draft-2:门的声明域必须等于 draft 时的 `intended_universe`**;改域走显式变更
  流程——披露已看过的该因子矩阵结果 + 新域的经济学先验,门复核可见;"声明晚于
  矩阵"的域自动标记 post-hoc,按更高怀疑等级复核
- 门在声明域上跑 IS walk-forward(掩码后截面;heldout RankICIR + 符号一致性,bar 不变)
- candidate 记录 `gated_universe`;dashboard 状态徽章旁标注域(如 `candidate@微盘`)
- **多重检验纪律**:同一因子在第 2 个域申请过门 = 新检验,testing ledger 按
  (factor, universe) 记账;**禁止结果驱动换域**(在 A 域失败后换 B 域申请,须在
  hypothesis 里披露 A 域的失败记录,门复核时可见)
- 薄域护栏:声明域月均截面 < 200 只(微盘400/液体300 边缘)时 heldout 方差大,
  门报告强制附 bootstrap CI(unified_eval 已有该机制)

### 3.4 sealed OOS candidate → approved(机制不变,激活既有字段)
`FrozenSelectionSet` 冻结身份**本就含 universe** —— 声明域写入冻结集,封条按
(选集+域) 花。无代码改动,只是从"从未用过非全市场"变为"按声明域使用"。
bar 不变(rank_icir 同号 + LS Sharpe>1.0,decile 口径)。

### 3.5 approved + **有效域元数据(新增)**
- approved 仍是单一状态(P6:不搞 7 域状态矩阵,避免 OOS 预算×7 的多重检验灾难)
- 批准时写入 `validity_domains`:= {过门域} ∪ {discovery 矩阵中指标过同等 bar 的域,
  标注 evidence-only}。两类来源区分清楚:**过门域是被 sealed-OOS 验证的;其余域是
  描述性证据**,策略引用非过门域时自担风险并在 prescription 里显式确认
- 策略/部署层按目标域过滤:`resolve` 时目标域 ∉ validity_domains → warn(不阻断,
  resolve-but-label 原则)

### 3.6 部署门(不变)
事件驱动 + 真实成本 + 1× + 目标域(通常 univ_liquid_top300 或基准域)。

## 4. 证据与留痕模型

- 证据行主键语义:(factor_id, universe_id, methodology_hash, run_id);
  `quantile_profile`(10 组逐组年化)按域留痕
- 一致性金丝雀保留:同因子同域的人签 vs 自动行分歧 > 0.005 → dashboard ⚠
- CICC 真值对照层(cicc_protocol)继续独立存在:服务复刻验证,不进注册表证据

## 5. 多重检验与封条经济学(P3/P6 的硬化)

| 场景 | 规则 |
|---|---|
| discovery 矩阵 7 域全跑 | 允许(描述性,不改状态),但**不得以矩阵结果直接申请"最好域"的门**——申请书须给出该域的经济学先验(为何该因子应在该域有效),先验写入 hypothesis,门复核时对照 |
| 同因子多域过门 | 每个域一次完整检验,testing ledger 按 (factor, universe) 计;第 N 域申请须披露前 N−1 域全部结果 |
| sealed OOS | 每个 FrozenSelectionSet(含域)一发;同因子换域 = 新冻结集 = 新封条,但 OOS 时窗重叠的部分照旧永久记账 |
| 经济学先验缺失 | 门可以"仅相关性"理由拒绝——A 股小盘反转有微观结构先验,某因子"恰好在成长域 ICIR 高"没有 |

## 6. 执行计划(阶段 → 交付物 → 验收)

| 阶段 | 内容 | 交付物 | 验收 | 依赖 |
|---|---|---|---|---|
| **D5**(下一步) | exact 档 ~24 复刻因子去重入目录(**首批走"入目录即全域体检"流程**:声明+注册+7域 sweep 一体) | catalog 新 draft + 映射表(CICC码↔目录id)+ 每因子 7 域证据 | definition_hash 零冲突;PIT-safety 测试过;7 域证据行齐 | F1(证据行带域) |
| **D4** | 槽位字段注册(balancesheet q1、cashflow q4-q7、income op/attr_p q1-q3) | 批准 YAML + parity 测试 + 12 个 D 后缀因子补做 | parity 0-mismatch;真值对照 IC 容差内 | 无(与 D5 并行) |
| **F1** | `universe_id` 进 EvalMethodology + 证据行 + store 列 | schema 变更 + 测试 | 旧行兼容读;新行带域 | 无 |
| **F2** | 全目录 × 7 域 discovery 矩阵首跑 | (190+新增) × 7 域证据 | 分批断点续跑完成;矩阵入 dashboard | F1, D5 |
| **F3** | IS 门声明域(prescription.universe_id + testing ledger 按域记账 + 披露规则) | factor_lifecycle 合同修改 + 测试 | 缺省 univ_all 向后兼容;多域纪律测试 | **§8-D1 批准** |
| **F4** | approved 有效域元数据 + 策略层过滤 warn | registry 列 + resolver 标注 | resolve-but-label 不破坏 | F2 |
| **E** | 价量 ~135 因子复刻(真值现读现对,4 域含 csi1000) | 定义模块 + 对照报告 | exact 档 IC 通过率 ≥ Phase D 同档水平 | D5 模式复用 |
| **G** | 全目录统一方法论重评(7 域、10 组、最新 unified_eval) | 全量证据刷新 + dashboard | 替代全部旧口径展示 | F1-F2 |
| 后续 | 分析师类子阶段(2022-05+ 窗)、复合因子合成、域限定策略研究(如微盘反转敞口) | — | — | E, F |

工程量评估:F1+F2 是主要计算成本(190×7 域 ≈ 7 倍现有 sweep;分批断点续跑机制现成,
矩阵全跑预估若干小时级,一次性);F3 是合同修改但代码量小;D4 是数据工程(走既有
promotion 流程,有先例模板)。

## 7. 风险与边界

1. **多重检验面扩大**是本方案最大的内生风险——§5 的纪律就是为此设计;testing ledger
   按 (factor, universe) 记账是硬要求,不是建议
2. 薄域(微盘400/液体300)统计功效低:10 组=40/30 只每组,门报告强制 CI;**不因薄域
   放宽 bar**
3. csi1000 域 2014-11 起,IS/OOS 切窗比其他域短 5 年——门报告须标注有效窗长
4. 有效域元数据的"evidence-only 域"可能被误读为已验证——dashboard 与 resolver
   的标注措辞要把"过门域 vs 描述域"打死,不给含糊空间
5. 全市场缺省保证了零迁移成本:不声明域 = 现状行为,所有存量 candidate/approved
   语义不变(等价于 gated_universe=univ_all)

## 8. 待你批准的决策点

| # | 决策 | 推荐 | 影响 |
|---|---|---|---|
| **D1** | IS 门接受事前声明域(§3.3) | **批准**(行业范式 P3;缺省 univ_all 零迁移) | factor_lifecycle 合同修改;出现域限定 candidate |
| D2 | 有效域中 evidence-only 域允许策略引用(带 warn) | 批准(resolve-but-label 一致) | 否则策略只能用过门域,过严 |
| D3 | discovery 矩阵 7 域全开 vs 先 4 域(all/300/500/1000) | 7 域全开(一次算完,边际成本低) | 计算时长 +75% |
| D4 | "结果驱动换域须披露前域失败"写入门复核清单 | 批准(§5 纪律的执行抓手) | 门复核多一项 |
| **D5**(Draft-2 新增,源自 review) | `intended_universe` 在 draft 注册时**必填**,声明须先于该因子任何矩阵证据;门声明域须等于 draft 声明(改域走披露流程) | **批准**(预注册时点前移,堵"看完矩阵再声明"的污染;计算身份仍 universe 无关) | sync_catalog/注册表加必填列;存量 190 因子批量回填 univ_all(其历史矩阵证据视为已看,任何改域均按 post-hoc 处理) |
| ~~D6~~ | ~~入目录即全域体检~~ | **已由用户直接指令确定(2026-06-11),不再是决策点** — 见 §3.1b | 注册驱动一体化 + daily QA 缺域检查 |

---
*Review 通过后:D5/D4/F1 立即并行开工;F3 待 D1 批准。*
