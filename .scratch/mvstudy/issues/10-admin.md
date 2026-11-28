# 10 — 在管理页启停账号并调整角色

**Parent:** [1 号 Spec](../../../docs/task-01-spec.md) · [共享契约与关闭规则](../../../docs/development.md)

**What to build:** 在管理页接 U3/U4，新增角色、调整权限、建立账号或停用账号；三类首页提供各自的功能入口。

**Blocked by:** [01 — 从空库登录并识别所属班级](01-login.md)

**Status:** done

- [x] 停用后用旧凭证发下一请求得 401；撤销教师权限或班级范围后原受限操作被拒。
- [x] 学生直访管理页和管理接口均被拒；管理员可看到已保存的角色及权限说明。

**验收证据：** PR #13 已于 2026-11-27 经 code-review 合入 `main`（合并提交 `8754cfa`，merge commit，7 个提交完整保留）。源分支 `feat/task-10-admin`，rebase 于 `71e6249`（含票 01 关票 PR #10 `ace2541`、F1 PR #11 `0a47637`、票 11 关票 PR #12 `71e6249`）。6 个实现提交按顺序为 `34c6328`（U3/U4 用例、6 个路由与权限码白名单）、`57a0dbc`（验收测试）、`3ab7ee6`（管理页与路由守卫）、`4d625cc`（运行说明与权限表）、`42c6fef`（票面证据）、`410133d`（对齐 F1 合入后的主干），另有 `799b201` 校正本段。合入后上述哈希在 `main` 上不再变化。本票不新增表，因此没有新迁移；仓库当前迁移单头仍为 `0002_platform_files (head)`（由票 11 引入）。

**rebase 冲突处理：** 与票 11 在 `platform/routes.py`、`platform/README.md` 两处重叠，均按“两票并存”解决——`routes.py` 保留 F1 的 `files` 两路由与 U3/U4 的 6 个端点、import 同时保留 `.admin` 与 `.files`，文档字符串统一为“U1–U5 与 F1”；`README.md` 的 F1 章节与管理接口章节、权限码表并存，标题与“本票边界”按 01/10/11 三票合并叙述。解决后 `pytest tests -q` 由 26 增至 42 passed，说明未丢失任一侧功能。

命令与结果（合入后于 `8754cfa` 上复跑）：`python -m pytest tests/test_platform_admin.py -q` → 12 passed；`python -m pytest tests -q` → 42 passed（12 管理 + 16 F1 + 10 身份 + 4 其他）；`python tools/check_layout.py` → 项目结构检查通过；`pyflakes backend/mvstudy/domains/platform/ tests/test_platform_admin.py tests/test_platform_files.py` → 无告警；`python -m alembic heads` → `0002_platform_files (head)` 单头；`npm --prefix frontend run build` → `vue-tsc` 无报错、构建成功。

测试覆盖：匿名访问三个管理入口均 401；学生对用户/角色读写全部 403；管理员列表不含 `password_hash`；新建账号 201 且可用新口令登录、同名再建 409 `login_taken`；停用 `s01` 后其旧凭证请求 `/api/me` 与 `/api/admin/users` 均 401、重新登录也 401，恢复启用后原凭证立即可用；把 `t02` 角色改为 `student` 后其旧凭证查本班名册由 200 变 404，改回后恢复 200；新建角色非法权限码 400 `invalid_permission`、重复 `role_id` 409 `role_exists`、改名与改权限 200 且列表可见；新建角色并挂账号后，`/api/me` 的 `permissions` 随角色权限增删即时变化；管理员不能停用自己（400）也不能移除自己角色的 `admin.roles`（400）；未知用户/角色 404；缺字段、只读字段（`password`、`role_id`）与空 PATCH 均 400。

**权限边界：** `platform/permissions.py` 是唯一取值域，当前只登记各域真正检查的 8 个码（`case.read`、`case.write`、`run.create`、`submission.write`、`grade.write`、`analytics.read`、`admin.users`、`admin.roles`）；未登记的码一律 `invalid_permission`。管理页的中文说明在 `frontend/src/features/platform/permission-notes.ts`，与后端同改同增。

**前端：** `/admin/users`、`/admin/roles` 由路由 `meta.permission` 守卫，缺权限回首页；首页按 `actor.permissions` 显示「用户管理」「角色权限」入口，学生与无管理权限者看不到。守卫只影响体验，后端对直接请求仍返回 403（已在测试中用学生凭证验证）。

**关闭记录：** PR #13 已于 2026-11-27 经 code-review 合入 `main`（合并提交 `8754cfa`，merge commit，7 个提交完整保留）。票 01 已随 PR #10 合入 `main`（`ace2541`），`Blocked by` 的 `done` 要求早已解除；F1 已随 PR #11 合入（`0a47637`），票 11 关票 PR #12 亦已合入（`71e6249`）。合入后主干复跑 `pytest tests -q`：42 passed；`alembic heads`：`0002_platform_files (head)` 单头；`tools/check_layout.py`：通过；`npm --prefix frontend run build`：成功。上述两条验收与测试证据在合并后的 `main` 上成立，状态置 `done`。下游 32 号票的 `Blocked by` 中本票部分由此解除，但它仍被 22、26 两票阻塞。
