"""D3 — sealed-OOS bar + reproduction wrapper, extracted from ``select_e_wave_sealed_oos.py``.

Design: ``workspace/research/factor_eval_methodology/FACTOR_EVAL_PARTG_BUILD_DESIGN.md``
(v2, D3). Two layers:

  * :func:`direction_aligned_pass` / :func:`evaluate_sealed_oos_bar` — the PURE bar logic
    (lifted verbatim from the script's ``_dir_aligned_pass``). Fast, deterministic,
    regression-tested against the recorded E-wave 6/6 verdict.
  * :func:`run_sealed_oos` — the SLOW orchestration that calls ``reproduce_sealed_oos``
    (reused verbatim from ``research_orchestrator.promotion_evidence``) then applies the bar.
    ``n_quantiles=10`` is pinned (the post-2026-06-11 decile standard); the bar is one
    module constant (the GP / eps_diffusion / arXiv bar).

The bar is the registration metric (gross / decile / full-universe) — NOT tradability.
Deployability is the SEPARATE Stage-8 gate (:mod:`deployment`).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

# The single OOS registration bar (sign-aligned rank_icir>0 AND aligned ls_sharpe>floor).
DEFAULT_LS_SHARPE_FLOOR = 1.0
DEFAULT_N_QUANTILES = 10  # decile (post-2026-06-11 unified 10-group standard)
DEFAULT_HORIZON = 20
# FrozenSelectionSet side convention: an inverse factor is HELD short, a positive one long.
DIR_MAP = {"inverse": "short", "positive": "long"}
VALID_SIDES = frozenset({"long", "short"})

# The A5/factor-level reproduction step id — one constant shared by the claim, the
# reproduction record, and the cmd_seal same-run resume exemption (R6 Major).
A5_REPRODUCTION_STEP_ID = "reproduce_sealed_oos"


def direction_aligned_pass(
    side: str, rank_icir: float | None, ls_sharpe: float | None, *, ls_floor: float = DEFAULT_LS_SHARPE_FLOOR
) -> tuple[bool, float, float]:
    """Direction-aware bar (verbatim from the E-wave script ``_dir_aligned_pass``): sign-align
    rank_icir + ls_sharpe by the held side, then require aligned rank_icir>0 AND aligned
    ls_sharpe>``ls_floor``. Returns ``(ok, aligned_rank_icir, aligned_ls_sharpe)``.

    Fail-closed on the side (GPT cross-review 2026-06-21): only ``long``/``short`` are valid —
    a factor-level value like ``positive``/``inverse`` is a caller error, NOT silently 'short'."""
    side = str(side).strip().lower()
    if side not in VALID_SIDES:
        raise ValueError(f"held side must be one of {sorted(VALID_SIDES)}, got {side!r}")
    s = 1.0 if side == "long" else -1.0
    da_ri = s * rank_icir if rank_icir is not None and not math.isnan(rank_icir) else float("nan")
    da_ls = s * ls_sharpe if ls_sharpe is not None and not math.isnan(ls_sharpe) else float("nan")
    ok = (not math.isnan(da_ri) and da_ri > 0) and (not math.isnan(da_ls) and da_ls > ls_floor)
    return ok, da_ri, da_ls


def sides_from_frozen_set(frozen_set) -> dict[str, str]:
    """Derive ``{factor_id: held_side}`` from a FrozenSelectionSet — its
    ``SelectedFactor.expected_direction`` IS the held side ("long"/"short"). Using this
    instead of a separate ``sides`` arg removes the risk of a sides map that disagrees with
    the sealed set (self-review 2026-06-21).

    Fail-closed: if a SelectedFactor carries a factor-level direction ("positive"/"inverse")
    instead of a held side, raise — the seal builder must convert via DIR_MAP first (GPT review)."""
    sides = {sf.factor_id: str(sf.expected_direction).strip().lower() for sf in frozen_set.selected}
    bad = {f: s for f, s in sides.items() if s not in VALID_SIDES}
    if bad:
        raise ValueError(f"FrozenSelectionSet has non-held-side directions {bad} (expected long/short)")
    return sides


@dataclass(frozen=True)
class SealedOosVerdict:
    results: tuple[dict, ...]
    n_pass: int

    @property
    def n_total(self) -> int:
        return len(self.results)


def evaluate_sealed_oos_bar(
    sides: Mapping[str, str],
    per_factor: Mapping[str, Mapping[str, Any]],
    *,
    ls_floor: float = DEFAULT_LS_SHARPE_FLOOR,
) -> SealedOosVerdict:
    """Apply the direction-aligned bar to a reproduction's per-factor OOS metrics.

    ``sides`` = ``{factor_id: "long"|"short"}`` (the held side); ``per_factor`` = the
    reproduction's ``{factor_id: {"oos_rank_icir":…, "oos_ls_sharpe":…}}``. Pure — this is
    the layer the E-wave regression replays from the recorded numbers (no backtest)."""
    results = []
    n_pass = 0
    for factor_id, side in sides.items():
        m = per_factor.get(factor_id, {})
        ri = m.get("oos_rank_icir", float("nan"))
        ls = m.get("oos_ls_sharpe", float("nan"))
        ok, da_ri, da_ls = direction_aligned_pass(side, ri, ls, ls_floor=ls_floor)
        results.append({
            "factor": factor_id, "side": side, "oos_rank_icir": ri, "oos_ls_sharpe": ls,
            "aligned_rank_icir": da_ri, "aligned_ls_sharpe": da_ls, "pass": ok,
        })
        n_pass += int(ok)
    return SealedOosVerdict(results=tuple(results), n_pass=n_pass)


# R6 Blocker 3 + R7 Major 1 — the CANONICAL registration bar: the FULL judgment
# semantics as data, so the bar an OOS observation was judged against is (a) hash
# material in the eval-protocol identity and the A5 request hash, and (b) PERSISTED
# with the verdict inside the A5 completion record. A later code deploy can never
# re-judge already-observed OOS data — the persisted verdict is the verdict.
#
# R7 hardening: the mapping is IMMUTABLE (MappingProxyType — a runtime mutation raises),
# and ``evaluator_hash`` binds the ACTUAL comparison semantics: it hashes the SOURCE of
# the evaluator functions, so silently editing e.g. ``>`` to ``>=`` changes the bar hash
# automatically (the descriptive rule strings alone could drift from the code).
# Changing the bar = a NEW bar hash = a DIFFERENT sealed recipe, never a reinterpretation.
def _evaluator_source_hash() -> str:
    import inspect

    from src.alpha_research.factor_eval_skill._hashing import payload_hash

    # R8 Major 1: the hash covers EVERY function that determines the judgment — the
    # bar comparisons AND the held-side derivation (sides_from_frozen_set decides what
    # long/short MEAN; changing it flips verdicts without touching the bar functions).
    return payload_hash({
        "direction_aligned_pass": inspect.getsource(direction_aligned_pass),
        "evaluate_sealed_oos_bar": inspect.getsource(evaluate_sealed_oos_bar),
        "sides_from_frozen_set": inspect.getsource(sides_from_frozen_set),
        "valid_sides": sorted(VALID_SIDES),
    })


def canonical_registration_bar_snapshot() -> dict[str, Any]:
    """R9 Blocker 2 — the EXECUTABLE canonical bar, built from LITERALS + a LIVE
    recomputation of the evaluator-source hash. It reads NO replaceable module global,
    so a monkeypatched/mutated ``REGISTRATION_BAR`` (or a caller-forged self-consistent
    bar dict) can never masquerade as the canonical judgment: the sealed execution
    layer compares the DECLARED bar against THIS, before any claim or OOS read. The
    descriptive rule strings are tied to the actual comparison code through
    ``evaluator_hash`` (the source hash of the judgment + sides functions)."""
    return {
        "bar_id": "registration_bar_v1",
        "direction_alignment": "held_side_sign_alignment",  # s=+1 long / -1 short on both metrics
        "rank_icir_rule": "aligned_rank_icir > 0",
        "ls_sharpe_rule": "aligned_ls_sharpe > ls_sharpe_floor",
        "ls_sharpe_floor": DEFAULT_LS_SHARPE_FLOOR,
        "nan_rule": "nan_fails",
        "sides_source": "frozen_set.selected.expected_direction",
        "evaluator_hash": _evaluator_source_hash(),
    }


# The published reference constant — BUILT FROM the canonical builder (single source)
# and immutable (a runtime mutation raises). Identity/enforcement paths never read it;
# they call canonical_registration_bar_snapshot() live.
REGISTRATION_BAR: Mapping[str, Any] = MappingProxyType(canonical_registration_bar_snapshot())


def registration_bar_snapshot() -> dict[str, Any]:
    """One PLAIN-DICT snapshot of the CANONICAL bar for a single run: hash it, persist
    it, and evaluate from IT (R7 Major 1 / R9 B2 — delegates to the literal builder,
    never the replaceable module global)."""
    return canonical_registration_bar_snapshot()


def registration_bar_hash() -> str:
    from src.alpha_research.factor_eval_skill._hashing import payload_hash

    return payload_hash(canonical_registration_bar_snapshot())


# R10 Blocker 1 — the EXECUTABLE runtime protocol: what the sealed registration-metric
# runner ACTUALLY does, as data. reproduce_sealed_oos executes decile long-short gross
# registration metrics (rank_icir at `horizon` + primary-horizon ls_sharpe) over the
# FULL provider universe with cs_rank / forward_return / no neutralization / no
# rebalanced book. A declared EvalProtocolSpec must match these values EXACTLY (plus the
# runtime horizon/n_quantiles/window) — declaring anything the runtime does not execute
# REFUSES before any claim; it is never merely hashed into identity.
EXECUTABLE_PROTOCOL_FIELDS: Mapping[str, str] = MappingProxyType({
    "metric": "rank_icir",
    "portfolio_construction": "decile_long_short",
    "universe_filter_policy": "full_provider_universe",
    "neutralization": "none",
    "rebalance": "none",
    "label_definition": "forward_return",
    "rank_transform": "cs_rank",
    "winsorization": "none",
    "missing_data_policy": "drop",
    "tie_break_policy": "average",
    "cost_slippage_for_registration": "gross",
})


# R11 Blocker — the axes the sealed registration runtime can ACTUALLY execute.
# runtime-EQUAL is not runtime-EXECUTABLE: run_batch_screening computes exactly these
# horizons (a matched-but-uncomputed horizon like 60 would yield NaN metrics while
# still consuming a seal), and the canonical protocol is the DECILE standard (a
# quintile n_quantiles=5 would execute a different spread than the declared
# decile_long_short construction).
EXECUTABLE_HORIZONS = (5, 10, 20)
# R12 Blocker: the LS-Sharpe judgment horizon IS the primary (first) screening horizon
# — pre-declared identity, never an after-the-fact note.
EXECUTABLE_LS_SHARPE_HORIZON = EXECUTABLE_HORIZONS[0]


def validate_executable_protocol_axes(
    *, horizon: int, n_quantiles: int
) -> tuple[int, int]:
    horizon = int(horizon)
    n_quantiles = int(n_quantiles)

    if horizon not in EXECUTABLE_HORIZONS:
        raise ValueError(
            f"unsupported horizon={horizon}; executable horizons are "
            f"{EXECUTABLE_HORIZONS}"
        )
    if n_quantiles != DEFAULT_N_QUANTILES:
        raise ValueError(
            f"unsupported n_quantiles={n_quantiles}; the canonical sealed "
            f"protocol requires {DEFAULT_N_QUANTILES} deciles"
        )
    return horizon, n_quantiles


def executable_protocol_spec(*, horizon: int, n_quantiles: int, oos_window: str):
    """Build THE declarable protocol for the sealed registration runtime: executable
    constants + VALIDATED-executable runtime axes + the canonical bar hash. cmd_seal
    (and any sanctioned caller) declares protocols ONLY through this constructor."""
    from src.alpha_research.factor_eval_skill.identity import EvalProtocolSpec

    horizon, n_quantiles = validate_executable_protocol_axes(
        horizon=horizon,
        n_quantiles=n_quantiles,
    )
    return EvalProtocolSpec(
        horizon=horizon, n_quantiles=n_quantiles, oos_window=str(oos_window),
        # R12 Blocker: the ordered horizon set + LS judgment horizon are declared
        # identity — a code drift reordering horizons mints a DIFFERENT protocol.
        screening_horizons=EXECUTABLE_HORIZONS,
        ls_sharpe_horizon=EXECUTABLE_LS_SHARPE_HORIZON,
        registration_bar_hash=registration_bar_hash(),
        **EXECUTABLE_PROTOCOL_FIELDS,
    )


def run_sealed_oos(
    *,
    frozen_set,
    oos_start: str,
    oos_end: str,
    qlib_dir: str,
    run_dir: str,
    design_hash: str,
    hypothesis_id: str,
    registration_bar: Mapping[str, Any],
    registration_bar_hash: str,
    eval_protocol,
    horizon: int = DEFAULT_HORIZON,
    n_quantiles: int = DEFAULT_N_QUANTILES,
    claim_seal: bool = True,
    fresh_window_override_id: str = "",
    multiplicity_ack: bool = False,
    a6_multiplicity_override_id: str = "",
    allow_same_run: bool = False,
) -> dict[str, Any]:
    """SLOW orchestration: reproduce the sealed OOS (reused ``reproduce_sealed_oos``) then
    apply the bar. Returns ``{"reproduction": …, "verdict": SealedOosVerdict}``.

    R5 Blocker 4: the held SIDES and the pass FLOOR are NOT caller parameters — they are
    part of the sealed evaluation recipe. Sides derive from ``frozen_set`` (each
    ``SelectedFactor.expected_direction``) and the floor is the fixed module constant
    ``DEFAULT_LS_SHARPE_FLOOR``. Seeing the OOS metrics can never let a caller re-judge a
    completed reproduction with a laxer floor or a flipped direction.
    R4 B1/B3: there is no ``seal_root`` (the sealed stores derive from the CONFIGURED
    global holdout root) and no ``factor_exprs`` (expressions resolve from the current
    catalog, definition-hash-verified against the frozen set).

    v1.4 A5 (PR3): this is a FACTOR-LEVEL (frozen-set-keyed) path — on a FRESH/virgin
    (post-2026-02-27) window it is an A5 signal-replication study, which requires a
    ``fresh_window_override_id`` recorded BEFORE access (the pre-authorized exception;
    the spend counts against the A6 book budget and burns the window for overlapping
    downstream books). Enforced HERE (the shared wrapper) so a direct script call cannot
    bypass the ``cmd_seal`` CLI enforcement. Book-level spends use
    :mod:`.book_seal` (``book_seal_key``), never this path."""
    from src.research_orchestrator import promotion_evidence as pe

    from src.alpha_research.factor_eval_skill.multiplicity import is_virgin_window

    if claim_seal and is_virgin_window(oos_end) and not str(fresh_window_override_id).strip():
        # fail-fast wrapper check; the AUTHORITATIVE enforcement (pre-recorded, consume-once,
        # window+scope-bound authorization) lives at the lowest shared claim point inside
        # reproduce_sealed_oos (R1 Blocker 3) — an invented id fails THERE even if a caller
        # bypasses this wrapper.
        raise ValueError(
            "v1.4_A5_fresh_window_override_required: a factor-level sealed-OOS spend on a "
            f"virgin (post-2026-02-27) window (oos_end={oos_end}) is an A5 signal-replication "
            "study and requires a PRE-RECORDED fresh_window_signal_replication_override_id "
            "(OverrideAuthorizationStore, kind=a5_fresh_window). Book-level spends go through "
            "factor_eval_skill.book_seal (book_seal_key)."
        )

    reproduction = pe.reproduce_sealed_oos(
        frozen_set=frozen_set, oos_start=oos_start,
        oos_end=oos_end, qlib_dir=qlib_dir, run_dir=run_dir,
        design_hash=design_hash, hypothesis_id=hypothesis_id, horizon=horizon,
        n_quantiles=n_quantiles, claim_seal=claim_seal,
        fresh_window_override_id=str(fresh_window_override_id),
        multiplicity_ack=multiplicity_ack,
        a6_multiplicity_override_id=str(a6_multiplicity_override_id),
        allow_same_run=allow_same_run, step_id=A5_REPRODUCTION_STEP_ID,
        # R8 Blocker 3 + R9 Blocker 2: the DECLARED bar snapshot + the FULL
        # EvalProtocolSpec are threaded down — reproduce verifies the bar against the
        # canonical executable bar and the protocol chain (bar hash + frozen-set
        # observation hash); bare caller-supplied hash strings are never accepted.
        registration_bar=dict(registration_bar),
        registration_bar_hash=str(registration_bar_hash),
        eval_protocol=eval_protocol,
    )
    # R5 B4 + R6 B3: the verdict is judged against the CANONICAL registration bar INSIDE
    # reproduce_sealed_oos's locked span and PERSISTED with the completion record — this
    # wrapper only reads it back. Re-running with changed code (a new constant, a new bar
    # function) returns the SAME persisted verdict; a record without one (pre-R6) is
    # quarantined, never silently re-judged by current code.
    bar_verdict = reproduction.get("bar_verdict")
    if not isinstance(bar_verdict, Mapping) or not bar_verdict.get("results"):
        raise ValueError(
            "sealed reproduction carries no persisted bar_verdict — a pre-R6 completion "
            "record must be explicitly migrated (with its original bar semantics), not "
            "re-judged by the current code"
        )
    # R7 Major 1: the persisted bar must re-hash to its recorded hash — a record whose
    # bar payload was altered after judgment (or judged against a mutated global) refuses.
    from src.alpha_research.factor_eval_skill._hashing import payload_hash as _phash

    if _phash(dict(reproduction.get("registration_bar") or {})) != str(
        reproduction.get("registration_bar_hash")
    ):
        raise ValueError(
            "persisted registration_bar does not re-hash to its recorded "
            "registration_bar_hash — tamper/mutation; the record is quarantined"
        )
    verdict = SealedOosVerdict(
        results=tuple(dict(r) for r in bar_verdict["results"]),
        n_pass=int(bar_verdict["n_pass"]),
    )
    return {"reproduction": reproduction, "verdict": verdict}
