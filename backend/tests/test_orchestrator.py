"""编排器状态机集成测试。

覆盖有过 bug 的关键路径：状态校验、审核流程、异常处理。
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def _make_client() -> TestClient:
    app = create_app()
    return TestClient(app)


def _login(client: TestClient) -> str:
    """登录 admin 账号返回 token。"""
    resp = client.post("/api/v1/auth/login", json={
        "username": "admin", "password": "admin123",
    })
    if resp.status_code == 200:
        return resp.json()["access_token"]
    return ""


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"} if token else {}


def test_create_experiment_and_get_detail() -> None:
    """创建实验后能查到详情。"""
    with _make_client() as client:
        token = _login(client)
        headers = _auth_header(token)

        resp = client.get("/api/v1/protocols", headers=headers)
        assert resp.status_code == 200
        protocols = resp.json()["protocols"]
        assert len(protocols) > 0

        proto_id = protocols[0]["id"]
        resp = client.post("/api/v1/experiments", json={
            "protocol_id": proto_id,
            "operator_id": "OP-001",
            "sample_code": "SAMPLE-001",
            "name": "测试实验",
        }, headers=headers)
        assert resp.status_code == 200
        exp_id = resp.json()["id"]

        resp = client.get(f"/api/v1/experiments/{exp_id}", headers=headers)
        assert resp.status_code == 200
        detail = resp.json()
        assert detail["experiment"]["status"] == "草稿"


def test_start_nonexistent_experiment_returns_404() -> None:
    """启动不存在的实验返回 404。"""
    with _make_client() as client:
        token = _login(client)
        resp = client.post("/api/v1/experiments/EXP-NONEXISTENT/start",
                           headers=_auth_header(token))
        assert resp.status_code == 404


def test_approve_non_pending_experiment_returns_400() -> None:
    """对非待审核实验执行审核返回 400。"""
    with _make_client() as client:
        token = _login(client)
        headers = _auth_header(token)

        protocols = client.get("/api/v1/protocols", headers=headers).json()["protocols"]
        proto_id = protocols[0]["id"]
        resp = client.post("/api/v1/experiments", json={
            "protocol_id": proto_id,
            "operator_id": "OP-001",
            "sample_code": "SAMPLE-001",
            "name": "测试实验-审核",
        }, headers=headers)
        assert resp.status_code == 200
        exp_id = resp.json()["id"]

        reviewers = client.get("/api/v1/reviewers", headers=headers).json()["reviewers"]
        assert len(reviewers) > 0
        reviewer_id = reviewers[0]["id"]

        resp = client.post(f"/api/v1/experiments/{exp_id}/approve", json={
            "reviewer_id": reviewer_id,
            "comment": "test",
        }, headers=headers)
        assert resp.status_code == 400


def test_abort_non_running_experiment_returns_400() -> None:
    """对非执行中实验执行中止返回 400。"""
    with _make_client() as client:
        token = _login(client)
        headers = _auth_header(token)

        protocols = client.get("/api/v1/protocols", headers=headers).json()["protocols"]
        proto_id = protocols[0]["id"]
        exp = client.post("/api/v1/experiments", json={
            "protocol_id": proto_id,
            "operator_id": "OP-001",
            "sample_code": "SAMPLE-001",
            "name": "测试实验-中止",
        }, headers=headers).json()
        exp_id = exp["id"]

        resp = client.post(f"/api/v1/experiments/{exp_id}/abort", headers=headers)
        assert resp.status_code == 400


def test_retry_nonexistent_experiment_returns_404() -> None:
    """对不存在的实验重试步骤返回 404。"""
    with _make_client() as client:
        token = _login(client)
        resp = client.post("/api/v1/experiments/EXP-NONEXISTENT/retry-step",
                           json={"step_order": 1},
                           headers=_auth_header(token))
        assert resp.status_code == 404


def test_skip_nonexistent_experiment_returns_404() -> None:
    """对不存在的实验跳过步骤返回 404。"""
    with _make_client() as client:
        token = _login(client)
        resp = client.post("/api/v1/experiments/EXP-NONEXISTENT/skip-step",
                           json={"step_order": 1},
                           headers=_auth_header(token))
        assert resp.status_code == 404


def test_experimenters_and_reviewers_list() -> None:
    """实验员和审核人列表都能正常返回。"""
    with _make_client() as client:
        token = _login(client)
        headers = _auth_header(token)

        resp = client.get("/api/v1/experimenters", headers=headers)
        assert resp.status_code == 200
        assert "experimenters" in resp.json()

        resp = client.get("/api/v1/reviewers", headers=headers)
        assert resp.status_code == 200
        reviewers = resp.json()["reviewers"]
        for r in reviewers:
            assert r["role"] in ("reviewer", "admin")


def test_dashboard_returns_stats() -> None:
    """看板端点返回统计数据。"""
    with _make_client() as client:
        token = _login(client)
        resp = client.get("/api/v1/dashboard", headers=_auth_header(token))
        assert resp.status_code == 200
