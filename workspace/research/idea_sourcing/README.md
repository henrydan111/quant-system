# Idea-Sourcing Pipeline (research-direction inflow)

*Created 2026-06-08. Purpose: turn "the system lacks research ideas" into a steady,
deduplicated inflow of **pre-registerable hypotheses** + citations.*

This is **upstream idea-sourcing tooling**, not a formal data plane. It does NOT
touch the PIT ledger / Qlib provider / field registry / the 5 typed registries.
A paper or 研报 sourced here is a **hypothesis source, never evidence** — any factor
it inspires still runs the full IS-only → sealed-OOS lifecycle (CLAUDE.md §3.5, §7).

## What's built (pilot — English-academic slice)

| File | Role |
|---|---|
| [probe_idea_sources.py](probe_idea_sources.py) | Read-only feasibility probe — one minimal real call per source, classifies ACCESS/RATE_LIMITED/BLOCKED/ERROR. Stdlib only (no dependency). Mirrors the house norm of `scripts/probe_tushare_endpoints.py`. |
| [fetchers/fetch_arxiv_qfin.py](fetchers/fetch_arxiv_qfin.py) | Incremental, dedup'd, ToU-compliant fetcher for newest arXiv `q-fin.*` preprints → Parquet store. |
| [fetchers/fetch_osap_signaldoc.py](fetchers/fetch_osap_signaldoc.py) | Pulls the Open Source Asset Pricing **SignalDoc catalog** (212 published predictors + 114 placebos, each with source paper / sign / economic category / original t-stat / GScholar cites / reproduction quality) → Parquet. Replicates only the public Google-Drive CSV path — **no `openassetpricing` install** (avoids `polars` + the paid-WRDS dependency, see below). |
| [triage/triage_osap_to_ashare.py](triage/triage_osap_to_ashare.py) | **Extraction/triage layer (#3).** Turns the 212 OSAP predictors into a ranked A-share candidate shortlist (feasibility × novelty vs the live 177-catalog) + **draft hypothesis stubs** for human pre-registration. Does not register anything. |
| `store/arxiv_qfin.parquet` | One row per arXiv base id (latest version), with `first_seen`/`last_seen`. Gitignored. |
| `store/osap_signaldoc.parquet` | One row per OSAP signal (331), `osap_release` + `fetched_utc` stamped. Gitignored. |
| `triage/osap_ashare_triage.{parquet,md}` + `triage/stubs/*.json` | Ranked triage table + readable report + per-candidate draft stubs. |

The LLM "extract testable claim → pre-registration stub" step is **intentionally not
built yet** — this pilot stops at a queryable store.

## Verified feasibility (live probe, 2026-06-08 — not memorized)

| Source | Verdict | Notes |
|---|---|---|
| **arXiv q-fin** | 🟢 ACCESS | ATOM API, full abstract+PDF, 18,364 q-fin matches. ToU: ≥3s/req, single conn. |
| **OpenAlex** | 🟢 ACCESS (keyless) | Scholarly metadata + citation graph. Returned Carhart 1997 on a momentum query. The keyless substitute for the S2 citation-graph role. |
| **Semantic Scholar** | 🟡 RATE_LIMITED | Keyless public pool 429s from this IP (3/3 tries). Needs a free `x-api-key` (env `IDEA_S2_API_KEY`) or the bulk Datasets snapshots. |
| **Open Source Asset Pricing** | 🟢 ACCESS (via Google Drive) | openassetpricing.com itself TLS-times-out here, but that host is irrelevant: the data lives in public **Google-Drive** release folders (reachable, HTTP 200). The `openassetpricing` pip pkg drags in `polars` + **`wrds` (paid Wharton subscription)** — needed only for US/CRSP signal *values* (permno-keyed, unusable in A-shares). We replicate just the SignalDoc-catalog CSV path → 212 predictors, dependency-free. **Built (fetch_osap_signaldoc.py).** |

Probe artifacts: `workspace/outputs/idea_sources_probe_*.json`.

### Why not `pip install openassetpricing`

Its `install_requires` = `polars, pandas, requests, tabulate, wrds, pyarrow, beautifulsoup4`.
`wrds` needs a **paid Wharton Research Data Services account** (it opens a Postgres
connection in `_dl_signal_crsp3`) and is imported at module top. The WRDS-gated part is
the firm-month signal *values* — which are US `permno`-keyed and not portable to A-shares
anyway. The idea-sourcing payload (the **catalog**: paper, sign, category, t-stat, cites,
repro-quality) is a single public Drive CSV (`SignalDoc.csv`), so we pull only that with
the existing requests/pandas stack and add **zero** dependencies to the pinned Qlib venv.

## Run

```bash
# feasibility probe (safe, read-only)
venv/Scripts/python.exe workspace/research/idea_sourcing/probe_idea_sources.py

# fetch newest 100 q-fin preprints (idempotent — re-run to incrementally top up)
venv/Scripts/python.exe workspace/research/idea_sourcing/fetchers/fetch_arxiv_qfin.py --max-results 100

# subset + extra full-text term
...fetch_arxiv_qfin.py --categories q-fin.PM,q-fin.ST --query "cross-sectional" --max-results 300
```

## Run (OSAP catalog)

```bash
# pull the latest (202510) predictor catalog → store/osap_signaldoc.parquet
venv/Scripts/python.exe workspace/research/idea_sourcing/fetchers/fetch_osap_signaldoc.py

# inspect a release folder without downloading; or dry-run a different release
...fetch_osap_signaldoc.py --list
...fetch_osap_signaldoc.py --release 202410 --dry-run
```

## Store schemas

- **`arxiv_qfin.parquet`**: `arxiv_id, version, title, abstract, authors,
  primary_category, categories, published, updated, doi, journal_ref, comment,
  pdf_url, abs_url, source, first_seen_utc, last_seen_utc`
- **`osap_signaldoc.parquet`** (31 cols): key idea-triage fields are `Acronym, Authors,
  Year, Journal, LongDescription, Sign, Cat.Economic, Cat.Signal` (Predictor/Placebo/Drop),
  `SampleStartYear/EndYear, Return, T-Stat, Signal Rep Quality, GScholarCites202509`,
  + `osap_release, fetched_utc`.

## Triage / extraction (#3) — how to use

```bash
venv/Scripts/python.exe workspace/research/idea_sourcing/triage/triage_osap_to_ashare.py --top-stubs 15
```

Output of the 2026-06-08 run (212 predictors):

| feasibility \ novelty | DUP | LIKELY_NOVEL | REVIEW |
|---|---|---|---|
| BUILDABLE_NOW | 14 | 0 | 124 |
| NOT_PORTABLE | 0 | 9 | 0 |
| PARTIAL | 1 | 64 | 0 |

- **NOT_PORTABLE (9)** = optionrisk / short-sale-constraint anomalies — no data / A-share
  structural mismatch. Correctly excluded.
- **PARTIAL + LIKELY_NOVEL (64)** = the orthogonal frontier (analyst/earnings-forecast,
  recommendation, earnings-event, informed-trading, ownership, external-financing) — blocked
  on the Tushare expansion (report_rc Wave-1 etc.). This is where new, uncorrelated alpha lives.
- **BUILDABLE_NOW + REVIEW (124)** = buildable on data we have, but the category is already
  covered — human must confirm whether it's a genuinely new variant. Verified genuine gaps
  surfaced here: **Beta** (CAPM/betting-against-beta), **IdioVol3F**, **LRreversal**,
  **BetaLiquidityPS**, **GP**, **Coskewness**, **AssetGrowth**.

**A stub is a DRAFT, not a registered hypothesis.** Each `stubs/*.json` loads via
`Hypothesis.from_dict` but `validate()` *refuses* it while `expected_effect` is null — the
safe gate. To promote one: implement the proposed factor (US def → A-share fields, PIT-safe),
set `expected_effect` to YOUR A-share prediction (never copy the US `_draft_review` evidence),
edit the `[DRAFT]` concerns, confirm an unburned OOS window, then
`hypothesis_cli.py register --file stubs/<f>.json --profile-id factor_screening`.

The novelty/dup flags are a **heuristic** (small confident dup map + category coverage) — they
need human confirmation, not blind trust.

## Phase-1 build — batch 1 (the 4 verified price/market-relative gaps)

[build/eval_phase1_price_gaps.py](build/eval_phase1_price_gaps.py) — governance-safe SANDBOX
screen (custom `compute_factors` dict, no `catalog.py` mutation). IS 2014-2020, fwd_20d,
EW-market proxy, 1707 days × 4121 stocks.

| candidate | mean RankIC | RankICIR | \|t\| | pred. sign | verdict |
|---|---|---|---|---|---|
| `idiovol_capm_60d` | −0.1127 | −0.854 | 34.0 | −1 ✓ | clears massively — **suspect** (size/vol entanglement; overlaps `risk_vol_*`) |
| `beta_250d` | −0.0331 | −0.134 | 5.1 | +1 → **flipped** | clears; **betting-against-beta** (low-β wins) |
| `rev_lt_36_12` | −0.0171 | −0.135 | 5.6 | −1 ✓ | clears; genuine new factor |
| `coskew_250d` | −0.0078 | −0.047 | 1.6 | −1 | **fails** (\|t\|<2) — drop |
| `daily_ret_1d` (sanity) | −0.0075 | −0.070 | 2.9 | −1 ✓ | weak, expected |

**Read:** 3 of 4 clear the ~0.02 RankICIR floor; coskew fails. These are **raw, un-neutralized,
IS-only** RankICs — NOT validation. Before any promotion: (1) size/industry-neutralize, (2)
**marginal-contribution test vs the existing catalog** (idio-vol especially — its huge standalone
ICIR likely repackages the small-cap/`risk_vol_*` effect; select by marginal IC × low correlation,
not standalone ICIR), (3) cost/turnover. Then survivors → real operator + the formal
`factor_lifecycle` IS-only gate → sealed OOS. Outputs: `workspace/outputs/idea_sourcing_phase1/`.

### Batch 2 — accounting gaps (all from approved fina_indicator/daily_basic fields, no new data)

Field probe (2026-06-08) confirmed `assets_yoy, grossprofit_margin, assets_turn, total_share,
eqt_yoy` resolve with ~full coverage. Screen (same IS/fwd_20d):

| candidate | expr | mean RankIC | RankICIR | \|t\| | pred. sign | verdict |
|---|---|---|---|---|---|---|
| `gross_profitability` | `grossprofit_margin × assets_turn` | +0.0191 | +0.147 | 6.1 | +1 ✓ | genuine (Novy-Marx ports) |
| `net_stock_issuance` | `total_share` YoY | −0.0098 | −0.133 | 5.5 | −1 ✓ | genuine (split confound to clean up) |
| `asset_growth` | `assets_yoy` | +0.0088 | +0.116 | 4.8 | −1 → **flipped** | sig. but **US anomaly does NOT port** (positive here) |
| `equity_growth` | `eqt_yoy` | +0.0040 | +0.039 | 1.6 | −1 | **fails** |

### Phase-1 combined scorecard (8 candidates → keep ~5)

| keep (clears + defensible sign) | suspect (needs marginal test) | doesn't port / fails |
|---|---|---|
| `gross_profitability` (+0.15), `net_stock_issuance` (−0.13), `rev_lt_36_12` (−0.14), `beta_250d` (−0.13, BAB) | `idiovol_capm_60d` (−0.85 — likely repackages size/`risk_vol_*`) | `asset_growth` (sign-flipped), `coskew_250d` (fails), `equity_growth` (fails) |

**Decisive next test for ALL survivors:** size/industry-neutralize + **marginal-contribution vs the
177-catalog** (marginal IC × low correlation, not standalone ICIR — the house rule). That separates
orthogonal new alpha from repackaged existing factors (critical for idio-vol & gross-profitability).
Only then → real operator + formal `factor_lifecycle` (draft→candidate→sealed-OOS).

### Phase-1 marginal-contribution gate (DECISIVE — overturns the standalone screen)

`build/eval_phase1_marginal_test.py` vs the cached 31-factor book (combined RankICIR **0.791**).

| candidate | standalone ICIR | size-neut ICIR | max payoff corr | most-corr existing | increment to book | verdict |
|---|---|---|---|---|---|---|
| gross_profitability | 0.147 | 0.224 | 0.891 | qual_gross_margin | **+0.022** | PARTIAL |
| asset_growth | 0.116 | 0.235 | 0.852 | qual_net_margin | +0.009 | REDUNDANT |
| idiovol_capm_60d | **0.854** | 0.795 | 0.835 | risk_vol_60d | +0.009 | REDUNDANT |
| rev_lt_36_12 | 0.135 | 0.121 | 0.685 | grow_revenue_yoy | −0.005 | PARTIAL |
| net_stock_issuance | 0.133 | 0.036 | 0.798 | qual_gross_margin | −0.007 | REDUNDANT |
| beta_250d | 0.134 | 0.312 | 0.909 | val_ep_ttm | −0.011 | REDUNDANT |

**Conclusion: NONE are clean orthogonal additions.** The book (ICIR 0.79) already spans these
price/accounting styles. The biggest standalone winner (idiovol 0.85) is the *most* redundant
(corr 0.84 to `risk_vol_60d`, +0.009 increment) — the house rule (marginal > standalone ICIR)
vindicated; it just stopped a false promotion. `net_stock_issuance` collapses under
size-neutralisation (0.13→0.04 = a size bet). Only `gross_profitability` adds anything (+0.022) and
even it is 0.89-correlated to `qual_gross_margin` → a *refinement*, not new alpha.

**Strategic takeaway:** the price/accounting style space is **saturated** for this book. New
orthogonal alpha lives in dimensions it does NOT cover — the PARTIAL/analyst/event/ownership bucket
that needs the `report_rc` integration. Stop mining price/accounting variants; prioritise the data
integration.

### GP orthogonal-residual probe (`build/probe_gross_profitability_residual.py`)

| variant | mean RankIC | RankICIR | \|t\| | retained vs raw |
|---|---|---|---|---|
| gross_profitability (raw) | 0.0191 | 0.147 | 6.1 | 100% |
| residual ⟂ {gross_margin, asset_turn} | 0.0182 | **0.174** | 7.2 | 118% |
| residual ⟂ full quality set | 0.0119 | 0.155 | 6.4 | 106% |

**GP is a genuine keeper.** Orthogonalised to its own components AND the full quality set, the signal
*strengthens* (ICIR 0.147→0.174) — gross-profit-to-**assets** carries independent structure (|t|=7.2)
not in `qual_gross_margin`/`qual_asset_turnover`. Final Phase-1 tally: **8 OSAP candidates → 1 keeper
(GP)**; the process correctly rejected 7 (incl. the standalone star idiovol).

### Batch 3 (Tier 1) — thin-coverage gaps: DRY (marginal-test verdict)

`build/eval_phase1_batch3_tier1.py` + the marginal gate vs the 31-factor book (ICIR 0.79):

| candidate | standalone ICIR | size-neut | max payoff corr | most-corr existing | increment | verdict |
|---|---|---|---|---|---|---|
| cash_to_assets | 0.047 | 0.071 | 0.835 | lev_debt_to_assets | +0.019 | PARTIAL |
| rd_to_assets | 0.254 | 0.180 | **0.636** | val_sp_ttm | +0.017 | PARTIAL |
| noa | 0.084 | 0.257 | 0.749 | size_ln_circmv | −0.006 | REDUNDANT |
| fcff_to_assets | 0.197 | 0.325 | 0.906 | val_cftp | −0.008 | REDUNDANT |

**0 clean orthogonal additions.** Standalone-strong ones collapse on the marginal test: `fcff_to_assets`
(ICIR 0.197) is OCF-yield repackaged (0.91 corr to `val_cftp`, negative increment); `noa` is a size bet.
The two that add anything (cash, rd) are below the +0.02 bar. `rd_to_assets` has the lowest correlation
(0.636, the one true R&D gap) but only 31% coverage + below-bar increment → not worth the OOS spend
(esp. after GP's OOS collapse).

### Cumulative OSAP verdict (the well is dry for this book)

**12 OSAP factors screened → 1 reached candidate (GP) → 0 deployable** (GP failed sealed-OOS).
Batches 1 (price/market-relative), 2 (accounting), 3 (thin-coverage gaps) ALL confirm: the
price/accounting style space is **saturated** for the existing 178-factor book — more US-anomaly ports
yield near-duplicates. New orthogonal alpha needs a **new data dimension** (analyst/event/ownership →
`report_rc`) or a **new idea source outside OSAP** (arXiv frontier / Chinese 研报). Stop mining OSAP
price/accounting.

## Next targets (not yet built)

1. ✅ **GP added as a catalog draft** (2026-06-08): `qual_gross_profitability` =
   `Ref($grossprofit_margin,1) * Ref($assets_turn,1)` in [catalog.py](src/alpha_research/factor_library/catalog.py)
   QUALITY. The factor count is now SELF-UPDATING via `catalog_composition()` (the hard-coded 177
   tripwire was replaced by a derived catalog↔registry parity check), so GP flowed in 177→178 with
   no test edits. Remaining: register the draft row (`sync_catalog`) + run `factor_lifecycle`
   (draft→candidate IS gate) → sealed-OOS for `approved`.
2. ✅ **`report_rc` integrated + eps_diffusion promoted** (2026-06-09): the analyst dimension the
   saturated-book finding pointed to — **and it paid off.** report_rc approved (4 `$report_rc__*`
   event-flow primitives); built the EPS-revision-breadth family ([build/eval_report_rc_diffusion.py](build/eval_report_rc_diffusion.py)),
   size-neutralized IS ICIR **+0.55** (60d) and it **SURVIVES orthogonalization to ROE/growth**
   (residual retains ~100%) → the **first genuinely-new-dimension** factor (analyst info beyond
   fundamentals); reproduces the prior untrusted hand-rolled pilot through the compliant path.
   Promoted `earn_eps_diffusion_60` / `earn_eps_diffusion_120` to formal-eligible catalog **draft**.
   ⚠ marginal increment is only +0.011 (PARTIAL in EW-composite — correlated 0.67 to `qual_roe`);
   ⚠ candidate→approved **sealed-OOS is HARD-GATED behind the 2026-06-15 breadth canary**.
   Remaining: `factor_lifecycle` IS gate now → sealed-OOS after the canary.
3. **OpenAlex enrichment**; **Chinese 研报 slice** via AKShare.
