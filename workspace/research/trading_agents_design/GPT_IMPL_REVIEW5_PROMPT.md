# GPT‑5.5 Pro 实现级跨审 #5(re-review)—— MVP 金股 AI re-rank:review #4 三 Blocker + 两 Major 的应用验收(终裁请求)

你在 review #4(REVISE:3B+2M)把残余风险定位为 "terminal failed/abandoned attempts and bootstrap/coverage evidence are not yet fully content-addressed"。全部已应用。请终裁 SHIP/REVISE(2026-08-04 首前向周期)。

**公开仓库(已推送):** `https://github.com/henrydan111/quant-system` 分支 **`calendar-unfreeze`**
raw:`https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/<path>`

---

## 0. 自审结论(§10 前置)

机械核查:(a) 无 OOS seal 引用/花费;(b) 引用数字仅 NON-FORMAL 锚。**verdict: clean for GPT**。
**一处超出裁定字面的加强(披露):** R4-B1 你的 exact fix 要求"重试前验证 terminal manifest 存在 + ledger hash 与封印文件 hash 匹配";我们**额外重验产物树**(`verify_terminal_attempt_seal` 把当前树逐文件重哈希与封印内 `artifact_hashes` 比对)——否则"改 artifact 不改封印文件"仍逃逸(封印文件 hash 仍与 ledger 匹配)。测试 `test_modified_artifact_after_sealing_refuses_retry` 钉住。

## 1. 逐项应用映射

| 发现 | 应用 | 位置 |
|---|---|---|
| **R4-B1** 终态封印 | `hash_attempt_tree`(整树逐文件 sha256,封印文件自身除外)→ `write_terminal_attempt_manifest`(cycle/id/status/时刻/reason/artifact_hashes)→ 返回封印文件 hash 记入 ledger 事件(`attempt_failed` / `attempt_abandoned` 均带 `terminal_attempt_manifest_hash`);`ensure_attempt_allowed` 重试前对每个既往终态 attempt 执行 `verify_terminal_attempt_seal`:无封印=拒(unsealed)、ledger 无 hash=拒、封印≠ledger=拒(tampered)、**树≠封印=拒(超字面)** | `run_forward_cycle.py` |
| **R4-B2** abandon fail-closed | `_pid_alive` 无 psutil 即 `ForwardGateError`(unverified 永不进入可重试终态);manifest 无 pid 亦拒;活 PID 拒;成功路径记 `pid_liveness_at_abandon="dead_verified"`;abandon 同样走 R4-B1 封印;`psutil==7.2.2` 入 requirements.txt | 同上 + `requirements.txt` |
| **R4-B3** 覆盖内容寻址 | coverage record = `manifest_sha256_by_file`(每个窗口相交的 manifest 全部钉 hash,含失败的)+ `coverage_by_source_day`(每 (源,日)→覆盖 manifest 名)+ `failed_manifests_recovered_later` 带 sha256;决策 manifest 的 `text_coverage_manifest_hash` 对整个 record 取 hash(传递性钉住);**bootstrap 退役 min..max 行推导版**(checker 对 `bootstrap:true` 且无 `coverage_by_day` 的 manifest 零记分,测试钉住),替换为**真实逐日 API 实扫**:[bootstrap_text_coverage_sweep.py](workspace/scripts/bootstrap_text_coverage_sweep.py) 逐 (日,源) 实际查询并记录 `ok_zero_rows/ok_nonzero_rows/failed` + query_log + query_log_hash;实跑 2026-06-28..07-08 每源 11/11 天 ok(irm_qa_sz 的零行日如实 ok_zero_rows,非区间近似);failed 日不得分(测试钉住) | 同上 + sweep 脚本 |
| **R4-Major-1** | prereg §4 陈旧 hash(5c8a462e…)修正为 `07492b544b52288c`(与头部 standalone pin 一致);新增一致性测试:`_load_pinned_hash()` == 从 live rerank_v2.yaml+两 prompt 重算的 hash,且 prereg 全文正则搜出的所有 `config_hash_v2` pin 必须恰为单值——冻结工件漂移或 pin 矛盾即测试断 | `FORWARD_PREREG.md` + `tests/harness/..._refuses_stale_...py::test_prereg_pinned_hash_matches_frozen_config` |
| **R4-Major-2** | `dossier_hashes[code] = sha256_text(dossier)` 移至 no_text 分支前——每个 floor 名字(含 no_text=sha256(""))都在 `dossier_hash_by_ts_code` 中 | `run_forward_cycle.py` |

**验证:** MVP 面 **98/98 green**(harness 42:终态封印 5 个新测试 [unsealed 拒/tampered 拒/树改动拒/roundtrip/密封重试放行] + 覆盖内容寻址 4 个 [sha256 逐 manifest/逐(源,日)指名/day-level bootstrap 记分/coarse bootstrap 与 failed 日不记分] + prereg 钉板一致性)。

## 2. 显式审查问题

1. **R4-B1 验收**:树重验(超字面)有无副作用遗漏——例如 published attempt 是否也应有等价封印(当前 published 的完整性由 manifest.json 的产物 hash + `llm_artifact_hash_by_ts_code` 承担,未另设 terminal 封印)?
2. **R4-B3 验收**:bootstrap 实扫的"当日重查"语义——6 月末/7 月初的行早已在库(原 first_ingested_at 保留),扫描重查只证明"今天查询该历史日成功",不是"当日实时查询成功"。对 fixture 时代的 source-availability 证明,这个语义可接受吗(visibility 仍由 first_ingested_at 独立把关)?
3. **终裁**:除 schtasks(用户侧)与第 2 周期 transition ledger 外,还有 2026-08-04 前必须项吗?若无,请给 SHIP。

**裁定格式:** SHIP / REVISE。
