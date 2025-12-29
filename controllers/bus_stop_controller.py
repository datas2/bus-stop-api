from fastapi import Query, HTTPException
from utils.parquet import query_stops

def list_stops(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    name: str | None = Query(None, description="Partial Stop Name filter"),
):
    """
    List bus stops from stops.parquet using DuckDB + SQL.
    Supports optional name filter and pagination.
    """
    base_sql = """
        SELECT
            stop_code,
            UPPER(stop_name) AS stop_name,
            latitude,
            longitude,
            parent_station
        FROM stops
    """
    params: list = []

    # Filter by name (using ILIKE for case-insensitive)
    if name:
        base_sql += " WHERE stop_name ILIKE ?"
        params.append(f"%{name}%")

    # Ordering and pagination
    base_sql += " ORDER BY stop_code LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    stops = query_stops(base_sql, tuple(params))
    return {"count": len(stops), "results": stops}


def get_stop_by_code(stop_code: int | str):
    """
    Get full details of a bus stop by Stop Code.
    """
    sql = """
        SELECT
            stop_code,
            UPPER(stop_name) AS stop_name,
            latitude,
            longitude,
            parent_station,
            x_meters,
            y_meters
        FROM stops
        WHERE stop_code = ?
    """
    if results := query_stops(sql, (stop_code,)):
        # If there are duplicates, we return all; if you want just one, use results[0]
        return {"count": len(results), "results": results}
    else:
        raise HTTPException(status_code=404, detail=f"Stop Code {stop_code} not found")


def get_nearby_by_name(
    stop_name: str,
    radius_m: float = 100.0,
    limit: int = 20,
):
    """
    Given a stop_name, find its coordinates and then return nearby stops within a radius (in meters).
    Uses Haversine distance (approx) computed in DuckDB SQL.
    """
    # 1. Get reference stop (we take the first match)
    ref_sql = """
        SELECT
            stop_code,
            UPPER(stop_name) AS stop_name,
            latitude AS stop_lat,
            longitude AS stop_lon
        FROM stops
        WHERE UPPER(stop_name) ILIKE ?
        ORDER BY stop_code
        LIMIT 1
    """
    ref_results = query_stops(ref_sql, (f"%{stop_name.upper()}%",))
    if not ref_results:
        raise HTTPException(status_code=404, detail=f"No stop found with name like '{stop_name}'")

    ref = ref_results[0]
    ref_lat = ref["stop_lat"]
    ref_lon = ref["stop_lon"]

    # 2. Query nearby stops using Haversine in SQL
    # DuckDB: acos/sin/cos expect radians; we approximate or convert using radians().
    nearby_sql = """
        SELECT
            s.stop_code,
            UPPER(s.stop_name) AS stop_name,
            s.latitude,
            s.longitude,
            s.parent_station,
            2 * 6371000 * ASIN(
                SQRT(
                    POWER(SIN(RADIANS(s.latitude - ?) / 2), 2) +
                    COS(RADIANS(?)) * COS(RADIANS(s.latitude)) *
                    POWER(SIN(RADIANS(s.longitude - ?) / 2), 2)
                )
            ) AS distance_m
        FROM stops AS s
        ORDER BY distance_m
        LIMIT ?
    """
    params = (ref_lat, ref_lat, ref_lon, limit)
    nearby = query_stops(nearby_sql, params)

    # Optionally filter by radius
    nearby = [st for st in nearby if st["distance_m"] <= radius_m]

    return {
        "reference_stop": ref,
        "radius_m": radius_m,
        "count": len(nearby),
        "results": nearby,
    }


def get_nearby_by_coords(
    lat: float,
    lon: float,
    radius_m: float = 100.0,
    limit: int = 20,
):
    """
    Given coordinates (lat, lon), return nearby stops within a radius (in meters).
    Uses Haversine distance computed in DuckDB SQL.
    """
    sql = """
        SELECT
            s.stop_code,
            UPPER(s.stop_name) AS stop_name,
            s.latitude,
            s.longitude,
            s.parent_station,
            2 * 6371000 * ASIN(
                SQRT(
                    POWER(SIN(RADIANS(s.latitude - ?) / 2), 2) +
                    COS(RADIANS(?)) * COS(RADIANS(s.latitude)) *
                    POWER(SIN(RADIANS(s.longitude - ?) / 2), 2)
                )
            ) AS distance_m
        FROM stops AS s
        ORDER BY distance_m
        LIMIT ?
    """
    params = (lat, lat, lon, limit)
    nearby = query_stops(sql, params)

    nearby = [st for st in nearby if st["distance_m"] <= radius_m]

    return {
        "reference_coords": {"latitude": lat, "longitude": lon},
        "radius_m": radius_m,
        "count": len(nearby),
        "results": nearby,
    }