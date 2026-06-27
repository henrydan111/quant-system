# -*- coding: utf-8 -*-
"""Extract the 85 unique inline 公式() expressions and classify their tokens
(function / custom-indicator / builtin / field) so each can be decomposed exactly.

Emits inline_formulas_classified.json + a readable dump to stdout-safe file.
"""
import json
import re
from pathlib import Path

BASE = Path(r"E:\量化系统\workspace\research\idea_sourcing\guorn")
KDOC = Path(r"E:\量化系统\Knowledge\果仁帮助文档")
CUSTOM = Path(r"E:\量化系统\workspace\outputs\guorn_indicators\guorn_indicators_export.json")

usage = json.loads((BASE / "indicator_usage.json").read_text(encoding="utf-8"))
custom = json.loads(CUSTOM.read_text(encoding="utf-8"))

cust_names = set()
for cat in custom["categories"]:
    for ind in cat["indicators"]:
        cust_names.add(ind["名称"].lower())

builtin_names = set()
def parse_fin_table(path):
    for line in path.read_text(encoding="utf-8").split("\n"):
        if "\t" in line:
            parts = [p.strip() for p in line.split("\t") if p.strip()]
            if len(parts) >= 3:
                builtin_names.add(parts[-3].lower())
parse_fin_table(KDOC / "财务指标公式.txt")
parse_fin_table(KDOC / "果仁选股指标详解.txt")

func_set = set()
for line in (KDOC / "自定义函数列表.txt").read_text(encoding="utf-8").split("\n"):
    m = re.match(r"\s*([A-Za-z][A-Za-z0-9_]*)\s*[（(]", line)
    if m:
        func_set.add(m.group(1).lower())
func_set |= {x.lower() for x in [
    "ref","barref","delta","ma","ema","sma","wma","decayma","med","sum","product","max","min",
    "stdev","avedev","skewness","kurt","var","rank","percentile","percentrank","zscore","corr",
    "slope","slopexy","interceptxy","rsquare","neutralize","havg","hmax","hmin","hmed","hwavg",
    "hsum","hstdev","hvar","hscale","hskewness","hkurt","hcorr","hrank","hrankscore","hpercentrank",
    "hpercentile","hwinsorize","hstandarize","hneutralize","hneutralize2","hslopexy","hinterceptxy",
    "hneutralizemi","hdemean","hdemedian","smax","smin","savg","swavg","smed","ssum","sstdev","srank",
    "srankic","sslopexy","sinterceptxy","abs","log","ln","sqrt","round","mod","floor","power","exp",
    "sigmoid","stdevm","square","sign","greater","less","argmax","argmin","lastvalue","lastvaluen",
    "tickervalue","ticker","isnull","ifnull","null","if","iif","and","or","not","ttm","accuq","accru",
    "annual","refq","avgq","stdevq","sumq","kfirst","klast","kmax","kmin","ksum","timing","countbars",
    "barslast","crossover","count","dayslast","mod","med",
]}

TOKEN_RE = re.compile(r"[A-Za-z0-9_一-鿿%]+")
def has_alpha(t):
    return bool(re.search(r"[A-Za-z一-鿿]", t))

def classify_tokens(expr):
    funcs, customs, builtins_, fields = [], [], [], []
    for t in TOKEN_RE.findall(expr):
        if not has_alpha(t):
            continue
        low = t.lower()
        if low in func_set:
            funcs.append(t)
        elif low in cust_names:
            customs.append(t)
        elif low in builtin_names:
            builtins_.append(t)
        else:
            fields.append(t)
    dedup = lambda xs: sorted(set(xs), key=lambda x: xs.index(x))
    return dedup(funcs), dedup(customs), dedup(builtins_), dedup(fields)

# dedupe inline formulas
agg = {}
for inl in usage["inline_formulas"]:
    e = inl["expr"]
    agg.setdefault(e, {"expr": e, "strategies": set(), "sections": set()})
    agg[e]["strategies"].add(inl["strategy"])
    agg[e]["sections"].add(inl["section"])

rows = []
for e, v in agg.items():
    f, c, b, fl = classify_tokens(e)
    rows.append({
        "expr": e,
        "count": len(v["strategies"]),
        "strategies": sorted(v["strategies"]),
        "sections": sorted(v["sections"]),
        "funcs": f, "customs": c, "builtins": b, "fields": fl,
        "len": len(e),
    })
rows.sort(key=lambda r: (-r["count"], r["expr"]))

(BASE / "inline_formulas_classified.json").write_text(
    json.dumps({"n_unique": len(rows), "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")

# readable dump for authoring
out = ["# 85 条内联公式 — 分类草稿\n"]
for i, r in enumerate(rows, 1):
    out.append(f"## [{i}] 用量{r['count']} | 段:{','.join(r['sections'])}")
    out.append(f"公式: {r['expr']}")
    if r['funcs']: out.append(f"  函数: {', '.join(r['funcs'])}")
    if r['customs']: out.append(f"  自定义: {', '.join(r['customs'])}")
    if r['builtins']: out.append(f"  内置: {', '.join(r['builtins'])}")
    if r['fields']: out.append(f"  字段/其它: {', '.join(r['fields'])}")
    out.append("")
(BASE / "_inline_scaffold.md").write_text("\n".join(out), encoding="utf-8")
print("unique inline formulas:", len(rows))
print("wrote inline_formulas_classified.json + _inline_scaffold.md")
