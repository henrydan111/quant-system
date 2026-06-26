"""Extract the EXECUTION layer (trade model / holding count / rebalance cadence / fill / candidate pool /
market timing / cost) for each of the 20 deployed guorn strategies — the spec needed to reproduce
execution faithfully (not just the factors). Prints a table + writes deployed_20_trade_models.md.
"""
import difflib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8")
G = ROOT / "workspace" / "research" / "idea_sourcing" / "guorn"
master = json.loads((G / "guorn_strategies_master.json").read_text(encoding="utf-8"))
deployed = json.loads((G / "deployed_portfolio_20260624.json").read_text(encoding="utf-8"))
strats = master if isinstance(master, list) else master.get("strategies", list(master.values()))
by_name = {s["name"]: s for s in strats}


def implied_holds(pos_range):
    m = re.findall(r"([\d.]+)\s*%", pos_range or "")
    if len(m) >= 2:
        lo, hi = float(m[0]) / 100, float(m[1]) / 100
        return f"{1/hi:.0f}-{1/lo:.0f} (~{round(2/(lo+hi))})"
    if len(m) == 1:
        return f"~{1/(float(m[0])/100):.0f}"
    return "?"


rows = []
md = ["# 20 deployed guorn strategies — EXECUTION spec (trade model / holdings / rebalance)\n",
      "Extracted from guorn_strategies_master.json recipe.trade_model + market_timing + backtest.cost.",
      "`隐含持仓` = derived from 个股仓位范围 (1/upper .. 1/lower, ~target). `部署持仓` = live count from the screenshot.\n"]
for d in deployed["strategies"]:
    s = by_name.get(d["name"])
    tag = ""
    if s is None:
        m = difflib.get_close_matches(d["name"], list(by_name.keys()), n=1, cutoff=0.5)
        if m:
            s = by_name[m[0]]; tag = f"~{m[0]}"
    if s is None:
        rows.append([d["idx"], d["name"], "—", "—", "—", "—", "—", "—", "—", d["n_holdings"], "NO MATCH"])
        continue
    tm = s.get("recipe", {}).get("trade_model", {})
    mt = s.get("recipe", {}).get("market_timing", "无") or "无"
    bt = s.get("backtest", {})
    cost = bt.get("cost_note") or bt.get("cost") or bt.get("cost_pct") or "?"
    posr = tm.get("个股仓位范围") or tm.get("持仓数量") or tm.get("个股仓位") or "?"
    rows.append([
        d["idx"], d["name"], tm.get("模型", "?"), tm.get("调仓周期", "?"), tm.get("调仓价格", "?"),
        posr, implied_holds(posr if "%" in str(posr) else ""), tm.get("备选买入股票数", "?"),
        ("有" if mt != "无" else "无"), d["n_holdings"], cost,
    ])
    md.append(f"\n## {d['idx']}. {d['name']} {tag}")
    md.append(f"- model={tm.get('模型')} · 调仓周期={tm.get('调仓周期')} · 调仓价格={tm.get('调仓价格')} · "
              f"个股仓位范围={posr} (隐含 {implied_holds(posr if '%' in str(posr) else '')}) · 备选={tm.get('备选买入股票数')}")
    md.append(f"- 新股理想仓位={tm.get('新股理想仓位')} · 最小建仓={tm.get('最小建仓仓位')} · 空闲资金={tm.get('空闲资金配置')} · "
              f"实时选股={tm.get('实时选股')} · 交易日期={tm.get('交易日期')}")
    md.append(f"- market_timing={mt}")
    md.append(f"- cost={cost} · 部署持仓(screenshot)={d['n_holdings']}")

print(f"{'#':>2} {'name':26} {'模型':3} {'周期':4} {'价格':6} {'仓位范围':13} {'隐含':10} {'备选':4} {'择时':4} {'部署':4}  cost")
print("-" * 120)
for r in rows:
    print(f"{r[0]:>2} {str(r[1])[:26]:26} {str(r[2]):3} {str(r[3]):>4} {str(r[4])[:6]:6} {str(r[5])[:13]:13} "
          f"{str(r[6]):10} {str(r[7]):>4} {str(r[8]):4} {str(r[9]):>4}  {str(r[10])[:30]}")
(G / "deployed_20_trade_models.md").write_text("\n".join(md), encoding="utf-8")
print(f"\n[ok] wrote {G / 'deployed_20_trade_models.md'}")
