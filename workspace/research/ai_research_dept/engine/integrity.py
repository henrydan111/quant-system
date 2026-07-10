# SCRIPT_STATUS: ACTIVE — 归档完整性纯函数(链与平台共用同一把尺;零 LLM/编排依赖)
"""Archive/manifest integrity primitives (chain_v2.3, 复审#3 B2 验证不信任).

只依赖 stdlib(json/hashlib)——平台进程可安全 import(INTEL_CENTER §6 硬边界)。
磁盘自称的指纹一律不作数:manifest_fp 由正文重算、artifact_fp 由存档输入快照重算、
archive_sha256 由输出正文重算。
"""
from __future__ import annotations

import hashlib
import json


def sha16_json(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True,
                                     ensure_ascii=False).encode()).hexdigest()[:16]


def manifest_core_fp(m: dict) -> str:
    return sha16_json({k: v for k, v in m.items()
                       if k not in ("created_at", "manifest_fp")})


def input_artifact_fp(cards: dict, mc: str, manifest_fp: str) -> str:
    return sha16_json({"manifest_fp": manifest_fp,
                       "input_snapshot": {"cards": cards, "market_context": mc}})


def verify_manifest_body(m: dict) -> list[str]:
    """manifest 正文自校验:自称指纹必须等于正文重算。"""
    if not isinstance(m, dict):
        return ["manifest 不是对象"]
    recomputed = manifest_core_fp(m)
    if recomputed != m.get("manifest_fp"):
        return [f"manifest 正文与自称指纹不符(自称 {m.get('manifest_fp')} "
                f"重算 {recomputed})"]
    return []


def verify_archive_body(a: dict, *, expect_chain: str | None = None,
                        expect_date: str | None = None,
                        expect_stem: str | None = None,
                        expect_manifest_fp: str | None = None) -> list[str]:
    """归档正文自校验(返回问题列表;空=通过)。

    结构性检查对所有版本适用;封印检查(archive_sha256/存档输入指纹)只对携带
    这些字段的 v2.3+ 归档强制——legacy 归档由调用方标注 unverified_legacy。
    """
    problems: list[str] = []
    if expect_chain is not None and a.get("chain_version") != expect_chain:
        problems.append(f"chain_version={a.get('chain_version')} 与目录 {expect_chain} 不符")
    if expect_date is not None and a.get("date") != expect_date:
        problems.append(f"date={a.get('date')} 与目录 {expect_date} 不符")
    if expect_stem is not None and str(a.get("ts_code", "")).replace(".", "_") != expect_stem:
        problems.append(f"ts_code={a.get('ts_code')} 与文件名 {expect_stem} 不符")
    if expect_manifest_fp is not None and a.get("manifest_fp") != expect_manifest_fp:
        problems.append("archive.manifest_fp 与版本 manifest 不符")
    if "archive_sha256" in a:
        core = {k: v for k, v in a.items() if k != "archive_sha256"}
        if sha16_json(core) != a.get("archive_sha256"):
            problems.append("archive_sha256 封印不符(输出正文疑似篡改)")
    if "artifact_fp" in a and "cards" in a:
        stored = input_artifact_fp(a.get("cards", {}), a.get("market_context", ""),
                                   a.get("manifest_fp", ""))
        if stored != a.get("artifact_fp"):
            problems.append("存档输入快照与自称 artifact_fp 不符(疑似篡改)")
    return problems


def is_sealed(a: dict) -> bool:
    """v2.3+ 归档(携带封印字段,可完整自校验)。"""
    return "archive_sha256" in a and "artifact_fp" in a and "cards" in a
