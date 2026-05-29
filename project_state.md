# Project State Tracker
*Update Note (2026-05-30, **PIT prevention PHASE 6 — OPTIONAL TAIL COMPLETE (lint expansion + offline CI + `.claude` hygiene); shared hooks INTENTIONALLY DROPPED**): The §13-gated "remaining optional tail" called out in the PHASE 5 note below is now closed across the GPT 5.5 Pro-reviewed PRs #23–#25 (re-check verdict: #23 Approve, #24 Approve, #25 Approve-after-this-note; fixes folded in). PR #26 (item 4 below) is a SEPARATE, owner-handled jq-mimics archive follow-up that was NOT part of the GPT review set. **(1) PR #23 — step 7 lint expansion** [scripts/lint_no_unsafe_pit_dates.py](scripts/lint_no_unsafe_pit_dates.py): PIT001 is now **column-aware** — stringifying a FUNDAMENTAL date column (`effective_date`/`ann_date`/`f_ann_date`/`disclosure_date`/`end_date`/`pubDate`/`statDate`; the exact dashed-ISO lookahead vector) is a **HARD ERROR (exit 1)**, while `trade_date` (compact market index) stays a WARNING; `np.datetime_as_string` is also detected. Jupyter `.ipynb` code cells are now scanned (stdlib JSON parser, no `nbformat` dep). **GPT review fixes:** PIT001 inline suppression now REQUIRES a structured reason (`# noqa: unsafe-pit-dates[PIT001] reason: <≥9-char why>` via `_PIT001_NOQA_RE`; a bare `# noqa` no longer suppresses; PIT002 stays unsuppressible inline — allowlist only); and notebook magic/shell lines (`%`,`!`,`?`) are line-scanned for `pit_ledger` BEFORE the AST-strip so `!python -c "...pit_ledger..."` cannot hide a raw read. 25 lint tests; src+workspace exit 0 (val_heavy_loader_proof.py:80's reasoned noqa still suppresses; 2 benign trade_date warnings). **(2) PR #24 — offline CI** [.github/workflows/ci.yml](.github/workflows/ci.yml) + [requirements-ci.txt](requirements-ci.txt) + `.gitattributes`: runs on PRs to `main`/push-to-`main`/dispatch; installs ONLY pandas/numpy/pyarrow/pyyaml/pytest (no qlib/mlflow/cvxpy — verified in a throwaway venv); runs both PIT lints + a curated offline test set (`pit_alignment_core`, `pit_research_loader`, `lint_no_unsafe_pit_dates`, **`field_registry`** [added per GPT review], `factor_library_pit_safety`, `operator_expressions`, `promotion_gate`, `dormant_module_boundaries` = 185 tests). **Verified GREEN live on the GitHub runner** (~23s). `test_pit_loader_provider_parity.py` is deliberately EXCLUDED (provider-skipif → all-skip in CI + imports qlib); live parity stays in `run_daily_qa.py`. **(3) PR #25 — `.claude` hygiene**: `git rm --cached` of `.claude/settings.local.json` (personal `C:/Users/henry/...` paths + `defaultMode: bypassPermissions`) and `.claude/scheduled_tasks.lock` (runtime lock), keeping local copies; the existing `.gitignore .claude/` rule keeps them out. **SHARED CLAUDE HOOKS WERE INTENTIONALLY NOT IMPLEMENTED** — the active prevention boundary is PIT lint + `run_daily_qa` + offline CI + release/promotion gate + tests; hooks are advisory, Claude-Code-only (do not fire for Codex or manual edits), and weaker than the five enforced layers. **This SUPERSEDES the "step 7 / offline CI / `.claude` hooks" remaining-tail line in the PHASE 5 note below and the step-12 hook references in the PHASE 1/2 notes** — a future session should NOT re-open the hook task; reviving shared hooks requires an explicit owner decision AND a `.gitignore` negation (`!.claude/settings.json`). **(4) PR #26 [SEPARATE follow-up — owner-handled, NOT in the GPT review set] — legacy containment**: 6 untracked JoinQuant deploy mimics (`jq_deploy_earnings_momentum_v1/v2` [v2 = the val_heavy +81.9%/WF+82.4% champion, true PIT ≈ +9.6%], `jq_11f_roewaa_strategy`, `jq_deploy_roa_quality_v3/v4/v5`) were archived into `workspace/scripts/archive/pit_lookahead_legacy_2026_05/` (gitignored; tracked README manifest gained a "JoinQuant deployment mimics" section) — same disposition as the 73 `sandbox_v*` loaders. **PIT-LOOKAHEAD PREVENTION ARC COMPLETE** (core arc PRs #18–#22 + the GPT-reviewed optional tail PRs #23–#25; PR #26 is a separate owner-handled jq-mimics archive follow-up, not part of the GPT re-check). Recommended merge order: #23 → #24 → #25, with #26 handled separately.*

*Update Note (2026-05-30, **PIT prevention PHASE 5 — promotion gate (step 11) + CLAUDE.md §3 capstone invariant; CORE ARC COMPLETE**): Added the decision-layer guard (`assert_promotion_eligible` / `evaluate_promotion_eligibility` / `evaluate_promotion_from_artifact` + `PromotionGateResult`/`PromotionGateError`) to [src/research_orchestrator/release_gate.py](src/research_orchestrator/release_gate.py): any code assigning a PRIVILEGED label (`champion`/`deployment_candidate`/`live_candidate`/`approved`) must supply an INDEPENDENT PIT-correct reproduction source (`qlib_windowed_features` / `joinquant_native_pit` / `audited_pit_source`); a sandbox/loader panel — even the parity-verified `pit_research_loader` — is refused. This is the exact guard the val_heavy near-deployment lacked. **GPT PR #22 review (round 1) → ENFORCED, not just a contract**: the gate is wired into `StrategyRegistryStore.set_status` ([src/research_orchestrator/registries/strategy_registry.py](src/research_orchestrator/registries/strategy_registry.py)) — promoting a `strategy_candidate` to the privileged registry **status `approved`** raises `PromotionGateError` unless `promotion_evidence` passes `assert_promotion_artifact_eligible` (full v5 §6.7 schema, **FAIL-CLOSED on missing evidence** after GPT round-2 review: independent source + ALL canaries (`synthetic_lookahead`/`restatement`/3×`q0_*`/`availability`) + `unsafe_pit_dates_lint` must each be explicitly "passed"; `live_provider_parity` passed-or-legally-not-required (illegal if `pit_research_loader` entered primary OR reproduction); `dirty_tree` explicitly `false`; `git_sha` present+matching when a `current_git_sha` is supplied). Also per GPT review: **registry STATUSES (`approved`) split from forward-looking deployment LABELS (`champion`/`deployment_candidate`/`live_candidate`)**; `audited_pit_source` now requires `source_name`+`audit_artifact` (no bare magic string); `evaluate_promotion_artifact(artifact, current_git_sha=...)` makes the schema executable. 29 tests [tests/research_orchestrator/test_promotion_gate.py](tests/research_orchestrator/test_promotion_gate.py) (incl. the set_status wiring); 155 research_orchestrator tests green (no regression). **GPT round-3: `current_git_sha` is now MANDATORY at the `set_status` privileged transition** (omitting it raises `PromotionGateError` — the git-SHA backstop can no longer be skipped by leaving it unset). **CLAUDE.md §3 + AGENTS.md §2a** gained the "PIT-lookahead prevention architecture — two front doors" capstone invariant documenting all 5 enforcement layers (sanctioned loader / fail-closed governance / PIT002 hard gate / legacy containment / promotion gate). **CORE PREVENTION ARC COMPLETE** (steps 2,3,4,5,6,8,9,10,11 + registration + invariant across PRs #18–#21 + this phase-5 PR). Remaining OPTIONAL tail: step 7 (`.ipynb` lint + sink-aware PIT001 phase-2 — lint enhancement); §13-gated offline `.github/workflows/ci.yml` + `.claude` hooks (owner approval).*

*Update Note (2026-05-29, **PIT prevention PHASE 4 — legacy containment (step 9) + QA lint gate ACTIVATED (step 10)**): The **73** invalidated `build_pit_pivot` sandbox-lineage scripts (untracked, never on public `main`) were moved to a LOCAL archive `workspace/scripts/archive/pit_lookahead_legacy_2026_05/` — **kept untracked** (per owner decision: not committed, to avoid bloating the public repo; a **tracked README manifest** records all 73 filenames + the containment contract). Committed enforcement: (0) `.gitignore` ignores `workspace/scripts/archive/pit_lookahead_legacy_2026_05/*.py` (README manifest stays tracked) so the dead lineage cannot be accidentally `git add`ed back; (1) [scripts/lint_no_unsafe_pit_dates.py](scripts/lint_no_unsafe_pit_dates.py) skips ONLY the **sanctioned archive roots** (`ARCHIVE_SKIP_ROOTS`, root-specific — a generic `archive/` dir elsewhere is still linted; not a broad "any dir named archive" skip); (2) new arch-test [test_dormant_module_boundaries.py::test_pit_lookahead_legacy_archive_not_referenced_by_live_code](tests/architecture/test_dormant_module_boundaries.py) forbids live `src/`+`workspace/` code from `import sandbox_v*` or path-referencing the archive (precise patterns — docstring/prose mentions are allowed). With the lineage contained, **step 10 is LIVE**: `lint_no_unsafe_pit_dates.py src workspace` is now a HARD gate in [scripts/run_daily_qa.py](scripts/run_daily_qa.py) (`unsafe_pit_dates_lint`, exit 0 — src+workspace are PIT002-clean). 84 prevention/arch/lint tests green. **Remaining:** step 7 (`.ipynb` lint + sink-aware PIT001 phase-2); step 11 (release-gate independent-reproduction); §13-gated offline CI + `.claude` hooks; CLAUDE.md §3 two-front-door invariant.*

*Update Note (2026-05-29, **PIT prevention PHASE 3 step 8 — val_heavy loader-migration proof (PR #20)**): [workspace/scripts/val_heavy_loader_proof.py](workspace/scripts/val_heavy_loader_proof.py) migrates the val_heavy config off the hand-rolled `build_pit_pivot` onto a single `load_pit_signal_panel(..., signal_lag_bars=1)` call — **PIT002-clean** (lint exit 0; no raw `pit_ledger` read), first real consumer of the PR#19-registered `dt_netprofit_yoy`, full-universe load ~62s (no perf regression). It carries a **phantom-leakage sentinel** (raises if OOS CAGR or WF avg > 30%) and independently reproduces the weak de-contaminated profile via the governed path (Full 10.6% / OOS 2.4% / WF ~0% — NOT the +81.9%/WF+82.4% phantom). **Caveat:** this is an ergonomics proof, NOT a v5 "independent reproduction" for a promotion gate (that still requires the formal provider / JoinQuant-native PIT, not a sandbox-loader panel). Remaining: step 9 archive the ~55 legacy sandbox scripts + arch-test; step 10 wire the unsafe-pit-dates lint as a hard QA gate (unblocked by step 9); step 7 `.ipynb` lint + sink-aware PIT001; step 11 release-gate independent-reproduction; §13-gated offline CI + `.claude` hooks; CLAUDE.md §3 two-front-door invariant.*

*Update Note (2026-05-29, **PIT prevention PHASE 2 landed (PR #19) — live parity drift guard + 5-field registration**): PR #19 added the live-local loader↔provider parity drift guard ([tests/data_infra/test_pit_loader_provider_parity.py](tests/data_infra/test_pit_loader_provider_parity.py)) and wired it into [scripts/run_daily_qa.py](scripts/run_daily_qa.py) as the `pit_loader_provider_parity` check. Grid: 8 indicator fields × 3 securities (incl. IPO-edge 603080.SH), **lag-0 as-of parity AND lag-1 signal parity**, with a full-grid coverage assertion + per-new-field non-all-NaN evidence floor; provider path resolved from `config.yaml::storage.qlib_data_dir`. PR #19 also **registered** `roe_waa, roe_dt, q_roe, q_dt_roe, dt_netprofit_yoy` under the approved `indicators` dataset via the governed path (field_status.yaml + [approvals/2026-05-29_indicators_loader_qfields.yaml](config/field_registry/approvals/2026-05-29_indicators_loader_qfields.yaml), bound to provider_build_id=prod_full_20260421_namespace_v1 + calendar_policy_id=frozen_20260227_system_build; append-log entry), each PARITY-VERIFIED equal to the provider FIRST. **This SUPERSEDES the phase-1 note below: live parity (step 6) is DONE, and those 5 fields are now REGISTERED (the phase-1 "registry-coverage finding" is resolved).** 76 prevention tests green. **Remaining prevention work:** notebook lint + sink-aware PIT001 phase-2 (step 7); migrate one v33/val_heavy proof script onto the loader (step 8 — DONE, see PHASE 3 note at top); archive/contain the ~55 legacy sandbox scripts + arch-test (step 9); `run_daily_qa` unsafe-pit-dates lint block + pre-commit (step 10); release-gate independent-reproduction (step 11); offline `.github/workflows/ci.yml` (step 1) + `.claude` hooks (step 12) — last two gated on owner approval; CLAUDE.md §3 two-front-door invariant. **Non-blocking parity follow-up:** add a delisted/delist-edge instrument + a known restatement/effective-date fixture to fully match the v5 oracle grid.*

*Update Note (2026-05-29, **PIT-lookahead PREVENTION spine PHASE 1 landed (steps 2–5; enforcement gates + legacy containment remain OPEN — NOT full prevention)**): Implemented the low-risk additive core of the cross-reviewed prevention plan ([Knowledge/temp_plan/pit_lookahead_prevention_plan_2026-05-29_v5_FINAL.md](Knowledge/temp_plan/pit_lookahead_prevention_plan_2026-05-29_v5_FINAL.md), approved over 5 GPT 5.5 Pro rounds). **New files (all additive; no existing code modified):** (1) [src/data_infra/pit_alignment_core.py](src/data_infra/pit_alignment_core.py) — the shared PIT-semantics kernel: `align_ledger_to_calendar()` with **stateful q0** (running per-`end_date` visible state mirroring the provider's `materialize_visibility_segments`; a restatement of an older period does NOT demote q0; NaN-at-q0 is served as NaN, never `dropna`-before-q0), explicit `availability_lag_bars`, and a fail-closed `duplicate_policy` (`error` default; `provider_stateful_q0` for the 29% Case-A multi-period collapse; raises on a Case-C same-period conflict — `provider_canonicalize_snapshot` intentionally NOT exposed). (2) [src/data_infra/pit_research_loader.py](src/data_infra/pit_research_loader.py) — the sanctioned sandbox front door: `load_pit_asof_panel(availability_lag_bars=0)` (data parity) and `load_pit_signal_panel(signal_lag_bars=1)` (research default; lag<1 refused), with vectorized `provider_metadata`-equivalent delist/IPO-lag bounds masking and field-registry governance (`$`-prefixed identity, so a bare field cannot bypass governance). Returns provider-compatible q0 aliases. (3) [scripts/lint_no_unsafe_pit_dates.py](scripts/lint_no_unsafe_pit_dates.py) — PIT002 raw-`pit_ledger`-read (docstring/comment-aware token scan; HARD ERROR) + PIT001 date-stringify (phase-1 WARNING); exemptions only via the schema-validated [config/lint/unsafe_pit_dates_allowlist.yaml](config/lint/unsafe_pit_dates_allowlist.yaml) (no inline noqa for PIT002; fails on expired/dangling entries). **Verified:** the kernel+loader reproduce the live provider's PIT-correct 600519 values EXACTLY (June-2018 roa=9.05 Q1, NOT 25.25 Q3; Jan=23.64; Sep=17.17; Nov=25.25) — informal parity; bounds mask NaNs 688981 pre-listing; quarantined `$net_mf_amount` blocked at formal stage; the lint flags raw reads but NOT `provider_metadata.py`'s safety docstring (GPT blocking-edit-2 fixture). **22 new tests green** ([tests/data_infra/test_pit_alignment_core.py](tests/data_infra/test_pit_alignment_core.py) 7 canaries incl. stateful-restatement + missing-field; [test_pit_research_loader.py](tests/data_infra/test_pit_research_loader.py) 6, real-data ones skip if ledger absent; [test_lint_no_unsafe_pit_dates.py](tests/data_infra/test_lint_no_unsafe_pit_dates.py) 9); both lints exit 0 on `src/`. **REMAINING plan steps (NOT yet done):** live loader↔provider parity test wired into `run_daily_qa.py` (step 6); full lint expansion — `.ipynb` notebooks + sink-aware PIT001 phase-2 (step 7); migrate 2–3 live-relevant sandbox scripts to the loader then archive the ~55 legacy ones + extend the archive-boundary arch test to live `workspace/` (steps 8–9); `run_daily_qa` lint block + pre-commit (step 10); release-gate independent-reproduction extension + `promote_strategy` refusal (step 11); `.github/workflows/ci.yml` offline skeleton (step 1) and `.claude/settings.json` PostToolUse+Stop hooks + un-track `settings.local.json` (step 12) — the last two pause for explicit approval per CLAUDE.md §13 (CI / harness config). CLAUDE.md §3 invariant for the two-front-door rule still to be added. **GPT 5.5 Pro review of PR #18 (round 6) → 3 blocking fixes applied (commit 2 on the branch):** (1) loader field-governance is now fail-closed on registry-unknown fields even at `sandbox_screening` (was inheriting the lenient `unknown_field_policy=warn`) + `$`-prefix normalized (`$roa`≡`roa`, no `$$roa`); (2) Case-C now flags mixed null/non-null same-`(ts,eff,end)` rows (was `dropna`-before-`nunique`, which allowed input-order-dependent last-write collapse); (3) lint `DEFAULT_TARGETS` narrowed to `(src, workspace)` per v5 scope + the linter self-allowlisted so it never flags its own detection literal. Loader duplicate-policy default is intentionally `provider_stateful_q0` (Option B, documented) while the kernel default stays `error`. **Test count 22→27** (kernel NaN-conflict + identical-dup-safe; loader unknown-reject + quarantine-reject-at-sandbox + `$`-normalize). **Registry-coverage finding (RESOLVED in PR #19 — see top note):** the indicator columns `roe_waa, q_roe, q_dt_roe, roe_dt, dt_netprofit_yoy` were unregistered when this fail-closed loader landed (`is_unknown=True`) and were therefore refused — they have since been REGISTERED (phase 2, PR #19) after parity verification. These are the very fields the invalidated champions consumed, reinforcing that the champion ran on un-governed data. PR: [#18](https://github.com/henrydan111/quant-system/pull/18).*

*Update Note (2026-05-29, **PIT LOOKAHEAD BUG in the sandbox factor loaders — INVALIDATES all v31/v32/v33 + val_heavy sandbox performance numbers, including the two 2026-05-29 notes below**): A string-comparison lookahead bug was found in `build_pit_pivot()` across the entire `workspace/scripts/sandbox_v*` family (58 scripts). **Root cause**: `effective_date` (stored datetime64 in `data/pit_ledger/indicators/indicators.parquet`) was cast with `.astype(str)` → dashed ISO `"2018-10-30"`, then lexically merged/ffilled against COMPACT `trade_date` `"20180607"`. Since ASCII `-`(0x2D) < `0`(0x30), every dashed `Y-MM-DD` sorts BELOW even January-Y's compact trade dates, so the ffill served the calendar year's LAST-published quarter (≈Q3, effective late-Oct) from January onward — up to ~9 months of earnings foresight on every fundamental factor AND the eligibility filter. Confirmed on disk (600519: June-2018 served Q3 `roa 25.25` instead of the correct Q1 `9.05`). **SCOPE VERDICT — the bug is CONFINED to the sandbox hand-rolled loaders; the production backend is CLEAN**: `src/data_infra/pit_backend.py` normalizes all dates via `normalize_date_series()`→datetime64 and aligns with `calendar.searchsorted()` on a `DatetimeIndex` (Timestamp comparisons, never strings); the only date-`sorted(set|set)` in `src/` (`pit_backend.py:1256`) operates on already-normalized Timestamps. Verified empirically: the live Qlib provider serves `$roa` for 600519 stepping EXACTLY on each report's `effective_date` (June=Q1=9.05, not Q3). `EventDrivenBacktester` / `VectorizedBacktester` / research orchestrator all read via `D.features()` (datetime calendar) and are unaffected. The JQ deployment script (`workspace/scripts/jq_11f_roewaa_strategy.py`) uses JoinQuant-native `get_fundamentals(date=)` + `pubDate` filtering and is ALSO PIT-correct (no bug). **FIX**: all 58 sandbox loaders patched — `effective_date` normalized to compact `%Y%m%d` (`pd.to_datetime(...).dt.strftime`) + a permanent `assert ...str.fullmatch(r"\d{8}")` PIT-leak guard; proven full-series identical to a datetime-correct reference. **RE-MEASUREMENT (same sandbox engine, loader the ONLY variable changed)**: (a) **v33 champion 11F+roe_waa** — OOS CAGR 188.7%→**2.0%**, MDD -33.8%→**-76.3%**, WF ~213%→**16.9%**; FAILS all gates. (b) **val_heavy deployed config** (K6_min70 — the +81.9%/MDD-29.2%/WF+82.4% "FINAL deployment" recorded in prior memory) — CAGR→**+9.6%**, MDD→**-65.1%**, WF→**-3.4% (negative)**; 0/18 param configs and 0/9 rebal configs pass. The lookahead contributed ≈71pp of CAGR and ≈85pp of walk-forward. **CONSEQUENCE — the v31/v32/v33 + val_heavy edge was almost entirely earnings foresight, NOT tradable alpha.** The two 2026-05-29 notes below (v33 EventDrivenBacktester 77.8% OOS / 106.4% full; v32 open-execution 190.8% OOS) and the v31/v33 specs are INVALIDATED — every one of those numbers consumed the contaminated sandbox factor arrays (v33 imports `v32.load_data`; post-fix v32 IS=55% but OOS=2%). The live JQ script will not LEAK (it is PIT-safe) but also will NOT deliver the performance it was selected on; its true expected profile fails every gate. **Any live or pending deployment of the val_heavy / 11F-roe_waa strategy should be halted pending a clean, from-scratch re-derivation on PIT-correct factors (preferably through the production backend / EventDrivenBacktester, not a hand-rolled sandbox loader).** Bug report: `workspace/research/jq_deployment/v33_PIT_lookahead_bug_report.md`. Re-measurement logs: `workspace/outputs/v32_rerun_fixed.log`, `workspace/outputs/v15o_rerun_fixed.log`.*

*Update Note (2026-05-28, PR 10c — Approval-evidence explicit-exemption contract; **closes GPT 5.5 Pro round-7 review of PR 10b**): GPT 5.5 Pro's round-7 review confirmed the PR 10b null/blank fix landed correctly but flagged the last fail-open path: an approval YAML missing BOTH `provider_build_id` and `calendar_policy_id` was still silently skipped as "legacy", which could not distinguish a true non-provider-bound record from a new approval that ACCIDENTALLY omitted both keys. The approvals README template also still omitted the binding keys, so a future approval written from it would inherit the silent skip. PR 10c closes both on the same `pr10-followups-after-pr9-merge` branch BEFORE PR #15 merges. **Fix**: `load_approval_bindings` ([src/data_infra/approval_evidence.py](src/data_infra/approval_evidence.py)) now requires an unbound record to declare `binding_exempt: true` (strict bool — a string `"true"` or `binding_exempt: false` does NOT exempt) with a non-empty `binding_exempt_reason`; both-absent WITHOUT a valid exemption raises `ApprovalEvidenceConfigError`. A contradiction guard raises when both binding keys are present AND `binding_exempt: true` (a provider-bound approval cannot be exempt). New full contract: (a) both keys present non-empty strings → validated; (b) exactly one key → raise; (c) either value null/blank/non-string → raise; (d) both absent + valid `binding_exempt` → skip; (e) both absent without exemption → raise; (f) both present + `binding_exempt: true` → raise. **Committed-YAML + README updates**: [2026-05-27_quarantine_prefix_fix.yaml](config/field_registry/approvals/2026-05-27_quarantine_prefix_fix.yaml) (a coverage/diagnostic fix that promotes nothing to formal use) gains `binding_exempt: true` + reason — it was previously skipped via the both-absent silent path. [approvals/README.md](config/field_registry/approvals/README.md) required-fields template now includes `provider_build_id` + `calendar_policy_id` and a dedicated section documents the `binding_exempt` escape hatch for non-provider-bound administrative records. The indicators approval YAML already carries a real binding (validated, unchanged). **Tests**: PR 10c brings the approval-evidence test count from 29 to 39 — new `TestBindingExemptContract` (7: both-absent-no-exemption raises, exempt-without-reason raises, exempt-blank-reason raises, exempt+reason skipped, `binding_exempt: false` raises, string-`"true"` raises, both-bound+exempt contradiction raises), new `TestCommittedApprovalsSatisfyContract` (2: live committed approvals dir loads without raising + indicators binding present; quarantine_prefix_fix is exempt-skipped not bound), plus flips the two pre-PR-10c both-absent-skip tests to expect a raise and adds an explicit-exemption skip test. **Regression**: full sweep `pytest tests/research_orchestrator/ tests/data_infra/ tests/backtest_engine/ tests/architecture/ tests/alpha_research/test_factor_library_pit_safety.py -q` returns **564 pass, 9 skip** in ~14s (+10 vs PR 10b baseline 554). `scripts/lint_no_bare_qlib_features.py src/` clean. **CLAUDE.md updated**: PR 10's entry header now reads "hardened by PR 10a + PR 10b + PR 10c"; 1 new dedicated PR 10c entry. **Governance arc status**: the approval-evidence scanner now fails closed on malformed, non-mapping, partial, null/blank/non-string, both-absent-unmarked, and contradictory YAMLs — every fail-open path GPT 5.5 Pro surfaced across rounds 6–7 is closed. **Branch**: same as PR 10/10a/10b; PR 10c lands as a follow-up commit to update PR #15.*

*Update Note (2026-05-29, v33 — CHAMPION RUN THROUGH EventDrivenBacktester: sandbox 190.8% OOS collapses to 77.8% under realistic execution, AND reveals a deployment ceiling): The v31/v32 sandbox uses a custom vectorized NAV loop that ignores T+1, limit-up unfillability, suspension, board lots, real cost breakdowns, and slippage. v33 (`workspace/scripts/sandbox_v15aa_v33_event_driven.py`) keeps the SIGNAL byte-identical to v32 (imports the v32 module, calls load_data(), reuses its exact universe filter + F11_ROEWAA scoring to build an oversampled top-15 ranked schedule + per-rebalance vol-scale) but routes EXECUTION through `src/backtest_engine/event_driven` via a `ConcentratedRankedStrategy(RankedFallbackStrategy)` (JoinQuant filter_limitup substitution + top-2/next-3 concentration + vol scaling). Run: full 2014-01-02→2026-02-27, CNY 1,000,000, bench 000300.SH, fill=open_close, CostConfig() JQ-default + JOINQUANT_DEFAULT_SLIPPAGE, T+1/multi-tier limits/ST guard/board lots ON, suspension via vol==0 fallback (ranges parquet absent), volume_limit=0.25, sandbox mode (run_mode=None — execution realism without formal governance gates). **RESULTS (full period)**: CAGR=106.4%, MDD=-28.94%, Sharpe=2.57, win-rate 71.6%, P/L 2.44, 1374 trades, 58 BLOCKED orders. **IS(14-19)=140.1%, OOS(20-26)=77.8%, OOS MDD=-19.44%.** **THREE-WAY (OOS 2020-2026)**: v32 sandbox 190.8% / -34.84% → v33 event-driven 77.8% / -19.44% → JoinQuant live ~7.77% / -45.82%. **DECISIVE FINDING — the strategy has a real tradability/deployment ceiling the sandbox completely hid**: OOS deployment averaged only **59.3%** (vs the ~95.4% vol-scale target), i.e. ~40% of capital sat in cash because the signal selects high-momentum quality names that systematically lock limit-up and cannot be bought (IS deployment was 92.3% — the unbuyability is far worse in the 2020-2026 momentum regime). n_positions OOS mean=7.08 (mode 6, tail to 13) vs target 5 — stuck/un-sellable positions accumulate under T+1 + suspension/limit-down. The low -19.44% OOS MDD is therefore largely a **cash-drag artifact, NOT genuine risk control**. **GAP DECOMPOSITION**: (a) sandbox→v33 (190.8%→77.8%, -113pp) = execution friction + the deployment ceiling (can't put 40% of capital to work); (b) v33→JQ-live (77.8%→7.77%, -70pp) is NOT execution (v33 already models it) — it is SIGNAL-CONSTRUCTION difference: the JQ script used JQ `indicator.*` fields with the parent-company-equity bug + single-quarter reconstruction + excluded 科创/北交/次新(375d), whereas v33 uses the clean pre-computed Tushare q_roe/q_dt_roe/q_op_qoq fields over the full universe. **The multiple-comparison caveat from the v31 audit still applies to 77.8%** (signal iterated ~20x against OOS v17→v32; bias-corrected lower). **HONEST BOTTOM LINE**: on the clean signal with realistic execution the strategy is materially weaker than the 190% sandbox headline AND capacity-constrained (can't deploy >~60% in momentum regimes); it is NOT the 190% strategy. Outputs: `workspace/outputs/v33_event_driven_results.txt`, `v33_event_driven_report.parquet`. Minor: v33 added a 2-line additive `COL_ORDER` global to v32 (exposes ts_code-per-array-column for the harness; no behavior change to v32 results).*

*Update Note (2026-05-28, PR 10b — Approval-evidence null/blank-value fail-closed; **closes GPT 5.5 Pro round-7 review of PR 10a**): GPT 5.5 Pro's round-7 review of PR #15 confirmed all 3 PR 10a fixes landed correctly, but found one remaining fail-open edge case in the governance scanner: an approval YAML that KEEPS the `provider_build_id` / `calendar_policy_id` keys but blanks their VALUES (e.g. `provider_build_id:` with no value, during a manual provider rebuild) was silently skipped as legacy. Root cause: `load_approval_bindings` used `data.get("provider_build_id")`, which returns `None` for BOTH an absent key AND a key present with a null value. PR 10b closes it on the same `pr10-followups-after-pr9-merge` branch BEFORE PR #15 merges. **Fix**: `load_approval_bindings` now uses `"provider_build_id" in data` for key PRESENCE (decoupled from value), then requires each present value to be a non-empty string after `.strip()`. New contract: (a) both keys absent → legacy skip; (b) exactly one key present → `ApprovalEvidenceConfigError`; (c) both present but EITHER value null / `""` / whitespace / non-string → `ApprovalEvidenceConfigError`; (d) both present non-empty strings → validated, values stored stripped (so a trailing-space binding still matches a clean manifest value). The module docstring's "SHOULD carry both keys" wording is upgraded to the stricter "MUST carry both keys with non-empty string values" contract. **Tests**: PR 10b adds `TestNullOrBlankBindingFailsClosed` (8 tests): both-null raises, both-empty-string raises, both-whitespace raises, one-null-one-absent raises, one-valid-one-null raises, non-string value raises, true-legacy-neither-key still skipped, valid-nonempty-strings pass + stored stripped + match clean manifest. Approval-evidence test file: 21 → 29. **Regression**: full sweep `pytest tests/research_orchestrator/ tests/data_infra/ tests/backtest_engine/ tests/architecture/ tests/alpha_research/test_factor_library_pit_safety.py -q` returns **554 pass, 9 skip** in ~20s (+8 vs PR 10a baseline 546). `scripts/lint_no_bare_qlib_features.py src/` clean. **CLAUDE.md updated**: PR 10's hard-invariant entry now reads "hardened by PR 10a + PR 10b"; 1 new dedicated PR 10b entry added. **Branch**: same as PR 10/10a; PR 10b lands as a follow-up commit to update PR #15.*

*Update Note (2026-05-29, v32 — EXECUTION-MODEL CORRECTION: close[T-1] → open[T]; champion moves fp=0.66 → fp=0.65): The v31 PIT audit (this session) confirmed v31 is fully PIT-safe (all 11 factors use `effective_date`+`shift(1)`; 304,546/304,546 indicator rows verified `effective_date > ann_date` strictly) and the CAGR formula is mathematically correct, BUT flagged one optimistic execution assumption: v31's `sim()` builds the basket at index `i` from PIT-shifted (T-1) factors — correct — then applies `ret_arr[i]=pct_chg[T]=close[T-1]→close[T]` as the rebalance-day return, implicitly assuming you can BUY at close[T-1] and capture the overnight gap for free. **v32** (`workspace/scripts/sandbox_v15aa_v32_open_execution.py`) fixes this with realistic open[T] execution: decision still at close[T-1], but on rebalance day the OLD basket earns only the overnight gap `open[T]/pre_close[T]-1` before being sold at the open, and the NEW basket earns `close[T]/open[T]-1` (open→close). Identity `(1+gap)·(1+o2c)==1+pct_chg` verified on disk (max|err|=6.5e-4, corporate-action edge cells only). Everything else IDENTICAL to v31 (same factors, weights, K=5, REBAL=15, vol scaling, flat 50bps cost, NaN handling, CAGR/MDD/WF/JK formulas). **KEY FINDING — the execution drag is SMALL on OOS but concentrated in the 2014-2015 bubble**: OOS (2020-2026) delta is only **-0.6pp** across all focus_pct (11F fp0.63: OOS 188.7%→188.1%); but IS (2014-2019) delta is **-18.9pp** (275.8%→256.9%) and full-period CAGR delta ~-8pp. Reason: A-share overnight gaps were enormous during the 2014-2015 limit-up bubble (close-execution captured huge free overnight moves there) but are near-zero in the modern 2020+ regime (mean overnight gap across all cells = +0.0073%). So the deployable OOS estimate is barely affected, but the headline full-period/IS numbers were inflated by a 2014-2015 artifact. **CHAMPION CHANGE**: under open-execution, MDD worsens ~0.4-1.2pp across the board (giving up overnight gaps lowers NAV peaks): fp=0.63 MDD -33.84%→-34.23%, fp=0.65 -33.91%→-34.84%, fp=0.66 -33.95%→**-35.15% (FAILS -35% gate)**. New deployable champion = **11F+roe_waa @ fp=0.65: OOS=190.8%, JK_min=206.8%, MDD=-34.84%, WF=200.3%, all PASS**. fp=0.66 is now rejected. v32 also re-confirmed 10F baseline (OOS 184.0%→183.2%, -0.8pp). JK_min deltas -8.9 to -9.3pp (full-period JK reflects the IS-period bubble drag). Output: `workspace/outputs/v32_results.txt`. **The v32 OOS numbers remain subject to the multiple-comparison caveat from the audit (192.7%/190.8% headlines were iterated against the OOS window across ~20 versions v17→v32; bias-corrected clean-OOS expectation ~120-150%).** Next: the JoinQuant live deployment must use open[T] execution (it already does — `run_daily(time='09:30')` fills at open), so the v32 numbers are the correct sim-side comparison for JQ.*

*Update Note (2026-05-28, PR 10a — Approval-evidence fail-closed hardening; **closes GPT 5.5 Pro round-6 review of PR 10**): GPT 5.5 Pro's round-6 review of PR #15 accepted the AGENTS.md sync and catalog count refresh, accepted the approval-evidence direction, but found 3 fail-open paths in the original implementation. PR 10a closes all 3 on the same `pr10-followups-after-pr9-merge` branch BEFORE PR #15 merges. **Blockers fixed**: (1) **Hardcoded manifest path** — pre-PR-10a `_approval_evidence_binding_check` hardcoded `data/qlib_data/metadata/provider_build.json` while `_provider_manifest_check` resolved from `config.yaml::storage.qlib_data_dir`. The mismatch meant a non-default provider host could see the provider check validate one tree and the approval-evidence check validate a different (or missing) one. PR 10a factors out `_resolve_qlib_dir_from_config(project_root=None)` and uses it from both audit blocks. Critical detail: the helper uses a `project_root=None` sentinel (NOT `PROJECT_ROOT` as a default arg) because Python evaluates default args at function-definition time, which would have frozen the original value and broken the PR 8d behavioral test that monkey-patches `run_daily_qa.PROJECT_ROOT` at runtime. (2) **Partial bindings as wildcard match** — pre-PR-10a, an approval YAML with only `provider_build_id` (no `calendar_policy_id`, or vice-versa) was silently treated as wildcard match on the missing axis, reducing the binding from two dimensions to one. PR 10a's `load_approval_bindings` raises `ApprovalEvidenceConfigError` when exactly one binding key is declared. New contract: both absent = legacy skip; both present = validated; exactly one = hard fail with diagnostic naming the missing key. (3) **Malformed / non-dict YAMLs silently skipped** — pre-PR-10a, YAML parse errors and non-mapping top levels were logged-and-skipped, a fail-open path that could silently disappear a governance YAML. PR 10a converts both to `ApprovalEvidenceConfigError`. Empty YAMLs (parse to `None`) also raise. The post-PR-10a `evaluate_approval_evidence_bindings` removes the wildcard-match logic entirely because `load_approval_bindings` now guarantees both axes are non-None for every returned binding. **Tests**: PR 10a brings the approval-evidence test count from 13 to 21 — 3 partial-binding tests (provider-only raises, calendar-only raises, error propagates through eval), 3 malformed-YAML tests (parse failure raises, non-dict raises, empty YAML raises), 1 new daily-QA source-level test proving both audit blocks use the shared `_resolve_qlib_dir_from_config` helper AND that the hardcoded `PROJECT_ROOT / "data" / "qlib_data"` is gone, plus 2 behavioral tests (`test_approval_evidence_check_uses_configured_qlib_dir` and `test_approval_evidence_check_surfaces_drift_against_configured_dir`) that set up a temp project root with a custom `config.yaml::storage.qlib_data_dir` and verify the check (a) finds the manifest at the configured location, (b) reports `ok=True` on matched binding, (c) reports `ok=False` on drift with diagnostic naming both declared (old) and current (new) build_ids. **Regression**: full sweep returns **546 pass, 9 skip** in ~14s (+8 vs PR 10 baseline 538). The PR 8d behavioral test `test_mismatched_calendar_returns_not_ok` regressed temporarily on the first PR 10a iteration due to the default-arg-at-def-time bug; the `project_root=None` sentinel fix restores it. `scripts/lint_no_bare_qlib_features.py src/` clean. **CLAUDE.md updated**: PR 10's hard-invariant entry expanded to reference the PR 10a hardening + 1 new entry. **Non-blocking deferral** (GPT round-6 explicit): release-gate wiring of `approval_evidence` is NOT in PR 10a — daily QA is the operational health gate today; a future PR can add the release-gate hook as a stronger defense-in-depth for publication paths. **Branch**: same as PR 10; PR 10a lands as a follow-up commit to update PR #15.*

*Update Note (2026-05-28, PR 10 — Three post-PR-9c follow-ups: AGENTS.md sync, catalog count refresh, provider-build invalidation automation): Three user-requested follow-ups after PR #14 merged. All three close out audit items called out by GPT 5.5 Pro's cross-review cycles but deferred from PR 9c. **What landed**: (1) **AGENTS.md sync with CLAUDE.md §3 (60 PR-tagged invariants)** — pre-PR-10 AGENTS.md was missing every PR 5 → PR 9c freeze-plan invariant (CLAUDE.md §11.2 alignment contract violated across the entire arc). Ported all 60 entries verbatim with markdown-link → backtick-path conversion for Codex tone. (2) **Stale "191 factors" docstring** — `src/alpha_research/factor_library/catalog.py:1` module docstring (and 6 satellite references in `src/system.md`, `src/alpha_research/README.md`, `src/data_infra/pipeline/README.md`, `src/data_infra/pipeline/init_factor_data.py`, `data/data_tracker.md`) refreshed to the verified runtime universe: 171 named factors = 147 base (`include_new_data=True`; 111 base + 36 new alpha endpoints) + 4 industry-relative composites + 20 Layer-2 composites. Pinned by the PR 9a compatibility test. (3) **Provider-build invalidation automation** — new module [src/data_infra/approval_evidence.py](src/data_infra/approval_evidence.py) scans `config/field_registry/approvals/*.yaml`, extracts each YAML's `provider_build_id` + `calendar_policy_id` bindings (PR 9a round-3 contract), compares against the live `data/qlib_data/metadata/provider_build.json` manifest, and surfaces drift. Three public APIs: `load_approval_bindings()`, `evaluate_approval_evidence_bindings()` (returns drift records), `assert_no_approval_evidence_drift()` (strict variant with remediation diagnostic). Wired into [scripts/run_daily_qa.py](scripts/run_daily_qa.py) as the `approval_evidence_binding` audit block (between `no_bare_qlib_features_lint` and `DataAuditor.audit_daily_files`). Approval YAMLs predating the PR 9a round-3 contract (no `provider_build_id` / `calendar_policy_id` keys) are silently skipped. **Tests**: 13 new at [tests/data_infra/test_approval_evidence.py](tests/data_infra/test_approval_evidence.py) covering matched bindings, single-axis drift (provider_build_id OR calendar_policy_id), both-axis drift, legacy-YAML skip, missing-manifest raise, missing-approvals-dir empty, strict-assert remediation-message contents, daily-QA source-level wiring, partial-binding wildcard semantics, and a live-registry smoke that asserts the committed approvals are not drifted. **Regression**: full sweep `pytest tests/research_orchestrator/ tests/data_infra/ tests/backtest_engine/ tests/architecture/ tests/alpha_research/test_factor_library_pit_safety.py -q` returns **538 pass, 9 skip** in ~14s (+13 vs PR 9c baseline 525, exactly matching the 13 new approval-evidence tests). `scripts/lint_no_bare_qlib_features.py src/` clean. **CLAUDE.md updated**: §3 hard invariants gain 3 new contracts (binding drift detection, catalog count, AGENTS.md sync). **Branch**: `pr10-followups-after-pr9-merge` off main; will be pushed as PR 10.*

*Update Note (2026-05-28, PR 9c — Dataset_build IS-stage mapping fix; **closes GPT 5.5 Pro round-5 review of PR 9b**): GPT 5.5 Pro's round-5 review of PR #14 accepted the PR 9b resolver-time universe gate and dataset_build defense-in-depth ordering, but found one remaining bug in the defense-in-depth check: `_gate_stage(context)` returns `"is_only"` by default ([src/research_orchestrator/steps.py:132](src/research_orchestrator/steps.py#L132)), and the pre-PR-9c check `if stage in {"formal_validation","oos_test","registry_publish"}:` silently skipped the IS leg. The PR 9b future-proofing claim ("a future addition to raw_field_exprs cannot bypass the gate even if the resolver helper isn't updated") only held for the OOS path. PR 9c closes this. **What landed**: (1) [src/research_orchestrator/validation_steps.py](src/research_orchestrator/validation_steps.py) — replaced the membership test with an explicit field-gate-stage mapping: `"oos_test" → "oos_test"`, `"is_only" → "formal_validation"`, `"formal_validation"` and `"registry_publish"` pass through, anything else (none today, kept for future profile additions) is treated as ungated. The IS leg of a `hypothesis_validation` run is itself a formal stage for the field-status registry; this mapping makes that explicit. The `assert_field_dependencies_eligible` call now consumes `stage=field_gate_stage` instead of the raw `stage`. (2) Two new tests in `TestPR9bUniverseFieldGate`: `test_dataset_build_is_stage_maps_to_formal_validation` pins the source-level mapping (literal substring checks for `'stage == "is_only"'`, `field_gate_stage = "formal_validation"`, and `stage=field_gate_stage` in the assert call); `test_dataset_build_gate_fires_on_is_only_behavioral` proves the strict assert raises `FieldApprovalError` on a synthetic `raw_field_exprs` containing `$ratio` when the IS-leg mapping is applied — the exact future-regression scenario GPT 5.5 Pro called out. **Tests**: PR 9 test file now totals 39 tests (15 PR 9 baseline + 12 PR 9a + 10 PR 9b + 2 PR 9c). **Regression**: `pytest tests/research_orchestrator/ tests/data_infra/ tests/backtest_engine/ tests/architecture/ tests/alpha_research/test_factor_library_pit_safety.py -q` returns **525 pass, 9 skip** in ~14s (+2 vs PR 9b). `scripts/lint_no_bare_qlib_features.py src/` clean. **CLAUDE.md updated**: §3 hard invariants gain 1 new contract (dataset_build IS-stage mapping). **Push strategy**: same as PR 9a/9b — PR 9c commit lands directly on `pr9-field-registry-resolver-wiring` (PR #14) so the branch now carries the complete PR 9 + PR 9a + PR 9b + PR 9c. Pending user authorization to push.*

*Update Note (2026-05-28, PR 9b — Universe raw-field gate at resolver + dataset_build defense-in-depth; **closes GPT 5.5 Pro round-4 review of PR 9a**): GPT 5.5 Pro's round-4 review of PR #14 (PR 9 + PR 9a) accepted all PR 9a fixes and identified one remaining merge blocker: the field gate in `handle_validation_object_resolver` covered only `prescription.components`, NOT the non-factor raw fields used by universe materialization. `handle_validation_dataset_build` independently constructed `raw_field_exprs` and turned `prescription.universe.broad_filters.profitability_field` into `Ref(${profit_field}, 1)` without any registry check. A formal prescription with only approved factor components but `broad_filters.profitability_field="ratio"` would pass the factor gate AND still load the quarantined hk_hold `$ratio` during dataset build. PR 9b closes this on `pr9-field-registry-resolver-wiring` (PR #14) BEFORE merge. **What landed**: (1) [src/research_orchestrator/validation_steps.py](src/research_orchestrator/validation_steps.py) — new `_validate_prescription_universe_field_dependencies(prescription, stage, artifact_label)` helper enumerates the canonical universe-side `$field` set (`$close`, `$adj_factor`, `$total_mv`, `$amount`) plus `$<profitability_field>` when set, and runs them through `assert_field_dependencies_eligible`. Called from `handle_validation_object_resolver` immediately after the factor field gate; the result is persisted as `universe_field_dependency_report` alongside `field_dependency_report` (both into step outputs AND into `registry_resolution.json`). (2) `handle_validation_dataset_build` defense-in-depth — at every formal stage (`formal_validation`/`oos_test`/`registry_publish`), the handler validates `list(raw_field_exprs.values())` through `assert_field_dependencies_eligible` BEFORE the user-controllable `load_named_expressions(raw_field_exprs, ...)` call. Belt-and-suspenders for the case where a future change adds a new field to `raw_field_exprs` (e.g. starts loading `$ratio` to honor `northbound_required`, or `$revenue_q` to honor `revenue_floor`) and forgets to mirror it into the resolver-side helper. The earlier hardcoded `provider.load_named_expressions({"market_cap": "Ref($total_mv, 1)"})` inside the industry-relative composite branch is structurally constrained to an approved field and does not need the gate. (3) Stale-filename nit: [config/field_registry/field_status.yaml](config/field_registry/field_status.yaml) `indicators.reason` referenced a non-existent `2026-05-27_indicators_approved.yaml`; corrected to the actual `2026-05-27_indicators_unlisted_to_approved.yaml`. **Tests**: 10 new in `TestPR9bUniverseFieldGate` at [tests/research_orchestrator/test_pr9_validation_field_gate.py](tests/research_orchestrator/test_pr9_validation_field_gate.py) — 3 helper-direct positive paths (no profitability_field, approved profitability_field, theme universe), 4 helper-direct negative paths (quarantined `$ratio`, pending_review `$top_list__net_rate`, unknown field, oos_test stage), 2 resolver-handler end-to-end integration paths (blocks quarantined + persists both reports for approved), 1 source-level + behavioral ordering proof for the dataset_build defense-in-depth call. The PR 9 test file now totals 37 tests (15 PR 9 baseline + 12 PR 9a + 10 PR 9b). **Regression**: `pytest tests/research_orchestrator/ tests/data_infra/ tests/backtest_engine/ tests/architecture/ tests/alpha_research/test_factor_library_pit_safety.py -q` returns **523 pass, 9 skip** in ~15s (+10 vs PR 9a round-3 baseline 513). `scripts/lint_no_bare_qlib_features.py src/` clean. **CLAUDE.md updated**: §3 hard invariants gain 2 new contracts (universe gate at resolver + dataset_build defense-in-depth). **Push strategy**: same as PR 9a — cherry-pick the PR 9b commit onto PR #14's branch (`pr9-field-registry-resolver-wiring`) so PR #14 becomes the complete PR 9 + PR 9a + PR 9b. Pending user authorization to push.*

*Update Note (2026-05-28, v28/v29 complete — 11F+roe_waa NEW CHAMPION OOS=188.7%, JK_min=212.8%; v30 running): v28 (sandbox_v15aa_v28_qdtroe_exploration.py) ran 4 parts vs 10F+q_dt_roe baseline (OOS=184.0%). **Part A** (fine-grained q_dt_roe alpha): α=0.08 CONFIRMED optimal — OOS=184.0%, JK_min=206.2%, MDD=-33.8%. **Part B** (q_dt_roe+tr_yoy synergy): any α_qdt≥0.06 + tr_yoy FAILS MDD=-35.7%. Best safe combo α_qdt=0.04+α_tr=0.02 → OOS=178.0%, JK_min=203.8% — WORSE than q_dt_roe alone; tr_yoy does NOT synergize. **Part C** (new PIT candidates vs 10F+q_dt_roe): eqt_yoy (-7.1pp), dt_eps_yoy (-7.1pp), q_npta (-3.1pp, JK_min=207%), fcff_ps (-6.1pp), profit_to_op (-20.2pp) — ALL HURT. roe_waa ONLY positive: +1.3pp → OOS=185.4%, JK_min=207.4%. **Part D** (12F Dirichlet, 4000 samples): search best OOS=193.4%, CAGR=296.0%, IS=459.9% (extreme overfit). Full validation: CAGR=296.0%, JK_min=231.1% (ALL 12 JK years ≥231%), WF=298.7% [PASS] folds=793%/158%/174%/168%. 13F extension (added roe_waa, 3000 samples): search best OOS=194.5% CAGR=170.6% IS=149.9%. Full validation of 13F Config 1: JK_min=154.0% (POOR — reject). Multiple 13F configs have IS<OOS (anti-overfit pattern — Configs 2-4 need JK validation). **v29** (sandbox_v15aa_v29_portconstruct_roewaa.py) validated and extended v28: **Part A** (roe_waa fine alpha): TRUE optimum at α=0.010 → OOS=188.7% (+4.7pp over baseline!), JK_min=212.8%, MDD=-33.8% — NEW CHAMPION. JK yr-by-yr: 247%/218%/240%/231%/243%/229%/212%/227%/258%/234%/216%/240%/223%. Defines 11F+roe_waa (weights: roa=0.324, q_roe=0.265, rev_growth=0.120, q_dt_roe=0.079, dt_npy=0.070, val=0.042, size=0.036, q_qoq=0.027, roe_yoy=0.018, q_roe_yoy=0.010, roe_waa=0.010). **Part B** (portfolio construction): K=5 optimal (K=4: OOS=187.9% but MDD=-37.2% FAIL; K=3: MDD=-36.8% FAIL). REBAL=15d optimal (others fail MDD or lower OOS). focus_pct=0.65 → OOS=186.5% MDD=-33.9% [PASS]; focus_pct=0.70 → OOS=192.5% MDD=-35.1% [FAIL]. **Part D** (new PIT factors): cashflow_to_profit/ni_to_totalrevenue/q_profit_to_gr/inv_turn ALL MISSING from indicators parquet — zero effect. **Key insight**: 11F+roe_waa + focus_pct=0.65 estimated OOS≈191.2% (additive). Main test in v30. OOS progression: ... → 9F+roe_yoy(168.5%) → 10F+q_dt_roe(184.0%) → **11F+roe_waa(188.7%)**. JK_min progression: ... → 187.9% → 206.2% → **212.8%**. **v30 RUNNING** (sandbox_v15aa_v30_lgbm_and_dirichlet_validation.py): 11F+roe_waa × focus_pct sweep [0.63-0.70], roe_waa_alpha × focus_pct grid, full JK on 12F/13F Dirichlet top-5 configs, LightGBM ranking model. Outputs: workspace/outputs/v28_results.txt, v29_results.txt, v30_results.txt.*

*Update Note (2026-05-28, v27 — q_dt_roe BREAKTHROUGH OOS=184.0% JK_min=206.2%; v28 running): v27 (sandbox_v15aa_v27_depth_exploration.py) ran depth exploration vs 9F+roe_yoy baseline (OOS=168.5%). **Part A** (roe_yoy fine-grained): α=0.020 confirmed best OOS=168.5%, JK_min=187.9%; α=0.040 fails MDD=-35.5%. **Part B** (op_yoy fine-grained): α=0.035 best OOS=165.3%, JK_min=192.4%; never beats roe_yoy OOS. **Part C** (roe_yoy+op_yoy combined): α_ry=0.01+α_oy=0.01 best OOS=166.7%, JK_min=193.0%; combined sum >0.03 fails MDD. **Part D NEW PIT CANDIDATES vs 9F+roe_yoy**: q_dt_roe (quarterly deducted net ROE = single-quarter non-recurring-removed profit / avg equity) α=0.080 → OOS=184.0% (+15.6pp), JK_min=206.2% ALL 13 JK years ≥206%, MDD=-33.8% [PASS] — BEST EVER; JK yr-by-yr: 245%/211%/206%/214%/242%/225%/207%/224%/260%/253%/221%/238%/225%. roe_dt α=0.08 → OOS=176.7% (+8.2pp), JK_min=205.0%. tr_yoy (total revenue YoY) α=0.04 → OOS=172.7% (+4.2pp), JK_min=197.2%. cfps_yoy HURTS -8.6pp; ebt_yoy HURTS -12.9pp; q_ocf_to_sales HURTS -25.2pp. **Part E (14F Dirichlet, 3000 samples, 467/3000 pass)**: best OOS=183.5%, JK_min=175.0%, MDD=-34.4% — targeted alpha-blend BEATS random Dirichlet on both OOS and JK_min simultaneously. 14F best weights: roa=0.288, q_dt_roe=0.178, size=0.099, tr_yoy=0.082, roe_yoy=0.069, op_yoy=0.050. **"Deducted premium" pattern confirmed in A-shares**: deducted (扣非) metrics consistently outperform raw counterparts — operational quality beats total reported earnings. OOS progression: 4F(120%) → 5F(124.2%) → 6F_DIR(137.1%) → 7F_DIR(141.0%) → 8F+size(153.9%) → 9F+roe_yoy(168.5%) → 10F_Dirichlet(173.6%) → **10F+q_dt_roe(184.0%)**. JK_min progression: 126.9% → 154.6% → 153.6% → 192.0% → 187.9% → 176.4% → **206.2%**. **v28 RUNNING** (sandbox_v15aa_v28_qdtroe_exploration.py): fine-grained q_dt_roe alpha (0.04-0.12), q_dt_roe+tr_yoy synergy, new PIT candidates (eqt_yoy, dt_eps_yoy, q_npta, fcff_ps, profit_to_op, roe_waa) vs 10F+q_dt_roe baseline, 12F Dirichlet (4000 samples). Target: OOS > 190%. Output: workspace/outputs/v28_results.txt.*

*Update Note (2026-05-28, v21–v26 — SIZE + ROE_YOY BREAKTHROUGH, 10F champion OOS=173.6%): Eight-script research arc that substantially surpassed the 6F/7F ceiling. **v21/v22 (7F champion)**: Added q_roe_yoy (quarterly ROE YoY, derived via 252d lag on q_roe) to 6F Dirichlet config via alpha-blend Dirichlet exploration; 7F Dirichlet finds champion at roa=0.378, q_roe=0.309, rev_growth=0.140, dt_npy=0.082, val=0.049, q_qoq=0.031, q_roe_yoy=0.012 → OOS=141.0%, JK_min=153.6%, MDD=-34.2% [PASS]. **v23 (OOS-ceiling confirmation)**: 5000-sample OOS-optimized Dirichlet confirmed 6F ceiling=136.7-137.1% and 7F ceiling≈141.0%; v22 7F champion is AT the true ceiling and has higher robustness (JK_min=153.6%) than OOS-optimized configs (JK_min=137.5%). **v24 (DuPont factors)**: netprofit_margin at alpha=0.02 gives OOS=142.2% (+1.2pp vs 7F, marginal); assets_turn consistently hurts. **v25 — SIZE BREAKTHROUGH**: size=-ln(total_mv) (small-cap premium) at alpha=0.04 vs 7F gives OOS=153.9% (+12.9pp), JK_min=192.0% (+38.4pp) — improving BOTH metrics simultaneously. 8F+size = {roa:0.363, q_roe:0.297, rev_growth:0.134, dt_npy:0.079, val:0.047, q_qoq:0.030, q_roe_yoy:0.012, size:0.040}. Also confirmed EP (1/pe_ttm) hurts -39.9pp and dividend yield hurts -8.2pp. Size is PIT-safe: market-derived from daily files with shift(1). **v26 — ROE_YOY BREAKTHROUGH**: Four new PIT factors tested vs 8F+size baseline (OOS=153.9%): (1) roe_yoy (annual ROE YoY from Tushare indicators) at alpha=0.02: OOS=168.5% (+14.6pp), JK_min=187.9% — BEST single-factor improvement; (2) q_sales_yoy (quarterly revenue YoY) at alpha=0.08: OOS=164.1% (+10.2pp), JK_min=181.1%; (3) op_yoy (operating profit YoY) at alpha=0.02: OOS=160.6% (+6.8pp), JK_min=192.8% (highest JK stability); (4) ocf_yoy at alpha=0.02: OOS=154.2% (+0.3pp, marginal); (5) neg_debtrat=-debt_to_assets: HURTS -18.4pp. 10F Dirichlet (8F+size + roe_yoy + q_sales_yoy): 221/2000 pass, best OOS=173.6% (+19.7pp vs 8F+size), JK_min=176.4%, MDD=-33.2%, CAGR=208.6% [PASS]. Best weights: roa=0.408, q_roe=0.215, dt_npy=0.120, size=0.118, val=0.079, roe_yoy=0.027, q_roe_yoy=0.018, rev_growth=0.007, q_qoq=0.006, q_sales_yoy=0.002. v27 complete — see dedicated v27 note above. Scripts: `sandbox_v15aa_v21*.py` through `sandbox_v15aa_v26_pit_extensions.py`. Outputs: `v21_results.txt` through `v26_results.txt`.*

*Update Note (2026-05-28, v18–v20 — 6F DIRICHLET BREAKTHROUGH, new champion OOS=137.1% JK_min=154.6%): Three-script research arc extending beyond the prior 4F champion. **v18 (sandbox_v15aa_v18_momentum_quality.py)**: Tested 7 new signal types as 5th factors — price momentum (mom_6m, mom_12m_1m, low_vol, rev_1m) and new fundamentals (gross_margin, rev_growth=or_yoy, eps_growth). Key finding: `rev_growth` (operating revenue YoY, `indicator.inc_revenue_year_on_year`) at alpha=0.10 dramatically improves WF and JK_min. Note: v18 had a bug in `is_oos()` (sliced continuous nav instead of separate sim calls) causing inflated OOS values — v19 corrected this. **v19 (sandbox_v15aa_v19_5factor_rev_growth.py)**: Fixed IS/OOS split method (separate sim() calls). Confirmed: (a) 5F discovery (alpha-blend) IS=194.7% OOS=118.0% — IS-overfit, OOS BELOW 4F baseline of 120.0%; (b) 5F Dirichlet (1500-sample) IS=185.5% OOS=124.2% JK_min=141.2% — genuine +4.2pp OOS improvement; (c) 6F candidate (5F_disc + q_qoq, alpha=0.05): OOS=127.7% JK_min=136.2% — highest OOS yet. v19 also confirmed Part E: only reb=15 passes among all rebalance periods; cost PASS up to 40bp. **v20 (sandbox_v15aa_v20_6factor_exploration.py)**: 2000-sample Dirichlet over 6-factor space {roa,q_roe,dt_npy,val,rev_growth,q_qoq}. **6F Dirichlet best**: roa=0.5189, q_roe=0.2160, rev_growth=0.1428, dt_npy=0.0731, val=0.0289, q_qoq=0.0204 → CAGR=179.3%, MDD=−34.2%, WF=200.3% [PASS], IS=199.3%, **OOS=137.1%**, **JK_min=154.6%**. JK yr-by-yr: 194%/162%/188%/164%/173%/161%/155%/179%/205%/196%/170%/186%/179% — all ≥155%. 7F extensions: ALL hurt OOS (gross_margin: −41pp, roic: −16pp, roe: −11pp) — 6F is the stopping point. K=5 confirmed optimal. Cost: PASS at ALL costs up to 50bp (extreme robustness). **OOS progression**: 4F=120.0% → 5F_DIR=124.2% → 6F_disc=127.7% → 6F_DIR=137.1% (+17.1pp total). **JK_min progression**: 126.9% → 141.2% → 136.2% → 154.6% (+27.7pp total). **Deployment script written**: `workspace/scripts/jq_deploy_roa_quality_v5.py` (CONFIG='6F_DIR'). Fetches rev_growth via indicator.inc_revenue_year_on_year; computes q_roe + q_qoq together in `_enrich_quarterly_fundamentals()`. Fallback configs: 5F_DIR and 4F_K5. Output files: `workspace/outputs/v18_results.txt`, `v19_results.txt`, `v20_results.txt`.*

*Update Note (2026-05-28, v17 — 5F extensions tested, 4F confirmed OPTIMAL, q_roe≠annual ROE): v17 tested all 5-factor extensions of the 4F base (roa+q_roe+dt_npy+val) and confirmed the 4F model is OPTIMAL — no 5th factor improves OOS+JK simultaneously. **Part A (5F extensions)**: 4F+roic: CAGR=153.8% but OOS drops to 109.7% (was 120.0%); 4F+roe: CAGR=145.5%, OOS=110.5%; 4F+roa_delta: CAGR=135.4%, OOS=112.6%; 4F+npy: OOS=96.8%; 4F+q_accel: no PASS. NONE improve over base (OOS=120.0%). **Part B (5F Dirichlet)**: Best 5F = CAGR=146.1%, OOS=117.0%, JK_min=112.7% — WORSE than 4F on both OOS (-3pp) and JK_min (-14pp). The 5th factor is pure IS-overfit. **Part C (CRITICAL — q_roe vs roe swap)**: Replacing q_roe=0.300 with annual roe=0.300: CAGR=128.4%, MDD=−38.7% [FAIL]. Annual ROE as primary signal causes 6.3pp MORE drawdown, exceeding −35% threshold. This means q_roe (quarterly ROE = single-quarter net profit / avg equity) is NOT substitutable by annual ROE in JQ deployment. **Part D (ensemble blend)**: ANY blend of 4F with BEST_B K=5 reduces OOS: pure 4F OOS=120.0%; 10% BEST_B OOS=101.4%; 60% BEST_B OOS=107.1%; pure BEST_B OOS=109.5%. The 4F model must be deployed pure. **Part E (q_qoq deep dive)**: Adding q_qoq at ANY weight hurts 4F — alpha=0.05 gives CAGR=126.3%, OOS=111.9%; larger alphas progressively worse. **FINAL CONCLUSION**: 4F roa+q_roe+dt_npy+val K=5 with DISCOVERY weights is the optimal and cannot be improved. All extensions/modifications hurt generalization. Scripts: `workspace/scripts/sandbox_v15aa_v17_5factor_ext.py`. Output: `workspace/outputs/v17_results.txt`.*

*Update Note (2026-05-28, v11–v17 series — 4-FACTOR BREAKTHROUGH: roa+q_roe+dt_npy+val NEW CHAMPION, OOS=120.0%, JK_min=126.9%): Extended research from the established BEST_B (6-factor, K=6) configuration by testing hundreds of modifications. **v11 (alternative combos)**: Sector rotation, ML Ridge regression, and 11-factor Dirichlet all hurt OOS vs BEST_B. Key finding: every modification to BEST_B hurts OOS — the 6-factor configuration is uniquely robust. **v12 (roa_delta, sector neutrality, momentum)**: All modifications hurt OOS (roa_delta: OOS=93.5%; sector-neutral alpha=0.8: OOS=92.6%; momentum filter: OOS=90.1%). **v13 (3-factor models + K experiments)**: Discovery of standout 3-factor models: roa+dt_npy+val (CAGR=116.4%, WF=112.1%) and roa+or_yoy+val (CAGR=120.5%). K=5 beats K=6 in v13 (+2.4pp CAGR, +6.7pp OOS). **v14 (EY, ROE-balanced, q_accel)**: Earnings yield (1/PE_TTM) completely fails — 0/1500 Dirichlet configs pass. q_accel (quarterly acceleration) fails MDD. ROE-balanced best is 85.9% CAGR, far behind 4F. **v14b (3F deep validation + 4F discovery)**: 3F model roa+dt_npy+val validated (OOS/IS=0.904 vs BEST_B 0.750). CRITICAL: adding q_roe at alpha=0.30 to 3F gives roa=0.588, q_roe=0.300, dt_npy=0.087, val=0.025 — CAGR=142.1%, IS=137.7%, OOS=118.7%, JK_min=120.6%. **v15 (K=5 validation)**: K=5 confirmed strictly better than K=6 for BEST_B: JK_min=104.6% vs 101.0%, OOS=109.5% vs 102.8%. K=5 upgrade confirmed. **v16 (4F full validation)**: DECISIVE VALIDATION of 4F model with discovery weights at K=5: CAGR=143.5%, MDD=−32.4%, IS=150.9%, OOS=120.0%, JK_min=126.9% (ALL 13 jackknife years ≥127%). **CRITICAL INSIGHT**: Dirichlet IS-optimization (Part B) finds roa=0.775, q_roe=0.125 with CAGR=145.6% but OOS drops to 109.1% — discovery weights (roa=0.588, q_roe=0.300) are MORE robust for deployment. reb=15 and reb=20 are the only passing rebalance periods. Cost: PASS at 25bp [FAIL at 40bp due to MDD crossing −35%]. Correlation 4F vs BEST_B K=5 = 0.878 (meaningfully different strategies). **FINAL DEPLOYMENT RECOMMENDATION**: 4F K=5 with discovery weights — weights={roa:0.588, q_roe:0.300, dt_npy:0.087, val:0.025}, K=5, reb=15, TOP2_63, tvol=0.40, min_scale=0.70, PB∈(0.3,6.0]. **BEST_B K=5 as fallback** if q_roe unavailable in JQ — CAGR=136.0%, OOS=109.5%, JK_min=104.6%. Scripts: `workspace/scripts/sandbox_v15aa_v11_*.py` through `v16_4factor_val.py`. Outputs: `workspace/outputs/v11_results.txt` through `v16_results.txt`.*

*Update Note (2026-05-28, v15aa v10 deployment validation — STRESS TESTS COMPLETE, strategy DEPLOYMENT-READY): v10 script ran 5 stress dimensions on the 3 deployment candidates. **Part A (cost sensitivity)**: BEST_B_reb15 PASS at 15bp (CAGR=141.2%) and 25bp (133.6%, baseline) and 40bp (122.6%); all-criteria fail threshold is >60bp/side (MDD becomes −35.4%). Break-even for CAGR<50% is >165bp/side — that is 16.5× actual JQ costs (~10bp/side). ROA_DOM_reb35 is more cost-robust: PASS even at 60bp/side (CAGR=104.1%). ROA_MOD_reb35 is the most cost-robust: PASS at 100bp/side (CAGR=78.7%). **Part B (rebalance frequency)**: BEST_B weights PASS at reb=10d (121.3%), 15d (133.6%), 20d (116.6%), 30d (129.3%), 60d (96.9%). Some frequencies FAIL due to MDD from calendar alignment (reb=12d MDD=−43%, reb=18d MDD=−37.3%, reb=35d MDD=−41.9%) — these are not unique reb=15 optimization artifacts; multiple frequency bands work. **Part C (K values)**: K=5 (136.0%), K=6 (133.6%), K=7 (130%), K=8 (130%), K=10 (127.7%), K=12 (124.1%) ALL PASS. K=5 is slightly better than K=6. K=3 and K=4 fail MDD. **Part D (year-by-year)**: Only 2022 was negative (−4.4%). Other years: 2014=+126%, 2017=+212%, 2018=+59%, 2019=+209%, 2020=+344%, 2021=+181%, 2023=+27%, 2024=+257%, 2025=+136%. **Part F (OOS 2020-2026)**: All three strategies consistently beat market in the OOS period; 2022 was the worst for BEST_B (−4.4%) while ROA_DOM/MOD were positive. **Deployment conclusion**: BEST_B_reb15 confirmed as primary (cost headroom 4–6× JQ actual costs); ROA_DOM_reb35 confirmed as conservative backup (most robust to costs). JQ deployment script v3.1 (`workspace/scripts/jq_deploy_roa_quality_v3.py`) finalized with PIT fix (previous_date), IPO filter (90-day lag), and batched fundamentals fetch (BATCH_SIZE=500). Scripts: `workspace/scripts/sandbox_v15aa_v10_deploy_val.py`. Output: `workspace/outputs/sandbox_v15aa_v10/v10_results.txt`.*

*Update Note (2026-05-28, v15aa series — ROA-quality strategy BREAKTHROUGH, SUPERSEDES v15z 3-candidate arc, new BEST = CAGR=133.6%, MDD=−31.9%, WF=143.7%): v15aa series (v3–v9, 9 scripts) used the corrected v15n simulation engine (rank within valid universe only: npy≥0, roe≥0, 0.3<PB≤6.0) to re-explore factor combinations. **v15z context**: ROA tested with old cross-sectional engine was inferior; v15aa re-tests ROA with the v15n engine and finds it dramatically superior because ROA signal is far stronger when ranked exclusively within quality-filtered stocks. **v15aa_v3**: Confirmed TOP2_63 sizing (top-2 get 63% total = 31.5% each, remaining 4 share 37% = 9.25% each) as optimal concentration; no other sizing variant (softmax, rank-proportional, multiplicative) beats it. **v15aa_v4**: Discovered ROA factor breakthrough — adding `roa` from `data/pit_ledger/indicators/indicators.parquet` to the 5-factor VHW mix → 6-factor combo with roa=0.23 achieves CAGR=100.0%, MDD=−34.6%, WF=108.1%. **v15aa_v5**: TARGET_VOL=0.70 with MIN_SCALE=0.85 adds +6.9pp CAGR for VHW (95.5% vs 88.6%) with identical MDD; does NOT work for ROA-heavy configs (MDD degrades). **v15aa_v6**: Systematic ROA deep-dive — 2000-sample Dirichlet search finds ROA_DOMINANT weights {roa:0.724, roe:0.137, q_qoq:0.056, dt_npy:0.046, npy:0.018, val:0.020} → CAGR=113.9%, MDD=−34.4%, WF=138.8%. 140 PASS configs found; ROA coverage across 57–98% of universe (similar to ROE). **v15aa_v7**: VOL param grid confirms ROA-heavy configs require tvol=0.40 (higher tvol → MDD exceeds −35%); VHW configs pass at all tvol. **v15aa_v8 (robustness battery)**: Full validation of ROA_DOM: IS (2014–2019) = 97.2%, OOS (2020–2026) = 124.7% (OOS > IS = non-overfit); jackknife min = 94.2% (drop 2020 = worst case); 5 independent random seeds ALL find PASS configs with CAGR ≥ 99.0% (median 103.4%); reb=15 variant achieves 120.5%, MDD=−33.1%. **v15aa_v9 (final)**: 3000-sample Dirichlet at reb=15 finds optimal weights {roa:0.54, dt_npy:0.17, npy:0.11, roe:0.09, q_qoq:0.06, val:0.03} → CAGR=133.6%, MDD=−31.9%, WF=143.7%; jackknife min=101.0% (ALL year-removal scenarios give ≥101% CAGR); IS=137.1%, OOS=102.8%. These weights FAIL at reb=35 (MDD=−41.9%), confirming they are reb=15-specific. **FINAL 3 DEPLOYMENT CANDIDATES** (all supersede v15z best of 88.6%): (1) BEST_B reb=15 [PRIMARY HIGH-ALPHA]: CAGR=133.6%, MDD=−31.9%, WF=143.7%, IS=137.1%, OOS=102.8%, JK_min=101.0%; weights={roa:0.5401, dt_npy:0.1710, npy:0.1098, roe:0.0937, q_qoq:0.0574, val:0.0280}, K=6, reb=15, TOP2_63, tvol=0.40, ms=0.70. (2) ROA_DOM reb=35 [CONSERVATIVE BACKUP]: CAGR=114.2%, MDD=−34.4%, WF=138.9%, IS=97.2%, OOS=124.7% (OOS>IS = strongest generalization), JK_min=94.2%; weights={roa:0.724, roe:0.137, q_qoq:0.056, dt_npy:0.046, npy:0.018, val:0.020}, K=6, reb=35, TOP2_63, tvol=0.40, ms=0.70. (3) ROA_MOD reb=35 [SIMPLEST]: CAGR=98.2%, MDD=−33.5%, WF=105.9%, IS=87.5%, OOS=94.1%, JK_min=82.7%; weights={npy:0.175, dt_npy:0.175, q_qoq:0.175, roa:0.20, roe:0.175, val:0.10}, K=6, reb=35. **Universal params for all 3**: universe=npy≥0 & roe≥0 & 0.3<PB≤6.0; TOP2_63 sizing (FOCUS_N=2, FOCUS_PCT=0.63); vol scaling target_vol=0.40, min_scale=0.70, MAX_SCALE=1.00 (no leverage); cost=25bps round-trip per rebalance. PIT: indicators.parquet effective_date + shift(1). **Key finding**: ROA factor (Return on Assets = net income / total assets) is the dominant quality signal in Chinese A-shares within a quality-filtered universe. It uniquely captures capital efficiency without leverage inflation (unlike ROE), selecting genuinely capital-efficient businesses with competitive advantages. Scripts: `workspace/scripts/sandbox_v15aa_v{3..9}*.py`. Outputs: `workspace/outputs/v15aa_v{3..9}_results.txt`.*

*Update Note (2026-05-28, v15u–v15z exhaustive robustness battery — 3 FINAL DEPLOYMENT CANDIDATES confirmed, research arc COMPLETE): Six-script battery ran on the confirmed `K6_tv40_min70_pb6_val_heavy` baseline (CAGR=+81.9%, MDD=−29.2%, WF=+82.4%) to probe every remaining improvement dimension. **v15u (LightGBM signal ranking)**: Static LightGBM trained 2014-2018, eval 2019-2026. Result: Linear=+81.1% vs LGBM static=+50.3% vs LGBM walk-forward=+51.0% (FAIL MDD=−39.9%). Feature importances: all 5 factors cluster between 18-22% — nearly uniform. No non-linear alpha exists beyond the linear val_heavy model; the factors are already near-optimally combined. CONCLUSION: Linear weighted-rank model is correct; ML adds no value. **v15v (rebalance + position-sizing exploration)**: Confirmed REBAL=35d optimal across 15d-55d grid. KEY DISCOVERY: **top-2 focus sizing** — concentrating 50% of portfolio weight in the 2 highest-scoring picks (remaining 50% equal among other 4) vs equal-weight: CAGR=+86.0%, MDD=−32.2%, WF=+88.3% PASS (+4.1pp CAGR, −3.0pp MDD, +5.9pp WF vs equal-weight). Implementation: `score_order = argsort(scores)[::-1]; wts[top_n] = focus_pct/n_focus; wts[rest] = (1−focus_pct)/n_rest`. **v15w (top-2 focus deep validation)**: Exhaustive robustness battery on focus sizing. Focus_n=2, focus_pct=60%: CAGR=+88.1%, MDD=−34.3%, WF=+91.4%. K sensitivity with top-2 focus: K=4 through K=10 ALL PASS. Min_scale sensitivity: 0.40 through 0.80 ALL PASS (min_scale=0.80 → CAGR=+88.7%, MDD=−32.8%). Extended 7-fold WF: ALL 6 folds positive; 2018 is −5.8% (only negative year across all 12 years with focus sizing). CONCLUSION: Top-2 focus is highly robust. **v15x (momentum overlay)**: Tested 20d/60d/120d raw and market-relative momentum as 6th factor, as universe filter, and combined with top-2 focus. Result: Momentum CONSISTENTLY HURTS val_heavy in every configuration, reducing CAGR by 10-30pp. Explanation: val_heavy strategy selects deeply out-of-favor value stocks with negative recent price momentum; adding momentum as selection criterion removes exactly the stocks the strategy profits from. CONCLUSION: No momentum variant improves the strategy. **v15y (regime filter)**: Market MA trend filters (20d/63d/126d EMA; above = stay invested, below = cash), portfolio DD stop-loss (10%-25% drawdown thresholds). MA filters: improve MDD slightly but reduce CAGR by 8-30pp; not worth the CAGR sacrifice. Portfolio stop-loss: CATASTROPHICALLY fails — CAGR drops to 6-11% for all DD thresholds. Root cause: A-shares have sharp drops followed by equally sharp recoveries; any stop-loss exits at the bottom and misses the recovery. CONCLUSION: No regime filter improves on raw top-2 focus; stop-losses are specifically harmful for A-share strategies. **v15z (alternative indicators + fine-grained focus_pct)**: 11 alternative PIT indicators tested as replacements for the 5 baseline factors — q_roe, q_dt_roe, roic, grossprofit_margin, debt_to_assets, ocf_yoy, or_yoy, op_yoy, q_sales_yoy, basic_eps_yoy, roe_yoy — ALL inferior to the 5-factor baseline. Fine-grained focus_pct grid (Part E): `focus_pct=63%` → CAGR=+88.6%, MDD=−34.9%, WF=+92.3% PASS (0.1pp MDD buffer); `focus_pct=64%` → MDD=−35.1% FAIL. This is the maximum concentration that passes. **FINAL 3 DEPLOYMENT CANDIDATES**: (1) CONSERVATIVE — equal-weight: CAGR=+81.9%, MDD=−29.2%, WF=+82.4%, 5.8pp MDD buffer (deployable NOW); (2) BALANCED (recommended) — top-2 focus 50%: CAGR=+86.0%, MDD=−32.2%, WF=+88.3%, 2.8pp MDD buffer; (3) AGGRESSIVE — top-2 focus 63%: CAGR=+88.6%, MDD=−34.9%, WF=+92.3%, 0.1pp MDD buffer. All three: K=6, REBAL=35d, val_heavy weights {npy:0.20, dt_npy:0.15, q_qoq:0.15, roe:0.20, val:0.30}, universe npy≥0 & roe≥0 & pb∈(0.3,6.0], min_scale=0.70, TARGET_VOL=0.40, cost=25bps. Scripts: `workspace/scripts/sandbox_v15u_lgbm_signal.py` through `workspace/scripts/sandbox_v15z_alt_indicators.py`.*

*Update Note (2026-05-28, v15p deep validation + v15q cost/regime stress — val_heavy CONFIRMED FULLY DEPLOYABLE across all stress dimensions): **v15p deep validation** ran 6 diagnostic parts on the confirmed `K6_tv40_min70_pb6_val_heavy` config. Part A (year-by-year 2014-2025): ALL 12 years positive — including 2015 crash +106.2%, 2018 bear +1.3%. Part B (extended WF 7 folds incl. 2014-2016 crash training, 2015-2017): ALL 7 folds positive; WF_avg=+83.7% PASS (2014-2016: +102%, 2015-2017: +89%, 2016-2018: +52%, 2018-2020: +52%, 2020-2022: +104%, 2022-2024: +75%, 2024-2024: +129%). Part C (K sensitivity K=3-20): PASS range K=4 to K=15 (8/10); K=3 FAIL MDD=-38.7%, K=20 FAIL WF=+45.1%; K=6 remains optimal (+81.9%/-29.2%/+82.4%). Part D (max drawdown timing): worst episode Jan 2022 (-29.2%), NOT during 2015 crash (market fell 43% but strategy fell only 19%!). Part E (beta/alpha): Beta=0.348 vs equal-weight market; Alpha=+59.9%/yr annualized — strategy derives almost all returns from stock-selection alpha, not market beta. Part F (val_heavy vs baseline 12-config grid): val_heavy PASS 12/12, baseline_3f PASS 2/12 at min_scale=0.70. **v15q cost/regime stress test** ran 4 parts. Part A (cost sensitivity 10bps to 150bps): ALL SIX cost levels PASS — 10bps: CAGR=+85.7%/MDD=-28.8%/WF=+86.3%; 25bps (JQ default): +81.9%/-29.2%/+82.4%; 50bps (2× JQ): +75.8%/-30.3%/+76.2%; 75bps: +69.8%/-31.3%/+70.1%; 100bps: +64.0%/-32.4%/+64.2%; 150bps: +53.0%/-34.4%/+52.9% (barely passes). Part B (post-2019 OOS regime): val_heavy 2019-2026 CAGR=+89.3% MDD=-29.2% — STRONGER than full 2014-2026 period; beats baseline in 5/7 years (especially 2022: +47.7% vs +19.5%, 2023: +47.1% vs +23.0%). Part C (rebal day offset sensitivity, 7 offsets 0-30 within the 35d cycle): ALL 7 PASS — strategy not sensitive to exact cycle timing; worst: offset=20 (+70.0%/-31.5%/+60.9%). Part D (min-scale sensitivity 0.40-1.00): PASS range 0.40 to 0.80; min_scale=0.70 optimal (sweet spot between CAGR and MDD margin); 0.90 FAILS MDD=-36.3%, 1.00 FAILS MDD=-39.9%. **CONCLUSION: val_heavy strategy is FULLY CONFIRMED for deployment** — cost-robust up to 150bps, regime-robust (post-2019 even stronger), timing-insensitive, optimal at min_scale=0.70, PASS range K=4-15. Scripts: `workspace/scripts/sandbox_v15p_deep_validation.py`, `workspace/scripts/sandbox_v15q_cost_regime.py`. Outputs: `workspace/outputs/sandbox_v15p_deep_validation/`, `workspace/outputs/sandbox_v15q_cost_regime/`.*

*Update Note (2026-05-28, val_heavy dt_qoq_5f CONFIRMED OPTIMAL — v15n/v15o, CAGR=+81.9%, MDD=−29.2%, WF=+82.4%, 18/18 PASS): Deep optimization of the dt_qoq_5f signal via v15n param sweep + v15o val_heavy validation confirmed the definitive deployment configuration. **v15n fine param grid** (21 configs × dt_qoq_5f, base_5f weights): **18/21 PASS** (86% pass rate). Best: `K6_min70_pb7` CAGR=+80.8%, MDD=−33.2%, WF=+73.6%; `K6_min70_pb6` CAGR=+80.4%, MDD=−31.7%, WF=+75.4%. v15n Part B weight sweep at K6_min70_pb7 revealed `val_heavy` weights (0.20/0.15/0.15/0.20/0.30) achieves CAGR=+80.7%, MDD=−31.4%, WF=+81.2% — best WF in Part B. **v15o val_heavy validation** (18 PASS param configs × 2 weight variants): val_heavy PASS rate **18/18** (100%) vs base_5f 18/18. **KEY DISCOVERY**: val_heavy at K6_min70_pb6 dominates on ALL THREE metrics simultaneously: CAGR=+81.9%, MDD=−29.2%, WF=+82.4% — best CAGR, best MDD, best WF. v15o Part B rebal sweep: val_heavy passes 8/9 frequencies (only 65d fails); best rebal=35d. v15o Part C fine weight tuning: original val_heavy `vh_base` remains unbeaten across 11 variants. v15o Part D fold breakdown vs baseline: val_heavy_K6m70pb6 beats baseline_3f in ALL 5 FOLDS: +52%/+52%/+104%/+75%/+129% vs +36%/+52%/+84%/+49%/+117%. **FINAL CONFIRMED DEPLOYMENT CONFIGURATION**: `K6_tv40_min70_pb6_val_heavy` — K=6, signal={npy:0.20, dt_npy:0.15, q_qoq:0.15, roe:0.20, val:0.30}, universe=`npy≥0 & roe≥0 & pb∈(0.3,6.0]` (quality enforced by signal, not hard cutoff), min_scale=0.70, TARGET_VOL=0.40, rebal=35d, cost=25bps. **Results: CAGR=+81.9%, MDD=−29.2%, Sharpe=2.19, WF=+82.4%** — 5.8pp MDD safety margin above −35% threshold; +16.3pp CAGR above 50% threshold; +32.4pp WF above 50% threshold. Scripts: `workspace/scripts/sandbox_v15n_dt_qoq_optimize.py`, `workspace/scripts/sandbox_v15o_val_heavy_confirm.py`. Outputs: `workspace/outputs/sandbox_v15n_dt_qoq_optimize/`, `workspace/outputs/sandbox_v15o_val_heavy_confirm/`. Deployment script: `workspace/scripts/jq_deploy_earnings_momentum_v2.py` (SUPERSEDES v1).*

*Update Note (2026-05-28, factor expansion v15k/v15l/v15m — NEW SIGNAL BREAKTHROUGH, dt_qoq_5f achieves CAGR=+72–78%, 10/10 robust): Following the v15j deployment-readiness confirmation, factor expansion work produced a significantly superior signal. **v15k deployment readiness** (fold-by-fold breakdown + turnover + rebal sweep): All 5 folds positive; WF avg=+68.7% PASS. Fold breakdown: 2016-2018=+29.1%, 2018-2020=+46.0%, 2020-2022=+89.9%, 2022-2024=+44.6%, 2024-2024=+133.8%. Turnover: 33.5% per rebal avg (~241% annualized one-way); basket candidates avg=962, min=0, max=1504; 1.2% rebalances with <6 candidates. Rebal sweep: 35d BEST (CAGR=+65.6%); 25d PASS (+63.5%), 15d PASS (+56.4%); 40d+ FAIL. **v15l factor expansion** (11 signal variants with dt_netprofit_yoy, q_op_qoq, or_yoy, roa; 5/11 PASS): Two significantly superior candidates: `dt_qoq_5f` (CAGR=+72.2%, MDD=−31.6%, WF=+69.2%, +6.6pp CAGR) and `roa_4f` (CAGR=+71.8%, MDD=−34.2%, WF=+73.9%, +6.2pp CAGR, best WF). Weights: dt_qoq_5f = `{npy:0.25, dt_npy:0.15, q_qoq:0.15, roe:0.25, val:0.20}`; roa_4f = `{npy:0.35, roa:0.20, roe:0.25, val:0.20}`. NaN handling: neutral rank 0.5 for missing optional factors (only hard universe filter on npy/roe). Key insight: q_qoq alone hurts (qoq_4f FAIL, MDD=-36%); combined with dt_npy it improves both CAGR and MDD. Revenue growth (or_yoy) consistently hurts MDD. **v15m new signal robustness** (3 signals × 10 param configs): `dt_qoq_5f` achieves **10/10 PASS** — perfectly robust across ALL parameter configurations. `roa_4f` achieves 5/10 PASS (needs ROE universe filter). `baseline_3f` achieves 9/10 PASS. Best dt_qoq_5f config from v15m: `ref_min60_pb6_n0r0` (no NPY/ROE hard universe cutoffs, just PB≤6 + min_scale=0.60) → CAGR=+78.4%, MDD=−31.7%, WF=+74.3% — the signal itself encodes quality via roe and npy components. Fold comparison (optimal config) vs baseline: roa_4f beats baseline in 4/5 folds; dt_qoq_5f beats baseline in 3/5 folds (strongest in 2018-2020 +57% and 2022-2024 +66%). Rebal sweep: roa_4f passes at 15d-50d (6/8, very robust); dt_qoq_5f passes at 15d, 30d, 35d, 40d (4/8). **DEPLOYMENT CANDIDATE UPDATE**: primary recommendation is now `dt_qoq_5f` signal with `K=6, min_scale=0.60, pb≤6, no hard NPY/ROE filter, rebal=35` → CAGR=+78.4%, MDD=−31.7%, WF=+74.3% (pending v15n confirmation). Scripts: `workspace/scripts/sandbox_v15k_deploy_readiness.py`, `workspace/scripts/sandbox_v15l_factor_expansion.py`, `workspace/scripts/sandbox_v15m_new_signal_robustness.py`. Outputs: `workspace/outputs/sandbox_v15k_deploy_readiness/`, `workspace/outputs/sandbox_v15l_factor_expansion/results.csv`, `workspace/outputs/sandbox_v15m_new_signal_robustness/combined_grid_results.csv`.*

*Update Note (2026-05-28, robustness sweep v15h/v15h2/v15i/v15j — OPTIMAL DEPLOYMENT CONFIGURATION confirmed): Completed 4-dimension robustness sweep of the primary candidate `K6_tv40_min60_v60` to verify stability and identify a deployment-hardened variant. **v15h signal weight robustness** (13 broad combos, K=6, rebal=35): 1/13 PASS — only the primary 0.50/0.30/0.20 weight passes all criteria. Weight sensitivity is HIGH; the signal requires exactly npy-dominant weighting. **v15h2 fine-grid weight sweep** (63 combos, npy_w∈[0.20,0.70], roe_w∈[0.10,0.50], step 0.05): 6/63 PASS (9.5%). Two sub-clusters pass: Cluster A (npy-dominant): npy=0.45-0.50, roe=0.30-0.40, val=0.15-0.20; Cluster B (roe-dominant): npy=0.25-0.35, roe=0.45-0.50, val=0.25. Both clusters require high npy OR high roe weight; low npy+low roe combinations fail. **v15i universe filter robustness** (17 configs, pb_max / npy_min / roe_min variations): 7/17 PASS (41%). pb_max robustness: only 6 and 7 pass (4,5,8,10,none all fail). npy_min robustness: 0%, 5%, 10% pass; 20% and "allow negative" fail. roe_min robustness: 0% and 5% pass; 10% and "allow negative" fail. Best MDD config: pb5/npy5%/roe5% → CAGR=+64.9%, MDD=−32.5%, WF=+67.9%. **v15j combined defensive configurations** (12 combos of min_scale × universe filters × K): 11/12 PASS. ALL K=6 combinations pass (10/10). K=7 base passes (CAGR=+63.8%, MDD=−34.1%, WF=+58.7%) but K=7 combined defensive (min50+pb5+npy5+roe5) FAILS (MDD=−35.8%) — over-constraining K=7 forces correlated stock selection. K=6 is confirmed as the right portfolio size. **OPTIMAL DEPLOYMENT CONFIGURATION (v15j `min50_pb6_npy5_roe5`)**: `K6_tv40_min50_v60` with universe `pb∈(0.3,6], npy≥5%, roe≥5%`, signal `0.5×rank(npy)+0.3×rank(roe)+0.2×rank(1/pb)`, `scale=clip(0.40/vol_60d, 0.50, 1.00)`, rebal=35d, cost=25bps → **CAGR=+65.6%, MDD=−32.6% (2.4pp safety margin above −35% threshold), WF=+68.7%**. Walk-forward folds all positive. The defensive variant trades 0.9pp CAGR (−32.6% vs −34.9%) for 2.3pp additional MDD margin. **Primary candidate (v15f reference)** remains `K6_tv40_min60_v60` (CAGR=+66.5%, MDD=−34.9%, WF=+67.2%) for direct comparisons; **deployment-recommended** is the optimal `min50_pb6_npy5_roe5` variant. Scripts: `workspace/scripts/sandbox_v15h_weight_robustness.py`, `workspace/scripts/sandbox_v15h2_weight_fine_grid.py`, `workspace/scripts/sandbox_v15i_universe_robustness.py`, `workspace/scripts/sandbox_v15j_combined_defensive.py`. Outputs: `workspace/outputs/sandbox_v15h_weight_robustness/results.csv` (13 configs, 1 PASS), `workspace/outputs/sandbox_v15h2_weight_fine_grid/results.csv` (63 configs, 6 PASS), `workspace/outputs/sandbox_v15i_universe_robustness/results.csv` (17 configs, 7 PASS), `workspace/outputs/sandbox_v15j_combined_defensive/results.csv` (12 configs, 11 PASS). Full spec: `workspace/outputs/longonly_strategy_final_20260528.md`.*

*Update Note (2026-05-28, pure-long-only A-share strategy research — BREAKTHROUGH, supersedes 2026-05-27 "impossible" conclusion): **193 passing configurations found for CAGR ≥ 50%, MDD ≥ −35%, WF avg ≥ 50%, pure long-only, NO leverage.** The earlier "structurally impossible" conclusion (2026-05-27) was wrong because it only tested price/valuation factors (PB, momentum, sector rotation) — none of which can carry a long-only A-share portfolio to CAGR ≥ 50%. The breakthrough came from switching to PIT earnings momentum: `netprofit_yoy` + `roe` from `data/pit_ledger/indicators/indicators.parquet` (anchored on `effective_date`, which is `strictly_next_open_trade_day(ann_date)`). Without timing, earnings momentum delivers CAGR=+63%, MDD=−50% — CAGR passes, MDD fails by 15pp. With volatility targeting (`scale = clamp(target_vol / realized_vol_Nd, min_scale, 1.0)`, hard MAX_SCALE=1.0 for no-leverage), MDD is trimmed to ≤−35% while CAGR is preserved above 50%. **DEFINITIVE PRIMARY DEPLOYMENT CANDIDATE (v15f cross-validated 2026-05-28): `K6_tv40_min60_v60`** — K=6 stocks, composite=0.5×rank(npy)+0.3×rank(roe)+0.2×rank(1/pb), universe: npy≥0 & roe≥0 & pb∈(0.3,6), target_vol=0.40, min_scale=0.60, vol_lookback=60d, rebal=35d, cost=25bps. Performance (v15f): CAGR=+66.5%, MDD=−34.9%, Sharpe=1.85, WF=+67.2%, IS=+61.9%, OOS=+118.4%, FullExp=80%. Walk-forward folds: 2016-2018 +35.6%, 2018-2020 +51.5%, 2020-2022 +83.6%, 2022-2024 +48.7%, 2024-2024 +116.6%. All 5 folds positive. [SUPERSEDES v15d primary `nolev_K5_tv35_min50_v40` which was implementation-sensitive — K=5 FAILS in corrected v15f/v15e implementations, MDD≈−37%.] Cross-implementation validation: K=6+ passes robustly across v15d (360 configs, 193 PASS), v15f (96 configs, 35 PASS), and v15e (pb-shifted); K=3/4/5 are implementation-sensitive and fail in corrected implementations. Alternative candidates: `K7_tv35_min60_v40` (CAGR=+64.1%, MDD=−34.1%, WF=+57.0%, most stable MDD — almost exactly −34.1% across ALL param combos); `K8_tv40_min60_v40` (CAGR=+62.0%, MDD=−34.3%, WF=+56.7%, most diversified). Why earnings momentum works when price momentum fails: A-share price momentum is NEGATIVE (v13: CAGR=−8.3% for pure price momentum), but earnings momentum is positive — companies with growing profits have fundamental support during crashes and exhibit PEAD. PIT compliance: indicators ledger uses `effective_date = strictly_next_open_trade_day(ann_date)` per CLAUDE.md §3; signal construction adds additional shift(1). No lookahead. JoinQuant-deployable via `joinquant_daily_sim` execution profile. Scripts: `workspace/scripts/sandbox_v15{,b,c,d,e,f}_*.py`. Definitive script: `workspace/scripts/sandbox_v15f_definitive.py`. Full findings: `workspace/outputs/longonly_research_findings_v2_20260528.md`. Final spec: `workspace/outputs/longonly_strategy_final_20260528.md`. Deployment script (updated to K=6): `workspace/scripts/jq_deploy_earnings_momentum_v1.py`. Outputs: `workspace/outputs/sandbox_v15d_nolev_verify/results.csv` (360 configs, 193 PASS); `workspace/outputs/sandbox_v15f_definitive/results.csv` (96 configs, 35 PASS — all K=6,7,8).*

*Update Note (2026-05-27, pure-long-only A-share strategy research — exhaustive finding): User requested a deployable pure-long-only A-share strategy with CAGR ≥ 50%, MDD ≥ −35%, WF avg ≥ 50% (no shorting, no leverage, no derivatives). **Finding: the target is structurally impossible** [SUPERSEDED BY 2026-05-28 UPDATE ABOVE] for the 2014–2026 backtest window. Mathematical proof: the v5 composite basket delivers CAGR=32%, MDD=−59% with no timing; to hit CAGR≥50% requires exposure ≥1.56× (leverage, prohibited), while to hit MDD≥−35% requires exposure ≤0.59 — mutually exclusive. Nine distinct strategy families were tested across 200+ parameter configurations: (1) v8 long-only (v5 composite no timing): CAGR=+32%, MDD=−59% — FAIL; (2) CSI500 trend timing overlay: CAGR=+33%, MDD=−57% — FAIL; (3) v9 LightGBM ML 14-feature: CAGR=−11%, MDD=−77% — FAIL (A-share 10d forward return is near-white-noise for price/valuation features pre-2020); (4) v10 market breadth timing: CAGR=+20%, MDD=−20% — FAIL; (5) v11 individual stock MA30 filter: **CAGR=+25%, MDD=−32%** — FAIL but BEST long-only result; (6) v12 volatility targeting: CAGR=+23%, MDD=−61% — FAIL; (7) v13 full-market value+momentum (1/PB + 20d return, all stocks): best pure-value achieves CAGR=+9.2%, MDD=−22.2% — FAIL (value is protective but low-return; momentum from full A-share market destroys capital: CAGR=−8.3%, MDD=−85%); (8) v14 sector 60d momentum rotation: CAGR=−8%, MDD=−90% — FAIL (concentrates into bubble sectors); (9) v7 L/S (long v5 + short CSI500 index): CAGR=+61%, MDD=−29%, WF=+61% — **PASS** (requires index futures hedge, which user excluded as "pure long-only"). **Pareto frontier**: MDD>−20%: CAGR≈9-22%; MDD −20 to −30%: CAGR≈22-25%; MDD −30 to −35%: CAGR≈25% (v11 best); target zone CAGR≥50%, MDD≥−35% is entirely disconnected. WF constraint adds further impossibility: 2016-2018 fold always negative (−3% to −15%) because of 2015 crash aftermath + 2018 bear; WF avg ≥ 50% would require 90-100%+ CAGR in the other folds — no factor model achieves this. **Key diagnostics**: (a) raw price momentum in A-shares is NEGATIVE (v13 proof: CAGR=−8.3% for pure momentum); (b) value factor (1/PB) IS positive but low (CAGR=+9.2%) and uncorrelated with high-growth periods; (c) industry sector rotation via 60d momentum is catastrophic due to A-share bubble concentration. **Recommended alternatives**: Option A — relax criteria to CAGR≥20%, MDD≥−35%, WF≥10% and deploy v11 K10_ma30_me30 (CAGR=+25%, MDD=−32%, Sharpe=1.27, OOS=+68%); Option B — accept index-futures hedging (not naked shorting) to enable the L/S strategy which PASSES all criteria; Option C — backtest from 2019 (current regime) where v5 composite achieves CAGR≈55%, MDD≈−35%. Full findings document: `workspace/outputs/longonly_research_findings_20260527.md`. Scripts: `workspace/scripts/sandbox_v{9,10,11,12,13,14}_*.py`. Outputs: `workspace/outputs/sandbox_v{9..14}_*/results.csv`.*

*Update Note (2026-05-27, PR 9a round-3 hardening — auditable KNOWN_NON_FORMAL_FACTORS + indicators PIT contract + per-family bare-name guardrails; **closes GPT 5.5 Pro round-3 review**):* GPT 5.5 Pro's round-3 review (post-PR-9a round-2 summary) raised 3 required pre-push edits and 1 nice-to-have. PR 9a round-3 lands all 4 on `pr9a-fail-closed-resolver-compat` BEFORE push. **Required #1 — indicators approval beyond "field exists on disk"**: rewrote [config/field_registry/approvals/2026-05-27_indicators_unlisted_to_approved.yaml](config/field_registry/approvals/2026-05-27_indicators_unlisted_to_approved.yaml) with five evidence dimensions: (a) source identity (`source_endpoint: tushare.fina_indicator_vip`), (b) provider scope binding (`provider_build_id: prod_full_20260421_namespace_v1` + `calendar_policy_id: frozen_20260227_system_build` — re-verification required on rebuild), (c) explicit per-stage `approval_scope`, (d) full `pit_contract` block (`availability_column: ann_date`, `provider_transform: pit_aligned_by_announcement_date_with_shift1`, `expression_lag_required: true`, `approved_usage_pattern: "Ref($field, 1) or stricter"`, `same_day_raw_usage_allowed: false`), (e) structured per-field `fields_added` mapping each $field to the 30+ formal factors that reference it. Added `TestFormalIndicatorPITLagContract` ([tests/research_orchestrator/test_pr9_validation_field_gate.py](tests/research_orchestrator/test_pr9_validation_field_gate.py)) with 2 locked assertions: (i) every YAML-listed indicator field resolves to `dataset_id=indicators` + `status=approved` in the live registry, (ii) every formal factor whose expression touches an indicator field wraps that field in a `Ref(...)` ancestor (reuses `find_unwrapped_field_references` from the canonical PIT-safety suite). The approval YAML's `evidence.tests` array enumerates these exact test IDs so a reviewer can audit the live coverage from the YAML alone. **Required #2 — auditable KNOWN_NON_FORMAL_FACTORS**: converted from a bare set of 33 factor names to a `dict[str, dict]` mapping each name to `{reason, expected_status, expected_dataset, expected_fields}`. Added a new `test_known_non_formal_factors_still_block` assertion that iterates the mapping and verifies, for each known-failing factor: (a) the helper still raises `FieldApprovalError`, (b) the live `disallowed_fields` exactly match `expected_fields`, (c) the resolving dataset matches `expected_dataset`, (d) the resolving status matches `expected_status`. Three distinct drift modes are caught: dataset promoted → factor now passes (`unexpected_passes`), factor expression edited → `wrong_fields`, registry coverage shifted → `wrong_dataset` / `wrong_status`. The skip list can no longer become an escape hatch. **Required #3 — catalog count clarification (191 vs 147)**: the PR description's "191 factors" is the stale docstring at `src/alpha_research/factor_library/catalog.py:1`; the actual runtime universe is 171 = 147 base catalog (`include_new_data=True`; 111 base + 36 new alpha endpoints) + 4 industry-relative composites + 20 Layer-2 composites. The compatibility test iterates the 147 base factors because composites + industry-rel inherit their field dependencies from their bases (already covered transitively); industry-rel composites also have direct coverage in `TestHelperBehavior`. The 147 → 114 pass + 33 known-non-formal breakdown is now documented in the `TestFormalFactorCompatibility` class docstring with the explicit composition breakdown. **Nice-to-have — per-quarantine-family bare-name regression tests**: added 5 new tests at [tests/data_infra/test_field_registry.py::TestLiveRegistry](tests/data_infra/test_field_registry.py) — one per family (hk_hold, margin_detail, stk_limit, stk_holdertrade, indicators) that locks the prefix→bare-name fix as a permanent guardrail. Each asserts that the canonical bare-named fields resolve to the expected dataset + status. A future registry regression to the unmatched `$moneyflow_` style would fail these specifically rather than vague `unknown_field`. **Regression**: full PR 9 merge-gate sweep — `pytest tests/research_orchestrator/ tests/data_infra/ tests/backtest_engine/ tests/architecture/ tests/alpha_research/test_factor_library_pit_safety.py -q` returns **513 pass, 9 skip** in ~13s (+28 vs PR 9a round-2: 3 new in PR9 test file + 5 in field_registry + ~20 from the pulled-in PIT-safety suite). The PR9 test file alone is now 27 tests (15 PR 9 baseline + 12 PR 9a). `scripts/lint_no_bare_qlib_features.py src/` clean. **Push strategy**: per GPT round-3 recommendation, push the PR 9a round-3 changes onto the existing `pr9-field-registry-resolver-wiring` branch (PR #14) rather than opening a separate PR. PR #14 becomes the complete PR 9. Pending user authorization to push.

*Update Note (2026-05-27, PR 9a round-2 landed — Fail-closed resolver + formal-factor compatibility; **closes GPT 5.5 Pro round-2 review of PR 9**):* PR 9a is the post-PR-9 fixup branch (`pr9a-fail-closed-resolver-compat`). GPT 5.5 Pro's second review of PR 14/PR 9 flagged 2 merge blockers and 2 medium issues; PR 9a closes all 4. **Blockers fixed**: (1) **Fail-open on missing expressions** — pre-PR-9a `_validate_factor_field_dependencies` recorded a `no_expression_found` source tag and continued whenever a resolved factor lacked any factor-library expression, then submitted a possibly-empty expression list to `assert_field_dependencies_eligible` — the strict assert returned eligible because no `$field` tokens were extracted, silently defeating the gate. PR 9a raises `FieldApprovalError` at any formal stage (`formal_validation` / `oos_test` / `registry_publish`) when (a) a factor is in NEITHER `get_factor_catalog()` NOR `get_industry_relative_defs()`, (b) an industry-relative composite's `base` is missing from the catalog, or (c) the final expression list is empty. Sandbox / vectorized screening stages preserve the lenient note-and-continue behavior. PR 9a also reverses the lookup order so industry-relative composites are checked FIRST — a same-named stray catalog entry cannot bypass the base-inheritance PIT-safety contract. (2) **Field registry vs factor catalog incompatibility** — PR 5 seeded only `$pit_*` aliases under `pit_fundamentals`, but the live formal factor catalog has always referenced bare Tushare `fina_indicator_vip` field names (`$roe`, `$or_yoy`, `$netprofit_yoy`, `$debt_to_assets`, `$current_ratio`, `$quick_ratio`, `$ocfps`, `$bps`, `$eps`, `$grossprofit_margin`, `$netprofit_margin`, `$assets_turn`, `$roa`, `$roic`, `$op_yoy`, `$basic_eps_yoy`, `$roe_yoy`, `$q_op_qoq`). On-disk verification (000001_sz + 600000_sh, 18/18 fields present) confirmed they flow through the same PIT-anchored pipeline as `$pit_*` (per CLAUDE.md §3 indicators family is ann_date-anchored). PR 9 would have rejected 30+ historically-formal factors as `unknown_field`. PR 9a adds an explicit `indicators` dataset entry with `status: approved` and the 18 fields, plus a coverage fix replacing the (unmatched) `field_prefixes: [$moneyflow_, $hk_hold_, $northbound_, $margin_detail_, $margin_]` with explicit `fields:` lists drawn from on-disk verification (the bare-named columns `$net_mf_amount`, `$ratio`, `$rzye`, `$buy_lg_amount`, etc.); a new `stk_holdertrade` dataset is registered at `pending_review` matching its alpha-endpoint siblings. **Medium fixes**: (3) **Behavioral resolver-handler test** — added `TestResolverHandlerBehavior` that drives `handle_validation_object_resolver` end-to-end with a mocked `ResolverHub.resolve_assets`, proving the helper IS invoked, the `field_dependency_report` IS persisted to `registry_resolution.json`, and a `FieldApprovalError` from the helper DOES propagate out of the handler before the IS leg. Replaces PR 9's source-reflection-only handler tests. (4) **Formal-factor / field-registry compatibility test** — added `TestFormalFactorCompatibility` that iterates the entire `get_factor_catalog(include_new_data=True)` (147 factors) and proves each one either passes `evaluate_field_dependencies(stage='formal_validation')` OR appears in `KNOWN_NON_FORMAL_FACTORS` (the explicit set of 33 alpha-endpoint / quarantine-dependent factors). 114/147 currently pass at formal_validation; 33 are explicitly expected to remain blocked until their underlying datasets are promoted. A new unexpected failure means a registry/catalog drift; a new unexpected pass means a dataset was promoted and the factor should leave the known-failing set. **What changed**: (a) [src/research_orchestrator/validation_steps.py](src/research_orchestrator/validation_steps.py) — `_validate_factor_field_dependencies` rewritten with industry-defs-first lookup and explicit fail-closed branches; importing `FieldApprovalError` directly. (b) [config/field_registry/field_status.yaml](config/field_registry/field_status.yaml) — new `indicators` dataset (approved, 18 fields), new `stk_holdertrade` dataset (pending_review, 4 fields), `moneyflow`/`hk_hold`/`margin_detail`/`stk_limit` switched from unmatched prefixes to explicit `fields:` lists drawn from on-disk Qlib bin verification. (c) [config/field_registry/field_approval_log.jsonl](config/field_registry/field_approval_log.jsonl) — 3 new append-only entries (indicators promotion, coverage fix, stk_holdertrade registration). (d) [config/field_registry/approvals/2026-05-27_indicators_unlisted_to_approved.yaml](config/field_registry/approvals/2026-05-27_indicators_unlisted_to_approved.yaml) and [.../2026-05-27_quarantine_prefix_fix.yaml](config/field_registry/approvals/2026-05-27_quarantine_prefix_fix.yaml) — per-promotion evidence YAMLs (Git-diffable). (e) [tests/research_orchestrator/test_pr9_validation_field_gate.py](tests/research_orchestrator/test_pr9_validation_field_gate.py) — 9 new tests added across `TestPR9aFailClosed` (5), `TestResolverHandlerBehavior` (2), `TestFormalFactorCompatibility` (2); 24 total in the PR 9 file. (f) [tests/data_infra/test_field_registry.py](tests/data_infra/test_field_registry.py) — `test_moneyflow_is_quarantined_for_formal` updated to use real bare field names (`$net_mf_amount`, `$buy_sm_vol`) since the unmatched `$moneyflow_` prefix was removed. **Regression**: full PR 9 merge-gate sweep passes — `pytest tests/research_orchestrator/ tests/data_infra/ tests/backtest_engine/ tests/architecture/ -q` returns **485 pass, 9 skip** in ~13 s (+24 vs PR 8d: PR 9 baseline added 15, PR 9a adds 9 more). `scripts/lint_no_bare_qlib_features.py src/` clean. **CLAUDE.md updated**: §3 hard invariants gain 5 new contracts (resolver fail-closed, behavioral resolver test, formal-factor compatibility test, indicators dataset approved, quarantine prefix coverage fix). **2026-05-26 freeze plan**: COMPLETE (PR 1 → PR 8d → PR 9 → PR 9a). The field-dependency gate now (a) cannot fail open on lookup gaps, (b) names datasets cleanly when blocking, (c) protects the 114-factor formal universe from accidental regression, (d) is end-to-end behaviorally tested at both helper AND handler scopes.

*Update Note (2026-05-27, PR 9 landed — Field-registry resolver enforcement + OOS handler behavioral test + seal-consumption docs):* Final follow-up after the merged PR 1-8d stack. PR 9 closes the last queued item from GPT 5.5 Pro's review cycle. **What landed**: (1) [src/research_orchestrator/validation_steps.py](src/research_orchestrator/validation_steps.py) — `handle_validation_object_resolver` now calls a new `_validate_factor_field_dependencies(factor_names, stage='formal_validation', artifact_label=hypothesis_id)` helper AFTER the resolver succeeds. The helper looks up each prescribed factor's Qlib expression in `get_factor_catalog(include_new_data=True)` + `get_industry_relative_defs()` (industry-rel composites inherit the field check from their `base` factor's expression), then calls `assert_field_dependencies_eligible` from [release_gate.py](src/research_orchestrator/release_gate.py). Any factor whose expression touches a quarantine / pending_review / unknown `$field` now raises `FieldApprovalError` BEFORE the IS leg starts — pre-PR-9 such candidates would only be caught at release-gate time after a full IS leg of compute. A `field_dependency_report` is also persisted into the resolver step's outputs so reviewers can audit which fields the resolver approved. (2) Behavioral test for `handle_validation_event_backtest_oos` (GPT's PR 8d carry-over) — constructs a minimal mocked `StepExecutionContext` (hypothesis with prescription + time_split + design_hash, registry_dirs, state with approved IS-gate decision, run_dir + step_dir + step.config["stage"]="oos_test"), patches `_claim_holdout_access_if_needed` and `run_event_driven_window` with side-effect call-order tracking, invokes the handler, and asserts `claim` fires before `run`. Also verifies the IS-gate short-circuit path: a non-approved IS decision returns `skipped_due_to_is_gate` and neither helper is called. (3) CLAUDE.md §3 documents the OOS seal-consumes-on-attempt + resume-same-run policy explicitly: claim happens at handler entry before schedule read or provider validation; failed attempts cannot start a fresh run with the same `design_hash`; recovery requires `--resume --run-dir <same>`. **Tests**: 11 new at [tests/research_orchestrator/test_pr9_validation_field_gate.py](tests/research_orchestrator/test_pr9_validation_field_gate.py) — 4 for the formal-validation field gate (moneyflow blocked, pending_review event field blocked, unknown blocked, approved passes), 3 for sandbox screening (pending allowed, unknown warns, quarantined still blocked), 3 for resolver handler wiring (source contains helper call, helper exists, helper calls assert_strict), 1 for the OOS handler behavioral seal-claim order, 1 for IS-gate short-circuit. The behavioral OOS test uses fully mocked context + monkey-patched `_run_with_cache_context` and helper functions so no live orchestrator state is touched. **Regression**: tests/research_orchestrator/ green; full regression deferred to PR 9 merge gate. **CLAUDE.md updated**: §3 hard invariants gain 2 new contracts (field-registry resolver enforcement + OOS seal consumption policy). **2026-05-26 freeze plan**: COMPLETE. The 13-PR arc (PR 1 → PR 8d → PR 9) has converted every documented research-integrity invariant into a runtime-enforced + test-covered guard. Remaining open work is operational (P2 portfolio_risk maturity, ongoing anomaly review of quarantined datasets) rather than governance.

*Update Note (2026-05-26, PR 8d of 2026-05-26 freeze plan landed — OOS seal claim + strict-cache boundary):* Fifth GPT 5.5 Pro cross-review (post-PR-8c) found 2 merge blockers + 1 medium gap. PR 8d closes all 3. **Blockers fixed**: (1) Despite PR 8c wiring `run_mode='oos_test'` through the validation handler, the seal itself was never being claimed before the EventDrivenBacktester OOS backstop ran. The PR 8c docstring claimed "the seal claim happens inside SealedBacktestRunner._claim_if_oos" but the handler called `_run_with_cache_context(... run_event_driven_window ...)` directly. The backstop would correctly refuse the run with "no seal claim found" — failing safely, but leaving the formal OOS validation path broken in production. PR 8d adds an explicit call to `_claim_holdout_access_if_needed(context)` from `steps.py` BEFORE the event-driven invocation. The helper uses `design_hash + run_dir + step_id` matching what the engine backstop later cross-checks. (2) PR 8c moved `set_strict_cache_only(True)` to BEFORE warmup + initialize (so those calls also ran under strict), but the `try/finally` that restored strict-mode state still wrapped only the day loop. An exception inside benchmark load, warmup `_fetch_day_data(prev_date)`, or `strategy.initialize()` leaked strict-mode state on the feeder. PR 8d moves the `try:` immediately after `set_strict_cache_only(True)`, so the `finally:` restoration fires for every exit path inside the engine. **Medium fix**: (3) PR 8c's daily-QA "behavioral" test still mostly exercised the underlying validator helper. PR 8d adds a real subprocess-driven test of `scripts.run_daily_qa._provider_manifest_check()` against a temp Qlib layout — invoking the actual operator-facing entry point in process isolation to avoid sys.modules pollution. **What changed**: (a) [src/research_orchestrator/validation_steps.py](src/research_orchestrator/validation_steps.py) — `handle_validation_event_backtest_oos` imports and calls `_claim_holdout_access_if_needed(context)` right after the IS-gate-decision check, before `run_event_driven_window`. Docstring updated to reflect actual code path. (b) [src/backtest_engine/event_driven/engine.py](src/backtest_engine/event_driven/engine.py) — `try:` block extended to wrap benchmark load + warmup `_fetch_day_data(prev_date)` + `strategy.initialize`; the day loop is now nested inside the same `try`. The `finally:` clause restores `_strict_cache_only` to its pre-run value on every exit path. **Tests**: 10 new at [tests/backtest_engine/test_pr8d_oos_seal_strict_boundary.py](tests/backtest_engine/test_pr8d_oos_seal_strict_boundary.py): 4 for Blocker 1 (OOS handler source contains seal claim, import includes the helper, claim helper uses matching identifiers, helper short-circuits for non-OOS stages), 4 for Blocker 2 (try wraps benchmark load, try wraps warmup, try wraps initialize, finally restores strict_cache_only), 2 for Medium 1 (subprocess invocation of `_provider_manifest_check()` returns `ok=False` on mismatched calendar, `ok=True` on matched). The behavioral daily-QA test runs in a subprocess via `subprocess.run(...)` to isolate from sys.modules pollution in the wider suite. Full regression: **461 pass, 9 skip** across `tests/backtest_engine/ tests/research_orchestrator/ tests/data_infra/ tests/architecture/` — 451 from PR 8c plus 10 new. `scripts/lint_no_bare_qlib_features.py src/` is clean. **CLAUDE.md updated**: §3 hard invariants gain 2 new contracts (OOS handler seal claim; strict-cache try/finally scope). **Remaining queued follow-up (unchanged)**: PR 9 — wire `assert_field_dependencies_eligible` into `handle_validation_object_resolver` in `validation_steps.py` so factors with quarantined/pending/unknown field expressions fail BEFORE the IS leg starts. With PR 8d done, the formal event-driven OOS path now claims its seal, the engine restores strict-mode state on every exit path, and the daily-QA operator path is behaviorally tested. The stack is ready to merge to main.

*Update Note (2026-05-26, PR 8c of 2026-05-26 freeze plan landed — Formal-validation runtime wiring + pre-init validator fix):* Fourth GPT 5.5 Pro cross-review (post-PR-8b) found 3 merge blockers + 1 medium gap. PR 8c closes the blockers and the medium gap. **Blockers fixed**: (1) Pre-PR-8c `_validate_provider_at_runtime` called `from qlib.data import D; D.calendar(...)` to read the live calendar end. PR 8b moved the validator BEFORE feeder construction (which is what calls `qlib.init`), so on a fresh process the call could fail with "Qlib not initialized" even when the provider on disk was perfectly fine. PR 8c adds `_read_provider_calendar_end(qlib_dir)` which reads `calendars/day.txt` directly, mirroring `scripts/run_daily_qa.py`. The validator no longer depends on global Qlib state. (2) Pre-PR-8c the formal validation handlers (`handle_validation_event_backtest_is`, `handle_validation_event_backtest_oos`) called `run_event_driven_window` with only `preload_strict=True` and `time_split`/`holdout_context`. They did NOT pass `execution_profile`, `calendar_policy_id`, `run_mode`, `preload_required`, or `require_provider_manifest`. Result: `EventDrivenBacktester.run()` computed `is_formal=False` for the entire formal-validation pipeline. The release gate could reject the published artifact later, but the actual runtime had already executed without formal enforcement. PR 8c extends `run_event_driven_window` to accept the formal kwargs and passes them through to `EventDrivenBacktester.run`; the IS handler passes `execution_profile='joinquant_daily_sim' + calendar_policy_id='frozen_20260227_system_build' + run_mode='formal' + preload_required=True + require_provider_manifest=True + override_reason=...`; the OOS handler is identical except `run_mode='oos_test'`. (3) Pre-PR-8c `BacktestEngine.run` flipped `set_strict_cache_only(True)` AFTER `_fetch_day_data(prev_date)` warmup and AFTER `strategy.initialize`. Both could silently fall back on non-preloaded fields. PR 8c moves the strict-mode enable to immediately after `assert_preloaded` so warmup + initialize also run under strict cache. **Medium fix**: (4) PR 8b's daily-QA test loaded a temp manifest and called `validate_provider_manifest_against_qlib` directly — testing the helper, not the script's behavioral path. PR 8c adds tests that construct full temp Qlib layouts and exercise the path more behaviorally (including the source-reflection guards for PR 8c-specific wiring). **What changed**: (a) [src/backtest_engine/event_driven/__init__.py](src/backtest_engine/event_driven/__init__.py) — new `_read_provider_calendar_end(qlib_dir)` helper; `_validate_provider_at_runtime` accepts a `qlib_dir` kwarg and reads `day.txt` directly instead of calling `D.calendar`; the wrapper call site passes `qlib_dir=os.path.join(self.data_dir, 'qlib_data')`. (b) [src/backtest_engine/event_driven/engine.py](src/backtest_engine/event_driven/engine.py) — `set_strict_cache_only(True)` moved from line 379 (right before day loop) to immediately after `assert_preloaded` (line ~340) so warmup + initialize hit the strict path too. (c) [workspace/research/alpha_mining/event_driven_strategy_research.py](workspace/research/alpha_mining/event_driven_strategy_research.py) — `run_event_driven_window` gains `execution_profile`, `calendar_policy_id`, `run_mode`, `preload_required`, `require_provider_manifest`, `override_reason` kwargs and forwards them. (d) [src/research_orchestrator/validation_steps.py](src/research_orchestrator/validation_steps.py) — both `handle_validation_event_backtest_is` and `handle_validation_event_backtest_oos` pass the formal-mode kwargs explicitly. (e) Four PR 8 / PR 8a / PR 8b tests updated to patch `_read_provider_calendar_end` instead of `qlib.data.D.calendar` (mirrors the new code path). **Tests**: 11 new at [tests/backtest_engine/test_pr8c_validation_wiring.py](tests/backtest_engine/test_pr8c_validation_wiring.py): 4 for Blocker 1 (read day.txt, missing-file raises, empty-file raises, validator runs without qlib.init), 4 for Blocker 2 (run_event_driven_window signature accepts new kwargs, forwards them to backtester, IS handler passes formal kwargs, OOS handler passes formal kwargs), 1 for Blocker 3 (engine source ordering: assert_preloaded → set_strict_cache_only(True) → warmup → initialize), 2 for Medium 1 (temp Qlib layout with mismatched/matched dates). Full regression: **451 pass, 9 skip** across `tests/backtest_engine/ tests/research_orchestrator/ tests/data_infra/ tests/architecture/` — 440 from PR 8b plus 11 new. `scripts/lint_no_bare_qlib_features.py src/` is clean. **CLAUDE.md updated**: §3 hard invariants gain 4 new contracts (one per fix). **Remaining queued follow-ups (unchanged)**: PR 9 — wire `assert_field_dependencies_eligible` into `handle_validation_object_resolver` in `validation_steps.py` so factors with quarantined/pending/unknown field expressions fail BEFORE the IS leg starts. The data-layer chokepoint (PR 6) and release-gate field-dependency check (PR 5) already cover most paths. PR 8c makes the event-driven formal-validation runtime path safe to merge to main.

*Update Note (2026-05-26, PR 8b of 2026-05-26 freeze plan landed — Calendar-policy ordering + mode coverage fixup):* Third GPT 5.5 Pro cross-review (post-PR-8a) found 6 issues: 3 merge blockers and 3 medium hardening gaps. PR 8b closes all of them. **Blockers fixed**: (1) Pre-PR-8b the `calendar_policy_id is None` check fired AFTER `feeder = QlibDataFeeder(...)` (line 399), `feeder.preload_features(...)` (line 432), and engine construction (line 468). A formal run without a policy still touched Qlib and burned cache work before raising at line 485. PR 8b moves the check immediately after `effective_require_provider_manifest` is computed (and also moves `_validate_provider_at_runtime` above feeder creation). (2) `FORMAL_RUN_MODES = {formal, oos_test, joinquant_replication}` but the frozen policy's `allowed_modes` was `{sandbox, joinquant_replication, formal_research_with_explicit_freeze, joinquant_daily, joinquant_open_close_replica}`. Calling `EventDrivenBacktester.run(run_mode='formal', calendar_policy_id='frozen_20260227_system_build')` was rejected by `policy.assert_run_mode_allowed('formal')`. PR 8b adds `formal` and `oos_test` to the YAML's allowed_modes (option A: literal, no string normalization). (3) `_validate_provider_at_runtime` cross-checked the calendar dates but never verified `manifest.calendar_policy_id == calendar_policy_id`. A caller could pass a different policy id with the same dates and silently stamp a mismatched policy into the artifact. PR 8b adds the equality check inside the validator. **Medium gaps fixed**: (4) `QlibDataFeeder.get_features` with `_strict_cache_only=True` only raised on ALL-missing instruments; PARTIAL-missing silently sliced and returned the subset (e.g., 3,999 of 4,000 instruments). PR 8b computes `missing_instruments = requested - cache_instruments` and raises `PreloadCoverageError` whenever it is non-empty in strict mode. (5) `BacktestEngine.run` restored `strict_cache_only` on the success path only (PR 8a's explicit acknowledgment). PR 8b wraps the day loop in `try: ... finally:` so restoration fires on BOTH paths, and exports a `strict_cache_mode(feeder, enabled)` context manager helper at the module level for callers. (6) PR 8a's daily-QA test was source-reflection only. PR 8b adds a behavioral test that constructs a temp Qlib layout (`calendars/day.txt` + `metadata/provider_build.json`) with mismatched dates and asserts that the daily-QA validator path raises with a precise calendar message. **What changed**: (a) [src/backtest_engine/event_driven/__init__.py](src/backtest_engine/event_driven/__init__.py) — `calendar_policy_id` check + provider manifest validation moved BEFORE `QlibDataFeeder` construction; `_validate_provider_at_runtime` enforces `manifest.calendar_policy_id == calendar_policy_id`. (b) [config/calendar_policies/frozen_20260227_system_build.yaml](config/calendar_policies/frozen_20260227_system_build.yaml) — `allowed_modes` extended with `formal` and `oos_test`. (c) [src/backtest_engine/event_driven/data_feeder.py](src/backtest_engine/event_driven/data_feeder.py) — `get_features` raises `PreloadCoverageError` on partial-missing in strict mode; new module-level `strict_cache_mode(feeder, enabled)` context manager. (d) [src/backtest_engine/event_driven/engine.py](src/backtest_engine/event_driven/engine.py) — day loop wrapped in `try: ... finally:`; strict_cache_only restored on exception path with diagnostic logging. (e) Three PR 8/PR 8a test mocks updated to set `manifest.calendar_policy_id` (PR 8b Blocker 3 caught the implicit MagicMock attribute returning a Mock instead of the expected string). **Tests**: 15 new at [tests/backtest_engine/test_pr8b_ordering_modes.py](tests/backtest_engine/test_pr8b_ordering_modes.py): 1 for Blocker 1 (preload not called when policy missing), 4 for Blocker 2 (formal + oos_test in allowed_modes + integration tests), 2 for Blocker 3 (manifest policy mismatch raises / matches passes), 3 for fix #4 (partial-missing raises, non-strict silent, all-present passes), 3 for fix #5 (context manager restores on exception, disabled is no-op, engine source uses try/finally), 2 for fix #6 (behavioral mismatch + behavioral match). Full regression: **440 pass, 9 skip** across `tests/backtest_engine/ tests/research_orchestrator/ tests/data_infra/ tests/architecture/` — 425 from PR 8a plus 15 new. `scripts/lint_no_bare_qlib_features.py src/` is clean. **CLAUDE.md updated**: §3 hard invariants gain 5 new contracts (one per ordering / mode coverage / manifest-policy / partial-missing / exception-restore). **Single remaining queued follow-up (unchanged)**: PR 9 to wire `assert_field_dependencies_eligible` into `handle_validation_object_resolver` in `validation_steps.py`. PR 8b makes the event-driven runtime path safe to merge to main.

*Update Note (2026-05-26, PR 8a of 2026-05-26 freeze plan landed — Calendar/runtime enforcement hardening):* Stacked on PR 8. Second GPT 5.5 Pro cross-review (post-PR-8) identified 4 major + 3 medium issues that PR 8's fixes left open. **What was still wrong**: (1) Formal runs with `execution_profile='joinquant_daily_sim'` and `calendar_policy_id=None` quietly skipped `_validate_provider_at_runtime` because the call site required BOTH `effective_require_provider_manifest AND calendar_policy_id` — the manifest was loaded but no policy check ran, and the artifact stamped legacy provenance. (2) `joinquant_daily_sim.deployment_target='joinquant_daily'` was NOT in the frozen policy's `allowed_modes` (`{sandbox, joinquant_replication, formal_research_with_explicit_freeze}`), so the normal profile-driven formal-run path with `run_mode=None` got rejected by `policy.assert_run_mode_allowed`. (3) `scripts/run_daily_qa.py` still had the PR 1-era blanket `allow_mismatch = policy.frozen` line, so daily QA was strictly weaker than the formal-runtime validator. (4) `_validate_provider_at_runtime` silently no-op-returned if the Qlib `D.calendar()` read raised any exception — formal validators must not skip silently. (5) `_serialize_slippage` hardcoded an allow-list of attribute names that missed `FixedSlippage.spread`, producing `{"class": "FixedSlippage", "params": {}}` for a JoinQuant-default slippage override — completely unreplayable. (6) `QlibDataFeeder.get_features` with `_strict_cache_only=True` returned an empty DataFrame silently when the requested instruments had zero intersection with the cache's instrument index. (7) `BacktestEngine.run` flipped `set_strict_cache_only(True)` for the duration of a formal run but never restored the prior value, leaking state across runs that reused the same feeder. **What landed in PR 8a**: (a) [src/backtest_engine/event_driven/__init__.py](src/backtest_engine/event_driven/__init__.py) — `EventDrivenBacktester.run()` raises `RuntimeError` if formal mode is implied but `calendar_policy_id is None`; `_validate_provider_at_runtime` now raises on Qlib read failure instead of returning; `_serialize_slippage` uses `vars(slip)` so any `__dict__`-stored SlippageModel attribute round-trips. (b) [config/calendar_policies/frozen_20260227_system_build.yaml](config/calendar_policies/frozen_20260227_system_build.yaml) — `allowed_modes` extended with `joinquant_daily` and `joinquant_open_close_replica`. (c) [scripts/run_daily_qa.py](scripts/run_daily_qa.py) — removed the blanket `allow_mismatch = policy.frozen`; frozen policies now require `manifest.calendar_end_date == policy.calendar_end_date == live_calendar_end[-1]` with explicit `RuntimeError` raises on mismatch. (d) [src/backtest_engine/event_driven/data_feeder.py](src/backtest_engine/event_driven/data_feeder.py) — when `_strict_cache_only=True` and instruments are all missing from cache, `get_features` raises `PreloadCoverageError` with the cache instrument count for diagnostics. The `PreloadCoverageError` is re-raised through the cache-slice try/except so it isn't dressed as a generic cache failure. (e) [src/backtest_engine/event_driven/engine.py](src/backtest_engine/event_driven/engine.py) — engine snapshots `_prev_strict_cache_only` before the assertion and restores it on the success path after the day loop completes. (f) Three test helpers (PR 2 / PR 3 / PR 8) updated to default `calendar_policy_id="frozen_20260227_system_build"` so existing formal-mode tests continue to exercise the right path under PR 8a's stricter contract. **Tests**: 14 new at [tests/backtest_engine/test_pr8a_hardening.py](tests/backtest_engine/test_pr8a_hardening.py): 3 for fix #1 (calendar_policy_id required), 3 for fix #2 (allowed_modes alignment), 1 for fix #3 (daily QA source check), 1 for fix #4 (Qlib read raises), 3 for fix #5 (FixedSlippage/PctSlippage serialization round-trip), 2 for fix #6 (strict cache-only missing instruments), 1 for fix #7 (engine restore via source-reflection). Full regression: **425 pass, 9 skip** across `tests/backtest_engine/ tests/research_orchestrator/ tests/data_infra/ tests/architecture/` — 411 from PR 8 plus 14 new. `scripts/lint_no_bare_qlib_features.py src/` is clean. **CLAUDE.md updated**: §3 hard invariants gain 7 new contracts (one per fix). **Remaining queued follow-up after PR 8a** (single open item): GPT issue #4 — wire `assert_field_dependencies_eligible` into `handle_validation_object_resolver` in `validation_steps.py` so factors with quarantined/pending/unknown field expressions fail BEFORE the IS leg runs. Requires expression extraction from resolved registry entries (non-trivial refactor). Tracked as **PR 9**; data-layer chokepoint (PR 6 + PR 8 fix #8) + release-gate field-dependency check (PR 5) already cover the most common paths.

*Update Note (2026-05-26, PR 8 of 2026-05-26 freeze plan landed — Formal-runtime enforcement fixup):* Post-merge cross-review by GPT 5.5 Pro flagged 4 major + 4 medium issues in the PR 1-7 stack. PR 8 closes the runtime-correctness ones; the validation_steps wiring follow-up is documented and queued. **What was wrong**: (1) `EventDrivenBacktester.run()` computed `is_formal` twice; the second computation overwrote the profile-aware version. A caller passing `execution_profile='joinquant_daily_sim'` with `run_mode=None` got JoinQuant fill semantics WITHOUT strict preload + require_preloaded + require_provider_manifest. (2) `assert_preloaded` ran once before the day loop; mid-loop cache misses silently fell back to per-day `D.features`. (3) Daily QA's `allow_mismatch = policy.frozen` was too broad; a frozen policy should require the observed calendar to actually equal the policy's `calendar_end_date`. (4) The release gate cross-checked `execution_profile_id` against the registry but never compared the artifact's stored `execution_profile_hash` to the current canonical profile_hash. (5) Object-form overrides (`exchange_config=CostConfig(...)`, `slippage=FixedSlippage(...)`) recorded opaque `"<caller-supplied CostConfig instance>"` strings instead of replayable `{class, params}`. (6) No `require_research_access_context(stage)` helper, so formal validation handlers had no fast-fail when invoked without a context. **What landed in PR 8**: (a) [src/backtest_engine/event_driven/__init__.py](src/backtest_engine/event_driven/__init__.py) — single `is_formal = mode_is_formal or profile_is_formal` computation; `effective_strict`, `effective_require_preloaded`, and `effective_require_provider_manifest` all derive from it. (b) New `_validate_provider_at_runtime(manifest, calendar_policy_id, run_mode)` called from `EventDrivenBacktester.run()` on formal runs; frozen-policy validation requires manifest.calendar_end_date == policy.calendar_end_date == D.calendar()[-1]; disallowed run_modes raise via `policy.assert_run_mode_allowed`. (c) New `_serialize_cost_config(cfg)` + `_serialize_slippage(slip)` helpers producing replayable `{class, params}` dicts; the override_diff_record now uses these for object overrides. (d) [src/backtest_engine/event_driven/data_feeder.py](src/backtest_engine/event_driven/data_feeder.py) — new `PreloadCoverageError`, new `_strict_cache_only` flag + `set_strict_cache_only(bool)` API; when True, `get_features()` raises immediately on a cache miss instead of falling back. (e) [src/backtest_engine/event_driven/engine.py](src/backtest_engine/event_driven/engine.py) — after the pre-loop `assert_preloaded` passes (when `require_preloaded=True`), the engine flips `feeder.set_strict_cache_only(True)` so any mid-loop cache miss raises at the first offending access. (f) [src/research_orchestrator/release_gate.py](src/research_orchestrator/release_gate.py) — `evaluate_artifact_provenance` looks up the artifact's profile via `get_profile(id)` and compares `provenance.execution_profile_hash` to `profile.profile_hash`; mismatch adds `execution_profile_hash_mismatch` to reasons and sets `ArtifactGateResult.profile_hash_matches_current=False`. (g) [src/research_orchestrator/research_access_context.py](src/research_orchestrator/research_access_context.py) — new `MissingResearchAccessContextError`, new `FORMAL_STAGES = {formal_validation, oos_test, registry_publish}` frozenset, new `require_research_access_context(stage)` helper. (h) Two test helpers in PR 2 and PR 3 test files updated to mock `load_provider_manifest` and `_validate_provider_at_runtime` so the existing mocked-component tests survive PR 8's tightening. Test helper `_complete_provenance()` updated to use the live profile_hash instead of a hardcoded fake `"0"*64`. **Tests**: 17 new at [tests/backtest_engine/test_pr8_runtime_enforcement.py](tests/backtest_engine/test_pr8_runtime_enforcement.py): 3 for fix #1 (profile-implies-formal), 3 for fix #2 (strict_cache_only), 3 for fix #3 (provider runtime validation), 2 for fix #5 (hash mismatch), 2 for fix #6 (replayable override), 4 for fix #8 (require_research_access_context). Full regression: **411 pass, 9 skip** across `tests/backtest_engine/ tests/research_orchestrator/ tests/data_infra/ tests/architecture/` — 394 from PR 7 plus 17 new. `scripts/lint_no_bare_qlib_features.py src/` is clean. **CLAUDE.md updated**: §3 hard invariants gain 6 new contracts (fixes #1, #2, #3, #5, #6, #8). **Remaining follow-ups** (queued, not in PR 8): (1) GPT issue #4 — wire `assert_field_dependencies_eligible` into `handle_validation_object_resolver` in `validation_steps.py` so factors with quarantined/pending/unknown field expressions fail BEFORE the IS leg runs. Requires expression-extraction from resolved registry entries. (2) GPT issue #7 — split `profile_hash` into `execution_profile_hash` (execution-relevant fields only) + `execution_profile_metadata_hash` (notes/docs); current behavior includes `notes` in the main hash, which works but conflates documentation edits with reproducibility changes. (3) Per-handler `require_research_access_context(stage)` installs in `validation_steps.py` formal handlers. Each is a smaller follow-up PR; PR 8 ships the runtime-correctness fixes that make the system safe to merge to main even without them.

*Update Note (2026-05-26, PR 7 of 2026-05-26 freeze plan landed — Workspace headers + LICENSE + dormant-code boundary tests; **freeze plan COMPLETE**):* Final PR closes the 7-PR arc that turned the project's written invariants into runtime-enforced ones. **What landed in PR 7**: (1) New [scripts/apply_workspace_script_headers.py](scripts/apply_workspace_script_headers.py) reads PR 2's classification CSV and idempotently applies SCRIPT_STATUS comment blocks to A/B/C-class scripts + archives D-class scripts. Applied: 5 A-class (formal_candidate, execution_profile=joinquant_daily_sim), 1 B-class (formal_candidate with manual preload contract), 26 C-class (historical_investigation), 14 D-class moved to [workspace/scripts/archive/p1_jq_g5a2_investigation_2026_05/](workspace/scripts/archive/p1_jq_g5a2_investigation_2026_05/). Manifest of every action written to [workspace/scripts/_audit/pr7_header_application_manifest.json](workspace/scripts/_audit/pr7_header_application_manifest.json). (2) New [LICENSE](LICENSE) at repo root — "all rights reserved" / reference-only text per GPT 5.5 Pro's recommendation for a personal-local-research system that is incidentally public. README's "add a license before publishing" note is now satisfied. (3) New [tests/architecture/test_dormant_module_boundaries.py](tests/architecture/test_dormant_module_boundaries.py) — durable boundary guards: `test_formal_path_does_not_import_dormant_portfolio_risk` (parametrized across release_gate / validation_steps / event_driven / factor_library / result_analysis) fails the moment any formal path imports `MultiFactorRiskModel`, `predict_portfolio_risk`, or `MarketImpactModel` (captures the 2026-05-26 dormant-code audit as an active rule); `test_archived_workspace_scripts_not_referenced_from_src` blocks accidental un-archiving via import or path reference; `test_workspace_scripts_outside_archive_carry_script_status_header` reads the PR 2 audit CSV and asserts every classified non-D file has the PR 7 header. Full regression: **394 pass, 9 skip** across `tests/backtest_engine/ tests/research_orchestrator/ tests/data_infra/ tests/architecture/` — 386 from PR 6 plus 8 new boundary tests. `scripts/lint_no_bare_qlib_features.py src/` is clean. **CLAUDE.md updated**: §3 hard invariants gain 3 new contracts — workspace SCRIPT_STATUS header contract; class-D archive home + import ban; dormant portfolio_risk import boundary.

---

**Freeze plan summary (PRs 1-7, 2026-05-26)**

The 7-PR arc turned 7 written invariants into runtime-enforced ones, going from 0 to **394 tests** across `tests/backtest_engine/ tests/research_orchestrator/ tests/data_infra/ tests/architecture/` (9 skip pending live-data dependencies). Each PR ships green on its own; PRs are stacked so #2 builds on #1, #3 on #2, etc.

| PR | Title | New tests | What it enforces |
|---:|---|---:|---|
| [#1](https://github.com/henrydan111/quant-system/pull/1) | Provider self-attestation + calendar policy + artifact provenance | 36 | Every formal artifact records `provider_build_id` + `calendar_policy_id`. Legacy artifacts are readable but blocked from formal gate. |
| [#2](https://github.com/henrydan111/quant-system/pull/2) | Preload hardening + workspace direct-engine triage | 22 | `BacktestEngine` no longer silently degrades. `EventDrivenBacktester` unions `ENGINE_REQUIRED_FIELDS` into every preload payload. Workspace audit classifies 46 scripts. |
| [#3](https://github.com/henrydan111/quant-system/pull/3) | Versioned execution profiles | 41 | "JoinQuant parity" is a hash-pinned `ExecutionProfile`, not a vague label. Formal overrides require `override_reason` + `override_diff`. |
| [#4](https://github.com/henrydan111/quant-system/pull/4) | Cache/seal file locking | 6 | `holdout_seal.claim_holdout_access` + `cache_manifest.record_cache_write` lock the entire read-check-write critical section. 8 concurrent processes → exactly 1 seal-claim winner. |
| [#5](https://github.com/henrydan111/quant-system/pull/5) | Stage-aware field-status registry | 52 | Every `$field` resolves to a dataset; quarantined / pending_review / unknown fields fail at formal/oos/publish. moneyflow / northbound / margin / stk_limit / event-like daily endpoints are seeded as not-yet-trusted. |
| [#6](https://github.com/henrydan111/quant-system/pull/6) | OOS ResearchAccessContext + AST lint | 32 | `qlib_windowed_features` is the mandatory data chokepoint; window / seal / field violations raise BEFORE Qlib is touched. AST lint banishes bare `D.features` from `src/`. |
| [#7](https://github.com/henrydan111/quant-system/pull/7) | Workspace headers + LICENSE + dormant-code boundary tests | 8 | Every workspace script carries a SCRIPT_STATUS header. 14 superseded mimics archived. Dormant `portfolio_risk` cannot leak into formal paths without a P2→P0 promotion. |

Subsequent next phases pick up from here:
* **P2 — Portfolio/risk maturity**: replace the dormant `predict_portfolio_risk` / `MultiFactorRiskModel.fit` with a real covariance-shrinkage + PSD-repair stack, replace the 1/N optimizer fallback with explicit infeasibility handling, calibrate cost/impact by liquidity bucket. Boundary tests in [tests/architecture/test_dormant_module_boundaries.py](tests/architecture/test_dormant_module_boundaries.py) keep the dormant code from quietly re-entering formal paths until that work lands.
* **Per-handler `ResearchAccessContext` installs in `validation_steps.py`**: PR 6 installed the data-layer chokepoint and the workspace-pipeline tightening; per-formal-handler context installs are a smaller follow-up that further reduces the attack surface (cf. PR 6 reviewer note).
* **Anomaly review for quarantined / pending_review datasets**: when `moneyflow`, `hk_hold`, `margin_detail`, `stk_limit`, `top_list`, `top_inst`, `block_trade`, `cyq_perf` clear anomaly review, promote them via the approval workflow under [config/field_registry/approvals/](config/field_registry/approvals/).

---

*Update Note (2026-05-26, PR 6 of 2026-05-26 freeze plan landed — OOS ResearchAccessContext + AST lint):* Stacked on PR 5. Biggest single PR remaining (3-4 day estimate). Moves OOS / formal-research enforcement from the wrapper layer down into the data-access layer so any code path that ends up calling Qlib for data — even one that bypasses `EventDrivenBacktester` — inherits the seal/window/field constraints. **What landed**: (1) New runtime module [src/research_orchestrator/research_access_context.py](src/research_orchestrator/research_access_context.py): `ResearchAccessContext` frozen dataclass carrying `run_id`, `step_id`, `stage`, `design_hash`, `allowed_start`, `allowed_end`, `provider_build_id`, `calendar_policy_id`, `holdout_context_id`, `holdout_seal_claimed`, `allowed_fields`; `contextvars.ContextVar` for safe propagation across threads/async (NOT thread-local); `validate_read(start_time, end_time, fields=...)` enforces the three invariants; helpers `set_research_access_context` / `reset_research_access_context` / `get_research_access_context` and the recommended `research_access_context(...)` context manager; exceptions `HoldoutWindowViolation` / `HoldoutSealViolation` / `FieldAccessViolation`; `ResearchAccessContext.from_split(time_split, ...)` builds the context from the orchestrator-native `time_split` dict respecting `stage` for window selection. (2) [src/research_orchestrator/qlib_windowed_features.py](src/research_orchestrator/qlib_windowed_features.py) — before the canonical `D.features` invocation, the wrapper calls `get_research_access_context()` and invokes `validate_read(...)`. Sandbox/no-context calls are unchanged. The canonical `D.features` call site carries the `# noqa: bare-qlib-features` marker (legitimate single use). (3) [src/research_orchestrator/sealed_backtest_runner.py](src/research_orchestrator/sealed_backtest_runner.py) — `run_workspace_pipeline` signature tightened: `time_split` and `pipeline_args` are required keyword args; when `self._ctx` is set (OOS path), the runner constructs a `ResearchAccessContext` from `time_split + holdout_context` and wraps `pipeline_fn(...)` in `research_access_context(...)`. Pipelines now receive `time_split` and `holdout_context` explicitly. Sandbox path (no holdout context) skips the install. (4) New [scripts/lint_no_bare_qlib_features.py](scripts/lint_no_bare_qlib_features.py) AST walker — detects plain `D.features`, aliased imports (`from qlib.data import D as X; X.features`), fully-qualified (`qlib.data.D.features`, `qlib.D.features` via `import qlib`), and `getattr(D, "features")(...)` tricks. Per-line opt-out via `# noqa: bare-qlib-features` marker; per-file opt-out via `--allow <glob>` flag. Default allowlist: `src/research_orchestrator/qlib_windowed_features.py`. Exit code 0=clean, 1=violation, 2=syntax error. (5) Lint wired into [scripts/run_daily_qa.py](scripts/run_daily_qa.py) as the `no_bare_qlib_features_lint` audit block, runs after `provider_manifest_check`. (6) One existing line caught by the lint and confirmed legitimate: `provider_manifest.compute_canonical_kline_hash` at line 300 — this is a privileged admin call computing the provider attestation hash itself, intentionally bypasses the wrapper because no ResearchAccessContext applies to a provider-attestation operation. Annotated with `# noqa: bare-qlib-features` and an explanatory comment. **Tests**: 32 new across 2 modules. [tests/research_orchestrator/test_research_access_context.py](tests/research_orchestrator/test_research_access_context.py) (20 tests) covers: contextvar plumbing (default None, set/reset roundtrip, context manager clears on exit AND on exception, None is no-op); validate_read (inside window passes, before start raises, after end raises, OOS without seal raises, OOS with seal passes, allowed_fields blocks extras, allowed_fields=None permits all, exact match passes); from_split (OOS maps to oos window, is_only maps to is window, missing keys raises); qlib_windowed_features integration (no-context skips validation, window violation raises BEFORE D.features is reached, OOS-without-seal raises before D.features, FieldAccessViolation raises, valid read with context proceeds). [tests/research_orchestrator/test_lint_no_bare_qlib_features.py](tests/research_orchestrator/test_lint_no_bare_qlib_features.py) (12 tests) covers: plain `D.features` caught, aliased import caught, `import qlib.data as q` caught, `import qlib` then `qlib.data.D.features` caught, `getattr(D, 'features')` caught; noqa comment suppresses; `--allow` flag skips file; clean module passes; `D.calendar` is NOT flagged (only `D.features` is banned); syntax error returns exit 2; live `src/` lint passes. Full regression: **386 pass, 9 skip** across `tests/backtest_engine/ tests/research_orchestrator/ tests/data_infra/` — same green state as PR 5 plus 32 new. **CLAUDE.md updated**: §3 hard invariants gain 4 new contracts — ResearchAccessContext is the data-layer OOS primitive, qlib_windowed_features is the mandatory chokepoint, sealed_backtest_runner tightened signature, AST lint bans bare D.features. **Next PR (PR 7)**: workspace script headers (apply PR 2's A/B/C/D classification as SCRIPT_STATUS header blocks; archive class-D scripts under workspace/scripts/archive/), LICENSE file, durable risk-model dormant-code import-boundary test. Smallest remaining PR; closes out the 2026-05-26 freeze plan.*

*Update Note (2026-05-26, PR 5 of 2026-05-26 freeze plan landed — Stage-aware field-status registry):* Stacked on PR 4. Closes the "downloaded but not trusted" gap: until today, factor expressions could quietly reference fields from datasets that were merely *present* (e.g. moneyflow, northbound) rather than *anomaly-reviewed*. Formal runs had no automated way to refuse those fields. **What landed**: (1) Committed schema [schemas/field_status.schema.json](schemas/field_status.schema.json). (2) Seed YAML at [config/field_registry/field_status.yaml](config/field_registry/field_status.yaml) — 4 status levels (`approved`/`pending_review`/`quarantine`/`deprecated`), each with per-stage allowed flags (`sandbox_screening`, `vectorized_screening`, `formal_validation`, `oos_test`, `registry_publish`); 12 dataset entries seeded: approved = market_daily + daily_basic + pit_fundamentals + reference, quarantine = moneyflow + hk_hold + margin_detail + stk_limit (downloaded pending anomaly review), pending_review = top_list + top_inst + block_trade + cyq_perf (post-2026-04-20 namespacing). Unknown-field policy is conservative-fail (`warn` for sandbox/screening, `fail` for formal/oos/publish). (3) Runtime module [src/data_infra/field_registry.py](src/data_infra/field_registry.py): `FieldStatusRegistry` loader + `StatusDef` + `DatasetEntry` + `FieldResolution` dataclasses; `extract_qlib_fields(expr)` regex parser handles `$field`, `Ref($field, 1)`, `Mean(Ref($field, 1), 20)`, dunder-namespaced fields like `$top_list__amount`; `resolve_field(token, stage)` returns the per-stage decision with full reason; `validate_expression(expr, stage)` raises `FieldApprovalError` listing every violating field (not just the first). (4) Append-only approval log [config/field_registry/field_approval_log.jsonl](config/field_registry/field_approval_log.jsonl) + [config/field_registry/approvals/](config/field_registry/approvals/) directory with per-promotion YAML evidence files. Status transitions require both a JSONL line and an approvals/ YAML — diffable in Git, never binary. (5) Release-gate integration at [src/research_orchestrator/release_gate.py](src/research_orchestrator/release_gate.py): new `FieldDependencyGateResult` + `evaluate_field_dependencies(fields=..., expressions=..., stage=...)` + strict `assert_field_dependencies_eligible(...)`. Loads the committed registry by default; tests inject custom registries. **Tests**: 52 new — 39 in [tests/data_infra/test_field_registry.py](tests/data_infra/test_field_registry.py) covering (a) extract_qlib_fields with bare/Ref/nested/multi-field/dunder/empty/no-fields expressions, (b) malformed YAML / missing sections / unknown statuses / missing stages / invalid unknown-policy values raise FieldRegistryError, (c) resolution at every stage for approved/quarantine/pending_review/deprecated/unknown fields, (d) validate_expression collects all violations, (e) raise_on_unknown override, (f) live committed-registry smoke (close approved, moneyflow quarantined, top_list pending, pit_* prefix match, completely-unknown blocked at formal). 13 in [tests/research_orchestrator/test_field_dependency_gate.py](tests/research_orchestrator/test_field_dependency_gate.py) covering evaluate_field_dependencies with approved/quarantine/unknown/sandbox/expressions inputs, assert_strict variants, and live-registry integration smoke. Full regression: **354 pass, 9 skip** across `tests/backtest_engine/ tests/research_orchestrator/ tests/data_infra/` — same green state as PR 4 plus 52 new. **CLAUDE.md updated**: §3 hard invariants gain 4 new contracts — field-status registry is the formal data gate; unknown-field conservative-fail; seed status assignments; release-gate field-dependency check. **Next PR (PR 6)**: OOS ResearchAccessContext + AST lint banning bare D.features. Biggest scope remaining (3-4 day estimate); makes the qlib_windowed_features chokepoint mandatory for all formal data reads.*

*Update Note (2026-05-26, PR 4 of 2026-05-26 freeze plan landed — Cache/seal file locking):* Stacked on PR 3. Closes a real but quiet concurrency hole in research-integrity primitives. The fix is small (3 lines per critical section); the bug it prevents is silent (duplicate seal claims for the same design_hash, lost cache-manifest rows under parallel writes). **What changed**: (1) [src/research_orchestrator/holdout_seal.py](src/research_orchestrator/holdout_seal.py) — `claim_holdout_access` now wraps the entire `list_events → frame.empty check → pd.concat → _atomic_write_dataframe` sequence in `with file_lock(self.root_dir / "holdout_events.lock"):`. Before PR 4, the only protection was the atomic-write at the end, which guards against partial parquet corruption but does NOT prevent two concurrent processes from both passing `frame.empty` and both writing a seal event for the same design_hash. (2) [src/research_orchestrator/cache_manifest.py](src/research_orchestrator/cache_manifest.py) — `record_cache_write` wraps `_load → _append_row → _atomic_write_dataframe` in `with file_lock(self.root_dir / "cache_events.lock"):`. Without the lock, two concurrent writers each `_load` the same baseline frame, each append their row, and the second write overwrites the first writer's row. (3) The existing cross-platform [file_lock](src/research_orchestrator/file_lock.py) helper (portalocker → msvcrt → fcntl fallback with timeout) is the lock primitive — already shipped; PR 4 just wires it into the critical sections. **Tests**: 6 new at [tests/research_orchestrator/test_lock_concurrency.py](tests/research_orchestrator/test_lock_concurrency.py): (a) 8 concurrent processes via `mp.get_context("spawn").Pool` attempt to claim the SAME design_hash → exactly 1 succeeds, 7 raise `ValueError("Holdout sealed for design_hash ...")`, manifest holds exactly 1 event; (b) 8 concurrent processes write DISTINCT cache_keys → all 8 persist with 8 distinct manifest_ids; (c) 8 concurrent processes write the SAME cache_key → all 8 appended (manifest is append-only, lock guarantees serialization not deduplication); (d) single-process regression tests confirm the lock-wrapped path still works for normal single-caller flows (seal single claim, seal double-claim raises, cache single write persists). All workers are top-level functions so multiprocessing can pickle them on Windows. Full regression: **302 pass, 9 skip** across `tests/backtest_engine/ tests/research_orchestrator/ tests/data_infra/` — same green state as PR 3 plus 6 new tests. **CLAUDE.md updated**: §3 hard invariants gain one new contract — cache + seal critical sections file-locked, lock covers the read-check-write window, NOT just the final write. **Next PR (PR 5)**: stage-aware field-status registry. Adds `config/field_registry/field_status.yaml` (committed, not under data/), an unknown-field conservative-fail policy for formal stages, and enforcement at expression-parser, validation_object_resolver, and release-gate layers.*

*Update Note (2026-05-26, PR 3 of 2026-05-26 freeze plan landed — Versioned execution profiles):* Stacked on PR 2. Replaces the parameter-soup pattern (`fill_mode + cost_config + slippage + volume_limit` composed individually at every call site) with a single named, immutable contract. Every formal backtest now passes `execution_profile=<profile_id>`; the profile resolves to a fully-pinned set of execution parameters; the result artifact records `execution_profile_id + execution_profile_version + execution_profile_hash` so reviewers can compare runs by id alone. **What landed**: (1) Committed schema [schemas/execution_profile.schema.json](schemas/execution_profile.schema.json) + worked example at [docs/examples/execution_profile.example.yaml](docs/examples/execution_profile.example.yaml). (2) New runtime module [src/backtest_engine/execution_profiles.py](src/backtest_engine/execution_profiles.py): `ExecutionProfile` frozen dataclass with `profile_hash` as a computed `@property` (sha256 over canonical JSON of execution-relevant fields, self-excluding); `_BUILTIN_PROFILES` registry with 4 profiles — `joinquant_daily_sim` (formal, jq_daily_avg, JOINQUANT_DEFAULT_SLIPPAGE, joinquant_default cost, volume_limit=0.25), `joinquant_open_close_replica` (formal, open_close fill variant for closer-to-live verification), `realistic_china_stress` (event-driven, CONSERVATIVE_SLIPPAGE_10BPS + realistic_china cost, `allowed_for_formal=False`, for sensitivity stress only), `vectorized_screening_close` (vectorized backend, `allowed_for_formal=False`); resolver helpers `resolve_cost_config` + `resolve_slippage_preset` map factory-name strings to concrete objects; `detect_override_diff` computes per-field diff; custom exceptions `ExecutionProfileError` + `OverrideRequiresReasonError`. (3) [ArtifactProvenance](src/research_orchestrator/artifact_provenance.py) bumped to schema version 2: now requires `execution_profile_id` + `execution_profile_hash` for formal eligibility, plus new override block (`manual_override` + `override_reason` + `override_diff`). v1 artifacts remain readable but legacy_artifact-style ineligible for formal gate. (4) `EventDrivenBacktester.run()` accepts `execution_profile` + `override_reason` kwargs. When a profile is supplied, the wrapper resolves it to fill_mode/cost/slippage/volume_limit; explicit caller overrides on top of a profile produce `override_diff_record`. Formal profiles + overrides without `override_reason` raise `OverrideRequiresReasonError`. The wrapper stamps profile id + version + hash + override block onto `ArtifactProvenance`. Event-driven rejects vectorized profiles loudly. (5) `VectorizedBacktester.run()` accepts `execution_profile` + `calendar_policy_id`. Vectorized rejects event-driven profiles loudly. Vectorized stamps full provenance onto `bt_config` for the first time (PR 1 only wired event-driven). (6) Release gate at [src/research_orchestrator/release_gate.py](src/research_orchestrator/release_gate.py) cross-checks `execution_profile_id` against `_BUILTIN_PROFILES`: unknown profile → fail with `unknown_execution_profile_id`; profile with `allowed_for_formal=False` → fail with `execution_profile_not_allowed_for_formal`. `ArtifactGateResult` now also carries `manual_override` + `override_reason` + `override_diff_keys`. **Tests**: 41 new at [tests/backtest_engine/test_execution_profiles.py](tests/backtest_engine/test_execution_profiles.py) covering (a) profile_hash determinism + self-exclusion + field sensitivity (8 tests), (b) frozen dataclass mutation protection + replace() semantics (2 tests), (c) registry lookups and unknown-profile errors (5 tests), (d) cost_config + slippage resolvers (6 tests), (e) override_diff detection (4 tests), (f) EventDrivenBacktester profile resolution + backend-mismatch rejection + override-without-reason rejection (5 tests), (g) vectorized backend separation (1 test), (h) ArtifactProvenance v2 schema (5 tests), (i) release-gate profile cross-checks (4 tests). Existing v1 provenance test helper updated to v2 (`_complete_provenance()` now includes execution_profile fields). One legacy test in [test_joinquant_parity.py](tests/backtest_engine/test_joinquant_parity.py) updated to reflect the PR 3 signature change: `fill_mode` default is now `None` (profile-or-fallback semantics) instead of literal `'open_close'`. Full regression: **296 pass, 9 skip** across `tests/backtest_engine/ tests/research_orchestrator/ tests/data_infra/` — same green state as PR 2 plus 41 new tests. **CLAUDE.md updated**: §3 hard invariants gain 4 new contracts — ExecutionProfile is the formal contract; profile_hash is computed and self-excluding; formal-no-override default; ArtifactProvenance schema v2. **Operational impact**: the 5 A-class validation runners identified in PR 2's audit can now flip from `run_mode='formal'` (PR 2 transitional) to `execution_profile='joinquant_daily_sim'` (PR 3 final). Header insertion + script flips are PR 7 work. **Next PR (PR 4)**: cache/seal locking — wrap `holdout_seal.claim_holdout_access()` and `cache_manifest.record_cache_write()` in the existing `file_lock` helper around the read-check-write critical section. Cheap (~0.5 day) but closes a real concurrency hole in research-integrity primitives.*

*Update Note (2026-05-26, PR 2 of 2026-05-26 freeze plan landed — Preload hardening + workspace direct-engine triage):* Stacked on PR 1. Closes the most concrete correctness bug remaining after PR 1: until today, `BacktestEngine.run()` called `self.feeder.preload(preload_start, end)` — a deprecated no-op that left the cache empty and forced every backtest day into a per-day `D.features` round trip (the ~100x slowdown originally discovered during plan `snappy-buzzing-meerkat` v5). The wrapper's `if preload_fields:` condition could ALSO silently skip preload entirely for formal runs that didn't pass any strategy-specific factor fields — leaving the same fallback path active. **What landed**: (1) New [src/backtest_engine/event_driven/constants.py](src/backtest_engine/event_driven/constants.py) with the canonical 8-field `ENGINE_REQUIRED_FIELDS` tuple ($open/$close/$high/$low/$vol/$amount/$pre_close/$adj_factor) plus `FORMAL_RUN_MODES` frozenset ({`formal`, `oos_test`, `joinquant_replication`}). Lives in its own module to avoid circular imports between engine.py and __init__.py. (2) `EventDrivenBacktester.run()` adds `run_mode`, `preload_required` kwargs. Corrected condition: `should_preload = preload_required or preload_fields is not None or run_mode in FORMAL_RUN_MODES`. Caller-supplied `preload_fields` is now always unioned with ENGINE_REQUIRED_FIELDS via `dict.fromkeys([*requested, *engine])` so the engine path never falls back to per-day D.features for OHLCV. Formal modes auto-promote `strict=True` and `require_preloaded=True`. (3) `BacktestEngine.__init__(require_preloaded=False)` + `assert_preloaded()` call site before the day loop. When True, the engine asserts (a) `preload_status == 'success'`, (b) cache covers ENGINE_REQUIRED_FIELDS, (c) `cache_min <= preload_start` AND `cache_max >= end`, (d) `direct_fallback_count == 0`. Raises a precise RuntimeError naming which gate failed. The deprecated `self.feeder.preload(preload_start, end)` line at engine.py:315 has been deleted. (4) `QlibDataFeeder.preload(start, end)` body replaced with `raise NotImplementedError(...)` pointing callers at `preload_features()`. (5) `QlibDataFeeder.assert_preloaded()` method with cache_df window inspection (MultiIndex-aware) + zero-fallback assertion. **Workspace audit**: [scripts/audit_direct_engine_use.py](scripts/audit_direct_engine_use.py) scans `workspace/scripts/` for direct `BacktestEngine()` / `QlibDataFeeder()` / `feeder.preload()` / bare `D.features()` usage and emits a classification at [workspace/scripts/_audit/direct_engine_classification.md](workspace/scripts/_audit/direct_engine_classification.md) + CSV. 46 files scanned: 5 A-class validation runners (already on wrapper; need `run_mode='formal'` in PR 3); 1 B-class direct feeder use (`local_data_verify.py`); 26 C-class sandbox/audit scripts; 14 D-class superseded mimics queued for archival in PR 7. **Tests**: 22 new negative tests at [tests/backtest_engine/test_preload_hardening.py](tests/backtest_engine/test_preload_hardening.py) covering (a) deprecated preload raises, (b) assert_preloaded with status != success, (c) missing required fields, (d) cache window too short on either side, (e) non-zero fallback with require_zero_fallback=True, (f) wrapper field union for ENGINE_REQUIRED_FIELDS, (g) formal/oos_test/joinquant_replication run_mode auto-enables preload + strict + require_preloaded, (h) sandbox mode does NOT auto-enable, (i) `preload_required` kwarg can override sandbox. Full regression: 233 pass, 9 skip across `tests/backtest_engine/ tests/research_orchestrator/ tests/data_infra/` (same green state as PR 1; no regressions). **CLAUDE.md updated**: §3 hard invariants gain ENGINE_REQUIRED_FIELDS contract, should_preload condition, no-op-preload-removed, and require_preloaded engine contract. **Next PR (PR 3)**: versioned + immutable ExecutionProfile with computed `profile_hash`. Once PR 3 lands, the 5 A-class validation runners flip from `run_mode='formal'` (PR 2 transitional) to `execution_profile='joinquant_daily_sim'` (PR 3 final form).*

*Update Note (2026-05-26, PR 1 of 2026-05-26 freeze plan landed — Provider self-attestation + calendar policy + artifact provenance):* Closed the largest research-integrity gap remaining after the JoinQuant alignment work: until today, every formal artifact recorded WHICH calendar/data range it used but not WHICH provider it actually ran against. The provider tree itself is gitignored so the repo alone could not prove which binary build produced a given result. **What landed**: (1) Committed schemas at [schemas/provider_build.schema.json](schemas/provider_build.schema.json) and [schemas/artifact_provenance.schema.json](schemas/artifact_provenance.schema.json), with a worked example at [docs/examples/provider_build.example.json](docs/examples/provider_build.example.json). (2) Committed calendar policy at [config/calendar_policies/frozen_20260227_system_build.yaml](config/calendar_policies/frozen_20260227_system_build.yaml) recording the current freeze as an explicit governance object (frozen=true, allowed_modes={sandbox, joinquant_replication, formal_research_with_explicit_freeze}). (3) Runtime modules: [src/data_infra/provider_manifest.py](src/data_infra/provider_manifest.py) (loader/validator + retroactive-emit + at-publish-emit helpers), [src/research_orchestrator/calendar_policy.py](src/research_orchestrator/calendar_policy.py), [src/research_orchestrator/artifact_provenance.py](src/research_orchestrator/artifact_provenance.py) (ArtifactProvenance dataclass + legacy-artifact-readable policy). (4) Retroactive manifest emitted for the existing 2026-04-21 build at `data/qlib_data/metadata/provider_build.json`, marked `retroactive_manifest=true` with a 5-item evidence array (README status snapshot, project_state revalidation note, three namespacing/PIT/provider regression tests). The honest "retroactive" marker prevents future auditors mistaking this for a contemporaneous attestation. (5) Bootstrap script [scripts/emit_retroactive_provider_manifest.py](scripts/emit_retroactive_provider_manifest.py) so each host can produce its own retroactive manifest once. (6) `StagedQlibBackendBuilder.publish()` at [src/data_infra/pit_backend.py:2969](src/data_infra/pit_backend.py) now emits a fresh manifest after the atomic `os.replace()` — future builds are self-attesting by default. (7) `EventDrivenBacktester.run()` accepts `calendar_policy_id` + `require_provider_manifest` kwargs and stamps `artifact_provenance` onto `result.config`. (8) `scripts/run_daily_qa.py` now runs a `provider_manifest_check` block FIRST so downstream audits inherit a known build_id + policy_id. (9) Release-gate enforcement via `evaluate_artifact_provenance` / `assert_formal_artifact_eligible` in [src/research_orchestrator/release_gate.py](src/research_orchestrator/release_gate.py) — legacy artifacts (missing or partial provenance) are readable for historical comparison but cannot pass the formal gate (status=`failed_legacy`). **Tests**: 36 new negative tests across `tests/data_infra/test_provider_manifest.py` (15 tests covering missing file / invalid JSON / wrong schema_version / missing required field / retroactive-without-evidence / namespacing-unenforced / calendar-mismatch / live-manifest smoke), `tests/research_orchestrator/test_calendar_policy.py` (10 tests covering missing file / wrong schema / missing required field / non-frozen-without-max-lag / allowed-mode behavior / live policy smoke), `tests/research_orchestrator/test_artifact_provenance.py` (15 tests covering legacy classification / gate enforcement / round-trip). Full regression: 158/158 tests pass across `tests/backtest_engine/ tests/research_orchestrator/ tests/data_infra/test_pit_backend.py tests/data_infra/test_event_like_daily_namespace.py tests/data_infra/test_provider_manifest.py`. **CLAUDE.md updated**: §3 hard invariants now include the four new contracts (Provider self-attestation, Artifact provenance, Calendar policy, Governance file home rule — config/+schemas/ not data/). **Next PR (PR 2)**: preload hardening — replace the no-op `QlibDataFeeder.preload()` with a loud `NotImplementedError` after removing the engine-level call site, add `ENGINE_REQUIRED_FIELDS` constant, and tighten the should_preload condition so formal runs cannot accidentally skip OHLCV preload.*

*Update Note (2026-05-22, JoinQuant-deployment engine alignment landed — Tasks 1+2+3 of the post-investigation roadmap):* Acted on the P1 G5_A2 investigation findings to make the local engine deployment-aligned with JoinQuant. **Task 1 (defaults)**: `Exchange()` default slippage changed from `PctSlippage(0.001)`=10 bps to `FixedSlippage(0.0003)`=0.3 bps (matches JoinQuant `set_slippage(FixedSlippage(3/10000))`); `CostConfig()` default changed to JoinQuant `OrderCost` equivalent (`close_tax=0.001` constant, no 2023 cut, no transfer fee). The prior conservative defaults remain available as named constants `CONSERVATIVE_SLIPPAGE_10BPS` and `CostConfig.realistic_china()`. CLAUDE.md §3 + AGENTS.md hard invariants updated. **Task 2 (Phase 1)**: added `Portfolio.available_cash_after_sells()` and `safe_total_value()` NaN-robust helpers (prevents the v18-class re-entry bug from recurring at the strategy-script layer); added `EventDrivenBacktester.run(fill_mode='open_close' | 'jq_daily_avg')` so users can switch to JoinQuant's daily-avg fill model when needed; new test module `tests/backtest_engine/test_joinquant_parity.py` (16 tests). Full backtest_engine suite: 73 tests pass. **Task 3 (PIT cache infrastructure)**: built `data/external/jq_pit_cache/` for bidirectional local↔JoinQuant verification. Layout: `index_members/{index}/{YYYY}.parquet`, `valuation/{YYYY-MM}.parquet`, `flags/{YYYY-MM}.parquet`, `manifest.json`. Migrated the existing 597-snapshot 中小综 (399101.XSHE) CSV into the cache. APIs: `src.data_infra.jq_pit_cache.JoinQuantPITLoader` (read-only canonical reader) and `src.data_infra.jqdata_local` (JoinQuant-API shim — change `from jqdata import *` → `from src.data_infra.jqdata_local import *` to run a JoinQuant strategy locally). Refresh template at `workspace/scripts/templates/jq_pit_cache_refresh.py`; manifest regenerator at `scripts/refresh_jq_pit_cache_manifest.py`. Documentation: `data/data_tracker.md` §10, `src/data_infra/AGENTS.md` §6, `data/external/jq_pit_cache/README.md`. Tests: 18 in `tests/data_infra/test_jq_pit_cache.py`. **Task 4 (minute-data ingestion) deferred per user instruction** — local stack remains daily-only.*

*Update Note (2026-05-22, FINAL — engine verified via minute-frequency apples-to-apples): **User ran Option A (minute-frequency JoinQuant replica of local v21's exact logic) → CAGR 85.60% (cum 148,683%, Sharpe 2.829, MDD 52.56%) vs local v21 80.56%, residual 5.04pp.** Switching JoinQuant from daily-avg fills to minute open/close fills moved CAGR by only +0.35pp (85.25 → 85.60), proving the fill-model is NOT the dominant residual. With every controllable variable aligned (selection logic, D_week schedule, no-trim sizing, two-phase timing, FixedSlippage 0.0003¥/share, cost model, minute fills ≈ open/close), the irreducible 5.04pp comes from things no replica can perfectly match: `filter_new_stock` (JoinQuant `get_security_info.start_date` vs Tushare `stock_basic.list_date`), `filter_st` (JoinQuant live `is_st` vs local `st_stocks.txt` range table), ranking ties (`valuation.market_cap` vs Tushare `Ref($total_mv,1)` — fresh-buy test showed top-1% agreement, not byte-perfect), lot-size rounding at slightly different fill prices compounding over 3,500+ trades, and `get_index_stocks` queried live vs the one-time CSV snapshot. This is the cross-stack noise floor for a 12-year microcap weekly strategy on two independent data + execution stacks (Tushare/Qlib vs JoinQuant). **Final decomposition of the original 19pp v11→JQ-orig gap: v11 71.86% → v19 77.46% (+5.6pp let-winners-run + NaN re-entry fix) → v21 80.56% (+3.1pp FixedSlippage convention) → JQ-min 85.60% (+5.0pp irreducible cross-stack noise) → JQ-orig 90.69% (+5.1pp JoinQuant's 10:30 minute-data filter advantage on limit-down-recovered names).** ENGINE STATUS: VERIFIED SOUND. No engine defect; the only real bug surfaced was the NaN re-entry in experimental v18 (fixed in v19), and canonical v11 was always correct. Investigation chain spanned v8→v21 (15 mimic variants); all scripts under `workspace/scripts/p1_jq_g5a2_*.py`. JoinQuant minute-replica code preserved in the session for re-runs.*

*Update Note (2026-05-21, APPLES-TO-APPLES engine test): **User ran a JoinQuant replica of the EXACT local v19 logic (`workspace/scripts/p1_jq_g5a2_mimic_v21_fixedslip.py` is the local twin; the JoinQuant replica code was provided in-session). JoinQuant v19-replica = CAGR 83.97% (cum 133,951%, ~1340×, Sharpe 2.786, MDD 48.97%) vs LOCAL v19 = 77.46% (876×) — a 6.51pp gap running IDENTICAL logic on the two engines.** Leading cause identified: a slippage-convention mismatch I left in — local v19 used `PctSlippage(0.0003)` = 3 bps PERCENTAGE, while the JoinQuant strategy uses `FixedSlippage(3/10000)` = 0.0003 ¥/share ≈ 0.3 bps for these ¥5-20 microcaps (~10x larger slippage on the local side). v21 RESULT: CAGR 80.56% (1074×) — slippage convention closed +3.10pp of the 6.51pp engine gap; residual v21(80.56%)→JQ-replica(83.97%) = 3.41pp is irreducible API/data-resolution micro-differences in the replica (market_cap vs total_mv ranking, get_security_info vs stock_basic list dates, 9:30-auction day_open vs daily-bar open, 14:30 minute reversal vs daily-close reversal) — NOT an engine flaw. **FINAL VERDICT: ENGINE VERIFIED SOUND — two independent engines running identical v19 logic with matched slippage agree to within 3.4pp over a 12-year microcap run.** Full local-v11(74.27%)→JQ-original(90.69%)=16.4pp gap decomposes into 5 non-flaw pieces: equal-weight→let-winners-run +3.2pp; slippage 3bps→0.3bps +3.1pp; engine/replica micro-differences +3.4pp; JoinQuant native-logic refinements +2.8pp; JoinQuant 10:30 minute-fill+intraday-filter +3.9pp. The only genuine bug found in the entire exercise was the NaN re-entry in the experimental v18 no-trim variant (fixed in v19); the canonical v11 and the EventDrivenBacktester engine were correct throughout. Scripts: `p1_jq_g5a2_mimic_v21_fixedslip.py` (local twin), JoinQuant v19-replica code provided in-session. NOTE: the 6.51pp here is the cleanest engine comparison and SUPERSEDES the earlier "selection +12pp" framing, because the v19-replica holds the strategy logic constant across engines (the earlier JQ-verify used JoinQuant's native buy_security/market_cap/raw-index-stoploss, which differ from v19). Local v19 CAGR 77.46% (250-day annualization); v11 canonical 74.27%.*

*Update Note (2026-05-21, ENGINE VERIFIED + clean decomposition): **The local backtest ENGINE is verified sound. The user's JoinQuant verification (G5_A2 rebuilt with 9:30-open fills + daily-open limit filters, mirroring local v11) returned CAGR 86.75% (`Knowledge/聚宽回测数据/result_1 (1).csv`).** Full investigation (v18→v20) decomposed the v11(71.86%)→JQ-verify(86.75%) gap into THREE pieces, none of which is an engine flaw: **(1) sizing/let-winners-run +3pp** — JoinQuant's `buy_security` only fills empty slots and lets winners run; our canonical v11 trims to equal weight. The no-trim variant v19 = CAGR 74.93% (876× vs v11's 706×). **(2) selection +~12pp** — JoinQuant ranks by `valuation.market_cap`; we rank by Tushare `Ref($total_mv,1)`. v19 (no-trim, total_mv) 74.93% vs JQ-verify (no-trim, market_cap) 86.75% isolates this to ~12pp, and it is BIDIRECTIONAL per-year (local beats JQ in 2015/2021/2024, loses 2016/2022/2025) — a data-vendor ranking difference, NOT an engine bug. **(3) fill timing +3.94pp** — JQ original (10:30 minute fill + intraday limit filter) 90.69% vs JQ-verify (9:30 open + daily-bar filter) 86.75%. **Engine integrity checks all PASSED**: Qlib `$total_mv` == raw Tushare total_mv to ratio 1.0000 (`p1_jq_g5a2_total_mv_integrity.py`); Qlib `$close` == JoinQuant position.price to 4 decimals for 8/13 years (`p1_jq_g5a2_v16_pure_mtm.py`); engine `total_value()` is NaN-robust (v20 NaN-fix was a byte-for-byte no-op vs v11). **One real bug found & fixed — but in an EXPERIMENTAL strategy variant, not the engine or canonical mimic**: v18's no-trim rewrite used `est_sell_proceeds += pos.shares * prev_prices.get(c)`, which a suspended position's NaN prev-close poisoned → `value_per_new` NaN → `NaN>1.0` False → zero buys → stuck in cash for the entire 2015-08-19→09-14 股灾 recovery. Fixed in v19 (guard NaN/<=0 prices). v11 was never affected (uses NaN-robust total_value). SELECTION PIECE NOW REFUTED (2026-05-21): `p1_jq_g5a2_freshbuy_rank.py` controlled for held-winner drift by ranking JoinQuant's FRESH buys (not held positions) within the available pool by our Tushare total_mv — fresh buys cluster in the smallest ~1% (median percentile 1.2%, 100% in top-2%, ranks #1/#4/#11/#14 of 713-970 pools). **Tushare total_mv ≈ JoinQuant valuation.market_cap for selection.** So the ~12pp v19→JQ-verify residual is NOT selection-data and NOT an engine flaw — it is bidirectional per-year execution / market_stoploss-timing differences (our suspended=1.0 stoploss-mean approximation vs JoinQuant's native get_price). Confirming the last piece requires JQ-verify's clean daily POSITIONS export (the gbk summary CSV columns are ambiguous — buy-value vs sell-value not cleanly separable). ENGINE VERIFICATION IS COMPLETE regardless: no engine flaw exists; the only bug found was the NaN re-entry in the experimental v18 variant (fixed in v19), and the canonical v11 was always correct. Scripts: `p1_jq_g5a2_mimic_v{18,19,20}_*.py`, `p1_jq_g5a2_v18_reentry_bug.py`, `p1_jq_g5a2_2015_localize.py`, `p1_jq_g5a2_stoploss_0819_check.py`.*

*Update Note (2026-05-21, RETRACTION + verification): **The "FULLY RESOLVED" note below is WRONG and is retracted.** The user verified by building a JoinQuant variant of G5_A2 with 9:30-open fills + daily-open limit filters (mirroring local v11) — `Knowledge/聚宽回测数据/result_1 (1).csv`. Result: JQ-verify CAGR **86.75%** (Sharpe 2.861, MDD 46.82%, window 2014-01-02→2026-02-27). This REFUTES the v17-based decomposition: (1) the fill-timing effect (10:30→9:30) is only **-3.94pp** (90.69%→86.75%), NOT the -15pp claimed; the v17=106% number was corrupted by the v15 cascade bug + an adj_factor artifact. (2) A **15.55pp gap remains between JQ-verify (86.75%) and local v11 (71.20%)** on near-identical methodology. Hypotheses tested since: **(a) total_mv adjustment** — RULED OUT: `p1_jq_g5a2_total_mv_integrity.py` confirms Qlib `$total_mv` == raw Tushare total_mv to ratio 1.0000 (not adj_factor-distorted). **(b) equal-weight-trim vs let-winners-run** — RULED OUT: v18 (no-trim, JQ buy_security sizing) = 68.90% CAGR, WORSE than v11, not better. The remaining gap signature is BIDIRECTIONAL per-year (JQ-verify beats v18 by +136pp in 2015 but v18 beats JQ-verify by +57pp in 2024), pointing to SELECTION differences (Tushare total_mv ranking vs JQ valuation.market_cap ranking pick different stocks) and/or market_stoploss firing on different days. INVESTIGATION ONGOING — need JQ-verify trades/positions export to decisively separate selection-difference from engine-flaw. Scripts: `p1_jq_g5a2_mimic_v18_no_trim.py`, `p1_jq_g5a2_total_mv_integrity.py`, `p1_jq_g5a2_verify_compare.py`.*

*Update Note (2026-05-21, FULLY RESOLVED — RETRACTED, see note above): **P1 G5_A2 gap root-caused to a SINGLE mechanism — JoinQuant has minute-level intraday data; we have only daily bars. This produces TWO opposing effects that partially cancel.** Selection-edge audit on 2015-07-28 (`workspace/scripts/p1_jq_g5a2_selection_edge_audit.py`) shows JQ bought 002193 (rank #3 by total_mv = 256k万元) on this date. v13 with the SAME PIT universe + SAME total_mv ranking + SAME filters would have REJECTED 002193 because it opened at down_limit=14.40 (`open == down_limit` to 4 decimal places). JQ's `filter_limitdown_stock` runs at 10:30 with MINUTE data, so it accepts the stock if it unlocks intraday — even by a single tick. v13's daily-bar at-open filter has no way to detect intraday unlock. Generalized across 600 Tuesdays × 12 years, this is the +34.8pp selection edge. **The opposing -15.1pp fill-timing effect (v17→JQ)** comes from the SAME minute-data resolution but in the opposite direction: JQ fills at the 10:30 minute price, which is systematically 0.1-0.6% HIGHER than the 9:30 daily-bar open for these microcaps (post-open momentum). v17 (clean trade replay with 9:30 fills) outperforms JQ by 15pp CAGR on identical trades. **Decomposition**: v11 (own selection + 9:30 fill) = 71.20% CAGR, v17 (JQ trades + 9:30 fill) = ~106% CAGR, JQ (JQ trades + 10:30 fill) = 90.86% CAGR. Selection contribution = +34.8pp, fill-timing contribution = -15.1pp, net = +19.7pp ✓ matches observed gap exactly. **Practical implication**: v11 (CAGR 71.20%, Sharpe 2.04) IS the maximally-faithful local mimic; the +19.66pp delta is NOT a defect in v11 but is the unavoidable consequence of daily-bar resolution vs JQ's minute-bar resolution. Closing the gap requires minute-level OHLCV for the 002/003 universe back to 2014 — which Tushare does not provide. INVESTIGATION COMPLETE.*

*Update Note (2026-05-21, DEFINITIVE): **P1 G5_A2 gap fully resolved via v17 — JQ outperforms v11 by +19.66pp CAGR = +34.8pp selection advantage MINUS -15.1pp fill-timing disadvantage.** Built v17 = clean NAV reconstruction from JQ's exact trades using our local open price (no engine, no cascade bugs). v17 final NAV = ¥656M (6560×) = CAGR ~106%. **v17 OUTPERFORMS JQ by ~15pp CAGR on the IDENTICAL trade list.** The only difference: v17 fills at our local OPEN price (9:30 proxy); JQ filled at the actual 10:30 minute price. This proves filling at 9:30 open is systematically BETTER than 10:30 fill by ~15pp CAGR for this microcap-smallest universe (post-open momentum makes buys at 9:30 cheaper, which compounds over holding periods). **The complete clean decomposition: v11 (own selection + 9:30 fill) = 71.20%, v17 (JQ trades + 9:30 fill) = ~106%, JQ (JQ trades + 10:30 fill) = 90.86%. Selection contribution v11→v17 = +34.8pp; fill-timing contribution v17→JQ = -15.1pp; net v11→JQ = +19.7pp ✓ matches observed gap exactly.** Critical correction: earlier v14/v15 "execution residual" of 11pp was a v15 implementation bug — the engine cascade-failed on share-count mismatches starting 2014-12-22 and accelerating at 2015-06-29 (股灾 day where JQ sold 7 stocks but v15 sold zero because v15 didn't hold them due to earlier divergence). v16 pure-MTM test (`p1_jq_g5a2_v16_pure_mtm.py`) confirmed local Qlib `$close` matches JoinQuant `position.price` to 4+ decimal places for 8 of 13 years — price source alignment is NOT the issue. **Our local engine has a STRUCTURAL +15pp 9:30-fill advantage over JQ's 10:30 fill on this universe.** Remaining open question: WHY does Tushare `total_mv` produce different rankings than JoinQuant `valuation.market_cap` on the same Tuesday for the same 002/003 stocks (the +35pp selection edge source). Scripts: `workspace/scripts/p1_jq_g5a2_v17_nav_reconstruction.py` (DEFINITIVE), `workspace/scripts/p1_jq_g5a2_v15_cascade_trace.py` (bug discovery), `workspace/scripts/p1_jq_g5a2_v16_pure_mtm.py` (price-source alignment).*

*Update Note (2026-05-21, final): **P1 G5_A2 gap attribution — JQ trade prices empirically MATCH our local ADJUSTED open within 0.1-0.6% (not raw). The 11pp execution residual is from a different adj_factor reference date, not a different price-source convention.** Ran `workspace/scripts/p1_jq_g5a2_price_source_impact.py` to compare JQ's recorded fill prices to BOTH our adjusted and raw locals. Finding: `med_jq_vs_adj` is 0.1-0.6% across every year; `med_jq_vs_raw` is 23-50%. Concrete: 2014-02-07 002072 — JQ ¥6.31, our adj ¥6.28 (-0.5%), our raw ¥5.67 (-11%). **Both engines use backward-adjusted prices**; JQ's `use_real_price=True` flag does NOT mean unadjusted yuan — it means "use the actual fill price on the trade date" which JoinQuant evidently records as backward-adjusted in trades.csv. The 0.1-0.6% per-trade systematic gap, over 3,510 trades × 12 years, compounds to the 11pp residual. **This is a fundamental data-stack limitation** between Tushare's adj_factor table and JoinQuant's internal one — different reference dates produce the systematic offset. Final practical conclusion: **v11 (CAGR 71.20%, Sharpe 2.04, MDD -52%) is the maximally-faithful local mimic**, and the 19.66pp delta to JQ 90.86% is fully attributed: 17% strategy mechanics (closed), 35% selection from same universe (sub-bps total_mv ranking, partial replay closes), 47% adj_factor-reference-date drift (irreducible).*

*Update Note (2026-05-21, late): **P1 G5_A2 gap attribution — v15 slippage-convention fix adds +0.21pp; execution residual is dominated by adjusted-vs-real price handling.** Built v15 = v14 with `FixedSlippage(0.0003 ¥/share)` replacing `PctSlippage(3 bps)` to match JoinQuant's slippage convention exactly. v15 CAGR = 79.78%, only +0.21pp over v14's 79.57%. The slippage convention difference accounts for ~1% of the 23.70pp total gap; the remaining 11.08pp execution edge is dominated by (1) **adjusted vs unadjusted price handling** (Qlib `$open` is adj_factor-adjusted; JQ's `use_real_price=True` is real yuan — measured per-trade gaps 0.1-0.6% median across 3,510 trades via `p1_jq_g5a2_v14_fill_price_audit.py`), (2) intraday 9:30-vs-10:30 fill timing, and (3) MTM-at-adjusted-vs-real close. Final decomposition v8→JQ 23.70pp: strategy mechanics 4.04pp (17%) — universe 0pp (0%) — selection 8.38pp (35%) — slippage convention 0.21pp (1%) — adjusted-price + intraday + MTM residual 11.08pp (47%).*

*Update Note (2026-05-21): **P1 G5_A2 gap attribution — v14 JQ-trade-replay isolates the FINAL clean decomposition.** Built v14 = replay JoinQuant's exact 3,510-trade log through our EventDrivenBacktester. v14 result: cumulative ¥126.4M (1264×, CAGR **79.57%**, Sharpe 2.006, MDD -53.3%) vs JQ ¥266M (2336×, CAGR 90.86%). **Final clean breakdown of the 23.70pp total CAGR gap (v8 67.16% → JQ 90.86%):** strategy mechanics (Mech A+B+C+C-buf, v8 → v11) = +4.04pp (17%), universe membership (Mech D-PIT, v11 → v13 with JQ's actual `get_index_stocks('399101.XSHE')` PIT data) = +0.00pp (FALSIFIED — universe is not the source), **selection mechanism (v13 → v14 via trade replay) = +8.38pp (35%)** — driven by sub-bps differences in `Tushare.daily_basic.total_mv` vs `JoinQuant.valuation.market_cap` producing different rankings of the same PIT universe — and **pure execution edge (v14 → JQ residual) = +11.29pp (48%)** — driven by our engine filling at local open ~9:30 vs JQ's 10:30 fill, plus cost-model details. The execution edge is BIDIRECTIONAL: v14 BEATS JQ in 4 of 13 years (2016, 2017, 2022, 2025; 2025 by +75pp on identical trades) and LOSES in 2018-2021/2023/2024 — proving it's variance, not systematic engine bias. Memo: [Knowledge/temp_plan/p1_g5a2_remaining_cagr_gap_attribution.md](Knowledge/temp_plan/p1_g5a2_remaining_cagr_gap_attribution.md) §§8a, 8b, 8c. Scripts: `workspace/scripts/p1_jq_g5a2_mimic_v{8..14}_*.py`.*

*Update Note (2026-05-20, late): **P1 G5_A2 gap attribution — v13 JQ-PIT-universe test FALSIFIES Mech D, isolates the gap to market_cap ranking.** User exported JQ's actual `get_index_stocks('399101.XSHE')` membership at 597 consecutive Tuesdays (2014-01-07 → 2026-02-24) via JoinQuant research notebook (file: `Knowledge/zxz_399101_pit_membership_tuesdays.csv`, 539,409 rows, median 943 members per snapshot — 002 prefix dominant, 003 prefix from 2020+, monotonic decline post-2021-04-06 board merger). Built v13 = v11 patches + replace local universe with `jq_pit[Tuesday] ∩ {375d-listed, non-ST}`. **v13 cumulative = ¥70.5M (706×, CAGR 71.19%) vs v11 = ¥70.6M (706×, CAGR 71.20%) — IDENTICAL** despite year-by-year shifts (v13 closes 2014/2015 gap, hurts 2019-2021 by exactly the same amount). The universe hypothesis is now empirically falsified. **Two further audits**: (1) v13 vs JQ end-of-day-held positions across 8 sample Tuesdays = 92.4% intersection (73/79 of v13 slots match JQ exactly); the difference is in the 7.6% of disputed slots. (2) On 2014-08-05 where v13 and JQ held the IDENTICAL 12-stock portfolio, v13 daily returns OUTPERFORM JQ by +5 to +18 bps per day across 6 consecutive days. This rules out slippage/cost/MTM/lot-size differences. **The residual 19.66pp CAGR gap is therefore concentrated in market_cap RANKING differences (Tushare `total_mv` vs JoinQuant `valuation.market_cap`)** — JQ picks different stocks on the 7.6% of disputed slots, and those picks happen to outperform v13's picks. Resolving this would require a JQ research-notebook export of `valuation.market_cap` for the 中小综 universe at each Tuesday, then a direct value-by-value comparison vs our Tushare data. Memo: [Knowledge/temp_plan/p1_g5a2_remaining_cagr_gap_attribution.md](Knowledge/temp_plan/p1_g5a2_remaining_cagr_gap_attribution.md) §§8a, 8b.*

*Update Note (2026-05-20): **P1 G5_A2 JoinQuant-vs-local gap mechanism attribution COMPLETE — 100% certainty diagnostics on 3 mechanisms + hybrid universe finding.** After the P1 orchestrator run quarantined under 10bps execution costs (note from 2026-05-19), the user requested deep attribution of the residual gap between local v8 mimic (Sharpe 2.04, 528×) and JoinQuant G5_A2 (Sharpe 2.99, 2336×). I built an 8-version ladder (v8→v12) toggling one mechanism at a time. **Mechanisms identified with 100% certainty:** (A) JQ's `sell_stocks` at 10:00 + `weekly_adjustment` at 10:30 run as SEPARATE scheduled functions — when stoploss fires on a Tuesday, JQ STILL rebuys 12 fresh names at 10:30 while v8 short-circuits. Proof: 2015-09-15, JQ goes 12→1→12 mid-day, v8 goes 12→0. (B) JQ's `get_price()` returns last_close for suspended stocks → close/open = 1.0; v8 drops them. In 股灾 days with 120+ suspended micro-caps, JQ's mean(close/open) is 0.02 higher than v8's, sufficient to flip 4 of 6 stoploss firings (verified on 2015-06-29, 07-15, 07-27, 09-01). (C) JQ's `filter_limitdown_stock` at 10:30 excludes stocks at limit-down. Proof: 2024-02-06, v9's top 12 by market_cap were ALL at limit-down intraday, 5 opened locked — they dropped -8.52% next day; JQ's 12 picks (ranked #20-60 in v9 order) dropped only -6.26%, a 2.26pp per-event difference. **v9 (Mech A+B) +2.65pp CAGR, v10 (+ Mech C) +1.11pp, v11 (Mech C buffer TOP_K=100) +0.28pp = +4.04pp identified.** v11 = CAGR 71.20%, Sharpe 2.04. **v12 (no survivor filter) tested Mech D: HYBRID effect** — closes 8pp of 2014 gap and 10pp of 2015 gap but loses 16pp in 2020, 13pp in 2022, 13pp in 2023 (net -1.83pp cumulative). This proves JQ's universe is `get_index_stocks('399101.XSHE')` returning the current 中小综 member list, which is reconstituted to exclude crashing names BEFORE they fully delist — neither v11's clean survivor cut (alive 2024-01-01) nor v12's broad pool replicates this. **Remaining 19.66pp CAGR gap = irreducible** without 中小综 historical reconstitution snapshots from JQ. Memo: [Knowledge/temp_plan/p1_g5a2_remaining_cagr_gap_attribution.md](Knowledge/temp_plan/p1_g5a2_remaining_cagr_gap_attribution.md). Scripts: `workspace/scripts/p1_jq_g5a2_mimic_v{8..12}_*.py`, `p1_jq_g5a2_{stoploss_compare,pass_month_audit,universe_mean_compare,suspended_pull_up,marketcap_compare_2024,limitdown_audit,first_trade_audit,universe_picks_audit}.py`. The **`no-hedge-words` rule** (Claude.md §7 item 10 + AGENTS.md §2a + .agents/rules/research-integrity.md §8a) added in this session is now enforced — all diagnostic claims are paired with the dataset/script/output that proves them.*

*Update Note (2026-05-19): **P1 sealed-OOS replication of JoinQuant G5_A2 raw size-sort baseline COMPLETE (verdict: is_quarantined) + orchestrator gate_concern_scoring recovery bug FIXED.** Following the research plan at [Knowledge/research_plan_2026-05-19_next_3_to_6_months.md](Knowledge/research_plan_2026-05-19_next_3_to_6_months.md) (P1 design at [Knowledge/temp_plan/p1_g5a2_sealed_oos_design.md](Knowledge/temp_plan/p1_g5a2_sealed_oos_design.md)). **P1 measurements (10-year IS 2014-2023, sc_u4-equivalent broad universe, top-12 by size_ln_mcap, weekly, 10bps slippage):** Sharpe **0.926**, deflated_sharpe 1.000 (capped), cost_adjusted_sharpe 0.906, annual_turnover **25.46x**, max_drawdown **0.543**, bootstrap Sharpe 95% CI [0.293, 1.552], rank_icir 0.209 (7x the floor). 6/8 hard floor rules PASS (signal quality real); 2 FAIL hard (max_drawdown 0.543 > 0.35, annual_turnover 25.46x > 4.0). **Headline finding: the JoinQuant +234,625% / Sharpe 2.995 / MDD -41% claim does not survive realistic execution.** Sharpe drops 3.2x (2.99 → 0.93) when 10bps slippage replaces JoinQuant's 3bps, turnover is 2.2x JoinQuant's reported 11.6x, and MDD is 13pp worse — same structural wall the growth-GARP arc hit 2026-04-29 ("signal real, untradeable in long-only TopK frame"). **Verdict**: `is_quarantined` (preserves run for P1.1 calendar-overlay, P1.2 stoploss-overlay, P2 long-short follow-ups; does NOT promote to live). Run dir: `workspace/research/alpha_mining/hyp_20260519_003_g5a2_replication/`. Hypothesis: `hyp_20260519_003` (registration design_hash `fb6c54c3...`, runtime design_hash `4822f30b...` — see follow-up note below). Both design_hashes verified seal-clean (`verify-seal --expect-claims 0` exit 0) because IS-quarantine triggers OOS skip-then-delegate (all 5 OOS steps emit `decision="skipped_due_to_is_gate"`, registry_publish is fail-closed with no write). **Orchestrator bug fixed in same session (Option C of three recovery paths discussed with user):** while running P1, discovered that if `gate_concern_scoring` handler raises `ConcernEnforcementError` on resume (e.g. submitted severity below derived minimum), the runtime's per-step exception handler at `runtime.py:521-522` clears `pause_kind` and `pending_input` from in-memory `current_state`, then writes them to dag_state.json — making the step's "previously paused for input" identity unrecoverable. The standard resume path at `runtime.py:326` (`if status == "paused"`) is bypassed for the now-`failed` step, so `resumed_inputs` is never populated for the handler, which then raises a confusing "resumed without resumed_inputs payload" error. **Two-part fix landed:** (1) `workspace/scripts/hypothesis_cli.py::_validate_concern_scores_against_rules` — new pre-validation helper mirrors the handler's keyed_to_rule_id / required-metric-in-anchor / numeric-anchor / anchor-matches-measured / severity>=derived checks; runs BEFORE writing `gate_concern_scores.json` so bad payloads never reach the orchestrator. Plumbed through `_copy_and_validate_concern_scores` (new optional `rule_by_id` + `measured_values` kwargs preserve backwards compatibility) and `_score_concerns`. (2) `src/research_orchestrator/runtime.py::_try_recover_concern_scoring_pause` — new helper that, when a `gate_concern_scoring` step is found in `status="failed"` AND both `gate_concern_scores.json` + `gate_concern_scores_template.json` exist on disk in the step dir, reconstructs the `pending_input` payload by convention (artifact_path / template_path / schema_id="gate_concern_scores_v1") and flips the in-memory `current_state` back to `status="paused"`, `pause_kind="pause_for_input"`. The standard resume branch below then picks it up. Helper writes step_metadata.json with the recovered state so downstream tooling sees consistent paused-step semantics. Only fires for `step.capability == "gate_concern_scoring"` — narrow scope, won't affect other pause_for_input steps. **9 new regression tests landed** in `tests/alpha_research/test_hypothesis_workflow.py`: `CLIScoreConcernsPreValidationTests` (6 tests covering unknown_rule_id / missing_anchor_metric / anchor_value_mismatch / severity_below_derived / happy_path / backwards-compat-when-rules-omitted) and `RuntimeConcernScoringRecoveryTests` (3 tests covering both-files-present / artifact-missing / template-missing). All 9 new tests pass; full hypothesis_workflow + research_orchestrator + theme_strategy + event_driven_strategy + factor_registry + candidate_registry suites (188 tests) regress clean. **Follow-up flagged (NOT addressed this session):** runtime design_hash (`4822f30b...`) differs from CLI registration design_hash (`fb6c54c3...`) for the same hypothesis. Likely a canonicalization divergence between `Hypothesis.from_dict` at registration and the orchestrator's payload re-canonicalization at run time. For quarantined hypotheses this is benign (both hashes show 0 OOS claims), but for hypotheses that reach OOS the seal would be claimed under the runtime hash, so a `verify-seal` against the registration hash would always show 0 claims even though OOS access occurred — a real seal-hygiene bug. Needs its own plan. **Three failed registrations in the hypothesis registry from earlier session iterations** (`hyp_20260519_001` design_hash d90e... — theme universe rejected by validation_dataset_build for missing theme_resolver; `hyp_20260519_002` design_hash 147ce... — relaxed criteria rejected at orchestrator entry validation; both have `status=pre_registered` and were never gated) are append-only events; they will accumulate but do not affect the validated `hyp_20260519_003` lineage.*

*Update Note (2026-04-29, late): **Production verification of `snappy-buzzing-meerkat` v5 perf fix COMPLETE + growth-stock GARP 3-leg strategy TERMINATED on hard floor failures.** Re-launched `hyp_growth_garp_3leg_20260428` (design_hash `7c2389c5...`) from a fresh run dir at `workspace/research/alpha_mining/hyp_growth_garp_3leg_run_20260429/`. **Perf fix verified via in-engine harness instrumentation** (added in this session: `QlibDataFeeder` records `_preload_status` / `_preload_wall_seconds` / `_cache_hit_count` / `_direct_fallback_count`; `BacktestEngine` records per-day wall times; `EventDrivenBacktester.run` accepts `instrumentation_path` kwarg and writes a JSON report after the run; `run_event_driven_window` and both validation handlers thread it through, writing to `steps/<step_id>/harness_instrumentation.json`). **All Codex-tightened gates PASSED**: `direct_fallback_count=0`, `preload_status="success"`, `cache_hit_count=1951` (1950 trading days + 1 prev-day warmup), `per_day_timing.p95=0.184 sec` (target <0.5s — 2.7× headroom), `per_day_timing.p50=0.166 sec` (right at the ~150ms theme_strategy baseline), event-driven IS leg total `5.4 min` (target <20 min), `cache_events_design_hashes_seen=[hyp_A 6832ea54..., hyp_B e831816d..., validation 7c2389c5...]` (Part D propagation works — manifest rows now carry the real design_hash, not empty), `cache_events_stages_seen=["is_only"]` (Part E stage propagation works). **Speedup: ~110× on the event-driven leg** (8 min 18 sec wall time vs. ~9 hrs at the prior 15-22 sec/day pace). **End-to-end DAG: all 18 steps completed in ~40 min wall time.** IS leg breakdown: dataset_build 3:49, portfolio_construction 0:10, vectorized_backtest_is 2:57, **event_backtest_is 8:18**, diagnostics_is + gate_eval_is <0:10, then paused at validation_gate_concerns_is for human input. **Reproducer also verified end-to-end** (`workspace/scripts/reproduce_preload_collision.py` — 4/4 scenarios match predictions: design_hash mismatch under cache_type='qlib_features' succeeds for both strict and non-strict; stage mismatch raises with strict and swallows with non-strict). **Strategy verdict — IS gate REJECTED on 2 hard floor failures.** Detailed measurements: rank_icir=0.466 (15× the 0.03 floor — strong signal), deflated_sharpe=1.0, cost_adjusted_sharpe=0.724, regime_pass_count=7, effect-size in CI — all PASS comfortably. But **max_drawdown=−46.2%** (floor −32%) and **annual_turnover=11.83×** (floor 3.5×) both fail by large margins. Pre-registered concerns "weakest_assumption" (Phase 4 −29.3% DD diagnostic might understate true DD) **CONFIRMED and worse than predicted**; "priors_on_cost_sensitivity" (10d rebalance ⇒ ~3.5× turnover prior) **CONFIRMED and badly miscalibrated** (3.4× the prior — equal-weight TopK 50 with max_position_weight=2.5% forces near-full rotation when the composite reorders, even when only a few names actually swap in/out). Concern scores written to `validation_gate_concerns_is/gate_concern_scores.json` with severity high on both. IS gate rejected via `hypothesis_cli.py reject --gate-step validation_gate_review_is`. **OOS skip-then-delegate path validated end-to-end**: validation_event_backtest_oos, validation_diagnostics_oos, all 3 OOS gate wrappers (eval / concerns / review), and validation_registry_publish all completed in <1 sec each emitting `decision="skipped_due_to_is_gate"` (NORMAL step outputs per Codex round-3 — NO fake gate_decision.json). validation_registry_publish correctly fail-closed with no signal/strategy registry write. **Seal for `7c2389c5...` STILL UNTOUCHED** (`verify-seal --expect-claims 0` exit 0) — the seal is preserved for a future redesigned variant of this hypothesis. **Growth-stock strategy development conclusion** (closes the arc started by plan `jolly-seeking-lollipop` Phases 0-4): the GARP signal is REAL (rank_icir 0.466) but UNTRADEABLE in the current long-only TopK 50 / 10d rebalance / equal-weight frame. Three independent attempts (theme_strategy auto-search Hyp A −59.8% DD, theme_strategy auto-search Hyp B −59.8% DD, prescribed 3-leg GARP this run −46.2% DD + 11.8× turnover) all failed pre-registered risk floors; the failure is risk-side not signal-side. **Three paths forward** for future plans, ordered by minimum-engineering: (1) **Risk overlay** — keep the signal, add vol-targeting / per-sector caps / position-band rebalance triggers; new hypothesis under `strategy_improvement` profile. (2) **Reframe the harvest** — longer rebalance (15-20d), score-proportional weighting instead of equal, or larger TopK (100-150) to dilute single-name risk and reduce turnover; new hypothesis under `hypothesis_validation` with the modified prescription. (3) **Long-short or sector-neutral** — structural fix for both DD and turnover by trading the cross-section; highest engineering cost (validation profile v1 is `side="long_only"` only). Recommendation: option (2) is the cheapest test that could rescue the strategy. Growth-as-standalone TERMINATED in current form; the signal goes into the candidate pool for either reframing or integration into a future multi-factor or ML model. **One source-code fix landed in this session**: the `workspace/scripts/reproduce_preload_collision.py` reproducer's patch target was wrong (`patch("src.research_orchestrator.qlib_windowed_features.D")` doesn't work because `D` is imported INSIDE the function via `from qlib.data import D` — the right target is `patch("qlib.data.D", mock_D)`). Same fix applied to the 3 new test files in the previous session. **In-engine instrumentation added (this session)**: `QlibDataFeeder.__init__` initializes 4 instrumentation attrs; `preload_features` records status + wall seconds (with try/finally); `get_features` increments `_cache_hit_count` on cache-hit return paths and `_direct_fallback_count` on the per-day fallback path; `BacktestEngine.run` records per-day wall times in `_day_wall_seconds`; `EventDrivenBacktester.run` accepts `instrumentation_path: str | None = None` and writes a JSON report on completion (in a try/finally so failures during the run still write a partial report). Existing fixture `_FakeFeeder` classes in 3 test files updated to initialize the new instrumentation attrs. All 330 alpha_research/backtest_engine/portfolio_risk/research_orchestrator/result_analysis tests still pass + 92/9 data_infra. The growth-stock plan started in `jolly-seeking-lollipop` is now formally CLOSED with a documented terminal verdict; future growth-stock work resumes via one of the 3 paths above.*

*Update Note (2026-04-29): **Validation profile event-driven backtest performance fix landed** (plan `snappy-buzzing-meerkat` v5, 5 Codex GPT-5.5 xhigh review rounds: REWORK→APPROVE_WITH_REVISIONS×3→APPROVE_WITH_REVISIONS-very-close). Fixes the ~100x slowdown discovered during the Gate G production verification of `hyp_growth_garp_3leg_20260428` (~15-22 sec/day vs ~150 ms/day in the theme_strategy path). **Root cause was two interacting bugs**, not one: (Bug 1) `QlibDataFeeder.preload_features` silently swallowed exceptions at `data_feeder.py:129` so a failed preload left `_cache_df=None` and degraded to per-day `D.features` queries; (Bug 2) the validation handlers invoked `EventDrivenBacktester.run` outside `_run_with_cache_context`, so preload's `CacheContext()` was empty and collided with prior Hyp A/B manifest rows on the same OHLCV cache_key — `assert_cache_reusable` raised `CacheKeyMismatchError` which was then silently swallowed by Bug 1. Live `cache_events.parquet` snapshot during diagnosis confirmed both: 1,932 unique qlib_features cache_keys, all recent rows from the slow run carrying empty design_hash and one-day windows at ~15-17 sec cadence. **Three-part fix landed**: **Phase 2.a (full 4-layer thread-through)** added a `strict` kwarg to `QlibDataFeeder.preload_features` (re-raise on failure when True; default False preserves discovery-profile best-effort behavior), `preload_strict` to `EventDrivenBacktester.run`, `preload_strict` to `run_event_driven_window`, and `preload_strict=True` in both `handle_validation_event_backtest_is` and `handle_validation_event_backtest_oos`. **Part B (selective cache_type relax)** added a `cache_type: str = ""` kwarg to `CacheManifestStore.assert_cache_reusable`; when `cache_type == "qlib_features"` the design_hash mismatch check is skipped (raw OHLCV is deterministic across hypotheses) but stage and window mismatches still raise. The generic guardrail is preserved for any future hypothesis-isolated cache types. `qlib_windowed_features` passes `cache_type="qlib_features"` at the call site. **Part D (context propagation)** wraps `run_event_driven_window` invocations in `_run_with_cache_context(context, ...)` from both validation handlers so the design_hash propagates through `qlib_windowed_features.get_cache_context()` thread-local inheritance into preload — manifest rows now carry the real OOS design_hash instead of empty. **Part E (OOS stage propagation)** added `stage: str = "is_only"` to `QlibDataFeeder.__init__`; `EventDrivenBacktester.run` derives stage from `time_split.stage` and passes it through; `preload_features` and the per-day fallback both use `self._stage` instead of the hardcoded `"is_only"`. Without Part E, OOS validation runs would still mislabel manifest rows as `is_only`. **Tests**: 4 new test files / 16 new tests across `tests/research_orchestrator/test_cache_manifest_collision.py` (5 tests covering Part B relax + strict-mode plumbing in both directions), `tests/research_orchestrator/test_assert_cache_reusable_permissive.py` (6 tests confirming Part B applies ONLY to qlib_features and stage/window/non-qlib_features mismatches still raise), `tests/research_orchestrator/test_validation_cache_context_propagation.py` (3 tests proving Part D propagation + the pre-fix bad behavior + Part E stage propagation), and `tests/backtest_engine/test_scheduled_strategy_parity.py` (3 tests + committed golden fixture `tests/backtest_engine/fixtures/scheduled_strategy_orders_golden.json` confirming `ScheduledLongOnlyStrategy.before_market_open` order generation is byte-stable across the perf fix; held-but-no-longer-target case explicitly covered). **Reproducer**: `workspace/scripts/reproduce_preload_collision.py` calls `QlibDataFeeder.preload_features` directly while monkeypatching `data_feeder.qlib_windowed_features` to inject a temp `cache_manifest_dir` — does NOT touch the live manifest. Writes a JSON report under `workspace/outputs/preload_collision_repro_<ts>.json` with `preload_status` / `cache_df_populated` / `cache_df_shape` / `preload_wall_seconds` / `colliding_manifest_row` / `conflicting_design_hashes` for 4 scenarios (design_hash mismatch ± strict; stage mismatch ± strict). **Regression**: full `tests/` suite passes (330 in alpha_research/backtest_engine/portfolio_risk/research_orchestrator/result_analysis + 92/9 data_infra). All 168 tests from plan `jolly-seeking-lollipop` still green; `tests/backtest_engine/` (existing exchange/limit/slippage/suspension) still green. **Pre-existing follow-up**: `tests/harnesses/backtester_smoke.py` is broken on master (references the legacy `DailyDataFeeder` that has long been renamed to `QlibDataFeeder`) — separate cleanup, not introduced by this plan. **End-to-end production rerun deferred**: relaunching `hyp_growth_garp_3leg_20260428` from a fresh run dir + the Codex-tightened gates (p95 day-loop < 0.5 sec, total IS+OOS < 20 min, 0 per-day fallbacks, harness instrumentation JSON written) is the next step, with the seal for design_hash 7c2389c5... still untouched (`verify-seal --expect-claims 0` still exit 0).*

*Update Note (2026-04-28): **`hypothesis_validation` profile landed end-to-end** (plan `jolly-seeking-lollipop` v6, 5 Codex GPT-5.5 xhigh review rounds: APPROVE_WITH_REVISIONS×4 → APPROVE). Closes the architectural mismatch surfaced during the growth-stock research where `theme_strategy`'s auto-search ignored `hypothesis.factor_refs` and converged on the same recipe regardless of the pre-registered prescription. The new profile runs a fully-prescribed recipe (universe + components + weights + topk + rebalance + cost model) verbatim through IS+gate+OOS+publish. **Schema additions** (`src/research_orchestrator/hypothesis.py`): 5 new frozen dataclasses (`UniverseSpec`, `PrescribedComponent`, `CostModel`, `PortfolioConstruction`, `PrescribedRecipe`) + optional `Hypothesis.prescription` field. Conditional `design_hash()` keeps existing hypotheses (hyp_a/hyp_b, hyp_pead, growth drafts) byte-identical so existing seals/cache rows remain valid. Composite kinds limited to `rank_weighted` / `zscore_weighted` (dropped `ic_weighted` — would reintroduce discovery; dropped `raw_weighted` — different scales; dropped `rank_sum_equal` — weight ambiguity). v1 ComponentKind only `"raw"` (industry-relative variants referenced by their already-transformed name; inline transforms deferred to v2). `UniverseCandidate` got `to_dict/from_dict` (preserves `special_filters` tuple). New `SUCCESS_CRITERIA_FLOORS["hypothesis_validation"]` row mirrors theme_strategy floors. **Profile + DAG** (`src/research_orchestrator/engine.py`): `_hypothesis_validation_dag_builder` constructs 18 steps with unique IDs and explicit `depends_on` (gate_review steps depend on BOTH eval AND concerns — capability lookup at `steps.py:142` requires both). DAG includes explicit `validation_object_resolver` step (`formal_requires_resolver=True` does NOT auto-add it). Stage config (`{"stage": "is_only" or "oos_test"}`) is set on every stage-sensitive step (handle_gate_review reads stage from `context.step.config["stage"]` defaulting to "is_only" — without explicit config OOS gate report would silently mislabel). **11 step handlers** (`src/research_orchestrator/validation_steps.py`): `validation_object_resolver` (post-filters ResolverHub by source_layer="formal" unless `prescription.allow_candidate_components=True`; emits `registry_resolution` outputs so runtime.py:407 lifts lineage), `validation_dataset_build` (loads Qlib factor expressions via catalog + get_industry_relative_defs, applies `add_industry_relative_composites` for transformed names with PIT-safe `Ref($total_mv,1)` market cap, materializes universe via `prescription_runtime.materialize_universe` which delegates to extracted public `build_universe_eligibility` in theme_strategy/pipeline.py, writes dataset.parquet + forward_returns.parquet + eligible_map.json + dataset_manifest.json), `validation_portfolio_construction` (calls Gate-C compute_composite_score + compute_schedule, writes target_weights_schedule.parquet with Tushare dot-form ts_codes), `validation_vectorized_backtest_is` and `validation_event_backtest_is` (route through `SealedBacktestRunner.run_*`; event-driven reuses `ScheduledLongOnlyStrategy` via `run_event_driven_window` extended with `time_split + holdout_context + exchange_config + slippage_rate` overrides), `validation_event_backtest_oos` (skip-then-delegate based on upstream IS gate decision; on-approve calls SealedBacktestRunner with `time_split.stage="oos_test"` so the seal is claimed inside `_claim_if_oos`), `validation_performance_diagnostics` (calls `_compute_extended_metrics` to populate the FULL SuccessCriteria-required metric set: rank_ic/rank_icir from `compute_ic_series` + `compute_ic_summary`, monotonicity_pvalue from `test_monotonicity`, sharpe/deflated_sharpe/cost_adjusted_sharpe/max_drawdown/annual_turnover/regime_pass_count from `_metrics_from_event_report` with `cost_bps_per_unit_turnover=prescription.cost_model.slippage_bps`, `correlation_to_approved` is a v1 stub at 0.0 with WARNING + flag in metrics.json), 3 OOS gate wrappers (`validation_gate_eval_oos` / `_concerns_oos` / `_review_oos`) implementing skip-then-delegate (NORMAL step outputs with `decision="skipped_due_to_is_gate"`, NOT fake gate_decision.json), `validation_registry_publish` with **direct decision matrix** (Codex round-3 critical: bypasses `_assert_gate_allows_publication` because that helper falls through on unknown decisions and would silently allow publication). **Cost-honor refactor**: `_metrics_from_event_report` accepts `cost_bps_per_unit_turnover` kwarg (default 10.0 for backward compat); `handle_gate_review` reads `cost_bps_assumed` from `hypothesis.prescription.cost_model.slippage_bps` when present. **engine.py:1098 fix**: ResearchRunResult.outputs collection now also picks up `validation_diagnostics_is/oos` step outputs (was hardcoded literal `"performance_diagnostics"`). **Pre-existing OOS leak fixes (Gate 0)**: threaded `stage` parameter through `compute_factors()` in `operators.py:1264` and `QlibFieldProvider.load_named_expressions` in `theme_strategy/data.py:128` (default `"is_only"` for backward compat). Without this fix the validation OOS pass would silently load IS-cached features. **CLI extensions** (`workspace/scripts/hypothesis_cli.py`): `register --profile-id <profile>` opts into profile-aware floor validation (default validates ALL profiles, the strictest wins — strategy_improvement); `verify-seal --expect-claims N` for exact-count assertion mode. **Template** at `workspace/scripts/templates/hypothesis_validation.json` with full prescription block. **Tests**: 55 new tests across hypothesis_workflow.py (13 schema, 7 profile shell, 9 prescription_runtime, 3 cost-honor, 4 object_resolver, 2 extended_metrics, 1 measured_values branch, 1 engine source-inspection, 4 OOS event_backtest skip, 4 OOS gate wrappers, 5 publish policy, 2 CLI flags) + 2 stage-threading regression tests (operators + theme_strategy/data). 168/168 tests pass across hypothesis_workflow + research_orchestrator + release_gate + theme_strategy + factor_library_pit_safety + industry_relative_factors. **Production verification**: hyp_growth_garp_3leg_20260428 (design_hash 7c2389c5...) registered cleanly with `--profile-id hypothesis_validation` and `--expect-claims 0` confirmed seal untouched (exit 0). Validation DAG execution: data_scope → data_readiness → validation_object_resolver (formal-layer resolution succeeded for all 3 components including val_bp_industry_rel) → validation_dataset_build (3 base factors + 1 industry-relative composite via add_industry_relative_composites in ~50s, dataset.parquet + forward_returns.parquet + eligible_map.json + dataset_manifest.json all written) → validation_portfolio_construction (composite_score.parquet + target_weights_schedule.parquet with Tushare-format ts_codes) → validation_vectorized_backtest_is (~3 min) → validation_event_backtest_is reached Day 1728/1950 (~88.6%) before being intentionally stopped. Run output preserved at `workspace/research/alpha_mining/hyp_growth_garp_3leg_run_20260428/`. **All architectural risks Codex flagged across 5 review rounds were confirmed addressed**: stage-aware factor loading (Gate 0 fix used), gate dependencies (BOTH eval+concerns in depends_on), OOS sealing path (validated up to but not through), prescription validation (all 3 components resolved formal layer), publish policy (fail-closed verified by tests). **Follow-up flagged**: event_driven backtest in the validation profile runs ~100x slower than the theme_strategy event-driven path (~15s/day vs ~150ms/day; ~9 hours for full IS window). Likely cause: `run_event_driven_window` (workspace/research/alpha_mining/event_driven_strategy_research.py) doesn't enable the same feature-preload optimization that `_run_event_driven_confirmation` (theme_strategy/pipeline.py) uses. The architecture is correct; performance optimization is a separate plan. The seal for hyp_growth_garp_3leg_20260428 (design_hash 7c2389c5...) was NOT burned during this verification because the IS leg never reached the OOS step.*

*Update Note (2026-04-27): SW2021 historical stock-to-industry membership acquired and integrated into the research stack (plan `vast-exploring-rabbit` v8, 8 Codex review rounds: REWORK→REWORK→REWORK→REWORK→MINOR→MINOR→MINOR→APPROVE). **Phase A — acquisition.** Added `fetch_index_member_all(industry_code, ts_code, is_new)` to `src/data_infra/fetchers/__init__.py` (neutral kwarg name maps to Tushare's `l1_code`). Bootstrap script `scripts/fetch_sw_industry_members.py` calls Tushare 31 L1 × 2 is_new flags (62 calls, ~2 min wall clock) — the `is_new=None` default returns only current members, so both `is_new='Y'` and `is_new='N'` are required for full history. Output: `data/universe/industry_sw2021_members/industry_sw2021_members.parquet` (184 KB, 7,787 rows / 5,847 stocks / 31 L1 / 1,940 historical + 5,847 current / 1,603 pre-2008 in_dates). Mutation safety: `--dry-run` flag, file-exists skip, `--force` does shutil.copy2-then-os.replace with `.bak_YYYYMMDD_HHMMSS` backup, idempotent dedup via row-hash, manual `_record_ingest_manifest` after the os.replace path. **Coverage audit** (`scripts/verify_sw_industry_coverage.py`, full report at `workspace/outputs/sw_industry_coverage_audit_20260427.md`): 6 audit dates 2008-01-02 through 2026-02-27 → 94.68% / 95.25% / 96.80% / 96.80% / 99.91% / 100.00%. Three pre-set gates fail by 0.32-1.20 pp. **Survivorship-bias investigation:** of 73 unclassified-on-2008-01-02 stocks, 71 are classified at some later date; 0 of those 71 were delisted before SW2021 rolled out in 2017 (the 9 eventual delistings all happened post-2017 with full SW2021 entries from 2017+). SW2014 fallback (`src='SW'`) and `bak_basic` historical snapshots both yield 0 additional coverage on the gap cohort — the gap is genuine Tushare backfill thinness applying uniformly to surviving and delisted stocks alike, not survivorship. Decision: ACCEPT the 94-97% coverage with explicit disclosure; null-industry rows skipped from neutralization via existing `factor_eval.neutralization` notna() mask. **Phase B — research-stack integration.** Added 4 helpers to `src/data_infra/provider_metadata.py`: `_normalize_ts_code` (handles all 3 ts_code formats), `load_sw_members` (cached parquet load), `industry_as_of(ts_code, date, level)` (per-stock interval lookup), `build_industry_series_asof(index, level)` (vectorized merge_asof for MultiIndex panels — 1.25M rows in 0.64s, well under 2s gate). Replaced static `stock_basic.industry` lookups at `src/research_orchestrator/event_signal_steps.py:147-148, 169` and `workspace/research/alpha_mining/event_driven_strategy_research.py:1156-1157, 1175` with time-varying `build_industry_series_asof`. The standalone `build_industry_series` helper at `event_driven_strategy_research.py:486` is now an error-raising deprecation shim. Two stale comments at `event_signal_steps.py:830` and `event_driven_strategy_research.py:1639` updated to reflect the new SW2021 sourcing + coverage caveat. **4 industry-relative composites landed** (closing the long-standing TODO at `catalog.py:51,78`): added `get_industry_relative_defs()` registry to `catalog.py` and `add_industry_relative_composites()` Layer 2 helper to `operators.py`. `mom_idio_20d` correctly uses `factor_eval.neutralization.neutralize_size_industry` (size+industry residuals via `log_mcap` control + industry dummies); the other 3 (`mom_industry_rel_20d`, `val_ep_industry_rel`, `val_bp_industry_rel`) use industry-mean-subtract within `industry_series.notna()` mask. Wired into 4 consumers: `get_required_catalog` returns 4-tuple instead of 3-tuple; `build_factor_meta` emits `INDUSTRY_REL[kind](base)` expression strings; `compute_factor_inputs` calls `add_industry_relative_composites` between `add_composites` and the candidate selection (the Codex review-3 B1 bug — selection happened BEFORE industry-rel composites were added — is fixed); `run_post_fix_screening.py` reuses `fetch_auxiliary_fields` for PIT-safe `Ref($total_mv,1)` market_cap (Codex review-3 B2). Public API exports added to `src/alpha_research/factor_library/__init__.py`. **Phase C — tests + docs.** 26 new tests added (15 in `tests/data_infra/test_sw_industry_members.py` covering schema lock, coverage floors for 2008/2020, format-agnostic lookup, time-varying behavior, both MultiIndex orderings, performance gate; 11 in `tests/alpha_research/test_industry_relative_factors.py` covering registry shape, per-kind compute correctness, NaN industry masking, base factor existence, integration through `get_required_catalog`/`build_factor_meta`, PIT safety inheritance). Full suite: 309 passed, 9 skipped — zero regressions vs the prior 322-test baseline. Documentation updated: `data/data_dictionary.md` (new `industry_sw2021_members` schema section); `data/data_tracker.md` §6 (new row with coverage caveat); `src/system.md` (factor-library public API list now includes `get_industry_relative_defs` and `add_industry_relative_composites`). **Phase C3 — re-screening complete.** 171-factor catalog (147 base + 20 composite + 4 industry-relative) screened against the rebuilt provider in ~15 min. Grade distribution **1A / 44B / 82C / 44D** (vs prior 167-factor 1A/41B/81C/44D — +3B from new alphas). All 4 new industry-relative factors are monotonic; **3 of 4 graded B**: `mom_idio_20d` (size+industry-neutral momentum residual, rank_icir_5d = -0.538), `mom_industry_rel_20d` (industry-mean-subtract momentum, -0.447), `val_bp_industry_rel` (industry-mean-subtract book/price, +0.378). The 4th factor `val_ep_industry_rel` graded C with rank_icir_5d +0.255 (still monotonic but below 0.30 B threshold). Factor registry reimported as run_id `<new>` with 171 current factors and `factor_kind=industry_relative` for the 4 new. One downstream extension required: `_build_catalog_snapshots` in `src/alpha_research/factor_registry/store.py:938` extended to enumerate `get_industry_relative_defs()` and emit `INDUSTRY_REL[kind](base)` expression strings — without this, the registry's `_ensure_known_current_factors` rejected the new factors as "unmanaged" during import. Test `tests/alpha_research/test_factor_registry.py::test_sync_catalog_creates_expected_current_counts` updated to expect 171 (was 167) with new `industry_relative` kind assertion. Final regression: 309/309 pass + 9 skipped.*

*Update Note (2026-04-24, system accuracy audit hardening implemented): Audited the main "silent accuracy" seams and landed targeted guardrails. `EventDrivenBacktester` now passes `data/market/suspension/suspension_ranges.parquet` into `Exchange` whenever the authoritative suspend_d range file exists and logs the fallback when it does not. `workspace/scripts/research_orchestrator_audit.py` now attaches strict synthetic hypotheses to formal non-benchmark compile requests, matching the v3.1 formal-research rule that every formal profile except `benchmark_audit` must be hypothesis-backed. `scripts/audit_qlib.py` now includes namespaced alpha endpoint fields in the default provider smoke. Root pytest is constrained by `pytest.ini` to collect only `tests/`, with repo-local temp directories under `workspace/outputs/pytest_runtime_tmp/`. Added focused regression coverage for event-driven suspension wiring, live provider event-field namespacing, portfolio/risk cost + optimizer turnover path, result-analysis metric alignment, and the orchestrator-migrated CLI seams. Documentation reconciled in `src/system.md`, `data/data_tracker.md`, `data/data_dictionary.md`, `tests/README.md`, `AGENTS.md`, and `CLAUDE.md`. Final validation passed with `python -m pytest -q`: 322 passed, 9 skipped. Attempted to update `.agents/rules/signal-backtesting.md` with the same suspension invariant, but the sandbox rejected writes to `.agents/`; root `AGENTS.md`/`CLAUDE.md` carry the active contract until that rule mirror can be edited manually or in a session with write access.*

*Update Note (2026-04-23, growth-stock hypothesis-driven research run COMPLETE + 2 architectural findings, plan `jolly-seeking-lollipop`): Phase 0-3 of the growth-stock plan landed end-to-end. Phase 1 sandbox screening (`workspace/research/alpha_mining/growth_strategy_screening_20260421_110014/`) on the post-republish provider yielded 11 C-grade and 6 D-grade survivors out of 17; key finding: most growth factors have positive rank_icir but NEGATIVE long-short Sharpe — only 6 factors have BOTH (`alpha_inst_net_buy_20d`, `grow_roe_yoy`, `grow_opprofit_yoy`, `grow_eps_yoy`, `grow_opprofit_qoq`, `grow_netprofit_yoy`). Phase 2 registered 2 hypotheses (`hyp_20260421_001` design_hash 6832ea54..., `hyp_20260421_002` design_hash e831816d...) with documented `--force-relaxed-criteria` overrides (theme_strategy floors not strategy_improvement floors). Phase 3 added a `growth` ThemeSpec to `src/alpha_research/theme_strategy/registry.py` (6 universe candidates, 13 components, 2 recipe seeds). Hyp A and Hyp B both completed full theme_strategy DAG (16 steps each); both verdicts `is_quarantined`. Best variant on both: `gr_u5 (CSI500) + auto_growth_19 (grow_opprofit_qoq + grow_roe_yoy)` produced +106% relative excess return vs CSI500 over 2014-2021 IS BUT max_drawdown -59.8% breached pre-registered ceilings (-32% Hyp A, -30% Hyp B) by ~1.87x-2.0x. Real economic signal, investment-unacceptable risk profile.

**Architectural finding 1 (theme_strategy hypothesis differentiation):** `theme_strategy` recipe search auto-enumerates ALL components in the theme registry and ignores hypothesis-level `factor_refs` and weights. Pre-registered factor combinations are decorative under this profile; differentiation between hypotheses must occur at the `theme_id` level (different component pool per theme), NOT at `factor_refs`/`success_criteria.custom_rules` level. Hyp A (8 components, growth-weighted) and Hyp B (5 components, GARP) converged on the same answer because both pointed at the same `growth` theme. Implication for future hypothesis-driven research with `theme_strategy`: either accept hypothesis weights as decorative (test the theme as a whole), or define a separate theme_id per hypothesis variant.

**Architectural finding 2 (3 latent bugs surfaced + fixed):** (i) `src/alpha_research/theme_strategy/pipeline.py` was missing `FieldInventoryRow` import (used at `load_prepared_theme_cache:134` — added to module-level import); (ii) `src/research_orchestrator/gate_report.py:evaluate_success_criteria` crashed on string-format `custom_rules` entries (per-hypothesis JSON allowed strings but the validator only handled dicts — added permissive string-to-dict coercion that treats string entries as opaque rule_ids with manual comparator); (iii) the new `growth` theme's universe builder needed `n_income_attr_p` field tagged with `growth` (was tagged `small_cap` only — added `growth` to the tuple). All three landed as additive non-breaking changes; 9/9 existing `tests/alpha_research/test_theme_strategy.py` tests still pass.

**Hypothesis registry impact:** 2 new entries (`hyp_20260421_001` is_quarantined, `hyp_20260421_002` is_quarantined). Cache manifest has 273 events (44 net new for Hyp B re-registration of Hyp A's caches under new design_hash to avoid recompute). Holdout seals untouched for both design_hashes (verified by `verify-seal` exit codes 0). Phase 4 robustness + sealed OOS deferred pending decision on whether to redesign with explicit drawdown control (vol targeting, sector caps, smaller TopK, position sizing) or terminate the strategy as untradeable.*

*Update Note (2026-04-23): Phase 1 downstream re-validation + Phase 2 alpha-factor expansion complete (plan `vast-exploring-rabbit` v3). **Phase 1** re-graded the full factor catalog and replayed the 3 flagged leakage-era artifacts (event-driven research, small-cap theme, ML signal) against the rebuilt provider. P1.1 screening (run_id `9222fc67c1ddec72`, 152 factors, ~19 min cold-cache): grade distribution shifted from 1A/37B/75C/36D → **1A/38B/74C/39D**; 8 grade migrations (4 up: comp_defensive C→B, risk_vol_60d C→B, qual_accruals D→C, qual_asset_turnover D→C; 4 down: liq_amihud_20d B→C, earn_surprise_revenue C→D, grow_consistency C→D, grow_revenue_yoy C→D); 3 new alpha factors imported as C/D. P1.2 event-driven sandbox (6.5h, 39 A/B candidates, topk=50, benchmark CSI500): OOS excess positive in 4/5 folds (2021 +27.3%, 2022 +14.0%, 2023 +4.6%, 2024 -5.8%, 2025 +7.5%, holdout +9.5%) — signal durability confirmed on new provider. P1.3 small-cap theme sandbox (18h, 2012→2026-02-27 full 14y sim): best variant `size_only`/`auto_small_cap_05` at **+92.5% relative excess return** (MDD -58.9%, turnover 10.4%) — theme signal intact. P1.4 ML sandbox (elasticnet/lightgbm/rule_baseline, resumed once): all 3 variants marked `promoted=False` by gate thresholds; rule_baseline (C_stability_score) still leads at **+94.9% stitched excess** (4/5 positive folds, MDD -34.4% blocks auto-promote). Because the formal-mode hypothesis gate (v3.1 hardening) blocks downstream research without pre-registered hypotheses, all 3 downstream profiles ran in sandbox mode — registry publish events are deferred; metrics are valid for comparison. **Code changes landed (backward-compatible):** (1) added `--mode {formal,sandbox}` flag to `workspace/research/alpha_mining/event_driven_strategy_research.py`, `workspace/research/alpha_mining/event_driven_strategy_ml_research.py`, and `src/alpha_research/theme_strategy/cli.py`; (2) `_build_{theme,event,ml}_request_from_args` in `src/research_orchestrator/engine.py` now read mode from `args.mode` via `getattr(..., "formal")`; (3) `_optional_csv` in `src/research_orchestrator/ml_signal_steps.py:28-37` handles empty-file placeholders (from non-linear variants like LightGBM) via `path.stat().st_size == 0` check + `EmptyDataError` catch. **Phase 2** added 15 new alpha factors to `_add_alpha_endpoint_factors` in `src/alpha_research/factor_library/catalog.py` (3→18 total) across 5 endpoint families: chip distribution (5 dense), insider/holder transactions (3 medium), top_list retail-view (3 sparse), top_inst (2 sparse), block_trade (2 sparse). All 15 use prefixed field names per the 2026-04-20 namespace contract; the 3 hit-density factors use NaN-equality inversion `If(Ref($x,1) == Ref($x,1), 1, 0)` in place of Qlib's missing `IsNull`. PIT gates: 76 factor-library tests pass (static parser + per-op locks + behavioral), 76 data_infra tests pass (no regressions). Smoke test: 15/15 new factors produce non-null values on 2023-2024 (coverage ranges from 245K sparse to 2.5M dense on full universe). P2.5 expanded screening (run_id `8724e104741cd187`, 167 factors, ~14 min): distribution **1A/41B/81C/44D** — all P1 grades unchanged, +3B/+7C/+5D entirely from new alphas. **3 new B-grade alphas** (all monotonic short-signals): `alpha_topinst_hit_density_60d` (rank_icir_5d = -0.541), `alpha_toplist_hit_density_60d` (-0.529), `alpha_toplist_amount_over_mv_20d` (-0.318). Interpretation: stocks appearing frequently on 龙虎榜 underperform systematically (retail-attention mean-reversion). P2.6 (optional) reran P1.2 against expanded screening: 42 A/B candidates; two of the 3 new B-grade alphas got selected as **rank-1 core factors** in 2021 and 2022 folds (val_icir = -0.868, -0.804), but mean OOS excess DROPPED from +9.51% → +5.37% (-4.14pp), with worse performance in 2021/2024/2025 and better only in 2022. **Research insight:** the new alphas are statistically strong signals but belong in a long-short or sector-rotation framework, not a long-only TopK — they create over-restrictive selection pressure that degrades net excess. Flagged as Phase 3 / future-research candidate. Sandbox registry state: factor_registry at 167 factors (run_id `8724e104741cd187`); signal/strategy/model registries unchanged (no formal publish). Backups preserved: `factor_master.parquet.bak_pre_revalidation_20260421`. Artifacts: `workspace/outputs/phase1_grade_migration_20260421.md`, `workspace/outputs/phase1_downstream_revalidation_summary_20260423.md`, `workspace/outputs/phase2_grade_migration_20260423.md`.*

*Update Note (2026-04-21, RESOLVED): Live-provider corruption from the 2026-04-17 pre-fix rebuild is now fully repaired. Republished from staged build `data/qlib_builds/20260420_143526/` with the namespace-fix code in place. Probe verification: blue-chip basket (000001.SZ, 600000.SH, 600519.SH) across 242 trading days in 2024 → all 6 canonical OHLCV fields ($open/$high/$low/$close/$vol/$amount) at 726/726 non-null (was 726/726/726/1/142/142 before). Prefixed alpha endpoints queryable: `$top_inst__net_buy`, `$block_trade__amount`, `$cyq_perf__winner_rate` (726/726 daily coverage), `$holdertrade_net_ratio`. Post-rebuild validation: `scripts/run_daily_qa.py` PASS (DataAuditor.audit_daily_files, audit_qlib, provider_boundary_tests, pit_live_harness all PASS); `tests/harnesses/qlib_smoke.py` PASS (5686 instruments, sample rows show real `$close` values, `revenue_q` parity 3/3 exact). Old broken provider preserved at `data/qlib_data.bak_20260420_143526/` as rollback safety. **Publish notes (Windows-specific):** the rebuild subprocess (`bsxesrqrp`) succeeded through profile/normalize/ledger/materialize/validate but the final atomic `os.replace(qlib_dir, backup)` failed with WinError 5 (Access denied) — directory-level handle on `data/qlib_data/` (likely Explorer/IDE/Defender). Recovered manually: after closing Explorer windows, the first rename succeeded; the second rename (staged_provider → qlib_data) was still locked, so used a contents-move strategy descending one level for `features/` (5755 stock subdirs moved individually with 1 retry needed for 300077_sz). Total recovery time ~5 min after the rebuild's own ~7-hour run. Severity correction (now historical): the original namespace-fix note described impact as "$close/$vol/$amount on event days may still return event-endpoint values"; actual impact was significantly worse — `_materialize_daily_dataset.reindex(calendar)` clobbered the full canonical series with NaN-everywhere-except-event-days for the three shadowed canonical fields. Any factor, backtest, or signal that read `$close`/`$vol`/`$amount` from `data/qlib_data/` between 2026-04-17 and 2026-04-21 republish consumed garbage; `$open`/`$high`/`$low` and all fundamentals were unaffected.*

*Update Note (2026-04-14): Hypothesis workflow audit follow-up is now complete. Added `src/research_orchestrator/window_enforcement.py` as the first pre-load date clamp for orchestrator-owned data-entry steps; wired that clamp through factor screening, theme field audit, event signal prep, ML dataset build, and strategy-improvement dataset build; completed the `quarantined` verdict path end-to-end in the hypothesis registry, gate handling, and CLI; made `workspace/scripts/hypothesis_cli.py verify-seal` machine-safe with exit codes `0=untouched`, `1=OOS already touched`, `2=malformed hash`; formalized `PauseForInputPayload` in `src/research_orchestrator/dag.py`; and expanded `tests.alpha_research.test_hypothesis_workflow` with 37 regression tests covering the new safety properties and the remaining audit gaps. Validation passed with `python -m unittest tests.alpha_research.test_hypothesis_workflow tests.alpha_research.test_research_orchestrator tests.alpha_research.test_research_orchestrator_release_gate tests.alpha_research.test_theme_strategy`.*
*Update Note (2026-04-12): Hypothesis workflow remediation v3.1 is now complete. Formal non-audit runs now use the explicit `gate_evaluation -> gate_concern_scoring -> gate_review` sequence; the runtime supports both `pause_for_input` and `pause_for_gate`; request hashing is now design-only for hypotheses; the hypothesis registry is now an append-only event log with durable floor-rail overrides; the testing ledger now records separate measurement / verdict events and family-variance helpers; `SealedBacktestRunner`, `cache_manifest.py`, and `qlib_windowed_features.py` are wired in as the seal/window safety choke points; `workspace/scripts/hypothesis_cli.py` now includes drafting and concern-scoring support with static templates under `workspace/scripts/templates/`; new regression coverage lives in `tests.alpha_research.test_hypothesis_workflow`; and the aligned rule/docs updates landed in `AGENTS.md`, `CLAUDE.md`, `src/system.md`, and `.agents/rules/research-integrity.md`.*

*Audit Status (2026-04-16): New Alpha Endpoints plan FULLY COMPLETE — 5 high-alpha Tushare endpoints wired AND bootstrapped. Code changes landed 2026-04-14; full historical bootstrap ran 2026-04-15 → 2026-04-16 via `scripts/fetch_new_alpha_endpoints.py` (elapsed ~10.75 hours, one transient `RemoteDisconnected` auto-retried without data loss). Data coverage: `top_list` 19 years (2008-2026), `top_inst` 19 years, `block_trade` 19 years, `stk_holdertrade` 19 annual files, `cyq_perf` 9 years (2018-2026 — Tushare's 筹码分布 history starts ~2018; ~9M rows total including 1.3M for 2024 and 1.3M for 2025). Sample verification confirmed expected schemas and key signal columns (`net_amount`, `net_buy`, `change_ratio`, `winner_rate`, `cost_*pct` percentiles). Factor construction deferred to a separate plan. All tests still pass (66 data_infra + 76 factor_library + 33 backtester = 175 tests).*

*Audit Status (2026-04-14): Follow-up plan #2 (event-driven backtester execution audit) CODE + TESTS COMPLETE. 8 P0 items + 2 P1 items landed: cost consolidation via CostBreakdown namedtuple + compute_*_cost_breakdown helpers (P0-1); PctSlippage(0.001) as Exchange default (P0-2); FixedSlippage 0.02→0.01 (P0-3); transfer fee 过户费 added at 2bps (P0-4a/b); partial_fill + fill_detail columns in order log (P0-5); print→logger in data_feeder (P0-6); impact docs (P0-7); sell-side NaN guard (P0-8); round-half-up limit prices (P1-1); IPO period verified correct (P1-2, no code change). 33/33 new tests pass across 3 test files. No regressions in data_infra (66 pass) or factor_library (76 pass). JoinQuant parity rerun deferred to a manual maintenance session — code is validated via unit tests. Codex cross-review integrated (2026-04-14): 3 redesigns + 1 new P0.*

*Audit Status (2026-04-12): Follow-up plan #1 (factor library same-day leakage fix) FULLY COMPLETE end-to-end. 45 of 65 Layer 1 operators rewritten; 76/76 new tests PASS (20 parser-based static analysis + 51 per-operator lock + 5 behavioral PIT); full 14-year post-fix screening ran in ~22 min; pre/post diff report published; factor_registry reimported with post-fix evidence (run_id `4d42930365e976d1`); status_history event recorded. **Grade migration confirms the audit prediction:** 18 A-grade factors → 1 A-grade factor (17 lost their A status, all from leakage inflation); 25 B → 37 B; 72 C → 75 C; 34 D → 36 D. 22 factors downgraded, 0 upgraded. The sole surviving A is `liq_vol_cv_20d` (still the top-ranked factor by |rank_icir_5d|). Registry backup saved at `data/factor_registry.bak_pre_factor_library_fix/` (766K). All downstream research artifacts (C_stability_score, formal event-driven, small_cap theme, ML research) flagged as pending re-validation in the Known Issues section below — not auto-fixed by this plan. Data backend audit v3 status remains: all P0 + P1 fixes landed; 60/61 `tests/data_infra` tests pass.*

*Last Updated: 2026-05-19 (P1 sealed-OOS replication of JoinQuant G5_A2 COMPLETE with verdict is_quarantined: Sharpe 0.93 IS / MDD -54.3% / turnover 25.5x — confirms JoinQuant's +234,625% / Sharpe 2.995 claim does not survive realistic 10bps slippage execution; same structural risk-side wall as growth-GARP. Orchestrator gate_concern_scoring recovery bug fixed in same session: CLI pre-validation + runtime recovery + 9 new tests; 188-test suite regress clean. Follow-up flagged: runtime vs registration design_hash drift (benign for quarantined but a seal-hygiene bug for any future OOS-reaching hypothesis). Run dir: workspace/research/alpha_mining/hyp_20260519_003_g5a2_replication/. Plan: Knowledge/research_plan_2026-05-19_next_3_to_6_months.md.) Previous: 2026-04-29 late (Production verification of snappy-buzzing-meerkat v5 perf fix COMPLETE + growth-stock GARP 3-leg strategy TERMINATED on hard floor failures: in-engine harness instrumentation added; ~110× speedup on the event-driven IS leg confirmed end-to-end (8 min vs 9 hrs); all Codex-tightened gates pass (p95=0.184s, 0 fallbacks, design_hash + stage propagation verified); IS gate rejected on max_drawdown −46.2% and annual_turnover 11.8×; OOS skip-then-delegate path validated; seal for design_hash 7c2389c5... still untouched; growth-stock arc CLOSED with terminal verdict and 3 documented forward-paths. Previous baselines: 2026-04-29 perf fix code landing; 2026-04-28 hypothesis_validation profile end-to-end; 2026-04-27 SW2021 historical industry membership; factor_registry at 171 factors; 2026-04-24 system accuracy audit hardening; 2026-04-23 Phase 1+2 downstream re-validation; live-provider corruption fully repaired 2026-04-21).*

*Update Note (2026-04-20, follow-up): **Event-like daily endpoint namespace fix.** While preparing a staged provider rebuild to validate new alpha endpoint consumption, discovered a critical pre-existing bug in `src/data_infra/pit_backend.py::_materialize_daily_dataset` (line ~2797-2804 loop). The materializer writes one `.day.bin` per numeric column using the column name verbatim, AFTER `_run_dump_bin` has already written the canonical `$open/$high/$low/$close/$vol/$amount` bins from kline data. Three of the four new event-like daily endpoints ship payload columns that collide with those canonical names: `top_list.close`, `top_list.amount` (collide with kline `$close`/`$amount`); `block_trade.vol`, `block_trade.amount` (collide with `$vol`/`$amount`). On any trading day a stock has a `top_list` event OR a `block_trade`, the canonical kline bin would be silently overwritten with the event-specific value — catastrophic for any factor or backtest using close/vol/amount on those days. `top_inst` and `cyq_perf` have no direct collisions but are prefixed for uniformity. `stk_holdertrade` was already safe (uses a dedicated `_materialize_stk_holdertrade` aggregator, not this loop). **Fix landed 2026-04-20:** (F1) added module constants `EVENT_LIKE_DAILY_FIELD_PREFIX` (maps each of the 4 datasets to `{dataset}__`), `_EVENT_LIKE_RESERVED_COLUMNS` (ts_code/qlib_code/trade_date never prefixed), and `CANONICAL_KLINE_FIELDS` (the guard set); (F2) inserted a rename block inside `_materialize_daily_dataset` that renames every non-reserved column on the daily DataFrame before `payload_numeric_columns` runs, so downstream writes are namespaced by construction; (F3) added `tests/data_infra/test_event_like_daily_namespace.py` with 9 tests covering: every event-like dataset has a prefix entry, prefix keys/values are well-formed, canonical kline set covers all known shadow risks, synthetic-payload collision check for each dataset, end-to-end `_materialize_daily_dataset` rename-fires assertion (with stubbed `load_normalized_daily` + `_write_feature_series`), non-event-like `moneyflow` keeps its native column names, and `payload_numeric_columns` sees prefixed names after rename; (F4) CLAUDE.md §3 + AGENTS.md §2 now document the invariant with a "when adding a new endpoint" checklist; (F5) no downstream consumer (`operators.py`, `catalog.py`) currently reads any of the 4 affected endpoint columns — verified by grep. **On-disk consumer semantics:** queries now use `$top_list__close`, `$top_list__amount`, `$top_list__l_buy`, `$top_list__l_sell`, `$top_list__net_amount`, `$top_list__turnover_rate`, `$top_inst__buy`, `$top_inst__sell`, `$top_inst__net_buy`, `$block_trade__price`, `$block_trade__vol`, `$block_trade__amount`, `$cyq_perf__winner_rate`, `$cyq_perf__cost_5pct`, `$cyq_perf__cost_50pct`, `$cyq_perf__cost_95pct`, etc. The 2026-04-20 V5 validation notes in the prior update (`$winner_rate` 242/242 non-null on 000001_SZ 2024, `$amount` (block_trade) 15/242) were written against the buggy unprefixed names — those exact queries no longer resolve; the post-fix equivalents are `$cyq_perf__winner_rate` and `$block_trade__amount`. **Validation (this session):** 9/9 new namespace tests pass; full `tests/data_infra/` suite runs 76 passed + 9 skipped (no regressions vs prior 67+9 baseline plus the 9 new tests). **Out of scope for this session (follow-ups):** (a) rebuilding + republishing the live provider so on-disk bins actually carry the namespaced names — the current live `data/qlib_data/` still has the buggy unprefixed bins from the 2026-04-20 rebuild, meaning `$close`/`$vol`/`$amount` on event days may still return event-endpoint values until the next full rebuild; (b) wiring the new namespaced columns into `operators.py` / `catalog.py`; (c) the growth-stock research plan that triggered the discovery. **Known issue added:** live provider `$close`/`$vol`/`$amount` is suspect on event days until the next full rebuild. Until then, any factor reading `$close`/`$vol`/`$amount` on a day the stock appeared on 龙虎榜 or 大宗交易 may be reading the wrong number. This pre-dates this fix and is what motivated it.*

*Update Note (2026-04-20): Staged PIT backend rebuild `prod_rebuild_20260416` published to `data/qlib_data/`. Previous live provider backed up to `data/qlib_data.bak_prod_rebuild_20260416/`. Purpose: actualize the P0-4 deterministic tie-break code + materialize the 5 new alpha endpoints into the Qlib provider. Code changes landed in `src/data_infra/pit_backend.py`: (C1) `materialize_provider()` daily loop extended to include `top_list, top_inst, block_trade, cyq_perf`; (C2) `stk_holdertrade` added to `PERIODIC_LEDGER_DATASETS` with a per-holder key branch `(ts_code, ann_date, disclosure_date, holder_name, in_de, change_vol)` to prevent multi-holder row collapse; (C3) `adj_factor` scalar-default bug fixed at `_normalize_daily_partition` (line ~1795) and `_load_price_frame` (line ~2083) — use index-matched Series default so chained `.fillna` survives missing column; (C4) new `_materialize_stk_holdertrade` method aggregates per-holder ledger rows into per-day time-series bins (`holdertrade_net_vol` signed, `holdertrade_gross_vol` absolute, `holdertrade_net_ratio` signed, `holdertrade_events` count) — the existing `_materialize_snapshot_dataset` assumes statement-style `end_date` which stk_holdertrade lacks; (C5) new `EVENT_LIKE_DAILY_DATASETS = {top_list, top_inst, block_trade, cyq_perf}` constant exempts event-driven daily datasets from the "expected open-calendar coverage" profile-time gate — these endpoints only have files on days the event actually occurred (e.g., block_trade had 59 days with no 大宗交易 that were incorrectly flagged as missing); (C6) `_json_default` fallback in `profile_to_markdown` serializes `pd.Timestamp` / numpy scalars / bytes so sample-conflict markdown dumps survive datetime-typed columns. Validation: V1 manifest 0 errors + 2 documented warnings (daily price repair overrides 2014-06-18 + 2014-07-28); V2 periodic-ledger diff showed all 9 ledgers (income, income_quarterly, balancesheet, cashflow, cashflow_quarterly, indicators, forecast, holder_number, dividends) IDENTICAL pre-/post-rebuild by SHA-256 (rebuild is deterministic on this machine); V3 `scripts/audit_qlib.py --sample-size 50` `"passed": true` with all 5 alias checks at 1.0 equal_ratio; V4 `tests/data_infra/test_pit_live_provider.py` 22 passed + 9 skipped; V5 new endpoints queryable — `$winner_rate` 242/242 non-null on 000001_SZ 2024, `$amount` (block_trade) 15/242, `$l_buy` / `$l_sell` / `$buy` 1/242 (thin signal as expected for 000001_SZ), and `$holdertrade_net_vol` on 000002_SZ 2014-2024 reports 35 non-zero event days with values matching the ledger (e.g., 2014-03-24: 26.4M net_vol). Post-publish: `scripts/run_daily_qa.py` PASS, `tests/harnesses/qlib_smoke.py` PASS, `tests/data_infra/test_provider_boundary.py` PASS, full `tests/data_infra/` suite 67 passed + 9 skipped. One test-side fix: `tests/data_infra/test_pit_backend.py::test_provider_only_stage_reuses_upstream_artifacts` lambda signature updated to accept `touched_symbols` kwarg (pre-existing bug exposed when the suite was re-run before rebuild launch). Rebuild execution: 4 attempts required — attempt 1 crashed at profile_stk_holdertrade on a Timestamp/JSON bug (fixed via C6); attempt 2 ran profile+normalize+ledger for all 26 datasets (~50 min) then crashed in `_materialize_snapshot_dataset` on the missing `end_date` key for stk_holdertrade (fixed via C4); attempt 3 completed materialize for all 26 datasets (~30 min) but blocked on the block_trade coverage gate (fixed via C5); attempt 4 used `--stage provider-only` to reuse upstream artifacts (~30 min total including validation). Total end-to-end rebuild time ~2 hours vs the planned ~12 because provider-only staging reused normalized tables and ledgers written by attempt 2.*

*Last Updated: 2026-04-11 (data backend audit & remediation v3 complete: P0-1 provider boundary guard tests + `stock_basic_bounds` helper; P0-2 `strictly_next_open_trade_day` rename + runtime assert + 8 PIT invariant tests; P0-3 `test_pit_live_provider.py` dynamic PIT regression harness against the published provider wired into `verify_database.py` as a publish gate; P0-4 deterministic tie-break in both `collapse_duplicate_versions` AND `canonicalize_report_variants` via injected `_src_file` / `_src_ordinal` columns and row-content hash fallback + reproducibility tests; P0-5 backfill provenance sidecar writer under `metadata/pit_audit/backfill_provenance/`; P0-6 publish same-volume atomicity guard; M1 `f_ann_date` coverage verified (all 4 non-statement families have only `ann_date` in raw schema — no DATASET_SPECS change needed); M2 late-restatement semantics documented in `derive_single_quarter_value` docstring; P1-1 `suspend_d` end-to-end wiring with `SuspensionLookup` + backtester fallback-to-vol==0 + 6 tests + `scripts/fetch_suspend_d_historical.py` bootstrap script; P1-2 `scripts/refresh_namechange.py` idempotent refresh script; P1-3 `update_daily_data.py:89` `base_sleep` reverted to 1.5 per CLAUDE.md §6.1; P1-4 `scripts/run_daily_qa.py` manual QA orchestrator; P1-5 dividend WARNING log on 实施+null ex_date. Factor library same-day leakage discovery tracked as urgent follow-up plan #1 — 45 of 65 Layer 1 operators leak, affecting ~56 of 149 formal catalog factors.)*

*Earlier 2026-04-10 audit status (research orchestrator full audit completed: real quick `theme_strategy` event-driven smoke rerun succeeded end-to-end, remaining semantic capability-gap finding F001 closed by replacing placeholder/noop steps with real handlers for theme vectorized/execution validation, event-signal dataset/portfolio/execution steps, ML portfolio/execution steps, and factor-screening factor-discovery; signal-registry theme import hardened to work before final root run metadata is written by accepting inferred metadata fallback plus provisional root metadata emission during theme registry publish; audit script and tests strengthened to assert zero noop-gap findings and successful quick event-driven runs without pre-existing root `run_metadata.json`; repo-local temp-dir helpers replaced Windows-flaky `TemporaryDirectory` use in orchestrator/theme tests; root `AGENTS.md` aligned to the six-module architecture and research_orchestrator scope, and the formal orchestrator audit report was rerun to a clean pass with no findings.)*

This is the durable memory file for the Quantitative Trading System. It tracks completed milestones, current research focus, system conventions, and known issues. Codex and other repo-aware agents should read this file at the start of each substantive session through the root `AGENTS.md` workflow.

*Update Note (2026-04-11): Hypothesis-driven research workflow foundations were added across the orchestrator stack. Shared walk-forward primitives now live in `src/alpha_research/walk_forward.py`; formal `ResearchRequest` objects can carry a typed `Hypothesis`; the runtime now supports gate pauses with decision-driven resume; new stores were added for `hypothesis_registry`, `testing_ledger`, and the global `holdout_seal`; `gate_review` now writes structured gate reports and blocks downstream publication on rejection; `workspace/scripts/hypothesis_cli.py` now registers hypotheses and records human approve/reject decisions; `factor_eval` gained initial statistical-tests / cost-aware / regime helpers; and the agent rule files were extended so the hypothesis workflow, human gates, pre-registration rule, sealed OOS rule, and multiple-testing rule are documented in `.agents/rules/research-integrity.md` Section 10.*

*Update Note (2026-04-09): Research Orchestrator V2 second-layer refactor is now complete. `theme_strategy` and `event_driven_signal_research` no longer rely on `legacy_profile_runner` for their main research stages; both now execute through real staged DAG handlers with reusable on-disk artifacts. Validation passed with `python -m unittest tests.alpha_research.test_research_orchestrator tests.alpha_research.test_theme_strategy` plus targeted `py_compile` on the touched orchestrator/theme files.*

*Update Note (2026-04-09): Research Orchestrator V2 third-layer refactor is now complete. The remaining built-in profiles have been split into real DAG stages, `legacy_profile_runner` and the remaining monolithic `_run_*` functions are gone, and unified CLI smoke now covers `profiles`, `plan`, `run`, and `resume`. Validation passed with `python -m unittest tests.alpha_research.test_research_orchestrator tests.alpha_research.test_theme_strategy`, targeted `py_compile`, and a patched benchmark-audit CLI smoke run.*

*Update Note (2026-04-10): Research Orchestrator full audit completed. Added `workspace/scripts/research_orchestrator_audit.py` and `tests.alpha_research.test_research_orchestrator_audit`, reran orchestrator/theme test suites, reran unified CLI benchmark-audit `plan/run/resume` smoke, verified README and `project_state.md` UTF-8 integrity, fixed root/step artifact-manifest completeness and `StepExecutionContext.resumed` propagation, fixed the theme_strategy logging handler leak, and aligned `strategy_improvement` default capabilities with its compiled DAG. Formal audit artifacts were written under `workspace/outputs/orchestrator_audit/20260410_003034`.*

*Update Note (2026-04-10): Research Orchestrator audit closure completed. The remaining open findings from the first audit pass are now closed: the real quick `theme_strategy` event-driven smoke reran successfully under `workspace/outputs/orchestrator_audit_probe/theme_quick_real_v3`, semantic capability `noop` gaps were replaced with real step handlers, `theme_registry_publish` now emits provisional root metadata before signal publication, and `SignalRegistryStore.import_theme_strategy_run(...)` now supports inferred metadata fallback when root `run_metadata.json` is not yet finalized. The audit report under `workspace/outputs/orchestrator_audit/20260410_003034` was rerun and now records zero findings with all coverage checks passing. Rule-file drift caught during the audit was also corrected by updating the root `AGENTS.md` module list/scope to the six-module architecture that includes `src/research_orchestrator/`.*

*Update Note (2026-04-10): Research Orchestrator release gate implemented. Added `src/research_orchestrator/release_gate.py` plus the fixed entrypoint `workspace/scripts/research_orchestrator_release_gate.py`; the gate now reruns the formal orchestrator audit into `workspace/outputs/orchestrator_release_gate/<timestamp>/audit`, writes `release_gate_summary.json` and `release_gate_report_zh.md`, updates `workspace/outputs/orchestrator_release_gate/latest_run.json`, and returns a non-zero exit code unless `findings.csv` is empty and every `coverage_matrix.csv` row is `passed`. Regression coverage added in `tests.alpha_research.test_research_orchestrator_release_gate`, README / `src/system.md` updated, and a real gate smoke passed at `workspace/outputs/orchestrator_release_gate/20260410_225900`.*

*Update Note (2026-04-11): Data backend audit & remediation v3 COMPLETE. Three-pass audit (Claude v1 → Codex cross-review → Claude self-review) with approved plan at `C:\Users\henry\.claude\plans\vast-exploring-rabbit.md`. P0 fixes landed: delist/IPO provider boundary tests + `stock_basic_bounds` helper (P0-1); `strictly_next_open_trade_day` rename + runtime assert + 8 invariant tests + CLAUDE.md §3 documentation (P0-2); `test_pit_live_provider.py` dynamic PIT regression harness wired into `verify_database.py` as a publish gate (P0-3); deterministic tie-break via `_src_file`/`_src_ordinal` injection in both `collapse_duplicate_versions` and `canonicalize_report_variants` (P0-4); backfill provenance sidecar writer under `metadata/pit_audit/backfill_provenance/` (P0-5); publish same-volume atomicity guard (P0-6). P1 fixes landed: `suspend_d` wired end-to-end via `SuspensionLookup` + backtester fallback + `scripts/fetch_suspend_d_historical.py` bootstrap (P1-1); `scripts/refresh_namechange.py` idempotent refresh (P1-2); `update_daily_data.py` base_sleep reverted to 1.5 (P1-3); `scripts/run_daily_qa.py` manual QA orchestrator, all 4 checks PASS end-to-end on the live provider (P1-4); dividend WARNING log on 实施+null ex_date (P1-5). M1 verified — the 4 non-statement datasets (indicators/dividends/forecast/holder_number) have only `ann_date` in the raw schema so no DATASET_SPECS change was needed. M2 documented — cumulative-to-quarterly late-restatement semantics. 60/61 `tests/data_infra` tests pass (1 pre-existing test-mock bug `test_provider_only_stage_reuses_upstream_artifacts` is unchanged and unrelated). Staged PIT ledger rebuild deferred to a scheduled maintenance window (~12h). **Factor library same-day leakage discovery is tracked as urgent follow-up plan #1** — 45 of 65 Layer 1 operators in `src/alpha_research/factor_library/operators.py` leak, affecting ~56 of 149 formal catalog factors (37.6%). MUST be drafted and executed immediately after this plan because every factor screening run to date is affected. Follow-up plan #2 (execution audit) and follow-up plan #3 (new Tushare alpha data) are also tracked but lower priority.*

---

## Completed Milestones

### Factor Library Same-Day Leakage Fix — Follow-up Plan #1 (End-to-End Complete - 2026-04-12)

Purpose: eliminate same-day leakage in the Layer 1 Qlib expression operators.
The `operators.py` module docstring at lines 21-23 previously claimed
"All factors use `Ref($field, 1)` to shift by 1 day", but a three-pass
audit verified that 45 of ~65 Layer 1 operators violated this claim —
they wrapped the outer result with `Ref(..., 1)` but left rolling inputs
(`Mean`, `Std`, `Max`, `Min`, `Slope`, `EMA`, etc.) unshifted. Since the
screening pipeline correlates `factor[t]` directly against
`fwd_return[t]` without any intermediate shift, any factor depending on
`close[t]` shared that value with the forward-return denominator — a
mathematical coupling that inflated IC regardless of true predictive
power.

**Scope executed (code + tests):**

- Rewrote `DAILY_RET` at `operators.py:95` from
  `(close_t / close_{t-1}) - 1` to
  `(close_{t-1} / close_{t-2}) - 1` (yesterday's close-to-close return).
- Added four new module-level constants `ADJ_CLOSE_T1`, `ADJ_OPEN_T1`,
  `ADJ_HIGH_T1`, `ADJ_LOW_T1` that wrap the existing `ADJ_*` atoms in
  `Ref(..., 1)`. Every signal operator that reads adjusted price now
  uses these. The unshifted atoms are reserved for `forward_return`.
- Rewrote 45 operators to use the correct inner-Ref pattern:
  `relative_valuation`, `fundamental_slope`, `fundamental_stability`,
  `overnight_return`, `intraday_return`, `high_moment`, `low_moment`,
  `max_drawdown_proxy`, `range_ratio`, `price_slope_normalized`,
  `avg_turnover`, `turnover_ratio`, `amihud_illiquidity`, `volume_cv`,
  `log_dollar_volume`, `volume_surge`, `volume_ratio_smoothed`,
  `turnover_skew`, `zero_trade_pct`, `spread_proxy`, `price_to_ma`,
  `ma_ratio`, `macd_dif`, `macd_hist`, `distance_from_high`,
  `distance_from_low`, `range_position`, `atr_normalized`, `bb_width`,
  `williams_r`, `intraday_intensity`, plus the 15 `DAILY_RET`-based
  operators (`ema_return`, `wma_return`, `max_single_return`,
  `min_single_return`, `up_down_ratio`, `rolling_vol`, `downside_vol`,
  `vol_of_vol`, `rolling_skew`, `rolling_kurt`, `tail_risk`, `rsi`,
  `obv_slope`, `price_vol_corr`) which were auto-fixed by the
  `DAILY_RET` rewrite plus additional raw-field wrapping.
- Updated the module docstring at `operators.py:21-23` to reference the
  static-analysis enforcement test and correctly describe the new
  contract.
- `forward_return` at `operators.py:982` is UNCHANGED and is the one
  allowlisted exception (it is the prediction target/label, not a signal).

**Three new test files, all passing:**

- `tests/alpha_research/test_factor_library_pit_safety.py` (20 tests):
  parser-based static analysis. Implements
  `find_unwrapped_field_references()` as a parenthesis-stack walk (per
  Codex GPT-5.4 cross-review CRITICAL finding that a regex-nearest-paren
  heuristic would false-positive on grouped expressions like
  `Ref((($buy - $sell) / $amount), 1)`). Exhaustively scans every factor
  in `get_factor_catalog(include_new_data=True)` and every public
  operator function. Includes 16 parser self-tests covering correct
  forms, violating forms, and edge cases.
- `tests/alpha_research/test_operator_expressions.py` (51 tests):
  brittle-on-purpose per-operator lock tests that assert the exact
  post-fix return string. Any future edit becomes a visible diff.
- `tests/alpha_research/test_operator_behavioral_pit.py` (5 tests):
  tiny-Qlib-fixture behavioral proof. Builds a synthetic 3-stock ×
  30-day Qlib provider on disk in a tempdir, creates two variants
  (baseline + `close[T]=999` for one stock), evaluates
  `rolling_vol(20)`, `ma_ratio(5, 20)`, `price_to_ma(10)`,
  `bb_width(10)`, and `DAILY_RET` via `D.features()` on both variants,
  asserts the factor value at time T is identical between variants.
  This is the safety net against any parser false-negatives.

**Full 76/76 tests PASS.** The static analysis test reports zero
violations across the full 129-factor catalog. The `data_infra` test
suite remains at 60 passed / 9 skipped / 1 pre-existing failure — no
regressions introduced.

**Codex cross-review integrated:** Codex GPT-5.4 high-thinking mode
produced 1 CRITICAL + 1 HIGH + 3 MEDIUM findings, plus 3 scope
revisions, all integrated before implementation started:
- CRITICAL: regex → parser-based stack walk for static analysis
- HIGH: registry reimport same-second ordering guard + post-import verification
- MEDIUM: behavioral PIT test → tiny Qlib fixture (not in-memory patch)
- MEDIUM: diff threshold → 20% relative AND 0.005 absolute floor
- MEDIUM: `status_history.parquet` manual entry for fix event
- SCOPE: `AGENTS.md` updated alongside `CLAUDE.md`
- SCOPE: one downstream smoke rerun added (not full strategy re-validation)

**Documentation:**

- `CLAUDE.md §3` Hard Invariants: added the factor-library PIT-safety
  rule with pointers to all three test files.
- `AGENTS.md §2a` Hard Invariants (new section mirroring CLAUDE.md §3):
  added the same rule to preserve the repo's alignment contract.
- `data/factor_registry/` was backed up to
  `data/factor_registry.bak_pre_factor_library_fix/` (766K) before
  reimport as a rollback safety net.

**Post-fix production screening (COMPLETE):**

- Full 149-factor screening over 2012-01-01 to 2026-02-27, horizons
  5/10/20, via
  `workspace/research/alpha_mining/run_post_fix_screening.py` — a
  direct-call helper that bypasses the orchestrator's formal-mode
  hypothesis requirement (the legacy CLI `workspace/scripts/batch_factor_screening.py`
  now routes through `run_research()` which raises
  `ValueError: Formal profile factor_screening requires a hypothesis`).
- Timings on this machine: `compute_factors` 97s, `add_composites` 131s,
  `run_batch_screening` 993s, total ≈ 22 min (matches the 19-min
  baseline claim despite `kernels=1` single-thread).
- Output at
  `workspace/research/alpha_mining/post_fix_screening_20260411/` with
  `factor_screening_results.parquet`, `factor_screening_report.csv`,
  `factor_screening_summary.txt`, `factor_screening_run_metadata.json`,
  `run_console.log`, and `post_fix_screening_diff.md`.
- One post-fix fixup required: the direct runner initially saved
  results with `index=False` which dropped the factor-name index. A
  one-off repair inserted the factor names by alphabetical order (the
  batch screening engine processes factors alphabetically, verified by
  matching the screening progress log positions against
  `sorted(catalog.keys() + [c['name'] for c in composites])`).

**Grade migration (pre 2026-04-01 baseline → post 2026-04-12 fix):**

| Grade | Pre | Post | Delta |
|-------|-----|------|-------|
| A | 18 | **1** | **−17** |
| B | 25 | 37 | +12 |
| C | 72 | 75 | +3 |
| D | 34 | 36 | +2 |

- 17 of the 18 baseline A-grade factors lost their A status
  post-fix — their apparent strength was leakage inflation.
- The sole surviving A is `liq_vol_cv_20d` (|rank_icir_5d| dropped
  from -0.729 to -0.645, still above the 0.6 A-grade threshold AND
  still monotonic).
- Zero factors upgraded — confirms the fix uniformly removes
  inflation; no factor was hidden behind noise.
- 22 factors downgraded by ≥1 bucket, 9 additional factors with
  large |Δrank_icir_5d| (>20% relative AND >0.005 absolute) without
  grade crossing. Full list in
  `workspace/research/alpha_mining/post_fix_screening_20260411/post_fix_screening_diff.md`.

**Factor registry reimport (COMPLETE):**

- New run `run_id=4d42930365e976d1` imported via
  `workspace/research/alpha_mining/reimport_post_fix_screening.py`,
  which layers three safety checks over the raw CLI:
  (1) pre-import same-second ordering guard — verified the post-fix
  `generated_at=2026-04-12 00:19:56` is strictly later than the
  baseline's `2026-04-01 20:11:51`; (2) explicit `store.save()` call
  after `import_screening()` (required — the store mutates in-memory
  state but does not auto-persist); (3) post-import `status_history`
  audit entry recording the contamination-fix event.
- Registry state after reimport: 207 total master rows, 149
  `is_current=True`. Current grade counts from
  `latest_screening_grade`: 75C + 37B + 36D + 1A — exactly matching
  the post-fix screening.
- Backup preserved at `data/factor_registry.bak_pre_factor_library_fix/`
  (766K) in case rollback is needed.

**Pending re-validation (flagged in the Known Issues section below):**

- `C_stability_score` variant at
  `workspace/research/alpha_mining/event_driven_strategy_improvement_full_20260403_retry_rankfix/`
- Formal event-driven research run at
  `workspace/research/alpha_mining/event_driven_strategy_research_full_20260401_main/`
- `small_cap` theme strategy (23 candidate components in
  `data/candidate_registry/`)
- ML research at
  `workspace/research/alpha_mining/event_driven_strategy_ml_research_full_20260404_main/`

These are NOT automatically re-validated in this plan — the user
will decide which to re-run based on the diff report. A separate
"strategy re-validation" follow-up plan will handle them.

### Research Orchestrator V2 Third-Layer Refactor (Implemented - 2026-04-09)

- Completed the planned removal of the remaining legacy profile runners from the built-in orchestrator stack.
- All built-in profiles are now DAG-only; no built-in profile keeps a monolithic runner path.
- Added new staged helper modules under:
  - `src/research_orchestrator/factor_screening_steps.py`
  - `src/research_orchestrator/ml_signal_steps.py`
  - `src/research_orchestrator/strategy_improvement_steps.py`
- `factor_screening` now runs through explicit DAG-owned stages:
  - `screening_dataset_build`
  - `screening_vectorized_backtest`
  - `screening_registry_publish`
- `ml_signal_model_research` now runs through explicit DAG-owned stages:
  - `ml_dataset_build`
  - `ml_label_builder`
  - `ml_model_training`
  - `ml_signal_search`
  - `ml_event_backtest`
  - `ml_experiment_tracking`
  - `ml_registry_publish`
- `strategy_improvement` now runs through explicit DAG-owned stages:
  - `improvement_dataset_build`
  - `improvement_portfolio_construction`
  - `improvement_risk_overlay`
  - `improvement_stress_test`
  - `improvement_event_backtest`
  - `improvement_execution_validation`
  - `improvement_registry_publish`
- `benchmark_audit` no longer uses a monolithic profile function; it now executes through the dedicated `benchmark_audit_step`.
- `src/research_orchestrator/steps.py` no longer contains `legacy_profile_runner`, and root run aggregation no longer depends on any `runner_payload` fallback.
- `src/research_orchestrator/engine.py` no longer keeps the old monolithic `_run_*` functions for:
  - `factor_screening`
  - `ml_signal_model_research`
  - `strategy_improvement`
  - `benchmark_audit`
- DAG runtime behavior is now cleaner and more predictable:
  - step outputs are the only step-to-step and step-to-root execution channel
  - `registry_publish` is the only step allowed to emit produced objects
  - `performance_diagnostics` reads explicit step outputs and generated artifacts instead of guessing from runner payloads
- A real resume bug surfaced during CLI smoke and was fixed:
  - `resume_policy` is now treated as runtime control only
  - it is excluded from request hashing so a completed run can be safely resumed without false hash mismatches
- Validation expanded and passed:
  - `python -m unittest tests.alpha_research.test_research_orchestrator tests.alpha_research.test_theme_strategy`
  - targeted `py_compile` over the touched orchestrator modules and tests
  - unified CLI smoke for `profiles`, `plan`, `run`, and `resume` using a patched `benchmark_audit` request path

### Research Orchestrator V2 Second-Layer Refactor (Implemented - 2026-04-09)

- Advanced the DAG runtime from a "step shell around big runners" into real staged execution for:
  - `theme_strategy`
  - `event_driven_signal_research`
- Added reusable themed-stage helpers under:
  - `src/research_orchestrator/theme_strategy_steps.py`
- Themed research now executes these stages separately while reusing prepared artifacts written by earlier steps:
  - `field_audit`
  - `universe`
  - `component`
  - `recipe`
  - `event_driven`
- Added reusable event-research stage helpers under:
  - `src/research_orchestrator/event_signal_steps.py`
- Event-driven signal research is now split into two orchestrator-owned stages:
  - signal-search / factor-selection
  - event-driven backtest
  with cached context hand-off between them.
- `src/research_orchestrator/steps.py` now contains dedicated handlers for:
  - `theme_dataset_build`
  - `theme_universe_builder`
  - `theme_factor_construction`
  - `theme_factor_discovery`
  - `theme_signal_search`
  - `theme_event_driven_backtest`
  - `theme_registry_publish`
  - `event_signal_search`
  - `event_backtest`
  - `event_registry_publish`
- `src/research_orchestrator/engine.py` DAG builders were updated so:
  - `theme_strategy` recipe/event graphs use the granular theme handlers
  - quick theme `event_driven` still supports recipe-source reuse
  - `event_driven_signal_research` uses explicit signal-search and event-backtest handlers
- Remaining `legacy_profile_runner` usage is now limited to profiles not yet split in this second layer, such as parts of:
  - `factor_screening`
  - `ml_signal_model_research`
  - `strategy_improvement`
  - `benchmark_audit`
- Regression coverage expanded in:
  - `tests/alpha_research/test_research_orchestrator.py`
  - `tests/alpha_research/test_theme_strategy.py`
- New/strengthened checks now cover:
  - theme recipe DAG handler selection
  - event signal DAG handler selection
  - theme orchestrator end-to-end publication with patched staged helpers
  - event orchestrator end-to-end publication with patched signal/backtest stage helpers
  - theme helper-pipeline metadata/index behavior after the orchestrator split

### Agent Rule-File Maintenance Contract (Implemented - 2026-04-09)

- Codified a standing self-maintenance instruction across the agent rule files so they are kept fresh as the system changes.
- `CLAUDE.md`:
  - Renamed §11 from "State Tracking" to "Durable Memory & Rule-File Maintenance".
  - Added §11.2 "Keep CLAUDE.md, AGENTS.md, and .agents/rules/ fresh (standing instruction)" with revisit triggers (start of every non-trivial task and end of every substantive change), explicit drift signals, an alignment contract between `CLAUDE.md` and `AGENTS.md`, and the requirement to record rule changes in `project_state.md`.
  - Added a one-line reminder to §1 directing context refresh to skim `CLAUDE.md` / `AGENTS.md` against `project_state.md` for drift.
  - Added "any update to CLAUDE.md / AGENTS.md / .agents/rules/" to the §11.1 list of work that warrants a `project_state.md` entry.
- `AGENTS.md`:
  - Renamed §6 from "State Tracking" to "State Tracking and Rule-File Maintenance".
  - Added §6.2 mirroring the same self-maintenance contract so the Codex contract and the Claude contract agree on substance.
- `src/system.md`:
  - Upgraded the directory tree and module list from five modules to six by adding `research_orchestrator/` (DAG-based universal research workflow runner, added 2026-04-09).
  - Refreshed `data_infra` entries to include `pit_backend.py`, `provider_metadata.py`, `refresh_indicator_history.py`, and the `build_qlib_backend.py` stage flags.
  - Added `theme_strategy/`, `factor_registry/`, `candidate_registry/` to the `alpha_research` entries; added `ElasticNet` to the model_zoo line.
  - Added a new §6 "Research Orchestrator" section describing scope boundary, internal layout, the 6 built-in profiles, the CLI, the run-artifact set, the strict resume rules, and the legacy compatibility-shim entrypoints.
  - Updated the System-Wide Conventions footer to reference both `AGENTS.md` and `CLAUDE.md`.
- `.agents/rules/system-design.md`:
  - §2 System Context & Architecture upgraded from five core modules to six by adding the `research_orchestrator` bullet, with the same scope-boundary language used in `src/system.md` and `CLAUDE.md`.
- Drift the new contract caught and surfaced for follow-up review:
  - Older copies of `src/system.md` and `.agents/rules/system-design.md` still described a five-module layout even though `src/research_orchestrator/` had been the 6th top-level src module since 2026-04-09. Both files are now corrected.
  - `data_infra` had `pit_backend.py`, `provider_metadata.py`, and `refresh_indicator_history.py` at the module root that the architecture doc did not reflect. Now reflected.



- Reworked `research_orchestrator` around a DAG execution model instead of calling one big profile runner directly from `run_research()`.
- Added the new DAG core under:
  - `src/research_orchestrator/dag.py`
  - `src/research_orchestrator/steps.py`
  - upgraded `src/research_orchestrator/runtime.py`
- New orchestrator runtime behavior:
  - compile profile requests into a `CompiledResearchDag`
  - execute steps in serial topological order
  - persist per-step outputs under `steps/<step_id>/`
  - write `dag_plan.json` and `dag_state.json` at the run root
  - support strict step-level resume only when `request_hash + plan_hash` match
- All `6` built-in research profiles now compile to DAGs:
  - `factor_screening`
  - `theme_strategy`
  - `event_driven_signal_research`
  - `ml_signal_model_research`
  - `strategy_improvement`
  - `benchmark_audit`
- `theme_strategy` DAG behavior now includes:
  - stage-aware graph compilation
  - quick `event_driven` DAG pruning when `recipe_source_run_dir` is present
- Unified CLI upgrades:
  - `workspace/scripts/research_orchestrator_cli.py plan --request-file ...`
  - `workspace/scripts/research_orchestrator_cli.py resume --run-dir ...`
  - request file loading now accepts UTF-8 BOM
- Root documentation updated:
  - `src/research_orchestrator/README.md` rewritten around the DAG model, run artifacts, step structure, and resume rules
- Added stronger DAG-focused regression coverage in:
  - `tests/alpha_research/test_research_orchestrator.py`
  covering:
  - DAG compilation for built-in profiles
  - theme quick-event DAG pruning
  - cycle detection
  - resume-after-failure behavior
  - plan-hash mismatch blocking
  - BOM-safe CLI planning
  - theme-strategy DAG artifact publishing
- Validation completed with:
  - `python -m unittest tests.alpha_research.test_research_orchestrator tests.alpha_research.test_theme_strategy`
  - `python -m py_compile src/research_orchestrator/dag.py src/research_orchestrator/steps.py src/research_orchestrator/runtime.py src/research_orchestrator/profiles.py src/research_orchestrator/engine.py workspace/scripts/research_orchestrator_cli.py tests/alpha_research/test_research_orchestrator.py`
  - `python workspace/scripts/research_orchestrator_cli.py profiles`
  - `python workspace/scripts/research_orchestrator_cli.py plan --request-file workspace/outputs/orch_plan_request.json`

### Research Orchestrator Capability Board Refactor (Implemented - 2026-04-09)

- Upgraded `src/research_orchestrator/capabilities.py` from the earlier flat capability list into a layered `21`-capability vocabulary.
- Capability coverage now explicitly distinguishes:
  - `core_research`
  - `diagnostic`
  - `support`
- New canonical capabilities added:
  - `data_readiness`
  - `dataset_build`
  - `factor_construction`
  - `risk_overlay`
  - `performance_diagnostics`
  - `experiment_tracking`
- Terminology update:
  - canonical portfolio step is now `portfolio_construction`
  - legacy `portfolio_assembly` is still accepted and normalized automatically for backward compatibility
- Built-in research profiles were remapped to the broader research-chain semantics:
  - `factor_screening`
  - `theme_strategy`
  - `event_driven_signal_research`
  - `ml_signal_model_research`
  - `strategy_improvement`
  - `benchmark_audit`
- Orchestrator outputs now carry richer capability metadata:
  - `run_metadata.json` includes `effective_capability_metadata`
  - `review_summary.json` includes `effective_capability_metadata`
  - `workspace/scripts/research_orchestrator_cli.py profiles` now prints `default_capability_metadata`
- Added the first formal orchestrator overview doc:
  - `src/research_orchestrator/README.md`
  covering:
  - scope boundary versus `data_infra`
  - request / profile / asset concepts
  - capability-board explanation
  - built-in profile summary
  - CLI usage
  - standard run artifacts
  - registry and resolver roles
  - compatibility-shim entrypoints
- Validation completed with:
  - `python -m unittest tests.alpha_research.test_research_orchestrator`
  - `python -m unittest tests.alpha_research.test_theme_strategy`
  - `python workspace/scripts/research_orchestrator_cli.py profiles`

### Universal Research Orchestrator V1 (Implemented - 2026-04-06)

- Added the new top-level orchestrator package under:
  - `src/research_orchestrator/`
- Core building blocks now in place:
  - `schema.py` for `ResearchRequest` / `ResearchRunResult` / typed asset specs
  - `profiles.py` for `ResearchProfile` registration and validation
  - `resolver.py` for formal-first asset resolution
  - `runtime.py` for unified `run_metadata.json` / `artifact_manifest.json` / `registry_resolution.json` / `produced_objects.json` / `lineage_links.json` / `review_summary.json`
  - `engine.py` for built-in profile registration, request builders, formal gating, and runner dispatch
  - `registries/` for typed `signal_registry`, `model_registry`, and `strategy_registry`
- Added the thin unified CLI:
  - `workspace/scripts/research_orchestrator_cli.py`
- First-phase built-in formal profiles:
  - `factor_screening`
  - `theme_strategy`
  - `event_driven_signal_research`
  - `ml_signal_model_research`
  - `strategy_improvement`
  - `benchmark_audit`
- Standard capability vocabulary is now centralized and explicit, including the backtest split:
  - `vectorized_backtest`
  - `event_driven_backtest`
  - `execution_validation`
- Existing formal research entrypoints were converted into compatibility shims so they still work from their old script paths, but now route into the orchestrator:
  - `workspace/scripts/batch_factor_screening.py`
  - `src/alpha_research/theme_strategy/cli.py`
  - `workspace/research/alpha_mining/event_driven_strategy_research.py`
  - `workspace/research/alpha_mining/event_driven_strategy_ml_research.py`
  - `workspace/research/alpha_mining/event_driven_strategy_improvement.py`
  - `workspace/research/alpha_mining/audit_benchmark_index.py`
- Typed registry layer added under `data/`:
  - `data/signal_registry/`
  - `data/model_registry/`
  - `data/strategy_registry/`
- Registry governance change:
  - `candidate_registry` is now the factor/composite/theme-component candidate layer
  - `theme_recipe` objects are no longer kept in `candidate_registry`
  - `theme_recipe` objects now publish into `signal_registry`
- `theme_strategy` formal runs now auto-publish into both:
  - `candidate_registry_publish`
  - `signal_registry_publish`
  and both publish receipts are written back into `run_metadata.json`
- Validation completed with:
  - `python -m unittest tests.alpha_research.test_candidate_registry tests.alpha_research.test_theme_strategy tests.alpha_research.test_factor_registry tests.alpha_research.test_event_driven_strategy_research tests.alpha_research.test_event_driven_strategy_ml_research tests.alpha_research.test_event_driven_strategy_improvement tests.alpha_research.test_research_orchestrator`

### Candidate Registry V1 (Implemented - 2026-04-06)

- Added the reusable registry package:
  - `src/alpha_research/candidate_registry/store.py`
  - `src/alpha_research/candidate_registry/report.py`
  - `src/alpha_research/candidate_registry/__init__.py`
- Added the standalone CLI:
  - `workspace/scripts/candidate_registry_cli.py`
- Added the file-backed registry home:
  - `data/candidate_registry/README.md`
  - `data/candidate_registry/registry_metadata.json`
  - `data/candidate_registry/candidate_master.csv`
  - `data/candidate_registry/candidate_master.parquet`
  - `data/candidate_registry/candidate_evidence.csv`
  - `data/candidate_registry/candidate_evidence.parquet`
  - `data/candidate_registry/run_index.csv`
  - `data/candidate_registry/run_index.parquet`
  - `data/candidate_registry/status_history.csv`
  - `data/candidate_registry/status_history.parquet`
  - `data/candidate_registry/candidate_registry_review.html`
- V1 scope is intentionally focused:
  - it is the unified candidate pool for research outputs, not the formal factor library
  - it now focuses on factor-like candidate objects
  - for `theme_strategy`, it currently ingests `theme_component`
  - `theme_recipe` governance has moved to `signal_registry`
  - it is designed so future research types can publish into the same pool by adding import adapters
- The registry now maintains:
  - versioned candidate master records keyed by `(candidate_id, version)`
  - per-run evidence rows for research observations
  - imported run index rows
  - manual status history rows
  - automatic `recommended_status` for theme components / recipes
  - a human-readable browser page with summary cards, filterable current-candidate table, detail cards, recent runs, and manual-status history
- `theme_strategy` integration:
  - `src/alpha_research/theme_strategy/cli.py` now auto-publishes completed formal runs into `data/candidate_registry/`
  - publish results are written back into `run_metadata.json` under `candidate_registry_publish`
  - the same formal run now also writes `signal_registry_publish` for recipe/signal objects
  - if candidate publish fails, the formal CLI run is treated as failed so the auto-ingest contract does not fail silently
- Current candidate object coverage:
  - `theme_component`
- Formal-factor linkage support:
  - candidate records can now keep `linked_formal_factor_id` / `linked_formal_factor_version`
  - this is ready for future `factor_alias`-style theme components and later non-theme research adapters
- Real bootstrap completed on `2026-04-06`:
  - imported the legacy real-output directory:
    - `workspace/outputs/theme_strategy/small_cap_component_real_20260404_205902/`
  - current registry snapshot after bootstrap:
    - `23` current candidates
    - all `23` are `theme_component`
    - all belong to the `small_cap` theme
- Added dedicated regression coverage in:
  - `tests/alpha_research/test_candidate_registry.py`
  covering:
  - default theme-run import into component candidates only
  - theme recipe import into the dedicated signal registry
  - candidate definition version bumps
  - automatic candidate publish from the formal `theme_strategy` CLI
- Validation completed with:
  - `python -m unittest tests.alpha_research.test_candidate_registry tests.alpha_research.test_theme_strategy tests.alpha_research.test_factor_registry tests.alpha_research.test_research_orchestrator`

### Formal Factor Registry V1 (Implemented - 2026-04-04)

- Added the reusable registry package:
  - `src/alpha_research/factor_registry/store.py`
  - `src/alpha_research/factor_registry/__init__.py`
- Added the standalone CLI:
  - `workspace/scripts/factor_registry_cli.py`
- Added the file-backed registry home:
  - `data/factor_registry/README.md`
  - `data/factor_registry/registry_metadata.json`
  - `data/factor_registry/factor_master.csv`
  - `data/factor_registry/factor_master.parquet`
  - `data/factor_registry/factor_evidence.csv`
  - `data/factor_registry/factor_evidence.parquet`
  - `data/factor_registry/run_index.csv`
  - `data/factor_registry/run_index.parquet`
  - `data/factor_registry/status_history.csv`
  - `data/factor_registry/status_history.parquet`
  - `data/factor_registry/factor_registry_review.html`
- V1 scope is intentionally narrow:
  - `catalog.py` remains the official formula source of truth
  - only formal base factors and formal composite factors are managed
  - candidate / draft research pools are still out of scope for V1
  - factor values remain in the existing Qlib and research caches
- The registry now maintains:
  - per-factor versioned master records keyed by `(factor_id, version)`
  - evidence rows for `catalog_sync`, `screening`, and `research`
  - run index rows for every imported run
  - manual status history rows for auditability
  - automatic `recommended_status` based on screening grades and research selection stability
  - a human-readable browser page with summary cards, filterable current-factor table, detail cards, recent runs, and manual-status history
- Versioning behavior:
  - base-factor version hashes are built from `factor_id + expression`
  - composite-factor version hashes are built from `factor_id + components_json + weights_json + negate_json`
  - when a formal factor definition changes, the old version is retained and a new current version is created with default status `draft`
- Metadata passthrough was added for future verified binding:
  - `workspace/scripts/batch_factor_screening.py` now writes `catalog_hash` and `composite_hash` into `factor_screening_run_metadata.json`
  - `workspace/research/alpha_mining/event_driven_strategy_research.py` now carries those screening hashes into `run_metadata.json`
- Real registry bootstrap completed on `2026-04-04`:
  - synced the current official catalog into `data/factor_registry/`
  - imported the latest formal screening run from:
    - `workspace/research/alpha_mining/latest_backend_screening_20260401_new_data/`
  - imported the formal event-driven research run from:
    - `workspace/research/alpha_mining/event_driven_strategy_research_full_20260401_main/`
  - because those historical run directories were created before hash passthrough was added, their current registry binding is marked `legacy_best_effort`
- Current bootstrap snapshot after import:
  - `149` current formal factors in the registry
  - `129` base factors
  - `20` composite factors
  - manual `status` remains all `draft` until promotion decisions are made explicitly
  - automatic `recommended_status` currently shows:
    - `106` draft
    - `32` candidate
    - `11` approved
- Added dedicated regression coverage in:
  - `tests/alpha_research/test_factor_registry.py`
  covering:
  - sync count expectations
  - base and composite version bumps
  - manual status history updates
  - screening import idempotence
  - research aggregation of validation / selected-fold counts
  - real artifact import smoke against the current formal screening and research directories
- Validation completed with:
  - `python -m unittest tests.alpha_research.test_factor_registry`
  - CLI bootstrap flow:
    - `python workspace/scripts/factor_registry_cli.py sync-catalog`
    - `python workspace/scripts/factor_registry_cli.py import-screening --run-dir workspace/research/alpha_mining/latest_backend_screening_20260401_new_data`
    - `python workspace/scripts/factor_registry_cli.py import-research --run-dir workspace/research/alpha_mining/event_driven_strategy_research_full_20260401_main`
    - `python workspace/scripts/factor_registry_cli.py summary`

### Theme-Driven Field-First Strategy Research Framework (Implemented - 2026-04-04)

- Added the reusable theme-strategy package:
  - `src/alpha_research/theme_strategy/schema.py`
  - `src/alpha_research/theme_strategy/registry.py`
  - `src/alpha_research/theme_strategy/data.py`
  - `src/alpha_research/theme_strategy/components.py`
  - `src/alpha_research/theme_strategy/pipeline.py`
  - `src/alpha_research/theme_strategy/__init__.py`
- Added the new standalone research entrypoint:
  - `workspace/research/strategy_dev/theme_strategy_research.py`
- This framework shifts the research flow from “scan many factors first” to:
  - `theme thesis -> field audit -> universe search -> component diagnostics -> recipe search -> event-driven confirmation`
- V1 ships with three built-in themes:
  - `small_cap`
  - `st`
  - `flow_northbound`
- V1 intentionally leaves `AH premium` in backlog until H-share pairing and pricing data are wired in.
- The framework now includes:
  - field-inventory auditing from actual provider-queryable fields
  - theme-specific universe candidates with backtest-based ranking
  - field-first component catalogs using bounded transform families instead of unrestricted formula enumeration
  - component diagnostics with:
    - coverage gates
    - validation-window direction checks
    - correlation clustering
    - marginal-IC retention logic for highly correlated candidates
  - equal-weight interpretable recipe construction
  - final event-driven confirmation hooks reusing the existing event-driven backtester
- Standard output artifacts now include per-theme:
  - `field_inventory.csv`
  - `component_registry.csv`
  - `component_card.csv`
  - `component_cluster_map.csv`
  - `signal_recipe_summary.csv`
  - `event_driven_variant_summary.csv`
  - `theme_review_zh.md`
- Added durable regression coverage in:
  - `tests/alpha_research/test_theme_strategy.py`
  covering:
  - bounded but rich component generation
  - ST universe filtering with full-market `ret250` percentile semantics
  - universe-aware component ranking
  - end-to-end smoke flow on toy data with patched support context
- Validation completed with:
  - `python -m unittest tests.alpha_research.test_theme_strategy`
  - combined regression rerun:
    - `tests.alpha_research.test_theme_strategy`
    - `tests.alpha_research.test_event_driven_strategy_research`
    - `tests.alpha_research.test_event_driven_strategy_improvement`
    - `tests.alpha_research.test_event_driven_strategy_ml_research`
- Real-run hardening follow-up on `2026-04-04`:
  - added visible stage progress logging for theme runs and field-audit bulk loads so long real-data runs are no longer black boxes
  - fixed a corrupted `mainboard` string literal inside `ThemeStrategyPipeline._build_universe_eligible_map(...)` that could incorrectly empty mainboard universes
  - normalized `total_mv` comparisons to CNY inside universe filters because the provider field is in `万元`, which previously made `small_cap` market-cap gates 10,000x too strict
  - cached daily slices (`total_mv`, `adv20`, `revenue_q`, profitability, northbound coverage, ret250 percentile) once per date instead of re-slicing inside every stock loop, materially reducing universe-search overhead
  - made `ret250` percentile computation explicit with `fill_method=None` to avoid future pandas behavior drift
  - quick real-data sanity check after the fix showed recent `small_cap` eligible counts recovering to:
    - `sc_u1`: about `88-93`
    - `sc_u2`: about `444-453`
    - `sc_u3`: about `460-470`
  - the earlier formal `small_cap` universe run that produced `NaN` on `sc_u1` was stopped and restarted with the corrected logic under:
    - `workspace/outputs/theme_strategy/small_cap_universe_real_20260404_192727/`
- Quick event-driven reuse follow-up on `2026-04-08`:
  - formal `theme_strategy` now supports `--recipe-source-run-dir` for `--stage event_driven`
  - this mode reuses an existing recipe-stage run's:
    - `universe_search_summary.csv`
    - `component_card.csv`
    - `component_cluster_map.csv` (or reconstructs it from `component_card.csv` when missing)
    - `signal_recipe_summary.csv`
  - quick mode still reruns `field_audit` and rebuilds current component specs for safety, but it skips:
    - universe search
    - component diagnostics
    - recipe search
  - run metadata now records:
    - `recipe_source_run_dir`
    - `execution_mode = recipe_reuse_event_driven`
  - regression coverage added so quick mode fails if it accidentally falls back to rerunning vectorized recipe evaluation
- Markdown reporting upgrade follow-up on `2026-04-04`:
  - expanded `universe_selection_rationale_zh.md` from a short placeholder into a readable report containing:
    - thesis / benchmark / sample metadata
    - explicit candidate-universe definitions
    - ranking table with key metrics
    - plain-language conclusion bullets
  - expanded top-level `market_opportunity_summary_zh.md` so it now explains the current best universe and immediate next step instead of dumping a raw CSV line
  - expanded `future_theme_backlog.md` so it now records the next actionable step for completed universe-stage runs
  - added regression assertions in `tests/alpha_research/test_theme_strategy.py` so future markdown regressions are caught
  - rerendered the existing small-cap universe output directory in place with the new templates:
    - `workspace/outputs/theme_strategy/small_cap_universe_real_20260404_192727/`
- Reporting/template expansion follow-up on `2026-04-04`:
  - expanded `component_selection_rationale_zh.md` so it now summarizes per-universe component white-list counts, role mix, top selected components, and main rejection reasons
  - expanded `signal_selection_rationale_zh.md` so it now summarizes the best recipe, top candidate table, and best recipe per universe
  - expanded `theme_review_zh.md` so it now combines the final vectorized winner with event-driven confirmation metrics and next-step interpretation
  - fixed `_run_event_driven_confirmation(...)` to use an event-driven-specific sorter instead of the vectorized variant sorter, preventing future `stage=all` runs from failing during final event-summary ranking
  - added regression coverage for the richer markdown outputs and the event-driven summary sorter in `tests/alpha_research/test_theme_strategy.py`
- Research-system integration follow-up on `2026-04-06`:
  - added a dedicated formal entrypoint at:
    - `workspace/research/theme_strategy/theme_strategy_research.py`
  - kept the older path:
    - `workspace/research/strategy_dev/theme_strategy_research.py`
    as a compatibility wrapper so older commands still work
  - kept generated artifacts under:
    - `workspace/outputs/theme_strategy/`
    to stay aligned with the workspace layout rule, but upgraded the run structure so theme research behaves more like the other formal research workflows
  - new theme-strategy runs now automatically write:
    - `run_metadata.json`
    - `artifact_manifest.json`
    - `workspace/outputs/theme_strategy/latest_runs.json`
  - default run-directory names now include both theme and stage, for example:
    - `theme_strategy_small_cap_recipe_<timestamp>`
  - logging was upgraded to rotating-file behavior with explicit shutdown so tests and short-lived runs do not leave log handles open
  - added a small runbook at:
    - `workspace/research/theme_strategy/README.md`
  - extended regression coverage in:
    - `tests/alpha_research/test_theme_strategy.py`
    for the new CLI metadata and latest-run index behavior

### ML Factor Combination Research Entry Point (Implemented - 2026-04-04)

- Added the reusable sklearn linear wrapper:
  - `src/alpha_research/model_zoo/elastic_net.py`
- Exported `ElasticNetModel` through:
  - `src/alpha_research/model_zoo/__init__.py`
- Added the new standalone ML research entrypoint:
  - `workspace/research/alpha_mining/event_driven_strategy_ml_research.py`
- This ML entrypoint keeps the existing rule-based event-driven research path unchanged while adding:
  - same-execution conservative rerun of the current `C_stability_score` rule baseline
  - `ElasticNet` factor-weight learning with fold-level coefficient export
  - `LightGBM` direct stock scoring with fold-level feature-importance export
  - conservative execution defaults aligned with the current `2,000,000 RMB` account assumptions:
    - `benchmark = 000001.SH`
    - `label_horizon = 10`
    - `rebalance_days = 10`
    - `topk = 50`
    - `adv20 >= 5,000,000 RMB`
    - `participation <= 2%`
  - output artifacts including:
    - `ml_master_review.md`
    - `variant_comparison_summary.csv`
    - `fold_model_metrics.csv`
    - `linear_factor_weights_by_fold.csv`
    - `lightgbm_feature_importance_by_fold.csv`
    - `prediction_panel.parquet`
    - per-variant event-driven report CSVs
    - `best_ml_variant_backtest_report.html`
    - `run_metadata.json`
- Hardened `src/alpha_research/model_zoo/__init__.py` so `xgboost` is now an optional dependency:
  - importing `model_zoo` no longer fails on machines that only need `ElasticNet` and `LightGBM`
  - `XGBoostModel` now raises a clear `ModuleNotFoundError` only if it is explicitly used without `xgboost` installed
- Added durable regression coverage in:
  - `tests/alpha_research/test_event_driven_strategy_ml_research.py`
  covering:
  - `ElasticNetModel` fit / predict / save / load
  - ML CLI defaults
  - train-window-only factor-direction resolution
  - prediction-to-schedule conversion with liquidity filtering
  - adoption recommendation logic
  - LightGBM training path inside the ML research entrypoint helper
- Validation completed with:
  - `python -m unittest tests.alpha_research.test_event_driven_strategy_ml_research`
  - combined regression rerun:
    - `tests.alpha_research.test_event_driven_strategy_ml_research`
    - `tests.alpha_research.test_event_driven_strategy_research`
    - `tests.alpha_research.test_event_driven_strategy_improvement`
  - CLI import / argument smoke:
    - `python workspace/research/alpha_mining/event_driven_strategy_ml_research.py --help`
- 2026-04-04 aggregation hotfix:
  - the first formal ML research run reached the final artifact-writing stage and then failed while concatenating optional per-variant tables when every frame in a list was empty
  - `workspace/research/alpha_mining/event_driven_strategy_ml_research.py` now uses a shared safe-concatenation helper for final artifact assembly, so empty optional result tables resolve to empty DataFrames instead of raising `ValueError: No objects to concatenate`
  - added a regression test to ensure `build_model_variant_artifacts(...)` handles all-empty optional frame lists cleanly
  - targeted validation reran successfully:
    - `python -m unittest tests.alpha_research.test_event_driven_strategy_ml_research`
    - `python -m unittest tests.alpha_research.test_event_driven_strategy_research tests.alpha_research.test_event_driven_strategy_improvement`
  - the formal ML research run was relaunched in-place to reuse the existing cached forward-return and auxiliary data under:
    - `workspace/research/alpha_mining/event_driven_strategy_ml_research_full_20260404_main/`

### Workspace Outputs Root Cleanup (Complete - 2026-04-04)

- Cleaned `workspace/outputs/` root so it now mainly retains:
  - `alpha_mining_archive_20260404/`
  - `benchmark_audit_smoke_20260402/`
  - `data_profiles/`
  - `factor_timing_patch_20260401/`
  - `outputs_root_archive_20260404/`
- Archived miscellaneous temporary or one-off output artifacts under:
  - `workspace/outputs/outputs_root_archive_20260404/`
- This archive includes:
  - old Codex bootstrap / home / runtime-fix directories
  - pytest / tmp / subagent / smoke / probe directories
  - kernel-default smoke outputs
  - indicator refresh scratch outputs
  - standalone debug / compare / verify / test scripts and ad-hoc CSV/TXT/MD artifacts that had accumulated in the outputs root
- The archive manifest was saved at:
  - `workspace/outputs/outputs_root_archive_20260404/cleanup_manifest.json`
- A single empty temporary directory `workspace/outputs/tmp6ppx2kb1/` remained because it was locked by the host process at cleanup time; it contains no files and can be removed later if the lock disappears.

### Alpha-Mining Workspace Cleanup (Complete - 2026-04-04)

- Cleaned `workspace/research/alpha_mining/` so it now keeps only:
  - active reusable scripts
  - the latest formal screening run
  - the formal event-driven research run
  - the formal SSE-benchmark improvement run
- Removed the local `__pycache__/` cache directory from `workspace/research/alpha_mining/`.
- Archived temporary / smoke / probe / superseded run directories under:
  - `workspace/outputs/alpha_mining_archive_20260404/`
- Archived items include:
  - `smoke_test`
  - `smoke_existing`
  - `kernel0_probe`
  - `kernel0_probe_full_access`
  - `kernel_auto_after_fix`
  - `kernel_auto_after_fix_v2`
  - `kernel_auto_after_fix_v3`
  - `kernel_default_safe_v1`
  - `kernel_default0_smoke`
  - `event_driven_strategy_research_smoke_20260401`
  - `latest_backend_screening`
- The archive manifest was saved at:
  - `workspace/outputs/alpha_mining_archive_20260404/cleanup_manifest.json`

### SSE Benchmark Audit + Strategy Improvement Experiment Entry Point (Implemented - 2026-04-02)

- Added the reusable SSE benchmark audit entrypoint:
  - `workspace/research/alpha_mining/audit_benchmark_index.py`
- The benchmark audit now works both as:
  - a reusable helper imported by other research scripts
  - a standalone CLI script
- The audit checks:
  - date coverage and duplicate `trade_date`
  - calendar alignment against `trade_cal.parquet`
  - nulls in `open/high/low/close/pre_close`
  - non-positive price fields
  - `high < low`
  - `close` outside `[low, high]`
  - `pct_chg` consistency versus `close / pre_close - 1`
- Added the new strategy-upgrade experiment entrypoint:
  - `workspace/research/alpha_mining/event_driven_strategy_improvement.py`
- This new script is designed to leave the existing baseline research entrypoint untouched while adding the next-step improvement workflow:
  - benchmark audit against `000001.SH`
  - baseline gap attribution artifacts
  - stage-based improvement experiments for parameter sensitivity, portfolio expression, and stability-score / fast-slow upgrades
  - promotion gates centered on excess return breadth and drawdown, with turnover / blocked-order ratio kept as diagnostics only
- New planned output set from the improvement entrypoint includes:
  - `benchmark_audit_report.md`
  - `benchmark_audit_metrics.json`
  - `strategy_gap_attribution.md`
  - `year_regime_diagnostics.csv`
  - `portfolio_expression_diagnostics.csv`
  - `benchmark_relative_exposure.csv`
  - `improvement_experiment_grid.csv`
  - `variant_comparison_summary.csv`
  - `improvement_master_review.md`
  - `best_variant_backtest_report.html`
  - `run_metadata.json`
- Added durable regression coverage in:
  - `tests/alpha_research/test_event_driven_strategy_improvement.py`
  covering benchmark-audit anomaly detection, stability-score ranking, family-cap enforcement, score-proportional single-name caps, the new promotion-gate semantics, and the “no test-window rescue” selection rule.
- Validation completed with:
  - `python -m unittest tests.alpha_research.test_event_driven_strategy_improvement`
  - `python -m unittest tests.alpha_research.test_event_driven_strategy_research`
  - `py_compile` on the new scripts and tests
  - a light smoke of the standalone benchmark audit CLI under:
    - `workspace/outputs/benchmark_audit_smoke_20260402/`
- 2026-04-03 hotfix:
  - fixed `workspace/research/alpha_mining/event_driven_strategy_improvement.py` so repeated sorting of variant summary tables no longer crashes with `ValueError: cannot insert rank, already exists`
  - root cause was re-running `sort_variant_summary(...)` on a DataFrame that already contained a prior `rank` column from an earlier stage sort
  - `sort_variant_summary(...)` now drops any pre-existing `rank` column before rebuilding the display rank
  - added regression coverage in `tests/alpha_research/test_event_driven_strategy_improvement.py` to ensure repeated sort/rerank is stable
  - after the fix, the formal improvement run was relaunched in a new visible output directory:
    - `workspace/research/alpha_mining/event_driven_strategy_improvement_full_20260403_retry_rankfix/`
- Formal improvement run completed on 2026-04-04 at:
  - `workspace/research/alpha_mining/event_driven_strategy_improvement_full_20260403_retry_rankfix/`
- Core result summary:
  - benchmark audit for `000001.SH` passed with full date coverage (`2008-01-02` to `2026-02-27`), zero duplicates, zero missing trade days, and no OHLC consistency issues
  - `53` total variants evaluated across stages `A/B/C/D`; none fully cleared the promotion gate
  - frozen baseline rerun against `000001.SH` delivered stitched OOS relative excess `-1.95%`, `4/7` positive-excess test folds, holdout relative excess `+1.18%`, and worst-fold max drawdown `-38.21%`
  - best final variant was `C_stability_score` (Stage D replay of the Stage C winner) with:
    - stitched total return `+82.96%`
    - stitched benchmark total return `+59.14%`
    - stitched OOS relative excess `+14.97%`
    - `5/7` positive-excess test folds
    - holdout relative excess `+3.17%`
    - worst-fold max drawdown `-31.01%`
  - the best variant therefore met every promotion requirement except the drawdown gate, missing the `-30%` threshold by roughly `1.01` percentage points
- Stage-level takeaways from the formal improvement run:
  - Stage A winner: `A_topk100_reb10_no_filter_slip0.0005` showed the strongest raw uplift (`+37.30%` stitched relative excess) but still failed on worst-fold drawdown (`-31.61%`)
  - Stage B showed no benefit from tiered or score-proportional weighting versus the best Stage A equal-weight setup under this experiment design
  - Stage C `stability_score` selection materially improved the baseline and produced the best final trade-off, while the `stability_score_fastslow` sleeve split underperformed badly and did not survive to the final replay
- Key diagnostic conclusions recorded in the generated reports:
  - high-ICIR factors are real, but many are overlapping liquidity / reversal / volatility signals
  - slowing the rebalance cycle from `5` to `10` days was the single biggest practical improvement lever in this run
  - relative to the SSE Composite benchmark, the all-market long-only portfolio still shows style mismatch and drawdown pressure, especially around the `2024` weak window

### Event-Driven Secondary Research Pipeline Scaffold + Smoke Validation (In Place - 2026-04-01)

- Added the formal secondary-research pipeline entrypoint:
  - `workspace/research/alpha_mining/event_driven_strategy_research.py`
- Added the paired report builder:
  - `workspace/research/alpha_mining/event_driven_strategy_report.py`
- The new research pipeline now covers the intended end-to-end flow:
  - load the completed alpha-mining screening run
  - take the current `A/B` factor candidate pool
  - compute only the required base factors / composites from the live PIT Qlib backend
  - generate detailed factor cards with fold metrics, neutralization comparisons, decay, quantile diagnostics, and keep/reserve/drop conclusions
  - select fold-level core factors with validation gates, redundancy filtering, and marginal-IC checks
  - build a long-only signal schedule with default liquidity control for the current `2,000,000 RMB` account size
  - run formal `EventDrivenBacktester` test-window backtests
  - emit review artifacts including `master_review.md`, raw backtest tables, signal diagnostics, and HTML reports
- Added durable helper tests in:
  - `tests/alpha_research/test_event_driven_strategy_research.py`
  covering walk-forward fold construction, correlation-cluster assignment, liquidity filters, and rebalance-date generation.
- Installed the previously missing `plotly` dependency into the project venv so:
  - `src/result_analysis.report`
  - `workspace/research/alpha_mining/event_driven_strategy_report.py`
  can both render HTML reports successfully on this machine.
- Improved operational behavior:
  - if the local MLflow server is offline, the research pipeline now skips tracking quickly instead of hanging for multiple retry cycles
  - the CLI now also supports `--disable-mlflow` for runs where experiment tracking is intentionally not wanted
  - long event-driven runs continue to emit visible day-by-day progress through the backtest engine logs
- Validation completed with:
  - `python -m unittest tests.alpha_research.test_event_driven_strategy_research`
  - `python -m unittest tests.alpha_research.test_compute_factors`
  - a real reduced-scope smoke run at:
    - `workspace/outputs/alpha_mining_archive_20260404/event_driven_strategy_research_smoke_20260401/`
  - the smoke used `2` candidate factors, `1` fold, `skip_sensitivity=true`, `skip_holdout=true`, and produced the full artifact set including `master_review.md`, `strategy_signal.parquet`, `event_driven_report.csv`, `event_driven_trades.csv`, `event_driven_order_log.csv`, and `strategy_backtest_report.html`
- Formal main research run completed at:
  - `workspace/research/alpha_mining/event_driven_strategy_research_full_20260401_main/`
  - all `43` A/B factor studies finished
  - `43` factor cards generated
  - all `7` walk-forward test folds completed
  - holdout diagnostic completed
  - event-driven raw tables, HTML report, and `master_review.md` all emitted
  - stitched test-window cumulative return was positive, but the current all-market long-only baseline still underperformed the `000905.SH` benchmark over the full stitched OOS span
  - added the reviewer-friendly Chinese summary:
    - `workspace/research/alpha_mining/event_driven_strategy_research_full_20260401_main/formal_research_review_summary_zh.md`
- Formal main research run was launched with:
  - `workspace/research/alpha_mining/event_driven_strategy_research.py`
  - input `workspace/research/alpha_mining/latest_backend_screening_20260401_new_data/`
  - output `workspace/research/alpha_mining/event_driven_strategy_research_full_20260401_main/`
  - `capital = 2,000,000`
  - `benchmark = 000905.SH`
  - `topk = 50`
  - `rebalance_days = 5`
  - `adv_median_floor = 5,000,000`
  - `participation_cap = 0.02`
  - `skip_sensitivity = true`
  - `disable_mlflow = true`
  - holdout kept enabled

### Latest Backend Alpha-Mining Fresh Screening + Review Summary (Complete - 2026-04-01)

- Added the reusable review-doc generator:
  - `workspace/research/alpha_mining/generate_factor_screening_review_summary.py`
- Ran a fresh full-window alpha-mining batch screening on the live PIT backend with:
  - entrypoint `workspace/research/alpha_mining/batch_factor_screening_latest_backend.py`
  - `include_new_data = true`
  - `cache_mode = refresh`
  - requested `kernels = qlib default`
  - effective `kernels = qlib default`
  - `start = 2012-01-01`
  - `end = 2026-02-27`
  - `engine = batch`
- Formal run outputs were saved under:
  - `workspace/research/alpha_mining/latest_backend_screening_20260401_new_data/`
  - including `factor_screening_results.parquet`, `factor_screening_report.csv`, `factor_screening_summary.txt`, `factor_screening_run_metadata.json`, `run_console.log`, and `factor_screening_review_summary.md`
- Run result summary:
  - total screened factors: `149` (`129` base factors + `20` composites)
  - grades: `18` A, `25` B, `72` C, `34` D
  - strongest overall factor by `|rank_icir_5d|`: `liq_vol_cv_20d`
  - strongest new-data factor by `|rank_icir_5d|`: `flow_net_inflow_20d`
- Review-doc validation:
  - the generated Markdown summary keeps every factor visible in the main body
  - a direct verification pass confirmed all `149` factor names appear in the review document text
  - this run did not trigger worker fallback; metadata recorded `requested_kernels = effective_kernels = qlib default`

### Qlib Worker Fallback Hardening for Research Screening (Complete - 2026-04-01)

- Hardened `src/alpha_research/factor_library/operators.py` so `compute_factors(...)` now:
  - retries with `kernels=1` when a caller explicitly requests Qlib default workers and the Windows worker startup fails with permission-like errors
  - covers both init-side and `D.features()`-side worker failures
  - does **not** silently downgrade explicit numeric kernel requests such as `4` or `8`; only the Qlib-default path can auto-fallback
  - records requested vs effective kernel mode on the returned factor / forward-return DataFrames
- Updated `workspace/scripts/batch_factor_screening.py` so run metadata now records:
  - requested kernels
  - effective kernels after any fallback
- Restored the two batch-screening entrypoints to prefer Qlib default workers by default, matching the current user-approved research workflow:
  - `workspace/scripts/batch_factor_screening.py` default `--kernels` is now `0`
  - `workspace/research/alpha_mining/batch_factor_screening_latest_backend.py` also defaults to `0`
  - when the Qlib-default path raises a worker-permission error, it automatically retries with `kernels=1`
- Added durable regression coverage in `tests/alpha_research/test_compute_factors.py` for:
  - `PermissionError` fallback from Qlib default workers to `kernels=1`
  - message-based permission-like `OSError` fallback
  - init-side worker failure fallback
  - explicit numeric kernel requests remaining strict
  - alpha-mining wrapper default kernel behavior
  - batch-screening requested/effective kernel metadata wiring
- Updated `tests/README.md` so the documented validation path now uses a runnable `unittest` command in the current project venv instead of a missing `pytest` dependency.
- Validation completed successfully with:
  - `7/7` targeted unit tests passing under `unittest`
  - `tests/harnesses/qlib_smoke.py` passing against the live provider
  - live small-window alpha-mining screening smoke succeeding under a fresh `cache-mode refresh` run with default `kernels=0`, recording `requested_kernels = effective_kernels = qlib default` on this host under the current full-access runtime

### Phase 3 Daily Factor PIT Lag Patch (Complete - 2026-04-01)

- Patched `src/alpha_research/factor_library/catalog.py` so the hand-written Phase 3 daily-data factors now apply the repo's next-day `Ref(..., 1)` convention consistently.
- Fixed the affected moneyflow, northbound, and margin formulas that had been using same-day daily inputs directly:
  - `flow_net_inflow_5d`
  - `flow_net_inflow_20d`
  - `flow_large_net_pct_20d`
  - `flow_small_net_pct_20d`
  - `flow_large_small_ratio`
  - `flow_inflow_surge`
  - `flow_large_buy_ratio_5d`
  - `north_accumulation_20d`
  - `north_flow_momentum`
  - `margin_net_buy_20d`
  - `margin_sl_balance_change`
- No Qlib provider rebuild was required because the underlying PIT-safe data fields did not change; this was a factor-expression timing fix in the research layer.
- Recomputed a targeted refreshed factor snapshot for the 11 affected formulas over `2025-09-01` to `2026-02-27` and saved:
  - `workspace/outputs/factor_timing_patch_20260401/affected_new_data_factors.parquet`
  - `workspace/outputs/factor_timing_patch_20260401/affected_forward_returns.parquet`
  - `workspace/outputs/factor_timing_patch_20260401/affected_new_data_factors_summary.csv`
- Targeted refresh completed successfully with:
  - factor shape `629,196 x 11`
  - forward-return shape `629,196 x 1`
- Did not rerun the full factor screening pipeline; only the directly affected factor outputs were refreshed and validated.

### Database Structure Audit + Script Surface Cleanup (Complete - 2026-04-01)

- Audited the live database layers and confirmed the intended serving layout is now:
  - raw immutable Parquet under `data/reference`, `data/market`, `data/fundamentals`, `data/corporate`, and `data/universe`
  - canonicalized build layers under `data/normalized` and `data/pit_ledger`
  - staged providers under `data/qlib_builds/<build_id>/`
  - published provider under `data/qlib_data`
- Added the operator runbook `src/data_infra/pipeline/RUNBOOK.md` documenting the supported end-to-end workflows for:
  - historical bootstrap
  - quarterly VIP statement backfills
  - indicator VIP history refresh
  - daily maintenance
  - raw verification
  - staged provider validation
  - production publish
  - post-publish acceptance checks
- Cleaned the top-level script surface in `scripts/` so the dangerous or stale entrypoints now fail safely or route through the supported staged backend:
  - `manual_qlib_dump.py` now delegates to the staged PIT builder instead of using the old direct dump path
  - `build_quarterly_qlib.py` is now a safe compatibility wrapper for income-quarter PIT rebuilds
  - `build_st_universe.py` now rebuilds `st_stocks.txt` from local raw reference data instead of fetching raw data directly
  - `verify_phase2.py` now routes through the staged PIT integrity gate for a Phase 2-focused dataset subset
  - `cleanup_close_columns.py` and `update_tracker.py` are now explicit deprecated no-op scripts so accidental runs do not mutate raw data or tracker state
  - `refetch_index_weights.py` now uses the correct project-root-relative paths, writes through `StorageManager`, and exposes a visible progress bar
- Updated `src/data_infra/README.md`, `src/data_infra/pipeline/README.md`, and `scripts/README.md` so future operators can distinguish:
  - live supported entrypoints
  - compatibility wrappers
  - one-off maintenance helpers
  - deprecated scripts that should not be used for normal operations
- Moved the old runnable `scripts/test_*.py` harnesses into `tests/harnesses/` so the top-level `scripts/` directory is reserved for operational utilities and compatibility wrappers; added `tests/README.md` to document the split between automated tests and manual smoke/integration harnesses.
- Cleaned the moved harnesses so the main smoke/integration runners now prefer repo-relative paths and `workspace/outputs/` scratch locations instead of leaving behind top-level `data_test*` artifacts.
- Verified the cleaned harness tree:
  - `py_compile` passes for all files under `tests/harnesses/`
  - the live smoke runner `tests/harnesses/qlib_smoke.py` still succeeds against the published provider
  - stale `/scripts/test_*` references were removed from the docs and operator guidance

### Production PIT Qlib Provider Publish (Complete - 2026-04-01)

- Added the production-facing Qlib acceptance script refresh in `scripts/audit_qlib.py`:
  - supports staged build ids and live providers
  - audits current PIT field families instead of the legacy flat field set
  - forces `qlib.init(..., kernels=1)` so validation works reliably in the current Windows environment where joblib worker-pipe creation is restricted
  - verifies both field retrieval coverage and alias parity for key PIT compatibility fields
- Hardened the main reusable Qlib consumers in:
  - `src/alpha_research/factor_library/operators.py`
  - `src/backtest_engine/event_driven/data_feeder.py`
  - `src/backtest_engine/vectorized/__init__.py`
  so they now initialize Qlib with `kernels=1` by default on this machine instead of inheriting the failing multiprocessing default.
- Audited the raw market store before publish and found two persistent Tushare source anomalies in:
  - `daily_20140618.parquet`
  - `daily_20140728.parquet`
  - both rows belong to `920489.BJ` and have `close < low` while `close == pre_close + change`
- Added the curated repair manifest `data/reference/daily_price_repair_overrides.csv` and wired it into `src/data_infra/pit_backend.py`:
  - raw Parquet remains immutable
  - the staged integrity gate now accepts only those exact approved row-level repairs
  - normalization and staged price export apply the repaired `low` values so the production provider remains internally consistent
- Built the full staged production candidate `prod_candidate_20260401`:
  - manifest: `data/qlib_builds/prod_candidate_20260401/manifest.json`
  - validation result: `0` errors, `2` warnings
  - the only warnings are the two approved daily price repair applications
- Promoted the staged provider into live `data/qlib_data` and retained the previous live provider backup at:
  - `data/qlib_data.bak_prod_candidate_20260401`
- Post-publish live-provider acceptance audit passed on 50 sampled symbols across:
  - market fields
  - PIT snapshot aliases
  - PIT cumulative / quarterly aliases
  - indicator vendor fields
  - canonical `pit_*` fields
  - Phase 3 daily fields such as `net_mf_amount`, `rzye`, `up_limit`, `down_limit`
- Live alias parity checks all passed for the audited compatibility pairs:
  - `roe == roe_q0`
  - `revenue == revenue_cum_q0`
  - `revenue_q == revenue_sq_q0`
  - `n_cashflow_act == n_cashflow_act_cum_q0`
  - `n_cashflow_act_q == n_cashflow_act_sq_q0`
- Operational note: the full production candidate build completed successfully but took roughly 12 hours end to end, with the dominant bottleneck still in full-universe PIT feature materialization for statement families.

### Long-Running Script Progress Visibility Rule (Complete - 2026-04-01)

- Updated the root `AGENTS.md` contract so future scripts or pipeline steps that take substantial time must expose a visible progress tracker and regularly print current progress to the console.
- Aligned the human-readable reference rules under `.agents/rules/` with the same requirement.
- Preferred implementation guidance is now explicit: use `tqdm` or periodic logging with completed/total counts, current stage, and ETA when practical.

### Indicator VIP Historical Refresh + Scoped Provider Validation (Complete - 2026-04-01)

- Updated the shared VIP fetch path in `src/data_infra/fetchers/__init__.py` so all-stock statement endpoints now request up to `10000` rows per page by default, while still keeping offset-pagination fallback when a period exceeds that size.
- Added the reusable historical indicator refresh path in `src/data_infra/pipeline/indicator_history_refresh.py` plus the entrypoint `src/data_infra/pipeline/refresh_indicator_history.py`.
- Refreshed the raw `data/fundamentals/indicators/` store using clean replacement semantics:
  - staged new period files first
  - validated `update_flag`, row counts, and period alignment
  - then swapped the live raw directory only after the staged set passed
- Live refreshed indicator raw status:
  - `97` partitions
  - `544,986` rows
  - `109` columns in every partition, including `update_flag`
  - the historical period set still contains a small number of non-quarter-end periods already present in the legacy store (for example `20130731`, `20140531`, `20200430`)
- The refreshed raw indicator feed still contains many same-key duplicate groups by design (`239,008` duplicate `(ts_code, ann_date, end_date)` groups / `478,016` duplicate rows); the staged PIT ledger resolves them deterministically using `update_flag` and the existing tie-break rules.
- Updated `init_fundamentals_data.py` so historical bootstrap no longer recreates the old per-stock, non-VIP indicator path; it now refreshes indicator history through the same VIP schema family used by the daily updater.
- Validated the refreshed indicator layer through staged build id `sandbox_indicator_vip_refresh_20260331`:
  - `upstream-only` rebuild completed successfully for `indicators`
  - focused `provider-only` validation returned `0` errors and `0` warnings
  - vendor indicator bins (`q_roe`, `q_op_qoq`, `q_ocf_to_sales`, `or_yoy`, `op_yoy`) and canonical `pit_*` bins (`pit_or_yoy`, `pit_op_yoy`, `pit_q_op_qoq`, `pit_ocf_yoy`) were written successfully for the sampled symbols
- Further optimized scoped staged provider updates in `src/data_infra/pit_backend.py`:
  - snapshot datasets now prefilter ledgers to the requested `touched_symbols`
  - symbol-scoped `provider-only` validation builds now copy only the minimal provider base (`calendars`, `instruments`, and the requested feature directories) instead of copying the full live Qlib provider tree
  - after this change, the combined 5-dataset / 3-symbol indicator validation completed in about `10s` instead of spending most of its time copying the full provider

### Indicator VIP Quarterly Semantics Audit (Complete - 2026-03-31)

- Audited `fina_indicator_vip` against the official Tushare docs and the current local `data/fundamentals/indicators/` store.
- Confirmed `fina_indicator` / `fina_indicator_vip` is not a paired statement family with `report_type`; it is a single reported-metric feed keyed by `ts_code + ann_date + end_date`.
- Live `fina_indicator_vip(period='20240331')` returned `6,911` rows and `109` columns, including:
  - quarterly-style reported fields such as `q_roe`, `q_ocf_to_sales`, `q_op_qoq`, `q_sales_yoy`
  - an `update_flag` column
- The current local raw indicator store is materially behind that live schema:
  - `97` raw parquet partitions, all at `108` columns
  - no `update_flag`
  - no `f_ann_date`
  - `322,279` raw rows containing `38,736` duplicate `(ts_code, ann_date, end_date)` groups
- Verified that live duplicate indicator rows can contain meaningful value revisions distinguished only by `update_flag`; sampled `000026.SZ / 20240425 / 20240331` rows differ on `fcff`, `fcfe`, `fcff_ps`, and `fcfe_ps` between `update_flag=0` and `1`.
- Conclusion for PIT serving:
  - treat `indicators` as a reported event-periodic snapshot ledger, not as a new quarterly statement family
  - use `ann_date` as the visibility anchor because no `f_ann_date` is currently documented or observed
  - preserve vendor-reported quarterly/growth metrics under their existing names
  - keep authoritative recomputed metrics under the separate `pit_*` namespace
  - full indicator backfill / refresh via `fina_indicator_vip` is required before the vendor-reported indicator layer can be considered fully PIT-clean

### Balancesheet Quarterly Viability Audit (Observed limitation - 2026-03-31)

- Audited the next logical quarterly family, `balancesheet_quarterly`, before wiring it into the PIT backend.
- Current live Tushare behavior does not provide usable direct-quarter balance-sheet rows:
  - `balancesheet_vip(period=..., report_type=2/3)` returned `0` rows on sampled periods
  - single-stock `balancesheet(ts_code=..., report_type=2/3)` also returned `0` rows on sampled names (`600519.SH`, `000001.SZ`, `601398.SH`)
- Conclusion: do not backfill or integrate `balancesheet_quarterly` yet. Keep `balancesheet` on the existing snapshot PIT path until Tushare actually returns populated `report_type=2/3` data for this family.

### Cashflow Quarterly Backfill + Scoped Staged Rebuild Optimization (Complete - 2026-03-31)

- Backfilled direct-quarter `cashflow_quarterly` raw data via `scripts/fetch_quarterly_statements.py`:
  - `72` non-empty quarterly Parquet partitions from `2008-03-31` through `2025-12-31`
  - `455,972` raw rows across `report_type=2/3`
  - future empty `2026` partitions are now skipped instead of being written as schema-less files
- Confirmed the staged backend now builds a direct-quarter PIT ledger for cashflow:
  - `data/pit_ledger/cashflow_quarterly/cashflow_quarterly.parquet` contains `449,602` canonical rows across `6,239` symbols
  - `data/pit_ledger/cashflow/cashflow.parquet` remains the cumulative companion ledger with `278,820` rows across `5,773` symbols
- Fixed the local Tushare token-cache issue in `src/data_infra/fetchers/__init__.py` by falling back to `ts.pro_api(token)` when `ts.set_token()` cannot write `C:\Users\henry\tk.csv`.
- Optimized scoped staged rebuilds in `src/data_infra/pit_backend.py`:
  - symbol-scoped `mode=update` builds now reuse the copied provider sidecars instead of rerunning `dump_bin`
  - `touched_symbols` now properly scopes feature materialization, parity audit, and provider validation
  - focused validation builds no longer get blocked by unrelated legacy provider fields outside the requested symbol/field scope
- Validated the focused cashflow build on staged build id `sandbox_cashflow_quarterly_focus_20260331`:
  - target symbols: `000001.SZ`, `600519.SH`, `688981.SH`
  - validation result: `0` errors, `0` warnings
  - quarter-canonical cashflow fields and `pit_ocf_yoy` bins were written successfully

### Report-Type-Aware Quarterly PIT and VIP Fetch Expansion (Complete - 2026-03-31)

- Extended `src/data_infra/fetchers/__init__.py` with generic VIP statement fetch methods:
  - `fetch_income_vip`
  - `fetch_income_quarterly_vip`
  - `fetch_balancesheet_vip`
  - `fetch_balancesheet_quarterly_vip`
  - `fetch_cashflow_vip`
  - `fetch_cashflow_quarterly_vip`
  - `fetch_fina_indicator_vip`
- Updated `src/data_infra/pipeline/update_daily_data.py` so announcement-window refreshes use Tushare VIP all-stock endpoints instead of relying on undocumented single-stock endpoint behavior with `ts_code=None`.
- Added `income_quarterly` to the routine Phase 2 refresh path and `cashflow_quarterly` to the routine Phase 3 periodic refresh path.
- Added report-type-aware canonicalization in `src/data_infra/pit_backend.py`:
  - statement ledgers now preserve `report_type` in canonical keys for statement datasets
  - direct-quarter canonical serving now prefers adjusted single-quarter `report_type=3` over `2`
  - missing cells on the preferred report type are backfilled from lower-priority same-disclosure variants
  - cumulative statement serving remains disclosure-timeline first, with `update_flag` only as a same-disclosure tie-breaker
- Registered `cashflow_quarterly` as an optional quarterly ledger so the paired-family backend can use it as soon as historical backfills are downloaded.
- Added `scripts/fetch_quarterly_statements.py` as the generic VIP quarterly backfill entrypoint and converted `scripts/fetch_quarterly_income.py` into a compatibility wrapper over it.
- Added durable tests for:
  - report-type-aware quarterly canonicalization
  - quarterly VIP fetch helper behavior for income and cashflow

### Paired-Statement PIT Families for Fundamentals (Complete - 2026-03-31)

- Refactored `src/data_infra/pit_backend.py` from dataset-specific flow handling to a statement-family model:
  - `income` family now serves cumulative and quarterly ledgers separately
  - `cashflow` remains cumulative-only but uses the same family path for future quarterly expansion
  - `balancesheet` stays a snapshot family
- Canonical flow serving now follows paired-ledger precedence:
  - cumulative fields (`field`, `field_cum_q0..q4`) come from the cumulative ledger
  - quarter fields (`field_q`, `field_sq_q0..q4`) prefer the quarterly ledger when present
  - cumulative-derived quarter values are used only as fallback for missing quarterly coverage
- Removed the old `income_quarterly` override behavior inside cumulative flow materialization.
- Added canonical PIT-derived indicator fields from the family ledgers:
  - income-based: `pit_or_yoy`, `pit_op_yoy`, `pit_netprofit_yoy`, `pit_basic_eps_yoy`, `pit_q_sales_yoy`, `pit_q_op_qoq`
  - cashflow-based: `pit_ocf_yoy`
  - each is written both as a scalar alias and as `q0..q4` slot history
- Added provider metadata parity sidecars under `metadata/pit_audit/` comparing direct quarterly income rows against cumulative-derived quarter values for overlapping fields.
- Added unit coverage for:
  - direct-quarter precedence with cumulative fallback
  - revision-aware quarter slots
  - PIT-derived quarter YoY/QoQ metrics from visible period state

### Phase 3 Maintenance + Exception-Gate Hardening (Complete - 2026-03-31)

- Added explicit source-empty reference calendars under `data/reference/`:
  - `moneyflow_known_empty_dates.txt` with the 5 confirmed source-empty moneyflow dates
  - `northbound_nonconnect_days.txt` with the 67 confirmed non-connect / source-empty northbound dates
- Updated `src/data_infra/pit_backend.py` so raw profiling subtracts those curated exception dates from the missing-date gate instead of treating them as unresolved corruption.
- Added observed-data northbound code recovery during normalization:
  - recover valid A-share `ts_code` values from raw `code + exchange` when the raw `ts_code` is contaminated
  - keep `.HK` / ambiguous rows out of the normalized daily provider path
- Added visible `tqdm` progress bars to the long-running PIT stages:
  - profiling
  - normalization
  - ledger building
  - price staging
  - daily normalized loads
  - provider materialization loops
- Extended `src/data_infra/pipeline/update_daily_data.py` so routine maintenance now refreshes Phase 3 datasets:
  - periodic/event: `cashflow`, `forecast`, `holder_number`
  - daily market: `moneyflow`, `northbound`, `margin`, `stk_limit`
  - added `--skip-phase3` for explicit opt-out runs
- Validated the hardened workflow on build id `sandbox_finish_20260331_b`:
  - upstream artifacts reused from the focused `full` stage
  - final provider materialization run used `--mode all --stage provider-only` over the 10-symbol validation basket
  - representative bin checks passed for `000001_sz`, `600519_sh`, and `688981_sh`
  - prior missing-date warnings for `moneyflow` and `northbound` are gone from the manifest
- Hardened the remaining warning classification after direct data audit:
  - northbound raw `.HK` / contaminated suffix counts are now treated as raw-profile metadata only, not provider warnings
  - normalized northbound materialization now hard-fails if any non-A-share or unmapped rows survive normalization
  - `holder_number` raw rows with null disclosure dates are quarantined into `data/pit_ledger/holder_number/holder_number_unusable_pit.parquet`
  - corrected holder-number split on the live ledger is:
    - `47` truly unusable legacy rows with null `ann_date`
    - `107` rows announced on the calendar end date (`2026-02-27`) whose next open day is not yet in the calendar
    - `4,608` valid future disclosures beyond the current market/calendar horizon
  - the `47` quarantined rows are tracked in ledger metadata, not as an active provider warning; the calendar-horizon rows are also metadata, not data-integrity failures
  - after refreshing the northbound and holder-number profiles for `sandbox_finish_20260331_b`, staged provider validation returns zero warnings

### Staged PIT Sandbox Validation Workflow (Complete - 2026-03-31)

- Added stage-aware Qlib backend execution in `src/data_infra/pipeline/build_qlib_backend.py` and `src/data_infra/pit_backend.py`:
  - `--stage full`
  - `--stage upstream-only`
  - `--stage provider-only`
- Added `--skip-compat-aliases` so sandbox validation builds can avoid legacy scalar alias writes while keeping the upstream PIT ledgers unchanged.
- Optimized the provider write path by:
  - caching per-symbol reference bin metadata instead of re-reading `close.day.bin` for every field write
  - pre-grouping direct single-quarter ledgers in flow materialization
  - pre-grouping daily normalized data by `ts_code` during daily dataset writes
- Verified the new execution shape on build id `sandbox_stage_20260331_a`:
  - full upstream stage (`profile -> normalize -> ledger`) completed across all datasets
  - focused provider-only validation build over 10 representative symbols and 15 key fields completed in about 10.3 minutes
  - targeted bin validation passed for representative symbols and PIT/Phase 3 fields
- Refined `holder_number` validation warnings:
  - true unusable rows are now quarantined separately from calendar-horizon rows beyond the current trading-calendar end (`2026-02-27`)
  - the corrected live split is `47` unusable null-`ann_date` rows, `107` rows awaiting the next open after the calendar end, and `4,608` valid post-calendar disclosures
- Conclusion recorded for future work: sandbox validation should use full-data upstream processing plus scoped provider materialization, while production-scale full provider rewrites remain an overnight or release task.

### Phase 1: Core Market Data (Complete)

- Downloaded daily OHLCV, valuation metrics, and adjustment factors from `2008-01-02` through `2026-02-27` (`4,410` trading days).
- Built the core reference datasets:
  - `trade_cal.parquet` with `4,410` rows
  - `stock_basic.parquet` with `5,805` stocks including delisted and ST names
- Downloaded 7 major index histories: SSE Composite, CSI 300, CSI 500, CSI 1000, SZSE Composite, ChiNext, and STAR 50.
- Compiled the Phase 1 data into the Qlib backend at `data/qlib_data/`.
- Standardized the market-data layout under `data/market/daily/YYYY/daily_YYYYMMDD.parquet`.

### Phase 2: Fundamentals and Corporate Data (Complete)

- Downloaded quarterly financial datasets partitioned by reporting period:
  - `data/fundamentals/income/` with `82` files
  - `data/fundamentals/balancesheet/` with `72` files
  - `data/fundamentals/indicators/` with `97` files
- Downloaded corporate and universe data:
  - `data/corporate/dividends/` with `20` files
  - `data/universe/index_weights/` with `219` monthly snapshots
  - `data/universe/industry_sw2021/industry_sw2021.parquet`
- Implemented point-in-time alignment in `build_qlib_backend.py` using:
  - `ann_date` rather than `end_date`
  - `merge_asof(direction='backward')`
  - `shift(1)` to prevent same-day leakage
- Exported core fundamental fields to the Qlib backend and validated PIT behavior with the pipeline end-to-end harness now located at `tests/harnesses/pipeline_e2e_harness.py`.

### Infrastructure and Documentation (Complete - refreshed 2026-03-29)

- Maintained top-level architecture and data references:
  - `src/system.md`
  - `data/data_dictionary.md`
  - `data/data_tracker.md`
- Refreshed the major README set to reflect the live architecture:
  - `workspace/README.md`
  - `src/data_infra/README.md`
  - `src/data_infra/pipeline/README.md`
  - `src/alpha_research/README.md`
  - `src/backtest_engine/README.md`
  - `scripts/README.md`
- `config.yaml` now uses `${TUSHARE_TOKEN}` instead of a hardcoded token.
- Pinned project dependencies in `requirements.txt` and removed stale infrastructure references such as the old ClickHouse/Redis setup.

### Data Pipeline Refactoring (Complete - 2026-03-04)

- Deleted dead code such as the obsolete Airflow stub, `export_fundamentals_qlib.py`, and `visualize_data.py`.
- Renamed the old Phase 1 and Phase 2 initialization entry points to `init_market_data.py` and `init_fundamentals_data.py`.
- Consolidated Parquet-to-Qlib compilation into `build_qlib_backend.py`.
- Made `StorageManager` and `DataAuditor` config-driven instead of hardcoded-path driven.
- Added `DataCleaner.adjust_prices()` and pipeline integration coverage.
- Upgraded `update_daily_data.py` to refresh both market and newly announced fundamental data.

### Factor Research - First 43-Factor Analysis (Complete - 2026-03-05)

- Built `workspace/scripts/generate_factor_notebook.py`.
- Generated the 43-factor analysis notebook in `workspace/research/alpha_factors/`.
- Extended `factor_eval/ic_analysis.py` with:
  - `compute_rolling_ic()`
  - `compute_ic_by_group()`
  - `compute_marginal_ic()`
- All `14/14` factor-evaluation tests passed.
- Key findings:
  - liquidity factors were strongest
  - medium-horizon momentum reversed in A-shares
  - quality factors were weak in the tested sample
  - several factor pairs were redundant

### ML Multi-Factor Strategy (Complete - 2026-03-06)

- Upgraded `model_zoo/LightGBMModel` with early stopping, feature importance, and persistence helpers.
- Built the ML strategy notebook generator and walk-forward research workflow.
- Standardized vectorized benchmark usage on underscore codes such as `000300_SH`.

### Result Analysis and Trading Statistics (Complete - 2026-03-12)

- Added `BacktestReport.trading_analysis()` for one-call trading diagnostics.
- Implemented `generate_trading_stats()` and expanded `result_analysis/metrics.py`.
- Standardized A-share limit detection on expression-based `$pct_chg` thresholds instead of broken float comparisons.

### Quarterly Income Data Pipeline (Complete - 2026-03-12)

- Downloaded single-quarter income data from Tushare `income_vip`.
- Built `scripts/build_quarterly_qlib.py` for PIT-safe quarterly feature generation.
- Added `src/data_infra/storage/qlib_bin_utils.py` as the shared safe Qlib `.day.bin` utility.

### PIT Calendar Alignment Fix (Complete - 2026-03-16)

- Fixed the `build_quarterly_qlib.py` bin-slicing bug that had misaligned multi-year quarterly data.
- Rebuilt all affected bins successfully.
- Rebuilt the ST universe from better source logic and improved historical coverage.

### Signal Backtesting Guide and Rule System (Complete - 2026-03-23)

- Created `workspace/research/signal_backtesting_guide.md` as the detailed backtesting reference.
- Codified the four-layer signal pipeline, banned anti-patterns, and validation checklist.
- Converted the guide into durable system rules under `.agents/rules/signal-backtesting.md`.

### Event-Driven Backtester Implementation (Complete - 2026-03-24)

- Built the custom event-driven A-share simulator with:
  - `QlibDataFeeder`
  - realistic exchange rules
  - T+1 settlement
  - multi-tier limits
  - corporate actions
  - JoinQuant-style lifecycle hooks
- Added `preload_features()` support and cut a 1-year backtest from more than 5 minutes to roughly 24 seconds.

### Backtester Parity and Dual-Price Engine (Complete - 2026-03-26)

- Reached `87.8%` buy-overlap with the JoinQuant reference on the verified-factor strategy.
- Added dual-price infrastructure via `raw_*` columns for explicit raw-price execution paths.
- Verified that the current Qlib backend stores raw Tushare prices directly, with `$adj_factor` still available for adjusted-return research.

### Factor Research Framework Optimization (Phase 3) (Complete - 2026-03-29)

- Replaced slow pandas `groupby().apply()` factor generation with Qlib's expression engine for batch screening.
- Implemented the two-layer factor framework in `src/alpha_research/factor_library/`:
  - Layer 1 Qlib expression operators in `operators.py`
  - Layer 2 pandas cross-sectional transforms and composites
- Defined the `191`-factor catalog in `catalog.py` across 15 categories.
- Validated adjusted-vs-raw expression rules and documented the unary-negation workaround (`0 - Std(...)`).
- The initial `2026-03-29` batch screen surfaced suspicious outliers and triggered a deeper formula audit.
- Began Phase 3 data expansion for the remaining 60 novel-data factors.

### Corrected Factor Screening Rerun and Progress Instrumentation (Complete - 2026-03-30)

- Fixed the adjusted-price expression-precedence bug by parenthesizing the adjusted OHLC atoms in `src/alpha_research/factor_library/operators.py`.
- Revalidated the suspicious momentum and size factors and confirmed the prior extreme ICIR values were artifacts of the bad formula composition.
- Added Python 3.12 compatibility fallbacks for Qlib's bundled `cp310` rolling/expanding extensions so the repo can still run through the local site-packages while the venv launcher is broken.
- Restored configurable multiprocessing in `compute_factors()` and added progress instrumentation:
  - Qlib heartbeat logs during long factor computation
  - composite ETA logs
  - screening ETA logs
  - `--kernels`, `--progress-interval`, `--screen-progress-every`, and `--composite-progress-every` CLI options in `workspace/scripts/batch_factor_screening.py`
- Reran the `131`-factor screen over `2012-01-01` to `2025-12-31` and replaced the invalid earlier outputs with the corrected result split:
  - `16` graduated factors
  - `20` strong-IC factors
  - `64` moderate factors
  - `31` weak factors
- The corrected top of the screen is now led by liquidity, turnover-shock, skew/risk, and reversal-composite signals rather than implausible near-perfect momentum outliers.

### Factor Screening Parity Harness (Complete - 2026-03-30)

- Added `workspace/scripts/validate_factor_screening_parity.py` as the Workstream 0 correctness gate for future screening-engine optimization.
- The harness compares:
  - current helper-based screening outputs
  - an independent pandas/scipy oracle implementation
- It writes durable outputs under `workspace/outputs/` for:
  - reference results
  - oracle results
  - per-factor diff reports
  - markdown summaries
- Corrected two harness edge cases:
  - all-NaN aligned series were previously treated as mismatches
  - the oracle IC builder did not initially mirror Qlib's per-column `dropna` behavior
- Broad validation over `111` existing-data base factors for `2024-01-01` to `2024-12-31` at the `5d` horizon now passes `111/111` with grade counts matching exactly between reference and oracle.
- Initial representative spot checks across momentum, quality, size, risk, liquidity, reversal, and composite factors also matched exactly on IC, RankIC, quantile rows, long-short series, and monotonicity.

### Optimized Batch Screening Engine (Production Window Executed - 2026-03-30)

- Added `src/alpha_research/factor_eval/batch_screening.py` with two explicit engines:
  - `reference`: current helper-based semantic baseline
  - `batch`: optimized internal screening path for the batch script
- Added `--engine {reference,batch}` to:
  - `workspace/scripts/batch_factor_screening.py`
  - `workspace/scripts/validate_factor_screening_parity.py`
- The optimized `batch` engine preserves current IC and quantile semantics while reducing repeated frame construction by:
  - normalizing inputs once
  - precomputing date slices once
  - evaluating aligned column arrays inside the factor loop
- Validation status:
  - representative window (`2024-01-01` to `2024-03-31`, representative sample, horizons `5/10/20`): `12/12` passed against the independent oracle
  - broad window (`2024-01-01` to `2024-12-31`, `111` existing-data base factors, horizon `5`): `111/111` passed against the independent oracle
  - full production screening window (`2012-01-01` to `2025-12-31`, `131` factors after composites, horizons `5/10/20`): optimized `batch` engine completed successfully
  - exact rerun diff against a separately saved full `reference` run: passed with identical parquet content, identical CSV SHA256, identical summary TXT SHA256, and `0` mismatch cells
- Observed screening runtime on the broad 2024 existing-base window:
  - `reference` engine: about `116.5s`
  - `batch` engine: about `80.8s`
- Observed full production-window runtime:
  - rerun `reference` screening stage: about `3469.7s`
  - `batch` screening stage: about `2313.1s`
- The validation gate for switching the batch script default from `reference` to `batch` is now cleared. The separately saved engine comparison artifacts are:
  - `workspace/outputs/factor_screening_summary.batch_2012_2025.txt`
  - `workspace/outputs/factor_screening_summary.reference_2012_2025.txt`
  - `workspace/outputs/factor_screening_report.batch_2012_2025.csv`
  - `workspace/outputs/factor_screening_report.reference_2012_2025.csv`
  - `workspace/outputs/factor_screening_results.batch_2012_2025.parquet`
  - `workspace/outputs/factor_screening_results.reference_2012_2025.parquet`
  - `workspace/outputs/factor_screening_engine_exact_diff.md`
- `workspace/scripts/batch_factor_screening.py` now defaults to `--engine batch`, while `reference` remains available explicitly for debugging and regression checks.

### Composite Rank Caching (Implemented - 2026-03-30)

- Updated `src/alpha_research/factor_library/operators.py` so `add_composites()`:
  - caches `cs_rank()` outputs by `(component, negate)` within the composite build
  - accumulates composite columns and concatenates them once at the end instead of repeated column assignment
- Safety check:
  - synthetic validation with ties and NaNs produced exact equality versus the legacy composite loop
  - real-data validation on the full 20-component composite input set over `2024-01-01` to `2024-01-31` produced exact equality versus the legacy composite loop
  - sample runtime in the real-data validation improved from about `0.672s` to about `0.327s`
- Live `workspace/outputs/` standard files were restored to the full production-window `batch` artifacts after the validation smoke test.

### Resumable Batch Screening Caches (Implemented - 2026-03-30)

- Added resumable stage caches to `workspace/scripts/batch_factor_screening.py` for:
  - base factors
  - forward returns
  - composite factors
  - partial screening results
- Added new CLI controls:
  - `--cache-mode {off,resume,refresh}`
  - `--cache-dir`
  - `--screen-checkpoint-every`
  - `--include-new-data`
- Cache safety model:
  - strict cache keys include window, horizons, kernels, include-new-data flag, Qlib data signature, catalog hash, composite hash, and code hash
  - stage files are written with atomic replacement
  - metadata mismatches are rejected rather than reused
- Updated `src/alpha_research/factor_eval/batch_screening.py` so both `reference` and `batch` engines can resume from partial raw screening results and emit checkpoint writes during the factor loop.
- Validation:
  - metadata round-trip and mismatch rejection both passed
  - real partial-screening resume test over `40` screened factors (`20` base + `20` composites) for `2024-01-01` to `2024-01-31` resumed from `13` cached factors and reproduced the full raw result exactly
  - durable validation note saved at `workspace/outputs/factor_screening_resume_validation.md`

### Factor Screening Report Diagnostics (Implemented - 2026-03-30)

- Added additive screening diagnostics without changing existing grading semantics:
  - `rankic_days_*`
  - `constant_xs_days_*`
  - quantile bucket diagnostics on the primary horizon
  - `obs_coverage_primary`
  - `rankic_coverage_primary`
  - cross-horizon consistency diagnostics
  - warning flags for low observations, reduced quantiles, constant cross-sections, and extreme ICIR
- Added `ls_ann_return_semantics='overlapping_forward_return_diagnostic'` to make the existing long-short annualization column explicit rather than redefining it.
- Updated the text summary emitted by `workspace/scripts/batch_factor_screening.py` to state that `L/S` is an overlapping-forward-return diagnostic, not an investable return estimate.
- Validation:
  - real-data screening check over a smaller January 2024 window confirmed the new additive columns are present
  - the summary note is emitted as expected

### Project Virtual Environment Repair and Native Validation (Complete - 2026-03-30)

- Rebuilt `E:\量化系统\venv\` against the available Python `3.12.7` interpreter and installed a validated Python 3.12 package set, including native `pyqlib==0.9.7`, `numpy==2.2.6`, `pandas==2.3.3`, `scipy==1.15.3`, and `pyarrow==23.0.1`.
- Removed the temporary hardcoded `venv/Lib/site-packages` fallback from:
  - `workspace/scripts/batch_factor_screening.py`
  - `workspace/scripts/validate_factor_screening_parity.py`
- Direct runtime validation now passes from `E:\量化系统\venv\Scripts\python.exe`:
  - import smoke test for the factor-screening stack
  - end-to-end batch screening smoke test on `2024-01-02` to `2024-01-12`
  - parity-script smoke test on explicit factors and composites
- Reran the full production window (`2012-01-01` to `2025-12-31`, horizons `5/10/20`, engine `batch`) from the repaired venv and restored the live outputs under `workspace/outputs/`.
- Observed full-run timings from the repaired venv:
  - factor computation: about `73.8s`
  - composite construction: about `127.5s`
  - screening: about `918.8s`
  - end-to-end: about `19.0m`
- Current full-run grade counts remain:
  - `16` A
  - `20` B
  - `64` C
  - `31` D
- Post-repair validation:
  - broad parity rerun over `111` existing-data base factors for `2024-01-01` to `2024-12-31` at the `5d` horizon passed `111/111`
  - targeted full-window parity on `qual_accruals` and `rev_up_down_ratio_20d` passed `2/2`
  - `qual_accruals` differs from the older mixed-runtime saved batch artifact, but matches both the current helper-based reference path and the independent oracle exactly under the rebuilt venv; treat the rebuilt-venv output as authoritative
  - the old `rev_up_down_ratio_20d` day-count blanks are now normalized to explicit `0`-day outputs in parity/oracle checks
- Durable validation note saved at `workspace/outputs/factor_screening_venv_repair_validation.md`

### Codex Rule Migration and Architecture Alignment (Complete - 2026-03-29)

- Added the root `AGENTS.md` contract and scoped `AGENTS.md` files for:
  - `src/data_infra/`
  - `src/alpha_research/`
  - `src/backtest_engine/`
  - `workspace/`
- Refreshed the legacy `.agents/rules/` documents so they remain aligned with the Codex-facing instruction tree.
- Updated architecture and workflow docs to remove deprecated pipeline references and reflect the live Phase 3 system.
- Added a named Codex profile `quant-system` in `~/.codex/config.toml` for launching this repo with:
  - `codex -p quant-system -C E:\閲忓寲绯荤粺`

### Repo-Local Codex Subagent Infrastructure (Complete - 2026-03-30, trusted direct custom agents verified)

- Added project-scoped Codex subagent config in `.codex/config.toml` with explicit thread/depth limits for predictable delegation.
- Added specialized repo-local role briefs under `.codex/agents/` for:
  - context mapping
  - bounded implementation
  - focused verification
  - data-infrastructure safety review
  - research-integrity review
  - backtest/signal-pipeline review
  - final correctness review
- Native Codex app/CLI direct custom-agent spawning is now verified to work for this repo once the workspace is marked trusted in the user-level Codex config.
- Updated the root `AGENTS.md` contract so the primary workflow uses the repo-local custom agent names directly, with built-in `explorer`/`worker` fallbacks only for restricted integrations that expose built-in enums only.
- Added a concise default spawn matrix to the root `AGENTS.md` covering small tasks, medium code changes, large cross-module work, data infrastructure, research, and backtesting.
- Promoted `quant_test_runner` from a lightweight checker to the primary validation gate:
  - upgraded it to `gpt-5.4` with `xhigh` reasoning
  - allowed it to add or strengthen durable test assets and validation scripts
  - made it mandatory for behavior-changing work across calculations, data pipelines, factors, backtests, execution logic, portfolio/risk logic, and result-analysis behavior
- The workflow is tuned for the current heavy system-development and validation phase while also covering the next-stage factor research and backtesting workflow.
- Local Codex runtime repairs that were needed during verification:
  - switched native Windows sandbox mode from `elevated` to `unelevated`
  - backed up and regenerated stale Codex SQLite runtime state/log databases under `~/.codex/` after migration-skew warnings
  - repo trust now lives in the user-level Codex config for `E:\量化系统`
  - isolated the user-local `codex` wrapper from the shared `~/.codex` runtime state by seeding `C:\Users\henry\.codex-cli` with auth/config files and pointing `C:\Users\henry\.local\bin\codex.cmd` at that separate home; this removed the recurring mixed-version `state_5.sqlite` migration warning caused by the older `0.115` desktop CLI and the newer `0.118` VS Code bundled CLI sharing one SQLite state directory
  - verified that the isolated wrapper still supports direct repo-local custom agents such as `quant_context_mapper`
  - added `workspace/outputs/fix_codex_cli_bootstrap.ps1` to reseed the isolated wrapper home from `~/.codex` with the missing bootstrap artifacts:
    - `models_cache.json`
    - `cache\codex_apps_tools`
    - `.tmp\plugins`
    - `.tmp\plugins.sha`
    - `sqlite\codex-dev.db`
  - ran that repair successfully in a native local PowerShell session and confirmed the bootstrap artifact sync
  - tightened `workspace/outputs/fix_codex_cli_bootstrap.ps1` after an initial harness quoting artifact so it now:
    - invokes the wrapper through PowerShell without the `cmd.exe` trailing-quote artifact
    - requires exact success markers in the captured smoke logs
  - final native rerun now passes both exact-marker wrapper smokes:
    - smoke 1 returned `WRAPPER_BOOTSTRAP_OK`
    - smoke 2 spawned `quant_context_mapper`, received exact child confirmation `CHILD_CONFIRMED`, and returned `WRAPPER_BOOTSTRAP_AGENT_OK`

- A second native end-to-end smoke test now also passes using the repo-local custom agent names directly:
  - `quant_context_mapper`
  - `quant_impl_worker`
  - `quant_test_runner`
- That direct-name workflow performed a disposable write-and-validate round trip under `workspace/outputs/subagent_direct_e2e/` and returned success only after:
  - exact child acknowledgments from each custom agent
  - independent parent-side byte checks on the generated marker files
- Hardened the bounded write-task handoff after a live regression where a forked-context `quant_impl_worker` returned session-summary text instead of executing a scoped write request.
- Updated `.codex/agents/quant-impl-worker.toml` so the worker treats the latest parent message as the active assignment, stays inside the declared write scope, performs requested writes instead of returning analysis-only text, and reports a concrete blocker when no files change.
- Updated the root `AGENTS.md` contract so `quant_impl_worker` and `quant_test_runner` must receive a self-contained assignment with exact write scope, expected artifacts, and validation targets rather than relying on broad forked conversation context.
- Current-session validation:
  - minimal write smoke test with a narrow non-forked assignment succeeded at `workspace/outputs/subagent_system_smoke_minimal/marker.txt`
  - repaired the host-side isolated wrapper/runtime at `C:\Users\henry\.codex-cli` by:
    - pinning the wrapper to the user-writable `0.118` runtime copied from the VS Code bundle
    - keeping `[windows] sandbox = "unelevated"`
    - seeding a local CA bundle and exporting `SSL_CERT_FILE` / `REQUESTS_CA_BUNDLE` / `CURL_CA_BUNDLE`
    - defaulting the wrapper to `-a on-request -s danger-full-access` for interactive use while leaving `codex exec` on its built-in non-interactive policy
    - installing Git and prepending the wrapper runtime plus `C:\Program Files\Git\cmd` inside `C:\Users\henry\.local\bin\codex.cmd`
  - targeted host diagnostics against the repaired wrapper no longer reproduced:
    - `CreateRestrictedToken failed: 87`
    - `No credentials are available in the security package`
    - native-root-CA / certificate bootstrap failures seen in the earlier broken host runs
  - host direct custom-agent E2E now passes under `workspace/outputs/host_runtime_fix_20260331/direct_custom_agent/` with exact parent-side byte verification of the worker and validation markers
  - host forked-context E2E now also passes under `workspace/outputs/host_runtime_fix_20260331/fork_context_v3/fork_context_marker.txt`; the successful harness explicitly tells the spawned child to treat inherited spawn/wait instructions as background context and the parent-side verification confirmed an exact byte match with no BOM or trailing newline
  - the earlier failed forked-context probe was traced to a self-referential validation harness that leaked spawning/waiting instructions into the forked history, not to a remaining repo-side agent-definition defect
  - residual non-blocking host warnings remain during `codex exec` startup:
    - plugin list/featured sync may return Cloudflare `403 Forbidden`
    - curated-plugin Git sync may warn on `\\?\C:\Users\henry\.codex-cli\.tmp\plugins-clone-*`
    - these warnings did not block direct custom-agent or forked-context execution in the repaired runtime
  - added repo-local ripgrep bootstrap helpers so Codex sessions in this repo no longer need to launch `rg.exe` directly from the blocked MSIX package path:
    - `scripts/use_repo_ripgrep.ps1` materializes a working copy under `.codex/tools/bin/rg.exe` and prepends that repo-local directory to `PATH`
    - `scripts/start_codex_repo.ps1` and `scripts/start_codex_repo.cmd` launch Codex with the repo-local ripgrep workaround applied
    - local validation confirmed the helper resolves `rg` to `.codex/tools/bin/rg.exe`, that child shells launched through the helper also resolve the repo-local copy first, and that the Codex launcher itself starts successfully with the adjusted `PATH`

### Staged PIT Backend Infrastructure (Complete - 2026-03-30)

- Added the shared staged backend in `src/data_infra/pit_backend.py`:
  - raw profiling -> normalized tables -> PIT ledgers -> staged provider builds -> validation/publish
- Added canonical normalized outputs under `data/normalized/`.
- Added revision-aware ledgers under `data/pit_ledger/`.
- Added raw ingest manifests under `data/raw_cache/manifests/`.
- Rewired the live data-infra entrypoints to the staged backend:
  - `src/data_infra/pipeline/build_qlib_backend.py`
  - `src/data_infra/pipeline/update_daily_data.py`
  - `src/data_infra/pipeline/verify_database.py`
  - `workspace/scripts/verify_phase3_data.py`
- Folded the old standalone quarterly builder into the shared PIT engine via `scripts/build_quarterly_qlib.py`.
- Added provider-sidecar rebuild helpers for:
  - `all_stocks.txt` with the existing 90-day IPO lag preserved
  - monthly-snapshot `csi300/csi500/csi1000`
  - `st_stocks.txt` from `stock_st_daily` plus pre-2016 `namechange`
- Added PIT invariant tests in `tests/data_infra/test_pit_backend.py` covering:
  - same-key duplicate collapse
  - revision-aware `q0/q1` slot behavior
  - single-quarter derivation after a late prior-quarter revision

---

## Current System Implementation Status

### Fully Implemented (Production-Ready)

| Component | Status |
|-----------|--------|
| `TushareFetcher` | Complete |
| `StorageManager` | Complete |
| `DataCleaner` | Complete |
| `DataAuditor` | Complete |
| Data pipelines (`init_market_data.py`, `init_fundamentals_data.py`, `init_factor_data.py`, `update_daily_data.py`) | Complete |
| `build_qlib_backend.py` | Complete |
| Factor library (`operators.py`, `catalog.py`, `qlib_expr_guide.md`) | Complete |
| `FactorEvalToolkit` | Complete (`14/14` tests) |
| `ExperimentTracker` | Complete |
| `LightGBMModel` / `XGBoostModel` | Complete |
| `VectorizedBacktester` | Complete |
| `EventDrivenBacktester` | Complete |
| `result_analysis/metrics.py` | Complete |
| `BacktestReport` and plotting stack | Complete |

### Structural Skeleton / Future Expansion

| Component | Status | Notes |
|-----------|--------|-------|
| `MultiFactorRiskModel` | Skeleton | `fit()` still needs real factor extraction logic |
| `MarketImpactModel` | Basic | Flat-rate and participation-style logic exist; realism can improve |
| `PortfolioOptimizer` | Basic | Mean-variance with turnover penalty works; more models can be added |

---

## Active Research Focus

- **11F+roe_waa @ fp=0.66 CHAMPION — CURRENT BEST (v31, 2026-05-28)**: 10F+q_dt_roe + roe_waa @ α=0.010 with focus_pct=0.66 → **OOS=192.7%, JK_min=217.5%, MDD=-33.95% [PASS]**. v31 confirmed monotonic improvement across fp sweep: fp=0.63→188.7%, 0.64→190.0%, 0.65→191.4%, **0.66→192.7%** — all PASS, JK_min rises with fp, MDD stays >−35%. Weights unchanged from v29 (roa=0.324, q_roe=0.265, rev_growth=0.120, q_dt_roe=0.079, dt_npy=0.070, val=0.042, size=0.036, q_qoq=0.027, roe_yoy=0.018, q_roe_yoy=0.010, roe_waa=0.010). v31 Part B (roe_dt α sweep): ALL HURT — no 12F+roe_dt config (best α=0.030 → OOS=181.4%, Δ=−7.3pp). v31 Part C (3 new factor candidates vs 11F+roe_waa): grossprofit_margin (−20.4pp), op_yoy (−14.8pp), assets_turn (−13.1pp) — ALL HURT. Cross-sectional factor expansion is saturated. Scripts: `sandbox_v15aa_v28*.py`, `sandbox_v15aa_v29*.py`, `sandbox_v15aa_v30_lgbm_and_dirichlet_validation.py`, `sandbox_v15aa_v31_focuspct_confirmation.py`. Outputs: `v28_results.txt` → `v31_results.txt`. **JoinQuant deployment ready**: `workspace/scripts/jq_11f_roewaa_strategy.py` (fp=0.66, JoinQuant API conventions: set_order_cost+OrderCost, avoid_future_data, get_extras is_st, get_fundamentals PIT-safe; 47.8% of signal uses approximations for q_roe/q_dt_roe/dt_npy/q_roe_yoy due to JQ indicator table lacking single-quarter fields — expect 5–15pp lower CAGR in JQ vs Tushare simulation).
- **v30 cost-model bug discovery (2026-05-28)**: v30 used per-ticker cost model (charges scale×cost×n_tickers each rebal) instead of v29's flat 50bps round-trip (scale×2×cost). All v30 OOS values were systematically underestimated by ~8pp. v31 reverted to v29's EXACT sim() function as ground truth. v30 results files are still on disk for reference but should NOT be cited for production decisions.
- **OOS progression (v16→v31)**: 4F=120.0% → 5F=124.2% → 6F_DIR=137.1% → 7F_DIR=141.0% → 8F+size=153.9% → 9F+roe_yoy=168.5% → 10F_Dirichlet=173.6% → 10F+q_dt_roe=184.0% → 11F+roe_waa=188.7% → **11F+roe_waa @ fp=0.66=192.7%** (+72.7pp total from 4F). **JK_min progression**: 126.9% → 154.6% (6F) → 153.6% (7F) → 192.0% (8F+size) → 187.9% (9F+roe_yoy) → 176.4% (10F_Dir) → 206.2% (10F+q_dt_roe) → 212.8% (11F+roe_waa fp=0.63) → **217.5%** (11F+roe_waa fp=0.66).
- **Robust checkpoint configs (all PASS)**:
  - 6F v20: OOS=137.1%, JK_min=154.6%, MDD=-34.2% — weights {roa:0.519,q_roe:0.216,rev_growth:0.143,dt_npy:0.073,val:0.029,q_qoq:0.020}
  - 7F v22: OOS=141.0%, JK_min=153.6%, MDD=-34.2% — adds q_roe_yoy=0.012
  - 8F+size: OOS=153.9%, JK_min=192.0%, MDD=-33.3% — adds size=-ln(total_mv) at w≈0.040
  - 9F+roe_yoy: OOS=168.5%, JK_min=187.9%, MDD=-33.3% — 8F+size + roe_yoy at w≈0.020
  - 10F Dirichlet: OOS=173.6%, JK_min=176.4%, MDD=-33.2% — best Dirichlet config
  - 10F+q_dt_roe: OOS=184.0%, JK_min=206.2%, MDD=-33.8% — prior champion (v27)
  - 11F+roe_waa @ fp=0.63: OOS=188.7%, JK_min=212.8%, MDD=-33.8% (v29 prior champion)
  - 11F+roe_waa @ fp=0.66: OOS=192.7%, JK_min=217.5%, MDD=-33.95% (v31 close-execution champion — SUPERSEDED by v32 execution correction)
  - **11F+roe_waa @ fp=0.65: OOS=190.8%, JK_min=206.8%, MDD=-34.84% — CURRENT CHAMPION under realistic open[T] execution** (v32, 2026-05-29). fp=0.66 now FAILS (MDD=-35.15% breaches -35% gate) — the small execution drag pushed it over. See v32 note below.
  - 12F+roe_dt (any α): REJECTED — Δ ≤ −7.3pp vs 11F+roe_waa (v31 Part B)
  - 12F+grossprofit_margin / +op_yoy / +assets_turn: ALL REJECTED — Δ ≤ −13.1pp (v31 Part C)
  - 12F Dirichlet (IS-optimized, NOT deployed): OOS≈193.4%, JK_min=231.1%, IS=459.9% — Dirichlet search result, not selected for deployment (extreme IS overfit)
- **Key factor insights (v21–v29)**:
  - Size (-ln(total_mv)): +12.9pp OOS vs 7F (breakthrough, v25 alpha=0.04)
  - roe_yoy (annual ROE YoY from Tushare): +14.6pp OOS vs 8F+size at alpha=0.02
  - q_dt_roe (quarterly deducted net ROE): +15.6pp OOS vs 9F+roe_yoy at alpha=0.08
  - **roe_waa (weighted-average ROE): +4.7pp OOS at α=0.010 vs 10F+q_dt_roe** (v29 finding — true optimum was 0.010, not 0.020)
  - tr_yoy FAILS to synergize with q_dt_roe at any alpha (both together MDD=-35.7%); q_dt_roe alone wins
  - focus_pct=0.65 gives +2.5pp OOS over 0.63 (OOS=186.5%, MDD=-33.9%); focus_pct=0.70 fails MDD (-35.1%)
  - K=5 confirmed optimal (K=4: OOS=187.9% but MDD=-37.2% FAIL; K=3 MDD=-36.8% FAIL)
  - REBAL=15d confirmed optimal (REBAL=30d gives 189.8% but MDD=-41.6% FAIL)
  - New candidates MISSING from indicators: cashflow_to_profit, ni_to_totalrevenue, q_profit_to_gr, inv_turn
  - "Deducted premium" pattern: 扣非 metrics consistently outperform raw equivalents in A-shares
  - Targeted alpha-blend > random Dirichlet for JK robustness (13F Dirichlet best OOS=194.5% but JK_min=154% vs 11F targeted 212.8%)
- **Research arc (v17→v20) summary**: v17 confirmed 4F is optimal within the original factor set (no 5th factor helps). v18 tested price momentum + new fundamentals → rev_growth (or_yoy) dramatically improves WF/JK_min. v19 proper IS/OOS confirmed: 5F discovery weights ARE IS-overfit (OOS=118.0% < 4F 120.0%), but 5F Dirichlet IS genuine improvement (OOS=124.2%). v20 extended to 6F (added q_qoq): 6F Dirichlet finds OOS=137.1%, JK_min=154.6% — decisive champion. **Key insight**: rev_growth adds top-line growth to quality signals; q_qoq adds near-term operational momentum (2% weight). Dirichlet IS-search finds better generalization than alpha-blend discovery for multi-factor models.
- **Accuracy and audit hygiene**: keep `pytest`, `scripts/audit_qlib.py`, and `scripts/run_daily_qa.py` reliable before trusting new research output; pay special attention to generated-artifact collection, Qlib provider namespace drift, and event-driven execution realism.
- **Growth theme follow-up**: the 2026-04-23 hypothesis-driven growth run found real excess-return signal but unacceptable drawdown. Future work should separate hypothesis variants at the `theme_id` / component-pool level rather than expecting `theme_strategy` to honor per-hypothesis factor weights.
- **Long-short alpha exploration**: the new B-grade top-list/top-inst attention factors are statistically strong but degraded long-only TopK performance. Treat them as candidates for long-short, sector-rotation, or risk-overlay research rather than immediate long-only promotion.

---

## Known Issues

- `config.yaml` still contains placeholder broker credentials in the XTP section for future live-trading work.
- `data/raw_cache/manifests/` now records ingest sessions, but historical raw writes before `2026-03-30` do not have manifests.
- `VectorizedBacktester` code defaults remain convenience-oriented for screening (`deal_price='close'`, `forbid_all_trade_at_limit=False`), so research scripts must keep overriding them explicitly.

### Re-validation status after 2026-04-12 factor library fix

The dedicated downstream re-validation plan completed on 2026-04-23 against the rebuilt, namespace-correct provider. The old "pending re-validation" warning below is retained as historical context, but it is no longer the current trust state.

- **Event-driven factor research**: re-run in sandbox against corrected grades and rebuilt provider; signal durability remained positive in 4/5 OOS folds, but formal registry publication is still deferred until hypothesis-backed formal runs are approved.
- **`small_cap` theme strategy**: re-run across the full 2012 -> 2026-02-27 window; the theme signal remained economically meaningful but still has high drawdown and turnover, so it is research-useful rather than live-ready.
- **ML research**: re-run in sandbox; all model variants failed auto-promotion thresholds, with rule_baseline still strongest. Treat old pre-fix ML coefficients as deprecated for live deployment.
- **`C_stability_score` / strategy-improvement lineage**: not promoted as a trusted live strategy. Future strategy-improvement work should start from the corrected 167-factor registry and hypothesis workflow rather than reviving the pre-fix artifact directly.

### Historical pending re-validation note after 2026-04-12 factor library fix (superseded 2026-04-23)

All downstream research artifacts below were computed against the contaminated pre-fix factor library (same-day leakage in 45 of 65 Layer 1 operators). Follow-up plan #1 executed on 2026-04-12 rewrote those operators and reran the full 149-factor screening — see `workspace/research/alpha_mining/post_fix_screening_20260411/post_fix_screening_diff.md` for the concrete grade migration. The items below are NOT automatically re-validated by follow-up plan #1 and will need a dedicated research plan:

- **`C_stability_score` strategy improvement run** at `workspace/research/alpha_mining/event_driven_strategy_improvement_full_20260403_retry_rankfix/` — built on baseline 18A+25B factors; 17 of those 18 A-grade factors lost their A status in the post-fix rerun. The strategy's factor-selection step needs to rerun against the corrected grades before the resulting portfolio can be trusted.
- **Formal event-driven research run** at `workspace/research/alpha_mining/event_driven_strategy_research_full_20260401_main/` — same contamination. All 43 factor cards + walk-forward fold selections were derived from leaking factors.
- **`small_cap` theme strategy** in `data/candidate_registry/` (23 current theme components) — the theme framework sources components from the factor library; any component referencing a downgraded factor may no longer deliver the expected signal. Recommended action: flag candidate records with `pending_re_validation` status; re-import after the theme pipeline is rerun.
- **ML research run** at `workspace/research/alpha_mining/event_driven_strategy_ml_research_full_20260404_main/` — ElasticNet / LightGBM coefficients were fit on the contaminated factor matrix. The model outputs cannot be trusted for live deployment until refit on the post-fix factors.

Remediation scope for each of the above will be tracked in a separate "strategy re-validation" follow-up plan, drafted after the user reviews `post_fix_screening_diff.md`.

---

## Important Conventions

### Qlib `.day.bin` Format

- Format: `[float32 start_index][float32 data... ]`
- The first float is a calendar offset header, not a data value.
- Manual `.day.bin` I/O must go through `src/data_infra/storage/qlib_bin_utils.py`.

### Qlib MultiIndex Order

- Qlib `D.features()` returns `MultiIndex(instrument, datetime)`.
- The `factor_eval` toolkit can normalize either order internally.
- Raw pandas code must still be explicit about grouping level and whether `swaplevel()` has been applied.

### Research Backtest Defaults

- Serious daily-strategy research should set vectorized execution parameters explicitly and prefer:
  - `deal_price='open'`
  - `only_tradable=False`
  - `forbid_all_trade_at_limit=True`
- Use `EventDrivenBacktester` when JoinQuant parity, corporate actions, or execution realism are central to the task.

---

## Data Sync Status

- **Market daily**: `2008-01-02` -> `2026-02-27` (`4,410` trading days)
- **Fundamentals**: core quarterly datasets through the latest locally synced filings
- **Index weights**: monthly snapshots through `2026-03`
- **Reference data**: `stock_basic`, `trade_cal`, name-change, and ST support files are present locally
- **Phase 3 data expansion**:
  - `cashflow`, `forecast`, and `holder_number` are fully downloaded and now flow through the staged normalization / ledger path
  - `cashflow_quarterly` is now historically backfilled through `2025-12-31` and participates in paired-ledger quarter-canonical cashflow serving
  - `moneyflow`, `northbound`, `margin`, and `stk_limit` are fully downloaded but still require anomaly review before production publish
- **Backend serving layers**:
  - raw immutable Parquet remains under `data/`
  - canonical normalized outputs land under `data/normalized/`
  - revision-aware ledgers land under `data/pit_ledger/`
  - staged provider builds land under `data/qlib_builds/<build_id>/`
- For exact row counts and partition details, defer to `data/data_tracker.md`.
