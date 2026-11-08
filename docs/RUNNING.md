# Running ORBITAL EYE

This guide takes a fresh copy of the code from zero to a working dashboard on Windows, then lists every URL you can open to check that each part works.

**You need:** Windows with PowerShell, **Python 3.12** (not 3.13 or later, because `rasterio` fails to load on newer versions), Node.js with npm, and internet access.

## Contents

1. [Set up](#set-up)
2. [Run the project](#run-the-project)
3. [Links to check everything](#links-to-check-everything)
4. [Check every endpoint at once](#check-every-endpoint-at-once)
5. [Reading the results](#reading-the-results)
6. [Run the tests](#run-the-tests)
7. [Quick fixes](#quick-fixes)

---

## Set up

Do these steps once.

### Step 0: Check the prerequisites

```powershell
py -3.12 --version
node --version
npm --version
```

- If `py -3.12` fails, install Python 3.12 from python.org and tick "Add to PATH".
- If `node` fails, install the current LTS release from nodejs.org.

### Step 1: Get the code

If it comes as a zip, extract it to a folder such as `C:\orbital-eye`.

If it comes from a Git repository, clone it. Use the real address and type no angle brackets:

```powershell
git clone https://github.com/yourname/orbital-eye.git
cd orbital-eye
```

### Step 2: Backend

```powershell
cd backend
py -3.12 -m venv .venv312
.venv312\Scripts\Activate.ps1
pip install -r requirements.txt
cd ..
```

If PowerShell blocks the activate script, run this first and retry:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

### Step 3: Frontend

```powershell
cd frontend
npm install
cd ..
```

### Step 4: Environment file

```powershell
Copy-Item .env.example .env
notepad .env
```

Fill in the values that `.env.example` lists. The NASA FIRMS key is the main one, and it is free from NASA. Without it, fire detections will not load. Never commit `.env`.

### Step 5: Load the first data

This needs internet. Run it from `backend` with `.venv312` active:

```powershell
cd backend
python -m app.ingestion.run_celestrak
python -m app.ingestion.run_firms
python -m app.analysis.vegetation_job
python -m app.analysis.vegetation_backfill --days 180 --limit 12
python -m app.analysis.change_series --days 180
python -m app.analysis.change_baseline
cd ..
```

The Sentinel-2 steps read imagery over the network and can take several minutes. `change_series` and `change_baseline` need the scenes from the earlier steps, so run them in this order. A fresh database starts empty, so panels show "no data" until these finish.

---

## Run the project

Use three terminals and keep each one open.

**Terminal 1: Backend API**

```powershell
cd backend
.venv312\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

**Terminal 2: Frontend dashboard**

```powershell
cd frontend
npm run dev
```

**Terminal 3: Scheduler (optional, refreshes data every 30 minutes)**

```powershell
cd backend
.venv312\Scripts\Activate.ps1
python -m app.scheduler --loop-minutes 30
```

The dashboard works without the scheduler and shows whatever is stored. Without it, jobs turn overdue and orbital elements go stale after 14 days.

To stop any of them, click its terminal and press `Ctrl+C`.

Then open:

- Dashboard: <http://localhost:5173>
- API docs: <http://127.0.0.1:8000/docs>

---

## Links to check everything

The backend must be running for every link except the dashboard page itself.

### Main pages

| What | Link |
|---|---|
| Dashboard | <http://localhost:5173> |
| API docs (Swagger). Lists every route, including alerts, AOI and footprint | <http://127.0.0.1:8000/docs> |
| API docs (ReDoc) | <http://127.0.0.1:8000/redoc> |
| Raw API schema | <http://127.0.0.1:8000/openapi.json> |

### Health and system

| What to check | Link |
|---|---|
| Server is up | <http://127.0.0.1:8000/api/health> |
| Scheduler and job status | <http://127.0.0.1:8000/api/system/status> |

### Satellites and orbits

| What to check | Link |
|---|---|
| Current state of all six satellites | <http://127.0.0.1:8000/api/satellites/state> |
| Sentinel-2B track | <http://127.0.0.1:8000/api/satellites/42063/track> |
| Sentinel-2A track | <http://127.0.0.1:8000/api/satellites/40697/track> |
| Sentinel-2C track | <http://127.0.0.1:8000/api/satellites/60989/track> |
| Suomi NPP track | <http://127.0.0.1:8000/api/satellites/37849/track> |
| NOAA-20 track | <http://127.0.0.1:8000/api/satellites/43013/track> |
| NOAA-21 track | <http://127.0.0.1:8000/api/satellites/54234/track> |
| Upcoming passes over the AOI | <http://127.0.0.1:8000/api/passes/next> |
| Idealized orbit (simulated) | <http://127.0.0.1:8000/api/orbit/ground-track> |
| SGP4 fixture track (December 2019, simulated) | <http://127.0.0.1:8000/api/orbit/tle-ground-track> |

### Fires

| What to check | Link |
|---|---|
| Stored thermal anomalies | <http://127.0.0.1:8000/api/fires> |
| Last 30 days | <http://127.0.0.1:8000/api/fires?days=30> |
| Multi-satellite clusters | <http://127.0.0.1:8000/api/fires/corroborated?days=30> |

### Vegetation (NDVI)

| What to check | Link |
|---|---|
| Latest NDVI result | <http://127.0.0.1:8000/api/vegetation/latest> |
| Latest NDVI image | <http://127.0.0.1:8000/api/vegetation/latest.png> |
| One point per stored scene | <http://127.0.0.1:8000/api/vegetation/series> |
| Latest two-date change | <http://127.0.0.1:8000/api/vegetation/change/latest> |
| Latest change image | <http://127.0.0.1:8000/api/vegetation/change/latest.png> |
| Each scene against the previous one | <http://127.0.0.1:8000/api/vegetation/change/series> |
| Each scene against the baseline | <http://127.0.0.1:8000/api/vegetation/change/baseline> |

The alert, AOI and footprint routes are not listed here. Open `/docs` and expand them there.

### Through the frontend proxy

The dashboard also serves the API through its own proxy. <http://localhost:5173/api/health> should return the same result as the backend link. If it does, the frontend and backend are connected correctly.

---

## Check every endpoint at once

Run this in a new terminal while the backend is running. It prints the status code of each endpoint above.

```powershell
$base = "http://127.0.0.1:8000"
$paths = @(
 "/api/health","/api/system/status","/api/satellites/state",
 "/api/satellites/42063/track","/api/satellites/40697/track","/api/satellites/60989/track",
 "/api/satellites/37849/track","/api/satellites/43013/track","/api/satellites/54234/track",
 "/api/passes/next","/api/orbit/ground-track","/api/orbit/tle-ground-track",
 "/api/fires","/api/fires/corroborated?days=30",
 "/api/vegetation/latest","/api/vegetation/latest.png","/api/vegetation/series",
 "/api/vegetation/change/latest","/api/vegetation/change/latest.png",
 "/api/vegetation/change/series","/api/vegetation/change/baseline"
)
foreach ($p in $paths) {
  try { $r = Invoke-WebRequest "$base$p" -UseBasicParsing -TimeoutSec 60; "{0}  {1}" -f $r.StatusCode, $p }
  catch { "{0}  {1}" -f $_.Exception.Response.StatusCode.value__, $p }
}
```

---

## Reading the results

| Result | Meaning |
|---|---|
| `200` | Working |
| `404` on a `.png` link | No image stored yet. Run the vegetation job, or the change job for the change image |
| `404` on a track link | That catalogue number is not configured |
| `200` with `"status": "none"`, or an empty list | A real answer: no data is stored yet. This is not an error |
| `500` | A bug or a missing table. Check the backend terminal for the error |
| No response | The backend is not running |

---

## Run the tests

```powershell
cd backend
.venv312\Scripts\Activate.ps1
python -m pytest tests -q
```

The C cross-check tests may need a C compiler on the PATH. If they fail, check that first.

---

## Quick fixes

| Problem | Fix |
|---|---|
| `No module named 'app'` | Run Python commands from `backend`, not the project root |
| `rasterio` import error | Wrong Python. Use the `.venv312` environment and check that `python --version` says 3.12 |
| `another scheduler holds ...scheduler.lock` | A scheduler is already running. If none is, delete `backend\data\scheduler.lock` |
| Panels show `getaddrinfo failed` | Network or DNS problem. Check the internet connection and rerun the job |
| Satellite shows `stale_element_set` | Run `python -m app.ingestion.run_celestrak` |
| PowerShell says `The '<' operator is reserved` | A placeholder such as `<PID>` was typed literally. Replace it with a real value |
