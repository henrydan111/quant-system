# GPT-5.5 Pro cross-review — R2 (8-quarter factor unlock plan)

**Status:** R1 returned REVISE. All findings folded; re-review requested per CLAUDE.md §10
("apply the findings and re-review until no blocking issue remains").

## What this is

A NON-FORMAL parity-verification campaign on an A-share quant system (果仁/guorn.com = trusted
external benchmark; the LOCAL Tushare+Qlib system is under test). 52 of 56 deployed-campaign factors
reproduce 果仁's top-5/10/20 selection. **4 stay BLOCKED** because they need an 8-quarter (year-ago
TTM / year-over-year) financial-statement lookback that the live Qlib provider does not materialize
(it carries q0..q4 = depth 5). This plan unlocks them via 3 routes, all NON-FORMAL (no publish, no
field_status writes, no registry writes, no OOS spend):

- **Route A** — transient scoped deep-slot build (slot_depth=8, 3 fields, publish=False) → unlocks
  `RnDTTMGr%PY` and `AssetTurnoverDiffPY`.
- **Route B** — PIT-visible 8-quarter share-count sampling → unlocks `SharesAvgGr%PY`.
- **Route C** — direct dividend-ledger aggregation via the already-validated caliber helper → unlocks
  the dividend-aggregate family.

## Live links (report-rc-registration branch — all verified HTTP 200)

- Plan: https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/workspace/research/idea_sourcing/guorn/UNLOCK_8Q_FACTORS_PLAN.md
- Comparator (M2 change): https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/workspace/scripts/guorn_factor_parity.py
- Deep-slot wrapper (M4, new): https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/workspace/scripts/_build_deepslot_8q.py
- Contract — PIT invariants §3.2: https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/CLAUDE.md
  (§3.2 PIT correctness; §6.3 backend-rebuild discipline; §7 research integrity)

## R1 findings and how each was folded

| # | R1 finding | Fold |
|---|---|---|
| M1 | Plan not fetchable (404) | Branch-slip fixed; plan + code now live on `report-rc-registration` (links above all 200). Added SCRIPT_STATUS header + acceptance gates. |
| M2 | Comparator hard-coded the live provider | `guorn_factor_parity.py` now takes `--provider-uri`, threaded into `load_local_factor`+`qlib.init`, with `staged_deepslot` logging. Route A reads the STAGED provider. |
| M3 | Route B PIT anchor (calendar vs disclosure) | Rewrote: q0..q7 anchored to the PIT-visible report sequence, ineligible-if-unannounced, NaN if the chain is incomplete, + a pre-annual-report canary. |
| M4 | Route A wrapper mismatch | Added `_build_deepslot_8q.py` (slot_depth=8, 3 fields, publish=False) with a hard disk/governance preflight (30GB ceiling, refuse-live-provider, refuse-publish). |
| M5 | Asset-turnover denominator unverified | Pre-register BOTH AvgQ(4) and (begin+end)/2; accept only the variant that matches 果仁. |
| M6 | Dividend total-amount share base | Pre-register 5 share-base candidates + unit checks; per-share-yield parity is NOT accepted as proof for a total-denominated ratio. |
| m1 | Top-K not sufficient | Gate now requires pointwise parity AND top-K overlap. |
| m2 | Universe must cover the export | Route A asserts `果仁_export_codes ⊆ touched_symbols`. |
| m3 | ann_date clamp ≠ full PIT for formal | Route C stays NON-FORMAL (direct ledger read); any future FORMAL use must route through the PIT ledger/provider + registration. |

## Highest-risk item to scrutinize (your R1 flag)

> "Route B's fiscal-quarter-date selection: if the eight share samples are anchored to calendar
> quarter-ends rather than PIT-visible reported fiscal periods, the factor leaks undisclosed
> financial-period information."

This is the §3.2 no-lookahead core. Please verify the M3 rewrite actually closes it: the 8 samples
are taken from the report sequence VISIBLE as-of the signal date (anchored on ann_date/f_ann_date
visibility), a quarter is ineligible until its report is announced, the chain returns NaN if
incomplete, and the canary refuses a fiscal quarter-end that would enter the window before its annual
report is disclosed. Is there any remaining path by which an undisclosed period's share count enters
the window?

## Self-review (done before this re-review, per §10)

§3.2 PIT preserved and strengthened (M3); §6.3 disk/governance hardened (M4: scoped + ceiling +
refuse-live + refuse-publish); no publish/registry/field_status writes anywhere (m3); no hedge words.
**Verdict: clean for GPT re-review.**

## Review questions (R2)

1. Is the **Route B PIT anchor** (M3) now leak-free, or is there a residual lookahead path?
2. Does the **Route A wrapper** (`_build_deepslot_8q.py`) adequately guard the 1TB-blowup hazard
   (scoping, ceiling, refuse-live, refuse-publish), and is slot_depth=8 the correct minimum for a
   year-ago TTM leg (q0..q7)?
3. Is the **M2 comparator** change correct — does reading the staged provider via `--provider-uri`
   actually exercise the deep-slot data for Route A, with no silent fallback to the live provider?
4. Are the **M5 dual-denominator** and **M6 share-base** pre-registrations sufficient to avoid a
   false pass, or is a candidate missing?
5. Any remaining blocking issue before execution?
