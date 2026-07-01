# Tushare 数据接口 (document/2) — 全部接口正文合集

抓取自 https://tushare.pro/document/2 ，共 266 个接口。


---

### [14] 股票数据  ·  (顶级)
(api: — | 输出字段: 0 | PIT字段: 否)

# (doc_id=14)  https://tushare.pro/document/2?doc_id=14

## 上市公司数据
上市公司数据是Tushare最传统最有历史的数据服务项目，从一开始就为广大的投资者，尤其是量化投资者提供了稳定、便捷的接口。Tushare Pro版在继承了旧版API的便捷易用性的同时又加强了数据的广度和深度。最关键的是，数据来源和采集方式也发生了根本的变化，除了公开渠道的数据源，最重要的变化是Tushare构建起来了自有的数据存储和数据治理体系，同时依托平台化的维护和管理方式，让数据更稳定可靠，而且服务能力也能得到了质的变化。
Pro版首先提供的是基础数据，主要包括：
股票基础列表
上市公司信息
各交易所交易日历
沪深股通成份股
股票曾用名
IPO新股列表
在Tushare数据接口里，股票代码参数都叫ts_code，每种股票代码都有规范的后缀
| 交易所名称 | 交易所代码 | 股票代码后缀 | 备注 |
| --- | --- | --- | --- |
| 上海证券交易所 | SSE | .SH | 600000.SH(股票) 000001.SH(0开头指数) |
| 深圳证券交易所 | SZSE | .SZ | 000001.SZ(股票) 399005.SZ(3开头指数) |
| 北京证券交易所 | BSE | .BJ | 9开头的股票 |
| 香港证券交易所 | HKEX | .HK | 00001.HK |

当然，数据不仅上述所列，包括以下要介绍的部分，数据在一点点上线，社区朋友可以经常上来网站，或许会发现数据的更迭变化。
其次，就是最为重要的行情和财务数据部分，在行情数据方面，我们提供了：
日线行情
中高频的分钟行情
Tick级行情
大单成交数据
复权因子
停复牌信息
每日行情指标
在财务等反应上市公司基本面情况的数据方面，目前提供的有：
利润表
资产负债表
现金流量表
业绩预告
业绩快报
分红送股
财务指标数据
财务审计意见
主营业务构成
而在其他数据方面，其实也是对Tushare来说有很大发挥空间的市场行为和公司治理方面的参考数据，这一部分数据相信在未来很一段时间，我们都会作为一个重点来突破，为广大的社区用户和更多的投资者发掘、采集、整理和呈现好，一定会走心的为大家把数据的脏活累活消灭在各位写策略之前，让大家愉快的去实现自己的投资思想。总结一句话就是，大家只管安心的去挖矿赚钱就行了。
这部分数据，我们在这里暂时不一一罗列，已经在左侧菜单呈现，一目了然。


---

### [24] 基础数据  ·  股票数据
(api: — | 输出字段: 0 | PIT字段: 否)

# (doc_id=24)  https://tushare.pro/document/2?doc_id=24

## 基础数据
提供交易和回测所需要的基础信息，目前主要提供的是上市公司股票列表和交易日历等
股票列表
各交易所交易日历
沪深股通成份股
股票曾用名
上市公司基本信息
IPO新股列表


---

### [25] 股票列表  ·  股票数据 / 基础数据
(api: stock_basic | 输出字段: 17 | PIT字段: 否)

# (doc_id=25)  https://tushare.pro/document/2?doc_id=25

## 股票基础信息
接口：stock_basic，可以通过 数据工具 调试和查看数据 描述：获取基础信息数据，包括股票代码、名称、上市日期、退市日期等 限量：每次最多返回6000行数据（覆盖全市场A股，会随股票总数增长而增加） 权限：2000积分起，每分钟请求50次。此接口是基础信息，调取一次就可以拉取完，建议保存倒本地存储后使用
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | TS股票代码( 格式说明 ) |
| name | str | N | 名称 |
| market | str | N | 市场类别 （主板/创业板/科创板/CDR/北交所） |
| list_status | str | N | 上市状态 L上市 D退市 P暂停上市 G 未交易，默认是L |
| exchange | str | N | 交易所 SSE上交所 SZSE深交所 BSE北交所 |
| is_hs | str | N | 是否沪深港通标的，N否 H沪股通 S深股通 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS代码 |
| symbol | str | Y | 股票代码 |
| name | str | Y | 股票名称 |
| area | str | Y | 地域 |
| industry | str | Y | 所属行业 |
| fullname | str | N | 股票全称 |
| enname | str | N | 英文全称 |
| cnspell | str | Y | 拼音缩写 |
| market | str | Y | 市场类型（主板/创业板/科创板/CDR） |
| exchange | str | N | 交易所代码 |
| curr_type | str | N | 交易货币 |
| list_status | str | N | 上市状态 L上市 D退市 G过会未交易 P暂停上市 |
| list_date | str | Y | 上市日期 |
| delist_date | str | N | 退市日期 |
| is_hs | str | N | 是否沪深港通标的，N否 H沪股通 S深股通 |
| act_name | str | Y | 实控人名称 |
| act_ent_type | str | Y | 实控人企业性质 |

说明：旧版上的PE/PB/股本等字段，请在行情接口 “每日指标” 中获取。
接口示例
或者：
数据样例


---

### [329] 每日股本（盘前）  ·  股票数据 / 基础数据
(api: stk_premarket | 输出字段: 7 | PIT字段: 否)

# (doc_id=329)  https://tushare.pro/document/2?doc_id=329

## 股本情况（盘前）
接口：stk_premarket 描述：每日开盘前获取当日股票的股本情况，包括总股本和流通股本，涨跌停价格等。 限量：单次最大8000条数据，可循环提取 权限：与积分无关，可以 在线开通 权限。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码 |
| trade_date | str | N | 交易日期(YYYYMMDD格式，下同) |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 交易日期 |
| ts_code | str | Y | TS股票代码 |
| total_share | float | Y | 总股本（万股） |
| float_share | float | Y | 流通股本（万股） |
| pre_close | float | Y | 昨日收盘价 |
| up_limit | float | Y | 今日涨停价 |
| down_limit | float | Y | 今日跌停价 |

接口示例
数据示例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：stk_premarket 描述：每日开盘前获取当日股票的股本情况，包括总股本和流通股本，涨跌停价格等。 限量：单次最大8000条数据，可循环提取 权限：与积分无关，可以 在线开通 权限。


---

### [26] 交易日历  ·  股票数据 / 基础数据
(api: trade_cal | 输出字段: 4 | PIT字段: 否)

# (doc_id=26)  https://tushare.pro/document/2?doc_id=26

## 交易日历
接口：trade_cal，可以通过 数据工具 调试和查看数据。 描述：获取各大交易所交易日历数据,默认提取的是上交所 积分：需2000积分
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| exchange | str | N | 交易所 SSE上交所,SZSE深交所,CFFEX 中金所,SHFE 上期所,CZCE 郑商所,DCE 大商所,INE 上能源 |
| start_date | str | N | 开始日期 （格式：YYYYMMDD 下同） |
| end_date | str | N | 结束日期 |
| is_open | str | N | 是否交易 '0'休市 '1'交易 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| exchange | str | Y | 交易所 SSE上交所 SZSE深交所 |
| cal_date | str | Y | 日历日期 |
| is_open | str | Y | 是否交易 0休市 1交易 |
| pretrade_date | str | Y | 上一个交易日 |

接口示例
或者
数据样例


---

### [397] ST股票列表  ·  股票数据 / 基础数据
(api: stock_st | 输出字段: 5 | PIT字段: 否)

# (doc_id=397)  https://tushare.pro/document/2?doc_id=397

## ST股票列表
接口：stock_st，可以通过 数据工具 调试和查看数据。 描述：获取ST股票列表，可根据交易日期获取历史上每天的ST列表 权限：3000积分起 提示：每天上午9:20更新，单次请求最大返回1000行数据，可循环提取,本接口数据从20160101开始,太早历史无法补齐
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码 |
| trade_date | str | N | 交易日期（格式：YYYYMMDD下同） |
| start_date | str | N | 开始时间 |
| end_date | str | N | 结束时间 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| name | str | Y | 股票名称 |
| trade_date | str | Y | 交易日期 |
| type | str | Y | 类型 |
| type_name | str | Y | 类型名称 |

接口用法
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：stock_st，可以通过 数据工具 调试和查看数据。 描述：获取ST股票列表，可根据交易日期获取历史上每天的ST列表 权限：3000积分起 提示：每天上午9:20更新，单次请求最大返回1000行数据，可循环提取,本接口数据从20160101开始,太早历史无法补齐


---

### [423] ST风险警示板股票  ·  股票数据 / 基础数据
(api: st | 输出字段: 7 | PIT字段: 是)

# (doc_id=423)  https://tushare.pro/document/2?doc_id=423

## ST风险警示板股票
## 接口介绍
接口：st 描述：ST风险警示板股票列表 限量：单次最大1000，可根据股票代码循环获取历史数据 积分：6000积分可提取数据，具体请参阅 积分获取办法
## 输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码 |
| pub_date | str | N | 发布日期 |
| imp_date | str | N | 实施日期 |

## 输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| name | str | Y | 股票名称 |
| pub_date | str | Y | 发布日期 |
| imp_date | str | Y | 实施日期 |
| st_tpye | str | Y | 类型 |
| st_reason | str | Y | st变更原因 |
| st_explain | str | Y | st变更详细原因 |

## 代码示例
## 数据结果
| ts_code | name | pub_date | imp_date | st_tpye | st_reason | st_explain |
| --- | --- | --- | --- | --- | --- | --- |
| 300125.SZ | *ST聆达 | 20260127 | 20260128 | 撤销叠加*ST | 重整完成或和解协议执行完成或案件结束 | 公司重整计划已经执行完毕,根据《上市规则》第10.4.14条第一款的规定,公司符合申请撤销因重整而实施的退市风险警示的条件,公司已于2026年1月8日向深圳证券交易所(以下简称:深交所)申请撤销因重整而实施的退市风险警示。2026年1月27日,深交所审核同意撤销公司因重整而实施的退市风险警示,公司触及财务类退市风险警示及其他风险警示的情形保持不变。 |
| 300125.SZ | *ST聆达 | 20251119 | 20251119 | 叠加*ST | 法院依法受理公司重整、和解或者破产清算申请 | 公司2024年扣除非经常性损益后的净利润为负且扣除后营业收入低于1亿元;最近一个会计年度经审计的期末净资产为负值,公司股票交易于2025年4月25日起被实施退市风险警示;因六安中院依法裁定受理申请人对公司的重整申请,根据《深交所创业板股票上市规则》的规定,公司股票将于2025年11月19开市被叠加实施退市风险警示。 |
| 300125.SZ | *ST聆达 | 20250424 | 20250425 | 从ST变为*ST | 最近一个会计年度经审计的利润总额、净利润或者扣除非经常性损益后的净利润孰低者为负值且营业收入低于1亿元，或者追溯重述后最近一个会计年度利润总额、净利润或者扣除非经常性损益后的净利润孰低者为负值且营业收入低于1亿元 | 公司2024年度经审计的扣除非经常性损益后的净利润为-85,579万元且扣除后营业收入为5,785万元,期末净资产为-53,841万元。根据《上市规则》第10.3.1条第一款第(一)(二)项规定:上市公司出现“最近一个会计年度经审计的利润总额、净利润、扣除非经常性损益后的净利润三者孰低为负值,且扣除后的营业收入低于1亿元的情形。”;“最近一个会计年度经审计的期末净资产为负值”,公司股票交易将被实施退市风险警示。 |
| 300125.SZ | ST聆达 | 20240819 | 20240819 | 叠加ST | 公司向控股股东或其关联方提供资金或违反规定程序对外提供担保且情形严重 | 公司及子公司金寨嘉悦新能源科技有限公司、格尔木神光新能源有限公司在未履行董事会审议程序及信息披露义务的情况下,违规为中财招商投资集团商业保理有限公司与金寨嘉悦正丰新能源有限公司的借款合同提供担保,涉及担保金额1600万元。 |
| 300125.SZ | ST聆达 | 20240427 | 20240430 | ST | 公司最近一年被出具无法表示意见或者否定意见的内部控制审计报告或者鉴证报告 | 根据《深圳证券交易所创业板股票上市规则》第9.7条等相关规定,公司股票将于2024年4月29日停牌一天,2024年4月30日实施其他风险警示,实施其他风险警示后公司股价的日涨跌幅限制为20%。 |


## [PIT / 更新口径 — 自动标记]
- (正文) 接口：st 描述：ST风险警示板股票列表 限量：单次最大1000，可根据股票代码循环获取历史数据 积分：6000积分可提取数据，具体请参阅 积分获取办法
- (字段) `pub_date` — str N 发布日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `pub_date` — str Y 发布日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [398] 沪深港通股票列表  ·  股票数据 / 基础数据
(api: stock_hsgt | 输出字段: 5 | PIT字段: 否)

# (doc_id=398)  https://tushare.pro/document/2?doc_id=398

## 沪深港通股票列表
接口：stock_hsgt，可以通过 数据工具 调试和查看数据。 描述：获取沪深港通股票列表 权限：3000积分起 提示：每天上午9:20更新，单次请求最大返回2000行数据，可根据类型循环提取,本接口数据从20250812开始
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码 |
| trade_date | str | N | 交易日期（格式：YYYYMMDD） |
| type | str | Y | 类型（参考下表） |
| start_date | str | N | 开始时间 |
| end_date | str | N | 结束时间 |

类型说明如下：
| 类型 | 类型名称 |
| --- | --- |
| HK_SZ | 深股通(港>深) |
| SZ_HK | 港股通(深>港) |
| HK_SH | 沪股通(港>沪) |
| SH_HK | 港股通(沪>港) |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| trade_date | str | Y | 交易日期 |
| type | str | Y | 类型 |
| name | str | Y | 股票名称 |
| type_name | str | Y | 类型名称 |

接口用法
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：stock_hsgt，可以通过 数据工具 调试和查看数据。 描述：获取沪深港通股票列表 权限：3000积分起 提示：每天上午9:20更新，单次请求最大返回2000行数据，可根据类型循环提取,本接口数据从20250812开始


---

### [100] 股票曾用名  ·  股票数据 / 基础数据
(api: namechange | 输出字段: 6 | PIT字段: 是)

# (doc_id=100)  https://tushare.pro/document/2?doc_id=100

## 股票曾用名
接口：namechange 描述：历史名称变更记录
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | TS代码 |
| start_date | str | N | 公告开始日期 |
| end_date | str | N | 公告结束日期 |

输出参数
| 名称 | 类型 | 默认输出 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS代码 |
| name | str | Y | 证券名称 |
| start_date | str | Y | 开始日期 |
| end_date | str | Y | 结束日期 |
| ann_date | str | Y | 公告日期 |
| change_reason | str | Y | 变更原因 |

接口示例
数据样例

## [PIT / 更新口径 — 自动标记]
- (字段) `ann_date` — str Y 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [112] 上市公司基本信息  ·  股票数据 / 基础数据
(api: stock_company | 输出字段: 18 | PIT字段: 否)

# (doc_id=112)  https://tushare.pro/document/2?doc_id=112

## 上市公司基本信息
接口：stock_company，可以通过 数据工具 调试和查看数据。 描述：获取上市公司基础信息，单次提取4500条，可以根据交易所分批提取 积分：用户需要至少120积分才可以调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必须 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码 |
| exchange | str | N | 交易所代码 ，SSE上交所 SZSE深交所 BSE北交所 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| com_name | str | Y | 公司全称 |
| com_id | str | Y | 统一社会信用代码 |
| exchange | str | Y | 交易所代码 |
| chairman | str | Y | 法人代表 |
| manager | str | Y | 总经理 |
| secretary | str | Y | 董秘 |
| reg_capital | float | Y | 注册资本(万元) |
| setup_date | str | Y | 注册日期 |
| province | str | Y | 所在省份 |
| city | str | Y | 所在城市 |
| introduction | str | N | 公司介绍 |
| website | str | Y | 公司主页 |
| email | str | Y | 电子邮件 |
| office | str | N | 办公室 |
| employees | int | Y | 员工人数 |
| main_business | str | N | 主要业务及产品 |
| business_scope | str | N | 经营范围 |

接口示例
数据示例


---

### [193] 上市公司管理层  ·  股票数据 / 基础数据
(api: stk_managers | 输出字段: 12 | PIT字段: 是)

# (doc_id=193)  https://tushare.pro/document/2?doc_id=193

## 上市公司管理层
接口：stk_managers 描述：获取上市公司管理层 积分：用户需要2000积分才可以调取，5000积分以上频次相对较高，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码，支持单个或多个股票输入 |
| ann_date | str | N | 公告日期（YYYYMMDD格式，下同） |
| start_date | str | N | 公告开始日期 |
| end_date | str | N | 公告结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS股票代码 |
| ann_date | str | Y | 公告日期 |
| name | str | Y | 姓名 |
| gender | str | Y | 性别 |
| lev | str | Y | 岗位类别 |
| title | str | Y | 岗位 |
| edu | str | Y | 学历 |
| national | str | Y | 国籍 |
| birthday | str | Y | 出生年月 |
| begin_date | str | Y | 上任日期 |
| end_date | str | Y | 离任日期 |
| resume | str | N | 个人简历 |

接口用例
数据样例

## [PIT / 更新口径 — 自动标记]
- (字段) `ann_date` — str N 公告日期（YYYYMMDD格式，下同）  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `ann_date` — str Y 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [194] 管理层薪酬和持股  ·  股票数据 / 基础数据
(api: stk_rewards | 输出字段: 7 | PIT字段: 是)

# (doc_id=194)  https://tushare.pro/document/2?doc_id=194

## 管理层薪酬和持股
接口：stk_rewards 描述：获取上市公司管理层薪酬和持股 积分：用户需要2000积分才可以调取，5000积分以上频次相对较高，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS股票代码，支持单个或多个代码输入 |
| end_date | str | N | 报告期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS股票代码 |
| ann_date | str | Y | 公告日期 |
| end_date | str | Y | 截止日期 |
| name | str | Y | 姓名 |
| title | str | Y | 职务 |
| reward | float | Y | 报酬 |
| hold_vol | float | Y | 持股数 |

接口用例
数据样例

## [PIT / 更新口径 — 自动标记]
- (字段) `ann_date` — str Y 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [375] 北交所新旧代码对照  ·  股票数据 / 基础数据
(api: bse_mapping | 输出字段: 4 | PIT字段: 否)

# (doc_id=375)  https://tushare.pro/document/2?doc_id=375

## 北交所新旧代码对照表
接口：bse_mapping 描述：获取北交所股票代码变更后新旧代码映射表数据 限量：单次最大1000条（本接口总数据量300以内） 积分：120积分即可调取
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| o_code | str | N | 旧代码 |
| n_code | str | N | 新代码 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| name | str | Y | 股票名称 |
| o_code | str | Y | 原代码 |
| n_code | str | Y | 新代码 |
| list_date | str | Y | 上市日期 |

接口示例
数据示例


---

### [123] IPO新股上市  ·  股票数据 / 基础数据
(api: new_share | 输出字段: 12 | PIT字段: 否)

# (doc_id=123)  https://tushare.pro/document/2?doc_id=123

## IPO新股列表
接口：new_share 描述：获取新股上市列表数据 限量：单次最大2000条，总量不限制 积分：用户需要至少120积分才可以调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| start_date | str | N | 上网发行开始日期 |
| end_date | str | N | 上网发行结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS股票代码 |
| sub_code | str | Y | 申购代码 |
| name | str | Y | 名称 |
| ipo_date | str | Y | 上网发行日期 |
| issue_date | str | Y | 上市日期 |
| amount | float | Y | 发行总量（万股） |
| market_amount | float | Y | 上网发行总量（万股） |
| price | float | Y | 发行价格 |
| pe | float | Y | 市盈率 |
| limit_amount | float | Y | 个人申购上限（万股） |
| funds | float | Y | 募集资金（亿元） |
| ballot | float | Y | 中签率 |

接口示例
数据示例


---

### [262] 股票历史列表  ·  股票数据 / 基础数据
(api: bak_basic | 输出字段: 24 | PIT字段: 否)

# (doc_id=262)  https://tushare.pro/document/2?doc_id=262

## 股票历史列表（历史每天股票列表）
接口：bak_basic 描述：获取备用基础列表，数据从2016年开始 限量：单次最大7000条，可以根据日期参数循环获取历史，正式权限需要5000积分。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | N | 交易日期 |
| ts_code | str | N | 股票代码 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 交易日期 |
| ts_code | str | Y | TS股票代码 |
| name | str | Y | 股票名称 |
| industry | str | Y | 行业 |
| area | str | Y | 地域 |
| pe | float | Y | 市盈率（动） |
| float_share | float | Y | 流通股本（亿） |
| total_share | float | Y | 总股本（亿） |
| total_assets | float | Y | 总资产（亿） |
| liquid_assets | float | Y | 流动资产（亿） |
| fixed_assets | float | Y | 固定资产（亿） |
| reserved | float | Y | 公积金 |
| reserved_pershare | float | Y | 每股公积金 |
| eps | float | Y | 每股收益 |
| bvps | float | Y | 每股净资产 |
| pb | float | Y | 市净率 |
| list_date | str | Y | 上市日期 |
| undp | float | Y | 未分配利润 |
| per_undp | float | Y | 每股未分配利润 |
| rev_yoy | float | Y | 收入同比（%） |
| profit_yoy | float | Y | 利润同比（%） |
| gpr | float | Y | 毛利率（%） |
| npr | float | Y | 净利润率（%） |
| holder_num | int | Y | 股东人数 |

接口示例
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：bak_basic 描述：获取备用基础列表，数据从2016年开始 限量：单次最大7000条，可以根据日期参数循环获取历史，正式权限需要5000积分。


---

### [15] 行情数据  ·  股票数据
(api: — | 输出字段: 0 | PIT字段: 否)

# (doc_id=15)  https://tushare.pro/document/2?doc_id=15

## 行情数据
Tushare行情数据目前已经具备高可用高稳定性，提供了包括股票、指数、基金、期货等在内的质量比较高的日线行情和分钟行情。而且也像老版本中ts.bar接口一样，提供了一个统一的行情数据输出标准接口。
分钟行情
日线行情
周线行情
月线行情
复权行情
复权因子
停复牌信息
每日行情指标
通用行情接口


---

### [27] 历史日线  ·  股票数据 / 行情数据
(api: daily | 输出字段: 11 | PIT字段: 否)

# (doc_id=27)  https://tushare.pro/document/2?doc_id=27

## A股日线行情
接口：daily，可以通过 数据工具 调试和查看数据 数据说明：交易日每天15点～16点之间入库。本接口是未复权行情，停牌期间不提供数据 调取说明：基础积分每分钟内可调取500次，每次6000条数据，一次请求相当于提取一个股票23年历史 描述：获取股票行情数据，或通过 通用行情接口 获取数据，包含了前后复权数据
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码（支持多个股票同时提取，逗号分隔） |
| trade_date | str | N | 交易日期（YYYYMMDD） |
| start_date | str | N | 开始日期(YYYYMMDD) |
| end_date | str | N | 结束日期(YYYYMMDD) |

注：日期都填YYYYMMDD格式，比如20181010
输出参数
| 名称 | 类型 | 描述 |
| --- | --- | --- |
| ts_code | str | 股票代码 |
| trade_date | str | 交易日期 |
| open | float | 开盘价 |
| high | float | 最高价 |
| low | float | 最低价 |
| close | float | 收盘价 |
| pre_close | float | 昨收价【除权价】 |
| change | float | 涨跌额 |
| pct_chg | float | 涨跌幅（%） 【基于除权后的昨收计算的涨跌幅：（今收-除权昨收）/除权昨收 】 |
| vol | float | 成交量 （手） |
| amount | float | 成交额 （千元） |

接口示例
或者
也可以通过日期取历史某一天的全部历史
数据样例


---

### [372] 实时日线  ·  股票数据 / 行情数据
(api: rt_k | 输出字段: 15 | PIT字段: 否)

# (doc_id=372)  https://tushare.pro/document/2?doc_id=372

## A股实时日线
接口：rt_k 描述：获取实时日k线行情，支持按股票代码及股票代码通配符一次性提取全部股票实时日k线行情 限量：单次最大可提取6000条数据，等同于一次提取全市场 积分：本接口是单独开权限的数据，单独申请权限请参考 权限列表 ，可以 在线开通 权限。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 支持通配符方式，e.g. 所有上交所股票：6*.SH、所有创业板股票3*.SZ、所有科创板股票688*.SH，或单个股票600000.SH |

注：ts_code代码一定要带 .SH/.SZ/.BJ 后缀
输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| name | None | Y | 股票名称 |
| pre_close | float | Y | 昨收价 |
| high | float | Y | 最高价 |
| open | float | Y | 开盘价 |
| low | float | Y | 最低价 |
| close | float | Y | 收盘价（最新价） |
| vol | int | Y | 成交量（股） |
| amount | int | Y | 成交金额（元） |
| num | int | Y | 开盘以来成交笔数 |
| ask_price1 | float | N | 委托卖盘（元） |
| ask_volume1 | int | N | 委托卖盘（股） |
| bid_price1 | float | N | 委托买盘（元） |
| bid_volume1 | int | N | 委托买盘（股） |
| trade_time | str | N | 交易时间 |

接口示例
数据示例


---

### [370] 历史分钟  ·  股票数据 / 行情数据
(api: stk_mins | 输出字段: 8 | PIT字段: 否)

# (doc_id=370)  https://tushare.pro/document/2?doc_id=370

## 股票历史分钟行情
接口：stk_mins 描述：获取A股分钟数据，支持1min/5min/15min/30min/60min行情，提供Python SDK和 http Restful API两种方式 限量：单次最大8000行数据，可以通过股票代码和时间循环获取，本接口可以提供超过10年历史分钟数据 权限：需单独开权限，正式权限请参阅 权限说明 ，可以 在线开通 分钟权限。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码，e.g. 600000.SH |
| freq | str | Y | 分钟频度（1min/5min/15min/30min/60min） |
| start_date | datetime | N | 开始日期 格式：2023-08-25 09:00:00 |
| end_date | datetime | N | 结束时间 格式：2023-08-25 19:00:00 |

freq参数说明
| freq | 说明 |
| --- | --- |
| 1min | 1分钟 |
| 5min | 5分钟 |
| 15min | 15分钟 |
| 30min | 30分钟 |
| 60min | 60分钟 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| trade_time | str | Y | 交易时间 |
| open | float | Y | 开盘价 |
| close | float | Y | 收盘价 |
| high | float | Y | 最高价 |
| low | float | Y | 最低价 |
| vol | int | Y | 成交量(股) |
| amount | float | Y | 成交金额（元） |

接口用法
数据样例


---

### [374] 实时分钟  ·  股票数据 / 行情数据
(api: rt_min | 输出字段: 8 | PIT字段: 否)

# (doc_id=374)  https://tushare.pro/document/2?doc_id=374

## A股实时分钟
接口：rt_min 描述：获取全A股票实时分钟数据，包括1~60min 限量：单次最大1000行数据，可以通过股票代码提取数据，支持逗号分隔的多个代码同时提取 权限：正式权限请参阅 权限说明
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| freq | str | Y | 1MIN,5MIN,15MIN,30MIN,60MIN （大写） |
| ts_code | str | Y | 支持单个和多个：600000.SH 或者 600000.SH,000001.SZ |

freq参数说明
| freq | 说明 |
| --- | --- |
| 1MIN | 1分钟 |
| 5MIN | 5分钟 |
| 15MIN | 15分钟 |
| 30MIN | 30分钟 |
| 60MIN | 60分钟 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| code | str | Y | 股票代码 |
| time | None | Y | 交易时间 |
| open | float | Y | 开盘价 |
| close | float | Y | 收盘价 |
| high | float | Y | 最高价 |
| low | float | Y | 最低价 |
| vol | float | Y | 成交量(股） |
| amount | float | Y | 成交额（元） |

接口用法


---

### [457] A股实时分钟-日累计  ·  股票数据 / 行情数据
(api: rt_min_daily | 输出字段: 9 | PIT字段: 否)

# (doc_id=457)  https://tushare.pro/document/2?doc_id=457

## A股实时分钟-日累计
## 接口介绍
接口：rt_min_daily 描述：获取A股当日盘中历史分钟数据，可以提取单只股票当日开盘以来的所有分钟数据 权限：开通了实时分钟权限自动获得本接口权限
## 输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| freq | str | Y | 频度：1MIN,5MIN,15MIN,30MIN,60MIN |
| ts_code | str | Y | 股票代码，如：600000.SH |

## 输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| freq | None | Y | 频次 |
| time | None | Y | 交易时间 |
| open | float | Y | 开盘价 |
| close | float | Y | 收盘价 |
| high | float | Y | 最高价 |
| low | float | Y | 最低价 |
| vol | float | Y | 成交量(股） |
| amount | float | Y | 成交额（元） |

## 代码示例
## 数据结果


---

### [144] 周线行情  ·  股票数据 / 行情数据
(api: weekly | 输出字段: 11 | PIT字段: 否)

# (doc_id=144)  https://tushare.pro/document/2?doc_id=144

## 周线行情
接口：weekly 描述：获取A股周线行情，本接口每周最后一个交易日更新，如需要使用每天更新的周线数据，请使用 日度更新的周线行情接口 。 限量：单次最大6000行，可使用交易日期循环提取，总量不限制 积分：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | TS代码 （ts_code,trade_date两个参数任选一） |
| trade_date | str | N | 交易日期 （每周最后一个交易日期，YYYYMMDD格式） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| trade_date | str | Y | 交易日期 |
| close | float | Y | 周收盘价 |
| open | float | Y | 周开盘价 |
| high | float | Y | 周最高价 |
| low | float | Y | 周最低价 |
| pre_close | float | Y | 上一周收盘价 |
| change | float | Y | 周涨跌额 |
| pct_chg | float | Y | 周涨跌 （未复权，未 100，如果是复权请用 通用行情接口 ，如需%单位请 100 ） |
| vol | float | Y | 周成交量 |
| amount | float | Y | 周成交额 |

接口用法
或者
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：weekly 描述：获取A股周线行情，本接口每周最后一个交易日更新，如需要使用每天更新的周线数据，请使用 日度更新的周线行情接口 。 限量：单次最大6000行，可使用交易日期循环提取，总量不限制 积分：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法


---

### [145] 月线行情  ·  股票数据 / 行情数据
(api: monthly | 输出字段: 11 | PIT字段: 否)

# (doc_id=145)  https://tushare.pro/document/2?doc_id=145

## 月线行情
接口：monthly 描述：获取A股月线数据 限量：单次最大4500行，总量不限制 积分：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | TS代码 （ts_code,trade_date两个参数任选一） |
| trade_date | str | N | 交易日期 （每月最后一个交易日日期，YYYYMMDD格式） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| trade_date | str | Y | 交易日期 |
| close | float | Y | 月收盘价 |
| open | float | Y | 月开盘价 |
| high | float | Y | 月最高价 |
| low | float | Y | 月最低价 |
| pre_close | float | Y | 上月收盘价 |
| change | float | Y | 月涨跌额 |
| pct_chg | float | Y | 月涨跌幅 （未复权，如果是复权请用 通用行情接口 ） |
| vol | float | Y | 月成交量 |
| amount | float | Y | 月成交额 |

接口用法
或者
数据样例


---

### [146] 复权行情  ·  股票数据 / 行情数据
(api: — | 输出字段: 0 | PIT字段: 否)

# (doc_id=146)  https://tushare.pro/document/2?doc_id=146

## A股复权行情
接口名称 ：pro_bar 接口说明 ：复权行情通过 通用行情接口 实现，利用Tushare Pro提供的 复权因子 进行动态计算，因此http方式无法调取。若需要静态复权行情（支持http），请访问 股票技术因子接口 。 Python SDK版本要求 ： >= 1.2.26
复权说明
| 类型 | 算法 | 参数标识 |
| --- | --- | --- |
| 不复权 | 无 | 空或None |
| 前复权 | 当日收盘价 × 当日复权因子 / 最新复权因子 | qfq |
| 后复权 | 当日收盘价 × 当日复权因子 | hfq |

注：目前只支持A股的日线复权。在Tushare数据接口里，不管是旧版的一些接口还是Pro版的行情接口，都是以用户设定的end_date开始往前复权，跟所有行情软件或者财经网站上看到的前复权可能存在差异，因为行情软件都是以最近一个交易日开始往前复权的。比如今天是2018年10月26日，您想查2018年1月5日～2018年9月28日的前复权数据，Tushare是先查找9月28日的复权因子，从28日开始复权，而行情软件是从10月26日这天开始复权的。同时，Tushare的复权采用“分红再投”模式计算。
接口参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 证券代码 |
| start_date | str | N | 开始日期 (格式：YYYYMMDD) |
| end_date | str | N | 结束日期 (格式：YYYYMMDD) |
| asset | str | Y | 资产类别：E股票 I沪深指数 FT期货 FD基金 O期权，默认E |
| adj | str | N | 复权类型(只针对股票)：None未复权 qfq前复权 hfq后复权 , 默认None |
| freq | str | Y | 数据频度 ：1MIN表示1分钟（1/5/15/30/60分钟） D日线 ，默认D |
| ma | list | N | 均线，支持任意周期的均价和均量，输入任意合理int数值 |

接口用例
日线复权
周线复权
月线复权


---

### [336] 周/月线行情(每日更新)  ·  股票数据 / 行情数据
(api: stk_weekly_monthly | 输出字段: 13 | PIT字段: 否)

# (doc_id=336)  https://tushare.pro/document/2?doc_id=336

## 股票周/月线行情(每日更新)
接口：stk_weekly_monthly 描述：股票周/月线行情(每日更新) 限量：单次最大6000,可使用交易日期循环提取，总量不限制 积分：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | TS代码 |
| trade_date | str | N | 交易日期(格式：YYYYMMDD，每周或每月最后一天的日期） |
| start_date | str | N | 开始交易日期 |
| end_date | str | N | 结束交易日期 |
| freq | str | Y | 频率week周，month月 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| trade_date | str | Y | 交易日期 |
| end_date | str | Y | 计算截至日期 |
| freq | str | Y | 频率(周week,月month) |
| open | float | Y | (周/月)开盘价 |
| high | float | Y | (周/月)最高价 |
| low | float | Y | (周/月)最低价 |
| close | float | Y | (周/月)收盘价 |
| pre_close | float | Y | 上一(周/月)收盘价 |
| vol | float | Y | (周/月)成交量 |
| amount | float | Y | (周/月)成交额 |
| change | float | Y | (周/月)涨跌额 |
| pct_chg | float | Y | (周/月)涨跌幅(未复权,如果是复权请用 通用行情接口) |

接口用法
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：stk_weekly_monthly 描述：股票周/月线行情(每日更新) 限量：单次最大6000,可使用交易日期循环提取，总量不限制 积分：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法


---

### [365] 周/月线复权行情(每日更新)  ·  股票数据 / 行情数据
(api: stk_week_month_adj | 输出字段: 0 | PIT字段: 否)

# (doc_id=365)  https://tushare.pro/document/2?doc_id=365

## 股票周/月线行情(复权--每日更新)
接口：stk_week_month_adj 描述：股票周/月线行情(复权--每日更新) 限量：单次最大6000,可使用交易日期循环提取，总量不限制 积分：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | TS代码 |
| trade_date | str | N | 交易日期（格式：YYYYMMDD，每周或每月最后一天的日期） |
| start_date | str | N | 开始交易日期 |
| end_date | str | N | 结束交易日期 |
| freq | str | Y | 频率week周，month月 |

| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| trade_date | str | Y | 交易日期（每周五或者月末日期） |
| end_date | str | Y | 计算截至日期 |
| freq | str | Y | 频率(周week,月month) |
| open | float | Y | (周/月)开盘价 |
| high | float | Y | (周/月)最高价 |
| low | float | Y | (周/月)最低价 |
| close | float | Y | (周/月)收盘价 |
| pre_close | float | Y | 上一(周/月)收盘价【除权价，前复权】 |
| open_qfq | float | Y | 前复权(周/月)开盘价 |
| high_qfq | float | Y | 前复权(周/月)最高价 |
| low_qfq | float | Y | 前复权(周/月)最低价 |
| close_qfq | float | Y | 前复权(周/月)收盘价 |
| open_hfq | float | Y | 后复权(周/月)开盘价 |
| high_hfq | float | Y | 后复权(周/月)最高价 |
| low_hfq | float | Y | 后复权(周/月)最低价 |
| close_hfq | float | Y | 后复权(周/月)收盘价 |
| vol | float | Y | (周/月)成交量 |
| amount | float | Y | (周/月)成交额 |
| change | float | Y | (周/月)涨跌额 |
| pct_chg | float | Y | (周/月)涨跌幅 【基于除权后的昨收计算的涨跌幅：（今收-除权昨收）/除权昨收 】 |

数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：stk_week_month_adj 描述：股票周/月线行情(复权--每日更新) 限量：单次最大6000,可使用交易日期循环提取，总量不限制 积分：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法


---

### [28] 复权因子  ·  股票数据 / 行情数据
(api: adj_factor | 输出字段: 3 | PIT字段: 否)

# (doc_id=28)  https://tushare.pro/document/2?doc_id=28

## 复权因子
接口：adj_factor，可以通过 数据工具 调试和查看数据。 更新时间：盘前9点15~20分完成当日复权因子入库 描述：本接口由Tushare自行生产，获取股票复权因子，可提取单只股票全部历史复权因子，也可以提取单日全部股票的复权因子。 积分要求：2000积分起，5000以上可高频调取
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码 |
| trade_date | str | N | 交易日期(YYYYMMDD，下同) |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

注：日期都填YYYYMMDD格式，比如20181010
输出参数
| 名称 | 类型 | 描述 |
| --- | --- | --- |
| ts_code | str | 股票代码 |
| trade_date | str | 交易日期 |
| adj_factor | float | 复权因子 |

接口示例
或者
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：adj_factor，可以通过 数据工具 调试和查看数据。 更新时间：盘前9点15~20分完成当日复权因子入库 描述：本接口由Tushare自行生产，获取股票复权因子，可提取单只股票全部历史复权因子，也可以提取单日全部股票的复权因子。 积分要求：2000积分起，5000以上可高频调取


---

### [32] 每日指标  ·  股票数据 / 行情数据
(api: daily_basic | 输出字段: 18 | PIT字段: 否)

# (doc_id=32)  https://tushare.pro/document/2?doc_id=32

## 每日指标
接口：daily_basic，可以通过 数据工具 调试和查看数据。 更新时间：交易日每日15点～17点之间 描述：获取全部股票每日重要的基本面指标，可用于选股分析、报表展示等。单次请求最大返回6000条数据，可按日线循环提取全部历史。 积分：至少2000积分才可以调取，5000积分无总量限制，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码（二选一） |
| trade_date | str | N | 交易日期 （二选一） |
| start_date | str | N | 开始日期(YYYYMMDD) |
| end_date | str | N | 结束日期(YYYYMMDD) |

注：日期都填YYYYMMDD格式，比如20181010
输出参数
| 名称 | 类型 | 描述 |
| --- | --- | --- |
| ts_code | str | TS股票代码 |
| trade_date | str | 交易日期 |
| close | float | 当日收盘价 |
| turnover_rate | float | 换手率（%） |
| turnover_rate_f | float | 换手率（自由流通股） |
| volume_ratio | float | 量比 |
| pe | float | 市盈率（总市值/净利润， 亏损的PE为空） |
| pe_ttm | float | 市盈率（TTM，亏损的PE为空） |
| pb | float | 市净率（总市值/净资产） |
| ps | float | 市销率 |
| ps_ttm | float | 市销率（TTM） |
| dv_ratio | float | 股息率 （%），除息日发生在去年期间的派现 |
| dv_ttm | float | 股息率（TTM）（%），除息日在近12个月且分红报告期在12个月以内的派现 |
| total_share | float | 总股本 （万股） |
| float_share | float | 流通股本 （万股） |
| free_share | float | 自由流通股本 （万） |
| total_mv | float | 总市值 （万元） |
| circ_mv | float | 流通市值（万元） |

接口用法
或者
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：daily_basic，可以通过 数据工具 调试和查看数据。 更新时间：交易日每日15点～17点之间 描述：获取全部股票每日重要的基本面指标，可用于选股分析、报表展示等。单次请求最大返回6000条数据，可按日线循环提取全部历史。 积分：至少2000积分才可以调取，5000积分无总量限制，具体请参阅 积分获取办法


---

### [109] 通用行情接口  ·  股票数据 / 行情数据
(api: — | 输出字段: 0 | PIT字段: 否)

# (doc_id=109)  https://tushare.pro/document/2?doc_id=109

## 通用行情接口
接口名称 ：pro_bar，本接口是集成开发接口，部分指标是现用现算 更新时间 ：股票和指数通常在15点～17点之间，具体请参考各接口文档明细。 描述 ：目前整合了股票（未复权、前复权、后复权）、指数、ETF基金、期货、期权的行情数据，未来还将整合包括外汇在内的所有交易行情数据，同时提供分钟数据。不同数据对应不同的积分要求，具体请参阅每类数据的文档说明。 其它 ：由于本接口是集成接口，在SDK层做了一些逻辑处理，目前暂时没法用http的方式调取通用行情接口。用户可以访问Tushare的Github，查看源代码完成类似功能。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 证券代码，不支持多值输入，多值输入获取结果会有重复记录 |
| start_date | str | N | 开始日期 (日线格式：YYYYMMDD，提取分钟数据请用2019-09-01 09:00:00这种格式) |
| end_date | str | N | 结束日期 (日线格式：YYYYMMDD) |
| asset | str | N | 资产类别：E股票 I沪深指数 FT期货 FD基金 O期权 CB可转债（v1.2.39），如果不填默认为E |
| adj | str | N | 复权类型(只针对股票)：None未复权 qfq前复权 hfq后复权 , 默认None， 目前只支持日线复权 ，同时复权机制是根据设定的end_date参数动态复权，采用分红再投模式，具体请参考 常见问题列表 里的说明。 |
| freq | str | N | 数据频度 ：支持分钟(min)/日(D)/周(W)/月(M)K线，其中1min表示1分钟（类推1/5/15/30/60分钟） ，如果不填默认为D。对于分钟数据有600积分用户可以试用（请求2次），正式权限可以参考 权限列表说明 ，使用方法请参考 股票分钟使用方法 。 |
| ma | list | N | 均线，支持任意合理int数值。注：均线是动态计算，要设置一定时间范围才能获得相应的均线，比如5日均线，开始和结束日期参数跨度必须要超过5日。目前只支持单一个股票提取均线，即需要输入ts_code参数。e.g: ma_5表示5日均价，ma_v_5表示5日均量 |
| factors | list | N | 股票因子（asset='E'有效）支持 tor换手率 vr量比 |
| adjfactor | str | N | 复权因子，在复权数据时，如果此参数为True，返回的数据中则带复权因子，默认为False。 该功能从1.2.33版本开始生效 |

输出指标
具体输出的数据指标可参考各行情具体指标：
股票Daily： https://tushare.pro/document/2?doc_id=27
基金Daily： https://tushare.pro/document/2?doc_id=127
期货Daily： https://tushare.pro/document/2?doc_id=138
期权Daily： https://tushare.pro/document/2?doc_id=159
指数Daily： https://tushare.pro/document/2?doc_id=95
接口用例
注：Tushare pro_bar接口的均价和均量数据是动态计算，想要获取某个时间段的均线，必须要设置start_date日期大于最大均线的日期数，然后自行截取想要日期段。例如，想要获取20190801开始的3日均线，必须设置start_date='20190729'，然后剔除20190801之前的日期记录。
说明
对于pro_api参数，如果在一开始就通过 ts.set_token('xxxx') 设置过token的情况，这个参数就不是必需的。
例如：

## [PIT / 更新口径 — 自动标记]
- (正文) 接口名称 ：pro_bar，本接口是集成开发接口，部分指标是现用现算 更新时间 ：股票和指数通常在15点～17点之间，具体请参考各接口文档明细。 描述 ：目前整合了股票（未复权、前复权、后复权）、指数、ETF基金、期货、期权的行情数据，未来还将整合包括外汇在内的所有交易行情数据，同时提供分钟数据。不同数据对应不同的积分要求，具体请参阅每类数据的文档说明。 其它 ：由于本接口是集成接口，在SDK层做了一些逻辑处理，目前暂时没法用http的方式调取通用行情接口。用户可以访问Tushare的Github，查看源代码完成类似功能。


---

### [183] 每日涨跌停价格  ·  股票数据 / 行情数据
(api: stk_limit | 输出字段: 5 | PIT字段: 否)

# (doc_id=183)  https://tushare.pro/document/2?doc_id=183

## 每日涨跌停价格
接口：stk_limit 描述：获取全市场（包含A/B股和基金）每日涨跌停价格，包括涨停价格，跌停价格等，每个交易日8点40左右更新当日股票涨跌停价格。 限量：单次最多提取5800条记录，可循环调取，总量不限制 积分：用户积2000积分可调取，单位分钟有流控，积分越高流量越大，请自行提高积分，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码 |
| trade_date | str | N | 交易日期 |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 交易日期 |
| ts_code | str | Y | TS股票代码 |
| pre_close | float | N | 昨日收盘价 |
| up_limit | float | Y | 涨停价 |
| down_limit | float | Y | 跌停价 |

接口示例
数据示例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：stk_limit 描述：获取全市场（包含A/B股和基金）每日涨跌停价格，包括涨停价格，跌停价格等，每个交易日8点40左右更新当日股票涨跌停价格。 限量：单次最多提取5800条记录，可循环调取，总量不限制 积分：用户积2000积分可调取，单位分钟有流控，积分越高流量越大，请自行提高积分，具体请参阅 积分获取办法


---

### [214] 每日停复牌信息  ·  股票数据 / 行情数据
(api: suspend_d | 输出字段: 4 | PIT字段: 否)

# (doc_id=214)  https://tushare.pro/document/2?doc_id=214

## 每日停复牌信息
接口：suspend_d 更新时间：不定期 描述：按日期方式获取股票每日停复牌信息
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码(可输入多值) |
| trade_date | str | N | 交易日日期 |
| start_date | str | N | 停复牌查询开始日期 |
| end_date | str | N | 停复牌查询结束日期 |
| suspend_type | str | N | 停复牌类型：S-停牌,R-复牌 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS代码 |
| trade_date | str | Y | 停复牌日期 |
| suspend_timing | str | Y | 日内停牌时间段 |
| suspend_type | str | Y | 停复牌类型：S-停牌，R-复牌 |

接口用法
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：suspend_d 更新时间：不定期 描述：按日期方式获取股票每日停复牌信息


---

### [48] 沪深股通十大成交股  ·  股票数据 / 行情数据
(api: hsgt_top10 | 输出字段: 11 | PIT字段: 否)

# (doc_id=48)  https://tushare.pro/document/2?doc_id=48

## 沪深股通十大成交股
接口：hsgt_top10 描述：获取沪股通、深股通每日前十大成交详细数据，每天18~20点之间完成当日更新
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码（二选一） |
| trade_date | str | N | 交易日期（二选一） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |
| market_type | str | N | 市场类型（1：沪市 3：深市） |

输出参数
| 名称 | 类型 | 描述 |
| --- | --- | --- |
| trade_date | str | 交易日期 |
| ts_code | str | 股票代码 |
| name | str | 股票名称 |
| close | float | 收盘价 |
| change | float | 涨跌额 |
| rank | int | 资金排名 |
| market_type | str | 市场类型（1：沪市 3：深市） |
| amount | float | 成交金额（元） |
| net_amount | float | 净成交金额（元） |
| buy | float | 买入金额（元） |
| sell | float | 卖出金额（元） |

接口用法
或者
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：hsgt_top10 描述：获取沪股通、深股通每日前十大成交详细数据，每天18~20点之间完成当日更新


---

### [49] 港股通十大成交股  ·  股票数据 / 行情数据
(api: ggt_top10 | 输出字段: 17 | PIT字段: 否)

# (doc_id=49)  https://tushare.pro/document/2?doc_id=49

## 港股通十大成交股
接口：ggt_top10 描述：获取港股通每日成交数据，其中包括沪市、深市详细数据，每天18~20点之间完成当日更新
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码（二选一） |
| trade_date | str | N | 交易日期（二选一） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |
| market_type | str | N | 市场类型 2：港股通（沪） 4：港股通（深） |

输出参数
| 名称 | 类型 | 描述 |
| --- | --- | --- |
| trade_date | str | 交易日期 |
| ts_code | str | 股票代码 |
| name | str | 股票名称 |
| close | float | 收盘价 |
| p_change | float | 涨跌幅 |
| rank | int | 资金排名 |
| market_type | str | 市场类型 2：港股通（沪） 4：港股通（深） |
| amount | float | 累计成交金额（元） |
| net_amount | float | 净买入金额（元） |
| sh_amount | float | 沪市成交金额（元） |
| sh_net_amount | float | 沪市净买入金额（元） |
| sh_buy | float | 沪市买入金额（元） |
| sh_sell | float | 沪市卖出金额 |
| sz_amount | float | 深市成交金额（元） |
| sz_net_amount | float | 深市净买入金额（元） |
| sz_buy | float | 深市买入金额（元） |
| sz_sell | float | 深市卖出金额（元） |

接口用法
或者
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：ggt_top10 描述：获取港股通每日成交数据，其中包括沪市、深市详细数据，每天18~20点之间完成当日更新


---

### [196] 港股通每日成交统计  ·  股票数据 / 行情数据
(api: ggt_daily | 输出字段: 5 | PIT字段: 否)

# (doc_id=196)  https://tushare.pro/document/2?doc_id=196

## 港股通每日成交统计
接口：ggt_daily 描述：获取港股通每日成交信息，数据从2014年开始 限量：单次最大1000，总量数据不限制 积分：用户积2000积分可调取，5000积分以上频次相对较高，请自行提高积分，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | N | 交易日期 （格式YYYYMMDD，下同。支持单日和多日输入） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 交易日期 |
| buy_amount | float | Y | 买入成交金额（亿元） |
| buy_volume | float | Y | 买入成交笔数（万笔） |
| sell_amount | float | Y | 卖出成交金额（亿元） |
| sell_volume | float | Y | 卖出成交笔数（万笔） |

接口示例
数据示例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：ggt_daily 描述：获取港股通每日成交信息，数据从2014年开始 限量：单次最大1000，总量数据不限制 积分：用户积2000积分可调取，5000积分以上频次相对较高，请自行提高积分，具体请参阅 积分获取办法


---

### [255] 备用行情  ·  股票数据 / 行情数据
(api: bak_daily | 输出字段: 31 | PIT字段: 否)

# (doc_id=255)  https://tushare.pro/document/2?doc_id=255

## 备用行情
接口：bak_daily 描述：获取备用行情，包括特定的行情指标(数据从2017年中左右开始，早期有几天数据缺失，近期正常) 限量：单次最大7000行数据，可以根据日期参数循环获取，正式权限需要5000积分。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码 |
| trade_date | str | N | 交易日期 |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |
| offset | str | N | 开始行数 |
| limit | str | N | 最大行数 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| trade_date | str | Y | 交易日期 |
| name | str | Y | 股票名称 |
| pct_change | float | Y | 涨跌幅 |
| close | float | Y | 收盘价 |
| change | float | Y | 涨跌额 |
| open | float | Y | 开盘价 |
| high | float | Y | 最高价 |
| low | float | Y | 最低价 |
| pre_close | float | Y | 昨收价 |
| vol_ratio | float | Y | 量比 |
| turn_over | float | Y | 换手率 |
| swing | float | Y | 振幅 |
| vol | float | Y | 成交量 |
| amount | float | Y | 成交额 |
| selling | float | Y | 内盘（主动卖，手） |
| buying | float | Y | 外盘（主动买， 手） |
| total_share | float | Y | 总股本(亿) |
| float_share | float | Y | 流通股本(亿) |
| pe | float | Y | 市盈(动) |
| industry | str | Y | 所属行业 |
| area | str | Y | 所属地域 |
| float_mv | float | Y | 流通市值 |
| total_mv | float | Y | 总市值 |
| avg_price | float | Y | 平均价 |
| strength | float | Y | 强弱度(%) |
| activity | float | Y | 活跃度(%) |
| avg_turnover | float | Y | 笔换手 |
| attack | float | Y | 攻击波(%) |
| interval_3 | float | Y | 近3月涨幅 |
| interval_6 | float | Y | 近6月涨幅 |

接口示例
数据样例


---

### [16] 财务数据  ·  股票数据
(api: — | 输出字段: 0 | PIT字段: 否)

# (doc_id=16)  https://tushare.pro/document/2?doc_id=16

## 财务数据
Pro版的财务数据跟旧版有着明显的差异，Pro提供的是完整的财务指标和全部历史数据，同时也提供质量比较高的业绩预告和业绩快报数据。我们将继续完善和充实财务指标，为大家提供更全面的反映上市公司基本面情况的数据，希望大家愉快的使用。
目前提供的主要接口有：
利润表
资产负债表
现金流量表
业绩预告
业绩快报

## [PIT / 更新口径 — 自动标记]
- (正文) Pro版的财务数据跟旧版有着明显的差异，Pro提供的是完整的财务指标和全部历史数据，同时也提供质量比较高的业绩预告和业绩快报数据。我们将继续完善和充实财务指标，为大家提供更全面的反映上市公司基本面情况的数据，希望大家愉快的使用。


---

### [33] 利润表  ·  股票数据 / 财务数据
(api: income | 输出字段: 94 | PIT字段: 是)

# (doc_id=33)  https://tushare.pro/document/2?doc_id=33

## 利润表
接口：income，可以通过 数据工具 调试和查看数据。 描述：获取上市公司财务利润表数据 积分：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法 提示：当前接口只能按单只股票获取其历史数据，如果需要获取某一季度全部上市公司数据，请使用income_vip接口（参数一致），需积攒5000积分。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| ann_date | str | N | 公告日期（YYYYMMDD格式，下同） |
| f_ann_date | str | N | 实际公告日期 |
| start_date | str | N | 公告日开始日期 |
| end_date | str | N | 公告日结束日期 |
| period | str | N | 报告期(每个季度最后一天的日期，比如20171231表示年报，20170630半年报，20170930三季报) |
| report_type | str | N | 报告类型，参考文档最下方说明 |
| comp_type | str | N | 公司类型（1一般工商业2银行3保险4证券） |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS代码 |
| ann_date | str | Y | 公告日期 |
| f_ann_date | str | Y | 实际公告日期 |
| end_date | str | Y | 报告期 |
| report_type | str | Y | 报告类型 见底部表 |
| comp_type | str | Y | 公司类型(1一般工商业2银行3保险4证券) |
| end_type | str | Y | 报告期类型 |
| basic_eps | float | Y | 基本每股收益 |
| diluted_eps | float | Y | 稀释每股收益 |
| total_revenue | float | Y | 营业总收入 |
| revenue | float | Y | 营业收入 |
| int_income | float | Y | 利息收入 |
| prem_earned | float | Y | 已赚保费 |
| comm_income | float | Y | 手续费及佣金收入 |
| n_commis_income | float | Y | 手续费及佣金净收入 |
| n_oth_income | float | Y | 其他经营净收益 |
| n_oth_b_income | float | Y | 加:其他业务净收益 |
| prem_income | float | Y | 保险业务收入 |
| out_prem | float | Y | 减:分出保费 |
| une_prem_reser | float | Y | 提取未到期责任准备金 |
| reins_income | float | Y | 其中:分保费收入 |
| n_sec_tb_income | float | Y | 代理买卖证券业务净收入 |
| n_sec_uw_income | float | Y | 证券承销业务净收入 |
| n_asset_mg_income | float | Y | 受托客户资产管理业务净收入 |
| oth_b_income | float | Y | 其他业务收入 |
| fv_value_chg_gain | float | Y | 加:公允价值变动净收益 |
| invest_income | float | Y | 加:投资净收益 |
| ass_invest_income | float | Y | 其中:对联营企业和合营企业的投资收益 |
| forex_gain | float | Y | 加:汇兑净收益 |
| total_cogs | float | Y | 营业总成本 |
| oper_cost | float | Y | 减:营业成本 |
| int_exp | float | Y | 减:利息支出 |
| comm_exp | float | Y | 减:手续费及佣金支出 |
| biz_tax_surchg | float | Y | 减:营业税金及附加 |
| sell_exp | float | Y | 减:销售费用 |
| admin_exp | float | Y | 减:管理费用 |
| fin_exp | float | Y | 减:财务费用 |
| assets_impair_loss | float | Y | 减:资产减值损失 |
| prem_refund | float | Y | 退保金 |
| compens_payout | float | Y | 赔付总支出 |
| reser_insur_liab | float | Y | 提取保险责任准备金 |
| div_payt | float | Y | 保户红利支出 |
| reins_exp | float | Y | 分保费用 |
| oper_exp | float | Y | 营业支出 |
| compens_payout_refu | float | Y | 减:摊回赔付支出 |
| insur_reser_refu | float | Y | 减:摊回保险责任准备金 |
| reins_cost_refund | float | Y | 减:摊回分保费用 |
| other_bus_cost | float | Y | 其他业务成本 |
| operate_profit | float | Y | 营业利润 |
| non_oper_income | float | Y | 加:营业外收入 |
| non_oper_exp | float | Y | 减:营业外支出 |
| nca_disploss | float | Y | 其中:减:非流动资产处置净损失 |
| total_profit | float | Y | 利润总额 |
| income_tax | float | Y | 所得税费用 |
| n_income | float | Y | 净利润(含少数股东损益) |
| n_income_attr_p | float | Y | 净利润(不含少数股东损益) |
| minority_gain | float | Y | 少数股东损益 |
| oth_compr_income | float | Y | 其他综合收益 |
| t_compr_income | float | Y | 综合收益总额 |
| compr_inc_attr_p | float | Y | 归属于母公司(或股东)的综合收益总额 |
| compr_inc_attr_m_s | float | Y | 归属于少数股东的综合收益总额 |
| ebit | float | Y | 息税前利润 |
| ebitda | float | Y | 息税折旧摊销前利润 |
| insurance_exp | float | Y | 保险业务支出 |
| undist_profit | float | Y | 年初未分配利润 |
| distable_profit | float | Y | 可分配利润 |
| rd_exp | float | Y | 研发费用 |
| fin_exp_int_exp | float | Y | 财务费用:利息费用 |
| fin_exp_int_inc | float | Y | 财务费用:利息收入 |
| transfer_surplus_rese | float | Y | 盈余公积转入 |
| transfer_housing_imprest | float | Y | 住房周转金转入 |
| transfer_oth | float | Y | 其他转入 |
| adj_lossgain | float | Y | 调整以前年度损益 |
| withdra_legal_surplus | float | Y | 提取法定盈余公积 |
| withdra_legal_pubfund | float | Y | 提取法定公益金 |
| withdra_biz_devfund | float | Y | 提取企业发展基金 |
| withdra_rese_fund | float | Y | 提取储备基金 |
| withdra_oth_ersu | float | Y | 提取任意盈余公积金 |
| workers_welfare | float | Y | 职工奖金福利 |
| distr_profit_shrhder | float | Y | 可供股东分配的利润 |
| prfshare_payable_dvd | float | Y | 应付优先股股利 |
| comshare_payable_dvd | float | Y | 应付普通股股利 |
| capit_comstock_div | float | Y | 转作股本的普通股股利 |
| net_after_nr_lp_correct | float | N | 扣除非经常性损益后的净利润（更正前） |
| credit_impa_loss | float | N | 信用减值损失 |
| net_expo_hedging_benefits | float | N | 净敞口套期收益 |
| oth_impair_loss_assets | float | N | 其他资产减值损失 |
| total_opcost | float | N | 营业总成本（二） |
| amodcost_fin_assets | float | N | 以摊余成本计量的金融资产终止确认收益 |
| oth_income | float | N | 其他收益 |
| asset_disp_income | float | N | 资产处置收益 |
| continued_net_profit | float | N | 持续经营净利润 |
| end_net_profit | float | N | 终止经营净利润 |
| update_flag | str | Y | 更新标识 |

接口使用说明
获取某一季度全部股票数据
数据样例
主要报表类型说明
| 代码 | 类型 | 说明 |
| --- | --- | --- |
| 1 | 合并报表 | 上市公司最新报表（默认） |
| 2 | 单季合并 | 单一季度的合并报表 |
| 3 | 调整单季合并表 | 调整后的单季合并报表（如果有） |
| 4 | 调整合并报表 | 本年度公布上年同期的财务报表数据，报告期为上年度 |
| 5 | 调整前合并报表 | 数据发生变更，将原数据进行保留，即调整前的原数据 |
| 6 | 母公司报表 | 该公司母公司的财务报表数据 |
| 7 | 母公司单季表 | 母公司的单季度表 |
| 8 | 母公司调整单季表 | 母公司调整后的单季表 |
| 9 | 母公司调整表 | 该公司母公司的本年度公布上年同期的财务报表数据 |
| 10 | 母公司调整前报表 | 母公司调整之前的原始财务报表数据 |
| 11 | 母公司调整前合并报表 | 母公司调整之前合并报表原数据 |
| 12 | 母公司调整前报表 | 母公司报表发生变更前保留的原数据 |


## [PIT / 更新口径 — 自动标记]
- (正文) 接口：income，可以通过 数据工具 调试和查看数据。 描述：获取上市公司财务利润表数据 积分：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法 提示：当前接口只能按单只股票获取其历史数据，如果需要获取某一季度全部上市公司数据，请使用income_vip接口（参数一致），需积攒5000积分。
- (字段) `ann_date` — str N 公告日期（YYYYMMDD格式，下同）  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `f_ann_date` — str N 实际公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `start_date` — str N 公告日开始日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `end_date` — str N 公告日结束日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `ann_date` — str Y 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `f_ann_date` — str Y 实际公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `update_flag` — str Y 更新标识  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [36] 资产负债表  ·  股票数据 / 财务数据
(api: balancesheet | 输出字段: 158 | PIT字段: 是)

# (doc_id=36)  https://tushare.pro/document/2?doc_id=36

## 资产负债表
接口：balancesheet，可以通过 数据工具 调试和查看数据。 描述：获取上市公司资产负债表 积分：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法 提示：当前接口只能按单只股票获取其历史数据，如果需要获取某一季度全部上市公司数据，请使用balancesheet_vip接口（参数一致），需积攒5000积分。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| ann_date | str | N | 公告日期(YYYYMMDD格式，下同) |
| start_date | str | N | 公告日开始日期 |
| end_date | str | N | 公告日结束日期 |
| period | str | N | 报告期(每个季度最后一天的日期，比如20171231表示年报，20170630半年报，20170930三季报) |
| report_type | str | N | 报告类型：见下方详细说明 |
| comp_type | str | N | 公司类型：1一般工商业 2银行 3保险 4证券 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS股票代码 |
| ann_date | str | Y | 公告日期 |
| f_ann_date | str | Y | 实际公告日期 |
| end_date | str | Y | 报告期 |
| report_type | str | Y | 报表类型 |
| comp_type | str | Y | 公司类型(1一般工商业2银行3保险4证券) |
| end_type | str | Y | 报告期类型 |
| total_share | float | Y | 期末总股本 |
| cap_rese | float | Y | 资本公积金 |
| undistr_porfit | float | Y | 未分配利润 |
| surplus_rese | float | Y | 盈余公积金 |
| special_rese | float | Y | 专项储备 |
| money_cap | float | Y | 货币资金 |
| trad_asset | float | Y | 交易性金融资产 |
| notes_receiv | float | Y | 应收票据 |
| accounts_receiv | float | Y | 应收账款 |
| oth_receiv | float | Y | 其他应收款 |
| prepayment | float | Y | 预付款项 |
| div_receiv | float | Y | 应收股利 |
| int_receiv | float | Y | 应收利息 |
| inventories | float | Y | 存货 |
| amor_exp | float | Y | 待摊费用 |
| nca_within_1y | float | Y | 一年内到期的非流动资产 |
| sett_rsrv | float | Y | 结算备付金 |
| loanto_oth_bank_fi | float | Y | 拆出资金 |
| premium_receiv | float | Y | 应收保费 |
| reinsur_receiv | float | Y | 应收分保账款 |
| reinsur_res_receiv | float | Y | 应收分保合同准备金 |
| pur_resale_fa | float | Y | 买入返售金融资产 |
| oth_cur_assets | float | Y | 其他流动资产 |
| total_cur_assets | float | Y | 流动资产合计 |
| fa_avail_for_sale | float | Y | 可供出售金融资产 |
| htm_invest | float | Y | 持有至到期投资 |
| lt_eqt_invest | float | Y | 长期股权投资 |
| invest_real_estate | float | Y | 投资性房地产 |
| time_deposits | float | Y | 定期存款 |
| oth_assets | float | Y | 其他资产 |
| lt_rec | float | Y | 长期应收款 |
| fix_assets | float | Y | 固定资产 |
| cip | float | Y | 在建工程 |
| const_materials | float | Y | 工程物资 |
| fixed_assets_disp | float | Y | 固定资产清理 |
| produc_bio_assets | float | Y | 生产性生物资产 |
| oil_and_gas_assets | float | Y | 油气资产 |
| intan_assets | float | Y | 无形资产 |
| r_and_d | float | Y | 研发支出 |
| goodwill | float | Y | 商誉 |
| lt_amor_exp | float | Y | 长期待摊费用 |
| defer_tax_assets | float | Y | 递延所得税资产 |
| decr_in_disbur | float | Y | 发放贷款及垫款 |
| oth_nca | float | Y | 其他非流动资产 |
| total_nca | float | Y | 非流动资产合计 |
| cash_reser_cb | float | Y | 现金及存放中央银行款项 |
| depos_in_oth_bfi | float | Y | 存放同业和其它金融机构款项 |
| prec_metals | float | Y | 贵金属 |
| deriv_assets | float | Y | 衍生金融资产 |
| rr_reins_une_prem | float | Y | 应收分保未到期责任准备金 |
| rr_reins_outstd_cla | float | Y | 应收分保未决赔款准备金 |
| rr_reins_lins_liab | float | Y | 应收分保寿险责任准备金 |
| rr_reins_lthins_liab | float | Y | 应收分保长期健康险责任准备金 |
| refund_depos | float | Y | 存出保证金 |
| ph_pledge_loans | float | Y | 保户质押贷款 |
| refund_cap_depos | float | Y | 存出资本保证金 |
| indep_acct_assets | float | Y | 独立账户资产 |
| client_depos | float | Y | 其中：客户资金存款 |
| client_prov | float | Y | 其中：客户备付金 |
| transac_seat_fee | float | Y | 其中:交易席位费 |
| invest_as_receiv | float | Y | 应收款项类投资 |
| total_assets | float | Y | 资产总计 |
| lt_borr | float | Y | 长期借款 |
| st_borr | float | Y | 短期借款 |
| cb_borr | float | Y | 向中央银行借款 |
| depos_ib_deposits | float | Y | 吸收存款及同业存放 |
| loan_oth_bank | float | Y | 拆入资金 |
| trading_fl | float | Y | 交易性金融负债 |
| notes_payable | float | Y | 应付票据 |
| acct_payable | float | Y | 应付账款 |
| adv_receipts | float | Y | 预收款项 |
| sold_for_repur_fa | float | Y | 卖出回购金融资产款 |
| comm_payable | float | Y | 应付手续费及佣金 |
| payroll_payable | float | Y | 应付职工薪酬 |
| taxes_payable | float | Y | 应交税费 |
| int_payable | float | Y | 应付利息 |
| div_payable | float | Y | 应付股利 |
| oth_payable | float | Y | 其他应付款 |
| acc_exp | float | Y | 预提费用 |
| deferred_inc | float | Y | 递延收益 |
| st_bonds_payable | float | Y | 应付短期债券 |
| payable_to_reinsurer | float | Y | 应付分保账款 |
| rsrv_insur_cont | float | Y | 保险合同准备金 |
| acting_trading_sec | float | Y | 代理买卖证券款 |
| acting_uw_sec | float | Y | 代理承销证券款 |
| non_cur_liab_due_1y | float | Y | 一年内到期的非流动负债 |
| oth_cur_liab | float | Y | 其他流动负债 |
| total_cur_liab | float | Y | 流动负债合计 |
| bond_payable | float | Y | 应付债券 |
| lt_payable | float | Y | 长期应付款 |
| specific_payables | float | Y | 专项应付款 |
| estimated_liab | float | Y | 预计负债 |
| defer_tax_liab | float | Y | 递延所得税负债 |
| defer_inc_non_cur_liab | float | Y | 递延收益-非流动负债 |
| oth_ncl | float | Y | 其他非流动负债 |
| total_ncl | float | Y | 非流动负债合计 |
| depos_oth_bfi | float | Y | 同业和其它金融机构存放款项 |
| deriv_liab | float | Y | 衍生金融负债 |
| depos | float | Y | 吸收存款 |
| agency_bus_liab | float | Y | 代理业务负债 |
| oth_liab | float | Y | 其他负债 |
| prem_receiv_adva | float | Y | 预收保费 |
| depos_received | float | Y | 存入保证金 |
| ph_invest | float | Y | 保户储金及投资款 |
| reser_une_prem | float | Y | 未到期责任准备金 |
| reser_outstd_claims | float | Y | 未决赔款准备金 |
| reser_lins_liab | float | Y | 寿险责任准备金 |
| reser_lthins_liab | float | Y | 长期健康险责任准备金 |
| indept_acc_liab | float | Y | 独立账户负债 |
| pledge_borr | float | Y | 其中:质押借款 |
| indem_payable | float | Y | 应付赔付款 |
| policy_div_payable | float | Y | 应付保单红利 |
| total_liab | float | Y | 负债合计 |
| treasury_share | float | Y | 减:库存股 |
| ordin_risk_reser | float | Y | 一般风险准备 |
| forex_differ | float | Y | 外币报表折算差额 |
| invest_loss_unconf | float | Y | 未确认的投资损失 |
| minority_int | float | Y | 少数股东权益 |
| total_hldr_eqy_exc_min_int | float | Y | 股东权益合计(不含少数股东权益) |
| total_hldr_eqy_inc_min_int | float | Y | 股东权益合计(含少数股东权益) |
| total_liab_hldr_eqy | float | Y | 负债及股东权益总计 |
| lt_payroll_payable | float | Y | 长期应付职工薪酬 |
| oth_comp_income | float | Y | 其他综合收益 |
| oth_eqt_tools | float | Y | 其他权益工具 |
| oth_eqt_tools_p_shr | float | Y | 其他权益工具(优先股) |
| lending_funds | float | Y | 融出资金 |
| acc_receivable | float | Y | 应收款项 |
| st_fin_payable | float | Y | 应付短期融资款 |
| payables | float | Y | 应付款项 |
| hfs_assets | float | Y | 持有待售的资产 |
| hfs_sales | float | Y | 持有待售的负债 |
| cost_fin_assets | float | Y | 以摊余成本计量的金融资产 |
| fair_value_fin_assets | float | Y | 以公允价值计量且其变动计入其他综合收益的金融资产 |
| cip_total | float | Y | 在建工程(合计)(元) |
| oth_pay_total | float | Y | 其他应付款(合计)(元) |
| long_pay_total | float | Y | 长期应付款(合计)(元) |
| debt_invest | float | Y | 债权投资(元) |
| oth_debt_invest | float | Y | 其他债权投资(元) |
| oth_eq_invest | float | N | 其他权益工具投资(元) |
| oth_illiq_fin_assets | float | N | 其他非流动金融资产(元) |
| oth_eq_ppbond | float | N | 其他权益工具:永续债(元) |
| receiv_financing | float | N | 应收款项融资 |
| use_right_assets | float | N | 使用权资产 |
| lease_liab | float | N | 租赁负债 |
| contract_assets | float | Y | 合同资产 |
| contract_liab | float | Y | 合同负债 |
| accounts_receiv_bill | float | Y | 应收票据及应收账款 |
| accounts_pay | float | Y | 应付票据及应付账款 |
| oth_rcv_total | float | Y | 其他应收款(合计)（元） |
| fix_assets_total | float | Y | 固定资产(合计)(元) |
| update_flag | str | Y | 更新标识 |

接口使用说明
获取某一季度全部股票数据
数据样例
主要报表类型说明
代码 | 类型 | 说明 ---- | ----- | ---- | 1 | 合并报表 | 上市公司最新报表（默认） 2 | 单季合并 | 单一季度的合并报表 3 | 调整单季合并表 | 调整后的单季合并报表（如果有） 4 | 调整合并报表 | 本年度公布上年同期的财务报表数据，报告期为上年度 5 | 调整前合并报表 | 数据发生变更，将原数据进行保留，即调整前的原数据 6 | 母公司报表 | 该公司母公司的财务报表数据 7 | 母公司单季表 | 母公司的单季度表 8 | 母公司调整单季表 | 母公司调整后的单季表 9 | 母公司调整表 | 该公司母公司的本年度公布上年同期的财务报表数据 10 | 母公司调整前报表 | 母公司调整之前的原始财务报表数据 11 | 母公司调整前合并报表 | 母公司调整之前合并报表原数据 12 | 母公司调整前报表 | 母公司报表发生变更前保留的原数据

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：balancesheet，可以通过 数据工具 调试和查看数据。 描述：获取上市公司资产负债表 积分：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法 提示：当前接口只能按单只股票获取其历史数据，如果需要获取某一季度全部上市公司数据，请使用balancesheet_vip接口（参数一致），需积攒5000积分。
- (字段) `ann_date` — str N 公告日期(YYYYMMDD格式，下同)  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `start_date` — str N 公告日开始日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `end_date` — str N 公告日结束日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `ann_date` — str Y 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `f_ann_date` — str Y 实际公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `update_flag` — str Y 更新标识  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [44] 现金流量表  ·  股票数据 / 财务数据
(api: cashflow | 输出字段: 97 | PIT字段: 是)

# (doc_id=44)  https://tushare.pro/document/2?doc_id=44

## 现金流量表
接口：cashflow，可以通过 数据工具 调试和查看数据。 描述：获取上市公司现金流量表 积分：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法 提示：当前接口只能按单只股票获取其历史数据，如果需要获取某一季度全部上市公司数据，请使用cashflow_vip接口（参数一致），需积攒5000积分。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| ann_date | str | N | 公告日期（YYYYMMDD格式，下同） |
| f_ann_date | str | N | 实际公告日期 |
| start_date | str | N | 公告日开始日期 |
| end_date | str | N | 公告日结束日期 |
| period | str | N | 报告期(每个季度最后一天的日期，比如20171231表示年报，20170630半年报，20170930三季报) |
| report_type | str | N | 报告类型：见下方详细说明 |
| comp_type | str | N | 公司类型：1一般工商业 2银行 3保险 4证券 |
| is_calc | int | N | 是否计算报表 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS股票代码 |
| ann_date | str | Y | 公告日期 |
| f_ann_date | str | Y | 实际公告日期 |
| end_date | str | Y | 报告期 |
| comp_type | str | Y | 公司类型(1一般工商业2银行3保险4证券) |
| report_type | str | Y | 报表类型 |
| end_type | str | Y | 报告期类型 |
| net_profit | float | Y | 净利润 |
| finan_exp | float | Y | 财务费用 |
| c_fr_sale_sg | float | Y | 销售商品、提供劳务收到的现金 |
| recp_tax_rends | float | Y | 收到的税费返还 |
| n_depos_incr_fi | float | Y | 客户存款和同业存放款项净增加额 |
| n_incr_loans_cb | float | Y | 向中央银行借款净增加额 |
| n_inc_borr_oth_fi | float | Y | 向其他金融机构拆入资金净增加额 |
| prem_fr_orig_contr | float | Y | 收到原保险合同保费取得的现金 |
| n_incr_insured_dep | float | Y | 保户储金净增加额 |
| n_reinsur_prem | float | Y | 收到再保业务现金净额 |
| n_incr_disp_tfa | float | Y | 处置交易性金融资产净增加额 |
| ifc_cash_incr | float | Y | 收取利息和手续费净增加额 |
| n_incr_disp_faas | float | Y | 处置可供出售金融资产净增加额 |
| n_incr_loans_oth_bank | float | Y | 拆入资金净增加额 |
| n_cap_incr_repur | float | Y | 回购业务资金净增加额 |
| c_fr_oth_operate_a | float | Y | 收到其他与经营活动有关的现金 |
| c_inf_fr_operate_a | float | Y | 经营活动现金流入小计 |
| c_paid_goods_s | float | Y | 购买商品、接受劳务支付的现金 |
| c_paid_to_for_empl | float | Y | 支付给职工以及为职工支付的现金 |
| c_paid_for_taxes | float | Y | 支付的各项税费 |
| n_incr_clt_loan_adv | float | Y | 客户贷款及垫款净增加额 |
| n_incr_dep_cbob | float | Y | 存放央行和同业款项净增加额 |
| c_pay_claims_orig_inco | float | Y | 支付原保险合同赔付款项的现金 |
| pay_handling_chrg | float | Y | 支付手续费的现金 |
| pay_comm_insur_plcy | float | Y | 支付保单红利的现金 |
| oth_cash_pay_oper_act | float | Y | 支付其他与经营活动有关的现金 |
| st_cash_out_act | float | Y | 经营活动现金流出小计 |
| n_cashflow_act | float | Y | 经营活动产生的现金流量净额 |
| oth_recp_ral_inv_act | float | Y | 收到其他与投资活动有关的现金 |
| c_disp_withdrwl_invest | float | Y | 收回投资收到的现金 |
| c_recp_return_invest | float | Y | 取得投资收益收到的现金 |
| n_recp_disp_fiolta | float | Y | 处置固定资产、无形资产和其他长期资产收回的现金净额 |
| n_recp_disp_sobu | float | Y | 处置子公司及其他营业单位收到的现金净额 |
| stot_inflows_inv_act | float | Y | 投资活动现金流入小计 |
| c_pay_acq_const_fiolta | float | Y | 购建固定资产、无形资产和其他长期资产支付的现金 |
| c_paid_invest | float | Y | 投资支付的现金 |
| n_disp_subs_oth_biz | float | Y | 取得子公司及其他营业单位支付的现金净额 |
| oth_pay_ral_inv_act | float | Y | 支付其他与投资活动有关的现金 |
| n_incr_pledge_loan | float | Y | 质押贷款净增加额 |
| stot_out_inv_act | float | Y | 投资活动现金流出小计 |
| n_cashflow_inv_act | float | Y | 投资活动产生的现金流量净额 |
| c_recp_borrow | float | Y | 取得借款收到的现金 |
| proc_issue_bonds | float | Y | 发行债券收到的现金 |
| oth_cash_recp_ral_fnc_act | float | Y | 收到其他与筹资活动有关的现金 |
| stot_cash_in_fnc_act | float | Y | 筹资活动现金流入小计 |
| free_cashflow | float | Y | 企业自由现金流量 |
| c_prepay_amt_borr | float | Y | 偿还债务支付的现金 |
| c_pay_dist_dpcp_int_exp | float | Y | 分配股利、利润或偿付利息支付的现金 |
| incl_dvd_profit_paid_sc_ms | float | Y | 其中:子公司支付给少数股东的股利、利润 |
| oth_cashpay_ral_fnc_act | float | Y | 支付其他与筹资活动有关的现金 |
| stot_cashout_fnc_act | float | Y | 筹资活动现金流出小计 |
| n_cash_flows_fnc_act | float | Y | 筹资活动产生的现金流量净额 |
| eff_fx_flu_cash | float | Y | 汇率变动对现金的影响 |
| n_incr_cash_cash_equ | float | Y | 现金及现金等价物净增加额 |
| c_cash_equ_beg_period | float | Y | 期初现金及现金等价物余额 |
| c_cash_equ_end_period | float | Y | 期末现金及现金等价物余额 |
| c_recp_cap_contrib | float | Y | 吸收投资收到的现金 |
| incl_cash_rec_saims | float | Y | 其中:子公司吸收少数股东投资收到的现金 |
| uncon_invest_loss | float | Y | 未确认投资损失 |
| prov_depr_assets | float | Y | 加:资产减值准备 |
| depr_fa_coga_dpba | float | Y | 固定资产折旧、油气资产折耗、生产性生物资产折旧 |
| amort_intang_assets | float | Y | 无形资产摊销 |
| lt_amort_deferred_exp | float | Y | 长期待摊费用摊销 |
| decr_deferred_exp | float | Y | 待摊费用减少 |
| incr_acc_exp | float | Y | 预提费用增加 |
| loss_disp_fiolta | float | Y | 处置固定、无形资产和其他长期资产的损失 |
| loss_scr_fa | float | Y | 固定资产报废损失 |
| loss_fv_chg | float | Y | 公允价值变动损失 |
| invest_loss | float | Y | 投资损失 |
| decr_def_inc_tax_assets | float | Y | 递延所得税资产减少 |
| incr_def_inc_tax_liab | float | Y | 递延所得税负债增加 |
| decr_inventories | float | Y | 存货的减少 |
| decr_oper_payable | float | Y | 经营性应收项目的减少 |
| incr_oper_payable | float | Y | 经营性应付项目的增加 |
| others | float | Y | 其他 |
| im_net_cashflow_oper_act | float | Y | 经营活动产生的现金流量净额(间接法) |
| conv_debt_into_cap | float | Y | 债务转为资本 |
| conv_copbonds_due_within_1y | float | Y | 一年内到期的可转换公司债券 |
| fa_fnc_leases | float | Y | 融资租入固定资产 |
| im_n_incr_cash_equ | float | Y | 现金及现金等价物净增加额(间接法) |
| net_dism_capital_add | float | Y | 拆出资金净增加额 |
| net_cash_rece_sec | float | Y | 代理买卖证券收到的现金净额(元) |
| credit_impa_loss | float | Y | 信用减值损失 |
| use_right_asset_dep | float | Y | 使用权资产折旧 |
| oth_loss_asset | float | Y | 其他资产减值损失 |
| end_bal_cash | float | Y | 现金的期末余额 |
| beg_bal_cash | float | Y | 减:现金的期初余额 |
| end_bal_cash_equ | float | Y | 加:现金等价物的期末余额 |
| beg_bal_cash_equ | float | Y | 减:现金等价物的期初余额 |
| update_flag | str | Y | 更新标志(1最新） |

输出参数
接口使用说明
获取某一季度全部股票数据
数据样例
主要报表类型说明
代码 | 类型 | 说明 ---- | ----- | ---- | 1 | 合并报表 | 上市公司最新报表（默认） 2 | 单季合并 | 单一季度的合并报表 3 | 调整单季合并表 | 调整后的单季合并报表（如果有） 4 | 调整合并报表 | 本年度公布上年同期的财务报表数据，报告期为上年度 5 | 调整前合并报表 | 数据发生变更，将原数据进行保留，即调整前的原数据 6 | 母公司报表 | 该公司母公司的财务报表数据 7 | 母公司单季表 | 母公司的单季度表 8 | 母公司调整单季表 | 母公司调整后的单季表 9 | 母公司调整表 | 该公司母公司的本年度公布上年同期的财务报表数据 10 | 母公司调整前报表 | 母公司调整之前的原始财务报表数据 11 | 目公司调整前合并报表 | 母公司调整之前合并报表原数据 12 | 母公司调整前报表 | 母公司报表发生变更前保留的原数据

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：cashflow，可以通过 数据工具 调试和查看数据。 描述：获取上市公司现金流量表 积分：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法 提示：当前接口只能按单只股票获取其历史数据，如果需要获取某一季度全部上市公司数据，请使用cashflow_vip接口（参数一致），需积攒5000积分。
- (字段) `ann_date` — str N 公告日期（YYYYMMDD格式，下同）  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `f_ann_date` — str N 实际公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `start_date` — str N 公告日开始日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `end_date` — str N 公告日结束日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `ann_date` — str Y 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `f_ann_date` — str Y 实际公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `update_flag` — str Y 更新标志(1最新）  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [45] 业绩预告  ·  股票数据 / 财务数据
(api: forecast | 输出字段: 12 | PIT字段: 是)

# (doc_id=45)  https://tushare.pro/document/2?doc_id=45

## 业绩预告
接口：forecast，可以通过 数据工具 调试和查看数据。 描述：获取业绩预告数据 权限：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法 提示：当前接口只能按单只股票获取其历史数据，如果需要获取某一季度全部上市公司数据，请使用forecast_vip接口（参数一致），需积攒5000积分。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码(二选一) |
| ann_date | str | N | 公告日期 (二选一) |
| start_date | str | N | 公告开始日期 |
| end_date | str | N | 公告结束日期 |
| period | str | N | 报告期(每个季度最后一天的日期，比如20171231表示年报，20170630半年报，20170930三季报) |
| type | str | N | 预告类型(预增/预减/扭亏/首亏/续亏/续盈/略增/略减) |

输出参数
| 名称 | 类型 | 描述 |
| --- | --- | --- |
| ts_code | str | TS股票代码 |
| ann_date | str | 公告日期 |
| end_date | str | 报告期 |
| type | str | 业绩预告类型(预增/预减/扭亏/首亏/续亏/续盈/略增/略减) |
| p_change_min | float | 预告净利润变动幅度下限（%） |
| p_change_max | float | 预告净利润变动幅度上限（%） |
| net_profit_min | float | 预告净利润下限（万元） |
| net_profit_max | float | 预告净利润上限（万元） |
| last_parent_net | float | 上年同期归属母公司净利润 |
| first_ann_date | str | 首次公告日 |
| summary | str | 业绩预告摘要 |
| change_reason | str | 业绩变动原因 |

接口用法
获取某一季度全部股票数据
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：forecast，可以通过 数据工具 调试和查看数据。 描述：获取业绩预告数据 权限：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法 提示：当前接口只能按单只股票获取其历史数据，如果需要获取某一季度全部上市公司数据，请使用forecast_vip接口（参数一致），需积攒5000积分。
- (字段) `ann_date` — str N 公告日期 (二选一)  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `ann_date` — str 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `first_ann_date` — str 首次公告日  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [46] 业绩快报  ·  股票数据 / 财务数据
(api: express | 输出字段: 32 | PIT字段: 是)

# (doc_id=46)  https://tushare.pro/document/2?doc_id=46

## 业绩快报
接口：express 描述：获取上市公司业绩快报 权限：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法 提示：当前接口只能按单只股票获取其历史数据，如果需要获取某一季度全部上市公司数据，请使用express_vip接口（参数一致），需积攒5000积分。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| ann_date | str | N | 公告日期 |
| start_date | str | N | 公告开始日期 |
| end_date | str | N | 公告结束日期 |
| period | str | N | 报告期(每个季度最后一天的日期,比如20171231表示年报，20170630半年报，20170930三季报) |

输出参数
| 名称 | 类型 | 描述 |
| --- | --- | --- |
| ts_code | str | TS股票代码 |
| ann_date | str | 公告日期 |
| end_date | str | 报告期 |
| revenue | float | 营业收入(元) |
| operate_profit | float | 营业利润(元) |
| total_profit | float | 利润总额(元) |
| n_income | float | 净利润(元) |
| total_assets | float | 总资产(元) |
| total_hldr_eqy_exc_min_int | float | 股东权益合计(不含少数股东权益)(元) |
| diluted_eps | float | 每股收益(摊薄)(元) |
| diluted_roe | float | 净资产收益率(摊薄)(%) |
| yoy_net_profit | float | 去年同期修正后净利润 |
| bps | float | 每股净资产 |
| yoy_sales | float | 同比增长率:营业收入 |
| yoy_op | float | 同比增长率:营业利润 |
| yoy_tp | float | 同比增长率:利润总额 |
| yoy_dedu_np | float | 同比增长率:归属母公司股东的净利润 |
| yoy_eps | float | 同比增长率:基本每股收益 |
| yoy_roe | float | 同比增减:加权平均净资产收益率 |
| growth_assets | float | 比年初增长率:总资产 |
| yoy_equity | float | 比年初增长率:归属母公司的股东权益 |
| growth_bps | float | 比年初增长率:归属于母公司股东的每股净资产 |
| or_last_year | float | 去年同期营业收入 |
| op_last_year | float | 去年同期营业利润 |
| tp_last_year | float | 去年同期利润总额 |
| np_last_year | float | 去年同期净利润 |
| eps_last_year | float | 去年同期每股收益 |
| open_net_assets | float | 期初净资产 |
| open_bps | float | 期初每股净资产 |
| perf_summary | str | 业绩简要说明 |
| is_audit | int | 是否审计： 1是 0否 |
| remark | str | 备注 |

接口用法
获取某一季度全部股票数据
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：express 描述：获取上市公司业绩快报 权限：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法 提示：当前接口只能按单只股票获取其历史数据，如果需要获取某一季度全部上市公司数据，请使用express_vip接口（参数一致），需积攒5000积分。
- (字段) `ann_date` — str N 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `ann_date` — str 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [103] 分红送股数据  ·  股票数据 / 财务数据
(api: dividend | 输出字段: 16 | PIT字段: 是)

# (doc_id=103)  https://tushare.pro/document/2?doc_id=103

## 分红送股
接口：dividend 描述：分红送股数据 权限：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | TS代码 |
| ann_date | str | N | 公告日 |
| record_date | str | N | 股权登记日期 |
| ex_date | str | N | 除权除息日 |
| imp_ann_date | str | N | 实施公告日 |

以上参数至少有一个不能为空
输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS代码 |
| end_date | str | Y | 分红年度 |
| ann_date | str | Y | 预案公告日 |
| div_proc | str | Y | 实施进度 |
| stk_div | float | Y | 每股送转 |
| stk_bo_rate | float | Y | 每股送股比例 |
| stk_co_rate | float | Y | 每股转增比例 |
| cash_div | float | Y | 每股分红（税后） |
| cash_div_tax | float | Y | 每股分红（税前） |
| record_date | str | Y | 股权登记日 |
| ex_date | str | Y | 除权除息日 |
| pay_date | str | Y | 派息日 |
| div_listdate | str | Y | 红股上市日 |
| imp_ann_date | str | Y | 实施公告日 |
| base_date | str | N | 基准日 |
| base_share | float | N | 基准股本（万） |

接口示例
数据样例

## [PIT / 更新口径 — 自动标记]
- (字段) `ann_date` — str N 公告日  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `imp_ann_date` — str N 实施公告日  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `ann_date` — str Y 预案公告日  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `imp_ann_date` — str Y 实施公告日  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [79] 财务指标数据  ·  股票数据 / 财务数据
(api: fina_indicator | 输出字段: 167 | PIT字段: 是)

# (doc_id=79)  https://tushare.pro/document/2?doc_id=79

## 财务指标数据
接口：fina_indicator，可以通过 数据工具 调试和查看数据。 描述：获取上市公司财务指标数据，为避免服务器压力，现阶段每次请求最多返回100条记录，可通过设置日期多次请求获取更多数据。 权限：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法 提示：当前接口只能按单只股票获取其历史数据，如果需要获取某一季度全部上市公司数据，请使用fina_indicator_vip接口（参数一致），需积攒5000积分。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS股票代码,e.g. 600001.SH/000001.SZ |
| ann_date | str | N | 公告日期 |
| start_date | str | N | 报告期开始日期 |
| end_date | str | N | 报告期结束日期 |
| period | str | N | 报告期(每个季度最后一天的日期,比如20171231表示年报) |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS代码 |
| ann_date | str | Y | 公告日期 |
| end_date | str | Y | 报告期 |
| eps | float | Y | 基本每股收益 |
| dt_eps | float | Y | 稀释每股收益 |
| total_revenue_ps | float | Y | 每股营业总收入 |
| revenue_ps | float | Y | 每股营业收入 |
| capital_rese_ps | float | Y | 每股资本公积 |
| surplus_rese_ps | float | Y | 每股盈余公积 |
| undist_profit_ps | float | Y | 每股未分配利润 |
| extra_item | float | Y | 非经常性损益 |
| profit_dedt | float | Y | 扣除非经常性损益后的净利润（扣非净利润） |
| gross_margin | float | Y | 毛利 |
| current_ratio | float | Y | 流动比率 |
| quick_ratio | float | Y | 速动比率 |
| cash_ratio | float | Y | 保守速动比率 |
| invturn_days | float | N | 存货周转天数 |
| arturn_days | float | N | 应收账款周转天数 |
| inv_turn | float | N | 存货周转率 |
| ar_turn | float | Y | 应收账款周转率 |
| ca_turn | float | Y | 流动资产周转率 |
| fa_turn | float | Y | 固定资产周转率 |
| assets_turn | float | Y | 总资产周转率 |
| op_income | float | Y | 经营活动净收益 |
| valuechange_income | float | N | 价值变动净收益 |
| interst_income | float | N | 利息费用 |
| daa | float | N | 折旧与摊销 |
| ebit | float | Y | 息税前利润 |
| ebitda | float | Y | 息税折旧摊销前利润 |
| fcff | float | Y | 企业自由现金流量 |
| fcfe | float | Y | 股权自由现金流量 |
| current_exint | float | Y | 无息流动负债 |
| noncurrent_exint | float | Y | 无息非流动负债 |
| interestdebt | float | Y | 带息债务 |
| netdebt | float | Y | 净债务 |
| tangible_asset | float | Y | 有形资产 |
| working_capital | float | Y | 营运资金 |
| networking_capital | float | Y | 营运流动资本 |
| invest_capital | float | Y | 全部投入资本 |
| retained_earnings | float | Y | 留存收益 |
| diluted2_eps | float | Y | 期末摊薄每股收益 |
| bps | float | Y | 每股净资产 |
| ocfps | float | Y | 每股经营活动产生的现金流量净额 |
| retainedps | float | Y | 每股留存收益 |
| cfps | float | Y | 每股现金流量净额 |
| ebit_ps | float | Y | 每股息税前利润 |
| fcff_ps | float | Y | 每股企业自由现金流量 |
| fcfe_ps | float | Y | 每股股东自由现金流量 |
| netprofit_margin | float | Y | 销售净利率 |
| grossprofit_margin | float | Y | 销售毛利率 |
| cogs_of_sales | float | Y | 销售成本率 |
| expense_of_sales | float | Y | 销售期间费用率 |
| profit_to_gr | float | Y | 净利润/营业总收入 |
| saleexp_to_gr | float | Y | 销售费用/营业总收入 |
| adminexp_of_gr | float | Y | 管理费用/营业总收入 |
| finaexp_of_gr | float | Y | 财务费用/营业总收入 |
| impai_ttm | float | Y | 资产减值损失/营业总收入 |
| gc_of_gr | float | Y | 营业总成本/营业总收入 |
| op_of_gr | float | Y | 营业利润/营业总收入 |
| ebit_of_gr | float | Y | 息税前利润/营业总收入 |
| roe | float | Y | 净资产收益率 |
| roe_waa | float | Y | 加权平均净资产收益率 |
| roe_dt | float | Y | 净资产收益率(扣除非经常损益) |
| roa | float | Y | 总资产报酬率 |
| npta | float | Y | 总资产净利润 |
| roic | float | Y | 投入资本回报率 |
| roe_yearly | float | Y | 年化净资产收益率 |
| roa2_yearly | float | Y | 年化总资产报酬率 |
| roe_avg | float | N | 平均净资产收益率(增发条件) |
| opincome_of_ebt | float | N | 经营活动净收益/利润总额 |
| investincome_of_ebt | float | N | 价值变动净收益/利润总额 |
| n_op_profit_of_ebt | float | N | 营业外收支净额/利润总额 |
| tax_to_ebt | float | N | 所得税/利润总额 |
| dtprofit_to_profit | float | N | 扣除非经常损益后的净利润/净利润 |
| salescash_to_or | float | N | 销售商品提供劳务收到的现金/营业收入 |
| ocf_to_or | float | N | 经营活动产生的现金流量净额/营业收入 |
| ocf_to_opincome | float | N | 经营活动产生的现金流量净额/经营活动净收益 |
| capitalized_to_da | float | N | 资本支出/折旧和摊销 |
| debt_to_assets | float | Y | 资产负债率 |
| assets_to_eqt | float | Y | 权益乘数 |
| dp_assets_to_eqt | float | Y | 权益乘数(杜邦分析) |
| ca_to_assets | float | Y | 流动资产/总资产 |
| nca_to_assets | float | Y | 非流动资产/总资产 |
| tbassets_to_totalassets | float | Y | 有形资产/总资产 |
| int_to_talcap | float | Y | 带息债务/全部投入资本 |
| eqt_to_talcapital | float | Y | 归属于母公司的股东权益/全部投入资本 |
| currentdebt_to_debt | float | Y | 流动负债/负债合计 |
| longdeb_to_debt | float | Y | 非流动负债/负债合计 |
| ocf_to_shortdebt | float | Y | 经营活动产生的现金流量净额/流动负债 |
| debt_to_eqt | float | Y | 产权比率 |
| eqt_to_debt | float | Y | 归属于母公司的股东权益/负债合计 |
| eqt_to_interestdebt | float | Y | 归属于母公司的股东权益/带息债务 |
| tangibleasset_to_debt | float | Y | 有形资产/负债合计 |
| tangasset_to_intdebt | float | Y | 有形资产/带息债务 |
| tangibleasset_to_netdebt | float | Y | 有形资产/净债务 |
| ocf_to_debt | float | Y | 经营活动产生的现金流量净额/负债合计 |
| ocf_to_interestdebt | float | N | 经营活动产生的现金流量净额/带息债务 |
| ocf_to_netdebt | float | N | 经营活动产生的现金流量净额/净债务 |
| ebit_to_interest | float | N | 已获利息倍数(EBIT/利息费用) |
| longdebt_to_workingcapital | float | N | 长期债务与营运资金比率 |
| ebitda_to_debt | float | N | 息税折旧摊销前利润/负债合计 |
| turn_days | float | Y | 营业周期 |
| roa_yearly | float | Y | 年化总资产净利率 |
| roa_dp | float | Y | 总资产净利率(杜邦分析) |
| fixed_assets | float | Y | 固定资产合计 |
| profit_prefin_exp | float | N | 扣除财务费用前营业利润 |
| non_op_profit | float | N | 非营业利润 |
| op_to_ebt | float | N | 营业利润／利润总额 |
| nop_to_ebt | float | N | 非营业利润／利润总额 |
| ocf_to_profit | float | N | 经营活动产生的现金流量净额／营业利润 |
| cash_to_liqdebt | float | N | 货币资金／流动负债 |
| cash_to_liqdebt_withinterest | float | N | 货币资金／带息流动负债 |
| op_to_liqdebt | float | N | 营业利润／流动负债 |
| op_to_debt | float | N | 营业利润／负债合计 |
| roic_yearly | float | N | 年化投入资本回报率 |
| total_fa_trun | float | N | 固定资产合计周转率 |
| profit_to_op | float | Y | 利润总额／营业收入 |
| q_opincome | float | N | 经营活动单季度净收益 |
| q_investincome | float | N | 价值变动单季度净收益 |
| q_dtprofit | float | N | 扣除非经常损益后的单季度净利润 |
| q_eps | float | N | 每股收益(单季度) |
| q_netprofit_margin | float | N | 销售净利率(单季度) |
| q_gsprofit_margin | float | N | 销售毛利率(单季度) |
| q_exp_to_sales | float | N | 销售期间费用率(单季度) |
| q_profit_to_gr | float | N | 净利润／营业总收入(单季度) |
| q_saleexp_to_gr | float | Y | 销售费用／营业总收入 (单季度) |
| q_adminexp_to_gr | float | N | 管理费用／营业总收入 (单季度) |
| q_finaexp_to_gr | float | N | 财务费用／营业总收入 (单季度) |
| q_impair_to_gr_ttm | float | N | 资产减值损失／营业总收入(单季度) |
| q_gc_to_gr | float | Y | 营业总成本／营业总收入 (单季度) |
| q_op_to_gr | float | N | 营业利润／营业总收入(单季度) |
| q_roe | float | Y | 净资产收益率(单季度) |
| q_dt_roe | float | Y | 净资产单季度收益率(扣除非经常损益) |
| q_npta | float | Y | 总资产净利润(单季度) |
| q_opincome_to_ebt | float | N | 经营活动净收益／利润总额(单季度) |
| q_investincome_to_ebt | float | N | 价值变动净收益／利润总额(单季度) |
| q_dtprofit_to_profit | float | N | 扣除非经常损益后的净利润／净利润(单季度) |
| q_salescash_to_or | float | N | 销售商品提供劳务收到的现金／营业收入(单季度) |
| q_ocf_to_sales | float | Y | 经营活动产生的现金流量净额／营业收入(单季度) |
| q_ocf_to_or | float | N | 经营活动产生的现金流量净额／经营活动净收益(单季度) |
| basic_eps_yoy | float | Y | 基本每股收益同比增长率(%) |
| dt_eps_yoy | float | Y | 稀释每股收益同比增长率(%) |
| cfps_yoy | float | Y | 每股经营活动产生的现金流量净额同比增长率(%) |
| op_yoy | float | Y | 营业利润同比增长率(%) |
| ebt_yoy | float | Y | 利润总额同比增长率(%) |
| netprofit_yoy | float | Y | 归属母公司股东的净利润同比增长率(%) |
| dt_netprofit_yoy | float | Y | 归属母公司股东的净利润-扣除非经常损益同比增长率(%) |
| ocf_yoy | float | Y | 经营活动产生的现金流量净额同比增长率(%) |
| roe_yoy | float | Y | 净资产收益率(摊薄)同比增长率(%) |
| bps_yoy | float | Y | 每股净资产相对年初增长率(%) |
| assets_yoy | float | Y | 资产总计相对年初增长率(%) |
| eqt_yoy | float | Y | 归属母公司的股东权益相对年初增长率(%) |
| tr_yoy | float | Y | 营业总收入同比增长率(%) |
| or_yoy | float | Y | 营业收入同比增长率(%) |
| q_gr_yoy | float | N | 营业总收入同比增长率(%)(单季度) |
| q_gr_qoq | float | N | 营业总收入环比增长率(%)(单季度) |
| q_sales_yoy | float | Y | 营业收入同比增长率(%)(单季度) |
| q_sales_qoq | float | N | 营业收入环比增长率(%)(单季度) |
| q_op_yoy | float | N | 营业利润同比增长率(%)(单季度) |
| q_op_qoq | float | Y | 营业利润环比增长率(%)(单季度) |
| q_profit_yoy | float | N | 净利润同比增长率(%)(单季度) |
| q_profit_qoq | float | N | 净利润环比增长率(%)(单季度) |
| q_netprofit_yoy | float | N | 归属母公司股东的净利润同比增长率(%)(单季度) |
| q_netprofit_qoq | float | N | 归属母公司股东的净利润环比增长率(%)(单季度) |
| equity_yoy | float | Y | 净资产同比增长率 |
| rd_exp | float | N | 研发费用 |
| update_flag | str | N | 更新标识 |

接口用法
或者
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：fina_indicator，可以通过 数据工具 调试和查看数据。 描述：获取上市公司财务指标数据，为避免服务器压力，现阶段每次请求最多返回100条记录，可通过设置日期多次请求获取更多数据。 权限：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法 提示：当前接口只能按单只股票获取其历史数据，如果需要获取某一季度全部上市公司数据，请使用fina_indicator_vip接口（参数一致），需积攒5000积分。
- (字段) `ann_date` — str N 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `ann_date` — str Y 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `update_flag` — str N 更新标识  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [80] 财务审计意见  ·  股票数据 / 财务数据
(api: fina_audit | 输出字段: 7 | PIT字段: 是)

# (doc_id=80)  https://tushare.pro/document/2?doc_id=80

## 财务审计意见
接口：fina_audit 描述：获取上市公司定期财务审计意见数据 权限：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| ann_date | str | N | 公告日期 |
| start_date | str | N | 公告开始日期 |
| end_date | str | N | 公告结束日期 |
| period | str | N | 报告期(每个季度最后一天的日期,比如20171231表示年报) |

输出参数
| 名称 | 类型 | 描述 |
| --- | --- | --- |
| ts_code | str | TS股票代码 |
| ann_date | str | 公告日期 |
| end_date | str | 报告期 |
| audit_result | str | 审计结果 |
| audit_fees | float | 审计总费用（元） |
| audit_agency | str | 会计事务所 |
| audit_sign | str | 签字会计师 |

接口使用
数据示例

## [PIT / 更新口径 — 自动标记]
- (字段) `ann_date` — str N 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `ann_date` — str 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [81] 主营业务构成  ·  股票数据 / 财务数据
(api: fina_mainbz | 输出字段: 9 | PIT字段: 是)

# (doc_id=81)  https://tushare.pro/document/2?doc_id=81

## 主营业务构成
接口：fina_mainbz 描述：获得上市公司主营业务构成，分地区和产品两种方式 权限：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法 ，单次最大提取100行，总量不限制，可循环获取。 提示：当前接口只能按单只股票获取其历史数据，如果需要获取某一季度全部上市公司数据，请使用fina_mainbz_vip接口（参数一致），需积攒5000积分。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| period | str | N | 报告期(每个季度最后一天的日期,比如20171231表示年报) |
| type | str | N | 类型：P按产品 D按地区 I按行业（请输入大写字母P或者D） |
| start_date | str | N | 报告期开始日期 |
| end_date | str | N | 报告期结束日期 |

输出参数
| 名称 | 类型 | 描述 |
| --- | --- | --- |
| ts_code | str | TS代码 |
| end_date | str | 报告期 |
| bz_item | str | 主营业务来源 |
| bz_code | str | 主营业务来源类型（P按产品 D按地区 I按行业） |
| bz_sales | float | 主营业务收入(元) |
| bz_profit | float | 主营业务利润(元) |
| bz_cost | float | 主营业务成本(元) |
| curr_type | str | 货币代码 |
| update_flag | str | 是否更新 |

代码示例
获取某一季度全部股票数据
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：fina_mainbz 描述：获得上市公司主营业务构成，分地区和产品两种方式 权限：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法 ，单次最大提取100行，总量不限制，可循环获取。 提示：当前接口只能按单只股票获取其历史数据，如果需要获取某一季度全部上市公司数据，请使用fina_mainbz_vip接口（参数一致），需积攒5000积分。
- (字段) `update_flag` — str 是否更新  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [162] 财报披露日期表  ·  股票数据 / 财务数据
(api: disclosure_date | 输出字段: 6 | PIT字段: 是)

# (doc_id=162)  https://tushare.pro/document/2?doc_id=162

## 财报披露计划
接口：disclosure_date 描述：获取财报披露计划日期 限量：单次最大3000，总量不限制 积分：用户需要至少500积分才可以调取，积分越多权限越大，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | TS股票代码 |
| end_date | str | N | 财报周期（每个季度最后一天的日期，比如20181231表示2018年年报，20180630表示中报) |
| pre_date | str | N | 计划披露日期 |
| ann_date | str | N | 最新披露公告日 |
| actual_date | str | N | 实际披露日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS代码 |
| ann_date | str | Y | 最新披露公告日 |
| end_date | str | Y | 报告期 |
| pre_date | str | Y | 预计披露日期 |
| actual_date | str | Y | 实际披露日期 |
| modify_date | str | N | 披露日期修正记录 |

接口使用
数据示例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：disclosure_date 描述：获取财报披露计划日期 限量：单次最大3000，总量不限制 积分：用户需要至少500积分才可以调取，积分越多权限越大，具体请参阅 积分获取办法
- (字段) `pre_date` — str N 计划披露日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `ann_date` — str N 最新披露公告日  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `actual_date` — str N 实际披露日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `ann_date` — str Y 最新披露公告日  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `pre_date` — str Y 预计披露日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `actual_date` — str Y 实际披露日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `modify_date` — str N 披露日期修正记录  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [17] 参考数据  ·  股票数据
(api: — | 输出字段: 0 | PIT字段: 否)

# (doc_id=17)  https://tushare.pro/document/2?doc_id=17

## 市场参考数据
正如开篇所讲，公司行为、市场行为等市场参考数据是Pro未来可以有极大发挥的地方。我们将努力为大家提供尽可能多的数据内容，因为这一部分的很多数据可以为大家提供具有更有发掘价值的信息。
这一部分数据将采用迭代的方式，有新的就上新，没有新的就继续规划和发掘。很欢迎大家在Tushare社区里积极建言，提交需求，尤其是有意思的数据，我们分析确认后将纳入整体规划。对了，提供需求和建议，我们会有积分赠送哦。
从已经上线的数据来罗列，主要有以下：
沪深港通资金流向
沪深股通十大成交股
港股通十大成交股
融资融券交易汇总
融资融券交易明细


---

### [451] 个股异常波动  ·  股票数据 / 参考数据
(api: stk_shock | 输出字段: 6 | PIT字段: 是)

# (doc_id=451)  https://tushare.pro/document/2?doc_id=451

## 个股异常波动
## 接口介绍
接口：stk_shock 描述：根据证券交易所交易规则的有关规定，交易所每日发布股票交易异常波动情况 限量：单次最大1000条，可根据代码或日期循环提取 积分：需要6000积分可以调取，具体请参阅 积分获取办法
## 输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码（可以通过stock_basic获取）示例:000001.SZ |
| trade_date | str | N | 交易日期（YYYYMMDD格式）示例:20260312 |
| start_date | str | N | 开始日期（YYYYMMDD格式）示例:20260312 |
| end_date | str | N | 结束日期（YYYYMMDD格式）示例:20260312 |

## 输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| trade_date | str | Y | 公告日期 |
| name | str | Y | 股票名称 |
| trade_market | str | Y | 交易所 |
| reason | str | Y | 异常说明 |
| period | str | Y | 异常期间 |

## 代码示例
## 数据结果

## [PIT / 更新口径 — 自动标记]
- (字段) `trade_date` — str Y 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [452] 个股严重异常波动  ·  股票数据 / 参考数据
(api: stk_high_shock | 输出字段: 6 | PIT字段: 是)

# (doc_id=452)  https://tushare.pro/document/2?doc_id=452

## 个股严重异常波动
## 接口介绍
接口：stk_high_shock 描述：根据证券交易所交易规则的有关规定，交易所每日发布股票交易严重异常波动情况 限量：单次最大1000条，可根据代码或日期循环提取 积分：需要6000积分可以调取，具体请参阅 积分获取办法
## 输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码（可以通过stock_basic获取）示例:000001.SZ |
| trade_date | str | N | 交易日期（YYYYMMDD格式）示例:20260312 |
| start_date | str | N | 开始日期（YYYYMMDD格式）示例:20260312 |
| end_date | str | N | 结束日期（YYYYMMDD格式）示例:20260312 |

## 输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| trade_date | str | Y | 公告日期 |
| name | str | Y | 股票名称 |
| trade_market | str | Y | 交易所 |
| reason | str | Y | 异常说明 |
| period | str | Y | 异常期间 |

## 代码示例
## 数据结果

## [PIT / 更新口径 — 自动标记]
- (字段) `trade_date` — str Y 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [453] 交易所重点提示证券  ·  股票数据 / 参考数据
(api: stk_alert | 输出字段: 5 | PIT字段: 否)

# (doc_id=453)  https://tushare.pro/document/2?doc_id=453

## 交易所重点提示证券
## 接口介绍
接口：stk_alert 描述：根据证券交易所交易规则的有关规定，交易所每日发布重点提示证券 限量：单次最大1000条，可根据代码或日期循环提取 积分：需要6000积分可以调取，具体请参阅 积分获取办法
## 输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码（可以通过stock_basic获取）示例:000001.SZ |
| trade_date | str | N | 交易所重点提示起始日期（YYYYMMDD格式）示例:20260312 |
| start_date | str | N | 开始日期（YYYYMMDD格式）示例:20260312 |
| end_date | str | N | 结束日期（YYYYMMDD格式）示例:20260312 |

## 输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| name | str | Y | 股票名称 |
| start_date | str | Y | 交易所重点提示起始日期 |
| end_date | str | Y | 交易所重点提示参考截至日期 |
| type | str | Y | 提示类型 |

## 代码示例
## 数据结果


---

### [61] 前十大股东  ·  股票数据 / 参考数据
(api: top10_holders | 输出字段: 9 | PIT字段: 是)

# (doc_id=61)  https://tushare.pro/document/2?doc_id=61

## 前十大股东
接口：top10_holders 描述：获取上市公司前十大股东数据，包括持有数量和比例等信息 积分：需2000积分以上才可以调取本接口，5000积分以上频次会更高
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS代码 |
| period | str | N | 报告期（YYYYMMDD格式，一般为每个季度最后一天） |
| ann_date | str | N | 公告日期 |
| start_date | str | N | 报告期开始日期 |
| end_date | str | N | 报告期结束日期 |

输出参数
| 名称 | 类型 | 描述 |
| --- | --- | --- |
| ts_code | str | TS股票代码 |
| ann_date | str | 公告日期 |
| end_date | str | 报告期 |
| holder_name | str | 股东名称 |
| hold_amount | float | 持有数量（股） |
| hold_ratio | float | 占总股本比例(%) |
| hold_float_ratio | float | 占流通股本比例(%) |
| hold_change | float | 持股变动 |
| holder_type | str | 股东类型 |

接口用法
或者
数据样例

## [PIT / 更新口径 — 自动标记]
- (字段) `ann_date` — str N 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `ann_date` — str 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [62] 前十大流通股东  ·  股票数据 / 参考数据
(api: top10_floatholders | 输出字段: 9 | PIT字段: 是)

# (doc_id=62)  https://tushare.pro/document/2?doc_id=62

## 前十大流通股东
接口：top10_floatholders 描述：获取上市公司前十大流通股东数据 积分：需2000积分以上才可以调取本接口，5000积分以上频次会更高
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS代码 |
| period | str | N | 报告期（YYYYMMDD格式，一般为每个季度最后一天） |
| ann_date | str | N | 公告日期 |
| start_date | str | N | 报告期开始日期 |
| end_date | str | N | 报告期结束日期 |

输出参数
| 名称 | 类型 | 描述 |
| --- | --- | --- |
| ts_code | str | TS股票代码 |
| ann_date | str | 公告日期 |
| end_date | str | 报告期 |
| holder_name | str | 股东名称 |
| hold_amount | float | 持有数量（股） |
| hold_ratio | float | 占总股本比例(%) |
| hold_float_ratio | float | 占流通股本比例(%) |
| hold_change | float | 持股变动 |
| holder_type | str | 股东类型 |

接口用法
或者
数据样例

## [PIT / 更新口径 — 自动标记]
- (字段) `ann_date` — str N 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `ann_date` — str 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [110] 股权质押统计数据  ·  股票数据 / 参考数据
(api: pledge_stat | 输出字段: 7 | PIT字段: 否)

# (doc_id=110)  https://tushare.pro/document/2?doc_id=110

## 股权质押统计数据
接口：pledge_stat 描述：获取股票质押统计数据 限量：单次最大1000 积分：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码 |
| end_date | str | N | 截止日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS代码 |
| end_date | str | Y | 截止日期 |
| pledge_count | int | Y | 质押次数 |
| unrest_pledge | float | Y | 无限售股质押数量（万） |
| rest_pledge | float | Y | 限售股份质押数量（万） |
| total_share | float | Y | 总股本 |
| pledge_ratio | float | Y | 质押比例 |

接口使用
或者
数据示例


---

### [111] 股权质押明细数据  ·  股票数据 / 参考数据
(api: pledge_detail | 输出字段: 14 | PIT字段: 是)

# (doc_id=111)  https://tushare.pro/document/2?doc_id=111

## 股权质押明细
接口：pledge_detail 描述：获取股票质押明细数据 限量：单次最大1000 积分：用户需要至少500积分才可以调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码 |
| ann_date | str | N | 公告日期 |
| start_date | str | N | 公告开始日期 |
| end_date | str | N | 公告结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS股票代码 |
| ann_date | str | Y | 公告日期 |
| holder_name | str | Y | 股东名称 |
| pledge_amount | float | Y | 质押数量（万股） |
| start_date | str | Y | 质押开始日期 |
| end_date | str | Y | 质押结束日期 |
| is_release | str | Y | 是否已解押 |
| release_date | str | Y | 解押日期 |
| pledgor | str | Y | 质押方 |
| holding_amount | float | Y | 持股总数（万股） |
| pledged_amount | float | Y | 质押总数（万股） |
| p_total_ratio | float | Y | 本次质押占总股本比例 |
| h_total_ratio | float | Y | 持股总数占总股本比例 |
| is_buyback | str | Y | 是否回购（0否 1是） |

接口使用
或者
数据示例

## [PIT / 更新口径 — 自动标记]
- (字段) `ann_date` — str N 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `ann_date` — str Y 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [124] 股票回购  ·  股票数据 / 参考数据
(api: repurchase | 输出字段: 9 | PIT字段: 是)

# (doc_id=124)  https://tushare.pro/document/2?doc_id=124

## 股票回购
接口：repurchase 描述：获取上市公司回购股票数据 积分：用户需要至少600积分才可以调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ann_date | str | N | 公告日期（任意填参数，如果都不填，单次默认返回2000条） |
| start_date | str | N | 公告开始日期 |
| end_date | str | N | 公告结束日期 |

以上日期格式为：YYYYMMDD，比如20181010
输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS代码 |
| ann_date | str | Y | 公告日期 |
| end_date | str | Y | 截止日期 |
| proc | str | Y | 进度 |
| exp_date | str | Y | 过期日期 |
| vol | float | Y | 回购数量 |
| amount | float | Y | 回购金额 |
| high_limit | float | Y | 回购最高价 |
| low_limit | float | Y | 回购最低价 |

接口示例
数据示例

## [PIT / 更新口径 — 自动标记]
- (字段) `ann_date` — str N 公告日期（任意填参数，如果都不填，单次默认返回2000条）  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `ann_date` — str Y 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [160] 限售股解禁  ·  股票数据 / 参考数据
(api: share_float | 输出字段: 7 | PIT字段: 是)

# (doc_id=160)  https://tushare.pro/document/2?doc_id=160

## 限售股解禁
接口：share_float 描述：获取限售股解禁 限量：单次最大6000条，总量不限制 积分：120分可调取，每分钟内限制次数，超过5000积分频次相对较高，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | TS股票代码 |
| ann_date | str | N | 公告日期（日期格式：YYYYMMDD，下同） |
| float_date | str | N | 解禁日期 |
| start_date | str | N | 解禁开始日期 |
| end_date | str | N | 解禁结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS代码 |
| ann_date | str | Y | 公告日期 |
| float_date | str | Y | 解禁日期 |
| float_share | float | Y | 流通股份(股) |
| float_ratio | float | Y | 流通股份占总股本比率 |
| holder_name | str | Y | 股东名称 |
| share_type | str | Y | 股份类型 |

接口使用
数据示例

## [PIT / 更新口径 — 自动标记]
- (字段) `ann_date` — str N 公告日期（日期格式：YYYYMMDD，下同）  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `ann_date` — str Y 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [161] 大宗交易  ·  股票数据 / 参考数据
(api: block_trade | 输出字段: 7 | PIT字段: 否)

# (doc_id=161)  https://tushare.pro/document/2?doc_id=161

## 大宗交易
接口：block_trade 描述：大宗交易 限量：单次最大1000条，总量不限制 积分：300积分可调取，每分钟内限制次数，超过5000积分频次相对较高，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | TS代码（股票代码和日期至少输入一个参数） |
| trade_date | str | N | 交易日期（格式：YYYYMMDD，下同） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS代码 |
| trade_date | str | Y | 交易日历 |
| price | float | Y | 成交价 |
| vol | float | Y | 成交量（万股） |
| amount | float | Y | 成交金额 |
| buyer | str | Y | 买方营业部 |
| seller | str | Y | 卖方营业部 |

接口使用
数据示例


---

### [164] 股票开户数据（停）  ·  股票数据 / 参考数据
(api: stk_account | 输出字段: 5 | PIT字段: 否)

# (doc_id=164)  https://tushare.pro/document/2?doc_id=164

## 股票账户开户数据
接口：stk_account 描述：获取股票账户开户数据，统计周期为一周 积分：600积分可调取，具体请参阅 积分获取办法
注：此数据官方已经停止更新。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| date | str | N | 日期 |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| date | str | Y | 统计周期 |
| weekly_new | float | Y | 本周新增（万） |
| total | float | Y | 期末总账户数（万） |
| weekly_hold | float | Y | 本周持仓账户数（万） |
| weekly_trade | float | Y | 本周参与交易账户数（万） |

接口使用
数据示例
数据说明：从2017年2月10日开始，中国证券登记结算公司停止了发布本周持仓账户数和本周交易账户数；另外，2015年5月8日之前的数据结构也不同，具体请参阅 股票开户旧数据 接口。

## [PIT / 更新口径 — 自动标记]
- (正文) 注：此数据官方已经停止更新。


---

### [165] 股票开户数据（旧）  ·  股票数据 / 参考数据
(api: stk_account_old | 输出字段: 9 | PIT字段: 否)

# (doc_id=165)  https://tushare.pro/document/2?doc_id=165

## 股票账户开户数据（旧）
接口：stk_account_old 描述：获取股票账户开户数据旧版格式数据，数据从2008年1月开始，到2015年5月29，新数据请通过 股票开户数据 获取。 积分：600积分可调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| date | str | Y | 统计周期 |
| new_sh | int | Y | 本周新增（上海，户） |
| new_sz | int | Y | 本周新增（深圳，户） |
| active_sh | float | Y | 期末有效账户（上海，万户） |
| active_sz | float | Y | 期末有效账户（深圳，万户） |
| total_sh | float | Y | 期末账户数（上海，万户） |
| total_sz | float | Y | 期末账户数（深圳，万户） |
| trade_sh | float | Y | 参与交易账户数（上海，万户） |
| trade_sz | float | Y | 参与交易账户数（深圳，万户） |

接口使用
数据示例


---

### [166] 股东人数  ·  股票数据 / 参考数据
(api: stk_holdernumber | 输出字段: 4 | PIT字段: 是)

# (doc_id=166)  https://tushare.pro/document/2?doc_id=166

## 股东人数
接口：stk_holdernumber 描述：获取上市公司股东户数数据，数据不定期公布 限量：单次最大3000,总量不限制 积分：600积分可调取，基础积分每分钟调取100次，5000积分以上频次相对较高。具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | TS股票代码 |
| ann_date | str | N | 公告日期 |
| enddate | str | N | 截止日期 |
| start_date | str | N | 公告开始日期 |
| end_date | str | N | 公告结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS股票代码 |
| ann_date | str | Y | 公告日期 |
| end_date | str | Y | 截止日期 |
| holder_num | int | Y | 股东户数 |

接口使用
数据示例

## [PIT / 更新口径 — 自动标记]
- (字段) `ann_date` — str N 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `ann_date` — str Y 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [175] 股东增减持  ·  股票数据 / 参考数据
(api: stk_holdertrade | 输出字段: 13 | PIT字段: 是)

# (doc_id=175)  https://tushare.pro/document/2?doc_id=175

## 股东增减持
接口：stk_holdertrade 描述：获取上市公司增减持数据，了解重要股东近期及历史上的股份增减变化 限量：单次最大提取3000行记录，总量不限制 积分：用户需要至少2000积分才可以调取。基础积分有流量控制，积分越多权限越大，5000积分以上无明显限制，请自行提高积分，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | TS股票代码 |
| ann_date | str | N | 公告日期 |
| start_date | str | N | 公告开始日期 |
| end_date | str | N | 公告结束日期 |
| trade_type | str | N | 交易类型IN增持DE减持 |
| holder_type | str | N | 股东类型C公司P个人G高管 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS代码 |
| ann_date | str | Y | 公告日期 |
| holder_name | str | Y | 股东名称 |
| holder_type | str | Y | 股东类型G高管P个人C公司 |
| in_de | str | Y | 类型IN增持DE减持 |
| change_vol | float | Y | 变动数量 |
| change_ratio | float | Y | 占流通比例（%） |
| after_share | float | Y | 变动后持股 |
| after_ratio | float | Y | 变动后占流通比例（%） |
| avg_price | float | Y | 平均价格 |
| total_share | float | Y | 持股总数 |
| begin_date | str | N | 增减持开始日期 |
| close_date | str | N | 增减持结束日期 |

接口示例
数据示例

## [PIT / 更新口径 — 自动标记]
- (字段) `ann_date` — str N 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `ann_date` — str Y 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [291] 特色数据  ·  股票数据
(api: — | 输出字段: 0 | PIT字段: 否)

# (doc_id=291)  https://tushare.pro/document/2?doc_id=291

## 股票特色数据
Tushare股票特色数据将陆续上线，第一批包括卖方盈利预测、股票每日筹码和成本数据等。
1、 券商（卖方）盈利预测数据
数据来自于券商发布的研究报告，通过结构化，提取针对个股的盈利预测和评级数据。数据从2010年开始，提供超过10年的盈利预测数据，每天20点更新。主要的盈利预测数据主要来自报告的核心部分，如下图：
部分券商给出了评级，比如强烈推荐买入，增持等，以及未来一年或半年内最高目标价和最低目标价信息。
2、 股票每日筹码成本和胜率
筹码数据分析投资者持仓成本的关键指标数据，本接口提供每个股票每天的平均成本以及胜率数据。在各大行情软件上，我们都可以看到筹码展示，但绝大多数数据公司都不直接提供筹码数据API或者数据库服务，Tushare根据多年经验，自行设计开发了筹码数据供用户使用，因每家公司算法不同，甚至用于计算的基础数据也不同，因此数据会有一些差异，这属于正常情况。
Tushare的每日筹码平均成本和胜率数据，主要包括了：该股历史最高价、最低价、各分位持仓成本价格、加权平均价和胜率。
3、 股票每日筹码分布
股票的每日筹码筹码分布，是每个股票每天的持仓价位及占比，能详细看出当前投资者的持仓成本情况。数据在各大行情软件上呈现出的是一个堆积的波浪图形状。由于目前市场直接提供该类数据的供应商非常少，对于量化分析或者筹码数据融入量化策略中寻求Alpha则非常困难，我们通过直接提供API方式为用户方便获取筹码数据开发另类策略提供了可能。
每日筹码分布数据，包括了成本价附近上下各50档成本的分布，一定程度体现了市场的持仓成本分布情况。注：该数据只作为参考，不具有绝对真实性。
4、 券商金股数据
券商研究所一般会在每个月末发布下个月十大金股，代表了该研究所和各团队对下个月市场热点的观点，通过收集市场金股数据，可以形成一致预期效果，对投资者有一定参考作用，尤其从组合的角度作为选择的依据之一。建议投资者跟踪参考，积2000积分可以调取。

## [PIT / 更新口径 — 自动标记]
- (正文) 数据来自于券商发布的研究报告，通过结构化，提取针对个股的盈利预测和评级数据。数据从2010年开始，提供超过10年的盈利预测数据，每天20点更新。主要的盈利预测数据主要来自报告的核心部分，如下图：


---

### [292] 券商盈利预测数据  ·  股票数据 / 特色数据
(api: report_rc | 输出字段: 23 | PIT字段: 是)

# (doc_id=292)  https://tushare.pro/document/2?doc_id=292

## 卖方盈利预测数据
接口：report_rc 描述：获取券商（卖方）每天研报的盈利预测数据，数据从2010年开始，每晚19~22点更新当日数据 限量：单次最大3000条，可分页和循环提取所有数据 权限：本接口120积分可以试用，每天10次请求，正式权限需8000积分，每天可请求100000次，10000积分以上无总量限制。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码 |
| report_date | str | N | 报告日期 |
| start_date | str | N | 报告开始日期 |
| end_date | str | N | 报告结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| name | str | Y | 股票名称 |
| report_date | str | Y | 研报日期 |
| report_title | str | Y | 报告标题 |
| report_type | str | Y | 报告类型 |
| classify | str | Y | 报告分类 |
| org_name | str | Y | 机构名称 |
| author_name | str | Y | 作者 |
| quarter | str | Y | 预测报告期 |
| op_rt | float | Y | 预测营业收入（万元） |
| op_pr | float | Y | 预测营业利润（万元） |
| tp | float | Y | 预测利润总额（万元） |
| np | float | Y | 预测净利润（万元） |
| eps | float | Y | 预测每股收益（元） |
| pe | float | Y | 预测市盈率 |
| rd | float | Y | 预测股息率 |
| roe | float | Y | 预测净资产收益率 |
| ev_ebitda | float | Y | 预测EV/EBITDA |
| rating | str | Y | 卖方评级 |
| max_price | float | Y | 预测最高目标价 |
| min_price | float | Y | 预测最低目标价 |
| imp_dg | str | N | 机构关注度 |
| create_time | datetime | N | TS数据更新时间 |

接口用法
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：report_rc 描述：获取券商（卖方）每天研报的盈利预测数据，数据从2010年开始，每晚19~22点更新当日数据 限量：单次最大3000条，可分页和循环提取所有数据 权限：本接口120积分可以试用，每天10次请求，正式权限需8000积分，每天可请求100000次，10000积分以上无总量限制。
- (字段) `create_time` — datetime N TS数据更新时间  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [293] 每日筹码及胜率  ·  股票数据 / 特色数据
(api: cyq_perf | 输出字段: 11 | PIT字段: 否)

# (doc_id=293)  https://tushare.pro/document/2?doc_id=293

## 每日筹码及胜率
接口：cyq_perf 描述：获取A股每日筹码平均成本和胜率情况，每天18~19点左右更新，数据从2018年开始 来源：Tushare社区 限量：单次最大6000条，可以分页或者循环提取 积分：5000积分每天20000次，10000积分每天200000次，15000积分每天不限总量
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| trade_date | str | N | 交易日期（YYYYMMDD） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| trade_date | str | Y | 交易日期 |
| his_low | float | Y | 历史最低价 |
| his_high | float | Y | 历史最高价 |
| cost_5pct | float | Y | 5分位成本 |
| cost_15pct | float | Y | 15分位成本 |
| cost_50pct | float | Y | 50分位成本 |
| cost_85pct | float | Y | 85分位成本 |
| cost_95pct | float | Y | 95分位成本 |
| weight_avg | float | Y | 加权平均成本 |
| winner_rate | float | Y | 胜率 |

接口用法
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：cyq_perf 描述：获取A股每日筹码平均成本和胜率情况，每天18~19点左右更新，数据从2018年开始 来源：Tushare社区 限量：单次最大6000条，可以分页或者循环提取 积分：5000积分每天20000次，10000积分每天200000次，15000积分每天不限总量


---

### [294] 每日筹码分布  ·  股票数据 / 特色数据
(api: cyq_chips | 输出字段: 4 | PIT字段: 否)

# (doc_id=294)  https://tushare.pro/document/2?doc_id=294

## 每日筹码分布
接口：cyq_chips 描述：获取A股每日的筹码分布情况，提供各价位占比，数据从2018年开始，每天18~19点之间更新当日数据 来源：Tushare社区 限量：单次最大6000条，可以按股票代码和日期循环提取 积分：5000积分每天20000次每分钟可以取200次，10000积分每天200000次，15000积分每天不限总量
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| trade_date | str | N | 交易日期（YYYYMMDD） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| trade_date | str | Y | 交易日期 |
| price | float | Y | 成本价格 |
| percent | float | Y | 价格占比（%） |

接口用法
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：cyq_chips 描述：获取A股每日的筹码分布情况，提供各价位占比，数据从2018年开始，每天18~19点之间更新当日数据 来源：Tushare社区 限量：单次最大6000条，可以按股票代码和日期循环提取 积分：5000积分每天20000次每分钟可以取200次，10000积分每天200000次，15000积分每天不限总量


---

### [296] 股票技术面因子  ·  股票数据 / 特色数据
(api: stk_factor | 输出字段: 35 | PIT字段: 否)

# (doc_id=296)  https://tushare.pro/document/2?doc_id=296

## 股票技术因子（量化因子）
接口：stk_factor 描述：获取股票每日技术面因子数据，用于跟踪股票当前走势情况，数据由Tushare社区自产，覆盖全历史 限量：单次最大10000条，可以循环或者分页提取 积分：5000积分每分钟可以请求100次，8000积分以上每分钟500次，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码 |
| trade_date | str | N | 交易日期 （yyyymmdd，下同） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| trade_date | str | Y | 交易日期 |
| close | float | Y | 收盘价 |
| open | float | Y | 开盘价 |
| high | float | Y | 最高价 |
| low | float | Y | 最低价 |
| pre_close | float | Y | 昨收价 |
| change | float | Y | 涨跌额 |
| pct_change | float | Y | 涨跌幅 |
| vol | float | Y | 成交量 （手） |
| amount | float | Y | 成交额 （千元） |
| adj_factor | float | Y | 复权因子 |
| open_hfq | float | Y | 开盘价后复权 |
| open_qfq | float | Y | 开盘价前复权 |
| close_hfq | float | Y | 收盘价后复权 |
| close_qfq | float | Y | 收盘价前复权 |
| high_hfq | float | Y | 最高价后复权 |
| high_qfq | float | Y | 最高价前复权 |
| low_hfq | float | Y | 最低价后复权 |
| low_qfq | float | Y | 最低价前复权 |
| pre_close_hfq | float | Y | 昨收价后复权 |
| pre_close_qfq | float | Y | 昨收价前复权 |
| macd_dif | float | Y | MACD_DIF (基于前复权价格计算，下同) |
| macd_dea | float | Y | MACD_DEA |
| macd | float | Y | MACD |
| kdj_k | float | Y | KDJ_K |
| kdj_d | float | Y | KDJ_D |
| kdj_j | float | Y | KDJ_J |
| rsi_6 | float | Y | RSI_6 |
| rsi_12 | float | Y | RSI_12 |
| rsi_24 | float | Y | RSI_24 |
| boll_upper | float | Y | BOLL_UPPER |
| boll_mid | float | Y | BOLL_MID |
| boll_lower | float | Y | BOLL_LOWER |
| cci | float | Y | CCI |

接口用法
数据样例


---

### [328] 股票技术面因子(专业版）  ·  股票数据 / 特色数据
(api: stk_factor_pro | 输出字段: 261 | PIT字段: 否)

# (doc_id=328)  https://tushare.pro/document/2?doc_id=328

## 股票技术面因子(专业版)
接口：stk_factor_pro 描述：获取股票每日技术面因子数据，用于跟踪股票当前走势情况，数据由Tushare社区自产，覆盖全历史；输出参数_bfq表示不复权，_qfq表示前复权 _hfq表示后复权，描述中说明了因子的默认传参，如需要特殊参数或者更多因子可以联系管理员评估 限量：单次调取最多返回10000条数据，可以通过日期参数循环 积分：5000积分每分钟可以请求30次，8000积分以上每分钟500次，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码 |
| trade_date | str | N | 交易日期(格式：yyyymmdd，下同) |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| trade_date | str | Y | 交易日期 |
| open | float | Y | 开盘价 |
| open_hfq | float | Y | 开盘价（后复权） |
| open_qfq | float | Y | 开盘价（前复权） |
| high | float | Y | 最高价 |
| high_hfq | float | Y | 最高价（后复权） |
| high_qfq | float | Y | 最高价（前复权） |
| low | float | Y | 最低价 |
| low_hfq | float | Y | 最低价（后复权） |
| low_qfq | float | Y | 最低价（前复权） |
| close | float | Y | 收盘价 |
| close_hfq | float | Y | 收盘价（后复权） |
| close_qfq | float | Y | 收盘价（前复权） |
| pre_close | float | Y | 昨收价(前复权)--为daily接口的pre_close,以当时复权因子计算值跟前一日close_qfq对不上，可不用 |
| change | float | Y | 涨跌额 |
| pct_chg | float | Y | 涨跌幅 （除权后的涨跌幅） |
| vol | float | Y | 成交量 （手） |
| amount | float | Y | 成交额 （千元） |
| turnover_rate | float | Y | 换手率（%） |
| turnover_rate_f | float | Y | 换手率（自由流通股） |
| volume_ratio | float | Y | 量比 |
| pe | float | Y | 市盈率（总市值/净利润， 亏损的PE为空） |
| pe_ttm | float | Y | 市盈率（TTM，亏损的PE为空） |
| pb | float | Y | 市净率（总市值/净资产） |
| ps | float | Y | 市销率 |
| ps_ttm | float | Y | 市销率（TTM） |
| dv_ratio | float | Y | 股息率 （%） |
| dv_ttm | float | Y | 股息率（TTM）（%） |
| total_share | float | Y | 总股本 （万股） |
| float_share | float | Y | 流通股本 （万股） |
| free_share | float | Y | 自由流通股本 （万） |
| total_mv | float | Y | 总市值 （万元） |
| circ_mv | float | Y | 流通市值（万元） |
| adj_factor | float | Y | 复权因子 |
| asi_bfq | float | Y | 振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10 |
| asi_hfq | float | Y | 振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10 |
| asi_qfq | float | Y | 振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10 |
| asit_bfq | float | Y | 振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10 |
| asit_hfq | float | Y | 振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10 |
| asit_qfq | float | Y | 振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10 |
| atr_bfq | float | Y | 真实波动N日平均值-CLOSE, HIGH, LOW, N=20 |
| atr_hfq | float | Y | 真实波动N日平均值-CLOSE, HIGH, LOW, N=20 |
| atr_qfq | float | Y | 真实波动N日平均值-CLOSE, HIGH, LOW, N=20 |
| bbi_bfq | float | Y | BBI多空指标-CLOSE, M1=3, M2=6, M3=12, M4=20 |
| bbi_hfq | float | Y | BBI多空指标-CLOSE, M1=3, M2=6, M3=12, M4=21 |
| bbi_qfq | float | Y | BBI多空指标-CLOSE, M1=3, M2=6, M3=12, M4=22 |
| bias1_bfq | float | Y | BIAS乖离率-CLOSE, L1=6, L2=12, L3=24 |
| bias1_hfq | float | Y | BIAS乖离率-CLOSE, L1=6, L2=12, L3=24 |
| bias1_qfq | float | Y | BIAS乖离率-CLOSE, L1=6, L2=12, L3=24 |
| bias2_bfq | float | Y | BIAS乖离率-CLOSE, L1=6, L2=12, L3=24 |
| bias2_hfq | float | Y | BIAS乖离率-CLOSE, L1=6, L2=12, L3=24 |
| bias2_qfq | float | Y | BIAS乖离率-CLOSE, L1=6, L2=12, L3=24 |
| bias3_bfq | float | Y | BIAS乖离率-CLOSE, L1=6, L2=12, L3=24 |
| bias3_hfq | float | Y | BIAS乖离率-CLOSE, L1=6, L2=12, L3=24 |
| bias3_qfq | float | Y | BIAS乖离率-CLOSE, L1=6, L2=12, L3=24 |
| boll_lower_bfq | float | Y | BOLL指标，布林带-CLOSE, N=20, P=2 |
| boll_lower_hfq | float | Y | BOLL指标，布林带-CLOSE, N=20, P=2 |
| boll_lower_qfq | float | Y | BOLL指标，布林带-CLOSE, N=20, P=2 |
| boll_mid_bfq | float | Y | BOLL指标，布林带-CLOSE, N=20, P=2 |
| boll_mid_hfq | float | Y | BOLL指标，布林带-CLOSE, N=20, P=2 |
| boll_mid_qfq | float | Y | BOLL指标，布林带-CLOSE, N=20, P=2 |
| boll_upper_bfq | float | Y | BOLL指标，布林带-CLOSE, N=20, P=2 |
| boll_upper_hfq | float | Y | BOLL指标，布林带-CLOSE, N=20, P=2 |
| boll_upper_qfq | float | Y | BOLL指标，布林带-CLOSE, N=20, P=2 |
| brar_ar_bfq | float | Y | BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26 |
| brar_ar_hfq | float | Y | BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26 |
| brar_ar_qfq | float | Y | BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26 |
| brar_br_bfq | float | Y | BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26 |
| brar_br_hfq | float | Y | BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26 |
| brar_br_qfq | float | Y | BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26 |
| cci_bfq | float | Y | 顺势指标又叫CCI指标-CLOSE, HIGH, LOW, N=14 |
| cci_hfq | float | Y | 顺势指标又叫CCI指标-CLOSE, HIGH, LOW, N=14 |
| cci_qfq | float | Y | 顺势指标又叫CCI指标-CLOSE, HIGH, LOW, N=14 |
| cr_bfq | float | Y | CR价格动量指标-CLOSE, HIGH, LOW, N=20 |
| cr_hfq | float | Y | CR价格动量指标-CLOSE, HIGH, LOW, N=20 |
| cr_qfq | float | Y | CR价格动量指标-CLOSE, HIGH, LOW, N=20 |
| dfma_dif_bfq | float | Y | 平行线差指标-CLOSE, N1=10, N2=50, M=10 |
| dfma_dif_hfq | float | Y | 平行线差指标-CLOSE, N1=10, N2=50, M=10 |
| dfma_dif_qfq | float | Y | 平行线差指标-CLOSE, N1=10, N2=50, M=10 |
| dfma_difma_bfq | float | Y | 平行线差指标-CLOSE, N1=10, N2=50, M=10 |
| dfma_difma_hfq | float | Y | 平行线差指标-CLOSE, N1=10, N2=50, M=10 |
| dfma_difma_qfq | float | Y | 平行线差指标-CLOSE, N1=10, N2=50, M=10 |
| dmi_adx_bfq | float | Y | 动向指标-CLOSE, HIGH, LOW, M1=14, M2=6 |
| dmi_adx_hfq | float | Y | 动向指标-CLOSE, HIGH, LOW, M1=14, M2=6 |
| dmi_adx_qfq | float | Y | 动向指标-CLOSE, HIGH, LOW, M1=14, M2=6 |
| dmi_adxr_bfq | float | Y | 动向指标-CLOSE, HIGH, LOW, M1=14, M2=6 |
| dmi_adxr_hfq | float | Y | 动向指标-CLOSE, HIGH, LOW, M1=14, M2=6 |
| dmi_adxr_qfq | float | Y | 动向指标-CLOSE, HIGH, LOW, M1=14, M2=6 |
| dmi_mdi_bfq | float | Y | 动向指标-CLOSE, HIGH, LOW, M1=14, M2=6 |
| dmi_mdi_hfq | float | Y | 动向指标-CLOSE, HIGH, LOW, M1=14, M2=6 |
| dmi_mdi_qfq | float | Y | 动向指标-CLOSE, HIGH, LOW, M1=14, M2=6 |
| dmi_pdi_bfq | float | Y | 动向指标-CLOSE, HIGH, LOW, M1=14, M2=6 |
| dmi_pdi_hfq | float | Y | 动向指标-CLOSE, HIGH, LOW, M1=14, M2=6 |
| dmi_pdi_qfq | float | Y | 动向指标-CLOSE, HIGH, LOW, M1=14, M2=6 |
| downdays | float | Y | 连跌天数 |
| updays | float | Y | 连涨天数 |
| dpo_bfq | float | Y | 区间震荡线-CLOSE, M1=20, M2=10, M3=6 |
| dpo_hfq | float | Y | 区间震荡线-CLOSE, M1=20, M2=10, M3=6 |
| dpo_qfq | float | Y | 区间震荡线-CLOSE, M1=20, M2=10, M3=6 |
| madpo_bfq | float | Y | 区间震荡线-CLOSE, M1=20, M2=10, M3=6 |
| madpo_hfq | float | Y | 区间震荡线-CLOSE, M1=20, M2=10, M3=6 |
| madpo_qfq | float | Y | 区间震荡线-CLOSE, M1=20, M2=10, M3=6 |
| ema_bfq_10 | float | Y | 指数移动平均-N=10 |
| ema_bfq_20 | float | Y | 指数移动平均-N=20 |
| ema_bfq_250 | float | Y | 指数移动平均-N=250 |
| ema_bfq_30 | float | Y | 指数移动平均-N=30 |
| ema_bfq_5 | float | Y | 指数移动平均-N=5 |
| ema_bfq_60 | float | Y | 指数移动平均-N=60 |
| ema_bfq_90 | float | Y | 指数移动平均-N=90 |
| ema_hfq_10 | float | Y | 指数移动平均-N=10 |
| ema_hfq_20 | float | Y | 指数移动平均-N=20 |
| ema_hfq_250 | float | Y | 指数移动平均-N=250 |
| ema_hfq_30 | float | Y | 指数移动平均-N=30 |
| ema_hfq_5 | float | Y | 指数移动平均-N=5 |
| ema_hfq_60 | float | Y | 指数移动平均-N=60 |
| ema_hfq_90 | float | Y | 指数移动平均-N=90 |
| ema_qfq_10 | float | Y | 指数移动平均-N=10 |
| ema_qfq_20 | float | Y | 指数移动平均-N=20 |
| ema_qfq_250 | float | Y | 指数移动平均-N=250 |
| ema_qfq_30 | float | Y | 指数移动平均-N=30 |
| ema_qfq_5 | float | Y | 指数移动平均-N=5 |
| ema_qfq_60 | float | Y | 指数移动平均-N=60 |
| ema_qfq_90 | float | Y | 指数移动平均-N=90 |
| emv_bfq | float | Y | 简易波动指标-HIGH, LOW, VOL, N=14, M=9 |
| emv_hfq | float | Y | 简易波动指标-HIGH, LOW, VOL, N=14, M=9 |
| emv_qfq | float | Y | 简易波动指标-HIGH, LOW, VOL, N=14, M=9 |
| maemv_bfq | float | Y | 简易波动指标-HIGH, LOW, VOL, N=14, M=9 |
| maemv_hfq | float | Y | 简易波动指标-HIGH, LOW, VOL, N=14, M=9 |
| maemv_qfq | float | Y | 简易波动指标-HIGH, LOW, VOL, N=14, M=9 |
| expma_12_bfq | float | Y | EMA指数平均数指标-CLOSE, N1=12, N2=50 |
| expma_12_hfq | float | Y | EMA指数平均数指标-CLOSE, N1=12, N2=50 |
| expma_12_qfq | float | Y | EMA指数平均数指标-CLOSE, N1=12, N2=50 |
| expma_50_bfq | float | Y | EMA指数平均数指标-CLOSE, N1=12, N2=50 |
| expma_50_hfq | float | Y | EMA指数平均数指标-CLOSE, N1=12, N2=50 |
| expma_50_qfq | float | Y | EMA指数平均数指标-CLOSE, N1=12, N2=50 |
| kdj_bfq | float | Y | KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3 |
| kdj_hfq | float | Y | KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3 |
| kdj_qfq | float | Y | KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3 |
| kdj_d_bfq | float | Y | KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3 |
| kdj_d_hfq | float | Y | KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3 |
| kdj_d_qfq | float | Y | KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3 |
| kdj_k_bfq | float | Y | KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3 |
| kdj_k_hfq | float | Y | KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3 |
| kdj_k_qfq | float | Y | KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3 |
| ktn_down_bfq | float | Y | 肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10 |
| ktn_down_hfq | float | Y | 肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10 |
| ktn_down_qfq | float | Y | 肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10 |
| ktn_mid_bfq | float | Y | 肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10 |
| ktn_mid_hfq | float | Y | 肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10 |
| ktn_mid_qfq | float | Y | 肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10 |
| ktn_upper_bfq | float | Y | 肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10 |
| ktn_upper_hfq | float | Y | 肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10 |
| ktn_upper_qfq | float | Y | 肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10 |
| lowdays | float | Y | LOWRANGE(LOW)表示当前最低价是近多少周期内最低价的最小值 |
| topdays | float | Y | TOPRANGE(HIGH)表示当前最高价是近多少周期内最高价的最大值 |
| ma_bfq_10 | float | Y | 简单移动平均-N=10 |
| ma_bfq_20 | float | Y | 简单移动平均-N=20 |
| ma_bfq_250 | float | Y | 简单移动平均-N=250 |
| ma_bfq_30 | float | Y | 简单移动平均-N=30 |
| ma_bfq_5 | float | Y | 简单移动平均-N=5 |
| ma_bfq_60 | float | Y | 简单移动平均-N=60 |
| ma_bfq_90 | float | Y | 简单移动平均-N=90 |
| ma_hfq_10 | float | Y | 简单移动平均-N=10 |
| ma_hfq_20 | float | Y | 简单移动平均-N=20 |
| ma_hfq_250 | float | Y | 简单移动平均-N=250 |
| ma_hfq_30 | float | Y | 简单移动平均-N=30 |
| ma_hfq_5 | float | Y | 简单移动平均-N=5 |
| ma_hfq_60 | float | Y | 简单移动平均-N=60 |
| ma_hfq_90 | float | Y | 简单移动平均-N=90 |
| ma_qfq_10 | float | Y | 简单移动平均-N=10 |
| ma_qfq_20 | float | Y | 简单移动平均-N=20 |
| ma_qfq_250 | float | Y | 简单移动平均-N=250 |
| ma_qfq_30 | float | Y | 简单移动平均-N=30 |
| ma_qfq_5 | float | Y | 简单移动平均-N=5 |
| ma_qfq_60 | float | Y | 简单移动平均-N=60 |
| ma_qfq_90 | float | Y | 简单移动平均-N=90 |
| macd_bfq | float | Y | MACD指标-CLOSE, SHORT=12, LONG=26, M=9 |
| macd_hfq | float | Y | MACD指标-CLOSE, SHORT=12, LONG=26, M=9 |
| macd_qfq | float | Y | MACD指标-CLOSE, SHORT=12, LONG=26, M=9 |
| macd_dea_bfq | float | Y | MACD指标-CLOSE, SHORT=12, LONG=26, M=9 |
| macd_dea_hfq | float | Y | MACD指标-CLOSE, SHORT=12, LONG=26, M=9 |
| macd_dea_qfq | float | Y | MACD指标-CLOSE, SHORT=12, LONG=26, M=9 |
| macd_dif_bfq | float | Y | MACD指标-CLOSE, SHORT=12, LONG=26, M=9 |
| macd_dif_hfq | float | Y | MACD指标-CLOSE, SHORT=12, LONG=26, M=9 |
| macd_dif_qfq | float | Y | MACD指标-CLOSE, SHORT=12, LONG=26, M=9 |
| mass_bfq | float | Y | 梅斯线-HIGH, LOW, N1=9, N2=25, M=6 |
| mass_hfq | float | Y | 梅斯线-HIGH, LOW, N1=9, N2=25, M=6 |
| mass_qfq | float | Y | 梅斯线-HIGH, LOW, N1=9, N2=25, M=6 |
| ma_mass_bfq | float | Y | 梅斯线-HIGH, LOW, N1=9, N2=25, M=6 |
| ma_mass_hfq | float | Y | 梅斯线-HIGH, LOW, N1=9, N2=25, M=6 |
| ma_mass_qfq | float | Y | 梅斯线-HIGH, LOW, N1=9, N2=25, M=6 |
| mfi_bfq | float | Y | MFI指标是成交量的RSI指标-CLOSE, HIGH, LOW, VOL, N=14 |
| mfi_hfq | float | Y | MFI指标是成交量的RSI指标-CLOSE, HIGH, LOW, VOL, N=14 |
| mfi_qfq | float | Y | MFI指标是成交量的RSI指标-CLOSE, HIGH, LOW, VOL, N=14 |
| mtm_bfq | float | Y | 动量指标-CLOSE, N=12, M=6 |
| mtm_hfq | float | Y | 动量指标-CLOSE, N=12, M=6 |
| mtm_qfq | float | Y | 动量指标-CLOSE, N=12, M=6 |
| mtmma_bfq | float | Y | 动量指标-CLOSE, N=12, M=6 |
| mtmma_hfq | float | Y | 动量指标-CLOSE, N=12, M=6 |
| mtmma_qfq | float | Y | 动量指标-CLOSE, N=12, M=6 |
| obv_bfq | float | Y | 能量潮指标-CLOSE, VOL |
| obv_hfq | float | Y | 能量潮指标-CLOSE, VOL |
| obv_qfq | float | Y | 能量潮指标-CLOSE, VOL |
| psy_bfq | float | Y | 投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6 |
| psy_hfq | float | Y | 投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6 |
| psy_qfq | float | Y | 投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6 |
| psyma_bfq | float | Y | 投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6 |
| psyma_hfq | float | Y | 投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6 |
| psyma_qfq | float | Y | 投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6 |
| roc_bfq | float | Y | 变动率指标-CLOSE, N=12, M=6 |
| roc_hfq | float | Y | 变动率指标-CLOSE, N=12, M=6 |
| roc_qfq | float | Y | 变动率指标-CLOSE, N=12, M=6 |
| maroc_bfq | float | Y | 变动率指标-CLOSE, N=12, M=6 |
| maroc_hfq | float | Y | 变动率指标-CLOSE, N=12, M=6 |
| maroc_qfq | float | Y | 变动率指标-CLOSE, N=12, M=6 |
| rsi_bfq_12 | float | Y | RSI指标-CLOSE, N=12 |
| rsi_bfq_24 | float | Y | RSI指标-CLOSE, N=24 |
| rsi_bfq_6 | float | Y | RSI指标-CLOSE, N=6 |
| rsi_hfq_12 | float | Y | RSI指标-CLOSE, N=12 |
| rsi_hfq_24 | float | Y | RSI指标-CLOSE, N=24 |
| rsi_hfq_6 | float | Y | RSI指标-CLOSE, N=6 |
| rsi_qfq_12 | float | Y | RSI指标-CLOSE, N=12 |
| rsi_qfq_24 | float | Y | RSI指标-CLOSE, N=24 |
| rsi_qfq_6 | float | Y | RSI指标-CLOSE, N=6 |
| taq_down_bfq | float | Y | 唐安奇通道(海龟)交易指标-HIGH, LOW, 20 |
| taq_down_hfq | float | Y | 唐安奇通道(海龟)交易指标-HIGH, LOW, 20 |
| taq_down_qfq | float | Y | 唐安奇通道(海龟)交易指标-HIGH, LOW, 20 |
| taq_mid_bfq | float | Y | 唐安奇通道(海龟)交易指标-HIGH, LOW, 20 |
| taq_mid_hfq | float | Y | 唐安奇通道(海龟)交易指标-HIGH, LOW, 20 |
| taq_mid_qfq | float | Y | 唐安奇通道(海龟)交易指标-HIGH, LOW, 20 |
| taq_up_bfq | float | Y | 唐安奇通道(海龟)交易指标-HIGH, LOW, 20 |
| taq_up_hfq | float | Y | 唐安奇通道(海龟)交易指标-HIGH, LOW, 20 |
| taq_up_qfq | float | Y | 唐安奇通道(海龟)交易指标-HIGH, LOW, 20 |
| trix_bfq | float | Y | 三重指数平滑平均线-CLOSE, M1=12, M2=20 |
| trix_hfq | float | Y | 三重指数平滑平均线-CLOSE, M1=12, M2=20 |
| trix_qfq | float | Y | 三重指数平滑平均线-CLOSE, M1=12, M2=20 |
| trma_bfq | float | Y | 三重指数平滑平均线-CLOSE, M1=12, M2=20 |
| trma_hfq | float | Y | 三重指数平滑平均线-CLOSE, M1=12, M2=20 |
| trma_qfq | float | Y | 三重指数平滑平均线-CLOSE, M1=12, M2=20 |
| vr_bfq | float | Y | VR容量比率-CLOSE, VOL, M1=26 |
| vr_hfq | float | Y | VR容量比率-CLOSE, VOL, M1=26 |
| vr_qfq | float | Y | VR容量比率-CLOSE, VOL, M1=26 |
| wr_bfq | float | Y | W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6 |
| wr_hfq | float | Y | W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6 |
| wr_qfq | float | Y | W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6 |
| wr1_bfq | float | Y | W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6 |
| wr1_hfq | float | Y | W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6 |
| wr1_qfq | float | Y | W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6 |
| xsii_td1_bfq | float | Y | 薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7 |
| xsii_td1_hfq | float | Y | 薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7 |
| xsii_td1_qfq | float | Y | 薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7 |
| xsii_td2_bfq | float | Y | 薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7 |
| xsii_td2_hfq | float | Y | 薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7 |
| xsii_td2_qfq | float | Y | 薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7 |
| xsii_td3_bfq | float | Y | 薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7 |
| xsii_td3_hfq | float | Y | 薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7 |
| xsii_td3_qfq | float | Y | 薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7 |
| xsii_td4_bfq | float | Y | 薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7 |
| xsii_td4_hfq | float | Y | 薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7 |
| xsii_td4_qfq | float | Y | 薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7 |

接口用法
数据示例


---

### [295] 中央结算系统持股统计  ·  股票数据 / 特色数据
(api: ccass_hold | 输出字段: 6 | PIT字段: 否)

# (doc_id=295)  https://tushare.pro/document/2?doc_id=295

## 中央结算系统持股汇总
接口：ccass_hold 描述：获取中央结算系统持股汇总数据，覆盖全部历史数据，根据交易所披露时间，当日数据在下一交易日早上9点前完成入库 限量：单次最大5000条数据，可循环或分页提供全部 积分：用户120积分可以试用看数据，5000积分每分钟可以请求300次，8000积分以上可以请求500次每分钟，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码 (e.g. 605009.SH) |
| hk_code | str | N | 港交所代码 （e.g. 95009） |
| trade_date | str | N | 交易日期(YYYYMMDD格式，下同) |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 交易日期 |
| ts_code | str | Y | 股票代号 |
| name | str | Y | 股票名称 |
| shareholding | str | Y | 于中央结算系统的持股量(股) Shareholding in CCASS |
| hold_nums | str | Y | 参与者数目（个） |
| hold_ratio | str | Y | 占于上交所上市及交易的A股总数的百分比（%） % of the total number of A shares listed and traded on the SSE |

Note:
The total number of A shares listed and traded on the SSE of the relevant SSE-listed company used for calculating the percentage of shareholding may not have taken into account any change in connection with or as a result of any corporate actions of the relevant company and hence, may not be up-to-date. The percentage of shareholding is for reference only.
The total number of A shares listed and traded on the SSE of the relevant SSE-listed company used for calculating the percentage of shareholding may not be equal to the actual total number of issued shares of that company.
接口用法
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：ccass_hold 描述：获取中央结算系统持股汇总数据，覆盖全部历史数据，根据交易所披露时间，当日数据在下一交易日早上9点前完成入库 限量：单次最大5000条数据，可循环或分页提供全部 积分：用户120积分可以试用看数据，5000积分每分钟可以请求300次，8000积分以上可以请求500次每分钟，具体请参阅 积分获取办法


---

### [274] 中央结算系统持股明细  ·  股票数据 / 特色数据
(api: ccass_hold_detail | 输出字段: 7 | PIT字段: 否)

# (doc_id=274)  https://tushare.pro/document/2?doc_id=274

## 中央结算系统持股明细
接口：ccass_hold_detail 描述：获取中央结算系统机构席位持股明细，数据覆盖 全历史 ，根据交易所披露时间，当日数据在下一交易日早上9点前完成 限量：单次最大返回6000条数据，可以循环或分页提取 积分：用户积8000积分可调取，每分钟可以请求300次
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码 (e.g. 605009.SH) |
| hk_code | str | N | 港交所代码 （e.g. 95009） |
| trade_date | str | N | 交易日期(YYYYMMDD格式，下同) |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 交易日期 |
| ts_code | str | Y | 股票代号 |
| name | str | Y | 股票名称 |
| col_participant_id | str | Y | 参与者编号 |
| col_participant_name | str | Y | 机构名称 |
| col_shareholding | str | Y | 持股量(股) |
| col_shareholding_percent | str | Y | 占已发行股份/权证/单位百分比(%) |

接口用法
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：ccass_hold_detail 描述：获取中央结算系统机构席位持股明细，数据覆盖 全历史 ，根据交易所披露时间，当日数据在下一交易日早上9点前完成 限量：单次最大返回6000条数据，可以循环或分页提取 积分：用户积8000积分可调取，每分钟可以请求300次


---

### [188] 沪深股通持股明细  ·  股票数据 / 特色数据
(api: hk_hold | 输出字段: 7 | PIT字段: 否)

# (doc_id=188)  https://tushare.pro/document/2?doc_id=188

## 沪深港股通持股明细
接口：hk_hold，可以通过 数据工具 调试和查看数据。 描述：获取沪深港股通持股明细，数据来源港交所。 限量：单次最多提取3800条记录，可循环调取，总量不限制 积分：用户积120积分可调取试用，2000积分可正常使用，单位分钟有流控，积分越高流量越大，请自行提高积分，具体请参阅 积分获取办法
说明：交易所于从2024年8月20开始停止发布日度北向资金数据，改为季度披露
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| code | str | N | 交易所代码 |
| ts_code | str | N | TS股票代码 |
| trade_date | str | N | 交易日期 |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |
| exchange | str | N | 类型：SH沪股通（北向）SZ深股通（北向）HK港股通（南向持股） |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| code | str | Y | 原始代码 |
| trade_date | str | Y | 交易日期 |
| ts_code | str | Y | TS代码 |
| name | str | Y | 股票名称 |
| vol | int | Y | 持股数量(股) |
| ratio | float | Y | 持股占比（%），占已发行股份百分比 |
| exchange | str | Y | 类型：SH沪股通SZ深股通HK港股通 |

接口示例
数据示例

## [PIT / 更新口径 — 自动标记]
- (正文) 说明：交易所于从2024年8月20开始停止发布日度北向资金数据，改为季度披露


---

### [353] 股票开盘集合竞价数据  ·  股票数据 / 特色数据
(api: stk_auction_o | 输出字段: 9 | PIT字段: 否)

# (doc_id=353)  https://tushare.pro/document/2?doc_id=353

## 股票开盘集合竞价数据
接口：stk_auction_o 描述：股票开盘9:30集合竞价数据，每天盘后更新 限量：单次请求最大返回10000行数据，可根据日期循环 权限：本接口是单独开权限的数据，具体参考 权限说明
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码 |
| trade_date | str | N | 交易日期(YYYYMMDD) |
| start_date | str | N | 开始日期(YYYYMMDD) |
| end_date | str | N | 结束日期(YYYYMMDD) |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| trade_date | str | Y | 交易日期 |
| close | float | Y | 开盘集合竞价收盘价 |
| open | float | Y | 开盘集合竞价开盘价 |
| high | float | Y | 开盘集合竞价最高价 |
| low | float | Y | 开盘集合竞价最低价 |
| vol | float | Y | 开盘集合竞价成交量 |
| amount | float | Y | 开盘集合竞价成交额 |
| vwap | float | Y | 开盘集合竞价均价 |

接口用法
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：stk_auction_o 描述：股票开盘9:30集合竞价数据，每天盘后更新 限量：单次请求最大返回10000行数据，可根据日期循环 权限：本接口是单独开权限的数据，具体参考 权限说明


---

### [354] 股票收盘集合竞价数据  ·  股票数据 / 特色数据
(api: stk_auction_c | 输出字段: 9 | PIT字段: 否)

# (doc_id=354)  https://tushare.pro/document/2?doc_id=354

## 股票收盘集合竞价数据
接口：stk_auction_c 描述：股票收盘15:00集合竞价数据，每天盘后更新 限量：单次请求最大返回10000行数据，可根据日期循环 权限：本接口是单独开权限的数据，具体参考 权限说明
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码 |
| trade_date | str | N | 交易日期(YYYYMMDD) |
| start_date | str | N | 开始日期(YYYYMMDD) |
| end_date | str | N | 结束日期(YYYYMMDD) |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| trade_date | str | Y | 交易日期 |
| close | float | Y | 收盘集合竞价收盘价 |
| open | float | Y | 收盘集合竞价开盘价 |
| high | float | Y | 收盘集合竞价最高价 |
| low | float | Y | 收盘集合竞价最低价 |
| vol | float | Y | 收盘集合竞价成交量 |
| amount | float | Y | 收盘集合竞价成交额 |
| vwap | float | Y | 收盘集合竞价均价 |

接口用法
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：stk_auction_c 描述：股票收盘15:00集合竞价数据，每天盘后更新 限量：单次请求最大返回10000行数据，可根据日期循环 权限：本接口是单独开权限的数据，具体参考 权限说明


---

### [364] 神奇九转指标  ·  股票数据 / 特色数据
(api: stk_nineturn | 输出字段: 13 | PIT字段: 否)

# (doc_id=364)  https://tushare.pro/document/2?doc_id=364

## 神奇九转指标
接口：stk_nineturn（由于涉及分钟数据每天21点更新） 描述：神奇九转（又称“九转序列”）是一种基于技术分析的股票趋势反转指标，其思想来源于技术分析大师汤姆·迪马克（Tom DeMark）的TD序列。该指标的核心功能是通过识别股价在上涨或下跌过程中连续9天的特定走势，来判断股价的潜在反转点，从而帮助投资者提高抄底和逃顶的成功率，日线级别配合60min的九转效果更好，数据从20230101开始。 限量：单次提取最大返回10000行数据，可通过股票代码和日期循环获取全部数据 权限：达到6000积分可以调用
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码 |
| trade_date | str | N | 交易日期 （格式：YYYY-MM-DD HH:MM:SS) |
| freq | str | N | 频率(日daily) |
| start_date | str | N | 开始时间 |
| end_date | str | N | 结束时间 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| trade_date | datetime | Y | 交易日期 |
| freq | str | Y | 频率(日daily) |
| open | float | Y | 开盘价 |
| high | float | Y | 最高价 |
| low | float | Y | 最低价 |
| close | float | Y | 收盘价 |
| vol | float | Y | 成交量 |
| amount | float | Y | 成交额 |
| up_count | float | Y | 上九转计数 |
| down_count | float | Y | 下九转计数 |
| nine_up_turn | str | Y | 是否上九转)+9表示上九转 |
| nine_down_turn | str | Y | 是否下九转-9表示下九转 |

接口用法
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：stk_nineturn（由于涉及分钟数据每天21点更新） 描述：神奇九转（又称“九转序列”）是一种基于技术分析的股票趋势反转指标，其思想来源于技术分析大师汤姆·迪马克（Tom DeMark）的TD序列。该指标的核心功能是通过识别股价在上涨或下跌过程中连续9天的特定走势，来判断股价的潜在反转点，从而帮助投资者提高抄底和逃顶的成功率，日线级别配合60min的九转效果更好，数据从20230101开始。 限量：单次提取最大返回10000行数据，可通过股票代码和日期循环获取全部数据 权限：达到6000积分可以调用


---

### [399] AH股比价  ·  股票数据 / 特色数据
(api: stk_ah_comparison | 输出字段: 11 | PIT字段: 否)

# (doc_id=399)  https://tushare.pro/document/2?doc_id=399

## AH股比价
接口：stk_ah_comparison，可以通过 数据工具 调试和查看数据。 描述：AH股比价数据，可根据交易日期获取历史 权限：5000积分起 提示：每天盘后17:00更新，单次请求最大返回1000行数据，可循环提取,本接口数据从20250812开始，由于历史不好补充，只能累积
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| hk_code | str | N | 港股股票代码（xxxxx.HK) |
| ts_code | str | N | A股票代码(xxxxxx.SH/SZ/BJ) |
| trade_date | str | N | 交易日期（格式：YYYYMMDD下同） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| hk_code | str | Y | 港股股票代码 |
| ts_code | str | Y | A股股票代码 |
| trade_date | str | Y | 交易日期 |
| hk_name | str | Y | 港股股票名称 |
| hk_pct_chg | float | Y | 港股股票涨跌幅 |
| hk_close | float | Y | 港股股票收盘价 |
| name | str | Y | A股股票名称 |
| close | float | Y | A股股票收盘价 |
| pct_chg | float | Y | A股股票涨跌幅 |
| ah_comparison | float | Y | 比价(A/H) |
| ah_premium | float | Y | 溢价(A/H)% |

接口用法
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：stk_ah_comparison，可以通过 数据工具 调试和查看数据。 描述：AH股比价数据，可根据交易日期获取历史 权限：5000积分起 提示：每天盘后17:00更新，单次请求最大返回1000行数据，可循环提取,本接口数据从20250812开始，由于历史不好补充，只能累积


---

### [275] 机构调研数据  ·  股票数据 / 特色数据
(api: stk_surv | 输出字段: 10 | PIT字段: 否)

# (doc_id=275)  https://tushare.pro/document/2?doc_id=275

## 机构调研表
接口：stk_surv 描述：获取上市公司机构调研记录数据 限量：单次最大获取100条数据，可循环或分页提取 积分：用户积5000积分可使用
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码 |
| trade_date | str | N | 调研日期 |
| start_date | str | N | 调研开始日期 |
| end_date | str | N | 调研结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| name | str | Y | 股票名称 |
| surv_date | str | Y | 调研日期 |
| fund_visitors | str | Y | 机构参与人员 |
| rece_place | str | Y | 接待地点 |
| rece_mode | str | Y | 接待方式 |
| rece_org | str | Y | 接待的公司 |
| org_type | str | Y | 接待公司类型 |
| comp_rece | str | Y | 上市公司接待人员 |
| content | None | N | 调研内容 |

接口用法
数据样例


---

### [267] 券商月度金股  ·  股票数据 / 特色数据
(api: broker_recommend | 输出字段: 4 | PIT字段: 否)

# (doc_id=267)  https://tushare.pro/document/2?doc_id=267

## 券商每月荐股
接口：broker_recommend 描述：获取券商月度金股，一般1日~3日内更新当月数据 限量：单次最大1000行数据，可循环提取 积分：积分达到6000即可调用，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| month | str | Y | 月度（YYYYMM） |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| month | str | Y | 月度 |
| broker | str | Y | 券商 |
| ts_code | str | Y | 股票代码 |
| name | str | Y | 股票简称 |

接口示例
数据示例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：broker_recommend 描述：获取券商月度金股，一般1日~3日内更新当月数据 限量：单次最大1000行数据，可循环提取 积分：积分达到6000即可调用，具体请参阅 积分获取办法


---

### [330] 两融及转融通  ·  股票数据
(api: — | 输出字段: 0 | PIT字段: 否)

# (doc_id=330)  https://tushare.pro/document/2?doc_id=330


---

### [58] 融资融券交易汇总  ·  股票数据 / 两融及转融通
(api: margin | 输出字段: 9 | PIT字段: 否)

# (doc_id=58)  https://tushare.pro/document/2?doc_id=58

## 融资融券交易汇总
接口：margin 描述：获取融资融券每日交易汇总数据 限量：单次请求最大返回4000行数据，可根据日期循环 权限：2000积分可获得本接口权限，积分越高权限越大，具体参考 权限说明
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | N | 交易日期（格式：YYYYMMDD，下同） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |
| exchange_id | str | N | 交易所代码（SSE上交所SZSE深交所BSE北交所） |

输出参数
| 名称 | 类型 | 描述 |
| --- | --- | --- |
| trade_date | str | 交易日期 |
| exchange_id | str | 交易所代码（SSE上交所SZSE深交所BSE北交所） |
| rzye | float | 融资余额(元) |
| rzmre | float | 融资买入额(元) |
| rzche | float | 融资偿还额(元) |
| rqye | float | 融券余额(元) |
| rqmcl | float | 融券卖出量(股,份,手) |
| rzrqye | float | 融资融券余额(元) |
| rqyl | float | 融券余量(股,份,手) |

接口使用
或者
数据样例
说明 融资融券数据从证券交易所网站直接获取，提供了有记录以来的全部汇总和明细数据。 根据交所网站提示：数据根据券商申报的数据汇总，由券商保证数据的真实、完整、准确。
其中： 本日融资余额(元)=前日融资余额＋本日融资买入-本日融资偿还额 本日融券余量(股)=前日融券余量＋本日融券卖出量-本日融券买入量-本日现券偿还量 本日融券余额(元)=本日融券余量×本日收盘价 本日融资融券余额(元)=本日融资余额＋本日融券余额
2014年9月22日起，“融资融券交易总量”数据包含调出标的证券名单的证券的融资融券余额


---

### [59] 融资融券交易明细  ·  股票数据 / 两融及转融通
(api: margin_detail | 输出字段: 11 | PIT字段: 否)

# (doc_id=59)  https://tushare.pro/document/2?doc_id=59

## 融资融券交易明细
接口：margin_detail 描述：获取沪深两市每日融资融券明细 限量：单次请求最大返回6000行数据，可根据日期循环 权限：2000积分可获得本接口权限，积分越高权限越大，具体参考 权限说明
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | N | 交易日期（格式：YYYYMMDD，下同） |
| ts_code | str | N | TS代码 |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 描述 |
| --- | --- | --- |
| trade_date | str | 交易日期 |
| ts_code | str | TS股票代码 |
| name | str | 股票名称 （20190910后有数据） |
| rzye | float | 融资余额(元) |
| rqye | float | 融券余额(元) |
| rzmre | float | 融资买入额(元) |
| rqyl | float | 融券余量（股） |
| rzche | float | 融资偿还额(元) |
| rqchl | float | 融券偿还量(股) |
| rqmcl | float | 融券卖出量(股,份,手) |
| rzrqye | float | 融资融券余额(元) |

接口使用
或者
数据样例
说明
本报表基于证券公司报送的融资融券余额数据汇总生成，其中： 本日融资余额(元)=前日融资余额＋本日融资买入-本日融资偿还额 本日融券余量(股)=前日融券余量＋本日融券卖出量-本日融券买入量-本日现券偿还量 本日融券余额(元)=本日融券余量×本日收盘价 本日融资融券余额(元)=本日融资余额＋本日融券余额
单位说明：股（标的证券为股票）、份（标的证券为基金）、手（标的证券为债券）。
2014年9月22日起，“融资融券交易总量”数据包含调出标的证券名单的证券的融资融券余额。


---

### [326] 融资融券标的（盘前）  ·  股票数据 / 两融及转融通
(api: margin_secs | 输出字段: 4 | PIT字段: 否)

# (doc_id=326)  https://tushare.pro/document/2?doc_id=326

## 融资融券标的（盘前更新）
接口：margin_secs 描述：获取沪深京三大交易所融资融券标的（包括ETF），每天盘前更新 限量：单次最大6000行数据，可根据股票代码、交易日期、交易所代码循环提取 积分：2000积分可调取，5000积分无总量限制，积分越高权限越大，具体参考 权限说明
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 标的代码 |
| trade_date | str | N | 交易日 |
| exchange | str | N | 交易所（SSE上交所 SZSE深交所 BSE北交所） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 交易日期 |
| ts_code | str | Y | 标的代码 |
| name | str | Y | 标的名称 |
| exchange | str | Y | 交易所 |

接口用法
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：margin_secs 描述：获取沪深京三大交易所融资融券标的（包括ETF），每天盘前更新 限量：单次最大6000行数据，可根据股票代码、交易日期、交易所代码循环提取 积分：2000积分可调取，5000积分无总量限制，积分越高权限越大，具体参考 权限说明


---

### [332] 转融券交易汇总(停）  ·  股票数据 / 两融及转融通
(api: slb_sec | 输出字段: 7 | PIT字段: 否)

# (doc_id=332)  https://tushare.pro/document/2?doc_id=332

## 转融券交易汇总
接口：slb_sec 描述：转融通转融券交易汇总 限量：单次最大可以提取5000行数据，可循环获取所有历史 积分：2000积分每分钟请求200次，5000积分500次请求
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | N | 交易日期（YYYYMMDD格式，下同） |
| ts_code | str | N | 股票代码 |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 交易日期（YYYYMMDD） |
| ts_code | str | Y | 股票代码 |
| name | str | Y | 股票名称 |
| ope_inv | float | Y | 期初余量(万股) |
| lent_qnt | float | Y | 转融券融出数量(万股) |
| cls_inv | float | Y | 期末余量(万股) |
| end_bal | float | Y | 期末余额(万元) |

接口示例
数据示例


---

### [331] 转融资交易汇总  ·  股票数据 / 两融及转融通
(api: slb_len | 输出字段: 6 | PIT字段: 否)

# (doc_id=331)  https://tushare.pro/document/2?doc_id=331

## 转融资交易汇总
接口：slb_len 描述：转融通融资汇总 限量：单次最大可以提取5000行数据，可循环获取所有历史 积分：2000积分每分钟请求200次，5000积分500次请求
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | N | 交易日期（YYYYMMDD格式，下同） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 交易日期 |
| ob | float | Y | 期初余额(亿元) |
| auc_amount | float | Y | 竞价成交金额(亿元) |
| repo_amount | float | Y | 再借成交金额(亿元) |
| repay_amount | float | Y | 偿还金额(亿元) |
| cb | float | Y | 期末余额(亿元) |

接口示例
数据示例


---

### [333] 转融券交易明细(停）  ·  股票数据 / 两融及转融通
(api: slb_sec_detail | 输出字段: 6 | PIT字段: 否)

# (doc_id=333)  https://tushare.pro/document/2?doc_id=333

## 转融券交易明细
接口：slb_sec_detail 描述：转融券交易明细 限量：单次最大可以提取5000行数据，可循环获取所有历史 积分：2000积分每分钟请求200次，5000积分500次请求
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | N | 交易日期（YYYYMMDD格式，下同） |
| ts_code | str | N | 股票代码 |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 交易日期（YYYYMMDD） |
| ts_code | str | Y | 股票代码 |
| name | str | Y | 股票名称 |
| tenor | str | Y | 期 限(天) |
| fee_rate | float | Y | 融出费率(%) |
| lent_qnt | float | Y | 转融券融出数量(万股) |

接口示例
数据示例


---

### [334] 做市借券交易汇总(停）  ·  股票数据 / 两融及转融通
(api: slb_len_mm | 输出字段: 7 | PIT字段: 否)

# (doc_id=334)  https://tushare.pro/document/2?doc_id=334

## 做市借券交易汇总
接口：slb_len_mm 描述：做市借券交易汇总 限量：单次最大可以提取5000行数据，可循环获取所有历史 积分：2000积分每分钟请求200次，5000积分500次请求
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | N | 交易日期（YYYYMMDD格式，下同） |
| ts_code | str | N | 股票代码 |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 交易日期（YYYYMMDD） |
| ts_code | str | Y | 股票代码 |
| name | str | Y | 股票名称 |
| ope_inv | float | Y | 期初余量(万股) |
| lent_qnt | float | Y | 融出数量(万股) |
| cls_inv | float | Y | 期末余量(万股) |
| end_bal | float | Y | 期末余额(万元) |

接口示例
数据示例


---

### [342] 资金流向数据  ·  股票数据
(api: — | 输出字段: 0 | PIT字段: 否)

# (doc_id=342)  https://tushare.pro/document/2?doc_id=342


---

### [170] 个股资金流向  ·  股票数据 / 资金流向数据
(api: moneyflow | 输出字段: 20 | PIT字段: 否)

# (doc_id=170)  https://tushare.pro/document/2?doc_id=170

## 个股资金流向
接口：moneyflow，可以通过 数据工具 调试和查看数据。 描述：获取沪深A股票资金流向数据，分析大单小单成交情况，用于判别资金动向，数据开始于2010年。 限量：单次最大提取6000行记录，总量不限制 积分：用户需要至少2000积分才可以调取，基础积分有流量控制，积分越多权限越大，请自行提高积分，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码 （股票和时间参数至少输入一个） |
| trade_date | str | N | 交易日期 |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS代码 |
| trade_date | str | Y | 交易日期 |
| buy_sm_vol | int | Y | 小单买入量（手） |
| buy_sm_amount | float | Y | 小单买入金额（万元） |
| sell_sm_vol | int | Y | 小单卖出量（手） |
| sell_sm_amount | float | Y | 小单卖出金额（万元） |
| buy_md_vol | int | Y | 中单买入量（手） |
| buy_md_amount | float | Y | 中单买入金额（万元） |
| sell_md_vol | int | Y | 中单卖出量（手） |
| sell_md_amount | float | Y | 中单卖出金额（万元） |
| buy_lg_vol | int | Y | 大单买入量（手） |
| buy_lg_amount | float | Y | 大单买入金额（万元） |
| sell_lg_vol | int | Y | 大单卖出量（手） |
| sell_lg_amount | float | Y | 大单卖出金额（万元） |
| buy_elg_vol | int | Y | 特大单买入量（手） |
| buy_elg_amount | float | Y | 特大单买入金额（万元） |
| sell_elg_vol | int | Y | 特大单卖出量（手） |
| sell_elg_amount | float | Y | 特大单卖出金额（万元） |
| net_mf_vol | int | Y | 净流入量（手） |
| net_mf_amount | float | Y | 净流入额（万元） |

各类别统计规则如下： 小单 ：5万以下 中单 ：5万～20万 大单 ：20万～100万 特大单 ：成交额>=100万 ，数据基于主动买卖单统计
接口示例
数据示例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：moneyflow，可以通过 数据工具 调试和查看数据。 描述：获取沪深A股票资金流向数据，分析大单小单成交情况，用于判别资金动向，数据开始于2010年。 限量：单次最大提取6000行记录，总量不限制 积分：用户需要至少2000积分才可以调取，基础积分有流量控制，积分越多权限越大，请自行提高积分，具体请参阅 积分获取办法


---

### [348] 个股资金流向（THS）  ·  股票数据 / 资金流向数据
(api: moneyflow_ths | 输出字段: 13 | PIT字段: 否)

# (doc_id=348)  https://tushare.pro/document/2?doc_id=348

## 个股资金流向（THS）
接口：moneyflow_ths 描述：获取同花顺个股资金流向数据，每日盘后更新 限量：单次最大6000，可根据日期或股票代码循环提取数据 积分：6000积分可调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码 |
| trade_date | str | N | 交易日期（YYYYMMDD格式，下同） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 交易日期 |
| ts_code | str | Y | 股票代码 |
| name | str | Y | 股票名称 |
| pct_change | float | Y | 涨跌幅 |
| latest | float | Y | 最新价 |
| net_amount | float | Y | 资金净流入(万元) |
| net_d5_amount | float | Y | 5日主力净额(万元) |
| buy_lg_amount | float | Y | 今日大单净流入额(万元) |
| buy_lg_amount_rate | float | Y | 今日大单净流入占比(%) |
| buy_md_amount | float | Y | 今日中单净流入额(万元) |
| buy_md_amount_rate | float | Y | 今日中单净流入占比(%) |
| buy_sm_amount | float | Y | 今日小单净流入额(万元) |
| buy_sm_amount_rate | float | Y | 今日小单净流入占比(%) |

接口示例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：moneyflow_ths 描述：获取同花顺个股资金流向数据，每日盘后更新 限量：单次最大6000，可根据日期或股票代码循环提取数据 积分：6000积分可调取，具体请参阅 积分获取办法


---

### [349] 个股资金流向（DC）  ·  股票数据 / 资金流向数据
(api: moneyflow_dc | 输出字段: 15 | PIT字段: 否)

# (doc_id=349)  https://tushare.pro/document/2?doc_id=349

## 个股资金流向（DC）
接口：moneyflow_dc 描述：获取东方财富个股资金流向数据，每日盘后更新，数据开始于20230911 限量：单次最大获取6000条数据，可根据日期或股票代码循环提取数据 积分：用户需要至少5000积分才可以调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码 |
| trade_date | str | N | 交易日期（YYYYMMDD格式，下同） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 交易日期 |
| ts_code | str | Y | 股票代码 |
| name | str | Y | 股票名称 |
| pct_change | float | Y | 涨跌幅 |
| close | float | Y | 最新价 |
| net_amount | float | Y | 今日主力净流入额（万元） |
| net_amount_rate | float | Y | 今日主力净流入净占比（%） |
| buy_elg_amount | float | Y | 今日超大单净流入额（万元） |
| buy_elg_amount_rate | float | Y | 今日超大单净流入占比（%） |
| buy_lg_amount | float | Y | 今日大单净流入额（万元） |
| buy_lg_amount_rate | float | Y | 今日大单净流入占比（%） |
| buy_md_amount | float | Y | 今日中单净流入额（万元） |
| buy_md_amount_rate | float | Y | 今日中单净流入占比（%） |
| buy_sm_amount | float | Y | 今日小单净流入额（万元） |
| buy_sm_amount_rate | float | Y | 今日小单净流入占比（%） |

接口示例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：moneyflow_dc 描述：获取东方财富个股资金流向数据，每日盘后更新，数据开始于20230911 限量：单次最大获取6000条数据，可根据日期或股票代码循环提取数据 积分：用户需要至少5000积分才可以调取，具体请参阅 积分获取办法


---

### [371] 板块资金流向（THS)  ·  股票数据 / 资金流向数据
(api: moneyflow_cnt_ths | 输出字段: 12 | PIT字段: 否)

# (doc_id=371)  https://tushare.pro/document/2?doc_id=371

## 同花顺概念板块资金流向（THS）
接口：moneyflow_cnt_ths 描述：获取同花顺概念板块每日资金流向 限量：单次最大可调取5000条数据，可以根据日期和代码循环提取全部数据 积分：6000积分可以调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 板块代码 |
| trade_date | str | N | 交易日期(格式：YYYYMMDD，下同) |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 交易日期 |
| ts_code | str | Y | 板块代码 |
| name | str | Y | 板块名称 |
| lead_stock | str | Y | 领涨股票名称 |
| close_price | float | Y | 最新价 |
| pct_change | float | Y | 行业涨跌幅 |
| industry_index | float | Y | 板块指数点位 |
| company_num | int | Y | 公司数量 |
| pct_change_stock | float | Y | 领涨股涨跌幅 |
| net_buy_amount | float | Y | 流入资金(亿元) |
| net_sell_amount | float | Y | 流出资金(亿元) |
| net_amount | float | Y | 净额(亿元) |

接口示例
数据示例


---

### [343] 行业资金流向（THS）  ·  股票数据 / 资金流向数据
(api: moneyflow_ind_ths | 输出字段: 12 | PIT字段: 否)

# (doc_id=343)  https://tushare.pro/document/2?doc_id=343

## 同花顺行业资金流向（THS）
接口：moneyflow_ind_ths 描述：获取同花顺行业资金流向，每日盘后更新 限量：单次最大可调取5000条数据，可以根据日期和代码循环提取全部数据 积分：6000积分可以调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 代码 |
| trade_date | str | N | 交易日期(YYYYMMDD格式，下同) |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 交易日期 |
| ts_code | str | Y | 板块代码 |
| industry | str | Y | 板块名称 |
| lead_stock | str | Y | 领涨股票名称 |
| close | float | Y | 收盘指数 |
| pct_change | float | Y | 指数涨跌幅 |
| company_num | int | Y | 公司数量 |
| pct_change_stock | float | Y | 领涨股涨跌幅 |
| close_price | float | Y | 领涨股最新价 |
| net_buy_amount | float | Y | 流入资金(亿元) |
| net_sell_amount | float | Y | 流出资金(亿元) |
| net_amount | float | Y | 净额(亿元) |

接口示例
数据示例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：moneyflow_ind_ths 描述：获取同花顺行业资金流向，每日盘后更新 限量：单次最大可调取5000条数据，可以根据日期和代码循环提取全部数据 积分：6000积分可以调取，具体请参阅 积分获取办法


---

### [344] 板块资金流向（DC）  ·  股票数据 / 资金流向数据
(api: moneyflow_ind_dc | 输出字段: 18 | PIT字段: 否)

# (doc_id=344)  https://tushare.pro/document/2?doc_id=344

## 东财概念及行业板块资金流向（DC）
接口：moneyflow_ind_dc 描述：获取东方财富板块资金流向，每天盘后更新 限量：单次最大可调取5000条数据，可以根据日期和代码循环提取全部数据 积分：6000积分可以调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 代码 |
| trade_date | str | N | 交易日期（YYYYMMDD格式，下同） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |
| content_type | str | N | 资金类型(行业、概念、地域) |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 交易日期 |
| content_type | str | Y | 数据类型 |
| ts_code | str | Y | DC板块代码（行业、概念、地域） |
| name | str | Y | 板块名称 |
| pct_change | float | Y | 板块涨跌幅（%） |
| close | float | Y | 板块最新指数 |
| net_amount | float | Y | 今日主力净流入 净额（元） |
| net_amount_rate | float | Y | 今日主力净流入净占比% |
| buy_elg_amount | float | Y | 今日超大单净流入 净额（元） |
| buy_elg_amount_rate | float | Y | 今日超大单净流入 净占比% |
| buy_lg_amount | float | Y | 今日大单净流入 净额（元） |
| buy_lg_amount_rate | float | Y | 今日大单净流入 净占比% |
| buy_md_amount | float | Y | 今日中单净流入 净额（元） |
| buy_md_amount_rate | float | Y | 今日中单净流入 净占比% |
| buy_sm_amount | float | Y | 今日小单净流入 净额（元） |
| buy_sm_amount_rate | float | Y | 今日小单净流入 净占比% |
| buy_sm_amount_stock | str | Y | 今日主力净流入最大股 |
| rank | int | Y | 序号 |

接口示例
数据示例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：moneyflow_ind_dc 描述：获取东方财富板块资金流向，每天盘后更新 限量：单次最大可调取5000条数据，可以根据日期和代码循环提取全部数据 积分：6000积分可以调取，具体请参阅 积分获取办法


---

### [345] 大盘资金流向（DC）  ·  股票数据 / 资金流向数据
(api: moneyflow_mkt_dc | 输出字段: 15 | PIT字段: 否)

# (doc_id=345)  https://tushare.pro/document/2?doc_id=345

## 大盘资金流向（DC）
接口：moneyflow_mkt_dc 描述：获取东方财富大盘资金流向数据，每日盘后更新 限量：单次最大3000条，可根据日期或日期区间循环获取 积分：120积分可试用，6000积分可正式调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | N | 交易日期(YYYYMMDD格式，下同） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 交易日期 |
| close_sh | float | Y | 上证收盘价（点） |
| pct_change_sh | float | Y | 上证涨跌幅(%) |
| close_sz | float | Y | 深证收盘价（点） |
| pct_change_sz | float | Y | 深证涨跌幅(%) |
| net_amount | float | Y | 今日主力净流入 净额（元） |
| net_amount_rate | float | Y | 今日主力净流入净占比% |
| buy_elg_amount | float | Y | 今日超大单净流入 净额（元） |
| buy_elg_amount_rate | float | Y | 今日超大单净流入 净占比% |
| buy_lg_amount | float | Y | 今日大单净流入 净额（元） |
| buy_lg_amount_rate | float | Y | 今日大单净流入 净占比% |
| buy_md_amount | float | Y | 今日中单净流入 净额（元） |
| buy_md_amount_rate | float | Y | 今日中单净流入 净占比% |
| buy_sm_amount | float | Y | 今日小单净流入 净额（元） |
| buy_sm_amount_rate | float | Y | 今日小单净流入 净占比% |

接口示例
数据示例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：moneyflow_mkt_dc 描述：获取东方财富大盘资金流向数据，每日盘后更新 限量：单次最大3000条，可根据日期或日期区间循环获取 积分：120积分可试用，6000积分可正式调取，具体请参阅 积分获取办法


---

### [47] 沪深港通资金流向  ·  股票数据 / 资金流向数据
(api: moneyflow_hsgt | 输出字段: 7 | PIT字段: 否)

# (doc_id=47)  https://tushare.pro/document/2?doc_id=47

## 沪深港通资金流向
接口：moneyflow_hsgt，可以通过 数据工具 调试和查看数据。 描述：获取沪股通、深股通、港股通每日资金流向数据，每次最多返回300条记录，总量不限制。 积分要求：2000积分起，5000积分每分钟可提取500次
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | N | 交易日期 (二选一) |
| start_date | str | N | 开始日期 (二选一) |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 描述 |
| --- | --- | --- |
| trade_date | str | 交易日期 |
| ggt_ss | float | 港股通（上海） |
| ggt_sz | float | 港股通（深圳） |
| hgt | float | 沪股通（百万元） |
| sgt | float | 深股通（百万元） |
| north_money | float | 北向资金（百万元） |
| south_money | float | 南向资金（百万元） |

接口用法
或者
数据样例


---

### [346] 打板专题数据  ·  股票数据
(api: — | 输出字段: 0 | PIT字段: 否)

# (doc_id=346)  https://tushare.pro/document/2?doc_id=346


---

### [106] 龙虎榜每日统计单  ·  股票数据 / 打板专题数据
(api: top_list | 输出字段: 15 | PIT字段: 否)

# (doc_id=106)  https://tushare.pro/document/2?doc_id=106

## 龙虎榜每日明细
接口：top_list 描述：龙虎榜每日交易明细 数据历史： 2005年至今 限量：单次请求返回最大10000行数据，可通过参数循环获取全部历史 积分：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 交易日期 |
| ts_code | str | N | 股票代码 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 交易日期 |
| ts_code | str | Y | TS代码 |
| name | str | Y | 名称 |
| close | float | Y | 收盘价 |
| pct_change | float | Y | 涨跌幅 |
| turnover_rate | float | Y | 换手率 |
| amount | float | Y | 总成交额 |
| l_sell | float | Y | 龙虎榜卖出额 |
| l_buy | float | Y | 龙虎榜买入额 |
| l_amount | float | Y | 龙虎榜成交额 |
| net_amount | float | Y | 龙虎榜净买入额 |
| net_rate | float | Y | 龙虎榜净买额占比 |
| amount_rate | float | Y | 龙虎榜成交额占比 |
| float_values | float | Y | 当日流通市值 |
| reason | str | Y | 上榜理由 |

接口用户
数据样例


---

### [107] 龙虎榜机构交易单  ·  股票数据 / 打板专题数据
(api: top_inst | 输出字段: 10 | PIT字段: 否)

# (doc_id=107)  https://tushare.pro/document/2?doc_id=107

## 龙虎榜机构明细
接口：top_inst 描述：龙虎榜机构成交明细 限量：单次请求最大返回10000行数据，可根据参数循环获取全部历史 积分：用户需要至少5000积分才可以调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 交易日期 |
| ts_code | str | N | TS代码 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 交易日期 |
| ts_code | str | Y | TS代码 |
| exalter | str | Y | 营业部名称 |
| side | str | Y | 买卖类型0：买入金额最大的前5名， 1：卖出金额最大的前5名 |
| buy | float | Y | 买入额（元） |
| buy_rate | float | Y | 买入占总成交比例 |
| sell | float | Y | 卖出额（元） |
| sell_rate | float | Y | 卖出占总成交比例 |
| net_buy | float | Y | 净成交额（元） |
| reason | str | Y | 上榜理由 |

接口用法
数据样例


---

### [355] THS涨跌停榜单  ·  股票数据 / 打板专题数据
(api: limit_list_ths | 输出字段: 24 | PIT字段: 否)

# (doc_id=355)  https://tushare.pro/document/2?doc_id=355

## 涨跌停榜单（同花顺）
接口：limit_list_ths 描述：获取同花顺每日涨跌停榜单数据，历史数据从20231101开始提供，增量每天16点左右更新 限量：单次最大4000条，可根据日期或股票代码循环提取 积分：8000积分以上每分钟500次，每天总量不限制，具体请参阅 积分获取办法 注意：本接口只限个人学习和研究使用，如需商业用途，请自行联系同花顺解决数据采购问题。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | N | 交易日期 |
| ts_code | str | N | 股票代码 |
| limit_type | str | N | 涨停池、连扳池、冲刺涨停、炸板池、跌停池，默认：涨停池 |
| market | str | N | HS-沪深主板 GEM-创业板 STAR-科创板 |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 交易日期 |
| ts_code | str | Y | 股票代码 |
| name | str | Y | 股票名称 |
| price | float | Y | 收盘价(元) |
| pct_chg | float | Y | 涨跌幅% |
| open_num | int | Y | 打开次数 |
| lu_desc | str | Y | 涨停原因 |
| limit_type | str | Y | 板单类别 |
| tag | str | Y | 涨停标签 |
| status | str | Y | 涨停状态（N连板、一字板） |
| first_lu_time | str | N | 首次涨停时间 |
| last_lu_time | str | N | 最后涨停时间 |
| first_ld_time | str | N | 首次跌停时间 |
| last_ld_time | str | N | 最后跌停时间 |
| limit_order | float | Y | 封单量(元 |
| limit_amount | float | Y | 封单额(元 |
| turnover_rate | float | Y | 换手率% |
| free_float | float | Y | 实际流通(元 |
| lu_limit_order | float | Y | 最大封单(元 |
| limit_up_suc_rate | float | Y | 近一年涨停封板率 |
| turnover | float | Y | 成交额 |
| rise_rate | float | N | 涨速 |
| sum_float | float | N | 总市值（亿元） |
| market_type | str | Y | 股票类型：HS沪深主板、GEM创业板、STAR科创板 |

接口用法
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：limit_list_ths 描述：获取同花顺每日涨跌停榜单数据，历史数据从20231101开始提供，增量每天16点左右更新 限量：单次最大4000条，可根据日期或股票代码循环提取 积分：8000积分以上每分钟500次，每天总量不限制，具体请参阅 积分获取办法 注意：本接口只限个人学习和研究使用，如需商业用途，请自行联系同花顺解决数据采购问题。


---

### [298] 涨跌停和炸板数据  ·  股票数据 / 打板专题数据
(api: limit_list_d | 输出字段: 18 | PIT字段: 否)

# (doc_id=298)  https://tushare.pro/document/2?doc_id=298

## 涨跌停列表（新）
接口：limit_list_d 描述：获取A股每日涨跌停、炸板数据情况，数据从2020年开始（不提供ST股票的统计） 限量：单次最大可以获取2500条数据，可通过日期或者股票循环提取 积分：5000积分每分钟可以请求200次每天总量1万次，8000积分以上每分钟500次每天总量不限制，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | N | 交易日期 |
| ts_code | str | N | 股票代码 |
| limit_type | str | N | 涨跌停类型（U涨停D跌停Z炸板） |
| exchange | str | N | 交易所（SH上交所SZ深交所BJ北交所） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 交易日期 |
| ts_code | str | Y | 股票代码 |
| industry | str | Y | 所属行业 |
| name | str | Y | 股票名称 |
| close | float | Y | 收盘价 |
| pct_chg | float | Y | 涨跌幅 |
| amount | float | Y | 成交额 |
| limit_amount | float | Y | 板上成交金额(成交价格为该股票跌停价的所有成交额的总和，涨停无此数据) |
| float_mv | float | Y | 流通市值 |
| total_mv | float | Y | 总市值 |
| turnover_ratio | float | Y | 换手率 |
| fd_amount | float | Y | 封单金额（以涨停价买入挂单的资金总量） |
| first_time | str | Y | 首次封板时间（跌停无此数据） |
| last_time | str | Y | 最后封板时间 |
| open_times | int | Y | 炸板次数(跌停为开板次数) |
| up_stat | str | Y | 涨停统计（N/T T天有N次涨停） |
| limit_times | int | Y | 连板数（个股连续封板数量） |
| limit | str | Y | D跌停U涨停Z炸板 |

接口用法
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：limit_list_d 描述：获取A股每日涨跌停、炸板数据情况，数据从2020年开始（不提供ST股票的统计） 限量：单次最大可以获取2500条数据，可通过日期或者股票循环提取 积分：5000积分每分钟可以请求200次每天总量1万次，8000积分以上每分钟500次每天总量不限制，具体请参阅 积分获取办法


---

### [356] 涨停股票连板天梯  ·  股票数据 / 打板专题数据
(api: limit_step | 输出字段: 4 | PIT字段: 否)

# (doc_id=356)  https://tushare.pro/document/2?doc_id=356

## 连板天梯
接口：limit_step 描述：获取每天连板个数晋级的股票，可以分析出每天连续涨停进阶个数，判断强势热度 限量：单次最大2000行数据，可根据股票代码或者日期循环提取全部 积分：8000积分以上每分钟500次，每天总量不限制，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | N | 交易日期（格式：YYYYMMDD，下同） |
| ts_code | str | N | 股票代码 |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |
| nums | str | N | 连板次数，支持多个输入，例如nums='2,3' |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 代码 |
| name | str | Y | 名称 |
| trade_date | str | Y | 交易日期 |
| nums | str | Y | 连板次数 |

接口用法
数据样例


---

### [357] 涨停最强板块统计  ·  股票数据 / 打板专题数据
(api: limit_cpt_list | 输出字段: 9 | PIT字段: 否)

# (doc_id=357)  https://tushare.pro/document/2?doc_id=357

## 最强板块统计
接口：limit_cpt_list 描述：获取每天涨停股票最多最强的概念板块，可以分析强势板块的轮动，判断资金动向 限量：单次最大2000行数据，可根据股票代码或者日期循环提取全部 积分：8000积分以上每分钟500次，每天总量不限制，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | N | 交易日期（格式：YYYYMMDD，下同） |
| ts_code | str | N | 板块代码 |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 板块代码 |
| name | str | Y | 板块名称 |
| trade_date | str | Y | 交易日期 |
| days | int | Y | 上榜天数 |
| up_stat | str | Y | 连板高度 |
| cons_nums | int | Y | 连板家数 |
| up_nums | int | Y | 涨停家数 |
| pct_chg | float | Y | 涨跌幅% |
| rank | str | Y | 板块热点排名 |

接口用法
数据样例


---

### [259] THS概念板块分类  ·  股票数据 / 打板专题数据
(api: ths_index | 输出字段: 6 | PIT字段: 否)

# (doc_id=259)  https://tushare.pro/document/2?doc_id=259

## 概念和行业指数
接口：ths_index 描述：获取板块指数，包括概念、行业、特色指数。 权限：本接口需有6000积分，单次最大返回5000行数据，一次可提取全部数据，请勿循环提取。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 指数代码 |
| exchange | str | N | 市场类型A-a股 HK-港股 US-美股 |
| type | str | N | 指数类型 N-概念指数 I-行业指数 R-地域指数 S-特色指数 ST-风格指数 TH-主题指数 BB-宽基指数 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 代码 |
| name | str | Y | 名称 |
| count | int | Y | 成分个数 |
| exchange | str | Y | 交易所 |
| list_date | str | Y | 上市日期 |
| type | str | Y | N概念指数S特色指数 |

接口示例
数据样例


---

### [260] THS概念板块行情  ·  股票数据 / 打板专题数据
(api: ths_daily | 输出字段: 14 | PIT字段: 否)

# (doc_id=260)  https://tushare.pro/document/2?doc_id=260

## 板块指数行情
接口：ths_daily 描述：获取板块指数行情 限量：单次最大3000行数据（需6000积分），可根据指数代码、日期参数循环提取
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 板块指数代码 |
| trade_date | str | N | 交易日期（YYYYMMDD格式，下同） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS指数代码 |
| trade_date | str | Y | 交易日 |
| close | float | Y | 收盘点位 |
| open | float | Y | 开盘点位 |
| high | float | Y | 最高点位 |
| low | float | Y | 最低点位 |
| pre_close | float | Y | 昨日收盘点 |
| avg_price | float | Y | 平均价 |
| change | float | Y | 涨跌点位 |
| pct_change | float | Y | 涨跌幅 |
| vol | float | Y | 成交量（手） |
| turnover_rate | float | Y | 换手率（%） |
| total_mv | float | N | 总市值（元） |
| float_mv | float | N | 流通市值（元） |

接口示例
数据样例


---

### [261] THS概念板块成分  ·  股票数据 / 打板专题数据
(api: ths_member | 输出字段: 7 | PIT字段: 否)

# (doc_id=261)  https://tushare.pro/document/2?doc_id=261

## 概念板块成分
接口：ths_member 描述：获取概念板块成分列表 限量：用户积累6000积分可调取，每分钟可调取200次，可按概念板块代码循环提取所有成分
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 板块指数代码 |
| con_code | str | N | 股票代码 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 指数代码 |
| con_code | str | Y | 股票代码 |
| con_name | str | Y | 股票名称 |
| weight | float | N | 权重(暂无) |
| in_date | str | N | 纳入日期(暂无) |
| out_date | str | N | 剔除日期(暂无) |
| is_new | str | N | 是否最新Y是N否 |

接口示例
数据样例


---

### [362] DC概念板块分类  ·  股票数据 / 打板专题数据
(api: dc_index | 输出字段: 13 | PIT字段: 否)

# (doc_id=362)  https://tushare.pro/document/2?doc_id=362

## 概念板块
接口：dc_index 描述：获取每个交易日的概念板块数据，支持按日期查询 限量：单次最大可获取5000条数据，历史数据可根据日期循环获取 权限：用户积累6000积分可调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 指数代码（支持多个代码同时输入，用逗号分隔） |
| name | str | N | 板块名称（例如：人形机器人） |
| trade_date | str | N | 交易日期（YYYYMMDD格式，下同） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |
| idx_type | str | Y | 板块类型(行业板块、概念板块、地域板块) |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 概念代码 |
| trade_date | str | Y | 交易日期 |
| name | str | Y | 概念名称 |
| leading | str | Y | 领涨股票名称 |
| leading_code | str | Y | 领涨股票代码 |
| pct_change | float | Y | 涨跌幅 |
| leading_pct | float | Y | 领涨股票涨跌幅 |
| total_mv | float | Y | 总市值（万元） |
| turnover_rate | float | Y | 换手率 |
| up_num | int | Y | 上涨家数 |
| down_num | int | Y | 下降家数 |
| idx_type | str | Y | 板块类型(行业板块、概念板块、地域板块) |
| level | str | Y | 行业层级 |

接口示例
数据示例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：dc_index 描述：获取每个交易日的概念板块数据，支持按日期查询 限量：单次最大可获取5000条数据，历史数据可根据日期循环获取 权限：用户积累6000积分可调取，具体请参阅 积分获取办法


---

### [363] DC概念板块成分  ·  股票数据 / 打板专题数据
(api: dc_member | 输出字段: 4 | PIT字段: 否)

# (doc_id=363)  https://tushare.pro/document/2?doc_id=363

## 板块成分
接口：dc_member 描述：获取板块每日成分数据，可以根据概念板块代码和交易日期，获取历史成分 限量：单次最大获取5000条数据，可以通过日期和代码循环获取 权限：用户积累6000积分可调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 板块指数代码 |
| con_code | str | N | 成分股票代码 |
| trade_date | str | N | 交易日期（YYYYMMDD格式） |
| start_date | str | N | 开始日期（YYYYMMDD格式） |
| end_date | str | N | 结束日期（YYYYMMDD格式） |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 交易日期 |
| ts_code | str | Y | 概念代码 |
| con_code | str | Y | 成分代码 |
| name | str | Y | 成分股名称 |

接口示例
数据示例


---

### [382] DC概念板块行情  ·  股票数据 / 打板专题数据
(api: dc_daily | 输出字段: 12 | PIT字段: 否)

# (doc_id=382)  https://tushare.pro/document/2?doc_id=382

## 概念板块行情
接口：dc_daily 描述：获取概念板块、行业指数板块、地域板块行情数据，历史数据开始于2020年 限量：单次最大2000条数据，可根据日期参数循环获取 权限：用户积累6000积分可调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 板块代码（格式：xxxxx.DC) |
| trade_date | str | N | 交易日期(格式：YYYYMMDD下同） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |
| idx_type | str | N | 板块类型： 概念板块、行业板块、地域板块 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 板块代码 |
| trade_date | str | Y | 交易日 |
| close | float | Y | 收盘点位 |
| open | float | Y | 开盘点位 |
| high | float | Y | 最高点位 |
| low | float | Y | 最低点位 |
| change | float | Y | 涨跌点位 |
| pct_change | float | Y | 涨跌幅 |
| vol | float | Y | 成交量(股) |
| amount | float | Y | 成交额(元) |
| swing | float | Y | 振幅 |
| turnover_rate | float | Y | 换手率 |

接口示例
数据示例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：dc_daily 描述：获取概念板块、行业指数板块、地域板块行情数据，历史数据开始于2020年 限量：单次最大2000条数据，可根据日期参数循环获取 权限：用户积累6000积分可调取，具体请参阅 积分获取办法


---

### [369] 开盘竞价成交（当日）  ·  股票数据 / 打板专题数据
(api: stk_auction | 输出字段: 9 | PIT字段: 否)

# (doc_id=369)  https://tushare.pro/document/2?doc_id=369

## 当日集合竞价
接口：stk_auction 描述：获取当日个股和ETF的集合竞价成交情况，每天9点26~29分之间可以获取当日的集合竞价成交数据 限量：单次最大返回8000行数据，可根据日期或代码循环获取历史 积分：本接口是单独开权限的数据，单独申请权限请参考 权限列表 。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码 |
| trade_date | str | N | 交易日期（YYYYMMDD格式，下同) |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| trade_date | str | Y | 数据日期 |
| vol | int | Y | 成交量（股） |
| price | int | Y | 成交均价（元） |
| amount | float | Y | 成交金额（元） |
| pre_close | float | Y | 昨收价（元） |
| turnover_rate | float | Y | 换手率（%） |
| volume_ratio | float | Y | 量比 |
| float_share | float | Y | 流通股本（万股） |

接口示例
数据示例


---

### [311] 市场游资最全名录  ·  股票数据 / 打板专题数据
(api: hm_list | 输出字段: 3 | PIT字段: 否)

# (doc_id=311)  https://tushare.pro/document/2?doc_id=311

## 游资名录
接口：hm_list 描述：获取游资分类名录信息 限量：单次最大1000条数据，目前总量未超过500 积分：5000积分可以调取，积分获取办法请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| name | str | N | 游资名称 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| name | str | Y | 游资名称 |
| desc | str | Y | 说明 |
| orgs | None | Y | 关联机构 |

接口示例
数据列表
| 名称 | 说明 | 关联机构 |
| --- | --- | --- |
| 龙飞虎 | 龙飞虎(克拉美书)股灾期间曾为桃县精神领袖，留有颇多名言，可见人品股品。 | 华泰证券股份有限公司南京六合雄州西路证券营业部 |
| 高送转专家 | 擅长在高送转个股进行波段操作 | 财通证券股份有限公司常熟枫林路证券营业部 |
| 高毅邻山 | 价投大神“茅台03"，真名冯柳。自述曾有9年时间多达93%的年复利回报。眼光犀利独到，风格以中长线为主，碰上短线风口会主动配合炒作迅速推升股价。 | 国信证券股份有限公司深圳罗湖宝安北路证券营业部 |
| 骑牛 | 敢于追涨，锁仓，也敢于割肉。 | 中国银河证券股份有限公司重庆民族路证券营业部 |
| 首板挖掘 | 善于发掘低位首板或跟风板，市场上活跃的挖掘资金，擅长在题材爆发后挖掘补涨机会，一旦出现高位分歧就会及时离场。 | 申万宏源证券有限公司北京劲松九区证券营业部、湘财证券股份有限公司武汉友谊大道证券营业部、国都证券股份有限公司北京阜外大街证券营业部、华鑫证券有限责任公司泉州宝洲路证券营业部、华鑫证券有限责任公司江苏分公司、华鑫证券有限责任公司山东分公司、兴业证券股份有限公司厦门分公司、中信证券股份有限公司金华分公司、中信建投证券股份有限公司西安南大街证券营业部、东莞证券股份有限公司深圳后海工业八路证券营业部、东莞证券股份有限公司厦门分公司、东方财富证券股份有限公司江苏分公司、万和证券股份有限公司福建分公司 |
| 飞云江路 | 知名游资，近来崛起的江浙资金席位，接力操作为主，尤擅点火操作，资金规模适中，但活跃力度较高。 | 华鑫证券有限责任公司杭州飞云江路证券营业部 |
| 隐秀路 | 杭州隐秀路，60后，代表作南天信息，深桑达。隐秀路有人称其为散户收割机，也反映出不一样的手法操作，市场理解超于常人，信创概念股个人保守估计浮盈约1亿。操作手法一流，将极限做到极致，喜欢一家独大。 | 华鑫证券有限责任公司杭州隐秀路证券营业部 |
| 陈小群 | 活跃于网络论坛的实力游资，擅长趋势龙头，分歧打板介入，理解力尤其优秀。 | 中国银河证券股份有限公司大连黄河路证券营业部、中国银河证券股份有限公司大连金马路证券营业部 |
| 金田路 | 交易手法简单粗暴，追龙头，专做高位接力板，敢收敢割，在市场好的时候敢在高位连续加仓，遭遇行情不好的时候割的非常果断，毫不犹豫。 | 光大证券股份有限公司深圳金田路证券营业部、中天证券股份有限公司深圳分公司、中天证券股份有限公司台州市府大道证券营业部 |
| 量化打板 | 量化打板，绝大多数操作以首板二板为主，次日不能秒板开盘都会先兑现一半，上板纠错买回部分仓位，不能走强则直接清仓。 | 华鑫证券有限责任公司上海分公司、华创证券有限责任公司上海第二分公司 |
| 量化基金 | 20年参与京粮控股首次携假机构入场，凭借机构席位溢价次日获得一字板，到现在量化基金已经是市场上非常活跃的一股力量，内部资金成分复杂，多家机构混杂在其中，但是整体策略同样是起到助涨助跌的作用，会频繁做T。 | 华泰证券股份有限公司总部、中国国际金融股份有限公司上海黄浦区湖滨路证券营业部、中国国际金融股份有限公司上海分公司、中国中金财富证券有限公司北京宋庄路证券营业部、东北证券股份有限公司绍兴金柯桥大道证券营业部 |
| 赵老哥 | 以短线点火打板为主，擅长主线题材炒作，主抓龙头股。主要参与市场风口的龙头股接力板，激发市场资金持续接力。盘中操作手法主要以急速暴量扫货封板为主，利用资金优势万手大单排板。 | 银泰证券有限责任公司上海嘉善路证券营业部、湘财证券股份有限公司上海陆家嘴证券营业部、浙商证券股份有限公司绍兴分公司、浙商证券股份有限公司湖州双子大厦证券营业部、华泰证券股份有限公司浙江分公司、中国银河证券股份有限公司绍兴证券营业部、中国银河证券股份有限公司北京阜成路证券营业部 |
| 西湖国贸 | 顶级价投型资金，顶级理解力，善于挖掘低位的趋势牛股，波段持股为主。 | 财信证券股份有限公司杭州西湖国贸中心证券营业部 |
| 葛卫东 | 葛卫东偏爱科技股，其次是医药股，基本以中、长线投资为主，买入股票后往往会持有几年时间直至股价起飞\r\n | 国泰君安证券股份有限公司上海分公司 |
| 著名刺客 | 活跃于股吧、论坛的小游资，擅长龙头股锁仓。 | 海通证券股份有限公司北京阜外大街证券营业部、东莞证券股份有限公司北京分公司 |
| 落升(江南神鹰) | 落升(江南神鹰)03年的股评红遍网络05年底隐居隐居3年狂赚112倍他的故事网上有详细记载据观察其后自然人名罗申，取的是谐音，大熊市战绩斐然，令人惊叹，游资界早年网红派。 | 光大证券股份有限公司金华宾虹路证券营业部 |
| 苏州帮 | 以做短线为主，常见高抛低吸，做T营业部。 | 海通证券股份有限公司杭州市心北路证券营业部、广发证券股份有限公司苏州东吴北路证券营业部、华泰证券股份有限公司苏州人民路证券营业部、兴业证券股份有限公司上海金陵东路证券营业部、东吴证券股份有限公司苏州西北街证券营业部、东吴证券股份有限公司常州通江中路证券营业部 |
| 苏南帮 | 短庄游资，资金体量较大且人员众多，席位多为江苏本地席位联动操作，3/4板多为强顶一字板。 | 长江证券股份有限公司武汉友谊路证券营业部、长江证券股份有限公司南京中山东路证券营业部、申万宏源西部证券有限公司南宁英华路证券营业部、海通证券股份有限公司武汉光谷证券营业部、海通证券股份有限公司南京广州路证券营业部、天风证券股份有限公司深圳福华路证券营业部、天风证券股份有限公司深圳后海证券营业部、国泰君安证券股份有限公司深圳登良路证券营业部、国泰君安证券股份有限公司南京金融城证券营业部、南京证券股份有限公司张家港东环路证券营业部、华泰证券股份有限公司镇江句容华阳北路证券营业部、华泰证券股份有限公司无锡金融一街证券营业部、华泰证券股份有限公司宁波柳汀街证券营业部、华泰证券股份有限公司南宁民族大道证券营业部、华泰证券股份有限公司南京江宁天元东路证券营业部、华泰证券股份有限公司南京庐山路证券营业部、华泰证券股份有限公司南京中华路证券营业部、中国银河证券股份有限公司北京学院南路证券营业部、东莞证券股份有限公司苏州聚茂街路证券营业部、东莞证券股份有限公司福建分公司、东莞证券股份有限公司浙江分公司、东莞证券股份有限公司四川分公司、东海证券股份有限公司南京洪武北路证券营业部、上海证券有限责任公司黄浦区延安东路证券营业部、上海证券有限责任公司南京胜太路证券营业部、上海证券有限责任公司南京溧水致远路证券营业部 |
| 红岭路 | 联同作战，喜欢运作的强势主力之一，往往在核心个股第一波爆量后吸筹进场，随后维护股价，等待时机启动二波。 | 平安证券股份有限公司深圳蛇口招商路招商大厦证券营业部、平安证券股份有限公司深圳分公司、华泰证券股份有限公司深圳彩田路证券营业部 |
| 粉葛 | 擅长趋势热门股，打板交易 | 东亚前海证券有限责任公司深圳分公司 |
| 章盟主 | 江浙地区元老级顶级游资之一，90年代5万元入市。现在资金体量百亿，20年20万倍，操作霸气，尤好在权重大票上主升浪上重仓出击。 | 海通证券股份有限公司上海徐汇区建国西路证券营业部、方正证券股份有限公司杭州延安路证券营业部、国泰君安证券股份有限公司宁波广福街证券营业部、国泰君安证券股份有限公司上海江苏路证券营业部、中信证券股份有限公司杭州延安路证券营业部、中信证券股份有限公司杭州富春路证券营业部 |
| 竞价抢筹 | 量化交易，尤其擅长分歧回暖日竞价最后时间扫货，有能力制造弱转强分时吸引市场资金流入 | 中国银河证券股份有限公司北京中关村大街证券营业部 |
| 益田路 | 顶级情绪资金，对价投亦有独到理解。益田路游资基本上多是以自买自卖的形式出现在龙虎榜上。 | 华鑫证券有限责任公司深圳益田路证券营业部 |
| 申港广东分 | 情绪周期先行者,实力彪悍执行力务必坚决 | 申港证券股份有限公司广东分公司 |
| 瑞鹤仙 | 2011年入市，在当时的熊市中依然所向披靡，入市3年资金就从数十万达到上亿。以白衣骑士自居，操作风格独来独往。 | 诚通证券股份有限公司宜昌东山大道证券营业部、中国银河证券股份有限公司宜昌新世纪证券营业部、中信建投证券股份有限公司宜昌解放路证券营业部 |
| 玉兰路 | 近来崛起的资金席位，接力操作为主，风格激进，擅长龙头股锁仓 | 东莞证券股份有限公司南京分公司 |
| 独股一剑 | 网名，独股一剑，天涯论坛最早布道者，影响了一大批后来者，几乎是桃县半数超短手的启蒙老师，最早是天涯直播交割单火起来的。乔帮主便是在07年入市7年之后接触其交割单后顿悟，大开大合，一年过亿的。 | 华泰证券股份有限公司北京月坛南街证券营业部 |
| 牛散朱彬 | 朱彬实际控制并使用的账户“朱彬”“朱某宏”和“林某丽”证券账户（以下简称账户组）由朱彬实际控制并使用。其中朱某宏、林某丽是朱彬的父母，账户组内的资金主要为朱彬所有。账户组所使用的交易终端在中泰证券宁波江东北路营业部大户室，与账户组交易资料核对一致，并由朱彬予以确认。 | 中泰证券股份有限公司宁波江东北路证券营业部 |
| 牛散唐汉若 | 牛散唐汉若，喜欢巨量出击，创小板玩得不错，但也有乐视网（300104）硬封割肉的时候，敢干敢割死队成员之一，资金量也在10位之上，硬派选手，圈内盛传千股跌停之下7个亿死扛浙富控股。 | 首创证券股份有限公司北京雍和宫证券营业部、华泰证券股份有限公司北京雍和宫证券营业部 |
| 炒股养家 | 目前资金量极大，对市场和个股都有很独到的理解力，通道优势较强，常常利用通道使个股一字涨停，隔日高位逐步离场。善于挖掘题材龙头。 | 浙商证券股份有限公司绍兴解放北路证券营业部、华鑫证券有限责任公司马鞍山分公司、华鑫证券有限责任公司西安南二环证券营业部、华鑫证券有限责任公司珠海海滨南路证券营业部、华鑫证券有限责任公司南昌分公司、华鑫证券有限责任公司北京光华路证券营业部、华鑫证券有限责任公司上海莘庄证券营业部、华鑫证券有限责任公司上海茅台路证券营业部、华鑫证券有限责任公司上海红宝石路证券营业部、华鑫证券有限责任公司上海松江证券营业部、华鑫证券有限责任公司上海宛平南路证券营业部、华创证券有限责任公司上海大连路证券营业部 |
| 炒新一族 | 市场上专做次新股的几个游资，近期参与了彩讯、锋龙，仙鹤股份的接力，主要是上海的几个席位，分别是上海共和新路、上海武定路、上海澳门路。这几个席位经常联合出动，利用资金优势拉升开板次新，风格也是超短为主，一日游居多。 | 华泰证券股份有限公司无锡解放西路证券营业部、华泰证券股份有限公司上海静安区广中西路证券营业部、华泰证券股份有限公司上海武定路证券营业部、华泰证券股份有限公司上海普陀区江宁路证券营业部 |
| 湖里大道 | 厦门一线游资，眼光独到，出手大气 | 兴业证券股份有限公司厦门湖里大道证券营业部 |
| 湖州劳动路 | 湖州实力游资，做票以接力居多，风格剽悍，尤好操控，常常与江浙资金联动出没。 | 华鑫证券有限责任公司湖州劳动路浙北金融中心证券营业部、华鑫证券有限责任公司深圳分公司、华鑫证券有限责任公司南京清凉门大街证券营业部 |
| 温州帮 | 2016年操作次新股一战成名，手法彪悍，经常连续拉升3个涨停板。操作手法往往多席位联合出动，同时盘踞在数只次新股，建仓迅速，深度控盘，快速对倒拉升。 | 银泰证券有限责任公司济南大纬二路证券营业部、财信证券股份有限公司上海大连路证券营业部、西南证券股份有限公司温州汤家桥路证券营业部、第一创业证券股份有限公司青岛秦岭路证券营业部、申万宏源证券有限公司温州车站大道证券营业部、申万宏源证券有限公司扬州分公司、平安证券股份有限公司上海常熟路证券营业部、华鑫证券有限责任公司乐清双雁路证券营业部、华泰证券股份有限公司郑州经三路证券营业部、 申万宏源西部证券福州古田路证券营业部 |
| 深股通专用 | 深港通，是深港股票市场交易互联互通机制的简称，指深圳证券交易所和香港联合交易所有限公司建立技术连接，使内地和香港投资者可以通过当地证券公司或经纪商买卖规定范围内的对方交易所上市的股票。 | 深股通专用 |
| 深圳帮 | 深圳营业部做T做的飞起，经常可以看见深圳帮做T，同样活跃还有上海帮、杭州帮，所操作标的彼此之间重合度很高。 | 财通证券股份有限公司绍兴柯桥区钱清钱门大道证券营业部、恒泰证券股份有限公司深圳梅林路证券营业部、恒泰证券股份有限公司武汉新华路证券营业部、华龙证券股份有限公司深圳民田路证券营业部、华泰证券股份有限公司福州五一北路证券营业部 |
| 涪陵广场路 | 西南地区，巨型打板游资，资金实力雄厚，出手频率不高，但尤好重仓大手笔出手，风格剽悍，经常单笔近亿，曾在美锦能源、泰禾集团、北斗星通上大手笔出手。 | 方正证券股份有限公司重庆金开大道证券营业部、中信建投证券股份有限公司重庆涪陵证券营业部 |
| 涅盘重升 | 90后知名选手，曾有四年百倍战绩 | 长城证券股份有限公司资阳蜀乡大道证券营业部、上海证券有限责任公司苏州太湖西路证券营业部 |
| 浙江帮 | 浙江帮的特点是出货的时候下方喜欢挂出非常多的自己的买单，撑住盘面不下跌，再用快速拉升法快速拉高股价，吸引散户追高，用密集的中小单抛货，躲过散户的眼睛，从浙江帮选股的特点来看，他们喜欢选一些低价股，这样会有非常多的买卖单，进出也是非常频繁密集，这样是很容易躲过散户的眼睛的。 | 西部证券股份有限公司西安高新路证券营业部、申万宏源证券有限公司瑞安罗阳大道证券营业部、浙商证券股份有限公司路桥数码街证券营业部、兴业证券股份有限公司石狮宝岛中路证券营业部、九州证券股份有限公司厦门分公司、万联证券股份有限公司广州番禺清河东路证券营业部 |
| 流沙河 | 成名于网络论坛，异常活跃的游资席位。专一的打板选手，主做低位板。喜欢做顶板、秒板，快速拉升的分时强势个股。 | 中信证券股份有限公司北京远大路证券营业部 |
| 沪股通专用 | 沪港通是指上海证券交易所和香港联合交易所允许两地投资者通过当地证券公司（或经纪商）买卖规定范围内的对方交易所上市的股票，是沪港股票市场交易互联互通机制。 | 沪股通专用 |
| 毛老板 | 成都毛老板（现改名塞力斯）对强基本面个股有自己独到的理解，更早之前毛老板是造妖大师金田路，后面转型趋势打法淡出短线市场 | 申万宏源证券有限公司深圳金田路证券营业部、广发证券股份有限公司上海东方路证券营业部、国泰君安证券股份有限公司北京光华路证券营业部、万和证券股份有限公司成都通盈街证券营业部 |
| 歌神 | 分时看的准，情绪面把控的很到位。 | 兴业证券股份有限公司杭州体育场路证券营业部、中国中金财富证券有限公司杭州江河汇证券营业部、中信证券股份有限公司杭州金城路证券营业部 |
| 欢乐海岸 | 极少涉及首板，一般都是高位板；经常多席位联动，大手笔封单，总额经常上亿；介入后经常锁仓，也不轻易砸盘，往往离场之后尾盘也会拉升进行善后。 | 第一创业证券股份有限公司深圳福华一路总部证券营业部、招商证券股份有限公司深圳深南大道车公庙证券营业部、广发证券股份有限公司深圳福华一路证券营业部、平安证券股份有限公司深圳金田路证券营业部、国金证券股份有限公司深圳湾一号证券营业部、华泰证券股份有限公司深圳科苑南路华润大厦证券营业部、华泰证券股份有限公司深圳深南大道基金大厦证券营业部、华泰证券股份有限公司深圳分公司、中泰证券股份有限公司深圳科苑南路证券营业部、中泰证券股份有限公司深圳宝源南路证券营业部、中泰证券股份有限公司深圳分公司、中国中金财富证券有限公司深圳宝安兴华路证券营业部、中国中金财富证券有限公司云浮新兴东堤北路证券营业部、中信证券股份有限公司深圳科技园证券营业部、中信证券股份有限公司深圳后海证券营业部、中信证券股份有限公司深圳分公司 |
| 杭州帮 | 杭州系短线游资，资金量较大，喜欢动用多个营业部同时操作一股，波段操作，整体成功率较高。偏好上市3年以上的老股票，规模上，大盘股与小盘股都是他的最爱，整体分布较为平均。 | 浙商证券股份有限公司杭州萧山永久路证券营业部、光大证券股份有限公司杭州延安路证券营业部、中国银河证券股份有限公司杭州景芳证券营业部、中国银河证券股份有限公司杭州天城东路证券营业部、中国银河证券股份有限公司杭州凤起路证券营业部、中信证券股份有限公司杭州庆春路证券营业部、中信建投证券股份有限公司杭州庆春路证券营业部 |
| 机构专用 | 新交易规则规定，机构席位是指基金专用席位、券商自营专用席位、社保专用席位、券商理财专用席位、保险机构专用席位、保险机构租用席位、QFII专用席位等机构投资者买卖证券的专用通道和席位。 | 机构专用5、机构专用4、机构专用3、机构专用2、机构专用1、机构专用 |
| 方新侠 | 与赵老哥同期的顶级游资，操作手法大开大合，擅长大成交趋势股。2020年主导了省广集团大二波、未名医药等票。 | 兴业证券股份有限公司陕西分公司、中信证券股份有限公司西安朱雀大街证券营业部 |
| 新生代 | 新晋市场主力，擅长低位题材挖掘潜伏及打造板块补涨，通常喜欢提前埋伏底仓。 | 银泰证券有限责任公司成都顺城大街证券营业部、安信证券股份有限公司广州猎德大道证券营业部、华泰证券股份有限公司上海牡丹江路证券营业部、中国银河证券股份有限公司上海新闸路证券营业部、中信证券(山东)有限责任公司莱州文化东路证券营业部 |
| 敢死队 | 宁波敢死队主要由4号人物组成,又并称为“超短F4”。1号人物叫徐翔,是敢死队中年纪最轻的一位。2号人物姓吴,大约35岁。两人大约在1999年从其他营业部转到银河证券宁波解放南路营业部,当时资金不过几十万元,4年后,两人账户上的钱都变成了数千万元。3号人物徐海鸥,1975年出生,上大学时就开始炒股,1997年毕业于北京商学院后没找工作,就直接回宁波专职炒股。而马信琪在这三位之前,2002年5月,被临近的天一证券(现为光大证券)解放南路营业部挖走,数位大户亦追随而去。4人并称“超短F4”。敢死队以吃庄家为生, | 平安证券股份有限公司深圳深南东路罗湖商务中心证券营业部、中泰证券股份有限公司上海建国中路证券营业部 |
| 撬板王 | 风格上喜欢撬跌停板，尤其是连续跌停的个股，人称撬板王 | 兴业证券股份有限公司苏州分公司、兴业证券股份有限公司深圳分公司 |
| 招商深南东 | 作为国内A股市场游资主力，招商证券深南东路手法相对温和，在选股方面并不热衷于次新股，跟踪上市时间三年以上个股较多，选择热点板块其中的人气个股，但大多为上涨行情还没有启动，或者已进入调整期的个股；其操作套路还是集中优势资金趋势加速，吸引跟盘资金接盘出货。 | 招商证券股份有限公司深圳深南东路证券营业部 |
| 成都系 | 超短游资，具备短时间内引导个股价格的能力，风格稳定，以超跌板为主，盘中都是直线拉升涨停，引导资金合力封板。擅长做首板个股并且盘中喜欢直线拉升，次日冲高后爱砸盘，偏爱中小盘个股。 | 宏信证券有限责任公司成都紫竹北街证券营业部、国融证券股份有限公司青岛分公司、国联证券股份有限公司成都锦城大道证券营业部、国泰君安证券股份有限公司成都天府二街证券营业部、国泰君安证券股份有限公司成都北一环路证券营业部、华泰证券股份有限公司成都天府广场证券营业部、华泰证券股份有限公司德阳长江西路钻石广场证券营业部、中国银河证券股份有限公司成都科华北路证券营业部、中信建投证券股份有限公司成都马家花园证券营业部 |
| 成泉系 | 做均线多头发散向上的个股并惯提前建仓；涨停板往往不封死，反复打开并再度封板；次日继续涨停概率较低。 | 华泰证券股份有限公司北京西三环国际财经中心证券营业部、中泰证券股份有限公司北京自贸试验区证券营业部、中国国际金融股份有限公司北京建国门外大街证券营业部、中信证券股份有限公司北京金融大街证券营业部 |
| 思明南路 | 2022年90后游资，风格多变但选股水平极高，参与的个股大多有基本面支撑。 | 东莞证券股份有限公司湖北分公司、东亚前海证券有限责任公司上海分公司 |
| 徐留胜 | 著名牛散、顶级游资徐留胜，曾被证监会处罚罚没1.1亿。通常喜好大手笔出手后波段锁仓 | 华泰证券股份有限公司深圳益田路荣超商务中心证券营业部 |
| 徐晓 | 大手笔、低频率、资金实力雄厚、出手胜率极高，有主导热点板块龙头股趋势行情的能力 | 国元证券股份有限公司上海虹桥路证券营业部 |
| 广东帮 | 操作手法上习惯用“大阳线——调整数日——大阳线”反复拉升 | 财通证券股份有限公司温岭中华路证券营业部、申万宏源证券有限公司杭州密渡桥路证券营业部、申万宏源证券有限公司上海黄浦区中华路证券营业部、德邦证券股份有限公司上海岳州路证券营业部、华福证券有限责任公司厦门湖滨南路证券营业部、东方证券股份有限公司上海黄浦区中华路证券营业部 |
| 山东帮 | 因为当时山东席位为旗舰，故被称为“山东帮”，次新股手法,往往是多席位联合行动,同时盘踞在数只次新股上面,建仓迅速,深度控盘,快速对倒拉升。 | 方正证券股份有限公司温州小南路证券营业部、广发证券股份有限公司荣成石岛证券营业部、国海证券股份有限公司济宁邹城市太平东路证券营业部、国海证券股份有限公司济南历山路证券营业部、国海证券股份有限公司泰安擂鼓石大街证券营业部、国海证券股份有限公司山东分公司、华泰证券股份有限公司厦门厦禾路证券营业部、中泰证券股份有限公司荣成石岛黄海中路证券营业部、中信证券股份有限公司厦门分公司、中信证券(山东)有限责任公司荣成成山大道证券营业部、东海证券股份有限公司厦门祥福路证券营业部、东方证券股份有限公司厦门仙岳路证券营业部 |
| 屠文斌 | 屠文斌是叱咤风云的老牌游资，偏好大流通的板块中军，可观察其出手来判断板块地位。 | 中国银河证券股份有限公司上海杨浦区靖宇东路证券营业部 |
| 小鳄鱼 | 新生代90后游资，常常活跃在各大论坛社区，手法剽悍，资金体量过亿。在趋势性行情下也能与时俱进，对基本面的理解非常不错，胜率较高。 | 长江证券股份有限公司上海世纪大道证券营业部、南京证券股份有限公司南京大钟亭证券营业部、中国中金财富证券有限公司南京龙蟠中路证券营业部、东方证券股份有限公司上海浦东新区源深路证券营业部 |
| 小棉袄 | 价值投机型顶级选手，从钠电池到人工智能。逻辑牛股一个不落 | 上海证券有限责任公司上海分公司 |
| 宁波解放南 | 老牌游资席位，江浙宁波敢死队资金，喜好万手倒序单联排打板，冲击制造涨停的股票，买卖市场活跃情绪标 | 光大证券股份有限公司宁波解放南路证券营业部 |
| 宁波桑田路 | 宁波知名的游资，资金量超过10亿，操作风格彪悍凌厉，是众多知名游资里面溢价比较高的席位，交易风格多为打板为主，不拘泥于是高位板，还是低位板，可以锁仓做T很久，也可以跑的飞快 | 国盛证券有限责任公司宁波桑田路证券营业部 |
| 宁波和源路 | 杀伐果断的短线选手，高位接力敢于重仓，对日内情绪节点有深刻认识，一旦个股预期走弱出货也是毫不拖泥带水。此前常用该席位的短线资金已纷纷退出，但仍有大量通道资金在使用有关席位，主要用于排一字板。 | 甬兴证券有限公司宁波和源路证券营业部 |
| 境外机构 | 境外机构是指境外官方、非官方金融机构、金融组织以及投资基金，其通过QFII和RQFII获准投资或港股通等通道投资A股市场。其资金体量大而擅长中长线投资，爱好核心资产投资。 | 瑞银证券有限责任公司上海花园石桥路证券营业部、海通证券股份有限公司国际部、国泰君安证券股份有限公司总部、北京高华证券有限责任公司北京金融大街证券营业部 |
| 和平路 | 喜欢重仓出击妖股、龙头股，且喜欢波段操作；擅长趋势交易，打板，半路，低吸 | 东兴证券股份有限公司晋江和平路证券营业部 |
| 叶庆均 | 叶庆均席位，这个席位做的股票大都是热门风口股。 | 中国银河证券股份有限公司宁波大闸南路证券营业部 |
| 古北路 | 顶级游资，2016年11月份前还默默无闻，随后却异军突起，成为龙虎榜常客，在年初的雄安板块炒作中一战成名，擅长制造板块行情，和其他一线游资联动，敢于锁仓，隐藏身后的游资大佬，孙氏父子、赵老哥分身席位诸多传言，江湖多揣测。 | 中信证券股份有限公司上海红宝石路证券营业部、中信证券股份有限公司上海牡丹江路证券营业部、中信证券股份有限公司上海凯滨路证券营业部 |
| 华鑫宁波分 | 1、确定主线热点题材，选择强势个股低吸。2、确定题材龙头，会进行打板，享受龙头溢价。3、锁定市场主线热点，敢于持续锁仓等待其发酵拉抬。4、利用交易通道优势，一字排板上市新股炒作与利好复牌个股。敢于主动引导市场，资金格局较大 | 华鑫证券有限责任公司宁波分公司 |
| 北京炒家 | 北京炒家，网传是前字节跳动员工，擅长自媒体运营，听声音年龄应该是80后之间 | 长城证券股份有限公司绵阳飞云大道证券营业部 |
| 北京帮 | 有大格局的游资，资金雄厚。 | 海通证券股份有限公司北京知春路营业部、招商证券股份有限公司北京车公庄西路证券营业部、广发证券股份有限公司潮州潮枫路证券营业部、中国银河证券股份有限公司北京朝阳门北大街证券营业部、万和证券股份有限公司成都蜀汉路证券营业部 |
| 列夫 | 从市场最整体到情绪整体、板块整体、个股个性、高低位置，主做市场龙头 | 海通证券股份有限公司绍兴劳动路证券营业部 |
| 作手新一 | 新生代小游资，资金体量相对较小，但常常活跃在各大社交论坛，知名度相对较高。 | 国泰君安证券股份有限公司南京太平南路证券营业部、中国中金财富证券有限公司南京中央路证券营业部 |
| 佛山系 | 能够在短时间内主导个股走势，风格超短，嗅觉敏感。擅长短线，早盘快速拉板，制造日内龙头，一根线拉板，从小资金做起的典范。擅长做一板个股，往往以一日游为主，次日冲高快速获利出局； | 长江证券股份有限公司武汉武珞路证券营业部、长江证券股份有限公司惠州金山湖证券营业部、长江证券股份有限公司佛山普澜二路证券营业部、诚通证券股份有限公司佛山南海大道证券营业部、湘财证券股份有限公司佛山星辰路证券营业部、海通证券股份有限公司广州珠江西路证券营业部、方正证券股份有限公司北京安定门外大街证券营业部、国盛证券有限责任公司合肥翠微路证券营业部、国泰君安证券股份有限公司顺德大良证券营业部、华泰证券股份有限公司广州兴民路证券营业部、光大证券股份有限公司佛山绿景路证券营业部、光大证券股份有限公司佛山季华六路证券营业部、东莞证券股份有限公司东莞横沥中山东路证券营业部、 长江证券股份有限公司佛山南海大道证券营业部 |
| 余哥 | 2022年新晋游资，95后，资金增长速度之快令人咋舌，擅长机构游资合力大妖股，市场理解力顶级。 | 申港证券股份有限公司浙江分公司、甬兴证券有限公司青岛同安路证券营业部 |
| 交易猿 | 操作手法，大多都是满仓资金梭哈一只股票，且这只股票前期已经有巨大涨幅，流通盘、成交量巨大的大票，做大票的半路主升浪。\r\n\r\n | 华泰证券股份有限公司天津东丽开发区二纬路证券营业部 |
| 乔帮主 | 一线游资，资金量上亿，风格凶悍，纪律严格，低吸配合打板。 | 招商证券股份有限公司深圳蛇口工业三路证券营业部 |
| 中信总部 | 中信证券股份有限公司总部(非营业场所) | 中信证券股份有限公司总部(非营业场所) |
| 上海超短帮 | 以短线速度建仓吸凑,持股周期在3-5日内,经常协同机构专用席位拉升；资金实力雄厚，通常选取一些有明显的基本面支撑的标的，携手机构席位，以小波段运作为主，整体成功率较高 | 申万宏源证券有限公司上海闵行区东川路证券营业部、国泰君安证券股份有限公司济宁吴泰闸路证券营业部、国泰君安证券股份有限公司上海新闸路证券营业部、东方证券股份有限公司无锡新生路证券营业部、东方证券股份有限公司上海浦东新区银城中路证券营业部 |
| 上海溧阳路 | 老牌游资席位，整体席位资金较杂，多路资金并存，但是总体已超短隔夜操作为主，资金实力雄厚，体量较大，具体的操盘手法是喜欢操作龙头股，找到龙头后，反复进出看好的个股。 | 中信证券股份有限公司上海溧阳路证券营业部 |
| 上塘路 | 顶级节奏大师，市场上扫板封板率最高的几路资金之一。整体操作以套利为主，稳中求进，纪律严明。上塘对次新的理解非常之深，擅长把握市场情绪，对首板的理解也居市场前列 | 财通证券股份有限公司杭州上塘路证券营业部 |
| 一瞬流光 | 擅长龙头战法，分歧买入，跟随趋势，波段买卖 | 浙商证券股份有限公司海宁水月亭西路证券营业部、中泰证券股份有限公司湖北分公司 |
| zhouyu1933 |  | 长城证券股份有限公司仙桃钱沟路证券营业部 |
| T王 | 此类席位每天做T，其乐无穷。 | 国金证券股份有限公司上海奉贤区金碧路证券营业部、国金证券股份有限公司上海互联网证券分公司、东方财富证券股份有限公司拉萨团结路第二证券营业部、东方财富证券股份有限公司拉萨团结路第一证券营业部、东方财富证券股份有限公司拉萨东环路第二证券营业部、东方财富证券股份有限公司拉萨东环路第一证券营业部、东方财富证券股份有限公司拉萨东城区江苏大道证券营业部、东方财富证券股份有限公司山南香曲东路证券营业部 |
| N周二 | 擅长低吸和打板，短线趋势交易 | 中信证券股份有限公司杭州凤起路证券营业部 |
| bike770 | 论坛知名短线选手，小资金做大的典范，曾完成四年一千倍的超级战绩。 | 国泰君安证券股份有限公司南宁民族大道证券营业部 |
| Asking |  | 兴业证券股份有限公司福州湖东路证券营业部 |
| 92科比 | 淘股吧知名选手，理解力惊人，完全理解投机本质，真正为交易而生。低吸、追涨、打板样样精通，是典型的打板高手，根据市场所处阶段切换手法。 | 兴业证券股份有限公司南京天元东路证券营业部 |


---

### [312] 游资交易每日明细  ·  股票数据 / 打板专题数据
(api: hm_detail | 输出字段: 9 | PIT字段: 否)

# (doc_id=312)  https://tushare.pro/document/2?doc_id=312

## 游资每日明细
接口：hm_detail 描述：获取每日游资交易明细，数据开始于2022年8。游资分类名录，请点击 游资名录 限量：单次最多提取2000条记录，可循环调取，总量不限制 积分：用户积10000积分可调取使用，积分获取办法请参阅 积分获取办法
注：数据为当日部分数据，此处只未作为示例效果。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | N | 交易日期(YYYYMMDD) |
| ts_code | str | N | 股票代码 |
| hm_name | str | N | 游资名称 |
| start_date | str | N | 开始日期(YYYYMMDD) |
| end_date | str | N | 结束日期(YYYYMMDD) |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 交易日期 |
| ts_code | str | Y | 股票代码 |
| ts_name | str | Y | 股票名称 |
| buy_amount | float | Y | 买入金额（元） |
| sell_amount | float | Y | 卖出金额（元） |
| net_amount | float | Y | 净买卖（元） |
| hm_name | str | Y | 游资名称 |
| hm_orgs | str | Y | 关联机构（一般为营业部或机构专用） |
| tag | str | N | 标签 |

接口示例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：hm_detail 描述：获取每日游资交易明细，数据开始于2022年8。游资分类名录，请点击 游资名录 限量：单次最多提取2000条记录，可循环调取，总量不限制 积分：用户积10000积分可调取使用，积分获取办法请参阅 积分获取办法


---

### [320] THS热榜  ·  股票数据 / 打板专题数据
(api: ths_hot | 输出字段: 11 | PIT字段: 是)

# (doc_id=320)  https://tushare.pro/document/2?doc_id=320

## THS热榜
接口：ths_hot 描述：获取热榜数据，包括热股、概念板块、ETF、可转债、港美股等等，每日盘中提取4次，收盘后4次，最晚22点提取一次。 限量：单次最大2000条，可根据日期等参数循环获取全部数据 积分：用户积6000积分可调取使用，积分获取办法请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | N | 交易日期 |
| ts_code | str | N | TS代码 |
| market | str | N | 热榜类型(热股、ETF、可转债、行业板块、概念板块、期货、港股、热基、美股) |
| is_new | str | N | 是否最新（默认Y，如果为N则为盘中和盘后阶段采集，具体时间可参考rank_time字段，状态N每小时更新一次，状态Y更新时间为22：30） |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 交易日期 |
| data_type | str | Y | 数据类型 |
| ts_code | str | Y | 股票代码 |
| ts_name | str | Y | 股票名称 |
| rank | int | Y | 排行 |
| pct_change | float | Y | 涨跌幅% |
| current_price | float | Y | 当前价格 |
| concept | str | Y | 标签 |
| rank_reason | str | Y | 上榜解读 |
| hot | float | Y | 热度值 |
| rank_time | str | Y | 排行榜获取时间 |

接口示例
数据示例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：ths_hot 描述：获取热榜数据，包括热股、概念板块、ETF、可转债、港美股等等，每日盘中提取4次，收盘后4次，最晚22点提取一次。 限量：单次最大2000条，可根据日期等参数循环获取全部数据 积分：用户积6000积分可调取使用，积分获取办法请参阅 积分获取办法
- (字段) `is_new` — str N 是否最新（默认Y，如果为N则为盘中和盘后阶段采集，具体时间可参考rank_time字段，状态N每小时更新一次，状态Y更新时间为22：30）  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [321] DC热榜  ·  股票数据 / 打板专题数据
(api: dc_hot | 输出字段: 8 | PIT字段: 是)

# (doc_id=321)  https://tushare.pro/document/2?doc_id=321

## DC热榜
接口：dc_hot 描述：获取热榜数据，包括A股市场、ETF基金、港股市场、美股市场等等，每日盘中提取4次，收盘后4次，最晚22点提取一次。 限量：单次最大2000条，可根据日期等参数循环获取全部数据 积分：用户积8000积分可调取使用，积分获取办法请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | N | 交易日期 |
| ts_code | str | N | TS代码 |
| market | str | N | 类型(A股市场、ETF基金、港股市场、美股市场) |
| hot_type | str | N | 热点类型(人气榜、飙升榜) |
| is_new | str | N | 是否最新（默认Y，如果为N则为盘中和盘后阶段采集，具体时间可参考rank_time字段，状态N每小时更新一次，状态Y更新时间为22：30） |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 交易日期 |
| data_type | str | Y | 数据类型 |
| ts_code | str | Y | 股票代码 |
| ts_name | str | Y | 股票名称 |
| rank | int | Y | 排行或者热度 |
| pct_change | float | Y | 涨跌幅% |
| current_price | float | Y | 当前价 |
| rank_time | str | Y | 排行榜获取时间 |

接口示例
数据示例
数据来源

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：dc_hot 描述：获取热榜数据，包括A股市场、ETF基金、港股市场、美股市场等等，每日盘中提取4次，收盘后4次，最晚22点提取一次。 限量：单次最大2000条，可根据日期等参数循环获取全部数据 积分：用户积8000积分可调取使用，积分获取办法请参阅 积分获取办法
- (字段) `is_new` — str N 是否最新（默认Y，如果为N则为盘中和盘后阶段采集，具体时间可参考rank_time字段，状态N每小时更新一次，状态Y更新时间为22：30）  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [376] TDX概念板块分类  ·  股票数据 / 打板专题数据
(api: tdx_index | 输出字段: 9 | PIT字段: 否)

# (doc_id=376)  https://tushare.pro/document/2?doc_id=376

## TDX板块信息
接口：tdx_index 描述：获取板块基础信息，包括概念板块、行业、风格、地域等 限量：单次最大1000条数据，可根据日期参数循环提取 权限：用户积累6000积分可调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 板块代码：xxxxxx.TDX |
| trade_date | str | N | 交易日期(格式：YYYYMMDD） |
| idx_type | str | N | 板块类型：概念板块、行业板块、风格板块、地区板块 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 板块代码 |
| trade_date | str | Y | 交易日期 |
| name | str | Y | 板块名称 |
| idx_type | str | Y | 板块类型 |
| idx_count | int | Y | 成分个数 |
| total_share | float | Y | 总股本(亿) |
| float_share | float | Y | 流通股(亿) |
| total_mv | float | Y | 总市值(亿) |
| float_mv | float | Y | 流通市值(亿) |

接口示例
数据示例


---

### [377] TDX概念板块成分  ·  股票数据 / 打板专题数据
(api: tdx_member | 输出字段: 4 | PIT字段: 否)

# (doc_id=377)  https://tushare.pro/document/2?doc_id=377

## TDX板块成分
接口：tdx_member 描述：获取各板块成分股信息 限量：单次最大3000条数据，可以根据日期和板块代码循环提取 权限：用户积累6000积分可调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 板块代码：xxxxxx.TDX |
| con_code | str | N | 成分股票代码 |
| trade_date | str | N | 交易日期：（YYYYMMDD格式） |
| start_date | str | N | 开始日期：（YYYYMMDD格式） |
| end_date | str | N | 结束日期：（YYYYMMDD格式） |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 板块代码 |
| trade_date | str | Y | 交易日期 |
| con_code | str | Y | 成分股票代码 |
| con_name | str | Y | 成分股票名称 |

接口示例
数据示例


---

### [378] TDX概念板块行情  ·  股票数据 / 打板专题数据
(api: tdx_daily | 输出字段: 38 | PIT字段: 否)

# (doc_id=378)  https://tushare.pro/document/2?doc_id=378

## TDX板块行情
接口：tdx_daily 描述：获取各板块行情，包括成交和估值等数据 限量：单次提取最大3000条数据，可根据板块代码和日期参数循环提取 权限：用户积累6000积分可调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 板块代码：xxxxxx.TDX |
| trade_date | str | N | 交易日期，格式YYYYMMDD,下同 |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 板块代码 |
| trade_date | str | Y | 交易日期 |
| close | float | Y | 收盘点位 |
| open | float | Y | 开盘点位 |
| high | float | Y | 最高点位 |
| low | float | Y | 最低点位 |
| pre_close | float | Y | 昨日收盘点 |
| change | float | Y | 涨跌点位 |
| pct_change | float | Y | 涨跌幅% |
| vol | float | Y | 成交量（手） |
| amount | float | Y | 成交额（万元）, 对于期货指数，该字段存储持仓量 |
| rise | str | Y | 收盘涨速% |
| vol_ratio | float | Y | 量比 |
| turnover_rate | float | Y | 换手% |
| swing | float | Y | 振幅% |
| up_num | int | Y | 上涨家数 |
| down_num | int | Y | 下跌家数 |
| limit_up_num | int | Y | 涨停家数 |
| limit_down_num | int | Y | 跌停家数 |
| lu_days | int | Y | 连涨天数 |
| 3day | float | Y | 3日涨幅% |
| 5day | float | Y | 5日涨幅% |
| 10day | float | Y | 10日涨幅% |
| 20day | float | Y | 20日涨幅% |
| 60day | float | Y | 60日涨幅% |
| mtd | float | Y | 月初至今% |
| ytd | float | Y | 年初至今% |
| 1year | float | Y | 一年涨幅% |
| pe | str | Y | 市盈率 |
| pb | str | Y | 市净率 |
| float_mv | float | Y | 流通市值(亿) |
| ab_total_mv | float | Y | AB股总市值（亿） |
| float_share | float | Y | 流通股(亿) |
| total_share | float | Y | 总股本(亿) |
| bm_buy_net | float | Y | 主买净额(元) |
| bm_buy_ratio | float | Y | 主买占比% |
| bm_net | float | Y | 主力净额 |
| bm_ratio | float | Y | 主力占比% |

接口示例
数据示例


---

### [347] 榜单数据（KP）  ·  股票数据 / 打板专题数据
(api: kpl_list | 输出字段: 24 | PIT字段: 否)

# (doc_id=347)  https://tushare.pro/document/2?doc_id=347

## 开盘啦榜单数据
接口：kpl_list 描述：获取涨停、跌停、炸板等榜单数据 限量：单次最大8000条数据，可根据日期循环获取历史数据 积分：5000积分每分钟可以请求200次每天总量1万次，8000积分以上每分钟500次每天总量不限制，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码 |
| trade_date | str | N | 交易日期 |
| tag | str | N | 板单类型（涨停/炸板/跌停/自然涨停/竞价，默认为涨停) |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 代码 |
| name | str | Y | 名称 |
| trade_date | str | Y | 交易时间 |
| lu_time | str | Y | 涨停时间 |
| ld_time | str | Y | 跌停时间 |
| open_time | str | Y | 开板时间 |
| last_time | str | Y | 最后涨停时间 |
| lu_desc | str | Y | 涨停原因 |
| tag | str | Y | 标签 |
| theme | str | Y | 板块 |
| net_change | float | Y | 主力净额(元) |
| bid_amount | float | Y | 竞价成交额(元) |
| status | str | Y | 状态（N连板） |
| bid_change | float | Y | 竞价净额 |
| bid_turnover | float | Y | 竞价换手% |
| lu_bid_vol | float | Y | 涨停委买额 |
| pct_chg | float | Y | 涨跌幅% |
| bid_pct_chg | float | Y | 竞价涨幅% |
| rt_pct_chg | float | Y | 实时涨幅% |
| limit_order | float | Y | 封单 |
| amount | float | Y | 成交额 |
| turnover_rate | float | Y | 换手率% |
| free_float | float | Y | 实际流通 |
| lu_limit_order | float | Y | 最大封单 |

接口用法
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：kpl_list 描述：获取涨停、跌停、炸板等榜单数据 限量：单次最大8000条数据，可根据日期循环获取历史数据 积分：5000积分每分钟可以请求200次每天总量1万次，8000积分以上每分钟500次每天总量不限制，具体请参阅 积分获取办法


---

### [351] 题材成分（KP）  ·  股票数据 / 打板专题数据
(api: kpl_concept_cons | 输出字段: 7 | PIT字段: 否)

# (doc_id=351)  https://tushare.pro/document/2?doc_id=351

## 开盘啦题材成分
接口：kpl_concept_cons 描述：获取概念题材的成分股 限量：单次最大3000条，可根据代码和日期循环获取全部数据 积分：5000积分可提取数据，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | N | 交易日期（YYYYMMDD格式） |
| ts_code | str | N | 题材代码（xxxxxx.KP格式） |
| con_code | str | N | 成分代码（xxxxxx.SH格式） |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 题材ID |
| name | str | Y | 题材名称 |
| con_name | str | Y | 股票名称 |
| con_code | str | Y | 股票代码 |
| trade_date | str | Y | 交易日期 |
| desc | str | Y | 描述 |
| hot_num | int | Y | 人气值 |

接口用法
数据样例


---

### [421] 题材数据（DC）  ·  股票数据 / 打板专题数据
(api: dc_concept | 输出字段: 12 | PIT字段: 否)

# (doc_id=421)  https://tushare.pro/document/2?doc_id=421

## 题材库
## 接口介绍
接口：dc_concept 描述：获取概念题材列表，每天盘后更新 限量：单次最大5000，可根据日期循环获取历史数据,（数据从20260203开始） 积分：6000积分可提取数据，具体请参阅 积分获取办法
## 输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | N | 交易日期 |
| theme_code | str | N | 题材代码(xxxxxx.DC格式) |
| name | str | N | 题材名称 |

## 输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| theme_code | str | Y | 题材code |
| trade_date | str | Y | 交易日期 |
| name | str | Y | 名称 |
| pct_change | str | Y | 涨跌幅 |
| hot | str | Y | 热度 |
| sort | str | Y | 排名 |
| strength | str | Y | 强度 |
| z_t_num | str | Y | 涨停数量 |
| main_change | str | Y | 主力净流入（元） |
| lead_stock | str | Y | 领涨股票 |
| lead_stock_code | str | Y | 领涨股票code |
| lead_stock_pct_change | str | Y | 领涨股票涨跌幅 |

## 代码示例
## 数据结果
| theme_code | trade_date | name | pct_change | hot | sort | strength | z_t_num | main_change | lead_stock | lead_stock_code | lead_stock_pct_change |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 000053.DC | 20260204 | 可燃冰 | 3.98 | 1087 | 188 | 1864 | 2 | 167636450.76 | 中集集团 | 000039.SZ | 10.03 |
| 000053.DC | 20260203 | 可燃冰 | 1.65 | 880 | 399 | 773 | 1 | 229883964.11 | 中集集团 | 000039.SZ | 9.97 |


## [PIT / 更新口径 — 自动标记]
- (正文) 接口：dc_concept 描述：获取概念题材列表，每天盘后更新 限量：单次最大5000，可根据日期循环获取历史数据,（数据从20260203开始） 积分：6000积分可提取数据，具体请参阅 积分获取办法


---

### [422] 题材成分（DC）  ·  股票数据 / 打板专题数据
(api: dc_concept_cons | 输出字段: 8 | PIT字段: 否)

# (doc_id=422)  https://tushare.pro/document/2?doc_id=422

## 题材成分
## 接口介绍
接口：dc_concept_cons 描述：获取概念题材的成分股，每天盘后更新 限量：单次最大3000，可根据日期循环获取历史数据,（数据从20260203开始） 积分：6000积分可提取数据，具体请参阅 积分获取办法
## 输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码 |
| trade_date | str | N | 交易日期 |
| theme_code | str | N | 题材代码 |

## 输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| trade_date | str | Y | 交易日期 |
| name | str | Y | 名称 |
| theme_code | str | Y | 主题code |
| industry_code | str | Y | 所属行业code |
| industry | str | Y | 所属行业 |
| reason | str | Y | 入选原因 |
| hot_num | str | Y | 热点排行 |

## 代码示例
## 数据结果
| ts_code | trade_date | name | theme_code | industry_code | industry | reason | hot_num |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 000619.SZ | 20260204 | 海螺新材 | 000057.DC | BK0476 | 装修建材 | 公司主要从事中高档塑料型材、 板材、 门窗、 模具、 塑料改性剂的生产、 销售以及科研开发, 产品包括白色、 彩色、 木纹共挤、 木塑复合和覆膜异型材以及塑料栅栏、卷帘窗、 百叶窗等装饰异型材, 主要用于门窗加工制作及房屋装饰装修。海螺型材产销量连续多年位居行业首位。 | 2834 |
| 000619.SZ | 20260204 | 海螺新材 | 000113.DC | BK0476 | 装修建材 | 2019年9月27日回复称公司积极关注和拓展装配式建筑市场,目前已经有门窗产品应用到了装配式建筑。 | 2834 |
| 000619.SZ | 20260204 | 海螺新材 | 000654.DC | BK0476 | 装修建材 | None | 2834 |
| 000619.SZ | 20260203 | 海螺新材 | 000113.DC | BK0476 | 装修建材 | 2019年9月27日回复称公司积极关注和拓展装配式建筑市场,目前已经有门窗产品应用到了装配式建筑。 | 4104 |
| 000619.SZ | 20260203 | 海螺新材 | 000057.DC | BK0476 | 装修建材 | 公司主要从事中高档塑料型材、 板材、 门窗、 模具、 塑料改性剂的生产、 销售以及科研开发, 产品包括白色、 彩色、 木纹共挤、 木塑复合和覆膜异型材以及塑料栅栏、卷帘窗、 百叶窗等装饰异型材, 主要用于门窗加工制作及房屋装饰装修。海螺型材产销量连续多年位居行业首位。 | 4104 |
| 000619.SZ | 20260203 | 海螺新材 | 000654.DC | BK0476 | 装修建材 | None | 4104 |


## [PIT / 更新口径 — 自动标记]
- (正文) 接口：dc_concept_cons 描述：获取概念题材的成分股，每天盘后更新 限量：单次最大3000，可根据日期循环获取历史数据,（数据从20260203开始） 积分：6000积分可提取数据，具体请参阅 积分获取办法


---

### [384] ETF专题  ·  (顶级)
(api: — | 输出字段: 0 | PIT字段: 否)

# (doc_id=384)  https://tushare.pro/document/2?doc_id=384


---

### [385] ETF基本信息  ·  ETF专题
(api: etf_basic | 输出字段: 14 | PIT字段: 否)

# (doc_id=385)  https://tushare.pro/document/2?doc_id=385

## ETF基础信息
接口：etf_basic 描述：获取国内ETF基础信息，包括了QDII。数据来源与沪深交易所公开披露信息。 限量：单次请求最大放回5000条数据（当前ETF总数未超过2000） 权限：用户积8000积分可调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | ETF代码（带.SZ/.SH后缀的6位数字，如：159526.SZ） |
| index_code | str | N | 跟踪指数代码 |
| list_date | str | N | 上市日期（格式：YYYYMMDD） |
| list_status | str | N | 上市状态（L上市 D退市 P待上市） |
| exchange | str | N | 交易所（SH上交所 SZ深交所） |
| mgr | str | N | 管理人（简称，e.g.华夏基金) |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 基金交易代码 |
| csname | str | Y | ETF中文简称 |
| extname | str | Y | ETF扩位简称(对应交易所简称) |
| cname | str | Y | 基金中文全称 |
| index_code | str | Y | ETF基准指数代码 |
| index_name | str | Y | ETF基准指数中文全称 |
| setup_date | str | Y | 设立日期（格式：YYYYMMDD） |
| list_date | str | Y | 上市日期（格式：YYYYMMDD） |
| list_status | str | Y | 存续状态（L上市 D退市 P待上市） |
| exchange | str | Y | 交易所（上交所SH 深交所SZ） |
| mgr_name | str | Y | 基金管理人简称 |
| custod_name | str | Y | 基金托管人名称 |
| mgt_fee | float | Y | 基金管理人收取的费用 |
| etf_type | str | Y | 基金投资通道类型（境内、QDII） |

接口示例
数据示例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：etf_basic 描述：获取国内ETF基础信息，包括了QDII。数据来源与沪深交易所公开披露信息。 限量：单次请求最大放回5000条数据（当前ETF总数未超过2000） 权限：用户积8000积分可调取，具体请参阅 积分获取办法


---

### [386] ETF跟踪指数  ·  ETF专题
(api: etf_index | 输出字段: 8 | PIT字段: 是)

# (doc_id=386)  https://tushare.pro/document/2?doc_id=386

## ETF基准指数列表
接口：etf_index 描述：获取ETF基准指数列表信息 限量：单次请求最大返回5000行数据（当前未超过2000个） 权限：用户积累8000积分可调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 指数代码 |
| pub_date | str | N | 发布日期（格式：YYYYMMDD） |
| base_date | str | N | 指数基期（格式：YYYYMMDD） |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 指数代码 |
| indx_name | str | Y | 指数全称 |
| indx_csname | str | Y | 指数简称 |
| pub_party_name | str | Y | 指数发布机构 |
| pub_date | str | Y | 指数发布日期 |
| base_date | str | Y | 指数基日 |
| bp | float | Y | 指数基点(点) |
| adj_circle | str | Y | 指数成份证券调整周期 |

接口示例
数据示例

## [PIT / 更新口径 — 自动标记]
- (字段) `pub_date` — str N 发布日期（格式：YYYYMMDD）  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `pub_date` — str Y 指数发布日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [416] ETF实时分钟  ·  ETF专题
(api: rt_etf_min | 输出字段: 8 | PIT字段: 否)

# (doc_id=416)  https://tushare.pro/document/2?doc_id=416

## ETF实时分钟
接口：rt_etf_min 描述：获取ETF实时分钟数据，包括1~60min 限量：单次最大1000行数据，可以通过ETF代码提取数据，支持逗号分隔的多个代码同时提取 权限：正式权限请参阅 权限说明
注：支持股票当日开盘以来的所有ETF历史分钟数据提取，接口名：rt_etf_min_daily（仅支持一个个代码提取，不同同时提取多个），可以 在线开通 权限。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| freq | str | Y | 1MIN,5MIN,15MIN,30MIN,60MIN （大写） |
| ts_code | str | Y | 支持单个和多个：589960.SH 或者 589960.SH,159100.SZ |

freq参数说明
| freq | 说明 |
| --- | --- |
| 1MIN | 1分钟 |
| 5MIN | 5分钟 |
| 15MIN | 15分钟 |
| 30MIN | 30分钟 |
| 60MIN | 60分钟 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| time | None | Y | 交易时间 |
| open | float | Y | 开盘价 |
| close | float | Y | 收盘价 |
| high | float | Y | 最高价 |
| low | float | Y | 最低价 |
| vol | float | Y | 成交量(股） |
| amount | float | Y | 成交额（元） |

接口用法


---

### [387] ETF历史分钟  ·  ETF专题
(api: etf_mins | 输出字段: 8 | PIT字段: 否)

# (doc_id=387)  https://tushare.pro/document/2?doc_id=387

## ETF历史分钟行情
接口：etf_mins 描述：获取ETF分钟数据，支持1min/5min/15min/30min/60min行情，提供Python SDK和 http Restful API两种方式 限量：单次最大8000行数据，可以通过股票代码和时间循环获取，本接口可以提供超过10年ETF历史分钟数据 权限：正式权限请参阅 权限说明
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | ETF代码，e.g. 159001.SZ |
| freq | str | Y | 分钟频度（1min/5min/15min/30min/60min） |
| start_date | datetime | N | 开始日期 格式：2025-06-01 09:00:00 |
| end_date | datetime | N | 结束时间 格式：2025-06-20 19:00:00 |

freq参数说明
| freq | 说明 |
| --- | --- |
| 1min | 1分钟 |
| 5min | 5分钟 |
| 15min | 15分钟 |
| 30min | 30分钟 |
| 60min | 60分钟 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | ETF代码 |
| trade_time | str | Y | 交易时间 |
| open | float | Y | 开盘价 |
| close | float | Y | 收盘价 |
| high | float | Y | 最高价 |
| low | float | Y | 最低价 |
| vol | int | Y | 成交量（股） |
| amount | float | Y | 成交金额（元） |

接口用法
数据样例


---

### [400] ETF实时日线  ·  ETF专题
(api: rt_etf_k | 输出字段: 13 | PIT字段: 否)

# (doc_id=400)  https://tushare.pro/document/2?doc_id=400

## ETF实时日线
接口：rt_etf_k 描述：获取ETF实时日k线行情，支持按ETF代码或代码通配符一次性提取全部ETF实时日k线行情 积分：本接口是单独开权限的数据，单独申请权限请参考 权限列表
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 支持通配符方式，e.g. 5*.SH、15*.SZ、159101.SZ |
| topic | str | Y | 分类参数，取上海ETF时，需要输入'HQ_FND_TICK'，参考下面例子 |

注：ts_code代码一定要带 .SH/.SZ/.BJ 后缀
输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | ETF代码 |
| name | None | Y | ETF名称 |
| pre_close | float | Y | 昨收价 |
| high | float | Y | 最高价 |
| open | float | Y | 开盘价 |
| low | float | Y | 最低价 |
| close | float | Y | 收盘价（最新价） |
| vol | int | Y | 成交量（股） |
| amount | int | Y | 成交金额（元） |
| num | int | Y | 开盘以来成交笔数 |
| ask_volume1 | int | N | 委托卖盘（股） |
| bid_volume1 | int | N | 委托买盘（股） |
| trade_time | str | N | 交易时间 |

接口示例
数据示例


---

### [127] ETF日线行情  ·  ETF专题
(api: fund_daily | 输出字段: 11 | PIT字段: 否)

# (doc_id=127)  https://tushare.pro/document/2?doc_id=127

## ETF日线行情
接口：fund_daily 描述：获取ETF行情每日收盘后成交数据，历史超过10年 限量：单次最大5000行记录，可以根据ETF代码和日期循环获取历史，总量不限制 积分：需要至少5000积分才可以调取，8000积分频次更高，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 基金代码 |
| trade_date | str | N | 交易日期(YYYYMMDD格式，下同) |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS代码 |
| trade_date | str | Y | 交易日期 |
| open | float | Y | 开盘价(元) |
| high | float | Y | 最高价(元) |
| low | float | Y | 最低价(元) |
| close | float | Y | 收盘价(元) |
| pre_close | float | Y | 昨收盘价(元) |
| change | float | Y | 涨跌额(元) |
| pct_chg | float | Y | 涨跌幅(%) |
| vol | float | Y | 成交量(手) |
| amount | float | Y | 成交额(千元) |

接口示例
数据示例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：fund_daily 描述：获取ETF行情每日收盘后成交数据，历史超过10年 限量：单次最大5000行记录，可以根据ETF代码和日期循环获取历史，总量不限制 积分：需要至少5000积分才可以调取，8000积分频次更高，具体请参阅 积分获取办法


---

### [199] ETF复权因子  ·  ETF专题
(api: fund_adj | 输出字段: 3 | PIT字段: 否)

# (doc_id=199)  https://tushare.pro/document/2?doc_id=199

## 基金复权因子
接口：fund_adj 描述：获取基金复权因子，用于计算基金复权行情 限量：单次最大提取2000行记录，可循环提取，数据总量不限制 积分：用户积600积分可调取，超过5000积分以上频次相对较高。具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | TS基金代码（支持多只基金输入） |
| trade_date | str | N | 交易日期（格式：yyyymmdd，下同） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |
| offset | str | N | 开始行数 |
| limit | str | N | 最大行数 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | ts基金代码 |
| trade_date | str | Y | 交易日期 |
| adj_factor | float | Y | 复权因子 |

接口使用
数据示例


---

### [408] ETF份额规模  ·  ETF专题
(api: etf_share_size | 输出字段: 8 | PIT字段: 否)

# (doc_id=408)  https://tushare.pro/document/2?doc_id=408

## ETF份额规模
## 接口介绍
接口：etf_share_size 描述：获取沪深ETF每日份额和规模数据，能体现规模份额的变化，掌握ETF资金动向，同时提供每日净值和收盘价；数据指标是分批入库，建议在每日19点后提取；另外，涉及海外的ETF数据更新会晚一些属于正常情况。 限量：单次最大5000条，可根据代码或日期循环提取 积分：需要8000积分可以调取，具体请参阅 积分获取办法
## 输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 基金代码 （可从ETF基础信息接口提取） |
| trade_date | str | N | 交易日期（YYYYMMDD格式，下同） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |
| exchange | str | N | 交易所（SSE上交所 SZSE深交所） |

## 输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 交易日期 |
| ts_code | str | Y | ETF代码 |
| etf_name | str | Y | 基金名称 |
| total_share | float | Y | 总份额（万份） |
| total_size | float | Y | 总规模（万元） |
| nav | float | N | 基金份额净值(元) |
| close | float | N | 收盘价（元） |
| exchange | str | Y | 交易所（SSE上交所 SZSE深交所 BSE北交所） |

## 代码示例
## 数据结果

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：etf_share_size 描述：获取沪深ETF每日份额和规模数据，能体现规模份额的变化，掌握ETF资金动向，同时提供每日净值和收盘价；数据指标是分批入库，建议在每日19点后提取；另外，涉及海外的ETF数据更新会晚一些属于正常情况。 限量：单次最大5000条，可根据代码或日期循环提取 积分：需要8000积分可以调取，具体请参阅 积分获取办法


---

### [454] ETF实时参考  ·  ETF专题
(api: rt_etf_sz_iopv | 输出字段: 12 | PIT字段: 否)

# (doc_id=454)  https://tushare.pro/document/2?doc_id=454

## ETF实时参考
## 接口介绍
接口：rt_etf_sz_iopv 描述：ETF实时净值和申购赎回数据参考，目前只提供深市 限量：单次最大5000条，完全覆盖当前总量 权限：本接口为单独开权限的接口，跟积分多个无关。正式权限请参阅 权限说明
## 输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | ETF代码（默认为空，即一次全市场。支持单个和多个ETF过滤提取） |

## 输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_time | datetime | Y | 交易时间 |
| ts_code | str | Y | ETF代码 |
| vol | float | Y | 成交量（份） |
| num | int | Y | 成交笔数 |
| amount | float | Y | 成交金额（元） |
| price | float | Y | 最新价（元） |
| iopv | float | Y | 最近参考净值 |
| pre_iopv | float | Y | 前一日参考净值 |
| buy_num | int | Y | 申购笔数 |
| buy_vol | float | Y | 申购买量(份) |
| sell_num | int | Y | 赎回笔数 |
| sell_vol | float | Y | 赎回买量（份） |

## 代码示例
## 数据结果


---

### [460] 指数公司公告  ·  ETF专题
(api: idx_anns | 输出字段: 5 | PIT字段: 是)

# (doc_id=460)  https://tushare.pro/document/2?doc_id=460

## 指数公告
## 接口介绍
接口：idx_anns 描述：获取指数公司披露的相关公告信息，包括中证指数、国证指数、恒生指数和华证指数的及时与历史公告信息，跟踪指数最新信息和发展方向。 限量：单次最大返回1000条数据，可根据日期循环提取 积分：需要6000积分可以调取，具体请参阅 积分获取办法
## 输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ann_date | str | N | 公告日期（YYYYMMDD格式，下同） |
| start_date | str | N | 公告开始日期 |
| end_date | str | N | 公告结束日期 |
| src | str | N | 信息来源（中证指数、国证指数、恒生指数、华证指数） |

## 输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ann_date | str | Y | 公告日期 |
| title | str | Y | 标题 |
| url | str | Y | 链接 |
| source | str | Y | 来源 |
| type | str | Y | 类型(指数发布、指数修订、指数更名、其他） |

## 代码示例
## 数据结果

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：idx_anns 描述：获取指数公司披露的相关公告信息，包括中证指数、国证指数、恒生指数和华证指数的及时与历史公告信息，跟踪指数最新信息和发展方向。 限量：单次最大返回1000条数据，可根据日期循环提取 积分：需要6000积分可以调取，具体请参阅 积分获取办法
- (字段) `ann_date` — str N 公告日期（YYYYMMDD格式，下同）  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `ann_date` — str Y 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [93] 指数专题  ·  (顶级)
(api: — | 输出字段: 0 | PIT字段: 否)

# (doc_id=93)  https://tushare.pro/document/2?doc_id=93

## 指数数据
获取指数相关数据，为用户提供包括成分、权重和行情在内的数据。目前已经发布的数据如下：
指数基本信息
指数日线行情
指数成分和权重数据


---

### [94] 指数基本信息  ·  指数专题
(api: index_basic | 输出字段: 13 | PIT字段: 否)

# (doc_id=94)  https://tushare.pro/document/2?doc_id=94

## 指数基本信息
接口：index_basic，可以通过 数据工具 调试和查看数据。 描述：获取指数基础信息。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | TS指数代码 |
| symbol | str | N | 指数代码，支持多值输入，如000300,000001 |
| name | str | N | 指数简称 |
| market | str | N | 交易所或服务商(默认SSE，详见下方说明) |
| publisher | str | N | 发布商 |
| category | str | N | 指数类别 |

输出参数
| 名称 | 类型 | 描述 |
| --- | --- | --- |
| ts_code | str | TS代码 |
| name | str | 简称 |
| fullname | str | 指数全称 |
| market | str | 市场 |
| publisher | str | 发布方 |
| index_type | str | 指数风格 |
| category | str | 指数类别 |
| base_date | str | 基期 |
| base_point | float | 基点 |
| list_date | str | 发布日期 |
| weight_rule | str | 加权方式 |
| desc | str | 描述 |
| exp_date | str | 终止日期 |

市场说明(market)
| 市场代码 | 说明 |
| --- | --- |
| MSCI | MSCI指数 |
| CSI | 中证指数 |
| SSE | 上交所指数 |
| SZSE | 深交所指数 |
| CICC | 中金指数 |
| SW | 申万指数 |
| OTH | 其他指数 |

指数列表
主题指数
规模指数
策略指数
风格指数
综合指数
成长指数
价值指数
有色指数
化工指数
能源指数
其他指数
外汇指数
基金指数
商品指数
债券指数
行业指数
贵金属指数
农副产品指数
软商品指数
油脂油料指数
非金属建材指数
煤焦钢矿指数
谷物指数
接口使用
数据样例


---

### [95] 指数日线行情  ·  指数专题
(api: index_daily | 输出字段: 11 | PIT字段: 否)

# (doc_id=95)  https://tushare.pro/document/2?doc_id=95

## 指数日线行情
接口：index_daily，可以通过 数据工具 调试和查看数据。 描述：获取指数每日行情，还可以通过bar接口获取。由于服务器压力，目前规则是单次调取最多取8000行记录，可以设置start和end日期补全。指数行情也可以通过 通用行情接口 获取数据。本接口不包含 申万行业指数行情数据 。 权限：用户累积2000积分可调取，5000积分以上频次相对较高，具体请参阅 积分获取办法
注意：深证成指（399001.SZ）被普遍看作反映深证A股整体表现的大盘，而实际上该指数只包含500只成分股。而各类行情软件上展示的成交量、成交金额是深市所有A股的股票成交情况，如果需要获得与行情软件上一样的成交数据，可以调取深证A指（399107.SZ）。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 指数代码，来源 指数基础信息接口 |
| trade_date | str | N | 交易日期 （日期格式：YYYYMMDD，下同） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 描述 |
| --- | --- | --- |
| ts_code | str | TS指数代码 |
| trade_date | str | 交易日 |
| close | float | 收盘点位 |
| open | float | 开盘点位 |
| high | float | 最高点位 |
| low | float | 最低点位 |
| pre_close | float | 昨日收盘点 |
| change | float | 涨跌点 |
| pct_chg | float | 涨跌幅（%） |
| vol | float | 成交量（手） |
| amount | float | 成交额（千元） |

接口使用
数据样例


---

### [403] 指数实时日线  ·  指数专题
(api: rt_idx_k | 输出字段: 10 | PIT字段: 否)

# (doc_id=403)  https://tushare.pro/document/2?doc_id=403

## 交易所指数实时日线
接口：rt_idx_k 描述：获取交易所指数实时日线行情，支持按代码或代码通配符一次性提取全部交易所指数实时日k线行情 积分：本接口是单独开权限的数据，单独申请权限请参考 权限列表
## 输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 指数代码，支持通配符方式，e.g. 0*.SH、3*.SZ、000001.SH |

## 输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 指数代码 |
| name | str | Y | 指数名称 |
| trade_time | str | Y | 交易时间 |
| close | float | Y | 现价 |
| pre_close | float | Y | 昨收 |
| high | float | Y | 最高价 |
| open | float | Y | 开盘价 |
| low | float | Y | 最低价 |
| vol | float | Y | 成交量 |
| amount | float | Y | 成交金额（元） |

## 代码示例
## 数据结果


---

### [420] 指数实时分钟  ·  指数专题
(api: rt_idx_min | 输出字段: 8 | PIT字段: 否)

# (doc_id=420)  https://tushare.pro/document/2?doc_id=420

## A股实时分钟
接口：rt_idx_min 描述：获取交易所指数实时分钟数据，包括1~60min 限量：单次最大1000行数据，可以通过股票代码提取数据，支持逗号分隔的多个代码同时提取 权限：正式权限请参阅 权限说明
注：支持股票当日开盘以来的所有历史分钟数据提取，接口名：rt_idx_min_daily（仅支持一个个指数提取，不同同时提取多个），可以 在线开通 权限。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| freq | str | Y | 1MIN,5MIN,15MIN,30MIN,60MIN （大写） |
| ts_code | str | Y | 支持单个和多个：000001.SH 或者 000001.SH,399300.SZ |

freq参数说明
| freq | 说明 |
| --- | --- |
| 1MIN | 1分钟 |
| 5MIN | 5分钟 |
| 15MIN | 15分钟 |
| 30MIN | 30分钟 |
| 60MIN | 60分钟 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| time | None | Y | 交易时间 |
| open | float | Y | 开盘价 |
| close | float | Y | 收盘价 |
| high | float | Y | 最高价 |
| low | float | Y | 最低价 |
| vol | float | Y | 成交量(股） |
| amount | float | Y | 成交额（元） |

接口用法


---

### [171] 指数周线行情  ·  指数专题
(api: index_weekly | 输出字段: 11 | PIT字段: 否)

# (doc_id=171)  https://tushare.pro/document/2?doc_id=171

## 指数周线行情
接口：index_weekly 描述：获取指数周线行情 限量：单次最大1000行记录，可分批获取，总量不限制 积分：用户需要至少600积分才可以调取，积分越多频次越高，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | TS代码 |
| trade_date | str | N | 交易日期 |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS指数代码 |
| trade_date | str | Y | 交易日 |
| close | float | Y | 收盘点位 |
| open | float | Y | 开盘点位 |
| high | float | Y | 最高点位 |
| low | float | Y | 最低点位 |
| pre_close | float | Y | 昨日收盘点 |
| change | float | Y | 涨跌点位 |
| pct_chg | float | Y | 涨跌幅 |
| vol | float | Y | 成交量（手） |
| amount | float | Y | 成交额（千元） |

接口用法
或者
数据样例


---

### [419] 指数历史分钟  ·  指数专题
(api: idx_mins | 输出字段: 8 | PIT字段: 否)

# (doc_id=419)  https://tushare.pro/document/2?doc_id=419

## 股票历史分钟行情
接口：idx_mins 描述：获取交易所指数分钟数据，支持1min/5min/15min/30min/60min行情，提供Python SDK和 http Restful API两种方式 限量：单次最大8000行数据，可以通过指数代码和时间循环获取，本接口可以提供超过10年历史分钟数据 权限：需单独开权限，正式权限请参阅 权限说明 ，可以 在线开通 分钟权限。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 指数代码，e.g. 000001.SH |
| freq | str | Y | 分钟频度（1min/5min/15min/30min/60min） |
| start_date | datetime | N | 开始日期 格式：2023-08-25 09:00:00 |
| end_date | datetime | N | 结束时间 格式：2023-08-25 19:00:00 |

freq参数说明
| freq | 说明 |
| --- | --- |
| 1min | 1分钟 |
| 5min | 5分钟 |
| 15min | 15分钟 |
| 30min | 30分钟 |
| 60min | 60分钟 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 指数代码 |
| trade_time | str | Y | 交易时间 |
| open | float | Y | 开盘价 |
| close | float | Y | 收盘价 |
| high | float | Y | 最高价 |
| low | float | Y | 最低价 |
| vol | int | Y | 成交量(股) |
| amount | float | Y | 成交金额（元） |

接口用法
数据样例


---

### [172] 指数月线行情  ·  指数专题
(api: index_monthly | 输出字段: 11 | PIT字段: 否)

# (doc_id=172)  https://tushare.pro/document/2?doc_id=172

## 指数月线行情
接口：index_monthly 描述：获取指数月线行情,每月更新一次 限量：单次最大1000行记录,可多次获取,总量不限制 积分：用户需要至少600积分才可以调取，积分越多频次越高，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | TS代码 |
| trade_date | str | N | 交易日期 |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS指数代码 |
| trade_date | str | Y | 交易日 |
| close | float | Y | 收盘点位 |
| open | float | Y | 开盘点位 |
| high | float | Y | 最高点位 |
| low | float | Y | 最低点位 |
| pre_close | float | Y | 昨日收盘点 |
| change | float | Y | 涨跌点位 |
| pct_chg | float | Y | 涨跌幅 |
| vol | float | 成交量（手） |  |
| amount | float | 成交额（千元） |  |

接口用法
或者
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：index_monthly 描述：获取指数月线行情,每月更新一次 限量：单次最大1000行记录,可多次获取,总量不限制 积分：用户需要至少600积分才可以调取，积分越多频次越高，具体请参阅 积分获取办法


---

### [96] 指数成分和权重  ·  指数专题
(api: index_weight | 输出字段: 4 | PIT字段: 否)

# (doc_id=96)  https://tushare.pro/document/2?doc_id=96

## 指数成分和权重
接口：index_weight 描述：获取各类指数成分和权重， 月度数据 ，建议输入参数里开始日期和结束日分别输入当月第一天和最后一天的日期。 来源：指数公司网站公开数据 积分：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| index_code | str | Y | 指数代码，来源 指数基础信息接口 |
| trade_date | str | N | 交易日期（格式YYYYMMDD，下同） |
| start_date | str | N | 开始日期 |
| end_date | None | N | 结束日期 |

输出参数
| 名称 | 类型 | 描述 |
| --- | --- | --- |
| index_code | str | 指数代码 |
| con_code | str | 成分代码 |
| trade_date | str | 交易日期 |
| weight | float | 权重 |

接口调用
数据样例


---

### [128] 大盘指数每日指标  ·  指数专题
(api: index_dailybasic | 输出字段: 12 | PIT字段: 否)

# (doc_id=128)  https://tushare.pro/document/2?doc_id=128

## 大盘指数每日指标
接口：index_dailybasic，可以通过 数据工具 调试和查看数据。 描述：目前只提供上证综指，深证成指，上证50，中证500，中小板指，创业板指的每日指标数据 数据来源：Tushare社区统计计算 数据历史：从2004年1月开始提供 数据权限：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | N | 交易日期 （格式：YYYYMMDD，比如20181018，下同） |
| ts_code | str | N | TS代码 |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

注：trade_date，ts_code 至少要输入一个参数，单次限量3000条（即，单一指数单次可提取超过12年历史），总量不限制。
输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS代码 |
| trade_date | str | Y | 交易日期 |
| total_mv | float | Y | 当日总市值（元） |
| float_mv | float | Y | 当日流通市值（元） |
| total_share | float | Y | 当日总股本（股） |
| float_share | float | Y | 当日流通股本（股） |
| free_share | float | Y | 当日自由流通股本（股） |
| turnover_rate | float | Y | 换手率 |
| turnover_rate_f | float | Y | 换手率(基于自由流通股本) |
| pe | float | Y | 市盈率 |
| pe_ttm | float | Y | 市盈率TTM |
| pb | float | Y | 市净率 |

接口示例
数据示例


---

### [181] 申万行业分类  ·  指数专题
(api: index_classify | 输出字段: 7 | PIT字段: 否)

# (doc_id=181)  https://tushare.pro/document/2?doc_id=181

## 申万行业分类
接口：index_classify 描述：获取申万行业分类，可以获取申万2014年版本（28个一级分类，104个二级分类，227个三级分类）和2021年本版（31个一级分类，134个二级分类，346个三级分类）列表信息 权限：用户需2000积分可以调取，具体请参阅 积分获取办法
申万行业指数分类标准2021版
注：指数成分股小于5条该指数行情不发布
| 行业代码 | 指数代码 | 一级行业 | 二级行业 | 三级行业 | 指数类别 | 是否发布 | 变动原因 | 成分股数 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 110000 | 801010 | 农林牧渔 |  |  | 一级行业 | 1 | 2021保留 | 100 |
| 110100 | 801016 | 农林牧渔 | 种植业 |  | 二级行业 | 1 | 2021保留 | 20 |
| 110101 | 850111 | 农林牧渔 | 种植业 | 种子 | 三级行业 | 1 | 2021改名 | 8 |
| 110102 | 850112 | 农林牧渔 | 种植业 | 粮食种植 | 三级行业 | 0 | 2021保留 | 2 |
| 110103 | 850113 | 农林牧渔 | 种植业 | 其他种植业 | 三级行业 | 1 | 2021保留 | 6 |
| 110104 | 850114 | 农林牧渔 | 种植业 | 食用菌 | 三级行业 | 0 | 2021新增 | 4 |
| 110200 | 801015 | 农林牧渔 | 渔业 |  | 二级行业 | 1 | 2021保留 | 11 |
| 110201 | 850121 | 农林牧渔 | 渔业 | 海洋捕捞 | 三级行业 | 0 | 2021保留 | 2 |
| 110202 | 850122 | 农林牧渔 | 渔业 | 水产养殖 | 三级行业 | 1 | 2021保留 | 9 |
| 110300 | 801011 | 农林牧渔 | 林业Ⅱ |  | 二级行业 | 0 | 2021保留 | 3 |
| 110301 | 850131 | 农林牧渔 | 林业Ⅱ | 林业Ⅲ | 三级行业 | 0 | 2021保留 | 3 |
| 110400 | 801014 | 农林牧渔 | 饲料 |  | 二级行业 | 1 | 2021保留 | 11 |
| 110402 | 850142 | 农林牧渔 | 饲料 | 畜禽饲料 | 三级行业 | 1 | 2021新增 | 7 |
| 110403 | 850143 | 农林牧渔 | 饲料 | 水产饲料 | 三级行业 | 0 | 2021新增 | 2 |
| 110404 | 850144 | 农林牧渔 | 饲料 | 宠物食品 | 三级行业 | 0 | 2021新增 | 2 |
| 110500 | 801012 | 农林牧渔 | 农产品加工 |  | 二级行业 | 1 | 2021保留 | 23 |
| 110501 | 850151 | 农林牧渔 | 农产品加工 | 果蔬加工 | 三级行业 | 1 | 2021保留 | 5 |
| 110502 | 850152 | 农林牧渔 | 农产品加工 | 粮油加工 | 三级行业 | 1 | 2021保留 | 6 |
| 110504 | 850154 | 农林牧渔 | 农产品加工 | 其他农产品加工 | 三级行业 | 1 | 2021保留 | 12 |
| 110700 | 801017 | 农林牧渔 | 养殖业 |  | 二级行业 | 1 | 2021改名 | 20 |
| 110702 | 850172 | 农林牧渔 | 养殖业 | 生猪养殖 | 三级行业 | 1 | 2021新增 | 9 |
| 110703 | 850173 | 农林牧渔 | 养殖业 | 肉鸡养殖 | 三级行业 | 1 | 2021新增 | 7 |
| 110704 | 850174 | 农林牧渔 | 养殖业 | 其他养殖 | 三级行业 | 0 | 2021新增 | 4 |
| 110800 | 801018 | 农林牧渔 | 动物保健Ⅱ |  | 二级行业 | 1 | 2021保留 | 10 |
| 110801 | 850181 | 农林牧渔 | 动物保健Ⅱ | 动物保健Ⅲ | 三级行业 | 1 | 2021保留 | 10 |
| 110900 | 801019 | 农林牧渔 | 农业综合Ⅱ |  | 二级行业 | 0 | 2021新增 | 2 |
| 110901 | 850191 | 农林牧渔 | 农业综合Ⅱ | 农业综合Ⅲ | 三级行业 | 0 | 2021新增 | 2 |
| 220000 | 801030 | 基础化工 |  |  | 一级行业 | 1 | 2021改名 | 311 |
| 220200 | 801033 | 基础化工 | 化学原料 |  | 二级行业 | 1 | 2021保留 | 52 |
| 220201 | 850321 | 基础化工 | 化学原料 | 纯碱 | 三级行业 | 0 | 2021保留 | 4 |
| 220202 | 850322 | 基础化工 | 化学原料 | 氯碱 | 三级行业 | 1 | 2021保留 | 17 |
| 220203 | 850323 | 基础化工 | 化学原料 | 无机盐 | 三级行业 | 1 | 2021保留 | 12 |
| 220204 | 850324 | 基础化工 | 化学原料 | 其他化学原料 | 三级行业 | 1 | 2021保留 | 6 |
| 220205 | 850325 | 基础化工 | 化学原料 | 煤化工 | 三级行业 | 1 | 2021新增 | 7 |
| 220206 | 850326 | 基础化工 | 化学原料 | 钛白粉 | 三级行业 | 1 | 2021新增 | 6 |
| 220300 | 801034 | 基础化工 | 化学制品 |  | 二级行业 | 1 | 2021保留 | 109 |
| 220305 | 850335 | 基础化工 | 化学制品 | 涂料油墨 | 三级行业 | 1 | 2021改名 | 10 |
| 220307 | 850337 | 基础化工 | 化学制品 | 民爆制品 | 三级行业 | 1 | 2021保留 | 13 |
| 220308 | 850338 | 基础化工 | 化学制品 | 纺织化学制品 | 三级行业 | 1 | 2021保留 | 10 |
| 220309 | 850339 | 基础化工 | 化学制品 | 其他化学制品 | 三级行业 | 1 | 2021保留 | 37 |
| 220311 | 850382 | 基础化工 | 化学制品 | 氟化工 | 三级行业 | 1 | 2021改名 | 8 |
| 220313 | 850372 | 基础化工 | 化学制品 | 聚氨酯 | 三级行业 | 1 | 2021保留 | 8 |
| 220315 | 850135 | 基础化工 | 化学制品 | 食品及饲料添加剂 | 三级行业 | 1 | 2021新增 | 11 |
| 220316 | 850136 | 基础化工 | 化学制品 | 有机硅 | 三级行业 | 1 | 2021新增 | 9 |
| 220317 | 850137 | 基础化工 | 化学制品 | 胶黏剂及胶带 | 三级行业 | 0 | 2021新增 | 3 |
| 220400 | 801032 | 基础化工 | 化学纤维 |  | 二级行业 | 1 | 2021保留 | 21 |
| 220401 | 850341 | 基础化工 | 化学纤维 | 涤纶 | 三级行业 | 1 | 2021保留 | 8 |
| 220403 | 850343 | 基础化工 | 化学纤维 | 粘胶 | 三级行业 | 1 | 2021保留 | 5 |
| 220404 | 850344 | 基础化工 | 化学纤维 | 其他化学纤维 | 三级行业 | 0 | 2021改名 | 2 |
| 220405 | 850345 | 基础化工 | 化学纤维 | 氨纶 | 三级行业 | 0 | 2021保留 | 3 |
| 220406 | 850346 | 基础化工 | 化学纤维 | 锦纶 | 三级行业 | 0 | 2021新增 | 3 |
| 220500 | 801036 | 基础化工 | 塑料 |  | 二级行业 | 1 | 2021保留 | 57 |
| 220501 | 850351 | 基础化工 | 塑料 | 其他塑料制品 | 三级行业 | 1 | 2021保留 | 26 |
| 220503 | 850353 | 基础化工 | 塑料 | 改性塑料 | 三级行业 | 1 | 2021保留 | 13 |
| 220504 | 850354 | 基础化工 | 塑料 | 合成树脂 | 三级行业 | 1 | 2021新增 | 6 |
| 220505 | 850355 | 基础化工 | 塑料 | 膜材料 | 三级行业 | 1 | 2021新增 | 12 |
| 220600 | 801037 | 基础化工 | 橡胶 |  | 二级行业 | 1 | 2021保留 | 14 |
| 220602 | 850362 | 基础化工 | 橡胶 | 其他橡胶制品 | 三级行业 | 1 | 2021保留 | 7 |
| 220603 | 850363 | 基础化工 | 橡胶 | 炭黑 | 三级行业 | 1 | 2021保留 | 5 |
| 220604 | 850364 | 基础化工 | 橡胶 | 橡胶助剂 | 三级行业 | 0 | 2021新增 | 2 |
| 220800 | 801038 | 基础化工 | 农化制品 |  | 二级行业 | 1 | 2021新增 | 53 |
| 220801 | 850331 | 基础化工 | 农化制品 | 氮肥 | 三级行业 | 1 | 2021替换代码220301 | 5 |
| 220802 | 850332 | 基础化工 | 农化制品 | 磷肥及磷化工 | 三级行业 | 1 | 2021替换代码-改名220302 | 7 |
| 220803 | 850333 | 基础化工 | 农化制品 | 农药 | 三级行业 | 1 | 2021替换代码220303 | 28 |
| 220804 | 850336 | 基础化工 | 农化制品 | 钾肥 | 三级行业 | 0 | 2021替换代码220306 | 4 |
| 220805 | 850381 | 基础化工 | 农化制品 | 复合肥 | 三级行业 | 1 | 2021替换代码220310 | 9 |
| 220900 | 801039 | 基础化工 | 非金属材料Ⅱ |  | 二级行业 | 1 | 2021新增 | 5 |
| 220901 | 850523 | 基础化工 | 非金属材料Ⅱ | 非金属材料Ⅲ | 三级行业 | 1 | 2021替换代码240203 | 5 |
| 230000 | 801040 | 钢铁 |  |  | 一级行业 | 1 | 2021保留 | 43 |
| 230300 | 801043 | 钢铁 | 冶钢原料 |  | 二级行业 | 1 | 2021新增 | 7 |
| 230301 | 850431 | 钢铁 | 冶钢原料 | 铁矿石 | 三级行业 | 0 | 2021新增 | 4 |
| 230302 | 850432 | 钢铁 | 冶钢原料 | 冶钢辅料 | 三级行业 | 0 | 2021新增 | 3 |
| 230400 | 801044 | 钢铁 | 普钢 |  | 二级行业 | 1 | 2021新增 | 24 |
| 230401 | 850441 | 钢铁 | 普钢 | 长材 | 三级行业 | 0 | 2021新增 | 3 |
| 230402 | 850442 | 钢铁 | 普钢 | 板材 | 三级行业 | 1 | 2021新增 | 18 |
| 230403 | 850443 | 钢铁 | 普钢 | 钢铁管材 | 三级行业 | 0 | 2021新增 | 3 |
| 230500 | 801045 | 钢铁 | 特钢Ⅱ |  | 二级行业 | 1 | 2021新增 | 12 |
| 230501 | 850412 | 钢铁 | 特钢Ⅱ | 特钢Ⅲ | 三级行业 | 1 | 2021替换代码230102 | 12 |
| 240000 | 801050 | 有色金属 |  |  | 一级行业 | 1 | 2021保留 | 125 |
| 240200 | 801051 | 有色金属 | 金属新材料 |  | 二级行业 | 1 | 2021改名 | 20 |
| 240201 | 850521 | 有色金属 | 金属新材料 | 其他金属新材料 | 三级行业 | 1 | 2021改名 | 9 |
| 240202 | 850522 | 有色金属 | 金属新材料 | 磁性材料 | 三级行业 | 1 | 2021保留 | 11 |
| 240300 | 801055 | 有色金属 | 工业金属 |  | 二级行业 | 1 | 2021保留 | 56 |
| 240301 | 850551 | 有色金属 | 工业金属 | 铝 | 三级行业 | 1 | 2021保留 | 31 |
| 240302 | 850552 | 有色金属 | 工业金属 | 铜 | 三级行业 | 1 | 2021保留 | 13 |
| 240303 | 850553 | 有色金属 | 工业金属 | 铅锌 | 三级行业 | 1 | 2021保留 | 12 |
| 240400 | 801053 | 有色金属 | 贵金属 |  | 二级行业 | 1 | 2021改名 | 13 |
| 240401 | 850531 | 有色金属 | 贵金属 | 黄金 | 三级行业 | 1 | 2021保留 | 11 |
| 240402 | 850532 | 有色金属 | 贵金属 | 白银 | 三级行业 | 0 | 2021新增 | 2 |
| 240500 | 801054 | 有色金属 | 小金属 |  | 二级行业 | 1 | 2021改名 | 29 |
| 240501 | 850541 | 有色金属 | 小金属 | 稀土 | 三级行业 | 0 | 2021保留 | 4 |
| 240502 | 850542 | 有色金属 | 小金属 | 钨 | 三级行业 | 0 | 2021保留 | 4 |
| 240504 | 850544 | 有色金属 | 小金属 | 其他小金属 | 三级行业 | 1 | 2021保留 | 18 |
| 240505 | 850545 | 有色金属 | 小金属 | 钼 | 三级行业 | 0 | 2021新增 | 3 |
| 240600 | 801056 | 有色金属 | 能源金属 |  | 二级行业 | 1 | 2021新增 | 7 |
| 240601 | 850561 | 有色金属 | 能源金属 | 钴 | 三级行业 | 0 | 2021新增 | 3 |
| 240602 | 850562 | 有色金属 | 能源金属 | 镍 | 三级行业 | 0 | 2021新增 | 0 |
| 240603 | 850543 | 有色金属 | 能源金属 | 锂 | 三级行业 | 0 | 2021替换代码240503 | 4 |
| 270000 | 801080 | 电子 |  |  | 一级行业 | 1 | 2021保留 | 284 |
| 270100 | 801081 | 电子 | 半导体 |  | 二级行业 | 1 | 2021保留 | 49 |
| 270102 | 850812 | 电子 | 半导体 | 分立器件 | 三级行业 | 1 | 2021保留 | 9 |
| 270103 | 850813 | 电子 | 半导体 | 半导体材料 | 三级行业 | 1 | 2021保留 | 8 |
| 270104 | 850814 | 电子 | 半导体 | 数字芯片设计 | 三级行业 | 1 | 2021新增 | 14 |
| 270105 | 850815 | 电子 | 半导体 | 模拟芯片设计 | 三级行业 | 1 | 2021新增 | 6 |
| 270106 | 850816 | 电子 | 半导体 | 集成电路制造 | 三级行业 | 0 | 2021新增 | 1 |
| 270107 | 850817 | 电子 | 半导体 | 集成电路封测 | 三级行业 | 1 | 2021新增 | 6 |
| 270108 | 850818 | 电子 | 半导体 | 半导体设备 | 三级行业 | 1 | 2021新增 | 5 |
| 270200 | 801083 | 电子 | 元件 |  | 二级行业 | 1 | 2021保留 | 43 |
| 270202 | 850822 | 电子 | 元件 | 印制电路板 | 三级行业 | 1 | 2021保留 | 32 |
| 270203 | 850823 | 电子 | 元件 | 被动元件 | 三级行业 | 1 | 2021保留 | 11 |
| 270300 | 801084 | 电子 | 光学光电子 |  | 二级行业 | 1 | 2021保留 | 76 |
| 270301 | 850831 | 电子 | 光学光电子 | 面板 | 三级行业 | 1 | 2021改名 | 33 |
| 270302 | 850832 | 电子 | 光学光电子 | LED | 三级行业 | 1 | 2021保留 | 29 |
| 270303 | 850833 | 电子 | 光学光电子 | 光学元件 | 三级行业 | 1 | 2021保留 | 14 |
| 270400 | 801082 | 电子 | 其他电子Ⅱ |  | 二级行业 | 1 | 2021保留 | 26 |
| 270401 | 850841 | 电子 | 其他电子Ⅱ | 其他电子Ⅲ | 三级行业 | 1 | 2021保留 | 26 |
| 270500 | 801085 | 电子 | 消费电子 |  | 二级行业 | 1 | 2021改名 | 74 |
| 270503 | 850853 | 电子 | 消费电子 | 品牌消费电子 | 三级行业 | 1 | 2021新增 | 5 |
| 270504 | 850854 | 电子 | 消费电子 | 消费电子零部件及组装 | 三级行业 | 1 | 2021新增 | 69 |
| 270600 | 801086 | 电子 | 电子化学品Ⅱ |  | 二级行业 | 1 | 2021新增 | 16 |
| 270601 | 850861 | 电子 | 电子化学品Ⅱ | 电子化学品Ⅲ | 三级行业 | 1 | 2021新增 | 16 |
| 280000 | 801880 | 汽车 |  |  | 一级行业 | 1 | 2021保留 | 221 |
| 280200 | 801093 | 汽车 | 汽车零部件 |  | 二级行业 | 1 | 2021保留 | 171 |
| 280202 | 850922 | 汽车 | 汽车零部件 | 车身附件及饰件 | 三级行业 | 1 | 2021新增 | 23 |
| 280203 | 850923 | 汽车 | 汽车零部件 | 底盘与发动机系统 | 三级行业 | 1 | 2021新增 | 78 |
| 280204 | 850924 | 汽车 | 汽车零部件 | 轮胎轮毂 | 三级行业 | 1 | 2021新增 | 18 |
| 280205 | 850925 | 汽车 | 汽车零部件 | 其他汽车零部件 | 三级行业 | 1 | 2021新增 | 33 |
| 280206 | 850926 | 汽车 | 汽车零部件 | 汽车电子电气系统 | 三级行业 | 1 | 2021新增 | 19 |
| 280300 | 801092 | 汽车 | 汽车服务 |  | 二级行业 | 1 | 2021保留 | 14 |
| 280302 | 850232 | 汽车 | 汽车服务 | 汽车经销商 | 三级行业 | 1 | 2021新增 | 9 |
| 280303 | 850233 | 汽车 | 汽车服务 | 汽车综合服务 | 三级行业 | 1 | 2021新增 | 5 |
| 280400 | 801881 | 汽车 | 摩托车及其他 |  | 二级行业 | 1 | 2021改名 | 14 |
| 280401 | 858811 | 汽车 | 摩托车及其他 | 其他运输设备 | 三级行业 | 1 | 2021保留 | 6 |
| 280402 | 858812 | 汽车 | 摩托车及其他 | 摩托车 | 三级行业 | 1 | 2021新增 | 8 |
| 280500 | 801095 | 汽车 | 乘用车 |  | 二级行业 | 1 | 2021新增 | 9 |
| 280501 | 850951 | 汽车 | 乘用车 | 电动乘用车 | 三级行业 | 0 | 2021新增 | 1 |
| 280502 | 850952 | 汽车 | 乘用车 | 综合乘用车 | 三级行业 | 1 | 2021新增 | 8 |
| 280600 | 801096 | 汽车 | 商用车 |  | 二级行业 | 1 | 2021新增 | 13 |
| 280601 | 850912 | 汽车 | 商用车 | 商用载货车 | 三级行业 | 1 | 2021替换代码280102 | 7 |
| 280602 | 850913 | 汽车 | 商用车 | 商用载客车 | 三级行业 | 1 | 2021替换代码280103 | 6 |
| 330000 | 801110 | 家用电器 |  |  | 一级行业 | 1 | 2021保留 | 77 |
| 330100 | 801111 | 家用电器 | 白色家电 |  | 二级行业 | 1 | 2021保留 | 10 |
| 330102 | 851112 | 家用电器 | 白色家电 | 空调 | 三级行业 | 1 | 2021保留 | 5 |
| 330106 | 851116 | 家用电器 | 白色家电 | 冰洗 | 三级行业 | 1 | 2021新增 | 5 |
| 330200 | 801112 | 家用电器 | 黑色家电 |  | 二级行业 | 1 | 2021改名 | 9 |
| 330201 | 851121 | 家用电器 | 黑色家电 | 彩电 | 三级行业 | 0 | 2021保留 | 4 |
| 330202 | 851122 | 家用电器 | 黑色家电 | 其他黑色家电 | 三级行业 | 1 | 2021改名 | 5 |
| 330300 | 801113 | 家用电器 | 小家电 |  | 二级行业 | 1 | 2021新增 | 14 |
| 330301 | 851131 | 家用电器 | 小家电 | 厨房小家电 | 三级行业 | 1 | 2021新增 | 11 |
| 330302 | 851132 | 家用电器 | 小家电 | 清洁小家电 | 三级行业 | 0 | 2021新增 | 2 |
| 330303 | 851133 | 家用电器 | 小家电 | 个护小家电 | 三级行业 | 0 | 2021新增 | 1 |
| 330400 | 801114 | 家用电器 | 厨卫电器 |  | 二级行业 | 1 | 2021新增 | 9 |
| 330401 | 851141 | 家用电器 | 厨卫电器 | 厨房电器 | 三级行业 | 1 | 2021新增 | 6 |
| 330402 | 851142 | 家用电器 | 厨卫电器 | 卫浴电器 | 三级行业 | 0 | 2021新增 | 3 |
| 330500 | 801115 | 家用电器 | 照明设备Ⅱ |  | 二级行业 | 1 | 2021新增 | 8 |
| 330501 | 851151 | 家用电器 | 照明设备Ⅱ | 照明设备Ⅲ | 三级行业 | 1 | 2021新增 | 8 |
| 330600 | 801116 | 家用电器 | 家电零部件Ⅱ |  | 二级行业 | 1 | 2021新增 | 24 |
| 330601 | 851161 | 家用电器 | 家电零部件Ⅱ | 家电零部件Ⅲ | 三级行业 | 1 | 2021新增 | 24 |
| 330700 | 801117 | 家用电器 | 其他家电Ⅱ |  | 二级行业 | 0 | 2021新增 | 3 |
| 330701 | 851171 | 家用电器 | 其他家电Ⅱ | 其他家电Ⅲ | 三级行业 | 0 | 2021新增 | 3 |
| 340000 | 801120 | 食品饮料 |  |  | 一级行业 | 1 | 2021保留 | 113 |
| 340400 | 801124 | 食品饮料 | 食品加工 |  | 二级行业 | 1 | 2021保留 | 18 |
| 340401 | 851241 | 食品饮料 | 食品加工 | 肉制品 | 三级行业 | 1 | 2021保留 | 6 |
| 340404 | 851244 | 食品饮料 | 食品加工 | 其他食品 | 三级行业 | 0 | 2021改名 | 0 |
| 340406 | 851246 | 食品饮料 | 食品加工 | 预加工食品 | 三级行业 | 1 | 2021新增 | 7 |
| 340407 | 851247 | 食品饮料 | 食品加工 | 保健品 | 三级行业 | 1 | 2021新增 | 5 |
| 340500 | 801125 | 食品饮料 | 白酒Ⅱ |  | 二级行业 | 1 | 2021新增 | 19 |
| 340501 | 851251 | 食品饮料 | 白酒Ⅱ | 白酒Ⅲ | 三级行业 | 1 | 2021新增 | 19 |
| 340600 | 801126 | 食品饮料 | 非白酒 |  | 二级行业 | 1 | 2021新增 | 17 |
| 340601 | 851232 | 食品饮料 | 非白酒 | 啤酒 | 三级行业 | 1 | 2021替换代码340302 | 7 |
| 340602 | 851233 | 食品饮料 | 非白酒 | 其他酒类 | 三级行业 | 1 | 2021替换代码340303 | 10 |
| 340700 | 801127 | 食品饮料 | 饮料乳品 |  | 二级行业 | 1 | 2021新增 | 26 |
| 340701 | 851271 | 食品饮料 | 饮料乳品 | 软饮料 | 三级行业 | 1 | 2021新增 | 8 |
| 340702 | 851243 | 食品饮料 | 饮料乳品 | 乳品 | 三级行业 | 1 | 2021替换代码340403 | 18 |
| 340800 | 801128 | 食品饮料 | 休闲食品 |  | 二级行业 | 1 | 2021新增 | 19 |
| 340801 | 851281 | 食品饮料 | 休闲食品 | 零食 | 三级行业 | 1 | 2021新增 | 9 |
| 340802 | 851282 | 食品饮料 | 休闲食品 | 烘焙食品 | 三级行业 | 1 | 2021新增 | 8 |
| 340803 | 851283 | 食品饮料 | 休闲食品 | 熟食 | 三级行业 | 0 | 2021新增 | 2 |
| 340900 | 801129 | 食品饮料 | 调味发酵品Ⅱ |  | 二级行业 | 1 | 2021新增 | 14 |
| 340901 | 851242 | 食品饮料 | 调味发酵品Ⅱ | 调味发酵品Ⅲ | 三级行业 | 1 | 2021替换代码340402 | 14 |
| 350000 | 801130 | 纺织服饰 |  |  | 一级行业 | 1 | 2021改名 | 113 |
| 350100 | 801131 | 纺织服饰 | 纺织制造 |  | 二级行业 | 1 | 2021保留 | 38 |
| 350102 | 851312 | 纺织服饰 | 纺织制造 | 棉纺 | 三级行业 | 1 | 2021保留 | 9 |
| 350104 | 851314 | 纺织服饰 | 纺织制造 | 印染 | 三级行业 | 1 | 2021保留 | 5 |
| 350105 | 851315 | 纺织服饰 | 纺织制造 | 辅料 | 三级行业 | 1 | 2021保留 | 5 |
| 350106 | 851316 | 纺织服饰 | 纺织制造 | 其他纺织 | 三级行业 | 1 | 2021保留 | 18 |
| 350107 | 851317 | 纺织服饰 | 纺织制造 | 纺织鞋类制造 | 三级行业 | 0 | 2021新增 | 1 |
| 350200 | 801132 | 纺织服饰 | 服装家纺 |  | 二级行业 | 1 | 2021保留 | 59 |
| 350205 | 851325 | 纺织服饰 | 服装家纺 | 鞋帽及其他 | 三级行业 | 1 | 2021改名 | 16 |
| 350206 | 851326 | 纺织服饰 | 服装家纺 | 家纺 | 三级行业 | 1 | 2021保留 | 6 |
| 350208 | 851328 | 纺织服饰 | 服装家纺 | 运动服装 | 三级行业 | 0 | 2021新增 | 3 |
| 350209 | 851329 | 纺织服饰 | 服装家纺 | 非运动服装 | 三级行业 | 1 | 2021新增 | 34 |
| 350300 | 801133 | 纺织服饰 | 饰品 |  | 二级行业 | 1 | 2021新增 | 16 |
| 350301 | 851331 | 纺织服饰 | 饰品 | 钟表珠宝 | 三级行业 | 1 | 2021新增 | 14 |
| 350302 | 851332 | 纺织服饰 | 饰品 | 多品类奢侈品 | 三级行业 | 0 | 2021新增 | 0 |
| 350303 | 851333 | 纺织服饰 | 饰品 | 其他饰品 | 三级行业 | 0 | 2021新增 | 2 |
| 360000 | 801140 | 轻工制造 |  |  | 一级行业 | 1 | 2021保留 | 131 |
| 360100 | 801143 | 轻工制造 | 造纸 |  | 二级行业 | 1 | 2021保留 | 22 |
| 360102 | 851412 | 轻工制造 | 造纸 | 大宗用纸 | 三级行业 | 1 | 2021新增 | 11 |
| 360103 | 851413 | 轻工制造 | 造纸 | 特种纸 | 三级行业 | 1 | 2021新增 | 11 |
| 360200 | 801141 | 轻工制造 | 包装印刷 |  | 二级行业 | 1 | 2021保留 | 37 |
| 360202 | 851422 | 轻工制造 | 包装印刷 | 印刷 | 三级行业 | 1 | 2021新增 | 5 |
| 360203 | 851423 | 轻工制造 | 包装印刷 | 金属包装 | 三级行业 | 1 | 2021新增 | 7 |
| 360204 | 851424 | 轻工制造 | 包装印刷 | 塑料包装 | 三级行业 | 1 | 2021新增 | 5 |
| 360205 | 851425 | 轻工制造 | 包装印刷 | 纸包装 | 三级行业 | 1 | 2021新增 | 16 |
| 360206 | 851426 | 轻工制造 | 包装印刷 | 综合包装 | 三级行业 | 0 | 2021新增 | 4 |
| 360300 | 801142 | 轻工制造 | 家居用品 |  | 二级行业 | 1 | 2021改名 | 58 |
| 360306 | 851436 | 轻工制造 | 家居用品 | 瓷砖地板 | 三级行业 | 1 | 2021新增 | 10 |
| 360307 | 851437 | 轻工制造 | 家居用品 | 成品家居 | 三级行业 | 1 | 2021新增 | 14 |
| 360308 | 851438 | 轻工制造 | 家居用品 | 定制家居 | 三级行业 | 1 | 2021新增 | 13 |
| 360309 | 851439 | 轻工制造 | 家居用品 | 卫浴制品 | 三级行业 | 1 | 2021新增 | 5 |
| 360311 | 851491 | 轻工制造 | 家居用品 | 其他家居用品 | 三级行业 | 1 | 2021新增 | 16 |
| 360500 | 801145 | 轻工制造 | 文娱用品 |  | 二级行业 | 1 | 2021新增 | 14 |
| 360501 | 851451 | 轻工制造 | 文娱用品 | 文化用品 | 三级行业 | 0 | 2021新增 | 3 |
| 360502 | 851452 | 轻工制造 | 文娱用品 | 娱乐用品 | 三级行业 | 1 | 2021新增 | 11 |
| 370000 | 801150 | 医药生物 |  |  | 一级行业 | 1 | 2021保留 | 331 |
| 370100 | 801151 | 医药生物 | 化学制药 |  | 二级行业 | 1 | 2021保留 | 111 |
| 370101 | 851511 | 医药生物 | 化学制药 | 原料药 | 三级行业 | 1 | 2021保留 | 29 |
| 370102 | 851512 | 医药生物 | 化学制药 | 化学制剂 | 三级行业 | 1 | 2021保留 | 82 |
| 370200 | 801155 | 医药生物 | 中药Ⅱ |  | 二级行业 | 1 | 2021保留 | 70 |
| 370201 | 851521 | 医药生物 | 中药Ⅱ | 中药Ⅲ | 三级行业 | 1 | 2021保留 | 70 |
| 370300 | 801152 | 医药生物 | 生物制品 |  | 二级行业 | 1 | 2021保留 | 27 |
| 370302 | 851522 | 医药生物 | 生物制品 | 血液制品 | 三级行业 | 1 | 2021新增 | 6 |
| 370303 | 851523 | 医药生物 | 生物制品 | 疫苗 | 三级行业 | 1 | 2021新增 | 5 |
| 370304 | 851524 | 医药生物 | 生物制品 | 其他生物制品 | 三级行业 | 1 | 2021新增 | 16 |
| 370400 | 801154 | 医药生物 | 医药商业 |  | 二级行业 | 1 | 2021保留 | 32 |
| 370402 | 851542 | 医药生物 | 医药商业 | 医药流通 | 三级行业 | 1 | 2021新增 | 25 |
| 370403 | 851543 | 医药生物 | 医药商业 | 线下药店 | 三级行业 | 1 | 2021新增 | 7 |
| 370404 | 851544 | 医药生物 | 医药商业 | 互联网药店 | 三级行业 | 0 | 2021新增 | 0 |
| 370500 | 801153 | 医药生物 | 医疗器械 |  | 二级行业 | 1 | 2021保留 | 62 |
| 370502 | 851532 | 医药生物 | 医疗器械 | 医疗设备 | 三级行业 | 1 | 2021新增 | 18 |
| 370503 | 851533 | 医药生物 | 医疗器械 | 医疗耗材 | 三级行业 | 1 | 2021新增 | 23 |
| 370504 | 851534 | 医药生物 | 医疗器械 | 体外诊断 | 三级行业 | 1 | 2021新增 | 21 |
| 370600 | 801156 | 医药生物 | 医疗服务 |  | 二级行业 | 1 | 2021保留 | 29 |
| 370602 | 851562 | 医药生物 | 医疗服务 | 诊断服务 | 三级行业 | 0 | 2021新增 | 4 |
| 370603 | 851563 | 医药生物 | 医疗服务 | 医疗研发外包 | 三级行业 | 1 | 2021新增 | 12 |
| 370604 | 851564 | 医药生物 | 医疗服务 | 医院 | 三级行业 | 1 | 2021新增 | 12 |
| 370605 | 851565 | 医药生物 | 医疗服务 | 其他医疗服务 | 三级行业 | 0 | 2021新增 | 1 |
| 410000 | 801160 | 公用事业 |  |  | 一级行业 | 1 | 2021保留 | 120 |
| 410100 | 801161 | 公用事业 | 电力 |  | 二级行业 | 1 | 2021保留 | 92 |
| 410101 | 851611 | 公用事业 | 电力 | 火力发电 | 三级行业 | 1 | 2021保留 | 28 |
| 410102 | 851612 | 公用事业 | 电力 | 水力发电 | 三级行业 | 1 | 2021保留 | 11 |
| 410104 | 851614 | 公用事业 | 电力 | 热力服务 | 三级行业 | 1 | 2021保留 | 15 |
| 410106 | 851616 | 公用事业 | 电力 | 光伏发电 | 三级行业 | 1 | 2021新增 | 13 |
| 410107 | 851617 | 公用事业 | 电力 | 风力发电 | 三级行业 | 1 | 2021新增 | 8 |
| 410108 | 851618 | 公用事业 | 电力 | 核力发电 | 三级行业 | 0 | 2021新增 | 2 |
| 410109 | 851619 | 公用事业 | 电力 | 其他能源发电 | 三级行业 | 0 | 2021新增 | 1 |
| 410110 | 851610 | 公用事业 | 电力 | 电能综合服务 | 三级行业 | 1 | 2021新增 | 14 |
| 410300 | 801163 | 公用事业 | 燃气Ⅱ |  | 二级行业 | 1 | 2021保留 | 28 |
| 410301 | 851631 | 公用事业 | 燃气Ⅱ | 燃气Ⅲ | 三级行业 | 1 | 2021保留 | 28 |
| 420000 | 801170 | 交通运输 |  |  | 一级行业 | 1 | 2021保留 | 128 |
| 420800 | 801178 | 交通运输 | 物流 |  | 二级行业 | 1 | 2021保留 | 49 |
| 420802 | 851782 | 交通运输 | 物流 | 原材料供应链服务 | 三级行业 | 1 | 2021新增 | 14 |
| 420803 | 851783 | 交通运输 | 物流 | 中间产品及消费品供应链服务 | 三级行业 | 1 | 2021新增 | 8 |
| 420804 | 851784 | 交通运输 | 物流 | 快递 | 三级行业 | 1 | 2021新增 | 5 |
| 420805 | 851785 | 交通运输 | 物流 | 跨境物流 | 三级行业 | 1 | 2021新增 | 9 |
| 420806 | 851786 | 交通运输 | 物流 | 仓储物流 | 三级行业 | 1 | 2021新增 | 5 |
| 420807 | 851787 | 交通运输 | 物流 | 公路货运 | 三级行业 | 1 | 2021新增 | 8 |
| 420900 | 801179 | 交通运输 | 铁路公路 |  | 二级行业 | 1 | 2021新增 | 38 |
| 420901 | 851731 | 交通运输 | 铁路公路 | 高速公路 | 三级行业 | 1 | 2021替换代码420201 | 22 |
| 420902 | 851721 | 交通运输 | 铁路公路 | 公交 | 三级行业 | 1 | 2021替换代码420301 | 9 |
| 420903 | 851771 | 交通运输 | 铁路公路 | 铁路运输 | 三级行业 | 1 | 2021替换代码420701 | 7 |
| 421000 | 801991 | 交通运输 | 航空机场 |  | 二级行业 | 1 | 2021新增 | 12 |
| 421001 | 851741 | 交通运输 | 航空机场 | 航空运输 | 三级行业 | 1 | 2021替换代码420401 | 8 |
| 421002 | 851751 | 交通运输 | 航空机场 | 机场 | 三级行业 | 0 | 2021替换代码420501 | 4 |
| 421100 | 801992 | 交通运输 | 航运港口 |  | 二级行业 | 1 | 2021新增 | 29 |
| 421101 | 851761 | 交通运输 | 航运港口 | 航运 | 三级行业 | 1 | 2021替换代码420601 | 12 |
| 421102 | 851711 | 交通运输 | 航运港口 | 港口 | 三级行业 | 1 | 2021替换代码420101 | 17 |
| 430000 | 801180 | 房地产 |  |  | 一级行业 | 1 | 2021保留 | 131 |
| 430100 | 801181 | 房地产 | 房地产开发 |  | 二级行业 | 1 | 2021保留 | 122 |
| 430101 | 851811 | 房地产 | 房地产开发 | 住宅开发 | 三级行业 | 1 | 2021改名 | 101 |
| 430102 | 851812 | 房地产 | 房地产开发 | 商业地产 | 三级行业 | 1 | 2021新增 | 10 |
| 430103 | 851813 | 房地产 | 房地产开发 | 产业地产 | 三级行业 | 1 | 2021新增 | 11 |
| 430300 | 801183 | 房地产 | 房地产服务 |  | 二级行业 | 1 | 2021新增 | 9 |
| 430301 | 851831 | 房地产 | 房地产服务 | 物业管理 | 三级行业 | 1 | 2021新增 | 6 |
| 430302 | 851832 | 房地产 | 房地产服务 | 房产租赁经纪 | 三级行业 | 0 | 2021新增 | 3 |
| 430303 | 851833 | 房地产 | 房地产服务 | 房地产综合服务 | 三级行业 | 0 | 2021新增 | 0 |
| 450000 | 801200 | 商贸零售 |  |  | 一级行业 | 1 | 2021保留 | 104 |
| 450200 | 801202 | 商贸零售 | 贸易Ⅱ |  | 二级行业 | 1 | 2021保留 | 15 |
| 450201 | 852021 | 商贸零售 | 贸易Ⅱ | 贸易Ⅲ | 三级行业 | 1 | 2021保留 | 15 |
| 450300 | 801203 | 商贸零售 | 一般零售 |  | 二级行业 | 1 | 2021保留 | 68 |
| 450301 | 852031 | 商贸零售 | 一般零售 | 百货 | 三级行业 | 1 | 2021保留 | 25 |
| 450302 | 852032 | 商贸零售 | 一般零售 | 超市 | 三级行业 | 1 | 2021保留 | 11 |
| 450303 | 852033 | 商贸零售 | 一般零售 | 多业态零售 | 三级行业 | 1 | 2021保留 | 16 |
| 450304 | 852034 | 商贸零售 | 一般零售 | 商业物业经营 | 三级行业 | 1 | 2021新增 | 16 |
| 450400 | 801204 | 商贸零售 | 专业连锁Ⅱ |  | 二级行业 | 1 | 2021改名 | 7 |
| 450401 | 852041 | 商贸零售 | 专业连锁Ⅱ | 专业连锁Ⅲ | 三级行业 | 1 | 2021保留 | 7 |
| 450600 | 801206 | 商贸零售 | 互联网电商 |  | 二级行业 | 1 | 2021新增 | 13 |
| 450601 | 852061 | 商贸零售 | 互联网电商 | 综合电商 | 三级行业 | 0 | 2021新增 | 2 |
| 450602 | 852062 | 商贸零售 | 互联网电商 | 跨境电商 | 三级行业 | 1 | 2021新增 | 6 |
| 450603 | 852063 | 商贸零售 | 互联网电商 | 电商服务 | 三级行业 | 1 | 2021新增 | 5 |
| 450700 | 801207 | 商贸零售 | 旅游零售Ⅱ |  | 二级行业 | 0 | 2021新增 | 1 |
| 450701 | 852071 | 商贸零售 | 旅游零售Ⅱ | 旅游零售Ⅲ | 三级行业 | 0 | 2021新增 | 1 |
| 460000 | 801210 | 社会服务 |  |  | 一级行业 | 1 | 2021改名 | 72 |
| 460600 | 801216 | 社会服务 | 体育Ⅱ |  | 二级行业 | 0 | 2021新增 | 4 |
| 460601 | 852161 | 社会服务 | 体育Ⅱ | 体育Ⅲ | 三级行业 | 0 | 2021新增 | 4 |
| 460700 | 801217 | 社会服务 | 本地生活服务Ⅱ |  | 二级行业 | 0 | 2021新增 | 0 |
| 460701 | 852171 | 社会服务 | 本地生活服务Ⅱ | 本地生活服务Ⅲ | 三级行业 | 0 | 2021新增 | 0 |
| 460800 | 801218 | 社会服务 | 专业服务 |  | 二级行业 | 1 | 2021新增 | 16 |
| 460801 | 852181 | 社会服务 | 专业服务 | 人力资源服务 | 三级行业 | 0 | 2021新增 | 1 |
| 460802 | 852182 | 社会服务 | 专业服务 | 检测服务 | 三级行业 | 1 | 2021新增 | 9 |
| 460803 | 852183 | 社会服务 | 专业服务 | 会展服务 | 三级行业 | 1 | 2021新增 | 5 |
| 460804 | 852184 | 社会服务 | 专业服务 | 其他专业服务 | 三级行业 | 0 | 2021新增 | 1 |
| 460900 | 801219 | 社会服务 | 酒店餐饮 |  | 二级行业 | 1 | 2021新增 | 10 |
| 460901 | 852121 | 社会服务 | 酒店餐饮 | 酒店 | 三级行业 | 1 | 2021替换代码460201 | 6 |
| 460902 | 852141 | 社会服务 | 酒店餐饮 | 餐饮 | 三级行业 | 0 | 2021替换代码460401 | 4 |
| 461000 | 801993 | 社会服务 | 旅游及景区 |  | 二级行业 | 1 | 2021新增 | 21 |
| 461001 | 859931 | 社会服务 | 旅游及景区 | 博彩 | 三级行业 | 0 | 2021新增 | 0 |
| 461002 | 852111 | 社会服务 | 旅游及景区 | 人工景区 | 三级行业 | 1 | 2021替换代码460101 | 6 |
| 461003 | 852112 | 社会服务 | 旅游及景区 | 自然景区 | 三级行业 | 1 | 2021替换代码460102 | 10 |
| 461004 | 852131 | 社会服务 | 旅游及景区 | 旅游综合 | 三级行业 | 1 | 2021替换代码460301 | 5 |
| 461100 | 801994 | 社会服务 | 教育 |  | 二级行业 | 1 | 2021新增 | 21 |
| 461101 | 859851 | 社会服务 | 教育 | 学历教育 | 三级行业 | 0 | 2021新增 | 2 |
| 461102 | 859852 | 社会服务 | 教育 | 培训教育 | 三级行业 | 1 | 2021新增 | 15 |
| 461103 | 859853 | 社会服务 | 教育 | 教育运营及其他 | 三级行业 | 0 | 2021新增 | 4 |
| 480000 | 801780 | 银行 |  |  | 一级行业 | 1 | 2021保留 | 41 |
| 480200 | 801782 | 银行 | 国有大型银行Ⅱ |  | 二级行业 | 1 | 2021新增 | 6 |
| 480201 | 857821 | 银行 | 国有大型银行Ⅱ | 国有大型银行Ⅲ | 三级行业 | 1 | 2021新增 | 6 |
| 480300 | 801783 | 银行 | 股份制银行Ⅱ |  | 二级行业 | 1 | 2021新增 | 9 |
| 480301 | 857831 | 银行 | 股份制银行Ⅱ | 股份制银行Ⅲ | 三级行业 | 1 | 2021新增 | 9 |
| 480400 | 801784 | 银行 | 城商行Ⅱ |  | 二级行业 | 1 | 2021新增 | 16 |
| 480401 | 857841 | 银行 | 城商行Ⅱ | 城商行Ⅲ | 三级行业 | 1 | 2021新增 | 16 |
| 480500 | 801785 | 银行 | 农商行Ⅱ |  | 二级行业 | 1 | 2021新增 | 10 |
| 480501 | 857851 | 银行 | 农商行Ⅱ | 农商行Ⅲ | 三级行业 | 1 | 2021新增 | 10 |
| 480600 | 801786 | 银行 | 其他银行Ⅱ |  | 二级行业 | 0 | 2021新增 | 0 |
| 480601 | 857861 | 银行 | 其他银行Ⅱ | 其他银行Ⅲ | 三级行业 | 0 | 2021新增 | 0 |
| 490000 | 801790 | 非银金融 |  |  | 一级行业 | 1 | 2021保留 | 87 |
| 490100 | 801193 | 非银金融 | 证券Ⅱ |  | 二级行业 | 1 | 2021保留 | 49 |
| 490101 | 851931 | 非银金融 | 证券Ⅱ | 证券Ⅲ | 三级行业 | 1 | 2021保留 | 49 |
| 490200 | 801194 | 非银金融 | 保险Ⅱ |  | 二级行业 | 1 | 2021保留 | 7 |
| 490201 | 851941 | 非银金融 | 保险Ⅱ | 保险Ⅲ | 三级行业 | 1 | 2021保留 | 7 |
| 490300 | 801191 | 非银金融 | 多元金融 |  | 二级行业 | 1 | 2021保留 | 31 |
| 490302 | 851922 | 非银金融 | 多元金融 | 金融控股 | 三级行业 | 1 | 2021新增 | 13 |
| 490303 | 851923 | 非银金融 | 多元金融 | 期货 | 三级行业 | 0 | 2021新增 | 2 |
| 490304 | 851924 | 非银金融 | 多元金融 | 信托 | 三级行业 | 0 | 2021新增 | 3 |
| 490305 | 851925 | 非银金融 | 多元金融 | 租赁 | 三级行业 | 0 | 2021新增 | 4 |
| 490306 | 851926 | 非银金融 | 多元金融 | 金融信息服务 | 三级行业 | 0 | 2021新增 | 3 |
| 490307 | 851927 | 非银金融 | 多元金融 | 资产管理 | 三级行业 | 1 | 2021新增 | 5 |
| 490308 | 851928 | 非银金融 | 多元金融 | 其他多元金融 | 三级行业 | 0 | 2021新增 | 1 |
| 510000 | 801230 | 综合 |  |  | 一级行业 | 1 | 2021保留 | 40 |
| 510100 | 801231 | 综合 | 综合Ⅱ |  | 二级行业 | 1 | 2021保留 | 40 |
| 510101 | 852311 | 综合 | 综合Ⅱ | 综合Ⅲ | 三级行业 | 1 | 2021保留 | 40 |
| 610000 | 801710 | 建筑材料 |  |  | 一级行业 | 1 | 2021保留 | 76 |
| 610100 | 801711 | 建筑材料 | 水泥 |  | 二级行业 | 1 | 2021改名 | 25 |
| 610101 | 857111 | 建筑材料 | 水泥 | 水泥制造 | 三级行业 | 1 | 2021新增 | 18 |
| 610102 | 857112 | 建筑材料 | 水泥 | 水泥制品 | 三级行业 | 1 | 2021新增 | 7 |
| 610200 | 801712 | 建筑材料 | 玻璃玻纤 |  | 二级行业 | 1 | 2021改名 | 16 |
| 610201 | 857121 | 建筑材料 | 玻璃玻纤 | 玻璃制造 | 三级行业 | 1 | 2021新增 | 9 |
| 610202 | 857122 | 建筑材料 | 玻璃玻纤 | 玻纤制造 | 三级行业 | 1 | 2021新增 | 7 |
| 610300 | 801713 | 建筑材料 | 装修建材 |  | 二级行业 | 1 | 2021改名 | 35 |
| 610301 | 850615 | 建筑材料 | 装修建材 | 耐火材料 | 三级行业 | 1 | 2021保留 | 5 |
| 610302 | 850616 | 建筑材料 | 装修建材 | 管材 | 三级行业 | 1 | 2021保留 | 8 |
| 610303 | 850614 | 建筑材料 | 装修建材 | 其他建材 | 三级行业 | 1 | 2021保留 | 17 |
| 610304 | 850617 | 建筑材料 | 装修建材 | 防水材料 | 三级行业 | 0 | 2021新增 | 3 |
| 610305 | 850618 | 建筑材料 | 装修建材 | 涂料 | 三级行业 | 0 | 2021新增 | 2 |
| 620000 | 801720 | 建筑装饰 |  |  | 一级行业 | 1 | 2021保留 | 147 |
| 620100 | 801721 | 建筑装饰 | 房屋建设Ⅱ |  | 二级行业 | 1 | 2021保留 | 9 |
| 620101 | 850623 | 建筑装饰 | 房屋建设Ⅱ | 房屋建设Ⅲ | 三级行业 | 1 | 2021保留 | 9 |
| 620200 | 801722 | 建筑装饰 | 装修装饰Ⅱ |  | 二级行业 | 1 | 2021保留 | 28 |
| 620201 | 857221 | 建筑装饰 | 装修装饰Ⅱ | 装修装饰Ⅲ | 三级行业 | 1 | 2021保留 | 28 |
| 620300 | 801723 | 建筑装饰 | 基础建设 |  | 二级行业 | 1 | 2021保留 | 46 |
| 620306 | 857236 | 建筑装饰 | 基础建设 | 基建市政工程 | 三级行业 | 1 | 2021新增 | 23 |
| 620307 | 857251 | 建筑装饰 | 基础建设 | 园林工程 | 三级行业 | 1 | 2021替换代码620501 | 23 |
| 620400 | 801724 | 建筑装饰 | 专业工程 |  | 二级行业 | 1 | 2021保留 | 34 |
| 620401 | 857241 | 建筑装饰 | 专业工程 | 钢结构 | 三级行业 | 1 | 2021保留 | 9 |
| 620402 | 857242 | 建筑装饰 | 专业工程 | 化学工程 | 三级行业 | 1 | 2021保留 | 7 |
| 620403 | 857243 | 建筑装饰 | 专业工程 | 国际工程 | 三级行业 | 1 | 2021改名 | 5 |
| 620404 | 857244 | 建筑装饰 | 专业工程 | 其他专业工程 | 三级行业 | 1 | 2021保留 | 13 |
| 620600 | 801726 | 建筑装饰 | 工程咨询服务Ⅱ |  | 二级行业 | 1 | 2021新增 | 30 |
| 620601 | 857261 | 建筑装饰 | 工程咨询服务Ⅱ | 工程咨询服务Ⅲ | 三级行业 | 1 | 2021新增 | 30 |
| 630000 | 801730 | 电力设备 |  |  | 一级行业 | 1 | 2021改名 | 239 |
| 630100 | 801731 | 电力设备 | 电机Ⅱ |  | 二级行业 | 1 | 2021保留 | 19 |
| 630101 | 850741 | 电力设备 | 电机Ⅱ | 电机Ⅲ | 三级行业 | 1 | 2021保留 | 19 |
| 630300 | 801733 | 电力设备 | 其他电源设备Ⅱ |  | 二级行业 | 1 | 2021改名 | 25 |
| 630301 | 857331 | 电力设备 | 其他电源设备Ⅱ | 综合电力设备商 | 三级行业 | 0 | 2021保留 | 3 |
| 630304 | 857334 | 电力设备 | 其他电源设备Ⅱ | 火电设备 | 三级行业 | 1 | 2021保留 | 6 |
| 630306 | 857336 | 电力设备 | 其他电源设备Ⅱ | 其他电源设备Ⅲ | 三级行业 | 1 | 2021保留 | 16 |
| 630500 | 801735 | 电力设备 | 光伏设备 |  | 二级行业 | 1 | 2021新增 | 32 |
| 630501 | 857351 | 电力设备 | 光伏设备 | 硅料硅片 | 三级行业 | 0 | 2021新增 | 3 |
| 630502 | 857352 | 电力设备 | 光伏设备 | 光伏电池组件 | 三级行业 | 1 | 2021新增 | 9 |
| 630503 | 857353 | 电力设备 | 光伏设备 | 逆变器 | 三级行业 | 0 | 2021新增 | 3 |
| 630504 | 857354 | 电力设备 | 光伏设备 | 光伏辅材 | 三级行业 | 1 | 2021新增 | 10 |
| 630505 | 857355 | 电力设备 | 光伏设备 | 光伏加工设备 | 三级行业 | 1 | 2021新增 | 7 |
| 630600 | 801736 | 电力设备 | 风电设备 |  | 二级行业 | 1 | 2021新增 | 18 |
| 630601 | 857361 | 电力设备 | 风电设备 | 风电整机 | 三级行业 | 0 | 2021新增 | 4 |
| 630602 | 857362 | 电力设备 | 风电设备 | 风电零部件 | 三级行业 | 1 | 2021新增 | 14 |
| 630700 | 801737 | 电力设备 | 电池 |  | 二级行业 | 1 | 2021新增 | 41 |
| 630701 | 857371 | 电力设备 | 电池 | 锂电池 | 三级行业 | 1 | 2021新增 | 12 |
| 630702 | 857372 | 电力设备 | 电池 | 电池化学品 | 三级行业 | 1 | 2021新增 | 17 |
| 630703 | 857373 | 电力设备 | 电池 | 锂电专用设备 | 三级行业 | 1 | 2021新增 | 5 |
| 630704 | 857374 | 电力设备 | 电池 | 燃料电池 | 三级行业 | 0 | 2021新增 | 0 |
| 630705 | 857375 | 电力设备 | 电池 | 蓄电池及其他电池 | 三级行业 | 1 | 2021新增 | 7 |
| 630800 | 801738 | 电力设备 | 电网设备 |  | 二级行业 | 1 | 2021新增 | 104 |
| 630801 | 857381 | 电力设备 | 电网设备 | 输变电设备 | 三级行业 | 1 | 2021新增 | 27 |
| 630802 | 857382 | 电力设备 | 电网设备 | 配电设备 | 三级行业 | 1 | 2021新增 | 16 |
| 630803 | 857321 | 电力设备 | 电网设备 | 电网自动化设备 | 三级行业 | 1 | 2021替换代码630201 | 18 |
| 630804 | 857323 | 电力设备 | 电网设备 | 电工仪器仪表 | 三级行业 | 1 | 2021替换代码-改名630203 | 14 |
| 630805 | 857344 | 电力设备 | 电网设备 | 线缆部件及其他 | 三级行业 | 1 | 2021替换代码630204 | 29 |
| 640000 | 801890 | 机械设备 |  |  | 一级行业 | 1 | 2021保留 | 379 |
| 640100 | 801072 | 机械设备 | 通用设备 |  | 二级行业 | 1 | 2021改名 | 161 |
| 640101 | 850711 | 机械设备 | 通用设备 | 机床工具 | 三级行业 | 1 | 2021保留 | 13 |
| 640103 | 850713 | 机械设备 | 通用设备 | 磨具磨料 | 三级行业 | 1 | 2021保留 | 13 |
| 640105 | 850715 | 机械设备 | 通用设备 | 制冷空调设备 | 三级行业 | 1 | 2021保留 | 12 |
| 640106 | 850716 | 机械设备 | 通用设备 | 其他通用设备 | 三级行业 | 1 | 2021改名 | 31 |
| 640107 | 850731 | 机械设备 | 通用设备 | 仪器仪表 | 三级行业 | 1 | 2021替换代码640301 | 32 |
| 640108 | 850751 | 机械设备 | 通用设备 | 金属制品 | 三级行业 | 1 | 2021替换代码640401 | 60 |
| 640200 | 801074 | 机械设备 | 专用设备 |  | 二级行业 | 1 | 2021保留 | 133 |
| 640203 | 850725 | 机械设备 | 专用设备 | 能源及重型设备 | 三级行业 | 1 | 2021改名 | 38 |
| 640204 | 850728 | 机械设备 | 专用设备 | 楼宇设备 | 三级行业 | 1 | 2021保留 | 15 |
| 640206 | 850721 | 机械设备 | 专用设备 | 纺织服装设备 | 三级行业 | 1 | 2021保留 | 10 |
| 640207 | 850723 | 机械设备 | 专用设备 | 农用机械 | 三级行业 | 0 | 2021保留 | 3 |
| 640208 | 850726 | 机械设备 | 专用设备 | 印刷包装机械 | 三级行业 | 1 | 2021保留 | 9 |
| 640209 | 850727 | 机械设备 | 专用设备 | 其他专用设备 | 三级行业 | 1 | 2021改名 | 58 |
| 640500 | 801076 | 机械设备 | 轨交设备Ⅱ |  | 二级行业 | 1 | 2021改名 | 21 |
| 640501 | 850936 | 机械设备 | 轨交设备Ⅱ | 轨交设备Ⅲ | 三级行业 | 1 | 2021改名 | 21 |
| 640600 | 801077 | 机械设备 | 工程机械 |  | 二级行业 | 1 | 2021新增 | 21 |
| 640601 | 850771 | 机械设备 | 工程机械 | 工程机械整机 | 三级行业 | 1 | 2021新增 | 16 |
| 640602 | 850772 | 机械设备 | 工程机械 | 工程机械器件 | 三级行业 | 1 | 2021新增 | 5 |
| 640700 | 801078 | 机械设备 | 自动化设备 |  | 二级行业 | 1 | 2021新增 | 43 |
| 640701 | 850781 | 机械设备 | 自动化设备 | 机器人 | 三级行业 | 1 | 2021新增 | 11 |
| 640702 | 850782 | 机械设备 | 自动化设备 | 工控设备 | 三级行业 | 1 | 2021新增 | 17 |
| 640703 | 850783 | 机械设备 | 自动化设备 | 激光设备 | 三级行业 | 1 | 2021新增 | 6 |
| 640704 | 850784 | 机械设备 | 自动化设备 | 其他自动化设备 | 三级行业 | 1 | 2021新增 | 9 |
| 650000 | 801740 | 国防军工 |  |  | 一级行业 | 1 | 2021保留 | 97 |
| 650100 | 801741 | 国防军工 | 航天装备Ⅱ |  | 二级行业 | 1 | 2021保留 | 8 |
| 650101 | 857411 | 国防军工 | 航天装备Ⅱ | 航天装备Ⅲ | 三级行业 | 1 | 2021保留 | 8 |
| 650200 | 801742 | 国防军工 | 航空装备Ⅱ |  | 二级行业 | 1 | 2021保留 | 35 |
| 650201 | 857421 | 国防军工 | 航空装备Ⅱ | 航空装备Ⅲ | 三级行业 | 1 | 2021保留 | 35 |
| 650300 | 801743 | 国防军工 | 地面兵装Ⅱ |  | 二级行业 | 1 | 2021保留 | 9 |
| 650301 | 857431 | 国防军工 | 地面兵装Ⅱ | 地面兵装Ⅲ | 三级行业 | 1 | 2021保留 | 9 |
| 650400 | 801744 | 国防军工 | 航海装备Ⅱ |  | 二级行业 | 1 | 2021改名 | 12 |
| 650401 | 850935 | 国防军工 | 航海装备Ⅱ | 航海装备Ⅲ | 三级行业 | 1 | 2021改名 | 12 |
| 650500 | 801745 | 国防军工 | 军工电子Ⅱ |  | 二级行业 | 1 | 2021新增 | 33 |
| 650501 | 857451 | 国防军工 | 军工电子Ⅱ | 军工电子Ⅲ | 三级行业 | 1 | 2021新增 | 33 |
| 710000 | 801750 | 计算机 |  |  | 一级行业 | 1 | 2021保留 | 239 |
| 710100 | 801101 | 计算机 | 计算机设备 |  | 二级行业 | 1 | 2021保留 | 64 |
| 710102 | 850702 | 计算机 | 计算机设备 | 安防设备 | 三级行业 | 1 | 2021新增 | 16 |
| 710103 | 850703 | 计算机 | 计算机设备 | 其他计算机设备 | 三级行业 | 1 | 2021新增 | 48 |
| 710300 | 801103 | 计算机 | IT服务Ⅱ |  | 二级行业 | 1 | 2021新增 | 90 |
| 710301 | 852226 | 计算机 | IT服务Ⅱ | IT服务Ⅲ | 三级行业 | 1 | 2021替换代码710202 | 90 |
| 710400 | 801104 | 计算机 | 软件开发 |  | 二级行业 | 1 | 2021新增 | 85 |
| 710401 | 851041 | 计算机 | 软件开发 | 垂直应用软件 | 三级行业 | 1 | 2021新增 | 69 |
| 710402 | 851042 | 计算机 | 软件开发 | 横向通用软件 | 三级行业 | 1 | 2021新增 | 16 |
| 720000 | 801760 | 传媒 |  |  | 一级行业 | 1 | 2021保留 | 149 |
| 720400 | 801764 | 传媒 | 游戏Ⅱ |  | 二级行业 | 1 | 2021新增 | 38 |
| 720401 | 857641 | 传媒 | 游戏Ⅱ | 游戏Ⅲ | 三级行业 | 1 | 2021新增 | 38 |
| 720500 | 801765 | 传媒 | 广告营销 |  | 二级行业 | 1 | 2021新增 | 38 |
| 720501 | 857651 | 传媒 | 广告营销 | 营销代理 | 三级行业 | 1 | 2021新增 | 34 |
| 720502 | 857652 | 传媒 | 广告营销 | 广告媒体 | 三级行业 | 0 | 2021新增 | 4 |
| 720600 | 801766 | 传媒 | 影视院线 |  | 二级行业 | 1 | 2021新增 | 23 |
| 720601 | 857661 | 传媒 | 影视院线 | 影视动漫制作 | 三级行业 | 1 | 2021新增 | 19 |
| 720602 | 857662 | 传媒 | 影视院线 | 院线 | 三级行业 | 0 | 2021新增 | 4 |
| 720700 | 801767 | 传媒 | 数字媒体 |  | 二级行业 | 1 | 2021新增 | 11 |
| 720701 | 857671 | 传媒 | 数字媒体 | 视频媒体 | 三级行业 | 0 | 2021新增 | 2 |
| 720702 | 857672 | 传媒 | 数字媒体 | 音频媒体 | 三级行业 | 0 | 2021新增 | 0 |
| 720703 | 857673 | 传媒 | 数字媒体 | 图片媒体 | 三级行业 | 0 | 2021新增 | 1 |
| 720704 | 857674 | 传媒 | 数字媒体 | 门户网站 | 三级行业 | 1 | 2021新增 | 7 |
| 720705 | 857675 | 传媒 | 数字媒体 | 文字媒体 | 三级行业 | 0 | 2021新增 | 1 |
| 720706 | 857676 | 传媒 | 数字媒体 | 其他数字媒体 | 三级行业 | 0 | 2021新增 | 0 |
| 720800 | 801768 | 传媒 | 社交Ⅱ |  | 二级行业 | 0 | 2021新增 | 0 |
| 720801 | 857681 | 传媒 | 社交Ⅱ | 社交Ⅲ | 三级行业 | 0 | 2021新增 | 0 |
| 720900 | 801769 | 传媒 | 出版 |  | 二级行业 | 1 | 2021新增 | 27 |
| 720901 | 857691 | 传媒 | 出版 | 教育出版 | 三级行业 | 1 | 2021新增 | 10 |
| 720902 | 857692 | 传媒 | 出版 | 大众出版 | 三级行业 | 1 | 2021新增 | 17 |
| 720903 | 857693 | 传媒 | 出版 | 其他出版 | 三级行业 | 0 | 2021新增 | 0 |
| 721000 | 801995 | 传媒 | 电视广播Ⅱ |  | 二级行业 | 1 | 2021新增 | 12 |
| 721001 | 859951 | 传媒 | 电视广播Ⅱ | 电视广播Ⅲ | 三级行业 | 1 | 2021新增 | 12 |
| 730000 | 801770 | 通信 |  |  | 一级行业 | 1 | 2021保留 | 100 |
| 730100 | 801223 | 通信 | 通信服务 |  | 二级行业 | 1 | 2021改名 | 34 |
| 730102 | 852212 | 通信 | 通信服务 | 电信运营商 | 三级行业 | 0 | 2021新增 | 4 |
| 730103 | 852213 | 通信 | 通信服务 | 通信工程及服务 | 三级行业 | 1 | 2021新增 | 19 |
| 730104 | 852214 | 通信 | 通信服务 | 通信应用增值服务 | 三级行业 | 1 | 2021新增 | 11 |
| 730200 | 801102 | 通信 | 通信设备 |  | 二级行业 | 1 | 2021保留 | 66 |
| 730204 | 851024 | 通信 | 通信设备 | 通信网络设备及器件 | 三级行业 | 1 | 2021新增 | 24 |
| 730205 | 851025 | 通信 | 通信设备 | 通信线缆及配套 | 三级行业 | 1 | 2021新增 | 11 |
| 730206 | 851026 | 通信 | 通信设备 | 通信终端及配件 | 三级行业 | 1 | 2021新增 | 23 |
| 730207 | 851027 | 通信 | 通信设备 | 其他通信设备 | 三级行业 | 1 | 2021新增 | 8 |
| 740000 | 801950 | 煤炭 |  |  | 一级行业 | 1 | 2021新增 | 38 |
| 740100 | 801951 | 煤炭 | 煤炭开采 |  | 二级行业 | 1 | 2021新增 | 29 |
| 740101 | 859511 | 煤炭 | 煤炭开采 | 动力煤 | 三级行业 | 1 | 2021新增 | 18 |
| 740102 | 859512 | 煤炭 | 煤炭开采 | 焦煤 | 三级行业 | 1 | 2021新增 | 11 |
| 740200 | 801952 | 煤炭 | 焦炭Ⅱ |  | 二级行业 | 1 | 2021新增 | 9 |
| 740201 | 859521 | 煤炭 | 焦炭Ⅱ | 焦炭Ⅲ | 三级行业 | 1 | 2021新增 | 9 |
| 750000 | 801960 | 石油石化 |  |  | 一级行业 | 1 | 2021新增 | 47 |
| 750100 | 801961 | 石油石化 | 油气开采Ⅱ |  | 二级行业 | 0 | 2021新增 | 4 |
| 750101 | 859611 | 石油石化 | 油气开采Ⅱ | 油气开采Ⅲ | 三级行业 | 0 | 2021新增 | 4 |
| 750200 | 801962 | 石油石化 | 油服工程 |  | 二级行业 | 1 | 2021新增 | 14 |
| 750201 | 859621 | 石油石化 | 油服工程 | 油田服务 | 三级行业 | 1 | 2021新增 | 7 |
| 750202 | 859622 | 石油石化 | 油服工程 | 油气及炼化工程 | 三级行业 | 1 | 2021新增 | 7 |
| 750300 | 801963 | 石油石化 | 炼化及贸易 |  | 二级行业 | 1 | 2021新增 | 29 |
| 750301 | 859631 | 石油石化 | 炼化及贸易 | 炼油化工 | 三级行业 | 1 | 2021新增 | 9 |
| 750302 | 859632 | 石油石化 | 炼化及贸易 | 油品石化贸易 | 三级行业 | 1 | 2021新增 | 6 |
| 750303 | 859633 | 石油石化 | 炼化及贸易 | 其他石化 | 三级行业 | 1 | 2021新增 | 14 |
| 760000 | 801970 | 环保 |  |  | 一级行业 | 1 | 2021新增 | 97 |
| 760100 | 801971 | 环保 | 环境治理 |  | 二级行业 | 1 | 2021新增 | 82 |
| 760101 | 859711 | 环保 | 环境治理 | 大气治理 | 三级行业 | 1 | 2021新增 | 8 |
| 760102 | 859712 | 环保 | 环境治理 | 水务及水治理 | 三级行业 | 1 | 2021新增 | 40 |
| 760103 | 859713 | 环保 | 环境治理 | 固废治理 | 三级行业 | 1 | 2021新增 | 23 |
| 760104 | 859714 | 环保 | 环境治理 | 综合环境治理 | 三级行业 | 1 | 2021新增 | 11 |
| 760200 | 801972 | 环保 | 环保设备Ⅱ |  | 二级行业 | 1 | 2021新增 | 15 |
| 760201 | 859721 | 环保 | 环保设备Ⅱ | 环保设备Ⅲ | 三级行业 | 1 | 2021新增 | 15 |
| 770000 | 801980 | 美容护理 |  |  | 一级行业 | 1 | 2021新增 | 27 |
| 770100 | 801981 | 美容护理 | 个护用品 |  | 二级行业 | 1 | 2021新增 | 12 |
| 770101 | 859811 | 美容护理 | 个护用品 | 生活用纸 | 三级行业 | 1 | 2021新增 | 8 |
| 770102 | 859812 | 美容护理 | 个护用品 | 洗护用品 | 三级行业 | 0 | 2021新增 | 4 |
| 770200 | 801982 | 美容护理 | 化妆品 |  | 二级行业 | 1 | 2021新增 | 13 |
| 770201 | 859821 | 美容护理 | 化妆品 | 化妆品制造及其他 | 三级行业 | 1 | 2021新增 | 7 |
| 770202 | 859822 | 美容护理 | 化妆品 | 品牌化妆品 | 三级行业 | 1 | 2021新增 | 6 |
| 770300 | 801983 | 美容护理 | 医疗美容 |  | 二级行业 | 0 | 2021新增 | 2 |
| 770301 | 859831 | 美容护理 | 医疗美容 | 医美耗材 | 三级行业 | 0 | 2021新增 | 1 |
| 770302 | 859832 | 美容护理 | 医疗美容 | 医美服务 | 三级行业 | 0 | 2021新增 | 1 |

输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| index_code | str | N | 指数代码 |
| level | str | N | 行业分级（L1/L2/L3） |
| parent_code | str | N | 父级代码（一级为0） |
| src | str | N | 指数来源（SW2014：申万2014年版本，SW2021：申万2021年版本） |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| index_code | str | Y | 指数代码 |
| industry_name | str | Y | 行业名称 |
| parent_code | str | Y | 父级代码 |
| level | str | Y | 行业层级 |
| industry_code | str | Y | 行业代码 |
| is_pub | str | Y | 是否发布了指数 |
| src | str | N | 行业分类（SW申万） |

接口示例
数据示例


---

### [335] 申万行业成分（分级）  ·  指数专题
(api: index_member_all | 输出字段: 11 | PIT字段: 否)

# (doc_id=335)  https://tushare.pro/document/2?doc_id=335

## 申万行业成分构成(分级)
接口：index_member_all 描述：按三级分类提取申万行业成分，可提供某个分类的所有成分，也可按股票代码提取所属分类，参数灵活 限量：单次最大2000行，总量不限制 权限：用户需2000积分可调取，积分获取方法请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| l1_code | str | N | 一级行业代码 |
| l2_code | str | N | 二级行业代码 |
| l3_code | str | N | 三级行业代码 |
| ts_code | str | N | 股票代码 |
| is_new | str | N | 是否最新（默认为“Y是”） |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| l1_code | str | Y | 一级行业代码 |
| l1_name | str | Y | 一级行业名称 |
| l2_code | str | Y | 二级行业代码 |
| l2_name | str | Y | 二级行业名称 |
| l3_code | str | Y | 三级行业代码 |
| l3_name | str | Y | 三级行业名称 |
| ts_code | str | Y | 成分股票代码 |
| name | str | Y | 成分股票名称 |
| in_date | str | Y | 纳入日期 |
| out_date | str | Y | 剔除日期 |
| is_new | str | Y | 是否最新Y是N否 |

接口示例
数据示例


---

### [327] 申万日线行情  ·  指数专题
(api: sw_daily | 输出字段: 15 | PIT字段: 否)

# (doc_id=327)  https://tushare.pro/document/2?doc_id=327

## 申万行业日线行情
接口：sw_daily 描述：获取申万行业日线行情（默认是申万2021版行情） 限量：单次最大4000行数据，可通过指数代码和日期参数循环提取，5000积分可调取
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 行业代码 |
| trade_date | str | N | 交易日期 |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 指数代码 |
| trade_date | str | Y | 交易日期 |
| name | str | Y | 指数名称 |
| open | float | Y | 开盘点位 |
| low | float | Y | 最低点位 |
| high | float | Y | 最高点位 |
| close | float | Y | 收盘点位 |
| change | float | Y | 涨跌点位 |
| pct_change | float | Y | 涨跌幅 |
| vol | float | Y | 成交量（万股） |
| amount | float | Y | 成交额（万元） |
| pe | float | Y | 市盈率 |
| pb | float | Y | 市净率 |
| float_mv | float | Y | 流通市值（万元） |
| total_mv | float | Y | 总市值（万元） |

接口示例
数据示例


---

### [417] 申万实时行情  ·  指数专题
(api: rt_sw_k | 输出字段: 11 | PIT字段: 否)

# (doc_id=417)  https://tushare.pro/document/2?doc_id=417

## 申万实时行情
## 接口介绍
接口：rt_sw_k 描述：获取申万行业指数的最新截面数据 积分：本接口是单独开权限的数据，单独申请权限请参考 权限列表
## 输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 指数代码，如: 801005.SI；可以是逗号隔开的多个，如: 801005.SI,801001.SI |

## 输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 指数代码 |
| name | str | Y | 指数名称 |
| trade_time | str | Y | 交易时间 |
| close | float | Y | 现价 |
| pre_close | float | Y | 昨收 |
| high | float | Y | 最高价 |
| open | float | Y | 开盘价 |
| low | float | Y | 最低价 |
| vol | float | Y | 成交量（股） |
| amount | float | Y | 成交金额（元） |
| pct_change | float | Y | 增长率 |

## 代码示例
## 数据结果
| ts_code | name | trade_time | close | pre_close | high | open | low | vol | amount | pct_change |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 801001.SI | 申万50 | 2026-01-29 11:20:15 | 3787.9120 | 3798.2100 | 3813.4650 | 3813.4650 | 3774.6250 | 3705199982 | 222824326266 | -0.27 |
| 801002.SI | 申万中小 | 2026-01-29 11:20:15 | 8806.2050 | 8809.4800 | 8838.5460 | 8775.2190 | 8730.5520 | 25634196750 | 360691370056 | -0.04 |
| 801003.SI | 申万Ａ指 | 2026-01-29 11:20:15 | 4974.9430 | 4970.4900 | 4986.6610 | 4968.8140 | 4950.5050 | 115336604744 | 1936675504044 | 0.09 |
| 801005.SI | 申万创业 | 2026-01-29 11:20:15 | 4094.8600 | 4081.5400 | 4123.7230 | 4070.4380 | 4041.4720 | 19045101938 | 494472518112 | 0.33 |
| 801010.SI | 农林牧渔 | 2026-01-29 11:20:15 | 2931.1360 | 2915.1700 | 2950.3920 | 2910.8210 | 2904.0440 | 2594579310 | 22663408519 | 0.55 |
| 801012.SI | 农产品加工 | 2026-01-29 11:20:15 | 2544.5850 | 2526.3300 | 2560.6810 | 2522.3710 | 2517.1980 | 227870337 | 2384134145 | 0.72 |
| 801014.SI | 饲料 | 2026-01-29 11:20:15 | 4421.3600 | 4371.4000 | 4446.7450 | 4377.4080 | 4372.6460 | 437877589 | 2850725238 | 1.14 |
| 801015.SI | 渔业 | 2026-01-29 11:20:15 | 881.9780 | 873.6900 | 884.1620 | 871.7710 | 864.7650 | 100200890 | 447089570 | 0.95 |
| 801016.SI | 种植业 | 2026-01-29 11:20:15 | 2953.6730 | 2887.6000 | 2995.5200 | 2892.5670 | 2892.5670 | 1044165536 | 8740207605 | 2.29 |
| 801017.SI | 养殖业 | 2026-01-29 11:20:15 | 2988.3250 | 2978.0600 | 3012.0680 | 2971.0800 | 2963.3590 | 397154376 | 4079931700 | 0.34 |


---

### [469] SW历史分钟  ·  指数专题
(api: sw_mins | 输出字段: 8 | PIT字段: 否)

# (doc_id=469)  https://tushare.pro/document/2?doc_id=469

## SW指数历史分钟
## 接口介绍
接口：sw_mins 描述：获取申万指数历史分钟数据 限量：单次最大5000条，可根据代码或日期循环提取 积分：本接口是单独的权限，具体请参阅 积分获取办法
## 输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 指数代码 |
| freq | str | Y | 分钟频度（1min/5min/15min/30min/60min） |
| start_date | datetime | N | 开始日期 格式：2023-08-25 09:00:00 |
| end_date | datetime | N | 结束时间 格式：2023-08-25 19:00:00 |

## 输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 指数代码 |
| trade_time | str | Y | 交易时间 |
| open | float | Y | 开盘点数 |
| close | float | Y | 收盘点数 |
| high | float | Y | 最高点数 |
| low | float | Y | 最低点数 |
| amount | float | Y | 成交金额（元） |
| vol | float | Y | 成交量（股） |

## 代码示例
## 数据结果


---

### [373] 中信行业成分  ·  指数专题
(api: ci_index_member | 输出字段: 11 | PIT字段: 否)

# (doc_id=373)  https://tushare.pro/document/2?doc_id=373

## 中信行业成分
接口：ci_index_member 描述：按三级分类提取中信行业成分，可提供某个分类的所有成分，也可按股票代码提取所属分类，参数灵活 限量：单次最大5000行，总量不限制 权限：用户需5000积分可调取，积分获取方法请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| l1_code | str | N | 一级行业代码 |
| l2_code | str | N | 二级行业代码 |
| l3_code | str | N | 三级行业代码 |
| ts_code | str | N | 股票代码 |
| is_new | str | N | 是否最新（默认为“Y是”） |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| l1_code | str | Y | 一级行业代码 |
| l1_name | str | Y | 一级行业名称 |
| l2_code | str | Y | 二级行业代码 |
| l2_name | str | Y | 二级行业名称 |
| l3_code | str | Y | 三级行业代码 |
| l3_name | str | Y | 三级行业名称 |
| ts_code | str | Y | 成分股票代码 |
| name | str | Y | 成分股票名称 |
| in_date | str | Y | 纳入日期 |
| out_date | str | Y | 剔除日期 |
| is_new | str | Y | 是否最新Y是N否 |

接口示例
数据示例


---

### [308] 中信行业指数日行情  ·  指数专题
(api: ci_daily | 输出字段: 11 | PIT字段: 否)

# (doc_id=308)  https://tushare.pro/document/2?doc_id=308

## 中信行业指数行情
接口：ci_daily 描述：获取中信行业指数日线行情 限量：单次最大4000条，可循环提取 积分：5000积分可调取，可通过指数代码和日期参数循环获取所有数据
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 行业代码 |
| trade_date | str | N | 交易日期（YYYYMMDD格式，下同） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 指数代码 |
| trade_date | str | Y | 交易日期 |
| open | float | Y | 开盘点位 |
| low | float | Y | 最低点位 |
| high | float | Y | 最高点位 |
| close | float | Y | 收盘点位 |
| pre_close | float | Y | 昨日收盘点位 |
| change | float | Y | 涨跌点位 |
| pct_change | float | Y | 涨跌幅 |
| vol | float | Y | 成交量（万股） |
| amount | float | Y | 成交额（万元） |

接口示例
数据示例


---

### [211] 国际主要指数  ·  指数专题
(api: index_global | 输出字段: 12 | PIT字段: 否)

# (doc_id=211)  https://tushare.pro/document/2?doc_id=211

## 国际指数
接口：index_global，可以通过 数据工具 调试和查看数据。 描述：获取国际主要指数日线行情 限量：单次最大提取4000行情数据，可循环获取，总量不限制 积分：用户积6000积分可调取，积分越高频次越高，请自行提高积分，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | TS指数代码，见下表 |
| trade_date | str | N | 交易日期，YYYYMMDD格式，下同 |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

| TS指数代码 | 指数名称 |
| --- | --- |
| XIN9 | 富时中国A50指数 (富时A50) |
| HSI | 恒生指数 |
| HKTECH | 恒生科技指数 |
| HKAH | 恒生AH股H指数 |
| DJI | 道琼斯工业指数 |
| SPX | 标普500指数 |
| IXIC | 纳斯达克指数 |
| FTSE | 富时100指数 |
| FCHI | 法国CAC40指数 |
| GDAXI | 德国DAX指数 |
| N225 | 日经225指数 |
| KS11 | 韩国综合指数 |
| AS51 | 澳大利亚标普200指数 |
| SENSEX | 印度孟买SENSEX指数 |
| IBOVESPA | 巴西IBOVESPA指数 |
| RTS | 俄罗斯RTS指数 |
| TWII | 台湾加权指数 |
| CKLSE | 马来西亚指数 |
| SPTSX | 加拿大S&P/TSX指数 |
| CSX5P | STOXX欧洲50指数 |
| RUT | 罗素2000指数 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS指数代码 |
| trade_date | str | Y | 交易日 |
| open | float | Y | 开盘点位 |
| close | float | Y | 收盘点位 |
| high | float | Y | 最高点位 |
| low | float | Y | 最低点位 |
| pre_close | float | Y | 昨日收盘点 |
| change | float | Y | 涨跌点位 |
| pct_chg | float | Y | 涨跌幅 |
| swing | float | Y | 振幅 |
| vol | float | Y | 成交量 （大部分无此项数据） |
| amount | float | N | 成交额 （大部分无此项数据） |

接口使用
数据示例


---

### [358] 指数技术面因子(专业版)  ·  指数专题
(api: idx_factor_pro | 输出字段: 89 | PIT字段: 否)

# (doc_id=358)  https://tushare.pro/document/2?doc_id=358

## 指数技术因子(专业版)
接口：idx_factor_pro 描述：获取指数每日技术面因子数据，用于跟踪指数当前走势情况，数据由Tushare社区自产，覆盖全历史；输出参数_bfq表示不复权描述中说明了因子的默认传参，如需要特殊参数或者更多因子可以联系管理员评估，指数包括大盘指数 申万行业指数 中信指数 限量：单次最大8000 积分：5000积分每分钟可以请求30次，8000积分以上每分钟500次
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 指数代码(大盘指数 申万指数 中信指数) |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |
| trade_date | str | N | 交易日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 指数代码 |
| trade_date | str | Y | 交易日期 |
| open | float | Y | 开盘价 |
| high | float | Y | 最高价 |
| low | float | Y | 最低价 |
| close | float | Y | 收盘价 |
| pre_close | float | Y | 昨收价 |
| change | float | Y | 涨跌额 |
| pct_change | float | Y | 涨跌幅 （未复权，如果是复权请用 通用行情接口 ） |
| vol | float | Y | 成交量 （手） |
| amount | float | Y | 成交额 （千元） |
| asi_bfq | float | Y | 振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10 |
| asit_bfq | float | Y | 振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10 |
| atr_bfq | float | Y | 真实波动N日平均值-CLOSE, HIGH, LOW, N=20 |
| bbi_bfq | float | Y | BBI多空指标-CLOSE, M1=3, M2=6, M3=12, M4=20 |
| bias1_bfq | float | Y | BIAS乖离率-CLOSE, L1=6, L2=12, L3=24 |
| bias2_bfq | float | Y | BIAS乖离率-CLOSE, L1=6, L2=12, L3=24 |
| bias3_bfq | float | Y | BIAS乖离率-CLOSE, L1=6, L2=12, L3=24 |
| boll_lower_bfq | float | Y | BOLL指标，布林带-CLOSE, N=20, P=2 |
| boll_mid_bfq | float | Y | BOLL指标，布林带-CLOSE, N=20, P=2 |
| boll_upper_bfq | float | Y | BOLL指标，布林带-CLOSE, N=20, P=2 |
| brar_ar_bfq | float | Y | BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26 |
| brar_br_bfq | float | Y | BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26 |
| cci_bfq | float | Y | 顺势指标又叫CCI指标-CLOSE, HIGH, LOW, N=14 |
| cr_bfq | float | Y | CR价格动量指标-CLOSE, HIGH, LOW, N=20 |
| dfma_dif_bfq | float | Y | 平行线差指标-CLOSE, N1=10, N2=50, M=10 |
| dfma_difma_bfq | float | Y | 平行线差指标-CLOSE, N1=10, N2=50, M=10 |
| dmi_adx_bfq | float | Y | 动向指标-CLOSE, HIGH, LOW, M1=14, M2=6 |
| dmi_adxr_bfq | float | Y | 动向指标-CLOSE, HIGH, LOW, M1=14, M2=6 |
| dmi_mdi_bfq | float | Y | 动向指标-CLOSE, HIGH, LOW, M1=14, M2=6 |
| dmi_pdi_bfq | float | Y | 动向指标-CLOSE, HIGH, LOW, M1=14, M2=6 |
| downdays | float | Y | 连跌天数 |
| updays | float | Y | 连涨天数 |
| dpo_bfq | float | Y | 区间震荡线-CLOSE, M1=20, M2=10, M3=6 |
| madpo_bfq | float | Y | 区间震荡线-CLOSE, M1=20, M2=10, M3=6 |
| ema_bfq_10 | float | Y | 指数移动平均-N=10 |
| ema_bfq_20 | float | Y | 指数移动平均-N=20 |
| ema_bfq_250 | float | Y | 指数移动平均-N=250 |
| ema_bfq_30 | float | Y | 指数移动平均-N=30 |
| ema_bfq_5 | float | Y | 指数移动平均-N=5 |
| ema_bfq_60 | float | Y | 指数移动平均-N=60 |
| ema_bfq_90 | float | Y | 指数移动平均-N=90 |
| emv_bfq | float | Y | 简易波动指标-HIGH, LOW, VOL, N=14, M=9 |
| maemv_bfq | float | Y | 简易波动指标-HIGH, LOW, VOL, N=14, M=9 |
| expma_12_bfq | float | Y | EMA指数平均数指标-CLOSE, N1=12, N2=50 |
| expma_50_bfq | float | Y | EMA指数平均数指标-CLOSE, N1=12, N2=50 |
| kdj_bfq | float | Y | KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3 |
| kdj_d_bfq | float | Y | KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3 |
| kdj_k_bfq | float | Y | KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3 |
| ktn_down_bfq | float | Y | 肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10 |
| ktn_mid_bfq | float | Y | 肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10 |
| ktn_upper_bfq | float | Y | 肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10 |
| lowdays | float | Y | LOWRANGE(LOW)表示当前最低价是近多少周期内最低价的最小值 |
| topdays | float | Y | TOPRANGE(HIGH)表示当前最高价是近多少周期内最高价的最大值 |
| ma_bfq_10 | float | Y | 简单移动平均-N=10 |
| ma_bfq_20 | float | Y | 简单移动平均-N=20 |
| ma_bfq_250 | float | Y | 简单移动平均-N=250 |
| ma_bfq_30 | float | Y | 简单移动平均-N=30 |
| ma_bfq_5 | float | Y | 简单移动平均-N=5 |
| ma_bfq_60 | float | Y | 简单移动平均-N=60 |
| ma_bfq_90 | float | Y | 简单移动平均-N=90 |
| macd_bfq | float | Y | MACD指标-CLOSE, SHORT=12, LONG=26, M=9 |
| macd_dea_bfq | float | Y | MACD指标-CLOSE, SHORT=12, LONG=26, M=9 |
| macd_dif_bfq | float | Y | MACD指标-CLOSE, SHORT=12, LONG=26, M=9 |
| mass_bfq | float | Y | 梅斯线-HIGH, LOW, N1=9, N2=25, M=6 |
| ma_mass_bfq | float | Y | 梅斯线-HIGH, LOW, N1=9, N2=25, M=6 |
| mfi_bfq | float | Y | MFI指标是成交量的RSI指标-CLOSE, HIGH, LOW, VOL, N=14 |
| mtm_bfq | float | Y | 动量指标-CLOSE, N=12, M=6 |
| mtmma_bfq | float | Y | 动量指标-CLOSE, N=12, M=6 |
| obv_bfq | float | Y | 能量潮指标-CLOSE, VOL |
| psy_bfq | float | Y | 投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6 |
| psyma_bfq | float | Y | 投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6 |
| roc_bfq | float | Y | 变动率指标-CLOSE, N=12, M=6 |
| maroc_bfq | float | Y | 变动率指标-CLOSE, N=12, M=6 |
| rsi_bfq_12 | float | Y | RSI指标-CLOSE, N=12 |
| rsi_bfq_24 | float | Y | RSI指标-CLOSE, N=24 |
| rsi_bfq_6 | float | Y | RSI指标-CLOSE, N=6 |
| taq_down_bfq | float | Y | 唐安奇通道(海龟)交易指标-HIGH, LOW, 20 |
| taq_mid_bfq | float | Y | 唐安奇通道(海龟)交易指标-HIGH, LOW, 20 |
| taq_up_bfq | float | Y | 唐安奇通道(海龟)交易指标-HIGH, LOW, 20 |
| trix_bfq | float | Y | 三重指数平滑平均线-CLOSE, M1=12, M2=20 |
| trma_bfq | float | Y | 三重指数平滑平均线-CLOSE, M1=12, M2=20 |
| vr_bfq | float | Y | VR容量比率-CLOSE, VOL, M1=26 |
| wr_bfq | float | Y | W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6 |
| wr1_bfq | float | Y | W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6 |
| xsii_td1_bfq | float | Y | 薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7 |
| xsii_td2_bfq | float | Y | 薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7 |
| xsii_td3_bfq | float | Y | 薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7 |
| xsii_td4_bfq | float | Y | 薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7 |


---

### [215] 沪深市场每日交易统计  ·  指数专题
(api: daily_info | 输出字段: 14 | PIT字段: 否)

# (doc_id=215)  https://tushare.pro/document/2?doc_id=215

## 市场交易统计
接口：daily_info 描述：获取交易所股票交易统计，包括各板块明细 限量：单次最大4000，可循环获取，总量不限制 权限：用户积600积分可调取， 频次有限制，积分越高每分钟调取频次越高，5000积分以上频次相对较高，积分获取方法请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | N | 交易日期（YYYYMMDD格式，下同） |
| ts_code | str | N | 板块代码（请参阅下方列表） |
| exchange | str | N | 股票市场（SH上交所 SZ深交所） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |
| fields | str | N | 指定提取字段 |

| 板块代码（TS_CODE） | 板块名称（TS_NAME） | 数据开始日期 |
| --- | --- | --- |
| SZ_MARKET | 深圳市场 | 20041231 |
| SZ_MAIN | 深圳主板 | 20081231 |
| SZ_A | 深圳A股 | 20080103 |
| SZ_B | 深圳B股 | 20080103 |
| SZ_GEM | 创业板 | 20091030 |
| SZ_SME | 中小企业板 | 20040602 |
| SZ_FUND | 深圳基金市场 | 20080103 |
| SZ_FUND_ETF | 深圳基金ETF | 20080103 |
| SZ_FUND_LOF | 深圳基金LOF | 20080103 |
| SZ_FUND_CEF | 深圳封闭基金 | 20080103 |
| SZ_FUND_SF | 深圳分级基金 | 20080103 |
| SZ_BOND | 深圳债券 | 20080103 |
| SZ_BOND_CN | 深圳债券现券 | 20080103 |
| SZ_BOND_REP | 深圳债券回购 | 20080103 |
| SZ_BOND_ABS | 深圳债券ABS | 20080103 |
| SZ_BOND_GOV | 深圳国债 | 20080103 |
| SZ_BOND_ENT | 深圳企业债 | 20080103 |
| SZ_BOND_COR | 深圳公司债 | 20080103 |
| SZ_BOND_CB | 深圳可转债 | 20080103 |
| SZ_WR | 深圳权证 | 20080103 |
| ---- | ---- | --- |
| SH_MARKET | 上海市场 | 20190102 |
| SH_A | 上海A股 | 19910102 |
| SH_B | 上海B股 | 19920221 |
| SH_STAR | 科创板 | 20190722 |
| SH_REP | 股票回购 | 20190102 |
| SH_FUND | 上海基金市场 | 19901219 |
| SH_FUND_ETF | 上海基金ETF | 19901219 |
| SH_FUND_LOF | 上海基金LOF | 19901219 |
| SH_FUND_REP | 上海基金回购 | 19901219 |
| SH_FUND_CEF | 上海封闭式基金 | 19901219 |
| SH_FUND_METF | 上海交易型货币基金 | 19901219 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 交易日期 |
| ts_code | str | Y | 市场代码 |
| ts_name | str | Y | 市场名称 |
| com_count | int | Y | 挂牌数 |
| total_share | float | Y | 总股本（亿股） |
| float_share | float | Y | 流通股本（亿股） |
| total_mv | float | Y | 总市值（亿元） |
| float_mv | float | Y | 流通市值（亿元） |
| amount | float | Y | 交易金额（亿元） |
| vol | float | Y | 成交量（亿股） |
| trans_count | int | Y | 成交笔数（万笔） |
| pe | float | Y | 平均市盈率 |
| tr | float | Y | 换手率（％），注：深交所暂无此列 |
| exchange | str | Y | 交易所（SH上交所 SZ深交所） |

接口示例
数据示例


---

### [268] 深圳市场每日交易情况  ·  指数专题
(api: sz_daily_info | 输出字段: 9 | PIT字段: 否)

# (doc_id=268)  https://tushare.pro/document/2?doc_id=268

## 深圳市场每日交易概况
接口：sz_daily_info 描述：获取深圳市场每日交易概况 限量：单次最大2000，可循环获取，总量不限制 权限：用户积2000积分可调取， 频次有限制，积分越高每分钟调取频次越高，5000积分以上频次相对较高，积分获取方法请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | N | 交易日期（YYYYMMDD格式，下同） |
| ts_code | str | N | 板块代码 |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

ts_code主要包括：
| 板块代码（TS_CODE） | 板块说明 | 数据开始日期 |
| --- | --- | --- |
| 股票 | 深圳市场股票总和 | 20080102 |
| 主板A股 | 深圳主板A股情况 | 20080102 |
| 主板B股 | 深圳主板B股情况 | 20080102 |
| 创业板A股 | 深圳创业板情况 | 20080102 |
| 基金 | 深圳市场基金总和 | 20080102 |
| ETF | 深圳ETF交易情况 | 20080102 |
| LOF | 深圳LOF交易情况 | 20080102 |
| 封闭式基金 | 深圳封闭式基金交易情况 | 20080102 |
| 基础设施基金 | 深圳RETIS基金交易情况 | 20210621 |
| 债券 | 深圳债券市场总和 | 20080102 |
| 债券现券 | 深圳现券交易情况 | 20080102 |
| 债券回购 | 深圳债券回购交易情况 | 20080102 |
| ABS | 深圳ABS交易情况 | 20080102 |
| 期权 | 深圳期权总和 | 20080102 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y |  |
| ts_code | str | Y | 市场类型 |
| count | int | Y | 股票个数 |
| amount | float | Y | 成交金额 |
| vol | None | Y | 成交量 |
| total_share | float | Y | 总股本 |
| total_mv | float | Y | 总市值 |
| float_share | float | Y | 流通股票 |
| float_mv | float | Y | 流通市值 |

接口示例
数据示例


---

### [18] 公募基金  ·  (顶级)
(api: — | 输出字段: 0 | PIT字段: 否)

# (doc_id=18)  https://tushare.pro/document/2?doc_id=18

## 基金数据
在Tushare Pro基金数据模块里面，我们打算上线公募基金和私募基金两部分数据，数据来源于网络公开渠道和第三方合作伙伴。当前阶段，我们先上线部分公募基金数据，包括了基金基础信息,基金净值,基金分红等常规数据。未来将逐步丰富数据内容,同时进一步加强数据的稳定性与可靠性。
公募基金列表
公募基金公司
公募基金净值
场内基金日线行情
公募基金分红
公募基金持仓数据


---

### [19] 基金列表  ·  公募基金
(api: fund_basic | 输出字段: 25 | PIT字段: 否)

# (doc_id=19)  https://tushare.pro/document/2?doc_id=19

## 公募基金列表
接口：fund_basic，可以通过 数据工具 调试和查看数据。 描述：获取公募基金数据列表，包括场内和场外基金 积分：用户需要2000积分才可以调取，单次最大可以提取15000条数据，5000积分以上权限更高，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 基金代码 |
| market | str | N | 交易市场: E场内 O场外（默认E） |
| status | str | N | 存续状态 D摘牌 I发行 L上市中 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 基金代码 |
| name | str | Y | 简称 |
| management | str | Y | 管理人 |
| custodian | str | Y | 托管人 |
| fund_type | str | Y | 投资类型 |
| found_date | str | Y | 成立日期 |
| due_date | str | Y | 到期日期 |
| list_date | str | Y | 上市时间 |
| issue_date | str | Y | 发行日期 |
| delist_date | str | Y | 退市日期 |
| issue_amount | float | Y | 发行份额(亿) |
| m_fee | float | Y | 管理费 |
| c_fee | float | Y | 托管费 |
| duration_year | float | Y | 存续期 |
| p_value | float | Y | 面值 |
| min_amount | float | Y | 起点金额(万元) |
| exp_return | float | Y | 预期收益率 |
| benchmark | str | Y | 业绩比较基准 |
| status | str | Y | 存续状态D摘牌 I发行 L已上市 |
| invest_type | str | Y | 投资风格 |
| type | str | Y | 基金类型 |
| trustee | str | Y | 受托人 |
| purc_startdate | str | Y | 日常申购起始日 |
| redm_startdate | str | Y | 日常赎回起始日 |
| market | str | Y | E场内O场外 |

接口用例
数据样例


---

### [118] 基金管理人  ·  公募基金
(api: fund_company | 输出字段: 18 | PIT字段: 否)

# (doc_id=118)  https://tushare.pro/document/2?doc_id=118

## 公募基金公司
接口：fund_company 描述：获取公募基金管理人列表 积分：用户需要1500积分才可以调取，一次可以提取全部数据。具体请参阅 积分获取办法
输入参数
无，可提取全部
输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| name | str | Y | 基金公司名称 |
| shortname | str | Y | 简称 |
| short_enname | str | N | 英文缩写 |
| province | str | Y | 省份 |
| city | str | Y | 城市 |
| address | str | Y | 注册地址 |
| phone | str | Y | 电话 |
| office | str | Y | 办公地址 |
| website | str | Y | 公司网址 |
| chairman | str | Y | 法人代表 |
| manager | str | Y | 总经理 |
| reg_capital | float | Y | 注册资本 |
| setup_date | str | Y | 成立日期 |
| end_date | str | Y | 公司终止日期 |
| employees | float | Y | 员工总数 |
| main_business | str | Y | 主要产品及业务 |
| org_code | str | Y | 组织机构代码 |
| credit_code | str | Y | 统一社会信用代码 |

接口示例
数据示例


---

### [208] 基金经理  ·  公募基金
(api: fund_manager | 输出字段: 10 | PIT字段: 是)

# (doc_id=208)  https://tushare.pro/document/2?doc_id=208

## 基金经理
接口：fund_manager 描述：获取公募基金经理数据，包括基金经理简历等数据 限量：单次最大5000，支持分页提取数据 积分：用户有500积分可获取数据，2000积分以上可以提高访问频次
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 基金代码，支持多只基金，逗号分隔 |
| ann_date | str | N | 公告日期，格式：YYYYMMDD |
| name | str | N | 基金经理姓名 |
| offset | intint | N | 开始行数 |
| limit | int | N | 每页行数 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 基金代码 |
| ann_date | str | Y | 公告日期 |
| name | str | Y | 基金经理姓名 |
| gender | str | Y | 性别 |
| birth_year | str | Y | 出生年份 |
| edu | str | Y | 学历 |
| nationality | str | Y | 国籍 |
| begin_date | str | Y | 任职日期 |
| end_date | str | Y | 离任日期 |
| resume | str | Y | 简历 |

代码示例
数据示例

## [PIT / 更新口径 — 自动标记]
- (字段) `ann_date` — str N 公告日期，格式：YYYYMMDD  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `ann_date` — str Y 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [462] 基金业绩基准  ·  公募基金
(api: mkt_idx_bmk | 输出字段: 8 | PIT字段: 否)

# (doc_id=462)  https://tushare.pro/document/2?doc_id=462

## 公募基金业绩基准库
## 接口介绍
接口：mkt_idx_bmk 描述：获取官方发布的ETF业绩比较基准列表信息，分为一类库、二类库 限量：单次最大500条，单次可以提取全部列表 积分：需要5000积分可以调取，具体请参阅 积分获取办法
## 输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 指数代码 |
| bmk_type | str | N | 基准类型：策略指数、行业主题指数、行业主题指数、宽基指数 |
| bmk_level | str | N | 基准分类： 一类库、二类库 |

## 输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS代码 |
| symbol | str | Y | 代码 |
| name | str | Y | 指数简称 |
| fullname | str | Y | 指数名称 |
| bmk_level | str | Y | 基准库分层 一类库、二类库 |
| bmk_type | str | Y | 基准类型 策略、宽基、行业主题 |
| bmk_src | str | Y | 指数编制机构 |
| idx_type | str | Y | 指数类型 策略类指数；规模类指数；主题类指数；综合类指数；行业类指数；风格类指数 |

## 代码示例
## 数据结果


---

### [207] 基金规模  ·  公募基金
(api: fund_share | 输出字段: 3 | PIT字段: 否)

# (doc_id=207)  https://tushare.pro/document/2?doc_id=207

## 基金规模数据
接口：fund_share，可以通过 数据工具 调试和查看数据。 描述：获取基金规模数据，包含上海和深圳ETF基金 限量：单次最大提取2000行数据 积分：用户需要至少2000积分可以调取，5000积分以上频次较高，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | TS基金代码 |
| trade_date | str | N | 交易日期 |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |
| market | str | N | 市场代码（SH上交所 ，SZ深交所） |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 基金代码，支持多只基金同时提取，用逗号分隔 |
| trade_date | str | Y | 交易（变动）日期，格式YYYYMMDD |
| fd_share | float | Y | 基金份额（万） |

代码示例
数据示例


---

### [119] 基金净值  ·  公募基金
(api: fund_nav | 输出字段: 9 | PIT字段: 是)

# (doc_id=119)  https://tushare.pro/document/2?doc_id=119

## 公募基金净值
接口：fund_nav，可以通过 数据工具 调试和查看数据。 描述：获取公募基金净值数据 积分：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | TS基金代码 （二选一） |
| nav_date | str | N | 净值日期 （二选一） |
| market | str | N | E场内 O场外 |
| start_date | str | N | 净值开始日期 |
| end_date | str | N | 净值结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS代码 |
| ann_date | str | Y | 公告日期 |
| nav_date | str | Y | 净值日期 |
| unit_nav | float | Y | 单位净值 |
| accum_nav | float | Y | 累计净值 |
| accum_div | float | Y | 累计分红 |
| net_asset | float | Y | 资产净值 |
| total_netasset | float | Y | 合计资产净值 |
| adj_nav | float | Y | 复权单位净值 |

代码示例
数据示例

## [PIT / 更新口径 — 自动标记]
- (字段) `ann_date` — str Y 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [120] 基金分红  ·  公募基金
(api: fund_div | 输出字段: 16 | PIT字段: 是)

# (doc_id=120)  https://tushare.pro/document/2?doc_id=120

## 公募基金分红
接口：fund_div 描述：获取公募基金分红数据 积分：用户需要至少400积分才可以调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ann_date | str | N | 公告日（以下参数四选一） |
| ex_date | str | N | 除息日 |
| pay_date | str | N | 派息日 |
| ts_code | str | N | 基金代码 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS代码 |
| ann_date | str | Y | 公告日期 |
| imp_anndate | str | Y | 分红实施公告日 |
| base_date | str | Y | 分配收益基准日 |
| div_proc | str | Y | 方案进度 |
| record_date | str | Y | 权益登记日 |
| ex_date | str | Y | 除息日 |
| pay_date | str | Y | 派息日 |
| earpay_date | str | Y | 收益支付日 |
| net_ex_date | str | Y | 净值除权日 |
| div_cash | float | Y | 每股派息(元) |
| base_unit | float | Y | 基准基金份额(万份) |
| ear_distr | float | Y | 可分配收益(元) |
| ear_amount | float | Y | 收益分配金额(元) |
| account_date | str | Y | 红利再投资到账日 |
| base_year | str | Y | 份额基准年度 |

接口示例
数据示例

## [PIT / 更新口径 — 自动标记]
- (字段) `ann_date` — str N 公告日（以下参数四选一）  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `ann_date` — str Y 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `imp_anndate` — str Y 分红实施公告日  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [121] 基金持仓  ·  公募基金
(api: fund_portfolio | 输出字段: 8 | PIT字段: 是)

# (doc_id=121)  https://tushare.pro/document/2?doc_id=121

## 公募基金持仓数据
接口：fund_portfolio 描述：获取公募基金持仓数据，季度更新 积分：5000积分以上每分钟请求200次，8000积分以上每分钟请求500次，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 基金代码 (ts_code,ann_date,period至少输入一个参数) |
| symbol | str | N | 股票代码 |
| ann_date | str | N | 公告日期（YYYYMMDD格式） |
| period | str | N | 季度（每个季度最后一天的日期，比如20131231表示2013年年报） |
| start_date | str | N | 报告期开始日期（YYYYMMDD格式） |
| end_date | str | N | 报告期结束日期（YYYYMMDD格式） |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS基金代码 |
| ann_date | str | Y | 公告日期 |
| end_date | str | Y | 截止日期 |
| symbol | str | Y | 股票代码 |
| mkv | float | Y | 持有股票市值(元) |
| amount | float | Y | 持有股票数量（股） |
| stk_mkv_ratio | float | Y | 占股票市值比 |
| stk_float_ratio | float | Y | 占流通股本比例 |

接口示例
数据示例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：fund_portfolio 描述：获取公募基金持仓数据，季度更新 积分：5000积分以上每分钟请求200次，8000积分以上每分钟请求500次，具体请参阅 积分获取办法
- (字段) `ann_date` — str N 公告日期（YYYYMMDD格式）  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `ann_date` — str Y 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [359] 基金技术面因子(专业版)  ·  公募基金
(api: fund_factor_pro | 输出字段: 90 | PIT字段: 否)

# (doc_id=359)  https://tushare.pro/document/2?doc_id=359

## 场内基金技术因子(专业版)
接口：fund_factor_pro 描述：获取场内基金每日技术面因子数据，用于跟踪场内基金当前走势情况，数据由Tushare社区自产，覆盖全历史；输出参数_bfq表示不复权，描述中说明了因子的默认传参，如需要特殊参数或者更多因子可以联系管理员评估 限量：单次最大8000 积分：5000积分每分钟可以请求30次，8000积分以上每分钟500次
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 基金代码 |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |
| trade_date | str | N | 交易日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 基金代码 |
| trade_date | str | Y | 交易日期 |
| trade_date_doris | None | Y | 日期 |
| open | float | Y | 开盘价 |
| high | float | Y | 最高价 |
| low | float | Y | 最低价 |
| close | float | Y | 收盘价 |
| pre_close | float | Y | 昨收价 |
| change | float | Y | 涨跌额 |
| pct_change | float | Y | 涨跌幅 （未复权，如果是复权请用 通用行情接口 ） |
| vol | float | Y | 成交量 （手） |
| amount | float | Y | 成交额 （千元） |
| asi_bfq | float | Y | 振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10 |
| asit_bfq | float | Y | 振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10 |
| atr_bfq | float | Y | 真实波动N日平均值-CLOSE, HIGH, LOW, N=20 |
| bbi_bfq | float | Y | BBI多空指标-CLOSE, M1=3, M2=6, M3=12, M4=20 |
| bias1_bfq | float | Y | BIAS乖离率-CLOSE, L1=6, L2=12, L3=24 |
| bias2_bfq | float | Y | BIAS乖离率-CLOSE, L1=6, L2=12, L3=24 |
| bias3_bfq | float | Y | BIAS乖离率-CLOSE, L1=6, L2=12, L3=24 |
| boll_lower_bfq | float | Y | BOLL指标，布林带-CLOSE, N=20, P=2 |
| boll_mid_bfq | float | Y | BOLL指标，布林带-CLOSE, N=20, P=2 |
| boll_upper_bfq | float | Y | BOLL指标，布林带-CLOSE, N=20, P=2 |
| brar_ar_bfq | float | Y | BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26 |
| brar_br_bfq | float | Y | BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26 |
| cci_bfq | float | Y | 顺势指标又叫CCI指标-CLOSE, HIGH, LOW, N=14 |
| cr_bfq | float | Y | CR价格动量指标-CLOSE, HIGH, LOW, N=20 |
| dfma_dif_bfq | float | Y | 平行线差指标-CLOSE, N1=10, N2=50, M=10 |
| dfma_difma_bfq | float | Y | 平行线差指标-CLOSE, N1=10, N2=50, M=10 |
| dmi_adx_bfq | float | Y | 动向指标-CLOSE, HIGH, LOW, M1=14, M2=6 |
| dmi_adxr_bfq | float | Y | 动向指标-CLOSE, HIGH, LOW, M1=14, M2=6 |
| dmi_mdi_bfq | float | Y | 动向指标-CLOSE, HIGH, LOW, M1=14, M2=6 |
| dmi_pdi_bfq | float | Y | 动向指标-CLOSE, HIGH, LOW, M1=14, M2=6 |
| downdays | float | Y | 连跌天数 |
| updays | float | Y | 连涨天数 |
| dpo_bfq | float | Y | 区间震荡线-CLOSE, M1=20, M2=10, M3=6 |
| madpo_bfq | float | Y | 区间震荡线-CLOSE, M1=20, M2=10, M3=6 |
| ema_bfq_10 | float | Y | 指数移动平均-N=10 |
| ema_bfq_20 | float | Y | 指数移动平均-N=20 |
| ema_bfq_250 | float | Y | 指数移动平均-N=250 |
| ema_bfq_30 | float | Y | 指数移动平均-N=30 |
| ema_bfq_5 | float | Y | 指数移动平均-N=5 |
| ema_bfq_60 | float | Y | 指数移动平均-N=60 |
| ema_bfq_90 | float | Y | 指数移动平均-N=90 |
| emv_bfq | float | Y | 简易波动指标-HIGH, LOW, VOL, N=14, M=9 |
| maemv_bfq | float | Y | 简易波动指标-HIGH, LOW, VOL, N=14, M=9 |
| expma_12_bfq | float | Y | EMA指数平均数指标-CLOSE, N1=12, N2=50 |
| expma_50_bfq | float | Y | EMA指数平均数指标-CLOSE, N1=12, N2=50 |
| kdj_bfq | float | Y | KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3 |
| kdj_d_bfq | float | Y | KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3 |
| kdj_k_bfq | float | Y | KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3 |
| ktn_down_bfq | float | Y | 肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10 |
| ktn_mid_bfq | float | Y | 肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10 |
| ktn_upper_bfq | float | Y | 肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10 |
| lowdays | float | Y | LOWRANGE(LOW)表示当前最低价是近多少周期内最低价的最小值 |
| topdays | float | Y | TOPRANGE(HIGH)表示当前最高价是近多少周期内最高价的最大值 |
| ma_bfq_10 | float | Y | 简单移动平均-N=10 |
| ma_bfq_20 | float | Y | 简单移动平均-N=20 |
| ma_bfq_250 | float | Y | 简单移动平均-N=250 |
| ma_bfq_30 | float | Y | 简单移动平均-N=30 |
| ma_bfq_5 | float | Y | 简单移动平均-N=5 |
| ma_bfq_60 | float | Y | 简单移动平均-N=60 |
| ma_bfq_90 | float | Y | 简单移动平均-N=90 |
| macd_bfq | float | Y | MACD指标-CLOSE, SHORT=12, LONG=26, M=9 |
| macd_dea_bfq | float | Y | MACD指标-CLOSE, SHORT=12, LONG=26, M=9 |
| macd_dif_bfq | float | Y | MACD指标-CLOSE, SHORT=12, LONG=26, M=9 |
| mass_bfq | float | Y | 梅斯线-HIGH, LOW, N1=9, N2=25, M=6 |
| ma_mass_bfq | float | Y | 梅斯线-HIGH, LOW, N1=9, N2=25, M=6 |
| mfi_bfq | float | Y | MFI指标是成交量的RSI指标-CLOSE, HIGH, LOW, VOL, N=14 |
| mtm_bfq | float | Y | 动量指标-CLOSE, N=12, M=6 |
| mtmma_bfq | float | Y | 动量指标-CLOSE, N=12, M=6 |
| obv_bfq | float | Y | 能量潮指标-CLOSE, VOL |
| psy_bfq | float | Y | 投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6 |
| psyma_bfq | float | Y | 投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6 |
| roc_bfq | float | Y | 变动率指标-CLOSE, N=12, M=6 |
| maroc_bfq | float | Y | 变动率指标-CLOSE, N=12, M=6 |
| rsi_bfq_12 | float | Y | RSI指标-CLOSE, N=12 |
| rsi_bfq_24 | float | Y | RSI指标-CLOSE, N=24 |
| rsi_bfq_6 | float | Y | RSI指标-CLOSE, N=6 |
| taq_down_bfq | float | Y | 唐安奇通道(海龟)交易指标-HIGH, LOW, 20 |
| taq_mid_bfq | float | Y | 唐安奇通道(海龟)交易指标-HIGH, LOW, 20 |
| taq_up_bfq | float | Y | 唐安奇通道(海龟)交易指标-HIGH, LOW, 20 |
| trix_bfq | float | Y | 三重指数平滑平均线-CLOSE, M1=12, M2=20 |
| trma_bfq | float | Y | 三重指数平滑平均线-CLOSE, M1=12, M2=20 |
| vr_bfq | float | Y | VR容量比率-CLOSE, VOL, M1=26 |
| wr_bfq | float | Y | W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6 |
| wr1_bfq | float | Y | W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6 |
| xsii_td1_bfq | float | Y | 薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7 |
| xsii_td2_bfq | float | Y | 薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7 |
| xsii_td3_bfq | float | Y | 薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7 |
| xsii_td4_bfq | float | Y | 薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7 |


---

### [134] 期货数据  ·  (顶级)
(api: — | 输出字段: 0 | PIT字段: 否)

# (doc_id=134)  https://tushare.pro/document/2?doc_id=134

## Tushare期货数据
1、Tushare期货交易所代码表
| 交易所名称 | 交易所代码 | 合约后缀 |
| --- | --- | --- |
| 郑州商品交易所 | CZCE | .ZCE |
| 上海期货交易所 | SHFE | .SHF |
| 大连商品交易所 | DCE | .DCE |
| 中国金融期货交易所 | CFFEX | .CFX |
| 上海国际能源交易所 | INE | .INE |
| 广州期货交易所 | GFEX | .GFE |

2、合约代码规则
| 主力合约 | 连续合约 | 普通合约 |
| --- | --- | --- |
| XX | XXL | XXMMDD |
| 例如：CU.SHF | 例如：CUL.SHF 例外：TL0表示30年期国债主力合约，TL表示T合约的主连合约，TLL表示TL合约的主连合约 | 例如：CU1811.SHF |
|  |  |  |
|  |  |  |

| 主力合约 | 连续合约 |
| --- | --- |
| IF.CFX ：沪深300期货主力合约 | IFL.CFX ：沪深300期货当月 |
|  | IFL1.CFX ：沪深300期货次月 |
|  | IFL2.CFX：沪深300期货当季 |
|  | IFL3.CFX：沪深300期货下季 |

中金所其他合约规则同上
3、一些数据规则 在Tushare期货数据里，如果提取跟行情相关的数据，例如日线行情、每日结算参数等，都是带交易所后缀的，比如CU1811.SHF ；如果是提取跟品种相关数据，例如持仓排名，仓单数据等，只需要输入品种代码，比如CU:沪深300期货
4、目前提供的数据列表
| 数据名称 | API | 描述 | 需要最低积分 | 每分钟次数 |
| --- | --- | --- | --- | --- |
| 期货合约列表 | fut_basic | 全部历史 | 2000 | 80 |
| 期货交易日历 | trade_cal | 数据开始月1996年1月，定期更新 | 2000 | 200 |
| 期货日线行情 | fut_daily | 数据开始月1996年1月，每日盘后更新 | 2000 | 120 |
| 每日成交持仓排名 | fut_holding | 数据开始月2002年1月，每日盘后更新 | 2000 | 200 |
| 仓单日报 | fut_wsr | 数据开始月2006年1月，每日盘后更新 | 2000 | 200 |
| 结算参数 | fut_settle | 数据开始月2012年1月，每日盘后更新 | 2000 | 200 |
|  |  |  |  |  |

注：Tushare积分5000以上，正常调取无限制。(积分越高频次越高)


---

### [135] 合约信息  ·  期货数据
(api: fut_basic | 输出字段: 16 | PIT字段: 否)

# (doc_id=135)  https://tushare.pro/document/2?doc_id=135

## 期货合约信息表
接口：fut_basic 描述：获取期货合约列表数据 限量：单次最大10000 积分：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| exchange | str | Y | 交易所代码 CFFEX-中金所 DCE-大商所 CZCE-郑商所 SHFE-上期所 INE-上海国际能源交易中心 GFEX-广州期货交易所 |
| fut_type | str | N | 合约类型 (1 普通合约 2主力与连续合约 默认取全部) |
| fut_code | str | N | 标准合约代码，如白银AG、AP鲜苹果等 |
| list_date | str | N | 上市开始日期(格式YYYYMMDD，从某日开始以来所有合约） |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 合约代码 |
| symbol | str | Y | 交易标识 |
| exchange | str | Y | 交易市场 |
| name | str | Y | 中文简称 |
| fut_code | str | Y | 合约产品代码 |
| multiplier | float | Y | 合约乘数(只适用于国债期货、指数期货) |
| trade_unit | str | Y | 交易计量单位 |
| per_unit | float | Y | 交易单位(每手) |
| quote_unit | str | Y | 报价单位 |
| quote_unit_desc | str | Y | 最小报价单位说明 |
| d_mode_desc | str | Y | 交割方式说明 |
| list_date | str | Y | 上市日期 |
| delist_date | str | Y | 最后交易日期 |
| d_month | str | Y | 交割月份 |
| last_ddate | str | Y | 最后交割日 |
| trade_time_desc | str | N | 交易时间说明 |

接口示例
数据示例


---

### [467] 期货交易日历  ·  期货数据
(api: fut_trade_cal | 输出字段: 4 | PIT字段: 否)

# (doc_id=467)  https://tushare.pro/document/2?doc_id=467

## 交易日历
接口：fut_trade_cal 描述：获取各大期货交易所交易日历数据 积分：需2000积分才可以提取数据
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| exchange | str | N | 交易所 SHFE 上期所 DCE 大商所 CFFEX中金所 CZCE郑商所 INE上海国际能源交易所 |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |
| is_open | int | N | 是否交易 0休市 1交易 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| exchange | str | Y | 交易所 同参数部分描述 |
| cal_date | str | Y | 日历日期 |
| is_open | int | Y | 是否交易 0休市 1交易 |
| pretrade_date | str | N | 上一个交易日 |

接口示例
或者
数据样例


---

### [138] 日线行情  ·  期货数据
(api: fut_daily | 输出字段: 16 | PIT字段: 否)

# (doc_id=138)  https://tushare.pro/document/2?doc_id=138

## 期货日线行情
接口：fut_daily，可以通过 数据工具 调试和查看数据。 描述：期货日线行情数据 限量：单次最大2000条，总量不限制 积分：用户需要至少2000积分才可以调取，未来可能调整积分，请尽量多的积累积分。具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | N | 交易日期(YYYYMMDD格式，下同) |
| ts_code | str | N | 合约代码 |
| exchange | str | N | 交易所代码 |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS合约代码 |
| trade_date | str | Y | 交易日期 |
| pre_close | float | Y | 昨收盘价 |
| pre_settle | float | Y | 昨结算价 |
| open | float | Y | 开盘价 |
| high | float | Y | 最高价 |
| low | float | Y | 最低价 |
| close | float | Y | 收盘价 |
| settle | float | Y | 结算价 |
| change1 | float | Y | 涨跌1 收盘价-昨结算价 |
| change2 | float | Y | 涨跌2 结算价-昨结算价 |
| vol | float | Y | 成交量(手) |
| amount | float | Y | 成交金额(万元) |
| oi | float | Y | 持仓量(手) |
| oi_chg | float | Y | 持仓量变化 |
| delv_settle | float | N | 交割结算价 |

接口示例
数据示例


---

### [337] 期货周/月线行情(每日更新)  ·  期货数据
(api: fut_weekly_monthly | 输出字段: 18 | PIT字段: 否)

# (doc_id=337)  https://tushare.pro/document/2?doc_id=337

## 期货周/月线行情(每日更新)
接口：fut_weekly_monthly 描述：期货周/月线行情(每日更新) 限量：单次最大6000
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | TS代码 |
| trade_date | str | N | 交易日期 |
| start_date | str | N | 开始交易日期 |
| end_date | str | N | 结束交易日期 |
| freq | str | Y | 频率week周，month月 |
| exchange | str | N | 交易所 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 期货代码 |
| trade_date | str | Y | 交易日期（每周五或者月末日期） |
| end_date | str | Y | 计算截至日期 |
| freq | str | Y | 频率(周week,月month) |
| open | float | Y | (周/月)开盘价 |
| high | float | Y | (周/月)最高价 |
| low | float | Y | (周/月)最低价 |
| close | float | Y | (周/月)收盘价 |
| pre_close | float | Y | 前一(周/月)收盘价 |
| settle | float | Y | (周/月)结算价 |
| pre_settle | float | Y | 前一(周/月)结算价 |
| vol | float | Y | (周/月)成交量(手) |
| amount | float | Y | (周/月)成交金额(万元) |
| oi | float | Y | (周/月)持仓量(手) |
| oi_chg | float | Y | (周/月)持仓量变化 |
| exchange | str | Y | 交易所 |
| change1 | float | Y | (周/月)涨跌1 收盘价-昨结算价 |
| change2 | float | Y | (周/月)涨跌2 结算价-昨结算价 |


## [PIT / 更新口径 — 自动标记]
- (正文) 接口：fut_weekly_monthly 描述：期货周/月线行情(每日更新) 限量：单次最大6000


---

### [313] 历史分钟行情  ·  期货数据
(api: ft_mins | 输出字段: 9 | PIT字段: 否)

# (doc_id=313)  https://tushare.pro/document/2?doc_id=313

## 期货历史分钟行情
接口：ft_mins 描述：获取全市场期货合约分钟数据，支持1min/5min/15min/30min/60min行情，提供Python SDK和 http Restful API两种方式，如果需要主力合约分钟，请先通过主力 mapping 接口（需要有至少2000积分）获取对应的合约代码后提取分钟。 限量：单次最大8000行数据，可以通过期货合约代码和时间循环获取，本接口可以提供超过10年历史分钟数据。 权限：需单独开权限，120积分可以调取2次接口查看数据，正式权限请参阅 权限说明 。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码，e.g.CU2310.SHF |
| freq | str | Y | 分钟频度（1min/5min/15min/30min/60min） |
| start_date | datetime | N | 开始日期 格式：2023-08-25 09:00:00 |
| end_date | datetime | N | 结束时间 格式：2023-08-25 19:00:00 |

freq参数说明
| freq | 说明 |
| --- | --- |
| 1min | 1分钟 |
| 5min | 5分钟 |
| 15min | 15分钟 |
| 30min | 30分钟 |
| 60min | 60分钟 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| trade_time | str | Y | 交易时间 |
| open | float | Y | 开盘价（元） |
| close | float | Y | 收盘价（元） |
| high | float | Y | 最高价（元） |
| low | float | Y | 最低价（元） |
| vol | int | Y | 成交量（手） |
| amount | float | Y | 成交金额（元） |
| oi | float | Y | 持仓量（手） |

接口用法
数据样例


---

### [340] 实时分钟行情  ·  期货数据
(api: rt_fut_min | 输出字段: 10 | PIT字段: 否)

# (doc_id=340)  https://tushare.pro/document/2?doc_id=340

## 期货实时分钟行情
接口：rt_fut_min 描述：获取全市场期货合约实时分钟数据，支持1min/5min/15min/30min/60min行情，提供Python SDK、 http Restful API和websocket三种方式，如果需要主力合约分钟，请先通过主力 mapping 接口获取对应的合约代码后提取分钟。 限量：每分钟可以请求500次，支持多个合约同时提取 权限：需单独开权限，正式权限请参阅 权限说明 。
rt_fut_min输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码，e.g.CU2310.SHF，支持多个合约（逗号分隔） |
| freq | str | Y | 分钟频度（1MIN/5MIN/15MIN/30MIN/60MIN） |

同时提供当日开市以来所有历史分钟（即：分钟快照回放），接口名：rt_fut_min_daily，只支持一个个合约提取。
rt_fut_min_daily输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码，e.g.CU2310.SHF，仅支持一次一个合约的回放 |
| freq | str | Y | 分钟频度（1MIN/5MIN/15MIN/30MIN/60MIN） |
| date_str | str | N | 回放日期（格式：YYYY-MM-DD，默认为交易当日，支持回溯一天） |

freq参数说明
| freq | 说明 |
| --- | --- |
| 1MIN | 1分钟 |
| 5MIN | 5分钟 |
| 15MIN | 15分钟 |
| 30MIN | 30分钟 |
| 60MIN | 60分钟 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| code | str | Y | 股票代码 |
| freq | str | Y | 频度 |
| time | str | Y | 交易时间 |
| open | float | Y | 开盘价 |
| close | float | Y | 收盘价 |
| high | float | Y | 最高价 |
| low | float | Y | 最低价 |
| vol | int | Y | 成交量 |
| amount | float | Y | 成交金额 |
| oi | float | Y | 持仓量 |

接口用法


---

### [140] 仓单日报  ·  期货数据
(api: fut_wsr | 输出字段: 17 | PIT字段: 否)

# (doc_id=140)  https://tushare.pro/document/2?doc_id=140

## 仓单日报
接口：fut_wsr 描述：获取仓单日报数据，了解各仓库/厂库的仓单变化 限量：单次最大1000，总量不限制 积分：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | N | 交易日期 |
| symbol | str | N | 产品代码 |
| start_date | str | N | 开始日期(YYYYMMDD格式，下同) |
| end_date | str | N | 结束日期 |
| exchange | str | N | 交易所代码 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 交易日期 |
| symbol | str | Y | 产品代码 |
| fut_name | str | Y | 产品名称 |
| warehouse | str | Y | 仓库名称 |
| wh_id | str | N | 仓库编号 |
| pre_vol | int | Y | 昨日仓单量 |
| vol | int | Y | 今日仓单量 |
| vol_chg | int | Y | 增减量 |
| area | str | N | 地区 |
| year | str | N | 年度 |
| grade | str | N | 等级 |
| brand | str | N | 品牌 |
| place | str | N | 产地 |
| pd | int | N | 升贴水 |
| is_ct | str | N | 是否折算仓单 |
| unit | str | Y | 单位 |
| exchange | str | N | 交易所 |

接口示例
数据示例


---

### [141] 每日结算参数  ·  期货数据
(api: fut_settle | 输出字段: 12 | PIT字段: 否)

# (doc_id=141)  https://tushare.pro/document/2?doc_id=141

## 结算参数
接口：fut_settle 描述：获取每日结算参数数据，包括交易和交割费率等 限量：单次最大返回1600行数据，可根据日期循环，总量不限制 积分：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | N | 交易日期 （trade_date/ts_code至少需要输入一个参数） |
| ts_code | str | N | 合约代码 |
| start_date | str | N | 开始日期(YYYYMMDD格式，下同) |
| end_date | str | N | 结束日期 |
| exchange | str | N | 交易所代码 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 合约代码 |
| trade_date | str | Y | 交易日期 |
| settle | float | Y | 结算价 |
| trading_fee_rate | float | Y | 交易手续费率 |
| trading_fee | float | Y | 交易手续费 |
| delivery_fee | float | Y | 交割手续费 |
| b_hedging_margin_rate | float | Y | 买套保交易保证金率 |
| s_hedging_margin_rate | float | Y | 卖套保交易保证金率 |
| long_margin_rate | float | Y | 买投机交易保证金率 |
| short_margin_rate | float | Y | 卖投机交易保证金率 |
| offset_today_fee | float | N | 平今仓手续率 |
| exchange | str | N | 交易所 |

接口示例
数据示例


---

### [314] 历史Tick行情  ·  期货数据
(api: — | 输出字段: 0 | PIT字段: 是)

# (doc_id=314)  https://tushare.pro/document/2?doc_id=314

## 期货Tick行情数据
获取全市场期货合约的Tick高频行情，当前不提供API方式获取，只提供csv网盘交付，近10年历史数据，一次性网盘拷贝（支持按交易所按日期定制），每天增量更新。tick行情属于单独的数据服务内容，不在积分权限范畴，有需求的用户请微信联系：waditu_a ，联系时请注明期货tick数据。
数据字段内容说明
| 字段 | 类型 | 中文含义 | 样例 |
| --- | --- | --- | --- |
| InstrumentID | string | 合约ID | cu2310 |
| BidPrice1 | float | 买一价 | 68190.000000 |
| BidVolume1 | int | 买一量 | 4 |
| AskPrice1 | float | 卖一价 | 68212.000000 |
| AskVolume1 | int | 卖一量 | 2 |
| LastPrice | float | 最新价 | 68210.000000 |
| Volume | int | 成交量 | 3223 |
| Turnover | float | 成交金额 | 382577245.000000 |
| OpenInterest | int | 持仓量 | 203332.000000 |
| UpperLimitPrice | float | 涨停价 | 68210.000000 |
| LowerLimitPrice | float | 跌停价 | 62210.000000 |
| OpenPrice | float | 今开盘 | 68010.000000 |
| PreSettlementPrice | float | 昨结算价 | 68110.000000 |
| PreClosePrice | float | 昨收盘价 | 68113.000000 |
| PreOpenInterest | int | 昨持仓量 | 3232343.000000 |
| TradingDay | string | 交易日期 | 20230925 |
| UpdateTime | string | 更新时间 | 10:00:00.500 |

文件样例

## [PIT / 更新口径 — 自动标记]
- (正文) 获取全市场期货合约的Tick高频行情，当前不提供API方式获取，只提供csv网盘交付，近10年历史数据，一次性网盘拷贝（支持按交易所按日期定制），每天增量更新。tick行情属于单独的数据服务内容，不在积分权限范畴，有需求的用户请微信联系：waditu_a ，联系时请注明期货tick数据。
- (字段) `UpdateTime` — string 更新时间 10:00:00.500  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [139] 每日持仓排名  ·  期货数据
(api: fut_holding | 输出字段: 10 | PIT字段: 否)

# (doc_id=139)  https://tushare.pro/document/2?doc_id=139

## 每日成交持仓排名
接口：fut_holding 描述：获取每日成交持仓排名数据 限量：单次最大2000，总量不限制 积分：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | N | 交易日期 （trade_date/symbol至少输入一个参数） |
| symbol | str | N | 合约或产品代码 |
| start_date | str | N | 开始日期(YYYYMMDD格式，下同) |
| end_date | str | N | 结束日期 |
| exchange | str | N | 交易所代码 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 交易日期 |
| symbol | str | Y | 合约代码或类型 |
| broker | str | Y | 期货公司会员简称 |
| vol | int | Y | 成交量 |
| vol_chg | int | Y | 成交量变化 |
| long_hld | int | Y | 持买仓量 |
| long_chg | int | Y | 持买仓量变化 |
| short_hld | int | Y | 持卖仓量 |
| short_chg | int | Y | 持卖仓量变化 |
| exchange | str | N | 交易所 |

接口示例
数据示例


---

### [468] 南华期货指数日线行情  ·  期货数据
(api: fut_index_daily | 输出字段: 11 | PIT字段: 否)

# (doc_id=468)  https://tushare.pro/document/2?doc_id=468

## 南华期货指数日线行情
接口：fut_index_daily 描述：获取南华指数每日行情，指数行情也可以通过 通用行情接口 获取数据． 权限：用户需要累积2000积分才可以调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 指数代码（南华期货指数以 .NH 结尾，具体请参考本文最下方） |
| trade_date | str | N | 交易日期 （日期格式：YYYYMMDD，下同） |
| start_date | str | N | 开始日期 |
| end_date | None | N | 结束日期 |

输出参数
| 名称 | 类型 | 描述 |
| --- | --- | --- |
| ts_code | str | TS指数代码 |
| trade_date | str | 交易日 |
| close | float | 收盘点位 |
| open | float | 开盘点位 |
| high | float | 最高点位 |
| low | float | 最低点位 |
| pre_close | float | 昨日收盘点 |
| change | float | 涨跌点 |
| pct_chg | float | 涨跌幅 |
| vol | float | 成交量（手） |
| amount | float | 成交额（千元） |

接口使用
数据样例
指数列表
| 指数代码 | 指数名称 |
| --- | --- |
| NHAI.NH | 南华农产品指数 |
| NHCI.NH | 南华商品指数 |
| NHECI.NH | 南华能化指数 |
| NHFI.NH | 南华黑色指数 |
| NHII.NH | 南华工业品指数 |
| NHMI.NH | 南华金属指数 |
| NHNFI.NH | 南华有色金属 |
| NHPMI.NH | 南华贵金属指数 |
| A.NH | 南华连大豆指数 |
| AG.NH | 南华沪银指数 |
| AL.NH | 南华沪铝指数 |
| AP.NH | 南华郑苹果指数 |
| AU.NH | 南华沪黄金指数 |
| BB.NH | 南华连胶合板指数 |
| BU.NH | 南华沪石油沥青指数 |
| C.NH | 南华连玉米指数 |
| CF.NH | 南华郑棉花指数 |
| CS.NH | 南华连玉米淀粉指数 |
| CU.NH | 南华沪铜指数 |
| CY.NH | 南华棉纱指数 |
| ER.NH | 南华郑籼稻指数 |
| FB.NH | 南华连纤维板指数 |
| FG.NH | 南华郑玻璃指数 |
| FU.NH | 南华沪燃油指数 |
| HC.NH | 南华沪热轧卷板指数 |
| I.NH | 南华连铁矿石指数 |
| J.NH | 南华连焦炭指数 |
| JD.NH | 南华连鸡蛋指数 |
| JM.NH | 南华连焦煤指数 |
| JR.NH | 南华郑粳稻指数 |
| L.NH | 南华连乙烯指数 |
| LR.NH | 南华郑晚籼稻指数 |
| M.NH | 南华连豆粕指数 |
| ME.NH | 南华郑甲醇指数 |
| NI.NH | 南华沪镍指数 |
| P.NH | 南华连棕油指数 |
| PB.NH | 南华沪铅指数 |
| PP.NH | 南华连聚丙烯指数 |
| RB.NH | 南华沪螺钢指数 |
| RM.NH | 南华郑菜籽粕指数 |
| RO.NH | 南华郑菜油指数 |
| RS.NH | 南华郑油菜籽指数 |
| RU.NH | 南华沪天胶指数 |
| SC.NH | 南华原油指数 |
| SF.NH | 南华郑硅铁指数 |
| SM.NH | 南华郑锰硅指数 |
| SN.NH | 南华沪锡指数 |
| SP.NH | 南华纸浆指数 |
| SR.NH | 南华郑白糖指数 |
| TA.NH | 南华郑精对苯二甲酸指数 |
| TC.NH | 南华郑动力煤指数 |
| V.NH | 南华连聚氯乙烯指数 |
| WR.NH | 南华沪线材指数 |
| WS.NH | 南华郑强麦指数 |
| Y.NH | 南华连豆油指数 |
| ZN.NH | 南华沪锌指数 |


---

### [189] 期货主力与连续合约  ·  期货数据
(api: fut_mapping | 输出字段: 3 | PIT字段: 否)

# (doc_id=189)  https://tushare.pro/document/2?doc_id=189

## 期货主力与连续合约
接口：fut_mapping 描述：获取期货主力（或连续）合约与月合约映射数据 限量：单次最大2000条，总量不限制 积分：用户需要至少2000积分才可以调取，未来可能调整积分，请尽可能多积累积分。具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 合约代码 |
| trade_date | str | N | 交易日期(YYYYMMDD格式，下同) |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 连续合约代码 |
| trade_date | str | Y | 起始日期 |
| mapping_ts_code | str | Y | 期货合约代码 |

接口示例
数据示例


---

### [216] 期货主要品种交易周报  ·  期货数据
(api: fut_weekly_detail | 输出字段: 17 | PIT字段: 否)

# (doc_id=216)  https://tushare.pro/document/2?doc_id=216

## 期货主要品种交易周报
接口：fut_weekly_detail 描述：获取期货交易所主要品种每周交易统计信息，数据从2010年3月开始 权限：600积分可调取，单次最大获取4000行数据，积分越高频次越高，5000积分以上正常调取不受限制 数据来源：中国证监会，本数据由Tushare社区成员CE完成规划和采集
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| week | str | N | 周期（每年第几周，e.g. 202001 表示2020第1周） |
| prd | str | N | 期货品种（支持多品种输入，逗号分隔） |
| start_week | str | N | 开始周期 |
| end_week | str | N | 结束周期 |
| exchange | str | N | 交易所（请参考 交易所说明 ） |
| fields | str | N | 提取的字段，e.g. fields='prd,name,vol' |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| exchange | str | Y | 交易所代码 |
| prd | str | Y | 期货品种代码 |
| name | str | Y | 品种名称 |
| vol | int | Y | 成交量（手） |
| vol_yoy | float | Y | 同比增减（%） |
| amount | float | Y | 成交金额（亿元） |
| amout_yoy | float | Y | 同比增减（%） |
| cumvol | int | Y | 年累计成交总量（手） |
| cumvol_yoy | float | Y | 同比增减（%） |
| cumamt | float | Y | 年累计成交金额（亿元） |
| cumamt_yoy | float | Y | 同比增减（%） |
| open_interest | int | Y | 持仓量（手） |
| interest_wow | float | Y | 环比增减（%） |
| mc_close | float | Y | 本周主力合约收盘价 |
| close_wow | float | Y | 环比涨跌（%） |
| week | str | Y | 周期 |
| week_date | str | Y | 周日期 |

接口示例
数据示例


---

### [368] 期货合约涨跌停价格  ·  期货数据
(api: ft_limit | 输出字段: 8 | PIT字段: 否)

# (doc_id=368)  https://tushare.pro/document/2?doc_id=368

## 期货合约涨跌停价格（盘前）
接口：ft_limit 描述：获取所有期货合约每天的涨跌停价格及最低保证金率，数据开始于2005年。 限量：单次最大获取4000行数据，可以通过日期、合约代码等参数循环获取所有历史 积分：用户积5000积分可调取，积分获取方法具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 合约代码 |
| trade_date | str | N | 交易日期（格式：YYYYMMDD） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |
| cont | str | N | 合约代码（例如：cont='CU') |
| exchange | str | N | 交易所代码 （例如：exchange='DCE') |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 交易日期 |
| ts_code | str | Y | TS股票代码 |
| name | str | Y | 合约名称 |
| up_limit | float | Y | 涨停价 |
| down_limit | float | Y | 跌停价 |
| m_ratio | float | Y | 最低交易保证金率（%） |
| cont | str | Y | 合约代码 |
| exchange | str | Y | 交易所代码 |

接口示例
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：ft_limit 描述：获取所有期货合约每天的涨跌停价格及最低保证金率，数据开始于2005年。 限量：单次最大获取4000行数据，可以通过日期、合约代码等参数循环获取所有历史 积分：用户积5000积分可调取，积分获取方法具体请参阅 积分获取办法


---

### [283] 现货数据  ·  (顶级)
(api: — | 输出字段: 0 | PIT字段: 否)

# (doc_id=283)  https://tushare.pro/document/2?doc_id=283

## 现货数据
主要提供上海黄金交易所现货数据，包括：
黄金现货基础信息
现货黄金日行情


---

### [284] 上海黄金基础信息  ·  现货数据
(api: sge_basic | 输出字段: 14 | PIT字段: 否)

# (doc_id=284)  https://tushare.pro/document/2?doc_id=284

## 黄金现货基础信息
接口：sge_basic 描述：获取上海黄金交易所现货合约基础信息 限量：单次最大100条，当前现货合约数不足20个，可以一次提取全部，不需要循环提取 积分：用户积5000积分可以调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 合约代码 （支持多个，逗号分隔，不输入为获取全部） |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 品种代码 |
| ts_name | str | Y | 品种名称 |
| trade_type | str | Y | 交易类型 |
| t_unit | float | Y | 交易单位(克/手) |
| p_unit | float | Y | 报价单位 |
| min_change | float | Y | 最小变动价位 |
| price_limit | float | Y | 每日价格最大波动限制 |
| min_vol | int | Y | 最小单笔报价量(手) |
| max_vol | int | Y | 最大单笔报价量(手) |
| trade_mode | str | Y | 交易期限 |
| margin_rate | float | Y | 保证金比例 |
| liq_rate | float | Y | 违约金比例(%) |
| trade_time | str | Y | 交易时间 |
| list_date | str | Y | 上市日期 |

接口用法
或者
数据样例


---

### [285] 上海黄金现货日行情  ·  现货数据
(api: sge_daily | 输出字段: 14 | PIT字段: 否)

# (doc_id=285)  https://tushare.pro/document/2?doc_id=285

## 现货黄金日行情
接口：sge_daily 描述：获取上海黄金交易所现货合约日线行情 限量：单次最大2000，可循环或者分页提取 积分：用户积2000积分可调取，具体请参阅 积分获取办法
注：数据由当日9:00至15:30的交易和前一日夜盘的20:00至2:30数据构成，成交量和成交金额为双向计量。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 合约代码，可通过 基础信息 获得 |
| trade_date | str | N | 交易日期 |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 现货合约代码 |
| trade_date | str | Y | 交易日 |
| close | float | Y | 收盘点(元/克) |
| open | float | Y | 开盘点(元/克) |
| high | float | Y | 最高点(元/克) |
| low | float | Y | 最低点(元/克) |
| price_avg | float | Y | 加权平均价(元/克) |
| change | float | Y | 涨跌点位(元/克) |
| pct_change | float | Y | 涨跌幅 |
| vol | float | Y | 成交量(千克) |
| amount | float | Y | 成交金额(元) |
| oi | float | Y | 市场持仓 |
| settle_vol | float | Y | 交收量 |
| settle_dire | str | Y | 持仓方向 |

接口示例
数据示例


---

### [157] 期权数据  ·  (顶级)
(api: — | 输出字段: 0 | PIT字段: 否)

# (doc_id=157)  https://tushare.pro/document/2?doc_id=157

## Tushare期权数据
1、Tushare期权交易所代码表
| 交易所名称 | 交易所代码 | 合约后缀 |
| --- | --- | --- |
| 郑州商品交易所 | CZCE | .ZCE |
| 上海期货交易所 | SHFE | .SHF |
| 大连商品交易所 | DCE | .DCE |
| 上海证券交易所 | SSE | .SH |
| 深圳证券交易所 | SZSE | .SZ |
| 中国金融期货交易所 | CFFEX | .CFX |

2、目前提供的数据列表
期权合约信息
期权日线行情


---

### [158] 期权合约信息  ·  期权数据
(api: opt_basic | 输出字段: 20 | PIT字段: 否)

# (doc_id=158)  https://tushare.pro/document/2?doc_id=158

## 期权合约信息
接口：opt_basic 描述：获取期权合约信息 积分：用户需要至少5000积分可以调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | TS期权代码 |
| exchange | str | N | 交易所代码 （包括上交所SSE等 交易所 ） |
| list_date | str | N | 上市交易日 |
| opt_code | str | N | 标准合约代码，OP+期货合约TS_CODE，如棕榈油2207合约，输入OPP2207.DCE |
| call_put | str | N | 期权类型 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS代码 |
| symbol | str | Y | 交易代码 |
| exchange | str | Y | 交易市场 |
| name | str | Y | 合约名称 |
| per_unit | str | Y | 合约单位 |
| opt_code | str | Y | 标的合约代码 |
| opt_type | str | Y | 合约类型 |
| call_put | str | Y | 期权类型 |
| exercise_type | str | Y | 行权方式 |
| exercise_price | float | Y | 行权价格，经过除权除息调整 |
| opt_multiplier | float | Y | 合约单位，经过除权除息调整 |
| s_month | str | Y | 结算月 |
| maturity_date | str | Y | 到期日 |
| list_price | float | Y | 挂牌基准价 |
| list_date | str | Y | 开始交易日期 |
| delist_date | str | Y | 最后交易日期 |
| last_edate | str | Y | 最后行权日期 |
| last_ddate | str | Y | 最后交割日期 |
| quote_unit | str | Y | 报价单位 |
| min_price_chg | str | Y | 最小价格波幅 |

接口示例
数据示例


---

### [159] 期权日线行情  ·  期权数据
(api: opt_daily | 输出字段: 13 | PIT字段: 否)

# (doc_id=159)  https://tushare.pro/document/2?doc_id=159

## 期权日线行情
接口：opt_daily 描述：获取期权日线行情 限量：单次最大15000条数据，可跟进日线或者代码循环，总量不限制 积分：用户需要至少2000积分才可以调取，但有流量控制，请自行提高积分，积分越多权限越大，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | TS合约代码（输入代码或时间至少任意一个参数） |
| trade_date | str | N | 交易日期 |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |
| exchange | str | N | 交易所(SSE/SZSE/CFFEX/DCE/SHFE/CZCE） |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS代码 |
| trade_date | str | Y | 交易日期 |
| exchange | str | Y | 交易市场 |
| pre_settle | float | Y | 昨结算价 |
| pre_close | float | Y | 前收盘价 |
| open | float | Y | 开盘价 |
| high | float | Y | 最高价 |
| low | float | Y | 最低价 |
| close | float | Y | 收盘价 |
| settle | float | Y | 结算价 |
| vol | float | Y | 成交量(手) |
| amount | float | Y | 成交金额(万元) |
| oi | float | Y | 持仓量(手) |

接口示例
数据示例


---

### [341] 期权分钟行情  ·  期权数据
(api: opt_mins | 输出字段: 9 | PIT字段: 否)

# (doc_id=341)  https://tushare.pro/document/2?doc_id=341

## 期权历史分钟行情
接口：opt_mins 描述：获取全市场期权合约分钟数据，支持1min/5min/15min/30min/60min行情，提供Python SDK和 http Restful API两种方式。 限量：单次最大8000行数据，可以通过合约代码和时间循环获取。 权限：120积分可以调取2次接口查看数据，正式权限请参阅 权限说明 。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码，e.g：10007976.SH |
| freq | str | Y | 分钟频度（1min/5min/15min/30min/60min） |
| start_date | datetime | N | 开始日期 格式：2024-08-25 09:00:00 |
| end_date | datetime | N | 结束时间 格式：2024-08-25 19:00:00 |

freq参数说明
| freq | 说明 |
| --- | --- |
| 1min | 1分钟 |
| 5min | 5分钟 |
| 15min | 15分钟 |
| 30min | 30分钟 |
| 60min | 60分钟 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| trade_time | str | Y | 交易时间 |
| open | float | Y | 开盘价 |
| close | float | Y | 收盘价 |
| high | float | Y | 最高价 |
| low | float | Y | 最低价 |
| vol | int | Y | 成交量 |
| amount | float | Y | 成交金额 |
| oi | float | Y | 持仓量 |

接口用法
数据样例


---

### [184] 债券专题  ·  (顶级)
(api: — | 输出字段: 0 | PIT字段: 否)

# (doc_id=184)  https://tushare.pro/document/2?doc_id=184

## Tushare债券数据
目前提供的债券数据列表
可转债基础信息数据
可转债发行数据
可转债日线行情数据


---

### [185] 可转债基础信息  ·  债券专题
(api: cb_basic | 输出字段: 38 | PIT字段: 否)

# (doc_id=185)  https://tushare.pro/document/2?doc_id=185

## 可转债基本信息
接口：cb_basic 描述：获取可转债基本信息 限量：单次最大2000，总量不限制 权限：用户需要至少2000积分才可以调取，但有流量控制，5000积分以上频次相对较高，积分越多权限越大，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 转债代码 |
| list_date | str | N | 上市日期 |
| exchange | str | N | 上市交易所 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 转债代码 |
| bond_full_name | str | Y | 转债名称 |
| bond_short_name | str | Y | 转债简称 |
| cb_code | str | Y | 转股申报代码 |
| cb_type | str | Y | 转债类型: CB-可转债,EB-可交换债 |
| stk_code | str | Y | 正股代码 |
| stk_short_name | str | Y | 正股简称 |
| maturity | float | Y | 发行期限（年） |
| par | float | Y | 面值 |
| issue_price | float | Y | 发行价格 |
| issue_size | float | Y | 发行总额（元） |
| remain_size | float | Y | 债券余额（元） |
| value_date | str | Y | 起息日期 |
| maturity_date | str | Y | 到期日期 |
| rate_type | str | Y | 利率类型 |
| coupon_rate | float | Y | 票面利率（%） |
| add_rate | float | Y | 补偿利率（%） |
| pay_per_year | int | Y | 年付息次数 |
| list_date | str | Y | 上市日期 |
| delist_date | str | Y | 摘牌日 |
| exchange | str | Y | 上市交易所 |
| conv_start_date | str | Y | 转股起始日 |
| conv_end_date | str | Y | 转股截止日 |
| conv_stop_date | str | Y | 停止转股日(提前到期) |
| first_conv_price | float | Y | 初始转股价 |
| conv_price | float | Y | 最新转股价 |
| rate_clause | str | Y | 利率说明 |
| put_clause | str | N | 回售条款 |
| maturity_call_price | str | N | 到期赎回价格(含税) |
| maturity_put_price | str | N | 到期赎回价格(含税)[更名停用，请使用maturity_call_price] |
| call_clause | str | N | 赎回条款 |
| reset_clause | str | N | 特别向下修正条款 |
| conv_clause | str | N | 转股条款 |
| guarantor | str | N | 担保人 |
| guarantee_type | str | N | 担保方式 |
| issue_rating | str | N | 发行信用等级 |
| newest_rating | str | N | 最新信用等级 |
| rating_comp | str | N | 最新评级机构 |

接口示例
数据示例


---

### [186] 可转债发行  ·  债券专题
(api: cb_issue | 输出字段: 35 | PIT字段: 是)

# (doc_id=186)  https://tushare.pro/document/2?doc_id=186

## 可转债发行
接口：cb_issue 描述：获取可转债发行数据 限量：单次最大2000，可多次提取，总量不限制 积分：用户需要至少2000积分才可以调取，5000积分以上频次相对较高，积分越多权限越大，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | TS代码 |
| ann_date | str | N | 发行公告日 |
| start_date | str | N | 公告开始日期 |
| end_date | str | N | 公告结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 转债代码 |
| ann_date | str | Y | 发行公告日 |
| res_ann_date | str | Y | 发行结果公告日 |
| plan_issue_size | float | Y | 计划发行总额（元） |
| issue_size | float | Y | 发行总额（元） |
| issue_price | float | Y | 发行价格 |
| issue_type | str | Y | 发行方式 |
| issue_cost | float | N | 发行费用（元） |
| onl_code | str | Y | 网上申购代码 |
| onl_name | str | Y | 网上申购简称 |
| onl_date | str | Y | 网上发行日期 |
| onl_size | float | Y | 网上发行总额（张） |
| onl_pch_vol | float | Y | 网上发行有效申购数量（张） |
| onl_pch_num | int | Y | 网上发行有效申购户数 |
| onl_pch_excess | float | Y | 网上发行超额认购倍数 |
| onl_winning_rate | float | N | 网上发行中签率（%） |
| shd_ration_code | str | Y | 老股东配售代码 |
| shd_ration_name | str | Y | 老股东配售简称 |
| shd_ration_date | str | Y | 老股东配售日 |
| shd_ration_record_date | str | Y | 老股东配售股权登记日 |
| shd_ration_pay_date | str | Y | 老股东配售缴款日 |
| shd_ration_price | float | Y | 老股东配售价格 |
| shd_ration_ratio | float | Y | 老股东配售比例 |
| shd_ration_size | float | Y | 老股东配售数量（张） |
| shd_ration_vol | float | N | 老股东配售有效申购数量（张） |
| shd_ration_num | int | N | 老股东配售有效申购户数 |
| shd_ration_excess | float | N | 老股东配售超额认购倍数 |
| offl_size | float | Y | 网下发行总额（张） |
| offl_deposit | float | N | 网下发行定金比例（%） |
| offl_pch_vol | float | N | 网下发行有效申购数量（张） |
| offl_pch_num | int | N | 网下发行有效申购户数 |
| offl_pch_excess | float | N | 网下发行超额认购倍数 |
| offl_winning_rate | float | N | 网下发行中签率 |
| lead_underwriter | str | N | 主承销商 |
| lead_underwriter_vol | float | N | 主承销商包销数量（张） |

接口示例
数据示例

## [PIT / 更新口径 — 自动标记]
- (字段) `ann_date` — str N 发行公告日  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `ann_date` — str Y 发行公告日  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `res_ann_date` — str Y 发行结果公告日  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [269] 可转债赎回信息  ·  债券专题
(api: cb_call | 输出字段: 11 | PIT字段: 是)

# (doc_id=269)  https://tushare.pro/document/2?doc_id=269

## 可转债赎回信息
接口：cb_call，可以通过 数据工具 调试和查看数据。 描述：获取可转债到期赎回、强制赎回等信息。数据来源于公开披露渠道，供个人和机构研究使用，请不要用于数据商业目的。 限量：单次最大2000条数据，可以根据日期循环提取，本接口需5000积分。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 转债代码，支持多值输入 |
| ann_date | str | N | 公告日期(YYYYMMDD格式，下同) |
| start_date | str | N | 公告开始日期 |
| end_date | str | N | 公告结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 转债代码 |
| call_type | str | Y | 赎回类型：到赎、强赎 |
| is_call | str | Y | 是否赎回：已满足强赎条件、公告提示强赎、公告实施强赎、公告到期赎回、公告不强赎 |
| ann_date | str | Y | 公告/提示日期 |
| call_date | str | Y | 赎回日期 |
| call_price | float | Y | 赎回价格(含税，元/张) |
| call_price_tax | float | Y | 赎回价格(扣税，元/张) |
| call_vol | float | Y | 赎回债券数量(张) |
| call_amount | float | Y | 赎回金额(万元) |
| payment_date | str | Y | 行权后款项到账日 |
| call_reg_date | str | Y | 赎回登记日 |

接口示例
数据示例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：cb_call，可以通过 数据工具 调试和查看数据。 描述：获取可转债到期赎回、强制赎回等信息。数据来源于公开披露渠道，供个人和机构研究使用，请不要用于数据商业目的。 限量：单次最大2000条数据，可以根据日期循环提取，本接口需5000积分。
- (字段) `ann_date` — str N 公告日期(YYYYMMDD格式，下同)  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `ann_date` — str Y 公告/提示日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [305] 可转债票面利率  ·  债券专题
(api: cb_rate | 输出字段: 5 | PIT字段: 否)

# (doc_id=305)  https://tushare.pro/document/2?doc_id=305

## 可转债票面利率
接口：cb_rate 描述：获取可转债票面利率 限量：单次最大2000，总量不限制 权限：用户需要至少5000积分才可以调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 转债代码，支持多值输入 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 转债代码 |
| rate_freq | int | N | 付息频率(次/年) |
| rate_start_date | str | N | 付息开始日期 |
| rate_end_date | str | N | 付息结束日期 |
| coupon_rate | float | N | 票面利率(%) |

接口示例
数据示例


---

### [187] 可转债行情  ·  债券专题
(api: cb_daily | 输出字段: 15 | PIT字段: 否)

# (doc_id=187)  https://tushare.pro/document/2?doc_id=187

## 可转债行情
接口：cb_daily 描述：获取可转债行情 限量：单次最大2000条，可多次提取，总量不限制 积分：用户需要至少2000积分才可以调取，5000积分以上频次相对较高，积分越多权限越大，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | TS代码 |
| trade_date | str | N | 交易日期(YYYYMMDD格式，下同) |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 转债代码 |
| trade_date | str | Y | 交易日期 |
| pre_close | float | Y | 昨收盘价(元) |
| open | float | Y | 开盘价(元) |
| high | float | Y | 最高价(元) |
| low | float | Y | 最低价(元) |
| close | float | Y | 收盘价(元) |
| change | float | Y | 涨跌(元) |
| pct_chg | float | Y | 涨跌幅(%) |
| vol | float | Y | 成交量(手) |
| amount | float | Y | 成交金额(万元) |
| bond_value | float | N | 纯债价值 |
| bond_over_rate | float | N | 纯债溢价率(%) |
| cb_value | float | N | 转股价值 |
| cb_over_rate | float | N | 转股溢价率(%) |

接口示例
数据示例


---

### [459] 可转债十大持有人  ·  债券专题
(api: top10_cb_holders | 输出字段: 6 | PIT字段: 否)

# (doc_id=459)  https://tushare.pro/document/2?doc_id=459

## 可转债十大持有人
## 接口介绍
接口：top10_cb_holders 描述：获取可转债前十大持有人 限量：单次最大3000条，可根据代码或日期循环提取 积分：需要5000积分可以调取，具体请参阅 积分获取办法
## 输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS代码，支持多值输入，如110059.SH,110060.SH |
| period | str | N | 报告期（YYYYMMDD格式，年中和年报日期，如20240630,20251231） |
| start_date | str | N | 报告期开始日期 |
| end_date | str | N | 报告期结束日期 |

## 输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 转债代码 |
| end_date | str | Y | 报告期 |
| holder_rank | int | Y | 持有排名 |
| holder_name | str | Y | 持有人名称 |
| hold_amount | float | Y | 持有数量(万张) |
| hold_ratio | float | Y | 持有比例(%) |

## 代码示例
## 数据结果


---

### [392] 可转债技术面因子(专业版)  ·  债券专题
(api: cb_factor_pro | 输出字段: 89 | PIT字段: 否)

# (doc_id=392)  https://tushare.pro/document/2?doc_id=392

## 可转债技术因子(专业版)
接口：cb_factor_pro 描述：获取可转债每日技术面因子数据，用于跟踪可转债当前走势情况，数据由Tushare社区自产，覆盖全历史；输出参数_bfq表示不复权，_qfq表示前复权 _hfq表示后复权，描述中说明了因子的默认传参，如需要特殊参数或者更多因子可以联系管理员评估 限量：单次调取最多返回10000条数据，可以通过日期参数循环 积分：5000积分每分钟可以请求30次，8000积分以上每分钟500次，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 可转债代码 |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |
| trade_date | str | N | 交易日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 转债代码 |
| trade_date | str | Y | 交易日期 |
| open | float | Y | 开盘价 |
| high | float | Y | 最高价 |
| low | float | Y | 最低价 |
| close | float | Y | 收盘价 |
| pre_close | float | Y | 昨收价 |
| change | float | Y | 涨跌额 |
| pct_change | float | Y | 涨跌幅 （未复权，如果是复权请用 通用行情接口 ） |
| vol | float | Y | 成交量 （手） |
| amount | float | Y | 成交金额(万元) |
| asi_bfq | float | Y | 振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10 |
| asit_bfq | float | Y | 振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10 |
| atr_bfq | float | Y | 真实波动N日平均值-CLOSE, HIGH, LOW, N=20 |
| bbi_bfq | float | Y | BBI多空指标-CLOSE, M1=3, M2=6, M3=12, M4=20 |
| bias1_bfq | float | Y | BIAS乖离率-CLOSE, L1=6, L2=12, L3=24 |
| bias2_bfq | float | Y | BIAS乖离率-CLOSE, L1=6, L2=12, L3=24 |
| bias3_bfq | float | Y | BIAS乖离率-CLOSE, L1=6, L2=12, L3=24 |
| boll_lower_bfq | float | Y | BOLL指标，布林带-CLOSE, N=20, P=2 |
| boll_mid_bfq | float | Y | BOLL指标，布林带-CLOSE, N=20, P=2 |
| boll_upper_bfq | float | Y | BOLL指标，布林带-CLOSE, N=20, P=2 |
| brar_ar_bfq | float | Y | BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26 |
| brar_br_bfq | float | Y | BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26 |
| cci_bfq | float | Y | 顺势指标又叫CCI指标-CLOSE, HIGH, LOW, N=14 |
| cr_bfq | float | Y | CR价格动量指标-CLOSE, HIGH, LOW, N=20 |
| dfma_dif_bfq | float | Y | 平行线差指标-CLOSE, N1=10, N2=50, M=10 |
| dfma_difma_bfq | float | Y | 平行线差指标-CLOSE, N1=10, N2=50, M=10 |
| dmi_adx_bfq | float | Y | 动向指标-CLOSE, HIGH, LOW, M1=14, M2=6 |
| dmi_adxr_bfq | float | Y | 动向指标-CLOSE, HIGH, LOW, M1=14, M2=6 |
| dmi_mdi_bfq | float | Y | 动向指标-CLOSE, HIGH, LOW, M1=14, M2=6 |
| dmi_pdi_bfq | float | Y | 动向指标-CLOSE, HIGH, LOW, M1=14, M2=6 |
| downdays | float | Y | 连跌天数 |
| updays | float | Y | 连涨天数 |
| dpo_bfq | float | Y | 区间震荡线-CLOSE, M1=20, M2=10, M3=6 |
| madpo_bfq | float | Y | 区间震荡线-CLOSE, M1=20, M2=10, M3=6 |
| ema_bfq_10 | float | Y | 指数移动平均-N=10 |
| ema_bfq_20 | float | Y | 指数移动平均-N=20 |
| ema_bfq_250 | float | Y | 指数移动平均-N=250 |
| ema_bfq_30 | float | Y | 指数移动平均-N=30 |
| ema_bfq_5 | float | Y | 指数移动平均-N=5 |
| ema_bfq_60 | float | Y | 指数移动平均-N=60 |
| ema_bfq_90 | float | Y | 指数移动平均-N=90 |
| emv_bfq | float | Y | 简易波动指标-HIGH, LOW, VOL, N=14, M=9 |
| maemv_bfq | float | Y | 简易波动指标-HIGH, LOW, VOL, N=14, M=9 |
| expma_12_bfq | float | Y | EMA指数平均数指标-CLOSE, N1=12, N2=50 |
| expma_50_bfq | float | Y | EMA指数平均数指标-CLOSE, N1=12, N2=50 |
| kdj_bfq | float | Y | KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3 |
| kdj_d_bfq | float | Y | KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3 |
| kdj_k_bfq | float | Y | KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3 |
| ktn_down_bfq | float | Y | 肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10 |
| ktn_mid_bfq | float | Y | 肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10 |
| ktn_upper_bfq | float | Y | 肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10 |
| lowdays | float | Y | LOWRANGE(LOW)表示当前最低价是近多少周期内最低价的最小值 |
| topdays | float | Y | TOPRANGE(HIGH)表示当前最高价是近多少周期内最高价的最大值 |
| ma_bfq_10 | float | Y | 简单移动平均-N=10 |
| ma_bfq_20 | float | Y | 简单移动平均-N=20 |
| ma_bfq_250 | float | Y | 简单移动平均-N=250 |
| ma_bfq_30 | float | Y | 简单移动平均-N=30 |
| ma_bfq_5 | float | Y | 简单移动平均-N=5 |
| ma_bfq_60 | float | Y | 简单移动平均-N=60 |
| ma_bfq_90 | float | Y | 简单移动平均-N=90 |
| macd_bfq | float | Y | MACD指标-CLOSE, SHORT=12, LONG=26, M=9 |
| macd_dea_bfq | float | Y | MACD指标-CLOSE, SHORT=12, LONG=26, M=9 |
| macd_dif_bfq | float | Y | MACD指标-CLOSE, SHORT=12, LONG=26, M=9 |
| mass_bfq | float | Y | 梅斯线-HIGH, LOW, N1=9, N2=25, M=6 |
| ma_mass_bfq | float | Y | 梅斯线-HIGH, LOW, N1=9, N2=25, M=6 |
| mfi_bfq | float | Y | MFI指标是成交量的RSI指标-CLOSE, HIGH, LOW, VOL, N=14 |
| mtm_bfq | float | Y | 动量指标-CLOSE, N=12, M=6 |
| mtmma_bfq | float | Y | 动量指标-CLOSE, N=12, M=6 |
| obv_bfq | float | Y | 能量潮指标-CLOSE, VOL |
| psy_bfq | float | Y | 投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6 |
| psyma_bfq | float | Y | 投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6 |
| roc_bfq | float | Y | 变动率指标-CLOSE, N=12, M=6 |
| maroc_bfq | float | Y | 变动率指标-CLOSE, N=12, M=6 |
| rsi_bfq_12 | float | Y | RSI指标-CLOSE, N=12 |
| rsi_bfq_24 | float | Y | RSI指标-CLOSE, N=24 |
| rsi_bfq_6 | float | Y | RSI指标-CLOSE, N=6 |
| taq_down_bfq | float | Y | 唐安奇通道(海龟)交易指标-HIGH, LOW, 20 |
| taq_mid_bfq | float | Y | 唐安奇通道(海龟)交易指标-HIGH, LOW, 20 |
| taq_up_bfq | float | Y | 唐安奇通道(海龟)交易指标-HIGH, LOW, 20 |
| trix_bfq | float | Y | 三重指数平滑平均线-CLOSE, M1=12, M2=20 |
| trma_bfq | float | Y | 三重指数平滑平均线-CLOSE, M1=12, M2=20 |
| vr_bfq | float | Y | VR容量比率-CLOSE, VOL, M1=26 |
| wr_bfq | float | Y | W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6 |
| wr1_bfq | float | Y | W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6 |
| xsii_td1_bfq | float | Y | 薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7 |
| xsii_td2_bfq | float | Y | 薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7 |
| xsii_td3_bfq | float | Y | 薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7 |
| xsii_td4_bfq | float | Y | 薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7 |

接口用法
数据样例


---

### [246] 可转债转股价变动  ·  债券专题
(api: cb_price_chg | 输出字段: 7 | PIT字段: 是)

# (doc_id=246)  https://tushare.pro/document/2?doc_id=246

## 可转债转股价变动
接口：cb_price_chg 描述：获取可转债转股价变动 限量：单次最大2000，总量不限制 权限：本接口需单独开权限（跟积分没关系），具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 转债代码，支持多值输入 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 转债代码 |
| bond_short_name | str | Y | 转债简称 |
| publish_date | str | Y | 公告日期 |
| change_date | str | Y | 变动日期 |
| convert_price_initial | float | Y | 初始转股价格 |
| convertprice_bef | float | Y | 修正前转股价格 |
| convertprice_aft | float | Y | 修正后转股价格 |

接口示例
数据示例

## [PIT / 更新口径 — 自动标记]
- (字段) `publish_date` — str Y 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [247] 可转债转股结果  ·  债券专题
(api: cb_share | 输出字段: 15 | PIT字段: 是)

# (doc_id=247)  https://tushare.pro/document/2?doc_id=247

## 可转债转股结果
接口：cb_share 描述：获取可转债转股结果 限量：单次最大2000，总量不限制 权限：用户需要至少2000积分才可以调取，但有流量控制，5000积分以上频次相对较高，积分越多权限越大，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 转债代码，支持多值输入 |
| ann_date | str | Y | 公告日期（YYYYMMDD格式，下同） |
| start_date | str | N | 公告开始日期 |
| end_date | str | N | 公告结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 债券代码 |
| bond_short_name | str | Y | 债券简称 |
| publish_date | str | Y | 公告日期 |
| end_date | str | Y | 统计截止日期 |
| issue_size | float | Y | 可转债发行总额 |
| convert_price_initial | float | Y | 初始转换价格 |
| convert_price | float | Y | 本次转换价格 |
| convert_val | float | Y | 本次转股金额 |
| convert_vol | float | Y | 本次转股数量 |
| convert_ratio | float | Y | 本次转股比例 |
| acc_convert_val | float | Y | 累计转股金额 |
| acc_convert_vol | float | Y | 累计转股数量 |
| acc_convert_ratio | float | Y | 累计转股比例 |
| remain_size | float | Y | 可转债剩余金额 |
| total_shares | float | Y | 转股后总股本 |

接口示例
数据示例

## [PIT / 更新口径 — 自动标记]
- (字段) `ann_date` — str Y 公告日期（YYYYMMDD格式，下同）  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `publish_date` — str Y 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [458] 可转债债券评级  ·  债券专题
(api: cb_rating | 输出字段: 8 | PIT字段: 是)

# (doc_id=458)  https://tushare.pro/document/2?doc_id=458

## 获取可转债评级历史记录
## 接口介绍
接口：cb_rating 描述：获取可转债评级历史记录 限量：单次最大3000条，可根据代码或日期循环提取 积分：需要2000积分可以调取，具体请参阅 积分获取办法
## 输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 转债代码，支持多值输入 |

## 输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 转债代码 |
| ann_date | str | Y | 评级发布日期 |
| rating_date | str | Y | 评级日期 |
| rating_com_name | str | Y | 评级机构 |
| rating_way | str | Y | 评级方式 |
| rating_type | str | Y | 评级类别 |
| rating | str | Y | 信用等级 |
| rating_outlook | str | Y | 评级展望 |

## 代码示例
## 数据结果

## [PIT / 更新口径 — 自动标记]
- (字段) `ann_date` — str Y 评级发布日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [256] 债券回购日行情  ·  债券专题
(api: repo_daily | 输出字段: 12 | PIT字段: 否)

# (doc_id=256)  https://tushare.pro/document/2?doc_id=256

## 债券回购日行情
接口：repo_daily 描述：债券回购日行情 限量：单次最大2000条，可多次提取，总量不限制 权限：用户需要累积2000积分才可以调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | TS代码 |
| trade_date | str | N | 交易日期(YYYYMMDD格式，下同) |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS代码 |
| trade_date | str | Y | 交易日期 |
| repo_maturity | str | Y | 期限品种 |
| pre_close | float | Y | 前收盘(%) |
| open | float | Y | 开盘价(%) |
| high | float | Y | 最高价(%) |
| low | float | Y | 最低价(%) |
| close | float | Y | 收盘价(%) |
| weight | float | Y | 加权价(%) |
| weight_r | float | Y | 加权价(利率债)(%) |
| amount | float | Y | 成交金额(万元) |
| num | int | Y | 成交笔数(笔) |

接口使用
数据样例


---

### [322] 柜台流通式债券报价  ·  债券专题
(api: bc_otcqt | 输出字段: 13 | PIT字段: 否)

# (doc_id=322)  https://tushare.pro/document/2?doc_id=322

## 柜台流通式债券报价
接口：bc_otcqt 描述：柜台流通式债券报价 限量：单次最大2000条，可多次提取，总量不限制 积分：用户需要至少500积分可以试用调取，2000积分以上频次相对较高，积分越多权限越大，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | N | 交易日期(YYYYMMDD格式，下同) |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |
| ts_code | str | N | TS代码 |
| bank | str | N | 报价机构 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | N | 报价日期 |
| qt_time | str | N | 报价时间 |
| bank | str | N | 报价机构 |
| ts_code | str | N | 债券编码 |
| name | str | N | 债券简称 |
| maturity | str | N | 期限 |
| remain_maturity | str | N | 剩余期限 |
| bond_type | str | N | 债券类型 |
| coupon_rate | float | N | 票面利率（%） |
| buy_price | float | N | 投资者买入全价 |
| sell_price | float | N | 投资者卖出全价 |
| buy_yield | float | N | 投资者买入到期收益率（%） |
| sell_yield | float | N | 投资者卖出到期收益率（%） |

接口示例
数据示例


---

### [323] 柜台流通式债券最优报价  ·  债券专题
(api: bc_bestotcqt | 输出字段: 11 | PIT字段: 否)

# (doc_id=323)  https://tushare.pro/document/2?doc_id=323

## 柜台流通式债券最优报价
接口：bc_bestotcqt 描述：柜台流通式债券最优报价 限量：单次最大2000，可多次提取，总量不限制 积分：用户需要至少500积分可以试用调取，2000积分以上频次相对较高，积分越多权限越大，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | N | 报价日期(YYYYMMDD格式，下同) |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |
| ts_code | str | N | TS代码 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | N | 报价日期 |
| ts_code | str | N | 债券编码 |
| name | str | N | 债券简称 |
| remain_maturity | str | N | 剩余期限 |
| bond_type | str | N | 债券类型 |
| best_buy_bank | str | N | 最优报买价方 |
| best_buy_yield | float | N | 投资者最优买入价到期收益率（%） |
| best_buy_price | float | N | 投资者最优买入全价 |
| best_sell_bank | str | N | 最优卖报价方 |
| best_sell_yield | float | N | 投资者最优卖出价到期收益率（%） |
| best_sell_price | float | N | 投资者最优卖出全价 |

接口示例
数据示例


---

### [271] 大宗交易  ·  债券专题
(api: bond_blk | 输出字段: 6 | PIT字段: 否)

# (doc_id=271)  https://tushare.pro/document/2?doc_id=271

## 债券大宗交易
接口：bond_blk 权限：用户满5000积分有数据权限，单次最大1000条，可根据日期循环提取，总量不限制 描述：获取沪深交易所债券大宗交易数据
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 债券代码 |
| trade_date | str | N | 交易日期（YYYYMMDD格式，下同） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 交易日期 |
| ts_code | str | Y | 债券代码 |
| name | str | Y | 债券名称 |
| price | float | Y | 成交价（元） |
| vol | float | Y | 累计成交数量（万股/万份/万张/万手） |
| amount | float | Y | 累计成交金额（万元） |

接口示例
数据样例


---

### [272] 大宗交易明细  ·  债券专题
(api: bond_blk_detail | 输出字段: 8 | PIT字段: 否)

# (doc_id=272)  https://tushare.pro/document/2?doc_id=272

## 大宗交易明细
接口：bond_blk_detail 权限：用户满5000积分有数据权限，单次最大1000条，可根据日期循环提取，总量不限制 描述：获取沪深交易所债券大宗交易数据
注：本接口目前只有深交所的大宗交易明细，上交所明细已经包含在大宗交易接口里，未单独罗列。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 债券代码 |
| trade_date | str | N | 交易日期（YYYYMMDD格式，下同） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 交易日期 |
| ts_code | str | Y | 债券代码 |
| name | str | Y | 债券名称 |
| price | float | Y | 成交价（元） |
| vol | float | Y | 成交数量（万股/万份/万张/万手） |
| amount | float | Y | 成交金额（万元） |
| buy_dp | str | Y | 买方营业部 |
| sell_dp | str | Y | 卖方营业部 |

接口示例
数据样例


---

### [201] 国债收益率曲线  ·  债券专题
(api: yc_cb | 输出字段: 6 | PIT字段: 否)

# (doc_id=201)  https://tushare.pro/document/2?doc_id=201

## 国债收益率曲线
接口：yc_cb 描述：获取中债收益率曲线，目前可获取中债国债收益率曲线即期和到期收益率曲线数据 限量：单次最大2000，总量不限制，可循环提取 权限：属于单独的权限接口，请在群里联系群主或管理员
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 收益率曲线编码：1001.CB-国债收益率曲线 |
| curve_type | str | N | 曲线类型：0-到期，1-即期 |
| trade_date | str | N | 交易日期 |
| start_date | str | N | 查询起始日期 |
| end_date | str | N | 查询结束日期 |
| curve_term | float | N | 期限 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 交易日期 |
| ts_code | str | Y | 曲线编码 |
| curve_name | str | Y | 曲线名称 |
| curve_type | str | Y | 曲线类型：0-到期，1-即期 |
| curve_term | float | Y | 期限(年) |
| yield | float | Y | 收益率(%) |

接口示例
数据示例


---

### [233] 全球财经事件  ·  债券专题
(api: eco_cal | 输出字段: 8 | PIT字段: 否)

# (doc_id=233)  https://tushare.pro/document/2?doc_id=233

## 财经日历
接口：eco_cal 描述：获取全球财经日历、包括经济事件数据更新 限量：单次最大获取100行数据 积分：2000积分可调取
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| date | str | N | 日期（YYYYMMDD格式） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |
| currency | str | N | 货币代码 |
| country | str | N | 国家（比如：中国、美国） |
| event | str | N | 事件 （支持模糊匹配： *非农*） |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| date | str | Y | 日期 |
| time | str | Y | 时间 |
| currency | str | Y | 货币代码 |
| country | str | Y | 国家 |
| event | str | Y | 经济事件 |
| value | str | Y | 今值 |
| pre_value | str | Y | 前值 |
| fore_value | str | Y | 预测值 |

接口示例
数据示例
美国非农数据：

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：eco_cal 描述：获取全球财经日历、包括经济事件数据更新 限量：单次最大获取100行数据 积分：2000积分可调取


---

### [177] 外汇数据  ·  (顶级)
(api: — | 输出字段: 0 | PIT字段: 否)

# (doc_id=177)  https://tushare.pro/document/2?doc_id=177

## Tushare外汇数据
1、在岸人民币 （上线中）
2、海外市场
| 交易商名称 | 交易所代码 | TS_CODE代码后缀 |
| --- | --- | --- |
| 福汇 | FXCM | .FXCM |

3、目前提供的数据列表
外汇基础信息（海外）
外汇日线行情


---

### [178] 外汇基础信息（海外）  ·  外汇数据
(api: fx_obasic | 输出字段: 12 | PIT字段: 否)

# (doc_id=178)  https://tushare.pro/document/2?doc_id=178

## 外汇基础信息（海外）
接口：fx_obasic 描述：获取海外外汇基础信息，目前只有FXCM交易商的数据 数量：单次可提取全部数据 积分：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| exchange | str | N | 交易商 |
| classify | str | N | 分类 |
| ts_code | str | N | TS代码 |

classify分类说明
| 序号 | 分类代码 | 分类名称 | 样例 |
| --- | --- | --- | --- |
| 1 | FX | 外汇货币对 | USDCNH（美元人民币对） |
| 2 | INDEX | 指数 | US30（美国道琼斯工业平均指数） |
| 3 | COMMODITY | 大宗商品 | SOYF（大豆） |
| 4 | METAL | 金属 | XAUUSD （黄金） |
| 5 | BUND | 国库债券 | Bund（长期欧元债券） |
| 6 | CRYPTO | - | BTCUSD |
| 7 | FX_BASKET | 外汇篮子 | USDOLLAR （美元指数） |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 外汇代码 |
| name | str | Y | 名称 |
| classify | str | Y | 分类 |
| exchange | str | Y | 交易商 |
| min_unit | float | Y | 最小交易单位 |
| max_unit | float | Y | 最大交易单位 |
| pip | float | Y | 点 |
| pip_cost | float | Y | 点值 |
| traget_spread | float | Y | 目标差价 |
| min_stop_distance | float | Y | 最小止损距离（点子） |
| trading_hours | str | Y | 交易时间 |
| break_time | str | Y | 休市时间 |

接口示例
数据示例


---

### [179] 外汇日线行情  ·  外汇数据
(api: fx_daily | 输出字段: 12 | PIT字段: 否)

# (doc_id=179)  https://tushare.pro/document/2?doc_id=179

## 外汇日线行情
接口：fx_daily 描述：获取外汇日线行情 限量：单次最大提取1000行记录，可多次提取，总量不限制 积分：用户需要至少2000积分才可以调取，但有流量控制，5000积分以上频次相对较高，积分越多权限越大，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | TS代码 |
| trade_date | str | N | 交易日期（GMT，日期是格林尼治时间，比北京时间晚一天） |
| start_date | str | N | 开始日期（GMT） |
| end_date | str | N | 结束日期（GMT） |
| exchange | str | N | 交易商，目前只有FXCM |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 外汇代码 |
| trade_date | str | Y | 交易日期 |
| bid_open | float | Y | 买入开盘价 |
| bid_close | float | Y | 买入收盘价 |
| bid_high | float | Y | 买入最高价 |
| bid_low | float | Y | 买入最低价 |
| ask_open | float | Y | 卖出开盘价 |
| ask_close | float | Y | 卖出收盘价 |
| ask_high | float | Y | 卖出最高价 |
| ask_low | float | Y | 卖出最低价 |
| tick_qty | int | Y | 报价笔数 |
| exchange | str | N | 交易商 |

接口示例
数据示例


---

### [190] 港股数据  ·  (顶级)
(api: — | 输出字段: 0 | PIT字段: 否)

# (doc_id=190)  https://tushare.pro/document/2?doc_id=190

## Tushare港股数据
目前提供的港股数据主要是如下列表，数据还在不断规划和开发中，我们会尽快上线发布，为用户尽可能多的提供稳定和高质量数据
港股列表
港股日线行情


---

### [191] 港股基础信息  ·  港股数据
(api: hk_basic | 输出字段: 12 | PIT字段: 否)

# (doc_id=191)  https://tushare.pro/document/2?doc_id=191

## 港股列表
接口：hk_basic 描述：获取港股列表信息 数量：单次可提取全部在交易的港股列表数据 积分：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | TS代码 |
| list_status | str | N | 上市状态 L上市 D退市 P暂停上市 ，默认L |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y |  |
| name | str | Y | 股票简称 |
| fullname | str | Y | 公司全称 |
| enname | str | Y | 英文名称 |
| cn_spell | str | Y | 拼音 |
| market | str | Y | 市场类别 |
| list_status | str | Y | 上市状态 |
| list_date | str | Y | 上市日期 |
| delist_date | str | Y | 退市日期 |
| trade_unit | float | Y | 交易单位 |
| isin | str | Y | ISIN代码 |
| curr_type | str | Y | 货币代码 |

接口示例
数据示例


---

### [250] 港股交易日历  ·  港股数据
(api: hk_tradecal | 输出字段: 3 | PIT字段: 否)

# (doc_id=250)  https://tushare.pro/document/2?doc_id=250

## 港股交易日历
接口：hk_tradecal 描述：获取交易日历 限量：单次最大2000 权限：用户积累2000积分才可调取
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |
| is_open | str | N | 是否交易 '0'休市 '1'交易 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| cal_date | str | Y | 日历日期 |
| is_open | int | Y | 是否交易 '0'休市 '1'交易 |
| pretrade_date | str | Y | 上一个交易日 |

接口示例
数据示例


---

### [192] 港股日线行情  ·  港股数据
(api: hk_daily | 输出字段: 11 | PIT字段: 否)

# (doc_id=192)  https://tushare.pro/document/2?doc_id=192

## 港股行情
接口：hk_daily，可以通过 数据工具 调试和查看数据。 描述：获取港股每日增量和历史行情，每日18点左右更新当日数据 限量：单次最大提取5000行记录，可多次提取，总量不限制 积分：本接口单独开权限，具体请参阅 权限说明
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码 |
| trade_date | str | N | 交易日期 |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| trade_date | str | Y | 交易日期 |
| open | float | Y | 开盘价 |
| high | float | Y | 最高价 |
| low | float | Y | 最低价 |
| close | float | Y | 收盘价 |
| pre_close | float | Y | 昨收价 |
| change | float | Y | 涨跌额 |
| pct_chg | float | Y | 涨跌幅(%) |
| vol | float | Y | 成交量(股) |
| amount | float | Y | 成交额(元) |

接口示例
数据示例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：hk_daily，可以通过 数据工具 调试和查看数据。 描述：获取港股每日增量和历史行情，每日18点左右更新当日数据 限量：单次最大提取5000行记录，可多次提取，总量不限制 积分：本接口单独开权限，具体请参阅 权限说明


---

### [339] 港股复权行情  ·  港股数据
(api: hk_daily_adj | 输出字段: 18 | PIT字段: 否)

# (doc_id=339)  https://tushare.pro/document/2?doc_id=339

## 港股复权行情
接口：hk_daily_adj，可以通过 数据工具 调试和查看数据。 描述：获取港股复权行情，提供股票股本、市值和成交及换手多个数据指标 限量：单次最大可以提取6000条数据，可循环获取全部，支持分页提取 要求：120积分可以试用查看数据，开通正式权限请参考 权限说明文档
注：港股复权逻辑是：价格 * 复权因子 = 复权价格，比如close * adj_factor = 前复权收盘价。复权因子历史数据可能除权等被刷新，请注意动态更新。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码（e.g. 00001.HK） |
| trade_date | str | N | 交易日期（YYYYMMDD） |
| start_date | str | N | 开始日期（YYYYMMDD） |
| end_date | str | N | 结束日期（YYYYMMDD） |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| trade_date | str | Y | 交易日期 |
| close | float | Y | 收盘价 |
| open | float | Y | 开盘价 |
| high | float | Y | 最高价 |
| low | float | Y | 最低价 |
| pre_close | float | Y | 昨收价 |
| change | float | Y | 涨跌额 |
| pct_change | float | Y | 涨跌幅 |
| vol | None | Y | 成交量 |
| amount | float | Y | 成交额 |
| vwap | float | Y | 平均价 |
| adj_factor | float | Y | 复权因子 |
| turnover_ratio | float | Y | 换手率(基于总股本) |
| free_share | None | Y | 流通股本 |
| total_share | None | Y | 总股本 |
| free_mv | float | Y | 流通市值 |
| total_mv | float | Y | 总市值 |

接口示例
数据示例

## [PIT / 更新口径 — 自动标记]
- (正文) 注：港股复权逻辑是：价格 * 复权因子 = 复权价格，比如close * adj_factor = 前复权收盘价。复权因子历史数据可能除权等被刷新，请注意动态更新。


---

### [401] 港股复权因子  ·  港股数据
(api: hk_adjfactor | 输出字段: 4 | PIT字段: 否)

# (doc_id=401)  https://tushare.pro/document/2?doc_id=401

## 港股复权因子
接口：hk_adjfactor 描述：获取港股每日复权因子数据，每天滚动刷新 限量：单次最大6000行数据，可以根据日期循环 权限：本接口是在开通港股日线权限后自动获取权限，权限请参考 权限说明文档
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码 |
| trade_date | str | N | 交易日期（格式：YYYYMMDD，下同） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| trade_date | str | Y | 交易日期 |
| cum_adjfactor | float | Y | 累计复权因子 |
| close_price | float | Y | 收盘价 |

接口示例
数据示例


---

### [304] 港股分钟行情  ·  港股数据
(api: hk_mins | 输出字段: 8 | PIT字段: 否)

# (doc_id=304)  https://tushare.pro/document/2?doc_id=304

## 港股分钟行情
接口：hk_mins 描述：港股分钟数据，支持1min/5min/15min/30min/60min行情，提供Python SDK和 http Restful API两种方式 限量：单次最大8000行数据，可以通过股票代码和日期循环获取 权限：120积分可以调取2次接口查看数据，正式权限请参阅 权限说明 。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码，e.g.00001.HK |
| freq | str | Y | 分钟频度（1min/5min/15min/30min/60min） |
| start_date | datetime | N | 开始日期 格式：2023-03-13 09:00:00 |
| end_date | datetime | N | 结束时间 格式：2023-03-13 19:00:00 |

freq参数说明
| freq | 说明 |
| --- | --- |
| 1min | 1分钟 |
| 5min | 5分钟 |
| 15min | 15分钟 |
| 30min | 30分钟 |
| 60min | 60分钟 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| trade_time | str | Y | 交易时间 |
| open | float | Y | 开盘价 |
| close | float | Y | 收盘价 |
| high | float | Y | 最高价 |
| low | float | Y | 最低价 |
| vol | int | Y | 成交量 |
| amount | float | Y | 成交金额 |

接口用法
数据样例


---

### [383] 港股实时日线  ·  港股数据
(api: rt_hk_k | 输出字段: 8 | PIT字段: 否)

# (doc_id=383)  https://tushare.pro/document/2?doc_id=383

## 港股实时日线
接口：rt_hk_k 描述：获取港股实时日k线行情，支持按股票代码及股票代码通配符一次性提取全部股票实时日k线行情 限量：单次最大可提取5000条数据 积分：本接口是单独开权限的数据，单独申请权限请参考 权限列表
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 支持通配符方式，e.g. 00001.HK、02*.HK |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| pre_close | float | Y | 昨收价 |
| close | float | Y | 收盘价 |
| high | float | Y | 最高价 |
| open | float | Y | 开盘价 |
| low | float | Y | 最低价 |
| vol | float | Y | 成交量（股） |
| amount | float | Y | 成交额(元) |

接口示例
数据示例


---

### [389] 港股利润表  ·  港股数据
(api: hk_income | 输出字段: 5 | PIT字段: 否)

# (doc_id=389)  https://tushare.pro/document/2?doc_id=389

## 港股利润表
接口：hk_income，可以通过 数据工具 调试和查看数据。 描述：获取港股上市公司财务利润表数据 权限：需单独开权限，具体权限信息请参考 权限列表 提示：当前接口按单只股票获取其历史数据，单次请求最大返回10000行数据，可循环提取
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| period | str | N | 报告期(格式：YYYYMMDD） |
| ind_name | str | N | 指标名（如：营业额） |
| start_date | str | N | 报告期开始日期（格式：YYYYMMDD） |
| end_date | str | N | 报告结束始日期（格式：YYYYMMDD） |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| end_date | str | Y | 报告期 |
| name | str | Y | 股票名称 |
| ind_name | str | Y | 财务科目名称 |
| ind_value | float | Y | 财务科目值 |

接口用法
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：hk_income，可以通过 数据工具 调试和查看数据。 描述：获取港股上市公司财务利润表数据 权限：需单独开权限，具体权限信息请参考 权限列表 提示：当前接口按单只股票获取其历史数据，单次请求最大返回10000行数据，可循环提取


---

### [390] 港股资产负债表  ·  港股数据
(api: hk_balancesheet | 输出字段: 5 | PIT字段: 否)

# (doc_id=390)  https://tushare.pro/document/2?doc_id=390

## 港股资产负债表
接口：hk_balancesheet，可以通过 数据工具 调试和查看数据。 描述：获取港股上市公司资产负债表 权限：需单独开权限，具体权限信息请参考 权限列表 提示：当前接口按单只股票获取其历史数据，单次请求最大返回10000行数据，可循环提取
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| period | str | N | 报告期(格式：YYYYMMDD） |
| ind_name | str | N | 指标名（如：应收帐款） |
| start_date | str | N | 报告期开始日期（格式：YYYYMMDD） |
| end_date | str | N | 报告结束始日期（格式：YYYYMMDD） |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| name | str | Y | 股票名称 |
| end_date | str | Y | 报告期 |
| ind_name | str | Y | 财务科目名称 |
| ind_value | float | Y | 财务科目值 |

接口用法
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：hk_balancesheet，可以通过 数据工具 调试和查看数据。 描述：获取港股上市公司资产负债表 权限：需单独开权限，具体权限信息请参考 权限列表 提示：当前接口按单只股票获取其历史数据，单次请求最大返回10000行数据，可循环提取


---

### [391] 港股现金流量表  ·  港股数据
(api: hk_cashflow | 输出字段: 5 | PIT字段: 否)

# (doc_id=391)  https://tushare.pro/document/2?doc_id=391

## 港股现金流量表
接口：hk_cashflow，可以通过 数据工具 调试和查看数据。 描述：获取港股上市公司现金流量表数据 权限：需单独开权限，具体权限信息请参考 权限列表 提示：当前接口按单只股票获取其历史数据，单次请求最大返回10000行数据，可循环提取
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| period | str | N | 报告期(格式：YYYYMMDD） |
| ind_name | str | N | 指标名（如：新增贷款） |
| start_date | str | N | 报告期开始日期（格式：YYYYMMDD） |
| end_date | str | N | 报告结束始日期（格式：YYYYMMDD） |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| end_date | str | Y | 报告期 |
| name | str | Y | 股票名称 |
| ind_name | str | Y | 财务科目名称 |
| ind_value | float | Y | 财务科目值 |

接口用法
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：hk_cashflow，可以通过 数据工具 调试和查看数据。 描述：获取港股上市公司现金流量表数据 权限：需单独开权限，具体权限信息请参考 权限列表 提示：当前接口按单只股票获取其历史数据，单次请求最大返回10000行数据，可循环提取


---

### [388] 港股财务指标数据  ·  港股数据
(api: hk_fina_indicator | 输出字段: 87 | PIT字段: 否)

# (doc_id=388)  https://tushare.pro/document/2?doc_id=388

## 港股财务指标数据
接口：hk_fina_indicator，可以通过 数据工具 调试和查看数据。 描述：获取港股上市公司财务指标数据，为避免服务器压力，现阶段每次请求最多返回200条记录，可通过设置日期多次请求获取更多数据。 权限：需单独开权限，具体权限信息请参考 权限列表 提示：当前接口按单只股票获取其历史数据，单次请求最大返回10000行数据，可循环提取
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| period | str | N | 报告期(格式：YYYYMMDD） |
| report_type | str | N | 报告期类型（Q1一季报Q2半年报Q3三季报Q4年报） |
| start_date | str | N | 报告期开始日期(格式：YYYYMMDD） |
| end_date | str | N | 报告结束日期(格式：YYYYMMDD） |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| name | str | Y | 股票名称 |
| end_date | str | Y | 报告期 |
| ind_type | str | Y | 报告类型,Q-按报告期(季度),Y-按年度 |
| report_type | str | Y | 报告期类型 |
| std_report_date | str | Y | 标准报告期 |
| per_netcash_operate | float | Y | 每股经营现金流(元) |
| per_oi | float | Y | 每股营业收入(元) |
| bps | float | Y | 每股净资产(元) |
| basic_eps | float | Y | 基本每股收益(元) |
| diluted_eps | float | Y | 稀释每股收益(元) |
| operate_income | float | Y | 营业总收入(元) |
| operate_income_yoy | float | Y | 营业总收入同比增长(%) |
| gross_profit | float | Y | 毛利润(元) |
| gross_profit_yoy | float | Y | 毛利润同比增长(%) |
| holder_profit | float | Y | 归母净利润(元) |
| holder_profit_yoy | float | Y | 归母净利润同比增长(%) |
| gross_profit_ratio | float | Y | 毛利率(%) |
| eps_ttm | float | Y | ttm每股收益(元) |
| operate_income_qoq | float | Y | 营业总收入滚动环比增长(%) |
| net_profit_ratio | float | Y | 净利率(%) |
| roe_avg | float | Y | 平均净资产收益率(%) |
| gross_profit_qoq | float | Y | 毛利润滚动环比增长(%) |
| roa | float | Y | 总资产净利率(%) |
| holder_profit_qoq | float | Y | 归母净利润滚动环比增长(%) |
| roe_yearly | float | Y | 年化净资产收益率(%) |
| roic_yearly | float | Y | 年化投资回报率(%) |
| total_assets | float | Y | 资产总额 |
| total_liabilities | float | Y | 负债总额 |
| tax_ebt | float | Y | 所得税/利润总额(%) |
| ocf_sales | float | Y | 经营现金流/营业收入(%) |
| total_parent_equity | float | Y | 本公司权益持有人应占权益 |
| debt_asset_ratio | float | Y | 资产负债率(%) |
| operate_profit | float | Y | 经营盈利 |
| pretax_profit | float | Y | 除税前盈利 |
| netcash_operate | float | Y | 经营活动所得现金流量净额 |
| netcash_invest | float | Y | 投资活动耗用现金流量净额 |
| netcash_finance | float | Y | 融资活动耗用现金流量净额 |
| end_cash | float | Y | 期末的现金及现金等价物 |
| divi_ratio | float | Y | 分红比例 |
| dividend_rate | float | Y | 股息率 |
| current_ratio | float | Y | 流动比率(倍) |
| common_acs | float | Y | 普通股应计股息 |
| currentdebt_debt | float | Y | 流动负债/总负债(%) |
| issued_common_shares | float | Y | 已发行普通股 |
| hk_common_shares | float | Y | 港股本( 不建议使用数据源有误 ) |
| per_shares | float | Y | 每手股数 |
| total_market_cap | float | Y | 总市值 |
| hksk_market_cap | float | Y | 港股市值 |
| pe_ttm | float | Y | 滚动市盈率 |
| pb_ttm | float | Y | 滚动市净率 |
| report_date_sq | str | Y | 季报日期 |
| report_type_sq | str | Y | 报告类型 |
| operate_income_sq | float | Y | 营业收入 |
| dps_hkd | float | Y | 每股股息（港元） |
| operate_income_qoq_sq | float | Y | 营业收入环比 |
| net_profit_ratio_sq | float | Y | 净利润率 |
| holder_profit_sq | float | Y | 归属于股东净利润 |
| holder_profit_qoq_sq | float | Y | 归母净利润环比 |
| roe_avg_sq | float | Y | 平均净资产收益率 |
| pe_ttm_sq | float | Y | 季报滚动市盈率 |
| pb_ttm_sq | float | Y | 季报滚动市净率 |
| roa_sq | float | Y | 总资产收益率 |
| start_date | float | Y | 会计年度起始日 |
| fiscal_year | float | Y | 会计年度截止日 |
| currency | str | Y | 币种 港元（hkd） |
| is_cny_code | float | Y | 是否人民币代码 |
| dps_hkd_ly | float | Y | 上一年每股股息 |
| org_type | str | Y | 企业类型 |
| premium_income | float | Y | 保费收入 |
| premium_income_yoy | float | Y | 保费收入同比 |
| net_interest_income | float | Y | 净利息收入 |
| net_interest_income_yoy | float | Y | 净利息收入同比 |
| fee_commission_income | float | Y | 手续费及佣金收入 |
| fee_commission_income_yoy | float | Y | 手续费及佣金收入同比 |
| accounts_rece_tdays | float | Y | 应收账款周转率(次) |
| inventory_tdays | float | Y | 存货周转率(次) |
| current_assets_tdays | float | Y | 流动资产周转率(次) |
| total_assets_tdays | float | Y | 总资产周转率(次) |
| premium_expense | float | Y | 保险赔付支出 |
| loan_deposit | float | Y | 贷款/存款 |
| loan_equity | float | Y | 贷款/股东权益 |
| loan_assets | float | Y | 贷款/总资产 |
| deposit_equity | float | Y | 存款/股东权益 |
| deposit_assets | float | Y | 存款/总资产 |
| equity_multiplier | float | Y | 权益乘数 |
| equity_ratio | float | Y | 产权比率 |

注：输出指标太多可在接口fields参数设定你需要的指标，例如：fields='ts_coe,bps,basic_eps'
接口用法
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：hk_fina_indicator，可以通过 数据工具 调试和查看数据。 描述：获取港股上市公司财务指标数据，为避免服务器压力，现阶段每次请求最多返回200条记录，可通过设置日期多次请求获取更多数据。 权限：需单独开权限，具体权限信息请参考 权限列表 提示：当前接口按单只股票获取其历史数据，单次请求最大返回10000行数据，可循环提取


---

### [251] 美股数据  ·  (顶级)
(api: — | 输出字段: 0 | PIT字段: 否)

# (doc_id=251)  https://tushare.pro/document/2?doc_id=251

## 美股数据
1、提供美股基础数据
2、提供美股交易日历数据
3、提供美股历史行情数据（未复权）


---

### [252] 美股基础信息  ·  美股数据
(api: us_basic | 输出字段: 6 | PIT字段: 否)

# (doc_id=252)  https://tushare.pro/document/2?doc_id=252

## 美股列表
接口：us_basic 描述：获取美股列表信息 限量：单次最大6000，可分页提取 积分：120积分可以试用，5000积分有正式权限
输入参数
| 名称 | 类型 | 必选 | 描述 | 示例 |
| --- | --- | --- | --- | --- |
| ts_code | str | N | 股票代码 | AAPL（苹果） |
| classify | str | N | 股票分类 | ADR/GDR/EQ |
| offset | str | N | 开始行数 | 1：第一行 |
| limit | str | N | 每页最大行数 | 500：每页500行 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 美股代码 |
| name | str | Y | 中文名称 |
| enname | str | N | 英文名称 |
| classify | str | Y | 分类ADR/GDR/EQ |
| list_date | str | Y | 上市日期 |
| delist_date | str | Y | 退市日期 |

接口示例
数据示例


---

### [253] 美股交易日历  ·  美股数据
(api: us_tradecal | 输出字段: 3 | PIT字段: 否)

# (doc_id=253)  https://tushare.pro/document/2?doc_id=253

## 美股交易日历
接口：us_tradecal 描述：获取美股交易日历信息 限量：单次最大6000，可根据日期阶段获取
输入参数
| 名称 | 类型 | 必选 | 描述 | 示例 |
| --- | --- | --- | --- | --- |
| start_date | str | N | 开始日期 | 20200101 |
| end_date | str | N | 结束日期 | 20200701 |
| is_open | str | N | 是否交易 | 0：休市 、1：交易 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| cal_date | str | Y | 日历日期 |
| is_open | int | Y | 是否交易 '0'休市 '1'交易 |
| pretrade_date | str | Y | 上一个交易日 |

接口示例
数据示例


---

### [254] 美股日线行情  ·  美股数据
(api: us_daily | 输出字段: 16 | PIT字段: 否)

# (doc_id=254)  https://tushare.pro/document/2?doc_id=254

## 美股行情
接口：us_daily 描述：获取美股行情（未复权），包括全部股票全历史行情，以及重要的市场和估值指标 限量：单次最大6000行数据，可根据日期参数循环提取，开通正式权限后也可支持分页提取全部历史 要求：120积分可以试用查看数据，开通正式权限请参考 权限说明文档 。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码（e.g. AAPL） |
| trade_date | str | N | 交易日期（YYYYMMDD） |
| start_date | str | N | 开始日期（YYYYMMDD） |
| end_date | str | N | 结束日期（YYYYMMDD） |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| trade_date | str | Y | 交易日期 |
| close | float | Y | 收盘价 |
| open | float | Y | 开盘价 |
| high | float | Y | 最高价 |
| low | float | Y | 最低价 |
| pre_close | float | Y | 昨收价 |
| change | float | N | 涨跌额 |
| pct_change | float | Y | 涨跌幅 |
| vol | float | Y | 成交量 |
| amount | float | Y | 成交额 |
| vwap | float | Y | 平均价 |
| turnover_ratio | float | N | 换手率 |
| total_mv | float | N | 总市值 |
| pe | float | N | PE |
| pb | float | N | PB |

接口示例
数据示例


---

### [338] 美股复权行情  ·  美股数据
(api: us_daily_adj | 输出字段: 19 | PIT字段: 否)

# (doc_id=338)  https://tushare.pro/document/2?doc_id=338

## 美股复权行情
接口：us_daily_adj，可以通过 数据工具 调试和查看数据。 描述：获取美股复权行情，支持美股全市场股票，提供股本、市值、复权因子和成交信息等多个数据指标 限量：单次最大可以提取8000条数据，可循环获取全部，支持分页提取 要求：120积分可以试用查看数据，开通正式权限请参考 权限说明文档
注：美股复权逻辑是：价格 * 复权因子 = 复权价格，比如close * adj_factor = 前复权收盘价。复权因子历史数据可能除权等被刷新，请注意动态更新。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码（e.g. AAPL） |
| trade_date | str | N | 交易日期（YYYYMMDD） |
| start_date | str | N | 开始日期（YYYYMMDD） |
| end_date | str | N | 结束日期（YYYYMMDD） |
| exchange | str | N | 交易所（NAS/NYS/OTC) |
| offset | int | N | 开始行数 |
| limit | int | N | 每页行数行数 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| trade_date | str | Y | 交易日期 |
| close | float | Y | 收盘价 |
| open | float | Y | 开盘价 |
| high | float | Y | 最高价 |
| low | float | Y | 最低价 |
| pre_close | float | Y | 昨收价 |
| change | float | Y | 涨跌额 |
| pct_change | float | Y | 涨跌幅 |
| vol | int | Y | 成交量 |
| amount | float | Y | 成交额 |
| vwap | float | Y | 平均价 |
| adj_factor | float | Y | 复权因子 |
| turnover_ratio | float | Y | 换手率 |
| free_share | int | Y | 流通股本 |
| total_share | int | Y | 总股本 |
| free_mv | float | Y | 流通市值 |
| total_mv | float | Y | 总市值 |
| exchange | str | Y | 交易所代码 |

接口示例
数据示例

## [PIT / 更新口径 — 自动标记]
- (正文) 注：美股复权逻辑是：价格 * 复权因子 = 复权价格，比如close * adj_factor = 前复权收盘价。复权因子历史数据可能除权等被刷新，请注意动态更新。


---

### [402] 美股复权因子  ·  美股数据
(api: us_adjfactor | 输出字段: 5 | PIT字段: 否)

# (doc_id=402)  https://tushare.pro/document/2?doc_id=402

## 美股复权因子
接口：us_adjfactor 描述：获取美股每日复权因子数据，在每天美股收盘后滚动刷新 限量：单次最大15000行数据，可以根据日期循环 权限：本接口是在开通美股日线权限后自动获取权限，权限请参考 权限说明文档
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码 |
| trade_date | str | N | 交易日期（格式：YYYYMMDD，下同） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| trade_date | str | Y | 交易日期 |
| exchange | str | Y | 交易所 |
| cum_adjfactor | float | Y | 累计复权因子 |
| close_price | float | Y | 收盘价 |

接口示例
数据示例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：us_adjfactor 描述：获取美股每日复权因子数据，在每天美股收盘后滚动刷新 限量：单次最大15000行数据，可以根据日期循环 权限：本接口是在开通美股日线权限后自动获取权限，权限请参考 权限说明文档


---

### [394] 美股利润表  ·  美股数据
(api: us_income | 输出字段: 7 | PIT字段: 否)

# (doc_id=394)  https://tushare.pro/document/2?doc_id=394

## 美股利润表
接口：us_income，可以通过 数据工具 调试和查看数据。 描述：获取美股上市公司财务利润表数据（目前只覆盖主要美股和中概股） 权限：需单独开权限，具体权限信息请参考 权限列表 提示：当前接口按单只股票获取其历史数据，单次请求最大返回10000行数据，可循环提取
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| period | str | N | 报告期（格式：YYYYMMDD，每个季度最后一天的日期，如20241231) |
| ind_name | str | N | 指标名(如：新增借款） |
| report_type | str | N | 报告期类型(Q1一季报Q2半年报Q3三季报Q4年报) |
| start_date | str | N | 报告期开始时间（格式：YYYYMMDD） |
| end_date | str | N | 报告结束始时间（格式：YYYYMMDD） |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| end_date | str | Y | 报告期 |
| ind_type | str | Y | 报告期类型(Q1一季报Q2半年报Q3三季报Q4年报) |
| name | str | Y | 股票名称 |
| ind_name | str | Y | 财务科目名称 |
| ind_value | float | Y | 财务科目值 |
| report_type | str | Y | 报告类型 |

接口用法
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：us_income，可以通过 数据工具 调试和查看数据。 描述：获取美股上市公司财务利润表数据（目前只覆盖主要美股和中概股） 权限：需单独开权限，具体权限信息请参考 权限列表 提示：当前接口按单只股票获取其历史数据，单次请求最大返回10000行数据，可循环提取


---

### [395] 美股资产负债表  ·  美股数据
(api: us_balancesheet | 输出字段: 7 | PIT字段: 否)

# (doc_id=395)  https://tushare.pro/document/2?doc_id=395

## 美股资产负债表
接口：us_balancesheet，可以通过 数据工具 调试和查看数据。 描述：获取美股上市公司资产负债表（目前只覆盖主要美股和中概股） 权限：需单独开权限，具体权限信息请参考 权限列表 提示：当前接口按单只股票获取其历史数据，单次请求最大返回10000行数据，可循环提取
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| period | str | N | 报告期（格式：YYYYMMDD，每个季度最后一天的日期，如20241231) |
| ind_name | str | N | 指标名(如：新增借款） |
| report_type | str | N | 报告期类型(Q1一季报Q2半年报Q3三季报Q4年报) |
| start_date | str | N | 报告期开始时间（格式：YYYYMMDD） |
| end_date | str | N | 报告结束始时间（格式：YYYYMMDD） |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| end_date | str | Y | 报告期 |
| ind_type | str | Y | 报告期类型(Q1一季报Q2半年报Q3三季报Q4年报) |
| name | str | Y | 股票名称 |
| ind_name | str | Y | 财务科目名称 |
| ind_value | float | Y | 财务科目值 |
| report_type | str | Y | 报告类型 |

接口用法
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：us_balancesheet，可以通过 数据工具 调试和查看数据。 描述：获取美股上市公司资产负债表（目前只覆盖主要美股和中概股） 权限：需单独开权限，具体权限信息请参考 权限列表 提示：当前接口按单只股票获取其历史数据，单次请求最大返回10000行数据，可循环提取


---

### [396] 美股现金流量表  ·  美股数据
(api: us_cashflow | 输出字段: 7 | PIT字段: 否)

# (doc_id=396)  https://tushare.pro/document/2?doc_id=396

## 美股现金流量表
接口：us_cashflow，可以通过 数据工具 调试和查看数据。 描述：获取美股上市公司现金流量表数据（目前只覆盖主要美股和中概股） 权限：需单独开权限，具体权限信息请参考 权限列表 提示：当前接口按单只股票获取其历史数据，单次请求最大返回10000行数据，可循环提取
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| period | str | N | 报告期（格式：YYYYMMDD，每个季度最后一天的日期，如20241231) |
| ind_name | str | N | 指标名(如：新增借款） |
| report_type | str | N | 报告期类型(Q1一季报Q2半年报Q3三季报Q4年报) |
| start_date | str | N | 报告期开始时间（格式：YYYYMMDD） |
| end_date | str | N | 报告结束始时间（格式：YYYYMMDD） |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| end_date | str | Y | 报告期 |
| ind_type | str | Y | 报告期类型(Q1一季报Q2半年报Q3三季报Q4年报) |
| name | str | Y | 股票名称 |
| ind_name | str | Y | 财务科目名称 |
| ind_value | float | Y | 财务科目值 |
| report_type | str | Y | 报告类型 |

接口用法
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：us_cashflow，可以通过 数据工具 调试和查看数据。 描述：获取美股上市公司现金流量表数据（目前只覆盖主要美股和中概股） 权限：需单独开权限，具体权限信息请参考 权限列表 提示：当前接口按单只股票获取其历史数据，单次请求最大返回10000行数据，可循环提取


---

### [393] 美股财务指标数据  ·  美股数据
(api: us_fina_indicator | 输出字段: 69 | PIT字段: 是)

# (doc_id=393)  https://tushare.pro/document/2?doc_id=393

## 美股财务指标数据
接口：us_fina_indicator，可以通过 数据工具 调试和查看数据。 描述：获取美股上市公司财务指标数据，目前只覆盖主要美股和中概股。为避免服务器压力，现阶段每次请求最多返回200条记录，可通过设置日期多次请求获取更多数据。 权限：需单独开权限，具体权限信息请参考 权限列表 提示：当前接口按单只股票获取其历史数据，单次请求最大返回10000行数据，可循环提取
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| period | str | N | 报告期（格式：YYYYMMDD，每个季度最后一天的日期，如20241231) |
| report_type | str | N | 报告期类型(Q1一季报Q2半年报Q3三季报Q4年报) |
| start_date | str | N | 报告期开始时间（格式：YYYYMMDD） |
| end_date | str | N | 报告结束始时间（格式：YYYYMMDD） |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| end_date | str | Y | 报告期 |
| ind_type | str | Y | 报告类型,Q1一季报,Q2中报,Q3三季报,Q4年报 |
| security_name_abbr | str | Y | 股票名称 |
| accounting_standards | str | Y | 会计准则 |
| notice_date | str | Y | 公告日期 |
| start_date | str | Y | 报告期开始时间 |
| std_report_date | str | Y | 标准报告期 |
| financial_date | str | Y | 年结日 |
| currency | str | Y | 币种 |
| date_type | str | Y | 报告期类型 |
| report_type | str | Y | 报告类型 |
| operate_income | float | Y | 收入 |
| operate_income_yoy | float | Y | 收入增长 |
| gross_profit | float | Y | 毛利 |
| gross_profit_yoy | float | Y | 毛利增长 |
| parent_holder_netprofit | float | Y | 归母净利润 |
| parent_holder_netprofit_yoy | float | Y | 归母净利润增长 |
| basic_eps | float | Y | 基本每股收益 |
| diluted_eps | float | Y | 稀释每股收益 |
| gross_profit_ratio | float | Y | 销售毛利率 |
| net_profit_ratio | float | Y | 销售净利率 |
| accounts_rece_tr | float | Y | 应收账款周转率(次) |
| inventory_tr | float | Y | 存货周转率(次) |
| total_assets_tr | float | Y | 总资产周转率(次) |
| accounts_rece_tdays | float | Y | 应收账款周转天数 |
| inventory_tdays | float | Y | 存货周转天数 |
| total_assets_tdays | float | Y | 总资产周转天数 |
| roe_avg | float | Y | 净资产收益率 |
| roa | float | Y | 总资产净利率 |
| current_ratio | float | Y | 流动比率(倍) |
| speed_ratio | float | Y | 速动比率(倍) |
| ocf_liqdebt | float | Y | 经营业务现金净额/流动负债 |
| debt_asset_ratio | float | Y | 资产负债率 |
| equity_ratio | float | Y | 产权比率 |
| basic_eps_yoy | float | Y | 基本每股收益同比增长 |
| gross_profit_ratio_yoy | float | Y | 毛利率同比增长(%) |
| net_profit_ratio_yoy | float | Y | 净利率同比增长(%) |
| roe_avg_yoy | float | Y | 平均净资产收益率同比增长(%) |
| roa_yoy | float | Y | 净资产收益率同比增长(%) |
| debt_asset_ratio_yoy | float | Y | 资产负债率同比增长(%) |
| current_ratio_yoy | float | Y | 流动比率同比增长(%) |
| speed_ratio_yoy | float | Y | 速动比率同比增长(%) |
| currency_abbr | str | Y | 币种 |
| total_income | float | Y | 收入总额 |
| total_income_yoy | float | Y | 收入总额同比增长 |
| premium_income | float | Y | 保费收入 |
| premium_income_yoy | float | Y | 保费收入同比 |
| basic_eps_cs | float | Y | 基本每股收益 |
| basic_eps_cs_yoy | float | Y | 基本每股收益同比增长 |
| diluted_eps_cs | float | Y | 稀释每股收益 |
| payout_ratio | float | Y | 保费收入/赔付支出 |
| capitial_ratio | float | Y | 总资产周转率 |
| roe | float | Y | 净资产收益率 |
| roe_yoy | float | Y | 净资产收益率同比增长 |
| debt_ratio | float | Y | 资产负债率 |
| debt_ratio_yoy | float | Y | 资产负债率同比增长 |
| net_interest_income | float | Y | 净利息收入 |
| net_interest_income_yoy | float | Y | 净利息收入增长 |
| diluted_eps_cs_yoy | float | Y | 稀释每股收益增长 |
| loan_loss_provision | float | Y | 贷款损失准备 |
| loan_loss_provision_yoy | float | Y | 贷款损失准备增长 |
| loan_deposit | float | Y | 贷款/存款 |
| loan_equity | float | Y | 贷款/股东权益(倍) |
| loan_assets | float | Y | 贷款/总资产 |
| deposit_equity | float | Y | 存款/股东权益(倍) |
| deposit_assets | float | Y | 存款/总资产 |
| rol | float | Y | 贷款回报率 |
| rod | float | Y | 存款回报率 |

注：输出指标太多可在接口fields参数设定你需要的指标，例如：fields='ts_coe,bps,basic_eps'
接口用法
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：us_fina_indicator，可以通过 数据工具 调试和查看数据。 描述：获取美股上市公司财务指标数据，目前只覆盖主要美股和中概股。为避免服务器压力，现阶段每次请求最多返回200条记录，可通过设置日期多次请求获取更多数据。 权限：需单独开权限，具体权限信息请参考 权限列表 提示：当前接口按单只股票获取其历史数据，单次请求最大返回10000行数据，可循环提取
- (字段) `notice_date` — str Y 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [147] 宏观经济  ·  (顶级)
(api: — | 输出字段: 0 | PIT字段: 否)

# (doc_id=147)  https://tushare.pro/document/2?doc_id=147

## 宏观经济数据
包括：
1、国内宏观
2、国际宏观


---

### [224] 国内宏观  ·  宏观经济
(api: — | 输出字段: 0 | PIT字段: 否)

# (doc_id=224)  https://tushare.pro/document/2?doc_id=224

## 国内宏观经济
1、利率数据
2、国民经济
3、价格指数
4、金融
5、景气度


---

### [461] 中国经济数据发布日程  ·  宏观经济 / 国内宏观
(api: cn_schedule | 输出字段: 5 | PIT字段: 否)

# (doc_id=461)  https://tushare.pro/document/2?doc_id=461

## 中国经济数据发布日程
## 接口介绍
接口：cn_schedule 描述：获取国家统计局、中国人民银行等经济数据发布日程及对应tushare接口，持续更新中 限量：单次最大3000条，可根据代码或日期循环提取 积分：需要2000积分可以调取，具体请参阅 积分获取办法
## 输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| m | str | N | 月份（YYYYMM） |
| title | str | N | 发布数据 |

## 输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| month | str | Y | 月份YYYYMM |
| publish_date | str | Y | 发布日期 |
| title | str | Y | 发布数据 |
| issuing_org | str | Y | 发布单位 |
| data_api | str | Y | tushare对应接口 |

## 代码示例
## 数据结果

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：cn_schedule 描述：获取国家统计局、中国人民银行等经济数据发布日程及对应tushare接口，持续更新中 限量：单次最大3000条，可根据代码或日期循环提取 积分：需要2000积分可以调取，具体请参阅 积分获取办法


---

### [148] 利率数据  ·  宏观经济 / 国内宏观
(api: — | 输出字段: 0 | PIT字段: 否)

# (doc_id=148)  https://tushare.pro/document/2?doc_id=148

## 利率数据
提供银行和政府公布的利率数据，日度更新。目前主要数据有：
Shibor利率
Shibor报价数据
LPR贷款基础利率
Libor利率
Hibor利率

## [PIT / 更新口径 — 自动标记]
- (正文) 提供银行和政府公布的利率数据，日度更新。目前主要数据有：


---

### [149] Shibor利率  ·  宏观经济 / 国内宏观 / 利率数据
(api: shibor | 输出字段: 9 | PIT字段: 否)

# (doc_id=149)  https://tushare.pro/document/2?doc_id=149

## Shibor利率数据
接口：shibor 描述：shibor利率 限量：单次最大2000，总量不限制，可通过设置开始和结束日期分段获取 积分：用户积累120积分可以调取，具体请参阅 积分获取办法
Shibor利率介绍
上海银行间同业拆放利率（Shanghai Interbank Offered Rate，简称Shibor），以位于上海的全国银行间同业拆借中心为技术平台计算、发布并命名，是由信用等级较高的银行组成报价团自主报出的人民币同业拆出利率计算确定的算术平均利率，是单利、无担保、批发性利率。目前，对社会公布的Shibor品种包括隔夜、1周、2周、1个月、3个月、6个月、9个月及1年。
Shibor报价银行团现由18家商业银行组成。报价银行是公开市场一级交易商或外汇市场做市商，在中国货币市场上人民币交易相对活跃、信息披露比较充分的银行。中国人民银行成立Shibor工作小组，依据《上海银行间同业拆放利率（Shibor）实施准则》确定和调整报价银行团成员、监督和管理Shibor运行、规范报价行与指定发布人行为。
全国银行间同业拆借中心受权Shibor的报价计算和信息发布。每个交易日根据各报价行的报价，剔除最高、最低各4家报价，对其余报价进行算术平均计算后，得出每一期限品种的Shibor，并于11:00对外发布。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| date | str | N | 日期 (日期输入格式：YYYYMMDD，下同) |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| date | str | Y | 日期 |
| on | float | Y | 隔夜 |
| 1w | float | Y | 1周 |
| 2w | float | Y | 2周 |
| 1m | float | Y | 1个月 |
| 3m | float | Y | 3个月 |
| 6m | float | Y | 6个月 |
| 9m | float | Y | 9个月 |
| 1y | float | Y | 1年 |

接口调用
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) Shibor报价银行团现由18家商业银行组成。报价银行是公开市场一级交易商或外汇市场做市商，在中国货币市场上人民币交易相对活跃、信息披露比较充分的银行。中国人民银行成立Shibor工作小组，依据《上海银行间同业拆放利率（Shibor）实施准则》确定和调整报价银行团成员、监督和管理Shibor运行、规范报价行与指定发布人行为。


---

### [150] Shibor报价数据  ·  宏观经济 / 国内宏观 / 利率数据
(api: shibor_quote | 输出字段: 18 | PIT字段: 否)

# (doc_id=150)  https://tushare.pro/document/2?doc_id=150

## Shibor报价数据
接口：shibor_quote 描述：Shibor报价数据 限量：单次最大4000行数据，总量不限制，可通过设置开始和结束日期分段获取 积分：用户积累120积分可以调取，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| date | str | N | 日期 (日期输入格式：YYYYMMDD，下同) |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |
| bank | str | N | 银行名称 （中文名称，例如 农业银行） |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| date | str | Y | 日期 |
| bank | str | Y | 报价银行 |
| on_b | float | Y | 隔夜_Bid |
| on_a | float | Y | 隔夜_Ask |
| 1w_b | float | Y | 1周_Bid |
| 1w_a | float | Y | 1周_Ask |
| 2w_b | float | Y | 2周_Bid |
| 2w_a | float | Y | 2周_Ask |
| 1m_b | float | Y | 1月_Bid |
| 1m_a | float | Y | 1月_Ask |
| 3m_b | float | Y | 3月_Bid |
| 3m_a | float | Y | 3月_Ask |
| 6m_b | float | Y | 6月_Bid |
| 6m_a | float | Y | 6月_Ask |
| 9m_b | float | Y | 9月_Bid |
| 9m_a | float | Y | 9月_Ask |
| 1y_b | float | Y | 1年_Bid |
| 1y_a | float | Y | 1年_Ask |

接口调用
数据样例


---

### [151] LPR贷款基础利率  ·  宏观经济 / 国内宏观 / 利率数据
(api: shibor_lpr | 输出字段: 3 | PIT字段: 否)

# (doc_id=151)  https://tushare.pro/document/2?doc_id=151

## LPR贷款基础利率
接口：shibor_lpr 描述：LPR贷款基础利率 限量：单次最大4000(相当于单次可提取18年历史)，总量不限制，可通过设置开始和结束日期分段获取 积分：用户积累120积分可以调取，具体请参阅 积分获取办法
LPR介绍
贷款基础利率（Loan Prime Rate，简称LPR），是基于报价行自主报出的最优贷款利率计算并发布的贷款市场参考利率。目前，对社会公布1年期贷款基础利率。
LPR报价银行团现由10家商业银行组成。报价银行应符合财务硬约束条件和宏观审慎政策框架要求，系统重要性程度高、市场影响力大、综合实力强，已建立内部收益率曲线和内部转移定价机制，具有较强的自主定价能力，已制定本行贷款基础利率管理办法，以及有利于开展报价工作的其他条件。市场利率定价自律机制依据《贷款基础利率集中报价和发布规则》确定和调整报价行成员，监督和管理贷款基础利率运行，规范报价行与指定发布人行为。
全国银行间同业拆借中心受权贷款基础利率的报价计算和信息发布。每个交易日根据各报价行的报价，剔除最高、最低各1家报价，对其余报价进行加权平均计算后，得出贷款基础利率报价平均利率，并于11:30对外发布。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| date | str | N | 日期 (日期输入格式：YYYYMMDD，下同) |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| date | str | Y | 日期 |
| 1y | float | Y | 1年贷款利率 |
| 5y | float | Y | 5年贷款利率 |

接口调用
数据样例


---

### [152] Libor利率  ·  宏观经济 / 国内宏观 / 利率数据
(api: libor | 输出字段: 9 | PIT字段: 否)

# (doc_id=152)  https://tushare.pro/document/2?doc_id=152

## Libor拆借利率
接口：libor 描述：Libor拆借利率 限量：单次最大4000行数据，总量不限制，可通过设置开始和结束日期分段获取 积分：用户积累120积分可以调取，具体请参阅 积分获取办法
Libor（London Interbank Offered Rate ），即伦敦同业拆借利率，是指伦敦的第一流银行之间短期资金借贷的利率，是国际金融市场中大多数浮动利率的基础利率。作为银行从市场上筹集资金进行转贷的融资成本，贷款协议中议定的LIBOR通常是由几家指定的参考银行，在规定的时间（一般是伦敦时间上午11：00）报价的平均利率。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| date | str | N | 日期 (日期输入格式：YYYYMMDD，下同) |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |
| curr_type | str | N | 货币代码 (USD美元 EUR欧元 JPY日元 GBP英镑 CHF瑞郎，默认是USD) |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| date | str | Y | 日期 |
| curr_type | str | Y | 货币 |
| on | float | Y | 隔夜 |
| 1w | float | Y | 1周 |
| 1m | float | Y | 1个月 |
| 2m | float | Y | 2个月 |
| 3m | float | Y | 3个月 |
| 6m | float | Y | 6个月 |
| 12m | float | Y | 12个月 |

接口调用
数据样例


---

### [153] Hibor利率  ·  宏观经济 / 国内宏观 / 利率数据
(api: hibor | 输出字段: 9 | PIT字段: 否)

# (doc_id=153)  https://tushare.pro/document/2?doc_id=153

## Hibor利率
接口：hibor 描述：Hibor利率 限量：单次最大4000行数据，总量不限制，可通过设置开始和结束日期分段获取 积分：用户积累120积分可以调取，具体请参阅 积分获取办法
HIBOR (Hongkong InterBank Offered Rate)，是香港银行同行业拆借利率。指香港货币市场上，银行与银行之间的一年期以下的短期资金借贷利率，从伦敦同业拆借利率（LIBOR）变化出来的。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| date | str | N | 日期 (日期输入格式：YYYYMMDD，下同) |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| date | str | Y | 日期 |
| on | float | Y | 隔夜 |
| 1w | float | Y | 1周 |
| 2w | float | Y | 2周 |
| 1m | float | Y | 1个月 |
| 2m | float | Y | 2个月 |
| 3m | float | Y | 3个月 |
| 6m | float | Y | 6个月 |
| 12m | float | Y | 12个月 |

接口调用
数据样例


---

### [173] 温州民间借贷利率  ·  宏观经济 / 国内宏观 / 利率数据
(api: wz_index | 输出字段: 13 | PIT字段: 否)

# (doc_id=173)  https://tushare.pro/document/2?doc_id=173

## 温州民间借贷利率
接口：wz_index 描述：温州民间借贷利率，即温州指数 限量：不限量，一次可取全部指标全部历史数据 积分：用户需要积攒2000积分可调取，具体请参阅 积分获取办法 数据来源：温州指数网 注： 温州指数 ，即温州民间融资综合利率指数，该指数及时反映民间金融交易活跃度和交易价格。该指数样板数据主要采集于四个方面：由温州市设立的几百家企业测报点，把各自借入的民间资本利率通过各地方金融办不记名申报收集起来；对各小额贷款公司借出的利率进行加权平均；融资性担保公司如典当行在融资过程中的利率，由温州经信委和商务局负责测报；民间借贷服务中心的实时利率。这些利率进行加权平均，就得出了“温州指数”。它是温州民间融资利率的风向标。2012年12月7日，温州指数正式对外发布。
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| date | str | N | 日期 |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| date | str | Y | 日期 |
| comp_rate | float | Y | 温州民间融资综合利率指数 (%，下同) |
| center_rate | float | Y | 民间借贷服务中心利率 |
| micro_rate | float | Y | 小额贷款公司放款利率 |
| cm_rate | float | Y | 民间资本管理公司融资价格 |
| sdb_rate | float | Y | 社会直接借贷利率 |
| om_rate | float | Y | 其他市场主体利率 |
| aa_rate | float | Y | 农村互助会互助金费率 |
| m1_rate | float | Y | 温州地区民间借贷分期限利率（一月期） |
| m3_rate | float | Y | 温州地区民间借贷分期限利率（三月期） |
| m6_rate | float | Y | 温州地区民间借贷分期限利率（六月期） |
| m12_rate | float | Y | 温州地区民间借贷分期限利率（一年期） |
| long_rate | float | Y | 温州地区民间借贷分期限利率（长期） |

接口用法
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：wz_index 描述：温州民间借贷利率，即温州指数 限量：不限量，一次可取全部指标全部历史数据 积分：用户需要积攒2000积分可调取，具体请参阅 积分获取办法 数据来源：温州指数网 注： 温州指数 ，即温州民间融资综合利率指数，该指数及时反映民间金融交易活跃度和交易价格。该指数样板数据主要采集于四个方面：由温州市设立的几百家企业测报点，把各自借入的民间资本利率通过各地方金融办不记名申报收集起来；对各小额贷款公司借出的利率进行加权平均；融资性担保公司如典当行在融资过程中的利率，由温州经信委和商务局负责测报；民间借贷服务中心的实时利率。这些利率进行加权平均，就得出了“温州指数”。它是温州民间融资利率的风向标。2012年12月7日，温州指数正式对外发布。


---

### [174] 广州民间借贷利率  ·  宏观经济 / 国内宏观 / 利率数据
(api: gz_index | 输出字段: 7 | PIT字段: 否)

# (doc_id=174)  https://tushare.pro/document/2?doc_id=174

## 广州民间借贷利率
接口：gz_index 描述：广州民间借贷利率 限量：不限量，一次可取全部指标全部历史数据 积分：用户需要积攒2000积分可调取，具体请参阅 积分获取办法 数据来源：广州民间金融街
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| date | str | N | 日期 |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| date | str | Y | 日期 |
| d10_rate | float | Y | 小额贷市场平均利率（十天） （单位：%，下同） |
| m1_rate | float | Y | 小额贷市场平均利率（一月期） |
| m3_rate | float | Y | 小额贷市场平均利率（三月期） |
| m6_rate | float | Y | 小额贷市场平均利率（六月期） |
| m12_rate | float | Y | 小额贷市场平均利率（一年期） |
| long_rate | float | Y | 小额贷市场平均利率（长期） |

接口用法
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：gz_index 描述：广州民间借贷利率 限量：不限量，一次可取全部指标全部历史数据 积分：用户需要积攒2000积分可调取，具体请参阅 积分获取办法 数据来源：广州民间金融街


---

### [225] 国民经济  ·  宏观经济 / 国内宏观
(api: — | 输出字段: 0 | PIT字段: 否)

# (doc_id=225)  https://tushare.pro/document/2?doc_id=225

## 国民经济核算
提供国家统计局公布的国民经济核算数据。目前主要数据有：
国内生产总值（GDP）


---

### [227] 国内生产总值（GDP）  ·  宏观经济 / 国内宏观 / 国民经济
(api: cn_gdp | 输出字段: 9 | PIT字段: 否)

# (doc_id=227)  https://tushare.pro/document/2?doc_id=227

## GDP数据
接口：cn_gdp 描述：获取国民经济之GDP数据 限量：单次最大10000，一次可以提取全部数据 权限：用户积累600积分可以使用，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| q | str | N | 季度（2019Q1表示，2019年第一季度） |
| start_q | str | N | 开始季度 |
| end_q | str | N | 结束季度 |
| fields | str | N | 指定输出字段（e.g. fields='quarter,gdp,gdp_yoy'） |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| quarter | str | Y | 季度 |
| gdp | float | Y | GDP累计值（亿元） |
| gdp_yoy | float | Y | 当季同比增速（%） |
| pi | float | Y | 第一产业累计值（亿元） |
| pi_yoy | float | Y | 第一产业同比增速（%） |
| si | float | Y | 第二产业累计值（亿元） |
| si_yoy | float | Y | 第二产业同比增速（%） |
| ti | float | Y | 第三产业累计值（亿元） |
| ti_yoy | float | Y | 第三产业同比增速（%） |

接口调用
数据样例


---

### [226] 价格指数  ·  宏观经济 / 国内宏观
(api: — | 输出字段: 0 | PIT字段: 否)

# (doc_id=226)  https://tushare.pro/document/2?doc_id=226

## 价格指数
提供国家统计局公布的价格指数数据，月度度更新。目前主要数据有：
居民消费价格指数（CPI）
工业生产者出厂价格指数（PPI）

## [PIT / 更新口径 — 自动标记]
- (正文) 提供国家统计局公布的价格指数数据，月度度更新。目前主要数据有：


---

### [228] 居民消费价格指数（CPI）  ·  宏观经济 / 国内宏观 / 价格指数
(api: cn_cpi | 输出字段: 13 | PIT字段: 否)

# (doc_id=228)  https://tushare.pro/document/2?doc_id=228

## 居民消费价格指数
接口：cn_cpi 描述：获取CPI居民消费价格数据，包括全国、城市和农村的数据 限量：单次最大5000行，一次可以提取全部数据 权限：用户积累600积分可以使用，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| m | str | N | 月份（YYYYMM，下同），支持多个月份同时输入，逗号分隔 |
| start_m | str | N | 开始月份 |
| end_m | str | N | 结束月份 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| month | str | Y | 月份YYYYMM |
| nt_val | float | Y | 全国当月值 |
| nt_yoy | float | Y | 全国同比（%） |
| nt_mom | float | Y | 全国环比（%） |
| nt_accu | float | Y | 全国累计值 |
| town_val | float | Y | 城市当月值 |
| town_yoy | float | Y | 城市同比（%） |
| town_mom | float | Y | 城市环比（%） |
| town_accu | float | Y | 城市累计值 |
| cnt_val | float | Y | 农村当月值 |
| cnt_yoy | float | Y | 农村同比（%） |
| cnt_mom | float | Y | 农村环比（%） |
| cnt_accu | float | Y | 农村累计值 |

接口调用
数据样例


---

### [245] 工业生产者出厂价格指数（PPI）  ·  宏观经济 / 国内宏观 / 价格指数
(api: cn_ppi | 输出字段: 31 | PIT字段: 否)

# (doc_id=245)  https://tushare.pro/document/2?doc_id=245

## 工业生产者出厂价格指数
接口：cn_ppi 描述：获取PPI工业生产者出厂价格指数数据 限量：单次最大5000，一次可以提取全部数据 权限：用户600积分可以使用，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| m | str | N | 月份（YYYYMM，下同），支持多个月份同时输入，逗号分隔 |
| start_m | str | N | 开始月份 |
| end_m | str | N | 结束月份 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| month | str | Y | 月份YYYYMM |
| ppi_yoy | float | Y | PPI：全部工业品：当月同比 |
| ppi_mp_yoy | float | Y | PPI：生产资料：当月同比 |
| ppi_mp_qm_yoy | float | Y | PPI：生产资料：采掘业：当月同比 |
| ppi_mp_rm_yoy | float | Y | PPI：生产资料：原料业：当月同比 |
| ppi_mp_p_yoy | float | Y | PPI：生产资料：加工业：当月同比 |
| ppi_cg_yoy | float | Y | PPI：生活资料：当月同比 |
| ppi_cg_f_yoy | float | Y | PPI：生活资料：食品类：当月同比 |
| ppi_cg_c_yoy | float | Y | PPI：生活资料：衣着类：当月同比 |
| ppi_cg_adu_yoy | float | Y | PPI：生活资料：一般日用品类：当月同比 |
| ppi_cg_dcg_yoy | float | Y | PPI：生活资料：耐用消费品类：当月同比 |
| ppi_mom | float | Y | PPI：全部工业品：环比 |
| ppi_mp_mom | float | Y | PPI：生产资料：环比 |
| ppi_mp_qm_mom | float | Y | PPI：生产资料：采掘业：环比 |
| ppi_mp_rm_mom | float | Y | PPI：生产资料：原料业：环比 |
| ppi_mp_p_mom | float | Y | PPI：生产资料：加工业：环比 |
| ppi_cg_mom | float | Y | PPI：生活资料：环比 |
| ppi_cg_f_mom | float | Y | PPI：生活资料：食品类：环比 |
| ppi_cg_c_mom | float | Y | PPI：生活资料：衣着类：环比 |
| ppi_cg_adu_mom | float | Y | PPI：生活资料：一般日用品类：环比 |
| ppi_cg_dcg_mom | float | Y | PPI：生活资料：耐用消费品类：环比 |
| ppi_accu | float | Y | PPI：全部工业品：累计同比 |
| ppi_mp_accu | float | Y | PPI：生产资料：累计同比 |
| ppi_mp_qm_accu | float | Y | PPI：生产资料：采掘业：累计同比 |
| ppi_mp_rm_accu | float | Y | PPI：生产资料：原料业：累计同比 |
| ppi_mp_p_accu | float | Y | PPI：生产资料：加工业：累计同比 |
| ppi_cg_accu | float | Y | PPI：生活资料：累计同比 |
| ppi_cg_f_accu | float | Y | PPI：生活资料：食品类：累计同比 |
| ppi_cg_c_accu | float | Y | PPI：生活资料：衣着类：累计同比 |
| ppi_cg_adu_accu | float | Y | PPI：生活资料：一般日用品类：累计同比 |
| ppi_cg_dcg_accu | float | Y | PPI：生活资料：耐用消费品类：累计同比 |

接口调用
数据样例


---

### [240] 金融  ·  宏观经济 / 国内宏观
(api: — | 输出字段: 0 | PIT字段: 否)

# (doc_id=240)  https://tushare.pro/document/2?doc_id=240


---

### [241] 货币供应量  ·  宏观经济 / 国内宏观 / 金融
(api: — | 输出字段: 0 | PIT字段: 否)

# (doc_id=241)  https://tushare.pro/document/2?doc_id=241


---

### [242] 货币供应量（月）  ·  宏观经济 / 国内宏观 / 金融 / 货币供应量
(api: cn_m | 输出字段: 10 | PIT字段: 否)

# (doc_id=242)  https://tushare.pro/document/2?doc_id=242

## 货币供应量
接口：cn_m 描述：获取货币供应量之月度数据 限量：单次最大5000，一次可以提取全部数据 权限：用户积累600积分可以使用，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| m | str | N | 月度（202001表示，2020年1月） |
| start_m | str | N | 开始月度 |
| end_m | str | N | 结束月度 |
| fields | str | N | 指定输出字段（e.g. fields='month,m0,m1,m2'） |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| month | str | Y | 月份YYYYMM |
| m0 | float | Y | M0（亿元） |
| m0_yoy | float | Y | M0同比（%） |
| m0_mom | float | Y | M0环比（%） |
| m1 | float | Y | M1（亿元） |
| m1_yoy | float | Y | M1同比（%） |
| m1_mom | float | Y | M1环比（%） |
| m2 | float | Y | M2（亿元） |
| m2_yoy | float | Y | M2同比（%） |
| m2_mom | float | Y | M2环比（%） |

接口调用
数据样例


---

### [309] 社会融资  ·  宏观经济 / 国内宏观 / 金融
(api: — | 输出字段: 0 | PIT字段: 否)

# (doc_id=309)  https://tushare.pro/document/2?doc_id=309


---

### [310] 社融增量（月度）  ·  宏观经济 / 国内宏观 / 金融 / 社会融资
(api: sf_month | 输出字段: 4 | PIT字段: 否)

# (doc_id=310)  https://tushare.pro/document/2?doc_id=310

## 社融数据（月度）
接口：sf_month 描述：获取月度社会融资数据 限量：单次最大2000条数据，可循环提取 积分：需2000积分
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| m | str | N | 月份（YYYYMM，下同），支持多个月份同时输入，逗号分隔 |
| start_m | str | N | 开始月份 |
| end_m | str | N | 结束月份 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| month | str | Y | 月度 |
| inc_month | float | Y | 社融增量当月值（亿元） |
| inc_cumval | float | Y | 社融增量累计值（亿元） |
| stk_endval | float | Y | 社融存量期末值（万亿元） |

接口调用
数据样例


---

### [324] 景气度  ·  宏观经济 / 国内宏观
(api: — | 输出字段: 0 | PIT字段: 否)

# (doc_id=324)  https://tushare.pro/document/2?doc_id=324


---

### [325] 采购经理指数（PMI）  ·  宏观经济 / 国内宏观 / 景气度
(api: cn_pmi | 输出字段: 60 | PIT字段: 否)

# (doc_id=325)  https://tushare.pro/document/2?doc_id=325

## 采购经理人指数
接口：cn_pmi 描述：采购经理人指数 限量：单次最大2000，一次可以提取全部数据 权限：用户积累2000积分可以使用，具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| m | str | N | 月度（202401表示，2024年1月） |
| start_m | str | N | 开始月度 |
| end_m | str | N | 结束月度（e.g. fields='month,pmi010000,pmi010400'） |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| month | str | N | 月份YYYYMM |
| pmi010000 | float | N | 制造业PMI |
| pmi010100 | float | N | 制造业PMI:企业规模/大型企业 |
| pmi010200 | float | N | 制造业PMI:企业规模/中型企业 |
| pmi010300 | float | N | 制造业PMI:企业规模/小型企业 |
| pmi010400 | float | N | 制造业PMI:构成指数/生产指数 |
| pmi010401 | float | N | 制造业PMI:构成指数/生产指数:企业规模/大型企业 |
| pmi010402 | float | N | 制造业PMI:构成指数/生产指数:企业规模/中型企业 |
| pmi010403 | float | N | 制造业PMI:构成指数/生产指数:企业规模/小型企业 |
| pmi010500 | float | N | 制造业PMI:构成指数/新订单指数 |
| pmi010501 | float | N | 制造业PMI:构成指数/新订单指数:企业规模/大型企业 |
| pmi010502 | float | N | 制造业PMI:构成指数/新订单指数:企业规模/中型企业 |
| pmi010503 | float | N | 制造业PMI:构成指数/新订单指数:企业规模/小型企业 |
| pmi010600 | float | N | 制造业PMI:构成指数/供应商配送时间指数 |
| pmi010601 | float | N | 制造业PMI:构成指数/供应商配送时间指数:企业规模/大型企业 |
| pmi010602 | float | N | 制造业PMI:构成指数/供应商配送时间指数:企业规模/中型企业 |
| pmi010603 | float | N | 制造业PMI:构成指数/供应商配送时间指数:企业规模/小型企业 |
| pmi010700 | float | N | 制造业PMI:构成指数/原材料库存指数 |
| pmi010701 | float | N | 制造业PMI:构成指数/原材料库存指数:企业规模/大型企业 |
| pmi010702 | float | N | 制造业PMI:构成指数/原材料库存指数:企业规模/中型企业 |
| pmi010703 | float | N | 制造业PMI:构成指数/原材料库存指数:企业规模/小型企业 |
| pmi010800 | float | N | 制造业PMI:构成指数/从业人员指数 |
| pmi010801 | float | N | 制造业PMI:构成指数/从业人员指数:企业规模/大型企业 |
| pmi010802 | float | N | 制造业PMI:构成指数/从业人员指数:企业规模/中型企业 |
| pmi010803 | float | N | 制造业PMI:构成指数/从业人员指数:企业规模/小型企业 |
| pmi010900 | float | N | 制造业PMI:其他/新出口订单 |
| pmi011000 | float | N | 制造业PMI:其他/进口 |
| pmi011100 | float | N | 制造业PMI:其他/采购量 |
| pmi011200 | float | N | 制造业PMI:其他/主要原材料购进价格 |
| pmi011300 | float | N | 制造业PMI:其他/出厂价格 |
| pmi011400 | float | N | 制造业PMI:其他/产成品库存 |
| pmi011500 | float | N | 制造业PMI:其他/在手订单 |
| pmi011600 | float | N | 制造业PMI:其他/生产经营活动预期 |
| pmi011700 | float | N | 制造业PMI:分行业/装备制造业 |
| pmi011800 | float | N | 制造业PMI:分行业/高技术制造业 |
| pmi011900 | float | N | 制造业PMI:分行业/基础原材料制造业 |
| pmi012000 | float | N | 制造业PMI:分行业/消费品制造业 |
| pmi020100 | float | N | 非制造业PMI:商务活动 |
| pmi020101 | float | N | 非制造业PMI:商务活动:分行业/建筑业 |
| pmi020102 | float | N | 非制造业PMI:商务活动:分行业/服务业业 |
| pmi020200 | float | N | 非制造业PMI:新订单指数 |
| pmi020201 | float | N | 非制造业PMI:新订单指数:分行业/建筑业 |
| pmi020202 | float | N | 非制造业PMI:新订单指数:分行业/服务业 |
| pmi020300 | float | N | 非制造业PMI:投入品价格指数 |
| pmi020301 | float | N | 非制造业PMI:投入品价格指数:分行业/建筑业 |
| pmi020302 | float | N | 非制造业PMI:投入品价格指数:分行业/服务业 |
| pmi020400 | float | N | 非制造业PMI:销售价格指数 |
| pmi020401 | float | N | 非制造业PMI:销售价格指数:分行业/建筑业 |
| pmi020402 | float | N | 非制造业PMI:销售价格指数:分行业/服务业 |
| pmi020500 | float | N | 非制造业PMI:从业人员指数 |
| pmi020501 | float | N | 非制造业PMI:从业人员指数:分行业/建筑业 |
| pmi020502 | float | N | 非制造业PMI:从业人员指数:分行业/服务业 |
| pmi020600 | float | N | 非制造业PMI:业务活动预期指数 |
| pmi020601 | float | N | 非制造业PMI:业务活动预期指数:分行业/建筑业 |
| pmi020602 | float | N | 非制造业PMI:业务活动预期指数:分行业/服务业 |
| pmi020700 | float | N | 非制造业PMI:新出口订单 |
| pmi020800 | float | N | 非制造业PMI:在手订单 |
| pmi020900 | float | N | 非制造业PMI:存货 |
| pmi021000 | float | N | 非制造业PMI:供应商配送时间 |
| pmi030000 | float | N | 中国综合PMI:产出指数 |

接口调用
数据样例


---

### [217] 国际宏观  ·  宏观经济
(api: — | 输出字段: 0 | PIT字段: 否)

# (doc_id=217)  https://tushare.pro/document/2?doc_id=217

## 国际宏观经济数据
上线中....


---

### [218] 美国利率  ·  宏观经济 / 国际宏观
(api: — | 输出字段: 0 | PIT字段: 否)

# (doc_id=218)  https://tushare.pro/document/2?doc_id=218

## 美国利率统计数据
数据上线中，请查看本节点下的数据类目。


---

### [219] 国债收益率曲线利率  ·  宏观经济 / 国际宏观 / 美国利率
(api: us_tycr | 输出字段: 14 | PIT字段: 否)

# (doc_id=219)  https://tushare.pro/document/2?doc_id=219

## 国债收益率曲线利率（日频）
接口：us_tycr 描述：获取美国每日国债收益率曲线利率 限量：单次最大可获取2000条数据 权限：用户积累120积分可以使用，积分越高频次越高。具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| date | str | N | 日期 （YYYYMMDD格式，下同） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |
| fields | str | N | 指定输出字段（e.g. fields='m1,y1'） |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| date | str | Y | 日期 |
| m1 | float | Y | 1月期 |
| m2 | float | Y | 2月期 |
| m3 | float | Y | 3月期 |
| m4 | float | Y | 4月期（数据从20221019开始） |
| m6 | float | Y | 6月期 |
| y1 | float | Y | 1年期 |
| y2 | float | Y | 2年期 |
| y3 | float | Y | 3年期 |
| y5 | float | Y | 5年期 |
| y7 | float | Y | 7年期 |
| y10 | float | Y | 10年期 |
| y20 | float | Y | 20年期 |
| y30 | float | Y | 30年期 |

接口调用
数据样例


---

### [220] 国债实际收益率曲线利率  ·  宏观经济 / 国际宏观 / 美国利率
(api: us_trycr | 输出字段: 6 | PIT字段: 否)

# (doc_id=220)  https://tushare.pro/document/2?doc_id=220

## 国债实际收益率曲线利率
接口：us_trycr 描述：国债实际收益率曲线利率 限量：单次最大可获取2000行数据，可循环获取 权限：用户积累120积分可以使用，积分越高频次越高。具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| date | str | N | 日期 （YYYYMMDD格式，下同） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |
| fields | str | N | 指定输出字段 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| date | str | Y | 日期 |
| y5 | float | Y | 5年期 |
| y7 | float | Y | 7年期 |
| y10 | float | Y | 10年期 |
| y20 | float | Y | 20年期 |
| y30 | float | Y | 30年期 |

接口调用
数据样例


---

### [221] 短期国债利率  ·  宏观经济 / 国际宏观 / 美国利率
(api: us_tbr | 输出字段: 13 | PIT字段: 否)

# (doc_id=221)  https://tushare.pro/document/2?doc_id=221

## 短期国债利率
接口：us_tbr 描述：获取美国短期国债利率数据 限量：单次最大可获取2000行数据，可循环获取 权限：用户积累120积分可以使用，积分越高频次越高。具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| date | str | N | 日期 |
| start_date | str | N | 开始日期(YYYYMMDD格式) |
| end_date | str | N | 结束日期 |
| fields | str | N | 指定输出字段(e.g. fields='w4_bd,w52_ce') |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| date | str | Y | 日期 |
| w4_bd | float | Y | 4周银行折现收益率 |
| w4_ce | float | Y | 4周票面利率 |
| w8_bd | float | Y | 8周银行折现收益率 |
| w8_ce | float | Y | 8周票面利率 |
| w13_bd | float | Y | 13周银行折现收益率 |
| w13_ce | float | Y | 13周票面利率 |
| w17_bd | float | Y | 17周银行折现收益率（数据从20221019开始） |
| w17_ce | float | Y | 17周票面利率（数据从20221019开始） |
| w26_bd | float | Y | 26周银行折现收益率 |
| w26_ce | float | Y | 26周票面利率 |
| w52_bd | float | Y | 52周银行折现收益率 |
| w52_ce | float | Y | 52周票面利率 |

接口调用
数据样例


---

### [222] 国债长期利率  ·  宏观经济 / 国际宏观 / 美国利率
(api: us_tltr | 输出字段: 4 | PIT字段: 否)

# (doc_id=222)  https://tushare.pro/document/2?doc_id=222

## 国债长期利率
接口：us_tltr 描述：国债长期利率 限量：单次最大可获取2000行数据，可循环获取 权限：用户积累120积分可以使用，积分越高频次越高。具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| date | str | N | 日期 |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |
| fields | str | N | 指定字段 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| date | str | Y | 日期 |
| ltc | float | Y | 收益率 LT COMPOSITE (>10 Yrs) |
| cmt | float | Y | 20年期CMT利率(TREASURY 20-Yr CMT) |
| e_factor | float | Y | 外推因子EXTRAPOLATION FACTOR |

接口调用
数据样例


---

### [223] 国债长期利率平均值  ·  宏观经济 / 国际宏观 / 美国利率
(api: us_trltr | 输出字段: 2 | PIT字段: 否)

# (doc_id=223)  https://tushare.pro/document/2?doc_id=223

## 国债实际长期利率平均值
接口：us_trltr 描述：国债实际长期利率平均值 限量：单次最大可获取2000行数据，可循环获取 权限：用户积累120积分可以使用，积分越高频次越高。具体请参阅 积分获取办法
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| date | str | N | 日期 |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |
| fields | str | N | 指定字段 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| date | str | Y | 日期 |
| ltr_avg | float | Y | 实际平均利率LT Real Average (10> Yrs) |

接口调用
数据样例


---

### [142] 大模型语料专题数据  ·  (顶级)
(api: — | 输出字段: 0 | PIT字段: 否)

# (doc_id=142)  https://tushare.pro/document/2?doc_id=142

## 特色大数据
Tushare Pro 将逐步开放互联网相关特色数据，为满足不同投资人群的特殊数据需求服务。目前暂时开放新闻快讯等数据，供大家研究使用。
新闻快讯
新闻通讯（长篇新闻）
新闻联播文字稿
公告原文
全球新冠疫情数据


---

### [406] 国家政策库  ·  大模型语料专题数据
(api: npr | 输出字段: 7 | PIT字段: 是)

# (doc_id=406)  https://tushare.pro/document/2?doc_id=406

## 国家政策法规库
## 接口介绍
为更好地学习和熟悉国家有关部门发布的政策法规和各类批复意见，同时为大语言模型提供更精准的语料和专业知识库，我们搜集整理了由国家有关部门 公开披露 的政策法规文件，所有文字均为原始输出，未作任何二次加工处理，同时提供原始出处。
接口：npr，（National Policy Repository） 描述：获取国家行政机关公开披露的各类法规、条例政策、批复、通知等文本数据。 限量：单次最大500条，可根据参数循环提取 积分：本接口需单独开权限（跟积分没关系），具体请参阅 权限说明
## 输入参数
| 名称 | 类型 | 必选 | 描述 | 可选内容 |
| --- | --- | --- | --- | --- |
| org | str | N | 发布机构 | 国务院办公厅/国务院办公厅/国务院、中央军委/国务院应急管理办公室 |
| start_date | datetime | N | 发布开始时间 | 格式样例：2024-11-21 00:00:00 |
| end_date | datetime | N | 发布结束时间 | 格式样例：2024-11-28 00:00:00 |
| ptype | str | N | 类型 | 对外经贸合作/农业、畜牧业、渔业/海关/城市规划/土地/科技/教育/卫生/民航 等110类 |

## 输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| pubtime | datetime | Y | 发布时间 |
| title | str | Y | 标题 |
| url | str | N | 政策文件url |
| content_html | str | N | 正文内容 |
| pcode | str | Y | 发文字号 |
| puborg | str | Y | 发文机关 |
| ptype | str | Y | 主题分类 |

## 代码示例
## 数据结果

## [PIT / 更新口径 — 自动标记]
- (正文) 为更好地学习和熟悉国家有关部门发布的政策法规和各类批复意见，同时为大语言模型提供更精准的语料和专业知识库，我们搜集整理了由国家有关部门 公开披露 的政策法规文件，所有文字均为原始输出，未作任何二次加工处理，同时提供原始出处。
- (正文) 接口：npr，（National Policy Repository） 描述：获取国家行政机关公开披露的各类法规、条例政策、批复、通知等文本数据。 限量：单次最大500条，可根据参数循环提取 积分：本接口需单独开权限（跟积分没关系），具体请参阅 权限说明
- (字段) `pubtime` — datetime Y 发布时间  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [415] 券商研究报告  ·  大模型语料专题数据
(api: research_report | 输出字段: 10 | PIT字段: 是)

# (doc_id=415)  https://tushare.pro/document/2?doc_id=415

## 券商研究报告
接口：research_report 描述：获取券商研究报告-个股、行业等，历史数据从20170101开始提供，增量每天两次更新 限量：单次最大1000条，可根据日期或券商名称代码循环提取，每天总量不限制 权限：本接口需单独开权限（跟积分没关系），具体请参阅 权限说明
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | N | 研报日期（格式：YYYYMMDD，下同） |
| start_date | str | N | 研报开始日期 |
| end_date | str | N | 研报结束日期 |
| report_type | str | N | 研报类别：个股研报/行业研报 |
| ts_code | str | N | 股票代码 |
| inst_csname | str | N | 券商名称 |
| ind_name | str | N | 行业名称 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| trade_date | str | Y | 研报发布时间 |
| abstr | str | Y | 研报摘要 |
| title | str | Y | 研报标题 |
| report_type | str | Y | 研报类别 |
| author | str | Y | 作者 |
| name | str | Y | 股票名称 |
| ts_code | str | Y | 股票代码 |
| inst_csname | str | Y | 机构简称 |
| ind_name | str | Y | 行业名称 |
| url | str | Y | 下载链接 |

接口用法
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：research_report 描述：获取券商研究报告-个股、行业等，历史数据从20170101开始提供，增量每天两次更新 限量：单次最大1000条，可根据日期或券商名称代码循环提取，每天总量不限制 权限：本接口需单独开权限（跟积分没关系），具体请参阅 权限说明
- (字段) `trade_date` — str Y 研报发布时间  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [465] 央行货币政策执行报告  ·  大模型语料专题数据
(api: monetary_policy | 输出字段: 5 | PIT字段: 是)

# (doc_id=465)  https://tushare.pro/document/2?doc_id=465

## 央行货币政策执行报告
## 接口介绍
接口：monetary_policy 描述：获取央行季度更新的货币政策执行报告，历史数据开始于2001年每年四篇，提供原始PDF下载链接，可用于分析过去20多年央行货币政策的动向、宏观以及金融市场的情况。 限量：单次最大1000条，一次可以拉取全部 积分：本接口为单独权限（跟积分没关系），具体请参阅 权限对应列表
## 输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| start_date | str | N | 发布开始日期（YYYYMMDD格式）示例:20260312 |
| end_date | str | N | 发布结束日期（YYYYMMDD格式）示例:20260312 |

## 输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| pub_date | str | Y | 发布日期 |
| title | str | Y | 标题 |
| url | str | Y | 原文链接 |
| pdf_url | str | Y | pdf链接 |
| content_html | str | Y | 带标签的正文内容 |

## 代码示例
## 数据结果

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：monetary_policy 描述：获取央行季度更新的货币政策执行报告，历史数据开始于2001年每年四篇，提供原始PDF下载链接，可用于分析过去20多年央行货币政策的动向、宏观以及金融市场的情况。 限量：单次最大1000条，一次可以拉取全部 积分：本接口为单独权限（跟积分没关系），具体请参阅 权限对应列表
- (字段) `pub_date` — str Y 发布日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [143] 新闻快讯（短讯）  ·  大模型语料专题数据
(api: news | 输出字段: 4 | PIT字段: 否)

# (doc_id=143)  https://tushare.pro/document/2?doc_id=143

## 新闻快讯
接口：news 描述：获取主流新闻网站的快讯新闻数据,提供超过6年以上历史新闻。 限量：单次最大1500条新闻，可根据时间参数循环提取历史 积分：本接口需单独开权限（跟积分没关系），具体请参阅 权限说明
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| start_date | datetime | Y | 开始日期(格式：2018-11-20 09:00:00） |
| end_date | datetime | Y | 结束日期 |
| src | str | Y | 新闻来源 见下表 |

数据源
| 来源名称 | src标识 | 描述 |
| --- | --- | --- |
| 新浪财经 | sina | 获取新浪财经实时资讯 |
| 华尔街见闻 | wallstreetcn | 华尔街见闻快讯 |
| 同花顺 | 10jqka | 同花顺财经新闻 |
| 东方财富 | eastmoney | 东方财富财经新闻 |
| 云财经 | yuncaijing | 云财经新闻 |
| 凤凰新闻 | fenghuang | 凤凰新闻 |
| 金融界 | jinrongjie | 金融界新闻 |
| 财联社 | cls | 财联社快讯 |
| 第一财经 | yicai | 第一财经快讯 |

时间参数格式例子：start_date='2018-11-20 09:00:00', end_date='2018-11-20 22:05:03'
输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| datetime | str | Y | 新闻时间 |
| content | str | Y | 内容 |
| title | str | Y | 标题 |
| channels | str | N | 分类 |

接口调用
数据样例
更多数据预览，请点击网站头部菜单的 资讯数据 。


---

### [195] 新闻通讯（长篇）  ·  大模型语料专题数据
(api: major_news | 输出字段: 4 | PIT字段: 是)

# (doc_id=195)  https://tushare.pro/document/2?doc_id=195

## 新闻通讯
接口：major_news 描述：获取长篇通讯信息，覆盖主要新闻资讯网站，提供超过8年历史新闻。 限量：单次最大400行记录，可循环提取保存到本地。 积分：本接口需单独开权限（跟积分没关系），具体请参阅 权限说明
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| src | str | N | 新闻来源（新华网、凤凰财经、同花顺、新浪财经、华尔街见闻、中证网、财新网、第一财经、财联社） |
| start_date | str | N | 新闻发布开始时间，e.g. 2018-11-21 00:00:00 |
| end_date | str | N | 新闻发布结束时间，e.g. 2018-11-22 00:00:00 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| title | str | Y | 标题 |
| content | str | N | 内容 (默认不显示，需要在fields里指定) |
| pub_time | str | Y | 发布时间 |
| src | str | Y | 来源网站 |

接口调用
数据样例

## [PIT / 更新口径 — 自动标记]
- (字段) `pub_time` — str Y 发布时间  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [154] 新闻联播文字稿  ·  大模型语料专题数据
(api: cctv_news | 输出字段: 3 | PIT字段: 否)

# (doc_id=154)  https://tushare.pro/document/2?doc_id=154

## 新闻联播
为了更加深入地学习贯彻我党的重要指示精神，利用新时代的新技术弘扬社会主义新价值观，特地整理了过去十年新闻联播的文字稿供大家研究、参考学习。希望大家领悟在心，实务在行，同时也别忘了抓住投资机会。
接口：cctv_news 描述：获取新闻联播文字稿数据，数据开始于2017年。 限量：可根据日期参数循环提取，总量不限制 积分：本接口需单独开权限（跟积分没关系），具体请参阅 权限说明
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| date | str | Y | 日期（输入格式：YYYYMMDD 比如：20181211） |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| date | str | Y | 日期 |
| title | str | Y | 标题 |
| content | str | Y | 内容 |

接口调用
数据样例
我们对新闻联播进行了分段处理，即每一个大段都加了标题处理，便于大家选择和过滤，也可以合成到一起进行分析。

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：cctv_news 描述：获取新闻联播文字稿数据，数据开始于2017年。 限量：可根据日期参数循环提取，总量不限制 积分：本接口需单独开权限（跟积分没关系），具体请参阅 权限说明


---

### [176] 上市公司公告  ·  大模型语料专题数据
(api: anns_d | 输出字段: 6 | PIT字段: 是)

# (doc_id=176)  https://tushare.pro/document/2?doc_id=176

## 上市公司全量公告
接口：anns_d 描述：获取全量公告数据，提供pdf下载URL 限量：单次最大2000条数，可以跟进日期循环获取全量 权限：本接口为单独权限，请参考 权限说明
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码 |
| ann_date | str | N | 公告日期（yyyymmdd格式，下同） |
| start_date | str | N | 公告开始日期 |
| end_date | str | N | 公告结束日期 |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ann_date | str | Y | 公告日期 |
| ts_code | str | Y | 股票代码 |
| name | str | Y | 股票名称 |
| title | str | Y | 标题 |
| url | str | Y | URL，原文下载链接 |
| rec_time | datetime | N | 发布时间 |

接口调用
数据样例

## [PIT / 更新口径 — 自动标记]
- (字段) `ann_date` — str N 公告日期（yyyymmdd格式，下同）  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `ann_date` — str Y 公告日期  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `rec_time` — datetime N 发布时间  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [366] 上证e互动问答  ·  大模型语料专题数据
(api: irm_qa_sh | 输出字段: 6 | PIT字段: 是)

# (doc_id=366)  https://tushare.pro/document/2?doc_id=366

## 上证E互动
接口：irm_qa_sh，历史数据开始于2023年6月。 描述：获取上交所e互动董秘问答文本数据。上证e互动是由上海证券交易所建立、上海证券市场所有参与主体无偿使用的沟通平台,旨在引导和促进上市公司、投资者等各市场参与主体之间的信息沟通,构建集中、便捷的互动渠道。本接口数据记录了以上沟通问答的文本数据。 限量：单次请求最大返回3000行数据，可根据股票代码，日期等参数循环提取全部数据 权限：需单独开权限，请参考 权限说明
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码 |
| trade_date | str | N | 交易日期（格式YYYYMMDD，下同） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |
| pub_date | str | N | 发布开始日期(格式：2025-06-03 16:43:03) |
| pub_date | str | N | 发布结束日期(格式：2025-06-03 18:43:23) |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| name | str | Y | 公司名称 |
| trade_date | str | Y | 日期 |
| q | str | Y | 问题 |
| a | str | Y | 回复 |
| pub_time | datetime | Y | 回复时间 |

接口调用
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：irm_qa_sh，历史数据开始于2023年6月。 描述：获取上交所e互动董秘问答文本数据。上证e互动是由上海证券交易所建立、上海证券市场所有参与主体无偿使用的沟通平台,旨在引导和促进上市公司、投资者等各市场参与主体之间的信息沟通,构建集中、便捷的互动渠道。本接口数据记录了以上沟通问答的文本数据。 限量：单次请求最大返回3000行数据，可根据股票代码，日期等参数循环提取全部数据 权限：需单独开权限，请参考 权限说明
- (字段) `pub_date` — str N 发布开始日期(格式：2025-06-03 16:43:03)  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `pub_date` — str N 发布结束日期(格式：2025-06-03 18:43:23)  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [367] 深证易互动问答  ·  大模型语料专题数据
(api: irm_qa_sz | 输出字段: 7 | PIT字段: 是)

# (doc_id=367)  https://tushare.pro/document/2?doc_id=367

## 深证互动易
接口：irm_qa_sz，历史数据开始于2010年10月。 描述：互动易是由深交所官方推出,供投资者与上市公司直接沟通的平台,一站式公司资讯汇集,提供第一手的互动问答、投资者关系信息、公司声音等内容。 限量：单次请求最大返回3000行数据，可根据股票代码，日期等参数循环提取全部数据 权限：需单独开权限，请参考 权限说明
输入参数
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | N | 股票代码 |
| trade_date | str | N | 交易日期（格式YYYYMMDD，下同） |
| start_date | str | N | 开始日期 |
| end_date | str | N | 结束日期 |
| pub_date | str | N | 发布开始日期(格式：2025-06-03 16:43:03) |
| pub_date | str | N | 发布结束日期(格式：2025-06-03 18:43:23) |

输出参数
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| name | str | Y | 公司名称 |
| trade_date | str | Y | 发布时间 |
| q | str | Y | 问题 |
| a | str | Y | 回复 |
| pub_time | str | Y | 答复时间 |
| industry | str | Y | 涉及行业 |

接口调用
数据样例

## [PIT / 更新口径 — 自动标记]
- (正文) 接口：irm_qa_sz，历史数据开始于2010年10月。 描述：互动易是由深交所官方推出,供投资者与上市公司直接沟通的平台,一站式公司资讯汇集,提供第一手的互动问答、投资者关系信息、公司声音等内容。 限量：单次请求最大返回3000行数据，可根据股票代码，日期等参数循环提取全部数据 权限：需单独开权限，请参考 权限说明
- (字段) `pub_date` — str N 发布开始日期(格式：2025-06-03 16:43:03)  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `pub_date` — str N 发布结束日期(格式：2025-06-03 18:43:23)  ← 名义日期≠可见日期的信号，PIT 须以此为锚
- (字段) `trade_date` — str Y 发布时间  ← 名义日期≠可见日期的信号，PIT 须以此为锚


---

### [209] 数据索引  ·  (顶级)
(api: — | 输出字段: 0 | PIT字段: 否)

# (doc_id=209)  https://tushare.pro/document/2?doc_id=209

## Tushare数据索引
股票基础
分钟行情 日线行情 周线行情 月线行情 复权行情 复权因子 每日涨跌停价格 每日涨跌停统计 停复牌 交易日历
总市值 流通市值 总股本 流通股本 自由流通股本 换手率 量比 股息率 市盈率（PE） 市净率 市销率 均线
上市公司基本信息 公司高管 管理层持股 新股发行 沪港通成分股 深港通成分股 历史曾用名
财务数据
利润表 资产负债表 现金流量表 业绩快报 业绩预告 主营业务构成 分红送股 财务审计报告 财报预披露日期表

## [PIT / 更新口径 — 自动标记]
- (正文) 利润表 资产负债表 现金流量表 业绩快报 业绩预告 主营业务构成 分红送股 财务审计报告 财报预披露日期表

