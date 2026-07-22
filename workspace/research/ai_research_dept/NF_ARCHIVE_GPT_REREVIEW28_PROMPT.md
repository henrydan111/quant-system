# GPT Cross-Review Request — NF Final-Integration Unit 1 RE-REVIEW #28 (v2 round 2: entry contract snapshot + one ledger identity gate)

You are re-reviewing the **decision-archive boundary** of the news-flash (NF) seat against the
**amended v2 threat model**. This is **round 2 of 3** against v2 (#27 was round 1).

**Commit under review: `6886e39`** on branch `calendar-unfreeze`. Threat model v2 = `c3a8d93`.

## The v2 criterion (unchanged)

Full text: https://raw.githubusercontent.com/henrydan111/quant-system/c3a8d93/workspace/research/ai_research_dept/NF_ARCHIVE_THREAT_MODEL.md

A boundary function is **defective iff** a crafted in-process instance can **(i) seal/accept a
forged / non-exact / decoupled value, (ii) mutate already-verified/trusted state, or (iii) leak** —
*fail-closed integrity*. A benign callback on a path that then **raises** (seals/accepts/mutates/leaks
nothing) is **OUT-OF-SCOPE**. Out-of-scope also: code-edit-equivalent capability (monkeypatch,
class-level dunder reassignment), on-disk tamper, cross-process race, sha256 break, DoS.

Your #27 findings were correctly in-scope under v2 — both **accepted** a substituted value or
**returned trusted data under a wrong identity**. Both are folded here.

## Files (embedded text authoritative; links pin to `6886e39`)

- https://raw.githubusercontent.com/henrydan111/quant-system/6886e39/workspace/research/ai_research_dept/engine/news_executors.py
- https://raw.githubusercontent.com/henrydan111/quant-system/6886e39/workspace/research/ai_research_dept/engine/news_decision.py
- https://raw.githubusercontent.com/henrydan111/quant-system/6886e39/workspace/research/ai_research_dept/engine/news_archive.py
- https://raw.githubusercontent.com/henrydan111/quant-system/6886e39/workspace/research/ai_research_dept/tests/test_news_engine_invariants.py

## How the two P1s were folded

**P1#1 (class 2/4) — entry snapshot.** `execute_news_decision` now gates `decision_id` and then binds
`contract = snapshot_exact_contract(contract)` and `artifact = verify_d7_artifact(artifact)` before
touching `artifact.final_registry`; everything downstream uses those independent copies. Both
primitives already existed from the #23 fold — this call site had simply never been wired to them,
which is why the registry `.items()` callback could substitute a self-consistent contract that then
flowed into the commitment and archive.

**P1#2 (decision-flip / leak) — one identity gate, six readers.** New single gate
`news_decision.require_exact_id(value, what)` — exact non-empty `str`, static refusal, applied
**before reading the chain and before any comparison**. Applied to **all six** readers of the
`disk_str == caller_id` shape:

| reader | ids gated |
|---|---|
| `news_decision.lookup_decision` | decision_id |
| `news_decision.find_success_commitment` | decision_id |
| `news_decision.find_execution_commitment` | decision_id, execution_id |
| `news_archive._find_success_commitment` | decision_id |
| `news_archive._find_commitment` | decision_id, execution_id |
| `news_executors._resolve_terminal` | decision_id, execution_id |

The last one you did not name — **the mechanical guard found it** (see below).

## Mechanical surface enumeration (please attack this)

`tests/test_news_engine_invariants.py` adds two guards:

1. **Runtime**: every gated reader × every id parameter, probed with an always-equal `str` subclass;
   asserts refusal and that the redirect `__eq__` never ran.
2. **AST, precise shape**: a row's id field (`e["decision_id"]` / `r.get("execution_id")`) compared
   with `==` against a **bare parameter name** — the shape whose result a subclass `__eq__` can
   redirect. The enclosing function must carry one of three sanctioned gates: `require_exact_id`,
   `_deep_plain_json`, or `type(x) is not str`. Markers are matched against **real source text**
   because `type(x) is not str` renders as `IsNot()`/`Name('str')` in `ast.dump` and would otherwise
   be missed. Field-binding comparisons against an already-snapshotted attribute
   (`row["decision_id"] != outcome.decision_id`) are deliberately not this shape.

## Regressions (all three verified to FAIL on the pre-fix engine)

- registry-callback contract swap: the callback **does** fire, but the executed outcome stays
  `primary_horizon` (the entry snapshot froze the original contract) instead of the substituted
  `vector_only`;
- every ledger reader refuses an always-equal `str` subclass on every id parameter, redirect count 0;
- the AST guard (which is what surfaced `_resolve_terminal`).

## Self-review

Verdict: **clean for GPT**. Both P1s folded by invariant class rather than per site; the enumeration
guard found a sixth site the review had not named. Tests: ai_research_dept **728** green +
data_infra news 17 green. Disclosed residuals: (a) `require_exact_id` is applied at the readers, so a
*new* reader that forgets it is caught by the AST guard only if it uses the exact shape the guard
expresses — if you can name a seventh shape that redirects a lookup, that is more valuable than
another instance; (b) `_check_terminal_row` / `verify_execution_bundle` compare row ids against
*snapshotted attributes* rather than raw parameters and are deliberately outside the guard — please
confirm that reasoning holds. Your #27 note about a leftover sandbox temp dir
(`.review_tmp_nf27_7f1a`) — nothing by that name exists in the repo; it was outside the working tree.

## Review questions

1. Under v2, can a crafted instance still make the boundary **seal/accept** a forged or substituted
   value, **mutate** verified state, or **leak**? Reproduce against `6886e39`.
2. Is the entry snapshot in `execute_news_decision` complete — any remaining path where the live
   contract/artifact is read after the registry callback?
3. Is the identity gate's coverage honest — is there a **seventh** reader or a different shape that
   takes a caller id into a trusted-row comparison, and does the AST guard express the class or only
   the instances?
4. Are the two deliberate guard exclusions (snapshotted-attribute comparisons) correct?
5. **Verdict:** SOUND-TO-PROCEED (to the four-seat session-archive embedding), or REVISE with a
   **v2-in-scope** gap reproduced against `6886e39`. Benign-callback observations are out-of-scope
   notes and must not gate.
