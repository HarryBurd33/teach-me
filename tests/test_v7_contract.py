"""Public unittest adapter; frozen expressions and assertions retained."""
import os
from pathlib import Path
import tempfile
import unittest
import _v7_frozen as h
EXPRESSIONS = {'H01': 'hist', 'R01': 'recovery_finish', 'H02': "lambda:refused_unchanged(lambda:imp(HS,HR,HT,digest='0'*64,ok=False),HS)", 'H03': "lambda:refused_unchanged(lambda:imp(HS,HR,'0'*64,ok=False),HS)", 'H04': "lambda:refused_unchanged(lambda:imp(HS,HR,HT,ident='wrong',ok=False),HS)", 'H05': "lambda:[refused_unchanged(lambda:imp(HS,HR,HT,reason=x,ok=False),HS) for x in ['  ','x'*4097]]", 'H06': "lambda:mutate_entry('origin','current_checked_append')", 'H07': "lambda:[mutate_entry('receipt_base64','!!'),mutate_entry('origin_note','',True),mutate_entry('previous','f'*64),mutate_entry('foreign','key')]", 'H08': 'mixed', 'H09': 'hist_locks', 'R02': "lambda:[rbad('tampered-zip',lambda p,s,a:next(a.glob('*.zip')).write_bytes(b'corrupt')),rbad('tampered-manifest',lambda p,s,a:(a/'archive-manifest.json').write_bytes(b'{}\\n'))]", 'R03': "lambda:[rbad('incomplete-zip',lambda p,s,a:next(a.glob('*.zip')).unlink()),rbad('incomplete-manifest',lambda p,s,a:(a/'archive-manifest.json').unlink())]", 'R04': 'protect', 'R05': 'stale', 'R06': 'digest_approval', 'R07': "lambda:[rbad('unknown-'+k,lambda p,s,a:(s if k=='store' else a).joinpath('unknown').write_text('preserve')) for k in ['store','archive']]", 'R08': 'foreign', 'R09': 'repeat', 'R10': 'noop', 'R11': 'archive_locks'}
class V7Frozen(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  h.WORK=Path(self.temp.name).resolve();h.SCRIPTS=Path(os.environ.get('TEACH_ME_SKILL',Path(__file__).resolve().parents[1]/'teach-me')).resolve()/'scripts';h.logs=[];h.results=[]
 def exercise(self,key):
  if key.startswith('H') and key!='H01':h.hist()
  if key.startswith('R') and key!='R01':h.recovery_fixture()
  eval(EXPRESSIONS[key],h.__dict__)()
 def test_H01(self):self.exercise('H01')
 def test_H02(self):self.exercise('H02')
 def test_H03(self):self.exercise('H03')
 def test_H04(self):self.exercise('H04')
 def test_H05(self):self.exercise('H05')
 def test_H06(self):self.exercise('H06')
 def test_H07(self):self.exercise('H07')
 def test_H08(self):self.exercise('H08')
 def test_H09(self):self.exercise('H09')
 def test_R01(self):self.exercise('R01')
 def test_R02(self):self.exercise('R02')
 def test_R03(self):self.exercise('R03')
 def test_R04(self):self.exercise('R04')
 def test_R05(self):self.exercise('R05')
 def test_R06(self):self.exercise('R06')
 def test_R07(self):self.exercise('R07')
 def test_R08(self):self.exercise('R08')
 def test_R09(self):self.exercise('R09')
 def test_R10(self):self.exercise('R10')
 def test_R11(self):self.exercise('R11')
