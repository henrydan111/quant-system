# 输入卡与 Prompt 专业审计 v1(逐维改进提案 → 实施中)

- 日期:2026-07-09 · 作者:Claude(链版本基线 chain_v1.3)· 状态:**实施中(chain_v2.0)**
- **GPT 跨审延后(用户指令 2026-07-09:GPT 当前不可接收 review,自评通过即执行)**——
  三轮自评(§7/§8)通过;§7.3 五项由自裁 + 探测裁决(见下);GPT 复审在恢复可用后补做,
  且必须在任何前向 PREREG 之前完成。
- **§7.3 自裁记录**:① 双重计分 → **方案 B**(方向性状态行无幅度,幅度留消息席,
  prompt 围栏只准支撑 earnings_inflection);② 空头全量 scorecard → **采纳**
  (deepseek 输入 token 增量成本可忽略);③ regime 第二枚举轴 → **不加**(6 标签保持,
  趋势信息由确定性行承载,避免无消费方的枚举膨胀);④ 聚合行围栏 → **采纳**
  ([概念聚合] 前缀 + prompt 明示封顶 3 分);⑤ F2 对 149 份存量档案 → **不逐档标注**
  (chain_version 徽章已表达差异,v2.0 全月重放自然覆盖)。
- **F3 口径探测裁决(2026-07-09 实测)**:`or_yoy_q1` 被 loader 拒绝
  (指标类 q-slot 未注册,fail-closed 正常)→ 8 季序列采用**退化方案:vintage 序列**
  (各点为当时已知值,来自既有季度采样面板)+ 卡内显式标注。
- 触发:用户裁定"市场情境卡不应只局限于当日信息,应考虑过去一段时间的趋势;每一部分的输入都还有很大优化空间",要求从**专业投资分析师和交易员**的角度逐维审计并提改进建议,交 GPT 评审。
- 审计对象(全部现行原文见附录 A):市场情境卡([regime_brief.py](engine/regime_brief.py))、
  基本面卡([fact_table.py](engine/fact_table.py) + [cards.py](engine/cards.py) `render_fund_card`)、
  技术面卡([pv_pack.py](engine/pv_pack.py) + `render_pv_card`)、
  消息面卡([retrieval.py](engine/retrieval.py) + `render_news_card`)、
  四个席位 prompt([prompts/](engine/prompts/))与 regime prompt。
- 不变约束(所有提案在此框内):C15 payload=数据非指令;C16 LLM 只出 0-5 维度分+逐字证据,
  总分/建议永远是代码;PIT=卡片日期 D 只含 D 收盘可知信息(全部新增项为**向后滚动窗**统计);
  三席互盲;重放产物 NON_EVIDENTIARY;卡/prompt 变更=新 chain 版本(C16b 精神);
  检索层配置(RETRIEVAL_CONFIG/快照)**本提案一概不动**——只动"卡片渲染层"(呈现),边界见 §6.5。

---

## §1 市场情境卡(用户点名项)

### 1.1 现状与专业视角批评

现状 7 项全部是**单日快照**(仅成交额带 250 日分位):当日指数涨跌/当日风格差/当日宽度/
当日涨跌停数/成交额分位/当日行业轮动/近 3 日政策行。

交易员批评:**单日是噪音,regime 本质是多日状态。** 任何一份专业晨会纪要都不会只说"昨天沪深300
跌 0.4%",而是"三周下行通道内的第 N 天、缩量、风格连续 X 日偏大盘"。具体缺陷:

| # | 缺陷 | 后果 |
|---|---|---|
| 1 | 风格差只有当日(+1.1pp) | 单日风格差几乎全是噪音;连续 10 日累计 +5pp 才是可交易的风格环境 |
| 2 | 宽度只有当日 | 无法区分"普跌第一天"(转折候选)与"普跌第五天"(趋势确认) |
| 3 | 涨停温度只有当日 | 打板情绪的边际变化(今日涨停 48 vs 5 日均值 80 = 急剧退潮)完全丢失 |
| 4 | 无波动/回撤状态 | "指数距 60 日高点回撤多深"是仓位语境的第一变量,卡内没有 |
| 5 | 行业轮动只有当日 | 无法区分主线(连续领涨)与一日游轮动——这是 A 股最重要的情境变量之一 |
| 6 | 无资金面 | 两融余额趋势(risk appetite 的慢变量)缺失;数据已批准($rzye 等) |
| 7 | regime 无持续性 | 标签逐日独立生成,LLM 看不到"这是收缩的第几天" |

### 1.2 提案:情境卡 v0.2 = 三节结构(快照 / 趋势 / 持续性)

```
【市场情境卡 D】(全部数字由代码计算)
◆ 当日快照(现有 7 项,保留)
◆ 趋势(5d/20d,全部向后滚动)
  - 指数累计: 沪深300 5d -2.1% / 20d -4.5%;中证1000 5d -3.8% / 20d -2.2%
  - 风格累计差(300−1000): 5d +1.7pp / 20d -2.3pp(近5日转向大盘)
  - 指数位置: 沪深300 距60日高 -5.2%,60日区间分位 18%
  - 宽度均值: 涨家占比 5d均值 38%(今日 35%)
  - 涨停温度: 涨停家数 5d均值 80(今日 48,退潮);最高连板 4;昨日涨停今日平均溢价 +1.2%
  - 成交额: 今日 1.42万亿(250日分位 68%);5d均值/20d均值 = 0.87(缩量)
  - 波动: 沪深300 20d年化波动 分位 62%
  - 两融(截至D-1): 融资余额 20d变动 +2.1%(分位 71%)【数据窗口硬性截止 D-1,见 §6.3a 类③】
◆ 持续性
  - 行业主线: 领涨前5与前5日领涨重合 3/5(银行/煤炭/公用连续,主线=红利防御)
  - 宽度连续: 涨家占比<45% 已连续 4 日
◆ 近3日重要政策(现有,保留)
```

实现要点:全部由 `build_card` 从已加载的面板扩展计算(mkt 面板已取 400 日、amt_daily 已有、
指数 parquet 已有 pct_chg 全史、涨停温度从事件库按 payload.day 聚合、两融从 provider `$rzye`
日 bin 聚合——**全部 ≤D 收盘可知,无新数据源**,昨日涨停今日溢价 = D-1 涨停名单在 D 的表现,D 收盘可知)。
"最高连板"从事件库连板高度 payload 聚合。**不喂 LLM 自己昨日的 regime 标签**(避免叙事自反馈,
v2 叙事记忆卡再议);持续性由确定性子状态行表达,LLM 自行归纳。

Prompt 影响:regime prompt 叙述上限 4 句→5 句;枚举 6 标签不变;锚外数字禁令不变(卡内数字变多,
禁令覆盖面同步变大);新增一句"归纳必须区分'今日边际变化'与'多日趋势'"。

### 1.3 优先级:P0(用户点名;无新数据源;纯 build_card 扩展)

---

## §2 基本面卡

### 2.1 现状与 PM 批评

现状:15 字段三锚定行(11 财务 + PE/PB/市值/换手)+ 业务构成 top5。

| # | 缺陷 | PM 视角 |
|---|---|---|
| 1 | **无时间维度** | 只有最新报告期一个点 + 10 年分位。基本面分析的核心动作是看**轨迹**:近 8 季营收/净利同比序列的方向与二阶变化(加速/减速)。"盈利拐点"维度现在是让 LLM 用一个点+一个分位猜拐点 |
| 2 | 估值锚单薄 | SMIC 案例:PE(TTM) 194 对亏损边缘半导体无意义,PS/股息率缺失。PE 高分位+PS 低分位是完全不同的故事 |
| 3 | 披露状态盲区 | 该股是否已出业绩预告/快报?预告方向?基本面席完全不知道(在消息席的卡里),它在用滞后一季的数据判断"拐点",而预告可能已宣告拐点 |
| 4 | **数字格式危险** | `总市值(万): 7.49326e+07`——科学计数法喂中文 LLM 是幻觉温床;`毛利率%: 17.6393` 四位小数是伪精度 |
| 5 | 杜邦无提示 | 净利率/周转/杠杆三件套都在卡内但 prompt 未点破,LLM 不一定组装 |

### 2.2 提案(基本面卡 v0.2)

1. **近 8 季核心序列节**(P1;**口径规则(自评 F3)**:必须单一 vintage——首选"D 日已知口径"
   (8 个季度全部按 D 日已知的最新值渲染,内部一致,适合拐点判断;需指标 q-slot 字段,实施前验证),
   不可用则退化为"各点当时已知值"的 vintage 序列并显式标注;**禁止**最新点用 D 日已知、
   历史点用当时已知的静默混合(§3.2 restatement 语义下两者可以不同)):
   ```
   ◆ 关键指标近8季(旧→新)
   - 营收同比%: 8.1 → 12.4 → ... → 26.5(加速)
   - 净利同比%: ... → -26.4
   - 毛利率%: ... → 17.6
   - ROE%: ... → 1.9
   ```
   「加速/减速/转正/转负」状态标签由代码判定(连续两季二阶同号),不留给 LLM 推断。
2. **估值节补 PS(TTM) 与股息率**(P1):`$ps_ttm`/`$dv_ratio` 均为 daily_basic 已批准字段,
   三锚定同格式。PE 为负时显示"亏损(PE 无意义)"而非数字。
3. **披露状态行**(P1,**设计争议点,交 GPT 裁决**,见 §6.4):
   `◆ 披露动态: 已披露至 2024Q3;业绩预告[2025-01-21 预增 50%-60%](来自事件库 direct)`
   ——这打破了"预告只在消息席"的现状,存在基本面席与消息席对同一事件双重计分的风险。
   备选方案 B:只给"已披露至 XQX + 是否存在预告(方向,不给幅度)"的最小状态行。
4. **格式规范**(P0):百分比 1 位小数;市值输出"749.3亿";比率 2 位小数;所有行带单位。

### 2.3 Prompt 影响

- `earnings_inflection` 锚改写:「看近 8 季序列的方向与二阶变化(代码已标注加速/减速),
  以及同比指标 10 年分位的相互印证」。
- 新增杜邦提示一句:「盈利质量可用 净利率×周转×杠杆 三行相互印证」。
- 若采纳披露状态行:加围栏「披露动态行只可支撑 earnings_inflection,不得重复支撑其他维度」。

---

## §3 技术面卡

### 3.1 现状与交易员批评

现状五子卡 37 项已较丰富(趋势/量能/筹码/主力/涨停语言)。批评集中在:

| # | 缺陷 | 交易员视角 |
|---|---|---|
| 1 | **单位不明** | `大单净流5d: -243177`——万元?千元?LLM 无从判断量级;`RS_vs_300_20d: 0.0046` 裸小数 |
| 2 | 无本股多窗收益 | 有距 52 周高/低和 60 日回撤,但无 5d/20d 本股收益——"这股票最近一周怎么走的"是交易员第一问 |
| 3 | 换手趋势缺失 | 有当日换手分位,无 5d 均值 vs 20d 均值(量能退潮/放大趋势) |
| 4 | **解禁盲区** | 未来 30/90 日限售解禁占流通盘比例——A 股最硬的日历型压力,整包没有(需 share_float 端点,未入库) |
| 5 | 龙虎榜席位性质 | top_inst 已入库,"机构买 vs 游资对倒"未进卡(事件库有方向,卡里只有 20d 次数) |
| 6 | 格式 | 比率类应显示为 %(`距52周高: -0.1052` → `-10.5%`) |

### 3.2 提案(pv_pack v0.2)

0. **P0 修复现存 PIT 缺陷(自评 F2,本审计的额外产出;实查 pv_pack.py 36-167 行确认)**:
   现行技术面卡四个项目读窗口 ≤D 但其 D 日值均为次日盘前才披露——
   `融资余额20d变动`/`融资买入占比分位`(两融,交易所次晨披露)与
   `北向持股比`/`北向20d变动`(hk_hold,港交所 CCASS T+1 晨披露)。
   在"D 盘后打分"会话中 D 日值不可知(单项一日级超前,幅度小但违反"卡片日期 D 只含
   D 收盘可知"契约)。修复:四项窗口硬性截止 D-1 + 行内标注"截至D-1"。
   同时按 §6.3a 复核龙虎榜类项目(交易所 D 晚间披露,事件库已保守戳 D+1 晨——
   卡内龙虎榜项与事件口径对齐,窗口 ≤D-1)。
1. **P0 格式与单位**:所有比率 → %(1 位小数);资金流标注单位(万元);消灭裸 4 位小数。
2. **P1 增项**(全部现有数据即可算):本股收益 5d/20d;换手 5d 均值分位与 20d 均值之比;
   龙虎榜最近一次的机构净买方向(来自 top_inst 事件 payload);大单净流占成交额比(量纲归一,
   替代裸金额)。
3. **P2 数据缺口**:share_float(限售解禁日历)入库 → `未来30/90日解禁占流通盘 %` 行。
   PIT 锚:解禁计划为公告披露的未来日程,按披露可见(ann_date 型),无穿越;按 §6.1 流程先读
   Tushare 文档再入库(v1.6 数据项,本提案只立项不实施)。

### 3.3 Prompt 影响

- `momentum_quality` 锚补一句:「本股 5d/20d 收益与 RS 相互印证;量价确认过的动量才可给 4-5」。
- 若解禁行落地:crowding/罚分区新增「解禁临近(30 日内解禁>流通盘 3%)按压力程度罚 2-4」。

---

## §4 消息面卡

### 4.1 现状与批评(信息面是当前最弱的卡)

| # | 缺陷 | 后果 |
|---|---|---|
| 1 | **行内无日期** | `render_news_card` 丢弃了 visible_at——LLM 判断 novelty/catalyst_timing 时完全不知道事件是昨天的还是 29 天前的。novelty 维度现在是盲打 |
| 2 | 无重要性标注 | 事件库有 importance_0_5,卡内不显示,让 LLM 从标题重推重要性 |
| 3 | **间接节被单一类型刷屏** | 实测 SMIC 0127:top15 间接事件 15/15 全是概念同伴业绩预告(相关度并列 0.49)。多样性为零,且"30 家概念股预告、18 家首亏"这个**截面信号**以 15 行零散标题的低效形态出现 |
| 4 | 直接节无上限 | 热门股 30+ 直接事件时卡会爆;无重要性×新近度排序 |
| 5 | 同源重复不聚合 | 3 条互动易-产能逐行列出 |

### 4.2 提案(news_card v0.3)

1. **P0 每行加相对时间与重要性**:`- [3日前|★★★★]研报点评|...|中性`。
2. **P0 间接节类型配额 + 返回集内聚合行**(自评 F5 修正后的口径):每 event_type 最多 3 行
   明细;同类型溢出的压缩成一条聚合行,**聚合范围 = 检索已返回的 top-25 集合内**
   (`- [概念聚合]业绩预告:top25内15条(利好5/利空10)`)——这才是纯渲染层操作。
   **真截面聚合**(概念组全体 31 条,不受 25 上限截断)无法从检索 parquet 算出,需要检索层
   自己产出聚合统计字段 → 属于检索层变更,`retr_v0.3` 版本升级,列为 P1.5(§6.5 修正)。
3. **P1 直接节排序与上限**:按 importance desc → 新近度 desc 取 top12,溢出聚合同上。
4. **P1 同源合并**:同 (event_type, source) 的互动易/研报按时间序合并为一行多值。

### 4.3 Prompt 影响(news prompt v2)

- novelty 锚改写:「novelty 看相对时间标注:7 日内首次出现的实质事件=高;30 日窗内重复/复读=低」。
- catalyst_timing 锚:「以行内相对时间与事件内声明的时点判断兑现窗口」。
- 聚合行规则:「聚合行属间接证据,封顶 3 分规则适用;聚合行可作为行业景气语境支撑 fundamental_link」。

---

## §5 空头席与裁判

### 5.1 空头席(prompt v2 提案)

现状:只看三席各自 top-2 主张。批评:真正的魔鬼代言人读**全部**评分,且最锋利的攻击是
**验证多头自己声明的证伪条件**。

1. **P1 喂全量 scorecard**(而非 top-2):token 成本 +~1k,对抗质量收益大。
2. **P1 证伪条件回验**(新机制,廉价而锋利):三席都输出了 `what_could_weaken`;
   空头 prompt 新增职责——「逐条检查三席声明的证伪条件,若卡内已存在满足该条件的行,
   这是最高优先级反驳(强度 5)」。席位自己声明的证伪点被卡内事实命中 = 结构性最强的反驳,
   且完全在 C16 围栏内(仍是逐字反证)。
3. 反驳目标维度须存在于对应席位权重表(现状已由裁判过滤,prompt 中明示可减少无效输出)。

### 5.2 裁判(不动)

确定性合成公式、折减、分歧度、背离旗:**本提案零改动**。理由:裁判是 C16 遏制的核心,
每次动它都要重新论证遏制完整性;输入端优化不需要动它。

---

## §6 横切与治理

### 6.1 数字格式规范(P0,所有卡统一)

百分比 1 位小数;金额自动选位(亿/万亿);比率 2 位小数;**禁止科学计数法**;每行单位显式。
理由:格式噪音是 LLM 误读/幻觉的直接温床,也污染逐字证据(span 里带着 `7.49326e+07`)。

### 6.2 Token 预算

现状四卡合计 ~3.1k 字符;提案后估计 ~5.5-6.5k 字符/股(情境卡 +0.8k、基本面 +0.6k、
技术面 +0.3k、消息面 +0.5k)。dimension_scoring max_tokens 4000 不变(输出端不变),
输入端远低于上下文限制。全月重放成本增量 <15%。

### 6.3 PIT 逐项自查(全部新增项)

| 新增项 | 数据源 | D 日可知性 |
|---|---|---|
| 指数/风格/宽度/涨停/成交额 5d/20d 滚动统计 | 已有面板向后窗 | D 收盘 ✔ |
| 昨日涨停今日溢价 | D-1 涨停名单 × D 行情 | D 收盘 ✔ |
| 两融余额 20d 变动 | `$rzye` 日 bin(approved) | T+1 披露 → **数据窗口硬截止 D-1** + 行内标注"截至D-1"(F1 修正,见 §6.3a 类③) ✔ |
| 近 8 季财务序列 | pit loader 已加载的季度史(lag-1) | ✔(与现有分位同源) |
| PS/股息率 | daily_basic bins(approved) | D 收盘 ✔ |
| 预告披露状态 | 事件库 direct(visible_at≤D) | ✔ |
| 本股 5d/20d 收益/换手趋势 | 已有 px 窗口 | D 收盘 ✔ |
| 解禁日历(P2,未实施) | share_float(未入库) | 公告披露锚,入库时按 §6.1 读文档定 PIT |

### 6.3a 可知性分类(自评 F4 新增;所有卡内项目必须归类,防未来漂移)

| 类 | 定义 | 窗口规则 | 卡内项目例 |
|---|---|---|---|
| ① 收盘派生 | 日线/指数/事件库行情事件 | ≤ D | 全部行情统计、涨停温度、昨日涨停今日溢价 |
| ② 晚间披露 | 交易所 D 晚间公布(龙虎榜/大宗) | **≤ D-1**(与事件库 D+1 晨可见戳对齐;D 晚间会话开始时未必已出) | 龙虎榜类项目、机构席位方向 |
| ①b 晚间供应商/交易所 | D 日值当晚更新但时刻无硬保证(cyq_perf 文档载 18-19 点;moneyflow/top_list 晚间、镜像文档未载时刻) | ≤ D **仅当数据就绪门通过**(见下),否则回退 ≤ D-1 + 行内标注 | 筹码五分位/获利盘、大单净流、龙虎榜金额 |
| ③ 次晨披露 | T 日值次日盘前公布(两融余额、hk_hold 北向持股) | **≤ D-1** + 行内标注"截至D-1" | 融资余额趋势(regime + pv 卡)、北向持股比/20d变动(pv 卡) |
| ④ 公告锚 | ann_date/visible_at 型 | pit loader lag-1 / visible_at ≤ D | 财务、预告状态、政策行 |

**数据就绪门(①b 类的运行时契约,前向必备)**:重放中 ①b 项目 ≤D 恒可得(历史数据齐全),
不构成穿越;**前向**装配卡片前必须逐数据集检查当日 ingest 完成戳(update_daily_data 产物),
未就绪的 ①b 项目自动回退 D-1 值并渲染"未更新(截至D-1)"。PIT 正确性由**运行时校验**保证,
不靠"通常 19 点前会更新"的假设。此契约写入 FORWARD_RETRIEVAL_PREREG 运维节。

### 6.4 双重计分争议(交 GPT 裁决)

预告/快报状态进基本面卡(§2.2-3)后,同一预告事件可能同时抬升基本面席 earnings_inflection
与消息席 event_materiality,composite 双重受益。三个方案:
- A(激进):完整预告行进基本面卡 + prompt 围栏「只可支撑 earnings_inflection」;
- B(保守):只给方向性状态行(预增/预减,不给幅度),幅度留给消息席;
- C(现状):基本面席保持盲区。
自评倾向 **B**(拐点判断需要知道方向,双计风险被"无幅度"钝化),请 GPT 裁决。

### 6.5 层边界声明(自评 F5 修正版)

检索层(倒排/通道权重/衰减/精筛/快照 id)在 **P0/P1 范围内一概不动**;渲染层可以做的仅限
"对检索已返回集合的呈现变换"(排序、类型配额、**返回集内**聚合、时间/重要性标注)。
**修正(F5)**:原稿的"概念同伴 30 日内共 31 条"式真截面聚合**不是**渲染层能力——检索 parquet
每股每日非直接项上限 25,真截面计数必须由检索层产出聚合统计字段,即 `retr_v0.3` 检索层版本
升级(P1.5,按 C16b 候选纪律走版本)。C16b 管检索配置候选;卡渲染变更走 chain 版本纪律
(chain_v2.0)。全部为重放期变更,NON_EVIDENTIARY;首轮前向前按 FORWARD_RETRIEVAL_PREREG
连同卡版本一起冻结。

### 6.6 版本与实施切分

- **chain_v2.0**:cards v0.2/0.3 + prompts v2(四席)+ regime 卡 v0.2。一次性升级,
  不做逐项小版本(避免版本碎片;#10 全月重放直接用 v2.0 输入跑,与 chain_v1.x 档案不混)。
- 实施顺序:P0(情境卡三节 + 全卡格式 + news 日期/重要性/配额)→ P1(8 季序列/PS/披露状态
  按 GPT 裁决方案/换手趋势/空头全量+证伪回验)→ P2(share_float 立项,独立数据 PR)。

---

## §7 结构化自评(§10 self-review;对抗性执行,2026-07-09 第二轮)

### 7.1 自评发现(对本提案自身的评审;F1-F5 修正已全部写回上文)

| # | 级别 | 发现 | 处置 |
|---|---|---|---|
| F1 | Major | 情境卡两融行原稿只要求"标注截至D-1",未硬性要求**数据窗口截止 D-1**——两融 T 日余额次日盘前才披露,D 盘后会话不可知(标注≠正确) | 已改 §1.2:窗口硬截止 D-1 + 标注 |
| F2 | Major(**现存缺陷**) | 现行 pv 卡**四个项目**窗口 ≤D 但 D 日值次晨才披露:两融两项 + 北向两项(`北向持股比`/`北向20d变动`,hk_hold CCASS T+1 晨)→ 现行卡有一日级 PIT 超前(幅度小,契约违反)。本审计的额外产出 | 已立 §3.2-0 为 v2.0 P0 修复项;龙虎榜类项目一并按 §6.3a 复核 |
| F3 | Major | 8 季序列的 vintage 口径原稿未定义——§3.2 restatement 语义下"当时已知"与"D 日已知"可以不同,静默混合不一致 | 已改 §2.2-1:单一 vintage 规则(首选 D 日已知,退化需标注,禁止混合) |
| F4 | Major | 缺"可知性分类"框架,F1/F2 型错误会随加项复发 | 已新增 §6.3a 四类窗口规则,全部项目必须归类 |
| F5 | Major | 原稿"概念同伴30日内共31条"真截面聚合**超出渲染层能力**(检索 parquet 有 25 上限截断),"检索层一概不动"的边界声明不成立 | 已改 §4.2-2/§6.5:返回集内聚合=渲染层(P0);真截面聚合=retr_v0.3 检索层版本(P1.5) |
| F6 | 已证实 | `$ps_ttm`/`$dv_ratio` 批准状态 | 实查 field_status.yaml daily_basic approved 列表(94-99 行)✔;两融披露时点 Tushare 镜像未载,采用对披露时刻稳健的保守规则(≤D-1) |

### 7.2 原则逐条核查

**§3 硬不变量**:不触碰 provider/账本/注册表/回测引擎;全部读数走既有 sanctioned 门
(pit loader 面板、provider bins、事件库);无新 D.features 裸调;Tushare 零新抓取
(share_float 仅立项,入库时按 §6.1 先读文档)。✔
**PIT**:§6.3 逐项表 + §6.3a 可知性分类;F1/F2 修正后所有项目有明确窗口规则;
宽度/温度统计在全市场面板上计算(含停牌名,按日 NaN 剔除),无幸存者过滤。✔
**反馈回路**:regime 卡不喂 LLM 自身历史标签;无任何"分数→输入"回路;空头证伪回验消费的
是席位声明文本,反驳仍须卡内逐字反证(接地校验兜底)。✔
**C16 遏制**:LLM 输出 schema 零变化;裁判零变化;所有变更在输入端。✔
**C15**:卡内容变化不改 payload=数据地位;席位 what_could_weaken 文本进空头 payload
同样受 C15 约束(不可执行指令)。✔
**多重检验/OOS**:无评分口径用于选股(composite 仍 research_summary 禁入);
一条新增纪律——**卡版本取舍只能以信息设计论证,不得以"哪版重放分数好看"选版本**
(否则是非正式的重放调参,违背 NON_EVIDENTIARY)。✔
**无对冲措辞**(memory 纪律双查):(a) OOS 引用追踪——全文无 OOS 选择器引用;
(b) 引用数字时效——未引用任何 §3 标记为 stale 的数字;实证引语(15/15 刷屏、卡片原文、
字段批准状态)全部为 2026-07-09 平台/注册表实查。✔

### 7.3 留给 GPT 的真问题(自评无法裁决)

① §6.4 双重计分方案 A/B/C(自评倾向 B);② 空头席全量 scorecard 的 token/对抗质量权衡;
③ 情境卡三节化后 regime 6 枚举是否需要"趋势中继/转折候选"类第二轴;
④ 返回集内聚合行的 prompt 围栏是否足以防止 LLM 把间接截面信号当直接证据;
⑤ F2 修复的波及面判断(现行 149 份档案的技术席分数受一日级两融超前影响,是否需要在
档案页标注,还是等 v2.0 重建自然覆盖)。

### 7.4 结论

第一轮自评(原 §7)结论"clean for GPT"**过早**——第二轮对抗性执行发现 5 项 Major
(其中 1 项现存缺陷),全部修正/立项完毕。**修正后结论:clean for GPT。**

---

## §8 PIT 系统清查(全输入项逐一归类;2026-07-09 第三轮,用户指令)

方法:枚举四张卡的**全部数据源字段**(pv_pack FIELDS 23 项、fact_table 15 字段、regime 7 组、
retrieval/事件库),逐项归入 §6.3a 可知性类,标注 D 盘后会话可知性。

| 数据源 | 卡内项目 | 类 | 判定 |
|---|---|---|---|
| 日线 OHLCV/pre_close/adj_factor/up·down_limit | 全部趋势/量能/涨停语言项、regime 宽度/温度 | ① | ✔ D 收盘 |
| daily_basic($turnover_rate/$volume_ratio/$pe_ttm/$pb/$total_mv + 拟增 $ps_ttm/$dv_ratio) | 换手/量比/估值行 | ① | ✔ Tushare 盘后 16-17 点落地 |
| 指数日线(pct_chg) | regime 指数/风格/轮动 | ① | ✔ |
| moneyflow($buy/sell_sm·lg·elg_amount) | 大单净流5d/20d、同向天数、大小单形态、净流强度 | **①b** | 重放 ✔;前向走数据就绪门(镜像文档未载更新时刻) |
| cyq_perf(cost_5/15/50/85/95pct、winner_rate) | 获利盘、成本分位距、筹码集中度 | **①b** | 重放 ✔;文档载 18-19 点更新,前向走就绪门 |
| top_list($top_list__amount) | 龙虎榜20d | **①b** | 同上;注意与事件库 D+1 晨可见戳的口径差在就绪门下消解 |
| margin_detail($rzye/$rzmre) | 融资余额20d变动、融资买入占比 | **③** | ✘ 现行 ≤D 为一日级超前(F2)→ v2.0 硬截 D-1 |
| hk_hold($ratio) | 北向持股比、北向20d变动 | **③** | ✘ 同上(F2)→ 硬截 D-1 |
| pit loader 11 财务字段(lag-1) | 三锚定行、拟增 8 季序列 | ④ | ✔ 系统最强锚 |
| fina_mainbz(income ann_date 联接) | 业务构成节 | ④ | ✔ 报告期+可见性双标注 |
| 事件库(visible_at) | 消息卡全部行、regime 政策行(≤D 10:00) | ④ | ✔;消息卡检索 cutoff D 09:15 比盘后口径更严 |
| 行业归属(industry_as_of) | 行业分位、RS 行业分位 | ④ | ✔ 申万 PIT 区间 |
| trade_cal | 决策日序列 | — | ✔ |

**清查结论**:除 F2 的四项(两融×2、北向×2,已立 P0 修复)外,重放口径下无其他超前项;
前向口径下 ①b 三数据源(moneyflow/cyq_perf/top_list)的正确性依赖**数据就绪门**(§6.3a),
这是从"假设按时更新"到"运行时验证"的升级,为前向必备件。
另注:关注度(attention)含 top_list 分量,但它只进平台展示,不进任何 LLM 卡,无 PIT 影响。

---

## §9 LLM 性能榨取(机构分析师视角:同样的模型,如何拿到更好的输出)

原则:所有手段分两类——**输入端信息设计**(让证据更可发现)与**推理端引导**(让模型
把已有信息用尽);两类都不得触碰 C16 遏制(总分/建议永远是代码)。每项标注预期收益/成本。

### 9.1 输入端:信息设计六式

1. **行 ID 编号(高收益,近零成本)**:全部卡行加稳定编号(`F03`/`T21`/`N07`),
   evidence_spans 引用"ID+原文"。接地校验从 8-160 字模糊匹配升级为 **ID 精确匹配+文本一致**
   双重验证;证据独占从模糊归一升级为 ID 集合不相交。副作用:span 更短,输出 token 更省,
   平台上证据高亮可精确定位。
2. **确定性焦点旗(高收益,低成本)**:代码预计算每卡 top-3 异常并加「⚑」标注——
   三锚定背离(|行业分位−10年分位|>50pp,如 SMIC 现金流行业分位94%/10年分位22%)、
   极端分位(>90/<10)、量价背离确立。LLM 对显著性标注的注意力远高于自行扫描 15 行;
   旗标是**事实标注**不是意见(不写"利好/利空")。
3. **负面缺席声明(中收益,低成本)**:消息卡尾行
   `- [N15]检索窗口内无:减持/质押/监管处分/诉讼类直接事件`。
   "没有红旗"是治理维度的正面证据,但 LLM 无法从空列表安全推断缺席——显式声明使
   governance_flag 可以有据打 0 而非弃权。直接通道检索无 25 上限截断,渲染层可算(F5 边界内)。
4. **同业对标行(中收益,中成本)**:基本面卡每关键指标加"行业中值/龙头值"
   (`毛利率 17.6 | 行业中值 24.3 | 行业90分位 41.2`)——分位数告诉 LLM 位置,
   对标值告诉它**距离**,后者是分析师实际使用的语言。代码从既有全市场面板算,无新数据。
5. **行业情境行进技术卡(中收益,低成本)**:互盲挡的是**观点**不是**事实**
   (market_context 先例):技术卡加一行
   `- [T00]所属申万行业: 半导体;行业指数 5d -4.2% / 20d -8.1%`,
   使 RS 判断有绝对基准(跑赢一个暴跌行业 ≠ 强)。
6. **事件全景计数行(低收益,低成本)**:消息卡头部加
   `- [N00]30日窗口: 直接事件 7 条(公告4/研报2/互动易1),间接 25 条`——
   给 LLM 信息密度总览,校准"novelty/materiality"的相对判断。

### 9.2 推理端:引导五式

1. **证据先行的字段序(高收益,零成本)**:现行 schema
   `{"name","score_0_5","evidence_spans"}` 让自回归模型**先写分后抄证据**——分数没有条件在
   证据上。改为 `{"name","evidence_spans","score_0_5"}` + prompt「先抄证据行,再打分」,
   打分被强制条件在刚抄写的证据上。这是 LLM 工程里最便宜的接地强化,一行 schema 顺序。
2. **检查单式席位职责(中收益,零成本)**:prompt 从"人设"升级为"决策程序":
   基本面席「①先读⚑焦点旗 ②盈利质量三件套互证 ③增长方向×行业分位 ④拐点看 8 季序列
   二阶 ⑤最后才看估值」。检查单降低维度-证据错配率(实测档案里存在把成长证据挂到
   盈利质量维的案例)。
3. **结构化证伪条件(中收益,低成本)**:`what_could_weaken` 从自由文本 ≤20 字升级为
   `{"condition":"...","observable_in":"fund|tech|news|market"}`,空头席的证伪回验
   (§5.1-2)从语义匹配变成机械可查,裁判可统计"证伪条件已命中数"进档案。
4. **thinking 预算按席位分层 + 截断遥测(低收益,防御性)**:消息/空头卡变厚后,
   记录每次调用 finish_reason,截断率>1% 的席位提升 max_tokens(历史上 thinking 耗尽
   出过空 content 事故)。
5. **温度与自洽性(条件启用)**:先在重放测**评分信度**——同一输入跑 3 次的维度分方差
   (20 名抽样 ×3);若测得方差实质影响排序带,再上**自适应集成**(仅对三席分歧度>阈值或
   composite 处于决策边界带的名字做 k=3 取中位),把 ~3 倍算力花在不确定的 10-20% 名字上,
   而非全池。**先测噪声,再买算力。**

### 9.3 度量纪律(不可回避的前提:榨取要可证明,且不许在重放上调参)

- **过程质量指标(重放即可测,与收益无关,允许用于 AB)**:接地通过率、维度覆盖率
  (scored_dims/total)、证据独占违规率、adj−final 折减幅、空头反驳有效率、
  证据多样性(被引用行数/可引用行数)、评分信度(重测方差)、截断率。
- **预测质量指标(禁止在重放上优化)**:任何"哪版输入让分数更能预测收益"的比较都是
  在 NON_EVIDENTIARY 重放上做隐性选择 → 只允许 golden set(人工标注 ~50 股·日,
  v1.5 待办)与 PREREG 后的前向累积作为准绳。
- **版本选择只以信息设计论证**(§7.2 已立),过程指标佐证,预测指标留给前向。

### 9.4 明确不做(与更高层治理冲突)

- ❌ 喂 LLM 上一会话自身评分/叙述(叙事自反馈;v2 叙事记忆卡有独立治理再议);
- ❌ 让 confidence 进裁判权重(LLM 借道影响合成=遏制蠕变;可作诊断字段记录不消费);
- ❌ few-shot 完整评分范例(锚定污染:模型复读示例分布;仅允许边界锚点措辞);
- ❌ 在重放分数上择优选 prompt/卡版本(见 §9.3)。

---

## §10 GPT 跨审裁定与处置(2026-07-09,补审完成)

**裁定:REVISE**(5 Blocker / 8 Major / 7 Minor + Q1-Q12 全答)。核心批评:
"prompt 层围栏未机械执行,未经校验的 LLM 输出能确定性改分数" —— 全部成立。
处置(chain_v2.1,全部实施并有回归测试):

| # | Blocker | 修复 |
|---|---|---|
| B1 | 档案版本隔离破缺(旧 v1.0 档案被无条件复用;平台把 v2 卡渲在旧分旁) | 档案改 `analyst_chain/<chain_version>/<date>/` 目录;只有版本完全一致才复用;每版本 manifest.json(prompt 哈希/卡版本/配置指纹);存量 149 档案迁入 chain_v1.0/ 并补记 manifest(注明 v1 prompt 其后被原地修订非冻结快照);平台按版本取数,非现行版本不重渲卡片只读档案+raw;RENDER_VERSION==CHAIN_VERSION 由测试断言 |
| B2 | 注册维可重名双计(复现:同维两条 ×2 计分) | scorecard 重名**无条件拒收**(所有消费者的 C16 漏洞);注册维恰一次/分数域 finite∈[0,5] 硬失败/证伪 schema 为 **opt-in** 严格参数(冻结 MVP 默认行为不变);tests/ai_layer 50/50 绿 |
| B3 | 空头输出未 typed 校验即改分(strength=999 曾被接受) | `validate_bear_record` fail-closed 逐条丢弃:精确键集/席位-维度配对/强度域/文本上限/counter_quote 必须整行;strength=5 仅限携带有效 falsifier_id(机械回验快径),否则降 4;裁判只消费校验后反驳 |
| B4 | 行 ID/独占/围栏只在 prompt | `validators.enforce_v2_evidence`:span=「[ID]+完整行」精确匹配(子串拒收);独占按行 ID 全席去重;news 间接证据→分数确定性钳 ≤3;披露行(FD1)非 earnings_inflection 引用即剔除;行 ID 改**固定语义注册表**(F/FS/FD/FB/TA-TE 按字段注册,缺项不移位;news 动态节 event_id 平局裁决) |
| B5 | 历史聚合用决策月幸存者 universe(漏 52 只回看期名字) | regime+pv 的 instruments 按**完整回看窗**解析,按日 NaN 剔除;布局回归测试落盘 |

**Major 处置**:涨停温度史改 bins 全窗直算(400 日预热,连板/昨停溢价用交易日历语义,弃事件库依赖)✔;两融分位改算在 `pct_change(20)` 序列上(水平分位配变动值是误导)+ pv [-21] 基准 ✔;净流强度 `net/(amount/10)`(旧式错 100 倍)、融资买入占比 `(rzmre元/1000)/amount千元` ✔;红旗缺席改**类型+标题谓词**(修复"卡内有董监高减持却声明无减持")✔;news 间接明细补龄+星标、聚合按通道×类型分组带龄距、直接节同源(类型,来源)≤2 超额聚合(retrieval 透传 source)✔;序列节显示采样日+真二阶(穿零优先,相邻差分判加速)✔;NaN 估值行显式状态(亏损/未披露,NaN≠0)✔;空头 payload 补全(证据不截断+罚分含证据+market_context)✔;行业中值/90 分位对标列 ✔(Q7);事件标题百分数 1 位小数 ✔;市值≥1万亿切万亿 ✔;成分等权收益如实命名 ✔。

**声明式延后(带理由)**:①"已披露至 XQX"行——需扩展 pit_research_loader API 暴露可见报告期
(sanctioned 门变更,独立 PR;直读账本被禁);②top_inst 机构方向行、大宗折溢价行、股东户数行
(Q7)——需事件 payload 抽取管线,列下一输入批次;③①b 数据就绪门实现——前向期前置件,规格已
按 Q10 升级(分页完成/schema/行覆盖/空源白名单/精确 as-of/内容哈希/消费快照冻结,部分 D/D-1
混合=失败);④golden set 按 Q12 协议(300-500 分层决策时点盲样/双标注+仲裁/冻结 rubric/
留出子集/prompt 作者不得独任标注)——建库时执行。

**Q1-Q12 采纳**:全部按裁定执行(Q2=B 方案代码围栏 ✔;Q3 返回集配额=渲染层合法、真截面聚合
=retr_v0.3 ✔;Q5 展示采样日+计算二阶 ✔;Q8 顺序=正确性优先,**#10 全月重放推迟到本轮全绿后**;
Q11 ⚑ 旗保留但准则冻结且方向中性,消费率进过程指标)。

### §10.2 复审#2 裁定与处置(2026-07-10,chain_v2.2)

**裁定:REVISE**(4 残余 Blocker + 4 Major;GPT 用对抗性输入复现全部成立)。处置:

| # | 残余 Blocker | chain_v2.2 修复 |
|---|---|---|
| B1' | **同版本漂移**:版本号相同即复用旧分,manifest 每次运行被覆盖,平台把新渲卡摆在旧分旁 | `ensure_immutable_manifest`(首次写入定格指纹,漂移=VersionCollisionError 硬失败)+ **artifact_fp 逐档输入绑定**(manifest_fp × 精确输入快照哈希;不一致=硬失败,禁止静默复用)+ **完整性感知复用**(失败席/空头失败的档案=不完整,重算覆盖,绝不固化)+ **档案落精确快照**(cards/market_context/validated records 全存档,平台对已完成工件展示归档快照绝不重渲,cards_source 标注) |
| B3' | **单条畸形字段清空整只空头**(list 值 target_seat/falsifier_id 触发 TypeError→空空头被归档固化) | validate_bear_record 逐条健壮化:类型检查**先于**成员检查;bool/字符串数字/NaN/域外强度=单条 strength drop;非字符串 fid 不入集合成员测试;kill_switches/blind_spots 非列表不迭代;空头失败档案经 B1' 完整性规则不可复用 |
| B4' | **聚合行绕过 ≤3 钳位**(渲染词匹配漏 `[NDA]`/`[关联]`/`[N00]`;实测 NDA 行 5 分漏网,月度 1,077 条 NDA) | `_news_requires_cap(lid)` 按**注册 ID 类**判定(N00/NI*/NIA*/NDA* 钳,ND/NX 不钳);回归测试覆盖 NDA 带龄距/关联通道/N00 |
| B5' | **pv 仍未通过 5455 复现**(110d mkt_start 窗仍是 5403) | avail 改用 **420d start 窗**解析(读窗≠解析窗;60d RS 的 D.features 读数仍由 mkt_start 界定) |

**Major 处置**:①独占改**两遍计数**——被争用行 ID 在所有条目一律作废(顺序无关;同内容换序 10→5 的复现进回归测试);②平台 raw 路径**防穿越**(`safe_raw_dir`:已知链集合+day/code 严格正则+resolve 后包含性断言;`day=../chain_v1.0/...` 注入用例进测试)+ /api/archives|dept|reasoning 全部校验 chain;③空头收 market_context(regime 卡 v0.4 加固定 M01-M16 行 ID,市场行可被引用为反证)+ 证伪注册表带元数据 `{fid:{seat,observable_in}}`,strength=5 快径要求**席位绑定**;④事件库行情/停复牌/修正潮生成器扩 **30 日预热交易日**(首决策日检索窗不再伪冷启动)。
**Minor 处置**:scorecard 名称必须非空字符串+seen 集合去重(NaN 名封死);标题 canonical `_t70` 全渲染点统一;event_id 哈希**全文标题+来源**(截断只在显示层);attention 标注"金股池内截面分位,不进 LLM 卡";证伪规范化损失计数进档案(`falsifier_norm`);bear `parse_mode` 记录+宽松解析再失败归一 ArkClientError。FB 位置 ID 经 B1' 快照冻结后被 GPT 认可保留。
**R3 采纳**:强度 5 锚改为"且仅=席位绑定+机械确认命中的注册证伪条件;4=同维直接反证或跨证据强冲突"(prompt 待 v2.2 重放前更新——判定阈值 ≥4 不变,语义收紧)。
**R4**:loader 扩展/top_inst 行/golden set 可延后过重放;①b 就绪门+golden set 仍为前向/证据级使用的强制前置。
**测试:73/73 绿**(+23 条复审#2 回归)。

### §10.3 复审#3 裁定与处置(2026-07-10,chain_v2.3)

**裁定:REVISE**(3 Blocker + 4 Major + 2 Minor;核心:评分契约不在指纹里/磁盘自称指纹被信任/
顶层 schema 损坏的空头可装完整)。处置:

| # | Blocker | chain_v2.3 修复 |
|---|---|---|
| B1'' | 改席位权重不动 manifest_fp → 同版本静默复用旧规则产物 | manifest 绑定**完整评分契约**:确定性引擎代码字节哈希(analyst_chain/cards/validators/scorecard 四文件)、有效 prompt 全文(含 SYSTEM_C15)+逐文件 sha256、seat_weights/composite/折扣阈值/背离阈值快照、LLM 路由快照 |
| B2'' | manifest/档案/平台信任磁盘自称指纹(篡改正文保留旧指纹曾被接受;伪造 composite=99.9 被复用) | **验证不信任**([integrity.py](engine/integrity.py) 纯模块,链与平台同一把尺):manifest 正文重算复核;档案增 `archive_sha256` 输出正文封印,复用前重算 存档输入指纹+封印+chain/date/文件名/manifest_fp 五重校验;manifest 首写 file_lock+临时文件+os.replace 原子发布;平台**加载即验证**,不符拒载并告警 |
| B3'' | `refutations` 非列表被静默洗成空列表 → "空但正常"空头 + 单席/无 bear 曾判完整 | `schema_valid` 顶层容器校验写入 bear 结果;`archive_complete` 严格化:三席**恰好齐全**+final 有限实数+records 齐全+bear schema_valid+parse_mode∈{strict,lenient}+kill_switches 非空+judge finals 齐全(逐条 validation_dropped>0 仍算技术完成) |

**Major**:①`float(10**10000)` OverflowError 防护(validators 单条 drop;scorecard 严格路径→ScorecardViolation、非严格→NO-SCORE;错误消息 repr 受保护——修复中发现 repr 自身也会触发 int→str 上限);②批处理失败语义:不完整档案计 failure、退出码 2,VersionCollisionError 全体撤单上抛,LLM 提交前对已有档案全量指纹**预检**;③attempts 审计结构(`day/attempts/<code>/attempt_NNNN/{raw,archive.json,status.json}` + append-only attempts_ledger.jsonl,失败 raw 永不被覆盖;完整结果原子发布到 `day/<code>.json`);④前端 chain 全链传播(analysis→dept/stock 链接、department/stock 页 fetch 全带 chain)+ 归档视图从**冻结 manifest** 返回 prompt/routing/weights(contract_source 标注),不读当前进程。
**Minor**:strength=5 快径增加 **observable_in 域校验**(反证行 ID 前缀→域,须∈证伪声明域;observable_in=fund 引 M 行不再保 5);事件预热窗首多取一个开市日;regime 首日 M14 用前一交易日轮动初始化。
**测试:92/92**(+19 条复审#3 回归,含篡改正文保留指纹/伪造输出封印识破/单席判完整复现/超大整数)。

### §10.4 复审#4 裁定与处置(2026-07-10,chain_v2.4)

**裁定:REVISE**(3 Blocker + 4 Major + 2 Minor)。处置:

| # | Blocker | chain_v2.4 修复 |
|---|---|---|
| B1''' | **删字段降级封印**:删 cards/archive_sha256 重封印后档案被当 legacy 绕过校验;缺 manifest_fp 的 manifest 平台跳过验证 | manifest 声明 `integrity_schema=1`+`sealed_required=True`;`verify_archive_body(require_sealed=True)` 必需字段(manifest_fp/artifact_fp/archive_sha256/cards/market_context)缺失即硬失败,封印**无条件重算**;legacy=平台 `LEGACY_CHAINS` **显式 allowlist**(绝不由缺字段推断);声明 schema 却缺 fp 的 manifest 本身违规 |
| B2''' | **冻结 prompt 未被执行**:manifest 存快照但每股仍重读磁盘,同一 manifest_fp 下可混用两套 prompt | `read_prompt_bundle()` 只读一次 → `build_manifest(bundle)` → **`ChainContract.from_verified_manifest`**;run_stock 只接受已验证契约(裸 manifest_fp 参数删除),run_seat/run_bear 从契约取有效 prompt(含 SYSTEM_C15,不再拼接) |
| B3''' | **缺输入静默退出 0**:inputs=None 既不算成功也不算失败;预检逐日,后期碰撞前早期日已花钱 | **全月预检**(全部日×股)先于任何 LLM 提交;缺输入→`run_status.json{status:failed_preflight}`+退出 2;结束时机械断言 `complete==expected` 否则退出 2;`run_status.json` 持久化完成标记(崩溃后部分月与完整月可区分) |

**Major**:①attempts **状态机**(`started→attempt_completed/attempt_failed→published` 全程 ledger 留痕;编号=跨进程 file_lock 下 max(解析编号)+1+`mkdir(exist_ok=False)`,稀疏编号 {0001,0003} 不再重复分配;ledger 跨进程锁+flush+fsync;published 事件在 os.replace **之后**;意外异常写 failed status 后上抛)+ 版本级 `.batch.lock` 单实例(第二实例 BatchInstanceError);②契约文件扩到 **7 个**(+integrity.py/llm_config.py/ark_client.py;项目相对路径前缀;PIT loaders 不入——其产物已由 artifact_fp 绑定,GPT 认可);③claim/reason 类型总函数(10**10000 claim 曾炸穿 `_norm(str())` 波及合法兄弟;list/dict 曾被当文本)+ `_valid_final` 总函数 + archive_complete 全输入 dict 校验;④平台验证状态**外置**(`archive_verification` 字典,不再写 `_verify` 进封印正文——曾使 API 返回的档案不再匹配封印)+ `/api/meta` 暴露 `integrity_status`(loaded/rejected/原因)+ RENDER_VERSION manifest 损坏时**不静默回退旧版本** + JSON 解析异常计入拒载。
**Minor**:`archive_sha256`/新增 `manifest_sha256` 用**完整 64 位**摘要(语义指纹 manifest_fp 保持 16 位短 ID);archives.html 加链版本选择器,日期按 `archive_days_by_version` 填充,分析链接带 chain。
**测试:111/111**(+19 条复审#4 回归:逐字段删除降级、稀疏编号、总函数、claim 类型)。

### §10.5 复审#5 裁定与处置(2026-07-10 收到,chain_v2.5;此前一次贴回为复审#4 旧裁定
原文——已机械核对其全部条目在 HEAD 已修复,未采取行动;本节处置对 66a33e6 的真实复审)

**裁定:REVISE**(3 Blocker + 3 Major + 1 Minor;R2 追加裁定:评分参数**必须**从不可变契约
执行、单文件互覆盖 run_status 不可接受、直跑写正式目录需逐股锁、非 legacy 无条件要求封印)。处置:

| # | Blocker | chain_v2.5 修复 |
|---|---|---|
| B1⁗ | **ChainContract 可伪造 + 评分参数仍从可变全局执行**:直接实例化 dataclass 配真 manifest_fp 即通过;运行中改 SEAT_WEIGHTS 全局即改分,档案无从自证执行契约 | 契约**只能 `ChainContract.load(vdir)` 对盘构造**(验 chain_version/schema=2/sealed_required/manifest_sha256/prompt 逐文件哈希/评分契约存在);`_deep_ro`(MappingProxyType 深只读——frozen dataclass 挡不住改内部字典);run_stock 入口 `verify_contract_matches_manifest`(与磁盘 manifest 五项逐比,伪造构造器+真指纹组合识破);**评分参数从契约执行**(run_seat weights / run_bear seat_weights / judge scoring / archive_complete scoring 全走 `contract.scoring`,改模块全局无效);档案新增必带封印字段 **`executed_contract_sha256`**(=契约 manifest_sha256,复用/平台加载均与版本 manifest 对照) |
| B2⁗ | **平台自声明降级**:manifest 写 `sealed_required:false` 即让新版本只过结构检查(自声明字段决定校验强度) | 非 legacy 版本**无条件要求封印**:manifest 必须声明 sealed_required=True + integrity_schema≥1 + manifest_sha256,否则**整版本拒载**(降级=拒载理由,不是校验开关);封印字段集按 `integrity_schema` 分级(schema1=v2.4 五字段,schema2=v2.5 +executed_contract_sha256——新字段不追溯拒掉 v2.4 真封印档案,引擎侧只产/只验 schema2);封印版本加载再过共享 `verify_archive_semantics` |
| B3⁗ | **完成范围无绑定**:烟测(--day/--names)同样写 run_status.json 覆盖月度标记;"complete" 只是对本次参数的断言,无从区分全月 | manifest 绑 **`job_spec` 全月范围**(完整 日×股 集合 + `job_set_sha256`,预检/参数无关);运行范围摘要==job_spec 才算 full_month,否则 scope_kind=smoke;**`full_month_status.json` 只由全月范围运行写**(烟测机械不可能触碰);新增 append-only **`runs_ledger.jsonl`**(run_started/run_failed_preflight/run_aborted_collision/run_finished,file_lock+fsync,run_id 逐次);**终局重验**:完成度不用内存计数——对每个计划名·日从磁盘重读+全封印验证+`archive_complete` 后计数,并算 `archive_set_sha256`(全部通过档案封印的集合摘要)落台账;run_status.json 降级为"最近一次运行"便捷指针 |

**Major**:①缺输入=**MissingInputError**(直接调用不得静默 None;批预检仍先行过滤)+ run_stock 全程**逐(日,股)跨进程锁**(`.{code}.stock.lock`,从档案检查持有到发布结束——并发双跑互覆盖窗口关闭);②`_safe_error` 错误格式化总函数(`RuntimeError(10**10000)` 曾让 except 路径的 f-string 二次爆炸)全 except 路径统一 + **publish_failed** ledger 事件(os.replace 失败留痕后上抛)+ **启动对账** `_reconcile_ledger`(published 事件↔磁盘档案互相印证,单侧存在=异常,记 runs_ledger 后开跑);③`verify_archive_semantics` 共享语义校验(integrity.py,引擎 archive_complete 与平台加载同一把尺):seats/records 键集==评分契约、final/finals [0,100] 有限、judge.finals 逐席==seats.final、composite 按契约权重**重算复核**(±0.11)、bear.refutations dict 列表、kill_switches 非空**字符串**列表——空 records 条目/字符串 kill_switches/伪造 composite 全部点名。
**Minor**:平台 manifest/档案解析 except 补 `ValueError`;/api/meta 暴露 `full_month_status`(按版本,只信引擎终局重验写下的文件)。
**测试:134/134**(+22 条复审#5 回归:伪造契约/深只读/降级 manifest 拒作契约/prompt 哈希不符/缺·错 executed_contract/schema 分级/job_spec 范围/烟测范围不匹配/MissingInputError/_safe_error 超大整数/语义校验 6 复现/平台版本断言)。

### §10.6 复审#6 裁定与处置(2026-07-11 收到,chain_v2.6;版本 bump 因修复改变冻结引擎契约——GPT R4 裁定)

**裁定:REVISE**(2 Blocker + 1 Major;R1 确认既往复现全部通过,新缺口如下)。处置:

| # | Blocker | chain_v2.6 修复 |
|---|---|---|
| B1⁵ | **评分契约仍 fail-open**:缺 `bear_discount_strength`/`divergence_gap` 的自洽 manifest 通过 `ChainContract.load`,judge 经 `.get(…, 全局)` 回退——改全局把 adj 15→30;平台侧 `scoring.get("seat_weights")` 条件让**无评分契约的版本跳过语义校验**(GPT 复现:schema-2 空档案无 seats/records/bear/judge 被 sealed_ok 加载) | 共享 **`verify_scoring_contract`**(integrity.py,`REQUIRED_SCORING_KEYS` 四键齐全+seat/composite 键集一致+折扣∈[0,5]/背离∈[0,100] 有限数):`ChainContract.load` 与平台版本加载**同拒**(缺=整版本拒);`judge`/`archive_complete` 持契约时**直接索引、无回退**(缺键=KeyError/False,scoring=None 仅测试路径);平台语义校验对封印档案**无条件执行**(评分契约已在版本级验完备) |
| B2⁵ | **full_month_status 被平台原样信任**:GPT 种下伪造 2384/2384 marker(错 job 哈希+错档案集哈希),平台原样暴露 | **`validate_full_month_status`**(纯函数,server.py):marker 移到**档案加载之后**验证——scope_kind==full_month、job_set_sha256==manifest.job_spec、expected==job_spec、complete==磁盘已验证档案数、archive_set_sha256==已加载档案封印集重算,五重全过才暴露;任何不符 = `{status:"integrity_failed", problems:[…]}` + integrity_status 告警(伪造 marker、事后删档、同数换档全部点名——终局重验→平台链路闭合) |

**Major(残余关切 (a) 被裁定不可接受)**:平台 `SCHEMA1_CHAINS = {"chain_v2.4"}`——`integrity_schema=1` 只承认 v2.4 这一个历史版本,后续版本自声明 schema=1(借以绕过 executed_contract 绑定)= 整版本拒载(GPT 复现 chain_v9.9 schema-1 曾 sealed_ok)。关切 (b)(c)(d) 裁定可接受:对账 report-only 保留、逐股锁 30s 超时、每股一次 manifest 读开销可忽略。
**测试:159/159**(+25 条复审#6 回归:四键逐一缺失/坏值域/load 拒不完备契约/judge 缺键 KeyError 不回退/持契约改全局 inert/archive_complete 畸形契约 fail-closed/月度 marker 伪造·删档·换档·smoke-scope 全拒/schema-1 allowlist)。

### §10.7 复审#7 裁定与处置(2026-07-11 收到,chain_v2.7;版本再 bump 因修复改变冻结引擎契约——GPT R4 裁定)

**裁定:REVISE**(4 Blocker,0 Major/Minor;R1 确认复审#6 全部复现通过,新对抗测试打开 4 个新缺口)。处置:

| # | Blocker | chain_v2.7 修复 |
|---|---|---|
| B1⁶ | **冻结 routing 未被实际执行**:三席/空头只传任务名,`L.call()` 读可变全局 `TASK_LLM`——GPT 复现:契约冻结 doubao-seed-2.0-pro,实际执行 tampered-model,manifest 复核仍 PASSED;模型/thinking/温度/fallback 可在契约加载后漂移 | `llm_config.call_with_config(messages, route)`(只接受显式路由,`ROUTE_EXEC_KEYS` 缺=KeyError,绝不读 TASK_LLM);run_seat/run_bear 直接收 `contract.routing["scoring"]`/`["bear"]`;`archive["llm_config_hash"]` 从冻结契约取(不再现场调 `L.llm_config_hash()`);ChainContract 增 `llm_config_hash` 字段+load 验 routing 两腿执行字段齐全+对盘复核加比 llm_config_hash;回归:契约加载后篡改 TASK_LLM→捕获执行参数保持冻结值(并对照证明旧 `L.call` 门确实会漂移) |
| B2⁶ | **嵌套权重未校验,NaN 让 composite 复核 fail-open**:`composite_weights["fund"]=NaN` 过契约校验+语义校验(abs(NaN−x)>0.11 恒假)→ 任意 composite sealed_ok | `verify_scoring_contract` 加嵌套校验(GPT 精确替换):每席 dims 非空 dict+逐值 `_num_ok[0,100]`;composite 逐值 `[0,1]` 有限数+**合计==1(±1e-12)**;语义复核第二道防线 `not _num_ok(recomputed,0,100) or abs(...)>0.11`(重算值本身非有限数=点名) |
| B3⁶ | **平台与引擎"合格档案"判定不一致**:平台只跑 `verify_archive_semantics`,引擎 `archive_complete` 还要求席位/空头无 error+schema_valid+parse_mode——GPT 复现:`bear.schema_valid=False` 的封印档案引擎判 incomplete、平台 sealed_ok 且计入 full_month complete | **`verify_publishable_archive`**(integrity.py 共享纯函数)=语义一致性+席位无错误+bear 无错误/schema_valid/parse_mode 合法;引擎 `archive_complete` 变成它的 bool 包装,平台加载对封印档案改调它——同一把尺,回归含逐例等价断言 `archive_complete(a) == (not verify_publishable_archive(a,…))` |
| B4⁶ | **marker 的 status 文本没有验证**:真实 1/2 档案,仅把 `"partial"` 改成 `"complete"`(其余字段全真)仍 `(True, [])` | `validate_full_month_status` 加(GPT 精确替换):`actual_status = complete if len(seals)==expected else partial`,`status.get("status") != actual_status` = 点名;回归覆盖 partial→complete 冒充/complete→partial/缺失/非法 status/真 complete+真 partial 接受 |

**R2/R3 采纳**:残余 (a) 席位名不必钉死(不同席位集=不同 manifest 身份)但嵌套权重必须先过 B2 校验 ✔;残余 (b) 原则可接受但实现须过 B3 ✔;残余 (c) 可接受,2384 实弹不前置。
**测试:185/185**(+26 条复审#7 回归:TASK_LLM 篡改后执行参数冻结/route 缺字段 KeyError/契约携带 llm_config_hash/load 拒破损 routing·缺 llm 哈希/NaN composite 拒收/坏席位 dims 6 例/composite 合计≠1 三例/语义第二道防线/schema_valid=False·席位 error·parse_mode 点名/引擎-平台逐例等价/status 文本冒充 4 例)。

### §10.8 复审#8 裁定与处置(2026-07-11 收到,chain_v2.8;版本再 bump——引擎哈希文件变更,GPT R4 裁定)

**裁定:REVISE**(1 Blocker + 1 Major;GPT 独立探针在 185 全绿之外打开新的档案校验 fail-open)。处置:

| # | 缺陷 | chain_v2.8 修复 |
|---|---|---|
| Blocker⁷ | **共享合格判定仍用真值性,fail-open**:真 v2.7 档案改 `schema_valid=NaN` 重封印后 `verify_publishable_archive==[]`+`archive_complete==True`+平台 sealed_ok;`schema_valid="false"`/`1` 同过;falsey 非空错误([]/{}/0/"")被当"无错误"——统一谓词两侧一致但一致地放行 | GPT 精确替换:`error` 只有**字面 None** 算干净(`is not None` 即点名);`schema_valid` 只有**字面 True** 算通过(`is not True` 即点名);回归覆盖 NaN/1/"false"/"true"/[1]/0/None 的 schema_valid 与 []/{}/0/""/False 的席位·空头 error;存量 v2.4-v2.7 档案全存字面 True/None——兼容性回归 `literal_none_error_is_clean` |
| Major⁷ | **路由值类型未校验**:`thinking:"False"`(truthy 字符串)的自洽 manifest 过 `ChainContract.load`,Ark 按 thinking 开启解释——静默语义反转 | **`verify_llm_route`**(integrity.py 共享,三处消费点同一把尺——ChainContract.load / call_with_config / 平台版本门):model 非空 str;thinking 字面 bool 或 None;temperature [0,2] 有限数(bool 除外);max_tokens 正整数(bool 除外);fallback None 或非空 str;`ROUTE_EXEC_KEYS` 规范定义迁入 integrity.py(llm_config 引用);现存 v2.4-v2.7 manifest 路由全过(实测) |

**测试:224/224**(+39 条复审#8 回归:schema_valid 7 例/席位 error falsey 5 例/空头 error falsey 4 例/字面 None 兼容/route 值类型 16 例/字符串 thinking 拒于 load·call_with_config/缺键·非对象)。

### §10.9 复审#9 终裁:**SHIP**(2026-07-11 收到;0 Blocker / 0 Major / 1 Minor)

GPT 对 669a33d 复核:R1 全部复现通过(NaN/1/"false" 重封印档案 archive_complete=False+平台 loaded=0/rejected=1;falsey 非空错误全点名;"False"/1/"true" thinking 双端拒;温度/token/fallback 滥用全拒,call_with_config 在 chat 前抛,捕获 LLM 调用=0;v2.4-v2.8 存量路由全过);R2 共享谓词无残余承重真值性;R3 完整性与完成链在对抗输入下闭合(类型化评分+路由绑 manifest/契约 load 校验+深只读+逐字执行/档案必带封印+引擎平台单一严格谓词/真两档终局重算=2 无缺失且重现集合哈希/月度 marker 只能计入平台已验证档案);**R4:chain_v2.8 适合执行 149×16 NON_EVIDENTIARY 全月重放**。
**Minor(唯一发现,server-only 硬化,不需再 bump 链版本,已同日落地)**:平台版本门先解引用 `(manifest.get("routing") or {}).get(leg)`——truthy 非 Mapping 容器(list/str)曾 AttributeError 炸掉整个 Data() 初始化而非只拒该版本(fail-closed:无档案可执行/发布/计数,故不阻塞重放)。修复=GPT 精确替换(容器先验 `isinstance(routing, Mapping)` 再逐腿校验)+回归(list/str 容器只拒该版本、Data() 正常完成、v2.8 照常加载)。ChainContract.load/call_with_config 的同类崩溃 GPT 裁定 fail-closed 可接受,且改引擎文件会再 bump 版本——不动。**测试:225/225**。
**八轮跨审终局:chain_v2.0→v2.8,5+4+3+3+3+2+4+1 = 25 Blocker 全闭,#10 全月重放解锁。**

---

## 附录 A:现行输入原文(审计基线,2026-07-09 实查 688981.SH @ 20250127)

### A.1 市场情境卡(现行)
```
【市场情境卡 20250127】(全部数字由代码计算)
◆ 指数: 上证-0.1% 沪深300-0.4% 中证1000-1.6% 创业板-2.7%
◆ 风格: 沪深300−中证1000 当日差 +1.1 个百分点(大盘占优)
◆ 宽度: 上涨 1816 家 / 下跌 3430 家(涨家占比 35%)
◆ 涨跌停温度: 涨停 48 家 · 跌停 50 家 · 炸板 37 家
◆ 成交额: 250日分位 68%
◆ 行业轮动(当日): 领涨 银行+1.5% 煤炭+0.9% 公用事业+0.9% 钢铁+0.8% 建筑材料+0.7% | 领跌 汽车-1.7% 机械设备-1.8% 非银金融-2.0% 电子-2.8% 通信-3.1%
◆ 近3日重要政策: [财政部 海关总署 税务总局] 关于调整海南自由贸易港原辅料"零关税"政策的通知;[国家医保局办公室] …;[国家文物局办公室] …
regime: 风险偏好收缩
```

### A.2 基本面卡(现行,节选可见格式问题)
```
【基本面三锚定事实表】(值|行业分位(同业家数)|自身10年分位)
- ROE(加权)%: 1.9|行业分位35%(468家)|10年分位33%
- 毛利率%: 17.6393|行业分位30%(470家)|10年分位22%
- 经营现金流/营收: 0.2928|行业分位94%(470家)|10年分位22%
- 净利润同比%: -26.3578|行业分位28%(470家)|10年分位44%
- PE(TTM): 194.417|行业分位90%(355家)|10年分位94%
- 总市值(万): 7.49326e+07|行业分位100%(474家)|10年分位97%
(… 15 行 + 业务构成 top5)
```

### A.3 技术面卡(现行,节选)
```
【量价情报包】(项目: 值「状态」[分位];全部由代码判定)
◆ 趋势形态: 均线排列 0「缠绕」;距52周高 -0.1052;RS_行业分位_60d 0.7323[分位73%];…
◆ 量能结构: 量价四象限 1「缩量跌」;量比 0.8;收盘位置5d 0.2078「持续收低」;…
◆ 筹码持仓: 获利盘 28.04[分位38%];现价距成本50分位 -0.0375;融资余额20d变动 -0.2073;…
◆ 主力行为: 大单净流5d -243177;大小单形态 0「派发形态」;净流强度分位 -0.001[分位14%];…
◆ 涨停语言: 涨停20d 0;连板高度 0;涨停次日溢价均值 0.0819「样本3次」
```

### A.4 消息面卡(现行 chain_v1.3)
```
【检索装配单】
—— 直接事件(本股,3 条)——
- 研报点评|华鑫证券研报:…集成电路制造业领导者…|中性
- 互动易-产能|2024年第一季度公司平均产能利用率为80.8%|中性
- 互动易-产能|2024年二季度平均产能利用率为85.2%|中性
—— 间接事件(概念/行业同伴,top15)——
- [概念]业绩预告|688519.SH 业绩预告:扭亏 134.75%~147.88%|显著利好|相关度0.49
(× 15 行全部为业绩预告 —— §4.1-3 的刷屏实证)
```

### A.5 四席 prompt 现行版本
fund/tech/news v1.1(news 语义 v1.2)、bear v1:全文见 [prompts/](engine/prompts/)。
