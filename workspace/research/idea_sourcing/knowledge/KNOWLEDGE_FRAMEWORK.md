# arXiv Knowledge Framework — finding valuable papers & research directions

*Created 2026-06-10. Purpose: turn the arXiv firehose (~18k q-fin matches, growing daily) into a
small, value-ranked, **dimension-clustered** stream of actionable A-share research directions — and
do it repeatably, not once.*

This is the **intelligence layer** the original `fetch_arxiv_qfin.py` lacked. That fetcher lands the
*newest* q-fin preprints into a queryable store and stops — a firehose, not a framework. The pieces
here add the three things that make raw arXiv usable: a **definition of value** specific to this
system, a **deterministic value scorer**, and a **research-direction map** that organizes the result
against what we already know about our own frontier.

---

## The core idea: what "valuable" means here

Ranking arXiv by recency (the old fetcher) or by citations (OpenAlex) both miss. For *this* system,
the value of a paper is:

> **value ≈ P( the paper yields a new, orthogonal, DEPLOYABLE A-share factor )**

That probability is high only when a paper is simultaneously (a) about the **cross-section of equity
returns**, (b) **computable on data we have**, and (c) in a research dimension we have **not already
saturated**. The framework estimates that prior from keyword evidence, then a human/LLM read of the
top slice is the precision verdict. The score is a **triage prior, never a verdict** — the same
honest split the OSAP novelty heuristic uses.

The decisive input is our hard-won **saturation map** (from the OSAP experiment: 12 US-anomaly ports →
1 candidate → 0 deployable). Price / accounting / volatility / size / liquidity are **SATURATED** for
our 182-factor book; the open frontier is **analyst · earnings-event · informed-flow · ownership ·
behavioral-chips** — dimensions where we recently approved the data (`report_rc`, `moneyflow`,
`hk_hold`, `cyq_perf`, …) but have barely built factors. The scorer rewards frontier exposure.

---

## The four layers

| Layer | File | What it does |
|---|---|---|
| **0 · Acquire** | [fetchers/fetch_arxiv_qfin.py](../fetchers/fetch_arxiv_qfin.py) | Now supports `--query-pack frontier`: a **themed relevance harvest** across ~45 phrases aligned to the frontier dimensions, over a **broadened** category set (`q-fin.* + cs.LG + econ.EM + stat.ML`). Unions + dedups into the store. (The legacy newest-N mode is preserved as the default.) |
| **1 · Know** | [knowledge/taxonomy.py](taxonomy.py) | The **brain**: our data inventory (16 HAVE / 12 LACK capabilities), the research-dimension taxonomy tagged with **our saturation status**, and the scoring lexicons (relevance / hard-veto / empirical / China). Single source of truth for "what we already know about our own frontier." Pure data, no deps. |
| **2 · Score** | [knowledge/score_papers.py](score_papers.py) | Per-paper sub-scores → composite. Deterministic + offline (reproducible ranking). Two presets: **frontier** (default; dimension·empirics·recency dominate — finds new directions) and **established** (impact dominates — surfaces canonical work). |
| **3 · Map** | [knowledge/build_research_map.py](build_research_map.py) | Clusters the ranked papers into the taxonomy → `RESEARCH_DIRECTIONS.md` (the scaffold) + draft pre-registration stubs for the top buildable frontier papers. |
| **4 · Impact** | [enrich/enrich_openalex.py](../enrich/enrich_openalex.py) | Attaches OpenAlex citations / venue (the credibility signal). Keyless polite pool. Sparse-by-design for 2026 preprints; the frontier preset is robust to its absence. |

### The score, precisely

```
composite = relevance_gate × Σ wᵢ · subscoreᵢ
```
- **relevance_gate** ∈ [0.05, 1] — is it cross-sectional equity at all? A **hard veto** (crypto / FX /
  bond vocabulary) caps it near the floor regardless of incidental factor-speak.
- **dimension_value** — the taxonomy status weight of the paper's primary dimension
  (FRONTIER_OPEN 1.0 · METHOD/BLOCKED 0.5-0.55 · SATURATED 0.2 · NOT_PORTABLE 0.05), + a bonus for
  touching multiple open frontiers. **This is where novelty + feasibility enter.**
- **empirical** — density of OOS / Sharpe / IC / t-stat / long-short vocabulary in the abstract.
- **recency** — frontier preference (2015→0 … 2026→1).
- **china** — A-share-specific bonus.
- **impact** — log-scaled OpenAlex citations (frontier preset weight only 0.12).

Frontier weights: `dimension 0.42 · empirical 0.22 · recency 0.16 · impact 0.12 · china 0.08`.

---

## Run it

```bash
# 0. harvest a high-signal corpus (themed, relevance-sorted; ToU-compliant ≥3s/req, ~5 min)
venv/Scripts/python.exe workspace/research/idea_sourcing/fetchers/fetch_arxiv_qfin.py \
    --query-pack frontier --per-query 40

# 4. (optional) attach OpenAlex citations — the impact signal
venv/Scripts/python.exe workspace/research/idea_sourcing/enrich/enrich_openalex.py

# 2. score & rank (frontier = find new directions; established = canonical work)
venv/Scripts/python.exe workspace/research/idea_sourcing/knowledge/score_papers.py --top 50
venv/Scripts/python.exe workspace/research/idea_sourcing/knowledge/score_papers.py --preset established --top 40

# 3. build the dimension-clustered research map + draft stubs
venv/Scripts/python.exe workspace/research/idea_sourcing/knowledge/build_research_map.py --top 80 --stubs 8
```

Re-running is incremental and idempotent (the store dedups by arXiv id; enrichment resumes from cache).
Run the harvest periodically to top up; re-score to re-rank.

---

## Outputs (the deliverables)

| File | What |
|---|---|
| `store/arxiv_qfin.parquet` | the harvested corpus (gitignored) |
| `store/arxiv_qfin_enriched.parquet` | OpenAlex citations/venue per paper (gitignored) |
| `knowledge/ranked_papers.{parquet,md}` | the value-ranked shortlist |
| `knowledge/research_map.parquet` + `RESEARCH_DIRECTIONS.md` | the auto-generated dimension map (regenerable scaffold) |
| **`knowledge/TOP_DIRECTIONS.md`** | the **curated analyst extraction** — top directions mapped to our exact fields, novelty-assessed, with build recipes + validation path. The durable deliverable. |
| `knowledge/stubs/arxiv_*.json` | draft pre-registration stubs (non-registerable until a human fills `expected_effect` + confirms an unburned OOS window) |

---

## How this connects to the lifecycle (the guardrail)

This is **upstream idea-sourcing tooling** (Class-D), not a formal data plane. It does NOT touch the
PIT ledger / Qlib provider / field registry / the 5 typed registries. A paper sourced here is a
**hypothesis source, never evidence**. Any factor it inspires still runs the full pipeline:

```
arXiv paper → TOP_DIRECTIONS recipe → factor_library draft (PIT-safe Ref(...,1), registered fields)
  → sandbox screen → size/industry-neutralized MARGINAL-contribution test vs catalog (the house rule)
  → factor_lifecycle (draft→candidate, IS-only) → single-shot sealed-OOS → (maybe) approved
  → SEPARATE deployment gate (approved factor ≠ tradable strategy)
```

The framework's job ends at a ranked, field-grounded, pre-registerable **hypothesis**. The gates do
the rest — and as `eps_diffusion` showed, a genuine `approved` factor can still fail the deployment
gate. The framework raises P(finding a real direction); it does not lower any bar.

---

## Honest limitations

- The score is **keyword-heuristic** (high recall, moderate precision). It surfaces candidates; it does
  not understand a paper. The LLM read of the top ~40 is mandatory (→ `TOP_DIRECTIONS.md`).
- Harvest recall is bounded by the themed phrases in `THEME_QUERIES` — a dimension with no phrase is
  invisible. Extend the pack as the frontier moves.
- OpenAlex impact is **sparse for frontier preprints** (2026 papers usually have 0 citations / no
  record yet). Impact mainly discriminates older, canonical work — hence its low frontier-preset weight.
- The taxonomy encodes **today's** saturation map; when a SATURATED dimension is re-opened by new data,
  or an OPEN one gets mined out, update `taxonomy.py` (it is the single source of truth for status).
