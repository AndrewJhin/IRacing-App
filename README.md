# iRacing data extraction starter

## Run on any Windows PC

Install Python 3.11 or newer, clone this repository (do not copy another computer's `.venv`), then run from the project directory:

```powershell
py start.py all
```

The launcher creates `.venv`, installs requirements when needed, initializes SQLite, starts the viewer and recorder, and opens the browser after the viewer is ready. Keep its terminal open; Ctrl+C stops both processes. iRacing must be installed/running on that PC for capture. Viewing saved recordings does not require the simulator.

Use `py start.py setup` to prepare only, `py start.py viewer` for analysis, or `py start.py record` for extraction. `--no-browser` skips opening a browser. `--database 'D:\iRacingData\iracing.sqlite3'` applies the same override to both processes; `--port 8766` changes the viewer port.

Each Windows user's database is `%USERPROFILE%\.iracing-app\storage\iracing.sqlite3`; capture files are in `%USERPROFILE%\.iracing-app\captures`. No account name or project location is hardcoded. Both locations are created automatically. Each PC has its own local data; this does not synchronize recordings between devices. `IRACING_DATABASE` remains available as an override. Use the backup command in STORAGE.md to transfer a consistent database.

The existing VS Code commands still work after setup:

```powershell
.\.venv\Scripts\python.exe -m iracing_storage serve
.\.venv\Scripts\python.exe iracing_local.py
```

Run these in separate terminals. The viewer prints its database path and URL. Profiles resolve relative to the script, so launching from another working directory works. The viewer serves current source assets directly, with no Node build required. Restart the Python viewer/recorder after backend changes.

## After-session review

Session Finder is the landing page. It shows at most five recent sessions across all dates, plus circuit/car/date/text search. An empty archive shows no cards. Search is paginated in batches of 20; filters narrow the actual results, including matches beyond the first page. Choose both circuit and car to open a search result. Opening a recent session explicitly selects its recorded circuit/car pair for you. Sessions without identified circuit/car metadata cannot open review.

The viewer uses “session” in its UI; existing database recording IDs and capture formats remain unchanged. Date is optional and uses local midnight boundaries. Search accepts circuit/car names, layout, status or a session ID. Returning to Finder preserves the search. There is no recurring polling.

Summary shows clean lap best/average, lap history, and estimated sector bests/averages. The sector count and boundaries come from each recording's `SplitTimeInfo.Sectors`. Timing uses linear interpolation only between consecutive, gap-free telemetry samples at those boundaries, plus SDK lap timing at the finish. Only fully observed laps with known incident data, no incidents, no pit visit and no gaps contribute. Missing boundaries/timing remain unavailable; no assumption of three sectors is made.

Summary retains the session metrics and adds the all-time clean best across saved sessions for the exact circuit layout and car. Analytics can compare a lap from this session, that all-time best, or the average of every clean complete lap in the selected session on either side. Average traces align laps by distance and weight each lap equally. A channel is blank where any included lap lacks coverage; gear is the mode of recorded gears, never a fractional average. Average-speed metrics calculate time-weighted speed per lap in the displayed range, then weight those lap averages equally. Stint and condition filters apply to individual session laps, not to the all-clean-lap composite.

Analytics retains independent stint/condition filters, sector/custom distance zoom, speed/throttle/brake/steering traces and both gears at the cursor. The Stints tab compares clean-lap best/average and incident/partial counts without another data fetch. Steering is converted from radians to degrees. Named corner boundaries are not present in the captured session metadata; use a custom distance range to inspect a corner.

A new stint starts on pit exit and ends on pit entry or leaving the car. Starting capture while already driving creates a partial initial stint. A simulator session change also closes the prior stint. Garage/pit ticks never open a stint. The starting setup is captured once per stint and reused by every telemetry sample. Setup review selects a stint and can compare it with the previous stint. Existing recordings are retained and use the earliest setup snapshot of each historical stint; historical stint boundaries are not rewritten.

## Session Studio frontend

Select a circuit, car and recording, then use **Summary**, **Analytics** and **Setup** to explore observed lap pace, compare recorded speed/throttle/brake traces and inspect car-specific setup snapshots. Analytics supports session laps, the all-time clean best and clean-lap composites; Setup selects the starting setup for a stint.

```powershell
.\.venv\Scripts\python.exe -m iracing_storage serve
```

Open `http://127.0.0.1:8765/`. The viewer uses only stored data; missing sensors remain unavailable. Incomplete laps and detected gaps or incidents are labeled, and lap statistics require an observed start and finish. Sector times and optimal laps are not yet calculated. See [the frontend guide](frontend/README.md).

## Local SQL storage

Both extractors now save to SQLite in addition to their existing files. New telemetry fields, arrays and car-specific setup structures can be stored without adding SQL columns. Storage includes capture imports, setup history, SQL analytics views and a read-only frontend API.

```powershell
.\.venv\Scripts\python.exe -m iracing_storage init
.\.venv\Scripts\python.exe -m iracing_storage list
.\.venv\Scripts\python.exe -m iracing_storage serve
```

The default database is `~\.iracing-app\storage\iracing.sqlite3`. Use `--database` for a different local database or `--no-database` on an extractor for file-only capture. See [the storage guide](STORAGE.md) for setup, imports, endpoints, schema, SQL examples and backups, and [validation results](STORAGE_VALIDATION.md).

## Setup

1. Create a virtual environment and install dependencies:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

2. For web API extraction, set `IRACING_EMAIL` and `IRACING_PASSWORD` in a local `.env` file. Keep `.env` private. Local SDK capture does not need these credentials.

3. Pull a starter response:

   ```powershell
   .\.venv\Scripts\python.exe iracing_client.py
   ```

The default request uses `/data/member/info` and writes the response to `data/iracing-response.json`. To try another endpoint from the iRacing data API, pass its path under `/data`:

```powershell
.\.venv\Scripts\python.exe iracing_client.py --endpoint /member/info
```

The client hashes the password with SHA-256 and base64-encodes the digest before sending it to iRacing's authentication endpoint. It does not print or store the password.

## Capture the running simulator without login

When the iRacing simulator is open, the local SDK provides live telemetry through shared memory. It does not need your email or password. The collector uses `practice_profile.json` to select telemetry fields (the default profile contains 130). It also includes the core session, lap, activity and incident fields needed by the viewer, even with a custom profile. The available variable catalog depends on the running simulator:

```powershell
.venv\Scripts\python.exe iracing_local.py
```

To use a different profile or specify its path:

```powershell
.venv\Scripts\python.exe iracing_local.py --profile path/to/custom_profile.json
```

By default output is written under `%USERPROFILE%/.iracing-app/captures/<UTC session>/`:

- `catalog/live_variables.json` and `.csv`: the complete runtime variable catalog, with excluded fields marked as `excluded_by_profile`.
- `stints/stint-0000/telemetry.jsonl`: one record per captured SDK tick with selected profile variables and core viewer fields. Unavailable fields are marked explicitly.
- `stints/stint-0000/session_info.yaml`: complete raw SessionInfo YAML at stint start.
- `stints/stint-0000/session_info_updates.jsonl`: retained as an empty compatibility file; live capture saves YAML only at stint start.
- `stints/stint-0000/car_setup.yaml` and `.json`: the setup captured once at stint start.
- `stints/stint-0000/metadata.json`: includes profile ID, version, and field availability for this stint.

A stint starts on pit exit (or a partial start if capture begins while already driving). Pit entry or leaving the car closes it; garage/pit states never create a new stint. Stop with `Ctrl+C`. For a short validation capture, use `--max-ticks 120`.

Run offline tests with:

```powershell
.venv\Scripts\python.exe -m unittest test_iracing_local.py
```

This local feed is for the active simulator session; use `iracing_client.py` for account data and historical web API endpoints.


## On-demand loading and caching

Finder reads only session metadata and sends five recent cards plus one page of matching results, not telemetry. Opening a session calls its `/review` endpoint, which returns its summary and the matching all-time best descriptor. The first benchmark lookup derives clean-lap summaries for matching saved sessions on the backend; it may take longer for a large archive. Parsed identities and benchmark candidates are cached until their source changes. Detailed summaries use a 64-session LRU cache; average traces use a 16-entry cache. Caches are local to the running viewer and rebuild after restart.

Telemetry is requested only on entering Analytics or changing a comparison/range. Setup payloads are requested only on entering Setup. The client caches comparisons, combines duplicate requests and cancels obsolete requests. The new `/api/v1/finder`, `/recordings/{id}/review`, `/comparison` and `/stint-setups` endpoints preserve the same local-only, read-only access rules as the existing API. No telemetry, setup or database migration is required for this update.
