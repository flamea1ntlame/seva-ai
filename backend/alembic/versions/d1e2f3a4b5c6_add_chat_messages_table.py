"""Add chat_messages table for conversation history and audit

Revision ID: d1e2f3a4b5c6
Revises: 0088659d92be
Create Date: 2026-09-26 12:55:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, None] = '0088659d92be'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('application_id', sa.UUID(), nullable=True),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('original_message', sa.Text(), nullable=False),
        sa.Column('normalized_message', sa.Text(), nullable=True),
        sa.Column('intent', sa.String(length=100), nullable=True),
        sa.Column('service_code', sa.String(length=100), nullable=True),
        sa.Column('corrections', sa.JSON(), nullable=True),
        sa.Column('reply', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chat_messages_user_id'), 'chat_messages', ['user_id'], unique=False)
    op.create_index(op.f('ix_chat_messages_application_id'), 'chat_messages', ['application_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_chat_messages_application_id'), table_name='chat_messages')
    op.drop_index(op.f('ix_chat_messages_user_id'), table_name='chat_messages')
    op.drop_table('chat_messages')
