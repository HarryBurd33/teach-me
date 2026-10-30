"""Independent v0.11 contract cases, frozen before candidate inspection.

TEACH_ME_SKILL selects an installed, baseline or candidate skill directory.
Use Python -B; the checker must not create product artifacts or alter inputs.
Missing checker is an explicit feature failure, never negative-test credit.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SKILL = Path(os.environ.get('TEACH_ME_SKILL', Path(__file__).resolve().parents[1] / 'teach-me')).resolve()
CHECKER = SKILL / 'scripts' / 'draft_merge_check.py'
MERGER = SKILL / 'scripts' / 'draft_merge.py'
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n').encode('utf-8')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def node(ident, old=False):
    return dict(id=ident, name='Name ' + ident, statement='Statement ' + ident,
                aliases=['別名', 'alias'] if old else [], createdAt='2024-01-01T00:00:00Z' if old else '',
                provenance=[dict(chatId='chat_α', messageId='msg_β')] if old else [])


def chain(ident='k', premises=None, old=False):
    return dict(id=ident, premises=premises or ['a', 'b'], conclusion='c',
                createdAt='2024-02-01T00:00:00Z' if old else '',
                provenance=[dict(chatId='chat_γ', messageId='msg_δ')] if old else [])


def patch(**values):
    result = dict(version=1, delete_nodes=[], delete_chains=[], upsert_nodes=[], upsert_chains=[])
    result.update(values)
    return result


class MergeCheckContract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='teach-me-v11-review-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.paths = {name: self.root / (name + '.json') for name in ('base', 'left', 'right', 'plan', 'decisions')}
        self.base = dict(format='teach-me-learning-v1', source_files=[], sessions=[],
                         nodes=[node(x, True) for x in ('a', 'b', 'c')],
                         chains=[chain(old=True)], warnings=['Preserved history Ω'])
        a = copy.deepcopy(self.base['nodes'][0]); a['statement'] = 'Café 雪 → 🌱'
        k = copy.deepcopy(self.base['chains'][0]); k['premises'] = ['a', 'b', 'd']
        self.make(patch(upsert_nodes=[a]), patch(upsert_nodes=[node('d')], upsert_chains=[k]))

    def run_cmd(self, argv):
        return subprocess.run([sys.executable, '-B'] + [str(x) for x in argv], cwd=self.root,
                              env=ENV, text=True, capture_output=True, timeout=15)

    def put(self, name, value):
        self.paths[name].write_bytes(encoded(value))

    def make(self, left, right, choices=None):
        self.put('base', self.base)
        bh = digest(self.paths['base'].read_bytes())
        for name, value in [('left', left), ('right', right)]:
            self.put(name, dict(version=1, base_sha256=bh, patch=value))
        self.paths['plan'].unlink(missing_ok=True)
        result = self.run_cmd([MERGER, 'plan', '--base', self.paths['base'], '--left', self.paths['left'],
                               '--right', self.paths['right'], '--output', self.paths['plan']])
        self.assertEqual(result.returncode, 0, 'Fixture must be accepted by old merge planner: ' + result.stderr)
        self.plan = json.loads(self.paths['plan'].read_text())
        self.put('decisions', dict(version=1, plan_sha256=digest(self.paths['plan'].read_bytes()), choices=choices or []))
        self.refresh_hashes()

    def refresh_hashes(self):
        self.ph = digest(self.paths['plan'].read_bytes())
        self.dh = digest(self.paths['decisions'].read_bytes())

    def args(self):
        return ['check', '--base', self.paths['base'], '--left', self.paths['left'], '--right', self.paths['right'],
                '--plan', self.paths['plan'], '--expected-plan-sha256', self.ph,
                '--decisions', self.paths['decisions'], '--expected-decisions-sha256', self.dh]

    def tree(self):
        return {str(p.relative_to(self.root)): ('directory' if p.is_dir() else p.read_bytes())
                for p in self.root.rglob('*')}

    def check(self, args=None):
        self.assertTrue(CHECKER.is_file(), 'FEATURE ABSENT: no read-only merge checker; negative cases receive no credit')
        before = self.tree()
        result = self.run_cmd([CHECKER] + (self.args() if args is None else args))
        self.assertEqual(self.tree(), before, 'Checker changed input bytes or created product files')
        return result

    def refusal(self, result, reason):
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(result.stdout, '', 'Refusal must not emit success JSON')
        self.assertRegex(result.stderr.lower(), reason.lower())
        self.assertNotIn('traceback', result.stderr.lower())

    def apply(self):
        output = self.root / 'merged.json'
        args = self.args(); args[0] = 'apply'
        result = self.run_cmd([MERGER] + args + ['--output', output, '--approve'])
        self.assertEqual(result.returncode, 0, result.stderr)
        return output.read_bytes()

    def test_positive_exact_digest_metadata_and_joint_premises(self):
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(set(value), {'version', 'operation', 'format', 'applicable', 'plan_sha256',
                                     'decisions_sha256', 'draft_sha256', 'draft_bytes', 'nodes', 'chains',
                                     'conflicts_resolved', 'changes', 'semantic_correctness_verified', 'notice'})
        self.assertEqual(value['version'], 1); self.assertIs(type(value['version']), int)
        self.assertEqual(value['operation'], 'check')
        self.assertEqual(value['format'], 'teach-me-draft-merge-check-v1')
        self.assertIs(value['applicable'], True)
        self.assertIs(value['semantic_correctness_verified'], False)
        self.assertEqual(value['plan_sha256'], self.ph); self.assertEqual(value['decisions_sha256'], self.dh)
        self.assertEqual((value['nodes'], value['chains'], value['conflicts_resolved']), (4, 1, 0))
        self.assertEqual(value['changes'], dict(delete_nodes=[], delete_chains=[], upsert_nodes=['a', 'd'], upsert_chains=['k']))
        for name in ('base', 'left', 'right', 'plan', 'decisions'):
            self.assertNotIn(str(self.paths[name]), result.stdout)
        self.assertNotIn('Café', result.stdout)
        self.assertTrue(value['notice']); self.assertIn('structur', value['notice'].lower())
        self.assertRegex(value['notice'].lower(), 'authoriz|approv')
        second = self.check(); self.assertEqual(result.stdout, second.stdout)
        raw = self.apply()
        self.assertEqual((value['draft_sha256'], value['draft_bytes']), (digest(raw), len(raw)))
        out = json.loads(raw)['patch']
        self.assertEqual(out['upsert_nodes'][0]['statement'], 'Café 雪 → 🌱')
        for key in ('aliases', 'createdAt', 'provenance'):
            self.assertEqual(out['upsert_nodes'][0][key], self.base['nodes'][0][key])
        self.assertEqual(out['upsert_chains'][0]['premises'], ['a', 'b', 'd'])
        for key in ('createdAt', 'provenance'):
            self.assertEqual(out['upsert_chains'][0][key], self.base['chains'][0][key])

    def conflict(self, choice='left'):
        a = copy.deepcopy(self.base['nodes'][0]); a['statement'] = 'left wording'
        b = copy.deepcopy(self.base['nodes'][0]); b['name'] = 'right name'
        self.make(patch(upsert_nodes=[a]), patch(upsert_nodes=[b]), [dict(kind='node', id='a', choose=choice)])

    def test_each_whole_record_conflict_choice_matches_apply(self):
        for side in ('base', 'left', 'right'):
            with self.subTest(side=side):
                (self.root / 'merged.json').unlink(missing_ok=True)
                self.conflict(side)
                r = self.check(); self.assertEqual(r.returncode, 0, r.stderr)
                value = json.loads(r.stdout); self.assertEqual(value['conflicts_resolved'], 1)
                self.assertEqual(value['draft_sha256'], digest(self.apply()))

    def test_missing_extra_duplicate_choices(self):
        self.conflict()
        good = json.loads(self.paths['decisions'].read_text())
        cases = [([], 'every conflict'), (good['choices'] * 2, 'duplicate'),
                 (good['choices'] + [dict(kind='node', id='b', choose='base')], 'not a required conflict')]
        for choices, reason in cases:
            with self.subTest(reason=reason):
                value = copy.deepcopy(good); value['choices'] = choices; self.put('decisions', value); self.refresh_hashes()
                self.refusal(self.check(), reason)

    def test_incompatible_selected_endpoint_is_refused(self):
        self.base['nodes'].append(node('x', True))
        k = copy.deepcopy(self.base['chains'][0]); k['premises'] = ['a', 'x']
        self.make(patch(delete_nodes=['x']), patch(upsert_chains=[k]))
        self.assertEqual({(x['kind'], x['id']) for x in self.plan['conflicts']}, {('node', 'x'), ('chain', 'k')})
        self.put('decisions', dict(version=1, plan_sha256=self.ph, choices=[dict(kind='node', id='x', choose='left'), dict(kind='chain', id='k', choose='right')]))
        self.refresh_hashes(); self.refusal(self.check(), 'unresolved endpoints')

    def test_independent_logical_duplicates_are_refused(self):
        self.make(patch(upsert_chains=[chain('u', ['a'])]), patch(upsert_chains=[chain('v', ['a'])]))
        self.assertEqual(self.plan['conflicts'], [])
        self.refusal(self.check(), 'duplicate logical argument')

    def test_reviewed_plan_and_decisions_raw_hashes(self):
        for name in ('plan', 'decisions'):
            with self.subTest(name=name):
                old = self.paths[name].read_bytes(); self.paths[name].write_bytes(old + b' ')
                self.refusal(self.check(), name + '.*changed since review')
                self.paths[name].write_bytes(old)

    def test_reviewed_sources_are_current_exact_bytes(self):
        for name in ('base', 'left', 'right'):
            with self.subTest(name=name):
                old = self.paths[name].read_bytes(); self.paths[name].write_bytes(old + b' ')
                self.refusal(self.check(), 'base sha256|current source drafts')
                self.paths[name].write_bytes(old)

    def test_forged_plan_with_matching_raw_hash_still_refuses(self):
        p = copy.deepcopy(self.plan); p['automatic']['nodes'] = []; self.put('plan', p)
        self.ph = digest(self.paths['plan'].read_bytes())
        d = json.loads(self.paths['decisions'].read_text()); d['plan_sha256'] = self.ph; self.put('decisions', d); self.refresh_hashes()
        self.refusal(self.check(), 'current source drafts')

    def test_decisions_must_bind_exact_plan(self):
        d = json.loads(self.paths['decisions'].read_text()); d['plan_sha256'] = 'f' * 64; self.put('decisions', d); self.refresh_hashes()
        self.refusal(self.check(), 'another plan')

    def test_malformed_choices_and_exact_decision_schema(self):
        self.conflict()
        good = json.loads(self.paths['decisions'].read_text())
        variants = []
        for version in (True, 1.0, 2):
            v = copy.deepcopy(good); v['version'] = version; variants.append((v, 'version'))
        v = copy.deepcopy(good); v['extra'] = 1; variants.append((v, 'keys'))
        for key, value in [('choose', 'merge'), ('kind', 'graph')]:
            v = copy.deepcopy(good); v['choices'][0][key] = value; variants.append((v, 'choice'))
        for v, reason in variants:
            with self.subTest(v=v):
                self.put('decisions', v); self.refresh_hashes(); self.refusal(self.check(), reason)

    def test_duplicate_json_members_refuse(self):
        raw = self.paths['decisions'].read_bytes().replace(b'"version": 1', b'"version": 1, "version": 1')
        self.paths['decisions'].write_bytes(raw); self.refresh_hashes(); self.refusal(self.check(), 'duplicate json member')

    def test_input_byte_bounds(self):
        for name, limit in [('base', 2), ('left', 2), ('right', 2), ('decisions', 2), ('plan', 8)]:
            with self.subTest(name=name):
                old = self.paths[name].read_bytes()
                self.paths[name].write_bytes(old + b' ' * (limit * 1024 * 1024 + 1 - len(old)))
                self.refresh_hashes(); self.refusal(self.check(), str(limit) + ' mib')
                self.paths[name].write_bytes(old); self.refresh_hashes()

    def test_final_record_capacity_choice_refuses(self):
        self.base['nodes'] += [node('n%03d' % i, True) for i in range(251)]
        self.make(patch(upsert_nodes=[node('l1'), node('l2')]), patch(upsert_nodes=[node('r1'), node('r2')]))
        self.assertEqual(len(self.plan['conflicts']), 4)
        choices = [dict(kind=c['kind'], id=c['id'], choose='left' if c['id'].startswith('l') else 'right') for c in self.plan['conflicts']]
        self.put('decisions', dict(version=1, plan_sha256=self.ph, choices=choices)); self.refresh_hashes()
        self.refusal(self.check(), '256')

    def test_cli_requires_hashes_and_rejects_output_or_approve(self):
        for option in ('--expected-plan-sha256', '--expected-decisions-sha256'):
            with self.subTest(option=option):
                args = self.args(); start = args.index(option); del args[start:start + 2]
                self.refusal(self.check(args), 'required')
        for extras in (['--approve'], ['--output', self.root / 'unwanted.json']):
            with self.subTest(extras=extras):
                self.refusal(self.check(self.args() + extras), 'unrecognized arguments')
        for value in ('A' * 64, 'x', '0' * 63):
            args = self.args(); args[args.index('--expected-plan-sha256') + 1] = value
            self.refusal(self.check(args), 'sha256')

    def test_final_reread_refuses_changes_to_each_of_five_sources(self):
        self.assertTrue(CHECKER.is_file(), 'FEATURE ABSENT: race refusals receive no credit')
        wrapper = r'''
import importlib.util, pathlib, sys
checker = pathlib.Path(sys.argv[1]); target = pathlib.Path(sys.argv[2]); args = sys.argv[3:]
sys.path.insert(0, str(checker.parent))
spec = importlib.util.spec_from_file_location('review_checker', checker)
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
fired = False
def trace(frame, event, value):
    global fired
    if not fired and event == 'return' and frame.f_code.co_name == 'resolved_graph' and pathlib.Path(frame.f_code.co_filename).name == 'draft_merge.py':
        fired = True
        target.write_bytes(target.read_bytes() + b' ')
        print('REVIEW_RACE_INJECTED', file=sys.stderr)
    return trace
sys.settrace(trace)
result = module.main(args)
sys.settrace(None)
if not fired:
    print('REVIEW_RACE_NOT_INJECTED', file=sys.stderr)
    sys.exit(97)
sys.exit(result)
'''
        for name in ('base', 'left', 'right', 'plan', 'decisions'):
            with self.subTest(name=name):
                old = self.paths[name].read_bytes(); before = self.tree()
                result = self.run_cmd(['-c', wrapper, CHECKER, self.paths[name]] + self.args())
                self.assertIn('REVIEW_RACE_INJECTED', result.stderr)
                self.refusal(result, 'chang|differ|stale')
                before[name + '.json'] = old + b' '
                self.assertEqual(self.tree(), before, 'Checker wrote beyond the injected source mutation')
                self.paths[name].write_bytes(old)


if __name__ == '__main__':
    unittest.main(verbosity=2)
