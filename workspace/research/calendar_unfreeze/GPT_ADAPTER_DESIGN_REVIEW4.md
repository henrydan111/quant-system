# GPT §10 DESIGN re-review #4 — adapter v4 (final F1 + F7 fold → interface freeze?)

Independent GPT‑5.5 Pro reviewer. re-review #3 discharged F2/F3/F4/F5 and held only F1 + F7, stating:
*"Once F1 gains constants/non-paged binding and F7 gains content-level conservation, I see no remaining
design blocker to freezing the quartet interface."* This is that fold.

Repo `https://github.com/henrydan111/quant-system` · Branch **`calendar-unfreeze`** · HEAD after push.
Design v4: `…/workspace/research/calendar_unfreeze/ADAPTER_PHASE_DESIGN.md` (§2a, §2e updated).

## F1 → resolved (§2a)
`CallRecipe` now = `(recipe_id, vendor_method, request_parameter_map, constant_kwargs, pagination_binding)`:
- **`constant_kwargs`** — content-hashed JSON scalars that aren't request keys, e.g.
  `report_rc.fields = REPORT_RC_FIELDS` (the fixed projection yielding `create_time`; verified at
  fetch_bucket_a.py:103).
- **`pagination_binding`** ∈ {`none` (single_page — sends NO paging kwargs; the zero limit is an internal
  ledger sentinel, never a vendor arg), `limit_offset(limit_kw, offset_kw)` (offset-paged — injects the
  claimed cursor only)}.
- request-map / constant / paging keys are pairwise DISJOINT; every frozen request param mapped exactly
  once (validated at freeze). No transformation language — a future transform lives in the population
  RESOLVER (re-sign the request-set hash), never the recipe.
- **report_rc `create_time` is now machine-required**: added to the signed contract `required_fields`
  (re-signed; 31 clean from generator AND disk). Its PIT anchor `max(report_date, create_time)` no longer
  depends on an unenforced field.

## F7 → resolved (§2e): count-equality replaced by typed `conservation_mode`
- **`multiset_identity`** (income, top_list, broker_recommend): inputs are the immutable verified
  POST-DEDUP request outputs; confirmed empties contribute zero; require BOTH
  `sum(input post_dedup_rows) == sum(output rows)` AND
  `multiset(canonical input row hashes) == multiset(canonical output row hashes)` (so a drop-one +
  duplicate-one can't pass). Extra dedup recorded separately (key + dropped count + bounded allowance).
  Conservation is WITHIN ONE FROZEN RUN — a later restatement changing counts doesn't weaken it (restated
  versions stay distinct via the signed income version key).
- **`base_key_preserving_merge`** (A01): output natural-key SET + row_count == the `daily` base, plus the
  signed aux rules (drop `daily_basic.close`, 100% positive adj_factor coverage, ≥90% daily_basic
  coverage, `validate="one_to_one"`, no dup keys, trade_date == partition).

## Reviewer riders folded
- F2: the `fetch_authorized` event is written ONLY by a separate `authorize-fetch` CLI; the fetch command
  has NO self-mint path; OS SID recorded as EVIDENCE, not the boundary.
- F4: deterministic canary = the LOWEST verified-nonempty request_id for the same endpoint;
  `RETRY_EMPTY_CONFIRM` carries a lease_id; `CONFIRM_EMPTY` only once a canary exists.

## Verified before folding
report_rc uses a fixed `REPORT_RC_FIELDS` projection carrying `create_time` (fetch_bucket_a.py:103);
`create_time` is in doc-292 vocab and was ABSENT from the old required_fields (now added). Battery 171
passed; `--plan` = 30 UNBOUND + A07 held.

## Questions
1. Do `constant_kwargs` + `pagination_binding` (with disjointness/totality) + the report_rc create_time
   requirement fully discharge F1?
2. Does the typed `conservation_mode` (multiset content identity | base-key-preserving) discharge F7?
3. Any remaining design blocker, or is the quartet interface FROZEN for implementation (A07 excepted,
   pending its period-discovery probe)?

## Self-review (mine): clean. §3 invariants intact; the two folds are the exact concrete changes you
specified; no new surface introduced. If this freezes the interface, I proceed to implement the quartet
(A01 + income + top_list + broker_recommend) + the pre-fetch test matrix for the IMPLEMENTATION review.
