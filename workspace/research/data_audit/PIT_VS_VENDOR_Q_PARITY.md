# Part B — our pit_* (recomputed via deployed primitives) vs Tushare vendor q_*

Per (ts_code, fiscal end_date), FINAL restatement. merged rows=253692.

| ours | vendor | N | pearson | spearman | sign% | <=1pp% | <=5pp% | medAbsΔ |
|---|---|---|---|---|---|---|---|---|
| pit_netprofit_yoy | q_netprofit_yoy | 233613 | 0.0000 | 0.9835 | 99.1 | 93.2 | 95.0 | 0.000 |
  - near-exact(|Δ|<0.05): 91.0% · Pearson after ±300 clip: 0.9861 (keeps 88.10%) · |Δ|>50pp count: 5747
| pit_op_yoy | q_op_yoy | 233534 | 0.8947 | 0.9812 | 98.9 | 91.2 | 93.7 | 0.000 |
  - near-exact(|Δ|<0.05): 88.2% · Pearson after ±300 clip: 0.9839 (keeps 87.77%) · |Δ|>50pp count: 6745
| pit_or_yoy | q_sales_yoy | 232634 | 0.0237 | 0.9705 | 98.9 | 94.9 | 96.2 | 0.000 |
  - near-exact(|Δ|<0.05): 93.5% · Pearson after ±300 clip: 0.9538 (keeps 98.31%) · |Δ|>50pp count: 3551

## 结论 (Part B)

**我们自算的 `pit_*` 单季同比 = 正确，可信赖**（无需依赖厂商 `q_*`）：

- **~90% 近乎逐值相等**（|Δ|<0.05pp：netprofit 91.0% / op 88.2% / sales 93.5%）——我们用 `derive_single_quarter_value` + `percent_change` 复算出的值，与 Tushare 独立计算的 `q_*` 在 ~90% 的"股票-季度"上精确到两位小数一致。
- **Spearman 0.97–0.98、符号一致 99%**——排序与方向几乎完全一致。
- **裁掉极端 YoY（|值|>300%）后 Pearson 0.954–0.986**（保留 88–98% 数据）。原始 Pearson 近 0（netprofit 0.00 / sales 0.02）**完全由 ~1.5–3% 的极端季度驱动**：当去年同期单季基数接近 0 或为负时，YoY 比率会爆炸（数学固有的不稳定），我们的 `percent_change` 与厂商对这种爆炸的截断方式不同 → 少数极端值拉垮线性相关，但中位差≈0、排序/符号不受影响。**这不是核心计算的 bug**，是 YoY 比率在小基数下的固有性质。

**可行动建议**：基于 `pit_*`（或任何 YoY）的增长因子应做 winsorize/裁剪以中和近零基数的爆炸（标准做法，因子库的 cs_winsorize 已覆盖）。**Part C 的单季比率可放心建在已验证的 `derive_single_quarter_value` 之上。**

脚本：[validate_pit_vs_vendor_q.py](../../scripts/validate_pit_vs_vendor_q.py)（纯 pandas + 部署原语，无 qlib/loader）。
