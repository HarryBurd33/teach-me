"""Independent fault-injection checks frozen before candidate source read."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

RUN=Path(__file__).resolve().parents[2]
SKILL=Path(os.environ.get('TEACH_ME_SKILL',str(RUN/'candidate/teach-me')))

class AtomicPublication(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve()
        spec=importlib.util.spec_from_file_location('review_atomic_learning_data',SKILL/'scripts/learning_data.py')
        self.mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.mod)
        self.source=self.root/'source.txt';self.source.write_text('synthetic source\n');self.raw=self.source.read_bytes();self.out=self.root/'report.json'
    def tearDown(self):self.temp.cleanup()
    def test_link_failure_leaves_no_incomplete_output_or_source_change(self):
        with patch.object(self.mod.os,'link',side_effect=OSError('injected publication failure')):
            with self.assertRaises(OSError):self.mod.publish({'fixture':'value'},self.out,[(self.source,self.raw)])
        self.assertFalse(self.out.exists());self.assertEqual(self.source.read_bytes(),self.raw)
    def test_foreign_result_created_during_staging_is_preserved(self):
        def fault(fd):
            if self.out.exists():self.out.unlink()
            self.out.write_text('foreign result created by another writer')
            raise OSError('injected staging failure after foreign destination appears')
        with patch.object(self.mod.os,'fsync',side_effect=fault):
            with self.assertRaises(OSError):self.mod.publish({'fixture':'value'},self.out,[(self.source,self.raw)])
        self.assertTrue(self.out.exists())
        self.assertEqual(self.out.read_text(),'foreign result created by another writer')
        self.assertEqual(self.source.read_bytes(),self.raw)

if __name__=='__main__':unittest.main(verbosity=2)
