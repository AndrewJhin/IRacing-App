"""Local session viewer and read-only JSON API. No simulator dependencies."""

from __future__ import annotations

import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from .database import Store, encode
from .viewer import Viewer, library, trace


def create_server(database: Path, port: int = 8765) -> ThreadingHTTPServer:
    # Fail before listening if this is not an initialized application database.
    with Store(database, readonly=True):
        pass
    viewer = Viewer()
    frontend = Path(__file__).resolve().parents[1] / 'frontend'
    assets = {'/': ('index.html', 'text/html; charset=utf-8'),
              '/index.html': ('index.html', 'text/html; charset=utf-8'),
              '/styles.css': ('styles.css', 'text/css; charset=utf-8'),
              '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
              '/data.js': ('data.js', 'text/javascript; charset=utf-8'),
              '/live.js': ('live.js', 'text/javascript; charset=utf-8'),
              '/favicon.svg': ('favicon.svg', 'image/svg+xml')}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def send_json(self, status, body):
            data = encode(body).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            # Do not allow browser DNS rebinding or cross-origin reads of local data.
            host = self.headers.get('Host', '')
            if host not in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'):
                self.send_json(403, {'error': 'Local host required'})
                return
            origin = self.headers.get('Origin')
            if origin is not None and origin != 'http://' + host:
                self.send_json(403, {'error': 'Use a same-origin frontend proxy'})
                return
            url = urlsplit(self.path)
            if url.path in assets:
                filename, content_type = assets[url.path]
                directory = frontend / 'dist' if (frontend / 'dist' / 'index.html').is_file() else frontend
                try:
                    data = (directory / filename).read_bytes()
                except OSError:
                    self.send_json(404, {'error': 'Frontend asset not available'})
                    return
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(data)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.end_headers()
                self.wfile.write(data)
                return
            parts = [unquote(part) for part in url.path.strip('/').split('/')]
            params = parse_qs(url.query, keep_blank_values=True)

            def get(name, default=None, convert=str):
                values = params.get(name)
                if values is None:
                    return default
                if len(values) != 1:
                    raise ValueError(f'{name} must appear once')
                return convert(values[0])

            def allowed(*names):
                if set(params) - set(names):
                    raise ValueError('Unknown query parameter')

            try:
                with Store(database, readonly=True) as store:
                    if parts == ['api', 'v1', 'library']:
                        allowed('limit', 'offset')
                        body = library(store, limit=get('limit', 100, int), offset=get('offset', 0, int))
                    elif parts == ['api', 'v1', 'recordings']:
                        allowed('limit', 'offset')
                        body = {'items': store.list_recordings(limit=get('limit', 100, int), offset=get('offset', 0, int))}
                    elif parts == ['api', 'v1', 'documents']:
                        allowed('kind', 'limit', 'offset')
                        body = {'items': store.documents(kind=get('kind'), limit=get('limit', 100, int), offset=get('offset', 0, int))}
                    elif len(parts) in (4, 5) and parts[:3] == ['api', 'v1', 'recordings']:
                        recording_id = parts[3]
                        recording = store.recording(recording_id)
                        if len(parts) == 4:
                            allowed()
                            body = recording
                        elif parts[4] == 'overview':
                            allowed()
                            body = viewer.overview(store, recording_id)
                        elif parts[4] == 'trace':
                            allowed('start', 'end', 'limit')
                            start, end = get('start', convert=int), get('end', convert=int)
                            if start is None or end is None:
                                raise ValueError('start and end are required')
                            body = trace(store, recording_id, start, end, get('limit', 1200, int))
                        elif parts[4] == 'samples':
                            allowed('after', 'limit', 'channels', 'stint_id', 'session_num', 'lap', 'time_min', 'time_max')
                            channels = get('channels')
                            body = store.samples(recording_id, after=get('after', -1, int), limit=get('limit', 1000, int),
                                                 channels=channels.split(',') if channels is not None else None,
                                                 stint_id=get('stint_id', convert=int), session_num=get('session_num', convert=int),
                                                 lap=get('lap', convert=int), time_min=get('time_min', convert=float),
                                                 time_max=get('time_max', convert=float))
                        elif parts[4] == 'catalog':
                            allowed()
                            body = {'items': store.catalog(recording_id)}
                        elif parts[4] == 'snapshots':
                            allowed('after', 'limit')
                            body = {'items': store.snapshots(recording_id, after=get('after', 0, int), limit=get('limit', 100, int))}
                        else:
                            raise KeyError('route')
                    else:
                        raise KeyError('route')
                self.send_json(200, body)
            except KeyError:
                self.send_json(404, {'error': 'Not found'})
            except (ValueError, OverflowError):
                self.send_json(400, {'error': 'Invalid query parameters'})
            except sqlite3.Error:
                self.send_json(503, {'error': 'Database unavailable; retry shortly'})

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def serve(database: Path, port: int = 8765) -> None:
    # The viewer can be launched before the first capture on a fresh installation.
    with Store(database):
        pass
    with create_server(database, port) as server:
        print(f'Session Studio: http://127.0.0.1:{server.server_port}/', flush=True)
        print(f'Read-only storage API: http://127.0.0.1:{server.server_port}/api/v1/recordings', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
