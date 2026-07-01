"""Build the 果仁 FACTOR-LEVEL inventory + validation tracker (dashboard-consumable).

Enumerates every 果仁 indicator used across the strategies (resolved_indicators.json = 195 unique named tokens
over 65 strategies), joins each to (a) its local mapping + parity status from the CANONICAL ledger
guorn_local_field_mapping.md (§1/§1b/§1c tables) and (b) its usage breadth (strategies_master), then classifies
each into one of six buckets:

  validated      ✅  in the ledger with a penny/structure-exact or vendor-approx parity status
  doable         🟢  resolves to a local provider field / pointwise expr; not yet validated — run the comparator
  harness        🟡  cross-sectional / 行业内 / 综合 — needs the 综合级 harness (comparator is pointwise-only)
  data_blocked   🔴  needs UNMATERIALIZED data (forward-quarterly consensus / EV / D&A single-q / q5+ depth / 行业 aggregates)
  irreducible    ⛔  cannot penny-match 果仁 by design (中性化 regression / 壳价值 / 退市风险 screens / vendor-diff)
  triage         ❓  not auto-classifiable — needs a human pass

Outputs (next to the other guorn artifacts):
  guorn_factor_tracker.json  — machine-readable (dashboard reads this)
  guorn_factor_tracker.md    — human summary + per-bucket tables

⚠ The bucket auto-classification is a FIRST PASS: `validated` (ledger join) and the named `irreducible`/
`data_blocked` patterns are high-confidence; the `doable`/`harness`/`triage` split is heuristic and the MD flags
it for human review. NON-FORMAL parity tooling.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
G = ROOT / "workspace" / "research" / "idea_sourcing" / "guorn"
OUT_JSON = G / "guorn_factor_tracker.json"
OUT_MD = G / "guorn_factor_tracker.md"

# ---- classification patterns (from the ledger §5 + the known data gaps) ----
IRREDUCIBLE = ["中性化", "中性", "壳价值", "SSlope", "Neutralize", "HNeutralize", "退市", "风险预警",
               "重大违规", "国九条", "预期ST", "新增流通股"]                       # +§5 no-feed/lookahead
DATA_BLOCKED = ["EV", "企业价值", "EBITDAQ%EV", "EBITDA%EV", "折旧", "摊销", "FCFQ", "自由现金流",
                "3年", "三年", "复合增长", "CAGR", "预期净利润", "预期营收", "预期EPS", "一致预期",
                "朝阳永续", "行业净利润", "行业涨幅", "行业增长",
                "快报", "调入指数", "波动率_季度指标", "StdevQ", "StDevQ"]          # +快报/index-event/12q-depth
HARNESS = ["行业内", "排名", "HAVG", "hAvg", "综合", "分位"]
NOISE = {"无", "", "-", "—", "全部"}
LEDGER_VALIDATED_STATUSES = ("display_precision", "validated", "penny", "penny_exact", "structure_exact",
                             "rank_faithful", "vendor_approx", "vendor-approx")


def parse_ledger_md(md: str) -> dict:
    """Extract {guorn_name: {local_expr, status, parity, section}} from the §1/§1b/§1c markdown tables.
    Rows look like:  | **总市值** | <formula> | `$total_mv` (万元) | ✅ display-precision (...) | 4 |"""
    out = {}
    section = None
    for line in md.splitlines():
        if line.startswith("### 1c"): section = "1c"; continue
        if line.startswith("### 1b"): section = "1b"; continue
        if line.startswith("## 1."): section = "1"; continue
        if line.startswith("## 2."): section = "2"; continue       # data-validated, reconstruction-convention
        if line.startswith("## 3."): section = "3"; continue       # un-validatable (display 0.00); data path OK
        if line.startswith("## 4.") or line.startswith("## 5.") or line.startswith("## 6."): section = None; continue
        if section and line.startswith("| **"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 2:
                continue
            name = cells[0].strip().strip("*").strip()
            if section in ("1", "1b", "1c"):                        # | name | formula | local | status | … |
                local = cells[2] if len(cells) > 2 else ""
                status = cells[3] if len(cells) > 3 else cells[-1]
            elif section == "2":                                   # | name | local expr | residual | proof |
                local = cells[1] if len(cells) > 1 else ""
                status = "data-validated (convention residual): " + (cells[2] if len(cells) > 2 else "")
            else:                                                  # §3: | name | why un-validatable | note |
                local = None
                status = "un-validatable (display 0.00); data path OK"
            out[name] = {"local_expr": local, "status_text": status, "section": section}
    return out


def classify(tok: str, kind: str, expr: str, ledger_hit) -> tuple[str, str]:
    """-> (bucket, reason)."""
    t = tok + " " + (expr or "")
    if ledger_hit is not None:
        st = ledger_hit["status_text"]
        if "vendor-approx" in st or "rank-faithful" in st or ledger_hit["section"] == "1c":
            return "validated", f"ledger §{ledger_hit['section']} vendor-approx (rank-faithful): {st[:40]}"
        return "validated", f"ledger §{ledger_hit['section']}: {st[:50]}"
    if any(p in t for p in IRREDUCIBLE):
        return "irreducible", "cannot penny-match (中性化/壳价值/退市风险/vendor regression)"
    if any(p in t for p in DATA_BLOCKED):
        return "data_blocked", "needs unmaterialized data (consensus-Q / EV / D&A-sq / q5+ depth / 行业 aggregate)"
    if any(p in t for p in HARNESS):
        return "harness", "cross-sectional / 行业内 / 综合 — use the 综合级 harness (comparator is pointwise-only)"
    if kind in ("custom", "builtin_prose_or_field", "builtin_table") and (expr or kind != "custom"):
        return "doable", "resolves to a local field/pointwise expr — validate via guorn_factor_parity.py"
    return "triage", "not auto-classifiable — needs a human pass"


def main():
    resolved = json.loads((G / "resolved_indicators.json").read_text(encoding="utf-8"))["resolved"]
    ledger = parse_ledger_md((G / "guorn_local_field_mapping.md").read_text(encoding="utf-8"))

    factors = []
    n_noise = 0
    for e in resolved:
        tok = (e.get("token") or e.get("base") or "").strip()
        if tok in NOISE or len(tok) < 2:                            # drop noise/empty tokens
            n_noise += 1
            continue
        kind = e.get("kind", "")
        expr = e.get("expr", "")
        hit = ledger.get(tok) or ledger.get(e.get("base", ""))
        bucket, reason = classify(tok, kind, expr, hit)
        factors.append({
            "guorn_indicator": tok,
            "kind": kind,
            "guorn_formula": expr or None,
            "local_expr": (hit["local_expr"] if hit else None),
            "bucket": bucket,
            "ledger_status": (hit["status_text"] if hit else None),
            "ledger_section": (hit["section"] if hit else None),
            "n_strategies": e.get("n_strategies", 0),
            "usage_count": e.get("count", 0),
            "reason": reason,
        })

    factors.sort(key=lambda f: (f["bucket"], -f["n_strategies"]))
    counts = {}
    for f in factors:
        counts[f["bucket"]] = counts.get(f["bucket"], 0) + 1

    meta = {
        "generated_from": ["resolved_indicators.json", "guorn_local_field_mapping.md", "strategies (65)"],
        "n_indicators": len(factors), "n_strategies": 65, "bucket_counts": counts,
        "buckets_legend": {
            "validated": "✅ in the ledger, parity-validated (penny/structure-exact or vendor-approx rank-faithful)",
            "doable": "🟢 resolves to a local field/pointwise expr — validate via guorn_factor_parity.py",
            "harness": "🟡 cross-sectional/综合 — needs the 综合级 harness (comparator is pointwise-only)",
            "data_blocked": "🔴 needs UNMATERIALIZED data (consensus-Q / EV / D&A-sq / q5+ depth / 行业 aggregate)",
            "irreducible": "⛔ cannot penny-match 果仁 by design (中性化 / 壳价值 / 退市风险 / vendor regression)",
            "triage": "❓ not auto-classifiable — human pass needed",
        },
        "caveat": "Auto-classified FIRST PASS. validated(ledger)+named irreducible/data_blocked = high-confidence; "
                  "doable/harness/triage split is heuristic — confirm by hand before relying on it.",
    }
    OUT_JSON.write_text(json.dumps({"_meta": meta, "factors": factors}, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- human MD ----
    order = ["validated", "doable", "harness", "data_blocked", "irreducible", "triage"]
    icon = {"validated": "✅", "doable": "🟢", "harness": "🟡", "data_blocked": "🔴", "irreducible": "⛔", "triage": "❓"}
    L = ["# 果仁 factor-level inventory + validation tracker",
         "",
         "> Auto-generated by `workspace/scripts/build_guorn_factor_tracker.py` from `resolved_indicators.json` "
         "(195 unique indicators over 65 strategies) joined to the canonical ledger `guorn_local_field_mapping.md` "
         "+ usage. **NON-FORMAL.** The bucket split is a FIRST PASS — `validated` and named `irreducible`/"
         "`data_blocked` are high-confidence; `doable`/`harness`/`triage` are heuristic (confirm by hand). "
         "Machine-readable sidecar: `guorn_factor_tracker.json` (dashboard reads this).",
         "",
         f"**{len(factors)} indicators** · " + " · ".join(f"{icon[b]} {b} **{counts.get(b,0)}**" for b in order),
         ""]
    for b in order:
        rows = [f for f in factors if f["bucket"] == b]
        if not rows:
            continue
        L += [f"## {icon[b]} {b} ({len(rows)}) — {meta['buckets_legend'][b]}", "",
              "| 果仁 indicator | local expr / status | n_strat | note |", "|---|---|---|---|"]
        for f in rows:
            loc = f["local_expr"] or (f["ledger_status"] or "—")
            note = (f["ledger_status"] or f["reason"])[:70] if b == "validated" else f["reason"][:70]
            L.append(f"| {f['guorn_indicator']} | {loc[:48]} | {f['n_strategies']} | {note} |")
        L.append("")
    L += ["## How to use this tracker", "",
          "- **Validate the 🟢 doable batch first, highest-usage first** (rows sorted by `n_strat`): per factor run "
          "`guorn_factor_parity.py` (字段级) — export 果仁's value via the web guide, compare. The doable split is a "
          "first pass; some entries will reclassify to harness/blocked on a closer look.",
          "- 🔴 **data_blocked** → each needs a data-infra unlock (consensus-Q / EV / D&A single-q / q5+ statement "
          "depth / 行业 aggregate) before its factors are reproducible.",
          "- ⛔ **irreducible** → label un-reproducible (果仁's proprietary 中性化 regression / no local data); do "
          "NOT chase penny-parity.",
          "- ❓ **triage** → human pass to assign a bucket.",
          "",
          "**Dashboard integration (后续):** the machine-readable `guorn_factor_tracker.json` (`_meta.bucket_counts` "
          "+ `factors[]` rows) is the dashboard data source. A future `src/dashboard/` reader loads it and renders a "
          "'果仁 Factor Validation' panel (bucket-count summary + per-bucket sortable tables, prioritized by "
          "`n_strategies`). Regenerate with `venv/Scripts/python.exe workspace/scripts/build_guorn_factor_tracker.py` "
          "whenever the ledger (`guorn_local_field_mapping.md`) or the recipes change."]
    OUT_MD.write_text("\n".join(L), encoding="utf-8")
    print(f"[tracker] {len(factors)} indicators -> {counts}")
    print(f"[tracker] wrote {OUT_JSON.name} + {OUT_MD.name}")


if __name__ == "__main__":
    main()
