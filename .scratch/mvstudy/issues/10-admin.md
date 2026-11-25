# 10 — 在管理页启停账号并调整角色

**Parent:** [1 号 Spec](../../../docs/task-01-spec.md) · [共享契约与关闭规则](../../../docs/development.md)

**What to build:** 在管理页接 U3/U4，新增角色、调整权限、建立账号或停用账号；三类首页提供各自的功能入口。

**Blocked by:** [01 — 从空库登录并识别所属班级](01-login.md)

**Status:** ready-for-agent（实现已就绪，待 PR 合入后置 done）

- [x] 停用后用旧凭证发下一请求得 401；撤销教师权限或班级范围后原受限操作被拒。
- [x] 学生直访管理页和管理接口均被拒；管理员可看到已保存的角色及权限说明。

**验收证据：** 分支 `feat/task-10-admin`，基于 `origin/main` 的 `d7c50d5`。实现提交 `36de018`（U3/U4 用例与 6 个路由、权限码白名单）、`7fa74ce`（验收测试）、`dce86cc`（管理页与路由守卫）、`0bb19ae`（运行说明与权限表）。本票不新增表，因此没有新迁移，`alembic heads` 仍为 `0001_platform_identity (head)` 单头。

命令与结果：`python -m pytest tests/test_platform_admin.py -q` → 12 passed；`python -m pytest tests -q` → 26 passed；`python -m unittest discover -s tests` → 26 tests OK；`python tools/check_layout.py` → 项目结构检查通过；`pyflakes backend/mvstudy/domains/platform/ tests/test_platform_admin.py` → 无告警；`alembic check`（对测试库）→ 无待生成差异；`npm --prefix frontend run build` → `vue-tsc` 无报错、构建成功。

测试覆盖：匿名访问三个管理入口均 401；学生对用户/角色读写全部 403；管理员列表不含 `password_hash`；新建账号 201 且可用新口令登录、同名再建 409 `login_taken`；停用 `s01` 后其旧凭证请求 `/api/me` 与 `/api/admin/users` 均 401、重新登录也 401，恢复启用后原凭证立即可用；把 `t02` 角色改为 `student` 后其旧凭证查本班名册由 200 变 404，改回后恢复 200；新建角色非法权限码 400 `invalid_permission`、重复 `role_id` 409 `role_exists`、改名与改权限 200 且列表可见；新建角色并挂账号后，`/api/me` 的 `permissions` 随角色权限增删即时变化；管理员不能停用自己（400）也不能移除自己角色的 `admin.roles`（400）；未知用户/角色 404；缺字段、只读字段（`password`、`role_id`）与空 PATCH 均 400。

**权限边界：** `platform/permissions.py` 是唯一取值域，当前只登记各域真正检查的 8 个码（`case.read`、`case.write`、`run.create`、`submission.write`、`grade.write`、`analytics.read`、`admin.users`、`admin.roles`）；未登记的码一律 `invalid_permission`。管理页的中文说明在 `frontend/src/features/platform/permission-notes.ts`，与后端同改同增。

**前端：** `/admin/users`、`/admin/roles` 由路由 `meta.permission` 守卫，缺权限回首页；首页按 `actor.permissions` 显示「用户管理」「角色权限」入口，学生与无管理权限者看不到。守卫只影响体验，后端对直接请求仍返回 403（已在测试中用学生凭证验证）。

**关闭前置未完成：** 实现、测试与文档已提交到本地分支，但尚未推送 fork、未开 PR、未 code-review、未合入集成分支。另：票 01 的 `done` 提交仍在 PR #10，未合入 `main`，`Blocked by` 的 `done` 状态要求待该 PR 合入后解除。
