# SCRIPT_STATUS: ACTIVE — 验证日读档验收摘要(只读;不 import engine,契约零接触)
"""#10 读档验收辅助:把一个链版本某决策日的全部档案聚合成一页式验收摘要,
让人工验收从"点开 149 页"变成"读一页摘要 + 定向抽查 ~6 只"。

只读纯 JSON 解析(不 import engine 任何模块——本脚本永不影响契约哈希);
输出 md 到 workspace/outputs/ai_research_dept/acceptance/。

用法:
  venv/Scripts/python.exe workspace/research/ai_research_dept/acceptance_digest.py
  ... --version chain_v3.0 --day 20250127
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

if hasattr(sys.stdout, "reconfigure"):          # Windows GBK 控制台兜底
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CHAIN_ROOT = (PROJECT_ROOT / "workspace" / "outputs" / "ai_research_dept"
              / "analyst_chain")
OUT_DIR = PROJECT_ROOT / "workspace" / "outputs" / "ai_research_dept" / "acceptance"
SEATS = ("fund", "tech", "news")
FENCE_KEYS = ("dropped_ungrounded", "dropped_exclusive", "dropped_domain",
              "dropped_disclosure_fence")


def _stats(vals: list[float]) -> str:
    a = np.array([v for v in vals if v is not None and np.isfinite(v)], dtype=float)
    if a.size == 0:
        return "n=0"
    return (f"n={a.size} min={a.min():.1f} p10={np.percentile(a, 10):.1f} "
            f"med={np.median(a):.1f} p90={np.percentile(a, 90):.1f} "
            f"max={a.max():.1f} mean={a.mean():.1f}")


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

    arcs = [json.loads(p.read_text(encoding="utf-8")) for p in files]
    n = len(arcs)
    uniform = {k: Counter(str(a.get(k)) for a in arcs)
               for k in ("chain_version", "llm_config_hash",
                         "executed_contract_sha256", "manifest_fp")}
    complete = sum(bool(a.get("complete")) for a in arcs)
    attempts = Counter(a.get("attempt") for a in arcs)

    comp = [a["judge"].get("composite") for a in arcs]
    comp_adj = [a["judge"].get("composite_adj") for a in arcs]
    disp = [a["judge"].get("dispersion") for a in arcs]
    seat_finals = {s: [a["judge"]["finals"].get(s) for a in arcs] for s in SEATS}
    divergent = [a for a in arcs if a["judge"].get("divergence_flags")]
    disc_counter = Counter()
    for a in arcs:
        for d in (a["judge"].get("bear_discounts") or []):
            disc_counter[f"{d.get('seat')}.{d.get('dim')}"] += 1

    fence_sum = {s: Counter() for s in SEATS}
    seat_errors, empty_scores, clamped_names = [], [], []
    for a in arcs:
        for s in SEATS:
            seat = a.get("seats", {}).get(s) or {}
            fs = seat.get("fence_stats") or {}
            for k in FENCE_KEYS:
                fence_sum[s][k] += int(fs.get(k) or 0)
            fence_sum[s]["contested"] += len(fs.get("contested_ids") or [])
            fence_sum[s]["indirect_clamped"] += len(fs.get("indirect_clamped") or [])
            if fs.get("indirect_clamped"):
                clamped_names.append((a["ts_code"], s))
            if seat.get("error") not in (None, "None"):
                seat_errors.append((a["ts_code"], s, str(seat.get("error"))[:80]))
            if not (a.get("records", {}).get(s) or {}).get("factor_scores"):
                empty_scores.append((a["ts_code"], s))

    bear_valid = sum(bool(a["bear"].get("schema_valid")) for a in arcs)
    parse_modes = Counter(a["bear"].get("parse_mode") for a in arcs)
    nrefs = [len(a["bear"].get("refutations") or []) for a in arcs]
    zero_ref = [a["ts_code"] for a in arcs if not a["bear"].get("refutations")]
    bear_dropped = Counter()
    for a in arcs:
        for k, v in (a["bear"].get("validation_dropped") or {}).items():
            bear_dropped[k] += int(v or 0)

    def _top(vals, k=3, rev=True):
        pairs = [(a["ts_code"], v) for a, v in zip(arcs, vals) if v is not None]
        return sorted(pairs, key=lambda x: x[1], reverse=rev)[:k]

    spot = {
        "composite_adj 最高": _top(comp_adj),
        "composite_adj 最低": _top(comp_adj, rev=False),
        "dispersion 最高(席位最分歧)": _top(disp),
        "空头 refutations 最多": _top(nrefs),
    }

    lines = [
        f"# 读档验收摘要 · {args.version} · {args.day}",
        "",
        f"**档案** {n} 份 | complete {complete}/{n} | attempt 分布 {dict(attempts)}",
        "",
        "## 1. 一致性(必须每项只有 1 个值)",
    ]
    for k, c in uniform.items():
        ok = "✅" if len(c) == 1 else f"❌ {len(c)} 个不同值!"
        lines.append(f"- {k}: {ok} `{next(iter(c))[:60]}`")
    lines += [
        "",
        "## 2. 裁判分布",
        f"- composite: {_stats(comp)}",
        f"- composite_adj: {_stats(comp_adj)}",
        f"- dispersion: {_stats(disp)}",
    ]
    for s in SEATS:
        lines.append(f"- {s}.final: {_stats(seat_finals[s])}")
    lines += [
        f"- 背离旗: {len(divergent)}/{n}",
        f"- 空头折减 top5 维度: {disc_counter.most_common(5)}",
        "",
        "## 3. 机械围栏聚合(总丢弃量;大数 = 席位输出接地质量差,该抽查)",
    ]
    for s in SEATS:
        lines.append(f"- {s}: {dict(fence_sum[s])}")
    lines += [
        "",
        "## 4. 空头席",
        f"- schema_valid: {bear_valid}/{n} | parse_mode: {dict(parse_modes)}",
        f"- refutations/名: {_stats([float(x) for x in nrefs])} | 零反驳名字: {len(zero_ref)}",
        f"- validation_dropped 聚合: {dict(bear_dropped)}",
        "",
        "## 5. 异常清单(验收时优先看这些)",
        f"- 席位 error 非空: {seat_errors or '无'}",
        f"- factor_scores 为空的席位: {empty_scores[:10] or '无'}"
        + (f" (共{len(empty_scores)})" if len(empty_scores) > 10 else ""),
        f"- 间接证据被钳位的(news 席正常现象,>0 说明围栏在工作): {len(clamped_names)} 处",
        "",
        "## 6. 定向抽查建议(平台「个股分析」tab 打开原文核对)",
    ]
    for label, pairs in spot.items():
        lines.append(f"- {label}: " + ", ".join(f"{c}({v})" for c, v in pairs))
    lines += [
        "",
        "验收问题三件套:①一致性全绿?②异常清单可解释?③抽查名字的证据引用与结论"
        "读起来成立(证据行 ID 真实存在于卡片、结论没有引用外数字)?三件套通过即可"
        "签验收、开 16 日重放。",
    ]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"acceptance_digest_{args.version}_{args.day}.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nwritten -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
