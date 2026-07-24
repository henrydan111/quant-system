# GPT Re-review #7 — Macro wave M1 — CONFIRMATION round 4 (narrow)

Confirming exactly the round-6 P1 fix. Scope: the one diff. **Tier-2**.

**Fold commit: `c399370`** (you reviewed `400c29c`).

## Your P1 → the fold

> `np.int64(20260709)` is not a Python `int`, slipped the isinstance blacklist, and parsed as
> epoch nanoseconds → 1970 → `FUTURE.TI` through the 2025 cutoff again. Fix with a POSITIVE
> allowlist before parsing, not a wider blacklist.

Folded exactly as prescribed: `_parse_fetched_at` is a positive allowlist — **only** `str`
(parsed via `pd.Timestamp`, failure/NaT = refuse) and `datetime.datetime`/`pd.Timestamp` values
are accepted; every other type (every NumPy scalar, `int`/`float`/`bool`, `None`, `NaT`) is
source failure. Parsing is **element-wise only** — the column-level `pd.to_datetime` that created
the epoch path is gone entirely, so no numeric can ever reach a parser.

Your two boundary rulings folded with it:
- **tz-aware values** normalize to Asia/Shanghai naive (the NF canon convention) — the
  tz-vs-naive-cutoff `TypeError` is dead, and the instant is correct;
- **bare `datetime.date` refuses** — a midnight assumption is not PIT proof against an intra-day
  cutoff.

Regressions pinned: your probe verbatim (`np.int64` row + valid `pd.Timestamp` row, both orders)
across four NumPy scalar types (`int64`/`int32`/`uint64`/`float32`), no `FUTURE.TI` anywhere;
tz-aware ISO string → `mapped` at the CN-naive instant; bare date → `source_unavailable`.
Verified **fail-pre-fix** by stashing (1 failed pre-fix). **25** M1 tests + full
`ai_research_dept` suite **941** green.

## Files (pin to `c399370`)

- https://raw.githubusercontent.com/henrydan111/quant-system/c399370/workspace/research/ai_research_dept/engine/macro_exposure.py
- https://raw.githubusercontent.com/henrydan111/quant-system/c399370/workspace/research/ai_research_dept/tests/test_macro_exposure.py

## Confirmation questions

1. Is the positive allowlist now complete and correctly bounded — anything it wrongly refuses
   (a legitimate store shape) or still wrongly admits?
2. **Verdict:** SOUND-TO-PROCEED (M1 closed → M2, the macro flash section; mapping YAMLs still
   queued for the user's content pass) or a specific residual gap.
