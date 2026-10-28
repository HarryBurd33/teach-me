"""Frozen independent CLI contract cases. Written before candidate inspection."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

SKILL = Path(os.environ.get('TEACH_ME_SKILL', Path(__file__).resolve().parents[1] / 'teach-me')).resolve()
SCRIPTS = SKILL / 'scripts'
CHECKS = ['goal-stage-next-action', 'evidence-scope', 'sources-and-claims', 'merge-consistency']
CORE = {'plan.md', 'progress.json', 'sources.md'}
TYPED = {'knowledge-graph.json', 'knowledge-proposal.json', 'knowledge-source.txt', 'journey-review.json'}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


class V5Contract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.workspace = self.root / 'work'; self.workspace.mkdir()
        self.cli('journey.py', 'init', '--root', self.workspace, '--id', 'logic', '--topic', 'Logic', '--goal', 'Explain a joint argument')
        self.j = self.workspace / 'learning/logic'
        self.text = '🧠 A holds.\r\nB follows.\r\n'
        self.source = self.text.encode('utf-8')
        self.proposal = {'version': 1, 'source_sha256': sha(self.source), 'nodes': [
            {'id': 'A', 'name': 'A', 'statement': 'A holds', 'evidence': {'start': 0, 'end': 10, 'quote': '🧠 A holds.'}},
            {'id': 'B', 'name': 'B', 'statement': 'B follows', 'evidence': {'start': 12, 'end': 22, 'quote': 'B follows.'}}],
            'chains': [{'id': 'c', 'premises': ['A'], 'conclusion': 'B', 'evidence': {'start': 12, 'end': 22, 'quote': 'B follows.'}}]}

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, script, *args, code=0):
        result = subprocess.run([sys.executable, '-B', str(SCRIPTS / script), *map(str, args)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, code, result.stderr + result.stdout)
        return json.loads(result.stdout) if result.stdout and code == 0 else result

    def write(self, path, value):
        path.write_bytes(encoded(value)); return path

    def files(self, folder=None):
        folder = folder or self.j
        return {p.name: p.read_bytes() for p in folder.iterdir() if p.is_file() and (p.name in CORE | TYPED | {'knowledge.md', 'practice.md', 'harness-project.md', 'learning-pilot.md'})}

    def add_proposal(self):
        (self.j / 'knowledge-source.txt').write_bytes(self.source)
        self.write(self.j / 'knowledge-proposal.json', self.proposal)

    def add_graph(self):
        self.add_proposal()
        self.cli('graph_workbench.py', 'apply', '--source', self.j / 'knowledge-source.txt', '--proposal', self.j / 'knowledge-proposal.json', '--expected-proposal-sha256', sha((self.j / 'knowledge-proposal.json').read_bytes()), '--output', self.j / 'knowledge-graph.json', '--approve')

    def pack(self, name='bundle', folder=None):
        path = self.root / (name + '.zip')
        self.cli('transfer.py', 'pack', '--journey', folder or self.j, '--output', path)
        return path

    def packet(self, name='packet'):
        path = self.root / (name + '.json')
        self.cli('coherence_review.py', 'prepare', '--journey', self.j, '--output', path)
        return path, json.loads(path.read_bytes())

    def decisions(self, packet, name='decisions', result='consistent'):
        value = {'version': 1, 'packet_sha256': packet['packet_sha256'], 'reviewer_role': 'tutor', 'decisions': [
            {'check_id': check, 'result': result if i == 0 else 'consistent', 'rationale': 'Explicit fixture review of ' + check} for i, check in enumerate(CHECKS)]}
        return self.write(self.root / (name + '.json'), value)

    def receipt(self, name='journey-review.json', result='consistent'):
        packet_path, packet = self.packet()
        decisions = self.decisions(packet, result=result)
        out = self.j / name
        self.cli('coherence_review.py', 'record', '--journey', self.j, '--packet', packet_path, '--decisions', decisions, '--output', out)
        return out

    def test_legacy_v1_roundtrip(self):
        original = self.files()
        archive = self.pack()
        with zipfile.ZipFile(archive) as z:
            self.assertEqual(json.loads(z.read('manifest.json'))['version'], 1)
        receiving = self.root / 'receiving'; receiving.mkdir()
        self.cli('transfer.py', 'unpack', '--archive', archive, '--root', receiving, '--id', 'logic')
        self.assertEqual(self.files(receiving / 'learning/logic'), original)

    def test_typed_archive_and_snapshot_restore_exact_bytes(self):
        self.add_graph(); self.receipt()
        original = self.files(); self.assertEqual(len(original), 7)
        archive = self.pack()
        with zipfile.ZipFile(archive) as z:
            manifest = json.loads(z.read('manifest.json'))
            self.assertEqual(manifest['version'], 2)
            self.assertEqual(set(manifest['files']), set(original))
            for name, raw in original.items(): self.assertEqual(z.read(name), raw)
        store = self.root / 'store'; store.mkdir()
        snap = self.cli('journey_versions.py', 'snapshot', '--journey', self.j, '--store', store, '--expected-head', 'none')
        receiving = self.root / 'receiving'; receiving.mkdir()
        self.cli('journey_versions.py', 'restore', '--store', store, '--revision', snap['revision'], '--root', receiving, '--id', 'logic')
        restored = receiving / 'learning/logic'
        self.assertEqual(self.files(restored), original)
        self.cli('coherence_review.py', 'verify', '--journey', restored, '--receipt', restored / 'journey-review.json')

    def test_v1_cannot_smuggle_typed_member(self):
        archive = self.pack(); files = {}
        with zipfile.ZipFile(archive) as z:
            files = {name: z.read(name) for name in z.namelist()}
        manifest = json.loads(files['manifest.json']); raw = b'Chosen source\n'
        manifest['files']['knowledge-source.txt'] = {'sha256': sha(raw), 'size': len(raw)}
        files['knowledge-source.txt'] = raw; files['manifest.json'] = encoded(manifest)
        bad = self.root / 'smuggled.zip'
        with zipfile.ZipFile(bad, 'w') as z:
            for name, raw in files.items(): z.writestr(name, raw)
        receiving = self.root / 'receiving'; receiving.mkdir()
        self.cli('transfer.py', 'unpack', '--archive', bad, '--root', receiving, '--id', 'logic', code=2)
        self.assertFalse((receiving / 'learning/logic').exists())

    def test_proposal_stale_hash_quote_and_missing_source_rejected(self):
        self.add_proposal(); old = (self.j / 'knowledge-proposal.json').read_bytes()
        for mutation in ('hash', 'quote', 'source'):
            with self.subTest(mutation=mutation):
                value = copy.deepcopy(self.proposal)
                if mutation == 'hash': value['source_sha256'] = '0' * 64
                if mutation == 'quote': value['nodes'][0]['evidence']['quote'] = 'Invented'
                self.write(self.j / 'knowledge-proposal.json', value)
                (self.j / 'knowledge-source.txt').write_bytes(self.source)
                if mutation == 'source': (self.j / 'knowledge-source.txt').unlink()
                out = self.root / (mutation + '.zip')
                self.cli('transfer.py', 'pack', '--journey', self.j, '--output', out, code=2)
                self.assertFalse(out.exists())
        self.assertNotEqual(old, b'')

    def test_malformed_graph_sessions_and_duplicate_json_rejected(self):
        self.add_graph(); graphpath = self.j / 'knowledge-graph.json'; graph = json.loads(graphpath.read_bytes())
        for i, value in enumerate((dict(graph, nodes='bad'), dict(graph, sessions=[{'id': 'not-graph'}]))):
            self.write(graphpath, value)
            out = self.root / ('bad' + str(i) + '.zip')
            self.cli('transfer.py', 'pack', '--journey', self.j, '--output', out, code=2)
            self.assertFalse(out.exists())
        graphpath.write_bytes(b'{"format":"teach-me-learning-v1","format":"teach-me-learning-v1"}')
        self.cli('transfer.py', 'pack', '--journey', self.j, '--output', self.root / 'duplicate.zip', code=2)

    def test_clean_file_merge_rejects_new_crossfile_source_mismatch(self):
        (self.j / 'knowledge-source.txt').write_bytes(self.source)
        base_files = self.files(); local = dict(base_files); incoming = dict(base_files)
        local['knowledge-source.txt'] = b'Different chosen source\n'
        incoming['knowledge-proposal.json'] = encoded(self.proposal)
        archives = []
        for name, files in [('base', base_files), ('local', local), ('incoming', incoming)]:
            folder = self.root / name / 'logic'; folder.mkdir(parents=True)
            for key, raw in files.items(): (folder / key).write_bytes(raw)
            archives.append(self.pack(name, folder))
        report = self.root / 'compare.json'
        self.cli('journey_versions.py', 'compare', '--base', archives[0], '--local', archives[1], '--incoming', archives[2], '--output', report)
        self.assertEqual(json.loads(report.read_bytes())['conflicts'], [])
        output = self.root / 'merged.zip'
        self.cli('journey_versions.py', 'merge', '--base', archives[0], '--local', archives[1], '--incoming', archives[2], '--output', output, code=2)
        self.assertFalse(output.exists())

    def test_packet_closed_keys_and_source_digest_freshness(self):
        packetpath, packet = self.packet()
        self.assertEqual(set(packet), {'version', 'journey_id', 'files', 'checks', 'summary', 'packet_sha256'})
        self.assertEqual(packet['journey_id'], 'logic')
        self.assertFalse(packet['summary']['semantic_correctness_verified'])
        self.assertEqual(set(packet['files']), CORE)
        for name, record in packet['files'].items():
            raw = (self.j / name).read_bytes(); self.assertEqual(record, {'sha256': sha(raw), 'size': len(raw)})
        decisions = self.decisions(packet)
        (self.j / 'plan.md').write_bytes(b'Changed plan after packet\n')
        output = self.j / 'journey-review.json'
        self.cli('coherence_review.py', 'record', '--journey', self.j, '--packet', packetpath, '--decisions', decisions, '--output', output, code=2)
        self.assertFalse(output.exists())

    def test_needs_changes_is_recorded_but_not_ready(self):
        receipt = self.receipt(result='needs_changes'); value = json.loads(receipt.read_bytes())
        self.assertIs(value['resume_ready'], False)
        self.assertIs(value['semantic_correctness_verified'], False)
        self.cli('coherence_review.py', 'verify', '--journey', self.j, '--receipt', receipt, code=1)

    def test_optional_addition_and_deletion_stale_a_receipt(self):
        receipt = self.receipt(); optional = self.j / 'knowledge.md'; optional.write_bytes(b'New learner notes\n')
        self.cli('coherence_review.py', 'verify', '--journey', self.j, '--receipt', receipt, code=2)
        optional.unlink()
        self.cli('coherence_review.py', 'verify', '--journey', self.j, '--receipt', receipt)
        (self.j / 'sources.md').unlink()
        self.cli('coherence_review.py', 'verify', '--journey', self.j, '--receipt', receipt, code=2)

    def test_stale_receipt_preserved_as_history_through_transfer(self):
        receipt = self.receipt(); original = receipt.read_bytes()
        (self.j / 'practice.md').write_bytes(b'Attempt after review\n')
        archive = self.pack(); receiving = self.root / 'receiving'; receiving.mkdir()
        self.cli('transfer.py', 'unpack', '--archive', archive, '--root', receiving, '--id', 'logic')
        restored = receiving / 'learning/logic'
        self.assertEqual((restored / 'journey-review.json').read_bytes(), original)
        self.cli('coherence_review.py', 'verify', '--journey', restored, '--receipt', restored / 'journey-review.json', code=2)

    def test_receipt_derived_ready_boolean_and_unknown_fields_rejected(self):
        receipt = self.receipt(result='needs_changes'); original = json.loads(receipt.read_bytes())
        for i, value in enumerate((dict(original, resume_ready=True), dict(original, semantic_correctness_verified=True), dict(original, resume_ready=0), dict(original, invented='extra'))):
            self.write(receipt, value)
            self.cli('coherence_review.py', 'verify', '--journey', self.j, '--receipt', receipt, code=2)
            out = self.root / ('badreceipt' + str(i) + '.zip')
            self.cli('transfer.py', 'pack', '--journey', self.j, '--output', out, code=2)
            self.assertFalse(out.exists())

    def test_incomplete_blank_duplicate_decisions_write_nothing(self):
        packetpath, packet = self.packet(); good = json.loads(self.decisions(packet).read_bytes())
        values = []
        value = copy.deepcopy(good); value['decisions'].pop(); values.append(value)
        value = copy.deepcopy(good); value['decisions'][0]['rationale'] = '  '; values.append(value)
        value = copy.deepcopy(good); value['decisions'][1]['check_id'] = CHECKS[0]; values.append(value)
        value = copy.deepcopy(good); value['packet_sha256'] = '0' * 64; values.append(value)
        for i, value in enumerate(values):
            decisions = self.write(self.root / ('baddecisions' + str(i) + '.json'), value)
            out = self.root / ('receipt' + str(i) + '.json')
            self.cli('coherence_review.py', 'record', '--journey', self.j, '--packet', packetpath, '--decisions', decisions, '--output', out, code=2)
            self.assertFalse(out.exists())

    def test_wrong_replacement_hash_preserves_existing_receipt(self):
        receipt = self.receipt(); before = receipt.read_bytes()
        packetpath, packet = self.packet('secondpacket'); decisions = self.decisions(packet, 'seconddecisions')
        self.cli('coherence_review.py', 'record', '--journey', self.j, '--packet', packetpath, '--decisions', decisions, '--output', receipt, '--expected-output-sha256', '0' * 64, code=2)
        self.assertEqual(receipt.read_bytes(), before)
        self.assertFalse((self.j / 'journey-review.previous.json').exists())
        self.cli('coherence_review.py', 'record', '--journey', self.j, '--packet', packetpath, '--decisions', decisions, '--output', receipt, '--expected-output-sha256', sha(before))
        self.assertEqual((self.j / 'journey-review.previous.json').read_bytes(), before)
        self.cli('coherence_review.py', 'verify', '--journey', self.j, '--receipt', receipt)

    def test_existing_foreign_output_and_content_overwrite_protected(self):
        packetpath, packet = self.packet(); decisions = self.decisions(packet)
        for name in ('plan.md', 'progress.json', 'knowledge-graph.json'):
            output = self.j / name
            if not output.exists(): output.write_bytes(b'FOREIGN CONTENT')
            before = output.read_bytes()
            self.cli('coherence_review.py', 'record', '--journey', self.j, '--packet', packetpath, '--decisions', decisions, '--output', output, '--expected-output-sha256', sha(before), code=2)
            self.assertEqual(output.read_bytes(), before)
        foreign = self.root / 'existing.json'; foreign.write_bytes(b'FOREIGN CONTENT')
        self.cli('coherence_review.py', 'prepare', '--journey', self.j, '--output', foreign, code=2)
        self.assertEqual(foreign.read_bytes(), b'FOREIGN CONTENT')


if __name__ == '__main__':
    unittest.main()
