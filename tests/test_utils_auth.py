import os

import pytest
from fastapi import HTTPException
from fastapi import Header
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from utils.auth import require_api_key


@pytest.mark.parametrize(
    "env_value, header_value",
    [
        pytest.param("simple-key", "simple-key", id="match-simple-key"),
        pytest.param("another-SECRET-123", "another-SECRET-123", id="match-secret-like"),
        pytest.param("KEY_WITH_UNDERSCORES_123", "KEY_WITH_UNDERSCORES_123", id="match-underscored"),
        pytest.param("1234567890", "1234567890", id="match-numeric"),
    ],
)
def test_require_api_key_happy_path(monkeypatch, env_value, header_value):

    # Arrange
    monkeypatch.setenv("API_KEY", env_value)
    # Reload to ensure API_KEY is picked up correctly
    from importlib import reload
    import utils.auth as auth_module

    reload(auth_module)

    # Act
    result = auth_module.require_api_key(header_value)

    # Assert
    assert result is None


@pytest.mark.parametrize(
    "env_value, header_value, expected_status, expected_detail",
    [
        pytest.param("correct-key", "wrong-key", 401, "Invalid or missing API Key.", id="mismatch-key"),
        pytest.param("correct-key", "", 401, "Invalid or missing API Key.", id="empty-header"),
        pytest.param("", "anything", 401, "Invalid or missing API Key.", id="empty-env-key"),
        pytest.param(None, "anything", 401, "Invalid or missing API Key.", id="none-env-key"),
    ],
)
def test_require_api_key_invalid(monkeypatch, env_value, header_value, expected_status, expected_detail):

    # Arrange
    if env_value is None:
        monkeypatch.delenv("API_KEY", raising=False)
    else:
        monkeypatch.setenv("API_KEY", env_value)

    from importlib import reload
    import utils.auth as auth_module

    reload(auth_module)

    # Act
    with pytest.raises(HTTPException) as exc_info:
        auth_module.require_api_key(header_value)

    # Assert
    exc = exc_info.value
    assert exc.status_code == expected_status
    assert exc.detail == expected_detail


def test_require_api_key_dependency_with_fastapi_app(monkeypatch):
    """
    Integration-style test using FastAPI to ensure Header dependency works:
    - Missing header triggers RequestValidationError (before our function runs).
    - Invalid header triggers our HTTPException.
    - Valid header passes and endpoint returns payload.
    """

    # Arrange
    monkeypatch.setenv("API_KEY", "integration-key")
    from importlib import reload
    import utils.auth as auth_module

    reload(auth_module)

    from fastapi import FastAPI, Depends

    app = FastAPI()

    @app.get("/protected")
    def protected_route(_=Depends(auth_module.require_api_key)):
        return {"ok": True}

    client = TestClient(app)

    # Act
    # 1) Missing header -> FastAPI validation error (422)
    response_missing = client.get("/protected")

    # 2) Invalid header -> our HTTPException 401
    response_invalid = client.get(
        "/protected", headers={"x-api-key": "wrong-key"}
    )

    # 3) Valid header -> success 200
    response_valid = client.get(
        "/protected", headers={"x-api-key": "integration-key"}
    )

    # Assert
    assert response_missing.status_code == 422
    assert response_invalid.status_code == 401
    assert response_invalid.json()["detail"] == "Invalid or missing API Key."
    assert response_valid.status_code == 200
    assert response_valid.json() == {"ok": True}
