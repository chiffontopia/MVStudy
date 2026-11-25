"""票 10 验收：管理页启停账号与角色权限（U3/U4）。

全部走隔离的 PostgreSQL 库与公开 HTTP 面；不使用 create_all()，不以 SQLite 替代。
运行：python -m pytest tests/test_platform_admin.py -q
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from mvstudy.app import create_app
from mvstudy.db import build_engine, build_session_factory
from mvstudy.domains.platform.seed import seed

TEST_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://mvstudy:mvstudy@127.0.0.1:5433/mvstudy_test",
)

STUDENT = {"login": "s01", "password": "Stud@123"}
TEACHER = {"login": "t02", "password": "Teach@123"}
ADMIN = {"login": "a01", "password": "Admin@123"}

ADMIN_PERMISSIONS = [
    "admin.users",
    "admin.roles",
    "case.read",
    "case.write",
    "run.create",
    "grade.write",
    "analytics.read",
]


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


class AdminTicketTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.previous_url = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = TEST_URL
        run_sql("DROP SCHEMA IF EXISTS public CASCADE")
        run_sql("CREATE SCHEMA public")
        command.upgrade(alembic_config(), "head")
        session = build_session_factory(build_engine(TEST_URL))()
        try:
            seed(session)
        finally:
            session.close()
        cls.app = create_app({"DATABASE_URL": TEST_URL, "TESTING": True})

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.previous_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = cls.previous_url

    def client(self):
        return self.app.test_client()

    def login(self, account: dict) -> str:
        response = self.client().post("/api/login", json=account)
        self.assertEqual(response.status_code, 200, response.json)
        return response.json["access_token"]

    def auth(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    def delete_user(self, login_name: str) -> None:
        run_sql("DELETE FROM users WHERE login = :login", {"login": login_name})

    def delete_role(self, role_id: str) -> None:
        run_sql("DELETE FROM roles WHERE role_id = :role_id", {"role_id": role_id})

    def test_anonymous_is_unauthenticated(self):
        client = self.client()
        self.assertEqual(client.get("/api/admin/users").status_code, 401)
        self.assertEqual(client.get("/api/admin/roles").status_code, 401)
        self.assertEqual(client.post("/api/admin/users", json={}).status_code, 401)

    def test_student_is_forbidden_on_every_admin_entry(self):
        token = self.login(STUDENT)
        client = self.client()
        headers = self.auth(token)
        self.assertEqual(client.get("/api/admin/users", headers=headers).status_code, 403)
        self.assertEqual(client.get("/api/admin/roles", headers=headers).status_code, 403)
        self.assertEqual(
            client.post(
                "/api/admin/users",
                headers=headers,
                json={"login": "x01", "display_name": "越权", "password": "Test@123", "role_id": "student"},
            ).status_code,
            403,
        )
        self.assertEqual(
            client.patch("/api/admin/users/u-s01", headers=headers, json={"enabled": False}).status_code, 403
        )
        self.assertEqual(
            client.patch("/api/admin/roles/teacher", headers=headers, json={"name": "改名"}).status_code, 403
        )

    def test_admin_lists_users_without_password_hash(self):
        token = self.login(ADMIN)
        response = self.client().get("/api/admin/users", headers=self.auth(token))
        self.assertEqual(response.status_code, 200)
        items = response.json["items"]
        self.assertGreaterEqual(len(items), 11)
        for item in items:
            self.assertEqual(set(item), {"user_id", "login", "display_name", "role_id", "enabled"})
            self.assertNotIn("password_hash", item)
        self.assertIn("s01", {item["login"] for item in items})

    def test_admin_creates_user_and_new_login_works(self):
        token = self.login(ADMIN)
        client = self.client()
        payload = {
            "login": "s99",
            "display_name": "新同学",
            "password": "Newbie@123",
            "role_id": "student",
        }
        try:
            response = client.post("/api/admin/users", headers=self.auth(token), json=payload)
            self.assertEqual(response.status_code, 201, response.json)
            created = response.json
            self.assertEqual(set(created), {"user_id", "login", "display_name", "role_id", "enabled"})
            self.assertTrue(created["user_id"])
            self.assertTrue(created["enabled"])

            login = client.post("/api/login", json={"login": "s99", "password": "Newbie@123"})
            self.assertEqual(login.status_code, 200)

            duplicate = client.post("/api/admin/users", headers=self.auth(token), json=payload)
            self.assertEqual(duplicate.status_code, 409)
            self.assertEqual(duplicate.json["error"]["code"], "login_taken")
        finally:
            self.delete_user("s99")

    def test_disabled_account_loses_access_with_old_token(self):
        token = self.login(STUDENT)
        admin = self.login(ADMIN)
        client = self.client()
        self.assertEqual(client.get("/api/me", headers=self.auth(token)).status_code, 200)
        try:
            response = client.patch(
                "/api/admin/users/u-s01", headers=self.auth(admin), json={"enabled": False}
            )
            self.assertEqual(response.status_code, 200, response.json)
            self.assertFalse(response.json["enabled"])

            self.assertEqual(client.get("/api/me", headers=self.auth(token)).status_code, 401)
            self.assertEqual(client.post("/api/login", json=STUDENT).status_code, 401)
            self.assertEqual(client.get("/api/admin/users", headers=self.auth(token)).status_code, 401)
        finally:
            client.patch("/api/admin/users/u-s01", headers=self.auth(admin), json={"enabled": True})

        self.assertEqual(client.get("/api/me", headers=self.auth(token)).status_code, 200)

    def test_role_change_takes_effect_on_next_request(self):
        token = self.login(TEACHER)
        admin = self.login(ADMIN)
        client = self.client()
        self.assertEqual(client.get("/api/classes/c2/members", headers=self.auth(token)).status_code, 200)
        try:
            response = client.patch(
                "/api/admin/users/u-t02", headers=self.auth(admin), json={"role_id": "student"}
            )
            self.assertEqual(response.status_code, 200, response.json)
            self.assertEqual(response.json["role_id"], "student")
            self.assertEqual(client.get("/api/classes/c2/members", headers=self.auth(token)).status_code, 404)
        finally:
            client.patch("/api/admin/users/u-t02", headers=self.auth(admin), json={"role_id": "teacher"})

        self.assertEqual(client.get("/api/classes/c2/members", headers=self.auth(token)).status_code, 200)

    def test_role_can_be_created_and_updated(self):
        token = self.login(ADMIN)
        client = self.client()
        try:
            invalid = client.post(
                "/api/admin/roles",
                headers=self.auth(token),
                json={"role_id": "assistant", "name": "助教", "permissions": ["case.read", "no.such"]},
            )
            self.assertEqual(invalid.status_code, 400)
            self.assertEqual(invalid.json["error"]["code"], "invalid_permission")

            created = client.post(
                "/api/admin/roles",
                headers=self.auth(token),
                json={"role_id": "assistant", "name": "助教", "permissions": ["case.read"]},
            )
            self.assertEqual(created.status_code, 201, created.json)
            self.assertEqual(created.json["permissions"], ["case.read"])

            duplicate = client.post(
                "/api/admin/roles",
                headers=self.auth(token),
                json={"role_id": "assistant", "name": "助教二", "permissions": []},
            )
            self.assertEqual(duplicate.status_code, 409)
            self.assertEqual(duplicate.json["error"]["code"], "role_exists")

            updated = client.patch(
                "/api/admin/roles/assistant",
                headers=self.auth(token),
                json={"name": "助教（改）", "permissions": ["case.read", "analytics.read"]},
            )
            self.assertEqual(updated.status_code, 200, updated.json)
            self.assertEqual(updated.json["name"], "助教（改）")
            self.assertEqual(updated.json["permissions"], ["case.read", "analytics.read"])

            listing = client.get("/api/admin/roles", headers=self.auth(token))
            self.assertEqual(listing.status_code, 200)
            saved = {item["role_id"]: item for item in listing.json["items"]}
            self.assertEqual(saved["assistant"]["permissions"], ["case.read", "analytics.read"])
            self.assertEqual(saved["admin"]["permissions"], ADMIN_PERMISSIONS)
        finally:
            self.delete_role("assistant")

    def test_permission_change_reaches_current_identity(self):
        token = self.login(ADMIN)
        client = self.client()
        try:
            client.post(
                "/api/admin/roles",
                headers=self.auth(token),
                json={"role_id": "probe", "name": "观察员", "permissions": ["case.read"]},
            )
            client.post(
                "/api/admin/users",
                headers=self.auth(token),
                json={"login": "p99", "display_name": "观察同学", "password": "Probe@123", "role_id": "probe"},
            )
            me = client.post("/api/login", json={"login": "p99", "password": "Probe@123"})
            self.assertEqual(me.status_code, 200)
            probe_token = me.json["access_token"]

            self.assertEqual(client.get("/api/me", headers=self.auth(probe_token)).json["permissions"], ["case.read"])

            client.patch(
                "/api/admin/roles/probe",
                headers=self.auth(token),
                json={"permissions": ["case.read", "analytics.read"]},
            )
            after_grant = client.get("/api/me", headers=self.auth(probe_token)).json["permissions"]
            self.assertEqual(after_grant, ["case.read", "analytics.read"])

            client.patch("/api/admin/roles/probe", headers=self.auth(token), json={"permissions": []})
            self.assertEqual(client.get("/api/me", headers=self.auth(probe_token)).json["permissions"], [])
        finally:
            self.delete_user("p99")
            self.delete_role("probe")

    def test_admin_cannot_disable_self(self):
        token = self.login(ADMIN)
        client = self.client()
        response = client.patch("/api/admin/users/u-a01", headers=self.auth(token), json={"enabled": False})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["error"]["code"], "invalid_params")
        self.assertEqual(client.get("/api/me", headers=self.auth(token)).status_code, 200)

    def test_admin_cannot_drop_own_roles_permission(self):
        token = self.login(ADMIN)
        client = self.client()
        response = client.patch(
            "/api/admin/roles/admin",
            headers=self.auth(token),
            json={"permissions": [code for code in ADMIN_PERMISSIONS if code != "admin.roles"]},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["error"]["code"], "invalid_params")
        self.assertEqual(client.get("/api/admin/roles", headers=self.auth(token)).status_code, 200)

    def test_unknown_user_or_role_is_not_found(self):
        token = self.login(ADMIN)
        client = self.client()
        missing_user = client.patch("/api/admin/users/u-nobody", headers=self.auth(token), json={"enabled": False})
        self.assertEqual(missing_user.status_code, 404)
        self.assertEqual(missing_user.json["error"]["code"], "not_found")
        missing_role = client.patch("/api/admin/roles/nobody", headers=self.auth(token), json={"name": "无人"})
        self.assertEqual(missing_role.status_code, 404)

    def test_invalid_or_unsupported_fields_are_rejected(self):
        token = self.login(ADMIN)
        client = self.client()
        headers = self.auth(token)
        self.assertEqual(client.post("/api/admin/users", headers=headers, json={}).status_code, 400)
        self.assertEqual(
            client.post(
                "/api/admin/users",
                headers=headers,
                json={"login": "s98", "display_name": "缺口令", "role_id": "student"},
            ).status_code,
            400,
        )
        self.assertEqual(
            client.post(
                "/api/admin/users",
                headers=headers,
                json={"login": "s98", "display_name": "角色不存在", "password": "Test@123", "role_id": "ghost"},
            ).status_code,
            400,
        )
        self.assertEqual(
            client.patch("/api/admin/users/u-s01", headers=headers, json={"password": "hacked"}).status_code, 400
        )
        self.assertEqual(client.patch("/api/admin/users/u-s01", headers=headers, json={}).status_code, 400)
        self.assertEqual(
            client.patch("/api/admin/roles/student", headers=headers, json={"role_id": "renamed"}).status_code, 400
        )


if __name__ == "__main__":
    unittest.main()
