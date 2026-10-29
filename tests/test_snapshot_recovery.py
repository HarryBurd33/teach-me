"""Isolated recovery fault tests; no real learner-store writes."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

DEFAULT = Path(__file__).resolve().parents[1] / 'teach-me'
SKILL = Path(os.environ.get('TEACH_ME_SKILL', str(DEFAULT))).resolve()
sys.path.insert(0, str(SKILL / 'scripts'))
import journey_versions as versions
import snapshot_maintenance as maintenance
import snapshot_recovery as recovery
import transfer
from storage import StorageError


class SnapshotRecovery(unittest.TestCase):
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
        for i in range(6):
            (self.j / 'plan.md').write_bytes(('Synthetic plan %d\n' % i).encode())
            tip = versions.snapshot(self.j, self.store, tip)['revision']
            self.revisions.append(tip)
        self.before = self.bytes(self.store)
        self.original_path = self.root / 'original.json'
        self.original = maintenance.plan(self.store, self.revisions[:4], self.original_path)
        self.archive = self.archives / self.original['plan_sha256']
        # Real maintenance publishes its complete archive, removes one source,
        # then suffers an injected failure. Its abandoned stage is preserved.
        real_remove = maintenance.remove_revision
        calls = []
        def interrupt(path):
            calls.append(path)
            if len(calls) == 2:
                raise OSError('injected maintenance interruption')
            real_remove(path)
        with mock.patch.object(maintenance, 'remove_revision', side_effect=interrupt):
            with self.assertRaises(StorageError):
                maintenance.apply(self.store, self.original_path, self.archives,
                                  self.original['plan_sha256'], True)
        self.archive_bytes = self.bytes(self.archive)
        self.stage_names = sorted(p.name for p in self.archives.glob(maintenance.STAGE_PREFIX + '*'))
        self.output = self.root / 'recovery.json'

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def bytes(folder):
        return {p.name: p.read_bytes() for p in folder.iterdir() if p.is_file()}

    def cli(self, script, *args, ok=True):
        result = subprocess.run([sys.executable, '-B', str(SKILL / 'scripts' / script),
                                 *map(str, args)], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0 if ok else 2, result.stderr + result.stdout)
        return json.loads(result.stdout) if ok else result.stderr

    def plan(self, output=None):
        return recovery.plan(self.store, self.archive, output or self.output)

    def apply(self, value, output=None):
        return recovery.apply(self.store, self.archive, output or self.output, value['plan_sha256'], True)

    def assert_preserved(self, store_before=None):
        if store_before is not None:
            self.assertEqual(self.bytes(self.store), store_before)
        self.assertEqual(self.bytes(self.archive), self.archive_bytes)
        for name in ['HEAD.json'] + [r + '.zip' for r in self.revisions[-2:]]:
            self.assertEqual((self.store / name).read_bytes(), self.before[name])
        self.assertEqual(sorted(p.name for p in self.archives.glob(maintenance.STAGE_PREFIX + '*')), self.stage_names)

    def write_manifest(self, value):
        (self.archive / 'archive-manifest.json').write_bytes(versions.encoded(value))

    def test_cli_real_partial_recovery_raw_hashes_restore_and_complete_noop(self):
        value = self.cli('snapshot_recovery.py', 'plan', '--store', self.store,
                         '--archive', self.archive, '--output', self.output)
        self.assertEqual(set(value), recovery.PLAN_KEYS)
        selected = sorted(self.revisions[:4])
        self.assertEqual(value['remaining'], selected[1:])
        self.assertEqual(value['already_absent'], selected[:1])
        self.assertEqual(value['original_plan_sha256'], self.original['plan_sha256'])
        canonical = lambda v: (json.dumps(v, sort_keys=True, ensure_ascii=False,
                                          allow_nan=False, separators=(',', ':')) + '\n').encode()
        for folder, key in [(self.store, 'store_sha256'), (self.archive, 'archive_sha256')]:
            mapping = {name: hashlib.sha256(raw).hexdigest() for name, raw in self.bytes(folder).items()}
            self.assertEqual(value[key], hashlib.sha256(canonical(mapping)).hexdigest())
        self.assertEqual(value['plan_sha256'], hashlib.sha256(canonical({k: v for k, v in value.items() if k != 'plan_sha256'})).hexdigest())
        result = self.cli('snapshot_recovery.py', 'apply', '--store', self.store,
                          '--archive', self.archive, '--plan', self.output,
                          '--expected-plan-sha256', value['plan_sha256'], '--approve')
        self.assertEqual(result['retired'], value['remaining'])
        self.assertFalse(result['head_changed']); self.assertFalse(result['automatic_replay'])
        self.assert_preserved()
        for i, revision in enumerate(self.revisions[:4]):
            target = self.root / ('restored%d' % i); target.mkdir()
            transfer.unpack(self.archive / (revision + '.zip'), target, 'algebra')
            self.assertEqual((target / 'learning/algebra/plan.md').read_bytes(), ('Synthetic plan %d\n' % i).encode())
        complete_path = self.root / 'complete.json'; complete = self.plan(complete_path)
        self.assertEqual(complete['remaining'], [])
        before = self.bytes(self.store)
        with mock.patch.object(recovery, 'remove_revision', side_effect=AssertionError('no removal')):
            self.assertTrue(self.apply(complete, complete_path)['noop'])
        self.assert_preserved(before)

    def test_repeated_partial_failure_requires_fresh_plan(self):
        value = self.plan(); real_remove = recovery.remove_revision; calls = []
        def interrupt(path):
            calls.append(path)
            if len(calls) == 2: raise OSError('injected recovery interruption')
            real_remove(path)
        with mock.patch.object(recovery, 'remove_revision', side_effect=interrupt):
            with self.assertRaisesRegex(StorageError, 'fresh recovery plan'): self.apply(value)
        before = self.bytes(self.store)
        with self.assertRaisesRegex(StorageError, 'changed'): self.apply(value)
        self.assert_preserved(before)
        fresh_path = self.root / 'fresh.json'; fresh = self.plan(fresh_path)
        self.assertEqual(len(fresh['remaining']), len(value['remaining']) - 1)
        self.apply(fresh, fresh_path); self.assert_preserved()

    def test_no_approval_wrong_sha_and_no_overwrite(self):
        value = self.plan(); before = self.bytes(self.store); raw = self.output.read_bytes()
        with self.assertRaisesRegex(StorageError, 'approve'):
            recovery.apply(self.store, self.archive, self.output, value['plan_sha256'])
        for digest in ['0' * 64, 'bad', True]:
            with self.assertRaises(StorageError):
                recovery.apply(self.store, self.archive, self.output, digest, True)
        with self.assertRaises(StorageError): self.plan()
        self.assertEqual(self.output.read_bytes(), raw); self.assert_preserved(before)

    def test_new_current_unselected_snapshot_allowed_but_old_recovery_stale(self):
        value = self.plan()
        (self.j / 'plan.md').write_bytes(b'new current unselected')
        versions.snapshot(self.j, self.store, self.revisions[-1])
        before = self.bytes(self.store)
        with self.assertRaisesRegex(StorageError, 'changed'): self.apply(value)
        fresh_path = self.root / 'fresh.json'; fresh = self.plan(fresh_path)
        self.assertNotEqual(fresh['head'], value['head'])
        self.apply(fresh, fresh_path)
        for name in ['HEAD.json'] + [r + '.zip' for r in fresh['protected']]:
            self.assertEqual((self.store / name).read_bytes(), before[name])
        self.assertEqual(self.bytes(self.archive), self.archive_bytes)

    def test_current_head_or_previous_selected_refused(self):
        for position in ('revision', 'previous'):
            head = json.loads(self.before['HEAD.json'])
            head[position] = sorted(self.revisions[:4])[1]
            (self.store / 'HEAD.json').write_bytes(versions.encoded(head))
            before = self.bytes(self.store)
            with self.assertRaisesRegex(StorageError, 'protected'): self.plan()
            self.assertEqual(self.bytes(self.store), before)
        (self.store / 'HEAD.json').write_bytes(self.before['HEAD.json'])

    def test_changed_raw_head_bytes_invalidates_plan(self):
        value = self.plan(); (self.store / 'HEAD.json').write_text(json.dumps(value['head'], indent=4))
        before = self.bytes(self.store)
        with self.assertRaisesRegex(StorageError, 'changed'): self.apply(value)
        self.assertEqual(self.bytes(self.store), before)

    def test_archive_corruption_including_already_absent_refused(self):
        value = self.plan()
        for revision in sorted(self.revisions[:4]):
            path = self.archive / (revision + '.zip'); original = path.read_bytes()
            path.write_bytes(original + b'changed')
            before = self.bytes(self.store)
            with self.subTest(revision=revision), self.assertRaises(StorageError): self.apply(value)
            self.assertEqual(self.bytes(self.store), before); path.write_bytes(original)

    def test_incomplete_archive_refused_without_repair(self):
        path = self.archive / (self.original['revisions'][0] + '.zip'); path.unlink()
        before = self.bytes(self.store); archive_before = self.bytes(self.archive)
        with self.assertRaises(StorageError): self.plan()
        self.assertEqual(self.bytes(self.store), before)
        self.assertEqual(self.bytes(self.archive), archive_before)
        self.assertFalse(self.output.exists())

    def test_manifest_noncanonical_unknown_files_and_metadata_refused(self):
        raw = self.archive_bytes['archive-manifest.json']; original = json.loads(raw)
        variants = [dict(original, version=True), dict(original, extra=1),
                    dict(original, files={}), dict(original, plan=dict(self.original, extra=1))]
        for metadata in [{'sha256': self.original['revisions'][0], 'size': True},
                         {'sha256': self.original['revisions'][0], 'size': -1},
                         {'sha256': self.original['revisions'][0], 'size': transfer.ARCHIVE_LIMIT + 1},
                         {'sha256': '0' * 64, 'size': 100}, {'sha256': self.original['revisions'][0], 'size': 100, 'extra': 1}]:
            item = json.loads(raw); item['files'][self.original['revisions'][0] + '.zip'] = metadata
            variants.append(item)
        before = self.bytes(self.store)
        for value in variants:
            self.write_manifest(value)
            with self.subTest(value=value), self.assertRaises(StorageError): self.plan()
            self.assertEqual(self.bytes(self.store), before)
        (self.archive / 'archive-manifest.json').write_bytes(json.dumps(original, indent=2).encode())
        with self.assertRaisesRegex(StorageError, 'canonical'): self.plan()
        (self.archive / 'archive-manifest.json').write_bytes(raw)
        foreign = self.archive / 'foreign'; foreign.write_bytes(b'preserve')
        with self.assertRaisesRegex(StorageError, 'unexpected'): self.plan()
        self.assertEqual(foreign.read_bytes(), b'preserve')

    def test_wrong_archive_leaf_and_ancestry_refused(self):
        renamed = self.archives / ('0' * 64); self.archive.rename(renamed)
        with self.assertRaisesRegex(StorageError, 'leaf'):
            recovery.plan(self.store, renamed, self.output)
        renamed.rename(self.archive)
        for archive in [self.store, self.root, self.store / 'inside']:
            with self.assertRaises(StorageError): recovery.plan(self.store, archive, self.output)
        for output in [self.store / 'new.json', self.archive / 'new.json']:
            with self.assertRaises(StorageError): recovery.plan(self.store, self.archive, output)

    def test_current_store_unknown_stages_corrupt_and_foreign_refused(self):
        before = self.bytes(self.store)
        for name, directory in [('foreign', False), ('.teach-me-snapshot-orphan', True), ('.teach-me-head-orphan', False)]:
            path = self.store / name
            if directory: path.mkdir()
            else: path.write_bytes(b'preserve')
            with self.assertRaises(StorageError): self.plan()
            if directory: path.rmdir()
            else: self.assertEqual(path.read_bytes(), b'preserve'); path.unlink()
        path = self.store / (self.revisions[-1] + '.zip'); path.write_bytes(b'corrupt')
        with self.assertRaises((StorageError, zipfile.BadZipFile)): self.plan()
        path.write_bytes(before[path.name])
        foreign = self.foreign_archive()
        target = self.store / (transfer.sha(foreign.read_bytes()) + '.zip'); target.write_bytes(foreign.read_bytes())
        with self.assertRaisesRegex(StorageError, 'identity'): self.plan()
        target.unlink(); self.assert_preserved(before)

    def foreign_archive(self):
        self.cli('journey.py', 'init', '--root', self.workspace, '--id', 'foreign',
                 '--topic', 'Foreign', '--goal', 'Foreign example')
        output = self.root / 'foreign.zip'
        transfer.pack(self.workspace / 'learning/foreign', output)
        return output

    def test_self_consistent_archive_with_foreign_inner_identity_refused(self):
        foreign = self.foreign_archive(); raw = foreign.read_bytes(); digest = transfer.sha(raw)
        old = self.original['revisions'][0]
        manifest = json.loads(self.archive_bytes['archive-manifest.json'])
        original = manifest['plan']; original['revisions'].remove(old); original['revisions'].append(digest)
        original['revisions'].sort(); original.pop('plan_sha256')
        original['plan_sha256'] = transfer.sha(versions.encoded(original))
        (self.archive / (old + '.zip')).unlink(); (self.archive / (digest + '.zip')).write_bytes(raw)
        manifest['files'].pop(old + '.zip'); manifest['files'][digest + '.zip'] = {'sha256': digest, 'size': len(raw)}
        self.write_manifest(manifest)
        changed = self.archive.parent / original['plan_sha256']; self.archive.rename(changed)
        before = self.bytes(self.store)
        with self.assertRaisesRegex(StorageError, 'identity'): recovery.plan(self.store, changed, self.output)
        self.assertEqual(self.bytes(self.store), before)

    def test_store_and_archive_parent_locks_preserved(self):
        value = self.plan(); before = self.bytes(self.store)
        for folder, name in [(self.store, versions.LOCK), (self.archives, maintenance.ARCHIVE_LOCK)]:
            path = folder / name; path.write_bytes(b'foreign lock owner')
            with self.assertRaisesRegex(StorageError, 'lock exists'): self.apply(value)
            self.assertEqual(path.read_bytes(), b'foreign lock owner'); path.unlink()
        self.assert_preserved(before)

    def test_symlink_archive_store_plan_and_member_refused(self):
        value = self.plan()
        for index, original in enumerate([self.store, self.archive, self.output]):
            link = self.root / ('link%d' % index); link.symlink_to(original, target_is_directory=original.is_dir())
            args = [self.store, self.archive, self.output]; args[index] = link
            with self.assertRaises(StorageError): recovery.apply(*args, value['plan_sha256'], True)
        name = self.original['revisions'][0] + '.zip'; path = self.archive / name
        external = self.root / 'external.zip'; external.write_bytes(path.read_bytes()); path.unlink(); path.symlink_to(external)
        with self.assertRaises(StorageError): self.apply(value)

    def test_every_removal_revalidates_entire_backup_and_protected_bytes(self):
        # Corrupt an already-absent backup between unlinks: the next removal stops.
        value = self.plan(); real_remove = recovery.remove_revision; calls = []
        def alter_backup(path):
            real_remove(path); calls.append(path)
            if len(calls) == 1:
                (self.archive / (value['already_absent'][0] + '.zip')).write_bytes(b'corrupt')
        with mock.patch.object(recovery, 'remove_revision', side_effect=alter_backup):
            with self.assertRaises(StorageError): self.apply(value)
        self.assertEqual(len(calls), 1)
        # Restore test-controlled corruption, then replan and mutate a protected ZIP.
        for name, raw in self.archive_bytes.items(): (self.archive / name).write_bytes(raw)
        fresh_path = self.root / 'fresh.json'; fresh = self.plan(fresh_path); calls.clear()
        def alter_protected(path):
            real_remove(path); calls.append(path)
            if len(calls) == 1: (self.store / (fresh['protected'][0] + '.zip')).write_bytes(b'corrupt')
        with mock.patch.object(recovery, 'remove_revision', side_effect=alter_protected):
            with self.assertRaisesRegex(StorageError, 'protected'): self.apply(fresh, fresh_path)
        self.assertEqual(len(calls), 1)

    def test_malformed_recovery_plan_refused_without_removal(self):
        value = self.plan(); raw = self.output.read_bytes(); before = self.bytes(self.store)
        variants = [b'{"version":1,"version":1}', b'{"version":NaN}', b'[]', b'\xff']
        for changed in [dict(value, version=True), dict(value, extra=1), dict(value, protected=[]),
                        dict(value, remaining=list(reversed(value['remaining']))),
                        dict(value, already_absent=value['remaining']), dict(value, plan_sha256='0' * 64)]:
            variants.append(versions.encoded(changed))
        for changed in variants:
            self.output.write_bytes(changed)
            with self.subTest(raw=changed), self.assertRaises((ValueError, UnicodeError)): self.apply(value)
            self.assertEqual(self.bytes(self.store), before)
        self.output.write_bytes(raw)

    def test_cli_failure_has_no_traceback(self):
        error = self.cli('snapshot_recovery.py', 'apply', '--store', self.store,
                         '--archive', self.archive, '--plan', self.root / 'missing.json',
                         '--expected-plan-sha256', '0' * 64, '--approve', ok=False)
        self.assertNotIn('Traceback', error)


if __name__ == '__main__':
    unittest.main(verbosity=2)
