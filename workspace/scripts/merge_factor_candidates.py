# ──────────────────────────────────────────────────────────────────────
# PR 7 of 2026-05-26 freeze plan — SCRIPT_STATUS header block.
# script_status: historical_investigation
# formal_research_allowed: false
# deployment_target: joinquant_attribution_only
# requires_provider_manifest: false
# requires_preload_strict: false
# pr2_audit_class: C
# notes: |
#   Read-only merge of the Claude-generated candidate CSV and the GPT 5.5 Pro
#   review CSV into one combined, deduplicated, re-stamped artifact. Adds a
#   `source` column (claude_v2 / gpt_review). Drops the GPT rows that duplicate
#   a Claude row by name. Re-resolves registry status from the live registry so
#   the merged file is internally consistent. Validates every row against the
#   raw materialized field set + PIT parser before writing. No other mutation.
# ──────────────────────────────────────────────────────────────────────
"""Merge Claude + GPT factor-candidate CSVs into one reviewed artifact.

Output: workspace/research/factor_expansion/factor_candidates_merged.csv
"""

from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data_infra.field_registry import extract_qlib_fields, load_field_registry
from tests.alpha_research.test_factor_library_pit_safety import (
    find_unwrapped_field_references,
)

CLAUDE_CSV = PROJECT_ROOT / "workspace/research/factor_expansion/factor_candidates.csv"
GPT_CSV = PROJECT_ROOT / "Knowledge/factor_expansion_gpt_review_new_candidates.csv"
GPT_R3_CSV = PROJECT_ROOT / "Knowledge/factor_candidates_round3_additions_corrections.csv"
OUT_CSV = PROJECT_ROOT / "workspace/research/factor_expansion/factor_candidates_merged.csv"
FEATURES_DIR = PROJECT_ROOT / "data" / "qlib_data" / "features"
FORMAL_STAGE = "formal_validation"

# Rows superseded by the Round-3 fixes (now baked into the regenerated claude_v2
# set under corrected names). The merge skips them so the buggy originals do not
# re-enter from the Round-2 GPT CSV.
#   mom_continuous_info_252d  -> replaced by mom_continuous_info_252d_dir (sign fix)
# The GPT Round-3 CSV rows whose names already match a claude_v2 row
# (qual_gross_profitability_ttm, margin_net_buy_ratio_20d, flow_inst_retail_*)
# dedup automatically by name; the *_unitfix/*_scaled aliases are skipped as dups.
SUPERSEDED_NAMES = {
    # Round-3 fix: Abs() on the up-minus-down count (sign bug).
    "mom_continuous_info_252d",
    # Round-5 fix: `0 - IdxMax(...)` is sign-inverted under Qlib's IdxMax
    # convention (1-indexed from oldest). Replaced by
    # tech_high_breakout_freshness_250d (claude_v2 row).
    "tech_high_breakout_age_250d",
    # Round-5 / F1 lint: original Count(cond, N) is silently degenerate.
    # Replaced by Sum(If(...,1,0),N) versions under the same name in claude_v2.
    # NOTE: the Round-2 GPT CSV rows are superseded; the claude_v2 corrected
    # rows publish under the SAME canonical names. We do NOT add to
    # SUPERSEDED_NAMES because the claude_v2 same-name row loads FIRST and the
    # gpt_review row dedup-skips on name. This entry is documentation-only.
}
# GPT Round-3 alias rows that duplicate a canonical claude_v2 row already carrying
# the same fix — skip to avoid near-duplicate names in the merged set.
R3_ALIAS_SKIP = {
    "margin_net_buy_ratio_20d_scaled",      # == margin_net_buy_ratio_20d (fixed)
    "flow_elg_net_pct_20d_unitfix",         # == flow_elg_net_pct_20d (fixed)
    "flow_inst_retail_divergence_20d_unitfix",  # == flow_inst_retail_divergence_20d
}

COLS = [
    "name", "category", "qlib_expression", "fields_used", "price_basis",
    "registry_status", "formal_eligible", "expected_sign",
    "expected_decay_days", "neutralization", "rationale", "source",
]


def load_raw_stems() -> set[str]:
    import re
    best_dir, best = None, -1
    for child in FEATURES_DIR.iterdir():
        if child.is_dir():
            n = sum(1 for _ in child.glob("*.bin"))
            if n > best:
                best, best_dir = n, child
    stems = set()
    for binf in best_dir.glob("*.bin"):
        name = binf.name
        name = name[:-8] if name.endswith(".day.bin") else name[:-4]
        stems.add(re.sub(r"\.[0-9]+$", "", name))
    return stems


def _resolve(expr: str, registry) -> tuple[str, str, str]:
    fields = extract_qlib_fields(expr)
    statuses, eligible = set(), True
    for f in fields:
        res = registry.resolve_field(f, FORMAL_STAGE)
        statuses.add(res.status_id or "unknown_field")
        if not res.allowed:
            eligible = False
    if "unknown_field" in statuses:
        status = "unknown_field"
    elif "quarantine" in statuses:
        status = "quarantine"
    elif "pending_review" in statuses:
        status = "pending_review"
    elif statuses == {"approved"}:
        status = "approved"
    else:
        status = ";".join(sorted(statuses))
    return ";".join(fields), status, ("yes" if eligible else "no")


def main() -> int:
    raw_stems = load_raw_stems()
    registry = load_field_registry(
        PROJECT_ROOT / "config" / "field_registry" / "field_status.yaml"
    )

    merged: dict[str, dict] = {}
    counts = Counter()
    for path, source in [
        (CLAUDE_CSV, "claude_v2"),
        (GPT_CSV, "gpt_review"),
        (GPT_R3_CSV, "gpt_round3"),
    ]:
        for r in csv.DictReader(open(path, encoding="utf-8")):
            name = r["name"]
            if name in SUPERSEDED_NAMES:
                print(f"  superseded: '{name}' from {source} — skipped (Round-3 fix)")
                continue
            if name in R3_ALIAS_SKIP:
                print(f"  alias-skip: '{name}' from {source} — canonical row already carries the fix")
                continue
            if name in merged:
                print(f"  dedup: '{name}' from {source} duplicates {merged[name]['source']} — skipped")
                continue
            expr = r["qlib_expression"]
            # Authoritative validation.
            tokens = [t[1:] for t in extract_qlib_fields(expr)]
            missing = [t for t in tokens if t not in raw_stems]
            if missing:
                print(f"  REJECT '{name}' ({source}): non-materialized fields {missing}")
                continue
            if find_unwrapped_field_references(expr):
                print(f"  REJECT '{name}' ({source}): unwrapped $field (PIT-unsafe)")
                continue
            fields_used, status, eligible = _resolve(expr, registry)
            merged[name] = {
                "name": name,
                "category": r.get("category", ""),
                "qlib_expression": expr,
                "fields_used": fields_used,
                "price_basis": r.get("price_basis", ""),
                "registry_status": status,
                "formal_eligible": eligible,
                "expected_sign": r.get("expected_sign", ""),
                "expected_decay_days": r.get("expected_decay_days", ""),
                "neutralization": r.get("neutralization", ""),
                "rationale": r.get("rationale", ""),
                "source": source,
            }
            counts[source] += 1

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        for row in merged.values():
            w.writerow(row)

    print(f"\nMerged {len(merged)} rows -> {OUT_CSV}")
    print(f"  by source: {dict(counts)}")
    print(f"  by status: {dict(Counter(r['registry_status'] for r in merged.values()))}")
    print(f"  formal-eligible: {sum(1 for r in merged.values() if r['formal_eligible']=='yes')}/{len(merged)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
