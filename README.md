# iRacing data extraction starter

## Setup

1. Create a virtual environment and install dependencies:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   py -m pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and set your iRacing credentials. Keep `.env` private.

3. Pull a starter response:

   ```powershell
   py iracing_client.py
   ```

The default request uses `/data/member/info` and writes the response to `data/iracing-response.json`. To try another endpoint from the iRacing data API, pass its path under `/data`:

```powershell
py iracing_client.py --endpoint /member/info
```

The client hashes the password with SHA-256 and base64-encodes the digest before sending it to iRacing's authentication endpoint. It does not print or store the password.

## Capture the running simulator without login

When the iRacing simulator is open, the local SDK provides live telemetry through shared memory. It does not need your email or password. The collector uses `practice_profile.json` to select which of the 334 available SDK variables to record (default: 130 fields optimized for race engineering analysis):

```powershell
.venv\Scripts\python.exe iracing_local.py
```

To use a different profile or specify its path:

```powershell
.venv\Scripts\python.exe iracing_local.py --profile path/to/custom_profile.json
```

Output is written under `data/captures/<UTC session>/`:

- `catalog/live_variables.json` and `.csv`: the complete runtime variable catalog (all 334 headers), with excluded fields marked as `excluded_by_profile`.
- `stints/stint-0000/telemetry.jsonl`: one record per SDK tick with only the selected live variables from the active profile.
- `stints/stint-0000/session_info.yaml`: latest complete raw SessionInfo YAML (unchanged).
- `stints/stint-0000/session_info_updates.jsonl`: every raw SessionInfo update (unchanged).
- `stints/stint-0000/car_setup.yaml` and `.json`: the setup captured at stint start and after pit entries (unchanged).
- `stints/stint-0000/metadata.json`: includes profile ID, version, and field availability for this stint.

The first stint starts immediately. A new stint starts when `OnPitRoad` changes from false to true, creating a new telemetry batch, setup snapshot, and metadata record. Stop with `Ctrl+C`. For a short validation capture, use `--max-ticks 120`.

Run offline tests with:

```powershell
.venv\Scripts\python.exe -m unittest test_iracing_local.py
```

This local feed is for the active simulator session; use `iracing_client.py` for account data and historical web API endpoints.
