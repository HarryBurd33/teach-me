"""Held-out actual-process/HEAD activation checks frozen before source inspection."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

RUN=Path(__file__).resolve().parents[2]
SKILL=Path(os.environ.get('TEACH_ME_SKILL',str(RUN/'candidate/teach-me')))
SCRIPTS=SKILL/'scripts'

class FailurePaths(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve()
    def tearDown(self):self.temp.cleanup()
    def cli(self,name,*args,expected=0):
        p=subprocess.run([sys.executable,'-B',str(SCRIPTS/name),*map(str,args)],capture_output=True,text=True,timeout=15)
        if expected==0:self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        else:self.assertNotEqual(p.returncode,0,p.stdout+p.stderr)
        return p
    def setup_snapshot(self):
        self.cli('journey.py','init','--root',self.root,'--id','logic','--topic','Logic','--goal','Explain a changed case')
        j=self.root/'learning/logic';store=self.root/'store';store.mkdir()
        self.cli('journey_versions.py','snapshot','--journey',j,'--store',store,'--expected-head','none')
        return j,store,(store/'HEAD.json').read_bytes()
    def test_activation_failure_preserves_old_head_and_restore(self):
        j,store,old=self.setup_snapshot();rev=json.loads(old)['revision'];(j/'plan.md').write_text('new plan\n')
        code="""import os,sys,runpy
from pathlib import Path
script=Path(sys.argv[1]);sys.path.insert(0,str(script.parent));real=os.replace
def fail(source,target,*args,**kwargs):
    if Path(target).name=='HEAD.json':raise OSError('injected HEAD activation failure')
    return real(source,target,*args,**kwargs)
os.replace=fail
sys.argv=sys.argv[1:]
runpy.run_path(str(script),run_name='__main__')
"""
        p=subprocess.run([sys.executable,'-B','-c',code,str(SCRIPTS/'journey_versions.py'),'snapshot','--journey',str(j),'--store',str(store),'--expected-head',rev],capture_output=True,text=True,timeout=15)
        self.assertNotEqual(p.returncode,0,p.stdout+p.stderr);self.assertEqual((store/'HEAD.json').read_bytes(),old)
        receiving=self.root/'receiving';receiving.mkdir();self.cli('journey_versions.py','restore','--store',store,'--revision',rev,'--root',receiving,'--id','logic')
        self.assertNotEqual((receiving/'learning/logic/plan.md').read_bytes(),(j/'plan.md').read_bytes())
    def test_two_snapshot_writers_same_changed_head_one_transition(self):
        j,store,old=self.setup_snapshot();rev=json.loads(old)['revision'];(j/'plan.md').write_text('new plan for concurrent snapshot\n')
        cmd=[sys.executable,'-B',str(SCRIPTS/'journey_versions.py'),'snapshot','--journey',str(j),'--store',str(store),'--expected-head',rev]
        processes=[subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(2)]
        results=[]
        for p in processes:
            out,err=p.communicate(timeout=15);results.append((p.returncode,out,err))
        self.assertEqual(sum(code==0 for code,out,err in results),1,results)
        head=json.loads((store/'HEAD.json').read_text());self.assertNotEqual(head['revision'],rev)
        self.assertEqual(hashlib.sha256((store/(head['revision']+'.zip')).read_bytes()).hexdigest(),head['revision'])
    def test_newer_orphan_archive_does_not_replace_committed_head(self):
        j,store,old=self.setup_snapshot();rev=json.loads(old)['revision'];(j/'plan.md').write_text('orphan plan\n');archive=self.root/'orphan.zip'
        self.cli('transfer.py','pack','--journey',j,'--output',archive);digest=hashlib.sha256(archive.read_bytes()).hexdigest();shutil.copy2(archive,store/(digest+'.zip'))
        p=subprocess.run([sys.executable,'-B',str(SCRIPTS/'journey_versions.py'),'status','--store',str(store)],capture_output=True,text=True,timeout=15)
        self.assertEqual((store/'HEAD.json').read_bytes(),old)
        if p.returncode==0:
            self.assertIn(rev,p.stdout)
            data=json.loads(p.stdout)
            if 'revision' in data:self.assertEqual(data['revision'],rev)
    @unittest.skipUnless(os.name=='posix','actual SIGKILL fixture requires POSIX')
    def test_killed_report_writer_never_publishes_incomplete_final(self):
        source=self.root/'source.txt';source.write_text('synthetic source\n');before=source.read_bytes();out=self.root/'report.json';ready=self.root/'ready'
        code="""import importlib.util,sys,time
from pathlib import Path
spec=importlib.util.spec_from_file_location('killed_report',sys.argv[1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
source=Path(sys.argv[2]);out=Path(sys.argv[3]);ready=Path(sys.argv[4]);real=m.os.link
def pause(source,target,*args,**kwargs):
    ready.write_text('stage complete; final not linked')
    time.sleep(20)
    return real(source,target,*args,**kwargs)
m.os.link=pause
m.publish({'fixture':'complete JSON only'},out,[(source,source.read_bytes())])
"""
        process=subprocess.Popen([sys.executable,'-B','-c',code,str(SCRIPTS/'learning_data.py'),str(source),str(out),str(ready)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            until=time.monotonic()+4
            while not ready.exists() and process.poll() is None and time.monotonic()<until:time.sleep(.01)
            self.assertTrue(ready.exists(),'writer never reached pre-publication link gate')
            self.assertFalse(out.exists())
            process.send_signal(signal.SIGKILL);process.communicate(timeout=5)
            self.assertFalse(out.exists());self.assertEqual(source.read_bytes(),before)
        finally:
            if process.poll() is None:process.kill();process.communicate(timeout=5)

if __name__=='__main__':unittest.main(verbosity=2)
