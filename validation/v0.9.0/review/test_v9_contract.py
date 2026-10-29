"""Independent frozen v0.9 DOM contracts. Node.js required; not browser QA."""
import os
from pathlib import Path
import subprocess
import unittest
ROOT = Path(os.environ.get('TEACH_ME_SKILL', Path(__file__).resolve().parents[1] / 'candidate' / 'teach-me')).resolve()
RUNNER = Path(__file__).with_name('contract-runner.js')
CASES = ['history_exact_metadata','redo_branch_and_noop','failed_mutation_preserves','reset_undo_redo','import_replaces_from_base_and_undo','import_roundtrip_and_joint','reject_malformed','reject_duplicate_members','reject_nested_duplicate_members','reject_wrong_base','reject_unknown_and_bool','reject_metadata','reject_bad_shapes_ids_endpoints','reject_size_and_depth','history_step_bound','history_byte_bound','focus_controls_and_hostile_text']
class FrozenContract(unittest.TestCase):
    pass

def method(name):
    def run(self):
        r = subprocess.run(['node', str(RUNNER), str(ROOT/'assets/graph-editor.js'), str(ROOT/'assets/graph-editor.html'), name], capture_output=True, text=True, timeout=15)
        self.assertEqual(r.returncode, 0, r.stdout + '\n' + r.stderr)
    return run
for name in CASES:
    setattr(FrozenContract, 'test_'+name, method(name))
if __name__ == '__main__':
    unittest.main(verbosity=2)
