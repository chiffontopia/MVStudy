"""票 11 验收：F1 受控文件上传与取回。

全部走隔离 PostgreSQL 库与临时私有目录，不使用 create_all()。
运行：python -m pytest tests/test_platform_files.py -q
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from mvstudy.app import create_app
from mvstudy.db import build_engine, build_session_factory
from mvstudy.domains.platform.files import InvalidFile, create_file, read_bytes
from mvstudy.domains.platform.identity import login as login_use_case
from mvstudy.domains.platform.seed import seed

TEST_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://mvstudy:mvstudy@127.0.0.1:5433/mvstudy_test",
)

STUDENT = {"login": "s01", "password": "Stud@123"}
OTHER_STUDENT = {"login": "s02", "password": "Stud@123"}
FILE_LIMIT = 1024


def alembic_config() -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", TEST_URL)
    return config


def run_sql(statement: str, params: dict | None = None) -> None:
    engine = build_engine(TEST_URL)
    try:
        with engine.begin() as connection:
            connection.execute(text(statement), params or {})
    finally:
        engine.dispose()


def scalar_sql(statement: str):
    engine = build_engine(TEST_URL)
    try:
        with engine.connect() as connection:
            return connection.execute(text(statement)).scalar_one()
    finally:
        engine.dispose()


class PlatformFilesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.previous_url = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = TEST_URL
        cls.storage_dir = tempfile.mkdtemp(prefix="mvstudy-files-")
        run_sql("DROP SCHEMA IF EXISTS public CASCADE")
        run_sql("CREATE SCHEMA public")
        command.upgrade(alembic_config(), "head")
        session = build_session_factory(build_engine(TEST_URL))()
        try:
            seed(session)
        finally:
            session.close()
        cls.app = create_app(
            {
                "DATABASE_URL": TEST_URL,
                "TESTING": True,
                "FILE_STORAGE_DIR": cls.storage_dir,
                "MAX_FILE_BYTES": FILE_LIMIT,
            }
        )

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.storage_dir, ignore_errors=True)
        if cls.previous_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = cls.previous_url

    def setUp(self) -> None:
        run_sql("DELETE FROM files")
        shutil.rmtree(self.storage_dir, ignore_errors=True)
        Path(self.storage_dir).mkdir(parents=True, exist_ok=True)

    def client(self):
        return self.app.test_client()

    def login(self, account: dict) -> str:
        response = self.client().post("/api/login", json=account)
        self.assertEqual(response.status_code, 200, response.json)
        return response.json["access_token"]

    def auth(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    def upload(
        self,
        token: str,
        data: bytes = b"hello mvstudy\n",
        filename: str = "t.txt",
        media_type: str = "text/plain",
    ):
        return self.client().post(
            "/api/files",
            headers=self.auth(token),
            data={"file": (BytesIO(data), filename, media_type)},
            content_type="multipart/form-data",
        )

    def stored_objects(self) -> list[Path]:
        return [path for path in Path(self.storage_dir).rglob("*") if path.is_file()]

    def file_count(self) -> int:
        engine = build_engine(TEST_URL)
        try:
            with engine.connect() as connection:
                return connection.execute(text("SELECT count(*) FROM files")).scalar_one()
        finally:
            engine.dispose()

    def test_upload_then_download_returns_same_bytes(self):
        token = self.login(STUDENT)
        payload = b"hello mvstudy\n"
        response = self.upload(token, payload)

        self.assertEqual(response.status_code, 201, response.json)
        self.assertEqual(
            set(response.json), {"file_id", "name", "media_type", "byte_size"}
        )
        self.assertEqual(response.json["name"], "t.txt")
        self.assertEqual(response.json["media_type"], "text/plain")
        self.assertEqual(response.json["byte_size"], len(payload))

        # 第二次请求重新读库与读盘，验证刷新后仍能取回相同字节。
        download = self.client().get(
            f"/api/files/{response.json['file_id']}", headers=self.auth(token)
        )
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.data, payload)
        self.assertIn("filename=t.txt", download.headers["Content-Disposition"])

    def test_same_name_upload_creates_new_file_id(self):
        token = self.login(STUDENT)
        first = self.upload(token, b"first\n", "same.txt")
        second = self.upload(token, b"second\n", "same.txt")

        self.assertEqual(first.status_code, 201, first.json)
        self.assertEqual(second.status_code, 201, second.json)
        self.assertNotEqual(first.json["file_id"], second.json["file_id"])
        self.assertEqual(self.client().get(
            f"/api/files/{first.json['file_id']}", headers=self.auth(token)
        ).data, b"first\n")
        self.assertEqual(self.client().get(
            f"/api/files/{second.json['file_id']}", headers=self.auth(token)
        ).data, b"second\n")

    def test_other_student_gets_404(self):
        owner_token = self.login(STUDENT)
        file_id = self.upload(owner_token).json["file_id"]

        response = self.client().get(
            f"/api/files/{file_id}", headers=self.auth(self.login(OTHER_STUDENT))
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json["error"]["code"], "not_found")

    def test_unknown_file_id_is_404(self):
        response = self.client().get(
            "/api/files/f-does-not-exist", headers=self.auth(self.login(STUDENT))
        )
        self.assertEqual(response.status_code, 404)

    def test_missing_object_is_404_not_500(self):
        # 元信息在、私有卷对象被误删时，按不可读处理，不泄露内部状态。
        token = self.login(STUDENT)
        file_id = self.upload(token).json["file_id"]
        for path in self.stored_objects():
            path.unlink()
        response = self.client().get(f"/api/files/{file_id}", headers=self.auth(token))
        self.assertEqual(response.status_code, 404)

    def test_storage_rejects_keys_outside_the_hex_namespace(self):
        from mvstudy.domains.platform import storage

        for key in ("../escape", "A" * 32, "a" * 31, "a" * 33, "a" * 31 + "/"):
            with self.assertRaises(ValueError, msg=key):
                storage.save(b"x", key, base_dir=self.storage_dir)
        self.assertEqual(self.stored_objects(), [])

    def test_unauthenticated_upload_and_download_are_401(self):
        self.assertEqual(self.upload_without_token().status_code, 401)

        token = self.login(STUDENT)
        file_id = self.upload(token).json["file_id"]
        self.assertEqual(self.client().get(f"/api/files/{file_id}").status_code, 401)

    def upload_without_token(self):
        return self.client().post(
            "/api/files",
            data={"file": (BytesIO(b"x"), "t.txt", "text/plain")},
            content_type="multipart/form-data",
        )

    def test_missing_file_field_is_400(self):
        response = self.client().post(
            "/api/files",
            headers=self.auth(self.login(STUDENT)),
            data={},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["error"]["code"], "invalid_files")
        self.assertEqual(self.file_count(), 0)
        self.assertEqual(self.stored_objects(), [])

    def test_exact_limit_is_allowed_and_one_byte_over_is_413(self):
        token = self.login(STUDENT)
        allowed = self.upload(token, b"a" * FILE_LIMIT, "limit.txt")
        self.assertEqual(allowed.status_code, 201, allowed.json)
        self.assertEqual(allowed.json["byte_size"], FILE_LIMIT)

        before_rows = self.file_count()
        before_objects = len(self.stored_objects())
        rejected = self.upload(token, b"a" * (FILE_LIMIT + 1), "over.txt")
        self.assertEqual(rejected.status_code, 413, rejected.json)
        self.assertEqual(rejected.json["error"]["code"], "payload_too_large")
        self.assertEqual(self.file_count(), before_rows)
        self.assertEqual(len(self.stored_objects()), before_objects)

    def test_transport_level_oversize_returns_json_413(self):
        response = self.upload(
            self.login(STUDENT), b"a" * (FILE_LIMIT + 128 * 1024), "huge.txt"
        )
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json["error"]["code"], "payload_too_large")
        self.assertEqual(self.file_count(), 0)
        self.assertEqual(self.stored_objects(), [])

    def test_download_name_is_sanitized(self):
        token = self.login(STUDENT)
        response = self.upload(token, b"x", "../../evil.txt")
        self.assertEqual(response.status_code, 201, response.json)

        download = self.client().get(
            f"/api/files/{response.json['file_id']}", headers=self.auth(token)
        )
        disposition = download.headers["Content-Disposition"]
        self.assertNotIn("/", disposition)
        self.assertNotIn("\\", disposition)

    def test_internal_create_and_read_use_case(self):
        client = self.client()
        token = self.login(STUDENT)
        actor = client.get("/api/me", headers=self.auth(token)).json

        session = build_session_factory(build_engine(TEST_URL))()
        try:
            row = create_file(
                session,
                actor,
                name="internal.py",
                media_type="text/x-python",
                data=b"print('ok')\n",
                max_bytes=FILE_LIMIT,
                base_dir=self.storage_dir,
            )
        finally:
            session.close()

        self.assertEqual(row.name, "internal.py")
        self.assertEqual(row.owner_id, actor["user_id"])
        reader = build_session_factory(build_engine(TEST_URL))()
        try:
            self.assertEqual(
                read_bytes(reader, row.file_id, base_dir=self.storage_dir),
                b"print('ok')\n",
            )
        finally:
            reader.close()

    def test_invalid_name_and_media_type_are_handled(self):
        actor = self.client().get(
            "/api/me", headers=self.auth(self.login(STUDENT))
        ).json

        rejected = build_session_factory(build_engine(TEST_URL))()
        try:
            with self.assertRaises(InvalidFile):
                create_file(
                    rejected,
                    actor,
                    name="bad\x00.txt",
                    media_type="text/plain",
                    data=b"x",
                    max_bytes=FILE_LIMIT,
                    base_dir=self.storage_dir,
                )
        finally:
            rejected.close()
        self.assertEqual(self.file_count(), 0)
        self.assertEqual(self.stored_objects(), [])

        accepted = build_session_factory(build_engine(TEST_URL))()
        try:
            row = create_file(
                accepted,
                actor,
                name="t.bin",
                media_type="not a media type",
                data=b"x",
                max_bytes=FILE_LIMIT,
                base_dir=self.storage_dir,
            )
        finally:
            accepted.close()
        self.assertEqual(row.media_type, "application/octet-stream")

    def test_repeated_upgrade_keeps_files(self):
        token = self.login(STUDENT)
        uploaded = self.upload(token, b"keep me\n", "keep.txt")
        command.upgrade(alembic_config(), "head")
        download = self.client().get(
            f"/api/files/{uploaded.json['file_id']}", headers=self.auth(token)
        )
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.data, b"keep me\n")

    def test_each_method_and_path_has_one_handler(self):
        seen: dict[tuple[str, str], str] = {}
        for rule in self.app.url_map.iter_rules():
            for method in rule.methods - {"HEAD", "OPTIONS"}:
                key = (method, rule.rule)
                self.assertNotIn(key, seen, f"{key} 被多个处理器提供")
                seen[key] = rule.endpoint


class UpgradePathTest(unittest.TestCase):
    """从 0001 升级到 0002：保留原有身份数据，并可使用新 files 表。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.previous_url = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = TEST_URL
        cls.storage_dir = tempfile.mkdtemp(prefix="mvstudy-upgrade-")
        run_sql("DROP SCHEMA IF EXISTS public CASCADE")
        run_sql("CREATE SCHEMA public")
        command.upgrade(alembic_config(), "0001_platform_identity")
        cls.files_table_before = scalar_sql(
            "SELECT to_regclass('public.files') IS NOT NULL"
        )

        session = build_session_factory(build_engine(TEST_URL))()
        try:
            seed(session)
            cls.users_before = session.execute(
                text("SELECT count(*) FROM users")
            ).scalar_one()
            # 在旧版本上确认原账号仍可签发凭证，再升级到 head。
            login_use_case(
                session,
                STUDENT["login"],
                STUDENT["password"],
                "upgrade-test-secret-0123456789abcdef",
                60,
            )
        finally:
            session.close()

        command.upgrade(alembic_config(), "head")
        cls.users_after = scalar_sql("SELECT count(*) FROM users")
        cls.app = create_app(
            {
                "DATABASE_URL": TEST_URL,
                "TESTING": True,
                "FILE_STORAGE_DIR": cls.storage_dir,
                "MAX_FILE_BYTES": FILE_LIMIT,
            }
        )

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.storage_dir, ignore_errors=True)
        if cls.previous_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = cls.previous_url

    def test_upgrade_from_previous_revision_keeps_identity(self):
        self.assertFalse(self.files_table_before)
        self.assertGreater(self.users_before, 0)
        self.assertEqual(self.users_after, self.users_before)
        self.assertTrue(
            scalar_sql("SELECT to_regclass('public.files') IS NOT NULL")
        )

        client = self.app.test_client()
        login_response = client.post("/api/login", json=STUDENT)
        self.assertEqual(login_response.status_code, 200, login_response.json)
        token = login_response.json["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        payload = b"after upgrade\n"
        uploaded = client.post(
            "/api/files",
            headers=headers,
            data={"file": (BytesIO(payload), "after-upgrade.txt", "text/plain")},
            content_type="multipart/form-data",
        )
        self.assertEqual(uploaded.status_code, 201, uploaded.json)
        downloaded = client.get(
            f"/api/files/{uploaded.json['file_id']}", headers=headers
        )
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(downloaded.data, payload)


if __name__ == "__main__":
    unittest.main()
