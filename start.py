"""Portable Windows launcher: py start.py [viewer|record|all|setup]."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent


def prepare() -> Path:
    if sys.version_info < (3, 11):
        raise RuntimeError('Install Python 3.11 or newer, then run py start.py again.')
    python = ROOT / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.exists():
        subprocess.run([sys.executable, '-m', 'venv', str(ROOT / '.venv')], check=True)
    check = subprocess.run([str(python), '-c', 'import sys; assert sys.version_info >= (3,11)'], capture_output=True)
    if check.returncode:
        raise RuntimeError('The project virtual environment is unusable. Rename .venv and rerun this launcher to recreate it on this device.')
    requirements = ROOT / 'requirements.txt'
    stamp = ROOT / '.venv' / '.requirements-sha256'
    digest = hashlib.sha256(requirements.read_bytes()).hexdigest()
    dependencies = subprocess.run([str(python), '-c', 'import irsdk, yaml, requests, dotenv'], capture_output=True)
    if dependencies.returncode or not stamp.exists() or stamp.read_text() != digest:
        subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(requirements)], check=True)
        stamp.write_text(digest)
    return python


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', nargs='?', choices=['viewer', 'record', 'all', 'setup'], default='viewer')
    parser.add_argument('--database', type=Path, help='Optional shared path override for both processes on this PC.')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    children = []
    try:
        python = prepare()
        database_args = ['--database', str(args.database.expanduser().resolve())] if args.database else []
        storage = [str(python), '-m', 'iracing_storage', *database_args]
        subprocess.run([*storage, 'init'], cwd=ROOT, check=True)
        if args.mode == 'setup':
            print('Setup complete. Run py start.py all to start the viewer and recorder.')
            return
        if args.mode in ('viewer', 'all'):
            viewer = subprocess.Popen([*storage, 'serve', '--port', str(args.port)], cwd=ROOT)
            children.append(viewer)
            for _ in range(100):
                if viewer.poll() is not None:
                    raise RuntimeError('Viewer could not start. Check the error above; the port may already be in use.')
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{args.port}/api/v1/library?limit=1', timeout=.3):
                        break
                except OSError:
                    time.sleep(.1)
            else:
                raise RuntimeError('Viewer did not become ready.')
            if not args.no_browser:
                webbrowser.open(f'http://127.0.0.1:{args.port}/')
        if args.mode in ('record', 'all'):
            children.append(subprocess.Popen([str(python), str(ROOT / 'iracing_local.py'), *database_args], cwd=ROOT))
        print('Keep this terminal open. Ctrl+C stops the application.', flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(.2)
        if any(child.returncode for child in children if child.poll() is not None):
            raise RuntimeError('An application process stopped with an error. See the terminal output above.')
    except KeyboardInterrupt:
        pass  # Console Ctrl+C is also delivered to children, allowing normal flush/shutdown.
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f'Startup error: {exc}\n')
    finally:
        for child in children:
            if child.poll() is None:
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.terminate()
                    child.wait(timeout=5)


if __name__ == '__main__':
    main()
