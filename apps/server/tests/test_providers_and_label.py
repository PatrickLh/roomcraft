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
from app.media.image_prep import prepare_image_for_vision
from app.plan.checks import check_semantics, is_usable
from app.providers import MockImage, MockVision
from app.providers.base import ProviderError
from app.providers.openai_compatible import extract_answer
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


# ---- extract_answer：兼容普通与推理型（DeepSeek R1 风格）响应 ----


def test_extract_answer_normal_content() -> None:
    body = {"choices": [{"message": {"role": "assistant", "content": "{\"a\":1}"}, "finish_reason": "stop"}]}
    assert extract_answer(body) == "{\"a\":1}"


def test_extract_answer_empty_content_with_reasoning_raises() -> None:
    # 真实案例：DeepSeek 推理模型 content 为空、思考在 reasoning_content，
    # 且 finish_reason=length（8192 token 全部耗在推理上）
    body = {
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "", "reasoning_content": "Let me analyze..."},
                "finish_reason": "length",
                "logprobs": None,
            }
        ],
        "usage": {"completion_tokens_details": {"reasoning_tokens": 8192}},
    }
    with pytest.raises(ProviderError) as e:
        extract_answer(body)
    assert "未返回正文" in str(e.value)
    assert "finish_reason=length" in str(e.value)
    assert "ROOMCRAFT_VISION_MAX_TOKENS" in str(e.value)
    assert "Let me analyze" in str(e.value)  # 保留 reasoning 摘要供诊断


def test_extract_answer_truncated_content_raises() -> None:
    body = {"choices": [{"message": {"content": "{\"walls\": ["}, "finish_reason": "length"}]}
    with pytest.raises(ProviderError) as e:
        extract_answer(body)
    assert "截断" in str(e.value)


def test_extract_answer_malformed_body_raises() -> None:
    with pytest.raises(ProviderError):
        extract_answer({"choices": []})


# ---- 图片预处理 ----


def test_prepare_image_downscales_oversized() -> None:
    big = Image.new("RGB", (4000, 3000), (200, 210, 220))
    buf = io.BytesIO()
    big.save(buf, format="JPEG", quality=95)
    data, mime = prepare_image_for_vision(buf.getvalue(), "image/jpeg")
    img = Image.open(io.BytesIO(data))
    assert max(img.size) <= 2048
    assert mime == "image/jpeg"


def test_prepare_image_passthrough_small() -> None:
    small = Image.new("RGB", (800, 600), (240, 240, 240))
    buf = io.BytesIO()
    small.save(buf, format="JPEG", quality=85)
    raw = buf.getvalue()
    data, mime = prepare_image_for_vision(raw, "image/jpeg")
    assert data == raw  # 小图直接透传，避免重编码损失
    assert mime == "image/jpeg"


def test_prepare_image_flattens_alpha() -> None:
    rgba = Image.new("RGBA", (3000, 100), (10, 200, 10, 128))
    buf = io.BytesIO()
    rgba.save(buf, format="PNG")
    data, mime = prepare_image_for_vision(buf.getvalue(), "image/png")
    assert mime == "image/jpeg"
    assert Image.open(io.BytesIO(data)).mode == "RGB"
