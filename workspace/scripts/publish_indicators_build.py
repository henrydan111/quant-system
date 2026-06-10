"""Publish the staged indicators_fields_20260609 provider into live data/qlib_data.

The staged build was `--mode update --stage provider-only --datasets indicators`,
which copytree'd the FULL live provider first, then materialized the 33 new
indicator fields. So the stage = current-live (report_rc_incr_20260608 + all
datasets) + 33 new fields. publish() = atomic dir-swap with a backup.

Pre-publish completeness guard: refuse if the staged provider is missing
non-indicator datasets (canonical kline + report_rc namespaced bins), so we never
overwrite live with a partial provider.
"""
import os
import sys

sys.path.insert(0, r'E:\量化系统\src')
from data_infra.pit_backend import StagedQlibBackendBuilder  # noqa: E402

BUILD_ID = 'indicators_fields_20260609'
b = StagedQlibBackendBuilder(build_id=BUILD_ID)
prov = b.paths.provider_dir
print('staged provider_dir:', prov, '-> exists', os.path.isdir(prov))
print('target qlib_dir     :', b.paths.qlib_dir)

# completeness guard
feat = os.path.join(prov, 'features', '000001_SZ')
have = set(os.listdir(feat)) if os.path.isdir(feat) else set()
n_sym = len(os.listdir(os.path.join(prov, 'features')))
rr = [f for f in have if f.startswith('report_rc__')]
print(f'staged symbols={n_sym}  000001_SZ bins={len(have)}  report_rc bins={len(rr)}')
for needed in ['close.day.bin', 'roe_avg.day.bin']:
    assert needed in have, f'ABORT: staged provider missing {needed} — would publish a partial provider!'
assert len(rr) > 0, 'ABORT: staged provider has no report_rc__* bins — copytree incomplete!'
assert n_sym > 5000, f'ABORT: staged only {n_sym} symbols (<5000) — incomplete!'
print('completeness guard PASSED (kline + roe_avg + report_rc all present, full universe)')

b.publish(calendar_policy_id='frozen_20260227_system_build')
print('PUBLISHED OK')

import json
m = json.load(open(os.path.join(b.paths.qlib_dir, 'metadata', 'provider_build.json'), encoding='utf-8'))
print('new provider_build_id:', m['provider_build_id'])
print('calendar:', m['provider']['calendar_start_date'], '->', m['provider']['calendar_end_date'])
print('backup kept at:', f"{b.paths.qlib_dir}.bak_{BUILD_ID}")
