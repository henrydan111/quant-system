"""D4 — orchestration handlers for the factor-eval / strategy-build CLIs.

Design: ``workspace/research/factor_eval_methodology/FACTOR_EVAL_PARTG_BUILD_DESIGN.md``
(v2, D4). These are thin FAIL-CLOSED COORDINATORS — they own sequencing, the mode
(deployment_bound vs exploratory_research), the identity-equality chain, and the
evidence-tier reads, and delegate ALL compute to the foundation (D1/D2/D3/D5) + the reused
engines. They own invariants, not computation.

Forbidden-verb invariants are STRUCTURAL (the CLIs expose different verb sets):
``factor-eval`` cannot ``deploy``; ``strategy-build`` cannot ``seal``. ``strategy-build
deploy`` requires ``frozen_set_hash`` + ``envelope_hash`` + ``target_universe_declaration_hash``
(read from the run-dir artifacts + re-checked by ``assert_identity_chain``).

Factor-class rule (GPT cross-review): the CLI must NOT infer ``native()`` on a failed
manifest lookup — class comes from explicit declaration OR registry/manifest membership
(``replication_cohort_id`` present → cohort; declared cohort but absent → fail).

Each command reads/writes JSON artifacts under ``ctx.run_dir`` (the orchestrator pattern):
``register.json`` → ``tud.json`` → ``characterize.json`` → ``gate.json`` →
``selected_set.json`` → ``seal.json`` → ``deploy.json``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from src.alpha_research.factor_eval_skill._hashing import payload_hash
from src.alpha_research.factor_eval_skill.identity import (
    DeploymentFrozenPlan,
    FrozenSelectionEnvelope,
    SelectedRepresentative,
    SelectedSet,
    TargetUniverseDeclaration,
    assert_identity_chain,
)
from src.alpha_research.factor_eval_skill.marginal import select_marginal
from src.alpha_research.factor_eval_skill.sealed_oos import DIR_MAP
from src.alpha_research.factor_eval_skill.stage3_reader import (
    MatrixResults,
    Stage3GovernanceInputs,
    stage3_caps,
)
from src.alpha_research.factor_eval_skill.stores import (
    FactorProvenanceStore,
    FrozenSelectionEnvelopeStore,
    RoleDeclarationStore,
    Stage3QualityRecordStore,
)
from src.alpha_research.factor_registry.replication_governance import STATUS_CEILINGS

MODES = ("deployment_bound", "exploratory_research")

A_REGISTER = "register.json"
A_TUD = "tud.json"
A_CHARACTERIZE = "characterize.json"
A_GATE = "gate.json"
A_SELECTED = "selected_set.json"
A_SEAL = "seal.json"
A_DEPLOY = "deploy.json"

CANDIDATE_CEILING_RANK = STATUS_CEILINGS.index("candidate_ceiling")


class FactorEvalError(RuntimeError):
    """Fail-closed error from a factor-eval / strategy-build command."""


@dataclass(frozen=True)
class FactorIdentity:
    factor_id: str
    definition_hash: str
    version: int
    cohort_id: str  # "" for a native catalog factor
    expr: str       # the catalog expression (for seal / deploy)


def _default_resolver(registry_root: str | Path) -> Callable[[str], FactorIdentity]:
    """The production factor resolver: definition_hash/version/cohort from the registry,
    expr from the catalog. Tests inject a fake instead."""
    from src.alpha_research.factor_library import get_factor_catalog
    from src.alpha_research.factor_registry.store import FactorRegistryStore
    import pandas as pd

    store = FactorRegistryStore(registry_root)
    catalog = get_factor_catalog(include_new_data=True)
    cat_hashes = store.current_catalog_definition_hashes()
    master = store.factor_master[store.factor_master["is_current"].fillna(False)]

    def resolve(factor_id: str) -> FactorIdentity:
        if factor_id not in catalog:
            raise FactorEvalError(f"{factor_id} not in catalog")
        defh = cat_hashes.get(factor_id, "")
        if not defh:
            raise FactorEvalError(f"{factor_id} has no catalog definition_hash")
        rows = master[master["factor_id"] == factor_id]
        if rows.empty:
            raise FactorEvalError(f"{factor_id} not in factor registry")
        row = rows.iloc[0]
        cohort_raw = row.get("replication_cohort_id")
        cohort = "" if cohort_raw is None or pd.isna(cohort_raw) else str(cohort_raw)
        return FactorIdentity(factor_id, defh, int(row["version"]), cohort, str(catalog[factor_id]))

    return resolve


@dataclass
class FactorEvalContext:
    run_dir: Path
    store_root: Path
    resolve_factor: Callable[[str], FactorIdentity]

    @classmethod
    def create(cls, *, run_dir: str | Path, store_root: str | Path, registry_root: str | Path,
               resolve_factor: Callable[[str], FactorIdentity] | None = None) -> "FactorEvalContext":
        run_dir = Path(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        return cls(run_dir=run_dir, store_root=Path(store_root),
                   resolve_factor=resolve_factor or _default_resolver(registry_root))

    def _write(self, name: str, payload: Mapping[str, Any]) -> dict:
        (self.run_dir / name).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        return dict(payload)

    def _read(self, name: str) -> dict | None:
        path = self.run_dir / name
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def _require(self, name: str, step: str) -> dict:
        value = self._read(name)
        if value is None:
            raise FactorEvalError(f"{step} requires {name} — run the prior command first")
        return value


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _tud_from_args(args: Mapping[str, Any]) -> TargetUniverseDeclaration:
    return TargetUniverseDeclaration(
        target_universe_id=args["target_universe_id"],
        universe_definition_filters=args.get("universe_definition_filters") or {},
        eligibility_policy=args["eligibility_policy"],
        asof_policy=args["asof_policy"],
    )


def resolve_governance(
    identity: FactorIdentity, *, factor_class: str | None = None,
    replication_tier: str = "", claim_class: str = "", oos_eligibility: str = "", **kwargs: Any,
) -> Stage3GovernanceInputs:
    """Resolve the P-GATE governance from explicit declaration OR registry membership.
    A failed manifest lookup NEVER silently becomes native (GPT cross-review)."""
    if factor_class is None:
        factor_class = "cohort" if identity.cohort_id else "native"
    if factor_class == "native":
        return Stage3GovernanceInputs.native()
    if not identity.cohort_id:
        raise FactorEvalError(
            f"declared factor_class=cohort but {identity.factor_id} has no replication_cohort_id "
            "(a manifest row was expected, not found) — refusing to fall back to native"
        )
    return Stage3GovernanceInputs.cohort(
        replication_tier=replication_tier, claim_class=claim_class,
        oos_eligibility=oos_eligibility, **kwargs,
    )


# --------------------------------------------------------------------------- factor-eval
def cmd_register(
    ctx: FactorEvalContext, *, factor_id: str, mode: str, evidence_tier: str, direction_source: str,
    role: str, role_direction: str, multiplicity_scope_id: str = "", filter_role_subtype: str = "",
    rationale: str = "",
) -> dict:
    if mode not in MODES:
        raise FactorEvalError(f"mode must be one of {MODES}, got {mode!r}")
    identity = ctx.resolve_factor(factor_id)
    prov = FactorProvenanceStore(ctx.store_root).record_provenance(
        factor_id=factor_id, definition_hash=identity.definition_hash, evidence_tier=evidence_tier,
        direction_source=direction_source, multiplicity_scope_id=multiplicity_scope_id, rationale=rationale,
    )
    roled = RoleDeclarationStore(ctx.store_root).record_role(
        factor_id=factor_id, definition_hash=identity.definition_hash, role=role,
        role_context={"mode": mode}, direction=role_direction, filter_role_subtype=filter_role_subtype,
    )
    return ctx._write(A_REGISTER, {
        "mode": mode, "factor_id": factor_id, "definition_hash": identity.definition_hash,
        "version": identity.version, "cohort_id": identity.cohort_id,
        "evidence_tier": prov["evidence_tier"], "role": roled["role"],
        "role_direction": roled["direction"],
    })


def cmd_declare_target(
    ctx: FactorEvalContext, *, target_universe_id: str, eligibility_policy: str, asof_policy: str,
    universe_definition_filters: Mapping[str, Any] | None = None,
) -> dict:
    args = {
        "target_universe_id": target_universe_id, "eligibility_policy": eligibility_policy,
        "asof_policy": asof_policy, "universe_definition_filters": dict(universe_definition_filters or {}),
    }
    tud = _tud_from_args(args)
    return ctx._write(A_TUD, {"tud_hash": tud.tud_hash, "target_universe_id": target_universe_id, "args": args})


def cmd_characterize(
    ctx: FactorEvalContext, *, matrix_path: str | Path, factor_class: str | None = None,
    replication_tier: str = "", claim_class: str = "", oos_eligibility: str = "",
) -> dict:
    reg = ctx._require(A_REGISTER, "characterize")
    identity = ctx.resolve_factor(reg["factor_id"])
    tud_a = ctx._read(A_TUD)
    if tud_a is None:
        if reg["mode"] == "deployment_bound":
            raise FactorEvalError("deployment_bound mode requires declare_target BEFORE characterize")
        # exploratory_research: a research candidate may be characterized on univ_all (scope-stamped)
        tud = TargetUniverseDeclaration("univ_all", {}, "research_default", "pit_lag_1")
        tud_a = ctx._write(A_TUD, {
            "tud_hash": tud.tud_hash, "target_universe_id": "univ_all",
            "args": {"target_universe_id": "univ_all", "eligibility_policy": "research_default",
                     "asof_policy": "pit_lag_1", "universe_definition_filters": {}},
        })
    tud = _tud_from_args(tud_a["args"])
    if tud.tud_hash != tud_a["tud_hash"]:
        raise FactorEvalError("tud_hash drift between declare_target and characterize")
    governance = resolve_governance(
        identity, factor_class=factor_class, replication_tier=replication_tier,
        claim_class=claim_class, oos_eligibility=oos_eligibility,
    )
    matrix = MatrixResults.from_jsonl(matrix_path, strict=True)
    record = stage3_caps(
        matrix, factor_id=reg["factor_id"], definition_hash=reg["definition_hash"],
        tud=tud, role=reg["role"], governance=governance,
    )
    record.persist(Stage3QualityRecordStore(ctx.store_root))
    return ctx._write(A_CHARACTERIZE, {
        "factor_id": reg["factor_id"], "role": record.role, "factor_class": governance.factor_class,
        "target_universe_id": tud.target_universe_id, "tud_hash": tud.tud_hash,
        "status_effect": record.status_effect, "target_universe_pass": record.target_universe_pass,
        "quality_flags": record.quality_flags, "cross_universe_sign_divergence": record.cross_universe_sign_divergence,
        "layer1_methodology_hash": record.layer1_methodology_hash,
    })


def cmd_gate(ctx: FactorEvalContext) -> dict:
    ch = ctx._require(A_CHARACTERIZE, "gate")
    role = ch["role"]
    ceiling_ok = STATUS_CEILINGS.index(ch["status_effect"]) >= CANDIDATE_CEILING_RANK
    if role == "filter":
        # a filter has no IC bar — eligibility is its availability ceiling only; the deployment
        # A/B is a strategy-build (Stage 8) concern, not decided here.
        eligible = ceiling_ok
        reason = f"filter: status_effect={ch['status_effect']} (ceiling_ok={ceiling_ok}); A/B deferred to strategy-build"
    else:
        eligible = bool(ch["target_universe_pass"]) and ceiling_ok
        reason = (f"ranking: target_universe_pass={ch['target_universe_pass']} AND "
                  f"status_effect={ch['status_effect']} (>= candidate_ceiling = {ceiling_ok})")
    return ctx._write(A_GATE, {
        "factor_id": ch["factor_id"], "role": role, "candidate_eligible": eligible,
        "status_effect": ch["status_effect"], "reason": reason,
    })


def cmd_select(
    ctx: FactorEvalContext, *, matrix_path: str | Path, pool: Mapping[str, str],
    caps: Mapping[str, int], floor: float, references: Sequence[str] = (), n: int | None = None,
    selection_code_hash: str = "",
) -> dict:
    reg = ctx._require(A_REGISTER, "select")
    tud_a = ctx._require(A_TUD, "select")
    metrics = {}
    for line in Path(matrix_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if (row.get("universe_id") or "") == "univ_all" and row.get("factor") in pool:
            metrics[str(row["factor"])] = row
    import pandas as pd
    corr_names = list(pool) + [r for r in references if r not in pool]
    corr = pd.DataFrame(0.0, index=corr_names, columns=corr_names)  # single/diagonal pool -> no redundancy
    selection = select_marginal(pool=pool, metrics=metrics, corr=corr, caps=caps,
                                floor=floor, references=references)
    versions, def_hashes = {}, {}
    for fid in selection.factor_ids:
        ident = ctx.resolve_factor(fid)
        versions[fid], def_hashes[fid] = ident.version, ident.definition_hash
    pool_hash = payload_hash(sorted(pool))
    sset = selection.to_selected_set(
        tud_hash=tud_a["tud_hash"], pool_hash=pool_hash,
        selection_code_hash=selection_code_hash or "select_marginal_v1",
        versions=versions, definition_hashes=def_hashes, n=n,
    )
    members = [{"factor_id": r.factor_id, "version": r.version, "definition_hash": r.definition_hash,
                "expected_direction": r.expected_direction} for r in sset.selected]
    return ctx._write(A_SELECTED, {
        "selected_set_hash": sset.selected_set_hash, "tud_hash": sset.tud_hash,
        "pool_hash": pool_hash, "selection_code_hash": sset.selection_code_hash,
        "members": members, "trace": list(selection.trace),
    })


def _rebuild_selected_set(sel: Mapping[str, Any]) -> SelectedSet:
    reps = tuple(
        SelectedRepresentative(m["factor_id"], int(m["version"]), m["definition_hash"], m["expected_direction"])
        for m in sel["members"]
    )
    return SelectedSet(tud_hash=sel["tud_hash"], pool_hash=sel["pool_hash"], selected=reps,
                       selection_code_hash=sel["selection_code_hash"])


def cmd_seal(
    ctx: FactorEvalContext, *, mode: str = "show", oos_start: str = "", oos_end: str = "",
    qlib_dir: str = "", horizon: int = 20, n_quantiles: int = 10,
    metric: str = "rank_icir", neutralization: str = "none", rebalance: str = "20d",
    created_by: str = "factor-eval",
) -> dict:
    if mode not in ("show", "dryrun", "live"):
        raise FactorEvalError(f"seal mode must be show/dryrun/live, got {mode!r}")
    reg = ctx._require(A_REGISTER, "seal")
    tud_a = ctx._require(A_TUD, "seal")
    sel = ctx._require(A_SELECTED, "seal")
    if sel["tud_hash"] != tud_a["tud_hash"]:
        raise FactorEvalError("selected_set tud_hash != declared target tud_hash")

    from src.research_orchestrator.frozen_selection_set import FrozenSelectionSet, SelectedFactor

    # convert factor-level direction -> HELD side (long/short) before building the frozen set
    selected = tuple(
        SelectedFactor(m["factor_id"], int(m["version"]), m["definition_hash"], DIR_MAP[m["expected_direction"]])
        for m in sel["members"]
    )
    eval_protocol = {"horizon": horizon, "n_quantiles": n_quantiles,
                     "oos_window": f"{oos_start}..{oos_end}", "metric": metric}
    fs = FrozenSelectionSet(
        selected=selected, candidate_pool_hash=sel["pool_hash"],
        selection_rule_hash=sel["selection_code_hash"], eval_protocol_hash=payload_hash(eval_protocol),
        metric=metric, portfolio_side="long_short", universe=tud_a["target_universe_id"],
        time_split_window=f"{oos_start}..{oos_end}", rebalance=rebalance, neutralization=neutralization,
    )
    envelope = FrozenSelectionEnvelope(
        frozen_set_hash=fs.frozen_set_hash, target_universe_declaration_hash=tud_a["tud_hash"],
        selected_set_hash=sel["selected_set_hash"], created_at=_now(), created_by=created_by,
    )
    # MANDATORY identity chain before any seal/persist
    assert_identity_chain(_tud_from_args(tud_a["args"]), _rebuild_selected_set(sel), envelope)
    FrozenSelectionEnvelopeStore(ctx.store_root).record_envelope(envelope)

    base = {"mode": mode, "frozen_set_hash": fs.frozen_set_hash, "envelope_hash": envelope.envelope_hash,
            "tud_hash": tud_a["tud_hash"], "n_quantiles": n_quantiles, "horizon": horizon,
            "held_sides": [{"factor_id": s.factor_id, "side": s.expected_direction} for s in selected]}
    if mode == "show":
        return ctx._write(A_SEAL, {**base, "note": "recipe + identity chain verified; NO OOS touched, NO seal"})

    # dryrun / live: run the (slow) sealed OOS. Caller supplies qlib_dir + a seal_root.
    from src.alpha_research.factor_eval_skill.sealed_oos import run_sealed_oos
    exprs = {m["factor_id"]: ctx.resolve_factor(m["factor_id"]).expr for m in sel["members"]}
    seal_root = str(ctx.run_dir / ("seals_dry" if mode == "dryrun" else "seals_live"))
    result = run_sealed_oos(
        frozen_set=fs, factor_exprs=exprs, oos_start=oos_start, oos_end=oos_end, qlib_dir=qlib_dir,
        seal_root=seal_root, run_dir=str(ctx.run_dir), design_hash=fs.frozen_set_hash,
        hypothesis_id=reg["factor_id"], horizon=horizon, n_quantiles=n_quantiles, claim_seal=True,
    )
    verdict = result["verdict"]
    return ctx._write(A_SEAL, {**base, "n_pass": verdict.n_pass, "n_total": verdict.n_total,
                               "results": list(verdict.results)})


# ------------------------------------------------------------------------- strategy-build
def cmd_deploy(
    ctx: FactorEvalContext, *, mode: str = "show", deployment_universe: str, portfolio_side: str,
    construction: Mapping[str, Any], pre_declared_bar: Mapping[str, Any],
) -> dict:
    if mode not in ("show", "dryrun", "live"):
        raise FactorEvalError(f"deploy mode must be show/dryrun/live, got {mode!r}")
    seal = ctx._require(A_SEAL, "deploy")
    tud_a = ctx._require(A_TUD, "deploy")
    sel = ctx._require(A_SELECTED, "deploy")
    # strategy-build deploy REQUIRES the three identity hashes (forbidden-verb contract)
    for key in ("frozen_set_hash", "envelope_hash", "tud_hash"):
        if not seal.get(key):
            raise FactorEvalError(f"deploy requires {key} from the seal artifact")
    envelope = FrozenSelectionEnvelope(
        frozen_set_hash=seal["frozen_set_hash"], target_universe_declaration_hash=tud_a["tud_hash"],
        selected_set_hash=sel["selected_set_hash"], created_at=_now(), created_by="strategy-build",
    )
    if envelope.envelope_hash != seal["envelope_hash"]:
        raise FactorEvalError("rebuilt envelope_hash != sealed envelope_hash (binding drift)")
    plan = DeploymentFrozenPlan(
        frozen_set_hash=seal["frozen_set_hash"], envelope_hash=seal["envelope_hash"],
        target_universe_declaration_hash=tud_a["tud_hash"], deployment_universe=deployment_universe,
        portfolio_side=portfolio_side, construction=construction, pre_declared_bar=pre_declared_bar,
    )
    # MANDATORY identity chain (incl. plan) before any deployment run
    assert_identity_chain(_tud_from_args(tud_a["args"]), _rebuild_selected_set(sel), envelope, plan)
    base = {"mode": mode, "plan_hash": plan.plan_hash, "frozen_set_hash": seal["frozen_set_hash"],
            "envelope_hash": seal["envelope_hash"], "tud_hash": tud_a["tud_hash"],
            "deployment_universe": deployment_universe, "pre_declared_bar": dict(pre_declared_bar)}
    if mode == "show":
        return ctx._write(A_DEPLOY, {**base, "note": "plan + identity chain verified; NO backtest run"})
    # dryrun / live deployment backtest is the caller's wiring (run_deployment needs a panel +
    # rebalance dates + goal_metrics); the show path proves the contract/chain.
    raise FactorEvalError("deploy dryrun/live requires an event-driven panel — wire run_deployment via the CLI")
