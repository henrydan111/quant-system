# SCRIPT_STATUS: ACTIVE — 新闻快讯管线确定性核心(NF wave §7 step 2+3;LLM 分型/路由在下一块)
"""News-flash pipeline — the DETERMINISTIC, PIT-safe core (design v1.12 §6b/§7).

本模块只做**确定性、可复现、零 LLM** 的部分,全部 as-of `input_cutoff_at`:
- session/market-state(M2‴):`market_state_at_publish` + `no_exchange_session_since_publish`
  纯由发布时刻 × 交易日历判定(午休/节假日/集合竞价显式处理),PIT 平凡安全;
- 不可变簇快照(M1″):成员按 `decision_visible_at = max(source_published_at,
  first_ingested_at) ≤ cutoff` 分桶;跨源规范化指纹聚簇 append-only;
- 源家族(B4):同措辞/同时序 = 一个 `n_independent_sources`,`n_outlets` 只展示;
- 流特征(E1):固定窗 (T−24h,T]/(T−120h,T]/(T−480h,T] 唯一簇计数 + 独立源广度;
  velocity = count_1d/(count_20d/20) 仅分母>0 否则 null(**绝不地板**);
- 确定性预过滤 + 协同检测(B4/E6):长度域/黑嘴词表硬丢弃 + coordination_flag。

⚠ 所有流/广度只从 cutoff 前可见成员算;history_bulk 成员(回填、无真时间戳)由
`decision_visible_at` 语义自动排除——回填行 first_ingested_at 晚,cutoff 前不可见。
LLM 分型(event_type × verification_status × content_kind)+ 三路路由 + attention 卡
渲染在 news_ingest_llm.py(下一块),消费本模块的确定性输出。
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field

import pandas as pd

# ---- A-share trading sessions (Asia/Shanghai, calendar = truth) ----
_AM_OPEN = pd.Timedelta("9:30:00")
_AM_CLOSE = pd.Timedelta("11:30:00")
_PM_OPEN = pd.Timedelta("13:00:00")
_PM_CLOSE = pd.Timedelta("15:00:00")
_CALL_AUCTION_OPEN = pd.Timedelta("9:15:00")   # 集合竞价起


def _norm_text(s) -> str:
    """规范化用于指纹/相似:NFKC + 去控制符 + 折叠空白 + 小写(纯 ASCII 小写)。"""
    s = unicodedata.normalize("NFKC", str(s))
    s = "".join(ch for ch in s if unicodedata.category(ch) not in ("Cc", "Cf"))
    return re.sub(r"\s+", " ", s).strip().lower()


def _text_fingerprint(content: str) -> str:
    """跨源规范化指纹(聚簇基础):正文前 120 规范化字符的 sha1[:16]。"""
    return hashlib.sha1(_norm_text(content)[:120].encode()).hexdigest()[:16]


# --------------------------------------------------- session / market state (M2‴)

def market_state_at_publish(published_at, is_open_day: bool) -> str:
    """发布时刻所处市场状态(交易所派生,PIT 平凡):
    intraday / after_close / pre_open / overnight。非交易日 = overnight。"""
    ts = pd.Timestamp(published_at)
    if not is_open_day:
        return "overnight"
    tod = ts - ts.normalize()
    if tod >= _PM_CLOSE:
        return "after_close"                   # 15:00 起
    if _CALL_AUCTION_OPEN <= tod < _AM_OPEN:
        return "pre_open"                       # 9:15–9:30 集合竞价
    if tod >= _AM_OPEN:
        return "intraday"                       # 9:30–15:00,含午休(当日市场已成交)
    return "overnight"                          # 开市日 9:15 前


def _sessions_in_window(open_days: set, t0: pd.Timestamp, t1: pd.Timestamp) -> bool:
    """(t0, t1] 内是否存在任一交易所价格发现区间(含集合竞价)。逐开市日检查
    该日 [9:15, 11:30] ∪ [13:00, 15:00] 与 (t0,t1] 是否相交。"""
    for d in open_days:
        day = pd.Timestamp(d).normalize()
        if day > t1.normalize() or day < (t0.normalize() - pd.Timedelta(days=1)):
            continue
        for a, b in ((_CALL_AUCTION_OPEN, _AM_CLOSE), (_PM_OPEN, _PM_CLOSE)):
            s, e = day + a, day + b
            if s <= t1 and e > t0:             # 区间 (t0,t1] 与 [s,e] 相交
                return True
    return False


def no_exchange_session_since_publish(published_at, cutoff, open_days: set) -> bool:
    """事实字段(M2‴ 替代 unpriced_since_close):自发布至 cutoff 之间是否**没有**任何
    交易所价格发现区间。True = 市场自发布起一直关闭 → 该快讯至 cutoff 尚未有被定价机会。"""
    t0, t1 = pd.Timestamp(published_at), pd.Timestamp(cutoff)
    if t1 <= t0:
        return True
    return not _sessions_in_window(set(open_days), t0, t1)


# --------------------------------------------------- 确定性预过滤 + 协同(B4/E6)

#: 黑嘴/荐股话术硬丢弃词表(版本化;命中即 drop,进运行清单对账)
TOUT_PATTERNS_V1 = (
    "涨停战法", "抓涨停", "翻倍黑马", "牛股推荐", "免费荐股", "加微信", "加qq",
    "进群领", "老师带", "包赚", "稳赚", "保底收益", "目标价", "满仓", "梭哈",
    "内幕消息", "独家内幕", "拉升在即", "主力已介入", "今日金股",
)
_MIN_CONTENT_LEN = 8


def deterministic_prefilter(content: str) -> tuple[bool, str]:
    """确定性预过滤(零 LLM,先砍量)。返回 (kept, drop_reason)。"""
    norm = _norm_text(content)
    if len(norm) < _MIN_CONTENT_LEN:
        return False, "too_short"
    for pat in TOUT_PATTERNS_V1:
        if pat in norm:
            return False, f"tout:{pat}"
    return True, ""


# --------------------------------------------------- 簇 + 源家族(M1″/B4)

@dataclass
class ClusterSnapshot:
    """cutoff T 的不可变簇快照(M1″)。只含 decision_visible_at ≤ T 的成员。"""
    cluster_id: str
    cutoff: pd.Timestamp
    members: pd.DataFrame                       # src / datetime / content / decision_visible_at
    cluster_first_visible_at: pd.Timestamp
    n_outlets: int                              # 不同 src 数(展示)
    n_independent_sources: int                  # 源家族数(计分)
    snapshot_id: str = field(default="")

    def __post_init__(self):
        if not self.snapshot_id:
            key = f"{self.cluster_id}\x1f{self.cutoff.isoformat()}\x1f{len(self.members)}"
            self.snapshot_id = hashlib.sha1(key.encode()).hexdigest()[:16]


def _source_families(members: pd.DataFrame) -> int:
    """独立源家族数(B4):同规范化正文指纹 + 同分钟 = 一个家族(转载洗白封死)。
    独立性无法确立时默认合并(保守=1)。"""
    if members.empty:
        return 0
    fam = (members["content"].map(_text_fingerprint) + "|"
           + members["datetime"].map(lambda x: pd.Timestamp(x).strftime("%Y%m%d%H%M")))
    return int(fam.nunique())


def build_cluster_snapshots(visible: pd.DataFrame, cutoff) -> list[ClusterSnapshot]:
    """从 cutoff 前可见成员构造不可变簇快照(M1″)。visible 必须已按
    decision_visible_at ≤ cutoff 过滤(由 text_store.load_text 保证)。
    聚簇键 = 规范化正文指纹(跨源同一事实归一簇)。"""
    cutoff = pd.Timestamp(cutoff)
    if visible.empty:
        return []
    v = visible.copy()
    v["_fp"] = v["content"].map(_text_fingerprint)
    out = []
    for fp, grp in v.groupby("_fp", sort=True):
        grp = grp.sort_values("decision_visible_at")
        out.append(ClusterSnapshot(
            cluster_id=fp, cutoff=cutoff, members=grp.drop(columns="_fp"),
            cluster_first_visible_at=pd.Timestamp(grp["decision_visible_at"].min()),
            n_outlets=int(grp["src"].nunique()),
            n_independent_sources=_source_families(grp)))
    return out


def coordination_flag(cluster: ClusterSnapshot, *, burst_seconds: int = 900) -> dict:
    """协同/pump 检测(E6 → 空头反转风险,NFC 负向证据类)。多个貌似独立媒体 +
    同措辞 + 突发爆量 = 协同。返回 {flag, n_outlets, n_independent_sources, burst}。
    结构化背书状态由下游(有结构化事件簇)判定,此处只给确定性形态特征。"""
    m = cluster.members
    times = pd.to_datetime(m["datetime"])
    burst = (len(m) >= 3 and (times.max() - times.min()).total_seconds() <= burst_seconds)
    # 多 outlet 但独立源家族少 = 转载协同(n_outlets >> n_independent_sources)
    syndicated = cluster.n_outlets >= 3 and cluster.n_independent_sources <= 1
    return {"coordination_flag": bool(burst and syndicated),
            "n_outlets": cluster.n_outlets,
            "n_independent_sources": cluster.n_independent_sources,
            "burst": bool(burst), "syndicated": bool(syndicated)}


# --------------------------------------------------- 流特征(E1,as-of 固定窗)

_FLOW_WINDOWS = {"1d": pd.Timedelta(hours=24), "5d": pd.Timedelta(hours=120),
                 "20d": pd.Timedelta(hours=480)}


def flow_features(entity_clusters: list[ClusterSnapshot], cutoff) -> dict:
    """单实体流动态(E1,attention_only 域)。窗口止于 cutoff,计数=唯一簇,
    广度=唯一独立源家族总数。velocity=count_1d/(count_20d/20) 仅分母>0 否则 None
    (**绝不地板**,round-8 M1)。全部 as-of:传入的簇已是 cutoff 快照。"""
    cutoff = pd.Timestamp(cutoff)
    counts, breadth = {}, {}
    for name, span in _FLOW_WINDOWS.items():
        lo = cutoff - span
        in_win = [c for c in entity_clusters if lo < c.cluster_first_visible_at <= cutoff]
        counts[name] = len(in_win)
        breadth[name] = sum(c.n_independent_sources for c in in_win)
    c1, c20 = counts["1d"], counts["20d"]
    velocity = (c1 / (c20 / 20.0)) if c20 > 0 else None
    return {"flow_count_1d": c1, "flow_count_5d": counts["5d"],
            "flow_count_20d": c20, "coverage_breadth_1d": breadth["1d"],
            "flow_velocity": velocity,
            "flow_velocity_status": "ok" if c20 > 0 else "not_applicable_zero_baseline"}
