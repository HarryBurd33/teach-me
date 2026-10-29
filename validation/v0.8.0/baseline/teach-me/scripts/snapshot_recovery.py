#!/usr/bin/env python3
"""Review and finish an interrupted snapshot removal. Python 3.9+ stdlib."""
import argparse
import json
import sys
import zipfile
import zlib

import journey_versions as versions
import snapshot_maintenance as maintenance
import transfer
from storage import StorageError, checked_path, file_lock

PLAN_KEYS = {'version', 'journey_id', 'original_plan_sha256', 'store_sha256',
             'archive_sha256', 'head', 'protected', 'remaining',
             'already_absent', 'plan_sha256'}
RECOVERY = ('Inspect the archive and actual store, then create and review a fresh '
            'recovery plan; never automatically replay an interrupted plan.')


def fail(message):
    raise StorageError(message)


def outside(path, directory):
    if path == directory or directory in path.parents:
        fail('Recovery plan must be outside the store and complete archive')


def verified_archive(directory):
    """Validate the complete original backup, including every inner identity."""
    directory = checked_path(directory)
    if not directory.is_dir():
        fail('Recovery requires an existing complete archive directory')
    raw_manifest = transfer.read_regular(directory / 'archive-manifest.json', versions.META_LIMIT)
    manifest = transfer.strict_json(raw_manifest)
    if (not isinstance(manifest, dict) or set(manifest) != {'version', 'plan', 'files'}
            or type(manifest['version']) is not int or manifest['version'] != 1):
        fail('Malformed archive manifest')
    original = maintenance.validate_plan(manifest['plan'])
    if directory.name != original['plan_sha256']:
        fail('Archive directory leaf must match the original plan SHA256')
    if raw_manifest != versions.encoded(manifest):
        fail('Archive manifest must use canonical bytes')
    files = manifest['files']
    expected = {revision + '.zip' for revision in original['revisions']}
    if not isinstance(files, dict) or set(files) != expected:
        fail('Archive files must exactly match the original selected revisions')
    if {entry.name for entry in directory.iterdir()} != expected | {'archive-manifest.json'}:
        fail('Complete archive has unexpected or missing entries')
    hashes = {'archive-manifest.json': transfer.sha(raw_manifest)}
    total = 0
    for name in sorted(files):
        metadata = files[name]
        if (not isinstance(metadata, dict) or set(metadata) != {'sha256', 'size'}
                or metadata['sha256'] != name[:-4]
                or type(metadata['size']) is not int
                or not 0 < metadata['size'] <= transfer.ARCHIVE_LIMIT):
            fail('Malformed archive file metadata: ' + name)
        versions.digest(metadata['sha256'])
        total += metadata['size']
        if total > maintenance.SELECTED_LIMIT:
            fail('Selected archive ZIP bytes exceed 64 MiB')
        path = checked_path(directory / name)
        raw = transfer.read_regular(path, transfer.ARCHIVE_LIMIT)
        if len(raw) != metadata['size'] or transfer.sha(raw) != metadata['sha256']:
            fail('Archived revision verification failed: ' + name)
        _, actual, _, ident = versions.archive(path)
        if actual != metadata['sha256'] or ident != original['journey_id']:
            fail('Archive revision hash or inner journey identity differs')
        hashes[name] = actual
    if transfer.read_regular(directory / 'archive-manifest.json', versions.META_LIMIT) != raw_manifest:
        fail('Archive manifest changed during verification')
    return original, transfer.sha(versions.encoded(hashes))


def current_plan(store, archive):
    """Caller holds store then archive-parent lock; bind all current raw bytes."""
    store, archive = checked_path(store), checked_path(archive)
    maintenance.disjoint(store, archive)
    original, archive_hash = verified_archive(archive)
    head, raw_head, revisions, staging, ident = versions.read_store(store)
    if head is None:
        fail('Recovery requires an initialized valid snapshot store')
    if staging:
        fail('Store has orphan staging entries; inspect and reconcile first')
    if ident != original['journey_id']:
        fail('Store and original archive journey identities differ')
    protected = sorted({head['revision']} | ({head['previous']} if head['previous'] else set()))
    remaining = sorted(set(original['revisions']).intersection(revisions))
    if set(remaining).intersection(protected):
        fail('Current HEAD and previous revisions are protected')
    hashes = {'HEAD.json': transfer.sha(raw_head)}
    protected_bytes = {'HEAD.json': raw_head}
    for revision in sorted(revisions):
        name = revision + '.zip'
        raw = transfer.read_regular(store / name, transfer.ARCHIVE_LIMIT)
        if transfer.sha(raw) != revision:
            fail('Revision changed while planning recovery')
        hashes[name] = revision
        if revision in protected:
            protected_bytes[name] = raw
    verify_protected(store, protected_bytes)
    value = {'version': 1, 'journey_id': ident,
             'original_plan_sha256': original['plan_sha256'],
             'store_sha256': transfer.sha(versions.encoded(hashes)),
             'archive_sha256': archive_hash, 'head': head, 'protected': protected,
             'remaining': remaining,
             'already_absent': sorted(set(original['revisions']) - set(remaining))}
    value['plan_sha256'] = transfer.sha(versions.encoded(value))
    return value, protected_bytes


def verify_protected(store, protected_bytes):
    for name, raw in protected_bytes.items():
        limit = versions.META_LIMIT if name == 'HEAD.json' else transfer.ARCHIVE_LIMIT
        if transfer.read_regular(store / name, limit) != raw:
            fail('Current HEAD or protected revision bytes changed; stopping removal')


def validate_plan(value):
    if (not isinstance(value, dict) or set(value) != PLAN_KEYS
            or type(value['version']) is not int or value['version'] != 1):
        fail('Unsupported or malformed recovery plan')
    for key in ('original_plan_sha256', 'store_sha256', 'archive_sha256', 'plan_sha256'):
        versions.digest(value[key])
    for key in ('remaining', 'already_absent'):
        entries = value[key]
        if not isinstance(entries, list) or len(entries) > versions.MAX_REVISIONS:
            fail('Malformed recovery revision list')
        for revision in entries:
            versions.digest(revision)
        if entries != sorted(set(entries)):
            fail('Recovery revision lists must be sorted and unique')
    if set(value['remaining']).intersection(value['already_absent']):
        fail('Recovery revision lists overlap')
    # Reuse the maintenance HEAD, identity, selection and protection validators.
    projected = {key: value[key] for key in ('version', 'journey_id', 'store_sha256', 'head', 'protected')}
    projected['revisions'] = sorted(value['remaining'] + value['already_absent'])
    projected['plan_sha256'] = transfer.sha(versions.encoded(projected))
    maintenance.validate_plan(projected)
    unsigned = {key: item for key, item in value.items() if key != 'plan_sha256'}
    if transfer.sha(versions.encoded(unsigned)) != value['plan_sha256']:
        fail('Recovery plan SHA256 does not match its contents')
    return value


def plan(store, archive, output):
    store, archive, output = map(checked_path, (store, archive, output))
    maintenance.disjoint(store, archive)
    outside(output, store)
    outside(output, archive)
    with file_lock(store, versions.LOCK):
        with file_lock(archive.parent, maintenance.ARCHIVE_LOCK):
            value, _ = current_plan(store, archive)
            versions.write_new(output, versions.encoded(value))
    return value


def remove_revision(path):
    """Separate removal boundary for deterministic fault injection."""
    checked_path(path).unlink()


def apply(store, archive, plan_path, expected_plan_sha256, approve=False):
    if not approve:
        fail('Applying a reviewed recovery plan requires --approve')
    versions.digest(expected_plan_sha256)
    store, archive, plan_path = map(checked_path, (store, archive, plan_path))
    maintenance.disjoint(store, archive)
    outside(plan_path, store)
    outside(plan_path, archive)
    raw = transfer.read_regular(plan_path, versions.META_LIMIT)
    value = validate_plan(transfer.strict_json(raw))
    if raw != versions.encoded(value):
        fail('Recovery plan must use canonical bytes')
    if value['plan_sha256'] != expected_plan_sha256:
        fail('Expected plan SHA256 does not match the reviewed recovery plan')
    with file_lock(store, versions.LOCK):
        with file_lock(archive.parent, maintenance.ARCHIVE_LOCK):
            current, protected_bytes = current_plan(store, archive)
            if current != value:
                fail('Store or archive changed; create and review a fresh recovery plan')
            try:
                for revision in value['remaining']:
                    original, archive_hash = verified_archive(archive)
                    if (archive_hash != value['archive_sha256']
                            or original['plan_sha256'] != value['original_plan_sha256']):
                        fail('Complete archive changed; stopping removal')
                    verify_protected(store, protected_bytes)
                    path = checked_path(store / (revision + '.zip'))
                    if transfer.sha(transfer.read_regular(path, transfer.ARCHIVE_LIMIT)) != revision:
                        fail('Selected source revision changed before removal')
                    remove_revision(path)
                # Also fence a no-op and the state after the last removal.
                if verified_archive(archive)[1] != value['archive_sha256']:
                    fail('Complete archive changed')
                verify_protected(store, protected_bytes)
            except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, zlib.error) as exc:
                fail('Recovery stopped: ' + str(exc) + '. ' + RECOVERY)
    return {'retired': value['remaining'], 'already_absent': value['already_absent'],
            'archive': str(archive), 'plan_sha256': expected_plan_sha256,
            'original_plan_sha256': value['original_plan_sha256'],
            'head_changed': False, 'automatic_replay': False,
            'noop': not value['remaining']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('plan', 'apply'):
        command = commands.add_parser(name)
        command.add_argument('--store', required=True)
        command.add_argument('--archive', required=True)
        if name == 'plan':
            command.add_argument('--output', required=True)
        else:
            command.add_argument('--plan', required=True)
            command.add_argument('--expected-plan-sha256', required=True)
            command.add_argument('--approve', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.command == 'plan':
            result = plan(args.store, args.archive, args.output)
        else:
            result = apply(args.store, args.archive, args.plan, args.expected_plan_sha256, args.approve)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False, sort_keys=True))
        return 0
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, zlib.error) as exc:
        print('Error: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
