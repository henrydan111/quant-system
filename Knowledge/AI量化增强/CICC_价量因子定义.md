# 中金价量因子手册（系列7）— 因子定义

> 逐字转录自《中金量化多因子系列7价量因子手册》各类「构建方式」图（图表4/16/28/40/52/64/76/88/100）。
> 测试：2010.01.04–2022.07.01（中证1000 自 2014.11.01）；全市场/沪深300/中证500/中证1000；月度；10 分组。
> 8 大类：动量&反转、波动率、流动性、量价相关性、筹码分布、资金流、北向资金、融资融券（+ 价量复合）。
> 我方日频价量数据齐全 → **几乎全部 ✅ 可复刻**；筹码分布依赖 cyq_perf（已批准）；北向依赖 hk_hold（已批准）；
> 融资融券依赖 margin_detail（部分批准）；资金流依赖 moneyflow（已批准）。

## 1. 动量 & 反转因子（19，图表4）

| 代码 | 名称 | 计算公式 | 可复刻 |
|---|---|---|---|
| mmt_normal_M | 1个月收益率 | 过去1个月的收益率 | ✅ |
| mmt_normal_A | 1年收益率 | 过去12个月收益率 − 过去1个月收益率（剔除近月反转） | ✅ |
| mmt_avg_M | 相对均价的1个月收益率 | 当期收盘价 / 过去20交易日均价 | ✅ |
| mmt_avg_A | 相对均价的1年收益率 | 1个月前的收盘价 / 过去1年的均价 | ✅ |
| mmt_intraday_M | 1个月日内动量 | 过去一个月的日内涨跌幅之和 | ✅ |
| mmt_intraday_A | 1年日内动量 | 过去一年的日内涨跌幅之和 − 过去一个月的日内涨跌幅之和 | ✅ |
| mmt_overnight_M | 1个月隔夜动量 | 过去1个月内，隔夜涨跌幅之和 | ✅ |
| mmt_overnight_A | 1年隔夜动量 | 过去一年的隔夜涨跌幅之和 − 过去一个月隔夜涨跌幅之和 | ✅ |
| mmt_off_limit_A | 1年去涨跌停动量 | 除去涨跌停状态外，过去1年的收盘涨跌幅 − 过去1个月的收盘涨跌幅 | ✅（用 $up_limit/$down_limit） |
| mmt_off_limit_M | 1个月去涨跌停动量 | 除去涨跌停状态外，过去1个月的收盘涨跌幅 | ✅ |
| mmt_range_M | 1个月振幅调整动量 | 过去1个月内，振幅大的前20%的收盘收益率 − 振幅小的后20%的收盘收益率 | ✅ |
| mmt_range_A | 1年振幅调整动量 | 过去1年内，振幅大的前20%收盘收益率 − 振幅小的后20%收盘收益率 | ✅ |
| mmt_route_M | 1个月路径调整动量 | 过去1个月内收益率 / 过去1个月内日度涨跌幅绝对值之和 | ✅ |
| mmt_route_A | 1年路径调整动量 | 过去1年内收益率 / 过去1年内日度涨跌幅绝对值之和 | ✅ |
| mmt_discrete_M | 1个月信息离散度动量 | 过去1个月内，上涨天数占比 − 下跌天数占比 | ✅ |
| mmt_discrete_A | 1年信息离散度动量 | 过去1年内，上涨天数占比 − 下跌天数占比 | ✅ |
| mmt_sec_rank_M | 1个月截面rank动量 | 每日计算个股日收益在横截面的排名，取过去20个交易日排名均值 | ✅ |
| mmt_sec_rank_A | 1年截面rank动量 | 每日计算个股日收益在横截面的排名，取过去1年排名均值 | ✅ |
| mmt_time_rank_M | 1个月时序rank动量 | 每日计算个股价格在时序（1年内）的排名，取过去20个交易日排名均值 | ✅ |
| mmt_report_overnight | 业绩公告前隔夜动量 | 最近一个业绩公告日前的一个月隔夜收益率之和 | ✅（用 ann_date） |
| mmt_report_jump | 业绩跳空动量 | 最近一个业绩公告日的下一交易日隔夜超额收益率 | ✅ |
| mmt_report_period | 业绩期动量 | 业绩公告前一交易日至后一交易日 | ✅ |
| mmt_highest_days_A | 近1年最高价日期距今的天数 | 过去1年最高价出现的日期距离当前期的天数 | ✅ |

> 注：转录到 23 行（含 mmt_report_* 与 mmt_highest_days_A）；手册正文称"动量&反转分4小类：隔夜动量、
> 报告期动量、月度反转、年度动量"。与我方已有 `mom_*`/`rev_*`/`mom_overnight_20d`/`mom_intraday_20d` 多处同源，
> 复刻前比对去重。

## 2. 波动率因子（39，图表16）

系统命名：`vol_{类型}_{avg|std}_{1M|3M|6M}`。窗口 1M/3M/6M 各一支；统计量 avg=均值、std=标准差。
日收益率均为"调整日收益率"（剔除涨跌停日：下行波动用涨跌幅<0 的日、上行用>0 的日）。

| 子类 | 因子代码 | 计算公式 | 可复刻 |
|---|---|---|---|
| 收益波动率 | vol_std_{1M,3M,6M} | 过去 N 个月（日收益率）的标准差 | ✅ |
| 下行波动率 | vol_down_std_{1M,3M,6M} | 过去 N 个月（调整日收益率）的标准差，调整=日收益率指涨跌幅<0 的日收益率 | ✅ |
| 上行波动率 | vol_up_std_{1M,3M,6M} | 过去 N 个月（调整日收益率）的标准差，调整=涨跌幅>0 的日收益率 | ✅ |
| 日内振幅 | vol_highlow_avg_{1M,3M,6M} | 过去 N 个月（最高价/最低价）的均值 | ✅ |
| 日内振幅标准差 | vol_highlow_std_{1M,3M,6M} | 过去 N 个月（最高价/最低价）的标准差 | ✅ |
| 标准化上影线均值 | vol_upshadow_avg_{1M,3M,6M} | 上影线因子均值；标准化上影线=(最高价 − max(开盘价,收盘价))/最高价 | ✅ |
| 标准化上影线标准差 | vol_upshadow_std_{1M,3M,6M} | 上影线因子标准差 | ✅ |
| 标准化下影线均值 | vol_downshadow_avg_{1M,3M,6M} | 下影线因子均值；标准化下影线=(min(开盘价,收盘价) − 最低价)/最低价 | ✅ |
| 标准化下影线标准差 | vol_downshadow_std_{1M,3M,6M} | 下影线因子标准差 | ✅ |
| 威廉下影线均值 | vol_w_downshadow_avg_{1M,3M,6M} | 威廉下影线因子均值；威廉下影线=(收盘价 − 最低价)/最低价 | ✅ |
| 威廉下影线标准差 | vol_w_downshadow_std_{1M,3M,6M} | 威廉下影线因子标准差 | ✅ |
| 威廉上影线均值 | vol_w_upshadow_avg_{1M,3M,6M} | 威廉上影线因子均值；威廉上影线=(最高价 − 收盘价)/最高价 | ✅ |
| 威廉上影线标准差 | vol_w_upshadow_std_{1M,3M,6M} | 威廉上影线因子标准差 | ✅ |

> 13 子类 × 3 窗口 = 39。全部仅需 OHLC 日频，✅ 可复刻。与我方 `risk_vol_*`/`risk_downvol_*`/`risk_range_ratio` 多处同源，去重。

## 3. 流动性因子（21，图表28）

基于换手率与价格弹性构建；命名 `liq_{类型}_{avg|std}_{1M|3M|6M}`。

| 子类 | 因子代码 | 计算公式 | 可复刻 |
|---|---|---|---|
| 换手率均值 | liq_turn_avg_{1M,3M,6M} | 过去 N 个月换手率的均值 | ✅ |
| 换手率标准差 | liq_turn_std_{1M,3M,6M} | 过去 N 个月换手率的标准差 | ✅ |
| 成交波动比 | liq_vstd_{1M,3M,6M} | 过去 N 个月成交额 / 过去 N 个月收益率标准差 | ✅ |
| Amihud 非流动均值 | liq_amihud_avg_{1M,3M,6M} | 过去 N 个月 (|日收益率| / 成交额) 的平均值 | ✅ |
| Amihud 非流动标准差 | liq_amihud_std_{1M,3M,6M} | 过去 N 个月 (|日收益率| / 成交额) 的标准差 | ✅ |
| 最短路径非流动均值 | liq_shortcut_avg_{1M,3M,6M} | 过去 N 个月 (日K线最短路径/成交额) 的平均值；日K线最短路径=2×(最高−最低)−|开盘−收盘| | ✅ |
| 最短路径非流动标准差 | liq_shortcut_std_{1M,3M,6M} | 过去 N 个月 (日K线最短路径/成交额) 的标准差 | ✅ |

> 7 子类 × 3 窗口 = 21。仅需价量日频，✅ 全可复刻。与我方 `liq_turnover_*`/`liq_amihud_20d`/`liq_vol_cv` 同源，去重。

## 4. 量价相关性因子（8，图表40）

均为过去 20 个交易日的相关系数；"prior/post"指领先/滞后 1 日。三小类：价格相关、量能领先、量价同步。

| 代码 | 名称 | 计算公式 | 可复刻 |
|---|---|---|---|
| corr_price_turn_1M | 换手率与价格相关性（量价同步） | 过去20交易日，日换手率与日收盘价的相关系数 | ✅ |
| corr_price_turn_post_1M | 换手率与价格相关性（量能领先） | 过去20交易日，日换手率与t+1日收盘价的相关系数 | ✅ |
| corr_price_turn_prior_1M | 换手率与价格相关性（价格领先） | 过去20交易日，日换手率与t−1日收盘价的相关系数 | ✅ |
| corr_ret_turn_1M | 换手率与收益率相关性（量价同步） | 过去20交易日，日换手率与日收益率的相关系数 | ✅ |
| corr_ret_turn_post_1M | 换手率与收益率相关性（量能领先） | 过去20交易日，日换手率与t+1日收益率的相关系数 | ✅ |
| corr_ret_turn_prior_1M | 换手率与收益率相关性（价格领先） | 过去20交易日，日换手率与t−1日收益率的相关系数 | ✅ |
| corr_ret_turnd_1M | 换手率变动与收益率相关性（量价同步） | 过去20交易日，日换手率的变动与日收益率的相关系数 | ✅ |
| corr_ret_turnd_prior_1M | 换手率变动与收益率相关性（价格领先） | 过去20交易日，日换手率变动与t−1日收益率的相关系数 | ✅ |

## 5. 筹码分布因子（9，图表52）

依赖 Tushare `cyq_perf`（筹码分布，已批准）。两小类：筹码分布形状、筹码占比。

| 代码 | 名称 | 计算公式 | 可复刻 |
|---|---|---|---|
| distribution_ret_avg | 筹码平均收益因子 | 各筹码收益率的平均数 | ✅ cyq_perf |
| distribution_ret_std | 筹码标准差因子 | 各筹码收益率的标准差 | ✅ |
| distribution_ret_skew | 筹码偏度因子 | 各筹码收益率的偏度统计量 | ✅ |
| distribution_ret_kurt | 筹码峰度因子 | 各筹码收益率的峰度统计量 | ✅ |
| distribution_max_prob_ret | 最大筹码收益率因子 | 占比最大的筹码区间的收益率 | ✅ |
| distribution_bal | 盈亏平衡筹码占比因子 | −2% 至 2% 收益率的筹码占比 | ✅ |
| distribution_profit_l | 大幅盈利筹码占比因子 | 10% 以上收益率的筹码占比 | ✅ |
| distribution_profit_s | 小幅盈利筹码占比因子 | 2% 至 10% 收益率的筹码占比 | ✅ |
| distribution_loss_s | 小幅亏损筹码占比因子 | −2% 至 −10% 收益率的筹码占比 | ✅ |
| distribution_loss_l | 大幅亏损筹码占比因子 | −10% 以下收益率的筹码占比 | ✅ |

> （表含 10 行；标题称 9，差异为 profit_l/profit_s/loss_s/loss_l 的归并口径，以表为准）

## 6. 资金流因子（32，图表64）

依赖 Tushare `moneyflow`（已批准）。两小类：大小单资金流向、开盘/尾盘资金流向。均基于过去 20 交易日。
"shift_dist"=位移路程比（净流入金额之和 / |流入|+|流出| 之和，即净额相对总活跃度）。后缀 _xl 超大单 / _l 大单 / _m 中单 / _s 小单。

**大小单资金流向**（占比 prop = 净/主动流入金额之和 / 成交额之和；shift_dist = 净额 / 流出入绝对额之和）：
- `act_buy_prop` 主动买入占比 = 过去20日(净买入金额)之和 / 成交额之和
- `act_buy_shift_dist` 主动买入的位移路程比
- `act_buy_shift_dist_{xl,l,m,s}` 超大/大/中/小单主动买入位移路程比因子
- `act_buy_prop_{l,m,s}` 大/中/小单主动买入占比因子
- `buy_prop` / `buy_prop_{l,m,s}` 总（含被动）买入占比族
- `buy_shift_dist` / `buy_shift_dist_{xl,l,m,s}` 总买入位移路程比族

**开盘/尾盘资金流向**（open=开盘集合竞价后首段；close=尾盘段；prop=占比，rate=占成交额比，shift_dist=位移路程比，amount=金额）：
- `inflow_prop_open` 开盘资金净流入占比 = 过去20日(开盘资金净流入金额 / 当日成交额)的平均值
- `inflow_shift_dist_open` 开盘资金净流入位移路程比（**手册重点推荐，尤其中证1000**）
- `amount_prop_open` 开盘资金净流入金额因子
- `inflow_rate_open` 开盘资金净流入率
- `inflow_shift_dist_open_l` 大单开盘净流入位移路程比
- `inflow_prop_close` / `inflow_shift_dist_close` / `amount_prop_close` / `inflow_rate_close` / `inflow_shift_dist_close_l` 尾盘对应族

> ✅ 全部基于日度大小单资金流（moneyflow），可复刻；与我方 `flow_*` 族多处同源。

## 7. 北向资金流因子（9，图表76）

依赖 Tushare `hk_hold`（陆股通持仓，已批准）。两小类：持仓占比、持仓变化。

| 代码 | 名称 | 计算公式 | 可复刻 |
|---|---|---|---|
| north_hold_prop | 北向持仓占比因子 | 当日北向持仓占比 = 当日陆股通持仓量 / 当日流通股本 | ✅ |
| north_hold_prop_st_chg | 北向持仓占比短期变动 | 当日占比 − 过去20交易日占比的均值 | ✅ |
| north_excess_hold_st | 北向超额持仓因子 | 当期陆股通持仓量·VWAP /(20个交易日 VWAP×持仓) − 过去20日涨跌幅 | ✅ |
| north_inflow_shift_dist | 北向资金的位移路程比因子 | 过去20日(北向单日净流入)之和 / (北向单日|净流入|之和) | ✅ |
| north_trade_prop | 北向交易占比因子 | 当期陆股通持仓量·VWAP /(20交易日陆股通持仓量×VWAP) / 20日成交额之和 | ✅ |
| north_inflow_shift_dist（细分） | — | 北向单日净流入相关位移路程 | ✅ |
| north_hold_st_chg | 北向持仓占比短期变动 | 当日 − 过去20日北向持仓占比因子的均值 | ✅ |
| north_hold_prefer | 北向持仓偏好因子 | 当期占比 / 当期市场所有股票占比 | ✅ |
| north_hold_prefer_st_chg | 北向持仓偏好短期变动 | 当期 − 过去20日北向持仓偏好因子的均值 | ✅ |
| north_hold_prefer_lt_chg | 北向持仓偏好长期变动 | 当期 − 过去N日北向持仓偏好因子的均值 | ✅ |

> 与我方 `north_*` 族同源，去重。

## 8. 融资融券因子（约 12，图表88）

依赖 Tushare `margin_detail`（部分字段批准；`$rqye`/`$rqchl` 等融券字段在 quarantine）。均基于过去 20 交易日。

| 代码 | 名称 | 计算公式 | 可复刻 |
|---|---|---|---|
| margin_buy_money_prop | 融资买入占比因子 | 过去20日融资买入额之和 / 成交额之和 | ✅ 融资侧已批准 |
| net_margin_buy_money_shift_dist | 净融资买入的位移路程比因子 | 过去20日(融资买入额−融券卖出额)之和 / (|融买|+|融卖|之和) | ⚠️ 含融券 |
| margin_money_bal_growth | 融资增量增长率因子 | (当期融资余额 /(20交易日前融资余额+1)) − 过去20日涨跌幅 | ✅ |
| margin_sell_sec_prop | 融券卖出占比因子 | 过去20日(融券卖出量·VWAP)之和 / 成交额之和 | ❌ 融券 quarantine |
| margin_money_bal_prop | 融资余额占比因子 | 当期融资余额 / 流通市值 | ✅ |
| margin_money_bal_growth（增量族） | 融资超额增长率因子 | (融资余额 /(20交易日前融资余额+1)) − 过去20日涨跌幅 | ✅ |
| net_margin_sell_sec_shift_dist | 净融券卖出的位移路程比因子 | 过去20日(融券卖出量·VWAP − 融券偿还量·VWAP)之和 / (|...|之和) | ❌ 融券 |
| margin_sell_sec_bal_growth | 融券增量增长率因子 | (当期融券余额 /(20交易日前融券余额+1)) − 过去20日涨跌幅 | ❌ 融券 |
| margin_sec_avg | 融券卖出因子 | 过去20日融券卖出量·VWAP / 成交额之和 | ❌ 融券 |
| margin_sec_bal_prop | 融券余额占比因子 | 当期融券余额 / 流通市值 | ❌ 融券 |

> 融资侧 ✅；融券侧 ❌（`$rqye`/`$rqchl` 仍 quarantine——与我方唯一字段不合格因子 `margin_net_buy_20d` 同因）。

## 9. 价量复合因子（图表100，等权加权构造）

中金价量复合 = 各类代表因子按给定权重等权合成（z-score 后加权）：

| 子块 | 成分（权重） |
|---|---|
| 动量-隔夜 | mmt_overnight_A (50%) + mmt_report_overnight (50%) |
| 动量-报告期 | mmt_report_jump_open (50%) + mmt_report_period (50%) |
| 动量-年动量 | mmt_off_limit_A (100%) |
| 反转 | mmt_intraday_M (50%) + mmt_range_M (50%) |
| 波动率 | vol_highlow_std_6M / vol_up_std_6M / vol_upshadow_std_6M / vol_w_downshadow_std_6M (各 25%) |
| 流动性-换手率 | liq_turn_std_6M (100%) |
| 流动性-价格弹性 | liq_shortcut_avg_1M (50%) + liq_vstd_1M (50%) |
| 资金流-大小单 | buy_shift_dist_l (50%) + act_buy_shift_dist_s (50%) |
| 资金流-开盘 | inflow_rate_open / inflow_prop_open / inflow_shift_dist_open (各 16.67%) + inflow_shift_dist_open_l (50%) |
| 北向-持仓占比 | north_hold_prefer (50%) + north_hold_prop (50%) |
| 北向-持仓变化 | north_hold_prop_lt_chg (50%) + north_hold_prop_st_chg (50%) |
| 量价相关性 | corr_ret_turnd_1M / corr_price_turn_1M / corr_ret_turn_post_1M (各 33.33%) |

> 这是中金给出的"价量大类复合"权重配方，可作为我方 Layer-2 价量复合的参照构造。

