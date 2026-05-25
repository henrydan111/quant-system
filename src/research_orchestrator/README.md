# Research Orchestrator

## Current Status (2026-04-10)

- All built-in profiles are now **DAG-only**.
- `ResearchProfile` no longer carries a `runner` field.
- The orchestrator root summary now reads only from **step outputs** plus root metadata.
- A strict release gate now exists at [workspace/scripts/research_orchestrator_release_gate.py](../../workspace/scripts/research_orchestrator_release_gate.py). It reruns the formal orchestrator audit and returns a non-zero exit code if any finding remains open or any coverage check is not `passed`.
- Remaining built-in profiles that were still using large legacy execution blocks have now been split into explicit staged handlers:
  - `factor_screening`
  - `ml_signal_model_research`
  - `strategy_improvement`
  - `benchmark_audit`
- The canonical run model is now:
  - compile request -> build DAG -> execute step by step -> persist per-step state -> resume safely when hashes match

## Hypothesis Workflow Addendum (2026-04-11)

- Formal non-audit runs now carry a typed `Hypothesis`.
- The gate flow is now explicit: `gate_evaluation -> gate_concern_scoring -> gate_review`.
- `gate_concern_scoring` pauses with `pause_for_input` and expects a schema-validated `gate_concern_scores.json`.
- `gate_review` writes `gate_report.json` / `gate_report.md`, records the automated verdict, then pauses with `pause_for_gate` until a human decision is written.
- The workflow now has dedicated stores for:
  - `hypothesis_registry`
  - `testing_ledger`
  - `holdout_seal`
- Sealed-OOS enforcement now has two choke points:
  - `SealedBacktestRunner` for orchestrator-owned backtest execution
  - `cache_manifest.py` + `qlib_windowed_features.py` for window-aware Qlib feature access
- `workspace/scripts/hypothesis_cli.py` now supports `draft`, `register`, `score-concerns`, `approve`, `reject`, and static templates under `workspace/scripts/templates/`.
- The detailed lifecycle rules now live in `.agents/rules/research-integrity.md` Section 10.


`research_orchestrator` 是这套量化系统里的统一研究编排层。

它的职责不是重新发明因子、信号或回测逻辑，而是把现有研究能力组织成一套标准研究流程，让不同研究类型都能：

- 用同一种请求格式发起
- 按标准步骤执行
- 在失败后从中间继续
- 统一记录元信息、产物、血缘和结果摘要

可以把它理解成“研究流程调度台”，而不是某一个具体策略脚本。

## 1. 它负责什么，不负责什么

### 负责

- 研究请求校验
- profile 到 DAG 的编译
- 步骤级执行与状态落盘
- 正式对象解析
- 统一研究产物目录
- registry 发布
- review / metadata 汇总

### 不负责

- 原始数据下载
- 原始数据清洗和标准化
- PIT ledger 构建
- Qlib backend 构建和发布

这些仍然归 [`src/data_infra/`](../data_infra/)。

换句话说，`research_orchestrator` 的边界是：

**从“数据已经准备好，可以研究”开始，到“研究结果已经被记录和发布”结束。**

## 2. 现在的执行模型

当前版本已经从“一个 profile 对应一个大 runner”升级成了 **DAG 编排**。

核心思想是：

- `profile` 负责把请求编译成一张研究步骤图
- `step handler` 负责执行单一步骤
- `runtime` 负责顺序、状态、续跑和产物

第一版 DAG 有两个明确取舍：

- 只做 **串行执行**
- 优先保证 **正确性、可恢复性、可审计性**

还没有做并行节点调度。

## 3. 核心概念

### 3.1 ResearchRequest

定义在 [schema.py](./schema.py)。

它描述的是“这次要做什么研究”，核心字段包括：

- `profile_id`
- `mode`
- `consumes`
- `produces`
- `requested_capabilities`
- `inputs`
- `run_context`
- `hypothesis`

### 3.2 ResearchProfile

定义在 [profiles.py](./profiles.py)。

它描述的是“一类研究模板”，包括：

- 支持哪些 mode
- 吃什么对象
- 产什么对象
- 默认能力板块
- 如何把 request 编译成 DAG

### 3.3 AssetRef

也是定义在 [schema.py](./schema.py)。

它表示“我要消费哪个正式对象”，当前支持：

- `universe`
- `label`
- `factor`
- `composite_factor`
- `signal`
- `model`
- `portfolio_template`
- `strategy_candidate`

### 3.4 CompiledResearchDag

定义在 [dag.py](./dag.py)。

它是编译后的研究图，主要包含：

- `run_dir`
- 一组 `DagStepSpec`
- 步骤依赖关系
- 计划级 metadata

### 3.5 StepExecutionContext / StepExecutionResult

也定义在 [dag.py](./dag.py)。

你可以把它们理解成：

- `StepExecutionContext`：一步执行时能看到的上下文
- `StepExecutionResult`：这一步执行后交回来的结果摘要

## 4. 通用能力板块

能力板块定义在 [capabilities.py](./capabilities.py)。

它们不是具体脚本，而是研究链路里的通用模块。

### 4.1 Core Research

- `data_scope`
- `data_readiness`
- `dataset_build`
- `universe_builder`
- `label_builder`
- `factor_construction`
- `factor_discovery`
- `signal_search`
- `model_training`
- `portfolio_construction`
- `risk_overlay`
- `vectorized_backtest`
- `event_driven_backtest`
- `execution_validation`
- `stress_test`
- `performance_diagnostics`

### 4.2 Diagnostic

- `benchmark_audit`

### 4.3 Support

- `object_resolver`
- `gate_review`
- `registry_publish`
- `experiment_tracking`
- `report_render`

Current honesty note:

- `data_scope`
- `data_readiness`
- `performance_diagnostics`
- `report_render`

These names still exist in the capability vocabulary, but they should be treated as planned / partial placeholders rather than fully independent research stages.

兼容说明：

- 旧的 `portfolio_assembly` 仍然会自动归一化成 `portfolio_construction`

## 5. 当前内置 profile

当前内置了 6 类正式研究类型：

- `factor_screening`
- `theme_strategy`
- `event_driven_signal_research`
- `ml_signal_model_research`
- `strategy_improvement`
- `benchmark_audit`

这些 profile 现在都会先编译成 DAG，再由 runtime 执行。

## 6. 标准步骤集合

当前 orchestrator 的通用积木是：

1. `object_resolver`
2. `data_scope`
3. `data_readiness`
4. `dataset_build`
5. `universe_builder`
6. `label_builder`
7. `factor_construction`
8. `factor_discovery`
9. `signal_search`
10. `model_training`
11. `portfolio_construction`
12. `risk_overlay`
13. `vectorized_backtest`
14. `event_driven_backtest`
15. `execution_validation`
16. `stress_test`
17. `performance_diagnostics`
18. `benchmark_audit`
19. `registry_publish`
20. `experiment_tracking`
21. `report_render`

并不是每个 profile 都会用到全部步骤。

## 7. 统一 CLI

统一入口在：

- [workspace/scripts/research_orchestrator_cli.py](../../workspace/scripts/research_orchestrator_cli.py)

当前支持 4 个核心命令。

### 7.1 查看内置 profile

```powershell
E:\量化系统\venv\Scripts\python.exe `
  E:\量化系统\workspace\scripts\research_orchestrator_cli.py `
  profiles
```

### 7.2 只编译计划，不执行

```powershell
E:\量化系统\venv\Scripts\python.exe `
  E:\量化系统\workspace\scripts\research_orchestrator_cli.py `
  plan --request-file E:\量化系统\workspace\configs\example_request.json
```

这个命令很适合先确认：

- 会跑哪些步骤
- 顺序是什么
- 最终输出目录是什么

### 7.3 正式执行

```powershell
E:\量化系统\venv\Scripts\python.exe `
  E:\量化系统\workspace\scripts\research_orchestrator_cli.py `
  run --request-file E:\量化系统\workspace\configs\example_request.json
```

### 7.4 从已有 run_dir 续跑

```powershell
E:\量化系统\venv\Scripts\python.exe `
  E:\量化系统\workspace\scripts\research_orchestrator_cli.py `
  resume --run-dir E:\量化系统\workspace\outputs\some_run
```

### 7.5 固定 release gate

`research_orchestrator_cli.py` 负责 request 驱动的研究运行；针对 orchestrator 本身的“是否允许发布 / 合并”检查，使用单独的 release gate：

```powershell
E:\量化系统\venv\Scripts\python.exe `
  E:\量化系统\workspace\scripts\research_orchestrator_release_gate.py `
  --theme-run-dir E:\量化系统\workspace\outputs\orchestrator_audit_probe\theme_quick_real_v3
```

这个脚本会：

- 重新执行正式 orchestrator 审计
- 生成一份新的 gate 目录到 `workspace/outputs/orchestrator_release_gate/<timestamp>/`
- 只有在下面两个条件都满足时返回 `0`
  - `findings.csv` 没有 `open` / `risk` 行
  - `coverage_matrix.csv` 的所有检查都是 `passed`

Release gate 输出包括：

- `release_gate_summary.json`
- `release_gate_report_zh.md`
- `audit/` 子目录下的完整审计产物
- `workspace/outputs/orchestrator_release_gate/latest_run.json`

## 8. 续跑规则

当前续跑规则比较严格，这是故意的。

只有同时满足下面条件才允许自动续跑：

- 使用同一个 `run_dir`
- `request_hash` 一致
- `plan_hash` 一致

如果请求内容变了，或者编译出的 DAG 变了，系统会直接拒绝续跑，而不是“猜测你想接着跑什么”。

这样做更安全，也更容易排查问题。

## 9. 标准 run 目录结构

一个 DAG run 完成后，根目录通常会看到：

- `dag_plan.json`
- `dag_state.json`
- `run_metadata.json`
- `artifact_manifest.json`
- `produced_objects.json`
- `review_summary.json`

每个步骤还会有自己的目录：

- `steps/<step_id>/step_metadata.json`
- `steps/<step_id>/step_outputs.json`
- `steps/<step_id>/artifact_manifest.json`

### 9.1 `dag_plan.json`

记录编译后的研究图，包括：

- request 快照
- request hash
- plan hash
- 步骤列表
- DAG 级 metadata

### 9.2 `dag_state.json`

记录运行时状态，包括：

- 当前 run 状态
- 已完成步骤数
- 失败步骤 id
- 每一步的状态、开始时间、结束时间

### 9.3 `run_metadata.json`

这是根级总摘要，通常会包括：

- `research_profile`
- `research_mode`
- `execution_model`
- `effective_capabilities`
- `effective_capability_metadata`
- `request_hash`
- `plan_hash`
- `resume_policy`
- `completed_step_count`
- `failed_step_id`

如果底层研究脚本本身会产出自己的 metadata，orchestrator 也会把那些关键信息合并进来。

### 9.4 `review_summary.json`

这是更适合快速看的结果摘要，会告诉你：

- 用了什么 profile
- 命中了多少 formal / candidate object
- 产出了多少对象
- 这轮 run 的目录在哪
- DAG 一共多少步，完成了多少步

## 10. Registry 和 Resolver

当前 orchestrator 已经接上这些 registry：

- `factor_registry`
- `candidate_registry`
- `signal_registry`
- `model_registry`
- `strategy_registry`

`formal` 模式下，如果 profile 需要 resolver，系统会显式执行 `object_resolver` 步骤。

它的规则可以简单理解成：

1. 先找 formal registry
2. 找不到再看 candidate / typed registry
3. formal run 里如果关键输入找不到，就直接阻断

## 11. Theme Strategy 在这套架构里的位置

`theme_strategy` 现在不再被看作“特殊系统”。

从 orchestrator 视角看，它只是某个 profile，内部大致对应：

- `theme` = 研究 preset
- `universe_builder` = 选股票池
- `factor_construction` = 生成 component
- `factor_discovery` = component 诊断和筛选
- `signal_search` = recipe 搜索
- `event_driven_backtest` = 正式确认

当前版本里，主题研究已经能编译成 DAG，并且支持 quick event-driven 的裁剪图。

## 12. 当前成熟度

已经比较稳的部分：

- request / result schema
- capability board
- DAG 编译
- 串行 DAG runtime
- step 状态落盘
- resume 规则
- 6 个内置 profile 的 DAG 化
- theme_strategy 的 quick event-driven DAG 裁剪

还在继续演进的部分：

- 真正细粒度的步骤实现
- 并行节点调度
- universe 作为 resolver / registry 一等对象
- 更细的 signal / strategy canonical identity

## 13. 推荐阅读顺序

如果你想快速理解这套 orchestrator，建议按这个顺序看：

1. [README.md](./README.md)
2. [schema.py](./schema.py)
3. [capabilities.py](./capabilities.py)
4. [dag.py](./dag.py)
5. [profiles.py](./profiles.py)
6. [runtime.py](./runtime.py)
7. [steps.py](./steps.py)
8. [engine.py](./engine.py)

如果你更关心具体研究怎么接进来，再去看：

- [src/alpha_research/theme_strategy/cli.py](../alpha_research/theme_strategy/cli.py)
- [workspace/research/alpha_mining/event_driven_strategy_research.py](../../workspace/research/alpha_mining/event_driven_strategy_research.py)
- [workspace/research/alpha_mining/event_driven_strategy_ml_research.py](../../workspace/research/alpha_mining/event_driven_strategy_ml_research.py)
- [workspace/research/alpha_mining/event_driven_strategy_improvement.py](../../workspace/research/alpha_mining/event_driven_strategy_improvement.py)
