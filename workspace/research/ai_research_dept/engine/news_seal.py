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
        # GPT #25 同类面:`str(k)` 会执行不可信键的 `__str__` 并把结果送进封印
        # 哈希;键一律经 fail-closed chokepoint(非 str 键静态拒)
        return {plain_str(k): canon(val) for k, val in v.items()}
    if isinstance(v, (list, tuple)):
        return [canon(x) for x in v]
    # GPT #25 同类面(哈希路径):旧兜底 `str(v)` 会对**任意**对象执行其 `__str__`
    # (调用方代码),且其返回值直接进封印哈希。实际到达此分支的只有 str——所有
    # canonical-payload helper 都先把字段门成恰基础类型。故收紧为 str-only:
    # 非 str 在**哈希构造**前静态拒,封印输入面与快照面语义一致。
    if not isinstance(v, str):
        raise SealError("canon 兜底只接受 str——非 str 值不得进入封印哈希"
                        "(绝不 str() 强转,GPT #25 同类面;静态错误)")
    return " ".join(str.__str__(v).split())


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


def plain_str(x) -> str:
    """**全仓唯一**的 str 归一 chokepoint(GPT #25 结构化收口)。

    归一为**普通 str**(archive-re-review#11 P0 同类面:str 子类可覆写
    `__eq__`/`__hash__`/`__str__` 使"封存哈希"与"语义==/成员"两次读取脱钩;
    `str.__str__` 是内建未绑定方法,取真实字符内容,绕过可覆写的 `__str__`)。

    GPT #25 P1#2:非 str **fail-closed 静态拒**——绝不 `str(x)` 兜底。旧的
    `news_evidence._plain_str` 分叉实现正是以 `str(x)` 收尾:那会(a)在快照边界
    上执行不可信对象的 `__str__`(类3/类5),且(b)`str()` 原样返回 `__str__` 所
    返的 **str 子类**,于是"独立基础类型快照"的保证被击穿——快照字段仍非恰 str。
    一个归一原语只许有一份实现、且只许有 fail-closed 一种语义。
    """
    if type(x) is str:
        return x
    if isinstance(x, str):                     # str 子类 → 内建拍平,无调用方代码
        return str.__str__(x)
    raise SealError("须恰 str(str 子类拍平;非 str 一律拒——绝不 str() 强转,"
                    "GPT #25 P1#2;静态错误)")


def plain_str_tuple(x) -> tuple:
    """归一为**普通 tuple[普通 str]**(archive-re-review#11 P0 同类面:哈希/ID
    元组的容器子类或状态化 `__iter__` 可在"哈希迭代"与"绑定检查迭代"间给出不同
    序列;一次性快照 + 每元素归一 → 两次读取永远一致的普通不可变元组)。"""
    return tuple(plain_str(u) for u in list(x))


def plain_object_tuple(x) -> tuple:
    """归一为**普通 tuple**(元素原样——已恰类型/自验的密封对象),只拆掉容器
    子类/状态化迭代(archive-re-review#11 P0 同类面)。"""
    return tuple(list(x))


_HEX64 = __import__("re").compile(r"[0-9a-f]{64}")

#: 安全渲染原语(GPT #24 类3 的**类级**修复)——拒绝路径上诊断不可信值时,
#: 绝不调用调用方代码。`{x!r}` 走 `type(x).__repr__`、`type(x).__name__` 走元类
#: `__getattribute__`,二者都是调用方代码;在**类型门**上(即正因为不信其类型
#: 才拒绝)它们必然在不可信对象上触发。下面两个 helper 只用 `type(x)` 内建 +
#: `is` 身份比对 + 字面量返回,全程零调用方代码。
_PLAIN_KINDS = ((bool, "bool"), (int, "int"), (float, "float"), (str, "str"),
                (list, "list"), (dict, "dict"), (tuple, "tuple"))


#: GPT #25 P1#1 的**类级**修复:`type(x) in (bool, int, float)` 展开为
#: `type(x) == bool or ...`——说谎的元类令 `type(x) == bool` 返真即可让任意对象
#: 冒充基础标量,且该 `__eq__` 本身就是拒绝路径上执行的调用方代码。全仓唯一的
#: 基础标量判定必须是**逐项 `is` 身份比对**;`type(x) in (...)` 在 NF 安全模块
#: 内被 meta-test 机械禁止(见 tests/test_news_engine_invariants.py)。
_PLAIN_SCALARS = (bool, int, float, str)


def is_plain_scalar(x, *, allow_str: bool = True) -> bool:
    """恰基础标量判定,零调用方代码(内建 `type()` + `is` 身份比对)。
    `None` 不算标量——需要接受 None 的调用点自行 `x is None` 短路。"""
    t = type(x)
    for cls in _PLAIN_SCALARS:
        if t is cls:
            return allow_str or cls is not str
    return False


def safe_kind(x) -> str:
    """不可信值的**类型名**,零调用方代码:只对**恰**基础类型报真名,其余一律
    `<非纯值>`(子类/自定义对象/说谎元类都落这里——正是要拒的那些)。"""
    if x is None:
        return "None"
    t = type(x)                                # 内建,不跑调用方代码
    for cls, name in _PLAIN_KINDS:
        if t is cls:                           # `is` 身份比对,元类 __eq__ 无从干预
            return name
    return "<非纯值>"


def safe_repr(x) -> str:
    """不可信值的**可诊断渲染**,零调用方代码:仅当类型**恰**为 None/bool/int/
    float/str 时才 `repr`(此时是内建 repr,安全且信息量最大);其余返回类型名
    占位。凡在类型门/成员门上诊断调用方传入值,一律用本函数,绝不用 `!r`。"""
    if x is None or type(x) is bool or type(x) is int or type(x) is float \
            or type(x) is str:
        return repr(x)                         # 恰基础类型 → 内建 repr
    return f"<{safe_kind(x)}>"


def verify_sealed(payload: dict, claimed_hash: str, *, field_name: str = "hash") -> None:
    """verify-not-trust:重算 payload 的 seal_hash 与自称哈希比对,不符硬失败。
    直接构造伪造对象(真 payload + 任意哈希 / 篡改 payload 留旧哈希)均被识破。
    archive-re-review#13:**先拒非精确 str / 非 64-hex 的 claimed_hash**——所有
    自封哈希都是 seal_hash 输出(64 位小写 hex),故 str 子类/int 子类等可覆写
    `__eq__`/`__ne__` 的对象在此死,先于 `!=` 比对(否则 `real != evil` 被
    evil 的 __ne__ 骗过,伪哈希序列化进档案)。这是所有哈希注入的单点闸门。"""
    if type(claimed_hash) is not str or not _HEX64.fullmatch(claimed_hash):
        # re-review#21 P1:错误信息**静态**——不读不可信 claimed_hash 的
        # `type().__name__` / `repr`(会在抛异常前触发元类 __getattribute__ /
        # 自定义 __repr__,拒绝路径也不得跑调用方代码)。`field_name` 是内部常量。
        raise SealError(
            f"{field_name} 须恰 str 且 64 位小写 hex(str/int 子类等脱钩拒,"
            f"re-review#13/#21)")
    recomputed = seal_hash(payload)
    if recomputed != claimed_hash:
        raise SealError(f"{field_name} 不符:自称 {claimed_hash[:12]} 重算 {recomputed[:12]}")
