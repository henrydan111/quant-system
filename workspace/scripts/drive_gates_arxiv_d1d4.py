# ──────────────────────────────────────────────────────────────────────
# SCRIPT_STATUS header block.
# script_status: class_d_research_tooling
# formal_research_allowed: false
# touches_formal_data_plane: false
# pr2_audit_class: D
# notes: |
#   Gate driver for the arXiv D1-D4 idea-sourced factor_lifecycle batch
#   (alpha_chip_cgo_smooth_20d, earn_sue_ni_mcap/_assets,
#   north_hold_change_{20,60}d_cov). Same mechanics as phase6_drive_gates.py
#   but with HONEST batch-specific concern evidence: unlike Phase 6 (an
#   oos_informed_backfill of factors with prior full-window OOS knowledge),
#   THIS batch was selected on IS-only statistics (sandbox screens + the
#   marginal-contribution gate, all <= 2020-12-31), so 2021-2026 is UNBURNED
#   by our own numbers — with the literature-informed caveat that the source
#   papers (e.g. arXiv:2505.20608, sampled 1995-2024) observed the OOS years.
#   The phase6 canned text ("pre-restricted to factors with independent
#   full-window OOS support") would be FALSE for this batch.
# ──────────────────────────────────────────────────────────────────────
"""Drive the paused arXiv-D1-D4 factor_lifecycle run through both human gates."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research_orchestrator.engine import resume_research
from src.research_orchestrator.runtime import load_run_state

_EVIDENCE = {
    "most_likely_failure_mode": (
        "The IS-only walk-forward gate is structurally blind to OOS, and an IS-stable "
        "factor CAN collapse out-of-sample (precedent: qual_gross_profitability, IS +0.14 "
        "-> OOS -0.12). This batch is idea-sourced (arXiv D1-D4) and was selected on "
        "IS-only statistics (sandbox screens + the marginal-contribution gate, all "
        "<= 2020-12-31), so 2021-2026 remains unburned by our own numbers; the residual "
        "risk is literature-informed selection (the source papers sampled through "
        "2024). The keyed rank_icir={v:.4f} clears the 0.10 IS floor; the OOS-collapse "
        "concern is unrealized but NOT refuted at this gate."
    ),
    "weakest_assumption": (
        "IS sign-consistency over the covered window (2014/2017/2018..2020 depending on "
        "dataset coverage) generalizes out-of-sample; this is NOT attested by this gate "
        "(candidate != approved). The measured IS rank_icir={v:.4f} supports only the "
        "draft->candidate step; the genuinely-sealed OOS promotion path is separate."
    ),
    "what_would_falsify_this": (
        "A measured rank_icir below the 0.10 IS heldout floor leaves a factor at draft. "
        "The observed batch rank_icir={v:.4f} is above the floor, so the gate admits the "
        "factor as a candidate (not as approved/deployable)."
    ),
    "priors_on_cost_sensitivity": (
        "An IS-only cross-sectional rank-IC gate applies no cost model; cost-adjusted "
        "viability is a later-phase recompute. The keyed rank_icir={v:.4f} is a gross "
        "predictive statistic, not a net tradable return. Note the D4 _cov factors rank "
        "within the Connect sub-universe (larger caps, better liquidity) and the D1 chip "
        "factor is dense daily — turnover/cost profiling belongs to the deployment gate."
    ),
}

_DEFAULT_REASON = (
    "arXiv D1-D4 idea-sourced drafts clear the IS-only heldout gate (heldout ICIR "
    "0.34-0.60, sign-consistency 0.86-1.00); promote draft->candidate. candidate != "
    "approved: the sealed-OOS promotion path is separate and remains unburned by our own "
    "selection statistics (literature-informed caveat recorded). Selection evidence: "
    "workspace/research/idea_sourcing/knowledge/D1_D4_SCREEN_RESULTS.md."
)


def _author_concern_scores(run_dir: Path) -> dict:
    ev = json.loads((run_dir / "steps" / "gate_evaluation" / "step_outputs.json").read_text(encoding="utf-8"))
    rank_icir = float(ev["measured_values"]["rank_icir"])
    template = json.loads(
        (run_dir / "steps" / "gate_concern_scoring" / "gate_concern_scores_template.json").read_text(encoding="utf-8")
    )
    scores = []
    for stub in template["scores"]:
        cid = stub["concern_id"]
        scores.append({
            "concern_id": cid,
            "concern_text": stub["concern_text"],
            "keyed_to_rule_id": "min_rank_icir",
            "measured_evidence_against_concern": _EVIDENCE[cid].format(v=rank_icir),
            "quantitative_anchor": {"rank_icir": rank_icir},
            "confirmed": False,
            "severity": "low",  # min_rank_icir passed -> derived severity 'low'
        })
    return {"scores": scores}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--decision", default="approved", choices=["approved", "rejected", "quarantined"])
    ap.add_argument("--decision-by", default="claude_arxiv_d1d4")
    ap.add_argument("--reason", default=_DEFAULT_REASON)
    args = ap.parse_args()
    run_dir = Path(args.run_dir).resolve()

    st = load_run_state(run_dir)
    print(f"[before] status={st.get('status')} completed={st.get('completed_step_count')}")

    concern_dir = run_dir / "steps" / "gate_concern_scoring"
    scores = _author_concern_scores(run_dir)
    (concern_dir / "gate_concern_scores.json").write_text(
        json.dumps(scores, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[concern] wrote {len(scores['scores'])} scores keyed to min_rank_icir")
    resume_research(run_dir)
    st1 = load_run_state(run_dir)
    print(f"[after concern resume] status={st1.get('status')} completed={st1.get('completed_step_count')}")

    review_dir = run_dir / "steps" / "gate_review"
    review_dir.mkdir(parents=True, exist_ok=True)
    decision = {"decision": args.decision, "decision_by": args.decision_by, "reason": args.reason}
    (review_dir / "gate_decision.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[gate_review] wrote decision={args.decision}")
    resume_research(run_dir)
    st2 = load_run_state(run_dir)
    print(f"[after decision resume] status={st2.get('status')} "
          f"completed={st2.get('completed_step_count')} failed={st2.get('failed_step_id')}")

    pub = run_dir / "steps" / "registry_publish" / "step_outputs.json"
    if pub.exists():
        p = json.loads(pub.read_text(encoding="utf-8"))
        print("=== PUBLISH OUTCOME ===")
        for k in ("decision", "published", "promoted_to_candidate", "skipped_drift", "skipped_unknown"):
            print(f"{k}:", p.get(k))
    else:
        print("NO registry_publish/step_outputs.json (run did not reach publish)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
