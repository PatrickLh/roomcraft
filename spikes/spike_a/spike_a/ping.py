"""视觉模型连通性分步诊断（不依赖样本图片）。

用法：
    pnpm spike:ping                 # 步骤1 纯文本 + 步骤2 内置小图
    pnpm spike:ping -- --image spikes/samples/001_electronic_1.jpg   # 加测真实图片

步骤 1 纯文本   → 验证 base_url / api_key / model（接入点）是否可用
步骤 2 内置小图 → 验证图片输入链路（base64 data URL）
步骤 3 真实图片 → 验证真实尺寸样本（经 prepare_image_for_vision 压缩）

每步打印耗时、completion tokens 与响应开头；失败即停并给出针对性提示。
输出绝不包含密钥。
"""

from __future__ import annotations

import argparse
import asyncio
import io
import time
from pathlib import Path

from app.config import get_settings
from app.media.image_prep import prepare_image_for_vision
from app.providers.base import ImageRef, ProviderError
from app.providers.openai_compatible import OpenAICompatibleVision

MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


def tiny_red_square() -> ImageRef:
    """64x64 纯红 PNG，验证图片输入链路用。"""
    from PIL import Image

    img = Image.new("RGB", (64, 64), (220, 40, 40))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return ImageRef(data=buf.getvalue(), mime="image/png")


async def run_step(vision: OpenAICompatibleVision, name: str, prompt: str, image: ImageRef | None) -> bool:
    t0 = time.monotonic()
    try:
        resp = await vision.complete("你是连通性测试助手，用一句话回答。", prompt, image)
    except ProviderError as e:
        print(f"  ✗ {name} 失败（{time.monotonic() - t0:.1f}s）：{e}")
        return False
    dt = time.monotonic() - t0
    usage = resp.usage or {}
    print(f"  ✓ {name} 成功（{dt:.1f}s）")
    print(f"    completion tokens: {usage.get('completion_tokens')}  模型: {resp.model}")
    print(f"    响应开头: {resp.text[:120]}")
    return True


def hint_for_failure(step: int) -> str:
    hints = {
        1: "排查顺序：404→model 不是接入点 ID/已开通模型名；401→key；超时→base_url 或网络；"
           "先用 curl 打一个 1 token 的请求对照。",
        2: "纯文本通了但带图失败：该模型大概率不支持图片输入，换视觉模型"
           "（如 doubao-seed-1-6-flash-250615 / qwen-vl-max）。",
        3: "小图通了但真实图片失败/超慢：看本步耗时——几十秒属正常推理时长，"
           "超时则尝试关闭思考（ROOMCRAFT_VISION_EXTRA_BODY）。",
    }
    return hints.get(step, "")


async def main() -> int:  # noqa: C901
    parser = argparse.ArgumentParser(description="视觉模型连通性分步诊断")
    parser.add_argument("--image", default=None, help="步骤 3 使用的真实样本图片路径")
    args = parser.parse_args([a for a in __import__("sys").argv[1:] if a != "--"])

    settings = get_settings()
    print(f"base_url : {settings.vision_base_url or '(未配置)'}")
    print(f"model    : {settings.vision_model or '(未配置)'}")
    print(f"key      : {'已配置' if settings.vision_api_key else '未配置'}")
    print(f"timeout  : {settings.vision_timeout}s  max_tokens: {settings.vision_max_tokens}  "
          f"extra_body: {settings.vision_extra_body or '(无)'}")

    if not (settings.vision_base_url and settings.vision_api_key and settings.vision_model):
        print("\n✗ vision 配置不完整：请在 .env 填写 ROOMCRAFT_VISION_BASE_URL / API_KEY / MODEL")
        return 1

    vision = OpenAICompatibleVision(settings.vision_base_url, settings.vision_api_key, settings.vision_model)

    print("\n[步骤 1] 纯文本调用（验证 key/模型/接入点）")
    if not await run_step(vision, "纯文本", "请回复两个字：pong", None):
        print(f"\n提示：{hint_for_failure(1)}")
        return 2

    print("\n[步骤 2] 内置 64x64 红色小图（验证图片输入链路）")
    if not await run_step(vision, "小图", "这张图的主色是什么颜色？只回答颜色名。", tiny_red_square()):
        print(f"\n提示：{hint_for_failure(2)}")
        return 3

    if args.image:
        path = Path(args.image)
        if not path.exists():
            print(f"\n✗ 图片不存在：{path}")
            return 1
        data, mime = prepare_image_for_vision(path.read_bytes(), MIME.get(path.suffix.lower(), "image/jpeg"))
        print(f"\n[步骤 3] 真实图片 {path.name}（发送 {len(data) / 1024:.0f}KB）")
        ref = ImageRef(data=data, mime=mime)
        ok = await run_step(vision, "真实图片", "这是一张户型图吗？用一句话回答是或不是。", ref)
        if not ok:
            print(f"\n提示：{hint_for_failure(3)}")
            return 4

    print("\n全部通过：模型调用链路正常，可执行 pnpm spike:a。")
    return 0


if __name__ == "__main__":

    raise SystemExit(asyncio.run(main()))
