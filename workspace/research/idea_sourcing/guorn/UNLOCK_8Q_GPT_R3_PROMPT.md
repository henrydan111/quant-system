# GPT-5.5 Pro cross-review — R3 (8-quarter factor unlock plan)

**Status:** R2 returned REWORK (B1 depth, B2 comparator, M1 wrapper assert, M2 Route-B kernel, M3 top-K
enforcement, M4 dividend grain). All folded; re-review per CLAUDE.md §10.

> ⚠ **Read the `raw.githubusercontent.com` links below, NOT `github.com/.../blob/...`.** R2's B2 finding
> ("comparator has no `--provider-uri`") was a **stale GitHub `blob/` HTML cache** — the change has been on the
> branch since commit d085204. GitHub's HTML `blob/` view lags the CDN after a push; the `raw` endpoint is
> authoritative and current (verified: `git show origin/report-rc-registration:…`, the raw view, and `--help`
> all show `--provider-uri` at lines 43/130/138-140/263/273).

## What this is

NON-FORMAL parity campaign (果仁/guorn.com = trusted benchmark; local Tushare+Qlib under test). 52/56 campaign
factors reproduce 果仁's top-K; 4 stay blocked needing an 8-quarter statement lookback the live provider doesn't
carry (q0..q4). This plan unlocks them via 3 NON-FORMAL routes (no publish/registry/field_status/OOS).

## Live links (report-rc-registration @ b2086ee — RAW, all current)

- Plan: https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/workspace/research/idea_sourcing/guorn/UNLOCK_8Q_FACTORS_PLAN.md
- Comparator: https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/workspace/scripts/guorn_factor_parity.py
- Deep-slot wrapper: https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/workspace/scripts/_build_deepslot_8q.py
- Contract §3.2/§6.3/§7: https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/CLAUDE.md
- (path-resolver evidence for M1) `resolve_build_paths` / `BuildPaths`: https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/src/data_infra/pit_backend.py

## R2 findings and how each was folded (all verified)

| # | R2 finding | Fold | Verification |
|---|---|---|---|
| **B1** | depth 8 can't test begin/end ATO at year-ago leg (needs assets_q8) | `slot_depth=9` (q0..q8); q8 only for candidate B | wrapper dry-run prints `slot_depth=9`, est 15.7GB<30GB |
| **B2** | "comparator has no --provider-uri" | **stale blob cache** — it IS live (d085204) | `git show` + raw + `--help` all show it |
| **M1** | wrapper assert guards source not output | assert now on `provider_dir` (staged OUTPUT under qlib_builds, != live) + publish=False; old `qlib_dir!=live` removed | real dry-run: source=live `qlib_data`, output=staged `qlib_builds/…`, no abort |
| **M2** | Route B sequence must use sanctioned PIT kernel | plan: q0..q7 end_dates from `pit_alignment_core`/loader/staged provider, never raw `pit_ledger/*` scan; + restatement canary 2 | plan Route B |
| **M3** | top-K printed, not enforced | comparator `--min-top5/10/20` (default 0.8) → `TOP-K GATE` + single `OVERALL` verdict (✗ if pointwise OR top-K fails) | smoke-test: clean→`OVERALL ✅`, rank-inverted→`OVERALL ✗` |
| **M4** | dividend total = aggregate-DPS × one base | plan: `div_total = Σ_i (dps_i × share_base_i)` at event/FY grain | plan Route C |
| **m1/m2** | naming / export-subset | build_id `guorn_unlock_9q_scoped`; wrapper `--export-xlsx` asserts `export ⊆ touched` | wrapper |

## Key code to scrutinize

- **M1 (path-resolver):** `resolve_build_paths` (pit_backend.py ~L723-759) returns `qlib_dir` = live
  `data/qlib_data` (the scoped-copy SOURCE + publish target) and `provider_dir = build_root/provider` under
  `data/qlib_builds/<id>`. The wrapper now asserts `staged(=provider_dir) != live` and `"qlib_builds" in staged`,
  keeps `qlib_dir` as the source, and post-build asserts the builder wrote `provider_dir`. Is this the correct
  source/output separation, and does anything still let a build escape the staged dir or publish?
- **M3 (gate):** `report(...)` computes per-K overlap into `ovk`, then `topk_fail` vs `min_topk`, then prints a
  single `OVERALL` that is ✗ if `metric_verdict` starts ✗ OR any top-K under threshold OR the top-20 zone has
  local NaNs. Is the combined verdict logic correct and un-gameable?

## Self-review (per §10)

§3.2 strengthened (M2 kernel-sourced sequence + restatement canary); §6.3 output-path-guarded (M1) + depth-9
still <30GB (B1); false-pass closed by the machine gate (M3) + per-event aggregation (M4). Verified: both
scripts parse; `--provider-uri`/`--min-top` wired; `resolve_build_paths` resolves; wrapper dry-run clean; M3
smoke-test passes both paths. **Verdict: clean for re-review.**

## Review questions (R3)

1. Is the **M1 source/output separation** correct, with no path by which a build writes to the live provider or
   publishes?
2. Is **depth-9** now sufficient AND minimal for both pre-registered ATO denominators?
3. Is the **M3 OVERALL verdict** logic correct (no way to read "verified" on pointwise parity alone)?
4. Is **Route B** (M2) now leak-free given the period sequence is sourced from the sanctioned PIT kernel +
   canaries 1 & 2?
5. **Any remaining blocking issue before execution?** If none, please state APPROVE.
