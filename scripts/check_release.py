#!/usr/bin/env python3
"""Check portable release assets and links without third-party dependencies."""
import json
import hashlib
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    'docs/V0.11.0.md', 'docs/ROADMAP.md', 'teach-me/scripts/draft_merge_check.py', 'teach-me/references/draft-merge-check.md', 'tests/test_draft_merge_check.py', 'tests/test_v11_contract.py', 'browser-tests/draft-merge-preflight.spec.js',
    'README.md', 'LICENSE', 'teach-me/SKILL.md', 'teach-me/LICENSE',
    'teach-me/references/domains.md', 'teach-me/references/research.md',
    'teach-me/references/state.md', 'teach-me/references/progress.schema.json',
    'teach-me/templates/plan.md', 'teach-me/templates/sources.md',
    'teach-me/scripts/journey.py', 'tests/test_journey.py', 'docs/VALIDATION.md',
    'teach-me/references/learning-harness.md', 'teach-me/references/harness-engineering.md',
    'teach-me/templates/knowledge.md', 'teach-me/templates/practice.md',
    'teach-me/templates/harness-project.md', 'docs/V0.2.0.md',
    'teach-me/scripts/learning_data.py', 'teach-me/scripts/storage.py',
    'teach-me/scripts/transfer.py', 'teach-me/scripts/harness.py',
    'teach-me/references/data-tools.md', 'teach-me/references/transfer.md',
    'teach-me/references/local-runtime.md', 'teach-me/references/host-integration.md',
    'teach-me/templates/harness-plan.json', 'teach-me/templates/learning-pilot.md',
    'tests/test_learning_data.py', 'tests/test_transfer.py', 'tests/test_harness.py',
    'docs/V0.3.0.md', 'docs/V0.4.0.md', 'docs/V0.5.0.md', 'docs/V0.6.0.md', 'docs/V0.7.0.md', 'docs/V0.8.0.md', 'docs/V0.9.0.md', 'docs/V0.10.0.md', 'teach-me/scripts/draft_merge.py', 'teach-me/references/draft-merge.md', 'teach-me/templates/draft-merge-decisions.json', 'teach-me/references/editor-recovery.md', 'tests/test_v9_contract.py', 'tests/v9-contract-runner.js', 'package-lock.json', 'playwright.config.js', '.github/workflows/browser.yml',
    'teach-me/scripts/graph_editor.py', 'teach-me/references/graph-editor.md',
    'teach-me/assets/graph-editor.html', 'teach-me/assets/graph-editor.js', 'teach-me/assets/graph-editor.css',
    'teach-me/scripts/snapshot_recovery.py', 'teach-me/references/snapshot-recovery.md',
    'teach-me/scripts/review_history.py', 'teach-me/scripts/snapshot_maintenance.py',
    'teach-me/references/review-history.md', 'teach-me/references/snapshot-maintenance.md',
    'teach-me/scripts/journey_assets.py', 'teach-me/scripts/coherence_review.py',
    'teach-me/references/coherence-review.md', 'teach-me/templates/coherence-decisions.json',
    'teach-me/scripts/graph_workbench.py', 'teach-me/scripts/journey_versions.py',
    'teach-me/references/graph-workbench.md', 'teach-me/references/journey-versions.md',
    'teach-me/templates/graph-proposal.json', 'tests/test_graph_workbench.py',
    'tests/test_journey_versions.py', 'tests/test_typed_assets.py', 'tests/test_coherence_review.py', 'tests/test_v5_contract.py', 'tests/test_v5_output_limit.py', 'tests/test_review_history.py', 'tests/test_snapshot_maintenance.py',
    'tests/test_v6_actual_limits.py', 'tests/test_v6_contract.py', 'tests/test_v6_faults.py', 'tests/test_history_import.py', 'tests/test_snapshot_recovery.py', 'tests/test_v7_contract.py', 'tests/_v7_frozen.py', 'tests/test_report_publication.py',
    'tests/test_v4_contract.py', 'tests/test_v4_failure_paths.py', 'tests/test_v4_atomic.py',
    'validation/fixtures/resume-one/learning/algebra/progress.json',
    'validation/fixtures/resume-many/learning/algebra/progress.json',
    'validation/fixtures/resume-many/learning/piano/progress.json',
    'validation/fixtures/resume-malformed/learning/algebra/progress.json',
]


def check():
    for relative in REQUIRED:
        path = ROOT / relative
        assert path.is_file() and not path.is_symlink(), relative
    license_text = (ROOT / 'LICENSE').read_text(encoding='utf-8')
    assert license_text.startswith('MIT License\n'), 'Root license is not MIT'
    assert license_text == (ROOT / 'teach-me/LICENSE').read_text(encoding='utf-8')
    skill = (ROOT / 'teach-me/SKILL.md').read_text(encoding='utf-8')
    assert skill.startswith('---\nname: teach-me\n'), 'Skill metadata/name mismatch'
    assert 'license: MIT\n' in skill.split('---', 2)[1]
    assert 'version: "0.11.0"' in skill.split('---', 2)[1], 'Release version mismatch'
    schema = json.loads((ROOT / 'teach-me/references/progress.schema.json').read_text())
    assert schema['$id'] == 'urn:teach-me:progress:v1'
    links = 0
    files = [p for p in ROOT.rglob('*')
             if p.is_file() and '.git' not in p.relative_to(ROOT).parts
             and not any(x in p.parts for x in ('__pycache__','node_modules','test-results','playwright-report')) and p.suffix != '.pyc']
    for path in files:
        relative = path.relative_to(ROOT)
        assert not path.is_symlink(), 'Symlink in release: ' + str(relative)
        assert not any(part in {'.checkpoint', '.forge', '.env'} for part in relative.parts)
        if path.suffix == '.json':
            if relative.as_posix() == 'validation/fixtures/resume-malformed/learning/algebra/progress.json':
                try:
                    json.loads(path.read_text(encoding='utf-8'))
                except json.JSONDecodeError:
                    pass
                else:
                    raise AssertionError('Malformed-state fixture must remain malformed')
            else:
                json.loads(path.read_text(encoding='utf-8'))
        if path.suffix != '.md':
            continue
        text = path.read_text(encoding='utf-8')
        assert not re.search(r'/(?:Users|home)/[^/\s]+/', text), 'Private local path in ' + str(relative)
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', text):
            if target.startswith(('https://', 'http://', '#', 'mailto:')):
                continue
            target = target.split('#', 1)[0].strip('<>')
            dest = (path.parent / target).resolve()
            assert ROOT == dest or ROOT in dest.parents, 'Escaping link: ' + target
            assert dest.exists(), 'Missing link from ' + str(relative) + ': ' + target
            links += 1
    evidence = ROOT / 'validation/v0.7.0'
    manifest = json.loads((evidence / 'public-evidence-hashes.json').read_text())
    assert type(manifest['version']) is int and manifest['version'] == 1
    for name, record in manifest['files'].items():
        relative = Path(name)
        assert not relative.is_absolute() and '..' not in relative.parts and relative.as_posix() == name
        item = evidence / relative
        assert not item.is_symlink() and item.is_file()
        assert evidence.resolve() in item.resolve().parents
        assert hashlib.sha256(item.read_bytes()).hexdigest() == record['published_sha256'], 'Published evidence hash mismatch: ' + name
    evidence = ROOT / 'validation/v0.8.0'
    manifest = json.loads((evidence / 'public-evidence-hashes.json').read_text())
    assert type(manifest['version']) is int and manifest['version'] == 1
    for name, record in manifest['files'].items():
        relative = Path(name)
        assert not relative.is_absolute() and '..' not in relative.parts and relative.as_posix() == name
        item = evidence / relative
        assert not item.is_symlink() and item.is_file()
        assert evidence.resolve() in item.resolve().parents
        assert hashlib.sha256(item.read_bytes()).hexdigest() == record['published_sha256'], 'Published evidence hash mismatch: ' + name
    evidence = ROOT / 'validation/v0.9.0'
    manifest = json.loads((evidence / 'public-evidence-hashes.json').read_text())
    assert type(manifest['version']) is int and manifest['version'] == 1
    for name, record in manifest['files'].items():
        relative = Path(name)
        assert not relative.is_absolute() and '..' not in relative.parts and relative.as_posix() == name
        item = evidence / relative
        assert not item.is_symlink() and item.is_file()
        assert evidence.resolve() in item.resolve().parents
        assert hashlib.sha256(item.read_bytes()).hexdigest() == record['published_sha256'], 'Published evidence hash mismatch: ' + name
    evidence = ROOT / 'validation/v0.10.0'
    manifest = json.loads((evidence / 'public-evidence-hashes.json').read_text())
    assert type(manifest['version']) is int and manifest['version'] == 1
    for name, record in manifest['files'].items():
        relative = Path(name)
        assert not relative.is_absolute() and '..' not in relative.parts and relative.as_posix() == name
        item = evidence / relative
        assert not item.is_symlink() and item.is_file()
        assert evidence.resolve() in item.resolve().parents
        assert hashlib.sha256(item.read_bytes()).hexdigest() == record['published_sha256'], 'Published evidence hash mismatch: ' + name
    evidence = ROOT / 'validation/v0.11.0'
    manifest = json.loads((evidence / 'public-evidence-hashes.json').read_text())
    assert type(manifest['version']) is int and manifest['version'] == 1
    for name, record in manifest['files'].items():
        relative = Path(name)
        assert not relative.is_absolute() and '..' not in relative.parts and relative.as_posix() == name
        item = evidence / relative
        assert not item.is_symlink() and item.is_file()
        assert evidence.resolve() in item.resolve().parents
        assert hashlib.sha256(item.read_bytes()).hexdigest() == record['published_sha256'], 'Published evidence hash mismatch: ' + name
    print(json.dumps({'release': 'pass', 'files_checked': len(files),
                      'relative_links_checked': links, 'license': 'MIT'}))


if __name__ == '__main__':
    check()
