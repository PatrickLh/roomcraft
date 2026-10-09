"""OpenAI 兼容协议实现。

覆盖面说明（M0-06 评审时可按最终选型增补厂商专用实现）：
- 视觉：/chat/completions 多模态消息。阿里百炼兼容模式（qwen-vl-*）、
  智谱、火山方舟兼容模式等均支持。
- 生图：/images/generations。参考图通过 `image` 扩展参数传递
  （火山方舟 Seedream 系列的兼容实现接受数组）；OpenAI gpt-image-1 走
  /images/edits，如最终选型为它，在本类上增补分支或另写实现类。

已适配的响应形态：
- 普通模型：choices[0].message.content
- 推理型模型（DeepSeek R1 风格）：思考过程在 message.reasoning_content，
  content 才是正文；reasoning token 计入 max_tokens，耗尽时
  finish_reason=length 且 content 为空 —— 此时应报错并提示调大预算，
  而不是把空串当答案继续解析。
"""

from __future__ import annotations

import base64
import json
import logging

import httpx

from app.config import get_settings
from app.providers.base import (
    GeneratedImage,
    ImageProvider,
    ImageRef,
    ProviderError,
    ProviderResponse,
    VisionProvider,
)

logger = logging.getLogger("roomcraft.vision")

TIMEOUT = httpx.Timeout(300.0, connect=15.0)


def extract_answer(body: dict) -> str:
    """从 chat.completion 响应中取出正文；空正文/截断抛带诊断信息的 ProviderError。"""
    try:
        choice = body["choices"][0]
        message = choice.get("message", {})
        content = (message.get("content") or "").strip()
        finish = choice.get("finish_reason")
    except (KeyError, IndexError, TypeError) as e:
        raise ProviderError(f"vision unexpected response: {str(body)[:300]}") from e

    if not content:
        reasoning = (message.get("reasoning_content") or "").strip()
        detail = f"finish_reason={finish}"
        if reasoning:
            detail += f"；reasoning_content 前 200 字：{reasoning[:200]}"
        raise ProviderError(
            "模型未返回正文（" + detail + "）。常见原因："
            "① 推理型模型把 token 预算耗在思考上（调大 ROOMCRAFT_VISION_MAX_TOKENS）；"
            "② 该模型不支持图片输入。"
        )
    if finish == "length":
        # 正文有了但被截断，JSON 必然不完整，趁早报错比让下游解析失败更可诊断
        raise ProviderError(
            "模型输出因 max_tokens 被截断（finish_reason=length），"
            "请调大 ROOMCRAFT_VISION_MAX_TOKENS 后重试"
        )
    return content


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
        settings = get_settings()
        content: list[dict] = [{"type": "text", "text": user_text}]
        if image is not None:
            content.append({"type": "image_url", "image_url": {"url": image.to_data_url()}})
        payload: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            "max_tokens": settings.vision_max_tokens,
        }
        # 厂商扩展参数透传（如方舟关闭深度思考 {"thinking":{"type":"disabled"}}）
        if settings.vision_extra_body:
            try:
                extra = json.loads(settings.vision_extra_body)
                if not isinstance(extra, dict):
                    raise ValueError("必须是 JSON 对象")
            except ValueError as e:
                raise ProviderError(f"ROOMCRAFT_VISION_EXTRA_BODY 不是合法 JSON 对象: {e}") from e
            payload.update(extra)
        timeout = httpx.Timeout(settings.vision_timeout, connect=15.0)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
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

        if settings.vision_debug:
            logger.info("vision raw body: %s", json.dumps(body, ensure_ascii=False)[:4000])

        text = extract_answer(body)
        finish = body.get("choices", [{}])[0].get("finish_reason")
        return ProviderResponse(
            text=text, model=body.get("model", self.model), usage=body.get("usage"), finish=finish
        )


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
