"""Constructor tests for the bounded, read-only preflight (Python 3.9+)."""
import argparse
import copy
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

sys.dont_write_bytecode = True
SKILL = Path(os.environ.get('TEACH_ME_SKILL', str(Path(__file__).resolve().parents[1] / 'candidate' / 'teach-me'))).resolve()
sys.path.insert(0, str(SKILL / 'scripts'))
check = importlib.import_module('draft_merge_check')
merge = check.merge
data = check.data


def node(ident, statement=None):
    return dict(id=ident, name=ident, statement=statement or ident, aliases=[], createdAt='', provenance=[])


def chain(ident, premises, conclusion):
    return dict(id=ident, premises=premises, conclusion=conclusion, createdAt='', provenance=[])


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.base = data.envelope([])
        self.base['nodes'] = [node('a'), node('b'), node('c')]
        self.base['nodes'][0].update(aliases=['retained alias'], createdAt='old', provenance=[dict(chatId='chat', messageId='m')])
        self.base['chains'] = [chain('and', ['b', 'a'], 'c')]
        self.base['chains'][0].update(createdAt='old', provenance=[dict(chatId='chat', messageId='m')])
        self.left = copy.deepcopy(self.base)
        self.right = copy.deepcopy(self.base)
        self.left['nodes'][0]['statement'] = 'left é'
        self.right['nodes'][0]['statement'] = 'right'
        self.rebuild()

    def write(self, name, value):
        path = self.root / name
        path.write_bytes(merge.encoded(value))
        return path

    def rebuild(self):
        self.bp = self.write('base.json', self.base)
        self.lp = self.write('left.json', merge.draft_from_graph(self.base, self.left, data.sha(self.bp.read_bytes())))
        self.rp = self.write('right.json', merge.draft_from_graph(self.base, self.right, data.sha(self.bp.read_bytes())))
        self.plan = merge.make_plan(self.base, self.left, self.right,
                                   *(data.sha(p.read_bytes()) for p in (self.bp, self.lp, self.rp)))
        self.pp = self.write('plan.json', self.plan)
        self.decisions = dict(version=1, plan_sha256=data.sha(self.pp.read_bytes()),
                              choices=[dict(kind=c['kind'], id=c['id'], choose='left') for c in self.plan['conflicts']])
        self.dp = self.write('decisions.json', self.decisions)
        self.args = argparse.Namespace(base=str(self.bp), left=str(self.lp), right=str(self.rp), plan=str(self.pp),
                                       decisions=str(self.dp), expected_plan_sha256=data.sha(self.pp.read_bytes()),
                                       expected_decisions_sha256=data.sha(self.dp.read_bytes()))

    def refresh_decisions(self):
        self.write('decisions.json', self.decisions)
        self.args.expected_decisions_sha256 = data.sha(self.dp.read_bytes())

    def argv(self):
        result = ['check']
        for key, value in vars(self.args).items():
            result.extend(['--' + key.replace('_', '-'), value])
        return result

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def fail_cli(self, argv=None):
        before = self.snapshot()
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                result = check.main(self.argv() if argv is None else argv)
            except SystemExit as exc:
                result = exc.code
        self.assertEqual(result, 2)
        self.assertEqual(out.getvalue(), '')
        self.assertTrue(err.getvalue())
        self.assertEqual(before, self.snapshot())
        return err.getvalue()

    def test_matches_actual_apply_bytes_metadata_and_premises(self):
        before = self.snapshot()
        result = check.check(self.args)
        self.assertEqual(before, self.snapshot())
        output = self.root / 'merged.json'
        applied = merge.apply(argparse.Namespace(**vars(self.args), approve=True, output=str(output)))
        self.assertEqual(result['draft_sha256'], applied['draft_sha256'])
        self.assertEqual(result['draft_bytes'], len(output.read_bytes()))
        draft = data.decode(output.read_bytes(), 'actual output')
        graph = merge.workbench.edited_graph(self.base, draft['patch'])
        self.assertEqual(graph['nodes'][0]['aliases'], ['retained alias'])
        self.assertEqual(graph['nodes'][0]['createdAt'], 'old')
        self.assertEqual(graph['nodes'][0]['provenance'], self.base['nodes'][0]['provenance'])
        self.assertEqual(graph['chains'][0], self.base['chains'][0])
        self.assertEqual(graph['chains'][0]['premises'], ['b', 'a'])
        self.assertEqual(result['conflicts_resolved'], 1)
        self.assertEqual(result['changes'], dict(delete_nodes=[], delete_chains=[], upsert_nodes=['a'], upsert_chains=[]))
        self.assertEqual((result['nodes'], result['chains']), (3, 1))
        self.assertFalse(result['semantic_correctness_verified'])
        self.assertNotIn(str(self.root), json.dumps(result))
        self.assertEqual(result['notice'], 'bounded structural check, not authorization or guarantee future apply')

    def test_deterministic_report(self):
        self.assertEqual(check.check(self.args), check.check(self.args))

    def test_missing_choices(self):
        self.decisions['choices'] = []
        self.refresh_decisions()
        self.assertIn('Every conflict', self.fail_cli())

    def test_extra_choices(self):
        self.decisions['choices'].append(dict(kind='node', id='b', choose='base'))
        self.refresh_decisions()
        self.assertIn('not a required conflict', self.fail_cli())

    def test_duplicate_choices(self):
        self.decisions['choices'] *= 2
        self.refresh_decisions()
        self.assertIn('Duplicate conflict', self.fail_cli())

    def test_duplicate_logical_arguments_cli(self):
        for key in vars(self.args):
            with self.subTest(argument=key):
                self.assertIn('duplicate argument', self.fail_cli(self.argv() + ['--' + key.replace('_', '-') + '=' + getattr(self.args, key)]))

    def test_required_hashes(self):
        for option in ('--expected-plan-sha256', '--expected-decisions-sha256'):
            argv = self.argv()
            index = argv.index(option)
            del argv[index:index + 2]
            self.fail_cli(argv)

    def test_no_output_approve_abbreviations_or_apply(self):
        for extras in (['--output', str(self.root / 'new')], ['--approve'], ['--expected-plan', '0' * 64]):
            self.fail_cli(self.argv() + extras)
        self.fail_cli(['apply'] + self.argv()[1:])

    def test_raw_plan_and_decisions_hashes(self):
        for selected in (self.pp, self.dp):
            with self.subTest(source=selected.name):
                original = selected.read_bytes()
                selected.write_bytes(original + b' ')
                self.assertIn('changed since review', self.fail_cli())
                selected.write_bytes(original)

    def test_stale_base_and_branches(self):
        for selected in (self.bp, self.lp, self.rp):
            with self.subTest(source=selected.name):
                original = selected.read_bytes()
                selected.write_bytes(original + b' ')
                self.fail_cli()
                selected.write_bytes(original)

    def test_forged_plan_even_with_updated_hash(self):
        self.plan['notice'] = 'forged'
        self.write('plan.json', self.plan)
        self.args.expected_plan_sha256 = data.sha(self.pp.read_bytes())
        self.decisions['plan_sha256'] = self.args.expected_plan_sha256
        self.refresh_decisions()
        self.assertIn('does not match', self.fail_cli())

    def test_decisions_bind_another_plan(self):
        self.decisions['plan_sha256'] = '0' * 64
        self.refresh_decisions()
        self.assertIn('bind another plan', self.fail_cli())

    def test_invalid_json_schema_and_nonfinite(self):
        for raw in (b'{"version":1,"version":1}', b'{"value":NaN}', b'[]', b'{"version":true}'):
            self.dp.write_bytes(raw)
            self.args.expected_decisions_sha256 = data.sha(raw)
            self.fail_cli()

    def test_path_boundaries(self):
        self.args.plan = str(self.root / 'missing')
        self.fail_cli()
        self.args.plan = str(self.root / '..' / self.root.name / 'plan.json')
        self.assertIn('Parent traversal', self.fail_cli())
        link = self.root / 'link.json'
        link.symlink_to(self.pp)
        self.args.plan = str(link)
        self.assertIn('Symlink', self.fail_cli())
        self.args.plan = str(self.root / '.env-plan')
        self.assertIn('Sensitive', self.fail_cli())

    def test_final_rereads_all_five(self):
        original = data.read_bytes
        with mock.patch.object(data, 'read_bytes', wraps=original) as reader:
            check.check(self.args)
        self.assertEqual([Path(call.args[0]) for call in reader.call_args_list[-5:]], [self.bp, self.lp, self.rp, self.pp, self.dp])

    def test_each_source_mutated_during_analysis(self):
        for selected in (self.bp, self.lp, self.rp, self.pp, self.dp):
            with self.subTest(source=selected.name):
                original = selected.read_bytes()
                resolver = merge.resolved_graph
                def mutate(*args):
                    graph = resolver(*args)
                    selected.write_bytes(original + b' ')
                    return graph
                with mock.patch.object(merge, 'resolved_graph', side_effect=mutate):
                    self.assertIn('Source changed during analysis', self.fail_cli_without_snapshot())
                selected.write_bytes(original)

    def fail_cli_without_snapshot(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            result = check.main(self.argv())
        self.assertEqual(result, 2)
        self.assertEqual(out.getvalue(), '')
        return err.getvalue()

    def test_duplicate_logical_argument_combination_matches_apply_rejection(self):
        self.left['chains'].append(chain('left-arg', ['c'], 'a'))
        self.right['chains'].append(chain('right-arg', ['c'], 'a'))
        self.rebuild()
        self.assertIn('Duplicate logical argument', self.fail_cli())
        with self.assertRaisesRegex(data.DataError, 'Duplicate logical argument'):
            merge.apply(argparse.Namespace(**vars(self.args), approve=True, output=str(self.root / 'output.json')))

    def test_missing_endpoint_selected_combination_matches_apply(self):
        self.left['nodes'] = [n for n in self.left['nodes'] if n['id'] != 'a']
        self.left['chains'] = []
        self.right['chains'][0]['premises'] = ['a']
        self.rebuild()
        # Select deletion of a, but retain the right branch's dependent argument.
        for choice in self.decisions['choices']:
            choice['choose'] = 'left' if choice['kind'] == 'node' else 'right'
        self.refresh_decisions()
        self.assertIn('unresolved endpoints', self.fail_cli())
        with self.assertRaisesRegex(data.DataError, 'unresolved endpoints'):
            merge.apply(argparse.Namespace(**vars(self.args), approve=True, output=str(self.root / 'output.json')))

    def test_256_records_allowed_257_combined_refused(self):
        self.base['nodes'] = [node('n%03d' % i) for i in range(255)]
        self.base['chains'] = []
        self.left = copy.deepcopy(self.base)
        self.right = copy.deepcopy(self.base)
        self.left['nodes'].append(node('z'))
        self.rebuild()
        self.assertEqual(check.check(self.args)['nodes'], 256)
        self.right['nodes'].append(node('y'))
        self.rebuild()
        for choice in self.decisions['choices']:
            choice['choose'] = 'left' if choice['id'] == 'z' else 'right'
        self.refresh_decisions()
        self.assertIn('256', self.fail_cli())

    def test_draft_decisions_plan_read_size_limits(self):
        for path, limit in ((self.lp, check.editor.INPUT_LIMIT), (self.dp, check.editor.INPUT_LIMIT), (self.pp, data.LIMIT)):
            with self.subTest(source=path.name):
                original = path.read_bytes()
                path.write_bytes(b' ' * (limit + 1))
                self.assertIn('limit', self.fail_cli())
                path.write_bytes(original)

    def test_final_encoded_draft_limit_and_exact_boundary(self):
        # Independent edits fit each input while their union exceeds 2 MiB.
        self.base['chains'] = []
        self.left = copy.deepcopy(self.base)
        self.right = copy.deepcopy(self.base)
        self.left['nodes'][1]['statement'] = 'l' * (1100 * 1024)
        self.right['nodes'][2]['statement'] = 'r' * (1100 * 1024)
        self.rebuild()
        for choice in self.decisions['choices']:
            choice['choose'] = 'right' if choice['id'] == 'c' else 'left'
        self.refresh_decisions()
        self.assertIn('Merged draft exceeds', self.fail_cli())
        # Exercise the exact final encoded boundary without allocating oversized graphs.
        self.left = copy.deepcopy(self.base)
        self.right = copy.deepcopy(self.base)
        self.rebuild()
        encoded = merge.encoded(merge.draft_from_graph(self.base, self.base, data.sha(self.bp.read_bytes())))
        # No-op graph encoding does not include graph warning history.
        with mock.patch.object(check.editor, 'INPUT_LIMIT', len(encoded)):
            # read_json shares this bound, so use actual original reader for inputs.
            actual_reader = check.editor.read_json
            def read_unbounded(path, label):
                with mock.patch.object(check.editor, 'INPUT_LIMIT', 2 * 1024 * 1024):
                    return actual_reader(path, label)
            with mock.patch.object(check.editor, 'read_json', side_effect=read_unbounded):
                self.assertEqual(check.check(self.args)['draft_bytes'], len(encoded))
        with mock.patch.object(merge, 'encoded', return_value=b' ' * (check.editor.INPUT_LIMIT + 1)):
            self.assertIn('Merged draft exceeds', self.fail_cli())

    def test_standalone_command_no_new_files_and_no_publish(self):
        before = self.snapshot()
        with mock.patch.object(data, 'publish', side_effect=AssertionError('publisher must not run')), redirect_stdout(io.StringIO()):
            self.assertEqual(check.main(self.argv()), 0)
        completed = subprocess.run([sys.executable, '-B', str(SKILL / 'scripts' / 'draft_merge_check.py')] + self.argv(), capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(json.loads(completed.stdout)['applicable'])
        self.assertEqual(before, self.snapshot())


if __name__ == '__main__':
    unittest.main()
