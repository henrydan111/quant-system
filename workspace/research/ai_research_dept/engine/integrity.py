# SCRIPT_STATUS: ACTIVE — 归档完整性纯函数(链与平台共用同一把尺;零 LLM/编排依赖)
"""Archive/manifest integrity primitives (chain_v2.4, 复审#4 B1 必需封印).

只依赖 stdlib(json/hashlib)——平台进程可安全 import(INTEL_CENTER §6 硬边界)。
磁盘自称的一切不作数:manifest_fp 由正文重算、artifact_fp 由存档输入快照重算、
archive_sha256(完整 64 位)由输出正文重算。

复审#4 B1:封印检查不得是"有字段才查"的条件式——删除 cards/archive_sha256 曾把
v2.3 档案降级成 legacy 绕过全部校验。`require_sealed=True`(由 manifest 的
`sealed_required` 驱动)时必需字段缺失即硬失败;legacy 由**显式 allowlist** 指定,
绝不由"缺字段"推断。
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

#: v2.4(integrity_schema=1)起 manifest 声明 sealed_required=True 后,
#  档案必须携带的封印字段
REQUIRED_SEAL_FIELDS_SCHEMA1 = frozenset({
    "manifest_fp", "artifact_fp", "archive_sha256", "cards", "market_context",
})
#: v2.5(integrity_schema=2)+executed_contract_sha256(复审#5 B1:档案必须自证
#  执行契约,与版本 manifest 的 manifest_sha256 对照)。schema 分级是为了不让新字段
#  追溯性拒掉 v2.4 真封印档案;引擎侧只产/只验 schema 2。
REQUIRED_SEAL_FIELDS = REQUIRED_SEAL_FIELDS_SCHEMA1 | frozenset(
    {"executed_contract_sha256"})


def required_seal_fields(schema: int) -> frozenset:
    """按 manifest.integrity_schema 取必需封印字段集(≥2 = 现行全集)。"""
    return REQUIRED_SEAL_FIELDS if schema >= 2 else REQUIRED_SEAL_FIELDS_SCHEMA1


def _canon(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()


def sha16_json(obj) -> str:
    """短语义指纹(身份显示/比较用)。"""
    return hashlib.sha256(_canon(obj)).hexdigest()[:16]


def sha256_json(obj) -> str:
    """完整 64 位十六进制摘要(封印用,复审#4 minor:名为 SHA-256 就该是完整摘要)。"""
    return hashlib.sha256(_canon(obj)).hexdigest()


def manifest_core_fp(m: dict) -> str:
    return sha16_json({k: v for k, v in m.items()
                       if k not in ("created_at", "manifest_fp", "manifest_sha256")})


def manifest_full_sha256(m: dict) -> str:
    """覆盖 created_at 的完整摘要(语义指纹 manifest_fp 仍排除它)。"""
    return sha256_json({k: v for k, v in m.items() if k != "manifest_sha256"})


def input_artifact_fp(cards: dict, mc: str, manifest_fp: str) -> str:
    return sha16_json({"manifest_fp": manifest_fp,
                       "input_snapshot": {"cards": cards, "market_context": mc}})


def archive_seal(a: dict) -> str:
    return sha256_json({k: v for k, v in a.items() if k != "archive_sha256"})


def verify_manifest_body(m: dict) -> list[str]:
    """manifest 正文自校验:自称指纹必须等于正文重算;声明 integrity_schema/
    sealed_required 的 manifest 缺 manifest_fp 本身就是违规(复审#4 B1 平台旁路)。"""
    if not isinstance(m, dict):
        return ["manifest 不是对象"]
    if (m.get("integrity_schema") or m.get("sealed_required")) \
            and not m.get("manifest_fp"):
        return ["声明完整性 schema 却缺 manifest_fp"]
    recomputed = manifest_core_fp(m)
    if recomputed != m.get("manifest_fp"):
        return [f"manifest 正文与自称指纹不符(自称 {m.get('manifest_fp')} "
                f"重算 {recomputed})"]
    if m.get("manifest_sha256") is not None \
            and manifest_full_sha256(m) != m.get("manifest_sha256"):
        return ["manifest_sha256 完整摘要不符"]
    return []


def verify_archive_body(a: dict, *, require_sealed: bool = False,
                        expect_chain: str | None = None,
                        expect_date: str | None = None,
                        expect_stem: str | None = None,
                        expect_manifest_fp: str | None = None,
                        expect_executed_contract: str | None = None,
                        seal_schema: int = 2) -> list[str]:
    """归档正文自校验(返回问题列表;空=通过)。

    require_sealed=True(manifest.sealed_required 驱动):必需封印字段缺失即失败,
    且封印**无条件重算**——绝不依赖档案自称"是否 sealed"(复审#4 B1)。
    require_sealed=False 仅用于显式 allowlist 的 legacy 版本(结构性检查仍执行)。
    seal_schema:按版本 manifest 的 integrity_schema 取必需字段集(缺省=现行最严)。
    """
    if not isinstance(a, dict):
        return ["archive 不是对象"]
    problems: list[str] = []
    if require_sealed:
        missing = required_seal_fields(seal_schema) - set(a)
        if missing:
            return [f"缺少必需封印字段: {sorted(missing)}"]
    if expect_chain is not None and a.get("chain_version") != expect_chain:
        problems.append(f"chain_version={a.get('chain_version')} 与目录 {expect_chain} 不符")
    if expect_date is not None and a.get("date") != expect_date:
        problems.append(f"date={a.get('date')} 与目录 {expect_date} 不符")
    if expect_stem is not None and str(a.get("ts_code", "")).replace(".", "_") != expect_stem:
        problems.append(f"ts_code={a.get('ts_code')} 与文件名 {expect_stem} 不符")
    if expect_manifest_fp is not None and a.get("manifest_fp") != expect_manifest_fp:
        problems.append("archive.manifest_fp 与版本 manifest 不符")
    if expect_executed_contract is not None \
            and a.get("executed_contract_sha256") != expect_executed_contract:
        problems.append("executed_contract_sha256 与版本 manifest 不符(执行契约不一致)")
    if require_sealed:
        if archive_seal(a) != a.get("archive_sha256"):
            problems.append("archive_sha256 封印不符(输出正文疑似篡改)")
        stored = input_artifact_fp(a.get("cards", {}), a.get("market_context", ""),
                                   a.get("manifest_fp", ""))
        if stored != a.get("artifact_fp"):
            problems.append("存档输入快照与自称 artifact_fp 不符(疑似篡改)")
    return problems


#: LLM 路由腿必备的执行字段(复审#7 B1;规范定义在此,llm_config 引用)
ROUTE_EXEC_KEYS = ("model", "thinking", "temperature", "max_tokens")


def verify_llm_route(route) -> list[str]:
    """LLM 路由腿的**值类型**校验(复审#8 Major:`thinking="False"` 是 truthy 字符串
    ——曾静默把 thinking 语义反转;只查键存在不查类型 = fail-open)。
    ChainContract.load、call_with_config、平台版本门共用同一把尺。
    model 非空 str;thinking 字面 bool 或 None;temperature [0,2] 有限数(bool 除外);
    max_tokens 正整数(bool 除外);fallback None 或非空 str。"""
    if not isinstance(route, Mapping):
        return ["route 不是对象"]
    missing = [k for k in ROUTE_EXEC_KEYS if k not in route]
    if missing:
        return [f"缺执行字段: {missing}"]
    if not isinstance(route["model"], str) or not route["model"].strip():
        return ["model 必须是非空字符串"]
    if route["thinking"] is not None and not isinstance(route["thinking"], bool):
        return ["thinking 必须是字面 bool 或 None"]
    if not _num_ok(route["temperature"], 0, 2):
        return ["temperature 必须是 [0,2] 有限数(bool 除外)"]
    mt = route["max_tokens"]
    if isinstance(mt, bool) or not isinstance(mt, int) or mt <= 0:
        return ["max_tokens 必须是正整数(bool 除外)"]
    fb = route.get("fallback")
    if fb is not None and (not isinstance(fb, str) or not fb.strip()):
        return ["fallback 必须是 None 或非空字符串"]
    return []


#: 执行契约必备的评分参数(复审#6 B1:缺 bear_discount_strength/divergence_gap 的
#  manifest 曾通过 ChainContract.load,judge 经 .get 回退到可变模块全局——fail-open)
REQUIRED_SCORING_KEYS = frozenset({
    "seat_weights", "composite_weights",
    "bear_discount_strength", "divergence_gap",
})


def verify_scoring_contract(scoring: object) -> list[str]:
    """评分契约完备性(复审#6 B1,引擎 ChainContract.load 与平台版本加载共用):
    四键齐全 + 类型/范围;不完备 = 整版本拒绝,绝不回退到模块常量。"""
    if not isinstance(scoring, dict):
        return ["scoring_contract 不是对象"]
    missing = REQUIRED_SCORING_KEYS - set(scoring)
    if missing:
        return [f"scoring_contract 缺字段: {sorted(missing)}"]
    sw, cw = scoring["seat_weights"], scoring["composite_weights"]
    if not isinstance(sw, dict) or not sw:
        return ["seat_weights 非空对象要求失败"]
    if not isinstance(cw, dict) or set(cw) != set(sw):
        return ["composite_weights 键集与 seat_weights 不符"]
    # 复审#7 B2:嵌套权重必须逐值校验——composite_weights["fund"]=NaN 曾让
    # 语义复核 fail-open(abs(NaN-x)>0.11 恒假,任意 composite 都通过)
    for seat, dims in sw.items():
        if not isinstance(dims, dict) or not dims:
            return [f"seat_weights[{seat}] 必须是非空对象"]
        if any(not _num_ok(v, 0, 100) for v in dims.values()):
            return [f"seat_weights[{seat}] 含非法权重"]
    if any(not _num_ok(v, 0, 1) for v in cw.values()):
        return ["composite_weights 必须是 [0,1] 有限数"]
    if abs(sum(float(v) for v in cw.values()) - 1.0) > 1e-12:
        return ["composite_weights 合计必须为 1"]
    if not _num_ok(scoring["bear_discount_strength"], 0, 5):
        return ["bear_discount_strength 非 [0,5] 有限数"]
    if not _num_ok(scoring["divergence_gap"], 0, 100):
        return ["divergence_gap 非 [0,100] 有限数"]
    return []


def _num_ok(v, lo: float, hi: float) -> bool:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return False
    try:
        f = float(v)
    except (TypeError, ValueError, OverflowError):
        return False
    return f == f and f not in (float("inf"), float("-inf")) and lo <= f <= hi


def verify_archive_semantics(a: dict, seat_weights: dict,
                             composite_weights: dict) -> list[str]:
    """跨字段语义一致性(复审#5 Major-3):records/bear/judge 的真实类型、范围与
    相互一致性——引擎复用与平台加载共用同一函数。空 records 条目、字符串
    kill_switches、与席位分不符的 judge.finals 都必须被点名。"""
    problems: list[str] = []
    if not isinstance(a, dict):
        return ["archive 不是对象"]
    seats = a.get("seats")
    records = a.get("records")
    bear = a.get("bear")
    verdict = a.get("judge")
    seat_set = set(seat_weights)
    if not isinstance(seats, dict) or set(seats) != seat_set:
        return ["seats 键集与评分契约不符"]
    if not isinstance(records, dict) or set(records) != seat_set:
        return ["records 键集与评分契约不符"]
    for s in sorted(seat_set):
        if not isinstance(seats[s], dict):
            problems.append(f"seats[{s}] 不是对象")
            continue
        if not isinstance(records[s], dict) \
                or not isinstance(records[s].get("factor_scores"), list):
            problems.append(f"records[{s}] 缺 factor_scores 列表")
        if not _num_ok(seats[s].get("final"), 0, 100):
            problems.append(f"seats[{s}].final 非 [0,100] 有限数")
    if not isinstance(bear, dict):
        problems.append("bear 不是对象")
    else:
        if not isinstance(bear.get("refutations"), list) \
                or not all(isinstance(r, dict) for r in bear.get("refutations", [])):
            problems.append("bear.refutations 非 dict 列表")
        ks = bear.get("kill_switches")
        if not isinstance(ks, list) or not ks \
                or not all(isinstance(k, str) and k.strip() for k in ks):
            problems.append("bear.kill_switches 必须是非空字符串列表")
    if not isinstance(verdict, dict) or not isinstance(verdict.get("finals"), dict) \
            or set(verdict.get("finals", {})) != seat_set:
        problems.append("judge.finals 键集与评分契约不符")
        return problems
    for s in sorted(seat_set):
        jf = verdict["finals"].get(s)
        sf = seats[s].get("final") if isinstance(seats[s], dict) else None
        if not _num_ok(jf, 0, 100) or jf != sf:
            problems.append(f"judge.finals[{s}] 与 seats[{s}].final 不一致")
    comp = verdict.get("composite")
    if not _num_ok(comp, 0, 100):
        problems.append("judge.composite 非 [0,100] 有限数")
    elif composite_weights and all(_num_ok(verdict["finals"].get(s), 0, 100)
                                   for s in seat_set):
        try:
            recomputed = round(sum(float(composite_weights[s])
                                   * float(verdict["finals"][s])
                                   for s in seat_set), 1)
            # 复审#7 B2 第二道防线:重算值本身必须是 [0,100] 有限数——
            # NaN 权重让 abs(NaN-x)>0.11 恒假,曾放行任意 composite
            if not _num_ok(recomputed, 0, 100) \
                    or abs(recomputed - float(comp)) > 0.11:
                problems.append(
                    f"judge.composite={comp} 与按契约权重重算 {recomputed} 不符")
        except (KeyError, TypeError, ValueError, OverflowError):
            problems.append("composite 重算失败(契约权重/finals 异常)")
    if not _num_ok(verdict.get("composite_adj"), 0, 100):
        problems.append("judge.composite_adj 非 [0,100] 有限数")
    return problems


def verify_publishable_archive(a: dict, seat_weights: dict,
                               composite_weights: dict) -> list[str]:
    """**合格档案的唯一共享判定**(复审#7 B3):引擎 archive_complete 与平台加载
    必须调用同一个函数——平台只跑较弱的 verify_archive_semantics 曾把引擎终局
    重算明确排除的档案(bear.schema_valid=False)计入完整月份。
    = 语义一致性 + 席位无错误 + bear 无错误/schema_valid/parse_mode 合法。"""
    problems = verify_archive_semantics(a, seat_weights, composite_weights)
    if problems:
        return problems
    # 复审#8 Blocker:严格判定,不用真值性——schema_valid=NaN/1/"false" 曾 sealed_ok,
    # falsey 非空错误([]/{}/0/"")曾被当"无错误"。error 只有字面 None 算干净,
    # schema_valid 只有字面 True 算通过。
    for s in sorted(a["seats"]):           # 语义通过后 seats 均为 dict
        if a["seats"][s].get("error") is not None:
            problems.append(f"seats[{s}] 带执行错误")
    bear = a["bear"]
    if bear.get("error") is not None:
        problems.append("bear 带执行错误")
    if bear.get("schema_valid") is not True:
        problems.append("bear.schema_valid 非严格布尔真")
    if bear.get("parse_mode") not in ("strict", "lenient"):
        problems.append("bear.parse_mode 非法")
    return problems
