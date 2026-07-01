"""Extract the recipes of the 20 LIVE-DEPLOYED guorn strategies (deployed_portfolio_20260624.json)
from guorn_strategies_master.json into a triage doc, and print a compact 1-2-line summary per strategy
for factor-availability classification. Writes deployed_20_recipes.md (full detail); prints the summary.
"""
import difflib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8")
G = ROOT / "workspace" / "research" / "idea_sourcing" / "guorn"

master = json.loads((G / "guorn_strategies_master.json").read_text(encoding="utf-8"))
deployed = json.loads((G / "deployed_portfolio_20260624.json").read_text(encoding="utf-8"))
strats = master if isinstance(master, list) else master.get("strategies", list(master.values()) if isinstance(master, dict) else master)
by_name = {s["name"]: s for s in strats}

lines_md = ["# 20 deployed guorn strategies — recipes (triage source)\n",
            f"Source: deployed_portfolio_20260624.json x guorn_strategies_master.json. {len(by_name)} strategies in master.\n"]
print(f"{'#':>2} {'name':32} {'cat':6} {'uni':18} {'flt':>3} {'rnk':>3} {'annual':>7} {'shrp':>5}  key_ranking_factors")
print("-" * 130)

for d in deployed["strategies"]:
    dn = d["name"]
    s = by_name.get(dn)
    tag = ""
    if s is None:
        m = difflib.get_close_matches(dn, list(by_name.keys()), n=1, cutoff=0.5)
        if m:
            s = by_name[m[0]]; tag = f"~{m[0]}"
    if s is None:
        print(f"{d['idx']:>2} {dn:32} NO MATCH IN MASTER")
        lines_md.append(f"\n## {d['idx']}. {dn} — NO MATCH IN MASTER\n")
        continue
    r = s.get("recipe", {})
    uni = r.get("universe", {})
    filt = r.get("filters", [])
    rank = r.get("rankings", [])
    tm = r.get("trade_model", {})
    mt = r.get("market_timing", "")
    iu = s.get("indicators_used", {})
    bt = s.get("backtest", {})
    uni_s = uni.get("板块") or uni.get("股票池") or uni.get("指数") or "?"
    rank_toks = [x.get("indicator", "?") for x in rank]
    annual = bt.get("annual_pct"); sharpe = bt.get("sharpe")
    print(f"{d['idx']:>2} {dn[:32]:32} {str(s.get('category',''))[:6]:6} {str(uni_s)[:18]:18} "
          f"{len(filt):>3} {len(rank):>3} {str(annual)[:7]:>7} {str(sharpe)[:5]:>5}  "
          f"{', '.join(rank_toks[:5])}{' …' if len(rank_toks) > 5 else ''}")
    # full detail to md
    lines_md.append(f"\n## {d['idx']}. {dn}  (nn={s.get('nn')}, {s.get('category')}) {tag}")
    lines_md.append(f"- **backtest**: annual={annual} sharpe={sharpe} mdd={bt.get('max_drawdown_pct')} "
                    f"vol={bt.get('volatility_pct')} bench={bt.get('benchmark')} excess={bt.get('excess_annual_pct')}")
    lines_md.append(f"- **universe**: {json.dumps(uni, ensure_ascii=False)}")
    lines_md.append(f"- **filters({len(filt)})**: " + "; ".join(
        f"{f.get('indicator')} {f.get('op','')} {f.get('value','')}".strip() for f in filt))
    lines_md.append(f"- **rankings({len(rank)})**:")
    for x in rank:
        lines_md.append(f"    - `{x.get('indicator')}` dir={x.get('direction')} scope={x.get('scope')} w={x.get('weight')}")
    lines_md.append(f"- **trade_model**: {json.dumps(tm, ensure_ascii=False)}")
    lines_md.append(f"- **buy_limit (新股买入限制)**: {json.dumps(r.get('buy_limit', []), ensure_ascii=False)}")
    lines_md.append(f"- **sell_conditions (卖出条件)**: {json.dumps(r.get('sell_conditions', []), ensure_ascii=False)}")
    lines_md.append(f"- **hold_keep_conditions (不卖条件)**: {json.dumps(r.get('hold_keep_conditions', []), ensure_ascii=False)}")
    lines_md.append(f"- **market_timing (大盘择时)**: {mt}")
    cust = iu.get("custom", [])
    lines_md.append(f"- **custom factors({len(cust)})**:")
    for c in cust:
        lines_md.append(f"    - `{c.get('token')}` = {c.get('expr','')}")
    lines_md.append(f"- **builtin/field**: {iu.get('builtin_or_field', [])}")
    lines_md.append(f"- **inline formulas**: {iu.get('inline_formulas', [])}")

(G / "deployed_20_recipes.md").write_text("\n".join(lines_md), encoding="utf-8")
print(f"\n[ok] wrote {G / 'deployed_20_recipes.md'}")
