"""平台宿主配置：只从环境变量读取，应用工厂与 Alembic 共用同一份。"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_URL = "postgresql+psycopg://mvstudy:mvstudy@127.0.0.1:5433/mvstudy"
MULTIPART_OVERHEAD_BYTES = 64 * 1024


def _storage_dir(value: str) -> str:
    """相对路径一律按仓库根解析，避免从 backend/ 启动时落到另一个目录。"""
    if not value.strip():
        value = str(ROOT / "var" / "files")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return str(path)


def load_config() -> dict:
    """读取 .env 后返回 Flask 可直接 update 的配置字典。"""
    load_dotenv(ROOT / ".env")
    max_file_bytes = int(os.getenv("MAX_CONTENT_LENGTH", str(512 * 1024)))
    return {
        "DATABASE_URL": os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL),
        "JWT_SECRET": os.getenv("JWT_SECRET", "local-dev-only"),
        "JWT_TTL_MINUTES": int(os.getenv("JWT_TTL_MINUTES", "480")),
        "FILE_STORAGE_DIR": _storage_dir(
            os.getenv("FILE_STORAGE_DIR", str(ROOT / "var" / "files"))
        ),
        # MAX_CONTENT_LENGTH 表示单文件字节上限；multipart 的边界与头部另有开销，
        # 故 Flask 的请求体上限放宽一个固定余量，精确校验在 create_file() 内完成。
        "MAX_FILE_BYTES": max_file_bytes,
        "MAX_CONTENT_LENGTH": max_file_bytes + MULTIPART_OVERHEAD_BYTES,
        "WEB_ORIGIN": os.getenv("WEB_ORIGIN", "http://localhost:5173"),
    }


def database_url() -> str:
    """迁移命令与测试夹具统一从这里取连接串。"""
    return load_config()["DATABASE_URL"]
