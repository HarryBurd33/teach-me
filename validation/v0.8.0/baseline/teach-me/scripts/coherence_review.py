#!/usr/bin/env python3
"""Hash-bound operator consistency review. Python 3.9+, standard library only.

This records judgments; it does not automatically understand claims or certify truth,
mastery, human identity, authorization, or permission to resume any external task.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

import journey
import journey_assets as assets
from storage import StorageError, checked_path, journey_lock

FILE_LIMIT = 2 * 1024 * 1024
TOTAL_LIMIT = 16 * 1024 * 1024
META_LIMIT = 2 * 1024 * 1024
SHA = re.compile(r'[0-9a-f]{64}\Z')
CHECKS = [
    {'check_id': 'goal-stage-next-action',
     'question': 'Do the plan, current stage and next action agree with the learner goal and constraints?'},
    {'check_id': 'evidence-scope',
     'question': 'Are assessment claims supported by the recorded attempts and evidence, with help and self-report distinguished?'},
    {'check_id': 'sources-and-claims',
     'question': 'Do the source notes, knowledge claims and graph/proposal agree, with uncertainty and provenance preserved?'},
    {'check_id': 'merge-consistency',
     'question': 'Do the combined files make sense together after any merge, restore or edit, with contradictions and missing information resolved?'}
]
CHECK_IDS = {item['check_id'] for item in CHECKS}
PACKET_KEYS = {'version', 'journey_id', 'files', 'checks', 'summary', 'packet_sha256'}
RECEIPT_KEYS = {'version', 'journey_id', 'files', 'packet_sha256', 'reviewer_role',
                'decisions', 'recorded_at', 'resume_ready', 'semantic_correctness_verified'}


def fail(message):
    raise StorageError(message)


def exact(value, keys, where):
    if not isinstance(value, dict) or set(value) != set(keys):
        fail(where + ': keys must match exactly: ' + ', '.join(sorted(keys)))


def version(value, keys, where):
    exact(value, keys, where)
    if type(value['version']) is not int or value['version'] != 1:
        fail(where + ': supported version is integer 1')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def check_digest(value, where):
    if not isinstance(value, str) or not SHA.fullmatch(value):
        fail(where + ': expected lowercase SHA256 hex')
    return value


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def strict_json(raw):
    return json.loads(raw, object_pairs_hook=journey.unique_members,
                      parse_constant=journey.reject_constant)


def read_regular(path, limit=FILE_LIMIT):
    path = checked_path(path)
    fd = os.open(str(path), os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) |
                 getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as handle:
        before = os.fstat(handle.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            fail('Not a bounded regular file: ' + path.name)
        raw = handle.read(limit + 1)
        after = os.fstat(handle.fileno())
    if (len(raw) > limit or
            (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) !=
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
        fail('File changed while reading: ' + path.name)
    return raw


def identity(value):
    if not isinstance(value, str) or not journey.SLUG.fullmatch(value):
        fail('journey_id must be a lowercase hyphenated slug')


def validate_manifest(value):
    if not isinstance(value, dict) or not assets.REQUIRED <= set(value) <= assets.CONTENT_FILES:
        fail('Review files must be the explicit content allowlist with all three required files')
    total = 0
    for name, record in value.items():
        exact(record, {'sha256', 'size'}, 'review file ' + name)
        check_digest(record['sha256'], name + '.sha256')
        if type(record['size']) is not int or not 0 <= record['size'] <= FILE_LIMIT:
            fail(name + '.size: expected a bounded nonnegative integer')
        total += record['size']
    if total > TOTAL_LIMIT:
        fail('Review content exceeds total size limit')
    return value


def validate_decisions(value):
    if not isinstance(value, list) or len(value) != len(CHECK_IDS):
        fail('Review requires exactly the four check decisions')
    seen = set()
    for item in value:
        exact(item, {'check_id', 'result', 'rationale'}, 'decision')
        key = item['check_id']
        if not isinstance(key, str) or key not in CHECK_IDS or key in seen:
            fail('Decision check IDs must be the exact four unique IDs')
        seen.add(key)
        if item['result'] not in ('consistent', 'needs_changes'):
            fail('Decision result must be consistent or needs_changes')
        if not isinstance(item['rationale'], str) or not item['rationale'].strip():
            fail('Every decision needs a nonempty rationale based on inspected content')
    return all(item['result'] == 'consistent' for item in value)


def reviewer_role(value):
    if value not in ('tutor', 'learner', 'other'):
        fail('reviewer_role must be tutor, learner or other')


def validate_receipt(value):
    """Validate historical receipt shape; intentionally does not assert freshness."""
    version(value, RECEIPT_KEYS, 'receipt')
    identity(value['journey_id'])
    validate_manifest(value['files'])
    check_digest(value['packet_sha256'], 'packet_sha256')
    reviewer_role(value['reviewer_role'])
    ready = validate_decisions(value['decisions'])
    journey.timestamp(value['recorded_at'], 'recorded_at')
    if type(value['resume_ready']) is not bool or value['resume_ready'] != ready:
        fail('resume_ready must be a boolean derived from all four decisions')
    if value['semantic_correctness_verified'] is not False:
        fail('semantic_correctness_verified must remain false')
    return value


def read_content(directory):
    files = {}
    for name in sorted(assets.CONTENT_FILES):
        path = checked_path(directory / name)
        if path.exists():
            files[name] = read_regular(path)
        elif name in assets.REQUIRED:
            fail('Missing required journey file: ' + name)
    if sum(map(len, files.values())) > TOTAL_LIMIT:
        fail('Journey exceeds total content limit')
    state = journey.validate(strict_json(files['progress.json']))
    if state['journey_id'] != directory.name:
        fail('Progress journey_id must match the selected journey folder')
    assets.validate_assets(files)
    return files, state


def packet_for(directory, files, state):
    warnings = assets.validate_assets(files)
    if 'knowledge-proposal.json' in files:
        warnings.append('Proposal remains a draft; transport does not apply it or establish its claims.')
    result = {'version': 1, 'journey_id': state['journey_id'],
              'files': assets.content_manifest(files), 'checks': CHECKS,
              'summary': {'goal': state['goal'], 'current_stage': state['current_stage'],
                          'next_action': state['next_action'],
                          'assessment_count': len(state['assessments']),
                          'evidence_count': len(state['evidence']),
                          'typed_files': sorted(set(files) & assets.TYPED_ALLOWED),
                          'warnings': warnings,
                          'semantic_correctness_verified': False}}
    result['packet_sha256'] = digest(canonical(result))
    return result


def validate_packet(value):
    version(value, PACKET_KEYS, 'packet')
    identity(value['journey_id'])
    validate_manifest(value['files'])
    check_digest(value['packet_sha256'], 'packet_sha256')
    if value['checks'] != CHECKS or not isinstance(value['summary'], dict):
        fail('Packet questions or summary are not the current review contract')
    body = {key: item for key, item in value.items() if key != 'packet_sha256'}
    if digest(canonical(body)) != value['packet_sha256']:
        fail('Packet digest mismatch')
    return value


def selected_journey(value):
    directory = checked_path(value)
    if not directory.is_dir():
        fail('Journey must be an existing directory')
    return directory


def output_path(value, directory, receipt=False):
    output = checked_path(value)
    if not output.parent.is_dir():
        fail('Output parent must be an existing directory')
    protected = set(assets.ALLOWED) | {'journey-review.previous.json', 'progress.previous.json',
                                     '.teach-me.lock'}
    if output.parent == directory and output.name in protected:
        if not (receipt and output.name == 'journey-review.json'):
            fail('Review output may not overwrite or create a protected journey content file')
    return output


def unchanged(directory, files):
    current, _ = read_content(directory)
    if current != files:
        fail('Journey content changed; prepare a fresh packet before recording')


def stage(path, raw):
    if len(raw) > META_LIMIT:
        fail('Review output exceeds bounded metadata size limit')
    fd, temporary = tempfile.mkstemp(prefix='.teach-me-review-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        os.unlink(temporary)
        raise
    return Path(temporary)


def write_new(output, raw, before_publish):
    temporary = stage(output, raw)
    try:
        before_publish()
        checked_path(output)
        os.link(str(temporary), str(output))
    finally:
        if temporary.exists():
            temporary.unlink()


def prepare(journey_path, output):
    directory = selected_journey(journey_path)
    output = output_path(output, directory)
    with journey_lock(directory):
        files, state = read_content(directory)
        value = packet_for(directory, files, state)
        write_new(output, encoded(value), lambda: unchanged(directory, files))
    return value


def record(journey_path, packet_path, decisions_path, output, expected_output_sha256=None):
    directory = selected_journey(journey_path)
    output = output_path(output, directory, receipt=True)
    canonical_output = directory / 'journey-review.json'
    if expected_output_sha256 is not None:
        check_digest(expected_output_sha256, 'expected-output-sha256')
        if output != canonical_output:
            fail('Digest replacement is allowed only for canonical journey-review.json')
    with journey_lock(directory):
        packet_raw = read_regular(packet_path, META_LIMIT)
        packet = validate_packet(strict_json(packet_raw))
        decisions_raw = read_regular(decisions_path, META_LIMIT)
        choice = strict_json(decisions_raw)
        version(choice, {'version', 'packet_sha256', 'reviewer_role', 'decisions'}, 'decisions')
        if choice['packet_sha256'] != packet['packet_sha256']:
            fail('Decision packet digest differs; inspect the current packet')
        reviewer_role(choice['reviewer_role'])
        ready = validate_decisions(choice['decisions'])
        files, state = read_content(directory)
        if packet != packet_for(directory, files, state):
            fail('Packet is stale or differs from the current journey; prepare a fresh packet')
        receipt = {'version': 1, 'journey_id': state['journey_id'], 'files': packet['files'],
                   'packet_sha256': packet['packet_sha256'], 'reviewer_role': choice['reviewer_role'],
                   'decisions': choice['decisions'], 'recorded_at': dt.datetime.now(dt.timezone.utc).isoformat(),
                   'resume_ready': ready, 'semantic_correctness_verified': False}
        validate_receipt(receipt)
        raw = encoded(receipt)

        def inputs_unchanged():
            unchanged(directory, files)
            if read_regular(packet_path, META_LIMIT) != packet_raw or read_regular(decisions_path, META_LIMIT) != decisions_raw:
                fail('Packet or decisions changed while recording')

        if expected_output_sha256 is None:
            write_new(output, raw, inputs_unchanged)
        else:
            old = read_regular(output, META_LIMIT)
            old_value = validate_receipt(strict_json(old))
            if old_value['journey_id'] != state['journey_id']:
                fail('Existing receipt belongs to another journey; nothing was overwritten')
            if digest(old) != expected_output_sha256:
                fail('Receipt changed; expected output digest mismatch')
            previous = checked_path(directory / 'journey-review.previous.json')
            previous_raw = read_regular(previous, META_LIMIT) if previous.exists() else None
            if previous_raw is not None:
                previous_value = validate_receipt(strict_json(previous_raw))
                if previous_value['journey_id'] != state['journey_id']:
                    fail('Previous receipt belongs to another journey; nothing was overwritten')
            new_stage = stage(output, raw)
            old_stage = None
            try:
                old_stage = stage(previous, old)
                inputs_unchanged()
                if read_regular(output, META_LIMIT) != old:
                    fail('Receipt changed while replacing')
                checked_path(previous)
                if previous.exists() != (previous_raw is not None):
                    fail('Previous receipt changed while replacing')
                if previous_raw is not None and read_regular(previous, META_LIMIT) != previous_raw:
                    fail('Previous receipt changed while replacing')
                os.replace(str(old_stage), str(previous))
                os.replace(str(new_stage), str(output))
            finally:
                for temporary in (old_stage, new_stage):
                    if temporary is not None and temporary.exists():
                        temporary.unlink()
    return receipt


def verify(journey_path, receipt_path):
    directory = selected_journey(journey_path)
    with journey_lock(directory):
        receipt_raw = read_regular(receipt_path, META_LIMIT)
        receipt = validate_receipt(strict_json(receipt_raw))
        files, state = read_content(directory)
        current = packet_for(directory, files, state)
        if (receipt['journey_id'] != state['journey_id'] or receipt['files'] != current['files'] or
                receipt['packet_sha256'] != current['packet_sha256']):
            fail('Receipt is stale or belongs to another journey; inspect current content and record a fresh review')
        unchanged(directory, files)
        if read_regular(receipt_path, META_LIMIT) != receipt_raw:
            fail('Receipt changed while verifying')
    return {'current': True, 'resume_ready': receipt['resume_ready'],
            'semantic_correctness_verified': False, 'journey_id': receipt['journey_id'],
            'meaning': 'Recorded operator consistency judgments; no truth, mastery, human identity or authorization certification'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('prepare', 'record', 'verify'):
        p = commands.add_parser(name)
        p.add_argument('--journey', required=True)
        if name in ('prepare', 'record'):
            p.add_argument('--output', required=True)
        if name == 'record':
            p.add_argument('--packet', required=True)
            p.add_argument('--decisions', required=True)
            p.add_argument('--expected-output-sha256')
        if name == 'verify':
            p.add_argument('--receipt', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'prepare':
            result = prepare(args.journey, args.output)
        elif args.command == 'record':
            result = record(args.journey, args.packet, args.decisions, args.output,
                            args.expected_output_sha256)
        else:
            result = verify(args.journey, args.receipt)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 1 if args.command == 'verify' and not result['resume_ready'] else 0
    except (OSError, ValueError, RuntimeError, TypeError) as exc:
        print('Error: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
