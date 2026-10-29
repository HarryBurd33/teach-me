#!/usr/bin/env python3
"""Frozen independent v0.8 contract tests. Set TEACH_ME_ROOT to the target skill."""
import argparse
import copy
import hashlib
import html.parser
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(os.environ['TEACH_ME_ROOT']).resolve()
BASELINE = Path(__file__).resolve().parents[1] / 'baseline' / 'teach-me'
EDITOR = ROOT / 'scripts' / 'graph_editor.py'

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def node(nid, name=None):
    return {'id': nid, 'name': name or nid, 'statement': 'Claim ' + nid,
            'aliases': ['alias-' + nid], 'createdAt': '2024-01-02T03:04:05Z',
            'provenance': [{'chatId': 'source-chat', 'messageId': 'source-message'}]}

def base_graph():
    return {'format': 'teach-me-learning-v1',
            'source_files': [{'name': 'selected.txt', 'sha256': 'a' * 64}],
            'sessions': [], 'nodes': [node('p'), node('q'), node('r')],
            'chains': [{'id': 'c', 'premises': ['p', 'q'], 'conclusion': 'r',
                        'createdAt': '2024-01-02T03:04:05Z',
                        'provenance': [{'chatId': 'source-chat', 'messageId': 'chain-message'}]}],
            'warnings': ['Keep this history warning']}

def patch():
    return {'version': 1, 'delete_nodes': [], 'delete_chains': [],
            'upsert_nodes': [], 'upsert_chains': []}

class Tags(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(); self.tags=[]; self.in_script=False; self.scripts=[]; self.current=''
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs); self.tags.append((tag, attrs))
        if tag == 'script': self.in_script=True; self.current=''
    def handle_data(self, text):
        if self.in_script: self.current += text
    def handle_endtag(self, tag):
        if tag == 'script' and self.in_script:
            self.scripts.append(self.current); self.in_script=False

class Contract(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.dir=Path(self.tmp.name); self.base=self.dir/'base.json'; self.draft=self.dir/'draft.json'
        self.out=self.dir/'new.json'; self.graph=base_graph(); self.write(self.base,self.graph)
        self.bundle={'version':1,'base_sha256':digest(self.base.read_bytes()),'patch':patch()}
        self.save_draft()
    def write(self, path, value):
        path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def save_draft(self): self.write(self.draft,self.bundle)
    def cli(self,*args, ok=True, script=None):
        r=subprocess.run([sys.executable,str(script or EDITOR),*map(str,args)],capture_output=True,text=True)
        if ok: self.assertEqual(r.returncode,0,r.stderr+'\n'+r.stdout)
        else: self.assertNotEqual(r.returncode,0,'unexpected acceptance: '+r.stdout)
        return r
    def check(self,ok=True): return self.cli('check','--base',self.base,'--draft',self.draft,ok=ok)
    def apply(self, ok=True, approve=True, expected=None):
        args=['apply','--base',self.base,'--draft',self.draft,'--expected-draft-sha256',
              expected or digest(self.draft.read_bytes()),'--output',self.out]
        if approve: args.append('--approve')
        return self.cli(*args,ok=ok)
    def load_module(self):
        sys.path.insert(0,str(ROOT/'scripts')); self.addCleanup(sys.path.pop,0)
        for name in ('learning_data','graph_workbench','graph_editor'): sys.modules.pop(name,None)
        spec=importlib.util.spec_from_file_location('graph_editor',EDITOR)
        mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod
    def test_01_metadata_preserving_node_edit(self):
        edited=copy.deepcopy(self.graph['nodes'][0]); edited['name']='Edited title'; edited['statement']='Manual claim'
        self.bundle['patch']['upsert_nodes']=[edited]; self.save_draft()
        raw=self.base.read_bytes(); result=json.loads(self.check().stdout); self.apply()
        graph=json.loads(self.out.read_text()); self.assertEqual(self.base.read_bytes(),raw)
        self.assertEqual(graph['nodes'][0],edited); self.assertEqual(graph['chains'],self.graph['chains'])
        self.assertEqual(graph['source_files'],self.graph['source_files'])
        self.assertIn('Keep this history warning',graph['warnings'])
        self.assertIs(result.get('semantic_correctness_verified'),False)
    def test_02_joint_premise_new_chain_and_empty_timestamp(self):
        self.bundle['patch']['delete_chains']=['c']
        self.bundle['patch']['upsert_chains']=[{'id':'and','premises':['p','q'],'conclusion':'r','createdAt':'','provenance':[]}]
        self.save_draft(); self.check(); self.apply()
        graph=json.loads(self.out.read_text()); self.assertEqual(graph['chains'][0]['premises'],['p','q'])
        self.assertEqual(graph['chains'][0]['createdAt'],''); self.assertEqual(graph['chains'][0]['provenance'],[])
    def test_03_new_node_manual_metadata(self):
        n={'id':'new','name':'New','statement':'Manual','aliases':[],'createdAt':'','provenance':[]}
        self.bundle['patch']['upsert_nodes']=[n];self.save_draft();self.check();self.apply()
        self.assertIn(n,json.loads(self.out.read_text())['nodes'])
    def test_23_null_creation_timestamp_refused(self):
        n=node('new');n['createdAt']=None
        self.bundle['patch']['upsert_nodes']=[n];self.save_draft();self.check(False)
    def test_04_stale_base_hash(self):
        self.graph['warnings'].append('Changed');self.write(self.base,self.graph)
        self.check(False);self.apply(False);self.assertFalse(self.out.exists())
    def test_05_raw_draft_hash_binding(self):
        old=digest(self.draft.read_bytes());self.draft.write_bytes(self.draft.read_bytes()+b' ')
        self.check();self.apply(False,expected=old);self.assertFalse(self.out.exists())
    def test_06_approve_required(self):
        self.apply(False,approve=False);self.assertFalse(self.out.exists())
    def test_07_exact_bundle_keys(self):
        self.bundle['truth']=True;self.save_draft();self.check(False)
        del self.bundle['truth'];del self.bundle['base_sha256'];self.save_draft();self.check(False)
    def test_08_unknown_patch_key(self):
        self.bundle['patch']['mastered']=True;self.save_draft();self.check(False)
    def test_09_bool_and_unsupported_versions(self):
        for container in (self.bundle,self.bundle['patch']):
            for v in (True,False,2,'1'):
                with self.subTest(value=v):
                    container['version']=v;self.save_draft();self.check(False)
            container['version']=1
    def test_10_duplicate_json_members(self):
        raw=self.draft.read_text();self.draft.write_text(raw.replace('"version": 1','"version": 1, "version": 1',1))
        self.check(False)
    def test_11_invalid_ids_and_duplicate_premises(self):
        for nid in (' x','x\n','x'*129,''):
            n=node(nid);self.bundle['patch']['upsert_nodes']=[n];self.save_draft();self.check(False)
        self.bundle['patch']['upsert_nodes']=[]
        chain=copy.deepcopy(self.graph['chains'][0]);chain['premises']=['p','p']
        self.bundle['patch']['upsert_chains']=[chain];self.save_draft();self.check(False)
    def test_12_session_data_refused(self):
        self.graph['sessions']=[{'id':'s','title':'Private','kind':'teach','events':[]}];self.write(self.base,self.graph)
        self.bundle['base_sha256']=digest(self.base.read_bytes());self.save_draft()
        self.check(False);self.cli('render','--input',self.base,'--output',self.dir/'bad.html',ok=False)
    def test_13_missing_endpoint_and_referenced_delete(self):
        self.bundle['patch']['delete_nodes']=['p'];self.save_draft();self.check(False)
        self.bundle['patch']=patch();chain=copy.deepcopy(self.graph['chains'][0]);chain['conclusion']='absent'
        self.bundle['patch']['upsert_chains']=[chain];self.save_draft();self.check(False)
    def test_14_render_unresolved_then_repair(self):
        self.graph['chains'][0]['conclusion']='gap';self.write(self.base,self.graph)
        self.bundle['base_sha256']=digest(self.base.read_bytes());self.save_draft()
        self.cli('render','--input',self.base,'--output',self.dir/'repair.html');self.check(False)
        self.bundle['patch']['upsert_nodes']=[node('gap')];self.save_draft();self.check();self.apply()
    def test_15_record_limits(self):
        for field in ('nodes','chains'):
            g=base_graph()
            if field=='nodes': g[field]=[node('n'+str(i)) for i in range(257)]
            else: g[field]=[{'id':'c'+str(i),'premises':['p'],'conclusion':'r','createdAt':'','provenance':[]} for i in range(257)]
            self.write(self.base,g);self.cli('render','--input',self.base,'--output',self.dir/'bound.html',ok=False)
    def test_16_byte_limits(self):
        self.graph['warnings']=['z'*(2*1024*1024)];self.write(self.base,self.graph)
        self.cli('render','--input',self.base,'--output',self.dir/'large.html',ok=False)
        self.write(self.base,base_graph());self.bundle['base_sha256']=digest(self.base.read_bytes());self.save_draft()
        self.draft.write_bytes(self.draft.read_bytes()+b' '*(2*1024*1024));self.check(False)
    def test_17_existing_output_and_source_preserved(self):
        self.out.write_bytes(b'FOREIGN');self.apply(False);self.assertEqual(self.out.read_bytes(),b'FOREIGN')
        self.out=self.base;raw=self.base.read_bytes();self.apply(False);self.assertEqual(self.base.read_bytes(),raw)
    def test_18_foreign_publication_race(self):
        mod=self.load_module();original=mod.data.os.link
        def competing(source,destination):
            Path(destination).write_bytes(b'FOREIGN-RACE');raise FileExistsError('competitor')
        mod.data.os.link=competing
        try:
            args=argparse.Namespace(base=str(self.base),draft=str(self.draft),expected_draft_sha256=digest(self.draft.read_bytes()),output=str(self.out),approve=True)
            with self.assertRaises((OSError,mod.data.DataError)):mod.apply(args)
            self.assertEqual(self.out.read_bytes(),b'FOREIGN-RACE')
        finally:mod.data.os.link=original
    def test_19_sources_rechecked_before_publish(self):
        for target in (self.base,self.draft):
            with self.subTest(target=target.name):
                self.write(self.base,base_graph());self.bundle['base_sha256']=digest(self.base.read_bytes());self.save_draft()
                mod=self.load_module();original=mod.data.publish
                def mutate(*args,**kwargs):
                    target.write_bytes(target.read_bytes()+b' ');return original(*args,**kwargs)
                mod.data.publish=mutate
                try:
                    args=argparse.Namespace(base=str(self.base),draft=str(self.draft),expected_draft_sha256=digest(self.draft.read_bytes()),output=str(self.out),approve=True)
                    with self.assertRaises((OSError,mod.data.DataError)):mod.apply(args)
                    self.assertFalse(self.out.exists())
                finally:mod.data.publish=original
    def test_20_hostile_html_csp_and_assets(self):
        hostile='</script><script>globalThis.PWNED=true</script><img src=x onerror=alert(1)>'
        self.graph['nodes'][0]['name']=hostile;self.graph['nodes'][0]['statement']=hostile;self.write(self.base,self.graph)
        page=self.dir/'safe.html';self.cli('render','--input',self.base,'--output',page)
        raw=page.read_text();parsed=Tags();parsed.feed(raw)
        self.assertNotIn(hostile,raw);self.assertLessEqual(len(page.read_bytes()),32*1024*1024)
        csp=[attrs['content'] for tag,attrs in parsed.tags if tag=='meta' and attrs.get('http-equiv','').lower()=='content-security-policy']
        self.assertEqual(len(csp),1);policy=csp[0]
        for directive in ("default-src 'none'","object-src 'none'","base-uri 'none'",'sha256-'):self.assertIn(directive,policy)
        for bad in ('unsafe-eval','unsafe-inline','https:','http:'):self.assertNotIn(bad,policy)
        for tag,attrs in parsed.tags:
            if tag in ('script','link','iframe','img'):self.assertFalse(attrs.get('src') or attrs.get('href'))
        js=(ROOT/'assets'/'graph-editor.js').read_text()
        for bad in ('innerHTML','eval(','fetch(','XMLHttpRequest','localStorage','serviceWorker'):self.assertNotIn(bad,js)
        template=(ROOT/'assets'/'graph-editor.html').read_text()
        for marker in ('{{EDITOR_DATA}}','{{EDITOR_SCRIPT}}','{{EDITOR_STYLE}}','{{SCRIPT_HASH}}','{{STYLE_HASH}}'):self.assertEqual(template.count(marker),1)
    def test_21_old_cli_edit_unchanged(self):
        edited=copy.deepcopy(self.graph['nodes'][0]);edited['statement']='Changed old CLI'
        oldpatch=patch();oldpatch['upsert_nodes']=[edited];p=self.dir/'patch.json';self.write(p,oldpatch)
        results=[]
        for i,root in enumerate((BASELINE,ROOT)):
            out=self.dir/('old'+str(i)+'.json')
            self.cli('edit','--base',self.base,'--patch',p,'--expected-base-sha256',digest(self.base.read_bytes()),'--expected-patch-sha256',digest(p.read_bytes()),'--output',out,'--approve',script=root/'scripts'/'graph_workbench.py')
            results.append(json.loads(out.read_text()))
        self.assertEqual(*results)
    def test_22_shared_pure_helper(self):
        mod=self.load_module();self.assertTrue(callable(mod.workbench.edited_graph) if hasattr(mod,'workbench') else callable(__import__('graph_workbench').edited_graph))
        text=EDITOR.read_text();self.assertIn('edited_graph(',text)

if __name__=='__main__':unittest.main(verbosity=2)
