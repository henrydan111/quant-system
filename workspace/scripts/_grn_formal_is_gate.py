# SCRIPT_STATUS: ACTIVE — 门1 grn 成长质量因子 IS-only walk-forward gate (draft->candidate), dry-run default
"""果仁复刻因子 → official strategy book 的门1:把一组 grn_* 成长质量因子跑过 factor_lifecycle 的
IS-only 走查门(与 orchestrator 的 handle_factor_lifecycle_walk_forward BIT-IDENTICAL 路径:同一个
run_is_walk_forward + per_factor_field_eligible),看哪些达到 candidate。

因子集 = 高保真 成长簇(#1/#2/#6)蒸馏出的"果仁成长质量核心",全部是 2026-07-03 入库的 grn_* draft:
  grn_core_profit_qgr  (核心利润单季同比, 越大越好)
  grn_dedt_qgr         (扣非利润单季同比)
  grn_roe_ttm_diff_q   (ROE-TTM 环比改善 — 已知选股级脆弱, 让 IS-gate 判)
  grn_shares_avg_gr    (股本均值同比 = 低稀释, 越小越好)
  grn_ato_diff_py      (总资产周转率改善)
  grn_true_debt_assets (真实负债资产率 = 低杠杆, 越小越好)

Provenance = a_priori(果仁书 IS 选出, 2021+ 保持 SEALED)→ factor_origin='a_priori', IS 窗 2010-2020,
用 yearly-blocked sign-consistency, 不需要 generated-heldout。

默认 dry-run(只报判定, 不落库)。--live 需 GPT 跨审后由用户单独执行(E1x 同款纪律)。
NON-DESTRUCTIVE 除非 --live。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

sys.stdout.reconfigure(encoding="utf-8")

FACTORS = [
    "grn_core_profit_qgr",
    "grn_dedt_qgr",
    "grn_roe_ttm_diff_q",
    "grn_shares_avg_gr",
    "grn_ato_diff_py",
    "grn_true_debt_assets",
]
IS_START, IS_END = "2010-01-01", "2020-12-31"
OUT = ROOT / "workspace" / "outputs" / "guorn_formal"
OUT.mkdir(parents=True, exist_ok=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizon", type=int, default=20)
    a = ap.parse_args()

    from src.alpha_research.factor_library.catalog import get_factor_catalog
    from src.alpha_research.factor_lifecycle.walk_forward_validation import run_is_walk_forward
    from src.alpha_research.walk_forward import TimeSplit
    from src.research_orchestrator.factor_lifecycle_steps import per_factor_field_eligible

    full = get_factor_catalog(include_new_data=True)
    catalog = {f: full[f] for f in FACTORS}
    missing = [f for f in FACTORS if f not in full]
    if missing:
        raise SystemExit(f"factors absent from catalog: {missing}")

    # field eligibility at formal_validation (fail-closed) — the SAME check the gate applies
    field_eligible = per_factor_field_eligible(FACTORS, stage="formal_validation")
    print("[field-eligibility @ formal_validation]")
    for f in FACTORS:
        print(f"  {f:24} {field_eligible[f]}")

    # 2021+ stays SEALED — the a_priori path only reads is_start..is_end; oos_* satisfies the invariant
    ts = TimeSplit(is_start=IS_START, is_end=IS_END, oos_start="2021-01-01", oos_end="2026-02-27")

    print(f"\n[IS-gate] run_is_walk_forward a_priori {IS_START}..{IS_END} horizon={a.horizon} "
          f"(compute over full universe — this is the slow leg)", flush=True)
    result = run_is_walk_forward(
        catalog=catalog, time_split=ts, horizon=a.horizon, factor_origin="a_priori",
        field_eligible=field_eligible,
    )

    print(f"\n[VERDICTS] evidence_kind={result.evidence_kind} "
          f"effective_eval_end={result.effective_eval_end}")
    print(f"  {'factor':24}{'status':>11}{'heldout_icir':>14}{'sign_consist':>14}{'n_blocks':>10}")
    rows = []
    for r in result.rows:
        rows.append(dict(r))
        hv = r.get("heldout_rank_icir")
        sc = r.get("sign_consistency")
        hs = f"{hv:+.4f}" if isinstance(hv, (int, float)) else str(hv)
        ss = f"{sc:.3f}" if isinstance(sc, (int, float)) else str(sc)
        print(f"  {r.get('factor',''):24}{r.get('status',''):>11}{hs:>14}{ss:>14}"
              f"{str(r.get('n_heldout_blocks', r.get('n_valid',''))):>10}")
    cand = [r["factor"] for r in result.rows if r.get("status") == "candidate"]
    print(f"\n  → candidate: {cand}")
    print(f"  → stay draft: {[r['factor'] for r in result.rows if r.get('status') != 'candidate']}")

    (OUT / "grn_is_gate_result.json").write_text(
        json.dumps({"is_window": [IS_START, IS_END], "horizon": a.horizon,
                    "evidence_kind": result.evidence_kind, "field_eligible": field_eligible,
                    "rows": rows, "candidate": cand}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"\n[saved] {OUT / 'grn_is_gate_result.json'}")
    print("[note] DRY-RUN — no registry write. --live promotion needs GPT cross-review + user go (E1x discipline).")


if __name__ == "__main__":
    main()
