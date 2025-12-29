import json
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from utils.parquet import query_stops


@pytest.fixture
def tmp_parquet_file(tmp_path, monkeypatch):
    """
    Fixture to create a temporary Parquet file and patch STOPS_PARQUET_PATH
    so query_stops reads from it.
    """
    # Arrange
    df = pd.DataFrame(
        [
            {"stop_code": 1001, "stop_name": "STOP A", "latitude": -36.84, "longitude": 174.76},
            {"stop_code": 1002, "stop_name": "STOP B", "latitude": -36.85, "longitude": 174.77},
            {"stop_code": 1003, "stop_name": "STOP C", "latitude": -36.86, "longitude": 174.78},
        ]
    )
    parquet_path = tmp_path / "stops.parquet"
    df.to_parquet(parquet_path)

    # Patch STOPS_PARQUET_PATH used by query_stops
    import utils.parquet as parquet_module

    monkeypatch.setattr(parquet_module, "STOPS_PARQUET_PATH", parquet_path)
    return parquet_path


@pytest.mark.parametrize(
    "sql, params, expected_len, description",
    [
        pytest.param(
            "SELECT * FROM stops ORDER BY stop_code",
            None,
            3,
            "select-all-no-params",
            id="select-all-no-params",
        ),
        pytest.param(
            "SELECT * FROM stops WHERE stop_code > ? ORDER BY stop_code",
            (1001,),
            2,
            "select-with-param-greater-than",
            id="select-with-param-greater-than",
        ),
        pytest.param(
            "SELECT stop_code, stop_name FROM stops WHERE stop_name LIKE ? ORDER BY stop_code",
            ("STOP B%",),
            1,
            "select-like-on-stop-name",
            id="select-like-on-stop-name",
        ),
    ],
)
def test_query_stops_happy_path(tmp_parquet_file, sql, params, expected_len, description):

    # Act
    if params is None:
        result = query_stops(sql)
    else:
        result = query_stops(sql, params)

    # Assert
    assert isinstance(result, list)
    assert len(result) == expected_len
    for row in result:
        assert isinstance(row, dict)
        # ensure serializable as JSON (like FastAPI would do)
        json.dumps(row)


def test_query_stops_file_not_found(monkeypatch, tmp_path):
    """
    Error case: if STOPS_PARQUET_PATH does not exist, FileNotFoundError must be raised.
    """

    # Arrange
    fake_path = tmp_path / "nonexistent.parquet"
    import utils.parquet as parquet_module

    monkeypatch.setattr(parquet_module, "STOPS_PARQUET_PATH", fake_path)

    # Act
    with pytest.raises(FileNotFoundError) as exc_info:
        query_stops("SELECT * FROM stops")

    # Assert
    assert "Parquet file not found" in str(exc_info.value)
    assert str(fake_path) in str(exc_info.value)


@pytest.mark.parametrize(
    "sql, params, expected_exception, case_id",
    [
        pytest.param(
            "SELECT * FROM non_existing_view",
            None,
            duckdb.Error,
            "invalid-view-name",
            id="invalid-view-name",
        ),
        pytest.param(
            "SELEC * FROM stops",  # typo in SELECT
            None,
            duckdb.Error,
            "syntax-error",
            id="syntax-error",
        ),
    ],
)
def test_query_stops_duckdb_errors(tmp_parquet_file, sql, params, expected_exception, case_id):

    # Act
    with pytest.raises(expected_exception):

        query_stops(sql, params)


def test_query_stops_parameterized_edge_case_no_results(tmp_parquet_file):
    """
    Edge case: parameterized query that returns no rows should return an empty list.
    """

    # Arrange
    sql = "SELECT * FROM stops WHERE stop_code < ?"
    params = (0,)

    # Act
    result = query_stops(sql, params)

    # Assert
    assert isinstance(result, list)
    assert result == []


def test_query_stops_multiple_calls_reuse_parquet(tmp_parquet_file):
    """
    Edge case: multiple sequential calls should work fine,
    ensuring connections are closed and recreated each time.
    """

    # Arrange
    sql_all = "SELECT * FROM stops"
    sql_filtered = "SELECT * FROM stops WHERE stop_code = ?"

    # Act
    result1 = query_stops(sql_all)
    result2 = query_stops(sql_filtered, (1002,))
    result3 = query_stops(sql_filtered, (9999,))  # no match

    # Assert
    assert len(result1) == 3
    assert len(result2) == 1
    assert result2[0]["stop_code"] == 1002
    assert result3 == []
