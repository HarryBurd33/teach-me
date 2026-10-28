#!/usr/bin/env python3
"""Source-grounded graph drafts and explicit edits. Python 3.9+, stdlib."""
import argparse
import copy
import datetime as dt
import json
import sys

import learning_data as data

PROPOSAL_KEYS = {'version', 'source_sha256', 'nodes', 'chains'}
PATCH_KEYS = {'version', 'delete_nodes', 'delete_chains', 'upsert_nodes', 'upsert_chains'}
NODE_KEYS = {'id', 'name', 'statement', 'evidence'}
CHAIN_KEYS = {'id', 'premises', 'conclusion', 'evidence'}
WARNING = ('Source-grounded draft/edit: exact spans and structure were checked, not '
           'semantic truth, valid inference, human endorsement or learner mastery.')
MAX_EDITS = 256
MAX_GRAPH = 4096


def exact(value, fields, where):
    data.require(isinstance(value, dict) and set(value) == fields,
                 where + ': keys must be exactly ' + ', '.join(sorted(fields)))


def version(value, fields, where):
    exact(value, fields, where)
    data.require(type(value['version']) is int and value['version'] == 1,
                 where + ': supported version is integer 1')


def digest(value, where):
    data.require(isinstance(value, str) and len(value) == 64 and
                 all(ch in '0123456789abcdef' for ch in value),
                 where + ': expected lowercase SHA256')
    return value


def ident(value, where):
    data.text(value, where)
    data.require(len(value) <= 128 and value == value.strip() and
                 not any(ord(ch) < 32 or ord(ch) == 127 for ch in value),
                 where + ': ID must be bounded text without surrounding whitespace/control characters')
    return value


def array(value, where, maximum=MAX_EDITS):
    data.require(isinstance(value, list) and len(value) <= maximum,
                 where + ': expected a bounded list')
    return value


def id_list(value, where, nonempty=False):
    array(value, where, MAX_GRAPH)
    data.require(not nonempty or value, where + ': at least one ID is required')
    for item in value:
        ident(item, where)
    data.require(len(value) == len(set(value)), where + ': duplicate IDs')
    return value


def span(value, source, where):
    exact(value, {'start', 'end', 'quote'}, where)
    start, end = value['start'], value['end']
    data.require(type(start) is int and type(end) is int and 0 <= start < end <= len(source),
                 where + ': expected valid Unicode character offsets, end exclusive')
    quote = data.text(value['quote'], where + '.quote')
    data.require(source[start:end] == quote, where + ': quote differs from exact source span')
    return value


def validate_proposal(value, source_raw):
    version(value, PROPOSAL_KEYS, 'proposal')
    data.require(digest(value['source_sha256'], 'source_sha256') == data.sha(source_raw),
                 'Proposal source SHA256 is stale or does not match')
    try:
        source = source_raw.decode('utf-8')
    except UnicodeError as exc:
        raise data.DataError('Source must be UTF-8: ' + str(exc))
    node_ids, chain_ids = set(), set()
    for node in array(value['nodes'], 'proposal.nodes'):
        exact(node, NODE_KEYS, 'proposal node')
        nid = ident(node['id'], 'node.id')
        data.require(nid not in node_ids, 'Duplicate proposal node ID')
        node_ids.add(nid)
        data.text(node['name'], 'node.name')
        data.text(node['statement'], 'node.statement')
        span(node['evidence'], source, 'node.evidence')
    for chain in array(value['chains'], 'proposal.chains'):
        exact(chain, CHAIN_KEYS, 'proposal chain')
        cid = ident(chain['id'], 'chain.id')
        data.require(cid not in chain_ids, 'Duplicate proposal chain ID')
        chain_ids.add(cid)
        id_list(chain['premises'], 'chain.premises', nonempty=True)
        ident(chain['conclusion'], 'chain.conclusion')
        span(chain['evidence'], source, 'chain.evidence')
    return value


def unresolved(graph):
    known = {node['id'] for node in graph['nodes']}
    return sorted({endpoint for chain in graph['chains']
                   for endpoint in chain['premises'] + [chain['conclusion']]
                   if endpoint not in known})


def validate_graph(value, complete=True):
    data.validate_document(value)
    data.require(not value['sessions'], 'Workbench accepts graph-only documents; sessions are not discarded')
    node_ids, chain_ids, arguments = set(), set(), set()
    for node in array(value['nodes'], 'graph.nodes', MAX_GRAPH):
        nid = ident(node['id'], 'node.id')
        data.require(nid not in node_ids, 'Duplicate graph node ID')
        node_ids.add(nid)
    for chain in array(value['chains'], 'graph.chains', MAX_GRAPH):
        cid = ident(chain['id'], 'chain.id')
        data.require(cid not in chain_ids, 'Duplicate/ambiguous graph chain ID')
        chain_ids.add(cid)
        id_list(chain['premises'], 'chain.premises', nonempty=True)
        ident(chain['conclusion'], 'chain.conclusion')
        logical = (tuple(sorted(chain['premises'])), chain['conclusion'])
        data.require(logical not in arguments, 'Duplicate logical argument; preserve one explicit identity/provenance record')
        arguments.add(logical)
    if complete:
        missing = unresolved(value)
        data.require(not missing, 'Graph has unresolved endpoints: ' + ', '.join(missing))
    return value


def read_graph(path):
    selected, raw, value = data.source(path)
    validate_graph(value, complete=False)
    return selected, raw, value


def mark_resolved_endpoint_history(graph):
    # Final endpoint validation has passed. Preserve prior warnings as history,
    # rather than describing repaired input gaps as gaps in the new graph.
    graph['warnings'] = ['Input history: ' + warning
                         if warning.startswith('Missing graph endpoint: ') else warning
                         for warning in graph['warnings']]


def load_proposal(source_path, proposal_path):
    selected, source_raw = data.read_bytes(source_path)
    proposal_selected, proposal_raw, value = data.source(proposal_path)
    validate_proposal(value, source_raw)
    return selected, source_raw, proposal_selected, proposal_raw, value


def provenance(source_hash, evidence):
    return [{'chatId': 'src_' + source_hash,
             'messageId': 'chars:' + str(evidence['start']) + ':' + str(evidence['end'])}]


def as_graph(proposal, source_path, source_raw):
    graph = data.envelope([(source_path, source_raw)])
    created = dt.datetime.now(dt.timezone.utc).isoformat()
    for node in proposal['nodes']:
        graph['nodes'].append({'id': node['id'], 'name': node['name'],
                               'statement': node['statement'], 'aliases': [],
                               'createdAt': created,
                               'provenance': provenance(proposal['source_sha256'], node['evidence'])})
    for chain in proposal['chains']:
        graph['chains'].append({'id': chain['id'], 'premises': list(chain['premises']),
                                'conclusion': chain['conclusion'], 'createdAt': created,
                                'provenance': provenance(proposal['source_sha256'], chain['evidence'])})
    graph['warnings'].append(WARNING)
    return graph


def require_review(args, content_hash, field='proposal'):
    data.require(args.approve, 'Explicit --approve acknowledges operator review; no output was written')
    expected = getattr(args, 'expected_' + field + '_sha256')
    data.require(digest(expected, 'expected ' + field + ' SHA256') == content_hash,
                 field.capitalize() + ' changed since review')


def check(args):
    source_path, raw, proposal_path, proposal_raw, proposal = load_proposal(args.source, args.proposal)
    graph = as_graph(proposal, source_path, raw)
    validate_graph(graph, complete=False)
    missing = unresolved(graph)
    return {'version': 1, 'source_spans_valid': True, 'proposal_sha256': data.sha(proposal_raw),
            'source_sha256': data.sha(raw), 'nodes': len(graph['nodes']),
            'chains': len(graph['chains']), 'unresolved_endpoint_ids': missing,
            'ready_without_base': not missing, 'semantic_correctness_verified': False,
            'notice': WARNING}


def apply(args):
    source_path, raw, proposal_path, proposal_raw, proposal = load_proposal(args.source, args.proposal)
    require_review(args, data.sha(proposal_raw))
    added = as_graph(proposal, source_path, raw)
    sources = [(source_path, raw), (proposal_path, proposal_raw)]
    if args.base:
        data.require(args.expected_base_sha256 is not None, '--base requires --expected-base-sha256')
        base_path, base_raw, base = read_graph(args.base)
        data.require(digest(args.expected_base_sha256, 'expected base SHA256') == data.sha(base_raw),
                     'Base changed since review')
        graph = copy.deepcopy(base)
        for field in ('nodes', 'chains'):
            existing = {item['id'] for item in graph[field]}
            data.require(not existing.intersection(item['id'] for item in added[field]),
                         'Proposal would overwrite an existing ' + field + ' ID; use explicit edit')
            graph[field].extend(added[field])
        data.union(graph['source_files'], added['source_files'])
        data.union(graph['warnings'], added['warnings'])
        sources.append((base_path, base_raw))
    else:
        data.require(args.expected_base_sha256 is None, 'Expected base hash supplied without --base')
        graph = added
    validate_graph(graph)
    mark_resolved_endpoint_history(graph)
    result = data.publish(graph, args.output, sources)
    result.update(operation='apply', operator_review_acknowledged=True,
                  semantic_correctness_verified=False, nodes=len(graph['nodes']), chains=len(graph['chains']))
    return result


def validate_patch(value):
    version(value, PATCH_KEYS, 'patch')
    for field in ('delete_nodes', 'delete_chains'):
        array(value[field], field)
        id_list(value[field], field)
    for field in ('upsert_nodes', 'upsert_chains'):
        array(value[field], field)
        # The existing normalized schema validates complete records below.
    graph = data.envelope([])
    graph['nodes'] = value['upsert_nodes']
    graph['chains'] = value['upsert_chains']
    validate_graph(graph, complete=False)
    for field, upsert in (('delete_nodes', 'upsert_nodes'), ('delete_chains', 'upsert_chains')):
        data.require(not set(value[field]).intersection(item['id'] for item in value[upsert]),
                     'Cannot delete and upsert the same ID in one patch')
    return value


def edit(args):
    base_path, base_raw, base = read_graph(args.base)
    patch_path, patch_raw, patch = data.source(args.patch)
    validate_patch(patch)
    require_review(args, data.sha(patch_raw), 'patch')
    data.require(digest(args.expected_base_sha256, 'expected base SHA256') == data.sha(base_raw),
                 'Base changed since review')
    graph = copy.deepcopy(base)
    for field, deleted, upserted in [('nodes', 'delete_nodes', 'upsert_nodes'),
                                    ('chains', 'delete_chains', 'upsert_chains')]:
        current = {item['id']: item for item in graph[field]}
        data.require(set(patch[deleted]) <= set(current), 'Cannot delete unknown ' + field + ' ID')
        for nid in patch[deleted]:
            del current[nid]
        for item in patch[upserted]:
            current[item['id']] = copy.deepcopy(item)
        graph[field] = list(current.values())
    data.union(graph['warnings'], [WARNING, 'Explicit graph edit; any changed claim/provenance is operator supplied.'])
    validate_graph(graph)
    mark_resolved_endpoint_history(graph)
    result = data.publish(graph, args.output, [(base_path, base_raw), (patch_path, patch_raw)])
    result.update(operation='edit', operator_review_acknowledged=True,
                  semantic_correctness_verified=False, nodes=len(graph['nodes']), chains=len(graph['chains']))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('check')
    p.add_argument('--source', required=True)
    p.add_argument('--proposal', required=True)
    p = commands.add_parser('apply')
    p.add_argument('--source', required=True)
    p.add_argument('--proposal', required=True)
    p.add_argument('--expected-proposal-sha256', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--base')
    p.add_argument('--expected-base-sha256')
    p.add_argument('--approve', action='store_true')
    p = commands.add_parser('edit')
    p.add_argument('--base', required=True)
    p.add_argument('--patch', required=True)
    p.add_argument('--expected-base-sha256', required=True)
    p.add_argument('--expected-patch-sha256', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--approve', action='store_true')
    args = parser.parse_args(argv)
    try:
        result = {'check': check, 'apply': apply, 'edit': edit}[args.command](args)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (data.DataError, OSError, UnicodeError, RecursionError, OverflowError) as exc:
        print('graph_workbench: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
