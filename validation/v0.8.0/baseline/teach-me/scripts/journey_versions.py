#!/usr/bin/env python3
"""Verified local snapshots and file-level three-way journey merge. Python 3.9+."""
import argparse
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import zipfile
import zlib

import journey
import transfer
from storage import StorageError, checked_path, file_lock

HASH = re.compile(r'[0-9a-f]{64}\Z')
META_LIMIT = 65536
MAX_REVISIONS = 64
LOCK = '.teach-me-store.lock'


def fail(message):
    raise StorageError(message)


def digest(value):
    if not isinstance(value, str) or not HASH.fullmatch(value):
        fail('Expected a lowercase SHA256 digest')
    return value


def encoded(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                       separators=(',', ':')) + '\n').encode('utf-8')


def archive(path):
    path = checked_path(path)
    before = transfer.read_regular(path, transfer.ARCHIVE_LIMIT)
    files = transfer.inspect_archive(path)
    after = transfer.read_regular(path, transfer.ARCHIVE_LIMIT)
    if before != after:
        fail('Archive changed during inspection')
    state = journey.validate(transfer.strict_json(files['progress.json']))
    if len(state['journey_id']) > 255:
        fail('Journey ID must fit one local filesystem leaf (at most 255 ASCII characters)')
    return path, transfer.sha(before), files, state['journey_id']


def write_new(path, raw):
    path = checked_path(path)
    if not path.parent.is_dir() or path.exists():
        fail('New output needs an existing parent and must not exist')
    fd, temporary = tempfile.mkstemp(prefix='.teach-me-version-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        checked_path(path)
        os.link(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_store(store):
    """Caller holds the cooperative store lock; validate every bounded revision."""
    store = checked_path(store)
    if not store.is_dir():
        fail('Store must be an existing nonsymlink directory')
    entries = list(store.iterdir())
    if len(entries) > 192:
        fail('Too many store entries; review/archive old revisions explicitly')
    revisions, staging = {}, []
    for path in entries:
        checked_path(path)
        if path.name == LOCK:
            if not stat.S_ISREG(path.stat().st_mode):
                fail('Invalid store lock')
            continue
        if path.name == 'HEAD.json':
            continue
        if path.name.startswith('.teach-me-snapshot-') and path.is_dir():
            staging.append(path.name)
            continue
        if path.name.startswith('.teach-me-head-') and path.is_file():
            transfer.read_regular(path, META_LIMIT)
            staging.append(path.name)
            continue
        if not path.is_file() or not path.name.endswith('.zip'):
            fail('Unknown store entry; preserve and reconcile: ' + path.name)
        revision = digest(path.name[:-4])
        if len(revisions) >= MAX_REVISIONS:
            fail('Store exceeds 64 immutable revisions')
        _, actual, _, ident = archive(path)
        if actual != revision:
            fail('Revision bytes do not match its filename digest')
        revisions[revision] = ident
    identities = set(revisions.values())
    if len(identities) > 1:
        fail('Store contains more than one journey identity')
    path = checked_path(store / 'HEAD.json')
    head = None
    raw_head = None
    if path.exists():
        raw_head = transfer.read_regular(path, META_LIMIT)
        head = transfer.strict_json(raw_head)
        if (not isinstance(head, dict) or set(head) != {'version', 'journey_id', 'revision', 'previous'}
                or type(head['version']) is not int or head['version'] != 1
                or not isinstance(head['journey_id'], str)
                or not journey.SLUG.fullmatch(head['journey_id'])):
            fail('Unsupported or malformed snapshot HEAD')
        current = digest(head['revision'])
        previous = head['previous']
        if previous is not None:
            digest(previous)
            if previous == current or previous not in revisions:
                fail('Invalid previous snapshot reference')
        if current not in revisions or revisions[current] != head['journey_id']:
            fail('HEAD revision missing or journey identity differs')
        identities.add(head['journey_id'])
    return head, raw_head, revisions, staging, next(iter(identities), None)


def status(store):
    store = checked_path(store)
    with file_lock(store, LOCK):
        head, _, revisions, staging, ident = read_store(store)
        return {'initialized': head is not None, 'head': head, 'journey_id': ident,
                'available_revisions': sorted(revisions), 'staging_entries': sorted(staging),
                'automatic_recovery': False}


def publish_head(store, value, old_raw):
    """Single HEAD publication, fenced for cooperating writers, not hostile FS CAS."""
    path = checked_path(store / 'HEAD.json')
    current = transfer.read_regular(path, META_LIMIT) if path.exists() else None
    if current != old_raw:
        fail('HEAD changed outside its writer; refusing activation')
    fd, temporary = tempfile.mkstemp(prefix='.teach-me-head-', dir=str(store))
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(encoded(value))
            handle.flush()
            os.fsync(handle.fileno())
        checked_path(path)
        current = transfer.read_regular(path, META_LIMIT) if path.exists() else None
        if current != old_raw:
            fail('HEAD changed before activation')
        if old_raw is None:
            os.link(temporary, str(path))
        else:
            os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def snapshot(journey_path, store, expected_head):
    source = checked_path(journey_path)
    store = checked_path(store)
    if not source.is_dir() or not store.is_dir() or store == source or source in store.parents:
        fail('Use existing journey/store directories, with the store outside the journey')
    if expected_head != 'none':
        digest(expected_head)
    with file_lock(store, LOCK):
        head, raw_head, revisions, _, identity = read_store(store)
        actual_head = head['revision'] if head else 'none'
        if actual_head != expected_head:
            fail('Stale expected HEAD; inspect and reconcile before snapshot')
        if identity is not None and identity != source.name:
            fail('Store belongs to a different journey')
        with tempfile.TemporaryDirectory(prefix='.teach-me-snapshot-', dir=str(store)) as directory:
            packed = Path(directory) / 'snapshot.zip'
            transfer.pack(source, packed)
            _, revision, _, ident = archive(packed)
            if ident != source.name:
                fail('Snapshot journey identity differs')
            if revision == actual_head:
                return {'snapshot': False, 'unchanged': True, 'revision': revision,
                        'journey_id': ident, 'previous': head['previous']}
            target = checked_path(store / (revision + '.zip'))
            if target.exists():
                if transfer.read_regular(target, transfer.ARCHIVE_LIMIT) != transfer.read_regular(packed, transfer.ARCHIVE_LIMIT):
                    fail('Existing revision differs; nothing was overwritten')
            else:
                if len(revisions) >= MAX_REVISIONS:
                    fail('Store has 64 revisions; explicitly archive before adding another')
                os.link(str(packed), str(target))
            value = {'version': 1, 'journey_id': ident, 'revision': revision,
                     'previous': head['revision'] if head else None}
            publish_head(store, value, raw_head)
        return {'snapshot': True, 'unchanged': False, 'revision': revision,
                'journey_id': ident, 'previous': value['previous']}


def restore(store, revision, root, ident):
    store, root = checked_path(store), checked_path(root)
    digest(revision)
    if root == store or store in root.parents:
        fail('Restore workspace must be outside the snapshot store')
    with file_lock(store, LOCK):
        _, _, revisions, _, identity = read_store(store)
        if revision not in revisions or identity != ident:
            fail('Unknown revision or different requested journey identity')
        result = transfer.unpack(store / (revision + '.zip'), root, ident)
    result.update(revision=revision, head_changed=False, automatic_resume=False)
    return result


def preparation(base, local, incoming):
    inputs = {name: archive(path) for name, path in [('base', base), ('local', local), ('incoming', incoming)]}
    identities = {item[3] for item in inputs.values()}
    if len(identities) != 1:
        fail('All three archives must describe the same journey')
    report = {'version': 1, 'journey_id': next(iter(identities)),
              'source_archives': {name: item[1] for name, item in inputs.items()},
              'files': {}, 'conflicts': []}
    names = sorted(set().union(*(set(item[2]) for item in inputs.values())))
    for name in names:
        b, l, i = (inputs[key][2].get(name) for key in ('base', 'local', 'incoming'))
        if l == b and i == b:
            classification, selected = 'unchanged', 'base'
        elif l == i:
            classification, selected = 'identical', 'local'
        elif l == b:
            classification, selected = 'incoming-only', 'incoming'
        elif i == b:
            classification, selected = 'local-only', 'local'
        else:
            classification, selected = 'conflict', None
            report['conflicts'].append(name)
        report['files'][name] = {'base': transfer.sha(b) if b is not None else None,
                                 'local': transfer.sha(l) if l is not None else None,
                                 'incoming': transfer.sha(i) if i is not None else None,
                                 'status': classification, 'selected': selected}
    report['report_sha256'] = transfer.sha(encoded(report))
    if len(encoded(report)) > META_LIMIT:
        fail('Comparison report exceeds metadata limit')
    return report, inputs


def unchanged_inputs(inputs):
    for path, digest_value, _, _ in inputs.values():
        if transfer.sha(transfer.read_regular(path, transfer.ARCHIVE_LIMIT)) != digest_value:
            fail('Input archive changed; repeat comparison before publishing')


def compare(base, local, incoming, output):
    report, inputs = preparation(base, local, incoming)
    unchanged_inputs(inputs)
    write_new(output, encoded(report))
    return report


def merge(base, local, incoming, output, resolutions=None):
    output = checked_path(output)
    if output.exists() or not output.parent.is_dir():
        fail('Merged archive must be a new output with an existing parent')
    report, inputs = preparation(base, local, incoming)
    choices = {}
    if resolutions is not None:
        value = transfer.strict_json(transfer.read_regular(resolutions, META_LIMIT))
        if (not isinstance(value, dict) or set(value) != {'version', 'report_sha256', 'choices'}
                or type(value['version']) is not int or value['version'] != 1
                or value['report_sha256'] != report['report_sha256']
                or not isinstance(value['choices'], dict)
                or set(value['choices']) != set(report['conflicts'])
                or any(v not in ('base', 'local', 'incoming') for v in value['choices'].values())):
            fail('Resolution choices must match every conflict and the exact current report digest')
        choices = value['choices']
    elif report['conflicts']:
        fail('Unresolved conflicts: ' + ', '.join(report['conflicts']))
    files = {}
    for name, entry in report['files'].items():
        selected = choices.get(name, entry['selected'])
        raw = inputs[selected][2].get(name)
        if raw is not None:
            files[name] = raw
    if not transfer.REQUIRED <= set(files):
        fail('Merge may not delete required journey files')
    transfer.validate_progress(files['progress.json'], report['journey_id'])
    if sum(map(len, files.values())) > transfer.TOTAL_LIMIT:
        fail('Merged journey exceeds transfer limit')
    unchanged_inputs(inputs)
    with tempfile.TemporaryDirectory(prefix='.teach-me-merge-', dir=str(output.parent)) as directory:
        target = Path(directory) / report['journey_id']
        target.mkdir()
        for name, raw in files.items():
            with (target / name).open('xb') as handle:
                handle.write(raw)
        unchanged_inputs(inputs)
        packed = transfer.pack(target, output)
    return {'merged': True, 'archive': str(output), 'sha256': packed['sha256'],
            'journey_id': report['journey_id'], 'files': len(files),
            'report_sha256': report['report_sha256'], 'resolved_conflicts': choices,
            'automatic_resume': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('snapshot')
    p.add_argument('--journey', required=True); p.add_argument('--store', required=True)
    p.add_argument('--expected-head', required=True)
    p = commands.add_parser('status'); p.add_argument('--store', required=True)
    p = commands.add_parser('restore')
    p.add_argument('--store', required=True); p.add_argument('--revision', required=True)
    p.add_argument('--root', required=True); p.add_argument('--id', required=True)
    for name in ('compare', 'merge'):
        p = commands.add_parser(name)
        p.add_argument('--base', required=True); p.add_argument('--local', required=True)
        p.add_argument('--incoming', required=True); p.add_argument('--output', required=True)
        if name == 'merge': p.add_argument('--resolutions')
    args = parser.parse_args(argv)
    try:
        if args.command == 'snapshot': result = snapshot(args.journey, args.store, args.expected_head)
        elif args.command == 'status': result = status(args.store)
        elif args.command == 'restore': result = restore(args.store, args.revision, args.root, args.id)
        elif args.command == 'compare': result = compare(args.base, args.local, args.incoming, args.output)
        else: result = merge(args.base, args.local, args.incoming, args.output, args.resolutions)
        print(json.dumps(result, ensure_ascii=False)); return 0
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, zlib.error) as exc:
        print('Error: ' + str(exc), file=sys.stderr); return 2


if __name__ == '__main__':
    sys.exit(main())
