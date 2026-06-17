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

## GPT verdict (2026-06-17): CHANGES REQUIRED → folded; broad direction APPROVED

All 6 answers confirmed: (1) build the faithful `sign_conditional_std`, zero-fill is proxy already held
by `risk_downvol`; (2) shadow lines inline `Greater`/`Less`, no named operator, drop `shadow_line` from
the manifest; (3) limit-day exclusion ONLY for up/down vol; (4) register BOTH `_avg` and `_std`; (5)
windows 20/60/120; (6) dedup calls approved. Four blocking contract fixes (B1–B4) are folded in below.

### B1 — `sign_conditional_std` operator contract (full)

```yaml
operator_id: sign_conditional_std
input:
  ret:    adjusted close-to-close daily return, PIT-shifted (Ref(...,1))
  sign:   down | up
  window: 20 | 60 | 120
  exclude_limit_days: true
selection:
  down: ret < 0 ; up: ret > 0
  ret == 0:                excluded (flat day, neither up nor down)
  suspended / NaN ret:     excluded
  limit day (see B2):      excluded
aggregation:
  std over SELECTED observations ONLY (NOT zero-fill; non-selected are ignored, not 0)
  ddof:            match Qlib Std exactly (certify reference-vs-vectorized against Qlib Std on a full mask)
  min_selected_obs: 2   ; below threshold -> NaN (NOT 0 — a 1-down-day stock must not read "low vol")
  all-nonmatching window:  NaN
```

Certification (§10A, no truth parity): golden cases (hand-computed subset std, incl. the
`[-2%,+1%,+1%,+1%]` down case where subset=std([-2%])→NaN at min_obs=2 vs zero-fill>0), property
(scale-invariance of dispersion up to scale, sign-symmetry up↔down on a flipped panel), reference
(slow numpy subset-std) vs vectorized random panels, PIT (future-row perturbation invariance), and a
**limit-basis test** (B2).

### B2 — limit-day basis safety (most likely silent bug)

Limit prices `$up_limit`/`$down_limit` are RAW exchange prices; our returns/shadows use ADJUSTED OHLC
(`raw × adj_factor`). **Never compare adjusted close to raw limit.** Decision = **Option A**: compute the
limit-day flag on **raw** PIT-shifted prices — `limit_day(t) = Ref($close,1) >= Ref($up_limit,1) OR
Ref($close,1) <= Ref($down_limit,1)` — while the return entering the std is the **adjusted** return.
Flag-from-raw, return-from-adjusted (they are different quantities; the flag marks the event, the value
is the adjusted return). A golden test pins a split-day where adjusted-vs-raw confusion would misflag.

### B3 — registration count = **36** new (not ~33)

down/up subset std 2×3=6 · highlow avg+std 2×3=6 · upshadow avg+std 2×3=6 · downshadow avg+std 2×3=6 ·
W-upshadow avg+std 2×3=6 · W-downshadow avg+std 2×3=6 = **36**. Plus **3 exact dedups**
`vol_std_{20,60,120}` → `risk_vol_{20,60,120}d` (skipped). Both `_avg` and `_std` registered (chart-16
faithfulness; chart-100's use of only selected `*_std_6M` is a composite recipe, not a reason to omit).

### B4 — `vol_std` dedup interpretation LOCKED

**Interpretation locked: limit-day exclusion applies ONLY to `vol_down_std`/`vol_up_std`. Plain
`vol_std` is `Std(ret, N)` with NO limit exclusion → exact-deduped to `risk_vol_{20,60,120}d` (skipped).**
If a future reading applies 剔除涨跌停 to plain return vol too, this dedup is void and `vol_std_exlimit_*`
must be registered distinctly.

## Build plan (GPT-approved, B1–B4 folded)

1 custom P-OP `sign_conditional_std` (build + §10A certify, incl. B2 limit-basis test) · `Greater`/`Less`
first-use semantic + PIT verification (no named operator) · **36 new draft factors** · 3 exact dedups
skipped · v2 manifest `required_operators` corrected to `sign_conditional_std` only (drop `shadow_line`) →
register draft → 7-domain matrix → P-GATE ceiling → IS-gate. resolve-but-label; no promotion here.
