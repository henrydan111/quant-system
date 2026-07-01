# -*- coding: utf-8 -*-
"""Replace the mislabeled 16_ file with the correct freshly-exported sm_noc backtest."""
import re
import time
from pathlib import Path
import openpyxl

DL = Path(r"E:\量化系统\Knowledge\果仁回测结果")
TARGET = DL / "16_sm_noc_纯市值正盈利_v4.xlsx"
HASH_RE = re.compile(r"^[0-9a-fA-F]{16,}\.xlsx$")

# poll for the new hash download to settle
deadline = time.time() + 90
src = None
while time.time() < deadline:
    cands = [p for p in DL.glob("*.xlsx") if HASH_RE.match(p.name)]
    if cands and not any(DL.glob("*.crdownload")) and not any(DL.glob("*.tmp")):
        newest = max(cands, key=lambda p: p.stat().st_mtime)
        if time.time() - newest.stat().st_mtime >= 1.0:
            src = newest
            break
    time.sleep(1.0)

if not src:
    print("FAIL: no new hash xlsx download found")
    raise SystemExit(2)

# verify it's sm_noc's real result (本策略 总收益 != 549.88 i.e. not the stale dup)
wb = openpyxl.load_workbook(src, read_only=True, data_only=True)
strat = [list(r) for r in wb.worksheets[0].iter_rows(min_row=2, max_row=2, values_only=True)][0]
wb.close()
total = strat[1]
print("new file 本策略 总收益(ratio):", total, " (stale was 549.88)")
if total is not None and abs(float(total) - 549.88) < 0.5:
    print("FAIL: still the stale 549.88 result -- NOT replacing")
    raise SystemExit(3)

src.replace(TARGET)
print(f"OK replaced 16_ with sm_noc real export: 总收益={round(float(total)*100,2)}%  ({TARGET.stat().st_size} bytes)")
