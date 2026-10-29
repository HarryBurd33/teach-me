#!/usr/bin/env python3
"""Learning-state utility with cooperative local writer locking. Python 3.9+, standard library."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

from storage import StorageError, checked_path, destination_lock, journey_lock

SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
STAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?(?:Z|[+-][0-9]{2}:[0-9]{2})\Z")
FIELDS = {'schema_version', 'journey_id', 'topics', 'goal', 'current_stage',
          'availability', 'assessments', 'evidence', 'difficulties', 'decisions',
          'next_action', 'updated_at'}


class StateError(ValueError):
    pass


def fail(message):
    raise StateError(message)


def keys(value, expected, where):
    if not isinstance(value, dict) or set(value) != expected:
        fail(where + ': required keys must match exactly: ' + ', '.join(sorted(expected)))


def string(value, where, empty=False):
    if not isinstance(value, str) or (not empty and not value.strip()):
        fail(where + ': expected ' + ('a string' if empty else 'a nonempty string'))


def strings(value, where, nonempty=False):
    if not isinstance(value, list) or (nonempty and not value):
        fail(where + ': expected ' + ('a nonempty list' if nonempty else 'a list'))
    for item in value:
        string(item, where + ' item')


def timestamp(value, where):
    string(value, where)
    if not STAMP.fullmatch(value):
        fail(where + ': expected ISO 8601 date and time with timezone')
    try:
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            fail(where + ': timezone required')
    except (ValueError, TypeError):
        fail(where + ': expected an ISO 8601 timestamp with timezone')


def validate(state):
    keys(state, FIELDS, 'progress')
    if type(state['schema_version']) is not int or state['schema_version'] != 1:
        fail('schema_version: supported version is integer 1')
    if not isinstance(state['journey_id'], str) or not SLUG.fullmatch(state['journey_id']):
        fail('journey_id: expected lowercase hyphenated slug')
    strings(state['topics'], 'topics', nonempty=True)
    for field in ('goal', 'current_stage', 'next_action'):
        string(state[field], field)
    keys(state['availability'], {'minutes_per_day', 'session_minutes'}, 'availability')
    for field, value in state['availability'].items():
        if value is not None and (type(value) is not int or value < 0):
            fail('availability.' + field + ': expected nonnegative integer or null')
    for field in ('difficulties', 'decisions'):
        strings(state[field], field)
    timestamp(state['updated_at'], 'updated_at')
    if not isinstance(state['evidence'], list) or not isinstance(state['assessments'], list):
        fail('evidence and assessments must be lists')
    evidence = {}
    for item in state['evidence']:
        keys(item, {'id', 'kind', 'summary', 'recorded_at'}, 'evidence item')
        string(item['id'], 'evidence.id')
        string(item['summary'], 'evidence.summary')
        if item['kind'] not in ('observed', 'self_reported'):
            fail('evidence.kind: expected observed or self_reported')
        timestamp(item['recorded_at'], 'evidence.recorded_at')
        if item['id'] in evidence:
            fail('evidence.id: duplicate ID')
        evidence[item['id']] = item
    assessment_ids = set()
    for item in state['assessments']:
        keys(item, {'id', 'task', 'result', 'evidence_ids', 'feedback'}, 'assessment item')
        string(item['id'], 'assessment.id')
        string(item['task'], 'assessment.task')
        string(item['feedback'], 'assessment.feedback', empty=True)
        if item['id'] in assessment_ids:
            fail('assessment.id: duplicate ID')
        assessment_ids.add(item['id'])
        if item['result'] not in ('pending', 'needs_review', 'demonstrated'):
            fail('assessment.result: expected pending, needs_review or demonstrated')
        strings(item['evidence_ids'], 'assessment.evidence_ids')
        if any(eid not in evidence for eid in item['evidence_ids']):
            fail('assessment.evidence_ids: unknown evidence ID')
        if item['result'] == 'demonstrated' and not any(
                evidence[eid]['kind'] == 'observed' for eid in item['evidence_ids']):
            fail('demonstrated assessment needs observed evidence, not only self-report')
    return state


def reject_constant(value):
    fail('Nonfinite JSON number is not allowed: ' + value)


def unique_members(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            fail('Duplicate JSON member is ambiguous: ' + key)
        result[key] = value
    return result


def load(path):
    raw = path.read_bytes()
    try:
        data = json.loads(raw, parse_constant=reject_constant,
                          object_pairs_hook=unique_members)
    except (ValueError, UnicodeError) as exc:
        fail('Malformed JSON in ' + str(path) + ': ' + str(exc))
    return validate(data), raw


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(state):
    return (json.dumps(state, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def no_symlinks(path, stop=None):
    """Reject symlinks from path through stop, inclusive; never resolve first."""
    path = Path(os.path.abspath(path))
    while True:
        if path.is_symlink():
            fail('Refusing symlink: ' + str(path))
        if path == stop or path.parent == path:
            break
        path = path.parent


def writable_journey(path):
    path = Path(os.path.abspath(path))
    # Reject symlinks through the workspace root in the learning/journey layout.
    no_symlinks(path, stop=path.parent.parent)
    if not path.is_dir():
        fail('Journey directory does not exist: ' + str(path))
    for name in ('progress.json', 'progress.previous.json', 'progress.lock'):
        if (path / name).is_symlink():
            fail('Refusing symlink: ' + str(path / name))
    return path


def atomic_write(path, raw):
    fd, temp = tempfile.mkstemp(prefix='.' + path.name + '-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def initial(args):
    if not SLUG.fullmatch(args.id):
        fail('--id must be a lowercase hyphenated slug')
    root = Path(os.path.abspath(args.root))
    # Only the approved root and its descendants are the init write scope.
    checked_path(root)
    if root.is_symlink() or not root.is_dir():
        fail('--root must be an existing, nonsymlink approved workspace directory')
    learning = root / 'learning'
    target = learning / args.id
    no_symlinks(target, stop=root)
    if target.exists():
        fail('Journey already exists; nothing was overwritten')
    state = {'schema_version': 1, 'journey_id': args.id, 'topics': args.topic,
             'goal': args.goal, 'current_stage': 'baseline',
             'availability': {'minutes_per_day': None, 'session_minutes': None},
             'assessments': [], 'evidence': [], 'difficulties': [], 'decisions': [],
             'next_action': 'Establish the baseline and first useful practice task.',
             'updated_at': dt.datetime.now(dt.timezone.utc).isoformat()}
    validate(state)
    learning.mkdir(exist_ok=True)
    with destination_lock(learning, args.id):
        if target.exists():
            fail('Journey appeared during init; nothing was overwritten')
        temp = Path(tempfile.mkdtemp(prefix='.' + args.id + '-', dir=str(learning)))
        try:
            (temp / 'progress.json').write_bytes(encoded(state))
            templates = Path(__file__).resolve().parent.parent / 'templates'
            for name in ('plan.md', 'sources.md'):
                source = templates / name
                content = source.read_text(encoding='utf-8') if source.is_file() else '# ' + name[:-3].capitalize() + '\n\nTo be completed with the learner.\n'
                (temp / name).write_text(content, encoding='utf-8')
            no_symlinks(target, stop=root)
            if target.exists():
                fail('Journey appeared during init; nothing was overwritten')
            os.rename(temp, target)
        finally:
            if temp.exists():
                shutil.rmtree(temp)
    return {'journey': str(target), 'sha256': digest((target / 'progress.json').read_bytes())}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init', help='Create one new journey; refuses an existing folder')
    init.add_argument('--root', required=True)
    init.add_argument('--id', required=True)
    init.add_argument('--topic', action='append', required=True)
    init.add_argument('--goal', required=True)
    show = commands.add_parser('show', help='Read validated state and its SHA256')
    show.add_argument('--journey', required=True)
    check = commands.add_parser('validate', help='Validate a state without writing')
    check.add_argument('--file', required=True)
    save = commands.add_parser('save', help='Replace valid state only if its hash still matches')
    save.add_argument('--journey', required=True)
    save.add_argument('--input', required=True)
    save.add_argument('--expected-sha256', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'init':
            result = initial(args)
        elif args.command == 'validate':
            _, raw = load(Path(args.file))
            result = {'valid': True, 'sha256': digest(raw)}
        elif args.command == 'show':
            path = writable_journey(args.journey)
            state, raw = load(path / 'progress.json')
            if state['journey_id'] != path.name:
                fail('journey_id does not match its folder; reconcile before resume')
            result = {'sha256': digest(raw), 'progress': state}
        else:
            path = writable_journey(args.journey)
            with journey_lock(path):
                current, raw = load(path / 'progress.json')
                if current['journey_id'] != path.name:
                    fail('journey_id does not match its folder; reconcile before saving')
                if digest(raw) != args.expected_sha256:
                    fail('Stale expected hash; reread and reconcile before saving')
                state, _ = load(Path(args.input))
                if state['journey_id'] != current['journey_id']:
                    fail('journey_id is immutable')
                replacement = encoded(state)
                atomic_write(path / 'progress.previous.json', raw)
                atomic_write(path / 'progress.json', replacement)
                result = {'saved': True, 'sha256': digest(replacement),
                          'backup': str(path / 'progress.previous.json')}
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, StateError, StorageError) as exc:
        print('Error: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
