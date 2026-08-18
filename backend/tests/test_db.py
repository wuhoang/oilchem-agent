"""DB CRUD 字段白名单测试。

验证流程字段（status/审核字段）不能被任意覆盖，
同时保证普通业务字段和 samples/devices 的 status 不受影响。
"""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(autouse=True)
def _no_background_services():
    """禁用后台服务，避免 SQLite 并发写锁导致测试随机失败。"""
    from unittest.mock import MagicMock

    mock_collector = MagicMock()
    mock_watcher = MagicMock()
    with patch("app.services.hardware_collector.get_hardware_collector", return_value=mock_collector), \
         patch("app.services.file_watcher.get_file_watcher", return_value=mock_watcher):
        yield


_ID_PREFIX = f"WL-{int(time.time())}"


def _make_client() -> TestClient:
    app = create_app()
    return TestClient(app)


def _login(client: TestClient) -> str:
    resp = client.post("/api/v1/auth/login", json={
        "username": "admin", "password": "admin123",
    })
    if resp.status_code == 200:
        return resp.json()["access_token"]
    return ""


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"} if token else {}


def _insert_experiment(client: TestClient, headers: dict[str, str], exp_id: str) -> None:
    resp = client.post("/api/v1/db/experiments/insert", json={
        "row": {"id": exp_id, "name": "白名单测试实验", "operator": "tester"},
    }, headers=headers)
    assert resp.status_code == 200, resp.text


def test_update_experiment_status_ignored() -> None:
    """更新实验的 status 字段不生效（必须走状态机）。"""
    with _make_client() as client:
        headers = _auth_header(_login(client))
        exp_id = f"{_ID_PREFIX}-S1"
        _insert_experiment(client, headers, exp_id)

        resp = client.post("/api/v1/db/experiments/update", json={
            "row": {"id": exp_id, "status": "已完成"},
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "待开始"


def test_update_experiment_review_fields_ignored() -> None:
    """审核字段（reviewed_by_id/reviewed_at）不能被 CRUD 直接修改。"""
    with _make_client() as client:
        headers = _auth_header(_login(client))
        exp_id = f"{_ID_PREFIX}-R1"
        _insert_experiment(client, headers, exp_id)

        resp = client.post("/api/v1/db/experiments/update", json={
            "row": {
                "id": exp_id,
                "reviewed_by_id": "U-999",
                "reviewed_at": "2026-01-01 00:00:00",
                "review_comment": "篡改",
            },
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["reviewed_by_id"] is None
        assert data["reviewed_at"] is None
        assert data["review_comment"] is None


def test_update_experiment_name_works() -> None:
    """普通业务字段（name）仍可正常更新。"""
    with _make_client() as client:
        headers = _auth_header(_login(client))
        exp_id = f"{_ID_PREFIX}-N1"
        _insert_experiment(client, headers, exp_id)

        resp = client.post("/api/v1/db/experiments/update", json={
            "row": {"id": exp_id, "name": "改名后的实验"},
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "改名后的实验"


def test_insert_experiment_status_forced_default() -> None:
    """插入实验时携带 status 被忽略，落库为默认「待开始」。"""
    with _make_client() as client:
        headers = _auth_header(_login(client))
        exp_id = f"{_ID_PREFIX}-I1"

        resp = client.post("/api/v1/db/experiments/insert", json={
            "row": {"id": exp_id, "name": "注入状态实验", "status": "已完成"},
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "待开始"


def test_update_sample_status_works() -> None:
    """samples 无状态机，status 仍可人工维护。"""
    with _make_client() as client:
        headers = _auth_header(_login(client))
        code = f"{_ID_PREFIX}-SAMPLE1"

        resp = client.post("/api/v1/db/samples/insert", json={
            "row": {"code": code, "name": "白名单样品"},
        }, headers=headers)
        assert resp.status_code == 200

        resp = client.post("/api/v1/db/samples/update", json={
            "row": {"code": code, "status": "留样"},
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "留样"