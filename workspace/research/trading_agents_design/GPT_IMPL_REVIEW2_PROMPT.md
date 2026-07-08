# GPT‑5.5 Pro 实现级跨审 #2(re-review)—— MVP 金股 AI re-rank:review #1 全部裁定的应用验收

你在 review #1(裁定 **REVISE:7 Blocker + 5 Major + 4 minor**)审过这套 MVP 实现。我们已应用**全部**发现(零拒绝),并按预注册规则把策略升版 `mvp_pool_rerank_v1 → mvp_pool_rerank_v2`。请验收每项修复是否真正封洞,并裁定能否在 2026-08-04 首个真前向周期前 SHIP。

**公开仓库(已推送,所有链接对着这个分支核对):**
`https://github.com/henrydan111/quant-system` 分支 **`calendar-unfreeze`**
raw 形式:`https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/<path>`

---

## 0. 必须优先检查的量化研究原则(与 review #1 相同)

1. **PIT / 无前视**:文本可见性 `decision_visible_at = max(published, first_ingested)`;前向决策严格早于成交日开盘;任何回填不可能伪装成决策。
2. **fail-closed**:每个闸门失败必须拒绝整个周期,不允许部分成功看起来像成功。
3. **LLM 遏制(C15/C16)**:不可信文本永不成为可执行 prompt 内容;LLM 永不输出最终分/动作;幻觉证据永不解锁分数。
4. **D3 / spent-OOS**:`spent_oos_end=2026-02-27` 不变;历史 +8.4%/0.46 基线保持 NON-FORMAL,未迁移为部署证据(你的 m4)。
5. **可复现性**:每个决策的全部输入按内容 hash 钉入 manifest。

## 1. 自审结论(§10 前置,已完成)

机械核查:(a) 全 diff 无任何 OOS seal 引用/花费(纯 forward-only);(b) 所有引用数字对照 CLAUDE.md §3 陈旧标志——仅引 NON-FORMAL 基线锚,无 E-wave/eps 部署数字。**verdict: clean for GPT**。
**对你裁定字面的 4 处偏离(全部披露,请逐条裁定):**

- **D1(M1 迁移路径)**:你建议 archive+re-pull;我们改为**就地重算**(原始列全在库内)——re-pull 会把全部行的 `first_ingested_at` 重置为今天,摧毁 7 月 PIT 可见性戳(严格的 PIT 回退)。原库已归档 `data/text_store_pre_m1_archive/`;实测清除 59 行 incidental 重复(M1 前提被证实)。
- **D2(schema 校正)**:你给的 research_report 哈希基含 `inst_name`;实际列名为 **`inst_csname`**,按真实 schema 落地。
- **D3(B1+ 加固,超出裁定字面)**:你的 B1 要求证据句落地于"可见上下文";初版实现用 digest+spans,自审发现残余通道——quick 层幻觉事件进 digest 后可被 deep 引用即"落地"。已改为落地基 = **dossier 原始文本**(spans ⊂ dossier,合法引用不受影响;纯幻觉被拦),score_v2 prompt 同步要求逐字引 spans。此变更引发 config hash 更新(prereg 已同步)。
- **D4(m1 实现)**:重试覆盖 429/5xx **加传输层异常**(ConnectionError/Timeout 同类瞬态),退避 3s(你的示例 2s);仍严格一次、schema 违规不重试。

irm_qa 哈希基按你的 dict 排除答案 `a`——权衡已注释在代码里(同 pub_time 的就地答案编辑=同对象;真修订带新 pub_time=新行)。你的 m2(load_text 全文件读)按裁定不动,记为 news 扩展前的 backlog。

## 2. 逐项应用映射(请对着 raw 链接核对)

| 发现 | 应用 | 位置 |
|---|---|---|
| **B1** payload 渲染 | 不可信文本只以 `json.dumps` payload 进 user 消息,SYSTEM 声明 untrusted;{PLACEHOLDER} 插值废除,prompts 升 v2 | `src/ai_layer/prompt_render.py` · `src/ai_layer/prompts/extract_v2.txt` / `score_v2.txt` |
| **B1** scorecard 硬化 | 未知顶层/条目字段 HARD-FAIL;证据逐字落地(空白归一,≤160 字)否则 NO-SCORE,罚分同样适用;签名强制 `evidence_context` | `src/ai_layer/scorecard.py` |
| **B2** C8 | `tushare_to_qlib_canonical`(upper)唯一门;MVP 面手搓转换清零 | `src/data_infra/provider_metadata.py` + 两个 runner |
| **B3** tilt/覆盖率 | cohort 均值中心化 + `min_scored_floor_pct=0.80 → disable_ai_overlay_for_cycle` | `config/ai_layer/rerank_v2.yaml` + 两个 runner |
| **B4** 前向 runner | decision_id=sha256(cycle\|time\|config\|git)[:16];cycles/<cycle>/ append-only(存在即拒);tmp-dir+原子 rename;manifest 全输入 hash;硬闸全部在 LLM 调用**之前** | `workspace/research/mvp_pool_book/run_forward_cycle.py` |
| **B5** 日拉取 | 每次落 manifest JSON;任一源失败 exit 1 | `workspace/scripts/text_daily_pull.py` |
| **B6** 池锚 | 最新月无激活=raise;有后月无到期=raise | `src/data_infra/golden_stock_universe.py` |
| **B7** 9 测试 | 22 个新测试,全部先 RED 语义后 GREEN | `tests/contracts/` ×2 · `tests/ai_layer/` ×3 · `tests/text/` ×1 · `tests/harness/` ×3 |
| **M1/M2** | `SOURCE_HASH_COLUMNS` 钉板 + `adapter_contract_hash` 列 + 同目录 tempfile+os.replace 原子写;迁移见 D1 | `src/data_infra/text_store.py` · `workspace/scripts/migrate_text_store_m1.py` |
| **M3** | `df.attrs['truncated']`;日拉取记为失败 | `src/data_infra/fetchers/__init__.py` |
| **M4** | portfolio_caps 声明+运行时断言(0.04/0.32/0.64/0.36) | `rerank_v2.yaml` + 两个 runner |
| **M5** | decision.json 带 fill_plan;`--record-fills` 事后补录停牌/一字涨停不可买,append-only | `run_forward_cycle.py` |
| **m1** | 一次有界重试(见 D4) | `src/ai_layer/ark_client.py` |
| **m3** | veto/tilt/行业-cap 三通道分账审计字段 | `src/portfolio_risk/rank_book_construction.py` |
| **m4** | 非正式标注保持;基线数字未迁移 | `project_state.md` 2026-07-08d |

**验证:** MVP 面 68/68 green + provider_boundary/suspension 12 green;改造后链路两次真实 LLM 冒烟 exit 0(5 名 cohort mean 32.0 / 3 名 dossier-落地 finals 16-47,证据未被误清零;caps 断言过)。**预注册:** `FORWARD_PREREG.md` 修订 v2(起跑前合法),`config_hash_v2: 12724e20f1f78b55`,覆盖率停用月计入判定分母。

## 3. 显式审查问题

1. **B4 闸门次序与完备性**:`run_decision` 里是否存在任何在 LLM 花费之后才可能失败并留下半决策状态的路径?staging tmp-dir + `os.replace`(Windows 目录 rename)+ 存在即拒,append-only 是否闭合?`--record-fills` 的补录语义有无污染决策记录的通道?
2. **B1+(D3)裁定**:落地基从 digest+spans 收紧为 dossier 原文——是否引入意外的过严(deep 只见 spans[:1200],dossier 落地是否恰好为超集)或残留通道(digest 概括句不再可作证据,是否会系统性压低 mgmt_clarity 类维度)?
3. **B3 分母**:覆盖率 `scored/floor_names`、cohort 均值只取 scored——no_text 名字 tilt=0 但仍在 overlay 候选内,这个组合有无系统性偏置?
4. **M1 哈希基**:irm_qa 排除 `a` 的修订盲点(同 pub_time 就地改答案)在 C1 语义下可接受吗?`adapter_contract_hash` 是否足以审计未来基变更?
5. **D1 迁移路径**:就地重算 vs 你建议的 re-pull——认可 PIT 戳保全的理由吗?
6. **前向起跑清单**:除 schtasks(用户侧待授权)外,还有什么是 2026-08-04 前必须补的?

**裁定格式:** SHIP / REVISE(逐条 Blocker/Major/minor,给可执行修复)。逐条对 D1–D4 表态。
