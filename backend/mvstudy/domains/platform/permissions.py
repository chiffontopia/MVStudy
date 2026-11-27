"""权限码白名单。

`roles.permissions` 的取值域只有这里列出的码；U4 新建或修改角色时按本表校验，
未登记的码一律以 `invalid_permission` 拒绝，避免出现无人校验的“空权限”。

新增权限码的条件：某个域真的在入口处检查它。只登记已投入使用的码，
否则管理页的权限说明会变成没有实际约束的装饰。
"""

from __future__ import annotations

PERMISSIONS: dict[str, str] = {
    "case.read": "查看案例、材料与算法目录",
    "case.write": "维护案例与材料版本",
    "run.create": "提交算法运行",
    "submission.write": "提交作业版本",
    "grade.write": "批改作业与写入成绩",
    "analytics.read": "读取班级学情与周报",
    "admin.users": "管理用户：列表、新建、启停",
    "admin.roles": "管理角色与权限",
}


def invalid_codes(codes: list[str]) -> list[str]:
    """按入参顺序返回不在白名单内的权限码。"""
    return [code for code in codes if code not in PERMISSIONS]
