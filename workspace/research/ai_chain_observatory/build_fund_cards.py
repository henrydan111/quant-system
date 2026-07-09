# SCRIPT_STATUS: ACTIVE — AI 链路观察站 Block B:基本面卡片(Class-D 试点,非证据)
"""Deterministic 基本面卡片 per (pool name, decision day) — the fundamental
persona's ONLY input (BLUEPRINT Layer-3 最简实现,DESIGN.md §4).

数据门:pit_research_loader.load_pit_signal_panel(lag=1,字段注册表校验,fail-closed)
— 绝不手搓 PIT 对齐(CLAUDE.md §3.2)。卡片由代码渲染成紧凑中文文本,内容哈希供
replay 缓存;LLM 只读卡片,不碰原始账本。

字段(11,均 sandbox_screening 批准,2026-07-08 探测确认):
  盈利质量: roe_waa · grossprofit_margin · netprofit_margin · ocf_to_or
  成长动能: or_yoy · netprofit_yoy · dt_netprofit_yoy · basic_eps_yoy
  偿债结构: debt_to_assets · current_ratio · assets_turn

用法:
  venv/Scripts/python.exe workspace/research/ai_chain_observatory/build_fund_cards.py
"""
from __future__ import annotations

import hashlib
import json
import logging
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from data_infra.pit_research_loader import load_pit_signal_panel  # noqa: E402
from data_infra.golden_stock_universe import load_golden_stock_events  # noqa: E402

OUT_DIR = PROJECT_ROOT / "workspace" / "outputs" / "ai_chain_observatory"
CARDS_PATH = OUT_DIR / "fund_cards.parquet"
TRADE_CAL = PROJECT_ROOT / "data" / "reference" / "trade_cal.parquet"
POOL_MONTH = "202501"
MONTH_END = "20250131"

#: (field, 中文标签, 单位) — 渲染顺序即卡片顺序
CARD_FIELDS = [
    ("roe_waa",            "ROE(加权)",       "%"),
    ("grossprofit_margin", "毛利率",           "%"),
    ("netprofit_margin",   "净利率",           "%"),
    ("ocf_to_or",          "经营现金流/营收",  "%"),
    ("or_yoy",             "营收同比",         "%"),
    ("netprofit_yoy",      "净利润同比",       "%"),
    ("dt_netprofit_yoy",   "扣非净利同比",     "%"),
    ("basic_eps_yoy",      "EPS同比",          "%"),
    ("debt_to_assets",     "资产负债率",       "%"),
    ("current_ratio",      "流动比率",         "倍"),
    ("assets_turn",        "总资产周转率",     "次"),
]

logger = logging.getLogger("fund_cards")


def decision_days() -> list[str]:
    """202501 池激活日..月末的交易日(与 replay 相同的日历切法)。"""
    events = load_golden_stock_events()
    cyc = events.loc[events["month"] == POOL_MONTH]
    if cyc.empty:
        raise RuntimeError(f"no golden pool rows for {POOL_MONTH}")
    activation = pd.Timestamp(cyc["activation_date"].iloc[0]).strftime("%Y%m%d")
    cal = pd.read_parquet(TRADE_CAL)
    opens = cal.loc[cal["is_open"] == 1, "cal_date"].astype(str)
    return sorted(opens[(opens >= activation) & (opens <= MONTH_END)])


def render_card(code: str, day: str, values: dict[str, float]) -> str:
    lines = [f"【基本面卡片】{code} 截至 {day}(最近已披露报告期,PIT lag-1)"]
    for field, label, unit in CARD_FIELDS:
        v = values.get(field)
        if v is None or pd.isna(v):
            lines.append(f"- {label}: 无数据")
        elif unit == "%":
            lines.append(f"- {label}: {v:.1f}%")
        else:
            lines.append(f"- {label}: {v:.2f}{unit}")
    return "\n".join(lines)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    events = load_golden_stock_events()
    pool = sorted(set(events.loc[events["month"] == POOL_MONTH, "ts_code"]))
    days = decision_days()
    logger.info("pool=%d names | %d decision days: %s..%s",
                len(pool), len(days), days[0], days[-1])

    fields = [f for f, _, _ in CARD_FIELDS]
    panels = load_pit_signal_panel(fields, days, instruments=pool)

    rows = []
    for day in days:
        for code in pool:
            vals = {}
            for f in fields:
                panel = panels[f"${f}"] if f"${f}" in panels else panels.get(f)
                if panel is None:
                    continue
                col = code if code in panel.columns else code.upper()
                if col in panel.columns and day in panel.index:
                    vals[f] = panel.loc[day, col]
            card = render_card(code, day, vals)
            n_data = sum(1 for f in fields if f in vals and pd.notna(vals[f]))
            # 缓存哈希只盖"数值负载"(不含日期行)—— 否则 截至{day} 使哈希每日必变,
            # fund-score 缓存全灭(149×16 次调用而非 ~149 次)
            values_payload = "|".join(
                f"{f}={vals.get(f)}" for f in fields
                if f in vals and pd.notna(vals.get(f)))
            rows.append({
                "ts_code": code, "trade_date": day, "card_text": card,
                "n_fields_present": n_data,
                "card_hash": hashlib.sha256(
                    (code + "|" + values_payload).encode("utf-8")).hexdigest()[:16],
            })
    df = pd.DataFrame(rows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(CARDS_PATH, index=False)

    cov = df.groupby("trade_date")["n_fields_present"].agg(["mean", "min"])
    logger.info("cards=%d | fields/card mean=%.1f min=%d | -> %s",
                len(df), df["n_fields_present"].mean(),
                df["n_fields_present"].min(), CARDS_PATH)
    summary = {
        "pool_names": len(pool), "decision_days": days,
        "cards": len(df),
        "mean_fields_present": round(float(df["n_fields_present"].mean()), 2),
        "cards_all_empty": int((df["n_fields_present"] == 0).sum()),
        "evidence_class": "NON_EVIDENTIARY_PILOT",
    }
    (OUT_DIR / "fund_cards_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(cov.to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
