# Macro wave M1: MS01-MS05 exposure rows — declared-invariant tests.
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from workspace.research.ai_research_dept.engine.macro_exposure import (  # noqa: E402
    MS_DIMENSIONS, MS_ROW_KEYS, MappingAssetError, build_ms_exposure_rows,
    exposure_mapping_bundle_sha256, load_default_mappings, load_mapping_asset,
    MAPPING_DIR,
)

SMIC = "688981.SH"        # 电子 801080.SI(PIT 已验证)
MAOTAI = "600519.SH"      # 食品饮料 801120.SI
DAY = "20250127"
CUT = "2025-01-27 18:00:00"

SW_L1_ALL = [
    "801010.SI", "801030.SI", "801040.SI", "801050.SI", "801080.SI",
    "801110.SI", "801120.SI", "801130.SI", "801140.SI", "801150.SI",
    "801160.SI", "801170.SI", "801180.SI", "801200.SI", "801210.SI",
    "801230.SI", "801710.SI", "801720.SI", "801730.SI", "801740.SI",
    "801750.SI", "801760.SI", "801770.SI", "801780.SI", "801790.SI",
    "801880.SI", "801890.SI", "801950.SI", "801960.SI", "801970.SI",
    "801980.SI",
]


@pytest.fixture(scope="module")
def mappings():
    return load_default_mappings()


def _pool(n=9, include=SMIC):
    rows = [{"ts_code": f"00000{i}.SZ", "float_mv": (i + 1) * 1e9,
             "turnover_20d": (i + 1) * 0.5, "vol_20d": (i + 1) * 0.05}
            for i in range(n - 1)]
    rows.append({"ts_code": include, "float_mv": 5e9, "turnover_20d": 2.0,
                 "vol_20d": 0.2})
    return pd.DataFrame(rows)


def _ths(fetched="2025-01-01T00:00:00"):
    return pd.DataFrame([
        {"ts_code": "883418.TI", "con_code": SMIC, "con_name": "x",
         "fetched_at": fetched},
        {"ts_code": "883300.TI", "con_code": SMIC, "con_name": "x",
         "fetched_at": fetched},
    ])


# ------------------------------------------------ mapping assets

def test_both_mapping_assets_load_and_cover_all_31_l1(mappings):
    for key in ("policy", "shock"):
        mp = mappings[key]
        assert set(mp["map"]) == set(SW_L1_ALL)        # exhaustive, no drift
        assert len(mp["mapping_sha256"]) == 64
    assert mappings["policy"]["mapping_id"] == "ms04_policy_channels"
    assert mappings["shock"]["mapping_id"] == "ms05_shock_channels"


def test_malformed_mapping_refused(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("mapping_id: x\nmapping_version: v1\nkey_type: sw2021_l1_code\n"
                   "channels: [a]\nmap:\n  \"801080.SI\": [b]\n", encoding="utf-8")
    with pytest.raises(MappingAssetError, match="未在 channels 注册"):
        load_mapping_asset(bad)


def test_bundle_hash_moves_with_content(tmp_path, mappings):
    import shutil
    h1 = exposure_mapping_bundle_sha256(mappings)
    alt = tmp_path / "ms04_policy_channels_v1.yaml"
    shutil.copy(MAPPING_DIR / "ms04_policy_channels_v1.yaml", alt)
    alt.write_text(alt.read_text(encoding="utf-8") + "\n# tweak\n",
                   encoding="utf-8")
    tweaked = dict(mappings)
    tweaked["policy"] = load_mapping_asset(alt)
    assert exposure_mapping_bundle_sha256(tweaked) != h1


# ------------------------------------------------ the five rows

def test_exactly_five_rows_frozen_schema(mappings):
    rows = build_ms_exposure_rows(SMIC, DAY, cutoff=CUT, pool_metrics=_pool(),
                                  ths_members=_ths(), mappings=mappings)
    assert [r["row_id"] for r in rows] == [rid for rid, _ in MS_DIMENSIONS]
    for r in rows:
        assert set(r) == MS_ROW_KEYS                   # strict 12-key schema
        assert r["ts_code"] == SMIC


def test_ms01_ms02_pool_terciles(mappings):
    rows = build_ms_exposure_rows(SMIC, DAY, cutoff=CUT, pool_metrics=_pool(),
                                  ths_members=_ths(), mappings=mappings)
    ms01, ms02 = rows[0], rows[1]
    assert ms01["mapping_status"] == "mapped"
    assert "float_mv_" in ms01["exposure_bucket"] and "vol_20d_" in ms01["exposure_bucket"]
    assert ms01["exposure_value"]["float_mv"] == 5e9
    assert ms02["mapping_status"] == "mapped"
    assert ms02["exposure_bucket"].startswith("turnover_20d_")


def test_missing_metrics_is_metric_unavailable_not_zero(mappings):
    rows = build_ms_exposure_rows(SMIC, DAY, cutoff=CUT,
                                  pool_metrics=_pool(include="999999.SZ"),
                                  ths_members=_ths(), mappings=mappings)
    assert rows[0]["mapping_status"] == "metric_unavailable"
    assert rows[0]["exposure_value"] is None           # never a fabricated 0


def test_ms03_pit_industry_and_snapshot_gated_concepts(mappings):
    rows = build_ms_exposure_rows(SMIC, DAY, cutoff=CUT, pool_metrics=_pool(),
                                  ths_members=_ths(), mappings=mappings)
    ms03 = rows[2]
    assert ms03["exposure_bucket"] == "801080.SI"      # PIT SW L1 (电子)
    assert ms03["exposure_value"]["concepts"] == ["883300.TI", "883418.TI"]
    assert ms03["snapshot_effective_at"] == "2025-01-01T00:00:00"


def test_ms03_future_snapshot_omits_concepts(mappings):
    # M4: the real ths_members was fetched 2026-07 — applying it to a 2025
    # replay day would be today's members on history; concepts are OMITTED
    rows = build_ms_exposure_rows(
        SMIC, DAY, cutoff=CUT, pool_metrics=_pool(),
        ths_members=_ths(fetched="2026-07-09T13:53:14"), mappings=mappings)
    ms03 = rows[2]
    assert ms03["exposure_value"]["concepts"] == []
    assert ms03["exposure_value"]["concepts_omitted"] \
        == "no_contemporaneous_snapshot"
    assert ms03["snapshot_effective_at"] is None
    assert ms03["exposure_bucket"] == "801080.SI"      # industry still PIT-valid


def test_ms04_ms05_curated_channels(mappings):
    rows = build_ms_exposure_rows(SMIC, DAY, cutoff=CUT, pool_metrics=_pool(),
                                  ths_members=_ths(), mappings=mappings)
    ms04, ms05 = rows[3], rows[4]
    assert ms04["mapping_status"] == "mapped"
    assert ms04["exposure_value"] == ["tech_selfreliance"]   # 电子 v1 mapping
    assert ms04["mapping_sha256"] == mappings["policy"]["mapping_sha256"]
    assert ms05["mapping_status"] == "mapped"
    assert {e["channel"] for e in ms05["exposure_value"]} \
        == {"global_supply_chain", "export_demand", "fx_sensitivity"}


def test_no_exposure_industry_yields_null_value(mappings):
    # 房地产 (801180.SI) has an EMPTY shock-channel list in the v1 mapping
    import workspace.research.ai_research_dept.engine.macro_exposure as ME
    rows = build_ms_exposure_rows("600048.SH", DAY, cutoff=CUT,
                                  pool_metrics=_pool(include="600048.SH"),
                                  ths_members=_ths(), mappings=mappings)
    ms05 = rows[4]
    if ME.industry_as_of("600048.SH", DAY, "L1") == "801180.SI":
        assert ms05["mapping_status"] == "mapped_no_exposure"
        assert ms05["exposure_value"] is None and ms05["exposure_bucket"] is None


def test_unmapped_industry_fail_closed(mappings, monkeypatch):
    import workspace.research.ai_research_dept.engine.macro_exposure as ME
    monkeypatch.setattr(ME, "industry_as_of", lambda *a, **k: None)
    rows = build_ms_exposure_rows(SMIC, DAY, cutoff=CUT, pool_metrics=_pool(),
                                  ths_members=_ths(), mappings=mappings)
    for i in (2, 3, 4):
        assert rows[i]["mapping_status"] == "unmapped_industry"
        assert rows[i]["exposure_value"] is None


def test_deterministic(mappings):
    a = build_ms_exposure_rows(SMIC, DAY, cutoff=CUT, pool_metrics=_pool(),
                               ths_members=_ths(), mappings=mappings)
    b = build_ms_exposure_rows(SMIC, DAY, cutoff=CUT, pool_metrics=_pool(),
                               ths_members=_ths(), mappings=mappings)
    assert a == b
