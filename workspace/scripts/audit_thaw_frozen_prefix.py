# SCRIPT_STATUS: ACTIVE — calendar-unfreeze Phase 3.2 frozen-prefix audit (UNFREEZE_PLAN.md, B2)
"""Publish-blocking audit of the thaw staged provider vs the LIVE provider.

Checks (all must pass before safe publish):
  1. calendar: staged day.txt == live day.txt (4,410 lines) + append-only tail
  2. bins: every live bin exists in staged with size >= live size (ALL files);
     deterministic 1-in-50 symbol sample: SHA256(live bin bytes) ==
     SHA256(staged bin first len(live) bytes)  [frozen-prefix byte identity]
  3. sidecars (set discovered from the instruments dir, not hardcoded):
     day-by-day membership over the frozen calendar must be IDENTICAL.
Writes a JSON audit artifact; exit 1 on any violation.

THAW_MONTHLY_MODE=1 (set by the monthly-bump driver) runs STRICT: the one-time first-thaw
provenance exceptions (indicator-refetch SHA drift, sidecar suspension-healing) are disabled, so
a recurring bump against the settled parent must be byte- and membership-identical.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
LIVE = ROOT / "data" / "qlib_data"
# The staged provider tree to audit. The monthly-bump driver points this at the NEW
# staged build via THAW_STAGED_PROVIDER; falls back to the first-thaw default otherwise.
STAGED = Path(os.environ.get("THAW_STAGED_PROVIDER",
              str(ROOT / "data" / "qlib_builds" / "thaw_step1_20260703c" / "provider")))

# Monthly-bump STRICT mode (the driver sets THAW_MONTHLY_MODE=1): the first-thaw provenance
# exceptions below (indicator-refetch SHA drift, sidecar suspension-healing) are ONE-TIME and
# already baked into the SETTLED parent provider, so a recurring monthly bump must see a
# byte-identical frozen prefix + identical sidecars — ANY drift is a real regression, not a
# blanket-approved exception. A deliberate approved frozen-prefix correction is an out-of-band
# migration (its own gate + provider-id rotation), NEVER an automatic monthly bump. Standalone
# first-thaw runs leave the flag unset, so the historical exceptions still apply there.
MONTHLY_MODE = bool(os.environ.get("THAW_MONTHLY_MODE"))

# ── Approved exceptions (2026-07-03 diagnosis, UNFREEZE_PLAN 执行期注记 3) ──
# 1. indicators-family SHA drift: the 2026-06-08 167-col refetch + update_flag
#    revisions serving for the first time — the separately-approved
#    provenance-breaking migration. Recognized by field base name membership
#    in the indicators ledger columns (+ the derived profit_dedt_sq family).
# 2. sidecar suspension-boundary healing: ADDITIVE-only membership diffs for
#    the 10 diagnosed codes in all.txt / all_stocks.txt.
import re as _re

def _indicator_fields() -> set:
    import pandas as pd
    cols = pd.read_parquet(ROOT / "data" / "pit_ledger" / "indicators" / "indicators.parquet").columns
    base = {c for c in cols if c not in ("ts_code", "effective_date", "end_date")}
    base.add("profit_dedt_sq")
    return base

SIDECAR_EXC_CODES = {"000711_SZ","000793_SZ","001285_SZ","002445_SZ","300344_SZ",
                     "300391_SZ","301057_SZ","600438_SH","600673_SH","600735_SH",
                     # round-2: the round-1 violation line truncated codes at [:10];
                     # full diff = 12 codes, each verified strictly additive.
                     "603121_SH","603966_SH"}
SIDECAR_EXC_FILES = {"all.txt", "all_stocks.txt"}

def _field_base(field: str) -> str:
    return _re.sub(r"_q\d+$", "", field)
OUT = ROOT / "workspace" / "outputs" / "calendar_unfreeze" / "frozen_prefix_audit.json"
SAMPLE_EVERY = 50

report: dict = {"live": str(LIVE), "staged": str(STAGED),
                "monthly_strict_mode": MONTHLY_MODE, "violations": []}
V = report["violations"]


def check_calendar() -> list[str]:
    live_cal = (LIVE / "calendars" / "day.txt").read_text(encoding="utf-8").split()
    staged_cal = (STAGED / "calendars" / "day.txt").read_text(encoding="utf-8").split()
    if staged_cal[: len(live_cal)] != live_cal:
        V.append("calendar prefix mismatch")
    if len(staged_cal) <= len(live_cal):
        V.append(f"staged calendar not longer: {len(staged_cal)} vs {len(live_cal)}")
    report["calendar"] = {"live_days": len(live_cal), "staged_days": len(staged_cal),
                          "appended": staged_cal[len(live_cal):]}
    return live_cal


def check_bins() -> None:
    live_feat, staged_feat = LIVE / "features", STAGED / "features"
    IND_FIELDS = _indicator_fields()
    n_checked = n_missing = n_shrunk = n_sha = n_sha_bad = n_sha_exc = 0
    sha_examples = []
    symbols = sorted(os.listdir(live_feat))
    for si, sym in enumerate(symbols):
        sdir_live, sdir_staged = live_feat / sym, staged_feat / sym
        if not sdir_staged.is_dir():
            n_missing += 1
            V.append(f"symbol dir missing in staged: {sym}")
            continue
        sample = (si % SAMPLE_EVERY == 0)
        with os.scandir(sdir_live) as it:
            for entry in it:
                if not entry.name.endswith(".bin"):
                    continue
                n_checked += 1
                tgt = sdir_staged / entry.name
                lsize = entry.stat().st_size
                try:
                    tsize = tgt.stat().st_size
                except OSError:
                    n_missing += 1
                    if n_missing <= 20:
                        V.append(f"bin missing in staged: {sym}/{entry.name}")
                    continue
                if tsize < lsize:
                    n_shrunk += 1
                    if n_shrunk <= 20:
                        V.append(f"bin SHRUNK: {sym}/{entry.name} {lsize}->{tsize}")
                    continue
                if sample:
                    n_sha += 1
                    lb = Path(entry.path).read_bytes()
                    with open(tgt, "rb") as fh:
                        sb = fh.read(lsize)
                    if hashlib.sha256(lb).digest() != hashlib.sha256(sb).digest():
                        field = entry.name[:-8]
                        # report_rc completion: rows the freeze-era fetch missed
                        # (create_time mid/late-Feb), landed by the contracted
                        # 202602 overlap refetch — PIT-correct frozen-tail fill.
                        # In MONTHLY strict mode these one-time first-thaw exceptions do NOT
                        # apply (the settled parent must be byte-identical) -> any drift = bad.
                        if (_field_base(field) in IND_FIELDS or field.startswith("report_rc__")) and not MONTHLY_MODE:
                            n_sha_exc += 1
                        else:
                            n_sha_bad += 1
                            if len(sha_examples) < 10:
                                sha_examples.append(f"{sym}/{entry.name}")
        if si % 500 == 0:
            print(f"bins: {si}/{len(symbols)} symbols, checked={n_checked} sha={n_sha} bad={n_sha_bad}", flush=True)
    if n_sha_bad:
        V.append(f"frozen-prefix SHA mismatches: {n_sha_bad} (examples {sha_examples})")
    report["bins"] = {"symbols": len(symbols), "files_checked": n_checked,
                      "missing": n_missing, "shrunk": n_shrunk,
                      "sha_sampled": n_sha, "sha_mismatch": n_sha_bad,
                      "gross_sha_drift": n_sha_bad + n_sha_exc,
                      "sha_approved_exceptions_ind_or_reportrc": n_sha_exc,
                      "monthly_strict": MONTHLY_MODE}


def _membership(path: Path, cal: pd.DatetimeIndex) -> pd.DataFrame:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 3:
            rows.append((parts[0], parts[1], parts[2]))
    df = pd.DataFrame(rows, columns=["code", "start", "end"])
    lo = cal.searchsorted(pd.to_datetime(df["start"]), side="left")
    hi = cal.searchsorted(pd.to_datetime(df["end"]), side="right")
    import numpy as np

    codes = sorted(df["code"].unique())
    cidx = {c: i for i, c in enumerate(codes)}
    mat = np.zeros((len(cal), len(codes)), dtype=bool)
    for (c, _, _), a, b in zip(rows, lo, hi):
        mat[a:b, cidx[c]] = True
    return pd.DataFrame(mat, index=cal, columns=codes)


def check_sidecars(live_cal: list[str]) -> None:
    cal = pd.to_datetime(pd.Index(live_cal))  # frozen prefix only
    live_dir, staged_dir = LIVE / "instruments", STAGED / "instruments"
    discovered = sorted(f for f in os.listdir(live_dir) if f.endswith(".txt"))
    report["sidecars"] = {}
    for name in discovered:
        tgt = staged_dir / name
        if not tgt.exists():
            V.append(f"sidecar missing in staged: {name}")
            continue
        m_live = _membership(live_dir / name, cal)
        m_staged = _membership(tgt, cal)
        cols = sorted(set(m_live.columns) | set(m_staged.columns))
        a = m_live.reindex(columns=cols, fill_value=False)
        b = m_staged.reindex(columns=cols, fill_value=False)
        diff = (a != b)
        n_diff = int(diff.values.sum())
        report["sidecars"][name] = {"codes": len(cols), "cell_diffs": n_diff}
        if n_diff:
            bad_codes = [c for c in cols if diff[c].any()]
            additive = bool((b.values >= a.values).all())
            # MONTHLY strict: no first-thaw sidecar-healing exception — a settled parent must be
            # membership-identical, so any diff is a violation.
            if (not MONTHLY_MODE and name in SIDECAR_EXC_FILES
                    and set(bad_codes) <= SIDECAR_EXC_CODES and additive):
                report["sidecars"][name]["approved_exception"] = f"suspension-healing, {n_diff} additive cells"
            else:
                days = diff.any(axis=1)
                first_day = str(diff.index[days][0].date())
                V.append(f"sidecar membership drift {name}: {n_diff} cells, first day {first_day}, codes {bad_codes[:10]}")
        print(f"sidecar {name}: codes={len(cols)} diffs={n_diff}", flush=True)


def main() -> None:
    live_cal = check_calendar()
    check_sidecars(live_cal)
    check_bins()
    report["ok"] = not V
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("calendar", "sidecars", "bins", "ok")},
                     ensure_ascii=False, default=str)[:1500])
    sys.exit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
