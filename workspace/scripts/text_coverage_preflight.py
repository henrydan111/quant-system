# SCRIPT_STATUS: ACTIVE — B2 daily text-coverage preflight (read-only alerting)
"""Rehearse the forward runner's TEXT gates daily: "if today were the
activation day, would the cycle be refused for text reasons?"

Why: the FORWARD_PREREG coverage-history gate (R3-Blocker-3) refuses a cycle
whose 30-day dossier window has ANY (source, day) gap. Without this preflight
a gap is discovered only at decision time (e.g. 08-04), when it is too late
to re-pull history. This script runs after every daily pull and raises the
alarm the DAY the gap appears.

Contract:
  - READ-ONLY preview. The runner's own gates remain the sole authority; this
    script REUSES the runner's gate functions verbatim (check_pull_manifest +
    check_text_coverage_history imported from run_forward_cycle.py) so the
    preview can never drift from the real gate. It never touches
    workspace/outputs/mvp_forward/, config, or any frozen prereg surface.
  - Alert flag mirrors run_daily_qa semantics: on failure writes
    logs/text_coverage_alert_<YYYYMMDD>.flag (JSON body with reasons); a
    recovered same-day run removes it. Exit 1 on any problem, else 0.
  - Also writes logs/text_pull/coverage_preflight_latest.json (status file;
    its name does not match the gate's pull_manifest_*.json glob).
  - Scope: latest-pull freshness/cleanliness + coverage history only. The
    runner's other text checks (store files, migration manifest) are
    decision-time concerns and are not rehearsed here.

Usage:
  venv/Scripts/python.exe workspace/scripts/text_coverage_preflight.py
  (chained automatically by a full text_daily_pull.py script run)
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

RUNNER_PATH = (PROJECT_ROOT / "workspace" / "research" / "mvp_pool_book"
               / "run_forward_cycle.py")
CONFIG_PATH = PROJECT_ROOT / "config" / "ai_layer" / "rerank_v2.yaml"
LOG_DIR = PROJECT_ROOT / "logs"
PULL_MANIFEST_DIR = LOG_DIR / "text_pull"
CN_TZ = "Asia/Shanghai"
STATUS_NAME = "coverage_preflight_latest.json"


def _load_runner():
    """Import the forward runner MODULE (constants + pure gate functions only
    at module level — main() is argparse-guarded)."""
    spec = importlib.util.spec_from_file_location(
        "run_forward_cycle_for_preflight", RUNNER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-dir", default=str(PULL_MANIFEST_DIR),
                        help="pull-manifest directory (test override)")
    parser.add_argument("--log-dir", default=str(LOG_DIR),
                        help="alert-flag directory (test override)")
    parser.add_argument("--now", default=None,
                        help="ISO timestamp to rehearse as decision time "
                             "(test override; default: now, CN wall time)")
    args = parser.parse_args(argv if argv is not None else [])

    manifest_dir = Path(args.manifest_dir)
    log_dir = Path(args.log_dir)
    now = (pd.Timestamp(args.now) if args.now
           else pd.Timestamp.now(tz=CN_TZ))
    if now.tzinfo is None:
        now = now.tz_localize(CN_TZ)

    # GPT 复审修正(B2 告警兜底):损坏/半写入的清单 JSON、字段格式异常等
    # 非预期异常同样必须记为预检失败并写 flag——否则脚本异常退出时当日告警
    # 静默失效(日拉刻意隔离预检退出码,不会替它报警)。
    problems: list[dict] = []
    required_sources: list[str] = []
    lookback_days: int | None = None
    coverage_window = None
    rfc = None
    try:
        cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        required_sources = list(cfg["dossier"]["sources"])
        lookback_days = int(cfg["dossier"]["lookback_days"])
        rfc = _load_runner()
    except Exception as e:  # noqa: BLE001 — fail-closed alerting
        problems.append({"check": "preflight_setup",
                         "error": f"unexpected_error {type(e).__name__}: {e}"})

    if rfc is not None:
        latest = manifest_dir / "pull_manifest_latest.json"
        if not latest.exists():
            problems.append({"check": "latest_pull",
                             "error": f"{latest} missing — text_daily_pull has "
                                      f"never completed a full run"})
        else:
            try:
                rfc.check_pull_manifest(
                    json.loads(latest.read_text(encoding="utf-8")), now,
                    required_sources)
            except rfc.ForwardGateError as e:
                problems.append({"check": "latest_pull", "error": str(e)})
            except Exception as e:  # noqa: BLE001 — 损坏 latest 也要当日报警
                problems.append({"check": "latest_pull",
                                 "error": f"unexpected_error "
                                          f"{type(e).__name__}: {e}"})
        try:
            record = rfc.check_text_coverage_history(
                manifest_dir, decision_time=now,
                lookback_days=lookback_days, required_sources=required_sources)
            coverage_window = {"start": record["window_start"],
                               "end": record["window_end"]}
        except rfc.ForwardGateError as e:
            problems.append({"check": "coverage_history", "error": str(e)})
        except Exception as e:  # noqa: BLE001 — 损坏历史清单也要当日报警
            problems.append({"check": "coverage_history",
                             "error": f"unexpected_error "
                                      f"{type(e).__name__}: {e}"})

    status = {
        "checked_at": now.isoformat(),
        "rehearsed_as_decision_time": True,
        "required_sources": required_sources,
        "lookback_days": lookback_days,
        "coverage_window": coverage_window,
        "ok": not problems,
        "problems": problems,
    }
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / STATUS_NAME).write_text(
        json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")

    flag = log_dir / f"text_coverage_alert_{now.tz_convert(CN_TZ).strftime('%Y%m%d')}.flag"
    if problems:
        log_dir.mkdir(parents=True, exist_ok=True)
        flag.write_text(json.dumps(status, indent=2, ensure_ascii=False),
                        encoding="utf-8")
        print(f"TEXT COVERAGE PREFLIGHT: FAIL — {len(problems)} problem(s); "
              f"flag -> {flag}", file=sys.stderr)
        for p in problems:
            print(f"  [{p['check']}] {p['error'][:400]}", file=sys.stderr)
        return 1
    flag.unlink(missing_ok=True)          # recovered same-day run clears it
    print(f"TEXT COVERAGE PREFLIGHT: ok ({coverage_window['start']}"
          f"..{coverage_window['end']}, {len(required_sources)} sources)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
