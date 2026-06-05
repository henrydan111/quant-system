# DESIGN Cross-Review (for GPT) — factor expansion on newly-unlocked A-share data

You are reviewing a **design** (no catalog/registry change yet) to build the first factors on 8
newly-`approved` A-share datasets, and to route the best ones to registry `approved` via a **fresh
sealed OOS**. No repo access — everything needed is embedded. Find any integrity/leakage hole or
unsound step. A NO-GO with a specific mechanism beats a GO. Attack §4 hardest (the clean-OOS claim).

## 0. System context you need

- **Factor lifecycle:** `draft → candidate → approved`. `candidate` = passed an IS-only walk-forward
  gate (2014-2020). `approved` = passed a promotion gate requiring an INDEPENDENT, PIT-correct,
  single-shot **sealed OOS** reproduction (the OOS window is run ONCE, pre-registered, no peeking).
- **Registry today:** 87 `candidate` + 84 `draft` + 6 `approved`. The 6 approved are sealed-OOS
  winners (a 13-factor set was frozen on IS, then the 2021-01..2026-02 OOS was spent ONCE). The 87
  candidates are `oos_informed_backfill` — their SELECTION used full-window 2021-26 knowledge, so
  that window is BURNED for them; they cannot reach `approved`.
- **The sealed-OOS mechanism:** a `HoldoutSealStore` records a one-time "claim" keyed by the
  FrozenSelectionSet hash (the exact frozen factor set). A different factor set → a different hash →
  an independent claim. The calendar is FROZEN at 2026-02-27 (system-build phase; no data beyond).
- **PIT enforcement:** every `$field` in a factor expression must sit in a `Ref(...,1)` frame (lint-
  enforced). The data layer (`qlib_windowed_features` + `ResearchAccessContext`) blocks reads outside
  an allowed window during formal/OOS stages.

## 1. What just unlocked

A data-governance review promoted 8 datasets `quarantine/pending_review → approved`: `moneyflow`
(capital flow, 16 order-size buy/sell components), `margin_detail` (5 balance fields), `hk_hold`
(northbound `$ratio`), `top_list`/`top_inst` (龙虎榜), `block_trade` (大宗), `cyq_perf` (筹码),
`stk_holdertrade`. **None of the 177 catalog factors uses any of them.** The review was a DATA-QUALITY
audit (coverage %, value sanity, provider parity, PIT anchor) — it did NOT compute any factor's
return/predictive performance.

## 2. The design (build the first factors on this data)

- ~15 candidate factors, all `Ref(...,1)`-wrapped, smoke-confirmed in the compute path. Tiers by IS
  coverage: **Tier 1** moneyflow + margin (daily-dense, full IS 2014-2020) — main-force net-imbalance,
  retail-pressure (contrarian), xlarge concentration, flow acceleration; margin-balance growth,
  short-interest ratio, financing-buy intensity, margin/mktcap. **Tier 2** 龙虎榜 + 大宗 (sparse
  events — NaN on non-event days → need recency/decay construction, open question). **Tier 3** cyq
  (2018+) + northbound (2017+) — short IS, lower-confidence.
- moneyflow's `net_mf_amount`/`net_mf_vol` are AVOIDED (opaque vendor nets that don't reconcile from
  the 16 components — a documented review finding); factors use the 16 component fields.
- **Process:** sandbox build → IS-2014-2020 discovery screen (IC/RankICIR/monotonicity/decay/turnover,
  bar pre-set BEFORE looking) → survivors to `draft` → `factor_lifecycle` IS-only gate → `candidate` →
  (later, separate) sealed OOS on 2021-26 → `approved`.

## 3. The claimed advantage

Unlike the 87 burned candidates, these NEW factors — designed purely on IS 2014-2020 — are claimed to
have an **unspent 2021-26 sealed OOS** available (new FrozenSelectionSet hash → independent seal
claim), so they can reach genuine `approved`.

## 4. The question I most want you to attack — is the "clean OOS" real?

Three distinct ways the clean-OOS claim could be unsound; please rule each in/out:

1. **Window-level reuse / OOS-as-finite-resource.** The 2021-26 window was ALREADY spent once (the 6
   sealed-OOS winners). The seal mechanism keys on the frozen-set hash, so a NEW factor set gets a NEW
   claim — mechanically permitted. But is running a SECOND independent sealed test on the SAME calendar
   window (for different factors) statistically legitimate, or does the project incur **window-level
   multiple testing** (test enough different factor sets against the same 2021-26 window and some pass
   by chance)? Is there a principled budget here (e.g. Bonferroni across all sealed tests ever run on
   this window), or is each genuinely-independent frozen set a fair single-shot? This is the decision
   I'm least sure of.
2. **Data-QA-touched-2021-26 contamination.** The gated-data review examined the new datasets' COVERAGE
   + VALUE SANITY across 2021-2026 (e.g. found the margin `.BJ` negatives in 2024, the hk_hold 2026
   gap). It did NOT compute any factor's RETURNS over 2021-26. Does inspecting the data's QUALITY (not
   returns) over the OOS window contaminate a future sealed OOS for factors built on it? My claim: no —
   leakage is about using OOS OUTCOMES (returns/predictive perf) to select; data-quality QA is
   orthogonal. Counter?
3. **IS-only discipline is the load-bearing assumption.** The whole advantage evaporates if 2021-26
   factor performance is examined during design/screening. The process is IS-2014-2020-only until the
   sealed run. Is "discipline + the ResearchAccessContext window guard" enough, or should the sealed-OOS
   claim be made (frozen) BEFORE the IS screen even runs, to structurally prevent peeking?

## 5. Other questions

4. **Multiple testing within the IS screen** (~15 candidates): is "pre-set bar + economic prior +
   monotonicity + decay + the gate's yearly-sign-consistency" sufficient, or do you want an explicit
   correction / a held-out IS sub-period?
5. **Sparse-event construction (Tier 2):** building recency/decay/count signals from NaN-on-non-event-
   day fields — any leakage trap (e.g. forward-filling an event across days that peeks)? Or defer Tier 2?
6. **Daily-outcome PIT:** all new fields are same-day outcomes (knowable at close T) → `Ref(...,1)`.
   Sufficient, or any field where even `Ref(...,1)` is too aggressive (e.g. margin balances disclosed
   T+1 after close)?
7. **Scope:** Tier 1 first (moneyflow+margin) as the IS screen — right call, or include Tier 2/3 now?

## 6. Verdict requested

GO to build Phase 1 (Tier-1 IS-2014-2020 discovery screen) — with any required changes (e.g. "claim the
seal before screening", "Bonferroni the window", "defer Tier 2") — or NO-GO with the specific integrity
gap. The build is IS-only; the sealed OOS is a separate, later, single-shot gate.
