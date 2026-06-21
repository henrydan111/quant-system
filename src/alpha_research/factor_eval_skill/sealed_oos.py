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
from typing import Any, Mapping

# The single OOS registration bar (sign-aligned rank_icir>0 AND aligned ls_sharpe>floor).
DEFAULT_LS_SHARPE_FLOOR = 1.0
DEFAULT_N_QUANTILES = 10  # decile (post-2026-06-11 unified 10-group standard)
DEFAULT_HORIZON = 20
# FrozenSelectionSet side convention: an inverse factor is HELD short, a positive one long.
DIR_MAP = {"inverse": "short", "positive": "long"}


def direction_aligned_pass(
    side: str, rank_icir: float | None, ls_sharpe: float | None, *, ls_floor: float = DEFAULT_LS_SHARPE_FLOOR
) -> tuple[bool, float, float]:
    """Direction-aware bar (verbatim from the E-wave script ``_dir_aligned_pass``): sign-align
    rank_icir + ls_sharpe by the held side, then require aligned rank_icir>0 AND aligned
    ls_sharpe>``ls_floor``. Returns ``(ok, aligned_rank_icir, aligned_ls_sharpe)``."""
    s = 1.0 if side == "long" else -1.0
    da_ri = s * rank_icir if rank_icir is not None and not math.isnan(rank_icir) else float("nan")
    da_ls = s * ls_sharpe if ls_sharpe is not None and not math.isnan(ls_sharpe) else float("nan")
    ok = (not math.isnan(da_ri) and da_ri > 0) and (not math.isnan(da_ls) and da_ls > ls_floor)
    return ok, da_ri, da_ls


def sides_from_frozen_set(frozen_set) -> dict[str, str]:
    """Derive ``{factor_id: held_side}`` from a FrozenSelectionSet — its
    ``SelectedFactor.expected_direction`` IS the held side ("long"/"short"). Using this
    instead of a separate ``sides`` arg removes the risk of a sides map that disagrees with
    the sealed set (self-review 2026-06-21)."""
    return {sf.factor_id: str(sf.expected_direction) for sf in frozen_set.selected}


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


def run_sealed_oos(
    *,
    frozen_set,
    factor_exprs: Mapping[str, str],
    oos_start: str,
    oos_end: str,
    qlib_dir: str,
    seal_root: str,
    run_dir: str,
    design_hash: str,
    hypothesis_id: str,
    sides: Mapping[str, str] | None = None,
    horizon: int = DEFAULT_HORIZON,
    n_quantiles: int = DEFAULT_N_QUANTILES,
    claim_seal: bool = True,
    ls_floor: float = DEFAULT_LS_SHARPE_FLOOR,
) -> dict[str, Any]:
    """SLOW orchestration: reproduce the sealed OOS (reused ``reproduce_sealed_oos``) then
    apply the bar. Returns ``{"reproduction": …, "verdict": SealedOosVerdict}``. ``sides``
    defaults to the held sides DERIVED from ``frozen_set`` (no divergence); the seal spend is
    governed by ``claim_seal`` + ``seal_root`` (the caller decides dryrun vs live)."""
    from src.research_orchestrator import promotion_evidence as pe

    if sides is None:
        sides = sides_from_frozen_set(frozen_set)
    reproduction = pe.reproduce_sealed_oos(
        frozen_set=frozen_set, factor_exprs=dict(factor_exprs), oos_start=oos_start,
        oos_end=oos_end, qlib_dir=qlib_dir, seal_root=seal_root, run_dir=run_dir,
        design_hash=design_hash, hypothesis_id=hypothesis_id, horizon=horizon,
        n_quantiles=n_quantiles, claim_seal=claim_seal,
    )
    per_factor = reproduction["independent_reproduction"]["per_factor"]
    verdict = evaluate_sealed_oos_bar(sides, per_factor, ls_floor=ls_floor)
    return {"reproduction": reproduction, "verdict": verdict}
