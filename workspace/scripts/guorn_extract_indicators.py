# -*- coding: utf-8 -*-
"""Stage 1: extract every indicator token used across the 65 guorn slct strategies
and map each to its source (custom indicator export / inline formula / unknown=likely built-in).

Outputs:
  workspace/research/idea_sourcing/guorn/indicator_usage.json   (full structured usage)
  workspace/research/idea_sourcing/guorn/indicator_mapping.md   (human-readable mapping)
"""
import json
import re
from collections import defaultdict
from pathlib import Path

BASE = Path(r"E:\量化系统\workspace\research\idea_sourcing\guorn")
STRAT = BASE / "guorn_slct_strategies.json"
CUSTOM = Path(r"E:\量化系统\workspace\outputs\guorn_indicators\guorn_indicators_export.json")

SECTION_HEADERS = ["投资域", "筛选条件", "排名条件", "交易模型",
                   "新股买入限制", "卖出条件", "不卖条件", "大盘择时"]

strategies = json.loads(STRAT.read_text(encoding="utf-8"))
custom = json.loads(CUSTOM.read_text(encoding="utf-8"))

# ---- build custom-indicator index: lowercased name -> record ----
cust_index = {}
for cat in custom["categories"]:
    for ind in cat["indicators"]:
        name = ind["名称"]
        rec = {
            "name": name,
            "category": cat["code"],
            "type": ind["类型"],
            "expr": ind["类型详情"],
            "unit": ind["显示单位"],
            "note": ind["说明"],
        }
        cust_index.setdefault(name.lower(), rec)  # keep first if dup

def parse_sections(defn):
    """Split a strategy definition into {section: [lines]}."""
    sections = defaultdict(list)
    cur = None
    for raw in defn.split("\n"):
        line = raw.rstrip()
        if not line.strip():
            continue
        head = line.strip().rstrip("：:")
        if head in SECTION_HEADERS and (line.strip().endswith("：") or line.strip().endswith(":") or line.strip() == head):
            cur = head
            # 大盘择时 may carry an inline formula on subsequent lines; keep capturing
            continue
        if cur:
            sections[cur].append(line)
    return sections

def base_name(token):
    """Strip a single trailing (...) parameter group for a NAMED indicator token.
    Leaves inline 公式(...) untouched (caller checks is_formula first)."""
    m = re.match(r"^([^()]+)\((.*)\)$", token.strip())
    if m:
        return m.group(1).strip()
    return token.strip()

# usage[token] = {count, strategies:set, sections:set}
usage = defaultdict(lambda: {"count": 0, "strategies": set(), "sections": set()})
inline_formulas = []   # (strategy, section, expr)
timing_formulas = []   # (strategy, formula)
sell_hold = defaultdict(lambda: {"count": 0, "strategies": set(), "kind": set()})

for s in strategies:
    name = s["name"]
    secs = parse_sections(s["definition"])
    for sec in ("筛选条件", "排名条件"):
        for line in secs.get(sec, []):
            token = line.split("\t")[0].strip()
            if not token:
                continue
            if token.startswith("公式(") or token.startswith("公式（"):
                inner = token[token.find("(")+1:]
                if inner.endswith(")"):
                    inner = inner[:-1]
                inline_formulas.append({"strategy": name, "section": sec, "expr": inner})
                continue
            u = usage[token]
            u["count"] += 1
            u["strategies"].add(name)
            u["sections"].add(sec)
    # sell / hold conditions
    for sec, kind in (("卖出条件", "sell"), ("不卖条件", "hold")):
        for line in secs.get(sec, []):
            t = line.strip()
            sh = sell_hold[t]
            sh["count"] += 1
            sh["strategies"].add(name)
            sh["kind"].add(kind)
    # market timing
    for line in secs.get("大盘择时", []):
        t = line.strip()
        if t in ("无",):
            continue
        timing_formulas.append({"strategy": name, "line": t})

# ---- classify each named token ----
def classify(token):
    bn = base_name(token)
    if token.lower() in cust_index:
        return "custom", token
    if bn.lower() in cust_index:
        return "custom", bn
    return "unknown", bn  # likely built-in (resolve via help docs in stage 2)

rows = []
for token, u in usage.items():
    kind, matched = classify(token)
    rec = cust_index.get(matched.lower()) if kind == "custom" else None
    rows.append({
        "token": token,
        "base": base_name(token),
        "class": kind,
        "matched_custom": matched if kind == "custom" else None,
        "count": u["count"],
        "n_strategies": len(u["strategies"]),
        "strategies": sorted(u["strategies"]),
        "custom_expr": rec["expr"] if rec else None,
        "custom_type": rec["type"] if rec else None,
    })

rows.sort(key=lambda r: (-r["count"], r["token"]))
n_custom = sum(1 for r in rows if r["class"] == "custom")
n_unknown = sum(1 for r in rows if r["class"] == "unknown")

out = {
    "n_strategies": len(strategies),
    "n_unique_named_tokens": len(rows),
    "n_custom_matched": n_custom,
    "n_unknown_builtin_or_other": n_unknown,
    "n_inline_formula_instances": len(inline_formulas),
    "n_timing_formula_instances": len(timing_formulas),
    "named_tokens": rows,
    "inline_formulas": inline_formulas,
    "timing_formulas": timing_formulas,
    "sell_hold_conditions": [
        {"text": k, "count": v["count"], "kind": sorted(v["kind"]), "n_strategies": len(v["strategies"])}
        for k, v in sorted(sell_hold.items(), key=lambda kv: -kv[1]["count"])
    ],
}
(BASE / "indicator_usage.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

print("strategies:", len(strategies))
print("unique named tokens:", len(rows))
print("  custom-matched:", n_custom)
print("  unknown (built-in/other):", n_unknown)
print("inline 公式() instances:", len(inline_formulas))
print("timing formula instances:", len(timing_formulas))
print("distinct sell/hold conditions:", len(sell_hold))
print()
print("== UNKNOWN (likely built-in) named tokens, by usage ==")
for r in rows:
    if r["class"] == "unknown":
        print(f'  {r["count"]:3d}x  {r["base"]}')
