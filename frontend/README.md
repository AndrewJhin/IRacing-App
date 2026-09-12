# Apex — Session Studio

See the [project guide](../README.md) for setup and measurement details. Run `py start.py viewer` and open the local URL. The Python viewer serves current source assets directly; no frontend build is required.

## Session Finder

The full-page landing view shows up to five recent sessions, regardless of date. Circuit, car, optional date and text search narrow a paginated result table. Circuit and car must be chosen before opening a search result. Recent-session shortcuts select their known pair directly. No session is automatically opened and no telemetry is downloaded on this page. A return button preserves search context.

## Review

- Summary preserves session metrics and adds the all-time clean best for the same circuit layout/car across saved sessions.
- Analytics offers an individual session lap, all-time best, or all-clean-session-lap average for either comparison side. Stint/condition filters affect individual laps only. Sector/custom-range zoom, steering and gear readouts remain available.
- Stints compares clean pace and coverage using the already-loaded summary.
- Setup loads on first opening and retains per-stint selection/comparison. Independently stacked columns remove gaps between short and tall setup sections.

Average traces use an equally weighted contribution per clean lap at shared distances. Missing coverage stays blank. Gear is the most common observed gear. The average-speed metric is the equally weighted mean of each lap's time-weighted speed over the shown range. These are derived analysis metrics, not official timing or setup instructions.

There is no recurring polling. Source/range requests are cached, duplicate comparisons share requests, and stale requests are cancelled. Finder never calls telemetry/setup endpoints. Initial review retrieves one session plus its benchmark descriptor; traces and setups load only on their tabs. Server caches are invalidated when source sessions change and restart empty.

## Checks

```powershell
node --test frontend/tests/*.test.js
node frontend/build.mjs
.\.venv\Scripts\python.exe -m unittest discover -v
```

The optional build checks syntax and copies assets. Tests cover empty/recent caps, filters and selection constraints, lazy loading, caching, stale responses, matching all-time bests, clean-lap averages, missing values and HTTP endpoints. Browser validation uses both real sessions and an isolated synthetic fixture database; fixtures are never inserted into the user's archive.
