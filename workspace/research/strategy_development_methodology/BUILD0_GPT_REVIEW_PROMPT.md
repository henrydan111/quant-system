# BUILD-0 TC PoC — GPT §10 cross-review prompt (round 1)

Self-contained prompt for GPT-5.5 Pro. HEAD to review: the commit adding
[build0_tc_poc.py](../../scripts/build0_tc_poc.py) + [BUILD0_TC_POC_FINDINGS.md](BUILD0_TC_POC_FINDINGS.md)
on branch `calendar-unfreeze`. `guorn_optimize_09.py` is **local-only (not on the remote)** → its reused
functions are embedded inline below so the reviewer can audit the PIT-safety of the reuse.

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. A single lookahead, a spent out-of-sample window, or a survivorship-filtered universe invalidates the result even if every test passes. Be skeptical, surface blockers, and do not rubber-stamp. This is an IS-only, design-stage PoC (no sealed OOS spent, reversible) — but its VERDICT will be recorded to durable memory and re-scope a build roadmap, so a wrong or over-claimed conclusion is the failure mode to catch.

REPO (public — fetch any file to verify against the live code)
https://github.com/henrydan111/quant-system   (branch: calendar-unfreeze)
Raw file form: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/<path>

CONTEXT — read these to judge the change against the contract:
- CLAUDE.md  (hard invariants §3, PIT §3.2, sealed-OOS §3.4, research integrity §7, no-hedge §7.10, no-leverage §7.11)
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/CLAUDE.md
- The methodology this PoC is the first empirical task OF (read §1.1 TC diagnosis, §S2 Grinold-α, §S3 light construction + the 4-condition optimizer gate, §4.5 lever ranking):
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/strategy_development_methodology/STRATEGY_DEVELOPMENT_METHODOLOGY_v1.0.md
- The script under review (authoritative — fetch it):
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/scripts/build0_tc_poc.py
- The findings under review (authoritative — fetch it; the verdict + all numbers live here):
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/strategy_development_methodology/BUILD0_TC_POC_FINDINGS.md
- (local-only, NOT on the remote — the reused functions are EMBEDDED below): workspace/scripts/guorn_optimize_09.py

SELF-REVIEW PREFLIGHT — completed before this GPT request.
VERDICT: clean for GPT. Two adversarial multi-agent workflows already ran and their findings are folded in: (1) a 4-lens DESIGN red-team, which found the FIRST-CUT verdict logic BROKEN (its TC leg was carried entirely by a tautological holdings-TC term → TC had zero decision weight; its return leg read Sharpe-OR-CAGR with MDD never read) and mis-headlined a tautological TC — REBUILT to net-Sharpe-primary + MDD-guard + paired-bootstrap significance, with TC removed from the gate (descriptive only) and the full-eligible calibrated TC as the headline; (2) a 2-lens FINDINGS verification, which reconciled every number bit-for-bit against the artifacts and softened three over-claims (a factual "neither uses σ" error; a sigcomp-vs-invvol TC mis-ranking; and three places where an association was promoted to established causation — now marked "consistent with … resolving test = …").
§3/§7/§8 checks: PIT §3.2 — factors are Ref(...,1) (via the reused catalog); comp/σ/top-K read only data ≤ pday=T-1 (σ uses ret.loc[:pday].tail(60), identical convention to the trusted build_opt_signal covariance input); the composite IS-IC uses comp(≤T-1) vs fwd_5d[d] over [d,d+5] with no overlap and feeds only a diagnostic, never a trade; no raw pit_ledger read, no hand-rolled alignment — all PIT flows through the reused g09._composite_series. §7.3 — no OOS path exists in the script (IS 2014-2020 only; sealed 2021-2026 untouched). §7.7 survivorship — universe is the full-market broad mask (listed ∧ ¬ST ∧ close≥2) from the trusted harness; delisting handled by the engine. §7.10 — hedge words scrubbed; causal claims not established are marked as such with the resolving test named. §7.11 — every book long-only, weights sum to 1, gross ≤ 1×, unlevered. §8 four-layer — factor(full market)→universe(boolean mask)→signal(rank within eligible top-K)→execution(tradability ONLY in the engine). §9 multiplicity — 5 constructions disclosed as an implicit family; the verdict is negative (ADJUST) so no false-positive is being promoted; no DSR/PBO claimed (design-stage, no promotion, no seal).
RESIDUAL CONCERNS for the reviewer: (a) σ is a TOTAL-vol proxy, not residual/idio vol — this correctly labels `alpha`(∝σz)/`invvol`(∝z/σ) as pedigree-approximate and gives `alpha` a high-vol tilt; whether residual σ changes the faithful-`alpha` verdict is UNTESTED (BUILD-0b). (b) Underpowered: paired-bootstrap 95% CIs are wide on one IS window → the honest claim is "construction is not a DETECTABLE lever here", not "no effect". (c) The positive causal attribution (style tilts drive the spread) is consistent-with the w~size/w~vol signs, not established (resolving test = regress the 5 books' returns on size/low-vol factor returns). (d) Scope: n=1 well-conditioned non-microcap value book — the case §S3 assigns to the OPTIMIZER, the opposite of the micro-tail lane §S3 prescribes light construction for; this PoC does NOT settle the micro-tail lane. (e) Absolute IS numbers are IS-fitted (sign-orientation on the same window) → optimistic, not deployable.

WHAT CHANGED (authoritative — fetch build0_tc_poc.py + BUILD0_TC_POC_FINDINGS.md from the raw links above; the reused-but-local guorn_optimize_09.py functions are embedded below).

=== EXPERIMENT (from FINDINGS) ===
Question: the methodology's §1.1 prior is "deployable return is lost at the portfolio-construction step because rank→top-K→equal-weight throws away the cardinal signal (a transfer-coefficient TC collapse); a signal-proportional light construction should beat top-K/EW". A parallel result had already shown an MV OPTIMIZER (λ=2..100, pragmatic Ledoit-Wolf Σ) did NOT beat naive top-K on this book. Open question: does a LIGHTER signal-proportional construction beat equal-weight on NET risk-adjusted PnL?
Controlled experiment: the SAME top-30 names of the s3_core book (value+quality+low-vol, size+industry-neutralized composite `comp`, non-microcap), 5 weight vectors that differ ONLY in the weights, run through the IDENTICAL event-driven envelope (0.2%/side, slippage 0, volume_limit 0.10, hold_on_limit_up, Model-I 5-day rebalance, benchmark 000300.SH, ¥1M, total-return), IS 2014-2020. Constructions:
  eqw     = 1/K                        (methodology low-TC baseline)
  alpha   = ∝ σ·z (Grinold α=IC·σ·z)   (§S3-literal target_w ∝ calibrated α — the METHODOLOGY-FAITHFUL primary)
  sigcomp = ∝ (comp − min + ε)         (the harness wmode="signal"; ∝ z, NOT α)
  invvol  = ∝ z/σ                      (MV-diagonal form; its holdings-TC=1 is a tautology)
  sqrtmv  = ∝ √circ_mv                 (#9's own weighting — a SIZE tilt; also a reuse cross-check)

=== RESULTS (from FINDINGS; all reconciled bit-for-bit against build0_results.json / build0_tc.json) ===
Step 1 — TC = corr(μ/σ, Δw·σ) (Clarke-de-Silva-Thorley), Δw vs equal-weight-over-eligible; calibrated μ=IC·σ·z ⇒ μ/σ=IC·z ⇒ TC=corr(z, Δw·σ). Composite IS rank-IC(5d) = +0.057; median eligible/date = 2865; 342 rebalances.
  construction | TC_full(headline) | TC_hold*(diagnostic) | eff-N | max_w | wt_turn | w~size | w~vol
  eqw          |      0.320        |       0.150          | 30.0  | 0.033 | 0.174   | flat   | flat
  alpha(∝σz)   |      0.286        |       0.408          | 26.1  | 0.070 | 0.185   | −0.16  | +0.86
  sigcomp(∝comp)|     0.262        |       0.941          | 15.5  | 0.135 | 0.193   | −0.05  | +0.15
  invvol(∝z/σ) |      0.338        |       1.000          | 27.3  | 0.061 | 0.189   | +0.16  | −0.79
  sqrtmv(∝√mv) |      0.284        |       0.032          | 21.8  | 0.113 | 0.198   | +0.95  | −0.17
  Headline (full-eligible, Fundamental-Law) TC does NOT support the §1.1 prior: it barely moves (all span 0.26-0.34), eqw sits near the top, the faithful alpha LOWERS it (ΔTC −0.034). Holdings-TC is a within-book diagnostic, TAUTOLOGICAL for any ∝signal weight (invvol=1.00 is algebra: w∝z/σ ⇒ Δw·σ∝z ⇒ corr=1) — never used to select a construction.
Step 2 — net-of-cost IS. Gate = net Sharpe primary (margin ≥0.10 AND paired-bootstrap p<0.10) + MDD-not-worse-by->2pp guard. TC is DESCRIPTIVE, not in the gate.
  construction | CAGR   | Sharpe | MDD     | vol   | eff-N | ΔSharpe vs eqw (bootstrap p)
  eqw          |+22.20% | 0.87   | −40.06% | 27.5% | 30.0  | baseline
  alpha        |+21.67% | 0.83   | −40.02% | 28.5% | 26.1  | −0.04 (p=0.76)
  sigcomp      |+20.96% | 0.80   | −42.22% | 29.2% | 15.5  | −0.07 (p=0.78)
  invvol       |+22.57% | 0.89   | −39.68% | 27.0% | 27.3  | +0.02 (p=0.23)
  sqrtmv       |+22.87% | 0.90   | −39.74% | 26.8% | 21.8  | +0.04 (p=0.33)
  #9 REPLAY    |+30.03% | 1.18   | −33.88% | 24.8% |  —    | (different NAMES — selection differs)
  reuse cross-check: my sqrtmv reproduces the cached g09 s3_core baseline BIT-FOR-BIT (max|Δ daily ret| = 0.0).
VERDICT: ADJUST. No signal-proportional construction beats equal-weight (the faithful alpha is worse, −0.04; every ΔSharpe is inside bootstrap noise). Net Sharpe is decoupled from holdings-TC (best-Sharpe sqrtmv has the near-lowest TC; the spread is consistent with incidental size/low-vol tilts, not signal transfer). Selection ≫ weighting is corroborated (not measured) by the +0.28 #9 gap and the external #9 26pp→~1pp tradeability result. → the deployable lever is signal-SELECTION + universe, not weighting; build the §S3 construction/risk stack (if at all) for risk/MDD control, not return. Scoped to this well-conditioned value book / one IS window; micro-tail lane untested.

=== REUSED-BUT-LOCAL guorn_optimize_09.py FUNCTIONS (audit these for PIT-safety of the composite + σ) ===
# pday = the PRIOR trading day (T-1) — the sole PIT anchor for all as-of reads:
def _pdays(grid_dates, trading_index) -> dict:
    out = {}
    for d in grid_dates:
        pos = trading_index.searchsorted(pd.Timestamp(d))
        if pos > 0:
            out[pd.Timestamp(d)] = trading_index[pos - 1]   # T-1
    return out

# neutralize a factor vs [1, log(circ_mv) (+ industry dummies)] over the broad ESTU, transform-then-mask:
def _neutralize(fval, logmv, ind, broad, mode):
    x = fval.where(broad)
    lo, hi = x.quantile(0.01), x.quantile(0.99); x = x.clip(lo, hi)
    if mode == "none":
        z = (x - x.mean()) / (x.std(ddof=0) or 1.0); return z.where(broad)
    ok = x.notna() & logmv.notna()
    if ok.sum() < 30: return pd.Series(np.nan, index=fval.index)
    cols_df = {"logmv": logmv[ok]}
    if mode == "size_ind":
        d = pd.get_dummies(ind[ok].astype("object").fillna("NA"), prefix="ind", drop_first=True)
        for c in d.columns: cols_df[c] = d[c].astype(float)
    X = pd.DataFrame(cols_df, index=x.index[ok]); X.insert(0, "const", 1.0)
    y = x[ok].astype(float)
    beta, *_ = np.linalg.lstsq(X.values, y.values, rcond=None)
    resid = y - X.values @ beta
    z = (resid - resid.mean()) / (resid.std(ddof=0) or 1.0)
    return z.reindex(fval.index)

# the SHARED composite generator build0 reuses — yields (d, pday, comp, broad) per rebalance date.
# comp = mean of IS-IC-oriented, neutralized z-scores over the eligible/broad set; NaN off-eligible.
# frames[f] are the cached Ref(...,1)-wrapped catalog factors; fr.loc[d]/v7._row(fr,d) read the factor value
# AS-OF the rebalance date d, prices/circ read at pday=T-1.
def _composite_series(cfg, cols, close, circ, frames, efr, ind_asof, bounds, rebal, pmap):
    ic = json.loads((CACHE / "is_ic.json").read_text())
    pool = cfg["pool"]
    sign = {f: (1.0 if ic.get(f, 0) >= 0 else -1.0) for f in pool}
    wmag = {f: (abs(ic.get(f, 0.0)) if cfg["weight"] == "ic" else 1.0) for f in pool}
    for d in rebal:
        pday = pmap.get(d)
        if pday is None: continue
        cr = close.loc[pday]
        st = ru.st_codes_on(d)
        listed = pd.Series([(bounds.get(str(c).upper()) is not None
                             and bounds[str(c).upper()][0] <= pday <= bounds[str(c).upper()][1])
                            for c in cols], index=cols)
        not_st = pd.Series([str(c).upper() not in st for c in cols], index=cols)
        broad = listed & cr.notna() & not_st & (cr >= 2.0).fillna(False)
        if broad.sum() < 30: continue
        logmv = np.log(circ.loc[pday].where(circ.loc[pday] > 0))
        ind = ind_asof.loc[pday] if (ind_asof is not None and pday in ind_asof.index) else pd.Series("NA", index=cols)
        comp = pd.Series(0.0, index=cols); wsum = pd.Series(0.0, index=cols)
        for f in pool:
            fval = (frames[f].loc[d] if d in frames[f].index else v7._row(frames[f], d)).reindex(cols)
            z = _neutralize(fval, logmv, ind, broad, cfg["neut"]) * sign[f]
            add = z * wmag[f]
            comp = comp.add(add.fillna(0.0), fill_value=0.0)
            wsum = wsum.add(add.notna().astype(float) * wmag[f], fill_value=0.0)
        comp = (comp / wsum.where(wsum > 0)).where(broad & _elig_mask(cfg["elig"], efr, d, pday, cols))
        yield d, pday, comp, broad

# the weighted-execution strategy build0 drives (weights_mode="explicit" → RAW weights, scaled down only if >1):
class ModelIDivLowVolStrategy(Strategy):
    def __init__(self, sched, *, max_holds=10, reserve=10, weights_mode="sqrt_mv"):
        super().__init__(); self.sched = {pd.Timestamp(k): v for k, v in sched.items()}
        self.max_holds, self.reserve = int(max_holds), int(reserve); self.weights_mode = weights_mode
    def before_market_open(self, context):
        from src.backtest_engine.event_driven.strategies import _emit_rebalance_orders
        today = pd.Timestamp(context.date); lst = self.sched.get(today)
        if lst is None: return []
        prices = {}; prev = context.prev_day_data
        if prev is not None and not prev.empty:
            prices = prev.set_index("ts_code")["close"].astype(float).to_dict()
        def tradable(code):
            p = prices.get(code); return p is not None and np.isfinite(p) and p > 0
        picks = []
        for item in lst:
            code, mv = (item[0], item[1]) if isinstance(item, (list, tuple)) else (item, np.nan)
            if len(picks) >= self.max_holds: break
            if tradable(code) and np.isfinite(mv) and mv > 0: picks.append((code, mv))
        if not picks: return _emit_rebalance_orders({}, context)
        if self.weights_mode == "explicit":
            tot = sum(mv for _, mv in picks); scale = 1.0 / tot if tot > 1.001 else 1.0
            target = {code: float(mv * scale) for code, mv in picks}
        else:
            w = np.sqrt(np.array([mv for _, mv in picks])); w = w / w.sum()
            target = {code: float(x) for (code, _), x in zip(picks, w)}
        return _emit_rebalance_orders(target, context)

QUANTITATIVE-RESEARCH PRINCIPLES — check the change against EACH; a violation is a Blocker
1. PIT / NO-LOOKAHEAD (cardinal). Does any value at time t use information not knowable at t? Audit: comp (via _composite_series, factors Ref(...,1), reads as-of d with prices/circ at pday=T-1), σ (_sigma_asof = ret.loc[:pday].tail(60), ≤ T-1), the composite IS-IC (comp[≤T-1] vs fwd_5d[d] over [d,d+5]) which feeds ONLY a diagnostic, and the top-K selection (on comp[≤T-1]). Is the sign-orientation (IS-IC over the SAME 2014-2020 window used for the composite) a lookahead, or only an in-sample-fit optimism that is common to all 5 constructions (so it doesn't bias the cross-construction delta)?
2. OUT-OF-SAMPLE IS SACRED. The script has no OOS path; IS 2014-2020 only; sealed 2021-2026 untouched. Confirm nothing selects on OOS.
3. SURVIVORSHIP. Universe = full-market broad mask (listed ∧ ¬ST ∧ close≥2); delisting handled by the engine. Confirm no filter to currently-listed-only.
4. FACTOR-EVAL STANDARD. N/A (not a factor promotion; no registry write, no seal).
5. EXECUTION & COST REALISM. Event-driven, total-return, T+1, limits, suspension inherited from the trusted engine; 0.2%/side flat cost = the #9/JoinQuant parity envelope (intentional for the controlled comparison), NOT realistic_china. Is the ABSOLUTE-Sharpe-vs-EW-eligible-TC benchmark mismatch adequately handled (the write-up says do not cross-cite TC→IR)?
6. NO LEVERAGE. All 5 books long-only, weights sum to 1, gross ≤ 1×.
7. NO HEDGE WORDS. Every quantitative claim backed by an artifact, or marked unverified with the resolving test. Flag any residual hedge or any certainty asserted without the data.
8. FOUR-LAYER PIPELINE. factor(full market)→universe(boolean mask)→signal(rank within eligible top-K)→execution(tradability only in the engine).
9. MULTIPLE TESTING. 5-construction implicit family disclosed; verdict is negative so no false-positive promoted; is that disclosure sufficient given the +0.02/+0.04 invvol/sqrtmv edges are cited (even though dismissed as insignificant)?

REVIEW QUESTIONS
1. Correctness — is the TC operationalization (Clarke-de-Silva-Thorley) right, the "IC scalar washes out ⇒ calibrated TC = corr(z, Δw·σ)" algebra right, and the invvol-TC=1.00 correctly labeled a tautology (not an edge)? Any bug in _weight_vectors, _tc_pair, _sigma_asof, the paired block-bootstrap (_boot_sharpe_diff), or the schedule-building (dot/underscore code format, weights-sum-to-1 vs the strategy's >1.001 rescale)?
2. Verdict logic — is the rebuilt gate (net Sharpe primary + meaningful margin + bootstrap p + MDD guard, TC removed) sound and correctly conservative? Is "ADJUST / construction is a weak, undetectable lever here" the honest conclusion, or is it over- or under-claimed given the wide CIs?
3. Governance / scope — does the write-up over-generalize past an n=1 well-conditioned value book on one IS window? Is the σ=total-vol proxy caveat, the selection-corroborated-not-measured framing, and the "does not settle the micro-tail lane" scope guard sufficient and correctly placed? Anything unsafe to record to durable memory?
4. Evidence — what proof is missing, and the exact test/command you'd run to confirm the load-bearing claims (esp. PIT-cleanliness of the reuse, and whether residual-σ would change the faithful-alpha verdict).

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending line/claim quoted and an exact suggested replacement. Map every Blocker to the principle or invariant it violates.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.
```
