#!/usr/bin/env python3
"""Explicit recoverable snapshot retirement. Python 3.9+ standard library."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import zipfile
import zlib

import journey_versions as versions
import transfer
from storage import StorageError, checked_path, file_lock

ARCHIVE_LOCK = '.teach-me-snapshot-maintenance.lock'
STAGE_PREFIX = '.teach-me-retirement-stage-'
SELECTED_LIMIT = 64 * 1024 * 1024
PLAN_KEYS = {'version', 'journey_id', 'store_sha256', 'head', 'protected',
             'revisions', 'plan_sha256'}
RECOVERY = ('Inspect the archive and actual store, then create a fresh plan; '
            'do not automatically replay this plan.')


def fail(message):
    raise StorageError(message)


def disjoint(a, b):
    if a == b or a in b.parents or b in a.parents:
        fail('Paths must be disjoint in both ancestry directions')


def selection(values):
    if not isinstance(values, list) or not values or len(values) > versions.MAX_REVISIONS:
        fail('Select between 1 and 64 explicit revision hashes')
    for value in values:
        versions.digest(value)
    if len(set(values)) != len(values):
        fail('Duplicate selected revision')
    return sorted(values)


def current_plan(store, selected):
    """Caller holds store lock. Fingerprint exact HEAD bytes and every ZIP."""
    selected = selection(selected)
    head, raw_head, revisions, staging, ident = versions.read_store(store)
    if head is None:
        fail('Maintenance requires an initialized valid snapshot store')
    if staging:
        fail('Store has orphan staging entries; inspect and reconcile first')
    protected = sorted({head['revision']} | ({head['previous']} if head['previous'] else set()))
    if any(value not in revisions for value in selected):
        fail('Unknown selected revision')
    if set(selected).intersection(protected):
        fail('HEAD and previous revisions are protected')
    hashes = {'HEAD.json': transfer.sha(raw_head)}
    total = 0
    for revision in sorted(revisions):
        raw = transfer.read_regular(store / (revision + '.zip'), transfer.ARCHIVE_LIMIT)
        actual = transfer.sha(raw)
        if actual != revision:
            fail('Revision changed while planning')
        hashes[revision + '.zip'] = actual
        if revision in selected:
            total += len(raw)
    if total > SELECTED_LIMIT:
        fail('Selected ZIP bytes exceed 64 MiB')
    # Preserve raw HEAD formatting through its hash as well as parsed references.
    if transfer.read_regular(store / 'HEAD.json', versions.META_LIMIT) != raw_head:
        fail('HEAD changed while planning')
    result = {'version': 1, 'journey_id': ident,
              'store_sha256': transfer.sha(versions.encoded(hashes)), 'head': head,
              'protected': protected, 'revisions': selected}
    result['plan_sha256'] = transfer.sha(versions.encoded(result))
    return result, raw_head


def validate_plan(value):
    if (not isinstance(value, dict) or set(value) != PLAN_KEYS or
            type(value['version']) is not int or value['version'] != 1):
        fail('Unsupported or malformed maintenance plan')
    for name in ('store_sha256', 'plan_sha256'):
        versions.digest(value[name])
    if selection(value['revisions']) != value['revisions']:
        fail('Plan revisions must be sorted')
    head = value['head']
    if (not isinstance(head, dict) or set(head) != {'version', 'journey_id', 'revision', 'previous'}
            or type(head['version']) is not int or head['version'] != 1
            or not isinstance(value['journey_id'], str)
            or not versions.journey.SLUG.fullmatch(value['journey_id'])
            or head['journey_id'] != value['journey_id']):
        fail('Malformed plan HEAD or journey identity')
    versions.digest(head['revision'])
    if head['previous'] is not None:
        versions.digest(head['previous'])
        if head['previous'] == head['revision']:
            fail('Malformed previous reference')
    protected = sorted({head['revision']} | ({head['previous']} if head['previous'] else set()))
    if value['protected'] != protected:
        fail('Malformed protected revision list')
    if set(value['revisions']).intersection(protected):
        fail('Plan selects protected revisions')
    unsigned = {key: item for key, item in value.items() if key != 'plan_sha256'}
    if transfer.sha(versions.encoded(unsigned)) != value['plan_sha256']:
        fail('Plan SHA256 does not match its contents')
    return value


def plan(store, revisions, output):
    store, output = checked_path(store), checked_path(output)
    if output == store or store in output.parents:
        fail('Plan output must be outside the snapshot store')
    with file_lock(store, versions.LOCK):
        value, _ = current_plan(store, revisions)
        versions.write_new(output, versions.encoded(value))
    return value


def copy_revision(source, destination):
    """Separate copy boundary for failure injection; no source hard links."""
    raw = transfer.read_regular(source, transfer.ARCHIVE_LIMIT)
    versions.write_new(destination, raw)


def verify_backup(directory, manifest):
    directory = checked_path(directory)
    expected = set(manifest['files']) | {'archive-manifest.json'}
    if {item.name for item in directory.iterdir()} != expected:
        fail('Archive directory has unexpected or missing entries')
    actual_manifest = transfer.read_regular(directory / 'archive-manifest.json', versions.META_LIMIT)
    if actual_manifest != versions.encoded(manifest):
        fail('Archive manifest bytes differ')
    for name, metadata in manifest['files'].items():
        raw = transfer.read_regular(directory / name, transfer.ARCHIVE_LIMIT)
        if len(raw) != metadata['size'] or transfer.sha(raw) != metadata['sha256']:
            fail('Archived revision verification failed: ' + name)
        # Validate the complete transfer archive, not just its byte digest.
        versions.archive(directory / name)


def publish_backup(stage, target, manifest):
    """Reserve a new directory, publish files create-new, manifest last.

    This avoids rename-over-empty-foreign-directory semantics. An interrupted
    publication may leave an incomplete destination; sources are untouched.
    """
    target = checked_path(target)
    target.mkdir()  # Exclusive reservation: never reuse/replace another directory.
    identity = target.stat()
    for name in sorted(manifest['files']) + ['archive-manifest.json']:
        checked_path(target)
        actual = target.stat()
        if (actual.st_dev, actual.st_ino) != (identity.st_dev, identity.st_ino):
            fail('Archive destination changed during publication')
        os.link(str(checked_path(stage / name)), str(checked_path(target / name)))
    verify_backup(target, manifest)


def remove_revision(path):
    """Separate removal boundary for failure injection."""
    checked_path(path).unlink()


def apply(store, plan_path, archive_root, expected_plan_sha256, approve=False):
    if not approve:
        fail('Applying a reviewed retirement plan requires --approve')
    versions.digest(expected_plan_sha256)
    store, plan_path, archive_root = map(checked_path, (store, plan_path, archive_root))
    disjoint(store, archive_root)
    if not archive_root.is_dir():
        fail('Archive root must be an existing nonsymlink directory')
    if plan_path == store or store in plan_path.parents:
        fail('Plan must be outside the snapshot store')
    value = validate_plan(transfer.strict_json(transfer.read_regular(plan_path, versions.META_LIMIT)))
    if value['plan_sha256'] != expected_plan_sha256:
        fail('Expected plan SHA256 does not match the reviewed plan')
    target = checked_path(archive_root / expected_plan_sha256)
    with file_lock(store, versions.LOCK):
        with file_lock(archive_root, ARCHIVE_LOCK):
            current, raw_head = current_plan(store, value['revisions'])
            if current != value:
                fail('Store changed; create and review a fresh maintenance plan')
            if target.exists():
                fail('Archive destination exists; nothing was overwritten. ' + RECOVERY)
            if any(item.name.startswith(STAGE_PREFIX) for item in archive_root.iterdir()):
                fail('Archive root has orphan staging; inspect and reconcile first. ' + RECOVERY)
            stage = Path(tempfile.mkdtemp(prefix=STAGE_PREFIX, dir=str(archive_root)))
            manifest = {'version': 1, 'plan': value, 'files': {}}
            try:
                for revision in value['revisions']:
                    name = revision + '.zip'
                    copy_revision(store / name, stage / name)
                    raw = transfer.read_regular(stage / name, transfer.ARCHIVE_LIMIT)
                    if transfer.sha(raw) != revision:
                        fail('Copied archive differs from selected revision')
                    manifest['files'][name] = {'sha256': revision, 'size': len(raw)}
                versions.write_new(stage / 'archive-manifest.json', versions.encoded(manifest))
                verify_backup(stage, manifest)
                # Revalidate all store bytes before publication and first unlink.
                if current_plan(store, value['revisions'])[0] != value:
                    fail('Store changed while preparing archive')
                publish_backup(stage, target, manifest)
                for revision in value['revisions']:
                    if transfer.read_regular(store / 'HEAD.json', versions.META_LIMIT) != raw_head:
                        fail('HEAD changed outside its writer; stopping removal')
                    path = checked_path(store / (revision + '.zip'))
                    if transfer.sha(transfer.read_regular(path, transfer.ARCHIVE_LIMIT)) != revision:
                        fail('Selected source revision changed before removal')
                    remove_revision(path)
                # Only success cleans its own staging copies; cleanup failures
                # also preserve the published backup and require inspection.
                shutil.rmtree(stage)
            except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, zlib.error) as exc:
                fail('Retirement stopped: ' + str(exc) + '. ' + RECOVERY)
            return {'retired': value['revisions'], 'archive': str(target),
                    'plan_sha256': expected_plan_sha256, 'head_changed': False,
                    'automatic_replay': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('plan')
    p.add_argument('--store', required=True)
    p.add_argument('--revisions', nargs='+', required=True)
    p.add_argument('--output', required=True)
    p = commands.add_parser('apply')
    p.add_argument('--store', required=True)
    p.add_argument('--plan', required=True)
    p.add_argument('--archive-root', required=True)
    p.add_argument('--expected-plan-sha256', required=True)
    p.add_argument('--approve', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'plan':
            result = plan(args.store, args.revisions, args.output)
        else:
            result = apply(args.store, args.plan, args.archive_root,
                           args.expected_plan_sha256, args.approve)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False, sort_keys=True))
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, zlib.error) as exc:
        print('Error: ' + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
