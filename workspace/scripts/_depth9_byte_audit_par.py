"""m1 PUBLISH GATE — PARALLEL full-hash variant of _depth9_byte_audit.py (I/O-bound → threads).

Same contract: every existing live bin must be byte-identical in the staged provider; the ONLY new files
allowed are q5..q8 slots. q0..q4 slots (`*_q[0-4].day.bin`) are HASHED (back prior formal evidence); non-q
bins size-checked (or --full-hash). Fail-closed: exit!=0 on any mismatch/missing/unexpected-new. Flushed
progress. ThreadPoolExecutor over symbols (single-threaded sha1 of 4.8M small files is ~2h; threaded ~20min).

  python -u workspace/scripts/_depth9_byte_audit_par.py --staged data/qlib_builds/depth9_20260630/provider --jobs 32
"""
import argparse
import hashlib
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8")
Q04 = ("_q0.day.bin", "_q1.day.bin", "_q2.day.bin", "_q3.day.bin", "_q4.day.bin")
Q58 = ("_q5.day.bin", "_q6.day.bin", "_q7.day.bin", "_q8.day.bin")


def _sha1(p: Path) -> str:
    h = hashlib.sha1()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _check_symbol(s: str, live_feat: Path, stg_feat: Path, full: bool) -> dict:
    ld, sd = live_feat / s, stg_feat / s
    r = {"q04": 0, "other": 0, "q58": 0, "mismatch": [], "missing": [], "new_bad": []}
    if not sd.is_dir():
        r["missing"].append(f"{s}/ (symbol dir absent in staged)")
        return r
    live_files = {p.name for p in ld.glob("*.day.bin")}
    stg_files = {p.name for p in sd.glob("*.day.bin")}
    for name in live_files:
        sp = sd / name
        if not sp.exists():
            r["missing"].append(f"{s}/{name}")
            continue
        if name.endswith(Q04):
            r["q04"] += 1
            if _sha1(ld / name) != _sha1(sp):
                r["mismatch"].append(f"{s}/{name}")
        else:
            r["other"] += 1
            if full:
                if _sha1(ld / name) != _sha1(sp):
                    r["mismatch"].append(f"{s}/{name}")
            elif (ld / name).stat().st_size != sp.stat().st_size:
                r["mismatch"].append(f"{s}/{name} (size)")
    for name in stg_files - live_files:
        if name.endswith(Q58):
            r["q58"] += 1
        else:
            r["new_bad"].append(f"{s}/{name}")
    return r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", default=str(ROOT / "data" / "qlib_data"))
    ap.add_argument("--staged", required=True)
    ap.add_argument("--full-hash", action="store_true")
    ap.add_argument("--jobs", type=int, default=32)
    a = ap.parse_args()
    live_feat = Path(a.live) / "features"
    stg_feat = Path(a.staged) / "features"
    assert live_feat.is_dir() and stg_feat.is_dir()
    syms = sorted(d.name for d in live_feat.iterdir() if d.is_dir())
    print(f"[audit] live={live_feat}\n[audit] staged={stg_feat}\n[audit] symbols={len(syms)} jobs={a.jobs} full_hash={a.full_hash}", flush=True)

    tot = {"q04": 0, "other": 0, "q58": 0}
    mismatch, missing, new_bad = [], [], []
    done = 0
    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        futs = {ex.submit(_check_symbol, s, live_feat, stg_feat, a.full_hash): s for s in syms}
        for fut in as_completed(futs):
            r = fut.result()
            for k in ("q04", "other", "q58"):
                tot[k] += r[k]
            mismatch += r["mismatch"]; missing += r["missing"]; new_bad += r["new_bad"]
            done += 1
            if done % 500 == 0:
                print(f"  …{done}/{len(syms)} symbols  q0-4_hashed={tot['q04']} q5-8_new={tot['q58']} "
                      f"mismatch={len(mismatch)} missing={len(missing)} unexpected_new={len(new_bad)}", flush=True)

    print(f"\n[audit] q0-4 slots hashed = {tot['q04']}")
    print(f"[audit] non-q bins checked = {tot['other']} ({'hashed' if a.full_hash else 'size-only'})")
    print(f"[audit] q5-8 NEW slots     = {tot['q58']}")
    ok = not (mismatch or missing or new_bad)
    for label, lst in (("MISMATCH (live≠staged)", mismatch), ("MISSING in staged", missing),
                       ("UNEXPECTED new (not q5-8)", new_bad)):
        if lst:
            print(f"\n✗ {label}: {len(lst)} — first 20:")
            for x in lst[:20]:
                print(f"    {x}")
    print(f"\n{'✅ ADDITIVE-ONLY: staged byte-identical to live except new q5..q8 — SAFE to publish' if ok else '✗ AUDIT FAILED — DO NOT PUBLISH'}", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
