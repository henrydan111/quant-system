# GPT Cross-Review Request — NF integration P2 RE-REVIEW #8 (confirm exact-type gate; **tier boundary restated**)

Narrow confirmation of one fix, plus an explicit restatement of this unit's **frozen review tier**.

**Commit under review: `4b901f4`** on branch `calendar-unfreeze`.

---

## ⚠ FROZEN REVIEW TIER — Tier-2 (please respect; do not escalate)

Per CLAUDE.md §10 review-tiering (2026-07-22): the tier is assigned when the design freezes, is stated
in the review prompt, and **the reviewer must not escalate it mid-arc**. This unit's tier was declared
**Tier-2** in round 1 and has not changed:

- **Tier-2 = declared-invariant review.** Judge P2 against its declared invariants and the
  quantitative-research principles (PIT / no-lookahead first), assuming **ordinary, well-formed
  in-process inputs** (real DataFrames, a real `DatetimeIndex`, real reference data).
- **Tier-1 analysis is OUT OF TIER here** — crafted objects, subclass overrides, dunder/metaclass
  attacks, adversarial in-process callers. That standard is reserved (by user decision) for the
  research-integrity-critical surfaces: seal spend / holdout access, PIT alignment kernels, and the
  sealed-archive commitment (a separate, already-shipped unit).

**Why this is being restated now, explicitly:** your re-review#7 P0 was a `DatetimeIndex` **subclass**
overriding `normalize()` — a crafted-object finding, i.e. Tier-1 analysis applied to a Tier-2 unit.
The finding was real and I folded it (see below), but this repo has one documented 24-round review arc
whose root cause was exactly this: an implicit Tier-1 (adversarial in-process caller) standard applied
to in-process Python, whose callback/override surface is combinatorial and cannot be closed by
enumeration. The tiering rule exists to prevent that recurrence.

**So for this round and any further P2 round:** if you find a crafted-object / subclass / dunder issue,
please **record it as an OUT-OF-TIER note** (valuable, tracked, not gating) rather than a gating P0/P1,
and give the verdict on the Tier-2 surface. If you believe P2 genuinely warrants Tier-1, say so
explicitly as a **recommendation to the user** — the tier is theirs to change, not the reviewer's or
mine.

---

## The fix under review (folded from your re-review#7)

`isinstance(cal, pd.DatetimeIndex)` accepted a subclass, which could override `normalize()` to pass
every shape check and re-enable same-day visibility. Every guard after the type check reads a calendar
attribute, so the **exact-type gate now fires first**:

```python
if type(cal) is not pd.DatetimeIndex:
    raise ValueError("open_calendar 须为恰 pd.DatetimeIndex——子类拒(…)")
# only then: tz / non-empty / NaT / sorted / unique / midnight checks
```

Regression `test_p0_datetimeindex_subclass_refused_before_any_override_runs`: a `DatetimeIndex`
subclass with an instrumented `normalize()` is refused and the override is **never invoked**
(`fired == 0`). Verified to FAIL on the pre-fix module (the subclass was not refused).

Tests: 30 P2 + full ai_research_dept **777** green.

## Files (pin to `4b901f4`)

- https://raw.githubusercontent.com/henrydan111/quant-system/4b901f4/workspace/research/ai_research_dept/engine/news_flash_assess.py
- https://raw.githubusercontent.com/henrydan111/quant-system/4b901f4/workspace/research/ai_research_dept/tests/test_news_flash_assess.py

## P2's declared Tier-2 invariants (the surface to judge)

1. PIT inherited + one canonical cutoff + fully as-of registry (listing dates fail-closed; names
   PIT via namechange with **strictly-next-open-trading-day** visibility; routing as-of the same cutoff).
2. P1 binding — artifact verified (dict or path), exact (cutoff, ingest_class), raw content-hash set
   EQUALS the P1-typed set, consumed SHA bound in.
3. Deterministic routing, no LLM, union over all cluster members; routing basis recorded.
4. `evidence_class` verify-not-trust; no cross-fact typing wash (mixed-typing clusters refused);
   importance = literal-int-validated max over members.
5. Macro-routed flashes kept but `news_render_eligible=False`.
6. Immutable write-once persistence (canonical microsecond-cutoff path).
7. NON_EVIDENTIARY; empty day → empty artifact.

## Confirmation questions

1. Does the exact-type gate close the subclass path as prescribed, with no calendar attribute read
   before it?
2. **On the Tier-2 surface** (well-formed inputs), is there any remaining declared-invariant gap —
   especially PIT/no-lookahead?
3. Any out-of-tier (crafted-object) observations you want recorded as tracked notes? Please label them
   as such rather than gating.
4. **Verdict:** SOUND-TO-PROCEED to P3 on the Tier-2 surface, or a specific in-tier gap. If your only
   remaining concerns are out-of-tier, the correct verdict is SOUND-TO-PROCEED with those listed as
   notes.
