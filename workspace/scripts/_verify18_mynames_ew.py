"""#18 decomp leg 3: MY selected names through EW (isolate SELECTION from my model-II construction).
3-way: 果仁-names-EW (+60.99, _verify18_replay) | my-names-EW (this) | my-names-modelII (+26.48, the harness).
my-names-EW ≈ my-modelII -> construction neutral, gap is pure SELECTION; my-names-EW > my-modelII ->
model-II/no-exits construction hurts. NON-FORMAL diagnostic."""
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "workspace" / "research" / "long_only_50cagr"))
sys.path.insert(0, str(ROOT / "workspace" / "scripts"))
sys.stdout.reconfigure(encoding="utf-8")
import research_utils as ru                                            # noqa: E402
from guorn_parity_rung6_quality59 import EqualWeightScheduleStrategy   # noqa: E402

OUT = ROOT / "workspace" / "outputs" / "guorn_parity"
GR = dict(annual=0.5546)


def main(start="2014-01-01", end="2026-02-27"):
    from src.backtest_engine.event_driven import EventDrivenBacktester, CostConfig
    from src.backtest_engine.event_driven.exchange import FixedSlippage
    raw = json.loads((OUT / "verify18_schedule.json").read_text(encoding="utf-8"))
    sched = {pd.Timestamp(k): v[:5] for k, v in raw.items() if v}   # MY top-5 each day
    strat = EqualWeightScheduleStrategy(sched, n=5)
    cost = CostConfig(buy_commission=0.002, sell_commission=0.002, stamp_tax=0.0, min_commission=0.0, transfer_fee=0.0)
    bt = EventDrivenBacktester(data_dir=str(ROOT / "data"))
    res = bt.run(strategy=strat, start_time=start, end_time=end, benchmark="000300.SH", account=1_000_000.0,
                 exchange_config=cost, slippage=FixedSlippage(0.0), volume_limit=0.10, hold_on_limit_up=True,
                 preload_fields=["$open", "$close", "$high", "$low", "$vol", "$amount", "$pre_close", "$adj_factor",
                                 "$up_limit", "$down_limit"])
    rep = res.report.copy()
    if "date" in rep.columns:
        rep = rep.set_index(pd.to_datetime(rep["date"]))
    net = rep["return"].astype(float)
    m = ru.goal_metrics(net)
    yr = net.groupby(net.index.year).apply(lambda r: (1 + r).prod() - 1)
    print("\n" + "=" * 64)
    print(f"  #18 MY-NAMES-EW annual≈{m['cagr']:+.2%}   (vs my-modelII +26.48% / 果仁-names-EW +60.99% / 果仁 +55.46%)")
    print("  year   my-names-EW")
    for y in sorted(yr.index):
        print(f"  {int(y)}   {yr[y]:+8.1%}")
    print("\n  INTERP: ≈+26% => construction neutral, gap is pure SELECTION. >>+26% => model-II construction hurts.")


if __name__ == "__main__":
    main()
