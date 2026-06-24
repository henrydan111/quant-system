# -*- coding: utf-8 -*-
"""One-off: print the structured recipe + backtest for the 20 strategies in the
live 果仁 portfolio (the equal-weight book the user wants to re-weight)."""
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

master = json.loads(Path(r"E:\量化系统\workspace\research\idea_sourcing\guorn\guorn_strategies_master.json").read_text(encoding="utf-8"))
strats = master if isinstance(master, list) else master.get("strategies", master)

want = [
 "sm_01_成长动量", "sm_01_成长_v1", "sm_大制造GARP_v3", "sm_GARP_illiq", "sm_双创研发强度_v1",
 "sm_01_成长高贝塔@TMT_v1", "value_红利低波_v2", "value_红利低波_央企_v1", "value_红利低波_重股息_v1",
 "value_AH_低溢价GARP_v1", "value_FCF_非金sm_v2", "value_创业板sm_v1", "成长_机构预期@周期_v1",
 "成长_净利润断层_v2", "成长_双创_GARP@周期_v2", "成长_隔夜动量@周期", "成长_高波@周期",
 "ST_大市值_v3", "MultiA_风险平价_v1", "MultiA_动量18",
]
by_name = {s.get("name"): s for s in strats}
print("MASTER has", len(strats), "strategies")
print("MISSING:", [w for w in want if w not in by_name])
print("=" * 100)


def short(d, keys):
    if not isinstance(d, dict):
        return str(d)
    return {k: d.get(k) for k in keys if d.get(k) not in (None, "", "全部", "无")}


for w in want:
    s = by_name.get(w)
    if not s:
        print("!! NOT FOUND", w)
        continue
    r = s.get("recipe", {}) or {}
    bt = s.get("backtest", {}) or {}
    print(f"\n##### nn={s.get('nn')}  {s.get('name')}   [{s.get('category')}]")
    uni = r.get("universe", {}) or {}
    print("  UNIVERSE:", short(uni, ["股票池", "指数", "板块", "行业", "ST", "科创板", "北交所", "创业板"]))
    flt = r.get("filters", []) or []
    print(f"  FILTERS ({len(flt)}):")
    for f in flt:
        print("     -", f.get("indicator"), f.get("op"), f.get("value"), ("scope=" + f["scope"]) if f.get("scope") else "")
    rk = r.get("rankings", []) or []
    print(f"  RANKINGS ({len(rk)}):")
    for f in rk:
        print("     *", f.get("indicator"), "|", f.get("direction"), "| w=", f.get("weight"), "| scope=", f.get("scope"))
    tm = r.get("trade_model", {}) or {}
    print("  TRADE:", short(tm, ["模型", "调仓周期", "调仓价格", "个股仓位范围", "备选买入股票数", "持股数", "最大持股数"]))
    mt = r.get("market_timing")
    if mt and mt != "无":
        print("  TIMING:", (mt[:200] + "...") if isinstance(mt, str) and len(mt) > 200 else mt)
    print("  BACKTEST: ann%=", bt.get("annual_pct"), "sharpe=", bt.get("sharpe"),
          "mdd%=", bt.get("max_drawdown_pct"), "vol%=", bt.get("volatility_pct"),
          "bench=", bt.get("benchmark"), "excess%=", bt.get("excess_annual_pct"))
