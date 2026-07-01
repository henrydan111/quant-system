# D5 注册映射表 — CICC 码 ↔ 目录 id ↔ 去重判定(2026-06-12)

> Phase D5:中金复刻 exact 档 30 因子的入目录裁决。**18 注册 / 7 跳过(秩等价)/
> 其余为锚监控项或不可表达**。注册的 18 个是 universe 方案 Draft-7 新流程的**首批队列**:
> 每个带 univ_all primary claim,且因 2010-2022 三域证据在注册前已被观察(Phase-D 真值
> 批),claim 被裁决器机械判为 `tainted_post_hoc_max_stat` —— 如实记账,无特例。
> external_prior(中金手册先于我方全部工作)可解释、不可重置 clean(informed_by 非空,R2-B2)。

## 注册(18)

| CICC 码 | 目录 id | 与既有条目的区别 |
|---|---|---|
| CFOA | qual_cfoa_ttm | 无既有 OCF-TTM/资产因子(val_cftp 是 vendor 累计每股口径) |
| ROA_TTM | qual_roa_ttm | qual_roa = vendor 累计期 $roa;本条 PIT 槽位 TTM(C 阶段证明刷新节奏差 ~2×) |
| NPM_TTM | qual_npm_ttm | qual_net_margin = vendor 累计;本条 NI_TTM/REV_TTM |
| AT | qual_at_ttm | qual_asset_turnover = vendor 累计;本条 REV_TTM/平均资产 |
| INVT | qual_invt_ttm | 无既有存货周转 TTM(vendor $inv_turn 未入目录) |
| RAT | qual_rat_ttm | 新(应收周转;缺应收票据 caveat) |
| GPMD | qual_gpmd_ttm | grow_gross_margin_chg = vendor 指标日差(仅公告日非零);本条为真·季度 TTM 毛利率差分(C 阶段三指纹靶心构造) |
| CSR | qual_csr | qual_cash_to_assets 分母是总资产;本条流动负债 |
| CCR | qual_ccr_ttm | 新(OCF_TTM/流动负债) |
| NP_Q_YOY | grow_ni_attr_q_yoy | 目录只有其加速度(grow_n_income_attr_p_yoy_accel_q = 本条的 Delta);Abs 分母 |
| NP_QOQ | grow_ni_q_qoq | 新(单季环比;含少数净利,归母 q1 槽缺) |
| OP_Q_YOY | grow_op_q_yoy | 同 NP_Q_YOY(只有加速度存在) |
| OR_Q_YOY | grow_or_q_yoy | 同上 |
| TA_YOY | grow_total_assets_yoy | 新(总资产同比) |
| EP_TTM | val_ep_ttm_pit | val_ep_ttm = 1/pe_ttm **丢亏损股**;本条 NI_TTM/MV 把亏损股排最底(中金口径) |
| OCFP_TTM | val_ocfp_ttm_pit | val_cftp = vendor 累计每股;本条 TTM/MV |
| FCFP_TTM | val_fcfp_ttm | 新(OCF−资本开支)/MV |
| FC_MC | size_float_ratio | 流通占比(有界比率),与 ln-市值族非同物 |

## 跳过 — 秩等价映射(7)

| CICC 码 | 既有目录 id | 等价理由 |
|---|---|---|
| Ln_MC / MC | size_ln_mcap | 单调变换,Spearman 等价 |
| Ln_FC / FC | size_ln_circmv | 同上 |
| BP_LR | val_bp | 同为 1/pb(LR 口径一致) |
| DP | val_div_yield | 同为 dv_ttm(差常数因子) |
| SP_TTM | val_sp_ttm | 1/ps_ttm 与 REV_TTM/MV 秩相似度极高(分母同,营收口径差异微) |
| CUR / QR / Debt_Asset | lev_current_ratio / lev_quick_ratio / lev_debt_to_assets | 同报表科目同比率,vendor 与槽位同锚 |
| mmt_normal_M | mom_return_20d | 表达式精确相同(Ref(close·adj,1)/Ref(·,21)−1) |
| OP_QOQ | grow_opprofit_qoq | 同为 $q_op_qoq |

## 未注册的其余 exact 档

- **mmt_range_M**:条件滚动和不可用 Qlib 表达式表达(协议层以 pandas 现算);
  入目录需新算子,挂起至价量批(Phase E)
- 9 个锚因子中的重复体(ln_mc/ep_ttm/dp/mmt_normal_m 等)已按上表映射

## Claim 与 taint 状态(新流程首批)

- 18 × univ_all primary claim,**全部 `tainted_post_hoc_max_stat`**(54 条
  exploratory_eval taint:每因子 × univ_all/csi300/csi500,源 = cicc_fundamental_batch)
- csi1000/microcap/growth/liquid_top300 四域未被该批观察 → 该四域的未来 claim 仍可 clean
  (F2 矩阵跑过之后则同样进入已观察)
- 后续 IS 门对这 18 个的 univ_all 裁决适用 **max-stat 档**(置换校准引擎就绪前用保守
  上界或 reviewer-block,绝不退回原 bar)

执行脚本:`workspace/scripts/d5_register_claims.py`;目录条目:catalog.py「CICC handbook
replication batch」块;7 域体检 sweep 待 F2 接线后补(daily QA 缺域 WARNING 属预期)。
