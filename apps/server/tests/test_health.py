"""健康检查与 Provider 状态接口。

注意：Settings 会读本地 .env，测试必须显式注入环境变量，
与开发者本机的密钥配置解耦。
"""

import pytest
from app.config import get_settings
from app.main import create_app
from fastapi.testclient import TestClient


@pytest.fixture
def mock_provider_env(monkeypatch):
    """强制 mock provider + 空密钥，隔离开发者本地 .env。"""
    for key in (
        "ROOMCRAFT_VISION_PROVIDER",
        "ROOMCRAFT_VISION_BASE_URL",
        "ROOMCRAFT_VISION_API_KEY",
        "ROOMCRAFT_VISION_MODEL",
        "ROOMCRAFT_IMAGE_PROVIDER",
        "ROOMCRAFT_IMAGE_BASE_URL",
        "ROOMCRAFT_IMAGE_API_KEY",
        "ROOMCRAFT_IMAGE_MODEL",
    ):
        monkeypatch.setenv(key, "mock" if key.endswith("PROVIDER") else "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_health_ok() -> None:
    client = TestClient(create_app())
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"]


def test_providers_report_ready_without_keys_for_mock(mock_provider_env) -> None:
    client = TestClient(create_app())
    body = client.get("/api/providers").json()
    kinds = {p["kind"]: p for p in body["providers"]}
    assert set(kinds) == {"vision", "image"}
    # 未配置密钥 → mock，且 mock 恒 ready；响应体不得包含任何密钥值
    for p in kinds.values():
        assert p["provider"] == "mock"
        assert p["keyConfigured"] is False
        assert p["ready"] is True
    assert "sk-" not in str(body)
