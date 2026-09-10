# Apex — Session Studio

See [the project guide](../README.md#run-on-any-windows-pc) for portable Windows setup and [after-session review](../README.md#after-session-review) for behavior and measurement limits.

Run `py start.py viewer`, or `.\.venv\Scripts\python.exe -m iracing_storage serve` after initial setup. Open the printed local URL. The Python viewer serves source assets directly; no build is required, and old `dist` files cannot hide source updates.

The viewer uses same-origin read-only API requests. It loads the selected date and recording on demand with no periodic polling. Date boundaries use the browser's local midnight through the next midnight, with SQL filtering before pagination. Each lap comparison has its own stint and condition filters. Sector and custom range changes request bounded telemetry for that distance range. Setup review receives only the first snapshot of each stint, not every historical update.

Validation:

```powershell
node --test frontend/tests/*.test.js
node frontend/build.mjs
.\.venv\Scripts\python.exe -m unittest discover -v
```

The optional build checks syntax and produces static copies for packaging; the local viewer always serves source. Tests cover browser fetch binding, manual loading, date ranges, independent lap filters, stale-response rejection, partial history loading, sector timing, steering, stint transitions and setup capture.
