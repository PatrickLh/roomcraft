import io
import json

import pytest
from app.config import get_settings
from app.main import create_app
from app.providers import MockVision, ProviderError, ProviderResponse
from fastapi.testclient import TestClient
from PIL import Image


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ROOMCRAFT_VISION_PROVIDER", "mock")
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


def picture() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (100, 100), "white").save(output, "PNG")
    return output.getvalue()


def test_upload_returns_validated_plan_and_marks_mock(client):
    result = client.post("/api/plans/recognize", content=picture())
    assert result.status_code == 200
    assert result.json()["simulated"] is True
    assert result.json()["plan"]["schemaVersion"] == "0.1"
    assert result.json()["plan"]["walls"]


def test_rejects_fake_image_before_calling_provider(client, monkeypatch):
    async def unexpected(*args, **kwargs):
        pytest.fail("Invalid upload must not call the provider")

    monkeypatch.setattr(MockVision, "complete", unexpected)
    assert client.post("/api/plans/recognize", content=b"not an image").status_code == 422


def test_rejects_large_upload(client):
    assert client.post("/api/plans/recognize", content=b"x" * (10 * 1024 * 1024 + 1)).status_code == 413


@pytest.mark.parametrize("output", ['{"failure":{"reason":"图片无尺寸标注"}}', '{}', 'not json'])
def test_rejects_failed_or_invalid_recognition(client, monkeypatch, output):
    async def complete(*args, **kwargs):
        return ProviderResponse(output, "test")

    monkeypatch.setattr(MockVision, "complete", complete)
    assert client.post("/api/plans/recognize", content=picture()).status_code == 422


def test_rejects_semantically_invalid_plan(client, monkeypatch):
    from app.providers.mock import MINIMAL_PLAN

    plan = json.loads(json.dumps(MINIMAL_PLAN))
    plan["walls"][0]["openings"][0]["width"] = 20

    async def complete(*args, **kwargs):
        return ProviderResponse(json.dumps(plan), "test")

    monkeypatch.setattr(MockVision, "complete", complete)
    assert client.post("/api/plans/recognize", content=picture()).status_code == 422


def test_provider_errors_do_not_expose_secrets(client, monkeypatch):
    async def complete(*args, **kwargs):
        raise ProviderError("secret-token upstream response")

    monkeypatch.setattr(MockVision, "complete", complete)
    result = client.post("/api/plans/recognize", content=picture())
    assert result.status_code == 502
    assert "secret-token" not in result.text
