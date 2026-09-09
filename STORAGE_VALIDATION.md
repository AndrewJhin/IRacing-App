# Storage and live viewer validation — 2026-09-09

Validated on Windows with Python 3.12.14, SQLite 3.53.1, pyirsdk 1.3.6 and PyYAML 6.0.3.

- `python -m unittest discover -v`: 37 tests passed, including extractor startup waiting, reconnect orchestration, interruption and bounded capture.
- `node --test frontend/tests/*.test.js`: 8 tests passed, including live discovery, stable recording selection, stale-response rejection, recovery and missing-value handling.
- `node frontend/build.mjs`: six public assets built successfully.
- Viewer HTTP integration: committed telemetry and new setup snapshots appear through the API while a writer remains active; pending samples remain invisible until committed. Lap tests cover observed crossings, delayed timing, partial capture, gaps, incidents, clock resets and unavailable channels. Bounded traces retain speed minima and brake spikes.
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

The updated viewer was started on localhost and its assets and empty production database were read successfully through the actual JavaScript adapter. No example telemetry was added to the application database. Browser interaction and visual testing have not been performed.

No real simulator session was available during validation. Run `iracing_local.py`, open iRacing, complete several laps, trigger a pit transition, then stop with Ctrl+C. Verify the frontend's track, player car, current telemetry, lap timing and setup history against that session. Historical viewing should continue after the collector stops. Tests use temporary databases with synthetic fixtures; actual SDK lap-boundary behavior still needs this on-track check.
