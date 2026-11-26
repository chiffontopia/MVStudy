"""私有卷读写：文件字节不经过数据库，也不返回给未经授权的调用方。

对象键是 32 位小写十六进制，按前两位分桶。键只由本域生成，
任何外部输入都要先经过 ``_path`` 的正则校验，避免路径穿越。
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from flask import current_app

from mvstudy.config import load_config

_STORAGE_KEY = re.compile(r"^[a-f0-9]{32}$")


def _root(base_dir: str | Path | None = None) -> Path:
    """定位存储根目录。

    优先使用显式传入的 ``base_dir``（3 号独立进程用）；否则取 Flask 配置；
    没有应用上下文时退回环境变量，便于后台脚本复用同一套存取函数。
    """
    if base_dir is not None:
        return Path(base_dir).expanduser()
    try:
        configured = current_app.config.get("FILE_STORAGE_DIR")
    except RuntimeError:
        configured = None
    if not configured:
        configured = load_config()["FILE_STORAGE_DIR"]
    return Path(configured).expanduser()


def _path(storage_key: str, base_dir: str | Path | None = None) -> Path:
    if not isinstance(storage_key, str) or not _STORAGE_KEY.fullmatch(storage_key):
        raise ValueError("非法 storage_key")
    return _root(base_dir) / storage_key[:2] / storage_key


def save(data: bytes, storage_key: str, base_dir: str | Path | None = None) -> None:
    """写入字节；先写 ``.tmp`` 再原子替换，避免读到半成品。"""
    path = _path(storage_key, base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def load(storage_key: str, base_dir: str | Path | None = None) -> bytes:
    """读取字节；对象不存在时由 ``Path.read_bytes`` 抛 ``FileNotFoundError``。"""
    return _path(storage_key, base_dir).read_bytes()


def delete(storage_key: str, base_dir: str | Path | None = None) -> None:
    """删除对象，仅用于事务失败后的回滚；不存在时静默返回。"""
    _path(storage_key, base_dir).unlink(missing_ok=True)
