# 因子等级与收录标准 · Factor Status Ladder & Registration Criteria

> 一页速查。深入版见同目录 [README.md](README.md);强制不变量见 [CLAUDE.md](../../../CLAUDE.md) §3.5。
> *English readers: this is the quick-reference for "what do draft/candidate/approved mean, and when
> should a factor be registered?" — the followable deep-dive is README.md.*

---

## 0. 一句话(最容易搞反的一点)

- **`draft` 是地板(默认起点),不是奖励。** 因子**写进代码库的那一刻就自动是 draft**,不需要任何测试。
- **"成为 draft" = 被收录进因子库(一个主动决定)**;**"升级" = 通过测试**(样本内 / 样本外)。
- 你**不可能"考不上 draft"**。只要在库里,它至少就是 draft;再往下只有 `deprecated`(退役)。

测试是用来把因子从 draft **往上抬**的,不是用来"进入" draft 的。方向别搞反。

---

## 1. 三个等级

| 等级 | 含义 | 怎么得到 | 谁能用 |
|---|---|---|---|
| **`draft`** | 已收录,但**没有任何证明** | 写进 [catalog.py](../factor_library/catalog.py) → `sync_catalog_to_registry` 同步成 draft 行 | 所有 discovery / sandbox 研究(忽略 status) |
| **`candidate`** | 通过**样本内(IS)**体检,"值得花 OOS 预算" | `factor_lifecycle` IS-only 关卡:`\|RankICIR\| ≥ 0.10` 且 年度符号一致性 ≥ 0.70 | 仅当正式 run 显式 opt-in(`allow_candidate_components`) |
| **`approved`** | 通过**样本外(OOS)**终检,可部署级 | sealed-OOS gate:独立 OOS 复现 + 干净 git 提交 + holdout seal(一次性消费);门槛 `OOS RankICIR > 0` 且 `OOS LS Sharpe > 1.0` | 正式 validation,始终可用 |
| ~~`deprecated`~~ | 退役 / 失败 | — | — |

---

## 2. 关键区别:**sandbox 测试 ≠ 收录**

> 在 sandbox 里回测一个表达式(自定义 `compute_factors` dict),它**不是**系统里的因子,**不是 draft**,测完就丢。

一个因子要"算数"(成为 draft),必须**主动收录**两步:

1. 把定义写进 [catalog.py](../factor_library/catalog.py)(PIT-safe:每个 `$field` 包在 `Ref(...)` 里);
2. `sync_catalog_to_registry(...)` 把目录同步进注册表(写成 draft 行)。

**例(本项目 2026-06-08 OSAP 实验):** triage 纸面筛了 **212** 个已发表因子 → 回测了 **8** 个 → 只有 **1 个(`qual_gross_profitability`)**通过全部样本内关卡,才被**收录**成 draft → 升到 candidate(最后 OOS 失败,停在 candidate)。**其余 7 个连 draft 都不是 —— 不是"不够格当 draft",而是我们故意没收录**(冗余 / 过拟合,加进库只会污染目录)。

---

## 3. 什么时候该把一个因子收录成 draft(实用判断标准)

**技术上** draft 不需要任何证据(draft = 未证明)。但**收录 = 往正式因子库加东西,会进入所有 discovery/screening**,所以不能随便加。收录前应满足:

- ✅ **经济逻辑清晰** —— 有 paper / 机制,不是纯数据挖掘;
- ✅ **PIT-safe** —— 每个 `$field` 在 `Ref(...)` 框架内(用 `ADJ_*_T1` 常量;基本面锚 `ann_date`);
- ✅ **数据已获批** —— `$field` 在 [field_status.yaml](../../../config/field_registry/field_status.yaml) 是 `approved`(否则收录后会是 field-ineligible 的 draft,测不了);
- ✅ **基本 IS 体检过得去** —— RankIC / RankICIR 有意义,符号符合先验;
- ✅ **边际贡献为正** —— 对现有 catalog 有正交增量(marginal IC × 低相关),**不是已有因子的重复**。这是本项目的核心教训:按 standalone ICIR 选会选到重复因子;要按边际贡献选(见 [[reference_factor_selection_marginal_not_icir]] / README §marginal)。
- ✅ **命名规范** —— `{category}_{name}_{lookback}`。

**不该收录(留 sandbox / 丢弃):** 与已有因子高相关、边际≈0 的重复;纯数据挖掘无逻辑;一次性诊断 / 研究表达式。

### 为什么 draft 也会"污染"因子库?(关键 —— 看似矛盾,其实不)

因为系统有**两个平面**,而 **discovery 平面故意忽略 status**:

- **正式 validation 平面**(status-gated):draft **进不去** → **污染不了**,这层是安全的。
- **discovery / research 平面**(`get_factor_catalog()` 忽略 status,42 个调用点):draft 是**完全活跃的参与者** —— 进所有 screen / 相关性矩阵 / 边际分析 / composite 构建 / 全市场 compute。

所以"污染"全发生在 discovery 层,主要代价:

1. **多重比较失真(最重要)** —— catalog 越大 = 被筛的候选越多 = 纯靠运气"看起来好"的假阳性越多;screen 挑出的"最好"越不可信,deflated-Sharpe / 多重检验校正被迫更严。本项目被烧过(val_heavy 抽奖簇、新数据 0/8 screen)。
2. **相关性 / 边际分析变噪** —— 一堆近似重复塞进相关矩阵,marginal 选择被冗余簇主导。
3. **计算成本** —— 每个 draft 每次 screen / compute 都被全市场算一遍(忽略 status)。
4. **垃圾抽屉** —— catalog 本应是"每个都有理由"的精选集;乱塞 → 分不清原则 vs 噪声(治理 / revalidation 也要反复重算它们)。

> 不是"draft = 坏"。一个有逻辑的 draft(如 GP)完全没问题。"污染"是**累积的、针对冗余 / 未筛因子** —— 正因为 discovery 是 status-blind 的,§3 的收录门槛(尤其**边际贡献**)就是用来挡住噪声淹没 discovery 层。

---

## 4. 各级之间怎么走(实操)

| 转换 | 工具 | 门槛 |
|---|---|---|
| 收录成 **draft** | 写 catalog.py → `sync_catalog_to_registry` | 无硬门槛(用 §3 的实用标准判断"值不值得加") |
| draft → **candidate** | `factor_lifecycle` IS gate:[phase6_setup_request.py](../../../workspace/scripts/phase6_setup_request.py) → `research_orchestrator_cli.py run` → [phase6_drive_gates.py](../../../workspace/scripts/phase6_drive_gates.py) | `\|RankICIR\| ≥ 0.10` 且 年度符号一致性 ≥ 0.70(样本内,不碰 OOS) |
| candidate → **approved** | sealed-OOS 驱动(参考 [promote_sealed_oos_winners.py](../../../workspace/scripts/promote_sealed_oos_winners.py));live 写注册表前**先 commit + 用户确认**(§13) | `OOS RankICIR > 0` 且 `OOS LS Sharpe > 1.0`(独立复现,一次性消费 OOS) |

> ⚠ candidate → approved 会**一次性消费**该 frozen set 的 OOS 窗口(spend-on-attempt):失败 = 窗口烧掉,因子停在 candidate。务必在干净已提交的树上、确认后再跑。

---

## 5. 为什么有一堆因子"停在 draft"?(draft 档里其实有三种)

draft 不是单一含义,它是"还没升上去"的总和:

1. **还没跑** IS 关卡;
2. 跑了但**没通过** IS 关卡(`RankICIR` 不到 0.10 或符号不稳);
3. **数据没获批**,根本测不了(field-ineligible,如依赖 quarantine 数据集的因子)。

这三种**都停在 draft —— 因为 draft 是地板,不会再往下掉**(再下面只有 deprecated)。所以"停在 draft"≠"失败收录",它就是"在库里、还没被抬上去"。

---

## 6. 当前真实分布(**不要硬记数字 —— 实时查**)

- catalog 总数:`catalog_composition()`(单一真相来源,自动随新增因子更新);
- 注册表分布:读 `data/factor_registry/factor_master.parquet` 的 `is_current` 行,按 `status` 计数。

截至 2026-06-08 大致为「少量 approved + 数十 candidate + 数十 draft」,但**以实时查询为准**(数字会变,故意不写死,见 [CLAUDE.md](../../../CLAUDE.md) §3.5)。

---

## 7. 两条不变量(别违反)

1. **`get_factor_catalog()` 对所有 discovery / sandbox 忽略 status** —— status 只在**正式 validation** 里 gate 组件,从不限制研究。
2. **status 只能通过 gate 升级,不能手改文件** —— 写 `approved` 需要 `current_git_sha` + 通过 promotion gate 的 `promotion_evidence`(独立 PIT-correct OOS 复现,sandbox/loader panel 不算)。
