# SCRIPT_STATUS: ACTIVE — AI 链路观察站 Block E:静态看板生成器(Class-D,非证据)
"""Generate the observatory board — a multi-page static HTML site (file:// safe).

Pages:
  board/index.html          总览:非证据横幅 · 状态卡 · 四腿NAV · 决策日表 · Δfinal 直方图 · 个股索引
  board/days/<date>.html    决策视图:全池打分表(按 combined 排序)+ 换股审计
  board/names/<code>.html   个股档案:分数演化 · 维度分+逐字证据 · dossier 组成 · 1年文本时间线

Reads: daily/*/decision.json + scorecards.parquet + names/*/{text,fund,anon}_scorecard.json,
data/text_store_hist_pilot/*, fund_cards.parquet, nav_daily.parquet (optional), fetch_manifest.json.

用法: venv/Scripts/python.exe workspace/research/ai_chain_observatory/build_board.py
"""
from __future__ import annotations

import html
import json
import logging
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from data_infra.provider_metadata import tushare_to_qlib_canonical  # noqa: E402

OUT_DIR = PROJECT_ROOT / "workspace" / "outputs" / "ai_chain_observatory"
DAILY_DIR = OUT_DIR / "daily"
BOARD_DIR = OUT_DIR / "board"
HIST_STORE = PROJECT_ROOT / "data" / "text_store_hist_pilot"
STOCK_BASIC = PROJECT_ROOT / "data" / "reference" / "stock_basic.parquet"

logger = logging.getLogger("board")

# ---- 调色(dataviz reference palette;文本永远用 ink tokens,系列色只上 marks) ----
CSS = """
:root{--surface:#fcfcfb;--plane:#f9f9f7;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;
--grid:#e1e0d9;--axis:#c3c2b7;--border:rgba(11,11,11,.10);
--s-quant:#2a78d6;--s-ai:#1baf7a;--s-pool:#eda100;--s-proto:#008300;
--seq:#256abf;--warn-bg:#fff3e0;--warn-ink:#8a4b00;--good:#006300;--bad:#d03b3b}
@media(prefers-color-scheme:dark){:root{--surface:#1a1a19;--plane:#0d0d0d;--ink:#fff;
--ink2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--axis:#383835;--border:rgba(255,255,255,.10);
--s-quant:#3987e5;--s-ai:#199e70;--s-pool:#c98500;--s-proto:#008300;--seq:#3987e5;
--warn-bg:#3a2a10;--warn-ink:#f0c070;--good:#0ca30c;--bad:#e66767}}
*{box-sizing:border-box}body{margin:0;background:var(--plane);color:var(--ink);
font:14px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:20px 24px 60px}
.banner{background:var(--warn-bg);color:var(--warn-ink);border:1px solid var(--border);
border-radius:8px;padding:10px 14px;font-weight:600;margin-bottom:18px}
h1{font-size:22px;margin:8px 0 4px}h2{font-size:17px;margin:26px 0 10px}
.sub{color:var(--ink2);margin:0 0 14px}
.cards{display:flex;gap:12px;flex-wrap:wrap;margin:14px 0}
.card{background:var(--surface);border:1px solid var(--border);border-radius:10px;
padding:12px 16px;min-width:130px}
.card .v{font-size:22px;font-weight:700}.card .k{color:var(--muted);font-size:12px}
table{border-collapse:collapse;width:100%;background:var(--surface);border:1px solid var(--border);
border-radius:10px;overflow:hidden;font-variant-numeric:tabular-nums}
th{color:var(--muted);font-weight:600;font-size:12px;text-align:left;padding:7px 10px;
border-bottom:1px solid var(--grid);position:sticky;top:0;background:var(--surface)}
td{padding:6px 10px;border-bottom:1px solid var(--grid);vertical-align:top}
tr:last-child td{border-bottom:none}
.num{text-align:right}.pos{color:var(--good)}.neg{color:var(--bad)}
.chip{display:inline-block;padding:1px 8px;border-radius:10px;font-size:12px;
border:1px solid var(--border);color:var(--ink2)}
.chip.in{background:rgba(27,175,122,.14)}.chip.out{background:rgba(211,59,59,.12)}
.chip.q{background:rgba(42,120,214,.12)}
.legend{display:flex;gap:16px;flex-wrap:wrap;margin:6px 0;color:var(--ink2);font-size:13px}
.sw{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px}
a{color:var(--s-quant);text-decoration:none}a:hover{text-decoration:underline}
.grid-names{display:flex;flex-wrap:wrap;gap:6px}
.grid-names a{border:1px solid var(--border);border-radius:7px;padding:3px 8px;
background:var(--surface);font-size:12.5px}
.ev{background:var(--plane);border-left:3px solid var(--axis);padding:4px 10px;margin:4px 0;
color:var(--ink2);font-size:13px;border-radius:0 6px 6px 0}
.dim{color:var(--muted)}.small{font-size:12.5px}
.scorebox{background:var(--surface);border:1px solid var(--border);border-radius:10px;
padding:12px 16px;margin:10px 0}
svg text{font:11.5px system-ui,-apple-system,"Segoe UI",sans-serif}
.tl{border-left:2px solid var(--axis);margin:8px 0 8px 6px;padding-left:14px}
.tl .it{margin:0 0 10px}.tl .t{color:var(--muted);font-size:12px}
"""

BANNER = ("⚠ 非证据(C5 quasi-forward replay)— 本看板全部打分与收益仅用于链路观察/抽取QA,"
          "不是 alpha 证据;LLM 训练记忆可能已知 2025 年结局(见匿名化对照);"
          "不得据此调参(C16b)。")

LEGS = [("quant_daily", "量化日度", "--s-quant"), ("ai_daily", "AI 日度", "--s-ai"),
        ("pool_ew", "池等权", "--s-pool"), ("ai_day4_protocol", "AI 协议腿(day-4)", "--s-proto")]


def esc(x) -> str:
    return html.escape(str(x)) if x is not None else ""


def page(title: str, body: str, depth: int = 0) -> str:
    home = "../" * depth + "index.html"
    return (f'<!doctype html><html lang="zh"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(title)}</title><style>{CSS}</style></head><body>'
            f'<div class="wrap"><div class="banner">{BANNER}</div>'
            f'<p class="small"><a href="{home}">← 总览</a></p>{body}</div></body></html>')


def fmt(v, nd=1, signed=False):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return '<span class="dim">—</span>'
    s = f"{v:+.{nd}f}" if signed else f"{v:.{nd}f}"
    cls = "pos" if (signed and v > 0) else ("neg" if (signed and v < 0) else "")
    return f'<span class="{cls}">{s}</span>' if cls else s


# ------------------------------------------------------------------ SVG charts

def svg_nav(nav: pd.DataFrame) -> str:
    days = sorted(nav["date"].unique())
    W, H, L, R, T, B = 980, 300, 52, 130, 14, 30
    lo = min(0.995, float(nav["nav"].min()) - 0.003)
    hi = max(1.005, float(nav["nav"].max()) + 0.003)
    x = lambda i: L + (W - L - R) * (i / max(1, len(days) - 1))
    y = lambda v: T + (H - T - B) * (1 - (v - lo) / (hi - lo))
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="四腿NAV曲线">']
    for g in [lo, 1.0, hi]:
        out.append(f'<line x1="{L}" y1="{y(g):.1f}" x2="{W-R}" y2="{y(g):.1f}" '
                   f'stroke="var(--grid)" stroke-width="1"/>'
                   f'<text x="{L-6}" y="{y(g)+4:.1f}" text-anchor="end" '
                   f'fill="var(--muted)">{g:.3f}</text>')
    for i in range(0, len(days), max(1, len(days) // 6)):
        out.append(f'<text x="{x(i):.0f}" y="{H-8}" text-anchor="middle" '
                   f'fill="var(--muted)">{days[i][4:6]}/{days[i][6:]}</text>')
    for leg, label, var in LEGS:
        sub = nav[nav["leg"] == leg].set_index("date").reindex(days)
        pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(sub["nav"]) if pd.notna(v))
        out.append(f'<polyline points="{pts}" fill="none" stroke="var({var})" '
                   f'stroke-width="2" stroke-linejoin="round"/>')
        last = sub["nav"].dropna()
        if len(last):
            out.append(f'<text x="{W-R+6}" y="{y(last.iloc[-1])+4:.1f}" '
                       f'fill="var(--ink2)">{label} {last.iloc[-1]:.3f}</text>')
        for i, v in enumerate(sub["nav"]):
            if pd.notna(v):
                out.append(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="7" fill="transparent">'
                           f'<title>{label} {days[i]}: {v:.4f}</title></circle>')
    out.append("</svg>")
    return "".join(out)


def svg_hist(values: list[float], title: str) -> str:
    if not values:
        return '<p class="dim">暂无数据</p>'
    s = pd.Series(values)
    lo, hi = float(s.min()), float(s.max())
    span = max(1e-9, hi - lo)
    nbins = 15
    counts = [0] * nbins
    for v in s:
        counts[min(nbins - 1, int((v - lo) / span * nbins))] += 1
    W, H, L, B = 620, 180, 40, 30
    bw = (W - L - 10) / nbins
    mx = max(counts)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{esc(title)}">']
    out.append(f'<line x1="{L}" y1="{H-B}" x2="{W-10}" y2="{H-B}" stroke="var(--axis)"/>')
    for i, c in enumerate(counts):
        if c == 0:
            continue
        bh = (H - B - 14) * c / mx
        bx, by = L + i * bw + 1, H - B - bh
        out.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw-2:.1f}" height="{bh:.1f}" '
                   f'rx="4" fill="var(--seq)"><title>{lo+span*i/nbins:.0f}..'
                   f'{lo+span*(i+1)/nbins:.0f}: {c}</title></rect>')
        if c == mx:
            out.append(f'<text x="{bx+bw/2-1:.1f}" y="{by-4:.1f}" text-anchor="middle" '
                       f'fill="var(--ink2)">{c}</text>')
    for v, anchor in [(lo, "start"), (0.0, "middle"), (hi, "end")]:
        if lo <= v <= hi:
            vx = L + (v - lo) / span * (W - L - 10)
            out.append(f'<text x="{vx:.0f}" y="{H-10}" text-anchor="{anchor}" '
                       f'fill="var(--muted)">{v:.0f}</text>')
    out.append("</svg>")
    return "".join(out)


# ------------------------------------------------------------------- data load

def load_all():
    decisions, scorecards = {}, {}
    for p in sorted(DAILY_DIR.glob("*/decision.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        decisions[d["date"]] = d
        sc = p.parent / "scorecards.parquet"
        if sc.exists():
            scorecards[d["date"]] = pd.read_parquet(sc)
    texts = {}
    for s in ("anns_d", "irm_qa_sh", "irm_qa_sz", "research_report"):
        p = HIST_STORE / s / f"text_{s}.parquet"
        if p.exists():
            texts[s] = pd.read_parquet(p)
    nav = None
    if (OUT_DIR / "nav_daily.parquet").exists():
        nav = pd.read_parquet(OUT_DIR / "nav_daily.parquet")
    sim = (json.loads((OUT_DIR / "sim_summary.json").read_text(encoding="utf-8"))
           if (OUT_DIR / "sim_summary.json").exists() else {})
    sb = pd.read_parquet(STOCK_BASIC, columns=["ts_code", "name", "industry"])
    meta = {r.ts_code: (r.name, r.industry) for r in sb.itertuples()}
    return decisions, scorecards, texts, nav, sim, meta


def name_scorecard(day: str, code: str, kind: str) -> dict | None:
    p = DAILY_DIR / day / "names" / tushare_to_qlib_canonical(code) / f"{kind}_scorecard.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


# ---------------------------------------------------------------- name pages

def render_scorebox(title: str, res: dict | None) -> str:
    if not res:
        return f'<div class="scorebox"><b>{esc(title)}</b><p class="dim">无(no_text / 失败 / 未跑)</p></div>'
    rec, out = res["record"], []
    out.append(f'<div class="scorebox"><b>{esc(title)}</b>'
               f'<span style="float:right" class="chip">final = {fmt(res.get("final"))}</span>')
    for fs in rec.get("factor_scores", []):
        out.append(f'<p style="margin:8px 0 2px"><b>{esc(fs["name"])}</b> = {fs["score_0_5"]}/5</p>')
        for sp in (fs.get("evidence_spans") or [])[:3]:
            out.append(f'<div class="ev">「{esc(sp[:160])}」</div>')
        if not fs.get("evidence_spans"):
            out.append('<div class="ev dim">无逐字证据 → 该维不计分</div>')
    pens = [p for p in rec.get("penalty_scores", []) if p.get("score_0_5", 0)]
    for p_ in pens:
        out.append(f'<p style="margin:8px 0 2px" class="neg"><b>罚分 {esc(p_["name"])}</b>'
                   f' = {p_["score_0_5"]}/5</p>')
        for sp in (p_.get("evidence_spans") or [])[:2]:
            out.append(f'<div class="ev">「{esc(sp[:160])}」</div>')
    if rec.get("what_could_weaken"):
        out.append(f'<p class="small dim">弱化因素:{esc(";".join(rec["what_could_weaken"][:3]))}</p>')
    if "digest" in res and res["digest"].get("events"):
        out.append('<p style="margin:10px 0 2px"><b>digest 事件(quick 层抽取)</b></p>')
        for ev in res["digest"]["events"][:8]:
            out.append(f'<p class="small" style="margin:2px 0">· [{esc(ev.get("type"))}] '
                       f'{esc(ev.get("summary"))} <span class="dim">({esc(ev.get("source"))} '
                       f'{esc(ev.get("date"))})</span></p>')
    out.append("</div>")
    return "".join(out)


def render_name_page(code: str, decisions, scorecards, texts, meta) -> str:
    nm, ind = meta.get(code, ("", ""))
    days = sorted(decisions)
    rows = []
    for d in days:
        det = scorecards.get(d)
        if det is None:
            continue
        r = det[det["ts_code"] == code]
        if r.empty:
            continue
        r = r.iloc[0]
        book = ("换入" if code in decisions[d]["overlay_audit"]["swaps_in"] else
                "换出" if code in decisions[d]["overlay_audit"]["swaps_out"] else
                "AI账本" if code in decisions[d]["legs"]["ai_book"] else
                "量化账本" if code in decisions[d]["legs"]["quant_book"] else "")
        rows.append(
            f'<tr><td><a href="../days/{d}.html">{d}</a></td>'
            f'<td class="num">{fmt(r.get("quant_score"), 3)}</td>'
            f'<td>{"✓" if r.get("in_floor") else ""}</td>'
            f'<td class="num">{fmt(r.get("text_final"), 0)}</td>'
            f'<td class="num">{fmt(r.get("fund_final"), 0)}</td>'
            f'<td class="num">{fmt(r.get("anon_final"), 0)}</td>'
            f'<td class="num">{fmt(r.get("delta_named_minus_anon"), 0, signed=True)}</td>'
            f'<td class="num">{fmt(r.get("combined"), 0)}</td>'
            f'<td class="num">{fmt(r.get("tilt"), 3, signed=True)}</td>'
            f'<td>{esc(book)}</td></tr>')
    last_day = max((d for d in days if (DAILY_DIR / d / "names" /
                    tushare_to_qlib_canonical(code)).exists()), default=None)
    boxes = ""
    if last_day:
        boxes = (f"<h2>最近打分明细({last_day})</h2>"
                 + render_scorebox("文本 persona(具名)", name_scorecard(last_day, code, "text"))
                 + render_scorebox("基本面 persona", name_scorecard(last_day, code, "fund"))
                 + render_scorebox("文本 persona(匿名对照,不进决策)",
                                   name_scorecard(last_day, code, "anon")))
    # 1yr text timeline (newest first, capped for page size)
    tl = []
    for s, df in texts.items():
        sub = df[df["ts_code"] == code]
        for _, r in sub.iterrows():
            if s == "anns_d":
                txt = f"[公告] {r.get('title', '')}"
            elif s.startswith("irm_qa"):
                txt = f"[互动易] 问:{str(r.get('q', ''))[:80]} 答:{str(r.get('a', ''))[:120]}"
            else:
                txt = f"[研报·{r.get('inst_csname', '')}] {r.get('title', '')}"
            tl.append((r["sim_visible_at"], r.get("visibility_basis", ""), txt))
    tl.sort(key=lambda x: str(x[0]), reverse=True)
    tl_html = "".join(
        f'<div class="it"><div class="t">{esc(str(t)[:16])} '
        f'<span class="chip">{esc(b)}</span></div>{esc(x[:220])}</div>'
        for t, b, x in tl[:400])
    body = (f"<h1>{esc(code)} {esc(nm)}</h1><p class='sub'>{esc(ind)} · "
            f"文本条数(1年):{len(tl)}</p>"
            f"<h2>分数演化</h2><table><tr><th>日期</th><th>量化分</th><th>floor</th>"
            f"<th>文本</th><th>基本面</th><th>匿名</th><th>Δ具名-匿名</th><th>combined</th>"
            f"<th>tilt</th><th>账本</th></tr>{''.join(rows) or '<tr><td colspan=10 class=dim>无打分记录</td></tr>'}</table>"
            f"{boxes}<h2>1 年文本时间线(模拟可见时点,新→旧,最多400条)</h2>"
            f"<div class='tl'>{tl_html or '<p class=dim>无文本</p>'}</div>")
    return page(f"{code} {nm} — AI链路观察站", body, depth=1)


# ----------------------------------------------------------------- day pages

def render_day_page(day: str, decisions, scorecards, meta) -> str:
    dec = decisions[day]
    det = scorecards.get(day, pd.DataFrame())
    au = dec["overlay_audit"]
    ai_book, q_book = set(dec["legs"]["ai_book"]), set(dec["legs"]["quant_book"])
    rows = []
    if not det.empty:
        det = det.sort_values("combined", ascending=False, na_position="last")
        for _, r in det.iterrows():
            c = r["ts_code"]
            nm, _ = meta.get(c, ("", ""))
            chips = []
            if c in au["swaps_in"]:
                chips.append('<span class="chip in">换入</span>')
            if c in au["swaps_out"]:
                chips.append('<span class="chip out">换出</span>')
            if c in ai_book and c not in au["swaps_in"]:
                chips.append('<span class="chip in">AI</span>')
            if c in q_book:
                chips.append('<span class="chip q">量化</span>')
            rows.append(
                f'<tr><td><a href="../names/{c}.html">{esc(c)}</a> {esc(nm)}</td>'
                f'<td class="num">{fmt(r.get("quant_score"), 3)}</td>'
                f'<td>{"✓" if r.get("in_floor") else ""}</td>'
                f'<td class="num">{fmt(r.get("text_final"), 0)}</td>'
                f'<td class="num">{fmt(r.get("fund_final"), 0)}</td>'
                f'<td class="num">{fmt(r.get("anon_final"), 0)}</td>'
                f'<td class="num">{fmt(r.get("combined"), 0)}</td>'
                f'<td class="num">{fmt(r.get("tilt"), 3, signed=True)}</td>'
                f'<td>{" ".join(chips)}</td></tr>')
    swaps = "".join(f'<li>{esc(i)} ⇄ {esc(o)}</li>' for i, o in au.get("tilt_swaps", []))
    body = (f"<h1>决策视图 · {day}</h1>"
            f"<p class='sub'>coverage(floor)={dec['coverage_scored_pct']:.0%} · "
            f"overlay_disabled={dec['overlay_disabled']} · scored={dec['n_scored']} · "
            f"config={esc(dec['config_hash'])}</p>"
            f"<h2>换股审计(entrant ⇄ 换出)</h2><ul>{swaps or '<li class=dim>无换股</li>'}</ul>"
            f"<h2>全池打分(按 combined 降序)</h2>"
            f"<table><tr><th>股票</th><th>量化分</th><th>floor</th><th>文本</th>"
            f"<th>基本面</th><th>匿名</th><th>combined</th><th>tilt</th><th>账本</th></tr>"
            f"{''.join(rows)}</table>")
    return page(f"决策 {day} — AI链路观察站", body, depth=1)


# ---------------------------------------------------------------- index page

def render_index(decisions, scorecards, texts, nav, sim, meta) -> str:
    days = sorted(decisions)
    all_det = pd.concat(scorecards.values()) if scorecards else pd.DataFrame()
    n_scored = int(all_det["combined"].notna().sum()) if not all_det.empty else 0
    deltas = (all_det["delta_named_minus_anon"].dropna().tolist()
              if "delta_named_minus_anon" in all_det else [])
    cards = [
        ("决策日", f"{len(days)}"), ("池", "149"),
        ("打分记录", f"{n_scored}"),
        ("文本行(4源)", f"{sum(len(t) for t in texts.values()):,}"),
        ("匿名Δ均值", f"{pd.Series(deltas).mean():+.1f}" if deltas else "—"),
    ]
    cards_html = "".join(f'<div class="card"><div class="v">{esc(v)}</div>'
                         f'<div class="k">{esc(k)}</div></div>' for k, v in cards)
    legend = "".join(f'<span><span class="sw" style="background:var({v})"></span>'
                     f'{l}</span>' for _, l, v in LEGS)
    nav_html = ""
    if nav is not None and not nav.empty:
        stats = "".join(
            f'<div class="card"><div class="v">{sim[l]["total_return_pct"]:+.1f}%</div>'
            f'<div class="k">{lab}(MDD {sim[l]["mdd_pct"]:.1f}%)</div></div>'
            for l, lab, _ in LEGS if l in sim)
        nav_html = (f"<h2>四腿 NAV(开盘成交,16bp 单边)</h2>"
                    f"<div class='legend'>{legend}</div>{svg_nav(nav)}"
                    f"<div class='cards'>{stats}</div>")
    day_rows = "".join(
        f'<tr><td><a href="days/{d}.html">{d}</a>{" <b>(day-4 协议)</b>" if i == 0 else ""}</td>'
        f'<td class="num">{decisions[d]["coverage_scored_pct"]:.0%}</td>'
        f'<td>{"⛔" if decisions[d]["overlay_disabled"] else "✓"}</td>'
        f'<td class="num">{len(decisions[d]["overlay_audit"]["swaps_in"])}</td>'
        f'<td class="small">{esc(", ".join(decisions[d]["overlay_audit"]["swaps_in"][:6]))}</td></tr>'
        for i, d in enumerate(days))
    codes = sorted(meta_codes(scorecards, texts))
    names_html = "".join(f'<a href="names/{c}.html">{esc(c)} {esc(meta.get(c, ("",""))[0])}</a>'
                         for c in codes)
    delta_html = ""
    if deltas:
        top = (all_det.dropna(subset=["delta_named_minus_anon"])
               .assign(a=lambda x: x["delta_named_minus_anon"].abs())
               .sort_values("a", ascending=False).head(10))
        top_rows = "".join(
            f'<tr><td><a href="names/{r.ts_code}.html">{esc(r.ts_code)}</a></td>'
            f'<td>{esc(r.trade_date)}</td><td class="num">{fmt(r.text_final, 0)}</td>'
            f'<td class="num">{fmt(r.anon_final, 0)}</td>'
            f'<td class="num">{fmt(r.delta_named_minus_anon, 0, signed=True)}</td></tr>'
            for r in top.itertuples())
        delta_html = (
            "<h2>匿名化对照(污染诊断)</h2>"
            "<p class='sub'>Δ = 具名 − 匿名。分布偏离 0 越远,LLM 对「认识这家公司」的依赖越强"
            "(训练记忆污染的直接测量)。</p>" + svg_hist(deltas, "Δfinal 分布")
            + f"<h2 class='small'>|Δ| 最大 10 例</h2><table><tr><th>股票</th><th>日期</th>"
              f"<th>具名</th><th>匿名</th><th>Δ</th></tr>{top_rows}</table>")
    body = (f"<h1>AI 链路观察站 · 202501 金股池</h1>"
            f"<p class='sub'>历史试点:文本(4源,模拟可见时点)+ 基本面卡片 → 双 persona LLM 维度分 "
            f"→ 确定性合成 → 有界叠加量化 top-25 → 日度模拟盘。config=pilot_v1</p>"
            f"<div class='cards'>{cards_html}</div>{nav_html}"
            f"<h2>决策日({len(days)})</h2><table><tr><th>日期</th><th>coverage</th>"
            f"<th>叠加</th><th>换股数</th><th>换入</th></tr>{day_rows}</table>"
            f"{delta_html}<h2>个股档案({len(codes)})</h2>"
            f"<div class='grid-names'>{names_html}</div>")
    return page("AI 链路观察站 — 202501 金股池", body, depth=0)


def meta_codes(scorecards, texts) -> set:
    codes = set()
    for det in scorecards.values():
        codes |= set(det["ts_code"])
    if not codes:
        for df in texts.values():
            codes |= set(df["ts_code"])
    return codes


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    decisions, scorecards, texts, nav, sim, meta = load_all()
    if not decisions:
        raise RuntimeError("no daily decisions — run run_chain_replay.py first")
    (BOARD_DIR / "days").mkdir(parents=True, exist_ok=True)
    (BOARD_DIR / "names").mkdir(parents=True, exist_ok=True)

    (BOARD_DIR / "index.html").write_text(
        render_index(decisions, scorecards, texts, nav, sim, meta), encoding="utf-8")
    for d in decisions:
        (BOARD_DIR / "days" / f"{d}.html").write_text(
            render_day_page(d, decisions, scorecards, meta), encoding="utf-8")
    codes = meta_codes(scorecards, texts)
    for c in sorted(codes):
        (BOARD_DIR / "names" / f"{c}.html").write_text(
            render_name_page(c, decisions, scorecards, texts, meta), encoding="utf-8")
    logger.info("board: index + %d day pages + %d name pages -> %s",
                len(decisions), len(codes), BOARD_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
