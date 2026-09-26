"""merge migration heads

Revision ID: 6cfbc105b59c
Revises: ('d1e2f3a4b5c6', 'd4f89a1c23ef')
Create Date: 2026-09-26 23:14:51.533663

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6cfbc105b59c'
down_revision: Union[str, None] = ('d1e2f3a4b5c6', 'd4f89a1c23ef')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
