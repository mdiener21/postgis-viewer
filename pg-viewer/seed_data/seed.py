import asyncio
import os
import asyncpg


def get_dsn():
    """Build an asyncpg DSN from DATABASE_URL, falling back to POSTGRES_* vars."""
    url = os.getenv("DATABASE_URL")
    if url:
        # asyncpg doesn't understand the SQLAlchemy "+asyncpg" driver suffix.
        return url.replace("postgresql+asyncpg://", "postgresql://")
    return (
        f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASS')}"
        f"@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    )


async def seed():
    conn = await asyncpg.connect(get_dsn())
    
    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
        
        await conn.execute("DROP TABLE IF EXISTS sample_points;")
        await conn.execute("""
            CREATE TABLE sample_points (
                id SERIAL PRIMARY KEY,
                name TEXT,
                geom GEOMETRY(Point, 4326)
            );
        """)
        
        # New York coordinates
        await conn.execute("""
            INSERT INTO sample_points (name, geom) VALUES
            ('Empire State Building', ST_SetSRID(ST_Point(-73.9857, 40.7484), 4326)),
            ('Central Park', ST_SetSRID(ST_Point(-73.9654, 40.7829), 4326)),
            ('Statue of Liberty', ST_SetSRID(ST_Point(-74.0445, 40.6892), 4326));
        """)

        await conn.execute("DROP TABLE IF EXISTS local_geoms;")
        await conn.execute("""
            CREATE TABLE local_geoms (
                id SERIAL PRIMARY KEY,
                name TEXT,
                geom GEOMETRY(Polygon, 0)
            );
        """)
        
        await conn.execute("""
            INSERT INTO local_geoms (name, geom) VALUES
            ('Square', ST_GeomFromText('POLYGON((0 0, 10 0, 10 10, 0 10, 0 0))', 0)),
            ('Triangle', ST_GeomFromText('POLYGON((20 20, 30 20, 25 30, 20 20))', 0));
        """)

        print("Seeding completed successfully.")
    finally:
        await conn.close()

if __name__ == "__main__":
    # Wait for DB to be ready
    import time
    time.sleep(5)
    asyncio.run(seed())
