"""1 号域模型：身份、班级与受控文件。字段、约束以 docs/database.md 为准。

本域独占写入：roles、users、classes、class_members、files。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from mvstudy.db import Base

RELATIONS = ("teacher", "student")


class Role(Base):
    """角色键与功能权限码；班级范围另行由 class_members 决定。"""

    __tablename__ = "roles"

    role_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    permissions: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )


class User(Base):
    """登录账号。密码只存摘要，接口不回传本表任何敏感字段。"""

    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    login: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role_id: Mapped[str] = mapped_column(
        ForeignKey("roles.role_id", name="fk_users_role"), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class SchoolClass(Base):
    """班级。名册用预置数据导入，不做教务排课。"""

    __tablename__ = "classes"

    class_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)


class ClassMember(Base):
    """班内关系，是各项班级范围授权的唯一来源。"""

    __tablename__ = "class_members"
    __table_args__ = (
        CheckConstraint("relation IN ('teacher', 'student')", name="ck_class_members_relation"),
        Index("ix_class_members_user_id", "user_id"),
    )

    class_id: Mapped[str] = mapped_column(
        ForeignKey("classes.class_id", name="fk_class_members_class"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.user_id", name="fk_class_members_user"), primary_key=True
    )
    relation: Mapped[str] = mapped_column(Text, nullable=False)


class File(Base):
    """受控文件元信息；字节存放在私有卷，不在数据库。

    ``file_id`` 面向调用方且不可变；``storage_key`` 只用于定位磁盘对象，
    不对外暴露。新内容一律生成新行，不提供覆盖路径。
    """

    __tablename__ = "files"
    __table_args__ = (UniqueConstraint("storage_key", name="uq_files_storage_key"),)

    file_id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.user_id", name="fk_files_owner"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[str] = mapped_column(Text, nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
