#!/usr/bin/env python3
"""Fault classes frozen before candidate inspection; exact injection points recorded."""
import importlib.util,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('heldouts',ROOT/'run_heldouts.py');h=importlib.util.module_from_spec(s);s.loader.exec_module(h)
sys.path.insert(0,str(h.TARGET/'scripts'))
import snapshot_maintenance as m
RESULT=[]
def fixture():
 c=h.Cases();c.setUp();r=c.snapshots();p,v=c.plan(r[:2]);return c,r,p,v
def capture(case,fn):
 try: data=fn();RESULT.append({'id':case,'status':'pass',**data})
 except Exception as e:
  import traceback
  RESULT.append({'id':case,'status':'fail','error':repr(e),'traceback':traceback.format_exc()})
def prebackup(kind):
 c,r,p,v=fixture();before={x.name:x.read_bytes() for x in c.s.iterdir()};original=m.copy_revision if kind=='copy' else m.verify_backup;remove=m.remove_revision;calls=[];copies=[]
 def deletion(path):calls.append(str(path));return remove(path)
 def failed(*args):
  if kind=='copy':
   copies.append(str(args[0]))
   if len(copies)==1:return original(*args)
  raise OSError('independent frozen '+kind+' fault')
 if kind=='copy':m.copy_revision=failed
 else:m.verify_backup=failed
 m.remove_revision=deletion
 try:
  try:m.apply(c.s,p,c.a,v['plan_sha256'],True);raise AssertionError('injected failure unexpectedly succeeded')
  except m.StorageError as e:message=str(e)
 finally:
  if kind=='copy':m.copy_revision=original
  else:m.verify_backup=original
  m.remove_revision=remove
 assert not calls,calls
 assert {x.name:x.read_bytes() for x in c.s.iterdir()}==before
 assert not (c.a/v['plan_sha256']).exists()
 return {'injection':'snapshot_maintenance.'+('copy_revision second call' if kind=='copy' else 'verify_backup first stage check'),'selected_unlink_calls':calls,'sources_preserved':True,'fixture':str(c.d),'message':message}
def partial():
 c,r,p,v=fixture();before={x.name:x.read_bytes() for x in c.s.iterdir()};remove=m.remove_revision;calls=[]
 def failed(path):
  calls.append(str(path))
  if len(calls)==2:raise OSError('independent frozen second-source-unlink fault')
  return remove(path)
 m.remove_revision=failed
 try:
  try:m.apply(c.s,p,c.a,v['plan_sha256'],True);raise AssertionError('injected partial failure unexpectedly succeeded')
  except m.StorageError as e:message=str(e)
 finally:m.remove_revision=remove
 assert len(calls)==2
 archive=c.a/v['plan_sha256'];manifest=json.loads((archive/'archive-manifest.json').read_bytes());m.verify_backup(archive,manifest)
 assert (c.s/'HEAD.json').read_bytes()==before['HEAD.json']
 for x in r[2:]:assert (c.s/(x+'.zip')).read_bytes()==before[x+'.zip']
 for x in r[:2]:assert (archive/(x+'.zip')).read_bytes()==before[x+'.zip']
 assert sum((c.s/(x+'.zip')).exists() for x in r[:2])==1
 for i,x in enumerate(r[:2]):
  root=c.d/('fault-restore-'+str(i));root.mkdir()
  h.run('transfer.py','unpack','--archive',archive/(x+'.zip'),'--root',root,'--id','calculus-a',base=True)
 # Apply old plan must reject rather than automatically replaying missing revision.
 newroot=c.d/'fresh-archive';newroot.mkdir()
 c.apply(p,v,archive=newroot,ok=2)
 return {'injection':'snapshot_maintenance.remove_revision second call','selected_unlink_calls':calls,'complete_backup_verified':True,'both_archives_restored':True,'protected_bytes_preserved':True,'old_plan_replay_refused':True,'fixture':str(c.d),'message':message}
capture('M04-copy-failure',lambda:prebackup('copy'))
capture('M04-verification-failure',lambda:prebackup('verify'))
capture('M05-partial-unlink',partial)
(ROOT/'fault-results.json').write_text(json.dumps(RESULT,indent=2)+'\n')
(ROOT/'fault-cli-log.json').write_text(json.dumps(h.LOG,indent=2)+'\n')
print(json.dumps(RESULT,indent=2));sys.exit(any(x['status']!='pass' for x in RESULT))
