# SCRIPT_STATUS: ACTIVE — strategy-build skill CLI (Part-G D4); thin coordinator over factor_eval_skill.orchestration
"""strategy-build CLI — the strategy-SPECIFIC half (Stage 8) of the methodology (v1.3).

Verb: deploy (the ONLY verb — it CANNOT seal; the forbidden-verb invariant is structural,
seal lives only in factor_eval_cli.py). deploy REQUIRES frozen_set_hash + envelope_hash +
target_universe_declaration_hash (from the seal artifact) and re-checks the full identity
chain (incl. the plan) before any deployment run. See FACTOR_EVAL_PARTG_BUILD_DESIGN.md (v2, D4).
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
    FactorEvalContext,
    FactorEvalError,
    cmd_deploy,
)

DEFAULT_STORE = ROOT / "data" / "factor_eval_skill"
DEFAULT_REGISTRY = ROOT / "data" / "factor_registry"


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="strategy-build")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--store-root", default=str(DEFAULT_STORE))
    ap.add_argument("--registry-root", default=str(DEFAULT_REGISTRY))
    sub = ap.add_subparsers(dest="cmd", required=True)

    de = sub.add_parser("deploy")
    de.add_argument("--mode", choices=["show", "dryrun", "live"], default="show")
    de.add_argument("--deployment-universe", required=True)
    de.add_argument("--portfolio-side", required=True)
    de.add_argument("--construction", required=True, help="JSON construction spec")
    de.add_argument("--pre-declared-bar", required=True, help="JSON pass/fail bar")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ctx = FactorEvalContext.create(run_dir=args.run_dir, store_root=args.store_root,
                                   registry_root=args.registry_root)
    try:
        if args.cmd == "deploy":
            out = cmd_deploy(ctx, mode=args.mode, deployment_universe=args.deployment_universe,
                             portfolio_side=args.portfolio_side, construction=json.loads(args.construction),
                             pre_declared_bar=json.loads(args.pre_declared_bar))
        else:  # pragma: no cover
            raise FactorEvalError(f"unknown command {args.cmd}")
        print(json.dumps(out, indent=2, default=str))
        return 0
    except FactorEvalError as exc:
        print(f"[strategy-build] FAIL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
