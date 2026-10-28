"""Executed CLI checks for persistence and evidence invariants."""
import copy
import os
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(os.environ.get('TEACH_ME_SKILL', str(Path(__file__).resolve().parents[1] / 'teach-me'))) / 'scripts' / 'journey.py'


class JourneyCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.journey = self.root / 'learning' / 'algebra'

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, *args, ok=True):
        proc = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                              text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0 if ok else 2, proc.stderr + proc.stdout)
        return json.loads(proc.stdout) if ok else proc.stderr

    def init(self):
        return self.cli('init', '--root', self.root, '--id', 'algebra',
                        '--topic', 'Linear systems', '--goal', 'Solve and explain systems')

    def read(self):
        return self.cli('show', '--journey', self.journey)

    def input_file(self, state):
        path = self.root / 'proposed.json'
        path.write_text(json.dumps(state))
        return path

    def save(self, state, sha, ok=True):
        return self.cli('save', '--journey', self.journey, '--input',
                        self.input_file(state), '--expected-sha256', sha, ok=ok)

    def test_create_save_resume_and_backup(self):
        self.init()
        self.assertTrue((self.journey / 'plan.md').is_file())
        self.assertTrue((self.journey / 'sources.md').is_file())
        before = self.read()
        raw = (self.journey / 'progress.json').read_bytes()
        state = before['progress']
        state['next_action'] = 'Try an independent transfer problem'
        state['evidence'] = [{'id': 'e1', 'kind': 'observed', 'summary': 'Written solution inspected',
                              'recorded_at': '2026-10-26T22:00:00-06:00'}]
        state['assessments'] = [{'id': 'a1', 'task': 'Solve a 2x2 system', 'result': 'demonstrated',
                                 'evidence_ids': ['e1'], 'feedback': 'Both equations verified'}]
        saved = self.save(state, before['sha256'])
        resumed = self.read()
        self.assertEqual(saved['sha256'], resumed['sha256'])
        self.assertEqual(resumed['progress'], state)
        self.assertEqual((self.journey / 'progress.previous.json').read_bytes(), raw)

    def test_zero_null_and_empty_arrays_preserved(self):
        self.init()
        before = self.read()
        state = before['progress']
        state['availability'] = {'minutes_per_day': 0, 'session_minutes': None}
        self.save(state, before['sha256'])
        self.assertEqual(self.read()['progress']['availability'], state['availability'])
        self.assertEqual(self.read()['progress']['assessments'], [])

    def test_missing_field_not_treated_as_zero(self):
        self.init()
        before = self.read()
        del before['progress']['availability']['minutes_per_day']
        self.save(before['progress'], before['sha256'], ok=False)
        self.assertIsNone(self.read()['progress']['availability']['minutes_per_day'])

    def test_refuses_existing_journey(self):
        self.init()
        raw = (self.journey / 'progress.json').read_bytes()
        self.cli('init', '--root', self.root, '--id', 'algebra', '--topic', 'Other', '--goal', 'Other', ok=False)
        self.assertEqual((self.journey / 'progress.json').read_bytes(), raw)

    def test_stale_save_preserves_both_files(self):
        self.init()
        before = self.read()
        changed = copy.deepcopy(before['progress'])
        changed['next_action'] = 'New action'
        self.save(changed, before['sha256'])
        current = (self.journey / 'progress.json').read_bytes()
        backup = (self.journey / 'progress.previous.json').read_bytes()
        self.save(before['progress'], before['sha256'], ok=False)
        self.assertEqual((self.journey / 'progress.json').read_bytes(), current)
        self.assertEqual((self.journey / 'progress.previous.json').read_bytes(), backup)

    def test_corrupt_state_cannot_be_silently_reset(self):
        self.init()
        before = self.read()
        path = self.journey / 'progress.json'
        path.write_bytes(b'{broken')
        self.cli('show', '--journey', self.journey, ok=False)
        self.save(before['progress'], before['sha256'], ok=False)
        self.assertEqual(path.read_bytes(), b'{broken')
        self.assertFalse((self.journey / 'progress.previous.json').exists())

    def test_unknown_version_and_unknown_keys_fail(self):
        self.init()
        before = self.read()
        for mutation in ({'schema_version': 2}, {'unexpected': 'value'}, {'schema_version': True}):
            state = {**before['progress'], **mutation}
            self.save(state, before['sha256'], ok=False)

    def test_boolean_or_negative_minutes_fail(self):
        self.init()
        before = self.read()
        for value in (True, -1, 1.5, '15'):
            state = copy.deepcopy(before['progress'])
            state['availability']['minutes_per_day'] = value
            self.save(state, before['sha256'], ok=False)

    def test_self_report_cannot_certify_and_ids_must_resolve(self):
        self.init()
        before = self.read()
        state = before['progress']
        state['evidence'] = [{'id': 'e1', 'kind': 'self_reported', 'summary': 'Says practised',
                              'recorded_at': '2026-10-26T22:00:00Z'}]
        state['assessments'] = [{'id': 'a1', 'task': 'Play a scale', 'result': 'demonstrated',
                                 'evidence_ids': ['e1'], 'feedback': ''}]
        self.save(state, before['sha256'], ok=False)
        state['assessments'][0]['result'] = 'pending'
        state['assessments'][0]['evidence_ids'] = ['absent']
        self.save(state, before['sha256'], ok=False)
        state['assessments'][0]['evidence_ids'] = ['e1']
        self.save(state, before['sha256'])

    def test_duplicate_ids_and_naive_timestamp_fail(self):
        self.init()
        before = self.read()
        state = before['progress']
        evidence = {'id': 'e1', 'kind': 'observed', 'summary': 'Written work',
                    'recorded_at': '2026-10-26T22:00:00Z'}
        state['evidence'] = [evidence, evidence]
        self.save(state, before['sha256'], ok=False)
        state['evidence'] = [evidence]
        state['updated_at'] = '2026-10-26T22:00:00'
        self.save(state, before['sha256'], ok=False)

    def test_id_immutable_and_traversal_refused(self):
        self.init()
        before = self.read()
        before['progress']['journey_id'] = 'piano'
        self.save(before['progress'], before['sha256'], ok=False)
        self.cli('init', '--root', self.root, '--id', '../escape', '--topic', 'X', '--goal', 'Y', ok=False)
        self.assertFalse((self.root / 'escape').exists())

    def test_symlinked_learning_directory_refused(self):
        external = self.root / 'external'
        external.mkdir()
        (self.root / 'learning').symlink_to(external, target_is_directory=True)
        self.cli('init', '--root', self.root, '--id', 'algebra', '--topic', 'X', '--goal', 'Y', ok=False)
        self.assertEqual(list(external.iterdir()), [])

    def test_symlink_state_backup_or_lock_refused(self):
        self.init()
        before = self.read()
        external = self.root / 'external.json'
        external.write_text('untouched')
        for name in ('progress.previous.json', 'progress.lock'):
            path = self.journey / name
            path.symlink_to(external)
            self.save(before['progress'], before['sha256'], ok=False)
            path.unlink()
        progress = self.journey / 'progress.json'
        progress.unlink()
        progress.symlink_to(external)
        self.cli('show', '--journey', self.journey, ok=False)
        self.assertEqual(external.read_text(), 'untouched')

    def test_renamed_folder_cannot_resume_as_another_journey(self):
        self.init()
        moved = self.journey.with_name('piano')
        self.journey.rename(moved)
        self.cli('show', '--journey', moved, ok=False)

    def test_validate_is_read_only_and_missing_progress_fails(self):
        self.init()
        progress = self.journey / 'progress.json'
        raw = progress.read_bytes()
        self.cli('validate', '--file', progress)
        self.assertEqual(progress.read_bytes(), raw)
        progress.unlink()
        self.cli('show', '--journey', self.journey, ok=False)
        self.assertFalse(progress.exists())

    def test_duplicate_json_members_are_rejected_without_writes(self):
        self.init()
        before = self.read()
        path = self.journey / 'progress.json'
        ambiguous = path.read_text().replace('"goal":', '"goal": "Unconfirmed duplicate", "goal":', 1)
        path.write_text(ambiguous)
        self.cli('validate', '--file', path, ok=False)
        self.save(before['progress'], before['sha256'], ok=False)
        self.assertEqual(path.read_text(), ambiguous)
        self.assertFalse((self.journey / 'progress.previous.json').exists())


if __name__ == '__main__':
    unittest.main()
