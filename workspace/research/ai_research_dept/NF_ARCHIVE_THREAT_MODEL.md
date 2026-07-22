# NF Decision-Archive Boundary — Frozen Threat Model (v1)

**Status:** proposed 2026-07-22, pending user approval. Once approved this is FROZEN for the
remainder of the archive-boundary review arc. Per CLAUDE.md §10, findings are judged against THIS
spec; re-scoping is a user decision, never round-N legislation.

**Unit under review:** NF Final-Integration Unit 1 — the decision-archive sealing/verification layer
(`news_archive.py` + its verify dependencies in `news_cards.py`, `news_evidence.py`, `news_seal.py`,
`news_legs.py`, `news_executors.py`).

**Purpose of the boundary:** given in-process inputs, either REJECT them or return a value provably
bound to on-disk *committed* state (the hash-chained ledger + write-once archive), such that the
sealed archive's committed hashes equal the hashes of the fields actually sealed.

---

## 1. Trust boundary

- **TRUSTED:** the OS process running the pipeline; the engine source modules and their class
  objects; the Python runtime/builtins; sha256; the file-lock + hash-chain + write-once machinery
  (covered by their own invariants, not this arc); on-disk ledger/archive bytes at rest.
- **UNTRUSTED:** the **in-process caller's arguments** to the boundary functions — `bundle`,
  `artifact`, `contract`, `registry`, `records`, `bundle_eval`, `chain`, `decision_id`,
  `execution_id`, and every object reachable through them. A caller may pass crafted objects:
  subclasses of `dict`/`list`/`str` with stateful `.items()`/`__iter__`/`__getitem__`/`__eq__`/
  `__ne__`, instances with overridden `__getattribute__`/`__repr__`/`__str__`, metaclass `__eq__`,
  and objects mutated via `object.__setattr__` during a callback the boundary triggers.

Rationale for treating a same-process caller as untrusted while the process is trusted: these
functions ARE the verification boundary. Their contract must hold for arbitrary in-process inputs so
that a construction bug (not just malice) cannot decouple the committed hash from the sealed fields.

## 2. In-scope failure classes (the boundary MUST prevent all five)

1. **Hash/field decoupling (forgery):** archive commits hash `H` but seals fields `F` with
   `sha256(F) ≠ H`; or a committed row's hash is not re-derived from its own on-disk content.
2. **Callback-time mutation (TOCTOU-via-callback):** a value is verified, then a caller-controlled
   `__eq__`/`__ne__`/`.items()`/`__iter__`/`__getattribute__`/serialization hook mutates it before
   it is used or sealed.
3. **Rejection-path callback:** constructing an error message or performing a gate comparison invokes
   untrusted `__repr__`/`__str__`/`type(x).__name__`/`__eq__` on a caller object.
4. **Phase-substitution:** a callback the boundary triggers (e.g. a registry mapping's `.items()`)
   swaps an already-verified component between its verification and its use.
5. **Pre-type-gate read:** a public entry compares or dereferences an untrusted id/object before the
   exact-type gate that is supposed to reject it.

**Acceptance criterion (what "closed" means for each class):** given an adversarial in-process input
of that class, the boundary either (a) raises with a STATIC error (no untrusted callback fires), or
(b) returns a value whose committed/sealed fields are reconstructed solely from disk-resolved,
frozen, or entry-captured state that the caller holds no live reference to — **proven by a pinned
regression that fails on the pre-fix code and passes after, and that asserts the adversarial hook is
never invoked.**

## 3. Out-of-scope failure classes (noted if raised, but they do NOT gate this arc)

- **Code-edit-equivalent capability:** monkeypatching engine functions; replacing `verify_sealed`,
  `json.dumps`, or builtins; reassigning an engine frozen-dataclass's class-level dunder
  (`D7BaseFact.__eq__ = …`); editing engine source. If the caller has this, it can write a forged
  archive directly and the boundary is moot.
- **On-disk tampering** with ledger/archive bytes by a process that already holds/defeats the file
  lock — that is the hash-chain + write-once + file_lock invariants' responsibility (separate arc).
- **Cross-process concurrency races** — covered by `file_lock` + write-once-first-write-wins.
- **Cryptographic breaks** — sha256 collision/preimage are assumed hard.
- **Denial of service / resource exhaustion** — availability is not a sealing-integrity property.

## 4. Boundary invariants (the standing contract, unchanged by this arc)

- Every committed ledger row's hash is re-derived from its own on-disk content before it is trusted.
- The archive commits exactly the canonical-success commitment; write-once, first-write-wins.
- Sealing consumes only the verified/captured payload + ledger head — zero live re-reads of caller
  objects after verification.
- Exact-type gates use `type(x) is C` (never `isinstance`, never `type(x) in (...)`); cross-object
  comparison uses canonical JSON, never the caller's `__eq__`.

---

**Convergence rule for the review arc:** a GPT finding is IN-SCOPE (must fold) iff it demonstrates
one of the five classes in §2 with an input that needs none of the §3 capabilities. A finding that
requires a §3 capability, or asserts a §3 class, is recorded as out-of-scope and does not gate
SOUND-TO-PROCEED.
