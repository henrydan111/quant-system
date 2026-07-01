"""Recover the partial publish: live qlib_data was moved to backup, but the
staged->live swap failed (WinError 5 lock). Try to COMPLETE the publish
(staged -> qlib_data); if the lock persists, RESTORE the old provider from
backup. Never delete the backup.
"""
import os
import sys
import json
import time

QLIB = r'E:\量化系统\data\qlib_data'
BAK = r'E:\量化系统\data\qlib_data.bak_indicators_fields_20260609'
STAGED = r'E:\量化系统\data\qlib_builds\indicators_fields_20260609\provider'

if os.path.isdir(QLIB):
    print('qlib_data already exists — nothing to recover. Inspect manually.')
    sys.exit(0)

assert os.path.isdir(BAK), 'backup missing — CRITICAL, do not proceed'
assert os.path.isdir(STAGED), 'staged provider missing — CRITICAL'

done = None
for attempt in range(4):
    try:
        os.replace(STAGED, QLIB)   # complete the publish (new provider live)
        done = 'A_completed_publish'
        break
    except Exception as e:
        print(f'  complete-publish attempt {attempt + 1}/4 failed: {e}')
        time.sleep(5)

if done is None:
    # restore old provider; backup -> live (backup name consumed, but data safe as live)
    os.replace(BAK, QLIB)
    done = 'B_restored_old_from_backup'

print('RESULT:', done)

if done.startswith('A'):
    # re-emit the attestation with the new build id (publish() failed before this step)
    sys.path.insert(0, r'E:\量化系统\src')
    from data_infra.pit_backend import StagedQlibBackendBuilder
    b = StagedQlibBackendBuilder(build_id='indicators_fields_20260609')
    b._emit_provider_manifest_at_publish(calendar_policy_id='frozen_20260227_system_build')
    print('provider_build.json re-emitted')

m = json.load(open(os.path.join(QLIB, 'metadata', 'provider_build.json'), encoding='utf-8'))
print('LIVE provider_build_id:', m['provider_build_id'])
print('LIVE symbols:', len(os.listdir(os.path.join(QLIB, 'features'))))
print('calendar end:', m['provider'].get('calendar_end_date'))
