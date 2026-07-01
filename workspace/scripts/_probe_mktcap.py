import sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
import qlib
from qlib.config import REG_CN
from qlib.data import D
qlib.init(provider_uri=str(ROOT / "data" / "qlib_data"), region=REG_CN, kernels=1)
for fld in ["$total_mv", "$circ_mv", "$total_share", "$float_share", "$amount", "$close", "$adj_factor"]:
    try:
        df = D.features(["000001_SZ", "000002_SZ"], [fld], start_time="2024-01-02", end_time="2024-01-05", freq="day")
        v = df.iloc[:, 0].dropna()
        print(f"OK  {fld:14} n={len(v)}  sample={v.head(2).round(3).tolist()}")
    except Exception as e:
        print(f"ERR {fld:14} {type(e).__name__}: {str(e)[:80]}")
