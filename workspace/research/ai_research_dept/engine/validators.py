# SCRIPT_STATUS: ACTIVE — chain_v2.1 机械围栏(GPT REVISE Blocker-3/4:围栏从 prompt 落到代码)
"""Deterministic containment enforcement for the analyst chain.

GPT cross-review (REVISE) Blocker-3/4: prompt-only rules let unvalidated LLM output
deterministically alter scores. This module makes every fence mechanical:

- 行 ID 精确接地:evidence span 必须是「[ID] + 完整行」的逐字复制(规范化空白后全行相等),
  不再接受子串;ID 必须存在于对应卡片。
- 证据独占按行 ID:同一行 ID 在 factor+penalty 全体条目中至多出现一次(先到先得)。
- 消息席间接钳位:任一证据行来自间接通道([概念]/[行业]/聚合)→ 该维分数确定性钳到 ≤3。
- 披露围栏:披露动态行(FD1)只可支撑 earnings_inflection,其他维引用即剔除该 span。
- 空头 typed 校验(fail-closed 逐条丢弃):精确键集/席位-维度配对/强度有限值[0,5]/
  文本长度上限/counter_quote 必须为卡内完整行;strength=5 仅当携带有效 falsifier_id
  (证伪回验快径,机械可查)——否则降级为 4。裁判只消费校验后的反驳。
"""
from __future__ import annotations

import re

_ID_RE = re.compile(r"\[([A-Z]{1,4}\d{0,3})\]")
_WS = re.compile(r"\s+")

BEAR_REF_KEYS = {"target_seat", "target_dim", "claim", "counter_quote",
                 "strength_0_5", "reason"}
BEAR_REF_OPTIONAL = {"falsifier_id"}
_MAX_CLAIM = 60
_MAX_REASON = 90
_MAX_TEXT = 60


def _norm(s: str) -> str:
    return _WS.sub(" ", str(s)).strip()


def line_map(card_text: str) -> dict[str, str]:
    """卡片行 ID → 规范化完整行(以「- [ID]」起头的行才是证据行)。"""
    out = {}
    for line in str(card_text).splitlines():
        t = line.strip()
        if not t.startswith("- ["):
            continue
        m = _ID_RE.search(t[:14])
        if m:
            out[m.group(1)] = _norm(t)
    return out


def span_line_id(span: str, lmap: dict[str, str]) -> str | None:
    """span 有效 ⇔ 含有效 ID 且规范化后与该 ID 的完整行相等(可省略行首'- ')。

    长度上限 160 与 scorecard._span_is_grounded 对齐:enforce 与 compute 必须用
    同一把尺,否则"enforce 收、compute 拒"会复活 adj>final 病灶(渲染端以标题截断
    保证合法行 <160)。
    """
    s = _norm(span)
    if len(s) > 160:
        return None
    m = _ID_RE.search(str(span))
    if not m or m.group(1) not in lmap:
        return None
    target = lmap[m.group(1)]
    if s == target or s == target[2:].strip() or f"- {s}" == target:
        return m.group(1)
    return None


def _is_indirect_line(line: str) -> bool:
    return ("[概念" in line) or ("[行业" in line) or ("聚合]" in line)


def enforce_v2_evidence(rec: dict, card_text: str, seat: str) -> dict:
    """行 ID 精确接地 + ID 独占 + 间接钳位 + 披露围栏。原地修改并返回 rec。

    统计信息写入 rec['_fence_stats'](档案审计用,进档案前剥离下划线键)。
    """
    lmap = line_map(card_text)
    used: set[str] = set()
    dropped_ungrounded = dropped_exclusive = dropped_fence = 0
    clamped: list[str] = []
    for entry in rec.get("factor_scores", []) + rec.get("penalty_scores", []):
        kept, ids = [], []
        for sp in (entry.get("evidence_spans") or []):
            lid = span_line_id(sp, lmap)
            if lid is None:
                dropped_ungrounded += 1
                continue
            if lid in used:
                dropped_exclusive += 1
                continue
            if seat == "fund" and lid == "FD1" and entry.get("name") != "earnings_inflection":
                dropped_fence += 1            # 披露行只准支撑盈利拐点(§6.4 B 方案围栏)
                continue
            used.add(lid)
            kept.append(sp)
            ids.append(lid)
        entry["evidence_spans"] = kept
        if (seat == "news" and kept
                and any(_is_indirect_line(lmap[i]) for i in ids)
                and isinstance(entry.get("score_0_5"), (int, float))
                and float(entry["score_0_5"]) > 3):
            entry["score_0_5"] = 3            # 间接证据封顶,确定性执行
            clamped.append(entry.get("name", "?"))
    rec["_fence_stats"] = {"dropped_ungrounded": dropped_ungrounded,
                           "dropped_exclusive": dropped_exclusive,
                           "dropped_disclosure_fence": dropped_fence,
                           "indirect_clamped": clamped}
    return rec


def validate_bear_record(rec: dict, all_cards_text: str, seat_weights: dict,
                         falsifier_ids: set[str]) -> dict:
    """空头输出 typed 校验:逐条 fail-closed 丢弃,返回净化记录 + 审计计数。"""
    lmap = line_map(all_cards_text)
    valid, dropped = [], {"keys": 0, "pairing": 0, "strength": 0, "quote": 0,
                          "falsifier_downgraded": 0}
    refs = rec.get("refutations", [])
    if not isinstance(refs, list):
        refs = []
    for r in refs:
        if not isinstance(r, dict) or not BEAR_REF_KEYS <= set(r) \
                or not set(r) <= (BEAR_REF_KEYS | BEAR_REF_OPTIONAL):
            dropped["keys"] += 1
            continue
        seat, dim = r.get("target_seat"), r.get("target_dim")
        if seat not in seat_weights or dim not in seat_weights.get(seat, {}):
            dropped["pairing"] += 1
            continue
        try:
            strength = float(r["strength_0_5"])
        except (TypeError, ValueError):
            dropped["strength"] += 1
            continue
        if not (strength == strength and 0 <= strength <= 5):   # NaN/域外
            dropped["strength"] += 1
            continue
        strength = int(min(5, max(0, strength)))
        if span_line_id(r.get("counter_quote", ""), lmap) is None:
            dropped["quote"] += 1
            continue
        fid = r.get("falsifier_id")
        if strength == 5 and fid not in falsifier_ids:
            strength = 4                       # 自动 5 分仅限机械验证过的证伪命中
            dropped["falsifier_downgraded"] += 1
        valid.append({"target_seat": seat, "target_dim": dim,
                      "claim": _norm(r.get("claim", ""))[:_MAX_CLAIM],
                      "counter_quote": _norm(r["counter_quote"])[:200],
                      "strength_0_5": strength,
                      "reason": _norm(r.get("reason", ""))[:_MAX_REASON],
                      **({"falsifier_id": fid} if fid in falsifier_ids else {})})
    ks = [_norm(k)[:_MAX_TEXT] for k in (rec.get("kill_switches") or [])
          if isinstance(k, str) and k.strip()][:5]
    bs = [_norm(b)[:_MAX_TEXT] for b in (rec.get("blind_spots") or [])
          if isinstance(b, str) and b.strip()][:5]
    return {"refutations": valid, "kill_switches": ks, "blind_spots": bs,
            "validation_dropped": dropped}
