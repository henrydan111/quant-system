# Report-Factor Expansion Plan (`report_rc` → factors, the COMPLIANT way)

*2026-06-08. This plan REDOES the report_rc factor work through the sanctioned backend, replacing the
quarantined hand-rolled sandbox pilot. Per CLAUDE.md §3.2 / src/system.md §0: a new dataset becomes a
factor ONLY after `pit_backend` materializes it into the PIT ledger + Qlib provider and `field_status.yaml`
registers it; factors are then Qlib expressions computed via `compute_factors` — never hand-rolled from
raw `data/` parquet.*

## 0. Status of the prior (tainted) work
The sandbox pilot found `eps_diffusion` (analyst EPS-revision breadth) looked strong + tradeable. That
result is **a HYPOTHESIS, not a finding** — it was produced by a non-compliant path (raw reads +
hand-rolled PIT + no provider-bounds masking). This plan re-derives it through the backend, where it
becomes trustworthy. Do not cite the sandbox numbers as evidence.

## 1. Goal & scope
Turn `report_rc` (sell-side analyst forecasts, RAW at `data/analyst/report_rc/`, 2.87M rows 2010-2026)
into a small set of PIT-correct, registry-governed **Qlib factor fields** (`$report_rc__*`) and screen
them through the factor lifecycle. Scope is `report_rc` only; the same six-step pattern extends to the
other Bucket A fundamentals/events (express, fina_mainbz, repurchase, pledge_stat, top10_floatholders,
fina_audit, disclosure_date) as follow-on expansions, NOT covered here.

## 2. Architecture mapping (where each piece slots in — verified anchors)
| Step | Mechanism (existing precedent) | File |
|---|---|---|
| Dataset contract | `DatasetSpec(kind="event_ledger", ann_date_column="report_date")` | `pit_backend.py` `DATASET_SPECS` (≈L240/L485 `stk_holdertrade`) |
| PIT ledger | normalize → `data/pit_ledger/report_rc/` with `effective_date = strictly_next_open_trade_day(report_date)` | `pit_backend.py` ledger builder + `strictly_next_open_trade_day` (L659) |
| Daily materialization | custom `_materialize_report_rc_consensus` → `$report_rc__*` bins (windowed rolling consensus) | precedent `_materialize_stk_holdertrade` (L2340) |
| Namespace protection | add `report_rc` to `EVENT_LIKE_DAILY_FIELD_PREFIX` (→ `report_rc__`) | `pit_backend.py` L122 |
| Field governance | register `$report_rc__*` in `field_status.yaml` (quarantine→approve) | `config/field_registry/` |
| Factor definitions | Qlib exprs `Ref($report_rc__eps_diffusion, 1)` in the catalog | `factor_library/catalog.py` + `operators.py` |
| IS screen | `factor_lifecycle` profile (draft→candidate) | `research_orchestrator` |
| OOS / ML | sealed-OOS (candidate→approved) OR ML features via `compute_factors`/`pit_research_loader` | — |

## 3. The hard part — the consensus materializer (key design)
Unlike `stk_holdertrade` (aggregate events to their own `effective_date`, NaN between), a report_rc
consensus is a **windowed, forward-evolving cross-analyst aggregate**: on each trading day T, the
consensus is computed from all forecasts visible (`effective_date ≤ T`) within a trailing window, one
vote per analyst (latest), with age-expiry. Design decisions to freeze BEFORE coding:

1. **Efficient rolling computation (NOT per-day recompute).** Event-driven per-stock state: on each
   forecast's `effective_date` insert/replace that analyst's vote; expire votes older than `AGE_DAYS`;
   emit the consensus on every calendar day the state is non-empty. O(events + days·stocks_active), not
   O(days × forecasts). Must be deterministic (P0-4 `_src_file`/`_src_ordinal` tie-break discipline).
2. **FY1 target rule** for the EPS-level/revision features: the consensus EPS refers to the nearest
   not-yet-reported annual period (`quarter == "{YYYY}Q4"` for the current fiscal year as-of T). Freeze
   the exact rule (handle the Q4-already-reported roll-forward) — it must be PIT-correct.
3. **Revision/diffusion semantics**: per-analyst direction = latest vs prior forecast within the window
   (the breadth/diffusion form, which the pilot suggested >> magnitude). Diffusion is discrete with a
   large zero-mass → factors built on it must be `cs_rank`/sign-based downstream, not quantile-sorted.
4. **PIT anchor**: `effective_date = strictly_next_open_trade_day(report_date)` (strictly later). Every
   factor wraps the field in `Ref(...,1)` (factor-library PIT-safety lint). Provider bounds (delist/
   IPO-lag) inherited because the materializer writes per `target_dirs` (the instruments-sidecar guard).
5. **report_date PIT-safety**: the backfill canary (2026-06-15) verifies `report_date` isn't backfilled;
   approval to `field_status` waits on its verdict (parallel track — does not block design/Phases 1-2).

## 4. Candidate field set (materialize as `$report_rc__*`; the SCREEN picks winners)
Materialize a small, economically-motivated set; let the compliant factor_lifecycle decide — do NOT
pre-select from the tainted pilot:
- `eps_diffusion` — net % of analysts raising FY1 EPS (revision breadth) ← lead hypothesis
- `eps_revision` — consensus FY1 EPS Δ over the window (magnitude)
- `rating_revision` — consensus rating-score Δ
- `eps_dispersion` — cross-analyst FY1 EPS std / |mean| (disagreement)
- `n_analysts` — coverage count (KNOWN size-proxy → expect it to fail the marginal-IC gate; keep as a control)
- `eps_fy1` — consensus FY1 EPS level (likely a price-level artifact; keep for the screen to reject)

Defer `tp`-based target-implied return — the raw `tp` field is unit-corrupted (e.g. 9600 targets) and
needs a cleaning pass first. Drop `rating_diffusion` / rec-change (2% coverage — A-share analysts don't
change ratings; dead in the data).

## 5. Phases, deliverables, gates
- **Phase 0 — Pre-register + design cross-review.** Write the hypothesis (`hypothesis_cli.py register`)
  + freeze the §3 design decisions + the §4 field definitions. GPT cross-review the materializer design
  (esp. the rolling-state correctness + FY1 rule + diffusion semantics) BEFORE coding. *Gate: design GO.*
- **Phase 1 — Dataset spec + PIT ledger.** Add the `report_rc` `DatasetSpec`; build
  `data/pit_ledger/report_rc/`. *Tests:* PIT invariant (`effective_date > report_date` for all rows),
  coverage vs raw, deterministic rebuild (SHA-256 stable). *Gate:* ledger parity.
- **Phase 2 — Consensus materializer.** Implement `_materialize_report_rc_consensus` + add to
  `EVENT_LIKE_DAILY_FIELD_PREFIX`. *Tests:* (a) PIT-safety — `factor[T] ⊥ report[T+1]` (behavioral, like
  `test_operator_behavioral_pit`); (b) **independent-recompute parity** — a from-scratch pandas
  reimplementation off the ledger matches `D.features` cell-by-cell (the method GPT validated for the
  Wave-1 statement promotion); (c) namespace protection (`test_event_like_daily_namespace`); (d) a
  synthetic-lookahead canary. *Gate:* all PIT + parity tests green.
- **Phase 3 — Provider build + registry.** Staged provider rebuild (`build_qlib_backend.py
  --stage provider-only` on a basket first, then full) → `$report_rc__*` bins exist; register in
  `field_status.yaml` as **quarantine**; run coverage + live-provider parity audit; write approval
  evidence (provider-build + calendar-policy bound); promote quarantine→approved **only after** the
  06-15 canary + user approval (§13). *Gate:* field-registry tests + approval-evidence binding green.
- **Phase 4 — Catalog factors.** Add `Ref($report_rc__<field>, 1)` (+ any smoothed/Δ variants) to
  `catalog.py`; update the catalog count docs. *Tests:* `test_factor_library_pit_safety`,
  `test_operator_expressions`. *Gate:* lints green.
- **Phase 5 — Compliant IS screen (REPLACES the tainted pilot).** Run the new factors through the
  `factor_lifecycle` IS gate (IS 2014-2020, the sanctioned `compute_factors`→`qlib_windowed_features`
  door) → IC / ICIR / LS-Sharpe / quantile / decay / turnover the proper way; promote draft→candidate
  for those that clear the bar (marginal/orthogonalized IC, per [[reference_factor_selection_marginal_not_icir]]).
  *This is where `eps_diffusion` is either confirmed or falsified — trustworthy this time.*
- **Phase 6 — OOS or ML.** Candidate→approved via a single sealed-OOS shot vs CSI500; OR, for the ML
  direction, the now-compliant `$report_rc__*` provider fields are read as ML features via
  `compute_factors` (qlib) into a feature store built the sanctioned way (no raw reads).

## 6. Risks / open questions
1. **The rolling-consensus materializer is novel + the main risk** (correctness, determinism,
   performance over daily × full history). Mitigation: independent-recompute parity test + a small-basket
   build first. *Hardest item — design-review it heavily in Phase 0.*
2. **`report_date` PIT-safety** unproven until the canary (06-15). Design/build proceed; formal approval waits.
3. **FY1 target-selection rule** has reporting-calendar edge cases (Q4 roll-forward) — freeze precisely.
4. **Provider rebuild cost** (Phase 3) — a §13 risky action; basket-first, confirm before full.
5. **Expectation**: the pilot hint is provisional; the compliant screen may yield a WEAKER (or null)
   result once provider-bounds masking removes survivorship inflation. Treat a null as a valid outcome.

## 7. Smallest first slice (if approved to start)
Phase 0 (pre-register + design) → Phase 1 (ledger) → Phase 2 (materializer + parity tests) on a small
symbol basket, WITHOUT a full provider rebuild — enough to prove the field materializes PIT-correctly and
matches an independent recompute. Then decide on the full rebuild + screen.
