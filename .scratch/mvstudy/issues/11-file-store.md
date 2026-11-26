# 11 — 凭文件编号上传和取回受控内容

**Parent:** [1 号 Spec](../../../docs/task-01-spec.md) · [共享契约与关闭规则](../../../docs/development.md)

**What to build:** 实现 F1 和同一后端使用的写入能力；字节存私有持久目录，元信息写库。各挂接模块按用途提供授权。

**Blocked by:** [01 — 从空库登录并识别所属班级](01-login.md)

**Status:** ready-for-agent（实现已就绪，待评审合入后置 done）

- [x] 上传后刷新仍可读出相同字节；同名再上传产生不同 file_id。
- [x] 其他学生读取未授权文件返回 404；非法内容或超限失败后无可访问的半成品。

**验收证据：** 分支 `feat/task-11-files`，已 rebase 到含票 01 关票（PR #10，合并提交 `ace2541`）的 `main`。实现提交 `e1e376f`（F1 与迁移）、`39477b9`（验收与升级测试）、`795468f`、`b98389d`（运行说明、限额与宿主 413 行为）。迁移 `migrations/versions/0002_platform_files.py`（`files` 表，`storage_key` 唯一，`owner_id` 外键）；用例 `platform/files.py`、私有卷 `platform/storage.py`、路由 `platform/routes.py`。`python -m pytest tests/test_platform_files.py -q`：16 passed；`python -m pytest tests -q`：30 passed；`python tools/check_layout.py`：通过；`python -m alembic heads`：`0002_platform_files (head)` 单头；`python -m alembic check`：无差异；`pyflakes backend/mvstudy/domains/platform/ tests/test_platform_files.py`：无告警。

测试覆盖：上传后二次请求取回相同字节、同名再传编号不同、重复 upgrade 后文件仍可读、**从 `0001_platform_identity` 升级到 `0002_platform_files` 后原用户数不变且原账号仍可登录**、他人读 404、未知编号 404、元信息在而对象缺失按 404、非法 `storage_key` 拒绝路径穿越、未登录 401、缺 `file` 字段 400、恰好等于上限可传、超一字节 413、请求体级超限也返回 JSON 413、失败后表与磁盘零残留、NUL 文件名在入库前拒绝、非法媒体类型退回通用类型、内部 `create_file`/`read_bytes` 同进程可用、每个方法与路径唯一处理器。

**限额：** F1 单文件按仓库联调默认 **512 KiB**（`MAX_CONTENT_LENGTH=524288`），已写入 `platform/README.md` 与 `.env.example`。9 号的 S1 整包、成员数与展开总量按常规教学作业包默认处理：**整包 10 MiB、成员 200、展开 50 MiB**，由 9 号在接收和解包时校验；11 号不解析压缩包。若 17 号需要经 F1 上传大于 512 KiB 的整包，应另行调整 F1 上限，不在本票放宽。

**授权边界：** `GET /files/{file_id}` 只授权所有者；材料、运行产物、提交附件的关联授权由 2/3/9 号在各自接口完成，再调用 `read_bytes()`。这与本票“各挂接模块按用途提供授权”的边界一致，`file_id` 不作为访问凭证。

**关闭前置已完成，待评审合入：** 票 01 已随 PR #10 合入 `main`（合并提交 `ace2541`），`Blocked by` 的 `done` 要求已解除。本票代码、测试与文档已推送 fork 的 `feat/task-11-files`，尚未开 PR、未经 code-review、未合入集成分支；按 `docs/development.md` 需合入并评审后才置 `done`。2 号的 12 号票在 F1 合入前不应解锁。
