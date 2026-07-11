# 新闻快讯接入设计 v1(NF 波次)— 设计稿,待 GPT 跨审

状态:DESIGN(2026-07-11)。用户裁定:新闻快讯是短期情绪机会的核心信息源,必须纳入
LLM 决策框架,**且必须配套噪音去除机制**。本文档 = 设计全案 + 单日采样评估证据。
实现前置:GPT 跨审通过。

---

## §1 采样评估(2026-07-11 实测,决策窗 2025-01-26 15:00 → 01-27 15:00)

| 指标 | 实测值 | 含义 |
|---|---|---|
| 量级 | **2,012 条/24h**(sina 884 / 10jqka 443 / eastmoney 361 / wallstreetcn 324;cls 返回 0——财联社疑需单独子权限,待查) | 单源单日一次调用即可(1500 上限未触顶) |
| 跨源重复 | **18%**(标题规范化指纹粗测;语义级更高) | 去重是第一道必修机制 |
| 时间戳 | 秒级(sina/东财/见闻),10jqka 分钟级 | PIT 锚质量好 |
| 正文长度 | 中位 119-148 字 | 真快讯体,适合 quick-LLM 分型 |
| **个股可挂钩率** | **~7%**(含代码 2% + 提及金股池名 5%,并集 134/2,012) | **93% 为宏观/行业/市场杂讯——噪音去除的量化依据** |
| 样例质量 | 「中芯国际港股盘中跌 7%」逐级快讯流(验证日 SMIC 在池) | 正是 news 席需要的短期情绪信息 |

接口事实(offline 文档 143 已读,§6.1 合规):`news` 端点,9 源,6 年+历史,
1500 条/次按时间窗循环,字段 `datetime/content/title/channels`,单独权限(Day-1 已验通)。
无 ★ 标记 PIT 陷阱字段(对照:major_news 有 ★pub_time)。

## §2 噪音去除管线(设计核心;确定性优先、LLM 其次、全部 fail-closed)

按序执行,每级淘汰都留结构化计数(进事件库审计字段,绝不静默丢弃):

1. **源分层白名单**:v1 仅收实测可用的 4-5 源;`source_tier` 分层(cls/wallstreetcn=T1,
   sina/eastmoney/10jqka=T2)。新源加入 = 配置版本变更。
2. **确定性预过滤**(零 LLM 成本,先砍量):长度域(<20 字弃);channels 栏目黑名单
   (娱乐/体育等);**黑嘴模式词表硬丢弃**(荐股话术:目标价/建仓/加群/涨停板战法等
   ——反操纵第一道,词表版本化)。
3. **跨源去重 + 佐证计数**:标题/正文规范化指纹聚簇(实测 18% 粗重复);簇内保留最早
   `visible_at` 为主事件,`n_sources` 记佐证度——**把重复从噪音变成信号**(多源同报
   = 重要度加分项,进分型输入)。
4. **实体挂钩硬门**(相关性,预计削减 ~90% 量):代码/股票名/别名精确匹配 →
   `subject_codes`;申万行业词表 + THS 概念词表 → `industry_tags/concept_tags`;
   **三类挂钩全空且非政策/宏观类 → 丢弃**(宏观政策类归 regime/政策通道,不进个股检索)。
5. **quick-LLM 分型**(复用 irm_qa 分型基建:doubao-lite thinking OFF、注册 enum、
   校验 fail-closed):`event_type ∈ {公司经营, 订单/合同, 产能/产品, 行业动态,
   政策转述, 盘面异动, 传闻/未证实, 市场评论}`;`direction`;`importance_0_5`;
   **`is_rumor` 旗:单源 + 未证实表述 → importance 封顶 2**。
6. **新颖度门**:与近 3 日同主体事件指纹比对,重复报道降权(novelty 字段),
   防同一故事连日刷屏。
7. **卡片端机械围栏**(消费侧,复用既有 validators 基建):新行 ID 类 **NF##**;
   `_news_requires_cap` 加 NF 前缀 → **NF 类证据对分数的贡献钳位 ≤3**(与 NI/NDA 同法);
   同源同类配额;间接快讯走 NDA 聚合;缺席谓词照旧(「窗口内无池内快讯」显式声明)。
8. **反操纵评分护栏**(KOL/情绪深研裁决落地):**`传闻/未证实` 类 NF 行不得作为
   score≥4 维度的唯一证据**(scorecard 端 validator 规则,机械执行);传闻旗事件
   自动进空头席证伪素材。

## §3 PIT 锚定

- `visible_at = datetime`(发布秒级);**前向抓取**加 `fetch_ts`,生效锚 =
  `max(datetime, fetch_ts)`(防迟到/回填行伪装历史可见——B1/B2 同款防御,快讯爬虫流
  风险低但审计字段必须在)。
- 历史重放本就 NON_EVIDENTIARY;快讯历史深度 6 年+,是否存在编辑/回填未经验证——
  入库记 `fetch_ts`,历史批次统一标 `history_bulk`,不承诺行级 PIT。

## §4 治理与版本

- 检索层新增 `news_flash` 通道 = **RetrievalConfigCandidate 版本变更(C16b)**;
  news 卡渲染/prompt 变 → **链版本 bump**(chain_v3.1+);前向前必须并入
  FORWARD_RETRIEVAL_PREREG 冻结。
- 量与成本预估:2,012 条/日原始 → 管线后 **~100-300 条/日入库**;分型 LLM
  (lite/mini)全月 ≈ 1.5-3M tokens ≈ 100-200 AFP,可忽略。
- 全月重放已按用户裁定**取消**;接入完成后在最终链版本跑**分层 3-4 日验证**
  (涨停潮/大跌/平静/节前日),其中 1 日做 with/without news 同日对照(诊断性,
  NON_EVIDENTIARY)。

## §5 实现清单(GPT 审后)

1. `TushareFetcher.fetch_news`(串行/时间窗循环/1500 分页)+ 月分片 parquet
   (`data/analyst/news_flash/`)
2. `engine/news_ingest.py`:管线 §2.1-2.6 → 事件库(event_store 既有 schema,
   source=`news_flash`,payload 带 n_sources/novelty/is_rumor/tier)
3. 检索层 `news_flash` 通道 + 配额;news 卡 NF 行渲染(NF ID 注册表)
4. validators:NF 钳位 + 传闻不撑高分规则;prompts v2 增两行消费说明
5. 测试:管线逐级淘汰计数/去重簇/挂钩门/分型 enum fail-closed/NF 钳位/传闻护栏
6. 单日烟测 → 分层 3-4 日验证(替代全月)
