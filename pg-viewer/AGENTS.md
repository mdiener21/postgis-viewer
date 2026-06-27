# AGENTS.md

# PostGIS SQL Map Viewer

## Purpose

This project enables users to execute raw PostgreSQL/PostGIS/pgRouting SQL queries and visualize spatial query results in a high-performance map viewer when returned rows contain geometry columns.

The local development app is expected to run at:

```text
http://localhost:8000/
```

## Tech Stack

Backend:

```text
FastAPI
PostgreSQL
PostGIS
pgRouting
```

Frontend:

```text
Vue 3
Tailwind CSS
MapLibre GL JS as map viewer frontend
```

Testing:

```text
Playwright CLI for end-to-end tests
```

## Core Product Behavior

The application should allow users to:

1. Enter raw SQL queries.
2. Execute queries against PostgreSQL.
3. Detect whether the result set contains geometry.
4. Return tabular data and geometry metadata.
5. Render geometry results on a performant interactive map.
6. Support PostGIS and pgRouting result sets.
7. Handle large result sets safely and predictably.
8. Surface SQL errors clearly without exposing sensitive system information.

## Important Safety Constraints

This application executes raw SQL. Treat this as a high-risk area.

Agents must not weaken SQL execution safety.

Before changing SQL execution logic, check:

* Query timeout behavior
* Row limits
* Read-only enforcement
* Transaction handling
* Database user permissions
* SQL error sanitization
* Geometry size limits
* Frontend rendering limits

The backend should prefer a restricted read-only database user for query execution.

Dangerous SQL should be blocked or impossible through permissions, including:

```sql
DROP
DELETE
UPDATE
INSERT
ALTER
CREATE
TRUNCATE
GRANT
REVOKE
COPY
VACUUM
```

If write access is intentionally supported in the future, it must be explicit, permissioned, audited, and isolated from normal map query execution.

## Backend Guidelines

The backend is FastAPI.

Prefer clear module separation:

```text
backend/
  app/
    main.py
    api/
    core/
    db/
    schemas/
    services/
    tests/
```

Recommended responsibilities:

```text
api/        HTTP routes and request/response handling
schemas/    Pydantic request and response models
services/   SQL execution, geometry detection, result transformation
db/         database connection/session/pool handling
core/       config, logging, security, app settings
tests/      backend tests
```

Do not put SQL parsing, database execution, and response formatting directly inside route handlers.

## SQL Execution Rules

When implementing or modifying SQL execution:

* Use parameterized values where parameters are supported.
* Never concatenate untrusted user input into internal system SQL.
* Execute user SQL in a transaction where possible.
* Prefer read-only transaction mode.
* Apply a statement timeout.
* Apply a maximum row limit.
* Apply a maximum response payload size.
* Return consistent error objects.
* Avoid leaking connection strings, usernames, hostnames, stack traces, or internal paths.

Suggested SQL execution safeguards:

```sql
SET LOCAL statement_timeout = '10s';
SET LOCAL idle_in_transaction_session_timeout = '10s';
SET LOCAL transaction_read_only = on;
```

When wrapping user queries, prefer a safe subquery pattern:

```sql
SELECT *
FROM (
  -- user query here
) AS q
LIMIT :limit;
```

Be careful: not all SQL can be safely wrapped. Validate behavior with realistic PostGIS and pgRouting queries.

## Geometry Detection

The backend should detect geometry columns returned by SQL queries.

Expected geometry-like outputs may include:

```text
geometry
geography
WKB
WKT
GeoJSON
ST_AsGeoJSON(...)
```

Preferred output format for the frontend map should be GeoJSON.

For PostGIS geometry columns, convert using:

```sql
ST_AsGeoJSON(ST_Transform(geom, 4326))
```

Only transform when the geometry SRID is known and not already `4326`.

Handle unknown SRID carefully.

Do not assume all geometries are valid.

Recommended geometry metadata:

```json
{
  "geometry_columns": ["geom"],
  "srid": 4326,
  "geometry_type": "MultiLineString",
  "feature_count": 120,
  "bbox": [16.3, 48.1, 16.4, 48.2]
}
```

## Map Rendering Guidelines

The frontend should render spatial results efficiently.

Preferred behavior:

* Render GeoJSON as map layers.
* Fit map bounds to result geometry.
* Support points, lines, polygons, and collections.
* Handle empty geometries.
* Handle mixed geometry types.
* Avoid freezing the browser on large datasets.
* Show loading, success, empty, and error states.
* Show row count and geometry count.
* Allow users to inspect feature properties.

For large datasets, consider:

* Feature count limits
* Geometry simplification
* Server-side bounding boxes
* Vector tiles
* Pagination
* Clustering for points
* Web workers for heavy frontend processing

## Frontend Guidelines

The frontend uses Vue 3 and Tailwind CSS.

Prefer this structure where applicable:

```text
frontend/
  src/
    components/
    composables/
    pages/
    services/
    stores/
    types/
    utils/
```

Suggested components:

```text
SqlEditor.vue
QueryResultTable.vue
MapViewer.vue
QueryErrorPanel.vue
ResultMetadata.vue
LayerControls.vue
```

Frontend expectations:

* Keep SQL editor state separate from map state.
* Keep API calls in services or composables.
* Do not hardcode backend URLs if environment config exists.
* Use clear loading and error states.
* Avoid blocking the UI during large result rendering.
* Keep Tailwind classes readable and consistent.

## API Design Guidelines

Recommended API endpoints:

```text
POST /api/query
GET  /api/health
```

Possible request shape:

```json
{
  "sql": "SELECT id, name, geom FROM roads LIMIT 100",
  "limit": 1000
}
```

Possible response shape:

```json
{
  "columns": [
    {
      "name": "id",
      "type": "integer"
    },
    {
      "name": "name",
      "type": "text"
    },
    {
      "name": "geom",
      "type": "geometry"
    }
  ],
  "rows": [],
  "geojson": {
    "type": "FeatureCollection",
    "features": []
  },
  "metadata": {
    "row_count": 0,
    "geometry_columns": ["geom"],
    "has_geometry": true,
    "srid": 4326,
    "bbox": null
  }
}
```

Error responses should be consistent:

```json
{
  "error": {
    "code": "SQL_EXECUTION_ERROR",
    "message": "Query failed.",
    "detail": "syntax error at or near ..."
  }
}
```

Do not expose raw stack traces in API responses.

## PostgreSQL/PostGIS Guidelines

When working with PostGIS:

* Preserve SRID information.
* Prefer `ST_AsGeoJSON` for frontend rendering.
* Use `ST_IsValid` where invalid geometry may break rendering.
* Use `ST_Envelope` or `ST_Extent` for bounds.
* Use `ST_GeometryType` for geometry metadata.
* Use `ST_Transform` only when SRID is known.
* Avoid expensive geometry operations on unbounded result sets.

Useful SQL snippets:

```sql
SELECT ST_SRID(geom) FROM table_name WHERE geom IS NOT NULL LIMIT 1;
```

```sql
SELECT ST_GeometryType(geom) FROM table_name WHERE geom IS NOT NULL LIMIT 1;
```

```sql
SELECT ST_Extent(geom) FROM table_name WHERE geom IS NOT NULL;
```

```sql
SELECT ST_AsGeoJSON(ST_Transform(geom, 4326))::json AS geometry
FROM table_name
WHERE geom IS NOT NULL
LIMIT 1000;
```

## pgRouting Guidelines

pgRouting query results may contain route node IDs, edge IDs, costs, and geometries joined from edge tables.

Common result columns:

```text
seq
path_seq
node
edge
cost
agg_cost
geom
```

When visualizing routes:

* Prefer ordered route geometries.
* Preserve `seq` or `path_seq`.
* Support line rendering.
* Return route metadata such as total cost if available.
* Do not assume pgRouting result rows contain geometry unless the query joins edge geometry.

## Testing Guidelines

Use Playwright CLI for end-to-end tests.

E2E tests should verify:

* App loads at `http://localhost:8000/`
* SQL editor accepts input.
* Query can be executed.
* Non-spatial query renders a table.
* Spatial query renders a map layer.
* Invalid SQL displays a useful error.
* Empty result sets are handled.
* Large result warnings or limits work.
* pgRouting-style result can be visualized.

Example Playwright command:

```bash
npx playwright test
```

If the project uses a specific config:

```bash
npx playwright test --config=playwright.config.ts
```

Recommended E2E test scenarios:

```text
health.spec.ts
sql-table-results.spec.ts
sql-geometry-results.spec.ts
sql-error-handling.spec.ts
pgrouting-route.spec.ts
```

## Local Development Commands

Inspect the repository first:

```bash
ls
find . -maxdepth 2 -type f | sort
```

If Docker Compose exists:

```bash
docker compose up -d
docker compose ps
docker compose logs --tail=100
```

Backend checks may include:

```bash
python -m pytest
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend checks may include:

```bash
npm install
npm run dev
npm run build
npm run lint
```

Playwright checks:

```bash
npx playwright test
```

Adjust commands to match the actual repository structure.

## Environment Variables

Expected environment variables may include:

```text
DATABASE_URL
POSTGRES_HOST
POSTGRES_PORT
POSTGRES_DB
POSTGRES_USER
POSTGRES_PASSWORD
QUERY_TIMEOUT_SECONDS
QUERY_MAX_ROWS
QUERY_MAX_PAYLOAD_BYTES
CORS_ORIGINS
```

Never commit real secrets.

Use `.env.example` for documented placeholders.

## Security Rules

Never commit:

```text
.env
*.key
*.pem
*.crt
*.p12
*.pfx
id_rsa
id_ed25519
credentials.json
service-account.json
```

Never log:

```text
Database passwords
Connection strings with credentials
User tokens
Session cookies
Private keys
```

Raw SQL execution must be treated as the most sensitive part of the system.

## Code Quality Rules

* Keep functions focused.
* Prefer explicit names.
* Avoid hidden global state.
* Avoid broad exception handlers.
* Use typed Pydantic models for API boundaries.
* Keep SQL execution isolated in a service layer.
* Add tests for changed behavior.
* Do not introduce new dependencies unless justified.

## Git Rules

Before editing:

```bash
git status
```

After editing:

```bash
git diff
```

Do not overwrite unrelated user changes.

Do not run destructive commands unless explicitly requested:

```bash
git reset --hard
git clean -fd
git checkout -- .
```

## Agent Completion Format

When reporting work, use:

```text
Summary:
- ...

Files changed:
- ...

Validation:
- ...

Notes:
- ...
```

If validation was not run, say exactly why.

## Local Verification Checklist

```text
[ ] App starts successfully
[ ] http://localhost:8000/ loads
[ ] Backend health endpoint responds
[ ] SQL query endpoint works
[ ] Non-spatial query renders table
[ ] Spatial query renders map
[ ] Invalid SQL shows safe error
[ ] Query timeout works
[ ] Row limit works
[ ] Playwright tests pass
[ ] No secrets committed
[ ] No unrelated files changed
```

