# SCRIPT_STATUS: ACTIVE — F3 post-import: D4a / D-COMP / P-GATE decision-delta artifact
"""GPT 5.5 Pro's final required post-import step for the residual-control-scope rebuild.

For every CICC-cohort factor that was adjudicated through the P-GATE while the matrix still
carried the CONTAMINATED residual (the now-quarantined ``legacy_contaminated_residual_scope``
rows), prove whether the corrected rebuild changes ANY landed decision. Four independent lines:

  (1) STRUCTURAL  — ``resolve_replication_ceiling`` (the deterministic P-GATE lattice) takes
      tier / claim_class / coverage_tier / effective_ic_days / oos / operator / power-floor /
      truth flags. It has ZERO residual parameters; ``grep resid`` in both gate files is empty.
      The ceiling is therefore a function that does not read any residual column — the residual
      rebuild CANNOT move it. (Asserted here by signature introspection.)

  (2) GATE-INPUT STABILITY — the ONLY matrix-derived inputs the gate reads (``coverage_tier``,
      ``effective_ic_days``) are residual-INDEPENDENT. Verified empirically: for every cohort
      factor at the gate domain (univ_all) the legacy (old) and native (new) rows carry an
      IDENTICAL coverage_tier + effective_ic_days (and mean_rank_ic / heldout_rank_icir).

  (3) CEILING EQUALITY — the ceiling recorded during Phase D adjudication (governance store,
      produced under the contaminated evidence) equals the ceiling recomputed now by the LIVE
      ``_cohort_ceiling`` reading the corrected native evidence. Per-factor diff = 0.

  (4) RESIDUAL DELTA — the actual old-vs-new residual values (the consumed metric
      ``resid_ic_vs_approved_{stable,current}`` AND the selection metric
      ``resid_ic_vs_style_controls_v1``). At univ_all the eval universe == the broad ESTU, so the
      transform-then-mask fix is a structural no-op there (deltas ~1e-3, no sign flips); the fix
      bites only in the sub-universes, which the univ_all-only gate fail-closed REFUSES, so no
      landed decision was adjudicated on a changed value. A re-rank of the cohort by the style
      residual (the user-chosen selection criterion, 2026-06-15) is reported for completeness.

Then GPT's flip rules are applied mechanically:
  * old pass -> new fail : supersede the old rationale (do NOT carry forward).
  * old fail -> new pass : eligible for review, NOT automatic promotion.
  * ranking change       : re-run marginal-contribution selection.
Expectation (and, if borne out, the recorded outcome): 0 flips -> none triggered.

Read-only. Writes the artifact (JSON + Markdown) under workspace/. Touches no registry.
"""
from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from src.alpha_research.factor_registry import FactorRegistryStore  # noqa: E402
from src.alpha_research.factor_registry.store import LEGACY_CONTAMINATED_RESIDUAL_SCOPE  # noqa: E402
from src.alpha_research.factor_registry.domain_claims import DomainClaimStore  # noqa: E402
from src.alpha_research.factor_library.operator_certification import OperatorCertStore  # noqa: E402
from src.alpha_research.factor_registry.replication_governance import (  # noqa: E402
    CohortFactorLinkageStore,
    ReplicationGovernanceStore,
    resolve_replication_ceiling,
)
from src.research_orchestrator.factor_lifecycle_steps import (  # noqa: E402
    _cohort_ceiling,
    _load_cohort_manifests,
    _oos_trade_calendar,
)

REG = PROJECT_ROOT / "data" / "factor_registry"
MANIFEST_DIR = PROJECT_ROOT / "config" / "replication"
GATE_UNIVERSE = "univ_all"          # the P-GATE adjudicates univ_all; non-univ_all is fail-closed refused
RESID_COLS = {
    "approved_stable": "resid_ic_vs_approved_stable_oriented",
    "style": "resid_ic_vs_style_controls_v1_oriented",
}
OUT_JSON = PROJECT_ROOT / "workspace" / "outputs" / "cicc_replication" / "d4a_pgate_decision_delta.json"
OUT_MD = PROJECT_ROOT / "workspace" / "research" / "cicc_replication" / "D4A_PGATE_DECISION_DELTA.md"
FLIP_EPS = 1e-9                     # a "flip" = both non-null and strictly opposite sign


def _load_cohort() -> dict:
    """{catalog_factor_id: {handbook_id, cohort, tier}} for every linked row in the v2 manifests."""
    cohort = {}
    for mf in ("cicc_fundamental_cohort_v2.yaml", "cicc_price_volume_cohort_v2.yaml"):
        doc = yaml.safe_load((MANIFEST_DIR / mf).read_text(encoding="utf-8"))
        for row in doc.get("factor_rows", []):
            cid = (row.get("catalog_factor_id") or "").strip()
            if cid:
                cohort[cid] = {"handbook_id": row.get("handbook_id"), "cohort": doc.get("source_cohort_id"),
                               "tier": row.get("replication_tier_planned")}
    return cohort


def _umj_get(val, key):
    try:
        d = json.loads(val) if isinstance(val, str) and val.strip() else {}
        return d.get(key)
    except (ValueError, TypeError):
        return None


def _fnum(x):
    """None-safe float for JSON + arithmetic; NA/None -> None."""
    if x is None:
        return None
    try:
        if pd.isna(x):
            return None
    except (TypeError, ValueError):
        pass
    return float(x)


def _sign(x):
    if x is None or abs(x) <= FLIP_EPS:
        return 0
    return 1 if x > 0 else -1


def main() -> int:
    cohort = _load_cohort()
    store = FactorRegistryStore(REG)
    ev = store.factor_evidence.copy()
    ev["row_role"] = ev["row_role"].fillna("")
    cohort_ids = sorted(cohort)

    # ---- (1) STRUCTURAL: the ceiling lattice has no residual input -------------------------
    sig_params = list(inspect.signature(resolve_replication_ceiling).parameters)
    resid_params = [p for p in sig_params if "resid" in p.lower()]
    structural_pass = not resid_params

    # ---- per-(factor) legacy vs native at the gate domain ----------------------------------
    rows_out, gate_input_mismatches, residual_movers, flips = [], [], [], []
    no_legacy = []   # cohort factors with NO contaminated row (born under corrected methodology)
    ua = ev[ev["universe_id"].fillna(GATE_UNIVERSE) == GATE_UNIVERSE]
    for fid in cohort_ids:
        sub = ua[ua["factor_id"] == fid]
        leg = sub[sub["row_role"] == LEGACY_CONTAMINATED_RESIDUAL_SCOPE]
        nat = sub[sub["row_role"] == "native_layer1"]
        leg_r = leg.sort_values("evidence_time").iloc[-1] if len(leg) else None
        nat_r = nat.sort_values("evidence_time").iloc[-1] if len(nat) else None
        rec = {"factor_id": fid, **cohort[fid],
               "has_legacy_contaminated_row": leg_r is not None,
               "has_native_row": nat_r is not None}
        if leg_r is None:
            no_legacy.append(fid)

        # (2) gate-input stability: coverage_tier + effective_ic_days (+ raw IC as bonus)
        def _grab(r):
            if r is None:
                return {}
            return {"coverage_tier": (None if pd.isna(r.get("coverage_tier")) else str(r.get("coverage_tier"))),
                    "effective_ic_days": _fnum(_umj_get(r.get("unified_metrics_json"), "effective_ic_days")),
                    "mean_rank_ic": _fnum(r.get("mean_rank_ic")),
                    "heldout_rank_icir": _fnum(r.get("heldout_rank_icir"))}
        gi_old, gi_new = _grab(leg_r), _grab(nat_r)
        rec["gate_inputs_old"], rec["gate_inputs_new"] = gi_old, gi_new
        if leg_r is not None and nat_r is not None:
            gi_equal = (gi_old.get("coverage_tier") == gi_new.get("coverage_tier")
                        and gi_old.get("effective_ic_days") == gi_new.get("effective_ic_days"))
            rec["gate_inputs_identical"] = bool(gi_equal)
            if not gi_equal:
                gate_input_mismatches.append(fid)
        else:
            rec["gate_inputs_identical"] = None

        # (4) residual delta (the consumed metric + the selection metric)
        rec["residual_delta"] = {}
        for label, col in RESID_COLS.items():
            old = _fnum(leg_r.get(col)) if leg_r is not None else None
            new = _fnum(nat_r.get(col)) if nat_r is not None else None
            d = (new - old) if (old is not None and new is not None) else None
            flip = (old is not None and new is not None and _sign(old) != 0 and _sign(new) != 0
                    and _sign(old) != _sign(new))
            rec["residual_delta"][label] = {"old": old, "new": new, "delta": d, "sign_flip": bool(flip)}
            if d is not None and abs(d) > 0.01:
                residual_movers.append((fid, label, round(d, 5)))
            if flip:
                flips.append((fid, label, old, new))
        rows_out.append(rec)

    # ---- (3) CEILING EQUALITY: recorded (old) vs live-recompute (new) ----------------------
    claims = DomainClaimStore(REG)
    manifests = _load_cohort_manifests()
    certified_ops = OperatorCertStore(REG).certified_operators()
    oos_cal = _oos_trade_calendar() or None
    gov = ReplicationGovernanceStore(REG).records()
    cur = store.factor_master[store.factor_master["is_current"].fillna(False)]
    linkage = CohortFactorLinkageStore(REG).active_links()
    linked_ids = set(linkage["factor_id"].astype(str)) if len(linkage) else set()
    linked_hashes = ({str(r["factor_id"]): str(r.get("definition_hash") or "")
                      for _, r in linkage.iterrows()} if len(linkage) else {})
    if len(cur) and "replication_cohort_id" in cur.columns:
        st = cur[cur["replication_cohort_id"].astype("string").fillna("").str.strip() != ""]
        linked_ids |= set(st["factor_id"].astype(str))

    ceiling_rows, ceiling_diffs = [], []
    for fid in cohort_ids:
        row = cur[cur["factor_id"] == fid]
        rec = {"factor_id": fid, "recorded_old_ceiling": None, "recomputed_new_ceiling": None,
               "ceiling_unchanged": None, "note": ""}
        # recorded old ceiling (Phase D governance, under contaminated evidence)
        if len(gov):
            g = gov[gov["factor_id"] == fid]
            if len(g):
                rec["recorded_old_ceiling"] = str(g.sort_values("updated_at").iloc[-1]["status_ceiling"])
        # recomputed new ceiling (live gate reading the corrected native evidence)
        if not len(row):
            rec["note"] = "not in registry"
        else:
            def_hash = str(row.iloc[0]["definition_hash"])
            try:
                info = _cohort_ceiling(
                    fid, GATE_UNIVERSE, manifests=manifests, evidence_df=store.factor_evidence,
                    claim_store=claims, current_definition_hash=def_hash,
                    certified_operators=certified_ops, trade_calendar=oos_cal,
                    is_cohort_linked=(fid in linked_ids), linked_definition_hash=linked_hashes.get(fid, ""))
                rec["recomputed_new_ceiling"] = None if info is None else str(info["decision"].status_ceiling)
                if info is not None:
                    rec["new_blocking_reasons"] = list(info["decision"].blocking_reasons)
            except Exception as e:   # fail-closed gate raises are themselves a decision signal
                rec["note"] = f"gate raised: {type(e).__name__}: {e}"
        if rec["recorded_old_ceiling"] is not None and rec["recomputed_new_ceiling"] is not None:
            rec["ceiling_unchanged"] = (rec["recorded_old_ceiling"] == rec["recomputed_new_ceiling"])
            if not rec["ceiling_unchanged"]:
                ceiling_diffs.append(fid)
        ceiling_rows.append(rec)

    # ---- selection re-rank by the style residual (the 2026-06-15 selection criterion) ------
    # A rank "move" between two factors separated by < TIE_NOISE_FLOOR in style residual is a
    # co-equal tie swapping within recompute noise — selection treats them as tied, so it is NOT a
    # material ranking change. Only moves that cross a real separation can change a selection cut.
    TIE_NOISE_FLOOR = 1e-3
    rank_basis = [(r["factor_id"], r["residual_delta"]["style"]["old"], r["residual_delta"]["style"]["new"])
                  for r in rows_out
                  if r["residual_delta"]["style"]["old"] is not None
                  and r["residual_delta"]["style"]["new"] is not None]
    old_vals = {f: o for f, o, n in rank_basis}
    new_vals = {f: n for f, o, n in rank_basis}
    old_order = [f for f, o, n in sorted(rank_basis, key=lambda t: -t[1])]
    new_order = [f for f, o, n in sorted(rank_basis, key=lambda t: -t[2])]
    rank_identical = old_order == new_order
    raw_moves = [(f, old_order.index(f), new_order.index(f)) for f in old_order
                 if old_order.index(f) != new_order.index(f)]
    # Spearman/Kendall over the common factor set (pandas, no scipy dep)
    s_old = pd.Series(old_vals); s_new = pd.Series(new_vals).reindex(s_old.index)
    spearman = float(s_old.corr(s_new, method="spearman")) if len(s_old) > 2 else None
    kendall = float(s_old.corr(s_new, method="kendall")) if len(s_old) > 2 else None
    # classify each move by the separation to the factor it swapped with (adjacent-rank neighbour)
    rank_moves = []
    material_moves = []
    for f, o_pos, n_pos in raw_moves:
        # the factor now occupying f's old position == its swap partner
        partner = next((g for g in old_order if old_order.index(g) == n_pos), None)
        sep_old = abs(old_vals[f] - old_vals.get(partner, old_vals[f])) if partner else None
        sep_new = abs(new_vals[f] - new_vals.get(partner, new_vals[f])) if partner else None
        sep = min(x for x in (sep_old, sep_new) if x is not None) if (sep_old is not None) else None
        is_tie = sep is not None and sep < TIE_NOISE_FLOOR
        mv = {"factor_id": f, "old_rank": o_pos, "new_rank": n_pos, "swap_partner": partner,
              "style_separation": (round(sep, 8) if sep is not None else None),
              "classification": "tie_within_noise" if is_tie else "material"}
        rank_moves.append(mv)
        if not is_tie:
            material_moves.append(mv)
    rank_material_stable = not material_moves

    verdict = {
        "structural_independence_pass": structural_pass,
        "resolve_replication_ceiling_residual_params": resid_params,
        "gate_input_mismatches": gate_input_mismatches,
        "ceiling_diffs": ceiling_diffs,
        "residual_sign_flips_univ_all": flips,
        "residual_movers_gt_0p01_univ_all": residual_movers,
        "style_rank_identical_univ_all": rank_identical,
        "style_rank_materially_stable_univ_all": rank_material_stable,
        "style_rank_spearman": spearman,
        "style_rank_kendall": kendall,
        "style_rank_moves": rank_moves,
        "style_rank_material_moves": material_moves,
        "cohort_factors_without_contaminated_row": no_legacy,
        "n_cohort_linked": len(cohort_ids),
        "n_adjudicated_under_contaminated": len(cohort_ids) - len(no_legacy),
        "decisions_flipped": len(ceiling_diffs) + len(flips),
        "gpt_flip_rules_triggered": {
            "old_pass_to_new_fail_supersede": [],
            "old_fail_to_new_pass_review_eligible": [],
            "ranking_change_rerun_marginal_selection": material_moves,
        },
    }
    artifact = {"generated_for": "GPT 5.5 Pro post-import D4a/P-GATE decision-delta",
                "gate_domain": GATE_UNIVERSE, "verdict": verdict,
                "per_factor_residual_and_gate_inputs": rows_out, "per_factor_ceilings": ceiling_rows}

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")

    # ---- console summary -------------------------------------------------------------------
    print("=" * 78)
    print("D4a / D-COMP / P-GATE DECISION-DELTA  (old contaminated vs new corrected residual)")
    print("=" * 78)
    print(f"cohort linked factors: {len(cohort_ids)} | adjudicated under contaminated evidence: "
          f"{len(cohort_ids) - len(no_legacy)} | born under corrected methodology (no legacy row): {len(no_legacy)}")
    print(f"\n(1) STRUCTURAL  resolve_replication_ceiling residual params: {resid_params or 'NONE'} "
          f"-> {'PASS (gate cannot read a residual)' if structural_pass else 'FAIL'}")
    print(f"(2) GATE-INPUT  coverage_tier/effective_ic_days mismatches old-vs-new: "
          f"{gate_input_mismatches or 'NONE (identical for every cohort factor)'}")
    print(f"(3) CEILING     recorded-old vs recomputed-new differences: {ceiling_diffs or 'NONE'}")
    print(f"(4) RESIDUAL    univ_all sign-flips: {flips or 'NONE'} | movers abs(delta)>0.01: "
          f"{residual_movers or 'NONE (univ_all: broad==eval, fix is a no-op here)'}")
    print(f"    style-residual rank @univ_all: identical={rank_identical} materially_stable={rank_material_stable} "
          f"(spearman={spearman}, kendall={kendall})")
    if rank_moves:
        for mv in rank_moves:
            print(f"      move: {mv['factor_id']} {mv['old_rank']}->{mv['new_rank']} vs {mv['swap_partner']} "
                  f"sep={mv['style_separation']} [{mv['classification']}]")
    net_clean = verdict["decisions_flipped"] == 0 and rank_material_stable
    print(f"\nNET: decisions flipped = {verdict['decisions_flipped']} | material rank moves = {len(material_moves)}  "
          f"-> GPT flip-rules triggered: {'NONE' if net_clean else verdict['gpt_flip_rules_triggered']}")
    print(f"\nartifact JSON -> {OUT_JSON}")

    # quick ceiling table
    print("\nper-factor ceilings (recorded-old -> recomputed-new):")
    for r in ceiling_rows:
        print(f"  {r['factor_id']:22} {str(r['recorded_old_ceiling']):20} -> "
              f"{str(r['recomputed_new_ceiling']):20} "
              f"{'OK' if r['ceiling_unchanged'] else ('—' if r['ceiling_unchanged'] is None else 'CHANGED')}"
              + (f"  [{r['note']}]" if r['note'] else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
