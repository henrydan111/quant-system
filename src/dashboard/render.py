"""Render the collected context into a single self-contained HTML page.

No external assets: all CSS/JS is inlined so the file opens offline. Each layer
is its own detail page (no global KPI band); per-page lead cards carry the
headline numbers. Interactions: per-section status/text filters, data sub-nav
(datasets / Qlib universe / approvals), factor master-detail (click a row to
expand its card), an in-page markdown viewer (fetch + render in a modal — needs
the dashboard served over http; see serve_dashboard.bat), and session todo
breakdown. Factor/strategy/research descriptions are Sonnet-generated bilingual
one-liners from translations.json (via the collectors).
"""
from __future__ import annotations

import html
import json
import os
from pathlib import Path
from typing import Any

from .translate import strategy_desc, thread_desc, dim_label, direction_desc, paper_gloss
from .util import HTML_OUTPUT, PROJECT_ROOT

_rel = os.path.relpath(PROJECT_ROOT, HTML_OUTPUT.parent)
ROOT_PREFIX = "" if _rel == "." else Path(_rel).as_posix() + "/"


def link(path: Any) -> str:
    p = str(path or "")
    if p.startswith(("http://", "https://", "file:")):
        return p
    return ROOT_PREFIX + p.lstrip("/")


def esc(s: Any) -> str:
    return html.escape(str(s if s is not None else ""))


def doclink(path: Any, text: Any) -> str:
    """Link to an internal doc. .md files open in the in-page modal viewer
    (class=docl); everything else (html, csv, external) opens normally."""
    href = link(path)
    if str(path).lower().endswith(".md"):
        return f'<a class="docl" data-doc="{esc(href)}" href="{esc(href)}">{esc(text)}</a>'
    tgt = " target=_blank" if href.startswith(("http://", "https://")) else ""
    return f'<a href="{esc(href)}"{tgt}>{esc(text)}</a>'


# --------------------------------------------------------------------------- #
CSS = """
:root{
  /* light theme (GitHub light palette) */
  --bg:#ffffff; --panel:#f6f8fa; --panel2:#eef1f4; --border:#d0d7de;
  --fg:#1f2328; --muted:#59636e; --accent:#0969da; --accent2:#8250df;
  --green:#1a7f37; --amber:#9a6700; --red:#cf222e; --blue:#0969da; --grey:#6e7781;
  --on-accent:#ffffff;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",Helvetica,Arial,sans-serif;
  font-size:14px;line-height:1.5}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.topbar{position:sticky;top:0;z-index:20;background:linear-gradient(180deg,var(--panel),var(--bg));
  border-bottom:1px solid var(--border);padding:13px 22px;display:flex;
  align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px}
.topbar h1{font-size:17px;margin:0;font-weight:650}
.topbar h1 .dot{color:var(--accent2)}
.meta{color:var(--muted);font-size:12px;display:flex;gap:14px;flex-wrap:wrap;align-items:center}
.meta b{color:var(--fg);font-weight:600}
.wrap{max-width:1560px;margin:0 auto;padding:14px 22px 80px}
nav.tabs{position:sticky;top:50px;z-index:15;background:var(--bg);display:flex;gap:6px;
  flex-wrap:wrap;padding:10px 0;border-bottom:1px solid var(--border);margin-bottom:16px}
nav.tabs button{background:var(--panel);color:var(--muted);border:1px solid var(--border);
  border-radius:8px;padding:6px 13px;font-size:13px;cursor:pointer;transition:.12s}
nav.tabs button:hover{color:var(--fg);border-color:var(--accent)}
nav.tabs button.active{background:var(--accent);color:var(--on-accent);border-color:var(--accent);font-weight:600}
#search{margin-left:auto;background:var(--panel2);border:1px solid var(--border);color:var(--fg);
  border-radius:8px;padding:6px 11px;font-size:13px;min-width:220px}
section.layer{margin-bottom:26px;scroll-margin-top:104px}
section.layer>h2{font-size:15px;margin:4px 0 12px;padding-bottom:7px;border-bottom:1px solid var(--border);
  display:flex;align-items:center;gap:9px}
section.layer>h2 .cnt{color:var(--muted);font-weight:400;font-size:12.5px}
.sub{color:var(--muted);font-size:12.5px;font-weight:600;margin:16px 0 8px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:11px;margin:4px 0 14px}
.kpi{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:12px 14px}
.kpi .v{font-size:22px;font-weight:680}
.kpi .l{color:var(--muted);font-size:12px;margin-top:3px}
.kpi .s{color:var(--muted);font-size:11px;margin-top:5px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:12px}
.card{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:13px 15px}
.card h3{margin:0 0 9px;font-size:13px;font-weight:620;display:flex;justify-content:space-between;align-items:center;gap:8px}
.card.act{border-left:3px solid var(--accent)}.card.act.todo{border-left-color:var(--amber)}.card.act.rec{border-left-color:var(--green)}
ul.items{list-style:none;margin:0;padding:0}
ul.items li{padding:6px 0;border-bottom:1px dashed var(--border);display:flex;gap:8px;align-items:flex-start}
ul.items li:last-child{border-bottom:none}
.pill{display:inline-block;padding:1px 8px;border-radius:20px;font-size:11px;font-weight:600;white-space:nowrap;border:1px solid transparent}
.pill.approved,.pill.green,.pill.BUILDABLE_NOW,.pill.LIKELY_NOVEL,.pill.completed{background:rgba(63,185,80,.15);color:var(--green);border-color:rgba(63,185,80,.4)}
.pill.candidate,.pill.amber,.pill.pending_review,.pill.in_progress,.pill.PARTIAL,.pill.REVIEW,.pill.pending{background:rgba(210,153,34,.15);color:var(--amber);border-color:rgba(210,153,34,.4)}
.pill.draft,.pill.grey,.pill.raw{background:rgba(110,118,129,.18);color:var(--muted);border-color:rgba(110,118,129,.4)}
.pill.quarantine,.pill.red,.pill.deprecated,.pill.NOT_PORTABLE,.pill.DUP{background:rgba(248,81,73,.15);color:var(--red);border-color:rgba(248,81,73,.4)}
.pill.observed,.pill.blue,.pill.board{background:rgba(56,139,253,.15);color:var(--blue);border-color:rgba(56,139,253,.4)}
.pill.auto,.pill.task{background:rgba(188,140,255,.13);color:var(--accent2);border-color:rgba(188,140,255,.4)}
.pill.ok{background:rgba(63,185,80,.15);color:var(--green);border-color:rgba(63,185,80,.4)}
.pill.warn{background:rgba(210,153,34,.15);color:var(--amber);border-color:rgba(210,153,34,.4)}
.pill.error{background:rgba(248,81,73,.15);color:var(--red);border-color:rgba(248,81,73,.4)}
.pill.info{background:rgba(56,139,253,.15);color:var(--blue);border-color:rgba(56,139,253,.4)}
.health{background:var(--panel);border:1px solid var(--border);border-left:3px solid var(--green);border-radius:10px;padding:12px 15px;margin-bottom:14px}
.health.attn{border-left-color:var(--amber)}
.health .hh{font-size:13px;font-weight:620;margin-bottom:9px;display:flex;align-items:center;gap:8px}
.health .hh .cnt{color:var(--muted);font-weight:400;font-size:12px}
.hchecks{display:flex;flex-direction:column;gap:5px;margin-bottom:9px}
.hck{display:flex;align-items:center;gap:8px;font-size:12.5px;flex-wrap:wrap}
.hfiles{display:flex;gap:6px;flex-wrap:wrap;border-top:1px dashed var(--border);padding-top:8px}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th,td{text-align:left;padding:6px 9px;border-bottom:1px solid var(--border);vertical-align:top}
th{color:var(--muted);font-weight:600;position:sticky;top:0;background:var(--panel);z-index:1}
th.sortable{cursor:pointer;user-select:none}
th.sortable:hover{color:var(--fg)}
th .si{color:var(--accent);font-size:10px;margin-left:2px}
td.num{text-align:right;font-variant-numeric:tabular-nums}
.tablewrap{background:var(--panel);border:1px solid var(--border);border-radius:10px;overflow:auto;max-height:600px}
.muted{color:var(--muted)}
.mono{font-family:"SF Mono",ui-monospace,Consolas,monospace;font-size:11.5px}
.warn{background:rgba(207,34,46,.08);border:1px solid rgba(207,34,46,.3);color:var(--red);padding:8px 12px;border-radius:8px;font-size:12.5px;margin-bottom:10px}
.note{background:rgba(9,105,218,.06);border:1px solid rgba(9,105,218,.25);color:#0a52c4;padding:7px 11px;border-radius:8px;font-size:12px;margin-bottom:10px}
/* sub-nav + filter bar */
.subnav{display:flex;gap:6px;flex-wrap:wrap;margin:4px 0 12px}
.subnav button{background:var(--panel2);color:var(--muted);border:1px solid var(--border);border-radius:7px;padding:5px 13px;font-size:12.5px;cursor:pointer}
.subnav button.active{background:var(--accent2);color:var(--on-accent);border-color:var(--accent2);font-weight:600}
.subview{display:none}.subview.active{display:block}
.subnav2{display:flex;gap:4px;flex-wrap:wrap;margin:2px 0 14px;border-bottom:1px solid var(--border)}
.subnav2 button{background:transparent;color:var(--muted);border:0;border-bottom:2px solid transparent;padding:6px 12px;font-size:12.5px;cursor:pointer;margin-bottom:-1px}
.subnav2 button:hover{color:var(--fg)}
.subnav2 button.active{color:var(--fg);border-bottom-color:var(--accent);font-weight:600}
.subview2{display:none}.subview2.active{display:block}
.filterbar{display:flex;gap:7px;flex-wrap:wrap;align-items:center;margin:4px 0 11px}
.filterbar .fb{background:var(--panel2);color:var(--muted);border:1px solid var(--border);border-radius:6px;padding:4px 10px;font-size:12px;cursor:pointer}
.filterbar .fb.active{background:var(--accent);color:var(--on-accent);border-color:var(--accent);font-weight:600}
.filterbar input,.filterbar select{background:var(--panel2);border:1px solid var(--border);color:var(--fg);border-radius:6px;padding:4px 9px;font-size:12px}
.filterbar .lbl{color:var(--muted);font-size:11.5px}
.fhide{display:none!important}
/* expandable rows */
.exp{background:var(--panel);border:1px solid var(--border);border-radius:9px;margin-bottom:7px;overflow:hidden}
.exp>.eh{display:flex;gap:9px;align-items:center;flex-wrap:wrap;cursor:pointer;padding:9px 13px}
.exp>.eh:hover{background:var(--panel2)}
.exp>.eb{display:none;padding:2px 13px 11px;border-top:1px solid var(--border)}
.exp.open>.eb{display:block}
.exp .arrow,.frow .arrow{color:var(--muted);font-size:10px;transition:.15s}
.exp.open .arrow{transform:rotate(90deg)}
.exp .abs{color:var(--muted);font-size:12px;margin-top:8px}
/* factor master-detail */
tr.frow{cursor:pointer}
tr.frow:hover{background:var(--panel2)}
tr.frow.open .arrow{transform:rotate(90deg);display:inline-block}
tr.fdetail{display:none}
tr.fdetail.open{display:table-row}
tr.fdetail>td{background:var(--bg);padding:12px 14px}
.fdcard .en{margin:2px 0;font-size:13px}
.fdcard .cn{color:var(--muted);margin-bottom:7px}
.fdcard .fx{background:var(--panel);border:1px solid var(--border);border-radius:6px;padding:6px 8px;margin:7px 0;white-space:pre-wrap;word-break:break-all;font-size:11.5px}
.kv{display:flex;gap:7px;flex-wrap:wrap;font-size:11.5px;color:var(--muted);margin:3px 0}
.kv b{color:var(--fg);font-weight:600}
.chips{display:flex;gap:5px;flex-wrap:wrap}
.chip{background:var(--panel2);border:1px solid var(--border);border-radius:5px;padding:1px 7px;font-size:11px;color:var(--muted)}
.chip b{color:var(--fg)}
/* hypothesis storyline cards */
.hcard>.eh .hsum{flex:1;min-width:220px;font-size:12.5px;color:var(--fg)}
.hcard>.eh .hsum .muted{font-weight:600}
.hsec{font-weight:700;font-size:11.5px;margin:11px 0 5px;color:var(--accent2);letter-spacing:.3px}
.htx{font-size:12.5px;line-height:1.5;margin:2px 0}
.tl{border-left:2px solid var(--border);margin:3px 0 3px 5px;padding-left:12px}
.tli{position:relative;margin:0 0 11px}
.tli::before{content:"";position:absolute;left:-17px;top:4px;width:8px;height:8px;border-radius:50%;background:var(--accent2);border:2px solid var(--bg)}
.tlh{display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-size:12px}
.tlh .d{color:var(--muted);font-size:11px;font-family:ui-monospace,Consolas,monospace}
.tlh b{font-weight:700}
.crit{display:flex;gap:5px;flex-wrap:wrap;margin:5px 0}
.cpill{font-size:10.5px;padding:1px 6px;border-radius:5px;border:1px solid var(--border);font-family:ui-monospace,Consolas,monospace;white-space:nowrap}
.cpill.ok{background:rgba(63,185,80,.11);color:var(--green);border-color:rgba(63,185,80,.3)}
.cpill.bad{background:rgba(248,81,73,.12);color:var(--red);border-color:rgba(248,81,73,.4);font-weight:700}
.cpill.soft{background:rgba(210,153,34,.1);color:var(--amber);border-color:rgba(210,153,34,.3)}
.cpill.na{color:var(--grey);opacity:.7}
.hfail{color:var(--red);font-weight:700}
.trsn{font-size:11.5px;color:var(--muted);line-height:1.5;margin:3px 0}
.mtab{border-collapse:collapse;margin:5px 0;font-size:11.5px}
.mtab th,.mtab td{border:1px solid var(--border);padding:3px 12px;text-align:right;font-variant-numeric:tabular-nums}
.mtab th{background:var(--panel2);color:var(--muted);font-weight:600}
.mtab td.ml{text-align:left;color:var(--muted)}
.rwarn{background:rgba(210,153,34,.1);border:1px solid rgba(210,153,34,.4);border-radius:6px;padding:6px 10px;margin:6px 0;font-size:11.5px;color:var(--amber);line-height:1.55}
.rbadge{font-size:10px;padding:1px 6px;border-radius:5px;background:rgba(210,153,34,.15);color:var(--amber);border:1px solid rgba(210,153,34,.4);white-space:nowrap}
.bars{display:flex;flex-direction:column;gap:3px}
.bar{display:flex;align-items:center;gap:8px;font-size:12px}
.bar .t{width:120px;color:var(--muted);flex-shrink:0}
.bar .g{height:9px;background:var(--accent);border-radius:3px;min-width:2px}
.bar .n{color:var(--muted);font-size:11px}
/* sessions */
.sess{background:var(--panel);border:1px solid var(--border);border-radius:9px;margin-bottom:9px;padding:11px 14px}
.sess .h{display:flex;gap:10px;align-items:center;flex-wrap:wrap;cursor:pointer}
.sess .ttl{font-weight:560;flex:1;min-width:200px}
.sess .det{margin-top:9px;padding-top:9px;border-top:1px dashed var(--border);display:none;font-size:12.5px}
.sess.open .det{display:block}
.sess .sm{color:var(--muted);font-size:11.5px}
.todo-done b{color:var(--green)} .todo-active b{color:var(--amber)}
.timeline{border-left:2px solid var(--border);margin-left:6px;padding-left:16px}
.tl-item{position:relative;padding:6px 0}
.tl-item::before{content:"";position:absolute;left:-22px;top:11px;width:8px;height:8px;border-radius:50%;background:var(--accent)}
.tl-item .d{color:var(--accent);font-size:11.5px;font-weight:600;margin-right:8px;font-variant-numeric:tabular-nums}
/* modal md viewer */
.modal{position:fixed;inset:0;background:rgba(0,0,0,.62);z-index:50;display:none;padding:38px 18px}
.modal.open{display:block}
.mbox{max-width:920px;margin:0 auto;background:var(--panel);border:1px solid var(--border);border-radius:12px;max-height:88vh;display:flex;flex-direction:column}
.mhead{display:flex;justify-content:space-between;align-items:center;padding:11px 18px;border-bottom:1px solid var(--border)}
.mhead .mt{font-weight:600;font-size:13px;word-break:break-all}
.mhead .mx{cursor:pointer;color:var(--muted);font-size:22px;line-height:1;padding:0 4px}
.mbody{padding:14px 22px;overflow:auto}
.mbody h1,.mbody h2,.mbody h3,.mbody h4{border-bottom:1px solid var(--border);padding-bottom:5px;margin:14px 0 8px}
.mbody code{background:var(--bg);padding:1px 5px;border-radius:4px;font-size:12px}
.mbody pre{background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:10px;overflow:auto}
.mbody pre code{background:none;padding:0}
.mbody a{color:var(--accent)}
.hide{display:none!important}
.foot{color:var(--muted);font-size:11.5px;text-align:center;margin-top:40px;padding-top:16px;border-top:1px solid var(--border)}
#updbar{position:fixed;right:18px;bottom:18px;z-index:60;display:none;align-items:center;gap:7px;
  background:var(--accent);color:var(--on-accent);font-weight:600;font-size:12.5px;padding:8px 14px;border-radius:20px;
  cursor:pointer;box-shadow:0 4px 16px rgba(0,0,0,.45)}
#updbar:hover{filter:brightness(1.08)}
"""

JS = r"""
const tabs=[...document.querySelectorAll('nav.tabs button[data-t]')];
const secs=[...document.querySelectorAll('section.layer')];
function show(id){
  tabs.forEach(b=>b.classList.toggle('active',b.dataset.t===id));
  if(id==='all'){secs.forEach(s=>s.classList.remove('hide'));}
  else{secs.forEach(s=>s.classList.toggle('hide',s.id!==id));}
  window.scrollTo({top:0,behavior:'smooth'});
}
tabs.forEach(b=>b.onclick=()=>show(b.dataset.t));

function applyFilter(bar){
  const scope=document.querySelector(bar.dataset.scope); if(!scope)return;
  const status=bar.dataset.status||'all';
  const inp=bar.querySelector('input.ft'), sel=bar.querySelector('select.fc');
  const q=inp?inp.value.trim().toLowerCase():'', cat=sel?sel.value:'';
  scope.querySelectorAll('[data-row]').forEach(row=>{
    const okS=status==='all'||row.dataset.status===status;
    const okC=!cat||row.dataset.cat===cat;
    const okQ=!q||(row.getAttribute('data-f')||'').toLowerCase().includes(q);
    const vis=okS&&okC&&okQ;
    row.classList.toggle('fhide',!vis);
    const d=row.nextElementSibling;
    if(d&&d.classList.contains('fdetail')){d.classList.toggle('fhide',!vis); if(!vis){d.classList.remove('open');row.classList.remove('open');}}
  });
}
function mdToHtml(md){
  const e=s=>s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  const blk=[]; md=md.replace(/```([\s\S]*?)```/g,(m,c)=>{blk.push('<pre><code>'+e(c.replace(/^[a-z]*\n/,''))+'</code></pre>');return ''+(blk.length-1)+'';});
  const il=s=>e(s).replace(/`([^`]+)`/g,'<code>$1</code>').replace(/\*\*([^*]+)\*\*/g,'<b>$1</b>').replace(/\*([^*\n]+)\*/g,'<i>$1</i>').replace(/\[([^\]]+)\]\(([^)]+)\)/g,'<a href="$2" target="_blank">$1</a>');
  let h='',inL=false; for(const raw of md.split('\n')){const l=raw;
    const ph=l.trim().match(/^(\d+)$/); if(ph){if(inL){h+='</ul>';inL=false;}h+=blk[+ph[1]];continue;}
    let m; if(m=l.match(/^(#{1,4})\s+(.*)/)){if(inL){h+='</ul>';inL=false;}h+='<h'+m[1].length+'>'+il(m[2])+'</h'+m[1].length+'>';}
    else if(/^\s*([-*]|\d+\.)\s+/.test(l)){if(!inL){h+='<ul>';inL=true;}h+='<li>'+il(l.replace(/^\s*([-*]|\d+\.)\s+/,''))+'</li>';}
    else if(l.trim()===''){if(inL){h+='</ul>';inL=false;}}
    else{if(inL){h+='</ul>';inL=false;}h+='<p>'+il(l)+'</p>';}}
  if(inL)h+='</ul>'; return h;
}
function openDoc(path,title){
  const m=document.getElementById('docmodal'); m.querySelector('.mt').textContent=title||path;
  const body=m.querySelector('.mbody'); body.innerHTML='<div class="muted">加载中…</div>'; m.classList.add('open');
  fetch(path).then(r=>{if(!r.ok)throw 0;return r.text();}).then(t=>{body.innerHTML=mdToHtml(t);})
   .catch(()=>{body.innerHTML='<div class="warn">无法在页内加载——file:// 双击打开时浏览器禁止 fetch 本地文件。请通过本地服务打开看板：双击 <b>src/dashboard/serve_dashboard.bat</b>（或运行 <code>python -m http.server</code> 后访问 localhost）。</div><a href="'+path+'" target="_blank">↗ 在新标签直接打开该文档</a>';});
}
function sortTable(th){
  const table=th.closest('table'), head=th.parentElement, ci=[...head.children].indexOf(th);
  const tb=table.tBodies[0], rows=[...tb.rows], units=[];
  for(let i=0;i<rows.length;i++){ if(rows[i].classList.contains('fdetail'))continue;
    const u=[rows[i]]; while(i+1<rows.length&&rows[i+1].classList.contains('fdetail'))u.push(rows[++i]); units.push(u); }
  const asc=th.dataset.dir!=='asc';
  [...head.children].forEach(h=>{h.dataset.dir='';const s=h.querySelector('.si');if(s)s.remove();});
  th.dataset.dir=asc?'asc':'desc';
  const txt=u=>{const c=u[0].children[ci];return c?c.textContent.trim():'';};
  const num=s=>{s=s.replace(/,/g,'').trim();let m;
    if(m=s.match(/^([-+]?\d*\.?\d+)$/))return parseFloat(m[1]);
    if(m=s.match(/^([-+]?\d*\.?\d+)\s*\/\s*\d+$/))return parseFloat(m[1]);
    return null;};
  units.sort((a,b)=>{const x=txt(a),y=txt(b),nx=num(x),ny=num(y);
    if(nx!==null&&ny!==null)return asc?nx-ny:ny-nx;
    if(nx!==null)return -1; if(ny!==null)return 1;
    return asc?x.localeCompare(y):y.localeCompare(x);});
  units.forEach(u=>u.forEach(r=>tb.appendChild(r)));
  const si=document.createElement('span');si.className='si';si.textContent=asc?'▲':'▼';th.appendChild(si);
}
document.addEventListener('click',e=>{
  const sth=e.target.closest('th.sortable'); if(sth){sortTable(sth);return;}
  const sn=e.target.closest('.subnav button');
  if(sn){const w=sn.closest('.layer');w.querySelectorAll('.subnav button').forEach(b=>b.classList.toggle('active',b===sn));
    w.querySelectorAll('.subview').forEach(v=>v.classList.toggle('active',v.dataset.sv===sn.dataset.sv));return;}
  const sn2=e.target.closest('.subnav2 button');
  if(sn2){const w=sn2.closest('.subview');
    w.querySelectorAll(':scope>.subnav2 button').forEach(b=>b.classList.toggle('active',b===sn2));
    w.querySelectorAll(':scope>.subview2').forEach(v=>v.classList.toggle('active',v.dataset.sv2===sn2.dataset.sv2));return;}
  const fb=e.target.closest('.filterbar .fb');
  if(fb){const bar=fb.closest('.filterbar');bar.querySelectorAll('.fb').forEach(b=>b.classList.toggle('active',b===fb));bar.dataset.status=fb.dataset.status;applyFilter(bar);return;}
  const dl=e.target.closest('a.docl'); if(dl){e.preventDefault();openDoc(dl.dataset.doc,dl.textContent);return;}
  if(e.target.id==='docmodal'||e.target.closest('#docmodal .mx')){document.getElementById('docmodal').classList.remove('open');return;}
  const fr=e.target.closest('tr.frow'); if(fr){const d=fr.nextElementSibling;if(d&&d.classList.contains('fdetail')){d.classList.toggle('open');fr.classList.toggle('open');}return;}
  const h=e.target.closest('.exp>.eh, .sess .h'); if(h){(h.closest('.exp')||h.parentElement).classList.toggle('open');return;}
});
document.addEventListener('input',e=>{const bar=e.target.closest('.filterbar');if(bar)applyFilter(bar);});
document.addEventListener('change',e=>{const bar=e.target.closest('.filterbar');if(bar)applyFilter(bar);});
document.addEventListener('keydown',e=>{if(e.key==='Escape')document.getElementById('docmodal').classList.remove('open');});
const sb=document.getElementById('search');
sb.addEventListener('input',()=>{const q=sb.value.trim().toLowerCase();
  secs.forEach(s=>s.classList.remove('hide')); tabs.forEach(b=>b.classList.toggle('active',b.dataset.t==='all'));
  document.querySelectorAll('[data-f]').forEach(el=>{el.classList.toggle('hide', q && !el.getAttribute('data-f').toLowerCase().includes(q));});
});
show('actions');

// lightweight auto-refresh: poll the tiny build_id.txt every 30s. A new build
// silently reloads background/idle tabs; an actively-used tab gets a click-to-
// refresh banner instead (never yanks the page out from under you). Fails
// silently on file:// (fetch blocked) — only active when served over http.
let _lastAct=Date.now(), _newBuild=false;
['mousemove','keydown','click','scroll','touchstart'].forEach(ev=>addEventListener(ev,()=>_lastAct=Date.now(),{passive:true,capture:true}));
function _reloadIfSafe(){ if(_newBuild && (document.hidden || Date.now()-_lastAct>45000)) location.reload(); }
document.addEventListener('visibilitychange',_reloadIfSafe);
setInterval(()=>{
  fetch('build_id.txt?t='+Date.now(),{cache:'no-store'}).then(r=>r.ok?r.text():'').then(t=>{
    t=(t||'').trim();
    if(t && typeof BUILD_ID!=='undefined' && t!==BUILD_ID){ _newBuild=true; const b=document.getElementById('updbar'); if(b)b.style.display='inline-flex'; _reloadIfSafe(); }
  }).catch(()=>{});
}, 30000);
"""


def pill(text: Any, cls: str | None = None) -> str:
    c = (cls if cls is not None else str(text)).strip().replace(" ", "_")
    return f'<span class="pill {esc(c)}">{esc(text)}</span>'


def _fmt(v) -> str:
    return "—" if v is None or v == "" else esc(v)


def _lead(cards: list[tuple]) -> str:
    out = ['<div class="kpis">']
    for label, val, sub in cards:
        out.append(f'<div class="kpi"><div class="v">{esc(val)}</div><div class="l">{esc(label)}</div><div class="s">{esc(sub)}</div></div>')
    out.append("</div>")
    return "".join(out)


def _tally_str(d: dict) -> str:
    return " · ".join(f"{k} {v}" for k, v in d.items()) or "—"


def _statusbar(scope: str, statuses: list[str], text_ph: str, cats: list[str] | None = None) -> str:
    """A per-section filter bar: status buttons + optional category select + text."""
    out = [f'<div class="filterbar" data-scope="{esc(scope)}" data-status="all">',
           '<span class="lbl">状态</span><span class="fb active" data-status="all">全部</span>']
    for s in statuses:
        out.append(f'<span class="fb" data-status="{esc(s)}">{esc(s)}</span>')
    if cats:
        out.append('<span class="lbl">类别</span><select class="fc"><option value="">全部</option>')
        for c in cats:
            out.append(f'<option value="{esc(c)}">{esc(c)}</option>')
        out.append("</select>")
    out.append(f'<input class="ft" placeholder="🔍 {esc(text_ph)}">')
    out.append("</div>")
    return "".join(out)


# --------------------------------------------------------------------------- #
def _action_card(title: str, items: list[dict], cls: str) -> str:
    out = [f'<div class="card act {cls}"><h3>{esc(title)}<span class="muted">{len(items)}</span></h3><ul class="items">']
    if not items:
        out.append('<li class="muted">（暂无）</li>')
    for it in items:
        extra = (" " + pill(it["status"])) if it.get("status") else ""
        if it.get("session"):
            extra += f' <span class="chip">{esc(it["session"])}</span>'
        srcpill = pill(it["src"]) if it.get("src") else ""
        out.append(f'<li data-f="{esc(it.get("text",""))}">{srcpill}<span>{esc(it.get("text",""))}{extra}</span></li>')
    out.append("</ul></div>")
    return "".join(out)


def _health_panel(ctx: dict) -> str:
    h = ctx.get("health") or {}
    checks = h.get("checks", []); files = h.get("files", []); summ = h.get("summary", {})
    attn = summ.get("warn", 0) + summ.get("error", 0)
    status = "全部正常 ✓" if not attn else f"{attn} 项需关注"
    out = [f'<div class="health{" attn" if attn else ""}"><div class="hh">🩺 数据新鲜度 / 一致性自审 '
           f'<span class="cnt">{esc(status)} · 每次重建自检源文件，落后即标红</span></div>']
    if h.get("error"):
        out.append(f'<div class="warn">{esc(h["error"])}</div>')
    out.append('<div class="hchecks">')
    for c in checks:
        out.append(f'<div class="hck" data-f="{esc(c["label"])} {esc(c["hint"])}">'
                   f'{pill(c["value"], c["level"])}<b>{esc(c["label"])}</b>'
                   f'<span class="muted">— {esc(c["hint"])}</span></div>')
    out.append('</div><div class="hfiles"><span class="muted" style="font-size:11px">源文件最后修改:</span>')
    for f in files:
        cls = "" if f.get("exists") else "muted"
        out.append(f'<span class="chip {cls}">{esc(f["label"])} <b>{esc(f["age"])}</b></span>')
    out.append("</div></div>")
    return "".join(out)


def _actions(ctx: dict) -> str:
    a = ctx["actions"]
    return "".join([
        f'<section class="layer" id="actions"><h2>📌 事项 <span class="cnt">当前分支 {esc(a.get("branch","?"))}</span></h2>',
        _health_panel(ctx),
        '<div class="grid">',
        _action_card("🔵 进行中", a.get("in_progress", []), "ip"),
        _action_card("🟡 待办", a.get("todo", []), "todo"),
        _action_card("🟢 推荐", a.get("recommended", []), "rec"),
        "</div></section>"])


_DIM_CLS = {"FRONTIER_OPEN": "green", "METHOD": "blue", "FRONTIER_BLOCKED": "amber",
            "SATURATED": "grey", "NOT_PORTABLE": "red"}
_DIM_STATUS_CN = {"FRONTIER_OPEN": "开放前沿 · 有数据未挖", "METHOD": "方法学 · 改进组合方式",
                  "FRONTIER_BLOCKED": "受阻前沿 · 缺数据", "SATURATED": "已饱和 · 簿已覆盖",
                  "NOT_PORTABLE": "不可移植"}
_DIM_ORDER = ["FRONTIER_OPEN", "METHOD", "FRONTIER_BLOCKED", "SATURATED", "NOT_PORTABLE"]
_TIER_CN = {1: "Tier 1 · 可即建前沿方向", 2: "Tier 2 · 方法学升级", 3: "Tier 3 · 受阻（数据采集目标）",
            4: "Tier 4 · 低优先"}
_PIPELINE = [
    ("取数 acquire", "主题相关性收割 · q-fin + cs.LG + econ.EM"),
    ("知识骨干 know", "数据清单 + 饱和分类法 + 打分词典"),
    ("价值打分 score", "相关闸 × (维度·实证·新近·影响·中国)"),
    ("方向聚类 map", "按维度聚类 → 研究方向 + 草稿 stub"),
]


def _arxiv_abs(aid: str) -> str:
    aid = (aid or "").strip()
    return f"https://arxiv.org/abs/{aid}" if aid else ""


_LC_ORDER = {"in_progress": 0, "completed": 1, "planned": 2}
_LC_BADGE = {"planned": ("计划", "grey"), "in_progress": ("进行中", "amber"), "completed": ("已完成", "green")}
_OUTCOME_CLS = {"win": "green", "mixed": "amber", "fail": "red"}


def _direction_card(d: dict) -> str:
    """One research-direction card, rendered by lifecycle (planned proposal /
    in_progress progress / completed results)."""
    did = d.get("id", ""); st = d.get("status", ""); lc = d.get("lifecycle", "planned")
    en, cn = direction_desc(did)
    oneliner = cn or d.get("en", "")
    lc_txt, lc_cls = _LC_BADGE.get(lc, ("计划", "grey"))
    star = ' <span title="首选">⭐</span>' if d.get("top_pick") else ''
    badges = pill(lc_txt, lc_cls) + ' ' + pill(st, _DIM_CLS.get(st, "grey"))
    if lc == "planned":
        badges += ' ' + (pill("可即建", "green") if d.get("buildable") else pill("受阻", "amber"))
    tierchip = f'<span class="chip">Tier {d.get("tier")}</span>' if d.get("tier") else ''
    srcs = " ".join(f'<a href="{esc(_arxiv_abs(a))}" target="_blank" class="mono">arXiv:{esc(a)}↗</a>'
                    for a in (d.get("source_arxiv") or []))
    accent = "border-left:3px solid var(--accent2)" if d.get("top_pick") else (
        "border-left:3px solid var(--green)" if lc == "completed" and d.get("outcome_kind") != "fail"
        else "border-left:3px solid var(--red)" if lc == "completed" else "")
    src = d.get("source_kind") or "arxiv"
    ftext = f'{did} {d.get("title","")} {oneliner} {st} {lc} {src} {d.get("factor_name","")}'
    out = [f'<div class="card" data-row data-status="{esc(lc)}" data-cat="{esc(src)}" data-f="{esc(ftext)}" '
           f'style="margin-bottom:8px;{accent}">',
           f'<h3>{esc(did)} · {esc(d.get("title",""))}{star} '
           f'<span style="font-weight:400">{badges} {tierchip}</span></h3>',
           f'<div style="margin:4px 0 6px">{esc(oneliner)}</div>']
    if d.get("factor_name"):
        out.append(f'<div class="muted mono" style="font-size:11px">因子 {esc(d["factor_name"])}</div>')

    if lc == "completed":
        res = d.get("results", {}) or {}
        ocls = _OUTCOME_CLS.get(d.get("outcome_kind", "mixed"), "grey")
        out.append(f'<div style="margin:6px 0">{pill("结果", ocls)} <b>{esc(res.get("outcome",""))}</b></div>')
        tl = res.get("timeline") or []
        if tl:
            out.append('<div style="font-size:11.5px;margin:4px 0"><span class="muted">时间线</span>'
                       '<ul class="items" style="margin:3px 0 0">')
            for step in tl:
                out.append(f'<li>{esc(step)}</li>')
            out.append('</ul></div>')
        if res.get("verdict"):
            out.append(f'<div class="muted" style="font-size:11.5px;margin-top:4px">结论：{esc(res["verdict"])}</div>')
        links = res.get("links") or []
        if links:
            out.append('<div style="font-size:11px;margin-top:5px"><span class="muted">产物 </span>'
                       + " · ".join(doclink(ln.get("path", ""), ln.get("title", "")) for ln in links) + '</div>')
    elif lc == "in_progress":
        prog = d.get("progress", {}) or {}
        if prog.get("current_step"):
            out.append(f'<div style="margin:6px 0">{pill("进展", "amber")} <b>{esc(prog["current_step"])}</b></div>')
        for note in (prog.get("notes") or []):
            out.append(f'<div class="muted" style="font-size:11.5px">• {esc(note)}</div>')
        if d.get("factor_expr"):
            out.append(f'<div class="mono" style="font-size:11.5px;background:var(--panel2);padding:5px 8px;'
                       f'border-radius:6px;margin:5px 0;overflow-x:auto">{esc(d["factor_expr"])}</div>')
        links = prog.get("links") or []
        if links:
            out.append('<div style="font-size:11px;margin-top:5px"><span class="muted">产物 </span>'
                       + " · ".join(doclink(ln.get("path", ""), ln.get("title", "")) for ln in links) + '</div>')
    else:  # planned
        if d.get("factor_expr"):
            out.append(f'<div class="mono" style="font-size:11.5px;background:var(--panel2);padding:5px 8px;'
                       f'border-radius:6px;margin:5px 0;overflow-x:auto">{esc(d["factor_expr"])}</div>')
        fields = d.get("fields") or []
        if fields:
            out.append('<div style="font-size:11.5px;margin:4px 0"><span class="muted">字段 </span>'
                       + " ".join(f'<span class="chip mono">{esc(f)}</span>' for f in fields) + '</div>')
        if d.get("novelty"):
            out.append(f'<div class="muted" style="font-size:11.5px">正交性：{esc(d.get("novelty",""))}</div>')
        if d.get("caveats"):
            out.append(f'<div class="muted" style="font-size:11.5px">注意：{esc(d.get("caveats",""))}</div>')
    if srcs or d.get("source_note"):
        out.append(f'<div class="muted" style="font-size:11px;margin-top:4px">来源 {srcs} · {esc(d.get("source_note",""))}</div>')
    out.append('</div>')
    return "".join(out)


_SRC_KIND_CN = {"academic": "学术", "anomaly_catalog": "异象目录", "structured_data": "结构化数据",
                "brokerage": "券商研报", "news": "新闻资讯", "alt_data": "另类数据"}
_PROVIDES_CN = {"research_directions": "研究方向", "value_papers": "价值论文", "value_articles": "价值文章",
                "saturation_map": "饱和地图", "signal_catalog": "信号目录"}


def _source_card(s: dict) -> str:
    """One knowledge-source card for the 知识源 overview (active vs planned)."""
    sid = s.get("id", ""); status = s.get("status", "planned")
    name = s.get("name_cn") or s.get("name_en") or sid
    summary = s.get("summary_cn") or s.get("summary_en") or ""
    active = status == "active"
    st_badge = pill("活跃", "green") if active else pill("计划接入", "grey")
    kind_badge = pill(_SRC_KIND_CN.get(s.get("kind", ""), s.get("kind", "")), "blue")
    stats = s.get("_stats", {}) or {}
    accent = "border-left:3px solid var(--green)" if active else "border-left:3px solid var(--border)"
    bits = []
    if stats.get("directions"):
        bits.append(f'{stats["directions"]} 研究方向')
    if stats.get("completed"):
        bits.append(f'{stats["completed"]} 已完成')
    if stats.get("papers"):
        bits.append(f'{stats["papers"]} 价值内容')
    statline = " · ".join(bits) or ("未接入（见 sources.yaml）" if not active else "—")
    provides = " ".join(f'<span class="chip">{esc(_PROVIDES_CN.get(p, p))}</span>' for p in (s.get("provides") or []))
    links = " · ".join(doclink(l.get("path", ""), l.get("title", "")) for l in (s.get("links") or []) if l.get("path"))
    out = [f'<div class="card" data-row data-status="{esc(status)}" data-cat="{esc(sid)}" '
           f'data-f="{esc(sid)} {esc(name)} {esc(summary)}" '
           f'style="opacity:{"1" if active else ".7"};{accent}">',
           f'<h3>{esc(name)} <span style="font-weight:400">{st_badge} {kind_badge}</span></h3>',
           f'<div style="font-size:11.5px;color:var(--muted);margin:5px 0">{esc(summary)}</div>']
    if s.get("pipeline_cn"):
        out.append(f'<div class="mono" style="font-size:10.5px;color:var(--muted)">{esc(s["pipeline_cn"])}</div>')
    out.append(f'<div class="sm" style="margin-top:5px;color:var(--muted)">{esc(statline)}</div>')
    if provides:
        out.append(f'<div style="margin-top:5px">{provides}</div>')
    if links:
        out.append(f'<div style="font-size:11px;margin-top:5px"><span class="muted">入口 </span>{links}</div>')
    out.append('</div>')
    return "".join(out)


_SRC_TAB = {"arxiv": "arXiv", "osap": "OSAP", "report_rc": "report_rc",
            "brokerage_report": "券商研报", "journal": "期刊/SSRN", "news": "财经新闻"}


def _source_sections(s: dict) -> list[tuple]:
    """The level-2 sections a source provides, in display order."""
    prov = set(s.get("provides") or [])
    sects = []
    if "saturation_map" in prov:
        sects.append(("framework", "知识框架"))
    if "research_directions" in prov:
        sects.append(("directions", "研究方向"))
    if prov & {"value_papers", "value_articles", "signal_catalog"}:
        sects.append(("content", "价值内容"))
    return sects or [("directions", "研究方向")]


def _kn_saturation(dims: list) -> str:
    out = ['<div class="sub">饱和地图 · alpha 对本簿还活在哪个维度（论文数 = 当前 arXiv 语料 top-80 命中；跨源研究前沿）</div>']
    for st in _DIM_ORDER:
        here = [d for d in dims if d.get("status") == st]
        if not here:
            continue
        here.sort(key=lambda d: -d.get("count", 0))
        out.append(f'<div class="card" style="margin-bottom:8px"><div style="margin-bottom:7px">'
                   f'{pill(_DIM_STATUS_CN.get(st, st), _DIM_CLS.get(st,"grey"))}</div>'
                   '<div style="display:flex;flex-wrap:wrap;gap:6px">')
        for d in here:
            en, cn = dim_label(d.get("key", ""))
            label = cn or d.get("label") or d.get("key")
            cnt = d.get("count", 0)
            build = "✓" if d.get("buildable_now") else ("⛔" if st in ("FRONTIER_BLOCKED", "NOT_PORTABLE") else "")
            cbadge = f'<span class="mono" style="color:var(--muted)">{cnt}</span>' if cnt else ''
            out.append(f'<span class="chip" title="{esc(d.get("note",""))}">{esc(label)} '
                       f'{cbadge} <span class="muted">{build}</span></span>')
        out.append('</div></div>')
    return "".join(out)


def _kn_framework(corp: dict, dims: list) -> str:
    out = ['<div class="note">价值定义：<b>P(论文 → 一个新的、正交的、可部署的 A 股因子)</b> —— 非引用数 / 非新近度。'
           '价值打分是确定性的<b>分诊先验</b>，精读（研究方向）才是定论。论文是<b>假设源、永不为证据</b>。'
           f'{doclink("workspace/research/idea_sourcing/knowledge/KNOWLEDGE_FRAMEWORK.md", "框架设计文档")}</div>',
           '<div class="sub">知识框架 · 取数 → 知识骨干 → 价值打分 → 方向聚类</div>', '<div class="grid">']
    for i, (lab, note) in enumerate(_PIPELINE, 1):
        out.append(f'<div class="card"><h3>{i}. {esc(lab)}</h3>'
                   f'<div class="muted" style="font-size:12px">{esc(note)}</div></div>')
    out.append('</div>')
    out.append(_kn_saturation(dims))
    return "".join(out)


def _kn_directions(src_dirs: list, scope_id: str) -> str:
    out = ['<div class="note">该数据源的研究方向，<b>全生命周期</b>：计划 → 进行中 → 已完成。计划=价值内容的精读提炼'
           '（DRAFT 假设，仍须走 sandbox → 边际正交检验 vs 簿 → factor_lifecycle → sealed-OOS）；已完成留档流程与结论。'
           f'{doclink("workspace/research/idea_sourcing/knowledge/research_directions.yaml", "方向记录(yaml)")}</div>']
    nlc: dict[str, int] = {}
    for d in src_dirs:
        nlc[d.get("lifecycle", "planned")] = nlc.get(d.get("lifecycle", "planned"), 0) + 1
    out.append(f'<div class="filterbar" data-scope="#{scope_id}" data-status="all">'
               '<span class="lbl">阶段</span><span class="fb active" data-status="all">全部</span>'
               f'<span class="fb" data-status="planned">计划 {nlc.get("planned",0)}</span>'
               f'<span class="fb" data-status="in_progress">进行中 {nlc.get("in_progress",0)}</span>'
               f'<span class="fb" data-status="completed">已完成 {nlc.get("completed",0)}</span>'
               '<input class="ft" placeholder="🔍 按方向/字段/结论过滤…"></div>')
    out.append(f'<div id="{scope_id}">')
    if not src_dirs:
        out.append('<div class="muted" style="padding:8px">（该源暂无登记的研究方向）</div>')
    for d in sorted(src_dirs, key=lambda x: (_LC_ORDER.get(x.get("lifecycle", "planned"), 9), x.get("tier") or 9)):
        out.append(_direction_card(d))
    out.append('</div>')
    return "".join(out)


def _kn_papers(ranked: list, scope_id: str, corp: dict) -> str:
    out = [f'<div class="note">该数据源的价值内容 · arXiv 价值排序论文（语料 {corp.get("papers",0)} 篇 → 过相关闸 '
           f'{corp.get("ranked",0)} 篇，显示 top-60）。分数 = 相关闸 ×(维度·实证·新近·影响·中国)，是<b>分诊先验</b>非定论。'
           '点表头按分数/引用/年排。</div>',
           f'<div class="filterbar" data-scope="#{scope_id}" data-status="all">'
           '<span class="lbl">维度</span><span class="fb active" data-status="all">全部</span>'
           '<span class="fb" data-status="FRONTIER_OPEN">FRONTIER_OPEN</span>'
           '<span class="fb" data-status="METHOD">METHOD</span>'
           '<span class="fb" data-status="FRONTIER_BLOCKED">FRONTIER_BLOCKED</span>'
           '<span class="fb" data-status="SATURATED">SATURATED</span>'
           '<input class="ft" placeholder="🔍 按标题/维度过滤…"></div>',
           f'<div class="tablewrap" id="{scope_id}"><table><thead><tr>'
           '<th class="sortable num">#</th><th class="sortable num">分数</th><th class="sortable">维度</th>'
           '<th class="sortable">状态</th><th class="sortable">可建</th><th class="sortable num">引用</th>'
           '<th class="sortable num">年</th><th>论文（点 abs 看原文）</th></tr></thead><tbody>']
    for p in ranked:
        st = p.get("status", "")
        cn = paper_gloss(p.get("id", ""))
        build = pill("可建", "green") if p.get("buildable") else (pill("阻", "amber") if st in ("FRONTIER_BLOCKED", "NOT_PORTABLE") else "—")
        cites = p.get("cites")
        score = p.get("score", 0) or 0
        gloss_html = f'<div class="muted" style="font-size:11px">{esc(cn)}</div>' if cn else ''
        abs_html = (f'<div class="muted" style="font-size:10.5px">{esc(p.get("abstract","")[:140])}…</div>'
                    if p.get("abstract") else '')
        out.append(f'<tr data-row data-status="{esc(st)}" data-f="{esc(p["title"])} {esc(p["dim"])}">'
                   f'<td class="num muted">{esc(p.get("rank",""))}</td>'
                   f'<td class="num"><b>{score:.3f}</b></td>'
                   f'<td class="muted">{esc(p.get("dim",""))}</td><td>{pill(st, _DIM_CLS.get(st,"grey"))}</td>'
                   f'<td>{build}</td><td class="num muted">{esc(cites) if cites is not None else "—"}</td>'
                   f'<td class="num muted">{esc(p.get("year",""))}</td>'
                   f'<td>{esc(p.get("title",""))}{gloss_html}{abs_html}'
                   f'<a href="{esc(link(p.get("url","")))}" target="_blank" class="sm">abs↗</a></td></tr>')
    out.append("</tbody></table></div>")
    return "".join(out)


def _kn_osap_triage(osap: list, ft: dict) -> str:
    out = [f'<div class="note">该数据源的价值内容 · OSAP 212 美股异象信号目录，A股可行性×新颖度三筛（{_tally_str(ft)}）。'
           '可筛选 / 点表头排序。每条是一个可移植性已评估的候选方向。</div>',
           _statusbar("#osap-list", ["BUILDABLE_NOW", "PARTIAL", "NOT_PORTABLE"], "按代号/描述/前缀过滤…"),
           '<div class="tablewrap" id="osap-list"><table><thead><tr><th class="sortable">代号</th>'
           '<th class="sortable">类别</th><th class="sortable">方向</th><th>描述</th>'
           '<th class="sortable num">US t</th><th class="sortable">可行性</th><th class="sortable">新颖度</th>'
           '<th>前缀/数据</th></tr></thead><tbody>']
    for o in osap:
        out.append(f'<tr data-row data-status="{esc(o["feasibility"])}" data-f="{esc(o["acronym"])} {esc(o["desc"])} {esc(o["prefix"])} {esc(o["novelty"])}">'
                   f'<td class="mono">{esc(o["acronym"])}</td><td class="muted">{esc(o["cat"])}</td><td>{esc(o["sign"])}</td>'
                   f'<td>{esc(o["desc"])}<div class="muted" style="font-size:11px">{esc(o["detailed"])}</div></td>'
                   f'<td class="num">{esc(o["tstat"])}</td><td>{pill(o["feasibility"])}</td><td>{pill(o["novelty"])}</td>'
                   f'<td class="muted"><span class="mono">{esc(o["prefix"])}</span> · {esc(o["data_need"])}</td></tr>')
    out.append("</tbody></table></div>")
    return "".join(out)


def _knowledge(ctx: dict) -> str:
    k = ctx["knowledge"]
    fw = k.get("framework", {}) or {}; corp = fw.get("corpus", {}) or {}
    sources = k.get("sources", []) or []
    dims = fw.get("dims", []); dirs = k.get("directions", []); ranked = k.get("ranked_papers", [])
    osap = k.get("osap", []); ft = k.get("osap_tally", {}).get("feasibility", {})
    active = [s for s in sources if s.get("status") == "active"]
    n_active = len(active)
    out = ['<section class="layer hide" id="knowledge"><h2>📚 知识层 '
           f'<span class="cnt">{n_active} 活跃源 · {corp.get("papers",0)} arXiv 论文 · '
           f'{corp.get("directions",0)} 方向 · OSAP {len(osap)} · 记忆 {len(k.get("memory",[]))}</span></h2>']
    if k.get("error"):
        out.append(f'<div class="warn">数据源异常: {esc(k["error"])}</div>')
    # level-1 nav = the knowledge-source directory: 总览 + one tab per active source
    out.append('<div class="subnav"><button class="active" data-sv="overview">🧭 总览</button>')
    for s in active:
        out.append(f'<button data-sv="src_{esc(s["id"])}">{esc(_SRC_TAB.get(s["id"], s["id"]))}</button>')
    out.append('</div>')

    # ── overview: the source directory + kb/memory ──
    out.append('<div class="subview active" data-sv="overview">')
    out.append(_lead([
        ("知识源", f'{n_active}/{len(sources)}', "活跃 / 总数"),
        ("arXiv 语料", corp.get("papers", 0), "主题相关性收割"),
        ("价值排序", corp.get("ranked", 0), "过相关闸"),
        ("引用富集", corp.get("enriched", 0), "OpenAlex"),
        ("研究方向", corp.get("directions", 0), "全生命周期"),
    ]))
    out.append('<div class="note">知识层按<b>数据源</b>分层组织：<b>知识源</b>是上层目录——点上方任一源进入，'
               '每个源下有自己的<b>知识框架 / 研究方向 / 价值内容</b>（依该源提供的内容而定）。'
               '源 = 外部文献（arXiv / OSAP / 券商研报 / 期刊 / 新闻）或内部数据集成（report_rc 及后续数据集）。'
               '价值定义：<b>P(线索 → 一个新的、正交的、可部署的 A 股因子)</b>；线索是<b>假设源、永不为证据</b>。'
               f'{doclink("workspace/research/idea_sourcing/knowledge/sources.yaml", "源注册表(yaml)")}</div>')
    out.append('<div class="sub">数据源目录 · 点上方对应标签进入该源（新增源 = sources.yaml 加一条 + 打 source 标签）</div>')
    out.append('<div class="filterbar" data-scope="#src-list" data-status="all">'
               '<span class="lbl">状态</span>'
               '<span class="fb active" data-status="all">全部</span>'
               f'<span class="fb" data-status="active">活跃 {n_active}</span>'
               f'<span class="fb" data-status="planned">计划接入 {len(sources)-n_active}</span>'
               '<input class="ft" placeholder="🔍 按源名/简介过滤…"></div>')
    out.append('<div class="grid" id="src-list">')
    for s in sources:
        out.append(_source_card(s))
    out.append('</div>')
    out.append('<div class="sub">知识库与记忆（保留）</div><div class="grid">')
    out.append('<div class="card"><h3>聚宽知识 (strategy_kb)</h3><ul class="items">')
    for c in k.get("strategy_kb", []):
        out.append(f'<li data-f="{esc(c["title"])}">{doclink(c["path"], c["title"])}</li>')
    out.append('</ul></div><div class="card"><h3>聚宽回测明细数据</h3><ul class="items">')
    for j in k.get("joinquant_data", []):
        out.append(f'<li data-f="{esc(j["name"])}"><a href="{esc(link(j["path"]))}" class="mono">{esc(j["name"])}</a><span class="muted">{esc(j["rows"])} 行</span></li>')
    out.append('</ul></div><div class="card"><h3>核心文档 + 诊断计划</h3><ul class="items">')
    for doc in k.get("docs", []):
        out.append(f'<li data-f="{esc(doc["title"])}">{doclink(doc["path"], doc["title"])}</li>')
    for t in k.get("temp_plan", []):
        out.append(f'<li data-f="{esc(t["title"])}">{doclink(t["path"], t["title"])}</li>')
    out.append('</ul></div><div class="card"><h3>持久记忆 (memory)</h3><ul class="items">')
    for m in k.get("memory", []):
        out.append(f'<li data-f="{esc(m["title"])} {esc(m["hook"])}"><span><b>{esc(m["title"])}</b> <span class="muted">— {esc(m["hook"])}</span></span></li>')
    out.append("</ul></div></div>")
    out.append('</div>')  # end overview

    # ── per active source: level-2 sections (知识框架 / 研究方向 / 价值内容) ──
    for s in active:
        sid = s["id"]
        sects = _source_sections(s)
        multi = len(sects) > 1
        out.append(f'<div class="subview" data-sv="src_{esc(sid)}">')
        if multi:
            out.append('<div class="subnav2">')
            for i, (sk, sl) in enumerate(sects):
                out.append(f'<button class="{"active" if i == 0 else ""}" data-sv2="{esc(sid)}_{sk}">{esc(sl)}</button>')
            out.append('</div>')
        for i, (sk, sl) in enumerate(sects):
            if multi:
                out.append(f'<div class="subview2{" active" if i == 0 else ""}" data-sv2="{esc(sid)}_{sk}">')
            if sk == "framework":
                out.append(_kn_framework(corp, dims))
            elif sk == "directions":
                src_dirs = [d for d in dirs if (d.get("source_kind") or "arxiv") == sid]
                out.append(_kn_directions(src_dirs, f"dir-{esc(sid)}"))
            elif sk == "content":
                if sid == "arxiv":
                    out.append(_kn_papers(ranked, "ranked-arxiv", corp))
                elif sid == "osap":
                    out.append(_kn_osap_triage(osap, ft))
                else:
                    out.append('<div class="muted" style="padding:8px">（该源价值内容待接入）</div>')
            if multi:
                out.append('</div>')
        out.append('</div>')  # end source subview

    out.append("</section>")
    return "".join(out)


# --------------------------------------------------------------------------- #
def _data(ctx: dict) -> str:
    d = ctx["data"]; q = d.get("qlib", {}); dsets = d.get("datasets", [])
    statuses = list(d.get("status_tally", {}).keys())
    out = ['<section class="layer hide" id="data"><h2>🗄️ 数据层 '
           f'<span class="cnt">{len(dsets)} 数据集 · {d.get("n_columns",0)} 列 · {q.get("instruments","?")} 标的入 Qlib</span></h2>']
    if d.get("error"):
        out.append(f'<div class="warn">数据源异常: {esc(d["error"])}</div>')
    out.append(_lead([
        ("数据集", len(dsets), _tally_str(d.get("status_tally", {}))),
        ("字段明细", f"{d.get('n_columns',0)} 列", "逐列中英文"),
        ("Qlib 标的", q.get("instruments", "—"), f"日历至 {q.get('calendar_end','?')}"),
        ("Universe", len(q.get("universes", [])), "见 Qlib universe 目录"),
        ("字段治理", _tally_str(d.get("gov_tally", {})), "field_status.yaml"),
    ]))
    # sub-nav (sibling sub-pages)
    out.append('<div class="subnav">'
               '<button class="active" data-sv="sets">全部数据集</button>'
               '<button data-sv="uni">Qlib universe</button>'
               '<button data-sv="appr">字段促进</button></div>')

    # --- subview: all datasets (with filter) ---
    out.append('<div class="subview active" data-sv="sets">')
    out.append('<div class="note">状态：<b>approved</b>=可用于正式研究（入 Qlib provider）· <b>quarantine/pending</b>=受限 · <b>raw</b>=磁盘有数据但未进字段治理。点击数据集展开逐列中英文。</div>')
    out.append(_statusbar("#data-allsets", statuses, "按数据集名/中文名/列名过滤…"))
    out.append('<div id="data-allsets">')
    for ds in dsets:
        cols = ds.get("columns", [])
        qbadge = pill("入Qlib", "green") if ds.get("in_qlib") else ""
        coltext = " ".join(c["col"] for c in cols)
        out.append(f'<div class="exp" data-row data-status="{esc(ds["status"])}" data-cat="{esc(ds["category"])}" '
                   f'data-f="{esc(ds["id"])} {esc(ds["cn_name"])} {esc(ds["category"])} {esc(coltext)}">'
                   f'<div class="eh"><span class="arrow">▶</span>{pill(ds["status"])}<b class="mono">{esc(ds["id"])}</b>'
                   f'<span>{esc(ds["cn_name"])}</span><span class="sm">· {esc(ds["category"])} · {len(cols)} 列</span>{qbadge}</div>'
                   '<div class="eb"><table><thead><tr><th>Column</th><th>English</th><th>中文</th></tr></thead><tbody>')
        for c in cols:
            out.append(f'<tr><td class="mono">{esc(c["col"])}</td><td>{esc(c["en"])}</td><td>{esc(c["cn"])}</td></tr>')
        out.append("</tbody></table></div></div>")
    out.append("</div>")  # data-allsets
    out.append("</div>")  # subview: sets (close before siblings — else uni/appr nest inside it)

    # --- subview: Qlib universe (sibling page) ---
    out.append('<div class="subview" data-sv="uni">')
    out.append(_lead([
        ("已注册标的", q.get("instruments", "—"), "data/qlib_data/features"),
        ("universe 数", len(q.get("universes", [])), "instruments/*.txt"),
        ("交易日历", q.get("calendar_end", "?"), "calendars/day.txt"),
    ]))
    out.append('<div class="tablewrap"><table><thead><tr><th>universe</th><th class="num">标的数</th><th>说明</th></tr></thead><tbody>')
    uni_desc = {"all": "全市场（含停牌在册）", "all_stocks": "PIT 边界后可交易全集（含退市/IPO 滞后约束）",
                "csi300": "沪深300", "csi500": "中证500", "csi1000": "中证1000", "st_stocks": "ST 标的（区间形式）"}
    for u in q.get("universes", []):
        out.append(f'<tr data-f="{esc(u["name"])}"><td class="mono">{esc(u["name"])}</td><td class="num">{esc(u["lines"])}</td>'
                   f'<td class="muted">{esc(uni_desc.get(u["name"], ""))}</td></tr>')
    out.append("</tbody></table></div>")
    out.append('<div class="note" style="margin-top:10px">universe 以布尔成员掩码使用（Layer-2），不在因子计算前裁剪宇宙；ST/退市判定见 CLAUDE.md §3.1。</div>')
    out.append("</div>")  # uni

    # --- subview: approvals ---
    out.append('<div class="subview" data-sv="appr"><div class="card"><h3>最近字段促进 (approval log)</h3><ul class="items">')
    for ev in d.get("recent_approvals", []):
        out.append(f'<li data-f="{esc(ev["dataset"])}"><span class="d muted mono">{esc(ev["date"])}</span>'
                   f'<span>{esc(ev["dataset"])} <span class="muted">{esc(ev["transition"])}</span></span></li>')
    out.append("</ul></div></div>")
    out.append("</section>")
    return "".join(out)


# --------------------------------------------------------------------------- #
def _factors(ctx: dict) -> str:
    f = ctx["factors"]; cur = f.get("current_tally", {}); cat = f.get("catalog", {}); facs = f.get("factors", [])
    out = ['<section class="layer hide" id="factors"><h2>🧮 因子层 '
           f'<span class="cnt">登记 {f.get("total_rows",0)} · 当前 {len(facs)} · catalog {cat.get("total","?")}</span></h2>']
    if f.get("error"):
        out.append(f'<div class="warn">数据源异常: {esc(f["error"])}</div>')
    out.append(_lead([
        ("approved", cur.get("approved", 0), "通过 sealed-OOS"),
        ("candidate", cur.get("candidate", 0), "过 IS-only 闸"),
        ("draft", cur.get("draft", 0), "写入即可发现"),
        ("catalog", cat.get("total", "?"), f"base {cat.get('base','?')}·comp {cat.get('composite','?')}·ind {cat.get('industry_relative','?')}"),
        ("candidate_reg", f.get("candidates", 0), "研究候选"),
    ]))
    out.append('<div class="note">中英文描述由 <b>Claude Sonnet</b> 依每个因子的表达式/类别生成（不含业绩声明）。<b>点击任一行</b>展开该因子的明细卡。</div>')
    cats = sorted(f.get("category_dist", {}).keys())
    out.append(_statusbar("#factor-list", ["approved", "candidate", "draft"], "按 id/中英文描述过滤…", cats=cats))
    out.append('<div class="tablewrap" id="factor-list"><table><thead><tr><th></th>'
               '<th class="sortable">factor_id</th><th class="sortable">类别</th><th class="sortable">kind</th>'
               '<th class="sortable">状态</th><th class="sortable">评级</th>'
               '<th class="sortable num">5d RankICIR</th><th class="sortable num">验证/折</th></tr></thead><tbody>')
    for x in facs:
        # main clickable row
        out.append(f'<tr class="frow" data-row data-status="{esc(x["status"])}" data-cat="{esc(x["category"])}" '
                   f'data-f="{esc(x["id"])} {esc(x["en"])} {esc(x["cn"])} {esc(x["category"])} {esc(x["status"])}">'
                   f'<td><span class="arrow">▶</span></td><td class="mono">{esc(x["id"])}</td><td class="muted">{esc(x["category"])}</td>'
                   f'<td>{esc(x["kind"])}</td><td>{pill(x["status"])}</td><td>{_fmt(x["grade"])}</td>'
                   f'<td class="num">{_fmt(x["rank_icir_5d"])}</td><td class="num">{_fmt(x["val_pass"])}/{_fmt(x["folds"])}</td></tr>')
        # detail row (hidden until click)
        ev = []
        if x["grade"]:
            ev.append(f'<span class="chip">评级 <b>{esc(x["grade"])}</b></span>')
        if x["rank_icir_5d"] is not None:
            ev.append(f'<span class="chip">IS RankICIR <b>{esc(x["rank_icir_5d"])}</b></span>')
        if x["ls_ann"] is not None:
            ev.append(f'<span class="chip">LS年化 <b>{esc(x["ls_ann"])}</b></span>')
        if x["monotonic"]:
            ev.append(f'<span class="chip">单调 {esc(x["monotonic"])}</span>')
        if x["best_decay"]:
            ev.append(f'<span class="chip">衰减 {esc(x["best_decay"])}</span>')
        comp = ""
        if x.get("components"):
            cc = x["components"] if isinstance(x["components"], list) else []
            comp = f'<div class="kv"><b>成分</b> <span class="mono">{esc(", ".join(map(str, cc))[:240])}</span></div>'
        rec = (" " + pill(x["recommended"], "blue")) if x["recommended"] and x["recommended"] != x["status"] else ""
        out.append('<tr class="fdetail"><td colspan="8"><div class="fdcard">'
                   f'<div class="ft">{pill(x["status"])}{rec} <b class="mono">{esc(x["id"])}</b> <span class="muted">{esc(x["category_bi"])}</span></div>'
                   f'<div class="en">{esc(x["en"])}</div><div class="cn">{esc(x["cn"])}</div>'
                   f'<div class="kv">{esc(x["kind"])}'
                   + (f' · 方向 {esc(x["direction"])}' if x["direction"] else "")
                   + (f' · {esc(x["validity"])}' if x["validity"] else "")
                   + (f' · 绑定 {esc(x["binding"])}' if x["binding"] else "")
                   + (f' · 更新 {esc(x["updated"])}' if x["updated"] else "") + "</div>"
                   f'<div class="fx mono">{esc(x["expr"])}</div>' + comp
                   + (f'<div class="ev chips">{"".join(ev)}</div>' if ev else "")
                   + (f'<div class="kv muted">{esc(x["notes"])}</div>' if x["notes"] else "")
                   + "</div></td></tr>")
    out.append("</tbody></table></div></section>")
    return "".join(out)


# --------------------------------------------------------------------------- #
def _gov_table(title: str, headers: list, rows: list, rowfn) -> str:
    out = [f'<div class="sub">{title}</div><div class="tablewrap"><table><thead><tr>']
    for h in headers:
        out.append(f'<th class="sortable">{esc(h)}</th>')
    out.append("</tr></thead><tbody>")
    for x in rows:
        out.append(rowfn(x))
    if not rows:
        out.append(f'<tr><td colspan="{len(headers)}" class="muted">（无）</td></tr>')
    out.append("</tbody></table></div>")
    return "".join(out)


def _fmtm(v, fmt: str) -> str:
    if v is None or v == "":
        return '<span class="muted">–</span>'
    try:
        f = float(v)
    except Exception:
        return esc(str(v))
    if fmt == "pct":
        return f"{f * 100:.1f}%"
    if fmt == "pctmdd":
        return f'<span class="hfail">{f * 100:.1f}%</span>' if f > 0.35 else f"{f * 100:.1f}%"
    if fmt == "x":
        return f"{f:.1f}×"
    if fmt == "int":
        return f"{int(f)}"
    return f"{f:.2f}"


_MROWS = [("年化 CAGR", "cagr", "pct"), ("Sharpe", "sharpe", "r2"), ("最大回撤", "mdd", "pctmdd"),
          ("信息比率 IR", "ir", "r2"), ("Beta", "beta", "r2"), ("年化换手", "turnover", "x"),
          ("胜率", "win_rate", "pct"), ("同期基准", "benchmark", "pct"), ("交易天数", "days", "int")]


def _metrics_panel(x: dict) -> str:
    """Real backtest performance, IS vs OOS side-by-side — the contrast that exposes a regime artifact."""
    is_m, oos_m = x.get("is_metrics") or {}, x.get("oos_metrics") or {}
    if not is_m and not oos_m:
        return ""
    out = ['<div class="hsec">📊 实测表现（IS 全样本 ╱ OOS 封存窗 · 同口径）</div>']
    if x.get("regime_warn"):
        out.append(f'<div class="rwarn">⚠ 制度警示：{esc(x["regime_warn"])}</div>')
    out.append('<table class="mtab"><thead><tr><th>指标</th><th>IS 全样本</th><th>OOS 封存窗</th></tr></thead><tbody>')
    for label, field, fmt in _MROWS:
        iv, ov = is_m.get(field), oos_m.get(field)
        if iv is None and ov is None:
            continue
        out.append(f'<tr><td class="ml">{esc(label)}</td><td>{_fmtm(iv, fmt)}</td><td>{_fmtm(ov, fmt)}</td></tr>')
    out.append("</tbody></table>")
    return "".join(out)


def _story_card(x: dict) -> str:
    """One hypothesis as a storyline: 测什么 → 实测表现(IS vs OOS) → 每步证实了什么 → 结论."""
    thesis = x.get("thesis") or "（无 thesis）"
    head_thesis = thesis if len(thesis) <= 88 else thesis[:88] + "…"
    rwarn = bool(x.get("regime_warn"))
    fkey = f'{x["id"]} {thesis} {x["status"]} {" ".join(x.get("factors",[]))} {x.get("profile","")}{" 制度依赖 regime" if rwarn else ""}'
    rbadge = '<span class="rbadge">⚠制度依赖</span>' if rwarn else ''
    out = [f'<div class="exp hcard" data-row data-status="{esc(x["status"])}" data-f="{esc(fkey)}"><div class="eh">'
           f'<span class="arrow">▶</span>{pill(x["status"])}{rbadge}<b class="mono">{esc(x["id"])}</b>'
           f'<span class="hsum">{esc(head_thesis)} <span class="muted">→ {esc(x["summary"])}</span></span>'
           f'</div><div class="eb">']
    # 🎯 测试什么
    out.append('<div class="hsec">🎯 测试什么</div>')
    out.append(f'<div class="htx">{esc(thesis)}</div>')
    if x.get("mechanism"):
        out.append(f'<div class="kv"><b>机制</b><span>{esc(x["mechanism"])}</span></div>')
    if x.get("expected"):
        out.append(f'<div class="kv"><b>预期效应</b><span class="mono">{esc(x["expected"])}</span></div>')
    if x.get("bar"):
        out.append(f'<div class="kv"><b>成功标准（预先承诺的闸）</b><span class="mono">{esc(x["bar"])}</span></div>')
    if x.get("factors"):
        out.append(f'<div class="kv"><b>因子</b><span class="mono">{esc(", ".join(x["factors"]))}</span></div>')
    meta = " · ".join(m for m in [x.get("universe"), x.get("benchmark"), x.get("rebalance"), x.get("profile")] if m)
    if meta:
        out.append(f'<div class="kv muted">{esc(meta)}</div>')
    # 📊 实测表现（IS vs OOS）
    out.append(_metrics_panel(x))
    # 🪜 每一步证实了什么
    steps = x.get("steps", [])
    if steps:
        out.append('<div class="hsec">🪜 每一步证实了什么</div><div class="tl">')
        for s in steps:
            out.append('<div class="tli"><div class="tlh">'
                       f'<span class="d">{esc(s["date"])}</span><b>{esc(s["stage"])}</b>{pill(s["decision"])}</div>')
            crit = s.get("criteria", [])
            if crit:
                npass = sum(1 for c in crit if c["passed"] is True)
                nhard = sum(1 for c in crit if c["passed"] is False and c.get("hard"))
                nna = sum(1 for c in crit if c["passed"] is None)
                lbl = f'{npass}/{len(crit)} 通过'
                hf = f'<span class="hfail"> · {nhard} 硬性未过</span>' if nhard else ''
                na = f'<span class="muted"> · {nna} 未计算</span>' if nna else ''
                out.append(f'<div class="crit"><span class="muted" style="font-size:10.5px">{lbl}{hf}{na}：</span>')
                for c in crit:
                    p = c["passed"]
                    if p is True:
                        cls, mark = "ok", "✓"
                    elif p is None:
                        cls, mark = "na", "–"
                    elif c.get("hard"):
                        cls, mark = "bad", "✗"
                    else:
                        cls, mark = "soft", "✗"
                    out.append(f'<span class="cpill {cls}">{esc(c["metric"])} {esc(c["actual"])} '
                               f'{esc(c["comp"])} {esc(c["threshold"])} {mark}</span>')
                out.append('</div>')
            if s.get("reason"):
                out.append(f'<div class="trsn">{esc(s["reason"])}</div>')
            out.append('</div>')
        out.append('</div>')
    # 🏁 最终结论
    out.append(f'<div class="hsec">🏁 最终结论 {pill(x["status"])}</div>')
    out.append(f'<div class="trsn">{esc(x.get("conclusion") or "（仅预注册，尚未进入闸评估）")}</div>')
    out.append('</div></div>')
    return "".join(out)


def _governance(ctx: dict) -> str:
    g = ctx.get("governance") or {}
    cnt = g.get("counts", {})
    out = []
    if g.get("error"):
        out.append(f'<div class="warn">治理源异常: {esc(g["error"])}</div>')
    out.append('<div class="note">每个 hypothesis = 一次正式研究（注册时 design_hash 即身份，改措辞不改身份）。'
               '下面每张卡把它讲成一条故事线：<b>测什么 → 每一步用预先承诺的标准证实了什么 → 最终结论</b>。'
               '全部 append-only、机制强制（手改 / 重测已花费的 OOS / 不过闸→抛异常）。点卡片展开。</div>')
    out.append(f'<div class="sub">① 预注册假设故事线（{len(g.get("hypotheses",[]))}）'
               '<span class="muted" style="font-weight:400;margin-left:10px">闸内每条标准：'
               '<span class="cpill ok">✓ 通过</span> <span class="cpill bad">✗ 硬性未过</span> '
               '<span class="cpill soft">✗ 软性未达</span> <span class="cpill na">– 未计算</span> '
               '；<b class="hfail">⚠超N硬闸</b>=带 N 条硬性未过被记录在案地批准（理由见时间线）</span></div>')
    hyps = g.get("hypotheses", [])
    statuses = sorted({x["status"] for x in hyps if x.get("status")})
    fb = ['<div class="filterbar" data-scope="#govcards" data-status="all">',
          '<span class="lbl">状态</span>',
          '<span class="fb active" data-status="all">全部</span>']
    for s in statuses:
        fb.append(f'<span class="fb" data-status="{esc(s)}">{esc(s)}</span>')
    fb.append('<input class="ft" placeholder="搜索 假设id / thesis / 因子 / profile…">')
    fb.append('</div>')
    out.append("".join(fb))
    out.append('<div id="govcards">')
    if not hyps:
        out.append('<div class="muted">（无）</div>')
    for x in hyps:
        out.append(_story_card(x))
    out.append('</div>')
    # ② raw governance records — folded into one collapsed section
    out.append('<div class="exp"><div class="eh"><span class="arrow">▶</span>'
               f'<b>② 原始治理记录（明细表）</b><span class="muted">正式 run {cnt.get("runs",0)} · '
               f'测试裁决 {cnt.get("verdicts",0)} verdict / {cnt.get("measurements",0)} measurement · '
               f'OOS 封存 {cnt.get("seals",0)} · 状态变迁 {cnt.get("status_changes",0)}</span></div>'
               '<div class="eb">')
    out.append(_gov_table(
        f'正式 run（{len(g.get("runs",[]))}，各 registry 的 run_index —— 每次发布对象的正式执行）',
        ["registry", "run_id", "profile/类型", "生成时间", "明细"],
        g.get("runs", []),
        lambda x: (f'<tr data-f="{esc(x["run_id"])} {esc(x["registry"])} {esc(x["profile"])}">'
                   f'<td>{pill(x["registry"], "blue")}</td><td class="mono">{esc(x["run_id"])}</td>'
                   f'<td>{esc(x["profile"])}</td><td class="muted">{esc(x["generated_at"])}</td>'
                   f'<td class="muted">{esc(x["detail"])}</td></tr>')))
    out.append(_gov_table(
        f'测试裁决（testing_ledger · {len(g.get("verdicts",[]))} verdict / {cnt.get("measurements",0)} measurement —— 多重检验记账）',
        ["时间", "假设", "阶段", "裁决", "统计", "理由"],
        g.get("verdicts", []),
        lambda x: (f'<tr data-f="{esc(x["hypothesis_id"])} {esc(x["verdict"])}"><td class="muted">{esc(x["recorded_at"])}</td>'
                   f'<td class="mono">{esc(x["hypothesis_id"])}</td><td>{esc(x["stage"])}</td><td>{pill(x["verdict"])}</td>'
                   f'<td class="muted">{esc(x["stat"])}{(" · Sharpe " + esc(x["sharpe"])) if x["sharpe"] else ""}</td>'
                   f'<td class="muted">{esc(x["reason"])}</td></tr>')))
    out.append(_gov_table(
        f'OOS 封存花费（holdout_seals · {len(g.get("seals",[]))} —— 同一封存集 seal_key 不可重测）',
        ["时间", "假设", "阶段", "seal_key", "design", "profile"],
        g.get("seals", []),
        lambda x: (f'<tr data-f="{esc(x["hypothesis_id"])}"><td class="muted">{esc(x["recorded_at"])}</td>'
                   f'<td class="mono">{esc(x["hypothesis_id"])}</td><td>{pill(x["stage"], "amber")}</td>'
                   f'<td class="mono muted">{esc(x["seal_key"])}</td><td class="mono muted">{esc(x["design"])}</td>'
                   f'<td class="muted">{esc(x["profile"])}</td></tr>')))
    out.append(_gov_table(
        f'状态变迁（status_history · {len(g.get("status_changes",[]))}，近 60）',
        ["时间", "registry", "对象", "变迁", "理由"],
        g.get("status_changes", [])[:60],
        lambda x: (f'<tr data-f="{esc(x["object_id"])} {esc(x["new"])}"><td class="muted">{esc(x["changed_at"])}</td>'
                   f'<td>{esc(x["registry"])}</td><td class="mono">{esc(x["object_id"])}</td>'
                   f'<td>{esc(x["old"])} → {pill(x["new"])}</td><td class="muted">{esc(x["reason"])}</td></tr>')))
    out.append('</div></div>')
    return "".join(out)


def _research(ctx: dict) -> str:
    r = ctx["research"]; threads = r.get("threads", [])
    with_f = [t for t in threads if t["has_findings"]]
    gc = (ctx.get("governance") or {}).get("counts", {})
    out = ['<section class="layer hide" id="research"><h2>🔬 研究层 '
           f'<span class="cnt">{len(threads)} 线程 · {gc.get("hypotheses",0)} 预注册假设 · {gc.get("runs",0)} 正式run</span></h2>']
    if r.get("error"):
        out.append(f'<div class="warn">数据源异常: {esc(r["error"])}</div>')
    out.append(_lead([
        ("研究线程（非正式）", len(threads), f"{len(with_f)} 有 FINDINGS"),
        ("预注册假设", gc.get("hypotheses", 0), "hypothesis_registry"),
        ("正式 run", gc.get("runs", 0), "registry run_index"),
        ("OOS 封存花费", gc.get("seals", 0), "holdout_seals · 不可重测"),
        ("里程碑", len(r.get("milestones", [])), "project_state"),
    ]))
    out.append('<div class="subnav"><button class="active" data-sv="threads">研究线程（非正式探索）</button>'
               '<button data-sv="gov">正式研究治理</button><button data-sv="ms">里程碑</button></div>')

    out.append('<div class="subview active" data-sv="threads">')
    out.append('<div class="note">非正式探索/叙事层（`workspace/research/*`）：还没正式立项的工作台 + 把多个正式 run 串成结论的 FINDINGS。点击展开摘要。</div>')
    out.append('<div class="filterbar" data-scope="#threadlist" data-status="all"><span class="lbl">搜索</span>'
               '<input class="ft" placeholder="线程名 / 描述…"></div>')
    out.append('<div id="threadlist">')
    for t in threads:
        ten, tcn = thread_desc(t["name"])
        badge = pill("FINDINGS", "green") if t["has_findings"] else pill("无", "grey")
        out.append(f'<div class="exp" data-row data-f="{esc(t["name"])} {esc(ten)} {esc(tcn)}">'
                   f'<div class="eh"><span class="arrow">▶</span>{badge}<b class="mono">{esc(t["name"])}</b>'
                   f'<span class="sm">{esc(tcn or ten)}</span></div><div class="eb">')
        if ten:
            out.append(f'<div class="muted" style="font-size:11.5px;margin:4px 0">{esc(ten)}</div>')
        for fd in t["findings"]:
            out.append(f'<div style="margin:7px 0"><b>{doclink(fd["path"], fd["title"])}</b>'
                       f'<div class="muted" style="font-size:12px">{esc(fd["summary"])}</div></div>')
        if not t["findings"]:
            out.append('<div class="muted">（无 FINDINGS 文档）</div>')
        out.append("</div></div>")
    out.append("</div>")
    out.append("</div>")

    out.append('<div class="subview" data-sv="gov">')
    out.append(_governance(ctx))
    out.append("</div>")

    out.append('<div class="subview" data-sv="ms"><div class="sub">里程碑时间线 (project_state.md Update Notes)</div>')
    out.append('<div class="filterbar" data-scope="#mslist" data-status="all"><span class="lbl">搜索</span>'
               '<input class="ft" placeholder="里程碑标题 / 日期…"></div>')
    out.append('<div class="timeline" id="mslist">')
    for m in r.get("milestones", []):
        out.append(f'<div class="tl-item" data-row data-f="{esc(m["title"])} {esc(m["date"])}"><span class="d">{esc(m["date"])}</span>{esc(m["title"])}</div>')
    out.append("</div></div></section>")
    return "".join(out)


# --------------------------------------------------------------------------- #
def _strategy(ctx: dict) -> str:
    s = ctx["strategy"]; reg = s.get("registry", {}); sigs = s.get("signal_rows", [])
    out = ['<section class="layer hide" id="strategy"><h2>📈 策略层 '
           f'<span class="cnt">策略 {reg.get("strategies",0)} · 信号 {s.get("signals",0)} · 模型 {s.get("models",0)}</span></h2>']
    if s.get("error"):
        out.append(f'<div class="warn">数据源异常: {esc(s["error"])}</div>')
    out.append(_lead([
        ("strategy_registry", reg.get("strategies", 0), "正式策略"),
        ("signal_registry", s.get("signals", 0), "信号配方"),
        ("model_registry", s.get("models", 0), "训练模型"),
        ("可部署书 (策展)", len(s.get("deployable", [])), "活在 FINDINGS"),
    ]))
    if reg.get("strategies", 0) == 0:
        out.append('<div class="warn">strategy_registry 为空——已验证可部署策略目前存在于 FINDINGS / project_state，下方为 board.yaml 人工策展。</div>')
    out.append('<div class="sub">可部署策略（board.yaml 策展 + Sonnet 双语）</div><div class="grid">')
    for st in s.get("deployable", []):
        if not isinstance(st, dict):
            continue
        name = st.get("name", "?"); en, cn = strategy_desc(name)
        out.append(f'<div class="card" data-f="{esc(name)} {esc(en)} {esc(st.get("note",""))}">'
                   f'<h3>{esc(name)} <span class="pill green">{esc(st.get("metrics",""))}</span></h3>'
                   + (f'<div style="font-size:12.5px;margin-bottom:5px">{esc(en)}</div>' if en else "")
                   + f'<div class="muted" style="font-size:12px">{esc(cn or st.get("note",""))}</div></div>')
    out.append("</div>")
    if sigs:
        out.append(f'<div class="sub">signal_registry 配方（前 {len(sigs)}，共 {s.get("signals",0)}）</div>')
        out.append(_statusbar("#sig-list", [], "按 object/profile 过滤…"))
        out.append('<div class="tablewrap" id="sig-list"><table><thead><tr><th class="sortable">object</th>'
                   '<th class="sortable">类型</th><th class="sortable">profile</th><th class="sortable">状态</th><th>摘要</th></tr></thead><tbody>')
        for r in sigs:
            out.append(f'<tr data-row data-status="{esc(r["status"])}" data-f="{esc(r["name"])} {esc(r["profile"])}">'
                       f'<td class="mono">{esc(r["name"])}</td><td class="muted">{esc(r["type"])}</td><td>{esc(r["profile"])}</td>'
                       f'<td>{pill(r["status"])}</td><td class="muted">{esc(r["metric"])}</td></tr>')
        out.append("</tbody></table></div>")
    out.append("</section>")
    return "".join(out)


# --------------------------------------------------------------------------- #
def _session_title(s: dict) -> str:
    """Concise title derived from the first prompt (the session's task)."""
    t = (s.get("first_prompt") or "").strip()
    if not t:
        return "(无文本指令)"
    for stop in ("。", ".", "\n", "；", ";", "，"):
        i = t.find(stop)
        if 12 <= i <= 80:
            return t[:i].strip()
    return t[:80].strip()


def _sessions(ctx: dict) -> str:
    sr = ctx["sessions"]; sessions = sr.get("sessions", [])
    # dedupe by derived title — many sessions share the same opening prompt
    # (re-runs, auto-continuations) and render identically; keep the most recent
    # (list is end-desc) and fold the rest into a ×N badge.
    groups: dict[str, dict] = {}; order: list[str] = []
    for s in sessions:
        key = _session_title(s)
        if key in groups:
            groups[key]["count"] += 1
        else:
            groups[key] = {"s": s, "count": 1}; order.append(key)
    items = [groups[k] for k in order]
    out = ['<section class="layer hide" id="sessions"><h2>💬 会话采集 '
           f'<span class="cnt">{sr.get("count",0)} 个 transcript · {len(items)} 个会话（同标题已合并）</span></h2>']
    if sr.get("error"):
        out.append(f'<div class="warn">{esc(sr["error"])}</div>')
    for item in items[:40]:
        s = item["s"]; dup = item["count"]
        dur = f'{esc((s.get("start") or "")[:10])} → {esc((s.get("end") or "")[11:16])}' if s.get("start") else ""
        title = _session_title(s)
        tasks = s.get("tasks") or []
        todos = [t for t in (s.get("todos") or []) if isinstance(t, dict)]
        _DONE = {"completed", "done"}; _SKIP = {"cancelled", "canceled"}
        done = ([t["subject"] for t in tasks if t["status"].lower() in _DONE]
                + [t.get("content", "") for t in todos if str(t.get("status", "")).lower() in _DONE])
        active = ([t["subject"] for t in tasks if t["status"].lower() not in (_DONE | _SKIP)]
                  + [t.get("content") or t.get("activeForm", "") for t in todos
                     if str(t.get("status", "")).lower() in ("in_progress", "pending", "")])
        done = [x for x in done if x]; active = [x for x in active if x]
        has_tk = bool(done or active)
        tools = s.get("tools", {})
        toptools = " ".join(f'<span class="chip">{esc(n)}×{esc(c)}</span>' for n, c in sorted(tools.items(), key=lambda x: -x[1])[:6])
        files = s.get("files_edited", []); commits = s.get("commits", [])
        out.append('<div class="sess" data-f="{f}">'.format(f=esc(title + " " + (s.get("branch") or ""))))
        out.append('<div class="h">')
        if s.get("is_command"):
            out.append(pill("cmd", "blue"))
        out.append(f'<span class="ttl">{esc(title)}</span><span class="chip">{esc(s.get("branch") or "?")}</span>')
        if dup > 1:
            out.append(f'<span class="chip">×{dup} 同标题</span>')
        if has_tk:
            out.append(f'<span class="todo-done"><b>✅ {len(done)}</b></span><span class="todo-active"><b>🔵 {len(active)}</b></span>')
        out.append(f'<span class="sm">{dur} · {esc(s.get("n_user",0))}问 {esc(s.get("n_assistant",0))}答 · {len(files)} 文件 · {len(commits)} commit</span></div>')
        out.append('<div class="det">')
        if s.get("summary"):
            out.append(f'<div style="margin-bottom:8px"><b class="muted">末条助手摘要:</b> {esc(s["summary"])}</div>')
        if active:
            out.append('<div style="margin-bottom:6px"><b class="todo-active">🔵 进行中 / 未完成:</b><ul class="items">')
            for t in active[:14]:
                out.append(f'<li><span>{esc(t)}</span></li>')
            out.append("</ul></div>")
        if done:
            out.append('<div style="margin-bottom:6px"><b class="todo-done">✅ 已完成:</b><ul class="items">')
            for t in done[:16]:
                out.append(f'<li><span>{esc(t)}</span></li>')
            out.append("</ul></div>")
        if toptools:
            out.append(f'<div class="chips" style="margin-bottom:6px">{toptools}</div>')
        if files:
            out.append('<div class="sm" style="margin-bottom:5px"><b>改动文件:</b> '
                       + " ".join(f'<span class="mono">{esc(x)}</span>' for x in files[:12])
                       + (f' <span class="muted">+{len(files)-12}</span>' if len(files) > 12 else "") + "</div>")
        if commits:
            out.append('<div class="sm"><b>commits:</b> ' + " ; ".join(f'<span class="muted">{esc(c)}</span>' for c in commits[:8]) + "</div>")
        out.append(f'<div class="sm muted" style="margin-top:6px">session {esc(s["session_id"])} · {esc(s.get("out_tokens",0))} out-tokens · {esc(s.get("lines",0))} 行</div>')
        out.append("</div></div>")
    out.append("</section>")
    return "".join(out)


# --------------------------------------------------------------------------- #
def render_html(ctx: dict) -> str:
    meta = ctx["build"]
    clean = meta.get("git_clean")
    clean_txt = "clean" if clean else ("dirty" if clean is False else "?")
    parts = [
        "<!doctype html><html lang=zh><head><meta charset=utf-8>",
        "<meta name=viewport content='width=device-width,initial-scale=1'>",
        "<title>量化系统 · 中心化看板</title><style>", CSS, "</style></head><body>",
        "<div class=topbar><h1>量化系统 <span class=dot>●</span> 中心化看板</h1>",
        f'<div class="meta"><span>更新 <b>{esc(meta.get("generated"))}</b></span>'
        f'<span>分支 <b>{esc(meta.get("branch"))}</b> ({esc(clean_txt)})</span>'
        f'<span>{esc(meta.get("build_secs"))}s 构建</span></div></div>',
        "<div class=wrap>",
        "<nav class=tabs>",
        "<button data-t=actions class=active>📌 事项</button>",
        "<button data-t=knowledge>📚 知识层</button>",
        "<button data-t=data>🗄️ 数据层</button>",
        "<button data-t=factors>🧮 因子层</button>",
        "<button data-t=research>🔬 研究层</button>",
        "<button data-t=strategy>📈 策略层</button>",
        "<button data-t=sessions>💬 会话</button>",
        "<button data-t=all>全部</button>",
        "<input id=search placeholder='🔍 全局过滤…'>",
        "</nav>",
        _actions(ctx), _knowledge(ctx), _data(ctx), _factors(ctx),
        _research(ctx), _strategy(ctx), _sessions(ctx),
        '<div class="foot">由 src/dashboard/build_dashboard.py 生成 · 只读投影 · 双语描述由 Claude Sonnet 生成 · '
        'md 页内查看需经本地服务打开（src/dashboard/serve_dashboard.bat）· 策展见 workspace/configs/dashboard_board.yaml</div>',
        "</div>",
        '<div id="updbar" onclick="location.reload()">● 看板已更新 — 点击刷新</div>',
        # in-page markdown viewer modal
        '<div class="modal" id="docmodal"><div class="mbox"><div class="mhead"><span class="mt"></span>'
        '<span class="mx">×</span></div><div class="mbody"></div></div></div>',
        f'<script>const BUILD_ID={json.dumps(meta.get("generated"))};</script>',
        "<script>", JS, "</script></body></html>",
    ]
    return "".join(parts)
