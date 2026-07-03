# 交接 Prompt — 瞬态深槽(slot_depth=16)scoped 构建,解锁 #11 + GARP 3年复合项

> 把本文件全文作为另一个 Claude Code session 的初始指令。工作目录 E:\量化系统。

---

你在 E:\量化系统(A 股量化系统 repo)。先按 CLAUDE.md §1 刷新上下文(project_state.md / config.yaml /
src/system.md / data_dictionary.md / data_tracker.md),并读:
- `workspace/research/idea_sourcing/guorn/DEPLOYED20_REPLICATION_REPORT.md`(战役总结,你的任务在 §8)
- `workspace/research/idea_sourcing/guorn/UNLOCK_8Q_FACTORS_PLAN.md` 的 Route A(被 depth-9 取代的部分不用管,
  **rung-6 瞬态深槽机制**是你要复用的先例)
- `workspace/scripts/_build_deepslot_scoped.py`(rung-6 已验证的构建驱动)
- 记忆 `feedback_provider_build_disk_hazard`(⚠ 必须 scoped:上次未限定范围吃掉 1TB 磁盘)

## 任务

构建一个**临时的** slot_depth=16 staged Qlib provider(不发布、不碰 live provider),范围严格限定到
下述字段×universe,然后从它计算 4 个因子 frame 存为 parquet,最后**删除 staged 目录**。

### 目标因子(为什么需要 16 深度)

1. `波动率_季度指标(FCFTTM_重算GR%PY,12)`(#11 value_FCF_非金sm 的 w3 主排名项):FCF TTM 同比增速的
   12 季标准差 → 增速序列要 12 个点、每点回看 4 季 → 单季槽 q0..q15。
   - FCFQ_重算 = 经营现金流量净额(单季) − 购建固定资产…支付的现金(单季) + 处置固定资产…收回的现金净额(单季)
     + 折旧和摊销(单季)。D&A 单季走 **cum 相邻差分**(报告节奏半年;参照
     `workspace/scripts/_verify04_upgrade.py` 的 `da_sq()` 实现,含 Q1 相位探测器)。
   - FCFTTM(k) = Σ FCFQ(k..k+3);GR%PY(t) = (FCFTTM(t)−FCFTTM(t+4))/|FCFTTM(t+4)|;
     stdev 取 t=0..11,≥8/12 个有效点(rung-6 的 STDEVQ 约定)。
2. `营业收入3年复合增长` 与 `净利润3年复合增长`(#4/#15/#13 的省略项):
   3Y CAGR = (TTM(0)/TTM(12))^(1/3)−1 → 需 q12..q15。
3. `CoreProfitTTMGr%3Y` 同理(CoreProfit 用 **0-fill 口径**:费用行 NaN→0、营收必须非空 —— registry fix #11,
   见 REPORT §2;这是果仁厂商行为,已在建行案例结构级验证)。

### 需要深挖的字段(field_filter)

单季/累计槽到 depth 16:`revenue`, `oper_cost`, `admin_exp`, `sell_exp`, `fin_exp`, `biz_tax_surchg`
(CoreProfit 六腿), `n_income`(3Y NP), `n_cashflow_act`, `c_pay_acq_const_fiolta`, `n_recp_disp_fiolta`
(FCF 现金流三腿), `depr_fa_coga_dpba`, `amort_intang_assets`, `lt_amort_deferred_exp`(D&A 三腿,cum 槽)。

### Universe(touched_symbols)

主板+中小+创业板+科创(`guorn_universe.in_guorn_universe(c, include_star=True)`)∩
`guorn_beta._is_ashare_stock`(⚠ 剔除 6 位码指数冲突,如 000001_SH 上证指数 —— REPORT §6 的教训)。
约 5400 只。从 `data/qlib_data/instruments/all_stocks.txt` 交叉确认。

### 执行步骤(严格照 rung-6 模式)

1. **先估算磁盘**:字段数 × 槽数 × universe;rung-6 的 7 字段×4817 只 depth-16 ≈ 182GB 瞬态。
   本次 ~14 字段 → 预估并打印;E: 盘剩余空间必须 >2× 预估。**绝不做无 field_filter 的全字段深槽build**。
2. `_build_deepslot_scoped.py` 模式调 `build_unified_qlib(field_filter=…, datasets=…, touched_symbols=…,
   slot_depth=16, publish=False)` → staged 目录在 `data/qlib_builds/` 下,后台运行 + 日志到 logs/。
3. 构建后抽查:随机 5 股,`revenue_sq_q12..q15` 对 rung-6 深槽真值/原始报表交叉验证(PIT kernel 在
   depth 16 已被 rung-6 逐位验证,但仍要抽查本次构建完整性)。
4. 从 staged provider(`--provider-uri` 指向 staged)计算 4 个 frame,存到
   `workspace/outputs/guorn_parity/deepslot16_frames/`:
   `f_fcf_ttm_gr_stdev12.parquet` / `f_rev_cagr3y.parquet` / `f_np_cagr3y.parquet` / `f_core_ttm_gr3y.parquet`
   (datetime × instrument,float32,全 grid 2013-01..2026-02-27)。
5. **验证**(保真门,必做):用 `Knowledge/果仁回测结果/23_value_FCF_非金sm_v2.xlsx` 的 持仓详单
   真值列 `波动率_季度指标(FCFTTM_重算GR%PY,12)` 做逐股值对齐(pday=开始日期前一交易日;方法照
   `guorn_verify_09_divheavy.py::factor_parity`),报告 medRel/sign/Spearman。#4 的 xlsx(09_sm_GARP_illiq)
   有 `公式(营业收入增长-营业收入3年复合增长)` 与 `公式(COREPROFITTTMGr%PY-COREPROFITTTMGr%3Y)` 列,
   可对 3Y 项做差值级验证。**没有 top-K/Spearman 数字不算验证完成**(guorn-verification skill 纪律)。
6. **删除 staged 目录**(robocopy 空镜像法删大树;确认磁盘回收)。
7. 记录:REPORT §5 表加一行、deployed_20_replication_status.md 台账、project_state.md 注记。

### 硬约束

- NON-FORMAL 平价工具链:staged provider 不发布;任何东西不进 formal 路径、不动 field_status.yaml。
- 不并行跑任何 Tushare fetcher(本任务纯本地重物化,无需 Tushare)。
- 用 `venv/Scripts/python.exe`;长任务 run_in_background + 日志;§13:staged build 属沙盒构建可直接做,
  但**删除前列出将删路径**。
- 完成后可顺手跑 #11 的复刻(可选,若做:harness 模式照 `guorn_verify_12_chinext_value.py` 薄
  harness + REPORT §2 的口径 registry;#11 recipe 在 deployed_20_recipes.md L376;注意其
  `机构持股环比增长` w1 数据缺 → 省略并记录;预期它是构成噪声类,先跑 replay 定界)。
