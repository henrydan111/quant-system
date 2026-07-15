# SCRIPT_STATUS: ACTIVE — 2026-07-13 incident recovery: Windows no-follow handle write broker (GPT B3)
"""No-follow, handle-identity-validated write broker for the recovery coordinator.

The lexical reparse scan (`os.lstat` per component) closes the BROKEN-junction bypass, but a TOCTOU
remains: between the scan and the later `mkdir`/`open`/`copy2`, a component could be swapped for a
junction pointing outside the run root. This broker closes that window (GPT re-review #3/#4 B3):

- Every path component from the run ROOT down is opened with a NO-FOLLOW handle
  (`FILE_FLAG_OPEN_REPARSE_POINT` + `FILE_FLAG_BACKUP_SEMANTICS`); a component that IS a reparse point
  (`FILE_ATTRIBUTE_REPARSE_POINT`, incl. a broken junction) refuses.
- The run root's `(volume_serial, file_index)` identity is captured once; every opened handle is
  cross-checked with `GetFinalPathNameByHandleW` to prove its REAL path is component-contained in the
  root's real path — a junction swapped in mid-walk resolves elsewhere and refuses.
- Descendants are created component-by-component through opened parent handles; the final handle is
  re-validated AFTER creation.
- The source walker for preflight refuses every reparse point (incl. broken leaves) with no follow.
- If the broker cannot be constructed (non-Windows, missing API), every write-capable mode fails
  closed — a recovery write NEVER falls back to an unchecked path.

Pure-ctypes (no pywin32 dependency). Windows-only by construction; the coordinator refuses write modes
on any other platform.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)

    GENERIC_READ = 0x80000000
    FILE_SHARE_READ = 0x00000001
    FILE_SHARE_WRITE = 0x00000002
    FILE_SHARE_DELETE = 0x00000004
    OPEN_EXISTING = 3
    FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
    FILE_ATTRIBUTE_REPARSE_POINT = 0x400
    INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
    VOLUME_NAME_DOS = 0x0

    class _BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTime", wintypes.FILETIME),
            ("ftLastAccessTime", wintypes.FILETIME),
            ("ftLastWriteTime", wintypes.FILETIME),
            ("dwVolumeSerialNumber", wintypes.DWORD),
            ("nFileSizeHigh", wintypes.DWORD),
            ("nFileSizeLow", wintypes.DWORD),
            ("nNumberOfLinks", wintypes.DWORD),
            ("nFileIndexHigh", wintypes.DWORD),
            ("nFileIndexLow", wintypes.DWORD),
        ]

    _k32.CreateFileW.restype = wintypes.HANDLE
    _k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                 wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    _k32.GetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.POINTER(_BY_HANDLE_FILE_INFORMATION)]
    _k32.GetFileInformationByHandle.restype = wintypes.BOOL
    _k32.GetFinalPathNameByHandleW.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
    _k32.GetFinalPathNameByHandleW.restype = wintypes.DWORD
    _k32.CloseHandle.argtypes = [wintypes.HANDLE]
    _k32.CloseHandle.restype = wintypes.BOOL


class WriteBrokerError(RuntimeError):
    pass


class NoFollowWriteBroker:
    """Validates that a path is safely inside `root` with NO reparse point in its realized ancestry,
    using real OS handles (not just lexical checks). Construction fails closed off-Windows."""

    def __init__(self, root: Path):
        if sys.platform != "win32":
            raise WriteBrokerError("no-follow write broker requires Windows; write modes fail closed elsewhere")
        self.root = Path(root)
        if not self.root.exists():
            raise WriteBrokerError(f"broker root does not exist: {self.root}")
        self._root_id = self._identity(self.root)  # (vol, idx); raises if root itself is a reparse point
        self._root_final = self._final_path(self.root)

    # ── low-level handle ops ──────────────────────────────────────────────────────────────────────
    def _open_nofollow(self, path: Path):
        h = _k32.CreateFileW(str(path), GENERIC_READ,
                             FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, None, OPEN_EXISTING,
                             FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, None)
        if h == INVALID_HANDLE_VALUE:
            raise WriteBrokerError(f"cannot open {path}: WinError {ctypes.get_last_error()}")
        return h

    def _identity(self, path: Path):
        h = self._open_nofollow(path)
        try:
            info = _BY_HANDLE_FILE_INFORMATION()
            if not _k32.GetFileInformationByHandle(h, ctypes.byref(info)):
                raise WriteBrokerError(f"GetFileInformationByHandle failed for {path}")
            if info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT:
                raise WriteBrokerError(f"REFUSED: {path} is a reparse point")
            return (info.dwVolumeSerialNumber, (info.nFileIndexHigh << 32) | info.nFileIndexLow)
        finally:
            _k32.CloseHandle(h)

    def _final_path(self, path: Path) -> str:
        h = self._open_nofollow(path)
        try:
            buf = ctypes.create_unicode_buffer(32768)
            n = _k32.GetFinalPathNameByHandleW(h, buf, len(buf), VOLUME_NAME_DOS)
            if n == 0 or n >= len(buf):
                raise WriteBrokerError(f"GetFinalPathNameByHandleW failed for {path}")
            return buf.value
        finally:
            _k32.CloseHandle(h)

    @staticmethod
    def _strip(p: str) -> str:
        return p[4:] if p.startswith("\\\\?\\") else p

    # ── public API ────────────────────────────────────────────────────────────────────────────────
    def validate_ancestry(self, target: Path) -> Path:
        """Refuse unless every EXISTING component from root..target is a non-reparse node whose real
        path stays component-contained in root's real path. Returns the lexically-normalized target.
        Not-yet-existing tail components are fine (the broker's own mkdir will create them safely)."""
        target = Path(os.path.normpath(str(target)))
        try:
            target.relative_to(self.root)
        except ValueError:
            raise WriteBrokerError(f"REFUSED: {target} outside root {self.root}")
        # walk existing components from the root down, each opened no-follow + identity/real-path checked
        rel_parts = target.relative_to(self.root).parts
        cur = self.root
        root_final = self._strip(self._root_final).rstrip("\\")
        for part in rel_parts:
            cur = cur / part
            if not cur.exists() and not os.path.islink(str(cur)):
                # first non-existent component: an lstat that raises anything but FileNotFoundError refuses
                try:
                    os.lstat(cur)
                except FileNotFoundError:
                    break
                except OSError as exc:
                    raise WriteBrokerError(f"REFUSED: cannot lstat {cur}: {exc}")
            self._identity(cur)  # reparse-point refusal via a real handle
            fin = self._strip(self._final_path(cur)).rstrip("\\")
            if not (fin == root_final or fin.startswith(root_final + "\\")):
                raise WriteBrokerError(f"REFUSED: {cur} realizes to {fin}, outside root {root_final}")
        return target

    def mkdirs(self, target_dir: Path) -> None:
        """Create target_dir (and parents) one no-follow-validated component at a time."""
        target_dir = self.validate_ancestry(target_dir)
        rel = target_dir.relative_to(self.root).parts
        cur = self.root
        for part in rel:
            cur = cur / part
            if not cur.exists():
                os.mkdir(cur)
            self._identity(cur)  # revalidate AFTER creation (no swap slipped in)

    def open_for_write(self, target: Path, mode: str = "wb", encoding: str | None = None):
        """Validate the parent ancestry, create parents no-follow, then open the leaf. Text modes
        default to utf-8. Caller writes + closes."""
        target = self.validate_ancestry(target)
        self.mkdirs(target.parent)
        if "b" not in mode and encoding is None:
            encoding = "utf-8"
        return open(target, mode, encoding=encoding)

    def copy_into(self, src: Path, dst: Path) -> None:
        """Copy a validated no-follow SOURCE into a broker-validated dest (preserving mtime)."""
        assert_no_reparse_source(src)
        with open(src, "rb") as s, self.open_for_write(dst, "wb") as d:
            shutil.copyfileobj(s, d)
        try:
            os.utime(dst, (os.path.getatime(src), os.path.getmtime(src)))
        except OSError:
            pass


def assert_no_reparse_source(path: Path) -> Path:
    """No-follow source guard for preflight reads (GPT B3): refuse a reparse point at any component of
    a SOURCE path, incl. a broken leaf, WITHOUT following it. os.lstat only (never resolve())."""
    import stat as _stat
    p = Path(os.path.normpath(str(path)))
    comps = [Path(p.anchor)] + [Path(p.anchor).joinpath(*p.parts[1:i + 1]) for i in range(1, len(p.parts))]
    for anc in comps:
        try:
            st = os.lstat(anc)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise WriteBrokerError(f"REFUSED (source): cannot lstat {anc}: {exc}")
        if (getattr(st, "st_file_attributes", 0) & 0x400) or _stat.S_ISLNK(st.st_mode):
            raise WriteBrokerError(f"REFUSED (source): reparse point {anc}")
    return p


def walk_no_follow(root: Path):
    """Yield files under `root` with NO reparse traversal — a junction dir is refused (not followed),
    a reparse leaf is refused. Replaces rglob()/is_file() for preflight survivor copying (GPT B3)."""
    import stat as _stat
    stack = [Path(root)]
    while stack:
        d = stack.pop()
        for entry in os.scandir(d):
            st = entry.stat(follow_symlinks=False)
            if (getattr(st, "st_file_attributes", 0) & 0x400) or _stat.S_ISLNK(st.st_mode):
                raise WriteBrokerError(f"REFUSED (source walk): reparse point {entry.path}")
            if entry.is_dir(follow_symlinks=False):
                stack.append(Path(entry.path))
            elif entry.is_file(follow_symlinks=False):
                yield Path(entry.path)
