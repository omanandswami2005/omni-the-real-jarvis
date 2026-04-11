from fastapi import FastAPI
from starlette.testclient import TestClient

from app.middleware.cors import setup_cors


def test_cors_specific_origins(monkeypatch):
    """Test that specific origins allow credentials."""
    monkeypatch.setattr("app.config.settings.CORS_ORIGINS", "http://localhost:5173")

    app = FastAPI()
    setup_cors(app)

    @app.get("/")
    def read_root():
        return {"Hello": "World"}

    client = TestClient(app)
    response = client.get("/", headers={"Origin": "http://localhost:5173"})
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_wildcard_origins(monkeypatch):
    """Test that wildcard origin sets allow_credentials to false/omitted."""
    monkeypatch.setattr("app.config.settings.CORS_ORIGINS", "*")

    app = FastAPI()
    setup_cors(app)

    @app.get("/")
    def read_root():
        return {"Hello": "World"}

    client = TestClient(app)
    response = client.get("/", headers={"Origin": "http://evil.com"})
    assert response.headers.get("access-control-allow-origin") == "*"
    assert response.headers.get("access-control-allow-credentials") is None
