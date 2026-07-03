# SCRIPT_STATUS: ACTIVE — grn 成长质量因子 draft->candidate IS-gate promotion (fresh a_priori), dry-run default
"""果仁复刻因子 → official book 的门1 --live 促进:把门1 IS-gate(`_grn_formal_is_gate.py`,现算
run_is_walk_forward a_priori 2010-2020)判定为 candidate 的 4 个成长质量因子 draft->candidate 落库。

与 E1x 促进(promote_e1a_is_candidates.py)同纪律,但因子无预算矩阵 → 用现算 IS 走查的存档
(grn_is_gate_result.json)作证据源,并 RE-VERIFY 每个判定可从存档指标复现(assign_candidate_status
bit-identical)。GPT §10 复审已过(compute-safety 修复 APPROVE 2026-07-03;本促进用户 go=(a))。

HARDENING(照 E1x,全 blocking):
  1. 现算存档的每个 candidate 行用真实门规则 assign_candidate_status(field_ok, icir, sc, evidence_kind)
     重算,必须仍判 candidate(存档未被篡改 / 门规则未漂移)。
  2. field_ok 走 canonical per_factor_field_eligible(stage='formal_validation')(非本地阈值)。
  3. ALL-OR-NONE:record_lifecycle_evidence 的 attached 必须 == 全部请求且无 drift/unknown。
  4. pre-status 必须全 draft(拒 candidate->candidate 覆写)。
  5. record_lifecycle_evidence 自身 fail-closed 重查 definition drift(registry hash == 当前 catalog hash)。

Provenance a_priori(2010-2020 IS 选,2021+ 保持 SEALED,NOT oos_informed_backfill)。
默认 dry-run(临时 registry 副本);--live 提交(先备份)。
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from src.alpha_research.factor_registry.store import FactorRegistryStore  # noqa: E402
from src.alpha_research.factor_lifecycle.status_rules import assign_candidate_status  # noqa: E402
from src.alpha_research.factor_lifecycle.walk_forward_validation import _expected_direction  # noqa: E402
from src.research_orchestrator.factor_lifecycle_steps import per_factor_field_eligible  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

RUN_ID = "grn_is_candidate_2010_2020"
EVIDENCE_CLASS = "a_priori"
IS_RESULT = PROJECT_ROOT / "workspace" / "outputs" / "guorn_formal" / "grn_is_gate_result.json"
PROV_DIR = PROJECT_ROOT / "workspace" / "research" / "idea_sourcing" / "guorn" / "grn_is_promotion"
# The 4 门1-passers (grn_is_gate_result.json candidate list) — coherent 成长质量核心
FACTORS = ["grn_core_profit_qgr", "grn_dedt_qgr", "grn_roe_ttm_diff_q", "grn_ato_diff_py"]


def _status(store, fid):
    cur = store.factor_master[store.factor_master["is_current"].fillna(False)]
    row = cur[cur["factor_id"] == fid]
    return str(row.iloc[0]["status"]) if len(row) else "MISSING"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="commit to the REAL registry (default: temp dry-run)")
    args = ap.parse_args()

    res = json.loads(IS_RESULT.read_text(encoding="utf-8"))
    evidence_kind = str(res.get("evidence_kind") or "a_priori")
    rows_by_f = {r["factor"]: r for r in res["rows"]}
    saved_candidates = set(res.get("candidate", []))
    if set(FACTORS) != saved_candidates:
        raise SystemExit(f"FACTORS {sorted(FACTORS)} != saved门1 candidate list {sorted(saved_candidates)} — "
                         "the IS-gate result changed; re-run _grn_formal_is_gate.py and reconcile before promoting.")

    field_elig = per_factor_field_eligible(FACTORS, stage="formal_validation")
    verdicts, report = [], []
    print(f"[门1 promotion] evidence_class={EVIDENCE_CLASS} evidence_kind={evidence_kind} "
          f"IS={res['is_window']} horizon={res.get('horizon')}")
    for fid in FACTORS:
        r = rows_by_f.get(fid)
        if r is None:
            raise SystemExit(f"{fid} absent from IS-gate rows")
        icir, sc = r.get("heldout_rank_icir"), r.get("sign_consistency")
        fok = bool(field_elig.get(fid, False))
        # (1)+(2) RE-VERIFY the candidate verdict from the saved metrics via the REAL gate rule
        status, reason = assign_candidate_status(fok, icir, sc, evidence_kind=evidence_kind)
        if status != "candidate":
            raise SystemExit(f"{fid}: re-verified gate rule says {status!r} ({reason}) — NOT candidate; "
                             f"refuse promotion (icir={icir} sign={sc} field_ok={fok}).")
        direction = _expected_direction(icir)
        verdicts.append({"factor": fid, "heldout_rank_icir": icir, "sign_consistency": sc,
                         "n_heldout_blocks": r.get("n_heldout_blocks"), "universe_id": "univ_all",
                         "effective_start": res["is_window"][0], "effective_end": res["is_window"][1],
                         "expected_direction": direction})
        report.append({"factor": fid, "heldout_rank_icir": icir, "sign_consistency": sc,
                       "expected_direction": direction, "field_ok": fok})
        print(f"  {fid:22} ICIR={icir:+.4f} sign={sc:.2f} dir={direction} field_ok={fok} → candidate ✓")
    expected = {v["factor"] for v in verdicts}

    # ── registry target (temp copy unless --live) ──
    if args.live:
        registry_dir = PROJECT_ROOT / "data" / "factor_registry"
        bkp = PROJECT_ROOT / "data" / "backups" / f"factor_registry_grn_promote_{datetime.now():%Y%m%d_%H%M%S}"
        bkp.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(registry_dir, bkp)
        print(f"\n[live] backup → {bkp}")
    else:
        tmp = Path(tempfile.mkdtemp(prefix="grn_promote_dryrun_"))
        shutil.copytree(PROJECT_ROOT / "data" / "factor_registry", tmp / "factor_registry")
        registry_dir = tmp / "factor_registry"
        print(f"\ndry-run registry copy: {registry_dir}")

    store = FactorRegistryStore(registry_dir)
    pre_status = {fid: _status(store, fid) for fid in FACTORS}
    bad = {fid: st for fid, st in pre_status.items() if st != "draft"}
    if bad:
        raise SystemExit(f"(4) expected ALL requested factors at 'draft'; got {bad} (refuse overwrite).")

    out = store.record_lifecycle_evidence(
        run_id=RUN_ID, verdicts=verdicts, evidence_class=EVIDENCE_CLASS, source_run_dir=str(PROV_DIR))
    attached = set(out["attached"])
    print(f"\nrecord_lifecycle_evidence: attached={sorted(attached)} "
          f"skipped_drift={out['skipped_drift']} skipped_unknown={out['skipped_unknown']}")
    if attached != expected or out["skipped_drift"] or out["skipped_unknown"]:
        raise SystemExit(f"(3) evidence attach INCOMPLETE — attached={sorted(attached)} "
                         f"expected={sorted(expected)} drift={out['skipped_drift']} "
                         f"unknown={out['skipped_unknown']} — refuse (all-or-none).")

    promoted = []
    for v in verdicts:
        fid = v["factor"]
        store.set_status(factor_id=fid, status="candidate",
                         reason=(f"grn factor_lifecycle IS-heldout gate ({evidence_kind}; heldout "
                                 f"ICIR={v['heldout_rank_icir']:+.3f}, sign={v['sign_consistency']:.2f})"),
                         source_run_id=RUN_ID)
        store.set_expected_direction(factor_id=fid, expected_direction=v["expected_direction"])
        promoted.append(fid)
    assert set(promoted) == expected, f"promoted {sorted(promoted)} != {sorted(expected)}"
    if args.live:
        store.save()
        print("store.save() committed to disk")

    post_status = {fid: _status(store, fid) for fid in FACTORS}
    print("\nstatus transitions:")
    for fid in FACTORS:
        print(f"  {fid:22} {pre_status[fid]} -> {post_status[fid]}")

    PROV_DIR.mkdir(parents=True, exist_ok=True)
    prov = {
        "run_id": RUN_ID, "generated_at": datetime.now().isoformat(timespec="seconds"),
        "live": bool(args.live), "evidence_class": EVIDENCE_CLASS, "evidence_kind": evidence_kind,
        "is_window": res["is_window"], "horizon": res.get("horizon"),
        "mechanism": ("FRESH run_is_walk_forward(factor_origin='a_priori') over 2010-2020 full universe "
                      "(_grn_formal_is_gate.py, bit-identical to orchestrator handle_factor_lifecycle_"
                      "walk_forward); verdicts re-verified via assign_candidate_status(field_ok,...)."),
        "gate_authorization": ("User authorized 'promote the 门1 IS-passers' (2026-07-03, option (a)) after "
                               "GPT §10 APPROVE of the compute-safety fix. Writing formal IS evidence + "
                               "set_status(candidate) IS the human gate."),
        "oos_status": ("a_priori IS-selection on 2010-2020 only; 2021+ UNBURNED/sealed. Under v1.4, candidate "
                       "is TERMINAL (factor-level approved retired); official book = book-level seal (v1.4 PR3)."),
        "compute_safety": ("v2 cross-dataset broadcast fix (commit 34de062) verified compute-clean on the "
                           "2011-H1 young-stock window; grn_roe/grn_ato promoted here are v2."),
        "hardening_guards": ["re-verify assign_candidate_status(field_ok)", "all-or-none attach",
                             "record_lifecycle_evidence definition-drift fail-closed", "pre-status==draft",
                             "saved-candidate-set == FACTORS"],
        "promoted": promoted, "verdicts": report,
        "recorder_result": {k: out[k] for k in ("attached", "skipped_drift", "skipped_unknown")},
    }
    (PROV_DIR / f"promotion_{'live' if args.live else 'dryrun'}.json").write_text(
        json.dumps(prov, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n[prov] {PROV_DIR / ('promotion_live.json' if args.live else 'promotion_dryrun.json')}")
    if not args.live:
        print("dry-run complete — real registry untouched. Re-run with --live to commit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
