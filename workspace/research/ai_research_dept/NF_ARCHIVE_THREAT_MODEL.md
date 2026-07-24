# NF Decision-Archive Boundary — Frozen Threat Model (v3)

**Status:** v1 frozen + user-approved 2026-07-22 (commit `fe99286`). **v2 amendment user-approved
2026-07-22** after the round-3 arbitration on the GPT #26 verdict (the 3-round budget for classes
3/5 was reached; the user chose *re-scope* over further folding). **v3 amendment user-approved
2026-07-24** after the P4a round-3 arbitration (GPT P4a re-review#3 P1#1: a caller can supply its
own root directories and commit a genuine chain over fabricated data; the user chose *re-scope*
over a config-binding mechanism or tracked debt). Once approved this is FROZEN again; per CLAUDE.md
§10, findings are judged against THIS spec; re-scoping is a user decision, never round-N legislation.

**v3 amendment in one line:** **root selection is OUT OF SCOPE.** The operator-designated root
directories (`ledger_dir`, `prov_dir`, `archive_dir`, and — since P4a — `store_dir`,
`artifact_dir`) are ONE trust class: the boundary's guarantees are **relative to a given, fixed set
of roots** ("no forged/decoupled value is ever sealed or accepted *within the operator's world*").
An in-process caller who designates different roots and runs the genuine pipeline over them has not
forged anything *in the operator's world* — it has built its own world, which in-process Python
cannot prevent (a caller with root-selection freedom could equally point `ledger_dir` itself at a
fresh directory; caller-distinguishing inside one process is the documented combinatorial trap —
ledger-integrity arc, user decision 2026-07-22). **Binding "which roots are the production roots" is
a deployment/configuration obligation discharged at the FORWARD_PREREG integration** (a governed
runner pins the roots; the same pattern as `book_seal.py`'s live-refusal preconditions), NOT an
in-process boundary property. A finding is admissible against this boundary iff it demonstrates
forgery / decoupling / mutation / leak **within one fixed root set** the operator designated.

**v2 amendment in one line:** the load-bearing guarantee is **fail-closed integrity** — nothing
forged or non-exact is ever sealed/accepted, and no callback can mutate trusted state or leak. A
benign caller callback that fires on a path which *raises* (seals nothing, accepts nothing, mutates
no trusted state, leaks nothing) is **NOT a defect** under the process-is-trusted model. See §2 for
the precise wording; the rationale is that "zero caller code observed on a raising reject path" is a
purity property stricter than the integrity guarantee requires, and chasing it site-by-site is the
documented combinatorial-surface trap (CLAUDE.md §10; memory `incident_raw_store_deleted_20260713`).

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

## 2. In-scope failure classes (v2)

**The single load-bearing criterion (v2):** a boundary function is DEFECTIVE iff a crafted in-process
instance can cause it to **(i) seal or accept a forged / non-exact / decoupled value, (ii) mutate
already-verified/trusted state, or (iii) leak trusted data** — i.e. any breach of *fail-closed
integrity*. A caller callback that merely fires on a path which then **raises** (seals nothing,
accepts nothing, mutates no trusted state, leaks nothing) is **explicitly OUT-OF-SCOPE** — the caller
runs its own code against its own object to no effect, which under the process-is-trusted model is a
construction/purity nit, not a security defect. (DoS via a callback is already out-of-scope, §3.)

1. **Hash/field decoupling (forgery):** archive commits hash `H` but seals fields `F` with
   `sha256(F) ≠ H`; or a committed row's hash is not re-derived from its own on-disk content.
2. **Callback-time mutation (TOCTOU-via-callback):** a value is verified, then a caller-controlled
   `__eq__`/`__ne__`/`.items()`/`__iter__`/`__getattribute__`/serialization hook **mutates trusted
   state or the value being sealed** before it is used or sealed. *(A callback that mutates only the
   caller's own object on a path that then raises is out-of-scope per the v2 criterion.)*
3. **Decision-flipping rejection-path callback (v2-narrowed):** a callback runs on a security
   comparison and **could change the comparison's outcome** so that a forged/mismatched input is
   *accepted* (e.g. a key `__eq__` that makes a forged archive match a lookup; a `__eq__`/`__ne__`
   that makes a non-equal value compare equal). **OUT-OF-SCOPE (v2):** a callback that runs on a gate
   which then *raises* regardless of what the callback returns — including `isinstance(x, str)`
   reading a spoofed `__class__`, or `canon`/`pd.isna`/`hasattr` touching an object that is then
   refused — because it flips no decision and seals nothing. *(Diagnostics still SHOULD use
   `safe_repr`/`safe_kind` as defence-in-depth, but a residual benign callback here no longer gates.)*
4. **Phase-substitution:** a callback the boundary triggers (e.g. a registry mapping's `.items()`)
   swaps an already-verified component between its verification and its use **such that the swapped
   value is trusted downstream** (sealed/consumed).
5. **Pre-type-gate read that changes an outcome:** a public entry compares or dereferences an
   untrusted id/object before its gate **in a way that could accept a forged input or run a
   mutation** (e.g. `bundle["outcome"]` where a colliding non-str key's `__eq__` could redirect the
   lookup). **OUT-OF-SCOPE (v2):** a pre-gate read whose only effect is a benign callback on a path
   that then raises and seals/accepts nothing.

**Acceptance criterion (what "closed" means):** given an adversarial in-process input of an in-scope
class, the boundary either (a) **fails closed** — raises / refuses, sealing and accepting nothing and
mutating no trusted state — or (b) returns a value whose committed/sealed fields are reconstructed
solely from disk-resolved, frozen, or entry-captured state the caller holds no live reference to.
Proven by a pinned regression that fails on the pre-fix code. A regression MAY additionally assert a
hook is never invoked (defence-in-depth), but under v2 the *gating* assertion is fail-closed
integrity, not the hook count.

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
- **(v3) Root selection / root identity** — an in-process caller designating its OWN root
  directories (`store_dir` / `artifact_dir` / `ledger_dir` / `prov_dir` / `archive_dir`) and running
  the genuine pipeline over them. The boundary's guarantees are relative to a fixed root set;
  production-root binding is a FORWARD_PREREG deployment obligation (governed runner), not an
  in-process property. In-scope findings must hold the root set fixed.
- **(v2) Benign callback on a raising/refusing path** — a crafted instance's `__class__` / `__str__`
  / `__getattr__` / `__array__` / `__repr__` firing on a gate that then raises, when it flips no
  security decision, seals/accepts nothing, mutates no trusted state, and leaks nothing. Documented
  examples ruled out-of-scope at v2: `plain_str`/`SealedCardRegistry` `isinstance(x, str)` reading a
  `@property __class__` (GPT #26 #1); `canon`'s `pd.isna`/`hasattr(to_pydatetime)` running before
  exact-type dispatch on a value that is then refused (GPT #26 #2). Both were confirmed fail-closed
  (nothing forged sealed). Defence-in-depth hardening of these MAY still be done opportunistically but
  does not gate SOUND-TO-PROCEED.

## 4. Boundary invariants (the standing contract, unchanged by this arc)

- Every committed ledger row's hash is re-derived from its own on-disk content before it is trusted.
- The archive commits exactly the canonical-success commitment; write-once, first-write-wins.
- Sealing consumes only the verified/captured payload + ledger head — zero live re-reads of caller
  objects after verification.
- **Decision-bearing** exact-type gates use `type(x) is C` (never `type(x) in (...)` — that uses `==`
  and a lying metaclass controls the answer, which CAN flip a decision → in-scope). `isinstance` is
  discouraged (it reads `__class__`) but, where its only failure mode is a benign callback on a
  raising path (v2 §3), it is tolerated as out-of-scope. Cross-object comparison that could ACCEPT a
  forged value uses canonical JSON / plain-typed snapshots, never the caller's `__eq__`.
- The str-normalization chokepoint is single and fail-closed: `news_seal.plain_str` (exact str passes;
  str subclass flattened via builtin `str.__str__`; anything else raises — never `str()`). No module
  may carry a forked normalizer with a `str(x)` fallback. *Enforced:* the AST meta-tests in
  `tests/test_news_engine_invariants.py` (ban `type(...)`-with-`==`/`in`, ban bare `str(x)` in the 8
  security modules).

---

**Convergence rule for the review arc (v2):** a GPT finding is IN-SCOPE (must fold) iff it
demonstrates, with an input needing none of the §3 capabilities, a breach of **fail-closed
integrity** per §2 — i.e. it seals/accepts a forged/non-exact value, mutates trusted state, or leaks.
A finding whose only effect is a benign callback on a path that raises and seals/accepts nothing is
OUT-OF-SCOPE (§3) and does NOT gate SOUND-TO-PROCEED, regardless of hook counts.
