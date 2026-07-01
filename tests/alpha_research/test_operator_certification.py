"""Tests for the P-OP OperatorCertification skeleton (roadmap §10A)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.alpha_research.factor_library.operator_certification import (
    CERT_TEST_KINDS,
    OperatorCertStore,
    resolve_operator_status,
    run_certification,
)


class TestResolveOperatorStatus:
    def test_all_pass_certified(self):
        d = resolve_operator_status("op", {k: True for k in CERT_TEST_KINDS})
        assert d.status == "certified" and d.failed == () and d.missing == ()

    def test_any_explicit_fail_blocks(self):
        tr = {k: True for k in CERT_TEST_KINDS}
        tr["pit_alignment"] = False
        d = resolve_operator_status("op", tr)
        assert d.status == "blocked" and "pit_alignment" in d.failed

    def test_missing_required_is_experimental(self):
        d = resolve_operator_status("op", {"golden_panel": True})
        assert d.status == "experimental" and "pit_alignment" in d.missing


class TestHarness:
    def _panels(self, n=10, length=60):
        return [pd.Series(np.random.default_rng(i).standard_normal(length)) for i in range(n)]

    def test_correct_operator_passes_random_and_pit(self):
        w = 5
        fn = lambda s: s.rolling(w, min_periods=w).mean()  # noqa: E731 — causal rolling mean
        r = run_certification(operator_id="rm", reference_fn=fn, vectorized_fn=fn,
                              random_panels=self._panels(), window_for_pit=w)
        assert r["reference_vs_vectorized_random"] is True
        assert r["pit_alignment"] is True

    def test_lookahead_operator_fails_pit_and_reference(self):
        # a vectorized impl that peeks one step into the FUTURE must fail both the
        # reference cross-check and the PIT-causality test.
        w = 5
        ref = lambda s: s.rolling(w, min_periods=w).mean()           # noqa: E731 — causal oracle
        bad = lambda s: s.shift(-1).rolling(w, min_periods=w).mean()  # noqa: E731 — uses s[t+1]
        r = run_certification(operator_id="bad", reference_fn=ref, vectorized_fn=bad,
                              random_panels=self._panels(), window_for_pit=w)
        assert r["reference_vs_vectorized_random"] is False
        assert r["pit_alignment"] is False

    def test_wrong_but_causal_operator_fails_reference_only(self):
        # off-by-window: still causal (passes PIT) but wrong vs the reference.
        w = 5
        ref = lambda s: s.rolling(w, min_periods=w).mean()        # noqa: E731
        bad = lambda s: s.rolling(w + 3, min_periods=w + 3).mean()  # noqa: E731 — wrong window
        r = run_certification(operator_id="ob", reference_fn=ref, vectorized_fn=bad,
                              random_panels=self._panels(), window_for_pit=w + 3)
        assert r["reference_vs_vectorized_random"] is False
        assert r["pit_alignment"] is True   # wrong, but not a lookahead


class TestOperatorCertStore:
    def test_failclosed_then_certify(self, tmp_path):
        s = OperatorCertStore(tmp_path)
        assert s.status_of("x") == "blocked"          # no record -> uncertified (fail-closed)
        dec = s.certify(operator_id="x", test_results={k: True for k in CERT_TEST_KINDS},
                        spec_source="spec", formula_text="f", reference_impl_hash="r",
                        vectorized_impl_hash="v", alignment_policy={"lag": 0})
        assert dec.status == "certified"
        assert s.status_of("x") == "certified" and "x" in s.certified_operators()

    def test_blocked_cert_not_in_certified_set(self, tmp_path):
        s = OperatorCertStore(tmp_path)
        tr = {k: True for k in CERT_TEST_KINDS}
        tr["golden_panel"] = False
        dec = s.certify(operator_id="y", test_results=tr, spec_source="s", formula_text="f",
                        reference_impl_hash="r", vectorized_impl_hash="v", alignment_policy={})
        assert dec.status == "blocked"
        assert "y" not in s.certified_operators() and s.status_of("y") == "blocked"

    def test_certify_is_idempotent_on_operator_id(self, tmp_path):
        s = OperatorCertStore(tmp_path)
        for _ in range(2):
            s.certify(operator_id="z", test_results={k: True for k in CERT_TEST_KINDS},
                      spec_source="s", formula_text="f", reference_impl_hash="r",
                      vectorized_impl_hash="v", alignment_policy={})
        assert len(s.records()) == 1

    def test_per_window_results_persisted_and_status_unaffected(self, tmp_path):
        """GPT E1a-gate finding 2: a multi-window cert persists BOTH windows' full results in the
        first-class per_window_results_json column (audit-complete), while status still resolves from
        the flat test_results (the conservative/deepest window)."""
        import json
        s = OperatorCertStore(tmp_path)
        pw = {"W20": {k: True for k in CERT_TEST_KINDS}, "W250": {k: True for k in CERT_TEST_KINDS}}
        dec = s.certify(operator_id="multi", test_results={k: True for k in CERT_TEST_KINDS},
                        spec_source="s", formula_text="f", reference_impl_hash="r",
                        vectorized_impl_hash="v", alignment_policy={}, per_window_results=pw)
        assert dec.status == "certified"
        row = s.records()
        rec = row[row["operator_id"] == "multi"].iloc[-1]
        assert json.loads(rec["per_window_results_json"]) == pw    # both windows durably present
        # a cert WITHOUT per-window payload defaults to "{}" (back-compat) and still certifies
        s.certify(operator_id="single", test_results={k: True for k in CERT_TEST_KINDS},
                  spec_source="s", formula_text="f", reference_impl_hash="r",
                  vectorized_impl_hash="v", alignment_policy={})
        r2 = s.records()
        assert json.loads(r2[r2["operator_id"] == "single"].iloc[-1]["per_window_results_json"]) == {}
        assert "per_window_results_json" in s.records().columns   # schema stable for old+new rows
