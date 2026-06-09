"""Parse a saved Tushare documentation page (/document/N) into its hierarchical menu tree.

The Tushare doc site renders its left-sidebar menu as an inline jstree (nested
<ul><li><a href="/document/N?doc_id=ID">label</a>). This walks that structure and
emits an indented tree + JSON. Login-gated pages (document/2 数据接口,
document/41 另类数据) must be saved from a logged-in browser first.

Usage:
    python parse_tushare_doc_tree.py <saved_html> <docset_int> <out_basename>
"""
import sys
import re
import html
import json
from pathlib import Path


def parse_tree(html_text: str, docset: int):
    """Return list of (depth, doc_id, label) in document order.

    depth is normalized so top-level categories == 0. Depth is derived from
    <ul> nesting inside the jstree container; the first (container) <ul> is
    treated as the depth-0 frame.
    """
    # Restrict to the jstree menu region if present, to avoid header/footer noise.
    start = html_text.find('id="jstree"')
    region = html_text[start:] if start != -1 else html_text

    token_re = re.compile(
        r'(?P<ulopen><ul\b[^>]*>)'
        r'|(?P<ulclose></ul>)'
        r'|(?P<anchor><a\b[^>]*?href="/document/' + str(docset)
        + r'\?doc_id=(?P<id>\d+)"[^>]*>(?P<label>.*?)</a>)',
        re.S,
    )
    nodes = []
    depth = 0
    for m in token_re.finditer(region):
        if m.group('ulopen'):
            depth += 1
        elif m.group('ulclose'):
            depth = max(0, depth - 1)
        else:
            label = re.sub(r'<[^>]+>', '', m.group('label'))   # strip inner <i> icons etc.
            label = html.unescape(label).strip()
            # container <ul> is depth 1 -> top-level categories sit at depth 1; normalize to 0
            nodes.append((max(0, depth - 1), m.group('id'), label))
    return nodes


def to_nested(nodes):
    """Build a nested dict tree from (depth, id, label) using a depth stack."""
    root = {'label': 'ROOT', 'doc_id': None, 'children': []}
    stack = [(-1, root)]
    for depth, doc_id, label in nodes:
        node = {'label': label, 'doc_id': doc_id, 'children': []}
        while stack and stack[-1][0] >= depth:
            stack.pop()
        parent = stack[-1][1] if stack else root
        parent['children'].append(node)
        stack.append((depth, node))
    return root


def render(node, lines, prefix='', is_last=True, is_root=True):
    if not is_root:
        connector = '└─ ' if is_last else '├─ '
        did = f'[{node["doc_id"]}] ' if node['doc_id'] else ''
        lines.append(f'{prefix}{connector}{did}{node["label"]}')
        prefix += '    ' if is_last else '│   '
    kids = node['children']
    for i, k in enumerate(kids):
        render(k, lines, prefix, i == len(kids) - 1, is_root=False)


def main():
    src = Path(sys.argv[1])
    docset = int(sys.argv[2])
    out_base = sys.argv[3]
    text = src.read_text(encoding='utf-8', errors='replace')

    nodes = parse_tree(text, docset)
    unique_ids = {n[1] for n in nodes}

    tree = to_nested(nodes)
    lines = []
    render(tree, lines)
    tree_txt = '\n'.join(lines)

    out_txt = Path(out_base + '.txt')
    out_json = Path(out_base + '.json')
    out_txt.write_text(tree_txt + '\n', encoding='utf-8')
    out_json.write_text(json.dumps(tree['children'], ensure_ascii=False, indent=2), encoding='utf-8')

    # ASCII-only stdout summary (avoids Windows console codec issues with CJK)
    depth_hist = {}
    for d, _, _ in nodes:
        depth_hist[d] = depth_hist.get(d, 0) + 1
    print(f'parsed_anchors={len(nodes)} unique_doc_ids={len(unique_ids)}')
    print('depth_histogram=' + json.dumps(depth_hist))
    print(f'top_level_count={len(tree["children"])}')
    print(f'wrote {out_txt}')
    print(f'wrote {out_json}')


if __name__ == '__main__':
    main()
