"""Emit legible native-resolution band crops of CICC handbook charts for re-verification.

Usage: cicc_verify_crops.py <book> <chart_no> [<chart_no> ...]
  book in {fundamental, priceval, highfreq}

For each chart: if width<=1500 and height<=900 -> single native crop;
else split into vertical halves (wide) and/or horizontal bands (tall),
each kept under the harness no-downscale limit. No resize -> every original
pixel preserved (the reliable method). Outputs to _verify/<book>/.
"""
import json
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[2] / "Knowledge" / "AI量化增强"
MAXW = 1500  # keep crops under harness downscale threshold

def chart_map(book):
    ci = json.load(open(ROOT / "_extracted" / book / "chart_index.json", encoding="utf-8"))["records"]
    return {r["chart_no"]: ROOT / r["local"] for r in ci}

def emit(book, nos):
    m = chart_map(book)
    outdir = ROOT / "_verify" / book
    outdir.mkdir(parents=True, exist_ok=True)
    written = []
    for n in nos:
        n = int(n)
        p = m.get(n)
        if p is None or not p.exists():
            print(f"图表{n}: MISSING"); continue
        im = Image.open(p).convert("RGB")
        w, h = im.size
        # vertical splits if wide
        xcuts = [(0, w)]
        if w > MAXW:
            half = w // 2
            ov = 60  # overlap so a column straddling the cut is fully visible somewhere
            xcuts = [(0, half + ov), (half - ov, w)]
        # horizontal bands if tall (keep header row in each band via overlap)
        MAXH = 520
        ycuts = [(0, h)]
        if h > MAXH:
            nbands = (h + MAXH - 1) // MAXH
            step = h // nbands
            hov = 40
            ycuts = []
            for b in range(nbands):
                y0 = max(0, b * step - (hov if b else 0))
                y1 = h if b == nbands - 1 else (b + 1) * step + hov
                ycuts.append((y0, y1))
        for xi, (x0, x1) in enumerate(xcuts):
            for yi, (y0, y1) in enumerate(ycuts):
                crop = im.crop((x0, y0, x1, y1))
                tag = f"chart{n}"
                if len(xcuts) > 1:
                    tag += f"_x{xi}"
                if len(ycuts) > 1:
                    tag += f"_y{yi}"
                fp = outdir / f"{tag}.png"
                crop.save(fp)
                written.append((n, fp, crop.size))
                print(f"图表{n}: {fp.name}  {crop.size}")
    return written

if __name__ == "__main__":
    book = sys.argv[1]
    nos = sys.argv[2:]
    emit(book, nos)
