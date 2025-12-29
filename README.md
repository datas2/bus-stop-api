# bus-stop-api
Location of AT Bus Stops and Routes (Auckland, New Zealand).

Feature class showing location of stops for bus, school bus, train and ferry services, as sourced from IVU GTFS data. GIS data is sourced from the gis_gtfs_stop table held in the data warehouse. Data in GIS is refreshed from data warehouse on a daily basis through a scheduled FME Server job.

IVU holds data relating to AT public transport operations only so does not necessarily reflect all stops across the Auckland region (e.g. train lines where AT do not run services such as Helensville to Wellsford do not appear in this dataset).

Read more in [Auckland Transport Open GIS Data](https://data-atgis.opendata.arcgis.com/datasets/ATgis::bus-stop/about).

---
# Context & Question
### Why does this API exist?

This API provides a thin, JSON/HTTP wrapper around Auckland Transport’s open bus-stop dataset, with extra capabilities for:
- Listing stops with pagination and simple name filtering.
- Looking up detailed information for a stop by `stop_code`.
- Finding nearby stops by name or geographic coordinates (using a Haversine-based distance approximation).

It is intended as a **public utility** for experiments, prototypes, and research:
- It may change or be discontinued without notice.
- It is not an official service of Auckland Transport.
- It is not designed as a mission-critical or production SLO-backed API.

Typical uses:
- Building small demos or dashboards around bus stop locations.
- Quickly exploring stops and their approximate spatial relationships.
- Serving as a backend for teaching, labs, or spatial data exercises.

---
## What It Is — and What It Is Not
### Scope and non-goals

**What it is:**

- A read-only REST API over a Parquet snapshot of the `stops` dataset.
- A way to query stops by:
    - Pagination and partial name match.
    - Exact `stop_code`.
    - Proximity to a given stop name or coordinate pair (`lat`, `lon`).
- A simple FastAPI app with:
    - API key enforcement via header `x-api-key`.
    - Per-IP rate limiting.
    - JSON-structured logging.

**What it is not:**

- Not a real-time, guaranteed-fresh data source.
    - The source data is refreshed periodically, but freshness is not guaranteed at API level.
- Not an official routing or timetable API.
    - It does not provide route planning, schedules, delays, or live vehicle positions.
- Not a full GIS engine.
    - Only basic proximity queries are supported, via Haversine distance computed in DuckDB.
- Not a general-purpose GTFS API.
    - It focuses only on stops; routes, trips, calendars, etc. are out of scope.

---
## How It Works (Conceptual)
### Mental model before endpoints

At a high level:

1. **Data source**  
A Parquet file (`stops.parquet`) stores a tabular snapshot of bus stops, with columns like:
    - `stop_code`
    - `stop_name`
    - `latitude`
    - `longitude`
    - `parent_station`
    - (optionally precomputed metric coordinates `x_meters`, `y_meters`)

2. **Query engine (DuckDB)**  
Each request that queries stops uses a helper (`query_stops`) that:
    - Connects to DuckDB in-memory.
    - Exposes the Parquet file as a view (`stops`).
    - Executes a parameterized SQL query.
    - Returns results as a list of dictionaries (suitable for FastAPI JSON responses).

3. **HTTP API (FastAPI)**  
- `main.py` initializes:
    - Logging (`JsonFormatter` + `setup_logging`).
    - Rate limiting middleware (simple in-memory sliding window by IP).
    - API key enforcement via dependency `require_api_key`.
- The **`/`** endpoint provides a health-like status (`name`, `version`, `uptime`).
    - The **`/stops`** router exposes the bus-stop operations:
        - Listing, lookup, and proximity queries.

4. **Security & access control**
- All `/stops` endpoints are protected by an API key:
    - Header: `x-api-key: <your-key>`
    - The key is compared against `API_KEY` from environment variables.
- The health endpoint `/` is intentionally open for simple liveness checks.

You can think of the system as:

```text
Parquet (stops.parquet)
        |
    DuckDB (SQL)
        |
FastAPI endpoints
        |
    JSON clients
```
---
## Trade-offs, Limitations & Responsible Use
### What you gain, what you lose, and what to be careful with
#### What you gain:
- Simple, stateless API on top of an open dataset.
- Flexible querying via SQL under the hood (DuckDB):
    - Filtering by stop name.
    - Ordering and pagination.
    -   Haversine-based distance ordering and filtering.
- Lightweight deployment (designed to run easily on Cloud Run / containers).
- JSON-structured logs for easier observability.
#### Trade-offs & limitations:
- **Performance & rate limiting**
    - Per-IP limit is enforced in memory (sliding window with MAX_REQUESTS and WINDOW_SECONDS).
    - High-traffic or multi-tenant use may need a more robust rate limiting strategy (e.g. Redis, API Gateway).
- **In-memory rate limiter**
    - State is per-process; in scaled-out deployments each instance enforces its own limits.
- **Data freshness**
    - The underlying Parquet file reflects the upstream GTFS-derived data at some snapshot.
    - There is no strict guarantee on synchronization frequency with Auckland Transport.
- **Geospatial precision**
    - Distance calculations use a Haversine approximation on lat/lon.
    - Good enough for nearby-stop queries, but not a full GIS engine or authoritative metric.

#### Responsible use:
- Do not rely on this API as a single source of truth for safety-critical or operational decisions.
- Respect rate limits and API key policies.
- If you build apps on top of this API, make users aware that:
    - Data may be incomplete or slightly outdated.
    - Service may change or be discontinued.
---
## API Reference & Status
### How to use it — and what to expect

#### Authentication
All `/stops` endpoints require an API key:
- Header:
    `x-api-key: <your-api-key>`
The health endpoint `/` does not require an API key.

#### Health
##### `GET /`

Returns basic information about the API and its uptime:
```json
{
    "msg": "API status 🚀",
    "name": "bus-stop-api",
    "version": "1.0.0",
    "uptime": 12345
}
```

#### Stops
All endpoints below are under the /stops prefix and require x-api-key.

##### `GET /stops`

List bus stops (paginated), with an optional partial name filter.

**Query parameters:**

- limit (int, default 50, min 1, max 1000): number of results.
- offset (int, default 0, min 0): offset for pagination.
- name (str, optional): case-insensitive partial match on stop_name.

**Example:**
```curl
GET /stops?limit=20&offset=0&name=Albert
x-api-key: <your-api-key>
```

**Response**
```json
{
    "count": 2,
    "results": [
        {
        "stop_code": 1001,
        "stop_name": "STOP ALBERT",
        "latitude": -36.84,
        "longitude": 174.76,
        "parent_station": null
        },
        ...
    ]
}
```

##### `GET /stops/code/{stop_code}`
Get full details of a bus stop by its numeric code.

**Path parameter:**
- stop_code (int): the stop code (as in the dataset).

**Example:**
```curl
GET /stops/code/1001
x-api-key: <your-api-key>
```

**Response (200):**
```json
{
    "count": 1,
    "results": [
        {
        "stop_code": 1001,
        "stop_name": "STOP ALBERT",
        "latitude": -36.84,
        "longitude": 174.76,
        "parent_station": null,
        "x_meters": 1757440.0,
        "y_meters": 5921071.0
        }
    ]
}
```

**Response (404):**
```json
{
    "detail": "Stop Code 9999 not found"
}
```

##### `GET /stops/nearby/by-name`
Given a stop name (partial or full), find its coordinates and then return nearby stops within a radius.

**Query parameters:**
- stop_name (str, required): partial or full stop name (case-insensitive).
- radius_m (float, default 100.0, min 0): maximum distance in meters.
- limit (int, default 20, min 1, max 200): upper bound on number of candidates considered.

**Example:**
```curl
GET /stops/nearby/by-name?stop_name=Albert&radius_m=150
x-api-key: <your-api-key>
```

**Response (200):**
```json
{
    "reference_stop": {
        "stop_code": 1001,
        "stop_name": "STOP ALBERT",
        "stop_lat": -36.84,
        "stop_lon": 174.76
    },
    "radius_m": 150.0,
    "count": 2,
    "results": [
        {
        "stop_code": 1001,
        "stop_name": "STOP ALBERT",
        "latitude": -36.84,
        "longitude": 174.76,
        "parent_station": null,
        "distance_m": 0.0
        },
        {
        "stop_code": 1002,
        "stop_name": "STOP B",
        "latitude": -36.8405,
        "longitude": 174.7605,
        "parent_station": "P1",
        "distance_m": 50.0
        }
    ]
}
```

**Response (404):**
```json
{
    "detail": "No stop found with name like 'Albert'"
}
```

##### `GET /stops/nearby/by-coords`
Given coordinates, return nearby stops within a radius.

**Query parameters:**
- lat (float, required): latitude in degrees.
- lon (float, required): longitude in degrees.
- radius_m (float, default 100.0, min 0): maximum distance in meters.
- limit (int, default 20, min 1, max 200): number of closest stops to consider before filtering by radius.

**Example:**
```curl
GET /stops/nearby/by-coords?lat=-36.84&lon=174.76&radius_m=100
x-api-key: <your-api-key>
```

**Response (200):**
```json
{
    "reference_coords": {
        "latitude": -36.84,
        "longitude": 174.76
    },
    "radius_m": 100.0,
    "count": 2,
    "results": [
        {
        "stop_code": 1001,
        "stop_name": "STOP A",
        "latitude": -36.84,
        "longitude": 174.76,
        "parent_station": null,
        "distance_m": 0.0
        },
        {
        "stop_code": 1002,
        "stop_name": "STOP B",
        "latitude": -36.8405,
        "longitude": 174.7605,
        "parent_station": "P1",
        "distance_m": 50.0
        }
    ]
}
```

#### Status & Stability
- Version: 1.0.0
- Stability: Experimental / best-effort.
- Breaking changes: Possible without prior notice (especially in payload shape or filtering behavior).
- Uptime: Reported via / but not guaranteed; no formal SLA.

Use this API for learning, prototyping, and research — and keep in mind it may evolve.