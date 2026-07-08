# GPT‑5.5 Pro 实现级跨审 #6(re-review)—— MVP 金股 AI re-rank:review #5 三 Blocker 的应用验收(终裁请求)

你在 review #5(REVISE 窄口径:3B,无 Major)把残余定位为 "the successful published decision and its text-coverage proof are still not fully self-contained, sealed, and reconstructible as of decision time"。三项已全部应用。请终裁 SHIP/REVISE(2026-08-04 首前向周期)。

**公开仓库(已推送):** `https://github.com/henrydan111/quant-system` 分支 **`calendar-unfreeze`**
raw:`https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/<path>`

---

## 0. 自审结论(§10 前置)

机械核查:(a) 无 OOS seal 引用/花费;(b) 引用数字仅 NON-FORMAL 锚。**verdict: clean for GPT**。
**一处对你 exact fix 的实现调整(披露,请裁定):** 你的 `write_published_attempt_seal` 排除集为 {seal 自身, fill_record.json};我们**另加 `attempt_manifest.json`**。原因是次序死结:封印若含 attempt_manifest,则 (a) 先封印再翻状态 → 树漂移,验证必败;(b) 先翻状态再封印 → 封印 hash 尚未算出无法写入 attempt_state,写入后又改了被封的文件。attempt_manifest 是纯状态跟踪件,其 started→published 转移由 **ledger 事件**(带 `published_attempt_seal_hash`)保护;决策证据(decision/manifest/scorecards/全部 LLM 产物/coverage record)全在封内。测试 `test_published_seal_roundtrip_and_fill_record_excluded` 钉住三个排除项的语义。

## 1. 逐项应用映射

| 发现 | 应用 | 位置 |
|---|---|---|
| **R5-B1** published seal | `write_published_attempt_seal`(pre-fill,整树逐文件 sha256,排除集见上)→ hash 写入 attempt_state(`published_attempt_seal_hash`)+ ledger `attempt_published` 事件;`verify_published_attempt_seal`(封印缺失=拒 / ledger 无 hash=拒 / 封印≠ledger=拒 / 树≠封印=拒)由 `_published_attempt_dir` 强制——`run_record_fills` 与一切未来 forward-analysis 读者的必经门;fill_record 写后追加自己的 `fill_recorded` ledger 事件(`fill_record_hash`),从不触碰 pre-fill 封印 | `run_forward_cycle.py` |
| **R5-B2** coverage payload | `text_coverage_record.json`(含 `manifest_sha256_by_file` + `coverage_by_source_day` + 带 hash 的 failed 审计)**落盘 attempt 目录**;manifest 字段:`text_coverage_manifest_hash` 更名 **`text_coverage_record_hash`**(=落盘文件的 sha256,无别名混淆)+ 新增 **`text_coverage_record_path`**,双双入 REQUIRED_MANIFEST_FIELDS;你要求的测试已加:record 写入后删除被咨询的历史 manifest → 证据仍从落盘 payload 完整重建(逐 (源,日) 指名 + hash 俱在) | 同上 + `tests/harness/..._refuses_stale_...py::test_coverage_record_is_self_contained_after_source_manifest_loss` |
| **R5-B3** cutoff 对齐 | `dossier_cutoff_ts(decision_time, lookback_days)`(CN naive)= 唯一共享定义;覆盖闸 `start = dossier_cutoff_ts(...).date()`(31 个日历日,不完整首日入窗),dossier 过滤 `cutoff = dossier_cutoff_ts(...)` 同源;回归测试:旧 `lookback−1` 窗口(2026-07-05 起)现在必拒(缺 2026-07-04)、UTC 决策时刻解析出同一 CN cutoff | 同上 + 覆盖测试窗口全部前移一日 |

**验证:** MVP 面 **104/104 green**(harness 54:published 封印 3 个新测试 [roundtrip+fill_record/attempt_manifest 排除语义、篡改 decision.json 拒、无封/无 ledger/hash 不符拒] + 自含性 + cutoff 对齐 + 不完整首日回归)。

## 2. 显式审查问题

1. **排除集裁定**:attempt_manifest.json 出封印、由 ledger 保护 started→published 转移——接受吗?若要求封它,请给出可行的次序方案。
2. **终裁**:除 schtasks(用户侧)与第 2 周期 transition ledger 外,还有 2026-08-04 前必须项吗?若无,请给 SHIP。

**裁定格式:** SHIP / REVISE。
