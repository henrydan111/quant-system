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
_M_LINE_RESERVED_RE = re.compile(r"^M(0[1-9]|1[0-6])$")

#: 记录 ID 语法 v1(re-review#2 M2:空/标点 ID 曾可铸)。大写字母开头 + 2-16 位
#  大写字母数字,可选恰一注册 D7 属性后缀。
RECORD_ID_GRAMMAR_VERSION = "rid_v1"
_RECORD_ID_RE = re.compile(
    r"^[A-Z][A-Z0-9]{1,15}(\.(fact|economic_linkage|timing|source_status))?$")

#: 注册 domain enum(re-review#2 M2:domain 曾不受约束,M01 可挂 domain="news")
DOMAINS = frozenset({"news", "macro", "attention", "coordination", "research"})

#: kernel 级保留命名空间(re-review#2 M2:MP/MF 前缀曾可经通用 mint 铸成 news/NFD
#  正向记录,绕开 taxonomy 工厂)。前缀命中 → 必须满足该命名空间的冻结元数据契约。
_POLICY_NS_RE = re.compile(r"^MP\d{2,}$")
_MF_NS_RE = re.compile(r"^MF[A-Z]?\d{2,}$")
_MF_CLASSES = frozenset({"MFD", "MFI", "MFA", "MFR"})


def _m_line_expected(record_id: str) -> tuple:
    """保留 M-line ID 的规范元数据:(domain, class, uses, consumers, dims)。"""
    ec, dims = M_LINE_TAXONOMY[record_id]
    uses = frozenset({"factor_positive", "context_only"}) if dims \
        else frozenset({"context_only"})
    return "macro", ec, uses, frozenset({"macro"}), dims


def _enforce_protected_namespaces(record_id: str, domain: str, evidence_class: str,
                                  uses: frozenset, consumers: frozenset,
                                  dims: frozenset) -> None:
    """kernel 级命名空间锁(re-review#2 M2)。M01-M16 逐字(含 domain);MP* 只能是
    原子政策行的精确元数据;MF* 只能是宏观快讯类(MFR 精确;MFD/MFI/MFA 只许
    context_only-无维 或 正向-恰一宏观维)。"""
    if _M_LINE_RESERVED_RE.match(record_id):
        expected = _m_line_expected(record_id)
        if (domain, evidence_class, uses, consumers, dims) != expected:
            exp_d, exp_ec, exp_uses, exp_consumers, exp_dims = expected
            raise RegistryError(
                f"{record_id} 是冻结 M-line 保留 ID(§6b M1⁴)——元数据必须与权威表"
                f"逐字一致(期望 domain={exp_d}, class={exp_ec}, uses={sorted(exp_uses)}, "
                f"consumers={sorted(exp_consumers)}, dims={sorted(exp_dims)})")
        return
    if record_id.startswith("MP"):
        if not _POLICY_NS_RE.match(record_id):
            raise RegistryError(f"MP 前缀为原子政策行保留命名空间——{record_id!r} 不合"
                                f"其语法 MP\\d{{2,}}")
        expected = ("macro", "market_state_fact",
                    frozenset({"factor_positive", "context_only"}),
                    frozenset({"macro"}), frozenset({"policy_alignment"}))
        if (domain, evidence_class, uses, consumers, dims) != expected:
            raise RegistryError(
                f"{record_id} 在 MP 保留命名空间——元数据必须是原子政策行契约"
                f"(macro/market_state_fact/正向+context/macro 席/policy_alignment)")
        return
    if record_id.startswith("MF"):
        if not _MF_NS_RE.match(record_id):
            raise RegistryError(f"MF 前缀为宏观快讯保留命名空间——{record_id!r} 不合"
                                f"其语法 MF[A-Z]?\\d{{2,}}")
        if domain != "macro" or evidence_class not in _MF_CLASSES:
            raise RegistryError(
                f"{record_id} 在 MF 保留命名空间——须 domain=macro 且类 ∈ "
                f"{sorted(_MF_CLASSES)}(得 domain={domain!r}, class={evidence_class!r})")
        if evidence_class == "MFR":
            expected = (frozenset({"penalty", "bear"}), frozenset({"macro", "bear"}),
                        frozenset({"manipulation_risk"}))
            if (uses, consumers, dims) != expected:
                raise RegistryError(f"{record_id}(MFR)元数据须为 penalty+bear/"
                                    f"macro+bear/manipulation_risk 精确契约")
            return
        ctx_only = (uses == frozenset({"context_only"}) and not dims)
        positive = (uses == frozenset({"factor_positive", "context_only"})
                    and len(dims) == 1 and dims <= MACRO_DIMENSIONS)
        if consumers != frozenset({"macro"}) or not (ctx_only or positive):
            raise RegistryError(
                f"{record_id}(MF 正向类)须 consumers={{macro}} 且 context_only-无维 "
                f"或 正向-恰一宏观维(得 uses={sorted(uses)}, dims={sorted(dims)})")


# --------------------------------------------------- 逐卡注册记录(封印)

class RegistryError(Exception):
    """元数据注册表不变量违反 —— fail-closed。"""


class PayloadGateError(Exception):
    """正向 payload 含未授权/attention_only/未注册 ID —— 硬失败(§6b B1)。"""


@dataclass(frozen=True)
class CardRecord:
    """一条**封印**逐卡元数据记录。只能经 build_card_record 构造;content_hash =
    全 SHA-256 over 规范载荷;__post_init__ verify-not-trust(伪造直接构造被识破);
    allowed_* 深只读。授权**只读元数据**,绝不看 record_id 前缀(M3″)。"""
    record_id: str
    domain: str                      # news | macro | attention | coordination | research
    evidence_class: str
    allowed_uses: frozenset
    allowed_consumers: frozenset
    allowed_dimensions: frozenset
    content_hash: str = field(default="")

    def __post_init__(self):
        verify_sealed(self._payload(), self.content_hash, field_name="card record content_hash")

    def _payload(self) -> dict:
        return {"record_id": self.record_id, "domain": self.domain,
                "evidence_class": self.evidence_class,
                "allowed_uses": sorted(self.allowed_uses),
                "allowed_consumers": sorted(self.allowed_consumers),
                "allowed_dimensions": sorted(self.allowed_dimensions)}

    @property
    def positive_ceiling(self) -> int:
        """本记录可对某维贡献的最高分(非正向类 = 0)。"""
        return EVIDENCE_CEILING.get(self.evidence_class, 0)


def build_card_record(record_id: str, *, domain: str, evidence_class: str,
                      allowed_uses, allowed_consumers, allowed_dimensions=()) -> CardRecord:
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
    # re-review#2 M2:ID 语法 + domain enum 先于一切(空/标点/越界 ID 不可铸)
    if not isinstance(record_id, str) or not _RECORD_ID_RE.match(record_id):
        raise RegistryError(
            f"record_id {record_id!r} 不合语法 {RECORD_ID_GRAMMAR_VERSION}"
            f"(大写字母开头 2-16 位大写字母数字,可选恰一注册 D7 属性后缀)")
    if domain not in DOMAINS:
        raise RegistryError(f"未注册 domain {domain!r}(须 ∈ {sorted(DOMAINS)})")
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
    # re-review Major-3 + re-review#2 M2:保留命名空间锁(M01-M16 逐字含 domain;
    # MP*/MF* 前缀 kernel 级保留,只许各自的冻结元数据契约)。
    _enforce_protected_namespaces(record_id, domain, evidence_class,
                                  uses, consumers, dims)
    payload = {"record_id": record_id, "domain": domain, "evidence_class": evidence_class,
               "allowed_uses": sorted(uses), "allowed_consumers": sorted(consumers),
               "allowed_dimensions": sorted(dims)}
    # frozensets are already immutable — no deep_ro needed for the leaf sets
    return CardRecord(record_id=record_id, domain=domain, evidence_class=evidence_class,
                      allowed_uses=uses, allowed_consumers=consumers,
                      allowed_dimensions=dims, content_hash=seal_hash(payload))


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
    """封印注册表工厂。重复 record_id → 拒(身份必须唯一)。"""
    by_id: dict[str, CardRecord] = {}
    for r in records:
        if not isinstance(r, CardRecord):
            raise RegistryError("注册表只收封印 CardRecord")
        if r.record_id in by_id:
            raise RegistryError(f"重复 record_id {r.record_id!r}")
        by_id[r.record_id] = r
    payload = {"cutoff": cutoff_iso,
               "record_hashes": sorted(r.content_hash for r in by_id.values())}
    return SealedCardRegistry(cutoff_iso=cutoff_iso, records=deep_ro(by_id),
                              registry_hash=seal_hash(payload))


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
    return sorted(rid for rid, rec in registry.records.items()
                  if authorize(rec, use="factor_positive", consumer_seat=consumer_seat,
                               target_dimension=target_dimension))
