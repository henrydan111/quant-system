# Macro wave M1 — MS01-MS05 per-stock exposure rows (design draft)

**Review tier:** proposed Tier-2 (data-layer plumbing; mapping assets are versioned + hashed;
fail-closed omission semantics). *Tier is a user call at freeze.*

**Status:** DRAFT 2026-07-24 after premise checks. Open decisions at the bottom need the user
before freeze. Spec source: [NEWS_FLASH_INTEGRATION_v1.md](NEWS_FLASH_INTEGRATION_v1.md) §6 +
§0d m1/m2/M4 rows.

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

## The MS row schema (frozen by §0d m1 — verbatim)

Every row: `mapping_id / mapping_version / mapping_sha256 / mapping_status / exposure_type /
exposure_bucket / exposure_value / snapshot_effective_at / ts_code / dimension / source`.
`mapped_no_exposure → exposure_value=null` (never a fabricated 0). Absence rendering carries
`confirmed_absent_through=<exact channel cutoff>` — wording must never imply whole-evening
coverage.

## v1 exposure sources per dimension (proposal)

| row | dimension | exposure_type | v1 source | PIT basis |
|---|---|---|---|---|
| MS01 | risk_appetite_fit | style_bucket | size (float-mv tercile vs pool) + volatility bucket from D-close pv | D close |
| MS02 | liquidity_funding | liquidity_bucket | turnover-rate + free-float-mv bucket from D-close pv | D close |
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
