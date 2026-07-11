# SCRIPT_STATUS: ACTIVE — 引擎 LLM 配置:火山方舟统一入口 + 按任务复杂度分层 + thinking 开关
"""LLM routing config (用户裁定 2026-07-09):一切 LLM 调用走火山 Ark API key
(src/ai_layer/ark_client.chat —— 已支持任意 model id + thinking 三态);模型按任务
复杂度指定;thinking 模式按任务开启。

治理:本表属 config 工件(版本化+哈希);任一 (task → model/thinking) 变更 = 新
LLM_CONFIG_VERSION;凡进入评分/检索的任务路由变更同时受 C16b/横切#8 约束。
⚠ MVP 前向系统(rerank_v2,冻结哈希)不受本表影响 —— 两条产品线各自配置。

thinking 取舍(记录):抽取/分型类 = off(可复现性优先,产出走逐字校验);
评分/精读/反驳/归纳类 = on(用户指示:复杂任务开启 thinking;温度仍钉 0.1,
输出仍过确定性校验器 —— thinking 提升判断质量,校验器兜住漂移)。
"""
from __future__ import annotations

import hashlib
import json

LLM_CONFIG_VERSION = "llm_v0.1"

#: 模型注册表(用户指定 11 模型,全部经火山方舟)
#: PROBE 2026-07-09:11/11 可用;thinking 冒烟 doubao-pro/deepseek-v4-pro/glm-5.2 全通
#: (reasoning_content 独立字段)。个体特性已标注。
#: ⚠ G5 卫兵(2026-07-09 修订):reasoning_content **永不进入卡片/档案数据/任何下游消费**
#: (蚂蚁晨报 CoT 泄漏糟粕的防线);平台允许一个**隔离的只读审计视图**展示它(用户裁定:
#: 需要看到各席思路)——必须明确标注"模型推理独白,未经校验,不构成档案内容",且仅从
#: raw/ 审计目录按需读取,绝不写入档案 JSON。
MODEL_REGISTRY = {
    # doubao 家族(Ark 原生,保底可用)
    "doubao-seed-2.0-code":  {"family": "doubao",   "tier": "code",   "note": "代码生成/工具类"},
    "doubao-seed-2.0-pro":   {"family": "doubao",   "tier": "deep",   "note": "主力深层推理;thinking 可开关"},
    "doubao-seed-2.0-lite":  {"family": "doubao",   "tier": "quick",  "note": "高吞吐抽取(0.6s)"},
    "doubao-seed-2.0-mini":  {"family": "doubao",   "tier": "nano",   "note": "超轻量分类"},
    # 第三方(经 Ark 托管)
    "glm-5.2":               {"family": "glm",      "tier": "deep",   "note": "长文档理解;thinking 可开关(慢,6.5s)"},
    "kimi-k2.7-code":        {"family": "kimi",     "tier": "code",   "note": "代码;⚠常开thinking(不支持disable,客户端已降级处理)"},
    "kimi-k2.6":             {"family": "kimi",     "tier": "deep",   "note": "长上下文归纳;回复带md围栏(parse已容错)"},
    "deepseek-v4-pro":       {"family": "deepseek", "tier": "deep",   "note": "强推理/对抗;thinking 可开关"},
    "deepseek-v4-flash":     {"family": "deepseek", "tier": "quick",  "note": "快推理"},
    "minimax-m3":            {"family": "minimax",  "tier": "deep",   "note": "综合"},
    "minimax-m2.7":          {"family": "minimax",  "tier": "quick",  "note": "叙述流畅;⚠常开推理(thinking=False仍产reasoning)→max_tokens须≥800"},
}

#: 任务 → (model, thinking, temperature, max_tokens, fallback)
#  复杂度阶梯:nano(分型) < quick(抽取) < deep(评分/精读/反驳/归纳)
TASK_LLM = {
    # —— 情报层 ——
    "text_event_typing":     {"model": "doubao-seed-2.0-mini", "thinking": False, "temperature": 0.1, "max_tokens": 800,  "fallback": "doubao-seed-2.0-lite"},
    "extraction_quick":      {"model": "doubao-seed-2.0-lite", "thinking": False, "temperature": 0.1, "max_tokens": 1200, "fallback": "deepseek-v4-flash"},
    "borderline_relevance":  {"model": "doubao-seed-2.0-mini", "thinking": False, "temperature": 0.1, "max_tokens": 400,  "fallback": "doubao-seed-2.0-lite"},  # v1 关闭
    "narrative_assembly":    {"model": "minimax-m2.7",         "thinking": False, "temperature": 0.2, "max_tokens": 2000, "fallback": "doubao-seed-2.0-lite"},  # m2.7 常开推理,预算给足
    "regime_brief":          {"model": "doubao-seed-2.0-pro",  "thinking": True,  "temperature": 0.1, "max_tokens": 1500, "fallback": "glm-5.2"},
    # —— 研报管线 ——
    "report_section_extract": {"model": "doubao-seed-2.0-lite", "thinking": False, "temperature": 0.1, "max_tokens": 1500, "fallback": "deepseek-v4-flash"},
    "report_deep_reading":   {"model": "glm-5.2",              "thinking": True,  "temperature": 0.1, "max_tokens": 3000, "fallback": "doubao-seed-2.0-pro"},   # Pass-C
    "cross_report_synthesis": {"model": "kimi-k2.6",           "thinking": True,  "temperature": 0.1, "max_tokens": 2500, "fallback": "doubao-seed-2.0-pro"},
    "relation_extract":      {"model": "doubao-seed-2.0-lite", "thinking": False, "temperature": 0.1, "max_tokens": 1200, "fallback": "deepseek-v4-flash"},    # Pass-R
    # —— 分析师层 ——
    "dimension_scoring":     {"model": "doubao-seed-2.0-pro",  "thinking": True,  "temperature": 0.1, "max_tokens": 4000, "fallback": "deepseek-v4-pro"},   # thinking 吃预算,给足
    # bear 12000:deepseek 思维链**计入** max_tokens(doubao 不计入)——5000 预算被
    # reasoning 吃掉 4.6-5k 致正文空/截断(2026-07-11 v2.9 日跑实测 28/86 次
    # finish_reason=length,结构性非瞬态);观测 reasoning 峰值 ~5k+正文需 ~2-3k
    "bear_rebuttal":         {"model": "deepseek-v4-pro",      "thinking": True,  "temperature": 0.1, "max_tokens": 12000, "fallback": "doubao-seed-2.0-pro"},
    "chief_synthesis":       {"model": "deepseek-v4-pro",      "thinking": True,  "temperature": 0.1, "max_tokens": 3000, "fallback": "glm-5.2"},              # v2
    # —— 工程辅助(非生产链) ——
    "code_assist":           {"model": "doubao-seed-2.0-code", "thinking": False, "temperature": 0.2, "max_tokens": 4000, "fallback": "kimi-k2.7-code"},
}


def llm_config_hash() -> str:
    payload = json.dumps({"version": LLM_CONFIG_VERSION, "registry": sorted(MODEL_REGISTRY),
                          "tasks": TASK_LLM}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


#: 契约路由执行字段与值类型校验的规范定义在 integrity.py(复审#8 Major:
#  三处消费点——本模块/ChainContract.load/平台版本门——共用同一把尺)
from workspace.research.ai_research_dept.engine.integrity import (  # noqa: E402
    ROUTE_EXEC_KEYS, verify_llm_route,
)


def call(task: str, messages: list[dict], **overrides):
    """引擎统一 LLM 门:按任务路由(model/thinking/温度),失败自动降级到 fallback 一次。

    一切调用带 task 名进日志;overrides 仅测试用(生产改路由=改本表=新版本)。
    ⚠ 本函数读**可变全局** TASK_LLM——正式分析师链(run_seat/run_bear)禁用,
    必须走 call_with_config(冻结契约路由,复审#7 B1)。
    """
    return call_with_config(messages, {**TASK_LLM[task], **overrides}, task=task)


def call_with_config(messages: list[dict], route, *, task: str = "contract"):
    """契约执行 LLM 门(复审#7 B1):只接受**显式路由配置**(冻结契约的 routing
    快照),绝不读可变全局 TASK_LLM——加载契约后篡改路由表对执行无效。
    route: Mapping,必须含 model/thinking/temperature/max_tokens(可含 fallback)。"""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))
    from ai_layer.ark_client import ArkClientError, chat

    missing = [k for k in ROUTE_EXEC_KEYS if k not in route]
    if missing:
        raise KeyError(f"route 缺执行字段: {missing}")
    problems = verify_llm_route(route)   # 复审#8 Major:值类型也必须过共享校验
    if problems:
        raise ValueError(f"route 非法: {';'.join(problems)}")
    try:
        return chat(messages, model=route["model"], thinking=route["thinking"],
                    temperature=route["temperature"], max_tokens=route["max_tokens"])
    except ArkClientError:
        fb = route.get("fallback")
        if not fb:
            raise
        import logging
        logging.getLogger(__name__).warning(
            "task=%s primary %s failed -> fallback %s", task, route["model"], fb)
        return chat(messages, model=fb, thinking=route["thinking"],
                    temperature=route["temperature"], max_tokens=route["max_tokens"])
