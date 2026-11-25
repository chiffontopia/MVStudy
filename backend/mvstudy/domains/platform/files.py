"""F1 用例：受控文件的上传、取回与内部读取。

规则（docs/database.md:35、docs/interfaces.md:26）：

- 内容不可覆盖：每次上传生成新的 ``file_id`` 与 ``storage_key``；
- 元信息入库，字节只进私有卷；
- 读取按所有者授权，越权与不存在都返回 ``None``，由路由映射为 404；
- 超限在写盘前拒绝，失败后不留数据库行与磁盘对象。

``read_bytes`` 是给 2/3/9 号的服务内部入口：调用方必须先完成
材料、运行或提交等资源授权，不能把 ``file_id`` 直接当访问凭证。
"""

from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from flask import current_app
from sqlalchemy.orm import Session

from mvstudy.config import load_config

from . import storage
from .models import File

_MEDIA_TYPE = re.compile(r"^[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+$")
_UNSAFE_FILENAME = re.compile(r'[\\/:*?"<>|\x00-\x1f\x7f]')


class FileTooLarge(Exception):
    """单文件字节数超过上限；路由映射为 413 payload_too_large。"""

    code = "payload_too_large"
    status = 413

    def __init__(self, message: str = "文件超过大小限制。") -> None:
        super().__init__(message)
        self.message = message


class InvalidFile(Exception):
    """缺少文件名或内容不合法；路由映射为 400 invalid_files。"""

    code = "invalid_files"
    status = 400

    def __init__(self, message: str = "文件内容不合法。") -> None:
        super().__init__(message)
        self.message = message


def _file_limit() -> int:
    try:
        config = current_app.config
        configured = config.get("MAX_FILE_BYTES") or config.get("MAX_CONTENT_LENGTH")
        return int(configured) if configured else 512 * 1024
    except RuntimeError:
        return int(load_config()["MAX_FILE_BYTES"])


def _normalize_media_type(value: str | None) -> str:
    """只接受合法的 type/subtype；异常值退回通用二进制类型。"""
    if not isinstance(value, str):
        return "application/octet-stream"
    candidate = value.split(";", 1)[0].strip()
    return candidate if _MEDIA_TYPE.fullmatch(candidate) else "application/octet-stream"


def safe_name(name: str, fallback: str) -> str:
    """生成可用于 Content-Disposition 的文件名；磁盘路径从不使用它。"""
    cleaned = _UNSAFE_FILENAME.sub("_", (name or "").strip())
    cleaned = cleaned.strip()
    if cleaned in {"", ".", ".."}:
        return fallback
    return cleaned


def file_meta(row: File) -> dict[str, Any]:
    """F1 成功响应字段；不暴露 owner_id、storage_key 与时间。"""
    return {
        "file_id": row.file_id,
        "name": row.name,
        "media_type": row.media_type,
        "byte_size": row.byte_size,
    }


def create_file(
    session: Session,
    actor: dict[str, Any],
    *,
    name: str,
    media_type: str | None,
    data: bytes,
    max_bytes: int | None = None,
    base_dir: str | None = None,
) -> File:
    """新建一份文件记录并落盘；任何一步失败都不留下半成品。

    调用方应使用独立会话；若在更大的事务中调用，失败会回滚该事务，
    这正是提交、运行等场景需要的原子语义。
    """
    user_id = (actor or {}).get("user_id")
    if not user_id:
        raise InvalidFile("缺少上传者身份。")
    if not isinstance(name, str) or not name.strip():
        raise InvalidFile("请选择要上传的文件。")
    clean_name = name.strip()
    if "\x00" in clean_name:
        # PostgreSQL 的 text 不接受 NUL；在入库前拒绝，避免 500。
        raise InvalidFile("文件名包含非法字符。")
    if not isinstance(data, bytes):
        raise InvalidFile("文件内容必须是字节。")

    limit = _file_limit() if max_bytes is None else int(max_bytes)
    if len(data) > limit:
        raise FileTooLarge()

    file_id = f"f-{uuid4().hex[:12]}"
    storage_key = uuid4().hex
    row = File(
        file_id=file_id,
        owner_id=user_id,
        name=clean_name,
        media_type=_normalize_media_type(media_type),
        byte_size=len(data),
        storage_key=storage_key,
    )
    session.add(row)
    try:
        # 先让外键与唯一约束通过，再写盘，避免为非法记录产生孤儿文件。
        session.flush()
        storage.save(data, storage_key, base_dir)
        session.commit()
    except Exception:
        session.rollback()
        storage.delete(storage_key, base_dir)
        raise
    return row


def get_owned_file(
    session: Session, actor: dict[str, Any], file_id: str
) -> File | None:
    """仅返回属于当前用户的记录；他人文件与不存在同样返回 None。"""
    user_id = (actor or {}).get("user_id")
    if not user_id:
        return None
    row = session.get(File, file_id)
    if row is None or row.owner_id != user_id:
        return None
    return row


def read_file(
    session: Session,
    actor: dict[str, Any],
    file_id: str,
    base_dir: str | None = None,
) -> tuple[File, bytes] | None:
    """按所有者授权读取；元信息存在但字节缺失时同样按不可读处理。"""
    row = get_owned_file(session, actor, file_id)
    if row is None:
        return None
    try:
        return row, storage.load(row.storage_key, base_dir)
    except (FileNotFoundError, ValueError):
        # 对象缺失或库中对象键损坏，都按不可读处理，不向调用方暴露内部状态。
        return None


def read_bytes(session: Session, file_id: str, base_dir: str | None = None) -> bytes:
    """服务内部读取入口，供 2/3/9 号在完成资源授权后调用。

    红线：本函数只校验文件是否存在，不校验调用者身份。调用方必须先确认
    该文件已被关联到当前用户可见的材料、运行或提交，禁止直接暴露给 HTTP。
    """
    row = session.get(File, file_id)
    if row is None:
        raise FileNotFoundError(file_id)
    return storage.load(row.storage_key, base_dir)
