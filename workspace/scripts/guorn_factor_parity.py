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
try:                                          # import-safe under pytest's captured stdout
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass
PROVIDER_URI = str(ROOT / "data" / "qlib_data")
TRADE_CAL = ROOT / "data" / "reference" / "trade_cal.parquet"
EPS = 1e-9
# Pointwise-only guard. qlib's expression engine is PER-INSTRUMENT time-series (Ref/Mean/Corr/Rank-over-window
# …), so a valid --local-expr is computed independently per stock and the export-codes-only fetch is correct.
# A genuine CROSS-SECTIONAL / group / neutralized / composite factor is NOT a qlib expression (it lives in the
# factor_eval helpers / the 综合级 harness); refuse these tokens with a clear redirect rather than mis-handle.
CROSS_SECTIONAL_TOKENS = ("cs_", "csrank", "havg", "hneutralize", "neutralize", "grouped by")


def _trading_days() -> pd.DatetimeIndex:
    """The local provider trading calendar (the §3.1 ground truth)."""
    cal = pd.read_parquet(TRADE_CAL, columns=["cal_date", "is_open"])
    cal = cal[cal["is_open"] == 1]
    return pd.DatetimeIndex(pd.to_datetime(cal["cal_date"].astype(str), format="%Y%m%d")).sort_values()


def assert_pointwise(expr: str) -> None:
    """Refuse cross-sectional/group/neutralized/composite expressions (B2). They change value with the instrument
    set, and this tool fetches only the 果仁-export codes; qlib expressions are per-instrument, so a valid expr is
    pointwise — these tokens signal a 综合级 factor that must use the full-universe harness instead."""
    bad = [t for t in CROSS_SECTIONAL_TOKENS if t in expr.lower()]
    if bad:
        raise SystemExit(
            f"guorn_factor_parity.py is POINTWISE-only (fetches only 果仁-export codes); {expr!r} contains "
            f"cross-sectional token(s) {bad}. Compute a cross-sectional / group / neutralized / composite factor "
            "on the FULL intended universe via the 综合级 harness (_composite_row pattern), then join to the export.")


def validate_trading_date(date: str, cal: pd.DatetimeIndex) -> pd.Timestamp:
    """--date must be an actual trading day ≤ the local provider calendar max (no silent fallback, no lookahead)."""
    target = pd.Timestamp(date)
    if target > cal.max():
        raise SystemExit(f"--date {date} > local calendar max {cal.max().date()} — outside local coverage, unreproducible")
    if target not in set(cal):
        raise SystemExit(f"--date {date} is not a trading day in the local calendar — pass an actual trading day")
    return target


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
def load_local_factor(expr: str, date: str, lag: int, code6_set: set[str],
                      provider_uri: str = PROVIDER_URI) -> pd.Series:
    """Read `expr` (any qlib expression) at the (lag)-th trading day on/before `date`, return a Series indexed
    by 6-digit code. Restricted to the codes present in the export (cheap fetch). `provider_uri` selects the
    Qlib provider — pass a STAGED deep-slot build (data/qlib_builds/<build_id>/provider) for deep-slot parity
    (M2: the comparator must read the provider the factor is tested against, not always the live one)."""
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    staged = "qlib_builds" in str(provider_uri).replace("\\", "/")
    print(f"[provider] uri={provider_uri}  staged_deepslot={staged}", flush=True)
    qlib.init(provider_uri=provider_uri, region=REG_CN, kernels=1)

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
def report(g: pd.DataFrame, lv: pd.Series, kind: str, gscale: float, min_coverage: float, label: str,
           rank_desc: bool = True):
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
    if cov < min_coverage:                                   # coverage gate fires for ANY row count (B1 + Minor)
        print(f"  VERDICT: ✗ coverage gap — matched {cov:.1%} < --min-coverage {min_coverage:.1%}; fix "
              "universe/join/provider coverage before trusting any matched-subset metrics (lower --min-coverage "
              "with a documented reason to inspect the matched subset)")
        print("  (NON-FORMAL. Match the lag: most factors are T−1, PIT-gated are lag-0.)")
        return
    if len(both) < 5:
        print("  too few matched rows for stable metrics.")
        print("  VERDICT: ✗ insufficient matched rows — collect a larger export or use a purpose-built small-N audit")
        return
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
        # A vendor-approximate count (果仁 朝阳永续 vs our 卖方研报) can be off-by-one yet RANK perfectly — usable
        # for ranking/composite, NOT for a threshold filter or an exact data audit (a scaled count can rank-corr
        # 1.0 yet be threshold-wrong). So rank-faithful is ◑, not ✅; ✅ is reserved for same-vendor exact with
        # matching >0 breadth.
        strong_track = (pe_nz >= 0.95 and sp >= 0.95) if not np.isnan(pe_nz) else (sp >= 0.97)
        metric_verdict = (
            "✅ same-vendor count-exact" if exact >= 0.95 and abs(fg - fl) <= 0.01
            else "◑ vendor-approx rank-faithful — ranking/composite use ONLY; NOT threshold/value-exact"
            if strong_track and abs(fg - fl) <= 0.03
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
        metric_verdict = (
            "✅ penny/display-exact (residual = display/PIT-boundary)"
            if med <= 0.01 and w[0.05] >= 0.90 and sign >= 0.97
            else "◑ structure-exact (sub-detail residual)"
            if med <= 0.05 and sign >= 0.95 and sp >= 0.90
            else "✗ divergence — investigate (local bug vs vendor/复权/lag diff)")
    print(f"  VERDICT: {metric_verdict}")                    # coverage already cleared the gate above
    # top-K SELECTION overlap (deployment-relevant). RIGOROUS — 果仁's top-K is from its FULL export, so a 果仁
    # top name that local CAN'T value is a real MISS (local can't select it): any universe/筛选条件 inconsistency
    # surfaces here, not hidden by restricting to the matched subset. m = full 果仁 set (lval NaN where missing).
    asc = not rank_desc
    gtop = m["gval"].sort_values(ascending=asc, kind="mergesort")           # 果仁's true ranking (full universe)
    ltop = m["lval"].dropna().sort_values(ascending=asc, kind="mergesort")  # local's ranking (names local can value)
    ov = []
    for k in (5, 10, 20):
        kk = min(k, len(gtop))
        gk = set(gtop.head(kk).index)
        ov.append(f"top{k}={len(gk & set(ltop.head(min(k, len(ltop))).index)) / kk:.0%}")
    print(f"  selection overlap (by {'smallest' if asc else 'largest'} value): " + "  ".join(ov))
    miss20 = int(m.loc[list(set(gtop.head(min(20, len(gtop))).index)), "lval"].isna().sum())
    if miss20:
        print(f"  ⚠ {miss20} of 果仁's top-20 are NOT valued locally — coverage gap in the SELECTION zone; the "
              "rank comparison is affected. Match the 果仁 universe/筛选条件 to the local set before trusting top-K.")
    print("  (NON-FORMAL. A residual can be a legit vendor diff — 果仁 uses 朝阳永续 / its own 复权;")
    print("   localize before calling it a local bug. Match the lag: most factors are T−1, PIT-gated are lag-0.)")


def main():
    ap = argparse.ArgumentParser(description="果仁 web-export ↔ local factor parity")
    ap.add_argument("--xlsx", required=True, help="path to the 果仁 每日选股 export")
    ap.add_argument("--date", required=True, help="选股日期 YYYY-MM-DD; a trading day ≤ the local provider calendar max (printed at runtime)")
    ap.add_argument("--local-expr", required=True, help="POINTWISE qlib expression, e.g. '$total_mv/1e4' (no cross-sectional/composite)")
    ap.add_argument("--guorn-col", default=None, help="export column holding 果仁's value (header or 0-based idx)")
    ap.add_argument("--code-col", default=None, help="export code column (default col 0)")
    ap.add_argument("--lag", type=int, default=1, help="1=T−1 display lag (default); 0=lag-0 PIT fundamentals")
    ap.add_argument("--guorn-scale", type=float, default=1.0, help="multiply 果仁 value to match local unit")
    ap.add_argument("--kind", choices=["auto", "value", "count"], default="auto")
    ap.add_argument("--min-coverage", type=float, default=0.98,
                    help="min matched-果仁 fraction required before any ✅ verdict; lower ONLY with a documented reason")
    ap.add_argument("--select-asc", action="store_true",
                    help="factor selects the SMALLEST values (top-K = smallest, e.g. 市值最小); default = largest")
    ap.add_argument("--provider-uri", default=PROVIDER_URI,
                    help="Qlib provider to read; pass data/qlib_builds/<build_id>/provider for deep-slot parity (M2)")
    a = ap.parse_args()

    assert_pointwise(a.local_expr)                                    # B2: refuse cross-sectional/composite
    cal = _trading_days()
    print(f"[cal] local provider calendar max = {cal.max().date()}", flush=True)
    validate_trading_date(a.date, cal)                               # Minor 1+2: trading-day ≤ calendar max
    xlsx = (ROOT / a.xlsx) if not Path(a.xlsx).is_absolute() else Path(a.xlsx)
    g = load_guorn_export(xlsx, a.code_col, a.guorn_col)
    lv = load_local_factor(a.local_expr, a.date, a.lag, set(g.index), provider_uri=a.provider_uri)
    report(g, lv, a.kind, a.guorn_scale, a.min_coverage, f"{a.local_expr}  @ {a.date} (lag {a.lag})",
           rank_desc=not a.select_asc)


if __name__ == "__main__":
    main()
