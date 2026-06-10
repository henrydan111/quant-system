"""Collector for the FORMAL research-governance layer.

Surfaces what the orchestrator/hypothesis machinery records — distinct from the
informal `workspace/research` FINDINGS the research collector already shows:

- pre-registered hypotheses (`data/hypothesis_registry/hypothesis_events.parquet`)
- formal runs (each registry's `run_index.parquet`)
- status transitions (each registry's `status_history.parquet`)
- testing-ledger verdicts (`data/testing_ledger/testing_events_*.parquet`)
- OOS holdout-seal spends (`data/holdout_seals/holdout_events.parquet`)

Read-only. Every check is fail-soft (a missing/broken source → that table is
empty, never aborts the build).
"""
from __future__ import annotations

import json
import math
import os
import re
from typing import Any

from .util import PROJECT_ROOT, read_parquet

# event_driven_summary.json keys are "中文 (English)" — match on the exact English tag
# so we don't confuse Sharpe vs Excess Sharpe, Win Rate vs Daily Win Rate, etc.
_EDS_KEYS = [
    ("cagr", "(CAGR)"), ("total_return", "(Total Return)"), ("benchmark", "(Benchmark Return)"),
    ("excess", "(Excess Return)"), ("sharpe", "(Sharpe)"), ("mdd", "(Max Drawdown)"),
    ("ir", "(Information Ratio)"), ("beta", "(Beta)"), ("alpha", "(Alpha)"),
    ("win_rate", "(Win Rate)"), ("vol", "(Strategy Vol)"), ("days", "(Trading Days)"),
]


def _read_json(path: str):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _resolve_run_dir(run_dir: str) -> str:
    """Absolute run_dir as stored; fall back to re-rooting the workspace/ tail under PROJECT_ROOT."""
    if run_dir and os.path.isdir(run_dir):
        return run_dir
    m = re.search(r"workspace[\\/].*", run_dir or "")
    if m:
        cand = PROJECT_ROOT / m.group(0).replace("\\", "/")
        if cand.is_dir():
            return str(cand)
    return run_dir or ""


def _stage_metrics(run_dir: str, stage: str) -> dict:
    """Real backtest performance for one gate stage, read from its run artifacts.

    event_driven_summary.json → CAGR/total/benchmark/excess/Sharpe/MDD/IR/beta/alpha/winrate/vol/days;
    diagnostics/metrics.json → annual_turnover + rank_icir. Fail-soft → {} when absent.
    """
    if stage not in ("is_only", "oos_test"):
        return {}
    rd = _resolve_run_dir(run_dir)
    if not rd:
        return {}
    suf = "is" if stage == "is_only" else "oos"
    base = os.path.join(rd, "steps")
    m: dict = {}
    eds = _read_json(os.path.join(base, f"validation_event_backtest_{suf}", "event_driven_summary.json"))
    if isinstance(eds, dict):
        for field, tag in _EDS_KEYS:
            for k, v in eds.items():
                if k.endswith(tag):
                    m[field] = v
                    break
    diag = _read_json(os.path.join(base, f"validation_diagnostics_{suf}", "metrics.json"))
    if isinstance(diag, dict):
        for src, dst in (("annual_turnover", "turnover"), ("rank_icir", "rank_icir")):
            if diag.get(src) is not None:
                m[dst] = diag.get(src)
    return m

_REGS = [
    ("factor", "factor_registry", "factor_id"),
    ("candidate", "candidate_registry", "candidate_id"),
    ("signal", "signal_registry", "object_id"),
    ("model", "model_registry", "object_id"),
    ("strategy", "strategy_registry", "object_id"),
]


def _s(v) -> str:
    if v is None:
        return ""
    try:
        if isinstance(v, float) and math.isnan(v):
            return ""
    except Exception:
        pass
    return str(v)


def _parse(v):
    if not isinstance(v, str):
        return v if isinstance(v, dict) else None
    try:
        return json.loads(v)
    except Exception:
        return None


def _round(v):
    try:
        f = float(v)
        return "" if math.isnan(f) else (f"{f:.3f}".rstrip("0").rstrip("."))
    except Exception:
        return _s(v)


def _fmt_expected(ee, sign) -> str:
    if not isinstance(ee, dict):
        return ""
    txt = f"{ee.get('statistic', '效应')} ≈ {_round(ee.get('point_estimate'))}"
    lo, hi = ee.get("ci_low"), ee.get("ci_high")
    if lo is not None and hi is not None:
        txt += f"（CI {_round(lo)}–{_round(hi)}）"
    if ee.get("horizon_days"):
        txt += f" @ {ee.get('horizon_days')}d"
    if sign:
        txt += f"，方向 {sign}"
    return txt


def _fmt_bar(sc) -> str:
    if not isinstance(sc, dict):
        return ""
    labels = [("min_rank_icir", "rank_icir≥"), ("min_deflated_sharpe", "deflated_sharpe≥"),
              ("min_cost_adjusted_sharpe", "cost_adj_sharpe≥"), ("max_drawdown", "MDD≤"),
              ("max_annual_turnover", "turnover≤"), ("max_correlation_to_approved", "corr≤")]
    parts = []
    for k, lbl in labels:
        v = sc.get(k)
        if v not in (None, ""):
            parts.append(f"{lbl}{_round(v)}")
    return " · ".join(parts)


def collect_governance() -> dict:
    out: dict[str, Any] = {"hypotheses": [], "runs": [], "status_changes": [],
                           "verdicts": [], "seals": [], "counts": {}, "error": None}
    try:
        # 1) pre-registered hypotheses → per-hypothesis STORYLINE
        #    测什么 = registration (thesis/mechanism/expected/bar/factors)
        #    每步证实了什么 = each gate_decision's criteria pass/fail + decision_reason
        #    结论 = final decision (+ its reason)
        h = read_parquet(PROJECT_ROOT / "data" / "hypothesis_registry" / "hypothesis_events.parquet")
        if h is not None and len(h):
            seq = "event_sequence" if "event_sequence" in h.columns else "recorded_at"
            has_et = "event_type" in h.columns
            for hid, g in h.groupby("hypothesis_id"):
                g = g.sort_values(seq)
                reg = g[g["event_type"] == "registration"] if has_et else g.iloc[0:0]
                d = (_parse(reg.iloc[0].get("hypothesis_json")) if len(reg) else None) or {}
                refs = d.get("factor_refs") or []
                factors = [_s(f.get("object_name")) for f in refs
                           if isinstance(f, dict) and f.get("object_name")]
                bar = _fmt_bar(d.get("success_criteria"))
                dh = g["design_hash"].dropna() if "design_hash" in g.columns else []
                design = _s(dh.iloc[-1])[:10] if len(dh) else ""
                prof = g["profile_id"].dropna() if "profile_id" in g.columns else []
                profile = _s(prof.iloc[-1]) if len(prof) else ""
                # timeline of steps
                steps: list[dict] = []
                is_metrics: dict = {}
                oos_metrics: dict = {}
                status, conclusion, headline, final_hardfail = "registered", "", "", 0
                for _, e in g.iterrows():
                    kind = _s(e.get("event_type")) if has_et else ""
                    when = _s(e.get("recorded_at"))[:16]
                    if kind == "registration":
                        steps.append({"stage": "预注册", "date": when, "decision": "registered",
                                      "criteria": [], "reason": ("design " + design + (f"；成功标准 {bar}" if bar else ""))})
                        continue
                    if kind not in ("gate_decision", "manual_override"):
                        continue
                    cr = _parse(e.get("criteria_results_json")) or []
                    crit = [{"metric": _s(c.get("metric")), "actual": _round(c.get("actual")),
                             "comp": _s(c.get("comparator")), "threshold": _round(c.get("threshold")),
                             "passed": c.get("passed"), "hard": bool(c.get("is_hard"))}  # passed tri-state: True/False/None
                            for c in cr if isinstance(c, dict)]
                    dec = _s(e.get("decision")) or kind
                    gstage = _s(e.get("gate_stage"))
                    label = gstage or ("人工干预" if kind == "manual_override" else "闸")
                    sm = _stage_metrics(_s(e.get("run_dir")), gstage)
                    if sm:
                        if gstage == "is_only":
                            is_metrics = sm
                        elif gstage == "oos_test":
                            oos_metrics = sm
                    steps.append({"stage": label, "date": when, "decision": dec,
                                  "criteria": crit, "reason": _s(e.get("decision_reason"))[:340]})
                    if _s(e.get("decision")):
                        status = _s(e.get("decision"))
                        conclusion = _s(e.get("decision_reason"))[:340]
                        final_hardfail = sum(1 for c in crit if c["passed"] is False and c["hard"])
                        for c in crit:
                            if c["metric"] in ("rank_icir", "rank_ic"):
                                headline = f"{c['metric']} {c['actual']}"
                                break
                last_stage = steps[-1]["stage"] if steps else ""
                summary = status
                if last_stage and last_stage != "预注册":
                    summary += "（" + last_stage + (f" {headline}" if headline else "") + "）"
                if final_hardfail and status in ("approved", "promoted", "passed"):
                    summary += f" ⚠超{final_hardfail}硬闸"
                # regime-artifact flag: OOS Sharpe ≫ IS Sharpe AND IS drew down hard
                # → the OOS window was likely a single benign regime; true risk lives in IS.
                regime_warn = ""
                try:
                    iss, oss, ismdd = is_metrics.get("sharpe"), oos_metrics.get("sharpe"), is_metrics.get("mdd")
                    if iss is not None and oss is not None and ismdd is not None \
                            and float(oss) > 1.8 * float(iss) and float(ismdd) > 0.35:
                        regime_warn = (f"OOS Sharpe {float(oss):.2f} ≫ IS {float(iss):.2f}，且 IS 全样本最大回撤 "
                                       f"{float(ismdd) * 100:.0f}% — OOS 封存窗很可能是单一良性制度，"
                                       f"真实风险/可部署预期看 IS 全样本（年化 ~{float(is_metrics.get('cagr') or 0) * 100:.0f}%）")
                except Exception:
                    pass
                out["hypotheses"].append({
                    "id": _s(hid), "status": status, "profile": profile, "design": design,
                    "thesis": _s(d.get("thesis_statement")), "mechanism": _s(d.get("mechanism"))[:420],
                    "expected": _fmt_expected(d.get("expected_effect"), d.get("expected_sign")),
                    "bar": bar, "factors": factors,
                    "universe": _s(d.get("universe")), "benchmark": _s(d.get("benchmark")),
                    "rebalance": _s(d.get("rebalance_frequency")),
                    "steps": steps, "summary": summary, "conclusion": conclusion,
                    "is_metrics": is_metrics, "oos_metrics": oos_metrics, "regime_warn": regime_warn,
                    "last": _s(g["recorded_at"].max())[:16] if "recorded_at" in g.columns else "",
                })
            out["hypotheses"].sort(key=lambda x: x["last"], reverse=True)

        # 2) formal runs — union the 5 registry run_index tables
        for label, reg, _id in _REGS:
            df = read_parquet(PROJECT_ROOT / "data" / reg / "run_index.parquet")
            if df is None:
                continue
            for r in df.to_dict("records"):
                prof = _s(r.get("research_profile") or r.get("research_type") or r.get("run_type"))
                detail = []
                for k in ("theme", "stage", "status", "artifact_count", "benchmark"):
                    if r.get(k) not in (None, "") and not (isinstance(r.get(k), float) and math.isnan(r.get(k))):
                        detail.append(f"{k}={_s(r.get(k))}")
                if r.get("start_date"):
                    detail.append(f"{_s(r.get('start_date'))[:10]}→{_s(r.get('end_date'))[:10]}")
                out["runs"].append({
                    "registry": label, "run_id": _s(r.get("run_id")), "run_type": _s(r.get("run_type")),
                    "profile": prof, "generated_at": _s(r.get("generated_at"))[:16],
                    "detail": " · ".join(detail)[:120],
                })
        out["runs"].sort(key=lambda x: x["generated_at"], reverse=True)

        # 3) status transitions — union the 5 registry status_history tables
        for label, reg, idcol in _REGS:
            df = read_parquet(PROJECT_ROOT / "data" / reg / "status_history.parquet")
            if df is None or not len(df):
                continue
            ic = idcol if idcol in df.columns else ("object_id" if "object_id" in df.columns else df.columns[0])
            for r in df.to_dict("records"):
                out["status_changes"].append({
                    "registry": label, "object_id": _s(r.get(ic)),
                    "old": _s(r.get("old_status")), "new": _s(r.get("new_status")),
                    "reason": _s(r.get("reason"))[:80], "changed_at": _s(r.get("changed_at"))[:16],
                })
        out["status_changes"].sort(key=lambda x: x["changed_at"], reverse=True)

        # 4) testing-ledger verdicts (+ a measurement count)
        import glob
        frames = []
        for f in glob.glob(str(PROJECT_ROOT / "data" / "testing_ledger" / "testing_events_*.parquet")):
            df = read_parquet(f)  # type: ignore[arg-type]
            if df is not None:
                frames.append(df)
        n_meas = 0
        if frames:
            import pandas as pd
            t = pd.concat(frames, ignore_index=True)
            n_meas = int((t.get("event_kind") == "measurement").sum()) if "event_kind" in t.columns else 0
            v = t[t["event_kind"] == "verdict"] if "event_kind" in t.columns else t
            for r in v.to_dict("records"):
                out["verdicts"].append({
                    "recorded_at": _s(r.get("recorded_at"))[:16], "hypothesis_id": _s(r.get("hypothesis_id")),
                    "profile": _s(r.get("profile_id")), "stage": _s(r.get("stage")),
                    "verdict": _s(r.get("verdict")), "test": _s(r.get("test_name")),
                    "stat": f"{_s(r.get('statistic_name'))} {_s(r.get('statistic_value'))}".strip(),
                    "sharpe": _s(r.get("sharpe")), "reason": _s(r.get("decision_reason"))[:80],
                })
            out["verdicts"].sort(key=lambda x: x["recorded_at"], reverse=True)
        out["counts"]["measurements"] = n_meas

        # 5) OOS holdout-seal spends
        s = read_parquet(PROJECT_ROOT / "data" / "holdout_seals" / "holdout_events.parquet")
        if s is not None:
            for r in s.to_dict("records"):
                out["seals"].append({
                    "recorded_at": _s(r.get("recorded_at"))[:16], "hypothesis_id": _s(r.get("hypothesis_id")),
                    "design": _s(r.get("design_hash"))[:10], "seal_key": _s(r.get("seal_key"))[:10],
                    "profile": _s(r.get("profile_id")), "stage": _s(r.get("stage")), "run_dir": _s(r.get("run_dir")),
                })
            out["seals"].sort(key=lambda x: x["recorded_at"], reverse=True)

        out["counts"].update({
            "hypotheses": len(out["hypotheses"]), "runs": len(out["runs"]),
            "status_changes": len(out["status_changes"]), "verdicts": len(out["verdicts"]),
            "seals": len(out["seals"]),
        })
    except Exception as e:  # pragma: no cover
        out["error"] = f"{type(e).__name__}: {e}"
    return out
