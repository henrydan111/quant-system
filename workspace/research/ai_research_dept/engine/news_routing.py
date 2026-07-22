# SCRIPT_STATUS: ACTIVE — 新闻快讯:别名注册表 + 三路路由 + scoring_owner(NF wave §7;全面密封)
"""Deterministic entity-linking, 3-way routing, per-target ownership — sealed (review B3).

实现审 FIX-FIRST 全面密封束:
- **AliasRegistry / SystemicExposureSnapshot / AtomicClaim 均为封印对象**:只能经工厂构造,
  content_hash = 全 SHA-256 over 深只读规范载荷;直接构造伪造(真载荷+任意哈希 / 篡改
  载荷留旧哈希 / 改内部 dict)由 `__post_init__` 的 verify-not-trust 识破。
- **PIT 上市边界**:别名工厂按 `list_date ≤ cutoff < delist_date` 收录(未上市/已退市股票
  在该 cutoff 不解析);裸码显式后缀被尊重(`000001.SH` 不再被解析成 `.SZ`);种子 target
  必须在 A 股宇宙内。
- **原子 claim**:混合直接/系统性文本拆 AtomicClaim(claim_id + fact_cluster_id + 不可变
  subject_codes + 路由证据 + 注册表哈希);scoring_owner 消费封印 claim + 封印 exposure。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

from workspace.research.ai_research_dept.engine.news_seal import (
    SealError, deep_ro, seal_hash, verify_sealed,
)

_A_CODE_RE = re.compile(r"(?<!\d)([03456789]\d{5})(?:\.(SH|SZ|BJ))?(?!\d)")
_HK_CODE_RE = re.compile(r"(?<!\d)(\d{5})\.HK(?!\d)")
_MIN_NAME_LINK_LEN = 4


class AmbiguousAliasError(Exception):
    """歧义别名 —— fail-closed。"""


class ScoringOwnershipError(Exception):
    """零或重复计分所有权(M3 硬失败)。"""


# --------------------------------------------------- 别名注册表(封印,review B3)

@dataclass(frozen=True)
class AliasRegistry:
    """封印别名注册表。**只能经 build_alias_registry 构造**;__post_init__ 重算并校验
    content_hash(伪造识破);exact/a_universe 深只读。resolve as-of cutoff。"""
    version: str
    content_hash: str
    exact: object          # 深只读 {token: ts_code}
    ambiguous: frozenset
    a_universe: frozenset
    valid_from: str
    valid_to: str | None = None

    def __post_init__(self):
        verify_sealed(self._payload(), self.content_hash, field_name="alias content_hash")

    def _payload(self) -> dict:
        return {"version": self.version, "exact": dict(self.exact),
                "ambiguous": sorted(self.ambiguous), "a_universe": sorted(self.a_universe),
                "valid_from": self.valid_from, "valid_to": self.valid_to}

    def _effective(self, cutoff) -> bool:
        c = pd.Timestamp(cutoff)
        return (c >= pd.Timestamp(self.valid_from)
                and (self.valid_to is None or c <= pd.Timestamp(self.valid_to)))

    def resolve_codes(self, text: str, cutoff) -> tuple[list[str], list[dict]]:
        """as-of cutoff 解析被提及 A 股 ts_code。返回 (codes, mentions)。"""
        if not self._effective(cutoff):
            return [], [{"mentioned": None, "mapped": None,
                         "alias_type": "registry_not_effective"}]
        codes, mentions = [], []
        s = str(text)
        # 1) 裸 A 码——**尊重显式后缀**(review B3),须命中 PIT 宇宙
        for m in _A_CODE_RE.finditer(s):
            code6, suffix = m.group(1), m.group(2)
            tc = f"{code6}.{suffix}" if suffix else (
                self.exact.get(code6) or self._a_suffix(code6))
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
        # review B4: iterate the alias map in a CANONICAL (sorted) order so two
        # registries with the same sealed hash (built from row-permuted inputs)
        # resolve mentions in an identical order — the sealed identity must fully
        # determine the output, not the dict's insertion order.
        exact_sorted = sorted(self.exact.items())
        # 3) ADR/ASCII 别名(种子内显式的)
        for tok, tc in exact_sorted:
            if not (isinstance(tok, str) and tok.isascii() and not tok[0].isdigit()):
                continue
            if tok in self.ambiguous:
                continue
            if re.search(r"(?<![A-Za-z])" + re.escape(tok) + r"(?![A-Za-z])", s):
                codes.append(tc)
                mentions.append({"mentioned": tok, "mapped": tc, "alias_type": "adr"})
        # 4) ≥4 字唯一中文名
        for name, tc in exact_sorted:
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
        if code6[0] in "48" or code6[:3] == "920":
            return f"{code6}.BJ"
        return None


def build_alias_registry(stock_basic: pd.DataFrame, *, version: str,
                         valid_from: str, valid_to: str | None = None,
                         cutoff=None, hk_seed: dict | None = None,
                         adr_seed: dict | None = None,
                         as_of_names: "dict | None" = None) -> AliasRegistry:
    """封印别名注册表工厂。**PIT 上市边界**(review B3):给定 cutoff 时仅收录
    `list_date ≤ cutoff` 且(delist_date 空 或 cutoff < delist_date)的股票——未上市/
    已退市股票在该 cutoff 不解析。重名 → 歧义不入 exact。H/ADR 种子 target 须在 a_universe。
    content_hash = 全 SHA-256(行序无关)。

    GPT-P2 P0 (fail-closed omit):
    - `as_of_names`(可选 {ts_code: 截至 cutoff 的 PIT 名称})——**PIT 名称别名**。给定时,
      名称别名取该映射而非当前 `stock_basic.name`。**映射里没有的上市股 → 省略其名称别名**
      (仍留在 a_universe,数字 A/H 代码照常解析),而不是回退当前名(回退会重开未来名
      泄漏)。哪些股有干净、ann_date 锚定、唯一的 as-of 名由调用方(PIT 感知的 P2)判定。
    - **日期 fail-closed**:给定 cutoff 时,list_date/delist_date **列都必须存在**;list_date
      须可解析;delist_date 单元格若非空须可解析(空=未退市)——无法 PIT 判定一律拒。"""
    cut = pd.Timestamp(cutoff) if cutoff is not None else None
    exact, name_counts, a_universe = {}, {}, set()
    for _, r in stock_basic.iterrows():
        tc = str(r["ts_code"]).strip()
        if not tc:
            continue
        if cut is not None:
            if "list_date" not in r.index or "delist_date" not in r.index:
                raise ValueError(f"{tc}: cutoff 模式须存在 list_date+delist_date 列"
                                 f"(空单元格=未退市)——拒(fail-closed)")
            ld_raw = r.get("list_date")
            ld = pd.to_datetime(str(ld_raw), errors="coerce") \
                if not (ld_raw is None or pd.isna(ld_raw)) else pd.NaT
            if pd.isna(ld):
                raise ValueError(
                    f"{tc}: list_date {ld_raw!r} 缺失/不可解析——无法 PIT 判定上市,拒(fail-closed)")
            if ld > cut:
                continue                          # 未上市
            dd_raw = r.get("delist_date")
            if dd_raw is not None and not pd.isna(dd_raw) and str(dd_raw).strip():
                dd = pd.to_datetime(str(dd_raw), errors="coerce")
                if pd.isna(dd):
                    raise ValueError(
                        f"{tc}: delist_date {dd_raw!r} 非空却不可解析——拒(fail-closed)")
                if cut >= dd:
                    continue                      # 已退市
        a_universe.add(tc)
        if as_of_names is not None:
            nm = as_of_names.get(tc)              # 缺 → 省略名称(fail-closed omit)
            nm = str(nm).strip() if nm is not None else ""
        else:
            nm = str(r["name"]).strip()
        if nm:
            name_counts[nm] = name_counts.get(nm, 0) + 1
            exact.setdefault(nm, tc)
    ambiguous = {nm for nm, n in name_counts.items() if n > 1}
    for nm in ambiguous:
        exact.pop(nm, None)
    for seed, label in ((hk_seed, "hk_seed"), (adr_seed, "adr_seed")):
        for tok, tc in (seed or {}).items():
            if tc not in a_universe:
                raise ValueError(f"{label} target {tc} 不在 A 股宇宙(review B3)")
            exact[tok] = tc
    payload = {"version": version, "exact": exact, "ambiguous": sorted(ambiguous),
               "a_universe": sorted(a_universe), "valid_from": valid_from,
               "valid_to": valid_to}
    return AliasRegistry(version=version, content_hash=seal_hash(payload),
                         exact=deep_ro(dict(exact)), ambiguous=frozenset(ambiguous),
                         a_universe=frozenset(a_universe), valid_from=valid_from,
                         valid_to=valid_to)


# --------------------------------------------------- 三路路由(as-of,多路)

def route_cluster(content: str, registry: AliasRegistry, cutoff,
                  industry_terms: frozenset, concept_terms: frozenset) -> dict:
    """三路路由(as-of cutoff,行业/概念部分不丢)。返回 {primary_route, subject_codes,
    mentions, industry_tags, concept_tags}。"""
    codes, mentions = registry.resolve_codes(content, cutoff)
    s = str(content)
    ind = sorted({t for t in industry_terms if t in s})
    con = sorted({t for t in concept_terms if t in s})
    primary = "stock" if codes else ("industry_concept" if (ind or con) else "macro")
    return {"primary_route": primary, "subject_codes": codes, "mentions": mentions,
            "industry_tags": ind, "concept_tags": con}


# --------------------------------------------------- 原子 claim(封印,review B3)

@dataclass(frozen=True)
class AtomicClaim:
    """封印原子 claim:claim_id + fact_cluster_id + 不可变 subject_codes + 路由证据 +
    注册表哈希。scoring_owner 只消费封印 claim(不再收裸字符串/列表)。"""
    claim_id: str
    fact_cluster_id: str
    subject_codes: tuple
    industry_tags: tuple
    concept_tags: tuple
    alias_registry_hash: str
    content_hash: str = field(default="")

    def __post_init__(self):
        payload = self._payload()
        h = seal_hash(payload)
        if self.content_hash and self.content_hash != h:
            raise SealError(f"AtomicClaim 伪造:{self.content_hash[:12]} ≠ {h[:12]}")
        if not self.content_hash:
            object.__setattr__(self, "content_hash", h)

    def _payload(self) -> dict:
        return {"claim_id": self.claim_id, "fact_cluster_id": self.fact_cluster_id,
                "subject_codes": list(self.subject_codes),
                "industry_tags": list(self.industry_tags),
                "concept_tags": list(self.concept_tags),
                "alias_registry_hash": self.alias_registry_hash}


def build_atomic_claim(claim_id: str, fact_cluster_id: str, route: dict,
                       alias_registry_hash: str) -> AtomicClaim:
    return AtomicClaim(
        claim_id=claim_id, fact_cluster_id=fact_cluster_id,
        subject_codes=tuple(route.get("subject_codes", [])),
        industry_tags=tuple(route.get("industry_tags", [])),
        concept_tags=tuple(route.get("concept_tags", [])),
        alias_registry_hash=alias_registry_hash)


# --------------------------------------------------- 系统性暴露 + scoring_owner(封印)

@dataclass(frozen=True)
class SystemicExposureSnapshot:
    """封印系统性暴露工件。经工厂构造;content_hash 绑 mapping 属性 + 有效区间 + 不可变
    targets;__post_init__ verify-not-trust(改 targets 留旧哈希被识破)。"""
    mapping_id: str
    version: str
    content_hash: str
    valid_from: str
    valid_to: str | None
    targets: frozenset

    def __post_init__(self):
        verify_sealed(self._payload(), self.content_hash, field_name="exposure content_hash")

    def _payload(self) -> dict:
        return {"mapping_id": self.mapping_id, "version": self.version,
                "valid_from": self.valid_from, "valid_to": self.valid_to,
                "targets": sorted(self.targets)}

    def effective(self, cutoff) -> bool:
        c = pd.Timestamp(cutoff)
        return (c >= pd.Timestamp(self.valid_from)
                and (self.valid_to is None or c <= pd.Timestamp(self.valid_to)))


def build_systemic_exposure(mapping_id: str, version: str, valid_from: str,
                            targets, valid_to: str | None = None
                            ) -> SystemicExposureSnapshot:
    payload = {"mapping_id": mapping_id, "version": version, "valid_from": valid_from,
               "valid_to": valid_to, "targets": sorted(set(targets))}
    return SystemicExposureSnapshot(
        mapping_id=mapping_id, version=version, content_hash=seal_hash(payload),
        valid_from=valid_from, valid_to=valid_to, targets=frozenset(targets))


def scoring_owner(claim: AtomicClaim, target_ts_code: str, cutoff, *,
                  systemic_exposure: SystemicExposureSnapshot) -> str:
    """(claim, target, cutoff) 的唯一计分席(M3/review B3)。消费**封印** claim + exposure。
    target 在 claim.subject_codes → news;cutoff-有效 exposure 触达的非 subject 同业 →
    macro;否则 context。subject ∧ systemic = 硬失败。"""
    if not isinstance(claim, AtomicClaim):
        raise ScoringOwnershipError("claim 必须是封印 AtomicClaim")
    if not isinstance(systemic_exposure, SystemicExposureSnapshot):
        raise ScoringOwnershipError("systemic_exposure 必须是封印 SystemicExposureSnapshot")
    is_subject = target_ts_code in set(claim.subject_codes)
    in_systemic = (systemic_exposure.effective(cutoff)
                   and target_ts_code in systemic_exposure.targets)
    if is_subject and in_systemic:
        raise ScoringOwnershipError(
            f"claim {claim.claim_id} target {target_ts_code}: 同时 subject 与 systemic peer")
    if is_subject:
        return "news"
    if in_systemic:
        return "macro"
    return "context"
