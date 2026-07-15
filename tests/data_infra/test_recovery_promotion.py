"""Recovery FOUNDATION 5/5 — promotion state-machine battery (GPT recovery re-review #4 M3).

Crash injection BEFORE/AFTER every rename and journal transition (GPT §6 test requirement): the harness
raises InjectedCrash at each labelled checkpoint, then a FRESH coordinator resumes from the durable
journal + on-disk facts and MUST converge to SWAPPED with byte-identical live content. Network-free;
everything runs under tmp_path (one volume, so os.replace renames are atomic)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

_spec = importlib.util.spec_from_file_location("recovery_promotion", ROOT / "scripts" / "recovery_promotion.py")
rp = importlib.util.module_from_spec(_spec)
sys.modules["recovery_promotion"] = rp
_spec.loader.exec_module(rp)

_ALL_CRASH_LABELS = ["after_copy_intent", "after_copy", "after_copy_verified", "after_move_intent",
                     "after_move_rename", "after_old_moved", "after_install_intent",
                     "after_install_rename", "after_new_installed", "after_live_verified", "after_swapped"]


def _build(tmp_path: Path, family="market/daily", make_live=True):
    """A tiny staging tree on 'C:' + a live tree on 'E:' (both under tmp_path = one volume)."""
    staging = tmp_path / "cstage" / family
    staging.mkdir(parents=True)
    (staging / "2026").mkdir()
    (staging / "2026" / "daily_20260703.parquet").write_bytes(b"RECOVERED-A" * 100)
    (staging / "2026" / "daily_20260704.parquet").write_bytes(b"RECOVERED-B" * 100)
    data_root = tmp_path / "edata"
    live = data_root / family
    if make_live:
        live.mkdir(parents=True)
        (live / "stale.parquet").write_bytes(b"STALE")  # pre-incident junk to be tombstoned
    manifest = rp._manifest_from_dir(staging)
    fp = rp.FamilyPlan(
        family=family, staging_dir=staging, live_dir=live,
        incoming_dir=data_root / ".recovery_incoming" / "run1" / family,
        tombstone_dir=data_root / ".recovery_tombstone" / "run1" / family,
        manifest=manifest)
    journal = rp.PromotionJournal(data_root / ".recovery_journal.jsonl")
    return fp, journal, data_root, manifest


def _live_matches_staging(fp) -> bool:
    return rp._manifest_from_dir(fp.live_dir) == fp.manifest


def test_happy_path_promotes_and_tombstones(tmp_path):
    fp, journal, data_root, manifest = _build(tmp_path)
    coord = rp.PromotionCoordinator("run1", data_root, journal, [fp])
    final = coord.promote_all()
    assert final[fp.family] == rp.SWAPPED
    assert _live_matches_staging(fp)                 # recovered content is now live
    assert not fp.incoming_dir.exists()              # incoming consumed
    assert fp.tombstone_dir.exists()                 # old content preserved as tombstone
    assert (fp.tombstone_dir / "stale.parquet").read_bytes() == b"STALE"


@pytest.mark.parametrize("label", _ALL_CRASH_LABELS)
def test_crash_at_every_checkpoint_resumes_to_swapped(tmp_path, label):
    fp, journal, data_root, manifest = _build(tmp_path)

    def crash(l):
        if l == label:
            raise rp.InjectedCrash(l)

    crashed = rp.PromotionCoordinator("run1", data_root, journal, [fp], crash_hook=crash)
    with pytest.raises(rp.InjectedCrash):
        crashed.promote_all()
    # a FRESH coordinator (no crash hook) resumes from the durable journal + facts
    resumed = rp.PromotionCoordinator("run1", data_root, journal, [fp])
    final = resumed.promote_all()
    assert final[fp.family] == rp.SWAPPED, f"did not converge after crash@{label}"
    assert _live_matches_staging(fp), f"live content wrong after crash@{label}"
    assert not fp.incoming_dir.exists()


def test_lost_family_no_live_dir_still_installs(tmp_path):
    # the incident DELETED the family — live_dir never existed. Promotion must still install incoming.
    fp, journal, data_root, manifest = _build(tmp_path, make_live=False)
    assert not fp.live_dir.exists()
    final = rp.PromotionCoordinator("run1", data_root, journal, [fp]).promote_all()
    assert final[fp.family] == rp.SWAPPED
    assert _live_matches_staging(fp)
    assert not fp.tombstone_dir.exists()  # nothing to tombstone (OLD_ABSENT)


def test_foreign_incoming_refused(tmp_path):
    # a pre-existing incoming with NO owning journal intent = foreign collision -> refuse
    fp, journal, data_root, manifest = _build(tmp_path)
    fp.incoming_dir.mkdir(parents=True)
    (fp.incoming_dir / "foreign.parquet").write_bytes(b"NOT OURS")
    with pytest.raises(rp.PromotionError, match="foreign collision"):
        rp.PromotionCoordinator("run1", data_root, journal, [fp]).promote_all()


def test_corrupt_incoming_fails_verification(tmp_path):
    # a copy whose bytes don't match the frozen manifest must fail COPY_VERIFIED (no move happens)
    fp, journal, data_root, manifest = _build(tmp_path)
    # corrupt the staging source AFTER freezing the manifest -> the copied incoming won't match
    (fp.staging_dir / "2026" / "daily_20260703.parquet").write_bytes(b"CORRUPT")
    with pytest.raises(rp.PromotionError, match="incoming != frozen manifest"):
        rp.PromotionCoordinator("run1", data_root, journal, [fp]).promote_all()
    assert fp.live_dir.exists() and (fp.live_dir / "stale.parquet").exists()  # live untouched


def test_duplicate_family_in_set_refused(tmp_path):
    fp, journal, data_root, manifest = _build(tmp_path)
    with pytest.raises(rp.PromotionError, match="duplicate family"):
        rp.PromotionCoordinator("run1", data_root, journal, [fp, fp])


def test_sentinel_blocks_consumers(tmp_path):
    fp, journal, data_root, manifest = _build(tmp_path)
    coord = rp.PromotionCoordinator("run1", data_root, journal, [fp])
    rp.assert_no_active_recovery(data_root)  # no sentinel yet -> ok
    coord.write_sentinel()
    with pytest.raises(rp.PromotionError, match="RECOVERY_IN_PROGRESS"):
        rp.assert_no_active_recovery(data_root)
    coord.clear_sentinel()
    rp.assert_no_active_recovery(data_root)  # cleared -> ok again


def test_recovery_table_is_total_and_deterministic():
    # every mapped (state, live, incoming, tomb) yields ONE action; representative pins + unmapped raises
    assert rp.recovery_action(None, True, False, False) == rp.ACT_COPY
    assert rp.recovery_action(None, False, False, False) == rp.ACT_COPY  # lost family
    with pytest.raises(rp.PromotionError, match="foreign collision"):
        rp.recovery_action(None, True, True, False)                       # foreign incoming
    assert rp.recovery_action(rp.COPY_VERIFIED, True, True, False) == rp.ACT_MOVE_OLD
    assert rp.recovery_action(rp.MOVE_OLD_INTENT, True, True, False) == rp.ACT_MOVE_OLD       # pre-rename
    assert rp.recovery_action(rp.MOVE_OLD_INTENT, False, True, True) == rp.ACT_INSTALL_NEW    # post-rename
    assert rp.recovery_action(rp.INSTALL_NEW_INTENT, False, True, True) == rp.ACT_INSTALL_NEW  # pre-rename
    assert rp.recovery_action(rp.INSTALL_NEW_INTENT, True, False, True) == rp.ACT_VERIFY_LIVE  # post-rename
    assert rp.recovery_action(rp.NEW_INSTALLED, True, False, True) == rp.ACT_VERIFY_LIVE
    assert rp.recovery_action(rp.LIVE_VERIFIED, True, False, True) == rp.ACT_MARK_SWAPPED
    assert rp.recovery_action(rp.SWAPPED, True, False, True) == rp.ACT_DONE


def test_multi_family_frozen_set(tmp_path):
    # both _build calls share tmp_path -> the SAME data_root + journal file
    fp1, journal, data_root, _ = _build(tmp_path, family="market/daily")
    fp2, _, data_root2, _ = _build(tmp_path, family="fundamentals/income")
    assert data_root == data_root2
    final = rp.PromotionCoordinator("run1", data_root, journal, [fp1, fp2]).promote_all()
    assert final["market/daily"] == rp.SWAPPED and final["fundamentals/income"] == rp.SWAPPED
    assert _live_matches_staging(fp1) and _live_matches_staging(fp2)
