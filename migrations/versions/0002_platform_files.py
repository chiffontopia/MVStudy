"""platform files：受控文件元信息

Revision ID: 0002_platform_files
Revises: 0001_platform_identity
Create Date: 2026-11-23

字节存私有卷，数据库只存不可变编号、所有者与对象键。
字段依据 docs/database.md「身份、班级与文件」。
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_platform_files"
down_revision = "0001_platform_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "files",
        sa.Column("file_id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("media_type", sa.Text(), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.user_id"], name="fk_files_owner"),
        sa.PrimaryKeyConstraint("file_id"),
        sa.UniqueConstraint("storage_key", name="uq_files_storage_key"),
    )


def downgrade() -> None:
    op.drop_table("files")
