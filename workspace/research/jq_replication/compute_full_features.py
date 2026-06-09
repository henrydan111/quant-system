"""Compute the FULL feature set (111 base catalog + 20 Layer-2 composites + 4 industry-relative)
over 2014-2026 as ML features — the 'give ML genuinely rich features' run. Batched + float32 to
bound memory. PIT-safe (compute_factors = sanctioned door; Ref(...,1)). Saves full_features.parquet.
"""
from __future__ import annotations
import gc
import numpy as np, pandas as pd
import jq_rep_utils as JR
from src.alpha_research import factor_library as fl

OUT = JR.OUT
START, END = "2014-01-01", "2026-02-27"

cat = fl.get_factor_catalog()
items = list(cat.items())
B = 28
batches = [dict(items[i:i+B]) for i in range(0, len(items), B)]
print(f"base catalog {len(items)} factors in {len(batches)} batches", flush=True)

base = None; fwd = None
for bi, b in enumerate(batches):
    print(f"  batch {bi+1}/{len(batches)} ({len(b)} factors)...", flush=True)
    fdf, fw = fl.compute_factors(b, START, END, horizons=[20])
    fdf = fdf.astype("float32")
    base = fdf if base is None else base.join(fdf, how="outer")
    if fwd is None: fwd = fw[["fwd_20d"]].astype("float32")
    del fdf, fw; gc.collect()
print(f"base features: {base.shape}", flush=True)

# Layer-2 composites
try:
    base = fl.add_composites(base).astype("float32")
    print(f"+composites -> {base.shape}", flush=True)
except Exception as e:
    print(f"composites SKIPPED: {e}", flush=True)

# industry-relative (needs SW2021 industry series + market cap)
try:
    from src.data_infra import provider_metadata as pm
    ind = pm.build_industry_series_asof(base.index, level=1)
    mcap = np.exp(base["size_ln_mcap"].astype("float64")) if "size_ln_mcap" in base.columns else None
    base = fl.add_industry_relative_composites(base, ind, mcap).astype("float32")
    print(f"+industry-relative -> {base.shape}", flush=True)
except Exception as e:
    print(f"industry-relative SKIPPED: {e}", flush=True)

base.to_parquet(OUT / "full_features.parquet")
fwd.to_parquet(OUT / "full_fwd.parquet")
print(f"SAVED full_features {base.shape} + full_fwd -> {OUT}", flush=True)
print("columns:", list(base.columns), flush=True)
