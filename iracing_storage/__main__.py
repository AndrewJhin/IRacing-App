"""Run `python -m iracing_storage --help` for storage and query commands."""

import argparse
import json
import sqlite3
from pathlib import Path

from .database import Store, default_database, encode
from .importer import import_capture, read_json


def main() -> None:
    parser = argparse.ArgumentParser(description='Local iRacing SQL storage and read-only queries.')
    parser.add_argument('--database', type=Path, default=default_database())
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('init', help='Initialize or migrate the database.')
    importer = commands.add_parser('import-capture', help='Import one closed capture directory atomically.')
    importer.add_argument('directory', type=Path)
    documents = commands.add_parser('import-json', help='Store a web API response or future JSON document.')
    documents.add_argument('file', type=Path)
    documents.add_argument('--kind', required=True)
    documents.add_argument('--recording-id')
    documents.add_argument('--schema-version', type=int, default=1)
    for name in ('list', 'documents'):
        command = commands.add_parser(name)
        command.add_argument('--limit', type=int, default=100)
        command.add_argument('--offset', type=int, default=0)
        if name == 'documents':
            command.add_argument('--kind')
    for name in ('inspect', 'catalog', 'snapshots', 'samples'):
        command = commands.add_parser(name)
        command.add_argument('recording_id')
        if name in ('snapshots', 'samples'):
            command.add_argument('--limit', type=int, default=1000)
            command.add_argument('--after', type=int, default=-1 if name == 'samples' else 0)
        if name == 'samples':
            command.add_argument('--channels', help='Comma-separated exact channel names.')
            command.add_argument('--stint-id', type=int)
            command.add_argument('--session-num', type=int)
            command.add_argument('--lap', type=int)
            command.add_argument('--time-min', type=float)
            command.add_argument('--time-max', type=float)
    backup = commands.add_parser('backup')
    backup.add_argument('destination', type=Path)
    server = commands.add_parser('serve', help='Open the local frontend and read-only JSON API on 127.0.0.1.')
    server.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    try:
        if args.command == 'serve':
            from .api import serve
            serve(args.database, args.port)
            return
        readonly = args.command not in ('init', 'import-capture', 'import-json')
        with Store(args.database, readonly=readonly) as store:
            if args.command == 'init':
                result = {'database': str(store.path.resolve()), 'schema_version': 1}
            elif args.command == 'import-capture':
                result = import_capture(store, args.directory)
            elif args.command == 'import-json':
                with store.connection:
                    result = {'document_id': store.add_document(args.kind, read_json(args.file),
                              recording_id=args.recording_id, schema_version=args.schema_version, source_uri=str(args.file.resolve()))}
            elif args.command == 'list':
                result = store.list_recordings(limit=args.limit, offset=args.offset)
            elif args.command == 'documents':
                result = store.documents(kind=args.kind, limit=args.limit, offset=args.offset)
            elif args.command == 'inspect':
                result = store.recording(args.recording_id)
            elif args.command == 'catalog':
                result = store.catalog(args.recording_id)
            elif args.command == 'snapshots':
                result = store.snapshots(args.recording_id, after=args.after, limit=args.limit)
            elif args.command == 'samples':
                result = store.samples(args.recording_id, after=args.after, limit=args.limit,
                                       channels=args.channels.split(',') if args.channels is not None else None,
                                       stint_id=args.stint_id, session_num=args.session_num, lap=args.lap,
                                       time_min=args.time_min, time_max=args.time_max)
            elif args.command == 'backup':
                store.backup(args.destination)
                result = {'backup': str(args.destination.resolve())}
        print(json.dumps(json.loads(encode(result)), indent=2, ensure_ascii=False))
    except (OSError, ValueError, KeyError, sqlite3.Error) as exc:
        parser.exit(1, f'Storage error: {exc}\n')


if __name__ == '__main__':
    main()
