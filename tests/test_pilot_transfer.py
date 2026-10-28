"""Supplement frozen before candidate2 pilot allowlist extension."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile

SKILL=Path(os.environ.get('TEACH_ME_SKILL', str(Path(__file__).resolve().parents[1]/'teach-me')))
SCRIPTS=SKILL/'scripts'

class PilotTransferSupplement(unittest.TestCase):
    def test_pilot_record_exact_byte_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            def cli(name,*args):
                p=subprocess.run([sys.executable,'-B',str(SCRIPTS/name),*map(str,args)],capture_output=True,text=True,timeout=10)
                self.assertEqual(p.returncode,0,p.stderr+p.stdout)
                return json.loads(p.stdout)
            cli('journey.py','init','--root',root,'--id','pilot','--topic','Algebra','--goal','Explain an unfamiliar example')
            journey=root/'learning/pilot'
            pilot=('Real learner pilot — private synthetic fixture\nBaseline result: pending\n'
                   'Confidence: 0 (self-reported); delayed result: unknown\n').encode('utf-8')
            (journey/'learning-pilot.md').write_bytes(pilot)
            progress=(journey/'progress.json').read_bytes()
            archive=root/'pilot.zip'
            cli('transfer.py','pack','--journey',journey,'--output',archive)
            with zipfile.ZipFile(archive) as inp:
                self.assertEqual(inp.read('learning-pilot.md'),pilot)
            receiving=root/'receiving';receiving.mkdir()
            cli('transfer.py','unpack','--archive',archive,'--root',receiving,'--id','pilot')
            target=receiving/'learning/pilot'
            self.assertEqual((target/'learning-pilot.md').read_bytes(),pilot)
            self.assertEqual((target/'progress.json').read_bytes(),progress)
            self.assertEqual((journey/'learning-pilot.md').read_bytes(),pilot)
            self.assertEqual((journey/'progress.json').read_bytes(),progress)

if __name__=='__main__':unittest.main(verbosity=2)
