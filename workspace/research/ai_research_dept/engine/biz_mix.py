# SCRIPT_STATUS: ACTIVE — 业务构成卡段(fina_mainbz → 基本面卡「公司业务构成」节)
"""Business-mix section for the fund card (v1.5-A).

数据门:pit_event_feed('fina_mainbz')——可见性=同期定期报告 ann_date 严格次开盘日。
mainbz 的产品切分与地区切分混在同一列(raw 无 type 列),直接混合取 top 会把收入双计;
启发式分离:地区关键词命中(境内/境外/国内/国外/华东…/地区/洲)→ district,余为 product;
优先展示 product 切分(更有信息量),不足 2 项时回退 district,段首标注切分类型。

输出:biz_mix_{month}.parquet (ts_code, trade_date, biz_text) —— 渲染文本直接拼进基本面卡。
用法: venv/Scripts/python.exe workspace/research/ai_research_dept/engine/biz_mix.py
"""
from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from workspace.research.ai_research_dept.engine import config as C  # noqa: E402
from workspace.research.ai_research_dept.engine.fact_table import decision_days  # noqa: E402
from data_infra.pit_event_feed import load_event_feed  # noqa: E402

logger = logging.getLogger("biz_mix")

_DISTRICT_RE = re.compile(
    r"境内|境外|国内|国外|华东|华南|华北|华中|西南|西北|东北|地区|海外|大陆|亚太|欧洲|美洲|"
    r"中国|香港|台湾|澳门|亚洲|非洲|美国|日本|韩国|欧美|东南亚|出口|内销|外销|洲$|省$|市$")


def render_biz(sub: pd.DataFrame) -> str:
    """sub = 该股最新可见报告期的 mainbz 行。"""
    end = sub["end_date"].iloc[0]
    sub = sub.assign(is_district=sub["bz_item"].astype(str).str.contains(_DISTRICT_RE))
    prod = sub[~sub["is_district"]]
    pick, label = (prod, "分产品") if len(prod) >= 2 else (sub[sub["is_district"]], "分地区")
    if pick.empty:
        pick, label = sub, "混合切分"
    pick = pick.dropna(subset=["bz_sales"]).nlargest(5, "bz_sales")
    total = pick["bz_sales"].sum()
    if total <= 0 or pick.empty:
        return ""
    lines = [f"◆ 公司业务构成({label},报告期{str(end)[:10]},占前五项合计比)"]
    for _, r in pick.iterrows():
        share = r["bz_sales"] / total
        margin = ""
        if pd.notna(r.get("bz_profit")) and r["bz_sales"] > 0:
            margin = f",利润率{r['bz_profit'] / r['bz_sales']:.0%}"
        lines.append(f"- {str(r['bz_item']).strip()}: 占比{share:.0%}{margin}")
    return "\n".join(lines)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    days = decision_days(C.PILOT_POOL_MONTH, C.PILOT_MONTH_END)
    pool = sorted(set(pd.read_parquet(
        C.POOL_DIR / f"broker_recommend_{C.PILOT_POOL_MONTH}.parquet")["ts_code"]))
    # 一次取全史(池内),按决策日做 as-of 最新报告期
    mb = load_event_feed("fina_mainbz", start="2015-01-01", end=days[-1],
                         instruments=pool)
    logger.info("mainbz rows for pool: %d", len(mb))
    rows = []
    for day in days:
        cutoff = pd.Timestamp(day)
        vis = mb[mb["visible_at"] <= cutoff]
        for code in pool:
            sub = vis[vis["ts_code"] == code]
            if sub.empty:
                continue
            latest_end = sub["end_date"].max()
            txt = render_biz(sub[sub["end_date"] == latest_end])
            if txt:
                rows.append({"ts_code": code, "trade_date": day, "biz_text": txt})
    df = pd.DataFrame(rows)
    out = C.OUT_ROOT / "biz_mix" / f"biz_mix_{C.PILOT_POOL_MONTH}.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    cov = df[df.trade_date == days[-1]].ts_code.nunique()
    logger.info("biz mix -> %s | rows=%d | 末日覆盖 %d/%d", out, len(df), cov, len(pool))
    print(df[df.ts_code == '688981.SH'].iloc[-1]["biz_text"] if
          (df.ts_code == '688981.SH').any() else "(688981 无数据)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
