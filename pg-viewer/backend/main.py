import os
import re
import hashlib
import time
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
import json
import geojson
from typing import List, Dict, Any, Optional

app = FastAPI()

# Simple in-memory cache for queries with TTL to prevent memory leaks
class SimpleCache:
    def __init__(self, ttl=3600):
        self.cache = {}
        self.ttl = ttl

    def set(self, key, value):
        self.cache[key] = (value, time.time())

    def get(self, key):
        if key not in self.cache:
            return None
        value, timestamp = self.cache[key]
        if time.time() - timestamp > self.ttl:
            del self.cache[key]
            return None
        return value

    def __contains__(self, key):
        return self.get(key) is not None

    def __getitem__(self, key):
        return self.get(key)

query_cache = SimpleCache()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@db:5432/postgis_db")
engine = create_async_engine(DATABASE_URL)

async def detect_geometry_columns(conn, clean_sql, columns):
    """Return {column_name: srid} for every geometry/geography column in the query.

    Detection is type-based (pg_typeof) rather than error-driven, so it reliably
    finds geometry columns no matter what other (non-spatial) columns are present
    in the result set. Each probe runs in a SAVEPOINT so a failure on one column
    never aborts the surrounding transaction.
    """
    geometry_info = {}
    for col in columns:
        try:
            async with conn.begin_nested():
                type_query = f'SELECT pg_typeof("{col}")::text FROM ({clean_sql}) AS sub LIMIT 1'
                type_result = await conn.execute(text(type_query))
                type_row = type_result.fetchone()
        except Exception:
            continue

        # pg_typeof may return a schema-qualified name (e.g. "public.geometry").
        col_type = type_row[0].lower() if type_row and type_row[0] else ""
        if "geometry" not in col_type and "geography" not in col_type:
            continue

        srid = 0
        try:
            async with conn.begin_nested():
                srid_query = f'SELECT ST_SRID("{col}") FROM ({clean_sql}) AS sub WHERE "{col}" IS NOT NULL LIMIT 1'
                srid_result = await conn.execute(text(srid_query))
                srid_row = srid_result.fetchone()
                if srid_row is not None and srid_row[0] is not None:
                    srid = srid_row[0]
        except Exception:
            pass

        geometry_info[col] = srid

    return geometry_info


class QueryRequest(BaseModel):
    sql: str
    page: int = 1
    page_size: int = 10

@app.post("/api/query")
async def execute_query(request: QueryRequest):
    async with engine.connect() as conn:
        try:
            clean_sql = request.sql.strip().rstrip(';')
            # We wrap the user query to handle pagination
            # Note: This is a simple wrapper, might fail for complex queries with ORDER BY outside or CTEs if not careful.
            # But for version 1, we'll try a simple approach.
            
            # First, let's get the column info and detect geometries
            # We'll run the query with LIMIT 0 to get column metadata if possible, 
            # but asyncpg/sqlalchemy might not give us PostGIS specific types easily without fetching data.
            
            # Let's run the query with the requested limit and offset
            offset = (request.page - 1) * request.page_size
            paginated_sql = f"SELECT * FROM ({clean_sql}) AS user_query LIMIT {request.page_size} OFFSET {offset}"
            
            result = await conn.execute(text(paginated_sql))
            columns = list(result.keys())
            rows = []
            
            geom_cols = []
            
            # To detect geometry and SRID, we can check the first row if it exists
            # or try to use ST_SRID in a separate check.
            
            for row in result:
                row_dict = dict(zip(columns, row))
                processed_row = {}
                for col in columns:
                    val = row_dict[col]
                    # Check if it's a geometry by trying to call ST_AsGeoJSON on it? 
                    # No, let's just convert everything to string if it's not a common type for the table view.
                    # Or better, use ST_AsText for geometry columns in the table view.
                    processed_row[col] = str(val) if val is not None else None
                rows.append(processed_row)

            # Detect geometry columns and their SRIDs (type-based, order-independent)
            geometry_info = await detect_geometry_columns(conn, clean_sql, columns)

            return {
                "columns": columns,
                "rows": rows,
                "geometry_columns": geometry_info,
                "page": request.page,
                "page_size": request.page_size
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

class MapRequest(BaseModel):
    sql: str

@app.post("/api/map-data")
async def get_map_data(request: MapRequest):
    async with engine.connect() as conn:
        try:
            clean_sql = request.sql.strip().rstrip(';')
            
            # First, get columns
            temp_res = await conn.execute(text(f"SELECT * FROM ({clean_sql}) AS sub LIMIT 0"))
            columns = list(temp_res.keys())
            
            geometry_info = await detect_geometry_columns(conn, clean_sql, columns)
            geom_col = next(iter(geometry_info), None)
            srid = geometry_info.get(geom_col, 0) if geom_col else 0
            
            if not geom_col:
                return {"type": "FeatureCollection", "features": [], "srid": 0}

            # Calculate bounds for the entire query to zoom the map correctly
            # We'll return this to the frontend
            # Handle SRID 0 by assuming 4326 for extent if transform fails or SRID is 0
            if srid > 0:
                extent_query = f'SELECT ST_Extent(ST_Transform("{geom_col}", 4326)) FROM ({clean_sql}) AS sub'
            else:
                extent_query = f'SELECT ST_Extent("{geom_col}") FROM ({clean_sql}) AS sub'

            extent_result = await conn.execute(text(extent_query))
            extent_row = extent_result.fetchone()
            bbox = None
            if extent_row and extent_row[0]:
                # extent_row[0] is like "BOX(-122.4 37.7,-122.3 37.8)"
                match = re.match(r"BOX\((.*) (.*),(.*) (.*)\)", extent_row[0])
                if match:
                    bbox = [float(x) for x in match.groups()] # [xmin, ymin, xmax, ymax]

            # Generate a query ID to use for vector tiles
            query_id = hashlib.md5(clean_sql.encode()).hexdigest()
            query_cache.set(query_id, {
                "sql": clean_sql,
                "geom_col": geom_col,
                "srid": srid,
                "columns": [c for c in columns if c != geom_col]
            })

            return {
                "query_id": query_id,
                "srid": srid,
                "bbox": bbox,
                "use_tiles": True
            }
            
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/tiles/{query_id}/{z}/{x}/{y}")
async def get_tile(query_id: str, z: int, x: int, y: int):
    query_info = query_cache.get(query_id)
    if not query_info:
        raise HTTPException(status_code=404, detail="Query not found")

    sql = query_info["sql"]
    geom_col = query_info["geom_col"]
    srid = query_info["srid"]

    async with engine.connect() as conn:
        try:
            # We use ST_AsMVTGeom to transform and clip the geometry to the tile boundary.
            # ST_TileEnvelope(z, x, y) generates the tile boundary in SRID 3857.

            # Handle SRID 0: if SRID is 0, we assume 4326 as a fallback.
            # We use the spatial index if possible by transforming the envelope to the data SRID.
            target_srid = srid if srid > 0 else 4326
            geom_expr = f'"{geom_col}"'
            if srid == 0:
                geom_expr = f'ST_SetSRID("{geom_col}", 4326)'

            # Avoid trailing comma if no other columns
            columns_part = ""
            if query_info["columns"]:
                columns_part = ", " + ", ".join([f'"{c}"' for c in query_info["columns"]])

            mvt_query = f"""
                WITH
                bounds AS (
                  SELECT ST_TileEnvelope(:z, :x, :y) AS geom
                ),
                mvtgeom AS (
                  SELECT
                    ST_AsMVTGeom(
                        ST_Transform({geom_expr}, 3857),
                        bounds.geom,
                        4096, 256, true
                    ) AS mvt_geom,
                    inputs.*
                  FROM ({sql}) AS inputs, bounds
                  WHERE ST_Intersects({geom_expr}, ST_Transform(bounds.geom, {target_srid}))
                )
                SELECT ST_AsMVT(t, 'default') FROM (
                    SELECT mvt_geom AS geom {columns_part}
                    FROM mvtgeom
                ) AS t;
            """
            
            result = await conn.execute(text(mvt_query), {"z": z, "x": x, "y": y})
            row = result.fetchone()
            tile_content = row[0] if row and row[0] is not None else b""
            
            return Response(content=tile_content, media_type="application/x-protobuf")
        except Exception as e:
            print(f"Error generating tile: {e}")
            raise HTTPException(status_code=500, detail=str(e))

# Serve static files from the Vue build
if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
