"""应用配置：唯一的环境变量入口。

所有模块通过 `get_settings()` 取配置，禁止在业务代码里直接读 os.environ。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ 目录，用于把相对路径锚定到工程内，避免受启动时 CWD 影响
BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- 应用 ----
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    cors_origins: str = "http://localhost:5173"
    request_timeout: int = 120

    # ---- 数据库 ----
    db_url: str = "sqlite+aiosqlite:///./data/app.db"

    # ---- 存储 ----
    upload_dir: str = "./data/uploads"
    index_dir: str = "./data/index"
    max_file_mb: int = 20
    max_pages: int = 80

    # ---- 模型服务 ----
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    llm_timeout: int = 60
    llm_max_retry: int = 2
    llm_max_concurrency: int = 3

    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = "bge-m3"

    rerank_enabled: bool = False
    rerank_model: str = ""

    # ---- 检索 ----
    retrieve_top_k: int = 20
    rerank_top_n: int = 5
    min_confidence: float = 0.6

    # ---- 解析与开关 ----
    parse_timeout_sec: int = 10
    ocr_enabled: bool = False
    demo_mode: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def upload_path(self) -> Path:
        return self._anchor(self.upload_dir)

    @property
    def index_path(self) -> Path:
        return self._anchor(self.index_dir)

    @property
    def llm_configured(self) -> bool:
        """仅检查配置是否齐全，不发起真实调用（健康检查不能烧钱）。"""
        return bool(self.llm_base_url and self.llm_api_key and self.llm_model)

    def _anchor(self, raw: str) -> Path:
        p = Path(raw)
        return p if p.is_absolute() else (BACKEND_DIR / p).resolve()

    def ensure_dirs(self) -> None:
        for p in (self.upload_path, self.index_path):
            p.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
