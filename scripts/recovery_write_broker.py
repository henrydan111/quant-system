# SCRIPT_STATUS: ACTIVE — 2026-07-13 incident recovery: Windows no-follow handle write broker (GPT B3)
"""No-follow, handle-identity-validated write broker for the recovery coordinator.

The lexical reparse scan (`os.lstat` per component) closes the BROKEN-junction bypass, but a TOCTOU
remains: between the scan and the later `mkdir`/`open`/`copy2`, a component could be swapped for a
junction pointing outside the run root. This broker closes that window (GPT re-review #3/#4 B3):

- **Writes are HANDLE-RELATIVE, never by pathname** (GPT re-review #5 F1 BLOCKER). An earlier version
  validated the ancestry and then called `open(target, ...)`, which re-walked the pathname — a junction
  swapped into the gap redirected the write OUTSIDE the root (reproduced). Now every component is opened
  RELATIVE to its already-held parent handle via `NtCreateFile` with `OBJECT_ATTRIBUTES.RootDirectory`,
  so no pathname is re-resolved and no swap can redirect us; `FILE_OPEN_REPARSE_POINT` makes a
  swapped-in child open as the reparse point ITSELF, which is then refused.
- The leaf is opened NON-truncating (`FILE_OPEN_IF`), refused if it is a reparse point or a HARD LINK
  (`nNumberOfLinks > 1` — a second name for a file that may live outside the root), and only THEN
  truncated. Nothing outside the root can be created or truncated, even mid-swap.
- The lexical/handle `validate_ancestry` pre-check still refuses a reparse point (incl. a BROKEN
  junction, which `Path.exists()` reports as absent) and proves real-path containment via
  `GetFinalPathNameByHandleW`; it is a fast pre-filter, NOT the security boundary — the handle chain is.
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
    _k32.SetEndOfFile.argtypes = [wintypes.HANDLE]
    _k32.SetEndOfFile.restype = wintypes.BOOL
    _k32.SetFilePointerEx.argtypes = [wintypes.HANDLE, ctypes.c_longlong,
                                      ctypes.POINTER(ctypes.c_longlong), wintypes.DWORD]
    _k32.SetFilePointerEx.restype = wintypes.BOOL

    # ── ntdll: HANDLE-RELATIVE open/create (GPT re-review #5 F1 BLOCKER) ──────────────────────────
    # CreateFileW resolves the WHOLE pathname, so FILE_FLAG_OPEN_REPARSE_POINT only protects the FINAL
    # component — an ANCESTOR swapped for a junction after validation still redirects the write (the
    # exact scan->write TOCTOU GPT reproduced). NtCreateFile with OBJECT_ATTRIBUTES.RootDirectory set to
    # a handle we ALREADY hold resolves the child RELATIVE to that open directory object: no pathname is
    # re-walked, so no swap can redirect it, and FILE_OPEN_REPARSE_POINT makes a swapped child open as
    # the reparse point ITSELF (which we then refuse) instead of following it.
    _ntdll = ctypes.WinDLL("ntdll", use_last_error=True)

    GENERIC_WRITE = 0x40000000
    SYNCHRONIZE = 0x00100000
    FILE_LIST_DIRECTORY = 0x0001
    FILE_TRAVERSE = 0x0020
    FILE_READ_ATTRIBUTES = 0x0080  # required for GetFileInformationByHandle on our handles
    # CreateDisposition
    FILE_OPEN = 1
    FILE_CREATE = 2
    FILE_OPEN_IF = 3
    # CreateOptions
    FILE_DIRECTORY_FILE = 0x00000001
    FILE_SYNCHRONOUS_IO_NONALERT = 0x00000020
    FILE_NON_DIRECTORY_FILE = 0x00000040
    FILE_OPEN_REPARSE_POINT = 0x00200000
    FILE_BEGIN = 0

    class _UNICODE_STRING(ctypes.Structure):
        _fields_ = [("Length", wintypes.USHORT), ("MaximumLength", wintypes.USHORT),
                    ("Buffer", wintypes.LPWSTR)]

    class _OBJECT_ATTRIBUTES(ctypes.Structure):
        _fields_ = [("Length", wintypes.ULONG), ("RootDirectory", wintypes.HANDLE),
                    ("ObjectName", ctypes.POINTER(_UNICODE_STRING)), ("Attributes", wintypes.ULONG),
                    ("SecurityDescriptor", wintypes.LPVOID), ("SecurityQualityOfService", wintypes.LPVOID)]

    class _IO_STATUS_BLOCK(ctypes.Structure):
        _fields_ = [("Status", wintypes.LONG), ("Information", ctypes.c_size_t)]

    _ntdll.NtCreateFile.restype = wintypes.LONG
    _ntdll.NtCreateFile.argtypes = [ctypes.POINTER(wintypes.HANDLE), wintypes.DWORD,
                                    ctypes.POINTER(_OBJECT_ATTRIBUTES), ctypes.POINTER(_IO_STATUS_BLOCK),
                                    ctypes.POINTER(ctypes.c_longlong), wintypes.ULONG, wintypes.ULONG,
                                    wintypes.ULONG, wintypes.ULONG, wintypes.LPVOID, wintypes.ULONG]
    _ntdll.RtlNtStatusToDosError.restype = wintypes.ULONG
    _ntdll.RtlNtStatusToDosError.argtypes = [wintypes.LONG]


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

    # ── handle-RELATIVE primitives (GPT re-review #5 F1: no pathname is ever re-walked) ───────────
    @staticmethod
    def _nt_check(status: int, what: str) -> None:
        if status < 0:  # !NT_SUCCESS
            raise WriteBrokerError(f"{what}: NTSTATUS 0x{status & 0xFFFFFFFF:08X} "
                                   f"(WinError {_ntdll.RtlNtStatusToDosError(status)})")

    def _nt_open_relative(self, parent_h, name: str, *, directory: bool, disposition: int, access: int):
        """Open/create `name` STRICTLY relative to the already-held `parent_h` directory object. Because
        RootDirectory pins resolution to that handle, no ancestor swap can redirect us; FILE_OPEN_REPARSE
        _POINT makes a swapped-in child open as the reparse point itself, which _check_handle refuses."""
        if "\\" in name or "/" in name or name in ("", ".", ".."):
            raise WriteBrokerError(f"REFUSED: non-leaf relative name {name!r}")
        us = _UNICODE_STRING()
        buf = ctypes.create_unicode_buffer(name)
        us.Buffer = ctypes.cast(buf, wintypes.LPWSTR)
        us.Length = len(name) * 2
        us.MaximumLength = us.Length + 2
        oa = _OBJECT_ATTRIBUTES()
        oa.Length = ctypes.sizeof(_OBJECT_ATTRIBUTES)
        oa.RootDirectory = wintypes.HANDLE(parent_h)
        oa.ObjectName = ctypes.pointer(us)
        oa.Attributes = 0x40  # OBJ_CASE_INSENSITIVE
        oa.SecurityDescriptor = None
        oa.SecurityQualityOfService = None
        h = wintypes.HANDLE()
        iosb = _IO_STATUS_BLOCK()
        opts = FILE_OPEN_REPARSE_POINT | (FILE_DIRECTORY_FILE if directory else
                                          (FILE_NON_DIRECTORY_FILE | FILE_SYNCHRONOUS_IO_NONALERT))
        st = _ntdll.NtCreateFile(ctypes.byref(h), access, ctypes.byref(oa), ctypes.byref(iosb), None,
                                 0, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                                 disposition, opts, None, 0)
        self._nt_check(st, f"NtCreateFile({name})")
        return h.value

    def _check_handle(self, h, label: str) -> None:
        """Refuse a reparse point (a junction/symlink swapped in) or a HARD LINK (nNumberOfLinks > 1 —
        a second name for a file that may live outside the root)."""
        info = _BY_HANDLE_FILE_INFORMATION()
        if not _k32.GetFileInformationByHandle(h, ctypes.byref(info)):
            raise WriteBrokerError(f"GetFileInformationByHandle failed for {label}")
        if info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT:
            raise WriteBrokerError(f"REFUSED: {label} is a reparse point")
        if info.nNumberOfLinks > 1:
            raise WriteBrokerError(f"REFUSED: {label} is a hard link (nNumberOfLinks="
                                   f"{info.nNumberOfLinks}) — may alias a file outside the root")

    def _root_handle(self):
        h = _k32.CreateFileW(str(self.root), FILE_LIST_DIRECTORY | FILE_TRAVERSE | FILE_READ_ATTRIBUTES | SYNCHRONIZE,
                             FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, None, OPEN_EXISTING,
                             FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, None)
        if h == INVALID_HANDLE_VALUE:
            raise WriteBrokerError(f"cannot open broker root {self.root}: WinError {ctypes.get_last_error()}")
        try:
            self._check_handle(h, str(self.root))
        except WriteBrokerError:
            _k32.CloseHandle(h)
            raise
        return h

    def _dir_handle_chain(self, rel_parts, *, create: bool):
        """Walk root->...->rel_parts[-1] opening EACH component relative to its parent handle. Returns
        the final directory handle (caller closes). `create=True` creates missing components in place."""
        cur = self._root_handle()
        try:
            for part in rel_parts:
                nxt = self._nt_open_relative(
                    cur, part, directory=True,
                    disposition=FILE_OPEN_IF if create else FILE_OPEN,
                    access=FILE_LIST_DIRECTORY | FILE_TRAVERSE | FILE_READ_ATTRIBUTES | SYNCHRONIZE)
                try:
                    self._check_handle(nxt, part)
                except WriteBrokerError:
                    _k32.CloseHandle(nxt)
                    raise
                _k32.CloseHandle(cur)
                cur = nxt
            return cur
        except Exception:
            _k32.CloseHandle(cur)
            raise

    # ── public API ────────────────────────────────────────────────────────────────────────────────
    def mkdirs(self, target_dir: Path) -> None:
        """Create target_dir (and parents) component-by-component through HELD parent handles."""
        target_dir = self.validate_ancestry(target_dir)
        h = self._dir_handle_chain(target_dir.relative_to(self.root).parts, create=True)
        _k32.CloseHandle(h)

    def open_for_write(self, target: Path, mode: str = "wb", encoding: str | None = None):
        """Open the leaf for writing through a handle chain rooted at `self.root` — NOT by pathname.
        The parent chain is walked/created relative to held handles, the leaf is created RELATIVE to the
        validated parent, then refused if it is a reparse point or a hard link, and only THEN truncated.
        Nothing outside the root can be created or truncated even if a component is swapped mid-flight."""
        if mode not in ("wb", "w", "ab", "a"):
            raise WriteBrokerError(f"unsupported broker write mode {mode!r} (use wb|w|ab|a)")
        target = self.validate_ancestry(target)
        if "b" not in mode and encoding is None:
            encoding = "utf-8"
        parent_h = self._dir_handle_chain(target.parent.relative_to(self.root).parts, create=True)
        try:
            # FILE_OPEN_IF = open-or-create WITHOUT truncating: we must inspect before destroying bytes
            fh = self._nt_open_relative(parent_h, target.name, directory=False,
                                        disposition=FILE_OPEN_IF,
                                        access=GENERIC_WRITE | FILE_READ_ATTRIBUTES | SYNCHRONIZE)
        finally:
            _k32.CloseHandle(parent_h)
        try:
            self._check_handle(fh, str(target))
            if mode in ("wb", "w"):  # truncate ONLY after the leaf proved safe
                if not _k32.SetFilePointerEx(fh, 0, None, FILE_BEGIN) or not _k32.SetEndOfFile(fh):
                    raise WriteBrokerError(f"truncate failed for {target}")
            else:  # append
                if not _k32.SetFilePointerEx(fh, 0, None, 2):  # FILE_END
                    raise WriteBrokerError(f"seek-to-end failed for {target}")
        except Exception:
            _k32.CloseHandle(fh)
            raise
        import msvcrt
        fd = msvcrt.open_osfhandle(fh, 0)  # fd now OWNS the handle; closing the file closes it
        return os.fdopen(fd, mode, encoding=encoding)

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
