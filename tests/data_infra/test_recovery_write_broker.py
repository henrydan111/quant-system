"""No-follow handle write broker (GPT recovery B3): junction-swap TOCTOU, broken junction, containment,
and the no-follow source walker. Windows-only (the broker fails closed elsewhere). Runs under C:."""
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("rwb", ROOT / "scripts" / "recovery_write_broker.py")
rwb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rwb)

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="broker is Windows-only")


def _recovery_test_root(sub: str) -> Path:
    """A writable NON-E: root for the recovery batteries.

    NOT pytest tmp_path and NOT tempfile.mkdtemp(): this repo points tmp_path *and* TEMP at
    E:\\量化系统\\workspace\\outputs\\pytest_runtime_tmp, and the coordinator REFUSES every E: write by
    design — that refusal is the invariant under test, so running these there would test nothing.
    Default is the sanctioned C:\\quant_recovery area; set QUANT_RECOVERY_TEST_ROOT to any writable
    non-E: path if that drive is unavailable (GPT re-review #8: a sandboxed reviewer could not write it,
    so the full battery could not serve as passing evidence)."""
    base = Path(os.environ.get("QUANT_RECOVERY_TEST_ROOT") or r"C:\quant_recovery")
    # GPT re-review #10 MINOR: VALIDATE the root BEFORE creating or writing anything — the previous
    # order mkdir'd/wrote a relative or E: override before rejecting it.
    if not base.is_absolute():
        pytest.skip(f"QUANT_RECOVERY_TEST_ROOT {base} must be ABSOLUTE")
    if base.drive.upper() == "E:":
        pytest.skip(f"recovery test root must be NON-E: (E: is refused by the coordinator by design); "
                    f"got {base}")
    try:
        base.mkdir(parents=True, exist_ok=True)
        probe = base / f".writeprobe_{uuid.uuid4().hex}"
        probe.write_bytes(b"x")
        probe.unlink()
    except OSError as exc:
        pytest.skip(f"recovery test root {base} is not writable ({exc}); set QUANT_RECOVERY_TEST_ROOT to "
                    f"a writable NON-E: path (E: is refused by the coordinator by design)")
    return base / sub / uuid.uuid4().hex


@pytest.fixture()
def broot():
    base = _recovery_test_root("brokertest")
    base.mkdir(parents=True)
    yield base
    shutil.rmtree(base, ignore_errors=True)


def test_broker_off_windows_fails_closed(monkeypatch):
    monkeypatch.setattr(rwb.sys, "platform", "linux")
    with pytest.raises(rwb.WriteBrokerError, match="Windows"):
        rwb.NoFollowWriteBroker(Path("/tmp/x"))


def test_write_and_mkdirs_inside_root(broot):
    b = rwb.NoFollowWriteBroker(broot)
    with b.open_for_write(broot / "a" / "b" / "f.txt") as fh:
        fh.write(b"ok")
    assert (broot / "a" / "b" / "f.txt").read_bytes() == b"ok"


def test_write_outside_root_refused(broot):
    b = rwb.NoFollowWriteBroker(broot)
    with pytest.raises(rwb.WriteBrokerError, match="outside root"):
        b.validate_ancestry(broot.parent / "sibling" / "f.txt")
    with pytest.raises(rwb.WriteBrokerError, match="outside root"):
        b.validate_ancestry(Path(str(broot) + "_evil") / "f.txt")  # sibling-prefix


def test_junction_component_refused(broot):
    import _winapi
    b = rwb.NoFollowWriteBroker(broot)
    outside = broot.parent / ("target_" + uuid.uuid4().hex)
    outside.mkdir()
    try:
        junc = broot / "j"
        _winapi.CreateJunction(str(outside), str(junc))  # junction inside root -> points OUTSIDE
        # lexically junc/f.txt is "under" root, but the handle's real path escapes -> refuse
        with pytest.raises(rwb.WriteBrokerError, match="reparse point|outside root"):
            b.validate_ancestry(junc / "f.txt")
    finally:
        shutil.rmtree(outside, ignore_errors=True)


def test_broken_junction_component_refused(broot):
    import _winapi
    b = rwb.NoFollowWriteBroker(broot)
    tgt = broot / "tmp_tgt"
    tgt.mkdir()
    junc = broot / "bj"
    _winapi.CreateJunction(str(tgt), str(junc))
    tgt.rmdir()  # broken
    with pytest.raises(rwb.WriteBrokerError, match="reparse point"):
        b.validate_ancestry(junc / "f.txt")


def test_source_walker_refuses_reparse(broot):
    import _winapi
    (broot / "sub").mkdir()
    (broot / "sub" / "real.parquet").write_bytes(b"D")
    outside = broot.parent / ("wt_" + uuid.uuid4().hex)
    outside.mkdir()
    try:
        _winapi.CreateJunction(str(outside), str(broot / "sub" / "junc"))
        with pytest.raises(rwb.WriteBrokerError, match="reparse point"):
            list(rwb.walk_no_follow(broot))
    finally:
        shutil.rmtree(outside, ignore_errors=True)


def test_assert_no_reparse_source_broken_leaf(broot):
    import _winapi
    tgt = broot / "t2"
    tgt.mkdir()
    junc = broot / "bl"
    _winapi.CreateJunction(str(tgt), str(junc))
    tgt.rmdir()
    with pytest.raises(rwb.WriteBrokerError, match="reparse point"):
        rwb.assert_no_reparse_source(junc)


# ── GPT re-review #5 F1 BLOCKER: the reproduced scan->write TOCTOU + hardlink ─────────────────────
def test_ancestor_junction_swapped_INSIDE_validation_window_refused(broot, monkeypatch):
    """GPT re-review #5 F1: the REAL TOCTOU — the swap lands AFTER open_for_write's own validation and
    BEFORE the write. Deterministically simulated by racing the swap in as validate_ancestry returns.
    The OLD pathname `open(target, ...)` re-walked the path and wrote OUTSIDE the root here; the
    handle-relative chain opens 'sub' relative to a held root handle, sees the reparse point, refuses."""
    import _winapi
    root = broot / "root"; root.mkdir()
    outside = broot / "outside"; outside.mkdir()
    child = root / "sub"; child.mkdir()
    b = rwb.NoFollowWriteBroker(root)
    target = child / "f.txt"
    orig_validate = b.validate_ancestry
    swapped = {"done": False}

    def racing_validate(t):
        res = orig_validate(t)           # validation PASSES: 'sub' is still a genuine directory
        if not swapped["done"]:          # ---- the TOCTOU window opens here ----
            swapped["done"] = True
            child.rmdir()
            _winapi.CreateJunction(str(outside), str(child))
        return res

    monkeypatch.setattr(b, "validate_ancestry", racing_validate)
    with pytest.raises(rwb.WriteBrokerError, match="reparse point"):
        with b.open_for_write(target, "wb") as fh:
            fh.write(b"ESCAPED")
    assert swapped["done"], "probe never armed — the TOCTOU window was not exercised"
    assert not (outside / "f.txt").exists(), "broker wrote OUTSIDE the root through a swapped junction"


def test_hardlinked_target_refused(broot):
    """A hard link inside the root aliasing a file OUTSIDE it must refuse (nNumberOfLinks > 1) and the
    aliased file must keep its bytes — truncation happens only after the leaf proves safe."""
    import os
    root = broot / "root"; root.mkdir()
    outside_file = broot / "outside.bin"
    outside_file.write_bytes(b"ORIGINAL")
    target = root / "linked.bin"
    os.link(outside_file, target)        # same volume; target aliases the outside file
    b = rwb.NoFollowWriteBroker(root)
    with pytest.raises(rwb.WriteBrokerError, match="hard link"):
        with b.open_for_write(target, "wb") as fh:
            fh.write(b"CLOBBERED")
    assert outside_file.read_bytes() == b"ORIGINAL", "hard-linked outside file was clobbered"
