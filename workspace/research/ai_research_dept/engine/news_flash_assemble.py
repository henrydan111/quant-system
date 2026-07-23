# SCRIPT_STATUS: ACTIVE — NF integration P3b: per-stock D7 artifact assembly
"""NF per-stock D7 artifact assembly (integration unit P3b).

Producer stage 3b — the point where the market-wide artifacts become ONE stock's decision
input. It selects the flashes routing to a stock, reconstructs their sealed cluster
snapshots, renders the D7 flash section, joins P3a's attribute splits, and builds the
`D7DecisionArtifact` that P4 records/executes/seals.

Declared invariants (Tier-2; see NF_UNIT_P3B_DESIGN.md):

1. **Chain binding.** Both inputs are fully verified (dict or path), both must be for this
   run's `(cutoff, ingest_class)`, and P3a's `consumed_assessed_flash_sha256` MUST equal the
   P2 artifact's `artifact_sha256` — artifacts from two different runs cannot be mixed.
2. **PIT inherited; no dated source of its own.** The only text used is bound by
   **recomputing** `content_hash` from caller-supplied raw rows against the P2 population
   (the caller's `text_store` read is not trusted; the recomputation is the binding).
3. **Selection is DERIVED**, never caller-supplied: `news_render_eligible ∧
   ts_code ∈ route.subject_codes`.
4. **Split coverage is EXACT**: every minted base fact with `importance >= D7_IMPORTANCE_FLOOR`
   has exactly one P3a split, joined by `fact_cluster_id`; a missing one is a hard error here
   (with a clearer cause than the downstream `verify_d7_artifact` coverage gate would give).
5. **Verify-not-trust throughout**: the reconstructed `ClusterSnapshot` self-verifies its
   `snapshot_id`; `render_news_flash_section` recomputes `evidence_class`;
   `build_attribute_bundle` → `verify_d7_artifact` re-derives the whole lineage.
6. **`decision_id` discipline**: exact non-empty `str` (the ledger becomes its authority in P4).
7. **NON_EVIDENTIARY.** A stock with no selected flash yields **no artifact** — an explicit
   "nothing to decide" result, never an empty-but-valid D7 artifact.
8. **The assembly result is an immutable, canonically-hashed IDENTITY that binds the D7
   artifact** (GPT P3b#1 P1). It is not a loose dict: `AssemblyProvenance` is frozen,
   self-verifying (`assembly_hash` recomputed in `__post_init__`), and its hash body
   contains `artifact_hash` — so the upstream chain (which P2/P3a artifacts, which stock,
   which facts) cannot be silently dropped, swapped, or paired with a different artifact.

Output: `(D7DecisionArtifact, AssemblyProvenance)`. P3b seals nothing on disk of its own —
**P4 is the sealing boundary**.

⚠ **FROZEN P4 OBLIGATION** (the consumer half of GPT P3b#1 P1; a precondition of the P4
unit, not optional). Without it the chain still terminates here, because the archive would
prove only the D7 artifact and not which P2/P3a inputs, which stock, or which facts produced
it. P4 MUST:

  a. **require** the `AssemblyProvenance` (no default, no `None` path) at
     `record_decision` / `seal_decision_archive`;
  b. call `require_assembly_for(assembly, artifact)` — the single binding door below — so a
     provenance for a *different* artifact is refused;
  c. write `assembly_hash` into the decision ledger entry (first-write-wins then also pins
     WHICH upstream chain owns the decision id);
  d. embed `assembly.payload` + `assembly_hash` in the sealed archive under a bumped
     `_ARCHIVE_SCHEMA` (v1 → v2, extending the strict key set), and re-verify it through
     `verify_assembly_provenance` on read-back;
  e. ship refusal tests: missing provenance, artifact-hash mismatch, and an archive
     round-trip that proves the chain survives (a v1-shaped archive must not verify).
"""
from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from workspace.research.ai_research_dept.engine.news_cards import (  # noqa: E402
    D7_IMPORTANCE_FLOOR, build_attribute_bundle, render_news_flash_section,
)
from workspace.research.ai_research_dept.engine.news_flash_assess import (  # noqa: E402
    load_assessed_flash_artifact, verify_assessed_flash_artifact,
)
from workspace.research.ai_research_dept.engine.news_flash_split import (  # noqa: E402
    _bind_source_rows, load_split_artifact, verify_split_artifact,
)
from workspace.research.ai_research_dept.engine.news_flash_typing import (  # noqa: E402
    _canonical_cutoff,
)
from workspace.research.ai_research_dept.engine.news_ingest import (  # noqa: E402
    ClusterSnapshot,
)
from workspace.research.ai_research_dept.engine.news_seal import (  # noqa: E402
    safe_kind, safe_repr, seal_hash,
)

logger = logging.getLogger("news_flash_assemble")

#: 装配身份 schema。**内容契约**版本(同 P3a 的 ARTIFACT_SCHEMA 治理约定):
#: 任何改变 `_body()` 字段集合/取值派生方式的修改都必须升版,否则两种派生会共享
#: 一个哈希空间(旧档案的 assembly_hash 会与新派生冲撞或静默不可复算)。
ASSEMBLY_SCHEMA = "nf_d7_assembly_v1"

#: 装配载荷顶层严格键集(多/少键 = 拒;同 news_archive 的 _ARCHIVE_KEYS 约定)
_ASSEMBLY_KEYS = frozenset({
    "schema", "artifact_hash", "ts_code", "decision_id", "cutoff", "ingest_class",
    "assessed_sha", "split_sha", "selected_facts", "n_splits_used", "assembly_hash",
})


class NothingToDecide(Exception):
    """No flash routes to this stock at this cutoff (invariant 7). An explicit result, not
    an empty D7 artifact — a decision with no evidence must not be manufactured."""


@dataclass(frozen=True)
class AssemblyProvenance:
    """P3b 的**不可变、规范哈希**装配身份(invariant 8;GPT P3b#1 P1)。

    旧版返回一个普通 dict:P4 的三个接口都只收 `D7DecisionArtifact`,那个 dict
    无处可传、无处可封存,最终档案只能证明 D7 工件本体,**证明不了它来自哪次
    P2/P3a 运行、针对哪只股票、选了哪些事实**——上游链在此被丢弃。

    现在它是一等身份:frozen,字段恰基础类型,`assembly_hash` 在 `__post_init__`
    **重算**(自称不符 = 硬失败),且哈希体内含 `artifact_hash` ——装配结果与 D7
    工件互相绑定,换任一方哈希即变。P4 据此把整条链钉进账本与档案。"""
    artifact_hash: str
    ts_code: str
    decision_id: str
    cutoff_iso: str
    ingest_class: str
    consumed_assessed_flash_sha256: str
    consumed_d7_split_sha256: str
    #: 选中事实的 fact_occurrence_id(按其排序;P3b 的选择基础)
    selected_fact_occurrence_ids: tuple
    n_splits_used: int
    assembly_hash: str = field(default="")

    def __post_init__(self):
        for name in ("artifact_hash", "ts_code", "decision_id", "cutoff_iso",
                     "ingest_class", "consumed_assessed_flash_sha256",
                     "consumed_d7_split_sha256"):
            v = getattr(self, name)
            if type(v) is not str or not v.strip():
                raise ValueError(
                    f"AssemblyProvenance.{name} 须恰 str 非空(得 {safe_repr(v)})——"
                    f"子类/非 str 会让身份的两次读取脱钩,静态拒")
        ids = tuple(self.selected_fact_occurrence_ids)
        if not ids:
            raise ValueError(
                "AssemblyProvenance 选中事实为空——绝不产无证据的装配身份(invariant 7)")
        for fid in ids:
            if type(fid) is not str or not fid.strip():
                raise ValueError(
                    f"selected_fact_occurrence_ids 成员须恰 str 非空(得 {safe_repr(fid)})")
        object.__setattr__(self, "selected_fact_occurrence_ids", ids)
        if type(self.n_splits_used) is not int or self.n_splits_used < 0:
            raise ValueError(
                f"n_splits_used 须恰非负 int(得 {safe_repr(self.n_splits_used)};"
                f"bool 亦拒——`type(x) is int` 对 True 为假)")
        recomputed = seal_hash(self._body())
        if self.assembly_hash and self.assembly_hash != recomputed:
            raise ValueError(
                f"assembly_hash 伪造:自称 {self.assembly_hash[:12]} "
                f"重算 {recomputed[:12]}——拒")
        if not self.assembly_hash:
            object.__setattr__(self, "assembly_hash", recomputed)

    def _body(self) -> dict:
        return {"schema": ASSEMBLY_SCHEMA,
                "artifact_hash": self.artifact_hash,
                "ts_code": self.ts_code,
                "decision_id": self.decision_id,
                "cutoff": self.cutoff_iso,
                "ingest_class": self.ingest_class,
                "assessed_sha": self.consumed_assessed_flash_sha256,
                "split_sha": self.consumed_d7_split_sha256,
                "selected_facts": list(self.selected_fact_occurrence_ids),
                "n_splits_used": self.n_splits_used}

    @property
    def n_selected(self) -> int:
        return len(self.selected_fact_occurrence_ids)

    @property
    def payload(self) -> dict:
        """P4 封存进档案的**纯 JSON** 载荷(含自称 `assembly_hash`;读回一律经
        `verify_assembly_provenance` 重算,不信自称值)。"""
        return {**self._body(), "assembly_hash": self.assembly_hash}


def verify_assembly_provenance(payload) -> AssemblyProvenance:
    """从纯 JSON 载荷重建装配身份并**重算**其哈希(recompute-not-trust)。

    P4 读回档案时的唯一门:严格键集 + schema 值 + 逐字段类型门 + 哈希重算。"""
    if type(payload) is not dict:
        raise ValueError(f"装配载荷须恰 dict(得 {safe_kind(payload)})——拒")
    if set(payload) != _ASSEMBLY_KEYS:
        raise ValueError(
            f"装配载荷顶层键集不符 {ASSEMBLY_SCHEMA} schema——多/少键 = 拒")
    schema = payload["schema"]
    if type(schema) is not str or schema != ASSEMBLY_SCHEMA:
        raise ValueError(f"装配载荷 schema {safe_repr(schema)} ≠ {ASSEMBLY_SCHEMA}——拒")
    facts = payload["selected_facts"]
    if type(facts) is not list:
        raise ValueError(f"selected_facts 须恰 list(得 {safe_kind(facts)})——拒")
    return AssemblyProvenance(
        artifact_hash=payload["artifact_hash"], ts_code=payload["ts_code"],
        decision_id=payload["decision_id"], cutoff_iso=payload["cutoff"],
        ingest_class=payload["ingest_class"],
        consumed_assessed_flash_sha256=payload["assessed_sha"],
        consumed_d7_split_sha256=payload["split_sha"],
        selected_fact_occurrence_ids=tuple(facts),
        n_splits_used=payload["n_splits_used"],
        assembly_hash=payload["assembly_hash"])      # 自称 → __post_init__ 重算比对


def require_assembly_for(assembly, artifact) -> AssemblyProvenance:
    """**P4 必须调用的单一绑定门**(FROZEN P4 OBLIGATION b)。

    装配身份必须恰为 `AssemblyProvenance`、自哈希自洽,且其 `artifact_hash` /
    `decision_id` 与该 D7 工件逐字节相符——他次装配的出处配不上这个工件。"""
    if type(assembly) is not AssemblyProvenance:
        raise ValueError(
            f"装配出处须恰 AssemblyProvenance(得 {safe_kind(assembly)})——"
            f"P4 不接受普通 dict/子类:上游链必须是自验身份,拒")
    assembly = verify_assembly_provenance(assembly.payload)     # 重算,不信实例自称
    if assembly.artifact_hash != artifact.artifact_hash:
        raise ValueError(
            f"装配出处绑定的工件 {assembly.artifact_hash[:12]} ≠ 供给的 D7 工件 "
            f"{artifact.artifact_hash[:12]}——出处与工件不成对,拒")
    if assembly.decision_id != artifact.bundle.decision_id:
        raise ValueError(
            f"装配出处 decision_id {assembly.decision_id!r} ≠ 工件束 "
            f"{artifact.bundle.decision_id!r}——拒")
    return assembly


def _verified_inputs(cut, ingest_class: str, assessed_artifact, split_artifact):
    """Invariant 1: verify both artifacts, identity-match both to this run, and require the
    split artifact to have been produced FROM this exact assessed artifact."""
    p2 = (verify_assessed_flash_artifact(assessed_artifact)
          if isinstance(assessed_artifact, dict)
          else load_assessed_flash_artifact(assessed_artifact))
    p3a = (verify_split_artifact(split_artifact)
           if isinstance(split_artifact, dict)
           else load_split_artifact(split_artifact))
    for name, art in (("assessed-flash", p2), ("D7 split", p3a)):
        if art.get("cutoff_iso") != cut.isoformat() \
                or art.get("ingest_class") != ingest_class:
            raise ValueError(
                f"{name} artifact ({art.get('ingest_class')}, {art.get('cutoff_iso')}) "
                f"does not match this run ({ingest_class}, {cut.isoformat()}) — refusing")
    if p3a.get("consumed_assessed_flash_sha256") != p2.get("artifact_sha256"):
        raise ValueError(
            f"D7 split artifact was produced from a DIFFERENT assessed-flash artifact "
            f"(consumed {safe_repr(p3a.get('consumed_assessed_flash_sha256'))} vs supplied "
            f"{safe_repr(p2.get('artifact_sha256'))}) — artifacts from two runs cannot be "
            f"mixed, refusing (chain binding)")
    return p2, p3a


def _select_for_stock(p2: dict, ts_code: str) -> list[dict]:
    """Invariant 3: derived selection — never a caller-supplied flash list."""
    sel = [a for a in p2["assessed"]
           if a.get("news_render_eligible") is True
           and ts_code in a["route"]["subject_codes"]]
    return sorted(sel, key=lambda a: a["cluster"]["fact_occurrence_id"])


def _reconstruct_cluster(payload: dict) -> ClusterSnapshot:
    """Invariant 5: rebuild the sealed snapshot from P2's payload; `__post_init__`
    recomputes `snapshot_id`, and the payload itself is covered by P2's artifact seal."""
    return ClusterSnapshot(
        cluster_id=payload["cluster_id"], algo_version=payload["algo_version"],
        cutoff_iso=payload["cutoff_iso"],
        members=tuple(dict(m) for m in payload["members"]),
        fact_occurrence_id=payload["fact_occurrence_id"],
        cluster_first_visible_at_iso=payload["cluster_first_visible_at_iso"],
        n_outlets=int(payload["n_outlets"]))


def assemble_stock_artifact(cutoff, *, ingest_class: str, ts_code: str, decision_id: str,
                            assessed_artifact, split_artifact, source_rows) -> tuple:
    """Assemble ONE stock's `D7DecisionArtifact` for `cutoff`. Returns
    `(artifact, AssemblyProvenance)` — the second is the immutable, canonically-hashed
    identity of the whole upstream chain, bound to `artifact.artifact_hash` (invariant 8);
    P4 must require it and seal it. Raises `NothingToDecide` when nothing routes here."""
    cut = _canonical_cutoff(cutoff)
    if type(decision_id) is not str or not decision_id.strip():
        raise ValueError("decision_id 须恰 str 非空——拒(P4 的账本随后持有其权威)")
    if type(ts_code) is not str or not ts_code.strip():
        raise ValueError("ts_code 须恰 str 非空——拒")
    p2, p3a = _verified_inputs(cut, ingest_class, assessed_artifact, split_artifact)

    selected = _select_for_stock(p2, ts_code)
    if not selected:
        raise NothingToDecide(
            f"{ts_code} @ {cut.isoformat()}: 无路由命中的快讯——不产 D7 工件"
            f"(绝不制造无证据的决策,invariant 7)")

    # invariant 2: the only text used is bound by RECOMPUTED content_hash
    bound = _bind_source_rows(source_rows, {a["content_hash"] for a in selected})
    assessed = [{
        "cluster": _reconstruct_cluster(a["cluster"]),
        "typing": a["typing"],
        # render recomputes evidence_class from typing+route, so it re-derives rather than
        # trusting P2's class; `content` is the hash-bound source text
        "route": {"primary_route": a["route"]["primary_route"],
                  "content": bound[a["content_hash"]]},
        "evidence_class": a["evidence_class"],
        "coordination_fired": a["coordination_fired"],
    } for a in selected]

    card, records, base_facts = render_news_flash_section(assessed, cut)

    # invariant 4: exact split coverage, joined by fact_cluster_id
    splits_by_fact = {s["fact_occurrence_id"]: s["attributes"] for s in p3a["splits"]}
    splits = []
    for bf in base_facts:
        if bf.importance < D7_IMPORTANCE_FLOOR:
            continue
        attrs = splits_by_fact.get(bf.fact_cluster_id)
        if attrs is None:
            raise ValueError(
                f"{ts_code}: 基事实 {bf.base_record_id}(事实 {bf.fact_cluster_id})"
                f"在 D7 split 工件中无对应拆分——覆盖不全,拒(invariant 4)")
        splits.append({"base_record_id": bf.base_record_id, "attributes": dict(attrs)})

    artifact = build_attribute_bundle(splits, base_facts, records, card=card,
                                      decision_id=decision_id, cutoff=cut)
    # invariant 8: the chain identity — binds the artifact it was assembled FOR, so P4
    # cannot seal this artifact against a different upstream chain (or none at all)
    assembly = AssemblyProvenance(
        artifact_hash=artifact.artifact_hash,
        ts_code=ts_code, decision_id=decision_id,
        cutoff_iso=cut.isoformat(), ingest_class=ingest_class,
        consumed_assessed_flash_sha256=p2["artifact_sha256"],
        consumed_d7_split_sha256=p3a["artifact_sha256"],
        selected_fact_occurrence_ids=tuple(a["cluster"]["fact_occurrence_id"]
                                           for a in selected),
        n_splits_used=len(splits))
    logger.info("%s @ %s: %d flashes selected, %d D7 splits -> artifact %s (assembly %s)",
                ts_code, cut.isoformat(), len(selected), len(splits),
                artifact.artifact_hash[:12], assembly.assembly_hash[:12])
    return artifact, assembly
