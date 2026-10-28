import json
import importlib.util
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace

SKILL = Path(os.environ.get('TEACH_ME_SKILL', str(Path(__file__).resolve().parents[1] / 'teach-me')))
SCRIPT = SKILL / 'scripts/harness.py'


class HarnessCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.plan = self.root / 'plan.json'
        self.output = self.root / 'run.json'

    def tearDown(self):
        self.temp.cleanup()

    def node(self, ident='check', code='print("ok")', **changes):
        value = {'id': ident, 'argv': [sys.executable, '-c', code], 'depends_on': [],
                 'timeout_seconds': 2, 'max_attempts': 1, 'human_gate': False}
        value.update(changes)
        return value

    def write(self, nodes, maximum=5):
        self.plan.write_text(json.dumps({'version': 1, 'max_seconds': maximum, 'nodes': nodes}))

    def command(self, *extra):
        return [sys.executable, str(SCRIPT), 'run', '--plan', str(self.plan),
                '--root', str(self.root), '--output', str(self.output), *extra]

    def run_cli(self, *extra, expected=0):
        p = subprocess.run(self.command(*extra), capture_output=True, text=True, timeout=10)
        self.assertEqual(p.returncode, expected, p.stderr + p.stdout)
        return json.loads(p.stdout) if p.stdout else p.stderr

    def test_dry_run_creates_nothing(self):
        self.write([self.node(code="open('marker', 'w').write('bad')")])
        result = self.run_cli()
        self.assertEqual(result['status'], 'dry_run')
        self.assertFalse(self.output.exists())
        self.assertFalse((self.root / 'marker').exists())

    def test_success_orders_dependencies(self):
        maker = self.node('maker', "open('value', 'w').write('42')")
        checker = self.node('checker', "assert open('value').read() == '42'", depends_on=['maker'])
        self.write([checker, maker])
        result = self.run_cli('--execute')
        self.assertEqual([x['id'] for x in result['nodes']], ['maker', 'checker'])
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(json.loads(self.output.read_text()), result)

    def test_failure_blocks_dependency_and_bounds_retries(self):
        code = "from pathlib import Path; p=Path('count'); p.write_text(str(int(p.read_text())+1) if p.exists() else '1'); raise SystemExit(1)"
        self.write([self.node('bad', code, max_attempts=2), self.node('after', "open('forbidden','w').write('x')", depends_on=['bad'])])
        result = self.run_cli('--execute', expected=1)
        self.assertEqual((self.root / 'count').read_text(), '2')
        self.assertEqual(len(result['nodes'][0]['attempts']), 2)
        self.assertEqual(result['nodes'][1]['status'], 'blocked')
        self.assertFalse((self.root / 'forbidden').exists())

    def test_timeout_and_total_budget_stop_followup(self):
        self.write([self.node('slow', 'import time; time.sleep(10)'), self.node('after', "open('bad','w').write('x')")], maximum=0.15)
        began = time.monotonic()
        result = self.run_cli('--execute', expected=1)
        self.assertLess(time.monotonic() - began, 3)
        self.assertEqual(result['nodes'][0]['attempts'][0]['status'], 'timeout')
        self.assertEqual(result['nodes'][1]['status'], 'blocked')
        self.assertFalse((self.root / 'bad').exists())

    def test_human_gate_requires_explicit_node(self):
        self.write([self.node(code="open('gate','w').write('yes')", human_gate=True)])
        result = self.run_cli('--execute', expected=1)
        self.assertEqual(result['nodes'][0]['status'], 'gated')
        self.assertFalse((self.root / 'gate').exists())
        self.output = self.root / 'approved.json'
        self.assertEqual(self.run_cli('--execute', '--approve-node', 'check')['status'], 'passed')
        self.assertTrue((self.root / 'gate').exists())

    def test_cycles_unknown_dependencies_and_boolean_limits_refused(self):
        cases = [[self.node('a', depends_on=['b']), self.node('b', depends_on=['a'])],
                 [self.node(depends_on=['missing'])], [self.node(timeout_seconds=True)],
                 [self.node(max_attempts=True)], [self.node(human_gate='yes')]]
        for nodes in cases:
            with self.subTest(nodes=nodes):
                self.write(nodes)
                self.run_cli('--execute', expected=2)
                self.assertFalse(self.output.exists())

    def test_unknown_approval_and_duplicate_json_rejected(self):
        self.write([self.node()])
        self.run_cli('--execute', '--approve-node', 'missing', expected=2)
        self.plan.write_text('{"version":1,"version":1,"max_seconds":1,"nodes":[]}')
        self.run_cli('--execute', expected=2)
        self.assertFalse(self.output.exists())

    def test_existing_output_and_lock_preserved(self):
        self.write([self.node()])
        self.output.write_text('original')
        self.run_cli('--execute', expected=2)
        self.assertEqual(self.output.read_text(), 'original')
        self.assertFalse(Path(str(self.output) + '.lock').exists())
        self.output.unlink()
        lock = Path(str(self.output) + '.lock')
        lock.write_text('another writer')
        self.run_cli('--execute', expected=2)
        self.assertEqual(lock.read_text(), 'another writer')
        self.assertFalse(self.output.exists())

    @unittest.skipUnless(hasattr(os, 'symlink'), 'symlink support required')
    def test_symlink_output_and_source_refused(self):
        self.write([self.node()])
        victim = self.root / 'victim'
        victim.write_text('keep')
        self.output.symlink_to(victim)
        self.run_cli('--execute', expected=2)
        self.assertEqual(victim.read_text(), 'keep')
        self.output.unlink()
        real = self.root / 'real-plan.json'
        self.plan.rename(real)
        self.plan.symlink_to(real)
        self.run_cli('--execute', expected=2)
        self.assertFalse(self.output.exists())

    def test_output_limit_marks_failure_and_truncates(self):
        self.write([self.node(code="print('x'*200000)")])
        result = self.run_cli('--execute', expected=1)
        attempt = result['nodes'][0]['attempts'][0]
        self.assertEqual(attempt['status'], 'output_limit')
        self.assertTrue(attempt['stdout_truncated'])
        self.assertLessEqual(len(attempt['stdout']), 65536)

    def test_no_shell_expansion_and_missing_executable(self):
        self.write([self.node(argv=[sys.executable, '-c', 'import sys; print(sys.argv[1])', '$(touch forbidden); echo bad'])])
        result = self.run_cli('--execute')
        self.assertIn('$(touch forbidden)', result['nodes'][0]['attempts'][0]['stdout'])
        self.assertFalse((self.root / 'forbidden').exists())
        self.output = self.root / 'missing.json'
        self.write([self.node(argv=['/definitely/nonexistent/teach-me'], max_attempts=5)])
        result = self.run_cli('--execute', expected=1)
        self.assertEqual(len(result['nodes'][0]['attempts']), 1)
        self.assertEqual(result['nodes'][0]['attempts'][0]['status'], 'launch_failed')

    def test_cleanup_denial_is_not_a_launch_failure_and_blocks_followup(self):
        spec = importlib.util.spec_from_file_location('teach_me_runtime', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.write([self.node('first'), self.node('later', "open('bad','w').write('x')")])
        args = SimpleNamespace(plan=self.plan, root=self.root, output=self.output,
                               approve_node=[], execute=True)
        with patch.object(module, 'stop_child', side_effect=PermissionError('cleanup denied')):
            value, code = module.execute(args)
        self.assertEqual(code, 1)
        self.assertEqual(value['nodes'][0]['attempts'][0]['status'], 'cleanup_failed')
        self.assertEqual(value['uncertain_cleanup_nodes'], ['first'])
        self.assertEqual(value['nodes'][1]['status'], 'blocked')
        self.assertFalse((self.root / 'bad').exists())

    @unittest.skipUnless(os.name == 'posix', 'POSIX process-group cleanup')
    def test_sigterm_records_interruption_and_kills_child(self):
        code = "import os,time; open('child.pid','w').write(str(os.getpid())); time.sleep(10); open('late','w').write('bad')"
        self.write([self.node(code=code)])
        process = subprocess.Popen(self.command('--execute'), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            until = time.monotonic() + 3
            while not (self.root / 'child.pid').exists() and time.monotonic() < until:
                time.sleep(0.01)
            self.assertTrue((self.root / 'child.pid').exists())
            process.send_signal(signal.SIGTERM)
            stdout, stderr = process.communicate(timeout=5)
            self.assertEqual(process.returncode, 1, stdout + stderr)
            self.assertEqual(json.loads(self.output.read_text())['status'], 'interrupted')
            pid = int((self.root / 'child.pid').read_text())
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)
            self.assertFalse((self.root / 'late').exists())
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()

    @unittest.skipUnless(os.name == 'posix', 'POSIX process-group cleanup')
    def test_background_same_group_descendant_does_not_survive(self):
        inner = "import time; time.sleep(.5); open('descendant','w').write('bad')"
        code = 'import subprocess,sys; subprocess.Popen([sys.executable,"-c",' + repr(inner) + '])'
        self.write([self.node(code=code)])
        process = subprocess.run(self.command('--execute'), capture_output=True,
                                 text=True, timeout=10)
        self.assertIn(process.returncode, (0, 1), process.stderr + process.stdout)
        result = json.loads(process.stdout)
        attempt = result['nodes'][0]['attempts'][0]
        if process.returncode == 0:
            self.assertEqual(attempt['status'], 'passed')
        else:
            # macOS can deny a final group signal after the direct child exits.
            # The runner must report uncertainty, never invent successful cleanup.
            self.assertEqual(attempt['status'], 'cleanup_failed')
            self.assertEqual(attempt['exit_code'], 0)
            self.assertEqual(result['uncertain_cleanup_nodes'], ['check'])
        time.sleep(0.65)
        # Neither a zero exit nor an honest denial excuses a surviving writer.
        self.assertFalse((self.root / 'descendant').exists())


if __name__ == '__main__':
    unittest.main()
