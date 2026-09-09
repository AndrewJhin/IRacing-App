# Storage validation — 2026-09-08

Validated on Windows with Python 3.12.14, SQLite 3.53.1, pyirsdk 1.3.6 and PyYAML 6.0.3.

- `python -m unittest discover -v`: 27 tests passed, including the 6 existing extractor tests.
- Crash test: a subprocess exits without closing SQLite; both committed samples survive, the third pending sample is absent, and status does not falsely claim completion.
- Import tests: rollback after multiple batches and a malformed tail, repeat-import deduplication, source-change detection, and setup associations before/after updates.
- Actual ephemeral HTTP server: pagination, invalid parameters, missing recordings, read-only behavior, and cross-origin/Host rejection.
- Other coverage: fake-SDK capture/disconnect/interruption/errors, mocked web-response storage, stable per-user database paths, live file/SQL agreement, flexible arrays/missing/nonfinite fields, differently shaped setups, legacy provenance, schema reopening, foreign keys, concurrent readers and backups.
- CLI smoke checks: initialize, import JSON, list and backup; `pip check` found no broken dependencies.
- `git diff --check`: passed.

## Synthetic throughput

`python scripts/benchmark_storage.py` wrote 3,600 samples with the 130 current profile fields and representative six-element arrays, with 60-sample commits and FULL synchronization.

| Measurement | Observed |
| --- | ---: |
| Write/finalize time | 0.972 seconds |
| Throughput | 3,705 samples/second |
| Query 1,000 samples, requesting three channels | 91.61 milliseconds |
| Closed database size | 17.38 MB |
| Extrapolated SQL size at 60 Hz for this payload | 1.04 GB/hour |

These are storage-only measurements on this machine with synthetic values. They exclude SDK access, original file writes, large real per-car arrays, frontend rendering and long-duration growth. They do not guarantee live capture rate or disk usage. JSONL exports require additional space. The benchmark uses a temporary database and adds no synthetic sessions to the application database.

## Remaining simulator check

No real simulator session was available during validation. Run `iracing_local.py` with iRacing open, drive briefly, trigger a pit transition, then stop with Ctrl+C. Use the printed recording ID with `inspect`, `samples` and `snapshots`; verify track, car, setups and observed timing against that session. No real telemetry was inserted by automated validation.
