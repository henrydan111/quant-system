"""#7 zsfz 二级行业内 screen diagnosis — is 果仁's L2 partition as-of (historical intervals) or
CURRENT-snapshot-retroactive? Judged against the xlsx's own 二级行业 ground-truth column (held names).
Also: distribution of MY within-L2 zsfz pct for 果仁-held names (boundary convention probe).
SCRIPT_STATUS: Class-B parity diagnostic (verify07). NON-FORMAL."""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8")
SWM = ROOT / "data" / "universe" / "industry_sw2021_members" / "industry_sw2021_members.parquet"
XLSX = ROOT / "Knowledge" / "果仁回测结果" / "19_value_红利低波_v2.xlsx"
CACHE = ROOT / "workspace" / "outputs" / "guorn_parity" / "verify07_cache"

x = pd.read_excel(XLSX, sheet_name="各阶段持仓详单")
x["start"] = pd.to_datetime(x["开始日期"])
x["code"] = x["股票代码"].astype(str).str.zfill(6)
x = x[x["start"] <= pd.Timestamp("2026-02-27")]
m = pd.read_parquet(SWM)
m["c6"] = m["ts_code"].str.split(".").str[0]
cur = m[m["is_new"] == "Y"].drop_duplicates("c6", keep="last").set_index("c6")["l2_name"]

hits_asof = tot = hits_cur = 0
mism = []
for (d, c), grp in x.groupby(["start", "code"]):
    g = str(grp["二级行业"].iloc[0]).strip()
    if not g or g == "nan":
        continue
    tot += 1
    alive = m[(m["c6"] == c) & (m["in_date"] <= d) & ((m["out_date"].isna()) | (m["out_date"] > d))]
    a = str(alive["l2_name"].iloc[-1]).strip() if len(alive) else ""
    cv = str(cur.get(c, "")).strip()
    hits_asof += (a == g)
    hits_cur += (cv == g)
    if a != g and len(mism) < 15:
        mism.append((str(d.date()), c, g, a, cv))
print(f"二级行业 match: as-of {hits_asof}/{tot} = {hits_asof/tot:.1%}   current-only {hits_cur}/{tot} = {hits_cur/tot:.1%}")
print("as-of mismatches (date, code, 果仁L2, my-asof-L2, my-current-L2):")
for r in mism:
    print("  ", r)

# ---- held-name within-L2 zsfz percentile distribution (my values+groups, both near-exact valuewise)
close = pd.read_parquet(CACHE / "e_close_raw.parquet")
zsfz = pd.read_parquet(CACHE / "e_zsfz.parquet").reindex(columns=close.columns)
l2 = pd.read_parquet(CACHE / "industry_l2.parquet").reindex(columns=close.columns)
grid = close.index
up = {str(c).split("_")[0]: c for c in close.columns}
pcts = []
for d, grp in x.groupby("start"):
    pos = grid.searchsorted(pd.Timestamp(d))
    if pos == 0:
        continue
    pday = grid[pos - 1]
    l2row = l2.loc[pday] if pday in l2.index else l2.iloc[max(0, l2.index.searchsorted(pday) - 1)]
    l2row = l2row.replace({"nan": np.nan, "None": np.nan})
    zr = zsfz.loc[pday].where(close.loc[pday].notna())
    zp = zr.groupby(l2row).rank(pct=True)
    for c in grp["code"]:
        inst = up.get(c)
        if inst is not None:
            v = zp.get(inst, np.nan)
            if pd.notna(v):
                pcts.append(float(v))
s = pd.Series(pcts)
print(f"\n果仁-held names' MY within-L2 zsfz pct: n={len(s)}  >0.50: {(s>0.5).mean():.1%}")
print("deciles:", s.quantile([.1, .25, .5, .75, .9, .95, .99]).round(3).to_dict())
print("of those >0.5, distribution:", s[s > 0.5].quantile([.25, .5, .75]).round(3).to_dict())

# ---- boundary-rule × rank-base shootout for the zsfz 二级行业内 screen
sys.path.insert(0, str(ROOT / "workspace" / "research" / "long_only_50cagr"))
import research_utils as ru  # noqa: E402
bounds_df = pd.read_csv(ROOT / "data" / "qlib_data" / "instruments" / "all_stocks.txt", sep="\t",
                        header=None, names=["code", "start", "end"], dtype=str)
BOUNDS = {str(r.code).upper(): (pd.Timestamp(r.start), pd.Timestamp(r.end))
          for r in bounds_df.itertuples(index=False)}
insts = close.columns
res = {k: 0 for k in ("A_pct", "A_ceil", "B_pct", "B_ceil", "C_pct", "C_ceil")}
n = 0
for d, grp in x.groupby("start"):
    pos = grid.searchsorted(pd.Timestamp(d))
    if pos == 0:
        continue
    pday = grid[pos - 1]
    l2row = (l2.loc[pday] if pday in l2.index
             else l2.iloc[max(0, l2.index.searchsorted(pday) - 1)]).replace({"nan": np.nan, "None": np.nan})
    st = ru.st_codes_on(pd.Timestamp(d))
    quoted = close.loc[pday].notna()
    not_st = pd.Series([str(c).upper() not in st for c in insts], index=insts)
    listed = pd.Series([(BOUNDS.get(str(c).upper()) is not None
                         and BOUNDS[str(c).upper()][0] <= pday <= BOUNDS[str(c).upper()][1])
                        for c in insts], index=insts)
    bases = {"A": quoted, "B": quoted & not_st, "C": listed}
    zrow = zsfz.loc[pday]
    picks = [(c, up.get(c)) for c in grp["code"]]
    for tag, base in bases.items():
        zr = zrow.where(base)
        ra = zr.groupby(l2row).rank(method="min")
        Ng = l2row.map(zr.groupby(l2row).count())
        for c, inst in picks:
            if inst is None or pd.isna(ra.get(inst, np.nan)):
                continue
            if tag == "A":
                n += 1
            res[f"{tag}_pct"] += bool(ra[inst] / Ng[inst] <= 0.5)
            res[f"{tag}_ceil"] += bool(ra[inst] <= np.ceil(0.5 * Ng[inst]))
print(f"\nzsfz pass-rate of 果仁-held names (n≈{n}) — base A=quoted B=quoted∩非ST C=listed(incl 停牌/ST):")
for k, v in res.items():
    print(f"  {k}: {v/n:.3f}")

# ---- L1-group alternative + failing-name industry profile (vintage-restatement diagnosis)
l2f = l2  # keep name
mm = pd.read_parquet(SWM)
mm["c"] = mm["ts_code"].str.replace(".", "_", regex=False).str.upper()
upcols = {str(c).upper(): c for c in close.columns}
mm = mm[mm["c"].isin(upcols)]
resL1 = {"pct": 0, "ceil": 0}
fail_l1 = {}
n2 = 0
for d, grp in x.groupby("start"):
    pos = grid.searchsorted(pd.Timestamp(d))
    if pos == 0:
        continue
    pday = grid[pos - 1]
    alive = mm[(mm["in_date"] <= pday) & ((mm["out_date"].isna()) | (mm["out_date"] > pday))]
    s1 = alive.drop_duplicates("c", keep="last").set_index("c")["l1_name"]
    s1.index = [upcols[i] for i in s1.index]
    l1row = s1.reindex(close.columns)
    l2row = (l2f.loc[pday] if pday in l2f.index
             else l2f.iloc[max(0, l2f.index.searchsorted(pday) - 1)]).replace({"nan": np.nan, "None": np.nan})
    zr = zsfz.loc[pday].where(close.loc[pday].notna())
    raL1 = zr.groupby(l1row).rank(method="min")
    NL1 = l1row.map(zr.groupby(l1row).count())
    raL2 = zr.groupby(l2row).rank(method="min")
    NL2 = l2row.map(zr.groupby(l2row).count())
    for c in grp["code"]:
        inst = up.get(c)
        if inst is None or pd.isna(raL1.get(inst, np.nan)):
            continue
        n2 += 1
        resL1["pct"] += bool(raL1[inst] / NL1[inst] <= 0.5)
        resL1["ceil"] += bool(raL1[inst] <= np.ceil(0.5 * NL1[inst]))
        if pd.notna(raL2.get(inst, np.nan)) and raL2[inst] > np.ceil(0.5 * NL2[inst]):
            k = str(l1row.get(inst))
            fail_l1[k] = fail_l1.get(k, 0) + 1
print(f"\nzsfz pass-rate under L1 grouping (n={n2}): pct {resL1['pct']/n2:.3f}  ceil {resL1['ceil']/n2:.3f}")
print("L2-ceil FAILING held-names by L1 industry (top):")
for k, v in sorted(fail_l1.items(), key=lambda kv: -kv[1])[:12]:
    print(f"  {k:10} {v}")
