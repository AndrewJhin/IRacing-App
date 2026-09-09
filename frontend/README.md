# Apex — Session Studio

A local, interactive frontend mockup for the iRacing application. It is served by the existing Python backend and uses plain JavaScript modules, CSS and SVG charts. No frontend package installation or external assets are required.

## Run

From the GitHub checkout, with the existing virtual environment:

```powershell
.\.venv\Scripts\python.exe -m iracing_storage serve --port 8765
```

Open `http://127.0.0.1:8765/`. The backend still exposes its read-only `/api/v1/` routes on the same origin. Only five named frontend assets are served; the project directory, credentials, source Python and database files are not exposed.

## Included interactions

- Circuit, car and session selection: three circuits, three cars, three sessions per combination.
- Summary: best/optimal/average lap metrics, clean lap progression, lap filtering, sector opportunities and conditions.
- Lap table: open a specific lap in Analytics.
- Analytics: selected/reference lap pickers, speed/throttle/brake/delta charts and a shared distance cursor. The slider supports keyboard input; charts also support pointer inspection.
- Setup: stint snapshot selection, previous-snapshot comparison, changed-value highlighting and parameter structures that differ by car.
- Keyboard tab navigation, labeled selectors, focus indicators, narrow-screen layouts and reduced-motion support.

## Data boundary

**Every displayed session, time, trace, condition and setup value is synthetic demo data.** The interface marks this at the top and bottom of every view. Circuit drawings are illustrative schematics, and telemetry is generated for interaction design; neither should be used as an accurate reference for the named real tracks or cars. No telemetry is inserted into SQLite, and no garage changes are made.

This is a frontend mockup, not the production recording adapter. All demo generation is isolated in `data.js`; metrics are calculated from its session model. To connect real data, introduce an adapter over `/api/v1/recordings`, per-recording `snapshots`, `catalog` and paginated `samples`, preserving unavailable values and snapshot provenance. Real lap segmentation and completeness must be established from stored observations before reporting lap/sector results. Do not substitute demo metrics when a real recording is incomplete or empty.

Setup rendering traverses nested parameters instead of assuming every car has the same fields. It can later receive parsed setup snapshots through that adapter.

## Build and checks

With Node.js installed, run from `frontend/`:

```powershell
node --test tests/data.test.js
node build.mjs
```

The build checks JavaScript syntax and local asset references, then copies the five public files into ignored `frontend/dist/`. The server uses the built files when present and otherwise uses source files. After editing, rebuild and refresh the browser. No hosted deployment is needed for this local application.

The Node tests check all track/car/session combinations, metric arithmetic, timing/telemetry bounds, car-specific setup schemas and time formatting. The Python suite also checks frontend asset serving and rejection of nonpublic paths. Browser interaction/visual testing has not been performed.
