# 01 — 从空库登录并识别所属班级

**Parent:** [1 号 Spec](../../../docs/task-01-spec.md) · [共享契约与关闭规则](../../../docs/development.md)

**What to build:** 在正式 Flask 应用中，用预置学生或教师登录，页面显示当前身份与所属班级。此票交付共享应用工厂、数据库迁移入口、Vue 登录与路由宿主及 U1/U2/U5。1 号提供从仓库根运行 Alembic 的配置和幂等的开发种子入口。

**Blocked by:** None — can start immediately

**Status:** done

- [x] 在新 PostgreSQL 16 数据库执行 alembic upgrade head，植入两班样例；正确口令返回凭证，U2 的授权来自数据库。
- [x] 错误口令返回 401；学生查询他班名册得 404。刷新后仍是原身份。
- [x] 第二次升到 head 后原用户仍可登录；测试走同一套迁移。
- [x] 登录行为放在 `platform` 域；Flask 宿主只注册 Blueprint。用应用工厂生成的 URL 映射做集成检查：每对 HTTP 方法与路径只由一个处理器提供，后续注册新域时沿用此检查。

**验收证据：** 源分支 `feat/task-01-login`（5 个提交 `8aff8a6`→`c4ca06c`→`e345679`→`d7483ed`→`915345e`），经 fork `hhhjayson/MVStudy` 提交 PR #8，已合入集成分支 `main`，合并提交 `ff181a9`。迁移 `migrations/versions/0001_platform_identity.py`（`roles`/`classes`/`users`/`class_members`，无 `create_all`）。`python -m pytest tests/test_platform_integration.py -q`：10 passed；`PYTHONPATH=backend python -m pytest backend/mvstudy/domains/platform -q`：6 passed；`python tools/check_layout.py`：项目结构检查通过；`pyflakes backend/mvstudy/domains/platform/`：无告警。全部测试经 `command.upgrade(config, "head")` 对隔离库 `mvstudy_test` 建表后运行。运行说明见 `backend/mvstudy/domains/platform/README.md`。

**前端人工点验（2026-11-23，Edge）：** 未登录访问 `/` 跳转 `/login`；`s01`/`Stud@123` 登录后显示“李同学 / 学生 · u-s01 / c1（在读）/ case.read、submission.write”；按 F5 仍停留首页，不回登录页；错密码显示“登录名或密码不正确”。注：U2 的 `classes` 只含 `class_id` 与 `relation`，不含班名，故显示 `c1（在读）` 符合契约。

四条验收的对应测试：`test_login_issues_token_and_me_reads_database`（凭证签发、U2 直读数据库：改库后同一 token 立即生效）、`test_second_upgrade_keeps_existing_accounts`（二次 upgrade 后原用户仍可登录）、`test_wrong_password_and_missing_credentials` 与 `test_student_cannot_read_other_class_roster`（401/404）、`test_each_method_and_path_has_one_handler`（URL 映射唯一性）。应用工厂映射仅 `/api/login`(POST)、`/api/me`(GET)、`/api/classes/<class_id>/members`(GET) 三条业务路由，宿主只做 `register_blueprint`。

**关闭记录：** PR #8 已于 2026-11-23 经 code-review 合入 `main`（合并提交 `ff181a9`），上述四条验收与测试证据在合并后的 `main` 上成立，状态置 `done`。下游（12/13/15/23 等）自此解锁；它们仍须各自满足自身的 `Blocked by` 与技术基线，不因本票完成而免除。
