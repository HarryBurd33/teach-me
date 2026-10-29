#!/usr/bin/env python3
"""Plan and explicitly resolve same-base graph draft merges. Python 3.9+, stdlib.

Records are compared as complete values. No semantic inference, source writeback,
identity authentication or field-level conflict resolution is performed.
"""
import argparse
import copy
import json
import sys

import graph_editor as editor
import graph_workbench as workbench
import learning_data as data

FORMAT = 'teach-me-draft-merge-plan-v1'
PLAN_KEYS = {'version', 'format', 'base_sha256', 'left_sha256', 'right_sha256',
             'automatic', 'conflicts', 'notice'}
DECISION_KEYS = {'version', 'plan_sha256', 'choices'}
CHOICE_KEYS = {'kind', 'id', 'choose'}
KINDS = (('node', 'nodes'), ('chain', 'chains'))
MAX_CHOICES = 6 * editor.MAX_RECORDS
NOTICE = ('Whole-record merge choices are operator assertions, not verified truth, '
          'source support, authenticated review or learner mastery. Independent edits '
          'may be combined; conflicting content requires explicit choices. No source '
          'file is overwritten and no field-level or semantic merge is inferred.')


def encoded(value):
    """Match the existing publisher's output bytes for exact size checks."""
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n').encode('utf-8')


def maps(graph):
    return {field: {item['id']: item for item in graph[field]} for _, field in KINDS}


def preserve_metadata(base, branch):
    """Keep imported drafts inside the existing editor's metadata boundary."""
    originals = maps(base)
    for _, field in KINDS:
        metadata = ('aliases', 'createdAt', 'provenance') if field == 'nodes' else ('createdAt', 'provenance')
        for record in branch[field]:
            before = originals[field].get(record['id'])
            if before is not None:
                data.require(all(record[key] == before[key] for key in metadata),
                             'Draft changed retained metadata for ' + field + ' ID ' + record['id'])
            else:
                data.require(record['createdAt'] == '' and record['provenance'] == [] and
                             (field != 'nodes' or record['aliases'] == []),
                             'New records require blank creation time, provenance and aliases')


def read_inputs(base_path, left_path, right_path):
    bp, br, base = editor.read_graph(base_path)
    editor.validate_graph(base)
    branches, sources = [], [(bp, br)]
    for path, label in ((left_path, 'left draft'), (right_path, 'right draft')):
        selected, raw, draft = editor.read_json(path, label)
        workbench.version(draft, editor.DRAFT_KEYS, label)
        data.require(workbench.digest(draft['base_sha256'], label + '.base_sha256') == data.sha(br),
                     label + ': base SHA256 does not match the exact selected base')
        graph = workbench.edited_graph(base, draft['patch'])
        editor.validate_graph(graph)
        preserve_metadata(base, graph)
        branches.append(graph)
        sources.append((selected, raw))
    return base, branches[0], branches[1], sources


def graph_from_records(base, records):
    graph = copy.deepcopy(base)
    for _, field in KINDS:
        graph[field] = [copy.deepcopy(records[field][ident]) for ident in sorted(records[field])
                        if records[field][ident] is not None]
    return graph


def draft_from_graph(base, graph, base_sha256):
    before, after = maps(base), maps(graph)
    patch = {'version': 1, 'delete_nodes': [], 'delete_chains': [],
             'upsert_nodes': [], 'upsert_chains': []}
    for _, field in KINDS:
        for ident in sorted(set(before[field]) | set(after[field])):
            old, new = before[field].get(ident), after[field].get(ident)
            if old == new:
                continue
            if new is None:
                patch['delete_' + field].append(ident)
            else:
                patch['upsert_' + field].append(copy.deepcopy(new))
    return {'version': 1, 'base_sha256': base_sha256, 'patch': patch}


def make_plan(base, left, right, base_sha256, left_sha256, right_sha256):
    """Build a deterministic plan; unresolved records use base only for planning.

    Missing endpoint and capacity checks promote affected automatic changes to
    explicit decisions. They do not repair or silently discard a branch's work.
    Every chosen final combination is independently validated by apply.
    """
    versions = {'base': maps(base), 'left': maps(left), 'right': maps(right)}
    automatic = {'nodes': {}, 'chains': {}}
    conflicts = {}
    preview = {'nodes': {}, 'chains': {}}

    def conflict(kind, field, ident, reason):
        key = (kind, ident)
        if key not in conflicts:
            conflicts[key] = {'kind': kind, 'id': ident, 'reason': reason,
                              **{name: copy.deepcopy(versions[name][field].get(ident))
                                 for name in ('base', 'left', 'right')}}
        automatic[field].pop(ident, None)

    for kind, field in KINDS:
        all_ids = set().union(*(value[field] for value in versions.values()))
        for ident in sorted(all_ids):
            old, a, b = (versions[name][field].get(ident) for name in ('base', 'left', 'right'))
            if a == b:
                result = a
            elif a == old:
                result = b
            elif b == old:
                result = a
            else:
                conflict(kind, field, ident, 'both-edited')
                result = old
            preview[field][ident] = result
            if (kind, ident) not in conflicts and result != old:
                automatic[field][ident] = result

    known = {ident for ident, record in preview['nodes'].items() if record is not None}
    for ident, record in sorted(preview['chains'].items()):
        if record is None:
            continue
        missing = sorted(set(record['premises'] + [record['conclusion']]) - known)
        for endpoint in missing:
            conflict('node', 'nodes', endpoint, 'dependency')
            conflict('chain', 'chains', ident, 'dependency')

    preview_graph = graph_from_records(base, preview)
    too_many = {field for _, field in KINDS if len(preview_graph[field]) > editor.MAX_RECORDS}
    oversized = len(encoded(draft_from_graph(base, preview_graph, base_sha256))) > editor.INPUT_LIMIT
    for kind, field in KINDS:
        if field in too_many or oversized:
            for ident in sorted(list(automatic[field])):
                conflict(kind, field, ident, 'capacity')

    return {'version': 1, 'format': FORMAT, 'base_sha256': base_sha256,
            'left_sha256': left_sha256, 'right_sha256': right_sha256,
            'automatic': {field: [{'id': ident, 'record': copy.deepcopy(record)}
                                  for ident, record in sorted(automatic[field].items())]
                          for _, field in KINDS},
            'conflicts': [conflicts[key] for key in sorted(conflicts)], 'notice': NOTICE}


def loaded_plan(args):
    base, left, right, sources = read_inputs(args.base, args.left, args.right)
    plan = make_plan(base, left, right, *(data.sha(raw) for _, raw in sources))
    data.require(len(encoded(plan)) <= data.LIMIT, 'Merge plan exceeds 8 MiB limit')
    return base, plan, sources


def plan(args):
    _, value, sources = loaded_plan(args)
    result = data.publish(value, args.output, sources)
    result.update(operation='plan', plan_sha256=result['sha256'],
                  conflicts=len(value['conflicts']),
                  automatic_nodes=len(value['automatic']['nodes']),
                  automatic_chains=len(value['automatic']['chains']),
                  semantic_correctness_verified=False, notice=NOTICE)
    return result


def resolved_graph(base, plan, decisions):
    workbench.version(decisions, DECISION_KEYS, 'decisions')
    workbench.digest(decisions['plan_sha256'], 'decisions.plan_sha256')
    choices = workbench.array(decisions['choices'], 'decisions.choices', MAX_CHOICES)
    required = {(item['kind'], item['id']): item for item in plan['conflicts']}
    selected = {}
    for choice in choices:
        workbench.exact(choice, CHOICE_KEYS, 'choice')
        data.require(choice['kind'] in ('node', 'chain'), 'Choice kind must be node or chain')
        workbench.ident(choice['id'], 'choice.id')
        data.require(choice['choose'] in ('left', 'right', 'base'), 'Choice must select left, right or base')
        key = (choice['kind'], choice['id'])
        data.require(key in required, 'Choice is not a required conflict')
        data.require(key not in selected, 'Duplicate conflict choice')
        selected[key] = choice['choose']
    data.require(set(selected) == set(required), 'Every conflict requires exactly one explicit choice')
    records = copy.deepcopy(maps(base))
    for _, field in KINDS:
        for item in plan['automatic'][field]:
            records[field][item['id']] = copy.deepcopy(item['record'])
    for key, side in selected.items():
        kind, ident = key
        records['nodes' if kind == 'node' else 'chains'][ident] = copy.deepcopy(required[key][side])
    graph = graph_from_records(base, records)
    editor.validate_graph(graph)
    preserve_metadata(base, graph)
    return graph


def apply(args):
    data.require(args.approve, 'Explicit --approve acknowledges review; no output was written')
    expected_plan = workbench.digest(args.expected_plan_sha256, 'expected plan SHA256')
    expected_decisions = workbench.digest(args.expected_decisions_sha256, 'expected decisions SHA256')
    base, recomputed, sources = loaded_plan(args)
    pp, pr, supplied = data.source(args.plan)
    dp, dr, decisions = editor.read_json(args.decisions, 'decisions')
    data.require(data.sha(pr) == expected_plan, 'Plan changed since review')
    data.require(data.sha(dr) == expected_decisions, 'Decisions changed since review')
    workbench.version(supplied, PLAN_KEYS, 'plan')
    data.require(supplied == recomputed, 'Plan does not match the current source drafts')
    workbench.version(decisions, DECISION_KEYS, 'decisions')
    data.require(decisions['plan_sha256'] == expected_plan, 'Decisions bind another plan')
    graph = resolved_graph(base, recomputed, decisions)
    draft = draft_from_graph(base, graph, recomputed['base_sha256'])
    workbench.validate_patch(draft['patch'])
    data.require(len(encoded(draft)) <= editor.INPUT_LIMIT, 'Merged draft exceeds 2 MiB limit')
    result = data.publish(draft, args.output, sources + [(pp, pr), (dp, dr)])
    result.update(operation='apply', draft_sha256=result['sha256'], nodes=len(graph['nodes']),
                  chains=len(graph['chains']), conflicts_resolved=len(recomputed['conflicts']),
                  operator_review_acknowledged=True, semantic_correctness_verified=False, notice=NOTICE)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('plan')
    for name in ('base', 'left', 'right', 'output'):
        p.add_argument('--' + name, required=True)
    p = commands.add_parser('apply')
    for name in ('base', 'left', 'right', 'plan', 'expected-plan-sha256', 'decisions',
                 'expected-decisions-sha256', 'output'):
        p.add_argument('--' + name, required=True)
    p.add_argument('--approve', action='store_true')
    args = parser.parse_args(argv)
    try:
        print(json.dumps({'plan': plan, 'apply': apply}[args.command](args), ensure_ascii=False))
        return 0
    except (data.DataError, OSError, UnicodeError, RecursionError, OverflowError, TypeError, KeyError) as exc:
        print('draft_merge: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
