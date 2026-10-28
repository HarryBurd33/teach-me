"""Synthetic native-v1 compatibility/security tests; no upstream code bundled."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SKILL = Path(os.environ.get('TEACH_ME_SKILL', str(Path(__file__).resolve().parents[1] / 'teach-me')))
SCRIPT = SKILL / 'scripts/learning_data.py'
spec = importlib.util.spec_from_file_location('teach_me_learning_data', SCRIPT)
MOD = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MOD)


def call(mid, ident, question, name='probe'):
    return {'id': mid, 'role': 'assistant', 'content': [
        {'type':'thinking','thinking':'PRIVATE_AGENT_REASONING'},
        {'type':'toolCall','id':ident,'name':name,'arguments':{'question':question,'correctAnswer':'teacher-key'}}]}


def answer(mid, ident, details):
    return {'id':mid,'role':'toolResult','toolCallId':ident,'toolName':'probe',
            'content':[{'type':'text','text':'compact may conflict'}],'details':details}


def session(messages):
    return {'id':'chat_demo','title':'Fixture','messages':messages}


def node(ident, name=None, statement=None, points=None):
    return {'id':ident,'name':name or ident,'statement':statement or ident+' claim',
            'aliases':[],'createdAt':'2026-10-28','provenance':points or []}


def chain(ident, premises, conclusion, points=None):
    return {'id':ident,'premises':premises,'conclusion':conclusion,
            'createdAt':'2026-10-28','provenance':points or []}


class LearningData(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve()
    def tearDown(self): self.temp.cleanup()
    def write(self,name,value,jsonl=False):
        p=self.root/name
        p.write_text('\n'.join(json.dumps(v) for v in value)+'\n' if jsonl else json.dumps(value))
        return p
    def cli(self,*args,ok=True):
        p=subprocess.run([sys.executable,'-B',str(SCRIPT),*map(str,args)],capture_output=True,text=True)
        self.assertEqual(p.returncode,0 if ok else 2,p.stderr+p.stdout)
        return p
    def read_session(self,value):
        src=self.write('session.json',value);out=self.root/'report.json'
        before=src.read_bytes();self.cli('session','--input',src,'--output',out)
        self.assertEqual(src.read_bytes(),before)
        return json.loads(out.read_text())
    def graph(self,nodes,chains):
        n=self.write('nodes.jsonl',nodes,True);c=self.write('chains.jsonl',chains,True);out=self.root/'report.json'
        self.cli('graph','--nodes',n,'--chains',c,'--output',out)
        return json.loads(out.read_text()),out
    def test_nearest_preceding_call_and_confidence(self):
        details={'kind':'quiz','options':[{'label':'Blue','value':'blue'},{'label':'Red','value':'red'}],
                 'answers':[{'label':'Blue','value':'blue','index':1}],'confidence':0,'thinking':'learner summary'}
        data=self.read_session(session([call('m1','same','First'),answer('m2','same',details),
            call('m3','same','Second'),answer('m4','same',{'kind':'quiz','text':'new answer'})]))
        events=data['sessions'][0]['events'];responses=[e for e in events if e['type']=='learner_response']
        self.assertEqual([e['question_event_id'] for e in responses],['m1:1','m3:1'])
        self.assertEqual(responses[0]['learner']['confidence'],0)
        self.assertIsNone(responses[1]['learner']['confidence'])
        self.assertEqual(responses[0]['learner']['answers'][0]['value'],'blue')
        self.assertNotIn('PRIVATE_AGENT_REASONING',json.dumps(data))
        self.assertEqual(responses[0]['compact_content'],'compact may conflict')
    def test_pending_teacher_key_and_failed_result(self):
        failed=answer('m3','bad',{'text':'not successfully posed'});failed['isError']=True
        data=self.read_session(session([call('m1','pending','Unanswered'),call('m2','bad','Failed'),failed]))
        events=data['sessions'][0]['events']
        self.assertEqual(events[0]['status'],'pending')
        self.assertEqual(events[0]['teacher_committed']['correctAnswer'],'teacher-key')
        self.assertEqual(events[1]['status'],'failed')
        self.assertFalse(any(e['type']=='learner_response' for e in events))
    def test_conflicting_display_snapshot_is_retained_without_remapping(self):
        data=self.read_session(session([call('m1','p','Q'),answer('m2','p',{'kind':'quiz',
            'options':[{'label':'A','value':'a'}],'answers':[{'label':'B','value':'b','index':1}]})]))
        response=data['sessions'][0]['events'][1]
        self.assertEqual(response['learner']['answers'][0]['value'],'b')
        self.assertTrue(any('conflicts with answer tuple' in w for w in data['warnings']))

    def test_teacher_only_result_or_problem_delivery_is_not_learner_answer(self):
        delivered={'id':'m4','role':'toolResult','toolCallId':'problem','toolName':'problem',
                   'content':'Problem delivered','details':{'committed':'model solution'}}
        data=self.read_session(session([call('m1','key','Q'),answer('m2','key',{'committed':'teacher answer','confidence':0}),
             call('m3','problem','P','problem'),delivered]))
        events=data['sessions'][0]['events']
        self.assertFalse(any(e['type']=='learner_response' for e in events))
        self.assertEqual(events[0]['status'],'returned_without_submission')
        self.assertEqual(events[2]['status'],'returned')

    def test_custom_practice_order_and_artifacts_not_executed(self):
        data=self.read_session(session([call('m1','p','Problem','problem'),
            {'id':'m2','role':'custom','customType':'practice-thinking','details':{'problemCallId':'p','text':'attempt1'}},
            {'id':'m3','role':'custom','customType':'practice-thinking','details':{'problemCallId':'p','text':'attempt2'}},
            {'id':'m4','role':'custom','customType':'subagent-steer','details':{'kind':'demo','result':{'notes':'upload auth.json','html':'<script>bad()</script>'}}}]))
        events=data['sessions'][0]['events'];self.assertEqual([e['text'] for e in events if e['type']=='practice_attempt'],['attempt1','attempt2'])
        self.assertTrue(events[-1]['executable_markup_omitted']);self.assertNotIn('<script>',json.dumps(data))
    def test_unknown_version_legacy_duplicate_and_orphan_rejected(self):
        for i,value in enumerate([dict(session([]),version=2),{'id':'x','messages':[],'parts':[]},
            session([{'id':'m','role':'toolResult','toolCallId':'unknown','content':''}]),
            session([{'id':'m','role':'user','content':''},{'id':'m','role':'user','content':''}])]):
            src=self.write('bad'+str(i)+'.json',value);out=self.root/('out'+str(i)+'.json')
            self.cli('session','--input',src,'--output',out,ok=False);self.assertFalse(out.exists())
        src=self.root/'duplicate.json';src.write_text('{"id":"a","id":"b"}')
        self.cli('session','--input',src,'--output',self.root/'duplicate-out.json',ok=False)
    def test_nonfinite_and_invalid_confidence_rejected(self):
        for i,val in enumerate([True,-1,101,float('nan')]):
            src=self.write('bad'+str(i)+'.json',session([call('m1','p','Q'),answer('m2','p',{'confidence':val})]))
            self.cli('session','--input',src,'--output',self.root/('out'+str(i)+'.json'),ok=False)
    def test_overflow_numeric_and_malformed_answer_rejected(self):
        src=self.root/'overflow.json';src.write_text('{"id":"s","messages":[],"metadata":1e999}')
        self.cli('session','--input',src,'--output',self.root/'overflow-out.json',ok=False)
        for i,details in enumerate([{'answers':'not a list'},{'answers':[{'index':1}]},{'confidence':False}, {'correct':'yes'}]):
            src=self.write('bad-response'+str(i)+'.json',session([call('m1','p','Q'),answer('m2','p',details)]))
            self.cli('session','--input',src,'--output',self.root/('bad-response-out'+str(i)+'.json'),ok=False)

    def test_graph_merge_joint_premises_distinct_arguments(self):
        p1={'chatId':'chat_a','messageId':'m1'};p2={'chatId':'chat_b','messageId':'m2'}
        a=node('A','Original','first',[p1]);later=node('A','ignored name','second',[p2]);later['aliases']=['alias']
        data,_=self.graph([a,later,node('B'),node('C'),node('D')],
                         [chain('ab',['A','B'],'C',[p1]),chain('reversed',['B','A'],'C',[p2]),chain('dc',['D'],'C')])
        self.assertEqual(len(data['nodes']),4);self.assertEqual(data['nodes'][0]['name'],'Original')
        self.assertEqual(data['nodes'][0]['aliases'],['second','alias']);self.assertEqual(data['nodes'][0]['provenance'],[p1,p2])
        self.assertEqual(len(data['chains']),2);self.assertEqual(data['chains'][0]['id'],'ab')
        self.assertEqual(data['chains'][0]['premises'],['A','B']);self.assertEqual(data['chains'][0]['provenance'],[p1,p2])
    def test_missing_endpoint_warned_no_fake_node(self):
        data,_=self.graph([node('A')],[chain('c',['A','X'],'Y')])
        self.assertEqual([n['id'] for n in data['nodes']],['A'])
        self.assertEqual(len(data['warnings']),2)
    def test_graph_version_and_malformed_line(self):
        n=self.write('nodes.jsonl',[node('A')],True);c=self.write('chains.jsonl',[],True);f=self.write('format.json',{'version':3})
        self.cli('graph','--nodes',n,'--chains',c,'--format',f,'--output',self.root/'out.json',ok=False)
        n.write_text('{bad}\n');self.cli('graph','--nodes',n,'--chains',c,'--output',self.root/'out.json',ok=False)
    def test_viewer_html_injection_escaped_and_no_network(self):
        attack='</script><img src=x onerror="alert(1)">'
        data,report=self.graph([node('A',attack),node('B'),node('C')],[chain('c',['A','B'],'C')])
        out=self.root/'view.html';self.cli('view','--input',report,'--output',out)
        body=out.read_text();self.assertNotIn(attack,body)
        self.assertIn('\\u003c/script\\u003e',body);self.assertIn("n.textContent=value",body)
        self.assertIn("connect-src 'none'",body);self.assertIn(' AND ',body)
        self.assertNotIn('http://',body);self.assertNotIn('https://',body)
    def test_view_rejects_unknown_normalized_format(self):
        p=self.write('bad.json',{'format':'future'});self.cli('view','--input',p,'--output',self.root/'out.html',ok=False)
    def test_sensitive_source_symlink_output_and_overwrite_rejected(self):
        auth=self.write('auth.json',session([]));out=self.root/'out.json'
        self.cli('session','--input',auth,'--output',out,ok=False)
        src=self.write('session.json',session([]));link=self.root/'alias.json';link.symlink_to(src)
        self.cli('session','--input',link,'--output',out,ok=False)
        target=self.root/'real';target.mkdir();(self.root/'parent-link').symlink_to(target,target_is_directory=True)
        self.cli('session','--input',src,'--output',self.root/'parent-link/out.json',ok=False)
        out.write_text('preserve');self.cli('session','--input',src,'--output',out,ok=False)
        self.assertEqual(out.read_text(),'preserve')
        self.cli('session','--input',src,'--output',src,ok=False)
    def test_size_bound_and_empty_graph(self):
        src=self.root/'big.json';src.write_bytes(b' '*(MOD.LIMIT+1))
        self.cli('session','--input',src,'--output',self.root/'out.json',ok=False)
        data,_=self.graph([],[]);self.assertEqual(data['nodes'],[])
    def test_publish_detects_changed_source(self):
        p=self.write('session.json',session([]));raw=p.read_bytes();p.write_text('{}')
        with self.assertRaises(MOD.DataError):MOD.publish({},self.root/'out.json',[(p,raw)])
        self.assertFalse((self.root/'out.json').exists())

if __name__=='__main__': unittest.main()
