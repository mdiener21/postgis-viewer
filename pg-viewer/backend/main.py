import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
import json
import geojson
from typing import List, Dict, Any, Optional

app = FastAPI()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@db:5432/postgis_db")
engine = create_async_engine(DATABASE_URL)

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

            # Detect geometry columns and their SRIDs
            # We can use a trick: SELECT ST_SRID(col) FROM (user_query) LIMIT 1
            geometry_info = {}
            for col in columns:
                try:
                    srid_query = f"SELECT ST_SRID(\"{col}\") FROM ({clean_sql}) AS sub WHERE \"{col}\" IS NOT NULL LIMIT 1"
                    srid_result = await conn.execute(text(srid_query))
                    srid_row = srid_result.fetchone()
                    if srid_row is not None:
                        geometry_info[col] = srid_row[0]
                except Exception:
                    # Not a geometry column or other error
                    pass

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
            # We need to find the geometry column first.
            # If there are multiple, we'll pick the first one for now or let the user choose?
            # User said "if column with geometry in query we want a button to click to display all the geometry"
            # Let's find all geom columns.
            
            # First, get columns
            temp_res = await conn.execute(text(f"SELECT * FROM ({clean_sql}) AS sub LIMIT 0"))
            columns = list(temp_res.keys())
            
            geom_col = None
            srid = 0
            for col in columns:
                try:
                    srid_query = f"SELECT ST_SRID(\"{col}\") FROM ({clean_sql}) AS sub WHERE \"{col}\" IS NOT NULL LIMIT 1"
                    srid_result = await conn.execute(text(srid_query))
                    srid_row = srid_result.fetchone()
                    if srid_row is not None:
                        geom_col = col
                        srid = srid_row[0]
                        break # Just pick the first geom column for now
                except:
                    continue
            
            if not geom_col:
                return {"type": "FeatureCollection", "features": [], "srid": 0}

            # Now fetch all data as GeoJSON
            # We'll use ST_AsGeoJSON
            # To include attributes, we can use jsonb_build_object or just fetch and build in Python
            # Building in SQL is often faster for PostGIS
            
            geojson_query = f"""
                SELECT jsonb_build_object(
                    'type', 'FeatureCollection',
                    'features', jsonb_agg(features.feature)
                )
                FROM (
                  SELECT jsonb_build_object(
                    'type', 'Feature',
                    'geometry', ST_AsGeoJSON("{geom_col}")::jsonb,
                    'properties', to_jsonb(inputs) - '{geom_col}'
                  ) AS feature
                  FROM ({clean_sql}) AS inputs
                  WHERE "{geom_col}" IS NOT NULL
                ) features;
            """
            
            result = await conn.execute(text(geojson_query))
            row = result.fetchone()
            data = row[0] if row and row[0] else {"type": "FeatureCollection", "features": []}
            
            return {**data, "srid": srid}
            
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

# Serve static files from the Vue build
if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
