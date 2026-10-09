"""AI 生成内容标识模块（《人工智能生成合成内容标识办法》，2025-09 生效）。

显式标识：图片右下角「AI 生成」水印（半透明底条）。
隐式标识：PNG tEXt 元数据块（AI-Generated + 溯源字段）。

M0-03 起 Spike B 的全部产物即经过本模块；M3-04 负责生产链路全覆盖
（预览/历史/分享/下载）与格式转换后的标识完整性校验。
"""

from __future__ import annotations

import io
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from PIL.PngImagePlugin import PngInfo

WATERMARK_TEXT = "AI 生成"
METADATA_FLAG_KEY = "AI-Generated"
METADATA_FLAG_VALUE = "true"
METADATA_PREFIX = "roomcraft"

# 水印是合规要求，中文必须真正渲染出来；找不到系统 CJK 字体时退回内置字体（存在豆腐块风险）
_CJK_FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",  # macOS
    "/System/Library/Fonts/STHeiti Light.ttc",  # macOS
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # Debian/Ubuntu
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",  # Arch
]


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in _CJK_FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # 旧版 Pillow 无 size 参数
        return ImageFont.load_default()


def apply_explicit_watermark(image_bytes: bytes) -> bytes:
    """右下角绘制半透明水印底条 + 文本。输入任意格式，输出 PNG。"""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    w, h = img.size
    font = _font(max(18, h // 24))
    text_w = int(font.getlength(WATERMARK_TEXT))
    pad_x, pad_y = max(10, h // 40), max(6, h // 60)
    box_w, box_h = text_w + pad_x * 2, font.size + pad_y * 2
    margin = max(12, h // 30)

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle(
        [w - box_w - margin, h - box_h - margin, w - margin, h - margin],
        radius=max(4, box_h // 6),
        fill=(0, 0, 0, 140),
    )
    draw.text(
        (w - box_w - margin + pad_x, h - box_h - margin + pad_y),
        WATERMARK_TEXT,
        font=font,
        fill=(255, 255, 255, 235),
    )
    out = Image.alpha_composite(img, overlay)
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()


def embed_metadata(image_bytes: bytes, metadata: dict[str, str] | None = None) -> bytes:
    """写入隐式标识 PNG tEXt 块。输入任意格式，输出 PNG。"""
    img = Image.open(io.BytesIO(image_bytes))
    info = PngInfo()
    info.add_text(METADATA_FLAG_KEY, METADATA_FLAG_VALUE)
    info.add_text(f"{METADATA_PREFIX}:created-at", datetime.now(UTC).isoformat())
    for k, v in (metadata or {}).items():
        info.add_text(f"{METADATA_PREFIX}:{k}", str(v))
    buf = io.BytesIO()
    img.save(buf, format="PNG", pnginfo=info)
    return buf.getvalue()


def label_generated_image(image_bytes: bytes, metadata: dict[str, str] | None = None) -> bytes:
    """完整标识：先打显式水印，再写隐式元数据。所有对外产物必须经过本函数。"""
    meta = {"model": "unknown", **(metadata or {})}
    return embed_metadata(apply_explicit_watermark(image_bytes), meta)


def read_metadata(image_bytes: bytes) -> dict[str, str]:
    """读取隐式标识（校验与测试用）。"""
    img = Image.open(io.BytesIO(image_bytes))
    return dict(getattr(img, "text", {}) or {})
