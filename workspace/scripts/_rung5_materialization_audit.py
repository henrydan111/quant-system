"""Materialization audit: (1) confirm the D&A single-quarter root cause, (2) diff EVERY raw
ledger numeric column against what's materialized into the live Qlib provider.

Mechanism (verified in pit_backend.py): a FULL build materializes _apply_field_filter(
payload_numeric_columns(ledger)); with an empty field_filter that is ALL numeric ledger columns.
So a numeric ledger column is "downloaded-but-unmaterialized" ONLY if it entered the ledger AFTER
the last full build of its dataset family. This audit finds those.

Read-only. NON-FORMAL diagnostic. Writes rung5_materialization_audit.json.
"""
from __future__ import annotations
import os, re, sys, json, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np
import pyarrow as pa
import pyarrow.dataset as pds

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from data_infra.pit_backend import CORE_METADATA_COLUMNS  # noqa: E402

FEAT = ROOT / "data/qlib_data/features"
LED = ROOT / "data/pit_ledger"


def _base_of(binname: str) -> str:
    n = binname[:-8] if binname.endswith(".day.bin") else binname
    n = re.sub(r"_(sq_q|cum_q|q)\d+$", "", n)   # strip slot suffixes
    n = re.sub(r"_q$", "", n)                    # strip the _q compat suffix
    return n


def _numeric_cols(schema) -> list[str]:
    out = []
    for f in schema:
        if (pa.types.is_integer(f.type) or pa.types.is_floating(f.type) or pa.types.is_decimal(f.type)) \
                and f.name not in CORE_METADATA_COLUMNS:
            out.append(f.name)
    return out


def main():
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(ROOT / "data/qlib_data"), region=REG_CN, kernels=1)
    results = {}

    # diverse stock sample (spread across boards) for breadth + materialized-set union
    alldirs = [d for d in os.listdir(FEAT) if len(d) == 9 and d[6] == "_"]
    samp = alldirs[:: max(1, len(alldirs) // 250)][:250]

    # ── (1) D&A root-cause breadth confirm ────────────────────────────────────
    fields = ["$depr_fa_coga_dpba_sq_q0", "$depr_fa_coga_dpba_cum_q0",
              "$amort_intang_assets_sq_q0", "$amort_intang_assets_cum_q0",
              "$c_pay_acq_const_fiolta_sq_q0"]
    df = D.features(samp, fields, start_time="2015-01-01", end_time="2025-12-31", freq="day")
    df.columns = [c.replace("$", "") for c in fields]
    print("=== (1) D&A breadth: non-NaN fraction over sample×history ===", flush=True)
    cov = {}
    for c in df.columns:
        cov[c] = round(float(df[c].notna().mean()), 5)
        print(f"  {c:34s} {cov[c]:.5f}", flush=True)
    results["dna_breadth"] = cov

    # ── (2) materialized base-field set (union over diverse stocks) ───────────
    mat = set()
    union_stocks = list(dict.fromkeys(samp[:40] + ["000001_sz", "600519_sh", "300750_sz", "601318_sh", "000651_sz"]))
    for s in union_stocks:
        d = FEAT / s
        if d.exists():
            for f in os.listdir(d):
                if f.endswith(".day.bin"):
                    mat.add(_base_of(f))
    print(f"\n=== (2) AUDIT: materialized base fields (union of {len(union_stocks)} stocks) = {len(mat)} ===", flush=True)

    audit = {}
    for ds_name in sorted(os.listdir(LED)):
        p = LED / ds_name
        if (not p.is_dir()) or ds_name.endswith(".pre_rebuild_backup"):
            continue
        try:
            schema = pds.dataset(str(p)).schema
        except Exception as e:
            print(f"  {ds_name}: SCHEMA ERR {e}", flush=True)
            continue
        cols = _numeric_cols(schema)
        missing = sorted(c for c in cols if c not in mat)
        audit[ds_name] = {"numeric_cols": len(cols), "unmaterialized": missing}
        flag = "  <-- GAP" if missing else ""
        print(f"  {ds_name:28s} {len(cols)-len(missing):3d}/{len(cols):3d} materialized; "
              f"{len(missing)} candidate-unmaterialized{flag}", flush=True)
        if missing:
            print(f"      {missing[:30]}", flush=True)
    results["audit"] = audit

    LED.parent  # noop
    OUT = ROOT / "workspace/outputs/guorn_parity/rung5_materialization_audit.json"
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n[done] wrote rung5_materialization_audit.json", flush=True)


if __name__ == "__main__":
    main()
