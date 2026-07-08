# GPT‑5.5 Pro 实现级跨审 #3(re-review)—— MVP 金股 AI re-rank:review #2 全部裁定的应用验收

你在 review #2(裁定 **REVISE:6 Blocker + 5 Major**,并确认 R1 的 B2/B3/B5/B6/M1/M2/m3/D3 闭合)指出核心残余风险:"LLM-influenced decision attempt can still be partially executed, lost, retried, or incompletely reconstructed because attempt logging and manifest hashing are not yet evidence-grade"。我们已应用**全部** 6 Blocker + Major 1/2/4/5(Major 3 按你的裁定记为第 2 周期前必补,已入 prereg §5)。请验收并裁定能否 SHIP。

**公开仓库(已推送,对着这个分支核对):**
`https://github.com/henrydan111/quant-system` 分支 **`calendar-unfreeze`**
raw 形式:`https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/<path>`

---

## 0. 自审结论(§10 前置,已完成)

机械核查:(a) 全 diff 无 OOS seal 引用/花费(forward-only 不变);(b) 引用数字仅 NON-FORMAL 基线锚,与 CLAUDE.md §3 staleness 标志无冲突。**verdict: clean for GPT**。本轮无对裁定字面的偏离——你给的 exact replacement 全部按语义落地(个别标识符名不同)。一处自证:**C8 lint 测试在本轮抓到了我在新 runner 里写的手搓 `.replace('.','_')`**(R1-B7 的测试起了作用)。

## 1. 逐项应用映射

| 发现 | 应用 | 位置 |
|---|---|---|
| **R2-B1** 罚分证据 | `_evidence_ok`(非空 + 全部逐字落地)同一规则适用 factor 与 penalty;`all([])` 通道死;`_invalid_evidence` 内部标记废除(wire 上出现 = unknown field 即拒);score_v2 penalty schema 强制 `evidence_spans`,无证据风险显式导向 `risk_flags`(仅审计);`validate` 收纯结构/遏制,grounding 全在 `compute` | `src/ai_layer/scorecard.py` · `src/ai_layer/prompts/score_v2.txt` |
| **R2-B2** attempt 台账 | 纯闸门全过后、**任何 LLM 花费前**:`cycles/<cycle>/attempt_<decision_id>/` mkdir(exist_ok=False)+ `attempt_manifest.json(status=started)` + `attempts_ledger.jsonl` 追加;逐名 `names/<code>/extract_request/extract_response_raw/score_request/score_response_raw/validated_scorecard.json` **边跑边原子落盘**;异常→`status=failed`(stage/error)且目录永不删除;同 cycle 重跑必须 `--new-attempt <reason>`(published 存在则无条件拒) | `run_forward_cycle.py`:`ensure_attempt_allowed` / `run_decision` / `_run_attempt_body` |
| **R2-B3** 全 manifest | `REQUIRED_MANIFEST_FIELDS`(33 字段)+ `build_manifest` 缺/空即拒(CODE-enforced);含你列的全部字段:provider/trade_cal/qlib 日历/factor registry 文件 sha、7 因子表达式 hash、golden events hash、industry map hash、`quant_scores_hash`、prompt/model id、per-source in-window 行 hash、逐名 dossier/raw-LLM(extract+score 分列)/validated-scorecard hash、overlay_audit/decision/scorecards 产物 hash;**`git_worktree_clean` 为硬闸**(porcelain 非空拒绝决策) | 同上:`build_manifest` / `check_worktree_clean` |
| **R2-B4** as-of 上界 | `latest_allowed_asof = previous_open_day(fill_date)`(严格早于);`check_provider_asof_bound` 闸 + `quant_composite_for_pool(pool, asof_end=...)` 函数内二次拒绝 | `run_forward_cycle.py` + `run_ai_rerank_dryrun.py` |
| **R2-B5** CN 时区 | `decision_time = pd.Timestamp.now(tz="Asia/Shanghai")`;09:25 开盘线 CN 墙钟(**UTC 机器伪装开盘前的回归测试已钉**:02:00 UTC=10:00 CN 拒);text_store 全时间戳 CN 墙钟语义(`to_cn_naive`,aware 输入转换、naive 视为 CN);pull manifest `run_ts` 带 +08:00 | `run_forward_cycle.py` · `src/data_infra/text_store.py` · `workspace/scripts/text_daily_pull.py` |
| **R2-B6** 缺源硬拒 | store 文件缺失拒(`load_text(require_exists=True)` + runner 预检);pull manifest 增 `source_status`(`ok_zero_rows/ok_nonzero_rows/failed` —— 空文件合法、缺文件不合法);`check_pull_manifest(required_sources)` 校验每个 required source 有 ok 状态 | 同上三处 |
| **R2-Major-1** | 正式 migration manifest `data/text_store/migration_manifest.json`:old/new store hash、行数前后、去重数、**`first_ingested_at_changed_count=0` / `decision_visible_at_changed_count=0`**(迁移脚本内联结构性证明,非 0 即 abort) | `workspace/scripts/migrate_text_store_m2_dual_hash.py` |
| **R2-Major-2** | 双哈希落地:`object_id_hash`(identity)/`content_hash`(identity+**归一化内容**,irm_qa 的 `a` 计入)——同 object 改内容=revision 追加行,旧行与旧 `first_ingested_at` 冻结;从 pre-M1 归档重迁移:46 行为归一化吸收的格式噪声、**2 行真答案修订恢复为 revision 行**、PIT 戳零变动 | `src/data_infra/text_store.py` |
| **R2-Major-4** | 四项 caps 全部 `ForwardGateError` 显式闸(无 bare assert);observed 值写入 overlay_audit + manifest | `run_forward_cycle.py` |
| **R2-Major-5** | manifest 测试钉 `EVIDENCE_GRADE_FIELDS` 合约集(任一字段掉出 REQUIRED 集即测试断)+ 缺字段/空字段拒绝路径;harness 24 测试:attempt 台账 7(published 永拒/failed 阻默重/started 阻默重/显式 new-attempt 放行)+ manifest 5 + 闸门 12(含 as-of 上界、UTC 伪装、per-source status、脏工作树) | `tests/harness/` ×3 |
| **R2-Major-3** | 按裁定**未实现**(首周期现金起步非 blocker),记入 prereg §5 已知缺口为**第 2 周期前必补**的 transition fill ledger | `FORWARD_PREREG.md` §5.5 |
| **R2-minor** | forward 逐名记录 `reply_pure_json` 审计位(raw response 本就全量落盘);`load_text` 全文件读维持(news 扩展前 backlog);基线数字维持 NON-FORMAL | `run_forward_cycle.py` |

**config hash 重钉**(score_v2 罚分 schema 变更,仍在起跑前):`config_hash_v2: 5c8a462e1c5500b3`(prereg §4 同步)。**验证:** MVP 面 **79/79 green**;改后链路 3 名真实 LLM 冒烟(新 penalty schema)通过。

## 2. 显式审查问题

1. **R2-B2 验收**:attempt 预留在纯闸门之后、LLM 之前,粒度是否足够?`ensure_attempt_allowed` 的三态(published 永拒 / started·failed 阻默重 / `--new-attempt` 放行)+ ledger 追加,是否还留有 retry/selection 通道(例如删目录重跑——文件系统层无防护,是否需要 ledger 与目录双重核对)?
2. **R2-B3 验收**:`REQUIRED_MANIFEST_FIELDS` 33 字段对照你的清单还有缺吗?`git_worktree_clean` 硬闸的粒度(porcelain 全量非空即拒)是否过严到不可运维(如 untracked 日志文件)——若需豁免,正确的白名单形状是什么?
3. **R2-B1 验收**:罚分证据规则与 factor 完全一致(非空+全逐字)是否正确,还是罚分应允许"部分 span 落地即计"(当前:一条幻觉 span 毒化整条 entry,factor 与 penalty 同)?
4. **时区残余**:store 内 naive-CN 墙钟存储(而非 tz-aware 存储)+ `to_cn_naive` 边界转换,可接受吗?
5. **起跑清单终检**:除 schtasks 与 Major-3(第 2 周期项)外,2026-08-04 前还有必须项吗?

**裁定格式:** SHIP / REVISE(逐条 Blocker/Major/minor,给可执行修复)。
