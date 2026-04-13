"""Tournament play: question_ids, time_ms, tournament_answer

Revision ID: f8a2b1c0d9e3
Revises: 165aef838541
Create Date: 2026-04-13"""
from alembic import op
import sqlalchemy as sa

revision = 'f8a2b1c0d9e3'
down_revision = '165aef838541'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'tournament_answer',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tournament_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('question_id', sa.Integer(), nullable=False),
        sa.Column('answer', sa.Boolean(), nullable=True),
        sa.Column('correct', sa.Boolean(), nullable=False),
        sa.Column('response_time_ms', sa.Integer(), nullable=False),
        sa.Column('points_earned', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['question_id'], ['question.id']),
        sa.ForeignKeyConstraint(['tournament_id'], ['tournament.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tournament_id', 'user_id', 'question_id', name='uq_tournament_answer_user_q'),
    )
    with op.batch_alter_table('tournament', schema=None) as batch_op:
        batch_op.add_column(sa.Column('question_ids', sa.JSON(), nullable=True))
    with op.batch_alter_table('tournament_entry', schema=None) as batch_op:
        batch_op.add_column(sa.Column('time_ms', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('tournament_entry', schema=None) as batch_op:
        batch_op.drop_column('time_ms')
    with op.batch_alter_table('tournament', schema=None) as batch_op:
        batch_op.drop_column('question_ids')
    op.drop_table('tournament_answer')
