"""SCOPED deep-slot staged build for the #59 stability test — the CORRECT, minimal version.

Lesson from the 1TB disk blowup (memory feedback_provider_build_disk_hazard): a deep-slot build MUST be
scoped. This builds slot_depth=16 single-quarter slots for ONLY the 7 fields the 2 STDEVQ(.,12) stability
factors need, for ONLY the #59 ranking universe, into a staged dir (NO publish):
  - touched_symbols = the ~4817 沪深 universe (from the cache) -> NO full-tree copy (the 241GB blowup)
  - field_filter = 7 base fields -> NO ~200-field materialization
  - datasets = income, balancesheet only; slot_depth = 16
Estimated size ~18GB (7 fields x ~24 bins x 4817 symbols), vs ~1TB unscoped. Driven via the Python API
because 4817 codes (~48KB) exceed the Windows command-line limit for --touched-symbols.

  python workspace/scripts/_build_deepslot_scoped.py --test   # 2 symbols, verify before scaling
  python workspace/scripts/_build_deepslot_scoped.py          # full 4817-symbol universe
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
from src.data_infra.pipeline.build_qlib_backend import build_unified_qlib, _resolve_paths  # noqa: E402

# 7 base fields whose _sq_q* slots the 2 stability factors read (6 income flows + 1 balancesheet equity)
FIELDS = ["revenue", "oper_cost", "admin_exp", "sell_exp", "fin_exp", "biz_tax_surchg",
          "total_hldr_eqy_exc_min_int"]


def main():
    test = "--test" in sys.argv
    if test:
        syms = ["600519.SH", "000001.SZ"]
        bid = "deepslot_scoped_test"
    else:
        uni = (ROOT / "workspace/outputs/guorn_parity/rung6_universe.txt").read_text().strip()
        syms = [s for s in uni.split(",") if s]
        bid = "deepslot_scoped"
    data_root, qlib_dir = _resolve_paths()
    print(f"[scoped-build] {bid}: {len(syms)} symbols | fields={FIELDS} | datasets=income,balancesheet | "
          f"slot_depth=16 | publish=False", flush=True)
    build_unified_qlib(
        data_root=data_root, qlib_dir=qlib_dir, field_filter=FIELDS,
        mode="update", stage="provider-only", datasets=["income", "balancesheet"],
        touched_symbols=syms, build_id=bid, slot_depth=16, publish=False, include_phase3=True)
    print(f"[scoped-build] DONE -> data/qlib_builds/{bid}/provider", flush=True)


if __name__ == "__main__":
    main()
