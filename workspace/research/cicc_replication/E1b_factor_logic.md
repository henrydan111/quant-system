# CICC Wave E1b — volatility (chart 16) factor-logic spec

> Pre-registration factor logic for the E1b tranche, to be GPT-reviewed BEFORE any operator build /
> registration (mirrors the E1a logic review). Source: handbook chart 16 transcribed in
> [CICC_价量因子定义.md](../../../Knowledge/AI量化增强/CICC_价量因子定义.md) §2. Test window in the
> handbook: 2010.01.04–2022.07.01, monthly, 10-group, full + CSI300/500/1000.

## Scope: 13 subtypes × 3 windows {1M,3M,6M} = 39 templates

Project monthly convention (E1a precedent: 1M=20, 1Y=250): **1M=20, 3M=60, 6M=120** trading days —
which exactly matches the existing `risk_vol_{20,60,120}d` windows. Naming `vol_{type}_{avg|std}_{20,60,120}d`.
Per-day inputs use **adjusted** OHLC; the per-day quantity is wrapped in `Ref(...,1)` for PIT-safety
(predict next-day), then aggregated by `Mean`/`Std` over the window.

| # | subtype | per-day quantity | agg | handbook formula |
|---|---|---|---|---|
| 1 | return vol | `ret = adj_close[t-1]/adj_close[t-2]−1` | Std | std of daily returns |
| 2 | down vol | down-day returns (ret<0), **limit-excluded** | Std(subset) | std of adjusted returns, days with 涨跌幅<0 |
| 3 | up vol | up-day returns (ret>0), **limit-excluded** | Std(subset) | std of adjusted returns, days with 涨跌幅>0 |
| 4-5 | intraday amplitude | `high/low` | Mean, Std | mean/std of (最高价/最低价) |
| 6-7 | norm. upper shadow | `(high − max(open,close))/high` | Mean, Std | (最高价−max(开,收))/最高价 |
| 8-9 | norm. lower shadow | `(min(open,close) − low)/low` | Mean, Std | (min(开,收)−最低价)/最低价 |
| 10-11 | Williams lower shadow | `(close − low)/low` | Mean, Std | (收−低)/低 |
| 12-13 | Williams upper shadow | `(high − close)/high` | Mean, Std | (高−收)/高 |

## Dedup vs existing catalog (handbook itself flags `risk_vol_*`/`risk_downvol_*`/`risk_range_ratio` as 同源)

- **`vol_std_{20,60,120}` ≡ `risk_vol_{20,60,120}d`** (`Std(ret, N)`, identical window) → **EXACT dedup, DO NOT register.**
- **`vol_down_std` / `vol_up_std` vs `risk_downvol_{20,60}d`**: the existing `risk_downvol` = `Std(If(ret<0, ret, 0), N)` — a **ZERO-FILL proxy** (non-down days set to 0, kept in the std). The handbook construction is a **SUBSET std over only the sign-matching days, AND limit-excluded** (剔除涨跌停日). These are **not equal** (zero-fill changes the mean+count). → `vol_down_std`/`vol_up_std` are a **distinct, more-faithful construction**, not a dedup. (See operator decision below.)
- **`vol_highlow_{avg,std}` vs `risk_range_ratio_20d`**: existing = `Mean((high−low)/close, 20)`; handbook = `Mean(high/low, N)`. **Different formula** (ratio high/low vs range/close) → distinct, register.
- Shadow lines (4 subtypes) + `vol_highlow` → **all new**.

## Operator analysis — only ONE genuine custom operator

- **Shadow lines** = inline arithmetic on adjusted OHLC via Qlib elementwise **`Greater`**(max)/**`Less`**(min): upper `=(high−Greater(open,close))/high`, lower `=(Less(open,close)−low)/low`, Williams upper `=(high−close)/high`, Williams lower `=(close−low)/low`. **No custom operator** — but `Greater`/`Less` are **FIRST-USE in this catalog (0 current factors)** → require the same first-use semantic + PIT verification E1a did for `Rank`/`IdxMax`/`Sign` (elementwise max/min, NaN handling). ⇒ the manifest's `required_operators=[shadow_line]` is a **pre-registration mislabel** — correct it (drop `shadow_line`; shadow lines are built-in `Greater`/`Less` expressions), exactly as E1a's Q7 corrected `mmt_range`'s operator binding.
- **`sign_conditional_std`** (down/up vol) = the ONE genuine custom P-OP: **std over only the sign-matching, limit-excluded days** in the window. `If`+`Std` (the zero-fill proxy) is NOT faithful. Build + certify via the §10A harness (golden + property + reference-vs-vectorized + PIT; NO truth parity). Limit exclusion via `$up_limit`/`$down_limit` (precedent: `mmt_off_limit_*`).

## Open questions for GPT (before build/registration)

1. **Faithful subset-std vs zero-fill proxy** for `vol_down_std`/`vol_up_std`: build the genuine `sign_conditional_std` operator (true subset std, limit-excluded → `formula_equivalent`), or accept the tractable `If`+`Std` zero-fill as `proxy_approx`? (Recommend: build the faithful operator — the zero-fill changes the statistic, and the existing `risk_downvol` already occupies the proxy.)
2. **Shadow lines as inline `Greater`/`Less`** (no named operator) — agree, with first-use semantic verification + manifest `required_operators` correction (drop `shadow_line`)? Or insist on a named `shadow_line` operator for cert-store auditability?
3. **Limit-day exclusion**: for up/down vol only (handbook), or also shadow/highlow? (Handbook specifies it only for up/down vol.)
4. **avg vs std registration**: register BOTH `_avg` and `_std` per shadow subtype (handbook lists both), or only the std variants (the composite §chart-100 uses `*_std_6M`)? 
5. **Windows 20/60/120** confirmation (vs 21/63/126) — 20/60/120 makes `vol_std` an exact `risk_vol` dedup and matches the E1a monthly convention.
6. **Dedup calls**: confirm `vol_std`→`risk_vol` exact dedup (skip), and `vol_highlow`≠`risk_range_ratio` (register as distinct).

## Plan after GPT review

Operators (`sign_conditional_std` build+certify; `Greater`/`Less` first-use verify) → define the ~33
new factors (39 − 3 `vol_std` dedups − 3 if avg-only-drop) + dedup map → register draft → v2 manifest
`required_operators` correction → 7-domain matrix → P-GATE ceiling → IS-gate. resolve-but-label; no promotion here.
