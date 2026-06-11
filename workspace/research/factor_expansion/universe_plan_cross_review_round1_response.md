# Universe 方案 Cross-Review Round-1 裁决(GPT 5.5 Pro → Draft-4)

> 2026-06-11。GPT 总判:CHANGES REQUIRED,最小必改 4 件。本文逐条裁决;Draft-4 据此修订。

| # | GPT 发现 | 裁决 | 动作 |
|---|---|---|---|
| 1 | 事前声明防不住 sandbox 先看(注册前在 notebook 把 50 变体×7 域跑完再"干净"注册) | **ACCEPT,加一条诚实边界** | 所有 sanctioned 评估入口(batch_screening/unified_eval/cicc_protocol 驱动)强制写**探索台账**(expression_hash×字段集×universe×方法学×时间,无 claim 即标 exploratory_tainted);门复核时按表达式规范化哈希+字段集相似度**自动检索**台账并披露匹配。诚实边界:裸 pandas 算 Spearman 无法技术性禁止——该控制的目标是"干净声明可被验证",不是"作弊不可能";对本系统(单操作者+代理,评估几乎全走 sanctioned 工具)覆盖率实际很高 |
| 2 | 7 域矩阵后 IS 门不能无条件沿用单域原 bar;"记账+经济学故事"控不住假阳性(7 域 ≥1 过线 ≈30%) | **ACCEPT(本轮最强发现)** | 分层门槛表(见 Draft-4 §3.3):单一事前 primary 域=原 bar;声明 k 域=按 k 调整;post-hoc 改域=7 域 family max-stat 或 evidence-only;clone/composite=继承 taint 从严。校准方式采纳其建议:**block permutation 经验零分布 + max-stat 阈值**(域间高度相关,Bonferroni/7 过度修正;置换法自动吸收相关性)。190×7 回填矩阵正好是估计经验零分布的样本 |
| 3 | `validity_domains` 混 OOS 验证域与 evidence-only 域,中间层丢标签即等于绕过封条(`if target in validity_domains` 失败场景成立) | **ACCEPT 全盘,D2 原案撤回** | 三字段分离:`approved_scope.oos_validated_domains`(生产 resolver 唯一读取)/ `domain_evidence`(描述性,status_power=none)/ `deployment_policy.allowed_domains`。evidence-only 进策略须显式 `allow_descriptive_domain_evidence: true` 且默认 research-only |
| 4 | 等权 ESTU 中性化残留尺寸效应(A股小票数量主导等权回归斜率;残差在 top300 域仍带 size/流动性倾斜被当 alpha) | **ACCEPT 带变体处理** | `neutralization_weighting` 成为显式哈希参数;**新建**身份层中性化因子默认 `sqrt_float_cap` WLS;存量 EW 因子不静默重定义(定义不可变),改为命名变体(`ew_univ_all`)。门报告增加**硬暴露审计**:因子值对 ln_mcap/行业哑变量/ADV/上市年龄的目标域内残留暴露须低于阈值 |
| 5 | 薄域只靠 bootstrap CI 不够,bar 在低 breadth 下含义已变(microcap 剔完字段缺失某些月只剩 26-32 只/组,LS 腿可能 10-15 只驱动) | **ACCEPT** | status-bearing 门前置硬地板:`valid_names_total_p10≥300 / min_decile_count_p10≥30 / 两腿 effective_N_p10≥25 / 腿内行业集中度 p90≤35% / block bootstrap 单位=调仓周期非 iid 日`。不满足→只能 discovery/evidence-only。后果如实记录:univ_microcap 与 liquid_top300 在地板线上是边缘域,逐因子覆盖率决定能否过门 |
| 6 | clone/composite 洗白(zscore 包一层/微调 winsor 顺序→新 definition_hash 假装新因子;或用矩阵挑 8 个 microcap 最强做复合) | **ACCEPT(优秀捕获)** | 注册强制血缘声明:`derived_from_factor_ids / component_selection_basis(pre_registered|matrix_selected|external_prior) / lineage_taint_domains`;复合继承成分的已观察域 taint;无血缘声明不得进 formal 门;QA 用字段集重叠+表达式规范化相似度检测疑似未披露血缘 |
| 7 | 更简单模型:FactorDefinition(域无关)+ FactorDomainClaim(每 (factor,universe) 一个 claim,自带状态阶梯)——"approved 的是 claim 不是 factor" | **PARTIALLY ACCEPT** | 语义上更干净,采纳为**数据模型**:domain claim 表成为域生命周期的事实源(claim_id/factor_id/universe/hypothesis/pre_registered_at/status/lineage_taint/multiplicity_adjustment)。但不推翻现有 factor.status 体系——`factor.status = primary claim 的状态`(非规范化视图,42 个调用点与既有写入门零迁移)。它自然吸收 #3(validity = approved claims)与 gated_universe 元数据 |

## D1-D5 重裁(并入 GPT 条件)

| 决策点 | Draft-4 形态 |
|---|---|
| D1 声明域门 | **有条件版**:singleton `primary_intended_universe` 用原 bar;多域声明按 family 调整;门前必须已有 7 域矩阵(或失败行) |
| D2 evidence-only 引用 | **原案撤回**,改三字段分离 + 显式 override(research-only 默认) |
| D3 七域全开 | 维持,但**全开即制造 observed-domain taint**——此后任何域选择按 7 域 family 处理(写进规则) |
| D4 换域披露 | 升级:不止 hypothesis 文本,探索台账+血缘+成分选择全部机器可审计 |
| D5 draft 必填声明 | 改 `primary_intended_universe` 必填 + `secondary_universes` 可选但预先计入多重检验;存量/派生继承 post-hoc taint |

## 不接受/修正的部分(2 处,均为程度而非方向)

1. GPT 把评估入口强制 claim 写成"airtight 方案"——我们如实降格为"审计可验证方案"(裸 pandas 不可禁,见 #1 诚实边界)。
2. Bonferroni/Holm 按 7 硬除:域强相关(univ_all 包含其余全部),有效独立域 ~2-3,硬除过度修正会误杀真 alpha——以置换 max-stat 为准,Bonferroni 仅作无置换条件时的保守上界。
