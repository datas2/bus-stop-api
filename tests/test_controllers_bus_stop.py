# tests/controllers/test_bus_stop_controller_list_stops.py

import pytest
from fastapi import HTTPException

from controllers.bus_stop_controller import list_stops, get_stop_by_code, get_nearby_by_name, get_nearby_by_coords


@pytest.mark.parametrize(
    "limit, offset, name, fake_results",
    [
        pytest.param(
            50,
            0,
            None,
            [{"stop_code": 1}, {"stop_code": 2}],
            id="no-name-filter-first-page",
        ),
        pytest.param(
            10,
            10,
            "ALBERT",
            [{"stop_code": 11}, {"stop_code": 12}],
            id="with-name-filter-second-page",
        ),
        pytest.param(
            5,
            0,
            "central",
            [],
            id="with-name-filter-no-results",
        ),
    ],
)
def test_list_stops_happy_path(monkeypatch, limit, offset, name, fake_results):
    """Happy path: query_stops is called with expected SQL and params, and result is wrapped correctly."""

    # Arrange
    called = {}

    def fake_query_stops(sql, params):
        # capture for assertions
        called["sql"] = sql
        called["params"] = params
        return fake_results

    monkeypatch.setattr("controllers.bus_stop_controller.query_stops", fake_query_stops)

    # Act
    response = list_stops(limit=limit, offset=offset, name=name)

    # Assert
    assert response["count"] == len(fake_results)
    assert response["results"] == fake_results

    sql = called["sql"]
    params = called["params"]

    # common SQL parts
    assert "SELECT" in sql
    assert "FROM stops" in sql
    assert "ORDER BY stop_code" in sql
    assert "LIMIT ?" in sql
    assert "OFFSET ?" in sql

    if name:
        # when name is provided, expect WHERE with ILIKE and a LIKE param
        assert "WHERE stop_name ILIKE ?" in sql
        assert params[0] == f"%{name}%"
        assert params[1] == limit
        assert params[2] == offset
    else:
        # when name is None/empty, no WHERE clause and only limit/offset params
        assert "WHERE stop_name ILIKE ?" not in sql
        assert params[0] == limit
        assert params[1] == offset


@pytest.mark.parametrize(
    "name, expect_where",
    [
        pytest.param(None, False, id="name-none-no-where"),
        pytest.param("", False, id="empty-string-no-where"),
        pytest.param(" ", True, id="space-string-with-where"),
    ],
)
def test_list_stops_edge_cases_name_filter(monkeypatch, name, expect_where):
    """Edge cases around the 'name' filter and truthiness."""

    # Arrange
    captured = {}

    def fake_query_stops(sql, params):
        captured["sql"] = sql
        captured["params"] = params
        return []

    monkeypatch.setattr("controllers.bus_stop_controller.query_stops", fake_query_stops)

    # Act
    response = list_stops(limit=5, offset=2, name=name)

    # Assert
    assert response["count"] == 0
    assert response["results"] == []

    sql = captured["sql"]
    params = captured["params"]

    if expect_where:
        assert "WHERE stop_name ILIKE ?" in sql
        assert params[0] == f"%{name}%"
        assert params[1] == 5
        assert params[2] == 2
    else:
        assert "WHERE stop_name ILIKE ?" not in sql
        assert params[0] == 5
        assert params[1] == 2


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(RuntimeError("duckdb failure"), id="runtime-error-from-query"),
        pytest.param(Exception("generic error"), id="generic-exception-from-query"),
    ],
)
def test_list_stops_error_cases_bubbles_up(monkeypatch, exception):
    """
    Error cases: if query_stops raises an exception, list_stops should not swallow it.
    """

    # Arrange
    def fake_query_stops(sql, params):
        raise exception

    monkeypatch.setattr("controllers.bus_stop_controller.query_stops", fake_query_stops)

    # Act
    with pytest.raises(type(exception)) as exc_info:
        list_stops(limit=10, offset=0, name="X")

    # Assert
    assert exc_info.value is exception

@pytest.mark.parametrize(
    "stop_code, fake_results",
    [
        pytest.param(
            1001,
            [
                {
                    "stop_code": 1001,
                    "stop_name": "STOP A",
                    "latitude": -36.84,
                    "longitude": 174.76,
                    "parent_station": None,
                    "x_meters": 1.0,
                    "y_meters": 2.0,
                }
            ],
            id="single-result-int-code",
        ),
        pytest.param(
            "1002",
            [
                {
                    "stop_code": 1002,
                    "stop_name": "STOP B",
                    "latitude": -36.85,
                    "longitude": 174.77,
                    "parent_station": "P1",
                    "x_meters": 3.0,
                    "y_meters": 4.0,
                },
                {
                    "stop_code": 1002,
                    "stop_name": "STOP B DUP",
                    "latitude": -36.851,
                    "longitude": 174.771,
                    "parent_station": "P2",
                    "x_meters": 5.0,
                    "y_meters": 6.0,
                },
            ],
            id="multiple-results-str-code",
        ),
    ],
)
def test_get_stop_by_code_happy_path(monkeypatch, stop_code, fake_results):
    """Happy path: query_stops returns one or more rows and they are wrapped correctly."""

    # Arrange
    captured = {}

    def fake_query_stops(sql, params):
        captured["sql"] = sql
        captured["params"] = params
        return fake_results

    monkeypatch.setattr(
        "controllers.bus_stop_controller.query_stops",
        fake_query_stops,
    )

    # Act
    response = get_stop_by_code(stop_code)

    # Assert
    # Basic shape
    assert response["count"] == len(fake_results)
    assert response["results"] == fake_results

    # SQL and params
    sql = captured["sql"]
    params = captured["params"]

    assert "SELECT" in sql
    assert "FROM stops" in sql
    assert "WHERE stop_code = ?" in sql
    assert params == (stop_code,)


@pytest.mark.parametrize(
    "stop_code",
    [
        pytest.param(9999, id="int-code-not-found"),
        pytest.param("NO_SUCH_CODE", id="str-code-not-found"),
    ],
)
def test_get_stop_by_code_not_found(monkeypatch, stop_code):
    """Edge/error case: query_stops returns an empty list and HTTPException 404 is raised."""

    # Arrange
    def fake_query_stops(sql, params):
        return []

    monkeypatch.setattr(
        "controllers.bus_stop_controller.query_stops",
        fake_query_stops,
    )

    # Act
    with pytest.raises(HTTPException) as exc_info:
        get_stop_by_code(stop_code)

    # Assert
    exc = exc_info.value
    assert exc.status_code == 404
    assert exc.detail == f"Stop Code {stop_code} not found"


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(RuntimeError("duckdb failure"), id="runtime-error-from-query"),
        pytest.param(Exception("generic failure"), id="generic-exception-from-query"),
    ],
)
def test_get_stop_by_code_error_from_query_stops(monkeypatch, exception):
    """
    Error cases: if query_stops itself raises any exception, it should bubble up unchanged.
    """

    # Arrange
    def fake_query_stops(sql, params):
        raise exception

    monkeypatch.setattr(
        "controllers.bus_stop_controller.query_stops",
        fake_query_stops,
    )

    # Act
    with pytest.raises(type(exception)) as exc_info:
        get_stop_by_code(1234)

    # Assert
    assert exc_info.value is exception

@pytest.mark.parametrize(
    "stop_name,radius_m,limit,ref_result,nearby_results,expected_count,case_id",
    [
        pytest.param(
            "Albert",
            100.0,
            20,
            # reference stop
            [
                {
                    "stop_code": 1001,
                    "stop_name": "STOP ALBERT",
                    "stop_lat": -36.84,
                    "stop_lon": 174.76,
                }
            ],
            # nearby stops: two inside radius, one outside
            [
                {
                    "stop_code": 1001,
                    "stop_name": "STOP ALBERT",
                    "latitude": -36.84,
                    "longitude": 174.76,
                    "parent_station": None,
                    "distance_m": 0.0,
                },
                {
                    "stop_code": 1002,
                    "stop_name": "STOP B",
                    "latitude": -36.8405,
                    "longitude": 174.7605,
                    "parent_station": "P1",
                    "distance_m": 50.0,
                },
                {
                    "stop_code": 1003,
                    "stop_name": "STOP C FAR",
                    "latitude": -36.85,
                    "longitude": 174.77,
                    "parent_station": "P2",
                    "distance_m": 200.0,
                },
            ],
            2,
            "default-radius-filters-far-stops",
            id="default-radius-filters-far-stops",
        ),
        pytest.param(
            "central",
            10.0,
            5,
            [
                {
                    "stop_code": 2001,
                    "stop_name": "STOP CENTRAL",
                    "stop_lat": -36.85,
                    "stop_lon": 174.77,
                }
            ],
            [
                {
                    "stop_code": 2001,
                    "stop_name": "STOP CENTRAL",
                    "latitude": -36.85,
                    "longitude": 174.77,
                    "parent_station": None,
                    "distance_m": 0.0,
                },
                {
                    "stop_code": 2002,
                    "stop_name": "STOP CENTRAL 2",
                    "latitude": -36.8501,
                    "longitude": 174.7701,
                    "parent_station": None,
                    "distance_m": 9.9,
                },
            ],
            2,
            "small-radius-includes-only-very-close",
            id="small-radius-includes-only-very-close",
        ),
        pytest.param(
            "AllStops",
            1000.0,
            10,
            [
                {
                    "stop_code": 3001,
                    "stop_name": "STOP ALL",
                    "stop_lat": -36.86,
                    "stop_lon": 174.78,
                }
            ],
            [
                {
                    "stop_code": 3001,
                    "stop_name": "STOP ALL",
                    "latitude": -36.86,
                    "longitude": 174.78,
                    "parent_station": None,
                    "distance_m": 10.0,
                },
                {
                    "stop_code": 3002,
                    "stop_name": "STOP ALL 2",
                    "latitude": -36.861,
                    "longitude": 174.781,
                    "parent_station": "PX",
                    "distance_m": 500.0,
                },
            ],
            2,
            "large-radius-no-filtering",
            id="large-radius-no-filtering",
        ),
    ],
)
def test_get_nearby_by_name_happy_path(
    monkeypatch,
    stop_name,
    radius_m,
    limit,
    ref_result,
    nearby_results,
    expected_count,
    case_id,
):
    """Happy path: reference stop is found, nearby stops are returned and filtered by radius."""

    # Arrange
    calls = {"ref": [], "nearby": []}

    def fake_query_stops(sql, params):
        if "LIMIT 1" in sql:
            calls["ref"].append((sql, params))
            return ref_result
        else:
            calls["nearby"].append((sql, params))
            return nearby_results

    monkeypatch.setattr(
        "controllers.bus_stop_controller.query_stops",
        fake_query_stops,
    )

    # Act
    response = get_nearby_by_name(stop_name=stop_name, radius_m=radius_m, limit=limit)

    # Assert
    # Reference stop call
    assert len(calls["ref"]) == 1
    ref_sql, ref_params = calls["ref"][0]
    assert "FROM stops" in ref_sql
    assert "WHERE UPPER(stop_name) ILIKE ?" in ref_sql
    assert "LIMIT 1" in ref_sql
    assert ref_params == (f"%{stop_name.upper()}%",)

    # Nearby call
    assert len(calls["nearby"]) == 1
    nearby_sql, nearby_params = calls["nearby"][0]
    assert "FROM stops AS s" in nearby_sql
    assert "distance_m" in nearby_sql
    assert "LIMIT ?" in nearby_sql

    # nearby_params = (ref_lat, ref_lat, ref_lon, limit)
    ref = ref_result[0]
    assert nearby_params[0] == ref["stop_lat"]
    assert nearby_params[1] == ref["stop_lat"]
    assert nearby_params[2] == ref["stop_lon"]
    assert nearby_params[3] == limit

    # Response structure
    assert response["reference_stop"] == ref
    assert response["radius_m"] == radius_m
    assert response["count"] == expected_count
    # All results must respect the radius filter
    for st in response["results"]:
        assert st["distance_m"] <= radius_m


@pytest.mark.parametrize(
    "stop_name, ref_results",
    [
        pytest.param("Unknown", [], id="no-reference-stop-found"),
        pytest.param("Empty", None, id="reference-query-returns-none"),
    ],
)
def test_get_nearby_by_name_not_found(monkeypatch, stop_name, ref_results):
    """Error/edge case: if no reference stop is found, HTTPException 404 must be raised."""

    # Arrange
    def fake_query_stops(sql, params):
        if "LIMIT 1" in sql:
            # emulate query_stops possibly returning None or empty list
            return ref_results
        return []  # shouldn't be reached

    monkeypatch.setattr(
        "controllers.bus_stop_controller.query_stops",
        fake_query_stops,
    )

    # Act
    with pytest.raises(HTTPException) as exc_info:
        get_nearby_by_name(stop_name=stop_name, radius_m=100.0, limit=20)

    # Assert
    exc = exc_info.value
    assert exc.status_code == 404
    assert exc.detail == f"No stop found with name like '{stop_name}'"


@pytest.mark.parametrize(
    "radius_m, nearby_results, expected_count, case_id",
    [
        pytest.param(
            0.0,
            [
                {"stop_code": 1, "stop_name": "STOP A", "distance_m": 0.0},
                {"stop_code": 2, "stop_name": "STOP B", "distance_m": 1.0},
            ],
            1,
            "radius-zero-only-exact-match",
            id="radius-zero-only-exact-match",
        ),
        pytest.param(
            -10.0,
            [
                {"stop_code": 1, "stop_name": "STOP A", "distance_m": 0.0},
                {"stop_code": 2, "stop_name": "STOP B", "distance_m": 1.0},
            ],
            0,
            "negative-radius-no-results",
            id="negative-radius-no-results",
        ),
    ],
)
def test_get_nearby_by_name_edge_radius_filter(
    monkeypatch, radius_m, nearby_results, expected_count, case_id
):
    """Edge cases around radius filtering (0, negative)."""

    # Arrange
    ref_result = [
        {
            "stop_code": 999,
            "stop_name": "STOP REF",
            "stop_lat": -36.80,
            "stop_lon": 174.70,
        }
    ]
    calls = {"ref": [], "nearby": []}

    def fake_query_stops(sql, params):
        if "LIMIT 1" in sql:
            calls["ref"].append((sql, params))
            return ref_result
        calls["nearby"].append((sql, params))
        return nearby_results

    monkeypatch.setattr(
        "controllers.bus_stop_controller.query_stops",
        fake_query_stops,
    )

    # Act
    response = get_nearby_by_name(stop_name="Ref", radius_m=radius_m, limit=10)

    # Assert
    assert response["radius_m"] == radius_m
    assert response["count"] == expected_count
    assert len(response["results"]) == expected_count
    # All results must satisfy the radius condition
    for st in response["results"]:
        assert st["distance_m"] <= radius_m


@pytest.mark.parametrize(
    "which_call_fails, exception",
    [
        pytest.param("ref", RuntimeError("ref query failed"), id="ref-query-fails"),
        pytest.param("nearby", RuntimeError("nearby query failed"), id="nearby-query-fails"),
    ],
)
def test_get_nearby_by_name_error_propagation(monkeypatch, which_call_fails, exception):
    """
    Error cases: if query_stops raises an exception (either for ref or nearby query),
    it should bubble up unchanged.
    """

    # Arrange
    ref_result = [
        {
            "stop_code": 5000,
            "stop_name": "STOP REF",
            "stop_lat": -36.80,
            "stop_lon": 174.70,
        }
    ]

    def fake_query_stops(sql, params):
        if "LIMIT 1" in sql:  # ref query
            if which_call_fails == "ref":
                raise exception
            return ref_result
        # nearby query
        if which_call_fails == "nearby":
            raise exception
        return []

    monkeypatch.setattr(
        "controllers.bus_stop_controller.query_stops",
        fake_query_stops,
    )

    # Act
    with pytest.raises(type(exception)) as exc_info:
        get_nearby_by_name(stop_name="Ref", radius_m=100.0, limit=10)

    # Assert
    assert exc_info.value is exception

@pytest.mark.parametrize(
    "lat, lon, radius_m, limit, nearby_results, expected_count, case_id",
    [
        pytest.param(
            -36.84,
            174.76,
            100.0,
            20,
            [
                {
                    "stop_code": 1001,
                    "stop_name": "STOP A",
                    "latitude": -36.84,
                    "longitude": 174.76,
                    "parent_station": None,
                    "distance_m": 0.0,
                },
                {
                    "stop_code": 1002,
                    "stop_name": "STOP B",
                    "latitude": -36.8405,
                    "longitude": 174.7605,
                    "parent_station": "P1",
                    "distance_m": 50.0,
                },
                {
                    "stop_code": 1003,
                    "stop_name": "STOP C FAR",
                    "latitude": -36.85,
                    "longitude": 174.77,
                    "parent_station": "P2",
                    "distance_m": 150.0,
                },
            ],
            2,
            "default-radius-filters-far-stops",
            id="default-radius-filters-far-stops",
        ),
        pytest.param(
            -36.85,
            174.77,
            10.0,
            5,
            [
                {
                    "stop_code": 2001,
                    "stop_name": "STOP CENTRAL",
                    "latitude": -36.85,
                    "longitude": 174.77,
                    "parent_station": None,
                    "distance_m": 0.0,
                },
                {
                    "stop_code": 2002,
                    "stop_name": "STOP CENTRAL 2",
                    "latitude": -36.8501,
                    "longitude": 174.7701,
                    "parent_station": None,
                    "distance_m": 9.9,
                },
                {
                    "stop_code": 2003,
                    "stop_name": "STOP CENTRAL 3",
                    "latitude": -36.851,
                    "longitude": 174.771,
                    "parent_station": None,
                    "distance_m": 20.0,
                },
            ],
            2,
            "small-radius-includes-only-very-close",
            id="small-radius-includes-only-very-close",
        ),
        pytest.param(
            -36.86,
            174.78,
            1000.0,
            10,
            [
                {
                    "stop_code": 3001,
                    "stop_name": "STOP ALL",
                    "latitude": -36.86,
                    "longitude": 174.78,
                    "parent_station": None,
                    "distance_m": 10.0,
                },
                {
                    "stop_code": 3002,
                    "stop_name": "STOP ALL 2",
                    "latitude": -36.861,
                    "longitude": 174.781,
                    "parent_station": "PX",
                    "distance_m": 500.0,
                },
            ],
            2,
            "large-radius-no-filtering",
            id="large-radius-no-filtering",
        ),
    ],
)
def test_get_nearby_by_coords_happy_path(
    monkeypatch,
    lat,
    lon,
    radius_m,
    limit,
    nearby_results,
    expected_count,
    case_id,
):
    """Happy path: query_stops returns nearby stops, which are filtered by radius."""

    # Arrange
    captured = {}

    def fake_query_stops(sql, params):
        captured["sql"] = sql
        captured["params"] = params
        return nearby_results

    monkeypatch.setattr(
        "controllers.bus_stop_controller.query_stops",
        fake_query_stops,
    )

    # Act
    response = get_nearby_by_coords(lat=lat, lon=lon, radius_m=radius_m, limit=limit)

    # Assert
    # SQL and params
    sql = captured["sql"]
    params = captured["params"]

    assert "FROM stops AS s" in sql
    assert "distance_m" in sql
    assert "LIMIT ?" in sql
    # params = (lat, lat, lon, limit)
    assert params == (lat, lat, lon, limit)

    # Response structure
    assert response["reference_coords"] == {"latitude": lat, "longitude": lon}
    assert response["radius_m"] == radius_m
    assert response["count"] == expected_count
    assert len(response["results"]) == expected_count
    # All returned stops must satisfy the radius condition
    for st in response["results"]:
        assert st["distance_m"] <= radius_m


@pytest.mark.parametrize(
    "radius_m, nearby_results, expected_count, case_id",
    [
        pytest.param(
            0.0,
            [
                {"stop_code": 1, "stop_name": "STOP A", "distance_m": 0.0},
                {"stop_code": 2, "stop_name": "STOP B", "distance_m": 0.1},
            ],
            1,
            "radius-zero-only-distance-zero",
            id="radius-zero-only-distance-zero",
        ),
        pytest.param(
            -10.0,
            [
                {"stop_code": 1, "stop_name": "STOP A", "distance_m": 0.0},
                {"stop_code": 2, "stop_name": "STOP B", "distance_m": 1.0},
            ],
            0,
            "negative-radius-no-results",
            id="negative-radius-no-results",
        ),
        pytest.param(
            50.0,
            [],
            0,
            "no-nearby-stops-empty-input",
            id="no-nearby-stops-empty-input",
        ),
    ],
)
def test_get_nearby_by_coords_edge_radius_and_empty(
    monkeypatch, radius_m, nearby_results, expected_count, case_id
):
    """Edge cases: radius zero/negative and no results from query_stops."""

    # Arrange
    lat = -36.80
    lon = 174.70

    def fake_query_stops(sql, params):
        return nearby_results

    monkeypatch.setattr(
        "controllers.bus_stop_controller.query_stops",
        fake_query_stops,
    )

    # Act
    response = get_nearby_by_coords(lat=lat, lon=lon, radius_m=radius_m, limit=10)

    # Assert
    assert response["radius_m"] == radius_m
    assert response["count"] == expected_count
    assert len(response["results"]) == expected_count
    for st in response["results"]:
        assert st["distance_m"] <= radius_m


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(RuntimeError("duckdb failure"), id="runtime-error-from-query"),
        pytest.param(Exception("generic failure"), id="generic-exception-from-query"),
    ],
)
def test_get_nearby_by_coords_error_propagation(monkeypatch, exception):
    """
    Error cases: if query_stops raises any exception, it should bubble up unchanged.
    """

    # Arrange
    def fake_query_stops(sql, params):
        raise exception

    monkeypatch.setattr(
        "controllers.bus_stop_controller.query_stops",
        fake_query_stops,
    )

    # Act
    with pytest.raises(type(exception)) as exc_info:
        get_nearby_by_coords(lat=-36.84, lon=174.76, radius_m=100.0, limit=20)

    # Assert
    assert exc_info.value is exception