import time

import pytest

import utils.rate_limit as rate_limit_module
from utils.rate_limit import rate_limiter


def _reset_requests():
    """Helper to clear REQUESTS between tests."""
    rate_limit_module.REQUESTS.clear()


@pytest.mark.parametrize(
    "client_id, calls, expected_last_result",
    [
        pytest.param("client-a", 1, True, id="single-call-allowed"),
        pytest.param("client-b", 5, True, id="multiple-calls-under-limit"),
    ],
)
def test_rate_limiter_happy_path(client_id, calls, expected_last_result, monkeypatch):

    # Arrange
    _reset_requests()
    # Use real time, but keep limit relatively high so we don't hit it
    monkeypatch.setattr(rate_limit_module, "MAX_REQUESTS", 100)
    monkeypatch.setattr(rate_limit_module, "WINDOW_SECONDS", 60)

    last_result = None

    # Act
    for _ in range(calls):
        last_result = rate_limiter(client_id)

    # Assert
    assert last_result is expected_last_result
    assert len(rate_limit_module.REQUESTS[client_id]) == calls


def test_rate_limiter_hits_limit(monkeypatch):

    # Arrange
    _reset_requests()
    client_id = "client-limit"
    # Simplify scenario: allow only 3 requests in window
    monkeypatch.setattr(rate_limit_module, "MAX_REQUESTS", 3)
    monkeypatch.setattr(rate_limit_module, "WINDOW_SECONDS", 60)

    # Act
    results = [rate_limiter(client_id) for _ in range(4)]

    # Assert
    # First 3 are allowed, 4th is blocked
    assert results == [True, True, True, False]
    assert len(rate_limit_module.REQUESTS[client_id]) == 3


def test_rate_limiter_window_expiration(monkeypatch):

    # Arrange
    _reset_requests()
    client_id = "client-window"
    monkeypatch.setattr(rate_limit_module, "MAX_REQUESTS", 2)
    monkeypatch.setattr(rate_limit_module, "WINDOW_SECONDS", 10)

    base_time = 1_000_000.0

    # First two calls: both within the same window
    monkeypatch.setattr(rate_limit_module.time, "time", lambda: base_time)
    first = rate_limiter(client_id)
    second = rate_limiter(client_id)

    # Move beyond window: old timestamps should be purged
    monkeypatch.setattr(
        rate_limit_module.time, "time", lambda: base_time + 11
    )
    third = rate_limiter(client_id)

    # Act done above, just ensure results

    # Assert
    assert first is True
    assert second is True
    # After 11 seconds, previous timestamps should be out of the window
    assert third is True
    assert len(rate_limit_module.REQUESTS[client_id]) == 1
    assert rate_limit_module.REQUESTS[client_id][0] == base_time + 11


@pytest.mark.parametrize(
    "initial_timestamps, now_offset, expected_allowed, case_id",
    [
        pytest.param([], 0, True, "no-history-new-client", id="no-history-new-client"),
        pytest.param(
            [0.0, 1.0],
            2.0,
            False,
            "at-limit-no-expiration",
            id="at-limit-no-expiration",
        ),
        pytest.param(
            [0.0, 1.0],
            12.0,
            True,
            "all-expired-then-allowed",
            id="all-expired-then-allowed",
        ),
    ],
)
def test_rate_limiter_edge_cases_with_manual_requests(
    monkeypatch, initial_timestamps, now_offset, expected_allowed, case_id
):
    """
    Edge cases:
    - No history for a client_id.
    - History exactly at MAX_REQUESTS.
    - History expired by WINDOW_SECONDS.
    """

    # Arrange
    _reset_requests()
    client_id = "edge-client"
    monkeypatch.setattr(rate_limit_module, "MAX_REQUESTS", 2)
    monkeypatch.setattr(rate_limit_module, "WINDOW_SECONDS", 10)

    base_time = 1_000_000.0
    rate_limit_module.REQUESTS[client_id] = [base_time + t for t in initial_timestamps]

    monkeypatch.setattr(
        rate_limit_module.time, "time", lambda: base_time + now_offset
    )

    # Act
    result = rate_limiter(client_id)

    # Assert
    assert result is expected_allowed
    if expected_allowed:
        # A new timestamp should be appended
        assert len(rate_limit_module.REQUESTS[client_id]) >= 1
    else:
        # At limit and not expired: length stays the same
        assert len(rate_limit_module.REQUESTS[client_id]) == len(initial_timestamps)
