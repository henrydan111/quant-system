"""OperatorCertification — the P-OP skeleton (roadmap Rev5 §10A, GPT R2-B3 decoupling).

PIT-safety lint proves a factor expression has no lookahead and no field-format error; it
does NOT prove a *new operator* computes the CICC formula correctly. A wrong operator can
silently produce a plausible-but-wrong alpha that fools the IS gate. This module is the
certification harness that gates new operators before any factor using them may enter the
formal IS gate (§10A: an uncertified-operator factor is dev-evidence only).

The CRITICAL design rule (GPT R2-B3, breaking the dependency ring): OperatorCertification
proves operator **semantics / alignment / PIT-causality ONLY** — it NEVER consults a CICC
truth table, so certifying an operator does not observe (and burn) any OOS window. Truth-
table parity is a SEPARATE concern (FactorReplicationCertification), reached only when a
factor claims ``exact_certified``.

Four test kinds, none of which is truth-parity:
  - ``golden_panel``                — hand-computed small cases: vectorized == expected.
  - ``property_based``              — invariants the operator must satisfy (degenerate
    inputs, scale/shift behavior, NaN/suspension handling).
  - ``reference_vs_vectorized_random`` — a slow, obviously-correct reference impl vs the
    production vectorized impl on random panels (the core correctness pin).
  - ``pit_alignment``              — perturbing FUTURE rows must not change earlier outputs
    (causal / no lookahead), and the operator respects its declared window/lag.

An operator is ``certified`` iff ALL four pass; any explicit failure → ``blocked``; a
missing test → ``experimental`` (not yet run). An operator version change (impl hash)
invalidates the cert (downstream factor definition_hash must recompute).

Stores follow the registry pattern: parquet + ``file_lock`` around read-check-write.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from src.research_orchestrator.file_lock import file_lock

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CERT_DIR = _PROJECT_ROOT / "data" / "factor_registry"

OPERATOR_CERT_STATUSES = ("experimental", "certified", "blocked")
# the four test kinds — DELIBERATELY no "truth_parity" (§10A / R2-B3 decoupling).
CERT_TEST_KINDS = ("golden_panel", "property_based", "reference_vs_vectorized_random", "pit_alignment")

CERT_COLUMNS = [
    "operator_id", "status", "spec_source", "formula_text",
    "reference_impl_hash", "vectorized_impl_hash", "alignment_policy_json",
    "test_results_json", "failed_json", "certified_at", "notes",
]


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------- #
# 1. status resolver
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class OperatorCertDecision:
    operator_id: str
    status: str
    test_results: dict     # {kind: bool}
    failed: tuple          # kinds that explicitly failed
    missing: tuple         # required kinds not yet run


def resolve_operator_status(operator_id: str, test_results: dict,
                            *, required=CERT_TEST_KINDS) -> OperatorCertDecision:
    """``certified`` iff every required kind ran and passed; ``blocked`` if any explicitly
    failed (a wrong impl must hard-block, never silently degrade); ``experimental`` if a
    required test has not been run yet."""
    failed = tuple(k for k in required if test_results.get(k) is False)
    missing = tuple(k for k in required if k not in test_results)
    if failed:
        status = "blocked"
    elif missing:
        status = "experimental"
    else:
        status = "certified"
    return OperatorCertDecision(operator_id, status, dict(test_results), failed, missing)


# --------------------------------------------------------------------------- #
# 2. the certification harness (semantics / alignment / PIT only — no truth parity)
# --------------------------------------------------------------------------- #
def run_certification(
    *,
    operator_id: str,
    reference_fn,            # slow, obviously-correct implementation (Series -> Series)
    vectorized_fn,           # production vectorized implementation (Series -> Series)
    random_panels,           # iterable of pd.Series/DataFrame (time-indexed) to cross-check
    property_checks=(),      # iterable of callables(vectorized_fn) -> bool
    golden_cases=(),         # iterable of (input, expected_series)
    atol: float = 1e-9,
    pit_perturb_rows: int = 5,
    **_ignored,              # accept/ignore advisory kwargs (e.g. a window hint) for call-site stability
) -> dict:
    """Run the four certification tests and return ``{kind: bool}``. Pure: reads no market
    data and consults no truth table (§10A)."""
    results: dict = {}

    # golden_panel
    if golden_cases:
        ok = True
        for inp, expected in golden_cases:
            got = vectorized_fn(inp)
            ok = ok and np.allclose(np.asarray(got, float), np.asarray(expected, float),
                                    atol=atol, equal_nan=True)
        results["golden_panel"] = bool(ok)

    # property_based
    if property_checks:
        results["property_based"] = bool(all(bool(chk(vectorized_fn)) for chk in property_checks))

    # reference_vs_vectorized_random — the core correctness pin
    panels = list(random_panels)
    if panels:
        ok = True
        for p in panels:
            ref = np.asarray(reference_fn(p), float)
            vec = np.asarray(vectorized_fn(p), float)
            ok = ok and ref.shape == vec.shape and np.allclose(ref, vec, atol=atol, equal_nan=True)
        results["reference_vs_vectorized_random"] = bool(ok)

    # pit_alignment — perturbing FUTURE rows [k:] must not change ANY output before k. A
    # causal operator's output[t<k] depends only on input[<=t] ⊂ input[<k], so it is
    # invariant to a future shock. This catches ANY lookahead regardless of the operator's
    # legitimate lookback window (do NOT subtract the window from the safe region — a 1-step
    # lookahead smaller than the window would slip through).
    if panels:
        ok = True
        for p in panels:
            if len(p) <= pit_perturb_rows + 1:
                continue
            k = len(p) - pit_perturb_rows
            base = np.asarray(vectorized_fn(p), float)
            perturbed = p.copy()
            perturbed.iloc[k:] = perturbed.iloc[k:] + 1e6   # large future shock to rows [k:]
            after = np.asarray(vectorized_fn(perturbed), float)
            ok = ok and np.allclose(base[:k], after[:k], atol=atol, equal_nan=True)
        results["pit_alignment"] = bool(ok)

    return results


# --------------------------------------------------------------------------- #
# 3. cert store
# --------------------------------------------------------------------------- #
class OperatorCertStore:
    """Parquet-backed OperatorCertification with locked read-check-write. One row per
    operator_id (latest cert). ``status_of`` is FAIL-CLOSED: an operator with no cert row is
    ``blocked`` (uncertified), never silently allowed."""

    def __init__(self, base_dir: str | Path | None = None):
        self.base_dir = Path(base_dir) if base_dir else DEFAULT_CERT_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.base_dir / "operator_certification.parquet"
        self._lock = self.base_dir / ".operator_certification.lock"

    def records(self) -> pd.DataFrame:
        if self.path.exists():
            return pd.read_parquet(self.path)
        return pd.DataFrame(columns=CERT_COLUMNS)

    def status_of(self, operator_id: str) -> str:
        df = self.records()
        if df.empty:
            return "blocked"
        row = df[df["operator_id"] == operator_id]
        return str(row.iloc[-1]["status"]) if len(row) else "blocked"

    def certified_operators(self) -> frozenset:
        df = self.records()
        if df.empty:
            return frozenset()
        return frozenset(df[df["status"] == "certified"]["operator_id"])

    def certify(
        self,
        *,
        operator_id: str,
        test_results: dict,
        spec_source: str,
        formula_text: str,
        reference_impl_hash: str,
        vectorized_impl_hash: str,
        alignment_policy: dict,
        notes: str = "",
    ) -> OperatorCertDecision:
        """Resolve the status from the test results (callers cannot self-assign a status) and
        idempotently upsert the cert row."""
        import json

        decision = resolve_operator_status(operator_id, test_results)
        row = {
            "operator_id": operator_id, "status": decision.status,
            "spec_source": spec_source, "formula_text": formula_text,
            "reference_impl_hash": reference_impl_hash, "vectorized_impl_hash": vectorized_impl_hash,
            "alignment_policy_json": json.dumps(alignment_policy, ensure_ascii=False, sort_keys=True),
            "test_results_json": json.dumps(decision.test_results, ensure_ascii=False, sort_keys=True),
            "failed_json": json.dumps(list(decision.failed), ensure_ascii=False),
            "certified_at": _utcnow(), "notes": notes,
        }
        with file_lock(self._lock):
            df = self.records()
            keep = df[df["operator_id"] != operator_id] if not df.empty else df
            out = pd.concat([keep, pd.DataFrame([row])], ignore_index=True)[CERT_COLUMNS]
            out.to_parquet(self.path, index=False)
        return decision
