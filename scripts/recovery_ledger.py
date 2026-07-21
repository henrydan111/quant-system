# SCRIPT_STATUS: ACTIVE — 2026-07-13 incident recovery: page-receipt ledger (GPT re-review #4 B2)
"""Restoration-proof ledger: coordinator-OWNED page receipts + a hash chain anchored outside the JSONL.

Why counts-and-a-boolean are not proof (GPT re-review #2..#4 B2): an adapter can claim `last_page` for a
lone page 3, hand back arbitrary bytes, or replay one empty receipt twice. This ledger removes every
one of those:

- The COORDINATOR persists each page it is handed (a DataFrame) as an immutable receipt parquet and
  computes its row count + sha256 ITSELF — the adapter's claims are never trusted.
- A frozen, hashed request plan binds each request to its endpoint/params/partition, its OWN receipt
  output path (distinct from any consolidated file — two requests can't "verify" one shared output),
  its natural (null-check) key, its content-dedup key, its page limit, and the signed contract + doc
  hashes; the plan freeze also binds the coordinator commit + the adapter-bundle hash.
- `verify_request` proves CONTIGUOUS page coverage (retries supersede), an endpoint-correct TERMINAL
  (an exact-limit last page demands a following empty page unless the contract defines another proof),
  reconciles pre-dedup / post-dedup / excess-duplicate / null-key counts against the concatenated
  receipts, REJECTS null semantic keys and unexpected duplicates, and binds the per-request output to
  the ordered page hashes.
- Every appended row carries `prev_record_hash`/`record_hash`; the chain HEAD lives in a separate file,
  so a truncated or edited JSONL tail is detected on load (fail closed).

All writes go through the no-follow broker (recovery_write_broker). No network.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path


class LedgerError(RuntimeError):
    pass


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _h(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _canon_scalar(v) -> bytes:
    """Exact, type-distinguishing bytes for one vendor value (GPT re-review #7 M1 / #8 MAJOR).

    This is SEMANTIC canonicalization, NOT physical-type fidelity (GPT re-review #10 MINOR): equal
    VALUES digest equally regardless of carrier type — Python `int(1)` and `numpy.int64(1)` collapse
    (they are the same number), as do a mixed-object column's `datetime` and `pd.Timestamp` for the same
    instant. That is the INTENT for a vendor-row dedup key: two rows differing only in pandas' physical
    dtype are the same row. What it still distinguishes are values that are genuinely different: int vs
    float vs Decimal, tz-aware vs naive, -0.0 vs 0.0 (IEEE-754 bits), and each missing sentinel
    (`None`/`pd.NA`/`pd.NaT`/float-NaN — GPT re-review #8: these had collapsed to one `NULL` token, so
    rows differing only in which sentinel they carried merged; each now has its own). Strings are
    NFC-normalized. An UNKNOWN object type REFUSES rather than falling back to `repr` (an unstable
    __repr__ could alias distinct values — the one aliasing this key must never permit)."""
    import datetime as _dt
    import decimal as _dec
    import math
    import struct
    import unicodedata
    # --- distinct missing sentinels (never one shared NULL) ---
    # These come FIRST and by type NAME: pd.NaT subclasses datetime.datetime, so a later isoformat()
    # branch would swallow it and its distinctness would rest on `NaT.isoformat() == "NaT"` — an
    # accident, not a guarantee. Name checks avoid importing pandas just to classify a sentinel.
    if v is None:
        return b"\x00NONE"
    if v.__class__.__name__ == "NaTType":
        return b"\x00NAT"
    if v.__class__.__name__ == "NAType":
        return b"\x00PDNA"
    if isinstance(v, bool):  # BEFORE int — bool is an int subclass
        return b"B1" if v else b"B0"
    if isinstance(v, bytes):
        return b"Y" + v
    if isinstance(v, str):
        return b"S" + unicodedata.normalize("NFC", v).encode("utf-8")
    if isinstance(v, int):
        return b"I" + str(int(v)).encode("ascii")  # arbitrary precision, exact
    if isinstance(v, float):
        if math.isnan(v):
            return b"\x00FNAN"          # a float NaN is NOT pd.NA and NOT None
        if math.isinf(v):
            return b"\x00INF+" if v > 0 else b"\x00INF-"
        return b"F" + struct.pack(">d", v)         # exact bits: distinguishes -0.0 from 0.0
    if isinstance(v, _dec.Decimal):
        # exact, and NEVER via float: sign/digits/exponent is the value's own identity
        sign, digits, exp = v.as_tuple()
        if not isinstance(exp, int):                # NaN / sNaN / Infinity
            # GPT re-review #9 MAJOR: this returned only the exponent tag, DROPPING sign and digits —
            # so Decimal("Infinity") == Decimal("-Infinity") and NaN123 == NaN456 at the digest layer.
            # A special value's identity is still (sign, digits, tag).
            return b"\x00DEC-" + f"{sign}:{''.join(map(str, digits))}:{exp}".encode("ascii")
        return b"D" + f"{sign}:{''.join(map(str, digits))}:{exp}".encode("ascii")
    if isinstance(v, _dt.datetime):                 # BEFORE date — datetime subclasses date
        return b"TS" + v.isoformat().encode("utf-8")   # isoformat carries the tz offset (or its absence)
    if isinstance(v, _dt.date):
        return b"DT" + v.isoformat().encode("utf-8")
    if isinstance(v, _dt.time):
        return b"TM" + v.isoformat().encode("utf-8")
    try:
        import numpy as _np
        import pandas as _pd
    except ImportError:
        raise LedgerError(f"row_payload_digest: cannot canonicalize {type(v).__name__} without pandas")
    if v is _pd.NaT:
        return b"\x00NAT"
    if v is _pd.NA:
        return b"\x00PDNA"
    if isinstance(v, _pd.Timestamp):
        return b"TS" + v.isoformat().encode("utf-8")
    if isinstance(v, _np.datetime64):
        return b"TS" + str(v).encode("ascii")
    if isinstance(v, _np.integer):
        return b"I" + str(int(v)).encode("ascii")
    if isinstance(v, _np.floating):
        return _canon_scalar(float(v))
    if isinstance(v, _np.bool_):
        return b"B1" if bool(v) else b"B0"
    if isinstance(v, _np.bytes_):
        return b"Y" + bytes(v)
    if isinstance(v, _np.str_):
        return b"S" + unicodedata.normalize("NFC", str(v)).encode("utf-8")
    # No repr fallback: an unrecognized type must be reviewed and given an encoding, not guessed at.
    raise LedgerError(
        f"row_payload_digest: no canonical encoding for {type(v).__module__}.{type(v).__name__} "
        f"({v!r:.60}). A repr fallback would make the key depend on an unstable __repr__ and could "
        f"alias distinct values — add an explicit encoding instead.")


def _assert_contained_receipt_output(rel: str, staging_data: Path) -> None:
    """A receipt_output must be a RELATIVE path with no traversal, resolving strictly under
    staging_data (GPT re-review #10 MAJOR). Absolute paths, `..`, drive-relative and UNC forms all
    refuse — otherwise a signed plan could write a fetched page outside the recovery staging area."""
    if not isinstance(rel, str) or not rel.strip():
        raise LedgerError(f"receipt_output must be a non-empty relative path (got {rel!r})")
    pr = Path(rel)
    if pr.is_absolute() or pr.drive or pr.anchor:
        raise LedgerError(f"receipt_output {rel!r} must be RELATIVE (no drive/anchor/absolute)")
    if ".." in pr.parts:
        raise LedgerError(f"receipt_output {rel!r} contains '..' — traversal is refused")
    base = Path(os.path.normpath(str(staging_data)))
    dest = Path(os.path.normpath(str(base / pr)))
    try:
        dest.relative_to(base)
    except ValueError:
        raise LedgerError(f"receipt_output {rel!r} resolves to {dest} — OUTSIDE staging_data {base}")


def request_id(endpoint: str, params: dict, partition: str) -> str:
    return _h(_canon({"e": endpoint, "p": params, "part": partition}))[:24]


def _df_sha256(df) -> tuple[str, int]:
    """Deterministic content hash + row count of a DataFrame (column-sorted, index-dropped)."""
    import pandas as pd  # noqa: F401
    d = df.reindex(sorted(df.columns), axis=1).reset_index(drop=True)
    payload = d.to_json(orient="split", date_format="iso").encode("utf-8")
    return hashlib.sha256(payload).hexdigest(), int(len(d))


# request states; failed is never terminal-valid
_TERMINAL = {"verified", "confirmed_empty"}
# Design v4 pin 3: `recipe_id` (the frozen declarative CallRecipe) and `response_scope` (the concrete,
# request-bound scope rule+values) are FROZEN plan facts — grown here so freeze-time validation covers
# them and a fetch cannot run an unfrozen recipe or an unscoped request.
_PLAN_REQUIRED = {"request_id", "endpoint", "dataset", "params", "partition", "empty_policy",
                  "receipt_output", "natural_key", "content_dedup_key", "page_limit",
                  "pagination_mode", "max_content_dups", "contract_sha256", "doc_sha256",
                  "recipe_id", "response_scope"}
_PAGINATION_MODES = {"single_page", "offset_paged"}
# Immutable run modes (design v4 F2): fixed at declaration, gate every claim BEFORE any lease. A
# synthetic run can never execute a live call (executor-mode mismatch refuses pre-lease) and can never
# be promoted (assert_run_promotable).
_RUN_MODES = {"synthetic_nonpromotable", "live_authorized"}
# columns the COORDINATOR injects — never part of a vendor payload digest
_COORDINATOR_DERIVED_COLS = frozenset({"raw_fetch_ts", "row_payload_digest",
                                       "report_rc_payload_digest", "_src_file", "_src_ordinal"})
# TYPED terminal proofs (GPT re-review #5 F2 BLOCKER). The old generic `contract_terminal` was an
# UNPROVEN claim: a FULL final page marked that way verified, skipping the trailing-empty confirmation
# — i.e. a truncated fetch could certify as complete. Each terminal now carries a MACHINE-CHECKED
# invariant and there is NO free-form escape:
_TERMINALS = {
    "last_partial":         "offset_paged: page_limit>0 AND last row_count STRICTLY < page_limit",
    "empty_terminal":       "offset_paged: last page row_count == 0 (a trailing empty page)",
    "single_page_contract": "single_page: page_limit==0 AND exactly ONE page (contract declares no paging)",
}


def _assert_terminal_proof(rid: str, row: dict, pages: dict, nums: list) -> None:
    """The ONE typed terminal-proof validator (GPT re-review #7 B1: confirm_empty did not reuse
    verify_request's mode-specific proof, so an `offset_paged` empty request could be confirmed on a
    `single_page_contract` claim). Both verification paths call this; there is no second copy to drift."""
    limit = int(row["page_limit"]) if row["page_limit"] else 0
    mode = row["pagination_mode"]
    if mode not in _PAGINATION_MODES:
        raise LedgerError(f"{rid}: bad pagination_mode {mode!r}")
    last = pages[nums[-1]]
    tc = last.get("terminal_claim")
    if tc not in _TERMINALS:
        raise LedgerError(f"{rid}: last page lacks a valid terminal_claim ({tc})")
    if mode == "single_page":
        if tc != "single_page_contract":
            raise LedgerError(f"{rid}: single_page mode requires terminal single_page_contract, got {tc}")
        if limit or len(nums) != 1:
            raise LedgerError(f"{rid}: single_page_contract requires page_limit==0 and exactly one page "
                              f"(limit={limit}, pages={len(nums)})")
    else:  # offset_paged
        if tc == "single_page_contract":
            raise LedgerError(f"{rid}: single_page_contract invalid under offset_paged")
        if not limit:
            raise LedgerError(f"{rid}: offset_paged requires a positive page_limit")
        if tc == "last_partial" and last["row_count"] >= limit:
            raise LedgerError(f"{rid}: last_partial claimed but last page is FULL "
                              f"({last['row_count']} >= {limit}) — needs a trailing empty page "
                              f"(empty_terminal); a full final page never proves termination")
        if tc == "empty_terminal" and last["row_count"] != 0:
            raise LedgerError(f"{rid}: empty_terminal claimed but last page has {last['row_count']} rows")


from dataclasses import dataclass, field


@dataclass(frozen=True)
class Claim:
    """The atomic claim_next_fetch result (design v4 F3). FETCH / RETRY_PAGE / RETRY_EMPTY_CONFIRM carry
    an ALREADY-OPEN lease (cursor derivation + lease reservation are one lock acquisition — no TOCTOU
    between deciding and reserving); the other kinds carry no lease."""
    kind: str                       # FETCH|RETRY_PAGE|RETRY_EMPTY_CONFIRM|IN_FLIGHT|VERIFY|
    #                                 CONFIRM_EMPTY|WAIT_FOR_CANARY|SKIP_TERMINAL
    page: int = 0
    offset: int = 0
    lease_id: str = ""
    opened_at: str = ""
    canary_request_id: str = ""


@dataclass(frozen=True)
class PageResult:
    """fetch_claimed_page's LEDGER-DERIVED outcome (design v4 F3): the terminal is computed from the
    recorded row_count vs the frozen pagination facts, never claimed by a caller."""
    row_count: int
    terminal_kind: str              # ""(nonterminal) | last_partial | empty_terminal | single_page_contract
    next_offset: int


# Endpoint-scoped raw-page preparation (design v4 F8): trusted producers that may add ONLY the
# coordinator-DERIVED columns declared for that endpoint, run INSIDE the ledger boundary before receipt
# hashing. report_rc's producer is deliberately NOT registered yet — its digest production lives
# downstream in pit_backend and moves here at fan-out; until then a report_rc fetch through the claimed
# path refuses (fail closed) rather than silently omitting its natural-key column.
_PREPARE_REGISTRY: dict = {}       # endpoint -> callable(df) -> df  (populated below the class)


class PageReceiptLedger:
    def __init__(self, rp, *, coordinator_commit: str, adapter_bundle_hash: str):
        # rp is the coordinator's RecoveryPaths (provides .broker() + run-root paths).
        self.rp = rp
        self.ledger_path = rp.root / "ledger" / "recovery_ledger.jsonl"
        self.plan_path = rp.root / "ledger" / "request_plan.json"
        self.head_path = rp.root / "ledger" / "ledger_chain_head.json"
        self.receipts_dir = rp.root / "ledger" / "page_receipts"
        self.coordinator_commit = coordinator_commit
        self.adapter_bundle_hash = adapter_bundle_hash
        # GPT impl re-review #2: the legacy fetch_page door is DISABLED by default — a battery-only
        # capability the fixture flips per instance; production never sets it (and a declared run mode
        # refuses it regardless, so the flag cannot leak into a production run).
        self._legacy_fetch_enabled = False
        # the cross-process RUN-EXECUTION lock (GPT impl re-review #2): held by the executing worker
        # for the whole dispatch->call->close span; abandon/consolidate must acquire it too.
        self._exec_lock_path = rp.root / "ledger" / "run_execution.lock"
        self._exec_lock_timeout = 600.0
        self._abandon_lock_timeout = 0.5
        # process-local one-shot dispatch tokens (LiveExecutor refuses a call the ledger didn't mint)
        self._dispatch_tokens: dict = {}

    def execution_guard(self, timeout: float = None):
        """The cross-process run-execution lock as a context manager. A FRESH FileLock instance per
        call — deliberately NON-reentrant even in-process, so an operator abandon in another thread
        cannot slip inside a worker's dispatch->close span.

        GPT impl re-review #3 (P0): the lock path is validated through the SAME no-follow, handle-based
        path authority as every other write (rp.assert_write -> broker.validate_ancestry), computed
        FRESH per acquisition. A junction swapped in at <run>/ledger is refused BEFORE FileLock ever
        touches the path — the raw-path FileLock previously created (and on release deleted) a lock
        file OUTSIDE the run root. Mirrors RecoveryPaths._lock exactly."""
        from filelock import FileLock, Timeout as _FLTimeout
        lock_path = self.rp.assert_write(self._exec_lock_path)   # no-follow ancestry authority
        lock = FileLock(str(lock_path))
        t = self._exec_lock_timeout if timeout is None else timeout

        class _Guard:
            def __enter__(_g):
                try:
                    lock.acquire(timeout=t)
                except _FLTimeout:
                    raise LedgerError("run-execution lock BUSY — another worker holds the "
                                      "dispatch->close span; refusing")
                return _g

            def __exit__(_g, *exc):
                lock.release()
                return False
        return _Guard()

    @staticmethod
    def _canon_dispatch_spec(spec: dict) -> str:
        """Canonicalize ONLY the load-bearing request fields the executor must not alter."""
        return _canon({k: spec.get(k) for k in
                       ("endpoint", "recipe_id", "base_params", "limit", "offset", "page",
                        "pagination_mode")})

    def consume_dispatch_token(self, token: str, spec: dict) -> bool:
        """One-shot dispatch check (GPT impl re-review #3 P0): the token proves the call came through
        fetch_claimed_page, AND the presented `spec` must match — byte-for-byte on the load-bearing
        fields — the FROZEN spec the ledger dispatched. Returns False for a missing/replayed token
        (LiveExecutor raises 'no valid token'); RAISES on a spec MISMATCH — a wrapping executor that
        kept a valid `daily` token but swapped in `broker_recommend`/other params/offset is refused
        (it previously escaped the §13 endpoint scope). The token is popped either way (one-shot)."""
        frozen = self._dispatch_tokens.pop(token, None) if token else None
        if frozen is None:
            return False
        got = self._canon_dispatch_spec(spec)
        if got != frozen:
            raise LedgerError("dispatch token spec MISMATCH — the executor was handed a request that "
                              "DIFFERS from the ledger-dispatched one (endpoint/recipe/params/cursor); "
                              "a swapped, scope-escaping request is refused")
        return True

    # ── hash chain (head anchored OUTSIDE the editable jsonl) ────────────────────────────────────
    def _genesis(self) -> str:
        return _h(_canon({"run": self.rp.run_id, "commit": self.coordinator_commit,
                          "adapters": self.adapter_bundle_hash}))

    def _read_head(self) -> dict:
        if not self.head_path.exists():
            return {"n": 0, "record_hash": self._genesis()}
        return json.loads(self.head_path.read_text(encoding="utf-8"))

    def _append(self, row: dict) -> None:
        """Under the caller's lock. Chains record_hash off the external head, appends, then advances
        the head file — so a later JSONL edit/truncation breaks the replay."""
        head = self._read_head()
        prev = head["record_hash"]
        rec = {"seq": head["n"] + 1, "at": datetime.now().isoformat(timespec="seconds"),
               "prev_record_hash": prev, **row}
        rec["record_hash"] = _h(prev + _canon({k: v for k, v in rec.items() if k != "record_hash"}))
        p = self.rp.assert_write(self.ledger_path)
        with self.rp.broker().open_for_write(p, "a") as fh:
            fh.write(_canon(rec) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        self.rp.write_json(self.head_path, {"n": rec["seq"], "record_hash": rec["record_hash"]})

    def _load(self) -> list:
        """Replay + verify the chain from genesis; the recomputed tail MUST equal the head file. Any
        torn line / broken link / head mismatch = fail closed."""
        if not self.ledger_path.exists():
            return []
        rows, prev = [], self._genesis()
        for i, line in enumerate(self.ledger_path.read_text(encoding="utf-8").splitlines()):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                raise LedgerError(f"ledger torn/malformed at line {i + 1}")
            body = {k: v for k, v in rec.items() if k != "record_hash"}
            if rec.get("prev_record_hash") != prev or rec.get("record_hash") != _h(prev + _canon(body)):
                raise LedgerError(f"ledger hash-chain break at line {i + 1} (tamper/truncation)")
            prev = rec["record_hash"]
            rows.append(rec)
        if self._read_head().get("record_hash") != prev:
            raise LedgerError("ledger head does not match the chain tail (truncated/rewound)")
        return rows

    # ── plan ─────────────────────────────────────────────────────────────────────────────────────
    def _freeze_plan_unvalidated(self, plan_rows: list) -> str:
        """The RAW freeze. Named for what it is (GPT re-review #9): it performs NO contract validation,
        so recovery code must never call it — `raw_recovery_coordinator.freeze_request_plan` is the only
        sanctioned door and is the sole caller. Kept reachable for the ledger's own unit tests, where the
        contract layer is deliberately out of scope."""
        with self.rp._lock():
            # GPT re-review #10 BLOCKER: the frozen plan self-authenticated (its own embedded hash) and
            # the file was written BEFORE the hash-chained plan_frozen event, so a crash between them
            # left an ORPHAN plan.json that _plan still accepted — inside the stated crash threat model.
            # The hash-chained event is now the authority; the guard keys off IT, not the file, and a
            # same-plan resume HEALS a payload the crash lost.
            existing = [r for r in self._load()
                        if r.get("kind") == "lifecycle" and r.get("event") == "plan_frozen"]
            seen = set()
            outs = {}
            for r in plan_rows:
                if not _PLAN_REQUIRED <= set(r):
                    raise LedgerError(f"plan row missing {_PLAN_REQUIRED - set(r)}")
                if r["request_id"] != request_id(r["endpoint"], r["params"], r["partition"]):
                    raise LedgerError(f"request_id mismatch for {r['request_id']}")
                if r["request_id"] in seen:
                    raise LedgerError(f"duplicate request_id {r['request_id']}")
                if r["empty_policy"] not in ("dense_refuse", "sparse_canary"):
                    raise LedgerError(f"bad empty_policy {r['empty_policy']}")
                # GPT re-review #10 MAJOR (reproduced): receipt_output was joined onto staging_data and
                # only checked for uniqueness. `../reports/escaped.parquet` normalizes to <run>/reports/
                # — outside staging_data but inside the run root, so assert_write waved it through. It
                # must be a NORMALIZED RELATIVE path whose resolved destination stays UNDER staging_data.
                _assert_contained_receipt_output(r["receipt_output"], self.rp.staging_data)
                # per-request receipt outputs must be UNIQUE (no shared-output cross-verify)
                if r["receipt_output"] in outs:
                    raise LedgerError(f"two requests share receipt_output {r['receipt_output']}")
                outs[r["receipt_output"]] = r["request_id"]
                seen.add(r["request_id"])
            sha = _h(_canon(plan_rows))
            payload = {"sha256": sha, "coordinator_commit": self.coordinator_commit,
                       "adapter_bundle_hash": self.adapter_bundle_hash, "rows": plan_rows}
            if existing:
                # a plan is already attested for this run: it must be EXACTLY this one, else refuse.
                if len(existing) != 1 or existing[0].get("plan_sha256") != sha:
                    raise LedgerError(f"a plan is already frozen for this run "
                                      f"({len(existing)} plan_frozen event(s)); this one hashes {sha[:12]} "
                                      f"— re-freezing a DIFFERENT plan is refused")
                # same plan — HEAL the payload if the crash lost or corrupted it, then done (no 2nd event)
                if not self.plan_path.exists() or \
                        _h(_canon(json.loads(self.plan_path.read_text(encoding="utf-8"))["rows"])) != sha:
                    self.rp.write_json(self.plan_path, payload)
                return sha
            # FRESH freeze: the hash-chained AUTHORITY is appended BEFORE the payload file, so a crash
            # after it leaves an attested-but-missing plan (healable above), never an un-attested one.
            self._append({"kind": "lifecycle", "event": "plan_frozen", "plan_sha256": sha,
                          "coordinator_commit": self.coordinator_commit,
                          "adapter_bundle_hash": self.adapter_bundle_hash, "request_count": len(plan_rows)})
            self.rp.write_json(self.plan_path, payload)
            return sha

    def _plan(self) -> dict:
        """The frozen plan, ANCHORED to the hash-chained `plan_frozen` event (GPT re-review #10 BLOCKER).
        request_plan.json is only a payload; the tamper-evident chain is the authority. A rewritten
        plan.json (recomputed self-hash) and an orphan plan.json (crash before the event) both refuse."""
        frozen = [r for r in self._load()
                  if r.get("kind") == "lifecycle" and r.get("event") == "plan_frozen"]
        if not frozen:
            raise LedgerError("no plan_frozen event in the ledger — the plan is not attested")
        if len(frozen) != 1:
            raise LedgerError(f"{len(frozen)} plan_frozen events — a run freezes its plan exactly once")
        attested = frozen[0].get("plan_sha256")
        if not self.plan_path.exists():
            raise LedgerError("plan_frozen is attested but request_plan.json is MISSING (orphaned by a "
                              "crash between the event and the file); re-freeze the SAME plan to heal it")
        plan = json.loads(self.plan_path.read_text(encoding="utf-8"))
        recomputed = _h(_canon(plan["rows"]))
        if recomputed != plan["sha256"]:
            raise LedgerError("request plan self-hash mismatch (tampered)")
        if recomputed != attested:
            raise LedgerError(f"request_plan.json ({recomputed[:12]}) != the hash-chained plan_frozen "
                              f"event ({str(attested)[:12]}) — the plan was rewritten after freezing")
        return {r["request_id"]: r for r in plan["rows"]}

    def event(self, name: str, **kw) -> None:
        with self.rp._lock():
            self._load()
            self._append({"kind": "lifecycle", "event": name, **kw})

    # ── page receipts (coordinator-owned) ────────────────────────────────────────────────────────
    @staticmethod
    def add_row_payload_digest(df):
        """EXECUTABLE producer for the `row_payload_digest` derivation (GPT re-review #6 F3: it was a
        PROSE declaration with no producer — the matrix keyed the event families on a column nothing
        computed, so any adapter built against it would fail 'output missing natural-key columns').

        GPT re-review #7 M1 (reproduced): the first implementation used `iterrows()` + `repr`, which
        builds a Series PER ROW and coerces every value to one common dtype — so int64(1) beside a
        float column became float64(1.0) and collided with a genuinely different row. It was not
        lossless, which is the entire point of the key.

        Canonical TYPED encoding instead, column-wise (never iterrows):
          * vendor columns only (coordinator-derived columns excluded), in sorted name order;
          * each field contributes length-delimited (name, dtype-tag, value-bytes) — the dtype tag
            alone separates int64 from float64;
          * floats use exact IEEE-754 big-endian bytes (so -0.0 != 0.0), with NaN/±inf as fixed tokens
            (never a NaN payload); ints are exact decimal; strings are NFC-normalized UTF-8; bytes,
            bools, Decimals and timestamps have their own tags; an UNRECOGNIZED type REFUSES
            (there is no repr fallback — a repr-dependent key is the opposite of lossless).
        MUST be computed on the RAW vendor page BEFORE any non-injective normalization."""
        cols = sorted(c for c in df.columns if c not in _COORDINATOR_DERIVED_COLS)
        if not cols:
            raise LedgerError("row_payload_digest: no vendor columns to digest")
        out = df.reset_index(drop=True).copy()
        encoded = [(c.encode("utf-8"), str(out[c].dtype).encode("utf-8"),
                    [_canon_scalar(v) for v in out[c].tolist()]) for c in cols]
        digs = []
        for i in range(len(out)):
            h = hashlib.sha256()
            for name, dtag, vals in encoded:
                for part in (name, dtag, vals[i]):
                    h.update(len(part).to_bytes(4, "big"))  # length-delimited: no field-boundary aliasing
                    h.update(part)
            digs.append(h.hexdigest())
        out["row_payload_digest"] = digs
        return out

    def fetch_page(self, rid: str, page: int, call, *, terminal_claim: str = ""):
        """THE coordinator-owned fetch-attempt boundary (GPT re-review #7 B1).

        The old `record_page(df)` took data the adapter CLAIMED to have fetched and minted an
        `attempt_uid` at RECORD time — so `attempt_uid`/`recorded_at` proved a LEDGER WRITE happened,
        not an API CALL. One empty response recorded twice therefore certified as two independent
        attempts (reproduced), and `confirm_empty` counted those. My own test did exactly that.

        Now the ledger owns the call:
          1. an OPEN lease row is fsync'd BEFORE the call — a call that crashes still leaves evidence;
          2. the ledger INVOKES `call()` itself (a zero-arg callable performing EXACTLY ONE vendor API
             call and returning its DataFrame) — an adapter never hands us data it says it fetched;
          3. the response is recorded bound to that lease and the lease is CLOSED exactly once.
        Two empty confirmations therefore require two COMPLETED CALL LEASES with disjoint time windows
        — two calls the ledger actually made — never two record calls.

        The lock is NOT held across the call (that would serialize the network and fight the §6.1
        throttle); lease-open and lease-close each take it."""
        import io
        import uuid as _uuid
        # ---- -1. the LEGACY door is battery-only (GPT impl-review B2; re-review #2) --------------
        # This method takes a caller-supplied callable + terminal and predates the claimed-fetch path;
        # it checks NO run mode and NO §13 authorization. Two independent refusals, both BEFORE any
        # lease opens and BEFORE the callable could run:
        #   (a) DEFAULT-OFF: the door is disabled unless the battery flips the per-instance test
        #       capability — re-review #2 showed "refuse after mode declaration" alone was bypassable
        #       by fetching FIRST and declaring live_authorized after;
        #   (b) a DECLARED run mode refuses regardless of the flag — a battery capability that leaks
        #       into a production run still cannot fetch.
        if not getattr(self, "_legacy_fetch_enabled", False):
            raise LedgerError("legacy fetch_page is DISABLED — a battery-only door (set "
                              "_legacy_fetch_enabled on the test instance); production fetching goes "
                              "through claim_next_fetch/fetch_claimed_page")
        with self.rp._lock():
            if any(r.get("kind") == "lifecycle" and r.get("event") == "run_mode"
                   for r in self._load()):
                raise LedgerError("legacy fetch_page is REFUSED once a run mode is declared — "
                                  "production fetching goes through claim_next_fetch/"
                                  "fetch_claimed_page (GPT impl-review B2)")
        # ---- 0. RE-VERIFY the contract binding (GPT re-review #9 BLOCKER-1) ---------------------
        # The contract hash was checked once, at freeze. Editing the signed contract afterwards left
        # fetching enabled — a frozen hash proves what WAS signed, never what is signed NOW. Re-verify
        # against the live contract before every call; no loader = no binding to check = fail closed.
        with self.rp._lock():
            plan = self._plan()
            if rid not in plan:
                raise LedgerError(f"request {rid} not in the frozen plan")
        self._revalidate_contract(plan[rid])
        # ---- 1. OPEN the lease (durable, before the call) --------------------------------------
        with self.rp._lock():
            rows = self._load()
            plan = self._plan()
            if self._state_of(rows, rid) in _TERMINAL:
                raise LedgerError(f"request {rid} already terminal")
            lease_id = _uuid.uuid4().hex
            opened_at = datetime.now(timezone.utc).isoformat()
            self._append({"kind": "lease_open", "request_id": rid, "page": int(page),
                          "lease_id": lease_id, "opened_at": opened_at})
        # ---- 2. the LEDGER makes the call (outside the lock) ------------------------------------
        try:
            df = call()
        except Exception as exc:
            with self.rp._lock():
                self._append({"kind": "lease_failed", "request_id": rid, "page": int(page),
                              "lease_id": lease_id, "error": repr(exc)[:300]})
            raise
        if df is None or not hasattr(df, "columns"):
            with self.rp._lock():
                self._append({"kind": "lease_failed", "request_id": rid, "page": int(page),
                              "lease_id": lease_id, "error": "call returned no DataFrame"})
            raise LedgerError(f"{rid} page {page}: the fetch callable returned {type(df).__name__}, "
                              f"not a DataFrame")
        # ---- 3. record bound to the lease + CLOSE it exactly once --------------------------------
        return self._close_lease_record(rid, page, lease_id, opened_at, df, terminal_claim)

    def _close_lease_record(self, rid: str, page: int, lease_id: str, opened_at: str, df,
                            terminal_claim: str, *, vendor_page_sha: str = "") -> int:
        """The shared record core: bind the response to its OPEN lease, persist the receipt, close the
        lease exactly once. Called by fetch_page (legacy/below-contract path, caller-supplied terminal)
        and fetch_claimed_page (production path — the terminal is LEDGER-DERIVED before this call)."""
        import io
        with self.rp._lock():
            rows = self._load()
            # GPT impl-review B1 (re-check at CLOSE): a response may only close the lease that fetched
            # it — a matching OPEN lease row must exist for this request+page.
            if not any(r.get("kind") == "lease_open" and r.get("lease_id") == lease_id
                       and r.get("request_id") == rid and int(r.get("page", -1)) == int(page)
                       for r in rows):
                raise LedgerError(f"{rid} page {page}: no matching OPEN lease {lease_id[:8]} — a "
                                  f"response may only close the lease that fetched it")
            if any(r.get("kind") == "attempt" and r.get("lease_id") == lease_id for r in rows):
                raise LedgerError(f"lease {lease_id} already consumed — a lease closes exactly once")
            # GPT impl re-review #2 (second guard): an ABANDONED or already-FAILED lease can never
            # close — a zombie worker returning after an operator crash-resume cannot record a second
            # attempt for a page another lease has since re-fetched.
            if any(r.get("kind") in ("lease_abandoned", "lease_failed")
                   and r.get("lease_id") == lease_id for r in rows):
                raise LedgerError(f"{rid} page {page}: lease {lease_id[:8]} was ABANDONED/FAILED — a "
                                  f"stale worker's response is refused at close")
            closed_at = datetime.now(timezone.utc).isoformat()
            body = df.reset_index(drop=True).copy()
            # the coordinator OWNS first-seen: an adapter may never supply or pre-stamp it
            if "raw_fetch_ts" in body.columns:
                raise LedgerError(f"{rid} page {page}: the response carries a pre-supplied raw_fetch_ts "
                                  f"— first-seen is coordinator-owned and may never come from the adapter")
            body["raw_fetch_ts"] = opened_at   # stamped from the LEASE, not from a caller argument
            page_sha, n = _df_sha256(body)
            receipt = self.rp.assert_write(
                self.receipts_dir / rid / f"page_{int(page)}__{lease_id}.parquet")
            self.rp.broker().mkdirs(receipt.parent)
            buf = io.BytesIO()
            body.to_parquet(buf, index=False)
            payload = buf.getvalue()
            with self.rp.broker().open_for_write(receipt, "wb") as fh:  # broker-mediated, no raw path write
                fh.write(payload)
            rec = {"kind": "attempt", "request_id": rid, "endpoint": self._plan()[rid]["endpoint"],
                   "params": self._plan()[rid]["params"], "page": int(page), "row_count": n,
                   "lease_id": lease_id, "attempt_uid": lease_id,
                   "opened_at": opened_at, "closed_at": closed_at, "recorded_at": closed_at,
                   "page_sha256": page_sha,
                   "receipt_bytes_sha256": hashlib.sha256(payload).hexdigest(),
                   "receipt": str(receipt.relative_to(self.rp.root)).replace("\\", "/"),
                   "terminal_claim": terminal_claim}
            if vendor_page_sha:
                # the UNTOUCHED vendor payload hash, computed BEFORE prepare_raw_page and BEFORE the
                # raw_fetch_ts stamp (design v4 F8): receipts carry both identities.
                rec["vendor_page_sha256"] = vendor_page_sha
            self._append(rec)
        return n

    # ── run mode + §13 authorization (design v4 F2) ──────────────────────────────────────────────
    def declare_run_mode(self, mode: str) -> None:
        """Fix the IMMUTABLE run mode. Idempotent for the same mode; a differing re-declaration
        refuses — a run can never drift between synthetic and live."""
        if mode not in _RUN_MODES:
            raise LedgerError(f"unknown run mode {mode!r}; known: {sorted(_RUN_MODES)}")
        with self.rp._lock():
            rows = self._load()
            ex = [r for r in rows if r.get("kind") == "lifecycle" and r.get("event") == "run_mode"]
            if ex:
                if len(ex) != 1 or ex[0].get("mode") != mode:
                    raise LedgerError(f"run mode already declared as {ex[0].get('mode')!r} — it is "
                                      f"immutable; a {mode!r} re-declaration is refused")
                return
            self._append({"kind": "lifecycle", "event": "run_mode", "mode": mode})

    def run_mode(self, rows=None) -> str:
        rows = self._load() if rows is None else rows
        ex = [r for r in rows if r.get("kind") == "lifecycle" and r.get("event") == "run_mode"]
        if not ex:
            raise LedgerError("run mode undeclared — declare_run_mode() must run before any claim; an "
                              "undeclared mode is neither synthetic nor live and may do NOTHING")
        if len(ex) != 1 or ex[0].get("mode") not in _RUN_MODES:
            raise LedgerError(f"run mode events malformed ({len(ex)} events)")
        return ex[0]["mode"]

    def record_fetch_authorization(self, *, actor: str, expires_at: str, endpoint_scope) -> str:
        """Write the hash-chained `fetch_authorized` event — the SOLE §13 authority for a live wire
        call (design v4 F2). Called ONLY by the explicit user-triggered authorize-fetch CLI; the fetch
        command has no path that mints this. Binds the FROZEN plan + the adapter bundle: authorizing an
        unfrozen run is meaningless and refuses."""
        import getpass
        import uuid as _uuid
        if not str(actor).strip():
            raise LedgerError("fetch authorization requires a named human actor")
        try:
            exp = datetime.fromisoformat(str(expires_at))
            if exp.tzinfo is None:
                raise ValueError("naive")
        except ValueError:
            raise LedgerError("expires_at must be a timezone-AWARE ISO timestamp")
        scope = sorted({str(e) for e in (endpoint_scope or [])})
        if not scope:
            raise LedgerError("fetch authorization requires an explicit endpoint_scope")
        with self.rp._lock():
            rows = self._load()
            frozen = [r for r in rows if r.get("kind") == "lifecycle" and r.get("event") == "plan_frozen"]
            if len(frozen) != 1:
                raise LedgerError("authorize-fetch requires exactly one FROZEN plan to bind to")
            auth_id = _uuid.uuid4().hex
            # EVIDENCE, not the boundary: record BOTH the username and the actual Windows SID
            # (GPT impl-review minor: a username alone is not an OS identity).
            try:
                os_username = getpass.getuser()
            except Exception:
                os_username = "(unavailable)"
            os_sid = "(unavailable)"
            try:
                import subprocess
                out = subprocess.run(["whoami", "/user", "/fo", "csv"],
                                     capture_output=True, text=True, timeout=5)
                line = out.stdout.strip().splitlines()[-1]
                os_sid = [p.strip('"') for p in line.split('","')][-1]
            except Exception:
                pass
            self._append({"kind": "lifecycle", "event": "fetch_authorized", "auth_id": auth_id,
                          "actor": str(actor), "os_username": os_username, "os_sid": os_sid,
                          "issued_at": datetime.now(timezone.utc).isoformat(),
                          "expires_at": str(expires_at),
                          "plan_sha256": frozen[0].get("plan_sha256"),
                          "bundle_sha256": self.adapter_bundle_hash,
                          "endpoint_scope": scope})
            return auth_id

    def _assert_live_authorized(self, rows, endpoint: str) -> None:
        """Validate the `fetch_authorized` EVENT (never a passed object) for THIS endpoint, THIS frozen
        plan, THIS adapter bundle, unexpired. Checked pre-lease at claim AND again in-lease before the
        wire call."""
        evs = [r for r in rows if r.get("kind") == "lifecycle" and r.get("event") == "fetch_authorized"]
        if not evs:
            raise LedgerError("live run without a fetch_authorized event — §13 authorization missing "
                              "(run authorize-fetch; the fetch path cannot mint it)")
        ev = evs[-1]
        try:
            exp = datetime.fromisoformat(str(ev.get("expires_at")))
        except ValueError:
            raise LedgerError("fetch_authorized carries an unparseable expires_at")
        if exp <= datetime.now(timezone.utc):
            raise LedgerError(f"fetch authorization {ev.get('auth_id', '?')[:8]} EXPIRED at "
                              f"{ev.get('expires_at')}")
        scope = set(ev.get("endpoint_scope") or [])
        if endpoint not in scope and "*" not in scope:
            raise LedgerError(f"fetch authorization does not cover endpoint {endpoint!r} "
                              f"(scope: {sorted(scope)})")
        frozen = [r for r in rows if r.get("kind") == "lifecycle" and r.get("event") == "plan_frozen"]
        if len(frozen) != 1 or ev.get("plan_sha256") != frozen[0].get("plan_sha256"):
            raise LedgerError("fetch authorization binds a DIFFERENT plan than the one frozen here")
        if ev.get("bundle_sha256") != self.adapter_bundle_hash:
            raise LedgerError("fetch authorization binds a DIFFERENT adapter bundle — the adapter code "
                              "changed since authorization; re-authorize deliberately")

    def assert_run_promotable(self) -> None:
        """Promotion firewall (design v4 F2): only a live_authorized run may ever promote."""
        mode = self.run_mode()
        if mode != "live_authorized":
            raise LedgerError(f"run mode {mode!r} is NOT promotable — synthetic/mixed runs never reach "
                              f"the live store")

    # ── the claimed-fetch path (design v4 F1/F3/F4/F5/F8) ────────────────────────────────────────
    def claim_next_fetch(self, rid: str, executor_mode: str) -> "Claim":
        """THE atomic mutation authority (design v4 F3): derives the next action from the ledger AND
        reserves/opens the lease in the SAME lock acquisition — a concurrent caller sees IN_FLIGHT,
        never a duplicate cursor. Run-mode and (live) §13 authorization are checked BEFORE any lease
        opens, so a mismatched executor can never leave even an open-lease trace."""
        import uuid as _uuid
        with self.rp._lock():
            rows = self._load()
            plan = self._plan()
            if rid not in plan:
                raise LedgerError(f"request {rid} not in the frozen plan")
            row = plan[rid]
            mode = self.run_mode(rows)
            if executor_mode != mode:
                raise LedgerError(f"executor mode {executor_mode!r} != run mode {mode!r} — refused "
                                  f"BEFORE opening any lease (mixed mode is unreachable)")
            if mode == "live_authorized":
                self._assert_live_authorized(rows, row["endpoint"])
            if self._state_of(rows, rid) in _TERMINAL:
                return Claim("SKIP_TERMINAL")
            closed_ids = {r.get("lease_id") for r in rows
                          if r.get("kind") in ("attempt", "lease_failed", "lease_abandoned")
                          and r.get("request_id") == rid}
            open_ls = [r for r in rows if r.get("kind") == "lease_open" and r.get("request_id") == rid
                       and r.get("lease_id") not in closed_ids]
            if open_ls:
                return Claim("IN_FLIGHT")
            pages = self._latest_pages(rows, rid)
            nums = sorted(pages)
            if nums and nums != list(range(1, len(nums) + 1)):
                raise LedgerError(f"{rid}: recorded pages not contiguous 1..N: {nums} — corrupt state")
            failed_pages = {r.get("page") for r in rows
                            if r.get("kind") in ("lease_failed", "lease_abandoned")
                            and r.get("request_id") == rid}

            def _open(kind, page, offset):
                lease_id = _uuid.uuid4().hex
                opened_at = datetime.now(timezone.utc).isoformat()
                # the offset is PERSISTED in the lease (GPT impl-review B1): fetch_claimed_page
                # validates the presented Claim against this durable row, so a forged/altered claim
                # (any offset, any lease id) can never reach the executor.
                self._append({"kind": "lease_open", "request_id": rid, "page": int(page),
                              "offset": int(offset), "lease_id": lease_id, "opened_at": opened_at})
                return Claim(kind, page=int(page), offset=int(offset),
                             lease_id=lease_id, opened_at=opened_at)

            limit = int(row["page_limit"]) if row["page_limit"] else 0
            if row["pagination_mode"] == "single_page":
                if not pages:
                    return _open("RETRY_PAGE" if 1 in failed_pages else "FETCH", 1, 0)
                if pages[1]["row_count"] > 0:
                    return Claim("VERIFY")
                if row["empty_policy"] == "dense_refuse":
                    return Claim("VERIFY")          # verify_request refuses a dense-empty LOUDLY
                return self._empty_lifecycle(rows, plan, rid, row, _open)
            # offset_paged
            if not pages:
                return _open("RETRY_PAGE" if 1 in failed_pages else "FETCH", 1, 0)
            total = sum(pages[p]["row_count"] for p in nums)
            last_n = pages[nums[-1]]["row_count"]
            if limit and last_n > limit:
                raise LedgerError(f"{rid}: recorded page {nums[-1]} has {last_n} rows > the signed "
                                  f"page_limit {limit} — the cap fact is wrong; refuse")
            if limit and last_n == limit:
                nxt = nums[-1] + 1
                return _open("RETRY_PAGE" if nxt in failed_pages else "FETCH", nxt, total)
            # terminal reached (last page short or empty)
            if total > 0:
                return Claim("VERIFY")
            if row["empty_policy"] == "dense_refuse":
                return Claim("VERIFY")              # dense-empty refusal surfaces at verify
            return self._empty_lifecycle(rows, plan, rid, row, _open)

    def _empty_lifecycle(self, rows, plan, rid, row, _open) -> "Claim":
        """Sparse-empty confirmation lifecycle (design v4 F4): a second INDEPENDENT empty lease, then a
        deferred verdict until a same-endpoint nonempty canary verifies. VERIFY is never returned for an
        entirely-empty sparse request."""
        empt = [a for a in self._closed_leases(rows, rid) if a["row_count"] == 0]
        if len({a["lease_id"] for a in empt}) < 2:
            return _open("RETRY_EMPTY_CONFIRM", 1, 0)
        # deterministic canary: the LOWEST verified-nonempty same-endpoint request id
        cands = sorted(r2 for r2, rr in plan.items()
                       if rr["endpoint"] == row["endpoint"] and r2 != rid
                       and self._state_of(rows, r2) == "verified"
                       and any(a["row_count"] > 0 for a in self._attempts(rows, r2)))
        if cands:
            return Claim("CONFIRM_EMPTY", canary_request_id=cands[0])
        return Claim("WAIT_FOR_CANARY")

    def abandon_orphan_leases(self, rid: str, *, reason: str) -> int:
        """The EXPLICIT crash-resume transition (design v4 §3; GPT impl re-review #2): convert
        genuinely orphaned OPEN leases (a crash between lease-open and close) to `lease_abandoned` so
        claim_next_fetch can re-issue the cursor as RETRY_PAGE.

        The reason is AUDIT evidence; the MUTUAL EXCLUSION is the run-execution lock: a live worker
        holds it for its whole dispatch->call->close span, so abandoning while any worker is mid-call
        REFUSES at the lock (re-review #2 reproduced the race: operator abandoned mid-request, a retry
        succeeded, then the zombie ALSO closed the old lease -> two page-1 attempts). Second guard:
        _close_lease_record refuses an abandoned lease outright, so even a worker that crashed between
        the guard and its close can never record a stale attempt. run_family never calls this."""
        if not str(reason).strip():
            raise LedgerError("abandoning a lease requires an explicit auditable reason")
        with self.execution_guard(timeout=self._abandon_lock_timeout), self.rp._lock():
            rows = self._load()
            closed = {r.get("lease_id") for r in rows
                      if r.get("kind") in ("attempt", "lease_failed", "lease_abandoned")}
            orphans = [r for r in rows if r.get("kind") == "lease_open"
                       and r.get("request_id") == rid and r.get("lease_id") not in closed]
            for o in orphans:
                self._append({"kind": "lease_abandoned", "request_id": rid, "page": o.get("page"),
                              "lease_id": o["lease_id"], "reason": str(reason)[:200]})
            return len(orphans)

    def fetch_claimed_page(self, rid: str, claim: "Claim", executor) -> "PageResult":
        """The production fetch door (design v4; hardened per GPT impl re-review #2). The ledger BUILDS
        the page-call spec ITSELF from the frozen plan row + the atomically-claimed cursor, invokes the
        executor's ONE wire call, and derives the terminal. Concurrency contract:
          * the whole dispatch->call->close span holds the CROSS-PROCESS run-execution lock (a
            concurrent presenter blocks/refuses at the lock; abandon cannot interleave);
          * the claim is CONSUMED before the vendor call: a `lease_dispatch_started` marker is written
            in the same critical section as the validation, so the SAME valid Claim presented again is
            refused BEFORE any second wire call (re-review #2: replay executed twice);
          * a one-shot dispatch token is minted for the executor — LiveExecutor refuses a call the
            ledger did not dispatch;
          * ANY post-claim failure — LedgerError or not (e.g. Arrow serialization inside the close) —
            closes the lease as lease_failed (never IN_FLIGHT forever)."""
        if claim.kind not in ("FETCH", "RETRY_PAGE", "RETRY_EMPTY_CONFIRM"):
            raise LedgerError(f"fetch_claimed_page needs a fetch-bearing claim, got {claim.kind}")
        if not claim.lease_id:
            raise LedgerError("claim carries no lease — it was not produced by claim_next_fetch")
        import uuid as _uuid
        with self.execution_guard():                 # covers dispatch -> wire call -> close
            with self.rp._lock():
                rows = self._load()
                plan = self._plan()
                if rid not in plan:
                    raise LedgerError(f"request {rid} not in the frozen plan")
                row = plan[rid]
                # ---- BIND the presented Claim to its DURABLE OPEN LEASE (B1) --------------------
                # A Claim is a caller-held token; only the ledger's own lease_open row is the fact.
                # A forged presentation does NOT close the real lease.
                lo = [r for r in rows if r.get("kind") == "lease_open"
                      and r.get("lease_id") == claim.lease_id and r.get("request_id") == rid]
                if not lo:
                    raise LedgerError(f"{rid}: claim's lease {claim.lease_id[:8]} does not exist in "
                                      f"the ledger — forged/stale claim refused")
                lease = lo[-1]
                if (int(lease.get("page", -1)) != int(claim.page)
                        or int(lease.get("offset", -1)) != int(claim.offset)
                        or lease.get("opened_at") != claim.opened_at):
                    raise LedgerError(f"{rid}: claim (page {claim.page}, offset {claim.offset}) does "
                                      f"not match its durable lease (page {lease.get('page')}, offset "
                                      f"{lease.get('offset')}) — altered claim refused")
                if any(r.get("kind") in ("attempt", "lease_failed", "lease_abandoned")
                       and r.get("lease_id") == claim.lease_id for r in rows):
                    raise LedgerError(f"{rid}: claim's lease {claim.lease_id[:8]} is already consumed")
                # ---- CONSUME the claim (re-review #2): one dispatch per lease, ever -------------
                if any(r.get("kind") == "lease_dispatch_started"
                       and r.get("lease_id") == claim.lease_id for r in rows):
                    raise LedgerError(f"{rid}: lease {claim.lease_id[:8]} already DISPATCHED — a "
                                      f"claim is one-shot; a replay never reaches the vendor")
                # IN-LEASE re-validation (design v4 F2): run-mode + live authorization at the moment
                # of the wire call, not only at claim time.
                mode = self.run_mode(rows)
                ex_mode = getattr(executor, "mode", None)
                if ex_mode != mode:
                    self._append({"kind": "lease_failed", "request_id": rid, "page": int(claim.page),
                                  "lease_id": claim.lease_id,
                                  "error": f"executor mode {ex_mode!r} != run mode {mode!r}"})
                    raise LedgerError(f"executor mode {ex_mode!r} != run mode {mode!r} at execution")
                if mode == "live_authorized":
                    try:
                        self._assert_live_authorized(rows, row["endpoint"])
                    except LedgerError as exc:
                        self._append({"kind": "lease_failed", "request_id": rid,
                                      "page": int(claim.page), "lease_id": claim.lease_id,
                                      "error": str(exc)[:300]})
                        raise
                self._append({"kind": "lease_dispatch_started", "request_id": rid,
                              "page": int(claim.page), "lease_id": claim.lease_id})
            dispatch_token = _uuid.uuid4().hex
            limit0 = int(row["page_limit"]) if row["page_limit"] else 0
            frozen_spec = {"endpoint": row["endpoint"], "base_params": dict(row["params"]),
                           "limit": limit0, "offset": int(claim.offset), "page": int(claim.page),
                           "recipe_id": row["recipe_id"], "pagination_mode": row["pagination_mode"]}
            # the token is bound to the FROZEN spec (P0): the executor may not alter the request
            self._dispatch_tokens[dispatch_token] = self._canon_dispatch_spec(frozen_spec)
            try:
                return self._execute_dispatched(rid, claim, executor, row, dispatch_token,
                                                frozen_spec)
            except BaseException as exc:
                # TOTAL safety net (re-review #2): any failure after dispatch — refusal, executor
                # error, serialization/broker error inside the close — must leave the lease CLOSED.
                # Idempotent: skip when a site (or the close itself) already consumed the lease.
                with self.rp._lock():
                    rows2 = self._load()
                    if not any(r.get("kind") in ("attempt", "lease_failed", "lease_abandoned")
                               and r.get("lease_id") == claim.lease_id for r in rows2):
                        self._append({"kind": "lease_failed", "request_id": rid,
                                      "page": int(claim.page), "lease_id": claim.lease_id,
                                      "error": f"{type(exc).__name__}: {exc}"[:300]})
                raise
            finally:
                self._dispatch_tokens.pop(dispatch_token, None)

    def _execute_dispatched(self, rid: str, claim: "Claim", executor, row: dict,
                            dispatch_token: str, frozen_spec: dict) -> "PageResult":
        """The post-dispatch body (called under the execution guard + total safety net)."""
        self._revalidate_contract(row)               # live contract re-bind, every page
        limit = frozen_spec["limit"]
        spec = dict(frozen_spec, dispatch_token=dispatch_token)
        # ---- the ONE wire call (the §6.1 throttle lives in the proxy) ---------------------------
        df = executor.run_page(spec)
        if df is None or not hasattr(df, "columns"):
            raise LedgerError(f"{rid} page {claim.page}: executor returned "
                              f"{type(df).__name__}, not a DataFrame")
        n = int(len(df))
        if row["pagination_mode"] == "offset_paged" and limit and n > limit:
            raise LedgerError(f"{rid} page {claim.page}: {n} rows EXCEEDS the signed page_limit "
                              f"{limit} — the signed cap fact is wrong; refusing the page")
        vendor_sha, _ = _df_sha256(df)               # BEFORE prep and BEFORE the raw_fetch_ts stamp
        prepared = self._prepare_raw_page(row, df)
        self._assert_response_scope(row, prepared)
        if row["pagination_mode"] == "single_page":
            terminal = "single_page_contract"
        elif n == 0:
            terminal = "empty_terminal"
        elif limit and n < limit:
            terminal = "last_partial"
        else:
            terminal = ""                             # full page: nonterminal, fetch the next offset
        self._close_lease_record(rid, claim.page, claim.lease_id, claim.opened_at, prepared,
                                 terminal, vendor_page_sha=vendor_sha)
        return PageResult(row_count=n, terminal_kind=terminal, next_offset=int(claim.offset) + n)

    def _prepare_raw_page(self, row: dict, df):
        """Endpoint-scoped page preparation INSIDE the ledger boundary (design v4 F8): may only ADD the
        coordinator-derived columns declared for this endpoint; never drops/mutates/reorders vendor
        rows. Fail-closed: a natural key demanding a derived column with NO registered producer refuses
        (silently omitting it would fail verification later with a misleading error)."""
        ep = row["endpoint"]
        fn = _PREPARE_REGISTRY.get(ep)
        derived_nk = [c for c in (row.get("natural_key") or [])
                      if c in _COORDINATOR_DERIVED_COLS and c != "raw_fetch_ts"]
        if fn is None:
            if derived_nk:
                raise LedgerError(f"{ep}: natural key needs derived column(s) {derived_nk} but no "
                                  f"prepare_raw_page producer is registered — refusing (fail closed)")
            return df
        if not len(df):
            return df                                # nothing to derive on an empty page
        before_cols = set(df.columns)
        before_n = len(df)
        out = fn(df)
        if len(out) != before_n:
            raise LedgerError(f"{ep}: prepare_raw_page changed the row count "
                              f"({before_n} -> {len(out)}) — preparation may only ADD columns")
        removed = before_cols - set(out.columns)
        if removed:
            raise LedgerError(f"{ep}: prepare_raw_page REMOVED columns {sorted(removed)}")
        added = set(out.columns) - before_cols
        allowed = self._derived_allowed(ep)
        if not added <= allowed:
            raise LedgerError(f"{ep}: prepare_raw_page added undeclared column(s) "
                              f"{sorted(added - allowed)} — only {sorted(allowed)} are declared")
        return out

    def _derived_allowed(self, endpoint: str) -> set:
        """The endpoint's declared derived columns (coordinator authority; a private per-instance seam
        for the below-contract battery, like _revalidate_contract)."""
        import raw_recovery_coordinator as _rrc  # local: avoid an import cycle
        return set(_rrc.derived_fields_for(endpoint))

    def _assert_response_scope(self, row: dict, df) -> None:
        """Enforce the FROZEN response scope (design v4 F5): every returned row must belong to the
        request that asked for it — a wrong-date/wrong-stock page (vendor or cache error, or a wrong
        closure) REFUSES before receipt certification. Typed date parsing for ranges."""
        import pandas as pd
        scope = row.get("response_scope") or {}
        checks = scope.get("checks") or []
        if df is None or not len(df) or not checks:
            return                                   # scope constrains RETURNED rows; empty is fine
        for chk in checks:
            col, cmode, val = chk[0], chk[1], chk[2]
            if col not in df.columns:
                raise LedgerError(f"{row['request_id']}: response lacks scope column {col!r}")
            s = df[col].astype(str)
            if cmode == "eq":
                bad = int((s != str(val)).sum())
                if bad:
                    raise LedgerError(f"{row['request_id']}: {bad} rows outside the requested scope "
                                      f"({col} != {val!r}) — the response does not belong to this request")
            elif cmode == "date_in_range":
                lo, hi = str(val[0]), str(val[1])
                dv = pd.to_datetime(s, format="%Y%m%d", errors="coerce")
                lo_d = pd.to_datetime(lo, format="%Y%m%d")
                hi_d = pd.to_datetime(hi, format="%Y%m%d")
                bad = int((dv.isna() | (dv < lo_d) | (dv > hi_d)).sum())
                if bad:
                    raise LedgerError(f"{row['request_id']}: {bad} rows outside the requested "
                                      f"{col} range [{lo}, {hi}] (or unparseable as dates)")
            else:
                raise LedgerError(f"{row['request_id']}: unknown scope mode {cmode!r} — fail closed")

    def _assert_response_fields(self, endpoint: str, columns) -> None:
        """FETCH/verify-time check that the response carries the contract's signed required_fields
        (GPT re-review #10 BLOCKER). Delegates to the coordinator (reads the LIVE contract internally);
        a private per-instance seam for tests below the contract layer."""
        import raw_recovery_coordinator as _rrc  # local: avoid an import cycle
        try:
            _rrc.assert_response_has_required_fields(endpoint, columns)
        except RuntimeError as exc:
            raise LedgerError(str(exc))

    def _revalidate_contract(self, row: dict) -> None:
        """FETCH-time contract re-binding (GPT re-review #10 BLOCKER). Delegates to the coordinator,
        which reads the LIVE contracts INTERNALLY and re-runs FULL validation (an edited doc refuses).
        There is NO injectable loader state on the ledger — production cannot be redirected by swapping
        an attribute. Tests replace THIS method (a private per-instance seam), never a public attribute
        that production also reads."""
        import raw_recovery_coordinator as _rrc  # local: avoid an import cycle
        try:
            _rrc.revalidate_contract_for_fetch(row)
        except RuntimeError as exc:
            raise LedgerError(str(exc))

    def _closed_leases(self, rows, rid):
        """Attempts backed by a lease the ledger OPENED before the call and CLOSED after it — i.e.
        calls the ledger actually made. This, not a count of record calls, is what proves a re-attempt."""
        opened = {r["lease_id"]: r for r in rows
                  if r.get("kind") == "lease_open" and r.get("request_id") == rid}
        return [a for a in self._attempts(rows, rid)
                if a.get("lease_id") in opened and a.get("closed_at")]

    def _attempts(self, rows, rid):
        return [r for r in rows if r.get("kind") == "attempt" and r.get("request_id") == rid]

    def _latest_pages(self, rows, rid) -> dict:
        """page -> latest attempt (retry supersession)."""
        out = {}
        for a in self._attempts(rows, rid):
            out[a["page"]] = a  # ledger is ordered, so last wins
        return out

    def _state_of(self, rows, rid):
        st = "planned" if rid in self._plan() else None
        for r in rows:
            if r.get("request_id") != rid:
                continue
            st = r["state"] if r["kind"] == "verdict" else "fetched"
        return st

    # ── verification ─────────────────────────────────────────────────────────────────────────────
    def verify_request(self, rid: str) -> dict:
        """Prove contiguous coverage + terminal + key integrity + output binding; write the per-request
        receipt output; return the evidence. Raises LedgerError on any gap."""
        import pandas as pd
        with self.rp._lock():
            rows = self._load()
            plan = self._plan()
            if rid not in plan:
                raise LedgerError(f"request {rid} not in the frozen plan")
            row = plan[rid]
            pages = self._latest_pages(rows, rid)
            if not pages:
                raise LedgerError(f"{rid}: no page receipts")
            nums = sorted(pages)
            if nums != list(range(1, len(nums) + 1)):
                raise LedgerError(f"{rid}: pages not contiguous 1..N: {nums}")
            limit = int(row["page_limit"]) if row["page_limit"] else 0
            mode = row["pagination_mode"]
            if mode not in _PAGINATION_MODES:
                raise LedgerError(f"{rid}: bad pagination_mode {mode!r}")
            # every page except the last must be FULL (== limit) when a limit applies; the last proves termination
            if limit:
                for p in nums[:-1]:
                    if pages[p]["row_count"] != limit:
                        raise LedgerError(f"{rid}: short page {p} before the end (gap/truncation)")
            _assert_terminal_proof(rid, row, pages, nums)
            # --- RECEIPT INTEGRITY: re-read each receipt and RE-COMPUTE its hash/rowcount ----------
            # GPT re-review #5 F2: verification used to trust the recorded hash and just read the file,
            # so a receipt REPLACED after recording still verified and its substituted rows landed in
            # the staged output. The bytes on disk must re-derive the hash the ledger committed to.
            ordered_hashes = [pages[p]["page_sha256"] for p in nums]
            frames = []
            for p in nums:
                rec_rel = pages[p]["receipt"]
                rec_path = self.rp.root / rec_rel
                if not rec_path.is_file():
                    raise LedgerError(f"{rid}: page {p} receipt missing on disk: {rec_rel}")
                raw = rec_path.read_bytes()
                if "receipt_bytes_sha256" in pages[p] and \
                        hashlib.sha256(raw).hexdigest() != pages[p]["receipt_bytes_sha256"]:
                    raise LedgerError(f"{rid}: page {p} receipt BYTES on disk do not match the recorded "
                                      f"byte hash — the receipt file was rewritten after recording")
                fr = pd.read_parquet(rec_path)
                got_sha, got_n = _df_sha256(fr)
                if got_sha != pages[p]["page_sha256"]:
                    raise LedgerError(f"{rid}: page {p} receipt CONTENT does not match the recorded hash "
                                      f"({got_sha[:12]} != {pages[p]['page_sha256'][:12]}) — receipt tampered "
                                      f"or replaced after recording")
                if got_n != int(pages[p]["row_count"]):
                    raise LedgerError(f"{rid}: page {p} receipt row count {got_n} != recorded "
                                      f"{pages[p]['row_count']}")
                if pages[p].get("request_id", rid) != rid:
                    raise LedgerError(f"{rid}: page {p} receipt bound to another request")
                frames.append(fr)
            df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
            # GPT re-review #10 BLOCKER: the signed required_fields were never checked against the
            # FETCHED response. A vendor schema change dropping a signed column would pass verification.
            self._assert_response_fields(row["endpoint"], df.columns)
            # design v4 F5: the frozen response scope re-checked POST-CONCATENATION (defense in depth
            # over the per-page check — a legacy-path receipt is scoped here too).
            self._assert_response_scope(row, df)
            nk = list(row["natural_key"])
            miss = [k for k in nk if k not in df.columns]
            if miss:
                raise LedgerError(f"{rid}: output missing natural-key columns {miss}")
            null_keys = int(df[nk].isna().any(axis=1).sum()) if nk else 0
            if null_keys:
                raise LedgerError(f"{rid}: {null_keys} rows with a null natural key")
            # --- duplicates: the NATURAL key is the vendor's row identity -> a repeat is ALWAYS a bug -
            # GPT re-review #5 F2: `baseline_dups=True` was an unlimited free pass that then SILENTLY
            # dropped the excess, so a duplicated page could mask a missing one. Dups under the natural
            # key now always refuse; only genuine restatement collapse under the coarser content-dedup
            # key is allowed, and only up to the plan's DECLARED max_content_dups bound.
            nk_excess = int(len(df) - len(df.drop_duplicates(subset=nk))) if nk else 0
            if nk_excess:
                raise LedgerError(f"{rid}: {nk_excess} duplicate rows under the NATURAL key {nk} — a "
                                  f"repeated/duplicated page can mask a missing page; refusing")
            dk = list(row["content_dedup_key"]) or nk
            pre = int(len(df))
            deduped = df.drop_duplicates(subset=dk)
            post = int(len(deduped))
            excess = pre - post
            max_dups = int(row["max_content_dups"])
            if excess > max_dups:
                raise LedgerError(f"{rid}: {excess} duplicate rows under {dk} exceeds the declared "
                                  f"max_content_dups={max_dups}")
            # GPT re-review #6 F2 BLOCKER (reproduced): a SPARSE zero-row result used to fall straight
            # through to `verified` — bypassing the canary/confirmation gate entirely — and
            # consolidation_allowed() accepts `verified`. So a request that returned nothing because the
            # FETCH failed was indistinguishable from a partition the vendor genuinely has no data for:
            # missing data could certify as complete. A zero-row result is now NEVER verifiable by
            # verify_request under ANY empty_policy; sparse partitions must go through confirm_empty
            # (independent re-attempt envelopes + a verified nonempty same-endpoint canary).
            if pre == 0:
                if row["empty_policy"] == "dense_refuse":
                    raise LedgerError(f"{rid}: dense dataset verified with 0 rows")
                raise LedgerError(f"{rid}: sparse dataset returned 0 rows — verify_request can NEVER "
                                  f"certify an empty result; use confirm_empty (>=2 independent attempt "
                                  f"envelopes + a verified nonempty same-endpoint canary)")
            # Write the per-request staged output and bind it to its PERSISTED BYTES.
            # GPT re-review #7 B2 (reproduced): the verdict recorded only an in-memory logical hash and
            # consolidation_allowed() trusted terminal STATE alone — so replacing the output with a
            # valid, different parquet after verification still passed consolidation and the corrupt
            # value went on to be staged. That is exactly the in-scope "staged bytes corrupted between
            # steps" case. The verdict now carries path/size/byte-hash/logical-hash, fsync'd, re-read
            # and re-hashed from disk before it is recorded, and revalidated at consolidation.
            import io as _io
            out = self.rp.assert_write(self.rp.staging_data / row["receipt_output"])
            self.rp.broker().mkdirs(out.parent)
            buf = _io.BytesIO()
            deduped.reset_index(drop=True).to_parquet(buf, index=False)
            out_payload = buf.getvalue()
            with self.rp.broker().open_for_write(out, "wb") as fh:
                fh.write(out_payload)
                fh.flush()
                os.fsync(fh.fileno())          # durable BEFORE we certify it
            on_disk = out.read_bytes()          # re-READ: never certify the buffer we hoped we wrote
            out_bytes_sha = hashlib.sha256(on_disk).hexdigest()
            if out_bytes_sha != hashlib.sha256(out_payload).hexdigest():
                raise LedgerError(f"{rid}: staged output on disk does not match what was written")
            out_sha, _ = _df_sha256(deduped)
            ev = {"pre_dedup_rows": pre, "post_dedup_rows": post, "excess_dup_rows": excess,
                  "null_key_rows": 0, "ordered_page_hashes": ordered_hashes, "output_sha256": out_sha,
                  "output_path": row["receipt_output"], "output_size": len(on_disk),
                  "output_bytes_sha256": out_bytes_sha,
                  "contract_sha256": row["contract_sha256"], "doc_sha256": row["doc_sha256"]}
            self._append({"kind": "verdict", "request_id": rid, "state": "verified", "evidence": ev})
            return ev

    def confirm_empty(self, rid: str, *, canary_request_id: str) -> None:
        with self.rp._lock():
            rows = self._load()
            plan = self._plan()
            if rid not in plan:
                raise LedgerError(f"{rid} not in the frozen plan")
            row = plan[rid]
            if row["empty_policy"] != "sparse_canary":
                raise LedgerError(f"{rid}: dense dataset — an empty result can NEVER be accepted")
            # GPT re-review #5 F2: counting empty ATTEMPTS is not proof — the request must itself be a
            # STRUCTURALLY VALID terminal request (contiguous pages 1..N with a typed terminal proof),
            # otherwise a partial/aborted fetch that merely logged empties could certify as "empty".
            pages = self._latest_pages(rows, rid)
            if not pages:
                raise LedgerError(f"{rid}: confirmed_empty needs page receipts")
            nums = sorted(pages)
            if nums != list(range(1, len(nums) + 1)):
                raise LedgerError(f"{rid}: confirmed_empty pages not contiguous 1..N: {nums}")
            _assert_terminal_proof(rid, row, pages, nums)   # the SAME proof verify_request applies
            if any(pages[p]["row_count"] for p in nums):
                raise LedgerError(f"{rid}: confirmed_empty but some page has rows")
            # GPT re-review #6 F2: the old rule required two empty receipts with DIFFERENT payload
            # hashes — but two identical-schema empty responses hash IDENTICALLY, so the gate was
            # unsatisfiable by honest data and my own test only passed by adding a column to change the
            # schema. Independence is a property of the ATTEMPT ENVELOPE (a separate fetch, separately
            # stamped), never of the payload bytes: two genuine empty fetches are SUPPOSED to be
            # byte-identical.
            # GPT re-review #7 B1: counting attempt_uids counted LEDGER WRITES — one empty response
            # recorded twice certified as two independent attempts. Only a COMPLETED CALL LEASE (opened
            # by the ledger BEFORE it made the call, closed after) evidences a real fetch, and two of
            # them must not overlap in time — concurrent leases would be one response fanned out.
            empt = [a for a in self._closed_leases(rows, rid) if a["row_count"] == 0]
            if len({a["lease_id"] for a in empt}) < 2:
                raise LedgerError(f"{rid}: confirmed_empty needs >=2 COMPLETED CALL LEASES returning "
                                  f"empty (the ledger must have made two real calls); got {len(empt)}")
            windows = sorted((a["opened_at"], a["closed_at"]) for a in empt)
            if not any(windows[i][1] <= windows[i + 1][0] for i in range(len(windows) - 1)):
                raise LedgerError(f"{rid}: confirmed_empty needs two SEQUENTIAL empty calls (disjoint "
                                  f"lease windows); the leases overlap, which is one response fanned out")
            can = plan.get(canary_request_id)
            if not can or can["endpoint"] != row["endpoint"]:
                raise LedgerError(f"{rid}: canary must be a planned SAME-endpoint request")
            if self._state_of(rows, canary_request_id) != "verified" \
                    or not any(a["row_count"] > 0 for a in self._attempts(rows, canary_request_id)):
                raise LedgerError(f"{rid}: canary {canary_request_id} must be verified AND nonempty")
            self._append({"kind": "verdict", "request_id": rid, "state": "confirmed_empty",
                          "canary_request_id": canary_request_id})

    def verdict_of(self, rows, rid):
        ev = None
        for r in rows:
            if r.get("kind") == "verdict" and r.get("request_id") == rid:
                ev = r.get("evidence") or ev
        return ev

    def assert_staged_outputs_intact(self, dataset: str) -> None:
        """GPT re-review #7 B2: re-prove every VERIFIED staged output against the path/size/byte-hash
        recorded in its verdict. A verdict is a statement about bytes that existed at verify time; it
        is not evidence about the bytes that exist now. Called under the ledger lock at consolidation
        and again immediately before any dataset build."""
        rows = self._load()
        plan = self._plan()
        for rid, r in plan.items():
            if r["dataset"] != dataset or self._state_of(rows, rid) != "verified":
                continue
            ev = self.verdict_of(rows, rid) or {}
            want = ev.get("output_bytes_sha256")
            if not want:
                raise LedgerError(f"{rid}: verified without a persisted-byte binding — re-verify")
            out = self.rp.staging_data / ev.get("output_path", r["receipt_output"])
            if not out.is_file():
                raise LedgerError(f"{rid}: staged output {out} is GONE since verification")
            raw = out.read_bytes()
            if len(raw) != int(ev.get("output_size", -1)) or hashlib.sha256(raw).hexdigest() != want:
                raise LedgerError(f"{rid}: staged output {out} CHANGED since verification "
                                  f"(bytes/size mismatch) — rebuild it from the immutable receipts or "
                                  f"refuse; a verified verdict is not evidence about today's bytes")

    def consolidation_allowed(self, dataset: str):
        with self.rp._lock():
            rows = self._load()
            plan = self._plan()
            pend = [rid for rid, r in plan.items() if r["dataset"] == dataset
                    and self._state_of(rows, rid) not in _TERMINAL]
            if pend:
                return (False, pend)
            self.assert_staged_outputs_intact(dataset)   # bytes, not just state
            return (True, [])


# ── prepare_raw_page producer registry (design v4 F8) ────────────────────────────────────────────
# Endpoint-scoped, ledger-boundary producers for the coordinator-derived natural-key columns. The
# row_payload_digest producer is the ledger's own canonical lossless encoder; the three event families
# whose vendor rows carry no transaction id key on it. report_rc's digest producer is DELIBERATELY not
# registered yet (it lives downstream in pit_backend and moves here at fan-out); until then a report_rc
# claimed fetch refuses fail-closed in _prepare_raw_page.
_PREPARE_REGISTRY.update({
    "top_list": PageReceiptLedger.add_row_payload_digest,
    "top_inst": PageReceiptLedger.add_row_payload_digest,
    "block_trade": PageReceiptLedger.add_row_payload_digest,
})
