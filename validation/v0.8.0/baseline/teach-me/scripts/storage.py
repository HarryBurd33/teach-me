"""Cooperative local locks and path checks; no lock expiry or hostile-FS sandbox."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import stat
import uuid


class StorageError(ValueError):
    pass


def checked_path(path):
    """Return an absolute path, rejecting existing symlinks in every component."""
    path = Path(os.path.abspath(path))
    for item in (path,) + tuple(path.parents):
        if item.is_symlink():
            raise StorageError('Refusing symlink: ' + str(item))
    return path


@contextmanager
def file_lock(directory, name):
    directory = checked_path(directory)
    if not directory.is_dir() or '/' in name or '\\' in name:
        raise StorageError('Lock needs an existing nonsymlink directory and a leaf name')
    path = checked_path(directory / name)
    token = (json.dumps({'token': uuid.uuid4().hex, 'pid': os.getpid()}) + '\n').encode()
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, 'O_NOFOLLOW', 0)
    try:
        fd = os.open(str(path), flags, 0o600)
    except FileExistsError:
        raise StorageError('Writer lock exists; reconcile its owner before retrying: ' + str(path))
    identity = os.fstat(fd)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(token)
            handle.flush()
            os.fsync(handle.fileno())
        yield directory
    finally:
        # Never remove a replacement lock, even if it names this PID. A process
        # can be reused; the random bytes and file identity are both required.
        try:
            current = path.lstat()
            same = (stat.S_ISREG(current.st_mode) and
                    (current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino))
            if same:
                read_fd = os.open(str(path), os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
                with os.fdopen(read_fd, 'rb') as handle:
                    actual = os.fstat(handle.fileno())
                    same = ((actual.st_dev, actual.st_ino) ==
                            (identity.st_dev, identity.st_ino) and handle.read(1024) == token)
                if same:
                    path.unlink()
        except FileNotFoundError:
            pass


def journey_lock(journey):
    return file_lock(journey, '.teach-me.lock')


def destination_lock(learning, journey_id):
    return file_lock(learning, '.teach-me-destination-' + journey_id + '.lock')
