"""Layer-2 residual store — the append-only canonical home for the reference-DEPENDENT marginal
metrics (``resid_ic_vs_approved_stable/current``), decoupled from the reference-INVARIANT Layer-1
matrix evidence (GPT 5.5 Pro reference-decoupling review R2/C3/C4, 2026-06-15).

Design (see workspace/research/cicc_replication/MATRIX_REFERENCE_DECOUPLING_DESIGN.md):
  * Layer-1 (the matrix results.jsonl) is keyed by ``layer1_methodology_hash`` and is invariant to
    the approved-factor book. The ``resid_ic_vs_approved_*`` columns there are a CACHE (Option B).
  * Layer-2 (this store) is the CANONICAL record of "marginal contribution vs the approved book",
    keyed additionally by ``reference_book_type`` + ``reference_set_hash`` so a row always says which
    book it was computed against. APPEND-ONLY: a new book (an approval/revoke) appends fresh rows;
    nothing is overwritten (audit integrity).

Cross-factor comparison rule (C3): a comparison/selection MUST select ONE ``reference_set_hash`` —
``assert_single_reference`` enforces it. ``layer2_usage`` distinguishes ``descriptive_live`` (a
dashboard read of the latest book) from ``frozen_decision_snapshot`` (a Layer2DecisionSnapshot-bound
selection — that discipline lands in PR-2). Single-writer (the matrix run); no inter-process lock.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

LAYER2_COLUMNS = [
    "factor_id", "universe_id", "layer1_methodology_hash",
    "reference_book_type",            # "stable" | "current"
    "reference_set_hash", "reference_set_members_json",
    "residual_mean_rank_ic", "residual_oriented", "residual_hac_t",
    "effective_residual_coverage",
    "layer2_usage",                   # "descriptive_live" | "frozen_decision_snapshot"
    "computed_at",
]
BOOK_TYPES = ("stable", "current")
# keys that uniquely identify a Layer-2 row — must be non-empty at write time (GPT impl-review V2)
REQUIRED_KEYS = ("factor_id", "universe_id", "layer1_methodology_hash",
                 "reference_book_type", "reference_set_hash", "computed_at")


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Layer2ResidualStore:
    """Append-only parquet store of approved-book residuals."""

    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.base_dir / "layer2_residuals.parquet"

    def records(self) -> pd.DataFrame:
        if self.path.exists():
            return pd.read_parquet(self.path)
        return pd.DataFrame(columns=LAYER2_COLUMNS)

    def append(self, rows: list[dict]) -> int:
        """Append residual rows (never overwrites). Each row must carry the key fields; missing
        value fields are filled None. Returns the number appended."""
        if not rows:
            return 0
        norm = []
        for r in rows:
            if r.get("reference_book_type") not in BOOK_TYPES:
                raise ValueError(f"reference_book_type must be one of {BOOK_TYPES}, got {r.get('reference_book_type')!r}")
            row = {c: r.get(c) for c in LAYER2_COLUMNS}
            row["layer2_usage"] = row.get("layer2_usage") or "descriptive_live"
            row["computed_at"] = row.get("computed_at") or _utcnow()
            # V2: enforce key integrity at WRITE time — a Layer-2 row that can't be located by its
            # (factor, universe, layer1_hash, book_type, reference_hash) key is an audit orphan.
            missing = [k for k in REQUIRED_KEYS if row.get(k) in (None, "")]
            if missing:
                raise ValueError(f"Layer2 row missing required key(s) {missing}: {row}")
            norm.append(row)
        new_df = pd.DataFrame(norm)[LAYER2_COLUMNS]
        existing = self.records()
        out = new_df if existing.empty else pd.concat([existing, new_df], ignore_index=True)[LAYER2_COLUMNS]
        out.to_parquet(self.path, index=False)
        return len(norm)

    def latest_descriptive(self, *, universe_id: str, layer1_methodology_hash: str,
                           reference_book_type: str, reference_set_hash: str | None = None) -> pd.DataFrame:
        """Read-time 'latest descriptive' view: the most-recent row per factor for the given
        (universe, layer1 hash, book type). If ``reference_set_hash`` is given, restrict to that book
        (the comparison-safe path); else return the latest regardless of book (dashboard display)."""
        df = self.records()
        if df.empty:
            return df
        m = (df["universe_id"] == universe_id) & \
            (df["layer1_methodology_hash"] == layer1_methodology_hash) & \
            (df["reference_book_type"] == reference_book_type)
        if reference_set_hash is not None:
            m &= (df["reference_set_hash"] == reference_set_hash)
        sub = df[m].sort_values("computed_at")
        return sub.groupby("factor_id", as_index=False).last()

    @staticmethod
    def assert_single_reference(df: pd.DataFrame) -> None:
        """C3 guard: refuse to compare resid_ic_vs_approved_* across DIFFERENT reference books.
        Any cross-factor comparison / selection must pass a frame with ONE reference_set_hash."""
        hashes = set(df["reference_set_hash"].dropna().unique())
        if len(hashes) > 1:
            raise ValueError(
                "Layer-2 residuals span multiple reference_set_hash values "
                f"{sorted(hashes)} — cross-factor comparison is invalid; recompute all factors against "
                "ONE book snapshot (a frozen Layer2DecisionSnapshot) before comparing.")


def extract_layer2_residuals(results_jsonl: str | Path, store: Layer2ResidualStore, *,
                             computed_at: str | None = None,
                             members_by_book: dict | None = None) -> int:
    """Populate the canonical Layer-2 store from a matrix ``results.jsonl`` (the inline CACHE produced
    by `_evaluate_batch`). Each evaluated row yields up to two Layer-2 rows (stable + current).

    SKIPPED rows (V2 key integrity): error rows, rows without the reference hashes (legacy/pre-PR-1b),
    and rows without a ``layer1_methodology_hash`` (an un-keyable orphan). ``members_by_book`` (optional)
    = ``{"stable": [...], "current": [...]}`` from the methodology snapshot → populates
    ``reference_set_members_json`` for auditability (A2). Append-only; returns rows appended."""
    computed_at = computed_at or _utcnow()
    members_by_book = members_by_book or {}
    path = Path(results_jsonl)

    def _members_json(book_type: str) -> str | None:
        mem = members_by_book.get(book_type)
        return json.dumps(sorted(mem)) if mem else None

    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("error") or not rec.get("reference_set_stable_hash"):
            continue
        l1 = rec.get("layer1_methodology_hash")
        if not l1:   # V2: an un-keyable row would become an audit orphan — skip it explicitly
            continue
        fid, uni = rec.get("factor"), rec.get("universe_id", "univ_all")
        rows.append({
            "factor_id": fid, "universe_id": uni, "layer1_methodology_hash": l1,
            "reference_book_type": "stable", "reference_set_hash": rec.get("reference_set_stable_hash"),
            "reference_set_members_json": _members_json("stable"),
            "residual_mean_rank_ic": rec.get("resid_ic_vs_approved_stable_signed"),
            "residual_oriented": rec.get("resid_ic_vs_approved_stable_oriented"),
            "residual_hac_t": rec.get("resid_hac_t_vs_approved_stable"),
            "effective_residual_coverage": rec.get("resid_eff_coverage_vs_approved_stable"),
            "layer2_usage": "descriptive_live", "computed_at": computed_at,
        })
        rows.append({
            "factor_id": fid, "universe_id": uni, "layer1_methodology_hash": l1,
            "reference_book_type": "current", "reference_set_hash": rec.get("reference_set_current_hash"),
            "reference_set_members_json": _members_json("current"),
            "residual_mean_rank_ic": rec.get("resid_ic_vs_approved_current_signed"),
            "residual_oriented": None, "residual_hac_t": None, "effective_residual_coverage": None,
            "layer2_usage": "descriptive_live", "computed_at": computed_at,
        })
    return store.append(rows)
