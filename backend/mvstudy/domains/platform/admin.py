"""U3/U4 用例：管理员维护账号与角色。

授权判断集中在这里：路由只负责取当前身份与映射错误码。
JWT 只携带 user_id，`enabled`、角色与权限每次请求重新查库，
因此停用账号或改动权限后，旧凭证的下一个请求即按新授权执行。
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Role, User
from .permissions import invalid_codes
from .security import hash_password

MANAGE_USERS = "admin.users"
MANAGE_ROLES = "admin.roles"
USER_WRITABLE = ("display_name", "role_id", "enabled")
ROLE_WRITABLE = ("name", "permissions")


class AdminError(Exception):
    """管理操作失败；携带对外错误码与 HTTP 状态。"""

    def __init__(self, code: str, message: str, status: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def _require(actor: dict[str, Any] | None, code: str) -> dict[str, Any]:
    """管理员且持有指定功能权限码；否则一律 403，不区分缺角色还是缺权限。"""
    permissions = (actor or {}).get("permissions") or []
    if not actor or actor.get("role_id") != "admin" or code not in permissions:
        raise AdminError("forbidden", "需要管理员权限。", 403)
    return actor


def _invalid(message: str) -> AdminError:
    return AdminError("invalid_params", message, 400)


def _body(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise _invalid("请求内容必须是 JSON 对象。")
    return payload


def _text(body: dict[str, Any], key: str) -> str:
    value = body.get(key)
    if not isinstance(value, str) or not value.strip():
        raise _invalid(f"{key} 必须是非空字符串。")
    return value.strip()


def _only_fields(body: dict[str, Any], allowed: tuple[str, ...]) -> None:
    unknown = sorted(set(body) - set(allowed))
    if unknown:
        raise _invalid(f"不支持修改字段：{'、'.join(unknown)}。")


def _permissions(body: dict[str, Any]) -> list[str]:
    value = body.get("permissions")
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise _invalid("permissions 必须是字符串数组。")
    codes = list(dict.fromkeys(value))
    rejected = invalid_codes(codes)
    if rejected:
        raise AdminError("invalid_permission", f"未登记的权限码：{'、'.join(rejected)}。", 400)
    return codes


def _role_exists(session: Session, role_id: str) -> None:
    if session.get(Role, role_id) is None:
        raise _invalid(f"角色不存在：{role_id}。")


def _next_user_id(session: Session) -> str:
    while True:
        candidate = f"u-{uuid4().hex[:8]}"
        if session.get(User, candidate) is None:
            return candidate


def _user_view(user: User) -> dict[str, Any]:
    """对外只返回展示与授权所需字段，绝不包含 password_hash。"""
    return {
        "user_id": user.user_id,
        "login": user.login,
        "display_name": user.display_name,
        "role_id": user.role_id,
        "enabled": user.enabled,
    }


def _role_view(role: Role) -> dict[str, Any]:
    return {"role_id": role.role_id, "name": role.name, "permissions": list(role.permissions)}


def list_users(session: Session, actor: dict[str, Any] | None) -> list[dict[str, Any]]:
    _require(actor, MANAGE_USERS)
    users = session.scalars(select(User).order_by(User.login)).all()
    return [_user_view(user) for user in users]


def create_user(
    session: Session, actor: dict[str, Any] | None, payload: Any
) -> dict[str, Any]:
    _require(actor, MANAGE_USERS)
    body = _body(payload)
    _only_fields(body, ("login", "display_name", "password", "role_id"))
    login_name = _text(body, "login")
    display_name = _text(body, "display_name")
    password = _text(body, "password")
    role_id = _text(body, "role_id")
    _role_exists(session, role_id)
    if session.scalar(select(User.user_id).where(User.login == login_name)) is not None:
        raise AdminError("login_taken", "登录名已被占用。", 409)

    user = User(
        user_id=_next_user_id(session),
        login=login_name,
        display_name=display_name,
        password_hash=hash_password(password),
        role_id=role_id,
        enabled=True,
    )
    session.add(user)
    session.commit()
    return _user_view(user)


def update_user(
    session: Session, actor: dict[str, Any] | None, user_id: str, payload: Any
) -> dict[str, Any]:
    _require(actor, MANAGE_USERS)
    body = _body(payload)
    _only_fields(body, USER_WRITABLE)
    if not body:
        raise _invalid("至少提供一个可修改字段。")

    user = session.get(User, user_id)
    if user is None:
        raise AdminError("not_found", "用户不存在。", 404)

    # 先校验全部入参，再落库，避免半途失败留下部分修改。
    display_name = _text(body, "display_name") if "display_name" in body else None
    role_id = None
    if "role_id" in body:
        role_id = _text(body, "role_id")
        _role_exists(session, role_id)
    enabled = None
    if "enabled" in body:
        if not isinstance(body["enabled"], bool):
            raise _invalid("enabled 必须是布尔值。")
        if user.user_id == (actor or {}).get("user_id") and body["enabled"] is False:
            raise _invalid("不能停用当前登录的管理员账号。")
        enabled = body["enabled"]

    if display_name is not None:
        user.display_name = display_name
    if role_id is not None:
        user.role_id = role_id
    if enabled is not None:
        user.enabled = enabled

    session.commit()
    return _user_view(user)


def list_roles(session: Session, actor: dict[str, Any] | None) -> list[dict[str, Any]]:
    _require(actor, MANAGE_ROLES)
    roles = session.scalars(select(Role).order_by(Role.role_id)).all()
    return [_role_view(role) for role in roles]


def create_role(
    session: Session, actor: dict[str, Any] | None, payload: Any
) -> dict[str, Any]:
    _require(actor, MANAGE_ROLES)
    body = _body(payload)
    _only_fields(body, ("role_id", *ROLE_WRITABLE))
    role_id = _text(body, "role_id")
    name = _text(body, "name")
    permissions = _permissions(body)
    if session.get(Role, role_id) is not None:
        raise AdminError("role_exists", "角色键已存在。", 409)

    role = Role(role_id=role_id, name=name, permissions=permissions)
    session.add(role)
    session.commit()
    return _role_view(role)


def update_role(
    session: Session, actor: dict[str, Any] | None, role_id: str, payload: Any
) -> dict[str, Any]:
    _require(actor, MANAGE_ROLES)
    body = _body(payload)
    _only_fields(body, ROLE_WRITABLE)
    if not body:
        raise _invalid("至少提供一个可修改字段。")

    role = session.get(Role, role_id)
    if role is None:
        raise AdminError("not_found", "角色不存在。", 404)

    name = _text(body, "name") if "name" in body else None
    permissions = _permissions(body) if "permissions" in body else None
    if (
        permissions is not None
        and role.role_id == (actor or {}).get("role_id")
        and MANAGE_ROLES not in permissions
    ):
        raise _invalid("不能移除当前管理员角色的 admin.roles 权限。")

    if name is not None:
        role.name = name
    if permissions is not None:
        role.permissions = permissions

    session.commit()
    return _role_view(role)
