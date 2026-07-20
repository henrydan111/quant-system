# SCRIPT_STATUS: ACTIVE — 新闻快讯:密封逐卡元数据注册表 + 证据类上限算术 + 三元 payload 门(NF §7 step 5+6 核心)
"""Sealed per-card metadata registry, evidence-class ceilings, ternary payload gate.

设计 v1.12 §7 step 5+6 的**承重核心**——GPT 每轮 R4 点名的"未来双卡序列化器强制消费
的、唯一不可伪造的逐卡元数据注册表",并在其上机械拒绝一切 attention_only/流/NFC ID 进
正向 factor 字段。全部复用 [news_seal.py](news_seal.py) 的封印原语(全 SHA-256 /
verify-not-trust / 深只读)。

三个规范契约(逐条锚定设计文档):
- **§6b B1/B1′ 元数据注册表**:每条注册记录 = `{record_id, domain, evidence_class,
  allowed_uses, allowed_consumers, allowed_dimensions}`;`allowed_uses ⊆
  {context_only, penalty, bear, factor_positive, display_only}`;**域来自元数据、绝不
  单凭 ID 前缀**(M3″ line 306)。
- **§0/M2 + §6b M3‴ 证据类上限算术**:维度上限 = 所引证据中**最强合格类**的上限
  (NFD≤5 / NFI≤3 / NFA≤3 / NFR·NFC=0 正向;宏观 MFD≤5 / MFI≤3 / MFA≤3 / MFR=0;
  交易所派生 market_state_fact 系 ≤5)——替代"任一被钳则钳全维"。
- **§6b M1″/M1‴ 三元授权**:每个动态可见项须解析到**恰一**条注册记录且
  `factor_positive ∈ allowed_uses ∧ consumer_seat ∈ allowed_consumers ∧
  target_dimension ∈ allowed_dimensions`;attention_only / coordination_risk / 传闻 /
  未注册 ID 出现在正向 factor payload = **硬失败**(物理排除,非仅挡 evidence_spans)。

⚠ 本模块是 authorization KERNEL + factor-字段断言;逐席四卡的完整递归 payload 构造
(step 6 全量)在其上,消费本模块。设计已 GPT round-12 APPROVE;本实现待 §10 实现审。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from workspace.research.ai_research_dept.engine.news_seal import (
    SealError, deep_ro, seal_hash, verify_sealed,
)

# --------------------------------------------------- 规范 enum(M1⁴ 冻结)

#: 消费席位(allowed_consumers 取值)
CONSUMER_SEATS = frozenset({"news", "macro", "technical", "fund", "bear", "chief", "display"})

#: 消费用途(allowed_uses ⊆ 此;§6b B1 line 440 + research_summary 的 display_only)
USES = frozenset({"context_only", "penalty", "bear", "factor_positive", "display_only"})

#: news 席 20 分制正向维(M3‴ line 363):c16_v1 用 catalyst_timing,
#  c16_news_horizon_v1 只替换它为 tradeability_at_horizon(其余三维共用)
NEWS_FACTOR_DIMENSIONS = frozenset({
    "event_materiality", "fundamental_link", "novelty",
    "catalyst_timing", "tradeability_at_horizon"})

#: 宏观维(M1⁴ line 386 冻结唯一 enum)
MACRO_DIMENSIONS = frozenset({
    "risk_appetite_environment_fit", "liquidity_flows_transmission",
    "industry_concept_transmission", "policy_alignment", "external_shock_transmission"})

#: 罚分/空头维(负向)
PENALTY_DIMENSIONS = frozenset({"coordination_risk", "confidence_cap", "manipulation_risk"})

_ALL_DIMENSIONS = NEWS_FACTOR_DIMENSIONS | MACRO_DIMENSIONS | PENALTY_DIMENSIONS

#: 证据类 → 正向上限(0 = 绝不正向贡献)。keyed by evidence_class,NOT id 前缀。
EVIDENCE_CEILING = {
    # news 正向(§0/M2 line 122)
    "NFD": 5, "NFI": 3, "NFA": 3,
    # news 非正向
    "NFR": 0,                       # 传闻·操纵
    "coordination_risk": 0,         # NFC## 的 evidence_class(§6b M3 line 461)
    # 宏观(§6b M1⁴ line 398 + §0b M1)
    "MFD": 5, "MFI": 3, "MFA": 3, "MFR": 0,
    # 交易所派生市场状态事实(M1‴ line 334;数学形态无关)
    "market_state_fact": 5, "market_breadth_state": 5,
    "market_limit_state": 5, "market_leadership_state": 5,
    # 绝不正向
    "attention_only": 0,            # N00/NDA/NIA + news-flow 派生(line 347)
    "research_summary": 0,          # chief 综合(M2′ line 259)
    "news_context": 0,              # 行情/评论/未证实/观点:信息性但不计分(fail-closed)
}
EVIDENCE_CLASSES = frozenset(EVIDENCE_CEILING)

#: 每类允许用途的硬约束(超集之外的 use 在注册时即拒;正向类默认可含 factor_positive)
_CLASS_USE_CONSTRAINT = {
    "attention_only": frozenset({"context_only", "bear"}),      # line 438 只空头+非计分
    "coordination_risk": frozenset({"penalty", "bear"}),        # line 462
    "research_summary": frozenset({"display_only"}),            # M2′ line 259
    "NFR": frozenset({"penalty", "bear"}),                      # 正向上限 0
    "MFR": frozenset({"penalty", "bear"}),                      # line 399
    "news_context": frozenset({"context_only", "bear"}),        # 不计分上下文
}


def is_positive_class(evidence_class: str) -> bool:
    """该证据类是否可正向计分(上限>0)。"""
    return EVIDENCE_CEILING.get(evidence_class, 0) > 0


#: M01-M16 冻结权威表(§6b M1⁴/M1‴;record_id → (evidence_class, allowed_dimensions))。
#  定义在 kernel(而非 news_taxonomy)——工厂级保留 ID 锁直接对照它,凡 mint M01-M16
#  的记录必须与本表逐字一致(re-review Major-3:build_policy_row_record("M16") 曾能
#  铸出 factor_positive 的 M16——公开工厂自铸冲突元数据,现从工厂层封死)。
M_LINE_TAXONOMY: dict[str, tuple[str, frozenset]] = {
    "M01": ("market_state_fact", frozenset({"risk_appetite_environment_fit"})),
    "M02": ("market_state_fact", frozenset({"risk_appetite_environment_fit"})),
    "M03": ("market_breadth_state", frozenset({"risk_appetite_environment_fit"})),
    "M04": ("market_limit_state", frozenset({"risk_appetite_environment_fit",
                                             "liquidity_flows_transmission"})),
    "M05": ("market_state_fact", frozenset({"industry_concept_transmission"})),
    "M06": ("market_state_fact", frozenset({"risk_appetite_environment_fit"})),
    "M07": ("market_state_fact", frozenset({"risk_appetite_environment_fit"})),
    "M08": ("market_state_fact", frozenset({"risk_appetite_environment_fit"})),
    "M09": ("market_breadth_state", frozenset({"risk_appetite_environment_fit"})),
    "M10": ("market_limit_state", frozenset({"risk_appetite_environment_fit",
                                             "liquidity_flows_transmission"})),
    "M11": ("market_state_fact", frozenset({"liquidity_flows_transmission"})),
    "M12": ("market_state_fact", frozenset({"risk_appetite_environment_fit"})),
    "M13": ("market_state_fact", frozenset({"liquidity_flows_transmission"})),
    "M14": ("market_leadership_state", frozenset({"industry_concept_transmission"})),
    "M15": ("market_breadth_state", frozenset({"risk_appetite_environment_fit"})),
    "M16": ("market_state_fact", frozenset()),   # 聚合:context_only 永不正向(M1⁴)
}
_M_LINE_RESERVED_RE = re.compile(r"M(0[1-9]|1[0-6])")

#: 记录 ID 语法 v1(re-review#2 M2:空/标点 ID 曾可铸;re-review#3 M2:一律
#  fullmatch——`$` + match 会放行尾随换行的"视觉重复身份")。大写字母开头 +
#  2-16 位大写字母数字,可选恰一注册 D7 属性后缀。
RECORD_ID_GRAMMAR_VERSION = "rid_v1"
_RECORD_ID_RE = re.compile(
    r"[A-Z][A-Z0-9]{1,15}(\.(fact|economic_linkage|timing|source_status))?")

#: 注册 domain enum(re-review#2 M2:domain 曾不受约束,M01 可挂 domain="news")
DOMAINS = frozenset({"news", "macro", "attention", "coordination", "research"})

#: 注册记录 schema(re-review#3 B1:受保护 ID 必须经**类型化 schema 工厂**铸造并
#  密封派生输入——"形状正确"的通用铸造不再能伪造计分权威)。
RECORD_SCHEMAS = frozenset({"generic_v1", "m_line_v1", "mp_v1", "mf_v1", "d7_child_v2"})
MF_DERIVATION_VERSION = "mf_dim_v1"

#: 每 schema 的**精确规范 derivation 键序列**(re-review#4 Major:dict(derivation)
#  会静默取重复键最后一值 + 留冗余键。此表锁死每 schema 的键集、顺序、唯一性——
#  冲突重复键 / 冗余 provenance="FORGED" / M-line 挂任意 derivation 一律拒)。
_SCHEMA_DERIVATION_KEYS: dict[str, tuple] = {
    "generic_v1": (),
    "m_line_v1": (),
    "mp_v1": (),
    "mf_v1": ("derivation_version", "macro_type"),
    "d7_child_v2": ("source_parent_content_hash", "registry_parent_content_hash",
                    "attribute_type"),
}


def _validated_derivation(schema_id: str, derivation: tuple) -> dict:
    """re-review#4 Major:derivation 必须是该 schema 的**恰好**规范键序列(键集+顺序+
    唯一,零冗余)。返回 dict(此后 dict() 安全,无重复键)。"""
    pairs = tuple(tuple(kv) for kv in derivation)
    keys = [kv[0] for kv in pairs]
    expected = _SCHEMA_DERIVATION_KEYS.get(schema_id, ())
    if len(keys) != len(set(keys)):
        raise RegistryError(f"derivation 键重复 {keys}(re-review#4 Major:不得歧义)")
    if tuple(keys) != expected:
        raise RegistryError(
            f"{schema_id} derivation 键必须恰为 {expected}(得 {tuple(keys)};"
            f"冗余/缺失/乱序/冲突键一律拒,re-review#4 Major)")
    return dict(pairs)

#: MF macro_type → 恰一正向维(注册派生表 v1;re-review#3 B1:表移入 kernel,
#  MF 记录的维**只能由密封的 macro_type 派生**,不可直接供给)。优先级契约见
#  news_taxonomy 模块 docstring(与分型 prompt 配套)。
MACRO_TYPE_DIMENSION: dict[str, str] = {
    "货币政策": "policy_alignment",
    "财政政策": "policy_alignment",
    "监管全局": "policy_alignment",
    "地缘外围": "risk_appetite_environment_fit",
    "大盘资金面": "liquidity_flows_transmission",
    "商品汇率": "risk_appetite_environment_fit",
    "行业景气": "industry_concept_transmission",
    "external_shock": "external_shock_transmission",
}

#: D7 属性 → 注册维(§6b M4′;re-review#3 B1:表移入 kernel,子行结构契约由
#  kernel 强制——source_status 永不正向)
ATTRIBUTE_DIMENSIONS = {
    "fact": frozenset({"event_materiality"}),
    "economic_linkage": frozenset({"fundamental_link"}),
    "timing": frozenset({"catalyst_timing", "tradeability_at_horizon"}),
    "source_status": frozenset({"confidence_cap"}),
}
_HEX64_RE = re.compile(r"[0-9a-f]{64}")

#: kernel 级保留命名空间(re-review#2 M2 + re-review#3 B1:**整个 M 命名空间保留**,
#  含 MS/M17+——未落类型化工厂的 M 域 ID 一律拒)。
_POLICY_NS_RE = re.compile(r"MP\d{2,}")
_MF_NS_RE = re.compile(r"MF[A-Z]?\d{2,}")
_MF_CLASSES = frozenset({"MFD", "MFI", "MFA", "MFR"})


def _m_line_expected(record_id: str) -> tuple:
    """保留 M-line ID 的规范元数据:(domain, class, uses, consumers, dims)。"""
    ec, dims = M_LINE_TAXONOMY[record_id]
    uses = frozenset({"factor_positive", "context_only"}) if dims \
        else frozenset({"context_only"})
    return "macro", ec, uses, frozenset({"macro"}), dims


def _enforce_protected_namespaces(record_id: str, domain: str, evidence_class: str,
                                  uses: frozenset, consumers: frozenset,
                                  dims: frozenset, schema_id: str,
                                  derivation: tuple) -> None:
    """kernel 级命名空间 + schema 派生锁(re-review#2 M2 + re-review#3 B1)。
    受保护 ID 必须携带对应**类型化 schema** 且元数据与**密封派生输入**一致:
    - M01-M16:schema=m_line_v1,元数据(含 domain)与权威表逐字一致;
    - MP*:schema=mp_v1,原子政策行精确契约;
    - MF*:schema=mf_v1,**维只由密封 macro_type 经 mf_dim_v1 派生**(直接供维=拒);
    - **其余 M 开头 ID(含 MS/M17+)整体保留**:无类型化工厂 → 一律拒;
    - `X.attr` D7 子行:schema=d7_child_v2,派生绑 source+registry 双父哈希 + 与后缀
      一致的 attribute_type,domain 恰为 news,consumers 恰 {news}(source_status
      {news,bear}),维=该属性注册维,source_status 永不正向;
    - schema 与命名空间**双向绑定**:非保护 ID 只许 generic_v1。
    re-review#4 Major:derivation 先经 `_validated_derivation`(键集/顺序/唯一/零冗余)。"""
    d = _validated_derivation(schema_id, derivation)
    if record_id.startswith("M"):
        if _M_LINE_RESERVED_RE.fullmatch(record_id):
            if schema_id != "m_line_v1":
                raise RegistryError(
                    f"{record_id} 是冻结 M-line 保留 ID——须经类型化工厂"
                    f"(record_schema_id=m_line_v1,得 {schema_id!r})")
            expected = _m_line_expected(record_id)
            if (domain, evidence_class, uses, consumers, dims) != expected:
                exp_d, exp_ec, exp_uses, exp_consumers, exp_dims = expected
                raise RegistryError(
                    f"{record_id} 是冻结 M-line 保留 ID(§6b M1⁴)——元数据必须与权威表"
                    f"逐字一致(期望 domain={exp_d}, class={exp_ec}, uses={sorted(exp_uses)}, "
                    f"consumers={sorted(exp_consumers)}, dims={sorted(exp_dims)})")
            return
        if _POLICY_NS_RE.fullmatch(record_id):
            if schema_id != "mp_v1":
                raise RegistryError(f"{record_id} 在 MP 保留命名空间——须经类型化工厂"
                                    f"(record_schema_id=mp_v1,得 {schema_id!r})")
            expected = ("macro", "market_state_fact",
                        frozenset({"factor_positive", "context_only"}),
                        frozenset({"macro"}), frozenset({"policy_alignment"}))
            if (domain, evidence_class, uses, consumers, dims) != expected:
                raise RegistryError(
                    f"{record_id} 在 MP 保留命名空间——元数据必须是原子政策行契约"
                    f"(macro/market_state_fact/正向+context/macro 席/policy_alignment)")
            return
        if _MF_NS_RE.fullmatch(record_id):
            if schema_id != "mf_v1":
                raise RegistryError(f"{record_id} 在 MF 保留命名空间——须经类型化工厂"
                                    f"(record_schema_id=mf_v1,得 {schema_id!r})")
            if domain != "macro" or evidence_class not in _MF_CLASSES:
                raise RegistryError(
                    f"{record_id} 在 MF 保留命名空间——须 domain=macro 且类 ∈ "
                    f"{sorted(_MF_CLASSES)}(得 domain={domain!r}, class={evidence_class!r})")
            if d.get("derivation_version") != MF_DERIVATION_VERSION:
                raise RegistryError(f"{record_id}(MF)派生须密封 derivation_version="
                                    f"{MF_DERIVATION_VERSION}(re-review#3 B1)")
            if evidence_class == "MFR":
                expected = (frozenset({"penalty", "bear"}), frozenset({"macro", "bear"}),
                            frozenset({"manipulation_risk"}))
                if (uses, consumers, dims) != expected:
                    raise RegistryError(f"{record_id}(MFR)元数据须为 penalty+bear/"
                                        f"macro+bear/manipulation_risk 精确契约")
                return
            # re-review#3 B1:MF 正向维**只由密封 macro_type 派生**——绕过派生直铸
            # external_shock_transmission(不带 macro_type=external_shock)在此拒
            mt = d.get("macro_type")
            derived = MACRO_TYPE_DIMENSION.get(mt) if mt is not None else None
            if derived is None:
                if uses != frozenset({"context_only"}) or dims:
                    raise RegistryError(
                        f"{record_id}(MF,macro_type={mt!r} 缺/未注册)只许 "
                        f"context_only-无维(M4:绝不落真维度)")
            else:
                if (uses != frozenset({"factor_positive", "context_only"})
                        or dims != frozenset({derived})):
                    raise RegistryError(
                        f"{record_id}(MF,macro_type={mt!r})维必须是派生维 "
                        f"{{{derived}}}(得 {sorted(dims)})——维不可直接供给(B1)")
            if consumers != frozenset({"macro"}):
                raise RegistryError(f"{record_id}(MF)consumers 须 {{macro}}")
            return
        raise RegistryError(
            f"{record_id!r}:**整个 M 命名空间保留**(M01-M16/MP*/MF* 之外——含 "
            f"MS/M17+——尚无类型化工厂,一律拒;re-review#3 B1)")
    if "." in record_id:
        attr = record_id.split(".", 1)[1]
        # re-review#4 B1:d7_child_v2 —— domain 恰 news + consumers 精确集(防跨席扩张)
        if schema_id != "d7_child_v2":
            raise RegistryError(f"{record_id}(D7 子行后缀)须经类型化工厂"
                                f"(record_schema_id=d7_child_v2,得 {schema_id!r})")
        if domain != "news":
            raise RegistryError(f"D7 子行 {record_id} domain 须恰为 news"
                                f"(得 {domain!r};re-review#4 B1 防跨席扩张)")
        if evidence_class not in ("NFD", "NFI", "NFA"):
            raise RegistryError(f"D7 子行 {record_id} 类须 ∈ {{NFD, NFI, NFA}}"
                                f"(得 {evidence_class!r})")
        if d.get("attribute_type") != attr:
            raise RegistryError(f"D7 子行 {record_id} 派生 attribute_type "
                                f"{d.get('attribute_type')!r} 与后缀 {attr!r} 不符")
        for key in ("source_parent_content_hash", "registry_parent_content_hash"):
            h = d.get(key)
            if not (isinstance(h, str) and _HEX64_RE.fullmatch(h)):
                raise RegistryError(f"D7 子行 {record_id} 派生须绑 64-hex {key}(B1 双父哈希)")
        if dims != ATTRIBUTE_DIMENSIONS[attr]:
            raise RegistryError(f"D7 子行 {record_id} 维须为属性注册维 "
                                f"{sorted(ATTRIBUTE_DIMENSIONS[attr])}(得 {sorted(dims)})")
        if attr == "source_status":
            expected_uses = frozenset({"penalty", "bear"})
            expected_consumers = frozenset({"news", "bear"})
        else:
            expected_uses = frozenset({"factor_positive", "context_only"})
            expected_consumers = frozenset({"news"})
        if uses != expected_uses:
            raise RegistryError(f"D7 子行 {record_id}({attr})uses 须恰 "
                                f"{sorted(expected_uses)}(source_status 永不正向)")
        if consumers != expected_consumers:
            raise RegistryError(f"D7 子行 {record_id}({attr})consumers 须恰 "
                                f"{sorted(expected_consumers)}(re-review#4 B1 防跨席)")
        return
    if schema_id != "generic_v1":
        raise RegistryError(f"{record_id!r} 非保护命名空间——只许 record_schema_id="
                            f"generic_v1(得 {schema_id!r};schema 与命名空间双向绑定)")
    # re-review#3(chain) Major:news 罚分映射在**铸造点**强制——三条注册映射之外的
    # penalty 授权不可铸(执行体信任的注册表元数据必须在 mint 时即合法):
    # NFR 恰 {manipulation_risk};coordination_risk 恰 {coordination_risk};
    # confidence_cap **只经** d7_child_v2 source_status 类型化分支(上方已 return);
    # MFR 在 MF 命名空间分支(已 return)。其余任何类携带 penalty 用途 = 拒。
    if "penalty" in uses:
        if evidence_class == "NFR":
            if dims != frozenset({"manipulation_risk"}):
                raise RegistryError(
                    f"{record_id}(NFR)penalty 维须恰 {{manipulation_risk}}"
                    f"(得 {sorted(dims)})——注册映射不可跨/不可多维(re-review#3)")
        elif evidence_class == "coordination_risk":
            if dims != frozenset({"coordination_risk"}):
                raise RegistryError(
                    f"{record_id}(coordination_risk)penalty 维须恰 "
                    f"{{coordination_risk}}(得 {sorted(dims)})——注册映射不可跨(re-review#3)")
        else:
            raise RegistryError(
                f"{record_id}:类 {evidence_class!r} 不得携带 penalty 用途——news 罚分"
                f"只能由 NFR/coordination_risk/D7 source_status(/宏观 MFR)接地(re-review#3)")


# --------------------------------------------------- 逐卡注册记录(封印)

class RegistryError(Exception):
    """元数据注册表不变量违反 —— fail-closed。"""


class PayloadGateError(Exception):
    """正向 payload 含未授权/attention_only/未注册 ID —— 硬失败(§6b B1)。"""


def _plain_str(x) -> str:
    """归一为**普通 str**(archive-re-review#11 P0:str 子类可覆写 __eq__/__hash__
    使"哈希"与"成员/比较"两次读取脱钩;`str.__str__(x)` 取真实字符内容,不经可
    覆写的 `__str__`)。"""
    return x if type(x) is str else str.__str__(x) if isinstance(x, str) else str(x)


def _plain_str_frozenset(x) -> frozenset:
    """归一为**普通 frozenset[普通 str]**(archive-re-review#11 P0:frozenset 子类
    的迭代[sorted 哈希]与成员[in 授权]可给出不同答案;一次性快照迭代 + 每元素归一
    → 迭代与成员永远一致,存回后是不可覆写的普通容器)。"""
    return frozenset(_plain_str(u) for u in list(x))


def _plain_scalar(x):
    """derivation 值归一(archive-re-review#11 P0:str/str 子类 → 普通 str[防
    覆写 __eq__/__hash__ 在"封存哈希"与"关系检查 =="间脱钩];None/bool/int/float
    等**内建不可变标量**原样保留[genuine derivation 含 None];其它类型拒——
    derivation 只该承载 JSON 标量血缘)。"""
    if x is None or type(x) in (bool, int, float):
        return x
    if isinstance(x, str):
        return _plain_str(x)
    raise RegistryError(f"derivation 标量类型非法:{type(x).__name__}"
                        f"(只许 str/None/bool/int/float,re-review#11 P0)")


def _plain_derivation(derivation) -> tuple:
    """归一为**普通嵌套 tuple**(容器子类防御)+ 逐值 `_plain_scalar`。"""
    return tuple(tuple(_plain_scalar(x) for x in list(kv))
                for kv in list(derivation))


@dataclass(frozen=True)
class CardRecord:
    """一条**封印**逐卡元数据记录。只能经 build_card_record / 类型化工厂构造;
    content_hash = 全 SHA-256 over 规范载荷(**含 record_schema_id 与派生输入**,
    re-review#3 B1);__post_init__ 先跑命名空间/schema 锁再 verify-not-trust——
    直接 dataclass 构造同样过锁,"形状正确"的伪造无路可走。授权**只读元数据**,
    绝不看 record_id 前缀(M3″)。"""
    record_id: str
    domain: str                      # ∈ DOMAINS
    evidence_class: str
    allowed_uses: frozenset
    allowed_consumers: frozenset
    allowed_dimensions: frozenset
    record_schema_id: str = "generic_v1"
    derivation: tuple = ()           # 密封派生输入(类型化 schema 的键值对)
    content_hash: str = field(default="")

    def __post_init__(self):
        # archive-re-review#11 P0:**语义字段先归一为普通不可变值并写回**,再校验
        # 封印——恰类型只保护外层,内部 frozenset/str 子类或状态化容器可在"哈希
        # 迭代 sorted()"与"授权成员 in"两次读取间脱钩(封存身份不变、授权语义变)。
        # 归一后所有读取都见同一份普通容器,迭代==成员,不可覆写。
        object.__setattr__(self, "record_id", _plain_str(self.record_id))
        object.__setattr__(self, "domain", _plain_str(self.domain))
        object.__setattr__(self, "evidence_class", _plain_str(self.evidence_class))
        object.__setattr__(self, "record_schema_id", _plain_str(self.record_schema_id))
        object.__setattr__(self, "content_hash", _plain_str(self.content_hash))
        object.__setattr__(self, "allowed_uses", _plain_str_frozenset(self.allowed_uses))
        object.__setattr__(self, "allowed_consumers",
                           _plain_str_frozenset(self.allowed_consumers))
        object.__setattr__(self, "allowed_dimensions",
                           _plain_str_frozenset(self.allowed_dimensions))
        object.__setattr__(self, "derivation", _plain_derivation(self.derivation))
        # re-review#3 B1:锁在构造点(工厂与直接构造同一路径)——现读已归一普通值
        _enforce_protected_namespaces(
            self.record_id, self.domain, self.evidence_class,
            self.allowed_uses, self.allowed_consumers,
            self.allowed_dimensions, self.record_schema_id,
            self.derivation)
        verify_sealed(self._payload(), self.content_hash, field_name="card record content_hash")

    def _payload(self) -> dict:
        return card_record_canonical_payload(self)

    @property
    def positive_ceiling(self) -> int:
        """本记录可对某维贡献的最高分(非正向类 = 0)。"""
        return EVIDENCE_CEILING.get(self.evidence_class, 0)


def card_record_canonical_payload(record) -> dict:
    """CardRecord 的 **canonical 载荷**——模块级、不可覆写(archive-re-review#9
    P0:CardRecord 是身份链的叶子——registry_hash 由成员 content_hash 组成,
    子类覆写 `_payload()` 伪造 content_hash 即可让整条"全真类型"档案链脱钩。
    注册边界一律恰类型 + 经本 helper 重算 content_hash,绝不信成员自封哈希)。"""
    return {"record_id": record.record_id, "domain": record.domain,
            "evidence_class": record.evidence_class,
            "allowed_uses": sorted(record.allowed_uses),
            "allowed_consumers": sorted(record.allowed_consumers),
            "allowed_dimensions": sorted(record.allowed_dimensions),
            "record_schema_id": record.record_schema_id,
            "derivation": [list(kv) for kv in record.derivation]}


def assert_base_record_fields(record) -> None:
    """**每次消费**都断言 CardRecord 的语义字段确为**基础不可变类型**
    (archive-re-review#12 P0:frozen dataclass 的 `__dict__` 可被直接改写[无需
    object.__setattr__],构造时的归一可被事后 `record.__dict__[...] = evil` 注入
    撤销——状态化 mapping 在唯一一次 items() 里就能把已归一的普通 frozenset 换成
    "迭代 sorted()=context_only、成员 in=factor_positive"的子类;故消费门须逐字段
    恰类型:allowed_* 恰 frozenset[恰 str]、str 标量恰 str、derivation 恰嵌套
    tuple[基础标量]。任何子类/别名注入在此死,先于哈希重算与授权)。"""
    for _f in ("record_id", "domain", "evidence_class", "record_schema_id",
               "content_hash"):
        if type(getattr(record, _f)) is not str:
            raise RegistryError(
                f"CardRecord.{_f} 非恰 str(得 {type(getattr(record, _f)).__name__}"
                f";__dict__ 注入子类拒,re-review#12 P0)")
    for _f in ("allowed_uses", "allowed_consumers", "allowed_dimensions"):
        s = getattr(record, _f)
        if type(s) is not frozenset or any(type(u) is not str for u in s):
            raise RegistryError(
                f"CardRecord.{_f} 须恰 frozenset[恰 str](得 {type(s).__name__}"
                f";迭代≠成员的子类/别名注入拒,re-review#12 P0)")
    d = record.derivation
    if type(d) is not tuple:
        raise RegistryError(f"CardRecord.derivation 须恰 tuple(re-review#12 P0)")
    for kv in d:
        if type(kv) is not tuple \
                or any(not (x is None or type(x) in (str, bool, int, float))
                       for x in kv):
            raise RegistryError(
                "CardRecord.derivation 项须恰 tuple[str/None/bool/int/float]"
                "(re-review#12 P0)")


def verified_record_content_hash(record) -> str:
    """恰类型 CardRecord + **字段基础类型断言** + 经 canonical helper **重算并校验**
    content_hash,返回该已验证哈希(archive-re-review#9 P0 + #12 P0:registry_hash
    与所有身份链重算都基于此,绝不直接信任 `record.content_hash`,也绝不容许字段
    被 __dict__ 注入为迭代≠成员的多态对象)。"""
    if type(record) is not CardRecord:
        raise RegistryError(
            f"注册表只收恰 CardRecord(得 {type(record).__name__};子类可覆写 "
            f"_payload 伪造 content_hash 脱钩,拒,re-review#9 P0)")
    assert_base_record_fields(record)                  # re-review#12 P0
    verify_sealed(card_record_canonical_payload(record), record.content_hash,
                  field_name="card record content_hash")
    return record.content_hash


def normalize_card_record(v) -> "CardRecord":
    """把一条 CardRecord **重建为独立的基础不可变记录**(archive-re-review#12 P0:
    registry 不再持有调用方仍能改写 __dict__ 的记录对象——重建出的新记录调用方
    无引用;CardRecord.__post_init__ 再次归一全部字段,新记录字段皆基础类型)。
    重建**前**先断言外层恰 CardRecord + 字段基础类型(捕获 items() 迭代期注入),
    使重建读到的字段本身已是干净基础值。"""
    if type(v) is not CardRecord:
        raise RegistryError(
            f"注册表值须恰 CardRecord(得 {type(v).__name__};子类/duck-typed 拒,"
            f"re-review#12 P0)")
    assert_base_record_fields(v)
    return CardRecord(
        record_id=v.record_id, domain=v.domain, evidence_class=v.evidence_class,
        allowed_uses=v.allowed_uses, allowed_consumers=v.allowed_consumers,
        allowed_dimensions=v.allowed_dimensions,
        record_schema_id=v.record_schema_id, derivation=v.derivation,
        content_hash=v.content_hash)


def build_card_record(record_id: str, *, domain: str, evidence_class: str,
                      allowed_uses, allowed_consumers, allowed_dimensions=(),
                      record_schema_id: str = "generic_v1",
                      derivation: tuple = ()) -> CardRecord:
    """封印逐卡记录工厂。强制不变量(fail-closed):
    - evidence_class ∈ 注册 enum;allowed_uses ⊆ USES;allowed_consumers ⊆ CONSUMER_SEATS;
    - 每类用途约束(attention_only 只 context/bear、NFR/MFR/coordination 只 penalty/bear、
      research_summary 只 display_only);
    - **零上限类绝不可 factor_positive**(attention_only/NFR/NFC/MFR/research → 若含
      factor_positive 即拒——这是 line 440"attention_only 入 factor_scores 硬失败"的注册端);
    - factor_positive 记录必须有非空 allowed_dimensions ⊆ 注册维 且 allowed_consumers 非空。"""
    uses = frozenset(allowed_uses)
    consumers = frozenset(allowed_consumers)
    dims = frozenset(allowed_dimensions)
    # re-review#2 M2 + re-review#3 M2:ID 语法 fullmatch(尾随换行/CR/NUL 拒)+
    # domain/schema enum 先于一切
    if not isinstance(record_id, str) or not _RECORD_ID_RE.fullmatch(record_id):
        raise RegistryError(
            f"record_id {record_id!r} 不合语法 {RECORD_ID_GRAMMAR_VERSION}"
            f"(大写字母开头 2-16 位大写字母数字,可选恰一注册 D7 属性后缀)")
    if domain not in DOMAINS:
        raise RegistryError(f"未注册 domain {domain!r}(须 ∈ {sorted(DOMAINS)})")
    if record_schema_id not in RECORD_SCHEMAS:
        raise RegistryError(f"未注册 record_schema_id {record_schema_id!r}"
                            f"(须 ∈ {sorted(RECORD_SCHEMAS)})")
    if evidence_class not in EVIDENCE_CLASSES:
        raise RegistryError(f"未知 evidence_class {evidence_class!r}(须 ∈ {sorted(EVIDENCE_CLASSES)})")
    bad_use = uses - USES
    if bad_use:
        raise RegistryError(f"非法 allowed_uses {sorted(bad_use)}(须 ⊆ {sorted(USES)})")
    bad_seat = consumers - CONSUMER_SEATS
    if bad_seat:
        raise RegistryError(f"非法 allowed_consumers {sorted(bad_seat)}")
    constraint = _CLASS_USE_CONSTRAINT.get(evidence_class)
    if constraint is not None and not uses <= constraint:
        raise RegistryError(
            f"{evidence_class} 的 allowed_uses {sorted(uses)} 越界(须 ⊆ {sorted(constraint)})")
    if "factor_positive" in uses:
        if not is_positive_class(evidence_class):
            raise RegistryError(
                f"零上限类 {evidence_class} 不得含 factor_positive(attention_only/传闻/"
                f"协同/宏观传闻/research 永不正向,§6b B1 line 440)")
        bad_dim = dims - _ALL_DIMENSIONS
        if not dims or bad_dim:
            raise RegistryError(
                f"factor_positive 记录须有非空 allowed_dimensions ⊆ 注册维;越界 {sorted(bad_dim)}")
        if not consumers:
            raise RegistryError("factor_positive 记录须有非空 allowed_consumers")
    # 命名空间/schema 锁在 CardRecord.__post_init__(直接构造同样过锁,re-review#3 B1)
    derivation = tuple(tuple(kv) for kv in derivation)
    payload = {"record_id": record_id, "domain": domain, "evidence_class": evidence_class,
               "allowed_uses": sorted(uses), "allowed_consumers": sorted(consumers),
               "allowed_dimensions": sorted(dims), "record_schema_id": record_schema_id,
               "derivation": [list(kv) for kv in derivation]}
    # frozensets are already immutable — no deep_ro needed for the leaf sets
    return CardRecord(record_id=record_id, domain=domain, evidence_class=evidence_class,
                      allowed_uses=uses, allowed_consumers=consumers,
                      allowed_dimensions=dims, record_schema_id=record_schema_id,
                      derivation=derivation, content_hash=seal_hash(payload))


# --------------------------------------------------- 密封注册表(逐 cutoff)

@dataclass(frozen=True)
class SealedCardRegistry:
    """cutoff T 的**封印**逐卡元数据注册表。经 build_card_registry 构造;registry_hash =
    全 SHA-256 over 全部记录 content_hash(**记录序无关**);__post_init__ verify-not-trust。
    这是双卡序列化器唯一许可消费的元数据底物。"""
    cutoff_iso: str
    records: object                  # 深只读 {record_id: CardRecord}
    registry_hash: str = field(default="")

    def __post_init__(self):
        # archive-re-review#11 P0:records **深不可变快照 + 每值恰 CardRecord**,先于
        # 校验——调用方可传状态化 mapping,在 values()(哈希重算)与 items()/get()
        # (关系检查/消费)两次读取间变更记录;一次性快照后所有读取见同一冻结视图。
        # archive-re-review#12 P0:每个值**重建为独立的基础不可变记录**(不只冻结
        # 外层 mapping)——状态化 mapping 在这唯一一次 items() 迭代里经 __dict__
        # 注入 evil 集合也被 normalize_card_record 的基础类型断言 + 重建捕获;
        # 消费门(verified_record_content_hash)每次再验字段确为基础类型
        snap = {}
        for k, v in list(self.records.items()):
            snap[_plain_str(k)] = normalize_card_record(v)
        object.__setattr__(self, "records", deep_ro(snap))
        object.__setattr__(self, "cutoff_iso", _plain_str(self.cutoff_iso))
        object.__setattr__(self, "registry_hash", _plain_str(self.registry_hash))
        verify_sealed(self._payload(), self.registry_hash, field_name="registry_hash")

    def _payload(self) -> dict:
        return registry_canonical_payload(self)

    def get(self, record_id: str) -> "CardRecord | None":
        return self.records.get(record_id)


def registry_canonical_payload(registry) -> dict:
    """注册表的 **canonical 载荷**——模块级、不可覆写、只读实际字段
    (archive-re-review#7 P0:D7 消费边界绝不调用可被子类覆写的虚方法
    `_payload()`;记录序无关,按 content_hash 排序)。archive-re-review#9 P0:
    每条成员经 `verified_record_content_hash`(恰类型 + canonical 重算),
    registry_hash 基于**已验证**记录哈希,绝不直接信任成员自封 `content_hash`。"""
    return {"cutoff": registry.cutoff_iso,
            "record_hashes": sorted(verified_record_content_hash(r)
                                    for r in registry.records.values())}


def build_card_registry(cutoff_iso: str, records: list[CardRecord]) -> SealedCardRegistry:
    """封印注册表工厂。重复 record_id → 拒(身份必须唯一)。
    re-review#3 B1:逐记录重验受保护 schema 绑定(构造点已锁,此处显式重跑)+
    **D7 子行注册表级校验**:父行必须同表存在、子行类与父行类逐字一致(kernel 结构
    锁绑父哈希但解析不了父,类等式在此闭合——`NFI01.fact` 挂 NFD 类在此拒)。"""
    by_id: dict[str, CardRecord] = {}
    verified_hashes = []
    for r in records:
        # archive-re-review#9 P0:恰类型 + canonical 重算 content_hash(子类覆写
        # _payload 伪造哈希在此死),registry_hash 基于已验证哈希
        vh = verified_record_content_hash(r)
        if r.record_id in by_id:
            raise RegistryError(f"重复 record_id {r.record_id!r}")
        _enforce_protected_namespaces(
            r.record_id, r.domain, r.evidence_class, frozenset(r.allowed_uses),
            frozenset(r.allowed_consumers), frozenset(r.allowed_dimensions),
            r.record_schema_id, tuple(r.derivation))
        by_id[r.record_id] = r
        verified_hashes.append(vh)
    _verify_d7_relationships(by_id)                    # re-review#4 B1
    payload = {"cutoff": cutoff_iso, "record_hashes": sorted(verified_hashes)}
    return SealedCardRegistry(cutoff_iso=cutoff_iso, records=deep_ro(by_id),
                              registry_hash=seal_hash(payload))


def _verify_d7_relationships(records) -> None:
    """D7 子行的**关系级**语义校验(re-review#4 B1):子行必须绑**同一注册表内、ID 前缀
    指向的**那个父行——class、domain、以及密封的 registry_parent_content_hash 都必须与
    该父行一致。**从 build_card_registry 与 require_sealed_registry 双调用**(每次消费
    都重验),使 `NFD01.fact` 封 `NFD02` 的哈希、或子行错父/跨类无路可走。"""
    for rid, r in records.items():
        if "." not in rid:
            continue
        parent = records.get(rid.split(".", 1)[0])
        if parent is None:
            raise RegistryError(f"D7 子行 {rid} 无父行在同一注册表——孤儿拒(B1)")
        d = dict(tuple(kv) for kv in r.derivation)
        if d.get("registry_parent_content_hash") != parent.content_hash:
            raise RegistryError(
                f"D7 子行 {rid} 绑的 registry 父哈希 "
                f"{str(d.get('registry_parent_content_hash'))[:12]} ≠ 同表 ID-前缀父行 "
                f"{parent.record_id} 实际哈希 {parent.content_hash[:12]}——错父拒(B1)")
        if r.evidence_class != parent.evidence_class:
            raise RegistryError(
                f"D7 子行 {rid} 类 {r.evidence_class!r} ≠ 父行类 "
                f"{parent.evidence_class!r}——洗类拒(B1)")
        if r.domain != parent.domain:
            raise RegistryError(
                f"D7 子行 {rid} domain {r.domain!r} ≠ 父行 domain {parent.domain!r}(B1)")


def require_sealed_registry(registry) -> SealedCardRegistry:
    """消费边界强制(re-review#3 B2 + re-review#4 B1):只收真 SealedCardRegistry、重验
    其封印、**并重跑 D7 关系语义校验**——duck-typed 冒牌对象与错父 D7 子行在每个消费点拒。"""
    # archive-re-review#7 P0:恰类型(子类可覆写 _payload 使 registry_hash 与实际
    # records 脱钩,自封假身份过全链)+ canonical helper 重算,不经虚方法
    if type(registry) is not SealedCardRegistry:
        raise RegistryError("registry 必须是恰 SealedCardRegistry"
                            f"(得 {type(registry).__name__};子类/duck-typed 拒,"
                            f"re-review#7 P0)")
    verify_sealed(registry_canonical_payload(registry), registry.registry_hash,
                  field_name="registry_hash")
    _verify_d7_relationships(registry.records)         # re-review#4 B1:每次消费重验
    return registry


# --------------------------------------------------- 三元授权 + 上限算术

def authorize(record: CardRecord, *, use: str, consumer_seat: str,
              target_dimension: "str | None" = None) -> bool:
    """三元授权(M1‴ line 350):`use ∈ allowed_uses ∧ consumer_seat ∈ allowed_consumers
    ∧ (target_dimension 未给 或 ∈ allowed_dimensions)`。**只读元数据,绝不看 ID 前缀**。
    factor_positive 用途必须给 target_dimension(否则拒——正向必须指向一个注册维)。"""
    if type(record) is not CardRecord:
        raise RegistryError("authorize 只接受恰 CardRecord(子类拒,re-review#9 P0)")
    # re-review#12 P0:authorize 是**直接成员消费点**——先断言字段确为基础类型,
    # 使其自守(不依赖上游 require_sealed_registry;__dict__ 注入的迭代≠成员子类
    # 在成员判断前即死),迭代(哈希)与成员(此处)读的是同一份普通 frozenset。
    assert_base_record_fields(record)
    if use not in record.allowed_uses:
        return False
    if consumer_seat not in record.allowed_consumers:
        return False
    if use == "factor_positive":
        if target_dimension is None:
            return False                      # 正向必须指向恰一注册维
        return target_dimension in record.allowed_dimensions
    if target_dimension is not None:
        return target_dimension in record.allowed_dimensions
    return True


def dimension_ceiling(cited_ids, registry: SealedCardRegistry, *,
                      consumer_seat: str, target_dimension: str) -> int:
    """证据类上限算术(§0/M2 line 122):某维的上限 = 所引证据中,对 (seat, dimension)
    授权 factor_positive 的记录里**最强合格证据类的上限**;无合格证据 → 0(NO-SCORE)。
    传闻/协同/attention_only/未注册引用**不贡献**(它们授权不过 → 天然被排除)。"""
    registry = require_sealed_registry(registry)          # B2:消费边界重验
    ceils = []
    for rid in cited_ids:
        rec = registry.get(rid)
        if rec is None:
            continue                          # 未注册引用不贡献正向(gate 另行硬失败)
        if authorize(rec, use="factor_positive", consumer_seat=consumer_seat,
                     target_dimension=target_dimension):
            ceils.append(rec.positive_ceiling)
    return max(ceils) if ceils else 0


# --------------------------------------------------- 正向 payload 门(承重硬失败)

#: 证据引用的**规范编码**:ASCII `[ID]` 方括号组,内文恰为 record-id 语法(D7 后缀
#  原子)。外部正文的 ASCII 方括号已被 sanitize_text 全角化(〔〕),故正文物理无法
#  伪造一个 `[ID]` 引用;渲染器的元数据括号有自己的类型化语法(至少含一个 `|`,
#  见 _META_BRACKET_RE)。re-review#5 B2:`[ID]` 是 EvidenceRef 的**规范输出编码**,
#  不是授权边界——授权边界另由"裸已知 ID 拒绝"补全(_assert_no_stray_known_ids)。
_BRACKET_REF_RE = re.compile(r"\[([^\[\]]*)\]")
_ID_REF_GRAMMAR = re.compile(
    r"[A-Z][A-Z0-9]{1,15}(?:\.(?:fact|economic_linkage|timing|source_status))?")
#: 渲染器元数据括号的类型化语法(re-review#5 B2):内文至少含一个 `|` 且无嵌套括号
#  (如 `[2.1h|★★★★|NFD]`)——与证据引用 `[ID]` 语法互斥。
_META_BRACKET_RE = re.compile(r"[^\[\]|]*\|[^\[\]]*")


@dataclass(frozen=True)
class EvidenceRef:
    """类型化证据引用节点(re-review#5 B2:引用的**真身**;`[ID]` 只是其规范文本
    编码)。席位 payload 构造器应放 EvidenceRef 节点,序列化时 encode()。"""
    record_id: str

    def __post_init__(self):
        if not isinstance(self.record_id, str) \
                or not _ID_REF_GRAMMAR.fullmatch(self.record_id):
            raise RegistryError(f"EvidenceRef record_id {self.record_id!r} 不合引用语法")

    def encode(self) -> str:
        return f"[{self.record_id}]"


def extract_candidate_id_occurrences(payload) -> list:
    """从完整序列化 payload 抽取候选 record 引用的**逐次出现**(有序列表,
    **保多重性**;re-review#2(seat) B2:set 形态会让"类型化引用 + 同 ID 裸副本"
    互相掩护——重数必须可见)。候选 = 类型化 EvidenceRef 节点,或 ASCII `[ID]` 组
    且内文 fullmatch record-id 语法(D7 后缀原子)。递归遍历 dict/list/tuple/str;
    dict 键与值都扫;字符串内按出现位置从左到右。"""
    found: list = []

    def walk(o):
        if isinstance(o, EvidenceRef):
            found.append(o.record_id)
        elif isinstance(o, str):
            for m in _BRACKET_REF_RE.finditer(o):
                if _ID_REF_GRAMMAR.fullmatch(m.group(1)):
                    found.append(m.group(1))
        elif isinstance(o, dict):
            for k, v in o.items():
                walk(k)
                walk(v)
        elif isinstance(o, (list, tuple)):
            for x in o:
                walk(x)
    walk(payload)
    return found


def extract_candidate_ids(payload) -> set:
    """候选引用**集合**形态(仅用于成员/授权判定;重数判定用
    `extract_candidate_id_occurrences`,re-review#2(seat) B2)。"""
    return set(extract_candidate_id_occurrences(payload))


def _assert_no_stray_known_ids(payload, known_ids: set, *, context: str) -> None:
    """re-review#5 B2:**已知注册 ID 在类型化引用之外出现 = 硬失败**。逐字符串
    (含 dict 键)用最长优先原子边界扫描每个已知 ID;命中位置必须恰好是某个规范
    `[ID]` 组的内文(裸 `{"id":"NFC01"}`、裸键 `{"NFC01":...}`、空白垫 `[ NFC01 ]`、
    未闭合 `[NFC01` 全部拒);规范组紧邻内层/外层括号(嵌套 `[[NFC01]]`)也拒。
    只扫**已知注册 ID**——`Q4`/`H1` 等正常散文不受影响(它们不是注册 ID)。"""
    if not known_ids:
        return
    # 边界不含 `.`:最长优先已保证已注册子行整体优先命中;裸 `NFD01.`(句尾)仍被抓
    pat = re.compile(r"(?<![A-Za-z0-9_])(?:"
                     + "|".join(re.escape(k) for k in
                                sorted(known_ids, key=len, reverse=True))
                     + r")(?![A-Za-z0-9_])")

    def check(s: str):
        canonical: list = []
        for m in _BRACKET_REF_RE.finditer(s):
            if _ID_REF_GRAMMAR.fullmatch(m.group(1)):
                # 嵌套/畸形:规范组外侧紧邻另一括号 → 拒(re-review#5 B2)
                if (m.start() > 0 and s[m.start() - 1] == "[") \
                        or (m.end() < len(s) and s[m.end()] == "]"):
                    raise PayloadGateError(
                        f"{context}:引用 [{m.group(1)}] 处于嵌套/畸形括号内——拒")
                canonical.append((m.start(1), m.end(1)))
        for m in pat.finditer(s):
            if not any(a <= m.start() and m.end() <= b for a, b in canonical):
                raise PayloadGateError(
                    f"{context}:已知注册 ID {m.group(0)!r} 以**裸/畸形**形式出现"
                    f"(非规范 [ID] 引用)——拒(re-review#5 B2:模型看得见就必须"
                    f"过授权,引用必须走类型化编码)")

    def walk(o):
        if isinstance(o, str):
            check(o)
        elif isinstance(o, EvidenceRef):
            pass                                   # 类型化节点本身即合法引用
        elif isinstance(o, dict):
            for k, v in o.items():
                walk(k)
                walk(v)
        elif isinstance(o, (list, tuple)):
            for x in o:
                walk(x)
    walk(payload)


def scan_payload_ids(payload, registry: SealedCardRegistry) -> set:
    """抽取 payload 内**全部候选 record 引用**(re-review#4 B2:注册表无关,含未注册)。
    保留 registry 参数并重验(消费边界)以维持调用契约;真正的成员判定交给
    assert_factor_payload(未知 ID 硬失败)。"""
    require_sealed_registry(registry)                     # B2:消费边界重验
    return extract_candidate_ids(payload)


def assert_factor_payload(payload, registry: SealedCardRegistry, *,
                          consumer_seat: str, target_dimension: str) -> set:
    """**承重门**(§6b B1 line 440 / M1″ / re-review#4 B2):正向 factor payload 内出现的
    **每一个**候选 record 引用都必须 (a) 已注册——`candidate_ids − registry_ids` 非空即
    硬失败(伪造 `[NFD99]`、未注册 D7 子行 `[NFD01.fact]` 不再被误当父 ID 放行);
    (b) 对 (seat, dimension) 授权 factor_positive——任何 attention_only / coordination_risk
    / 传闻(NFR/MFR) / 未授权 / 域外记录出现 → PayloadGateError。返回通过的已授权 ID 集。"""
    registry = require_sealed_registry(registry)
    candidates = extract_candidate_ids(payload)
    known = set(registry.records)
    unknown = candidates - known
    if unknown:
        raise PayloadGateError(
            f"正向 payload(seat={consumer_seat}, dim={target_dimension})含**未注册** "
            f"record 引用 {sorted(unknown)}——伪造/未知 ID 硬失败(re-review#4 B2)")
    # re-review#5 B2:已知 ID 以裸/畸形形式出现(非类型化 [ID] 引用)= 硬失败——
    # 模型看得见的每个注册 ID 都必须走引用编码过授权,{"id":"NFC01"} 无处可藏
    _assert_no_stray_known_ids(payload, known,
                               context=f"正向 payload(seat={consumer_seat})")
    offenders = []
    for rid in sorted(candidates):
        rec = registry.get(rid)
        if not authorize(rec, use="factor_positive", consumer_seat=consumer_seat,
                         target_dimension=target_dimension):
            offenders.append((rid, rec.evidence_class, sorted(rec.allowed_uses)))
    if offenders:
        raise PayloadGateError(
            f"正向 payload(seat={consumer_seat}, dim={target_dimension})含未授权注册 ID:"
            + "; ".join(f"{rid}[{ec},uses={u}]" for rid, ec, u in offenders))
    return candidates


def assert_leg_payload(payload, registry: SealedCardRegistry, *, use: str,
                       consumer_seat: str) -> set:
    """**腿级** payload 门(M2‴ 元数据过滤):factor/penalty 腿的整体 payload 校验——
    每个引用必须 (a) 已注册(未知/伪造硬失败)、(b) `use ∈ allowed_uses ∧
    consumer_seat ∈ allowed_consumers`;裸已知 ID 同样硬失败。与逐维
    `assert_factor_payload` 的区别:腿 payload 合法地含多维记录(D7 属性行各限一维),
    维度绑定在**计分时**由 `dimension_ceiling` 逐维执行,此处只门 use×seat。"""
    if use not in USES:
        raise RegistryError(f"未注册 use {use!r}(须 ∈ {sorted(USES)})")
    registry = require_sealed_registry(registry)
    candidates = extract_candidate_ids(payload)
    known = set(registry.records)
    unknown = candidates - known
    if unknown:
        raise PayloadGateError(
            f"{use} 腿 payload(seat={consumer_seat})含**未注册** record 引用 "
            f"{sorted(unknown)}——伪造/未知 ID 硬失败")
    _assert_no_stray_known_ids(payload, known,
                               context=f"{use} 腿 payload(seat={consumer_seat})")
    offenders = []
    for rid in sorted(candidates):
        rec = registry.get(rid)
        if use not in rec.allowed_uses or consumer_seat not in rec.allowed_consumers:
            offenders.append((rid, rec.evidence_class, sorted(rec.allowed_uses)))
    if offenders:
        raise PayloadGateError(
            f"{use} 腿 payload(seat={consumer_seat})含未授权注册 ID:"
            + "; ".join(f"{rid}[{ec},uses={u}]" for rid, ec, u in offenders))
    return candidates


def build_factor_payload_ids(registry: SealedCardRegistry, *, consumer_seat: str,
                             target_dimension: str) -> list:
    """构造-自-注册表方向(M1″):返回对 (seat, dimension) **授权 factor_positive** 的
    record_id 白名单(按 id 排序,确定性)——序列化器只放这些进正向 payload。"""
    registry = require_sealed_registry(registry)          # B2:消费边界重验
    return sorted(rid for rid, rec in registry.records.items()
                  if authorize(rec, use="factor_positive", consumer_seat=consumer_seat,
                               target_dimension=target_dimension))
