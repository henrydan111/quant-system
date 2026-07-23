# P4a shared test helper: derive a VALID AssemblyProvenance for any test artifact.
# (The engine tests predate P3b; record/seal now require the assembly identity, so
# every ledger/archive test derives one from the artifact it already built. The
# derivation is pure → the same artifact always yields the same assembly_hash,
# which is exactly what the record→seal ledger cross-check demands.)
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from workspace.research.ai_research_dept.engine.news_cards import (  # noqa: E402
    D7_IMPORTANCE_FLOOR,
)
from workspace.research.ai_research_dept.engine.news_flash_assemble import (  # noqa: E402
    AssemblyProvenance,
)


def asm_for(artifact, *, ts_code="688981.SH", ingest_class="forward",
            assessed_sha="a" * 64, split_sha="b" * 64):
    """A valid assembly identity for `artifact`: fact set = the minted base facts'
    placeholders (or a fixed placeholder for context-only artifacts, which mint
    none); split count = the artifact's actual >=floor base-fact count (the exact
    relation `require_assembly_for` cross-checks)."""
    facts = tuple(sorted({bf.fact_cluster_id for bf in artifact.base_facts}))
    if not facts:
        facts = ("fam_v3:test_ctx@20250127",)
    high = [bf for bf in artifact.base_facts
            if bf.importance >= D7_IMPORTANCE_FLOOR]
    return AssemblyProvenance(
        artifact_hash=artifact.artifact_hash, ts_code=ts_code,
        decision_id=artifact.bundle.decision_id,
        cutoff_iso=artifact.bundle.cutoff_iso, ingest_class=ingest_class,
        consumed_assessed_flash_sha256=assessed_sha,
        consumed_d7_split_sha256=split_sha,
        selected_fact_occurrence_ids=facts, n_splits_used=len(high))
