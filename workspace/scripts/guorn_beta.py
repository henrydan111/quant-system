"""T1 local reproduction — 贝塔N日(000001,250): market beta = Cov(r_stock, r_idx, N) / Var(r_idx, N) at a
signal date, r = daily log-return, index = 上证指数 (000001). 果仁 form = SlopeXY(1日涨幅, 指数涨幅(000001), N)
= regression slope of stock-return on index-return = Cov/Var. Emits a code+value parquet for
guorn_factor_parity.py --local-series. Also the starting candidate for 历史贝塔 (may use a different index/window
— verify against 果仁 first). NON-FORMAL.

  python workspace/scripts/guorn_beta.py --date 2025-12-31 --n 250            # full main+chinext universe
  python workspace/scripts/guorn_beta.py --date 2025-12-31 --n 250 --limit 20 # sanity on 20 stocks
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "workspace" / "scripts"))


# Index codes collide on 6-digit with real stocks (000001_SH 上证指数 vs 000001_SZ 平安银行; 000852/000905 _SH
# indices vs their _SZ stocks). board_of() buckets by 6-digit prefix only, so a main-prefix index leaks into the
# EXCL_STAR universe and — since '_SH' sorts before '_SZ' — would win the loader's keep-first join and poison the
# stock's beta. Drop any instrument whose prefix↔exchange-suffix is not a valid A-share listing.
_SH_PREFIXES = ("600", "601", "603", "605", "688", "689", "900")
_SZ_PREFIXES = ("000", "001", "002", "003", "200", "300", "301")


def _is_ashare_stock(code: str) -> bool:
    num, _, suf = code.partition("_")
    if suf.upper() == "SH":
        return num.startswith(_SH_PREFIXES)
    if suf.upper() == "SZ":
        return num.startswith(_SZ_PREFIXES)
    return True  # BJ / other handled by the board filter


def _index_returns(index_code: str, start: str, end: str, n: int) -> pd.Series:
    # 果仁 caliber = SIMPLE daily returns (1日涨幅 / 指数涨幅), not log. Validated 2025-12-31: simple-后复权
    # beta lands medRelErr 0.19% vs 果仁 贝塔N日(000001,250) (log-raw was 1.52%). An index carries no
    # dividends so raw close = 后复权 for the index leg.
    from qlib.data import D
    for form in (index_code, index_code.upper(), index_code.replace("_sh", "_SH")):
        try:
            df = D.features([form], ["$close"], start_time=start, end_time=end)
            if len(df):
                s = df.reset_index(level=0, drop=True)["$close"].sort_index()
                r = s.pct_change(fill_method=None).dropna()
                return r.iloc[-n:], form
        except Exception:
            continue
    raise SystemExit(f"index {index_code} not queryable (tried case/suffix variants)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--n", type=int, default=250)
    ap.add_argument("--index", default="000001_sh")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--outdir", default=str(ROOT / "workspace" / "outputs" / "guorn_derived"))
    a = ap.parse_args()

    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(ROOT / "data" / "qlib_data"), region=REG_CN, kernels=1)
    from guorn_universe import EXCL_STAR, in_guorn_universe

    d = pd.Timestamp(a.date)
    start = (d - pd.Timedelta(days=int(a.n * 1.7) + 60)).strftime("%Y-%m-%d")
    r_idx, idx_form = _index_returns(a.index, start, a.date, a.n)
    var_idx = float(r_idx.var())
    print(f"[beta] index={idx_form}  n={a.n}  var_idx={var_idx:.3e}  idx window {r_idx.index.min().date()}..{r_idx.index.max().date()}", flush=True)

    univ = [c for c in D.list_instruments(D.instruments("all"), as_list=True)
            if in_guorn_universe(c, boards=EXCL_STAR) and _is_ashare_stock(c)]
    if a.limit:
        univ = univ[:a.limit]
    # 后复权 close ($close × $adj_factor) + SIMPLE daily returns = 果仁's 1日涨幅 caliber (validated:
    # simple-后复权 → medRelErr 0.19% vs 果仁 贝塔N日; raw/log leaves a ~1.5% dividend/return-convention residual).
    feat = D.features(univ, ["$close", "$adj_factor"], start_time=start, end_time=a.date)
    adjc = (feat["$close"] * feat["$adj_factor"]).unstack(level=0).sort_index()
    rets = adjc.pct_change(fill_method=None)
    idx_win = r_idx.index
    rows = []
    for code in rets.columns:
        r = rets[code].reindex(idx_win)
        pair = pd.concat([r, r_idx], axis=1).dropna()
        if len(pair) >= max(60, a.n // 2):  # need enough overlap
            beta = pair.iloc[:, 0].cov(pair.iloc[:, 1]) / var_idx
            rows.append((code.split("_")[0], beta))
    out = pd.DataFrame(rows, columns=["code", "value"])
    outdir = Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    tag = a.date.replace("-", "")
    dest = outdir / f"beta_{a.index}_{a.n}_{tag}.parquet"
    out.to_parquet(dest, index=False)
    print(f"[beta] wrote {len(out)} codes -> {dest}")
    print(out["value"].describe().to_string())


if __name__ == "__main__":
    main()
