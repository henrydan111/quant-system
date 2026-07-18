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

LLM 执行体可注入(`factor_leg_fn/penalty_leg_fn` 收**新铸 ExecutionView**——校验后
即铸的不可变视图,只暴露 payload_text,不暴露 AST/SealedPayload;抛异常=腿失败)
——本单元零 LLM 依赖;真实 prompt/route/schema 校验在下一单元接上。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import re

from workspace.research.ai_research_dept.engine.news_cards import (
    D7DecisionArtifact, verify_d7_artifact,
)
from workspace.research.ai_research_dept.engine.news_decision import (
    SealedPayload, build_leg_payload_ast, build_sealed_payload,
    make_execution_view, serialize_payload_ast, verify_payload_for_execution,
)
from workspace.research.ai_research_dept.engine.news_evidence import (
    RegistryError, require_sealed_registry,
)
from workspace.research.ai_research_dept.engine.news_seal import seal_hash, verify_sealed

_HEX64_RE = re.compile(r"[0-9a-f]{64}")

#: 输出模式(M3‴ hash-bound 二选一;binding 语义由矩阵推导)
OUTPUT_MODES = frozenset({"primary_horizon", "vector_only"})
_FACTOR_STATUSES = frozenset({"success", "failed"})
_PENALTY_STATUSES = frozenset({"success", "empty_success", "failed", "not_run"})


class LegIntegrityError(Exception):
    """M3⁴ 第 5 行:penalty 在零适格下竟被执行 = 完整性违规(或矩阵非法组合)。"""


def _require_canonical(sp: SealedPayload, artifact: D7DecisionArtifact, *,
                       use: str) -> None:
    """executor-review Blocker:腿 payload 必须**逐字节等于** canonical 内容承载
    渲染(`build_leg_payload_ast` 从已验工件确定性重推导)——裸 ID 列表/手搭
    payload 在执行体前拒。"""
    canonical = serialize_payload_ast(
        build_leg_payload_ast(artifact, use=use, consumer_seat="news"))
    if sp.payload_text != canonical:
        raise RegistryError(
            f"{use} 腿 payload 非 canonical 内容承载渲染——LLM 必须看到证据正文,"
            f"裸 ID/手搭 payload 拒(executor-review Blocker)")


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
        # re-review B3:**精确原语类型**先于矩阵比对(int 0/1 冒充 bool、bool 冒充
        # count 一律拒——Python 的 0==False 使宽松比较可被伪造)
        for name in ("decision_id", "output_mode", "factor_leg_status",
                     "penalty_eligible_set_hash", "penalty_leg_status",
                     "news_status", "factor_payload_hash"):
            if type(getattr(self, name)) is not str:
                raise RegistryError(f"{name} 须恰 str(得 {type(getattr(self, name)).__name__})")
        for name in ("shadow_complete", "decision_complete", "binding_eligible"):
            if type(getattr(self, name)) is not bool:
                raise RegistryError(f"{name} 须恰 bool(int 冒充拒,re-review B3)")
        if type(self.penalty_eligible_count) is not int \
                or isinstance(self.penalty_eligible_count, bool) \
                or self.penalty_eligible_count < 0:
            raise RegistryError("penalty_eligible_count 须非负 int(非 bool)")
        # re-review B3:强制哈希 64 位小写 hex
        for name in ("penalty_eligible_set_hash", "factor_payload_hash"):
            if not _HEX64_RE.fullmatch(getattr(self, name)):
                raise RegistryError(f"{name} 须 64 位小写 hex(得 {getattr(self, name)!r})")
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
        # re-review B3:penalty payload 哈希与腿状态**双向**绑定——
        # success/failed 恰须 64-hex;empty_success/not_run 恰须 None
        if self.penalty_leg_status in ("success", "failed"):
            if not (type(self.penalty_payload_hash) is str
                    and _HEX64_RE.fullmatch(self.penalty_payload_hash)):
                raise LegIntegrityError(
                    f"penalty {self.penalty_leg_status} 必须携带 64-hex payload 哈希"
                    f"(得 {self.penalty_payload_hash!r})——无 payload 的执行不存在(B3)")
        else:                                     # empty_success / not_run
            if self.penalty_payload_hash is not None:
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


def outcome_canonical_payload(outcome: NewsLegOutcome) -> dict:
    """终态的 **canonical 载荷**——模块级、不可覆写、只读实际字段
    (archive-re-review#6 P0 同类面:安全边界上绝不调用可被子类覆写的虚方法
    `_payload()`;配合各门的恰类型检查)。"""
    return {"decision_id": outcome.decision_id, "output_mode": outcome.output_mode,
            "factor_leg_status": outcome.factor_leg_status,
            "penalty_eligible_count": outcome.penalty_eligible_count,
            "penalty_eligible_set_hash": outcome.penalty_eligible_set_hash,
            "penalty_leg_status": outcome.penalty_leg_status,
            "news_status": outcome.news_status,
            "shadow_complete": outcome.shadow_complete,
            "decision_complete": outcome.decision_complete,
            "binding_eligible": outcome.binding_eligible,
            "factor_payload_hash": outcome.factor_payload_hash,
            "penalty_payload_hash": outcome.penalty_payload_hash}


def run_news_two_legs(artifact: D7DecisionArtifact, *, ledger_dir, decision_id: str,
                      output_mode: str, factor_payload_ast, penalty_payload_ast,
                      factor_leg_fn, penalty_leg_fn) -> NewsLegOutcome:
    """双腿执行状态机(M2‴/M3⁴)。执行序(确定性,短路):
    1. 工件过门 + penalty 适格集从终注册表推导(计数+集合哈希封存);
    2. factor 腿:经咽喉点铸密封 payload(账本门在内)→ 边界校验 → **新铸
       ExecutionView** → `factor_leg_fn(view)`(抛异常=腿失败 → penalty **不跑**
       (not_run)→ 硬失败终态);
    3. penalty 腿:适格=0 → **确定性 empty_success,结构上不调** `penalty_leg_fn`;
       适格>0 → 经咽喉点(use=penalty 腿级门)→ 边界校验 → 新铸视图 →
       `penalty_leg_fn(view)`(抛异常=腿失败 → news 硬失败,**绝不静默空罚分**);
    4. 终态经 `NewsLegOutcome` 密封(矩阵重算自验)。
    执行体只收校验后新铸的不可变 ExecutionView(链单元 BINDING #1)——消费
    view.payload_text,LLM 看到的就是被门与被封的字节。"""
    # ---- 预校验(re-review M3 + re-review#2 M1:一切确定性配置错误——含**精确
    # 类型**(str 子类冒充 mode/decision_id)——在任何执行体运行前发现)----
    if type(output_mode) is not str or output_mode not in OUTPUT_MODES:
        raise RegistryError(f"未注册 output_mode {output_mode!r}"
                            f"(须恰 str ∈ {sorted(OUTPUT_MODES)},子类拒)——执行体前拒(M3)")
    if type(decision_id) is not str or not decision_id.strip():
        raise RegistryError(f"decision_id 须恰 str 非空(得 {type(decision_id).__name__})"
                            f"——执行体前拒(re-review#2 M1)")
    verify_d7_artifact(artifact)
    if decision_id != artifact.bundle.decision_id:
        raise RegistryError(f"decision_id {decision_id!r} ≠ 工件 "
                            f"{artifact.bundle.decision_id!r}——执行体前拒")
    eligible = penalty_eligible_records(artifact)
    count, set_hash = len(eligible), _eligible_set_hash(eligible)
    if count == 0 and penalty_payload_ast is not None:
        raise RegistryError("penalty 适格=0 却提供了 penalty payload——配置错误,"
                            "执行体前拒(M3⁴ 行1:零适格不存在 penalty payload)")
    if count > 0 and penalty_payload_ast is None:
        raise RegistryError(
            f"penalty 适格={count} 但未提供 penalty payload——腿必须运行(M2‴),"
            f"执行体前拒(M3)")
    # 两腿密封 payload 全部先铸好(账本门/封闭 AST/出处/终字节门/完整性都在此),
    # 任何失败都发生在 factor 执行体之前
    factor_payload = build_sealed_payload(
        factor_payload_ast, artifact, ledger_dir=ledger_dir, decision_id=decision_id,
        consumer_seat="news", use="factor_positive")
    penalty_payload: "SealedPayload | None" = None
    if count > 0:
        penalty_payload = build_sealed_payload(
            penalty_payload_ast, artifact, ledger_dir=ledger_dir,
            decision_id=decision_id, consumer_seat="news", use="penalty")

    # ---- 执行(执行体只经边界校验器可达,且**调用方声明期望槽位**——penalty
    # payload 冒充 factor 槽在此拒,re-review B2 + re-review#2 B1)----
    verify_payload_for_execution(
        factor_payload, artifact, ledger_dir=ledger_dir,
        expected_decision_id=decision_id, expected_consumer_seat="news",
        expected_use="factor_positive", expected_target_dimension=None)
    # executor-review Blocker:边界**重渲染** canonical 内容承载 AST 并逐字节比对
    # ——非 canonical 渲染器产物(裸 ID 列表等)到不了执行体
    _require_canonical(factor_payload, artifact, use="factor_positive")
    try:
        # 链单元 BINDING #1:执行体唯一输入 = 校验后**新铸**的不可变视图
        factor_leg_fn(make_execution_view(factor_payload))
        factor_status = "success"
    except Exception:
        factor_status = "failed"

    if factor_status == "failed":
        penalty_status = "not_run"                    # 短路:必需腿失败即终态
        penalty_payload = None                        # 终态不携未执行 payload 哈希
    elif count == 0:
        penalty_status = "empty_success"              # 确定性封存,不调 LLM(M3⁴ 行1)
    else:
        verify_payload_for_execution(
            penalty_payload, artifact, ledger_dir=ledger_dir,
            expected_decision_id=decision_id, expected_consumer_seat="news",
            expected_use="penalty", expected_target_dimension=None)
        _require_canonical(penalty_payload, artifact, use="penalty")
        try:
            penalty_leg_fn(make_execution_view(penalty_payload))
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


def verify_outcome_for_binding(outcome: NewsLegOutcome, artifact: D7DecisionArtifact,
                               factor_payload: SealedPayload,
                               penalty_payload: "SealedPayload | None", *,
                               ledger_dir, expected_output_mode: str) -> NewsLegOutcome:
    """**档案/绑定边界**(re-review B3 + re-review#2 B1:绝不信终态自报值,也绝不
    信其自封 output_mode)。`expected_output_mode` 来自**冻结评分契约**——精确类型
    +精确值比对(vector 跑的 payload 挂上新铸 primary 终态在此拒:契约说 vector 则
    primary 终态不符,契约说 primary 则那才是合法模式);从已验工件**重算** penalty
    适格计数+集合哈希;两腿 payload 经执行体边界校验器(**带期望槽位**——penalty
    payload 冒充 factor 槽拒)重验且哈希与终态逐字节相等。"""
    if type(outcome) is not NewsLegOutcome:
        raise RegistryError(
            f"绑定边界只收恰 NewsLegOutcome(得 {type(outcome).__name__})——"
            f"子类可覆写 _payload 脱钩,拒(archive-re-review#6 P0 同类面)")
    if type(expected_output_mode) is not str or expected_output_mode not in OUTPUT_MODES:
        raise RegistryError(f"expected_output_mode 须恰 str ∈ {sorted(OUTPUT_MODES)}"
                            f"(来自冻结评分契约;得 {expected_output_mode!r})")
    verify_sealed(outcome_canonical_payload(outcome), outcome.outcome_hash,
                  field_name="outcome_hash")
    if outcome.output_mode != expected_output_mode:
        raise LegIntegrityError(
            f"终态自封 output_mode {outcome.output_mode!r} ≠ 冻结契约期望 "
            f"{expected_output_mode!r}——模式重放/翻铸拒(re-review#2 B1)")
    verify_d7_artifact(artifact)
    if outcome.decision_id != artifact.bundle.decision_id:
        raise RegistryError("终态 decision_id 与工件不符(绑定边界)")
    eligible = penalty_eligible_records(artifact)
    if (outcome.penalty_eligible_count != len(eligible)
            or outcome.penalty_eligible_set_hash != _eligible_set_hash(eligible)):
        raise LegIntegrityError(
            "终态自报的 penalty 适格计数/集合哈希与已验工件重算不符——拒(B3)")
    verify_payload_for_execution(
        factor_payload, artifact, ledger_dir=ledger_dir,
        expected_decision_id=outcome.decision_id, expected_consumer_seat="news",
        expected_use="factor_positive", expected_target_dimension=None)
    if factor_payload.payload_hash != outcome.factor_payload_hash:
        raise LegIntegrityError("factor payload 与终态自报哈希不符(B3)")
    if outcome.penalty_leg_status in ("success", "failed"):
        if penalty_payload is None:
            raise LegIntegrityError("penalty 执行过却未提供其 payload 供重验(B3)")
        verify_payload_for_execution(
            penalty_payload, artifact, ledger_dir=ledger_dir,
            expected_decision_id=outcome.decision_id, expected_consumer_seat="news",
            expected_use="penalty", expected_target_dimension=None)
        if penalty_payload.payload_hash != outcome.penalty_payload_hash:
            raise LegIntegrityError("penalty payload 与终态自报哈希不符(B3)")
    elif penalty_payload is not None:
        raise LegIntegrityError(
            f"penalty {outcome.penalty_leg_status} 不该有 payload(绑定边界)")
    return outcome
