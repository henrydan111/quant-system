# 果仁 Deployed-20 复刻战役 — 总结报告(2026-07-03 收官)

> 本文是 deployed-20 复刻战役的**沉淀文档**:结论、口径 registry、教训、可复刻性分类、数据通路。
> 逐日审计线在 [deployed_20_replication_status.md](deployed_20_replication_status.md)(台账)+ project_state.md
> (2026-07-02c..2026-07-03d 注记);逐因子映射在 [guorn_local_field_mapping.md](guorn_local_field_mapping.md)。
> 全部 NON-FORMAL 平价工作(读已发布 provider,不碰 pit_ledger 原始层)。

## 1. 核心结论(两条)

**结论一:本地引擎+数据与果仁平台一致 —— 执行路径 7/7 精确验证。**
把果仁的真实持仓+自报仓位喂进 EventDrivenBacktester(replay 分解),7 本书全部复现其净值曲线:

| 书 | REPLAY vs 果仁 CAGR | MDD | 备注 |
|---|---|---|---|
| #8 央企红利(日频 Model-II) | +34.47 vs +32.07 | **−21.64 vs −21.68(4bp!)** | 最强单点 |
| #9 重股息(5日 Model-I) | **+33.34 vs +33.25(+0.09pp)** | −33.9 vs −33.0 | |
| #17 高波(5日) | **+29.34 vs +29.46(−0.12pp)** | −64.8 vs −65.5 | |
| #16 隔夜动量(20日,含ST) | **+27.56 vs +27.76(−0.2pp)** | −53.8 vs −54.0 | 11/13 年 ±2.3pp |
| #12 创业板sm | +43.79 vs +41.75 | −41.6 vs −43.1 | |
| #7 红利低波 | +26.07 vs +29.73 | 均匀 −0.09pp/期 + 危机涨停锁定事件(果仁成交乐观类,rung-1 同源) | |
| #4/#15 微盘GARP | +55.28/+46.54 vs +49.59/+43.39 | 微盘上引擎为慷慨方(零滑点+税前分红) | |

覆盖 Model-I/II、日频/5日/20日调仓、大盘红利/微盘 GARP/含 ST 动量全书型。价格、税前分红入账
(cash_div_tax)、送股、停牌携带、涨跌停闸、退市强平全链与果仁行为一致。**这是本地系统对标果仁
基准的核心资产。**

**结论二:选股层缺口 = f(口径保真度 × 持仓数 × universe 规模),且 universe 规模是构成噪声的分母。**
对照实验:#12(创业板 ~800 只)与 #4(全市场 ~4800 只)用同类价值复合、同等口径保真度(同一批
frame),追踪率 0.47/0.71 vs 0.19,收益缺口 −2.3pp vs −17pp。分层结果:

| 类 | 书 | LOCAL vs 果仁 | 追踪 | 判定 |
|---|---|---|---|---|
| 高保真 | #2/#12/#1/#6/#18 | +0.4 ~ −2.5pp | in25 0.89-0.91 / in10 0.47 | 复刻成功 |
| 精度地板 | #7/#8/#9 红利族 | −6.0 ~ −8.1pp | in10 0.68-0.79, in20 0.78-0.88 | 残差全部定界(见 §3) |
| 构成噪声 | #16/#17 | −9.7 ~ −12.0pp | in10 0.25-0.27 | replay 精确,选股定界 |
| 不可复刻 | #4/#15/#5 微盘GARP/双创 | −17 ~ −28pp | in10 ~0.19 | **测量阴性**(见 §4) |

## 2. 口径 registry(13 条,全部由 xlsx 真值实测钉死,非推断)

完整表在台账 "Fixed-factor registry";此处按类归纳:

**排名/筛选语义**
1. `排名%区间 X%-100%` 从大到小,drop TOP (100−X)%(成长簇 fix-1)
2. `排名%最小 X%` = 保留最小 X%;**组内边界 = rank_asc ≤ ceil(X·N)**(#10:小奇数组多保一席,zsfz 84.4→87.7%)
3. 筛选 `上市天数>N` = 日历日(fix-2)
4. `SUM/MA` 窗口函数对次新 min_periods=1(fix-5);预告/快报类事件因子有**存活窗**(fix-6/express)
5. 果仁 `LOG()`=log10(fix-7,rank 不变);`%(a,b)` 变化率族同理 affine

**财报/分红锚**
6. `sumq(分红总金额,4,k)` 锚**个股已披露季度网格**(q0=最新披露季,cum==sq Q1 恒等式定位;#8 registry 行)
7. `annual(x,k)` FY 锚 = 个股**最新可见年报**(年报槽 = (k_Q1+1)%4;#9 行)
8. `TTM/SumQ/AvgQ/RefQ(x,N)` 的 **N=前移季度数**非窗口(#12:TTM(x,4)=一年前 4 季和;官方文档 L610)
9. **CoreProfitQ 金融股 0-fill**(#11:费用行缺失 NaN→0、营收必须非空;银行案例结构级一致)
10. **总资产周转率分母 = 4 季均资产**(#13:caliber A penny 0.983 完胜首末均 B)
11. ROETTMDiffPQ 用**加权平均净资产**代理 (0.5·q4+q3+q2+q1+0.5·q0)/4(fix-4)
12. 股息率TTM = **ann-date declared** 口径;分红金额因子 = dps × 当日 $total_share
13. **EV 按果仁公式 VERBATIM 复刻含"货币资金×2"作者 bug**(gp_ev sp 0.981 证明 bug 是真实部署形态)

**平台机制**
- Model-II 的 `本期起始仓位` **严禁归一化**(寡名期持部分仓位+现金,#8 归一化假象:MDD −50%)
- Model-I 权重 = sqrt(市值) 逐期重校准(xlsx 权重列反推验证)
- 池级宏观闸(SMED/SAVG 公式)只在通过日有锚点 → **FAIL 状态必须从 调仓详情 继承**(记录性循环仅限择时层)
- 果仁逐期收益 = fill-to-fill 记账(±1 日成对 diff 为报告噪声,年内对消)

## 3. 已定界的不可复原残差(按书)

- **#7 红利低波**:dy−CGB 2% 严格阈值上的 ±10-20bp 精度地板(分红厂商+价格约定);银行簇申万 L2
  vintage(果仁 2014 用"其他银行",申万已重述历史,members parquet 无此分类);2 个专有筛选
  (未来20日新增流通股 = share_float 未入库;退市风险的预期ST/风险预警/重大违规腿)。
- **#8 央企**:Tushare act_ent_type 当前快照的 15 个边缘案例(交行/新华标"无"、实控人变更史);
  中性换手率内部配方(最佳近似 = 全A logMV 回归残差,按日 sp 0.788)。
- **#9 重股息**:divvol720 的日频服务约定(金额版 sp 0.839 rank 可用,scale 不可复原);
  预期股息率 pre-2022 consensus 回退到 TTM NI。
- **#16/#17**:季度 consensus(预期净利润Q)不可得(w1 各一省略);rating_up/行业NP 聚合的厂商
  计数噪声;HneutralizeMI 内部语义(论坛答案登录墙,变体 sp −0.18 已剔除)。
- **通用**:果仁危机期成交乐观(涨停可买/跌停可卖假设)、复权/日历/朝阳永续 vintage。

## 4. 阴性结果(防止重复挖掘)

1. **#4 升级 arc(2026-07-03)**:解锁 9/12 省略权重后,v2-22/25w +15.09%、v3-17/25w(仅 penny 项)
   +24.16%,都劣于 v1-13/25w 的 +32.24% —— v1 收益是微盘风格 beta 而非保真度;加权重稀释 总市值
   倾斜占比 → 风格漂移。**大 universe × 多噪声项的微盘复合书不可选股复刻**,不带新保真杠杆
   (如对噪声项做多日期 web 导出复核)不再重试。
2. ILLIQ 2dp 量化(成长簇):因子级保真 ≠ 书级保真的最早案例。
3. mi_rndqp 变体(winsor+L1 内 logMV 残差):sp −0.18,比省略更糟,已从一切组合剔除。

## 5. 本战役打通的数据通路(可复用资产)

| 通路 | 实现 | 验证 |
|---|---|---|
| **快报 express 隐含单季 YoY** | 原始 parquet 直读 + ann_date PIT 钳 + 存活窗(快报期==q0+1,真报落地自杀) | **penny(sp 0.990)** |
| **EV/EBITDAQ 构造** | 资产负债表 6 腿 0-fill + D&A cum 差分(Q1 相位探测防跨 FY) | gp_ev 0.981 / ebitda_ev 0.714 |
| **声明制分红三口径** | guorn_dividend_caliber(ttm/byq/byfy)+ v7 向量化(逐位断言一致) | penny 全家 |
| **CGB10y/池公式恢复** | 从 xlsx 公式真值列反解宏观序列 + 时间插值 | 离散度 ≤7e-05 |
| **实控人企业性质** | stock_basic.act_ent_type(fetcher 早已拉取,data_dictionary 曾落后) | 127/142 |
| **申万 L1/L2 as-of** | members parquet 区间连接(⚠ $sw2021_l1 不是 provider bin,两次事故) | L2 vintage 有限 |
| **深度9 槽位** | q5..q8 解锁 SharesAvgGr/ATO/年前 TTM 族 | ato penny |

## 6. 基建产出(本战役触发的系统修复)

- **M4 缓存清单自愈**(provider 轮换后旧 cache_key 永久拒绝 → 重算+重录分支;独立会话修复,
  verify07 端到端复验:preload 恢复 + 终值逐位一致)
- **$sw2021_l1 假字段清理**(verify01/rung6 活性 bug 根治 + 文档警告;rung6 发现 #59 实为 10 活因子)
- 提醒:`D.list_instruments("all")` 泄漏指数码(000001_SH),新 harness 必须 `_is_ashare_stock` 过滤
  (老 harness 靠 all_stocks.txt bounds 掩码免疫)

## 7. 二十本书处置总表

| # | 书 | 状态 | 数字(LOCAL vs 果仁) |
|---|---|---|---|
| 1 | sm_01_成长动量 | ✅ v5 收口 | +54.73 vs +57.21 |
| 2 | sm_01_成长_v1 | ✅ v4 收口 | +58.59 vs +58.20 |
| 3 | sm_大制造GARP_v3 | ⏸ defer | 行业 vintage + 壳价值 + #4 类墙 |
| 4 | sm_GARP_illiq | ✗ 阴性定界 | +32.24 vs +49.59(v1 canonical) |
| 5 | sm_双创研发强度 | ✗ 同类(成长簇期) | +40.70 vs +62.67 |
| 6 | 成长高贝塔@TMT | ✅ v3 收口 | +57.78 vs +60.32 |
| 7 | value_红利低波_v2 | ◑ 精度地板收口 | +21.67 vs +29.73 |
| 8 | value_红利低波_央企 | ◑ 精度地板收口 | +26.09 vs +32.07 |
| 9 | value_红利低波_重股息 | ◑ 精度地板收口 | +26.10 vs +33.25 |
| 10 | value_AH_低溢价GARP | 🔒 阻塞 | hk_daily 未入库 |
| 11 | value_FCF_非金sm | ⏸ defer | 12 季 StdevQ 槽深(见深槽构建交接)+ 机构持股缺 |
| 12 | value_创业板sm | ✅ **最佳** | **+39.45 vs +41.75(−2.3pp)** |
| 13 | 成长_机构预期@周期 | ⏸ defer | consensus 签名项 pre-2022 厂商回填非 PIT |
| 14 | 成长_净利润断层 | ⏸ defer | PEAD 开盘缺口入场需引擎 fill-step 手术 |
| 15 | 成长_双创_GARP@周期 | ✗ 阴性定界 | +15.82 vs +43.39 |
| 16 | 成长_隔夜动量@周期 | ◑ 构成噪声收口 | +18.08 vs +27.76 |
| 17 | 成长_高波@周期 | ◑ 构成噪声收口 | +17.43 vs +29.46 |
| 18 | ST_大市值_v3 | ✅ 收口(2026-06) | 年度+持仓重合验证 |
| 19 | MultiA_风险平价 | 🔒 阻塞 | 基金/ETF 行情未入库 |
| 20 | MultiA_动量18 | 🔒 阻塞 | 基金/ETF 行情未入库 |

## 8. 后续行动指针

- 深槽 16 构建(解锁 #11 + GARP 3 年复合项):[PROMPT_deepslot16_build.md](PROMPT_deepslot16_build.md)
- 果仁因子入 catalog(正式化,治理门槛见 prompt):[PROMPT_catalog_integration.md](PROMPT_catalog_integration.md)
- 数据解锁:hk_daily(#10)、基金/ETF 行情(#19/#20)、share_float(未来20日新增流通股,多书通用筛选)
- harness 索引:guorn_verify_{01,02,04,05,06,07,08,09,12,15,16,17,18}*.py + _verify04_upgrade.py +
  _verify_v3_propagate.py;缓存 verify{01,04,07,08,09,16,17}_cache/
