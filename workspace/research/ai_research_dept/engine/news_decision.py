# SCRIPT_STATUS: ACTIVE — 新闻快讯:决策账本 + 密封 payload 咽喉点(NF §7 席位接线·单元1;re-review 全折叠)
"""Decision ledger + sealed-payload choke point (seat wiring, unit 1).

step5/6 底物终门后的第一承重单元,落 [NF_SEAL_HARDENING.md](../NF_SEAL_HARDENING.md)
的 5 条 BINDING 需求 + 席位接线首轮实现审(3B/3M)的全部处方:

1. **账本持有权威 `decision_id`**(BINDING #1 + 实现审 M1):原子首写胜出
   `decision_id → 完整工件派生行`,整个读-查-写在一把锁内;**严格行 schema**(精确
   键集+物理 seq+哈希链 prev_hash/entry_hash,任一字段被改/链断/行被换=读即 fail-closed;
   注:自含链无法察觉整本重算替换——链头锚定进发布/封印账本是档案单元的集成项);
   `require_recorded` 对**全部工件派生字段**逐一比对(不再只比两个哈希);写入
   flush+fsync 后 `os.replace`(LLM 前持久提交)。
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
    D7DecisionArtifact, verify_d7_artifact,
)
from workspace.research.ai_research_dept.engine.news_evidence import (
    EvidenceRef, RegistryError, assert_factor_payload, assert_leg_payload,
    build_factor_payload_ids, extract_candidate_ids, require_sealed_registry,
)
from workspace.research.ai_research_dept.engine.news_seal import seal_hash, verify_sealed

_LEDGER_NAME = "decision_ledger.jsonl"
_GENESIS = "0" * 64
_HEX64_RE = re.compile(r"[0-9a-f]{64}")

#: 账本行严格 schema(实现审 M1:精确键集,多/少键=fail-closed)
_ENTRY_KEYS = frozenset({"decision_id", "bundle_hash", "artifact_hash",
                         "final_registry_hash", "source_card_hash", "cutoff_iso",
                         "seq", "prev_hash", "entry_hash"})
#: 工件派生字段(require_recorded 全字段比对的范围)
_ARTIFACT_FIELDS = ("bundle_hash", "artifact_hash", "final_registry_hash",
                    "source_card_hash", "cutoff_iso")


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
    """读并**全量验证**账本(实现审 M1 fail-closed):精确键集、物理 seq、prev_hash
    链、每行 entry_hash 重算、decision_id 唯一。任一不符=拒。"""
    if not path.exists():
        return []
    entries: list = []
    seen: set = set()
    prev = _GENESIS
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(x for x in (ln.strip() for ln in f) if x):
            entry = json.loads(line)
            if set(entry) != _ENTRY_KEYS:
                raise RegistryError(
                    f"账本行 {i} 键集不符 {sorted(entry)}——严格 schema 拒(M1)")
            if entry["seq"] != i:
                raise RegistryError(f"账本行 {i} 物理序被改(seq={entry['seq']!r})——拒(M1)")
            if entry["prev_hash"] != prev:
                raise RegistryError(f"账本行 {i} 哈希链断裂——行被改/删/换,拒(M1)")
            body = {k: v for k, v in entry.items() if k != "entry_hash"}
            if seal_hash(body) != entry["entry_hash"]:
                raise RegistryError(f"账本行 {i} entry_hash 重算不符——行被改,拒(M1)")
            did = entry["decision_id"]
            if did in seen:
                raise RegistryError(f"账本含重复 decision_id {did!r}——append-only 被外改,拒")
            seen.add(did)
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
    if not isinstance(decision_id, str) or not decision_id.strip():
        raise RegistryError(f"权威 decision_id 须非空 str(得 {decision_id!r})")
    verify_d7_artifact(artifact)
    if artifact.bundle.decision_id != decision_id:
        raise RegistryError(
            f"工件束 decision_id {artifact.bundle.decision_id!r} ≠ 账本权威 "
            f"{decision_id!r}——账本持有期望 id,工件必须逐字节匹配(BINDING #1)")
    expected = _expected_fields(artifact)
    path = _ledger_path(ledger_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _ledger_lock(path):
        entries = _read_chain(path)
        existing = next((e for e in entries if e["decision_id"] == decision_id), None)
        if existing is not None:
            if all(existing[k] == expected[k] for k in _ARTIFACT_FIELDS):
                return dict(existing)              # 逐字节相同重算 → 幂等
            raise RegistryError(
                f"decision {decision_id!r} 已入账 bundle "
                f"{existing['bundle_hash'][:12]}——首写胜出,第二个不同世界线 "
                f"{artifact.bundle.bundle_hash[:12]} 拒(BINDING #1)")
        prev = entries[-1]["entry_hash"] if entries else _GENESIS
        body = {"decision_id": decision_id, **expected,
                "seq": len(entries), "prev_hash": prev}
        entry = {**body, "entry_hash": seal_hash(body)}
        _atomic_durable_write(entries + [entry], path)
    return dict(entry)


def lookup_decision(ledger_dir, decision_id: str) -> "dict | None":
    return next((e for e in _read_chain(_ledger_path(ledger_dir))
                 if e["decision_id"] == decision_id), None)


def require_recorded(ledger_dir, decision_id: str, artifact: D7DecisionArtifact) -> dict:
    """payload 构造/执行前的账本门(BINDING #1 + 实现审 M1):工件重验过门、决策
    已入账、且账本行与**全部工件派生字段**逐一相等(改任一字段/换行=拒)。"""
    verify_d7_artifact(artifact)
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
    if not isinstance(artifact, D7DecisionArtifact):
        raise RegistryError("factor_refs 只收 D7DecisionArtifact")
    return [EvidenceRef(rid) for rid in build_factor_payload_ids(
        artifact.final_registry, consumer_seat=consumer_seat,
        target_dimension=target_dimension)]


def leg_refs(artifact: D7DecisionArtifact, *, use: str, consumer_seat: str) -> list:
    """腿级引用白名单方向(= 期望总体的 EvidenceRef 形态,恰一次序)。"""
    if not isinstance(artifact, D7DecisionArtifact):
        raise RegistryError("leg_refs 只收 D7DecisionArtifact")
    return [EvidenceRef(rid) for rid in leg_expected_ids(
        artifact.final_registry, use=use, consumer_seat=consumer_seat)]


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
        if not self.payload_hash:
            raise RegistryError(
                "SealedPayload.payload_hash 不得为空——本对象只能经内部工厂铸造"
                f"(实现审 B2:无公开自动铸印)")
        verify_sealed(self._payload(), self.payload_hash, field_name="payload_hash")

    def _payload(self) -> dict:
        return {"decision_id": self.decision_id, "seat": self.consumer_seat,
                "use": self.use, "dimension": self.target_dimension,
                "payload_text": self.payload_text,
                "registry_hash": self.registry_hash,
                "artifact_hash": self.artifact_hash,
                "bundle_hash": self.bundle_hash,
                "ledger_entry_hash": self.ledger_entry_hash,
                "expected_ids": list(self.expected_ids),
                "ref_occurrences": list(self.ref_occurrences),
                "authorized_ids": list(self.authorized_ids)}


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
    extracted = extract_candidate_ids(text)
    if set(occurrences) != extracted:
        raise RegistryError(
            f"引用出处不符:类型化 EvidenceRef 出现 {sorted(set(occurrences))} vs "
            f"终字节抽取 {sorted(extracted)}——`[ID]` 语法为 EvidenceRef 专属,"
            f"普通字符串引用样 token 拒(实现审 M2)")
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
    终字节门 → 完整性 → 内部工厂铸印,一条不可分链。"""
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


def verify_payload_for_execution(sp: SealedPayload, artifact: D7DecisionArtifact, *,
                                 ledger_dir) -> SealedPayload:
    """**执行体边界校验器**(实现审 B2:LLM 执行体只经此可达)。自洽自铸的
    SealedPayload 在此无路——重跑账本门(全字段)、比对账本行/工件/束/注册表哈希、
    **重序列化保留 AST** 并逐字节比对、终字节重门、期望总体/出现序列/授权集重推导
    逐一比对。"""
    if not isinstance(sp, SealedPayload):
        raise RegistryError("执行体只收 SealedPayload(经边界校验器)")
    verify_sealed(sp._payload(), sp.payload_hash, field_name="payload_hash")
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
