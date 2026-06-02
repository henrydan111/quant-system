"""Formal IS-only walk-forward validator (Phase 4, mode 1) — the leakage-critical piece.

Produces the ``draft -> candidate`` evidence for a generated / IS-selected factor under a
**structural** ``is_end`` boundary. The forward-return label is FUTURE-looking
(``Ref(ADJ_CLOSE, -h)``), so bounding only the factor date is NOT enough — the boundary is
on the **label-realization date**. Three belts (design-review must-fix #1):

  1. **No `compute_factors` forward return** — factors computed with ``horizons=None`` over
     ``[is_start, is_end]`` (END = is_end).
  2. **Label capped at is_end** — built from adjusted close loaded ONLY over
     ``[is_start, is_end]``, at the EXACT trading-calendar target ``r(t)=open_days[pos(t)+h]``
     (NOT ``shift(-h)``-over-rows — a sparse/suspended or uncapped adj-close would otherwise
     reach a LATER row, possibly past ``is_end``). A missing ``r(t)`` row drops (never
     substituted by a later row); both inputs are asserted ``<= is_end`` (belt 0, GPT P0 review).
  3. **Runtime assertions** — :class:`IsWindowedPanel` raises unless ``max_factor_date`` AND
     ``max_label_realization_date`` are both ``<= is_end`` (the realization date is the
     factor date shifted ``+h`` TRADING days via ``trade_cal.parquet``), AND the factor/label
     indices are aligned.

The result (:class:`WalkForwardResult`) carries NO ``oos_*`` field (structurally cannot)
and labels ``evidence_kind`` on BOTH the result and every per-factor row so a
generated-heldout result can never be blurred with an a-priori one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from . import metrics
from .status_rules import assign_candidate_status
from src.alpha_research.walk_forward import build_walk_forward_folds

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_TRADE_CAL = _PROJECT_ROOT / "data" / "reference" / "trade_cal.parquet"
_DEFAULT_QLIB_DIR = _PROJECT_ROOT / "data" / "qlib_data"

DEFAULT_HORIZON = 20
# IS-internal holdout default (design-review sign-off): 3 train + 1 validation + 1 test,
# step 1 -> MULTIPLE heldout blocks across the canonical 7-year IS window (the default
# 5+2+1 yields ZERO folds for 2014-2020).
DEFAULT_WF_CONFIG = {"train_years": 3, "validation_years": 1, "test_years": 1, "step_years": 1}


class IsEndLeakageError(RuntimeError):
    """An IS-only panel would load a factor date or a label-realization date past
    ``is_end`` — the formal walk-forward boundary is violated."""


class NoHeldoutBlockError(RuntimeError):
    """A generated / IS-selected factor has no valid IS-internal heldout block — it cannot
    become ``candidate`` without true heldout evidence (fail-closed)."""


def load_open_trading_days(trade_cal=None) -> pd.DatetimeIndex:
    """Sorted open trading days. ``trade_cal`` may be an injected iterable of dates (tests);
    otherwise read ``data/reference/trade_cal.parquet`` (``is_open==1``)."""
    if trade_cal is not None:
        return pd.DatetimeIndex(sorted(pd.Timestamp(d) for d in trade_cal))
    df = pd.read_parquet(_DEFAULT_TRADE_CAL)
    open_days = df.loc[df["is_open"] == 1, "cal_date"]
    return pd.DatetimeIndex(sorted(pd.to_datetime(open_days.astype(str), format="%Y%m%d")))


def realization_date(factor_date, horizon: int, open_days: pd.DatetimeIndex):
    """The date a ``horizon``-day forward return for ``factor_date`` REALIZES — the trading
    day ``horizon`` positions later (Qlib ``Ref(-h)`` is trading-row based). Returns
    ``pd.NaT`` if there is no such day within ``open_days``."""
    t = pd.Timestamp(factor_date)
    # First open day >= t (if t is itself an open day, this is t's own position).
    pos = int(open_days.searchsorted(t, side="left"))
    target = pos + horizon
    if pos >= len(open_days) or target >= len(open_days):
        return pd.NaT
    return open_days[target]


def last_usable_factor_date(is_end, horizon: int, open_days: pd.DatetimeIndex):
    """The latest factor date whose label realizes ``<= is_end`` (i.e. ``is_end`` shifted
    BACK ``horizon`` trading days)."""
    end = pd.Timestamp(is_end)
    pos = open_days.searchsorted(end, side="right") - 1  # last open day <= is_end
    if pos < 0:
        return pd.NaT
    back = pos - horizon
    if back < 0:
        return pd.NaT
    return open_days[back]


@dataclass(frozen=True)
class IsWindowedPanel:
    """A factor panel + forward-return label that has been VALIDATED to never cross
    ``is_end`` — neither in the factor dates loaded NOR in the label-realization dates.
    Construction raises :class:`IsEndLeakageError` on any violation (belt 3)."""

    factor_panel: pd.DataFrame
    label: pd.Series
    is_end: pd.Timestamp
    horizon: int
    open_days: pd.DatetimeIndex
    max_factor_date: pd.Timestamp = field(init=False)
    max_label_realization_date: pd.Timestamp = field(init=False)

    def __post_init__(self):
        is_end = pd.Timestamp(self.is_end)
        if self.factor_panel.empty or self.label.empty:
            raise IsEndLeakageError("IsWindowedPanel: empty factor panel / label")
        # factor panel and label MUST be row-aligned (a directly-constructed panel with a
        # label indexed elsewhere — e.g. after is_end — must be rejected, GPT P0 review).
        if not self.factor_panel.index.equals(self.label.index):
            raise IsEndLeakageError(
                "IsWindowedPanel: factor_panel and label indices are not aligned"
            )
        max_factor = self.factor_panel.index.get_level_values("datetime").max()
        object.__setattr__(self, "max_factor_date", pd.Timestamp(max_factor))
        if self.max_factor_date > is_end:
            raise IsEndLeakageError(
                f"factor date {self.max_factor_date.date()} > is_end {is_end.date()}"
            )
        realized = realization_date(self.max_factor_date, self.horizon, self.open_days)
        if realized is pd.NaT or pd.isna(realized):
            raise IsEndLeakageError(
                f"cannot resolve label-realization date for {self.max_factor_date.date()} "
                f"(horizon={self.horizon}) within the trading calendar"
            )
        object.__setattr__(self, "max_label_realization_date", pd.Timestamp(realized))
        if self.max_label_realization_date > is_end:
            raise IsEndLeakageError(
                f"label for factor date {self.max_factor_date.date()} realizes "
                f"{self.max_label_realization_date.date()} > is_end {is_end.date()} "
                f"(future-return leak)"
            )


@dataclass(frozen=True)
class WalkForwardResult:
    """Formal IS-only walk-forward evidence. Carries NO ``oos_*`` field. ``evidence_kind``
    is on the result AND on every per-factor row (rows = list of dicts)."""

    rows: list
    evidence_kind: str
    protocol: dict
    n_heldout_blocks: int
    effective_eval_end: pd.Timestamp
    is_end: pd.Timestamp

    def to_frame(self) -> pd.DataFrame:
        df = pd.DataFrame(self.rows)
        leaked = [c for c in df.columns if str(c).startswith("oos")]
        if leaked:  # defensive: must never happen
            raise IsEndLeakageError(f"WalkForwardResult must not carry oos_* fields: {leaked}")
        return df


def _slice_dates(obj, start, end):
    dt = obj.index.get_level_values("datetime")
    return obj[(dt >= pd.Timestamp(start)) & (dt <= pd.Timestamp(end))]


def _expected_direction(icir) -> str:
    """Signed-ICIR direction label (GPT Phase-7): admit inverse predictors without implying
    long-only-positive alpha. ``positive`` = higher factor predicts higher return;
    ``inverse`` = higher factor predicts LOWER return; ``undetermined`` = NaN/zero ICIR."""
    if icir is None or pd.isna(icir) or icir == 0:
        return "undetermined"
    return "positive" if icir > 0 else "inverse"


def build_is_windowed_panel(
    factor_panel: pd.DataFrame,
    adj_close: pd.Series,
    *,
    is_end,
    horizon: int = DEFAULT_HORIZON,
    trade_cal=None,
) -> IsWindowedPanel:
    """Build a validated :class:`IsWindowedPanel` from an IS-only factor panel + an IS-only
    adjusted-close series. The label uses the EXACT trading-calendar target — for factor
    date ``t`` the future price is taken at ``r(t) = open_days[pos(t)+h]``, NOT the "next
    ``h`` available rows" (GPT P0 review: a sparse/suspended adj-close would otherwise reach
    a LATER row, possibly past ``is_end``, while the calendar assertion reported a safe
    date). A missing ``r(t)`` row -> NaN -> dropped (never substituted by a later row).

    Belt 0 (GPT P0): both inputs MUST already be capped at ``is_end`` — verified here, never
    assumed."""
    open_days = load_open_trading_days(trade_cal)
    is_end_ts = pd.Timestamp(is_end)
    if factor_panel.empty or adj_close.empty:
        raise IsEndLeakageError("build_is_windowed_panel: empty factor panel / adj_close")
    f_max = pd.Timestamp(factor_panel.index.get_level_values("datetime").max())
    a_max = pd.Timestamp(adj_close.index.get_level_values("datetime").max())
    if f_max > is_end_ts:
        raise IsEndLeakageError(f"factor_panel max date {f_max.date()} > is_end {is_end_ts.date()}")
    if a_max > is_end_ts:
        raise IsEndLeakageError(f"adj_close max date {a_max.date()} > is_end {is_end_ts.date()}")

    adj = adj_close.sort_index()
    # exact-calendar realization date r(t) per unique factor date
    factor_dates = pd.DatetimeIndex(sorted(factor_panel.index.get_level_values("datetime").unique()))
    pos = open_days.searchsorted(factor_dates, side="left")
    target = pos + horizon
    real_map: dict = {}
    for fdate, tgt in zip(factor_dates, target):
        real_map[fdate] = open_days[tgt] if tgt < len(open_days) else pd.NaT

    insts = factor_panel.index.get_level_values("instrument")
    dts = factor_panel.index.get_level_values("datetime")
    r_for_rows = pd.DatetimeIndex([real_map.get(d, pd.NaT) for d in dts])

    # The future-price lookup reindexes ``adj`` POSITIONALLY by MultiIndex level, so
    # ``future_index`` MUST carry the SAME level order as the factor panel, and ``adj`` MUST
    # share it too. ``compute_factors`` returns (datetime, instrument); a hardcoded
    # (instrument, datetime) future index silently matches NOTHING and yields an all-NaN
    # label (real-data dry-run finding, 2026-06-01 — the synthetic fixtures only ever used
    # (instrument, datetime) order so the integration point was untested). Be robust to
    # EITHER input order, mirroring the factor_eval helpers' MultiIndex normalization.
    names = list(factor_panel.index.names)
    if set(names) != {"instrument", "datetime"}:
        raise IsEndLeakageError(
            f"build_is_windowed_panel expects an (instrument, datetime) MultiIndex; got names={names}"
        )
    if list(adj.index.names) != names:
        adj = adj.reorder_levels(names).sort_index()
    _future_levels = {"datetime": r_for_rows, "instrument": insts}
    future_index = pd.MultiIndex.from_arrays(
        [_future_levels[name] for name in names], names=names,
    )

    cur = adj.reindex(factor_panel.index)
    fut = adj.reindex(future_index)  # adj at the EXACT calendar r(t); missing -> NaN
    # Defensive guard: if current prices matched but EVERY future price is NaN, the reindex
    # aligned on the wrong levels (a MultiIndex-order regression) rather than hitting a
    # legitimately empty window — fail loud with a diagnosable message instead of the
    # generic "empty factor panel / label" from IsWindowedPanel.__post_init__.
    if bool(cur.notna().any()) and not bool(fut.notna().any()):
        raise IsEndLeakageError(
            "build_is_windowed_panel: future-price reindex matched zero rows while current "
            f"prices matched (factor names={names}, adj names={list(adj.index.names)}) — "
            "MultiIndex level-order mismatch, not an empty window."
        )
    label_vals = fut.to_numpy() / cur.to_numpy() - 1.0
    label = pd.Series(label_vals, index=factor_panel.index, name="label").dropna()
    aligned = factor_panel.loc[label.index]
    return IsWindowedPanel(
        factor_panel=aligned, label=label, is_end=is_end_ts,
        horizon=horizon, open_days=open_days,
    )


def load_is_windowed_panel(
    catalog: dict,
    time_split,
    *,
    horizon: int = DEFAULT_HORIZON,
    qlib_dir=None,
    trade_cal=None,
    compute_factors_fn=None,
    adj_close_expr: str | None = None,
) -> IsWindowedPanel:
    """Load factors + adjusted close over ``[is_start, is_end]`` ONLY, with
    ``horizons=None`` (belt 1), and build a validated :class:`IsWindowedPanel`. Loading is
    injectable via ``compute_factors_fn`` for tests."""
    from src.alpha_research.factor_library import operators

    cf = compute_factors_fn or operators.compute_factors
    adj_expr = adj_close_expr or getattr(operators, "ADJ_CLOSE", "$close * $adj_factor")
    qdir = str(qlib_dir or _DEFAULT_QLIB_DIR)
    is_start, is_end = time_split.is_start, time_split.is_end

    factor_panel, _ = cf(
        catalog=dict(catalog), start_date=is_start, end_date=is_end,
        horizons=None, qlib_dir=qdir, kernels=1, stage="is_only",
    )
    adj_panel, _ = cf(
        catalog={"adj_close": adj_expr}, start_date=is_start, end_date=is_end,
        horizons=None, qlib_dir=qdir, kernels=1, stage="is_only",
    )
    return build_is_windowed_panel(
        factor_panel, adj_panel["adj_close"], is_end=is_end, horizon=horizon, trade_cal=trade_cal,
    )


def _default_industry_series(index):
    """Production industry labels (PIT-safe SW2021 L1 membership as-of the row date)."""
    from src.data_infra.provider_metadata import build_industry_series_asof

    return build_industry_series_asof(index, "L1")


def load_is_windowed_panel_with_layer2(
    *,
    gated_base: list,
    gated_composite_defs: list,
    gated_industry_defs: list,
    time_split,
    horizon: int = DEFAULT_HORIZON,
    qlib_dir=None,
    trade_cal=None,
    compute_factors_fn=None,
    industry_series_fn=None,
    adj_close_expr: str | None = None,
) -> IsWindowedPanel:
    """IS-only panel for BASE + Layer-2 (composite / industry-relative) factors (Phase 7).

    Composites and industry-relative factors are SAME-DATE cross-sectional transforms of
    already-PIT-safe base factors (composite = weighted ``Σ cs_rank(±base)``; industry-relative
    = within-``(date, industry)`` demean / size-industry-neutralize), so they inherit the
    ``is_end`` boundary UNCHANGED: the base dependency closure is computed over
    ``[is_start, is_end]`` with ``horizons=None`` (belt 1), the SAME exact-calendar ``r(t)``
    label is used, and the SAME :class:`IsWindowedPanel` belts assert ``is_end``. Only the GATED
    columns (``gated_base`` + the named composites/industry-rel) become verdict columns;
    dependency-only bases (composite components / industry-rel bases not themselves gated) are
    computed as INPUTS and EXCLUDED from the panel (mirrors the Phase-3 selection contract).

    With empty composite/industry defs this is equivalent to :func:`load_is_windowed_panel` over
    ``gated_base``. ``industry_series_fn`` / ``compute_factors_fn`` are injectable for tests.
    """
    from src.alpha_research.factor_library import operators
    from src.alpha_research.factor_library.catalog import get_factor_catalog

    cf = compute_factors_fn or operators.compute_factors
    adj_expr = adj_close_expr or getattr(operators, "ADJ_CLOSE", "$close * $adj_factor")
    qdir = str(qlib_dir or _DEFAULT_QLIB_DIR)
    is_start, is_end = time_split.is_start, time_split.is_end

    base_catalog = get_factor_catalog(include_new_data=True)
    # dependency closure: gated bases + every composite component + every industry-rel base.
    dep = set(gated_base)
    for d in gated_composite_defs:
        dep.update(d.get("components", []))
    for d in gated_industry_defs:
        if d.get("base"):
            dep.add(d["base"])
    dep = sorted(x for x in dep if x)
    missing = [x for x in dep if x not in base_catalog]
    if missing:
        raise ValueError(
            f"load_is_windowed_panel_with_layer2: dependency base factors absent from the "
            f"catalog: {missing}"
        )

    base_panel, _ = cf(
        catalog={n: base_catalog[n] for n in dep}, start_date=is_start, end_date=is_end,
        horizons=None, qlib_dir=qdir, kernels=1, stage="is_only",
    )
    adj_panel, _ = cf(
        catalog={"adj_close": adj_expr}, start_date=is_start, end_date=is_end,
        horizons=None, qlib_dir=qdir, kernels=1, stage="is_only",
    )

    panel = base_panel
    if gated_composite_defs or gated_industry_defs:
        # belt-and-suspenders (GPT Phase-7 review): the cross-sectional Layer-2 ops require a
        # (datetime, instrument) panel. cs_rank is now name-based, but assert the exact order
        # here so a wrong-order panel fails LOUDLY before the formal Layer-2 compute.
        if list(base_panel.index.names) != ["datetime", "instrument"]:
            raise IsEndLeakageError(
                "layer2 base panel must be a ['datetime', 'instrument'] MultiIndex; got "
                f"{list(base_panel.index.names)}"
            )
    if gated_composite_defs:
        panel = operators.add_composites(panel, gated_composite_defs, progress_every=0)
    if gated_industry_defs:
        industry = (industry_series_fn or _default_industry_series)(panel.index)
        mcap = None
        if any(bool(d.get("requires_market_cap")) for d in gated_industry_defs):
            mcap_panel, _ = cf(
                catalog={"market_cap": "Ref($total_mv, 1)"}, start_date=is_start, end_date=is_end,
                horizons=None, qlib_dir=qdir, kernels=1, stage="is_only",
            )
            mcap = mcap_panel["market_cap"]
        panel = operators.add_industry_relative_composites(
            panel, industry, market_cap=mcap, defs=gated_industry_defs, progress_every=0,
        )

    gated_cols = (
        list(gated_base)
        + [d["name"] for d in gated_composite_defs]
        + [d["name"] for d in gated_industry_defs]
    )
    missing_cols = [c for c in gated_cols if c not in panel.columns]
    if missing_cols:
        raise ValueError(f"load_is_windowed_panel_with_layer2: gated columns not produced: {missing_cols}")
    return build_is_windowed_panel(
        panel[gated_cols], adj_panel["adj_close"], is_end=is_end, horizon=horizon, trade_cal=trade_cal,
    )


def _heldout_metrics_generated(factor: pd.Series, label: pd.Series, folds) -> tuple[float, float, int]:
    """Per-fold IS-internal heldout rank ICIR over each fold's TEST window, aggregated.
    heldout ICIR = nanmean of fold test ICIRs; sign_consistency = fraction of valid fold
    ICIRs matching the mean sign; n = number of valid folds."""
    fold_icirs = []
    for fold in folds:
        f_test = _slice_dates(factor, fold.test_start, fold.test_end)
        l_test = _slice_dates(label, fold.test_start, fold.test_end)
        if len(f_test) == 0:
            continue
        ic = metrics.factor_ic(f_test, l_test)
        icir = metrics.rank_icir(ic)
        if not pd.isna(icir):
            fold_icirs.append(icir)
    if not fold_icirs:
        return float("nan"), float("nan"), 0
    arr = np.array(fold_icirs, dtype=float)
    heldout = float(np.nanmean(arr))
    sign = np.sign(heldout)
    sign_consistency = float((np.sign(arr) == sign).sum()) / float(len(arr)) if sign != 0 else float("nan")
    return heldout, sign_consistency, len(arr)


def run_is_walk_forward(
    *,
    time_split,
    panel: IsWindowedPanel | None = None,
    catalog: dict | None = None,
    horizon: int = DEFAULT_HORIZON,
    factor_origin: str = "generated",
    field_eligible: dict | None = None,
    walk_forward_config: dict | None = None,
    qlib_dir=None,
    trade_cal=None,
    compute_factors_fn=None,
) -> WalkForwardResult:
    """FORMAL IS-only walk-forward (mode 1). Pass a pre-built ``panel`` (testable without
    Qlib) OR a ``catalog`` (loaded via :func:`load_is_windowed_panel`). For
    ``factor_origin='generated'`` uses an explicit IS-internal heldout (fail-closed if none
    can be built); for ``'a_priori'`` uses yearly blocked sign-consistency within IS,
    labeled distinctly. Returns a :class:`WalkForwardResult` with NO ``oos_*`` field."""
    # GPT P1 review: an unknown factor_origin must NOT silently take the a_priori path —
    # a typo in a generated-factor run would bypass the heldout fail-closed requirement.
    if factor_origin not in ("generated", "a_priori"):
        raise ValueError(
            f"factor_origin must be 'generated' or 'a_priori', got {factor_origin!r}"
        )
    if panel is None:
        if catalog is None:
            raise ValueError("run_is_walk_forward requires either `panel` or `catalog`")
        panel = load_is_windowed_panel(
            catalog, time_split, horizon=horizon, qlib_dir=qlib_dir,
            trade_cal=trade_cal, compute_factors_fn=compute_factors_fn,
        )
    is_end = pd.Timestamp(time_split.is_end)
    # belt-3 re-assertion (panel already validated on construction)
    if panel.max_label_realization_date > is_end:
        raise IsEndLeakageError("panel label-realization date crosses is_end")

    cfg = dict(walk_forward_config or DEFAULT_WF_CONFIG)
    folds, _holdout = build_walk_forward_folds(time_split.is_start, time_split.is_end, **cfg)

    rows: list[dict] = []
    if factor_origin == "generated":
        if not folds:
            raise NoHeldoutBlockError(
                f"no IS-internal heldout block for is_window [{time_split.is_start}, "
                f"{time_split.is_end}] with config {cfg} — a generated factor cannot become "
                f"candidate without heldout evidence (fail-closed)"
            )
        evidence_kind = "generated_heldout"
        n_blocks = len(folds)
        for name in panel.factor_panel.columns:
            heldout, sign_consistency, n_valid = _heldout_metrics_generated(
                panel.factor_panel[name], panel.label, folds,
            )
            fld_ok = True if field_eligible is None else bool(field_eligible.get(name, False))
            status, reason = assign_candidate_status(
                fld_ok, heldout, sign_consistency, evidence_kind=evidence_kind,
            )
            rows.append({
                "factor": name, "evidence_kind": evidence_kind, "heldout_rank_icir": heldout,
                "sign_consistency": sign_consistency, "n_heldout_blocks": n_valid,
                "status": status, "reason": reason,
                "expected_direction": _expected_direction(heldout),
            })
    else:  # a_priori
        evidence_kind = "a_priori"
        n_blocks = 0
        for name in panel.factor_panel.columns:
            ic = metrics.factor_ic(panel.factor_panel[name], panel.label)
            heldout = metrics.rank_icir(ic)
            sign_consistency = metrics.yearly_sign_consistency(ic, heldout)
            n_valid = metrics.yearly_fold_count(ic)
            n_blocks = max(n_blocks, n_valid)
            fld_ok = True if field_eligible is None else bool(field_eligible.get(name, False))
            status, reason = assign_candidate_status(
                fld_ok, heldout, sign_consistency, evidence_kind=evidence_kind,
            )
            rows.append({
                "factor": name, "evidence_kind": evidence_kind, "heldout_rank_icir": heldout,
                "sign_consistency": sign_consistency, "n_heldout_blocks": n_valid,
                "status": status, "reason": reason,
                "expected_direction": _expected_direction(heldout),
            })

    return WalkForwardResult(
        rows=rows, evidence_kind=evidence_kind, protocol={"factor_origin": factor_origin, **cfg},
        n_heldout_blocks=n_blocks, effective_eval_end=panel.max_label_realization_date, is_end=is_end,
    )
