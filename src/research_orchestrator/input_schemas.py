"""Registry of JSON Schemas for pause_for_input artifacts."""

from __future__ import annotations

from typing import Any


GATE_CONCERN_SCORES_V1: dict[str, Any] = {
    "type": "object",
    "required": ["scores"],
    "properties": {
        "scores": {
            "type": "array",
            "minItems": 4,
            "maxItems": 4,
            "items": {
                "type": "object",
                "required": [
                    "concern_id",
                    "concern_text",
                    "keyed_to_rule_id",
                    "measured_evidence_against_concern",
                    "quantitative_anchor",
                    "confirmed",
                    "severity",
                ],
                "properties": {
                    "concern_id": {
                        "type": "string",
                        "enum": [
                            "most_likely_failure_mode",
                            "weakest_assumption",
                            "what_would_falsify_this",
                            "priors_on_cost_sensitivity",
                        ],
                    },
                    "concern_text": {"type": "string", "minLength": 1},
                    "keyed_to_rule_id": {"type": "string", "minLength": 1},
                    "measured_evidence_against_concern": {"type": "string", "minLength": 80},
                    "quantitative_anchor": {"type": "object", "minProperties": 1},
                    "confirmed": {"type": "boolean"},
                    "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                },
                "additionalProperties": False,
            },
        }
    },
    "patternProperties": {"^_": {}},
    "additionalProperties": False,
}


SCHEMAS: dict[str, dict[str, Any]] = {
    "gate_concern_scores_v1": GATE_CONCERN_SCORES_V1,
}


def get_schema(schema_id: str) -> dict[str, Any]:
    if schema_id not in SCHEMAS:
        raise KeyError(f"Unknown schema_id: {schema_id}")
    return SCHEMAS[schema_id]
