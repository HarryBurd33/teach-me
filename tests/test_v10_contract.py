"""Independent frozen v0.10 merge CLI contracts. Python3.9+ standard library."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(os.environ.get('TEACH_ME_SKILL', Path(__file__).resolve().parents[1] / 'teach-me')).resolve()
SCRIPT = ROOT/'scripts/draft_merge.py'
EDITOR = ROOT/'scripts/graph_editor.py'
LIMIT = 2*1024*1024

def sha(raw): return hashlib.sha256(raw).hexdigest()
def node(ident): return {'id':ident,'name':'Claim '+ident,'statement':ident+' holds','aliases':[],'createdAt':'','provenance':[]}
def chain(ident,premises,conclusion): return {'id':ident,'premises':premises,'conclusion':conclusion,'createdAt':'','provenance':[]}
def graph():
    nodes=[node(x) for x in ['a','b','c','d']]
    nodes[0].update(aliases=['historical-a'],createdAt='2025-01-02',provenance=[{'chatId':'synthetic','messageId':'original'}])
    return {'format':'teach-me-learning-v1','source_files':[],'sessions':[],'nodes':nodes,'chains':[chain('ab',['a','b'],'c')],'warnings':['Retain original warning']}
def empty_patch(): return {'version':1,'delete_nodes':[],'delete_chains':[],'upsert_nodes':[],'upsert_chains':[]}

class MergeContract(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()
        self.base=self.root/'base.json';self.left=self.root/'left.json';self.right=self.root/'right.json'
        self.plan=self.root/'plan.json';self.decisions=self.root/'decisions.json';self.out=self.root/'merged.json'
        self.g=graph();self.write(self.base,self.g);self.l=self.draft();self.r=self.draft();self.save_drafts()
    def write(self,path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    def draft(self):return {'version':1,'base_sha256':sha(self.base.read_bytes()),'patch':empty_patch()}
    def save_drafts(self):self.write(self.left,self.l);self.write(self.right,self.r)
    def edit(self,ident,**fields):
        value=copy.deepcopy(next(n for n in self.g['nodes'] if n['id']==ident));value.update(fields);return value
    def cli(self,*args,ok=True,script=None):
        r=subprocess.run([sys.executable,'-B',str(script or SCRIPT),*map(str,args)],capture_output=True,text=True,timeout=12)
        if ok:self.assertEqual(r.returncode,0,r.stdout+'\n'+r.stderr)
        else:self.assertNotEqual(r.returncode,0,'Unexpected acceptance: '+r.stdout)
        return r
    def planning(self,ok=True):return self.cli('plan','--base',self.base,'--left',self.left,'--right',self.right,'--output',self.plan,ok=ok)
    def plan_data(self):return json.loads(self.plan.read_text())
    def choices(self,values=None):
        if values is None:values=[{'kind':c['kind'],'id':c['id'],'choose':'left'} for c in self.plan_data()['conflicts']]
        value={'version':1,'plan_sha256':sha(self.plan.read_bytes()),'choices':values};self.write(self.decisions,value);return value
    def applying(self,ok=True,approve=True,plan_sha=None,decision_sha=None,output=None):
        args=['apply','--base',self.base,'--left',self.left,'--right',self.right,'--plan',self.plan,'--expected-plan-sha256',plan_sha or sha(self.plan.read_bytes()),'--decisions',self.decisions,'--expected-decisions-sha256',decision_sha or sha(self.decisions.read_bytes()),'--output',output or self.out]
        if approve:args.append('--approve')
        return self.cli(*args,ok=ok)
    def final_graph(self):
        merged=json.loads(self.out.read_text());self.assertEqual(set(merged),{'version','base_sha256','patch'});self.assertIs(type(merged['version']),int);self.assertEqual(merged['version'],1)
        self.assertEqual(merged['base_sha256'],sha(self.base.read_bytes()));dest=self.root/'applied.json'
        self.cli('check','--base',self.base,'--draft',self.out,script=EDITOR)
        self.cli('apply','--base',self.base,'--draft',self.out,'--expected-draft-sha256',sha(self.out.read_bytes()),'--output',dest,'--approve',script=EDITOR)
        return json.loads(dest.read_text())
    def conflict_setup(self):
        self.l['patch']['upsert_nodes']=[self.edit('a',statement='Left assertion')];self.r['patch']['upsert_nodes']=[self.edit('a',statement='Right assertion')];self.save_drafts();self.planning();self.choices()
    def snapshot(self):return {p.name:p.read_bytes() for p in [self.base,self.left,self.right,self.plan,self.decisions] if p.exists()}
    def assert_sources(self,before):
        for name,raw in before.items():self.assertEqual((self.root/name).read_bytes(),raw,name)
    def independent(self):
        self.l['patch']['upsert_nodes']=[self.edit('a',statement='Left claim')]
        c=copy.deepcopy(self.g['chains'][0]);c['conclusion']='d';self.r['patch']['upsert_chains']=[c];self.save_drafts()
    def module(self):
        sys.path.insert(0,str(ROOT/'scripts'));self.addCleanup(sys.path.pop,0)
        spec=importlib.util.spec_from_file_location('review_draft_merge',SCRIPT);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
    def apply_args(self):
        return ['apply','--base',str(self.base),'--left',str(self.left),'--right',str(self.right),'--plan',str(self.plan),'--expected-plan-sha256',sha(self.plan.read_bytes()),'--decisions',str(self.decisions),'--expected-decisions-sha256',sha(self.decisions.read_bytes()),'--output',str(self.out),'--approve']

    def test_01_independent_node_chain_metadata_and(self):
        self.independent();self.planning();self.assertEqual(self.plan_data()['conflicts'],[]);self.choices([]);before=self.snapshot();self.applying();actual=self.final_graph();self.assertEqual(actual['nodes'][0],self.l['patch']['upsert_nodes'][0]);self.assertEqual(actual['chains'][0]['premises'],['a','b']);self.assertEqual(actual['chains'][0]['conclusion'],'d');self.assert_sources(before)
    def test_02_identical_edits_automatic(self):
        change=self.edit('a',name='Same claim');self.l['patch']['upsert_nodes']=[change];self.r['patch']['upsert_nodes']=[copy.deepcopy(change)];self.save_drafts();self.planning();self.assertEqual(self.plan_data()['conflicts'],[]);self.choices([]);self.applying();self.assertEqual(self.final_graph()['nodes'][0],change)
    def test_03_plan_deterministic_exact_schema(self):
        self.independent();self.planning();raw=self.plan.read_bytes();p=self.plan_data();self.assertEqual(set(p),{'version','format','base_sha256','left_sha256','right_sha256','automatic','conflicts','notice'});self.assertEqual(p['format'],'teach-me-draft-merge-plan-v1');self.assertEqual(set(p['automatic']),{'nodes','chains'});self.assertEqual(p['left_sha256'],sha(self.left.read_bytes()));self.assertEqual(p['right_sha256'],sha(self.right.read_bytes()));self.assertNotIn(str(self.root),self.plan.read_text());self.plan=self.root/'again.json';self.planning();self.assertEqual(self.plan.read_bytes(),raw)
    def test_04_divergent_full_conflict_preview(self):
        self.conflict_setup();c=self.plan_data()['conflicts'][0];self.assertEqual(set(c),{'kind','id','reason','base','left','right'});self.assertEqual((c['kind'],c['id'],c['reason']),('node','a','both-edited'));self.assertEqual(c['base'],self.g['nodes'][0]);self.assertEqual(c['left'],self.l['patch']['upsert_nodes'][0]);self.assertEqual(c['right'],self.r['patch']['upsert_nodes'][0])
    def test_05_explicit_left(self):
        self.conflict_setup();self.applying();self.assertEqual(self.final_graph()['nodes'][0]['statement'],'Left assertion')
    def test_06_explicit_right(self):
        self.conflict_setup();self.choices([{'kind':'node','id':'a','choose':'right'}]);self.applying();self.assertEqual(self.final_graph()['nodes'][0]['statement'],'Right assertion')
    def test_07_explicit_base(self):
        self.conflict_setup();self.choices([{'kind':'node','id':'a','choose':'base'}]);self.applying();self.assertEqual(self.final_graph()['nodes'][0],self.g['nodes'][0])
    def test_08_delete_edit_and_absent_choice(self):
        self.l['patch']['delete_nodes']=['d'];self.r['patch']['upsert_nodes']=[self.edit('d',statement='Changed D')];self.save_drafts();self.planning();self.choices();self.assertEqual(self.plan_data()['conflicts'][0]['left'],None);self.applying();self.assertNotIn('d',[n['id'] for n in self.final_graph()['nodes']])
    def test_09_new_id_divergence_base_drops(self):
        self.l['patch']['upsert_nodes']=[dict(node('new'),statement='Left new')];self.r['patch']['upsert_nodes']=[dict(node('new'),statement='Right new')];self.save_drafts();self.planning();self.choices([{'kind':'node','id':'new','choose':'base'}]);self.applying();self.assertNotIn('new',[n['id'] for n in self.final_graph()['nodes']])
    def test_10_dependency_promotes_node_and_chain(self):
        self.l['patch']['delete_nodes']=['d'];self.r['patch']['upsert_chains']=[chain('uses-d',['a','d'],'c')];self.save_drafts();self.planning();cs=self.plan_data()['conflicts'];self.assertTrue({('node','d'),('chain','uses-d')} <= {(c['kind'],c['id']) for c in cs});self.assertTrue(all(c['reason']=='dependency' for c in cs));self.choices([{'kind':c['kind'],'id':c['id'],'choose':'right'} for c in cs]);self.applying();self.assertEqual(len(self.final_graph()['chains']),2)
    def test_11_invalid_dependency_choice_refused(self):
        self.l['patch']['delete_nodes']=['d'];self.r['patch']['upsert_chains']=[chain('uses-d',['d'],'c')];self.save_drafts();self.planning();self.choices([{'kind':c['kind'],'id':c['id'],'choose':'left' if c['kind']=='node' else 'right'} for c in self.plan_data()['conflicts']]);before=self.snapshot();self.applying(ok=False);self.assertFalse(self.out.exists());self.assert_sources(before)
    def test_12_capacity_promotes_changes(self):
        self.g['nodes']=[node('n'+str(i)) for i in range(255)];self.g['chains']=[];self.write(self.base,self.g);self.l=self.draft();self.r=self.draft();self.l['patch']['upsert_nodes']=[node('left-new')];self.r['patch']['upsert_nodes']=[node('right-new')];self.save_drafts();self.planning();cs=self.plan_data()['conflicts'];self.assertTrue({'left-new','right-new'} <= {c['id'] for c in cs if c['kind']=='node'});self.assertTrue(all(c['reason']=='capacity' for c in cs));self.choices([{'kind':c['kind'],'id':c['id'],'choose':'base'} for c in cs]);self.applying();self.assertEqual(len(self.final_graph()['nodes']),255)
    def test_13_incompatible_capacity_choices_refused(self):
        self.g['nodes']=[node('n'+str(i)) for i in range(255)];self.g['chains']=[];self.write(self.base,self.g);self.l=self.draft();self.r=self.draft();self.l['patch']['upsert_nodes']=[node('left-new')];self.r['patch']['upsert_nodes']=[node('right-new')];self.save_drafts();self.planning();self.choices([{'kind':c['kind'],'id':c['id'],'choose':'left' if c['id']=='left-new' else 'right'} for c in self.plan_data()['conflicts']]);self.applying(ok=False);self.assertFalse(self.out.exists())
    def test_14_missing_choices_refused(self):
        self.conflict_setup();self.choices([]);self.applying(ok=False);self.assertFalse(self.out.exists())
    def test_15_extra_choice_refused(self):
        self.planning();self.choices([{'kind':'node','id':'a','choose':'base'}]);self.applying(ok=False);self.assertFalse(self.out.exists())
    def test_16_duplicate_choice_refused(self):
        self.conflict_setup();c={'kind':'node','id':'a','choose':'left'};self.choices([c,c]);self.applying(ok=False)
    def test_17_unknown_decision_fields_and_choice(self):
        self.conflict_setup();d=self.choices();d['choices'][0]['choose']='invent';self.write(self.decisions,d);self.applying(ok=False);d=self.choices();d['choices'][0]['value']=node('a');self.write(self.decisions,d);self.applying(ok=False)
    def test_18_approve_required(self):
        self.planning();self.choices([]);self.applying(ok=False,approve=False);self.assertFalse(self.out.exists())
    def test_19_wrong_plan_review_hash(self):
        self.planning();self.choices([]);self.applying(ok=False,plan_sha='0'*64);self.assertFalse(self.out.exists())
    def test_20_wrong_decision_review_hash(self):
        self.planning();self.choices([]);self.applying(ok=False,decision_sha='0'*64);self.assertFalse(self.out.exists())
    def test_21_decision_bound_plan_hash(self):
        self.planning();d=self.choices([]);d['plan_sha256']='0'*64;self.write(self.decisions,d);self.applying(ok=False)
    def test_22_plan_tamper_recomputed_even_rehashed(self):
        self.independent();self.planning();p=self.plan_data();p['notice']='Tampered notice';self.write(self.plan,p);self.choices([]);self.applying(ok=False);self.assertFalse(self.out.exists())
    def test_23_changed_base_bytes_refused(self):
        self.planning();self.choices([]);self.base.write_bytes(self.base.read_bytes()+b' ');self.applying(ok=False)
    def test_24_changed_left_bytes_refused(self):
        self.planning();self.choices([]);self.left.write_bytes(self.left.read_bytes()+b' ');self.applying(ok=False)
    def test_25_changed_right_bytes_refused(self):
        self.planning();self.choices([]);self.right.write_bytes(self.right.read_bytes()+b' ');self.applying(ok=False)
    def test_26_wrong_branch_base_refused(self):
        self.l['base_sha256']='0'*64;self.save_drafts();self.planning(ok=False);self.assertFalse(self.plan.exists())
    def test_27_duplicate_json_members(self):
        self.left.write_text(self.left.read_text().replace('"version": 1,','"version": 1, "version": 1,',1));self.planning(ok=False)
    def test_28_unknown_draft_and_patch_fields(self):
        self.l['extra']=1;self.save_drafts();self.planning(ok=False);del self.l['extra'];self.l['patch']['extra']=1;self.save_drafts();self.planning(ok=False)
    def test_29_bool_float_versions(self):
        for value in [True,1.0]:
            self.l=self.draft();self.l['version']=value;self.save_drafts();self.planning(ok=False)
    def test_30_metadata_forgery_refused(self):
        for field,value in [('aliases',['forged']),('createdAt','now'),('provenance',[])]:
            self.l=self.draft();self.l['patch']['upsert_nodes']=[self.edit('a',**{field:value})];self.save_drafts();self.planning(ok=False)
    def test_31_new_record_blank_metadata_required(self):
        self.l['patch']['upsert_nodes']=[dict(node('new'),createdAt='now')];self.save_drafts();self.planning(ok=False)
    def test_32_sessions_and_incomplete_base_refused(self):
        self.g['sessions']=[{'id':'s','title':'x','kind':'quiz','events':[]}];self.write(self.base,self.g);self.l=self.draft();self.r=self.draft();self.save_drafts();self.planning(ok=False)
        self.g=graph();self.g['chains'][0]['conclusion']='missing';self.write(self.base,self.g);self.l=self.draft();self.r=self.draft();self.save_drafts();self.planning(ok=False)
    def test_33_source_limit(self):
        self.left.write_bytes(b' '*(LIMIT+1));self.planning(ok=False);self.assertFalse(self.plan.exists())
    def test_34_decisions_limit_and_version(self):
        self.planning();self.choices([]);self.decisions.write_bytes(b' '*(LIMIT+1));self.applying(ok=False)
        d=self.choices([]);d['version']=True;self.write(self.decisions,d);self.applying(ok=False)
    def test_35_existing_outputs_preserved(self):
        self.plan.write_bytes(b'FOREIGN PLAN');self.planning(ok=False);self.assertEqual(self.plan.read_bytes(),b'FOREIGN PLAN');self.plan.unlink();self.planning();self.choices([]);self.out.write_bytes(b'FOREIGN DRAFT');self.applying(ok=False);self.assertEqual(self.out.read_bytes(),b'FOREIGN DRAFT')
    def test_36_symlink_sensitive_traversal_refused(self):
        link=self.root/'linked.json';link.symlink_to(self.base);self.base=link;self.planning(ok=False)
        self.base=self.root/'base.json';self.left=self.root/'auth.json';self.write(self.left,self.l);self.planning(ok=False)
        self.left=self.root/'left.json';self.base=self.root/'..'/self.root.name/'base.json';self.planning(ok=False)
    def test_37_duplicate_logical_arguments_composed_refused(self):
        self.l['patch']['upsert_chains']=[chain('new-left',['a','b'],'d')];self.r['patch']['upsert_chains']=[chain('new-right',['b','a'],'d')];self.save_drafts();self.planning();self.choices();self.applying(ok=False);self.assertFalse(self.out.exists())
    def test_38_all_five_sources_rechecked(self):
        self.planning();self.choices([]);m=self.module();original=m.data.tempfile.mkstemp
        for target in [self.base,self.left,self.right,self.plan,self.decisions]:
            raw=target.read_bytes()
            def changed(*args,**kwargs):
                value=original(*args,**kwargs);target.write_bytes(raw+b' ');return value
            with patch.object(m.data.tempfile,'mkstemp',changed):self.assertNotEqual(m.main(self.apply_args()),0)
            target.write_bytes(raw);self.assertFalse(self.out.exists())
    def test_39_foreign_destination_race_preserved(self):
        self.planning();self.choices([]);m=self.module()
        def race(staged,destination):Path(destination).write_bytes(b'FOREIGN RACE');raise FileExistsError('other writer')
        with patch.object(m.data.os,'link',race):self.assertNotEqual(m.main(self.apply_args()),0)
        self.assertEqual(self.out.read_bytes(),b'FOREIGN RACE')
    def test_40_publication_io_failure_no_output(self):
        self.planning();self.choices([]);m=self.module();before=self.snapshot()
        with patch.object(m.data.os,'fsync',side_effect=OSError('injected storage failure')):self.assertNotEqual(m.main(self.apply_args()),0)
        self.assertFalse(self.out.exists());self.assert_sources(before)

if __name__=='__main__':unittest.main(verbosity=2)
