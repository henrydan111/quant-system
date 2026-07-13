# SCRIPT_STATUS: ACTIVE — 新闻快讯:M01-M16 冻结 taxonomy + MF 维度派生(NF §7 step 6 注册表数据)
"""M-line frozen taxonomy (M1⁴/M1‴ authoritative tables) + MF macro_type derivation.

设计 v1.12 的两张**规范表**逐字落码(§6b round-10 M1‴ + round-11 M1⁴):
- **证据类**(M1‴ line 337):交易所派生的价格/宽度/涨跌停/换手/波动/主线指标 =
  market_state_fact 系(**无论数学形态是计数/比率/百分位**——round-10 纠偏:数学形态
  不是 attention 判据);M03/M09/M15=market_breadth_state;M04/M10=market_limit_state;
  M14=market_leadership_state;其余=market_state_fact。
- **精确正向维集合**(M1⁴ line 390):M01-M15 各自的 `allowed_dimensions` 精确集;
  **M16 聚合 = ∅,context_only 永不正向**;policy_alignment **只由原子政策行接地**
  (M16 不作数);`external_shock_transmission` **只由注册 macro_type=external_shock 的
  正向 MF 记录接地**(M01/M02/M06-08/M12 不独立接地它)。
- **消费席**:全部 M 行 `allowed_consumers={macro}` —— fund/news 席**不**接收 M 行;
  technical 席消费 M 行须单独 technical 评分契约修订(M1‴ line 353),故不预授。
- **MF 派生**(M1⁴ line 398):MFD/MFI/MFA 正向记录的维 = 注册 `macro_type` 派生的
  **恰一**维度;`macro_type` 缺失/未注册 → context_only(M4:绝不落到真维度);
  MFR 无正向维,仅 penalty/bear。

⚠ `MACRO_TYPE_DIMENSION` 是**注册派生表 v1**(设计只规定"由注册 macro_type 派生恰一
维",未钉具体映射)——经济归属为本实现的判断,已列入 §10 实现审的显式审查点:
货币/财政/监管 → policy_alignment(原子政策行的快讯形态);地缘外围/商品汇率 →
risk_appetite(**非** external_shock 维——M1⁴ 明文只有 macro_type=external_shock 接地
该维);大盘资金面 → liquidity;行业景气 → industry_concept。
"""
from __future__ import annotations

from workspace.research.ai_research_dept.engine.news_evidence import (
    CardRecord, RegistryError, build_card_record,
)

#: M1⁴/M1‴ 权威表(冻结;record_id → (evidence_class, allowed_dimensions))
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

#: MF macro_type → 恰一正向维(注册派生表 v1;§10 审查点,见模块 docstring)
MACRO_TYPE_DIMENSION: dict[str, str] = {
    "货币政策": "policy_alignment",
    "财政政策": "policy_alignment",
    "监管全局": "policy_alignment",
    "地缘外围": "risk_appetite_environment_fit",     # 非 external_shock 维(M1⁴)
    "大盘资金面": "liquidity_flows_transmission",
    "商品汇率": "risk_appetite_environment_fit",     # 非 external_shock 维(M1⁴)
    "行业景气": "industry_concept_transmission",
    "external_shock": "external_shock_transmission",  # 该维的唯一接地入口
}
MACRO_TYPE_DERIVATION_VERSION = "mf_dim_v1"


def build_m_line_records() -> list[CardRecord]:
    """构造全部 16 条 M 行封印记录(macro 席专属)。M16 = context_only;
    其余 = factor_positive+context_only,维取权威表精确集。"""
    out = []
    for rid, (ec, dims) in sorted(M_LINE_TAXONOMY.items()):
        if dims:
            out.append(build_card_record(rid, domain="macro", evidence_class=ec,
                                         allowed_uses={"factor_positive", "context_only"},
                                         allowed_consumers={"macro"},
                                         allowed_dimensions=dims))
        else:                                    # M16 聚合:永不正向
            out.append(build_card_record(rid, domain="macro", evidence_class=ec,
                                         allowed_uses={"context_only"},
                                         allowed_consumers={"macro"}))
    return out


def build_policy_row_record(record_id: str) -> CardRecord:
    """注册原子政策行(M1⁴:policy_alignment 的唯一 M 域接地来源——M16 聚合不作数)。"""
    return build_card_record(record_id, domain="macro",
                             evidence_class="market_state_fact",
                             allowed_uses={"factor_positive", "context_only"},
                             allowed_consumers={"macro"},
                             allowed_dimensions={"policy_alignment"})


def build_mf_record(record_id: str, evidence_class: str, *,
                    macro_type: "str | None" = None) -> CardRecord:
    """构造宏观快讯记录(§6 宏观快讯节)。
    - MFR:仅 penalty/bear,无正向维(M1⁴);
    - MFD/MFI/MFA + 注册 macro_type:正向,维 = 派生表的**恰一**维;
    - MFD/MFI/MFA + macro_type 缺失/未注册:context_only(M4:绝不落真维度)。"""
    if evidence_class == "MFR":
        return build_card_record(record_id, domain="macro", evidence_class="MFR",
                                 allowed_uses={"penalty", "bear"},
                                 allowed_consumers={"macro", "bear"},
                                 allowed_dimensions={"manipulation_risk"})
    if evidence_class not in ("MFD", "MFI", "MFA"):
        raise RegistryError(f"MF 记录类须 ∈ {{MFD, MFI, MFA, MFR}}(得 {evidence_class!r})")
    dim = MACRO_TYPE_DIMENSION.get(macro_type) if macro_type is not None else None
    if dim is None:                               # 缺/未注册 macro_type → 不正向
        return build_card_record(record_id, domain="macro", evidence_class=evidence_class,
                                 allowed_uses={"context_only"},
                                 allowed_consumers={"macro"})
    return build_card_record(record_id, domain="macro", evidence_class=evidence_class,
                             allowed_uses={"factor_positive", "context_only"},
                             allowed_consumers={"macro"}, allowed_dimensions={dim})
