# SCRIPT_STATUS: ACTIVE — one-time E1b manifest correction (GPT IS-gate review B1): chart-16 expansion
"""Correct the CICC price-volume v2 manifest for the E1b volatility wave (GPT IS-gate review,
blocking finding 1): replace the 7 chart-16 SUBTYPE-TEMPLATE rows with 36 FACTOR-LEVEL rows, one per
registered ``vol_*`` catalog factor, each carrying ``catalog_factor_id`` so the P-GATE resolves it
exactly. Two content corrections fold in the approved E1b factor logic:
  * DROP ``shadow_line`` — shadow lines are inline built-in ``Greater``/``Less`` (no custom operator).
  * ``required_operators: [sign_conditional_std]`` ONLY on the ``vol_(down|up)_std_*`` rows.

Re-pins ``manifest_sha`` (the row-set + required_operators change the content hash; catalog_factor_id is
sha-excluded). Pre-registration correction — no E1b OOS spent. Dry-run by default (prints the new sha +
row count); ``--write`` applies.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from src.alpha_research.factor_library import get_factor_catalog  # noqa: E402

MANIFEST = PROJECT_ROOT / "config" / "replication" / "cicc_price_volume_cohort_v2.yaml"
NEEDS_SIGN_STD = re.compile(r"^vol_(down|up)_std_\d+d$")   # only these need the custom operator


def _row_line(fid: str) -> str:
    ops = " required_operators: [sign_conditional_std]," if NEEDS_SIGN_STD.match(fid) else ""
    return (f'  - {{factor_name_original: {fid}, handbook_id: F_{fid}, chart_id: "16", '
            f'replication_tier_planned: formula_equivalent_pending,{ops} '
            f'truth_table_label_end: "2022-07-01", oos_eligibility: short_window, '
            f'primary_claim_universe: univ_all, catalog_factor_id: {fid}}}')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="apply (default: dry-run)")
    args = ap.parse_args()

    vol_ids = sorted(n for n in get_factor_catalog(include_new_data=True) if n.startswith("vol_"))
    if len(vol_ids) != 36:
        raise SystemExit(f"expected 36 vol_ catalog factors, found {len(vol_ids)} — refuse (set drift)")

    text = MANIFEST.read_text(encoding="utf-8")
    lines = text.splitlines()
    chart16_idx = [i for i, ln in enumerate(lines) if 'chart_id: "16"' in ln]
    if not chart16_idx:
        raise SystemExit("no chart_id:\"16\" rows found in manifest")
    lo, hi = min(chart16_idx), max(chart16_idx)
    # the chart-16 block must be contiguous (the 7 template rows)
    if hi - lo + 1 != len(chart16_idx):
        raise SystemExit(f"chart-16 rows not contiguous ({chart16_idx}) — refuse")
    print(f"replacing {len(chart16_idx)} chart-16 template rows (lines {lo+1}-{hi+1}) with {len(vol_ids)} factor rows")

    new_rows = [_row_line(fid) for fid in vol_ids]
    new_lines = lines[:lo] + new_rows + lines[hi + 1:]
    new_text = "\n".join(new_lines) + ("\n" if text.endswith("\n") else "")

    # recompute the sha by loading the corrected content through the real loader
    import tempfile
    from src.alpha_research.factor_registry.replication_governance import load_cohort_manifest
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as tf:
        # blank the manifest_sha so the loader does not raise on mismatch while we recompute
        tf.write(re.sub(r'manifest_sha: "[0-9a-f]+"', 'manifest_sha: ""', new_text))
        tmp_path = tf.name
    m = load_cohort_manifest(tmp_path, verify_sha=False) if "verify_sha" in load_cohort_manifest.__code__.co_varnames else load_cohort_manifest(tmp_path)
    new_sha = m.manifest_sha
    Path(tmp_path).unlink(missing_ok=True)
    old_sha = re.search(r'manifest_sha: "([0-9a-f]+)"', text).group(1)
    final_text = re.sub(r'manifest_sha: "[0-9a-f]+"', f'manifest_sha: "{new_sha}"', new_text, count=1)
    print(f"manifest_sha: {old_sha} -> {new_sha}")
    # sanity: no shadow_line remains; sign_conditional_std only on (down|up)_std
    assert "shadow_line" not in final_text, "shadow_line still present"
    sl_rows = sum(1 for fid in vol_ids if NEEDS_SIGN_STD.match(fid))
    print(f"sign_conditional_std rows={sl_rows} (want 6: down/up_std × 3) | shadow_line removed=True | total factor rows={len(vol_ids)}")

    if args.write:
        MANIFEST.write_text(final_text, encoding="utf-8")
        # verify it reloads + the gate can resolve every factor
        m2 = load_cohort_manifest(str(MANIFEST))
        miss = [fid for fid in vol_ids if m2.row_for(catalog_factor_id=fid) is None]
        if miss:
            raise SystemExit(f"post-write: {len(miss)} factors unresolvable {miss[:5]} — investigate")
        print(f"WROTE {MANIFEST.name}; reload ok, all {len(vol_ids)} factors resolvable, sha={m2.manifest_sha}")
    else:
        print("dry-run — manifest untouched. Re-run with --write to apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
