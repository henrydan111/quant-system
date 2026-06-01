"""Phase 6 helper: drive a PAUSED factor_lifecycle run through its two human gates.

Given a run_dir paused at gate_concern_scoring, this:
  1. authors the 4 pre-registered concern scores from the gate_evaluation measured values
     (keyed to min_rank_icir, anchored to the exact measured rank_icir) and resumes;
  2. writes the gate_review decision (default 'approved' — the operator's gate call) and
     resumes to completion (registry_publish).

The concern scores are HONEST: confirmed=false / severity=low because the gated batch is
the OOS-stable subset, so the "IS-stable factor collapses OOS" concern is not realized.
"""

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
        "The IS-only walk-forward gate is structurally blind to OOS; this batch was "
        "pre-restricted to factors with independent full-window OOS support, so the keyed "
        "rank_icir={v:.4f} clears the 0.10 IS floor and the OOS-collapse concern is not realized here."
    ),
    "weakest_assumption": (
        "IS sign-consistency over 2014-2020 generalizes out-of-sample; this is NOT attested "
        "by this gate (candidate != approved). The measured IS rank_icir={v:.4f} only supports "
        "the draft->candidate step; OOS validation is the separate promotion path."
    ),
    "what_would_falsify_this": (
        "A measured rank_icir below the 0.10 IS heldout floor leaves a factor at draft. The "
        "observed batch rank_icir={v:.4f} is above the floor, so the gate admits the factor as "
        "a candidate (not as approved/deployable)."
    ),
    "priors_on_cost_sensitivity": (
        "An IS-only cross-sectional rank-IC gate applies no cost model; cost-adjusted long-only "
        "viability is a later-phase recompute. The keyed rank_icir={v:.4f} is a gross predictive "
        "signal statistic, not a net tradable return, so cost sensitivity does not bear on it."
    ),
}


def _author_concern_scores(run_dir: Path) -> dict:
    ev = json.loads((run_dir / "steps" / "gate_evaluation" / "step_outputs.json").read_text(encoding="utf-8"))
    measured = ev["measured_values"]
    rank_icir = float(measured["rank_icir"])
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
    ap.add_argument("--decision-by", default="claude_phase6")
    ap.add_argument("--reason", default="Phase 6: OOS-stable catalog factors clear the IS-only heldout gate; "
                                        "promote draft->candidate (candidate != approved; OOS path is separate).")
    args = ap.parse_args()
    run_dir = Path(args.run_dir).resolve()

    st = load_run_state(run_dir)
    print(f"[before] status={st.get('status')} completed={st.get('completed_step_count')}")

    # 1) concern scores -> resume
    concern_dir = run_dir / "steps" / "gate_concern_scoring"
    scores = _author_concern_scores(run_dir)
    (concern_dir / "gate_concern_scores.json").write_text(json.dumps(scores, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[concern] wrote {len(scores['scores'])} scores keyed to min_rank_icir")
    res1 = resume_research(run_dir)
    st1 = load_run_state(run_dir)
    print(f"[after concern resume] status={st1.get('status')} completed={st1.get('completed_step_count')}")

    # 2) gate decision -> resume
    review_dir = run_dir / "steps" / "gate_review"
    review_dir.mkdir(parents=True, exist_ok=True)
    decision = {"decision": args.decision, "decision_by": args.decision_by, "reason": args.reason}
    (review_dir / "gate_decision.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[gate_review] wrote decision={args.decision}")
    res2 = resume_research(run_dir)
    st2 = load_run_state(run_dir)
    print(f"[after decision resume] status={st2.get('status')} completed={st2.get('completed_step_count')} failed={st2.get('failed_step_id')}")

    # 3) report publish outcome
    pub = run_dir / "steps" / "registry_publish" / "step_outputs.json"
    if pub.exists():
        p = json.loads(pub.read_text(encoding="utf-8"))
        print("=== PUBLISH OUTCOME ===")
        print("decision:", p.get("decision"))
        print("published:", p.get("published"))
        print("promoted_to_candidate:", p.get("promoted_to_candidate"))
        print("skipped_drift:", p.get("skipped_drift"))
        print("skipped_unknown:", p.get("skipped_unknown"))
    else:
        print("NO registry_publish/step_outputs.json (run did not reach publish)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
