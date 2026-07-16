# SCRIPT_STATUS: ACTIVE — 新闻快讯:决策账本 + 密封 payload 咽喉点(NF §7 席位接线·单元1)
"""Decision ledger + sealed-payload choke point (seat wiring, unit 1).

step5/6 底物终门(SOUND-TO-PROCEED,272c13e)后的第一承重单元,逐字落
[NF_SEAL_HARDENING.md](../NF_SEAL_HARDENING.md) 的 5 条席位接线 BINDING 需求:

1. **账本持有权威 `decision_id`**(`DecisionLedger`):原子首写胜出
   `decision_id → bundle_hash`,整个 读-查-写 在**一把锁**内;只收
   `verify_d7_artifact` 过门的 `D7DecisionArtifact` 且其束 decision_id 与账本
   期望 id 逐字节相等;同 id 二次不同哈希=拒,逐字节相同重算=幂等;
   **payload 构造(`build_sealed_payload`)强制要求决策已入账**——先账本后
   payload 后 LLM,顺序机械化。
2. **封闭 payload AST**(`serialize_payload_ast`):节点类型闭集
   {dict[str→node], list/tuple, str, int, bool, float(有限), None, EvidenceRef};
   set/自定义对象/NaN/inf/非 str 键一律拒;**无 `default=` 任何回退**;
   EvidenceRef 序列化为其规范 `[ID]` 编码。
3. **禁拼接 + 终字节重门**:授权门(`assert_factor_payload`)跑在**最终序列化
   字节**上——LLM 看到什么就门什么;上游碎片在序列化后若拼成裸已知 ID 会在此拒。
4. **LLM 前封精确对**(`SealedPayload`):payload 精确文本 + 注册表哈希 +
   决策 id + 席位/维度 全 SHA-256 密封;LLM 调用方只消费 SealedPayload。
5. **身份逐字节保存**:序列化 `ensure_ascii=False`、不 strip/不折叠/不大小写化
   任何字符串;身份规范化整体归 H1 前向门。

正向引用只从 `factor_refs`(= `build_factor_payload_ids` 白名单方向)构造。
"""
from __future__ import annotations

import json
import math
import os
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from workspace.research.ai_research_dept.engine.news_cards import (
    D7DecisionArtifact, verify_d7_artifact,
)
from workspace.research.ai_research_dept.engine.news_evidence import (
    EvidenceRef, RegistryError, assert_factor_payload, build_factor_payload_ids,
)
from workspace.research.ai_research_dept.engine.news_seal import seal_hash, verify_sealed

_LEDGER_NAME = "decision_ledger.jsonl"


# --------------------------------------------------- 账本(原子首写胜出)

@contextmanager
def _ledger_lock(path: Path, *, timeout: float = 30.0):
    """跨进程账本锁(原子 mkdir 自旋,与 text_store._store_lock 同型):整个
    读-查-写事务在一把锁内(BINDING #1)。"""
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


def _read_entries(path: Path) -> dict:
    """读全部账本行 → {decision_id: entry}。append-only:同 id 只允许一行,重复
    行=账本被外改,fail-closed。"""
    if not path.exists():
        return {}
    out: dict = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            did = entry["decision_id"]
            if did in out:
                raise RegistryError(
                    f"账本含重复 decision_id {did!r}——append-only 被外改,拒(fail-closed)")
            out[did] = entry
    return out


def _atomic_write_lines(entries: list, path: Path) -> None:
    fd, tmp = tempfile.mkstemp(suffix=".jsonl.tmp", dir=path.parent)
    os.close(fd)
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e, ensure_ascii=False, allow_nan=False) + "\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def record_decision(ledger_dir, decision_id: str, artifact: D7DecisionArtifact) -> dict:
    """原子首写胜出入账(BINDING #1)。调用方(账本侧)持有**权威** decision_id;
    工件必须 `verify_d7_artifact` 过门且其束 decision_id 与之逐字节相等。
    - 首写:落账 {decision_id, bundle_hash, artifact_hash, final_registry_hash,
      source_card_hash, cutoff_iso, seq};
    - 同 id 同 bundle_hash+artifact_hash 重算:幂等返回既有行;
    - 同 id 不同哈希:拒(第二个不同世界线无法成为同一决策的权威)。"""
    if not isinstance(decision_id, str) or not decision_id.strip():
        raise RegistryError(f"权威 decision_id 须非空 str(得 {decision_id!r})")
    verify_d7_artifact(artifact)
    if artifact.bundle.decision_id != decision_id:
        raise RegistryError(
            f"工件束 decision_id {artifact.bundle.decision_id!r} ≠ 账本权威 "
            f"{decision_id!r}——账本持有期望 id,工件必须逐字节匹配(BINDING #1)")
    path = _ledger_path(ledger_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _ledger_lock(path):
        entries = _read_entries(path)
        existing = entries.get(decision_id)
        if existing is not None:
            if (existing["bundle_hash"] == artifact.bundle.bundle_hash
                    and existing["artifact_hash"] == artifact.artifact_hash):
                return dict(existing)              # 逐字节相同重算 → 幂等
            raise RegistryError(
                f"decision {decision_id!r} 已入账 bundle "
                f"{existing['bundle_hash'][:12]}——首写胜出,第二个不同哈希 "
                f"{artifact.bundle.bundle_hash[:12]} 拒(BINDING #1)")
        entry = {"decision_id": decision_id,
                 "bundle_hash": artifact.bundle.bundle_hash,
                 "artifact_hash": artifact.artifact_hash,
                 "final_registry_hash": artifact.final_registry.registry_hash,
                 "source_card_hash": artifact.card.card_hash,
                 "cutoff_iso": artifact.bundle.cutoff_iso,
                 "seq": len(entries)}
        _atomic_write_lines(list(entries.values()) + [entry], path)
    return dict(entry)


def lookup_decision(ledger_dir, decision_id: str) -> "dict | None":
    return _read_entries(_ledger_path(ledger_dir)).get(decision_id)


def require_recorded(ledger_dir, decision_id: str, artifact: D7DecisionArtifact) -> dict:
    """payload 构造前的账本门(BINDING #1:先账本后 payload):工件重验过门、
    决策已入账、且账本行与工件的 bundle/artifact 哈希逐字节一致。"""
    verify_d7_artifact(artifact)
    entry = lookup_decision(ledger_dir, decision_id)
    if entry is None:
        raise RegistryError(f"decision {decision_id!r} 未入账——payload 构造前必须"
                            f"原子首写(BINDING #1)")
    if (entry["bundle_hash"] != artifact.bundle.bundle_hash
            or entry["artifact_hash"] != artifact.artifact_hash
            or artifact.bundle.decision_id != decision_id):
        raise RegistryError(
            f"工件与账本行不符(decision {decision_id!r}):账本 bundle "
            f"{entry['bundle_hash'][:12]} vs 工件 {artifact.bundle.bundle_hash[:12]}"
            f"——只有入账的那个世界线可以构造 payload")
    return entry


# --------------------------------------------------- 封闭 payload AST(BINDING #2)

def serialize_payload_ast(node) -> str:
    """封闭 AST → 精确序列化文本。节点闭集 {dict[str→node], list/tuple, str, int,
    bool, float(有限), None, EvidenceRef};其外一律拒(**无 default=str 回退**,
    BINDING #2);EvidenceRef → 规范 `[ID]` 编码;字符串逐字节保存(BINDING #5)。"""
    def convert(o):
        if isinstance(o, EvidenceRef):
            return o.encode()
        if o is None or isinstance(o, (bool, str)):
            return o
        if isinstance(o, int):
            return o
        if isinstance(o, float):
            if not math.isfinite(o):
                raise RegistryError(f"payload AST 拒非有限 float({o!r})")
            return o
        if isinstance(o, dict):
            out = {}
            for k, v in o.items():
                if not isinstance(k, str):
                    raise RegistryError(f"payload AST dict 键须 str(得 {type(k).__name__})")
                out[k] = convert(v)
            return out
        if isinstance(o, (list, tuple)):
            return [convert(x) for x in o]
        raise RegistryError(
            f"payload AST 闭集外的节点类型 {type(o).__name__}——set/自定义对象拒,"
            f"绝无 default=str(BINDING #2)")
    return json.dumps(convert(node), ensure_ascii=False, allow_nan=False)


def factor_refs(artifact: D7DecisionArtifact, *, consumer_seat: str,
                target_dimension: str) -> list:
    """正向引用白名单方向(BINDING #4):从工件**终注册表**经
    `build_factor_payload_ids` 派生 EvidenceRef 列表——payload 构造器只放这些。"""
    if not isinstance(artifact, D7DecisionArtifact):
        raise RegistryError("factor_refs 只收 D7DecisionArtifact")
    return [EvidenceRef(rid) for rid in build_factor_payload_ids(
        artifact.final_registry, consumer_seat=consumer_seat,
        target_dimension=target_dimension)]


# --------------------------------------------------- 密封 payload(咽喉点)

@dataclass(frozen=True)
class SealedPayload:
    """LLM 调用的唯一输入单元(BINDING #4):精确 payload 文本 + 注册表哈希 +
    决策/席位/维度身份,payload_hash 全 SHA-256 密封。调用方消费 payload_text,
    档案封 payload_hash + registry_hash。"""
    decision_id: str
    consumer_seat: str
    target_dimension: str
    payload_text: str
    registry_hash: str
    authorized_ids: tuple
    payload_hash: str = field(default="")

    def __post_init__(self):
        if self.payload_hash:
            verify_sealed(self._payload(), self.payload_hash, field_name="payload_hash")
        else:
            object.__setattr__(self, "payload_hash", seal_hash(self._payload()))

    def _payload(self) -> dict:
        return {"decision_id": self.decision_id, "seat": self.consumer_seat,
                "dimension": self.target_dimension, "payload_text": self.payload_text,
                "registry_hash": self.registry_hash,
                "authorized_ids": list(self.authorized_ids)}


def build_sealed_payload(payload_ast, artifact: D7DecisionArtifact, *,
                         ledger_dir, decision_id: str, consumer_seat: str,
                         target_dimension: str) -> SealedPayload:
    """**咽喉点**(BINDING #1+#3+#4):decision → 账本 → 工件 → 终注册表 → 精确
    payload 一条不可分链:
    1. `require_recorded`——决策必须已原子入账且与工件逐字节一致(先账本后 payload);
    2. 封闭 AST 序列化 → **最终字节**;
    3. `assert_factor_payload` 跑在最终字节上(LLM 看到什么门什么,BINDING #3:
       未注册引用/裸已知 ID/未授权记录在此硬失败);
    4. 密封 (payload 文本, 注册表哈希, 决策/席位/维度) 五元组 → SealedPayload。"""
    require_recorded(ledger_dir, decision_id, artifact)
    text = serialize_payload_ast(payload_ast)
    authorized = assert_factor_payload(text, artifact.final_registry,
                                       consumer_seat=consumer_seat,
                                       target_dimension=target_dimension)
    return SealedPayload(decision_id=decision_id, consumer_seat=consumer_seat,
                         target_dimension=target_dimension, payload_text=text,
                         registry_hash=artifact.final_registry.registry_hash,
                         authorized_ids=tuple(sorted(authorized)))
