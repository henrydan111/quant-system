# GPT Cross-Review Request — Macro wave M1 (MS01-MS05 per-stock exposure rows) — Tier-2

Reviewing **one unit**: M1, the exposure-row data layer of the macro fourth-seat wave — the first of
four sub-units (M1 exposure data → M2 macro flash section → M3 macro card assembly → M4 fourth seat
+ chain bump). The macro seat itself is NOT in scope here.

## ⚠ FROZEN REVIEW TIER — Tier-2 (user-assigned at design freeze)

Per CLAUDE.md §10: the tier is set at design freeze and **the reviewer must not escalate it
mid-arc**. Tier-2 = declared-invariant review against ordinary well-formed inputs; no
crafted-object/dunder analysis. The v3 threat-model root-scope rule applies where relevant.

**Commit under review: `5d9a330`** on branch `calendar-unfreeze`.

## Context

Spec source: [NEWS_FLASH_INTEGRATION_v1.md](https://raw.githubusercontent.com/henrydan111/quant-system/5d9a330/workspace/research/ai_research_dept/NEWS_FLASH_INTEGRATION_v1.md)
§6 (macro fourth seat, GPT six-round APPROVE 2026-07-11) + §0d rows m1/m2/M4. The frozen MS row
schema (§0d m1, verbatim): `mapping_id / mapping_version / mapping_sha256 / mapping_status /
exposure_type / exposure_bucket / exposure_value / snapshot_effective_at / ts_code / dimension /
source`; `mapped_no_exposure → exposure_value=null` (never a fabricated 0); THS concepts omitted
when no contemporaneous snapshot exists (M4: never today's members applied to history).

User decisions at design freeze (2026-07-24, recorded in
[NF_UNIT_M1_DESIGN.md](https://raw.githubusercontent.com/henrydan111/quant-system/5d9a330/workspace/research/ai_research_dept/NF_UNIT_M1_DESIGN.md)):
(1) MS04/MS05 curated mappings authored by Claude as v1, **user reviews/edits before freeze** —
your content audit below feeds that same review pass; (2) MS01/MS02 buckets = pool-relative
terciles on D-close metrics; (3) Tier-2.

## What M1 ships

`engine/macro_exposure.py` — `build_ms_exposure_rows(ts_code, day, *, cutoff, pool_metrics,
ths_members, mappings)` → **exactly five rows** (MS01..MS05, fixed order, strict 12-key schema):

| row | dimension | v1 source | key mechanics |
|---|---|---|---|
| MS01 | risk_appetite_fit | pool terciles on `float_mv` + `vol_20d` (D close) | bucket rule = its own versioned hashed asset (`_TERCILE_RULE_V1` descriptor sha256); missing metric → `metric_unavailable`, value null |
| MS02 | liquidity_funding | pool tercile on `turnover_20d` | same rule asset |
| MS03 | industry_concept_prosperity | `industry_as_of` (PIT SW2021 L1) + THS members | THS gate: `fetched_at <= cutoff`; the REAL local snapshot is 2026-07-09, so any 2025 replay day omits concepts (`concepts_omitted=no_contemporaneous_snapshot`) while the PIT industry stays valid |
| MS04 | policy_alignment | curated YAML: SW L1 → policy channels (11-channel enum) | file-byte sha256 into every row; empty list → `mapped_no_exposure` (null); unresolvable industry → `unmapped_industry` |
| MS05 | external_shock_transmission | curated YAML: SW L1 → shock channels (6-channel enum, high/medium sensitivity; **sign-free** — direction is the seat's job pairing M/MF facts) | same governance; `low` sensitivity deliberately unregistered (weak exposure = `mapped_no_exposure`, keeps pairing noise out) |

Also: `load_mapping_asset` (strict schema validation: key_type, registered channels, sensitivity
enum, SW-code keys), `exposure_mapping_bundle_sha256` (the C16b label-bundle hash over all
rule+mapping hashes), status enum fail-closed (`_row` refuses unregistered statuses and any
non-null value on a null-mandated status).

**Input contract (deliberate):** M1 takes a plain `pool_metrics` DataFrame
(`ts_code/float_mv/turnover_20d/vol_20d`) rather than reading the session's card-shaped pv frames —
sourcing those metrics is the M3 assembler's duty; M1 stays pure and testable. `pandas`-level
inputs only; no LLM.

## Declared design decisions (challenge explicitly)

1. **Pool-relative terciles** (user-chosen over absolute thresholds): computed within the ~149-name
   decision pool per D-close metric. Flag any statistical trap you see (ties, tiny pools — <3
   non-NaN values refuse to bucket → `metric_unavailable`).
2. **MS03 status semantics**: when the industry resolves but concepts are snapshot-omitted, the row
   stays `mapped` with `value.concepts=[]` + `concepts_omitted` marker + `snapshot_effective_at=None`
   (the industry face is genuinely mapped). Alternative: a dedicated split status. Is the current
   shape faithful to §0d m1/M4?
3. **Sign-free channels**: both curated mappings carry NO direction (a coal producer and a coal
   consumer are both "energy-price-linked"); the macro seat scores direction by pairing the M/MF
   fact with the exposure row. Right boundary?
4. **The v1 mapping CONTENT** (the user's own review pass runs alongside yours — your judgment
   feeds it): audit the two YAMLs as research content. Named judgment calls: banks =
   [monetary_credit, financial_regulation, property_policy]; autos = [consumption_stimulus,
   energy_transition]; 综合/传媒/国防军工/银行/地产 have EMPTY shock-channel lists; 电子 =
   [global_supply_chain:high, export_demand:high, fx_sensitivity:medium]. Flag wrong/missing
   industry→channel assignments — mapping edits are cheap now (v1 unfrozen), a version bump later.

## Files (pin to `5d9a330`)

- https://raw.githubusercontent.com/henrydan111/quant-system/5d9a330/workspace/research/ai_research_dept/engine/macro_exposure.py
- https://raw.githubusercontent.com/henrydan111/quant-system/5d9a330/workspace/research/ai_research_dept/engine/macro_mappings/ms04_policy_channels_v1.yaml
- https://raw.githubusercontent.com/henrydan111/quant-system/5d9a330/workspace/research/ai_research_dept/engine/macro_mappings/ms05_shock_channels_v1.yaml
- https://raw.githubusercontent.com/henrydan111/quant-system/5d9a330/workspace/research/ai_research_dept/tests/test_macro_exposure.py
- design: https://raw.githubusercontent.com/henrydan111/quant-system/5d9a330/workspace/research/ai_research_dept/NF_UNIT_M1_DESIGN.md

## Self-review

Clean for GPT. Premise checks done before design: `industry_as_of` return format verified
(`801080.SI` for 688981.SH on 2025-01-27); the authoritative 31-industry SW2021 L1 list pulled from
`data/universe/industry_sw2021_members` (mapping keys verified against it, exhaustive-coverage
test); the real `ths_members.parquet` inspected (71,868 rows, single `fetched_at=2026-07-09`
snapshot — which makes the M4 omission rule mechanically decidable). PIT: the only date-bearing
reads are `industry_as_of` (PIT by construction, its own tested contract) and the THS gate
(`fetched_at <= cutoff` — a future snapshot can never inform a past decision). Tests: **12** M1
(incl. 31-L1 exhaustive mapping coverage, the future-snapshot omission pin, fail-closed
unmapped/unavailable paths, determinism) + full `ai_research_dept` suite **928** green.

## Review questions

1. **Schema fidelity**: does every row match the frozen §0d m1 schema and status semantics —
   anything the M3 assembler or the macro seat's pairing gate will need that a row cannot express?
2. **PIT / no-lookahead**: any path where a future-dated fact (THS snapshot, D-close metric,
   mapping content) informs a past decision day? Note `pool_metrics` is caller-supplied — M1's
   contract says D-close of the decision day; is documenting that contract enough at Tier-2, or do
   you want a mechanical guard here rather than in M3?
3. **The four declared design decisions**, incl. the mapping-content audit (question 4 above).
4. **Governance**: is file-byte sha256 per mapping + the bundle hash the right C16b registration
   surface; anything unversioned that could drift silently (e.g. the tercile rule descriptor —
   hashed; the SW membership parquet itself — governed upstream)?
5. **Verdict**: SOUND-TO-PROCEED (to M2, the macro flash section) or specific in-tier findings.
