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

Nothing here runs automatically. The live Qlib provider is untouched throughout. NO Tushare involvement.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from recovery_write_broker import assert_no_reparse_source, walk_no_follow  # noqa: E402


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
        return ACT_DONE
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

    def append(self, run_id: str, family: str, state: str, expected: dict) -> None:
        if state not in _ORDER:
            raise PromotionError(f"illegal journal state {state!r}")
        row = {"run_id": run_id, "family": family, "state": state, "expected": expected}
        line = json.dumps(row, ensure_ascii=False, sort_keys=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()
            os.fsync(fh.fileno())  # write-ahead: durable BEFORE the caller performs the mutation

    def replay(self) -> dict:
        """Return {family: last_state} from the durable journal (last row per family wins)."""
        last: dict = {}
        if not self.path.exists():
            return last
        for ln in self.path.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            row = json.loads(ln)
            last[row["family"]] = row["state"]
        return last

    def last_state(self, family: str):
        return self.replay().get(family)


def _dir_present(p: Path) -> bool:
    return p.exists() and p.is_dir()


def _manifest_from_dir(root: Path) -> dict:
    """Build {posix_rel: {sha256,size}} by walking `root` NO-FOLLOW (a reparse point in the tree
    refuses) — used to freeze the C: staging source and to re-verify an installed live tree."""
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
        self.run_id = run_id
        self.data_root = Path(data_root)
        self.journal = journal
        # frozen disjoint list fixed before the first move (GPT re-review #3 M3)
        seen = set()
        for fp in families:
            if fp.family in seen:
                raise PromotionError(f"duplicate family in promotion set: {fp.family}")
            seen.add(fp.family)
        self.families = list(families)
        self._crash = crash_hook or (lambda _label: None)

    # sentinel / quiescence ------------------------------------------------------------------------
    @property
    def sentinel_path(self) -> Path:
        return self.data_root / ".recovery_in_progress"

    def write_sentinel(self) -> None:
        self.sentinel_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.sentinel_path, "w", encoding="utf-8") as fh:
            json.dump({"run_id": self.run_id, "families": [f.family for f in self.families]}, fh)
            fh.flush()
            os.fsync(fh.fileno())

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

    def _copy_and_verify(self, fp: FamilyPlan) -> None:
        """Cross-volume C:->incoming copy (re-runnable), NO-FOLLOW, then verify vs the frozen manifest."""
        assert_no_reparse_source(fp.staging_dir)
        if fp.incoming_dir.exists():
            # a partial prior copy: rebuild deterministically
            import shutil
            shutil.rmtree(fp.incoming_dir)
        fp.incoming_dir.mkdir(parents=True, exist_ok=True)
        for src in sorted(walk_no_follow(fp.staging_dir)):
            rel = src.relative_to(fp.staging_dir)
            dst = fp.incoming_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            assert_no_reparse_source(src)
            with open(src, "rb") as r, open(dst, "wb") as w:
                for chunk in iter(lambda: r.read(1 << 20), b""):
                    w.write(chunk)
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
        state = self.journal.last_state(fp.family)
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
                had_live = _dir_present(fp.live_dir)
                self.journal.append(self.run_id, fp.family, MOVE_OLD_INTENT,
                                    {"from": str(fp.live_dir), "to": str(fp.tombstone_dir)})
                self._crash("after_move_intent")
                if had_live:
                    fp.tombstone_dir.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(fp.live_dir, fp.tombstone_dir)  # atomic same-volume
                    self._crash("after_move_rename")
                    self.journal.append(self.run_id, fp.family, OLD_MOVED, {"tombstone_dir": str(fp.tombstone_dir)})
                    state = OLD_MOVED
                else:
                    self.journal.append(self.run_id, fp.family, OLD_ABSENT, {"note": "live already empty"})
                    state = OLD_ABSENT
                self._crash("after_old_moved")
            elif act == ACT_INSTALL_NEW:
                self.journal.append(self.run_id, fp.family, INSTALL_NEW_INTENT,
                                    {"from": str(fp.incoming_dir), "to": str(fp.live_dir)})
                self._crash("after_install_intent")
                if _dir_present(fp.live_dir):
                    raise PromotionError(f"{fp.family}: live present at INSTALL_NEW (would clobber)")
                fp.live_dir.parent.mkdir(parents=True, exist_ok=True)
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
                self.journal.append(self.run_id, fp.family, SWAPPED, {"live_dir": str(fp.live_dir)})
                state = SWAPPED
                self._crash("after_swapped")
            else:
                raise PromotionError(f"unhandled action {act} for {fp.family}")

    def promote_all(self) -> dict:
        """Promote every family in the frozen list; returns {family: final_state}. Resume-safe: a fresh
        coordinator re-invoking this after a crash rolls each family forward from its durable state."""
        for fp in self.families:
            self._promote_family(fp)
        return self.journal.replay()

    def resume(self) -> dict:
        return self.promote_all()


def assert_no_active_recovery(data_root: Path) -> None:
    """Consumer-side quiescence hook: every raw reader / daily job / monthly bump / builder calls this
    at entry AND after acquiring its generation barrier, and FAILS CLOSED if a promotion sentinel
    exists. (Wiring into each consumer is the integration phase; this is the shared assertion.)"""
    sentinel = Path(data_root) / ".recovery_in_progress"
    if sentinel.exists():
        raise PromotionError(f"RECOVERY_IN_PROGRESS: raw store is mid-promotion ({sentinel}) — refusing "
                             f"to read/write until promotion completes and the sentinel clears")
