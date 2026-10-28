"""Synthetic CLI contracts for explicit cross-file review; no learner data."""
import copy
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

SKILL = Path(os.environ.get('TEACH_ME_SKILL', str(Path(__file__).resolve().parents[1] / 'candidate/teach-me')))
SCRIPT = SKILL / 'scripts/coherence_review.py'
IDS = ['goal-stage-next-action', 'evidence-scope', 'sources-and-claims', 'merge-consistency']


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class CoherenceReviewCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.journey = self.root / 'learning/logic'
        self.journey.mkdir(parents=True)
        state = {'schema_version': 1, 'journey_id': 'logic', 'topics': ['Logic'],
                 'goal': 'Explain joint premises', 'current_stage': 'Practice',
                 'availability': {'minutes_per_day': None, 'session_minutes': 0},
                 'assessments': [], 'evidence': [], 'difficulties': [], 'decisions': [],
                 'next_action': 'Try a joint-premise example', 'updated_at': '2026-10-28T00:00:00Z'}
        self.write(self.journey / 'progress.json', state)
        (self.journey / 'plan.md').write_text('Practice joint premises.\n')
        (self.journey / 'sources.md').write_text('Synthetic source notes.\n')
        self.packet = self.root / 'packet.json'
        self.decisions = self.root / 'decisions.json'
        self.receipt = self.journey / 'journey-review.json'

    def tearDown(self):
        self.temp.cleanup()

    def write(self, path, value):
        path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
        return path

    def cli(self, *args, expected=0):
        result = subprocess.run([sys.executable, '-B', str(SCRIPT), *map(str, args)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, expected, result.stderr + result.stdout)
        return json.loads(result.stdout) if result.stdout else result.stderr

    def prepare(self, output=None):
        return self.cli('prepare', '--journey', self.journey, '--output', output or self.packet)

    def choice(self, packet=None, result='consistent'):
        packet = packet or json.loads(self.packet.read_text())
        value = {'version': 1, 'packet_sha256': packet['packet_sha256'], 'reviewer_role': 'tutor',
                 'decisions': [{'check_id': key, 'result': result,
                                'rationale': 'Inspected synthetic ' + key + ' content.'} for key in IDS]}
        self.write(self.decisions, value)
        return value

    def record(self, expected=0, extra=(), output=None):
        return self.cli('record', '--journey', self.journey, '--packet', self.packet,
                        '--decisions', self.decisions, '--output', output or self.receipt,
                        *extra, expected=expected)

    def verify(self, expected=0):
        return self.cli('verify', '--journey', self.journey, '--receipt', self.receipt, expected=expected)

    def reviewed(self, result='consistent'):
        packet = self.prepare()
        self.choice(packet, result)
        return self.record()

    def test_current_review_and_literal_summary(self):
        packet = self.prepare()
        self.assertEqual(set(packet['files']), {'plan.md', 'progress.json', 'sources.md'})
        self.assertEqual(packet['summary']['next_action'], 'Try a joint-premise example')
        self.assertEqual(packet['summary']['evidence_count'], 0)
        self.assertIs(packet['summary']['semantic_correctness_verified'], False)
        self.choice(packet)
        receipt = self.record()
        self.assertTrue(receipt['resume_ready'])
        self.assertNotIn('journey-review.json', receipt['files'])
        result = self.verify()
        self.assertTrue(result['current'])
        self.assertIs(result['semantic_correctness_verified'], False)

    def test_needs_changes_is_recorded_but_verify_exit_one(self):
        receipt = self.reviewed('needs_changes')
        self.assertFalse(receipt['resume_ready'])
        self.assertFalse(self.verify(expected=1)['resume_ready'])

    def test_mixed_judgments_not_ready(self):
        self.prepare()
        value = self.choice()
        value['decisions'][2]['result'] = 'needs_changes'
        value['decisions'][2]['rationale'] = 'Graph claim differs from the quoted source.'
        self.write(self.decisions, value)
        self.assertFalse(self.record()['resume_ready'])
        self.verify(expected=1)

    def test_changed_plan_stales_packet_before_record(self):
        self.prepare(); self.choice()
        (self.journey / 'plan.md').write_text('Now study a different task.\n')
        self.record(expected=2)
        self.assertFalse(self.receipt.exists())

    def test_changed_plan_stales_receipt(self):
        self.reviewed()
        (self.journey / 'plan.md').write_text('Different plan\n')
        self.verify(expected=2)

    def test_new_optional_file_stales_receipt(self):
        self.reviewed()
        (self.journey / 'knowledge.md').write_text('A new assertion\n')
        self.verify(expected=2)

    def test_deleted_optional_file_stales_receipt(self):
        optional = self.journey / 'practice.md'
        optional.write_text('A practice attempt\n')
        self.reviewed(); optional.unlink()
        self.verify(expected=2)

    def test_all_exact_decisions_and_rationales_required(self):
        self.prepare(); good = self.choice()
        cases = [good['decisions'][:-1], good['decisions'] + [good['decisions'][0]],
                 [good['decisions'][0]] * 4]
        for decisions in cases:
            value = copy.deepcopy(good); value['decisions'] = decisions
            self.write(self.decisions, value); self.record(expected=2)
        for field, bad in [('check_id', 'unknown'), ('result', 'approved'), ('rationale', '  ')]:
            value = copy.deepcopy(good); value['decisions'][0][field] = bad
            self.write(self.decisions, value); self.record(expected=2)
        self.assertFalse(self.receipt.exists())

    def test_decision_digest_and_closed_shape(self):
        self.prepare(); value = self.choice()
        value['packet_sha256'] = '0' * 64
        self.write(self.decisions, value); self.record(expected=2)
        value = self.choice(); value['extra'] = True
        self.write(self.decisions, value); self.record(expected=2)

    def test_duplicate_json_and_nonfinite_input_rejected(self):
        self.prepare(); self.choice()
        self.decisions.write_text('{"version":1,"version":1}')
        self.record(expected=2)
        self.decisions.write_text('{"version":NaN}')
        self.record(expected=2)

    def test_altered_packet_summary_is_rejected(self):
        packet = self.prepare(); self.choice(packet)
        packet['summary']['goal'] = 'A substituted goal'
        self.write(self.packet, packet)
        self.record(expected=2)

    def test_rehashed_substituted_packet_still_rejected(self):
        packet = self.prepare()
        packet['summary']['goal'] = 'A substituted goal'
        body = {k: v for k, v in packet.items() if k != 'packet_sha256'}
        packet['packet_sha256'] = sha(json.dumps(body, sort_keys=True, ensure_ascii=False,
                                                separators=(',', ':'), allow_nan=False).encode())
        self.write(self.packet, packet); self.choice(packet)
        self.record(expected=2)

    def test_existing_outputs_preserve_exact_bytes(self):
        self.packet.write_bytes(b'foreign packet')
        self.prepare_reject_existing()
        self.assertEqual(self.packet.read_bytes(), b'foreign packet')
        self.packet.unlink(); self.prepare(); self.choice()
        self.receipt.write_bytes(b'foreign receipt')
        self.record(expected=2)
        self.assertEqual(self.receipt.read_bytes(), b'foreign receipt')

    def prepare_reject_existing(self):
        self.cli('prepare', '--journey', self.journey, '--output', self.packet, expected=2)

    def test_protected_missing_content_output_is_refused(self):
        self.cli('prepare', '--journey', self.journey,
                 '--output', self.journey / 'knowledge-graph.json', expected=2)
        self.assertFalse((self.journey / 'knowledge-graph.json').exists())

    def test_replacement_expected_digest_backup_and_refusal(self):
        self.reviewed(); old = self.receipt.read_bytes()
        self.record(expected=2, extra=('--expected-output-sha256', '0' * 64))
        self.assertEqual(self.receipt.read_bytes(), old)
        self.record(extra=('--expected-output-sha256', sha(old)))
        self.assertEqual((self.journey / 'journey-review.previous.json').read_bytes(), old)
        self.verify()
        other = self.root / 'other.json'
        other.write_bytes(self.receipt.read_bytes())
        before = other.read_bytes()
        self.record(expected=2, extra=('--expected-output-sha256', sha(before)), output=other)
        self.assertEqual(other.read_bytes(), before)

    def test_foreign_previous_receipt_preserved(self):
        self.reviewed(); old = self.receipt.read_bytes()
        previous = self.journey / 'journey-review.previous.json'
        previous.write_bytes(b'foreign previous')
        self.record(expected=2, extra=('--expected-output-sha256', sha(old)))
        self.assertEqual(previous.read_bytes(), b'foreign previous')
        self.assertEqual(self.receipt.read_bytes(), old)

    def test_forged_ready_truth_bool_and_timestamp_receipts_rejected(self):
        good = self.reviewed('needs_changes')
        for key, invalid in [('resume_ready', True), ('resume_ready', 0),
                             ('semantic_correctness_verified', True), ('semantic_correctness_verified', 0),
                             ('recorded_at', '2026-10-28T00:00:00')]:
            bad = copy.deepcopy(good); bad[key] = invalid
            self.write(self.receipt, bad); self.verify(expected=2)

    def test_receipt_manifest_and_journey_identity_rejected(self):
        good = self.reviewed()
        bad = copy.deepcopy(good); bad['files']['plan.md']['size'] = True
        self.write(self.receipt, bad); self.verify(expected=2)
        bad = copy.deepcopy(good); bad['journey_id'] = 'another'
        self.write(self.receipt, bad); self.verify(expected=2)

    def test_symlink_and_writer_lock_refused(self):
        target = self.root / 'secret.txt'; target.write_text('Not followed')
        linked = self.journey / 'knowledge.md'; linked.symlink_to(target)
        self.cli('prepare', '--journey', self.journey, '--output', self.packet, expected=2)
        linked.unlink()
        lock = self.journey / '.teach-me.lock'; lock.write_bytes(b'foreign owner')
        self.cli('prepare', '--journey', self.journey, '--output', self.packet, expected=2)
        self.assertEqual(lock.read_bytes(), b'foreign owner')

    def test_source_proposal_binding_and_draft_warning(self):
        source = b'All three premises are required.'
        (self.journey / 'knowledge-source.txt').write_bytes(source)
        proposal = {'version': 1, 'source_sha256': sha(source), 'nodes': [],
                    'chains': [{'id': 'draft', 'premises': ['missing'], 'conclusion': 'unknown',
                                'evidence': {'start': 0, 'end': len(source), 'quote': source.decode()}}]}
        self.write(self.journey / 'knowledge-proposal.json', proposal)
        packet = self.prepare()
        self.assertTrue(any('Unresolved draft' in item for item in packet['summary']['warnings']))
        self.assertIn('knowledge-source.txt', packet['files'])
        self.packet.unlink(); (self.journey / 'knowledge-source.txt').write_bytes(b'Changed source')
        self.cli('prepare', '--journey', self.journey, '--output', self.packet, expected=2)
        self.assertFalse(self.packet.exists())

    def test_oversized_or_nonregular_source_refused(self):
        path = self.journey / 'knowledge-source.txt'
        path.write_bytes(b'x' * (2 * 1024 * 1024 + 1))
        self.cli('prepare', '--journey', self.journey, '--output', self.packet, expected=2)
        path.unlink(); path.mkdir()
        self.cli('prepare', '--journey', self.journey, '--output', self.packet, expected=2)

    def test_bounded_decisions_cannot_publish_oversized_receipt(self):
        self.prepare(); value = self.choice()
        current_size = len(json.dumps(value, ensure_ascii=False).encode('utf-8'))
        value['decisions'][0]['rationale'] += 'x' * (2 * 1024 * 1024 - current_size - 1)
        self.write(self.decisions, value)
        self.assertLess(len(self.decisions.read_bytes()), 2 * 1024 * 1024)
        self.record(expected=2)
        self.assertFalse(self.receipt.exists())
        self.assertEqual(list(self.journey.glob('.teach-me-review-*')), [])

    def test_bounded_progress_cannot_publish_oversized_packet(self):
        progress = self.journey / 'progress.json'
        value = json.loads(progress.read_text())
        current_size = len(json.dumps(value, ensure_ascii=False).encode('utf-8'))
        value['goal'] += 'x' * (2 * 1024 * 1024 - current_size - 1)
        self.write(progress, value)
        self.assertLess(len(progress.read_bytes()), 2 * 1024 * 1024)
        self.cli('prepare', '--journey', self.journey, '--output', self.packet, expected=2)
        self.assertFalse(self.packet.exists())

    def module(self):
        scripts = str(SKILL / 'scripts')
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        spec = importlib.util.spec_from_file_location('review_component_under_test', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_change_after_staging_prevents_publication(self):
        module = self.module(); original = module.stage
        def changed(path, raw):
            temporary = original(path, raw)
            (self.journey / 'plan.md').write_text('An uncoordinated edit after staging')
            return temporary
        with mock.patch.object(module, 'stage', side_effect=changed):
            with self.assertRaises(ValueError):
                module.prepare(self.journey, self.packet)
        self.assertFalse(self.packet.exists())
        self.assertEqual(list(self.root.glob('.teach-me-review-*')), [])

    def test_foreign_publication_race_preserves_exact_foreign_bytes(self):
        module = self.module(); original = module.stage
        def competitor(path, raw):
            temporary = original(path, raw)
            path.write_bytes(b'foreign output racing before final link')
            return temporary
        with mock.patch.object(module, 'stage', side_effect=competitor):
            with self.assertRaises(FileExistsError):
                module.prepare(self.journey, self.packet)
        self.assertEqual(self.packet.read_bytes(), b'foreign output racing before final link')
        self.assertEqual(list(self.root.glob('.teach-me-review-*')), [])


if __name__ == '__main__':
    unittest.main()
