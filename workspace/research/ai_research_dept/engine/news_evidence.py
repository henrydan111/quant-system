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
RECORD_SCHEMAS = frozenset({"generic_v1", "m_line_v1", "mp_v1", "mf_v1", "d7_child_v1"})
MF_DERIVATION_VERSION = "mf_dim_v1"

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
    - `X.attr` D7 子行:schema=d7_child_v1,派生须绑 64-hex 父记录哈希 + 与后缀
      一致的 attribute_type,维=该属性注册维,source_status 永不正向;
    - schema 与命名空间**双向绑定**:非保护 ID 只许 generic_v1。"""
    d = dict(derivation)
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
        if schema_id != "d7_child_v1":
            raise RegistryError(f"{record_id}(D7 子行后缀)须经类型化工厂"
                                f"(record_schema_id=d7_child_v1,得 {schema_id!r})")
        if evidence_class not in ("NFD", "NFI", "NFA"):
            raise RegistryError(f"D7 子行 {record_id} 类须 ∈ {{NFD, NFI, NFA}}"
                                f"(得 {evidence_class!r})")
        if d.get("attribute_type") != attr:
            raise RegistryError(f"D7 子行 {record_id} 派生 attribute_type "
                                f"{d.get('attribute_type')!r} 与后缀 {attr!r} 不符")
        ph = d.get("parent_content_hash")
        if not (isinstance(ph, str) and _HEX64_RE.fullmatch(ph)):
            raise RegistryError(f"D7 子行 {record_id} 派生须绑 64-hex 父记录哈希")
        if dims != ATTRIBUTE_DIMENSIONS[attr]:
            raise RegistryError(f"D7 子行 {record_id} 维须为属性注册维 "
                                f"{sorted(ATTRIBUTE_DIMENSIONS[attr])}(得 {sorted(dims)})")
        expected_uses = frozenset({"penalty", "bear"}) if attr == "source_status" \
            else frozenset({"factor_positive", "context_only"})
        if uses != expected_uses:
            raise RegistryError(f"D7 子行 {record_id}({attr})uses 须 "
                                f"{sorted(expected_uses)}(source_status 永不正向)")
        return
    if schema_id != "generic_v1":
        raise RegistryError(f"{record_id!r} 非保护命名空间——只许 record_schema_id="
                            f"generic_v1(得 {schema_id!r};schema 与命名空间双向绑定)")


# --------------------------------------------------- 逐卡注册记录(封印)

class RegistryError(Exception):
    """元数据注册表不变量违反 —— fail-closed。"""


class PayloadGateError(Exception):
    """正向 payload 含未授权/attention_only/未注册 ID —— 硬失败(§6b B1)。"""


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
        # re-review#3 B1:锁在构造点(工厂与直接构造同一路径)
        _enforce_protected_namespaces(
            self.record_id, self.domain, self.evidence_class,
            frozenset(self.allowed_uses), frozenset(self.allowed_consumers),
            frozenset(self.allowed_dimensions), self.record_schema_id,
            tuple(self.derivation))
        verify_sealed(self._payload(), self.content_hash, field_name="card record content_hash")

    def _payload(self) -> dict:
        return {"record_id": self.record_id, "domain": self.domain,
                "evidence_class": self.evidence_class,
                "allowed_uses": sorted(self.allowed_uses),
                "allowed_consumers": sorted(self.allowed_consumers),
                "allowed_dimensions": sorted(self.allowed_dimensions),
                "record_schema_id": self.record_schema_id,
                "derivation": [list(kv) for kv in self.derivation]}

    @property
    def positive_ceiling(self) -> int:
        """本记录可对某维贡献的最高分(非正向类 = 0)。"""
        return EVIDENCE_CEILING.get(self.evidence_class, 0)


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
        verify_sealed(self._payload(), self.registry_hash, field_name="registry_hash")

    def _payload(self) -> dict:
        # 记录序无关:按 record_id 排序其 content_hash
        return {"cutoff": self.cutoff_iso,
                "record_hashes": sorted(r.content_hash for r in self.records.values())}

    def get(self, record_id: str) -> "CardRecord | None":
        return self.records.get(record_id)


def build_card_registry(cutoff_iso: str, records: list[CardRecord]) -> SealedCardRegistry:
    """封印注册表工厂。重复 record_id → 拒(身份必须唯一)。
    re-review#3 B1:逐记录重验受保护 schema 绑定(构造点已锁,此处显式重跑)+
    **D7 子行注册表级校验**:父行必须同表存在、子行类与父行类逐字一致(kernel 结构
    锁绑父哈希但解析不了父,类等式在此闭合——`NFI01.fact` 挂 NFD 类在此拒)。"""
    by_id: dict[str, CardRecord] = {}
    for r in records:
        if not isinstance(r, CardRecord):
            raise RegistryError("注册表只收封印 CardRecord")
        if r.record_id in by_id:
            raise RegistryError(f"重复 record_id {r.record_id!r}")
        _enforce_protected_namespaces(
            r.record_id, r.domain, r.evidence_class, frozenset(r.allowed_uses),
            frozenset(r.allowed_consumers), frozenset(r.allowed_dimensions),
            r.record_schema_id, tuple(r.derivation))
        by_id[r.record_id] = r
    for rid, r in by_id.items():
        if "." in rid:
            parent = by_id.get(rid.split(".", 1)[0])
            if parent is None:
                raise RegistryError(f"D7 子行 {rid} 无父行在同一注册表——孤儿拒")
            if r.evidence_class != parent.evidence_class:
                raise RegistryError(
                    f"D7 子行 {rid} 类 {r.evidence_class!r} ≠ 父行类 "
                    f"{parent.evidence_class!r}——洗类拒(re-review#3 B1)")
    payload = {"cutoff": cutoff_iso,
               "record_hashes": sorted(r.content_hash for r in by_id.values())}
    return SealedCardRegistry(cutoff_iso=cutoff_iso, records=deep_ro(by_id),
                              registry_hash=seal_hash(payload))


def require_sealed_registry(registry) -> SealedCardRegistry:
    """消费边界强制(re-review#3 B2):只收真 SealedCardRegistry 并重验其封印——
    duck-typed 冒牌对象(裸 .registry_hash 属性)在每个消费点拒,不再只在构造点。"""
    if not isinstance(registry, SealedCardRegistry):
        raise RegistryError("registry 必须是密封 SealedCardRegistry"
                            f"(得 {type(registry).__name__};duck-typed 拒,B2)")
    verify_sealed(registry._payload(), registry.registry_hash, field_name="registry_hash")
    return registry


# --------------------------------------------------- 三元授权 + 上限算术

def authorize(record: CardRecord, *, use: str, consumer_seat: str,
              target_dimension: "str | None" = None) -> bool:
    """三元授权(M1‴ line 350):`use ∈ allowed_uses ∧ consumer_seat ∈ allowed_consumers
    ∧ (target_dimension 未给 或 ∈ allowed_dimensions)`。**只读元数据,绝不看 ID 前缀**。
    factor_positive 用途必须给 target_dimension(否则拒——正向必须指向一个注册维)。"""
    if not isinstance(record, CardRecord):
        raise RegistryError("authorize 只接受封印 CardRecord")
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
    registry = require_sealed_registry(registry)          # B2:消费边界重验
    """证据类上限算术(§0/M2 line 122):某维的上限 = 所引证据中,对 (seat, dimension)
    授权 factor_positive 的记录里**最强合格证据类的上限**;无合格证据 → 0(NO-SCORE)。
    传闻/协同/attention_only/未注册引用**不贡献**(它们授权不过 → 天然被排除)。"""
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

def scan_payload_ids(payload, registry: SealedCardRegistry) -> set:
    """递归扫描完整序列化 payload(dict/list/tuple/str 任意嵌套),返回其中出现的**任何
    已注册 record_id 集合**——覆盖每卡/键/嵌套/别名/散文内联(M1″ line 286)。
    re-review Major-2:**最长优先 alternation 单趟扫描**——一个 token 恰解析为一条
    记录:`NFD01.economic_linkage`(D7 子行)不再同时命中父 `NFD01`(旧逐 ID 搜索里
    `.` 是词边界导致父子双解析);词边界仍防 `M1` 命中 `M16`、`NFD1` 命中 `NFD11`。"""
    registry = require_sealed_registry(registry)          # B2:消费边界重验
    known = sorted(registry.records, key=len, reverse=True)   # 最长优先
    if not known:
        return set()
    pat = re.compile(r"(?<![A-Za-z0-9_])(?:"
                     + "|".join(re.escape(k) for k in known)
                     + r")(?![A-Za-z0-9_])")
    found: set = set()

    def walk(o):
        if isinstance(o, str):
            found.update(pat.findall(o))
        elif isinstance(o, dict):
            for k, v in o.items():
                walk(k)
                walk(v)
        elif isinstance(o, (list, tuple)):
            for x in o:
                walk(x)
    walk(payload)
    return found


def assert_factor_payload(payload, registry: SealedCardRegistry, *,
                          consumer_seat: str, target_dimension: str) -> set:
    """**承重门**(§6b B1 line 440 / M1″):正向 factor payload 内出现的**每一个**已注册
    record_id 都必须对 (seat, dimension) 授权 factor_positive;任何 attention_only /
    coordination_risk / 传闻(NFR/MFR) / 未授权 / 域外记录出现 → PayloadGateError(物理
    排除,非仅挡 evidence_spans)。返回通过的已授权 ID 集(便于调用侧对账)。"""
    present = scan_payload_ids(payload, registry)
    offenders = []
    for rid in sorted(present):
        rec = registry.get(rid)
        if not authorize(rec, use="factor_positive", consumer_seat=consumer_seat,
                         target_dimension=target_dimension):
            offenders.append((rid, rec.evidence_class, sorted(rec.allowed_uses)))
    if offenders:
        raise PayloadGateError(
            f"正向 payload(seat={consumer_seat}, dim={target_dimension})含未授权注册 ID:"
            + "; ".join(f"{rid}[{ec},uses={u}]" for rid, ec, u in offenders))
    return present


def build_factor_payload_ids(registry: SealedCardRegistry, *, consumer_seat: str,
                             target_dimension: str) -> list:
    """构造-自-注册表方向(M1″):返回对 (seat, dimension) **授权 factor_positive** 的
    record_id 白名单(按 id 排序,确定性)——序列化器只放这些进正向 payload。"""
    registry = require_sealed_registry(registry)          # B2:消费边界重验
    return sorted(rid for rid, rec in registry.records.items()
                  if authorize(rec, use="factor_positive", consumer_seat=consumer_seat,
                               target_dimension=target_dimension))
