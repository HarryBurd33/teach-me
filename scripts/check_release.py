#!/usr/bin/env python3
"""Check portable release assets and links without third-party dependencies."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
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
    'docs/V0.3.0.md', 'docs/V0.4.0.md', 'docs/V0.5.0.md',
    'teach-me/scripts/journey_assets.py', 'teach-me/scripts/coherence_review.py',
    'teach-me/references/coherence-review.md', 'teach-me/templates/coherence-decisions.json',
    'teach-me/scripts/graph_workbench.py', 'teach-me/scripts/journey_versions.py',
    'teach-me/references/graph-workbench.md', 'teach-me/references/journey-versions.md',
    'teach-me/templates/graph-proposal.json', 'tests/test_graph_workbench.py',
    'tests/test_journey_versions.py', 'tests/test_typed_assets.py', 'tests/test_coherence_review.py', 'tests/test_v5_contract.py', 'tests/test_v5_output_limit.py', 'tests/test_report_publication.py',
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
    assert 'version: "0.5.0"' in skill.split('---', 2)[1], 'Release version mismatch'
    schema = json.loads((ROOT / 'teach-me/references/progress.schema.json').read_text())
    assert schema['$id'] == 'urn:teach-me:progress:v1'
    links = 0
    files = [p for p in ROOT.rglob('*')
             if p.is_file() and '.git' not in p.relative_to(ROOT).parts
             and '__pycache__' not in p.parts and p.suffix != '.pyc']
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
    print(json.dumps({'release': 'pass', 'files_checked': len(files),
                      'relative_links_checked': links, 'license': 'MIT'}))


if __name__ == '__main__':
    check()
