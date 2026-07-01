"""One-off scan (rung-2 selection): find 果仁 books that RANK on pure statement
ratios with NO proprietary cross-sectional ops (中性化/壳价值/MI) and NO
PIT-high-risk forecast/analyst factors (预期/预告/快报/朝阳/评级).

Output: workspace/outputs/guorn_parity/clean_statement_scan.txt (UTF-8).
Throwaway analysis utility — not wired into anything.
"""
from __future__ import annotations
import io
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MASTER = os.path.join(ROOT, "workspace", "research", "idea_sourcing", "guorn",
                      "guorn_strategies_master.json")
OUT = os.path.join(ROOT, "workspace", "outputs", "guorn_parity", "clean_statement_scan.txt")

NEUTRALIZE = ["中性", "Neutralize", "neutralize", "NEUTRAL", "壳", "SSlope", "Hneutralize"]
FORECAST = ["预期", "预告", "快报", "朝阳", "评级", "report_rc", "一致预期", "rc__"]
STATEMENT = ["营业收入", "营业成本", "净利润", "资产总计", "现金流", "所有者权益",
             "股东权益", "EBITDA", "FCF", "ROE", "ROA", "BP", "EP", "毛利", "核心利润",
             "Sales", "GrossProfit", "CoreProfit", "所得税", "扣非", "经营现金", "归属",
             "营业利润", "利润总额", "负债", "EBIT", "OPCF", "ProfitQ"]
# reproducible-but-not-statement price/vol factors (informational)
PRICEVOL = ["ILLIQ", "动量", "振幅", "换手", "波动", "隔夜", "反转", "新高", "成交额",
            "股价", "贝塔", "beta", "RSI", "MA(", "MACD", "量价"]


def _has(text, markers):
    return [m for m in markers if m in text]


def main():
    with io.open(MASTER, encoding="utf-8") as f:
        data = json.load(f)
    strategies = data["strategies"] if isinstance(data, dict) else data

    # token -> expr map is per-strategy (indicators_used.custom)
    rows = []
    for s in strategies:
        recipe = s.get("recipe", {}) or {}
        rankings = recipe.get("rankings", []) or []
        rank_tokens = [r.get("indicator", "") for r in rankings]
        custom = {c.get("token", ""): c.get("expr", "")
                  for c in (s.get("indicators_used", {}) or {}).get("custom", [])}
        # build the ranking text: indicator tokens + exprs of customs whose token
        # appears in any ranking token + inline formulas used in rankings
        rank_text = " ".join(rank_tokens)
        for tok, expr in custom.items():
            if tok and any(tok in rt for rt in rank_tokens):
                rank_text += " " + expr
        # also fold ALL custom exprs that are clearly ranking-side (best-effort:
        # include every custom expr so neutralization hidden one layer down is caught)
        deep_text = rank_text + " " + " ".join(custom.values())

        neut = sorted(set(_has(deep_text, NEUTRALIZE)))
        fcst = sorted(set(_has(deep_text, FORECAST)))
        stmt = sorted(set(_has(rank_text, STATEMENT)))
        pv = sorted(set(_has(rank_text, PRICEVOL)))

        uni = recipe.get("universe", {}) or {}
        bt = s.get("backtest", {}) or {}
        rows.append({
            "nn": s.get("nn"), "name": s.get("name"), "category": s.get("category"),
            "n_rank": len(rankings), "rank_tokens": rank_tokens,
            "neut": neut, "fcst": fcst, "stmt": stmt, "pv": pv,
            "board": uni.get("板块", ""), "stock_pool": uni.get("股票池", ""),
            "benchmark": bt.get("benchmark", ""), "annual": bt.get("annual_pct"),
            "sharpe": bt.get("sharpe"),
            "clean_statement": bool(stmt) and not neut and not fcst,
        })

    def _f(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return -9.0

    clean = [r for r in rows if r["clean_statement"]]
    # rank clean books: fewer rankings first, then statement-dominant, then sharpe
    clean.sort(key=lambda r: (r["n_rank"], -len(r["stmt"]), -_f(r["sharpe"])))

    lines = []
    lines.append("=== CLEAN STATEMENT-RANKING BOOKS (no 中性化/壳/MI, no 预期/预告/快报) ===")
    lines.append(f"{len(clean)} of {len(rows)} books qualify\n")
    for r in clean:
        lines.append(
            f"#{r['nn']:>2} {r['name']:<28} | rankings={r['n_rank']} "
            f"stmt={r['stmt']} pricevol={r['pv']}")
        lines.append(f"     board={r['board']!r} pool={r['stock_pool']!r} "
                     f"bench={r['benchmark']} annual={r['annual']} sharpe={r['sharpe']}")
        lines.append(f"     RANKINGS: {r['rank_tokens']}")
        lines.append("")

    lines.append("\n=== REJECTED (statement book BUT has neutralize/forecast) ===")
    for r in rows:
        if (r["stmt"] and not r["clean_statement"]):
            why = []
            if r["neut"]:
                why.append(f"NEUT={r['neut']}")
            if r["fcst"]:
                why.append(f"FORECAST={r['fcst']}")
            lines.append(f"#{r['nn']:>2} {r['name']:<28} n_rank={r['n_rank']} "
                         f"sharpe={r['sharpe']} | {'; '.join(why)}")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("wrote", OUT, "| clean books:", len(clean))


if __name__ == "__main__":
    main()
