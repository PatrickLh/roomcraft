"""Provider 工厂：按配置实例化视觉/生图 Provider。"""

from __future__ import annotations

from app.config import Settings, get_settings
from app.providers.base import (
    GeneratedImage,
    ImageProvider,
    ImageRef,
    ProviderError,
    ProviderResponse,
    VisionProvider,
    vision_ready,
)
from app.providers.mock import MockImage, MockVision
from app.providers.openai_compatible import OpenAICompatibleImage, OpenAICompatibleVision

VISION_PROVIDERS = {
    "mock": MockVision,
    "openai_compatible": OpenAICompatibleVision,
}
IMAGE_PROVIDERS = {
    "mock": MockImage,
    "openai_compatible": OpenAICompatibleImage,
}


def make_vision_provider(settings: Settings | None = None, provider: str | None = None) -> VisionProvider:
    s = settings or get_settings()
    name = provider or s.vision_provider
    if name not in VISION_PROVIDERS:
        raise ProviderError(f"未知视觉 Provider: {name}（可选: {sorted(VISION_PROVIDERS)}）")
    if name == "mock":
        return MockVision()
    if not (s.vision_base_url and s.vision_api_key and s.vision_model):
        raise ProviderError("视觉 Provider 缺少 base_url / api_key / model 配置")
    return VISION_PROVIDERS[name](s.vision_base_url, s.vision_api_key, s.vision_model)


def make_image_provider(settings: Settings | None = None, provider: str | None = None) -> ImageProvider:
    s = settings or get_settings()
    name = provider or s.image_provider
    if name not in IMAGE_PROVIDERS:
        raise ProviderError(f"未知生图 Provider: {name}（可选: {sorted(IMAGE_PROVIDERS)}）")
    if name == "mock":
        return MockImage()
    if not (s.image_base_url and s.image_api_key and s.image_model):
        raise ProviderError("生图 Provider 缺少 base_url / api_key / model 配置")
    return IMAGE_PROVIDERS[name](s.image_base_url, s.image_api_key, s.image_model)


__all__ = [
    "GeneratedImage",
    "ImageProvider",
    "ImageRef",
    "MockImage",
    "MockVision",
    "OpenAICompatibleImage",
    "OpenAICompatibleVision",
    "ProviderError",
    "ProviderResponse",
    "VISION_PROVIDERS",
    "VisionProvider",
    "IMAGE_PROVIDERS",
    "make_image_provider",
    "make_vision_provider",
    "vision_ready",
]
