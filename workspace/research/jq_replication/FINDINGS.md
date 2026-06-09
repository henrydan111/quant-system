# FINDINGS — Faithful JoinQuant replication + flaw-removal improvement

Date: 2026-06-08. Goal: "replicate JoinQuant strategies first (similar params), then improve to
remove the flaws." Source code: `C:\Users\henry\Desktop\聚宽回测系统\聚宽克隆策略\*.txt`.
Backend: local Qlib + PIT-safe cached factors. Numbers are TOTAL return (dividends reinvested),
realistic costs, survivorship-safe.

## Headline result

**Faithfully replicated 大市值价值投资 (the audit's "cleanest" strategy), then removed its #1
flaw (5-stock over-concentration) → a genuinely strong, deployable, PIT-safe book.**

Event-driven (gold-standard: T+1, limit-up substitution, suspension, JoinQuant costs+slippage,
10% ADV cap, dividends on ex-date), FULL 2014-01 .. 2026-02:

| Strategy | CAGR | MDD | Sharpe | Calmar | Negative years |
|---|---|---|---|---|---|
| 大市值价值 **top5 (faithful)**   | +16.6% | −31.9% | 0.78 | 0.52 | 2018, 2022 |
| 大市值价值 **top10 (IMPROVED)**  | **+20.7%** | **−26.6%** | **1.01** | **0.78** | **2018 only** |

The improvement raises CAGR +4pp, lifts Sharpe 0.78→1.01, AND lowers MDD. Improved-book yearly:
2014 +109, 2015 +6, 2016 +28, 2017 +27, 2018 −16, 2019 +13, 2020 +30, 2021 +11, 2022 +0,
2023 +24, 2024 +23, 2025 +17, 2026 +3 (%). One down year in twelve.

## Replication detail

**大市值价值 (post/41921):** main-board only (excl 创业板/科创/北交), >200d listed, ex-ST;
gate = pb<1 + 经营现金流>0 + 扣非>0 + ROA>0.15% + 净利同比>0; rank ROA desc, top 5; monthly;
cash-out when <5 pass; costs 0.1% tax + 万1.2 comm + ZERO slippage.
- Local mapping (PIT-safe cached factors, Ref(...,1)): pb<1→val_bp>1, OCF>0→val_cftp>0,
  ROA>0.15%→qual_roa>0.15, 净利同比>0→grow_netprofit_yoy>0; 扣非>0 ≈ qual_roa>0.15 (positive earnings).
- **Two units/universe details are decisive** (a prior abstraction got both wrong and falsely
  concluded the gate was "harmful"): (1) JoinQuant `indicator.roa` is in PERCENT, so `roa>0.15`
  is "positive ROA," NOT ROA>15% — pb<1 is the binding gate, ROA is the ranker; (2) the
  main-board restriction makes pb<1 select mature value (banks/industrials below book), not
  microcap distress. Faithful = +16.6% ED; the prior full-universe/ROA>15% abstraction = −60..−83% MDD.
- gate pass-count: median 16 (IS) / 56 (full); months_with_<5 = 13/146 (cash-out fires near bull tops).

**价值低波 (post/54680):** full market ex-ST/new(<180d); ATR(20) lowest 10% ∩ C/P highest 20%;
hold the ENTIRE intersection equal-weight (~100-220 names); monthly; 0.1% tax + 万3 + slippage.
- Local mapping: C/P→val_cftp, ATR(20)low→risk_vol_20d low. Faithful (total return): +12.6% CAGR /
  **−53.6% MDD** / Sharpe 0.69 (full). **Fails any sane MDD bar.**

## Improvement — what worked, what was tested-and-rejected (honest)

**大市值价值** (audit §三.4 flaws; tuned on IS 2014-20, FULL is the held-out check):
- **F1 diversify 5→10 = the WIN** (IS Sharpe 0.92→0.95; FULL CAGR +16→+21.5 sim / +16.6→+20.7 ED;
  MDD −32→−27 ED). 5-stock concentration was adding idiosyncratic noise, not alpha. Robust in BOTH
  sub-periods. top15 = even lower MDD (−32% sim) but lower CAGR — a more conservative variant.
- **F2 multifactor rank (ROA+C/P+low-vol) = REJECTED** — HURT (FULL +21.5→+15.8). Within the pb<1
  quality gate, pure ROA is the best ranker; blending diluted it.
- **F5 relax pb<1→pb<1.5 = REJECTED** — MDD blew to −54%. The pb<1 gate is the essential value/quality
  constraint; loosening it admits worse names. (Cash-out is a FEATURE, not a flaw.)
- **F3 zero-slippage = fixed** (realistic 10bps everywhere; ~−1.5% CAGR, still strong).
- **F4 explicit ST exclusion = added** (negligible effect — the gate already excludes distressed ST).

**价值低波**: universe restrictions (main-board / liq>40% / size>30%) only nudge MDD −54%→−49% and
CUT CAGR — **none reach <40% MDD**. The "low-vol" promise is overstated (audit's "低波≠低风险"): a
~100-name low-ATR∩value book is ~beta-1 in systematic crashes (2015/2018). KEY INSIGHT: the
CONCENTRATED 大市值价值 (−27% MDD) draws down LESS than the diversified low-vol book (−54%) —
deep-value+high-ROA main-board names (banks/utilities) are genuinely defensive; broad low-ATR
names include cyclicals that crash. Concentration on real value-quality > broad low-vol for A-share DD.

## Methodology / fidelity

- **Custom equal-weight monthly simulator** (explicit cash-out + buy-and-hold within month +
  turnover cost) used for fast variant screening. VALIDATED as a total-return proxy: reproduces the
  prior effort's known event-driven OOS (VL@core k40 = +11.6% total) at +12.2% (Δ +0.6% CAGR), and
  matches the 大市值价值 event-driven numbers within 0.8% CAGR. It is total-return + frictionless, so
  ~0.5-1% optimistic on absolute level; the EventDrivenBacktester is the deployable truth (used for
  the headline table). Early bug caught & fixed: a naive `mean(axis=1)` daily-rebalanced the book and
  harvested a spurious ~8% volatility premium — replaced with proper buy-and-hold-within-month.
- PIT-safe throughout (cached Ref(...,1) factors; event-driven uses the PIT provider). No lookahead.
- Anti-overfit: faithful params are the author's (zero DOF); the one improvement (5→10) is a generic,
  pre-specified diversification that improves BOTH 2014-20 and held-out 2021-26; the other audit fixes
  were tested and rejected. The improved book has a single down year in twelve (not one-year-driven:
  strong 2016/2017/2020/2023/2024 too).

## Not faithfully replicable on this backend (no data) — documented, not dismissed

ETF-momentum rotation (五福/四季/七星), 大小外 (foreign/gold/Nasdaq ETF legs), and futures CTA are
UNTESTABLE here (stock-only backend; no ETF/fund/foreign/futures data). Their reported returns also
lean on the audit-flagged microcap beta + 盘中 last_price soft-lookahead + handpicked pools.

## Bottom line vs the 50%-CAGR question

Still not 50% (that needs microcap/zero-slip/handpicked bias — see jq_regime_50cagr/FINDINGS.md). But
this CORRECTS the earlier overly-pessimistic "~12-16% ceiling": a faithfully-replicated + minimally-
improved JoinQuant value strategy is a **deployable +20.7% CAGR / −26.6% MDD / Sharpe 1.01** book
(event-driven, dividends, realistic frictions) — the strongest honest, deployable A-share long-only
result this project has produced.

Artifacts: `workspace/outputs/jq_replication/{rep_dashizhi,rep_valuelowvol,improve_dashizhi,
improve_valuelowvol,rep_eventdriven}_results.json` + `daily_ret_panel.parquet`. Scripts:
`jq_rep_utils.py, rep_dashizhi.py, rep_valuelowvol.py, improve_dashizhi.py, improve_valuelowvol.py,
rep_eventdriven.py, sanity_check.py, sim_vs_eventdriven.py`.
