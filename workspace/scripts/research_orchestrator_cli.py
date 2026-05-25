from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research_orchestrator.capabilities import describe_capabilities
from src.research_orchestrator import ResearchRequest, profile_registry, run_research
from src.research_orchestrator.engine import compile_research_plan, resume_research


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unified entrypoint for formal research profiles.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("profiles", help="List built-in research profiles")

    plan_parser = subparsers.add_parser("plan", help="Compile a research request into a DAG plan")
    plan_parser.add_argument("--request-file", required=True, help="Path to a JSON-serialized ResearchRequest")

    run_parser = subparsers.add_parser("run", help="Run research from a JSON request file")
    run_parser.add_argument("--request-file", required=True, help="Path to a JSON-serialized ResearchRequest")

    resume_parser = subparsers.add_parser("resume", help="Resume a previous DAG run from its run directory")
    resume_parser.add_argument("--run-dir", required=True, help="Run directory containing dag_plan.json and dag_state.json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "profiles":
        payload = {}
        for profile_id, profile in profile_registry().all_profiles().items():
            payload[profile_id] = {
                "supported_modes": list(profile.supported_modes),
                "consumes_types": list(profile.consumes_types),
                "produces_types": list(profile.produces_types),
                "default_capabilities": list(profile.default_capabilities),
                "default_capability_metadata": describe_capabilities(profile.default_capabilities),
                "formal_requires_resolver": bool(profile.formal_requires_resolver),
                "execution_model": profile.execution_model,
            }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.command == "resume":
        result = resume_research(Path(args.run_dir).resolve())
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=str))
        return 0

    request_path = Path(args.request_file).resolve()
    request_payload = json.loads(request_path.read_text(encoding="utf-8-sig"))
    request = ResearchRequest.from_dict(request_payload)
    if args.command == "plan":
        print(json.dumps(compile_research_plan(request), ensure_ascii=False, indent=2, default=str))
        return 0

    result = run_research(request)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
