"""No-follow handle write broker (GPT recovery B3): junction-swap TOCTOU, broken junction, containment,
and the no-follow source walker. Windows-only (the broker fails closed elsewhere). Runs under C:."""
from __future__ import annotations

import importlib.util
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


@pytest.fixture()
def broot():
    base = Path(r"C:\quant_recovery") / "brokertest" / uuid.uuid4().hex
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
