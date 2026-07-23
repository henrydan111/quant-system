# SCRIPT_STATUS: ACTIVE — NF integration P3a: market-wide D7 attribute splitting (v1: deterministic)
"""NF D7 attribute splitting (integration unit P3a).

Producer stage 3a. For every assessed flash that will become a POSITIVE base fact with
`importance >= D7_IMPORTANCE_FLOOR`, produce the D7 attribute texts that
`build_attribute_bundle` requires. `verify_d7_artifact` enforces **total coverage** —
every importance>=4 positive base fact must be split exactly once — so this artifact is
what makes the per-stock D7 assembly (P3b) possible at all.

**Market-wide, keyed by `fact_occurrence_id`.** A flash relevant to 50 stocks is split
ONCE, not 50 times: `render_news_flash_section` mints each base fact with
`fact_cluster_id == cluster.fact_occurrence_id`, so P3b joins a minted `base_record_id`
to its attributes through that stable key.

**v1 IS FULLY DETERMINISTIC — NO LLM.** The unit began as an LLM extraction step; three
review rounds established that no partial-text scheme can be trusted for a SCORING input:
- a free-written attribute invents facts ("增厚年营收 15%" from a source that never said it);
- a verbatim span proves characters exist, not that the claim survives its context
  ("It is false that ACME signed …" → the span inverts the meaning);
- sentence expansion fixes only the same-sentence subset — a qualifier in a NEIGHBOURING
  sentence, a headline/body newline, or an abbreviation like "U.S." still de-contextualizes.
Chasing the "right" context window is an unbounded NLP problem, so v1 does not truncate at
all: **`fact` is the WHOLE hash-bound source** (sanitized). With that, the model has nothing
left to contribute — `economic_linkage` and `timing` are deferred, `source_status` is
derived — so the LLM is removed entirely. Zero hallucination surface, zero LLM cost, and
the richer decomposition returns only with a grounding scheme that can verify cross-sentence
semantic relations.

Declared invariants (Tier-2; the review target):

1. **Source is BOUND to P2 by recomputation, not trust (PIT inherited).** The caller
   supplies raw news rows; P3a **recomputes** each row's canonical `content_hash`
   (`text_store.content_hash_for`) and binds only rows whose hash equals a P2 population
   hash. Since `content_hash` is a function of the row, this *proves* the text is the one
   behind P2's record — a substituted/edited (e.g. future) text changes the hash and simply
   stops matching. A population member with no hash-verified row is a hard error. Identity
   `(cutoff, ingest_class)` must equal P2's, so the PIT boundary is inherited from P2 (and
   through it P1). *(The CLI reads text_store to obtain the rows; that read is not trusted —
   the recomputation is what binds them.)*
2. **P2 binding.** The P2 artifact is fully verified whether passed as a dict or a path;
   its `(cutoff_iso, ingest_class)` must match this run; its `artifact_sha256` is bound
   into P3a's artifact.
3. **Population is DERIVED, never caller-supplied.** Exactly
   `{assessed : evidence_class ∈ POSITIVE_CLASSES and typing.importance >= 4}` computed from
   the verified P2 artifact — one split per member, no extras (precisely what
   `verify_d7_artifact`'s split-coverage gate will demand).
4. **`source_status` is DERIVED** from the verified `verification_status`/`is_rumor`. It is
   a PENALTY-bearing attribute (`allowed_uses={penalty,bear}`, dimension `confidence_cap`),
   so it must never be model-authored.
5. **`fact` is the WHOLE hash-bound source, sanitized — never a model-chosen fragment.**
   Nothing is truncated, so negation / attribution / conditional context, cross-sentence
   qualifiers, headline-body newlines and abbreviations cannot de-contextualize it. It is
   validated exact-`str` + substantive with the frozen predicate. `fact` is mandatory (the
   D7 rebuild refuses a split without it). **`economic_linkage` and `timing` are DEFERRED**
   — `economic_linkage` becomes a `factor_positive` `fundamental_link` attribute (a SCORING
   input), and a causal-transmission claim cannot be grounded by quotation.
6. **Deterministic + idempotent by construction** (no LLM, no injected callable); immutable
   write-once artifact on the canonical microsecond-cutoff path (same discipline as P1/P2).
   Re-running on the same inputs reproduces the same `artifact_sha256` exactly.
7. **NON_EVIDENTIARY.** Empty population → empty artifact; replay marker.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import tempfile
import unicodedata as _ud
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from data_infra.text_store import content_hash_for  # noqa: E402
from workspace.research.ai_research_dept.engine.news_cards import (  # noqa: E402
    D7_IMPORTANCE_FLOOR, has_substantive_text, sanitize_text,
)
from workspace.research.ai_research_dept.engine.news_flash_assess import (  # noqa: E402
    load_assessed_flash_artifact, verify_assessed_flash_artifact,
)
from workspace.research.ai_research_dept.engine.news_flash_typing import (  # noqa: E402
    _canonical_cutoff,
)
from workspace.research.ai_research_dept.engine.news_seal import seal_hash  # noqa: E402

logger = logging.getLogger("news_flash_split")

#: GPT-P3a re-review#4 (P1): the schema is bumped to **v2** because the CONTRACT changed —
#: v1 artifacts carry LLM-chosen (possibly truncated) `fact` text. Leaving the name at v1
#: meant an old sealed artifact, or a re-sealed one with `fact_mode="llm_span_v0"`, still
#: verified, so P3b could consume exactly the de-contextualized facts this arc eliminated.
#: The verifier now REQUIRES the exact `fact_mode`, and the artifact filename tracks the
#: schema so a stale v1 file cannot occupy a v2 path.
ARTIFACT_SCHEMA = "nf_d7_split_v2"
EVIDENCE_CLASS = "nf_d7_split/NON_EVIDENTIARY"
#: how `fact` was produced — recorded AND enforced at the read boundary
FACT_MODE = "deterministic_whole_source_v1"
#: categories the frozen `sanitize_text` DELETES (it does NFKC then drops Cc/Cf). Mirrored
#: here so the two cannot drift.
_SANITIZER_DELETES = ("Cc", "Cf")


def _space_out_deleted_controls(s: str) -> str:
    """GPT-P3a re-review#5 (P2): every character the frozen sanitizer would DELETE is first
    replaced by a SPACE, so it can never fuse the tokens on either side.

    Enumerating separators was the wrong shape — CR/LF was fixed, then NEL / Tab / ZWJ were
    still fusing (`does<NEL>not` → `doesnot`), which silently destroys the very negation the
    whole-source contract exists to preserve. This mirrors the sanitizer's own deletion
    predicate (NFKC, then `category in {Cc, Cf}`) instead of listing characters, so ANY such
    codepoint — present or future — becomes a boundary rather than a fusion.
    `sanitize_text`'s own whitespace collapse then merges the runs."""
    normalized = _ud.normalize("NFKC", s)
    return "".join(" " if _ud.category(ch) in _SANITIZER_DELETES else ch
                   for ch in normalized)


#: evidence classes that `render_news_flash_section` mints POSITIVE base facts for
POSITIVE_CLASSES = frozenset({"NFD", "NFI", "NFA"})

#: deterministic `source_status` text per verified verification_status (PENALTY path —
#: never model-authored). Keyed by the typing's `verification_status`.
_SOURCE_STATUS_TEXT = {
    "官方证实": "来源状态:公司/官方公告证实",
    "署名媒体": "来源状态:署名媒体报道,未经官方证实",
    "未证实": "来源状态:未证实",
    "传闻": "来源状态:传闻,未经证实",
    "观点": "来源状态:观点评论,非事实陈述",
}


def _derive_source_status(typing: dict) -> str:
    """Deterministic PENALTY-path attribute (invariant 4)."""
    vs = typing.get("verification_status")
    if type(vs) is not str or vs not in _SOURCE_STATUS_TEXT:
        raise ValueError(f"verification_status {vs!r} 未注册——无法派生 source_status,拒")
    text = _SOURCE_STATUS_TEXT[vs]
    if typing.get("is_rumor") is True and "传闻" not in text:
        text += "(分型标记为传闻)"
    return text


def _require_attr_text(v, *, where: str) -> str:
    """Exact-str + substantive after the frozen sanitizer (invariant 5)."""
    if type(v) is not str:
        raise ValueError(f"{where} 须恰 str——拒")
    # every sanitizer-deleted codepoint becomes a space FIRST, so nothing can fuse tokens
    clean = sanitize_text(_space_out_deleted_controls(v))
    if not clean.strip() or not has_substantive_text(clean):
        raise ValueError(f"{where} 净化后无实质性字符——拒(D7 拆行不得无事实)")
    return clean


def _bind_source_rows(rows, needed: set) -> dict:
    """GPT-P3a P0: bind the source to P2 by **RECOMPUTATION, not trust**.

    A `{content_hash: text}` mapping proves nothing — the caller can point P2's hash at a
    different (future) text. But `content_hash` IS a canonical function of the raw row, so
    recomputing it from the supplied row and requiring equality with P2's hash *proves* the
    text is the one P2 referenced: any edit changes the hash and the row stops matching.

    `rows` = the raw news rows (text_store shape). Returns {content_hash: content} for
    exactly the needed hashes; a needed hash with no hash-verified row is a hard error."""
    if not isinstance(rows, pd.DataFrame):
        raise ValueError("source rows 须为 DataFrame(text_store 原始行形状)——拒")
    if rows.empty:
        if needed:
            raise ValueError(f"{len(needed)} 个待拆事实无来源行——拒(fail-closed)")
        return {}
    if "content" not in rows.columns:
        raise ValueError("source rows 缺 content 列——拒")
    cols = list(rows.columns)
    bound: dict[str, str] = {}
    for _, r in rows.iterrows():
        h = content_hash_for("news", r, cols)      # recomputed, never taken from the row
        if h in needed and h not in bound:
            bound[h] = str(r["content"])
    missing = sorted(needed - set(bound))
    if missing:
        raise ValueError(
            f"{len(missing)} 个待拆事实没有 content_hash 可重算校验的来源行"
            f"(如 {missing[0][:12]})——正文与 P2 未绑定,拒(GPT-P3a P0 fail-closed)")
    return bound


def _split_population(assessed_artifact: dict) -> list[dict]:
    """Derived, never caller-supplied (invariant 3): the positive, importance>=4 flashes
    that `verify_d7_artifact` will demand a split for. Deterministic order."""
    pop = [a for a in assessed_artifact["assessed"]
           if a["evidence_class"] in POSITIVE_CLASSES
           and type(a["typing"]["importance"]) is int
           and a["typing"]["importance"] >= D7_IMPORTANCE_FLOOR]
    return sorted(pop, key=lambda a: a["cluster"]["fact_occurrence_id"])


def split_day_flashes(cutoff, *, ingest_class: str, assessed_artifact,
                      source_rows) -> dict:
    """Market-wide D7 attribute splitting for one (cutoff, ingest_class). **Deterministic
    — no LLM.** `source_rows` = the raw news rows (text_store shape) supplied by the
    caller; P3a recomputes each row's canonical `content_hash` and binds only rows whose
    hash equals a P2 population hash, so the attribute text is provably the text behind
    P2's record. Returns a self-describing split artifact keyed by `fact_occurrence_id`."""
    cut = _canonical_cutoff(cutoff)
    assessed_artifact = (verify_assessed_flash_artifact(assessed_artifact)
                         if isinstance(assessed_artifact, dict)
                         else load_assessed_flash_artifact(assessed_artifact))
    if assessed_artifact.get("cutoff_iso") != cut.isoformat() \
            or assessed_artifact.get("ingest_class") != ingest_class:
        raise ValueError(
            f"assessed-flash artifact ({assessed_artifact.get('ingest_class')}, "
            f"{assessed_artifact.get('cutoff_iso')}) does not match this run "
            f"({ingest_class}, {cut.isoformat()}) — refusing (P2/P3a identity mismatch)")
    consumed_p2_sha = assessed_artifact["artifact_sha256"]

    pop = _split_population(assessed_artifact)
    bound = _bind_source_rows(source_rows, {a["content_hash"] for a in pop})

    splits: list[dict] = []
    for a in pop:
        fid = a["cluster"]["fact_occurrence_id"]
        # invariant 5: the WHOLE hash-bound source, sanitized — nothing is truncated, so no
        # qualifier (same-sentence, neighbouring-sentence, across a newline) can be lost
        attrs = {"fact": _require_attr_text(bound[a["content_hash"]], where=f"{fid}.fact"),
                 "source_status": _derive_source_status(a["typing"])}
        splits.append({"fact_occurrence_id": fid,
                       "evidence_class": a["evidence_class"],
                       "importance": a["typing"]["importance"],
                       "attributes": attrs})
    splits.sort(key=lambda x: x["fact_occurrence_id"])
    population_hash = seal_hash(sorted(x["fact_occurrence_id"] for x in splits))
    artifact = {
        "artifact_schema": ARTIFACT_SCHEMA,
        "cutoff_iso": cut.isoformat(),
        "ingest_class": ingest_class,
        "evidence_class": EVIDENCE_CLASS,
        "fact_mode": FACT_MODE,
        "consumed_assessed_flash_sha256": consumed_p2_sha,
        "population_hash": population_hash,
        "n_splits": len(splits),
        "splits": splits,
    }
    artifact["artifact_sha256"] = seal_hash(artifact)
    return artifact


class SplitConflictError(ValueError):
    """write-once conflict (same discipline as P1/P2)."""


def _artifact_path(out_dir, cutoff_iso: str, ingest_class: str) -> Path:
    stamp = _canonical_cutoff(cutoff_iso).strftime("%Y%m%dT%H%M%S%f")
    # the filename tracks the SCHEMA so a stale v1 artifact cannot occupy a v2 path
    return Path(out_dir) / f"{ARTIFACT_SCHEMA}_{ingest_class}_{stamp}.json"


def write_split_artifact(artifact: dict, out_dir) -> Path:
    """Immutable, atomic, write-once / first-write-wins under a lock."""
    from research_orchestrator.file_lock import file_lock
    path = _artifact_path(out_dir, artifact["cutoff_iso"], artifact["ingest_class"])
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(artifact, ensure_ascii=False, indent=1)
    with file_lock(path.parent / (path.name + ".lock")):
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing == artifact:
                return path
            raise SplitConflictError(
                f"D7 split artifact for ({artifact['ingest_class']}, "
                f"{artifact['cutoff_iso']}) already exists with different content — "
                f"write-once, refusing to overwrite a possibly-consumed version")
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


def verify_split_artifact(artifact: dict) -> dict:
    """Full structural + seal verification (the single check any consumer runs, dict or
    path) — schema, artifact_sha256, population_hash, key uniqueness, count."""
    if not isinstance(artifact, dict) or artifact.get("artifact_schema") != ARTIFACT_SCHEMA:
        raise ValueError(f"not an {ARTIFACT_SCHEMA} artifact (a v1 artifact carries "
                         f"LLM-chosen, possibly truncated fact text — refused)")
    # GPT-P3a re-review#4 P1: the deterministic-whole-source contract is ENFORCED here, not
    # merely recorded. An artifact claiming any other extraction mode is refused, so a
    # de-contextualized fact cannot reach P3b.
    if artifact.get("fact_mode") != FACT_MODE:
        raise ValueError(
            f"fact_mode {artifact.get('fact_mode')!r} != {FACT_MODE!r} — only the "
            f"deterministic whole-source contract is consumable, refused")
    body = {k: v for k, v in artifact.items() if k != "artifact_sha256"}
    if seal_hash(body) != artifact.get("artifact_sha256"):
        raise ValueError("artifact_sha256 mismatch — D7 split artifact tampered")
    splits = artifact.get("splits")
    if not isinstance(splits, list):
        raise ValueError("D7 split artifact 'splits' must be a list")
    keys = [x["fact_occurrence_id"] for x in splits]
    if len(set(keys)) != len(keys):
        raise ValueError("D7 split artifact has duplicate fact_occurrence_id")
    if artifact.get("n_splits") != len(splits):
        raise ValueError("D7 split artifact n_splits != len(splits)")
    if seal_hash(sorted(keys)) != artifact.get("population_hash"):
        raise ValueError("population_hash mismatch — split set altered")
    return artifact


def load_split_artifact(path) -> dict:
    return verify_split_artifact(json.loads(Path(path).read_text(encoding="utf-8")))


def main() -> int:
    ap = argparse.ArgumentParser(description="NF D7 attribute splitting (integration P3a)")
    ap.add_argument("--cutoff", required=True)
    ap.add_argument("--ingest-class", default="history_bulk",
                    choices=["forward", "history_bulk"])
    ap.add_argument("--assessed-artifact", required=True)
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from data_infra.text_store import load_text
    from workspace.research.ai_research_dept.engine import config as C
    out_dir = Path(args.out_dir) if args.out_dir else C.OUT_ROOT / "nf_d7_split"
    # the CLI OBTAINS the rows (same read P2 made, same cutoff+panel) but that read is not
    # trusted: split_day_flashes recomputes each row's content_hash and binds only rows
    # matching a P2 population hash.
    cut = _canonical_cutoff(args.cutoff)
    rows = load_text("news", cut, ingest_class=args.ingest_class,
                     require_exists=args.ingest_class == "forward")
    artifact = split_day_flashes(args.cutoff, ingest_class=args.ingest_class,
                                 assessed_artifact=Path(args.assessed_artifact),
                                 source_rows=rows)
    path = write_split_artifact(artifact, out_dir)
    logger.info("split %d facts @ %s (%s) -> %s",
                artifact["n_splits"], artifact["cutoff_iso"], args.ingest_class, path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
