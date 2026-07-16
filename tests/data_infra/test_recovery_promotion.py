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


# ── GPT re-review #7 B3: PRE-EXISTING junction — the incident's own mechanism, explicitly IN scope ──
def test_preexisting_parent_junction_refused(tmp_path):
    """GPT re-review #7 B3 (reproduced): `data\\market` was made a junction BEFORE promotion. The old
    fact reads (`exists()/is_dir()`) FOLLOWED it, so it looked like an ordinary directory, the
    path-based rename resolved through it, and promotion installed the recovered tree OUTSIDE
    data_root while reporting SWAPPED. This is not the excluded mid-operation race — the junction was
    already there, exactly as on 2026-07-13."""
    import _winapi
    fp, journal, data_root, manifest = _build(tmp_path, family="market/daily", make_live=False)
    outside = tmp_path / "outside_target"
    outside.mkdir()
    junc = data_root / "market"           # the PARENT of live_dir
    assert not junc.exists()
    _winapi.CreateJunction(str(outside), str(junc))
    with pytest.raises(rp.PromotionError, match="reparse point|pre-existing junction"):
        rp.PromotionCoordinator("run1", data_root, journal, [fp]).promote_all(unattended=True)
    assert not (outside / "daily").exists(), \
        "promotion installed OUTSIDE data_root through a PRE-EXISTING junction"


def test_dir_present_refuses_a_reparse_point(tmp_path):
    """_dir_present used to be exists()/is_dir(), which follows. It must refuse, not traverse."""
    import _winapi
    real = tmp_path / "real"; real.mkdir()
    junc = tmp_path / "junc"
    _winapi.CreateJunction(str(real), str(junc))
    assert rp._dir_present(real) is True
    assert rp._dir_present(tmp_path / "nope") is False
    with pytest.raises(rp.PromotionError, match="reparse point"):
        rp._dir_present(junc)


def test_broken_junction_in_ancestry_refused(tmp_path):
    """A BROKEN junction reports exists()==False and would be SKIPPED by a following check."""
    import _winapi
    fp, journal, data_root, manifest = _build(tmp_path, family="market/daily", make_live=False)
    tgt = tmp_path / "gone"; tgt.mkdir()
    junc = data_root / "market"
    _winapi.CreateJunction(str(tgt), str(junc))
    tgt.rmdir()                            # now broken
    assert junc.exists() is False          # exists() lies about a broken junction
    with pytest.raises(rp.PromotionError, match="reparse point|pre-existing junction"):
        rp.PromotionCoordinator("run1", data_root, journal, [fp]).promote_all(unattended=True)


# ── GPT re-review #7 B4/B5: stale certificates + tombstone content ────────────────────────────────
def test_live_verified_is_not_a_stale_certificate(tmp_path):
    """GPT re-review #7 B4 (reproduced): crash after LIVE_VERIFIED, corrupt live, resume -> SWAPPED.
    A verification cannot survive as a trusted fact across a process boundary."""
    fp, journal, data_root, manifest = _build(tmp_path)

    def crash(l):
        if l == "after_live_verified":
            raise rp.InjectedCrash(l)

    with pytest.raises(rp.InjectedCrash):
        rp.PromotionCoordinator("run1", data_root, journal, [fp], crash_hook=crash).promote_all(unattended=True)
    assert journal.last_state("run1", fp.family) == rp.LIVE_VERIFIED
    (fp.live_dir / "2026" / "daily_20260703.parquet").write_bytes(b"CORRUPTED-AFTER-VERIFY")
    with pytest.raises(rp.PromotionError, match="frozen manifest"):
        rp.PromotionCoordinator("run1", data_root, journal, [fp]).promote_all(unattended=True)
    assert journal.last_state("run1", fp.family) != rp.SWAPPED, "stale LIVE_VERIFIED certified a corrupt tree"


def test_emptied_tombstone_directory_refused(tmp_path):
    """GPT re-review #7 B5 (reproduced): deleting every FILE while leaving the tombstone DIRECTORY
    still produced SWAPPED — the check tested existence, not content."""
    fp, journal, data_root, manifest = _build(tmp_path)
    rp.PromotionCoordinator("run1", data_root, journal, [fp]).promote_all(unattended=True)
    (fp.tombstone_dir / "stale.parquet").unlink()      # directory survives, content gone
    assert fp.tombstone_dir.exists()
    with pytest.raises(rp.PromotionError, match="tombstone CONTENT|tombstone"):
        rp.PromotionCoordinator("run1", data_root, journal, [fp]).promote_all(unattended=True)


def test_lost_tombstone_after_rename_before_old_moved_refused(tmp_path):
    """GPT re-review #7 B5 (reproduced): crash after the live->tombstone rename but BEFORE OLD_MOVED,
    delete the tombstone, resume -> SWAPPED. Without old_was_present, live=False+tomb=False reads as
    'there was never anything to move' — indistinguishable from losing the only copy."""
    fp, journal, data_root, manifest = _build(tmp_path)

    def crash(l):
        if l == "after_move_rename":
            raise rp.InjectedCrash(l)

    with pytest.raises(rp.InjectedCrash):
        rp.PromotionCoordinator("run1", data_root, journal, [fp], crash_hook=crash).promote_all(unattended=True)
    assert journal.last_state("run1", fp.family) == rp.MOVE_OLD_INTENT
    import shutil
    shutil.rmtree(fp.tombstone_dir)                    # the moved-aside tree disappears
    with pytest.raises(rp.PromotionError, match="lost|tombstone"):
        rp.PromotionCoordinator("run1", data_root, journal, [fp]).promote_all(unattended=True)


def test_move_old_intent_records_what_it_moved(tmp_path):
    """The intent must carry old_was_present + the frozen old manifest — the only record of what the
    live tree held before we moved it."""
    fp, journal, data_root, manifest = _build(tmp_path)
    rp.PromotionCoordinator("run1", data_root, journal, [fp]).promote_all(unattended=True)
    intent = [r for r in journal._rows()
              if r.get("state") == rp.MOVE_OLD_INTENT and r.get("run_id") == "run1"][0]["expected"]
    assert intent["old_was_present"] is True
    assert "stale.parquet" in intent["old_manifest"]


def test_lost_family_records_old_absent_and_owes_no_tombstone(tmp_path):
    fp, journal, data_root, manifest = _build(tmp_path, make_live=False)
    rp.PromotionCoordinator("run1", data_root, journal, [fp]).promote_all(unattended=True)
    intent = [r for r in journal._rows()
              if r.get("state") == rp.MOVE_OLD_INTENT and r.get("run_id") == "run1"][0]["expected"]
    assert intent["old_was_present"] is False and intent["old_manifest"] == {}
    # a resume must not demand a tombstone that was never owed
    assert rp.PromotionCoordinator("run1", data_root, journal, [fp]).promote_all(
        unattended=True)[fp.family] == rp.SWAPPED


def test_two_live_processes_same_run_id_refused(tmp_path):
    """GPT re-review #7 B6 (reproduced): the O_EXCL sentinel treats a matching run_id as a resume, so
    two coordinators alive concurrently under `run1` BOTH acquired the claim. Only a process-lifetime
    OS lock can distinguish 'the previous process crashed' from 'a sibling is running right now'."""
    fp, journal, data_root, manifest = _build(tmp_path)
    first = rp.PromotionCoordinator("run1", data_root, journal, [fp])
    first._acquire_process_lock()
    sibling = rp.PromotionCoordinator("run1", data_root, journal, [fp])   # SAME run_id, still alive
    try:
        with pytest.raises(rp.PromotionError, match="another LIVE process"):
            sibling._acquire_process_lock()
        # once the holder releases (process exit/crash does this for us), a genuine resume acquires it
        first.release_process_lock()
        sibling._acquire_process_lock()
    finally:
        sibling.release_process_lock()
        first.release_process_lock()
