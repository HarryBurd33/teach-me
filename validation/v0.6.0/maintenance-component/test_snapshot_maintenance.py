"""Executed isolated retirement safety cases; no real learner stores."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

DEFAULT = Path(__file__).resolve().parents[1] / 'candidate' / 'teach-me'
SKILL = Path(os.environ.get('TEACH_ME_SKILL', str(DEFAULT))).resolve()
sys.path.insert(0, str(SKILL / 'scripts'))
import journey
import journey_versions as versions
import snapshot_maintenance as maintenance
import transfer
from storage import StorageError


class SnapshotMaintenance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.workspace = self.root / 'workspace'; self.workspace.mkdir()
        self.store = self.root / 'store'; self.store.mkdir()
        self.archives = self.root / 'archives'; self.archives.mkdir()
        self.cli('journey.py', 'init', '--root', self.workspace, '--id', 'algebra',
                 '--topic', 'Algebra', '--goal', 'Explain an example')
        self.j = self.workspace / 'learning/algebra'
        self.revisions = []
        tip = 'none'
        for i in range(4):
            (self.j / 'plan.md').write_bytes(('Synthetic plan %d\n' % i).encode())
            value = versions.snapshot(self.j, self.store, tip)
            tip = value['revision']; self.revisions.append(tip)
        self.before = self.bytes(self.store)
        self.output = self.root / 'plan.json'

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def bytes(folder):
        return {p.name: p.read_bytes() for p in folder.iterdir() if p.is_file()}

    def cli(self, name, *args, ok=True):
        p = subprocess.run([sys.executable, '-B', str(SKILL / 'scripts' / name),
                            *map(str, args)], capture_output=True, text=True, timeout=20)
        self.assertEqual(p.returncode, 0 if ok else 2, p.stderr + p.stdout)
        return json.loads(p.stdout) if ok else p.stderr

    def make_plan(self, revisions=None):
        return maintenance.plan(self.store, revisions or self.revisions[:2], self.output)

    def apply(self, value, **kwargs):
        return maintenance.apply(self.store, self.output, self.archives,
                                 value['plan_sha256'], **dict(approve=True, **kwargs))

    def assert_protected(self):
        for name in ['HEAD.json'] + [rev + '.zip' for rev in self.revisions[2:]]:
            self.assertEqual((self.store / name).read_bytes(), self.before[name])

    def verify_archive(self, value):
        target = self.archives / value['plan_sha256']
        manifest = json.loads((target / 'archive-manifest.json').read_bytes())
        self.assertEqual(set(manifest), {'version', 'plan', 'files'})
        self.assertEqual(manifest['plan'], value)
        self.assertEqual(set(manifest['files']), {rev + '.zip' for rev in self.revisions[:2]})
        for name, metadata in manifest['files'].items():
            raw = (target / name).read_bytes()
            self.assertEqual(raw, self.before[name])
            self.assertEqual(metadata, {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)})
        return target

    def test_cli_plan_apply_exact_archive_and_restore(self):
        value = self.cli('snapshot_maintenance.py', 'plan', '--store', self.store,
                         '--revisions', *reversed(self.revisions[:2]), '--output', self.output)
        self.assertEqual(set(value), maintenance.PLAN_KEYS)
        independent = {'HEAD.json': hashlib.sha256(self.before['HEAD.json']).hexdigest()}
        independent.update({n: hashlib.sha256(b).hexdigest() for n, b in self.before.items() if n.endswith('.zip')})
        canonical = lambda v: (json.dumps(v, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False) + '\n').encode()
        self.assertEqual(value['store_sha256'], hashlib.sha256(canonical(independent)).hexdigest())
        unsigned = {k: v for k, v in value.items() if k != 'plan_sha256'}
        self.assertEqual(value['plan_sha256'], hashlib.sha256(canonical(unsigned)).hexdigest())
        result = self.cli('snapshot_maintenance.py', 'apply', '--store', self.store,
                          '--plan', self.output, '--archive-root', self.archives,
                          '--expected-plan-sha256', value['plan_sha256'], '--approve')
        self.assertFalse(result['head_changed']); self.assertFalse(result['automatic_replay'])
        target = self.verify_archive(value); self.assert_protected()
        self.assertEqual(set(self.bytes(self.store)), {'HEAD.json'} | {r + '.zip' for r in self.revisions[2:]})
        self.assertFalse(list(self.archives.glob(maintenance.STAGE_PREFIX + '*')))
        receiving = self.root / 'receiving'; receiving.mkdir()
        self.cli('transfer.py', 'unpack', '--archive', target / (self.revisions[0] + '.zip'),
                 '--root', receiving, '--id', 'algebra')
        self.assertEqual((receiving / 'learning/algebra/plan.md').read_bytes(), b'Synthetic plan 0\n')
        self.assertFalse((target / 'HEAD.json').exists())

    def test_protected_unknown_duplicate_empty_and_bad_hash_refused(self):
        cases = [[r] for r in self.revisions[2:]] + [[self.revisions[0]] * 2, ['0' * 64], [], ['../unsafe'], [True]]
        for selected in cases:
            with self.subTest(selected=selected), self.assertRaises(StorageError):
                maintenance.plan(self.store, selected, self.output)
            self.assertEqual(self.bytes(self.store), self.before)
            self.assertFalse(self.output.exists())

    def test_uninitialized_store_refused(self):
        empty = self.root / 'empty'; empty.mkdir()
        with self.assertRaises(StorageError): maintenance.plan(empty, self.revisions[:1], self.output)
        self.assertFalse(self.output.exists())

    def test_changed_head_raw_bytes_invalidates_plan(self):
        value = self.make_plan()
        head = json.loads(self.before['HEAD.json'])
        (self.store / 'HEAD.json').write_text(json.dumps(head, indent=4))
        with self.assertRaisesRegex(StorageError, 'Store changed'): self.apply(value)
        self.assertTrue(all((self.store / (r + '.zip')).exists() for r in self.revisions))
        self.assertEqual(list(self.archives.iterdir()), [])

    def test_added_snapshot_invalidates_plan(self):
        value = self.make_plan(); (self.j / 'plan.md').write_bytes(b'Fifth snapshot')
        versions.snapshot(self.j, self.store, self.revisions[-1])
        with self.assertRaisesRegex(StorageError, 'Store changed'): self.apply(value)
        self.assertTrue(all((self.store / (r + '.zip')).exists() for r in self.revisions))

    def test_strict_json_fields_hash_types_and_expected_hash_refused(self):
        value = self.make_plan(); original = self.output.read_bytes()
        variants = [b'{"version":1,"version":1}', b'{"version":NaN}', b'\xff', b'[]']
        altered = [dict(value, version=True), dict(value, extra=1), dict(value, plan_sha256='0' * 64),
                   dict(value, revisions=list(reversed(value['revisions']))), dict(value, protected=[]),
                   dict(value, journey_id='../escape')]
        variants += [json.dumps(v).encode() for v in altered]
        for raw in variants:
            self.output.write_bytes(raw)
            with self.subTest(raw=raw), self.assertRaises((ValueError, UnicodeError)):
                self.apply(value)
            self.assertEqual(self.bytes(self.store), self.before)
            self.assertEqual(list(self.archives.iterdir()), [])
        self.output.write_bytes(original)
        for expected in ['0' * 64, 'not-a-digest', True]:
            with self.assertRaises(StorageError):
                maintenance.apply(self.store, self.output, self.archives, expected, True)

    def test_requires_approval_and_plan_output_create_new(self):
        value = self.make_plan(); raw = self.output.read_bytes()
        with self.assertRaises(StorageError):
            maintenance.apply(self.store, self.output, self.archives, value['plan_sha256'])
        with self.assertRaises(StorageError): self.make_plan()
        self.assertEqual(self.output.read_bytes(), raw)
        self.assertEqual(self.bytes(self.store), self.before)

    def test_store_unknown_entry_and_orphan_stages_refused(self):
        for name, directory in [('foreign.txt', False), ('.teach-me-snapshot-orphan', True), ('.teach-me-head-orphan', False)]:
            path = self.store / name
            if directory: path.mkdir()
            else: path.write_bytes(b'preserve')
            with self.assertRaises(StorageError): self.make_plan()
            if directory: path.rmdir()
            else: self.assertEqual(path.read_bytes(), b'preserve'); path.unlink()
        self.assertEqual(self.bytes(self.store), self.before)

    def test_store_and_archive_locks_preserved(self):
        value = self.make_plan()
        for directory, name in [(self.store, versions.LOCK), (self.archives, maintenance.ARCHIVE_LOCK)]:
            path = directory / name; path.write_bytes(b'foreign owner')
            with self.assertRaisesRegex(StorageError, 'lock exists'): self.apply(value)
            self.assertEqual(path.read_bytes(), b'foreign owner'); path.unlink()
            self.assertEqual(self.bytes(self.store), self.before)

    def test_symlink_store_plan_archive_and_revision_refused(self):
        value = self.make_plan()
        for original in [self.store, self.output, self.archives]:
            link = self.root / ('linked-' + original.name); link.symlink_to(original, target_is_directory=original.is_dir())
            args = [self.store, self.output, self.archives]
            args[[self.store, self.output, self.archives].index(original)] = link
            with self.assertRaises(StorageError): maintenance.apply(*args, value['plan_sha256'], True)
        selected = self.store / (self.revisions[0] + '.zip'); raw = selected.read_bytes(); selected.unlink()
        external = self.root / 'selected.zip'; external.write_bytes(raw); selected.symlink_to(external)
        with self.assertRaises(StorageError): self.apply(value)
        self.assertEqual(external.read_bytes(), raw)

    def test_archive_ancestry_and_plan_inside_store_refused(self):
        value = self.make_plan()
        inside = self.store / 'archives'; inside.mkdir()
        for archive in [self.store, inside, self.root]:
            with self.assertRaises(StorageError):
                maintenance.apply(self.store, self.output, archive, value['plan_sha256'], True)
        inside.rmdir()
        with self.assertRaises(StorageError): maintenance.plan(self.store, self.revisions[:1], self.store / 'new.json')

    def test_existing_empty_foreign_directory_preserved(self):
        value = self.make_plan(); target = self.archives / value['plan_sha256']; target.mkdir()
        inode = target.stat().st_ino
        with self.assertRaisesRegex(StorageError, 'destination exists'): self.apply(value)
        self.assertEqual(target.stat().st_ino, inode); self.assertEqual(list(target.iterdir()), [])
        self.assertEqual(self.bytes(self.store), self.before)

    def test_foreign_destination_racing_publication_preserved(self):
        value = self.make_plan(); original = maintenance.publish_backup
        target = self.archives / value['plan_sha256']
        def race(stage, destination, manifest):
            destination.mkdir(); (destination / 'foreign.txt').write_bytes(b'foreign')
            return original(stage, destination, manifest)
        with mock.patch.object(maintenance, 'publish_backup', side_effect=race):
            with self.assertRaisesRegex(StorageError, 'fresh plan'): self.apply(value)
        self.assertEqual((target / 'foreign.txt').read_bytes(), b'foreign')
        self.assertEqual(set(p.name for p in target.iterdir()), {'foreign.txt'})
        self.assertEqual(self.bytes(self.store), self.before)

    def test_injected_second_copy_failure_never_deletes_source(self):
        value = self.make_plan(); original = maintenance.copy_revision; calls = []
        def copy(source, destination):
            calls.append(source)
            if len(calls) == 2: raise OSError('injected second copy failure')
            return original(source, destination)
        with mock.patch.object(maintenance, 'copy_revision', side_effect=copy):
            with self.assertRaisesRegex(StorageError, 'fresh plan'): self.apply(value)
        self.assertEqual(self.bytes(self.store), self.before)
        self.assertFalse((self.archives / value['plan_sha256']).exists())
        self.assertTrue(list(self.archives.glob(maintenance.STAGE_PREFIX + '*')))

    def test_copy_corruption_or_verification_failure_never_deletes_source(self):
        value = self.make_plan(); original = maintenance.copy_revision
        def corrupt(source, destination):
            original(source, destination); destination.write_bytes(b'corrupt')
        with mock.patch.object(maintenance, 'copy_revision', side_effect=corrupt):
            with self.assertRaises(StorageError): self.apply(value)
        self.assertEqual(self.bytes(self.store), self.before)

    def test_final_backup_verification_failure_never_deletes_source(self):
        value = self.make_plan(); original = maintenance.verify_backup
        target = self.archives / value['plan_sha256']
        def verify(directory, manifest):
            if directory == target:
                name = next(iter(manifest['files']))
                (directory / name).write_bytes(b'injected final corruption')
            return original(directory, manifest)
        with mock.patch.object(maintenance, 'verify_backup', side_effect=verify):
            with self.assertRaisesRegex(StorageError, 'verification failed'): self.apply(value)
        self.assertEqual(self.bytes(self.store), self.before)
        self.assertTrue((target / 'archive-manifest.json').is_file())

    def test_invalid_zip_store_cli_refuses_without_traceback(self):
        selected = self.store / (self.revisions[0] + '.zip'); selected.unlink()
        raw = b'not a zip archive'
        invalid = hashlib.sha256(raw).hexdigest()
        (self.store / (invalid + '.zip')).write_bytes(raw)
        error = self.cli('snapshot_maintenance.py', 'plan', '--store', self.store,
                         '--revisions', invalid, '--output', self.output, ok=False)
        self.assertNotIn('Traceback', error)
        self.assertFalse(self.output.exists())

    def test_injected_publication_failure_leaves_source_and_partial_archive(self):
        value = self.make_plan(); original = maintenance.os.link
        target = self.archives / value['plan_sha256']; calls = []
        def link(source, destination):
            if Path(destination).parent == target:
                calls.append(destination)
                if len(calls) == 2: raise OSError('injected publication failure')
            return original(source, destination)
        with mock.patch.object(maintenance.os, 'link', side_effect=link):
            with self.assertRaisesRegex(StorageError, 'fresh plan'): self.apply(value)
        self.assertEqual(self.bytes(self.store), self.before)
        self.assertTrue(target.is_dir()); self.assertFalse((target / 'archive-manifest.json').exists())
        self.assertEqual(len(list(target.glob('*.zip'))), 1)

    def test_second_unlink_failure_retains_complete_restorable_backup(self):
        value = self.make_plan(); original = maintenance.remove_revision; calls = []
        def remove(path):
            calls.append(path)
            if len(calls) == 2: raise OSError('injected second removal failure')
            return original(path)
        with mock.patch.object(maintenance, 'remove_revision', side_effect=remove):
            with self.assertRaisesRegex(StorageError, 'Inspect the archive and actual store'): self.apply(value)
        target = self.verify_archive(value); self.assert_protected()
        self.assertEqual(sum((self.store / (r + '.zip')).exists() for r in self.revisions[:2]), 1)
        for i, revision in enumerate(self.revisions[:2]):
            receiving = self.root / ('receiving%d' % i); receiving.mkdir()
            transfer.unpack(target / (revision + '.zip'), receiving, 'algebra')
            self.assertTrue((receiving / 'learning/algebra/progress.json').is_file())
        with self.assertRaises(StorageError): self.apply(value)
        self.assertEqual((target / 'archive-manifest.json').read_bytes(), versions.encoded(json.loads((target / 'archive-manifest.json').read_bytes())))

    def test_archive_orphan_staging_refused(self):
        value = self.make_plan(); orphan = self.archives / (maintenance.STAGE_PREFIX + 'foreign'); orphan.mkdir()
        (orphan / 'evidence').write_bytes(b'preserve')
        with self.assertRaisesRegex(StorageError, 'orphan staging'): self.apply(value)
        self.assertEqual((orphan / 'evidence').read_bytes(), b'preserve')
        self.assertEqual(self.bytes(self.store), self.before)

    def test_selected_total_limit_before_copy(self):
        with mock.patch.object(maintenance, 'SELECTED_LIMIT', 1):
            with self.assertRaisesRegex(StorageError, '64 MiB'): self.make_plan()
        self.assertEqual(self.bytes(self.store), self.before)
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
