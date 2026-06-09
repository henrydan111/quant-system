"""Field-parity audit: local ingested data vs official Tushare interface spec.

For every locally-ingested raw dataset, compare its stored Parquet columns against
the OFFICIAL Tushare output-parameter table (from the offline doc corpus at
Tushare数据接口/), and classify each field:
  - missing_default_Y : official field with 默认显示=Y absent locally  -> HIGH concern
                        (we should have it by default; absence = wrong acquisition)
  - missing_default_N : official field with 默认显示=N absent locally  -> MED (we did not
                        request `fields=`, so default-N fields are silently dropped)
  - extra_local       : local column not in the official spec (renamed / derived / internal)
  - date_anchors      : presence of ann_date/f_ann_date/report_date/create_time/end_date/trade_date

Deterministic + exhaustive (set diff, not eyeballing). Schema is sampled across up to
6 files per dataset to catch schema drift across period/partition files.

Usage: python audit_field_parity_vs_tushare.py
"""
import json
import glob
import re
from pathlib import Path
import pyarrow.parquet as pq

ROOT = Path(r'E:\量化系统')
DATA = ROOT / 'data'
CORPUS = ROOT / 'Tushare数据接口'
CONTENT = CORPUS / 'content'
OUT_MD = ROOT / 'workspace' / 'research' / 'data_audit' / 'FIELD_PARITY_AUDIT.md'
OUT_JSON = ROOT / 'workspace' / 'research' / 'data_audit' / 'field_parity_audit.json'

INTERNAL_COLS = {'_src_file', '_src_ordinal'}
DATE_ANCHORS = ('ann_date', 'f_ann_date', 'report_date', 'create_time', 'end_date',
                'trade_date', 'imp_ann_date', 'pub_date', 'in_date', 'out_date', 'enddate')

# local_dataset -> (raw_glob relative to data/, [doc_ids], note)
DATASETS = [
    ('stock_basic',            'reference/stock_basic.parquet',          [25],          ''),
    ('trade_cal',              'reference/trade_cal.parquet',            [26],          ''),
    ('namechange',             'reference/namechange.parquet',           [100],         ''),
    ('stock_st_daily',         'reference/stock_st_daily.parquet',       [],            'DERIVED from namechange — no direct endpoint'),
    ('daily',                  'market/daily/**/*.parquet',              [27, 28, 32],  'merged: daily + adj_factor + daily_basic'),
    ('index_daily',            'market/index/*.parquet',                 [95],          ''),
    ('moneyflow',              'market/moneyflow/**/*.parquet',          [170],         'pro.moneyflow (个股资金流向)'),
    ('northbound(hk_hold)',    'market/northbound/**/*.parquet',         [188],         'fetch_hk_hold'),
    ('margin(margin_detail)',  'market/margin/**/*.parquet',             [59],          'fetch_margin_detail'),
    ('stk_limit',              'market/stk_limit/**/*.parquet',          [183],         ''),
    ('top_list',               'market/top_list/**/*.parquet',           [106],         ''),
    ('top_inst',               'market/top_inst/**/*.parquet',           [107],         ''),
    ('block_trade',            'market/block_trade/**/*.parquet',        [161],         ''),
    ('cyq_perf',               'market/cyq_perf/**/*.parquet',           [293],         ''),
    ('income',                 'fundamentals/income/*.parquet',          [33],          ''),
    ('income_quarterly',       'fundamentals/income_quarterly/*.parquet',[33],          'report_type 2/3 single-quarter'),
    ('balancesheet',           'fundamentals/balancesheet/*.parquet',    [36],          ''),
    ('cashflow',               'fundamentals/cashflow/*.parquet',        [44],          ''),
    ('cashflow_quarterly',     'fundamentals/cashflow_quarterly/*.parquet',[44],        'report_type 2/3 single-quarter'),
    ('indicators(fina_indicator)','fundamentals/indicators/*.parquet',   [79],          ''),
    ('forecast',               'fundamentals/forecast/*.parquet',        [45],          ''),
    ('express',                'fundamentals/express/*.parquet',         [46],          'Bucket A raw'),
    ('disclosure_date',        'fundamentals/disclosure_date/*.parquet', [162],         'Bucket A raw'),
    ('fina_mainbz',            'fundamentals/fina_mainbz/*.parquet',      [81],          'Bucket A raw'),
    ('fina_audit',             'fundamentals/fina_audit/*.parquet',       [80],          'Bucket A raw'),
    ('dividends',              'corporate/dividends/*.parquet',          [103],         ''),
    ('holder_number',          'corporate/holder_number/*.parquet',      [166],         'stk_holdernumber'),
    ('stk_holdertrade',        'corporate/stk_holdertrade/*.parquet',    [175],         ''),
    ('pledge_stat',            'corporate/pledge_stat/*.parquet',        [110],         'Bucket A raw'),
    ('repurchase',             'corporate/repurchase/*.parquet',         [124],         'Bucket A raw'),
    ('top10_floatholders',     'corporate/top10_floatholders/*.parquet', [62],          'Bucket A raw'),
    ('index_weights',          'universe/index_weights/*.parquet',       [96],          'index_weight'),
    ('industry_sw2021',        'universe/industry_sw2021/*.parquet',     [181],         'index_classify SW2021'),
    ('industry_sw2021_members','universe/industry_sw2021_members/*.parquet',[335],      'index_member_all'),
    ('report_rc',              'analyst/report_rc/*.parquet',            [292],         ''),
]


def sample_files(matched):
    matched = sorted(matched)
    if len(matched) <= 6:
        return matched
    idx = [0, len(matched) // 4, len(matched) // 2, 3 * len(matched) // 4, len(matched) - 1]
    return [matched[i] for i in sorted(set(idx))]


def local_columns(raw_glob):
    matched = glob.glob(str(DATA / raw_glob), recursive=True)
    if not matched:
        return None, None, 0, []
    cols = set()
    coltypes = {}  # name -> arrow type str (or 'mixed:...' across files)
    for f in sample_files(matched):
        try:
            sch = pq.read_schema(f)
        except Exception as e:
            cols.add(f'<schema-error:{type(e).__name__}>')
            continue
        for nm, fld in zip(sch.names, sch):
            cols.add(nm)
            t = str(fld.type)
            if nm in coltypes and coltypes[nm] != t and not coltypes[nm].startswith('mixed'):
                coltypes[nm] = f'mixed:{coltypes[nm]}/{t}'
            elif nm not in coltypes:
                coltypes[nm] = t
    return cols, coltypes, len(matched), sample_files(matched)


def doc_kind(t):
    t = (t or '').lower()
    if any(x in t for x in ('float', 'double', 'decimal', 'number')) or t in ('int', 'integer'):
        return 'num'
    if 'int' in t:
        return 'num'
    if 'date' in t or 'time' in t:
        return 'time'
    if any(x in t for x in ('str', 'char', 'text')):
        return 'str'
    return t or '?'


def arrow_kind(t):
    t = (t or '').lower()
    if any(x in t for x in ('int', 'float', 'double', 'decimal')):
        return 'num'
    if any(x in t for x in ('timestamp', 'date', 'time')):
        return 'time'
    if any(x in t for x in ('string', 'utf8', 'binary')):
        return 'str'
    if 'bool' in t:
        return 'bool'
    return t or '?'


def official_fields(doc_id):
    """Return {field_lower: (orig_name, default_display)} from the 输出参数 table."""
    hits = glob.glob(str(CONTENT / f'{doc_id}_*.md'))
    if not hits:
        return None, None
    md = Path(hits[0]).read_text(encoding='utf-8', errors='replace')
    lines = md.splitlines()
    # locate the 输出参数 marker, then the first markdown table after it
    start = None
    for i, ln in enumerate(lines):
        if '输出参数' in ln:
            start = i
            break
    if start is None:
        return {}, Path(hits[0]).name
    # find first table block (contiguous lines starting with |)
    tbl = []
    seen = False
    for ln in lines[start + 1:]:
        if ln.strip().startswith('|'):
            tbl.append(ln)
            seen = True
        elif seen:
            break
    if len(tbl) < 2:
        return {}, Path(hits[0]).name
    header = [c.strip() for c in tbl[0].strip('|').split('|')]
    # find default-display + type column indices
    dd_idx = next((j for j, h in enumerate(header) if '默认显示' in h), None)
    ty_idx = next((j for j, h in enumerate(header) if '类型' in h), None)
    fields = {}
    for row in tbl[2:]:  # skip header + separator
        cells = [c.strip().strip('`') for c in row.strip('|').split('|')]
        if not cells or not cells[0]:
            continue
        name = cells[0]
        dd = cells[dd_idx] if (dd_idx is not None and dd_idx < len(cells)) else '?'
        ty = cells[ty_idx] if (ty_idx is not None and ty_idx < len(cells)) else '?'
        fields[name.lower()] = (name, dd, ty)
    return fields, Path(hits[0]).name


def main():
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, raw_glob, doc_ids, note in DATASETS:
        local, coltypes, nfiles, _ = local_columns(raw_glob)
        rec = {'dataset': name, 'raw_glob': raw_glob, 'doc_ids': doc_ids, 'note': note,
               'n_files': nfiles}
        if local is None:
            rec['status'] = 'NO_LOCAL_PARQUET'
            rows.append(rec)
            continue
        rec['local_cols'] = sorted(local)
        # official (union across doc_ids)
        official = {}
        doc_files = []
        for d in doc_ids:
            of, fn = official_fields(d)
            if of is None:
                rec.setdefault('missing_doc', []).append(d)
                continue
            doc_files.append(fn)
            for k, v in of.items():
                # prefer Y if any doc marks it Y
                if k not in official or v[1] == 'Y':
                    official[k] = v
        rec['doc_files'] = doc_files
        if not official and not doc_ids:
            rec['status'] = 'DERIVED_NO_ENDPOINT'
            rows.append(rec)
            continue
        local_lower = {c.lower() for c in local}
        missing_Y = sorted(orig for k, (orig, dd, ty) in official.items()
                           if k not in local_lower and dd == 'Y')
        missing_N = sorted(orig for k, (orig, dd, ty) in official.items()
                           if k not in local_lower and dd != 'Y')
        extra = sorted(c for c in local if c.lower() not in official
                       and c not in INTERNAL_COLS)
        # type parity for shared fields: official kind vs local arrow kind
        lc_lower = {c.lower(): c for c in (coltypes or {})}
        type_mismatch = []
        for k, (orig, dd, ty) in official.items():
            if k in lc_lower:
                lt = coltypes[lc_lower[k]]
                dk, ak = doc_kind(ty), arrow_kind(lt)
                if dk != ak and not (dk == 'time' and ak == 'str'):  # date-as-str is our convention
                    sev = 'HIGH' if (dk == 'num' and ak == 'str') else 'note'
                    type_mismatch.append(f'{orig}: doc={ty}({dk}) local={lt}({ak}) [{sev}]')
        anchors_local = sorted(a for a in DATE_ANCHORS if a in local_lower)
        anchors_official = sorted(a for a in DATE_ANCHORS if a in official)
        rec.update({
            'status': 'OK',
            'n_official': len(official),
            'n_local': len(local),
            'missing_default_Y': missing_Y,
            'missing_default_N': missing_N,
            'extra_local': extra,
            'date_anchors_local': anchors_local,
            'date_anchors_official': anchors_official,
            'anchor_gap': sorted(set(anchors_official) - set(anchors_local)),
            'type_mismatch': type_mismatch,
        })
        rows.append(rec)

    OUT_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')

    # markdown report
    L = ['# 本地数据 ↔ Tushare 接口 字段一致性审计', '',
         '逐数据集对比：本地 raw parquet 列 vs 官方输出参数（含 默认显示 Y/N）。',
         '- **missing_default_Y** = 官方默认输出(Y)但本地缺失 → **高风险**（获取方式可能漏字段）',
         '- **missing_default_N** = 官方非默认(N)且本地缺失 → 中（多因未传 `fields=` 只取默认列）',
         '- **extra_local** = 本地有、官方无（改名/派生/内部列）',
         '- **anchor_gap** = 官方有但本地缺的日期锚字段（PIT 关键）', '']
    flagged = []
    for r in rows:
        if r['status'] != 'OK':
            L.append(f"## {r['dataset']}  —  **{r['status']}**  (files={r.get('n_files',0)}, glob `{r['raw_glob']}`)")
            if r.get('local_cols'):
                L.append(f"local cols: {', '.join(r['local_cols'])}")
            L.append('')
            continue
        flag = ''
        hi_type = [m for m in r.get('type_mismatch', []) if '[HIGH]' in m]
        if r['missing_default_Y'] or r['anchor_gap'] or hi_type:
            flag = '  ⚠️ FLAG'
            flagged.append(r['dataset'])
        L.append(f"## {r['dataset']}  (doc {r['doc_ids']}, files={r['n_files']}, "
                 f"official={r['n_official']}, local={r['n_local']}){flag}")
        if r['note']:
            L.append(f"_note: {r['note']}_")
        L.append(f"- **missing_default_Y ({len(r['missing_default_Y'])})**: {', '.join(r['missing_default_Y']) or '—'}")
        L.append(f"- missing_default_N ({len(r['missing_default_N'])}): {', '.join(r['missing_default_N']) or '—'}")
        L.append(f"- extra_local ({len(r['extra_local'])}): {', '.join(r['extra_local']) or '—'}")
        L.append(f"- date anchors: local={r['date_anchors_local']} official={r['date_anchors_official']} "
                 f"**gap={r['anchor_gap'] or '—'}**")
        tm = r.get('type_mismatch', [])
        L.append(f"- type_mismatch ({len(tm)}): {'; '.join(tm) or '—'}")
        L.append('')
    L.insert(7, f'**FLAGGED datasets (missing default-Y or anchor gap): {flagged or "none"}**\n')
    OUT_MD.write_text('\n'.join(L) + '\n', encoding='utf-8')

    # stdout summary (ASCII)
    print(f'datasets={len(rows)} flagged={len(flagged)}')
    for r in rows:
        if r['status'] != 'OK':
            print(f"  {r['dataset']:<26} {r['status']}")
        else:
            tm = r.get('type_mismatch', [])
            hi = sum(1 for m in tm if '[HIGH]' in m)
            print(f"  {r['dataset']:<26} missY={len(r['missing_default_Y'])} "
                  f"missN={len(r['missing_default_N'])} extra={len(r['extra_local'])} "
                  f"anchor_gap={r['anchor_gap']} typemm={len(tm)}(HIGH={hi})")
    print(f'wrote {OUT_MD}')
    print(f'wrote {OUT_JSON}')


if __name__ == '__main__':
    main()
