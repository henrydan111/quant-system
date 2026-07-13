# SCRIPT_STATUS: ACTIVE — 新闻管线密封原语(NF wave;实现审 FIX-FIRST 全面密封束)
"""Unforgeable full-SHA PIT lineage primitives for the news pipeline.

GPT 实现审终裁:建**一个不可伪造的全 SHA PIT lineage 束**,未来双卡序列化器强制消费。
本模块是那束的地基,复用 chain_v2.x 密封链的全部教训:
- **规范类型编码**(review M5):`canon()` 单一缺失哨兵(None/NaN/pd.NA → 同一值)、
  时间戳 → CN-naive ISO、结构值 → 规范 JSON、标量 → 规范化文本。一处编码,处处一致,
  杜绝 `None`≠`NaN` 的幂等性漏洞。
- **全 SHA-256**(非截断)over 规范 payload。
- **深只读**(MappingProxyType/tuple 递归;frozen dataclass 挡不住改内部 dict——
  chain_v2.5 _deep_ro 教训)。
- **verify-not-trust**:封印工厂重算并嵌入哈希;任何"自称哈希"由校验函数重算比对,
  不符即硬失败。直接构造被工厂绕过时,`verify_sealed` 拒之。
"""
from __future__ import annotations

import hashlib
import json
import math
from types import MappingProxyType

import pandas as pd

#: 单一缺失哨兵(review M5:None/NaN/pd.NA 全归一,幂等)
NULL_SENTINEL = "\x00NULL\x00"


class SealError(Exception):
    """封印/校验失败(不可伪造性被破坏)—— fail-closed。"""


def _is_missing(v) -> bool:
    if v is None:
        return True
    try:
        if v is pd.NA or (isinstance(v, float) and math.isnan(v)):
            return True
    except (TypeError, ValueError):
        pass
    try:
        return bool(pd.isna(v))
    except (TypeError, ValueError):
        return False


def canon(v):
    """规范类型编码(review M5):唯一缺失哨兵、时间戳 CN-naive ISO、bool 保真、
    数字保真、结构值递归、其余 → 规范化空白文本。确定性、类型稳定。"""
    if _is_missing(v):
        return NULL_SENTINEL
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, (pd.Timestamp,)) or hasattr(v, "to_pydatetime"):
        t = pd.Timestamp(v)
        if t.tzinfo is not None:
            t = t.tz_convert("Asia/Shanghai").tz_localize(None)
        return "T:" + t.isoformat()
    if isinstance(v, dict):
        return {str(k): canon(val) for k, val in v.items()}
    if isinstance(v, (list, tuple)):
        return [canon(x) for x in v]
    return " ".join(str(v).split())


def canon_json(obj) -> str:
    """规范 JSON(sort_keys,规范值编码)—— 封印哈希的唯一序列化。"""
    return json.dumps(canon(obj), sort_keys=True, ensure_ascii=False)


def seal_hash(obj) -> str:
    """全 64 位 SHA-256 over 规范 payload(非截断,review B2)。"""
    return hashlib.sha256(canon_json(obj).encode()).hexdigest()


def deep_ro(obj):
    """深只读视图(MappingProxyType/tuple 递归)。frozen 挡不住改内部字典。"""
    if isinstance(obj, dict):
        return MappingProxyType({k: deep_ro(v) for k, v in obj.items()})
    if isinstance(obj, (list, tuple)):
        return tuple(deep_ro(x) for x in obj)
    return obj


def verify_sealed(payload: dict, claimed_hash: str, *, field_name: str = "hash") -> None:
    """verify-not-trust:重算 payload 的 seal_hash 与自称哈希比对,不符硬失败。
    直接构造伪造对象(真 payload + 任意哈希 / 篡改 payload 留旧哈希)均被识破。"""
    recomputed = seal_hash(payload)
    if recomputed != claimed_hash:
        raise SealError(f"{field_name} 不符:自称 {claimed_hash[:12]} 重算 {recomputed[:12]}")
