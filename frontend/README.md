# Apex — Session Studio

A local session viewer connected to SQLite through the Python backend. It uses JavaScript modules, CSS and SVG charts, with no frontend package installation or external assets required.

## Run

From the repository directory, start the viewer and open `http://127.0.0.1:8765/`:

```powershell
.\.venv\Scripts\python.exe -m iracing_storage serve
```

In another PowerShell window in the same directory, start extraction:

```powershell
.\.venv\Scripts\python.exe iracing_local.py
```

The extractor waits for iRacing and records when you drive on track. Both commands use `~\.iracing-app\storage\iracing.sqlite3` by default. The viewer creates it if needed. For another database, pass the same `--database` path to both commands. Stop each process with Ctrl+C; historical viewing does not require the simulator.

Restart the Python viewer after backend updates. If `frontend/dist` exists, rebuild it after frontend updates, then refresh the browser. A fresh checkout serves source assets without needing Node.js.

## Live views

- Circuit/car filters and a recording library populated from stored session metadata. Load older recordings beyond the first 100; selections use stable recording IDs.
- Summary: best observed lap, average and consistency, lap history, current telemetry and recorded conditions.
- Analytics: selected/reference lap pickers, speed/throttle/brake traces and a shared distance cursor. Follow the current lap or select a historical segment.
- Setup: recorded snapshots, optional following of the latest snapshot, previous-snapshot comparisons and added/removed parameter highlighting. Arbitrary nested car-specific fields retain their recorded values and units.
- Empty, loading, delayed-history and connection-error states, with automatic retry. No example sessions are substituted for unavailable data.

`live.js` polls the same-origin API 1.5 seconds after the previous refresh finishes. Extraction commits at least once per second while its loop is running, or when a sample batch fills. Expect updates within a few seconds under normal load. The interface shows sample age when capture pauses. New recordings are discovered automatically; an already selected recording remains selected.

## Measurement boundaries

Lap segmentation uses recording, stint, simulator session, lap number and clock resets. Statistics require an observed start and finish, a positive SDK last-lap time associated with that lap, and no detected gap, pit/garage activity or incident. The first partially captured lap and unfinished final lap remain visible without contributing to statistics. Incident-channel availability is labeled separately: complete capture does not certify official iRacing lap validity.

Missing channels stay unavailable; zero is a valid measurement. Trace responses contain at most 1,200 representative points by default, retaining bucket endpoints, minimum speed and maximum braking. Gaps and missing channels break chart lines. Cursor values come from nearby observed samples within 1% lap distance, without interpolation. The UI reports only whole-lap time differences between eligible laps; sector times and optimal laps are not calculated.

Setup snapshots reflect observed SDK updates. They do not establish the exact instant a garage change took effect. Legacy imports retain their provenance notices. The viewer never writes telemetry or modifies a car setup. `data.js` and its tests retain the original demo model as development fixtures; the application does not import it.

## Build and checks

With Node.js installed, run from the repository directory:

```powershell
node --test frontend/tests/*.test.js
node frontend/build.mjs
.\.venv\Scripts\python.exe -m unittest discover -v
```

The build checks JavaScript syntax and local asset references, then copies six public files into ignored `frontend/dist`. Only explicitly allowed frontend assets are served; credentials, Python source and database files are not exposed. API requests use read-only connections and reject cross-origin access.

Tests cover committed updates through a real local HTTP server, lap completeness and gaps, delayed SDK timing, telemetry reduction, missing data, adapter retries and stale-response rejection. Browser interaction and real simulator validation remain to be performed.
