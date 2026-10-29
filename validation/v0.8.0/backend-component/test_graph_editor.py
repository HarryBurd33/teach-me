"""Focused v0.8 backend contract tests; Python 3.9+, stdlib."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'candidate' / 'teach-me' / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import graph_editor as editor
import graph_workbench as workbench
import learning_data as data


def node(ident, name=None):
    return {'id': ident, 'name': name or ident, 'statement': 'Claim '+ident,
            'aliases': ['alias '+ident], 'createdAt': '2026-01-02',
            'provenance': [{'chatId': 'source', 'messageId': 'm1'}]}


def chain(ident='c1', premises=None, conclusion='b'):
    return {'id': ident, 'premises': premises or ['a'], 'conclusion': conclusion,
            'createdAt': '', 'provenance': []}


class EditorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.base = self.root / 'base.json'
        self.draft = self.root / 'draft.json'
        self.output = self.root / 'new.json'
        self.graph = data.envelope([])
        self.graph.update(nodes=[node('a'), node('b')], chains=[chain()],
                          source_files=[{'name':'native-source','sha256':'0'*64}], warnings=['kept warning'])
        self.patch = {'version':1, 'delete_nodes':[], 'delete_chains':[],
                      'upsert_nodes':[], 'upsert_chains':[]}
        self.write_base()
        self.write_draft()
        self.args = argparse.Namespace(base=str(self.base), draft=str(self.draft),
                                       expected_draft_sha256=data.sha(self.draft.read_bytes()),
                                       output=str(self.output), approve=True)

    def tearDown(self):
        self.temp.cleanup()

    def write_base(self):
        self.base.write_text(json.dumps(self.graph), encoding='utf-8')

    def write_draft(self, **extra):
        value = {'version':1, 'base_sha256':data.sha(self.base.read_bytes()), 'patch':self.patch}
        value.update(extra)
        self.draft.write_text(json.dumps(value), encoding='utf-8')

    def rejected(self, fn=None):
        with self.assertRaises((data.DataError, OSError)):
            (fn or (lambda: editor.check(self.args)))()
        self.assertFalse(self.output.exists())

    def test_check_writes_nothing_and_review_digest_exact(self):
        before = self.base.read_bytes()
        report = editor.check(self.args)
        self.assertEqual(report['draft_sha256'], data.sha(self.draft.read_bytes()))
        self.assertFalse(report['semantic_correctness_verified'])
        self.assertFalse(self.output.exists())
        self.assertEqual(before, self.base.read_bytes())

    def test_apply_preserves_full_metadata_sources_warnings_and_original(self):
        before = self.base.read_bytes()
        edited = copy.deepcopy(self.graph['nodes'][0]); edited['statement'] = 'Edited assertion'
        self.patch['upsert_nodes'] = [edited]
        self.write_draft(); self.args.expected_draft_sha256 = data.sha(self.draft.read_bytes())
        editor.apply(self.args)
        result = json.loads(self.output.read_text())
        self.assertEqual(result['nodes'][0], edited)
        self.assertEqual(result['source_files'], self.graph['source_files'])
        self.assertIn('kept warning', result['warnings'])
        self.assertIn(editor.WARNING, result['warnings'])
        self.assertNotIn(workbench.WARNING, result['warnings'])
        self.assertEqual(before, self.base.read_bytes())
        data.validate_document(result)

    def test_existing_legacy_notice_preserved_as_history(self):
        self.graph['warnings'].append(workbench.WARNING)
        self.write_base(); self.write_draft()
        _,_,_,_,result = editor.checked_draft(self.base,self.draft)
        self.assertIn(workbench.WARNING,result['warnings'])

    def test_joint_premises_and_new_unknown_creation_time(self):
        added = node('z'); added.update(aliases=[], createdAt='', provenance=[])
        self.patch.update(upsert_nodes=[added], upsert_chains=[chain('joint',['a','b'],'z')])
        self.write_draft()
        result = editor.check(self.args)
        self.assertEqual((result['nodes'], result['chains']), (3,2))

    def test_pure_helper_does_not_mutate_inputs(self):
        original, original_patch = copy.deepcopy(self.graph), copy.deepcopy(self.patch)
        result = workbench.edited_graph(self.graph, self.patch)
        self.assertEqual(self.graph, original); self.assertEqual(self.patch, original_patch)
        self.assertIsNot(result, self.graph)

    def test_unknown_draft_key(self):
        self.write_draft(extra=True); self.rejected()

    def test_unknown_patch_key(self):
        self.patch['extra'] = True; self.write_draft(); self.rejected()

    def test_bool_draft_version(self):
        self.write_draft(version=True); self.rejected()

    def test_bool_patch_version(self):
        self.patch['version'] = True; self.write_draft(); self.rejected()

    def test_duplicate_json_key(self):
        self.draft.write_text('{"version":1,"version":1}'); self.rejected()

    def test_stale_base_digest(self):
        self.base.write_bytes(self.base.read_bytes()+b'\n'); self.rejected()

    def test_malformed_digest(self):
        self.write_draft(base_sha256='X'*64); self.rejected()

    def test_stale_exact_draft_digest(self):
        self.draft.write_bytes(self.draft.read_bytes()+b'\n')
        self.rejected(lambda: editor.apply(self.args))

    def test_missing_approval(self):
        self.args.approve = False; self.rejected(lambda: editor.apply(self.args))

    def test_session_document_refused(self):
        self.graph['sessions'] = [{'id':'s','title':'','kind':'teach','events':[]}]
        self.write_base(); self.write_draft(); self.rejected()

    def test_null_creation_time_refused(self):
        self.patch['upsert_nodes'] = [dict(node('z'), createdAt=None)]
        self.write_draft(); self.rejected()

    def test_malformed_id_refused(self):
        self.patch['upsert_nodes'] = [node(' bad ')]; self.write_draft(); self.rejected()

    def test_duplicate_upsert_id_refused(self):
        self.patch['upsert_nodes'] = [node('z'),node('z')]; self.write_draft(); self.rejected()

    def test_duplicate_chain_id_refused(self):
        self.patch['upsert_chains'] = [chain('z'),chain('z',['b'],'a')]
        self.write_draft(); self.rejected()

    def test_duplicate_premise_refused(self):
        self.patch['upsert_chains'] = [chain('z',['a','a'])]; self.write_draft(); self.rejected()

    def test_empty_premises_refused(self):
        added = chain('z'); added['premises'] = []
        self.patch['upsert_chains'] = [added]; self.write_draft(); self.rejected()

    def test_unknown_delete_refused(self):
        self.patch['delete_nodes'] = ['absent']; self.write_draft(); self.rejected()

    def test_delete_upsert_overlap_refused(self):
        self.patch.update(delete_nodes=['a'],upsert_nodes=[node('a')]); self.write_draft(); self.rejected()

    def test_referenced_delete_refused(self):
        self.patch['delete_nodes'] = ['a']; self.write_draft(); self.rejected()

    def test_initial_missing_endpoint_allowed_but_final_check_refused(self):
        self.graph['chains'][0]['conclusion'] = 'missing'; self.write_base(); self.write_draft()
        editor.read_graph(self.base); self.rejected()

    def test_missing_endpoint_can_be_repaired_and_history_retained(self):
        self.graph['chains'][0]['conclusion'] = 'missing'
        self.graph['warnings'].append('Missing graph endpoint: missing in chain c1')
        self.write_base(); self.patch['upsert_nodes'] = [node('missing')]; self.write_draft()
        _,_,_,_,result = editor.checked_draft(self.base,self.draft)
        self.assertIn('Input history: Missing graph endpoint: missing in chain c1', result['warnings'])

    def test_base_bytes_bound(self):
        self.base.write_bytes(b' '*(editor.INPUT_LIMIT+1)); self.rejected()

    def test_draft_bytes_bound(self):
        self.draft.write_bytes(b' '*(editor.INPUT_LIMIT+1)); self.rejected()

    def test_base_node_count_bound(self):
        self.graph['nodes'] = [node('n'+str(i)) for i in range(257)]; self.graph['chains'] = []
        self.write_base(); self.write_draft(); self.rejected()

    def test_base_chain_count_bound(self):
        self.graph['nodes'] = [node('a')]+[node('n'+str(i)) for i in range(255)]
        self.graph['chains'] = [chain('c'+str(i),['a'],'n'+str(i%255)) for i in range(256)]
        # 257th distinct chain avoids duplicate-logical-argument rejection masking bound.
        self.graph['chains'][-1]['premises'] = ['a','n0']
        self.graph['chains'].append(chain('extra',['a','n1'],'n2'))
        self.write_base(); self.write_draft(); self.rejected()

    def test_final_node_count_bound(self):
        self.graph['nodes'] = [node('n'+str(i)) for i in range(256)]; self.graph['chains'] = []
        self.write_base(); self.patch['upsert_nodes'] = [node('extra')]; self.write_draft(); self.rejected()

    def test_existing_output_preserved(self):
        self.output.write_bytes(b'foreign')
        with self.assertRaises(OSError): editor.apply(self.args)
        self.assertEqual(self.output.read_bytes(),b'foreign')

    def test_output_cannot_replace_base(self):
        self.args.output = str(self.base)
        before = self.base.read_bytes(); self.rejected(lambda: editor.apply(self.args))
        self.assertEqual(self.base.read_bytes(), before)

    def test_source_change_during_publication_refused(self):
        original = data.os.fsync
        def mutate(fd):
            original(fd); self.draft.write_bytes(self.draft.read_bytes()+b'\n')
        with patch.object(data.os, 'fsync', side_effect=mutate):
            self.rejected(lambda: editor.apply(self.args))
        self.assertEqual(list(self.root.glob('.teach-me-report-*')), [])

    def test_foreign_output_race_preserved(self):
        original = data.os.link
        def replace(staging, target):
            Path(target).write_bytes(b'foreign-race'); return original(staging,target)
        with patch.object(data.os,'link',side_effect=replace):
            with self.assertRaises(OSError): editor.apply(self.args)
        self.assertEqual(self.output.read_bytes(),b'foreign-race')

    def test_render_escapes_hostile_data_and_hashes_exact_inline_bytes(self):
        self.graph['nodes'][0]['statement'] = '</script><img src=x onerror=alert(1)>&\u2028{{EDITOR_SCRIPT}}'
        html = editor.render_html(self.graph,'a'*64)
        self.assertNotIn('</script><img',html)
        self.assertIn('\\u003c/script\\u003e',html)
        self.assertIn('\\u2028',html)
        self.assertIn('{{EDITOR_SCRIPT}}',html)
        script = (editor.ASSET_DIR/'graph-editor.js').read_text()
        style = (editor.ASSET_DIR/'graph-editor.css').read_text()
        self.assertIn("'sha256-"+editor.inline_hash(script)+"'",html)
        self.assertIn("'sha256-"+editor.inline_hash(style)+"'",html)
        self.assertIn('<script>'+script+'</script>',html)
        self.assertIn('<style>'+style+'</style>',html)

    def test_render_uses_checked_publication_and_allows_repair(self):
        self.graph['chains'][0]['conclusion']='missing'; self.write_base()
        out = self.root/'editor.html'
        args = argparse.Namespace(input=str(self.base),output=str(out))
        report=editor.render(args)
        self.assertEqual(report['unresolved_endpoint_ids'],['missing'])
        self.assertTrue(out.read_text().startswith('<!doctype html>'))

    def test_html_size_bound(self):
        with patch.object(editor,'HTML_LIMIT',1):
            self.rejected(lambda:editor.render_html(self.graph,'a'*64))


if __name__ == '__main__':
    unittest.main()
