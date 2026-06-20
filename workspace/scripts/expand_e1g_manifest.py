# SCRIPT_STATUS: ACTIVE — one-time E1g manifest correction: chart-76 expansion (factor-level, no operator)
"""Correct the CICC price-volume v2 manifest for the E1g northbound wave: replace the 3 chart-76
SUBTYPE-TEMPLATE rows (north_hold_prop / north_hold_prefer / north_inflow_shift_dist [stale
required_operators: shift_distance_ratio]) with 4 FACTOR-LEVEL rows, one per registered E1g catalog
factor, each carrying ``catalog_factor_id``. Folds in the GPT-approved path-C factor logic:
  * NO ``required_operators`` — inline Sum/Mean/Delta/Abs/If (drops the stale ``shift_distance_ratio``).
  * Documents the DEFERRED north_hold_prop (dedup -> north_hold_pct) + prefer family (rank-alias /
    cross-sectional) and the issued-share / spent-OOS / short-window caveats as a comment.
Keeps ``oos_eligibility: spent_same_family`` (north family OOS already spent, arXiv D4).

Re-pins ``manifest_sha``. Pre-registration correction. Dry-run by default; ``--write``.
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
E1G_IDS = ["north_hold_prop_st_chg_20d", "north_inflow_shift_dist_20d",
           "north_excess_hold_st_20d", "north_trade_prop_20d"]
NOTE = ('  # E1g 北向资金 (图表76): 4 faithful factor-level rows. Inline, NO custom operator '
        '(shift_distance_ratio DROPPED here; still used by chart-88). VWAP holding-VALUE uses '
        '$north_hold_vol (registered 2026-06-20), NOT a ratio*VWAP proxy. All masked to the held '
        'sub-universe (If($ratio>0)). DEFERRED: north_hold_prop (dedup -> existing north_hold_pct); '
        'the 持仓偏好 prefer family (level = cross-sectional rank-alias of north_hold_pct; st/lt change '
        'need cross-sectional materialization, not Qlib-per-instrument-expressible). CAVEATS: $ratio is '
        '% of ISSUED shares (doc 188, not CICC 流通股本); oos_eligibility spent_same_family (arXiv D4 '
        'sign-flip) -> candidate/resolve-but-label only; short IS window (hk_hold 2017-2020).')


def _row_line(fid: str) -> str:
    return (f'  - {{factor_name_original: {fid}, handbook_id: F_{fid}, chart_id: "76", '
            f'replication_tier_planned: formula_equivalent_pending, '
            f'truth_table_label_end: "2022-07-01", oos_eligibility: spent_same_family, '
            f'primary_claim_universe: univ_all, catalog_factor_id: {fid}}}')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    cat = set(get_factor_catalog(include_new_data=True))
    miss = [f for f in E1G_IDS if f not in cat]
    if miss:
        raise SystemExit(f"E1g factors not in catalog: {miss} — register them first")

    text = MANIFEST.read_text(encoding="utf-8")
    lines = text.splitlines()
    c76 = [i for i, ln in enumerate(lines) if 'chart_id: "76"' in ln]
    if not c76 or max(c76) - min(c76) + 1 != len(c76):
        raise SystemExit(f"chart-76 rows missing/non-contiguous ({c76}) — refuse")
    lo, hi = min(c76), max(c76)
    print(f"replacing {len(c76)} chart-76 template rows (lines {lo+1}-{hi+1}) with {len(E1G_IDS)} factor rows + note")

    new_rows = [NOTE] + [_row_line(fid) for fid in E1G_IDS]
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
    assert "required_operators" not in "\n".join(new_rows), "E1g rows must carry no required_operators"

    if args.write:
        MANIFEST.write_text(final, encoding="utf-8")
        m2 = load_cohort_manifest(str(MANIFEST))
        miss2 = [fid for fid in E1G_IDS if m2.row_for(catalog_factor_id=fid) is None]
        if miss2:
            raise SystemExit(f"post-write: {len(miss2)} unresolvable {miss2[:5]}")
        print(f"WROTE {MANIFEST.name}; reload ok, all {len(E1G_IDS)} E1g factors resolvable, sha={m2.manifest_sha}")
    else:
        print("dry-run — manifest untouched. Re-run with --write to apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
