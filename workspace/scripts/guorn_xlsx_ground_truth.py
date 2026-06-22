"""Extract 果仁 backtest ground-truth from an exported xlsx, for the local-vs-果仁
PARITY ladder (system-integrity check; 果仁 = trusted benchmark).

Usage:
    python workspace/scripts/guorn_xlsx_ground_truth.py "Knowledge/果仁回测结果/11_sm_纯市值01.xlsx" [--explore]

--explore: dump sheet names + shapes + heads (first time, to learn the layout).
Default: print the parity-relevant facts (headline metrics, rebalance cadence inferred
from the trade log, holding count, turnover) + write the daily NAV curve to a sibling csv.
"""
from __future__ import annotations

import sys
import argparse
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx")
    ap.add_argument("--explore", action="store_true")
    args = ap.parse_args()

    path = Path(args.xlsx)
    book = pd.read_excel(path, sheet_name=None, header=None)
    print(f"# {path.name}  —  {len(book)} sheets")
    for name, df in book.items():
        print(f"  sheet {name!r:32} shape={df.shape}")

    if args.explore:
        for name, df in book.items():
            print(f"\n===== {name} =====")
            with pd.option_context("display.max_rows", 30, "display.max_columns", 20, "display.width", 200):
                print(df.head(20).to_string())
        return

    # default: dump the daily NAV curve (date, strategy daily return, position, turnover) for the diff
    cur = book.get("收益曲线")
    if cur is not None:
        c = cur.iloc[1:].copy()                       # drop header row
        c.columns = ["date", "bench_cum", "strat_cum", "strat_ret", "position", "strat_turn", "bench_ret"][: c.shape[1]]
        c["date"] = pd.to_datetime(c["date"])
        out = path.with_name(path.stem + "__daily_curve.csv")
        c.to_csv(out, index=False, encoding="utf-8")
        print(f"\n[curve] {len(c)} days {c['date'].min().date()}..{c['date'].max().date()} -> {out.name}")
        print(f"[curve] avg position={pd.to_numeric(c['position'], errors='coerce').mean():.3f}  "
              f"avg daily turnover={pd.to_numeric(c['strat_turn'], errors='coerce').mean():.3f}")


if __name__ == "__main__":
    main()
