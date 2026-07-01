# CICC Wave E1c — liquidity (chart 28) factor-logic spec

> Pre-registration factor logic for the E1c tranche, to be GPT-reviewed BEFORE registration (mirrors
> the E1a/E1b logic reviews). Source: handbook chart 28 in
> [CICC_价量因子定义.md](../../../Knowledge/AI量化增强/CICC_价量因子定义.md) §3. **No custom operator**
> needed — all inline arithmetic (`Mean`/`Std`/`Abs`/division on existing approved fields).

## Scope: 7 subtypes × 3 windows {20,60,120} = 21 → 19 new (2 exact dedups; see GPT verdict below)

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

**19 new** (after the B3 guard-vs-dedup resolution: amihud_avg_20d is guarded → NEW): turn_avg(1: 120) + turn_std(3) + vstd(3) + amihud_avg(3: incl. guarded 20d) + amihud_std(3) + shortcut_avg(3) + shortcut_std(3); **2 exact dedups** (turn_avg_20/60 only).

## GPT verdict (2026-06-18): CHANGES REQUIRED → folded; APPROVE registration (no operator build)

GPT confirmed: no custom operator, 20/60/120, vstd is a single window ratio, `liq_turn_std`/`liq_vstd` ≠
`liq_vol_cv`, adjusted-OHLC shortcut. Four blocking fixes (B1–B4) folded in below — the headline is that
**guarding the Amihud denominator makes `liq_amihud_avg_20d` ≠ the unguarded `liq_amihud_20d`** → it's a
NEW factor → **19 new, 2 dedups** (not 18/3).

### B1+B2 — denominator guards (all amount + the vstd return-std denominator)

```
amt   = Ref($amount, 1)
ret   = ADJ_CLOSE_T1 / Ref(ADJ_CLOSE, 2) - 1
amihud_day   = If(amt > 0, Abs(ret) / amt, NaN)
shortcut_day = If(amt > 0, (2*(H-L) - Abs(O-C)) / amt, NaN)          # H/L/O/C = adjusted, PIT-shifted (B4)
liq_vstd_N    = If(Std(ret, N) > 0, Sum(amt, N) / Std(ret, N), NaN)  # single window ratio (no avg/std split)
```
`If(cond, x, NaN)` is established inline arithmetic (used by 18 catalog factors) → still no operator.

### B3 — guard-vs-dedup conflict resolved → 19 new, 2 dedups

Guarded `liq_amihud_avg_20d` ≠ unguarded `liq_amihud_20d` → **register it (new, guarded)**, do NOT skip.
Only the 2 turnover dedups remain (`liq_turn_avg_{20,60}` ≡ `liq_turnover_{20,60}d`, both `Mean(Ref($turnover_rate,1),N)`).

### B4 — shortcut basis = adjusted OHLC (recorded)

`H/L/O/C = Ref($high/$low/$open/$close × $adj_factor, 1)` (split-robust, project convention). Manifest note:
`price_basis: adjusted_OHLC; replication_note: split-robust project convention; raw-K-line vendor basis not independently truth-parity-certified`.

### Build set (19 new drafts, GPT-approved)

```
liq_turn_avg_120d                       (1; turn_avg_20/60 dedup to liq_turnover_{20,60}d)
liq_turn_std_{20,60,120}d               (3)
liq_vstd_{20,60,120}d                   (3; guarded)
liq_amihud_avg_{20,60,120}d             (3; guarded — 20d NEW, not deduped)
liq_amihud_std_{20,60,120}d             (3; guarded)
liq_shortcut_avg_{20,60,120}d           (3; adjusted, guarded)
liq_shortcut_std_{20,60,120}d           (3; adjusted, guarded)
```

## Plan (GPT-approved, B1–B4 folded)

Define the 19 guarded inline factors (no operator) → register draft → v2 manifest expand chart-28
(19 factor-level rows + catalog_factor_id + the adjusted-basis note) → 7-domain matrix → P-GATE →
IS-gate. resolve-but-label; no promotion here.
