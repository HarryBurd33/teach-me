#!/usr/bin/env python3
"""Read-only structural preflight of reviewed draft merge choices. Python 3.9+."""
import argparse
import json
import sys

# A standalone check must not create import cache files in an installed skill.
sys.dont_write_bytecode = True
import draft_merge as merge

data = merge.data
editor = merge.editor
workbench = merge.workbench
FORMAT = 'teach-me-draft-merge-check-v1'
NOTICE = 'bounded structural check, not authorization or guarantee future apply'


def check(args):
    expected_plan = workbench.digest(args.expected_plan_sha256, 'expected plan SHA256')
    expected_decisions = workbench.digest(args.expected_decisions_sha256, 'expected decisions SHA256')
    base, recomputed, sources = merge.loaded_plan(args)
    pp, pr, supplied = data.source(args.plan)
    dp, dr, decisions = editor.read_json(args.decisions, 'decisions')
    data.require(data.sha(pr) == expected_plan, 'Plan changed since review')
    data.require(data.sha(dr) == expected_decisions, 'Decisions changed since review')
    workbench.version(supplied, merge.PLAN_KEYS, 'plan')
    data.require(supplied == recomputed, 'Plan does not match the current source drafts')
    workbench.version(decisions, merge.DECISION_KEYS, 'decisions')
    data.require(decisions['plan_sha256'] == expected_plan, 'Decisions bind another plan')
    graph = merge.resolved_graph(base, recomputed, decisions)
    draft = merge.draft_from_graph(base, graph, recomputed['base_sha256'])
    workbench.validate_patch(draft['patch'])
    raw = merge.encoded(draft)
    data.require(len(raw) <= editor.INPUT_LIMIT, 'Merged draft exceeds 2 MiB limit')
    changes = {}
    for field in ('delete_nodes', 'delete_chains', 'upsert_nodes', 'upsert_chains'):
        changes[field] = sorted(draft['patch'][field] if field.startswith('delete_')
                                else (item['id'] for item in draft['patch'][field]))
    result = {'version': 1, 'operation': 'check', 'format': FORMAT, 'applicable': True,
              'plan_sha256': expected_plan, 'decisions_sha256': expected_decisions,
              'draft_sha256': data.sha(raw), 'draft_bytes': len(raw),
              'nodes': len(graph['nodes']), 'chains': len(graph['chains']),
              'conflicts_resolved': len(recomputed['conflicts']), 'changes': changes,
              'semantic_correctness_verified': False, 'notice': NOTICE}
    # Recheck all five selected sources through the same bounded, path-safe reader.
    # This is a point-in-time structural report; apply still revalidates independently.
    for path, original in sources + [(pp, pr), (dp, dr)]:
        _, current = data.read_bytes(path)
        data.require(current == original, 'Source changed during analysis')
    return result


class Once(argparse.Action):
    """Reject repeated logical arguments, including --name=value spellings."""
    def __call__(self, parser, namespace, values, option_string=None):
        if getattr(namespace, self.dest, None) is not None:
            parser.error('duplicate argument: ' + option_string)
        setattr(namespace, self.dest, values)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    commands = parser.add_subparsers(dest='command', required=True)
    command = commands.add_parser('check', allow_abbrev=False)
    for name in ('base', 'left', 'right', 'plan', 'expected-plan-sha256',
                 'decisions', 'expected-decisions-sha256'):
        command.add_argument('--' + name, required=True, action=Once)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(check(args), ensure_ascii=False))
        return 0
    except (data.DataError, OSError, UnicodeError, RecursionError, OverflowError,
            TypeError, KeyError) as exc:
        print('draft_merge_check: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
