# SCRIPT_STATUS: ACTIVE — NF integration P1: market-wide per-day news-flash typing driver
"""NF-flash typing pass (integration unit P1).

The **producer's first stage**: classify each day's cutoff-visible news flashes into
the NF typing schema so the per-stock decision units (P2→P4) can `assess_flash` /
`render_news_flash_section` without re-typing. Market-wide, once per (day, panel).

**This is a driver, not a new classifier.** The classifier `news_ingest.type_batch`
already exists and is tested (fail-closed enum coercion, exact-idx matching,
literal-bool guards, injectable `call_fn`, "payload is data not instructions" system
prompt). The PIT visibility gate is **inherited** from `text_store.load_text`
(returns only rows with `decision_visible_at <= cutoff`, and `ingest_class`
physically isolates the forward panel from history_bulk). P1 adds: dedup to distinct
content, batch, PIT-stamp, and a self-describing typed-flash artifact.

Declared invariants (Tier-2 — the review judges these; see
NF_INTEGRATION_SEQUENCING.md):

1. **PIT: typing input is cutoff-bound.** Only `load_text`-filtered rows
   (`decision_visible_at <= cutoff`) are typed; every typed row's
   `decision_visible_at` is carried verbatim and re-asserted `<= cutoff`. The
   classifier sees ONLY `content` (no timestamps), so typing itself cannot leak
   future data — PIT correctness is entirely about *which* flashes are in the
   population, which `load_text` owns.
2. **ingest_class isolation.** A forward run reads ONLY `ingest_class='forward'`;
   history_bulk is unreachable (inherited from `load_text` B1). The artifact records
   the class; a forward decision must never consume a history_bulk-typed artifact.
3. **Typed once per content identity.** Each distinct `content_hash` is typed exactly
   once; the downstream join key is `content_hash`, never row position. NB the store's
   content basis is `[src, datetime, title, content, channels]`, so the same wording
   from a different outlet or at a different time is a DISTINCT `content_hash` (a
   distinct occurrence) and is typed separately — the store already guarantees
   `content_hash` uniqueness on ingest, and P1's own dedup is defensive.
4. **Deterministic + idempotent.** Same (cutoff, panel, content set, call_fn) →
   byte-identical `artifact_sha256` (distinct flashes sorted by `content_hash`;
   per-batch local idx; output sorted). Re-running never changes a type unless the
   input population changes.
5. **Immutable, self-describing, fail-closed persistence.** The artifact carries
   `cutoff_iso` + `ingest_class` + `population_hash` (over the typed content set) +
   `artifact_sha256`; load re-verifies both hashes and refuses a tampered/mismatched
   artifact. The cutoff is canonicalized ONCE (Shanghai-naive, as `text_store` does)
   and the path is keyed by that full cutoff to MICROSECOND precision (so 09:30 vs
   18:00, two sub-second cutoffs, and two tz-offset cutoffs all get distinct files).
   The cutoff is **microsecond-max**: a sub-microsecond (nanosecond) cutoff is refused,
   so the allowed cutoff domain is exactly what the path encodes → path identity is
   bijective (no two distinct cutoffs share a file, no cutoff maps to two). The write is
   **write-once / first-write-wins** — a second
   typing run with different content is refused, never silently overwritten (a real
   LLM can return different valid types; a consumed version must stay stable). P2
   reads by (cutoff, ingest_class) and binds the `artifact_sha256` it verifies; P4
   binds the consumed SHA into the sealed decision.
6. **NON_EVIDENTIARY.** Zero flashes → empty artifact (not an error); every artifact
   carries the replay-class marker (this is replay infra until FORWARD_PREREG).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import tempfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from data_infra.text_store import load_text, to_cn_naive  # noqa: E402
from workspace.research.ai_research_dept.engine.news_ingest import type_batch  # noqa: E402
from workspace.research.ai_research_dept.engine.news_seal import seal_hash  # noqa: E402

logger = logging.getLogger("news_flash_typing")

ARTIFACT_SCHEMA = "nf_typed_flash_v1"
EVIDENCE_CLASS = "nf_typed_flash/NON_EVIDENTIARY"
INGEST_CLASSES = frozenset({"forward", "history_bulk"})
BATCH = 10

#: the NF typing fields type_batch emits (macro batch adds macro_type; P1 is the
#: per-stock news path, NOT the macro seat — macro=False here by design)
_TYPING_FIELDS = ("event_type", "verification_status", "content_kind",
                  "direction", "importance", "is_rumor")
#: provenance carried per distinct flash (content_hash is the join key). `src` is
#: the outlet (raw col, e.g. "sina"); the stamp `source` col is the store name
#: ("news") for every row, so it is not carried.
_PROV_FIELDS = ("content_hash", "object_id_hash", "src", "decision_visible_at")


def _canonical_cutoff(cutoff):
    """Canonicalize to Shanghai-naive AND enforce the precision contract (GPT-P1
    re-review#3, user-decided): a decision cutoff is **microsecond-max**. `pd.Timestamp`
    carries nanoseconds but the artifact path encodes only microseconds (`%f`), so a
    sub-microsecond cutoff would make the path non-injective. Rejecting `nanosecond != 0`
    makes the allowed cutoff domain EXACTLY what the path losslessly encodes — path
    identity is bijective over every valid cutoff, closing the identity class. Decision
    cutoffs are session times (whole-second in practice); sub-microsecond is nonsensical
    here."""
    cut = to_cn_naive(cutoff)
    if cut.nanosecond != 0:
        raise ValueError(
            f"cutoff has sub-microsecond precision (nanosecond={cut.nanosecond}) — a "
            f"decision cutoff is microsecond-max; refuse (the artifact identity path "
            f"encodes microseconds only, GPT-P1 re-review#3)")
    return cut


def _iso(v) -> str:
    """CN-naive ISO string — timestamps are stored as strings so the artifact hash is
    deterministic and canon never touches a live datetime object."""
    return pd.Timestamp(v).isoformat()


def _distinct_flashes(df: pd.DataFrame, cutoff: pd.Timestamp) -> list[dict]:
    """Dedup cutoff-visible rows to distinct `content_hash`, carrying the EARLIEST
    (most conservative) visibility as the representative provenance. Deterministic
    order by `content_hash`. Re-asserts the PIT bound as defence-in-depth."""
    need = {"content_hash", "object_id_hash", "src", "content", "decision_visible_at"}
    missing = need - set(df.columns)
    if missing:
        raise ValueError(f"news rows missing required columns {sorted(missing)} "
                         f"(must come through text_store.load_text)")
    v = df.copy()
    v["decision_visible_at"] = pd.to_datetime(v["decision_visible_at"], errors="coerce")
    if v["decision_visible_at"].isna().any():
        raise ValueError("decision_visible_at has NaT rows — refusing (text_store "
                         "stamps it; a NaT means the row bypassed ingest_rows)")
    # invariant 1 defence-in-depth: load_text already filtered, re-assert here
    if (v["decision_visible_at"] > cutoff).any():
        raise ValueError(f"{int((v['decision_visible_at'] > cutoff).sum())} rows visible "
                         f"after cutoff {cutoff} — load_text PIT gate violated")
    if v["content_hash"].map(lambda ch: not isinstance(ch, str) or not ch).any():
        raise ValueError("content_hash must be a non-empty str on every row")
    # deterministic dedup by content_hash; sorted so the EARLIEST visibility (tie-break
    # object_id_hash) is the representative provenance kept per distinct flash
    flash_map_out: dict[str, dict] = {}
    for _, r in v.sort_values(
            ["content_hash", "decision_visible_at", "object_id_hash"]).iterrows():
        ch = r["content_hash"]
        if ch in flash_map_out:
            continue                                     # earliest visibility kept (sorted)
        flash_map_out[ch] = {
            "content_hash": ch,
            "object_id_hash": r["object_id_hash"],
            "src": r["src"],
            "content": str(r["content"]),
            "decision_visible_at": _iso(r["decision_visible_at"]),
        }
    return [flash_map_out[k] for k in sorted(flash_map_out)]


def type_day_flashes(cutoff, *, ingest_class: str, call_fn,
                     store_dir=None, batch: int = BATCH,
                     require_exists: bool = False) -> dict:
    """Market-wide per-day NF-flash typing. Returns a self-describing artifact dict.

    `call_fn(messages) -> reply` (reply has `.text`) is injected — the CLI wires the
    real Ark route; tests inject a stub. `cutoff` is the decision cutoff; only
    `decision_visible_at <= cutoff` rows (of the requested `ingest_class` panel) are
    typed.

    GPT-P1 Blocker-1: the FORWARD panel is **always** fail-closed — a missing forward
    store is a config error ("data unavailable"), never a legitimate zero-news result;
    it must not be mislabeled as a valid NON_EVIDENTIARY empty artifact. history_bulk
    replay stays tolerant by default (`require_exists` opt-in) since a bulk panel for a
    day that was never backfilled is legitimately empty. Either way, an EXISTING panel
    with genuinely no rows before `cutoff` yields an empty artifact (that is real
    'no news at cutoff', not 'source unavailable')."""
    if ingest_class not in INGEST_CLASSES:
        raise ValueError(f"ingest_class must be ∈ {sorted(INGEST_CLASSES)} "
                         f"(a forward decision must not consume history_bulk types)")
    # GPT-P1 re-review#2: canonicalize the cutoff ONCE, Shanghai-naive, the same way
    # text_store does — this single value drives load, the PIT re-assert, cutoff_iso,
    # and the path, so a tz-aware or sub-second cutoff can never disagree between them.
    cut = _canonical_cutoff(cutoff)
    req = ingest_class == "forward" or bool(require_exists)   # forward: hard fail-closed
    df = load_text("news", cut, store_dir=store_dir, ingest_class=ingest_class,
                   require_exists=req)
    flashes = _distinct_flashes(df, cut) if not df.empty else []
    typed: list[dict] = []
    n_batches = (len(flashes) + batch - 1) // batch
    for bi in range(n_batches):
        chunk = flashes[bi * batch:(bi + 1) * batch]
        items = [{"idx": j, "content": chunk[j]["content"]} for j in range(len(chunk))]
        results = type_batch(items, call_fn, macro=False)   # by-idx, fail-closed enums
        by_idx = {r["idx"]: r for r in results}
        for j, fl in enumerate(chunk):
            t = by_idx[j]
            typed.append({
                **{k: fl[k] for k in _PROV_FIELDS},
                "content_preview": fl["content"][:200],     # audit only; full text in store
                "typing": {k: t[k] for k in _TYPING_FIELDS},
            })
        if n_batches > 1:
            logger.info("typed batch %d/%d (%d flashes)", bi + 1, n_batches, len(typed))
    typed.sort(key=lambda x: x["content_hash"])             # invariant 4
    population_hash = seal_hash(sorted(x["content_hash"] for x in typed))
    artifact = {
        "artifact_schema": ARTIFACT_SCHEMA,
        "cutoff_iso": cut.isoformat(),
        "ingest_class": ingest_class,
        "evidence_class": EVIDENCE_CLASS,
        "population_hash": population_hash,
        "n_flashes": len(typed),
        "typed": typed,
    }
    artifact["artifact_sha256"] = seal_hash(artifact)
    return artifact


class TypedFlashConflictError(ValueError):
    """GPT-P1 Blocker-2: a typed-flash artifact for this (ingest_class, cutoff) already
    exists with DIFFERENT content. The artifact is write-once/first-write-wins — a
    second typing run (a real LLM can legitimately return different valid types) must
    NOT overwrite the version a downstream decision may already have consumed."""


def _artifact_path(out_dir, cutoff_iso: str, ingest_class: str) -> Path:
    # GPT-P1 Blocker-2 + re-review#2/#3: canonicalize (Shanghai-naive), enforce the
    # microsecond-max contract (defence-in-depth at the encoding boundary — a
    # hand-built artifact with a nanosecond cutoff_iso is refused here too), and encode
    # the FULL cutoff to MICROSECOND precision. `%f` over a microsecond-max domain is
    # bijective, so distinct cutoffs never share a path and one cutoff never maps to two.
    cut = _canonical_cutoff(cutoff_iso)
    stamp = cut.strftime("%Y%m%dT%H%M%S%f")
    return Path(out_dir) / f"nf_typed_flash_{ingest_class}_{stamp}.json"


def write_typed_flash_artifact(artifact: dict, out_dir) -> Path:
    """Immutable, atomic write — **write-once / first-write-wins** per (ingest_class,
    cutoff) (GPT-P1 Blocker-2). If the path already holds a byte-identical artifact the
    write is idempotent (returns it); if it holds a DIFFERENT artifact the write is
    refused (`TypedFlashConflictError`) so a re-typing can never silently replace a
    consumed version. Atomic (fsync + os.replace) for the first write."""
    from research_orchestrator.file_lock import file_lock
    path = _artifact_path(out_dir, artifact["cutoff_iso"], artifact["ingest_class"])
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(artifact, ensure_ascii=False, indent=1)
    # the exists-check + write are serialized so write-once actually holds under a
    # concurrent re-run, not merely advisory (same pattern as seal_decision_archive)
    with file_lock(path.parent / (path.name + ".lock")):
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing == artifact:
                return path                              # idempotent re-write
            raise TypedFlashConflictError(
                f"typed-flash artifact for ({artifact['ingest_class']}, "
                f"{artifact['cutoff_iso']}) already exists with different content "
                f"(existing {existing.get('artifact_sha256', '')[:12]} vs new "
                f"{artifact.get('artifact_sha256', '')[:12]}) — write-once, refusing to "
                f"overwrite a possibly-consumed version")
        fd, tmp = tempfile.mkstemp(suffix=".json.tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(blob)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    return path


def verify_typed_flash_artifact(artifact: dict) -> dict:
    """Full structural + seal verification of a typed-flash artifact **dict** (schema,
    artifact_sha256, population_hash, content_hash uniqueness, n_flashes count). This is
    the SINGLE verification any consumer must run — whether it read the artifact from disk
    or was handed a dict — so a dict input can never bypass the seal check (GPT-P2 P1-#2).
    Returns the same dict on success; raises `ValueError` on any mismatch."""
    if not isinstance(artifact, dict) or artifact.get("artifact_schema") != ARTIFACT_SCHEMA:
        raise ValueError("not an nf_typed_flash_v1 artifact")
    body = {k: v for k, v in artifact.items() if k != "artifact_sha256"}
    if seal_hash(body) != artifact.get("artifact_sha256"):
        raise ValueError("artifact_sha256 mismatch — typed-flash artifact tampered")
    typed = artifact.get("typed")
    if not isinstance(typed, list):
        raise ValueError("typed-flash artifact 'typed' must be a list")
    hashes = [x["content_hash"] for x in typed]
    if len(set(hashes)) != len(hashes):
        raise ValueError("typed-flash artifact has duplicate content_hash")
    if artifact.get("n_flashes") != len(typed):
        raise ValueError("typed-flash artifact n_flashes != len(typed)")
    if seal_hash(sorted(hashes)) != artifact.get("population_hash"):
        raise ValueError("population_hash mismatch — typed set altered")
    return artifact


def load_typed_flash_artifact(path) -> dict:
    """Load from disk + fully verify (invariant 5). A tampered artifact is refused."""
    return verify_typed_flash_artifact(json.loads(Path(path).read_text(encoding="utf-8")))


def _ark_call_fn():
    """Production call_fn: the frozen text_event_typing route (doubao mini)."""
    from workspace.research.ai_research_dept.engine import llm_config as L
    return lambda msgs: L.call("text_event_typing", msgs, max_tokens=2000)


def main() -> int:
    ap = argparse.ArgumentParser(description="NF-flash typing pass (integration P1)")
    ap.add_argument("--cutoff", required=True, help="decision cutoff, e.g. '2025-01-27 18:00:00'")
    ap.add_argument("--ingest-class", default="history_bulk", choices=sorted(INGEST_CLASSES),
                    help="forward = live panel; history_bulk = NON_EVIDENTIARY replay (default)")
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("ai_layer.ark_client").setLevel(logging.WARNING)
    from workspace.research.ai_research_dept.engine import config as C
    out_dir = Path(args.out_dir) if args.out_dir else C.OUT_ROOT / "nf_typed_flash"
    artifact = type_day_flashes(args.cutoff, ingest_class=args.ingest_class,
                                call_fn=_ark_call_fn())
    path = write_typed_flash_artifact(artifact, out_dir)
    logger.info("typed %d flashes @ %s (%s) -> %s",
                artifact["n_flashes"], artifact["cutoff_iso"], args.ingest_class, path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
