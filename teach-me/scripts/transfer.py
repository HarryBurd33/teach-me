#!/usr/bin/env python3
"""Hash-verified manual journey transfer. Python 3.9+, standard library only."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import zipfile
import zlib

import journey
import journey_assets as assets
from storage import StorageError, checked_path, destination_lock, journey_lock

REQUIRED = assets.REQUIRED
# Preserve the legacy exported constants for callers that produce Markdown
# records. Current complete asset selection is journey_assets.ALLOWED.
ALLOWED = assets.LEGACY_ALLOWED
OPTIONAL = ALLOWED - REQUIRED
TYPED_ALLOWED = assets.TYPED_ALLOWED
ASSET_ALLOWED = assets.ALLOWED
FILE_LIMIT = assets.FILE_LIMIT
TOTAL_LIMIT = assets.TOTAL_LIMIT
MANIFEST_LIMIT = 65536
ARCHIVE_LIMIT = TOTAL_LIMIT + 1024 * 1024


def fail(message):
    raise StorageError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read_regular(path, limit):
    path = checked_path(path)
    if not stat.S_ISREG(path.stat().st_mode):
        fail('Not a regular file: ' + path.name)
    fd = os.open(str(path), os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as handle:
        before = os.fstat(handle.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            fail('Not a bounded regular file: ' + path.name)
        raw = handle.read(limit + 1)
        after = os.fstat(handle.fileno())
    if len(raw) > limit or (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
        fail('File changed while reading: ' + path.name)
    return raw


def strict_json(raw):
    return json.loads(raw, object_pairs_hook=journey.unique_members,
                      parse_constant=journey.reject_constant)


def validate_progress(raw, journey_id):
    state = journey.validate(strict_json(raw))
    if state['journey_id'] != journey_id:
        fail('Archive journey_id must match the source folder / requested --id')


def pack(journey_path, output):
    source = checked_path(journey_path)
    output = checked_path(output)
    if not source.is_dir() or not output.parent.is_dir():
        fail('Journey and output parent must be existing directories')
    if output == source or source in output.parents:
        fail('Archive output must be outside the source journey')
    if output.exists():
        fail('Output exists; nothing was overwritten')
    with journey_lock(source):
        files = {}
        for name in sorted(ASSET_ALLOWED):
            path = source / name
            # Check symlinks even for otherwise optional or dangling paths.
            checked_path(path)
            if path.exists():
                files[name] = read_regular(path, FILE_LIMIT)
            elif name in REQUIRED:
                fail('Missing required journey file: ' + name)
        if sum(map(len, files.values())) > TOTAL_LIMIT:
            fail('Journey exceeds transfer size limit')
        validate_progress(files['progress.json'], source.name)
        asset_warnings = assets.validate_assets(files)
        # Cooperative writers hold the same lock. This second pass detects
        # ordinary uncoordinated changes, but is not an adversarial snapshot.
        for name, raw in files.items():
            if read_regular(source / name, FILE_LIMIT) != raw:
                fail('Journey changed while packing: ' + name)
        manifest = {'version': 2 if set(files) & TYPED_ALLOWED else 1,
                    'files': {name: {'sha256': sha(raw), 'size': len(raw)}
                                          for name, raw in files.items()}}
        fd, temp = tempfile.mkstemp(prefix='.teach-me-pack-', dir=str(output.parent))
        try:
            with os.fdopen(fd, 'w+b') as handle:
                with zipfile.ZipFile(handle, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                    payload = dict(files)
                    payload['manifest.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
                    for name, raw in sorted(payload.items()):
                        info = zipfile.ZipInfo(name)
                        info.compress_type = zipfile.ZIP_DEFLATED
                        info.create_system = 3
                        info.external_attr = 0o100600 << 16
                        archive.writestr(info, raw)
                handle.flush()
                os.fsync(handle.fileno())
            checked_path(output)
            # Atomic create-if-absent; os.rename could replace an existing file.
            os.link(temp, str(output))
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
    return {'packed': True, 'archive': str(output), 'files': len(files),
            'sha256': sha(read_regular(output, ARCHIVE_LIMIT)), 'warnings': asset_warnings}


def inspect_archive(path):
    raw = read_regular(path, ARCHIVE_LIMIT)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        names = [i.filename for i in infos]
        if len(names) != len(set(names)):
            fail('Duplicate ZIP member')
        if set(names) - (ASSET_ALLOWED | {'manifest.json'}):
            fail('Unknown or unsafe ZIP member')
        if not (REQUIRED | {'manifest.json'}) <= set(names):
            fail('Archive is missing required files')
        total = 0
        for info in infos:
            mode = info.external_attr >> 16
            kind = stat.S_IFMT(mode)
            if (info.filename != info.orig_filename or info.is_dir() or
                    '\\' in info.filename or '/' in info.filename or
                    info.flag_bits & 1 or kind not in (0, stat.S_IFREG) or
                    info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                fail('Unsafe ZIP entry metadata')
            limit = MANIFEST_LIMIT if info.filename == 'manifest.json' else FILE_LIMIT
            if info.file_size < 0 or info.file_size > limit:
                fail('ZIP member exceeds size limit')
            total += info.file_size
        if total > TOTAL_LIMIT + MANIFEST_LIMIT:
            fail('Archive exceeds uncompressed size limit')
        manifest = strict_json(archive.read('manifest.json'))
        if (not isinstance(manifest, dict) or set(manifest) != {'version', 'files'} or
                type(manifest['version']) is not int or manifest['version'] not in (1, 2) or
                not isinstance(manifest['files'], dict)):
            fail('Unsupported or malformed transfer manifest')
        entries = manifest['files']
        if manifest['version'] == 1 and set(names) & TYPED_ALLOWED:
            fail('Transfer version 1 may not contain typed journey assets')
        if set(entries) != set(names) - {'manifest.json'}:
            fail('Manifest and ZIP members differ')
        files = {}
        for name, record in entries.items():
            if (not isinstance(record, dict) or set(record) != {'sha256', 'size'} or
                    type(record['size']) is not int or not 0 <= record['size'] <= FILE_LIMIT or
                    not isinstance(record['sha256'], str) or len(record['sha256']) != 64):
                fail('Malformed manifest file record')
            content = archive.read(name)
            if len(content) != record['size'] or sha(content) != record['sha256']:
                fail('Archive hash or size mismatch: ' + name)
            files[name] = content
    assets.validate_assets(files)
    return files


def unpack(archive_path, root, journey_id):
    if not journey.SLUG.fullmatch(journey_id):
        fail('--id must be a lowercase hyphenated slug')
    root = checked_path(root)
    if not root.is_dir():
        fail('--root must be an existing approved directory')
    files = inspect_archive(archive_path)
    validate_progress(files['progress.json'], journey_id)
    learning = checked_path(root / 'learning')
    target = checked_path(learning / journey_id)
    if target.exists():
        fail('Journey destination exists; nothing was overwritten')
    learning.mkdir(exist_ok=True)
    with destination_lock(learning, journey_id):
        checked_path(target)
        if target.exists():
            fail('Journey destination appeared; nothing was overwritten')
        temp = Path(tempfile.mkdtemp(prefix='.teach-me-import-', dir=str(learning)))
        try:
            for name, raw in files.items():
                with (temp / name).open('xb') as handle:
                    handle.write(raw)
                    handle.flush()
                    os.fsync(handle.fileno())
            checked_path(target)
            if target.exists():
                fail('Journey destination appeared; nothing was overwritten')
            os.rename(str(temp), str(target))
        finally:
            if temp.exists():
                shutil.rmtree(temp)
    return {'unpacked': True, 'journey': str(target), 'files': len(files),
            'automatic_resume': False, 'warnings': assets.validate_assets(files)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('pack')
    p.add_argument('--journey', required=True)
    p.add_argument('--output', required=True)
    p = commands.add_parser('unpack')
    p.add_argument('--archive', required=True)
    p.add_argument('--root', required=True)
    p.add_argument('--id', required=True)
    args = parser.parse_args(argv)
    try:
        result = (pack(args.journey, args.output) if args.command == 'pack' else
                  unpack(args.archive, args.root, args.id))
        print(json.dumps(result))
        return 0
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, zlib.error) as exc:
        print('Error: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
