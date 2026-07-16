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
        incoming_dir=data_root / rp.INCOMING_AREA / "run1" / family,
        tombstone_dir=data_root / rp.TOMBSTONE_AREA / "run1" / family,
        manifest=manifest)
    journal = rp.PromotionJournal(data_root / ".recovery_journal.jsonl")
    return fp, journal, data_root, manifest


def _live_matches_staging(fp) -> bool:
    return rp._manifest_from_dir(fp.live_dir) == fp.manifest


def test_happy_path_promotes_and_tombstones(tmp_path):
    fp, journal, data_root, manifest = _build(tmp_path)
    coord = rp.PromotionCoordinator("run1", data_root, journal, [fp])
    final = coord.promote_all(unattended=True)
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
        crashed.promote_all(unattended=True)
    # a FRESH coordinator (no crash hook) resumes from the durable journal + facts
    resumed = rp.PromotionCoordinator("run1", data_root, journal, [fp])
    final = resumed.promote_all(unattended=True)
    assert final[fp.family] == rp.SWAPPED, f"did not converge after crash@{label}"
    assert _live_matches_staging(fp), f"live content wrong after crash@{label}"
    assert not fp.incoming_dir.exists()


def test_lost_family_no_live_dir_still_installs(tmp_path):
    # the incident DELETED the family — live_dir never existed. Promotion must still install incoming.
    fp, journal, data_root, manifest = _build(tmp_path, make_live=False)
    assert not fp.live_dir.exists()
    final = rp.PromotionCoordinator("run1", data_root, journal, [fp]).promote_all(unattended=True)
    assert final[fp.family] == rp.SWAPPED
    assert _live_matches_staging(fp)
    assert not fp.tombstone_dir.exists()  # nothing to tombstone (OLD_ABSENT)


def test_foreign_incoming_refused(tmp_path):
    # a pre-existing incoming with NO owning journal intent = foreign collision -> refuse
    fp, journal, data_root, manifest = _build(tmp_path)
    fp.incoming_dir.mkdir(parents=True)
    (fp.incoming_dir / "foreign.parquet").write_bytes(b"NOT OURS")
    with pytest.raises(rp.PromotionError, match="foreign collision"):
        rp.PromotionCoordinator("run1", data_root, journal, [fp]).promote_all(unattended=True)


def test_corrupt_incoming_fails_verification(tmp_path):
    # a copy whose bytes don't match the frozen manifest must fail COPY_VERIFIED (no move happens)
    fp, journal, data_root, manifest = _build(tmp_path)
    # corrupt the staging source AFTER freezing the manifest -> the copied incoming won't match
    (fp.staging_dir / "2026" / "daily_20260703.parquet").write_bytes(b"CORRUPT")
    with pytest.raises(rp.PromotionError, match="incoming != frozen manifest"):
        rp.PromotionCoordinator("run1", data_root, journal, [fp]).promote_all(unattended=True)
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
    final = rp.PromotionCoordinator("run1", data_root, journal, [fp1, fp2]).promote_all(unattended=True)
    assert final["market/daily"] == rp.SWAPPED and final["fundamentals/income"] == rp.SWAPPED
    assert _live_matches_staging(fp1) and _live_matches_staging(fp2)


# -- GPT re-review #5 F5 BLOCKERs: the exact reproductions -----------------------------------------
def test_foreign_run_swapped_row_is_not_adopted(tmp_path):
    """GPT reproduced: a foreign-run SWAPPED journal entry was adopted by a new run, which reported
    success while the live tree stayed OLD. replay() is now run_id-scoped, so the foreign row is
    invisible and this run must actually do the work."""
    fp, journal, data_root, manifest = _build(tmp_path)
    # a DIFFERENT run claims this family already completed
    journal.append("someone_elses_run", fp.family, rp.SWAPPED, {"live_dir": str(fp.live_dir)})
    final = rp.PromotionCoordinator("run1", data_root, journal, [fp]).promote_all(unattended=True)
    assert final[fp.family] == rp.SWAPPED
    assert _live_matches_staging(fp), "adopted a foreign SWAPPED row and skipped the real work"
    assert (fp.tombstone_dir / "stale.parquet").exists()  # the old tree really was moved aside


def test_swapped_journal_with_missing_live_refuses(tmp_path):
    """A SWAPPED row must never be believed on its own: if the live tree vanished after journalling,
    resume must REFUSE rather than report a completed promotion."""
    fp, journal, data_root, manifest = _build(tmp_path)
    rp.PromotionCoordinator("run1", data_root, journal, [fp]).promote_all(unattended=True)
    import shutil
    shutil.rmtree(fp.live_dir)  # corruption/rollback AFTER the SWAPPED row
    with pytest.raises(rp.PromotionError, match="facts disagree"):
        rp.PromotionCoordinator("run1", data_root, journal, [fp]).promote_all(unattended=True)


def test_swapped_resume_rehashes_live_and_catches_corruption(tmp_path):
    """Resume of a SWAPPED family re-hashes the live tree vs the frozen manifest — bit-rot or a
    substituted file is caught instead of being reported as done."""
    fp, journal, data_root, manifest = _build(tmp_path)
    rp.PromotionCoordinator("run1", data_root, journal, [fp]).promote_all(unattended=True)
    (fp.live_dir / "2026" / "daily_20260703.parquet").write_bytes(b"TAMPERED")
    with pytest.raises(rp.PromotionError, match="frozen manifest"):
        rp.PromotionCoordinator("run1", data_root, journal, [fp]).promote_all(unattended=True)


def test_promote_all_arms_the_sentinel(tmp_path):
    """GPT: the sentinel existed but promote_all never wrote it -> no barrier existed. It must be
    armed, and consumers stay fail-closed after completion (cleared only by an explicit human step)."""
    fp, journal, data_root, manifest = _build(tmp_path)
    coord = rp.PromotionCoordinator("run1", data_root, journal, [fp])
    rp.assert_no_active_recovery(data_root)  # not armed yet
    coord.promote_all(unattended=True)
    assert coord.sentinel_path.exists(), "promote_all did not arm the quiescence sentinel"
    with pytest.raises(rp.PromotionError, match="RECOVERY_IN_PROGRESS"):
        rp.assert_no_active_recovery(data_root)


def test_paths_outside_data_root_refused(tmp_path):
    fp, journal, data_root, manifest = _build(tmp_path)
    escaped = rp.FamilyPlan(family="evil", staging_dir=fp.staging_dir,
                            live_dir=tmp_path / "elsewhere" / "evil",
                            incoming_dir=data_root / rp.INCOMING_AREA / "run1" / "evil",
                            tombstone_dir=data_root / rp.TOMBSTONE_AREA / "run1" / "evil",
                            manifest=fp.manifest)
    with pytest.raises(rp.PromotionError, match="escapes data_root"):
        rp.PromotionCoordinator("run1", data_root, journal, [escaped])


def test_plan_hash_binds_the_run(tmp_path):
    """A resume whose frozen plan changed (different expected content) is refused, not re-planned."""
    fp, journal, data_root, manifest = _build(tmp_path)
    rp.PromotionCoordinator("run1", data_root, journal, [fp]).freeze_or_verify_plan()
    mutated = rp.FamilyPlan(family=fp.family, staging_dir=fp.staging_dir, live_dir=fp.live_dir,
                            incoming_dir=fp.incoming_dir, tombstone_dir=fp.tombstone_dir,
                            manifest={"different.parquet": {"sha256": "0" * 64, "size": 1}})
    with pytest.raises(rp.PromotionError, match="plan hash mismatch"):
        rp.PromotionCoordinator("run1", data_root, journal, [mutated]).promote_all(unattended=True)


# ── GPT re-review #6 F5: crash/correctness (threat model scoped to accidents+crashes, not attackers) ─
def test_corrupted_incoming_after_copy_verified_never_touches_live(tmp_path):
    """GPT re-review #6 F5 (reproduced): COPY_VERIFIED was journalled before the crash, so resume
    trusted it, moved the OLD tree to tombstone, installed CORRUPTED incoming bytes, and only then
    failed the live check — after the damage. Incoming must be re-proven BEFORE the live tree moves."""
    fp, journal, data_root, manifest = _build(tmp_path)

    def crash(l):
        if l == "after_copy_verified":
            raise rp.InjectedCrash(l)

    with pytest.raises(rp.InjectedCrash):
        rp.PromotionCoordinator("run1", data_root, journal, [fp], crash_hook=crash).promote_all(unattended=True)
    assert journal.last_state("run1", fp.family) == rp.COPY_VERIFIED
    # corrupt the staged incoming AFTER it was certified
    (fp.incoming_dir / "2026" / "daily_20260703.parquet").write_bytes(b"CORRUPTED-IN-FLIGHT")
    with pytest.raises(rp.PromotionError, match=r"incoming\(pre-move\) != frozen manifest"):
        rp.PromotionCoordinator("run1", data_root, journal, [fp]).promote_all(unattended=True)
    # the LIVE tree must be completely untouched: still the old content, nothing tombstoned
    assert (fp.live_dir / "stale.parquet").read_bytes() == b"STALE"
    assert not fp.tombstone_dir.exists(), "old tree was moved aside before incoming was re-proven"


def test_deleted_tombstone_on_resume_refuses(tmp_path):
    """GPT re-review #6 F5: a SWAPPED family whose tombstone vanished was reported as clean success —
    but that tombstone held the only copy of the tree we replaced."""
    fp, journal, data_root, manifest = _build(tmp_path)
    rp.PromotionCoordinator("run1", data_root, journal, [fp]).promote_all(unattended=True)
    assert fp.tombstone_dir.exists()
    import shutil
    shutil.rmtree(fp.tombstone_dir)          # the replaced tree's only copy disappears
    with pytest.raises(rp.PromotionError, match="tombstone .* is GONE|tombstone"):
        rp.PromotionCoordinator("run1", data_root, journal, [fp]).promote_all(unattended=True)


def test_second_concurrent_run_refused(tmp_path):
    """GPT re-review #6 F5 (reproduced): the sentinel was a plain truncating write, so a SECOND run
    overwrote the first run's claim and replaced its live generation. The claim is O_EXCL now."""
    fp, journal, data_root, manifest = _build(tmp_path)
    first = rp.PromotionCoordinator("run1", data_root, journal, [fp])
    first.acquire_exclusive()
    other = rp.PromotionCoordinator("run2", data_root, journal, [fp])
    with pytest.raises(rp.PromotionError, match="already claimed by run"):
        other.acquire_exclusive()
    first.acquire_exclusive()   # our OWN claim is a legitimate resume, not a conflict


def test_promotion_is_human_driven_by_default(tmp_path):
    """Promotion is attended: one family at a time, machine verifies + refuses, operator proceeds.
    An unattended sweep over the whole store must be an explicit choice."""
    fp, journal, data_root, manifest = _build(tmp_path)
    coord = rp.PromotionCoordinator("run1", data_root, journal, [fp])
    with pytest.raises(rp.PromotionError, match="UNATTENDED sweep"):
        coord.promote_all()
    with pytest.raises(rp.PromotionError, match="not in this run's frozen plan"):
        coord.promote_family("market/nonexistent")
    assert coord.promote_family(fp.family) == {fp.family: rp.SWAPPED}
    assert _live_matches_staging(fp)
