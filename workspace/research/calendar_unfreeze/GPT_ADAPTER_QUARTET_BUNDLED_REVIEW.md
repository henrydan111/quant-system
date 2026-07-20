# GPT §10 BUNDLED review — adapter design-freeze confirmation (re-review #4) + quartet IMPLEMENTATION

You are the independent GPT‑5.5 Pro reviewer. This bundles TWO gates you must rule on separately:

- **Gate A (design re-review #4):** your re-review #3 held only F1 + F7 and pre-stated *"Once F1 gains
  constants/non-paged binding and F7 gains content-level conservation, I see no remaining design
  blocker to freezing the quartet interface."* Both were folded (design v4). You were then temporarily
  unavailable, so re-review #4 ran as an ADVERSARIAL SELF-REVIEW (recorded in the design doc §8, with
  3 code probes) and the interface was marked **PROVISIONALLY frozen**; the user explicitly authorized
  proceeding to implementation on that provisional freeze, with your confirmation OWED — this is it.
- **Gate B (implementation review):** the quartet was then implemented against the provisionally
  frozen v4 interface. Review the implementation for conformance + defects.

Repo `https://github.com/henrydan111/quant-system` · Branch **`calendar-unfreeze`**.
**Reviewed commit: `5cc3b9a`** (feat(incident): quartet adapter implementation). Later commits on the
branch are a CONCURRENT unrelated workstream (nf-wave) that does not touch the recovery files — verify
the five files below are unchanged at branch HEAD if you check there.
Raw base: `https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/`

Files (all under the raw base):
1. `workspace/research/calendar_unfreeze/ADAPTER_PHASE_DESIGN.md` — design v4 + the §8 self-review
   (probes: CallRecipe expressibility vs the actual resolved populations; the §6.1 throttle lives at
   the `tushare_lock.spaced_call` proxy, NOT `_safe_api_call`; multiset canonicalization reuse).
2. `scripts/recovery_ledger.py` — the claimed-fetch extensions (see below).
3. `scripts/recovery_adapters.py` — NEW: recipes / scopes / family+consolidation specs / orchestration.
4. `src/data_infra/fetchers/__init__.py` — `fetch_page_once` + `avoid_token_cache`.
5. `tests/data_infra/test_recovery_quartet.py` — NEW: the 30-test pre-fetch battery.

## Gate A — the two v4 folds you specified (confirm or refute)
- **F1:** `CallRecipe(recipe_id, vendor_method, request_parameter_map, constant_kwargs,
  pagination_binding)`. `constant_kwargs` carries report_rc's fixed `fields=` projection (create_time);
  **create_time was also added to the signed contract `required_fields`** (machine-required — its PIT
  anchor depended on an unenforced field). `pagination_binding=none` sends NO paging kwargs (the 0
  sentinel never reaches the vendor); `limit_offset` injects only the claimed cursor. Disjointness +
  totality validated at freeze. No transform language (a future transform lives in the population
  resolver + re-signed request-set hash).
- **F7:** typed `conservation_mode`: `multiset_identity` (count equality AND canonical row-hash
  multiset equality — reusing the ledger's lossless `add_row_payload_digest` encoder over the identical
  vendor-column set on both sides; drop-one+duplicate-one cannot pass) | `base_key_preserving_merge`
  (A01: output natural-key set + row count == the daily base, plus the signed aux rules).
- Riders folded: the `fetch_authorized` event is written ONLY by a separate authorize-fetch action
  (no self-mint path in fetch); OS SID recorded as evidence, not the boundary; deterministic canary =
  lowest verified-nonempty same-endpoint request.

## Gate B — what the implementation IS
**Ledger** (`recovery_ledger.py`): `claim_next_fetch(rid, executor_mode)` — atomic cursor+lease under
ONE lock (concurrent → `IN_FLIGHT`); run-mode + live-§13 checked BEFORE any lease; empty lifecycle
`RETRY_EMPTY_CONFIRM` → `WAIT_FOR_CANARY` → `CONFIRM_EMPTY(canary)`; VERIFY never for an empty sparse
request. `fetch_claimed_page(rid, claim, executor)` — one executor call outside the lock; n>limit
refuses; untouched vendor-page hash recorded (`vendor_page_sha256`) before `prepare_raw_page`
(registry-only derived columns; report_rc UNREGISTERED → fail-closed) and before the `raw_fetch_ts`
stamp; frozen `response_scope` enforced page-by-page AND post-concat in `verify_request` (typed date
ranges); terminals LEDGER-DERIVED (`single_page_contract` / `empty_terminal` / `last_partial` / ""
nonterminal). Immutable run-mode (`declare_run_mode`; `assert_run_promotable` refuses non-live). §13 =
`record_fetch_authorization` hash-chained event (actor, OS-identity evidence, expiry, endpoint scope,
plan_sha256, bundle_sha256), validated at claim AND in-lease. `_PLAN_REQUIRED` += `recipe_id`,
`response_scope`.

**Adapters** (`recovery_adapters.py`): 7 recipes; `response_scope_of`; `FamilySpec`/`ConsolidationSpec`
for the 4 physical layouts (A01 3-leg per-date merge; income per-stock→per-`end_date` repartition;
top_list per-event-date + `omit_output` empties; broker monthly); `merge_daily_legs` = the canonical
merger with `validate="one_to_one"` + the production coverage invariants; `build_plan_rows` /
`freeze_run_plan` (ONE freeze per run through the coordinator's sanctioned door) / `run_family`
(atomic-claim loop; live mode recomputes the content-hashed bundle manifest first) /
`consolidate_family` (separate step; hash-chained verdict binding every input verdict + each output's
path/bytes/rows). `compute_bundle_manifest` = content sha256 of the 5 fetch-affecting modules + the
canonical declarative registry.

**Fetcher**: `fetch_page_once(vendor_method, **kwargs)` — exactly ONE call through the LOCKED proxy
(sheds the retry loop, never the §6.1 throttle; a source lint in the battery pins no-loop /
no-`_safe_api_call`). `avoid_token_cache=True` skips `ts.set_token` (no user-profile write).

**Battery** (30 tests; full recovery suite **201 passed**): run-mode gates, §13 event
(missing/expired/valid/bundle binding), promotion refusal, single-page, exact-limit multipage +
trailing empty, last_partial, n>limit + RETRY_PAGE, concurrent IN_FLIGHT, crash resume at the next
offset, dense-empty refusal, the sparse 2-lease→canary lifecycle, wrong-date + wrong-stock scope
refusals, top_list digest prep, unregistered-producer fail-closed, 4 merger-invariant tests, the
digest-multiset drop+dup probe, four family E2Es under `SyntheticExecutor` (each physical layout), the
drifted-bundle live refusal, the `fetch_page_once` shape lint, recipe disjointness, and **the REAL A01
plan at full scale: 13,479 requests built from the SIGNED contracts and frozen through
`freeze_request_plan`'s complete validation (no fetching)**.

## Deviations from the design LETTER — flagged for your ruling (not hidden)
1. **`fetch_claimed_page` builds the spec ITSELF** from the frozen plan row + claimed cursor instead of
   validating a caller-passed `PageCallSpec` (design said "validates spec vs frozen request"). Rationale:
   strictly stronger — nothing exists for a caller to get wrong; the executor receives the
   ledger-constructed spec. Confirm this discharges the intent.
2. **Bundle drift refuses at LOAD**: the bundle hash is part of the chain GENESIS, so a ledger
   constructed with a different bundle hash cannot even replay the run (stronger than the event-level
   check, which still guards an authorization recorded under an older bundle within one genesis).
3. **Dense-empty surfaces at verify**: `claim_next_fetch` returns VERIFY for a dense-empty request and
   `verify_request` refuses loudly ("dense dataset verified with 0 rows") — the claim enum has no
   REFUSE_DENSE_EMPTY kind. The refusal is loud and total; confirm the placement is acceptable.
4. **The legacy `fetch_page(rid, page, call, terminal_claim)` remains** as the below-contract-layer
   primitive used by the EXISTING 41-test ledger battery to construct adversarial states (gap pages,
   retries, torn tails) that the claimed path prevents by construction. Production orchestration
   (`run_family`) uses ONLY the claimed path. QUESTION: must the legacy door be further restricted
   (e.g. refuse when a run-mode is declared), or is battery-only use acceptable with the claimed path
   as the sole production door?
5. **`RETRY_PAGE`** is returned when the target page has a RECORDED failure (lease_failed); otherwise
   FETCH. There is no separate crash-abandon transition yet — an orphaned OPEN lease currently returns
   IN_FLIGHT forever until a crash-resume rule (with the process-lifetime run lock) converts it; that
   rule is in the PENDING list below.

## Declared PENDING (not in this commit — rule whether any blocks fan-out)
(a) the F10 fresh-subprocess network-denied live-construction write test + the full write-surface
allowlist monitor; (b) the `authorize-fetch` CLI command (the ledger method exists + is tested; the CLI
wiring does not); (c) the crash-abandon rule for orphaned OPEN leases (design §3; currently IN_FLIGHT
forever); (d) the production `update_daily_data` refactor onto `merge_daily_legs` (F9 rider); (e) the
consolidation output-density gate (tracked promotion precondition); (f) the report_rc digest producer
registration (fan-out; fail-closed until then).

## Self-review (mine, §10 prerequisite)
Design §8 (3 probes) + implementation: built test-first against the acceptance matrix; every deviation
from the design letter enumerated above rather than silently absorbed; the pending list is explicit;
suite 201 green; `--fetch` still exits 3; no Tushare import on any test path. §3 invariants: raw
re-fetch only, PIT alignment downstream, fina_mainbz formal-PIT quarantine untouched, §6.1 throttle
preserved by construction. Verdict: clean for bundled review.

## Return format
Per gate: **Gate A** — is the interface freeze CONFIRMED (or what re-opens)? **Gate B** — per finding:
severity (BLOCKER/MAJOR/MINOR/NIT), whether it blocks (i) fan-out to the remaining 26 families,
(ii) the §13 live fetch; and a reproducing probe where applicable. Also rule on deviations 1–5 and
whether any PENDING item must land BEFORE fan-out rather than before §13.
