# 因子 × Universe 耦合评估:设计与执行方案(供 Review)

> 版本:**Draft-7(终稿)**,2026-06-11 — **GPT 5.5 Pro Round-3 终判 APPROVE**
> (五项条件全部 RESOLVED,无阻断项)。Draft-7 = Draft-6 + Round-3 五项实施层建议
> (语义指纹三档归族 / external_prior 证据标准 / 统一 TaintLedger / 前瞻新鲜窗 /
> FactorSetClaim),见 §3.1c/§3.8/§3.4。设计评审关闭;待用户批复 D1-D7 后进入实现。
> 历史:Draft-6 = Round-2 五条件(taint 机械后果/idea-family 污染/max-stat 校准合同/
> F4 清理/薄域 fallback 删除)。Draft-5:**评估永远全域,无可选项**——
> discovery 与 formal 的每次评估一律覆盖全部 universe;"声明"只决定哪个域的 claim
> 享受未调整门槛,绝不决定评估范围)。Draft-4 内容:GPT 5.5 Pro Round-1 全部必改项,
> 裁决见 [universe_plan_cross_review_round1_response.md](universe_plan_cross_review_round1_response.md)
> (FactorDomainClaim 模型/探索台账/分层门槛/三字段分离/薄域硬地板/血缘强制)。
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
| P3 | **评估永远全域**(discovery 与 formal 每次评估覆盖全部 universe,无可选);事前声明只决定哪个域的 **claim** 用未调整门槛 | 用户指令 + WorldQuant 声明纪律(作用于 claim 而非评估范围) |
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

### 3.0b 域生命周期数据模型:FactorDomainClaim(Draft-4,源自 review §7)

因子定义与域声明彻底拆开:**FactorDefinition**(factor_id/expression/definition_hash,
universe 无关,不变)+ **FactorDomainClaim** 表(域生命周期的事实源):

```yaml
FactorDomainClaim:
  claim_id / factor_id / universe_id / hypothesis_id
  pre_registered_at          # 时间戳,与探索台账交叉验证
  status: draft_claim | candidate_claim | approved_claim | rejected_claim
  multiplicity_adjustment    # 本 claim 适用的门槛层(§3.3 表)
  lineage_taint_domains      # 继承自血缘的已观察域
  gate_evidence_id / sealed_oos_id
```

"approved 的是 claim,不是 factor"。向后兼容:`factor.status` = 其 primary claim
状态的**非规范化视图**(42 个调用点与既有写入门零迁移);7 域 discovery 矩阵永远是
独立的 EvidenceMatrix,不进任何 claim 字段。

### 3.1 入目录 draft(Draft-2 声明必填 + **Draft-4 血缘强制**)
表达式 `Ref(...,1)` 包裹入 factor_library → `sync_catalog` → draft。
**新增(必填):`primary_intended_universe`(单值)+ `secondary_universes`(可预先声明
多个,均预先计入多重检验)**;天然子域因子填 univ_all+覆盖说明。声明时间戳**必须先于
该因子的任何评估证据**——时序锁:声明(draft)→ 看全域矩阵(discovery)→ 申请门(formal)。
**Draft-5 澄清:声明不限制评估范围**——评估(discovery 与 formal)永远全域;声明只决定
哪个域的 claim 在门上用未调整 bar(§3.3)。
**Draft-4 血缘强制**:注册必须声明 `derived_from_factor_ids` +
`component_selection_basis(pre_registered|matrix_selected|external_prior)`;凡引用旧因子/
旧矩阵筛选结果的派生(含 clone:zscore 包裹、winsor 顺序微调等),**继承全部成分的
已观察域 taint**;无血缘声明不得进 formal 门;QA 以字段集重叠+表达式规范化相似度
检测疑似未披露血缘(clone 洗白与 composite 洗白的对冲)。
**设计边界(review 已确认)**:universe 进的是**生命周期声明**,不进**计算身份**——
表达式与 definition_hash 保持 universe 无关(P1:同一表达式在任何域评估,计算结果
不变;目录是复用库,绑域会致条目爆炸 + definition_hash 去重语义崩坏)。

### 3.1c Idea-family 污染记账(**Draft-6,R2 条件2 = Round-2 最大新发现**)
全域 formal 证据会**跨因子**污染:factor_A 的 microcap 在案结果启发研究者设计
factor_B(非 clone、不引用 A、表达式不同),直接声明 primary=microcap 享受原 bar——
这是 post-hoc 域选择,选择证据来自 A 的全域证据而非 B 自己的矩阵。对冲:

```yaml
ResearchIdeaTaint:
  research_family_id        # 想法族(QA 按字段集聚类 + 类别自动归族,非纯自报)
  domain_prior_source: external_prior | pre_registered_theory |
                       internal_evidence_matrix | prior_factor_formal_evidence
  informed_by_evidence_ids: [...]   # 启发本因子的在案证据(强制声明)
  idea_taint_domains: [...]         # 族内已观察域(自动并集)
  taint_effect: internal 来源 → post_hoc_max_stat
```

- **自动归族为默认,按语义指纹三档置信(R3-B1,防"泛 taint 拖死研究"与"换字段逃逸"两面)**:
  归族依据不是裸字段重叠,而是 `FactorSemanticFingerprint`(经济通道/特异字段组/
  算子骨架/持有期桶/中性化轮廓/目标域先验);基础字段(`$close/$vol/$amount/$total_mv/
  行业码`)为 **stopword——单独重叠不触发硬 taint**。三档:high(同机制+相近 horizon+
  相似表达式或明确成分关系)→ 自动继承族 taint;medium(共享关键字段组但机制不全同)
  → dashboard 提醒 + reviewer 确认/拆族;low(仅共享基础字段)→ 只记 relatedness 不 taint。
- **`external_prior` 证据标准(R3-B2,防"经济学故事"后门复活)**:要把 high/medium
  taint 降回 clean primary,须同时满足:①时间戳早于该族×域的首个内部证据;②内容
  具体(域+方向+持有期+机制+失效边界——"微盘股更容易有 alpha"不合格);③与本表达式
  构造直接相关。**`informed_by_evidence_ids` 非空时,external_prior 只能作解释材料,
  不能重置为 clean**。自报仅是补充,不是唯一防线。
- **域选择新鲜度是被消耗品(R2-C3)**:非声明域的 formal 证据不花 OOS 封条,但
  **花掉该(族×域)的域选择新鲜度**——对同因子、声明后代、矩阵筛选复合、以及
  `informed_by` 引用它的 idea-family 后继,全部产生 observed-domain taint。
  "没花 OOS"≠"以后还能装没看过"。
- **family 级记账**:testing ledger 在 (factor, universe) 之上增加
  (research_family_id, universe) 维度;批量注册低成本变体收割全域信号地图
  (domain lottery farming)会在族级账上立即显形。

### 3.1b 入目录即全域体检(**用户指令 2026-06-11,已定**)
**任何因子进入 draft 时,自动在当前全部 universe 上各评估一遍**(unified discovery
方法学 × 7 域,证据行按 (factor, universe) 落表)——出生证明即全域有效性档案。
- **执行形态**:注册驱动 = 一个事务序列「写目录 + `intended_universe` 声明 →
  sync_catalog → 自动触发 7 域 sweep」;声明时间戳天然先于全部矩阵证据,§3.1 的
  时序锁由机械流程保证而非自觉
- **守门**:daily QA 增加检查——任何现役 draft 在当前 methodology_hash 下缺任一
  域的证据行 → WARNING(不阻断注册本身;评估失败可重跑,身份不悬置)
- **探索台账(Draft-4,review §1)**:所有 sanctioned 评估入口(batch_screening /
  unified_eval / cicc_protocol 驱动)每次调用强制落账:expression_hash(规范化)×
  字段集 × universe × methodology × 时间;无 claim 上下文的运行标 `exploratory_tainted`。
  门复核时对声明域**自动检索**台账中相似表达式的历史评估并披露。
  **Draft-6(R2 条件1):taint 命中有机械后果,不止披露**——
  ```yaml
  if similar_exploratory_tainted_run_found:
    default_claim_class: post_hoc        # 自动降档,适用 max-stat 阈值
    reviewer_override: required          # 要回到原 bar 必须显式 override
    override_reason_required: true
    override_is_audit_event: true        # override 本身入审计账
  ```
  诚实边界:裸 pandas 不可技术性禁止——本控制的目标是"干净声明可被验证",非"作弊
  不可能";**表达纪律(R2-B1)**:门报告只能写"在当前审计覆盖下未发现 sanctioned 路径
  taint",不得写"无污染"。本系统评估几乎全走 sanctioned 工具,实际覆盖率高
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

### 3.3 IS 门 draft → candidate(**待批的合同修改,§8-D1;Draft-5 重构:全域评估+声明域裁决**)
- **Draft-5:每次门运行一律计算全部 7 域的 IS walk-forward 报告**(同引擎同口径,
  无可选项)。**评估全域,裁决按声明**:
  - 声明域(= draft 时的 `primary_intended_universe`)的结果用**原 bar** 裁决
    claim → candidate_claim
  - 其余 6 域的结果**自动落为 formal 证据**(自动类,status_power=none)——将来任何
    对这些域的 claim 申请天然属于 post-hoc(§3.3 分层表 max-stat 档),且其当时结果
    已在案,**披露由系统结构自动完成,不依赖研究者自觉**(GPT §1/§4 的最强对冲)
  - hypothesis prescription 的 `universe_id` 缺省 univ_all = 完全向后兼容,现有
    candidate 全部等价于"univ_all 域过门"
- 改声明域走显式变更流程——全域 formal 结果本就在案,变更申请须给新域经济学先验,
  按 post-hoc 档复核
- **Draft-4 分层门槛(review §2,"记账披露"升级为"bar 本身分层")**:

  | 场景 | IS 门 bar |
  |---|---|
  | 单一事前 primary 域(声明先于一切证据,无血缘 taint) | 原 bar |
  | 声明 k 个域(primary+secondary) | 按 k 调整(Holm 或置换 max-stat) |
  | post-hoc 改域 / 声明晚于矩阵 | 7 域 family **置换 max-stat** 阈值,或只能 evidence-only |
  | 存量回填 / clone / composite 派生 | 默认 7 域已观察,按 post-hoc 从严 |

  **校准合同(Draft-6,R2 条件3,版本化)**:域间强相关(univ_all 包含其余),
  Bonferroni/7 过度修正——以 **block permutation / block sign-flip 经验零分布的
  max-stat** 为准,且:置换单位 = 月/调仓周期(非 iid 日);统计量 = 与门裁决完全
  一致(heldout RankICIR + 符号一致性组合分);max 维度 = claim family 内全部已观察
  域;保留域嵌套结构、月度跨域协方差与因子可得性掩码;`calibration_methodology_hash`
  + 阈值版本入库。**190×7 真实回填矩阵不得直接当 null**(含真 alpha/同源因子/历史
  选择偏差)——只用于估计相关结构与 sanity check;null 必须来自标签置换/区块符号
  翻转等破坏 alpha 关系但保留依赖结构的过程。Bonferroni 仅作无置换条件时的保守上界
- **Draft-4 薄域硬地板(review §5;不满足 → 该域只能 discovery/evidence-only)**:
  `valid_names_total_p10 ≥ 300 · min_decile_count_p10 ≥ 30 · 两腿 effective_N_p10 ≥ 25 ·
  腿内行业集中度 p90 ≤ 35% · block bootstrap 单位 = 调仓周期(非 iid 日)`。
  如实后果:univ_microcap 与 univ_liquid_top300 在地板线上为边缘域,逐因子覆盖率
  决定能否承载 status-bearing claim
- 判据不变:heldout RankICIR + 符号一致性(每域在掩码后截面上计算)
- candidate 记录 `gated_universe`;dashboard 状态徽章旁标注域(如 `candidate@微盘`),
  详情卡展示全部 7 域的门运行结果(声明域高亮,其余标"在案,未裁决")
- **命名纪律(R2-C4)**:非声明域结果对外绝不暴露为 `formal_pass@域`——必须是
  `automated_formal_method_evidence@域` + `claim_adjudicated: false` +
  `future_claim_default: post_hoc_max_stat`。"formal"只能描述方法学口径,
  不得暗示通过了 formal 门
- **多重检验纪律**:同一因子在第 2 个域申请过门 = 新检验,testing ledger 按
  (factor, universe) 记账;**禁止结果驱动换域**(在 A 域失败后换 B 域申请,须在
  hypothesis 里披露 A 域的失败记录,门复核时可见)
- (Draft-6 删除旧"<200 只附 CI 即可"软护栏——硬地板是入场券,bootstrap CI 只是
  附加诊断,不构成 status-bearing 资格;语义由上方硬地板条目唯一定义)

### 3.4 sealed OOS candidate → approved(机制不变,激活既有字段;**Draft-7 补选集层**)
`FrozenSelectionSet` 冻结身份**本就含 universe** —— 声明域写入冻结集,封条按
(选集+域) 花。无代码改动,只是从"从未用过非全市场"变为"按声明域使用"。
bar 不变(rank_icir 同号 + LS Sharpe>1.0,decile 口径)。
**R3-B5(因子组/策略选集启用前必须实现)**:跨域选集(如"微盘 IS 强 ∧ 成长域不崩"
挑出的 5 因子组)的封条身份必须包含**选择所用的全部域**——`FactorSetClaim`:
`selected_factor_claim_ids + selection_evidence_ids + selection_domains(全部!)
+ deployment_universe + selection_methodology_hash`。只冻结 5 个 factor_id +
部署域会把 growth 域的选择偏差藏出账外。复合部署域(微盘∩成长)须生成 PIT-safe
`composite_universe_hash` 正式域,不得写成两个普通域的并列说明。

### 3.5 approved 的域语义(**Draft-4 重写:三字段分离,review §3;原 validity_domains 撤回**)
原案把 OOS 验证域与 evidence-only 域混入同一 `validity_domains` 字段——中间层丢标签
即等于绕过封条(`if target in validity_domains` 失败场景成立)。改为:

```yaml
approved_scope:
  oos_validated_domains: [...]    # 唯一来源 = approved_claim;生产 resolver 只读这里
domain_evidence:                   # 描述性矩阵投影;status_power=none;含 post_hoc 标记
  descriptive_pass_domains: [...]
deployment_policy:
  allowed_domains: [...]           # 默认 = oos_validated_domains
```

evidence-only 域要进策略:prescription 显式 `allow_descriptive_domain_evidence: true`,
且该策略默认 research-only,不得直接进部署门。

### 3.6 部署门(不变)
事件驱动 + 真实成本 + 1× + 目标域(通常 univ_liquid_top300 或基准域)。

### 3.6b 统一 TaintLedger 与 claim 档位解析(**Draft-7,R3-B3:五类 taint 一个状态机**)

实现上**不做五套独立状态机**——exploratory/lineage/成分选择/idea-family/非声明域
formal 证据全部写入一个 `TaintLedger`(source_type 区分),门裁决只调一个函数:

```yaml
TaintLedgerEntry:
  source_type: exploratory_eval | lineage | component_selection |
               idea_family | non_primary_formal_evidence | manual_override
  factor_id / research_family_id / universe_id / observed_at / evidence_ids
  taint_effect: none | disclose | post_hoc_max_stat | block_status_claim
# 裁决:claim_class = resolve_claim_class(factor, family, universe, pre_registered_at)
# 输出仅四档:clean_singleton_primary | predeclared_multi_domain |
#           tainted_post_hoc_max_stat | evidence_only_not_status_bearing
```

**实施 MVP 顺序(R3 终判给出的防护价值/成本比)**:①三字段域语义 + F4 生产 block;
②TaintLedger + claim_class resolver(归族第一版只做 high-confidence + medium-review);
③薄域硬地板 + max-stat 校准 schema 先落库(置换引擎稳定前,非 clean claim 用保守
上界或 reviewer-block,**绝不退回"只披露不调门槛"**)。

### 3.6c 新鲜度终局与前瞻恢复(**Draft-7,R3-B4**)

全员全域评估的自然终态:成熟族(反转/动量/流动性/规模/价值)终将在全部 7 域"已观察",
clean singleton primary 趋于稀缺,max-stat 档成为常态——**这是设计终态,不是缺陷**
(置换 max-stat 在有效独立域 ~2-3 下不等于"全员死刑")。**禁止 taint 随时间衰减**
(统计污染不是过期记忆)。唯一合法恢复 = **前瞻新鲜窗**:

```yaml
ProspectiveFreshWindowClaim:
  fresh_window_start: max(内部证据标签终点, taint 观察点标签终点) + embargo
  evaluation_window: 仅 fresh_window_start 之后的新标签
  historical_evidence_use: descriptive_only   # 旧窗口永远只是背景
  claim_class: prospective_clean | prospective_post_hoc
```

12-24 个月新标签自然到来后,成熟族可开 prospective-only claim 用纯新数据裁决——
历史不洗白,但系统不会永远无法给成熟族产生新 status-bearing 证据。

### 3.7 横截面变换的归一化域(Layer-1.5,Draft-3 review 补充)

市值/行业**横截面**归一化(中性化残差、cs 排名、标准化)有一个隐藏参数——归一化
样本。规则(Barra 估计域范式):

- **因子身份层**:目录内任何含横截面变换的因子(市值中性化、行业相对复合),
  归一化一律在**固定估计域**(univ_all 过剔除屏)上做,算一次、值唯一、
  universe 无关,definition_hash 锁定。逐股缩放(如 /自身市值)不涉横截面,
  纯 Layer-1,无此问题。
- **Draft-4(review §4):`neutralization_weighting` 为显式哈希参数**——新建身份层
  中性化因子默认 `sqrt_float_cap` WLS(等权回归的斜率被小票数量主导,残差在大盘/
  流动域携带残留 size/流动性倾斜);存量 EW 因子不静默重定义,作命名变体
  (`ew_univ_all` vs `sqrt_cap_univ_all`)。**门报告增加硬暴露审计**:因子值对
  ln_mcap / 行业哑变量 / ADV / 上市年龄在**目标域内**的残留暴露须低于阈值,
  否则不得声称 size/industry-neutral alpha。
- **评估诊断层**:unified_eval 的"中性化 IC"在**评估域内**重新回归
  (EvalMethodology 旋钮,进 methodology_hash)——它回答"X 域内部扣掉 X 域
  自己的尺寸/行业结构后还剩多少信号",与上一条是**不同的问题**,名字必须分开。
- 现状:目录的行业相对复合已是全市场计算(合规);unified_eval 中性化 IC 目前
  为全市场样本 —— **F1 实现按域评估时,诊断端切换为域内样本**(实现项)。

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
| **F4** | approved 三字段域语义(§3.5)+ 生产 resolver 硬规则 | claim 表 + resolver:目标域 ∈ oos_validated → allow;仅 ∈ domain_evidence → **block**(除非 research-only override,且 override 不得进部署门) | 生产路径无 warn-and-pass;research override 可审计 | F2 |
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
4. (Draft-6 改写)三字段分离后误读风险移至实现层:生产 resolver 必须 block
   evidence-only 域(非 warn 后放行),F4 验收项;命名纪律见 §3.3(R2-C4)
5. 全市场缺省保证了零迁移成本:不声明域 = 现状行为,所有存量 candidate/approved
   语义不变(等价于 gated_universe=univ_all)

## 8. 待你批准的决策点

| # | 决策 | 推荐 | 影响 |
|---|---|---|---|
| **D1** | IS 门接受事前声明域(§3.3) | **批准(GPT 条件版)**:singleton primary 用原 bar;多域/post-hoc 按 §3.3 分层表调门槛;门前 7 域矩阵必须已存在 | factor_lifecycle 合同修改 + 分层 bar |
| D2 | evidence-only 域策略引用 | **原案撤回(GPT §3)**:三字段分离;生产 resolver 只认 oos_validated_domains;显式 override 仅 research-only | §3.5 重写 |
| D3 | discovery 矩阵 7 域全开 | 批准,**但全开即制造 observed-domain taint**——此后任何域选择按 7 域 family 处理 | 写入 §5 规则 |
| D4 | 换域披露 | 批准并升级(GPT §1/§6):探索台账 + 血缘 + 成分选择全部机器可审计,不止 hypothesis 文本 | 台账 + lineage 字段 |
| **D5** | draft 必填声明 | 批准修订版:`primary_intended_universe` 必填(单值)+ `secondary_universes` 预先计入多重检验;存量 190 回填 univ_all 且 7 域视为已观察;派生因子继承 taint | sync_catalog 必填列 + claim 表 |
| ~~D6~~ | ~~入目录即全域体检~~ | **已由用户直接指令确定(2026-06-11)** — 见 §3.1b | 注册驱动一体化 + daily QA 缺域检查 |
| **D7**(Draft-4 新增) | FactorDomainClaim 数据模型(§3.0b)取代散落的 gated_universe/validity_domains 元数据 | **批准建议**(GPT §7 部分采纳:claim 表为域生命周期事实源,factor.status=primary claim 视图,零迁移) | 注册表加 claim 表 |

---
*Review 通过后:D5/D4/F1 立即并行开工;F3 待 D1 批准。*
