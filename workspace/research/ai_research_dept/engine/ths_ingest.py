# SCRIPT_STATUS: ACTIVE — v1.5-E:THS 概念板块拉取(税onomy + 成分快照)
"""THS concept boards → reference parquets(概念标签维 + 检索 concept 通道的税onomy)。

⚠ PIT 诚实声明:ths_member 仅提供**当前成分快照**(无 in/out 日期)——概念标签的历史
应用弱于行业(区间制 PIT)。试点(NON_EVIDENTIARY)接受;生产期每次拉取带 fetched_at 戳,
版本随 tag_version 演进,前向使用取 as-of 最近快照。记录于此,不得静默当强 PIT 用。

用法: venv/Scripts/python.exe workspace/research/ai_research_dept/engine/ths_ingest.py
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from workspace.research.ai_research_dept.engine import config as C  # noqa: E402
from data_infra.fetchers import TushareFetcher  # noqa: E402

logger = logging.getLogger("ths_ingest")
OUT_DIR = C.PROJECT_ROOT / "data" / "reference" / "ths_concept"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    f = TushareFetcher()
    now = pd.Timestamp.now().isoformat()

    idx = f._safe_api_call(f.pro.ths_index, exchange="A", type="N")
    logger.info("ths_index (A股概念): %d boards", len(idx))
    idx["fetched_at"] = now

    frames, t0 = [], time.time()
    for i, code in enumerate(idx["ts_code"], 1):
        mem = f._safe_api_call(f.pro.ths_member, ts_code=code)
        if mem is not None and not mem.empty:
            frames.append(mem)
        if i % 50 == 0:
            logger.info("members %d/%d | %.0fs", i, len(idx), time.time() - t0)
    members = pd.concat(frames, ignore_index=True)
    members["fetched_at"] = now

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    idx.to_parquet(OUT_DIR / "ths_index.parquet", index=False)
    members.to_parquet(OUT_DIR / "ths_members.parquet", index=False)
    per = members.groupby("con_code").size()
    logger.info("members -> %d rows | 覆盖股票 %d | 概念数/股 中位 %d 最大 %d",
                len(members), members["con_code"].nunique(),
                int(per.median()), int(per.max()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
