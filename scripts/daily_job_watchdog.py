# SCRIPT_STATUS: ACTIVE — calendar-unfreeze Phase 5-C: independent missed-run watchdog
"""Phase 5-C watchdog: detect a SILENTLY-MISSED-or-INCOMPLETE daily raw job.

The main QuantDailyRawUpdate task cannot report that it never launched — a sleeping/offline machine
produces no flag at all. This independent morning task (QuantDailyRawWatchdog, ~10:00 CST) RECOMPUTES
the contiguous completed-session watermark from the per-session manifests (validating the WHOLE
(provider_floor, target] interval, not just one date's heartbeat — GPT M2) and, if it does not reach
the last complete trading session (CST), writes logs/daily_job_alert_<date>.flag and exits non-zero.
Clears its own alert on success.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
LOGS_DIR = PROJECT_ROOT / "logs"
HEARTBEAT = LOGS_DIR / "daily_job_heartbeat.json"


def _cst_date() -> str:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d")
    except Exception:  # pragma: no cover
        return datetime.now().strftime("%Y%m%d")


def _alert(msg: str) -> None:
    LOGS_DIR.mkdir(exist_ok=True)
    # own the daily_job_alert (NOT qa_alert, which a manual QA run would clear — GPT minor 1)
    (LOGS_DIR / f"daily_job_alert_{_cst_date()}.flag").write_text(msg + "\n", encoding="utf-8")
    print(msg, file=sys.stderr)


def main() -> int:
    from data_infra.pipeline.update_daily_data import resolve_last_complete_session
    from data_infra.pipeline.daily_ops import (compute_contiguous_watermark, manifest_set_digest,
                                               provider_floor, ProviderFloorError, read_attempt)
    ref_dir = str(PROJECT_ROOT / "data" / "reference")
    logs = str(LOGS_DIR)
    try:  # SAME attested floor the daily job uses (GPT REWORK-5 M2.4), not a raw day.txt read
        floor = provider_floor(PROJECT_ROOT, ref_dir)
    except ProviderFloorError as exc:
        _alert(f"watchdog: provider floor attestation failed: {exc}")
        return 1
    try:
        expected = resolve_last_complete_session(ref_dir)
    except (SystemExit, Exception) as exc:  # noqa: BLE001 — a missing/corrupt calendar is alert-worthy
        _alert(f"watchdog: cannot resolve last complete session: {exc}")
        return 1

    if floor > expected:  # provider calendar ahead of reality -> poisoned/misbuilt
        _alert(f"watchdog: provider floor {floor} is AHEAD of the last complete session {expected} "
               f"(poisoned/misbuilt provider calendar)")
        return 1
    if floor == expected:  # provider current (e.g. just after a monthly publish) -> nothing to backfill
        af = LOGS_DIR / f"daily_job_alert_{_cst_date()}.flag"
        if af.exists():
            af.unlink()
        print(f"watchdog OK: provider floor {floor} == last complete session; nothing to backfill")
        return 0

    # floor < expected: the daily job MUST have backfilled (floor, expected]. Recompute the contiguous
    # watermark PURELY (a monitor must not mutate progress state — GPT M2).
    watermark = compute_contiguous_watermark(ref_dir, logs, expected, floor)
    if watermark != expected:
        _alert(f"watchdog: daily job STALE/INCOMPLETE - contiguous watermark {watermark} != expected "
               f"{expected} (missed/failed/gap in (provider_floor {floor}, {expected}])")
        return 1

    # Complete manifests are necessary but NOT sufficient: raw+manifests can succeed while run_daily_qa
    # FAILS. The success certificate must belong to the LATEST attempt (start_attempt deletes a prior
    # heartbeat), be qa_ok, and match this target/floor/manifest-set — else a stale PASS would green a
    # later FAILED run (GPT REWORK-5 M2).
    attempt = read_attempt(logs)
    if not attempt:
        _alert(f"watchdog: manifests complete to {expected} but NO attempt record — cannot confirm a run.")
        return 1
    if not HEARTBEAT.exists():
        _alert(f"watchdog: latest attempt {attempt.get('attempt_id')} has NO QA-bound heartbeat — the "
               f"daily run's QA did not pass (or it never certified). Holding alert.")
        return 1
    try:
        hb = json.loads(HEARTBEAT.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 — unreadable heartbeat is not proof of a QA pass
        _alert(f"watchdog: heartbeat unreadable ({exc}) — cannot confirm QA; holding alert.")
        return 1
    want_digest = manifest_set_digest(ref_dir, logs, expected, floor)
    if not (str(hb.get("attempt_id")) == str(attempt.get("attempt_id")) and hb.get("qa_ok") is True
            and str(hb.get("completed_session")) == expected and str(hb.get("floor")) == floor
            and str(hb.get("manifest_digest")) == want_digest):
        _alert(f"watchdog: heartbeat does not certify the latest attempt (hb_attempt="
               f"{hb.get('attempt_id')} vs {attempt.get('attempt_id')}, qa_ok={hb.get('qa_ok')} "
               f"completed={hb.get('completed_session')}/{expected} floor={hb.get('floor')}/{floor}) — "
               f"holding alert.")
        return 1
    af = LOGS_DIR / f"daily_job_alert_{_cst_date()}.flag"  # clear our own alert only on a QA-proven run
    if af.exists():
        af.unlink()
    print(f"watchdog OK: contiguous watermark {watermark} == expected {expected}, latest-attempt "
          f"QA-bound heartbeat verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
