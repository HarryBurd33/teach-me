#!/usr/bin/env python3
"""Frozen independent capability/fault checks; writes only under review/fixtures.
Run one arm per process to prevent import/module contamination. No API/services.
"""
import argparse,base64,hashlib,json,os,pathlib,shutil,subprocess,sys,traceback
P=pathlib.Path
ROOT=P(__file__).resolve().parent
SHA=lambda b:hashlib.sha256(b).hexdigest()
ENC=lambda v:(json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode()
results=[]
def check(name,fn):
    try: details=fn(); results.append(dict(id=name,passed=True,details=details))
    except Exception as e: results.append(dict(id=name,passed=False,error=str(e),traceback=traceback.format_exc()))
def tree(p):return {str(x.relative_to(p)):SHA(x.read_bytes()) for x in p.rglob('*') if x.is_file()}
def run(script,*args,ok=True, fault_store=None,after=1):
    argv=[sys.executable,str(SCRIPTS/script),*map(str,args)]
    if fault_store:
        # Scoped fault at actual pathlib unlink boundary, before selected unlink #after+1.
        code="""import pathlib,sys,runpy
store=pathlib.Path(sys.argv[1]).resolve(); after=int(sys.argv[2]); orig=pathlib.Path.unlink; n=[0]
def fault(p,*a,**k):
 if p.parent.resolve()==store and p.suffix=='.zip':
  if n[0]>=after: raise OSError('FROZEN independent unlink fault')
  n[0]+=1
 return orig(p,*a,**k)
pathlib.Path.unlink=fault
sys.argv=sys.argv[3:]
sys.path.insert(0,str(pathlib.Path(sys.argv[0]).parent))
runpy.run_path(sys.argv[0],run_name='__main__')
"""
        argv=[sys.executable,'-c',code,str(fault_store),str(after),*argv[1:]]
    cp=subprocess.run(argv,text=True,capture_output=True,timeout=20)
    logs.append(dict(argv=argv if not fault_store else ['fault-wrapper',script,*map(str,args)],returncode=cp.returncode,stdout=cp.stdout,stderr=cp.stderr))
    if ok: assert cp.returncode==0,cp.stderr
    else: assert cp.returncode!=0,'Unexpected success: '+cp.stdout
    if cp.returncode==0:return json.loads(cp.stdout)
    return cp.stderr.strip()
def newdir(name):
    p=WORK/name; n=1
    while p.exists():p=WORK/(name+'-'+str(n));n+=1
    p.mkdir();return p
def makejourney(root,ident='heldout'):
    run('journey.py','init','--root',root,'--id',ident,'--topic','Evidence','--goal','Test optional maintenance safely')
    return root/'learning'/ident
def receipt(j,prefix):
    packet=WORK/(prefix+'-packet.json'); rp=WORK/(prefix+'-receipt.json'); dp=WORK/(prefix+'-decisions.json')
    v=run('coherence_review.py','prepare','--journey',j,'--output',packet)
    dp.write_bytes(ENC({'version':1,'packet_sha256':v['packet_sha256'],'reviewer_role':'tutor','decisions':[dict(check_id=x['check_id'],result='consistent',rationale='Inspected fixture evidence is internally consistent.') for x in v['checks']]}))
    run('coherence_review.py','record','--journey',j,'--packet',packet,'--decisions',dp,'--output',rp)
    rp.write_bytes(b' \n'+json.dumps(json.loads(rp.read_bytes()),indent=3,ensure_ascii=False).encode()+b'\n\n')
    return rp
def imp(s,r,tip='none',ident='heldout',reason='Imported old operator judgment; no current freshness approval.',digest=None,ok=True):
    return run('review_history.py','import','--store',s,'--receipt',r,'--id',ident,'--expected-tip',tip,'--expected-receipt-sha256',digest or SHA(r.read_bytes()),'--reason',reason,ok=ok)
def status(s):return run('review_history.py','status','--store',s)
def refused_unchanged(fn,*paths):
    before=[tree(p) for p in paths]; msg=fn(); assert before==[tree(p) for p in paths],'Refusal mutated files';return msg
def hist():
    j=makejourney(newdir('history-workspace')); r=receipt(j,'old'); original=r.read_bytes(); (j/'plan.md').write_text('Changed after historical review.\n')
    s=newdir('history'); imp(s,r); st=status(s); en=st['entries'][0]
    assert en['origin']=='historical_import' and en['resume_ready'] is False and en['receipt_resume_ready'] is True
    assert st['receipt_freshness_checked'] is False
    out=WORK/'extracted.json'; run('review_history.py','extract','--store',s,'--entry',st['tip'],'--output',out); assert out.read_bytes()==original
    globals().update(HJ=j,HR=r,HS=s,HT=st['tip']);return st
def mutate_entry(field,value,remove=False):
    s=newdir('malformed-'+str(len(results))); shutil.copytree(HS,s,dirs_exist_ok=True); p=next(s.glob('*.json')); v=json.loads(p.read_bytes())
    if remove:del v[field]
    else:v[field]=value
    p.unlink(); raw=ENC(v); (s/('%06d-%s.json'%(v['sequence'],SHA(raw)))).write_bytes(raw)
    return refused_unchanged(lambda:run('review_history.py','status','--store',s,ok=False),s)
def mixed():
    s=newdir('mixed'); j=makejourney(newdir('mixed-workspace')); r=receipt(j,'mixed-current')
    a=run('review_history.py','append','--store',s,'--journey',j,'--receipt',r,'--expected-tip','none'); before=tree(s)
    imp(s,HR,a['entry']); st=status(s); b=run('review_history.py','append','--store',s,'--journey',j,'--receipt',r,'--expected-tip',st['tip'])
    for name,sha in before.items():assert SHA((s/name).read_bytes())==sha
    vals=[json.loads(p.read_bytes()) for p in sorted(s.glob('*.json'))]; assert [v['version'] for v in vals]==[1,2,1]
    assert set(vals[0])==set(vals[2])=={'version','journey_id','sequence','previous','receipt_sha256','receipt_base64'}
    for en in status(s)['entries']:
        o=WORK/('mixed-out-'+str(en['sequence'])+'.json');run('review_history.py','extract','--store',s,'--entry',en['sha256'],'--output',o)
        assert o.read_bytes()==(HR.read_bytes() if en['sequence']==2 else r.read_bytes())
    return {'versions':[1,2,1],'old_raw_unchanged':True}
def hist_locks():
    out=[]
    for name in ['.teach-me-review-history.lock','.teach-me-history-stage-orphan']:
        s=newdir('hist-lock-'+str(len(out))); (s/name).write_text('foreign preserved')
        out.append(refused_unchanged(lambda:imp(s,HR,ok=False),s))
    return out

def recovery_fixture():
    base=newdir('recovery-base'); ws=base/'workspace';ws.mkdir(); j=makejourney(ws);store=base/'store';store.mkdir();ar=base/'archives';ar.mkdir(); rev=[]; head='none'
    for n in range(6):
        (j/'plan.md').write_text('Independent snapshot %d\n'%n); v=run('journey_versions.py','snapshot','--journey',j,'--store',store,'--expected-head',head);head=v['revision'];rev.append(head)
    selected=rev[:4]; plan=base/'retire.json';v=run('snapshot_maintenance.py','plan','--store',store,'--revisions',*selected,'--output',plan)
    before=tree(store);run('snapshot_maintenance.py','apply','--store',store,'--plan',plan,'--archive-root',ar,'--expected-plan-sha256',v['plan_sha256'],'--approve',ok=False,fault_store=store)
    archive=ar/v['plan_sha256']; assert archive.is_dir();assert len(list(store.glob('*.zip')))==5
    globals().update(RBASE=base,RSEL=sorted(selected),RORIG=v,RBEFORE=before,RARCHIVEHASH=tree(archive));return {'selected':selected,'archive':str(archive)}
def clone(name):
    p=newdir(name);shutil.copytree(RBASE,p,dirs_exist_ok=True); return p,p/'store',p/'archives'/RORIG['plan_sha256']
def rplan(p,s,a):return run('snapshot_recovery.py','plan','--store',s,'--archive',a,'--output',p/'recovery.json')
def rapp(p,s,a,v,**kwargs):return run('snapshot_recovery.py','apply','--store',s,'--archive',a,'--plan',p/'recovery.json','--expected-plan-sha256',v['plan_sha256'],'--approve',**kwargs)
def protected(s):
    h=json.loads((s/'HEAD.json').read_bytes());return {name:SHA((s/name).read_bytes()) for name in ['HEAD.json',h['revision']+'.zip',h['previous']+'.zip']}
def recovery_finish():
    recovery_fixture();p,s,a=clone('recovery-finish');b=protected(s);arc=tree(a);v=rplan(p,s,a)
    assert set(v)=={'version','journey_id','original_plan_sha256','store_sha256','archive_sha256','head','protected','remaining','already_absent','plan_sha256'}
    assert len(v['remaining'])==3 and len(v['already_absent'])==1 and set(v['remaining']+v['already_absent'])==set(RSEL)
    assert v['plan_sha256']==SHA(ENC({k:x for k,x in v.items() if k!='plan_sha256'}))
    rapp(p,s,a,v);assert protected(s)==b and tree(a)==arc
    dest=p/'restore';dest.mkdir();run('transfer.py','unpack','--archive',a/(RSEL[0]+'.zip'),'--root',dest,'--id','heldout');assert (dest/'learning/heldout/progress.json').is_file()
    return {'restored':True,'protected_unchanged':True,'archive_unchanged':True}
def rbad(name,change):
    p,s,a=clone(name);change(p,s,a);return refused_unchanged(lambda:run('snapshot_recovery.py','plan','--store',s,'--archive',a,'--output',p/'recovery.json',ok=False),s,a)
def repeat():
    p,s,a=clone('repeat');v=rplan(p,s,a);b=protected(s);ah=tree(a)
    rapp(p,s,a,v,ok=False,fault_store=s);assert len(list(s.glob('*.zip')))==4
    refused_unchanged(lambda:rapp(p,s,a,v,ok=False),s,a)
    (p/'recovery.json').rename(p/'old-recovery.json');v=rplan(p,s,a);assert len(v['remaining'])==2;rapp(p,s,a,v);assert protected(s)==b and tree(a)==ah;return v

def noop():
    p,s,a=clone('noop');v=rplan(p,s,a);rapp(p,s,a,v);(p/'recovery.json').rename(p/'done-plan.json');v=rplan(p,s,a);assert not v['remaining'] and sorted(v['already_absent'])==RSEL;b=tree(s);ah=tree(a);rapp(p,s,a,v);assert tree(s)==b and tree(a)==ah
    (a/'unexpected').write_text('preserve');refused_unchanged(lambda:rapp(p,s,a,v,ok=False),s,a);return v

def stale():
    p,s,a=clone('stale');v=rplan(p,s,a); h=json.loads((s/'HEAD.json').read_bytes());(s/'HEAD.json').write_bytes(json.dumps(h,indent=2).encode()+b'\n');return refused_unchanged(lambda:rapp(p,s,a,v,ok=False),s,a)
def digest_approval():
    p,s,a=clone('digest');v=rplan(p,s,a);out=[]
    for args in [('--expected-plan-sha256','0'*64,'--approve'),('--expected-plan-sha256',v['plan_sha256'])]:out.append(refused_unchanged(lambda:run('snapshot_recovery.py','apply','--store',s,'--archive',a,'--plan',p/'recovery.json',*args,ok=False),s,a))
    return out
def protect():
    out=[]
    for key in ['revision','previous']:
        def change(p,s,a):
            h=json.loads((s/'HEAD.json').read_bytes());h[key]=next(x for x in RSEL if (s/(x+'.zip')).exists());(s/'HEAD.json').write_bytes(ENC(h))
        out.append(rbad('protected-'+key,change))
    return out
def foreign():
    p,s,a=clone('foreign');manifest=json.loads((a/'archive-manifest.json').read_bytes());v=manifest['plan'];v['journey_id']='foreign';v['head']['journey_id']='foreign';v['plan_sha256']=SHA(ENC({k:x for k,x in v.items() if k!='plan_sha256'}));(a/'archive-manifest.json').write_bytes(ENC(manifest));new=a.parent/v['plan_sha256'];a.rename(new);a=new
    return refused_unchanged(lambda:run('snapshot_recovery.py','plan','--store',s,'--archive',a,'--output',p/'recovery.json',ok=False),s,a)
def archive_locks():
    out=[]
    for k in ['store','archive']:
        p,s,a=clone('locks-'+k); target=s/'.teach-me-store.lock' if k=='store' else a.parent/'.teach-me-snapshot-maintenance.lock';target.write_text('uncertain foreign lock');out.append(refused_unchanged(lambda:run('snapshot_recovery.py','plan','--store',s,'--archive',a,'--output',p/'recovery.json',ok=False),s,a))
    p,s,a=clone('ancestry');inside=s/'archive';shutil.copytree(a,inside);out.append(refused_unchanged(lambda:run('snapshot_recovery.py','plan','--store',s,'--archive',inside,'--output',p/'recovery.json',ok=False),s,inside));return out
