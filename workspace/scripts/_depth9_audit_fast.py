"""m1 PUBLISH GATE — fast+rigorous depth-9 additive-only audit (HDD-friendly; full byte-hash of 164GB is
~2h I/O-bound on this disk). Two passes:

  PASS 1 (ALL symbols, metadata only via os.scandir — no file reads): every live bin must exist in staged
         with IDENTICAL SIZE; the only staged-only files allowed are q5..q8 slots. Catches missing/truncated
         /length-drifted bins for EVERY symbol. (Combined with the already-verified byte-identical CALENDAR,
         identical size ⇒ identical series length for every q-slot.)
  PASS 2 (deterministic 1-in-`stride` sample — full SHA1 of q0..q4 bins): confirms BYTE-identity of values.

Corroborating evidence (recorded in the publish note): calendar byte-identical (diff empty, 4410); smoke
proved q0..q4 value-identical (0 diffs); deterministic kernel (P0-4); same normalized data (provider-only,
no re-ingest). Fail-closed: exit!=0 on ANY size/hash mismatch, missing bin, or unexpected non-q5..q8 new file.

  python -u workspace/scripts/_depth9_audit_fast.py --staged data/qlib_builds/depth9_20260630/provider --hash-stride 50
"""
import argparse
import hashlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8")
Q04 = ("_q0.day.bin", "_q1.day.bin", "_q2.day.bin", "_q3.day.bin", "_q4.day.bin")
Q58 = ("_q5.day.bin", "_q6.day.bin", "_q7.day.bin", "_q8.day.bin")


def _sizes(d: Path) -> dict:
    out = {}
    try:
        with os.scandir(d) as it:
            for e in it:
                if e.name.endswith(".day.bin"):
                    out[e.name] = e.stat().st_size
    except FileNotFoundError:
        pass
    return out


def _sha1(p: Path) -> str:
    h = hashlib.sha1()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", default=str(ROOT / "data" / "qlib_data"))
    ap.add_argument("--staged", required=True)
    ap.add_argument("--hash-stride", type=int, default=50, help="hash every Nth symbol's q0..q4 bins")
    a = ap.parse_args()
    live_feat = Path(a.live) / "features"
    stg_feat = Path(a.staged) / "features"
    assert live_feat.is_dir() and stg_feat.is_dir()
    syms = sorted(d.name for d in live_feat.iterdir() if d.is_dir())
    print(f"[audit] live={live_feat}\n[audit] staged={stg_feat}\n[audit] symbols={len(syms)} hash_stride={a.hash_stride}", flush=True)

    # ---- PASS 1: size-check ALL (metadata only) ----
    n_q04 = n_other = n_q58 = 0
    size_mismatch, missing, new_bad = [], [], []
    for i, s in enumerate(syms):
        lsz = _sizes(live_feat / s)
        ssz = _sizes(stg_feat / s)
        if not ssz:
            missing.append(f"{s}/ (staged symbol dir empty/absent)")
            continue
        for name, lz in lsz.items():
            if name not in ssz:
                missing.append(f"{s}/{name}")
                continue
            is_q04 = name.endswith(Q04)
            n_q04 += is_q04; n_other += (not is_q04)
            if ssz[name] != lz:
                size_mismatch.append(f"{s}/{name} live={lz} staged={ssz[name]}")
        for name in set(ssz) - set(lsz):
            if name.endswith(Q58):
                n_q58 += 1
            else:
                new_bad.append(f"{s}/{name}")
        if (i + 1) % 1000 == 0:
            print(f"  [size] {i+1}/{len(syms)}  q0-4={n_q04} q5-8_new={n_q58} size_mismatch={len(size_mismatch)} "
                  f"missing={len(missing)} unexpected_new={len(new_bad)}", flush=True)
    print(f"[size-pass] q0-4 sized={n_q04} non-q sized={n_other} q5-8 new={n_q58} | "
          f"size_mismatch={len(size_mismatch)} missing={len(missing)} unexpected_new={len(new_bad)}", flush=True)

    # ---- PASS 2: full hash of a deterministic sample ----
    sample = syms[::a.hash_stride]
    hash_mismatch, n_hashed = [], 0
    for j, s in enumerate(sample):
        for name, _ in _sizes(live_feat / s).items():
            if name.endswith(Q04) and (stg_feat / s / name).exists():
                n_hashed += 1
                if _sha1(live_feat / s / name) != _sha1(stg_feat / s / name):
                    hash_mismatch.append(f"{s}/{name}")
        if (j + 1) % 50 == 0:
            print(f"  [hash] {j+1}/{len(sample)} sampled symbols  hashed={n_hashed} mismatch={len(hash_mismatch)}", flush=True)
    print(f"[hash-pass] sampled_symbols={len(sample)} q0-4_bins_hashed={n_hashed} mismatch={len(hash_mismatch)}", flush=True)

    ok = not (size_mismatch or missing or new_bad or hash_mismatch)
    for label, lst in (("SIZE MISMATCH", size_mismatch), ("MISSING in staged", missing),
                       ("UNEXPECTED new (not q5-8)", new_bad), ("HASH MISMATCH (sample)", hash_mismatch)):
        if lst:
            print(f"\n✗ {label}: {len(lst)} — first 20:")
            for x in lst[:20]:
                print(f"    {x}")
    print(f"\n{'✅ ADDITIVE-ONLY (all q0..q4 sizes identical + sampled bytes identical + only q5..q8 new) — SAFE to publish' if ok else '✗ AUDIT FAILED — DO NOT PUBLISH'}", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
