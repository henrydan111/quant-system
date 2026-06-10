"""One-click manual backfill of missing Sonnet translations.

Run INSIDE a normal Claude Code session (where auth just works — no API key, no
stored token, no unattended agent). Deterministic Python does the two safe
halves; the description text comes from the session's model in between:

  1) detect → finds current factors/categories/strategies/research-threads that
     are missing from translations.json, writes `_backfill_input.json`.
  2) <the session translates _backfill_input.json → _backfill_output.json>
  3) merge  → validates the output and merges it into translations.json.

The easiest trigger is the `/backfill-translations` slash command, which runs
all three steps for you. Or run the two commands manually and let Claude do the
middle step.

    venv/Scripts/python.exe src/dashboard/backfill_translations.py detect
    venv/Scripts/python.exe src/dashboard/backfill_translations.py merge
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRANS = ROOT / "src" / "dashboard" / "translations.json"
INPUT = ROOT / "workspace" / "outputs" / "dashboard" / "_backfill_input.json"
OUTPUT = ROOT / "workspace" / "outputs" / "dashboard" / "_backfill_output.json"
SECTIONS = ("factors", "categories", "strategies", "research_threads")
# arXiv knowledge-framework sections (dimension labels / research-direction
# one-liners / ranked-paper Chinese glosses). Sonnet-translated, same flow.
KNOWLEDGE_SECTIONS = ("knowledge_dims", "knowledge_directions", "knowledge_papers")
ALL_SECTIONS = SECTIONS + KNOWLEDGE_SECTIONS
_IDEA = ROOT / "workspace" / "research" / "idea_sourcing"
PAPER_GLOSS_TOPN = 40


def _load_taxonomy_dims():
    """DIMENSION_TABLE from the idea-sourcing taxonomy (file-path import, fail-soft)."""
    try:
        import importlib.util
        import sys as _sys
        p = _IDEA / "knowledge" / "taxonomy.py"
        if not p.exists():
            return []
        spec = importlib.util.spec_from_file_location("_idea_tax_bf", p)
        mod = importlib.util.module_from_spec(spec)
        _sys.modules["_idea_tax_bf"] = mod
        spec.loader.exec_module(mod)
        return list(getattr(mod, "DIMENSION_TABLE", []))
    except Exception:
        return []


def _load(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def detect() -> int:
    import pandas as pd
    import yaml

    trans = _load(TRANS, {}) or {}
    have = {s: set((trans.get(s) or {}).keys()) for s in ALL_SECTIONS}

    m = pd.read_parquet(ROOT / "data" / "factor_registry" / "factor_master.parquet")
    cur = m[m["is_current"] == True]  # noqa: E712
    missing_factors = []
    for _, r in cur.iterrows():
        fid = r.get("factor_id")
        if fid and fid not in have["factors"]:
            zh = r.get("display_name_zh")
            missing_factors.append({
                "factor_id": fid,
                "category": str(r.get("category") or ""),
                "expression": str(r.get("expression") or "")[:240],
                "display_name_zh": "" if (zh is None or (isinstance(zh, float))) else str(zh),
            })
    cats = sorted(set(str(c) for c in cur["category"].dropna().unique()) - have["categories"])

    board = yaml.safe_load((ROOT / "workspace" / "configs" / "dashboard_board.yaml").read_text(encoding="utf-8")) or {}
    strat = [{"name": s.get("name"), "note_cn": s.get("note", "")}
             for s in (board.get("strategies") or [])
             if s.get("name") and s.get("name") not in have["strategies"]]

    threads = []
    rr = ROOT / "workspace" / "research"
    if rr.exists():
        for d in sorted(rr.iterdir()):
            if d.is_dir() and d.name not in have["research_threads"]:
                title = ""
                fnd = sorted(d.glob("FINDINGS*.md"))
                if fnd:
                    for line in fnd[0].read_text(encoding="utf-8", errors="replace").splitlines():
                        if line.strip().startswith("#"):
                            title = line.strip("# ").strip()
                            break
                threads.append({"name": d.name, "findings_title": title[:120]})

    # --- arXiv knowledge framework: dimensions / directions / ranked papers ---
    kdims = [{"key": d.get("key"), "en_label": d.get("label"), "status": d.get("status"), "note": d.get("note", "")}
             for d in _load_taxonomy_dims() if d.get("key") and d.get("key") not in have["knowledge_dims"]]
    kdirs = []
    ry = yaml.safe_load((_IDEA / "knowledge" / "research_directions.yaml").read_text(encoding="utf-8")) \
        if (_IDEA / "knowledge" / "research_directions.yaml").exists() else {}
    for d in (ry or {}).get("directions", []):
        did = d.get("id")
        if did and did not in have["knowledge_directions"]:
            kdirs.append({"id": did, "title": d.get("title", ""), "en": d.get("en", ""),
                          "dimension": d.get("dimension", "")})
    kpapers = []
    rp = _IDEA / "knowledge" / "ranked_papers.parquet"
    if rp.exists():
        for _, r in pd.read_parquet(rp).head(PAPER_GLOSS_TOPN).iterrows():
            aid = str(r.get("arxiv_id") or "")
            if aid and aid not in have["knowledge_papers"]:
                kpapers.append({"id": aid, "title": str(r.get("title") or ""),
                                "dim": str(r.get("primary_dim") or ""),
                                "abstract": str(r.get("abstract") or "")[:280]})

    payload = {"factors": missing_factors, "categories": cats, "strategies": strat, "research_threads": threads,
               "knowledge_dims": kdims, "knowledge_directions": kdirs, "knowledge_papers": kpapers}
    total = sum(len(payload[s]) for s in ALL_SECTIONS)
    if total == 0:
        print("✓ translations.json 已覆盖全部当前因子/类目/策略/研究线程/知识框架，无需补译。")
        # clean any stale scratch files
        for p in (INPUT, OUTPUT):
            try:
                p.unlink()
            except Exception:
                pass
        return 0

    INPUT.parent.mkdir(parents=True, exist_ok=True)
    INPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"发现 {total} 项待补译 —— 因子 {len(missing_factors)} / 类目 {len(cats)} / 策略 {len(strat)} / 线程 {len(threads)} "
          f"/ 知识维度 {len(kdims)} / 研究方向 {len(kdirs)} / 论文 {len(kpapers)}")
    print(f"待译清单已写入: {INPUT.relative_to(ROOT).as_posix()}")
    print("下一步（在当前 Claude 会话里，由会话的 Sonnet 完成）：")
    print("  读取该文件，为每项写一句话中英文（EN ~8-18 词 / CN ~12-28 字，客观描述，勿编造业绩）。")
    print("  factors/categories/strategies/research_threads/knowledge_dims/knowledge_directions: {en,cn} 都要；")
    print("  knowledge_papers: 只需 cn（论文标题保留英文，cn 是一句话中文导读）。")
    print(f"  写到 {OUTPUT.relative_to(ROOT).as_posix()}，schema:")
    print('  {"factors":{"<id>":{"en","cn"}}, ..., "knowledge_dims":{"<key>":{"en","cn"}},'
          ' "knowledge_directions":{"<id>":{"en","cn"}}, "knowledge_papers":{"<arxiv_id>":{"cn":".."}}}')
    print("  然后运行: venv/Scripts/python.exe src/dashboard/backfill_translations.py merge")
    return 0


def merge() -> int:
    out = _load(OUTPUT, None)
    if not isinstance(out, dict):
        print(f"找不到/无法解析 {OUTPUT.relative_to(ROOT).as_posix()} —— 先让 Claude 会话生成它（见 detect 的提示）。")
        return 1
    trans = _load(TRANS, {}) or {}
    added = {}
    for sec in ALL_SECTIONS:
        trans.setdefault(sec, {})
        n = 0
        cn_only = sec == "knowledge_papers"   # papers keep the EN title; cn gloss only
        for k, v in (out.get(sec) or {}).items():
            if not isinstance(v, dict) or not v.get("cn"):
                continue
            if cn_only:
                trans[sec][k] = {"cn": v["cn"]}
            elif v.get("en"):
                trans[sec][k] = {"en": v["en"], "cn": v["cn"]}
            else:
                continue
            n += 1
        added[sec] = n
    trans.setdefault("_meta", {})
    trans["_meta"]["factor_count"] = len(trans.get("factors", {}))
    TRANS.write_text(json.dumps(trans, ensure_ascii=False, indent=1), encoding="utf-8")
    print("已合并进 translations.json:", ", ".join(f"{k} +{v}" for k, v in added.items() if v) or "（无有效条目）")
    for p in (INPUT, OUTPUT):
        try:
            p.unlink()
        except Exception:
            pass
    print("提示：重建看板即可看到新描述：venv/Scripts/python.exe src/dashboard/build_dashboard.py")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Backfill missing dashboard Sonnet translations (manual, in-session).")
    ap.add_argument("cmd", choices=["detect", "merge"], help="detect missing items / merge translated output")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    return detect() if args.cmd == "detect" else merge()


if __name__ == "__main__":
    raise SystemExit(main())
