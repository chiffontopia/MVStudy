"""1 号业务域：身份、班级、权限、受控文件、三类首页。

对外只导出跨域需要的用例；模型与私有函数留在域内。
"""

from .classes import list_members
from .files import FileTooLarge, InvalidFile, create_file, read_bytes
from .identity import AuthError, load_current_actor, login
from .models import ClassMember, File, Role, SchoolClass, User

__all__ = [
    "AuthError",
    "ClassMember",
    "File",
    "FileTooLarge",
    "InvalidFile",
    "Role",
    "SchoolClass",
    "User",
    "create_file",
    "list_members",
    "load_current_actor",
    "login",
    "read_bytes",
]
