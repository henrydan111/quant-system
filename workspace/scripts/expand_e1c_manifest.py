# SCRIPT_STATUS: ACTIVE — one-time E1c manifest correction: chart-28 expansion (factor-level, no operator)
"""Correct the CICC price-volume v2 manifest for the E1c liquidity wave: replace the 3 chart-28
SUBTYPE-TEMPLATE rows (liq_amihud / liq_shortcut / liq_vstd) with 19 FACTOR-LEVEL rows, one per
registered E1c ``liq_*`` catalog factor, each carrying ``catalog_factor_id`` so the P-GATE resolves
it exactly. Corrections fold in the GPT-approved E1c factor logic:
  * NO ``required_operators`` — all E1c factors are inline arithmetic (Mean/Std/Abs/If), no custom
    operator (drops the stale ``kbar_shortcut`` placeholder on the shortcut row).
  * Records the shortcut adjusted-OHLC basis (GPT B4) as a comment.

Re-pins ``manifest_sha``. Pre-registration correction — no E1c OOS spent. Dry-run by default; ``--write``.
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
E1C_PREFIXES = ("liq_turn_avg_120", "liq_turn_std", "liq_vstd", "liq_amihud_avg", "liq_amihud_std", "liq_shortcut")
NOTE = ('  # E1c liquidity (图表28): 19 factor-level rows (2 dedups skipped: liq_turn_avg_{20,60}=='
        'liq_turnover). Inline arithmetic, NO custom operator. shortcut price_basis=adjusted_OHLC '
        '(GPT B4: split-robust project convention; raw-K-line vendor basis not truth-parity-certified). '
        'Guarded denominators (NaN not inf on amount<=0 / return-std<=0).')


def _row_line(fid: str) -> str:
    return (f'  - {{factor_name_original: {fid}, handbook_id: F_{fid}, chart_id: "28", '
            f'replication_tier_planned: formula_equivalent_pending, '
            f'truth_table_label_end: "2022-07-01", oos_eligibility: short_window, '
            f'primary_claim_universe: univ_all, catalog_factor_id: {fid}}}')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    e1c_ids = sorted(n for n in get_factor_catalog(include_new_data=True)
                     if any(n.startswith(p) for p in E1C_PREFIXES))
    if len(e1c_ids) != 19:
        raise SystemExit(f"expected 19 E1c liq factors, found {len(e1c_ids)} — refuse (set drift)")

    text = MANIFEST.read_text(encoding="utf-8")
    lines = text.splitlines()
    c28 = [i for i, ln in enumerate(lines) if 'chart_id: "28"' in ln]
    if not c28 or max(c28) - min(c28) + 1 != len(c28):
        raise SystemExit(f"chart-28 rows missing/non-contiguous ({c28}) — refuse")
    lo, hi = min(c28), max(c28)
    print(f"replacing {len(c28)} chart-28 template rows (lines {lo+1}-{hi+1}) with {len(e1c_ids)} factor rows + note")

    new_rows = [NOTE] + [_row_line(fid) for fid in e1c_ids]
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
    assert "kbar_shortcut" not in final, "stale kbar_shortcut still present"
    assert "required_operators" not in "\n".join(new_rows), "E1c rows must carry no required_operators"

    if args.write:
        MANIFEST.write_text(final, encoding="utf-8")
        m2 = load_cohort_manifest(str(MANIFEST))
        miss = [fid for fid in e1c_ids if m2.row_for(catalog_factor_id=fid) is None]
        if miss:
            raise SystemExit(f"post-write: {len(miss)} unresolvable {miss[:5]}")
        print(f"WROTE {MANIFEST.name}; reload ok, all {len(e1c_ids)} E1c factors resolvable, sha={m2.manifest_sha}")
    else:
        print("dry-run — manifest untouched. Re-run with --write to apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
