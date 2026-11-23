"""content posts, comments, metric snapshots, engagement actions

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-24 00:00:00
"""
from alembic import op
import sqlalchemy as sa
import app.database.base


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('content_posts',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('project_id', sa.String(length=64), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('output_file', sa.String(length=1024), nullable=True),
    sa.Column('caption', sa.Text(), nullable=True),
    sa.Column('hashtags', sa.JSON(), nullable=False),
    sa.Column('created_at', app.database.base.UTCDateTime(), nullable=False),
    sa.Column('updated_at', app.database.base.UTCDateTime(), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_content_posts_project_id_projects'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_content_posts'))
    )
    with op.batch_alter_table('content_posts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_content_posts_project_id'), ['project_id'], unique=False)

    with op.batch_alter_table('posts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('content_post_id', sa.String(length=32), nullable=True))
        batch_op.create_index(batch_op.f('ix_posts_content_post_id'), ['content_post_id'], unique=False)
        batch_op.create_foreign_key(batch_op.f('fk_posts_content_post_id_content_posts'), 'content_posts', ['content_post_id'], ['id'], ondelete='CASCADE')

    op.create_table('comments',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('post_id', sa.String(length=32), nullable=False),
    sa.Column('external_id', sa.String(length=200), nullable=False),
    sa.Column('parent_external_id', sa.String(length=200), nullable=True),
    sa.Column('author_name', sa.String(length=300), nullable=True),
    sa.Column('author_external_id', sa.String(length=200), nullable=True),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('like_count', sa.Integer(), nullable=False),
    sa.Column('reply_count', sa.Integer(), nullable=False),
    sa.Column('posted_at', app.database.base.UTCDateTime(), nullable=True),
    sa.Column('fetched_at', app.database.base.UTCDateTime(), nullable=False),
    sa.Column('is_own', sa.Boolean(), nullable=False),
    sa.Column('hidden', sa.Boolean(), nullable=False),
    sa.Column('liked_by_me', sa.Boolean(), nullable=False),
    sa.Column('removed_remotely', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['post_id'], ['posts.id'], name=op.f('fk_comments_post_id_posts'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_comments')),
    sa.UniqueConstraint('post_id', 'external_id', name=op.f('uq_comments_post_id'))
    )
    with op.batch_alter_table('comments', schema=None) as batch_op:
        batch_op.create_index('ix_comments_post_posted', ['post_id', 'posted_at'], unique=False)

    op.create_table('metric_snapshots',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('post_id', sa.String(length=32), nullable=False),
    sa.Column('collected_at', app.database.base.UTCDateTime(), nullable=False),
    sa.Column('metrics', sa.JSON(), nullable=False),
    sa.ForeignKeyConstraint(['post_id'], ['posts.id'], name=op.f('fk_metric_snapshots_post_id_posts'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_metric_snapshots'))
    )
    with op.batch_alter_table('metric_snapshots', schema=None) as batch_op:
        batch_op.create_index('ix_metric_snapshots_post_time', ['post_id', 'collected_at'], unique=False)

    op.create_table('engagement_actions',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('post_id', sa.String(length=32), nullable=False),
    sa.Column('comment_external_id', sa.String(length=200), nullable=True),
    sa.Column('action', sa.String(length=32), nullable=False),
    sa.Column('outcome', sa.String(length=16), nullable=False),
    sa.Column('detail', sa.Text(), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('created_at', app.database.base.UTCDateTime(), nullable=False),
    sa.ForeignKeyConstraint(['post_id'], ['posts.id'], name=op.f('fk_engagement_actions_post_id_posts'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_engagement_actions'))
    )
    with op.batch_alter_table('engagement_actions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_engagement_actions_post_id'), ['post_id'], unique=False)


def downgrade() -> None:
    op.drop_table('engagement_actions')
    op.drop_table('metric_snapshots')
    op.drop_table('comments')
    with op.batch_alter_table('posts', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_posts_content_post_id_content_posts'), type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_posts_content_post_id'))
        batch_op.drop_column('content_post_id')
    op.drop_table('content_posts')
