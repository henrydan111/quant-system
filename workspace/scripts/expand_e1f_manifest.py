# SCRIPT_STATUS: ACTIVE — one-time E1f manifest correction: chart-64 expansion (factor-level, no operator)
"""Correct the CICC price-volume v2 manifest for the E1f capital-flow wave: replace the 4 chart-64
SUBTYPE-TEMPLATE rows (flow_act_buy_prop / flow_shift_dist [stale required_operators: shift_distance_ratio] /
flow_inflow_open / flow_inflow_close [proxy_approx]) with 9 FACTOR-LEVEL rows, one per registered E1f
``flow_act_buy_*`` catalog factor, each carrying ``catalog_factor_id`` so the P-GATE resolves it exactly.
Folds in the GPT-approved path-A factor logic:
  * NO ``required_operators`` — all E1f factors are inline ``Sum``/``Ref``/division (drops the stale
    ``shift_distance_ratio`` placeholder, exactly as E1c/E1d dropped theirs).
  * Documents the DEFERRED families (the "总买入含被动" buy family = affine alias/proxy; the 开盘/尾盘
    family = no intraday split) as a comment — those are NOT registered and carry no factor-level row.

Re-pins ``manifest_sha``. Pre-registration correction — no E1f OOS spent. Dry-run by default; ``--write``.
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
E1F_PREFIX = "flow_act_buy_"   # uniquely E1f (the 9 faithful active-family factors)
NOTE = ('  # E1f 资金流 (图表64): 9 FAITHFUL active-family factors (path A). Inline Sum/Ref, NO custom '
        'operator (shift_distance_ratio DROPPED). prop = Sum(net,20)/Sum(amount,20) (ratio-of-sums); '
        'shift_dist = Sum(net,20)/Sum(gross,20) (位移路程比 in [-1,1]); net/gross from moneyflow buy/sell '
        'COMPONENTS, not the opaque $net_mf_amount; guarded NaN-not-inf. DEFERRED (GPT factor-logic review '
        '2026-06-19): the "总买入含被动" buy family (buy_shift_dist = rank-identical affine alias of '
        'act_buy_shift_dist, Pearson 1.0; total-buy needs passive flow, unavailable) + the 开盘/尾盘 family '
        '(no intraday split in daily moneyflow) — neither registered, no factor-level row.')


def _row_line(fid: str) -> str:
    return (f'  - {{factor_name_original: {fid}, handbook_id: F_{fid}, chart_id: "64", '
            f'replication_tier_planned: formula_equivalent_pending, '
            f'truth_table_label_end: "2022-07-01", oos_eligibility: short_window, '
            f'primary_claim_universe: univ_all, catalog_factor_id: {fid}}}')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    e1f_ids = sorted(n for n in get_factor_catalog(include_new_data=True) if n.startswith(E1F_PREFIX))
    if len(e1f_ids) != 9:
        raise SystemExit(f"expected 9 E1f flow_act_buy_ factors, found {len(e1f_ids)} — refuse (set drift)")

    text = MANIFEST.read_text(encoding="utf-8")
    lines = text.splitlines()
    c64 = [i for i, ln in enumerate(lines) if 'chart_id: "64"' in ln]
    if not c64 or max(c64) - min(c64) + 1 != len(c64):
        raise SystemExit(f"chart-64 rows missing/non-contiguous ({c64}) — refuse")
    lo, hi = min(c64), max(c64)
    print(f"replacing {len(c64)} chart-64 template rows (lines {lo+1}-{hi+1}) with {len(e1f_ids)} factor rows + note")

    new_rows = [NOTE] + [_row_line(fid) for fid in e1f_ids]
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
    # NOTE: shift_distance_ratio is ALSO used by chart-76 (north_inflow_shift_dist, E1g) — a global
    # absence check would wrongly fire. The chart-64 binding is dropped because the replacement rows carry
    # no required_operators (asserted next); the chart-76 reference is intentionally preserved.
    assert "required_operators" not in "\n".join(new_rows), "E1f rows must carry no required_operators"
    assert 'required_operators: [shift_distance_ratio]' not in final or \
        final.count('required_operators: [shift_distance_ratio]') == 1, \
        "chart-64 shift_distance_ratio binding not removed (only the chart-76 one should remain)"

    if args.write:
        MANIFEST.write_text(final, encoding="utf-8")
        m2 = load_cohort_manifest(str(MANIFEST))
        miss = [fid for fid in e1f_ids if m2.row_for(catalog_factor_id=fid) is None]
        if miss:
            raise SystemExit(f"post-write: {len(miss)} unresolvable {miss[:5]}")
        print(f"WROTE {MANIFEST.name}; reload ok, all {len(e1f_ids)} E1f factors resolvable, sha={m2.manifest_sha}")
    else:
        print("dry-run — manifest untouched. Re-run with --write to apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
