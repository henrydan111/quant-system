from __future__ import annotations

from importlib import import_module
from typing import Any

from src.alpha_research.walk_forward import TimeSplit

from .hypothesis import (
    ExpectedEffect,
    Hypothesis,
    HypothesisSource,
    LaxCriteriaError,
    PreRegisteredConcerns,
    SuccessCriteria,
)
from .schema import AssetRef, ProducedObjectSpec, ResearchRequest, ResearchRunResult

__all__ = [
    "AssetRef",
    "ExpectedEffect",
    "Hypothesis",
    "HypothesisSource",
    "LaxCriteriaError",
    "PreRegisteredConcerns",
    "ProducedObjectSpec",
    "ResearchRequest",
    "ResearchRunResult",
    "SuccessCriteria",
    "TimeSplit",
    "profile_registry",
    "register_profile",
    "run_research",
    "_build_factor_screening_request_from_args",
    "_build_theme_request_from_args",
    "_build_event_request_from_args",
    "_build_ml_request_from_args",
    "_build_improvement_request_from_args",
    "_build_audit_request_from_args",
    "compile_research_plan",
    "resume_research",
]

_ENGINE_EXPORTS = {
    "_build_audit_request_from_args",
    "_build_event_request_from_args",
    "_build_factor_screening_request_from_args",
    "_build_improvement_request_from_args",
    "_build_ml_request_from_args",
    "_build_theme_request_from_args",
    "compile_research_plan",
    "profile_registry",
    "register_profile",
    "resume_research",
    "run_research",
}


def __getattr__(name: str) -> Any:
    if name in _ENGINE_EXPORTS:
        engine = import_module("src.research_orchestrator.engine")
        return getattr(engine, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
