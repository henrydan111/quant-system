# NF engine MECHANICAL invariant guards (GPT #25 repeat-class structural fold).
#
# CLAUDE.md §10 "repeat-class ⇒ structural chokepoint": when the same invariant
# class gates two rounds running, per-site patching is banned — the fold must be
# ONE shared chokepoint plus a MECHANICAL meta-test that enumerates the module
# surface, so a newly added function cannot silently reintroduce the class.
#
# Two classes have now gated twice each:
#   class 3 (rejection path runs caller code) — #24 and #25
#   class 5 (pre-type-gate read)              — #24 and #25
#
# Both had the same root shape: a security module doing its OWN type/normalize
# logic with `==` semantics or a `str()` fallback, instead of routing through the
# single primitive in news_seal.py. These tests AST-scan every NF security module
# and fail on the banned shapes — they are the enumeration guard, not a sample.
import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

ENGINE = Path(__file__).resolve().parents[1] / "engine"

#: the sealing / governance surface these invariants bind (everything an
#: untrusted in-process caller can reach through the archive boundary)
SECURITY_MODULES = (
    "news_seal.py", "news_evidence.py", "news_cards.py", "news_decision.py",
    "news_legs.py", "news_executors.py", "news_archive.py", "news_horizon.py",
)


def _iter_modules():
    for name in SECURITY_MODULES:
        p = ENGINE / name
        assert p.exists(), f"security module missing: {name}"
        yield name, ast.parse(p.read_text(encoding="utf-8"), filename=str(p))


def _is_type_call(node) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "type" and len(node.args) == 1)


class TestNoEqualitySemanticsOnTypeGates:
    """class 3/#25 P1#1 — `type(x) == C` / `type(x) in (...)` uses `==`, which a
    lying metaclass answers with its own `__eq__`: it both (a) lets an arbitrary
    object impersonate a plain scalar and (b) runs caller code on the rejection
    path. Exact-type gates must use `is` / `is not` identity, and plain-scalar
    tests must route through news_seal.is_plain_scalar."""

    def test_no_type_call_compared_with_equality_or_membership(self):
        banned = []
        for name, tree in _iter_modules():
            for node in ast.walk(tree):
                if not isinstance(node, ast.Compare):
                    continue
                operands = [node.left, *node.comparators]
                if not any(_is_type_call(o) for o in operands):
                    continue
                for op in node.ops:
                    if isinstance(op, (ast.Eq, ast.NotEq, ast.In, ast.NotIn)):
                        banned.append(f"{name}:{node.lineno} ({type(op).__name__})")
        assert not banned, (
            "type() compared with ==/!=/in/not in — a lying metaclass controls the "
            "answer AND runs on the rejection path. Use `is`/`is not`, or "
            "news_seal.is_plain_scalar for plain-scalar tests. Offenders: "
            + "; ".join(banned))


class TestSingleStrNormalizationChokepoint:
    """class 5/#25 P1#2 — the fork. news_evidence used to carry its own
    `_plain_str` whose fallback was `str(x)`: that runs an untrusted object's
    `__str__` at a snapshot boundary AND returns whatever it produced (a str
    SUBCLASS passes straight through), defeating the "independent plain-typed
    snapshot" guarantee. There must be exactly ONE normalizer, it must be
    fail-closed, and no security module may re-derive one via bare `str(...)`."""

    def test_plain_str_is_fail_closed_and_flattens_subclasses(self):
        from workspace.research.ai_research_dept.engine.news_seal import (
            SealError, plain_str,
        )

        class _Evil:
            def __str__(self):
                raise AssertionError("__str__ must never be called")
        with pytest.raises(SealError):
            plain_str(_Evil())                       # non-str → static refusal

        class _EvilStr(str):
            def __str__(self):
                raise AssertionError("__str__ must never be called")
        out = plain_str(_EvilStr("x"))
        assert type(out) is str and out == "x"       # subclass flattened, no hook

    def test_no_security_module_stringifies_via_bare_str_call(self):
        # `str(x)` on an untrusted value is the exact shape that produced #25 P1#2.
        # Whitelist: only positions where the argument is provably not caller data.
        WHITELIST = {
            ("news_horizon.py", "sys.path bootstrap"): {43, 44},
        }
        allowed = {(m, ln) for (m, _why), lns in WHITELIST.items() for ln in lns}
        banned = []
        for name, tree in _iter_modules():
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                        and node.func.id == "str" and node.args
                        and (name, node.lineno) not in allowed):
                    banned.append(f"{name}:{node.lineno}")
        assert not banned, (
            "bare str(x) in a security module — it runs the object's __str__ "
            "(caller code) and returns whatever that produced, including a str "
            "SUBCLASS. Route through news_seal.plain_str (fail-closed) or render "
            "diagnostics with safe_repr/safe_kind. Offenders: " + "; ".join(banned))


class TestReviewerReproducedProbes:
    """the two probes GPT #25 reproduced against 4b14542, pinned."""

    def test_lying_metaclass_cannot_impersonate_plain_scalar(self):
        # #25 P1#1: `type(x) in (bool,int,float)` answered by a lying metaclass.
        # is_plain_scalar uses all-`is`, so the metaclass __eq__/__hash__/__repr__
        # never run and the impostor is refused.
        from workspace.research.ai_research_dept.engine.news_seal import (
            is_plain_scalar,
        )
        fired = {"n": 0}

        class _LiarMeta(type):
            def __eq__(cls, o):
                fired["n"] += 1
                return True
            def __hash__(cls):
                fired["n"] += 1
                return hash(int)
            def __repr__(cls):
                fired["n"] += 1
                return "<class 'int'>"

        class _Liar(metaclass=_LiarMeta):
            pass
        assert is_plain_scalar(_Liar()) is False
        assert fired["n"] == 0                       # no metaclass hook ran

    def test_registry_snapshot_refuses_object_whose_str_returns_subclass(self):
        # #25 P1#2: an object whose __str__ returns a str SUBCLASS used to pass
        # the old `_plain_str` fork's `str(x)` fallback — verify_d7_artifact then
        # returned an artifact whose final_registry.cutoff_iso was NOT exactly str.
        # The snapshot now statically refuses before any __str__ runs.
        from workspace.research.ai_research_dept.engine.news_evidence import (
            RegistryError, SealedCardRegistry,
        )
        fired = {"str": 0}

        class _SubStr(str):
            pass

        class _EvilCutoff:
            def __str__(self):
                fired["str"] += 1
                return _SubStr("2025-01-27T18:00:00")
        with pytest.raises(RegistryError, match="须为 str"):
            SealedCardRegistry(cutoff_iso=_EvilCutoff(), records={},
                               registry_hash="0" * 64)
        assert fired["str"] == 0                     # __str__ never ran


class TestLedgerIdentityGate:
    """GPT #27 P1#2 — `disk_str == caller_id` calls a str subclass's reflected
    __eq__, so an object whose real value is 'attacker-id' but whose __eq__ is
    always True gets back the TRUSTED ledger row of a different decision. That is
    not a benign rejection-path callback: it returns trusted data under the wrong
    identity = v2 decision-flip / leak. Every reader that compares a caller id
    against disk strings must pass news_decision.require_exact_id FIRST."""

    #: every public/boundary reader that takes a caller id into a disk comparison
    GATED_READERS = (
        ("news_decision", "lookup_decision", ("decision_id",)),
        ("news_decision", "find_success_commitment", ("decision_id",)),
        ("news_decision", "find_execution_commitment",
         ("decision_id", "execution_id")),
        ("news_archive", "_find_success_commitment", ("decision_id",)),
        ("news_archive", "_find_commitment", ("decision_id", "execution_id")),
    )

    def test_every_ledger_reader_refuses_str_subclass_ids(self, tmp_path):
        # MECHANICAL surface enumeration: each reader, each id parameter, probed
        # with an always-equal str subclass. A newly added reader that forgets the
        # gate is caught by adding it to GATED_READERS (and by the source scan
        # below, which fails if a reader compares an id without calling the gate).
        import importlib
        from workspace.research.ai_research_dept.engine.news_evidence import (
            RegistryError,
        )
        fired = {"eq": 0}

        class _EvilId(str):
            def __eq__(self, o):
                fired["eq"] += 1
                return True
            def __ne__(self, o):
                fired["eq"] += 1
                return False
            def __hash__(self):
                return hash(str.__str__(self))
        for mod_name, fn_name, id_params in self.GATED_READERS:
            mod = importlib.import_module(
                f"workspace.research.ai_research_dept.engine.{mod_name}")
            fn = getattr(mod, fn_name)
            first = tmp_path if mod_name == "news_decision" else []
            for bad in range(len(id_params)):
                args = [first] + ["ok-id"] * len(id_params)
                args[1 + bad] = _EvilId("attacker-id")
                with pytest.raises(RegistryError, match="须恰 str 非空"):
                    fn(*args)
        assert fired["eq"] == 0                          # no redirect ever ran

    #: the three sanctioned ways an id becomes exactly-str before a row compare.
    #: GPT #28 non-blocking hardening: the marker must name the SPECIFIC id
    #: parameter being compared — a function-level marker scan would let an
    #: unrelated `type(raw) is not str` elsewhere in the body wave the check
    #: through. Still a syntactic check, not a dataflow proof; the runtime probe
    #: above is the behavioural half of the guarantee.
    @staticmethod
    def _gate_markers(param: str) -> tuple:
        return (f"require_exact_id({param}",
                f"type({param}) is not str",
                f"{param} = _deep_plain_json(")

    def test_no_ledger_reader_compares_an_id_without_the_gate(self):
        # Source guard for the PRECISE lookup shape: a ROW's id field compared
        # against a bare parameter name — `e["decision_id"] == decision_id` or
        # `r.get("execution_id") == execution_id`. That is the shape whose result
        # a str subclass's __eq__ can redirect. (Field-binding comparisons like
        # `row["decision_id"] != outcome.decision_id` compare against an already
        # snapshotted attribute, not a raw caller name, and are not this shape.)
        import ast
        ID_KEYS = ("decision_id", "execution_id")

        def _reads_row_id(node):
            if isinstance(node, ast.Subscript):         # e["decision_id"]
                s = node.slice
                return isinstance(s, ast.Constant) and s.value in ID_KEYS
            if (isinstance(node, ast.Call)              # r.get("decision_id")
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get" and node.args):
                a = node.args[0]
                return isinstance(a, ast.Constant) and a.value in ID_KEYS
            return False

        offenders = []
        for name in SECURITY_MODULES:
            src = (ENGINE / name).read_text(encoding="utf-8")
            tree = ast.parse(src, filename=name)
            for fn in ast.walk(tree):
                if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                params = {a.arg for a in fn.args.args} | {a.arg for a in fn.args.kwonlyargs}
                # markers are matched against real SOURCE text — `type(x) is not
                # str` renders as IsNot()/Name('str') in ast.dump and would be missed
                seg = ast.get_source_segment(src, fn) or ""
                for cmp_node in ast.walk(fn):
                    if not isinstance(cmp_node, ast.Compare):
                        continue
                    if not any(isinstance(o, ast.Eq) for o in cmp_node.ops):
                        continue
                    ops = [cmp_node.left, *cmp_node.comparators]
                    if not any(_reads_row_id(o) for o in ops):
                        continue
                    # GPT #28: the gate must name THIS parameter, not merely exist
                    ungated = [o.id for o in ops
                               if isinstance(o, ast.Name) and o.id in params
                               and not any(m in seg
                                           for m in self._gate_markers(o.id))]
                    if ungated:
                        offenders.append(
                            f"{name}:{fn.lineno} {fn.name}({', '.join(ungated)})")
                        break
        assert not offenders, (
            "a function compares a caller id against ledger rows without routing "
            "through news_decision.require_exact_id — a str subclass's __eq__ can "
            "redirect the lookup to another decision's trusted row. Offenders: "
            + "; ".join(offenders))


class TestExecutionEntrySnapshotsContract:
    """GPT #27 P1#1 — execute_news_decision (the sole public entry) only called
    require_exact_contract, which VERIFIES but returns the LIVE object. The
    registry's .items() callback could then swap the verified contract for a
    different SELF-CONSISTENT one (primary_horizon/1-3d → vector_only/None with a
    recomputed hash), and run_news_two_legs / evaluation / commit_execution all
    used the swapped version — an accepted substitution flowing into the
    commitment and the archive (v2 class 2/4, not a benign callback)."""

    def test_registry_callback_cannot_swap_the_executing_contract(self, tmp_path):
        import test_news_archive as ta                  # reuse the fixtures
        from workspace.research.ai_research_dept.engine.news_decision import (
            record_decision,
        )
        from workspace.research.ai_research_dept.engine.news_executors import (
            NewsScoringContract, execute_news_decision,
        )
        art = ta._artifact_full("d1")
        record_decision(tmp_path / "ledger", "d1", art)
        contract = ta._contract()
        swapped = {"n": 0}

        class _SwapMap(dict):
            def items(self):
                # substitute a DIFFERENT but self-consistent contract
                swapped["n"] += 1
                object.__setattr__(contract, "output_mode", "vector_only")
                object.__setattr__(contract, "primary_decision_horizon", None)
                object.__setattr__(contract, "contract_hash", NewsScoringContract(
                    schema_id=contract.schema_id, output_mode="vector_only",
                    primary_decision_horizon=None).contract_hash)
                return super().items()
        object.__setattr__(art.final_registry, "records",
                           _SwapMap(dict(art.final_registry.records)))
        bundle = execute_news_decision(
            art, ledger_dir=tmp_path / "ledger", prov_dir=tmp_path / "prov",
            decision_id="d1", contract=contract, call_fn=ta._call_fn())
        assert swapped["n"] > 0                          # the callback DID fire
        # the entry snapshot froze the ORIGINAL contract: the executed outcome is
        # primary_horizon, not the substituted vector_only
        assert bundle["outcome"].output_mode == "primary_horizon"
        assert bundle["evaluation"] is not None          # vector_only has no scalar


class TestCanonRejectsNonStrFallback:
    """same class on the HASH path: canon()'s fallback used to `str(v)` an
    arbitrary object straight into the seal hash."""

    def test_canon_refuses_non_str_fallback(self):
        from workspace.research.ai_research_dept.engine.news_seal import (
            SealError, canon,
        )

        class _Evil:
            def __str__(self):
                raise AssertionError("__str__ must never be called")
        with pytest.raises(SealError):
            canon(_Evil())

    def test_canon_str_path_unchanged(self):
        from workspace.research.ai_research_dept.engine.news_seal import canon
        assert canon("  a\tb\n c ") == "a b c"       # whitespace folding preserved
