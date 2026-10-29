#!/usr/bin/env python3
"""Offline graph editing drafts with digest-bound checked apply. Python 3.9+."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import sys

import graph_workbench as workbench
import learning_data as data

INPUT_LIMIT = 2 * 1024 * 1024
MAX_RECORDS = 256
HTML_LIMIT = 32 * 1024 * 1024
DRAFT_KEYS = {'version', 'base_sha256', 'patch'}
ASSET_DIR = Path(__file__).resolve().parent.parent / 'assets'
MARKERS = ('EDITOR_DATA', 'EDITOR_SCRIPT', 'EDITOR_STYLE', 'SCRIPT_HASH', 'STYLE_HASH')
WARNING = ('Manual graph edits are operator assertions, not new source provenance. '
           'Review acknowledgment does not authenticate human consent or verify semantic '
           'truth, valid inference, evidence, or learner mastery.')


def read_json(path, label):
    selected = data.path_checked(path)
    data.require(selected.is_file(), label + ': source must be a regular file')
    before = selected.stat()
    data.require(before.st_size <= INPUT_LIMIT, label + ': exceeds 2 MiB limit')
    with selected.open('rb') as handle:
        raw = handle.read(INPUT_LIMIT + 1)
    after = selected.stat()
    data.require(len(raw) <= INPUT_LIMIT, label + ': exceeds 2 MiB limit')
    data.require((before.st_ino, before.st_size, before.st_mtime_ns) ==
                 (after.st_ino, after.st_size, after.st_mtime_ns),
                 label + ': source changed while reading')
    return selected, raw, data.decode(raw, label)


def validate_graph(value, complete=True):
    workbench.validate_graph(value, complete=complete)
    data.require(len(value['nodes']) <= MAX_RECORDS and len(value['chains']) <= MAX_RECORDS,
                 'Editor graph exceeds 256 nodes or chains')
    return value


def read_graph(path):
    selected, raw, graph = read_json(path, 'base graph')
    validate_graph(graph, complete=False)
    return selected, raw, graph


def checked_draft(base_path, draft_path):
    selected, raw, graph = read_graph(base_path)
    draft_selected, draft_raw, draft = read_json(draft_path, 'draft')
    workbench.version(draft, DRAFT_KEYS, 'draft')
    data.require(workbench.digest(draft['base_sha256'], 'draft.base_sha256') == data.sha(raw),
                 'Draft base SHA256 is stale or does not match selected base')
    workbench.validate_patch(draft['patch'])
    edited = workbench.edited_graph(graph, draft['patch'])
    validate_graph(edited)
    # Legacy workbench edits add a source-span notice. This editor has checked
    # no source spans: retain that notice only if it was already input history.
    if workbench.WARNING not in graph['warnings']:
        edited['warnings'].remove(workbench.WARNING)
    data.union(edited['warnings'], [WARNING])
    return selected, raw, draft_selected, draft_raw, edited


def summary(base_raw, draft_raw, graph):
    return {'version': 1, 'base_sha256': data.sha(base_raw),
            'draft_sha256': data.sha(draft_raw), 'nodes': len(graph['nodes']),
            'chains': len(graph['chains']), 'unresolved_endpoint_ids': [],
            'ready_to_apply': True, 'semantic_correctness_verified': False,
            'notice': WARNING}


def check(args):
    _, raw, _, draft_raw, graph = checked_draft(args.base, args.draft)
    return summary(raw, draft_raw, graph)


def apply(args):
    data.require(args.approve, 'Explicit --approve acknowledges operator review; no output was written')
    expected = workbench.digest(args.expected_draft_sha256, 'expected draft SHA256')
    base_path, raw, draft_path, draft_raw, graph = checked_draft(args.base, args.draft)
    data.require(expected == data.sha(draft_raw), 'Draft changed since review')
    result = data.publish(graph, args.output, [(base_path, raw), (draft_path, draft_raw)])
    result.update(summary(raw, draft_raw, graph))
    result.update(operation='apply', operator_review_acknowledged=True)
    return result


def inline_hash(value):
    return base64.b64encode(hashlib.sha256(value.encode('utf-8')).digest()).decode('ascii')


def render_html(graph, base_sha256):
    template = (ASSET_DIR / 'graph-editor.html').read_text(encoding='utf-8')
    script = (ASSET_DIR / 'graph-editor.js').read_text(encoding='utf-8')
    style = (ASSET_DIR / 'graph-editor.css').read_text(encoding='utf-8')
    data.require('</script' not in script.lower() and '</style' not in style.lower(),
                 'Bundled assets contain an unsafe inline closing tag')
    manifest = {'version': 1, 'base_sha256': base_sha256, 'graph': graph}
    payload = json.dumps(manifest, ensure_ascii=True, allow_nan=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    replacements = {'EDITOR_DATA': payload, 'EDITOR_SCRIPT': script, 'EDITOR_STYLE': style,
                    'SCRIPT_HASH': inline_hash(script), 'STYLE_HASH': inline_hash(style)}
    for name in MARKERS:
        data.require(template.count('{{' + name + '}}') == 1,
                     'Bundled editor template must contain exactly one ' + name + ' marker')
    # One pass prevents untrusted data that resembles a marker being substituted.
    import re
    rendered = re.sub(r'\{\{(' + '|'.join(MARKERS) + r')\}\}',
                      lambda match: replacements[match.group(1)], template)
    data.require(len(rendered.encode('utf-8')) <= HTML_LIMIT, 'Editor HTML exceeds 32 MiB limit')
    return rendered


def render(args):
    path, raw, graph = read_graph(args.input)
    missing = workbench.unresolved(graph)
    html = render_html(graph, data.sha(raw))
    result = data.publish(html, args.output, [(path, raw)], as_html=True)
    result.update(operation='render', base_sha256=data.sha(raw), nodes=len(graph['nodes']),
                  chains=len(graph['chains']), unresolved_endpoint_ids=missing,
                  semantic_correctness_verified=False, notice=WARNING)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('render')
    p.add_argument('--input', required=True)
    p.add_argument('--output', required=True)
    p = commands.add_parser('check')
    p.add_argument('--base', required=True)
    p.add_argument('--draft', required=True)
    p = commands.add_parser('apply')
    p.add_argument('--base', required=True)
    p.add_argument('--draft', required=True)
    p.add_argument('--expected-draft-sha256', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--approve', action='store_true')
    args = parser.parse_args(argv)
    try:
        print(json.dumps({'render': render, 'check': check, 'apply': apply}[args.command](args), ensure_ascii=False))
        return 0
    except (data.DataError, OSError, UnicodeError, RecursionError, OverflowError) as exc:
        print('graph_editor: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
