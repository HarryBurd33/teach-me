"""Review history contract cases; TEACH_ME_SKILL can select an installed copy."""
import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SKILL = Path(os.environ.get('TEACH_ME_SKILL',
             str(Path(__file__).resolve().parents[1] / 'candidate' / 'teach-me')))
sys.path.insert(0, str(SKILL / 'scripts'))
import coherence_review as review
import journey
import journey_versions as versions
import review_history as history
from storage import StorageError


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.make_journey('alpha')
        self.store = self.root / 'history'; self.store.mkdir()
        self.receipt = self.root / 'receipt.json'
        self.write_receipt()

    def make_journey(self, ident):
        journey.initial(argparse.Namespace(root=str(self.root), id=ident,
                        topic=['probability'], goal='Use probability in daily decisions'))
        return self.root / 'learning' / ident

    def write_receipt(self, source=None, needs_changes=False, whitespace=False):
        source = source or self.source
        files, state = review.read_content(source)
        packet = review.packet_for(source, files, state)
        value = {'version': 1, 'journey_id': state['journey_id'], 'files': packet['files'],
                 'packet_sha256': packet['packet_sha256'], 'reviewer_role': 'learner',
                 'decisions': [{'check_id': c['check_id'],
                     'result': 'needs_changes' if needs_changes and i == 0 else 'consistent',
                     'rationale': 'Inspected the current source and attempted example.'}
                     for i, c in enumerate(review.CHECKS)],
                 'recorded_at': '2026-10-28T23:00:00+00:00',
                 'resume_ready': not needs_changes, 'semantic_correctness_verified': False}
        raw = (json.dumps(value, indent=4) + '\n \t\n').encode() if whitespace else versions.encoded(value)
        self.receipt.write_bytes(raw)
        return raw

    def append(self, expected='none'):
        return history.append(self.store, self.source, self.receipt, expected)

    def committed(self):
        return {p.name: p.read_bytes() for p in self.store.iterdir() if p.name.endswith('.json')}

    def write_entry(self, value):
        raw = versions.encoded(value); sha = review.digest(raw)
        path = self.store / ('%06d-%s.json' % (value['sequence'], sha))
        path.write_bytes(raw)
        return path, sha

    def replace_entry(self, change):
        path = next(self.store.glob('*.json'))
        value = json.loads(path.read_bytes()); path.unlink(); change(value)
        return self.write_entry(value)

    def assert_denied_unchanged(self, action):
        before = self.committed()
        with self.assertRaises((OSError, ValueError, RuntimeError, TypeError)):
            action()
        self.assertEqual(before, self.committed())

    def test_exact_two_entry_whitespace_extraction_and_cli(self):
        first_raw = self.write_receipt(whitespace=True)
        first = self.append()
        second_raw = self.write_receipt(needs_changes=True, whitespace=True)
        second = self.append(first['entry'])
        status = history.status(self.store)
        self.assertEqual((status['sequence'], status['tip'], status['journey_id']),
                         (2, second['entry'], 'alpha'))
        self.assertFalse(status['receipt_freshness_checked'])
        for n, (result, raw) in enumerate([(first, first_raw), (second, second_raw)]):
            output = self.root / ('extract%d.json' % n)
            history.extract(self.store, result['entry'], output)
            self.assertEqual(output.read_bytes(), raw)
        proc = subprocess.run([sys.executable, str(SKILL / 'scripts/review_history.py'),
                               'status', '--store', str(self.store)], capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)['tip'], second['entry'])

    def test_empty_status(self):
        value = history.status(self.store)
        self.assertEqual((value['tip'], value['sequence'], value['journey_id']), (None, 0, None))

    def test_needs_changes_is_recordable_without_promotion(self):
        self.write_receipt(needs_changes=True)
        result = self.append()
        self.assertFalse(result['resume_ready'])
        self.assertFalse(result['semantic_correctness_verified'])
        self.assertFalse(history.status(self.store)['entries'][0]['resume_ready'])

    def test_stale_tip(self):
        self.append(); self.assert_denied_unchanged(self.append)

    def test_stale_receipt_content(self):
        (self.source / 'plan.md').write_text('Changed plan\n')
        self.assert_denied_unchanged(self.append)

    def test_stale_receipt_packet_digest(self):
        value = json.loads(self.receipt.read_bytes()); value['packet_sha256'] = 'a' * 64
        self.receipt.write_bytes(versions.encoded(value))
        self.assert_denied_unchanged(self.append)

    def test_cross_journey_receipt_and_initialized_history(self):
        first = self.append(); other = self.make_journey('beta')
        self.write_receipt(source=other)
        self.assert_denied_unchanged(lambda: self.append(first['entry']))
        self.assert_denied_unchanged(lambda: history.append(self.store, other, self.receipt, first['entry']))

    def test_store_inside_journey_and_uninitialized_journey(self):
        nested = self.source / 'history'; nested.mkdir()
        with self.assertRaises(StorageError):
            history.append(nested, self.source, self.receipt, 'none')
        empty = self.root / 'empty'; empty.mkdir()
        self.assert_denied_unchanged(lambda: history.append(self.store, empty, self.receipt, 'none'))

    def test_invalid_expected_digest(self):
        for bad in [None, True, 'A' * 64, '0' * 63]:
            self.assert_denied_unchanged(lambda: self.append(bad))

    def test_entry_hash_corruption(self):
        self.append(); path = next(self.store.glob('*.json')); path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaises(StorageError): history.status(self.store)

    def test_strict_entry_keys_versions_and_sequence(self):
        result = self.append(); original = self.committed()
        changes = [lambda v: v.update(extra=1), lambda v: v.update(version=True),
                   lambda v: v.update(sequence=True), lambda v: v.update(sequence=2),
                   lambda v: v.update(previous='a' * 64)]
        for change in changes:
            for p in self.store.glob('*.json'): p.unlink()
            for name, raw in original.items(): (self.store / name).write_bytes(raw)
            if change == changes[2]:
                # A bool cannot be formatted as a separate sequence filename contract.
                value = json.loads(next(iter(original.values()))); change(value)
                raw = versions.encoded(value)
                path = next(self.store.glob('*.json')); path.unlink()
                (self.store / ('000001-' + review.digest(raw) + '.json')).write_bytes(raw)
            else: self.replace_entry(change)
            with self.assertRaises(StorageError): history.status(self.store)

    def test_chain_break_and_duplicate_sequence(self):
        first = self.append(); self.append(first['entry'])
        first_path = sorted(self.store.glob('*.json'))[0]; first_path.unlink()
        with self.assertRaises(StorageError): history.status(self.store)

    def test_receipt_digest_identity_and_strict_schema(self):
        self.append(); original = self.committed()
        for field in ['digest', 'identity', 'extra', 'boolversion', 'utf16']:
            for p in self.store.glob('*.json'): p.unlink()
            for name, raw in original.items(): (self.store / name).write_bytes(raw)
            def change(value):
                if field == 'digest': value['receipt_sha256'] = 'a' * 64; return
                receipt = json.loads(base64.b64decode(value['receipt_base64']))
                if field == 'identity': receipt['journey_id'] = 'beta'
                if field == 'extra': receipt['extra'] = 1
                if field == 'boolversion': receipt['version'] = True
                raw = versions.encoded(receipt)
                if field == 'utf16': raw = json.dumps(receipt).encode('utf-16')
                value['receipt_base64'] = base64.b64encode(raw).decode()
                value['receipt_sha256'] = review.digest(raw)
            self.replace_entry(change)
            with self.assertRaises((ValueError, UnicodeError)): history.status(self.store)

    def test_base64_strict_and_noncanonical_padding_bits(self):
        self.append(); original = self.committed()
        for bad in ['!!!!', 'YWJj\n', 'YR==', 5]:
            for p in self.store.glob('*.json'): p.unlink()
            for name, raw in original.items(): (self.store / name).write_bytes(raw)
            self.replace_entry(lambda v: v.update(receipt_base64=bad))
            with self.assertRaises(StorageError): history.status(self.store)

    def test_duplicate_json_keys_and_noncanonical_entry_bytes(self):
        self.append(); path = next(self.store.glob('*.json'))
        value = json.loads(path.read_bytes()); path.unlink()
        for raw in [json.dumps(value, indent=2).encode(),
                    versions.encoded(value).replace(b'"version":1', b'"version":1,"version":1')]:
            target = self.store / ('000001-' + review.digest(raw) + '.json'); target.write_bytes(raw)
            with self.assertRaises(ValueError): history.status(self.store)
            target.unlink()

    def test_orphan_stage_report_refusal_and_nonregular(self):
        orphan = self.store / (history.STAGE_PREFIX + 'abandoned'); orphan.write_bytes(b'partial')
        self.assertEqual(history.status(self.store)['staging_entries'], [orphan.name])
        self.assert_denied_unchanged(self.append); self.assertEqual(orphan.read_bytes(), b'partial')
        orphan.unlink(); orphan.mkdir()
        with self.assertRaises((OSError, StorageError)): history.status(self.store)

    def test_history_and_journey_locks_preserved(self):
        for parent, name in [(self.store, history.LOCK), (self.source, '.teach-me.lock')]:
            lock = parent / name; lock.write_bytes(b'foreign owner')
            self.assert_denied_unchanged(self.append)
            self.assertEqual(lock.read_bytes(), b'foreign owner'); lock.unlink()

    def test_extract_create_new_output_and_unknown_entry(self):
        result = self.append(); output = self.root / 'existing.json'; output.write_bytes(b'foreign')
        for target in [output, self.store / 'new.json']:
            with self.assertRaises(StorageError): history.extract(self.store, result['entry'], target)
        self.assertEqual(output.read_bytes(), b'foreign')
        with self.assertRaises(StorageError): history.extract(self.store, 'a' * 64, self.root / 'new.json')

    def test_symlink_paths_preserved(self):
        link = self.root / 'linked-store'; link.symlink_to(self.store, target_is_directory=True)
        with self.assertRaises(StorageError): history.status(link)
        result = self.append(); target = self.root / 'foreign'; target.write_bytes(b'keep')
        output = self.root / 'linked-output'; output.symlink_to(target)
        with self.assertRaises(StorageError): history.extract(self.store, result['entry'], output)
        self.assertEqual(target.read_bytes(), b'keep'); self.assertTrue(output.is_symlink())

    def test_receipt_entry_and_directory_actual_size_bounds(self):
        self.receipt.write_bytes(b' ' * (history.RECEIPT_LIMIT + 1))
        self.assert_denied_unchanged(self.append)
        oversized = self.store / (history.STAGE_PREFIX + 'oversized')
        oversized.write_bytes(b'x' * (history.ENTRY_LIMIT + 1))
        with self.assertRaises(StorageError): history.status(self.store)
        oversized.unlink()
        for n in range(history.DIRECTORY_LIMIT):
            (self.store / (history.STAGE_PREFIX + str(n))).touch()
        with self.assertRaises(StorageError): history.status(self.store)

    def test_actual_64_entry_limit(self):
        original = json.loads(self.receipt.read_bytes())
        raw = self.receipt.read_bytes(); previous = None
        for n in range(1, 65):
            value = {'version': 1, 'journey_id': 'alpha', 'sequence': n, 'previous': previous,
                     'receipt_sha256': review.digest(raw), 'receipt_base64': base64.b64encode(raw).decode()}
            _, previous = self.write_entry(value)
        self.assertEqual(history.status(self.store)['sequence'], 64)
        self.assert_denied_unchanged(lambda: self.append(previous))

    def test_total_limit_read_and_append_boundary(self):
        first = self.append(); size = sum(len(v) for v in self.committed().values())
        with mock.patch.object(history, 'TOTAL_LIMIT', size - 1):
            with self.assertRaises(StorageError): history.status(self.store)
        with mock.patch.object(history, 'TOTAL_LIMIT', size):
            self.assert_denied_unchanged(lambda: self.append(first['entry']))
        self.assertEqual((history.TOTAL_LIMIT, history.ENTRY_LIMIT, history.RECEIPT_LIMIT),
                         (67108864, 3145728, 2097152))

    def test_receipt_raw_change_and_content_change_during_staging(self):
        original_stage = history.stage
        for change in ['receipt', 'content']:
            self.write_receipt()
            def stage(parent, raw):
                result = original_stage(parent, raw)
                if change == 'receipt': self.receipt.write_bytes(self.receipt.read_bytes() + b'\n')
                else: (self.source / 'plan.md').write_text('changed during append\n')
                return result
            with mock.patch.object(history, 'stage', side_effect=stage):
                self.assert_denied_unchanged(self.append)
        self.assertEqual(list(self.store.iterdir()), [])

    def test_publication_failure_and_foreign_output_preserved(self):
        with mock.patch.object(history.os, 'link', side_effect=OSError('injected publication failure')):
            self.assert_denied_unchanged(self.append)
        self.assertEqual(list(self.store.iterdir()), [])
        result = self.append(); output = self.root / 'foreign-at-publication.json'
        real_link = os.link
        def foreign_link(source, target):
            Path(target).write_bytes(b'foreign at publication')
            return real_link(source, target)
        with mock.patch.object(history.os, 'link', side_effect=foreign_link):
            with self.assertRaises(FileExistsError): history.extract(self.store, result['entry'], output)
        self.assertEqual(output.read_bytes(), b'foreign at publication')
        self.assertFalse(list(self.root.glob(history.STAGE_PREFIX + '*')))

    def test_history_raw_change_during_extraction(self):
        result = self.append(); original_stage = history.stage
        def stage(parent, raw):
            staged = original_stage(parent, raw)
            path = next(self.store.glob('*.json')); path.write_bytes(path.read_bytes() + b' ')
            return staged
        output = self.root / 'new.json'
        with mock.patch.object(history, 'stage', side_effect=stage):
            with self.assertRaises(StorageError): history.extract(self.store, result['entry'], output)
        self.assertFalse(output.exists())

    def test_cli_requires_expected_tip(self):
        proc = subprocess.run([sys.executable, str(SKILL / 'scripts/review_history.py'), 'append',
                 '--store', str(self.store), '--journey', str(self.source),
                 '--receipt', str(self.receipt)], capture_output=True)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(self.committed(), {})


if __name__ == '__main__': unittest.main()
