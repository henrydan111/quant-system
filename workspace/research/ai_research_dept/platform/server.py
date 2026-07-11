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
import re
import logging
import sys
from collections.abc import Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from workspace.research.ai_research_dept.engine import config as C  # noqa: E402
# 边界说明:cards=纯渲染器,llm_config=纯配置字典(call() 才会 lazy-import LLM 客户端,
# 平台绝不调 call)——均不违反"平台不 import 评分/编排执行"的硬边界(INTEL_CENTER §6)
from workspace.research.ai_research_dept.engine.cards import (  # noqa: E402
    COMPOSITE_W, SEAT_WEIGHTS, disclosure_status,
    render_fund_card, render_news_card, render_pv_card,
)
from workspace.research.ai_research_dept.engine.llm_config import TASK_LLM  # noqa: E402
from workspace.research.ai_research_dept.engine.integrity import (  # noqa: E402
    sha256_json, verify_archive_body, verify_llm_route, verify_manifest_body,
    verify_publishable_archive, verify_scoring_contract,
)

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "engine" / "prompts"
#: 现行渲染器/prompt 对应的链版本(GPT Blocker-1:平台按版本取数;
#  与 analyst_chain.CHAIN_VERSION 一致性由 workspace 测试断言——平台进程禁 import 编排模块)
RENDER_VERSION = "chain_v3.1"
#: legacy 显式 allowlist(复审#4 B1:legacy 绝不由"缺字段"推断)——
#  这些历史版本产生于封印 schema 之前,只做结构性校验
LEGACY_CHAINS = frozenset({"chain_v1.0", "chain_v2.1", "chain_v2.2", "chain_v2.3"})
#: schema-1 封印(无 executed_contract_sha256)只承认 chain_v2.4 这一个历史版本
#  (复审#6 Major:未来版本自声明 schema=1 曾可绕过执行契约绑定)
SCHEMA1_CHAINS = frozenset({"chain_v2.4"})
SEAT_PROMPT_FILES = {"fund": "fund_analyst_v2.txt", "tech": "tech_analyst_v2.txt",
                     "news": "news_analyst_v2.txt", "bear": "bear_analyst_v2.txt"}

_DAY_RE = re.compile(r"^\d{8}$")
_CODE_RE = re.compile(r"^\d{6}\.(SH|SZ|BJ)$")


def validate_full_month_status(status, manifest, version_archives) -> tuple[bool, list]:
    """月度完成标记验证(复审#6 B2,纯函数供测试):marker 必须与 manifest.job_spec
    及**已验证磁盘档案**的封印集重算完全一致——scope/job 哈希/expected/complete 计数/
    archive_set_sha256 五重对照;任何不符 = 不可信(伪造 2384/2384 或事后删档均被点名)。
    version_archives: {(ts_code, day): archive}(只含已通过封印+语义验证的档案)。"""
    js = (manifest or {}).get("job_spec") or {}
    if not isinstance(status, dict) or not js:
        return False, ["marker 或 manifest.job_spec 缺失/非对象"]
    seals = []
    for day in js.get("days", []):
        for code in js.get("codes", []):
            a = version_archives.get((code, day))
            if a is not None:
                seals.append([day, str(code).replace(".", "_"),
                              a.get("archive_sha256")])
    problems = []
    if status.get("scope_kind") != "full_month":
        problems.append("scope_kind 非 full_month")
    if status.get("job_set_sha256") != js.get("job_set_sha256"):
        problems.append("job_set_sha256 与 manifest job_spec 不符")
    if status.get("expected") != js.get("expected"):
        problems.append("expected 与 job_spec 不符")
    if status.get("complete") != len(seals):
        problems.append(f"complete={status.get('complete')} "
                        f"与磁盘已验证档案数 {len(seals)} 不符")
    if status.get("archive_set_sha256") != sha256_json(sorted(seals)):
        problems.append("archive_set_sha256 与磁盘封印集重算不符")
    # 复审#7 B4:status 文本本身也必须对照重算——把 "partial" 改成 "complete"
    # 而不动其余字段曾原样通过
    actual_status = ("complete" if len(seals) == js.get("expected")
                     else "partial")
    if status.get("status") != actual_status:
        problems.append(
            f"status={status.get('status')} 与重算状态 {actual_status} 不符")
    return (not problems), problems


def safe_raw_dir(base_dir: Path, chains: set[str], chain: str, day: str,
                 code: str, attempt: int | None = None) -> Path | None:
    """raw 路径防穿越(复审#2 Major-2):chain 必须在已知集合、day/code 严格格式,
    解析后路径必须仍在版本根内(day=../chain_v1.0/... 类注入一律拒绝)。
    v2.3 起 raw 住 attempts/<code>/attempt_NNNN/raw(发布档案带 attempt 号);
    legacy 版本仍为 day/raw/<code>。"""
    if chain not in chains or not _DAY_RE.match(day or "") \
            or not _CODE_RE.match(code or ""):
        return None
    if attempt is not None and not (isinstance(attempt, int) and 1 <= attempt <= 9999):
        return None
    base = base_dir.resolve()
    code_u = code.replace(".", "_")
    if attempt is not None:
        p = (base / chain / day / "attempts" / code_u
             / f"attempt_{attempt:04d}" / "raw").resolve()
    else:
        p = (base / chain / day / "raw" / code_u).resolve()
    return p if p.is_relative_to(base / chain) else None

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
        biz_path = C.OUT_ROOT / "biz_mix" / f"biz_mix_{MONTH}.parquet"
        self.biz = pd.read_parquet(biz_path) if biz_path.exists() else pd.DataFrame(
            columns=["ts_code", "trade_date", "biz_text"])
        rg_path = C.OUT_ROOT / "regime" / f"regime_{MONTH}.parquet"
        self.regime = pd.read_parquet(rg_path) if rg_path.exists() else pd.DataFrame(
            columns=["trade_date", "card_text", "regime", "narrative", "watch", "llm_ok"])
        sr_path = C.FACT_DIR / f"fund_series_{MONTH}.parquet"
        self.series = pd.read_parquet(sr_path) if sr_path.exists() else pd.DataFrame(
            columns=["ts_code", "trade_date", "field", "seq", "value"])
        sb = pd.read_parquet(C.PROJECT_ROOT / "data" / "reference" / "stock_basic.parquet",
                             columns=["ts_code", "name"])
        self.names = dict(zip(sb.ts_code, sb.name))
        mem = pd.read_parquet(C.PROJECT_ROOT / "data" / "universe"
                              / "industry_sw2021_members" / "industry_sw2021_members.parquet",
                              columns=["l1_code", "l1_name"]).drop_duplicates()
        self.ind_names = dict(zip(mem.l1_code, mem.l1_name))
        self.days = sorted(self.attn.trade_date.unique())
        self.pool = sorted(set(self.attn.ts_code))
        self.snapshot = str(self.retr.retrieval_profile_snapshot_id.iloc[0])
        # 研究档案:按链版本目录隔离(Blocker-1)+ **加载即验证**(复审#3 B2 + #4 B1:
        # sealed_required 由 manifest 驱动,legacy=显式 allowlist,验证状态**外置**
        # 不污染封印正文;拒载计数进 integrity_status)
        self.archives: dict[tuple[str, str, str], dict] = {}
        self.archive_verification: dict[tuple[str, str, str], str] = {}
        self.manifests: dict[str, dict] = {}
        self.integrity_status: dict[str, dict] = {}
        self.full_month_status: dict[str, dict] = {}
        chain_dir = C.OUT_ROOT / "analyst_chain"
        if chain_dir.exists():
            for vdir in sorted(chain_dir.iterdir()):
                if not vdir.is_dir() or not vdir.name.startswith("chain_v"):
                    continue
                st = {"loaded": 0, "rejected": 0, "reasons": []}
                self.integrity_status[vdir.name] = st
                mf = vdir / "manifest.json"
                try:
                    manifest = json.loads(mf.read_text(encoding="utf-8")) \
                        if mf.exists() else {}
                except (json.JSONDecodeError, ValueError, OSError) as e:
                    st["rejected"] += 1
                    st["reasons"].append(f"manifest 解析失败: {e}")
                    continue
                # 复审#5 B2:legacy 只认显式 allowlist;**非 legacy 版本无条件要求
                # 封印**——manifest 自声明 sealed_required=False 不是降级许可,而是
                # 整版本拒载理由(自声明字段不得决定校验强度)
                is_legacy = vdir.name in LEGACY_CHAINS and \
                    not manifest.get("sealed_required")
                if not is_legacy:
                    mp = verify_manifest_body(manifest)
                    schema = manifest.get("integrity_schema")
                    if not mp and (manifest.get("sealed_required") is not True
                                   or not isinstance(schema, int) or schema < 1
                                   or not manifest.get("manifest_sha256")):
                        mp = ["非 legacy 版本必须声明 sealed_required=True + "
                              "integrity_schema>=1 + manifest_sha256(自声明降级封死)"]
                    # 复审#6 Major:schema-1 只承认 chain_v2.4——未来版本自声明
                    # schema=1 不再能绕过 executed_contract 绑定
                    if not mp and schema == 1 and vdir.name not in SCHEMA1_CHAINS:
                        mp = ["integrity_schema=1 仅允许 chain_v2.4;"
                              "后续版本必须 schema>=2"]
                    # 复审#6 B1:评分契约不完备 = 整版本拒载(语义校验依赖它,
                    # 缺契约曾让空档案 sealed_ok)
                    if not mp:
                        mp = verify_scoring_contract(
                            manifest.get("scoring_contract"))
                    # 复审#8 Major + SHIP-Minor:routing 容器先验类型再解引用
                    # (truthy 非 Mapping 容器曾 AttributeError 炸掉整个 Data()
                    # 初始化,而不是只拒该版本)——两腿值类型与引擎同一把尺
                    if not mp:
                        routing = manifest.get("routing")
                        if not isinstance(routing, Mapping):
                            mp = ["routing: routing 不是对象"]
                        else:
                            for leg in ("scoring", "bear"):
                                rp = verify_llm_route(routing.get(leg))
                                if rp:
                                    mp = [f"routing[{leg}]: {';'.join(rp)}"]
                                    break
                    if mp or manifest.get("chain_version") != vdir.name:
                        st["rejected"] += 1
                        st["reasons"].append(
                            f"manifest: {';'.join(mp) or 'chain_version 与目录不符'}")
                        logger.warning("拒载 %s manifest: %s", vdir.name, st["reasons"][-1])
                        continue
                require_sealed = not is_legacy
                seal_schema = manifest.get("integrity_schema") or 1
                scoring = manifest.get("scoring_contract") or {}
                self.manifests[vdir.name] = manifest
                for day_dir in vdir.iterdir():
                    if not day_dir.is_dir() or day_dir.name == "attempts" \
                            or not day_dir.name.isdigit():
                        continue
                    for fj in day_dir.glob("*.json"):
                        try:
                            a = json.loads(fj.read_text(encoding="utf-8"))
                        except (json.JSONDecodeError, ValueError, OSError) as e:
                            st["rejected"] += 1
                            st["reasons"].append(f"{day_dir.name}/{fj.name}: 解析失败 {e}")
                            continue
                        problems = verify_archive_body(
                            a, require_sealed=require_sealed,
                            expect_chain=vdir.name, expect_date=day_dir.name,
                            expect_stem=fj.stem,
                            expect_manifest_fp=manifest.get("manifest_fp")
                            if require_sealed else None,
                            expect_executed_contract=manifest.get("manifest_sha256")
                            if require_sealed and seal_schema >= 2 else None,
                            seal_schema=seal_schema)
                        # 复审#5 Major-3 + #6 B1 + #7 B3:封印档案**无条件**过
                        # 共享合格判定 verify_publishable_archive——与引擎终局重算
                        # 同一把尺(平台只跑较弱语义校验曾把 bear.schema_valid=False
                        # 的档案计入完整月份)
                        if require_sealed and not problems:
                            problems = verify_publishable_archive(
                                a, scoring["seat_weights"],
                                scoring["composite_weights"])
                        if problems:
                            st["rejected"] += 1
                            st["reasons"].append(
                                f"{day_dir.name}/{fj.name}: {';'.join(problems)[:120]}")
                            logger.warning("拒载归档 %s/%s/%s: %s", vdir.name,
                                           day_dir.name, fj.name, ";".join(problems))
                            continue
                        key = (vdir.name, str(a.get("ts_code")), str(a.get("date")))
                        self.archives[key] = a         # 不写入 a 本体(封印不被污染)
                        self.archive_verification[key] = \
                            "sealed_ok" if require_sealed else "legacy_structural"
                        st["loaded"] += 1
                # 月度完成标记(复审#5 B3 + #6 B2):**验证后才暴露**——对照
                # manifest.job_spec + 已加载已验证档案的封印集重算;伪造/过期
                # marker 一律标 integrity_failed(档案加载之后才能做这一步)
                fms = vdir / "full_month_status.json"
                if fms.exists():
                    try:
                        raw_status = json.loads(fms.read_text(encoding="utf-8"))
                    except (json.JSONDecodeError, ValueError, OSError):
                        raw_status = None
                    varch = {(c, d): a for (v, c, d), a in self.archives.items()
                             if v == vdir.name}
                    ok, fm_problems = validate_full_month_status(
                        raw_status, manifest, varch)
                    if ok:
                        self.full_month_status[vdir.name] = raw_status
                    else:
                        self.full_month_status[vdir.name] = {
                            "status": "integrity_failed",
                            "problems": fm_problems[:5]}
                        st["reasons"].append(
                            "full_month_status: " + ";".join(fm_problems)[:120])
                        logger.warning("拒信 %s full_month_status: %s",
                                       vdir.name, ";".join(fm_problems))
                st["reasons"] = st["reasons"][:10]
        self.chain_versions = sorted(self.manifests)          # 字典序=版本序
        # 复审#4 Major-4:RENDER_VERSION manifest 损坏时**不得静默回退旧版本**——
        # default 只认现行版本;不健康则置空并由 integrity_status 暴露
        self.default_chain = RENDER_VERSION if RENDER_VERSION in self.manifests \
            else (self.chain_versions[-1] if self.chain_versions
                  and not (chain_dir / RENDER_VERSION).exists() else "")
        self.archive_days_by_v = {v: sorted({d for (vv, _, d) in self.archives if vv == v})
                                  for v in self.chain_versions}
        logger.info("loaded: %d events / %d facts / %d pv / %d retr / %d attn",
                    len(self.events), len(self.facts), len(self.pv),
                    len(self.retr), len(self.attn))

    def meta(self):
        return {"month": MONTH, "days": self.days,
                "archive_days": self.archive_days_by_v.get(self.default_chain, []),
                "chain_versions": self.chain_versions,
                "default_chain": self.default_chain,
                "render_version": RENDER_VERSION,
                "integrity_status": self.integrity_status,
                "full_month_status": self.full_month_status,
                "archive_days_by_version": self.archive_days_by_v,
                "pool": [{"code": c, "name": self.names.get(c, "")} for c in self.pool],
                "event_types": sorted(self.events.event_type.unique()),
                "industries": self.ind_names,
                "evidence_class": C.EVIDENCE_CLASS_REPLAY,
                "config_hash": C.config_hash(), "snapshot": self.snapshot}

    def archive_list(self, day: str, chain: str):
        out = []
        for (v, code, d), a in self.archives.items():
            if d != day or v != chain:
                continue
            j, b = a.get("judge", {}), a.get("bear", {})
            out.append({"ts_code": code, "name": self.names.get(code, ""),
                        "composite": j.get("composite"), "adj": j.get("composite_adj"),
                        "dispersion": j.get("dispersion"),
                        "flags": j.get("divergence_flags", []),
                        "n_refs": len(b.get("refutations", [])),
                        "kill": b.get("kill_switches", [])[:1]})
        out.sort(key=lambda x: -(x["adj"] if x["adj"] is not None else -1))
        return out

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

    def stock(self, code: str, day: str, chain: str | None = None):
        code = code.upper()
        chain = chain or self.default_chain
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
            "archive": self.archives.get((chain, code, day)),
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
            if u.path == "/api/archives":
                chain = q.get("chain", [DATA.default_chain])[0]
                if DATA.manifests and chain not in DATA.manifests:
                    return self._send(400, b"unknown chain version", "text/plain")
                vdays = DATA.archive_days_by_v.get(chain, [])
                day = q.get("date", [vdays[-1] if vdays else ""])[0]
                return self._json(DATA.archive_list(day, chain))
            if u.path == "/api/dept":
                # 投研分析部:每席 输入卡/Prompt/原始输出/档案 —— 按链版本取数(Blocker-1)。
                # 完成档案 → 展示**归档快照**(绝不重渲,复审#2 B1);无档案且为现行版本
                # → 重渲预览;旧版本 → 档案+raw+说明
                code, day = q["code"][0].upper(), q["date"][0]
                chain = q.get("chain", [DATA.default_chain])[0]
                if (DATA.manifests and chain not in DATA.manifests) \
                        or not _DAY_RE.match(day) or not _CODE_RE.match(code):
                    return self._send(400, b"invalid chain/date/code", "text/plain")
                arch = DATA.archives.get((chain, code, day))
                cards, cards_source = {}, ""
                if arch and arch.get("cards"):
                    # 归档精确输入快照(v2.2+ 档案自带)
                    cards = {"fund": arch["cards"].get("fund_card", ""),
                             "tech": arch["cards"].get("pv_card", ""),
                             "news": arch["cards"].get("news_card", "")}
                    if arch.get("market_context"):
                        cards["market_context"] = arch["market_context"]
                    cards_source = "archive_snapshot"
                elif chain == RENDER_VERSION or not DATA.chain_versions:
                    cards_source = "live_preview(无档案,现行渲染器)"
                    f = DATA.facts[(DATA.facts.ts_code == code) & (DATA.facts.trade_date == day)]
                    p = DATA.pv[(DATA.pv.ts_code == code) & (DATA.pv.trade_date == day)]
                    r = DATA.retr[(DATA.retr.ts_code == code) & (DATA.retr.trade_date == day)]
                    b = DATA.biz[(DATA.biz.ts_code == code) & (DATA.biz.trade_date == day)]
                    biz_text = b["biz_text"].iloc[0] if len(b) else None
                    ser = DATA.series[(DATA.series.ts_code == code)
                                      & (DATA.series.trade_date == day)]
                    disc = disclosure_status(r[r["channel"] == "direct"], day) \
                        if not r.empty else None
                    # v3.1 B3:渲染器返回 (text, ids);预览只取文本
                    cards = {"fund": render_fund_card(f, biz_text, ser, disc)[0]
                             if not f.empty else "",
                             "tech": render_pv_card(p)[0] if not p.empty else "",
                             "news": render_news_card(r, day)[0] if not r.empty else ""}
                    rg = DATA.regime[DATA.regime.trade_date == day]
                    if len(rg):
                        cards["market_context"] = (rg["card_text"].iloc[0]
                                                   + "\nregime: " + rg["regime"].iloc[0])
                else:
                    note = DATA.manifests.get(chain, {}).get(
                        "note", "该版本输入卡不可由现行渲染器重渲;只读档案与 raw 审计文件")
                    cards = {"fund": f"({chain}:{note})", "tech": "", "news": ""}
                att = DATA.attn[(DATA.attn.ts_code == code)
                                & (DATA.attn.trade_date == day)]
                raws = {}
                raw_dir = safe_raw_dir(C.OUT_ROOT / "analyst_chain",
                                       set(DATA.manifests), chain, day, code,
                                       attempt=(arch or {}).get("attempt"))
                for seat in ("fund", "tech", "news", "bear") if raw_dir else ():
                    fp = raw_dir / f"{seat}_raw.json"
                    if fp.exists():
                        raw = json.loads(fp.read_text(encoding="utf-8"))
                        content = raw.get("choices", [{}])[0].get("message", {}).get("content", "")
                        try:
                            i, k = content.find("{"), content.rfind("}")
                            raws[seat] = json.loads(content[i:k + 1]) if i >= 0 else None
                        except (json.JSONDecodeError, ValueError):
                            raws[seat] = None
                # 契约展示(复审#3 Major-4):归档视图从**冻结 manifest** 读 prompt/
                # routing/weights,不读当前进程(旧版本档案不得配现行语义)
                mfst = DATA.manifests.get(chain, {})
                if mfst.get("effective_prompts"):
                    seat_keys = ["fund", "tech", "news", "bear"]
                    pf = mfst.get("prompt_files", [])
                    prompts = {s: mfst["effective_prompts"].get(fn, "")
                               for s, fn in zip(seat_keys, pf)}
                    sc = mfst.get("scoring_contract", {})
                    routing = mfst.get("routing", {})
                    weights = sc.get("seat_weights", {})
                    composite_w = sc.get("composite_weights", {})
                    contract_source = "frozen_manifest"
                elif chain == RENDER_VERSION:
                    prompts = {s: (PROMPTS_DIR / fn).read_text(encoding="utf-8")
                               for s, fn in SEAT_PROMPT_FILES.items()}
                    routing = {"scoring": TASK_LLM["dimension_scoring"],
                               "bear": TASK_LLM["bear_rebuttal"]}
                    weights, composite_w = SEAT_WEIGHTS, COMPOSITE_W
                    contract_source = "current_process(无冻结manifest)"
                else:
                    prompts, routing = {}, {}
                    weights, composite_w = {}, {}
                    contract_source = "unavailable(legacy版本无冻结契约)"
                return self._json({
                    "ts_code": code, "name": DATA.names.get(code, ""), "date": day,
                    "chain": chain, "chain_versions": DATA.chain_versions,
                    "cards_source": cards_source,
                    "contract_source": contract_source,
                    "verification": DATA.archive_verification.get((chain, code, day)),
                    "manifest": {k: v for k, v in mfst.items()
                                 if k != "effective_prompts"},
                    "attention": None if att.empty else float(att.attention.iloc[0]),
                    "cards": cards, "raws": raws,
                    "archive": arch,
                    "prompts": prompts, "routing": routing,
                    "weights": weights, "composite_w": composite_w,
                })
            if u.path == "/api/reasoning":
                # G5 审计视图:按需从 raw/ 读推理链;只读展示,永不入档案数据
                code, day = q["code"][0].upper(), q["date"][0]
                chain = q.get("chain", [DATA.default_chain])[0]
                arch_r = DATA.archives.get((chain, code, day))
                raw_dir = safe_raw_dir(C.OUT_ROOT / "analyst_chain",
                                       set(DATA.manifests), chain, day, code,
                                       attempt=(arch_r or {}).get("attempt"))
                if raw_dir is None:
                    return self._send(400, b"invalid chain/date/code", "text/plain")
                out = {}
                for seat in ("fund", "tech", "news", "bear"):
                    p = raw_dir / f"{seat}_raw.json"
                    if p.exists():
                        raw = json.loads(p.read_text(encoding="utf-8"))
                        msg = raw.get("choices", [{}])[0].get("message", {})
                        out[seat] = msg.get("reasoning_content") or ""
                return self._json(out)
            if u.path == "/api/regime":
                # 市场情境简报(v1.5-F):确定性卡 + LLM 归纳(锚外数字校验后)
                day = q.get("date", [DATA.days[-1]])[0]
                rg = DATA.regime[DATA.regime.trade_date == day]
                if rg.empty:
                    return self._json(None)
                r = rg.iloc[0]
                return self._json({"date": day, "regime": r["regime"],
                                   "narrative": r["narrative"], "watch": r["watch"],
                                   "card_text": r["card_text"], "llm_ok": bool(r["llm_ok"])})
            if u.path == "/api/stock":
                chain = q.get("chain", [DATA.default_chain])[0]
                if DATA.manifests and chain not in DATA.manifests:
                    return self._send(400, b"unknown chain version", "text/plain")
                return self._json(DATA.stock(q["code"][0],
                                             q.get("date", [DATA.days[-1]])[0],
                                             chain))
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
