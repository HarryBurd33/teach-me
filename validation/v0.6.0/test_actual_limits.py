"""Post-inspection real64MiB limits; synthetic local fixtures, no learner data."""
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
SKILL=Path(os.environ.get('TEACH_ME_SKILL',str(Path(__file__).resolve().parent/'candidate/teach-me'))).resolve()
sys.path.insert(0,str(SKILL/'scripts'))
import review_history as history
import snapshot_maintenance as maintenance
import journey_versions as versions
import journey
from storage import StorageError

class ActualLimits(unittest.TestCase):
 def test_history_actual_total_bound(self):
  self.assertEqual(history.TOTAL_LIMIT,64*1024*1024)
  with tempfile.TemporaryDirectory() as raw:
   root=Path(raw).resolve(); store=root/'history';store.mkdir()
   # Recognized orphan stages are bounded regular bytes and count toward total.
   for i in range(21): (store/(history.STAGE_PREFIX+str(i))).write_bytes(b'x'*(3*1024*1024))
   tail=store/(history.STAGE_PREFIX+'tail');tail.write_bytes(b'x'*(1024*1024))
   self.assertEqual(len(history.status(store)['staging_entries']),22)
   with tail.open('ab') as f:f.write(b'x')
   with self.assertRaisesRegex(StorageError,'64 MiB'):history.status(store)
   self.assertFalse((store/history.LOCK).exists())
 def test_maintenance_actual_selected_bound(self):
  self.assertEqual(maintenance.SELECTED_LIMIT,64*1024*1024)
  with tempfile.TemporaryDirectory() as raw:
   root=Path(raw).resolve(); store=root/'store';store.mkdir()
   # All8 archives are valid stored transfer-v1 ZIPs with bounded members.
   state={'schema_version':1,'journey_id':'logic','topics':['logic'],'goal':'Explain arguments','current_stage':'diagnostic','availability':{'minutes_per_day':None,'session_minutes':None},'assessments':[],'evidence':[],'difficulties':[],'decisions':[],'next_action':'Try a premise','updated_at':'2026-10-28T00:00:00Z'}
   revisions=[];payload=b'x'*(2*1024*1024)
   for i in range(8):
    state['next_action']='Try premise '+str(i);journey.validate(state)
    files={name:payload for name in ('plan.md','sources.md','knowledge.md','practice.md','harness-project.md','learning-pilot.md')};files['progress.json']=versions.encoded(state)
    manifest={'version':1,'files':{n:{'sha256':hashlib.sha256(v).hexdigest(),'size':len(v)} for n,v in files.items()}}
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_STORED) as z:
     for n,v in files.items():z.writestr(n,v)
     z.writestr('manifest.json',versions.encoded(manifest))
    data=out.getvalue();sha=hashlib.sha256(data).hexdigest();(store/(sha+'.zip')).write_bytes(data);revisions.append(sha)
   head=versions.encoded({'version':1,'journey_id':'logic','revision':revisions[-1],'previous':revisions[-2]});(store/'HEAD.json').write_bytes(head)
   selected=revisions[:-2];self.assertGreater(sum((store/(s+'.zip')).stat().st_size for s in selected),64*1024*1024)
   output=root/'plan.json'
   with self.assertRaisesRegex(StorageError,'64 MiB'):maintenance.plan(store,selected,output)
   self.assertFalse(output.exists());self.assertEqual((store/'HEAD.json').read_bytes(),head)
   self.assertEqual(len(list(store.glob('*.zip'))),8);self.assertFalse((store/versions.LOCK).exists())

if __name__=='__main__':unittest.main()
