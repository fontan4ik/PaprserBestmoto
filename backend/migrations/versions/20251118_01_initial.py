"""Initial schema for Parser Bestmoto platform.

Revision ID: 20251118_01
Revises:
Create Date: 2025-11-18 17:35:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as pg


# revision identifiers, used by Alembic.
revision = "20251118_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("telegram_id", sa.BigInteger(), primary_key=True),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column(
            "role",
            sa.Enum("USER", "ADMIN", name="userrole"),
            nullable=False,
            server_default="USER",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("auth_date", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"])

    op.create_table(
        "parsing_tasks",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "task_type",
            sa.Enum(
                "PARSE_MARKETPLACE",
                "IMPORT_COMMERCEML",
                "MATCH_PRODUCTS",
                "EXPORT_GOOGLE",
                "FULL_BACKUP",
                name="tasktype",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("pending", "processing", "completed", "failed", "cancelled", name="taskstatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_percentage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_payload", sa.JSON(), nullable=True),
        sa.Column("result_data", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.telegram_id"], ondelete="CASCADE"),
    )
    op.create_index("ix_parsing_tasks_user_id", "parsing_tasks", ["user_id"])
    op.create_index("ix_parsing_tasks_task_type", "parsing_tasks", ["task_type"])

    op.create_table(
        "archived_tasks",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "task_type",
            sa.Enum(
                "PARSE_MARKETPLACE",
                "IMPORT_COMMERCEML",
                "MATCH_PRODUCTS",
                "EXPORT_GOOGLE",
                "FULL_BACKUP",
                name="tasktype",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("pending", "processing", "completed", "failed", "cancelled", name="taskstatus"),
            nullable=False,
        ),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("result_data", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("archived_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_archived_tasks_user_id", "archived_tasks", ["user_id"])
    op.create_index("ix_archived_tasks_task_type", "archived_tasks", ["task_type"])
    op.create_index("ix_archived_tasks_archived_at", "archived_tasks", ["archived_at"])

    op.create_table(
        "uploaded_files",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("upload_date", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.telegram_id"], ondelete="CASCADE"),
    )
    op.create_index("ix_uploaded_files_user_id", "uploaded_files", ["user_id"])

    op.create_table(
        "product_mappings",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("source_product_id", sa.String(length=255), nullable=False),
        sa.Column("matched_product_id", sa.String(length=255), nullable=True),
        sa.Column("confidence_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.telegram_id"], ondelete="SET NULL"),
    )
    op.create_index("ix_product_mappings_source_product_id", "product_mappings", ["source_product_id"])
    op.create_index("ix_product_mappings_matched_product_id", "product_mappings", ["matched_product_id"])

    op.create_table(
        "task_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False, server_default="INFO"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["task_id"], ["parsing_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.telegram_id"], ondelete="SET NULL"),
    )
    op.create_index("ix_task_logs_task_id", "task_logs", ["task_id"])

    op.create_table(
        "export_history",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("task_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("sheet_id", sa.String(length=128), nullable=False),
        sa.Column("sheet_url", sa.String(length=512), nullable=False),
        sa.Column("sheet_tab_name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="completed"),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.telegram_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["parsing_tasks.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_export_history_task_id", "export_history", ["task_id"])


def downgrade() -> None:
    op.drop_table("archived_tasks")
    op.drop_table("export_history")
    op.drop_table("task_logs")
    op.drop_table("product_mappings")
    op.drop_table("uploaded_files")
    op.drop_table("parsing_tasks")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS userrole")
    op.execute("DROP TYPE IF EXISTS tasktype")
    op.execute("DROP TYPE IF EXISTS taskstatus")

