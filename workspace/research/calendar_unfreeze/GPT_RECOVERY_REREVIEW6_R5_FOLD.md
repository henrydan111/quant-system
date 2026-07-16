# GPT 5.5 Pro — re-review #6: the re-review-#5 REWORK fold (recovery foundations)

**Branch pushed:** `calendar-unfreeze` @ `0335540`. **Scope: the DELTA since `8ddd399`** — your #5 verdict
(3 BLOCKERs + 2 MAJORs + 1 MINOR) folded. Still NO Tushare fetch (`--fetch` exits 3), no adapters, all
contracts unsigned. This gates whether contract sign-off may finally open.

## Every #5 finding was real — verified before folding, not argued with

I reproduced or code-confirmed each one first. Notably my prior self-review said "clean for GPT" and was
**wrong**: the broker did not close the TOCTOU it claimed to, and my "47 tests across four independent
batteries" was an artifact of import order (the ledger suite failed collection alone). Both corrected.

| # | Finding | Fold | Commit |
|---|---|---|---|
| F1 BLOCKER | validated a path, wrote another via `open(target)`; junction swapped in the gap escaped the root; hard-linked leaf not refused | writes are **handle-relative** (`NtCreateFile` + `OBJECT_ATTRIBUTES.RootDirectory` off a held parent handle — no pathname is ever re-walked); leaf opened **non-truncating** (`FILE_OPEN_IF`) → refuse reparse **or `nNumberOfLinks>1`** → *then* truncate | `8e7a6df` |
| F5 BLOCKER | `replay()` keyed on family alone → adopted a foreign run's `SWAPPED`; `SWAPPED`⇒DONE regardless of facts; destinations not broker-protected; `FamilyPlan` uncontained; `promote_all` never wrote the sentinel | run-scoped `replay(run_id)`; immutable **plan-hash binding** + journalled `expected` paths checked; `SWAPPED` requires facts **and re-hashes live vs the frozen manifest on resume**; paths contained under `data_root` + the two top-level staging areas; incoming writes go through the broker; **`promote_all` arms the sentinel** (left armed; cleared only by an explicit human step) | `8e7a6df` |
| F2 BLOCKER | receipts read without re-hash (replaced receipt verified); generic `contract_terminal` certified a FULL final page; `baseline_dups=True` = unlimited excess, silently dropped; `confirmed_empty` counted attempts only | every receipt **re-read and re-hashed** (+ row count + request binding); **typed terminal proofs** — `last_partial` (row_count **strictly <** limit), `empty_terminal` (==0), `single_page_contract` (limit==0 ∧ exactly one page) — generic escape **deleted**; **natural-key dups always refuse** + declared `max_content_dups` int bound; `confirmed_empty` now demands a structurally valid terminal request | `686cd9c` |
| F3 MAJOR | keys not checked against the docs/production; dividends omitted `record_date`/`ex_date`/`pay_date`; statements omitted `ann_date`; `report_rc`/event keys unproven | checked against **`pit_backend.DATASET_SPECS`** (production natural keys) — all three confirmed and fixed; event families now key on a **lossless `row_payload_digest`** (per your guidance: the docs establish no transaction id); **anti-drift test** binds all 21 mapped families to the production keys; `baseline_dups` bool → `profile_key_dups_expected` + explicit `max_content_dups` | `16f3bdb` |
| F4 MAJOR | doc not proven to belong to the declared endpoint; global derived allowlist usable by any endpoint | `parse_doc_identity` extracts each doc's own `doc_id=` + `接口：<api>`; wrong-API doc **refused** (probe: a valid top_inst doc cited for `moneyflow`); all **32** source endpoints verified to resolve to a declaring doc; derived fields now **endpoint-scoped** with declared provenance (`report_rc_payload_digest` unusable on `daily`) | `0335540` |
| MINOR | suites not independent | module registered in `sys.modules` pre-exec; each suite verified **standalone**: broker 9 / ledger 15 / coordinator 23 / promotion 25 = **72** | `8e7a6df` |

**Proof the F1 probe has teeth** (not a vacuous test): under the identical raced swap, the OLD path
(`validate_ancestry` → `open(target,"wb")`) wrote `outside\f.txt`; the NEW path refuses and no file
escapes. The probe races the swap in exactly as `validate_ancestry` returns and asserts the window armed.

## Raw links (`calendar-unfreeze` @ `0335540`)

- Broker: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/recovery_write_broker.py
- Ledger: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/recovery_ledger.py
- Coordinator (matrix + contract gate): https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/raw_recovery_coordinator.py
- Promotion SM: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/recovery_promotion.py
- Tests: .../tests/data_infra/{test_recovery_write_broker,test_recovery_ledger,test_raw_recovery_coordinator,test_recovery_promotion}.py
- Production PIT keys I bound the matrix to: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/src/data_infra/pit_backend.py
- Plan: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/calendar_unfreeze/RAW_STORE_RECOVERY_PLAN.md

## Review questions — please attack the FIXES

1. **Broker.** Is the `NtCreateFile`/`RootDirectory` chain genuinely un-redirectable? Any residual escape:
   a component swapped *between* two links of the handle chain; `OBJ_CASE_INSENSITIVE` / 8.3 short-name
   aliasing; the `msvcrt.open_osfhandle` fd taking ownership (double-close / leak on the error paths);
   `FILE_OPEN_IF` creating a 0-byte file before the hard-link check refuses; ADS (`file:stream`) names.
2. **Promotion.** With run-scoped replay + plan-hash binding + facts-checked `SWAPPED` + live re-hash on
   resume — find a crash/resume interleaving that still double-installs, clobbers live, loses the
   tombstone, or reports success wrongly. Is leaving the sentinel armed on completion right, or does it
   need a completion state distinct from "mid-promotion"? Is re-hashing the whole live tree on every
   resume acceptable, or does it need a bounded proof?
3. **Ledger.** Do the three typed terminals cover every real Tushare pagination shape (any endpoint that
   is neither single-page nor offset-capped)? Does re-hashing receipts at verify close the substitution
   hole, or is there still a window (receipt swapped *after* verify, before consolidation)? You flagged
   the co-located chain head as a secondary MAJOR — what is an acceptable independent anchor here given
   a same-privilege single-user machine?
4. **Matrix.** Is binding to `pit_backend.DATASET_SPECS` the right authority, or must keys be proven
   against the DOCS independently (the specs could themselves be wrong)? Is `row_payload_digest` on the
   event families sufficient, and where must it be computed to stay lossless (pre- or post-normalization)?
5. **Contract gate.** Is `接口：<api>` + `doc_id` a sufficient doc↔endpoint binding? The VIP variants cite
   their base doc (`income_vip` → `income`) — does that reopen a hole? Are the endpoint-scoped derived
   declarations narrow enough?
6. **Overall.** Is anything from #5 only *partially* closed? What is the highest-risk remaining gap, and
   is it now safe to open per-endpoint contract sign-off?

Return BLOCKER / MAJOR / MINOR / NIT with file+line, and a SHIP / REVISE / REWORK verdict for opening
contract sign-off.
