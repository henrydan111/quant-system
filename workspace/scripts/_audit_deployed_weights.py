"""Weight-handling audit for the 20 deployed 果仁 strategies. For each: list every ranking TERM
(indicator, 次序/direction, 范围/scope, 权重/weight) exactly as in the recipe, the TOTAL weight, and
flag DUPLICATE indicators (same factor listed >1× = separate terms that must each contribute
排名分×weight, e.g. 总市值 ×2 or OPCFNPDiff%NP ×2). Confirms (a) weights are read from the recipe's
`weight` field, (b) duplicates are kept as distinct terms, (c) scope (全部 vs 一级行业内) is captured.
The composite then applies 综合排名分 = Σ(排名分_i × weight_i) per 果仁筛选与排名功能 §3.1.4."""
import difflib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8")
G = ROOT / "workspace" / "research" / "idea_sourcing" / "guorn"
master = json.loads((G / "guorn_strategies_master.json").read_text(encoding="utf-8"))
deployed = json.loads((G / "deployed_portfolio_20260624.json").read_text(encoding="utf-8"))
strats = master if isinstance(master, list) else master.get("strategies", list(master.values()))
by_name = {s["name"]: s for s in strats}

problems = []
for d in deployed["strategies"]:
    s = by_name.get(d["name"])
    if s is None:
        m = difflib.get_close_matches(d["name"], list(by_name.keys()), n=1, cutoff=0.5)
        s = by_name[m[0]] if m else None
    if s is None:
        print(f"#{d['idx']:>2} {d['name']}: NO MATCH"); continue
    rank = s.get("recipe", {}).get("rankings", [])
    terms = []
    for r in rank:
        w = r.get("weight", r.get("权重"))
        try:
            wv = float(w)
        except (TypeError, ValueError):
            wv = None
            problems.append(f"#{d['idx']} {d['name']}: non-numeric weight {w!r} on {r.get('indicator')}")
        terms.append((r.get("indicator", "?"), r.get("direction", "?"), r.get("scope", "?"), wv))
    total_w = sum(t[3] for t in terms if t[3] is not None)
    counts = Counter(t[0] for t in terms)
    dups = {k: v for k, v in counts.items() if v > 1}
    nonunit = [t for t in terms if t[3] not in (1.0, None)]
    print(f"\n#{d['idx']:>2} {d['name']}  ({len(terms)} ranking terms, total weight = {total_w:g})")
    for ind, dirn, scope, wv in terms:
        star = " *" if wv not in (1.0, None) else "  "
        print(f"     w={('?' if wv is None else f'{wv:g}'):>3}{star} {str(ind)[:46]:46} {dirn}  [{scope}]")
    if dups:
        print(f"     ⟹ DUPLICATE indicators (each a SEPARATE weighted term): {dict(dups)}")

print("\n" + "=" * 72)
print("APPLICATION (all strategies): 综合排名分 = Σ(排名分_i × weight_i) over EVERY ranking term i")
print("  - 排名分_i = (N − 排名 + 1)/N × 100 within the scope (全部=cross-section, 一级行业内=within 申万L1)")
print("  - duplicate indicators -> each instance is its own term i (summed), NOT merged")
print("  - NaN factor -> ranked last (worst 排名分), per §3.1.4")
print(f"\nweight extraction problems: {problems if problems else 'NONE — all weights numeric'}")
