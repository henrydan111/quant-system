# SCRIPT_STATUS: ACTIVE — 新闻快讯:双卡渲染器(正向原子事实卡 + 密封注意力上下文卡;NF §7 step 5)
"""Two-card flash renderer — positive atomic-facts card + sealed attention context card.

设计 v1.12 §7 step 5(在 step 5+6 kernel [news_evidence.py](news_evidence.py) 之上):
- **证据类围栏**(§2 step 5+7,确定性):个股路→NFD(官方证实)/NFI(署名媒体);
  行业/概念路→NFA;宏观路→MFD/MFI;传闻/操纵/推广→NFR·MFR(正向 0,专属风险节);
  行情/评论/未证实/观点→`news_context`(不计分上下文,fail-closed 绝不正向);
  coordination_flag→独立 NFC 记录(coordination_risk)。**转载不清除传闻/操纵旗**
  (§2 step 4)——围栏只看分型+路由,不看 n_outlets。
- **正向快讯节 = 去重原子事实,零聚合计数行**(B1′):行 ID 用类前缀
  `NFD##/NFI##/NFA##`(§0 M2 字面记法);按 fact_occurrence_id 去重(M3 事实级独占);
  确定性排序(importance↓, first_visible↓, fact_id↑)。风险节(NFR/NFC)与上下文节
  (NFU)只进 `restricted_text`——**双腿元数据过滤**(M2‴):factor 腿只见
  `factor_payload_text`,penalty/bear 腿消费 restricted 切片。渲染器对自己的 factor
  切片跑 `assert_factor_payload` 自检(verify-not-trust 用在自己身上)。
- **密封 attention_context_card**(D6):flow 计数/广度/velocity 全 attention_only;
  覆盖不完整 → not_applicable 行(**绝不造 0**);仅 bear/chief/display 消费;
  factor 切片恒空。
- **D7 原子属性行**(importance≥4):`attribute_type ∈ {fact, economic_linkage,
  timing, source_status}` 各只入注册维(fact→materiality;linkage→fundamental_link;
  timing→catalyst/tradeability;source_status→confidence_cap,**永不正向**);
  每 `(claim_id, attribute_type)` 至多一行;每事件 ≤4 行。
- **B1′ 存量分类**:`is_legacy_attention_id` 判定 N00/NDA*/NIA* 为 attention_only
  (物理移出在席位接线块;此处提供语义判定钩子)。

卡片密封:`RenderedCard` 全 SHA-256(卡名/cutoff/两切片/记录哈希集),供 M3″ 空头
校验的"卡哈希匹配"。本模块零 LLM 依赖(消费 type_batch 的输出 dict)。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

from workspace.research.ai_research_dept.engine.cards import sanitize_text
from workspace.research.ai_research_dept.engine.news_evidence import (
    ATTRIBUTE_DIMENSIONS, RegistryError, assert_factor_payload, build_card_record,
    build_card_registry, require_sealed_registry,
)
from workspace.research.ai_research_dept.engine.news_seal import seal_hash, verify_sealed

# --------------------------------------------------- 证据类围栏(§2 step 5+7)

#: 快讯正向行对 news 席开放的维(未拆行时;D7 拆行后各行收窄到单维)
_NEWS_POSITIVE_DIMS = frozenset({
    "event_materiality", "fundamental_link", "novelty",
    "catalyst_timing", "tradeability_at_horizon"})


#: 注册路由 enum(re-review Major-1:未知路由绝不默认落宏观正向)
ROUTES = frozenset({"stock", "industry_concept", "macro"})
_DIRECTIONS = frozenset({"利好", "中性", "利空"})


def assign_evidence_class(typing_rec: dict, primary_route: str) -> str:
    """确定性证据类围栏。**独立 fail-closed**(re-review Major-1:即使不经 type_batch
    直接调用,非法路由/分型值也硬失败,绝不默认落到正向类)。优先级:
    1) 推广 / is_rumor / 传闻 → NFR(宏观路 MFR)——正向 0,风险节;
    2) 行情/评论/未证实/观点 → news_context(信息性,不计分)——未证实旗
       **不因转载清除**,多源转载的未证实内容仍不正向;
    3) 事实 × {官方证实→D 类, 署名媒体→I 类} × 路由 {stock→NFD/NFI,
       industry_concept→NFA, macro→MFD/MFI}。"""
    from workspace.research.ai_research_dept.engine.news_ingest import (
        CONTENT_KIND, VERIFICATION_STATUS,
    )
    if primary_route not in ROUTES:
        raise RegistryError(f"未注册 primary_route {primary_route!r}(须 ∈ {sorted(ROUTES)})"
                            f"——绝不默认归宏观正向(Major-1)")
    kind = typing_rec.get("content_kind")
    status = typing_rec.get("verification_status")
    rumor = typing_rec.get("is_rumor")
    if kind not in CONTENT_KIND:
        raise RegistryError(f"未注册 content_kind {kind!r}——围栏拒绝(Major-1)")
    if status not in VERIFICATION_STATUS:
        raise RegistryError(f"未注册 verification_status {status!r}——围栏拒绝(Major-1)")
    if type(rumor) is not bool:
        raise RegistryError(f"is_rumor 须字面 bool(得 {rumor!r})——围栏拒绝(Major-1)")
    macro = primary_route == "macro"
    if kind == "推广" or rumor is True or status == "传闻":
        return "MFR" if macro else "NFR"
    if kind in ("行情", "评论") or status in ("未证实", "观点"):
        return "news_context"
    if primary_route == "stock":
        return "NFD" if status == "官方证实" else "NFI"
    if primary_route == "industry_concept":
        return "NFA"
    return "MFD" if status == "官方证实" else "MFI"


def _validate_typing(typing_rec: dict) -> dict:
    """集中式分型校验(re-review#2 M3:assess 与渲染器入口共用同一校验器,渲染层
    不再 int() 强转)。返回规范化副本:importance 缺省 2,否则须**字面** int ∈ [0,5]
    (bool/float/str 一律拒);event_type/direction ∈ 注册 enum。围栏字段
    (status/kind/rumor)由 assign_evidence_class 校验。"""
    from workspace.research.ai_research_dept.engine.news_ingest import EVENT_TYPES
    t = dict(typing_rec)
    if t.get("event_type") not in EVENT_TYPES:
        raise RegistryError(f"未注册 event_type {t.get('event_type')!r}")
    if t.get("direction") not in _DIRECTIONS:
        raise RegistryError(f"未注册 direction {t.get('direction')!r}")
    imp = t.get("importance", 2)
    if type(imp) is not int or not 0 <= imp <= 5:
        raise RegistryError(f"importance 须字面 int ∈ [0,5](得 {imp!r})")
    t["importance"] = imp
    return t


def assess_flash(cluster, typing_rec: dict, route: dict, *,
                 coordination_fired: bool = False) -> dict:
    """组装一条簇的确定性证据评定(渲染输入单元)。全部字段经集中校验器(M3)。"""
    t = _validate_typing(typing_rec)
    return {"cluster": cluster, "typing": t, "route": dict(route),
            "evidence_class": assign_evidence_class(t, route["primary_route"]),
            "coordination_fired": bool(coordination_fired)}


# --------------------------------------------------- 密封渲染卡

@dataclass(frozen=True)
class RenderedCard:
    """密封渲染卡。两个文本切片实现双腿元数据过滤(M2‴):`factor_payload_text`
    只含 factor_positive 记录(factor 腿唯一可见);`restricted_text` 为风险/上下文
    (penalty/bear/context 消费)。card_hash = 全 SHA-256(供 M3″ 卡哈希匹配)。"""
    card_name: str
    cutoff_iso: str
    factor_payload_text: str
    restricted_text: str
    record_ids: tuple
    records_hash: str
    #: 本卡铸出的 D7BaseFact 总体哈希集(re-review#2 B1:束校验描述符成员资格——
    #  自铸描述符不在卡封总体内,直接拒)
    base_fact_hashes: tuple = ()
    card_hash: str = field(default="")

    def __post_init__(self):
        if self.card_hash:
            verify_sealed(self._payload(), self.card_hash, field_name="card_hash")
        else:
            object.__setattr__(self, "card_hash", seal_hash(self._payload()))

    def _payload(self) -> dict:
        return {"card": self.card_name, "cutoff": self.cutoff_iso,
                "factor_text": self.factor_payload_text,
                "restricted_text": self.restricted_text,
                "record_ids": list(self.record_ids), "records_hash": self.records_hash,
                "base_fact_hashes": list(self.base_fact_hashes)}


def _records_hash(records: list) -> str:
    return seal_hash(sorted(r.content_hash for r in records))


@dataclass(frozen=True)
class D7BaseFact:
    """密封 D7 基事实描述符(re-review#2 B1:拆行的证据类/importance/claim/事实
    血缘**只能**来自渲染器铸的本描述符——调用方无权提供,NFI 基行洗成 NFD 子行、
    imp-1 谎报过 ≥4 门的路径从源头封死)。由 render_news_flash_section 对每条
    正向行(NFD/NFI/NFA)铸出;base_content_hash 绑对应 CardRecord。"""
    base_record_id: str
    base_content_hash: str
    claim_id: str
    fact_cluster_id: str
    evidence_class: str
    importance: int
    fact_hash: str = field(default="")

    def __post_init__(self):
        if self.fact_hash:
            verify_sealed(self._payload(), self.fact_hash, field_name="D7BaseFact fact_hash")
        else:
            object.__setattr__(self, "fact_hash", seal_hash(self._payload()))

    def _payload(self) -> dict:
        return {"base_record_id": self.base_record_id,
                "base_content_hash": self.base_content_hash,
                "claim_id": self.claim_id, "fact_cluster_id": self.fact_cluster_id,
                "evidence_class": self.evidence_class, "importance": self.importance}


def _age_str(cutoff, first_visible_iso: str) -> str:
    hrs = (pd.Timestamp(cutoff) - pd.Timestamp(first_visible_iso)).total_seconds() / 3600
    return f"{hrs / 24:.1f}d" if hrs >= 48 else f"{hrs:.1f}h"


def _c70(content: str) -> str:
    return sanitize_text(content)[:70]


# --------------------------------------------------- 正向快讯节 + 风险/上下文切片

#: 事实级证据身份(re-review Blocker:去重前先比这组字段——冲突=硬失败,
#  importance 只许排序、绝不选择证据类/安全旗)
_FACT_IDENTITY_FIELDS = ("event_type", "verification_status", "content_kind",
                         "is_rumor", "direction")


def _fact_identity(a: dict) -> tuple:
    t = a["typing"]
    return (a["evidence_class"], a["route"].get("primary_route"),
            *(t.get(f) for f in _FACT_IDENTITY_FIELDS))


def render_news_flash_section(assessed: list[dict], cutoff) -> tuple:
    """渲染快讯双切片(§7 step 5)。返回 (密封卡, 全部 CardRecord, 正向行的密封
    D7BaseFact 列表——D7 拆行的唯一权威来源, re-review#2 B1)。
    - factor 切片:仅 NFD/NFI/NFA 行(去重原子事实,零聚合计数行,B1′);
    - restricted 切片:风险节(NFR + NFC)+ 上下文节(NFU);
    - **宏观路直接拒**(re-review Major-1:查 primary_route 而非类——宏观路评论
      曾以 news_context 类绕过类检;它们属宏观卡,§6);
    - **evidence_class 重算比对**(Major-1:不信 assessed 携带的类,围栏重算不符=拒);
    - **按 fact_occurrence_id 分组先于排序**(re-review Blocker):组内证据身份
      (类/路由/分型/传闻旗/方向)冲突 → 硬失败(importance 绝不选择证据类——
      旧实现里 NFD imp=5 会吞掉同事实的 NFR imp=1,传闻/协同旗静默丢失);
      身份一致的重复 → 合并(importance 取 max,coordination_fired 取 OR);
    - 排序 (importance↓, visible↓, fact↑) 只作用于**已合并**的事实。
    自检:factor 切片过 assert_factor_payload(渲染器不信自己)。"""
    cutoff_iso = pd.Timestamp(cutoff).isoformat()
    validated = []
    for a in assessed:
        # re-review#2 M3:渲染器入口**完整**重校验分型(不止围栏字段)——assess 后
        # 被改的 event_type/direction/importance("5"/5.0/True)在此拒,层内无 int() 强转
        t = _validate_typing(a["typing"])
        if a["route"].get("primary_route") == "macro":
            raise RegistryError("宏观路快讯不入 news 卡——进宏观卡(§6,Major-1 按路由拒)")
        recomputed = assign_evidence_class(t, a["route"]["primary_route"])
        if recomputed != a["evidence_class"]:
            raise RegistryError(
                f"evidence_class 伪造:携带 {a['evidence_class']!r} 围栏重算 "
                f"{recomputed!r}——拒绝渲染(Major-1 verify-not-trust)")
        v = dict(a)
        v["typing"] = t
        validated.append(v)
    # Blocker:先按事实分组,身份冲突硬失败,一致则合并(imp=max, coord=OR)
    groups: dict[str, list] = {}
    for a in validated:
        groups.setdefault(a["cluster"].fact_occurrence_id, []).append(a)
    deduped = []
    for fid, grp in groups.items():
        idents = {_fact_identity(g) for g in grp}
        if len(idents) > 1:
            raise RegistryError(
                f"事实 {fid} 存在冲突评定 {sorted(idents)}——拒绝渲染(Blocker:"
                f"importance 不得选择证据类/安全旗,冲突必须上游解决)")
        rep = sorted(grp, key=lambda g: (
            -g["typing"]["importance"],
            g["cluster"].cluster_first_visible_at_iso,
            str(g["route"].get("content", ""))))[0]
        merged = dict(rep)
        merged["typing"] = dict(rep["typing"])
        merged["typing"]["importance"] = max(g["typing"]["importance"] for g in grp)
        merged["coordination_fired"] = any(g["coordination_fired"] for g in grp)
        deduped.append(merged)
    deduped.sort(key=lambda a: (
        -a["typing"]["importance"],
        -pd.Timestamp(a["cluster"].cluster_first_visible_at_iso).value,
        a["cluster"].fact_occurrence_id))

    records: list = []
    base_facts: list = []
    counters: dict[str, int] = {}
    fact_lines, risk_lines, ctx_lines = [], [], []

    def _next_id(prefix: str) -> str:
        counters[prefix] = counters.get(prefix, 0) + 1
        return f"{prefix}{counters[prefix]:02d}"

    for a in deduped:
        c, t = a["cluster"], a["typing"]
        ec = a["evidence_class"]
        content = _c70(_member_content(a))
        age = _age_str(cutoff_iso, c.cluster_first_visible_at_iso)
        stars = "★" * t["importance"]
        if ec in ("NFD", "NFI", "NFA"):
            rid = _next_id(ec)
            rec = build_card_record(
                rid, domain="news", evidence_class=ec,
                allowed_uses={"factor_positive", "context_only"},
                allowed_consumers={"news"}, allowed_dimensions=_NEWS_POSITIVE_DIMS)
            records.append(rec)
            # re-review#2 B1:D7 拆行权威 = 渲染器铸的密封基事实描述符
            base_facts.append(D7BaseFact(
                base_record_id=rid, base_content_hash=rec.content_hash,
                claim_id=f"CLAIM:{c.fact_occurrence_id}",
                fact_cluster_id=c.fact_occurrence_id,
                evidence_class=ec, importance=t["importance"]))
            fact_lines.append(f"- [{rid}][{age}|{stars}|{ec}]{t['event_type']}"
                              f"|{content}|{t['direction']}")
        elif ec == "NFR":
            rid = _next_id("NFR")
            records.append(build_card_record(
                rid, domain="news", evidence_class="NFR",
                allowed_uses={"penalty", "bear"}, allowed_consumers={"news", "bear"},
                allowed_dimensions={"manipulation_risk"}))
            risk_lines.append(f"- [{rid}][{age}|传闻/操纵]{t['event_type']}|{content}")
        else:                                   # news_context
            rid = _next_id("NFU")
            records.append(build_card_record(
                rid, domain="news", evidence_class="news_context",
                allowed_uses={"context_only", "bear"}, allowed_consumers={"news", "bear"}))
            ctx_lines.append(f"- [{rid}][{age}|{t['verification_status']}]"
                             f"{t['event_type']}|{content}|{t['direction']}")
        if a["coordination_fired"]:             # 独立 NFC 记录(可与任何类并存)
            nid = _next_id("NFC")
            records.append(build_card_record(
                nid, domain="coordination", evidence_class="coordination_risk",
                allowed_uses={"penalty", "bear"}, allowed_consumers={"news", "bear"},
                allowed_dimensions={"coordination_risk"}))
            risk_lines.append(f"- [{nid}][协同]同措辞多源突发转载、无结构化背书"
                              f"(事实 {c.fact_occurrence_id[:24]}…)")

    factor_text = ("—— 快讯事实(去重原子,NFD≤5/NFI≤3/NFA≤3)——\n"
                   + "\n".join(fact_lines)) if fact_lines else \
        "—— 快讯事实:无 ——"
    restricted = []
    if risk_lines:
        restricted.append("—— 快讯风险(传闻/操纵/协同;不支撑正向分,自动入空头证伪)——\n"
                          + "\n".join(risk_lines))
    if ctx_lines:
        restricted.append("—— 快讯上下文(行情/评论/未证实;不计分)——\n"
                          + "\n".join(ctx_lines))
    restricted_text = "\n".join(restricted)

    # 自检(verify-not-trust 用在自己身上):factor 切片内每个注册 ID 都必须
    # factor_positive 授权;NFR/NFC/NFU 若泄入即在此硬失败
    reg = build_card_registry(cutoff_iso, records)
    assert_factor_payload(factor_text, reg, consumer_seat="news",
                          target_dimension="event_materiality")
    card = RenderedCard(card_name="news_flash_section", cutoff_iso=cutoff_iso,
                        factor_payload_text=factor_text, restricted_text=restricted_text,
                        record_ids=tuple(sorted(r.record_id for r in records)),
                        records_hash=_records_hash(records),
                        base_fact_hashes=tuple(sorted(bf.fact_hash for bf in base_facts)))
    return card, records, base_facts


def _member_content(a: dict) -> str:
    """簇的代表正文:路由输入的 content(调用侧传入 route['content'] 时优先),
    否则退回簇第一成员的 datetime 占位——正式管线 route 恒带 content。"""
    if "content" in a["route"]:
        return str(a["route"]["content"])
    return str(a["cluster"].members[0].get("content", a["cluster"].cluster_id))


# --------------------------------------------------- 注意力上下文卡(D6,密封独立)

def render_attention_context_card(flow: dict, cutoff, *,
                                  extra_rows: tuple = ()) -> tuple[RenderedCard, list]:
    """独立密封 attention_context_card(B1/D6)。全部记录 attention_only(仅
    bear/chief/display 消费);factor 切片**恒空**。flow=flow_features 输出;
    None 值渲染 not_applicable(**绝不造 0**)。extra_rows=[(id, text)] 容纳
    未来移入的 N00/NDA/NIA 全景行与 D6 截面百分位/HHI(冻结分母落地后)。"""
    cutoff_iso = pd.Timestamp(cutoff).isoformat()
    records, lines = [], []

    def _att(rid: str) -> str:
        records.append(build_card_record(
            rid, domain="attention", evidence_class="attention_only",
            allowed_uses={"context_only", "bear"},
            allowed_consumers={"bear", "chief", "display"}))
        return rid

    def _fmt(v) -> str:
        return "not_applicable" if v is None else str(v)

    lines.append("【注意力上下文卡】(attention_only;绝不入正向计分;仅空头/首席/展示)")
    lines.append(f"- [{_att('NFV01')}]事实占位流强度: 1d={_fmt(flow.get('flow_count_1d'))} "
                 f"5d={_fmt(flow.get('flow_count_5d'))} 20d={_fmt(flow.get('flow_count_20d'))}")
    lines.append(f"- [{_att('NFV02')}]措辞广度(1d 唯一源家族): "
                 f"{_fmt(flow.get('coverage_breadth_1d'))}")
    vel = flow.get("flow_velocity")
    vel_s = f"{vel:.2f}" if isinstance(vel, (int, float)) else "not_applicable"
    lines.append(f"- [{_att('NFV03')}]velocity(=count_1d/(count_20d/20)): {vel_s}"
                 f" | {flow.get('flow_velocity_status', 'not_applicable')}")
    for rid, text in extra_rows:
        lines.append(f"- [{_att(str(rid))}]{sanitize_text(text)}")

    # re-review Major-2:封印前必须过注册表构造——重复 ID(如 extra_rows 撞 NFV01)
    # 在此拒绝,绝不铸出含重复身份的密封卡
    build_card_registry(cutoff_iso, records)
    card = RenderedCard(card_name="attention_context_card", cutoff_iso=cutoff_iso,
                        factor_payload_text="",              # 恒空:本卡无正向切片
                        restricted_text="\n".join(lines),
                        record_ids=tuple(sorted(r.record_id for r in records)),
                        records_hash=_records_hash(records))
    return card, records


# --------------------------------------------------- D7 原子属性行(importance≥4)

#: 属性→注册维表本体在 kernel(re-review#3 B1:D7 子行结构契约由 kernel 强制);
#  此处保留类型元组(§6b M4′:source_status 永不正向 materiality)
ATTRIBUTE_TYPES = tuple(sorted(ATTRIBUTE_DIMENSIONS))
MAX_ATTRIBUTE_ROWS = 4
D7_IMPORTANCE_FLOOR = 4


@dataclass(frozen=True)
class AttributeRow:
    """D7 密封原子属性行:claim/fact/evidence_group 血缘 + 属性作用域。"""
    row_id: str
    claim_id: str
    fact_cluster_id: str
    evidence_group_id: str
    attribute_type: str
    text: str
    row_hash: str = field(default="")

    def __post_init__(self):
        if self.row_hash:
            verify_sealed(self._payload(), self.row_hash, field_name="attribute row_hash")
        else:
            object.__setattr__(self, "row_hash", seal_hash(self._payload()))

    def _payload(self) -> dict:
        return {"row_id": self.row_id, "claim_id": self.claim_id,
                "fact_cluster_id": self.fact_cluster_id,
                "evidence_group_id": self.evidence_group_id,
                "attribute_type": self.attribute_type, "text": self.text}


def _build_attribute_records(base_record_id: str, *, claim_id: str, fact_cluster_id: str,
                             evidence_class: str, importance: int,
                             parent_content_hash: str, attributes: dict) -> list[tuple]:
    """(私有,re-review#2 M1:唯一入口是 build_attribute_bundle)把 importance≥4 的
    重大直接事件拆为原子属性行(D7)。返回 [(AttributeRow, CardRecord)];每行
    record_id = `{base}.{attr}`,经 **d7_child_v1 类型化 schema** 铸造(re-review#3
    B1:密封父记录哈希 + attribute_type 派生,通用铸造对带后缀 ID 一律拒),维收窄到
    该属性的注册维。强制:importance≥4 才拆;非空且 ≤4 行(re-review#3 m1);
    attribute_type 注册;source_status 行 uses={penalty, bear}(永不 factor_positive)。"""
    if importance < D7_IMPORTANCE_FLOOR:
        raise RegistryError(
            f"D7 拆行仅限 importance≥{D7_IMPORTANCE_FLOOR}(得 {importance})——"
            f"小事件保持单行")
    if not attributes:
        raise RegistryError("D7 拆分 attributes 不得为空(re-review#3 m1:空拆分会"
                            "降级证据却不产任何子行)")
    if len(attributes) > MAX_ATTRIBUTE_ROWS:
        raise RegistryError(f"每事件属性行 ≤{MAX_ATTRIBUTE_ROWS}(得 {len(attributes)})")
    if evidence_class not in ("NFD", "NFI", "NFA"):
        raise RegistryError(f"D7 只拆正向类事件(得 {evidence_class})")
    out = []
    group = f"{claim_id}:attrs"
    for attr, text in attributes.items():   # dict 键唯一 = 本调用内每属性恰一
        if attr not in ATTRIBUTE_TYPES:
            raise RegistryError(f"未注册 attribute_type {attr!r}(须 ∈ {ATTRIBUTE_TYPES})")
        rid = f"{base_record_id}.{attr}"
        deriv = (("parent_content_hash", parent_content_hash), ("attribute_type", attr))
        if attr == "source_status":
            rec = build_card_record(rid, domain="news", evidence_class=evidence_class,
                                    allowed_uses={"penalty", "bear"},
                                    allowed_consumers={"news", "bear"},
                                    allowed_dimensions=ATTRIBUTE_DIMENSIONS[attr],
                                    record_schema_id="d7_child_v1", derivation=deriv)
        else:
            rec = build_card_record(rid, domain="news", evidence_class=evidence_class,
                                    allowed_uses={"factor_positive", "context_only"},
                                    allowed_consumers={"news"},
                                    allowed_dimensions=ATTRIBUTE_DIMENSIONS[attr],
                                    record_schema_id="d7_child_v1", derivation=deriv)
        row = AttributeRow(row_id=rid, claim_id=claim_id,
                           fact_cluster_id=fact_cluster_id, evidence_group_id=group,
                           attribute_type=attr, text=sanitize_text(text))
        out.append((row, rec))
    return out


@dataclass(frozen=True)
class AttributeBundle:
    """D7 **决策级**密封束(re-review#2 B1/M1)。一个决策的**完整**拆分总体经恰一束:
    - 拆行权威(类/importance/claim/事实)只来自渲染器铸的密封 D7BaseFact——束封
      **每个子行与降级基行的 content_hash**(授权元数据入印:NFI-子 与 NFD-子 变体
      绝不可能同哈希)+ 源注册表哈希 + **最终注册表哈希**(在工厂内构造并验证);
    - decision_id + cutoff 绑定:下游注册表须恰一匹配 final_registry_hash
      (`verify_bundle_registry`),两个束/两次调用无法都成为同一决策的权威。"""
    decision_id: str
    cutoff_iso: str
    source_card_hash: str            # re-review#3 M1:绑铸出卡的精确身份
    base_fact_hashes: tuple          # re-review#3 M1:精确基事实总体(非成员子集)
    source_registry_hash: str
    claim_ids: tuple
    row_hashes: tuple
    child_record_hashes: tuple
    demoted_record_hashes: tuple
    final_registry_hash: str
    bundle_hash: str = field(default="")

    def __post_init__(self):
        if self.bundle_hash:
            verify_sealed(self._payload(), self.bundle_hash, field_name="bundle_hash")
        else:
            object.__setattr__(self, "bundle_hash", seal_hash(self._payload()))

    def _payload(self) -> dict:
        return {"decision_id": self.decision_id, "cutoff": self.cutoff_iso,
                "source_card_hash": self.source_card_hash,
                "base_fact_hashes": list(self.base_fact_hashes),
                "source_registry_hash": self.source_registry_hash,
                "claim_ids": list(self.claim_ids), "row_hashes": list(self.row_hashes),
                "child_record_hashes": list(self.child_record_hashes),
                "demoted_record_hashes": list(self.demoted_record_hashes),
                "final_registry_hash": self.final_registry_hash}


def build_attribute_bundle(splits: list[dict], base_facts: list, base_records: list,
                           *, card: RenderedCard, decision_id: str, cutoff) -> tuple:
    """一个决策的**完整** D7 拆分总体 → 恰一密封束(re-review#2 B1/M1)。

    splits 每项**只许** {base_record_id, attributes}——证据类/importance/claim/事实
    血缘一律取自渲染器铸的密封 D7BaseFact(B1:调用方无权提供,NFI→NFD 洗类、
    imp 谎报过 ≥4 门在源头封死;多余键=拒)。强制:
    - **card 绑定**:base_records 总体哈希 == card.records_hash、cutoff == 卡 cutoff、
      每个描述符 fact_hash ∈ 卡封 base_fact_hashes(自铸描述符直接拒);
    - 描述符 evidence_class 与基行记录逐字一致(洗类双保险);
    - base_record_id 全局恰一(同基两拆=拒)+ claim 全局恰一;
    - D7BaseFact 密封自验、base_content_hash 与快讯节记录逐字一致;
    - 基行须为正向记录;被拆基行**重铸 context_only**(broad 行与属性行绝不同时正向);
    - **最终注册表在工厂内构造并验证**(重复身份在此拒,不留给下游);
    - 束封 decision_id/cutoff/源注册表哈希/全部子行与降级行 content_hash/最终注册表
      哈希——下游用 `verify_bundle_registry` 要求恰一匹配。
    返回 (bundle, rows, final_registry)。"""
    cutoff_iso = pd.Timestamp(cutoff).isoformat()
    # re-review#3 M1:decision_id 严格非空字符串,绝不 str() 强转(1 与 "1" 不同一)
    if not isinstance(decision_id, str) or not decision_id.strip():
        raise RegistryError(f"decision_id 须非空 str(得 {decision_id!r},不强转)")
    if not isinstance(card, RenderedCard):
        raise RegistryError("card 必须是密封 RenderedCard(B1:束绑定其铸出卡)")
    verify_sealed(card._payload(), card.card_hash, field_name="card_hash")
    if cutoff_iso != card.cutoff_iso:
        raise RegistryError(f"cutoff {cutoff_iso} 与卡 cutoff {card.cutoff_iso} 不符")
    if _records_hash(base_records) != card.records_hash:
        raise RegistryError("base_records 与卡封记录总体不符(B1:束只认卡的记录集)")
    # re-review#3 M1:基事实总体须与卡封**精确相等**(子集/超集皆拒,非成员检查)
    supplied_hashes = sorted(bf.fact_hash for bf in base_facts
                             if isinstance(bf, D7BaseFact))
    if len(supplied_hashes) != len(base_facts) or \
            supplied_hashes != sorted(card.base_fact_hashes):
        raise RegistryError(
            "base_facts 与卡封基事实总体不精确相等——子集/超集/自铸描述符拒"
            f"(B1/M1:得 {len(base_facts)} 个 vs 卡封 {len(card.base_fact_hashes)} 个)")
    source_registry = build_card_registry(cutoff_iso, base_records)
    facts_by_id = {bf.base_record_id: bf for bf in base_facts}
    recs_by_id = {r.record_id: r for r in base_records}
    seen_bases, seen_claims = set(), set()
    rows, attr_records, demoted_ids = [], [], []
    for sp in splits:
        extra = set(sp) - {"base_record_id", "attributes"}
        if extra:
            raise RegistryError(
                f"split 只许 {{base_record_id, attributes}}——多余键 {sorted(extra)} "
                f"(B1:证据类/importance/血缘无调用方权威)")
        bid = sp["base_record_id"]
        if bid in seen_bases:
            raise RegistryError(f"base {bid!r} 全局重复拆分(M1)")
        seen_bases.add(bid)
        bf = facts_by_id.get(bid)
        if bf is None:
            raise RegistryError(f"{bid!r} 无密封 D7BaseFact——非渲染器正向行不可拆(B1)")
        base = recs_by_id.get(bid)
        if base is None:
            raise RegistryError(f"base_record_id {bid!r} 不在快讯节记录集")
        if bf.base_content_hash != base.content_hash:
            raise RegistryError(f"D7BaseFact 与基行记录不符({bid}):描述符哈希 "
                                f"{bf.base_content_hash[:12]} ≠ 记录 {base.content_hash[:12]}")
        if bf.evidence_class != base.evidence_class:
            raise RegistryError(f"D7BaseFact 类 {bf.evidence_class!r} ≠ 基行记录类 "
                                f"{base.evidence_class!r}——洗类拒(B1)")
        if "factor_positive" not in base.allowed_uses:
            raise RegistryError(f"基行 {base.record_id} 非正向记录——无从拆分")
        if bf.claim_id in seen_claims:
            raise RegistryError(f"claim {bf.claim_id!r} 全局重复拆分(M1)")
        seen_claims.add(bf.claim_id)
        # re-review#3 m1:降级 broad 基行的拆分必须含 fact 属性(证据不凭空消失)
        if "fact" not in sp["attributes"]:
            raise RegistryError(f"拆分 {bid} 缺 'fact' 属性——降级基行的拆分必须"
                                f"保留事实行(re-review#3 m1)")
        pairs = _build_attribute_records(
            bid, claim_id=bf.claim_id, fact_cluster_id=bf.fact_cluster_id,
            evidence_class=bf.evidence_class, importance=bf.importance,
            parent_content_hash=base.content_hash, attributes=sp["attributes"])
        rows.extend(r for r, _ in pairs)
        attr_records.extend(rec for _, rec in pairs)
        demoted_ids.append(base.record_id)
    # 被拆事件的基行降级 context_only(broad 行与属性行绝不同时正向)
    final_records, demoted_records = [], []
    for r in base_records:
        if r.record_id in demoted_ids:
            demoted = build_card_record(
                r.record_id, domain=r.domain, evidence_class=r.evidence_class,
                allowed_uses={"context_only"}, allowed_consumers=r.allowed_consumers)
            final_records.append(demoted)
            demoted_records.append(demoted)
        else:
            final_records.append(r)
    final_records.extend(attr_records)
    # M1:最终注册表在工厂内构造并验证(重复身份在此拒,不留给下游)
    final_registry = build_card_registry(cutoff_iso, final_records)
    bundle = AttributeBundle(
        decision_id=decision_id, cutoff_iso=cutoff_iso,
        source_card_hash=card.card_hash,
        base_fact_hashes=tuple(sorted(card.base_fact_hashes)),
        source_registry_hash=source_registry.registry_hash,
        claim_ids=tuple(sorted(seen_claims)),
        row_hashes=tuple(sorted(r.row_hash for r in rows)),
        child_record_hashes=tuple(sorted(rec.content_hash for rec in attr_records)),
        demoted_record_hashes=tuple(sorted(rec.content_hash for rec in demoted_records)),
        final_registry_hash=final_registry.registry_hash)
    return bundle, rows, final_registry


def verify_bundle_registry(bundle: AttributeBundle, registry) -> None:
    """下游消费点强制:**真密封注册表**(re-review#3 B2:duck-typed 冒牌对象在此拒,
    经 require_sealed_registry 重验封印)且必须恰一匹配束封的 final_registry_hash
    (M1:两个束/改过的注册表无法都成为同一决策的权威)。"""
    if not isinstance(bundle, AttributeBundle):
        raise RegistryError("bundle 必须是密封 AttributeBundle")
    registry = require_sealed_registry(registry)
    if registry.registry_hash != bundle.final_registry_hash:
        raise RegistryError(
            f"注册表 {registry.registry_hash[:12]} 与束封最终注册表 "
            f"{bundle.final_registry_hash[:12]} 不符——拒绝消费(M1)")


# --------------------------------------------------- B1′ 存量 ID 语义分类

_LEGACY_ATTENTION_RE = re.compile(r"(N00|NDA\d+|NIA\d+)")


def is_legacy_attention_id(record_id: str) -> bool:
    """B1′:existing N00(全景计数)/NDA*(直接聚合)/NIA*(间接聚合)为语义
    attention_only——增量信息只是计数/广度/聚合。ND##/NI##(原子明细)/NX01
    (缺席声明)不是。物理移出在席位接线块;本判定是其唯一语义依据。
    re-review#3 M2:fullmatch(尾随换行不再算合法身份)。"""
    return bool(_LEGACY_ATTENTION_RE.fullmatch(str(record_id)))
