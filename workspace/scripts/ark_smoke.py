# SCRIPT_STATUS: ACTIVE — one-off Ark endpoint smoke test (2 calls, quick+deep)
"""Verify the Ark agent-plan endpoint, auth, thinking toggle and JSON discipline.

Sends ONE tiny extraction-shaped task to each pre-registered role model and
prints latency/usage/output. This is the empirical documentation check (the
docs page is JS-rendered); it also validates the JSON-only output discipline
the scorecard layer will rely on.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import logging  # noqa: E402
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

from ai_layer.ark_client import ARK_MODELS, chat  # noqa: E402

PROMPT = (
    "你是信息抽取器。只输出 JSON,不要任何其他文字。\n"
    "从下面公告标题抽取:{\"event_type\": \"业绩|订单|回购|减持|诉讼|其他\", "
    "\"direction\": \"pos|neg|neutral\"}\n\n"
    "公告标题:关于回购注销部分限制性股票减少注册资本的公告"
)


def main() -> int:
    for role, model in ARK_MODELS.items():
        print(f"\n=== {role}: {model} (thinking=off) ===", flush=True)
        r = chat([{"role": "user", "content": PROMPT}], model=model, thinking=False,
                 max_tokens=200)
        print(f"latency={r.latency_s:.1f}s usage={r.usage}", flush=True)
        print(f"output: {r.text[:300]}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
