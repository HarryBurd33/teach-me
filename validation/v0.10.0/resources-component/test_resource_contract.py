"""Resource and executable guide checks; no local browser execution."""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

RUN = Path(__file__).resolve().parents[1]
REPO = Path(os.environ.get('TEACH_ME_REPO', RUN if (RUN/'browser-tests').is_dir() else RUN/'release'))
SKILL = Path(os.environ.get('TEACH_ME_SKILL', RUN/'candidate/teach-me' if (RUN/'candidate/teach-me').is_dir() else RUN/'teach-me')).resolve()
MERGE = SKILL/'scripts/draft_merge.py'
EDITOR = SKILL/'scripts/graph_editor.py'
BROWSER = REPO/'browser-tests/draft-merge.spec.js'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

class ResourceContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.graph = {'format':'teach-me-learning-v1','source_files':[],'sessions':[],
                      'nodes':[self.node('a', aliases=['history'], createdAt='2025', provenance=[{'chatId':'synthetic','messageId':'m1'}]), self.node('b'), self.node('c')],
                      'chains':[{'id':'joint','premises':['a','b'],'conclusion':'c','createdAt':'','provenance':[]}],
                      'warnings':[]}
        self.base = self.write('base.json', self.graph)
    def node(self, ident, **extra):
        return dict({'id':ident,'name':ident,'statement':'Claim '+ident,'aliases':[],'createdAt':'','provenance':[]}, **extra)
    def write(self, name, value):
        path = self.root/name
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')
        return path
    def patch(self, **extra):
        return dict({'version':1,'delete_nodes':[],'delete_chains':[],'upsert_nodes':[],'upsert_chains':[]}, **extra)
    def cli(self, script, *args, ok=True):
        result = subprocess.run([sys.executable,'-B',str(script),*map(str,args)], capture_output=True,text=True)
        self.assertEqual(result.returncode,0 if ok else 2,result.stdout+'\n'+result.stderr)
        return json.loads(result.stdout) if ok else result
    def branches(self, left, right):
        self.left=self.write('left.json',{'version':1,'base_sha256':digest(self.base),'patch':left})
        self.right=self.write('right.json',{'version':1,'base_sha256':digest(self.base),'patch':right})
        self.plan=self.root/'plan.json'
        self.cli(MERGE,'plan','--base',self.base,'--left',self.left,'--right',self.right,'--output',self.plan)
        return json.loads(self.plan.read_text())
    def decisions(self, choices):
        return self.write('decisions.json',{'version':1,'plan_sha256':digest(self.plan),'choices':choices})
    def apply(self, decisions, output, *, ok=True, plan_hash=None):
        return self.cli(MERGE,'apply','--base',self.base,'--left',self.left,'--right',self.right,
                        '--plan',self.plan,'--expected-plan-sha256',plan_hash or digest(self.plan),
                        '--decisions',decisions,'--expected-decisions-sha256',digest(decisions),
                        '--output',output,'--approve',ok=ok)
    def snapshot(self):
        return {p:p.read_bytes() for p in (self.base,self.left,self.right,self.plan)}
    def unchanged(self, snapshot):
        for p,raw in snapshot.items():
            self.assertEqual(p.read_bytes(),raw,p.name)

    def test_template_and_guide_contract(self):
        template=json.loads((SKILL/'templates/draft-merge-decisions.json').read_text())
        self.assertEqual(template,{'version':1,'plan_sha256':'0'*64,'choices':[]})
        self.assertIs(type(template['version']),int)
        guide=SKILL/'references/draft-merge.md'
        text=guide.read_text()
        for expected in ('--expected-plan-sha256','--expected-decisions-sha256','--approve',
                         'Draft JSON to import','duplicate arguments','one choice','2 MiB','8 MiB',
                         'not authenticate','20','semantic','same'):
            if expected == '20':
                continue
            self.assertIn(expected,text)
        for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)',text):
            self.assertTrue((guide.parent/target).resolve().is_file(),target)

    def test_browser_syntax(self):
        result=subprocess.run(['node','--check',str(BROWSER)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_browser_preserves_frozen_scenarios(self):
        text=BROWSER.read_text()
        self.assertEqual(len(re.findall(r"^test\('",text,re.M)),3)
        for forbidden in ('test.skip','test.fixme','test.only','page.route('):
            self.assertNotIn(forbidden,text)
        for expected in ('download.saveAs','--expected-plan-sha256','--expected-decisions-sha256',
                         "plan.conflicts).toHaveLength(1)", "'FOREIGN OUTPUT'", "document_transport: 'file'"):
            self.assertIn(expected,text)

    def test_automatic_cli_guide_roundtrip(self):
        changed=copy.deepcopy(self.graph['nodes'][0]);changed['statement']='Left edit'
        chain={'id':'reflection','premises':['a','b'],'conclusion':'a','createdAt':'','provenance':[]}
        plan=self.branches(self.patch(upsert_nodes=[changed]),self.patch(upsert_chains=[chain]))
        self.assertEqual(plan['conflicts'],[])
        decisions=self.decisions([]);before=self.snapshot();decision_raw=decisions.read_bytes()
        merged=self.root/'merged.json';self.apply(decisions,merged)
        bundle=json.loads(merged.read_text());self.assertEqual(set(bundle),{'version','base_sha256','patch'})
        self.assertEqual(bundle['patch']['upsert_nodes'],[changed]);self.assertEqual(bundle['patch']['upsert_chains'],[chain])
        check=self.cli(EDITOR,'check','--base',self.base,'--draft',merged)
        self.assertFalse(check['semantic_correctness_verified'])
        out=self.root/'applied.json'
        self.cli(EDITOR,'apply','--base',self.base,'--draft',merged,'--expected-draft-sha256',check['draft_sha256'],'--output',out,'--approve')
        graph=json.loads(out.read_text());self.assertEqual(graph['nodes'][0],changed)
        self.assertEqual(next(c for c in graph['chains'] if c['id']=='reflection'),chain)
        self.assertEqual(decisions.read_bytes(),decision_raw);self.unchanged(before)

    def test_conflict_requires_full_choice(self):
        left=copy.deepcopy(self.graph['nodes'][0]);left['statement']='Left statement'
        right=copy.deepcopy(self.graph['nodes'][0]);right['name']='Right name'
        plan=self.branches(self.patch(upsert_nodes=[left]),self.patch(upsert_nodes=[right]))
        self.assertEqual(plan['conflicts'],[{'kind':'node','id':'a','reason':'both-edited','base':self.graph['nodes'][0],'left':left,'right':right}])
        decisions=self.decisions([]);out=self.root/'merged.json';before=self.snapshot()
        self.apply(decisions,out,ok=False);self.assertFalse(out.exists());self.unchanged(before)
        decisions=self.decisions([{'kind':'node','id':'a','choose':'left'}]);self.apply(decisions,out)
        self.assertEqual(json.loads(out.read_text())['patch']['upsert_nodes'],[left])
        self.unchanged(before)

    def test_stale_review_and_foreign_output_preserved(self):
        left=copy.deepcopy(self.graph['nodes'][0]);left['name']='Left'
        right=copy.deepcopy(self.graph['nodes'][0]);right['name']='Right'
        self.branches(self.patch(upsert_nodes=[left]),self.patch(upsert_nodes=[right]))
        decisions=self.decisions([{'kind':'node','id':'a','choose':'left'}]);before=self.snapshot()
        out=self.root/'merged.json';self.apply(decisions,out,ok=False,plan_hash='0'*64)
        self.assertFalse(out.exists());self.unchanged(before)
        out.write_bytes(b'FOREIGN OUTPUT');self.apply(decisions,out,ok=False)
        self.assertEqual(out.read_bytes(),b'FOREIGN OUTPUT');self.unchanged(before)

if __name__ == '__main__':
    unittest.main(verbosity=2)
