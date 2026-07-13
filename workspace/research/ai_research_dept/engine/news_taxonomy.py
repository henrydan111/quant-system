# SCRIPT_STATUS: ACTIVE — 新闻快讯:M-line 记录工厂 + MF 维度派生(NF §7 step 6 注册表数据)
"""M-line record factories + MF macro_type derivation (M1⁴/M1‴ authoritative tables).

**权威表本体在 kernel**([news_evidence.py](news_evidence.py) `M_LINE_TAXONOMY`,
re-review Major-3):工厂级保留 ID 锁使 M01-M16 只能以逐字一致的元数据铸出——本模块
只是其记录工厂 + 政策/MF 命名空间工厂。规范要点(§6b round-10 M1‴ + round-11 M1⁴):
- M03/M09/M15=market_breadth_state;M04/M10=market_limit_state;
  M14=market_leadership_state;其余=market_state_fact;M16 聚合=∅ 维,context_only
  永不正向;policy_alignment 只由原子政策行接地;external_shock_transmission 只由
  注册 macro_type=external_shock 的正向 MF 记录接地。
- 全部 M 行 `allowed_consumers={macro}`;fund/news 席不收;technical 须单独契约。
- **命名空间**(re-review Major-3):政策行 `MP\\d{2,}`;宏观快讯 `MF[A-Z]?\\d{2,}`;
  两工厂拒绝保留 M01-M16 与越界 ID。

**MF 派生表 v1 + 分型优先级**(re-review Major-5,与 news_ingest 宏观分型 prompt 的
优先级指令配套——两处必须一致):
- **离散外部冲击优先**:外盘利率决议/商品剧变/汇率急变/地缘突发等**离散外部冲击**
  必须归 `external_shock`(优先于 地缘外围/商品汇率/货币政策)——它是
  external_shock_transmission 的唯一入口;
- **国内**货币/财政/监管动作 → 各政策类 → policy_alignment(原子政策行的快讯形态);
- **非冲击性**外围情绪/常规商品汇率波动 → 地缘外围/商品汇率 → risk_appetite
  (**不是** external_shock 维——M1⁴ 保留);大盘资金面 → liquidity;行业景气 →
  industry_concept。
经济归属为本实现的注册判断(设计只规定"注册的恰一维派生"),已过 §10 实现审
(re-review R3:overlap 需显式优先级——已钉此处 + 分型 prompt)。
"""
from __future__ import annotations

import re

from workspace.research.ai_research_dept.engine.news_evidence import (
    M_LINE_TAXONOMY, CardRecord, RegistryError, build_card_record,
)

__all__ = ["M_LINE_TAXONOMY", "MACRO_TYPE_DIMENSION", "MACRO_TYPE_DERIVATION_VERSION",
           "build_m_line_records", "build_mf_record", "build_policy_row_record"]

#: MF macro_type → 恰一正向维(注册派生表 v1;优先级契约见模块 docstring)
MACRO_TYPE_DIMENSION: dict[str, str] = {
    "货币政策": "policy_alignment",
    "财政政策": "policy_alignment",
    "监管全局": "policy_alignment",
    "地缘外围": "risk_appetite_environment_fit",     # 非冲击外围情绪;冲击→external_shock
    "大盘资金面": "liquidity_flows_transmission",
    "商品汇率": "risk_appetite_environment_fit",     # 常规波动;离散冲击→external_shock
    "行业景气": "industry_concept_transmission",
    "external_shock": "external_shock_transmission",  # 该维的唯一接地入口(M1⁴)
}
MACRO_TYPE_DERIVATION_VERSION = "mf_dim_v1"

#: 命名空间(re-review Major-3):政策行/宏观快讯各自专属,绝不触碰保留 M01-M16
_POLICY_ID_RE = re.compile(r"^MP\d{2,}$")
_MF_ID_RE = re.compile(r"^MF[A-Z]?\d{2,}$")


def build_m_line_records() -> list[CardRecord]:
    """构造全部 16 条 M 行封印记录(macro 席专属)。元数据与权威表逐字一致——
    kernel 的工厂级保留锁对任何偏离直接拒(Major-3)。"""
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
    """注册原子政策行(M1⁴:policy_alignment 的唯一 M 域接地来源——M16 聚合不作数)。
    命名空间 `MP\\d{2,}`;保留 M-line ID 拒(Major-3)。"""
    if not _POLICY_ID_RE.match(record_id):
        raise RegistryError(
            f"政策行 ID {record_id!r} 越界——须匹配 MP\\d{{2,}}(保留 M01-M16 不可借用)")
    return build_card_record(record_id, domain="macro",
                             evidence_class="market_state_fact",
                             allowed_uses={"factor_positive", "context_only"},
                             allowed_consumers={"macro"},
                             allowed_dimensions={"policy_alignment"})


def build_mf_record(record_id: str, evidence_class: str, *,
                    macro_type: "str | None" = None) -> CardRecord:
    """构造宏观快讯记录(§6 宏观快讯节)。命名空间 `MF[A-Z]?\\d{2,}`(Major-3)。
    - MFR:仅 penalty/bear,无正向维(M1⁴);
    - MFD/MFI/MFA + 注册 macro_type:正向,维 = 派生表的**恰一**维;
    - MFD/MFI/MFA + macro_type 缺失/未注册:context_only(M4:绝不落真维度)。"""
    if not _MF_ID_RE.match(record_id):
        raise RegistryError(
            f"MF 记录 ID {record_id!r} 越界——须匹配 MF[A-Z]?\\d{{2,}}(保留 M01-M16 不可借用)")
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
