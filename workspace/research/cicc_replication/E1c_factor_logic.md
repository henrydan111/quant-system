# CICC Wave E1c — liquidity (chart 28) factor-logic spec

> Pre-registration factor logic for the E1c tranche, to be GPT-reviewed BEFORE registration (mirrors
> the E1a/E1b logic reviews). Source: handbook chart 28 in
> [CICC_价量因子定义.md](../../../Knowledge/AI量化增强/CICC_价量因子定义.md) §3. **No custom operator**
> needed — all inline arithmetic (`Mean`/`Std`/`Abs`/division on existing approved fields).

## Scope: 7 subtypes × 3 windows {20,60,120} = 21 → 18 new (3 exact dedups)

Naming `liq_{type}_{avg|std}_{20,60,120}d`. Per-day quantity `Ref(...,1)`-wrapped (PIT), then `Mean`/`Std`.
Fields: `$turnover_rate`, `$amount`, `$adj_factor`, `$close`, `$high`, `$low`, `$open` (all approved).

| subtype | per-day quantity | handbook |
|---|---|---|
| turnover avg/std | `$turnover_rate` | mean/std of 换手率 over N |
| vstd | `Sum($amount,N) / Std(ret,N)` (window-level ratio) | Σ成交额 / 收益率std |
| Amihud avg/std | `Abs(ret) / $amount` | mean/std of (\|日收益率\|/成交额) |
| shortcut avg/std | `(2*(high−low) − Abs(open−close)) / $amount` | (日K线最短路径/成交额); 最短路径=2×(高−低)−\|开−收\| |

## Dedup vs existing catalog (handbook flags `liq_turnover_*`/`liq_amihud_20d`/`liq_vol_cv` as 同源)

- **`liq_turn_avg_{20,60}` ≡ `liq_turnover_{20,60}d`** = `Mean(Ref($turnover_rate,1),N)` — IDENTICAL → **EXACT dedup, skip**. `liq_turn_avg_120d` → new (no `liq_turnover_120d`).
- **`liq_amihud_avg_20d` ≡ `liq_amihud_20d`** = `Mean(Abs(ret)/Ref($amount,1),20)` — IDENTICAL → **skip**. `liq_amihud_avg_{60,120}` → new.
- `liq_turn_std_*`: existing `liq_vol_cv_20d` = Std($vol)/Mean($vol) (volume CV) and `liq_turnover_skew_20d` (skew) are DIFFERENT → register (std of turnover, distinct).
- `liq_vstd_*` (Σamount/ret_std): distinct from `liq_vol_cv` (volume CV) → register.
- `liq_amihud_std_*`, `liq_shortcut_{avg,std}_*` → all new.

**18 new** = turn_avg(1: 120) + turn_std(3) + vstd(3) + amihud_avg(2: 60,120) + amihud_std(3) + shortcut_avg(3) + shortcut_std(3); **3 exact dedups** (turn_avg_20/60, amihud_avg_20).

## Open questions for GPT

1. **Shortcut price basis**: the formula `2*(high−low) − |open−close|` is a *price-range* (not a ratio). Use **adjusted** OHLC (`raw × adj_factor`, split-robust + consistent with the project's cross-day convention), or **raw** to literally match the handbook K-line? (Recommend adjusted — a raw price-range / raw-amount ratio is split-distorted; the existing `liq_amihud` already mixes adjusted-return / raw-amount, and a range needs the adjusted basis to be comparable across splits. The Amihud/vstd use returns which are already adjusted ratios, so only the shortcut numerator faces this.)
2. **vstd window semantics**: `Σamount(N) / Std(ret,N)` — window-level ratio (sum of amount over N ÷ return-std over N), NOT a per-day-then-aggregate. Confirm this matches 成交额/收益率std (a single ratio per date over the trailing window), with `avg/std` not applying (vstd is itself the metric; only one variant per window). The handbook lists `liq_vstd_{1M,3M,6M}` (3, no avg/std split) — so 3, not 6. ✓ already counted as 3.
3. **Dedup calls**: confirm `liq_turn_avg_{20,60}`→`liq_turnover` skip + `liq_amihud_avg_20`→`liq_amihud_20d` skip (identical expressions), and `liq_turn_std`/`liq_vstd` register as distinct from `liq_vol_cv`.
4. **Amihud `$amount` zero/NaN guard**: suspended days have amount=0/NaN → `Abs(ret)/amount` = inf/NaN. Guard with `If($amount>0, …, NaN)`? (The existing `liq_amihud_20d` does NOT guard — Mean skips NaN but inf would poison. Recommend adding an `$amount>0` guard for the new ones + note the existing is unguarded.)
5. **Windows 20/60/120** (project monthly convention) — OK?

## Plan after GPT review

Define the 18 new factors (inline expressions, no operator) + dedup map → register draft → v2 manifest
expand chart-28 (factor-level rows + catalog_factor_id, like E1b) → 7-domain matrix → P-GATE → IS-gate.
resolve-but-label; no promotion here. (Lighter than E1b — no operator build/cert.)
