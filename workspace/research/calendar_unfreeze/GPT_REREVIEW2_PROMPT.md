# GPT 5.5 Pro re-review prompt — Calendar Unfreeze Plan v3 (Round 3)

Status: ready to send AFTER `git push` of branch `trading-agents-design`.

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. This is ROUND 3. Round-1 verdict: REVISE (2 Blockers B1/B2 + M1-M4 + m1-m4; all 10 accepted → plan v2). Round-2 verdict: REVISE, converging — you judged 8/10 findings RESOLVED, no new Blockers, B1/M2 PARTIALLY RESOLVED with the gaps concretized as two new Majors (M6: the D3 live-policy clamp lacked a resolver for old policies without the additive spent_oos_end field; M7: executable hardcoded-policy cleanup in validation_steps.py:956/1112 was scheduled AFTER publish, contradicting the pre-publish no-global-policy wall) plus three add-on requirements (sidecar set discovered from manifest/tree, not a hardcoded list; Phase-1 caught-up raw data is not a research surface until Phase 2 gates are green; retention pruning fails closed if the reference scan cannot enumerate every reference store). All were accepted (none declined) → plan v3.

Your Round-3 mandate is NARROW: (1) verify M6, M7, and the three add-ons are adequately resolved in v3; (2) scan whether the v3 deltas introduce any NEW problem. Do not re-litigate items you marked RESOLVED in Round 2 — the v3 text outside the deltas listed below is unchanged from the v2 you already reviewed.

REPO (public — raw fetch may fail; the embedded text below is authoritative)
https://github.com/henrydan111/quant-system   (branch: trading-agents-design)
Raw file form: https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/<path>
Plan v3: workspace/research/calendar_unfreeze/UNFREEZE_PLAN.md · Self-review (Round-3 preflight): workspace/research/calendar_unfreeze/SELF_REVIEW.md · CLAUDE.md for the §3 invariants.

SELF-REVIEW PREFLIGHT (Round 3) — verdict "clean for GPT re-review". Faithfulness: M6 resolver matches your three-branch replacement text incl. the three required CI tests; M7 moved all executable policy/window constants into Phase 2 (new item 2a) with Phase 4 downgraded to verification-only (residual-hardcode assertion + dual-policy smoke; only non-executable error text may remain for Phase 4). New-content check: the frozen-without-field fallback (clamp to policy.calendar_end_date) is equivalent to the status quo under the old frozen policy (live end == calendar_end_date), so it relaxes nothing.

V3 DELTAS (authoritative, verbatim from the v3 plan; everything else is unchanged v2 text)

--- Delta 1 · §1-D3 new item 8 (M6) ---
8. 政策边界解析器（Round-2 M6）：钳制代码统一调用 resolve_spent_oos_boundary(policy, calendar)，解决"闸代码已合并、live 还是不含新字段的老冻结政策"的过渡态：
   - policy 含 spent_oos_end → 直接使用（并与 provider 日历互验；fresh_holdout_start 同）；
   - policy 缺该字段且 frozen == true → spent_oos_end = policy.calendar_end_date，fresh_holdout_start = 其后第一个交易日；若 provider 日历恰止于 spent_oos_end（老冻结态），则不存在新鲜 holdout 窗口，一切 post-spent 读取 fail-closed；
   - frozen == false 或字段缺失/非法的其他情形 → fail-closed（直到 max_calendar_lag_days 强制检查落地且测试绿）。
   CI 必测：老 frozen_20260227_system_build（无新字段）默认读钳到 2026-02-27；新 thaw_step1 政策在 provider_calendar_end > spent_oos_end 时默认读仍钳到 spent_oos_end；解冻政策的 spent_oos_end 缺失/非法 → fail-closed。

--- Delta 2 · Phase 2 retitled "发布前墙：D3 机械闸 + 政策贯通 + 耦合审计（B1/M2/M4/M6/M7）"; item 2 now reads "D3 机械闸落地（§1-D3 条目 1-6 + 条目 8 解析器的实现 + 测试）"; new item 2a (M7) ---
2a. 可执行硬编码全部在本阶段清除（Round-2 M7）：validation_steps.py:956/1112 的 calendar_policy_id 改为从 prescription/配置/artifact 记录流入；promotion_evidence/revalidation 的窗口末端改为从记录的 calendar_policy_id（经条目 8 解析器）或显式 seal 读取。Phase 2 完成后，不得残留任何可执行的政策/窗口常量（仅报错文案等非执行文本可留待 Phase 4）。

--- Delta 3 · Phase 4 retitled "发布后换绑与验证（验证性质，不再含可执行常量清理）"; item 2 replaced (M7) ---
2. 硬编码残留断言（M7 后 Phase 4 仅做验证）：断言 legacy fixture / 显式旧-artifact 回放测试之外无任何可执行的 frozen_20260227_system_build 残留（可执行清理已全部在 Phase 2 完成）；仅清理非执行文本（如 event_driven/__init__.py:489 报错文案）；对老 artifact 政策与新 thaw_step1 政策各跑一次正式验证 smoke。

--- Delta 4 · Phase 1 new item 7 (add-on 2) ---
7. 运行纪律（Round-2 附加要求）：在 Phase 2 闸全绿之前，追平后的原始层不是研究面——期间禁止任何研究 notebook / dashboard 刷新 / 因子扫描 / 临时 raw·PIT 读取触碰 2026-02-27 之后的新数据；追赶分支仅作运维用途。

--- Delta 5 · Phase 3.2(c) sidecar clause (add-on 1) ---
侧车成员矩阵（B2）：对 all_stocks / st_stocks / csi300/500/1000 及一切 universe/tradability 侧车——侧车集合由 provider 树/manifest 枚举发现，不允许仅按硬编码清单——把区间表物化为旧日历上的逐日成员矩阵，断言 ≤2026-02-27 每一天与旧 live 完全相等。

--- Delta 6 · Phase 5.3 retention clause (add-on 3) ---
修剪前必须完成对全部引用存储（approvals / 五注册表 evidence / seal store / frozen selection / deployment-gate 记录）的完整扫描；扫描无法枚举任一引用源时，修剪 fail-closed。

--- Delta 7 · Risk table, two new rows ---
| 政策"脑裂"过渡态（Round-2 首要残余风险）：闸读 live 政策但新旧政策字段/硬编码未解析齐 | D3 条目 8 解析器（老政策无新字段 → 钳到其 calendar_end_date；非法即 fail-closed）+ M7 可执行硬编码全部于 Phase 2 清除 + 双政策 smoke（Phase 4.2） |
| Phase 1-2 间隙：raw 已追平、闸未绿、老 provider 仍 live | Phase 1.7 运行纪律：追平后的原始层非研究面（受认可 door 读的仍是老 provider，直读被既有 lint 封死） |

--- Delta 8 · New §7 Round-2 disposition table (M6/M7/add-ons 1-3 all accepted, 0 declined) ---

RE-REVIEW QUESTIONS (Round 3, narrow scope)
1. M6: does resolve_spent_oos_boundary close the split-brain transition state? Judge each branch: (a) is the frozen-without-field fallback to policy.calendar_end_date safe in BOTH sub-states — old provider still live (live end == calendar_end_date, no fresh window, all post-spent fail-closed) AND hypothetically a thawed provider paired with an old-format policy (can that pairing even occur given the manifest must declare the policy id and the new policy carries the fields)? (b) are the three CI tests sufficient, or would you add a fourth (e.g. manifest-declares-new-policy but YAML file lacks the field)?
2. M7: with executable hardcodes cleared in Phase 2.2a and Phase 4 reduced to assertion + dual-policy smoke, is the ordering contradiction fully resolved? Anything still executable that the plan leaves post-publish?
3. Add-ons 1-3: adequately captured?
4. New-issue scan on the deltas only: e.g. does the Phase 1.7 operational-only rule conflict with daily QA needing to read the caught-up raw layer (verify_database) before Phase 2? Does clamping via the item-8 resolver interact correctly with legacy artifact REPLAY (which must use the recorded old policy, where the fallback yields 2026-02-27 — is that the intended replay semantics)?
5. Final: is v3 ready to execute (SHIP), or list exactly what remains.

OUTPUT FORMAT
- Per item (M6, M7, add-on 1/2/3): RESOLVED / PARTIALLY RESOLVED / NOT RESOLVED with the exact remaining gap.
- New issues ranked Blocker / Major / Minor with offending text quoted and exact suggested replacement.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.
```
