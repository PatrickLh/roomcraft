"""健康检查与 Provider 状态接口。"""

from app.main import create_app
from fastapi.testclient import TestClient


def test_health_ok() -> None:
    client = TestClient(create_app())
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"]


def test_providers_report_ready_without_keys_for_mock() -> None:
    client = TestClient(create_app())
    body = client.get("/api/providers").json()
    kinds = {p["kind"]: p for p in body["providers"]}
    assert set(kinds) == {"vision", "image"}
    # 测试环境未配置密钥 → 默认 mock，且 mock 恒 ready
    for p in kinds.values():
        assert p["provider"] == "mock"
        assert p["keyConfigured"] is False
        assert p["ready"] is True
        assert "api_key" not in str(body).lower() or p["keyConfigured"] is False
