"""Mock Provider：无密钥环境下的管线冒烟与测试。

MockVision 返回一份最小合规户型 JSON（能通过 schema + 语义校验），
让 Spike A / 后端管线在不调用真实 API 时可端到端跑通——
它验证的是「管线」，不是「模型能力」（计划 §5：不能用 mock 替代真实 API 验证）。
"""

from __future__ import annotations

import io
import json

from PIL import Image, ImageDraw

from app.media.ai_label import _font
from app.providers.base import (
    GeneratedImage,
    ImageProvider,
    ImageRef,
    ProviderResponse,
    VisionProvider,
)

MINIMAL_PLAN = {
    "schemaVersion": "0.1",
    "meta": {"name": "Mock·单间", "sourceType": "electronic", "floorHeight": 2.8},
    "walls": [
        {"id": "w-n", "p1": {"x": 0, "y": 0}, "p2": {"x": 4.0, "y": 0}, "thickness": 0.24,
         "openings": [{"id": "o-win", "type": "window", "t": 1.2, "width": 1.5, "height": 1.4, "sill": 0.9}]},
        {"id": "w-e", "p1": {"x": 4.0, "y": 0}, "p2": {"x": 4.0, "y": 3.6}, "thickness": 0.24, "openings": []},
        {"id": "w-s", "p1": {"x": 4.0, "y": 3.6}, "p2": {"x": 0, "y": 3.6}, "thickness": 0.24,
         "openings": [{"id": "o-door", "type": "door", "t": 1.5, "width": 0.9, "height": 2.05, "sill": 0}]},
        {"id": "w-w", "p1": {"x": 0, "y": 3.6}, "p2": {"x": 0, "y": 0}, "thickness": 0.24, "openings": []},
    ],
    "rooms": [
        {
            "id": "r-living",
            "name": "客厅",
            "polygon": [
                {"x": 0, "y": 0},
                {"x": 4.0, "y": 0},
                {"x": 4.0, "y": 3.6},
                {"x": 0, "y": 3.6},
            ],
            "labelPosition": {"x": 2.0, "y": 1.8},
        }
    ],
    "scale": {
        "references": [
            {"id": "s-n", "valueM": 4.0, "p1": {"x": 0, "y": 0}, "p2": {"x": 4.0, "y": 0}, "source": "annotation"}
        ]
    },
}


class MockVision(VisionProvider):
    name = "mock"

    def __init__(self, model: str = "mock-vision") -> None:
        super().__init__(model)

    async def complete(
        self,
        system: str,
        user_text: str,
        image: ImageRef | None = None,
    ) -> ProviderResponse:
        return ProviderResponse(
            text=json.dumps(MINIMAL_PLAN, ensure_ascii=False),
            model=self.model,
            usage={"mock": True},
        )


class MockImage(ImageProvider):
    name = "mock"

    def __init__(self, model: str = "mock-image") -> None:
        super().__init__(model)

    async def generate(
        self,
        prompt: str,
        reference_images: list[ImageRef],
        size: str = "1440x720",
    ) -> GeneratedImage:
        w, h = 720, 360
        img = Image.new("RGB", (w, h), (222, 228, 235))
        draw = ImageDraw.Draw(img)
        draw.rectangle([40, 40, w - 40, h - 40], outline=(120, 130, 145), width=4)
        draw.text((60, 60), f"MOCK render | prompt: {prompt[:40]}", fill=(60, 66, 76), font=_font(16))
        draw.text((60, 90), f"refs: {len(reference_images)}", fill=(60, 66, 76), font=_font(16))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return GeneratedImage(data=buf.getvalue(), mime="image/png", model=self.model)
