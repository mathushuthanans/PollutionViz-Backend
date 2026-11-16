"""/get_location and /get_trends send Cache-Control + ETag and honour If-None-Match."""
from fastapi.testclient import TestClient

from app.main import app
from app.services.response_service import response_service

client = TestClient(app)
PAYLOAD = {"data": {"pollution": {"aqi": 42}}}


def test_get_location_sets_cache_headers_and_serves_304(monkeypatch):
    monkeypatch.setattr(response_service, "get_location", lambda lat, lon: PAYLOAD)
    first = client.get("/get_location", params={"lat": 1, "lon": 2})
    assert first.status_code == 200
    assert first.json() == PAYLOAD
    assert first.headers["cache-control"].startswith("public, max-age=")
    etag = first.headers["etag"]

    again = client.get(
        "/get_location", params={"lat": 1, "lon": 2}, headers={"If-None-Match": etag}
    )
    assert again.status_code == 304
    assert again.content == b""


def test_errors_are_never_cached(monkeypatch):
    monkeypatch.setattr(response_service, "get_location", lambda lat, lon: {"error": "x"})
    r = client.get("/get_location", params={"lat": 1, "lon": 2})
    assert r.headers["cache-control"] == "no-store"
    assert "etag" not in r.headers
