# ──────────────────────────────────────────────────────────────────────
# PR 7 of 2026-05-26 freeze plan — SCRIPT_STATUS header block.
# script_status: historical_investigation
# formal_research_allowed: false
# deployment_target: joinquant_attribution_only
# requires_provider_manifest: false
# requires_preload_strict: false
# pr2_audit_class: C
# notes: |
#   Mechanically applies the PREDECLARED OOS top-set selection rule
#   (oos_topset_selection_rule.md, frozen before the Wave-2 screen) to the
#   Wave-2 IS screen. Deterministic — no post-hoc judgment except the single
#   logged redundancy prune the rule explicitly allows. Writes the frozen
#   top-set JSON + a per-factor selection-trace markdown. Read-only w.r.t.
#   registry/catalog. Run BEFORE the sealed OOS.
# ──────────────────────────────────────────────────────────────────────
"""Apply the frozen OOS top-set selection rule to the Wave-2 IS screen."""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXP = PROJECT_ROOT / "workspace" / "research" / "factor_expansion"
MERGED_CSV = EXP / "factor_candidates_merged.csv"
IS_REPORT = EXP / "screening_is_50" / "screening_is_report.csv"
IS_PARQUET = EXP / "screening_is_50" / "screening_is_results.parquet"
FROZEN_JSON = EXP / "oos_frozen_topset.json"
TRACE_MD = EXP / "oos_frozen_topset.md"

# Frozen rule thresholds (verbatim from oos_topset_selection_rule.md — DO NOT EDIT
# after seeing IS results; these are transcribed from the pre-committed rule).
STRUCTURAL_ZERO_EXCLUDE = {"acc_goodwill_ratio", "acc_noa_scaled"}
T1_ICIR, T1_LS, T1_MDD = 0.30, 1.5, 2.0       # Tier 1: icir>=, ls_sharpe>=, ls_max_dd<=(%)
T2_ICIR, T2_LS = 0.25, 0.8                     # Tier 2: icir>=, ls_sharpe>=
SHORTSIDE_ICIR = 0.30                          # |icir|>= AND opposite-signed LS -> short-side, exclude
HARD_CAP = 15

# Redundancy clusters (rule's only discretionary step; keep higher ls_sharpe).
# Declared here from the economic-concept groupings; the prune is logged.
REDUNDANCY_CLUSTERS = [
    {"grow_revenue_yoy_accel_q", "grow_total_revenue_yoy_accel_q"},  # revenue accel (gross vs total)
    {"grow_revenue_yoy_q", "grow_total_revenue_yoy_q"},              # revenue level YoY
]


def main() -> int:
    formal = {
        r["name"]
        for r in csv.DictReader(open(MERGED_CSV, encoding="utf-8"))
        if r["formal_eligible"] == "yes"
    }
    rep = pd.read_csv(IS_REPORT, index_col=0)
    df = pd.read_parquet(IS_PARQUET)
    df.index = rep.index
    df = df[["rank_icir_20d", "ls_sharpe", "ls_max_dd", "monotonic", "grade"]].copy()
    for c in ["rank_icir_20d", "ls_sharpe", "ls_max_dd"]:
        df[c] = df[c].astype(float)

    trace = []  # (name, decision, reason, icir, ls, mdd)
    eligible = {}

    for name, r in df.iterrows():
        icir, ls, mdd = r["rank_icir_20d"], r["ls_sharpe"], r["ls_max_dd"]
        if name not in formal:
            trace.append((name, "EXCLUDE", "not formal_eligible", icir, ls, mdd))
            continue
        if name in STRUCTURAL_ZERO_EXCLUDE:
            trace.append((name, "EXCLUDE", "structural-zero-pending (Round-6)", icir, ls, mdd))
            continue
        # short-side: high |IC| but opposite-signed LS Sharpe
        if abs(icir) >= SHORTSIDE_ICIR and (icir * ls) < 0:
            trace.append((name, "EXCLUDE", f"short-side (|icir|={abs(icir):.2f}, LS sign opposite)", icir, ls, mdd))
            continue
        eligible[name] = (icir, ls, mdd)

    # Tier 1
    tier1 = {n: v for n, v in eligible.items()
             if v[0] >= T1_ICIR and v[1] >= T1_LS and v[2] <= T1_MDD}
    # Tier 2 (fill by descending ls_sharpe up to cap)
    tier2_pool = {n: v for n, v in eligible.items()
                  if n not in tier1 and v[0] >= T2_ICIR and v[1] >= T2_LS}
    selected = dict(tier1)
    for n, v in sorted(tier2_pool.items(), key=lambda kv: kv[1][1], reverse=True):
        if len(selected) >= HARD_CAP:
            break
        selected[n] = v

    # Redundancy prune (logged) — keep higher ls_sharpe within each cluster
    pruned = []
    for cluster in REDUNDANCY_CLUSTERS:
        present = [n for n in cluster if n in selected]
        if len(present) > 1:
            keep = max(present, key=lambda n: selected[n][1])
            for n in present:
                if n != keep:
                    pruned.append((n, keep))
                    del selected[n]

    # Hard cap by ls_sharpe
    if len(selected) > HARD_CAP:
        keep = dict(sorted(selected.items(), key=lambda kv: kv[1][1], reverse=True)[:HARD_CAP])
        for n in list(selected):
            if n not in keep:
                trace.append((n, "EXCLUDE", "over hard-cap 15 (lower ls_sharpe)", *selected[n]))
        selected = keep

    # finalize trace for eligible-but-not-selected
    for n, v in eligible.items():
        if n not in selected and not any(t[0] == n and t[1] == "EXCLUDE" for t in trace):
            reason = "eligible but below Tier1/Tier2 thresholds"
            if any(n == p[0] for p in pruned):
                reason = f"redundancy-pruned (kept {[k for x,k in pruned if x==n][0]})"
            trace.append((n, "exclude", reason, *v))
    for n in selected:
        v = selected[n]
        tier = "Tier1" if (v[0] >= T1_ICIR and v[1] >= T1_LS and v[2] <= T1_MDD) else "Tier2"
        trace.append((n, f"SELECT ({tier})", "passes frozen rule", *v))

    selected_sorted = sorted(selected.items(), key=lambda kv: kv[1][1], reverse=True)
    frozen = {
        "frozen_at": datetime.now().isoformat(timespec="seconds"),
        "rule": "workspace/research/factor_expansion/oos_topset_selection_rule.md",
        "is_screen": "screening_is_50",
        "frozen_topset": [n for n, _ in selected_sorted],
        "count": len(selected),
        "redundancy_pruned": [{"dropped": d, "kept": k} for d, k in pruned],
        "oos_run": "NOT YET RUN",
    }
    FROZEN_JSON.write_text(json.dumps(frozen, indent=2), encoding="utf-8")

    # selection-trace markdown
    lines = [
        "# Frozen OOS Top Set — selection trace (mechanical)",
        "",
        f"Generated {frozen['frozen_at']} by applying the PRE-COMMITTED rule "
        "(oos_topset_selection_rule.md) to the Wave-2 IS screen (screening_is_50).",
        "**OOS NOT YET RUN.** Rule was frozen before the screen; this trace is deterministic.",
        "",
        f"## Frozen top set ({len(selected)} factors)",
        "",
        "| Factor | Tier | ICIR_20d | LS Sharpe | LS MaxDD% |",
        "|---|---|---|---|---|",
    ]
    for n, v in selected_sorted:
        tier = "Tier1" if (v[0] >= T1_ICIR and v[1] >= T1_LS and v[2] <= T1_MDD) else "Tier2"
        lines.append(f"| `{n}` | {tier} | {v[0]:.3f} | {v[1]:.2f} | {v[2]:.2f} |")
    if pruned:
        lines += ["", "## Redundancy prune (logged discretionary step)", ""]
        for d, k in pruned:
            lines.append(f"- dropped `{d}` (kept `{k}` — higher LS Sharpe)")
    lines += ["", "## Full decision trace (all 50)", "",
              "| Factor | Decision | Reason | ICIR20 | LS | MDD% |", "|---|---|---|---|---|---|"]
    for name, dec, reason, icir, ls, mdd in sorted(trace, key=lambda t: (not t[1].startswith("SELECT"), t[0])):
        lines.append(f"| `{name}` | {dec} | {reason} | {icir:.3f} | {ls:.2f} | {mdd:.2f} |")
    TRACE_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"FROZEN {len(selected)} factors -> {FROZEN_JSON.name}")
    for n, v in selected_sorted:
        print(f"  {n:34s} ICIR20={v[0]:+.3f} LS={v[1]:+.2f} MDD={v[2]:.2f}")
    if pruned:
        print("redundancy pruned:", pruned)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
