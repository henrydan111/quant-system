# SCRIPT_STATUS: ACTIVE — chain_v2.2 机械围栏(GPT 复审#2:逐条健壮化+ID 类钳位+两遍独占)
"""Deterministic containment enforcement for the analyst chain.

复审#1(REVISE)确立围栏必须机械执行;复审#2(REVISE)修四个残余:
- 空头校验**逐条健壮**:类型检查先于成员检查(list 值的 target_seat/dim/falsifier_id
  曾触发 TypeError → 整只空头被清空且被永久复用);bool/字符串数字不当强度;
  kill_switches/blind_spots 非列表不迭代字符。
- 间接钳位按**注册 ID 类**判定(N00/NI*/NIA*/NDA*),不再按渲染词匹配
  (`[NDA1][直接聚合|…]` 曾以 5 分漏网)。
- 证据独占改**两遍计数**:被争用的行 ID 在所有条目中一律作废(先到先得让模型
  输出顺序决定胜者——同一内容换序曾使得分 10→5)。
- 证伪注册表带元数据:{fid: {seat, observable_in}},strength=5 快径要求
  refutation.target_seat 与证伪声明席位绑定。
"""
from __future__ import annotations

import math
import re
from numbers import Real

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


def span_line_id(span, lmap: dict[str, str]) -> str | None:
    """span 有效 ⇔ 含有效 ID 且规范化后与该 ID 的完整行相等(可省略行首'- ')。

    长度上限 160 与 scorecard._span_is_grounded 对齐:enforce 与 compute 必须用
    同一把尺,否则"enforce 收、compute 拒"会复活 adj>final 病灶(渲染端以标题截断
    保证合法行 <160)。
    """
    if not isinstance(span, str):
        return None
    s = _norm(span)
    if len(s) > 160:
        return None
    m = _ID_RE.search(span)
    if not m or m.group(1) not in lmap:
        return None
    target = lmap[m.group(1)]
    if s == target or s == target[2:].strip() or f"- {s}" == target:
        return m.group(1)
    return None


def _news_requires_cap(lid: str) -> bool:
    """间接/聚合/全景证据 → 该维封顶 3(复审#2 B4:按注册 ID 类判定,非渲染词)。
    ND=直接明细不钳;NX=缺席声明不钳;NI/NIA(含关联通道)/NDA(直接聚合)/N00 钳。"""
    return lid == "N00" or lid.startswith(("NI", "NDA"))


def enforce_v2_evidence(rec: dict, card_text: str, seat: str) -> dict:
    """行 ID 精确接地 + **两遍**ID 独占 + 间接钳位 + 披露围栏。原地修改并返回 rec。

    统计信息写入 rec['_fence_stats'](档案审计用,进档案前剥离下划线键)。
    """
    lmap = line_map(card_text)
    entries = rec.get("factor_scores", []) + rec.get("penalty_scores", [])
    # 第一遍:接地/围栏过滤 + 统计每个 ID 的声明次数(跨全部条目)
    dropped_ungrounded = dropped_fence = 0
    claims: dict[str, int] = {}
    per_entry: list[list[tuple[str, str]]] = []
    for entry in entries:
        kept = []
        for sp in (entry.get("evidence_spans") or []):
            lid = span_line_id(sp, lmap)
            if lid is None:
                dropped_ungrounded += 1
                continue
            if seat == "fund" and lid == "FD1" and entry.get("name") != "earnings_inflection":
                dropped_fence += 1            # 披露行只准支撑盈利拐点(§6.4 B 方案围栏)
                continue
            kept.append((lid, sp))
            claims[lid] = claims.get(lid, 0) + 1
        per_entry.append(kept)
    # 第二遍:被争用(声明>1 次)的 ID 在所有条目中一律作废——顺序无关(复审#2 Major-1)
    contested = {lid for lid, n in claims.items() if n > 1}
    dropped_exclusive = 0
    clamped: list[str] = []
    for entry, kept in zip(entries, per_entry):
        final_spans, ids = [], []
        for lid, sp in kept:
            if lid in contested:
                dropped_exclusive += 1
                continue
            final_spans.append(sp)
            ids.append(lid)
        entry["evidence_spans"] = final_spans
        if (seat == "news" and ids
                and any(_news_requires_cap(i) for i in ids)
                and isinstance(entry.get("score_0_5"), (int, float))
                and not isinstance(entry.get("score_0_5"), bool)
                and float(entry["score_0_5"]) > 3):
            entry["score_0_5"] = 3            # 间接/聚合证据封顶,确定性执行
            clamped.append(entry.get("name", "?"))
    rec["_fence_stats"] = {"dropped_ungrounded": dropped_ungrounded,
                           "dropped_exclusive": dropped_exclusive,
                           "dropped_disclosure_fence": dropped_fence,
                           "contested_ids": sorted(contested),
                           "indirect_clamped": clamped}
    return rec


#: 行 ID 前缀 → 证据域(strength=5 快径的 observable_in 域校验,复审#3 minor)
def _lid_domain(lid: str) -> str | None:
    if lid.startswith("F"):        # F/FB/FS/FD
        return "fund"
    if lid.startswith("T"):
        return "tech"
    if lid.startswith("N"):
        return "news"
    if lid.startswith("M"):
        return "market"
    return None


def validate_bear_record(rec: dict, all_cards_text: str, seat_weights: dict,
                         falsifiers: dict) -> dict:
    """空头输出 typed 校验:**逐条** fail-closed 丢弃(单条畸形绝不波及他条),
    返回净化记录 + 审计计数 + **schema_valid**(复审#3 B3:顶层容器损坏不得
    伪装成"空但正常"——它会让档案被标记完整并永久固化)。

    falsifiers: {falsifier_id: {"seat": str, "observable_in": str}} —— strength=5
    快径要求 falsifier_id 存在、声明席位 == target_seat、且反证行所在证据域 ∈
    该证伪声明的 observable_in(机械确认命中,非仅 ID 存在)。
    """
    lmap = line_map(all_cards_text)
    schema_valid = (isinstance(rec, dict)
                    and isinstance(rec.get("refutations"), list)
                    and isinstance(rec.get("kill_switches"), list)
                    and isinstance(rec.get("blind_spots"), list))
    valid, dropped = [], {"keys": 0, "pairing": 0, "strength": 0, "quote": 0,
                          "falsifier_downgraded": 0}
    refs = rec.get("refutations", []) if isinstance(rec, dict) else []
    if not isinstance(refs, list):
        refs = []
    for r in refs:
        # 键集(类型防御:非 dict / 键非全字符串 / 键集不符)
        if (not isinstance(r, dict)
                or not all(isinstance(k, str) for k in r)
                or not BEAR_REF_KEYS <= set(r)
                or not set(r) <= (BEAR_REF_KEYS | BEAR_REF_OPTIONAL)):
            dropped["keys"] += 1
            continue
        seat, dim = r.get("target_seat"), r.get("target_dim")
        # 类型检查先于成员检查(list 值曾触发 TypeError 清空整只空头)
        if not isinstance(seat, str) or not isinstance(dim, str) \
                or seat not in seat_weights or dim not in seat_weights.get(seat, {}):
            dropped["pairing"] += 1
            continue
        raw_strength = r.get("strength_0_5")
        if isinstance(raw_strength, bool) or not isinstance(raw_strength, Real):
            dropped["strength"] += 1
            continue
        try:
            strength = float(raw_strength)     # 10**10000 是 Real 但 float() 溢出(复审#3)
        except (TypeError, ValueError, OverflowError):
            dropped["strength"] += 1
            continue
        if not math.isfinite(strength) or not 0 <= strength <= 5:
            dropped["strength"] += 1
            continue
        strength = int(strength)
        quote_lid = span_line_id(r.get("counter_quote", ""), lmap)
        if quote_lid is None:
            dropped["quote"] += 1
            continue
        fid = r.get("falsifier_id")
        # 机械确认命中(复审#3 minor):ID 存在 + 席位绑定 + 反证域 ∈ 证伪声明的
        # observable_in(observable_in=fund 的证伪引用 M 行不再保 5)
        allowed = set(str(falsifiers.get(fid, {}).get("observable_in", "")
                          ).split("|")) if isinstance(fid, str) else set()
        fid_ok = (isinstance(fid, str) and fid in falsifiers
                  and falsifiers[fid].get("seat") == seat
                  and _lid_domain(quote_lid) in allowed)
        if strength == 5 and not fid_ok:
            strength = 4                       # 自动 5 分仅限机械验证的证伪命中
            dropped["falsifier_downgraded"] += 1
        valid.append({"target_seat": seat, "target_dim": dim,
                      "claim": _norm(r.get("claim", ""))[:_MAX_CLAIM],
                      "counter_quote": _norm(r["counter_quote"])[:200],
                      "strength_0_5": strength,
                      "reason": _norm(r.get("reason", ""))[:_MAX_REASON],
                      **({"falsifier_id": fid} if fid_ok else {})})
    ks_raw = rec.get("kill_switches") if isinstance(rec, dict) else None
    bs_raw = rec.get("blind_spots") if isinstance(rec, dict) else None
    ks = [_norm(k)[:_MAX_TEXT] for k in (ks_raw if isinstance(ks_raw, list) else [])
          if isinstance(k, str) and k.strip()][:5]
    bs = [_norm(b)[:_MAX_TEXT] for b in (bs_raw if isinstance(bs_raw, list) else [])
          if isinstance(b, str) and b.strip()][:5]
    return {"refutations": valid, "kill_switches": ks, "blind_spots": bs,
            "schema_valid": schema_valid, "validation_dropped": dropped}
