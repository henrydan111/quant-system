"""Batch-fetch + parse ALL interface docs under https://tushare.pro/document/2.

Reads the parsed menu tree (tushare_doc2_tree.json), then for every doc_id:
  fetch the page (cookie auth) -> save raw HTML -> parse content -> write .md,
and finally writes an INDEX digest + a single concatenated ALL_INTERFACES.md.

Serial + rate-limited + resumable (skips already-saved pages). Polite to the doc
site; this is NOT the Tushare data API (api.tushare.pro), so no fetcher-style
account limit, but we still go one-at-a-time with a small sleep.

Cookie is read from env TUSHARE_DOC_COOKIE (never written to disk / committed).

Usage:
    export TUSHARE_DOC_COOKIE='uid=...; username=...; session-id=...'
    python fetch_all_tushare_doc2.py
"""
import os
import re
import sys
import json
import time
import urllib.request as U
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_tushare_doc_content import extract_content  # noqa: E402

ROOT = Path(r'E:\量化系统')
# Canonical reference folder for the document/2 doc corpus (see Tushare数据接口/README.md).
TREE_JSON = ROOT / 'Tushare数据接口' / '目录树.json'
OUT = ROOT / 'Tushare数据接口'
PAGES = OUT / 'pages'
CONTENT = OUT / 'content'
SLEEP = 0.4
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36'


def safe_name(label: str) -> str:
    s = re.sub(r'[\\/:*?"<>|（）()\[\]\s]+', '_', label or '').strip('_')
    return s or 'node'


def flatten(nodes, trail, out):
    for n in nodes:
        parent = ' / '.join(trail) if trail else '(顶级)'
        out.append((str(n['doc_id']), n['label'], parent))
        if n.get('children'):
            flatten(n['children'], trail + [n['label']], out)


def fetch(doc_id: str, cookie: str) -> str:
    url = f'https://tushare.pro/document/2?doc_id={doc_id}'
    req = U.Request(url, headers={
        'User-Agent': UA,
        'Cookie': cookie,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    })
    with U.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8', errors='replace')


def main():
    cookie = os.environ.get('TUSHARE_DOC_COOKIE', '').strip()
    if not cookie:
        print('FATAL: env TUSHARE_DOC_COOKIE is empty', flush=True)
        sys.exit(2)

    PAGES.mkdir(parents=True, exist_ok=True)
    CONTENT.mkdir(parents=True, exist_ok=True)

    tree = json.loads(TREE_JSON.read_text(encoding='utf-8'))
    items = []
    flatten(tree, [], items)
    # dedupe doc_ids preserving order
    seen, ordered = set(), []
    for d, label, parent in items:
        if d not in seen:
            seen.add(d)
            ordered.append((d, label, parent))
    total = len(ordered)
    print(f'START total_doc_ids={total}', flush=True)

    index_rows = []
    all_chunks = []
    login_streak = 0
    ok = empty = failed = 0

    for i, (doc_id, label, parent) in enumerate(ordered, 1):
        raw_path = PAGES / f'doc_{doc_id}.html'
        md_path = CONTENT / f'{doc_id}_{safe_name(label)}.md'
        try:
            if raw_path.exists() and raw_path.stat().st_size > 1000:
                html_text = raw_path.read_text(encoding='utf-8', errors='replace')
            else:
                try:
                    html_text = fetch(doc_id, cookie)
                except Exception:
                    time.sleep(1.0)
                    html_text = fetch(doc_id, cookie)  # one retry
                raw_path.write_text(html_text, encoding='utf-8')
                time.sleep(SLEEP)

            md, meta = extract_content(html_text, doc_id)

            if meta['is_login_page']:
                login_streak += 1
                failed += 1
                print(f'{i}/{total} doc_id={doc_id} {label} -> LOGIN PAGE (cookie expired?)', flush=True)
                if login_streak >= 3:
                    print('ABORT: 3 consecutive login pages -> cookie invalid/expired', flush=True)
                    break
                continue
            login_streak = 0

            md_path.write_text(md, encoding='utf-8')
            if meta['empty'] or meta['n_tables'] == 0:
                empty += 1
                kind = 'overview/empty'
            else:
                ok += 1
                kind = 'interface'

            index_rows.append({**meta, 'label': label, 'parent': parent, 'kind': kind,
                               'md_file': md_path.name})
            api_disp = meta['api_name'] or '—'
            pit_disp = '是' if meta['has_pit_field'] else '否'
            all_chunks.append(
                f"\n\n---\n\n### [{doc_id}] {label}  ·  {parent}\n"
                f"(api: {api_disp} | 输出字段: {meta['n_output_fields']} | PIT字段: {pit_disp})\n\n{md}"
            )

            flag = '★PIT' if meta['has_pit_field'] else '    '
            print(f"{i}/{total} doc_id={doc_id} {flag} api={api_disp:<18} "
                  f"fields={meta['n_output_fields']:<3} {kind:<14} {label}", flush=True)
        except Exception as e:
            failed += 1
            print(f'{i}/{total} doc_id={doc_id} {label} -> ERROR {type(e).__name__}: {e}', flush=True)
            continue

    # write digest + combined doc
    (OUT / 'index.json').write_text(json.dumps(index_rows, ensure_ascii=False, indent=2), encoding='utf-8')

    idx = ['# Tushare 数据接口 (document/2) — 全量字段/正文索引', '',
           f'共 {len(index_rows)} 个接口已解析 (ok={ok}, overview/empty={empty}, failed={failed}).',
           '★ = 含 create_time/ann_date 等"数据更新时间/公告日"字段 → 名义日期≠可见日期，PIT 须以该字段为锚。', '',
           '| doc_id | 接口名(api) | 名称 | 分类 | 输出字段数 | PIT字段 | 正文文件 |',
           '| --- | --- | --- | --- | --- | --- | --- |']
    for r in index_rows:
        pit = '★ ' + ','.join(r['pit_field_names']) if r['has_pit_field'] else ''
        idx.append(f"| {r['doc_id']} | {r['api_name']} | {r['label']} | {r['parent']} | "
                   f"{r['n_output_fields']} | {pit} | {r['md_file']} |")
    (OUT / 'INDEX.md').write_text('\n'.join(idx) + '\n', encoding='utf-8')

    header = ['# Tushare 数据接口 (document/2) — 全部接口正文合集', '',
              f'抓取自 https://tushare.pro/document/2 ，共 {len(index_rows)} 个接口。', '']
    (OUT / 'ALL_INTERFACES.md').write_text('\n'.join(header) + ''.join(all_chunks) + '\n', encoding='utf-8')

    pit_n = sum(1 for r in index_rows if r['has_pit_field'])
    print(f'DONE parsed={len(index_rows)} ok={ok} empty={empty} failed={failed} pit_field_interfaces={pit_n}', flush=True)
    print(f'wrote {OUT / "INDEX.md"}', flush=True)
    print(f'wrote {OUT / "ALL_INTERFACES.md"}', flush=True)
    print(f'wrote {OUT / "index.json"}', flush=True)


if __name__ == '__main__':
    main()
