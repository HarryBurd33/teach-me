"""Regression for observed UI/Python integer version token mismatch."""
import os
from pathlib import Path
import subprocess
import unittest
ROOT = Path(os.environ.get('TEACH_ME_SKILL', Path(__file__).resolve().parents[1] / 'teach-me')).resolve()
class NumericVersions(unittest.TestCase):
    def test_float_or_exponent_version_tokens_preserve_current_work(self):
        runner = Path(__file__).with_name('supplemental-number-runner.js')
        r = subprocess.run(['node',str(runner),str(ROOT/'assets/graph-editor.js'),str(ROOT/'assets/graph-editor.html'),'reject_noninteger_version_tokens'],capture_output=True,text=True,timeout=15)
        self.assertEqual(r.returncode,0,r.stdout+'\n'+r.stderr)
if __name__ == '__main__':
    unittest.main(verbosity=2)
