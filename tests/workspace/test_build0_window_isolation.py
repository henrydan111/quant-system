# Integration guards for the BUILD-0 TC PoC: window isolation (no row/metric past IS_END ever enters a
# computation), no OOS CLI path, and the a_priori==is_fit orientation equivalence that proves the composite
# carries no cross-time fitted parameter (no orientation lookahead). Requested by the GPT §10 REWORK.
import inspect
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "workspace" / "scripts"))
CACHE = ROOT / "workspace" / "outputs" / "guorn_parity" / "optimize09_cache"

pytestmark = pytest.mark.skipif(
    not (CACHE / "returns.parquet").exists() or not (CACHE / "is_ic.json").exists(),
    reason="BUILD-0 caches (panel/returns/is_ic) not present on this host",
)
import build0_tc_poc as b0  # noqa: E402


def test_setup_truncates_every_input_to_is_end():
    (_cfg, _cols, close, circ, ret, fwd5, mkt, frames, _efr, _ind, _bounds, rebal, _pmap) = b0._setup()
    end = pd.Timestamp(b0.IS_END)
    for nm, fr in (("close", close), ("circ", circ), ("ret", ret), ("fwd5", fwd5), ("mkt", mkt)):
        assert fr.index.max() <= end, f"{nm} leaks rows past IS_END ({fr.index.max()})"
    for f, fr in frames.items():
        assert fr.index.max() <= end, f"factor {f} leaks past IS_END"
    assert all(pd.Timestamp(d) <= end for d in rebal)


def test_no_oos_window_path_in_cli():
    # The script must expose no way to run/observe the sealed 2021-2026 window: no OOS window constants,
    # no --window selector, and the run path is hard-bound to IS_START..IS_END.
    assert not hasattr(b0, "OOS_START") and not hasattr(b0, "OOS_END"), "OOS window constant defined"
    assert "--window" not in inspect.getsource(b0.main), "a --window selector could pick OOS"
    rb = inspect.getsource(b0.run_book)
    assert "IS_START" in rb and "IS_END" in rb, "run path is not bound to the IS window"
    assert "oos" not in rb.lower(), "the run path references OOS"


def test_orientation_equivalence_retrospective_consistency():
    # a_priori (economic-prior signs) reproduces is_fit (IS-IC-fit signs) bit-for-bit. NOTE: this is a
    # RETROSPECTIVE consistency check (the a-priori sign map was committed after is_ic.json existed), not
    # proof of no orientation lookahead — the recipe is a_priori_is_informed (FINDINGS §7 B2).
    r = b0.verify_orientation_equivalence()
    assert r["identical"] is True
    assert r["max_abs_comp_diff"] < 1e-9
    assert r["topk_selection_symdiff"] == 0


def test_ic_labels_realized_within_is_window():
    # B1: the composite IS rank-IC must use only labels realized <= IS_END. prepare() records the max
    # label-realization date; assert it never crosses the boundary (skip if the tag has not been prepared).
    import json
    p = CACHE / "build0_ref_tc.json"
    if not p.exists():
        pytest.skip("build0_ref_tc.json not present — run prepare first")
    j = json.loads(p.read_text())
    mr = j.get("max_ic_label_realization")
    assert mr is not None and mr <= b0.IS_END, f"IC used a label realized {mr} > IS_END"
