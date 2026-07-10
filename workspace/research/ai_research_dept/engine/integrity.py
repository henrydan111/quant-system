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

#: v2.4 起 manifest 声明 sealed_required=True 后,档案必须携带的封印字段
REQUIRED_SEAL_FIELDS = frozenset({
    "manifest_fp", "artifact_fp", "archive_sha256", "cards", "market_context",
})


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
                        expect_manifest_fp: str | None = None) -> list[str]:
    """归档正文自校验(返回问题列表;空=通过)。

    require_sealed=True(manifest.sealed_required 驱动):必需封印字段缺失即失败,
    且封印**无条件重算**——绝不依赖档案自称"是否 sealed"(复审#4 B1)。
    require_sealed=False 仅用于显式 allowlist 的 legacy 版本(结构性检查仍执行)。
    """
    if not isinstance(a, dict):
        return ["archive 不是对象"]
    problems: list[str] = []
    if require_sealed:
        missing = REQUIRED_SEAL_FIELDS - set(a)
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
    if require_sealed:
        if archive_seal(a) != a.get("archive_sha256"):
            problems.append("archive_sha256 封印不符(输出正文疑似篡改)")
        stored = input_artifact_fp(a.get("cards", {}), a.get("market_context", ""),
                                   a.get("manifest_fp", ""))
        if stored != a.get("artifact_fp"):
            problems.append("存档输入快照与自称 artifact_fp 不符(疑似篡改)")
    return problems
