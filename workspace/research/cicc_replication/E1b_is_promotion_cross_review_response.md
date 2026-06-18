# CICC Wave E1b — IS-gate cross-review response & triage (GPT 5.5 Pro)

> 2026-06-17/18. GPT reviewed the E1b IS-gate at `1a08cdd`: **CHANGES REQUIRED before `--live`** — no
> objection to the 35-factor promotion; the blockers were ORDERING + SET-INTEGRITY. All 3 folded in +
> verified. GPT pre-committed: "I would approve `promote_e1b_is_candidates.py --live` after this packet
> is green." The packet is now green.

## Triage

| # | Finding | Verdict | Action |
|---|---|---|---|
| 1 | **Blocking** — P-GATE / manifest correction must PRECEDE the candidate status change (roadmap makes P-GATE a hard prerequisite); manifest still had `shadow_line` | **DONE** | (a) [expand_e1b_manifest.py](../../scripts/expand_e1b_manifest.py): replaced the 7 chart-16 template rows with **36 factor-level rows** (`catalog_factor_id` each), **dropped `shadow_line`** (inline Greater/Less), `sign_conditional_std` only on the 6 down/up_std rows; re-pinned `manifest_sha 3e07e048→66098014`. (b) Ran **P-GATE `--live`** for all 36 → 36 `ReplicationGovernanceRecord`s, all `candidate_ceiling` (`short_oos_power_floor_fail`), **0 status promotions**. |
| 2 | **Blocking** — driver promoted any `vol_*` passer (footgun); needs an expected-family guard | **DONE** | Set-integrity guard: `EXPECTED_E1B` derived DETERMINISTICALLY from the catalog (36 ids, independent of results.jsonl); asserts `set(rows)==EXPECTED_E1B` (no stray / no missing), `rule_blocked=={vol_down_std_20d}`, `passers==EXPECTED_E1B−blocked`. Fail-closed. |
| 3 | **Blocking** — IS status must agree with an existing P-GATE candidate_ceiling | **DONE** | `_assert_pgate_ceilings` preflight: every factor being promoted must carry a `candidate_ceiling` ReplicationGovernanceRecord, else refuse — enforces the ordering. PASSED in the dry-run. |

## Accepted (no further change)

- Promote all 35 with the cohort-redundancy caveat (resolve-but-label; ~4-6 orthogonal representatives downstream). `expected_direction='inverse'` (low-vol anomaly). `vol_down_std_20d` correctly blocked (sign 0.64 < 0.70). Do NOT count as 35 independent discoveries.

## Green packet (GPT's pre-approval checklist — all met)

```
manifest:  shadow_line_removed=true · all 36 catalog_factor_id linked=true · sign_conditional_std only on down/up_std · sha 66098014
pgate:     live_run_done=true · records_written=36 · candidate_ceiling=36 · short_oos_power_floor_fail=36 · status_promotions=0
is_dryrun: rows_evaluated=36 · passers=35 · blocked={vol_down_std_20d: sign<0.70} · unexpected_vol_rows=0 · missing=0 · attached=35 · skipped_drift/unknown=[] · pre_status_all=draft · expected_direction_all=inverse
```

Tests: replication_governance 57 pass; manifest reloads (sha 66098014, 80 rows), every E1a/E1b factor resolvable.

Awaiting the final APPROVE → backup → `promote_e1b_is_candidates.py --live` → verify 35 transitions → live provenance.
