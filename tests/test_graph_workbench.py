"""Executed source, edit, preservation and viewer checks; original fixtures."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SKILL = Path(os.environ.get('TEACH_ME_SKILL', str(Path(__file__).resolve().parents[1] / 'teach-me')))
SCRIPT = SKILL / 'scripts/graph_workbench.py'
VIEW = SKILL / 'scripts/learning_data.py'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class GraphWorkbenchCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / 'notes.txt'
        self.text = '🧠 A is red.\r\nB is square.\r\nA and B jointly support C.\r\nC is flagged.\r\n'
        self.source.write_bytes(self.text.encode('utf-8'))
        self.proposal = self.root / 'proposal.json'
        self.value = self.proposal_value()
        self.write(self.proposal, self.value)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, path, value):
        path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
        return path

    def evidence(self, quote):
        start = self.text.index(quote)
        return {'start': start, 'end': start + len(quote), 'quote': quote}

    def proposal_value(self):
        return {'version': 1, 'source_sha256': sha(self.source.read_bytes()),
                'nodes': [{'id': 'A', 'name': 'Red', 'statement': 'A is red', 'evidence': self.evidence('🧠 A is red.')},
                          {'id': 'B', 'name': 'Square', 'statement': 'B is square', 'evidence': self.evidence('B is square.')},
                          {'id': 'C', 'name': 'Flagged', 'statement': 'C is flagged', 'evidence': self.evidence('C is flagged.')}],
                'chains': [{'id': 'joint', 'premises': ['A', 'B'], 'conclusion': 'C',
                            'evidence': self.evidence('A and B jointly support C.')} ]}

    def cli(self, *args, expected=0, script=SCRIPT):
        p = subprocess.run([sys.executable, '-B', str(script), *map(str, args)],
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(p.returncode, expected, p.stderr + p.stdout)
        return json.loads(p.stdout) if p.stdout else p.stderr

    def check(self):
        return self.cli('check', '--source', self.source, '--proposal', self.proposal)

    def apply(self, output=None, value=None, **kwargs):
        if value is not None:
            self.write(self.proposal, value)
        output = output or self.root / 'graph.json'
        args = ['apply', '--source', self.source, '--proposal', self.proposal,
                '--expected-proposal-sha256', sha(self.proposal.read_bytes()), '--output', output, '--approve']
        args.extend(kwargs.pop('extra', []))
        self.cli(*args, **kwargs)
        return output

    def graph(self):
        path = self.apply()
        return path, json.loads(path.read_text())

    def patch(self, **change):
        value = {'version': 1, 'delete_nodes': [], 'delete_chains': [], 'upsert_nodes': [], 'upsert_chains': []}
        value.update(change)
        return value

    def edit(self, base, patch, output=None, **kwargs):
        patchfile = self.write(self.root / 'patch.json', patch)
        output = output or self.root / 'edited.json'
        self.cli('edit', '--base', base, '--patch', patchfile,
                 '--expected-base-sha256', kwargs.pop('base_sha', sha(base.read_bytes())),
                 '--expected-patch-sha256', kwargs.pop('patch_sha', sha(patchfile.read_bytes())),
                 '--output', output, '--approve', **kwargs)
        return output

    def test_unicode_zero_offset_and_joint_provenance_roundtrip(self):
        before = self.source.read_bytes()
        result = self.check()
        self.assertTrue(result['source_spans_valid'])
        self.assertTrue(result['ready_without_base'])
        self.assertFalse(result['semantic_correctness_verified'])
        self.assertEqual(result['proposal_sha256'], sha(self.proposal.read_bytes()))
        graph = json.loads(self.apply().read_text())
        self.assertEqual(graph['chains'][0]['premises'], ['A', 'B'])
        point = graph['nodes'][0]['provenance'][0]
        self.assertEqual(point['chatId'], 'src_' + sha(before))
        self.assertEqual(point['messageId'], 'chars:0:11')
        self.assertEqual(self.source.read_bytes(), before)

    def test_wrong_hash_quote_offsets_and_missing_fields_refused(self):
        variants = []
        v = copy.deepcopy(self.value); v['source_sha256'] = '0' * 64; variants.append(v)
        v = copy.deepcopy(self.value); v['nodes'][0]['evidence']['quote'] = 'Invented'; variants.append(v)
        for key, value in [('start', True), ('start', -1), ('end', 99999), ('end', 0)]:
            v = copy.deepcopy(self.value); v['nodes'][0]['evidence'][key] = value; variants.append(v)
        v = copy.deepcopy(self.value); del v['nodes'][0]['evidence']['start']; variants.append(v)
        for value in variants:
            self.write(self.proposal, value)
            self.cli('check', '--source', self.source, '--proposal', self.proposal, expected=2)

    def test_duplicate_unknown_and_nonfinite_json_refused(self):
        variants = [dict(self.value, version=True), dict(self.value, extra='unknown')]
        v = copy.deepcopy(self.value); v['nodes'].append(copy.deepcopy(v['nodes'][0])); variants.append(v)
        v = copy.deepcopy(self.value); v['chains'][0]['premises'] = ['A', 'A']; variants.append(v)
        v = copy.deepcopy(self.value); v['chains'].append(dict(v['chains'][0], id='duplicate-argument')); variants.append(v)
        for value in variants:
            self.write(self.proposal, value)
            self.cli('check', '--source', self.source, '--proposal', self.proposal, expected=2)
        self.proposal.write_text('{"version":1,"version":1}')
        self.cli('check', '--source', self.source, '--proposal', self.proposal, expected=2)
        self.proposal.write_text('{"version":NaN}')
        self.cli('check', '--source', self.source, '--proposal', self.proposal, expected=2)

    def test_stale_proposal_and_source_and_missing_review_write_nothing(self):
        output = self.root / 'new.json'
        digest = sha(self.proposal.read_bytes())
        self.cli('apply', '--source', self.source, '--proposal', self.proposal,
                 '--expected-proposal-sha256', digest, '--output', output, expected=2)
        self.cli('apply', '--source', self.source, '--proposal', self.proposal,
                 '--expected-proposal-sha256', '0'*64, '--output', output, '--approve', expected=2)
        self.source.write_text('Changed source')
        self.cli('apply', '--source', self.source, '--proposal', self.proposal,
                 '--expected-proposal-sha256', digest, '--output', output, '--approve', expected=2)
        self.assertFalse(output.exists())

    def test_unresolved_check_distinct_from_ready_and_apply_requires_base(self):
        base, graph = self.graph()
        proposal = copy.deepcopy(self.value)
        proposal['nodes'] = []
        proposal['chains'][0]['id'] = 'other'
        proposal['chains'][0]['premises'] = ['A']
        self.write(self.proposal, proposal)
        result = self.check()
        self.assertTrue(result['source_spans_valid'])
        self.assertFalse(result['ready_without_base'])
        self.assertEqual(result['unresolved_endpoint_ids'], ['A', 'C'])
        self.apply(self.root/'no-base.json', expected=2)
        self.assertFalse((self.root/'no-base.json').exists())
        path = self.apply(self.root/'extended.json', extra=['--base', base, '--expected-base-sha256', sha(base.read_bytes())])
        self.assertEqual(len(json.loads(path.read_text())['chains']), 2)

    def test_apply_never_overwrites_base_ids_or_uses_stale_base(self):
        base, graph = self.graph()
        raw = base.read_bytes()
        self.apply(self.root/'collision.json', extra=['--base', base, '--expected-base-sha256', sha(raw)], expected=2)
        self.apply(self.root/'stale.json', extra=['--base', base, '--expected-base-sha256', '0'*64], expected=2)
        self.assertEqual(base.read_bytes(), raw)
        self.assertFalse((self.root/'collision.json').exists())

    def test_existing_output_source_and_symlink_refused(self):
        output = self.root/'existing.json'; output.write_text('preserve')
        self.apply(output, expected=2)
        self.assertEqual(output.read_text(), 'preserve')
        source_raw = self.source.read_bytes()
        self.apply(self.source, expected=2)
        self.assertEqual(self.source.read_bytes(), source_raw)
        link = self.root/'link.txt'; link.symlink_to(self.source)
        self.cli('check', '--source', link, '--proposal', self.proposal, expected=2)
        sensitive = self.root/'auth.json'; sensitive.write_bytes(source_raw)
        self.cli('check', '--source', sensitive, '--proposal', self.proposal, expected=2)

    def test_explicit_edit_preserves_original_and_updates_record(self):
        base, graph = self.graph(); before = base.read_bytes()
        node = copy.deepcopy(graph['nodes'][0]); node['name'] = 'Edited label'
        edited = json.loads(self.edit(base, self.patch(upsert_nodes=[node])).read_text())
        self.assertEqual(edited['nodes'][0]['name'], 'Edited label')
        self.assertEqual(edited['chains'][0]['premises'], ['A','B'])
        self.assertEqual(base.read_bytes(), before)
        self.assertTrue(any('operator supplied' in warning for warning in edited['warnings']))

    def test_edit_orphan_unknown_delete_duplicate_and_overlap_refused(self):
        base, graph = self.graph()
        patches = [self.patch(delete_nodes=['A']), self.patch(delete_nodes=['unknown']),
                   self.patch(upsert_nodes=[graph['nodes'][0], graph['nodes'][0]]),
                   self.patch(delete_nodes=['A'], upsert_nodes=[graph['nodes'][0]])]
        for index, patch in enumerate(patches):
            self.edit(base, patch, output=self.root/('bad%d.json'%index), expected=2)
        output = self.edit(base, self.patch(delete_nodes=['A'], delete_chains=['joint']))
        result = json.loads(output.read_text())
        self.assertEqual([n['id'] for n in result['nodes']], ['B', 'C'])
        self.assertEqual(result['chains'], [])

    def test_edit_stale_hashes_preserve_existing_output(self):
        base, graph = self.graph()
        output = self.root/'edited.json'; output.write_text('foreign')
        self.edit(base, self.patch(), output=output, expected=2)
        self.assertEqual(output.read_text(), 'foreign')
        output.unlink()
        self.edit(base, self.patch(), base_sha='0'*64, expected=2)
        self.edit(base, self.patch(), patch_sha='0'*64, expected=2)
        self.assertFalse(output.exists())

    def test_sessions_and_ambiguous_chain_ids_refused_not_discarded(self):
        base, graph = self.graph()
        graph['sessions'] = [{'id':'s','title':'learner history','kind':'teach','events':[]}]
        self.write(base, graph)
        self.edit(base, self.patch(), expected=2)
        graph['sessions'] = []
        graph['chains'].append(dict(graph['chains'][0], premises=['A']))
        self.write(base, graph)
        self.edit(base, self.patch(), expected=2)

    def test_incomplete_base_must_be_repaired_explicitly(self):
        base, graph = self.graph()
        graph['nodes'] = [n for n in graph['nodes'] if n['id'] != 'A']
        graph['warnings'].append('Missing graph endpoint: A in chain joint')
        self.write(base, graph)
        self.edit(base, self.patch(), expected=2)
        result = json.loads(self.edit(base, self.patch(delete_chains=['joint'])).read_text())
        self.assertFalse(any(w.startswith('Missing graph endpoint: ') for w in result['warnings']))
        self.assertTrue(any(w.startswith('Input history: Missing graph endpoint: A') for w in result['warnings']))

    def test_hostile_labels_are_literal_in_existing_viewer(self):
        value = copy.deepcopy(self.value)
        value['nodes'][0]['name'] = '</script><img src=x onerror="alert(1)">'
        graph = self.apply(value=value)
        html = self.root/'map.html'
        self.cli('view', '--input', graph, '--output', html, script=VIEW)
        raw = html.read_text()
        self.assertNotIn('</script><img', raw)
        self.assertIn('\\u003c/script\\u003e', raw)
        self.assertIn('textContent', raw)
        self.assertIn(' AND ', raw)

    def test_exact_quote_is_not_claimed_to_prove_semantics(self):
        value = copy.deepcopy(self.value)
        value['nodes'][0]['statement'] = 'An unsupported paraphrase still needs review'
        self.write(self.proposal, value)
        self.assertFalse(self.check()['semantic_correctness_verified'])
        result = self.cli('apply', '--source', self.source, '--proposal', self.proposal,
                          '--expected-proposal-sha256', sha(self.proposal.read_bytes()),
                          '--output', self.root/'draft.json', '--approve')
        self.assertFalse(result['semantic_correctness_verified'])
        document = json.loads((self.root/'draft.json').read_text())
        self.assertTrue(any('not semantic truth' in w for w in document['warnings']))

    def test_oversized_source_refused_before_output(self):
        self.source.write_bytes(b'x'*(8*1024*1024+1))
        self.cli('check', '--source', self.source, '--proposal', self.proposal, expected=2)


if __name__ == '__main__':
    unittest.main()
