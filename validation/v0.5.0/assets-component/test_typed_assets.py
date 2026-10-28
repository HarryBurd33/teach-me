"""Synthetic discriminating typed-transfer cases; no services or real learner data."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

SKILL = Path(os.environ.get('TEACH_ME_SKILL', Path(__file__).resolve().parents[1] / 'candidate/teach-me')).resolve()
SCRIPTS = SKILL / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import journey_assets as assets
import transfer
import journey_versions as versions
import coherence_review as review


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def proposal(raw):
    text = raw.decode('utf-8')
    return {'version': 1, 'source_sha256': hashlib.sha256(raw).hexdigest(),
            'nodes': [{'id': 'claim', 'name': 'Illustration', 'statement': text,
                       'evidence': {'start': 0, 'end': len(text), 'quote': text}}], 'chains': []}


def graph():
    return {'format': 'teach-me-learning-v1', 'source_files': [], 'sessions': [],
            'nodes': [{'id': 'known', 'name': 'Existing', 'statement': 'Prior claim',
                       'aliases': [], 'createdAt': '', 'provenance': []}],
            'chains': [], 'warnings': []}


class TypedAssets(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.workspace = self.root / 'workspace'; self.workspace.mkdir()
        self.cli('journey.py', 'init', '--root', self.workspace, '--id', 'logic',
                 '--topic', 'Logic', '--goal', 'Explain an example')
        self.j = self.workspace / 'learning/logic'
        self.out = self.root / 'export.zip'

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, script, *args, expected=0):
        p = subprocess.run([sys.executable, '-B', str(SCRIPTS / script), *map(str, args)],
                           capture_output=True, text=True, timeout=15)
        self.assertEqual(p.returncode, expected, p.stderr + p.stdout)
        return json.loads(p.stdout) if expected == 0 else p.stderr

    def files(self):
        return {name: (self.j / name).read_bytes() for name in assets.ALLOWED if (self.j / name).exists()}

    def typed(self):
        raw = 'A café claim.\r\n'.encode('utf-8')
        for name in assets.LEGACY_ALLOWED - assets.REQUIRED:
            (self.j / name).write_bytes(('Learner file: ' + name + '\r\n').encode())
        (self.j / 'knowledge-source.txt').write_bytes(raw)
        (self.j / 'knowledge-proposal.json').write_bytes(encode(proposal(raw)))
        (self.j / 'knowledge-graph.json').write_bytes(encode(graph()))

    def pack_files(self, name, files):
        directory = self.root / ('tree-' + name); directory.mkdir()
        selected = directory / 'logic'; selected.mkdir()
        for filename, raw in files.items(): (selected / filename).write_bytes(raw)
        output = self.root / (name + '.zip')
        transfer.pack(selected, output)
        return output

    def forged(self, files, version=2):
        manifest = {'version': version, 'files': {name: {'sha256': hashlib.sha256(raw).hexdigest(),
                                                       'size': len(raw)} for name, raw in files.items()}}
        with zipfile.ZipFile(self.out, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, raw in files.items(): archive.writestr(name, raw)
            archive.writestr('manifest.json', encode(manifest))

    def test_exact_ten_file_roundtrip_and_snapshot_restore(self):
        self.typed(); original = self.files(); self.assertEqual(len(original), 10)
        # Raw imports and old backups are intentionally excluded.
        (self.j / 'raw-export.json').write_bytes(b'private raw data')
        (self.j / 'journey-review.previous.json').write_bytes(b'previous receipt')
        packed = transfer.pack(self.j, self.out)
        self.assertEqual(packed['files'], 10)
        with zipfile.ZipFile(self.out) as archive:
            self.assertEqual(json.loads(archive.read('manifest.json'))['version'], 2)
        receiving = self.root / 'receiving'; receiving.mkdir()
        transfer.unpack(self.out, receiving, 'logic')
        restored = receiving / 'learning/logic'
        self.assertEqual({p.name: p.read_bytes() for p in restored.iterdir()}, original)
        store = self.root / 'store'; store.mkdir()
        first = versions.snapshot(self.j, store, 'none')
        destination = self.root / 'restored'; destination.mkdir()
        versions.restore(store, first['revision'], destination, 'logic')
        self.assertEqual({p.name: p.read_bytes() for p in (destination/'learning/logic').iterdir()}, original)

    def test_legacy_manifest_unchanged_and_readable(self):
        transfer.pack(self.j, self.out)
        with zipfile.ZipFile(self.out) as archive:
            self.assertEqual(json.loads(archive.read('manifest.json'))['version'], 1)
        self.assertEqual(transfer.inspect_archive(self.out), self.files())
        self.assertEqual(transfer.ALLOWED, assets.LEGACY_ALLOWED)

    def test_version_one_cannot_smuggle_typed_and_boolean_version_rejected(self):
        files = self.files(); files['knowledge-source.txt'] = b'valid UTF-8 source'
        for version in (1, True, 3):
            with self.subTest(version=version):
                self.forged(files, version)
                with self.assertRaises(ValueError): transfer.inspect_archive(self.out)

    def test_missing_source_stale_hash_and_wrong_quote_rejected_without_output(self):
        self.typed()
        source = self.j / 'knowledge-source.txt'; original = source.read_bytes()
        source.unlink()
        with self.assertRaises(ValueError): transfer.pack(self.j, self.out)
        source.write_bytes(b'changed source')
        with self.assertRaises(ValueError): transfer.pack(self.j, self.out)
        source.write_bytes(original)
        bad = proposal(original); bad['nodes'][0]['evidence']['quote'] = 'invented quote'
        (self.j / 'knowledge-proposal.json').write_bytes(encode(bad))
        with self.assertRaises(ValueError): transfer.pack(self.j, self.out)
        self.assertFalse(self.out.exists()); self.assertFalse((self.j / '.teach-me.lock').exists())

    def test_hash_valid_archive_with_invalid_graph_or_proposal_refused(self):
        self.typed(); files = self.files()
        for name, raw in [('knowledge-graph.json', b'{"format":"wrong"}'),
                          ('knowledge-proposal.json', b'{"version":1,"version":1}')]:
            with self.subTest(name=name):
                bad = dict(files); bad[name] = raw; self.forged(bad)
                with self.assertRaises(ValueError): transfer.inspect_archive(self.out)
        bad = dict(files); bad['knowledge-source.txt'] = b'\xff'; self.forged(bad)
        with self.assertRaises(ValueError): transfer.inspect_archive(self.out)

    def test_graph_sessions_refused_but_unresolved_drafts_preserved_and_warned(self):
        self.typed(); value = graph()
        value['chains'] = [{'id': 'draft', 'premises': ['missing'], 'conclusion': 'known',
                            'createdAt': '', 'provenance': []}]
        (self.j / 'knowledge-graph.json').write_bytes(encode(value))
        item = transfer.pack(self.j, self.out)
        self.assertTrue(any('Unresolved graph endpoints' in w for w in item['warnings']))
        self.assertEqual(transfer.inspect_archive(self.out)['knowledge-graph.json'], encode(value))
        self.out.unlink()
        value['sessions'] = [{'id': 's', 'title': '', 'kind': 'practice', 'events': []}]
        (self.j / 'knowledge-graph.json').write_bytes(encode(value))
        with self.assertRaises(ValueError): transfer.pack(self.j, self.out)

    def test_typed_symlink_and_existing_output_preserved(self):
        self.typed(); target = self.j / 'knowledge-source.txt'; target.unlink()
        target.symlink_to(self.root/'missing')
        with self.assertRaises(ValueError): transfer.pack(self.j, self.out)
        target.unlink(); target.write_bytes(b'new source')
        self.out.write_bytes(b'foreign output')
        with self.assertRaises(ValueError): transfer.pack(self.j, self.out)
        self.assertEqual(self.out.read_bytes(), b'foreign output')

    def test_byte_clean_merge_refuses_cross_file_source_proposal_mismatch(self):
        base_files = self.files(); base_files['knowledge-source.txt'] = b'Old source'
        local_files = dict(base_files); local_files['knowledge-source.txt'] = b'New source'
        incoming_files = dict(base_files)
        incoming_files['knowledge-proposal.json'] = encode(proposal(b'Old source'))
        paths = [self.pack_files(name, files) for name, files in
                 [('base', base_files), ('local', local_files), ('incoming', incoming_files)]]
        report = versions.compare(*paths, self.root/'report.json')
        self.assertFalse(report['conflicts'])
        with self.assertRaises(ValueError): versions.merge(*paths, self.root/'merged.zip')
        self.assertFalse((self.root/'merged.zip').exists())

    def test_valid_typed_merge_preserves_combined_files(self):
        self.typed(); base_files = self.files(); local_files = dict(base_files); incoming_files = dict(base_files)
        local_files['knowledge.md'] += b'Local learning note\n'
        incoming_files['practice.md'] += b'Incoming attempt\n'
        paths = [self.pack_files(name, files) for name, files in
                 [('base', base_files), ('local', local_files), ('incoming', incoming_files)]]
        merged = self.root/'merged.zip'; versions.merge(*paths, merged)
        result = transfer.inspect_archive(merged)
        self.assertEqual(result['knowledge.md'], local_files['knowledge.md'])
        self.assertEqual(result['practice.md'], incoming_files['practice.md'])
        for name in assets.TYPED_ALLOWED - {'journey-review.json'}:
            self.assertEqual(result[name], base_files[name])

    def test_content_fingerprint_omits_receipt_only(self):
        self.typed(); files = self.files(); before = assets.content_manifest(files)
        files['journey-review.json'] = b'arbitrary receipt ignored for fingerprint'
        self.assertEqual(assets.content_manifest(files), before)
        files['knowledge-source.txt'] += b'change'
        self.assertNotEqual(assets.content_manifest(files), before)

    def receipt(self):
        packet_path = self.root/'packet.json'
        packet = review.prepare(self.j, packet_path)
        decisions = {'version': 1, 'packet_sha256': packet['packet_sha256'],
                     'reviewer_role': 'tutor', 'decisions': [
                         {'check_id': item['check_id'], 'result': 'consistent',
                          'rationale': 'Synthetic fixture judgment: claims remain explicitly unverified.'}
                         for item in review.CHECKS]}
        decisions_path = self.root/'decisions.json'; decisions_path.write_bytes(encode(decisions))
        return review.record(self.j, packet_path, decisions_path, self.j/'journey-review.json')

    def test_exact_eleven_file_receipt_roundtrip_snapshot_and_stale_transport(self):
        self.typed(); self.receipt(); original = self.files()
        self.assertEqual(len(original), 11)
        self.assertTrue(review.verify(self.j, self.j/'journey-review.json')['resume_ready'])
        transfer.pack(self.j, self.out)
        receiving = self.root/'receiving'; receiving.mkdir()
        transfer.unpack(self.out, receiving, 'logic')
        restored = receiving/'learning/logic'
        self.assertEqual({p.name: p.read_bytes() for p in restored.iterdir()}, original)
        self.assertTrue(review.verify(restored, restored/'journey-review.json')['resume_ready'])
        store = self.root/'store'; store.mkdir()
        saved = versions.snapshot(self.j, store, 'none')
        destination = self.root/'restored'; destination.mkdir()
        versions.restore(store, saved['revision'], destination, 'logic')
        self.assertEqual({p.name: p.read_bytes() for p in (destination/'learning/logic').iterdir()}, original)
        (self.j/'plan.md').write_bytes(b'Edited plan requiring another consistency review')
        with self.assertRaises(ValueError): review.verify(self.j, self.j/'journey-review.json')
        stale = self.root/'stale.zip'; item = transfer.pack(self.j, stale)
        self.assertTrue(any('stale' in warning for warning in item['warnings']))
        self.assertEqual(transfer.inspect_archive(stale)['journey-review.json'], original['journey-review.json'])
        stale_root = self.root/'stale-receiving'; stale_root.mkdir()
        unpacked = transfer.unpack(stale, stale_root, 'logic')
        self.assertTrue(any('stale' in warning for warning in unpacked['warnings']))
        stale_journey = stale_root/'learning/logic'
        with self.assertRaises(ValueError): review.verify(stale_journey, stale_journey/'journey-review.json')

    def test_malformed_foreign_and_needs_changes_receipts(self):
        self.typed(); receipt = self.receipt()
        for field, value in [('semantic_correctness_verified', True), ('resume_ready', 1),
                             ('journey_id', 'other-journey')]:
            with self.subTest(field=field):
                bad = dict(receipt); bad[field] = value
                (self.j/'journey-review.json').write_bytes(encode(bad))
                with self.assertRaises(ValueError): transfer.pack(self.j, self.out)
                self.assertFalse(self.out.exists())
        receipt['decisions'][0]['result'] = 'needs_changes'; receipt['resume_ready'] = False
        raw = encode(receipt); (self.j/'journey-review.json').write_bytes(raw)
        packed = transfer.pack(self.j, self.out)
        self.assertTrue(any('needs_changes' in warning for warning in packed['warnings']))
        self.assertEqual(transfer.inspect_archive(self.out)['journey-review.json'], raw)
        self.cli('coherence_review.py', 'verify', '--journey', self.j,
                 '--receipt', self.j/'journey-review.json', expected=1)

    def test_matching_file_manifest_with_altered_packet_hash_warns_stale(self):
        self.typed(); receipt = self.receipt()
        receipt['packet_sha256'] = '0' * 64
        raw = encode(receipt); (self.j/'journey-review.json').write_bytes(raw)
        self.assertEqual(receipt['files'], assets.content_manifest(self.files()))
        packed = transfer.pack(self.j, self.out)
        self.assertTrue(any('stale' in warning for warning in packed['warnings']))
        self.assertEqual(transfer.inspect_archive(self.out)['journey-review.json'], raw)
        with self.assertRaises(ValueError): review.verify(self.j, self.j/'journey-review.json')


if __name__ == '__main__':
    unittest.main()
