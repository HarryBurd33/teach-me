#!/usr/bin/env python3
"""Explicit, bounded local command DAGs. Python 3.9+, no shell or service."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time
import uuid

LIMIT = 16384
NODE_KEYS = {'id', 'argv', 'depends_on', 'timeout_seconds', 'max_attempts', 'human_gate'}


def safe_path(value):
    path = Path(os.path.abspath(value))
    for part in [path] + list(path.parents):
        if part.is_symlink():
            raise ValueError('Symlink path is not supported: ' + str(part))
    return path


def members(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON member: ' + key)
        result[key] = value
    return result


def number(value, maximum):
    return type(value) in (int, float) and math.isfinite(value) and 0 < value <= maximum


def read_plan(value):
    path = safe_path(value)
    if not path.is_file() or path.stat().st_size > 1048576:
        raise ValueError('Plan must be a regular file at most 1 MiB')
    with path.open('rb') as handle:
        raw = handle.read(1048577)
    if len(raw) > 1048576:
        raise ValueError('Plan exceeds 1 MiB')
    plan = json.loads(raw, object_pairs_hook=members)
    if not isinstance(plan, dict) or set(plan) != {'version', 'max_seconds', 'nodes'}:
        raise ValueError('Plan keys: version, max_seconds, nodes')
    if type(plan['version']) is not int or plan['version'] != 1:
        raise ValueError('Supported plan version is integer 1')
    if not number(plan['max_seconds'], 3600):
        raise ValueError('max_seconds must be positive and at most 3600')
    if not isinstance(plan['nodes'], list) or not 1 <= len(plan['nodes']) <= 32:
        raise ValueError('Expected 1 through 32 nodes')
    nodes = {}
    for node in plan['nodes']:
        if not isinstance(node, dict) or set(node) != NODE_KEYS:
            raise ValueError('Node keys: ' + ', '.join(sorted(NODE_KEYS)))
        ident = node['id']
        if not isinstance(ident, str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', ident):
            raise ValueError('Node id must be a lowercase hyphenated slug')
        if ident in nodes:
            raise ValueError('Duplicate node id')
        args = node['argv']
        if not isinstance(args, list) or not 1 <= len(args) <= 64 or any(
                not isinstance(x, str) or not x or '\0' in x or len(x) > 8192 for x in args):
            raise ValueError('argv must contain 1 through 64 nonempty bounded strings')
        deps = node['depends_on']
        if not isinstance(deps, list) or any(not isinstance(x, str) for x in deps) or len(set(deps)) != len(deps):
            raise ValueError('depends_on must contain distinct node IDs')
        if not number(node['timeout_seconds'], 300):
            raise ValueError('Node timeout must be positive and at most 300 seconds')
        if type(node['max_attempts']) is not int or not 1 <= node['max_attempts'] <= 5:
            raise ValueError('max_attempts must be integer 1 through 5')
        if type(node['human_gate']) is not bool:
            raise ValueError('human_gate must be boolean')
        nodes[ident] = node
    ordered, visiting, visited = [], set(), set()

    def visit(ident):
        if ident not in nodes:
            raise ValueError('Unknown dependency: ' + ident)
        if ident in visiting:
            raise ValueError('Dependency cycle')
        if ident in visited:
            return
        visiting.add(ident)
        for dep in nodes[ident]['depends_on']:
            visit(dep)
        visiting.remove(ident)
        visited.add(ident)
        ordered.append(nodes[ident])

    for ident in nodes:
        visit(ident)
    return plan, ordered, hashlib.sha256(raw).hexdigest()


class Journal:
    """Own one new result file; do not overwrite another run or changed result."""
    def __init__(self, path):
        self.path = safe_path(path)
        if not self.path.parent.is_dir():
            raise ValueError('Output parent must exist')
        self.token = uuid.uuid4().hex.encode()
        self.lock = self.path.with_name(self.path.name + '.lock')
        self.fingerprint = None

    def __enter__(self):
        fd = os.open(str(self.lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'wb') as handle:
            handle.write(self.token)
        self.inode = self.lock.stat().st_ino
        try:
            fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, 'wb') as handle:
                handle.write(b'{}\n')
            self.fingerprint = hashlib.sha256(b'{}\n').hexdigest()
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def save(self, value):
        safe_path(self.path)
        if hashlib.sha256(self.path.read_bytes()).hexdigest() != self.fingerprint:
            raise ValueError('Run output changed outside its writer; refusing overwrite')
        data = (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode('utf-8')
        fd, name = tempfile.mkstemp(prefix='.teach-me-run-', dir=str(self.path.parent))
        try:
            with os.fdopen(fd, 'wb') as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(name, self.path)
            self.fingerprint = hashlib.sha256(data).hexdigest()
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def __exit__(self, *unused):
        if self.lock.exists() and not self.lock.is_symlink() and self.lock.stat().st_ino == self.inode and self.lock.read_bytes() == self.token:
            self.lock.unlink()


def stop_child(process):
    # On POSIX, include descendants that remain in the owned process group.
    if os.name == 'posix':
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    elif process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=0.3)
    except subprocess.TimeoutExpired:
        if os.name == 'posix':
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            process.kill()
        process.wait()
    if os.name == 'posix':
        # The direct child may exit before a same-group grandchild.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def execute(args):
    plan, ordered, digest = read_plan(args.plan)
    root = safe_path(args.root)
    if not root.is_dir():
        raise ValueError('Root must be an existing directory')
    approved = set(args.approve_node)
    gated = {n['id'] for n in ordered if n['human_gate']}
    if approved - gated:
        raise ValueError('Approval must name an existing human-gated node')
    if not args.execute:
        return {'status': 'dry_run', 'plan_sha256': digest, 'nodes': ordered,
                'notice': 'No commands executed or output written. Review local commands and current authorization.'}, 0
    started = time.monotonic()
    deadline = started + plan['max_seconds']
    cancelled = []
    uncertain = []
    result = {'version': 1, 'status': 'running', 'plan_sha256': digest,
              'root': str(root), 'nodes': [], 'permissions': 'Commands inherit host permissions; this is not a sandbox.',
              'process_cleanup': 'POSIX owned process group; detached descendants and Windows child trees are not contained.'}
    prior = {}
    handlers = {}

    def interrupted(signum, frame):
        cancelled.append(signum)

    for sig in (signal.SIGINT, signal.SIGTERM):
        handlers[sig] = signal.signal(sig, interrupted)
    try:
        with Journal(args.output) as journal:
            journal.save(result)
            for node in ordered:
                record = {'id': node['id'], 'status': 'pending', 'attempts': []}
                result['nodes'].append(record)
                prior[node['id']] = record
                if uncertain:
                    record.update(status='blocked', reason='owned process cleanup uncertain')
                elif cancelled:
                    record.update(status='blocked', reason='run interrupted')
                elif time.monotonic() >= deadline:
                    record.update(status='blocked', reason='total time budget exhausted')
                elif any(prior[d]['status'] != 'passed' for d in node['depends_on']):
                    record.update(status='blocked', reason='dependency did not pass')
                elif node['human_gate'] and node['id'] not in approved:
                    record.update(status='gated', reason='explicit node approval absent')
                else:
                    for index in range(node['max_attempts']):
                        if cancelled or time.monotonic() >= deadline:
                            break
                        record['status'] = 'running'
                        attempt = {'number': index + 1, 'argv': node['argv'], 'status': 'running'}
                        record['attempts'].append(attempt)
                        journal.save(result)
                        began = time.monotonic()
                        child = None
                        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
                            try:
                                child = subprocess.Popen(node['argv'], cwd=str(root), shell=False,
                                                         stdout=stdout, stderr=stderr,
                                                         start_new_session=(os.name == 'posix'))
                                reason = None
                                until = min(deadline, began + node['timeout_seconds'])
                                while child.poll() is None:
                                    if cancelled:
                                        reason = 'interrupted'
                                    elif time.monotonic() >= until:
                                        reason = 'timeout'
                                    elif any(os.fstat(f.fileno()).st_size > LIMIT for f in (stdout, stderr)):
                                        reason = 'output_limit'
                                    if reason:
                                        break
                                    try:
                                        child.wait(timeout=min(0.03, max(0.001, until - time.monotonic())))
                                    except subprocess.TimeoutExpired:
                                        pass
                                # Also terminate any descendants left in the owned group.
                                stop_child(child)
                                overflow = any(os.fstat(f.fileno()).st_size > LIMIT for f in (stdout, stderr))
                                reason = reason or ('output_limit' if overflow else None)
                                attempt.update(exit_code=child.returncode, status=reason or ('passed' if child.returncode == 0 else 'failed'))
                            except OSError as exc:
                                if child is None:
                                    attempt.update(status='launch_failed', error=str(exc), exit_code=None)
                                else:
                                    attempt.update(status='cleanup_failed', error=str(exc), exit_code=child.poll())
                                    uncertain.append(node['id'])
                            finally:
                                if child is not None and child.poll() is None:
                                    try:
                                        stop_child(child)
                                    except OSError as exc:
                                        attempt.update(status='cleanup_failed', error=str(exc), exit_code=child.poll())
                                        uncertain.append(node['id'])
                            for name, file in [('stdout', stdout), ('stderr', stderr)]:
                                size = os.fstat(file.fileno()).st_size
                                file.seek(0)
                                attempt[name] = file.read(LIMIT).decode('utf-8', errors='replace')
                                attempt[name + '_truncated'] = size > LIMIT
                        attempt['elapsed_seconds'] = round(time.monotonic() - began, 6)
                        record['status'] = 'passed' if attempt['status'] == 'passed' else 'failed'
                        journal.save(result)
                        if record['status'] == 'passed' or attempt['status'] in ('interrupted', 'output_limit', 'launch_failed', 'cleanup_failed'):
                            break
                    if record['status'] in ('pending', 'running'):
                        record.update(status='blocked', reason='interrupted or total time budget exhausted')
                journal.save(result)
            result['elapsed_seconds'] = round(time.monotonic() - started, 6)
            result['uncertain_cleanup_nodes'] = sorted(set(uncertain))
            result['status'] = 'interrupted' if cancelled else 'passed' if all(n['status'] == 'passed' for n in result['nodes']) else 'failed'
            journal.save(result)
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
    return result, 0 if result['status'] == 'passed' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    validate = commands.add_parser('validate')
    validate.add_argument('--plan', required=True)
    run = commands.add_parser('run')
    run.add_argument('--plan', required=True)
    run.add_argument('--root', required=True)
    run.add_argument('--output', required=True)
    run.add_argument('--execute', action='store_true')
    run.add_argument('--approve-node', action='append', default=[])
    args = parser.parse_args()
    try:
        if args.command == 'validate':
            plan, nodes, digest = read_plan(args.plan)
            value, code = {'valid': True, 'nodes': len(nodes), 'plan_sha256': digest}, 0
        else:
            value, code = execute(args)
        print(json.dumps(value, ensure_ascii=False))
        return code
    except (OSError, ValueError, TypeError) as exc:
        print('harness: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
