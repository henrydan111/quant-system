# GPT‑5.5 Pro 实现级跨审 #4(re-review)—— MVP 金股 AI re-rank:review #3 三 Blocker + 三 Major 的应用验收

你在 review #3(REVISE:3 Blocker + 3 Major)把残余风险定位为 "evidence-grade attempt integrity: a `started` or partial LLM attempt can be bypassed or incompletely hashed, and a latest-clean text pull can mask missing source coverage inside the 30-day decision window"。三洞已全部闭合。请验收并给出 SHIP/REVISE 终裁(2026-08-04 首前向周期)。

**公开仓库(已推送):** `https://github.com/henrydan111/quant-system` 分支 **`calendar-unfreeze`**
raw:`https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/<path>`

---

## 0. 自审结论(§10 前置)

机械核查:(a) 无 OOS seal 引用/花费;(b) 引用数字仅 NON-FORMAL 锚。**verdict: clean for GPT**。
**一处对你裁定字面的偏离(D1,请裁定):** 你的 `check_text_coverage_history` 参考实现里,任何 `ok=False` 的历史 manifest 都进 `bad` 并触发 raise——即使其窗口日期已被其后重叠的干净拉取完全重新覆盖。我们改为:**失败 manifest 不自动毒化闸门,仅当存在"未被任何 ok manifest 覆盖的窗口日期"才拒绝**;失败 manifest 记入返回记录的 `failed_manifests_recovered_later`(审计保留)。理由:4 天回看 + content_hash 幂等去重的设计本意就是"次日干净拉取重新覆盖昨日失败";按字面实现,一次历史失败会使该周期**永久死锁**(没有任何合法途径"洗掉"一个失败 manifest)。测试 `test_failed_manifest_recovered_by_later_clean_pull_passes` 钉住此语义。

## 1. 逐项应用映射

| 发现 | 应用 | 位置 |
|---|---|---|
| **R3-B1** started 不可越过 | `TERMINAL_RETRYABLE={failed, abandoned_due_to_crash}` / `TERMINAL_FINAL={published}`;`ensure_attempt_allowed`:published 无条件永拒 → **非终态(started)无条件拒,`--new-attempt` 也不放行** → 终态失败/放弃 + 显式 `--new-attempt` 才放行;`load_attempt_index` **双重核对**:目录无 manifest=torn 拒、ledger 有记录而目录消失=证据违规永拒(ledger 成为 start-gate);唯一出口 `--abandon-started-attempt <id>`(要求非空归因;attempt_manifest 记录 PID,psutil 可用时活进程拒绝 abandon,不可用时记 `pid_liveness_unverified`;产物永久保留;ledger 记 `attempt_abandoned`) | `run_forward_cycle.py` |
| **R3-B2** 全产物哈希 | `collect_llm_artifact_hashes` **目录扫描**(非成功路径信任):ok 需全 5 件、失败至少 failure.json 且部分产物(如已落盘的 extract/score raw response)一并钉住、no_text 显式 `llm_attempted=False`;缺件 `ForwardGateError` 拒发布;`raw_llm_response_hash_by_ts_code` 退役 → `llm_artifact_hash_by_ts_code`(测试:成功/解析失败/scorecard 违规/no_text 四态 + 缺件拒 + 消失目录拒) | 同上 + `tests/harness/test_forward_manifest_contains_input_hashes.py` |
| **R3-B3** 覆盖史闸门 | `check_text_coverage_history`:30 天窗内**每个自然日 × 每个 required source** 必须被某 ok manifest 的 `ok_` 状态覆盖,缺口拒周期(拒绝方案,非"缺口→overlay 停用"替代——已预注册);**bootstrap manifests**(per-source 独立窗口,一源永不借另一源的窗口)覆盖 manifest 纪元前初始摄入(2026-06-01 起,方法与"visibility 仍由 first_ingested_at 独立把关"记录在 manifest 内);coverage 记录 hash+窗口+源列表入决策 manifest | 同上 + `workspace/scripts/write_text_bootstrap_manifest.py` |
| **R3-Major-1** | `text_store_migration_manifest_hash` + `text_store_migration_id` 入 REQUIRED_MANIFEST_FIELDS;决策时 migration manifest 缺失=拒 | `run_forward_cycle.py` |
| **R3-Major-2** | worktree 白名单=`logs/`、`workspace/outputs/`、`.env` 三者**仅限**;混合脏(白名单外任一行)仍拒;rename 条目按目标路径判定 | 同上 + 测试(config/src/tests/prereg 逐一验证不豁免) |
| **R3-Major-3** | `_MIN_SPAN_CHARS=8` + 泛词黑名单 `{公司,公告,投资者,互动易}`;score_v2 prompt 注明 8-80 字、泛词不算 → config hash 重钉 `07492b544b52288c`(prereg §4 同步,仍在起跑前) | `src/ai_layer/scorecard.py` · prompts |

**验证:** MVP 面 **90/90 green**(harness 34:attempt 纪律 9 + manifest/产物 8 + 闸门/覆盖 17);span 收紧后 3 名真实 LLM 冒烟通过。REQUIRED_MANIFEST_FIELDS 33→38,`EVIDENCE_GRADE_FIELDS` 测试合约集同步(含 `raw_llm_response_hash_by_ts_code` 必须不在集合内的负断言)。

## 2. 显式审查问题

1. **D1 裁定**:失败-后被重覆盖不毒化的语义,接受吗?若不接受,给出不死锁的替代(如何"清算"一个历史失败 manifest)。
2. **R3-B1 验收**:abandon 出口的攻击面——PID 复用(旧 PID 被新无关进程占用 → psutil 报 alive → 无法 abandon,只能等)与 psutil 缺失时的 attestation-only 降级,可接受吗?
3. **R3-B3 验收**:bootstrap manifest 用"店内 nominal 源日期 min..max"声明覆盖窗——一个范围内零行的日子会被连续窗口声明覆盖(近似)。对 fixture 时代可接受吗,还是要求逐日核证?
4. **终裁**:除 schtasks(用户侧)与第 2 周期 transition ledger 外,2026-08-04 前还有必须项吗?

**裁定格式:** SHIP / REVISE。
