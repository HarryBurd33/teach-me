"""Focused constructor checks for whole-record draft merging, Python3.9+."""
import argparse
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SKILL = Path(os.environ.get('TEACH_ME_SKILL', Path(__file__).resolve().parents[1] / 'candidate/teach-me')).resolve()
sys.path.insert(0, str(SKILL/'scripts'))
import draft_merge as merge


def node(ident, **extra):
    return dict(id=ident,name=ident,statement='Claim '+ident,aliases=[],createdAt='',provenance=[],**extra)


def graph():
    a=node('a');a.update(aliases=['old alias'],createdAt='2024',provenance=[{'chatId':'source','messageId':'m1'}])
    return {'format':'teach-me-learning-v1','source_files':[],'sessions':[],
            'nodes':[a,node('b'),node('c')],
            'chains':[{'id':'joint','premises':['a','b'],'conclusion':'c','createdAt':'2024','provenance':[{'chatId':'s','messageId':'c1'}]}],
            'warnings':['Retained original warning']}


class DraftMerge(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.base=self.root/'base.json';self.left=self.root/'left.json';self.right=self.root/'right.json'
        self.plan=self.root/'plan.json';self.decisions=self.root/'decisions.json';self.out=self.root/'new-draft.json'
        self.graph=graph();self.write(self.base,self.graph)
        self.left_patch=self.empty();self.right_patch=self.empty();self.save_branches()
    def empty(self):
        return {'version':1,'delete_nodes':[],'delete_chains':[],'upsert_nodes':[],'upsert_chains':[]}
    def write(self,path,value):
        path.write_bytes(merge.encoded(value))
    def sha(self,path):return hashlib.sha256(path.read_bytes()).hexdigest()
    def save_branches(self):
        for path,value in ((self.left,self.left_patch),(self.right,self.right_patch)):
            self.write(path,{'version':1,'base_sha256':self.sha(self.base),'patch':value})
    def args(self,approve=True):
        return argparse.Namespace(base=self.base,left=self.left,right=self.right,plan=self.plan,
              expected_plan_sha256=self.sha(self.plan),decisions=self.decisions,
              expected_decisions_sha256=self.sha(self.decisions),output=self.out,approve=approve)
    def make_plan(self):
        result=merge.plan(argparse.Namespace(base=self.base,left=self.left,right=self.right,output=self.plan))
        self.value=json.loads(self.plan.read_bytes());self.assertEqual(result['plan_sha256'],self.sha(self.plan))
        return self.value
    def choices(self,side='base'):
        self.write(self.decisions,{'version':1,'plan_sha256':self.sha(self.plan),'choices':[
            {'kind':c['kind'],'id':c['id'],'choose':side} for c in self.value['conflicts']]})
    def apply(self):
        result=merge.apply(self.args());self.assertEqual(result['draft_sha256'],self.sha(self.out))
        return json.loads(self.out.read_bytes())
    def revised(self,ident='a',**updates):
        result=copy.deepcopy(next(x for x in self.graph['nodes'] if x['id']==ident));result.update(updates);return result
    def refusal(self,args=None):
        with self.assertRaises((merge.data.DataError,OSError)):
            merge.apply(args or self.args())
        self.assertFalse(self.out.exists())
    def conflict(self):
        self.left_patch['upsert_nodes']=[self.revised(name='Left')]
        self.right_patch['upsert_nodes']=[self.revised(name='Right')];self.save_branches();self.make_plan();self.choices('left')
    def test_grammar_python39(self):
        ast.parse((SKILL/'scripts/draft_merge.py').read_text(),feature_version=(3,9))
    def test_noop_roundtrip(self):
        p=self.make_plan();self.assertEqual(p['automatic'],{'nodes':[],'chains':[]});self.assertEqual(p['conflicts'],[])
        self.choices();self.assertEqual(self.apply()['patch'],self.empty())
    def test_independent_metadata_and_joint_argument(self):
        self.left_patch['upsert_nodes']=[self.revised(name='L')]
        chain=copy.deepcopy(self.graph['chains'][0]);chain['conclusion']='b';self.right_patch['upsert_chains']=[chain]
        self.save_branches();self.make_plan();self.assertEqual(self.value['conflicts'],[]);self.choices();value=self.apply()
        self.assertEqual(value['patch']['upsert_nodes'][0],self.revised(name='L'))
        self.assertEqual(value['patch']['upsert_chains'],[chain])
    def test_identical_edits_auto_and_deterministic(self):
        self.left_patch['upsert_nodes']=[self.revised(name='same')];self.right_patch=copy.deepcopy(self.left_patch);self.save_branches();self.make_plan()
        before=self.plan.read_bytes();second=self.root/'second.json';merge.plan(argparse.Namespace(base=self.base,left=self.left,right=self.right,output=second))
        self.assertEqual(before,second.read_bytes());self.assertEqual(self.value['conflicts'],[])
        self.assertNotIn(str(self.root),before.decode())
    def test_divergent_edit_left_choice(self):
        self.conflict();self.assertEqual(self.value['conflicts'][0]['reason'],'both-edited')
        self.assertEqual(self.apply()['patch']['upsert_nodes'][0]['name'],'Left')
    def test_divergent_edit_right_choice(self):
        self.conflict();self.choices('right');self.assertEqual(self.apply()['patch']['upsert_nodes'][0]['name'],'Right')
    def test_divergent_edit_base_choice(self):
        self.conflict();self.choices('base');self.assertEqual(self.apply()['patch'],self.empty())
    def test_delete_edit_conflict(self):
        self.graph['chains']=[];self.write(self.base,self.graph)
        self.left_patch['delete_nodes']=['a'];self.right_patch['upsert_nodes']=[self.revised(name='Right')];self.save_branches();self.make_plan();self.choices('left')
        self.assertIsNone(self.value['conflicts'][0]['left']);self.assertEqual(self.apply()['patch']['delete_nodes'],['a'])
    def test_divergent_newid_base_choice_drops(self):
        self.left_patch['upsert_nodes']=[node('new')];other=node('new');other['name']='different';self.right_patch['upsert_nodes']=[other]
        self.save_branches();self.make_plan();self.choices('base');self.assertEqual(self.apply()['patch'],self.empty())
    def test_dependency_promotes_node_and_chain(self):
        self.graph['chains']=[];self.write(self.base,self.graph);self.left_patch['delete_nodes']=['a']
        self.right_patch['upsert_chains']=[{'id':'new','premises':['a','b'],'conclusion':'c','createdAt':'','provenance':[]}]
        self.save_branches();self.make_plan();self.assertEqual({(x['kind'],x['id'],x['reason']) for x in self.value['conflicts']},{('node','a','dependency'),('chain','new','dependency')})
        self.choices('right');value=self.apply();self.assertEqual(value['patch']['delete_nodes'],[]);self.assertEqual(value['patch']['upsert_chains'][0]['premises'],['a','b'])
    def test_incompatible_dependency_choices_refuse(self):
        self.graph['chains']=[];self.write(self.base,self.graph);self.left_patch['delete_nodes']=['a']
        self.right_patch['upsert_chains']=[{'id':'new','premises':['a'],'conclusion':'c','createdAt':'','provenance':[]}]
        self.save_branches();self.make_plan();self.choices('right');v=json.loads(self.decisions.read_bytes());next(x for x in v['choices'] if x['kind']=='node')['choose']='left';self.write(self.decisions,v);self.refusal()
    def test_capacity_promotes_node_changes(self):
        self.graph['nodes']=[node('n'+str(i)) for i in range(254)];self.graph['chains']=[];self.write(self.base,self.graph)
        self.left_patch['upsert_nodes']=[node('l1'),node('l2')];self.right_patch['upsert_nodes']=[node('r1'),node('r2')]
        self.save_branches();self.make_plan();self.assertEqual(len(self.value['conflicts']),4);self.assertTrue(all(x['reason']=='capacity' for x in self.value['conflicts']));self.choices();self.assertEqual(self.apply()['patch'],self.empty())
    def test_capacity_promotes_chain_changes(self):
        self.graph['nodes']=[node('a')]+[node('n'+str(i)) for i in range(254)]
        self.graph['chains']=[{'id':'c'+str(i),'premises':['a'],'conclusion':'n'+str(i),'createdAt':'','provenance':[]} for i in range(254)];self.write(self.base,self.graph)
        def chain(ident,p):return {'id':ident,'premises':['a',p],'conclusion':'a','createdAt':'','provenance':[]}
        self.left_patch['upsert_chains']=[chain('l1','n0'),chain('l2','n1')];self.right_patch['upsert_chains']=[chain('r1','n2'),chain('r2','n3')]
        self.save_branches();self.make_plan();self.assertEqual(len(self.value['conflicts']),4);self.choices();self.apply()
    def test_byte_capacity_promotes_changed_records(self):
        self.left_patch['upsert_nodes']=[self.revised(name='x'*1100000)];self.right_patch['upsert_nodes']=[self.revised('b',name='y'*1100000)];self.save_branches();self.make_plan()
        self.assertEqual(len(self.value['conflicts']),2);self.choices();self.assertEqual(self.apply()['patch'],self.empty())
    def test_logical_duplicate_combination_refuses(self):
        self.graph['chains']=[];self.write(self.base,self.graph)
        def chain(ident,p):return {'id':ident,'premises':p,'conclusion':'c','createdAt':'','provenance':[]}
        self.left_patch['upsert_chains']=[chain('left',['a','b'])];self.right_patch['upsert_chains']=[chain('right',['b','a'])];self.save_branches();self.make_plan();self.choices();self.refusal()
    def test_missing_choice_refuses(self):
        self.conflict();v=json.loads(self.decisions.read_bytes());v['choices']=[];self.write(self.decisions,v);self.refusal()
    def test_duplicate_or_extra_choice_refuses(self):
        self.conflict();v=json.loads(self.decisions.read_bytes());v['choices']*=2;self.write(self.decisions,v);self.refusal()
        v['choices']=[{'kind':'node','id':'unknown','choose':'left'}];self.write(self.decisions,v);self.refusal()
    def test_unknown_choice_fields_and_arbitrary_value_refuse(self):
        self.conflict();v=json.loads(self.decisions.read_bytes());v['choices'][0]['record']=self.revised();self.write(self.decisions,v);self.refusal()
        del v['choices'][0]['record'];v['choices'][0]['choose']='automatic';self.write(self.decisions,v);self.refusal()
    def test_approval_and_expected_hashes(self):
        self.make_plan();self.choices();self.refusal(self.args(False))
        a=self.args();a.expected_plan_sha256='0'*64;self.refusal(a)
        a=self.args();a.expected_decisions_sha256='0'*64;self.refusal(a)
    def test_decisions_bind_exact_plan(self):
        self.make_plan();self.choices();v=json.loads(self.decisions.read_bytes());v['plan_sha256']='0'*64;self.write(self.decisions,v);self.refusal()
    def test_stale_branch_and_rehashed_tampered_plan_refuse(self):
        self.make_plan();self.choices();old=self.left.read_bytes();self.left.write_bytes(old+b' ');self.refusal();self.left.write_bytes(old)
        v=json.loads(self.plan.read_bytes());v['notice']='forged';self.write(self.plan,v);self.choices();self.refusal()
    def test_plan_and_decisions_versions_strict(self):
        self.make_plan();self.choices();raw=self.plan.read_bytes()
        for value in (True,1.0):
            v=json.loads(raw);v['version']=value;self.write(self.plan,v);self.choices();self.refusal()
        self.plan.write_bytes(raw);self.choices();v=json.loads(self.decisions.read_bytes());v['version']=1.0;self.write(self.decisions,v);self.refusal()
    def test_duplicate_json_members_refuse(self):
        self.make_plan();self.choices();self.decisions.write_text('{"version":1,"version":1,"plan_sha256":"'+self.sha(self.plan)+'","choices":[]}');self.refusal()
    def test_source_wrong_base_duplicate_or_float_version_refuse(self):
        raw=self.left.read_bytes()
        for value in (True,1.0):
            v=json.loads(raw);v['version']=value;self.write(self.left,v)
            with self.assertRaises(merge.data.DataError):merge.loaded_plan(argparse.Namespace(base=self.base,left=self.left,right=self.right))
        v=json.loads(raw);v['base_sha256']='0'*64;self.write(self.left,v)
        with self.assertRaises(merge.data.DataError):merge.loaded_plan(argparse.Namespace(base=self.base,left=self.left,right=self.right))
    def test_source_metadata_forgery_and_new_metadata_refuse(self):
        for field,value in [('aliases',[]),('createdAt',''),('provenance',[])]:
            self.left_patch['upsert_nodes']=[self.revised(**{field:value})];self.save_branches()
            with self.assertRaises(merge.data.DataError):merge.loaded_plan(argparse.Namespace(base=self.base,left=self.left,right=self.right))
        n=node('new');n['provenance']=[{'chatId':'fake','messageId':'x'}];self.left_patch['upsert_nodes']=[n];self.save_branches()
        with self.assertRaises(merge.data.DataError):merge.loaded_plan(argparse.Namespace(base=self.base,left=self.left,right=self.right))
    def test_source_session_and_incomplete_base_refuse(self):
        self.graph['chains'][0]['conclusion']='missing';self.write(self.base,self.graph);self.save_branches()
        with self.assertRaises(merge.data.DataError):merge.loaded_plan(argparse.Namespace(base=self.base,left=self.left,right=self.right))
    def test_source_and_decision_size_limit(self):
        self.left.write_bytes(b' '*(merge.editor.INPUT_LIMIT+1))
        with self.assertRaises(merge.data.DataError):merge.loaded_plan(argparse.Namespace(base=self.base,left=self.left,right=self.right))
        self.save_branches();self.make_plan();self.choices();a=self.args();self.decisions.write_bytes(b' '*(merge.editor.INPUT_LIMIT+1))
        self.refusal(a)
    def test_existing_output_and_input_preserved(self):
        self.make_plan();self.choices();before={p:p.read_bytes() for p in (self.base,self.left,self.right,self.plan,self.decisions)}
        self.out.write_bytes(b'FOREIGN')
        with self.assertRaises(FileExistsError):merge.apply(self.args())
        self.assertEqual(self.out.read_bytes(),b'FOREIGN');self.assertTrue(all(p.read_bytes()==b for p,b in before.items()))
    def test_foreign_publication_race_preserved(self):
        self.make_plan();self.choices()
        def foreign(staging,destination):
            Path(destination).write_bytes(b'RACER');raise FileExistsError('competitor')
        with patch.object(merge.data.os,'link',foreign),self.assertRaises(FileExistsError):merge.apply(self.args())
        self.assertEqual(self.out.read_bytes(),b'RACER')
    def test_all_five_sources_rechecked_after_staging(self):
        self.make_plan();self.choices();a=self.args();original=merge.data.tempfile.mkstemp
        for target in (self.base,self.left,self.right,self.plan,self.decisions):
            with self.subTest(source=target.name):
                raw=target.read_bytes()
                def changed(*args,**kwargs):
                    answer=original(*args,**kwargs);target.write_bytes(raw+b' ');return answer
                try:
                    with patch.object(merge.data.tempfile,'mkstemp',changed),self.assertRaises(merge.data.DataError):merge.apply(a)
                    self.assertFalse(self.out.exists())
                finally:target.write_bytes(raw)
    def test_fsync_failure_preserves_inputs(self):
        self.make_plan();self.choices();before={p:p.read_bytes() for p in (self.base,self.left,self.right,self.plan,self.decisions)}
        with patch.object(merge.data.os,'fsync',side_effect=OSError('diskfailure')),self.assertRaises(OSError):merge.apply(self.args())
        self.assertFalse(self.out.exists());self.assertTrue(all(p.read_bytes()==b for p,b in before.items()))
    def test_sensitive_and_symlink_paths_refuse(self):
        self.make_plan();self.choices();a=self.args();a.output=self.root/'.env-output';self.refusal(a)
        if hasattr(os,'symlink'):
            symlink=self.root/'symlink.json';symlink.symlink_to(self.left);a=self.args();a.left=symlink;self.refusal(a)
    def test_cli_end_to_end_existing_editor_check(self):
        self.left_patch['upsert_nodes']=[self.revised(name='CLI')];self.save_branches()
        def run(script,args):
            p=subprocess.run([sys.executable,'-B',str(SKILL/'scripts'/script),*map(str,args)],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr);return json.loads(p.stdout)
        result=run('draft_merge.py',['plan','--base',self.base,'--left',self.left,'--right',self.right,'--output',self.plan]);self.value=json.loads(self.plan.read_bytes());self.choices()
        run('draft_merge.py',['apply','--base',self.base,'--left',self.left,'--right',self.right,'--plan',self.plan,'--expected-plan-sha256',result['sha256'],'--decisions',self.decisions,'--expected-decisions-sha256',self.sha(self.decisions),'--output',self.out,'--approve'])
        check=run('graph_editor.py',['check','--base',self.base,'--draft',self.out]);self.assertEqual(check['draft_sha256'],self.sha(self.out))

if __name__=='__main__':unittest.main(verbosity=2)
