#!/usr/bin/env python3
"""Immutable local review receipts; no truth, identity or authorization certification."""
import argparse
import base64
import binascii
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

import coherence_review as review
import journey_versions as versions
from storage import StorageError, checked_path, file_lock, journey_lock

LOCK = '.teach-me-review-history.lock'
STAGE_PREFIX = '.teach-me-history-stage-'
MAX_ENTRIES = 64
ENTRY_LIMIT = 3 * 1024 * 1024
TOTAL_LIMIT = 64 * 1024 * 1024
DIRECTORY_LIMIT = 192
RECEIPT_LIMIT = 2 * 1024 * 1024
ENTRY_KEYS = {'version', 'journey_id', 'sequence', 'previous',
              'receipt_sha256', 'receipt_base64'}
NAME = re.compile(r'([0-9]{6})-([0-9a-f]{64})\.json\Z')


def fail(message):
    raise StorageError(message)


def directory(value):
    path = checked_path(value)
    if not path.is_dir():
        fail('History store must be an existing nonsymlink directory')
    return path


def parse(raw):
    # Require UTF-8 explicitly: json.loads(bytes) also accepts UTF-16/32.
    return review.strict_json(raw.decode('utf-8'))


def receipt(raw):
    if len(raw) > RECEIPT_LIMIT:
        fail('Receipt exceeds 2 MiB')
    return review.validate_receipt(parse(raw))


def entry(value):
    review.version(value, ENTRY_KEYS, 'history entry')
    review.identity(value['journey_id'])
    if type(value['sequence']) is not int or not 1 <= value['sequence'] <= MAX_ENTRIES:
        fail('History sequence must be an exact integer from 1 through 64')
    if value['previous'] is not None:
        review.check_digest(value['previous'], 'previous')
    review.check_digest(value['receipt_sha256'], 'receipt_sha256')
    text = value['receipt_base64']
    if not isinstance(text, str):
        fail('receipt_base64 must be canonical base64 text')
    try:
        raw = base64.b64decode(text.encode('ascii'), validate=True)
    except (ValueError, UnicodeError, binascii.Error):
        fail('receipt_base64 must be canonical base64 text')
    if base64.b64encode(raw).decode('ascii') != text:
        fail('receipt_base64 is not canonical')
    if review.digest(raw) != value['receipt_sha256']:
        fail('Embedded receipt digest mismatch')
    value_receipt = receipt(raw)
    if value_receipt['journey_id'] != value['journey_id']:
        fail('Embedded receipt journey identity differs')
    return raw, value_receipt


def read_store(store):
    """Caller holds LOCK. Validate all bounded entries, without claiming freshness."""
    store = directory(store)
    paths = []
    for path in store.iterdir():
        paths.append(path)
        if len(paths) > DIRECTORY_LIMIT:
            fail('History directory exceeds 192 entries')
    records, stages, fingerprint = [], [], {}
    total = 0
    for path in sorted(paths):
        checked_path(path)
        if path.name == LOCK:
            review.read_regular(path, versions.META_LIMIT)
            continue
        raw = review.read_regular(path, ENTRY_LIMIT)
        total += len(raw)
        if total > TOTAL_LIMIT:
            fail('History exceeds 64 MiB total bytes')
        fingerprint[path.name] = review.digest(raw)
        if path.name.startswith(STAGE_PREFIX):
            stages.append(path.name)
            continue
        match = NAME.fullmatch(path.name)
        if match is None:
            fail('Unknown history entry; preserve and reconcile: ' + path.name)
        if len(records) >= MAX_ENTRIES:
            fail('History exceeds 64 entries')
        value = parse(raw)
        receipt_raw, value_receipt = entry(value)
        sha = review.digest(raw)
        if raw != versions.encoded(value) or sha != match.group(2):
            fail('History entry bytes are not canonical or filename digest differs')
        if int(match.group(1)) != value['sequence']:
            fail('History filename and sequence differ')
        records.append({'sha256': sha, 'filename': path.name, 'entry': value,
                        'receipt': receipt_raw, 'resume_ready': value_receipt['resume_ready']})
    previous, ident = None, None
    for sequence, record in enumerate(records, 1):
        value = record['entry']
        if value['sequence'] != sequence or value['previous'] != previous:
            fail('History sequence or previous hash chain is broken')
        if ident is not None and value['journey_id'] != ident:
            fail('History contains more than one journey identity')
        ident = value['journey_id']
        previous = record['sha256']
    return records, stages, fingerprint, total, len(paths)


def report(records, stages):
    return {'tip': records[-1]['sha256'] if records else None,
            'sequence': len(records),
            'journey_id': records[0]['entry']['journey_id'] if records else None,
            'entries': [{'sha256': r['sha256'], 'filename': r['filename'],
                         'sequence': r['entry']['sequence'],
                         'receipt_sha256': r['entry']['receipt_sha256'],
                         'resume_ready': r['resume_ready']} for r in records],
            'staging_entries': stages, 'receipt_freshness_checked': False,
            'semantic_correctness_verified': False, 'automatic_recovery': False}


def status(store):
    store = directory(store)
    with file_lock(store, LOCK):
        records, stages, _, _, _ = read_store(store)
        return report(records, stages)


def stage(parent, raw):
    fd, name = tempfile.mkstemp(prefix=STAGE_PREFIX, dir=str(parent))
    path = Path(name)
    identity = os.fstat(fd)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        remove_owned(path, identity)
        raise
    return path, identity


def remove_owned(path, identity):
    try:
        current = path.lstat()
        if (stat.S_ISREG(current.st_mode) and
                (current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino)):
            path.unlink()
    except FileNotFoundError:
        pass


def append(store, journey_path, receipt_path, expected_tip):
    store, source = directory(store), review.selected_journey(journey_path)
    receipt_path = checked_path(receipt_path)
    if store == source or source in store.parents:
        fail('History store must be outside the journey')
    if expected_tip != 'none':
        review.check_digest(expected_tip, 'expected-tip')
    with file_lock(store, LOCK):
        records, stages, fingerprint, total, count = read_store(store)
        if stages:
            fail('History has staging entries; preserve and reconcile before appending')
        actual_tip = records[-1]['sha256'] if records else 'none'
        if expected_tip != actual_tip:
            fail('Stale expected tip; inspect history before appending')
        if len(records) >= MAX_ENTRIES:
            fail('History has 64 entries; use a new history store explicitly')
        # Reserve a directory slot for staging and another for publication.
        if count + 2 > DIRECTORY_LIMIT:
            fail('History directory lacks room for staging and publication')
        with journey_lock(source):
            raw_receipt = review.read_regular(receipt_path, RECEIPT_LIMIT)
            value_receipt = receipt(raw_receipt)
            files, state = review.read_content(source)
            current = review.packet_for(source, files, state)
            if (value_receipt['journey_id'] != state['journey_id'] or
                    value_receipt['files'] != current['files'] or
                    value_receipt['packet_sha256'] != current['packet_sha256']):
                fail('Receipt is stale or belongs to another journey')
            if records and records[0]['entry']['journey_id'] != state['journey_id']:
                fail('History belongs to another journey')
            value = {'version': 1, 'journey_id': state['journey_id'],
                     'sequence': len(records) + 1,
                     'previous': None if not records else actual_tip,
                     'receipt_sha256': review.digest(raw_receipt),
                     'receipt_base64': base64.b64encode(raw_receipt).decode('ascii')}
            raw = versions.encoded(value)
            if len(raw) > ENTRY_LIMIT or total + len(raw) > TOTAL_LIMIT:
                fail('History entry or total byte limit would be exceeded')
            sha = review.digest(raw)
            output = checked_path(store / ('%06d-%s.json' % (value['sequence'], sha)))
            temporary, identity = stage(store, raw)
            try:
                review.unchanged(source, files)
                if review.read_regular(receipt_path, RECEIPT_LIMIT) != raw_receipt:
                    fail('Receipt bytes changed while appending')
                _, now_stages, now_fingerprint, _, _ = read_store(store)
                expected = dict(fingerprint)
                expected[temporary.name] = sha
                if now_stages != [temporary.name] or now_fingerprint != expected:
                    fail('History or staging bytes changed before publication')
                checked_path(output)
                os.link(str(temporary), str(output))
            finally:
                remove_owned(temporary, identity)
    return {'appended': True, 'entry': sha, 'sequence': value['sequence'],
            'journey_id': value['journey_id'], 'receipt_sha256': value['receipt_sha256'],
            'resume_ready': value_receipt['resume_ready'],
            'semantic_correctness_verified': False}


def extract(store, entry_sha, output):
    store, output = directory(store), checked_path(output)
    review.check_digest(entry_sha, 'entry')
    if output.parent == store or store in output.parents:
        fail('Extract output must be outside the history store')
    if not output.parent.is_dir() or output.exists():
        fail('Extract output must be new with an existing parent')
    with file_lock(store, LOCK):
        records, _, fingerprint, _, _ = read_store(store)
        selected = next((r for r in records if r['sha256'] == entry_sha), None)
        if selected is None:
            fail('Unknown history entry digest')
        temporary, identity = stage(output.parent, selected['receipt'])
        try:
            if read_store(store)[2] != fingerprint:
                fail('History bytes changed before extraction')
            if review.read_regular(temporary, RECEIPT_LIMIT) != selected['receipt']:
                fail('Extract staging bytes changed before publication')
            checked_path(output)
            os.link(str(temporary), str(output))
        finally:
            remove_owned(temporary, identity)
    return {'extracted': True, 'entry': entry_sha, 'output': str(output),
            'receipt_sha256': selected['entry']['receipt_sha256']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('append')
    p.add_argument('--store', required=True); p.add_argument('--journey', required=True)
    p.add_argument('--receipt', required=True); p.add_argument('--expected-tip', required=True)
    p = commands.add_parser('status'); p.add_argument('--store', required=True)
    p = commands.add_parser('extract')
    p.add_argument('--store', required=True); p.add_argument('--entry', required=True)
    p.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'append':
            result = append(args.store, args.journey, args.receipt, args.expected_tip)
        elif args.command == 'status':
            result = status(args.store)
        else:
            result = extract(args.store, args.entry, args.output)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except (OSError, ValueError, RuntimeError, TypeError) as exc:
        print('Error: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
