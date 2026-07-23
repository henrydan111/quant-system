# GPT Cross-Review Request — NF integration P3a RE-REVIEW #6 (Tier-2, diff-scoped)

Round 6. Your round-5 verdict: P1 (read-boundary contract) correctly fixed; **1 P2 remaining** — the
separator regex handled only CR/LF/U+2028/U+2029 while the frozen sanitizer deletes all `Cc`/`Cf`, so
NEL / Tab / ZWJ still fused words. Folded — **structurally**, not by extending the list.

**Commit under review: `f255680`** on branch `calendar-unfreeze`. Tier-2 (frozen; Tier-1
crafted-object analysis out of tier — record as tracked notes or recommend a tier change to the user).

## The fold — mirror the predicate, don't enumerate the characters

This was the **third** occurrence of one class (CR/LF fixed by enumeration → NEL/Tab/ZWJ still fused).
Per our convergence rule (repeat-class ⇒ structural chokepoint), the fix is no longer a separator list:

```python
_SANITIZER_DELETES = ("Cc", "Cf")          # mirrors the frozen sanitizer's own predicate

def _space_out_deleted_controls(s: str) -> str:
    normalized = _ud.normalize("NFKC", s)
    return "".join(" " if _ud.category(ch) in _SANITIZER_DELETES else ch
                   for ch in normalized)
```

`sanitize_text` does NFKC → drops `Cc`/`Cf` → collapses whitespace. This pre-pass mirrors that exact
deletion predicate, so **every** codepoint the sanitizer would delete — present or future — becomes a
boundary instead of a fusion, and the sanitizer's own whitespace collapse merges the runs.

## The guard is structural too, not a sample

- `test_every_sanitizer_deleted_codepoint_is_a_boundary` enumerates **all 0x110000 codepoints**, keeps
  those whose category is `Cc`/`Cf`, and asserts none of them fuses `does` + `not`.
- Plus a named parametrization: LF, CR, TAB, NEL, ZWJ, ZWNJ, ZWSP, LS, PS, BOM, SHY.

**Fail-pre-fix is itself the argument for the structural shape:** on the pre-fix module TAB, NEL, ZWJ,
ZWNJ, ZWSP, BOM and SHY all fused, and the enumeration guard failed — only the four separators the old
regex happened to list passed.

Tests: 34 P3a + full ai_research_dept **811** green.

## Files (pin to `f255680`)

- https://raw.githubusercontent.com/henrydan111/quant-system/f255680/workspace/research/ai_research_dept/engine/news_flash_split.py
- https://raw.githubusercontent.com/henrydan111/quant-system/f255680/workspace/research/ai_research_dept/tests/test_news_flash_split.py
- the frozen sanitizer being mirrored: https://raw.githubusercontent.com/henrydan111/quant-system/f255680/workspace/research/ai_research_dept/engine/cards.py (`sanitize_text`, line ~25)

## Diff-scoped review questions

1. Does mirroring the sanitizer's predicate close the token-fusion class **by construction**? Is
   `Cc`/`Cf` after NFKC exactly what `sanitize_text` deletes — any drift between the two (e.g. a
   codepoint whose category changes under NFKC, or a deletion the sanitizer performs that this
   predicate does not model)?
2. Is the ordering right — NFKC → space-out → `sanitize_text` (which normalizes again)? Any
   double-normalization hazard?
3. Does the whole-0x110000 enumeration guard actually pin the class, or is there a fusion shape it
   cannot express (e.g. a *multi-character* sequence that fuses only in combination)?
4. **New surface:** anything the fold introduced that creates a new declared-invariant gap?
5. **Verdict:** SOUND-TO-PROCEED (to P3b) or a specific in-tier gap. If your remaining concerns are
   out-of-tier or tracked-debt in nature, please say SOUND-TO-PROCEED with them listed as notes.
