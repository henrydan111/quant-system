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
from dataclasses import dataclass

import pandas as pd

# A股6位码(带交易所后缀或裸码)、H股5位.HK、精确股名
_A_CODE_RE = re.compile(r"(?<!\d)([03456789]\d{5})(?:\.(?:SH|SZ|BJ))?(?!\d)")
_HK_CODE_RE = re.compile(r"(?<!\d)(\d{5})\.HK(?!\d)")


class AmbiguousAliasError(Exception):
    """歧义别名(同 token 映射多个 A 股)—— fail-closed,不链接。"""


@dataclass(frozen=True)
class AliasRegistry:
    """受治理别名注册表(M4)。version + content_hash 封存;进 C16b 指纹与链 manifest。"""
    version: str
    content_hash: str
    #: 精确 token → A股 ts_code(仅**唯一**映射入表;歧义 token 入 _ambiguous 不链接)
    exact: dict          # {token: ts_code}
    ambiguous: frozenset  # 已知歧义 token 集(显式 fail-closed,不猜)
    valid_from: str
    valid_to: str | None = None

    def resolve_codes(self, text: str) -> tuple[list[str], list[dict]]:
        """从文本解析被提及 A 股 ts_code。返回 (ts_codes, mention_records)。
        mention_records 每条 {mentioned, mapped, alias_type} —— 卡片保留原提及。
        6位A股码直接识别;H股/ADR/股名经注册表;歧义 token 不链接(记 ambiguity)。"""
        codes: list[str] = []
        mentions: list[dict] = []
        s = str(text)
        # 1) 裸 A 股 6 位码(直接,无需注册表)
        for m in _A_CODE_RE.finditer(s):
            code6 = m.group(1)
            tc = self.exact.get(code6) or self._a_suffix(code6)
            if tc:
                codes.append(tc)
                mentions.append({"mentioned": m.group(0), "mapped": tc,
                                 "alias_type": "a_code"})
        # 2) H 股码经注册表
        for m in _HK_CODE_RE.finditer(s):
            tok = m.group(0)
            if tok in self.ambiguous:
                mentions.append({"mentioned": tok, "mapped": None,
                                 "alias_type": "hk_ambiguous"})
                continue
            tc = self.exact.get(tok)
            if tc:
                codes.append(tc)
                mentions.append({"mentioned": tok, "mapped": tc, "alias_type": "hk_code"})
        # 3) 精确股名(仅唯一名;子串不匹配以防误链——高精度优先)
        for name, tc in self.exact.items():
            if name.isascii():          # 名字都是中文;跳过码类 token
                continue
            if name in self.ambiguous:
                continue
            if name in s:
                codes.append(tc)
                mentions.append({"mentioned": name, "mapped": tc, "alias_type": "name"})
        # 去重保序
        seen, uniq = set(), []
        for c in codes:
            if c not in seen:
                seen.add(c)
                uniq.append(c)
        return uniq, mentions

    @staticmethod
    def _a_suffix(code6: str) -> str | None:
        """裸 6 位码 → 加交易所后缀(6→SH,0/3→SZ,4/8→BJ)。仅确定性前缀规则。"""
        if code6[0] in "6":
            return f"{code6}.SH"
        if code6[0] in "03":
            return f"{code6}.SZ"
        if code6[0] in "48":
            return f"{code6}.BJ"
        return None


def build_alias_registry(stock_basic: pd.DataFrame, *, version: str,
                         valid_from: str,
                         hk_seed: dict | None = None) -> AliasRegistry:
    """从 stock_basic(name→ts_code)+ 精选 H 股种子构造别名注册表。
    **重名(同 name 多 ts_code)→ 歧义,不入 exact**(fail-closed)。"""
    exact: dict = {}
    name_counts: dict = {}
    for _, r in stock_basic.iterrows():
        nm, tc = str(r["name"]).strip(), str(r["ts_code"]).strip()
        if not nm or not tc:
            continue
        name_counts[nm] = name_counts.get(nm, 0) + 1
        exact.setdefault(nm, tc)
    ambiguous = {nm for nm, n in name_counts.items() if n > 1}
    for nm in ambiguous:
        exact.pop(nm, None)               # 重名不链接
    for tok, tc in (hk_seed or {}).items():
        exact[tok] = tc                   # H 股种子(精选、唯一)
    payload = json.dumps({"exact": exact, "ambiguous": sorted(ambiguous),
                          "version": version, "valid_from": valid_from},
                         sort_keys=True, ensure_ascii=False)
    ch = hashlib.sha256(payload.encode()).hexdigest()[:16]
    return AliasRegistry(version=version, content_hash=ch, exact=exact,
                         ambiguous=frozenset(ambiguous), valid_from=valid_from)


# --------------------------------------------------- 三路路由(§2.5,确定性)

def route_cluster(content: str, registry: AliasRegistry,
                  industry_terms: frozenset, concept_terms: frozenset
                  ) -> dict:
    """三路路由(高精度优先)。返回
    {route, subject_codes, mentions, industry_tags, concept_tags}。
    route ∈ {stock, industry_concept, macro}。个股优先;否则命中行业/概念词→
    industry_concept;否则 macro。真垃圾已在 prefilter 丢弃。"""
    codes, mentions = registry.resolve_codes(content)
    if codes:
        return {"route": "stock", "subject_codes": codes, "mentions": mentions,
                "industry_tags": [], "concept_tags": []}
    s = str(content)
    ind = sorted({t for t in industry_terms if t in s})
    con = sorted({t for t in concept_terms if t in s})
    if ind or con:
        return {"route": "industry_concept", "subject_codes": [], "mentions": mentions,
                "industry_tags": ind, "concept_tags": con}
    return {"route": "macro", "subject_codes": [], "mentions": mentions,
            "industry_tags": [], "concept_tags": []}


# --------------------------------------------------- scoring_owner(M3)

class ScoringOwnershipError(Exception):
    """零或重复计分所有权(M3 硬失败)。"""


def scoring_owner(claim_id: str, target_ts_code: str, *,
                  subject_codes: list[str],
                  systemic_exposure_targets: set) -> str:
    """(claim, target, cutoff) 的唯一计分席(M3)。target 在 subject_codes 显式点名
    → news;经批准系统性暴露触达的非 subject 同业 → macro;否则该 (claim,target)
    非计分上下文。返回 'news' | 'macro' | 'context'。"""
    is_subject = target_ts_code in set(subject_codes)
    in_systemic = target_ts_code in set(systemic_exposure_targets)
    # 同一 claim 下 target 既被显式点名(subject)又经系统性暴露触达 = 配置矛盾,
    # 硬失败(不静默择一——那会掩盖所有权错误,M3)
    if is_subject and in_systemic:
        raise ScoringOwnershipError(
            f"claim {claim_id} target {target_ts_code}: 同时 subject 与 systemic peer")
    if is_subject:
        return "news"
    if in_systemic:
        return "macro"
    return "context"
