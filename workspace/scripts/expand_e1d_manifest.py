# SCRIPT_STATUS: ACTIVE — one-time E1d manifest correction: chart-40 expansion (factor-level, no operator)
"""Correct the CICC price-volume v2 manifest for the E1d price-volume-correlation wave: replace the 3
chart-40 SUBTYPE-TEMPLATE rows (corr_price_turn / corr_ret_turn / corr_ret_turnd, each carrying a stale
``required_operators: [lead_lag_corr]``) with 8 FACTOR-LEVEL rows, one per registered E1d ``corr_*``
catalog factor, each carrying ``catalog_factor_id`` so the P-GATE resolves it exactly. Folds in the
GPT-approved E1d factor logic:
  * NO ``required_operators`` — all E1d factors are inline ``Corr`` + ``Ref`` (no custom operator;
    drops the pre-registered ``lead_lag_corr`` placeholder, exactly as E1c dropped ``kbar_shortcut``).
  * Records the lead_lag_semantics (GPT naming guidance) as a comment.

Re-pins ``manifest_sha``. Pre-registration correction — no E1d OOS spent. Dry-run by default; ``--write``.
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
E1D_PREFIX = "corr_"   # the corr_ namespace is uniquely E1d (no other catalog factor starts with corr_)
NOTE = ('  # E1d 量价相关性 (图表40): 8 factor-level rows (0 dedup). Inline Corr+Ref, NO custom operator '
        '(lead_lag_corr DROPPED). Single 20d window (handbook chart 40 is 1M only). lead_lag_semantics: '
        '_post = price/return POSTerior (t+1) => turnover LEADS; _prior = price/return PRIOR (t-1) => '
        'price/return LEADS (lead realized by shifting the LEADING series back, never a forward Ref). '
        'price_basis: adjusted_close LEVEL for corr_price_turn* (split-robust), adjusted DAILY_RET + raw '
        '$turnover_rate elsewhere.')


def _row_line(fid: str) -> str:
    return (f'  - {{factor_name_original: {fid}, handbook_id: F_{fid}, chart_id: "40", '
            f'replication_tier_planned: formula_equivalent_pending, '
            f'truth_table_label_end: "2022-07-01", oos_eligibility: short_window, '
            f'primary_claim_universe: univ_all, catalog_factor_id: {fid}}}')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    e1d_ids = sorted(n for n in get_factor_catalog(include_new_data=True) if n.startswith(E1D_PREFIX))
    if len(e1d_ids) != 8:
        raise SystemExit(f"expected 8 E1d corr_ factors, found {len(e1d_ids)} — refuse (set drift)")

    text = MANIFEST.read_text(encoding="utf-8")
    lines = text.splitlines()
    c40 = [i for i, ln in enumerate(lines) if 'chart_id: "40"' in ln]
    if not c40 or max(c40) - min(c40) + 1 != len(c40):
        raise SystemExit(f"chart-40 rows missing/non-contiguous ({c40}) — refuse")
    lo, hi = min(c40), max(c40)
    print(f"replacing {len(c40)} chart-40 template rows (lines {lo+1}-{hi+1}) with {len(e1d_ids)} factor rows + note")

    new_rows = [NOTE] + [_row_line(fid) for fid in e1d_ids]
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
    assert "required_operators: [lead_lag_corr]" not in final, "stale lead_lag_corr binding still present"
    assert "required_operators" not in "\n".join(new_rows), "E1d rows must carry no required_operators"

    if args.write:
        MANIFEST.write_text(final, encoding="utf-8")
        m2 = load_cohort_manifest(str(MANIFEST))
        miss = [fid for fid in e1d_ids if m2.row_for(catalog_factor_id=fid) is None]
        if miss:
            raise SystemExit(f"post-write: {len(miss)} unresolvable {miss[:5]}")
        print(f"WROTE {MANIFEST.name}; reload ok, all {len(e1d_ids)} E1d factors resolvable, sha={m2.manifest_sha}")
    else:
        print("dry-run — manifest untouched. Re-run with --write to apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
