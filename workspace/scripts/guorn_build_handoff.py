# -*- coding: utf-8 -*-
"""Consolidate the guorn idea-source into one handoff package for the strategy/book
layer session: joins each strategy's parsed recipe + indicators used + backtest
performance + detail-file paths into guorn_strategies_master.json, and emits a
quick-scan overview CSV. (HANDOFF.md is authored separately.)
"""
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

G = Path(r"E:\量化系统\workspace\research\idea_sourcing\guorn")
BT = Path(r"E:\量化系统\Knowledge\果仁回测结果")

strategies = json.loads((G / "guorn_slct_strategies.json").read_text(encoding="utf-8"))
order = json.loads((G / "bt_queue.json").read_text(encoding="utf-8"))           # canonical 65 order
usage = json.loads((G / "indicator_usage.json").read_text(encoding="utf-8"))
resolved = {r["token"]: r for r in json.loads((G / "resolved_indicators.json").read_text(encoding="utf-8"))["resolved"]}
defn = {s["name"]: s["definition"] for s in strategies}

# backtest metrics by strategy name
bt = {}
with open(G / "backtest_summary.csv", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        bt[row["策略"]] = row

# invert indicator usage -> per strategy
named_by_strat = defaultdict(list)
for tok in usage["named_tokens"]:
    for s in tok["strategies"]:
        named_by_strat[s].append(tok)
inline_by_strat = defaultdict(list)
for inl in usage["inline_formulas"]:
    inline_by_strat[inl["strategy"]].append(inl["expr"])

SECTIONS = ["投资域", "筛选条件", "排名条件", "交易模型", "新股买入限制", "卖出条件", "不卖条件", "大盘择时"]

def parse_sections(text):
    secs = defaultdict(list)
    cur = None
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        head = line.rstrip("：:")
        if head in SECTIONS and (line.endswith("：") or line.endswith(":") or line == head):
            cur = head
            continue
        if cur:
            secs[cur].append(line)
    return secs

def kv_block(lines):
    d = {}
    for ln in lines:
        m = re.match(r"^(.+?)[：:]\s*(.*)$", ln)
        if m:
            d[m.group(1).strip()] = m.group(2).strip()
    return d

def parse_rules(lines, kind):
    out = []
    for ln in lines:
        f = [x.strip() for x in ln.split("\t")]
        ind = f[0]
        if kind == "filter":
            out.append({"indicator": ind, "op": f[1] if len(f) > 1 else "",
                        "scope": f[2] if len(f) > 3 else "", "value": f[-1] if len(f) > 1 else ""})
        else:  # ranking
            out.append({"indicator": ind, "direction": f[1] if len(f) > 1 else "",
                        "scope": f[2] if len(f) > 2 else "", "weight": f[-1] if len(f) > 3 else ""})
    return out

def category(name):
    if name.startswith("index_"):
        return "场内基金/QDII"
    if name.startswith("MultiA"):
        return "多资产轮动(基金)"
    if "_BJ_" in name:
        return "北证(BJ)"
    if name.startswith(("Comp_", "comp_")):
        return "策略组件(component)"
    return "A股"

NN_OF = {n: i + 1 for i, n in enumerate(order)}

records = []
for name in order:
    nn = NN_OF[name]
    secs = parse_sections(defn[name])
    # indicators
    cust, built, other = [], [], []
    for tok in named_by_strat.get(name, []):
        if tok["base"] == "无":
            continue
        entry = {"token": tok["token"], "base": tok["base"]}
        if tok["class"] == "custom":
            entry["expr"] = (resolved.get(tok["token"], {}) or {}).get("expr") or tok.get("custom_expr")
            cust.append(entry)
        else:
            built.append(entry)
    b = bt.get(name, {})
    rec = {
        "nn": nn,
        "name": name,
        "category": category(name),
        "recipe": {
            "universe": kv_block(secs.get("投资域", [])),
            "filters": parse_rules(secs.get("筛选条件", []), "filter"),
            "rankings": parse_rules(secs.get("排名条件", []), "ranking"),
            "trade_model": kv_block(secs.get("交易模型", [])),
            "buy_limit": secs.get("新股买入限制", []),
            "sell_conditions": secs.get("卖出条件", []),
            "hold_keep_conditions": secs.get("不卖条件", []),
            "market_timing": " ".join(secs.get("大盘择时", [])) or "无",
        },
        "indicators_used": {
            "custom": cust,
            "builtin_or_field": [e["base"] for e in built],
            "inline_formulas": sorted(set(inline_by_strat.get(name, []))),
        },
        "backtest": {
            "total_return_pct": b.get("总收益%"), "annual_pct": b.get("年化收益%"),
            "sharpe": b.get("夏普"), "max_drawdown_pct": b.get("最大回撤%"),
            "volatility_pct": b.get("波动率%"), "info_ratio": b.get("信息比率"),
            "beta": b.get("Beta"), "alpha_pct": b.get("Alpha%"),
            "benchmark": b.get("基准"), "benchmark_annual_pct": b.get("基准年化%"),
            "excess_annual_pct": b.get("超额年化%"),
            "cost_note": "单边千分之三 (默认千分之二因平台缓存bug不可用)" if name == "sm_noc_纯市值正盈利_v4" else "各策略平台默认成本(单边千分之二或千分之五)",
            "period": "2014-01-02..2026-06-18", "return_basis": "总收益(含分红再投资)",
        },
        "files": {
            "backtest_xlsx": f"Knowledge/果仁回测结果/{nn:02d}_{re.sub(r'[\\/:*?\"<>|]','_',name)}.xlsx",
            "definition_in": "workspace/research/idea_sourcing/guorn/guorn_slct_strategies.json",
        },
        "definition_text": defn[name],
    }
    records.append(rec)

master = {
    "_meta": {
        "source": "guorn.com slct tab (account leodan)",
        "count": len(records),
        "backtest_period": "2014-01-02 .. 2026-06-18",
        "return_basis": "total return (dividends reinvested) — compare to local EventDriven, NOT Vectorized price return",
        "leverage": "unlevered 1x (all guorn books)",
        "detail_docs": {
            "strategy_definitions": "guorn_slct_strategies.md / .json",
            "indicator_mapping": "indicator_mapping.md",
            "indicator_formulas_deps": "indicator_reference_auto.md",
            "indicator_analysis": "指标拆解与分析.md",
            "inline_formulas_breakdown": "内联公式85条拆解.md",
            "builtin_defs_via_ai": "guorn_aichat_indicator_defs.md",
            "backtest_xlsx_dir": "Knowledge/果仁回测结果/ (65 files, 11 sheets each)",
            "backtest_summary": "backtest_summary.csv",
        },
        "caveats": [
            "交易成本不统一: 各策略用其平台保存的默认成本(单边千分之二或千分之五); 复刻须逐个核对",
            "sm_noc_纯市值正盈利_v4 用千分之三导出(默认千分之二因guorn缓存bug不可用)",
            "收益=总收益口径(含分红再投资)",
        ],
    },
    "strategies": records,
}
(G / "guorn_strategies_master.json").write_text(json.dumps(master, ensure_ascii=False, indent=2), encoding="utf-8")

# quick-scan overview CSV
cols = ["nn", "name", "category", "n_filters", "n_rankings", "n_custom_factors", "n_inline_formulas",
        "annual_pct", "sharpe", "max_drawdown_pct", "benchmark", "excess_annual_pct"]
with open(G / "strategies_overview.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    for r in records:
        w.writerow({
            "nn": r["nn"], "name": r["name"], "category": r["category"],
            "n_filters": len(r["recipe"]["filters"]), "n_rankings": len(r["recipe"]["rankings"]),
            "n_custom_factors": len(r["indicators_used"]["custom"]),
            "n_inline_formulas": len(r["indicators_used"]["inline_formulas"]),
            "annual_pct": r["backtest"]["annual_pct"], "sharpe": r["backtest"]["sharpe"],
            "max_drawdown_pct": r["backtest"]["max_drawdown_pct"], "benchmark": r["backtest"]["benchmark"],
            "excess_annual_pct": r["backtest"]["excess_annual_pct"],
        })

print("wrote guorn_strategies_master.json (%d strategies) + strategies_overview.csv" % len(records))
# sanity
miss_bt = [r["name"] for r in records if not r["backtest"]["annual_pct"]]
miss_xlsx = [r["files"]["backtest_xlsx"] for r in records if not (Path(r"E:\量化系统") / r["files"]["backtest_xlsx"]).exists()]
print("strategies missing backtest metric:", miss_bt)
print("strategies missing xlsx file:", len(miss_xlsx), miss_xlsx[:3])
ex = records[11]
print("sample [12]:", ex["name"], "| filters", len(ex["recipe"]["filters"]), "| rankings", len(ex["recipe"]["rankings"]),
      "| custom", len(ex["indicators_used"]["custom"]), "| annual", ex["backtest"]["annual_pct"])
