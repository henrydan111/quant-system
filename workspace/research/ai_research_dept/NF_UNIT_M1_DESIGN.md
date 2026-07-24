# Macro wave M1 — MS01-MS05 per-stock exposure rows (design, FROZEN)

**Review tier:** **Tier-2** (user-assigned 2026-07-24).

**Status:** FROZEN 2026-07-24 — user decisions recorded: (1) MS04/MS05 curated mappings =
**Claude drafts v1 YAML, user reviews/edits BEFORE the GPT arc** (mapping sha256 into the
registry; content change = version bump); (2) MS01/MS02 buckets = **pool-relative terciles** on
D-close metrics (stable to universe drift); (3) Tier-2. Mapping keys = SW2021 **L1 codes**
(`industry_as_of` returns e.g. `801120.SI` — verified). Spec source:
[NEWS_FLASH_INTEGRATION_v1.md](NEWS_FLASH_INTEGRATION_v1.md) §6 + §0d m1/m2/M4 rows.

## Premise checks (done)

- **SW industry, PIT-correct**: `src/data_infra/provider_metadata.industry_as_of(ts_code, as_of,
  level)` exists — the SW2021 industry a stock belonged to ON the date. ✓ usable for any day.
- **THS concepts = CURRENT snapshot only**: `data/reference/ths_concept/ths_members.parquet`
  (71,868 rows; `ts_code`(board)/`con_code`/`con_name`/`fetched_at=2026-07-09T13:53`). Per the
  frozen M4 rule: a replay day BEFORE the snapshot has no contemporaneous membership → concept
  tags are **omitted** (`mapping_status=no_contemporaneous_snapshot`), never today's members
  applied to 2025; forward days ≥ snapshot date use it with
  `snapshot_effective_at = fetched_at`.
- **Style/liquidity inputs**: the session's pv pack carries D-close per-stock fields (exact
  column set to re-verify at implementation); §0a evening mode makes D-close inputs legal.
- **MS04/MS05 mapping tables DO NOT EXIST** — policy-channel and external-shock-channel
  exposures need **curated, versioned mapping assets** (the biggest research-content decision;
  see open decisions).

## Round-1 fold record (2026-07-24, 3×P1 + 2×P2, zero declines)

- **P1#1 THS snapshot coherence**: `select_ths_snapshot` picks the UNIQUE latest
  `fetched_at <= cutoff` snapshot and uses only that snapshot's complete membership — a mixed
  old/future frame can no longer leak future concepts, and the result is order-independent
  (both orders pinned).
- **P1#2 C16b identity completeness**: `exposure_mapping_bundle_sha256` hashes a **role-labelled
  canonical JSON** (`tercile_rule` / `ms03_rule` / `policy_mapping` / `shock_mapping` /
  `ths_snapshot{effective_at, content_sha256}`) — role swaps and snapshot-content changes move the
  bundle; MS03 rows carry the selected snapshot's `ths_content_sha256` in their value.
- **P1#3 all-or-nothing metrics**: any required metric that cannot bucket (NaN / <6 observations /
  <3 distinct / degenerate distribution) makes the WHOLE MS01/MS02 row `metric_unavailable` with
  null bucket/value — partial exposures are dead.
- **P2#1 schema amendment recorded**: the M1 row = the frozen 11 §0d fields **+ `row_id`** (an
  explicit M1-layer addition for M2/M3 pairing; not "verbatim §0d"). MS03's omission semantics
  (industry stays `mapped`, concepts omitted via the value marker) are the CONTRACT — the status
  enum no longer lists an unused `no_contemporaneous_snapshot` status. MS02 uses `turnover_20d`
  only (the earlier "free-float-mv" phrasing was wrong).
- **P2#2 tercile rule frozen into the hashed descriptor**: `min_observations=6`,
  `min_distinct=3`, `tie_rule=le_boundary_falls_lower`, degenerate distribution = unavailable.

**FROZEN M3 OBLIGATIONS** (recorded here so the assembly unit inherits them):
(a) M3 supplies `pool_metrics` and MUST seal the pool's as-of + content identity (M1's date
strings are contract documentation, not proof); (b) M3 seals the selected THS snapshot identity
(`effective_at` + `content_sha256`, via `select_ths_snapshot` / the bundle hash with
`ths_snapshot=`) into the macro-card snapshot; (c) absence RENDERING
(`confirmed_absent_through=<exact channel cutoff>`) is M3's rendering duty.

**Open note for the user's mapping edit pass** (reviewer suggestion, non-blocking): consider
adding `fx_sensitivity: medium` to 交通运输 (airline USD debt/fuel) and 家用电器 (export revenue)
in the MS05 map.

## The MS row schema (frozen by §0d m1 + the recorded `row_id` amendment)

Every row — the frozen 11 §0d fields PLUS the M1-amendment `row_id` (12 keys total, matching the
implementation's `MS_ROW_KEYS` exactly; re-review#2 P2#1): `row_id / mapping_id /
mapping_version / mapping_sha256 / mapping_status / exposure_type / exposure_bucket /
exposure_value / snapshot_effective_at / ts_code / dimension / source`.
`mapped_no_exposure → exposure_value=null` (never a fabricated 0). Absence rendering carries
`confirmed_absent_through=<exact channel cutoff>` — wording must never imply whole-evening
coverage (an M3 rendering duty).

## v1 exposure sources per dimension (as implemented)

| row | dimension | exposure_type | v1 source | PIT basis |
|---|---|---|---|---|
| MS01 | risk_appetite_fit | style_bucket | `float_mv` + `vol_20d` pool terciles from D-close metrics | D close |
| MS02 | liquidity_funding | liquidity_bucket | `turnover_20d` pool tercile from D-close metrics (**turnover only** — the earlier "turnover-rate + free-float-mv" wording was wrong; re-review#2 P2#2. float_mv already carries the size face in MS01; a future second MS02 metric = tercile-rule version bump) | D close |
| MS03 | industry_concept_prosperity | industry_tag + concept_tags | `industry_as_of` (PIT) + THS members (snapshot-gated) | PIT / snapshot |
| MS04 | policy_alignment | policy_channel | **curated** SW-industry→policy-channel mapping asset (versioned YAML, sha256 into the registry) | mapping version |
| MS05 | external_shock_transmission | shock_channel | **curated** SW-industry→shock-channel mapping (export / commodity-input / FX / supply-chain sensitivity) | mapping version |

All five rows are emitted per (stock, day) by one builder `build_ms_exposure_rows(...)`; a
dimension with no resolvable source emits `mapped_no_exposure` (null value) or the omission
status — never silence.

## Open decisions (user, before freeze)

1. **MS04/MS05 curated mapping content** — authored by me as v1 YAML assets (SW L1/L2 →
   channels), then user-reviewed before the freeze? Or user supplies/edits the mapping directly?
   (They are research content: which industries are export/commodity/FX-sensitive, which policy
   channels exist.)
2. **MS01/MS02 bucket definitions** — proposal: terciles within the decision pool (~149 names)
   per D-close metric; alternative: fixed absolute thresholds. Pool-relative is stable to
   universe drift; absolute is more interpretable.
3. **Tier** — proposed Tier-2.
