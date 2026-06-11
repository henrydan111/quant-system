# ──────────────────────────────────────────────────────────────────────
# script_status: research_tooling
# formal_research_allowed: false
# deployment_target: knowledge_extraction_only
# requires_provider_manifest: false
# requires_preload_strict: false
# pr2_audit_class: C
# notes: |
#   Phase A — download every image from the three CICC factor handbooks (HTML in
#   Knowledge/AI量化增强/), map 图表N → caption → local file, extract body text. Read-only
#   w.r.t. all project data; writes only under Knowledge/AI量化增强/_extracted/. WeChat CDN
#   needs a UA + mp.weixin.qq.com referer; /640 thumbnails are upscaled to /0 originals for
#   legible OCR. Resumable (skips already-downloaded files).
# ──────────────────────────────────────────────────────────────────────
"""Download + index the CICC handbook images and body text (Phase A)."""
from __future__ import annotations

import html as H
import json
import re
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "Knowledge" / "AI量化增强"
OUT_DIR = SRC_DIR / "_extracted"

HANDBOOKS = {
    "fundamental": "中金量化基本面因子手册.html",
    "priceval": "中金量化多因子系列7价量因子手册.html",
    "highfreq": "中金量化多因子系列12高频因子手册.html",
}
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
REFERER = "https://mp.weixin.qq.com/"


def _body_text(raw: str) -> str:
    raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S)
    txt = H.unescape(re.sub(r"<[^>]+>", "\n", raw))
    return "\n".join(l.strip() for l in txt.splitlines() if l.strip())


def _index_one(key: str, fname: str) -> dict:
    raw = (SRC_DIR / fname).read_text(encoding="utf-8", errors="replace")
    book_dir = OUT_DIR / key
    (book_dir / "images").mkdir(parents=True, exist_ok=True)
    (book_dir / "body_text.txt").write_text(_body_text(raw), encoding="utf-8")

    imgs = [(m.start(), m.group(1)) for m in re.finditer(r'<img[^>]+(?:src|data-src)="([^"]+)"', raw)]
    caps = [(m.start(), re.sub(r"\s+", " ", m.group(0)).strip())
            for m in re.finditer(r"图表\s*\d+\s*[:：][^<]{0,70}", raw)]
    # each caption → the first image AFTER it; images before the first caption are prologue
    records = []
    for i, (cpos, ctext) in enumerate(caps):
        nxt_cap = caps[i + 1][0] if i + 1 < len(caps) else len(raw)
        url = next((u for ipos, u in imgs if cpos < ipos < nxt_cap), None)
        num_m = re.search(r"图表\s*(\d+)", ctext)
        records.append({
            "chart_no": int(num_m.group(1)) if num_m else None,
            "caption": ctext, "url": url, "local": None,
        })
    return {"key": key, "file": fname, "n_images_total": len(imgs),
            "n_captions": len(caps), "records": records}


def _download(url: str, dest: Path) -> int:
    if dest.exists() and dest.stat().st_size > 1000:
        return dest.stat().st_size
    full = re.sub(r"/640(\?|$)", r"/0\1", url)  # thumbnail → original
    for attempt in range(3):
        r = subprocess.run(["curl", "-sL", "-A", UA, "-e", REFERER, "-o", str(dest), full],
                           capture_output=True, timeout=60)
        if dest.exists() and dest.stat().st_size > 1000:
            return dest.stat().st_size
        time.sleep(1.5)
    return 0


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for key, fname in HANDBOOKS.items():
        print(f"=== {key} ({fname}) ===")
        idx = _index_one(key, fname)
        book_dir = OUT_DIR / key
        ok = miss = 0
        for rec in idx["records"]:
            if not rec["url"] or rec["chart_no"] is None:
                continue
            ext = "jpg" if "jpg" in rec["url"].lower() or "jpeg" in rec["url"].lower() else "png"
            dest = book_dir / "images" / f"chart_{rec['chart_no']:03d}.{ext}"
            size = _download(rec["url"], dest)
            if size:
                rec["local"] = str(dest.relative_to(SRC_DIR)).replace("\\", "/")
                ok += 1
            else:
                miss += 1
                print(f"  MISS chart_{rec['chart_no']}: {rec['caption'][:40]}")
        print(f"  captions {idx['n_captions']} | downloaded {ok} | missing {miss}")
        manifest[key] = idx
        (book_dir / "chart_index.json").write_text(
            json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "manifest.json").write_text(
        json.dumps({k: {"file": v["file"], "n_captions": v["n_captions"],
                        "n_downloaded": sum(1 for r in v["records"] if r["local"])}
                    for k, v in manifest.items()}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("manifest ->", OUT_DIR / "manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
