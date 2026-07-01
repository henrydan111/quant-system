"""D3 — marginal-contribution selection, extracted from ``select_e_wave_marginal.py``.

Design: ``workspace/research/factor_eval_methodology/FACTOR_EVAL_PARTG_BUILD_DESIGN.md``
(v2, D3). The greedy is lifted VERBATIM from the E-wave script's ``greedy()`` — every
E-wave constant (cohort, references, caps, floor) is now a PARAMETER — so the E-wave
historical case reproduces bit-for-bit (the regression bar) while a non-E-wave factor set
runs the same code. The reusable selection rule (`reference_factor_selection_marginal_not_icir`):

    quality   = |heldout_rank_icir|                 (standalone IS strength; the IS-gate metric)
    redundancy = max month-end Spearman exposure correlation to the already-selected set
                 UNION the pre-existing redundancy references
    greedy: seed = max quality; then repeatedly add argmax of
            marginal = |icir| * (1 - max|rho|), subject to family caps;
            stop when marginal < floor or caps exhausted.

``resid_ic_vs_style_controls_v1`` is carried as an ANNOTATION only (NOT a gate) — the v1
blocking-contradiction fix (residualizing a vol/liq factor against a style book that
contains vol/liq controls nukes it tautologically).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import pandas as pd

from src.alpha_research.factor_eval_skill.identity import SelectedRepresentative, SelectedSet
from src.alpha_research.factor_lifecycle.walk_forward_validation import _expected_direction

# Matrix-row metric keys the selection consumes (the unified_eval results.jsonl schema).
_K_ICIR = "heldout_rank_icir"
_K_SIGN = "sign_consistency"
_K_RESID = "resid_ic_vs_style_controls_v1_signed"


@dataclass(frozen=True)
class MarginalSelection:
    """The raw greedy output: an ordered list of pick dicts + the human-readable trace.
    Convert to a hash-bound D2 :class:`SelectedSet` via :meth:`to_selected_set`."""

    selected: tuple[dict, ...]
    trace: tuple[str, ...]

    @property
    def factor_ids(self) -> list[str]:
        return [s["factor"] for s in self.selected]

    def head(self, n: int) -> list[str]:
        """The first ``n`` picks (e.g. the 6-core = picks above the natural marginal break)."""
        return self.factor_ids[:n]

    def to_selected_set(
        self,
        *,
        tud_hash: str,
        pool_hash: str,
        selection_code_hash: str,
        versions: Mapping[str, int],
        definition_hashes: Mapping[str, str],
        n: int | None = None,
    ) -> SelectedSet:
        """Build the D2 identity object from the greedy picks (the D4 ``select`` bridge).
        ``n`` optionally truncates to the top-n (the deployable core)."""
        picks = self.selected if n is None else self.selected[:n]
        reps = tuple(
            SelectedRepresentative(
                factor_id=s["factor"],
                version=int(versions.get(s["factor"], 1)),
                definition_hash=str(definition_hashes.get(s["factor"], "")),
                expected_direction=s["expected_direction"],
            )
            for s in picks
        )
        return SelectedSet(
            tud_hash=tud_hash, pool_hash=pool_hash, selected=reps,
            selection_code_hash=selection_code_hash,
        )


def select_marginal(
    *,
    pool: Mapping[str, str],
    metrics: Mapping[str, Mapping[str, Any]],
    corr: pd.DataFrame,
    caps: Mapping[str, int],
    floor: float,
    references: Sequence[str] = (),
) -> MarginalSelection:
    """Greedy marginal-contribution selection (extracted verbatim from the E-wave script).

    ``pool`` = ``{factor_id: family}``; ``metrics`` = ``{factor_id: row}`` with
    ``heldout_rank_icir`` + ``sign_consistency`` (+ optional ``resid_ic_vs_style_controls_v1_signed``);
    ``corr`` = a factor×factor exposure-correlation frame; ``caps`` = ``{family: max}``;
    ``references`` = pre-existing factors used ONLY as redundancy basis (never selected).
    """
    icir = {f: metrics[f][_K_ICIR] for f in pool if f in metrics}
    sign = {f: metrics[f][_K_SIGN] for f in pool if f in metrics}
    resid = {f: metrics[f].get(_K_RESID) for f in metrics}
    refs = list(references)

    def rho(f: str, g: str) -> float:
        if f in corr.index and g in corr.columns:
            v = corr.loc[f, g]
            return 0.0 if pd.isna(v) else abs(v)
        return 0.0

    selected: list[dict] = []
    fams: Counter = Counter()
    trace: list[str] = []
    selectable = [f for f in pool if f in icir]
    while True:
        best, best_score, best_info = None, -1.0, None
        for f in selectable:
            if f in [s["factor"] for s in selected]:
                continue
            if fams[pool[f]] >= caps.get(pool[f], 99):
                continue
            q = abs(icir[f])
            basis = [s["factor"] for s in selected] + refs
            mc, who = 0.0, None
            for g in basis:
                r = rho(f, g)
                if r > mc:
                    mc, who = r, g
            score = q * (1 - mc)
            if score > best_score:
                best, best_score, best_info = f, score, (q, mc, who)
        if best is None:
            trace.append("STOP: all family caps reached")
            break
        q, mc, who = best_info
        if selected and best_score < floor:
            trace.append(
                f"STOP: next-best {best} marginal={best_score:.3f} < floor {floor} "
                f"(|icir|={q:.3f}, maxcorr={mc:.2f} vs {who})"
            )
            break
        selected.append({
            "factor": best, "family": pool[best], "heldout_icir": round(icir[best], 3),
            "sign_consistency": round(sign[best], 2), "marginal_score": round(best_score, 3),
            "maxcorr_to_set": round(mc, 2), "closest_to": who,
            "style_resid_ic": (None if resid.get(best) is None else round(resid[best], 3)),
            "expected_direction": _expected_direction(icir[best]),
        })
        fams[pool[best]] += 1
        trace.append(
            f"PICK {best:34} fam={pool[best]:5} |icir|={q:.3f} maxcorr={mc:.2f}(vs {who}) marginal={best_score:.3f}"
        )
    return MarginalSelection(selected=tuple(selected), trace=tuple(trace))
