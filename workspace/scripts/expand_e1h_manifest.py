# SCRIPT_STATUS: ACTIVE — one-time E1h manifest correction: chart-88 expansion + STALE-exclusion fix
"""Correct the CICC price-volume v2 manifest for the E1h margin wave: replace the chart-88 SUBTYPE-TEMPLATE
rows (incl. the STALE `margin_sell_sec_prop` not_replicable row that cites a no-longer-applicable
`rqye/rqchl` quarantine) with 5 FACTOR-LEVEL rows, one per registered E1h catalog factor, each carrying
`catalog_factor_id`. Folds in the GPT-approved factor logic:
  * the 融券 side IS now replicable ($rzye/$rqye/$rzmre/$rqmcl approved 2026-06-04; only repayment
    $rzche/$rqchl quarantined) — the stale not_replicable exclusion is removed.
  * NO `required_operators` (inline). Dedup (margin_money_bal_prop≡margin_balance_pct) + deferred
    (margin_sec_avg ambiguous) + repayment-blocked (net_margin_*_shift_dist) documented in a comment.

Re-pins `manifest_sha`. Pre-registration correction. Dry-run by default; `--write`.
"""
from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from src.alpha_research.factor_library import get_factor_catalog  # noqa: E402
from src.alpha_research.factor_registry.replication_governance import load_cohort_manifest  # noqa: E402

MANIFEST = PROJECT_ROOT / "config" / "replication" / "cicc_price_volume_cohort_v2.yaml"
E1H_IDS = ["margin_buy_money_prop_20d", "margin_money_bal_growth_20d", "margin_sell_sec_prop_20d",
           "margin_sec_bal_prop", "margin_sec_bal_growth_20d"]
NOTE = ('  # E1h 融资融券 (图表88): 5 faithful factor-level rows. STALE-EXCLUSION FIX — the 融券 side is now '
        'replicable ($rzye/$rqye/$rzmre/$rqmcl approved 2026-06-04; only repayment $rzche/$rqchl quarantined). '
        'All MASKED to the margin-eligible sub-universe. Inline, NO operator. formula_equivalent_pending '
        '(unit-mixed 元/千元/shares → rank-valid, not a true proportion). DEDUP: margin_money_bal_prop≡existing '
        'margin_balance_pct. DEFERRED: margin_sec_avg (ambiguous handbook formula, avg vs ratio-of-sums). '
        'BLOCKED: net_margin_buy/sell_shift_dist (need quarantined repayment $rzche/$rqchl).')


def _row_line(fid: str) -> str:
    return (f'  - {{factor_name_original: {fid}, handbook_id: F_{fid}, chart_id: "88", '
            f'replication_tier_planned: formula_equivalent_pending, '
            f'truth_table_label_end: "2022-07-01", oos_eligibility: short_window, '
            f'primary_claim_universe: univ_all, catalog_factor_id: {fid}}}')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    cat = set(get_factor_catalog(include_new_data=True))
    miss = [f for f in E1H_IDS if f not in cat]
    if miss:
        raise SystemExit(f"E1h factors not in catalog: {miss} — register them first")

    text = MANIFEST.read_text(encoding="utf-8")
    lines = text.splitlines()
    c88 = [i for i, ln in enumerate(lines) if 'chart_id: "88"' in ln]
    if not c88 or max(c88) - min(c88) + 1 != len(c88):
        raise SystemExit(f"chart-88 rows missing/non-contiguous ({c88}) — refuse")
    lo, hi = min(c88), max(c88)
    print(f"replacing {len(c88)} chart-88 template rows (lines {lo+1}-{hi+1}) with {len(E1H_IDS)} factor rows + note")

    new_rows = [NOTE] + [_row_line(fid) for fid in E1H_IDS]
    new_lines = lines[:lo] + new_rows + lines[hi + 1:]
    new_text = "\n".join(new_lines) + ("\n" if text.endswith("\n") else "")

    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as tf:
        tf.write(re.sub(r'manifest_sha: "[0-9a-f]+"', 'manifest_sha: ""', new_text))
        tmp = tf.name
    new_sha = load_cohort_manifest(tmp).manifest_sha
    Path(tmp).unlink(missing_ok=True)
    old_sha = re.search(r'manifest_sha: "([0-9a-f]+)"', text).group(1)
    final = re.sub(r'manifest_sha: "[0-9a-f]+"', f'manifest_sha: "{new_sha}"', new_text, count=1)
    print(f"manifest_sha: {old_sha} -> {new_sha}")
    assert "required_operators" not in "\n".join(new_rows), "E1h rows must carry no required_operators"
    assert "not_replicable" not in "\n".join(new_rows), "E1h rows must not carry the stale not_replicable"

    if args.write:
        MANIFEST.write_text(final, encoding="utf-8")
        m2 = load_cohort_manifest(str(MANIFEST))
        miss2 = [fid for fid in E1H_IDS if m2.row_for(catalog_factor_id=fid) is None]
        if miss2:
            raise SystemExit(f"post-write: {len(miss2)} unresolvable {miss2[:5]}")
        print(f"WROTE {MANIFEST.name}; reload ok, all {len(E1H_IDS)} E1h factors resolvable, sha={m2.manifest_sha}")
    else:
        print("dry-run — manifest untouched. Re-run with --write to apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
