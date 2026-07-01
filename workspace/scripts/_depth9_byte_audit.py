"""m1 PUBLISH GATE (GPT §10) — prove the depth-9 staged provider is ADDITIVE-ONLY vs the live provider.

Every existing live bin MUST be byte-identical in the staged provider; the ONLY new files allowed are q5..q8
slots (`*_q[5-8].day.bin`). q0..q4 periodic slots (`*_q[0-4].day.bin`, incl. `_sq_q*` / `_cum_q*` which also
end `_q[0-4].day.bin`) are HASHED (these back prior formal evidence — they must not move). Non-q-slot bins
(daily kline etc.) are size-checked by default, hashed under --full-hash. Exit non-zero on ANY mismatch /
missing / unexpected-new — FAIL-CLOSED: do not publish if this does not exit 0.

  python workspace/scripts/_depth9_byte_audit.py --staged data/qlib_builds/depth9_20260630/provider
  python workspace/scripts/_depth9_byte_audit.py --staged <...> --full-hash   # hash daily bins too (slower)
"""
import argparse
import hashlib
import sys
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", default=str(ROOT / "data" / "qlib_data"))
    ap.add_argument("--staged", required=True, help="data/qlib_builds/<id>/provider")
    ap.add_argument("--full-hash", action="store_true", help="hash non-q-slot (daily) bins too (slower)")
    a = ap.parse_args()
    live_feat = Path(a.live) / "features"
    stg_feat = Path(a.staged) / "features"
    assert live_feat.is_dir(), f"no live features at {live_feat}"
    assert stg_feat.is_dir(), f"no staged features at {stg_feat}"

    syms = sorted(d.name for d in live_feat.iterdir() if d.is_dir())
    print(f"[audit] live={live_feat}\n[audit] staged={stg_feat}\n[audit] symbols={len(syms)} full_hash={a.full_hash}")
    mismatch, missing, new_bad = [], [], []
    n_q04_hashed = n_other = n_q58 = 0

    for i, s in enumerate(syms):
        ld, sd = live_feat / s, stg_feat / s
        if not sd.is_dir():
            missing.append(f"{s}/ (whole symbol dir absent in staged)")
            continue
        live_files = {p.name for p in ld.glob("*.day.bin")}
        stg_files = {p.name for p in sd.glob("*.day.bin")}
        # every live bin must exist + match in staged
        for name in live_files:
            sp = sd / name
            if not sp.exists():
                missing.append(f"{s}/{name}")
                continue
            if name.endswith(Q04):
                n_q04_hashed += 1
                if _sha1(ld / name) != _sha1(sp):
                    mismatch.append(f"{s}/{name}")
            else:
                n_other += 1
                if a.full_hash:
                    if _sha1(ld / name) != _sha1(sp):
                        mismatch.append(f"{s}/{name}")
                elif (ld / name).stat().st_size != sp.stat().st_size:
                    mismatch.append(f"{s}/{name} (size)")
        # staged-only files must be q5..q8 additions
        for name in stg_files - live_files:
            if name.endswith(Q58):
                n_q58 += 1
            else:
                new_bad.append(f"{s}/{name}")
        if (i + 1) % 200 == 0:
            print(f"  …{i+1}/{len(syms)}  q0-4_hashed={n_q04_hashed} other={n_other} q5-8_new={n_q58} "
                  f"mismatch={len(mismatch)} missing={len(missing)} unexpected_new={len(new_bad)}", flush=True)

    print(f"\n[audit] q0-4 slots hashed = {n_q04_hashed}")
    print(f"[audit] non-q bins checked = {n_other} ({'hashed' if a.full_hash else 'size-only'})")
    print(f"[audit] q5-8 NEW slots     = {n_q58}")
    ok = not (mismatch or missing or new_bad)
    for label, lst in (("MISMATCH (live≠staged)", mismatch), ("MISSING in staged", missing),
                       ("UNEXPECTED new (not q5-8)", new_bad)):
        if lst:
            print(f"\n✗ {label}: {len(lst)} — first 20:")
            for x in lst[:20]:
                print(f"    {x}")
    print(f"\n{'✅ ADDITIVE-ONLY: staged is byte-identical to live except for new q5..q8 slots — SAFE to publish' if ok else '✗ AUDIT FAILED — DO NOT PUBLISH'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
