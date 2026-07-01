# 中心化 HTML 看板 (Centralized Dashboard)

A single self-contained HTML board that projects the whole research system —
five content layers plus three action sections — and collects every Claude Code
session into a timeline. Read-only: it never mutates project data.

## What it shows

| 区块 | 来源 (实时读取，非复制) |
|---|---|
| 📌 事项（进行中 / 待办 / 推荐） | git 分支 + session 未完成 TodoWrite + Task-tool 任务 + 启发式 + 手编 `board.yaml` |
| 📚 知识层 | **数据源为上层目录 · 两级导航**（浅色主题）：**level-1** = `总览` + 每个活跃源一个标签（arXiv / OSAP / report_rc，读 `sources.yaml`）；**level-2**（每个源下，依其 `provides`）= **知识框架**（pipeline + **饱和地图** 跨源前沿，读 `taxonomy.py`+`research_map.parquet`，仅 arXiv）· **研究方向**（该源的 `research_directions.yaml` 精读卡，按**生命周期** 计划/进行中/已完成 过滤；已完成留档流程+结果时间线+结论，如 report_rc 下 C1 eps_diffusion approved-但不可部署、OSAP 下 C2 GP OOS-失败）· **价值内容**（arXiv=`ranked_papers.parquet` 价值排序论文；OSAP=212 信号三筛）。`总览` 页=源卡片(active/planned + 实时统计) + `strategy_kb`/文档/`MEMORY.md`。`.subnav2`/`.subview2` 两级 tab（JS `:scope>` 作用域隔离）。**扩展**：新增数据源 = `sources.yaml` 加一条 + 给方向/内容打 `source_kind`/`source` 标签，看板自动出标签页+其 framework/方向/内容。Chinese 经 Sonnet 译。 |
| 🗄️ 数据层 | `config/field_registry/field_status.yaml`（raw vs approved 的权威视图）+ `field_approval_log.jsonl` + `data/qlib_data/`（已注册标的/universe/日历）+ `data/` 磁盘数据域 |
| 🧮 因子层 | `data/factor_registry/factor_master.parquet` + `catalog_composition()` 实时派生 + `candidate_master.parquet` |
| 🔬 研究层 | 子导航三页：**非正式探索**（`workspace/research/*` FINDINGS）/ **正式研究治理**（`hypothesis_registry` 预注册假设 + 各 registry `run_index` 正式 run + `testing_ledger` 裁决 + `holdout_seals` OOS 花费 + `status_history` 状态变迁，[governance.py](src/dashboard/governance.py)）/ **里程碑**（`project_state.md` Update Notes） |
| 📈 策略层 | `strategy/signal/model` 注册表 + `board.yaml` 策展的可部署策略书（它们活在 FINDINGS，不在注册表） |
| 💬 会话 | `~/.claude/projects/e------/*.jsonl` 全量解析（首条指令 / 分支 / 工具直方图 / 改动文件 / commit / TodoWrite 终态 / 末条助手摘要） |

深层证据不复制——因子/策略表直接链到各注册表已有的 `*_review.html`。

## 交互（前端，纯 JS）

- **顶部无全局 KPI 卡带**；每层页首自带 lead 卡。顶部标签页切层 + 一个全局过滤框。
- **数据层子导航**：`全部数据集 ┃ Qlib universe ┃ 字段促进` 三个同级子页。「全部数据集」带**按状态筛选条**（approved/quarantine/raw…）+ 文本框，每个数据集可展开看**逐列中英文表**；「Qlib universe」是独立子页（universe 表 + 标的数 + 日历）。
- **因子层主从式**：顶部**状态/类别/文本筛选条**；汇总表是主列表，**点任一行就地展开**该因子的明细卡（中英文 + 表达式 + 成分 + 证据），不再平铺。**点表头列名排序**（▲/▼ 切换；数值列按数值、文本列按字典序——整格判定，`earn_..._60` 不会被当数字）；OSAP/信号表同样可排序。
- **研究层筛选**：三个子页各带 filterbar——正式治理页按**状态药丸**（approved/rejected/registered…）+ 文本（假设id/thesis/因子/profile）过滤故事线卡；研究线程页 + 里程碑页各带文本框。复用因子层的 `applyFilter`（`data-scope`/`data-row`/`.fhide`）。
- **正式研究治理 = 每假设一条故事线（全貌）**：治理页 ① 把每个 hypothesis 渲成一张可展开卡，四段讲清 **🎯 测什么**（thesis/机制/预期效应/**预先承诺的成功标准闸**/因子）→ **📊 实测表现**（从 run 工件 `validation_event_backtest_{is,oos}/event_driven_summary.json` + `validation_diagnostics_*/metrics.json` 实读，IS 全样本 vs OOS 封存窗**同口径并排**：年化 CAGR / Sharpe / 最大回撤(>35% 标红) / IR / Beta / 换手 / 胜率 / 同期基准 / 交易天数）→ **🪜 每一步证实了什么**（预注册→各 gate 时间线，每个 gate 把 `criteria_results_json` 渲成逐条 `metric actual ⋛ threshold` 的 ✓/✗ 药丸：绿=通过、红=**硬性**未过、琥珀=软性未达、灰=未计算）→ **🏁 最终结论**。**自动制度警示**：当 OOS Sharpe ≫ IS（>1.8×）且 IS 全样本 MDD>35% → 卡头加 **⚠制度依赖** 徽章 + 一条警示（"OOS 封存窗很可能是单一良性制度，真实风险看 IS 全样本"）——把"OOS 太好看"的回报立刻用 IS 现实打脸（如 lxr_005：OOS 107% CAGR/Sharpe 2.96/MDD 12% vs IS 20%/0.75/**49%**，且同期基准 OOS +51%/277日 是牛市）。折叠摘要一行 `thesis… → 终态（末闸关键指标）`；override 批准加红色 **⚠超N硬闸**。② run/裁决/封存/状态变迁明细表折叠进"原始治理记录"（仍可排序）。数据全部实时读取 `governance.py`。
- **md 文档页内查看**：点 `.md` 链接弹**页内模态框**渲染（不跳出）。用 `fetch` 读取，需经本地服务（浏览器禁止 file:// 双击时 fetch 本地文件）。**已配常驻服务，开机自动起、无需手动**：at-logon 计划任务 `QuantDashboardServe` 用 pythonw 跑静默 [`serve.py`](serve.py) 绑 `127.0.0.1:8799`。⇒ **浏览器收藏 `http://127.0.0.1:8799/` 或双击 [`open_dashboard.bat`](open_dashboard.bat)** 打开即可。`*_review.html` 与外链照常新标签打开；直接双击 `index.html`（file://）时 md 模态会提示走服务并给直开链接。
  - 为什么要 `serve.py` 而非 `python -m http.server`：stock http.server 把日志写 stderr，pythonw（无窗口）没有 stderr → 每个请求抛错返回空响应；`serve.py` 静默日志即可。`serve_dashboard.bat`（console 版 http.server）是**手动备用**。
  - 安全：仅绑 127.0.0.1（不出网）；http.server 不发 CORS 头 → 其它源无法读取本地文件（恶意网页 fetch 你的 localhost 也读不到响应）。
- **会话页**：每个会话显示**派生的精简标题** + 把 Task-tool 任务/TodoWrite 拆成 **✅ 已完成 / 🔵 进行中** 两组（头部计数、展开看明细）；无任务跟踪的会话以改动文件/commit/末条摘要体现。**同标题去重**：很多 session 用了相同开场白（重跑/自动续接）→ 按派生标题合并，只展示最近一条 + `×N 同标题` 计数（避免重复刷屏）。
- **🩺 数据新鲜度/一致性自审**（落地页顶部）：看板只能忠实反映源文件，无法保证源文件自身新鲜——所以每次重建由 [`health.py`](health.py) **自检源文件、落后即标红**：① catalog（代码实时算）vs registry 当前数（不一致=需 `sync_catalog`）；② Sonnet 翻译覆盖（缺口=新因子未译）；③ `project_state` 顶部 Update Note 日期 vs 最新 git 提交（落后=该补记录）；④ 最近 `run_daily_qa` 通过率+时效；⑤ 关键源文件（factor_master/field_status/project_state/qlib 日历/board.yaml/translations）最后修改时间一览。任一项 warn → 面板左边框转琥珀色。把"看板会不会显示旧数据"从隐患变成可见指标。
- **自动刷新（轻量轮询）**：构建时写一个几字节的根 `build_id.txt`（= 构建时间戳，已 gitignore），页面每 **30s** 拉一次比对页内烘焙的 `BUILD_ID`。有新构建时：**后台/空闲(>45s 无操作)的标签页静默 `location.reload()`，正在操作的标签页只弹一个"● 看板已更新 — 点击刷新"小条**（不打断你正在看的内容，点一下才刷）。`file://` 双击时 fetch 失败→静默跳过（仅常驻服务模式下生效）。

## 输出

- `index.html` — **看板本体放在项目根目录**（双击用浏览器打开，零外部依赖、可离线）。链接均为根相对路径（`data/...` / `Knowledge/...`），从根打开即可解析。
- `workspace/outputs/dashboard/data.json` — 机器可读快照
- `workspace/outputs/dashboard/.sessions_cache.json` — 按 mtime 的增量缓存（首次全量解析，之后只解析改动的 transcript）

以上均被 `.gitignore` 忽略（根 `index.html` 单独 ignore，data.json/cache 随 `workspace/outputs/` 一并 ignore），不入库。

## 手动构建

```bash
venv/Scripts/python.exe src/dashboard/build_dashboard.py            # 重建
venv/Scripts/python.exe src/dashboard/build_dashboard.py --open     # 重建并在浏览器打开
venv/Scripts/python.exe src/dashboard/build_dashboard.py --quiet    # 静默（钩子/定时任务用）
```

或双击 `src/dashboard/refresh_dashboard.bat`（重建并打开）。脚本会自举 `sys.path`，与运行目录无关。

## 自动更新机制（两路 + 手动）

1. **Claude session 结束钩子** — `.claude/settings.json` 里的 `SessionEnd` 钩子，每次 Claude Code session 结束直接调 `python.exe ... build_dashboard.py --quiet`。这是"把所有 session 信息汇入看板"的自动化落点。
   - ⚠️ 项目级钩子首次会让 Claude Code 弹窗请求信任授权；批准一次即可。
2. **Windows 定时任务** `QuantDashboardRefresh` — 每小时重建一次，作为钩子的兜底（也覆盖在 session 之外发生的数据/因子层变化）。
   - 改频率：`schtasks /Change /TN QuantDashboardRefresh ...`；删除：`schtasks /Delete /TN QuantDashboardRefresh /F`。
3. **手动** — 上面的命令 / `.bat`。

每次构建都把 INFO 摘要追加到 `logs/dashboard_build.log`（`--quiet` 只静默控制台，不静默文件）。

### Windows 中文路径的坑（已规避）

`.bat` 文件由 cmd.exe 按系统 OEM 代码页读取；硬编码中文路径 `量化系统` 的 `.bat` 在非交互（定时任务）下会乱码→找不到 python。因此：钩子与定时任务**都直接调 `python.exe`**（命令行按 Unicode 传递，且本仓库所有路径无空格，免引号）；`refresh_dashboard.bat` 用 `%~dp0` 让 .bat 正文保持纯 ASCII，运行时再展开真实 Unicode 路径。

## 人工策展层

`workspace/configs/dashboard_board.yaml` —— 放"机器推不出、需人脑判断"的条目：
`in_progress` / `todo` / `recommended`（叠加到自动派生之上，标 `board` 来源）、
`strategies`（可部署策略书）。编辑后重新构建即生效。

## 双语描述（Claude Sonnet 生成 + 缓存）

因子/类目/策略/研究线程的**中英文一句话描述由 Claude Sonnet 生成**，缓存在 `src/dashboard/translations.json`（committed）。构建时 `translate.py` 只**读缓存**（快、离线、免 API key）；命中不到的新因子返回空串（卡片留白，不报错）。数据层不走 Sonnet——`data_dictionary.md` 本就逐列中英文，由 `dictionary.py` 直接解析。

**刷新（新增因子后补译）—— 一键手动**：🩺 自审面板的"Sonnet 翻译覆盖"会标出缺口。补译**在一个正常 Claude 会话里**做（认证天然可用，无需 API key / token / 无人值守 agent）：

- **最简：在会话里输入 `/backfill-translations`**（[.claude/commands/backfill-translations.md](../../.claude/commands/backfill-translations.md)）—— 它让会话自动跑完：`detect`（找缺口、写 `_backfill_input.json`）→ 会话的 Sonnet 逐项生成中英文 → 写 `_backfill_output.json` → `merge`（合并进 `translations.json` 并清理）→ 重建。
- **手动两步**（等价）：
  1. `venv/Scripts/python.exe src/dashboard/backfill_translations.py detect`
  2. 让会话把 `_backfill_input.json` 译成 `_backfill_output.json`
  3. `venv/Scripts/python.exe src/dashboard/backfill_translations.py merge`

> 确定性 Python 负责 detect+merge，描述文本由会话模型生成。**不走无头 `claude -p`**——本机 Claude 认证是宿主/网关代理的，spawn 的无头进程拿不到（实测 401），故采用"会话内一键"而非无人值守计划任务。当前 `translations.json`：185 因子 + 17 类目 + 2 策略 + 16 线程 + **20 知识维度 + 8 研究方向 + 40 价值论文**（arXiv 知识框架，2026-06-10 起），零缺失。`backfill_translations.py` 的 `detect`/`merge` 已覆盖 `knowledge_dims`/`knowledge_directions`/`knowledge_papers` 三个新 section（论文只需 `cn` 一句话导读，标题保留英文）——未来再收割 arXiv 后跑一次 `/backfill-translations` 即补译新论文。

## 代码结构

整个看板是 `src/` 下的一个专属包 `src/dashboard/`（**只读报表工具，不是 6 个研究模块之一**，不应被任何正式研究路径 import）：

```
src/dashboard/
  build_dashboard.py   入口：collect → render → 写 根/index.html + workspace/outputs 的 data.json
  util.py              路径解析 / fail-soft 读取器 / git 助手（session 目录按 cwd 编码定位）
  sessions.py          transcript 解析 + 增量缓存
  dictionary.py        解析 data_dictionary.md → 逐数据集逐列中英文（35 集 / 661 列）
  translate.py         读取 Sonnet 生成的 translations.json 双语缓存
  translations.json    Sonnet 生成的因子/类目/策略/线程双语描述（缓存，committed）
  content.py           知识/数据/因子/研究/策略 五层富采集器（永不抛错，异常→区块内告警）
  actions.py           进行中/待办/推荐 派生 + board.yaml 合并
  render.py            自包含 HTML：顶部无大卡带，子导航/筛选条/因子主从/md 模态/会话任务
  serve.py             静默 http 服务（绑 127.0.0.1:8799，pythonw 安全），常驻任务调用
  open_dashboard.bat   一键开浏览器到常驻服务地址（推荐；或直接收藏 URL）
  serve_dashboard.bat  手动备用：console 版 http.server（任务没起时用）
  refresh_dashboard.bat  手动双击：重建并打开（用 %~dp0 保持纯 ASCII）
```

自动化（Windows 计划任务）：`QuantDashboardRefresh`（每小时重建 HTML）+ `QuantDashboardServe`（**at-logon 常驻服务**，开机自动起，无需手动）+ `.claude/settings.json` 的 `SessionEnd` 钩子（每次 session 结束重建）。

每个采集器都是 fail-soft：单个源损坏只会在该区块显示告警，不会让整次构建失败——因为看板是自动重建的 artifact，必须始终能产出。
