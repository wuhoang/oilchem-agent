"""认证与权限集成测试（AUTH_ENABLED=true 场景）。"""
from __future__ import annotations

import os

os.environ["AUTH_ENABLED"] = "true"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402


def _make_client() -> TestClient:
    app = create_app()
    return TestClient(app)


def test_login_success_and_protected_access() -> None:
    with _make_client() as client:
        # 未登录访问受保护端点 → 401
        resp = client.get("/api/v1/experiments")
        assert resp.status_code == 401

        # 登录（种子用户）
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["access_token"]
        assert body["user"]["role"] == "admin"

        # 带 token 访问 → 200
        headers = {"Authorization": f"Bearer {body['access_token']}"}
        resp = client.get("/api/v1/experiments", headers=headers)
        assert resp.status_code == 200


def test_login_wrong_password_rejected() -> None:
    with _make_client() as client:
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "wrong-password"},
        )
        assert resp.status_code == 401


def test_fake_token_rejected() -> None:
    with _make_client() as client:
        resp = client.get(
            "/api/v1/experiments",
            headers={"Authorization": "Bearer not.a.real.token"},
        )
        assert resp.status_code == 401


def test_operator_cannot_review() -> None:
    with _make_client() as client:
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "operator", "password": "operator123"},
        )
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 操作员调审核接口 → 403
        resp = client.post(
            "/api/v1/experiments/exp-nonexistent/approve",
            headers=headers,
            json={"reviewer_id": "1", "comment": "x"},
        )
        assert resp.status_code == 403


def test_reviewers_from_users_table() -> None:
    with _make_client() as client:
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = resp.json()["access_token"]
        resp = client.get(
            "/api/v1/reviewers",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        reviewers = resp.json()["reviewers"]
        roles = {r["role"] for r in reviewers}
        assert "reviewer" in roles
        assert "admin" in roles
        # 操作员不应出现在审核人列表
        assert "operator" not in roles


def test_sse_requires_token() -> None:
    with _make_client() as client:
        resp = client.get("/api/v1/experiments/events")
        assert resp.status_code == 401


def test_me_reports_auth_enabled_without_token() -> None:
    """auth 开启但未登录时，/auth/me 应返回 auth_enabled=true（而非 401），
    让前端据此显示登录页。"""
    with _make_client() as client:
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 200
        body = resp.json()
        assert body["auth_enabled"] is True
        assert body["user"] is None