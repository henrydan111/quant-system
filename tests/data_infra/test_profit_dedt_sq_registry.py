"""Field-registry smoke test for $profit_dedt_sq_q0 (GPT Phase-C R2 Blocker follow-up).

Activates only AFTER the post-publish registration (_register_phasec.py) adds $profit_dedt_sq_q0 to the
indicators block of the COMMITTED field_status.yaml. Pre-registration it SKIPS (the field is intentionally
NOT registered until the provider attests to it — §3.4), so the branch is green pre-publish. Post-publish it
actively pins: the field resolves as `approved` under dataset `indicators` at every formal stage, and is NOT
mis-registered under income (GPT R2 Major-2).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from data_infra.field_registry import load_field_registry

ROOT = Path(__file__).resolve().parents[2]
FIELD = "$profit_dedt_sq_q0"
FIELD_STATUS = ROOT / "config" / "field_registry" / "field_status.yaml"


def _registered() -> bool:
    return FIELD_STATUS.exists() and f"- {FIELD}" in FIELD_STATUS.read_text(encoding="utf-8")


@pytest.mark.skipif(not _registered(),
                    reason=f"{FIELD} not yet registered (pre-publish; registered post-publish by _register_phasec.py)")
def test_profit_dedt_sq_q0_resolves_approved_under_indicators():
    reg = load_field_registry()
    for stage in ("sandbox_screening", "vectorized_screening", "formal_validation", "oos_test", "registry_publish"):
        r = reg.resolve_field(FIELD, stage)
        assert r.allowed is True, f"{FIELD} blocked at {stage} (status={r.status_id}, dataset={r.dataset_id})"
        assert r.status_id == "approved", f"{FIELD} status {r.status_id} != approved at {stage}"
        # GPT R2 Major-2: indicators-derived, NOT income.
        assert r.dataset_id == "indicators", f"{FIELD} mis-registered under {r.dataset_id}, expected indicators"
