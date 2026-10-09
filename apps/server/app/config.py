"""后端配置。

密钥仅从环境变量 / .env 读取（前缀 ROOMCRAFT_），绝不进入浏览器端。
「自行配置模型与密钥」的用户身份 = 部署维护者（plans/v1.0.md §2 第 1 项的 M0 口径）。
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ROOMCRAFT_",
        env_file=(".env", "apps/server/.env"),
        extra="ignore",
    )

    # 视觉大模型（户型解析）
    vision_provider: str = "mock"  # openai_compatible | mock
    vision_base_url: str = ""
    vision_api_key: str = ""
    vision_model: str = ""

    # 生图模型（风格效果图）
    image_provider: str = "mock"  # openai_compatible | mock
    image_base_url: str = ""
    image_api_key: str = ""
    image_model: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
