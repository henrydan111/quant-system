"""Probe live Tushare access tier (read-only, strictly sequential).

One-off diagnostic: after the account was upgraded 5000 -> 15000 积分, this
script asks the LIVE API which high-value endpoints (that the system does NOT
currently ingest) are now accessible, and captures the exact permission/points
message Tushare returns for the denied ones.

Design notes / safety (CLAUDE.md §6.1):
  - STRICTLY SEQUENTIAL. One call at a time. Never parallel.
  - Each probe is a single minimal call (limit small / single date / single code).
  - We do NOT reuse TushareFetcher._safe_api_call because it 30s-backoff-retries
    on any message containing "limit", and a permission-denied answer is
    definitive, not transient — retrying it 3x wastes minutes per endpoint.
    We retry ONCE only on a genuine rate-limit message.
  - Writes a JSON report to workspace/outputs/; touches no data/ partitions.

Usage:
    venv/Scripts/python.exe workspace/scripts/probe_tushare_endpoints.py
"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data_infra.fetchers import TushareFetcher  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("probe")

OUT_DIR = PROJECT_ROOT / "workspace" / "outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# A recent trading day with full data on the LIVE api, and a stable code/period.
D = "20250102"
CODE = "000001.SZ"
PERIOD = "20241231"

# (name, group, description, kwargs)  -- method resolved as pro.<name>
PROBES = [
    # ---- positive controls (account already owns these) ----
    ("daily", "control", "OHLCV (owned) — positive control", {"trade_date": D}),
    ("top_inst", "control", "龙虎榜机构明细 (owned, 5000 tier) — positive control", {"trade_date": D}),

    # ---- analyst / consensus / disclosure ----
    ("report_rc", "analyst", "卖方盈利预测明细 (analyst EPS/target/rating)", {"ts_code": CODE}),
    ("broker_recommend", "analyst", "券商月度金股", {"month": "202501"}),
    ("express", "disclosure", "业绩快报", {"ts_code": CODE}),
    ("express_vip", "disclosure", "业绩快报 VIP (all-stock)", {"period": PERIOD}),
    ("forecast_vip", "disclosure", "业绩预告 VIP (all-stock)", {"period": PERIOD}),
    ("fina_mainbz", "disclosure", "主营业务构成 (segment revenue)", {"ts_code": CODE}),
    ("fina_mainbz_vip", "disclosure", "主营业务构成 VIP", {"period": PERIOD}),
    ("disclosure_date", "disclosure", "财报披露计划日期", {"ts_code": CODE}),
    ("fina_audit", "disclosure", "财务审计意见", {"ts_code": CODE}),

    # ---- pre-computed technical factor packs ----
    ("stk_factor", "tech_factor", "技术面因子 (MACD/KDJ/RSI/BOLL…)", {"trade_date": D}),
    ("stk_factor_pro", "tech_factor", "技术面因子专业版 (复权+扩展)", {"trade_date": D}),

    # ---- money flow / smart money ----
    ("moneyflow_hsgt", "flow", "沪深港通资金流向 (whole market)", {"trade_date": D}),
    ("hsgt_top10", "flow", "沪深股通十大成交股", {"trade_date": D}),
    ("ggt_top10", "flow", "港股通十大成交股", {"trade_date": D}),
    ("moneyflow_dc", "flow", "个股资金流向 (东财)", {"trade_date": D}),
    ("moneyflow_ind_dc", "flow", "板块资金流向 (东财)", {"trade_date": D}),
    ("moneyflow_mkt_dc", "flow", "大盘资金流向 (东财)", {"trade_date": D}),

    # ---- limit-up board / hot money / 打板 ----
    ("limit_list_d", "limit_board", "涨跌停列表 D (连板/封单/成交额)", {"trade_date": D}),
    ("limit_list_ths", "limit_board", "同花顺涨跌停榜", {"trade_date": D}),
    ("hm_list", "limit_board", "游资名录", {}),
    ("hm_detail", "limit_board", "游资每日明细", {"trade_date": D}),
    ("kpl_list", "limit_board", "开盘啦榜单", {"trade_date": D}),
    ("kpl_concept", "limit_board", "开盘啦题材库", {"trade_date": D}),
    ("kpl_concept_cons", "limit_board", "开盘啦题材成分", {"trade_date": D}),

    # ---- concept / theme membership (for theme strategy framework) ----
    ("ths_index", "theme", "同花顺概念/行业指数列表", {}),
    ("ths_member", "theme", "同花顺概念成分", {}),
    ("ths_daily", "theme", "同花顺板块指数行情", {}),
    ("ths_hot", "theme", "同花顺App热榜", {"trade_date": D}),
    ("dc_index", "theme", "东方财富概念板块", {"trade_date": D}),
    ("dc_member", "theme", "东方财富板块成分", {"trade_date": D}),
    ("dc_hot", "theme", "东方财富App热榜", {"trade_date": D}),

    # ---- ownership / governance ----
    ("top10_holders", "ownership", "前十大股东", {"ts_code": CODE, "period": PERIOD}),
    ("top10_floatholders", "ownership", "前十大流通股东", {"ts_code": CODE, "period": PERIOD}),
    ("pledge_stat", "ownership", "股权质押统计", {"ts_code": CODE}),
    ("pledge_detail", "ownership", "股权质押明细", {"ts_code": CODE}),
    ("repurchase", "ownership", "股票回购", {}),
    ("share_float", "ownership", "限售股解禁", {"ts_code": CODE}),
    ("stk_managers", "ownership", "上市公司管理层", {"ts_code": CODE}),
    ("stk_rewards", "ownership", "管理层薪酬和持股", {"ts_code": CODE}),
    ("ccass_hold", "ownership", "中央结算系统持股汇总", {"trade_date": D}),
    ("ccass_hold_detail", "ownership", "中央结算系统持股明细", {"trade_date": D}),

    # ---- institutional research ----
    ("stk_surv", "research", "机构调研表", {"ts_code": CODE}),

    # ---- index / industry analytics ----
    ("index_dailybasic", "index", "大盘指数每日指标 (PE/PB)", {"trade_date": D}),
    ("sw_daily", "index", "申万行业日线行情", {}),
    ("ci_daily", "index", "中信行业指数行情", {}),
    ("daily_info", "index", "市场交易统计 (每日)", {"trade_date": D}),
    ("index_global", "index", "国际指数", {"trade_date": D}),

    # ---- chip distribution detail / auxiliary market ----
    ("cyq_chips", "market_aux", "每日筹码分布 (per-price-level)", {"ts_code": CODE, "trade_date": D}),
    ("bak_daily", "market_aux", "备用行情 (含更多字段)", {"trade_date": D}),
    ("stk_auction_c", "market_aux", "收盘集合竞价", {"trade_date": D}),

    # ---- intraday ----
    ("stk_mins", "intraday", "分钟线 (1/5/15/30/60min)",
     {"ts_code": CODE, "freq": "60min", "start_date": "20250102 09:00:00", "end_date": "20250102 15:00:00"}),

    # ---- adjacent asset classes (scope check only) ----
    ("cb_daily", "other_asset", "可转债日线", {"trade_date": D}),
    ("fund_nav", "other_asset", "基金净值", {"ts_code": "510300.SH"}),
]

PERM_TOKENS = ("没有访问该接口的权限", "权限", "积分", "permission", "不足")
RATE_TOKENS = ("每天最多", "每分钟最多", "抱歉，您每", "frequent", "请求过于频繁")


def classify(name, pro, kwargs):
    """Return (status, message, shape, cols)."""
    fn = getattr(pro, name, None)
    if fn is None:
        return "NO_METHOD", f"pro.{name} not in installed tushare SDK", None, None
    for attempt in range(2):
        try:
            df = fn(**kwargs)
            if df is None:
                return "ACCESS_EMPTY", "returned None", None, None
            shape = list(df.shape)
            cols = list(df.columns)[:25]
            return "ACCESS", f"{shape[0]} rows x {shape[1]} cols", shape, cols
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            low = msg.lower()
            if any(t in msg for t in RATE_TOKENS) or "frequent" in low:
                if attempt == 0:
                    logger.warning("rate-limited on %s; one backoff then retry", name)
                    time.sleep(20)
                    continue
                return "RATE_LIMIT", msg, None, None
            if any(t in msg for t in PERM_TOKENS) or "permission" in low:
                return "DENIED", msg, None, None
            # permission passed but params/other wrong -> endpoint IS accessible
            return "ACCESS_PARAM", msg, None, None
    return "UNKNOWN", "exhausted", None, None


def main():
    fetcher = TushareFetcher(config_path=str(PROJECT_ROOT / "config.yaml"))
    pro = fetcher.pro
    results = []
    total = len(PROBES)
    for i, (name, group, desc, kwargs) in enumerate(PROBES, 1):
        status, message, shape, cols = classify(name, pro, kwargs)
        logger.info("[%2d/%2d] %-20s %-12s -> %s", i, total, name, group, status)
        results.append({
            "endpoint": name, "group": group, "description": desc,
            "kwargs": kwargs, "status": status, "message": message,
            "shape": shape, "columns": cols,
        })
        time.sleep(1.3)  # respect rate limit, sequential

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = OUT_DIR / f"tushare_endpoint_probe_{stamp}.json"
    out.write_text(json.dumps({"probed_at_utc": stamp, "results": results},
                              ensure_ascii=False, indent=2), encoding="utf-8")

    # console summary grouped by status
    print("\n" + "=" * 78)
    by_status = {}
    for r in results:
        by_status.setdefault(r["status"], []).append(r)
    for status in ("ACCESS", "ACCESS_PARAM", "ACCESS_EMPTY", "DENIED", "RATE_LIMIT",
                   "NO_METHOD", "UNKNOWN"):
        rows = by_status.get(status, [])
        if not rows:
            continue
        print(f"\n### {status}  ({len(rows)})")
        for r in rows:
            extra = f"  [{r['message']}]" if status not in ("ACCESS",) else f"  ({r['message']})"
            print(f"  - {r['endpoint']:<20} {r['description']}{extra}")
    print("\nwrote", out)


if __name__ == "__main__":
    main()
