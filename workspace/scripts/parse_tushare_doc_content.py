"""Parse the *content* of a saved/fetched Tushare interface page (/document/2?doc_id=N).

The menu tree comes from parse_tushare_doc_tree.py; this extracts the right-hand
content pane of a single interface: title, api_name, 描述/限量/积分, the 输入参数 /
输出参数 field tables, and any 更新时间 / 数据起始 note (the PIT/backfill signal you
want BEFORE fetching). Content is absent from the bare menu page — needs a
logged-in save or a cookie'd fetch.

Reusable API:
    md_str, meta = extract_content(html_text, doc_id)

CLI:
    python parse_tushare_doc_content.py <saved_html> <doc_id> <out_md>
"""
import sys
import re
from pathlib import Path
from bs4 import BeautifulSoup

# A separate insert/announce/effective-date field is the tell that a row's nominal
# date != the date it became visible -> PIT must anchor on the update/ann field.
PIT_FIELD_NAMES = {'create_time', 'update_time', 'update_flag', 'ann_date', 'f_ann_date',
                   'disc_date', 'pub_date', 'crawl_time', 'fetch_time', 'mod_time'}
PIT_FIELD_DESC_KW = ('更新时间', '入库', '插入', '抓取', '爬取', '公告日', '披露日', '发布时间')
CADENCE_KW = ('更新时间', '更新频', '更新', '数据起始', '数据开始', '年开始', '起始时间',
              '开始时间', '历史数据', '盘后', '盘前', '次日', '滞后', '披露', '回溯', '回填')


def text_of(el) -> str:
    return ' '.join(el.get_text(' ', strip=True).split())


def find_content_div(soup):
    for div in soup.find_all('div'):
        cls = div.get('class') or []
        if 'content' in cls and 'col-md-9' in cls:
            return div
    return soup.find('div', class_='content') or soup.body or soup


def table_to_md(tbl) -> tuple:
    """Return (markdown, n_data_rows)."""
    rows = []
    for tr in tbl.find_all('tr'):
        cells = [text_of(c) for c in tr.find_all(['th', 'td'])]
        if cells:
            rows.append(cells)
    if not rows:
        return '', 0
    width = max(len(r) for r in rows)
    rows = [r + [''] * (width - len(r)) for r in rows]
    out = ['| ' + ' | '.join(rows[0]) + ' |',
           '| ' + ' | '.join(['---'] * width) + ' |']
    for r in rows[1:]:
        out.append('| ' + ' | '.join(r) + ' |')
    return '\n'.join(out), max(0, len(rows) - 1)


def extract_content(html_text: str, doc_id):
    """Parse one interface page. Returns (markdown_str, meta_dict)."""
    is_login = bool(re.search(r'login\?next|weborder/#/login', html_text))
    soup = BeautifulSoup(html_text, 'lxml')
    content = find_content_div(soup)

    lines = [f'# (doc_id={doc_id})  https://tushare.pro/document/2?doc_id={doc_id}', '']
    title = ''
    pit_flags, pit_fields = [], []
    n_tables = 0
    out_field_rows = 0
    pending_label = ''

    for el in content.find_all(['h1', 'h2', 'h3', 'h4', 'p', 'li', 'table']):
        if el.name != 'table' and el.find_parent('table'):
            continue
        if el.name == 'table':
            n_tables += 1
            md, nrows = table_to_md(el)
            lines.append(md)
            lines.append('')
            if '输出' in pending_label:
                out_field_rows = nrows
            pending_label = ''
            for tr in el.find_all('tr'):
                cells = [text_of(c) for c in tr.find_all('td')]
                if not cells:
                    continue
                name = cells[0].strip().lower()
                desc = ' '.join(cells[1:])
                if name in PIT_FIELD_NAMES or any(k in desc for k in PIT_FIELD_DESC_KW):
                    pit_fields.append((cells[0], desc))
        elif el.name in ('h1', 'h2', 'h3', 'h4'):
            val = text_of(el)
            if val:
                if not title:
                    title = val
                if '输入参数' in val:
                    pending_label = '输入'
                if '输出参数' in val:
                    pending_label = '输出'
                lines.append(f'## {val}')
        else:
            val = text_of(el)
            if not val:
                continue
            lines.append(val)
            if '输入参数' in val:
                pending_label = '输入'
            if '输出参数' in val:
                pending_label = '输出'
            if any(kw in val for kw in CADENCE_KW):
                pit_flags.append(val)

    api_name = ''
    m = re.search(r'接口[:：]\s*([A-Za-z_][A-Za-z0-9_]*)', html_text)
    if m:
        api_name = m.group(1)

    if pit_flags or pit_fields:
        lines += ['', '## [PIT / 更新口径 — 自动标记]']
        seen = set()
        for s in pit_flags:
            if s not in seen:
                lines.append(f'- (正文) {s}')
                seen.add(s)
        seen_f = set()
        for fname, fdesc in pit_fields:
            key = (fname, fdesc)
            if key in seen_f:
                continue
            seen_f.add(key)
            lines.append(f'- (字段) `{fname}` — {fdesc}  ← 名义日期≠可见日期的信号，PIT 须以此为锚')

    md_str = '\n'.join(lines).rstrip() + '\n'
    meta = {
        'doc_id': str(doc_id),
        'title': title,
        'api_name': api_name,
        'n_tables': n_tables,
        'n_output_fields': out_field_rows,
        'pit_field_names': list(dict.fromkeys(f for f, _ in pit_fields)),
        'has_pit_field': bool(pit_fields),
        'cadence_note': pit_flags[0] if pit_flags else '',
        'is_login_page': is_login,
        'empty': (n_tables == 0 and len(md_str) < 200),
    }
    return md_str, meta


def main():
    src = Path(sys.argv[1])
    doc_id = sys.argv[2]
    out_md = Path(sys.argv[3])
    html_text = src.read_text(encoding='utf-8', errors='replace')
    md, meta = extract_content(html_text, doc_id)
    out_md.write_text(md, encoding='utf-8')
    print(f"doc_id={doc_id} api={meta['api_name']} tables={meta['n_tables']} "
          f"out_fields={meta['n_output_fields']} pit_field={meta['has_pit_field']} -> {out_md.name}")


if __name__ == '__main__':
    main()
