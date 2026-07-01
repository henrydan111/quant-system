# -*- coding: utf-8 -*-
"""Stage 2: resolve every indicator used in the 65 guorn slct strategies.

For each used indicator attach:
  - classification: custom (in user export) / builtin (in help-doc tables) / field-or-prose / function
  - exact formula (custom export expr, or builtin help-doc formula)
  - dependency tree (recursively expand custom-indicator -> custom-indicator edges)

Emits:
  indicator_mapping.md       (the mapping the user asked for first)
  indicator_reference.md     (complete per-indicator breakdown w/ formulas + deps)
  resolved_indicators.json   (structured)
  unresolved_builtins.txt    (used builtins NOT in help-doc tables -> need prose/AI)
"""
import json
import re
from pathlib import Path

BASE = Path(r"E:\量化系统\workspace\research\idea_sourcing\guorn")
KDOC = Path(r"E:\量化系统\Knowledge\果仁帮助文档")
CUSTOM = Path(r"E:\量化系统\workspace\outputs\guorn_indicators\guorn_indicators_export.json")

usage = json.loads((BASE / "indicator_usage.json").read_text(encoding="utf-8"))
custom = json.loads(CUSTOM.read_text(encoding="utf-8"))

# ---------- custom index ----------
cust_map = {}          # lower(name) -> record
cust_display = {}      # lower(name) -> original name
for cat in custom["categories"]:
    for ind in cat["indicators"]:
        nm = ind["名称"]
        cust_map.setdefault(nm.lower(), {
            "name": nm, "category": cat["code"], "type": ind["类型"],
            "expr": ind["类型详情"], "unit": ind["显示单位"], "note": ind["说明"],
        })
        cust_display.setdefault(nm.lower(), nm)

# ---------- builtin financial tables ----------
builtin = {}   # lower(name) -> {name, formula, note, src}
def add_builtin(name, formula, note, src):
    name = name.strip()
    if name and name not in ("名称", "指标名称", "分类"):
        builtin.setdefault(name.lower(), {"name": name, "formula": formula.strip(), "note": note.strip(), "src": src})

def parse_fin_table(path, src):
    for line in path.read_text(encoding="utf-8").split("\n"):
        if "\t" not in line:
            continue
        parts = [p.strip() for p in line.split("\t")]
        parts = [p for p in parts if p != ""]
        if len(parts) >= 3:
            # name = parts[-3], formula = parts[-2], note = parts[-1]
            add_builtin(parts[-3], parts[-2], parts[-1], src)

parse_fin_table(KDOC / "财务指标公式.txt", "财务指标公式")
parse_fin_table(KDOC / "果仁选股指标详解.txt", "选股指标详解(财务表)")

# ---------- function names from 自定义函数列表 ----------
func_set = set()
fdoc = (KDOC / "自定义函数列表.txt").read_text(encoding="utf-8")
for line in fdoc.split("\n"):
    m = re.match(r"\s*([A-Za-z][A-Za-z0-9_]*)\s*[（(]", line)
    if m:
        func_set.add(m.group(1).lower())
# curated guarantee set (period / logic / common)
func_set |= {x.lower() for x in [
    "ref","barref","delta","ma","ema","sma","dma","wma","decayma","med","sum","product",
    "max","min","stdev","avedev","skewness","kurt","var","rank","percentile","percentrank",
    "zscore","corr","barcorr","covar","barcovar","forcast","slope","slopexy","interceptxy",
    "ssresid","rsquare","neutralize","havg","hmax","hmin","hmed","hwavg","hsum","hstdev",
    "hvar","hscale","hskewness","hkurt","hcorr","hcovar","hrank","hrankscore","hpercentrank",
    "hpercentile","hwinsorize","hstandarize","hneutralize","hneutralize2","hslopexy",
    "hinterceptxy","hneutralizemi","hdemean","hdemedian","smax","smin","savg","swavg","smed",
    "ssum","svar","sstdev","sskewness","skurt","scorr","srank","srankic","spercentile",
    "swinsorize","sstandarize","sscale","sneutralize","sneutralize2","sslopexy","sinterceptxy",
    "abs","log","ln","sqrt","round","mod","floor","power","exp","sigmoid","stdevm","square",
    "sign","sin","cos","tan","asin","acos","atan","greater","less","argmax","argmin","argmax2",
    "argmin2","lastvalue","lastvaluen","tickervalue","isnull","ifnull","null","if","and","or",
    "not","ttm","accuq","annual","refq","avgq","stdevq","kfirst","klast","kmax","kmin","ksum",
    "timing","countbars","barslast","crossover","count","hintercept","accru","accruq",
    "annualq","dayslast","winsorize","cs_rank","ma","iif",
]}

TOKEN_RE = re.compile(r"[A-Za-z0-9_一-鿿%]+")
def has_alpha(tok):
    return bool(re.search(r"[A-Za-z一-鿿]", tok))

PERIOD_MODS = {"单季","累计","年报","ttm","tTM"}

def tokens_of(expr):
    out = []
    for t in TOKEN_RE.findall(expr or ""):
        if not has_alpha(t):
            continue
        out.append(t)
    return out

def classify(tok):
    low = tok.lower()
    if low in func_set:
        return "func"
    if low in cust_map:
        return "custom"
    if low in builtin:
        return "builtin"
    if low in {m.lower() for m in PERIOD_MODS}:
        return "mod"
    return "field"   # raw financial field / 行情 prose indicator / unknown base

def base_name(token):
    m = re.match(r"^([^()（）]+)[（(](.*)[）)]$", token.strip())
    return m.group(1).strip() if m else token.strip()

# ---------- recursively expand a custom indicator ----------
def expand_custom(name_lower, seen):
    """Return ordered list of (name, record) for this custom and all transitive custom deps."""
    chain = []
    def rec(nl):
        if nl in seen:
            return
        seen.add(nl)
        rec_rec = cust_map.get(nl)
        if not rec_rec:
            return
        # find custom deps in its expr first (so deps listed before? we append self then deps)
        for t in tokens_of(rec_rec["expr"]):
            tl = t.lower()
            if tl in cust_map and tl not in seen:
                rec(tl)
        chain.append((cust_map[nl]["name"], cust_map[nl]))
    rec(name_lower)
    return chain

def dep_breakdown(expr):
    funcs, customs, builtins_, fields = set(), set(), set(), set()
    for t in tokens_of(expr):
        c = classify(t)
        if c == "func": funcs.add(t.lower())
        elif c == "custom": customs.add(cust_map[t.lower()]["name"])
        elif c == "builtin": builtins_.add(builtin[t.lower()]["name"])
        elif c == "field": fields.add(t)
    return sorted(funcs), sorted(customs), sorted(builtins_), sorted(fields)

# ---------- process used named tokens ----------
named = usage["named_tokens"]
resolved = []
unresolved_builtins = []
for r in named:
    token = r["token"]
    bn = base_name(token)
    cls = r["class"]
    rec = {"token": token, "base": bn, "count": r["count"], "n_strategies": r["n_strategies"]}
    if cls == "custom":
        cm = cust_map[(r["matched_custom"] or bn).lower()]
        rec["kind"] = "custom"
        rec["expr"] = cm["expr"]
        rec["unit"] = cm["unit"]
        rec["note"] = cm["note"]
        f, c, b, fl = dep_breakdown(cm["expr"])
        rec["dep_funcs"], rec["dep_customs"], rec["dep_builtins"], rec["dep_fields"] = f, c, b, fl
        chain = expand_custom(cm["name"].lower(), set())
        rec["expansion"] = [{"name": n, "expr": d["expr"]} for n, d in chain if n.lower() != cm["name"].lower()]
    else:
        # try builtin table by full token, then base
        hit = builtin.get(token.lower()) or builtin.get(bn.lower())
        if hit:
            rec["kind"] = "builtin"
            rec["expr"] = hit["formula"]
            rec["note"] = hit["note"]
            rec["src"] = hit["src"]
            f, c, b, fl = dep_breakdown(hit["formula"])
            rec["dep_funcs"], rec["dep_customs"], rec["dep_builtins"], rec["dep_fields"] = f, c, b, fl
        else:
            rec["kind"] = "builtin_prose_or_field"   # 行情/技术/事件 prose, N日 family, or raw field
            unresolved_builtins.append({"token": token, "base": bn, "count": r["count"]})
    resolved.append(rec)

# functions actually used anywhere (named exprs + inline + custom expansions)
used_funcs = set()
for r in resolved:
    used_funcs |= set(r.get("dep_funcs", []))
    for e in r.get("expansion", []):
        for t in tokens_of(e["expr"]):
            if t.lower() in func_set: used_funcs.add(t.lower())
for inl in usage["inline_formulas"]:
    for t in tokens_of(inl["expr"]):
        if t.lower() in func_set: used_funcs.add(t.lower())
for tf in usage["timing_formulas"]:
    for t in tokens_of(tf["line"]):
        if t.lower() in func_set: used_funcs.add(t.lower())

out = {
    "n_named": len(resolved),
    "n_custom": sum(1 for r in resolved if r["kind"] == "custom"),
    "n_builtin_table": sum(1 for r in resolved if r["kind"] == "builtin"),
    "n_builtin_prose_or_field": sum(1 for r in resolved if r["kind"] == "builtin_prose_or_field"),
    "used_functions": sorted(used_funcs),
    "resolved": resolved,
    "unresolved_builtins": unresolved_builtins,
}
(BASE / "resolved_indicators.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
(BASE / "unresolved_builtins.txt").write_text(
    "\n".join(f'{u["count"]:3d}x  {u["base"]}   (token: {u["token"]})' for u in
              sorted(unresolved_builtins, key=lambda x: -x["count"])), encoding="utf-8")

print("named tokens:", out["n_named"])
print("  custom:", out["n_custom"])
print("  builtin (table formula attached):", out["n_builtin_table"])
print("  builtin prose/field (need doc-prose or AI):", out["n_builtin_prose_or_field"])
print("functions used:", len(out["used_functions"]))
print("builtin financial defs loaded:", len(builtin))
print("custom defs loaded:", len(cust_map))
