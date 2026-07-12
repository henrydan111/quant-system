# SCRIPT_STATUS: ACTIVE — 新闻快讯:别名注册表 + 三路路由 + scoring_owner(NF wave §7 step 3-routing/4)
"""Deterministic entity-linking, 3-way routing, and per-target scoring ownership.

设计 v1.12:
- **别名注册表(M4)**:受治理的版本化 PIT 注册表,把被提及工具(A股6位码/H股/ADR/
  精确股名)映射到 A股 ts_code;**歧义 fail-closed(不链接)**,注册表版本+内容哈希封存;
  卡片保留「提及 00981.HK,映射至 688981.SH」而非改写 H 股行情。
- **三路路由(§2.5)**:个股(经别名注册表)/ 行业·概念(申万+THS 词表)/ 宏观;
  真垃圾(黑嘴/无信息)已在确定性预过滤丢弃。**高精度优先**(M6 直接挂钩精度 ≥98%):
  只在精确匹配时链接,漏链→宏观/未路由,绝不误链。
- **scoring_owner(M3)**:`(claim_id, target_ts_code, cutoff)` —— subject_codes 显式点名
  → news;经批准系统性暴露触达的非 subject 同业 → macro;每 (claim,target) 恰一席可
  计分,零或重复所有权硬失败。
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from types import MappingProxyType

import pandas as pd

# A股6位码(带交易所后缀或裸码)、H股5位.HK、精确股名
_A_CODE_RE = re.compile(r"(?<!\d)([03456789]\d{5})(?:\.(?:SH|SZ|BJ))?(?!\d)")
_HK_CODE_RE = re.compile(r"(?<!\d)(\d{5})\.HK(?!\d)")
#: 股名子串链接最小长度(高精度优先,M6 ≥98%):中文无词边界,2-3 字名子串误链风险高
#: (「中国」「国泰」类),故名链接仅限 ≥4 字;更短名只经 A股码/H股码链接。
_MIN_NAME_LINK_LEN = 4


class AmbiguousAliasError(Exception):
    """歧义别名(同 token 映射多个 A 股)—— fail-closed,不链接。"""


@dataclass(frozen=True)
class AliasRegistry:
    """受治理别名注册表(M4/review B3)。version + content_hash 封存;进 C16b 指纹与
    链 manifest。**深只读**(exact/universe 经 MappingProxyType,frozen 挡不住改内部
    dict——chain_v2.5 _deep_ro 同一教训);`valid_from/valid_to` 由 resolve 的 cutoff
    强制;裸 A 码须命中 PIT 工具宇宙才链接(空注册表不再凭空造 612345.SH)。"""
    version: str
    content_hash: str
    exact: object          # 只读 Mapping {token: ts_code}(含 ≥4 字股名/H 股/ADR 种子)
    ambiguous: frozenset
    a_universe: frozenset  # PIT 有效 A 股 ts_code 全集(裸码校验;空集=不链接裸码)
    valid_from: str
    valid_to: str | None = None

    def _effective(self, cutoff) -> bool:
        c = pd.Timestamp(cutoff)
        if c < pd.Timestamp(self.valid_from):
            return False
        return self.valid_to is None or c <= pd.Timestamp(self.valid_to)

    def resolve_codes(self, text: str, cutoff) -> tuple[list[str], list[dict]]:
        """从文本解析被提及 A 股 ts_code,as-of cutoff(review B3:无 cutoff 不解析)。
        注册表在 cutoff 无效 → 空结果。返回 (ts_codes, mention_records)。"""
        if not self._effective(cutoff):
            return [], [{"mentioned": None, "mapped": None,
                         "alias_type": "registry_not_effective"}]
        codes: list[str] = []
        mentions: list[dict] = []
        s = str(text)
        # 1) 裸 A 股 6 位码——须命中 PIT 工具宇宙(空注册表不再造码,review B3)
        for m in _A_CODE_RE.finditer(s):
            tc = self.exact.get(m.group(1)) or self._a_suffix(m.group(1))
            if tc and tc in self.a_universe:
                codes.append(tc)
                mentions.append({"mentioned": m.group(0), "mapped": tc, "alias_type": "a_code"})
            else:
                mentions.append({"mentioned": m.group(0), "mapped": None,
                                 "alias_type": "a_code_not_in_universe"})
        # 2) H 股码经注册表
        for m in _HK_CODE_RE.finditer(s):
            tok = m.group(0)
            if tok in self.ambiguous:
                mentions.append({"mentioned": tok, "mapped": None, "alias_type": "hk_ambiguous"})
                continue
            tc = self.exact.get(tok)
            if tc:
                codes.append(tc)
                mentions.append({"mentioned": tok, "mapped": tc, "alias_type": "hk_code"})
        # 3) 精选 ADR/其他 ASCII 别名(种子内显式列出的才解析,review B3)
        for tok, tc in self.exact.items():
            if not (isinstance(tok, str) and tok.isascii() and not tok[0].isdigit()):
                continue                # 只处理非码 ASCII 别名(如 BABA)
            if tok in self.ambiguous:
                continue
            if re.search(r"(?<![A-Za-z])" + re.escape(tok) + r"(?![A-Za-z])", s):
                codes.append(tc)
                mentions.append({"mentioned": tok, "mapped": tc, "alias_type": "adr"})
        # 4) 唯一股名子串(仅 ≥4 字中文名;短名只经码链接——高精度优先)
        for name, tc in self.exact.items():
            if not isinstance(name, str) or name.isascii() or len(name) < _MIN_NAME_LINK_LEN:
                continue
            if name in self.ambiguous:
                continue
            if name in s:
                codes.append(tc)
                mentions.append({"mentioned": name, "mapped": tc, "alias_type": "name"})
        seen, uniq = set(), []
        for c in codes:
            if c not in seen:
                seen.add(c)
                uniq.append(c)
        return uniq, mentions

    @staticmethod
    def _a_suffix(code6: str) -> str | None:
        if code6[0] == "6":
            return f"{code6}.SH"
        if code6[0] in "03":
            return f"{code6}.SZ"
        if code6[0] in "48" or code6[:3] in ("920",):   # BSE 920xxx (review B3)
            return f"{code6}.BJ"
        return None


def build_alias_registry(stock_basic: pd.DataFrame, *, version: str,
                         valid_from: str, valid_to: str | None = None,
                         hk_seed: dict | None = None,
                         adr_seed: dict | None = None) -> AliasRegistry:
    """从 stock_basic(name→ts_code)+ 精选 H 股/ADR 种子构造别名注册表。
    **重名 → 歧义不入 exact**(fail-closed);a_universe = stock_basic 全部 ts_code
    (裸码校验);exact 深只读;content_hash 覆盖完整规范载荷(含 valid_to,行序无关)。"""
    exact: dict = {}
    name_counts: dict = {}
    a_universe: set = set()
    for _, r in stock_basic.iterrows():
        nm, tc = str(r["name"]).strip(), str(r["ts_code"]).strip()
        if not tc:
            continue
        a_universe.add(tc)
        if not nm:
            continue
        name_counts[nm] = name_counts.get(nm, 0) + 1
        exact.setdefault(nm, tc)
    ambiguous = {nm for nm, n in name_counts.items() if n > 1}
    for nm in ambiguous:
        exact.pop(nm, None)
    for tok, tc in (hk_seed or {}).items():
        exact[tok] = tc
    for tok, tc in (adr_seed or {}).items():
        exact[tok] = tc
    payload = json.dumps({"exact": exact, "ambiguous": sorted(ambiguous),
                          "a_universe": sorted(a_universe), "version": version,
                          "valid_from": valid_from, "valid_to": valid_to},
                         sort_keys=True, ensure_ascii=False)
    ch = hashlib.sha256(payload.encode()).hexdigest()[:16]
    return AliasRegistry(version=version, content_hash=ch,
                         exact=MappingProxyType(dict(exact)),
                         ambiguous=frozenset(ambiguous),
                         a_universe=frozenset(a_universe),
                         valid_from=valid_from, valid_to=valid_to)


# --------------------------------------------------- 三路路由(§2.5,确定性)

def route_cluster(content: str, registry: AliasRegistry, cutoff,
                  industry_terms: frozenset, concept_terms: frozenset
                  ) -> dict:
    """三路路由(高精度优先,review B3:as-of cutoff + 不丢行业/概念部分)。返回
    {primary_route, subject_codes, mentions, industry_tags, concept_tags}。
    `primary_route` ∈ {stock, industry_concept, macro} 决定主卡归属,但**行业/概念
    标签始终一并返回**(一条既点名个股又提行业的快讯,其行业部分不再被丢弃——
    下游 fact 级 scoring_owner 决定各 claim 归属)。"""
    codes, mentions = registry.resolve_codes(content, cutoff)
    s = str(content)
    ind = sorted({t for t in industry_terms if t in s})
    con = sorted({t for t in concept_terms if t in s})
    if codes:
        primary = "stock"
    elif ind or con:
        primary = "industry_concept"
    else:
        primary = "macro"
    return {"primary_route": primary, "subject_codes": codes, "mentions": mentions,
            "industry_tags": ind, "concept_tags": con}


# --------------------------------------------------- scoring_owner(M3)

class ScoringOwnershipError(Exception):
    """零或重复计分所有权(M3 硬失败)。"""


@dataclass(frozen=True)
class SystemicExposureSnapshot:
    """密封的、按 cutoff 有效的系统性暴露工件(review B3:scoring_owner 不再收任意集合)。
    mapping_id/version/content_hash + 有效区间 + {target_ts_code} 集合。"""
    mapping_id: str
    version: str
    content_hash: str
    valid_from: str
    valid_to: str | None
    targets: frozenset

    def effective(self, cutoff) -> bool:
        c = pd.Timestamp(cutoff)
        return (c >= pd.Timestamp(self.valid_from)
                and (self.valid_to is None or c <= pd.Timestamp(self.valid_to)))


def scoring_owner(claim_id: str, target_ts_code: str, cutoff, *,
                  subject_codes: list[str],
                  systemic_exposure: SystemicExposureSnapshot) -> str:
    """(claim_id, target_ts_code, cutoff) 的唯一计分席(M3/review B3)。target 在
    subject_codes 显式点名 → news;经**密封且 cutoff 有效**的系统性暴露触达的非 subject
    同业 → macro;否则非计分 context。exposure 在 cutoff 无效 → 只认 subject。
    subject ∧ systemic = 配置矛盾硬失败(不静默择一,掩盖所有权错误)。"""
    if not isinstance(systemic_exposure, SystemicExposureSnapshot):
        raise ScoringOwnershipError("systemic_exposure 必须是密封 SystemicExposureSnapshot")
    is_subject = target_ts_code in set(subject_codes)
    in_systemic = (systemic_exposure.effective(cutoff)
                   and target_ts_code in systemic_exposure.targets)
    if is_subject and in_systemic:
        raise ScoringOwnershipError(
            f"claim {claim_id} target {target_ts_code}: 同时 subject 与 systemic peer")
    if is_subject:
        return "news"
    if in_systemic:
        return "macro"
    return "context"
