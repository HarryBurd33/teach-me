"""Historical import contract; TEACH_ME_SKILL selects a receiving skill copy."""
import argparse
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SKILL = Path(os.environ.get('TEACH_ME_SKILL',
             str(Path(__file__).resolve().parents[1] / 'teach-me')))
sys.path.insert(0, str(SKILL / 'scripts'))
import coherence_review as review
import journey
import journey_versions as versions
import review_history as history
from storage import StorageError


class HistoricalImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        journey.initial(argparse.Namespace(root=str(self.root), id='alpha',
                        topic=['probability'], goal='Use probability in daily decisions'))
        self.source = self.root / 'learning' / 'alpha'
        self.store = self.root / 'history'; self.store.mkdir()
        self.receipt_path = self.root / 'receipt.json'
        self.raw = self.write_receipt()

    def write_receipt(self, needs_changes=False, whitespace=True):
        files, state = review.read_content(self.source)
        packet = review.packet_for(self.source, files, state)
        value = {'version': 1, 'journey_id': 'alpha', 'files': packet['files'],
                 'packet_sha256': packet['packet_sha256'], 'reviewer_role': 'learner',
                 'decisions': [{'check_id': c['check_id'],
                     'result': 'needs_changes' if needs_changes and i == 0 else 'consistent',
                     'rationale': 'Inspected the recorded source and attempted example.'}
                     for i, c in enumerate(review.CHECKS)],
                 'recorded_at': '2020-01-01T00:00:00+00:00',
                 'resume_ready': not needs_changes, 'semantic_correctness_verified': False}
        raw = ((json.dumps(value, indent=4, ensure_ascii=False) + '\n \t\n').encode('utf-8')
               if whitespace else versions.encoded(value))
        self.receipt_path.write_bytes(raw)
        return raw

    def import_receipt(self, **kwargs):
        args = dict(store=self.store, receipt_path=self.receipt_path, journey_id='alpha',
                    expected_tip='none', expected_receipt_sha256=review.digest(self.raw),
                    origin_note='Retain an older review after changing the plan.')
        args.update(kwargs)
        return history.import_receipt(**args)

    def committed(self):
        return {p.name: p.read_bytes() for p in self.store.glob('*.json')}

    def all_bytes(self):
        return {p.name: p.read_bytes() for p in self.store.iterdir() if p.is_file()}

    def deny(self, action):
        before = self.all_bytes()
        with self.assertRaises((OSError, ValueError, RuntimeError, TypeError)):
            action()
        self.assertEqual(self.all_bytes(), before)

    def write_entry(self, value):
        raw = versions.encoded(value)
        sha = review.digest(raw)
        (self.store / ('%06d-%s.json' % (value['sequence'], sha))).write_bytes(raw)
        return sha

    def rewrite_entry(self, change):
        original = self.committed()
        self.assertEqual(len(original), 1)
        name, raw = next(iter(original.items()))
        value = json.loads(raw)
        change(value)
        (self.store / name).unlink()
        return self.write_entry(value)

    def cli(self, arguments):
        return subprocess.run([sys.executable, str(SKILL / 'scripts' / 'review_history.py')]
                              + arguments, capture_output=True)

    def test_old_stale_whitespace_exact_bytes_and_no_current_journey_read(self):
        (self.source / 'plan.md').write_text('Changed since the old receipt\n')
        with self.assertRaises(StorageError):
            history.append(self.store, self.source, self.receipt_path, 'none')
        shutil.rmtree(self.source)
        with mock.patch.object(review, 'read_content', side_effect=AssertionError('journey read')):
            result = self.import_receipt()
        output = self.root / 'extracted.json'
        history.extract(self.store, result['entry'], output)
        self.assertEqual(output.read_bytes(), self.raw)
        self.assertEqual(result['receipt_sha256'], review.digest(self.raw))
        self.assertFalse(result['resume_ready'])
        self.assertTrue(result['receipt_resume_ready'])
        self.assertFalse(result['receipt_freshness_checked'])
        self.assertFalse(result['origin_authenticated'])

    def test_ready_and_needs_changes_are_both_historical_and_not_ready(self):
        previous = 'none'
        for needs_changes in (False, True):
            self.raw = self.write_receipt(needs_changes=needs_changes)
            result = self.import_receipt(expected_tip=previous)
            previous = result['entry']
            self.assertIs(result['resume_ready'], False)
            self.assertIs(result['receipt_resume_ready'], not needs_changes)
        report = history.status(self.store)
        self.assertFalse(report['receipt_freshness_checked'])
        self.assertFalse(report['semantic_correctness_verified'])
        self.assertFalse(report['origin_authenticated'])
        self.assertEqual([r['origin'] for r in report['entries']], ['historical_import'] * 2)
        self.assertEqual([r['resume_ready'] for r in report['entries']], [False, False])
        self.assertEqual([r['receipt_resume_ready'] for r in report['entries']], [True, False])
        self.assertTrue(all(r['origin_note'] for r in report['entries']))

    def test_mixed_chain_retains_bytes_and_current_append_exact_v1(self):
        first = history.append(self.store, self.source, self.receipt_path, 'none')
        old = self.committed()
        second = self.import_receipt(expected_tip=first['entry'])
        middle = self.committed()
        third = history.append(self.store, self.source, self.receipt_path, second['entry'])
        current = self.committed()
        self.assertTrue(all(current[name] == raw for name, raw in middle.items()))
        self.assertTrue(all(middle[name] == raw for name, raw in old.items()))
        values = [json.loads(raw) for _, raw in sorted(current.items())]
        self.assertEqual([v['version'] for v in values], [1, 2, 1])
        self.assertEqual(set(values[0]), history.ENTRY_KEYS)
        self.assertEqual(set(values[2]), history.ENTRY_KEYS)
        self.assertEqual(set(values[1]), history.ENTRY_KEYS | {'origin', 'origin_note'})
        self.assertEqual([v['previous'] for v in values], [None, first['entry'], second['entry']])
        report = history.status(self.store)
        self.assertEqual(report['tip'], third['entry'])
        self.assertEqual([r['origin'] for r in report['entries']],
                         ['current_checked_append', 'historical_import', 'current_checked_append'])
        self.assertEqual([r['resume_ready'] for r in report['entries']], [True, False, True])
        for number, record in enumerate(report['entries']):
            output = self.root / ('exact-%s.json' % number)
            history.extract(self.store, record['sha256'], output)
            self.assertEqual(output.read_bytes(), self.raw)

    def test_wrong_digest_and_invalid_digest(self):
        for bad in ('f' * 64, None, True, 'A' * 64, '0' * 63):
            with self.subTest(bad=bad):
                self.deny(lambda: self.import_receipt(expected_receipt_sha256=bad))

    def test_wrong_tip_and_invalid_tip(self):
        first = self.import_receipt()
        for bad in ('none', 'f' * 64, None, True, 'A' * 64):
            with self.subTest(bad=bad):
                self.deny(lambda: self.import_receipt(expected_tip=bad))
        self.assertEqual(history.status(self.store)['tip'], first['entry'])

    def test_wrong_or_invalid_explicit_id(self):
        for bad in ('beta', '', '../alpha', True, None, 'ALPHA'):
            with self.subTest(bad=bad):
                self.deny(lambda: self.import_receipt(journey_id=bad))

    def test_foreign_store_identity(self):
        self.import_receipt()
        value = json.loads(self.raw); value['journey_id'] = 'beta'
        raw = versions.encoded(value); self.receipt_path.write_bytes(raw)
        self.deny(lambda: self.import_receipt(journey_id='beta',
                                             expected_receipt_sha256=review.digest(raw),
                                             expected_tip=history.status(self.store)['tip']))

    def test_blank_type_and_overlong_reason_refused(self):
        for bad in ('', ' \n\t', None, True, 'a' * 4097):
            with self.subTest(bad=repr(bad)[:30]):
                self.deny(lambda: self.import_receipt(origin_note=bad))

    def test_unicode_reason_4096_characters_preserved(self):
        note = ' Retain 🦉\n' + 'é' * (4096 - len(' Retain 🦉\n'))
        result = self.import_receipt(origin_note=note)
        self.assertEqual(result['origin_note'], note)
        self.assertEqual(history.status(self.store)['entries'][0]['origin_note'], note)

    def test_v2_rejects_forged_origin_versions_and_unknown_keys(self):
        self.import_receipt()
        original = self.committed()
        changes = [lambda v: v.update(origin='current_checked_append'),
                   lambda v: v.update(origin=True), lambda v: v.update(version=True),
                   lambda v: v.update(version=3), lambda v: v.update(extra='foreign'),
                   lambda v: v.pop('origin'), lambda v: v.pop('origin_note'),
                   lambda v: v.update(origin_note=' \n'),
                   lambda v: v.update(origin_note='a' * 4097),
                   lambda v: v.update(origin_note=False), lambda v: v.update(version=1)]
        for number, change in enumerate(changes):
            with self.subTest(case=number):
                for path in self.store.glob('*.json'): path.unlink()
                for name, raw in original.items(): (self.store / name).write_bytes(raw)
                self.rewrite_entry(change)
                with self.assertRaises(StorageError): history.status(self.store)

    def test_v2_bad_base64_receipt_digest_and_identity(self):
        self.import_receipt()
        original = self.committed()
        changes = [lambda v: v.update(receipt_base64='!!!!'),
                   lambda v: v.update(receipt_base64='YR=='),
                   lambda v: v.update(receipt_base64=True),
                   lambda v: v.update(receipt_sha256='f' * 64),
                   lambda v: v.update(journey_id='beta'),
                   lambda v: v.update(sequence=True),
                   lambda v: v.update(previous='f' * 64)]
        for number, change in enumerate(changes):
            with self.subTest(case=number):
                for path in self.store.glob('*.json'): path.unlink()
                for name, raw in original.items(): (self.store / name).write_bytes(raw)
                self.rewrite_entry(change)
                with self.assertRaises(StorageError): history.status(self.store)

    def test_embedded_receipt_closed_schema_bool_version_and_ready_consistency(self):
        original = json.loads(self.raw)
        for change in (lambda v: v.update(version=True), lambda v: v.update(extra=1),
                       lambda v: v.update(resume_ready=False),
                       lambda v: v.update(semantic_correctness_verified=True)):
            value = json.loads(json.dumps(original)); change(value)
            self.receipt_path.write_bytes(versions.encoded(value))
            self.deny(lambda: self.import_receipt(
                expected_receipt_sha256=review.digest(self.receipt_path.read_bytes())))

    def test_utf16_duplicate_receipt_keys_and_nonfinite_refused(self):
        value = json.loads(self.raw)
        variants = [json.dumps(value).encode('utf-16'),
                    versions.encoded(value).replace(b'"version":1', b'"version":1,"version":1'),
                    versions.encoded(value).replace(b'"version":1', b'"version":NaN')]
        for raw in variants:
            self.receipt_path.write_bytes(raw)
            self.deny(lambda: self.import_receipt(expected_receipt_sha256=review.digest(raw)))

    def test_cli_import_and_extract_exact_receipt_bytes(self):
        args = ['import', '--store', str(self.store), '--receipt', str(self.receipt_path),
                '--id', 'alpha', '--expected-tip', 'none', '--expected-receipt-sha256',
                review.digest(self.raw), '--reason', 'Preserve original bytes']
        proc = self.cli(args)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        value = json.loads(proc.stdout)
        self.assertTrue(value['imported']); self.assertFalse(value['resume_ready'])
        output = self.root / 'cli.json'
        proc = self.cli(['extract', '--store', str(self.store), '--entry', value['entry'],
                         '--output', str(output)])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(output.read_bytes(), self.raw)

    def test_cli_all_six_arguments_required(self):
        parts = [('--store', str(self.store)), ('--receipt', str(self.receipt_path)),
                 ('--id', 'alpha'), ('--expected-tip', 'none'),
                 ('--expected-receipt-sha256', review.digest(self.raw)), ('--reason', 'Old review')]
        for omitted in range(len(parts)):
            args = ['import'] + [part for i, pair in enumerate(parts) if i != omitted for part in pair]
            self.assertEqual(self.cli(args).returncode, 2)
            self.assertEqual(self.all_bytes(), {})

    def test_lock_and_stage_preserved(self):
        lock = self.store / history.LOCK; lock.write_bytes(b'foreign owner')
        self.deny(self.import_receipt); lock.unlink()
        orphan = self.store / (history.STAGE_PREFIX + 'orphan'); orphan.write_bytes(b'partial')
        self.deny(self.import_receipt)
        self.assertEqual(history.status(self.store)['staging_entries'], [orphan.name])

    def test_symlink_store_receipt_and_unknown_store_file_refused(self):
        linked_store = self.root / 'linked-store'; linked_store.symlink_to(self.store)
        self.deny(lambda: self.import_receipt(store=linked_store))
        linked_receipt = self.root / 'linked-receipt'; linked_receipt.symlink_to(self.receipt_path)
        self.deny(lambda: self.import_receipt(receipt_path=linked_receipt))
        foreign = self.store / 'foreign'; foreign.write_bytes(b'keep')
        self.deny(self.import_receipt)

    def test_receipt_change_during_stage_prevents_publication(self):
        original = history.stage
        def stage(parent, raw):
            result = original(parent, raw)
            self.receipt_path.write_bytes(self.raw + b'\n')
            return result
        with mock.patch.object(history, 'stage', side_effect=stage):
            self.deny(self.import_receipt)
        self.assertEqual(self.all_bytes(), {})

    def test_stage_change_during_import_prevents_publication(self):
        original = history.stage
        def stage(parent, raw):
            result = original(parent, raw)
            result[0].write_bytes(raw + b' ')
            return result
        with mock.patch.object(history, 'stage', side_effect=stage):
            self.deny(self.import_receipt)
        self.assertEqual(self.all_bytes(), {})

    def test_store_change_during_import_prevents_new_entry_preserves_foreign(self):
        original = history.stage
        foreign = self.store / (history.STAGE_PREFIX + 'foreign')
        def stage(parent, raw):
            result = original(parent, raw); foreign.write_bytes(b'foreign stage'); return result
        with mock.patch.object(history, 'stage', side_effect=stage):
            with self.assertRaises(StorageError): self.import_receipt()
        self.assertEqual(self.committed(), {})
        self.assertEqual(self.all_bytes(), {foreign.name: b'foreign stage'})

    def test_link_failure_no_publication(self):
        with mock.patch.object(history.os, 'link', side_effect=OSError('injected link failure')):
            self.deny(self.import_receipt)
        self.assertEqual(self.all_bytes(), {})

    def test_foreign_output_at_import_publication_preserved(self):
        real_link = os.link
        def link(source, target):
            Path(target).write_bytes(b'foreign at publication')
            return real_link(source, target)
        with mock.patch.object(history.os, 'link', side_effect=link):
            with self.assertRaises(FileExistsError): self.import_receipt()
        self.assertEqual(list(self.committed().values()), [b'foreign at publication'])
        self.assertFalse(list(self.store.glob(history.STAGE_PREFIX + '*')))

    def test_extract_existing_file_and_symlink_preserved(self):
        result = self.import_receipt()
        output = self.root / 'existing'; output.write_bytes(b'foreign')
        linked = self.root / 'linked'; linked.symlink_to(output)
        for target in (output, linked, self.store / 'output.json'):
            self.deny(lambda: history.extract(self.store, result['entry'], target))
        self.assertEqual(output.read_bytes(), b'foreign'); self.assertTrue(linked.is_symlink())

    def test_actual_receipt_limit_and_nonregular_source(self):
        self.receipt_path.write_bytes(b' ' * (history.RECEIPT_LIMIT + 1))
        self.deny(self.import_receipt)
        self.receipt_path.unlink(); self.receipt_path.mkdir()
        self.deny(self.import_receipt)

    def test_actual_stage_and_directory_limits_preserve_files(self):
        stage = self.store / (history.STAGE_PREFIX + 'large')
        stage.write_bytes(b'x' * (history.ENTRY_LIMIT + 1))
        self.deny(self.import_receipt); stage.unlink()
        for number in range(history.DIRECTORY_LIMIT):
            (self.store / (history.STAGE_PREFIX + str(number))).touch()
        self.deny(self.import_receipt)

    def test_actual_64_entry_mixed_chain_limit(self):
        previous = None
        for sequence in range(1, 65):
            value = {'version': 1, 'journey_id': 'alpha', 'sequence': sequence,
                     'previous': previous, 'receipt_sha256': review.digest(self.raw),
                     'receipt_base64': base64.b64encode(self.raw).decode('ascii')}
            if sequence % 2:
                value.update(version=2, origin='historical_import', origin_note='Retain old review')
            previous = self.write_entry(value)
        self.assertEqual(history.status(self.store)['sequence'], 64)
        self.deny(lambda: self.import_receipt(expected_tip=previous))

    def test_entry_total_and_directory_reservation_limits(self):
        with mock.patch.object(history, 'ENTRY_LIMIT', 10):
            self.deny(self.import_receipt)
        with mock.patch.object(history, 'TOTAL_LIMIT', 10):
            self.deny(self.import_receipt)
        with mock.patch.object(history, 'DIRECTORY_LIMIT', 2):
            self.deny(self.import_receipt)
        self.assertEqual((history.MAX_ENTRIES, history.ENTRY_LIMIT, history.RECEIPT_LIMIT,
                          history.TOTAL_LIMIT, history.DIRECTORY_LIMIT),
                         (64, 3145728, 2097152, 67108864, 192))


if __name__ == '__main__':
    unittest.main()
