"""FastAPI 入口。M0 仅暴露健康检查与 Provider 配置状态（不含任何密钥值）。"""

from datetime import UTC, datetime

from fastapi import FastAPI

from app.config import get_settings
from app.plan.recognition import router as recognition_router
from app.providers import vision_ready

VERSION = "0.1.0"


def create_app() -> FastAPI:
    app = FastAPI(title="RoomCraft API", version=VERSION)
    app.include_router(recognition_router)

    @app.get("/api/health")
    async def health() -> dict:
        return {"status": "ok", "version": VERSION, "time": datetime.now(UTC).isoformat()}

    @app.get("/api/providers")
    async def providers() -> dict:
        s = get_settings()
        vision = {
            "kind": "vision",
            "provider": s.vision_provider,
            "model": s.vision_model or None,
            "keyConfigured": bool(s.vision_api_key),
            "ready": vision_ready(s.vision_provider, s.vision_base_url, s.vision_api_key, s.vision_model),
        }
        image = {
            "kind": "image",
            "provider": s.image_provider,
            "model": s.image_model or None,
            "keyConfigured": bool(s.image_api_key),
            "ready": vision_ready(s.image_provider, s.image_base_url, s.image_api_key, s.image_model),
        }
        return {"providers": [vision, image]}

    return app


app = create_app()
