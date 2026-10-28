"""Publication and hard-interruption checks, outside candidate-controlled files."""
import errno
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SKILL = Path(os.environ.get('TEACH_ME_SKILL', str(Path(__file__).resolve().parents[1] / 'teach-me')))
SCRIPT = SKILL / 'scripts/learning_data.py'
spec = importlib.util.spec_from_file_location('publication_module', SCRIPT)
MOD = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MOD)


SLOW_WRITER = r'''
import os,sys,time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,sys.argv[1])
import learning_data as m
root=Path(sys.argv[2]);source=root/'source.json';output=root/'report.json'
original=m.os.fdopen
class Slow:
    def __init__(self,fd,*args,**kwargs):self.handle=original(fd,*args,**kwargs)
    def __enter__(self):return self
    def __exit__(self,*args):return self.handle.__exit__(*args)
    def write(self,data):
        self.handle.write(data[:len(data)//2]);self.handle.flush()
        (root/'ready').write_text('half written')
        while True:time.sleep(.1)
    def flush(self):self.handle.flush()
    def fileno(self):return self.handle.fileno()
with patch.object(m.os,'fdopen',Slow):
    m.publish({'message':'x'*1000},output,[(source,source.read_bytes())])
'''


class ReportPublication(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / 'source.json'
        self.source.write_text('{"id":"fixture"}')
        self.raw = self.source.read_bytes()
        self.output = self.root / 'report.json'

    def tearDown(self):
        self.temp.cleanup()

    def publish(self):
        return MOD.publish({'complete': True}, self.output, [(self.source, self.raw)])

    def assert_clean(self):
        self.assertEqual(self.source.read_bytes(), self.raw)
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.root.glob('.teach-me-report-*')), [])

    def test_final_name_only_appears_after_full_staging(self):
        original = MOD.os.link
        observed = []
        def linked(staging, output):
            self.assertFalse(self.output.exists())
            self.assertEqual(json.loads(Path(staging).read_text()), {'complete': True})
            observed.append(True)
            return original(staging, output)
        with patch.object(MOD.os, 'link', linked):
            self.publish()
        self.assertEqual(observed, [True])
        self.assertEqual(json.loads(self.output.read_text()), {'complete': True})
        self.assertEqual(self.source.read_bytes(), self.raw)
        self.assertEqual(list(self.root.glob('.teach-me-report-*')), [])

    def test_foreign_destination_created_in_race_survives(self):
        def race(staging, output):
            Path(output).write_text('foreign writer bytes')
            raise FileExistsError('racing destination')
        with patch.object(MOD.os, 'link', race), self.assertRaises(FileExistsError):
            self.publish()
        self.assertEqual(self.output.read_text(), 'foreign writer bytes')
        self.assertEqual(self.source.read_bytes(), self.raw)
        self.assertEqual(list(self.root.glob('.teach-me-report-*')), [])

    def test_existing_output_not_overwritten(self):
        self.output.write_text('existing')
        with self.assertRaises(FileExistsError):
            self.publish()
        self.assertEqual(self.output.read_text(), 'existing')
        self.assertEqual(list(self.root.glob('.teach-me-report-*')), [])

    def test_fsync_failure_does_not_publish(self):
        with patch.object(MOD.os, 'fsync', side_effect=OSError('injected disk failure')):
            with self.assertRaises(OSError):
                self.publish()
        self.assert_clean()

    def test_unsupported_atomic_link_fails_closed(self):
        with patch.object(MOD.os, 'link', side_effect=OSError(errno.ENOTSUP, 'unsupported link')):
            with self.assertRaises(OSError):
                self.publish()
        self.assert_clean()

    def test_changed_source_after_staging_refused(self):
        original = MOD.tempfile.mkstemp
        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            self.source.write_text('changed independently')
            return result
        with patch.object(MOD.tempfile, 'mkstemp', changed), self.assertRaises(MOD.DataError):
            self.publish()
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.root.glob('.teach-me-report-*')), [])

    def test_source_replacement_refused(self):
        self.output = self.source
        with self.assertRaises(MOD.DataError):
            self.publish()
        self.assertEqual(self.source.read_bytes(), self.raw)

    @unittest.skipUnless(os.name == 'posix', 'hard-kill fixture uses POSIX')
    def test_hard_interruption_exposes_no_partial_final_report(self):
        process = subprocess.Popen([sys.executable, '-B', '-c', SLOW_WRITER,
                                    str(SCRIPT.parent), str(self.root)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            until = time.monotonic() + 5
            while not (self.root / 'ready').exists() and time.monotonic() < until:
                time.sleep(.01)
            self.assertTrue((self.root / 'ready').exists(), 'Writer did not reach half-write fixture')
            self.assertFalse(self.output.exists())
            process.kill()
            process.communicate(timeout=3)
            self.assertFalse(self.output.exists())
            self.assertEqual(self.source.read_bytes(), self.raw)
            self.assertEqual(len(list(self.root.glob('.teach-me-report-*'))), 1)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()


if __name__ == '__main__':
    unittest.main()
