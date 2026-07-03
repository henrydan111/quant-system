# GPT 5.5 Pro 跨审 Prompt — grn 因子跨数据集 compute 崩溃修复(5 因子 v2)

> 复审对象:上一波(grn catalog 集成,你已 APPROVE)的 **compute-safety 修复回填**。分支已推送
> `calendar-unfreeze`,commit `34de062`。公共仓库 https://github.com/henrydan111/quant-system。
> 嵌入文本为权威;raw 链接:
> `https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/src/alpha_research/factor_library/catalog.py`(函数 `_add_guorn_replication_factors`,~L740-870)

---

你是独立评审。你上一轮 APPROVE 了 12 个 grn_* draft 因子入 catalog(审了表达式逻辑 + PIT + 治理)。
本轮是一个**你上轮无法发现的 bug 的修复**——因为它只在 FORMAL native compute 路径暴露,而上轮的审查
(逻辑/PIT/字段门)没有跑 `compute_factors`。

## Bug(走 formal factor_lifecycle IS-gate 时暴露)

把 grn 因子跑过 `run_is_walk_forward`(IS-only 走查,2010-2020,与 orchestrator 的
`handle_factor_lifecycle_walk_forward` bit-identical)时,`compute_factors` 崩溃:

```
ValueError: operands could not be broadcast together with shapes (0,) (N,) ()   # qlib If 的 np.where
```

**根因**:5 个因子的分子与分母(或涨停 flag 与价格)来自**不同 provider 数据集**(income vs balancesheet;
limit_status vs price)。某只股票在窗口内有 income bin 但 balancesheet 为**空序列 (0,)**(或 2010-11 早期
无 limit_status),而另一侧满长 (N,)。qlib 逐股原生求值**不做 index 对齐**,`If(denom_guard, num/denom, nan)`
的守卫来自空的那侧 (0,)、比值分支来自满的那侧 (N,) → `np.where((0,),(N,),...)` 广播崩。

**为什么之前没崩**:deployed-20 复刻 harness 用 `D.features(...).reindex(grid).ffill()` 强制把每个字段对齐
到统一 grid(空字段被 NaN 填满到 N) → `fillna(0)`/守卫都在等长序列上。原生 `compute_factors` 逐股求值
不对齐 → formal 路径崩。**这类"harness reindex 掩盖的原生求值脆弱性"是本次的核心教训。**

崩溃因子(5):`grn_roe_ttm_diff_q`(归母income / 加权净资产balancesheet)、`grn_ato_diff_py`(营收TTM
income / 均资产balancesheet)、`grn_gp_ev`(毛利income / EV[市值+balancesheet])、`grn_onmom_{250,120}_20`
(limit_status flag / 价格)。**同数据集的 7 个因子(core_profit/dedt/incometax/rnd/shares/true_debt/
core_qoq)未崩**——它们的分子分母同属一个数据集(可得性一致)。

## 修复(长度自洽 + 语义保真)

1. **比值-守卫(roe/ato/gp_ev)**:把守卫从"分母 > eps"改到**已算出的比值**上:
   `ratio = num / denom`(qlib Div 走 pandas 对齐 → 长度 = 满长那侧;分母空时 ratio 全 NaN);
   `If(Abs(ratio) < 上限, ratio, np.nan)`——cond 与 left 同源同长 → 无广播崩。上限(1e6 for ROE、
   1e12 for ATO、1e9 for GP/EV)≫ 任何真实量级,专杀 tiny-denom 的 inf 与空-denom 的 NaN。
   - 语义保真:**负权益 ROE 仍有限 → 保留**(果仁记录的 top-K 脆弱性来源);资产恒正 → `|ratio|<上限`
     等价于原 `denom>0` 守卫。
2. **长度锚定(onmom)**:`If(Eq($limit_status + $close*0, 1), 0, Log(...))`——`+ Ref($close,1)*0`
   把 limit_status 锚到价格长度(缺失处 NaN → `Eq(NaN,1)` False → 走 Log 分支 = 该股不排除涨停;
   有值处照常全排除)。

**通用规范(已写入 commit message + 因子注释)**:任何分子/分母跨数据集的 catalog 因子,守卫必须作用在
已算比值上、或用 `+field*0` 把稀疏字段锚到稠密字段长度。

## 验证(全绿)

- 12/12 grn 因子在 **2011-H1 幼股密集窗**(深槽 q5+ 与 limit_status 最易缺失)`compute_factors` 干净(原 5 崩)
- 门1 IS-gate 随即跑通:4/6 成长质量因子达 candidate(roe +0.56/sign1.0、core_profit +0.55、
  dedt +0.48、ato +0.38;shares/true_debt heldout 负 → 留 draft,门在工作)
- 测试:PIT 三件套 + `test_factor_registry.py` 全文件 = **112 passed**
- sync:5 个 new_versions(v2),parity_ok=True,全部仍 draft,caveat notes 已重写到 v2 行
- ⚠ v2 表达式改变 → `definition_hash` 变;因子从未被 validated,v2 是干净的重定义(v1 表达式在原生
  compute 下本就不可用)

## 结构化自审(§10,verdict: clean for GPT)

- §3.2 PIT:5 个改动因子每个 $field 仍在 Ref(...,1) 内(`+$close*0` 的 close 亦 Ref(...,1));PIT 三件套过 ✓
- 语义未变(比值-守卫与原分母-守卫在有效域等价;负权益保留是原意)✓
- 无对冲词;数字来自运行输出 ✓

## 请你重点回答

1. **最小修复 vs 统一修复**:我只改了 5 个确认崩溃的跨数据集因子;7 个同数据集因子保持原
   `If(Abs(denom)>eps, num/denom, nan)`(2011 幼股窗实测未崩,推断同数据集槽位可得性一致)。你认为应
   **对所有 guarded-ratio grn 因子统一改成比值-守卫**(防御性,但改变已过测因子的 definition_hash),
   还是最小改动正确?我的推断"同数据集 = 安全"是否稳健(会不会有 income q0 present 但 q7 empty 的幼股
   使 TTM4 求和为空、与 TTM0 满长不一致)?[注:grn_core_qoq_minus_ttm 用到 income q0..q7,2011 窗实测未崩]
2. **`Abs(ratio) < 上限` 阈值**:硬编码的 1e6/1e12/1e9 上限是否稳妥?有无更干净的 qlib 惯用式表达
   "有限且非空"(该 qlib 无 IsNull/IsFinite 算子)?
3. **onmom 的 `+$close*0` 锚定**:早期无 limit_status 的股票降级为"不排除涨停",与有 limit_status 的股票
   口径不一致——对一个横截面 draft 因子,这个时间异质性可接受吗?还是应把涨停-排除的隔夜收益**物化**
   成 provider 字段(B-档)以获得全历史一致口径?
4. **过程问题**:入 catalog 的 GPT 审查是否应**强制包含一次 native `compute_factors` 冒烟**(而非仅逻辑/
   PIT/字段门),以在评审阶段就抓住这类 harness 掩盖的脆弱性?若是,建议写入 §10 契约/PROMPT 模板。
5. 其它任何 PIT / 数值 / 治理问题。

裁决:APPROVE / CHANGES REQUIRED(逐条,标 blocker/major/minor)。
