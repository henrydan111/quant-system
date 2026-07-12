# 新闻快讯接入设计 v1.12(NF 波次 + 宏观席 + 新闻价值提取增强)
**v1.6 主体 APPROVED(round-6);§6b/§6c/§7 v1.12 = round-11(0B/3M/0m,GPT:完成即无进一步设计缺口)全采纳,待 round-12 终门**

状态:**APPROVED FOR IMPLEMENTATION**(GPT round-6 对 f86543f:0B/0M/1m 编辑项,R2=可以开工;前向证据与 macro weighted 另行授权——见 §4 哈希绑定清单)。⑧round-6 Minor(规范性优先级横幅)已落;selection_rule 除 id 外其**不可变政策内容哈希**须由会话档案/绑定与链 manifest 携带(round-6 追加处方,已入 §0d)。⑦GPT round-5(v1.5/d7b0d06):CHANGES REQUIRED
0B+2M——§0a 残留被取代的填充语义与 §0d 竞争权威 + M6 分母/结果合同未机械单一化;
全采纳,含其 R2 严化裁定(同 cutoff 不打破平局 = 完整性违规)。裁定史:①用户:快讯必须进决策框架 + 硬性噪音去除;
②用户:宏观/市场流是数据资产 → 第四席 + 逐股传导(v1.1);
③GPT round-1(v1/0958b07):CHANGES REQUIRED 4B+6M+2m,全采纳(§0);
④GPT round-2(v1.2/d843e55):CHANGES REQUIRED 3B+6M+2m,全采纳(§0b);
⑤GPT round-3(v1.3/4437185):CHANGES REQUIRED **0B**+3M+2m——晚间决策声明关闭
round-2 B1/B2;**B3 热修获准立即开工**(R5);三 Major 全采纳(§0c);
⑥GPT round-4(v1.4/b6bb084):CHANGES REQUIRED 1B+2M+1m——多决策会话生命周期
(与前向单发布规则冲突)+ macro_coverage_policy 入契约 + §6 传播,全采纳(§0d)。
实现前置:B3 热修先行(已获准,持续有效);其余待 GPT round-6 通过。

## §0d GPT round-4 处置表(全采纳)+ 决策谱系与成交绑定合同(B1)

| # | 发现 | v1.5 处置 |
|---|---|---|
| B1 | **刷新与"单发布决策"规则冲突**:前向合同禁止同 cycle 二次决策,fill resolver 取首个已发布 attempt——节假日刷新会变成未密封的事后择优 | 见下方**决策谱系合同**(GPT 处方逐条落地) |
| M1 | 档案封值只证"没被改",不证"算对了"——错误实现可封错误权重并复现自己的错 composite | **`macro_coverage_policy` 版本化入 scoring_contract**:formula_id/最低覆盖率 0.60/有效配对定义/基础权重 {fund .35, tech .25, news .30, macro .10}/not_applicable 政策/生效权重公式/舍入阶段与精度/`macro_deployment_mode ∈ {shadow_only, weighted}`/M6 覆盖阈值。规范公式:`Vᵢ` = mapping_status=mapped 且有注册 M·MF↔MS 有效证据对的维度集;`coverage_ratioᵢ = Σ_{d∈Vᵢ} w_d / Σ_{d∈D} w_d`;<0.60 → `macro_status=not_applicable` 且 **`macro_final=null`(绝非 0)**;适格时按有效维公式;macro 只在 `applicable ∧ weighted` 时入席集;`effective_weightᵢ,ₛ = base_s / Σ base_适格席`(无 macro ≈ .3888889/.2777778/.3333333/0);全精度计算、**声明的最终阶段一次舍入**;**verify_archive_semantics 从封存的原始维度/映射/证据记录重算**覆盖率/状态/macro final/生效权重/composite——不信封值 |
| M2 | §0c 的 target 级 scoring_owner 正确,但 §6 仍是被取代的全局归属旧文 | §6 已替换为完整规则(见 §6);§7 增 target 级/混合主张拆分/重复 owner/cutoff 版本回归测试 |
| m1 | MS 字段与确切缺席 cutoff 只在处置表、未进操作性 §6 | §6 MS 行 schema 补全:`mapping_id/mapping_version/mapping_sha256/mapping_status/exposure_type/exposure_bucket/exposure_value/snapshot_effective_at/目标代码/维度/来源`;`mapped_no_exposure → exposure_value=null`(不造 0);缺席渲染必带 `confirmed_absent_through=<确切通道 cutoff>`,测试拒绝暗示整晚覆盖的措辞 |

**决策谱系与成交绑定合同(B1 处方逐条):**
- 首个会话前冻结 `fill_intent_id / fill_trade_date / fill_open_at / binding_cutoff_at`;
  刷新**不得**把交易滚到另一个开盘;
- `decision_session_id` 与技术重试 attempt 分离——"单发布 attempt"规则作用于
  **会话内**,不作用于整个 fill intent;
- 每个会话档案不可变;**新**档案封 `supersedes_session_id`(向前指);
  **绝不回写旧档案**加 superseded_by——追加 `decision_superseded` 事件到
  append-only 谱系账本,UI 从账本派生视图;
- 在预注册 `binding_cutoff_at` **自动**选择:已完整密封、`macro_flash_cutoff_at`
  最大、且 `fill_open_at − macro_flash_cutoff_at ≤ 18h` 的会话;
  **无人工选择、无按分选择、无陈旧回退、无自动顺延**;无适格会话 → 封
  `fill_skipped`;
- 开盘前写并密封 **`fill_binding.json`**(fill_intent_id/选中 session_id/档案封印
  哈希/cutoff/龄/选择规则 ID **及其不可变政策内容哈希(round-6 追加)**/binding_at),哈希钉入账本并进链 manifest;`record_fills`
  **只消费该绑定**。

---

## §0a 决策时间线声明(round-2 B1/B2 的根因是本文档从未钉死它;现予声明并机械化)

**本系统唯一支持的决策模式 = D 收盘后晚间决策,次一开市日开盘执行**(与既有重放
语义、前向 MVP「晚间决策」完全一致;**不存在"D 早盘用 D 收盘卡"的模式**——GPT
round-2 按盘前决策模式推导的 lookahead 在声明后不成立,但其全部机械断言照单落地):

- **市场日与决策日历日解耦(round-3 M2;round-5 M1 修正:填充权威唯一化)**——
  逐档案封存:`market_asof_trade_date = 发布前最近开市日`(行情/M 卡锚);
  `decision_calendar_date = 新鲜晚间运行的日历日`(快讯锚);
  `macro_flash_cutoff_at = decision_calendar_date 当晚 cutoff`;
  **`fill_trade_date`/`fill_open_at` 属于预冻结的 `fill_intent_id`——任何决策会话
  不得从自身发布时间派生、更改或顺延它们**;
  **会话发布只产生不可变审计工件,不授予任何执行权;执行权唯一来自密封的
  `fill_binding.json`**(§0d);
  **18h 规则作用于绑定适格性而非发布**:超龄会话保留归档但不适格;无适格会话 →
  绑定器封 `fill_skipped`——0205 开盘绑定 0204 晚会话(0127 晚会话留档不适格),
  春节 8 天新闻不再被忽略;
  **绑定边界不变量**:发布事件与有效档案封印事件都须在 `binding_cutoff_at` 前
  落账;`binding_at < fill_open_at`。
- **四时间戳因果链(B2 处置,机械断言 + 违反即终态失败)**:
  `input_cutoff_at < pipeline_frozen_at <= attempt_started_at <
  decision_published_at < fill_open_at`。
  **成员 `effective_at ≤ input_cutoff_at`;管线完成 ≤ `pipeline_frozen_at`**
  (round-3 m1 措辞修正:查询窗止于 cutoff,抓取/分型/覆盖终查在 cutoff 之后、
  冻结之前完成);`input_cutoff_at` 显式定义 = 各通道 cutoff 的最晚者(通常 =
  macro_flash_cutoff_at);水位线只在全部子窗与管线记录落盘后推进;
  **盘前门用实际 `decision_published_at`** 对照 fill_open_at,错过 = 终态失败;
  预注册 p99 延迟预算(晚间模式小时级,65.5min 链实测宽裕)。
- 硬失败断言(发布侧):market_asof_trade_date ≠ 发布前最近开市日 / 任一成员
  effective_at 超其 cutoff / decision_published_at ≥ fill_open_at → 拒绝发布
  (flash 超龄**不再**是发布拒绝理由——它是绑定不适格理由,round-5 M1)。
- **绑定唯一性与竞态合同(round-5 R2 裁定,替代任何平局规则)**:适格已发布会话在
  `(fill_intent_id, macro_flash_cutoff_at)` 上**强制唯一**;技术重试属于会话内
  发布前;已发布档案**永不**技术性重封;同 cutoff 两个适格会话 = **完整性违规**,
  封 `fill_skipped(reason=duplicate_cutoff_sessions)` + 审计事件;发布或封印
  账本事件未在 binding_cutoff_at 前落账的会话不适格(无论其 flash cutoff 多早);
  会话发布与绑定在**同一 fill-intent 锁**下执行,墙钟相等由 append-only 账本
  序号裁决;余下唯一适格会话中取最大 `macro_flash_cutoff_at`。

> **规范性优先级:§0a、§0d、§5、§6 为 v1.6 唯一现行合同;§0、§0b、§0c 处置表仅作历史审计,任何冲突文字均视为已取代,不得生成实现规则。**

## §0b GPT round-2 处置表(历史审计)

| # | 发现 | v1.3 处置 |
|---|---|---|
| B1 | M01-M16 是当日收盘卡,盘前用 = lookahead | §0a:声明晚间决策唯一模式(收盘卡合法);四字段封存 + M 卡日期/成员 cutoff 硬断言全部照 GPT 处方落地;盘早模式不受支持,若启用必须回到 GPT 的 D−1 锚 |
| B2 | cutoff/冻结/发布时间线因果不可能 + 现行 forward runner 用 attempt 开始时间充当发布门 | §0a 四时间戳链 + 实际发布时间做盘前门 + 错过终态失败 + 水位线落盘后推进 + p99 预算预注册 |
| B3 | **逐股传导没有机械接地**:宏观席只引 M/MF 行,股票标签无证据 ID——可对 149 股发同一泛化分而过全部围栏 | **MS01-MS05 维度专属股票暴露行**(as-of:股票代码/适用行业·概念·风格暴露/来源/生效日);**配对证据规则**:每个传导分 ≥1 条 M/MF 宏观事实 + 对应 MS 暴露行;无适用暴露行 = **no-score**(不得给泛化市场分);维度专属 MS 行避开两遍独占误杀;`macro_card_snapshot_id`+逐股上下文哈希+生成 ID 注册表+ts_code 封入输入指纹与档案 |
| M1 | 宏观证据类未具体化 | **MFD/MFI/MFA/MFR** 四类(与 NF 同法;宏观传闻/操纵正向上限 0,只喂罚分/空头);政策细节行给注册宏观 ID,不依赖聚合 M16 行;证据类作为**不可变属性进生成 ID 注册表** |
| M2 | 带符号政策暴露在正向分 schema 下歧义(受损 5 分会加分) | 单维 **`policy_alignment` 居中评分**:0-1 实质受损 / 2-3 中性混合 / 4-5 实质受益;无适用证据 = no-score;**不拆两维**(防同一政策事实双计权) |
| M3 | 同一事实经 news 与 macro 双席双计 | 每个事实修订在每个 cutoff 有唯一 **`scoring_owner`**:发行人直接事实 → news;系统性广谱事实 → macro;非 owner 席可作上下文消费但**不得计分**(渲染标注);多路展示保留 |
| M4 | 股票标签束缺 PIT/覆盖合同(THS 概念是当前快照) | 每个标签束带 `snapshot_effective_at`+内容哈希;**历史诊断无同期 THS 快照时省略概念标签**(不得拿今日成员套 2025);风格/β 用 D 收盘输入(晚间模式);标签与暴露映射哈希入 C16b;**confirmed_absent 需端到端覆盖**(抓取完成+原始行对账+分型完成+路由终态+无失败 LLM 批次),仅抓取完成不够 |
| M5 | M6 门不可机器判定 | 冻结数值线(标注前):直接实体挂钩精度 ≥98%;宏观/行业路由精度 ≥95%;残余同事实重复 ≤5%;传闻/操纵入正向证据 =0;PIT/注入违规 =0;必需覆盖 =100%;**双独立标注 + 仲裁 + 留存分歧率**;M6 仍是读质量门,不是收益预测证据 |
| M6 | 未测量且相关的新席 20% 权重过高 | 采纳 GPT 建议先验:**fund 0.35 / tech 0.25 / news 0.30 / macro 0.10**(待用户终裁);M6 只授权席位运行、不授权加权;试 0.20 = 新 C16b 候选 + 新评分契约 + 链 bump,且须在观察其评判收益窗**之前**申报 |
| m1 | 「情绪位置」与技术/消息重叠且无拥挤度输入 | 第五维改为 **`external_shock_transmission`**(利率/商品/汇率/地缘外部冲击传导);拥挤度留待有确定性输入后另议 |
| m2 | 完整性核心席位无关但外围代码不是;数据字典义务 | 加**四席端到端测试**(prompt 表/执行环/证伪域/卡装配/平台展示/重算);fetcher 动工前把 news 端点契约写入 [data/data_dictionary.md](../../../data/data_dictionary.md),采集后更新 data_tracker(§6.1 家规本就要求,纳入清单) |
| R6 | B3 是现行链活漏洞 | **裁定采纳:B3 窄热修先行**(净化+ID 注册表+席位域+对抗测试,独立链 bump);热修落地前 chain_v3.0 不执行任何运行(当前无计划任务、重放已停,敞口为零;恢复运行必须先热修)——**round-3 R5 已获准立即开工** |

## §0c GPT round-3 处置表(0 Blocker;3 Major + 2 Minor 全采纳)

| # | 发现 | v1.4 处置 |
|---|---|---|
| M1 | **no-MS → no-score 把映射缺口变成看空信号**:无分维度贡献 0,映射稀疏的小盘股宏观分被系统性压低 | **不加分数地板**(那是造证据)。`mapping_status ∈ {mapped, mapped_no_exposure, unmapped}`;`coverage_ratio = 有效配对维度权重 / 宏观总维度权重`;覆盖 ≥ **预注册 0.60** → 宏观 final 按有分维度归一:`macro_final = 100×Σ(w×s)/(5×Σw_有效配对维)`;低于线 → **`macro_status=not_applicable` + 其余三席 composite 权重确定性重归一**(绝不用宏观 final 0);`coverage_ratio`/`macro_status`/生效 composite 权重**封入档案**供完整性重算;**M6 增映射覆盖线**:宏观席适格率总体 ≥90%、每个市值五分位 ≥80%、五分位最大-最小差 ≤15pp,否则宏观席 shadow-only |
| M2 | **晚间锚在周末/长假产生陈旧情绪决策**(0127 决策 0205 成交,8 天新闻被忽略——顶撞短期情绪命题) | 市场日与决策日历日**解耦**(§0a 重写):market_asof=发布前最近开市日,快讯 cutoff 在 decision_calendar_date 当晚,fill=发布后下一开市日;**`max_flash_age_at_fill ≤18h` 预注册**,超龄在复市前最后日历晚重跑或弃单——0205 开盘用 0127 市场卡+0204 晚快讯 |
| M3 | **scoring_owner 必须按目标股细化**:中芯出口管制头条对中芯是直接、对半导体同业是系统性——全局归属任一席都丢一半 | **`scoring_owner(claim_id, target_ts_code, cutoff)`**:target 在 subject_codes 中显式点名 → news 所有;经批准的系统性暴露触达的同业 → macro 所有;一文含直接+系统两类主张 → 拆**原子 claim_id**(共享 fact_cluster_id);每 (claim, target) 恰一席可计分;**重复所有权硬失败**(不用折减兜底——折减会掩盖所有权错误) |
| m1 | §0/§3 残留"cutoff 前完成全部拉取"旧措辞,与 §0a 正确时序矛盾 | 全文统一为:成员 `effective_at ≤ input_cutoff_at`;管线完成 ≤ `pipeline_frozen_at`;`input_cutoff_at` 显式定义 = 各通道 cutoff 最晚者(已改) |
| m2 | MS 行字段不足;缺席行未标注确切 cutoff | MS 行增 `mapping_id`/映射版本哈希/`mapping_status`/暴露类型/可测时的暴露档位·值;缺席行显示确切 cutoff(「截至 18:00 确认无」),不得暗示覆盖整晚 |

## §0 GPT round-1 处置表(全采纳,零拒绝)

| # | 发现 | v1.2 处置 |
|---|---|---|
| B1 | **佐证回填 = lookahead**:簇保最早 visible_at 却带最终 n_sources——后到的转载让早先决策"提前知道"佐证 | 簇改**append-only 修订版本化**:成员各带 `effective_at=max(source_published_at, first_ingested_at)`;`cluster_first_visible_at` 与 `cluster_state_effective_at` 分开存;每个新到源 = 新簇修订;检索取 `cluster_state_effective_at <= cutoff` 的最新修订;n_sources/novelty/importance 只用 cutoff 前可见成员 |
| B2 | **固定 5h 抓取窗有覆盖洞,缺席声明不安全**:漏日间/隔夜流;1500 触顶截断;零行可能是权限而非无新闻——却仍渲染「无池内快讯」 | **每源成功水位线**,从 `watermark−overlap` 抓到决策 cutoff;响应触 1500 递归二分时间窗(分钟级源用重叠边界);成员 effective_at ≤ input_cutoff_at,管线完成 ≤ pipeline_frozen_at(覆盖终查在 cutoff 后运行);写**源×窗覆盖清单**(查询窗/行数/触顶/状态/原始载荷哈希);**缺席三态**:`confirmed_absent`(唯一可作证据)/`coverage_incomplete`/`source_unavailable`;**cls 保持 disabled(非 required)直到权限与覆盖验证** |
| B3 | **不可信标题伪造机械合法证据行**(已在现行链复现:标题含换行+`- [F01]`,line_map 把伪造 F01 注册为合法行;news 席无席位-ID 域限制) | raw 原文只留审计档;渲染前 **Unicode 规范化 + 剥 CR/LF/控制符/零宽符 + 折叠空白 + 中和证据 token 模式**;渲染器返回**显式生成 ID 注册表**,校验器只对注册表校验、不从卡片文本重新发现 ID;**席位-ID 域强制**(news 只能引 news 域 ID,fund 只能引 F 域……);对抗测试:换行/`[F01]`/`[NF99]`/指令注入/控制符 |
| B4 | **转载洗白操纵**:四站转同一 PR/通稿/黑嘴 ≠ 四个独立确认;改写话术绕词表 + 转载得 n_sources>1 绕单源封顶 → importance 5 | `n_outlets`(展示)与 **`n_independent_sources`(计分)分离**;同措辞/同时序/同署名/同源头 = 一个**源家族**;独立性无法确立 → **默认 1**;多站转载**永不清除**操纵/未证实旗;确定性操纵特征 + 分型化识别(紧迫话术/保收益/加群邀约/匿名信源/推广祈使);冻结带标注对抗集(含改写+转载黑嘴) |
| M1 | 传闻与事件语义混在一个 enum | 三维分离:`event_type`(订单/产品/融资/异动/政策…)× `verification_status`(官方证实/署名媒体/未证实/传闻/观点)× `content_kind`(事实/行情/评论/推广);传闻入专属 **NFR## 隔离/风险节**,可喂罚分与空头,**不得支撑正向 factor_scores**;不走 NDA-only(会洗掉来源) |
| M2 | 一刀切 NF 钳位与产品命题冲突 + 现行"任一被钳 ID 钳全维"算术会误伤 | **证据类分级**:`NFD##` 已证实直接事件(上限 5)/`NFI##` 间接·单媒体(上限 3)/`NFA##` 聚合(上限 3)/`NFR##` 传闻·操纵(正向上限 0);维度上限 = **所引证据中最强合格类**的上限,替换"任一钳全钳" |
| M3 | bin 事件与盘面异动快讯双 ID 重复计分同一事实 | 双模态都保留,共享 **`fact_cluster_id`**;结构化事件一旦可见即权威;独占在 fact_cluster_id 级强制;卡片倾向合并行「NF 首报;后经结构化数据证实」 |
| M4 | 跨市场别名不能用无日期词典 | **独立审批的版本化别名注册表**:发行人 ID/被提及工具/映射 A 股/市场/别名类型/valid_from-to/来源/置信度/歧义态;歧义 fail closed;卡片保留「提及 00981.HK,映射至 688981.SH」而非把 H 股行情改写成 A 股;注册表版本/哈希进检索候选与链 manifest |
| M5 | 审计与治理记录不足 | 一等字段:`raw_event_id`/`cluster_id`/修订号/effective 时间/成员源/route/verification/操纵特征;**append-only 管线运行清单**:每源每级 `input = kept + 终态丢弃原因` 对账;**冻结哈希全集**:源表分层/过滤器/黑嘴规则/去重阈值/别名注册表/分型模型+prompt+schema/新颖度规则/配额/渲染器/校验器/决策 cutoff——全部注册进 **C16b CandidateID**(不只是检索通道权重);PREREG 落到精确工件 [workspace/research/mvp_pool_book/FORWARD_PREREG.md](../mvp_pool_book/FORWARD_PREREG.md) + 更新配置哈希 |
| M6 | 3-4 日不构成客观读质量门 | 看结果**之前**冻结 300-500 条分层盲审样本(跨源/直接·行业/重复/传闻/操纵);硬阈值:PIT 与证据行注入违规 = 0;必需源覆盖 100% 否则硬失败;传闻/操纵入正向直接证据 = 0;实体挂钩高精度且歧义拒绝;配额与 enum 确定性;残余重复率/误报率有记录。with/without 日仅作诊断,**不得**用于调阈值或性能声明 |
| m1 | 3 日指纹衰减会压掉真更正 | as-of `story_id` + `update_kind ∈ {重复, 新事实, 更正, 官方证实}`;更正/证实不降权 |
| m2 | 源分层无实测依据;cls 零行不能 T1;Tushare 响应不含 src 字段 | 分层基于**实测可靠性证据**(建库期收集);查询源显式打戳(我方注入列,采样探针已如此);cls 降为 disabled 待验 |

## §1 采样评估(2026-07-11 实测,不变)

2,012 条/24h(sina 884/10jqka 443/eastmoney 361/wallstreetcn 324;cls 0——**disabled 待验**);
跨源粗重复 18%;秒级时间戳(10jqka 分钟级 → 水位线用重叠边界);正文中位 119-148 字;
个股可挂钩 ~7%,宏观/行业/市场流 ~93%(→ 三路路由,§2.4)。`src` 为我方注入列
(Tushare 响应无此输出字段,m2 已记)。接口文档 143 已读(§6.1 合规)。

## §2 管线 v1.2(按序;每级淘汰进运行清单对账,绝不静默)

1. **抓取层(B2)**:每源成功水位线;`[watermark−overlap, cutoff]` 抓取;1500 触顶递归
   二分;源×窗覆盖清单(窗/行数/触顶/状态/载荷哈希);全部必需源完成才冻结决策输入;
   缺席三态。
2. **净化层(B3,渲染边界)**:raw 原文进审计档;进卡文本一律 Unicode 规范化、
   剥控制符/零宽符/CR-LF、折叠空白、中和 `- [XX##]` 型证据 token;渲染器输出
   **生成 ID 注册表**,校验器只认注册表;席位-ID 域表(fund→F/FS/FD/FB,tech→T*,
   news→N*/NF*,macro→M*/MF*)。
3. **确定性预过滤**:长度域;栏目黑名单;**黑嘴确定性特征**(紧迫/保收益/加群/
   匿名荐股/推广祈使,版本化规则)硬丢弃(进对账)。
4. **簇化(B1+B4)**:规范化指纹聚簇;**append-only 修订版本化**(B1 处置);
   `n_outlets` 与 `n_independent_sources` 分离,源家族判定(措辞/时序/署名/源头),
   独立性不明默认 1;操纵/未证实旗**不因转载清除**。
5. **三路路由**(v1.1,不变):个股路(经 M4 别名注册表,歧义 fail closed)→ NFD/NFI;
   行业/概念路 → NFA 聚合;宏观路 → 宏观卡 MF;真垃圾(黑嘴/娱乐/无信息)→ 终态丢弃。
6. **quick-LLM 分型(M1)**:`event_type × verification_status × content_kind` 三维
   (注册 enum,fail-closed)+ 宏观路 `macro_type`;操纵特征分型辅路(B4);
   importance_0_5;`story_id`+`update_kind`(m1)。
7. **卡片渲染 + 证据类围栏(M2/M3)**:NFD(≤5)/NFI(≤3)/NFA(≤3)/NFR(正向 0,
   专属风险节);维度上限 = 所引最强合格类;`fact_cluster_id` 级独占(M3);
   缺席声明只在 `confirmed_absent` 时渲染。
8. **评分护栏**:NFR 不支撑正向分(机械);传闻/操纵旗事件自动入空头证伪素材。

## §3 PIT 合同

- 成员级 `effective_at = max(source_published_at, first_ingested_at)`;簇修订 as-of 检索
  (B1);成员 effective_at ≤ input_cutoff_at,管线完成 ≤ pipeline_frozen_at(B2/round-3 m1)。
- **history_bulk 物理隔离**(R2 裁定):历史批次存独立目录 + 消费端强制的证据类标记,
  不与前向流混储;重放消费历史批次 = NON_EVIDENTIARY(本就如此)。

## §4 治理

- **C16b CandidateID 指纹全集**(M5):管线全配置哈希(见 §0 M5 行)+ 检索通道 +
  别名注册表版本 + 分型 prompt/schema;链版本 bump(SEAT_WEIGHTS/COMPOSITE_W/新卡/
  新 prompt 全进冻结契约);前向前并入 **FORWARD_PREREG.md(精确工件)**。
- 量与成本:管线后 ~100-300 条/日入库;分型 lite/mini ≈ 100-200 AFP/月,可忽略。

## §5 读质量门(M6 完整合同,round-5 M2 整合为唯一权威表;替代全月重放)

分层 3-4 日(涨停潮/大跌/平静/节前)集成验证。**两类指标、两个冻结分母**:

| 指标类 | 分母(冻结并封存) | 阈值 | 不过的后果 |
|---|---|---|---|
| 人工精度类(双独立标注+仲裁,留存分歧率) | **冻结的 300-500 条分层盲审样本**(跨源/直接·行业/重复/传闻/操纵,看结果前抽定) | 直接实体挂钩精度 ≥98%;宏观/行业路由精度 ≥95%;残余同事实重复 ≤5%;传闻/操纵入正向证据 =0;PIT/注入违规 =0;必需覆盖 =100% | **核心安全/精度失败 = 整波不验收** |
| 机械映射覆盖类 | **选定 3-4 日的完整目标股×决策日总体**(unmapped 计入分母);市值五分位按各会话 `market_asof_trade_date` 的 **PIT 市值**划定(在观察 mapping_status 之前) | 宏观席适格率总体 ≥90%;每市值五分位 ≥80%;五分位最大-最小差 ≤15pp | **仅覆盖/均衡失败 = 宏观席保持 `shadow_only`**,波仍可验收 |

封存:总体 ID 集/计数/五分位边界/分子/分母/结果。`weighted` 模式晋级需:全部 M6
门通过 + **用户显式授权** + 新 C16b/评分契约 + 链 bump。§7 增阈值边界(90%/80%/
15pp)与分母回归测试。with/without 日仅诊断;效果/alpha 结论只能来自前向。

## §6 宏观市场分析师(第四席,v1.3 = round-2 处方全落地)

**角色:** 消费宏观数据资产,把宏观情境**传导为逐股指引**——传导必须**机械接地**
(round-2 B3),不是泛化市场观点。
**输入 = 宏观卡(D 晚决策,§0a 时间线)+ 逐股暴露行:**
- 市场情境卡 v0.4(M01-M16,D 收盘,晚间决策合法);
- **宏观快讯节**:宏观路快讯按 macro_type 分组、每类 ≤3/合计 ≤12,证据类
  **MFD/MFI/MFA/MFR**(M1;类属性进 ID 注册表),带 `n_independent_sources` 与
  事件龄——同受 §2 全部机制(簇修订 as-of/覆盖三态/净化/席位域);
- 政策事件节(政策细节行有注册宏观 ID);
- **MS01-MS05 维度专属股票暴露行**(B3 + round-4 m1 完整 schema):每行含
  `mapping_id / mapping_version / mapping_sha256 / mapping_status / exposure_type /
  exposure_bucket / exposure_value / snapshot_effective_at / 目标代码 / 维度 / 来源`;
  `mapped_no_exposure → exposure_value=null`(不造 0);THS 概念无同期快照即省略
  (M4);标签束哈希入 C16b。缺席渲染必带 `confirmed_absent_through=<确切通道
  cutoff>`。
**输出 = 宏观传导 scorecard,五维**(每分都需 **M/MF 事实 + 对应 MS 暴露行配对
证据**):风险偏好环境适配/流动性·资金面传导/行业·概念景气传导/
**policy_alignment(居中评分,M2)**/**external_shock_transmission(m1)**。
**覆盖感知聚合(round-4 M1,公式钉入 scoring_contract.macro_coverage_policy):**
coverage_ratio < 0.60 → `macro_status=not_applicable`、`macro_final=null`、
其余席位按 base 权重确定性重归一;完整规范公式见 §0d M1 行;完整性层从封存
原始记录重算全链。
**跨席防双计(M3,round-4 M2 完整规则):** `scoring_owner(claim_id,
target_ts_code, input_cutoff_at)`——subject_codes 显式点名的 target → news 所有;
经**批准的、cutoff 时有效的**系统性暴露触达的非 subject 同业 → macro 所有;
混合文本拆原子 claim_id(共享 fact_cluster_id);每个计分 `(claim_id, target)`
校验器要求**恰一**计分席,零或重复所有权**硬失败**;非 owner 席只能以显式
不可计分上下文消费。
**封存:** `macro_card_snapshot_id`+逐股上下文哈希+生成 ID 注册表+ts_code 进输入
指纹与档案(B3)。
**接线:** 四席并列;`macro_analyst_v1.txt` 进 manifest;空头消费四席;composite
四席化(**冻结候选基础权重 fund 0.35/tech 0.25/news 0.30/macro 0.10;macro 保持 `shadow_only` 直到 §5 weighted 晋级(全 M6 门+用户显式授权+新 C16b+链 bump)**,round-5 M2;
加权 = 新 C16b 候选 + 链 bump,须在观察评判窗前申报);密封链核心席位无关,但
**外围代码四席化需端到端测试**(m2:prompt 表/执行环/证伪域/卡装配/平台/重算)。
**成本:** +1 调用/股 ≈ 12 AFP/股;宏观卡共享 → prompt 缓存摊薄;晚间决策模式下
p99 延迟预算宽裕(§0a)。

## §6b 新闻价值提取增强(v1.8 = round-7 处方全落地)—— GPT round-8 待审

**动机不变**(快讯价值分钟级衰减 vs 晚间决策/次开盘节奏;详见 round-7 prompt 存档)。
**round-7 裁定(1B/4M/1m)全采纳,核心矫正:**

**round-8 裁定(2B/5M)全采纳,关键升级(取代下方 round-7 条目中被收紧处):**

**B1′ 语义化 attention 分类(不止新行名):** evidence_class 是**语义**判定——凡增量信息
只是计数/广度/重复/聚合/velocity/百分位/HHI/持续性/生命周期的行,**含既有 `N00`
/`NDA*`/`NIA*`**,一律 `attention_only`,物理移出全部正向计分 payload,只进
`attention_context_card`。**正向 news 卡只含去重的原子事实,无任何聚合计数行。**
测试检查**序列化后的 payload**:断言 `news_card`/`market_context`/任何别名下不含任何
缺 `factor_positive` 权限的注册记录、不含任何 count-only 派生。

**B2′ D1 执行三分离(封死开盘价 lookahead):** `fill_binding.json` 只含不可变
`fill_execution_gate_policy_id/hash` + 阈值 + 声明的执行语义。次开盘成交的 gap 控制
必须是**竞价前提交的订单条件**(如由前收盘派生的开盘限价单),**不得**"先观察官方
开盘价再决定"。若系统先观察开盘价再决策,其最早可成交点是**更晚的时间戳/bar、不同
执行 profile,拿不到那个被观察的开盘价**。执行期另写不可变 `fill_execution_gate.json`
/账本事件(绑定哈希/observed_at/执行数据哈希/谓词结果/`accepted|fill_gate_rejected`),
**绝不改 binding**。流动性只用盘前已知的尾部数据或带时戳的竞价快照,**禁用 D+1 全日
成交量**。

**M1′ D2 schema 兼容(exact-once × horizon):** 新增 typed `horizon_theses` +
`horizon_factor_scores`。全局维 `name` exact-once;horizon 维 `(name, horizon)` 在注册
积 `horizon_dimensions × {next_open,1-3d,5-20d}` 上 exact-once;缺/多/重对硬失败。
证据独占**全局**跨 `factor_scores + horizon_factor_scores + penalty_scores`;非计分
论点引用**不解锁分**。正向论点只映射注册因子维,负向只映射注册罚分,混合=context/
no-score。产出 `news_final_by_horizon`;**无标量 roll-up**,除非 `primary_decision_horizon`
及其公式钉入评分契约。空头 target 变 `(seat, dimension, horizon|null)`。D3 的"当前
最强反证"是每个论点内**必填的接地字段**,区别于前瞻的 what_could_weaken。

**M2′ D4/D5 机械消费隔离:** `chief_synthesis` 只在裁判输出**冻结后**运行,收不可变
副本,产 typed 工件 `evidence_class=research_summary, allowed_uses={display_only},
consumer allowlist={archive, platform}`;禁入席位计分/空头/裁判/fill binding/执行门/
排序/选股;数值分/动作/排名字段硬失败;**档案校验在无 chief 数据下重算裁判并证逐字
相等**。D5 移到裁判后独立确定性 `display_flagger`(也 display_only);数值 `judge()`
**永不**接收 attention_context_card。

**M3′ D6 冻结截面分母:** 任何席位运行前冻结 `attention_population_id/hash`(完整
目标股 ID/完整 PIT 题材宇宙/cutoff/映射快照/适用政策/源面板 ID/覆盖态);百分位只在
声明的适用总体上算,封存排除 ID 与原因;**绝不**只在选中候选/成功映射/存活打分名字
里算排名;生命周期态从同一不可变簇快照派生,不改写既有态。

**M4′ D7 属性维度作用域(防一事件四正贡献):** 每原子行带 `claim_id/fact_cluster_id/
evidence_group_id/attribute_type ∈ {fact,economic_linkage,timing,source_status}/源
span/allowed_dimensions`;校验器限每属性只入其注册维(fact→materiality;economic
linkage→fundamental_link;timing→catalyst/tradeability;source_status→confidence
cap/penalty/bear,**永不**正向 materiality);每 `(claim_id, attribute_type)` 至多一行
计分;跨属性/跨席重复语义主张硬失败;未知/未接地的经济联结**省略**不臆测。

**M5′:** §7 已彻底重写为 §§6b-6c 的穷尽实现清单(见 §7)。

---

**round-9 裁定(0B/4M/1m)全采纳,普适化/版本化收口(弧线收敛,0 Blocker):**

**M1″ 普适每消费者 payload 门(不止 news_card):** B1′ 规则对,但强制边界不穷尽——
regime 卡 **M03/M04/M09/M10/M14/M15 本身就是计数/广度/聚合/持续性行**,而
`market_context` 注入**每个**正向席 payload;fund/pv 卡也可能含动态计数/纯百分位;
动态节头可无 ID 泄计数。修复:**每次正向 LLM 调用前,从密封元数据注册表递归构造+校验
完整序列化 payload**(覆盖每卡/键/嵌套/别名、每条 F/FS/FB/FD/T/N/NF/NFC/M/MF/MS
记录):每个动态可见项必须解析到**恰一**条带 `factor_positive` 的注册项;attention_only
/未注册动态散文/count-only 派生 → 物理省略或硬失败;**静态节头不得含动态计数/广度/
百分位值**;发布 M01-M16 逐 ID 分类并封存**逐消费者 payload + 注册表哈希**;四席全测
(真实卡键/嵌套别名攻击/未注册动态节头)。penalty-only 材料若仍 LLM 计分需独立隔离
罚分腿。

**M2″ horizon = 版本化 opt-in schema(不扩共享校验器):** 评分契约加
`scorecard_schema_id`;默认 `c16_v1` **保持现有 allowlist 并拒绝所有 horizon 字段**
(冻结 MVP 契约不被悄悄放松);另加 opt-in `c16_news_horizon_v1`(仅 news 席、新链
版本下):typed horizon_theses/horizon_factor_scores、注册 horizons/dimensions、精确
键集、独立 `compute_news_final_by_horizon`;**复用**既有 bool 拒收/有限数/OverflowError/
safe-repr/[0,5] 守卫;全局 name 唯一 + `(name,horizon)` 笛卡尔精确覆盖;证据独占跨
所有计分集合;钉死全局分/罚分如何进各 horizon final(含罚分全局 vs horizon 化 + 舍入);
bear schema 版本化 `(seat, dimension, horizon|null)`;**证明 legacy 行为不变、c16_v1
仍拒新字段**。

**M3″ 空头 attention 入口 B3 安全:** `run_bear` 收密封逐卡元数据注册表;
`validate_bear_record` 仅当 counter_quote 的 ID **存在于确切来源注册表 + 卡哈希匹配 +
`bear ∈ allowed_uses`** 才接受;域来自注册表元数据、**绝不单凭 ID 前缀**;禁文本重发现
ID。**不泛化** `SEAT_ID_DOMAINS["news"]`——attention 记录若留 `domain=news` 则
`allowed_uses=bear` 足够;若引入新 `attention` 域,只放宽 bear/context 消费者及其
证伪 enum。加伪造 ID/跨卡注册表复用/元数据替换测试。

**M4″ chief 隔离覆盖 liveness/封印身份/输入时点:** 逐字重算只证 chief 没改裁判字节,
**不证** chief 超时/畸形/完成态不会①使决策档案不完整②延迟发布过 binding cutoff
③改被 fill_binding 绑定的档案封印④把决策后/开盘/成交信息灌进展示工件。修复:
**先冻结+封印+发布权威决策核心工件,再调** chief_synthesis/display_flagger;其输入
allowlist 仅限 cutoff-valid 密封卡/已校验席位记录/已校验空头/冻结裁判——**绝不含
binding/执行门/fill/收益/任何决策后数据**;各写独立可选附属工件(自带封印 +
`parent_decision_archive_sha256`);失败/超时/重试/缺席**不得**改决策完整性/封印/发布/
绑定适格/排序/选股/执行。回归:chief 成功/失败/超时/畸形/缺席下决策哈希·发布态·成交
适格**恒等**。

**m1″:** §6c 下方 D1 旧段(仍说执行门"加在 fill_binding")被 B2′ 取代——改为直接
引用 B2′ + 断言 `execution_data_effective_at ≤ order_submitted_at <
auction_matching_cutoff_at ≤ fill_at`;预提交限价单**可以**在开盘成交(开盘价决定
既有订单是否成交,但未被用于决定是否提交)。

---

**round-10 裁定(0B/3M/1m)全采纳,taxonomy 纠偏 + horizon 公式钉死:**

**M1‴ 市场状态事实 ≠ 新闻注意力(taxonomy 纠偏):** 我 round-9 按**数学形态**(计数/
广度/持续)把 M03/04/09/10/14/15 判为 attention_only——**错**。它们是**交易所派生的
市场状态事实**(不是故事/发布方/重复/叙事扩散的计数)。`attention_only` 只适用于
**信息流注意力派生**(新闻簇/源家族/叙事/题材扩散的计数/广度/velocity/集中/持续);
交易所派生的价格/宽度/涨跌停/换手/波动/主线指标 = **`market_state_fact`**,无论表为
计数/比率/百分位/连续。**M01-M16 权威表(现予发布):**

| IDs | evidence_class | 正向消费域 |
|---|---|---|
| M01/M02/M06-M08/M12 | market_state_fact | macro risk_appetite/shock |
| M03/M09/M15 | `market_breadth_state` | macro `risk_appetite_environment_fit`(technical 仅在单独注册后) |
| M04/M10 | `market_limit_state` | macro risk-appetite/liquidity;空头 context |
| M05 | market_state_fact | macro industry_concept_transmission |
| M11/M13 | market_state_fact | macro liquidity_flows_transmission |
| M14 | `market_leadership_state` | macro `industry_concept_transmission` |
| M16 + 政策行 | market_state_fact | macro policy_alignment |
| MF##(宏观快讯) | MFD/MFI/MFA/MFR | macro(MFR 仅负向) |
| N00/NDA/NIA + news-flow 派生 | `attention_only` | **永不正向** |

M03/04/09/10 按 **PIT 合格股分母**归一并封 universe ID;M14 封 PIT 行业宇宙+成分 ID;
每个 macro 正向用途仍需对应 MS 暴露行。**per-consumer 门升级为三元**:
`factor_positive ∈ allowed_uses ∧ consumer_seat ∈ allowed_consumers ∧
target_dimension ∈ allowed_dimensions`(不只全局 factor_positive)——fund/news 席**不**
接收这些 M 行;technical 席消费 M 行须**单独** technical 评分契约修订。

**M2‴ 隔离罚分腿(补进 §7):** news 执行拆 `news_factor_leg` 与 `news_penalty_leg`:
factor 腿只收 `factor_positive` 记录、出全局/horizon 因子分与论点;penalty 腿只收带
`penalty` 记录、出 typed `penalty_scores/risk_flags`;各自独立 prompt/route/元数据过滤
payload/校验器/raw 审计/manifest 哈希;确定性代码在聚合前合并已校验输出。**有 penalty
适格记录而 penalty 腿失败 → news 结果 not_applicable 或硬失败(按钉定政策),绝不静默
空罚分**;无适格记录 → 封显式"成功评估的空罚分"。§7/§13 加此接线与失败矩阵。

**M3‴ horizon 公式钉死(不留事后选择自由度):** 保留 news 席 20 分制、只替
catalyst_timing;`global_weights={event_materiality:6, fundamental_link:5, novelty:5}`,
`horizon_weights={tradeability_at_horizon:4}`,`penalty_multiplier=2`,v1 全部罚分**全局**、
每 horizon 同样适用(horizon 特定罚分需新 schema ID)。每 horizon h:
`raw_h = 6·s_materiality + 5·s_fundamental + 5·s_novelty + 4·s_tradeability,h`;
`news_final_h = round(clamp(raw_h − 2·Σ s_grounded_global_penalties, 0, 100), 1)`
(全精度到 clamp,序列化时一次舍入;无效/未接地 = NO-SCORE 贡献 0)。评分契约**校验前
二选一 hash-bound 模式**:`primary_horizon`(钉一个策略级 `primary_decision_horizon`,
`news.final` = 该 horizon final 的确定性别名,喂既有 judge/composite)或 `vector_only`
(无标量 judge/composite/排序/选股/执行,horizon 向量仅 shadow/展示研究)。
**primary_horizon 不得逐股变、不得在观察验证结果后选,须绑策略持有政策(非仅由次开盘
fill 时点推断)。**

**m1‴ 附属执行物理非阻塞:** `decision_published_at` = 密封决策核心工件的 append-only
发布事件;`adjunct_started_at ≥ decision_published_at`;绑定只消费决策核心哈希、**绝不**
等 chief/display 附属;附属 worker 用独立队列/锁/账本命名空间,**绝不**获取 fill-intent
发布/绑定锁——四时间戳链不变,chief 可在 binding_cutoff_at 后甚至开盘后完成(可选、
执行惰性)。

---

**round-11 裁定(0B/3M/0m;GPT:三处完成即无进一步设计缺口)全采纳,散文→穷尽枚举:**

**M1⁴ M01-M16 机械权威表(规范 enum):** 冻结唯一维度 enum
`{risk_appetite_environment_fit, liquidity_flows_transmission,
industry_concept_transmission, policy_alignment, external_shock_transmission}`;
正向 scope 列改**精确集合**:

| IDs | `allowed_dimensions` |
|---|---|
| M01/M02/M03/M06-M09/M12/M15 | `{risk_appetite_environment_fit}` |
| M04/M10 | `{risk_appetite_environment_fit, liquidity_flows_transmission}` |
| M05/M14 | `{industry_concept_transmission}` |
| M11/M13 | `{liquidity_flows_transmission}` |
| M16 聚合 | `{}`;**context_only,永不正向** |
| 注册的原子政策行 | `{policy_alignment}` |
| MF 正向记录 | 由注册 `macro_type` 派生的**恰一**维度 |
| MFR | 无正向维;仅 penalty/bear |

**`external_shock_transmission` 需一条正向 MFD/MFI/MFA 记录且注册 `macro_type=
external_shock` + 对应 MS 暴露**(M01/M02/M06-08/M12 **不**独立接地外部冲击维);
`policy_alignment` **只由原子政策行接地,M16 聚合不作数**;每个 macro 维仍需 MS 配对。

**M2⁴ horizon 缺失/NO-SCORE/N-A 语义(fail-closed 钉死):** 每个有效冻结 fill intent
下**三个注册 horizon 全适用**,每个 `(tradeability_at_horizon, horizon)` 对**强制存在**;
缺对或非有限分 = **factor 腿 schema 失败**;存在有限项但证据空/未接地 = 派生 NO-SCORE
贡献恰 0;**v1 无 horizon 级 not_applicable、无权重重归一**(停牌/一字 → 低/零接地
tradeability 或执行门拒,**非** horizon N/A)。`primary_horizon` 模式:factor 腿成功后
所有 horizon final 必有限,`news.final` 别名选定 horizon,**`verify_archive_semantics`
从封存条目重算每个 horizon final/别名/judge final/composite——不信封存计算值**。
`vector_only` 模式:**独立版本化 shadow 档案 schema**,可 `shadow_complete=true`,但
**无 `seats[news].final`、永不过可执行档案的有限标量 schema、永远 `binding_eligible=
false`**。

**M3⁴ 双腿终态矩阵(穷尽,替代"N/A 或硬失败"):**

| factor 腿 | penalty 适格数 | penalty 结果 | primary 模式结果 | vector_only 结果 |
|---|---:|---|---|---|
| 成功 | 0 | 确定性封存 `empty_success`(**不调 LLM**) | news final 算出、可发布 | `shadow_complete=true` |
| 成功 | >0 | 成功 | news final 算出、可发布 | `shadow_complete=true` |
| 成功 | >0 | 失败/超时/畸形 | **硬失败 news;不发布、不绑定** | 封失败 shadow;`shadow_complete=false` |
| 失败/超时/畸形 | 任意 | 任意 | **硬失败 news;不发布、不绑定** | 封失败 shadow;`shadow_complete=false` |
| 成功 | 0 | penalty LLM 竟被调 | **完整性违规** | 失败 shadow |

**移除可执行模式下的 `news not_applicable`**(后续引入需独立版本化 news-coverage 政策+
确定性 composite 重归一+档案 schema+测试)。至少封存:`factor_leg_status /
penalty_eligible_count / penalty_eligible_set_hash / penalty_leg_status / news_status /
output_mode / shadow_complete / decision_complete / binding_eligible`。

---



**B1 处置——attention-only 机械隔离(替代口头规则):** NFV/theme-heat/narrative 类记录
为 `attention_only`:**从每个正向计分席的 payload 中物理排除**(仅挡 evidence_spans
不够——模型看得见热度行就能借别的行抬分),渲染进独立密封的
**`attention_context_card`**,只供空头席与非计分综合消费。**生成 ID 注册表升级为带
元数据**:`{id, domain, evidence_class, allowed_uses}`,
`allowed_uses ⊆ {context_only, penalty, bear, factor_positive}`;校验器对 `attention_only`
ID 出现在 `factor_scores` **硬失败**。未来任何正向/选股用途 = 新 C16b 候选 + 评分契约 +
链 bump + **预注册方向性检验**。

**M1 处置——流特征 as-of 不可变快照:** 流只从不可变 `(cluster_algo_version, T,
cluster_snapshot_id)` 快照派生,成员按 `decision_visible_at=max(source_published_at,
first_ingested_at) ≤ T`;迟到成员/合并/拆分 = 新 append-only 修订,**绝不改写既有流
快照**。窗口固定 `(T−24h,T]/(T−120h,T]/(T−480h,T]`;计数=唯一事实簇,广度=唯一源
家族;`flow_velocity=count_1d/(count_20d/20)` 仅当分母>0,否则 **null/not_applicable
(绝非地板)**;必需源窗口不完整 → 特征 not_applicable 而非 0。封存
`flow_snapshot_id`/簇修订 ID/源面板与覆盖 ID/窗口政策哈希/PIT 题材映射哈希。

**M2 处置——吸收状态替代"未定价",方向禁入:** `unpriced_since_close` 更名为事实性
字段 **`no_exchange_session_since_publish`**(由 `(effective_at, input_cutoff_at]` 内
是否存在交易所价格发现区间判定;Asia/Shanghai,显式处理午休/节假日/集合竞价/停牌/
一字板)。盘中事件的 D 收盘数据只产 **`absorption_status`**(市场/行业残差**绝对**
波动+异常换手+涨跌停状态+停牌状态;**带符号收益不得抬任何分**——动量伪装环路封死);
收盘后事件 `D_reaction=not_applicable`;日频归因标 `coarse_daily_unattributed`;
吸收证据**只能封顶/降低** tradeability,小反应=unknown 而非"仍利好";**实际次开盘
gap 是执行期数据,永不进晚间决策档案**。

**M3 处置——E6 独立负向证据类:** 新 **`NFC##`,evidence_class=coordination_risk**,
仅允许注册的 news 罚分维 `coordination_risk` 与空头反证;记录带源家族 ID/相似规则
版本哈希/爆发窗参数/`structured_backing_status ∈ {present, confirmed_absent,
coverage_incomplete, source_unavailable}`;**仅 confirmed_absent 时发旗**,不完整/
不可用 = not_applicable。E5/E6 全配置入 C16b 与评分契约;若未来影响 tilt/veto/选股
= 完整 C16 候选因子(负向不豁免)。

**M4 处置——M6 门扩展(§5 增补,同框架同样本量):** 新增 §6b 分层(盘中/午休/
收盘后/盘前/节假日边界/迟到修订/源中断/零基线/高低流/PIT 题材映射/停牌一字/协同
案例);机械验收:既有快照被改写=0;attention-only 入正向分=0;session 边界误判=0;
收盘后事件用 D 反应=0;覆盖不完整下发协同旗=0;双标注样本上 `coordination_flag`
精度 ≥95%(留分歧率);全部特征适用性/缺失计数封存。3-4 日验证仍 NON_EVIDENTIARY,
不得据以声称延续/反转/alpha。

**m1 处置:** E5 更名 **`narrative_direction_shift`**(自有流叙事方向转变,非一致
预期 surprise),context-only,**默认延后**。

## §6c DESK VIEW 采纳分诊(round-7 R3/R4;标注=GPT 原判)

**本波纳入(v1.8):**
- **D1 后隙延续/反转论点 + 预注册开盘执行门**(R3-1,GPT 首推;**执行合同以 B2′/m1″
  为准**):决策期——news 席对每个重大事件给分 horizon 的情景评估(见 D2);执行合同
  见 §6b B2′ 三分离,断言
  `execution_data_effective_at ≤ order_submitted_at < auction_matching_cutoff_at
  ≤ fill_at`——预提交限价单(前收盘派生)可在开盘成交(开盘价决定既有订单是否成交,
  但未被用于决定是否提交);不过门封 `fill_gate_rejected`;**实际 gap/开盘价永不回流
  决策分**。
- **D2 horizon/情景化 scorecard schema**(R3-2+R4-3,并入 E3 的评分契约变更):news
  席每论点带 `direction / horizon ∈ {next_open, 1-3d, 5-20d} / 因果链 / priced-in
  状态(=absorption_status 接地)/ 替代解释 / 基准·不利情景 / 可观察证伪条件`;
  单一无时限 0-5 分经济上不连贯——`tradeability_at_horizon` 维按 horizon 接地。
- **D3 证伪优先 prompt**(R4-4):四席 prompt 重排——先要求「最强反证解读」,后打分
  (现行 what_could_weaken 在打分之后,反转次序);prompt 变更入 manifest 冻结。
- **D4 非计分首席综合(第二遍)**(R4-2):空头后一遍 `chief_synthesis`(路由已有
  预留):调和因果链/horizon 错配/priced-in/矛盾,产出 research_summary 叙事;
  **不改任何席位分/权重/裁判**(纯展示+读档价值;+1 调用/股 ≈ +2.5 AFP)。
- **D5 确定性交互旗**(R4-5):裁判侧新增展示级旗(`material_news_but_fully_absorbed`
  /`theme_heat_without_entity_exposure`/`fundamental_technical_horizon_conflict`),
  纯确定性、只展示;若未来改数值 = 进评分契约+C16。
- **D6 注意力截面排名/扩散/生命周期**(R3-4+R3-5):attention_context_card 内容 =
  同 cutoff 截面百分位、成分扩散度、集中度 HHI、题材规模/源面板归一、3/5 日持续性、
  事实簇生命周期态 `emerging→independently_confirmed→diffusing→crowded→
  contradicted→decaying`——全部确定性、attention-only 域。
- **D7 原子属性行**(R4-6,范围化):重大直接事件(importance≥4)拆原子注册属性行
  (事实/经济联结/时点/来源状态),缓解行 ID 独占迫使一行撑一维;上限每事件 ≤4 行。

**v2 backlog(需新数据,不入本波):** 经济量级归一(R3-3,需结构化全文管线);
分钟级反应归因与竞价/排队上下文(R3-6 完整版);E5 一致预期锚(需干净预期源)。

## §7 实现清单(round-8 M5′ 重写:对 §§6b-6c **穷尽**;删除 v1.7 过时项)

**已删除(v1.7 过时,round-8 明令)**:`freshness_class`(→ M2′ 的事实字段
`no_exchange_session_since_publish`)、`direction_surprise`(→ m1 更名
`narrative_direction_shift`,context-only 延后)、普通渲染器内的 NFV/theme-heat
(→ 独立 attention_context_card)、旧的泛化"流不入正向分"测试(→ 语义 attention_only
硬失败 + payload 序列化断言)。

0. **B3 窄热修**:已完成(chain_v3.1,commit cb56eba,240/240)——渲染净化+emit-time
   ID 注册表+席位域;本波在此之上升级注册表为**带元数据** `{id, domain, evidence_class,
   allowed_uses}`。
1. **抓取层**:news 端点契约入 data_dictionary(`fields='datetime,content,title,channels'`
   ——channels 默认不返回;`src` 我方注入列)→ `fetch_news`(串行/水位线/递归窗)+
   源×窗覆盖清单(B2)→ 采集后更新 data_tracker。
2. **不可变快照层**(M1′/M3′):簇 `(cluster_algo_version, T, cluster_snapshot_id)`
   append-only,`decision_visible_at=max(published, first_ingested)≤T` 分桶;冻结
   `attention_population_id/hash`(完整目标股+PIT 题材宇宙+源面板+覆盖态)先于任何席位。
3. **`news_ingest.py` 管线**:净化/预过滤/簇修订/源家族(B4)/三路路由/三维分型;
   派生**确定性** attention 特征(全 attention_only 域):flow velocity/breadth(E1,
   固定窗 24/120/480h,分母>0 否则 null)、`no_exchange_session_since_publish` +
   `absorption_status`(M2′,方向中性)、theme_flow_velocity/扩散/HHI/生命周期(D6)、
   `coordination_flag`(NFC,仅 confirmed_absent)、`narrative_direction_shift`(延后)。
4. **别名注册表**(独立审批工件)+ fact_cluster_id + **scoring_owner**(target 级,
   M3/M4)。空头 attention 入口 B3 安全(M3″):`run_bear` 收密封逐卡元数据注册表,
   `validate_bear_record` 仅当 counter_quote ID 存在于确切来源注册表+卡哈希匹配+
   `bear∈allowed_uses` 才接受,域来自元数据非 ID 前缀,禁文本重发现;不泛化
   `SEAT_ID_DOMAINS["news"]`。加伪造 ID/跨卡复用/元数据替换测试。
5. **双卡渲染 + 带元数据注册表**:正向 `news_card`=**去重原子事实,零聚合计数行**
   (B1′:N00/NDA/NIA 移出);独立密封 `attention_context_card`=全部 attention_only
   内容(D6)。**D7 原子属性行**:`claim_id/fact_cluster_id/evidence_group_id/
   attribute_type/allowed_dimensions`,每属性只入注册维、每 `(claim_id, attribute_type)`
   至多一行计分。证据类上限算术 NFD/NFI/NFA/NFR/NFC + MFD 系。
6. **普适每消费者 payload 门(M1″/M1‴ 三元 + M-line taxonomy)+ 校验器升级**:每次
   正向 LLM 调用前从密封元数据注册表**递归构造+校验完整序列化 payload**(每卡/键/嵌套/
   别名、每条 F/FS/FB/FD/T/N/NF/NFC/M/MF/MS);每个动态可见项**三元授权**
   `factor_positive ∈ allowed_uses ∧ consumer_seat ∈ allowed_consumers ∧
   target_dimension ∈ allowed_dimensions`(维度取自 §6b M1⁴ 规范 enum),否则物理省略/
   硬失败;静态节头不得含动态计数/广度/百分位;**M01-M16 按 §6b M1⁴ 精确集合表分类**
   (交易所派生=market_state_fact 保留、按 PIT 合格股/行业宇宙归一并封 universe ID;
   **M16 聚合=context_only 永不正向、policy_alignment 只由原子政策行接地、
   external_shock 须注册 macro_type;N00/NDA/NIA + news-flow=attention_only 移出**;
   fund/news 席不收 M 行,technical 席 M 行须单独契约修订);封存
   逐消费者 payload+注册表哈希;attention_only ID 入 factor_scores **硬失败**;证据独占
   **全局**跨 factor+horizon+penalty;D7 dimension-scoped + evidence_group 防一事件四
   贡献;四席全测(真实卡键/嵌套别名/未注册动态节头/M-line 消费域)。
7. **双腿 news 执行(M2‴)+ horizon 版本化 schema(M2″/M3‴)**:news 拆
   `news_factor_leg`(只收 factor_positive,出全局+horizon 因子分与论点)与
   `news_penalty_leg`(只收 penalty,出 typed penalty_scores/risk_flags);各独立 prompt/
   route/元数据过滤 payload/校验器/raw 审计/manifest 哈希;确定性代码聚合前合并;
   **终态按 §6b M3⁴ 穷尽矩阵**(factor 腿失败 OR 有适格 penalty 而 penalty 腿失败 →
   **硬失败 news、不发布不绑定**;适格=0 → 确定性封 `empty_success` 不调 LLM;封存
   9 字段 factor_leg_status/penalty_eligible_count/set_hash/penalty_leg_status/
   news_status/output_mode/shadow_complete/decision_complete/binding_eligible)——
   **无可执行模式 news not_applicable**。评分契约加 `scorecard_schema_id`:默认 `c16_v1`
   **不变、拒所有 horizon
   字段**;opt-in `c16_news_horizon_v1`(仅 news 席)钉死公式:`global_weights=
   {event_materiality:6, fundamental_link:5, novelty:5}`、`horizon_weights=
   {tradeability_at_horizon:4}`、`penalty_multiplier=2`、全部罚分全局;每 horizon h
   `raw_h=6·materiality+5·fundamental+5·novelty+4·tradeability_h`,
   `news_final_h=round(clamp(raw_h−2·Σ grounded_global_penalty,0,100),1)`(全精度到
   clamp、一次舍入);**缺失/N-A 语义(M2⁴)**:三 horizon 全适用,每
   `(tradeability,horizon)` 对强制存在,缺对/非有限=factor 腿 schema 失败,空/未接地=
   NO-SCORE 贡献 0,**v1 无 horizon 级 not_applicable/无重归一**;**二选一 hash-bound
   模式**:`primary_horizon`(钉策略级 `primary_decision_horizon`,`news.final`=其确定性
   别名喂 judge,factor 腿成功后所有 horizon final 必有限,`verify_archive_semantics`
   从封存条目重算不信封值;**不得逐股变/不得事后选/绑持有政策**)或 `vector_only`
   (**独立版本化 shadow schema、无 seats[news].final、永不过可执行有限标量 schema、
   永远 binding_eligible=false**);
   复用既有 bool/有限数/OverflowError/safe-repr/[0,5] 守卫,bear schema 版本化
   `(seat,dimension,horizon|null)`,每论点必填当前最强反证接地字段(D3)。改
   [scorecard.py](../../../src/ai_layer/scorecard.py) **严格附加式**+评分契约+链 bump;
   **证明 legacy 恒等、c16_v1 仍拒新字段**。
8. **prompt 证伪优先**(D3):四席先陈述最强反证再打分;prompt 入 manifest 冻结。
9. **宏观卡 + MS 暴露行 + 宏观席 + 四席 composite**(§6);§0a 四时间戳链入引擎断言。
10. **裁判后隔离 + liveness/封印身份/输入时点(M4″/m1‴ 物理非阻塞)**:**先冻结+封印+
    发布权威决策核心工件(`decision_published_at`=其 append-only 发布事件),再调**
    `chief_synthesis`/`display_flagger`(`adjunct_started_at ≥ decision_published_at`);
    其输入 allowlist 仅限 cutoff-valid 密封卡/已校验席位·空头/冻结裁判——**绝不含
    binding/执行门/fill/收益/任何决策后数据**;各写独立可选附属工件(自带封印+
    `parent_decision_archive_sha256`);typed `research_summary/allowed_uses={display_only}/
    consumer={archive,platform}`,数值/动作/排名字段硬失败;`display_flagger`(D5)裁判后
    独立确定性,数值 judge() 永不收 attention_context_card;**绑定只消费决策核心哈希、
    绝不等附属;附属 worker 用独立队列/锁/账本命名空间、绝不获取 fill-intent 发布/绑定
    锁**(chief 可在 binding_cutoff_at 后甚至开盘后完成);**回归:chief 成功/失败/超时/
    畸形/缺席下决策哈希·发布态·成交适格恒等**。
11. **执行门三分离**(B2′/D1):`fill_binding.json` 只含
    `fill_execution_gate_policy_id/hash`+阈值+执行语义;竞价前提交订单条件(前收盘
    派生开盘限价);执行期另写不可变 `fill_execution_gate.json`(binding 哈希/
    observed_at/执行数据哈希/谓词/accepted|fill_gate_rejected),**绝不改 binding**,
    禁用 D+1 全日量,**观察到的开盘价不得既用于决策又据以成交**。
12. **运行清单对账 + C16b 指纹全集**(§6b/6c 全参数)+ FORWARD_PREREG.md。
13. **测试(§§6b-6c 穷尽 + M4′/round-9 边界/对抗)**:普适 payload 门四席×真实卡键×
    嵌套别名×未注册动态节头(M1″;M01-M16 逐 ID 分类断言)/horizon 版本化(c16_v1 拒
    新字段·legacy 恒等·(name,horizon) 精确覆盖,M2″)/空头注册表授权(伪造 ID·跨卡
    复用·元数据替换,M3″)/chief liveness(成功·失败·超时·畸形·缺席下决策哈希恒等,
    M4″)/既有 v1.6 测试全集 + attention_only
    payload 序列化断言 + 语义计数行分类 + 不可变快照(既有快照改写=0)+ 执行三分离
    (无开盘价 lookahead)+ horizon exact-once/全局独占 + chief 无 chief 重算相等 +
    display_flagger 不入 judge + D6 冻结分母 + D7 属性作用域(一事件四贡献=0)+
    session 边界×日历(误判=0/收盘后用 D 反应=0)+ coordination 仅 confirmed_absent
    (覆盖不完整发旗=0)+ **M-line 规范 enum 表(精确 allowed_dimensions/M16 聚合永不
    正向/policy 只原子行/external_shock 须 macro_type/三元消费域)+ 双腿终态矩阵五行
    穷尽(factor 失败·penalty 有适格失败=硬失败不发布/适格0=empty_success 不调 LLM/
    9 封存字段)+ horizon 公式数值锁(raw_h/一次舍入)+ 缺对=schema 失败/无 N-A/无
    重归一 + primary_horizon 不逐股不事后+别名有限标量+重算不信封值 + vector_only 独立
    shadow schema 永不 binding_eligible + 附属非阻塞(binding 不等 chief/独立锁)** +
    M6 §6b 分层 + coordination 精度≥95%。
14. 链版本 bump → 单日烟测 → §5 读质量门(M4′ 扩展分层 + 数值线 + 双标注协议)。
