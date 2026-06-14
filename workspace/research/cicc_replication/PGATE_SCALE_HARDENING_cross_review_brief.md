# P-GATE gate-at-scale hardening — cross-review brief (for GPT 5.5 Pro)

> 2026-06-14. In R1/R2 you flagged 4 items as "DEFERRED — required before the next live CICC
> publish-to-candidate sub-wave AT SCALE" (not blocking the canary, since nothing is promoted).
> I have now implemented all 4. This brief asks you to verify them and **hunt for new fail-open
> holes** — gate-at-scale is exactly where the earlier rounds found that "absence" silently passed.
>
> Web-based — repo `henrydan111/quant-system`, branch `report-rc-registration`, commit `d683eed`.
> - governance store + ledger + OOS assertion: https://github.com/henrydan111/quant-system/blob/report-rc-registration/src/alpha_research/factor_registry/replication_governance.py
> - gate adjudicator + handler: https://github.com/henrydan111/quant-system/blob/report-rc-registration/src/research_orchestrator/factor_lifecycle_steps.py
> - sealed-OOS handler guard: https://github.com/henrydan111/quant-system/blob/report-rc-registration/src/research_orchestrator/validation_steps.py
> - factor_master stamp columns + setter: https://github.com/henrydan111/quant-system/blob/report-rc-registration/src/alpha_research/factor_registry/store.py

## What was implemented (verify each)

**F11 — append-only linkage ledger.** New `CohortFactorLinkageStore` (parquet + file_lock): every
(cohort, factor) link event (`linked`/`relinked`/`unlinked`) is APPENDED (never edits a prior row),
binding the factor's `definition_hash` at link time. `catalog_factor_id` is excluded from the
manifest sha, so the freeze itself can't detect a DROPPED link — this ledger is the durable record +
the basis for F3. `active_links` = latest event per pair that isn't `unlinked`.

**F3 — reverse stamp + ≠1-row fail-closed.** Added `replication_cohort_id`/`replication_handbook_id`
to `factor_master` (+ `set_replication_link` setter; `_apply_schema` auto-fills the columns, no
migration). At gate time, every factor that resolves to EXACTLY ONE manifest row is stamped + a
ledger `linked` event is appended. `_cohort_ceiling` now takes `is_cohort_linked` (= has a stamp OR
an active ledger link): **a linked factor that resolves to 0 manifest rows raises (fail closed)** —
a dropped/forgotten link no longer silently reverts to "non-cohort, unguarded promotion" (previously
`matches==0 → return None`). An UNLINKED factor with 0 matches still returns None (genuinely
non-cohort; gate unchanged).

**F9-full — per-factor declared-domain adjudication.** Removed the `primary_claim_universe != gate
universe → raise` hard-fail. The handler now enumerates EVERY active-claim universe a factor carries
(univ_all primary + others), adjudicates each via `_cohort_ceiling(fid, domain)` (matrix evidence is
already keyed by `universe_id`), and persists a `ReplicationGovernanceRecord` PER domain
(resolve-but-label). **The candidate PROMOTION decision still uses ONLY the univ_all primary**;
non-primary domains are recorded, not promoted.

**OOS exact-quarantine (R1 F9).** `_cohort_ceiling` injects the trading calendar
(`_oos_trade_calendar`, lru-cached, fail-safe → `()` on load failure so the quarantine stays
approximate, never falsely exact) into `compute_oos_quarantine_start`, so persisted records now carry
`oos_quarantine_approximate=False` with the EXACT trading-day boundary. New
`assert_oos_quarantine_satisfied` raises `OosQuarantineError` if `approximate=True` OR the OOS window
starts before the quarantine. Wired into `handle_validation_event_backtest_oos` via
`_assert_cicc_oos_quarantine` — **before the seal claim** (a refused run never spends the seal slot);
it looks up governance records by the prescription's component `factor_name`s; a no-op for non-cohort
prescriptions (store-load guarded; the assertion itself never swallowed).

## Empirical demonstration (live re-gate of the 10 cohort factors)

```
governance record:  comp_cicc_profit / qual_cfoad / qual_roed  →  oos_quarantine_start 2023-02-09(approx)
                    → 2023-02-13  approximate=False    (exact 25-trading-day boundary after 2022-12-31)
F11 ledger:         10 rows, all 'linked', each binding handbook_id + the factor's full definition_hash
F3 stamps:          10 factors stamped replication_cohort_id=cicc_fundamental_handbook_v1 + handbook_id
ceilings unchanged: all candidate_ceiling (6 short_oos_power_floor_fail; 4 +proxy_approx) — nothing promoted
```
Tests: **112 pass** (lifecycle + governance + registry parity) + the new units (F11 append-only/
unlinked/relink/definition-bound; OOS assertion ×5 incl. injected-calendar-makes-exact; F3 linked-zero-
match fail-closed; F9-full non-univ_all adjudication). Sweep of the OOS-handler / lock / architecture
tests also green.

## Where I want adversarial scrutiny

1. **F3 gap — "never linked" vs "dropped link".** The fail-closed check protects a factor whose link
   was DROPPED (it was stamped/ledgered on a prior ==1 match, then the manifest lost the
   `catalog_factor_id`). It does NOT protect a factor that SHOULD be CICC but was NEVER successfully
   linked (no stamp/ledger, manifest never had its id) — that's treated as non-cohort. Is "we only
   guard dropped links, not never-created ones" acceptable, or do you want a positive assertion (e.g.
   a factor whose definition_hash matches a known cohort factor's, or a name-convention, must be
   linked)?
2. **F9-full promotion semantics.** I keep promotion on the univ_all primary and only RECORD
   non-primary domains. Is that right, or should a strong non-primary domain be able to independently
   gate/justify the factor-level candidate status? (Lifecycle status is factor-level; domain claims
   are the per-domain labels — so I treated non-primary as resolve-but-label.)
3. **OOS guard coverage.** It fires in `handle_validation_event_backtest_oos`, keyed on
   `prescription.components[].factor_name`. Two questions: (a) is that the right/only OOS-spend
   chokepoint, or can a CICC factor's sealed OOS be spent via another path (e.g. the
   promotion-evidence harness) that bypasses this guard? (b) it asserts EVERY matching governance
   record (univ_all + F9-full extra domains) — the strictest raises; is asserting all of them correct?
4. **New tier `formula_unbuilt_pending_source_transcription`** (APRD): maps to a `blocked` cap
   (`missing_required_field`) but stays a formalization candidate (so the denominator stays 46, unlike
   `not_replicable`). Is a distinct tier the right modeling, or overkill?
5. **Exact quarantine value.** `truth_label_end=2022-12-31` + horizon 20 + embargo 5 → quarantine
   `2023-02-13`. Confirm 20+5 trading days is the right embargo for a daily-rebalanced fundamental
   factor, and that keying the OOS window start ≥ this date is the correct leakage guard.

## Requested verdict

Overall verdict + numbered confirmations/objections, as in prior rounds. Especially: any NEW
fail-open hole introduced by these changes; whether the F3 "dropped-link-only" protection is
sufficient; whether the OOS guard's chokepoint is complete. Nothing is promoted — all cohort factors
remain drafts at candidate_ceiling; the proxies stay hard-capped.
