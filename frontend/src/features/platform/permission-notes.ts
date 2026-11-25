/**
 * 权限码的中文说明。
 *
 * 码本身由后端 `platform/permissions.py` 校验；这里只负责让管理页把
 * “这个码能做什么”讲清楚。新增权限码时两处要一起登记。
 */

export type PermissionNote = {
  code: string;
  label: string;
  scope: string;
};

export const PERMISSION_NOTES: PermissionNote[] = [
  { code: "case.read", label: "查看案例", scope: "案例、材料与算法目录" },
  { code: "case.write", label: "维护案例", scope: "创建与修改案例、材料版本" },
  { code: "run.create", label: "提交运行", scope: "提交算法运行请求" },
  { code: "submission.write", label: "提交作业", scope: "提交自己的作业版本" },
  { code: "grade.write", label: "批改与成绩", scope: "批改作业、写入成绩" },
  { code: "analytics.read", label: "读取学情", scope: "班级学情与周报" },
  { code: "admin.users", label: "管理用户", scope: "用户列表、新建、启停" },
  { code: "admin.roles", label: "管理角色", scope: "角色与权限配置" },
];

export const PERMISSION_CODES = PERMISSION_NOTES.map((item) => item.code);

export function permissionNote(code: string): PermissionNote {
  return PERMISSION_NOTES.find((item) => item.code === code) ?? { code, label: code, scope: "未登记的权限码" };
}
