# Tushare 数据接口文档（document/2）离线归档

本目录是 <https://tushare.pro/document/2>（数据接口）的**离线镜像 + 结构化解析**，抓取于 **2026-06-08**（登录态 session）。

## 为什么有这个目录

report_rc（券商盈利预测）当初花了大力气才把 PIT 搞对，根因是**取数前没看 Tushare 对该接口字段口径的官方说明**。这个归档就是为了让"**取数前先读官方接口文档**"成为可执行流程——CLAUDE.md / AGENTS.md 已把它列为硬性规则。

## 目录结构

| 路径 | 内容 |
|---|---|
| **`INDEX.md`** | 汇总索引表：doc_id / api 名 / 中文名 / 分类 / 输出字段数 / **★PIT字段** / 正文文件名。**先查这里。** |
| `ALL_INTERFACES.md` | 全部 266 接口正文合集（一个文件里 Ctrl-F 搜全部） |
| `content/<doc_id>_<名称>.md` | 266 个接口逐个正文：接口名、积分/限量、**输入/输出参数表**、数据样例、PIT 自动标记 |
| `pages/doc_<id>.html` | 266 份原始 HTML（可离线重解析，无需再联网） |
| `目录树.txt` / `目录树.json` | 14 顶级分类 / 266 接口的层级目录树 |
| `index.json` | 结构化元数据（程序消费用） |
| `Tushare数据.html` | 原始菜单页存档 |

## 怎么用（取数前必做四步）

1. **定位**：在 [`INDEX.md`](INDEX.md) 按 api 名（如 `income`）或中文名（如 `利润表`）找到接口。
2. **读正文**：打开 `content/<doc_id>_<名称>.md`，看**输入/输出参数表**、**积分要求**、描述里的**更新时间 / 数据起始**。
3. **看 PIT ★ 标记**：若接口带 `create_time` / `ann_date` / `f_ann_date` / `pub_date` / `update_flag` 等"数据更新时间 / 公告日"字段，说明**名义日期 ≠ 数据可见日期** → PIT 必须以该字段为锚（参见 CLAUDE.md §3.2）。
4. **落档再取数**：把字段口径 + 更新节奏 + PIT 锚点记入 `data/data_dictionary.md` / approval evidence，**然后**才写 fetcher / 入 ledger（参见记忆 `feedback_factors_must_go_through_ledger_qlib`）。

## 关键统计

- **14 顶级分类 / 266 接口**；238 含正文，28 为分类节点（无字段表）。
- **46 个接口带 PIT-关键日期字段**（INDEX 里 ★ 行），按价值分组：
  - **财务报表/披露**：`income` `balancesheet` `cashflow` `forecast` `express` `fina_indicator` `fina_audit` `fina_mainbz` `dividend` `disclosure_date`（富含 `ann_date`/`f_ann_date`/`update_flag`）
  - **股东/参考**：`top10_holders` `top10_floatholders` `pledge_detail` `repurchase` `share_float` `stk_holdernumber` `stk_holdertrade` `stk_managers` `stk_rewards` `namechange`
  - **盈利预测/研报**：`report_rc`(create_time) `research_report`
  - **异动/公告**：`stk_shock` `stk_high_shock` `anns_d` `idx_anns`
  - **基金**：`fund_manager` `fund_nav` `fund_div` `fund_portfolio`
  - **可转债**：`cb_issue` `cb_call` `cb_price_chg` `cb_share` `cb_rating`
  - **语料/舆情**：`major_news` `npr` `monetary_policy` `irm_qa_sh` `irm_qa_sz`
  - 其它：`us_fina_indicator`(notice_date)、`ths_hot`/`dc_hot`(is_new)、期货历史Tick(UpdateTime)、`etf_index`(pub_date)
- 反之，**未★标记**的（行情/指数日线、涨跌停、复权因子等）多为当日盘中可知的执行字段、无披露滞后 → 作预测因子须 `Ref(...,1)`（CLAUDE.md §3.2）。

## 时效 & 覆盖

- 抓取于 **2026-06-08**，覆盖 document/2 全量。Tushare 会增改接口——**过期就用下方脚本重抓**。
- `document/41`（另类数据）当前后端返回 `服务异常，请稍后再试`，**未归档**（非权限/cookie 问题，是该路径的服务端错误）。

## 如何重建 / 更新

构建工具（在 `workspace/scripts/`）：

- [`parse_tushare_doc_tree.py`](../workspace/scripts/parse_tushare_doc_tree.py) — 从一份存页解析菜单树。
- [`parse_tushare_doc_content.py`](../workspace/scripts/parse_tushare_doc_content.py) — 单接口正文，`extract_content(html, doc_id)` → (markdown, meta)。
- [`fetch_all_tushare_doc2.py`](../workspace/scripts/fetch_all_tushare_doc2.py) — 批量抓取+解析，输出落到**本目录**。cookie 走环境变量、复用 `pages/` 缓存（可纯离线重解析）。

```bash
# 重抓/更新（需登录态 cookie；api.tushare.pro 的 data token 不认文档站）
export TUSHARE_DOC_COOKIE='uid=...; username=...; session-id=...'
venv/Scripts/python.exe workspace/scripts/fetch_all_tushare_doc2.py
# 仅离线重解析（pages/ 已缓存时，不联网）：同上命令即可，已存在的页会跳过抓取
```

取 cookie：登录 tushare.pro → F12 → Network → `document/2` 请求 → 复制 `Cookie:` 头。

**来源**：<https://tushare.pro/document/2>
