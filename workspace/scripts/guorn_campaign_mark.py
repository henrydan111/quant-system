"""Mark a factor's status in the 果仁 web-validation campaign log (then refresh the MD).
Usage: guorn_campaign_mark.py "<indicator>" <status> "<verdict>" "<export_file>" <date> ["<local_expr>"] ["<note>"]
status ∈ pending|done|diverged|blocked|skipped. Re-runs build_guorn_validation_campaign.py to refresh the MD."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / "workspace" / "research" / "idea_sourcing" / "guorn" / "guorn_web_validation_campaign.json"


def main():
    ind, status = sys.argv[1], sys.argv[2]
    verdict = sys.argv[3] if len(sys.argv) > 3 else None
    export = sys.argv[4] if len(sys.argv) > 4 else None
    date = sys.argv[5] if len(sys.argv) > 5 else None
    local_expr = sys.argv[6] if len(sys.argv) > 6 else None
    note = sys.argv[7] if len(sys.argv) > 7 else None

    d = json.loads(LOG.read_text(encoding="utf-8"))
    hit = next((f for f in d["factors"] if f["guorn_indicator"] == ind), None)
    if hit is None:
        raise SystemExit(f"factor {ind!r} not in campaign log")
    hit["status"] = status
    if verdict is not None: hit["verdict"] = verdict
    if export is not None: hit["export_file"] = export
    if date is not None: hit["selection_date"] = date
    if local_expr is not None: hit["local_expr"] = local_expr
    if note is not None: hit["note"] = note
    LOG.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "workspace" / "scripts" / "build_guorn_validation_campaign.py")], check=True)
    print(f"[mark] {ind} -> {status}")


if __name__ == "__main__":
    main()
