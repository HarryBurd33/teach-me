"""Original executed snapshot/merge cases; no real learner records or services."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import warnings
import zipfile

SKILL = Path(os.environ.get('TEACH_ME_SKILL', str(Path(__file__).resolve().parents[1] / 'teach-me'))).resolve()
SCRIPTS = SKILL / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import journey_versions as versions
import transfer


class JourneyVersions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.workspace = self.root / 'workspace'; self.workspace.mkdir()
        self.store = self.root / 'store'; self.store.mkdir()
        self.cli('journey.py', 'init', '--root', self.workspace, '--id', 'algebra',
                 '--topic', 'Algebra', '--goal', 'Explain a new example')
        self.j = self.workspace / 'learning/algebra'
        for name in ('knowledge.md', 'practice.md', 'harness-project.md', 'learning-pilot.md'):
            (self.j / name).write_bytes(('Exact UTF-8 record — ' + name + '\n').encode())

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, name, *args, ok=True):
        p = subprocess.run([sys.executable, '-B', str(SCRIPTS / name), *map(str, args)],
                           capture_output=True, text=True, timeout=15)
        self.assertEqual(p.returncode, 0 if ok else 2, p.stderr + p.stdout)
        return json.loads(p.stdout) if ok else p.stderr

    def run_versions(self, *args, **kwargs):
        return self.cli('journey_versions.py', *args, **kwargs)

    def files(self, folder):
        return {n: (folder / n).read_bytes() for n in transfer.ALLOWED if (folder / n).exists()}

    def packed(self, name, files=None):
        target = self.root / (name + '.zip')
        if files is None:
            self.cli('transfer.py', 'pack', '--journey', self.j, '--output', target)
        else:
            parent = self.root / ('tree-' + name); parent.mkdir()
            j = parent / 'algebra'; j.mkdir()
            for n, b in files.items(): (j / n).write_bytes(b)
            self.cli('transfer.py', 'pack', '--journey', j, '--output', target)
        return target

    def snapshot(self, expected='none'):
        return self.run_versions('snapshot', '--journey', self.j, '--store', self.store,
                                 '--expected-head', expected)

    def inputs(self, local_changes=None, incoming_changes=None):
        base = self.files(self.j); local = dict(base); incoming = dict(base)
        for mapping, changes in [(local, local_changes or {}), (incoming, incoming_changes or {})]:
            for name, value in changes.items():
                if value is None: mapping.pop(name, None)
                else: mapping[name] = value
        return self.packed('base', base), self.packed('local', local), self.packed('incoming', incoming)

    def compare(self, paths):
        return self.run_versions('compare', '--base', paths[0], '--local', paths[1],
                                 '--incoming', paths[2], '--output', self.root / 'report.json')

    def merge(self, paths, **kwargs):
        extra = kwargs.pop('extra', [])
        return self.run_versions('merge', '--base', paths[0], '--local', paths[1],
                                 '--incoming', paths[2], '--output', self.root / 'merged.zip',
                                 *extra, **kwargs)

    def test_seven_file_snapshot_restore_and_previous(self):
        originals = self.files(self.j)
        first = self.snapshot()
        self.assertTrue(first['snapshot'])
        self.assertIsNone(first['previous'])
        state = self.run_versions('status', '--store', self.store)
        self.assertEqual(state['head']['revision'], first['revision'])
        (self.j / 'plan.md').write_bytes(b'New plan\n')
        second = self.snapshot(first['revision'])
        self.assertEqual(second['previous'], first['revision'])
        receiving = self.root / 'receiving'; receiving.mkdir()
        restored = self.run_versions('restore', '--store', self.store, '--revision', first['revision'],
                                     '--root', receiving, '--id', 'algebra')
        self.assertFalse(restored['automatic_resume'])
        self.assertFalse(restored['head_changed'])
        self.assertEqual(self.files(receiving / 'learning/algebra'), originals)
        self.assertEqual(len(originals), 7)
        self.run_versions('restore', '--store', self.store, '--revision', first['revision'],
                          '--root', receiving, '--id', 'algebra', ok=False)

    def test_identical_snapshot_is_noop_and_stale_head_refused(self):
        first = self.snapshot(); head = (self.store / 'HEAD.json').read_bytes()
        second = self.snapshot(first['revision'])
        self.assertTrue(second['unchanged'])
        self.assertEqual((self.store / 'HEAD.json').read_bytes(), head)
        self.run_versions('snapshot', '--journey', self.j, '--store', self.store,
                          '--expected-head', 'none', ok=False)
        self.assertEqual((self.store / 'HEAD.json').read_bytes(), head)
        self.assertEqual(len(list(self.store.glob('*.zip'))), 1)

    def test_failed_activation_preserves_old_head_and_new_inactive_revision(self):
        first = self.snapshot(); before = (self.store / 'HEAD.json').read_bytes()
        (self.j / 'plan.md').write_bytes(b'Changed current plan')
        original = self.files(self.j)
        with mock.patch.object(versions.os, 'replace', side_effect=OSError('injected HEAD replacement failure')):
            with self.assertRaises(OSError): versions.snapshot(self.j, self.store, first['revision'])
        self.assertEqual((self.store / 'HEAD.json').read_bytes(), before)
        self.assertEqual(len(list(self.store.glob('*.zip'))), 2)
        state = self.run_versions('status', '--store', self.store)
        self.assertEqual(state['head']['revision'], first['revision'])
        self.assertEqual(self.files(self.j), original)
        self.assertFalse((self.store / versions.LOCK).exists())

    def test_initial_activation_failure_has_no_invented_head(self):
        with mock.patch.object(versions, 'publish_head', side_effect=OSError('injected activation failure')):
            with self.assertRaises(OSError): versions.snapshot(self.j, self.store, 'none')
        state = self.run_versions('status', '--store', self.store)
        self.assertFalse(state['initialized'])
        self.assertIsNone(state['head'])
        self.assertEqual(len(state['available_revisions']), 1)
        self.assertFalse(state['automatic_recovery'])

    def test_two_snapshot_processes_same_expected_head_have_one_winner(self):
        command = [sys.executable, '-B', str(SCRIPTS / 'journey_versions.py'), 'snapshot',
                   '--journey', str(self.j), '--store', str(self.store), '--expected-head', 'none']
        children = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
        results = []
        for p in children:
            stdout, stderr = p.communicate(timeout=10); results.append((p.returncode, stdout, stderr))
        self.assertEqual(sum(code == 0 for code, _, _ in results), 1, results)
        self.assertTrue(self.run_versions('status', '--store', self.store)['initialized'])

    def test_unknown_foreign_or_symlink_store_refused(self):
        extra = self.store / 'unrelated.txt'; extra.write_text('preserve')
        self.run_versions('snapshot', '--journey', self.j, '--store', self.store, '--expected-head', 'none', ok=False)
        self.assertEqual(extra.read_text(), 'preserve'); extra.unlink()
        self.snapshot()
        head = json.loads((self.store / 'HEAD.json').read_text()); head['journey_id'] = 'different'
        (self.store / 'HEAD.json').write_text(json.dumps(head))
        self.run_versions('status', '--store', self.store, ok=False)
        self.assertEqual(json.loads((self.store / 'HEAD.json').read_text())['journey_id'], 'different')
        linked = self.root / 'linked-store'; linked.symlink_to(self.store, target_is_directory=True)
        self.run_versions('status', '--store', linked, ok=False)

    def test_tampered_revision_and_unknown_restore_refused(self):
        first = self.snapshot(); path = self.store / (first['revision'] + '.zip')
        path.write_bytes(path.read_bytes() + b'changed')
        self.run_versions('status', '--store', self.store, ok=False)
        receiving = self.root / 'receiving'; receiving.mkdir()
        self.run_versions('restore', '--store', self.store, '--revision', first['revision'],
                          '--root', receiving, '--id', 'algebra', ok=False)
        self.assertFalse((receiving / 'learning/algebra').exists())

    def test_store_inside_journey_and_held_lock_refused(self):
        inside = self.j / 'store'; inside.mkdir()
        self.run_versions('snapshot', '--journey', self.j, '--store', inside, '--expected-head', 'none', ok=False)
        self.assertEqual(list(inside.iterdir()), [])
        lock = self.store / versions.LOCK; lock.write_bytes(b'foreign lock')
        self.run_versions('status', '--store', self.store, ok=False)
        self.assertEqual(lock.read_bytes(), b'foreign lock')

    def test_clean_merge_preserves_independent_changes_and_deletion(self):
        paths = self.inputs({'plan.md': b'Local plan', 'knowledge.md': None},
                            {'sources.md': b'Incoming sources'})
        before = [p.read_bytes() for p in paths]
        report = self.compare(paths)
        self.assertEqual(report['conflicts'], [])
        self.assertEqual(report['files']['plan.md']['status'], 'local-only')
        self.assertEqual(report['files']['sources.md']['status'], 'incoming-only')
        result = self.merge(paths); self.assertTrue(result['merged'])
        actual = transfer.inspect_archive(self.root / 'merged.zip')
        self.assertEqual(actual['plan.md'], b'Local plan')
        self.assertEqual(actual['sources.md'], b'Incoming sources')
        self.assertNotIn('knowledge.md', actual)
        self.assertEqual([p.read_bytes() for p in paths], before)

    def test_identical_changes_and_new_pilot_merge(self):
        (self.j / 'learning-pilot.md').unlink()
        paths = self.inputs({'plan.md': b'Same change'}, {'plan.md': b'Same change', 'learning-pilot.md': b'Pending pilot'})
        report = self.compare(paths)
        self.assertEqual(report['files']['plan.md']['status'], 'identical')
        self.assertEqual(report['files']['learning-pilot.md']['status'], 'incoming-only')
        self.merge(paths)
        self.assertEqual(transfer.inspect_archive(self.root / 'merged.zip')['learning-pilot.md'], b'Pending pilot')

    def test_conflicting_progress_requires_digest_bound_explicit_choice(self):
        state = json.loads((self.j / 'progress.json').read_text())
        left = dict(state, next_action='Local next action'); right = dict(state, next_action='Incoming next action')
        local = json.dumps(left).encode(); incoming = json.dumps(right).encode()
        paths = self.inputs({'progress.json': local}, {'progress.json': incoming})
        report = self.compare(paths)
        self.assertEqual(report['conflicts'], ['progress.json'])
        self.merge(paths, ok=False); self.assertFalse((self.root / 'merged.zip').exists())
        choices = self.root / 'choices.json'
        choices.write_text(json.dumps({'version': 1, 'report_sha256': report['report_sha256'], 'choices': {'progress.json': 'local'}}))
        result = self.merge(paths, extra=['--resolutions', choices])
        self.assertEqual(result['resolved_conflicts'], {'progress.json': 'local'})
        self.assertEqual(transfer.inspect_archive(self.root / 'merged.zip')['progress.json'], local)

    def test_delete_versus_edit_is_conflict_not_silent_loss(self):
        paths = self.inputs({'practice.md': None}, {'practice.md': b'Incoming attempt summary'})
        report = self.compare(paths)
        self.assertEqual(report['conflicts'], ['practice.md'])
        choices = self.root / 'choices.json'; choices.write_text(json.dumps({'version': 1,
            'report_sha256': report['report_sha256'], 'choices': {'practice.md': 'incoming'}}))
        self.merge(paths, extra=['--resolutions', choices])
        self.assertEqual(transfer.inspect_archive(self.root / 'merged.zip')['practice.md'], b'Incoming attempt summary')

    def test_stale_report_unknown_or_missing_resolution_choices_refused(self):
        paths = self.inputs({'plan.md': b'Local'}, {'plan.md': b'Incoming'})
        report = self.compare(paths); choices = self.root / 'choices.json'
        invalid = [dict(version=1, report_sha256='0' * 64, choices={'plan.md': 'local'}),
                   dict(version=1, report_sha256=report['report_sha256'], choices={}),
                   dict(version=1, report_sha256=report['report_sha256'], choices={'plan.md': 'local', 'auth.json': 'base'}),
                   dict(version=1, report_sha256=report['report_sha256'], choices={'plan.md': 'invented'})]
        for value in invalid:
            choices.write_text(json.dumps(value)); self.merge(paths, extra=['--resolutions', choices], ok=False)
            self.assertFalse((self.root / 'merged.zip').exists())
        (self.root / 'tree-incoming/algebra/plan.md').write_bytes(b'Later incoming change')
        paths[2].unlink()
        self.cli('transfer.py', 'pack', '--journey', self.root / 'tree-incoming/algebra', '--output', paths[2])
        choices.write_text(json.dumps({'version': 1, 'report_sha256': report['report_sha256'], 'choices': {'plan.md': 'local'}}))
        self.merge(paths, extra=['--resolutions', choices], ok=False)

    def test_different_journey_id_refused_before_comparison_output(self):
        paths = self.inputs()
        other = self.root / 'other'; other.mkdir()
        self.cli('journey.py', 'init', '--root', other, '--id', 'different', '--topic', 'Topic', '--goal', 'New goal')
        paths[2].unlink(); self.cli('transfer.py', 'pack', '--journey', other / 'learning/different', '--output', paths[2])
        self.run_versions('compare', '--base', paths[0], '--local', paths[1], '--incoming', paths[2],
                          '--output', self.root / 'report.json', ok=False)
        self.assertFalse((self.root / 'report.json').exists())

    def test_unsafe_duplicate_and_traversal_archive_refused(self):
        paths = self.inputs(); original = paths[2].read_bytes()
        for extra in ['../escape', 'progress.json']:
            paths[2].write_bytes(original)
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                with zipfile.ZipFile(paths[2], 'a') as archive: archive.writestr(extra, b'unsafe')
            self.merge(paths, ok=False)
            self.assertFalse((self.root / 'merged.zip').exists())
        self.assertFalse((self.root / 'escape').exists())

    def test_existing_outputs_and_publication_race_preserve_foreign_bytes(self):
        paths = self.inputs(); output = self.root / 'merged.zip'; output.write_bytes(b'original')
        self.merge(paths, ok=False); self.assertEqual(output.read_bytes(), b'original')
        report = self.root / 'report.json'
        def racing_link(source, target):
            Path(target).write_bytes(b'foreign complete report')
            raise FileExistsError('injected winner')
        with mock.patch.object(versions.os, 'link', side_effect=racing_link):
            with self.assertRaises(FileExistsError): versions.compare(*paths, report)
        self.assertEqual(report.read_bytes(), b'foreign complete report')
        self.assertFalse(list(self.root.glob('.teach-me-version-*')))

    def test_input_change_detected_before_publication(self):
        paths = self.inputs(); output = self.root / 'report.json'
        with mock.patch.object(versions, 'unchanged_inputs', side_effect=StorageError('injected changed archive')):
            with self.assertRaises(StorageError): versions.compare(*paths, output)
        self.assertFalse(output.exists())


from storage import StorageError

if __name__ == '__main__':
    unittest.main(verbosity=2)
