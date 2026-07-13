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
    EvalProtocolSpec,
    FrozenSelectionEnvelope,
    SelectedRepresentative,
    SelectedSet,
    TargetUniverseDeclaration,
    assert_identity_chain,
)
from src.alpha_research.factor_eval_skill.marginal import select_marginal
from src.alpha_research.factor_eval_skill.multiplicity import (
    ACTION_ACKNOWLEDGE,
    ACTION_REFUSE,
    ACTION_REQUIRE,
    is_virgin_window,
    oos_window_multiplicity,
    virgin_window_multiplicity,
)
from src.alpha_research.factor_eval_skill.sealed_oos import DIR_MAP
from src.alpha_research.factor_eval_skill.stage3_reader import (
    MatrixResults,
    Stage3GovernanceInputs,
    stage3_caps,
)
from src.alpha_research.factor_eval_skill.stores import (
    FactorProvenanceStore,
    FrozenSealAliasStore,
    FrozenSelectionEnvelopeStore,
    OosWindowLedgerStore,
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
    # the GLOBAL cross-run holdout-seal store (data/holdout_seals). REQUIRED for a live seal —
    # a run-local seal would not enforce the single-shot OOS budget across runs.
    holdout_seal_root: Path | None = None

    @classmethod
    def create(cls, *, run_dir: str | Path, store_root: str | Path, registry_root: str | Path,
               resolve_factor: Callable[[str], FactorIdentity] | None = None,
               holdout_seal_root: str | Path | None = None) -> "FactorEvalContext":
        run_dir = Path(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        return cls(run_dir=run_dir, store_root=Path(store_root),
                   resolve_factor=resolve_factor or _default_resolver(registry_root),
                   holdout_seal_root=Path(holdout_seal_root) if holdout_seal_root else None)

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


def _seal_store(ctx: "FactorEvalContext"):
    """The global HoldoutSealStore (authoritative cross-tool spend record) if configured, else
    None. Folded into the OOS-window multiplicity denominator so the FDR count includes the
    historical seals (E-wave / GP / arXiv / eps_diffusion), not just skill-driven spends."""
    if not ctx.holdout_seal_root:
        return None
    from src.research_orchestrator.holdout_seal import HoldoutSealStore
    return HoldoutSealStore(ctx.holdout_seal_root)


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
    # strict, but SCOPED to this factor — another factor's legitimately-incomplete rows
    # (e.g. northbound on microcap) must not block characterizing this one.
    matrix = MatrixResults.from_jsonl(matrix_path, strict=True, strict_factor=reg["factor_id"])
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
        "layer1_methodology_hash": ch.get("layer1_methodology_hash", ""),
    })


# A factor is selected as a RANKING component; only ranking/both Stage-3 evidence may qualify it
# (a filter-role record must NOT satisfy ranking eligibility — GPT re-verify 2026-06-21).
ALLOWED_SELECTION_ROLES = ("ranking", "both")


def _ranking_record_eligible(rec: Mapping[str, Any]) -> bool:
    ceiling_ok = STATUS_CEILINGS.index(rec["status_effect"]) >= CANDIDATE_CEILING_RANK
    return ceiling_ok and str(rec.get("target_universe_pass")) == "True"


def _eligible_ranking_record(store: Stage3QualityRecordStore, *, factor_id: str, definition_hash: str,
                             layer1_hash: str, tud_hash: str):
    """The latest ELIGIBLE ranking/both Stage-3 record for this factor on this target+methodology — the
    lookup includes role + layer1_methodology_hash (both part of the record key) so a filter record or a
    stale-methodology record cannot shadow it (GPT re-verify 2026-06-21)."""
    for role in ALLOWED_SELECTION_ROLES:
        rec = store.latest(factor_id=factor_id, definition_hash=definition_hash,
                           layer1_methodology_hash=layer1_hash,
                           target_universe_declaration_hash=tud_hash, role=role)
        if rec is not None and _ranking_record_eligible(rec):
            return rec
    return None


def _assert_pool_eligible(ctx: FactorEvalContext, pool: Mapping[str, str], reg: Mapping[str, Any],
                          tud_a: Mapping[str, Any], metrics: Mapping[str, Mapping[str, Any]]) -> None:
    """Fail-closed (GPT re-review + re-verify): never select a factor whose ranking eligibility is not
    backed by a ranking/both Stage-3 record matching BOTH the declared target AND the selection-universe
    row's Layer-1 methodology. The registered factor uses gate.json (whose Layer-1 methodology must equal
    the selection row's); every other pool factor must have a matching eligible record."""
    gate = ctx._read(A_GATE)
    if gate is None:
        raise FactorEvalError("select requires the gate decision — run `gate` first")
    reg_fid = reg["factor_id"]
    tud_hash = tud_a["tud_hash"]
    store = Stage3QualityRecordStore(ctx.store_root)

    if reg_fid in pool:
        sel_l1 = str(metrics[reg_fid].get("layer1_methodology_hash", ""))
        if not gate.get("candidate_eligible", False):
            raise FactorEvalError(f"{reg_fid} is not candidate_eligible (gate: {gate.get('reason')}) — refusing to select it")
        if str(gate.get("role")) not in ALLOWED_SELECTION_ROLES:
            raise FactorEvalError(f"{reg_fid} gate role {gate.get('role')!r} is not a ranking selection role")
        if str(gate.get("layer1_methodology_hash", "")) != sel_l1:
            raise FactorEvalError(
                f"{reg_fid} gate Layer-1 methodology != the selection-universe row methodology (stale/mismatched evidence)"
            )

    ineligible = []
    for fid in pool:
        if fid == reg_fid:
            continue
        ident = ctx.resolve_factor(fid)
        sel_l1 = str(metrics[fid].get("layer1_methodology_hash", ""))
        if _eligible_ranking_record(store, factor_id=fid, definition_hash=ident.definition_hash,
                                    layer1_hash=sel_l1, tud_hash=tud_hash) is None:
            ineligible.append(fid)
    if ineligible:
        raise FactorEvalError(
            f"pool factors lack an eligible ranking/both Stage-3 record (matching the target + selection "
            f"Layer-1 methodology): {ineligible} — characterize + gate each pool factor on the target first"
        )


def cmd_select(
    ctx: FactorEvalContext, *, matrix_path: str | Path, pool: Mapping[str, str],
    caps: Mapping[str, int], floor: float, references: Sequence[str] = (), n: int | None = None,
    selection_code_hash: str = "", corr_path: str | Path | None = None,
    selection_universe: str | None = None, require_eligibility: bool = True,
) -> dict:
    reg = ctx._require(A_REGISTER, "select")
    tud_a = ctx._require(A_TUD, "select")
    # The selection basis universe = the declared TARGET by default (NOT hardcoded univ_all) — v1.3
    # target-universe discipline (GPT re-review: selecting on univ_all under a liquid target recreates
    # the E-wave failure). An explicit selection_universe is allowed (and folded into identity).
    sel_universe = selection_universe or tud_a["target_universe_id"]

    # A multi-factor pool MUST carry a precomputed exposure correlation — without it the greedy
    # would do NO redundancy pruning (the v1 defect). Fail-closed early (self-review 2026-06-21).
    if len(pool) > 1 and corr_path is None:
        raise FactorEvalError(
            f"multi-factor selection ({len(pool)} factors) requires a precomputed exposure correlation "
            "(corr_path); refusing no-redundancy selection (the v1 marginal-vs-ICIR defect)"
        )

    metrics = {}
    for line in Path(matrix_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if (row.get("universe_id") or "") == sel_universe and row.get("factor") in pool:
            metrics[str(row["factor"])] = row
    missing = [f for f in pool if f not in metrics]
    if missing:
        raise FactorEvalError(f"no '{sel_universe}' matrix rows for pool factors {missing}")

    # Eligibility AFTER the selection-universe rows load, so the check can match each factor's
    # Layer-1 methodology + role to the actual selection row (GPT re-verify 2026-06-21).
    if require_eligibility:
        _assert_pool_eligible(ctx, pool, reg, tud_a, metrics)

    import pandas as pd
    corr_names = list(pool) + [r for r in references if r not in pool]
    if corr_path is not None:
        corr = pd.read_parquet(corr_path).reindex(index=corr_names, columns=corr_names)
    else:  # singleton pool: no redundancy possible
        corr = pd.DataFrame(0.0, index=corr_names, columns=corr_names)
    selection = select_marginal(pool=pool, metrics=metrics, corr=corr, caps=caps,
                                floor=floor, references=references)

    # Canonical candidate_pool_hash over EVERY pool factor's identity (GPT re-review: a factor-ID-only
    # hash misses a non-selected factor's definition change that could have altered selection).
    versions, def_hashes, pool_identity = {}, {}, []
    for fid in sorted(pool):
        ident = ctx.resolve_factor(fid)
        versions[fid], def_hashes[fid] = ident.version, ident.definition_hash
        pool_identity.append([fid, ident.version, ident.definition_hash, str(pool[fid])])
    pool_hash = payload_hash({"selection_universe": sel_universe, "pool": pool_identity})

    sset = selection.to_selected_set(
        tud_hash=tud_a["tud_hash"], pool_hash=pool_hash,
        selection_code_hash=selection_code_hash or f"select_marginal_v1@{sel_universe}",
        versions=versions, definition_hashes=def_hashes, n=n,
    )
    members = [{"factor_id": r.factor_id, "version": r.version, "definition_hash": r.definition_hash,
                "expected_direction": r.expected_direction} for r in sset.selected]
    return ctx._write(A_SELECTED, {
        "selected_set_hash": sset.selected_set_hash, "tud_hash": sset.tud_hash,
        "pool_hash": pool_hash, "selection_code_hash": sset.selection_code_hash,
        "selection_universe": sel_universe, "members": members, "trace": list(selection.trace),
    })


def _rebuild_selected_set(sel: Mapping[str, Any]) -> SelectedSet:
    reps = tuple(
        SelectedRepresentative(m["factor_id"], int(m["version"]), m["definition_hash"], m["expected_direction"])
        for m in sel["members"]
    )
    return SelectedSet(tud_hash=sel["tud_hash"], pool_hash=sel["pool_hash"], selected=reps,
                       selection_code_hash=sel["selection_code_hash"])


def _enforce_multiplicity_action(report, *, ack: bool, override: bool) -> None:
    """Before OOS access, the multiplicity action is ENFORCED (not just stamped) — GPT re-review."""
    if report.action == ACTION_ACKNOWLEDGE and not (ack or override):
        raise FactorEvalError(
            f"OOS-window multiplicity requires reviewer acknowledgement (n_spent={report.n_spent}): "
            f"pass multiplicity_ack=True. {report.note}"
        )
    if report.action == ACTION_REQUIRE and not override:
        raise FactorEvalError(
            f"OOS-window multiplicity requires adjusted-FDR context or an explicit override "
            f"(n_spent={report.n_spent}): pass multiplicity_override=True. {report.note}"
        )


def _assert_not_already_spent(ctx: FactorEvalContext, frozen_set_hash: str) -> None:
    """Live preflight: refuse if this canonical hash OR any registered legacy alias is already a spent
    seal_key (GPT re-review: the holdout store self-checks only the exact key)."""
    seal_store = _seal_store(ctx)
    if seal_store is None:
        return
    events = seal_store.list_events()
    spent = set(events["seal_key"].dropna().astype("string")) if not events.empty else set()
    candidates = {frozen_set_hash} | set(FrozenSealAliasStore(ctx.store_root).aliases_for(frozen_set_hash))
    hit = candidates & spent
    if hit:
        raise FactorEvalError(
            f"OOS already spent for frozen_set_hash {frozen_set_hash} (matched {sorted(hit)}) — "
            "single-shot; refusing a re-spend of the same economic test"
        )


def cmd_seal(
    ctx: FactorEvalContext, *, mode: str = "show", oos_start: str = "", oos_end: str = "",
    qlib_dir: str = "", horizon: int = 20, n_quantiles: int = 10,
    metric: str = "rank_icir", neutralization: str = "none", rebalance: str = "20d",
    portfolio_side: str = "long_short", created_by: str = "factor-eval",
    multiplicity_ack: bool = False, multiplicity_override_id: str = "",
    fresh_window_override_id: str = "",
) -> dict:
    # dryrun REMOVED (GPT re-review): it ran the real OOS reproduction under a run-local seal — an
    # OOS-leak path. show = identity/multiplicity preview (no OOS); live = the ONLY OOS-access mode.
    if mode not in ("show", "live"):
        raise FactorEvalError(
            f"seal mode must be show/live, got {mode!r} (dryrun removed: it leaked OOS via a run-local seal)"
        )
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
    # CANONICAL eval-protocol identity (GPT re-review #3.1): the full protocol, not a thin dict.
    spec = EvalProtocolSpec(
        horizon=horizon, n_quantiles=n_quantiles, oos_window=f"{oos_start}..{oos_end}", metric=metric,
        universe_filter_policy=sel.get("selection_universe", tud_a["target_universe_id"]),
        portfolio_construction=f"decile_{portfolio_side}", neutralization=neutralization, rebalance=rebalance,
    )
    fs = FrozenSelectionSet(
        selected=selected, candidate_pool_hash=sel["pool_hash"],
        selection_rule_hash=sel["selection_code_hash"], eval_protocol_hash=spec.protocol_hash,
        metric=metric, portfolio_side=portfolio_side, universe=tud_a["target_universe_id"],
        time_split_window=f"{oos_start}..{oos_end}", rebalance=rebalance, neutralization=neutralization,
    )
    envelope = FrozenSelectionEnvelope(
        frozen_set_hash=fs.frozen_set_hash, target_universe_declaration_hash=tud_a["tud_hash"],
        selected_set_hash=sel["selected_set_hash"], created_at=_now(), created_by=created_by,
    )
    # MANDATORY identity chain before any seal/persist
    assert_identity_chain(_tud_from_args(tud_a["args"]), _rebuild_selected_set(sel), envelope)
    FrozenSelectionEnvelopeStore(ctx.store_root).record_envelope(envelope)

    oos_window_id = f"{oos_start}..{oos_end}"
    ledger = OosWindowLedgerStore(ctx.store_root)
    factor_ids = [m["factor_id"] for m in sel["members"]]
    base = {"mode": mode, "frozen_set_hash": fs.frozen_set_hash, "envelope_hash": envelope.envelope_hash,
            "tud_hash": tud_a["tud_hash"], "eval_protocol_hash": spec.protocol_hash,
            "portfolio_side": portfolio_side, "oos_window_id": oos_window_id, "n_quantiles": n_quantiles,
            "horizon": horizon, "selection_universe": sel.get("selection_universe", tud_a["target_universe_id"]),
            "held_sides": [{"factor_id": s.factor_id, "side": s.expected_direction} for s in selected]}

    # multiplicity computed with pending_self=True (this would-be spend counted) BEFORE OOS access (#8).
    report = oos_window_multiplicity(ledger, oos_window_id, seal_store=_seal_store(ctx), pending_self=True)
    if mode == "show":
        return ctx._write(A_SEAL, {**base, "multiplicity": report.to_dict(),
                                   "note": "recipe + identity chain verified; NO OOS touched, NO seal"})

    # ---- live: the ONLY OOS-access mode ----
    if not ctx.holdout_seal_root:
        raise FactorEvalError(
            "live seal requires a global holdout_seal_root (the cross-run single-shot store) — "
            "refusing a run-local live seal that would not enforce the OOS budget across runs"
        )
    # R2 Blocker 5: the multiplicity override is a pre-recorded, consume-once a6
    # AUTHORIZATION (OverrideAuthorizationStore at the global holdout root), never a
    # boolean — an invented id refuses here, before any OOS access.
    override_ok = False
    if str(multiplicity_override_id).strip():
        from src.alpha_research.factor_eval_skill.book_seal_stores import (
            OverrideAuthorizationStore,
        )

        OverrideAuthorizationStore(str(ctx.holdout_seal_root)).consume_authorization(
            kind="a6_multiplicity", override_id=str(multiplicity_override_id),
            oos_window_id=oos_window_id, scope_key=fs.frozen_set_hash,
        )
        override_ok = True
    _enforce_multiplicity_action(report, ack=multiplicity_ack, override=override_ok)  # (#7)
    # v1.4 A5 (PR3): a FRESH/virgin (post-2026-02-27) window through this FACTOR-LEVEL path is an
    # A5 signal-replication study — it requires a fresh_window_signal_replication_override_id
    # recorded BEFORE access, burns the window for overlapping downstream books, and is counted
    # under the STRICTER A6 virgin budget (warn 3 / hard 5 spend-unit keys). Book-level spends
    # use factor_eval_skill.book_seal (book_seal_key), never this door.
    virgin = is_virgin_window(oos_end)
    if virgin:
        if not str(fresh_window_override_id).strip():
            raise FactorEvalError(
                "v1.4_A5_fresh_window_override_required: a live factor-level seal on a virgin "
                f"window (oos_end={oos_end}) needs a pre-recorded "
                "fresh_window_signal_replication_override_id (A5); book-level spends go "
                "through book_seal.run_book_sealed_evaluation"
            )
        # R3 Blocker 2: the virgin budget reads the CANONICAL ledger colocated with the
        # global holdout store (where reproduce_sealed_oos reserves A5 spends) — the
        # run-local store_root ledger stays for legacy burned-window accounting only.
        canonical_ledger = OosWindowLedgerStore(str(ctx.holdout_seal_root))
        virgin_report = virgin_window_multiplicity(
            canonical_ledger, oos_window_id, override_recorded=override_ok, pending_self=True
        )
        if virgin_report.action == ACTION_REFUSE:
            raise FactorEvalError(
                f"virgin-window budget HARD STOP (n_spent={virgin_report.n_spent}): a user-signed "
                f"a6_multiplicity authorization must be recorded+consumed BEFORE the spend (A6). "
                f"{virgin_report.note}"
            )
        _enforce_multiplicity_action(virgin_report, ack=multiplicity_ack, override=override_ok)
    _assert_not_already_spent(ctx, fs.frozen_set_hash)                                            # (#1 preflight)
    seal_root = str(ctx.holdout_seal_root)
    from src.alpha_research.factor_eval_skill.sealed_oos import run_sealed_oos
    exprs = {m["factor_id"]: ctx.resolve_factor(m["factor_id"]).expr for m in sel["members"]}
    # R2 Blocker 4 + R3 Blocker 2: the A5 virgin spend is RESERVED inside
    # reproduce_sealed_oos (the lowest shared claim point) against the CANONICAL ledger
    # derived from seal_root, atomically before the claim, with the A6 bands enforced
    # inside the reservation — cmd_seal no longer selects the ledger path.
    result = run_sealed_oos(
        frozen_set=fs, factor_exprs=exprs, oos_start=oos_start, oos_end=oos_end, qlib_dir=qlib_dir,
        seal_root=seal_root, run_dir=str(ctx.run_dir), design_hash=fs.frozen_set_hash,
        hypothesis_id=reg["factor_id"], horizon=horizon, n_quantiles=n_quantiles, claim_seal=True,
        fresh_window_override_id=fresh_window_override_id,
        multiplicity_ack=multiplicity_ack,
        a6_multiplicity_override_id=str(multiplicity_override_id),
    )
    verdict = result["verdict"]
    # burned windows keep the legacy post-claim record (pre-claim failure never overcounts);
    # virgin windows were already reserved pre-claim inside reproduce_sealed_oos.
    if not virgin:
        ledger.record_spend(oos_window_id=oos_window_id, frozen_set_hash=fs.frozen_set_hash,
                            evidence_tier=reg.get("evidence_tier", ""), factor_ids=factor_ids,
                            seal_mode="live")
    # final report AFTER the spend is recorded (pending_self=False). On a VIRGIN window the
    # GOVERNING report is the stricter A6 virgin budget (R1 Major 3 — the legacy report must
    # not replace it); the legacy system-level report is retained alongside for compatibility.
    legacy_report = oos_window_multiplicity(ledger, oos_window_id, seal_store=_seal_store(ctx), pending_self=False)
    if virgin:
        final_report = virgin_window_multiplicity(
            OosWindowLedgerStore(str(ctx.holdout_seal_root)), oos_window_id, pending_self=False
        )
    else:
        final_report = legacy_report
    return ctx._write(A_SEAL, {**base, "multiplicity": final_report.to_dict(),
                               "legacy_multiplicity": legacy_report.to_dict(), "n_pass": verdict.n_pass,
                               "n_total": verdict.n_total, "results": list(verdict.results)})


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
