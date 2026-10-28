"""Frozen independent adversarial CLI checks; no candidate implementation read."""
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile

RUN = Path(__file__).resolve().parents[2]
SCRIPTS = RUN / 'candidate/teach-me/scripts'
FIXTURES = RUN / 'review/fixtures'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class HeldOutCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=str(RUN / 'review'))
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, name, *args, expected=0):
        result = subprocess.run([sys.executable, '-B', str(SCRIPTS / name), *map(str, args)],
                                capture_output=True, text=True, timeout=15)
        if expected == 0:
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        else:
            self.assertNotEqual(result.returncode, 0, result.stderr + result.stdout)
        return result

    def init(self, id='review'):
        self.cli('journey.py', 'init', '--root', self.root, '--id', id,
                 '--topic', 'Algebra', '--goal', 'Explain a changed example')
        return self.root / 'learning' / id

    def pack(self):
        journey = self.init()
        for name in ('knowledge.md', 'practice.md', 'harness-project.md'):
            (journey / name).write_text('Exact companion bytes: ' + name + '\n')
        archive = self.root / 'journey.zip'
        self.cli('transfer.py', 'pack', '--journey', journey, '--output', archive)
        return journey, archive

    def rewritten_archive(self, original, name, transform):
        target = self.root / name
        with zipfile.ZipFile(original) as src, zipfile.ZipFile(target, 'w') as dest:
            entries = [(i, src.read(i)) for i in src.infolist()]
            for info, content in transform(entries):
                dest.writestr(info, content)
        return target

    def test_native_unknown_and_duplicate_version_refused_before_output(self):
        for index, content in enumerate(('{"version":2,"id":"x","messages":[]}',
                                         '{"version":1,"version":2,"id":"x","messages":[]}',
                                         '{"id":"x","messages":[{"role":"user","parts":[]}]}')):
            source = self.root / ('source%d.json' % index)
            source.write_text(content)
            output = self.root / ('output%d.json' % index)
            before = digest(source)
            self.cli('learning_data.py', 'session', '--input', source, '--output', output, expected=1)
            self.assertFalse(output.exists())
            self.assertEqual(digest(source), before)

    def test_explicit_forbidden_source_and_symlink_are_refused(self):
        source = self.root / 'auth.json'
        source.write_text('{"version":1,"id":"auth","messages":[]}')
        self.cli('learning_data.py', 'session', '--input', source,
                 '--output', self.root / 'forbidden.json', expected=1)
        source.rename(self.root / 'session.json')
        link = self.root / 'linked.json'
        link.symlink_to(self.root / 'session.json')
        self.cli('learning_data.py', 'session', '--input', link,
                 '--output', self.root / 'linked-output.json', expected=1)
        self.assertFalse((self.root / 'forbidden.json').exists())
        self.assertFalse((self.root / 'linked-output.json').exists())

    def test_output_existing_symlink_and_source_overwrite_refused(self):
        source = self.root / 'session.json'
        source.write_text('{"version":1,"id":"x","messages":[]}')
        before = digest(source)
        self.cli('learning_data.py', 'session', '--input', source, '--output', source, expected=1)
        protected = self.root / 'protected.txt'
        protected.write_text('original')
        link = self.root / 'output.json'
        link.symlink_to(protected)
        self.cli('learning_data.py', 'session', '--input', source, '--output', link, expected=1)
        self.assertEqual(protected.read_text(), 'original')
        self.assertEqual(digest(source), before)

    def test_transfer_roundtrip_omits_unlisted_file_and_preserves_companions(self):
        journey, archive = self.pack()
        target_root = self.root / 'receiving'
        target_root.mkdir()
        self.cli('transfer.py', 'unpack', '--archive', archive, '--root', target_root, '--id', 'review')
        imported = target_root / 'learning/review'
        for name in ('plan.md', 'progress.json', 'sources.md', 'knowledge.md', 'practice.md', 'harness-project.md'):
            self.assertEqual((journey / name).read_bytes(), (imported / name).read_bytes())
        self.assertFalse((imported / 'pilot.md').exists())
        before = digest(imported / 'progress.json')
        self.cli('transfer.py', 'unpack', '--archive', archive, '--root', target_root, '--id', 'review', expected=1)
        self.assertEqual(digest(imported / 'progress.json'), before)

    def test_transfer_never_includes_unlisted_source_file(self):
        journey = self.init()
        (journey / 'pilot.md').write_text('Unlisted personal record must not enter bundle\n')
        before = digest(journey / 'progress.json')
        archive = self.root / 'with-extra.zip'
        result = subprocess.run([sys.executable, '-B', str(SCRIPTS / 'transfer.py'),
                                 'pack', '--journey', str(journey), '--output', str(archive)],
                                capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            with zipfile.ZipFile(archive) as inp:
                self.assertFalse(any(name.endswith('pilot.md') for name in inp.namelist()))
        else:
            self.assertFalse(archive.exists())
        self.assertEqual(digest(journey / 'progress.json'), before)

    def test_transfer_refuses_tamper_duplicate_traversal_and_symlink_member(self):
        journey, archive = self.pack()
        source_hash = digest(journey / 'progress.json')
        def tamper(entries):
            return [(i, (b'tampered' if i.filename.endswith('progress.json') else b)) for i, b in entries]
        def duplicate(entries):
            return entries + [next((i,b) for i,b in entries if i.filename.endswith('progress.json'))]
        def traverse(entries):
            return entries + [('../escape.txt', b'unsafe')]
        def backslash(entries):
            return entries + [('..\\escape.txt', b'unsafe')]
        def symlink(entries):
            i = zipfile.ZipInfo('knowledge.md')
            i.create_system = 3
            i.external_attr = (stat.S_IFLNK | 0o777) << 16
            return [(a,b) for a,b in entries if not a.filename.endswith('knowledge.md')] + [(i,b'../elsewhere')]
        for index, transform in enumerate((tamper, duplicate, traverse, backslash, symlink)):
            bad = self.rewritten_archive(archive, 'bad%d.zip' % index, transform)
            target_root = self.root / ('receive%d' % index)
            target_root.mkdir()
            self.cli('transfer.py', 'unpack', '--archive', bad, '--root', target_root, '--id', 'review', expected=1)
            self.assertFalse((target_root / 'learning/review').exists())
            self.assertFalse((target_root / 'escape.txt').exists())
        self.assertEqual(digest(journey / 'progress.json'), source_hash)

    def test_transfer_wrong_requested_id_and_unknown_file_refused(self):
        journey, archive = self.pack()
        target_root = self.root / 'receiving'
        target_root.mkdir()
        self.cli('transfer.py', 'unpack', '--archive', archive, '--root', target_root, '--id', 'different', expected=1)
        self.assertFalse((target_root / 'learning/different').exists())
        bad = self.rewritten_archive(archive, 'unknown.zip', lambda entries: entries + [('auth.json', b'not a secret')])
        self.cli('transfer.py', 'unpack', '--archive', bad, '--root', target_root, '--id', 'review', expected=1)
        self.assertFalse((target_root / 'learning/review').exists())

    def test_cooperative_held_lock_refuses_save_without_mutation(self):
        journey = self.init()
        raw = (journey / 'progress.json').read_bytes()
        data = json.loads(raw)
        data['next_action'] = 'A different next task'
        proposed = self.root / 'next.json'
        proposed.write_text(json.dumps(data))
        lock = journey / '.teach-me.lock'
        lock.write_text('{"token":"foreign","pid":-1,"created_at":"old-looking"}')
        lock_bytes = lock.read_bytes()
        self.cli('journey.py', 'save', '--journey', journey, '--input', proposed,
                 '--expected-sha256', hashlib.sha256(raw).hexdigest(), expected=1)
        self.assertEqual((journey / 'progress.json').read_bytes(), raw)
        self.assertEqual(lock.read_bytes(), lock_bytes)

    def test_two_real_save_processes_same_expected_hash_at_most_one_success(self):
        journey = self.init()
        raw = (journey / 'progress.json').read_bytes()
        commands = []
        for index in range(2):
            data = json.loads(raw)
            data['next_action'] = 'Writer %d' % index
            proposed = self.root / ('next%d.json' % index)
            proposed.write_text(json.dumps(data))
            commands.append([sys.executable, '-B', str(SCRIPTS / 'journey.py'), 'save', '--journey', str(journey),
                             '--input', str(proposed), '--expected-sha256', hashlib.sha256(raw).hexdigest()])
        processes = [subprocess.Popen(c, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for c in commands]
        results = []
        for p in processes:
            out, err = p.communicate(timeout=10)
            results.append((p.returncode, out, err))
        self.assertEqual(sum(code == 0 for code, out, err in results), 1, results)
        self.cli('journey.py', 'validate', '--file', journey / 'progress.json')
        self.assertEqual((journey / 'progress.previous.json').read_bytes(), raw)


if __name__ == '__main__':
    unittest.main(verbosity=2)
