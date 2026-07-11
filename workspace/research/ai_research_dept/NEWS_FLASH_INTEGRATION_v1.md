# 新闻快讯接入设计 v1.4(NF 波次 + 宏观席)— 设计稿,GPT round-4 待审

状态:DESIGN v1.4(2026-07-11)。裁定史:①用户:快讯必须进决策框架 + 硬性噪音去除;
②用户:宏观/市场流是数据资产 → 第四席 + 逐股传导(v1.1);
③GPT round-1(v1/0958b07):CHANGES REQUIRED 4B+6M+2m,全采纳(§0);
④GPT round-2(v1.2/d843e55):CHANGES REQUIRED 3B+6M+2m,全采纳(§0b);
⑤GPT round-3(v1.3/4437185):CHANGES REQUIRED **0B**+3M+2m——晚间决策声明关闭
round-2 B1/B2;**B3 热修获准立即开工**(R5);三 Major 全采纳(§0c)。
实现前置:B3 热修先行(已获准);其余待 GPT round-4 通过。

---

## §0a 决策时间线声明(round-2 B1/B2 的根因是本文档从未钉死它;现予声明并机械化)

**本系统唯一支持的决策模式 = D 收盘后晚间决策,次一开市日开盘执行**(与既有重放
语义、前向 MVP「晚间决策」完全一致;**不存在"D 早盘用 D 收盘卡"的模式**——GPT
round-2 按盘前决策模式推导的 lookahead 在声明后不成立,但其全部机械断言照单落地):

- **市场日与决策日历日解耦(round-3 M2:周末/长假陈旧情绪修复)**——逐档案封存:
  `market_asof_trade_date = 发布前最近开市日`(行情/M 卡锚);
  `decision_calendar_date = 新鲜晚间运行的日历日`(快讯锚);
  `macro_flash_cutoff_at = decision_calendar_date 当晚 cutoff`;
  `fill_trade_date = decision_published_at 之后的下一开市日`;
  **`max_flash_age_at_fill ≤ 18h`(预注册)**:超龄则在复市前最后一个日历晚
  **重跑新鲜决策**或放弃该次成交——0205 开盘用 0127 市场卡 + **0204 晚为止的快讯**,
  春节 8 天新闻不再被忽略(短期情绪命题守住)。
- **四时间戳因果链(B2 处置,机械断言 + 违反即终态失败)**:
  `input_cutoff_at < pipeline_frozen_at <= attempt_started_at <
  decision_published_at < fill_open_at`。
  **成员 `effective_at ≤ input_cutoff_at`;管线完成 ≤ `pipeline_frozen_at`**
  (round-3 m1 措辞修正:查询窗止于 cutoff,抓取/分型/覆盖终查在 cutoff 之后、
  冻结之前完成);`input_cutoff_at` 显式定义 = 各通道 cutoff 的最晚者(通常 =
  macro_flash_cutoff_at);水位线只在全部子窗与管线记录落盘后推进;
  **盘前门用实际 `decision_published_at`** 对照 fill_open_at,错过 = 终态失败;
  预注册 p99 延迟预算(晚间模式小时级,65.5min 链实测宽裕)。
- 硬失败断言:market_asof_trade_date ≠ 发布前最近开市日 / 任一成员 effective_at
  超其 cutoff / decision_published_at ≥ fill_open_at / flash 龄超
  max_flash_age_at_fill 且未重跑 → 拒绝发布。

## §0b GPT round-2 处置表(全采纳;B1/B2 以 §0a 声明为锚落地其机械处方)

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

## §5 读质量门(M6,替代全月重放的验证协议)

分层 3-4 日(涨停潮/大跌/平静/节前)集成验证 + **看结果前冻结的 300-500 条分层盲审
样本**与硬阈值(§0 M6 行);with/without 日仅诊断。效果/alpha 结论只能来自前向。

## §6 宏观市场分析师(第四席,v1.3 = round-2 处方全落地)

**角色:** 消费宏观数据资产,把宏观情境**传导为逐股指引**——传导必须**机械接地**
(round-2 B3),不是泛化市场观点。
**输入 = 宏观卡(D 晚决策,§0a 时间线)+ 逐股暴露行:**
- 市场情境卡 v0.4(M01-M16,D 收盘,晚间决策合法);
- **宏观快讯节**:宏观路快讯按 macro_type 分组、每类 ≤3/合计 ≤12,证据类
  **MFD/MFI/MFA/MFR**(M1;类属性进 ID 注册表),带 `n_independent_sources` 与
  事件龄——同受 §2 全部机制(簇修订 as-of/覆盖三态/净化/席位域);
- 政策事件节(政策细节行有注册宏观 ID);
- **MS01-MS05 维度专属股票暴露行**(B3):as-of,含股票代码/适用行业·概念·风格
  暴露/来源/`snapshot_effective_at`(M4:THS 概念无同期快照即省略;标签束哈希入
  C16b)。
**输出 = 宏观传导 scorecard,五维**(每分都需 **M/MF 事实 + 对应 MS 暴露行配对
证据**,缺 MS = no-score):风险偏好环境适配/流动性·资金面传导/行业·概念景气传导/
**policy_alignment(居中评分,M2)**/**external_shock_transmission(m1)**。
**跨席防双计(M3):** 事实修订带 `scoring_owner`(发行人直接 → news,系统广谱 →
macro);非 owner 席上下文可见、不可计分。
**封存:** `macro_card_snapshot_id`+逐股上下文哈希+生成 ID 注册表+ts_code 进输入
指纹与档案(B3)。
**接线:** 四席并列;`macro_analyst_v1.txt` 进 manifest;空头消费四席;composite
四席化(**round-2 建议先验 fund 0.35/tech 0.25/news 0.30/macro 0.10,待用户终裁**;
加权 = 新 C16b 候选 + 链 bump,须在观察评判窗前申报);密封链核心席位无关,但
**外围代码四席化需端到端测试**(m2:prompt 表/执行环/证伪域/卡装配/平台/重算)。
**成本:** +1 调用/股 ≈ 12 AFP/股;宏观卡共享 → prompt 缓存摊薄;晚间决策模式下
p99 延迟预算宽裕(§0a)。

## §7 实现清单(round-3 通过后;第 0 项按 R6 裁定先行)

0. **B3 窄热修(先行,独立链 bump)**:渲染净化 + 生成 ID 注册表(封入档案)+
   席位-ID 域 + 对抗注入测试;落地前 chain_v3.0 不执行任何运行
1. news 端点契约入 data_dictionary → 抓取层:`fetch_news` + 水位线 + 递归窗 +
   覆盖清单(B2)→ 采集后更新 data_tracker(m2)
2. `news_ingest.py`:净化/预过滤/簇修订/源家族/三路路由/三维分型(B1/B4/M1)
3. 别名注册表(独立审批工件)+ fact_cluster_id + scoring_owner(M3/M4)
4. 渲染:证据类上限算术 NFD/NFI/NFA/NFR + MFD/MFI/MFA/MFR(M2/round2-M1)
5. 宏观卡 + MS 暴露行 + 宏观席 + 四席 composite(§6;§0a 四时间戳链入引擎断言)
6. 运行清单对账 + C16b 指纹全集 + FORWARD_PREREG.md 更新(M5)
7. 测试:对抗注入集/簇 as-of/覆盖三态/源家族/证据类算术/席位域/配对证据/
   scoring_owner/四席端到端(含平台/重算)/四时间戳断言
8. 链版本 bump → 单日烟测 → §5 读质量门(M5 数值线 + 双标注协议)
