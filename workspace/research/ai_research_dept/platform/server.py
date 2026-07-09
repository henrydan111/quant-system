# SCRIPT_STATUS: ACTIVE — 情报中心本地 Web 平台 MVP(只读;INTEL_CENTER §6)
"""Read-only local platform: 热点榜 / 事件流浏览器 / 个股档案.

硬边界(GPT Minor-5 + dashboard 宪章):
- GET-only(其余方法 405);无任何写路径/重打标/config修改/LLM触发;
- 本进程 **不 import** 任何评分/LLM编排模块(只 pandas + stdlib + 引擎路径常量);
- 每页 evidence_class 横幅 + config/snapshot 哈希页脚。

用法: venv/Scripts/python.exe workspace/research/ai_research_dept/platform/server.py [port]
默认 http://127.0.0.1:8865
"""
from __future__ import annotations

import json
import logging
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from workspace.research.ai_research_dept.engine import config as C  # noqa: E402

logger = logging.getLogger("platform")
STATIC = Path(__file__).parent / "static"
MONTH = C.PILOT_POOL_MONTH


class Data:
    """启动时加载全部 parquet(量小,内存服务);只读。"""

    def __init__(self):
        self.events = pd.read_parquet(C.EVENT_DIR / f"events_{MONTH}.parquet")
        self.events["subject_codes"] = self.events["subject_codes"].apply(list)
        self.events["industry_tags"] = self.events["industry_tags"].apply(list)
        self.facts = pd.read_parquet(C.FACT_DIR / f"fact_table_{MONTH}.parquet")
        self.pv = pd.read_parquet(C.PV_DIR / f"pv_pack_{MONTH}.parquet")
        self.retr = pd.read_parquet(C.OUT_ROOT / "retrieval" / f"retrieval_{MONTH}.parquet")
        self.attn = pd.read_parquet(C.OUT_ROOT / "attention" / f"attention_{MONTH}.parquet")
        sb = pd.read_parquet(C.PROJECT_ROOT / "data" / "reference" / "stock_basic.parquet",
                             columns=["ts_code", "name"])
        self.names = dict(zip(sb.ts_code, sb.name))
        mem = pd.read_parquet(C.PROJECT_ROOT / "data" / "universe"
                              / "industry_sw2021_members" / "industry_sw2021_members.parquet",
                              columns=["l1_code", "l1_name"]).drop_duplicates()
        self.ind_names = dict(zip(mem.l1_code, mem.l1_name))
        self.days = sorted(self.attn.trade_date.unique())
        self.snapshot = str(self.retr.retrieval_profile_snapshot_id.iloc[0])
        logger.info("loaded: %d events / %d facts / %d pv / %d retr / %d attn",
                    len(self.events), len(self.facts), len(self.pv),
                    len(self.retr), len(self.attn))

    def meta(self):
        return {"month": MONTH, "days": self.days,
                "event_types": sorted(self.events.event_type.unique()),
                "industries": self.ind_names,
                "evidence_class": C.EVIDENCE_CLASS_REPLAY,
                "config_hash": C.config_hash(), "snapshot": self.snapshot}

    def hotboard(self, day: str):
        d = self.attn[self.attn.trade_date == day].nlargest(80, "attention")
        out = []
        for _, r in d.iterrows():
            out.append({"ts_code": r.ts_code, "name": self.names.get(r.ts_code, ""),
                        "attention": r.attention, "trend": None if pd.isna(r.trend) else r.trend,
                        "ev_density": round(float(r.ev_density), 2),
                        "turnover_p": round(float(r.turnover_p), 2),
                        "top_list": round(float(r.top_list), 2),
                        "limit_lang": round(float(r.limit_lang), 2)})
        return out

    def query_events(self, q: dict):
        ev = self.events
        if q.get("type"):
            ev = ev[ev.event_type == q["type"][0]]
        if q.get("min_imp"):
            ev = ev[ev.importance_0_5 >= int(q["min_imp"][0])]
        if q.get("direction"):
            ev = ev[ev.direction == q["direction"][0]]
        if q.get("industry"):
            ind = q["industry"][0]
            ev = ev[ev.industry_tags.apply(lambda x: ind in x)]
        if q.get("code"):
            code = q["code"][0].upper()
            ev = ev[ev.subject_codes.apply(lambda x: code in x)]
        if q.get("q"):
            ev = ev[ev.title.str.contains(q["q"][0], na=False)]
        ev = ev.sort_values("visible_at", ascending=False).head(300)
        out = []
        for _, r in ev.iterrows():
            out.append({"visible_at": str(r.visible_at)[:16], "type": r.event_type,
                        "title": r.title, "importance": int(r.importance_0_5),
                        "direction": r.direction,
                        "subjects": [f"{c} {self.names.get(c, '')}" for c in r.subject_codes[:3]],
                        "industries": [self.ind_names.get(i, i) for i in r.industry_tags],
                        "source": r.source})
        return out

    def stock(self, code: str, day: str):
        code = code.upper()
        facts = self.facts[(self.facts.ts_code == code) & (self.facts.trade_date == day)]
        pv = self.pv[(self.pv.ts_code == code) & (self.pv.trade_date == day)]
        retr = self.retr[(self.retr.ts_code == code) & (self.retr.trade_date == day)] \
            .sort_values("relevance", ascending=False)
        attn = self.attn[(self.attn.ts_code == code) & (self.attn.trade_date == day)]
        return {
            "ts_code": code, "name": self.names.get(code, ""), "date": day,
            "attention": None if attn.empty else float(attn.attention.iloc[0]),
            "facts": [{"field": r.field, "value": r.value,
                       "industry_pctl": None if pd.isna(r.industry_pctl) else round(float(r.industry_pctl), 3),
                       "industry_n": int(r.industry_n), "scope": r.pctl_scope,
                       "hist_pctl": None if pd.isna(r.hist_pctl) else round(float(r.hist_pctl), 3)}
                      for _, r in facts.iterrows()],
            "pv": [{"subcard": r["subcard"], "item": r["item"], "value": r["value"],
                    "state": r["state"],
                    "pctl": None if r["pctl"] is None or pd.isna(r["pctl"]) else float(r["pctl"])}
                   for _, r in pv.iterrows()],
            "retrieval": [{"channel": r.channel, "type": r.event_type, "title": r.title,
                           "direction": r.direction, "relevance": float(r.relevance)}
                          for _, r in retr.iterrows()],
        }


DATA: Data | None = None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        logger.info("%s %s", self.address_string(), fmt % args)

    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj):
        self._send(200, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def do_POST(self):   # 只读边界:一切写方法拒绝
        self._send(405, b"read-only platform", "text/plain")
    do_PUT = do_DELETE = do_PATCH = do_POST

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        try:
            if u.path == "/api/meta":
                return self._json(DATA.meta())
            if u.path == "/api/hotboard":
                return self._json(DATA.hotboard(q.get("date", [DATA.days[-1]])[0]))
            if u.path == "/api/events":
                return self._json(DATA.query_events(q))
            if u.path == "/api/stock":
                return self._json(DATA.stock(q["code"][0],
                                             q.get("date", [DATA.days[-1]])[0]))
            # static
            name = "index.html" if u.path == "/" else u.path.lstrip("/")
            f = (STATIC / name).resolve()
            if f.is_file() and STATIC.resolve() in f.parents:
                ctype = ("text/html; charset=utf-8" if f.suffix == ".html"
                         else "text/css" if f.suffix == ".css" else "application/javascript")
                return self._send(200, f.read_bytes(), ctype)
            self._send(404, b"not found", "text/plain")
        except Exception as e:  # noqa: BLE001
            logger.exception("request failed")
            self._send(500, str(e).encode(), "text/plain")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    global DATA
    DATA = Data()
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8865
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    logger.info("intel platform (read-only) -> http://127.0.0.1:%d", port)
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
