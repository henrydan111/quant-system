# SCRIPT_STATUS: ACTIVE — Macro wave M1: MS01-MS05 per-stock exposure rows
"""MS01-MS05 维度专属股票暴露行(宏观波次 M1,Tier-2)。

规范源:NEWS_FLASH_INTEGRATION_v1.md §6 + §0d m1/m2/M4。行 schema = 冻结的
11 字段 **+ M1 修订新增 `row_id`**(round-1 P2#1 记录在案,非"逐字"):
`row_id / mapping_id / mapping_version / mapping_sha256 / mapping_status /
exposure_type / exposure_bucket / exposure_value / snapshot_effective_at /
ts_code / dimension / source`;`mapped_no_exposure → exposure_value=null`
(绝不造 0);THS 概念无同期快照即省略(M4:不得拿今日成员套历史;省略 =
`mapped` 行业面 + value 内 `concepts_omitted` 标记,**非**行状态);THS **源
缺失/畸形**是独立的 `source_unavailable` 行状态(round-3 P1#1:源事故 ≠
合法省略)。

设计裁定(用户 2026-07-24,NF_UNIT_M1_DESIGN.md):
- MS04/MS05 = 策划映射资产(YAML,Claude 草拟 v1 → 用户审改 → 冻结;内容
  sha256 入注册表,改内容 = 升版);
- MS01/MS02 档位 = **池内三分位**(D 收盘指标,对池漂移稳定);
- 键 = 申万2021 L1 代码(`industry_as_of` 的返回,PIT 正确性由其承担)。

输入契约(M3 装配供给;M1 不读会话 pv 卡形帧):
- `pool_metrics`: DataFrame[ts_code, float_mv, turnover_20d, vol_20d] —— 决策池
  全体的 D 收盘指标(§0a 晚间模式下 D 收盘合法);
- `ths_members`: ths_members.parquet 形状(ts_code=板块, con_code=个股,
  fetched_at);快照门:`fetched_at <= cutoff` 才可用(未来快照套历史 = 省略)。

方向语义:映射通道**无符号**——受益/受损由宏观席配对 M/MF 事实评定;
缺席的**渲染措辞**(confirmed_absent_through)是 M3 宏观卡的职责,M1 行只携带
状态与 snapshot_effective_at。
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from data_infra.provider_metadata import industry_as_of  # noqa: E402

MAPPING_DIR = Path(__file__).parent / "macro_mappings"

#: 五维 → 行 ID(§6 输出五维,顺序即 MS01..MS05)
MS_DIMENSIONS = (
    ("MS01", "risk_appetite_fit"),
    ("MS02", "liquidity_funding"),
    ("MS03", "industry_concept_prosperity"),
    ("MS04", "policy_alignment"),
    ("MS05", "external_shock_transmission"),
)

#: 行 schema = §0d m1 冻结 11 字段 + **M1 修订新增 `row_id`**(GPT M1 round-1
#: P2#1:不得把 12 键描述为逐字合规——修订记录在 NF_UNIT_M1_DESIGN.md,
#: row_id 是 M2/M3 配对与渲染的行标识,属 M1 层的显式增字段)
MS_ROW_KEYS = frozenset({
    "row_id", "mapping_id", "mapping_version", "mapping_sha256",
    "mapping_status", "exposure_type", "exposure_bucket", "exposure_value",
    "snapshot_effective_at", "ts_code", "dimension", "source",
})

#: 注册状态枚举(fail-closed:未注册状态不得出现)。概念的快照省略**不是行
#: 状态**——行业面仍 mapped,省略以 value 内 `concepts_omitted` 标记呈现
#: (round-1 P2#1:实现语义保留,合同同步)。
MS_STATUSES = frozenset({
    "mapped",                       # 有暴露,bucket/value 已填
    "mapped_no_exposure",           # 已映射但该行业无注册通道 → value=null
    "unmapped_industry",            # PIT 行业不可解析/不在映射键内
    "metric_unavailable",           # 池指标缺该股/该列/分布不可分桶
    "source_unavailable",           # 上游源缺失/畸形(≠合法的历史无快照;
                                    # round-3 P1#1:源事故必须大声浮出,绝不
                                    # 伪装成 M4 省略)
})

#: 池内三分位的规则描述符(MS01/MS02 的 mapping_sha256 哈希对象——档位规则
#: 本身就是版本化资产;改规则 = 升版)。round-1 P2#2:tie/最小样本规则冻结
#: 入描述符——非平凡三分位要求 ≥6 个非 NaN 且 ≥3 个不同值;边界并列取低档
#: (value <= q 落 lower);退化分布 = 不可用,绝不产伪三分位。
_TERCILE_RULE_V1 = {
    "method": "pool_tercile", "version": "v1",
    "ms01_metrics": ["float_mv", "vol_20d"],
    "ms02_metrics": ["turnover_20d"],
    "labels": ["low", "mid", "high"],
    "min_observations": 6, "min_distinct": 3,
    "tie_rule": "le_boundary_falls_lower",
    "degenerate_distribution": "unavailable",
}
_TERCILE_RULE_SHA256 = hashlib.sha256(
    str(sorted(_TERCILE_RULE_V1.items())).encode()).hexdigest()

#: MS03 行业/概念标签规则描述符(同为版本化资产:PIT 行业源 + THS 快照门语义)
_MS03_RULE_V1 = {
    "method": "sw2021_l1_pit_plus_ths_snapshot", "version": "v1",
    "industry_source": "industry_as_of(L1)",
    "ths_gate": "fetched_at<=cutoff",
}
_MS03_RULE_SHA256 = hashlib.sha256(
    str(sorted(_MS03_RULE_V1.items())).encode()).hexdigest()


class MappingAssetError(ValueError):
    """映射资产畸形/未注册值 —— fail-closed。"""


def load_mapping_asset(path) -> dict:
    """载入 + 校验一份策划映射资产;`mapping_sha256` = 文件字节哈希(内容变 →
    哈希变 → C16b 注册面变)。"""
    path = Path(path)
    raw = path.read_bytes()
    doc = yaml.safe_load(raw)
    if not isinstance(doc, dict):
        raise MappingAssetError(f"{path.name}: 顶层须为映射对象")
    for k in ("mapping_id", "mapping_version", "key_type", "channels", "map"):
        if k not in doc:
            raise MappingAssetError(f"{path.name}: 缺必备键 {k}")
    if doc["key_type"] != "sw2021_l1_code":
        raise MappingAssetError(f"{path.name}: key_type {doc['key_type']!r} 未注册")
    channels = doc["channels"]
    if not isinstance(channels, list) or not all(
            isinstance(c, str) and c for c in channels):
        raise MappingAssetError(f"{path.name}: channels 须为非空字符串列表")
    reg = set(channels)
    mp = doc["map"]
    if not isinstance(mp, dict) or not mp:
        raise MappingAssetError(f"{path.name}: map 须为非空对象")
    for code, entry in mp.items():
        if not (isinstance(code, str) and code.endswith(".SI")):
            raise MappingAssetError(f"{path.name}: 键 {code!r} 非 SW L1 代码")
        if not isinstance(entry, list):
            raise MappingAssetError(f"{path.name}: {code} 值须为列表")
        for item in entry:
            ch = item.get("channel") if isinstance(item, dict) else item
            if ch not in reg:
                raise MappingAssetError(
                    f"{path.name}: {code} 通道 {ch!r} 未在 channels 注册")
            if isinstance(item, dict):
                extra = set(item) - {"channel", "sensitivity"}
                if extra or item.get("sensitivity") not in ("high", "medium"):
                    raise MappingAssetError(
                        f"{path.name}: {code} 条目 {item!r} 畸形"
                        f"(sensitivity 只注册 high/medium)")
    return {"mapping_id": doc["mapping_id"],
            "mapping_version": doc["mapping_version"],
            "mapping_sha256": hashlib.sha256(raw).hexdigest(),
            "channels": tuple(channels), "map": mp}


def load_default_mappings() -> dict:
    """仓内 v1 资产(用户审改对象)。返回 {"policy": ..., "shock": ...}。"""
    return {
        "policy": load_mapping_asset(MAPPING_DIR / "ms04_policy_channels_v1.yaml"),
        "shock": load_mapping_asset(MAPPING_DIR / "ms05_shock_channels_v1.yaml"),
    }


def select_ths_snapshot(ths_members, cutoff):
    """选定**唯一、完整、一致**的 THS 快照(round-1 P1#1:旧码取
    `fetched_at.iloc[0]` 判门却用整表取成员——混合新旧快照的帧会把未来概念漏进
    历史行,且结果依赖行序)。

    返回 `(snapshot_frame, effective_at_iso, content_sha256, status)`,
    status ∈ {selected, no_eligible_snapshot, source_unavailable}——
    round-3 P1#1:**源缺失/畸形**(非 DataFrame/空帧/缺列/时间戳全不可解析)
    与**真实历史库但快照全部晚于 cutoff**(合法的 M4 省略)必须可区分:前者
    是运维/配置事故,绝不伪装成"可证明的历史无快照"。

    规则:按 `fetched_at` 分组,候选 = 全部 `<= cutoff`,取**最新**一个,只用
    该时点完整成员;content_sha256 = 该快照 (板块, 个股) 有序对集合的规范哈希
    (round-1 P1#2 的快照内容身份)。"""
    if not isinstance(ths_members, pd.DataFrame) or ths_members.empty \
            or not {"fetched_at", "ts_code", "con_code"} <= set(ths_members.columns):
        return pd.DataFrame(), None, None, "source_unavailable"
    cut_ts = pd.Timestamp(cutoff)
    stamps = pd.to_datetime(ths_members["fetched_at"], errors="coerce")
    if stamps.isna().all():
        return pd.DataFrame(), None, None, "source_unavailable"
    ok = stamps.notna() & (stamps <= cut_ts)
    if not ok.any():
        return pd.DataFrame(), None, None, "no_eligible_snapshot"
    chosen = stamps[ok].max()
    snap = ths_members[stamps == chosen]
    pairs = sorted(zip(snap["ts_code"].astype(str),
                       snap["con_code"].astype(str)))
    content = hashlib.sha256(
        "\n".join(f"{b}|{c}" for b, c in pairs).encode()).hexdigest()
    return snap, chosen.isoformat(), content, "selected"


def exposure_mapping_bundle_sha256(mappings: dict, *, ths_snapshot=None) -> str:
    """暴露身份束哈希——入 C16b 注册面(标签束哈希合同)。

    round-1 P1#2:**带角色名的规范 JSON**(裸哈希排序会让 policy/shock 互换后
    束不变),覆盖全部静态规则/映射;`ths_snapshot=(effective_at, content_sha)`
    时把选定快照身份一并封入(M3 逐日封存用)。"""
    body = {"tercile_rule": _TERCILE_RULE_SHA256,
            "ms03_rule": _MS03_RULE_SHA256,
            "policy_mapping": mappings["policy"]["mapping_sha256"],
            "shock_mapping": mappings["shock"]["mapping_sha256"],
            "ths_snapshot": (None if ths_snapshot is None
                             else {"effective_at": ths_snapshot[0],
                                   "content_sha256": ths_snapshot[1]})}
    import json as _json
    return hashlib.sha256(
        _json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _tercile(value, series: pd.Series) -> "str | None":
    """池内三分位档(low/mid/high);值/样本量/分布不可用 → None(round-1
    P2#2 冻结规则:≥6 非 NaN、≥3 不同值、退化分布不可用、边界并列取低档)。"""
    if value is None or pd.isna(value):
        return None
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) < _TERCILE_RULE_V1["min_observations"] \
            or s.nunique() < _TERCILE_RULE_V1["min_distinct"]:
        return None
    q1, q2 = s.quantile(1 / 3), s.quantile(2 / 3)
    if q1 == q2:                                   # 退化分布 → 不可用
        return None
    return "low" if value <= q1 else ("mid" if value <= q2 else "high")


def _row(row_id, dimension, *, mapping_id, mapping_version, mapping_sha256,
         status, exposure_type, bucket, value, snapshot_at, ts_code,
         source) -> dict:
    if status not in MS_STATUSES:
        raise MappingAssetError(f"未注册 mapping_status {status!r}")
    if status != "mapped" and value is not None and status != "mapped_no_exposure":
        raise MappingAssetError(f"{row_id}: 非 mapped 状态不得携带 value")
    if status == "mapped_no_exposure" and value is not None:
        raise MappingAssetError(f"{row_id}: mapped_no_exposure 必须 value=null(不造 0)")
    out = {"row_id": row_id, "dimension": dimension, "mapping_id": mapping_id,
           "mapping_version": mapping_version, "mapping_sha256": mapping_sha256,
           "mapping_status": status, "exposure_type": exposure_type,
           "exposure_bucket": bucket, "exposure_value": value,
           "snapshot_effective_at": snapshot_at, "ts_code": ts_code,
           "source": source}
    assert set(out) == MS_ROW_KEYS
    return out


def build_ms_exposure_rows(ts_code: str, day, *, cutoff, pool_metrics,
                           ths_members, mappings) -> list:
    """一只股票一决策日的**恰五行**暴露行(MS01..MS05,顺序固定)。

    - `day`: 决策日 YYYYMMDD/Timestamp(PIT 行业按此解析);
    - `cutoff`: 决策 cutoff(THS 快照门:fetched_at <= cutoff 才可用);
    - `pool_metrics`: 决策池 D 收盘指标帧(见模块 docstring 契约);
    - `mappings`: `load_default_mappings()` 的返回。"""
    day_ts = pd.Timestamp(str(day))
    cut_ts = pd.Timestamp(cutoff)
    rows: list = []

    # round-3 P1#2:池指标 ts_code 必须**全表唯一**——重复行(上游 merge 事故
    # 的常见形态)曾让同股同日的档位随行序在 low/high 间翻转,iloc[0] 只是把
    # 任意选择封存下来。fail-closed 拒,不定义静默去重。
    if isinstance(pool_metrics, pd.DataFrame) and "ts_code" in pool_metrics:
        dup = pool_metrics["ts_code"][pool_metrics["ts_code"].duplicated()]
        if len(dup):
            raise MappingAssetError(
                f"pool_metrics.ts_code 重复({sorted(set(dup.astype(str)))[:3]}…)"
                f"——档位会依赖行序,拒(round-3 P1#2;上游先去重再供给)")

    # ---- MS01 风险偏好 / MS02 流动性:池内三分位(D 收盘) ----
    me = None
    if isinstance(pool_metrics, pd.DataFrame) and "ts_code" in pool_metrics:
        hit = pool_metrics[pool_metrics["ts_code"] == ts_code]
        me = hit.iloc[0] if len(hit) else None

    def _metric_row(row_id, dim, metrics, exposure_type):
        if me is None or any(m not in pool_metrics.columns for m in metrics):
            return _row(row_id, dim, mapping_id=f"{row_id.lower()}_style_terciles",
                        mapping_version=_TERCILE_RULE_V1["version"],
                        mapping_sha256=_TERCILE_RULE_SHA256,
                        status="metric_unavailable", exposure_type=exposure_type,
                        bucket=None, value=None, snapshot_at=str(day_ts.date()),
                        ts_code=ts_code, source="pool_metrics_d_close")
        # round-1 P1#3:**全有或全无**——任一必需指标不可分桶(NaN/样本不足/
        # 退化分布)= 整行 metric_unavailable,绝不输出部分暴露(NaN float_mv
        # 配有效 vol_20d 曾产出 mapped 的半行)
        buckets, values = {}, {}
        for m in metrics:
            t = _tercile(me[m], pool_metrics[m])
            if t is None:
                return _row(row_id, dim,
                            mapping_id=f"{row_id.lower()}_style_terciles",
                            mapping_version=_TERCILE_RULE_V1["version"],
                            mapping_sha256=_TERCILE_RULE_SHA256,
                            status="metric_unavailable",
                            exposure_type=exposure_type,
                            bucket=None, value=None,
                            snapshot_at=str(day_ts.date()),
                            ts_code=ts_code, source="pool_metrics_d_close")
            buckets[m] = t
            values[m] = float(me[m])
        bucket = "|".join(f"{m}_{buckets[m]}" for m in metrics)
        return _row(row_id, dim, mapping_id=f"{row_id.lower()}_style_terciles",
                    mapping_version=_TERCILE_RULE_V1["version"],
                    mapping_sha256=_TERCILE_RULE_SHA256, status="mapped",
                    exposure_type=exposure_type, bucket=bucket, value=values,
                    snapshot_at=str(day_ts.date()), ts_code=ts_code,
                    source="pool_metrics_d_close")

    rows.append(_metric_row("MS01", "risk_appetite_fit",
                            _TERCILE_RULE_V1["ms01_metrics"], "style_bucket"))
    rows.append(_metric_row("MS02", "liquidity_funding",
                            _TERCILE_RULE_V1["ms02_metrics"], "liquidity_bucket"))

    # ---- 行业解析(PIT,MS03/04/05 共用) ----
    l1 = industry_as_of(ts_code, day_ts, "L1")

    # ---- MS03 行业·概念:PIT 行业 + THS 概念(快照门) ----
    # round-1 P1#1:经 select_ths_snapshot 选定**唯一最新 <= cutoff** 的完整
    # 快照;round-3 P1#1:源缺失/畸形 ≠ 合法省略——source_unavailable 整行
    # 独立状态(即便行业可解析,源事故必须大声浮出,不可评分)
    snap, ths_snapshot, ths_content_sha, ths_status = \
        select_ths_snapshot(ths_members, cut_ts)
    if ths_status == "source_unavailable":
        rows.append(_row("MS03", "industry_concept_prosperity",
                         mapping_id="ms03_industry_concept_tags",
                         mapping_version=_MS03_RULE_V1["version"],
                         mapping_sha256=_MS03_RULE_SHA256,
                         status="source_unavailable",
                         exposure_type="industry_concept_tags", bucket=None,
                         value=None, snapshot_at=None, ts_code=ts_code,
                         source="sw2021_pit+ths_members"))
        l1_for_ms03_done = True
    else:
        l1_for_ms03_done = False
    concepts = []
    if ths_snapshot is not None:
        concepts = sorted(
            snap[snap["con_code"] == ts_code]["ts_code"]
            .astype(str).unique().tolist())
    if l1_for_ms03_done:
        pass
    elif l1 is None:
        rows.append(_row("MS03", "industry_concept_prosperity",
                         mapping_id="ms03_industry_concept_tags",
                         mapping_version=_MS03_RULE_V1["version"],
                         mapping_sha256=_MS03_RULE_SHA256,
                         status="unmapped_industry",
                         exposure_type="industry_concept_tags", bucket=None,
                         value=None, snapshot_at=ths_snapshot, ts_code=ts_code,
                         source="sw2021_pit+ths_members"))
    else:
        val = {"l1_code": l1, "concepts": concepts}
        status = "mapped"
        if ths_snapshot is None:
            # 行业仍可映射;概念按 M4 省略——状态用 mapped(行业面成立),
            # value.concepts=[] + snapshot_at=None 忠实呈现省略
            val["concepts_omitted"] = "no_contemporaneous_snapshot"
        else:
            val["ths_content_sha256"] = ths_content_sha   # P1#2:快照内容身份
        rows.append(_row("MS03", "industry_concept_prosperity",
                         mapping_id="ms03_industry_concept_tags",
                         mapping_version=_MS03_RULE_V1["version"],
                         mapping_sha256=_MS03_RULE_SHA256,
                         status=status, exposure_type="industry_concept_tags",
                         bucket=l1, value=val, snapshot_at=ths_snapshot,
                         ts_code=ts_code, source="sw2021_pit+ths_members"))

    # ---- MS04 政策通道 / MS05 冲击通道:策划映射 ----
    for row_id, dim, key, exposure_type in (
            ("MS04", "policy_alignment", "policy", "policy_channel"),
            ("MS05", "external_shock_transmission", "shock", "shock_channel")):
        mp = mappings[key]
        if l1 is None or l1 not in mp["map"]:
            rows.append(_row(row_id, dim, mapping_id=mp["mapping_id"],
                             mapping_version=mp["mapping_version"],
                             mapping_sha256=mp["mapping_sha256"],
                             status="unmapped_industry", exposure_type=exposure_type,
                             bucket=None, value=None, snapshot_at=None,
                             ts_code=ts_code, source=f"{mp['mapping_id']}[{l1}]"))
            continue
        entry = mp["map"][l1]
        if not entry:
            rows.append(_row(row_id, dim, mapping_id=mp["mapping_id"],
                             mapping_version=mp["mapping_version"],
                             mapping_sha256=mp["mapping_sha256"],
                             status="mapped_no_exposure",
                             exposure_type=exposure_type, bucket=None, value=None,
                             snapshot_at=None, ts_code=ts_code,
                             source=f"{mp['mapping_id']}[{l1}]"))
            continue
        if isinstance(entry[0], dict):             # MS05 带 sensitivity
            bucket = "|".join(f"{e['channel']}:{e['sensitivity']}" for e in entry)
            value = [dict(e) for e in entry]
        else:                                      # MS04 纯通道
            bucket = "|".join(entry)
            value = list(entry)
        rows.append(_row(row_id, dim, mapping_id=mp["mapping_id"],
                         mapping_version=mp["mapping_version"],
                         mapping_sha256=mp["mapping_sha256"], status="mapped",
                         exposure_type=exposure_type, bucket=bucket, value=value,
                         snapshot_at=None, ts_code=ts_code,
                         source=f"{mp['mapping_id']}[{l1}]"))
    assert [r["row_id"] for r in rows] == [rid for rid, _ in MS_DIMENSIONS]
    return rows
