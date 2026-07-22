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

archive-re-review#5(1×P0 + 1×P2)全数折叠:

- **P0 契约绑定进承诺**:`outcome_hash` 不含 `primary_decision_horizon`——
  承诺此前不绑契约,同 schema/同 mode/不同主评分周期的契约可在封存或恢复时
  合法替换主评分结果并永久占用该执行的档案位。现在承诺行内嵌**完整不可变
  契约载荷 + contract_hash**(链读验对自洽),`verify_execution_bundle`
  (=封存与两个读取共用)与恢复预检一律要求提供契约与承诺**逐字节**相符,
  在写任何文件前拒。
- **P2 恢复真幂等**:档案已在 → 恢复直接读验返回既有档案(账本此后合法
  增长不再触发 write-once 拒);仅档案缺失才重建封存。
- 四席集成约定(评审建议,记入 NF_SEAL_HARDENING):决策级消费者只准调
  `load_and_verify_decision_archive`;`load_and_verify_execution_archive`
  仅审计展示(scope=execution_audit)。

archive-re-review#6(1×P0 + 1×P2)全数折叠:

- **P0 虚方法脱钩**:`isinstance` 收子类 + 跨边界调用可覆写的 `_payload()`
  ——恶意但合法的 NewsScoringContract 子类可使承诺/档案载荷(覆写值)与
  evaluator 实际读取的字段脱钩,封出自相矛盾档案。现在:**所有门恰类型**
  (`require_exact_contract` / `type(outcome) is NewsLegOutcome`——runner、
  `commit_execution`、`verify_execution_bundle`、恢复、`verify_outcome_for_binding`),
  且安全边界上的载荷一律经**模块级不可覆写 canonical helper**
  (`contract_canonical_payload` / `outcome_canonical_payload`)从实际字段
  构造,绝不经虚方法。子类在任何 provenance/承诺/档案写入之前被拒。
- **P2 恢复并发竞争**:write-once 冲突类型化为
  `ArchiveWriteOnceConflictError`;恢复输掉竞争(入口查无档案 → 对手封存 →
  账本合法增长 → 本次重建锚更晚 → 冲突)时**转为读验既有档案返回**,
  不再报错——所有合法顺序下恢复幂等。

archive-re-review#7(1×P0 + 1×P2)全数折叠:

- **P0 工件族同类脱钩**:虚方法脱钩(#6 已修 contract/outcome)的同类面上移
  到 **D7 工件族**——`D7DecisionArtifact`/`RenderedCard`/`AttributeBundle`/
  `SealedCardRegistry`/`D7BaseFact`/`AttributeRow` 的子类可覆写 `_payload()`
  带伪造哈希过 `verify_d7_artifact`,封出伪造 `artifact_hash`/`registry_hash`。
  修复在 [news_cards.py](news_cards.py) `verify_d7_artifact` + [news_evidence.py](news_evidence.py)
  `require_sealed_registry`:全部组件**恰类型**(子类拒),边界哈希一律经
  **模块级 canonical helper**(`*_canonical_payload`)从真实字段重算,绝不
  调用虚方法。
- **P2 恢复"档案已存在"分支用新快照**:该分支改调
  `load_and_verify_execution_archive`(自取新账本快照)——恢复入口的旧快照
  遇竞争者合法增长后的新锚会误拒有效档案(re-review#6 未覆盖的顺序)。

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
from workspace.research.ai_research_dept.engine.news_evidence import (
    RegistryError, require_sealed_registry,
)
from workspace.research.ai_research_dept.engine.news_executors import (
    _EMPTY_PENALTY_RECORD, _EMPTY_PENALTY_SENTINEL, _TERMINAL_VERDICTS,
    NewsScoringContract, _check_terminal_row, _prov_lock, _rebuild_leg_payloads,
    _resolve_terminal, contract_canonical_payload, read_execution_provenance,
    require_exact_contract, snapshot_exact_contract,
)
from workspace.research.ai_research_dept.engine.news_horizon import (
    deterministic_zero_factor_record, evaluate_news_horizon,
)
from workspace.research.ai_research_dept.engine.news_legs import (
    NewsLegOutcome, _derive_terminal, _eligible_set_hash,
    assert_base_outcome_fields, outcome_canonical_payload,
    penalty_eligible_records, snapshot_exact_outcome, verify_outcome_for_binding,
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

def _deep_plain_json(x, *, path: str = "bundle"):
    """递归验证**精确基础 JSON 类型**并重建为普通结构(archive-re-review#20:
    `json.dumps` 会调 dict/list **子类**的 `.items()`/迭代——不是"不运行调用方
    代码"的纯化手段;状态化 `.items()` 在连续两次序列化间可改写可信磁盘行。故
    在**读磁盘/解析 resolved 之前**就把调用方 bundle/selected_provenance/records/
    evaluation 递归拍成普通快照:每层**恰类型门先于任何容器访问**(`type(x) is
    dict/list`,子类拒),只用内建 `dict.items` 迭代,之后只用快照——调用方容器
    代码再无触发点)。"""
    # re-review#21 P1:**全 `is` 身份判断**——`type(x) in (...)` 用 `==`,说谎的
    # 元类可令 `type(x) == str` 返真把任意容器当标量放行;`is` 比对类型对象身份,
    # 元类 __eq__ 无从干预。错误信息也**不读不可信类型的 `.__name__`**(同触发
    # 元类 __getattr__ 回调)。
    t = type(x)
    if x is None or t is bool or t is int or t is float or t is str:
        return x
    if t is list:
        return [_deep_plain_json(v, path=f"{path}[{i}]") for i, v in enumerate(x)]
    if t is dict:
        out = {}
        for k, v in x.items():                 # 恰 dict → 内建 items,无覆写
            if type(k) is not str:
                raise RegistryError(f"{path} 键须恰 str——拒(re-review#21)")
            out[k] = _deep_plain_json(v, path=f"{path}.{k}")
        return out
    raise RegistryError(
        f"{path} 含非纯 JSON 类型——bundle 须为精确基础 JSON(dict/list/str/int/"
        f"float/bool/None;子类/自定义对象/说谎元类拒,re-review#20/#21;不读不可信"
        f" __name__)")


def _canon_json(x) -> str:
    """canonical JSON 串(archive-re-review#19/#20:比较调用方对象**绝不用
    `!=`/`==`**——那会把可信对象本体传进对方 `__ne__`/`__eq__`;且 `json.dumps`
    对**子类**会调其 `.items()`。故 `_canon_json` 只作用于已 `_deep_plain_json`
    拍平的**普通** dict/资料 —— 此时序列化确定性、无调用方代码)。"""
    return json.dumps(x, sort_keys=True, ensure_ascii=False, allow_nan=False)


def _verify_selected_row(row, *, leg: str, outcome: NewsLegOutcome,
                         execution_id: str, contract: NewsScoringContract,
                         leg_payload_hash: str, resolved: dict,
                         artifact: D7DecisionArtifact, final_registry=None) -> None:
    """单条选定终态行的联合验证(BINDING #1 + archive-review B2 + re-review#2/#19)。
    调用方 `row` 只作**对盘上事实的引用**——经 canonical JSON 串**逐字节**比对
    (re-review#19:**绝不 `row != resolved`**——那会把可信 `resolved` 传进
    调用方 row 的 `__ne__`,dict 子类可原地改写 `resolved["parsed_record"]` 毒化
    档案);比对通过后,全量行校验对 **`resolved`(盘上权威)** 跑,绝不再碰
    调用方 `row`。re-review#18 点4:`final_registry` 冻结快照透传。"""
    if not isinstance(row, dict):
        raise RegistryError(f"{leg} 腿选定终态行缺失/非法——尝试过的腿必须恰一终态")
    try:
        row_json = _canon_json(row)
    except (TypeError, ValueError):
        raise RegistryError(
            f"{leg} 腿选定终态行含非纯 JSON 值(带魔术方法的对象)——拒(re-review#19)")
    if row_json != _canon_json(resolved):
        raise RegistryError(
            f"{leg} 腿选定终态行与盘上唯一状态机终态不符——bundle 携入的行不是"
            f"该执行的持久化事实,拒(archive-re-review#2 Blocker)")
    # 全量校验对**盘上 resolved**跑(不碰调用方 row)——re-review#19
    _check_terminal_row(resolved, leg=leg, outcome=outcome, execution_id=execution_id,
                        contract=contract, leg_payload_hash=leg_payload_hash,
                        artifact=artifact, final_registry=final_registry)


def _require_record_bound(record, row, *, leg: str, expect=None) -> None:
    """封存解析记录 ↔ 选定终态行的绑定(archive-review B2 + re-review#4/#19)。
    `record` 是调用方 records(sanity 校验用)、`row` 是**盘上 resolved 行**。
    re-review#19:一律用 **canonical JSON 串**比对——`record != ...` 会把可信对象
    传进调用方 record 的 `__ne__`;非纯 JSON record 在此拒。档案实际用的是
    `row["parsed_record"]`(盘上),本函数只确保调用方 records 与之相符。"""
    if not isinstance(record, dict):
        raise RegistryError(f"{leg} 腿封存记录须为 dict(re-review#21 静态错误)")
    try:
        rec_json = _canon_json(record)
    except (TypeError, ValueError):
        raise RegistryError(f"{leg} 腿封存记录含非纯 JSON 值——拒(re-review#19)")
    if expect is not None and rec_json != _canon_json(expect):
        raise RegistryError(f"{leg} 腿封存记录须逐字段等于确定性记录(archive-review B2)")
    if rec_json != _canon_json(row["parsed_record"]):
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
    # re-review#20 P1:**入口即把 bundle 的 JSON 部分递归拍成普通快照**——`bundle`
    # 须恰 dict;outcome 是密封对象另处;其余(execution_id/selected_provenance/
    # records/evaluation)经 `_deep_plain_json` 恰类型深拷成普通结构,之后调用方
    # 容器代码(`.get`/`.items`/`__getitem__`/状态化迭代)再无触发点,`_canon_json`
    # 与 `seal_hash` 的连续序列化只作用于普通 dict。
    if type(bundle) is not dict:
        # re-review#21 P1:错误信息**静态**——`{type(bundle).__name__}` 会在抛异常
        # 前触发不可信对象的元类 __getattribute__(拒绝路径也不得跑调用方代码)
        raise RegistryError("bundle 须恰 dict(子类/自定义对象拒,re-review#20/#21)")
    # GPT #24 P1#2(类5):**恰 dict 仍不安全**——它可含非 str 键;若某恶意键的
    # __hash__ 碰撞 hash("outcome"),内建 `bundle["outcome"]` 查槽时会调该键的
    # __eq__(调用方代码,先于任何键类型检查)。故在**任何 bundle[...] /
    # bundle.get(...) 之前**先遍历键做恰 str 门:恰 dict 的 __iter__ 是内建,
    # 只产出键对象而不调其 __hash__/__eq__;`type(k) is str` 亦不跑调用方代码。
    for _k in bundle:
        if type(_k) is not str:
            raise RegistryError(
                "bundle 键须恰 str——非 str 键的 __hash__/__eq__ 是调用方代码,"
                "拒(GPT #24 P1#2 类5;静态错误)")
    # GPT #23 P1 同类面:contract/outcome 在**任何回调点之前**重建为独立快照——
    # 验证过的 live 对象仍可被后续 registry `.items()` 回调经 object.__setattr__
    # 改写(output_mode 换带 __repr__ 的对象、penalty_leg_status 换带 __eq__ 的
    # 对象),之后的读取/比较/传参就在执行调用方代码。此后全程只用快照。
    contract = snapshot_exact_contract(contract)       # re-review#6 P0 + GPT #23
    # re-review#16 P1:契约 canonical 载荷 + hash **验证后立即捕获**进本地(冻进
    # verified 快照)——seal 此后绝不回读 live contract/artifact,污染无处施展
    v_contract_payload = contract_canonical_payload(contract)
    v_contract_hash = contract.contract_hash
    outcome = bundle["outcome"]                         # 密封对象,恰类型 + 断言
    if type(outcome) is not NewsLegOutcome:
        # re-review#21 P1:静态错误(不读不可信 outcome 的 type().__name__)
        raise RegistryError(
            "bundle.outcome 须为恰 NewsLegOutcome——子类可覆写 _payload 脱钩,拒"
            "(re-review#6 P0 同类面)")
    outcome = snapshot_exact_outcome(outcome)          # 含 assert(re-review#15/GPT #23)
    # 调用方 JSON 部分一次性深拍普通快照(下游只用它,绝不再碰 live bundle)
    execution_id = _deep_plain_json(bundle.get("execution_id"),
                                    path="bundle.execution_id")
    if type(execution_id) is not str or not execution_id.strip():
        raise RegistryError("bundle.execution_id 须为非空 str")
    sel = _deep_plain_json(bundle.get("selected_provenance"),
                           path="bundle.selected_provenance")
    records = _deep_plain_json(bundle.get("records"), path="bundle.records")
    bundle_eval = _deep_plain_json(bundle.get("evaluation"),
                                   path="bundle.evaluation")
    # re-review#21 P1:可选 `chain` 也是调用方可注入结构——恶意 list 子类的
    # `__iter__` 在迭代查承诺时可改写已验证记录。入口即递归精确类型深拍成普通
    # list;None 时下面自 `_read_chain`(其输出即普通 dict)。
    if chain is not None:
        chain = _deep_plain_json(chain, path="chain")
    # GPT #23 P1#1:**绑定 verify_d7_artifact 返回的独立可信副本**——旧代码丢弃
    # 返回值继续读 live artifact,其内部的 registry `.items()` 回调可把
    # live `artifact.bundle` 换成带属性钩子的对象再恢复,封档时 EvilBundle 的
    # bundle_hash 访问器已被执行。此后全部 artifact 读取/传参都是可信副本。
    artifact = verify_d7_artifact(artifact)
    v_artifact_hash = artifact.artifact_hash           # re-review#16:验证后即捕获
    v_bundle_hash = artifact.bundle.bundle_hash
    v_final_registry_hash = artifact.final_registry.registry_hash
    # re-review#17 P1:立即冻结**实际算分用的 registry 快照**(不只 hash)——
    # 否则调用方 evaluation 比较处(bundle["evaluation"].__ne__)可回调把
    # artifact.final_registry 换成另一份自洽但算分不同的 registry,trusted_eval
    # 用 live registry 算出错分却写进带原 hash 的档案。此后 evaluation 只用它。
    v_final_registry = require_sealed_registry(artifact.final_registry)
    factor_payload, penalty_payload = _rebuild_leg_payloads(
        artifact, outcome, ledger_dir=ledger_dir)
    verify_outcome_for_binding(outcome, artifact, factor_payload, penalty_payload,
                               ledger_dir=ledger_dir,
                               expected_output_mode=contract.output_mode)
    all_rows = read_execution_provenance(prov_dir)
    # re-review#2/#20:sel/records 已是**普通快照**(入口深拍);严格键集
    if set(sel) != {"factor", "penalty"}:              # 普通 dict,内建 set
        raise RegistryError("selected_provenance 须为恰 {factor, penalty} 两键 dict"
                            "(archive-re-review#2 Major)")
    if set(records) != {"factor", "penalty"}:
        raise RegistryError("bundle.records 须为恰 {factor, penalty} 两键 dict"
                            "(archive-review B2)")
    # factor 腿:总被尝试(真实执行或确定性零路径)→ 盘上解析恰一状态机终态
    f_resolved = _resolve_terminal(all_rows, execution_id=execution_id,
                                   decision_id=outcome.decision_id, leg="factor")
    f_row = sel["factor"]                               # 普通快照,内建取值
    _verify_selected_row(f_row, leg="factor", outcome=outcome,
                         execution_id=execution_id, contract=contract,
                         leg_payload_hash=factor_payload.payload_hash,
                         resolved=f_resolved, artifact=artifact,
                         final_registry=v_final_registry)   # re-review#18 点4
    if outcome.factor_leg_status == "success":
        # re-review#19:一律用**盘上 f_resolved**,绝不读调用方 f_row(dict 子类
        # 的 __getitem__ 可每次返回不同值)
        if f_resolved["verdict"] == "deterministic_zero":
            _require_record_bound(records["factor"], f_resolved, leg="factor",
                                  expect=deterministic_zero_factor_record())
        else:
            _require_record_bound(records["factor"], f_resolved, leg="factor")
    else:
        if records["factor"] is not None:
            raise RegistryError("factor 腿硬失败不得携带封存记录(archive-review B2)")
    # penalty 腿:按终态分派
    p_status = outcome.penalty_leg_status
    p_selected = None                                  # re-review#15:快照选定 penalty 行
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
        p_selected = p_resolved                        # re-review#15
        # BINDING #1:哨兵只**联合**接受——绝不凭 "0"*64 单独放行(re-review#19:
        # 读盘上 p_resolved,不读调用方 row)
        if not (outcome.penalty_eligible_count == 0
                and outcome.penalty_payload_hash is None
                and p_resolved["verdict"] == "empty_penalty"
                and p_resolved["payload_hash"] == _EMPTY_PENALTY_SENTINEL):
            raise RegistryError(
                "空罚分哨兵联合验证失败:须 eligible==0 ∧ empty_success ∧ outcome 无 "
                "penalty payload 哈希 ∧ verdict==empty_penalty 同时成立(BINDING #1)")
        # archive-review B2:确定性空罚分记录逐字段 + 哈希绑定
        _require_record_bound(records["penalty"], p_resolved, leg="penalty",
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
        p_selected = p_resolved                        # re-review#15
        if p_status == "success":
            _require_record_bound(records["penalty"], p_resolved, leg="penalty")
        elif records["penalty"] is not None:
            raise RegistryError("penalty 腿硬失败不得携带封存记录(archive-review B2)")
    # re-review#17 P1:先从**磁盘解析行**建可信 records + **冻结 registry 快照**算出
    # trusted_eval,再去比对调用方 evaluation——可信值在任何 bundle 回调之前算完,
    # 后续无论 artifact.final_registry 被怎样调包都不影响已定稿的 trusted_eval。
    trusted_records = {
        "factor": (f_resolved["parsed_record"]
                   if outcome.factor_leg_status == "success" else None),
        "penalty": (p_selected["parsed_record"]
                    if p_status in ("success", "empty_success") else None),
    }
    trusted_eval = None
    if outcome.news_status == "success":
        trusted_eval = evaluate_news_horizon(
            trusted_records["factor"], trusted_records["penalty"],
            v_final_registry, output_mode=v_contract_payload["output_mode"],
            primary_decision_horizon=v_contract_payload["primary_decision_horizon"])
        # re-review#18 P1:**算完立即冻结成独立 JSON 拷贝**——否则下面的 sanity
        # 比对 `trusted_eval != bundle["evaluation"]` 会把 trusted_eval **本体**
        # 传进调用方对象的 `__ne__`(当其令 dict.__ne__ 返回 NotImplemented 时),
        # 可被原地改成错分再入档。冻结后档案用的是这份不可被回调触及的拷贝。
        trusted_eval = json.loads(json.dumps(trusted_eval, ensure_ascii=False,
                                             allow_nan=False))
        # 调用方 evaluation(已是普通快照 bundle_eval)仅作 sanity 比对:**恰 dict
        # 门 + canonical JSON 串比**(bundle 值永不入档;快照后无回调面)
        if type(bundle_eval) is not dict:
            raise RegistryError("bundle.evaluation 须恰 dict(re-review#18 P1)")
        if _canon_json(trusted_eval) != _canon_json(bundle_eval):
            raise RegistryError(
                f"evaluation 重算不符:封存 {bundle_eval} vs 重算 {trusted_eval}"
                f"——不信封存计算值(M2⁴)")
    else:
        if bundle_eval is not None:
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
    # re-review#16:全部用**磁盘解析行** f_resolved/p_selected(非调用方 f_row/
    # sel)+ **已捕获**的 v_contract_*,不再回读 live 输入
    if commitment["factor_entry_hash"] != f_resolved["entry_hash"] \
            or commitment["penalty_entry_hash"] != (p_selected["entry_hash"]
                                                    if p_selected else None) \
            or commitment["outcome_hash"] != outcome.outcome_hash \
            or commitment["news_status"] != outcome.news_status:
        raise RegistryError(
            "选定终态/outcome 与账本承诺不符——出处文件被绕过写入器改写,拒"
            "(archive-re-review#2 Blocker)")
    if commitment["contract_hash"] != v_contract_hash \
            or commitment["contract"] != v_contract_payload:
        # re-review#5 P0:outcome_hash 不含 primary_decision_horizon——契约不
        # 绑进承诺,同 schema/同 mode/不同主评分周期的契约就能在封存/恢复时
        # 合法替换主评分结果。封存与读取一律要求契约与承诺**逐字节**相符
        raise RegistryError(
            f"契约与账本承诺不符(承诺 {commitment['contract']} vs 提供 "
            f"{v_contract_payload})——主评分周期等契约字段不可替换,拒(re-review#5 P0)")
    # re-review#16 P1:产出**完全独立、类型闭合的 verified 归档载荷**——归档
    # 序列化只消费它,seal 此后绝不回读 live bundle/contract/artifact。
    # - outcome 已在**入口**经 snapshot_exact_outcome 重建为独立快照
    #   (GPT #23:与 bundle["outcome"] 解除别名且先于一切回调点),直接作
    #   verified_outcome;
    # - records / selected_provenance 只由**磁盘解析终态行**(f_resolved/
    #   p_selected)构造,不取调用方 f_row/sel/bundle["records"];
    # - evaluation 基于该可信 records 重算;contract/artifact hash 用已捕获值;
    # - 整体经 JSON 深拷贝彻底解除别名(回调篡改的 live 输入到不了盘)。
    verified_outcome = outcome
    # re-review#17:trusted_records / trusted_eval 已在 evaluation 段用**冻结
    # registry 快照**在任何回调之前算好——此处直接复用,不再触碰 live artifact
    verified_payload = {
        "archive_schema": _ARCHIVE_SCHEMA,
        "decision_id": verified_outcome.decision_id,
        "execution_id": execution_id,
        "contract": v_contract_payload,
        "contract_hash": v_contract_hash,
        "artifact_hash": v_artifact_hash,
        "bundle_hash": v_bundle_hash,
        "final_registry_hash": v_final_registry_hash,
        "outcome": outcome_canonical_payload(verified_outcome),
        "outcome_hash": verified_outcome.outcome_hash,
        "evaluation": trusted_eval,
        "records": trusted_records,
        "selected_provenance": {"factor": f_resolved,
                                "penalty": p_selected if p_selected else None},
    }
    # 深拷贝彻底解除别名 + 校验纯 JSON(NaN/不可序列化在此拒)
    verified_payload = json.loads(json.dumps(verified_payload, ensure_ascii=False,
                                             allow_nan=False))
    return {"factor_payload_hash": factor_payload.payload_hash,
            "penalty_payload_hash": (penalty_payload.payload_hash
                                     if penalty_payload else None),
            "commitment": commitment, "verified": verified_payload,
            "verified_outcome": verified_outcome}


class ArchiveWriteOnceConflictError(RegistryError):
    """write-once 档案位已被**内容不同**的密封档案占用(re-review#6 P2:恢复
    据此与"验证性失败"区分——并发竞争的输家转为读验既有档案返回)。"""


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
        raise RegistryError("decision_id 须为非空 str(re-review#21 静态错误)")
    if type(execution_id) is not str or not execution_id:
        raise RegistryError("execution_id 须为非空 str(re-review#21 静态错误)")
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
    # re-review#16 P1:seal 只消费 verify 产出的**完整独立 verified 归档载荷**,
    # 除追加 `ledger_head_at_seal` 外**绝不回读任何 live 输入**(bundle/contract/
    # artifact 都不读)——验证后回调污染 live 输入到不了盘。
    verified = verify_execution_bundle(bundle, artifact, ledger_dir=ledger_dir,
                                       prov_dir=prov_dir, contract=contract)["verified"]
    payload = {**verified, "ledger_head_at_seal": ledger_head(ledger_dir)}
    archive = {**payload, "archive_sha256": seal_hash(payload)}
    path = _archive_path(archive_dir, verified["decision_id"], verified["execution_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with _prov_lock(path):                     # 按 (decision, execution) 的档案锁
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing == archive:
                return existing                # 幂等重试:完全相同才放行
            raise ArchiveWriteOnceConflictError(
                f"执行 ({verified['decision_id']!r}, {verified['execution_id']!r}) "
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
    # re-review#23 P1:ID 恰 str 门 + **验证并捕获 contract/artifact 先于任何身份
    # 比较**——旧序在验证门前就读 `artifact.bundle.decision_id`/`contract.
    # contract_hash`(未验对象的访问器先执行),且外部 decision_id 未先做类型门
    # 就进 `==`。此后身份比较只用**已捕获的基础值**(archive 来自盘上普通 JSON)。
    if type(decision_id) is not str or type(execution_id) is not str:
        raise RegistryError("decision_id/execution_id 须恰 str(re-review#23)")
    # GPT #23:契约**先**快照(verify_d7_artifact 内的 registry 回调可改写 live
    # contract 字段,旧序在其后才捕获 v_contract_*);artifact **绑定返回的独立
    # 可信副本**——此后本函数与下游 verify_execution_bundle 只用可信对象。
    contract = snapshot_exact_contract(contract)
    v_contract_hash = contract.contract_hash
    v_contract_payload = contract_canonical_payload(contract)
    artifact = verify_d7_artifact(artifact)
    v_artifact_hash = artifact.artifact_hash
    v_bundle_hash = artifact.bundle.bundle_hash
    v_final_registry_hash = artifact.final_registry.registry_hash
    v_bundle_decision_id = artifact.bundle.decision_id
    path = _archive_path(archive_dir, decision_id, execution_id)
    if not path.exists():
        raise RegistryError("决策档案缺失(re-review#21 静态错误)")
    archive = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(archive, dict) or set(archive) != _ARCHIVE_KEYS:
        raise RegistryError("档案顶层键集不符 news_decision_archive_v1 schema"
                            "(archive-review Major;多/少键=拒)")
    body = {k: v for k, v in archive.items() if k != "archive_sha256"}
    verify_sealed(body, archive.get("archive_sha256", ""),
                  field_name="archive_sha256")
    if archive["archive_schema"] != _ARCHIVE_SCHEMA:
        raise RegistryError("档案 archive_schema 不符(re-review#21 静态错误)")
    # archive-review Major:三向决策身份(archive 盘上普通值 vs 已捕获基础值)
    if not (archive["decision_id"] == decision_id == v_bundle_decision_id):
        raise RegistryError("决策身份三向不符:档案 / 请求 / 工件束 decision_id 不一致"
                            "(archive-review Major;re-review#21/#23)")
    if archive["execution_id"] != execution_id:
        raise RegistryError("档案 execution_id ≠ 请求——执行身份不符(re-review#4/#21)")
    if archive["contract_hash"] != v_contract_hash \
            or archive["contract"] != v_contract_payload:
        raise RegistryError("档案契约与提供的冻结契约不符")
    if archive["artifact_hash"] != v_artifact_hash:
        raise RegistryError("档案工件哈希与提供的工件不符")
    if archive["bundle_hash"] != v_bundle_hash:
        raise RegistryError("档案 bundle_hash 与提供工件的证据束不符(archive-review Major)")
    if archive["final_registry_hash"] != v_final_registry_hash:
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
    if o != outcome_canonical_payload(outcome):
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
    if type(decision_id) is not str:                   # re-review#23:先于 == 比较
        raise RegistryError("decision_id 须恰 str(re-review#23)")
    chain = _read_chain(_ledger_path(ledger_dir))
    success = _find_success_commitment(chain, decision_id)
    if success is None:
        raise RegistryError(
            "决策无 success 执行承诺——无 canonical 决策档案"
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
    """**success 承诺后的可恢复封存**(re-review#4 崩溃变体 + re-review#5
    P0/P2):承诺已入链、进程在封档前崩溃 → 从**纯盘上状态**重建执行束并走
    正常封印。恢复契约必须与**承诺哈希绑定的契约**逐字节相符(P0——换主评分
    周期在写任何文件前拒;承诺内嵌完整契约载荷,纯磁盘状态可自证);档案已在
    → 读验返回(P2——账本此后合法增长不破坏幂等),缺失才重建。重建全程
    verify-not-trust:终态从出处解析(唯一+状态机)且 entry_hash 必须等于
    账本承诺;解析记录取自终态行封存本体(哈希绑定在行封印内);outcome 从
    (工件+契约+终态 verdict)经 M3⁴ 矩阵**重推导**,其 outcome_hash 必须等于
    承诺的 outcome_hash(权威锚);evaluation 确定性重算。随后
    `seal_decision_archive` 重跑全量联合验证 + write-once。"""
    if type(decision_id) is not str:                   # re-review#23:先于 == 比较
        raise RegistryError("decision_id 须恰 str(re-review#23)")
    # GPT #23 P1#2:恢复入口**先**取得独立 contract/artifact 快照——旧代码在
    # artifact 类型门之前就把它交给 build_leg_payload_ast 迭代(rows 换成 list
    # 子类,其 __iter__ 在统一校验前执行)。verify_d7_artifact 的恰类型门
    # (rows 须恰 tuple)静态拒于任何迭代之前;此后全程只用可信副本。
    contract = snapshot_exact_contract(contract)       # re-review#6 P0 + GPT #23
    artifact = verify_d7_artifact(artifact)
    chain = _read_chain(_ledger_path(ledger_dir))
    success = _find_success_commitment(chain, decision_id)
    if success is None:
        raise RegistryError(
            "决策无 success 执行承诺——无可恢复的封存(re-review#4/#21 静态错误)")
    execution_id = success["execution_id"]
    # re-review#5 P0:恢复所用契约必须与承诺哈希绑定的契约**逐字节**相符——
    # 同 schema/同 mode/不同 primary_decision_horizon 的替换在写任何文件前拒
    if contract.contract_hash != success["contract_hash"] \
            or contract_canonical_payload(contract) != success["contract"]:
        raise RegistryError(
            f"恢复契约与账本承诺不符(承诺 {success['contract']} vs 提供 "
            f"{contract_canonical_payload(contract)})——主评分周期等契约字段"
            f"不可替换,拒(re-review#5 P0)")
    # re-review#5 P2 + re-review#6 P2:档案已在 → 读验并返回(真幂等)。**用
    # 新账本快照**(`load_and_verify_execution_archive` 自取)——恢复入口的
    # `chain` 可能是旧快照,竞争者此后合法增长账本+封存,拿旧快照验新锚会
    # 误拒有效档案(re-review#6 P2)
    if _archive_path(archive_dir, decision_id, execution_id).exists():
        return load_and_verify_execution_archive(
            decision_id, execution_id, artifact, ledger_dir=ledger_dir,
            prov_dir=prov_dir, contract=contract, archive_dir=archive_dir)
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
    try:
        return seal_decision_archive(bundle, artifact, ledger_dir=ledger_dir,
                                     prov_dir=prov_dir, contract=contract,
                                     archive_dir=archive_dir)
    except ArchiveWriteOnceConflictError:
        # re-review#6 P2:入口存在检查与封存不在同一锁内——并发的恢复/封存
        # 赢了竞争后账本又合法增长,本次重建的锚更晚 → write-once 冲突。输家
        # 不报错,**重新读验既有档案并返回**(先写者的档案就是该执行的档案)
        return load_and_verify_execution_archive(
            decision_id, execution_id, artifact, ledger_dir=ledger_dir,
            prov_dir=prov_dir, contract=contract, archive_dir=archive_dir)
