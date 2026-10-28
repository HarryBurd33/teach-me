#!/usr/bin/env python3
"""Independent fixed-contract deterministic review. No learner stores touched."""
import base64, hashlib, json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent/'baseline/teach-me'
TARGET=Path(os.environ.get('TEACH_ME_REVIEW_TARGET', str(ROOT.parent/'candidate/teach-me'))).resolve()
RUN=ROOT/'runs'; RUN.mkdir(exist_ok=True)
LOG=[]
def sha(b): return hashlib.sha256(b).hexdigest()
def canonical(x): return (json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n').encode()
def content(p): return {x.name:sha(x.read_bytes()) for x in p.iterdir() if x.is_file()}
def run(script,*args,ok=0,base=False):
    argv=[sys.executable,str((BASE if base else TARGET)/'scripts'/script)]+list(map(str,args))
    r=subprocess.run(argv,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
    LOG.append({'argv':argv,'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
    if ok is not None and r.returncode!=ok: raise AssertionError('exit %s expected %s: %s'%(r.returncode,ok,r.stderr))
    try: value=json.loads(r.stdout)
    except ValueError: value=None
    return r,value
class Cases(unittest.TestCase):
 def setUp(self):
    self.d=Path(tempfile.mkdtemp(prefix='heldout-',dir=str(RUN)))
    self.ws=self.d/'workspace';self.ws.mkdir()
    run('journey.py','init','--root',self.ws,'--id','calculus-a','--topic','Calculus','--goal','Explain derivative using slope.',base=True)
    self.j=self.ws/'learning/calculus-a'
    self.h=self.d/'history';self.h.mkdir()
    self.s=self.d/'snapshots';self.s.mkdir()
    self.a=self.d/'archives';self.a.mkdir()
 def receipt(self,label='r',needs=False,journey=None):
    j=journey or self.j
    p=self.d/(label+'-packet.json'); dec=self.d/(label+'-decisions.json');r=self.d/(label+'-receipt.json')
    run('coherence_review.py','prepare','--journey',j,'--output',p,base=True)
    packet=json.loads(p.read_bytes())
    v={'version':1,'packet_sha256':packet['packet_sha256'],'reviewer_role':'other','decisions':[{'check_id':x['check_id'],'result':'needs_changes' if needs and i==0 else 'consistent','rationale':'Explicit evaluator fixture judgment '+str(i)} for i,x in enumerate(packet['checks'])]}
    dec.write_bytes(canonical(v))
    run('coherence_review.py','record','--journey',j,'--packet',p,'--decisions',dec,'--output',r,base=True)
    # Deliberately retain valid noncanonical receipt whitespace in H01.
    r.write_text('\n  '+json.dumps(json.loads(r.read_bytes()),indent=3)+'\n\n')
    return r
 def append(self,r,tip='none',store=None,ok=0):
    return run('review_history.py','append','--store',store or self.h,'--journey',self.j,'--receipt',r,'--expected-tip',tip,ok=ok)
 def entries(self,h=None):return sorted((h or self.h).glob('[0-9]*.json'))
 def snapshots(self):
    revisions=[]; tip='none'
    for i in range(4):
      (self.j/'plan.md').write_text('# Plan\n\nSnapshot fixture %s.\n'%i)
      _,v=run('journey_versions.py','snapshot','--store',self.s,'--journey',self.j,'--expected-head',tip,base=True)
      tip=v['revision']; revisions.append(tip)
    return revisions
 def plan(self,revs,path=None,ok=0):
    path=path or self.d/'retire.json'
    r,v=run('snapshot_maintenance.py','plan','--store',self.s,'--revisions',*revs,'--output',path,ok=ok)
    return path, json.loads(path.read_bytes()) if path.exists() and ok==0 else None
 def apply(self,p,v,archive=None,approved=True,expected=None,ok=0):
    args=['apply','--store',self.s,'--plan',p,'--archive-root',archive or self.a,'--expected-plan-sha256',expected or v['plan_sha256']]
    if approved:args.append('--approve')
    return run('snapshot_maintenance.py',*args,ok=ok)
 def test_H01_exact_history(self):
    r1=self.receipt('one');self.append(r1)
    one=self.entries()[0];b1=one.read_bytes();tip=sha(b1)
    self.assertEqual(one.name,'000001-'+tip+'.json');e1=json.loads(b1)
    self.assertEqual(b1,canonical(e1));self.assertEqual(set(e1),{'version','journey_id','sequence','previous','receipt_sha256','receipt_base64'})
    self.assertEqual(e1['sequence'],1);self.assertIsNone(e1['previous']);self.assertEqual(e1['receipt_sha256'],sha(r1.read_bytes()))
    r2=self.receipt('two',needs=True);self.append(r2,tip)
    es=self.entries();self.assertEqual(len(es),2);self.assertEqual(es[0].read_bytes(),b1)
    e2=json.loads(es[1].read_bytes());self.assertEqual(e2['previous'],tip);self.assertEqual(e2['sequence'],2)
    self.assertFalse(json.loads(base64.b64decode(e2['receipt_base64']))['resume_ready'])
    for entry,receipt in zip(es,[r1,r2]):
      out=self.d/(entry.stem+'-extracted.json')
      run('review_history.py','extract','--store',self.h,'--entry',sha(entry.read_bytes()),'--output',out)
      self.assertEqual(out.read_bytes(),receipt.read_bytes())
    _,s=run('review_history.py','status','--store',self.h)
    self.assertEqual(s['tip'],sha(es[-1].read_bytes()));self.assertEqual(s['sequence'],2);self.assertEqual(s['journey_id'],'calculus-a')
 def test_H02_stale_and_foreign(self):
    r=self.receipt();self.append(r);before=content(self.h);tip=sha(self.entries()[0].read_bytes())
    self.append(r,'none',ok=2);self.assertEqual(content(self.h),before)
    (self.j/'plan.md').write_text('# Edited after receipt\n')
    self.append(r,tip,ok=2);self.assertEqual(content(self.h),before)
    run('journey.py','init','--root',self.ws,'--id','algebra-b','--topic','Algebra','--goal','Solve linear equations.',base=True)
    foreign=self.receipt('foreign',journey=self.ws/'learning/algebra-b')
    self.append(foreign,tip,ok=2);self.assertEqual(content(self.h),before)
 def test_H03_corruption(self):
    r=self.receipt();self.append(r);original=self.entries()[0];obj=json.loads(original.read_bytes())
    mutations={'receipt_hash':lambda e:e.update(receipt_sha256='f'*64),'base64_invalid':lambda e:e.update(receipt_base64='!!!'),'base64_noncanonical':lambda e:e.update(receipt_base64=e['receipt_base64']+'\n'),'sequence_bool':lambda e:e.update(sequence=True),'sequence_gap':lambda e:e.update(sequence=2),'wrong_previous':lambda e:e.update(previous='a'*64)}
    for name,change in mutations.items():
      h=self.d/name;h.mkdir();e=dict(obj);change(e);raw=canonical(e)
      seq=e['sequence'] if type(e['sequence']) is int else 1
      (h/('%06d-%s.json'%(seq,sha(raw)))).write_bytes(raw)
      before=content(h);run('review_history.py','status','--store',h,ok=2);self.assertEqual(content(h),before)
    for name,kind in [('filename','filename'),('unknown','unknown'),('symlink','symlink')]:
      h=self.d/name;shutil.copytree(self.h,h)
      if kind=='filename':self.entries(h)[0].write_bytes(self.entries(h)[0].read_bytes()+b' ')
      elif kind=='unknown':(h/'notes.txt').write_text('must refuse')
      else:(h/'elsewhere').symlink_to(r)
      run('review_history.py','status','--store',h,ok=2)
 def test_H03_orphans_locks(self):
    r=self.receipt();orphan=self.h/'.teach-me-history-stage-orphan';orphan.write_text('bounded interruption bytes')
    _,v=run('review_history.py','status','--store',self.h)
    self.assertIn(orphan.name,json.dumps(v));before=content(self.h)
    self.append(r,ok=2);self.assertEqual(content(self.h),before)
    orphan.unlink();lock=self.h/'.teach-me-review-history.lock';lock.write_text('owned')
    before=content(self.h);self.append(r,ok=2);self.assertEqual(content(self.h),before)
 def test_H04_outputs_bounds(self):
    r=self.receipt();self.append(r);entry=self.entries()[0];tip=sha(entry.read_bytes())
    out=self.d/'existing.json';out.write_bytes(b'preserve sentinel\n')
    run('review_history.py','extract','--store',self.h,'--entry',tip,'--output',out,ok=2);self.assertEqual(out.read_bytes(),b'preserve sentinel\n')
    run('review_history.py','extract','--store',self.h,'--entry',tip,'--output',self.h/'illegal.json',ok=2);self.assertFalse((self.h/'illegal.json').exists())
    huge=self.d/'huge.json';huge.write_bytes(r.read_bytes()+b' '*(2*1024*1024));before=content(self.h)
    self.append(huge,tip,ok=2);self.assertEqual(content(self.h),before)
    entry.write_bytes(b' '*(3*1024*1024+1));run('review_history.py','status','--store',self.h,ok=2)
 def test_M01_selection_and_hashes(self):
    revs=self.snapshots();before=content(self.s)
    for i,selected in enumerate([[revs[3]],[revs[2]],[revs[0],revs[0]],['0'*64],[]]):
      self.plan(selected,self.d/('bad-%s.json'%i),ok=2);self.assertEqual(content(self.s),before)
    p,v=self.plan([revs[1],revs[0]])
    self.assertEqual(set(v),{'version','journey_id','store_sha256','head','protected','revisions','plan_sha256'})
    self.assertEqual(v['revisions'],sorted(revs[:2]));self.assertEqual(v['plan_sha256'],sha(canonical({k:x for k,x in v.items() if k!='plan_sha256'})))
 def test_M02_valid_retirement(self):
    revs=self.snapshots();before={p.name:p.read_bytes() for p in self.s.iterdir()};p,v=self.plan(revs[:2]);self.apply(p,v)
    for x in revs[2:]:self.assertEqual((self.s/(x+'.zip')).read_bytes(),before[x+'.zip'])
    self.assertEqual((self.s/'HEAD.json').read_bytes(),before['HEAD.json'])
    archived=self.a/v['plan_sha256'];self.assertTrue(archived.is_dir())
    manifest=json.loads((archived/'archive-manifest.json').read_bytes())
    self.assertEqual(set(manifest),{'version','plan','files'});self.assertEqual(manifest['plan'],v)
    for i,x in enumerate(revs[:2]):
      name=x+'.zip';self.assertFalse((self.s/name).exists());self.assertEqual((archived/name).read_bytes(),before[name])
      self.assertEqual(manifest['files'][name],{'sha256':sha(before[name]),'size':len(before[name])})
      dest=self.d/('restore-%s'%i);dest.mkdir()
      run('transfer.py','unpack','--archive',archived/name,'--root',dest,'--id','calculus-a',base=True)
 def test_M03_refusals(self):
    revs=self.snapshots();p,v=self.plan(revs[:2]);before=content(self.s)
    self.apply(p,v,approved=False,ok=2);self.assertEqual(content(self.s),before)
    self.apply(p,v,expected='0'*64,ok=2);self.assertEqual(content(self.s),before)
    edited=dict(v);edited['journey_id']='foreign';bad=self.d/'edited-plan.json';bad.write_bytes(canonical(edited))
    self.apply(bad,v,ok=2);self.assertEqual(content(self.s),before)
    nested=self.s/'nested';nested.mkdir();self.apply(p,v,archive=nested,ok=2);nested.rmdir();self.assertEqual(content(self.s),before)
    self.apply(p,v,archive=self.d,ok=2);self.assertEqual(content(self.s),before)
    existing=self.a/v['plan_sha256'];existing.mkdir();sentinel=existing/'sentinel';sentinel.write_text('preserve')
    self.apply(p,v,ok=2);self.assertEqual(sentinel.read_text(),'preserve');self.assertEqual(content(self.s),before)
    # Semantic store remains valid but HEAD bytes differ, invalidating exact-store plan.
    head=self.s/'HEAD.json';head.write_bytes(head.read_bytes()+b'\n');changed=content(self.s)
    other=self.d/'archive-other';other.mkdir();self.apply(p,v,archive=other,ok=2);self.assertEqual(content(self.s),changed)
if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Cases)
    stream=open(ROOT/'deterministic-output.txt','w')
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite);stream.close()
    (ROOT/'cli-log.json').write_text(json.dumps(LOG,indent=2)+'\n')
    report={'run':len(result.failures)+len(result.errors)+result.testsRun,'testsRun':result.testsRun,'failures':[(str(t),x) for t,x in result.failures],'errors':[(str(t),x) for t,x in result.errors],'target':str(TARGET),'case_manifest_sha256':sha((ROOT/'frozen-cases.json').read_bytes())}
    (ROOT/'deterministic-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report));sys.exit(not result.wasSuccessful())
