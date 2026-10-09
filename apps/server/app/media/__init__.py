"""AI 生成内容标识（显式水印 + 隐式元数据）。"""

from app.media.ai_label import (
    WATERMARK_TEXT,
    label_generated_image,
    read_metadata,
)

__all__ = ["WATERMARK_TEXT", "label_generated_image", "read_metadata"]
