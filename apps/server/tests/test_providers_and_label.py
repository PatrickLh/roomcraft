"""Mock Provider 契约与 AI 标识模块。"""

import asyncio
import io
import json
from pathlib import Path

import pytest
from app.media.ai_label import (
    WATERMARK_TEXT,
    embed_metadata,
    label_generated_image,
    read_metadata,
)
from app.plan.checks import check_semantics, is_usable
from app.providers import MockImage, MockVision
from jsonschema import Draft202012Validator
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO_ROOT / "packages" / "shared-schema" / "floor-plan.schema.json"


@pytest.fixture
def validator() -> Draft202012Validator:
    return Draft202012Validator(json.loads(SCHEMA_PATH.read_text()))


def test_mock_vision_output_is_schema_and_semantics_valid(validator: Draft202012Validator) -> None:
    resp = asyncio.run(MockVision().complete("sys", "user"))
    plan = json.loads(resp.text)
    validator.validate(plan)  # 不抛即通过
    assert is_usable(check_semantics(plan))


def test_mock_image_returns_png() -> None:
    img = asyncio.run(MockImage().generate("测试 prompt", []))
    assert img.data[:8] == b"\x89PNG\r\n\x1a\n"


def test_label_adds_watermark_and_metadata() -> None:
    raw = asyncio.run(MockImage().generate("t", [])).data
    labeled = label_generated_image(raw, {"model": "mock-image", "task": "style-render"})

    assert labeled[:8] == b"\x89PNG\r\n\x1a\n"
    meta = read_metadata(labeled)
    assert meta.get("AI-Generated") == "true"
    assert meta.get("roomcraft:model") == "mock-image"
    assert meta.get("roomcraft:task") == "style-render"
    assert "roomcraft:created-at" in meta

    # 显式水印确实改变了像素（右下角区域非纯背景）
    before = Image.open(io.BytesIO(raw)).convert("RGBA")
    after = Image.open(io.BytesIO(labeled)).convert("RGBA")
    w, h = before.size
    region_b = before.crop((w - 120, h - 60, w, h)).tobytes()
    region_a = after.crop((w - 120, h - 60, w, h)).tobytes()
    assert region_a != region_b
    assert WATERMARK_TEXT


def test_embed_metadata_is_idempotent_over_flag() -> None:
    raw = asyncio.run(MockImage().generate("t", [])).data
    once = embed_metadata(raw, {"model": "m"})
    twice = embed_metadata(once, {"model": "m"})
    assert read_metadata(twice).get("AI-Generated") == "true"
