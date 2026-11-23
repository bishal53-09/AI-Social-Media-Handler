"""multiple media files per post

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-24 12:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ('content_posts', 'posts'):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column('media_files', sa.JSON(), nullable=False, server_default='[]'))


    with op.batch_alter_table('media_assets', schema=None) as batch_op:
        batch_op.add_column(sa.Column('display_name', sa.String(length=200), nullable=True))


def downgrade() -> None:
    for table in ('content_posts', 'posts'):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column('media_files')
    with op.batch_alter_table('media_assets', schema=None) as batch_op:
        batch_op.drop_column('display_name')
