"""Add sha256_hash and verification_details to documents

Revision ID: d4f89a1c23ef
Revises: cc438f2aa62c
Create Date: 2026-09-26 15:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4f89a1c23ef'
down_revision: Union[str, None] = 'cc438f2aa62c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('sha256_hash', sa.String(length=64), nullable=True))
    op.create_index(op.f('ix_documents_sha256_hash'), 'documents', ['sha256_hash'], unique=False)
    op.add_column('documents', sa.Column('verification_details', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('documents', 'verification_details')
    op.drop_index(op.f('ix_documents_sha256_hash'), table_name='documents')
    op.drop_column('documents', 'sha256_hash')
