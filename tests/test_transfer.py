"""Executed transfer, conflict and write-failure checks; no external services."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import warnings
import zipfile

SKILL = Path(os.environ.get('TEACH_ME_SKILL', Path(__file__).resolve().parents[1] / 'teach-me')).resolve()
SCRIPTS = SKILL / 'scripts'
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import storage
import journey
import transfer


class TransferCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / 'source'
        self.source.mkdir()
        self.target = self.root / 'target'
        self.target.mkdir()
        self.j = self.source / 'learning' / 'algebra'
        self.cli('journey.py', 'init', '--root', self.source, '--id', 'algebra',
                 '--topic', 'Algebra', '--goal', 'Explain a new case')
        self.zip = self.root / 'journey.zip'

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, script, *args, ok=True):
        p = subprocess.run([sys.executable, '-B', str(SCRIPTS / script), *map(str, args)],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0 if ok else 2, p.stderr + p.stdout)
        return json.loads(p.stdout) if ok else p.stderr

    def pack(self, ok=True):
        return self.cli('transfer.py', 'pack', '--journey', self.j, '--output', self.zip, ok=ok)

    def unpack(self, archive=None, root=None, ok=True):
        return self.cli('transfer.py', 'unpack', '--archive', archive or self.zip,
                        '--root', root or self.target, '--id', 'algebra', ok=ok)

    def files(self):
        return {name: (self.j / name).read_bytes() for name in transfer.REQUIRED}

    def archive(self, files=None, manifest=None, entries=None):
        files = self.files() if files is None else files
        manifest = ({'version': 1, 'files': {
            n: {'sha256': hashlib.sha256(b).hexdigest(), 'size': len(b)} for n, b in files.items()}}
                    if manifest is None else manifest)
        payload = list(files.items()) + [('manifest.json', json.dumps(manifest).encode())]
        payload += entries or []
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(self.zip, 'w', compression=zipfile.ZIP_DEFLATED) as z:
                for name, raw in payload:
                    z.writestr(name, raw)

    def test_roundtrip_preserves_optional_bytes_ignores_nonallowlisted(self):
        for name in transfer.OPTIONAL:
            (self.j / name).write_bytes(('Original learner edits: ' + name + '\n').encode())
        (self.j / 'auth.json').write_text('NEVER TRANSFER')
        before = {p.name: p.read_bytes() for p in self.j.iterdir()}
        self.pack()
        with zipfile.ZipFile(self.zip) as z:
            self.assertEqual(set(z.namelist()), transfer.ALLOWED | {'manifest.json'})
        result = self.unpack()
        self.assertFalse(result['automatic_resume'])
        destination = self.target / 'learning/algebra'
        for name in transfer.ALLOWED:
            self.assertEqual((destination / name).read_bytes(), before[name])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.j.iterdir()})

    def test_pack_no_overwrite_or_output_inside_source(self):
        self.zip.write_bytes(b'original')
        self.pack(ok=False)
        self.assertEqual(self.zip.read_bytes(), b'original')
        self.cli('transfer.py', 'pack', '--journey', self.j,
                 '--output', self.j / 'new.zip', ok=False)
        self.assertFalse((self.j / 'new.zip').exists())

    def test_unpack_no_overwrite_and_id_not_migrated(self):
        self.pack()
        self.unpack()
        sentinel = self.target / 'learning/algebra/plan.md'
        sentinel.write_bytes(b'keep learner edit')
        self.unpack(ok=False)
        self.assertEqual(sentinel.read_bytes(), b'keep learner edit')
        self.cli('transfer.py', 'unpack', '--archive', self.zip,
                 '--root', self.target, '--id', 'renamed', ok=False)
        self.assertFalse((self.target / 'learning/renamed').exists())

    def test_symlink_inputs_outputs_ancestors_refused(self):
        link = self.root / 'source-link'
        link.symlink_to(self.source, target_is_directory=True)
        self.cli('transfer.py', 'pack', '--journey', link / 'learning/algebra',
                 '--output', self.zip, ok=False)
        plan = self.j / 'plan.md'
        data = plan.read_bytes()
        plan.unlink()
        plan.symlink_to(self.root / 'absent')
        self.pack(ok=False)
        plan.unlink()
        plan.write_bytes(data)
        self.pack()
        target_link = self.root / 'target-link'
        target_link.symlink_to(self.target, target_is_directory=True)
        self.unpack(root=target_link, ok=False)
        out_link = self.root / 'out-link.zip'
        out_link.symlink_to(self.zip)
        self.cli('transfer.py', 'pack', '--journey', self.j,
                 '--output', out_link, ok=False)

    def test_missing_or_invalid_source_progress_refused(self):
        original = (self.j / 'progress.json').read_bytes()
        (self.j / 'progress.json').write_bytes(b'{broken')
        self.pack(ok=False)
        self.assertFalse(self.zip.exists())
        (self.j / 'progress.json').write_bytes(original)
        (self.j / 'sources.md').unlink()
        self.pack(ok=False)
        self.assertFalse((self.j / '.teach-me.lock').exists())

    def test_archive_tamper_missing_file_and_bad_crc_refused(self):
        files = self.files()
        manifest = {'version': 1, 'files': {
            n: {'sha256': hashlib.sha256(b).hexdigest(), 'size': len(b)} for n, b in files.items()}}
        files['plan.md'] += b'tamper'
        self.archive(files, manifest)
        self.unpack(ok=False)
        files.pop('sources.md')
        self.archive(files)
        self.unpack(ok=False)
        self.archive()
        raw = bytearray(self.zip.read_bytes())
        central = raw.index(b'PK\x01\x02')
        raw[central + 16] ^= 0xff
        self.zip.write_bytes(raw)
        self.unpack(ok=False)
        self.zip.write_bytes(b'not a zip')
        self.unpack(ok=False)
        self.assertFalse((self.target / 'learning/algebra').exists())

    def test_unknown_paths_and_duplicate_members_refused(self):
        for name in ['../outside', '/absolute', 'nested/plan.md', 'x\\plan.md', 'auth.json', 'PLAN.md']:
            with self.subTest(name=name):
                self.archive(entries=[(name, b'bad')])
                self.unpack(ok=False)
        self.archive(entries=[('plan.md', b'duplicate')])
        self.unpack(ok=False)
        self.assertFalse((self.target / 'learning/algebra').exists())

    def test_archive_symlink_oversize_encryption_refused(self):
        info = zipfile.ZipInfo('knowledge.md')
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        self.archive(entries=[(info, b'outside')])
        self.unpack(ok=False)
        self.archive(entries=[('knowledge.md', b'x' * (transfer.FILE_LIMIT + 1))])
        self.unpack(ok=False)
        self.archive()
        raw = bytearray(self.zip.read_bytes())
        start = raw.index(b'PK\x01\x02')
        raw[start + 8] |= 1
        self.zip.write_bytes(raw)
        self.unpack(ok=False)

    def test_manifest_version_types_duplicates_and_progress_validation(self):
        for version in [True, 2, '1']:
            self.archive(manifest={'version': version, 'files': {}})
            self.unpack(ok=False)
        files = self.files()
        state = json.loads(files['progress.json'])
        state['schema_version'] = 2
        files['progress.json'] = json.dumps(state).encode()
        self.archive(files)
        self.unpack(ok=False)
        files = self.files()
        manifest = {'version': 1, 'files': {
            n: {'sha256': hashlib.sha256(b).hexdigest(), 'size': True} for n, b in files.items()}}
        self.archive(files, manifest)
        self.unpack(ok=False)
        self.assertFalse((self.target / 'learning/algebra').exists())

    def test_pack_held_lock_and_fifo_refused(self):
        lock = self.j / '.teach-me.lock'
        lock.write_bytes(b'existing owner')
        self.pack(ok=False)
        self.assertEqual(lock.read_bytes(), b'existing owner')
        lock.unlink()
        if hasattr(os, 'mkfifo'):
            (self.j / 'knowledge.md').unlink(missing_ok=True)
            os.mkfifo(self.j / 'knowledge.md')
            self.pack(ok=False)

    def test_two_unpackers_publish_at_most_once(self):
        self.pack()
        argv = [sys.executable, '-B', str(SCRIPTS / 'transfer.py'), 'unpack',
                '--archive', str(self.zip), '--root', str(self.target), '--id', 'algebra']
        processes = [subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(2)]
        for process in processes:
            process.communicate(timeout=10)
        self.assertEqual(sorted(p.returncode for p in processes), [0, 2])
        self.assertEqual((self.target / 'learning/algebra/progress.json').read_bytes(),
                         (self.j / 'progress.json').read_bytes())

    def test_same_hash_saves_have_one_winner(self):
        original = (self.j / 'progress.json').read_bytes()
        state = json.loads(original)
        state['next_action'] = 'New independent retrieval task'
        proposal = self.root / 'next.json'
        proposal.write_text(json.dumps(state))
        argv = [sys.executable, '-B', str(SCRIPTS / 'journey.py'), 'save',
                '--journey', str(self.j), '--input', str(proposal),
                '--expected-sha256', hashlib.sha256(original).hexdigest()]
        processes = [subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(2)]
        for process in processes:
            process.communicate(timeout=10)
        self.assertEqual(sorted(p.returncode for p in processes), [0, 2])
        self.assertEqual((self.j / 'progress.previous.json').read_bytes(), original)
        self.assertEqual(json.loads((self.j / 'progress.json').read_bytes())['next_action'], state['next_action'])
        self.assertFalse((self.j / '.teach-me.lock').exists())

    def test_failed_progress_replacement_preserves_current_and_backup(self):
        original = (self.j / 'progress.json').read_bytes()
        state = json.loads(original)
        state['next_action'] = 'Changed'
        proposal = self.root / 'next.json'
        proposal.write_text(json.dumps(state))
        real_write = journey.atomic_write
        def injected(path, raw):
            if path.name == 'progress.json':
                raise OSError('injected replacement failure')
            return real_write(path, raw)
        with mock.patch.object(journey, 'atomic_write', side_effect=injected), contextlib.redirect_stderr(io.StringIO()):
            code = journey.main(['save', '--journey', str(self.j), '--input', str(proposal),
                                 '--expected-sha256', hashlib.sha256(original).hexdigest()])
        self.assertEqual(code, 2)
        self.assertEqual((self.j / 'progress.json').read_bytes(), original)
        self.assertEqual((self.j / 'progress.previous.json').read_bytes(), original)
        self.assertFalse((self.j / '.teach-me.lock').exists())

    def test_held_writer_lock_refuses_save_and_foreign_replacement_survives(self):
        original = (self.j / 'progress.json').read_bytes()
        proposal = self.root / 'next.json'
        proposal.write_bytes(original)
        lock = self.j / '.teach-me.lock'
        with storage.journey_lock(self.j):
            self.cli('journey.py', 'save', '--journey', self.j, '--input', proposal,
                     '--expected-sha256', hashlib.sha256(original).hexdigest(), ok=False)
            lock.write_bytes(b'foreign replacement token')
        self.assertEqual(lock.read_bytes(), b'foreign replacement token')
        self.assertEqual((self.j / 'progress.json').read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
