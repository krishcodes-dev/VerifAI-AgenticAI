"""convert_meta_data_to_json_type

Revision ID: 5b25c89ff87e
Revises: 0957c3f9955b
Create Date: 2026-03-05 14:29:23.949813

Changes:
  - audit_logs.meta_data:        VARCHAR(2000) → JSON
  - transactions.meta_data:      VARCHAR(2000) → JSON
  - verification_tokens.meta_data: VARCHAR(500) → JSON

The USING clause safely converts existing VARCHAR data:
  - Valid JSON strings → cast directly via ::json
  - NULL values → remain NULL (no data loss)
  - Invalid JSON strings (if any) → cast fails and the migration rolls back,
    which is the correct behaviour (data integrity takes priority).

If the migration fails on existing data, inspect rows with:
  SELECT id, meta_data FROM <table> WHERE meta_data IS NOT NULL
    AND meta_data !~ '^[{\\[\"truefalsnul0-9]';
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5b25c89ff87e'
down_revision: Union[str, None] = '0957c3f9955b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # audit_logs.meta_data: VARCHAR(2000) → JSON
    # The USING clause tells PostgreSQL how to cast existing rows.
    # NULL rows are preserved as NULL automatically.
    op.alter_column(
        'audit_logs', 'meta_data',
        existing_type=sa.VARCHAR(length=2000),
        type_=sa.JSON(),
        existing_nullable=True,
        postgresql_using="meta_data::json",
    )

    # transactions.meta_data: VARCHAR(2000) → JSON
    op.alter_column(
        'transactions', 'meta_data',
        existing_type=sa.VARCHAR(length=2000),
        type_=sa.JSON(),
        existing_nullable=True,
        postgresql_using="meta_data::json",
    )

    # verification_tokens.meta_data: VARCHAR(500) → JSON
    op.alter_column(
        'verification_tokens', 'meta_data',
        existing_type=sa.VARCHAR(length=500),
        type_=sa.JSON(),
        existing_nullable=True,
        postgresql_using="meta_data::json",
    )


def downgrade() -> None:
    # JSON → VARCHAR (cast back using ::text)
    op.alter_column(
        'verification_tokens', 'meta_data',
        existing_type=sa.JSON(),
        type_=sa.VARCHAR(length=500),
        existing_nullable=True,
        postgresql_using="meta_data::text",
    )
    op.alter_column(
        'transactions', 'meta_data',
        existing_type=sa.JSON(),
        type_=sa.VARCHAR(length=2000),
        existing_nullable=True,
        postgresql_using="meta_data::text",
    )
    op.alter_column(
        'audit_logs', 'meta_data',
        existing_type=sa.JSON(),
        type_=sa.VARCHAR(length=2000),
        existing_nullable=True,
        postgresql_using="meta_data::text",
    )
