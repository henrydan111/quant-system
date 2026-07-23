# SCRIPT_STATUS: ACTIVE — 读档验收·机械复核(独立重实现,不 import engine 校验器)
"""对一个链版本某决策日的全部档案做三类机械复核,作为验收辅助材料:

  A. 证据接地重验:每个席位 record 里幸存的 evidence_span 是否真的逐字对应
     其席位卡片的某条 `- [ID]` 行(独立于 validators.enforce_v2_evidence 的
     第二套实现——若这里报违规而围栏没报,说明围栏有洞,是重大发现);
  B. 空头引文接地:每条 refutation.counter_quote 对应全卡片文本的某条行;
  C. 裁判算术:composite ?= Σ COMPOSITE_W[seat]×finals[seat](0.4/0.3/0.3),
     composite_adj 同式于 adj_finals;adj_final ≤ final 单调性。

只读;发现全部列名输出。用法:
  venv/Scripts/python.exe workspace/research/ai_research_dept/acceptance_mechanical_check.py \
      [--version chain_v3.0] [--day 20250127]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CHAIN_ROOT = (PROJECT_ROOT / "workspace" / "outputs" / "ai_research_dept"
              / "analyst_chain")
SEATS = ("fund", "tech", "news")
SEAT_CARD = {"fund": "fund_card", "tech": "pv_card", "news": "news_card"}
COMPOSITE_W = {"fund": 0.4, "tech": 0.3, "news": 0.3}   # 与 cards.py 对照过
_ID = re.compile(r"\[([A-Z]{1,4}\d{0,3})\]")
_WS = re.compile(r"\s+")


def _norm(s: str) -> str:
    return _WS.sub(" ", str(s)).strip()


def card_lines(text: str) -> dict[str, str]:
    out = {}
    for line in str(text).splitlines():
        t = line.strip()
        if t.startswith("- ["):
            m = _ID.search(t[:14])
            if m:
                out[m.group(1)] = _norm(t)
    return out


def span_grounded(span: str, lmap: dict[str, str]) -> bool:
    s = _norm(span)
    m = _ID.search(s)
    if not m or m.group(1) not in lmap:
        return False
    target = lmap[m.group(1)]
    return s == target or s == target[2:].strip() or f"- {s}" == target


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="chain_v3.0")
    ap.add_argument("--day", default="20250127")
    args = ap.parse_args(argv if argv is not None else [])
    day_dir = CHAIN_ROOT / args.version / args.day
    files = sorted(day_dir.glob("*.json"))
    if not files:
        print(f"no archives under {day_dir}", file=sys.stderr)
        return 1

    n_span = n_quote = 0
    bad_span, bad_quote, bad_math, bad_mono = [], [], [], []
    for p in files:
        a = json.loads(p.read_text(encoding="utf-8"))
        code = a.get("ts_code", p.stem)
        cards = a.get("cards", {})
        all_lines = card_lines(a.get("market_context", ""))   # M 域=空头合法证据域
        for s in SEATS:
            all_lines.update(card_lines(cards.get(SEAT_CARD[s], "")))
        # A. 席位证据接地(按席位自己的卡)
        for s in SEATS:
            lmap = card_lines(cards.get(SEAT_CARD[s], ""))
            rec = a.get("records", {}).get(s) or {}
            for entry in (rec.get("factor_scores") or []) + (rec.get("penalty_scores") or []):
                for sp in (entry.get("evidence_spans") or []):
                    n_span += 1
                    if not span_grounded(sp, lmap):
                        bad_span.append((code, s, entry.get("name"), str(sp)[:60]))
        # B. 空头引文接地(全卡)
        for r in (a.get("bear", {}).get("refutations") or []):
            n_quote += 1
            if not span_grounded(r.get("counter_quote", ""), all_lines):
                bad_quote.append((code, r.get("target_seat"),
                                  str(r.get("counter_quote"))[:60]))
        # C. 裁判算术
        j = a.get("judge", {})
        for comp_key, fin_key in (("composite", "finals"),
                                  ("composite_adj", "adj_finals")):
            fins = j.get(fin_key) or {}
            got = j.get(comp_key)
            if got is None or any(fins.get(s) is None for s in SEATS):
                bad_math.append((code, comp_key, "missing"))
                continue
            want = sum(COMPOSITE_W[s] * float(fins[s]) for s in SEATS)
            # 链存 1 位小数:精确按 round(...,1) 语义对照。GPT 复审修正:去掉
            # 0.051 容差兜底——它会放过边界上错误的相邻 0.1 分档。
            if float(got) != round(want, 1):
                bad_math.append((code, comp_key,
                                 f"got {got} want {round(want, 2)}"))
        for s in SEATS:
            f0 = (j.get("finals") or {}).get(s)
            f1 = (j.get("adj_finals") or {}).get(s)
            if f0 is not None and f1 is not None and float(f1) > float(f0) + 1e-9:
                bad_mono.append((code, s, f"adj {f1} > final {f0}"))

    print(f"archives={len(files)}  spans_checked={n_span}  quotes_checked={n_quote}")
    print(f"A. 席位证据接地违规: {len(bad_span)}")
    for x in bad_span[:10]:
        print("   ", x)
    print(f"B. 空头引文接地违规: {len(bad_quote)}")
    for x in bad_quote[:10]:
        print("   ", x)
    print(f"C. 裁判算术不符: {len(bad_math)} | adj>final 单调性违规: {len(bad_mono)}")
    for x in (bad_math + bad_mono)[:10]:
        print("   ", x)
    ok = not (bad_span or bad_quote or bad_math or bad_mono)
    print("VERDICT:", "ALL CLEAN" if ok else "FINDINGS PRESENT")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
