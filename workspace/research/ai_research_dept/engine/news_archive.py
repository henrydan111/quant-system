# SCRIPT_STATUS: ACTIVE — 新闻快讯:档案/绑定边界(NF §7 最终集成·单元1)
"""Decision archive boundary — joint tuple verification + sealing + ledger-head anchoring.

最终集成子块的第一承重单元,逐字落执行体终审的 6 条 BINDING 需求中的 #1/#6:

- **联合验证先于封印**(BINDING #1,终审头条):`verify_execution_bundle` 对
  outcome / 选定终态出处行 / 空罚分三元组做**全量重推导联合验证**:
  * outcome 经 `verify_outcome_for_binding`(canonical payload 确定性重建 →
    哈希逐字节相等;expected_output_mode 来自冻结契约);
  * 每条选定终态行:entry_hash 重算、**盘上出处文件内存在**、execution_id/
    decision_id/schema_id/payload_hash 五向一致、verdict 与腿终态语义一致
    (success→valid|deterministic_zero;failed→invalid|call_error;
    empty_success→empty_penalty;not_run→无选定行);
  * **空罚分哨兵只联合接受**:`"0"*64` payload_hash 仅当
    penalty_eligible_count==0 ∧ empty_success ∧ outcome 无 penalty payload 哈希
    ∧ verdict==empty_penalty 同时成立——绝不凭哈希单独接受;
  * evaluation **从封存记录重算**(`evaluate_news_horizon` 同一路径)逐字节比对
    ——M2⁴"不信封存计算值";硬失败决策 evaluation 必须为 None。
- **档案密封 + 账本链头外锚**(BINDING #6):`seal_decision_archive` 把
  决策档案(契约/工件/outcome/评估/记录/选定出处行)与**封印时的账本链头**一起
  全 SHA-256 密封,原子 fsync 写盘;`load_and_verify_decision_archive` 重验档案
  封印、重建 outcome(矩阵自验)、重跑联合验证、并要求**档案锚定的链头仍在当前
  账本链内**——整本重算替换会换掉全部 entry_hash,旧链头消失即抓获(账本 M1
  已知盲区的外锚闭合)。

archive-review(2B/1M)全数折叠:

- **B1 write-once**:档案按 decision 加锁 + first-write-wins;已有档案仅在重推导
  结果**完全相同**的幂等重试时返回,第二次(哪怕同样有效的)执行一律拒——
  "sealed" 语义不可覆盖。
- **B2 终态行↔腿↔记录全绑定**:选定行严格出处 schema + `row["leg"] == leg`;
  出处行携 canonical `parsed_record_hash`,封存记录逐条复算比对(records 与
  evaluation 联改死);records 形状按腿终态严格限制(硬失败=None,
  empty_penalty=确定性空记录逐字段);`deterministic_zero` 合法性从工件重新
  导出正向期望总体为空(双向:非空总体禁零终态)。
- **Major 读档身份**:顶层严格键集 + archive_schema 值 + 三向决策身份
  (档案==请求==工件束)+ bundle_hash/final_registry_hash 对工件重验;文件名
  = decision_id 的**完整逐字节** sha256(canon 折叠空白,不可入路径)。

archive-re-review#2(1B/2M)全数折叠:

- **B 出处终态不可自伪造**:公开 persist API 撤除(写入器模块私有、收实际
  raw/record 内算哈希、写时状态机:每 (execution, leg) 恰一 attempt/恰一终态,
  LLM 终态连着同 payload 的 attempt 行);受控执行器把选定终态 entry_hash +
  outcome_hash **承诺进决策账本哈希链**(首写胜出 per (decision, execution));
  归档验证不信 bundle 带入的行——从盘上按键解析**唯一状态机相连**终态
  (`_resolve_terminal`,>1 = 伪造追加 = 键失去可验证性 = 拒)、bundle 行必须
  逐字节等于盘上事实、且与账本承诺逐哈希相符(绕过写入器直接改写文件的替换行
  在承诺处死)。
- **M 嵌套严格**:`selected_provenance` 恰 {factor, penalty} 两键;档案
  outcome dict 必须逐字段等于重建 outcome 的规范载荷(别名字段死)。
- **M genesis 降级**:链头锚验改**无条件**成员检验——封印必然晚于决策入账+
  执行承诺,genesis 永不合法。

四席装配/scorecard 薄分发/链 bump 在下一单元;本单元零活链触碰。
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from workspace.research.ai_research_dept.engine.news_cards import (
    D7DecisionArtifact, verify_d7_artifact,
)
from workspace.research.ai_research_dept.engine.news_decision import (
    _ledger_path, _read_chain, build_leg_payload_ast, build_sealed_payload,
    find_execution_commitment, ledger_head, leg_expected_ids,
)
from workspace.research.ai_research_dept.engine.news_evidence import RegistryError
from workspace.research.ai_research_dept.engine.news_executors import (
    _EMPTY_PENALTY_RECORD, _LLM_TERMINALS, _TERMINAL_VERDICTS,
    NewsScoringContract, PROV_ROW_KEYS, _prov_lock, read_execution_provenance,
)
from workspace.research.ai_research_dept.engine.news_horizon import (
    deterministic_zero_factor_record, evaluate_news_horizon,
)
from workspace.research.ai_research_dept.engine.news_legs import (
    NewsLegOutcome, verify_outcome_for_binding,
)
from workspace.research.ai_research_dept.engine.news_seal import seal_hash, verify_sealed

_EMPTY_PENALTY_SENTINEL = "0" * 64
#: 腿终态 ↔ 选定出处 verdict 的语义一致表(BINDING #1)
_LEG_VERDICTS = {
    ("factor", "success"): {"valid", "deterministic_zero"},
    ("factor", "failed"): {"invalid", "call_error"},
    ("penalty", "success"): {"valid"},
    ("penalty", "failed"): {"invalid", "call_error"},
    ("penalty", "empty_success"): {"empty_penalty"},
}


def _rebuild_leg_payloads(artifact, outcome, *, ledger_dir):
    """canonical payload 确定性重建(同 AST + 同工件 → 同哈希)。penalty 只在
    实际执行过(success/failed)时存在。"""
    factor_payload = build_sealed_payload(
        build_leg_payload_ast(artifact, use="factor_positive", consumer_seat="news"),
        artifact, ledger_dir=ledger_dir, decision_id=outcome.decision_id,
        consumer_seat="news", use="factor_positive")
    penalty_payload = None
    if outcome.penalty_leg_status in ("success", "failed"):
        penalty_payload = build_sealed_payload(
            build_leg_payload_ast(artifact, use="penalty", consumer_seat="news"),
            artifact, ledger_dir=ledger_dir, decision_id=outcome.decision_id,
            consumer_seat="news", use="penalty")
    return factor_payload, penalty_payload


def _resolve_terminal(all_rows: list, *, execution_id: str, decision_id: str,
                      leg: str) -> dict:
    """从盘上出处文件按 (decision_id, execution_id, leg) 解析**唯一、状态机相连**
    的终态行(archive-re-review#2 Blocker:归档不信 bundle 带入的行——盘上多于
    一条终态 = 有人事后追加伪造行 → 整个键失去可验证性,fail-closed 拒)。"""
    key_rows = [r for r in all_rows if isinstance(r, dict)
                and r.get("execution_id") == execution_id
                and r.get("decision_id") == decision_id
                and r.get("leg") == leg]
    terminals = [r for r in key_rows if r.get("verdict") in _TERMINAL_VERDICTS]
    if len(terminals) != 1:
        raise RegistryError(
            f"({execution_id!r}, {leg}) 盘上终态行数 = {len(terminals)},须恰一"
            f"——0 = 未持久化;>1 = 出处被事后追加伪造终态,键失去可验证性,拒"
            f"(archive-re-review#2 Blocker)")
    row = terminals[0]
    attempts = [r for r in key_rows if r.get("verdict") == "attempt_started"]
    if row.get("verdict") in _LLM_TERMINALS:
        if len(attempts) != 1 \
                or attempts[0].get("payload_hash") != row.get("payload_hash"):
            raise RegistryError(
                f"({execution_id!r}, {leg}) LLM 终态未连着同 payload 的恰一 "
                f"attempt_started 行——状态机断裂,拒(archive-re-review#2)")
    elif attempts:
        raise RegistryError(
            f"({execution_id!r}, {leg}) 确定性终态却存在 attempt_started 行"
            f"——免 LLM 路径无尝试行,状态机断裂,拒(archive-re-review#2)")
    return row


def _verify_selected_row(row, *, leg: str, outcome: NewsLegOutcome,
                         execution_id: str, contract: NewsScoringContract,
                         leg_payload_hash: str, resolved: dict) -> None:
    """单条选定终态行的联合验证(BINDING #1 + archive-review B2 + re-review#2:
    bundle 行必须**逐字节等于**盘上解析出的唯一状态机终态——bundle 不再是行的
    权威来源,只是对盘上事实的引用)。"""
    if not isinstance(row, dict):
        raise RegistryError(f"{leg} 腿选定终态行缺失/非法——尝试过的腿必须恰一终态")
    if row != resolved:
        raise RegistryError(
            f"{leg} 腿选定终态行与盘上唯一状态机终态不符——bundle 携入的行不是"
            f"该执行的持久化事实,拒(archive-re-review#2 Blocker)")
    if set(row) != PROV_ROW_KEYS:
        raise RegistryError(
            f"{leg} 腿选定终态行键集不符出处行 schema(archive-review B2;"
            f"多/少键 {sorted(set(row) ^ PROV_ROW_KEYS)})")
    body = {k: v for k, v in row.items() if k != "entry_hash"}
    if seal_hash(body) != row.get("entry_hash"):
        raise RegistryError(f"{leg} 腿选定终态行 entry_hash 重算不符——行被改,拒")
    if row["leg"] != leg:
        raise RegistryError(
            f"{leg} 腿终态槽装的是 {row['leg']!r} 腿的出处行——终态行↔腿绑定违规"
            f"(archive-review B2)")
    if row["execution_id"] != execution_id or row["decision_id"] != outcome.decision_id:
        raise RegistryError(f"{leg} 腿选定终态行 execution/decision 身份不符")
    if row["schema_id"] != contract.schema_id:
        raise RegistryError(f"{leg} 腿选定终态行 schema_id 与冻结契约不符")
    status = getattr(outcome, f"{leg}_leg_status")
    allowed = _LEG_VERDICTS.get((leg, status))
    if allowed is None or row["verdict"] not in allowed:
        raise RegistryError(
            f"{leg} 腿终态 {status!r} 与选定 verdict {row['verdict']!r} 语义不符"
            f"(允许 {sorted(allowed) if allowed else '无'})")
    if row["payload_hash"] != leg_payload_hash:
        raise RegistryError(f"{leg} 腿选定终态行 payload_hash 与重建 payload 不符")


def _require_record_bound(record, row, *, leg: str, expect=None) -> None:
    """封存解析记录 ↔ 选定终态行的 parsed_record_hash 绑定(archive-review B2:
    records 与 evaluation 联改在此死)。expect 非 None 时记录还须逐字段等于该
    确定性记录(deterministic_zero / empty_penalty 的记录不是自由文本)。"""
    if not isinstance(record, dict):
        raise RegistryError(f"{leg} 腿封存记录须为 dict(得 {type(record).__name__})")
    if expect is not None and record != expect:
        raise RegistryError(f"{leg} 腿封存记录须逐字段等于确定性记录(archive-review B2)")
    if seal_hash(record) != row["parsed_record_hash"]:
        raise RegistryError(
            f"{leg} 腿封存记录 canonical 哈希与选定终态行 parsed_record_hash 不符"
            f"——记录被换,拒(archive-review B2)")


def verify_execution_bundle(bundle: dict, artifact: D7DecisionArtifact, *,
                            ledger_dir, prov_dir,
                            contract: NewsScoringContract) -> dict:
    """**封印前的联合验证**(BINDING #1)。全量重推导:工件过门 → canonical
    payload 重建 → outcome 绑定验证 → 每条选定终态行五向一致 + 盘上存在 +
    verdict 语义 → 空罚分哨兵**联合**接受 → evaluation 从封存记录重算。"""
    if not isinstance(contract, NewsScoringContract):
        raise RegistryError("联合验证必须提供冻结 NewsScoringContract")
    outcome = bundle["outcome"]
    if not isinstance(outcome, NewsLegOutcome):
        raise RegistryError("bundle.outcome 须为密封 NewsLegOutcome")
    execution_id = bundle["execution_id"]
    if type(execution_id) is not str or not execution_id.strip():
        raise RegistryError("bundle.execution_id 须为非空 str")
    verify_d7_artifact(artifact)
    factor_payload, penalty_payload = _rebuild_leg_payloads(
        artifact, outcome, ledger_dir=ledger_dir)
    verify_outcome_for_binding(outcome, artifact, factor_payload, penalty_payload,
                               ledger_dir=ledger_dir,
                               expected_output_mode=contract.output_mode)
    all_rows = read_execution_provenance(prov_dir)
    sel = bundle["selected_provenance"]
    # re-review#2 Major:嵌套对象严格键集——selected_provenance 恰两键
    if not isinstance(sel, dict) or set(sel) != {"factor", "penalty"}:
        raise RegistryError("selected_provenance 须为恰 {factor, penalty} 两键 dict"
                            "(archive-re-review#2 Major)")
    # records 严格形状(archive-review B2:硬失败携任意 JSON records 在此死)
    records = bundle.get("records")
    if not isinstance(records, dict) or set(records) != {"factor", "penalty"}:
        raise RegistryError("bundle.records 须为恰 {factor, penalty} 两键 dict"
                            "(archive-review B2)")
    # factor 腿:总被尝试(真实执行或确定性零路径)→ 盘上解析恰一状态机终态
    f_resolved = _resolve_terminal(all_rows, execution_id=execution_id,
                                   decision_id=outcome.decision_id, leg="factor")
    f_row = sel.get("factor")
    _verify_selected_row(f_row, leg="factor", outcome=outcome,
                         execution_id=execution_id, contract=contract,
                         leg_payload_hash=factor_payload.payload_hash,
                         resolved=f_resolved)
    if outcome.factor_leg_status == "success":
        # archive-review B2:deterministic_zero 合法性从工件**重新导出**——
        # 正向期望总体为空 ⟺ 确定性零(伪造零终态压掉真实证据在此死)
        factor_expected = leg_expected_ids(artifact.final_registry,
                                           use="factor_positive",
                                           consumer_seat="news")
        if factor_expected:
            if f_row["verdict"] != "valid":
                raise RegistryError(
                    "factor 正向期望总体非空,选定终态却是 "
                    f"{f_row['verdict']!r}——deterministic_zero 只在总体为空时合法"
                    "(archive-review B2)")
            _require_record_bound(records["factor"], f_row, leg="factor")
        else:
            if f_row["verdict"] != "deterministic_zero":
                raise RegistryError(
                    "factor 正向期望总体为空,选定终态必须是 deterministic_zero"
                    f"(得 {f_row['verdict']!r},archive-review B2)")
            _require_record_bound(records["factor"], f_row, leg="factor",
                                  expect=deterministic_zero_factor_record())
    else:
        if records["factor"] is not None:
            raise RegistryError("factor 腿硬失败不得携带封存记录(archive-review B2)")
    # penalty 腿:按终态分派
    p_status = outcome.penalty_leg_status
    if p_status == "not_run":
        if sel.get("penalty") is not None:
            raise RegistryError("penalty not_run 不得有选定终态行")
        if records["penalty"] is not None:
            raise RegistryError("penalty not_run 不得携带封存记录(archive-review B2)")
    elif p_status == "empty_success":
        row = sel.get("penalty")
        p_resolved = _resolve_terminal(all_rows, execution_id=execution_id,
                                       decision_id=outcome.decision_id,
                                       leg="penalty")
        _verify_selected_row(row, leg="penalty", outcome=outcome,
                             execution_id=execution_id, contract=contract,
                             leg_payload_hash=_EMPTY_PENALTY_SENTINEL,
                             resolved=p_resolved)
        # BINDING #1:哨兵只**联合**接受——绝不凭 "0"*64 单独放行
        if not (outcome.penalty_eligible_count == 0
                and outcome.penalty_payload_hash is None
                and row["verdict"] == "empty_penalty"
                and row["payload_hash"] == _EMPTY_PENALTY_SENTINEL):
            raise RegistryError(
                "空罚分哨兵联合验证失败:须 eligible==0 ∧ empty_success ∧ outcome 无 "
                "penalty payload 哈希 ∧ verdict==empty_penalty 同时成立(BINDING #1)")
        # archive-review B2:确定性空罚分记录逐字段 + 哈希绑定
        _require_record_bound(records["penalty"], row, leg="penalty",
                              expect=dict(_EMPTY_PENALTY_RECORD))
    else:                                          # success / failed:真实执行过
        p_row = sel.get("penalty")
        p_resolved = _resolve_terminal(all_rows, execution_id=execution_id,
                                       decision_id=outcome.decision_id,
                                       leg="penalty")
        _verify_selected_row(p_row, leg="penalty", outcome=outcome,
                             execution_id=execution_id, contract=contract,
                             leg_payload_hash=penalty_payload.payload_hash,
                             resolved=p_resolved)
        if p_status == "success":
            _require_record_bound(records["penalty"], p_row, leg="penalty")
        elif records["penalty"] is not None:
            raise RegistryError("penalty 腿硬失败不得携带封存记录(archive-review B2)")
    # evaluation 从封存记录重算(M2⁴ 不信封存计算值)
    if outcome.news_status == "success":
        recomputed = evaluate_news_horizon(
            records["factor"], records["penalty"], artifact.final_registry,
            output_mode=contract.output_mode,
            primary_decision_horizon=contract.primary_decision_horizon)
        if recomputed != bundle["evaluation"]:
            raise RegistryError(
                f"evaluation 重算不符:封存 {bundle['evaluation']} vs 重算 "
                f"{recomputed}——不信封存计算值(M2⁴)")
    else:
        if bundle.get("evaluation") is not None:
            raise RegistryError("硬失败决策不得携带 evaluation")
    # archive-re-review#2 Blocker:选定终态必须与**账本承诺**(不可重写哈希链)
    # 逐哈希相符——受控执行器在返回束前把终态 entry_hash 承诺进决策账本;
    # 直接改写出处文件(绕过写入器)替换的行不在承诺内,在此死
    commitment = find_execution_commitment(ledger_dir, outcome.decision_id,
                                           execution_id)
    if commitment is None:
        raise RegistryError(
            f"执行 ({outcome.decision_id!r}, {execution_id!r}) 无账本承诺——"
            f"受控执行器未提交/账本被换,拒(archive-re-review#2 Blocker)")
    p_sel = sel.get("penalty")
    if commitment["factor_entry_hash"] != f_row["entry_hash"] \
            or commitment["penalty_entry_hash"] != (p_sel["entry_hash"]
                                                    if p_sel else None) \
            or commitment["outcome_hash"] != outcome.outcome_hash:
        raise RegistryError(
            "选定终态/outcome 与账本承诺不符——出处文件被绕过写入器改写,拒"
            "(archive-re-review#2 Blocker)")
    return {"factor_payload_hash": factor_payload.payload_hash,
            "penalty_payload_hash": (penalty_payload.payload_hash
                                     if penalty_payload else None)}


_ARCHIVE_SCHEMA = "news_decision_archive_v1"
#: 档案顶层严格键集(archive-review Major:多/少键=拒)
_ARCHIVE_KEYS = frozenset({
    "archive_schema", "decision_id", "execution_id", "contract", "contract_hash",
    "artifact_hash", "bundle_hash", "final_registry_hash", "outcome",
    "outcome_hash", "evaluation", "records", "selected_provenance",
    "ledger_head_at_seal", "archive_sha256",
})


def _archive_path(archive_dir, decision_id: str) -> Path:
    """档案路径。文件名 = decision_id 的**完整逐字节** sha256(archive-review
    Major:seal_hash 的 canon 会折叠字符串空白——`"d A"` 与 `"d\\tA"` 是不同
    决策,必须落不同文件)。"""
    if type(decision_id) is not str or not decision_id:
        raise RegistryError(f"decision_id 须为非空 str(得 {decision_id!r})")
    digest = hashlib.sha256(decision_id.encode("utf-8")).hexdigest()
    return Path(archive_dir) / f"news_decision_{digest}.json"


def seal_decision_archive(bundle: dict, artifact: D7DecisionArtifact, *,
                          ledger_dir, prov_dir, contract: NewsScoringContract,
                          archive_dir) -> dict:
    """联合验证 → 密封决策档案(news 席切片)+ **账本链头外锚**(BINDING #6)。
    archive_sha256 = 全 SHA-256 over {契约/工件/outcome/评估/记录/选定出处行/
    封印时账本链头};原子 fsync 写盘。**write-once + first-write-wins**
    (archive-review B1):按 decision 加锁,已有档案仅在重推导档案**逐字节完全
    相同**的幂等重试时返回,任何不同(哪怕是第二次同样有效的执行)一律拒——
    "sealed" 绝不可被覆盖。"""
    verify_execution_bundle(bundle, artifact, ledger_dir=ledger_dir,
                            prov_dir=prov_dir, contract=contract)
    outcome: NewsLegOutcome = bundle["outcome"]
    payload = {
        "archive_schema": _ARCHIVE_SCHEMA,
        "decision_id": outcome.decision_id,
        "execution_id": bundle["execution_id"],
        "contract": contract._payload(),
        "contract_hash": contract.contract_hash,
        "artifact_hash": artifact.artifact_hash,
        "bundle_hash": artifact.bundle.bundle_hash,
        "final_registry_hash": artifact.final_registry.registry_hash,
        "outcome": outcome._payload(),
        "outcome_hash": outcome.outcome_hash,
        "evaluation": bundle["evaluation"],
        "records": bundle["records"],
        "selected_provenance": bundle["selected_provenance"],
        "ledger_head_at_seal": ledger_head(ledger_dir),
    }
    archive = {**payload, "archive_sha256": seal_hash(payload)}
    path = _archive_path(archive_dir, outcome.decision_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _prov_lock(path):                     # 按 decision 的档案锁(B1)
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing == archive:
                return existing                # 幂等重试:完全相同才放行
            raise RegistryError(
                f"决策 {outcome.decision_id!r} 已有密封档案且内容不同——档案 "
                f"write-once,first-write-wins,拒绝覆盖(archive-review B1;"
                f"已有 execution_id={existing.get('execution_id')!r} vs 新 "
                f"{bundle['execution_id']!r})")
        fd, tmp = tempfile.mkstemp(suffix=".json.tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(archive, f, ensure_ascii=False, allow_nan=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    return archive


def load_and_verify_decision_archive(decision_id: str, artifact: D7DecisionArtifact,
                                     *, ledger_dir, prov_dir,
                                     contract: NewsScoringContract,
                                     archive_dir) -> dict:
    """档案读取 + **全量重验**:档案封印重算 → outcome 从封存字段重建(矩阵自验)
    → 联合验证重跑(canonical 重建/选定行/哨兵/evaluation 重算)→ **链头锚验**:
    档案锚定的链头必须仍在当前账本链内(整本重算=旧链头消失=拒,BINDING #6)。"""
    path = _archive_path(archive_dir, decision_id)
    if not path.exists():
        raise RegistryError(f"决策档案缺失:{path}")
    archive = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(archive, dict) or set(archive) != _ARCHIVE_KEYS:
        raise RegistryError("档案顶层键集不符 news_decision_archive_v1 schema"
                            "(archive-review Major;多/少键=拒)")
    body = {k: v for k, v in archive.items() if k != "archive_sha256"}
    verify_sealed(body, archive.get("archive_sha256", ""),
                  field_name="archive_sha256")
    if archive["archive_schema"] != _ARCHIVE_SCHEMA:
        raise RegistryError(f"档案 archive_schema 须为 {_ARCHIVE_SCHEMA!r}"
                            f"(得 {archive['archive_schema']!r})")
    # archive-review Major:三向决策身份——档案 == 请求 == 工件束(d1 档案拷到
    # d2 文件名、或用错工件读档,均在此死)
    if not (archive["decision_id"] == decision_id
            == artifact.bundle.decision_id):
        raise RegistryError(
            f"决策身份三向不符:档案 {archive['decision_id']!r} / 请求 "
            f"{decision_id!r} / 工件束 {artifact.bundle.decision_id!r}"
            f"(archive-review Major)")
    if archive["contract_hash"] != contract.contract_hash \
            or archive["contract"] != contract._payload():
        raise RegistryError("档案契约与提供的冻结契约不符")
    if archive["artifact_hash"] != artifact.artifact_hash:
        raise RegistryError("档案工件哈希与提供的工件不符")
    if archive["bundle_hash"] != artifact.bundle.bundle_hash:
        raise RegistryError("档案 bundle_hash 与提供工件的证据束不符(archive-review Major)")
    if archive["final_registry_hash"] != artifact.final_registry.registry_hash:
        raise RegistryError("档案 final_registry_hash 与提供工件的注册表不符"
                            "(archive-review Major)")
    # outcome 从封存字段重建——NewsLegOutcome 构造即重跑 M3⁴ 矩阵自验
    o = archive["outcome"]
    outcome = NewsLegOutcome(
        decision_id=o["decision_id"], output_mode=o["output_mode"],
        factor_leg_status=o["factor_leg_status"],
        penalty_eligible_count=o["penalty_eligible_count"],
        penalty_eligible_set_hash=o["penalty_eligible_set_hash"],
        penalty_leg_status=o["penalty_leg_status"], news_status=o["news_status"],
        shadow_complete=o["shadow_complete"],
        decision_complete=o["decision_complete"],
        binding_eligible=o["binding_eligible"],
        factor_payload_hash=o["factor_payload_hash"],
        penalty_payload_hash=o["penalty_payload_hash"],
        outcome_hash=archive["outcome_hash"])
    # re-review#2 Major:嵌套严格——重建 outcome 的规范载荷必须逐字段等于封存
    # dict(别名/多余键在此死;NewsLegOutcome 构造只取具名字段,等式补上封闭性)
    if o != outcome._payload():
        raise RegistryError(
            "档案 outcome 载荷含未验证字段/与规范载荷不符——嵌套对象严格键集,拒"
            "(archive-re-review#2 Major)")
    bundle = {"execution_id": archive["execution_id"], "outcome": outcome,
              "evaluation": archive["evaluation"], "records": archive["records"],
              "selected_provenance": archive["selected_provenance"]}
    verify_execution_bundle(bundle, artifact, ledger_dir=ledger_dir,
                            prov_dir=prov_dir, contract=contract)
    # 链头锚验(BINDING #6 + re-review#2 Major:**无条件**成员检验——封印必然
    # 晚于决策入账+执行承诺,账本非空,genesis 在此永不合法;把锚改写为
    # "0"*64 再重封 = 降级攻击,在此死)
    anchored = archive["ledger_head_at_seal"]
    current_hashes = {e["entry_hash"] for e in _read_chain(_ledger_path(ledger_dir))}
    if anchored not in current_hashes:
        raise RegistryError(
            f"档案锚定链头 {str(anchored)[:12]!r} 不在当前账本链内——账本被整本"
            f"重算/替换或锚被降级为 genesis,拒(BINDING #6 外锚,re-review#2)")
    return archive
