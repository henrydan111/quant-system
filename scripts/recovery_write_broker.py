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
import time
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

    # LockFileEx/UnlockFileEx: a byte-range OS lock taken on a HELD HANDLE (GPT impl re-review #4 P0).
    # This is what closes the validate-then-reopen-by-pathname TOCTOU that FileLock(str(path)) has —
    # the lock lives on the handle-relative-opened file object, no pathname is ever re-walked.
    LOCKFILE_FAIL_IMMEDIATELY = 0x00000001
    LOCKFILE_EXCLUSIVE_LOCK = 0x00000002

    class _OVERLAPPED(ctypes.Structure):
        _fields_ = [("Internal", ctypes.c_void_p), ("InternalHigh", ctypes.c_void_p),
                    ("Offset", wintypes.DWORD), ("OffsetHigh", wintypes.DWORD),
                    ("hEvent", wintypes.HANDLE)]

    _k32.LockFileEx.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                                wintypes.DWORD, ctypes.POINTER(_OVERLAPPED)]
    _k32.LockFileEx.restype = wintypes.BOOL
    _k32.UnlockFileEx.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.POINTER(_OVERLAPPED)]
    _k32.UnlockFileEx.restype = wintypes.BOOL
    ERROR_LOCK_VIOLATION = 33
    ERROR_IO_PENDING = 997

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

    # HANDLE-RELATIVE RENAME (GPT impl re-review #7 P0-2): os.replace(tmp, final) re-walks BOTH
    # pathnames after the safe write, so a parent swapped in that window lands the file outside the
    # root. NtSetInformationFile(FileRenameInformation) renames RELATIVE to a held parent handle
    # (RootDirectory), so no pathname is re-resolved.
    DELETE = 0x00010000
    FileRenameInformation = 10
    _ntdll.NtSetInformationFile.restype = wintypes.LONG
    _ntdll.NtSetInformationFile.argtypes = [wintypes.HANDLE, ctypes.POINTER(_IO_STATUS_BLOCK),
                                            wintypes.LPVOID, wintypes.ULONG, wintypes.ULONG]
    _k32.SetFileTime.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME),
                                 ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME)]
    _k32.SetFileTime.restype = wintypes.BOOL


class WriteBrokerError(RuntimeError):
    pass


#: sharing mask used for the DURATION of a write/create/rename chain (GPT impl re-review #8 P0).
#: Handle-relative opening stops the NAME being re-resolved; forbidding delete-sharing additionally
#: stops the held OBJECT (root, an intermediate dir, or the leaf) being renamed out of the root
#: mid-operation. Restored as soon as the handles close, so ordinary replace/delete of staged outputs
#: keeps working between operations.
_WRITE_SHARE = (FILE_SHARE_READ | FILE_SHARE_WRITE) if sys.platform == "win32" else 0


class NoFollowWriteBroker:
    """Validates that a path is safely inside `root` with NO reparse point in its realized ancestry,
    using real OS handles (not just lexical checks). Construction fails closed off-Windows."""

    def __init__(self, root: Path):
        if sys.platform != "win32":
            raise WriteBrokerError("no-follow write broker requires Windows; write modes fail closed elsewhere")
        self.root = Path(root)
        if not self.root.exists():
            raise WriteBrokerError(f"broker root does not exist: {self.root}")
        # GPT impl re-review #7 P0-1: the root BOOTSTRAP itself must not resolve by pathname.
        # CreateFileW(str(self.root)) walks the WHOLE name, so an ANCESTOR of the run root (e.g.
        # RECOVERY_ROOT) swapped for a junction redirected every "validated" write outside — and if the
        # swap happened BEFORE construction, the broker cached the EXTERNAL directory's identity as
        # legitimate, so comparing cached ids could never detect it. The run root is now opened by
        # walking from the VOLUME ANCHOR (C:\ — the trusted anchor of this threat model; re-mounting the
        # system volume is out of scope) with every component opened HANDLE-RELATIVE and no-follow.
        h = self._open_root_from_volume_anchor()
        try:
            info = _BY_HANDLE_FILE_INFORMATION()
            if not _k32.GetFileInformationByHandle(h, ctypes.byref(info)):
                raise WriteBrokerError(f"GetFileInformationByHandle failed for {self.root}")
            self._root_id = (info.dwVolumeSerialNumber,
                             (info.nFileIndexHigh << 32) | info.nFileIndexLow)
            buf = ctypes.create_unicode_buffer(32768)
            n = _k32.GetFinalPathNameByHandleW(h, buf, len(buf), VOLUME_NAME_DOS)
            if n == 0 or n >= len(buf):
                raise WriteBrokerError(f"GetFinalPathNameByHandleW failed for {self.root}")
            self._root_final = buf.value
        finally:
            _k32.CloseHandle(h)

    def _open_root_from_volume_anchor(self, share: int = None):
        """Open the RUN ROOT by walking from the volume anchor, every component handle-relative and
        no-follow (GPT impl re-review #7 P0-1). Returns a directory handle the caller closes."""
        anchor = Path(self.root.anchor)                      # e.g. 'C:\\'
        if not str(anchor).strip() or not self.root.is_absolute():
            raise WriteBrokerError(f"broker root {self.root} has no volume anchor — refusing")
        share_mask = (FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE) if share is None else share
        cur = _k32.CreateFileW(str(anchor),
                               FILE_LIST_DIRECTORY | FILE_TRAVERSE | FILE_READ_ATTRIBUTES | SYNCHRONIZE,
                               share_mask, None, OPEN_EXISTING,
                               FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, None)
        if cur == INVALID_HANDLE_VALUE:
            raise WriteBrokerError(f"cannot open volume anchor {anchor}: "
                                   f"WinError {ctypes.get_last_error()}")
        try:
            for part in self.root.relative_to(anchor).parts:
                nxt = self._nt_open_relative(
                    cur, part, directory=True, disposition=FILE_OPEN,
                    access=FILE_LIST_DIRECTORY | FILE_TRAVERSE | FILE_READ_ATTRIBUTES | SYNCHRONIZE,
                    share=share)
                try:
                    self._check_handle(nxt, part)            # a junctioned ANCESTOR refuses here
                except WriteBrokerError:
                    _k32.CloseHandle(nxt)
                    raise
                _k32.CloseHandle(cur)
                cur = nxt
            return cur
        except Exception:
            _k32.CloseHandle(cur)
            raise

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

    def _nt_open_relative(self, parent_h, name: str, *, directory: bool, disposition: int, access: int,
                          share: int = None):
        """Open/create `name` STRICTLY relative to the already-held `parent_h` directory object. Because
        RootDirectory pins resolution to that handle, no ancestor swap can redirect us; FILE_OPEN_REPARSE
        _POINT makes a swapped-in child open as the reparse point itself, which _check_handle refuses.

        `share` overrides the sharing mask (GPT impl re-review #5 P0). The default keeps
        READ|WRITE|DELETE for the write path; a LOCK leaf must omit FILE_SHARE_DELETE, else the file can
        be unlinked while held and a second holder locks a NEW file at the same pathname — the lock
        would no longer mutually exclude."""
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
        share_mask = (FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE) if share is None else share
        st = _ntdll.NtCreateFile(ctypes.byref(h), access, ctypes.byref(oa), ctypes.byref(iosb), None,
                                 0, share_mask, disposition, opts, None, 0)
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

    def _root_handle(self, share: int = None):
        """The authoritative run-root handle: walked from the VOLUME ANCHOR, every component
        handle-relative and no-follow (GPT impl re-review #7 P0-1 — CreateFileW(str(self.root)) let a
        junctioned ANCESTOR redirect every write). `share` omits FILE_SHARE_DELETE for lock chains
        (#6 P0), so an ancestor cannot be renamed between parent-open and leaf-open.

        The object identity is re-checked against the one bound at construction: even if the whole
        pathname now resolves elsewhere, a DIFFERENT directory object refuses."""
        h = self._open_root_from_volume_anchor(share)
        try:
            self._check_handle(h, str(self.root))
            info = _BY_HANDLE_FILE_INFORMATION()
            if not _k32.GetFileInformationByHandle(h, ctypes.byref(info)):
                raise WriteBrokerError(f"GetFileInformationByHandle failed for {self.root}")
            got = (info.dwVolumeSerialNumber, (info.nFileIndexHigh << 32) | info.nFileIndexLow)
            if got != self._root_id:
                raise WriteBrokerError(f"REFUSED: {self.root} now resolves to a DIFFERENT directory "
                                       f"object than the one bound at construction — the run root was "
                                       f"swapped underneath us")
        except WriteBrokerError:
            _k32.CloseHandle(h)
            raise
        return h

    def _dir_handle_chain(self, rel_parts, *, create: bool, share: int = None):
        """Walk root->...->rel_parts[-1] opening EACH component relative to its parent handle. Returns
        the final directory handle (caller closes). `create=True` creates missing components in place.
        `share` (GPT impl re-review #6 P0) propagates to the root AND every intermediate component: a
        lock chain opened without FILE_SHARE_DELETE cannot have an ancestor renamed out from under it."""
        cur = self._root_handle(share)
        try:
            for part in rel_parts:
                nxt = self._nt_open_relative(
                    cur, part, directory=True,
                    disposition=FILE_OPEN_IF if create else FILE_OPEN,
                    access=FILE_LIST_DIRECTORY | FILE_TRAVERSE | FILE_READ_ATTRIBUTES | SYNCHRONIZE,
                    share=share)
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
        # GPT impl re-review #8 P0: the chain forbids delete-sharing FOR THE DURATION — a
        # handle-relative open stops the NAME being re-walked, but the held directory OBJECT could
        # still be renamed out of the root mid-walk, so later components landed outside. Sharing is
        # restored the moment the handles close, so staged outputs stay replaceable/removable.
        h = self._dir_handle_chain(target_dir.relative_to(self.root).parts, create=True,
                                   share=_WRITE_SHARE)
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
        # the chain AND the leaf forbid delete-sharing while the write is in flight (#8 P0): a child
        # process could otherwise rename the leaf, or move the root, and the bytes landed outside.
        parent_h = self._dir_handle_chain(target.parent.relative_to(self.root).parts, create=True,
                                          share=_WRITE_SHARE)
        try:
            # FILE_OPEN_IF = open-or-create WITHOUT truncating: we must inspect before destroying bytes
            fh = self._nt_open_relative(parent_h, target.name, directory=False,
                                        disposition=FILE_OPEN_IF,
                                        access=GENERIC_WRITE | FILE_READ_ATTRIBUTES | SYNCHRONIZE,
                                        share=_WRITE_SHARE)
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

    def replace_into(self, tmp: Path, final: Path) -> None:
        """Atomically rename `tmp` onto `final` RELATIVE to a held parent directory handle (GPT impl
        re-review #7 P0-2). os.replace(tmp, final) re-walks BOTH pathnames after the safe write, so a
        parent swapped in that window landed the file OUTSIDE the root. Here the parent chain is opened
        handle-relative/no-follow, the temp file is opened relative to it with DELETE access, and
        NtSetInformationFile(FileRenameInformation) renames it using that handle as RootDirectory — no
        pathname is re-resolved. Both paths must share the same broker-validated parent."""
        import struct
        tmp = self.validate_ancestry(tmp)
        final = self.validate_ancestry(final)
        if tmp.parent != final.parent:
            raise WriteBrokerError(f"REFUSED: handle-relative replace requires one parent "
                                   f"({tmp.parent} != {final.parent})")
        # #8 P0: a relative rename does not re-walk the NAME, but parent_h itself could be moved out
        # of the root after we hold it — the rename then "succeeded" into the moved external tree.
        # Forbid delete-sharing on the chain for the duration.
        parent_h = self._dir_handle_chain(tmp.parent.relative_to(self.root).parts, create=False,
                                          share=_WRITE_SHARE)
        try:
            # FILE_READ_ATTRIBUTES is required for the _check_handle reparse/hard-link inspection
            fh = self._nt_open_relative(parent_h, tmp.name, directory=False, disposition=FILE_OPEN,
                                        access=DELETE | FILE_READ_ATTRIBUTES | SYNCHRONIZE,
                                        share=_WRITE_SHARE)
            try:
                self._check_handle(fh, str(tmp))
                name = final.name.encode("utf-16-le")
                # x64 FILE_RENAME_INFORMATION: BOOLEAN + pad(7) + HANDLE + ULONG + WCHAR[]
                head = struct.pack("<B7xQI", 1, parent_h, len(name))
                buf = ctypes.create_string_buffer(head + name, len(head) + len(name))
                iosb = _IO_STATUS_BLOCK()
                st = _ntdll.NtSetInformationFile(fh, ctypes.byref(iosb), buf, len(buf),
                                                 FileRenameInformation)
                self._nt_check(st, f"NtSetInformationFile(rename {tmp.name} -> {final.name})")
            finally:
                _k32.CloseHandle(fh)
        finally:
            _k32.CloseHandle(parent_h)

    def copy_into(self, src: Path, dst: Path) -> None:
        """Copy a validated no-follow SOURCE into a broker-validated dest (preserving mtime)."""
        import msvcrt
        assert_no_reparse_source(src)
        st = os.stat(src)
        with open(src, "rb") as s, self.open_for_write(dst, "wb") as d:
            shutil.copyfileobj(s, d)
            d.flush()
            # GPT impl re-review #7: set the times on the HELD HANDLE, not by pathname — os.utime(dst)
            # after the write is one more re-walk of a name the ancestor swap could have redirected.
            try:
                def _ft(epoch):
                    v = int(epoch * 10_000_000) + 116_444_736_000_000_000
                    return wintypes.FILETIME(v & 0xFFFFFFFF, v >> 32)
                at, mt = _ft(st.st_atime), _ft(st.st_mtime)
                _k32.SetFileTime(msvcrt.get_osfhandle(d.fileno()), None,
                                 ctypes.byref(at), ctypes.byref(mt))
            except OSError:
                pass

    def file_lock(self, target: Path, *, timeout: float = 600.0, poll: float = 0.02):
        """A cross-process OS lock taken on a HANDLE opened through the no-follow handle chain — NOT a
        pathname (GPT impl re-review #4 P0). Closes the FileLock(str(path)) TOCTOU: the lock file's
        parent chain is walked relative to held handles, the leaf is opened RELATIVE to the validated
        parent and refused if it is a reparse point/hard link, and the byte-range lock (LockFileEx) is
        taken on THAT handle — a junction swapped in after validation opens as the reparse point and
        refuses, never redirects. The lock file is NEVER deleted on release (deleting a pathname is what
        let the old code remove an external file); a persistent zero-byte lock file is standard.

        Returns a context manager; __enter__ raises WriteBrokerError('lock BUSY') on timeout."""
        broker = self
        target = self.validate_ancestry(target)
        rel = target.relative_to(self.root)

        # the ENTIRE lock chain (root + every intermediate dir + the leaf) forbids delete-sharing
        _LOCK_SHARE = FILE_SHARE_READ | FILE_SHARE_WRITE

        class _HandleLock:
            def __enter__(_self):
                parent_h = broker._dir_handle_chain(rel.parent.parts, create=True, share=_LOCK_SHARE)
                try:
                    # NO FILE_SHARE_DELETE on a lock leaf (GPT impl re-review #5 P0): with it, another
                    # process could unlink run_execution.lock while we hold it, after which a NEW file
                    # at the same pathname granted a SECOND lock — the dispatch->call->close span (and
                    # abandon/consolidation, which share this guard) stopped mutually excluding.
                    fh = broker._nt_open_relative(
                        parent_h, rel.name, directory=False, disposition=FILE_OPEN_IF,
                        access=GENERIC_READ | GENERIC_WRITE | FILE_READ_ATTRIBUTES | SYNCHRONIZE,
                        share=_LOCK_SHARE)
                finally:
                    _k32.CloseHandle(parent_h)
                try:
                    broker._check_handle(fh, str(target))     # reparse/hard-link refusal on the leaf
                except Exception:
                    _k32.CloseHandle(fh)
                    raise
                _self._fh = fh
                ov = _OVERLAPPED()
                deadline = time.monotonic() + max(0.0, timeout)
                while True:
                    ok = _k32.LockFileEx(fh, LOCKFILE_EXCLUSIVE_LOCK | LOCKFILE_FAIL_IMMEDIATELY,
                                         0, 1, 0, ctypes.byref(ov))
                    if ok:
                        return _self
                    err = ctypes.get_last_error()
                    if err not in (ERROR_LOCK_VIOLATION, ERROR_IO_PENDING) or time.monotonic() >= deadline:
                        _k32.CloseHandle(fh)
                        raise WriteBrokerError(f"run-execution lock BUSY on {target} "
                                               f"(WinError {err}) — another holder owns it; refusing")
                    time.sleep(poll)

            def __exit__(_self, *exc):
                ov = _OVERLAPPED()
                try:
                    _k32.UnlockFileEx(_self._fh, 0, 1, 0, ctypes.byref(ov))
                finally:
                    _k32.CloseHandle(_self._fh)   # release the lock; NEVER delete the file
                return False
        return _HandleLock()


def create_dir_tree_no_follow(target: Path) -> None:
    """Create `target` (and missing parents) walking from the VOLUME ANCHOR,每 component opened or
    created RELATIVE to its already-held parent handle (GPT impl re-review #8 P0).

    `Path.mkdir(parents=True)` resolves the whole pathname, so an ancestor swapped for a junction after
    the lexical pre-check created the run root INSIDE the external target (`external_run_created=True`,
    reproduced). This is the bootstrap twin of NoFollowWriteBroker._open_root_from_volume_anchor: the
    broker cannot be used here because it REQUIRES an existing root, so the creation path needs its own
    anchored walk. Every component is opened with FILE_OPEN_REPARSE_POINT and refused if it is a reparse
    point/hard link; the directory chain forbids delete-sharing for the duration so a component cannot be
    moved out from under the walk."""
    if sys.platform != "win32":
        raise WriteBrokerError("create_dir_tree_no_follow requires Windows")
    target = Path(target)
    if not target.is_absolute():
        raise WriteBrokerError(f"REFUSED: {target} is not absolute")
    anchor = Path(target.anchor)
    share = FILE_SHARE_READ | FILE_SHARE_WRITE          # no delete-sharing while we hold the chain
    probe = NoFollowWriteBroker.__new__(NoFollowWriteBroker)   # primitives only; no root binding
    cur = _k32.CreateFileW(str(anchor),
                           FILE_LIST_DIRECTORY | FILE_TRAVERSE | FILE_READ_ATTRIBUTES | SYNCHRONIZE,
                           share, None, OPEN_EXISTING,
                           FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, None)
    if cur == INVALID_HANDLE_VALUE:
        raise WriteBrokerError(f"cannot open volume anchor {anchor}: WinError {ctypes.get_last_error()}")
    try:
        parts = target.relative_to(anchor).parts
        for i, part in enumerate(parts):
            last = (i == len(parts) - 1)
            nxt = probe._nt_open_relative(
                cur, part, directory=True,
                # the LEAF must not already exist (mirrors mkdir(exist_ok=False)); parents may
                disposition=FILE_CREATE if last else FILE_OPEN_IF,
                access=FILE_LIST_DIRECTORY | FILE_TRAVERSE | FILE_READ_ATTRIBUTES | SYNCHRONIZE,
                share=share)
            try:
                probe._check_handle(nxt, part)
            except WriteBrokerError:
                _k32.CloseHandle(nxt)
                raise
            _k32.CloseHandle(cur)
            cur = nxt
    finally:
        _k32.CloseHandle(cur)


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
