# ──────────────────────────────────────────────────────────────────────
# SCRIPT_STATUS header block.
# script_status: class_d_research_tooling
# formal_research_allowed: false
# touches_formal_data_plane: false
# pr2_audit_class: D
# notes: |
#   Idea-sourcing EXTRACTION/TRIAGE layer (#3). Turns the OSAP SignalDoc
#   catalog (212 published US predictors) into a ranked A-share candidate
#   shortlist + DRAFT hypothesis stubs for human pre-registration.
#
#   It does NOT register anything. Pre-registration is a human gate
#   (research-integrity §7 / §10). Output stubs are intentionally
#   NON-registerable until a human fills `expected_effect` (their A-share
#   prediction) and confirms an unburned OOS window. The US Return/T-Stat
#   are carried only as CONTEXT in a `_draft_review` sidecar, never copied
#   into the prediction.
#
#   De-dup vs the live 177-factor catalog is a HEURISTIC (small high-confidence
#   dup map + category-coverage), flagged for human confirmation — not a claim
#   of certainty. Reads OSAP store + the live catalog; writes ONLY under
#   workspace/research/idea_sourcing/triage/.
# ──────────────────────────────────────────────────────────────────────
"""
OSAP → A-share hypothesis triage.

For each OSAP *Predictor* (excludes Placebos/Drops):
  1. feasibility  — can it be built on A-share data we HAVE? (BUILDABLE_NOW /
     PARTIAL / NOT_PORTABLE), via a curated Cat.Economic -> data-need map.
  2. novelty      — is it already in our 177-factor catalog? (DUP /
     REVIEW / LIKELY_NOVEL), via a small confident dup map + category coverage.
  3. rank         — feasibility, then novelty, then influence (GScholar cites),
     restricted to clean reproductions (1_good / 2_fair).

Outputs (under triage/):
  osap_ashare_triage.parquet   full table, all 212 predictors
  osap_ashare_triage.md        readable ranked report + summary matrix
  stubs/hyp_osap_<acro>.json   DRAFT hypothesis stubs for the top novel+buildable

Usage
-----
  venv/Scripts/python.exe workspace/research/idea_sourcing/triage/triage_osap_to_ashare.py
  ...triage_osap_to_ashare.py --top-stubs 15 --dry-run
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

IDEA_DIR = PROJECT_ROOT / "workspace" / "research" / "idea_sourcing"
OSAP_STORE = IDEA_DIR / "store" / "osap_signaldoc.parquet"
TRIAGE_DIR = IDEA_DIR / "triage"
STUB_DIR = TRIAGE_DIR / "stubs"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("triage_osap")

# ── Curated map: OSAP Cat.Economic -> (feasibility, our_prefix, data_need) ──
# feasibility is judged against datasets the system ALREADY ingests
# (price/vol/amount, mcap, income/balance/cashflow/fina_indicator, dividends,
# moneyflow, margin_detail, hk_hold northbound, LHB top_list/top_inst,
# stk_holdernumber). PARTIAL = needs a source in the Tushare-expansion plan
# (report_rc analyst / express / top10_holders). NOT_PORTABLE = no data or an
# A-share structural mismatch.
F_BUILD, F_PARTIAL, F_NO = "BUILDABLE_NOW", "PARTIAL", "NOT_PORTABLE"
FEASIBILITY_MAP: dict[str, tuple[str, str, str]] = {
    "momentum":               (F_BUILD,   "mom",   "price"),
    "long term reversal":     (F_BUILD,   "rev",   "price"),
    "short-term reversal":    (F_BUILD,   "rev",   "price"),
    "volatility":             (F_BUILD,   "risk",  "price"),
    "risk":                   (F_BUILD,   "risk",  "price+index"),
    "liquidity":              (F_BUILD,   "liq",   "price+vol+amount"),
    "volume":                 (F_BUILD,   "liq",   "vol"),
    "size":                   (F_BUILD,   "size",  "mcap"),
    "valuation":              (F_BUILD,   "val",   "daily_basic+statements"),
    "profitability":          (F_BUILD,   "qual",  "income+balance"),
    "profitability alt":      (F_BUILD,   "qual",  "income+balance"),
    "accruals":               (F_BUILD,   "qual",  "income+cashflow+balance"),
    "investment":             (F_BUILD,   "grow",  "balance (asset/capex growth)"),
    "investment alt":         (F_BUILD,   "grow",  "balance"),
    "investment growth":      (F_BUILD,   "grow",  "balance"),
    "asset composition":      (F_BUILD,   "qual",  "balance"),
    "composite accounting":   (F_BUILD,   "qual",  "multi-statement"),
    "leverage":               (F_BUILD,   "lev",   "balance"),
    "sales growth":           (F_BUILD,   "grow",  "income"),
    "earnings growth":        (F_BUILD,   "grow",  "income"),
    "cash flow risk":         (F_BUILD,   "qual",  "cashflow"),
    "payout indicator":       (F_BUILD,   "val",   "dividends"),
    "lead lag":               (F_BUILD,   "mom",   "cross-sectional price/industry (complex)"),
    "external financing":     (F_PARTIAL, "grow",  "net equity/debt issuance (derivable, messy)"),
    "earnings forecast":      (F_PARTIAL, "earn",  "report_rc analyst (Tushare Wave-1, in progress)"),
    "recommendation":         (F_PARTIAL, "earn",  "report_rc ratings (Wave-1)"),
    "earnings event":         (F_PARTIAL, "earn",  "express + disclosure_date (Wave-1)"),
    "informed trading":       (F_PARTIAL, "flow",  "moneyflow / LHB top_inst (proxy)"),
    "ownership":              (F_PARTIAL, "north", "hk_hold + holdernumber (top10_holders not yet)"),
    "r&d":                    (F_PARTIAL, "qual",  "rd_exp line (confirm fina_indicator coverage)"),
    "default risk":           (F_PARTIAL, "lev",   "no credit/bond data — leverage proxy only"),
    "short sale constraints": (F_NO,      "",      "A-share shorting heavily restricted + no short-interest data"),
    "optionrisk":             (F_NO,      "",      "no equity-options data ingested"),
    "info proxy":             (F_PARTIAL, "",      "case-by-case — review the definition"),
    "other":                  (F_PARTIAL, "",      "case-by-case — review the definition"),
}

# Small, HIGH-CONFIDENCE dup map: OSAP acronym -> an existing catalog factor we
# are confident is the same concept. Kept deliberately short; everything else
# is left to the category-coverage heuristic for human confirmation.
KNOWN_DUP: dict[str, str] = {
    "Size":          "size_ln_mcap",
    "Mom12m":        "mom_return_250d",
    "Mom6m":         "mom_return_120d",
    "Mom12mOffSeason": "mom_return_250d",
    "STreversal":    "rev_return_20d",
    "BM":            "val_bp",
    "BMdec":         "val_bp",
    "EarningsYield": "val_ep_ttm",
    "EP":            "val_ep_ttm",
    "SP":            "val_sp_ttm",
    "CF":            "val_cftp",
    "Illiquidity":   "liq_amihud_20d",
    "BidAskSpread":  "liq_spread_proxy_20d",
    "Accruals":      "qual_accruals",
    "RealizedVol":   "risk_vol_20d",
    "ReturnSkew":    "risk_skew_60d",
    "DivYield":      "val_div_yield",
}
# NOTE (verified against the live catalog 2026-06-08): the system has NO CAPM
# market beta, NO idiosyncratic/residual vol, NO total-asset-growth, NO
# long-term (3-5yr) reversal factor — so Beta / IdioVol3F / AssetGrowth /
# LRreversal are genuine gaps and are deliberately NOT marked DUP.

N_DUP, N_REVIEW, N_NOVEL = "DUP", "REVIEW", "LIKELY_NOVEL"
GOOD_REPRO = {"1_good", "2_fair"}

UNIVERSE_DEFAULT = "csi_all"
BENCHMARK_DEFAULT = "000905.SH"  # CSI500, mirrors the repo hypothesis template


def _load_catalog_prefix_counts() -> dict[str, int]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from src.alpha_research.factor_library.catalog import (
            get_factor_catalog, get_composite_defs, get_industry_relative_defs)
        names = list(get_factor_catalog(include_new_data=True).keys())
        for fn in (get_composite_defs, get_industry_relative_defs):
            try:
                r = fn()
                names += list(r.keys()) if isinstance(r, dict) else [
                    (c.get("name") if isinstance(c, dict) else c) for c in r]
            except Exception:  # noqa: BLE001
                pass
    counts: dict[str, int] = {}
    for n in names:
        if not n:
            continue
        counts[n.split("_")[0]] = counts.get(n.split("_")[0], 0) + 1
    return counts


def _nan_to_none(v):
    """JSON has no NaN; pandas coerces None->NaN in float cols. Restore None."""
    import math
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def _split_camel(s: str) -> str:
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", str(s))
    s = re.sub(r"(?<=[A-Za-z])(?=[0-9])", " ", s)
    return s.replace("_", " ").strip()


def _classify(row, prefix_counts: dict[str, int]) -> dict:
    cat = str(row.get("Cat.Economic", "")).strip().lower()
    feas, prefix, data_need = FEASIBILITY_MAP.get(cat, (F_PARTIAL, "", "unmapped category — review"))
    acro = str(row.get("Acronym", ""))
    # Novelty heuristic.
    if acro in KNOWN_DUP:
        novelty, dup_match = N_DUP, KNOWN_DUP[acro]
    else:
        cov = prefix_counts.get(prefix, 0) if prefix else 0
        if feas == F_NO:
            novelty, dup_match = N_NOVEL, ""          # no data anyway; "novel" moot
        elif feas == F_PARTIAL:
            novelty, dup_match = N_NOVEL, ""          # categories we barely cover
        elif cov >= 12:
            novelty, dup_match = N_REVIEW, f"{prefix}_* ({cov} factors) — verify variant"
        elif cov >= 1:
            novelty, dup_match = N_REVIEW, f"{prefix}_* ({cov} factors)"
        else:
            novelty, dup_match = N_NOVEL, ""
    return {"feasibility": feas, "our_prefix": prefix, "data_need": data_need,
            "novelty": novelty, "dup_match": dup_match}


def _rank_key(rec: dict) -> tuple:
    feas_rank = {F_BUILD: 2, F_PARTIAL: 1, F_NO: 0}[rec["feasibility"]]
    nov_rank = {N_NOVEL: 2, N_REVIEW: 1, N_DUP: 0}[rec["novelty"]]
    return (feas_rank, nov_rank, rec["cites"] or 0)


def _build_stub(rec: dict, today: str) -> dict:
    acro = rec["acronym"]
    direction = "higher" if rec["sign"] >= 0 else "lower"
    concept = _split_camel(rec["longdesc"] or acro)
    proposed = f"osap_{acro.lower()}_ashare"
    thesis = (f"In A-shares, higher {concept} predicts {direction} cross-sectional "
              f"forward returns (US predictor '{acro}', {rec['authors']} {rec['year']}, "
              f"{rec['journal']}). Test whether this published US anomaly ports to A-shares.")
    mechanism = (f"OSAP economic category: {rec['cat_economic']}. Proposed A-share build: "
                 f"{rec['data_need']} -> '{proposed}'. Definition (US): {rec['detailed'][:280]}")
    # 5d for short-horizon, else monthly (20d).
    rebal = "5d" if rec["cat_economic"] in {"short-term reversal", "informed trading", "earnings event"} else "20d"
    return {
        "hypothesis": {
            "hypothesis_id": f"hyp_osap_{acro.lower()}_{today}_001",
            "thesis_statement": thesis,
            "mechanism": mechanism,
            "source": {
                "source_type": "academic_paper",
                "identifier": f"OSAP:{acro}",
                "title": str(rec["longdesc"] or acro),
                "authors": [a.strip() for a in re.split(r",| and ", str(rec["authors"])) if a.strip()],
                "url": "",
                "publication_date": str(rec["year"]),
                "publisher": str(rec["journal"]),
            },
            "factor_refs": [{"object_type": "composite_factor", "object_name": proposed}],
            "factor_yaml_hashes": [],
            "universe": UNIVERSE_DEFAULT,
            "benchmark": BENCHMARK_DEFAULT,
            "time_split": {
                "is_start": "2015-01-01", "is_end": "2021-12-31",
                "oos_start": "2022-01-01", "oos_end": "2024-12-31",
                "walk_forward_config": {"train_years": 3, "validation_years": 1,
                                        "test_years": 1, "step_years": 1},
            },
            "rebalance_frequency": rebal,
            "neutralization": ["size", "industry"],
            "expected_sign": int(1 if rec["sign"] >= 0 else -1),
            # INTENTIONALLY NULL — your A-share prediction, not the US estimate.
            "expected_effect": None,
            "expected_decay_horizon_days": 20,
            "success_criteria": {
                "min_rank_icir": 0.025, "min_deflated_sharpe": 0.6,
                "min_cost_adjusted_sharpe": 0.4, "max_drawdown": 0.35,
                "max_annual_turnover": 4.0, "min_monotonicity_pvalue": 0.10,
                "max_correlation_to_approved": 0.80, "effect_size_must_be_in_ci": True,
                "custom_rules": [],
            },
            "pre_registered_concerns": {
                "most_likely_failure_mode": f"[DRAFT] The US '{acro}' effect may not survive A-share "
                    f"microstructure (T+1, limit boards, retail-dominated flow) or may be subsumed by "
                    f"existing {rec['our_prefix'] or 'catalog'} factors after neutralization.",
                "weakest_assumption": "[DRAFT] That the US accounting/price construction maps faithfully "
                    "to Tushare A-share fields without definitional drift.",
                "what_would_falsify_this": "[DRAFT] Sealed-OOS rank-ICIR below the committed band, or hard "
                    "rules failing after realistic costs.",
                "priors_on_cost_sensitivity": "[DRAFT] Review turnover at the chosen rebalance before committing.",
            },
            "pre_registered_at": "",
            "registered_by": "",
        },
        # Ignored by hypothesis_cli.py (it reads payload['hypothesis']). Review-only.
        "_draft_review": {
            "GENERATED_BY": "triage_osap_to_ashare.py — DRAFT, not registerable as-is",
            "feasibility": rec["feasibility"],
            "data_need": rec["data_need"],
            "novelty_heuristic": rec["novelty"],
            "dup_match_or_category": rec["dup_match"],
            "us_evidence_context_only": {
                "monthly_ls_return_pct": _nan_to_none(rec["return_us"]),
                "t_stat": _nan_to_none(rec["tstat_us"]),
                "gscholar_cites": rec["cites"], "reproduction_quality": rec["repro"],
                "us_sample": f"{rec['sample_start']}-{rec['sample_end']}",
            },
            "proposed_factor_name": f"osap_{acro.lower()}_ashare",
            "todo_before_registering": [
                f"Implement factor 'osap_{acro.lower()}_ashare' in factor_library "
                f"(map US definition -> A-share Tushare/Qlib fields; PIT-safe Ref(...,1)).",
                "CONFIRM not a duplicate of existing catalog factors in category "
                f"'{rec['our_prefix']}' (heuristic flag = {rec['novelty']}).",
                "SET expected_effect = YOUR A-share prediction (point + CI + horizon). "
                "Do NOT copy us_evidence_context_only above.",
                "CONFIRM the OOS window is unburned for this design before registering.",
                "Then: hypothesis_cli.py register --file <this> --profile-id factor_screening",
            ],
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Triage OSAP predictors into A-share hypothesis stubs.")
    ap.add_argument("--top-stubs", type=int, default=15, help="How many top novel+buildable stubs to emit.")
    ap.add_argument("--dry-run", action="store_true", help="Compute + report, but write no files.")
    args = ap.parse_args()

    import pandas as pd
    if not OSAP_STORE.exists():
        log.error("OSAP store missing: %s — run fetch_osap_signaldoc.py first.", OSAP_STORE)
        return 1
    df = pd.read_parquet(OSAP_STORE)
    pred = df[df["Cat.Signal"] == "Predictor"].copy()
    log.info("loaded %d OSAP predictors", len(pred))
    prefix_counts = _load_catalog_prefix_counts()
    log.info("live catalog category coverage: %s", prefix_counts)

    recs = []
    for _, row in pred.iterrows():
        cls = _classify(row, prefix_counts)
        cites = pd.to_numeric(row.get("GScholarCites202509"), errors="coerce")
        recs.append({
            "acronym": str(row.get("Acronym", "")),
            "sign": float(row.get("Sign")) if pd.notna(row.get("Sign")) else 1.0,
            "cat_economic": str(row.get("Cat.Economic", "")).strip().lower(),
            "authors": str(row.get("Authors", "")), "year": str(row.get("Year", "")),
            "journal": str(row.get("Journal", "")),
            "longdesc": str(row.get("LongDescription", "")),
            "detailed": str(row.get("Detailed Definition", "")),
            "cites": int(cites) if pd.notna(cites) else 0,
            "repro": str(row.get("Signal Rep Quality", "")),
            "return_us": (None if pd.isna(row.get("Return")) else float(row.get("Return"))),
            "tstat_us": (None if pd.isna(row.get("T-Stat")) else float(row.get("T-Stat"))),
            "sample_start": str(row.get("SampleStartYear", "")), "sample_end": str(row.get("SampleEndYear", "")),
            **cls,
        })
    recs.sort(key=_rank_key, reverse=True)
    out = pd.DataFrame(recs)

    # Summary matrix.
    matrix = out.pivot_table(index="feasibility", columns="novelty", values="acronym",
                             aggfunc="count", fill_value=0)
    print("\n== Triage matrix (feasibility x novelty), 212 predictors ==")
    print(matrix.to_string())

    clean = out[out["repro"].isin(GOOD_REPRO)]
    shortlist = clean[(clean["feasibility"] == F_BUILD) & (clean["novelty"].isin([N_NOVEL, N_REVIEW]))]
    print(f"\n== Top buildable+non-dup candidates (clean repro): {len(shortlist)} ==\n")
    for _, r in shortlist.head(args.top_stubs).iterrows():
        print(f"  {r['acronym']:<20} {('+' if r['sign']>=0 else '-')} | {r['cites']:>6} cites | "
              f"{r['novelty']:<12} | {r['cat_economic']:<18} | {r['data_need'][:34]}")

    if args.dry_run:
        log.info("DRY RUN — no files written.")
        return 0

    TRIAGE_DIR.mkdir(parents=True, exist_ok=True)
    out.to_parquet(TRIAGE_DIR / "osap_ashare_triage.parquet", index=False)

    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    STUB_DIR.mkdir(parents=True, exist_ok=True)
    stub_targets = shortlist.head(args.top_stubs)
    emitted = []
    for _, r in stub_targets.iterrows():
        stub = _build_stub(r.to_dict(), today)
        p = STUB_DIR / f"hyp_osap_{r['acronym'].lower()}.json"
        p.write_text(json.dumps(stub, indent=2, ensure_ascii=False), encoding="utf-8")
        emitted.append(r["acronym"])

    def _matrix_to_md(m) -> str:
        cols = list(m.columns)
        head = "| feasibility \\ novelty | " + " | ".join(map(str, cols)) + " |"
        sep = "|" + "---|" * (len(cols) + 1)
        rows = ["| " + str(idx) + " | " + " | ".join(str(m.loc[idx, c]) for c in cols) + " |"
                for idx in m.index]
        return "\n".join([head, sep, *rows])

    # Markdown report.
    md = ["# OSAP → A-share triage", "",
          f"*Generated {datetime.now(timezone.utc):%Y-%m-%d} from osap_signaldoc.parquet (212 predictors).*",
          "", "Heuristic triage — **novelty/dup flags need human confirmation**. Stubs under `stubs/` are "
          "DRAFTS: not registerable until you implement the factor, set `expected_effect`, and confirm an "
          "unburned OOS window.", "", "## Summary matrix (feasibility × novelty)", "",
          _matrix_to_md(matrix), "",
          f"## Top {len(stub_targets)} buildable, non-dup candidates (clean reproduction)", "",
          "| Acronym | Sign | Cites | Novelty | OSAP category | A-share data need | Stub |",
          "|---|---|---|---|---|---|---|"]
    for _, r in stub_targets.iterrows():
        md.append(f"| {r['acronym']} | {'+' if r['sign']>=0 else '−'} | {r['cites']} | {r['novelty']} | "
                  f"{r['cat_economic']} | {r['data_need']} | `stubs/hyp_osap_{r['acronym'].lower()}.json` |")
    md += ["", "## How to use a stub", "",
           "1. Implement the proposed factor in the factor library (US definition → A-share fields, PIT-safe).",
           "2. Open the stub, replace `expected_effect: null` with your A-share prediction.",
           "3. Edit the `[DRAFT]` pre-registered concerns.",
           "4. Confirm the OOS window is unburned, then "
           "`hypothesis_cli.py register --file stubs/<file>.json --profile-id factor_screening`.", ""]
    (TRIAGE_DIR / "osap_ashare_triage.md").write_text("\n".join(md), encoding="utf-8")

    log.info("wrote triage parquet + md; emitted %d draft stubs: %s",
             len(emitted), ", ".join(emitted))
    return 0


if __name__ == "__main__":
    sys.exit(main())
