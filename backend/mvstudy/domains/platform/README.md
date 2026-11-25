# 平台基础：身份、权限、班级与受控文件（01、11 号票）

本域提供 U1 登录、U2 当前身份、U5 班级名册、F1 受控文件，并交付全平台共用的应用工厂、Alembic 迁移入口与幂等开发种子。U3/U4 归 10 号票，P1 归 32 号票。

## 前置条件

- PostgreSQL 16，已建 `mvstudy` 与 `mvstudy_test` 两个库，属主为业务账号 `mvstudy`
- Python 3.12 及以上
- 连接串只从 `DATABASE_URL` 读取，默认 `postgresql+psycopg://mvstudy:mvstudy@127.0.0.1:5433/mvstudy`

首次使用先复制配置模板：

```bash
cp .env.example .env      # 按本机端口、口令修改
```

## 建库与迁移

在**仓库根**执行（`alembic.ini` 与 `migrations/` 都在根上，业务域内不放迁移）：

```bash
python -m alembic upgrade head
python -m alembic heads          # 期望只有一个 head
python -m alembic check          # 期望模型与库结构无差异
```

全部建表只走 Alembic，应用启动与测试都不调用 `create_all()`。

## 开发种子

两个班、三类角色、十一个账号，可重复执行：

```bash
cd backend
python -m mvstudy.domains.platform.seed
```

| 账号 | 角色 | 班级 |
|---|---|---|
| `a01` / `Admin@123` | 管理员 | — |
| `t01` / `Teach@123` | 教师 | c1 |
| `t02` / `Teach@123` | 教师 | c2 |
| `s01`–`s04` / `Stud@123` | 学生 | c1 |
| `s05`–`s08` / `Stud@123` | 学生 | c2 |

`t01` 与 `t02` 各教一个班，用于检验"教师查他班得 404"。若一人带两班，该校验无法成立。

## 测试

票级集成测试走隔离库 `mvstudy_test`，**不允许**以 SQLite 替代：

```bash
python -m pytest tests/test_platform_integration.py -q   # 01：登录、身份、班级
python -m pytest tests/test_platform_files.py -q         # 11：F1 文件与 0001→0002 升级
```

域内单元测试需要把 `backend` 放进 `PYTHONPATH`：

```bash
PYTHONPATH=backend python -m pytest backend/mvstudy/domains/platform -q
```

`unittest` 入口同样可用（团队旧基线沿用）：

```bash
python -m unittest discover -s tests
python -m unittest discover -s backend/mvstudy/domains/platform -t backend
```

结构约束检查（业务代码只在域目录、宿主不写路由、跨域只走公开入口）：

```bash
python tools/check_layout.py
```

测试通过 `alembic.command.upgrade(config, "head")` 在 `mvstudy_test` 上建表，因此测的是真实迁移产物，不是模型反射。`tests/test_platform_files.py` 另有一组升级路径测试：先升到 `0001_platform_identity` 并植入身份数据，再升到 `0002_platform_files`，断言用户数不变、原账号仍可登录且 `files` 表可用。

## 启动

```bash
cd backend
python -m flask --app mvstudy.app:create_app run --port 8000
```

前端 `vite.config.ts` 把 `/api` 代理到 `127.0.0.1:8000`，端口需一致。

## 手工验收

```bash
# U1 登录
curl -s -X POST http://127.0.0.1:8000/api/login \
  -H "Content-Type: application/json" \
  -d '{"login":"s01","password":"Stud@123"}'

# U2 取身份（TOKEN 换成上一步的 access_token）
curl -s http://127.0.0.1:8000/api/me -H "Authorization: Bearer TOKEN"

# 错误口令 → 401 invalid_credentials
curl -s -X POST http://127.0.0.1:8000/api/login \
  -H "Content-Type: application/json" -d '{"login":"s01","password":"wrong"}'

# 学生查他班名册 → 404 not_found（s01 属 c1，查 c2）
curl -s -o /dev/null -w "%{http_code}\n" \
  http://127.0.0.1:8000/api/classes/c2/members -H "Authorization: Bearer TOKEN"
```

错误响应统一为 `{"error":{"code":"…","message":"…"}}`。

## F1 受控文件（11 号票）

**存储分工。** 元信息写 `files` 表；字节写 `FILE_STORAGE_DIR` 下的私有卷。对象键是 32 位十六进制，按前两位分桶（`var/files/ab/ab…`），上传时先写 `.tmp` 再原子替换，读取方不会看到半成品。

**配置。** `.env` 中：

| 变量 | 含义 | 默认 |
|---|---|---|
| `FILE_STORAGE_DIR` | 私有卷根目录；相对路径按**仓库根**解析 | `./var/files` |
| `MAX_CONTENT_LENGTH` | **单个文件**的字节上限 | `524288`（512 KiB） |

`var/` 已在 `.gitignore` 中忽略。multipart 的边界与头部另有开销，因此 Flask 的请求体上限自动放宽 64 KiB；精确校验在 `create_file()` 内按文件字节数完成，恰好等于上限的文件允许上传。

**接口。**

```bash
# 上传：multipart 字段名固定为 file；成功 201
curl -s -X POST http://127.0.0.1:8000/api/files \
  -H "Authorization: Bearer TOKEN" \
  -F "file=@./main.py;type=text/x-python"

# 取回：仅所有者可读；他人与不存在都返回 404
curl -s -o out.py -D - http://127.0.0.1:8000/api/files/f-xxxxxxxxxxxx \
  -H "Authorization: Bearer TOKEN"
```

成功响应固定为 `{file_id,name,media_type,byte_size}`，不回传 `owner_id`、`storage_key`、`created_at`。下载使用经过清理的原文件名；磁盘路径从不使用原文件名。

**关键约束。**

- 内容不可覆盖：每次上传生成新 `file_id` 与新 `storage_key`，没有覆盖或更新接口；同名文件得到不同编号。
- 越权读返回 `404 not_found` 而非 403，不泄露文件是否存在。
- 超限返回 `413 payload_too_large`；先校验字节数，再建记录与写盘，失败不留数据库行或磁盘对象。
- `GET /files/{file_id}` 当前只授权给**所有者**。材料、运行产物、提交附件等“按资源授权”的读取由 2/3/9 号在自己的接口内校验关联关系后调用 `read_bytes()`；本域不提前猜测其他域的关联表。这是 11 号票的交付边界：F1 只提供所有者读取与同进程原语，不得把 `file_id` 当作访问凭证。
- 媒体类型取 multipart 声明的 `type/subtype`，非法值退回 `application/octet-stream`；不按扩展名推断。

**限额与 9 号移交。**

| 层级 | 限额 | 执行方 | 11 号是否实现 |
|---|---|---|---|
| F1 单文件 | 512 KiB（仓库联调默认） | 1 号 | 是，`create_file()` 精确校验 |
| 压缩包整包 | 10 MiB（常规教学作业包默认） | 9 号 S1 | 否 |
| 包内成员数 | 200 | 9 号 S1 | 否 |
| 展开总量 | 50 MiB | 9 号 S1 | 否 |

整包、成员数与展开总量由 9 号在接收和解包时校验；11 号不解析压缩包。若 17 号需要经 F1 上传大于 512 KiB 的整包，应另行调整 F1 上限，不在本票为压缩包单独放宽。9 号后续公布不同值时，以 9 号接口为准。

**给 2/3/9 号的同进程用例**（不经 HTTP）：

| 函数 | 位置 | 用途 |
|---|---|---|
| `create_file(session, actor, *, name, media_type, data, max_bytes=None, base_dir=None)` | `files.py` | 新建记录并落盘；超限抛 `FileTooLarge`，参数不合法抛 `InvalidFile`；失败自动回滚并删盘 |
| `read_bytes(session, file_id, base_dir=None)` | `files.py` | **内部读取**；只校验文件存在，不校验调用者身份，调用方必须先完成资源授权 |
| `get_owned_file(session, actor, file_id)` | `files.py` | 按所有者取记录，他人文件返回 `None` |
| `File`、`file_meta(row)` | `models.py`、`files.py` | 模型与 F1 响应字段组装 |

`base_dir` 供 3 号独立计算进程使用；不传时依次取 Flask 配置、环境变量。`read_bytes()` 的红线写在函数 docstring 中，禁止直接挂到 HTTP。

**手工验收清单。**

```bash
printf 'hello mvstudy\n' > /tmp/t.txt
# 1) 上传 201，记下 file_id
# 2) 用同一 TOKEN GET，字节应为 hello mvstudy
# 3) 换 s02 的 TOKEN GET，应为 404
# 4) 去掉 Authorization，应为 401
# 5) 传超过 MAX_CONTENT_LENGTH 的文件，应为 413，且 files 表与 var/files 均无新增
# 6) 同名再传，file_id 应不同
```

## 给其他域的装配边界

**`g.current_actor`** 由宿主 `create_app()` 在每个请求注入，结构逐字等同 U2 响应：

```python
{
  "user_id": "u-s01",
  "display_name": "李同学",
  "role_id": "student",
  "permissions": ["case.read", "submission.write"],
  "classes": [{"class_id": "c1", "relation": "student"}],
}
```

未登录或凭证失效时为 `None`。8 号 `analytics/routes.py` 已按此结构读取，改动字段会直接破坏其调用。

**授权逐次查库。** JWT 只携带 `user_id`；`enabled`、角色权限与班级关系每次请求重新读取。因此停用账号或撤销权限后，旧凭证的下一个请求即失效，无需等待 token 过期。

**`create_review_demo()` 必须保留。** 它是 7 号评审的独立演示入口，被其测试引用。23 号票接入统一身份之前，正式 `create_app()` 不注册 review 蓝图。

**对外可复用的用例函数**（不经 HTTP 亦可直接调用，2/4/8/9 号按需使用）：

| 函数 | 位置 | 用途 |
|---|---|---|
| `login(session, login_name, password, secret, ttl_minutes)` | `identity.py` | 校验口令并签发凭证，失败抛 `AuthError` |
| `load_current_actor(session, user_id)` | `identity.py` | 组装 U2 结构；停用或不存在返回 `None` |
| `list_members(session, actor, class_id, relation)` | `classes.py` | 返回名册项；无权限返回 `None` |
| `create_file(...)` / `read_bytes(...)` | `files.py` | F1 写入与内部读取，详见上一节 |

## 本票边界

不含：用户启停与角色权限维护（U3/U4，10 号票）、三类首页指标（P1，32 号票）。F1 已由 11 号票交付；跨资源的下载授权（材料、运行产物、提交附件）由 2/3/9 号在各自接口内完成。前端图形界面的登录跳转与刷新恢复需人工点验，自动化只覆盖构建与接口。
