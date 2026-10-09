"""OpenAI 兼容协议实现。

覆盖面说明（M0-06 评审时可按最终选型增补厂商专用实现）：
- 视觉：/chat/completions 多模态消息。阿里百炼兼容模式（qwen-vl-*）、
  智谱、火山方舟兼容模式等均支持。
- 生图：/images/generations。参考图通过 `image` 扩展参数传递
  （火山方舟 Seedream 系列的兼容实现接受数组）；OpenAI gpt-image-1 走
  /images/edits，如最终选型为它，在本类上增补分支或另写实现类。
"""

from __future__ import annotations

import base64

import httpx

from app.providers.base import (
    GeneratedImage,
    ImageProvider,
    ImageRef,
    ProviderError,
    ProviderResponse,
    VisionProvider,
)

TIMEOUT = httpx.Timeout(300.0, connect=15.0)


class OpenAICompatibleVision(VisionProvider):
    name = "openai_compatible"

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        super().__init__(model)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    async def complete(
        self,
        system: str,
        user_text: str,
        image: ImageRef | None = None,
    ) -> ProviderResponse:
        content: list[dict] = [{"type": "text", "text": user_text}]
        if image is not None:
            content.append({"type": "image_url", "image_url": {"url": image.to_data_url()}})
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            "max_tokens": 8192,
        }
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                resp.raise_for_status()
                body = resp.json()
        except httpx.HTTPStatusError as e:
            raise ProviderError(f"vision http {e.response.status_code}: {e.response.text[:300]}") from e
        except httpx.HTTPError as e:
            raise ProviderError(f"vision network error: {e}") from e

        try:
            text = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise ProviderError(f"vision unexpected response: {str(body)[:300]}") from e
        return ProviderResponse(text=text, model=body.get("model", self.model), usage=body.get("usage"))


class OpenAICompatibleImage(ImageProvider):
    name = "openai_compatible"

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        super().__init__(model)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    async def generate(
        self,
        prompt: str,
        reference_images: list[ImageRef],
        size: str = "1440x720",
    ) -> GeneratedImage:
        payload: dict = {"model": self.model, "prompt": prompt, "size": size}
        if reference_images:
            # 参考图扩展参数（火山方舟 Seedream 等兼容实现）
            payload["image"] = [ref.to_data_url() for ref in reference_images]
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.post(
                    f"{self.base_url}/images/generations",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                resp.raise_for_status()
                body = resp.json()
        except httpx.HTTPStatusError as e:
            raise ProviderError(f"image http {e.response.status_code}: {e.response.text[:300]}") from e
        except httpx.HTTPError as e:
            raise ProviderError(f"image network error: {e}") from e

        try:
            item = body["data"][0]
        except (KeyError, IndexError, TypeError) as e:
            raise ProviderError(f"image unexpected response: {str(body)[:300]}") from e

        if item.get("b64_json"):
            data = base64.b64decode(item["b64_json"])
            mime = "image/png"
        elif item.get("url"):
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                dl = await client.get(item["url"])
                dl.raise_for_status()
                data = dl.content
            mime = dl.headers.get("content-type", "image/png").split(";")[0]
        else:
            raise ProviderError("image response has neither b64_json nor url")
        return GeneratedImage(data=data, mime=mime, model=body.get("model", self.model), raw=body)
