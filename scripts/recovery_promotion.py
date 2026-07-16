# -*- coding: utf-8 -*-
"""Recovery FOUNDATION 5/5 — the crash-resumable promotion state machine (GPT recovery re-review #4 M3).

Promotion is the ONE authorized E: mutation: it installs the C:-staged, fully-verified recovered raw
families into the live `data\\` store. Cross-volume copies are NEVER atomic (GPT B6), so promotion is a
per-family WRITE-AHEAD state machine whose journal is fsync'd to the E: volume BEFORE each mutation, and
whose resume consults a deterministic STATE x PATH recovery table — it never guesses.

Per-family lifecycle (each transition names the exact expected on-disk state):

    COPYING -> COPY_VERIFIED -> MOVE_OLD_INTENT -> OLD_MOVED|OLD_ABSENT
            -> INSTALL_NEW_INTENT -> NEW_INSTALLED -> LIVE_VERIFIED -> SWAPPED

- Only same-volume renames are atomic: live->tombstone (MOVE_OLD) and incoming->live (INSTALL_NEW) are
  both intra-E:. The cross-volume C:->incoming COPY is re-runnable and proven by the frozen manifest.
- Write-ahead MOVE_OLD_INTENT / INSTALL_NEW_INTENT are journaled BEFORE their renames, so a crash mid-
  rename is recovered from the intent + observed path/hash state, not from a post-hoc marker a crash
  could precede.
- `.recovery_incoming\\` and `.recovery_tombstone\\` live at the `data\\` TOP LEVEL — outside every
  dataset glob (`market/**` cannot match them).
- Owned resume: a pre-existing incoming/tombstone is refused as a foreign collision UNLESS this run's
  own journal intent owns it.
- Quiescence: a durable E:-side RECOVERY_IN_PROGRESS sentinel is written before the first swap; every raw
  consumer fails closed while it exists (`assert_no_active_recovery`). Promotion additionally takes the
  generation barrier EXCLUSIVE so no shared consumer is mid-operation.

THREAT MODEL — EXPLICITLY SCOPED (user decision, 2026-07-16; GPT re-review #6):
IN scope, and defended:
  * PRE-EXISTING reparse points / junctions anywhere in a path we walk or write (this is what actually
    happened on 2026-07-13: `git worktree remove --force` followed junctions that were already there
    and deleted the live store). Refused via the no-follow broker + handle-relative writes.
  * CRASHES at any point (power loss, kill) — the write-ahead journal + the total recovery_action table
    + re-verification before every destructive step.
  * CORRUPTION of staged bytes between steps — incoming is re-proven against the frozen manifest
    immediately before the old tree is touched, and live is re-hashed on resume.
  * CONCURRENT RUNS — an O_EXCL sentinel claim (a different run_id refuses).
NOT YET TRUE, do not claim otherwise (GPT re-review #7 M2):
  * CONCURRENT CONSUMERS are NOT defended today. `assert_no_active_recovery` exists but has NO
    production caller — no raw reader / daily job / monthly bump / builder calls it, and there is no
    shared/exclusive generation barrier, so a consumer that started BEFORE the sentinel keeps running.
    This is a HARD PRE-PROMOTION INTEGRATION GATE (wire the hook into every consumer entry point, and
    the barrier, before any promotion is authorized) — not a property the code currently has.
  * Two live processes sharing ONE run_id both pass the sentinel claim (it treats a matching run_id as
    a resume). Needs a process-lifetime OS lock in addition to the durable sentinel.
OUT of scope, deliberately NOT defended:
  * An ACTIVE ADVERSARY racing us mid-operation on this machine (swapping a component between two links
    of a handle chain, ADS/8.3-alias tricks, replacing a parent between validation and rename). This is
    a single-user workstation; an attacker with local write access to `E:\\量化系统\\data` can destroy the
    store directly and needs no race. Hardening against it was adding NT-API complexity that itself
    became the source of new defects across three review rounds, for no reduction in real risk.
The consequence: promotion is HUMAN-DRIVEN and attended (`promote_family` one family at a time; the
machine verifies and refuses, the operator decides), not an unattended automated sweep.

Nothing here runs automatically. The live Qlib provider is untouched throughout. NO Tushare involvement.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from recovery_write_broker import (NoFollowWriteBroker, assert_no_reparse_source,  # noqa: E402
                                   walk_no_follow)

# Staging areas live at the `data\` TOP LEVEL — outside every dataset glob (`market/**` cannot match).
INCOMING_AREA = ".recovery_incoming"
TOMBSTONE_AREA = ".recovery_tombstone"
SENTINEL_NAME = ".recovery_in_progress"


class PromotionError(RuntimeError):
    """A promotion refused/aborted for a state the recovery table maps to no safe action."""


class InjectedCrash(RuntimeError):
    """Test-only: a simulated power loss at a labelled checkpoint (crash-injection harness)."""


# ── states ───────────────────────────────────────────────────────────────────────────────────────
COPYING = "COPYING"
COPY_VERIFIED = "COPY_VERIFIED"
MOVE_OLD_INTENT = "MOVE_OLD_INTENT"
OLD_MOVED = "OLD_MOVED"
OLD_ABSENT = "OLD_ABSENT"
INSTALL_NEW_INTENT = "INSTALL_NEW_INTENT"
NEW_INSTALLED = "NEW_INSTALLED"
LIVE_VERIFIED = "LIVE_VERIFIED"
SWAPPED = "SWAPPED"
_ORDER = (COPYING, COPY_VERIFIED, MOVE_OLD_INTENT, OLD_MOVED, OLD_ABSENT, INSTALL_NEW_INTENT,
          NEW_INSTALLED, LIVE_VERIFIED, SWAPPED)

# ── actions the recovery table can prescribe ─────────────────────────────────────────────────────
ACT_COPY = "DO_COPY"            # (re)copy C:->incoming then verify
ACT_VERIFY_COPY = "VERIFY_COPY"  # incoming exists; verify vs manifest
ACT_MOVE_OLD = "MOVE_OLD"        # rename live->tombstone
ACT_INSTALL_NEW = "INSTALL_NEW"  # rename incoming->live
ACT_VERIFY_LIVE = "VERIFY_LIVE"  # re-hash live vs manifest
ACT_MARK_SWAPPED = "MARK_SWAPPED"
ACT_DONE = "DONE"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class FamilyPlan:
    """One recovered family to swap in. `manifest` = {posix_rel_path: {'sha256':..., 'size':int}} frozen
    from the strictly-verified C: build (§4/§5); its ordering/content is fixed before the first move."""
    family: str          # e.g. "market/daily"
    staging_dir: Path    # C:\...\staging_data\market\daily (the verified source)
    live_dir: Path       # E:\量化系统\data\market\daily
    incoming_dir: Path   # E:\...\data\.recovery_incoming\<run>\market\daily
    tombstone_dir: Path  # E:\...\data\.recovery_tombstone\<run>\market\daily
    manifest: dict = field(default_factory=dict)


# ── STATE x PATH recovery table ──────────────────────────────────────────────────────────────────
def recovery_action(state: str | None, live: bool, incoming: bool, tomb: bool) -> str:
    """Map (last journalled state, live present?, incoming present?, tombstone present?) to ONE
    deterministic action. A write-ahead *_INTENT is resolved by FACTS: the rename may have completed
    before the crash (post-rename facts) or not (pre-rename facts). Unmapped tuples raise — never guess.
    Hash checks are applied by the caller when the action is a VERIFY_*.

    NOTE: live-ABSENT is a NORMAL start here — the incident deleted most families, so a `live_dir` that
    does not exist is the common (OLD_ABSENT-from-the-start) case, never an error."""
    if state is None:
        if not incoming and not tomb:
            return ACT_COPY                    # live present OR already-deleted — copy staging in either way
        raise PromotionError(f"fresh family but pre-existing incoming/tombstone "
                             f"(incoming={incoming} tomb={tomb}) — foreign collision")
    if state == SWAPPED:
        # GPT re-review #5 F5: NEVER trust the journal alone — a crash/corruption/rollback AFTER the
        # SWAPPED row would otherwise be reported as a completed promotion. Facts must agree, and the
        # caller re-hashes the live tree against the frozen manifest before accepting DONE.
        if live and not incoming:
            return ACT_DONE
        raise PromotionError(f"SWAPPED journalled but facts disagree (live={live} incoming={incoming}) "
                             f"— promotion did NOT complete; refusing to report success")
    if state == COPYING:
        if not tomb:                           # copy may be partial -> re-copy+verify; nothing moved yet
            return ACT_COPY
        raise PromotionError(f"COPYING but a tombstone exists (live={live} incoming={incoming})")
    if state == COPY_VERIFIED:
        if incoming and not tomb:
            return ACT_MOVE_OLD
        raise PromotionError(f"COPY_VERIFIED unexpected (live={live} incoming={incoming} tomb={tomb})")
    if state == MOVE_OLD_INTENT:
        # rename live->tombstone may or may not have happened; disambiguate by live/tomb facts
        if live and not tomb:
            return ACT_MOVE_OLD                # pre-rename: live still there -> move it
        if incoming and not live:
            return ACT_INSTALL_NEW             # post-rename (tomb set) OR live was already empty (OLD_ABSENT)
        raise PromotionError(f"MOVE_OLD_INTENT unresolved (live={live} incoming={incoming} tomb={tomb})")
    if state in (OLD_MOVED, OLD_ABSENT):
        if incoming and not live:
            return ACT_INSTALL_NEW
        if live and not incoming:
            return ACT_VERIFY_LIVE             # install already happened, unjournalled
        raise PromotionError(f"{state} unresolved (live={live} incoming={incoming})")
    if state == INSTALL_NEW_INTENT:
        # rename incoming->live may or may not have happened
        if incoming and not live:
            return ACT_INSTALL_NEW             # pre-rename: do it
        if live and not incoming:
            return ACT_VERIFY_LIVE             # post-rename: installed, verify
        raise PromotionError(f"INSTALL_NEW_INTENT unresolved (live={live} incoming={incoming})")
    if state == NEW_INSTALLED:
        if live and not incoming:
            return ACT_VERIFY_LIVE
        raise PromotionError(f"NEW_INSTALLED unresolved (live={live} incoming={incoming})")
    if state == LIVE_VERIFIED:
        if live:
            return ACT_MARK_SWAPPED
        raise PromotionError("LIVE_VERIFIED but live path absent")
    raise PromotionError(f"unknown state {state!r}")


class PromotionJournal:
    """Append-only, fsync'd write-ahead journal on the E: volume (co-located with the data it mutates,
    so a crash leaves the journal next to the half-done state). One JSONL row per transition."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _write(self, row: dict) -> None:
        line = json.dumps(row, ensure_ascii=False, sort_keys=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()
            os.fsync(fh.fileno())  # write-ahead: durable BEFORE the caller performs the mutation

    def append_plan(self, run_id: str, plan_hash: str, families: list) -> None:
        self._write({"kind": "plan", "run_id": run_id, "plan_hash": plan_hash, "families": families})

    def plan_row(self, run_id: str):
        for row in self._rows():
            if row.get("kind") == "plan" and row.get("run_id") == run_id:
                return row
        return None

    def append(self, run_id: str, family: str, state: str, expected: dict) -> None:
        if state not in _ORDER:
            raise PromotionError(f"illegal journal state {state!r}")
        self._write({"kind": "state", "run_id": run_id, "family": family, "state": state,
                     "expected": expected})

    def _rows(self):
        if not self.path.exists():
            return []
        out = []
        for ln in self.path.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if ln:
                out.append(json.loads(ln))
        return out

    def replay(self, run_id: str) -> dict:
        """Return {family: last_row} for THIS run only. GPT re-review #5 F5: replay used to key on
        family alone, so a FOREIGN run's `SWAPPED` row was adopted as our own and reported success while
        the live tree stayed old. run_id is now a hard filter — another run's rows are never our state."""
        if not run_id:
            raise PromotionError("replay requires a run_id (run-scoped by construction)")
        last: dict = {}
        for row in self._rows():
            if row.get("kind") != "state" or row.get("run_id") != run_id:
                continue
            last[row["family"]] = row
        return last

    def last_row(self, run_id: str, family: str):
        return self.replay(run_id).get(family)

    def last_state(self, run_id: str, family: str):
        row = self.last_row(run_id, family)
        return row["state"] if row else None


def _dir_present(p: Path) -> bool:
    """Is there a REAL directory at p? GPT re-review #7 B3 (reproduced): this used to be
    `p.exists() and p.is_dir()`, which FOLLOWS a reparse point — so a PRE-EXISTING junction at
    `data\\market` looked like an ordinary directory, every subsequent path resolved through it, and
    promotion installed the recovered tree OUTSIDE data_root while reporting SWAPPED.

    A pre-existing junction is the INCIDENT'S OWN MECHANISM and is explicitly IN scope. os.lstat never
    follows; a reparse point is refused, never silently traversed."""
    try:
        st = os.lstat(p)
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise PromotionError(f"cannot lstat {p}: {exc}")
    if (getattr(st, "st_file_attributes", 0) & 0x400) or stat.S_ISLNK(st.st_mode):
        raise PromotionError(f"REFUSED: {p} is a reparse point (pre-existing junction) — the 2026-07-13 "
                             f"incident's exact mechanism; refusing to traverse it")
    return stat.S_ISDIR(st.st_mode)


def _assert_no_reparse_ancestry(p: Path, label: str) -> None:
    """Refuse a reparse point at ANY component of p (incl. a broken one, which `exists()` reports as
    absent). Re-checked before every fact read and every rename — cheap, and the only thing standing
    between a stray junction and another 2026-07-13."""
    try:
        assert_no_reparse_source(p)
    except Exception as exc:  # WriteBrokerError
        raise PromotionError(f"{label}: {exc}")


def _manifest_from_dir(root: Path) -> dict:
    """Build {posix_rel: {sha256,size}} by walking `root` NO-FOLLOW (a reparse point in the tree
    refuses) — used to freeze the C: staging source and to re-verify an installed live tree.
    GPT re-review #7 B3: validates its OWN root ancestry rather than trusting the caller."""
    _assert_no_reparse_ancestry(Path(os.path.normpath(str(root))), f"manifest root {root}")
    out = {}
    for f in sorted(walk_no_follow(root)):
        rel = f.relative_to(root).as_posix()
        out[rel] = {"sha256": sha256_file(f), "size": f.stat().st_size}
    return out


class PromotionCoordinator:
    """Runs the per-family state machine over a FROZEN disjoint family list. `crash_hook(label)` is the
    test seam: the crash-injection harness raises InjectedCrash at a labelled checkpoint, then a fresh
    coordinator `.resume()`s from the durable journal + on-disk facts."""

    def __init__(self, run_id: str, data_root: Path, journal: PromotionJournal, families: list,
                 *, crash_hook=None):
        if not run_id:
            raise PromotionError("run_id required")
        self.run_id = run_id
        self.data_root = Path(os.path.normpath(str(data_root)))
        self.journal = journal
        # frozen disjoint list fixed before the first move (GPT re-review #3 M3)
        seen = set()
        for fp in families:
            if fp.family in seen:
                raise PromotionError(f"duplicate family in promotion set: {fp.family}")
            seen.add(fp.family)
            self._assert_contained(fp)
        self.families = list(families)
        self._broker = None
        self._crash = crash_hook or (lambda _label: None)

    def _assert_contained(self, fp: "FamilyPlan") -> None:
        """GPT re-review #5 F5: FamilyPlan established no containment — every mutated path must sit
        under data_root, and incoming/tombstone must live in their top-level staging areas (outside
        every dataset glob) so `market/**` can never match them.

        GPT re-review #7 B3: lexical containment ALONE is not containment — a pre-existing junction at
        an intermediate component satisfies `relative_to()` while resolving elsewhere. Every path's
        ancestry is now also proven reparse-free, no-follow."""
        for label, p in (("data_root", self.data_root), ("live_dir", fp.live_dir),
                         ("incoming_dir", fp.incoming_dir), ("tombstone_dir", fp.tombstone_dir),
                         ("journal", self.journal.path), ("sentinel", self.sentinel_path)):
            _assert_no_reparse_ancestry(Path(os.path.normpath(str(p))), f"{fp.family}: {label}")
        for label, p in (("live_dir", fp.live_dir), ("incoming_dir", fp.incoming_dir),
                         ("tombstone_dir", fp.tombstone_dir)):
            q = Path(os.path.normpath(str(p)))
            try:
                q.relative_to(self.data_root)
            except ValueError:
                raise PromotionError(f"{fp.family}: {label} {q} escapes data_root {self.data_root}")
        for label, p, area in (("incoming_dir", fp.incoming_dir, INCOMING_AREA),
                               ("tombstone_dir", fp.tombstone_dir, TOMBSTONE_AREA)):
            q = Path(os.path.normpath(str(p)))
            try:
                q.relative_to(self.data_root / area)
            except ValueError:
                raise PromotionError(f"{fp.family}: {label} {q} must live under {self.data_root / area}")

    def _plan_hash(self) -> str:
        payload = [{"family": fp.family, "live_dir": str(fp.live_dir), "incoming_dir": str(fp.incoming_dir),
                    "tombstone_dir": str(fp.tombstone_dir),
                    "manifest_hash": hashlib.sha256(
                        json.dumps(fp.manifest, sort_keys=True).encode("utf-8")).hexdigest()}
                   for fp in sorted(self.families, key=lambda f: f.family)]
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    def freeze_or_verify_plan(self) -> str:
        """Bind this run to an IMMUTABLE plan (paths + manifest hashes). A resume whose plan differs —
        different families, paths, or expected content — is REFUSED rather than silently re-planned."""
        ph = self._plan_hash()
        existing = self.journal.plan_row(self.run_id)
        if existing is None:
            self.journal.append_plan(self.run_id, ph, [fp.family for fp in self.families])
        elif existing.get("plan_hash") != ph:
            raise PromotionError(f"plan hash mismatch for run {self.run_id}: journal has "
                                 f"{existing.get('plan_hash')!r}, this plan is {ph!r} — the frozen "
                                 f"promotion plan changed; refusing resume")
        return ph

    # sentinel / quiescence ------------------------------------------------------------------------
    @property
    def sentinel_path(self) -> Path:
        return self.data_root / SENTINEL_NAME

    def _move_old_intent(self, fp: "FamilyPlan") -> dict:
        """The MOVE_OLD_INTENT row this run journalled for the family (its old_was_present +
        old_manifest are the ONLY record of what the live tree held before we moved it)."""
        for r in reversed(self.journal._rows()):
            if (r.get("kind") == "state" and r.get("run_id") == self.run_id
                    and r.get("family") == fp.family and r.get("state") == MOVE_OLD_INTENT):
                return r.get("expected") or {}
        return {}

    def _assert_tombstone_intact(self, fp: "FamilyPlan") -> None:
        """GPT re-review #7 B5: the tombstone check tested DIRECTORY EXISTENCE only, so deleting every
        file inside it still reported SWAPPED. If this run moved a real tree aside, that tombstone is
        the ONLY copy of what we replaced — prove it by CONTENT against the frozen old manifest."""
        intent = self._move_old_intent(fp)
        if not intent.get("old_was_present"):
            return  # nothing was ever moved aside (OLD_ABSENT) — no tombstone is owed
        if not _dir_present(fp.tombstone_dir):
            raise PromotionError(f"{fp.family}: the old tree was moved to {fp.tombstone_dir} but the "
                                 f"tombstone is GONE — it held the only copy of what we replaced")
        got = _manifest_from_dir(fp.tombstone_dir)
        want = intent.get("old_manifest") or {}
        if got != want:
            missing = sorted(set(want) - set(got))[:3]
            raise PromotionError(f"{fp.family}: tombstone CONTENT does not match what was moved aside "
                                 f"(missing={missing}, {len(got)} of {len(want)} files) — the only copy "
                                 f"of the replaced tree is damaged")

    def _journalled_old_moved(self, fp: "FamilyPlan") -> bool:
        """Did THIS run ever journal OLD_MOVED for this family (i.e. is a tombstone owed)?"""
        return any(r.get("kind") == "state" and r.get("run_id") == self.run_id
                   and r.get("family") == fp.family and r.get("state") == OLD_MOVED
                   for r in self.journal._rows())

    def acquire_exclusive(self) -> None:
        """Durable, EXCLUSIVE promotion claim (GPT re-review #6 F5: the sentinel was written with a
        plain truncating open, so a SECOND run simply overwrote the first run's claim and both mutated
        the live tree — one replaced the other's generation). Created O_EXCL: whoever wins owns the
        promotion; a different run_id finding it REFUSES; our own run_id is a legitimate resume."""
        self.sentinel_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"run_id": self.run_id, "families": [f.family for f in self.families]})
        try:
            fd = os.open(str(self.sentinel_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                held = json.loads(self.sentinel_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                raise PromotionError(f"promotion sentinel {self.sentinel_path} exists but is unreadable "
                                     f"— refusing (resolve by hand)")
            if held.get("run_id") != self.run_id:
                raise PromotionError(f"promotion already claimed by run {held.get('run_id')!r} — a second "
                                     f"concurrent promotion would replace its live generation; REFUSING")
            return  # our own claim: legitimate resume
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())

    def write_sentinel(self) -> None:
        """Back-compat alias for the exclusive claim (never a bare overwrite)."""
        self.acquire_exclusive()

    def clear_sentinel(self) -> None:
        # retained until QA + first verified backup complete; explicit call only
        if self.sentinel_path.exists():
            self.sentinel_path.unlink()

    # per-family engine ----------------------------------------------------------------------------
    def _facts(self, fp: FamilyPlan):
        return _dir_present(fp.live_dir), _dir_present(fp.incoming_dir), _dir_present(fp.tombstone_dir)

    def _assert_owned_or_fresh(self, fp: FamilyPlan, state) -> None:
        """A pre-existing incoming/tombstone with NO journal state for this family is a FOREIGN
        collision -> refuse. With a journal state, this run owns them -> legitimate resume."""
        _, incoming, tomb = self._facts(fp)
        if state is None and (incoming or tomb):
            raise PromotionError(f"{fp.family}: pre-existing incoming/tombstone but no owning journal "
                                 f"intent (foreign collision) — refusing")

    def broker(self) -> NoFollowWriteBroker:
        """GPT re-review #5 F5: promotion DESTINATIONS were raw open()/copy — every incoming write now
        goes through the handle-relative no-follow broker rooted at data_root (Foundation 1)."""
        if self._broker is None:
            self._broker = NoFollowWriteBroker(self.data_root)
        return self._broker

    def _copy_and_verify(self, fp: FamilyPlan) -> None:
        """Cross-volume C:->incoming copy (re-runnable), NO-FOLLOW on BOTH ends, then verify vs the
        frozen manifest. Destination writes go through the broker (handle-relative, reparse/hardlink-
        refusing), so a junction planted under .recovery_incoming cannot redirect a recovered file."""
        assert_no_reparse_source(fp.staging_dir)
        b = self.broker()
        if fp.incoming_dir.exists():
            import shutil
            shutil.rmtree(fp.incoming_dir)  # a partial prior copy: rebuild deterministically
        b.mkdirs(fp.incoming_dir)
        for src in sorted(walk_no_follow(fp.staging_dir)):
            rel = src.relative_to(fp.staging_dir)
            dst = fp.incoming_dir / rel
            assert_no_reparse_source(src)
            b.copy_into(src, dst)
        self._verify_tree(fp, fp.incoming_dir, "incoming")

    def _verify_tree(self, fp: FamilyPlan, root: Path, label: str) -> None:
        got = _manifest_from_dir(root)
        if got != fp.manifest:
            missing = set(fp.manifest) - set(got)
            extra = set(got) - set(fp.manifest)
            bad = [k for k in (set(fp.manifest) & set(got)) if got[k] != fp.manifest[k]]
            raise PromotionError(f"{fp.family}: {label} != frozen manifest "
                                 f"(missing={sorted(missing)[:3]} extra={sorted(extra)[:3]} bad={bad[:3]})")

    def _promote_family(self, fp: FamilyPlan) -> None:
        row = self.journal.last_row(self.run_id, fp.family)  # run-scoped: a foreign run is never our state
        state = row["state"] if row else None
        if row:  # the journalled intent must describe THIS plan's paths, not another shape
            exp = row.get("expected") or {}
            for k, want in (("live_dir", str(fp.live_dir)), ("incoming_dir", str(fp.incoming_dir)),
                            ("tombstone_dir", str(fp.tombstone_dir)), ("to", None), ("from", None)):
                if k in exp and want is not None and exp[k] != want:
                    raise PromotionError(f"{fp.family}: journalled {k}={exp[k]!r} != plan {want!r} — "
                                         f"refusing to resume a differently-shaped promotion")
        if state == SWAPPED:
            # Trust-but-VERIFY a completed family on resume: prove it on FACTS + content hashes.
            live, incoming, tomb = self._facts(fp)
            recovery_action(SWAPPED, live, incoming, tomb)  # raises if the facts disagree
            self._verify_tree(fp, fp.live_dir, "live(resume)")
            # GPT re-review #6 F5: a DELETED tombstone was silently accepted. If this run journalled
            # OLD_MOVED then the pre-incident tree was preserved there and is the ONLY copy of what was
            # replaced — its disappearance is a real loss, not a detail, and must not read as success.
            self._assert_tombstone_intact(fp)   # by CONTENT, not mere existence (B5)
            return
        self._assert_owned_or_fresh(fp, state)
        # drive the machine to SWAPPED; each loop consults the recovery table on CURRENT facts
        while True:
            live, incoming, tomb = self._facts(fp)
            act = recovery_action(state, live, incoming, tomb)
            if act == ACT_DONE:
                return
            if act == ACT_COPY:
                self.journal.append(self.run_id, fp.family, COPYING, {"live_dir": str(fp.live_dir)})
                self._crash("after_copy_intent")
                self._copy_and_verify(fp)
                self._crash("after_copy")
                self.journal.append(self.run_id, fp.family, COPY_VERIFIED, {"incoming_dir": str(fp.incoming_dir)})
                self._crash("after_copy_verified")
                state = COPY_VERIFIED
            elif act == ACT_MOVE_OLD:
                # GPT re-review #6 F5 (reproduced): COPY_VERIFIED was journalled BEFORE the crash, so a
                # resume trusted it and moved the OLD tree aside before ever re-checking incoming — if
                # incoming was corrupted in between, the corrupted bytes were installed, the old tree
                # was already tombstoned, and only the LIVE manifest check failed, after the damage.
                # Re-prove incoming against the frozen manifest BEFORE touching the live tree: nothing
                # is moved until the replacement is known good.
                self._verify_tree(fp, fp.incoming_dir, "incoming(pre-move)")
                had_live = _dir_present(fp.live_dir)
                # B5: the intent must record whether the old tree EXISTED and what it contained.
                # Without old_was_present, a crash after the rename but before OLD_MOVED is
                # indistinguishable from "there was never anything to move" (live=False, tomb=False
                # reads as OLD_ABSENT) — so a DELETED tombstone silently became a clean success.
                old_manifest = _manifest_from_dir(fp.live_dir) if had_live else {}
                self.journal.append(self.run_id, fp.family, MOVE_OLD_INTENT,
                                    {"from": str(fp.live_dir), "to": str(fp.tombstone_dir),
                                     "old_was_present": bool(had_live),
                                     "old_manifest": old_manifest})
                self._crash("after_move_intent")
                if had_live:
                    fp.tombstone_dir.parent.mkdir(parents=True, exist_ok=True)
                    _assert_no_reparse_ancestry(fp.live_dir, f"{fp.family}: live_dir pre-rename")
                    _assert_no_reparse_ancestry(fp.tombstone_dir, f"{fp.family}: tomb pre-rename")
                    os.replace(fp.live_dir, fp.tombstone_dir)  # atomic same-volume
                    self._crash("after_move_rename")
                    self.journal.append(self.run_id, fp.family, OLD_MOVED, {"tombstone_dir": str(fp.tombstone_dir)})
                    state = OLD_MOVED
                else:
                    self.journal.append(self.run_id, fp.family, OLD_ABSENT, {"note": "live already empty"})
                    state = OLD_ABSENT
                self._crash("after_old_moved")
            elif act == ACT_INSTALL_NEW:
                # B5: live=False+tomb=False after MOVE_OLD_INTENT reads as OLD_ABSENT, but if the
                # intent recorded old_was_present the rename DID happen and the tombstone has since
                # been lost — that is data loss, not an absent old tree.
                if state == MOVE_OLD_INTENT and self._move_old_intent(fp).get("old_was_present") \
                        and not _dir_present(fp.tombstone_dir):
                    raise PromotionError(f"{fp.family}: MOVE_OLD_INTENT recorded a REAL old tree, but "
                                         f"neither live nor tombstone exists — the replaced tree was "
                                         f"lost; refusing to install over the gap")
                self.journal.append(self.run_id, fp.family, INSTALL_NEW_INTENT,
                                    {"from": str(fp.incoming_dir), "to": str(fp.live_dir)})
                self._crash("after_install_intent")
                if _dir_present(fp.live_dir):
                    raise PromotionError(f"{fp.family}: live present at INSTALL_NEW (would clobber)")
                fp.live_dir.parent.mkdir(parents=True, exist_ok=True)
                _assert_no_reparse_ancestry(fp.incoming_dir, f"{fp.family}: incoming pre-install")
                _assert_no_reparse_ancestry(fp.live_dir, f"{fp.family}: live_dir pre-install")
                os.replace(fp.incoming_dir, fp.live_dir)  # atomic same-volume
                self._crash("after_install_rename")
                self.journal.append(self.run_id, fp.family, NEW_INSTALLED, {"live_dir": str(fp.live_dir)})
                state = NEW_INSTALLED
                self._crash("after_new_installed")
            elif act == ACT_VERIFY_LIVE:
                self._verify_tree(fp, fp.live_dir, "live")
                self.journal.append(self.run_id, fp.family, LIVE_VERIFIED, {"live_dir": str(fp.live_dir)})
                state = LIVE_VERIFIED
                self._crash("after_live_verified")
            elif act == ACT_MARK_SWAPPED:
                # GPT re-review #7 B4 (reproduced): LIVE_VERIFIED mapped straight to MARK_SWAPPED, so a
                # crash after LIVE_VERIFIED left a STALE CERTIFICATE — resume trusted it and reported
                # SWAPPED over a live tree corrupted in between. A verification cannot survive as a
                # trusted fact across a process boundary: re-hash immediately before appending SWAPPED.
                self._verify_tree(fp, fp.live_dir, "live(pre-swap)")
                self._assert_tombstone_intact(fp)
                self.journal.append(self.run_id, fp.family, SWAPPED, {"live_dir": str(fp.live_dir)})
                state = SWAPPED
                self._crash("after_swapped")
            else:
                raise PromotionError(f"unhandled action {act} for {fp.family}")

    def promote_family(self, family: str) -> dict:
        """THE human-driven door: promote ONE named family, attended, and report its state. The machine
        VERIFIES (manifests, facts, hashes) and refuses; the operator decides to proceed to the next
        family. Resume-safe — re-invoking after a crash rolls this family forward from its durable state.

        The quiescence sentinel is claimed EXCLUSIVELY before the first mutation and deliberately LEFT
        ARMED afterwards: consumers stay fail-closed until QA + the first verified backup, at which point
        `clear_sentinel()` is an explicit human step."""
        match = [fp for fp in self.families if fp.family == family]
        if not match:
            raise PromotionError(f"{family!r} is not in this run's frozen plan "
                                 f"({[f.family for f in self.families]})")
        self.freeze_or_verify_plan()   # bind the run to an immutable plan before any mutation
        self.acquire_exclusive()       # exclusive claim + arm the barrier
        self._promote_family(match[0])
        row = self.journal.last_row(self.run_id, family)
        return {family: row["state"] if row else None}

    def promote_all(self, *, unattended: bool = False) -> dict:
        """Promote EVERY family in the frozen list in one go. Promotion is meant to be human-driven one
        family at a time (`promote_family`) so an operator sees each verification before the next tree is
        touched; an unattended sweep over the whole store must be an explicit, deliberate choice."""
        if not unattended:
            raise PromotionError(
                "promote_all() is an UNATTENDED sweep over every family; promotion is human-driven — "
                "use promote_family(<name>) per family, or pass unattended=True to accept that the "
                "whole store is mutated without a per-family operator check")
        self.freeze_or_verify_plan()
        self.acquire_exclusive()
        for fp in self.families:
            self._promote_family(fp)
        return {f: r["state"] for f, r in self.journal.replay(self.run_id).items()}

    def resume(self, *, unattended: bool = False) -> dict:
        return self.promote_all(unattended=unattended)


def assert_no_active_recovery(data_root: Path) -> None:
    """Consumer-side quiescence hook: every raw reader / daily job / monthly bump / builder calls this
    at entry AND after acquiring its generation barrier, and FAILS CLOSED if a promotion sentinel
    exists. (Wiring into each consumer is the integration phase; this is the shared assertion.)"""
    sentinel = Path(data_root) / SENTINEL_NAME
    if sentinel.exists():
        raise PromotionError(f"RECOVERY_IN_PROGRESS: raw store is mid-promotion ({sentinel}) — refusing "
                             f"to read/write until promotion completes and the sentinel clears")
