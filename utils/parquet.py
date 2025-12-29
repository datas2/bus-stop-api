import duckdb
from pathlib import Path

# File path to Parquet file
STOPS_PARQUET_PATH = Path("data/stops.parquet")


def query_stops(sql: str, params: tuple | None = None) -> list[dict]:
    """
    Execute an SQL query against the stops.parquet file using DuckDB.

    Args:
        sql: SQL query string. You can refer to the file as 'stops'.
        params: Optional tuple of parameters for parameterized queries.

    Returns:
        List of dicts, suitable to be returned as JSON in FastAPI.
    """
    if not STOPS_PARQUET_PATH.exists():
        raise FileNotFoundError(f"Parquet file not found at {STOPS_PARQUET_PATH}")

    # Connect in-memory (fast, no .db file created)
    con = duckdb.connect()

    # Register the Parquet as a virtual "table"
    con.execute(f"CREATE VIEW stops AS SELECT * FROM read_parquet('{STOPS_PARQUET_PATH.as_posix()}')")

    # Execute the query
    if params is None:
        result_df = con.execute(sql).df()
    else:
        result_df = con.execute(sql, params).df()

    # Close the connection
    con.close()

    # Return as list of dicts
    return result_df.to_dict(orient="records")