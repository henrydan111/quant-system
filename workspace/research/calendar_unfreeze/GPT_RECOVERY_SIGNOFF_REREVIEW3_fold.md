# GPT §10 re-review #3 — fold of re-review #2's two held findings

Independent GPT‑5.5 Pro reviewer. Re-review #2 cleared B1/B2/B3/M2/M3/M4/MINOR and held on exactly two
FACTUAL points. Both were verified against the retained probe before fixing. This is the fold.

Repo `https://github.com/henrydan111/quant-system` · Branch **`calendar-unfreeze`** · HEAD **`9d2b750`**
Raw base: `https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/`
Files: `…/workspace/configs/recovery_endpoint_contracts.yaml`, `…/scripts/raw_recovery_coordinator.py`.
Probe cited: `…/workspace/outputs/bucket_a_pretest_20260607T173215Z.json`.

## Held finding 1 — B4 cap classification (page_limit VALUE safe, PROSE was wrong)
I verified the probe: `fina_mainbz_vip.rows == 10000 (cap_hit=false)`, `top10_floatholders_byperiod.rows
== 6000 (cap_hit=false)`. Fixes:

| endpoint | before | after | basis |
|---|---|---|---|
| fina_mainbz | 100 (base-endpoint doc cap — WRONG endpoint) | **10000** | probe VIP page (10000, cap_hit=false); doc-81's 100 is the single-stock base endpoint, not `_vip` |
| top10_floatholders | 5000 ("单次≤5000") | **6000** | probe page (6000); doc-62's 5000 is a 积分 tier, not a row cap |
| adj_factor 5000, income/bs/cf 2000, income_vip/cf_vip 10000, repurchase 2000 | prose said "单次≤" / "doc cap" | **values unchanged; prose relabelled** "DEFENSIVE CLIENT CHUNK / fetcher page size, NOT a doc-stated cap" | each ≤ true cap → safe; the docs state a 积分 tier or a fetcher limit, not a 单次 row cap |
| stk_limit 5800, block_trade 1000, disclosure_date 3000, pledge_stat 1000, report_rc 3000 | (unchanged) | (unchanged) | these ARE genuine doc-stated 单次 row caps — wording kept |

I accept your point that `contract_errors` cannot distinguish a real cap from a wrong one (`page_limit=1`
passes) — the validator checks internal consistency, not vendor truth; the page_limit correctness is a
human/probe judgment, now recorded honestly in the prose.

## Held finding 2 — fina_mainbz PIT proxy (was signed "anchor ann_date")
Probe-confirmed the `fina_mainbz_vip` response columns are `ts_code, end_date, bz_item, bz_code,
bz_sales, bz_profit, bz_cost, curr_type` — **no `ann_date`, no `update_flag`**. The signed `pit_anchors`
now states exactly this: visibility is a LOWER-BOUND proxy = the owning report's income `ann_date`
(build_aux_pit_ledgers join `.min()`); a later segment revision can be backdated → **RAW-RECOVERY ONLY,
formal PIT promotion QUARANTINED pending a revision-timing probe; `raw_fetch_ts` is the first-seen
floor**. (The `raw_fetch_ts` universal derived stamp is already retained by the ledger.)

## P2 (density comments) — also corrected
The coordinator notes for cyq_perf / income_quarterly / cashflow_quarterly said output density "is
enforced"; changed to "MUST BE enforced … NOT yet implemented; a promotion precondition" so the code no
longer overstates current protection.

## State
31 signed (`contract_errors == []` from generator AND re-loaded from disk); `--plan` = 30 families
`BLOCKED(UNBOUND callable)` + `A07/indicators BLOCKED(contract:fina_indicator_vip)`; recovery battery
**171 passed**. No Tushare call; fetch exits 3.

## Questions
1. Do the two reverts (fina_mainbz→10000, top10→6000) + the client-chunk relabelling discharge B4?
2. Does the fina_mainbz `pit_anchors` rewrite (raw-only, quarantined, lower-bound proxy) discharge the
   PIT proxy finding for the SIGN-OFF (formal promotion remains separately gated)?
3. Anything else blocking the all-endpoint sign-off, or is the gate open for adapters (with the density
   output-check and the fina_mainbz revision-timing probe as tracked promotion preconditions)?
