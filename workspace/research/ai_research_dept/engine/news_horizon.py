# SCRIPT_STATUS: ACTIVE — 新闻快讯:c16_news_horizon_v1 确定性契约核心(NF §7 链单元·子块1)
"""c16_news_horizon_v1 — the deterministic horizon-scorecard contract core.

设计 v1.12 §6b M2″(版本化 opt-in schema)+ M3‴(公式钉死)+ M2⁴(缺失/NO-SCORE
语义)+ 链单元 BINDING #4/#5 的**数学与校验核心**。默认 `c16_v1`
([scorecard.py](../../../../src/ai_layer/scorecard.py))**保持不变并拒绝一切
horizon 字段**(其 ALLOWED_TOP_LEVEL 白名单天然拒收——测试钉死);本 schema 为
news 席专属、新链版本下 opt-in;scorecard.py 的薄接线随链 bump 终局落地。

**钉死公式(M3‴,不留事后选择自由度):**
    GLOBAL_WEIGHTS = {event_materiality: 6, fundamental_link: 5, novelty: 5}
    HORIZON_WEIGHTS = {tradeability_at_horizon: 4};PENALTY_MULTIPLIER = 2
    raw_h = 6·s_mat + 5·s_fund + 5·s_nov + 4·s_trade,h        (满分恰 100)
    news_final_h = round(clamp(raw_h − 2·Σ grounded_global_penalties, 0, 100), 1)
    (全精度到 clamp,序列化时**一次**舍入;v1 全部罚分全局、每 horizon 同样适用)

**M2⁴ 语义(fail-closed 钉死):** 三个注册 horizon 全适用;每
`(tradeability_at_horizon, horizon)` 对**强制存在且有限**——缺对/重复/多余/非有限
= factor 腿 **schema 失败**(硬失败);存在有限项但证据空/未接地 = 派生 **NO-SCORE
贡献恰 0**(非失败);**v1 无 horizon 级 not_applicable、无权重重归一**。

**证据模型(链单元 BINDING #5):** 每条计分项带 `citations`(注册 record id 列表);
逐项**重算** `dimension_ceiling`(所引最强合格类上限)——有效分 = min(score, ceiling);
未授权/未注册/空引用 → 该项 NO-SCORE;**证据独占全局跨
factor_scores + horizon_factor_scores + penalty_scores**(同 id 进两条计分项 = 硬失败;
非计分论点 horizon_theses 的引用不解锁分)。

**零证据确定性路径(M2⁴ + 链单元 BINDING #4):** 正向总体为空时
`deterministic_zero_factor_record()` 免 LLM 直接产出全部必需对、零分、零引用。

守卫复用(M2″ 明令):`ScorecardViolation` / bool 拒收 / 有限数 / OverflowError /
safe-repr / [0,5] 一律沿用 [scorecard.py](../../../../src/ai_layer/scorecard.py)
的既有实现与模式,不重发明。
"""
from __future__ import annotations

import math
import sys
from numbers import Number
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[4]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from ai_layer.scorecard import ScorecardViolation, _valid_score  # noqa: E402

from workspace.research.ai_research_dept.engine.news_evidence import (  # noqa: E402
    RegistryError, authorize, dimension_ceiling, require_sealed_registry,
)

SCHEMA_ID = "c16_news_horizon_v1"
#: 注册 horizon(冻结顺序;M2″)
HORIZONS = ("next_open", "1-3d", "5-20d")
#: 全局维(M3‴:news 20 分制只替换 catalyst_timing)
GLOBAL_WEIGHTS = {"event_materiality": 6, "fundamental_link": 5, "novelty": 5}
HORIZON_WEIGHTS = {"tradeability_at_horizon": 4}
PENALTY_MULTIPLIER = 2.0
#: news penalty 腿的注册罚分维(v1 全局罚分)
PENALTY_DIMS = frozenset({"coordination_risk", "manipulation_risk", "confidence_cap"})

_FACTOR_TOP_LEVEL = frozenset({"factor_scores", "horizon_factor_scores",
                               "horizon_theses", "what_could_weaken"})
_PENALTY_TOP_LEVEL = frozenset({"penalty_scores", "risk_flags"})
_GLOBAL_ENTRY_KEYS = frozenset({"name", "score_0_5", "citations"})
_HORIZON_ENTRY_KEYS = frozenset({"name", "horizon", "score_0_5", "citations"})
#: D2 论点 typed schema + D3 必填最强反证接地字段
_THESIS_KEYS = frozenset({"horizon", "direction", "causal_chain", "priced_in_status",
                          "alternative_explanation", "base_adverse_scenario",
                          "falsifiable_condition", "strongest_counter"})
_DIRECTIONS = frozenset({"利好", "中性", "利空"})
_MAX_THESES = 8
_MAX_THESIS_CHARS = 200
#: 输出模式(与 news_legs.OUTPUT_MODES 一致;此处独立冻结避免循环依赖)
OUTPUT_MODES = frozenset({"primary_horizon", "vector_only"})


def _safe_repr(v) -> str:
    try:
        return repr(v)[:60]
    except (ValueError, OverflowError):          # repr(10**10000) 位数上限(复用模式)
        return f"<{type(v).__name__}: unrepresentable>"


def _require_score(entry: dict, where: str) -> float:
    """M2⁴:必需项的分数**硬失败**校验(bool 拒/有限/[0,5];复用 c16 守卫语义)。"""
    s = entry.get("score_0_5")
    try:
        ok = (isinstance(s, Number) and not isinstance(s, bool)
              and math.isfinite(float(s)) and 0 <= float(s) <= 5)
    except (TypeError, ValueError, OverflowError):
        ok = False
    if not ok:
        raise ScorecardViolation(
            f"{where} score_0_5 非有限 [0,5] 数(得 {_safe_repr(s)})——"
            f"M2⁴:缺对/非有限 = factor 腿 schema 失败")
    return float(s)


def _validate_citations(entry: dict, where: str) -> list:
    cits = entry.get("citations")
    if not isinstance(cits, list) or any(type(c) is not str for c in cits):
        raise ScorecardViolation(f"{where} citations 须为 str 列表(得 {_safe_repr(cits)})")
    if len(cits) != len(set(cits)):
        raise ScorecardViolation(f"{where} citations 内重复引用")
    return cits


def _entry_effective(score: float, citations: list, registry, *, use: str,
                     dimension: str) -> tuple:
    """单条计分项的**有效分**(链单元 BINDING #5:逐项重算 ceiling):
    - factor 项:每个引用须 authorize(factor_positive, news, dimension);
      有效分 = min(score, dimension_ceiling(citations));空/未授权/未注册引用 →
      NO-SCORE 0(M2⁴:非失败);
    - penalty 项:每个引用须 authorize(penalty, news, **dimension**)——
      **维度感知**(re-review Major:NFR 只封 manipulation_risk、NFC 只封
      coordination_risk、D7 source_status 只封 confidence_cap;错维引用 =
      NO-SCORE,注册映射不可跨);grounded 即计(罚分无类上限,风险方向不节流)。
    返回 (effective_score, grounded)。"""
    if not citations:
        return 0.0, False                        # 证据空 → NO-SCORE 贡献恰 0
    if use == "factor_positive":
        for rid in citations:
            rec = registry.get(rid)
            if rec is None or not authorize(rec, use="factor_positive",
                                            consumer_seat="news",
                                            target_dimension=dimension):
                return 0.0, False                # 未注册/未授权引用 → NO-SCORE
        ceiling = dimension_ceiling(citations, registry, consumer_seat="news",
                                    target_dimension=dimension)
        if ceiling <= 0:
            return 0.0, False
        return min(score, float(ceiling)), True
    for rid in citations:                        # penalty:维度感知授权(Major)
        rec = registry.get(rid)
        if rec is None or not authorize(rec, use="penalty", consumer_seat="news",
                                        target_dimension=dimension):
            return 0.0, False
    return score, True


def validate_factor_leg_output(record: dict, registry) -> dict:
    """factor 腿输出的**确定性校验**(schema 硬失败 + 逐项接地推导)。返回
    {"global": {dim: (eff, grounded)}, "horizon": {(dim, h): (eff, grounded)},
    "cited_ids": list}(供独占与聚合)。
    schema 失败(= factor 腿失败,M2⁴):顶层键越界;全局维非恰一;(name, horizon)
    对缺/重/多;分数非有限 [0,5];citations 形状非法;论点 schema 非法。"""
    registry = require_sealed_registry(registry)
    if not isinstance(record, dict):
        raise ScorecardViolation("factor 腿输出须为 dict")
    unknown = set(record) - _FACTOR_TOP_LEVEL
    if unknown:
        raise ScorecardViolation(f"factor 腿输出未知顶层键 {sorted(unknown)}"
                                 f"(含 penalty_scores——罚分属 penalty 腿,M2‴)")
    cited: list = []
    # ---- 全局维:恰一(require_registered_exact 语义) ----
    g_entries = record.get("factor_scores")
    if not isinstance(g_entries, list):
        raise ScorecardViolation("factor_scores 须为列表")
    g_seen: dict = {}
    for e in g_entries:
        if not isinstance(e, dict) or set(e) != _GLOBAL_ENTRY_KEYS:
            raise ScorecardViolation(f"全局计分项键须恰 {sorted(_GLOBAL_ENTRY_KEYS)}:"
                                     f"{_safe_repr(e)}")
        name = e["name"]
        if name not in GLOBAL_WEIGHTS:
            raise ScorecardViolation(f"未注册全局维 {name!r}(须 ∈ {sorted(GLOBAL_WEIGHTS)})")
        if name in g_seen:
            raise ScorecardViolation(f"全局维 {name!r} 重复——恰一(C16)")
        score = _require_score(e, f"factor_scores[{name}]")
        cits = _validate_citations(e, f"factor_scores[{name}]")
        cited.extend(cits)
        g_seen[name] = _entry_effective(score, cits, registry,
                                        use="factor_positive", dimension=name)
    missing = sorted(set(GLOBAL_WEIGHTS) - set(g_seen))
    if missing:
        raise ScorecardViolation(f"全局维缺失 {missing}——恰一强制(M2⁴)")
    # ---- horizon 维:(name, horizon) 恰一覆盖注册积 ----
    h_entries = record.get("horizon_factor_scores")
    if not isinstance(h_entries, list):
        raise ScorecardViolation("horizon_factor_scores 须为列表")
    h_seen: dict = {}
    for e in h_entries:
        if not isinstance(e, dict) or set(e) != _HORIZON_ENTRY_KEYS:
            raise ScorecardViolation(f"horizon 计分项键须恰 {sorted(_HORIZON_ENTRY_KEYS)}:"
                                     f"{_safe_repr(e)}")
        name, h = e["name"], e["horizon"]
        if name not in HORIZON_WEIGHTS or h not in HORIZONS:
            raise ScorecardViolation(
                f"未注册 (name, horizon) = ({name!r}, {h!r})"
                f"(须 ∈ {sorted(HORIZON_WEIGHTS)} × {list(HORIZONS)})")
        if (name, h) in h_seen:
            raise ScorecardViolation(f"(name, horizon) = ({name!r}, {h!r}) 重复——"
                                     f"exact-once(M2″)")
        score = _require_score(e, f"horizon[{name}@{h}]")
        cits = _validate_citations(e, f"horizon[{name}@{h}]")
        cited.extend(cits)
        h_seen[(name, h)] = _entry_effective(score, cits, registry,
                                             use="factor_positive", dimension=name)
    required = {(n, h) for n in HORIZON_WEIGHTS for h in HORIZONS}
    if set(h_seen) != required:
        raise ScorecardViolation(
            f"(name, horizon) 覆盖不符:缺 {sorted(required - set(h_seen))}——"
            f"三 horizon 全适用强制(M2⁴:无 horizon 级 not_applicable/无重归一)")
    # ---- 论点(D2 typed + D3 必填最强反证;非计分——引用不进独占集不解锁分)----
    theses = record.get("horizon_theses", [])
    if not isinstance(theses, list) or len(theses) > _MAX_THESES:
        raise ScorecardViolation(f"horizon_theses 须为 ≤{_MAX_THESES} 的列表")
    for t in theses:
        if not isinstance(t, dict) or set(t) != _THESIS_KEYS:
            raise ScorecardViolation(f"论点键须恰 {sorted(_THESIS_KEYS)}:{_safe_repr(t)}")
        if t["horizon"] not in HORIZONS or t["direction"] not in _DIRECTIONS:
            raise ScorecardViolation(f"论点 horizon/direction 未注册:{_safe_repr(t)}")
        for k in _THESIS_KEYS - {"horizon", "direction"}:
            v = t[k]
            if not isinstance(v, str) or not v.strip() or len(v) > _MAX_THESIS_CHARS:
                raise ScorecardViolation(
                    f"论点字段 {k} 须为非空有界字符串(D3:最强反证必填接地)")
    return {"global": g_seen, "horizon": h_seen, "cited_ids": cited}


def validate_penalty_leg_output(record: dict, registry) -> dict:
    """penalty 腿输出校验(M2‴ 隔离):只许 penalty_scores/risk_flags;罚分名 ∈
    注册罚分维、恰一;grounded 推导(penalty 授权)。返回
    {"penalties": {name: (eff, grounded)}, "cited_ids": list}。"""
    registry = require_sealed_registry(registry)
    if not isinstance(record, dict):
        raise ScorecardViolation("penalty 腿输出须为 dict")
    unknown = set(record) - _PENALTY_TOP_LEVEL
    if unknown:
        raise ScorecardViolation(f"penalty 腿输出未知顶层键 {sorted(unknown)}"
                                 f"(含 factor_scores——因子分属 factor 腿,M2‴)")
    entries = record.get("penalty_scores")
    if not isinstance(entries, list):
        raise ScorecardViolation("penalty_scores 须为列表")
    seen: dict = {}
    cited: list = []
    for e in entries:
        if not isinstance(e, dict) or set(e) != _GLOBAL_ENTRY_KEYS:
            raise ScorecardViolation(f"罚分项键须恰 {sorted(_GLOBAL_ENTRY_KEYS)}:"
                                     f"{_safe_repr(e)}")
        name = e["name"]
        if name not in PENALTY_DIMS:
            raise ScorecardViolation(f"未注册罚分维 {name!r}(须 ∈ {sorted(PENALTY_DIMS)})")
        if name in seen:
            raise ScorecardViolation(f"罚分维 {name!r} 重复——恰一")
        score = _require_score(e, f"penalty[{name}]")
        cits = _validate_citations(e, f"penalty[{name}]")
        cited.extend(cits)
        seen[name] = _entry_effective(score, cits, registry, use="penalty",
                                      dimension=name)
    flags = record.get("risk_flags", [])
    if not isinstance(flags, list) or any(not isinstance(x, str) for x in flags):
        raise ScorecardViolation("risk_flags 须为字符串列表(审计域,不计分)")
    return {"penalties": seen, "cited_ids": cited}


def assert_evidence_exclusive(factor_validated: dict, penalty_validated: dict) -> None:
    """证据独占**全局**跨 factor + horizon + penalty(M2″:同 id 进两条计分项 =
    硬失败——一行证据只能解锁一个分)。"""
    all_cited = factor_validated["cited_ids"] + penalty_validated["cited_ids"]
    dup = sorted({c for c in all_cited if all_cited.count(c) > 1})
    if dup:
        raise ScorecardViolation(
            f"证据独占违反:引用 {dup} 出现在多条计分项——行 ID 独占是全局契约(M2″)")


def compute_news_final_by_horizon(factor_validated: dict,
                                  penalty_validated: dict) -> dict:
    """钉死公式(M3‴):raw_h = 6·mat + 5·fund + 5·nov + 4·trade_h;
    news_final_h = round(clamp(raw_h − 2·Σ grounded_penalties, 0, 100), 1)。
    全精度到 clamp,一次舍入;NO-SCORE 项(ungrounded)贡献恰 0。"""
    g = factor_validated["global"]
    tr = factor_validated["horizon"]
    pen_total = sum(eff for eff, grounded in penalty_validated["penalties"].values()
                    if grounded)
    finals: dict = {}
    for h in HORIZONS:
        raw = (GLOBAL_WEIGHTS["event_materiality"] * g["event_materiality"][0]
               + GLOBAL_WEIGHTS["fundamental_link"] * g["fundamental_link"][0]
               + GLOBAL_WEIGHTS["novelty"] * g["novelty"][0]
               + HORIZON_WEIGHTS["tradeability_at_horizon"]
               * tr[("tradeability_at_horizon", h)][0])
        finals[h] = round(max(0.0, min(100.0, raw - PENALTY_MULTIPLIER * pen_total)), 1)
    return finals


def news_final_scalar(finals: dict, *, output_mode: str,
                      primary_decision_horizon: "str | None") -> "float | None":
    """标量别名(M3‴ 二选一 hash-bound 模式):primary_horizon → `news.final` =
    契约钉死 horizon 的确定性别名(不逐股、不事后选——horizon 由冻结契约供给);
    vector_only → **无标量**(None;永不喂 judge/composite/绑定)。"""
    if type(output_mode) is not str or output_mode not in OUTPUT_MODES:
        raise RegistryError(f"未注册 output_mode {output_mode!r}")
    if output_mode == "vector_only":
        if primary_decision_horizon is not None:
            raise RegistryError("vector_only 不得钉 primary_decision_horizon(无标量)")
        return None
    if type(primary_decision_horizon) is not str \
            or primary_decision_horizon not in HORIZONS:
        raise RegistryError(
            f"primary_horizon 模式须由冻结契约钉 primary_decision_horizon ∈ "
            f"{list(HORIZONS)}(得 {primary_decision_horizon!r})")
    v = finals[primary_decision_horizon]
    if not (isinstance(v, float) and math.isfinite(v)):
        raise ScorecardViolation("primary 模式下选定 horizon final 必须有限(M2⁴)")
    return v


def deterministic_zero_factor_record() -> dict:
    """零证据确定性路径(M2⁴ + 链单元 BINDING #4):正向总体为空时**免 LLM**
    产出全部必需对、零分、零引用——过 validate_factor_leg_output,全 NO-SCORE
    贡献恰 0(绝非 not_applicable)。"""
    return {"factor_scores": [{"name": d, "score_0_5": 0, "citations": []}
                              for d in sorted(GLOBAL_WEIGHTS)],
            "horizon_factor_scores": [{"name": "tradeability_at_horizon",
                                       "horizon": h, "score_0_5": 0, "citations": []}
                                      for h in HORIZONS],
            "horizon_theses": []}


def evaluate_news_horizon(factor_record: dict, penalty_record: dict, registry, *,
                          output_mode: str,
                          primary_decision_horizon: "str | None") -> dict:
    """一站式确定性评估(校验→独占→公式→别名;档案重算走同一函数——
    verify_archive_semantics 从封存条目重算,不信封存计算值,M2⁴)。"""
    f = validate_factor_leg_output(factor_record, registry)
    p = validate_penalty_leg_output(penalty_record, registry)
    assert_evidence_exclusive(f, p)
    finals = compute_news_final_by_horizon(f, p)
    scalar = news_final_scalar(finals, output_mode=output_mode,
                               primary_decision_horizon=primary_decision_horizon)
    return {"schema_id": SCHEMA_ID, "news_final_by_horizon": finals,
            "news_final": scalar, "output_mode": output_mode,
            "primary_decision_horizon": primary_decision_horizon}


# 复用证明:_valid_score 是 c16_v1 的 [0,5] 守卫(M2″ 明令沿用,此处 re-export
# 供 penalty/factor 腿执行体做前置轻校验;完整硬校验在 _require_score)
reused_valid_score = _valid_score
