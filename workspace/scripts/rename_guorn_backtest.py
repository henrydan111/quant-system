# -*- coding: utf-8 -*-
"""Rename freshly-downloaded guorn backtest xlsx (hash filenames) to NN_<strategy>.xlsx.

Self-counting: NN is derived from how many NN_*.xlsx already exist, so it can be
called after each export (or after a batch of exports). New hash-named files are
renamed in mtime (arrival) order to the next sequential indices, using the verified
bt_queue.json order (== guorn_slct_strategies.json order).

Usage:
  python rename_guorn_backtest.py            # rename all currently-un-renamed hash xlsx
  python rename_guorn_backtest.py --expect N # also assert exactly N new files renamed
"""
import sys
import re
import json
import time
from pathlib import Path

DL = Path(r"E:\量化系统\Knowledge\果仁回测结果")
QUEUE = json.loads(Path(r"E:\量化系统\workspace\research\idea_sourcing\guorn\bt_queue.json").read_text(encoding="utf-8"))

HASH_RE = re.compile(r"^[0-9a-fA-F]{16,}\.xlsx$")
DONE_RE = re.compile(r"^\d+_")

def sanitize(name):
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()

def downloading():
    return any(DL.glob("*.crdownload")) or any(DL.glob("*.tmp"))

def unrenamed():
    return sorted([p for p in DL.glob("*.xlsx") if HASH_RE.match(p.name)],
                  key=lambda p: p.stat().st_mtime)

def main():
    expect = None
    if "--expect" in sys.argv:
        expect = int(sys.argv[sys.argv.index("--expect") + 1])

    # wait for downloads to settle and for at least the expected files to be present
    deadline = time.time() + 200
    while time.time() < deadline:
        files = unrenamed()
        settled = (not downloading()) and files and (time.time() - files[-1].stat().st_mtime) >= 1.0
        if settled and (expect is None or len(files) >= expect):
            break
        time.sleep(1.0)

    files = unrenamed()
    done = sum(1 for p in DL.glob("*.xlsx") if DONE_RE.match(p.name))
    if not files:
        print(f"NO new hash xlsx found (already renamed {done}).")
        sys.exit(2 if expect else 0)

    renamed = 0
    for src in files:
        idx = done  # 0-based index into queue
        if idx >= len(QUEUE):
            print(f"WARN extra file {src.name}, beyond queue length {len(QUEUE)}")
            break
        nn = idx + 1
        target = DL / f"{nn:02d}_{sanitize(QUEUE[idx])}.xlsx"
        src.rename(target)
        print(f"OK {target.name}  ({target.stat().st_size} bytes)")
        done += 1
        renamed += 1

    print(f"renamed {renamed}; total done {done}/{len(QUEUE)}")
    if expect is not None and renamed != expect:
        print(f"WARNING: expected {expect} new files but renamed {renamed}")
        sys.exit(3)

if __name__ == "__main__":
    main()
