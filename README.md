# iRacing data extraction starter

## Run the application

The browser viewer/API and live telemetry extractor are separate processes in this same project. They use the same SQLite database by default and can run simultaneously. **The frontend reads real recordings and refreshes automatically while extraction runs.** SQLite does not require a separate database server.

For a new checkout, install Python 3.11+ and prepare the environment once from the repository directory:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m iracing_storage init
```

In one PowerShell window, start the viewer:

```powershell
.\.venv\Scripts\python.exe -m iracing_storage serve
```

Open `http://127.0.0.1:8765/` in your browser. Keep that PowerShell window running. After updating this code, stop an older viewer with Ctrl+C and restart it. The viewer creates the database if needed and shows an empty state until recordings arrive.

In a second PowerShell window in the same repository, start extraction:

```powershell
.\.venv\Scripts\python.exe iracing_local.py
```

The extractor waits for the simulator, then begins saving telemetry when you drive on track. It writes SQLite and capture files, and waits for another connection if the simulator closes. The frontend discovers recordings, track/car details, laps and setup snapshots automatically. Updates normally appear within a few seconds (up to roughly one second to commit plus a 1.5-second polling interval and request processing). Garage/menu pauses show the age of the last sample.

Stop either process with Ctrl+C in its own window; stopping the viewer does not stop extraction. The viewer can review saved sessions without iRacing open, and extraction can run without the viewer. Both processes must use the same database path if you override the default with `--database`.

After a drive, inspect the saved recordings:

```powershell
.\.venv\Scripts\python.exe -m iracing_storage list
```

`iracing_client.py` is an optional third command for iRacing's web/account data API; it is not required for live telemetry or the session viewer. Node.js is only needed to rebuild or test frontend assets during development, not to run this application from source. If you previously built `frontend/dist`, rebuild it with `node frontend/build.mjs` after updating; the server prefers built assets when present.

## Session Studio frontend

Select a circuit, car and recording, then use **Summary**, **Analytics** and **Setup** to explore observed lap pace, compare recorded speed/throttle/brake traces and inspect car-specific setup snapshots. Analytics follows the current lap and Setup follows the latest snapshot until you choose a historical item.

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

Output is written under `data/captures/<UTC session>/`:

- `catalog/live_variables.json` and `.csv`: the complete runtime variable catalog, with excluded fields marked as `excluded_by_profile`.
- `stints/stint-0000/telemetry.jsonl`: one record per captured SDK tick with selected profile variables and core viewer fields. Unavailable fields are marked explicitly.
- `stints/stint-0000/session_info.yaml`: latest complete raw SessionInfo YAML (unchanged).
- `stints/stint-0000/session_info_updates.jsonl`: every raw SessionInfo update (unchanged).
- `stints/stint-0000/car_setup.yaml` and `.json`: the setup captured at stint start and after pit entries (unchanged).
- `stints/stint-0000/metadata.json`: includes profile ID, version, and field availability for this stint.

The first stint starts when the car is actively on track. A new stint starts when `OnPitRoad` changes from false to true, creating a new telemetry batch, setup snapshot, and metadata record. Stop with `Ctrl+C`. For a short validation capture, use `--max-ticks 120`.

Run offline tests with:

```powershell
.venv\Scripts\python.exe -m unittest test_iracing_local.py
```

This local feed is for the active simulator session; use `iracing_client.py` for account data and historical web API endpoints.
