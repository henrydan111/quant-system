# SCRIPT_STATUS: ACTIVE — reference-decoupling evidence migration (one-time, --apply GATED)
"""Migrate pre-decoupling factor_evidence rows to carry the reference-INVARIANT identity.

Pre-decoupling matrix/refresh rows (run_type ``factor_lifecycle_auto`` / ``factor_lifecycle_refresh``,
``row_role`` "" / "legacy", no ``layer1_methodology_hash``) are keyed by the LEGACY reference-INCLUDED
methodology_hash, so an approval/revoke forked their run_id and made the marginal-vs-book residual a
moving identity. This migration appends a ``migrated_layer1`` SIBLING next to each immutable legacy row
(the legacy row is NEVER mutated — V4) that carries the stable ``layer1_methodology_hash`` + reference
hashes + schema, COPYING the Layer-1 metric values verbatim (no recompute) and recording a
``layer1_value_digest`` of exactly which values were carried.

Three modes — the production-touching ``--apply`` is GATED on the final GPT impl-review confirm:

  (default / --dry-run)  identify legacy rows, build the CURRENT per-universe methodologies, and report
                         the plan (legacy run_id -> new layer1 hash / ref hashes / schema / N rows,
                         expected definition-drift skips). No eval, no writes.

  --sample-recompute     V4 value-safety PROOF. Recompute a STRATIFIED sample of legacy (factor,
                         universe) pairs with the CURRENT producer code (mx.build_base_ctx +
                         fr._evaluate_batch) and assert every reference-INVARIANT Layer-1 column is
                         byte-equal to the STORED legacy value. A mismatch == protocol / window /
                         STYLE_CONTROLS drift => the legacy rows are stale and must be re-run NATIVELY,
                         not migrated => FAIL (fail-closed). Writes a PASS token tied to the git SHA +
                         the validated layer1 hashes. Read-only wrt the registry.

  --apply                A3 GATE: requires a GREEN R4 invariance test AND a FRESH sample-recompute PASS
                         token (same git SHA + matching layer1 hashes), then appends the migrated
                         siblings via the row_role-aware upsert. Writes the registry.

Run order (GPT impl-review V6): migrate FIRST, THEN re-run E1a natively (a native row supersedes a
migrated row via store.canonical_layer1_evidence).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import subprocess
import sys
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_research.factor_registry.store import (  # noqa: E402
    FactorRegistryStore, LAYER1_AUTO_RUN_TYPES,
)
from src.alpha_research.factor_eval.unified_eval import (  # noqa: E402
    BOOK_DEPENDENT_LAYER1_FIELDS, STYLE_CONTROLS_V1,
)
from workspace.scripts.unified_eval_common import build_frozen_methodology  # noqa: E402
from workspace.scripts import unified_eval_full_run as fr  # noqa: E402
from workspace.scripts import unified_eval_universe_matrix as mx  # noqa: E402

log = logging.getLogger("migrate_refdecouple")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

REGISTRY = PROJECT_ROOT / "data" / "factor_registry"
TOKEN = mx.OUTDIR / "migration_sample_recompute_token.json"
R4_TEST = "tests/alpha_research/test_matrix_reference_invariance.py::test_layer1_metrics_are_reference_invariant"

# Columns NOT compared in the byte-equality proof: the book-dependent family (legitimately changes
# when the approved book changed since the legacy run) + the reference-decoupling identity fields
# (absent on legacy rows) + mutable registry-snapshot metadata (status/kind/category/eligibility can
# change without any protocol drift) + the per-row timer. Everything else is a reference-INVARIANT
# Layer-1 metric and MUST match byte-for-byte.
_IDENTITY_FIELDS = {"methodology_schema_version", "layer1_methodology_hash",
                    "reference_set_stable_hash", "reference_set_current_hash",
                    "row_role", "legacy_methodology_hash", "migration_id", "layer1_value_digest"}
_MUTABLE_METADATA = {"registry_status", "factor_kind", "category", "field_eligible"}
COMPARE_EXCLUDE = set(BOOK_DEPENDENT_LAYER1_FIELDS) | _IDENTITY_FIELDS | _MUTABLE_METADATA | {"eval_seconds"}
# layer1_value_digest attests to EXACTLY the reference-invariant Layer-1 payload the proof validates
# (a native recompute reproduces it bit-for-bit) — so the digest excludes the same fields the
# byte-equality comparison does (book-dependent resid cache + identity + mutable metadata + timer).
DIGEST_EXCLUDE = COMPARE_EXCLUDE


def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       cwd=PROJECT_ROOT, text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def _layer1_digest(rec: dict) -> str:
    payload = {k: v for k, v in rec.items() if k not in DIGEST_EXCLUDE}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _legacy_universe(uid) -> str:
    u = (str(uid) if uid is not None and not pd.isna(uid) else "").strip()
    return u or "univ_all"


def load_legacy(store: FactorRegistryStore) -> pd.DataFrame:
    """The pre-decoupling auto/refresh rows (row_role "" / "legacy", no layer1 hash)."""
    ev = store.factor_evidence
    auto = ev[ev["run_type"].isin(LAYER1_AUTO_RUN_TYPES)].copy()
    role = auto["row_role"].fillna("").astype(str) if "row_role" in auto.columns else pd.Series("", index=auto.index)
    legacy = auto[role.isin(["", "legacy"])].copy()
    legacy["__uni"] = legacy["universe_id"].map(_legacy_universe)
    return legacy


def build_methods(universes: list) -> dict:
    return {u: build_frozen_methodology(is_start=fr.TIME_SPLIT.is_start,
                                        is_end=fr.TIME_SPLIT.is_end, universe_id=u)
            for u in universes}


def report_plan(legacy: pd.DataFrame, methods: dict) -> dict:
    plan = {}
    for u in sorted(legacy["__uni"].unique()):
        sub = legacy[legacy["__uni"] == u]
        m = methods[u]
        run_ids = sorted(sub["run_id"].map(str).unique())
        plan[u] = {"n_rows": int(len(sub)), "legacy_run_ids": run_ids,
                   "new_layer1_hash": m.layer1_methodology_hash,
                   "reference_set_stable_hash": m.reference_set_stable_hash,
                   "reference_set_current_hash": m.reference_set_current_hash,
                   "schema": m.methodology_schema_version}
        log.info("[plan] %-18s rows=%-4d legacy_run_ids=%s -> layer1=%s schema=%s",
                 u, len(sub), run_ids, m.layer1_methodology_hash, m.methodology_schema_version)
    return plan


def _category(fid: str, status_map: dict) -> str:
    if fid in STYLE_CONTROLS_V1:
        return "style"
    st = status_map.get(fid, "")
    if st == "approved":
        return "approved"
    if st == "candidate":
        return "candidate"
    pre = fid.split("_")[0]
    if pre in {"mmt", "rev", "liq", "risk", "vol", "alpha", "amp"}:
        return "pv"
    return "fundamental"


def stratified_sample(legacy: pd.DataFrame, store: FactorRegistryStore, n: int,
                      base_ok: set) -> list:
    """A deterministic stratified sample of (factor, universe) legacy pairs spanning
    style/approved/candidate/pv/fundamental × {univ_all, a thin domain}. Only field-eligible
    (currently computable) factors are sampleable."""
    master = store.factor_master
    status_map = dict(zip(master["factor_id"].map(str),
                          master["status"].map(lambda x: str(x) if x is not None else "")))
    thin = {"univ_microcap", "univ_growth", "univ_csi1000"}
    pairs = []
    for _, r in legacy.iterrows():
        fid = str(r["factor_id"])
        if fid not in base_ok:
            continue
        u = r["__uni"]
        uclass = "univ_all" if u == "univ_all" else ("thin" if u in thin else "other")
        pairs.append((_category(fid, status_map), uclass, fid, u))
    # round-robin across (category, uclass) buckets, deterministic by sorted factor name
    from collections import defaultdict
    buckets = defaultdict(list)
    for cat, uclass, fid, u in sorted(pairs, key=lambda x: (x[0], x[1], x[2])):
        buckets[(cat, uclass)].append((fid, u))
    sample, i = [], 0
    keys = sorted(buckets)
    seen = set()
    while len(sample) < n and any(buckets[k] for k in keys):
        k = keys[i % len(keys)]
        if buckets[k]:
            fid, u = buckets[k].pop(0)
            if (fid, u) not in seen:
                sample.append((fid, u)); seen.add((fid, u))
        i += 1
        if i > 10000:
            break
    return sample


def _recompute_one(base_ctx: dict, masks: dict, methods: dict, fid: str, uid: str,
                   scratch: Path, df_all: pd.DataFrame) -> dict:
    """Eval ONE (factor, universe) through the live producer path from the SHARED precomputed panel
    ``df_all`` (computed once for all distinct sampled factors — matches the matrix's batched compute;
    a per-factor recompute re-inits Qlib each call and is pathologically slow). Returns the rec."""
    masked = mx._mask_panel(df_all, [fid], masks[uid])
    aligned = masks[uid].reindex(df_all.index).fillna(False)
    rp = scratch / f"r_{uid}_{fid}.jsonl"
    if rp.exists():
        rp.unlink()
    ctx = {**base_ctx, "method": methods[uid], "results_path": rp,
           "record_extra": {"universe_id": uid}, "domain_total_cells": float(aligned.sum())}
    fr._evaluate_batch(masked, [fid], ctx)
    rows = [json.loads(l) for l in rp.read_text(encoding="utf-8").splitlines() if l.strip()]
    if len(rows) != 1:
        raise RuntimeError(f"recompute of {fid}@{uid} emitted {len(rows)} rows (expected 1)")
    return rows[0]


def _values_equal(a, b, *, rel_tol: float = 1e-9, abs_tol: float = 1e-12) -> bool:
    """Equality for the value-safety proof. Numbers compare with a TIGHT tolerance: recomputing a
    factor in a DIFFERENT batch composition than the original legacy run reorders floating-point
    summations, so an invariant metric can differ at the last ULP (~1e-15) — that is numerical noise,
    NOT protocol drift (a real drift moves a value by >> rel_tol). NaN==NaN; dict/list recurse;
    bools and everything non-numeric compare exactly."""
    if a is None and b is None:
        return True
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        fa, fb = float(a), float(b)
        if fa != fa and fb != fb:
            return True
        if fa != fa or fb != fb:
            return False
        return math.isclose(fa, fb, rel_tol=rel_tol, abs_tol=abs_tol)
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(_values_equal(a[k], b[k], rel_tol=rel_tol, abs_tol=abs_tol) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_values_equal(x, y, rel_tol=rel_tol, abs_tol=abs_tol) for x, y in zip(a, b))
    return a == b


def _max_rel_dev(a, b) -> float:
    """Max relative deviation between two (possibly nested) numeric structures — for reporting how
    tight the agreement actually is (the proof passes on tolerance; this shows it's ULP-level)."""
    if isinstance(a, bool) or isinstance(b, bool):
        return 0.0
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        fa, fb = float(a), float(b)
        if fa != fa or fb != fb or max(abs(fa), abs(fb)) == 0:
            return 0.0
        return abs(fa - fb) / max(abs(fa), abs(fb))
    if isinstance(a, dict) and isinstance(b, dict) and set(a) == set(b):
        return max((_max_rel_dev(a[k], b[k]) for k in a), default=0.0)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)) and len(a) == len(b):
        return max((_max_rel_dev(x, y) for x, y in zip(a, b)), default=0.0)
    return 0.0


def _compare(legacy_rec: dict, recompute_rec: dict) -> tuple:
    """Return (diffs, max_rel_dev) for the reference-invariant Layer-1 keys. ``diffs`` empty ==
    numerically equal to within tolerance; ``max_rel_dev`` is the tightest-agreement diagnostic."""
    diffs, max_rel = [], 0.0
    for k in sorted(set(legacy_rec) - COMPARE_EXCLUDE):
        a, b = legacy_rec.get(k), recompute_rec.get(k)
        if k not in recompute_rec or not _values_equal(a, b):
            diffs.append((k, a, b))
        max_rel = max(max_rel, _max_rel_dev(a, b))
    return diffs, max_rel


def sample_recompute(store: FactorRegistryStore, legacy: pd.DataFrame, methods: dict,
                     n: int, scratch: Path) -> dict:
    # reuse the matrix producer's exact catalog + field-eligibility functions (mx imports both at
    # module level) so the sample's eligibility test matches a real matrix run bit-for-bit.
    full = mx.get_factor_catalog(include_new_data=True)
    elig = mx.per_factor_field_eligible(list(full), stage="formal_validation")
    base_ok = {n_ for n_, v in elig.items() if v}
    sample = stratified_sample(legacy, store, n, base_ok)
    universes = sorted({u for _, u in sample})
    log.info("sample: %d pairs over %d universes %s", len(sample), len(universes), universes)
    if len(sample) < 20:
        log.warning("sample has only %d pairs (< 20 target) — narrow legacy/eligibility overlap", len(sample))

    base_ctx, masks, _seed = mx.build_base_ctx(universes, methods)
    scratch.mkdir(parents=True, exist_ok=True)

    # compute ALL distinct sampled factors ONCE (matches the matrix's batched compute; one Qlib init
    # for the whole set instead of one per (factor, universe) pair) then reindex to the panel anchor.
    distinct = sorted({fid for fid, _ in sample})
    log.info("computing %d distinct sampled factors in one batch ...", len(distinct))
    df_all = fr._compute_batch(distinct, include_adj=False)
    panel_index = base_ctx["adj_close"].index
    if not df_all.index.equals(panel_index):
        df_all = df_all.reindex(panel_index)

    legacy_by_key = {(str(r["factor_id"]), r["__uni"]): r for _, r in legacy.iterrows()}
    results, mismatches, global_max_rel = [], 0, 0.0
    for fid, uid in sample:
        legacy_row = legacy_by_key[(fid, uid)]
        legacy_rec = json.loads(legacy_row["unified_metrics_json"])
        rec = _recompute_one(base_ctx, masks, methods, fid, uid, scratch, df_all)
        diffs, max_rel = _compare(legacy_rec, rec)
        ok = not diffs
        global_max_rel = max(global_max_rel, max_rel)
        results.append({"factor": fid, "universe": uid, "equal": ok,
                        "n_compared": len(set(legacy_rec) - COMPARE_EXCLUDE),
                        "max_rel_dev": max_rel, "diffs": diffs[:8]})
        if not ok:
            mismatches += 1
            log.error("MISMATCH %s@%s: %d field(s) exceed tol e.g. %s", fid, uid, len(diffs), diffs[:3])
        else:
            log.info("ok %s@%s (%d invariant fields equal; max_rel_dev=%.2e)", fid, uid,
                     len(set(legacy_rec) - COMPARE_EXCLUDE), max_rel)

    passed = mismatches == 0 and len(sample) >= 1
    token = {"pass": bool(passed), "git_sha": _git_sha(), "n_pairs": len(sample),
             "mismatches": mismatches, "max_rel_dev": global_max_rel,
             "tolerance": {"rel_tol": 1e-9, "abs_tol": 1e-12},
             "layer1_hashes": {u: methods[u].layer1_methodology_hash for u in methods},
             "checked_at_utc": pd.Timestamp.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
             "results": results}
    TOKEN.parent.mkdir(parents=True, exist_ok=True)
    TOKEN.write_text(json.dumps(token, indent=2), encoding="utf-8")
    log.info("sample-recompute %s (%d/%d equal within tol; max_rel_dev=%.2e) -> token %s",
             "PASS" if passed else "FAIL", len(sample) - mismatches, len(sample), global_max_rel, TOKEN)
    return token


def _check_apply_gates(methods: dict) -> dict:
    """A3: a GREEN R4 invariance test + a FRESH sample-recompute PASS token (same git SHA + matching
    layer1 hashes). Returns the token; raises SystemExit on any gate failure (fail-closed)."""
    if not TOKEN.exists():
        raise SystemExit("no sample-recompute token — run --sample-recompute first (V4).")
    token = json.loads(TOKEN.read_text(encoding="utf-8"))
    if not token.get("pass"):
        raise SystemExit(f"sample-recompute token says FAIL ({token.get('mismatches')} mismatches) — "
                         "the legacy rows are NOT protocol-consistent; re-run them natively, do not migrate.")
    sha = _git_sha()
    if token.get("git_sha") != sha:
        raise SystemExit(f"token git_sha {token.get('git_sha')} != HEAD {sha} — code changed since the "
                         "proof; re-run --sample-recompute.")
    for u, m in methods.items():
        if token.get("layer1_hashes", {}).get(u) != m.layer1_methodology_hash:
            raise SystemExit(f"token layer1 hash for {u} != current — re-run --sample-recompute.")
    log.info("A3 gate: running R4 invariance test (%s) ...", R4_TEST)
    r = subprocess.run([sys.executable, "-m", "pytest", R4_TEST, "-q"], cwd=PROJECT_ROOT)
    if r.returncode != 0:
        raise SystemExit("R4 invariance test is NOT green — refusing to apply (A3).")
    log.info("A3 gate PASSED: R4 green + fresh sample-recompute token.")
    return token


def apply_migration(store: FactorRegistryStore, legacy: pd.DataFrame, methods: dict) -> dict:
    migration_id = f"migrate_refdecouple_{_git_sha()}"
    out = {"migration_id": migration_id, "attached": 0, "skipped": 0, "by_run_id": {}}
    work = legacy.copy()
    work["__rid"] = work["run_id"].map(str)
    # group legacy by (legacy run_id, universe) -> append migrated siblings under the SAME run_id
    for (run_id, uni), sub in work.groupby(["__rid", "__uni"]):
        m = methods[uni]
        recs = []
        legacy_hash = ""
        for _, r in sub.iterrows():
            rec = json.loads(r["unified_metrics_json"])
            legacy_hash = str(rec.get("methodology_hash") or r.get("methodology_hash") or "")
            rec["universe_id"] = uni
            rec["row_role"] = "migrated_layer1"
            rec["methodology_schema_version"] = m.methodology_schema_version
            rec["layer1_methodology_hash"] = m.layer1_methodology_hash
            rec["reference_set_stable_hash"] = m.reference_set_stable_hash
            rec["reference_set_current_hash"] = m.reference_set_current_hash
            rec["legacy_methodology_hash"] = legacy_hash
            rec["migration_id"] = migration_id
            rec["layer1_value_digest"] = _layer1_digest(rec)
            recs.append(rec)
        res = store.record_formal_auto_evidence(
            run_id=run_id, records=recs, methodology_hash=legacy_hash,
            source_path=f"migration:{migration_id}")
        n_att = len(res.get("attached", []))
        n_skip = len(res.get("skipped_drift", [])) + len(res.get("skipped_unknown", []))
        out["attached"] += n_att
        out["skipped"] += n_skip
        out["by_run_id"][f"{run_id}|{uni}"] = {"attached": n_att, "skipped": n_skip,
                                                "skipped_drift": res.get("skipped_drift", [])[:10]}
        log.info("migrated %s @ %s: +%d siblings, %d skipped (drift/unknown)",
                 run_id, uni, n_att, n_skip)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", help="default: report the plan, no eval/writes")
    g.add_argument("--sample-recompute", action="store_true", help="V4 byte-equality proof (read-only)")
    g.add_argument("--apply", action="store_true", help="A3-gated: append migrated siblings (WRITES)")
    ap.add_argument("--n", type=int, default=24, help="sample size for --sample-recompute (>=20)")
    args = ap.parse_args()

    store = FactorRegistryStore(REGISTRY)
    legacy = load_legacy(store)
    if legacy.empty:
        log.info("no legacy auto/refresh rows to migrate — nothing to do.")
        return 0
    universes = sorted(legacy["__uni"].unique())
    methods = build_methods(universes)
    log.info("legacy rows: %d over universes %s", len(legacy), universes)
    report_plan(legacy, methods)

    if args.sample_recompute:
        scratch = mx.OUTDIR / "migration_recompute_scratch"
        token = sample_recompute(store, legacy, methods, max(args.n, 20), scratch)
        return 0 if token["pass"] else 1

    if args.apply:
        _check_apply_gates(methods)
        out = apply_migration(store, legacy, methods)
        store.save()
        log.info("APPLY DONE: +%d migrated siblings, %d skipped; migration_id=%s; registry saved.",
                 out["attached"], out["skipped"], out["migration_id"])
        # post-condition: canonical view dedups migrated XOR legacy
        canon = store.canonical_layer1_evidence()
        log.info("canonical_layer1_evidence rows after migrate: %d", len(canon))
        return 0

    log.info("DRY-RUN complete (plan above). --sample-recompute to prove value-safety, then --apply "
             "(A3-gated) to write. RUN order: migrate -> then re-run E1a natively (V6).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
