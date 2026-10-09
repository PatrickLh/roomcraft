"""发给视觉模型的图片预处理。

图片过大不会导致超时（78KB 的样本 1 秒内传完），但真实手机照片可能到 5MB+：
压缩能显著降低上传耗时与 token 成本（多数视觉模型按像素计费），对识别精度无损。
"""

from __future__ import annotations

import io

from PIL import Image

# 小于该体积且尺寸合规的图直接透传，避免重编码损失
PASSTHROUGH_MAX_BYTES = 400_000


def prepare_image_for_vision(
    data: bytes,
    mime: str,
    max_dim: int = 2048,
    quality: int = 85,
) -> tuple[bytes, str]:
    """压缩/缩放到视觉模型友好的尺寸。返回 (bytes, mime)。"""
    img = Image.open(io.BytesIO(data))
    if max(img.size) <= max_dim and len(data) <= PASSTHROUGH_MAX_BYTES:
        return data, mime

    scale = min(1.0, max_dim / max(img.size))
    if scale < 1.0:
        img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    # 透明通道压到白底（户型图场景无透明需求，JPEG 体积最优）
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue(), "image/jpeg"
