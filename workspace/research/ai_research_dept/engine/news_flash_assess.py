# SCRIPT_STATUS: ACTIVE — NF integration P2: market-wide cluster + route + assess
"""NF market-wide clustering + routing + assessment (integration unit P2).

Producer stage 2. Consumes P1's typed-flash artifact and produces a **sealed
market-wide assessed-flash artifact**: for each cutoff-visible news cluster, its
typing (from P1), its route (which A-share stocks / industries / concepts it
mentions), and its evidence class. P3 then selects, per stock, the flashes whose
route touches that stock and renders them into a D7 decision artifact.

**Wiring, not new logic.** Every step already exists and is tested:
`text_store.load_text` (PIT gate + forward fail-closed), `news_ingest.build_cluster_
snapshots` (sealed clusters), `news_routing.route_cluster` over `AliasRegistry`
(deterministic, alias-based, as-of cutoff), `news_cards.assess_flash`
(verify-not-trust evidence class). The reference inputs (alias registry, industry
terms, concept terms) are INJECTED so the core is testable; the CLI builds them
from `stock_basic` / the SW industry reference / the THS concept index.

Declared invariants (Tier-2; see NF_UNIT_P2_DESIGN.md):

1. **PIT inherited + one canonical cutoff + fully as-of registry.** `load_text` filters +
   forward fail-closed; the SAME `_canonical_cutoff` (microsecond-max) drives load,
   clustering, and routing; `build_cluster_snapshots` re-asserts `effective_at <= cutoff`.
   **P2 builds the alias registry ITSELF as-of this canonical cutoff (GPT-P2 P0)** with
   both PIT boundaries: (a) listing — `list_date`/`delist_date` filtered at `cut`,
   **fail-closed on unparseable/missing dates**; (b) **names — the PIT name in effect at
   `cut` from `namechange` history, NOT the current `stock_basic.name`** (a post-cutoff
   rename can no longer resolve at a past cutoff). The as-of basis (registry hash/version,
   as_of_names hash, term-set hashes) is recorded in `routing_reference`.
2. **P1 binding — verified, same identity, POPULATION equality, fail-closed.** The consumed
   P1 artifact is fully verified whether passed as a dict or a path (`verify_typed_flash_
   artifact` — a dict's self-claimed SHA is never trusted, GPT-P2 P1-#2), must be for the
   exact (cutoff, ingest_class), and its `artifact_sha256` is bound into P2's artifact. The
   raw news content-hash set MUST EQUAL the P1-typed set exactly (`population_hash`, not just
   the cluster representatives, GPT-P2 P1-#3) — any missing/extra/duplicate refuses.
3. **Deterministic PIT routing, no LLM, union over members.** Routing is a pure function of
   (content, registry, cutoff, terms); every cluster member is routed and the mentions are
   UNIONed (not just the representative — the 120-char cluster key can group members that
   mention different stocks, GPT-P2). The routing basis is recorded so P3/P4 can bind it.
4. **evidence_class is verify-not-trust.** `assess_flash` recomputes it from typing+route.
5. **Macro-routed flashes kept but flagged.** A `primary_route=='macro'` cluster stays in
   the artifact (audit) with `news_render_eligible=False`; the news D7 render (P3) excludes
   it (the macro seat is a separate unit).
6. **Immutable, self-describing, write-once persistence** — same discipline as P1.
7. **NON_EVIDENTIARY.** Empty day → empty artifact; replay-class marker.
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

from data_infra.pit_backend import strictly_next_open_trade_day  # noqa: E402
from data_infra.text_store import load_text  # noqa: E402
from workspace.research.ai_research_dept.engine.news_cards import assess_flash  # noqa: E402
from workspace.research.ai_research_dept.engine.news_flash_typing import (  # noqa: E402
    _canonical_cutoff, load_typed_flash_artifact, verify_typed_flash_artifact,
)
from workspace.research.ai_research_dept.engine.news_ingest import (  # noqa: E402
    build_cluster_snapshots,
)
from workspace.research.ai_research_dept.engine.news_routing import (  # noqa: E402
    build_alias_registry, route_cluster,
)
from workspace.research.ai_research_dept.engine.news_seal import seal_hash  # noqa: E402

logger = logging.getLogger("news_flash_assess")

ARTIFACT_SCHEMA = "nf_assessed_flash_v1"
EVIDENCE_CLASS = "nf_assessed_flash/NON_EVIDENTIARY"


class AssessedFlashConflictError(ValueError):
    """write-once conflict: an assessed-flash artifact for this (ingest_class, cutoff)
    already exists with different content (same discipline as P1/P4)."""


def _cluster_payload(cluster) -> dict:
    """Serialize a sealed ClusterSnapshot to a JSON dict P3 can reconstruct + re-verify."""
    return {"cluster_id": cluster.cluster_id, "algo_version": cluster.algo_version,
            "cutoff_iso": cluster.cutoff_iso,
            "members": [dict(m) for m in cluster.members],
            "fact_occurrence_id": cluster.fact_occurrence_id,
            "cluster_first_visible_at_iso": cluster.cluster_first_visible_at_iso,
            "n_outlets": cluster.n_outlets}


#: typing fields that determine evidence identity (importance excluded — it is a max
#: over cluster members, not an identity field)
_TYPING_IDENTITY_FIELDS = ("event_type", "verification_status", "content_kind",
                           "direction", "is_rumor")


def _as_of_names(namechange, cut, open_calendar) -> dict:
    """PIT name resolution — **fail-closed omit** (GPT-P2 re-review#2, user-decided). A
    ts_code gets an as-of name ONLY if `namechange` gives exactly ONE name that is, at
    `cut`, both (a) IN EFFECT (`start_date <= cut <= end_date|∞`, inclusive DAY bounds) and
    (b) PIT-VISIBLE. Any code with 0 covering names, >1 (gap/overlap), an unparseable/missing
    start/ann date, or entirely absent from namechange gets **NO name alias** — it still
    resolves by numeric A/H code, just not by name. There is NO fallback to the current
    `stock_basic.name` (that reopens the future-name leak: an empty namechange would resolve
    every current — possibly future — name).

    GPT-P2 re-review#5 (P0): visibility is **STRICT**, per the repo's hard PIT contract
    (CLAUDE.md §3.2, `effective_date > disclosure_date`): a rename announced on `ann_date`
    is usable only from `strictly_next_open_trade_day(ann_date, open_calendar)` — a
    SAME-DAY announcement does NOT resolve. `open_calendar` is REQUIRED; there is no
    fail-open fallback to a day-inclusive `ann_date <= cut` comparison."""
    # GPT-P2 re-review#4: compare at DAY granularity. namechange dates are YYYYMMDD (they
    # parse to 00:00:00), while `cut` is a wall-clock timestamp — a raw `cut <= end_date`
    # wrongly excluded a name whose end_date IS the cutoff day (18:00 <= 00:00 is False).
    cut_d = pd.Timestamp(cut).normalize()

    def _d(v):
        t = pd.to_datetime(str(v), errors="coerce")
        return t.normalize() if pd.notna(t) else pd.NaT

    nc_df = namechange.reset_index(drop=True)
    if nc_df.empty:
        return {}
    # STRICT visibility anchor: the name is knowable only from the first open trading day
    # STRICTLY AFTER its announcement (the same function the PIT ledger is built on).
    ann = pd.to_datetime(nc_df.get("ann_date"), errors="coerce")
    visible_from = strictly_next_open_trade_day(ann, open_calendar)

    nc: dict[str, list] = {}
    for i, r in nc_df.iterrows():
        tc = str(r["ts_code"]).strip()
        s = _d(r.get("start_date"))
        e_raw = r.get("end_date")
        e = (_d(e_raw) if not (e_raw is None or pd.isna(e_raw)) else None)
        v = visible_from.iloc[i]
        v = pd.Timestamp(v).normalize() if pd.notna(v) else pd.NaT
        nc.setdefault(tc, []).append((s, e, v, str(r["name"]).strip()))
    out: dict[str, str] = {}
    for tc, rows in nc.items():
        covering = sorted({nm for (s, e, v, nm) in rows
                           if pd.notna(s) and s <= cut_d       # in effect (inclusive day)
                           and (e is None or (pd.notna(e) and cut_d <= e))
                           and pd.notna(v) and v <= cut_d})    # STRICTLY-next-open visible
        if len(covering) == 1:                                 # clean, unique → usable
            out[tc] = covering[0]
        # else (0, gap/overlap, not-yet-visible): omit → no name alias (numeric still works)
    return out


def _union_route(cluster, content_by_hash, registry, cut, industry_terms, concept_terms):
    """GPT-P2 representative-member fix: route EVERY member and UNION their mentions
    instead of routing only `members[0]`. The cluster key is only the first 120 canonical
    chars of content, so two members can share a family yet mention different stocks in
    their tails; routing the representative alone dropped the other stock. Union removes
    that approximation. Deterministic (sorted); `content` for render stays the
    representative's text."""
    codes, ind, con, mentions = set(), set(), set(), []
    for m in cluster.members:
        ch = m["content_hash"]
        if ch not in content_by_hash:
            raise ValueError(f"cluster {cluster.fact_occurrence_id} member content_hash "
                             f"absent from loaded rows — refusing")
        r = route_cluster(str(content_by_hash[ch]), registry, cut,
                          industry_terms, concept_terms)
        codes.update(r["subject_codes"])
        ind.update(r["industry_tags"])
        con.update(r["concept_tags"])
        mentions.extend(r["mentions"])
    primary = "stock" if codes else ("industry_concept" if (ind or con) else "macro")
    rep_ch = cluster.members[0]["content_hash"]
    return {"primary_route": primary, "subject_codes": sorted(codes),
            "industry_tags": sorted(ind), "concept_tags": sorted(con),
            "mentions": mentions, "content": str(content_by_hash[rep_ch])}


def assess_day_flashes(cutoff, *, ingest_class: str, typed_artifact,
                       stock_basic, namechange, open_calendar, industry_terms: frozenset,
                       concept_terms: frozenset,
                       alias_version: str = "p2_asof", alias_valid_from: str = "2000-01-01",
                       store_dir=None, require_exists: bool = False) -> dict:
    """Market-wide cluster + route + assess for one (cutoff, ingest_class). Reference
    inputs are injected: `typed_artifact` = the P1 artifact (dict OR path), `stock_basic`
    + `namechange` = DataFrames (P2 builds the alias registry from them AS-OF this
    canonical cutoff, with PIT names — see GPT-P2 P0), `industry_terms`/`concept_terms`
    = frozensets. Returns a self-describing assessed-flash artifact dict."""
    cut = _canonical_cutoff(cutoff)
    # GPT-P2 P1-#2: verify the P1 artifact whether it came as a dict or a path — a dict's
    # self-claimed SHA is NEVER trusted unverified.
    typed_artifact = (verify_typed_flash_artifact(typed_artifact)
                      if isinstance(typed_artifact, dict)
                      else load_typed_flash_artifact(typed_artifact))
    # invariant 2: the P1 artifact must be for the EXACT (cutoff, ingest_class)
    if typed_artifact.get("cutoff_iso") != cut.isoformat() \
            or typed_artifact.get("ingest_class") != ingest_class:
        raise ValueError(
            f"typed-flash artifact ({typed_artifact.get('ingest_class')}, "
            f"{typed_artifact.get('cutoff_iso')}) does not match this run "
            f"({ingest_class}, {cut.isoformat()}) — refusing (P1/P2 identity mismatch)")
    typing_index = {t["content_hash"]: t["typing"] for t in typed_artifact["typed"]}
    consumed_p1_sha = typed_artifact["artifact_sha256"]

    # GPT-P2 P0: build the alias registry AS-OF this canonical cutoff — P2 owns the as-of
    # binding, so it can never be handed a registry built for a different (future) cutoff
    # that would resolve future-listed stocks. list_date/delist_date filtered at `cut`
    # (fail-closed on unparseable dates); name aliases are the PIT names in effect at
    # `cut` (from namechange), not the current stock_basic.name.
    as_of_names = _as_of_names(namechange, cut, open_calendar)
    registry = build_alias_registry(stock_basic, version=alias_version,
                                    valid_from=alias_valid_from, valid_to=None, cutoff=cut,
                                    as_of_names=as_of_names)
    # bind the full routing basis so P3/P4 can verify it
    routing_reference = {
        "as_of_cutoff_iso": cut.isoformat(),
        "alias_registry_version": registry.version,
        "alias_registry_hash": registry.content_hash,
        "as_of_names_hash": seal_hash(sorted(as_of_names.items())),
        "industry_terms_hash": seal_hash(sorted(industry_terms)),
        "concept_terms_hash": seal_hash(sorted(concept_terms)),
    }

    req = ingest_class == "forward" or bool(require_exists)   # forward: hard fail-closed
    df = load_text("news", cut, store_dir=store_dir, ingest_class=ingest_class,
                   require_exists=req)
    content_by_hash = {} if df.empty else dict(zip(df["content_hash"], df["content"]))
    # GPT-P2 P1-#3: the raw panel content set MUST EQUAL the P1-typed set exactly (not
    # just the cluster representatives). A missing/extra/duplicate content_hash is a
    # P1/P2 population mismatch — refuse before clustering.
    raw_hashes = sorted(set(content_by_hash))
    if seal_hash(raw_hashes) != typed_artifact["population_hash"]:
        raise ValueError(
            "raw news population does not equal the P1-typed population "
            "(population_hash mismatch) — P1 and P2 saw different content sets, refusing")
    clusters = build_cluster_snapshots(df, cut) if not df.empty else []

    assessed: list[dict] = []
    for cluster in clusters:
        member_hashes = [m["content_hash"] for m in cluster.members]
        if any(h not in typing_index for h in member_hashes):   # population gate redundancy
            raise ValueError(f"cluster {cluster.fact_occurrence_id} member has no P1 typing")
        # GPT-P2 P1: the 120-char cluster key can group DISTINCT facts (e.g. an official
        # bullish flash and a rumor bearish flash sharing a long prefix). Reusing the
        # representative's typing would launder one fact's evidence class onto the other's
        # stock. Refuse the cluster if members' evidence-identity typings disagree
        # (fail-closed short-term fix — no cross-fact typing wash).
        identities = {tuple(typing_index[h][f] for f in _TYPING_IDENTITY_FIELDS)
                      for h in member_hashes}
        if len(identities) > 1:
            raise ValueError(
                f"cluster {cluster.fact_occurrence_id} members carry conflicting typings "
                f"{sorted(identities)} — distinct facts grouped by the 120-char key, "
                f"refusing (GPT-P2 P1: no evidence-class wash across members)")
        rep_ch = member_hashes[0]                         # members agree on evidence identity
        # GPT-P2 P1: identity fields agree across members; importance is NOT an identity
        # field — take the MAX over members (matches render's dedup, and preserves the D7
        # importance>=4 split gate that a low-importance representative would drop).
        # GPT-P2 re-review#4: NO coercion. `int()` silently turned 5.9/"5"/True into a
        # valid-looking importance that `assess_flash`'s exact-type gate would have
        # REJECTED, letting a tampered-but-hash-consistent P1 artifact move the D7
        # importance>=4 gate. Validate each member with the same rule as
        # `_validate_typing` (literal int in [0,5]; bool excluded since type(True) is bool)
        # and max the RAW values.
        imps = []
        for h in member_hashes:
            v = typing_index[h]["importance"]
            if type(v) is not int or not 0 <= v <= 5:
                raise ValueError(
                    f"cluster {cluster.fact_occurrence_id} member importance {v!r} is not a "
                    f"literal int in [0,5] — refusing (no coercion, GPT-P2 re-review#4)")
            imps.append(v)
        rep_typing = dict(typing_index[rep_ch])
        rep_typing["importance"] = max(imps)
        route = _union_route(cluster, content_by_hash, registry, cut,
                             industry_terms, concept_terms)   # union, not representative
        a = assess_flash(cluster, rep_typing, route)          # recomputes evidence_class
        assessed.append({
            "cluster": _cluster_payload(cluster),
            "content_hash": rep_ch,
            "typing": a["typing"],
            "route": {k: a["route"][k] for k in
                      ("primary_route", "subject_codes", "industry_tags",
                       "concept_tags", "mentions")},
            "evidence_class": a["evidence_class"],
            # GPT-P2 note: coordination is NOT evaluated in P2 v1 — this is 'unassessed',
            # NOT 'confirmed no coordination'. The NFC path is a separate wiring.
            "coordination_fired": a["coordination_fired"],
            "coordination_evaluated": False,
            # invariant 5: macro-routed flashes stay for audit but are not news-render eligible
            "news_render_eligible": a["route"]["primary_route"] != "macro",
        })
    assessed.sort(key=lambda x: x["cluster"]["fact_occurrence_id"])   # deterministic
    population_hash = seal_hash(sorted(x["cluster"]["fact_occurrence_id"] for x in assessed))
    artifact = {
        "artifact_schema": ARTIFACT_SCHEMA,
        "cutoff_iso": cut.isoformat(),
        "ingest_class": ingest_class,
        "evidence_class": EVIDENCE_CLASS,
        "consumed_typed_flash_sha256": consumed_p1_sha,
        "routing_reference": routing_reference,          # as-of-bound routing basis (P0)
        "population_hash": population_hash,
        "n_flashes": len(assessed),
        "assessed": assessed,
    }
    artifact["artifact_sha256"] = seal_hash(artifact)
    return artifact


def _artifact_path(out_dir, cutoff_iso: str, ingest_class: str) -> Path:
    stamp = _canonical_cutoff(cutoff_iso).strftime("%Y%m%dT%H%M%S%f")   # bijective (P1 contract)
    return Path(out_dir) / f"nf_assessed_flash_{ingest_class}_{stamp}.json"


def write_assessed_flash_artifact(artifact: dict, out_dir) -> Path:
    """Immutable, atomic, write-once / first-write-wins under a lock (same as P1/P4)."""
    from research_orchestrator.file_lock import file_lock
    path = _artifact_path(out_dir, artifact["cutoff_iso"], artifact["ingest_class"])
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(artifact, ensure_ascii=False, indent=1)
    with file_lock(path.parent / (path.name + ".lock")):
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing == artifact:
                return path
            raise AssessedFlashConflictError(
                f"assessed-flash artifact for ({artifact['ingest_class']}, "
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


def load_assessed_flash_artifact(path) -> dict:
    """Load + re-verify both hashes (a tampered artifact, or an altered consumed-P1 SHA,
    changes artifact_sha256 → refused)."""
    artifact = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(artifact, dict) or artifact.get("artifact_schema") != ARTIFACT_SCHEMA:
        raise ValueError("not an nf_assessed_flash_v1 artifact")
    body = {k: v for k, v in artifact.items() if k != "artifact_sha256"}
    if seal_hash(body) != artifact.get("artifact_sha256"):
        raise ValueError("artifact_sha256 mismatch — assessed-flash artifact tampered")
    if seal_hash(sorted(x["cluster"]["fact_occurrence_id"] for x in artifact["assessed"])) \
            != artifact["population_hash"]:
        raise ValueError("population_hash mismatch — assessed set altered")
    return artifact


def main() -> int:
    ap = argparse.ArgumentParser(description="NF market-wide cluster+route+assess (P2)")
    ap.add_argument("--cutoff", required=True)
    ap.add_argument("--ingest-class", default="history_bulk",
                    choices=["forward", "history_bulk"])
    ap.add_argument("--typed-artifact", required=True, help="path to the P1 typed-flash artifact")
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from workspace.research.ai_research_dept.engine import config as C
    # reference inputs are assembled from existing sources; kept in the CLI (not the core).
    # P2 builds the alias registry itself AS-OF the cutoff (P0), so the CLI supplies raw
    # stock_basic + the industry/concept term sets.
    stock_basic, namechange, open_calendar, industry_terms, concept_terms = \
        _build_reference_inputs(args.cutoff)
    out_dir = Path(args.out_dir) if args.out_dir else C.OUT_ROOT / "nf_assessed_flash"
    artifact = assess_day_flashes(
        args.cutoff, ingest_class=args.ingest_class,
        typed_artifact=Path(args.typed_artifact), stock_basic=stock_basic,
        namechange=namechange, open_calendar=open_calendar,
        industry_terms=industry_terms, concept_terms=concept_terms)
    path = write_assessed_flash_artifact(artifact, out_dir)
    logger.info("assessed %d flashes @ %s (%s) -> %s",
                artifact["n_flashes"], artifact["cutoff_iso"], args.ingest_class, path)
    return 0


def _build_reference_inputs(cutoff):
    """CLI-side assembly of the injected reference inputs from existing sources
    (kept out of the testable core): raw `stock_basic` (P2 builds the alias registry
    from it AS-OF the cutoff), the SW L1 industry-name set, and the THS concept-name set.
    Left as a thin seam; the per-source PIT details are wired when the offline P2 driver
    is first run for real."""
    raise NotImplementedError(
        "P2 CLI reference assembly (stock_basic, namechange history, the OPEN TRADING "
        "CALENDAR from data/reference/trade_cal.parquet, SW L1 industry-name set, THS "
        "concept-name set) is wired at first offline run; the testable core "
        "assess_day_flashes takes these injected")


if __name__ == "__main__":
    raise SystemExit(main())
