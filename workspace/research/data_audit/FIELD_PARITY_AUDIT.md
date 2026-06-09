# 本地数据 ↔ Tushare 接口 字段一致性审计

逐数据集对比：本地 raw parquet 列 vs 官方输出参数（含 默认显示 Y/N）。
- **missing_default_Y** = 官方默认输出(Y)但本地缺失 → **高风险**（获取方式可能漏字段）
- **missing_default_N** = 官方非默认(N)且本地缺失 → 中（多因未传 `fields=` 只取默认列）
- **extra_local** = 本地有、官方无（改名/派生/内部列）
- **anchor_gap** = 官方有但本地缺的日期锚字段（PIT 关键）
**FLAGGED datasets (missing default-Y or anchor gap): ['income_quarterly', 'cashflow_quarterly']**


## stock_basic  (doc [25], files=1, official=17, local=17)
- **missing_default_Y (0)**: —
- missing_default_N (0): —
- extra_local (0): —
- date anchors: local=[] official=[] **gap=—**
- type_mismatch (0): —

## trade_cal  (doc [26], files=1, official=4, local=4)
- **missing_default_Y (0)**: —
- missing_default_N (0): —
- extra_local (0): —
- date anchors: local=[] official=[] **gap=—**
- type_mismatch (1): is_open: doc=str(str) local=int64(num) [note]

## namechange  (doc [100], files=1, official=6, local=6)
- **missing_default_Y (0)**: —
- missing_default_N (0): —
- extra_local (0): —
- date anchors: local=['ann_date', 'end_date'] official=['ann_date', 'end_date'] **gap=—**
- type_mismatch (0): —

## stock_st_daily  —  **DERIVED_NO_ENDPOINT**  (files=1, glob `reference/stock_st_daily.parquet`)
local cols: name, trade_date, ts_code, type, type_name

## daily  (doc [27, 28, 32], files=4410, official=27, local=27)
_note: merged: daily + adj_factor + daily_basic_
- **missing_default_Y (0)**: —
- missing_default_N (0): —
- extra_local (0): —
- date anchors: local=['trade_date'] official=['trade_date'] **gap=—**
- type_mismatch (0): —

## index_daily  (doc [95], files=7, official=11, local=11)
- **missing_default_Y (0)**: —
- missing_default_N (0): —
- extra_local (0): —
- date anchors: local=['trade_date'] official=['trade_date'] **gap=—**
- type_mismatch (0): —

## moneyflow  (doc [170], files=4405, official=20, local=20)
_note: pro.moneyflow (个股资金流向)_
- **missing_default_Y (0)**: —
- missing_default_N (0): —
- extra_local (0): —
- date anchors: local=['trade_date'] official=['trade_date'] **gap=—**
- type_mismatch (0): —

## northbound(hk_hold)  (doc [188], files=2153, official=7, local=7)
_note: fetch_hk_hold_
- **missing_default_Y (0)**: —
- missing_default_N (0): —
- extra_local (0): —
- date anchors: local=['trade_date'] official=['trade_date'] **gap=—**
- type_mismatch (0): —

## margin(margin_detail)  (doc [59], files=3863, official=11, local=10)
_note: fetch_margin_detail_
- **missing_default_Y (0)**: —
- missing_default_N (1): name
- extra_local (0): —
- date anchors: local=['trade_date'] official=['trade_date'] **gap=—**
- type_mismatch (0): —

## stk_limit  (doc [183], files=4410, official=5, local=4)
- **missing_default_Y (0)**: —
- missing_default_N (1): pre_close
- extra_local (0): —
- date anchors: local=['trade_date'] official=['trade_date'] **gap=—**
- type_mismatch (0): —

## top_list  (doc [106], files=4410, official=15, local=15)
- **missing_default_Y (0)**: —
- missing_default_N (0): —
- extra_local (0): —
- date anchors: local=['trade_date'] official=['trade_date'] **gap=—**
- type_mismatch (0): —

## top_inst  (doc [107], files=3434, official=10, local=10)
- **missing_default_Y (0)**: —
- missing_default_N (0): —
- extra_local (0): —
- date anchors: local=['trade_date'] official=['trade_date'] **gap=—**
- type_mismatch (0): —

## block_trade  (doc [161], files=4339, official=7, local=7)
- **missing_default_Y (0)**: —
- missing_default_N (0): —
- extra_local (0): —
- date anchors: local=['trade_date'] official=['trade_date'] **gap=—**
- type_mismatch (0): —

## cyq_perf  (doc [293], files=2008, official=11, local=11)
- **missing_default_Y (0)**: —
- missing_default_N (0): —
- extra_local (0): —
- date anchors: local=['trade_date'] official=['trade_date'] **gap=—**
- type_mismatch (0): —

## income  (doc [33], files=82, official=94, local=85)
- **missing_default_Y (0)**: —
- missing_default_N (9): amodcost_fin_assets, asset_disp_income, credit_impa_loss, end_net_profit, net_after_nr_lp_correct, net_expo_hedging_benefits, oth_impair_loss_assets, oth_income, total_opcost
- extra_local (0): —
- date anchors: local=['ann_date', 'end_date', 'f_ann_date'] official=['ann_date', 'end_date', 'f_ann_date'] **gap=—**
- type_mismatch (6): transfer_surplus_rese: doc=float(num) local=null(null) [note]; transfer_housing_imprest: doc=float(num) local=null(null) [note]; transfer_oth: doc=float(num) local=null(null) [note]; adj_lossgain: doc=float(num) local=null(null) [note]; withdra_legal_pubfund: doc=float(num) local=null(null) [note]; workers_welfare: doc=float(num) local=null(null) [note]

## income_quarterly  (doc [33], files=72, official=94, local=21)  ⚠️ FLAG
_note: report_type 2/3 single-quarter_
- **missing_default_Y (63)**: adj_lossgain, ass_invest_income, assets_impair_loss, capit_comstock_div, comm_exp, comm_income, compens_payout, compens_payout_refu, compr_inc_attr_m_s, compr_inc_attr_p, comshare_payable_dvd, distable_profit, distr_profit_shrhder, div_payt, ebit, ebitda, end_type, fin_exp_int_exp, fin_exp_int_inc, forex_gain, fv_value_chg_gain, income_tax, insur_reser_refu, insurance_exp, int_exp, int_income, invest_income, minority_gain, n_asset_mg_income, n_commis_income, n_oth_b_income, n_oth_income, n_sec_tb_income, n_sec_uw_income, nca_disploss, non_oper_exp, non_oper_income, oper_exp, oth_b_income, oth_compr_income, other_bus_cost, out_prem, prem_earned, prem_income, prem_refund, prfshare_payable_dvd, reins_cost_refund, reins_exp, reins_income, reser_insur_liab, t_compr_income, transfer_housing_imprest, transfer_oth, transfer_surplus_rese, undist_profit, une_prem_reser, update_flag, withdra_biz_devfund, withdra_legal_pubfund, withdra_legal_surplus, withdra_oth_ersu, withdra_rese_fund, workers_welfare
- missing_default_N (10): amodcost_fin_assets, asset_disp_income, continued_net_profit, credit_impa_loss, end_net_profit, net_after_nr_lp_correct, net_expo_hedging_benefits, oth_impair_loss_assets, oth_income, total_opcost
- extra_local (0): —
- date anchors: local=['ann_date', 'end_date', 'f_ann_date'] official=['ann_date', 'end_date', 'f_ann_date'] **gap=—**
- type_mismatch (0): —

## balancesheet  (doc [36], files=72, official=158, local=152)
- **missing_default_Y (0)**: —
- missing_default_N (6): lease_liab, oth_eq_invest, oth_eq_ppbond, oth_illiq_fin_assets, receiv_financing, use_right_assets
- extra_local (0): —
- date anchors: local=['ann_date', 'end_date', 'f_ann_date'] official=['ann_date', 'end_date', 'f_ann_date'] **gap=—**
- type_mismatch (1): agency_bus_liab: doc=float(num) local=null(null) [note]

## cashflow  (doc [44], files=72, official=97, local=97)
- **missing_default_Y (0)**: —
- missing_default_N (0): —
- extra_local (0): —
- date anchors: local=['ann_date', 'end_date', 'f_ann_date'] official=['ann_date', 'end_date', 'f_ann_date'] **gap=—**
- type_mismatch (0): —

## cashflow_quarterly  (doc [44], files=72, official=97, local=92)  ⚠️ FLAG
_note: report_type 2/3 single-quarter_
- **missing_default_Y (5)**: conv_copbonds_due_within_1y, conv_debt_into_cap, free_cashflow, oth_loss_asset, uncon_invest_loss
- missing_default_N (0): —
- extra_local (0): —
- date anchors: local=['ann_date', 'end_date', 'f_ann_date'] official=['ann_date', 'end_date', 'f_ann_date'] **gap=—**
- type_mismatch (0): —

## indicators(fina_indicator)  (doc [79], files=97, official=167, local=167)
- **missing_default_Y (0)**: —
- missing_default_N (0): —
- extra_local (0): —
- date anchors: local=['ann_date', 'end_date'] official=['ann_date', 'end_date'] **gap=—**
- type_mismatch (0): —

## forecast  (doc [45], files=75, official=12, local=13)
- **missing_default_Y (0)**: —
- missing_default_N (0): —
- extra_local (1): update_flag
- date anchors: local=['ann_date', 'end_date'] official=['ann_date', 'end_date'] **gap=—**
- type_mismatch (0): —

## express  (doc [46], files=73, official=32, local=17)
_note: Bucket A raw_
- **missing_default_Y (0)**: —
- missing_default_N (16): eps_last_year, growth_assets, growth_bps, is_audit, np_last_year, op_last_year, or_last_year, remark, tp_last_year, yoy_dedu_np, yoy_eps, yoy_equity, yoy_op, yoy_roe, yoy_sales, yoy_tp
- extra_local (1): update_flag
- date anchors: local=['ann_date', 'end_date'] official=['ann_date', 'end_date'] **gap=—**
- type_mismatch (4): bps: doc=float(num) local=null(null) [note]; open_net_assets: doc=float(num) local=null(null) [note]; open_bps: doc=float(num) local=null(null) [note]; perf_summary: doc=str(str) local=null(null) [note]

## disclosure_date  (doc [162], files=73, official=6, local=5)
_note: Bucket A raw_
- **missing_default_Y (0)**: —
- missing_default_N (1): modify_date
- extra_local (0): —
- date anchors: local=['ann_date', 'end_date'] official=['ann_date', 'end_date'] **gap=—**
- type_mismatch (0): —

## fina_mainbz  (doc [81], files=65, official=9, local=8)
_note: Bucket A raw_
- **missing_default_Y (0)**: —
- missing_default_N (1): update_flag
- extra_local (0): —
- date anchors: local=['end_date'] official=['end_date'] **gap=—**
- type_mismatch (0): —

## fina_audit  (doc [80], files=1, official=7, local=7)
_note: Bucket A raw_
- **missing_default_Y (0)**: —
- missing_default_N (0): —
- extra_local (0): —
- date anchors: local=['ann_date', 'end_date'] official=['ann_date', 'end_date'] **gap=—**
- type_mismatch (0): —

## dividends  (doc [103], files=20, official=16, local=14)
- **missing_default_Y (0)**: —
- missing_default_N (2): base_date, base_share
- extra_local (0): —
- date anchors: local=['ann_date', 'end_date', 'imp_ann_date'] official=['ann_date', 'end_date', 'imp_ann_date'] **gap=—**
- type_mismatch (0): —

## holder_number  (doc [166], files=35, official=4, local=4)
_note: stk_holdernumber_
- **missing_default_Y (0)**: —
- missing_default_N (0): —
- extra_local (0): —
- date anchors: local=['ann_date', 'end_date'] official=['ann_date', 'end_date'] **gap=—**
- type_mismatch (0): —

## stk_holdertrade  (doc [175], files=19, official=13, local=11)
- **missing_default_Y (0)**: —
- missing_default_N (2): begin_date, close_date
- extra_local (0): —
- date anchors: local=['ann_date'] official=['ann_date'] **gap=—**
- type_mismatch (1): ann_date: doc=str(str) local=timestamp[ns](time) [note]

## pledge_stat  (doc [110], files=13, official=7, local=7)
_note: Bucket A raw_
- **missing_default_Y (0)**: —
- missing_default_N (0): —
- extra_local (0): —
- date anchors: local=['end_date'] official=['end_date'] **gap=—**
- type_mismatch (0): —

## repurchase  (doc [124], files=17, official=9, local=9)
_note: Bucket A raw_
- **missing_default_Y (0)**: —
- missing_default_N (0): —
- extra_local (0): —
- date anchors: local=['ann_date', 'end_date'] official=['ann_date', 'end_date'] **gap=—**
- type_mismatch (0): —

## top10_floatholders  (doc [62], files=77, official=9, local=9)
_note: Bucket A raw_
- **missing_default_Y (0)**: —
- missing_default_N (0): —
- extra_local (0): —
- date anchors: local=['ann_date', 'end_date'] official=['ann_date', 'end_date'] **gap=—**
- type_mismatch (0): —

## index_weights  (doc [96], files=219, official=4, local=4)
_note: index_weight_
- **missing_default_Y (0)**: —
- missing_default_N (0): —
- extra_local (0): —
- date anchors: local=['trade_date'] official=['trade_date'] **gap=—**
- type_mismatch (0): —

## industry_sw2021  (doc [181], files=1, official=7, local=7)
_note: index_classify SW2021_
- **missing_default_Y (0)**: —
- missing_default_N (0): —
- extra_local (0): —
- date anchors: local=[] official=[] **gap=—**
- type_mismatch (0): —

## industry_sw2021_members  (doc [335], files=1, official=11, local=11)
_note: index_member_all_
- **missing_default_Y (0)**: —
- missing_default_N (0): —
- extra_local (0): —
- date anchors: local=['in_date', 'out_date'] official=['in_date', 'out_date'] **gap=—**
- type_mismatch (2): in_date: doc=str(str) local=timestamp[ns](time) [note]; out_date: doc=str(str) local=timestamp[ns](time) [note]

## report_rc  (doc [292], files=17, official=23, local=22)
- **missing_default_Y (0)**: —
- missing_default_N (1): imp_dg
- extra_local (0): —
- date anchors: local=['create_time', 'report_date'] official=['create_time', 'report_date'] **gap=—**
- type_mismatch (0): —

