"""Build the RESUMABLE per-factor 果仁 web-validation campaign log for the DEPLOYED-20 books.

The user's directive: validate EVERY factor used by the deployed strategies — including the already-validated
ones — INDIVIDUALLY through the 果仁 web platform (one export per factor), deployed-20 first, highest-usage first.

This seeds the campaign: from the 20 deployed books' `indicators_used`, collect the unique factors, cross-ref the
factor tracker (bucket / local_expr / usage), keep only the WEB-VALIDATABLE ones (validated + doable — the
data_blocked/irreducible can't be reproduced locally so a web export only confirms divergence), order by deployed
usage, and emit a status log that the campaign updates one factor at a time.

Outputs (idempotent re-seed PRESERVES existing per-factor status/result):
  guorn_web_validation_campaign.json  — machine-readable status log (the resumable source of truth)
  guorn_web_validation_campaign.md    — human checklist (factor | bucket | local_expr | usage | status | verdict)

NON-FORMAL parity tooling.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
G = ROOT / "workspace" / "research" / "idea_sourcing" / "guorn"
LOG_JSON = G / "guorn_web_validation_campaign.json"
LOG_MD = G / "guorn_web_validation_campaign.md"

WEB_VALIDATABLE = {"validated", "doable"}     # data_blocked/irreducible/triage are NOT web-validatable here


def main():
    deployed = json.loads((G / "deployed_portfolio_20260624.json").read_text(encoding="utf-8"))
    dep_strats = deployed.get("strategies", [])
    dep_nn = {s.get("nn") for s in dep_strats if s.get("nn") is not None}
    dep_names = {s.get("name") for s in dep_strats}

    master = json.loads((G / "guorn_strategies_master.json").read_text(encoding="utf-8"))["strategies"]
    tracker = {f["guorn_indicator"]: f
               for f in json.loads((G / "guorn_factor_tracker.json").read_text(encoding="utf-8"))["factors"]}

    # collect unique factors used by the deployed books + which books use each
    used = {}                                  # token -> {books:set, n_dep:int}
    for s in master:
        if s.get("nn") not in dep_nn and s.get("name") not in dep_names:
            continue
        book = f"#{s.get('nn')} {s.get('name','')}"
        iu = s.get("indicators_used", {})
        toks = []
        for grp in ("custom", "builtin_or_field"):       # the real single-factor groups (inline_formulas = 综合, separate)
            for e in (iu.get(grp) or []):
                toks.append((e.get("token") or e.get("base")) if isinstance(e, dict) else e)
        for t in set(filter(None, toks)):
            used.setdefault(t, {"books": set(), "n_dep": 0})
            used[t]["books"].add(book)
    for t in used:
        used[t]["n_dep"] = len(used[t]["books"])

    # preserve any existing status/result on re-seed
    prior = {}
    if LOG_JSON.exists():
        for f in json.loads(LOG_JSON.read_text(encoding="utf-8")).get("factors", []):
            prior[f["guorn_indicator"]] = f

    rows = []
    for tok, u in used.items():
        tk = tracker.get(tok)
        bucket = tk["bucket"] if tk else "triage"
        if bucket not in WEB_VALIDATABLE:
            continue                            # skip data_blocked/irreducible/triage for the web campaign
        p = prior.get(tok, {})
        rows.append({
            "guorn_indicator": tok,
            "bucket": bucket,
            "local_expr": (tk.get("local_expr") if tk else None) or p.get("local_expr"),
            "guorn_formula": (tk.get("guorn_formula") if tk else None),
            "n_deployed_books": u["n_dep"],
            "n_strategies_all": (tk.get("n_strategies") if tk else u["n_dep"]),
            "deployed_books": sorted(u["books"]),
            "status": p.get("status", "pending"),       # pending | done | diverged | blocked | skipped
            "verdict": p.get("verdict"),                # the comparator verdict string
            "export_file": p.get("export_file"),
            "selection_date": p.get("selection_date"),
            "note": p.get("note"),
        })
    rows.sort(key=lambda r: (r["status"] != "pending", -r["n_deployed_books"], -r["n_strategies_all"]))

    done = sum(1 for r in rows if r["status"] in ("done", "diverged"))
    meta = {"scope": "deployed-20, web-validatable (validated+doable), one export per factor",
            "n_factors": len(rows), "n_done": done, "n_pending": len(rows) - done,
            "status_legend": "pending → done(✅ parity) / diverged(✗ real gap) / blocked / skipped",
            "procedure_per_factor": [
                "1. 果仁 web: rank-ONLY on this single indicator, universe to match (or a broad universe — factor "
                "VALUES are 范围/universe-invariant), 选股日期 ≤ local calendar max.",
                "2. 导出 → rename 果仁_{date}_{universe}_{indicator}.xlsx under Knowledge/果仁验证因子/.",
                "3. derive/confirm the local_expr (validated rows already have it; doable rows: map the 果仁_formula "
                "→ local qlib expr via guorn_local_field_mapping.md conventions).",
                "4. guorn_factor_parity.py --xlsx <export> --date <date> --local-expr '<expr>' --guorn-col <name> "
                "[--kind count] [--min-coverage X w/ reason].",
                "5. record status/verdict here (re-run this script preserves it).",
            ]}
    LOG_JSON.write_text(json.dumps({"_meta": meta, "factors": rows}, ensure_ascii=False, indent=2), encoding="utf-8")

    L = ["# 果仁 web-validation campaign — DEPLOYED-20 (per-factor)", "",
         f"> One export per factor, deployed-20 first, highest-usage first. **{len(rows)} web-validatable factors** "
         f"({done} done / {len(rows)-done} pending). Resumable: status lives in `guorn_web_validation_campaign.json`; "
         "re-run `build_guorn_validation_campaign.py` to re-seed (preserves status). NON-FORMAL.", "",
         "Procedure per factor: " + " ".join(meta["procedure_per_factor"]), "",
         "| # | 果仁 indicator | bucket | local_expr | dep books | status | verdict |",
         "|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        st = {"pending": "⬜ pending", "done": "✅ done", "diverged": "✗ diverged",
              "blocked": "🔴 blocked", "skipped": "⏭ skipped"}.get(r["status"], r["status"])
        # full (un-truncated) verdict/local_expr; escape pipes + flatten newlines so the MD stays a faithful,
        # table-safe render of the JSON store (prevents the MD↔JSON drift that hand-editing full verdicts caused).
        expr_cell = (r["local_expr"] or "— derive —").replace("|", "\\|").replace("\n", " ")
        verdict_cell = (r["verdict"] or "").replace("|", "\\|").replace("\n", " ")
        L.append(f"| {i} | {r['guorn_indicator']} | {r['bucket']} | {expr_cell} | "
                 f"{r['n_deployed_books']} | {st} | {verdict_cell} |")
    LOG_MD.write_text("\n".join(L), encoding="utf-8")
    print(f"[campaign] deployed-20 web-validatable factors: {len(rows)} ({done} done, {len(rows)-done} pending)")
    print(f"[campaign] wrote {LOG_JSON.name} + {LOG_MD.name}")


if __name__ == "__main__":
    main()
