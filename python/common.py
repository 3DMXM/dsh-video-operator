"""Shared local CLI utilities. No credentials in tool responses."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

class Failure(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code

def load(path):
    return json.loads(Path(path).expanduser().read_text(encoding='utf-8'))

def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        os.chmod(tmp, 0o600)
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)

def run(args, timeout=1800, env=None):
    p = subprocess.run([str(a) for a in args], capture_output=True, text=True,
                       timeout=timeout, env=env)
    if p.returncode:
        raise Failure('PROCESS_FAILED', f'{Path(str(args[0])).name} failed: {p.stderr[-2000:]}')
    return p.stdout

def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

@contextlib.contextmanager
def lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise Failure('BUSY', f'任务锁已存在：{path}。确认无正在运行的任务后再清理陈旧锁。')
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        path.unlink(missing_ok=True)

def cli(dispatch):
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', required=True)
    args = parser.parse_args()
    try:
        result = dispatch(load(args.request))
        print(json.dumps({'ok': True, 'data': result}, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({'ok': False, 'error': {'code': getattr(e, 'code', type(e).__name__),
                                                'message': str(e)}}, ensure_ascii=False))
        raise SystemExit(1)
