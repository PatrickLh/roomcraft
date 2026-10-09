"""AI Provider 抽象基类与工厂。

PRD 原则：视觉大模型与生图模型均可插拔，密钥走后端配置。
新增供应商 = 在本包内新增一个实现类并在 factory 注册，业务代码不感知厂商差异。
"""

from __future__ import annotations

import base64
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class ProviderError(RuntimeError):
    """Provider 调用失败（网络/鉴权/响应格式）。"""


@dataclass
class ImageRef:
    data: bytes
    mime: str = "image/png"

    def to_data_url(self) -> str:
        b64 = base64.b64encode(self.data).decode("ascii")
        return f"data:{self.mime};base64,{b64}"


@dataclass
class ProviderResponse:
    text: str
    model: str
    usage: dict | None = None  # token 用量（厂商返回时保留，供成本记录）


@dataclass
class GeneratedImage:
    data: bytes
    mime: str
    model: str
    raw: dict = field(default_factory=dict)


class VisionProvider(ABC):
    """视觉大模型：多模态补全（户型图 → 模型输出文本）。"""

    name: str = "base"

    def __init__(self, model: str) -> None:
        self.model = model

    @abstractmethod
    async def complete(
        self,
        system: str,
        user_text: str,
        image: ImageRef | None = None,
    ) -> ProviderResponse: ...


class ImageProvider(ABC):
    """生图模型：文本 + 参考图 → 图片。"""

    name: str = "base"

    def __init__(self, model: str) -> None:
        self.model = model

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        reference_images: list[ImageRef],
        size: str = "1440x720",
    ) -> GeneratedImage: ...


def vision_ready(provider: str, base_url: str, api_key: str, model: str) -> bool:
    return provider == "mock" or bool(base_url and api_key and model)
