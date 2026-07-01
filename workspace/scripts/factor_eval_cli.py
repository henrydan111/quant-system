# SCRIPT_STATUS: ACTIVE — factor-eval skill CLI (Part-G D4); thin coordinator over factor_eval_skill.orchestration
"""factor-eval CLI — the strategy-AGNOSTIC half of the factor-evaluation methodology (v1.3).

Verbs: register | declare_target | characterize | gate | select | seal. It CANNOT deploy
(the forbidden-verb invariant is structural — deploy lives only in strategy_build_cli.py).
Each command reads/writes JSON artifacts under --run-dir and delegates all compute to
src/alpha_research/factor_eval_skill/. See FACTOR_EVAL_PARTG_BUILD_DESIGN.md (v2, D4).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from src.alpha_research.factor_eval_skill.orchestration import (  # noqa: E402
    MODES,
    FactorEvalContext,
    FactorEvalError,
    cmd_characterize,
    cmd_declare_target,
    cmd_gate,
    cmd_register,
    cmd_select,
    cmd_seal,
)

DEFAULT_STORE = ROOT / "data" / "factor_eval_skill"
DEFAULT_REGISTRY = ROOT / "data" / "factor_registry"
DEFAULT_HOLDOUT = ROOT / "data" / "holdout_seals"


def _json(text: str) -> dict:
    return json.loads(text) if text else {}


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="factor-eval")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--store-root", default=str(DEFAULT_STORE))
    ap.add_argument("--registry-root", default=str(DEFAULT_REGISTRY))
    ap.add_argument("--holdout-seal-root", default=str(DEFAULT_HOLDOUT),
                    help="global cross-run holdout-seal store (used by seal --mode live)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("register")
    r.add_argument("--factor-id", required=True)
    r.add_argument("--mode", choices=MODES, required=True)
    r.add_argument("--evidence-tier", required=True)
    r.add_argument("--direction-source", required=True)
    r.add_argument("--role", required=True)
    r.add_argument("--role-direction", required=True)
    r.add_argument("--multiplicity-scope-id", default="")
    r.add_argument("--filter-role-subtype", default="")

    dt = sub.add_parser("declare_target")
    dt.add_argument("--target-universe-id", required=True)
    dt.add_argument("--eligibility-policy", required=True)
    dt.add_argument("--asof-policy", required=True)
    dt.add_argument("--filters", default="")

    ch = sub.add_parser("characterize")
    ch.add_argument("--matrix", required=True)
    ch.add_argument("--factor-class", choices=["native", "cohort"], default=None)
    ch.add_argument("--replication-tier", default="")
    ch.add_argument("--claim-class", default="")
    ch.add_argument("--oos-eligibility", default="")

    sub.add_parser("gate")

    se = sub.add_parser("select")
    se.add_argument("--matrix", required=True)
    se.add_argument("--pool", required=True, help='JSON {factor_id: family}')
    se.add_argument("--caps", required=True, help='JSON {family: cap}')
    se.add_argument("--floor", type=float, default=0.10)
    se.add_argument("--references", default="[]")
    se.add_argument("--n", type=int, default=None)
    se.add_argument("--corr", default=None, help="precomputed exposure-correlation parquet (required for multi-factor pools)")
    se.add_argument("--selection-universe", default=None, help="selection basis universe (default: the declared target)")

    sl = sub.add_parser("seal")
    sl.add_argument("--mode", choices=["show", "live"], default="show",
                    help="show = identity/multiplicity preview (no OOS); live = the only OOS-access mode")
    sl.add_argument("--oos-start", default="")
    sl.add_argument("--oos-end", default="")
    sl.add_argument("--qlib-dir", default=str(ROOT / "data" / "qlib_data"))
    sl.add_argument("--horizon", type=int, default=20)
    sl.add_argument("--n-quantiles", type=int, default=10)
    sl.add_argument("--portfolio-side", default="long_short",
                    choices=["long_short", "long_only", "short_only", "market_neutral"])
    sl.add_argument("--multiplicity-ack", action="store_true", help="acknowledge the OOS-window multiplicity (warn band)")
    sl.add_argument("--multiplicity-override", action="store_true", help="override the OOS-window multiplicity hard band")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ctx = FactorEvalContext.create(run_dir=args.run_dir, store_root=args.store_root,
                                   registry_root=args.registry_root,
                                   holdout_seal_root=args.holdout_seal_root)
    try:
        if args.cmd == "register":
            out = cmd_register(ctx, factor_id=args.factor_id, mode=args.mode, evidence_tier=args.evidence_tier,
                               direction_source=args.direction_source, role=args.role,
                               role_direction=args.role_direction, multiplicity_scope_id=args.multiplicity_scope_id,
                               filter_role_subtype=args.filter_role_subtype)
        elif args.cmd == "declare_target":
            out = cmd_declare_target(ctx, target_universe_id=args.target_universe_id,
                                     eligibility_policy=args.eligibility_policy, asof_policy=args.asof_policy,
                                     universe_definition_filters=_json(args.filters))
        elif args.cmd == "characterize":
            out = cmd_characterize(ctx, matrix_path=args.matrix, factor_class=args.factor_class,
                                   replication_tier=args.replication_tier, claim_class=args.claim_class,
                                   oos_eligibility=args.oos_eligibility)
        elif args.cmd == "gate":
            out = cmd_gate(ctx)
        elif args.cmd == "select":
            out = cmd_select(ctx, matrix_path=args.matrix, pool=_json(args.pool), caps=_json(args.caps),
                             floor=args.floor, references=json.loads(args.references), n=args.n,
                             corr_path=args.corr, selection_universe=args.selection_universe)
        elif args.cmd == "seal":
            out = cmd_seal(ctx, mode=args.mode, oos_start=args.oos_start, oos_end=args.oos_end,
                           qlib_dir=args.qlib_dir, horizon=args.horizon, n_quantiles=args.n_quantiles,
                           portfolio_side=args.portfolio_side, multiplicity_ack=args.multiplicity_ack,
                           multiplicity_override=args.multiplicity_override)
        else:  # pragma: no cover
            raise FactorEvalError(f"unknown command {args.cmd}")
        print(json.dumps(out, indent=2, default=str))
        return 0
    except FactorEvalError as exc:
        print(f"[factor-eval] FAIL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
