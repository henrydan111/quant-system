"""Parse the scraped guorn slct strategy markdown into structured JSON.

One-off helper for the guorn idea-sourcing pull. Reads the verified markdown
(name + fenced strategy definition per strategy) and emits a list of
{"name", "definition"} records for programmatic consumption by the local system.
"""
import re
import json
from pathlib import Path

BASE = Path(r"E:\量化系统\workspace\research\idea_sourcing\guorn")
MD = BASE / "guorn_slct_strategies.md"
OUT = BASE / "guorn_slct_strategies.json"

FENCE = chr(96) * 3  # ```

text = MD.read_text(encoding="utf-8")
blocks = re.split(r"\n## \d+\.\s", text)
items = []
for blk in blocks[1:]:
    name = blk.split("\n", 1)[0].strip()
    m = re.search(re.escape(FENCE) + r"\n(.*?)\n" + re.escape(FENCE), blk, re.S)
    definition = m.group(1).strip() if m else ""
    items.append({"name": name, "definition": definition})

OUT.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

empties = [x["name"] for x in items if len(x["definition"]) < 80]
print(f"parsed={len(items)} empties={len(empties)}")
if empties:
    print("EMPTY/SHORT:", empties)
print("first=", items[0]["name"])
print("last=", items[-1]["name"])
