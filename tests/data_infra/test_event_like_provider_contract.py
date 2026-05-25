from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FEATURE_DIR = PROJECT_ROOT / "data" / "qlib_data" / "features" / "000001_sz"


def test_published_provider_uses_event_like_namespaced_files():
    if not FEATURE_DIR.exists():
        pytest.skip("published Qlib provider is not available in this workspace")

    required_namespaced = {
        "top_list__amount.day.bin",
        "top_list__l_buy.day.bin",
        "top_inst__net_buy.day.bin",
        "block_trade__amount.day.bin",
        "cyq_perf__winner_rate.day.bin",
    }
    missing = [name for name in sorted(required_namespaced) if not (FEATURE_DIR / name).exists()]
    assert not missing, (
        f"000001_sz is missing namespaced event-like provider files: {missing}. "
        "A rebuilt provider must expose event payloads as dataset__field names so they cannot "
        "shadow canonical OHLCV fields."
    )

    stale_unprefixed = {
        "l_buy.day.bin",
        "net_buy.day.bin",
        "winner_rate.day.bin",
        "price.day.bin",
    }
    present = [name for name in sorted(stale_unprefixed) if (FEATURE_DIR / name).exists()]
    assert not present, (
        f"000001_sz still has stale unprefixed event-like files: {present}. "
        "These names indicate an old provider build that can silently confuse event fields with market fields."
    )
