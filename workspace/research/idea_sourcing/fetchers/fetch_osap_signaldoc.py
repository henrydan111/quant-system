# ──────────────────────────────────────────────────────────────────────
# SCRIPT_STATUS header block.
# script_status: class_d_research_tooling
# formal_research_allowed: false
# touches_formal_data_plane: false
# pr2_audit_class: D
# notes: |
#   Idea-sourcing fetcher (English-academic slice). Pulls the Open Source
#   Asset Pricing (Chen & Zimmermann) SignalDoc catalog — ~210 published
#   cross-sectional predictors, each mapped to its source paper, predicted
#   sign, economic category and sample window — into a local Parquet store.
#
#   Deliberately does NOT install the `openassetpricing` pip package: that
#   package's install_requires drags in `polars` + `wrds` (a paid Wharton
#   subscription, needed only for the US/CRSP signal VALUES which are
#   permno-keyed and unusable in this A-share system). For idea sourcing we
#   want the CATALOG, which is a single public Google-Drive CSV. We replicate
#   only that path with the existing requests/pandas stack — zero new deps.
#
#   This is a HYPOTHESIS source, never evidence: a predictor listed here is a
#   US-market published anomaly. Porting any of them to A-shares is a fresh
#   hypothesis that still runs the full IS-only -> sealed-OOS lifecycle.
#   Writes ONLY under workspace/research/idea_sourcing/store/.
# ──────────────────────────────────────────────────────────────────────
"""
OSAP SignalDoc fetcher — lands the published-predictor catalog into a local
Parquet store for research-idea triage.

Mechanism (reverse-engineered from mk0417/open-asset-pricing-download, the
official `openassetpricing` package, GPLv2):
  1. The data release is a public Google-Drive FOLDER (per-release id below).
  2. The folder HTML embeds a window['_DRIVE_ivd'] JS array of
     (file_id, name, mime) entries; we extract the id of 'SignalDoc.csv'.
  3. We download that CSV via Drive's uc?export=download endpoint (with the
     virus-scan confirm-token fallback) and parse it with pandas.

Store:  workspace/research/idea_sourcing/store/osap_signaldoc.parquet

Usage
-----
  venv/Scripts/python.exe workspace/research/idea_sourcing/fetchers/fetch_osap_signaldoc.py
  ...fetch_osap_signaldoc.py --release 202510 --dry-run
  ...fetch_osap_signaldoc.py --list            # just list the folder's files
"""
from __future__ import annotations

import argparse
import itertools
import json
import logging
import re
import sys
import warnings
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[4]
STORE_DIR = PROJECT_ROOT / "workspace" / "research" / "idea_sourcing" / "store"
DEFAULT_STORE = STORE_DIR / "osap_signaldoc.parquet"

# Release -> public Drive folder id (from openassetpricing/urls.py, GPLv2).
RELEASE_FOLDERS = {
    "202510": "1qQDuTsnyvWfEJR6nPBQZ8xxlq6bkLG_y",  # v2.00  (2025.10) — latest
    "202410": "1SSoHGbwgyhRwUCzLE0YWvUlS0DjLCd4k",  # v1.41  (2024.10)
    "202408": "1-PqsR-tOjv3-U9DRHw85X-VznYlu-Sfc",  # v1.40  (2024.08)
    "2023":   "1EP6oEabyZRamveGNyzYU0u6qJ-N43Qfq",  # v1.30  (2023.08)
    "2022":   "1O18scg9iBTiBaDiQFhoGxdn4FdsbMqGo",  # v1.20  (2022.03)
}
TARGET_FILE = "SignalDoc.csv"

BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("fetch_osap_signaldoc")


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": BROWSER_UA})
    return s


def _list_folder_files(sess: requests.Session, folder_id: str) -> list[tuple[str, str, str]]:
    """Return [(file_id, name, mime), ...] for a public Drive folder's top level."""
    url = f"https://drive.google.com/drive/folders/{folder_id}?hl=en"
    res = sess.get(url, timeout=40)
    res.raise_for_status()
    html = res.text
    # Find the <script> block carrying window['_DRIVE_ivd'] (faithful to gdrive_parse).
    block = None
    for script in re.findall(r"<script[^>]*>(.*?)</script>", html, flags=re.DOTALL):
        if "_DRIVE_ivd" in script:
            block = script
            break
    if block is None:
        raise RuntimeError(
            "Could not find _DRIVE_ivd in folder HTML — the folder may be private, "
            "or Drive served a login/consent page. Folder id=%s" % folder_id)
    # The 2nd single-quoted JS string in that block is the encoded array.
    it = re.compile(r"'((?:[^'\\]|\\.)*)'").finditer(block)
    encoded = next(itertools.islice(it, 1, None)).group(1)
    with warnings.catch_warnings():  # the JS array carries '\/' etc. — benign
        warnings.simplefilter("ignore", DeprecationWarning)
        decoded = encoded.encode("utf-8").decode("unicode_escape")
    arr = json.loads(decoded)
    entries = arr[0] or []
    out = []
    for e in entries:
        try:
            fid = e[0]
            name = e[2].encode("raw_unicode_escape").decode("utf-8")
            mime = e[3]
            out.append((fid, name, mime))
        except Exception:  # noqa: BLE001 - skip malformed entries defensively
            continue
    return out


def _download_drive_file(sess: requests.Session, file_id: str) -> bytes:
    """Download a public Drive file by id, handling the virus-scan confirm page."""
    base = "https://drive.google.com/uc"
    r = sess.get(base, params={"id": file_id, "export": "download"}, stream=True, timeout=60)
    ctype = r.headers.get("Content-Type", "")
    if "text/html" not in ctype.lower():
        return r.content
    # Confirm page: try the modern usercontent endpoint with a forced confirm token first.
    r2 = sess.get("https://drive.usercontent.google.com/download",
                  params={"id": file_id, "export": "download", "confirm": "t"},
                  stream=True, timeout=60)
    if "text/html" not in r2.headers.get("Content-Type", "").lower():
        return r2.content
    # Last resort: parse the confirm form action + hidden inputs out of the HTML.
    html = r2.text
    m = re.search(r'action="([^"]+)"', html)
    if not m:
        raise RuntimeError("Drive returned a confirm page we could not parse for id=%s" % file_id)
    action = m.group(1).replace("&amp;", "&")
    params = dict(re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)"', html))
    r3 = sess.get(action, params=params, stream=True, timeout=60)
    if "text/html" in r3.headers.get("Content-Type", "").lower():
        raise RuntimeError("Drive still served HTML after confirm for id=%s" % file_id)
    return r3.content


def _parse_signaldoc(raw: bytes):
    import pandas as pd
    for enc in ("utf-8", "latin-1"):
        try:
            return pd.read_csv(BytesIO(raw), encoding=enc)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(BytesIO(raw), encoding="utf-8", encoding_errors="replace")


def _summarize(df, release: str) -> None:
    import pandas as pd  # noqa: F401
    cols = list(df.columns)
    print(f"\nSignalDoc release {release}: {len(df)} rows x {len(cols)} cols")
    print("columns:", cols)
    # Surface the idea-sourcing essentials, tolerant to column-name drift across releases.
    def pick(*cands):
        for c in cands:
            if c in df.columns:
                return c
        return None
    cat_col = pick("Cat.Signal", "Cat_Signal", "Cat.Economic", "Cat.Form")
    if cat_col:
        print(f"\n'{cat_col}' breakdown:")
        print(df[cat_col].value_counts(dropna=False).head(12).to_string())
    name_c = pick("Acronym", "signalname", "Signal")
    auth_c = pick("Authors", "Author")
    year_c = pick("Year")
    jour_c = pick("Journal")
    sign_c = pick("Sign")
    desc_c = pick("LongDescription", "Detailed Definition", "Description")
    if name_c:
        print("\nSample predictors (acronym | sign | paper | description):")
        show = df.head(8)
        for _, r in show.iterrows():
            nm = r.get(name_c, "")
            sg = r.get(sign_c, "") if sign_c else ""
            paper = " ".join(str(r.get(c, "")) for c in (auth_c, year_c, jour_c) if c)
            desc = str(r.get(desc_c, "")) if desc_c else ""
            print(f"  {str(nm):<16} sign={str(sg):>3}  {paper[:55]:<55}  {desc[:60]}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch the OSAP SignalDoc predictor catalog.")
    ap.add_argument("--release", default="202510", choices=list(RELEASE_FOLDERS),
                    help="OSAP data release (default 202510 = latest).")
    ap.add_argument("--out", default=str(DEFAULT_STORE), help="Parquet store path.")
    ap.add_argument("--list", action="store_true", help="Just list the release folder's files and exit.")
    ap.add_argument("--dry-run", action="store_true", help="Fetch + summarize but do not write the store.")
    args = ap.parse_args()

    folder_id = RELEASE_FOLDERS[args.release]
    sess = _session()
    log.info("resolving release %s (folder %s) ...", args.release, folder_id)
    files = _list_folder_files(sess, folder_id)
    log.info("folder lists %d files", len(files))

    if args.list:
        for fid, name, mime in files:
            print(f"  {name:<48} {mime:<45} {fid}")
        return 0

    match = next((f for f in files if f[1] == TARGET_FILE), None)
    if match is None:
        log.error("'%s' not found in release %s. Files seen: %s",
                  TARGET_FILE, args.release, [f[1] for f in files][:20])
        return 1
    file_id = match[0]
    log.info("downloading %s (id=%s) ...", TARGET_FILE, file_id)
    raw = _download_drive_file(sess, file_id)
    log.info("downloaded %d bytes", len(raw))

    df = _parse_signaldoc(raw)
    df["osap_release"] = args.release
    df["fetched_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _summarize(df, args.release)

    if args.dry_run:
        log.info("DRY RUN — store not written.")
        return 0

    out_path = Path(args.out)
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    log.info("wrote %s (%d rows)", out_path, len(df))
    return 0


if __name__ == "__main__":
    sys.exit(main())
