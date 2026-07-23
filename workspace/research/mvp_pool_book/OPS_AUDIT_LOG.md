# mvp_pool_rerank_v2 · 运维审计日志（FORWARD_PREREG §3：运维修复允许，但必须记录）

Append-only。只记运维动作（拉取工具/调度/告警），决策面（config/prompt/闸门/判定规则）零接触——
触碰决策面 = rerank_v3 重新预注册，不属于本日志。

---

## 2026-07-22 · B1/B2 文本拉取运维加固（用户授权开工；来源：DSA_INTEGRATION_PLAN_v1 Track B）

**B1 — [text_daily_pull.py](../../scripts/text_daily_pull.py) 韧性加固**（闸门语义零变更）：
- 源内熔断：同一 source 连续 ≥2 次异常失败 → 本轮跳过其余天（仍记失败，绝不静默）；
- 收尾重试：冷却（默认 90s）后对每个 异常/被跳过 的 (source, day) 顺序重试一次；truncated
  （翻页上限）不重试；
- manifest 追加审计字段（attempts / breaker_events / retry_pass / partial_run / sources_pulled）——
  纯 additive，runner 两道闸只读 ok/run_ts/window/source_status/failures，不受影响；
- `--sources` 定向补拉：partial run **永不写 pull_manifest_latest.json**，未尝试 source 状态 =
  `not_attempted`（非 ok_*，覆盖闸门不给 credit）；
- B5 契约保持：任何失败 exit 非零；truncated 仍计失败并照常入库（dedup 使重拉免费）。

**B2 — 新增 [text_coverage_preflight.py](../../scripts/text_coverage_preflight.py)（只读预演告警）**：
- 每日 pull 后以"今天=决策日"预演 runner 的两道文本闸（逐字复用 run_forward_cycle 的
  check_pull_manifest + check_text_coverage_history，测试钉住不得本地重写——预演永不与真闸漂移）；
- 失败 → logs/text_coverage_alert_<CN日期>.flag（当日恢复运行则清除）+ exit 1；
  状态落 logs/text_pull/coverage_preflight_latest.json；
- text_daily_pull 以脚本方式全量运行时自动串跑 preflight（子进程，各自 exit code，互不影响）。

**测试**：tests/text/test_text_daily_pull_retry_and_breaker.py（6）+
tests/text/test_text_coverage_preflight.py（6）+ 既有
test_daily_pull_fails_on_partial_source_failure.py 全文件 +
tests/harness/test_forward_refuses_stale_provider_or_text_inputs.py 全文件 = **40 passed**。

**⚠ 首次真实预检结果（2026-07-23 CN）= FAIL，重大发现**：
- pull_manifest_latest.json 不存在 —— **text_daily_pull 从未完成过一次真实全量运行**
  （logs/text_pull/ 只有 4 份 ~07-08 的 bootstrap 清单）；
- 覆盖缺口：**2026-07-09 起全部日期、4 个 source 全缺**（bootstrap 只覆盖到 ~07-08），
  且每天 +1；06-23..27 亦缺（到 8 月决策日会自然滑出窗口，无碍）；
- **后果：不回填则 cycle 202608（决策 ~08-03/04）必被预注册覆盖闸门拒绝**（07-09..07-23
  落在 30 天 dossier 窗内）。
- **恢复路径（前向未起跑 = 仍属 bootstrap 期，合法）**：
  1. `bootstrap_text_coverage_sweep.py --start 20260709`（day-level 清单，闸门认可）；
  2. 恢复每日 `text_daily_pull.py`（schtasks `QuantTextDailyPull` 注册仍待用户授权；
     未注册期间每日人工跑）。
- **未自行执行回填**：机器上有多个长时 python 进程（疑含事故恢复拉取），§6.1/§13 禁止
  Tushare 并行拉取——待用户确认无在途拉取后执行。

**Tier 3 治理**：结构化自评已做（闸门语义零变更逐条核对 + 40 测试全绿）；一轮 GPT 审
待送（送审前需按 §10 push 工作分支）。
