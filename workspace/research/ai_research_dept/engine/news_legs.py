# SCRIPT_STATUS: ACTIVE — 新闻快讯:双腿执行状态机(NF §7 席位接线·单元2;M2‴/M3⁴)
"""Two-leg news execution — the M3⁴ five-row terminal-state matrix as a REAL state machine.

设计 v1.12 §6b M2‴(隔离罚分腿)+ M3⁴(穷尽终态矩阵)+ 实现铁律("双腿矩阵编码为
真状态机,必需腿失败终态阻止发布+绑定"):

- **两腿隔离**:`news_factor_leg` 只见 factor_positive 记录的密封 payload;
  `news_penalty_leg` 只见 penalty 记录的密封 payload——各自独立经
  [news_decision.build_sealed_payload](news_decision.py) 咽喉点(账本门+封闭 AST+
  终字节门+密封),M2‴ 的"元数据过滤 payload"由腿级门机械执行。
- **五行终态矩阵(M3⁴,穷尽)**:

  | factor 腿 | penalty 适格数 | penalty 结果 | primary 模式 | vector_only 模式 |
  |---|---|---|---|---|
  | success | 0 | `empty_success`(**不调 LLM**) | 可发布 | shadow_complete=true |
  | success | >0 | success | 可发布 | shadow_complete=true |
  | success | >0 | failed | **硬失败:不发布不绑定** | 失败 shadow |
  | failed | 任意 | `not_run`(短路) | **硬失败** | 失败 shadow |
  | success | 0 | penalty 竟被调(success/failed) | **完整性违规** | 完整性违规 |

  `NewsLegOutcome.__post_init__` 对矩阵**重算比对**(verify-not-trust 用在状态行上):
  非法组合(第 5 行、适格>0 却 empty_success、终态字段与推导不符)**无法构造**。
- **vector_only 永不 binding_eligible**(M2⁴);primary 模式仅 news success 可绑定。
- 有 penalty 适格记录而 penalty 腿失败 → news 硬失败(**绝不静默空罚分**);
  适格=0 → 确定性封 `empty_success`,状态机结构上不可能调 penalty 执行体。
- 封存字段 = 设计点名的 9 个(factor_leg_status / penalty_eligible_count /
  penalty_eligible_set_hash / penalty_leg_status / news_status / output_mode /
  shadow_complete / decision_complete / binding_eligible)+ 两腿 payload 哈希,
  outcome_hash 全 SHA-256 密封。

LLM 执行体可注入(`factor_leg_fn/penalty_leg_fn` 收 SealedPayload;抛异常=腿失败)
——本单元零 LLM 依赖;真实 prompt/route/schema 校验在下一单元接上。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from workspace.research.ai_research_dept.engine.news_cards import (
    D7DecisionArtifact, verify_d7_artifact,
)
from workspace.research.ai_research_dept.engine.news_decision import (
    SealedPayload, build_sealed_payload,
)
from workspace.research.ai_research_dept.engine.news_evidence import (
    RegistryError, require_sealed_registry,
)
from workspace.research.ai_research_dept.engine.news_seal import seal_hash, verify_sealed

#: 输出模式(M3‴ hash-bound 二选一;binding 语义由矩阵推导)
OUTPUT_MODES = frozenset({"primary_horizon", "vector_only"})
_FACTOR_STATUSES = frozenset({"success", "failed"})
_PENALTY_STATUSES = frozenset({"success", "empty_success", "failed", "not_run"})


class LegIntegrityError(Exception):
    """M3⁴ 第 5 行:penalty 在零适格下竟被执行 = 完整性违规(或矩阵非法组合)。"""


def penalty_eligible_records(artifact: D7DecisionArtifact) -> list:
    """penalty 适格集(M2‴):终注册表中 `penalty ∈ allowed_uses ∧ news ∈
    allowed_consumers` 的记录(NFR 风险行 / NFC 协同行 / D7 source_status 子行),
    按 record_id 排序(确定性)。"""
    reg = require_sealed_registry(artifact.final_registry)
    return sorted((r for r in reg.records.values()
                   if "penalty" in r.allowed_uses and "news" in r.allowed_consumers),
                  key=lambda r: r.record_id)


def _eligible_set_hash(records: list) -> str:
    return seal_hash([[r.record_id, r.content_hash] for r in records])


def _derive_terminal(factor_status: str, eligible_count: int, penalty_status: str,
                     output_mode: str) -> dict:
    """M3⁴ 矩阵的**唯一**推导函数(状态机与终态自验共用同一张表)。"""
    if output_mode not in OUTPUT_MODES:
        raise RegistryError(f"未注册 output_mode {output_mode!r}(须 ∈ {sorted(OUTPUT_MODES)})")
    if factor_status not in _FACTOR_STATUSES or penalty_status not in _PENALTY_STATUSES:
        raise RegistryError(f"未注册腿状态 factor={factor_status!r} penalty={penalty_status!r}")
    # 第 5 行:零适格下 penalty 被执行(success/failed 都算"被调")= 完整性违规
    if eligible_count == 0 and penalty_status in ("success", "failed"):
        raise LegIntegrityError(
            "M3⁴ 第 5 行:penalty 适格=0 却存在 penalty 执行结果"
            f"({penalty_status!r})——penalty LLM 绝不该被调,完整性违规")
    if eligible_count > 0 and penalty_status == "empty_success":
        raise LegIntegrityError(
            f"penalty 适格={eligible_count} 却记 empty_success——静默空罚分拒(M2‴)")
    if factor_status == "failed":
        if penalty_status != "not_run":
            raise LegIntegrityError("factor 腿失败即短路——penalty 状态必须 not_run")
        ok = False
    else:
        if penalty_status == "not_run":
            raise LegIntegrityError("factor 腿成功则 penalty 必须有终态(empty_success/success/failed)")
        ok = penalty_status in ("success", "empty_success")
    news_status = "success" if ok else "hard_failed"
    return {"news_status": news_status,
            "shadow_complete": (output_mode == "vector_only" and ok),
            "decision_complete": ok,
            # M2⁴:vector_only 永不 binding_eligible;primary 仅 success 可绑定
            "binding_eligible": (output_mode == "primary_horizon" and ok)}


@dataclass(frozen=True)
class NewsLegOutcome:
    """双腿**密封终态**(9 封存字段 + 两腿 payload 哈希)。__post_init__ 用
    `_derive_terminal` 对矩阵重算比对——非法组合(M3⁴ 第 5 行等)无法构造,
    终态字段与推导不符 = 拒;outcome_hash 全 SHA-256。"""
    decision_id: str
    output_mode: str
    factor_leg_status: str
    penalty_eligible_count: int
    penalty_eligible_set_hash: str
    penalty_leg_status: str
    news_status: str
    shadow_complete: bool
    decision_complete: bool
    binding_eligible: bool
    factor_payload_hash: str
    penalty_payload_hash: "str | None"
    outcome_hash: str = field(default="")

    def __post_init__(self):
        derived = _derive_terminal(self.factor_leg_status, self.penalty_eligible_count,
                                   self.penalty_leg_status, self.output_mode)
        stated = {"news_status": self.news_status,
                  "shadow_complete": self.shadow_complete,
                  "decision_complete": self.decision_complete,
                  "binding_eligible": self.binding_eligible}
        if stated != derived:
            raise LegIntegrityError(
                f"终态字段与 M3⁴ 矩阵推导不符:声明 {stated} vs 推导 {derived}——"
                f"状态行不可伪造(verify-not-trust)")
        if type(self.penalty_eligible_count) is not int or self.penalty_eligible_count < 0:
            raise RegistryError("penalty_eligible_count 须非负 int")
        if self.penalty_leg_status in ("empty_success", "not_run") \
                and self.penalty_payload_hash is not None:
            raise LegIntegrityError(
                f"penalty {self.penalty_leg_status} 不该有 payload 哈希——"
                f"零适格/短路下不存在 penalty payload")
        if self.outcome_hash:
            verify_sealed(self._payload(), self.outcome_hash, field_name="outcome_hash")
        else:
            object.__setattr__(self, "outcome_hash", seal_hash(self._payload()))

    def _payload(self) -> dict:
        return {"decision_id": self.decision_id, "output_mode": self.output_mode,
                "factor_leg_status": self.factor_leg_status,
                "penalty_eligible_count": self.penalty_eligible_count,
                "penalty_eligible_set_hash": self.penalty_eligible_set_hash,
                "penalty_leg_status": self.penalty_leg_status,
                "news_status": self.news_status,
                "shadow_complete": self.shadow_complete,
                "decision_complete": self.decision_complete,
                "binding_eligible": self.binding_eligible,
                "factor_payload_hash": self.factor_payload_hash,
                "penalty_payload_hash": self.penalty_payload_hash}


def run_news_two_legs(artifact: D7DecisionArtifact, *, ledger_dir, decision_id: str,
                      output_mode: str, factor_payload_ast, penalty_payload_ast,
                      factor_leg_fn, penalty_leg_fn) -> NewsLegOutcome:
    """双腿执行状态机(M2‴/M3⁴)。执行序(确定性,短路):
    1. 工件过门 + penalty 适格集从终注册表推导(计数+集合哈希封存);
    2. factor 腿:经咽喉点铸密封 payload(账本门在内)→ `factor_leg_fn(SealedPayload)`
       (抛异常=腿失败 → penalty **不跑**(not_run)→ 硬失败终态);
    3. penalty 腿:适格=0 → **确定性 empty_success,结构上不调** `penalty_leg_fn`;
       适格>0 → 经咽喉点(use=penalty 腿级门)→ `penalty_leg_fn(SealedPayload)`
       (抛异常=腿失败 → news 硬失败,**绝不静默空罚分**);
    4. 终态经 `NewsLegOutcome` 密封(矩阵重算自验)。
    执行体只收 SealedPayload——LLM 看到的就是被门与被封的字节。"""
    verify_d7_artifact(artifact)
    eligible = penalty_eligible_records(artifact)
    count, set_hash = len(eligible), _eligible_set_hash(eligible)

    factor_payload = build_sealed_payload(
        factor_payload_ast, artifact, ledger_dir=ledger_dir, decision_id=decision_id,
        consumer_seat="news", use="factor_positive")
    try:
        factor_leg_fn(factor_payload)
        factor_status = "success"
    except Exception:
        factor_status = "failed"

    penalty_payload: "SealedPayload | None" = None
    if factor_status == "failed":
        penalty_status = "not_run"                    # 短路:必需腿失败即终态
    elif count == 0:
        penalty_status = "empty_success"              # 确定性封存,不调 LLM(M3⁴ 行1)
    else:
        if penalty_payload_ast is None:
            raise RegistryError(
                f"penalty 适格={count} 但未提供 penalty payload——腿必须运行(M2‴)")
        penalty_payload = build_sealed_payload(
            penalty_payload_ast, artifact, ledger_dir=ledger_dir,
            decision_id=decision_id, consumer_seat="news", use="penalty")
        try:
            penalty_leg_fn(penalty_payload)
            penalty_status = "success"
        except Exception:
            penalty_status = "failed"

    derived = _derive_terminal(factor_status, count, penalty_status, output_mode)
    return NewsLegOutcome(
        decision_id=decision_id, output_mode=output_mode,
        factor_leg_status=factor_status, penalty_eligible_count=count,
        penalty_eligible_set_hash=set_hash, penalty_leg_status=penalty_status,
        news_status=derived["news_status"],
        shadow_complete=derived["shadow_complete"],
        decision_complete=derived["decision_complete"],
        binding_eligible=derived["binding_eligible"],
        factor_payload_hash=factor_payload.payload_hash,
        penalty_payload_hash=(penalty_payload.payload_hash
                              if penalty_payload is not None else None))
