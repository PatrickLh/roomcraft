"""Local prototype upload-to-plan endpoint; no persistence or public-service quotas yet."""

import io
import json

from fastapi import APIRouter, HTTPException, Request
from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from app.media.image_prep import prepare_image_for_vision
from app.plan.checks import check_semantics, is_usable
from app.plan.floor_plan_models import FloorPlan
from app.providers import ImageRef, ProviderError, make_vision_provider

router = APIRouter()
MAX_BYTES = 10 * 1024 * 1024
MIMES = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


def prepare_upload(data: bytes) -> ImageRef:
    try:
        with Image.open(io.BytesIO(data)) as image:
            mime = MIMES.get(image.format)
            if not mime or image.width * image.height > 24_000_000:
                raise HTTPException(422, "请上传不超过 2400 万像素的 JPG、PNG 或 WebP 图片")
            image.verify()
        prepared, mime = prepare_image_for_vision(data, mime)
        return ImageRef(prepared, mime)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise HTTPException(422, "图片无法读取，请重新选择 JPG、PNG 或 WebP 文件") from exc


@router.post("/api/plans/recognize")
async def recognize(request: Request) -> dict:
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > MAX_BYTES:
            raise HTTPException(413, "图片不能超过 10 MB")
    image = await run_in_threadpool(prepare_upload, bytes(data))
    try:
        provider = make_vision_provider()
    except ProviderError as exc:
        raise HTTPException(503, "识别服务尚未配置，请先体验示例户型或联系维护者") from exc
    prompt = (
        "将图片中的墙体、门窗、房间名转换为以下 Schema 的 JSON。坐标为米，x 向右、y 向下。"
        "只能依据图上可读的尺寸标注标定，不能猜测比例；至少提供一条 scale.references，"
        "其 valueM 与 p1/p2 距离误差不得超过 0.15 米。墙的 openings.t 是从 p1 开始的米制距离，"
        "门 sill=0，开口不能重叠或超出墙长。房间提供 polygon 和 labelPosition。"
        "不添加 Schema 之外的字段。不是户型图、尺寸缺失或无法辨认时，"
        '输出 {"failure":{"reason":"中文原因"}}。只输出 JSON，不要 Markdown。\n'
        + json.dumps(FloorPlan.model_json_schema(), ensure_ascii=False)
    )
    try:
        response = await provider.complete("你是严谨的户型图结构化解析器。", prompt, image)
        text = response.text.strip()
        if text.startswith("```"):
            text = "\n".join(text.splitlines()[1:-1])
        raw = json.loads(text)
        if isinstance(raw, dict) and "failure" in raw:
            reason = raw["failure"].get("reason") if isinstance(raw["failure"], dict) else None
            raise HTTPException(422, str(reason or "无法识别户型，请上传清晰且带尺寸标注的图片")[:300])
        plan = FloorPlan.model_validate(raw).model_dump(mode="json", exclude_none=True)
        issues = check_semantics(plan)
        if not is_usable(issues):
            raise HTTPException(422, "识别结果的尺寸或墙体结构不一致，请尝试更清晰的户型图")
        return {"plan": plan, "simulated": provider.name == "mock"}
    except ProviderError as exc:
        raise HTTPException(502, "识别服务暂时不可用，请稍后重试") from exc
    except (json.JSONDecodeError, ValidationError, TypeError, AttributeError) as exc:
        raise HTTPException(422, "识别结果不完整，请尝试更清晰、带尺寸标注的户型图") from exc
