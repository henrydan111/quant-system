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
            if abs(recomputed - float(comp)) > 0.11:
                problems.append(
                    f"judge.composite={comp} 与按契约权重重算 {recomputed} 不符")
        except (KeyError, TypeError, ValueError, OverflowError):
            problems.append("composite 重算失败(契约权重/finals 异常)")
    if not _num_ok(verdict.get("composite_adj"), 0, 100):
        problems.append("judge.composite_adj 非 [0,100] 有限数")
    return problems
