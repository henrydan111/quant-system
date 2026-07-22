# SCRIPT_STATUS: ACTIVE — 新闻快讯:决策账本 + 密封 payload 咽喉点(NF §7 席位接线·单元1;re-review 全折叠)
"""Decision ledger + sealed-payload choke point (seat wiring, unit 1).

step5/6 底物终门后的第一承重单元,落 [NF_SEAL_HARDENING.md](../NF_SEAL_HARDENING.md)
的 5 条 BINDING 需求 + 席位接线首轮实现审(3B/3M)的全部处方:

1. **账本持有权威 `decision_id`**(BINDING #1 + 实现审 M1):原子首写胜出
   `decision_id → 完整工件派生行`,整个读-查-写在一把锁内;**严格行 schema**(精确
   键集+物理 seq+哈希链 prev_hash/entry_hash,任一字段被改/链断/行被换=读即 fail-closed;
   注:自含链无法察觉整本重算替换——链头锚定进发布/封印账本是档案单元的集成项);
   `require_recorded` 对**全部工件派生字段**逐一比对(不再只比两个哈希);写入
   flush+fsync 后 `os.replace`(LLM 前持久提交)。**archive-re-review#2:链承载
   两类行**——`kind=decision`(决策注册)+ `kind=execution_commitment`
   (`record_execution_commitment`:受控执行器把一次执行的选定终态出处
   entry_hash + outcome_hash 提交进链;首写胜出 per (decision, execution),
   承诺必须晚于其决策注册)。
2. **封闭 payload AST**(BINDING #2 + 实现审 M2):**精确类型**闭集(`type(x) is …`,
   str/dict 子类、EvidenceRef 子类一律拒);无 `default=` 回退;
   **`[ID]` 语法为 EvidenceRef 专属**——普通字符串里的引用样 token 经"类型化出处
   ↔ 终字节抽取"相等性证明被拒(provenance 携带并证明,M2)。
3. **腿 payload 完整性**(实现审 B1):从终注册表推导**确定性期望总体**;类型化
   EvidenceRef 出现序列(**列表,非集合**)必须与期望总体**恰一次**逐一相等——
   空/子集/重复/多余在任何执行体运行前拒;期望集+出现序列+其哈希全部入印。
4. **SealedPayload 只能经内部工厂铸造**(实现审 B2):空 `payload_hash` 直接拒
   (无公开自动铸印);自洽自铸的对象在**执行体边界校验器**
   (`verify_payload_for_execution`:重跑账本门+全字段比对+保留 AST 重序列化+
   终字节重门+出现序列重比)前无路——执行体只经它可达。
5. **身份逐字节保存**(BINDING #5):序列化不 strip/不折叠/不大小写化。
"""
from __future__ import annotations

import json
import math
import os
import re
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from workspace.research.ai_research_dept.engine.news_cards import (
    D7DecisionArtifact, has_substantive_text, verify_d7_artifact,
)
from workspace.research.ai_research_dept.engine.news_evidence import (
    EvidenceRef, RegistryError, assert_factor_payload, assert_leg_payload,
    build_factor_payload_ids, extract_candidate_id_occurrences,
    require_sealed_registry,
)
from workspace.research.ai_research_dept.engine.news_seal import (
    plain_str, plain_str_tuple, seal_hash, verify_sealed,
)

_LEDGER_NAME = "decision_ledger.jsonl"
_GENESIS = "0" * 64
_HEX64_RE = re.compile(r"[0-9a-f]{64}")

#: 账本行严格 schema(实现审 M1:精确键集,多/少键=fail-closed)。
#  archive-re-review#2 Blocker:账本承载**两类**行——决策注册行 + 执行承诺行
#  (受控执行器把选定终态出处 entry_hash 提交进这条不可重写哈希链;归档验证对
#  承诺行复验,出处文件里事后追加/替换的伪造终态到不了档案)。
_DECISION_KEYS = frozenset({"kind", "decision_id", "bundle_hash", "artifact_hash",
                            "final_registry_hash", "source_card_hash", "cutoff_iso",
                            "seq", "prev_hash", "entry_hash"})
_COMMITMENT_KEYS = frozenset({"kind", "decision_id", "execution_id",
                              "factor_entry_hash", "penalty_entry_hash",
                              "outcome_hash", "news_status",
                              "contract", "contract_hash",
                              "seq", "prev_hash", "entry_hash"})
_COMMITMENT_STATUSES = frozenset({"success", "hard_failed"})
#: 工件派生字段(require_recorded 全字段比对的范围)
_ARTIFACT_FIELDS = ("bundle_hash", "artifact_hash", "final_registry_hash",
                    "source_card_hash", "cutoff_iso")
#: 承诺行身份外字段(_append_commitment_row 幂等比对的范围)
_COMMITMENT_FIELDS = ("factor_entry_hash", "penalty_entry_hash", "outcome_hash",
                      "news_status", "contract", "contract_hash")


# --------------------------------------------------- 账本(原子首写胜出+哈希链)

@contextmanager
def _ledger_lock(path: Path, *, timeout: float = 30.0):
    """跨进程账本锁(原子 mkdir 自旋):整个读-查-写事务在一把锁内(BINDING #1)。"""
    lock_dir = path.parent / (path.name + ".lock")
    deadline = time.monotonic() + timeout
    while True:
        try:
            lock_dir.mkdir(parents=False, exist_ok=False)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise RegistryError(f"账本锁超时({timeout}s):{lock_dir}")
            time.sleep(0.05)
    try:
        yield
    finally:
        try:
            lock_dir.rmdir()
        except OSError:
            pass


def _ledger_path(ledger_dir) -> Path:
    return Path(ledger_dir) / _LEDGER_NAME


def _read_chain(path: Path) -> list:
    """读并**全量验证**账本(实现审 M1 fail-closed):每行 kind ∈ {decision,
    execution_commitment}、按 kind 精确键集、物理 seq、prev_hash 链、每行
    entry_hash 重算、决策行 decision_id 唯一、承诺行 (decision_id, execution_id)
    唯一且其 decision 必已在前文注册。任一不符=拒。"""
    if not path.exists():
        return []
    entries: list = []
    seen: set = set()
    seen_commit: set = set()
    seen_success: set = set()
    prev = _GENESIS
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(x for x in (ln.strip() for ln in f) if x):
            entry = json.loads(line)
            kind = entry.get("kind")
            if kind == "decision":
                if set(entry) != _DECISION_KEYS:
                    raise RegistryError(
                        f"账本行 {i} 键集不符 {sorted(entry)}——严格 schema 拒(M1)")
            elif kind == "execution_commitment":
                if set(entry) != _COMMITMENT_KEYS:
                    raise RegistryError(
                        f"账本行 {i} 承诺行键集不符 {sorted(entry)}——严格 schema 拒")
                if entry["news_status"] not in _COMMITMENT_STATUSES:
                    raise RegistryError(
                        f"账本行 {i} 承诺 news_status {entry['news_status']!r} "
                        f"未注册——拒")
                # re-review#5 P0:承诺内嵌完整契约载荷,其哈希对必须自洽
                if seal_hash(entry["contract"]) != entry["contract_hash"]:
                    raise RegistryError(
                        f"账本行 {i} 承诺 contract/contract_hash 对不自洽——拒")
            else:
                raise RegistryError(f"账本行 {i} 未注册 kind {kind!r}——拒")
            if entry["seq"] != i:
                raise RegistryError(f"账本行 {i} 物理序被改(seq={entry['seq']!r})——拒(M1)")
            if entry["prev_hash"] != prev:
                raise RegistryError(f"账本行 {i} 哈希链断裂——行被改/删/换,拒(M1)")
            body = {k: v for k, v in entry.items() if k != "entry_hash"}
            if seal_hash(body) != entry["entry_hash"]:
                raise RegistryError(f"账本行 {i} entry_hash 重算不符——行被改,拒(M1)")
            did = entry["decision_id"]
            if kind == "decision":
                if did in seen:
                    raise RegistryError(
                        f"账本含重复 decision_id {did!r}——append-only 被外改,拒")
                seen.add(did)
            else:
                key = (did, entry["execution_id"])
                if key in seen_commit:
                    raise RegistryError(
                        f"账本含重复执行承诺 {key!r}——append-only 被外改,拒")
                if did not in seen:
                    raise RegistryError(
                        f"账本行 {i} 执行承诺先于决策注册({did!r})——状态机违规,拒")
                if entry["news_status"] == "success":
                    # re-review#3 P0:每决策至多一条 success 承诺(链级不变量)
                    if did in seen_success:
                        raise RegistryError(
                            f"账本含 {did!r} 的第二条 success 执行承诺——决策的"
                            f"成功执行唯一,链非法,拒(re-review#3 P0)")
                    seen_success.add(did)
                seen_commit.add(key)
            entries.append(entry)
            prev = entry["entry_hash"]
    return entries


def _atomic_durable_write(entries: list, path: Path) -> None:
    """写入 flush+fsync 后原子 replace(实现审 M1:LLM 前持久提交;Windows 上目录
    fsync 不可用,文件级 fsync + NTFS 元数据日志为该平台的持久性边界)。"""
    fd, tmp = tempfile.mkstemp(suffix=".jsonl.tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e, ensure_ascii=False, allow_nan=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _expected_fields(artifact: D7DecisionArtifact) -> dict:
    return {"bundle_hash": artifact.bundle.bundle_hash,
            "artifact_hash": artifact.artifact_hash,
            "final_registry_hash": artifact.final_registry.registry_hash,
            "source_card_hash": artifact.card.card_hash,
            "cutoff_iso": artifact.bundle.cutoff_iso}


def record_decision(ledger_dir, decision_id: str, artifact: D7DecisionArtifact) -> dict:
    """原子首写胜出入账(BINDING #1)。账本持有**权威** decision_id;工件必须
    `verify_d7_artifact` 过门且其束 decision_id 与之逐字节相等。幂等 = 全部工件
    派生字段逐一相等;任一不同 = 拒(第二个世界线无法成为同一决策的权威)。"""
    if type(decision_id) is not str or not decision_id.strip():
        raise RegistryError(f"权威 decision_id 须恰 str 非空(得 "
                            f"{type(decision_id).__name__} {decision_id!r};子类拒)")
    artifact = verify_d7_artifact(artifact)            # GPT #23:绑定独立可信副本
    if artifact.bundle.decision_id != decision_id:
        raise RegistryError(
            f"工件束 decision_id {artifact.bundle.decision_id!r} ≠ 账本权威 "
            f"{decision_id!r}——账本持有期望 id,工件必须逐字节匹配(BINDING #1)")
    expected = _expected_fields(artifact)
    path = _ledger_path(ledger_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _ledger_lock(path):
        entries = _read_chain(path)
        existing = next((e for e in entries if e["kind"] == "decision"
                         and e["decision_id"] == decision_id), None)
        if existing is not None:
            if all(existing[k] == expected[k] for k in _ARTIFACT_FIELDS):
                return dict(existing)              # 逐字节相同重算 → 幂等
            raise RegistryError(
                f"decision {decision_id!r} 已入账 bundle "
                f"{existing['bundle_hash'][:12]}——首写胜出,第二个不同世界线 "
                f"{artifact.bundle.bundle_hash[:12]} 拒(BINDING #1)")
        prev = entries[-1]["entry_hash"] if entries else _GENESIS
        body = {"kind": "decision", "decision_id": decision_id, **expected,
                "seq": len(entries), "prev_hash": prev}
        entry = {**body, "entry_hash": seal_hash(body)}
        _atomic_durable_write(entries + [entry], path)
    return dict(entry)


def _append_commitment_row(ledger_dir, *, decision_id: str, execution_id: str,
                           factor_entry_hash: str,
                           penalty_entry_hash: "str | None",
                           outcome_hash: str, news_status: str,
                           contract_payload: dict, contract_hash: str) -> dict:
    """执行承诺入链的**模块私有低层写入**(archive-re-review#2 Blocker +
    re-review#3 P0)。⚠ 公开承诺 API 已撤除——唯一受认可调用方是
    [news_executors.commit_execution](news_executors.py) 承诺权威(它只提交
    **自行从盘上解析并全链验证过的**终态,绝不透传调用方哈希);本函数不做该
    验证,故必须保持模块私有。规则:
    - 首写胜出 per (decision_id, execution_id):幂等 = 承诺字段逐一相等;
    - **success 承诺每决策唯一**(re-review#3 P0):真实执行承诺 success 后,
      伪造的"全新执行"无法再为同一决策提交第二条 success——归档只认账本里
      那唯一的 success 执行;hard_failed 承诺可多条(崩溃/重试的审计痕迹);
    - 决策必须已注册。"""
    if type(decision_id) is not str or not decision_id.strip():
        raise RegistryError(f"decision_id 须恰 str 非空(得 {decision_id!r})")
    if type(execution_id) is not str or not execution_id.strip():
        raise RegistryError(f"execution_id 须恰 str 非空(得 {execution_id!r})")
    if not (type(factor_entry_hash) is str and _HEX64_RE.fullmatch(factor_entry_hash)):
        raise RegistryError(f"factor_entry_hash 须 64-hex(得 {factor_entry_hash!r})")
    if penalty_entry_hash is not None and not (
            type(penalty_entry_hash) is str
            and _HEX64_RE.fullmatch(penalty_entry_hash)):
        raise RegistryError(f"penalty_entry_hash 须 None/64-hex(得 {penalty_entry_hash!r})")
    if not (type(outcome_hash) is str and _HEX64_RE.fullmatch(outcome_hash)):
        raise RegistryError(f"outcome_hash 须 64-hex(得 {outcome_hash!r})")
    if news_status not in _COMMITMENT_STATUSES:
        raise RegistryError(f"news_status {news_status!r} 未注册")
    # re-review#5 P0:承诺**哈希绑定完整冻结契约**(含 primary_decision_horizon
    # ——outcome_hash 不含主评分周期,契约不绑进承诺则封存/恢复可合法换周期改分)
    # 并内嵌不可变契约载荷本体(纯磁盘恢复可自证,而非只能校验调用方供给)
    if type(contract_payload) is not dict:
        raise RegistryError(f"contract_payload 须 dict(得 {type(contract_payload).__name__})")
    if not (type(contract_hash) is str and _HEX64_RE.fullmatch(contract_hash)):
        raise RegistryError(f"contract_hash 须 64-hex(得 {contract_hash!r})")
    if seal_hash(contract_payload) != contract_hash:
        raise RegistryError("contract_payload/contract_hash 对不自洽——拒")
    expected = {"factor_entry_hash": factor_entry_hash,
                "penalty_entry_hash": penalty_entry_hash,
                "outcome_hash": outcome_hash, "news_status": news_status,
                "contract": contract_payload, "contract_hash": contract_hash}
    path = _ledger_path(ledger_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _ledger_lock(path):
        entries = _read_chain(path)
        if not any(e["kind"] == "decision" and e["decision_id"] == decision_id
                   for e in entries):
            raise RegistryError(
                f"decision {decision_id!r} 未注册——执行承诺必须晚于决策入账")
        existing = next((e for e in entries if e["kind"] == "execution_commitment"
                         and e["decision_id"] == decision_id
                         and e["execution_id"] == execution_id), None)
        if existing is not None:
            if all(existing[k] == expected[k] for k in _COMMITMENT_FIELDS):
                return dict(existing)              # 逐字节相同重试 → 幂等
            raise RegistryError(
                f"执行 ({decision_id!r}, {execution_id!r}) 已承诺终态——首写胜出,"
                f"同一执行的第二套终态拒(archive-re-review#2 Blocker)")
        if news_status == "success" and any(
                e["kind"] == "execution_commitment"
                and e["decision_id"] == decision_id
                and e["news_status"] == "success" for e in entries):
            raise RegistryError(
                f"决策 {decision_id!r} 已有 success 执行承诺——决策的成功执行"
                f"唯一,第二条 success(含伪造的全新执行)拒(re-review#3 P0)")
        prev = entries[-1]["entry_hash"] if entries else _GENESIS
        body = {"kind": "execution_commitment", "decision_id": decision_id,
                "execution_id": execution_id, **expected,
                "seq": len(entries), "prev_hash": prev}
        entry = {**body, "entry_hash": seal_hash(body)}
        _atomic_durable_write(entries + [entry], path)
    return dict(entry)


def find_execution_commitment(ledger_dir, decision_id: str,
                              execution_id: str) -> "dict | None":
    return next((e for e in _read_chain(_ledger_path(ledger_dir))
                 if e["kind"] == "execution_commitment"
                 and e["decision_id"] == decision_id
                 and e["execution_id"] == execution_id), None)


def find_success_commitment(ledger_dir, decision_id: str) -> "dict | None":
    """该决策的**唯一** success 执行承诺(链级不变量保证至多一条)。"""
    return next((e for e in _read_chain(_ledger_path(ledger_dir))
                 if e["kind"] == "execution_commitment"
                 and e["decision_id"] == decision_id
                 and e["news_status"] == "success"), None)


def lookup_decision(ledger_dir, decision_id: str) -> "dict | None":
    return next((e for e in _read_chain(_ledger_path(ledger_dir))
                 if e["kind"] == "decision"
                 and e["decision_id"] == decision_id), None)


def ledger_head(ledger_dir) -> str:
    """账本哈希链**当前链头**(空账本 = 创世哨兵)。档案封印时把链头封进档案 =
    链头外锚(整本重算会换掉全部 entry_hash → 档案验证时旧链头不在新链内 → 抓获;
    M1 已知盲区的外锚闭合,最终集成 BINDING #6)。"""
    entries = _read_chain(_ledger_path(ledger_dir))
    return entries[-1]["entry_hash"] if entries else _GENESIS


def require_recorded(ledger_dir, decision_id: str, artifact: D7DecisionArtifact) -> dict:
    """payload 构造/执行前的账本门(BINDING #1 + 实现审 M1):工件重验过门、决策
    已入账、且账本行与**全部工件派生字段**逐一相等(改任一字段/换行=拒)。"""
    artifact = verify_d7_artifact(artifact)            # GPT #23:绑定独立可信副本
    entry = lookup_decision(ledger_dir, decision_id)
    if entry is None:
        raise RegistryError(f"decision {decision_id!r} 未入账——payload 构造前必须"
                            f"原子首写(BINDING #1)")
    expected = _expected_fields(artifact)
    if artifact.bundle.decision_id != decision_id \
            or any(entry[k] != expected[k] for k in _ARTIFACT_FIELDS):
        diffs = [k for k in _ARTIFACT_FIELDS if entry[k] != expected[k]]
        raise RegistryError(
            f"工件与账本行不符(decision {decision_id!r},字段 {diffs})——"
            f"只有入账的那个世界线可以构造 payload(M1 全字段比对)")
    return entry


# --------------------------------------------------- 封闭 payload AST(严格类型)

def _walk_ast(o, occurrences: list):
    """封闭 AST 严格类型递归(实现审 M2:`type(x) is …`——str/dict/list/tuple/int/
    float/bool 的**子类一律拒**,EvidenceRef 恰其类)。类型化引用出现按确定性
    DFS 序收进 occurrences(**列表**,B1 完整性用)。"""
    t = type(o)
    if t is EvidenceRef:
        occurrences.append(o.record_id)
        return o.encode()
    if o is None:
        return None
    if t is bool or t is str or t is int:
        return o
    if t is float:
        if not math.isfinite(o):
            raise RegistryError(f"payload AST 拒非有限 float({o!r})")
        return o
    if t is dict:
        out = {}
        for k, v in o.items():
            if type(k) is not str:
                raise RegistryError(f"payload AST dict 键须恰 str(得 {type(k).__name__})")
            out[k] = _walk_ast(v, occurrences)
        return out
    if t is list or t is tuple:
        return [_walk_ast(x, occurrences) for x in o]
    raise RegistryError(
        f"payload AST 闭集外的节点类型 {type(o).__name__}——set/自定义对象/子类拒,"
        f"绝无 default=str(BINDING #2 + M2 精确类型)")


def serialize_payload_ast(node) -> str:
    """封闭 AST → 精确序列化文本(BINDING #2/#5)。"""
    return json.dumps(_walk_ast(node, []), ensure_ascii=False, allow_nan=False)


def collect_evidence_refs(node) -> tuple:
    """类型化 EvidenceRef 出现序列(确定性 DFS 序,**列表语义**——重复保留)。"""
    occ: list = []
    _walk_ast(node, occ)
    return tuple(occ)


def leg_expected_ids(registry, *, use: str, consumer_seat: str) -> tuple:
    """腿的**确定性期望总体**(实现审 B1):终注册表中 `use ∈ allowed_uses ∧
    consumer_seat ∈ allowed_consumers` 的全部 record_id,排序。"""
    registry = require_sealed_registry(registry)
    return tuple(sorted(rid for rid, r in registry.records.items()
                        if use in r.allowed_uses
                        and consumer_seat in r.allowed_consumers))


def factor_refs(artifact: D7DecisionArtifact, *, consumer_seat: str,
                target_dimension: str) -> list:
    """逐维正向引用白名单方向(BINDING #4)。"""
    if type(artifact) is not D7DecisionArtifact:
        raise RegistryError("factor_refs 只收恰 D7DecisionArtifact(子类拒,re-review#9)")
    return [EvidenceRef(rid) for rid in build_factor_payload_ids(
        artifact.final_registry, consumer_seat=consumer_seat,
        target_dimension=target_dimension)]


def leg_refs(artifact: D7DecisionArtifact, *, use: str, consumer_seat: str) -> list:
    """腿级引用白名单方向(= 期望总体的 EvidenceRef 形态,恰一次序)。"""
    if type(artifact) is not D7DecisionArtifact:
        raise RegistryError("leg_refs 只收恰 D7DecisionArtifact(子类拒,re-review#9)")
    return [EvidenceRef(rid) for rid in leg_expected_ids(
        artifact.final_registry, use=use, consumer_seat=consumer_seat)]


_CARD_LINE_RE = re.compile(r"- \[([A-Z][A-Z0-9]{1,15}"
                           r"(?:\.(?:fact|economic_linkage|timing|source_status))?)\]")


def _card_line_map(card) -> dict:
    """从密封卡两切片解析 {record_id: 去掉引用前缀的行内容}(内容含元数据括号
    `[龄|星|类]`——带管道,非引用语法,不会被当候选)。"""
    out: dict = {}
    for text in (card.factor_payload_text, card.restricted_text):
        for ln in text.splitlines():
            m = _CARD_LINE_RE.match(ln)
            if m:
                out[m.group(1)] = ln[m.end():]
    return out


def build_leg_payload_ast(artifact: D7DecisionArtifact, *, use: str,
                          consumer_seat: str) -> dict:
    """**规范内容承载 payload 渲染器**(executor-review Blocker:LLM 必须看到证据
    正文,不是裸 ID 列表)。从**已验工件**确定性推导:期望总体(use×seat)内每条
    记录 = {"ref": EvidenceRef(id), "content": 密封正文}——
    - D7 子行:content = `AttributeRow.text`(拆分属性正文);
    - 其余记录:content = 卡切片中该 id 行的正文(去引用前缀,保元数据括号);
    - 被降级 broad 父行/错腿/上下文行天然被期望总体排除;
    - 期望内记录若无内容来源 = 拒(渲染不完整绝不静默)。
    输出按 id 排序(确定性)——`run_news_two_legs` 对每腿重渲染并**逐字节比对**
    (canonical 强制:非本渲染器产物到不了执行体)。"""
    if type(artifact) is not D7DecisionArtifact:
        raise RegistryError("canonical 渲染只收恰 D7DecisionArtifact(子类拒,re-review#9)")
    expected = leg_expected_ids(artifact.final_registry, use=use,
                                consumer_seat=consumer_seat)
    rows_by_id = {r.row_id: r for r in artifact.rows}
    line_map = _card_line_map(artifact.card)
    items = []
    for rid in expected:
        if rid in rows_by_id:
            content = rows_by_id[rid].text
        elif rid in line_map:
            content = line_map[rid]
        else:
            raise RegistryError(
                f"{rid} 在期望总体内却无内容来源(卡行/属性行均无)——canonical "
                f"渲染拒(executor-review Blocker:证据正文必须可见)")
        # executor-review#2 Major-1 + #3 Major:防御性收尾——选中内容必须过
        # 共享实质性文本谓词(与 AttributeRow/拆行工厂同一把尺)
        if not has_substantive_text(content):
            raise RegistryError(f"{rid} 内容非实质性({content!r})——空/语义空证据"
                                f"正文不得进 payload(executor-review#2/#3)")
        items.append({"ref": EvidenceRef(rid), "content": content})
    return {"evidence": items}


# --------------------------------------------------- 密封 payload(咽喉点)

@dataclass(frozen=True)
class SealedPayload:
    """LLM 执行体的唯一输入单元(BINDING #4 + 实现审 B2):精确 payload 文本 +
    注册表/工件/束/账本行哈希 + 期望总体 + 类型化出现序列,payload_hash 全 SHA-256。
    **空 payload_hash 直接拒**(无公开自动铸印——只能经内部工厂);自洽自铸对象
    在 `verify_payload_for_execution` 边界前无路。`payload_ast`(保留的类型化 AST,
    供边界重序列化证明)不入印——它由边界校验器**重推导比对**,改它=被抓。"""
    decision_id: str
    consumer_seat: str
    use: str
    target_dimension: "str | None"
    payload_text: str
    registry_hash: str
    artifact_hash: str
    bundle_hash: str
    ledger_entry_hash: str
    expected_ids: tuple
    ref_occurrences: tuple
    authorized_ids: tuple
    payload_ast: object = None
    payload_hash: str = field(default="")

    def __post_init__(self):
        # re-review#11 P0 同类面:str/tuple 字段归一为普通不可变(payload_ast 不动
        # ——由边界校验器重推导独立验证;target_dimension 可为 None 原样保留)
        for _f in ("decision_id", "consumer_seat", "use", "payload_text",
                   "registry_hash", "artifact_hash", "bundle_hash",
                   "ledger_entry_hash"):
            object.__setattr__(self, _f, plain_str(getattr(self, _f)))
        if self.target_dimension is not None:
            object.__setattr__(self, "target_dimension", plain_str(self.target_dimension))
        for _f in ("expected_ids", "ref_occurrences", "authorized_ids"):
            object.__setattr__(self, _f, plain_str_tuple(getattr(self, _f)))
        if not self.payload_hash:
            raise RegistryError(
                "SealedPayload.payload_hash 不得为空——本对象只能经内部工厂铸造"
                f"(实现审 B2:无公开自动铸印)")
        object.__setattr__(self, "payload_hash", plain_str(self.payload_hash))
        verify_sealed(self._payload(), self.payload_hash, field_name="payload_hash")

    def _payload(self) -> dict:
        return sealed_payload_canonical_payload(self)


def sealed_payload_canonical_payload(sp) -> dict:
    """SealedPayload 的 **canonical 载荷**——模块级、不可覆写(archive-re-review#7
    P0 同类面:执行体边界绝不调用可被子类覆写的虚方法)。"""
    return {"decision_id": sp.decision_id, "seat": sp.consumer_seat,
            "use": sp.use, "dimension": sp.target_dimension,
            "payload_text": sp.payload_text,
            "registry_hash": sp.registry_hash,
            "artifact_hash": sp.artifact_hash,
            "bundle_hash": sp.bundle_hash,
            "ledger_entry_hash": sp.ledger_entry_hash,
            "expected_ids": list(sp.expected_ids),
            "ref_occurrences": list(sp.ref_occurrences),
            "authorized_ids": list(sp.authorized_ids)}


def _derive_payload_facts(payload_ast, artifact, *, use: str, consumer_seat: str,
                          target_dimension: "str | None") -> tuple:
    """从(AST, 工件)**全量推导** payload 事实(构造与边界校验共用同一推导):
    1. 严格类型闭集遍历 → 类型化出现序列(列表)+ 精确序列化字节;
    2. **出处证明**(M2):终字节抽取的引用集合必须 == 类型化出现集合——普通
       字符串里的 `[ID]` 样 token(即使是"合法"ID)在此拒;
    3. 门跑在终字节上(逐维 factor 门 或 腿级 use×seat 门);
    4. **完整性**(B1):出现序列排序后必须与期望总体逐一相等(恰一次)——
       空/子集/重复/多余拒。
    返回 (text, occurrences, authorized, expected)。"""
    occurrences: list = []
    converted = _walk_ast(payload_ast, occurrences)
    text = json.dumps(converted, ensure_ascii=False, allow_nan=False)
    # re-review#2(seat) B2:**逐次出现序列**相等(有序+保多重性)——类型化引用无法
    # 掩护同 ID 的裸副本(类型化 1 次 + 裸 2 次 = 终字节 3 次 ≠ 类型化 1 次,拒);
    # 合法 payload 的类型化 DFS 序 == 序列化文本从左到右的出现序,逐一相等。
    extracted_occ = extract_candidate_id_occurrences(text)
    if list(occurrences) != extracted_occ:
        raise RegistryError(
            f"引用出处不符(含重数):类型化 EvidenceRef 出现 {occurrences} vs "
            f"终字节逐次抽取 {extracted_occ}——`[ID]` 语法为 EvidenceRef 专属,"
            f"裸副本/引用样 token 拒(实现审 M2 + re-review#2 B2)")
    registry = artifact.final_registry
    if target_dimension is not None:
        if use != "factor_positive":
            raise RegistryError("逐维门仅限 use=factor_positive(penalty 腿走腿级门)")
        authorized = assert_factor_payload(text, registry,
                                           consumer_seat=consumer_seat,
                                           target_dimension=target_dimension)
        expected = tuple(build_factor_payload_ids(registry,
                                                  consumer_seat=consumer_seat,
                                                  target_dimension=target_dimension))
    else:
        authorized = assert_leg_payload(text, registry, use=use,
                                        consumer_seat=consumer_seat)
        expected = leg_expected_ids(registry, use=use, consumer_seat=consumer_seat)
    if sorted(occurrences) != list(expected):
        raise RegistryError(
            f"payload 完整性不符(实现审 B1):期望总体 {list(expected)} 各恰一次,"
            f"得 {sorted(occurrences)}——空/子集/重复/多余在执行体前拒")
    return text, tuple(occurrences), tuple(sorted(authorized)), expected


def build_sealed_payload(payload_ast, artifact: D7DecisionArtifact, *,
                         ledger_dir, decision_id: str, consumer_seat: str,
                         use: str = "factor_positive",
                         target_dimension: "str | None" = None) -> SealedPayload:
    """**咽喉点**(BINDING #1+#3+#4 + 实现审 B1/B2/M2):
    decision → 账本(全字段)→ 工件 → 终注册表 → 类型化 AST → 出处证明 →
    终字节门 → 完整性 → 内部工厂铸印,一条不可分链。
    re-review#2(seat) M1:席位/用途/维度/决策 id 全部**精确类型**先验(str 子类拒)。"""
    if type(decision_id) is not str or not decision_id.strip():
        raise RegistryError(f"decision_id 须恰 str 非空(得 {type(decision_id).__name__})")
    if type(consumer_seat) is not str or type(use) is not str:
        raise RegistryError("consumer_seat/use 须恰 str(子类拒,re-review#2 M1)")
    if target_dimension is not None and type(target_dimension) is not str:
        raise RegistryError("target_dimension 须恰 str 或 None(子类拒)")
    entry = require_recorded(ledger_dir, decision_id, artifact)
    text, occurrences, authorized, expected = _derive_payload_facts(
        payload_ast, artifact, use=use, consumer_seat=consumer_seat,
        target_dimension=target_dimension)
    fields = {"decision_id": decision_id, "consumer_seat": consumer_seat,
              "use": use, "target_dimension": target_dimension,
              "payload_text": text,
              "registry_hash": artifact.final_registry.registry_hash,
              "artifact_hash": artifact.artifact_hash,
              "bundle_hash": artifact.bundle.bundle_hash,
              "ledger_entry_hash": seal_hash(entry),
              "expected_ids": expected, "ref_occurrences": occurrences,
              "authorized_ids": authorized}
    seal_fields = {"decision_id": decision_id, "seat": consumer_seat, "use": use,
                   "dimension": target_dimension, "payload_text": text,
                   "registry_hash": fields["registry_hash"],
                   "artifact_hash": fields["artifact_hash"],
                   "bundle_hash": fields["bundle_hash"],
                   "ledger_entry_hash": fields["ledger_entry_hash"],
                   "expected_ids": list(expected),
                   "ref_occurrences": list(occurrences),
                   "authorized_ids": list(authorized)}
    return SealedPayload(**fields, payload_ast=payload_ast,
                         payload_hash=seal_hash(seal_fields))


@dataclass(frozen=True)
class ExecutionView:
    """执行体的**唯一**输入(链单元 BINDING #1,re-review#3 R2/终裁点名):
    verified `payload_text` 的**新铸不可变视图**——全字段为不可变 str,**不暴露**
    `payload_ast` 或 SealedPayload 本体(验证后变异对执行体不可见的唯一途径)。
    只在 `verify_payload_for_execution` 通过后、每次执行前由状态机新铸;
    执行体消费 view.payload_text,别无他物。"""
    decision_id: str
    consumer_seat: str
    use: str
    payload_text: str
    payload_hash: str


def make_execution_view(sp: SealedPayload) -> ExecutionView:
    """从**已过边界校验**的 SealedPayload 新铸执行视图(调用方契约:必须紧跟
    verify_payload_for_execution 之后;视图不携带任何可变结构)。"""
    if type(sp) is not SealedPayload:
        raise RegistryError("执行视图只能铸自恰 SealedPayload(子类拒,re-review#7 P0)")
    return ExecutionView(decision_id=sp.decision_id, consumer_seat=sp.consumer_seat,
                         use=sp.use, payload_text=sp.payload_text,
                         payload_hash=sp.payload_hash)


def verify_payload_for_execution(sp: SealedPayload, artifact: D7DecisionArtifact, *,
                                 ledger_dir, expected_decision_id: str,
                                 expected_consumer_seat: str, expected_use: str,
                                 expected_target_dimension: "str | None"
                                 ) -> SealedPayload:
    """**执行体边界校验器**(实现审 B2 + re-review#2 B1:**调用方声明期望上下文**,
    绝不信对象自封的角色/槽位——penalty payload 冒充 factor 槽在此拒)。
    期望四元组(decision_id, seat, use, dimension)先做**精确类型+精确值**比对,
    再做语义重推导:重跑账本门(全字段)、比对账本行/工件/束/注册表哈希、
    **重序列化保留 AST** 并逐字节比对、终字节重门、期望总体/出现序列/授权集重比。"""
    if type(sp) is not SealedPayload:
        raise RegistryError(
            "执行体只收恰 SealedPayload(子类可覆写 _payload 脱钩,拒;re-review#7 P0)")
    # re-review#13 P0:**消费时**精确基础类型断言(__dict__ 注入的"str()真/
    # 其它方法伪"对象、非 str 字段在此死,不只靠构造期归一)
    for _f in ("decision_id", "consumer_seat", "use", "payload_text",
               "registry_hash", "artifact_hash", "bundle_hash",
               "ledger_entry_hash", "payload_hash"):
        if type(getattr(sp, _f)) is not str:
            raise RegistryError(f"SealedPayload.{_f} 须恰 str(re-review#13 P0)")
    if sp.target_dimension is not None and type(sp.target_dimension) is not str:
        raise RegistryError("SealedPayload.target_dimension 须恰 str/None(re-review#13 P0)")
    for _f in ("expected_ids", "ref_occurrences", "authorized_ids"):
        t = getattr(sp, _f)
        if type(t) is not tuple or any(type(x) is not str for x in t):
            raise RegistryError(f"SealedPayload.{_f} 须恰 tuple[恰 str](re-review#13 P0)")
    # re-review#2 B1:期望上下文精确类型 + 精确值,先于一切语义重推导
    if type(expected_decision_id) is not str or type(expected_consumer_seat) is not str \
            or type(expected_use) is not str \
            or (expected_target_dimension is not None
                and type(expected_target_dimension) is not str):
        raise RegistryError("期望上下文须恰 str(/None)——子类拒(re-review#2 B1)")
    if (sp.decision_id != expected_decision_id
            or sp.consumer_seat != expected_consumer_seat
            or sp.use != expected_use
            or sp.target_dimension != expected_target_dimension):
        raise RegistryError(
            f"payload 角色/槽位与期望上下文不符:对象自封 (decision={sp.decision_id!r}, "
            f"seat={sp.consumer_seat!r}, use={sp.use!r}, dim={sp.target_dimension!r}) vs "
            f"期望 ({expected_decision_id!r}, {expected_consumer_seat!r}, "
            f"{expected_use!r}, {expected_target_dimension!r})——重放进错槽拒"
            f"(re-review#2 B1)")
    verify_sealed(sealed_payload_canonical_payload(sp), sp.payload_hash,
                  field_name="payload_hash")
    entry = require_recorded(ledger_dir, sp.decision_id, artifact)
    if seal_hash(entry) != sp.ledger_entry_hash:
        raise RegistryError("SealedPayload 账本行哈希与权威账本不符——非入账世界线拒(B2)")
    if (sp.artifact_hash != artifact.artifact_hash
            or sp.bundle_hash != artifact.bundle.bundle_hash
            or sp.registry_hash != artifact.final_registry.registry_hash):
        raise RegistryError("SealedPayload 工件/束/注册表哈希与实际工件不符(B2)")
    text, occurrences, authorized, expected = _derive_payload_facts(
        sp.payload_ast, artifact, use=sp.use, consumer_seat=sp.consumer_seat,
        target_dimension=sp.target_dimension)
    if (text != sp.payload_text or occurrences != sp.ref_occurrences
            or authorized != sp.authorized_ids or expected != sp.expected_ids):
        raise RegistryError(
            "SealedPayload 重推导不符(文本/出现序列/授权集/期望总体)——"
            "保留 AST 被改或自铸伪造拒(B2)")
    return sp
