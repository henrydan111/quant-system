"""Collectors for the five content layers: knowledge, data, factor, research,
strategy. Each returns a plain dict and never raises (errors surface as an
``error`` key the renderer shows as a badge).

This is the *rich* version: data layer carries full bilingual per-column tables
(from data_dictionary.md), the factor layer carries factor_registry_review.html
parity (summary + per-factor detail + evidence + Sonnet bilingual descriptions), and the
knowledge layer carries the OSAP / arXiv / JoinQuant idea-sourcing corpus.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from .dictionary import parse_data_dictionary
from .translate import category_label, factor_desc
from .util import (
    PROJECT_ROOT,
    read_jsonl,
    read_parquet,
    read_text,
    read_yaml,
    rel,
)


def _first_heading(md: str | None) -> str:
    if not md:
        return ""
    for line in md.splitlines():
        s = line.strip()
        if s.startswith("#"):
            return s.lstrip("# ").strip()
    return ""


def _first_para(md: str | None, after_heading: bool = True) -> str:
    if not md:
        return ""
    lines = md.splitlines()
    i = 0
    if after_heading:
        while i < len(lines) and not lines[i].strip().startswith("#"):
            i += 1
        i += 1
    buf: list[str] = []
    for line in lines[i:]:
        s = line.strip()
        if not s:
            if buf:
                break
            continue
        if s.startswith("#"):
            if buf:
                break
            continue
        buf.append(s)
        if len(" ".join(buf)) > 300:
            break
    return re.sub(r"\s+", " ", " ".join(buf))[:320]


def _num(v, nd: int = 3) -> float | None:
    try:
        f = float(v)
        return None if math.isnan(f) else round(f, nd)
    except Exception:
        return None


def _s(v) -> str:
    if v is None:
        return ""
    try:
        if isinstance(v, float) and math.isnan(v):
            return ""
    except Exception:
        pass
    return str(v)


def _records(path: Path, limit: int | None = None) -> list[dict]:
    df = read_parquet(path)
    if df is None:
        return []
    if limit:
        df = df.head(limit)
    return [{k: (None if (isinstance(v, float) and math.isnan(v)) else v) for k, v in r.items()}
            for r in df.to_dict("records")]


def _parse_json(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    try:
        return json.loads(v) if isinstance(v, str) else v
    except Exception:
        return None


def _intish(*vals):
    for v in vals:
        try:
            if v is None or (isinstance(v, float) and math.isnan(v)):
                continue
            return int(v)
        except Exception:
            continue
    return None


def _load_taxonomy():
    """Load the idea-sourcing knowledge taxonomy module by FILE PATH (fail-soft).
    The dashboard READS the framework's knowledge backbone (pure data, no deps);
    it never imports the dashboard. Returns the module or None on any error."""
    try:
        import importlib.util
        import sys as _sys
        p = PROJECT_ROOT / "workspace" / "research" / "idea_sourcing" / "knowledge" / "taxonomy.py"
        if not p.exists():
            return None
        name = "_idea_taxonomy_dash"
        spec = importlib.util.spec_from_file_location(name, p)
        mod = importlib.util.module_from_spec(spec)
        _sys.modules[name] = mod  # dataclass() needs the module registered before exec
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# 1. Knowledge layer
# --------------------------------------------------------------------------- #
def collect_knowledge() -> dict:
    out: dict[str, Any] = {
        "docs": [], "strategy_kb": [], "memory": [], "temp_plan": [],
        "joinquant_data": [], "osap": [], "osap_tally": {}, "arxiv": [],
        "idea_readme": None, "error": None,
        "framework": {"dims": [], "corpus": {}}, "directions": [], "ranked_papers": [], "sources": [],
    }
    try:
        kdir = PROJECT_ROOT / "Knowledge"
        if kdir.exists():
            for f in sorted(kdir.glob("*.md")):
                out["docs"].append({"path": rel(f), "title": _first_heading(read_text(f, 4000)) or f.stem})
            for f in sorted(kdir.glob("*.csv")):
                out["docs"].append({"path": rel(f), "title": f.name})
            kb = kdir / "strategy_kb"
            if kb.exists():
                for f in sorted(kb.glob("*.md")):
                    out["strategy_kb"].append({"path": rel(f), "title": _first_heading(read_text(f, 4000)) or f.stem})
            tp = kdir / "temp_plan"
            if tp.exists():
                for f in sorted(tp.glob("*.md")):
                    out["temp_plan"].append({"path": rel(f), "title": _first_heading(read_text(f, 2500)) or f.stem})

        for d in (PROJECT_ROOT / "聚宽回测明细", PROJECT_ROOT / "Knowledge" / "聚宽回测数据"):
            if d.exists():
                for f in sorted(d.glob("*.csv")):
                    try:
                        n = sum(1 for _ in f.open(encoding="utf-8", errors="replace")) - 1
                    except Exception:
                        n = 0
                    out["joinquant_data"].append({"path": rel(f), "name": f.name, "rows": max(n, 0)})

        ideas = PROJECT_ROOT / "workspace" / "research" / "idea_sourcing"
        rm = ideas / "README.md"
        if rm.exists():
            out["idea_readme"] = {"path": rel(rm), "title": _first_heading(read_text(rm, 3000)) or "idea_sourcing",
                                  "summary": _first_para(read_text(rm, 4000))}
        for r in _records(ideas / "triage" / "osap_ashare_triage.parquet"):
            out["osap"].append({
                "acronym": _s(r.get("acronym")), "cat": _s(r.get("cat_economic")), "sign": _s(r.get("sign")),
                "desc": _s(r.get("longdesc")), "detailed": _s(r.get("detailed"))[:300],
                "tstat": _s(r.get("tstat_us")), "authors": _s(r.get("authors")), "year": _s(r.get("year")),
                "journal": _s(r.get("journal")), "feasibility": _s(r.get("feasibility")),
                "novelty": _s(r.get("novelty")), "prefix": _s(r.get("our_prefix")),
                "data_need": _s(r.get("data_need")), "dup": _s(r.get("dup_match")),
            })
        for key in ("feasibility", "novelty"):
            tally: dict[str, int] = {}
            for o in out["osap"]:
                tally[o[key]] = tally.get(o[key], 0) + 1
            out["osap_tally"][key] = tally
        for r in _records(ideas / "store" / "arxiv_qfin.parquet"):
            out["arxiv"].append({
                "id": _s(r.get("arxiv_id")), "title": _s(r.get("title")), "authors": _s(r.get("authors"))[:120],
                "cat": _s(r.get("primary_category")), "published": _s(r.get("published"))[:10],
                "abstract": _s(r.get("abstract")), "url": _s(r.get("abs_url")),
            })

        # --- arXiv Knowledge Framework (2026-06-10): taxonomy saturation map +
        #     value-ranked papers + curated research directions. Replaces the
        #     raw arXiv dump in the renderer; degrades to empty (fail-soft). ---
        kn = ideas / "knowledge"
        ranked_recs = _records(kn / "ranked_papers.parquet")
        out["ranked_papers"] = []
        for r in ranked_recs[:60]:
            out["ranked_papers"].append({
                "id": _s(r.get("arxiv_id")),
                "rank": _intish(r.get("rank")), "score": round(float(r.get("composite") or 0), 3),
                "dim": _s(r.get("primary_dim")), "status": _s(r.get("dim_status")),
                "buildable": bool(r.get("buildable_now")), "year": _s(r.get("year"))[:4],
                "cites": _intish(r.get("citations")), "title": _s(r.get("title")),
                "url": _s(r.get("url")), "abstract": _s(r.get("abstract"))[:600],
            })
        dim_counts: dict[str, int] = {}
        for r in ranked_recs[:80]:
            d = _s(r.get("primary_dim"))
            if d:
                dim_counts[d] = dim_counts.get(d, 0) + 1
        tax = _load_taxonomy()
        dims = []
        if tax is not None:
            for d in getattr(tax, "DIMENSION_TABLE", []):
                dims.append({**d, "count": dim_counts.get(d.get("key"), 0)})
        enr = _records(ideas / "store" / "arxiv_qfin_enriched.parquet")
        out["framework"] = {
            "dims": dims,
            "corpus": {
                "papers": len(out["arxiv"]),
                "ranked": len(ranked_recs),
                "enriched": sum(1 for e in enr if e.get("oa_matched")),
                "frontier_open": sum(1 for d in dims if d.get("status") == "FRONTIER_OPEN"),
            },
        }
        ry = read_yaml(kn / "research_directions.yaml")
        out["directions"] = (ry.get("directions") if isinstance(ry, dict) else None) or []
        out["framework"]["corpus"]["directions"] = len(out["directions"])

        # --- knowledge-source registry + per-source stats (source-centric view) ---
        for p in out["ranked_papers"]:
            p["source"] = p.get("source") or "arxiv"   # all ranked papers are arXiv today
        dir_by_src: dict[str, int] = {}
        comp_by_src: dict[str, int] = {}
        for d in out["directions"]:
            sid = d.get("source_kind") or "arxiv"
            dir_by_src[sid] = dir_by_src.get(sid, 0) + 1
            if d.get("lifecycle") == "completed":
                comp_by_src[sid] = comp_by_src.get(sid, 0) + 1
        pap_by_src: dict[str, int] = {}
        for p in out["ranked_papers"]:
            pap_by_src[p["source"]] = pap_by_src.get(p["source"], 0) + 1
        sy = read_yaml(kn / "sources.yaml")
        sources = (sy.get("sources") if isinstance(sy, dict) else None) or []
        for s in sources:
            sid = s.get("id")
            s["_stats"] = {"directions": dir_by_src.get(sid, 0),
                           "papers": pap_by_src.get(sid, 0),
                           "completed": comp_by_src.get(sid, 0)}
        out["sources"] = sources

        mem = Path.home() / ".claude" / "projects" / "e------" / "memory" / "MEMORY.md"
        txt = read_text(mem)
        if txt:
            for line in txt.splitlines():
                m = re.match(r"\s*-\s*\[(.+?)\]\((.+?)\)\s*[—-]+\s*(.*)", line)
                if m:
                    out["memory"].append({"title": m.group(1), "hook": m.group(3)})
    except Exception as e:  # pragma: no cover
        out["error"] = f"{type(e).__name__}: {e}"
    return out


# --------------------------------------------------------------------------- #
# 2. Data layer (full bilingual column detail)
# --------------------------------------------------------------------------- #
_FS_ALIAS = {
    "daily": "market_daily", "index": "index_daily", "stock_basic": "reference",
    "trade_cal": "reference", "namechange": "reference", "stock_st_daily": "reference",
    "suspend_d": "reference",
}


def collect_data() -> dict:
    out: dict[str, Any] = {
        "datasets": [], "status_tally": {}, "gov_tally": {}, "recent_approvals": [],
        "qlib": {}, "n_columns": 0, "error": None,
    }
    try:
        fs = read_yaml(PROJECT_ROOT / "config" / "field_registry" / "field_status.yaml")
        gov: dict[str, str] = {}
        if isinstance(fs, dict):
            for did, meta in (fs.get("datasets", {}) or {}).items():
                st = (meta or {}).get("status", "?")
                gov[did] = st
                out["gov_tally"][st] = out["gov_tally"].get(st, 0) + 1

        ddict = parse_data_dictionary()
        for did, info in sorted(ddict.items(), key=lambda kv: (kv[1].get("category", ""), kv[0])):
            fs_id = did if did in gov else _FS_ALIAS.get(did, did)
            status = gov.get(fs_id, "raw")  # not in field governance => raw-only
            out["datasets"].append({
                "id": did, "cn_name": info.get("cn_name", ""), "category": info.get("category", ""),
                "status": status, "in_qlib": status == "approved", "n_cols": len(info.get("columns", [])),
                "columns": info.get("columns", []),
            })
            out["status_tally"][status] = out["status_tally"].get(status, 0) + 1
            out["n_columns"] += len(info.get("columns", []))

        log = read_jsonl(PROJECT_ROOT / "config" / "field_registry" / "field_approval_log.jsonl")
        for ev in log[-14:][::-1]:
            out["recent_approvals"].append({
                "date": ev.get("date", ""), "dataset": ev.get("dataset_id", ""),
                "transition": f"{ev.get('from_status','')}→{ev.get('to_status','')}".strip("→") or ev.get("event", ""),
            })

        qroot = PROJECT_ROOT / "data" / "qlib_data"
        feats = qroot / "features"
        if feats.exists():
            out["qlib"]["instruments"] = sum(1 for _ in feats.iterdir() if _.is_dir())
        insts = qroot / "instruments"
        universes = []
        if insts.exists():
            for f in sorted(insts.glob("*.txt")):
                try:
                    n = sum(1 for _ in f.open(encoding="utf-8", errors="replace"))
                except Exception:
                    n = 0
                universes.append({"name": f.stem, "lines": n})
        out["qlib"]["universes"] = universes
        cal = qroot / "calendars" / "day.txt"
        if cal.exists():
            try:
                lines = cal.read_text(encoding="utf-8", errors="replace").splitlines()
                out["qlib"]["calendar_end"] = lines[-1].strip() if lines else None
            except Exception:
                pass
    except Exception as e:  # pragma: no cover
        out["error"] = f"{type(e).__name__}: {e}"
    return out


# --------------------------------------------------------------------------- #
# 3. Factor layer (factor_registry_review.html parity)
# --------------------------------------------------------------------------- #
def _evidence_by_class() -> dict[str, dict]:
    """Per-factor latest evidence row PER CLASS (Rev5 two-class taxonomy).

    {factor_id: {gated, refresh, discovery}} where
      - gated    = latest ``factor_lifecycle`` row with ``formal_evidence_eligible=True``
                   (the human-signed promotion evidence — the only rows that can back status)
      - refresh  = latest ``factor_lifecycle_refresh`` row (ungated full-metric sweep)
      - discovery= latest screening/research row that actually carries a grade
    ``catalog_sync`` stamp rows are IGNORED for metrics — the old global last-wins let their
    empty rows shadow real evidence (the original 评级 "—" bug).
    """
    df = read_parquet(PROJECT_ROOT / "data" / "factor_registry" / "factor_evidence.parquet")
    out: dict[str, dict] = {}
    if df is None:
        return out
    if "evidence_time" in df.columns:
        df = df.sort_values("evidence_time")
    for r in df.to_dict("records"):
        fid = r.get("factor_id")
        slot = out.setdefault(fid, {"gated": None, "refresh": None, "discovery": None})
        rt = _s(r.get("run_type"))
        if rt == "factor_lifecycle" and bool(r.get("formal_evidence_eligible")):
            slot["gated"] = r          # last wins = latest per class
        elif rt == "factor_lifecycle_refresh":
            slot["refresh"] = r
        elif rt in ("screening", "research") and _s(r.get("grade")):
            slot["discovery"] = r
    return out


def collect_factors() -> dict:
    out: dict[str, Any] = {
        "status_tally": {}, "current_tally": {}, "total_rows": 0, "catalog": {},
        "candidates": 0, "category_dist": {}, "factors": [], "error": None,
    }
    try:
        df = read_parquet(PROJECT_ROOT / "data" / "factor_registry" / "factor_master.parquet")
        if df is not None:
            out["total_rows"] = int(len(df))
            if "status" in df.columns:
                out["status_tally"] = {k: int(v) for k, v in df["status"].value_counts().items()}
            cur = df[df["is_current"] == True] if "is_current" in df.columns else df  # noqa: E712
            if "status" in cur.columns:
                out["current_tally"] = {k: int(v) for k, v in cur["status"].value_counts().items()}
            if "category" in cur.columns:
                out["category_dist"] = {k: int(v) for k, v in cur["category"].value_counts().items()}

            ev = _evidence_by_class()
            order = {"approved": 0, "candidate": 1, "draft": 2}
            rows = sorted(cur.to_dict("records"),
                          key=lambda r: (order.get(r.get("status"), 9), str(r.get("category")), str(r.get("factor_id"))))
            for r in rows:
                fid = r.get("factor_id")
                cls = ev.get(fid, {"gated": None, "refresh": None, "discovery": None})
                g, f, d = cls["gated"] or {}, cls["refresh"] or {}, cls["discovery"] or {}
                en, cn = factor_desc(fid)  # Sonnet-generated bilingual one-liner (cached)
                cat = _s(r.get("category"))
                cat_en, cat_cn = category_label(cat)

                # formal headline: the signed (gated) number wins where it exists; refresh fills.
                heldout = _num(g.get("is_rank_icir")) if g.get("is_rank_icir") is not None else _num(f.get("is_rank_icir"))
                heldout_src = "gated" if g.get("is_rank_icir") is not None else ("refresh" if f.get("is_rank_icir") is not None else "")
                sign_cons = _num(g.get("sign_consistency")) if g.get("sign_consistency") is not None else _num(f.get("sign_consistency"))
                # gated-vs-refresh consistency canary (same engine — material divergence = drift)
                drift = None
                if g.get("is_rank_icir") is not None and f.get("is_rank_icir") is not None:
                    try:
                        drift = abs(float(g["is_rank_icir"]) - float(f["is_rank_icir"]))
                    except (TypeError, ValueError):
                        drift = None
                # HAC significance (direction-aware |t| >= 3.0), neutralized-only labeling
                hac_t = _num(f.get("mean_rank_ic_hac_t"))
                neut_t = _num(f.get("neutralized_hac_t"))
                if hac_t is not None and abs(hac_t) >= 3.0:
                    hac_sig = "pass"
                elif neut_t is not None and abs(neut_t) >= 3.0:
                    hac_sig = "neut_only"
                elif hac_t is not None or neut_t is not None:
                    hac_sig = "no"
                else:
                    hac_sig = ""

                out["factors"].append({
                    "id": fid, "zh": _s(r.get("display_name_zh")),
                    "category": cat, "category_bi": f"{cat_en} {cat_cn}".strip(),
                    "kind": _s(r.get("factor_kind")), "status": _s(r.get("status")),
                    "recommended": _s(r.get("recommended_status")), "validity": _s(r.get("approval_validity")),
                    "direction": _s(r.get("expected_direction")), "binding": _s(r.get("definition_binding")),
                    "expr": _s(r.get("expression")), "components": _parse_json(r.get("components_json")),
                    "weights": _parse_json(r.get("weights_json")),
                    # ---- formal (lifecycle methodology): gated ✍ first, refresh 🔄 fills
                    "heldout_icir": heldout, "heldout_src": heldout_src, "sign_cons": sign_cons,
                    "gated_refresh_drift": _num(drift),
                    "hac_t": hac_t, "hac_sig": hac_sig,
                    "neut_icir": _num(f.get("neutralized_rank_icir")), "neut_hac_t": neut_t,
                    "mono_shape": _s(f.get("mono_shape")),
                    "direction_source": _s(f.get("direction_source")),
                    "coverage": _num(f.get("coverage")), "coverage_tier": _s(f.get("coverage_tier")),
                    "turnover_ann": _num(f.get("turnover_ann")),
                    "marginal": _num(f.get("resid_ic_vs_approved_stable_oriented")),
                    "resid_style": _num(f.get("resid_ic_vs_style_controls_v1_oriented")),
                    "ll_ir_300": _num(f.get("long_leg_ir_proxy_is_csi300")),
                    "ll_ir_500": _num(f.get("long_leg_ir_proxy_is_csi500")),
                    "methodology_hash": _s(f.get("methodology_hash"))[:8],
                    "unified_json": _s(f.get("unified_metrics_json")),
                    # 10-group oriented heldout profile (留痕 2026-06-11): list of
                    # {q, ann_return, mean_count}; None for pre-directive evidence rows.
                    "quantile_profile": (_parse_json(f.get("unified_metrics_json")) or {}).get("quantile_profile"),
                    # ---- discovery (screening triage) — demoted small print
                    "grade": _s(d.get("grade")) or _s(r.get("latest_screening_grade")),
                    "rank_icir_5d": _num(d.get("rank_icir_5d")) if d.get("rank_icir_5d") is not None else _num(r.get("latest_rank_icir_5d")),
                    # ---- legacy fields kept for the detail card
                    "mean_rank_ic": _num(d.get("mean_rank_ic_5d")), "monotonic": _s(d.get("monotonic")),
                    "best_decay": _s(d.get("best_decay_horizon")), "ls_ann": _num(d.get("ls_ann_return")),
                    "val_pass": _intish(d.get("validation_pass_count"), r.get("latest_validation_pass_count")),
                    "folds": _intish(d.get("selected_fold_count"), r.get("latest_selected_fold_count")),
                    "notes": _s(r.get("notes"))[:240], "en": en, "cn": cn, "updated": _s(r.get("updated_at"))[:10],
                })

        cdf = read_parquet(PROJECT_ROOT / "data" / "candidate_registry" / "candidate_master.parquet")
        if cdf is not None:
            out["candidates"] = int(len(cdf))

        try:
            import sys
            if str(PROJECT_ROOT) not in sys.path:
                sys.path.insert(0, str(PROJECT_ROOT))
            from src.alpha_research.factor_library import catalog_composition
            out["catalog"] = catalog_composition()
        except Exception as e:
            out["catalog"] = {"error": f"{type(e).__name__}: {e}"}
    except Exception as e:  # pragma: no cover
        out["error"] = f"{type(e).__name__}: {e}"
    return out


# --------------------------------------------------------------------------- #
# 4. Research layer
# --------------------------------------------------------------------------- #
def collect_research() -> dict:
    out: dict[str, Any] = {"threads": [], "n_output_runs": 0, "milestones": [], "error": None}
    try:
        rroot = PROJECT_ROOT / "workspace" / "research"
        if rroot.exists():
            for d in sorted(rroot.iterdir()):
                if not d.is_dir():
                    continue
                findings = []
                for f in sorted(d.glob("FINDINGS*.md")):
                    md = read_text(f, 6000)
                    findings.append({"path": rel(f), "name": f.name,
                                     "title": _first_heading(md) or f.name, "summary": _first_para(md)})
                out["threads"].append({"name": d.name, "findings": findings, "has_findings": bool(findings)})
        oroot = PROJECT_ROOT / "workspace" / "outputs"
        if oroot.exists():
            out["n_output_runs"] = sum(1 for d in oroot.iterdir() if d.is_dir())

        ps = read_text(PROJECT_ROOT / "project_state.md", 160000) or ""
        for m in re.finditer(r"\*Update Note \(([0-9]{4}-[0-9]{2}-[0-9]{2}[a-z]?)\s*,\s*\*\*(.+?)\*\*", ps):
            out["milestones"].append({"date": m.group(1)[:10], "title": re.sub(r"\s+", " ", m.group(2)).strip()[:200]})
            if len(out["milestones"]) >= 30:
                break
    except Exception as e:  # pragma: no cover
        out["error"] = f"{type(e).__name__}: {e}"
    return out


# --------------------------------------------------------------------------- #
# 5. Strategy layer
# --------------------------------------------------------------------------- #
def collect_strategy(board: dict | None) -> dict:
    out: dict[str, Any] = {
        "registry": {}, "signals": 0, "models": 0, "deployable": [], "signal_rows": [], "error": None,
    }
    try:
        sdf = read_parquet(PROJECT_ROOT / "data" / "strategy_registry" / "strategy_registry_master.parquet")
        out["registry"]["strategies"] = int(len(sdf)) if sdf is not None else 0
        sig = read_parquet(PROJECT_ROOT / "data" / "signal_registry" / "signal_registry_master.parquet")
        out["signals"] = int(len(sig)) if sig is not None else 0
        if sig is not None:
            cur = sig[sig["is_current"] == True] if "is_current" in sig.columns else sig  # noqa: E712
            for r in cur.head(150).to_dict("records"):
                summ = _parse_json(r.get("latest_summary_json")) or {}
                out["signal_rows"].append({
                    "id": _s(r.get("object_id")), "name": _s(r.get("object_name")),
                    "type": _s(r.get("object_type")),
                    "profile": _s(r.get("research_profile")) or _s(r.get("latest_source_profile")),
                    "status": _s(r.get("status")),
                    "metric": (_s(summ.get("metric") or summ.get("headline") or "")[:80]) if isinstance(summ, dict) else "",
                })
        mdl = read_parquet(PROJECT_ROOT / "data" / "model_registry" / "model_registry_master.parquet")
        out["models"] = int(len(mdl)) if mdl is not None else 0
        if board and isinstance(board.get("strategies"), list):
            out["deployable"] = board["strategies"]
    except Exception as e:  # pragma: no cover
        out["error"] = f"{type(e).__name__}: {e}"
    return out
