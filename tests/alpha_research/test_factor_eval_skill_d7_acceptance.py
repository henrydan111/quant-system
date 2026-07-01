"""D7 — the non-E-wave acceptance test (the merge gate, FACTOR_EVAL_PARTG_BUILD_DESIGN v2 D7).

Runs `mom_overnight_20d` — a base catalog momentum factor (native, price-only, NON-cohort) —
end-to-end through the GENERIC pipeline (register -> declare_target -> characterize -> gate ->
select -> seal(show) -> deploy(show)) using the PRODUCTION resolver (real registry + catalog)
and the LIVE 7-universe matrix, on a TEMP store/run-dir (no live registry mutation), seal in
SHOW mode (no live OOS spend). Proves the generic path touches ZERO E-wave/cicc code and
reproduces a hand-run stage3_caps. This is the build's definition of done.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.alpha_research.factor_eval_skill.identity import TargetUniverseDeclaration
from src.alpha_research.factor_eval_skill.orchestration import (
    FactorEvalContext,
    cmd_characterize,
    cmd_declare_target,
    cmd_deploy,
    cmd_gate,
    cmd_register,
    cmd_seal,
    cmd_select,
)
from src.alpha_research.factor_eval_skill.stage3_reader import (
    MatrixResults,
    Stage3GovernanceInputs,
    stage3_caps,
)
from src.alpha_research.factor_registry.replication_governance import STATUS_CEILINGS

ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "workspace" / "outputs" / "unified_eval_matrix" / "results.jsonl"
REGISTRY = ROOT / "data" / "factor_registry"
PKG = ROOT / "src" / "alpha_research" / "factor_eval_skill"
ACCEPT = "mom_overnight_20d"
TARGET = "univ_liquid_top300"

_live = pytest.mark.skipif(not (MATRIX.exists() and REGISTRY.exists()),
                           reason="live matrix / registry absent")


@_live
def test_mom_overnight_acceptance_end_to_end(tmp_path):
    # PRODUCTION resolver (real registry + catalog), TEMP store/run-dir -> no live mutation.
    ctx = FactorEvalContext.create(run_dir=tmp_path / "run", store_root=tmp_path / "store",
                                   registry_root=REGISTRY)
    reg = cmd_register(ctx, factor_id=ACCEPT, mode="deployment_bound", evidence_tier="theory_a_priori",
                       direction_source="theory", role="ranking", role_direction="long")
    assert reg["cohort_id"] == ""  # native catalog factor, NOT a cohort

    cmd_declare_target(ctx, target_universe_id=TARGET,
                       eligibility_policy="liquid_top300_20d_dollar_vol", asof_policy="pit_lag_1")
    ch = cmd_characterize(ctx, matrix_path=MATRIX)  # native governance, no manifest
    assert ch["factor_class"] == "native"
    assert ch["status_effect"] in STATUS_CEILINGS

    # hand-run reproduction: a direct stage3_caps must match the CLI's characterize
    matrix = MatrixResults.from_jsonl(MATRIX, strict=False)
    hand = stage3_caps(
        matrix, factor_id=ACCEPT, definition_hash=reg["definition_hash"],
        tud=TargetUniverseDeclaration(TARGET, {}, "liquid_top300_20d_dollar_vol", "pit_lag_1"),
        role="ranking", governance=Stage3GovernanceInputs.native(),
    )
    assert ch["status_effect"] == hand.status_effect
    assert ch["target_universe_pass"] == hand.target_universe_pass

    gate = cmd_gate(ctx)
    assert isinstance(gate["candidate_eligible"], bool)

    sel = cmd_select(ctx, matrix_path=MATRIX, pool={ACCEPT: "momentum"}, caps={"momentum": 1}, floor=0.10)
    assert [m["factor_id"] for m in sel["members"]] == [ACCEPT]

    seal = cmd_seal(ctx, mode="show", oos_start="2021-01-01", oos_end="2026-02-27")  # SHOW: no live OOS
    assert seal["frozen_set_hash"] and seal["envelope_hash"]
    assert seal["multiplicity"]["action"]  # D6 disclosure stamped

    deploy = cmd_deploy(ctx, mode="show", deployment_universe=TARGET, portfolio_side="long_only",
                        construction={"topk": 30, "rebalance": "monthly"},
                        pre_declared_bar={"min_cagr": "0.05", "max_mdd": "0.40"})
    # the chain held (cmd_seal + cmd_deploy call assert_identity_chain; no exception)
    assert deploy["plan_hash"] and deploy["frozen_set_hash"] == seal["frozen_set_hash"]

    # all artifacts produced; sidecars written to the TEMP store (live registry untouched)
    for art in ("register", "tud", "characterize", "gate", "selected_set", "seal", "deploy"):
        assert (tmp_path / "run" / f"{art}.json").exists()
    assert (tmp_path / "store" / "factor_provenance.parquet").exists()


def test_skill_path_imports_no_ewave_or_cicc():
    """The generic path must IMPORT zero E-wave / cicc code (docstring provenance mentions OK)."""
    forbidden = ("e_wave", "ewave", "cicc")
    for py in sorted(PKG.glob("*.py")):
        for line in py.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                low = stripped.lower()
                for token in forbidden:
                    assert token not in low, f"{py.name} imports E-wave/cicc code: {stripped!r}"
