"""Independent v0.4 checks frozen before candidate source inspection."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

SKILL = Path(os.environ.get('TEACH_ME_SKILL', str(Path(__file__).resolve().parents[1]/'teach-me')))
SCRIPTS = SKILL/'scripts'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class V4Contract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, script, *args, expected=0):
        p = subprocess.run([sys.executable, '-B', str(SCRIPTS/script), *map(str,args)], capture_output=True, text=True, timeout=15)
        if expected == 0:
            self.assertEqual(p.returncode, 0, p.stderr+p.stdout)
        else:
            self.assertNotEqual(p.returncode, 0, p.stderr+p.stdout)
        return json.loads(p.stdout) if p.returncode == 0 and p.stdout else p

    def write_json(self, name, value):
        p=self.root/name;p.write_text(json.dumps(value,ensure_ascii=False));return p

    def graph_fixture(self):
        source=self.root/'reasoning.txt'
        source.write_text('🙂 A holds.\nB holds.\nTogether A and B support C.\nD independently supports C.\n',encoding='utf-8')
        text=source.read_text(encoding='utf-8')
        def evidence(quote):
            start=text.index(quote);return {'start':start,'end':start+len(quote),'quote':quote}
        proposal={'version':1,'source_sha256':sha(source),'nodes':[
            {'id':'A','name':'A','statement':'A holds.','evidence':evidence('🙂 A holds.')},
            {'id':'B','name':'B','statement':'B holds.','evidence':evidence('B holds.')},
            {'id':'C','name':'C','statement':'C is supported jointly.','evidence':evidence('Together A and B support C.')}],
            'chains':[{'id':'joint','premises':['A','B'],'conclusion':'C','evidence':evidence('Together A and B support C.')}]}
        path=self.write_json('proposal.json',proposal)
        return source,path,proposal

    def apply_graph(self):
        source,proposal,value=self.graph_fixture();out=self.root/'graph.json';before=sha(source)
        self.cli('graph_workbench.py','check','--source',source,'--proposal',proposal)
        self.cli('graph_workbench.py','apply','--source',source,'--proposal',proposal,'--expected-proposal-sha256',sha(proposal),'--output',out,'--approve')
        self.assertEqual(sha(source),before)
        return source,proposal,out,json.loads(out.read_text())

    def test_unicode_zero_span_grouped_premises_and_source_preservation(self):
        source,proposal,out,data=self.apply_graph()
        self.assertEqual(data['format'],'teach-me-learning-v1')
        self.assertEqual({n['id'] for n in data['nodes']},{'A','B','C'})
        self.assertEqual(len(data['chains']),1)
        self.assertEqual(set(data['chains'][0]['premises']),{'A','B'})
        self.assertEqual(data['chains'][0]['conclusion'],'C')
        self.assertTrue(all(n['provenance'] for n in data['nodes']))
        self.assertEqual(data['sessions'],[])

    def test_wrong_quote_version_and_boolean_span_are_refused(self):
        source,path,proposal=self.graph_fixture()
        variants=[]
        bad=copy.deepcopy(proposal);bad['source_sha256']='0'*64;variants.append(bad)
        bad=copy.deepcopy(proposal);bad['nodes'][0]['evidence']['quote']='invented quote';variants.append(bad)
        bad=copy.deepcopy(proposal);bad['nodes'][0]['evidence']['start']=False;variants.append(bad)
        bad=copy.deepcopy(proposal);bad['nodes'][0]['evidence'].pop('end');variants.append(bad)
        bad=copy.deepcopy(proposal);bad['version']=2;variants.append(bad)
        before=sha(source)
        for i,value in enumerate(variants):
            p=self.write_json('bad%d.json'%i,value);out=self.root/('bad%d-out.json'%i)
            self.cli('graph_workbench.py','apply','--source',source,'--proposal',p,'--expected-proposal-sha256',sha(p),'--output',out,'--approve',expected=1)
            self.assertFalse(out.exists())
        self.assertEqual(sha(source),before)

    def test_stale_proposal_hash_and_changed_source_refused(self):
        source,p,value=self.graph_fixture();old=sha(p);value['nodes'][0]['name']='renamed';p.write_text(json.dumps(value));out=self.root/'stale.json'
        self.cli('graph_workbench.py','apply','--source',source,'--proposal',p,'--expected-proposal-sha256',old,'--output',out,'--approve',expected=1)
        self.assertFalse(out.exists())
        source.write_text(source.read_text()+'changed\n')
        self.cli('graph_workbench.py','check','--source',source,'--proposal',p,expected=1)

    def test_explicit_edit_is_new_safe_graph_and_stale_or_dangling_edits_refused(self):
        source,proposal,base,data=self.apply_graph();node=copy.deepcopy(data['nodes'][1]);node['name']='</script><img src=x onerror="alert(1)">'
        patch={'version':1,'delete_nodes':[],'delete_chains':[],'upsert_nodes':[node],'upsert_chains':[]};p=self.write_json('edit.json',patch);out=self.root/'edited.json';basehash=sha(base)
        self.cli('graph_workbench.py','edit','--base',base,'--patch',p,'--expected-base-sha256',basehash,'--expected-patch-sha256',sha(p),'--output',out,'--approve')
        self.assertEqual(sha(base),basehash)
        html=self.root/'map.html';self.cli('learning_data.py','view','--input',out,'--output',html)
        self.assertNotIn('</script><img',html.read_text());self.assertNotIn('<img src=x',html.read_text())
        for args in [('--expected-base-sha256','0'*64,'--expected-patch-sha256',sha(p)),('--expected-base-sha256',basehash,'--expected-patch-sha256','0'*64)]:
            bad=self.root/('stale-'+args[1][:2]+args[3][:2]+'.json');self.cli('graph_workbench.py','edit','--base',base,'--patch',p,*args,'--output',bad,'--approve',expected=1);self.assertFalse(bad.exists())
        patch['delete_nodes']=['A'];patch['upsert_nodes']=[];p.write_text(json.dumps(patch));bad=self.root/'dangling.json'
        self.cli('graph_workbench.py','edit','--base',base,'--patch',p,'--expected-base-sha256',basehash,'--expected-patch-sha256',sha(p),'--output',bad,'--approve',expected=1)
        self.assertFalse(bad.exists());self.assertEqual(sha(base),basehash)

    def test_graph_duplicate_ids_unknown_deletes_and_existing_output_preserved(self):
        source,p,value=self.graph_fixture();value['nodes'].append(copy.deepcopy(value['nodes'][0]));p.write_text(json.dumps(value));out=self.root/'duplicate.json'
        self.cli('graph_workbench.py','apply','--source',source,'--proposal',p,'--expected-proposal-sha256',sha(p),'--output',out,'--approve',expected=1);self.assertFalse(out.exists())
        source,p,base,data=self.apply_graph();patch=self.write_json('unknown.json',{'version':1,'delete_nodes':['absent'],'delete_chains':[],'upsert_nodes':[],'upsert_chains':[]})
        self.cli('graph_workbench.py','edit','--base',base,'--patch',patch,'--expected-base-sha256',sha(base),'--expected-patch-sha256',sha(patch),'--output',out,'--approve',expected=1)
        out.write_text('foreign result')
        self.cli('graph_workbench.py','apply','--source',source,'--proposal',p,'--expected-proposal-sha256',sha(p),'--output',out,'--approve',expected=1)
        self.assertEqual(out.read_text(),'foreign result')

    def journey(self, root=None):
        root=root or self.root
        self.cli('journey.py','init','--root',root,'--id','logic','--topic','Logic','--goal','Explain a changed argument')
        j=root/'learning/logic';(j/'practice.md').write_text('baseline practice\n');return j

    def archive(self,j,name):
        p=self.root/name;self.cli('transfer.py','pack','--journey',j,'--output',p);return p

    def branches(self):
        import shutil
        j=self.journey();base=self.archive(j,'base.zip')
        for arm in ['local','incoming']:
            parent=self.root/arm;parent.mkdir();target=parent/'learning/logic';target.parent.mkdir();shutil.copytree(j,target)
        return j,base,self.root/'local/learning/logic',self.root/'incoming/learning/logic'

    def test_snapshot_stale_head_tamper_and_fresh_restore(self):
        j=self.journey();store=self.root/'store';store.mkdir();self.cli('journey_versions.py','snapshot','--journey',j,'--store',store,'--expected-head','none')
        head=store/'HEAD.json';old=head.read_bytes();h=json.loads(old);rev=h['revision'];self.assertEqual(sha(store/(rev+'.zip')),rev)
        (j/'plan.md').write_text('changed plan\n')
        self.cli('journey_versions.py','snapshot','--journey',j,'--store',store,'--expected-head','none',expected=1);self.assertEqual(head.read_bytes(),old)
        receiving=self.root/'receiving';receiving.mkdir();self.cli('journey_versions.py','restore','--store',store,'--revision',rev,'--root',receiving,'--id','logic')
        self.cli('journey_versions.py','restore','--store',store,'--revision',rev,'--root',receiving,'--id','logic',expected=1)
        archive=store/(rev+'.zip');archive.write_bytes(b'tampered')
        self.cli('journey_versions.py','status','--store',store,expected=1)

    def test_clean_merge_combines_only_independent_changes(self):
        j,base,local,incoming=self.branches();(local/'plan.md').write_text('local changed plan\n');(incoming/'sources.md').write_text('incoming sources\n')
        l=self.archive(local,'local.zip');i=self.archive(incoming,'incoming.zip');before={p.name:sha(p) for p in [base,l,i]};report=self.root/'compare.json';out=self.root/'merged.zip'
        self.cli('journey_versions.py','compare','--base',base,'--local',l,'--incoming',i,'--output',report)
        self.cli('journey_versions.py','merge','--base',base,'--local',l,'--incoming',i,'--output',out)
        with zipfile.ZipFile(out) as z:self.assertEqual(z.read('plan.md'),b'local changed plan\n');self.assertEqual(z.read('sources.md'),b'incoming sources\n')
        self.assertEqual({p.name:sha(p) for p in [base,l,i]},before)
        receiving=self.root/'receiving';receiving.mkdir();self.cli('transfer.py','unpack','--archive',out,'--root',receiving,'--id','logic')

    def test_progress_conflict_requires_exact_digest_bound_choices(self):
        j,base,local,incoming=self.branches()
        for path,stage in [(local,'local-stage'),(incoming,'incoming-stage')]:
            p=path/'progress.json';data=json.loads(p.read_text());data['current_stage']=stage;p.write_text(json.dumps(data))
        l=self.archive(local,'local.zip');i=self.archive(incoming,'incoming.zip');report=self.root/'compare.json';out=self.root/'merged.zip'
        self.cli('journey_versions.py','compare','--base',base,'--local',l,'--incoming',i,'--output',report);value=json.loads(report.read_text())
        self.cli('journey_versions.py','merge','--base',base,'--local',l,'--incoming',i,'--output',out,expected=1);self.assertFalse(out.exists())
        choices={'version':1,'report_sha256':value['report_sha256'],'choices':{'progress.json':'local'}};resolution=self.write_json('choices.json',choices)
        self.cli('journey_versions.py','merge','--base',base,'--local',l,'--incoming',i,'--output',out,'--resolutions',resolution)
        with zipfile.ZipFile(out) as z:self.assertEqual(json.loads(z.read('progress.json'))['current_stage'],'local-stage')
        out=self.root/'stale.zip';choices['report_sha256']='0'*64;resolution.write_text(json.dumps(choices));self.cli('journey_versions.py','merge','--base',base,'--local',l,'--incoming',i,'--output',out,'--resolutions',resolution,expected=1);self.assertFalse(out.exists())
        choices['report_sha256']=value['report_sha256'];choices['choices']['plan.md']='incoming';resolution.write_text(json.dumps(choices));self.cli('journey_versions.py','merge','--base',base,'--local',l,'--incoming',i,'--output',out,'--resolutions',resolution,expected=1);self.assertFalse(out.exists())

    def test_delete_vs_edit_optional_file_is_a_conflict_not_silent_loss(self):
        j,base,local,incoming=self.branches();(local/'practice.md').unlink();(incoming/'practice.md').write_text('new practice evidence\n');l=self.archive(local,'local.zip');i=self.archive(incoming,'incoming.zip');report=self.root/'compare.json';out=self.root/'merged.zip'
        self.cli('journey_versions.py','compare','--base',base,'--local',l,'--incoming',i,'--output',report);value=json.loads(report.read_text());self.cli('journey_versions.py','merge','--base',base,'--local',l,'--incoming',i,'--output',out,expected=1);self.assertFalse(out.exists())
        resolution=self.write_json('choices.json',{'version':1,'report_sha256':value['report_sha256'],'choices':{'practice.md':'local'}})
        self.cli('journey_versions.py','merge','--base',base,'--local',l,'--incoming',i,'--output',out,'--resolutions',resolution)
        with zipfile.ZipFile(out) as z:self.assertNotIn('practice.md',z.namelist())


if __name__=='__main__':unittest.main(verbosity=2)
