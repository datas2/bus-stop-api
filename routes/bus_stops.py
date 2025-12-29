from fastapi import APIRouter, Query
from controllers import bus_stop_controller as ctrl

router = APIRouter(prefix="/stops", tags=["stops"])


@router.get("/")
def list_stops(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    name: str | None = Query(None, description="Partial STOP_NAME filter"),
):
    """
    GET /stops
    - List bus stops (paginated)
    - Optional name filter (partial match on STOP_NAME)
    """
    return ctrl.list_stops(limit=limit, offset=offset, name=name)


@router.get("/code/{stop_code}")
def get_stop_by_code(stop_code: int):
    """
    GET /code/{stop_code}
    - Get full details of a bus stop by STOP_CODE.
    """
    return ctrl.get_stop_by_code(stop_code)


@router.get("/nearby/by-name")
def nearby_by_name(
    stop_name: str = Query(..., description="Partial or full STOP_NAME"),
    radius_m: float = Query(100.0, ge=0),
    limit: int = Query(20, ge=1, le=200),
):
    """
    GET /stops/nearby/by-name
    - Given a STOP_NAME, find its coordinates and return nearby stops within a radius (meters).
    """
    return ctrl.get_nearby_by_name(stop_name=stop_name, radius_m=radius_m, limit=limit)


@router.get("/nearby/by-coords")
def nearby_by_coords(
    lat: float = Query(..., description="Latitude in degrees"),
    lon: float = Query(..., description="Longitude in degrees"),
    radius_m: float = Query(100.0, ge=0),
    limit: int = Query(20, ge=1, le=200),
):
    """
    GET /stops/nearby/by-coords
    - Given coordinates (lat, lon), return nearby stops within a radius (meters).
    """
    return ctrl.get_nearby_by_coords(lat=lat, lon=lon, radius_m=radius_m, limit=limit)