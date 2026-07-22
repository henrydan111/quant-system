# GPT Cross-Review Request — NF Final-Integration Unit 1 RE-REVIEW #27 (FINAL, against the AMENDED v2 threat model)

You are giving the **final scope-bounded verdict** on the decision-archive boundary of the news-flash
(NF) seat. Your #26 verdict was a round-3 same-class (3/5) REVISE that, per our frozen convergence
protocol, handed the decision to the user. **The user chose to RE-SCOPE the threat model, not to fold
further.** The model is now amended to **v2**. Your job here is to review the boundary **against v2**
and confirm SOUND-TO-PROCEED, or raise a finding that is in-scope *under v2*.

**Commits:** threat model v2 = `c3a8d93`; boundary code unchanged since `8fed4eb` (re-scope means the
two #26 findings do not gate — no code was changed for them).

## What changed in v2 (this is the ruling to apply)

Full text (pinned): https://raw.githubusercontent.com/henrydan111/quant-system/c3a8d93/workspace/research/ai_research_dept/NF_ARCHIVE_THREAT_MODEL.md

- **Single load-bearing criterion:** a boundary function is defective iff a crafted in-process
  instance can **(i) seal/accept a forged / non-exact / decoupled value, (ii) mutate
  already-verified/trusted state, or (iii) leak.** That is *fail-closed integrity*.
- **Explicitly OUT-OF-SCOPE (v2):** a benign caller callback that fires on a path which then
  **raises** — sealing nothing, accepting nothing, mutating no trusted state, leaking nothing. Under
  the process-is-trusted model the caller running its own code against its own object to no effect is
  a purity nit, not a security defect. Chasing "zero callback on a raising reject path" site-by-site
  is the documented combinatorial-surface trap.
- **Your two #26 findings are ruled OUT-OF-SCOPE by v2** (you confirmed both are fail-closed —
  nothing forged is sealed): `isinstance(x, str)` reading a `@property __class__` on a gate that then
  raises; `canon`'s `pd.isna`/`hasattr(to_pydatetime)` running before exact-type dispatch on a value
  that is then refused.
- **Classes that RETAIN FULL TEETH:** (1) forgery/hash-decoupling; (2) callback-time mutation of
  **trusted** state or the value being sealed; (4) phase-substitution where the swapped value is
  **trusted downstream**; and the **decision-FLIPPING** halves of (3)/(5) — a callback that could make
  a forged/mismatched input be *accepted* (e.g. a colliding key `__eq__` redirecting a lookup so a
  wrong record is sealed).

## The question v2 asks you (please answer within this scope)

Given v2, the review is no longer "does any caller callback ever fire on a reject path" — it is: **can
a crafted in-process instance make the boundary SEAL or ACCEPT something forged/non-exact, MUTATE
verified state, or LEAK?**

## Files (embedded text authoritative; code pinned to `8fed4eb`, model to `c3a8d93`)

- https://raw.githubusercontent.com/henrydan111/quant-system/8fed4eb/workspace/research/ai_research_dept/engine/news_archive.py
- https://raw.githubusercontent.com/henrydan111/quant-system/8fed4eb/workspace/research/ai_research_dept/engine/news_cards.py
- https://raw.githubusercontent.com/henrydan111/quant-system/8fed4eb/workspace/research/ai_research_dept/engine/news_evidence.py
- https://raw.githubusercontent.com/henrydan111/quant-system/8fed4eb/workspace/research/ai_research_dept/engine/news_legs.py
- https://raw.githubusercontent.com/henrydan111/quant-system/8fed4eb/workspace/research/ai_research_dept/engine/news_executors.py
- https://raw.githubusercontent.com/henrydan111/quant-system/8fed4eb/workspace/research/ai_research_dept/engine/news_decision.py
- https://raw.githubusercontent.com/henrydan111/quant-system/8fed4eb/workspace/research/ai_research_dept/engine/news_seal.py
- https://raw.githubusercontent.com/henrydan111/quant-system/8fed4eb/workspace/research/ai_research_dept/engine/news_horizon.py
- https://raw.githubusercontent.com/henrydan111/quant-system/8fed4eb/workspace/research/ai_research_dept/tests/test_news_archive.py
- https://raw.githubusercontent.com/henrydan111/quant-system/8fed4eb/workspace/research/ai_research_dept/tests/test_news_engine_invariants.py

## State of the in-scope classes (from the arc so far)

- **Class 1 (forgery):** every committed row's hash re-derived from its own on-disk content;
  `verify_d7_artifact` fully re-derives the artifact; archive `archive_sha256` verified on load.
- **Class 2 (mutation of trusted state):** `verify_d7_artifact` returns an independent copy consumed
  by all 8 call sites; contract/outcome snapshotted before any callback; sealing consumes only the
  captured `verified` payload.
- **Class 4 (phase-substitution):** registry `.items()` swap of `artifact.base_facts`/bundle is
  invisible — downstream uses the independent copies + fresh registries (pinned regressions).
- **Class 3/5 decision-flipping:** the `bundle` key sweep runs before any `bundle[...]` (colliding
  non-str key refused before its `__eq__` can redirect a lookup); `is_plain_scalar` is all-`is` so a
  lying metaclass cannot impersonate a scalar to pass a gate; `require_recorded` gates `decision_id`
  before it reaches ledger `==`.

## Review questions

1. Under v2, is there any path where a crafted in-process instance makes the boundary **seal or
   accept** a forged / non-exact / decoupled value? Reproduce against `8fed4eb` if so.
2. Any **callback-time mutation of trusted state** (class 2) or **phase-substitution trusted
   downstream** (class 4) still open?
3. Any **decision-flipping** class-3/5 callback — one whose return value could cause a forged input to
   be *accepted* (not merely a benign callback on a raising path) — still open?
4. Confirm the two #26 findings are correctly OUT-OF-SCOPE under v2 (fail-closed: they seal nothing,
   accept nothing, mutate nothing). If you believe either actually DOES seal/accept/mutate/leak,
   reproduce it — that would make it in-scope even under v2.
5. **Verdict:** SOUND-TO-PROCEED (to the four-seat session-archive embedding), or REVISE with a
   specific **v2-in-scope** (fail-closed-integrity) gap reproduced against `8fed4eb`. Benign-callback
   observations may be listed as out-of-scope notes but must not gate.
