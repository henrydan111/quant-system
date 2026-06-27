# -*- coding: utf-8 -*-
"""Stage 3: build the human deliverables from the resolved data.

  indicator_mapping.md          - the mapping (token -> class/source/usage)
  indicator_reference_auto.md   - exact backbone: every indicator's formula +
                                  classified dependencies + full custom expansion
                                  chain; functions used; unique inline formulas;
                                  timing formulas. (definitions/prose added in the
                                  curated companion doc.)
"""
import json
import re
from collections import defaultdict
from pathlib import Path

BASE = Path(r"E:\量化系统\workspace\research\idea_sourcing\guorn")
usage = json.loads((BASE / "indicator_usage.json").read_text(encoding="utf-8"))
res = json.loads((BASE / "resolved_indicators.json").read_text(encoding="utf-8"))

NOISE = {"无"}
resolved = [r for r in res["resolved"] if r["base"] not in NOISE]

# ---------------- mapping doc ----------------
def fmt_strats(strats, k=6):
    s = strats[:k]
    extra = len(strats) - k
    return ", ".join(s) + (f" …(+{extra})" if extra > 0 else "")

m = []
m.append("# 果仁 slct 策略 — 指标映射表 (Stage 1)\n")
m.append("> 对 65 个策略的筛选/排名条件中出现的每个**命名指标**做来源映射。")
m.append("> 另有内联 `公式()` 表达式与大盘择时公式，见 [指标拆解backbone](indicator_reference_auto.md)。\n")
m.append(f"- 命名指标去重总数: **{len(resolved)}**")
m.append(f"  - 自定义指标 (在你的 452 导出库中): **{sum(1 for r in resolved if r['kind']=='custom')}**")
m.append(f"  - 内置指标 (帮助文档财务表中有公式): **{sum(1 for r in resolved if r['kind']=='builtin')}**")
m.append(f"  - 内置/行情/事件/朝阳永续 (文档表中无公式, 走prose或AI): **{sum(1 for r in resolved if r['kind']=='builtin_prose_or_field')}**")
m.append(f"- 内联 `公式()` 表达式: {res and ''}**{len(usage['inline_formulas'])}** 处 / 去重 **{len(set(x['expr'] for x in usage['inline_formulas']))}** 条")
m.append(f"- 大盘择时公式: **{len(usage['timing_formulas'])}** 条")
m.append("")
m.append("## 自定义指标 (映射到你的导出库)\n")
m.append("| 指标(策略中写法) | 用量 | 策略数 | 类型 | 公式(摘要) |")
m.append("|---|---|---|---|---|")
for r in sorted([r for r in resolved if r["kind"] == "custom"], key=lambda r: -r["count"]):
    expr = (r.get("expr") or "").replace("|", "\\|").replace("\n", " ")
    if len(expr) > 90:
        expr = expr[:90] + "…"
    m.append(f'| {r["base"]} | {r["count"]} | {r["n_strategies"]} | {r.get("custom_type","")} | `{expr}` |')
m.append("")
m.append("## 内置指标 — 帮助文档财务表中有公式\n")
m.append("| 指标 | 用量 | 公式 | 来源 |")
m.append("|---|---|---|---|")
for r in sorted([r for r in resolved if r["kind"] == "builtin"], key=lambda r: -r["count"]):
    expr = (r.get("expr") or "").replace("|", "\\|")
    m.append(f'| {r["base"]} | {r["count"]} | `{expr}` | {r.get("src","")} |')
m.append("")
m.append("## 内置/行情/事件/朝阳永续 — 需 prose 文档或 AI 助手确认\n")
m.append("| 指标 | 写法 | 用量 | 备注 |")
m.append("|---|---|---|---|")
NEEDS_AI = {
    "真实负债资产率","果仁风险预警25版","ILLIQ","中性EP","中性BP","中性SP","中性历史贝塔",
    "中性N日波动率","中性N日换手率","研发销售比率","市研率","市净率B","财报预约公布天数",
    "申万行业指数标记","评级调高家数","评级机构数","评级增持家数","分析师评级分","近期评级变化",
    "预期净利润1年","预期盈利增长率","预期盈利2年复合增长","预期营收2年复合增长","预期EP第2年",
    "预期BP1年","预期BP第2年","预期ROE1年","预期SP1年","行业净利润增长","行业净利润环比增长",
    "10日融资偿还金额","AH股溢价率","5日平均溢价率","溢价率","年内累计涨幅","股权质押比例",
    "管理层持股比例","净利润环比增长","营业收入环比增长","净利润断层",
}
for r in sorted([r for r in resolved if r["kind"] == "builtin_prose_or_field"], key=lambda r: -r["count"]):
    note = "★需AI确认" if r["base"] in NEEDS_AI else "行情/技术/事件 prose 文档可定义"
    m.append(f'| {r["base"]} | `{r["token"]}` | {r["count"]} | {note} |')
m.append("")
(BASE / "indicator_mapping.md").write_text("\n".join(m), encoding="utf-8")

# ---------------- reference backbone ----------------
def dep_line(r):
    bits = []
    if r.get("dep_funcs"): bits.append("函数: " + ", ".join(r["dep_funcs"]))
    if r.get("dep_customs"): bits.append("自定义依赖: " + ", ".join(r["dep_customs"]))
    if r.get("dep_builtins"): bits.append("内置依赖: " + ", ".join(r["dep_builtins"]))
    if r.get("dep_fields"): bits.append("字段/其它: " + ", ".join(r["dep_fields"]))
    return "  \n".join(bits)

d = []
d.append("# 果仁 slct 策略 — 指标计算逻辑拆解 (backbone, 自动生成)\n")
d.append("> 每个自定义指标给出: 原始公式 → 依赖分类(函数/自定义/内置/字段) → 全部传递依赖的自定义指标展开链。")
d.append("> 经济含义与函数/内置指标定义见同目录的人工分析companion。\n")

cust = sorted([r for r in resolved if r["kind"] == "custom"], key=lambda r: -r["count"])
d.append(f"## A. 自定义指标 ({len(cust)})\n")
for r in cust:
    d.append(f'### {r["base"]}  ·  用量 {r["count"]} / {r["n_strategies"]}策略')
    if r.get("unit"): d.append(f'- 显示单位: {r["unit"]}')
    if r.get("note"): d.append(f'- 作者说明: {r["note"]}')
    d.append(f'- **公式**: `{r.get("expr","")}`')
    dl = dep_line(r)
    if dl: d.append(dl)
    if r.get("expansion"):
        d.append(f'- 依赖的自定义指标展开 ({len(r["expansion"])}):')
        for e in r["expansion"]:
            d.append(f'    - `{e["name"]}` = `{e["expr"]}`')
    d.append("")

bt = sorted([r for r in resolved if r["kind"] == "builtin"], key=lambda r: -r["count"])
d.append(f"## B. 内置指标 (帮助文档有公式, {len(bt)})\n")
for r in bt:
    d.append(f'### {r["base"]}  ·  用量 {r["count"]}')
    d.append(f'- **公式**: `{r.get("expr","")}`  ({r.get("src","")})')
    if r.get("note"): d.append(f'- 备注: {r["note"]}')
    d.append("")

# unique inline formulas with classification
d.append("## C. 内联 公式() 表达式 (去重)\n")
seen = {}
for inl in usage["inline_formulas"]:
    seen.setdefault(inl["expr"], []).append(inl["strategy"])
for expr, strats in sorted(seen.items(), key=lambda kv: -len(kv[1])):
    d.append(f'- **`{expr}`**')
    d.append(f'    - 用于 {len(strats)} 策略: {fmt_strats(sorted(set(strats)),5)}')
d.append("")

d.append("## D. 大盘择时公式\n")
for tf in usage["timing_formulas"]:
    d.append(f'- **{tf["strategy"]}**: `{tf["line"]}`')
d.append("")

d.append("## E. 卖出 / 不卖条件 (去重)\n")
for sc in usage["sell_hold_conditions"]:
    d.append(f'- `{sc["text"]}`  — {"/".join(sc["kind"])}, {sc["count"]}策略')
d.append("")

(BASE / "indicator_reference_auto.md").write_text("\n".join(d), encoding="utf-8")
print("wrote indicator_mapping.md and indicator_reference_auto.md")
print("custom:", len(cust), " builtin-table:", len(bt),
      " builtin-prose/field:", sum(1 for r in resolved if r['kind']=='builtin_prose_or_field'))
print("unique inline formulas:", len(seen))
