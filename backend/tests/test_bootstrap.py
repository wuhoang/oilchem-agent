"""Smoke test ensuring the FastAPI app boots and exposes core endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_root_banner() -> None:
    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "OilChem Agent"
        assert body["status"] == "running"
        assert "version" in body


def test_health_probe() -> None:
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
