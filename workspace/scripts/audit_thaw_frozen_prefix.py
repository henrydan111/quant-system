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
STAGED = ROOT / "data" / "qlib_builds" / "thaw_step1_20260702b" / "provider"
OUT = ROOT / "workspace" / "outputs" / "calendar_unfreeze" / "frozen_prefix_audit.json"
SAMPLE_EVERY = 50

report: dict = {"live": str(LIVE), "staged": str(STAGED), "violations": []}
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
    n_checked = n_missing = n_shrunk = n_sha = n_sha_bad = 0
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
                        n_sha_bad += 1
                        if len(sha_examples) < 10:
                            sha_examples.append(f"{sym}/{entry.name}")
        if si % 500 == 0:
            print(f"bins: {si}/{len(symbols)} symbols, checked={n_checked} sha={n_sha} bad={n_sha_bad}", flush=True)
    if n_sha_bad:
        V.append(f"frozen-prefix SHA mismatches: {n_sha_bad} (examples {sha_examples})")
    report["bins"] = {"symbols": len(symbols), "files_checked": n_checked,
                      "missing": n_missing, "shrunk": n_shrunk,
                      "sha_sampled": n_sha, "sha_mismatch": n_sha_bad}


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
            days = diff.any(axis=1)
            first_day = str(diff.index[days][0].date())
            bad_codes = [c for c in cols if diff[c].any()][:10]
            V.append(f"sidecar membership drift {name}: {n_diff} cells, first day {first_day}, codes {bad_codes}")
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
