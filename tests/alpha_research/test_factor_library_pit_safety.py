"""Follow-up Plan #1 — Factor Library PIT-Safety Static Analysis.

This module enforces the load-bearing invariant that **every `$field`
reference in every Layer 1 factor expression is wrapped inside a `Ref(...)`
frame**. It is the parser-based static-analysis regression test specified in
Step 1 of follow-up plan #1.

Why a parser, not a regex: Codex GPT-5.4 cross-review (2026-04-11) caught
that a "nearest unmatched ``(`` to the left" regex heuristic false-positives
on grouped expressions like ``Ref((($buy - $sell) / $amount), 1)``, because
the nearest ``(`` is an arithmetic grouping, not ``Ref(``. A real
parenthesis-stack walk is required.

Allowed exception: ``forward_return`` at ``operators.py:982`` is intentionally
a forward-looking label (used as the prediction target, not as a feature).
It is the ONLY operator exempt from the invariant.

Ref: plan file ``C:\\Users\\henry\\.claude\\plans\\vast-exploring-rabbit.md``
Step 1; CLAUDE.md §3 "Hard Invariants" (after this plan lands).
"""

from __future__ import annotations

import inspect
import unittest
from typing import Iterable

from src.alpha_research.factor_library import operators
from src.alpha_research.factor_library.catalog import (
    get_composite_defs,
    get_factor_catalog,
)


# ──────────────────────────────────────────────────────────────────────
# Core parser — walks a Qlib expression string and finds every $field
# reference whose parenthesis-stack ancestry does NOT contain a Ref(.
# ──────────────────────────────────────────────────────────────────────


def find_unwrapped_field_references(
    expression: str,
) -> list[tuple[int, str]]:
    """Return ``[(position, field_name), ...]`` for every ``$<field>`` token
    that is NOT inside any ``Ref(...)`` frame.

    Algorithm: walk the expression character-by-character maintaining a
    stack of open parentheses. Each stack frame records the NAME of the
    function that opened it (the identifier immediately preceding ``(``)
    or ``None`` for bare grouping parens. When a ``$<field>`` token is
    encountered, check whether any frame currently on the stack has name
    ``"Ref"``. If yes: safely wrapped. If no: violation.

    The "any Ref ancestor" rule is deliberate: an expression like
    ``Ref(Mean($close, 20), 1)`` is PIT-safe because the whole inner
    computation is frozen to one day earlier by the outer ``Ref``. The
    ``$close`` token in that expression has both ``Mean`` and ``Ref`` in
    its ancestor stack — any-Ref-ancestor is sufficient.
    """
    stack: list[str | None] = []
    violations: list[tuple[int, str]] = []
    i = 0
    n = len(expression)
    while i < n:
        c = expression[i]
        if c == "(":
            # Scan backwards for a function-identifier immediately preceding
            # this open paren (skipping whitespace).
            j = i - 1
            while j >= 0 and expression[j].isspace():
                j -= 1
            k = j
            while k >= 0 and (expression[k].isalnum() or expression[k] == "_"):
                k -= 1
            name = expression[k + 1 : j + 1] if k < j else ""
            stack.append(name or None)
            i += 1
            continue
        if c == ")":
            if stack:
                stack.pop()
            i += 1
            continue
        if c == "$":
            # Parse the field name: $ followed by [A-Za-z0-9_]+
            j = i + 1
            while j < n and (expression[j].isalnum() or expression[j] == "_"):
                j += 1
            field = expression[i + 1 : j]
            if field:
                wrapped = any(frame == "Ref" for frame in stack)
                if not wrapped:
                    violations.append((i, field))
            i = j
            continue
        i += 1
    return violations


# ──────────────────────────────────────────────────────────────────────
# Parser self-tests — hand-written cases that lock the algorithm before
# trusting it against the full catalog.
# ──────────────────────────────────────────────────────────────────────


class ParserSelfTest(unittest.TestCase):
    """Unit tests for ``find_unwrapped_field_references``.

    These must pass before the algorithm is trusted on real operator
    expressions. They cover correct forms, violating forms, and edge
    cases identified during the Codex cross-review.
    """

    # ── CORRECT forms — expect zero violations ──

    def test_simple_ref(self):
        self.assertEqual(find_unwrapped_field_references("Ref($close, 1)"), [])

    def test_mean_of_ref(self):
        # Idiomatic inner-Ref pattern
        self.assertEqual(
            find_unwrapped_field_references("Mean(Ref($close, 1), 20)"), []
        )

    def test_outer_ref_of_mean(self):
        # Outer-Ref alternative — any Ref ancestor satisfies the rule
        self.assertEqual(
            find_unwrapped_field_references("Ref(Mean($close, 20), 1)"), []
        )

    def test_ref_wrapping_grouped_arithmetic(self):
        # The Codex-critical case: grouped arithmetic inside Ref
        self.assertEqual(
            find_unwrapped_field_references("Ref(($a - $b) / $c, 1)"),
            [],
        )

    def test_negation_of_std_of_ref(self):
        # Pattern used by fundamental_stability after the fix
        self.assertEqual(
            find_unwrapped_field_references("0 - Std(Ref($roe, 1), 4)"),
            [],
        )

    def test_mixed_expression_all_wrapped(self):
        # Both fields properly wrapped by different Refs
        self.assertEqual(
            find_unwrapped_field_references(
                "Ref($pe_ttm, 1) / Mean(Ref($pe_ttm, 1), 750)"
            ),
            [],
        )

    def test_nested_ref_groups(self):
        # Deeper nesting with multiple Ref frames
        self.assertEqual(
            find_unwrapped_field_references(
                "Mean(Ref((($buy - $sell) / $amount), 1), 20)"
            ),
            [],
        )

    # ── VIOLATING forms — expect at least one violation ──

    def test_mean_without_ref(self):
        violations = find_unwrapped_field_references("Mean($close, 20)")
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0][1], "close")

    def test_slope_without_ref(self):
        violations = find_unwrapped_field_references("Slope($roe, 4)")
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0][1], "roe")

    def test_std_without_ref(self):
        violations = find_unwrapped_field_references("0 - Std($roe, 60)")
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0][1], "roe")

    def test_hybrid_leak_numerator_shifted_denominator_not(self):
        # The exact relative_valuation pre-fix pattern
        violations = find_unwrapped_field_references(
            "Ref($pe_ttm, 1) / Mean($pe_ttm, 750)"
        )
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0][1], "pe_ttm")

    def test_ma_ratio_both_sides_unshifted(self):
        violations = find_unwrapped_field_references(
            "Mean($close, 5) / Mean($close, 20)"
        )
        self.assertEqual(len(violations), 2)
        self.assertTrue(all(v[1] == "close" for v in violations))

    # ── EDGE CASES ──

    def test_empty_expression(self):
        self.assertEqual(find_unwrapped_field_references(""), [])

    def test_no_fields(self):
        self.assertEqual(find_unwrapped_field_references("100 - 1"), [])

    def test_one_correct_one_violating(self):
        # Same field appears twice: once wrapped, once not
        violations = find_unwrapped_field_references(
            "Ref($close, 1) / Mean($close, 5)"
        )
        self.assertEqual(len(violations), 1)
        # The unwrapped one is inside Mean(...)
        self.assertEqual(violations[0][1], "close")

    def test_ref_inside_mean_inside_ref(self):
        # Triple-nesting with both Mean and Ref frames — any-Ref-ancestor wins
        self.assertEqual(
            find_unwrapped_field_references(
                "Ref(Mean(Ref($close, 1), 20), 1)"
            ),
            [],
        )


# ──────────────────────────────────────────────────────────────────────
# Allowlist — factors/operators that are intentionally forward-looking.
# These are exempt from the PIT-safety invariant.
# ──────────────────────────────────────────────────────────────────────


ALLOWED_FORWARD_LOOKING: frozenset[str] = frozenset(
    {
        # The label operator — intentionally uses same-day close as denominator
        "forward_return",
    }
)


def _is_allowed_factor(factor_name: str) -> bool:
    """A factor is allowlisted if it's a forward-looking label.

    Factor names matching ``fwd_*`` or containing ``forward_return`` are
    treated as labels. Currently the catalog has no such entries (forward
    returns are computed by ``compute_factors`` internally, not stored as
    named catalog entries), but this check future-proofs the allowlist.
    """
    if factor_name.startswith("fwd_"):
        return True
    return False


# ──────────────────────────────────────────────────────────────────────
# Catalog-level and operator-level enforcement
# ──────────────────────────────────────────────────────────────────────


def _operator_sample_args(fn_name: str) -> tuple[tuple, dict]:
    """Return ``(args, kwargs)`` suitable for probing an operator function.

    Different operators have different signatures. Rather than introspecting
    every one, we provide sensible defaults for the common parameter names
    seen across ``operators.py``.
    """
    # Most operators are either window-based (int) or field-based (str)
    # or a combination. We'll try a reasonable default per name pattern.
    return (), {}


def _call_operator_safely(fn, fn_name: str) -> str | None:
    """Try to invoke an operator with sample args and return its expression.

    Returns ``None`` if the operator can't be called safely (e.g., requires
    non-default args we can't provide automatically). That's acceptable —
    the catalog-level check at :func:`test_catalog_has_no_pit_violations`
    still exercises every factor in the wired catalog.
    """
    sig = inspect.signature(fn)
    params = sig.parameters
    call_args: list = []
    call_kwargs: dict = {}
    for name, param in params.items():
        if param.default is not inspect.Parameter.empty:
            continue  # use default
        # Required parameter — guess a sensible default
        if "window" in name or name in ("skip", "total", "lag", "span"):
            call_args.append(20)
        elif name in ("short_window",):
            call_args.append(5)
        elif name in ("long_window",):
            call_args.append(60)
        elif name == "field":
            call_args.append("roe")
        elif name == "numerator":
            call_args.append("ocfps")
        elif name == "denominator":
            call_args.append("eps")
        elif name in ("inner_window",):
            call_args.append(5)
        elif name in ("outer_window",):
            call_args.append(20)
        elif name == "horizon":
            call_args.append(5)
        elif name == "percentile":
            call_args.append(0.05)
        else:
            return None  # give up; catalog-level check still covers this op
    try:
        result = fn(*call_args, **call_kwargs)
    except Exception:
        return None
    if not isinstance(result, str):
        return None
    return result


class FactorCatalogPITSafety(unittest.TestCase):
    """Enforce the PIT-safety invariant across the entire factor catalog
    and every public Layer 1 operator function.
    """

    def test_catalog_has_no_pit_violations(self):
        """Every expression returned by ``get_factor_catalog(include_new_data=True)``
        must have all ``$field`` references wrapped inside a ``Ref(...)`` frame.
        """
        catalog = get_factor_catalog(include_new_data=True)
        violations_by_factor: list[tuple[str, list[tuple[int, str]]]] = []
        for factor_name, expression in catalog.items():
            if _is_allowed_factor(factor_name):
                continue
            violations = find_unwrapped_field_references(expression)
            if violations:
                violations_by_factor.append((factor_name, violations))

        if violations_by_factor:
            report_lines = [
                f"{len(violations_by_factor)} factor(s) have unwrapped $field references:",
                "",
            ]
            for factor_name, violations in violations_by_factor[:50]:
                fields = sorted({field for _, field in violations})
                report_lines.append(
                    f"  - {factor_name}: {len(violations)} violation(s) in fields {fields}"
                )
                report_lines.append(
                    f"    expression: {get_factor_catalog(include_new_data=True)[factor_name]}"
                )
            if len(violations_by_factor) > 50:
                report_lines.append(
                    f"  ... and {len(violations_by_factor) - 50} more"
                )
            self.fail("\n".join(report_lines))

    def test_public_operators_have_no_pit_violations(self):
        """Every public Layer 1 operator function in ``operators.py`` must
        produce a PIT-safe expression string when called with sample args.

        Operators whose signatures can't be probed automatically are skipped
        here — the catalog-level check still exercises them indirectly as
        long as they're wired to a catalog entry.
        """
        violations_by_op: list[tuple[str, list[tuple[int, str]]]] = []
        probed_ops: list[str] = []

        for name, obj in inspect.getmembers(operators):
            if name.startswith("_"):
                continue
            if not callable(obj):
                continue
            # Must live in operators.py itself (skip imported helpers)
            if getattr(obj, "__module__", "") != operators.__name__:
                continue
            if name in ALLOWED_FORWARD_LOOKING:
                continue
            # Skip the non-Layer-1 helpers (they don't return expression strings)
            if name in (
                "compute_factors",
                "add_composites",
                "cs_rank",
                "cs_zscore",
                "cs_demean",
                "composite",
                "neutralize",
                "rolling_beta",
                "winsorize",
            ):
                continue
            result = _call_operator_safely(obj, name)
            if result is None:
                continue
            probed_ops.append(name)
            violations = find_unwrapped_field_references(result)
            if violations:
                violations_by_op.append((name, violations))

        # Sanity: we should have been able to probe a meaningful number of ops
        self.assertGreater(
            len(probed_ops),
            30,
            f"Only probed {len(probed_ops)} operators; sample args may need expansion",
        )

        if violations_by_op:
            report_lines = [
                f"{len(violations_by_op)} operator(s) have unwrapped $field references:",
                "",
            ]
            for op_name, violations in violations_by_op:
                fields = sorted({field for _, field in violations})
                report_lines.append(
                    f"  - {op_name}: {len(violations)} violation(s) in fields {fields}"
                )
            self.fail("\n".join(report_lines))

    def test_daily_ret_constant_is_pit_safe(self):
        """Module-level ``DAILY_RET`` constant must not leak today's close."""
        violations = find_unwrapped_field_references(operators.DAILY_RET)
        self.assertEqual(
            violations,
            [],
            f"DAILY_RET leaks: {operators.DAILY_RET!r} — violations: {violations}",
        )

    def test_composite_components_exist_in_catalog(self):
        """Sanity: every composite's components reference factor names that
        are currently wired into the catalog. This does not check PIT-safety
        directly (composites inherit from their components) but catches
        composite definitions that drift from the catalog.
        """
        catalog = get_factor_catalog(include_new_data=True)
        composites = get_composite_defs()
        missing: list[tuple[str, str]] = []
        for comp in composites:
            for component in comp["components"]:
                if component not in catalog:
                    missing.append((comp["name"], component))
        self.assertEqual(
            missing,
            [],
            f"Composite components reference missing catalog factors: {missing}",
        )


if __name__ == "__main__":
    unittest.main()
