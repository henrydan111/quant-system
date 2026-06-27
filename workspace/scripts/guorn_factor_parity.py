"""果仁 web-export ↔ LOCAL factor parity comparator (the reusable end-to-end consistency check).

Closes the "compare" half of the 果仁 web-verification flow (GUORN_WEB_FACTOR_VERIFICATION_GUIDE.md):
takes a 果仁 每日选股 export xlsx + a LOCAL qlib expression, joins them at the signal-date lag, and prints
the rung-4 parity battery (median rel-err, within-0.1/1/5%, sign-agreement, Spearman/Pearson, exact-match for
counts, corr-on-non-zero) + a verdict. NON-FORMAL parity diagnostic (not a formal artifact).

WHY a tool (not hand-rolled each time): the prior #18 overstatement came from eyeballing a return instead of
a per-stock value comparison. This makes "does my local factor reproduce 果仁's indicator?" a one-command,
reproducible answer — prove a field by DIRECT value comparison (the #18 lesson).

JOIN: 果仁 exports bare 6-digit codes (603268); local frames are Qlib form (603268_SH). We map 6-digit→Qlib
via the PROVIDER instrument list (robust — no fragile prefix→exchange table; handles 688→SH, BSE .BJ, etc.).
LAG: 果仁 displays each factor as-of the SIGNAL day = T−1 (the trading day before the buy day) for most
indicators (guorn_local_field_mapping.md §0). Default --lag 1. PIT-gated fundamentals gate lag-0 → --lag 0.
UNITS: pass a --local-expr already in 果仁's DISPLAYED unit (e.g. "$total_mv/1e4" for 总市值(亿)), or use
--guorn-scale to lift 果仁 onto the local unit. See the mapping doc §0 unit table.

Examples:
  # 评级机构数 (count) vs the published report_rc field, at the signal-date lag
  guorn_factor_parity.py --xlsx Knowledge/果仁验证因子/果仁_20251231_仅有ST_排名-评级机构数.xlsx \
      --date 2025-12-31 --local-expr '$report_rc__n_active_orgs' --guorn-col 评级机构数 --kind count
  # 总市值(亿) vs $total_mv (万元) → divide by 1e4 to land on 亿
  guorn_factor_parity.py --xlsx Knowledge/果仁验证因子/果仁_20251231_仅有ST_排名-总市值降序.xlsx \
      --date 2025-12-31 --local-expr '$total_mv/1e4' --guorn-col '总市值(亿)'
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "workspace" / "scripts"))
sys.stdout.reconfigure(encoding="utf-8")
PROVIDER_URI = str(ROOT / "data" / "qlib_data")
EPS = 1e-9


# ----------------------------------------------------------------------------- 果仁 export side
def _code6(v) -> str | None:
    """Normalize a 果仁 code cell to a 6-digit string. ⚠ 果仁 exports codes as INTEGERS, so SZ/BSE codes lose
    leading zeros (001270→'1270', 000656→'656'); a naive `(\\d{6})` regex SILENTLY DROPS them. Zero-pad bare
    numerics; regex-extract the embedded 6-digit run from 'name (603268)' / '603268.SH' forms."""
    s = str(v).strip()
    if re.fullmatch(r"\d+(\.0+)?", s):                 # bare (possibly int-truncated) numeric
        return f"{int(float(s)):06d}"
    m = re.search(r"(\d{6})", s)                       # embedded in a label / suffixed form
    return m.group(1) if m else None


def load_guorn_export(xlsx: Path, code_col, guorn_col) -> pd.DataFrame:
    """Return DataFrame[code6, gval] from a 果仁 每日选股 export. GBK-garble-safe: columns are picked by
    POSITION (int) OR by header string; the 6-digit code is regex-extracted so '*ST松发 (603268)' or a bare
    '603268' both work."""
    raw = pd.read_excel(xlsx)
    cols = list(raw.columns)
    print(f"[guorn] {xlsx.name}: {len(raw)} rows, {len(cols)} cols", flush=True)
    for i, c in enumerate(cols):
        print(f"        col[{i}] = {c!r}", flush=True)

    def pick(spec, default_idx):
        if spec is None:
            return cols[default_idx]
        try:                                  # integer position (garble-proof)
            return cols[int(spec)]
        except (ValueError, TypeError):
            if spec in cols:
                return spec
            hit = [c for c in cols if str(spec) in str(c)]
            if len(hit) == 1:
                return hit[0]
            raise SystemExit(f"--guorn-col {spec!r} matched {len(hit)} columns {hit}; pass a 0-based index")

    ccol = pick(code_col, 0)
    gcol = pick(guorn_col, len(cols) - 1)
    print(f"[guorn] code column = {ccol!r}; value column = {gcol!r}", flush=True)
    out = pd.DataFrame({
        "code6": raw[ccol].map(_code6),
        "gval": pd.to_numeric(raw[gcol], errors="coerce"),
    }).dropna(subset=["code6"])
    print(f"[guorn] normalized {len(out)} codes ({raw[ccol].map(_code6).isna().sum()} unparseable)", flush=True)
    return out.drop_duplicates("code6").set_index("code6")


# ----------------------------------------------------------------------------- local side
def load_local_factor(expr: str, date: str, lag: int, code6_set: set[str]) -> pd.Series:
    """Read `expr` (any qlib expression) at the (lag)-th trading day on/before `date`, return a Series indexed
    by 6-digit code. Restricted to the codes present in the export (cheap fetch)."""
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=PROVIDER_URI, region=REG_CN, kernels=1)

    all_insts = D.list_instruments(D.instruments("all"), as_list=True)
    by6 = {}                                  # 6-digit -> Qlib code (provider-driven join; robust)
    for c in all_insts:
        by6.setdefault(c.split("_")[0], c)
    insts = [by6[c] for c in code6_set if c in by6]
    miss = sorted(c for c in code6_set if c not in by6)
    if miss:
        print(f"[local] {len(miss)} 果仁 codes not in provider universe (e.g. {miss[:5]})", flush=True)

    start = (pd.Timestamp(date) - pd.Timedelta(days=45)).strftime("%Y-%m-%d")
    df = D.features(insts, [expr], start_time=start, end_time=date, freq="day")
    wide = df[expr].unstack(level=0).sort_index()          # datetime x instrument
    pos = wide.index.searchsorted(pd.Timestamp(date), side="right") - 1
    if pos - lag < 0:
        raise SystemExit(f"not enough history before {date} for lag={lag}")
    asof = wide.index[pos - lag]
    print(f"[local] expr={expr!r}  asof={asof.date()} (date={date}, lag={lag})", flush=True)
    row = wide.loc[asof]
    row.index = [str(c).split("_")[0] for c in row.index]   # Qlib -> 6-digit
    return row.groupby(level=0).first().rename("lval")


# ----------------------------------------------------------------------------- compare
def report(g: pd.DataFrame, lv: pd.Series, kind: str, gscale: float, label: str):
    m = g.join(lv, how="left")
    m["gval"] = m["gval"] * gscale
    n_g = len(m)
    both = m.dropna(subset=["gval", "lval"])
    cov = len(both) / max(n_g, 1)
    if kind == "auto":
        gv = both["gval"].dropna()
        kind = "count" if len(gv) and np.allclose(gv, gv.round(), atol=1e-6) else "value"

    print("\n" + "=" * 72)
    print(f"  果仁 ↔ LOCAL parity — {label}")
    print(f"  kind={kind}  guorn_scale={gscale:g}  n_果仁={n_g}  matched={len(both)}  coverage={cov:.1%}")
    if len(both) < 5:
        print("  too few matched rows for metrics."); return
    gvl, lvl = both["gval"], both["lval"]
    sp = gvl.corr(lvl, method="spearman")
    pe = gvl.corr(lvl, method="pearson")
    sign = float((np.sign(gvl) == np.sign(lvl)).mean())

    if kind == "count":
        exact = float((gvl.round() == lvl.round()).mean())
        nz = both[(gvl > 0) & (lvl > 0)]
        pe_nz = nz["gval"].corr(nz["lval"], method="pearson") if len(nz) > 4 else float("nan")
        fg, fl = float((gvl > 0).mean()), float((lvl > 0).mean())
        print(f"  EXACT-match      = {exact:.1%}   (integer/count factor)")
        print(f"  corr (non-zero)  = {pe_nz:.3f}   (n_nonzero={len(nz)})")
        print(f"  frac>0  果仁={fg:.1%}  local={fl:.1%}")
        print(f"  Spearman={sp:.3f}  Pearson={pe:.3f}")
        # a vendor-approximate count (果仁 朝阳永续 vs our 卖方研报) can be off-by-one yet track perfectly —
        # rank + breadth agreement = reproduces; exact-match is the stricter same-vendor (penny) bar.
        strong_track = (pe_nz >= 0.95 and sp >= 0.95) if not np.isnan(pe_nz) else (sp >= 0.97)
        verdict = ("✅ reproduces (vendor-approximate)" if exact >= 0.75 or strong_track
                   else "◑ partial — inspect (vendor diff vs local bug)" if exact >= 0.50 or sp >= 0.7
                   else "✗ divergence — investigate")
    else:
        rel = ((lvl - gvl) / gvl.where(gvl.abs() > EPS)).replace([np.inf, -np.inf], np.nan).abs()
        med = float(rel.median())
        w = {t: float((rel < t).mean()) for t in (0.001, 0.01, 0.05)}
        print(f"  median |rel-err| = {med:.4%}")
        print(f"  within 0.1% / 1% / 5% = {w[0.001]:.1%} / {w[0.01]:.1%} / {w[0.05]:.1%}")
        print(f"  sign-agreement   = {sign:.1%}")
        print(f"  Spearman={sp:.3f}  Pearson={pe:.3f}")
        verdict = ("✅ penny/display-exact (residual = display/PIT-boundary)"
                   if med <= 0.01 and w[0.05] >= 0.90 and sign >= 0.97
                   else "◑ structure-exact (sub-detail residual)"
                   if med <= 0.05 and sign >= 0.95 and sp >= 0.90
                   else "✗ divergence — investigate (local bug vs vendor/复权/lag diff)")
    print(f"  VERDICT: {verdict}")
    print("  (NON-FORMAL. A residual can be a legit vendor diff — 果仁 uses 朝阳永续 / its own 复权;")
    print("   localize before calling it a local bug. Match the lag: most factors are T−1, PIT-gated are lag-0.)")


def main():
    ap = argparse.ArgumentParser(description="果仁 web-export ↔ local factor parity")
    ap.add_argument("--xlsx", required=True, help="path to the 果仁 每日选股 export")
    ap.add_argument("--date", required=True, help="选股日期 YYYY-MM-DD (must be ≤ local freeze 2026-02-27)")
    ap.add_argument("--local-expr", required=True, help="qlib expression, e.g. '$total_mv/1e4'")
    ap.add_argument("--guorn-col", default=None, help="export column holding 果仁's value (header or 0-based idx)")
    ap.add_argument("--code-col", default=None, help="export code column (default col 0)")
    ap.add_argument("--lag", type=int, default=1, help="1=T−1 display lag (default); 0=lag-0 PIT fundamentals")
    ap.add_argument("--guorn-scale", type=float, default=1.0, help="multiply 果仁 value to match local unit")
    ap.add_argument("--kind", choices=["auto", "value", "count"], default="auto")
    a = ap.parse_args()

    xlsx = (ROOT / a.xlsx) if not Path(a.xlsx).is_absolute() else Path(a.xlsx)
    g = load_guorn_export(xlsx, a.code_col, a.guorn_col)
    lv = load_local_factor(a.local_expr, a.date, a.lag, set(g.index))
    report(g, lv, a.kind, a.guorn_scale, f"{a.local_expr}  @ {a.date} (lag {a.lag})")


if __name__ == "__main__":
    main()
