"""Volcengine Ark (火山方舟 agent plan) chat client — the MVP AI-leg LLM door.

Provider decision (2026-07-08, user directive): the cheap/quick extraction layer
runs on the Ark agent plan (OpenAI-compatible endpoint). Two-tier roles stay as
designed (provider-agnostic, TradingAgents-style):

    quick (extraction/summary, thinking OFF) : doubao-seed-2.0-lite
    deep  (scorecard dimension scoring)      : doubao-seed-2.0-pro

Model choices are pre-registered config, part of `refinery_config_version` /
CandidateID (C16); changing them = a new version, never a silent swap.

C2 note (recorded): Ark model training cutoffs are NOT published → per C2 the
outputs are `historical_*`-class only, which is moot here because the MVP AI
leg is FORWARD-ONLY by design. Every call logs `model_id` + usage telemetry
(m1); temperature is pinned low; prompts are frozen+hashed upstream.

Secrets: `ARK_API_KEY` comes from the environment / repo `.env` (never
committed). This module is NON-FORMAL-path only (ai_layer boundary).
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/plan/v3"

#: pre-registered role -> model mapping (config artifact; change = new version)
ARK_MODELS = {
    "quick": "doubao-seed-2.0-lite",
    "deep": "doubao-seed-2.0-pro",
}
DEFAULT_TEMPERATURE = 0.1
DEFAULT_MAX_TOKENS = 2000
TIMEOUT_S = 120


class ArkClientError(Exception):
    """Fail-closed error for Ark calls (non-200, malformed reply, missing key)."""


def _load_api_key() -> str:
    key = os.environ.get("ARK_API_KEY", "").strip()
    if not key:
        env_file = _PROJECT_ROOT / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("ARK_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not key:
        raise ArkClientError("ARK_API_KEY not found in environment or .env")
    return key


@dataclass
class ArkReply:
    text: str
    model: str
    usage: dict          # prompt/completion tokens (m1 telemetry)
    latency_s: float
    raw: dict


def chat(
    messages: list[dict],
    *,
    model: str,
    thinking: bool | None = False,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    timeout_s: int = TIMEOUT_S,
) -> ArkReply:
    """One chat-completions call (OpenAI-compatible /api/plan/v3).

    ``thinking``: False -> request thinking disabled (reproducibility-first
    default for extraction/scoring); True -> enabled; None -> omit the field
    (model default). If the endpoint rejects the thinking field (400), the call
    is retried once WITHOUT it and the event is logged — never silently.
    """
    payload: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if thinking is not None:
        payload["thinking"] = {"type": "enabled" if thinking else "disabled"}

    headers = {
        "Authorization": f"Bearer {_load_api_key()}",
        "Content-Type": "application/json",
    }
    url = f"{ARK_BASE_URL}/chat/completions"

    t0 = time.time()
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout_s)
    if resp.status_code == 400 and "thinking" in payload:
        logger.warning("Ark rejected 'thinking' field for %s — retrying without it "
                       "(body: %.200s)", model, resp.text)
        payload.pop("thinking")
        t0 = time.time()
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout_s)
    latency = time.time() - t0

    if resp.status_code != 200:
        raise ArkClientError(f"Ark {resp.status_code} for {model}: {resp.text[:500]}")
    data = resp.json()
    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise ArkClientError(f"malformed Ark reply for {model}: {json.dumps(data)[:500]}") from e

    usage = data.get("usage", {})
    logger.info("ark call model=%s latency=%.1fs usage=%s", model, latency, usage)
    return ArkReply(text=text, model=data.get("model", model), usage=usage,
                    latency_s=latency, raw=data)


def parse_json_reply(text: str) -> dict:
    """Defensive JSON extraction: strips markdown fences (kimi-k2.6 behaviour),
    tolerates stray prose around the object, fails closed on no/invalid JSON."""
    t = text.strip()
    i, j = t.find("{"), t.rfind("}")
    if i == -1 or j <= i:
        raise ArkClientError(f"no JSON object in reply: {t[:200]}")
    blob = t[i:j + 1]
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        # occasional double-escaped replies (literal \n / \" between tokens)
        try:
            return json.loads(blob.replace("\\n", " ").replace('\\"', '"'))
        except json.JSONDecodeError as e:
            raise ArkClientError(f"invalid JSON in reply: {blob[:200]}") from e
