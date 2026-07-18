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

archive-re-review#3(1B/1M)全数折叠:

- **P0 承诺权威**:公开裸哈希承诺 API 撤除——唯一门是
  [news_executors.commit_execution](news_executors.py)(不收任何哈希:自行
  重建 payload、验 outcome、从盘上解析唯一状态机终态并全量校验[共享
  `_check_terminal_row`],再把**自行解析出的**哈希经模块私有
  `_append_commitment_row` 入链);链级新不变量 **success 承诺每决策唯一**
  ——真实执行承诺 success 后,伪造的"全新执行"(评审的 `d1:api_forged_0001`
  探针)无法再提交第二条 success;归档要求承诺 news_status 与 outcome 相符,
  且硬失败束在 success 承诺存在时被**取代**(不可封/不可读)。
- **P1 祖先锚**:读档不再只验链头**成员性**——本执行的承诺行必须在以
  `ledger_head_at_seal` 为终点的祖先路径上(线性链 seq ≤);锚降级到承诺前
  的更早合法链成员(如决策注册行)= 拒。

archive-re-review#4(2×P1 + 崩溃变体)全数折叠:

- **P1-a 档案按执行独立不可变 + canonical-success 选择**:档案路径键 =
  (decision_id, execution_id)——失败档案永不堵死成功档案(不同文件,组合探针
  `hard_failed→seal→success→seal` 两份共存);哪份是**决策的** canonical 档案
  由账本**唯一 success 承诺**选定(`load_and_verify_decision_archive`),
  与文件封印先后无关;硬失败执行档案是该执行的不可变审计记录,走
  `load_and_verify_execution_archive` 按执行读取,不参与 canonical 选择
  (verify_execution_bundle 里的取代拒绝随之撤除——取代语义整体上移到
  决策级选择)。
- **P1-b 单快照读档**:决策级读取在**同一份** `_read_chain` 快照上完成
  canonical 选择 + 承诺相符 + 锚点成员/祖先校验(快照经 `chain` 参数贯穿
  `verify_execution_bundle`);canonical 规则使决策级读取在**任何交错**下都
  不可能返回 hard_failed 档案——TOCTOU 面结构性消除(payload 重建内部的
  账本门只触碰不可变的首写决策注册行,无竞争面)。
- **崩溃变体:success 承诺后可恢复封存**:出处行携完整 `parsed_record` 本体
  (与哈希同封在行 entry_hash 内);`recover_and_seal_success_archive` 从纯
  盘上状态重建执行束——终态解析对承诺逐哈希、记录取自行本体、outcome 经
  M3⁴ 矩阵重推导并对承诺 outcome_hash 验真、evaluation 重算——再走正常
  write-once 封印(已在且相同 = 幂等)。

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
    ledger_head,
)
from workspace.research.ai_research_dept.engine.news_evidence import RegistryError
from workspace.research.ai_research_dept.engine.news_executors import (
    _EMPTY_PENALTY_RECORD, _EMPTY_PENALTY_SENTINEL, _TERMINAL_VERDICTS,
    NewsScoringContract, _check_terminal_row, _prov_lock, _rebuild_leg_payloads,
    _resolve_terminal, read_execution_provenance,
)
from workspace.research.ai_research_dept.engine.news_horizon import (
    deterministic_zero_factor_record, evaluate_news_horizon,
)
from workspace.research.ai_research_dept.engine.news_legs import (
    NewsLegOutcome, _derive_terminal, _eligible_set_hash,
    penalty_eligible_records, verify_outcome_for_binding,
)
from workspace.research.ai_research_dept.engine.news_seal import seal_hash, verify_sealed


def _find_commitment(chain: list, decision_id: str,
                     execution_id: str) -> "dict | None":
    return next((e for e in chain if e["kind"] == "execution_commitment"
                 and e["decision_id"] == decision_id
                 and e["execution_id"] == execution_id), None)


def _find_success_commitment(chain: list, decision_id: str) -> "dict | None":
    return next((e for e in chain if e["kind"] == "execution_commitment"
                 and e["decision_id"] == decision_id
                 and e["news_status"] == "success"), None)

def _verify_selected_row(row, *, leg: str, outcome: NewsLegOutcome,
                         execution_id: str, contract: NewsScoringContract,
                         leg_payload_hash: str, resolved: dict,
                         artifact: D7DecisionArtifact) -> None:
    """单条选定终态行的联合验证(BINDING #1 + archive-review B2 + re-review#2:
    bundle 行必须**逐字节等于**盘上解析出的唯一状态机终态——bundle 不再是行的
    权威来源,只是对盘上事实的引用;全量行校验走与承诺权威**共享**的
    `_check_terminal_row`,两处语义永不分叉)。"""
    if not isinstance(row, dict):
        raise RegistryError(f"{leg} 腿选定终态行缺失/非法——尝试过的腿必须恰一终态")
    if row != resolved:
        raise RegistryError(
            f"{leg} 腿选定终态行与盘上唯一状态机终态不符——bundle 携入的行不是"
            f"该执行的持久化事实,拒(archive-re-review#2 Blocker)")
    _check_terminal_row(row, leg=leg, outcome=outcome, execution_id=execution_id,
                        contract=contract, leg_payload_hash=leg_payload_hash,
                        artifact=artifact)


def _require_record_bound(record, row, *, leg: str, expect=None) -> None:
    """封存解析记录 ↔ 选定终态行的绑定(archive-review B2 + re-review#4:
    records 与 evaluation 联改在此死)。行携完整 parsed_record 本体后,记录须
    **逐字节等于行本体**(canon 哈希折叠空白,单靠哈希不排除空白变体)+
    canonical 哈希绑定;expect 非 None 时还须逐字段等于该确定性记录。"""
    if not isinstance(record, dict):
        raise RegistryError(f"{leg} 腿封存记录须为 dict(得 {type(record).__name__})")
    if expect is not None and record != expect:
        raise RegistryError(f"{leg} 腿封存记录须逐字段等于确定性记录(archive-review B2)")
    if record != row["parsed_record"]:
        raise RegistryError(
            f"{leg} 腿封存记录与终态行封存的解析记录本体不符——记录被换,拒"
            f"(archive-review B2 + re-review#4)")
    if seal_hash(record) != row["parsed_record_hash"]:
        raise RegistryError(
            f"{leg} 腿封存记录 canonical 哈希与选定终态行 parsed_record_hash 不符"
            f"——记录被换,拒(archive-review B2)")


def verify_execution_bundle(bundle: dict, artifact: D7DecisionArtifact, *,
                            ledger_dir, prov_dir, contract: NewsScoringContract,
                            chain: "list | None" = None) -> dict:
    """**封印前的联合验证**(BINDING #1)。全量重推导:工件过门 → canonical
    payload 重建 → outcome 绑定验证 → 每条选定终态行五向一致 + 盘上存在 +
    verdict 语义 → 空罚分哨兵**联合**接受 → evaluation 从封存记录重算 →
    账本承诺逐哈希相符。`chain` 非 None = 调用方提供的**单次账本快照**
    (re-review#4 P1-b:读档的承诺/取代/锚点判定必须同一快照;payload 重建内部
    的账本门只触碰不可变的决策注册行,首写胜出使其无 TOCTOU 面)。canonical
    取代规则(success 承诺唯一 ⇒ 决策档案 = success 执行的档案)在
    `load_and_verify_decision_archive`,不在此。"""
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
                         resolved=f_resolved, artifact=artifact)
    if outcome.factor_leg_status == "success":
        # deterministic_zero ⟺ 总体为空已由共享 _check_terminal_row 双向重导出;
        # 此处按(已验证的)verdict 分派记录绑定的确定性期望
        if f_row["verdict"] == "deterministic_zero":
            _require_record_bound(records["factor"], f_row, leg="factor",
                                  expect=deterministic_zero_factor_record())
        else:
            _require_record_bound(records["factor"], f_row, leg="factor")
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
        stray = [r for r in all_rows if isinstance(r, dict)
                 and r.get("execution_id") == execution_id
                 and r.get("decision_id") == outcome.decision_id
                 and r.get("leg") == "penalty"
                 and r.get("verdict") in _TERMINAL_VERDICTS]
        if stray:
            raise RegistryError("penalty not_run 却存在盘上终态行——拒")
    elif p_status == "empty_success":
        row = sel.get("penalty")
        p_resolved = _resolve_terminal(all_rows, execution_id=execution_id,
                                       decision_id=outcome.decision_id,
                                       leg="penalty")
        _verify_selected_row(row, leg="penalty", outcome=outcome,
                             execution_id=execution_id, contract=contract,
                             leg_payload_hash=_EMPTY_PENALTY_SENTINEL,
                             resolved=p_resolved, artifact=artifact)
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
                             resolved=p_resolved, artifact=artifact)
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
    # 逐哈希相符——承诺权威在返回束前把终态 entry_hash 承诺进决策账本;
    # 直接改写出处文件(绕过写入器)替换的行不在承诺内,在此死
    entries = chain if chain is not None \
        else _read_chain(_ledger_path(ledger_dir))
    commitment = _find_commitment(entries, outcome.decision_id, execution_id)
    if commitment is None:
        raise RegistryError(
            f"执行 ({outcome.decision_id!r}, {execution_id!r}) 无账本承诺——"
            f"承诺权威未提交/账本被换,拒(archive-re-review#2 Blocker)")
    p_sel = sel.get("penalty")
    if commitment["factor_entry_hash"] != f_row["entry_hash"] \
            or commitment["penalty_entry_hash"] != (p_sel["entry_hash"]
                                                    if p_sel else None) \
            or commitment["outcome_hash"] != outcome.outcome_hash \
            or commitment["news_status"] != outcome.news_status:
        raise RegistryError(
            "选定终态/outcome 与账本承诺不符——出处文件被绕过写入器改写,拒"
            "(archive-re-review#2 Blocker)")
    return {"factor_payload_hash": factor_payload.payload_hash,
            "penalty_payload_hash": (penalty_payload.payload_hash
                                     if penalty_payload else None),
            "commitment": commitment}


_ARCHIVE_SCHEMA = "news_decision_archive_v1"
#: 档案顶层严格键集(archive-review Major:多/少键=拒)
_ARCHIVE_KEYS = frozenset({
    "archive_schema", "decision_id", "execution_id", "contract", "contract_hash",
    "artifact_hash", "bundle_hash", "final_registry_hash", "outcome",
    "outcome_hash", "evaluation", "records", "selected_provenance",
    "ledger_head_at_seal", "archive_sha256",
})


def _archive_path(archive_dir, decision_id: str, execution_id: str) -> Path:
    """档案路径——**每执行一份、各自不可变**(re-review#4 P1-a:失败档案不再
    堵死后续成功档案;哪份是决策的 canonical 档案由账本的唯一 success 承诺
    选定,不由文件先来后到)。文件名 = (decision_id, execution_id) JSON 对的
    **完整逐字节** sha256(JSON 编码定界无歧义;canon 折叠空白不可入路径)。"""
    if type(decision_id) is not str or not decision_id:
        raise RegistryError(f"decision_id 须为非空 str(得 {decision_id!r})")
    if type(execution_id) is not str or not execution_id:
        raise RegistryError(f"execution_id 须为非空 str(得 {execution_id!r})")
    digest = hashlib.sha256(json.dumps(
        [decision_id, execution_id],
        ensure_ascii=False).encode("utf-8")).hexdigest()
    return Path(archive_dir) / f"news_decision_{digest}.json"


def seal_decision_archive(bundle: dict, artifact: D7DecisionArtifact, *,
                          ledger_dir, prov_dir, contract: NewsScoringContract,
                          archive_dir) -> dict:
    """联合验证 → 密封**本执行**的档案(news 席切片)+ **账本链头外锚**
    (BINDING #6)。archive_sha256 = 全 SHA-256 over {契约/工件/outcome/评估/
    记录/选定出处行/封印时账本链头};原子 fsync 写盘。**write-once +
    first-write-wins per (decision, execution)**(archive-review B1 +
    re-review#4 P1-a):档案按执行独立不可变——已有档案仅在重推导档案**逐字节
    完全相同**的幂等重试时返回,任何不同一律拒;成功执行的封存永不被失败执行
    的档案堵死(不同文件)。"""
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
    path = _archive_path(archive_dir, outcome.decision_id, bundle["execution_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with _prov_lock(path):                     # 按 (decision, execution) 的档案锁
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing == archive:
                return existing                # 幂等重试:完全相同才放行
            raise RegistryError(
                f"执行 ({outcome.decision_id!r}, {bundle['execution_id']!r}) "
                f"已有密封档案且内容不同——档案 write-once,first-write-wins,"
                f"拒绝覆盖(archive-review B1)")
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


def _load_and_verify_archive_file(decision_id: str, execution_id: str,
                                  artifact: D7DecisionArtifact, *, ledger_dir,
                                  prov_dir, contract: NewsScoringContract,
                                  archive_dir, chain: list) -> dict:
    """单份执行档案的读取 + **全量重验**(共享核;`chain` = 调用方的单次账本
    快照,承诺/锚点判定全部基于它——re-review#4 P1-b):档案封印重算 → 身份
    (决策三向 + 执行)→ outcome 从封存字段重建(矩阵自验)→ 联合验证重跑
    (canonical 重建/选定行/哨兵/evaluation 重算/账本承诺)→ **链头锚验**
    (成员 + 祖先)。"""
    path = _archive_path(archive_dir, decision_id, execution_id)
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
    # d2 文件名、或用错工件读档,均在此死);re-review#4:执行身份同验
    if not (archive["decision_id"] == decision_id
            == artifact.bundle.decision_id):
        raise RegistryError(
            f"决策身份三向不符:档案 {archive['decision_id']!r} / 请求 "
            f"{decision_id!r} / 工件束 {artifact.bundle.decision_id!r}"
            f"(archive-review Major)")
    if archive["execution_id"] != execution_id:
        raise RegistryError(
            f"档案 execution_id {archive['execution_id']!r} ≠ 请求 "
            f"{execution_id!r}——执行身份不符(re-review#4)")
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
    verified = verify_execution_bundle(bundle, artifact, ledger_dir=ledger_dir,
                                       prov_dir=prov_dir, contract=contract,
                                       chain=chain)
    # 链头锚验(BINDING #6 + re-review#2 Major:**无条件**成员检验——封印必然
    # 晚于决策入账+执行承诺,账本非空,genesis 在此永不合法;把锚改写为
    # "0"*64 再重封 = 降级攻击,在此死)
    anchored = archive["ledger_head_at_seal"]
    anchored_row = next((e for e in chain if e["entry_hash"] == anchored), None)
    if anchored_row is None:
        raise RegistryError(
            f"档案锚定链头 {str(anchored)[:12]!r} 不在当前账本链内——账本被整本"
            f"重算/替换或锚被降级为 genesis,拒(BINDING #6 外锚,re-review#2)")
    # re-review#3 P1:成员性不够——本执行的承诺行必须在**以锚为终点的祖先路径**
    # 上(线性链上祖先 ⟺ seq ≤ 锚 seq)。把锚降级到承诺之前的更早合法链成员
    # (如该决策自己的注册行)= 档案声称"封印时链头"早于其自身承诺,矛盾,拒
    if verified["commitment"]["seq"] > anchored_row["seq"]:
        raise RegistryError(
            f"档案锚定链头 seq={anchored_row['seq']} 早于本执行的承诺行 "
            f"seq={verified['commitment']['seq']}——承诺不在锚的祖先路径上,"
            f"锚被降级到更早链成员,拒(re-review#3 P1)")
    return archive


def load_and_verify_execution_archive(decision_id: str, execution_id: str,
                                      artifact: D7DecisionArtifact, *,
                                      ledger_dir, prov_dir,
                                      contract: NewsScoringContract,
                                      archive_dir) -> dict:
    """**按执行**审计读取(re-review#4 P1-a):一份执行档案是该执行的不可变
    记录,永久可验证——包括被后续 success 取代的硬失败执行(取代只作用于
    决策级 canonical 选择,不作用于执行级审计)。单次账本快照。"""
    chain = _read_chain(_ledger_path(ledger_dir))
    return _load_and_verify_archive_file(
        decision_id, execution_id, artifact, ledger_dir=ledger_dir,
        prov_dir=prov_dir, contract=contract, archive_dir=archive_dir,
        chain=chain)


def load_and_verify_decision_archive(decision_id: str, artifact: D7DecisionArtifact,
                                     *, ledger_dir, prov_dir,
                                     contract: NewsScoringContract,
                                     archive_dir) -> dict:
    """**决策级 canonical 读取**(re-review#4 P1-a/b):在**同一份账本快照**上
    完成 canonical 选择 + 承诺/取代判定 + 锚点校验——决策的 canonical 档案 =
    账本**唯一 success 承诺**指定的那个执行的档案,与文件封印先后无关。
    快照无 success 承诺(纯硬失败/未执行)= 决策无 canonical 档案,拒
    (硬失败执行档案走 `load_and_verify_execution_archive` 按执行审计读);
    success 承诺在而档案缺 = 承诺后崩溃,走
    `recover_and_seal_success_archive` 从盘上重建。任何交错下本函数都不可能
    返回 hard_failed 档案(P1-b 的 TOCTOU 面结构性消除)。"""
    chain = _read_chain(_ledger_path(ledger_dir))
    success = _find_success_commitment(chain, decision_id)
    if success is None:
        raise RegistryError(
            f"决策 {decision_id!r} 无 success 执行承诺——无 canonical 决策档案"
            f"(硬失败执行档案请经 load_and_verify_execution_archive 按执行"
            f"审计读取,re-review#4 P1-a)")
    return _load_and_verify_archive_file(
        decision_id, success["execution_id"], artifact, ledger_dir=ledger_dir,
        prov_dir=prov_dir, contract=contract, archive_dir=archive_dir,
        chain=chain)


def recover_and_seal_success_archive(decision_id: str,
                                     artifact: D7DecisionArtifact, *,
                                     ledger_dir, prov_dir,
                                     contract: NewsScoringContract,
                                     archive_dir) -> dict:
    """**success 承诺后的可恢复封存**(re-review#4 崩溃变体):承诺已入链、
    进程在封档前崩溃 → 从**纯盘上状态**重建执行束并走正常封印。重建全程
    verify-not-trust:终态从出处解析(唯一+状态机)且 entry_hash 必须等于
    账本承诺;解析记录取自终态行封存本体(哈希绑定在行封印内);outcome 从
    (工件+契约+终态 verdict)经 M3⁴ 矩阵**重推导**,其 outcome_hash 必须等于
    承诺的 outcome_hash(权威锚);evaluation 确定性重算。随后
    `seal_decision_archive` 重跑全量联合验证 + write-once(档案已在且逐字节
    相同 = 幂等返回)。"""
    if not isinstance(contract, NewsScoringContract):
        raise RegistryError("恢复封存必须提供冻结 NewsScoringContract")
    chain = _read_chain(_ledger_path(ledger_dir))
    success = _find_success_commitment(chain, decision_id)
    if success is None:
        raise RegistryError(
            f"决策 {decision_id!r} 无 success 执行承诺——无可恢复的封存"
            f"(re-review#4)")
    execution_id = success["execution_id"]
    all_rows = read_execution_provenance(prov_dir)
    f_row = _resolve_terminal(all_rows, execution_id=execution_id,
                              decision_id=decision_id, leg="factor")
    if f_row["entry_hash"] != success["factor_entry_hash"]:
        raise RegistryError("恢复:factor 终态与账本承诺不符——拒")
    if f_row["verdict"] not in ("valid", "deterministic_zero"):
        raise RegistryError(
            f"恢复:success 承诺的 factor 终态 verdict {f_row['verdict']!r} 非法")
    if success["penalty_entry_hash"] is None:
        raise RegistryError("恢复:success 承诺缺 penalty 终态——非法承诺,拒")
    p_row = _resolve_terminal(all_rows, execution_id=execution_id,
                              decision_id=decision_id, leg="penalty")
    if p_row["entry_hash"] != success["penalty_entry_hash"]:
        raise RegistryError("恢复:penalty 终态与账本承诺不符——拒")
    if p_row["verdict"] == "empty_penalty":
        p_status = "empty_success"
    elif p_row["verdict"] == "valid":
        p_status = "success"
    else:
        raise RegistryError(
            f"恢复:success 承诺的 penalty 终态 verdict {p_row['verdict']!r} 非法")
    records = {}
    for leg, row in (("factor", f_row), ("penalty", p_row)):
        rec = row["parsed_record"]
        if type(rec) is not dict or seal_hash(rec) != row["parsed_record_hash"]:
            raise RegistryError(f"恢复:{leg} 终态行封存记录哈希绑定不符——拒")
        records[leg] = rec
    factor_payload = build_sealed_payload(
        build_leg_payload_ast(artifact, use="factor_positive",
                              consumer_seat="news"),
        artifact, ledger_dir=ledger_dir, decision_id=decision_id,
        consumer_seat="news", use="factor_positive")
    penalty_payload = None
    if p_status == "success":
        penalty_payload = build_sealed_payload(
            build_leg_payload_ast(artifact, use="penalty", consumer_seat="news"),
            artifact, ledger_dir=ledger_dir, decision_id=decision_id,
            consumer_seat="news", use="penalty")
    eligible = penalty_eligible_records(artifact)
    derived = _derive_terminal("success", len(eligible), p_status,
                               contract.output_mode)
    outcome = NewsLegOutcome(
        decision_id=decision_id, output_mode=contract.output_mode,
        factor_leg_status="success", penalty_eligible_count=len(eligible),
        penalty_eligible_set_hash=_eligible_set_hash(eligible),
        penalty_leg_status=p_status, news_status=derived["news_status"],
        shadow_complete=derived["shadow_complete"],
        decision_complete=derived["decision_complete"],
        binding_eligible=derived["binding_eligible"],
        factor_payload_hash=factor_payload.payload_hash,
        penalty_payload_hash=(penalty_payload.payload_hash
                              if penalty_payload else None))
    if outcome.outcome_hash != success["outcome_hash"]:
        raise RegistryError(
            "恢复:重建 outcome 与账本承诺的 outcome_hash 不符——工件/契约与"
            "承诺时不一致,拒(re-review#4)")
    evaluation = evaluate_news_horizon(
        records["factor"], records["penalty"], artifact.final_registry,
        output_mode=contract.output_mode,
        primary_decision_horizon=contract.primary_decision_horizon)
    bundle = {"execution_id": execution_id, "outcome": outcome,
              "evaluation": evaluation, "records": records,
              "selected_provenance": {"factor": f_row, "penalty": p_row}}
    return seal_decision_archive(bundle, artifact, ledger_dir=ledger_dir,
                                 prov_dir=prov_dir, contract=contract,
                                 archive_dir=archive_dir)
